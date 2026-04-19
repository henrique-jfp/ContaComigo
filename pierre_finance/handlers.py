from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, 
    MessageHandler, 
    filters, 
    ConversationHandler, 
    ContextTypes, 
    CallbackQueryHandler
)
from database.database import get_db, get_or_create_user
from models import Usuario
import logging
import asyncio
from .sync import sincronizar_carga_inicial, sincronizar_incremental
from .categorizador_llm import pipeline_categorizacao_pos_ingestao, processar_fallback_outros_llm
from .categorizador import aplicar_regras_lancamentos_open_finance

# Estados da conversação
CHOOSING_ACTION, ASK_KEY = range(2)

logger = logging.getLogger(__name__)


async def _pipeline_categorizacao_em_segundo_plano(usuario_id: int) -> None:
    """Nova sessão DB — regras + LLM após ingestão; não compartilha sessão com o handler."""
    db = next(get_db())
    try:
        res = await pipeline_categorizacao_pos_ingestao(db, usuario_id)
        logger.info(
            "Pipeline pós-ingestão (Open Finance) usuário %s: regras=%s llm=%s",
            usuario_id,
            res.get("regras"),
            res.get("llm"),
        )
    except Exception as e:
        logger.error("Falha no pipeline de categorização em segundo plano: %s", e, exc_info=True)
    finally:
        db.close()


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

        # Se a carga inicial nunca foi feita ou deu erro
        if not usuario.pierre_initial_sync_done:
            await msg.edit_text("⏳ Sua carga inicial está sendo processada ou ainda não foi concluída. Alfredo está trabalhando nisso!")
            # Tenta disparar a carga inicial se não estiver marcada como feita
            res = await sincronizar_carga_inicial(usuario, db)
            if isinstance(res, dict) and "error" not in res:
                asyncio.create_task(_pipeline_categorizacao_em_segundo_plano(usuario.id))
                await msg.edit_text(
                    f"✅ <b>Carga inicial concluída agora!</b>\n\n"
                    f"Importei <b>{res.get('lancamentos')}</b> transações. "
                    f"Categorização (regras + IA) roda em segundo plano. 🧠",
                    parse_mode='HTML',
                )
            return

        try:
            novos = await sincronizar_incremental(usuario, db)
            asyncio.create_task(_pipeline_categorizacao_em_segundo_plano(usuario.id))
            await msg.edit_text(
                f"✅ <b>Sincronização concluída!</b>\n\n"
                f"• <b>{novos}</b> novas transações importadas.\n"
                f"• Categorização (regras + IA) em segundo plano. 🧠",
                parse_mode='HTML',
            )
        except Exception as e:
            logger.error(f"Erro no sync manual: {e}")
            await msg.edit_text("❌ Ocorreu um erro na comunicação com o banco. Tente novamente mais tarde.")
    finally:
        db.close()


async def recategorizar_tudo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Reaplica todas as regras locais aos lançamentos Open Finance e, em seguida,
    envia ao LLM o que ainda estiver em Outros — sem chamar a API Pierre.
    """
    user_id = update.effective_user.id
    msg = await update.message.reply_text(
        "🔄 <i>Reaplicando regras e refinando categorias (sem sincronizar com o banco externo)...</i>",
        parse_mode="HTML",
    )
    db = next(get_db())
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
        if not usuario or not usuario.pierre_api_key:
            await msg.edit_text("❌ Open Finance não configurado. Use /pierre primeiro.")
            return
        n_regras = aplicar_regras_lancamentos_open_finance(db, usuario.id, escopo="tudo")
        n_llm = await processar_fallback_outros_llm(db, usuario.id)
        await msg.edit_text(
            f"✅ <b>Recategorização local concluída!</b>\n\n"
            f"• <b>{n_regras}</b> lançamentos atualizados pelas regras.\n"
            f"• <b>{n_llm}</b> refinados pela IA (fallback Outros).\n\n"
            f"Isso não consumiu chamadas ao Open Finance.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Erro em /recategorizar_tudo: %s", e, exc_info=True)
        await msg.edit_text("❌ Não foi possível concluir. Tente de novo em instantes.")
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
        "• Categorização automática local (sem depender da API).\n\n"
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
    """Recebe e salva a chave e dispara carga inicial."""
    chave = update.message.text.strip().replace("\u200b", "").replace("\u200c", "").replace(" ", "")
    user_id = update.effective_user.id
    
    if not chave.startswith("sk-"):
        await update.message.reply_text("❌ Chave inválida. Ela deve começar com 'sk-'. Operação cancelada.")
        return ConversationHandler.END

    db = next(get_db())
    try:
        # Busca ou recria o usuário se ele tiver sido deletado do banco
        usuario = get_or_create_user(db, user_id, update.effective_user.full_name)
        
        usuario.pierre_api_key = chave
        usuario.pierre_initial_sync_done = False # Reset obrigatório
        db.commit()
            
        try: await update.message.delete()
        except: pass
            
        status_msg = await update.message.reply_text(
            "✅ Chave salva! Iniciando carga inicial dos seus dados bancários... ⏳\nIsso pode levar alguns segundos."
        )
        
        # Carga Inicial Assíncrona
        try:
            res = await sincronizar_carga_inicial(usuario, db)
            if isinstance(res, dict) and "error" in res:
                await status_msg.edit_text("✅ Chave salva com sucesso, mas a carga inicial falhou.\nUse /sincronizar_banco para tentar novamente.")
            else:
                asyncio.create_task(_pipeline_categorizacao_em_segundo_plano(usuario.id))
                await status_msg.edit_text(
                    "✅ <b>Conexão Direta Estabelecida!</b>\n\n"
                    "📊 <b>Relatório de Importação:</b>\n"
                    f"• <b>{res.get('contas', 0)}</b> contas bancárias mapeadas\n"
                    f"• <b>{res.get('lancamentos', 0)}</b> transações importadas\n"
                    f"• Categorização (regras + IA) em segundo plano. 🧠\n\n"
                    "O Alfredo agora conhece seu histórico financeiro real. Use /sincronizar_banco para atualizações.",
                    parse_mode='HTML',
                )
        except Exception as sync_err:
            logger.error(f"Erro na carga inicial Pierre: {sync_err}", exc_info=True)
            await status_msg.edit_text("✅ Chave salva com sucesso, mas ocorreu um erro na carga inicial. Tente /sincronizar_banco em instantes.")
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
