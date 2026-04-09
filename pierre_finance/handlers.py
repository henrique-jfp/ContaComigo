from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, 
    MessageHandler, 
    filters, 
    ConversationHandler, 
    ContextTypes, 
    CallbackQueryHandler
)
from database.database import get_db
from models import Usuario
import logging
from .sync import sincronizar_open_finance

# Estados da conversação
CHOOSING_ACTION, ASK_KEY = range(2)

async def sincronizar_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /sincronizar_banco para forçar a leitura do Open Finance."""
    user_id = update.effective_user.id
    msg = await update.message.reply_text("🔄 <i>Sincronizando seus dados bancários... Aguarde.</i>", parse_mode='HTML')
    
    db = next(get_db())
    try:
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
    finally:
        db.close()

async def start_pierre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia a conversa secreta com botões de ação."""
    keyboard = [
        [
            InlineKeyboardButton("📖 Como conectar", callback_data="pierre_tutorial"),
            InlineKeyboardButton("🔑 Conectar Chave sk-", callback_data="pierre_input_key")
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="pierre_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🤫 <b>Você encontrou a Conexão Direta (Open Finance).</b>\n\n"
        "Ao vincular sua conta do Pierre Finance, o Alfredo ganha superpoderes:\n"
        "• Leitura de saldos reais de todos os seus bancos.\n"
        "• Visão de faturas fechadas e parcelamentos futuros.\n"
        "• Categorização automática sem que você precise digitar nada.\n\n"
        "O que deseja fazer?",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return CHOOSING_ACTION

async def show_tutorial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra o passo a passo para obter a chave."""
    query = update.callback_query
    await query.answer()

    tutorial_text = (
        "📖 <b>Passo a Passo para Conectar seu Banco:</b>\n\n"
        "1️⃣ Baixe o app <b>Pierre Finance</b> na Play Store ou App Store.\n"
        "2️⃣ Dentro do app Pierre, conecte suas contas bancárias e cartões (via Open Finance).\n"
        "3️⃣ Acesse o site <a href='https://pierre.finance/api-key'>pierre.finance/api-key</a> pelo navegador.\n"
        "4️⃣ Faça login e copie a sua <b>API Key</b> (ela começa com 'sk-').\n"
        "5️⃣ Volte aqui e clique no botão <b>'Conectar Chave sk-'</b> para colar o código."
    )

    keyboard = [
        [InlineKeyboardButton("🔑 Entendi, quero conectar a chave", callback_data="pierre_input_key")],
        [InlineKeyboardButton("❌ Sair", callback_data="pierre_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(tutorial_text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
    return CHOOSING_ACTION

async def request_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pede ao usuário para enviar a chave sk-."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔑 <b>Perfeito! Agora envie sua chave sk- abaixo.</b>\n\n"
        "Sua chave será salva de forma segura e a mensagem com o código será destruída por segurança.",
        parse_mode='HTML'
    )
    return ASK_KEY

async def receive_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe e salva a chave."""
    # Sanitização profunda
    chave = update.message.text.strip().replace("\u200b", "").replace("\u200c", "").replace(" ", "")
    user_id = update.effective_user.id
    
    # Validação básica
    if not chave.startswith("sk-"):
        await update.message.reply_text("❌ Chave inválida. Ela deve começar com 'sk-'. Operação cancelada.")
        return ConversationHandler.END

    # Salva no banco de dados
    db = next(get_db())
    try:
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
                "✅ <b>Conexão Direta Estabelecida com Sucesso!</b>\n\n"
                "A partir de agora, o Alfredo monitora seus bancos em tempo real. "
                "Para manter tudo atualizado, o Alfredo sincroniza seus dados periodicamente, "
                "mas você pode forçar uma atualização a qualquer momento usando /sincronizar_banco.\n\n"
                "<b>Tente perguntar agora:</b>\n"
                "• <i>'Qual meu saldo total em todos os bancos?'</i>\n"
                "• <i>'Quanto eu já gastei no cartão este mês?'</i>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Usuário não encontrado no banco de dados.")
    finally:
        db.close()

    return ConversationHandler.END

async def cancel_pierre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela a operação via botão ou comando."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Operação cancelada. Quando precisar, use /pierre novamente.")
    else:
        await update.message.reply_text("Operação cancelada.")
    return ConversationHandler.END

def get_pierre_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('pierre', start_pierre)],
        states={
            CHOOSING_ACTION: [
                CallbackQueryHandler(show_tutorial, pattern="^pierre_tutorial$"),
                CallbackQueryHandler(request_key, pattern="^pierre_input_key$"),
                CallbackQueryHandler(cancel_pierre, pattern="^pierre_cancel$")
            ],
            ASK_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_key)],
        },
        fallbacks=[CommandHandler('cancel', cancel_pierre), CallbackQueryHandler(cancel_pierre, pattern="^pierre_cancel$")],
    )