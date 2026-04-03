import logging
import json
from datetime import datetime, timezone
from telegram.ext import filters, CommandHandler, MessageHandler, CallbackQueryHandler
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy.orm import Session
from database.database import get_db, get_or_create_user
from models import Lancamento
from .gamification_utils import give_xp_for_action, touch_user_interaction
import config
from .states import AUDIO_CONFIRMATION_STATE

logger = logging.getLogger(__name__)

async def _reply_with_audio_summary(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    """Envia o resumo da transação extraída do áudio com botões inline."""
    dados_ia = context.user_data.get('dados_audio')
    if not dados_ia:
        return

    tipo_atual = dados_ia.get('tipo_transacao', 'Saída')
    tipo_emoji = "🔴" if tipo_atual == 'Saída' else "🟢"
    novo_tipo_texto = "Marcar como Entrada" if tipo_atual == 'Saída' else "Marcar como Saída"
    
    try:
        valor_float = float(dados_ia.get('valor_total', 0.0))
    except (ValueError, TypeError):
        valor_float = 0.0
    
    msg_texto = (
        f"🎙️ <b>Lançamentos via Áudio Identificado</b>\n\n"
        f"📍 <b>Descrição:</b> {dados_ia.get('nome_estabelecimento', 'N/A')}\n"
        f"{tipo_emoji} <b>Valor:</b> R$ {valor_float:.2f} ({tipo_atual})\n"
        f"📅 <b>Data:</b> {dados_ia.get('data', 'N/A')}\n"
        f"💳 <b>Forma de Pagto:</b> {dados_ia.get('forma_pagamento', 'N/A')}\n"
        f"🏷️ <b>Sugestões (Baseadas em IA):</b>\n"
        f"  • Categoria: {dados_ia.get('categoria_sugerida', 'N/A')}\n"
        f"\nConfirma o salvamento?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Confirmar Lançamento", callback_data="audio_salvar")],
        [InlineKeyboardButton(f"🔄 {novo_tipo_texto}", callback_data="audio_toggle_type")],
        [InlineKeyboardButton("❌ Descartar", callback_data="audio_cancelar")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update_or_query, 'message') and update_or_query.message:
        await update_or_query.message.reply_text(msg_texto, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update_or_query.edit_message_text(msg_texto, parse_mode='HTML', reply_markup=reply_markup)


async def handle_audio_expense(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe o áudio (VOICE), envia para o Gemini 2.5 Flash, e processa."""
    logger.info("🎙️ Iniciando processamento de áudio para lançamento...")
    await touch_user_interaction(update.effective_user.id, context)
    
    if not config.GEMINI_API_KEY:
        await update.message.reply_text("❌ A Chave do Gemini não está configurada.")
        return ConversationHandler.END

    message_wait = await update.message.reply_text("🎧 Escutando áudio e processando (Gemini 2.5)...")
    
    try:
        # Obter o arquivo de áudio (suporte para voice message ou audio enviado como file)
        voice_or_audio = update.message.voice or update.message.audio
        
        if not voice_or_audio:
            await message_wait.edit_text("❌ Não consegui encontrar o áudio na sua mensagem.")
            return ConversationHandler.END

        telegram_file = await voice_or_audio.get_file()
        file_bytearray = await telegram_file.download_as_bytearray()
        audio_bytes = bytes(file_bytearray)
        
        logger.info(f"✅ Áudio baixado: {len(audio_bytes)} bytes")
        
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\""))
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        hoje_str = datetime.now(timezone.utc).strftime('%d/%m/%Y')
        prompt = f"""
        Você é um assistente financeiro altamente inteligente. O usuário me enviou este áudio narrando um lançamento financeiro.
        Sua tarefa é transcrever o conteúdo do áudio, interpretar os dados e retornar EXCLUSIVAMENTE um objeto JSON com as informações, e NADA MAIS. Não use bloco de código Markdown. Retorne só o JSON purista.
        
        A data de hoje (referência para extrações de tempo) é: {hoje_str}
        
        JSON OBRIGATÓRIO (use estas chaves exatas):
        {{
            "nome_estabelecimento": "string (ex: Padaria do Zé, Conta de Luz)",
            "valor_total": float (ex: 25.50),
            "tipo_transacao": "Saída" ou "Entrada",
            "forma_pagamento": "string (ex: Pix, Cartão de Crédito, Dinheiro, N/A)",
            "data": "DD/MM/YYYY (infira baseando-se no {hoje_str})",
            "categoria_sugerida": "string (ex: Alimentação, Transporte, Moradia, N/A)"
        }}
        """
        
        logger.info("🤖 Enviando para Gemini...")
        response = model.generate_content([
            prompt,
            {
                "mime_type": voice_or_audio.mime_type or "audio/ogg",
                "data": audio_bytes
            }
        ])
        
        if not response or not response.text:
            raise Exception("Resposta vazia da IA Gemini.")
            
        texto_limpo = response.text.replace('```json', '').replace('```', '').strip()
        logger.info(f"💡 Resposta do Gemini (Limpa): {texto_limpo}")
        
        dados_ia = json.loads(texto_limpo)
        
        if not isinstance(dados_ia, dict) or "valor_total" not in dados_ia:
            raise ValueError("O formato JSON extraído é inválido ou faltando chaves.")
            
        context.user_data['dados_audio'] = dados_ia
        
        await message_wait.delete()
        await _reply_with_audio_summary(update, context)
        return AUDIO_CONFIRMATION_STATE
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar áudio no Gemini: {e}", exc_info=True)
        await message_wait.edit_text("❌ Falha ao processar o áudio. O modelo pode não ter entendido seu áudio ou ocorreu um problema na rede.")
        return ConversationHandler.END


async def audio_action_processor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lida com os callbacks de salvar ou cancelar o lançamento do áudio."""
    query = update.callback_query
    action = query.data
    dados = context.user_data.get('dados_audio')
    
    if not dados and action != 'audio_cancelar':
        await query.answer("Erro: Dados do áudio perdidos na sessão.", show_alert=True)
        return ConversationHandler.END

    if action == "audio_toggle_type":
        dados['tipo_transacao'] = 'Entrada' if dados.get('tipo_transacao') == 'Saída' else 'Saída'
        context.user_data['dados_audio'] = dados
        await _reply_with_audio_summary(query, context)
        return AUDIO_CONFIRMATION_STATE

    if action == "audio_cancelar":
        await query.edit_message_text("❌ Lançamento via áudio cancelado.")
        context.user_data.pop('dados_audio', None)
        return ConversationHandler.END

    if action == "audio_salvar":
        await query.edit_message_text("💾 Registrando no banco de dados...")
        
        try:
            db: Session = next(get_db())
            usuario_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)
            
            data_str = dados.get('data', datetime.now().strftime('%d/%m/%Y'))
            try:
                data_obj = datetime.strptime(data_str, '%d/%m/%Y')
            except ValueError:
                data_obj = datetime.now()
            
            try:
                valor_float = float(dados.get('valor_total', 0))
            except (ValueError, TypeError):
                valor_float = 0.0
                
            novo_lancamento = Lancamento(
                id_usuario=usuario_db.id,
                descricao=dados.get('nome_estabelecimento', 'Lançamento via Áudio'),
                valor=valor_float,
                tipo=dados.get('tipo_transacao', 'Saída'),
                data_transacao=data_obj,
                forma_pagamento=dados.get('forma_pagamento', 'N/A')
            )
            
            db.add(novo_lancamento)
            db.commit()
            try:
                await give_xp_for_action(query.from_user.id, "LANCAMENTO_AUDIO", context)
            except Exception:
                logger.debug("Falha ao conceder XP do lancamento por audio (nao critico).")
            
            await query.edit_message_text(f"✅ Sucesso!\nLançamento **'{novo_lancamento.descricao}'** de R$ {novo_lancamento.valor:.2f} foi salvo.", parse_mode='Markdown')
        except Exception as e:
            db.rollback()
            logger.error(f"Erro ao salvar do áudio: {e}", exc_info=True)
            await query.edit_message_text("❌ Erro interno ao salvar o lançamento no banco de dados. Tente usar o /lancamento manual.")
        finally:
            # Em sqlalchemy scoped session com next(get_db()), o finally lá do generator cuidaria disso.
            pass
            
        context.user_data.pop('dados_audio', None)
        return ConversationHandler.END

    return AUDIO_CONFIRMATION_STATE

audio_conv = ConversationHandler(
    entry_points=[
        MessageHandler(filters.VOICE | filters.AUDIO, handle_audio_expense)
    ],
    states={
        AUDIO_CONFIRMATION_STATE: [
            CallbackQueryHandler(audio_action_processor, pattern='^audio_')
        ]
    },
    fallbacks=[
        CommandHandler(['cancelar', 'cancel', 'sair', 'parar'], lambda u, c: ConversationHandler.END),
        MessageHandler(filters.Regex(r'(?i)^/?\s*(cancelar|cancel|sair|parar)$'), lambda u, c: ConversationHandler.END)
    ],
    per_message=False,
    per_user=True,
    per_chat=True
)
