from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from database.database import get_db
from models import Usuario
import logging
from .sync import sincronizar_open_finance

ASK_KEY = 1

async def sincronizar_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /sincronizar_banco para forçar a leitura do Open Finance."""
    user_id = update.effective_user.id
    msg = await update.message.reply_text("🔄 <i>Sincronizando seus dados bancários... Aguarde.</i>", parse_mode='HTML')
    
    with get_db() as db:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario or not usuario.pierre_api_key:
            await msg.edit_text("❌ Você ainda não configurou o Open Finance. Use /pierre primeiro.")
            return

        try:
            novos = await sincronizar_open_finance(usuario, db)
            if novos is not None:
                await msg.edit_text(f"✅ <b>Sincronização concluída!</b>\n\nEncontrei <b>{novos}</b> novas transações que já foram categorizadas pelo Alfredo.", parse_mode='HTML')
            else:
                await msg.edit_text("❌ Ocorreu um erro na comunicação com o banco. Tente novamente mais tarde.")
        except Exception as e:
            logging.error(f"Erro no sync manual: {e}")
            await msg.edit_text("❌ Erro inesperado ao sincronizar.")

async def start_pierre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia a conversa secreta."""
    await update.message.reply_text(
        "🤫 <i>Olá... Vejo que você encontrou a porta dos fundos.</i>\n\n"
        "Se você possui a <b>Chave de Acesso (sk-...)</b> para o Open Finance, envie-a abaixo.\n"
        "Sua chave será salva e esta mensagem será destruída.",
        parse_mode='HTML'
    )
    return ASK_KEY

async def receive_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe e salva a chave."""
    chave = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Validação básica
    if not chave.startswith("sk-"):
        await update.message.reply_text("❌ Chave inválida. Ela deve começar com 'sk-'. Operação cancelada.")
        return ConversationHandler.END

    # Salva no banco de dados
    with get_db() as db:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if usuario:
            usuario.pierre_api_key = chave
            db.commit()
            
            # Tenta apagar a mensagem com a chave por segurança
            try:
                await update.message.delete()
            except Exception as e:
                logging.warning(f"Não foi possível apagar a mensagem da chave: {e}")
                
            await update.message.reply_text(
                "✅ <b>Conexão Direta Estabelecida!</b>\n\n"
                "A partir de agora, o Alfredo pode consultar seus saldos e extratos reais. "
                "Basta perguntar: <i>'Qual meu saldo bancário?'</i>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Usuário não encontrado no banco de dados.")

    return ConversationHandler.END

async def cancel_pierre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela a operação."""
    await update.message.reply_text("Operação cancelada.")
    return ConversationHandler.END

def get_pierre_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('pierre', start_pierre)],
        states={
            ASK_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_key)],
        },
        fallbacks=[CommandHandler('cancel', cancel_pierre)],
    )