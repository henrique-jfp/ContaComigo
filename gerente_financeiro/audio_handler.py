import logging
import json
import os
from urllib.parse import quote
from datetime import datetime, timezone
from telegram.ext import filters, CommandHandler, MessageHandler, CallbackQueryHandler
import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from database.database import get_db, get_or_create_user
from models import Categoria, Lancamento, Subcategoria
from .gamification_utils import give_xp_for_action, touch_user_interaction
import config
from .states import AUDIO_FORMA_PAGAMENTO_STATE, AUDIO_CONFIRMATION_STATE

logger = logging.getLogger(__name__)

_FORMAS_PAGAMENTO = ["Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"]


def _audio_payload_valido(dados_ia: dict) -> bool:
    try:
        valor = float(dados_ia.get('valor_total', 0) or 0)
    except (ValueError, TypeError):
        valor = 0
    nome = str(dados_ia.get('nome_estabelecimento', '') or '').strip()
    data_str = str(dados_ia.get('data', '') or '').strip()

    if valor <= 0 and (not nome or nome.upper() == 'N/A'):
        if not data_str or data_str.upper() == 'N/A':
            return False
    return True


def _normalizar_tipo(tipo: str) -> str:
    return 'Entrada' if str(tipo).strip().lower() == 'entrada' else 'Saída'


def _get_webapp_url(tab: str | None = None, draft: dict | None = None) -> str:
    base_url = os.getenv("DASHBOARD_BASE_URL", "http://localhost:5000").rstrip("/")
    url = f"{base_url}/webapp"
    params: list[str] = []
    if tab:
        params.append(f"tab={quote(tab, safe='')}")
    if draft:
        params.append(f"draft={quote(json.dumps(draft, ensure_ascii=False), safe='')}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return url


def _resolve_categoria_ids(db: Session, dados: dict) -> tuple[int | None, int | None]:
    id_categoria = None
    id_subcategoria = None

    cat_sugerida = dados.get('categoria_sugerida')
    sub_sugerida = dados.get('subcategoria_sugerida')

    if cat_sugerida:
        categoria_obj = db.query(Categoria).filter(func.lower(Categoria.nome) == func.lower(cat_sugerida)).first()
        if categoria_obj:
            id_categoria = categoria_obj.id

    if sub_sugerida and id_categoria:
        subcategoria_obj = db.query(Subcategoria).filter(
            and_(Subcategoria.id_categoria == id_categoria, func.lower(Subcategoria.nome) == func.lower(sub_sugerida))
        ).first()
        if subcategoria_obj:
            id_subcategoria = subcategoria_obj.id

    return id_categoria, id_subcategoria


def _normalizar_forma_pagamento(valor: str | None) -> str:
    raw = str(valor or "").strip().lower()
    mapa = {
        "pix": "Pix",
        "credito": "Crédito",
        "crédito": "Crédito",
        "debito": "Débito",
        "débito": "Débito",
        "boleto": "Boleto",
        "dinheiro": "Dinheiro",
        "nao informado": "Nao_informado",
        "não informado": "Nao_informado",
        "n/a": "Nao_informado",
        "": "Nao_informado",
    }
    return mapa.get(raw, "Nao_informado")


def _build_forma_keyboard() -> InlineKeyboardMarkup:
    botoes = [InlineKeyboardButton(forma, callback_data=f"audio_pag_{forma}") for forma in _FORMAS_PAGAMENTO]
    return InlineKeyboardMarkup([botoes[i:i + 2] for i in range(0, len(botoes), 2)])


async def _ensure_audio_account(update_or_query, context: ContextTypes.DEFAULT_TYPE) -> int:
    dados_ia = context.user_data.get('dados_audio')
    if not dados_ia:
        return ConversationHandler.END

    tipo_atual = _normalizar_tipo(dados_ia.get('tipo_transacao', 'Saída'))
    dados_ia['tipo_transacao'] = tipo_atual

    if dados_ia.get('forma_pagamento'):
        dados_ia['forma_pagamento'] = _normalizar_forma_pagamento(dados_ia.get('forma_pagamento'))
        context.user_data['dados_audio'] = dados_ia
        await _reply_with_audio_summary(update_or_query, context)
        return AUDIO_CONFIRMATION_STATE

    teclado = _build_forma_keyboard()
    texto = (
        "💳 <b>Escolha a forma de pagamento</b>\n\n"
        "Selecione como a transação foi paga/recebida."
    )

    if hasattr(update_or_query, 'message') and update_or_query.message:
        await update_or_query.message.reply_text(texto, parse_mode='HTML', reply_markup=teclado)
    else:
        await update_or_query.edit_message_text(texto, parse_mode='HTML', reply_markup=teclado)

    return AUDIO_FORMA_PAGAMENTO_STATE

async def _reply_with_audio_summary(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    """Envia o resumo da transação extraída do áudio com botões inline."""
    dados_ia = context.user_data.get('dados_audio')
    if not dados_ia:
        return

    tipo_atual = dados_ia.get('tipo_transacao', 'Saída')
    tipo_emoji = "🔴" if tipo_atual == 'Saída' else "🟢"
    
    try:
        valor_float = float(dados_ia.get('valor_total', 0.0))
    except (ValueError, TypeError):
        valor_float = 0.0
    
    forma_pagamento = _normalizar_forma_pagamento(dados_ia.get('forma_pagamento'))
    categoria_sugerida = dados_ia.get('categoria_sugerida', 'N/A')
    subcategoria_sugerida = dados_ia.get('subcategoria_sugerida', 'N/A')
    categoria_str = f"{categoria_sugerida} / {subcategoria_sugerida}" if subcategoria_sugerida != 'N/A' else categoria_sugerida
    msg_texto = (
        f"🧾 <b>Resumo do Lançamento</b>\n\n"
        f"📍 <b>Descrição:</b> {dados_ia.get('nome_estabelecimento', 'N/A')}\n"
        f"{tipo_emoji} <b>Valor:</b> <code>R$ {valor_float:.2f}</code> ({tipo_atual})\n"
        f"📅 <b>Data:</b> {dados_ia.get('data', 'N/A')}\n"
        f"💳 <b>Forma de pagamento:</b> {forma_pagamento}\n"
        f"🏷️ <b>Categoria:</b> {categoria_str}\n\n"
        f"Confirma o salvamento?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data="audio_salvar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="audio_cancelar")],
        [InlineKeyboardButton("✍️ Editar no Miniapp", web_app=WebAppInfo(url=_get_webapp_url("editar", draft=dados_ia)))]
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
            "forma_pagamento": "Pix, Crédito, Débito, Boleto, Dinheiro ou Nao_informado",
            "data": "DD/MM/YYYY (infira baseando-se no {hoje_str})",
            "categoria_sugerida": "string (ex: Alimentação, Transporte, Moradia, N/A)",
            "subcategoria_sugerida": "string (ex: Restaurantes, Mercado, Combustível, N/A)"
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

        if not _audio_payload_valido(dados_ia):
            await message_wait.edit_text("❌ Audio inaudivel, enviar outro audio.")
            return ConversationHandler.END

        dados_ia['tipo_transacao'] = _normalizar_tipo(dados_ia.get('tipo_transacao', 'Saída'))
            
        context.user_data['dados_audio'] = dados_ia
        
        await message_wait.delete()
        return await _ensure_audio_account(update, context)
        
    except Exception as e:
        logger.error(f"❌ Erro ao processar áudio no Gemini: {e}", exc_info=True)
        await message_wait.edit_text("❌ Audio inaudivel, enviar outro audio.")
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
        dados['tipo_transacao'] = _normalizar_tipo('Entrada' if dados.get('tipo_transacao') == 'Saída' else 'Saída')
        dados.pop('forma_pagamento', None)
        context.user_data['dados_audio'] = dados
        return await _ensure_audio_account(query, context)

    if action.startswith("audio_pag_"):
        forma = action.replace("audio_pag_", "", 1)
        dados['forma_pagamento'] = _normalizar_forma_pagamento(forma)
        context.user_data['dados_audio'] = dados
        await _reply_with_audio_summary(query, context)
        return AUDIO_CONFIRMATION_STATE

    if action.startswith("audio_conta_"):
        await query.edit_message_text("ℹ️ Fluxo antigo de conta desativado. Selecione forma de pagamento.")
        return await _ensure_audio_account(query, context)

    if action == "audio_cancelar":
        await query.edit_message_text("❌ Lançamento via áudio cancelado.")
        context.user_data.pop('dados_audio', None)
        return ConversationHandler.END

    if action == "audio_salvar":
        if not dados.get('forma_pagamento'):
            return await _ensure_audio_account(query, context)
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
                
            id_categoria, id_subcategoria = _resolve_categoria_ids(db, dados)
            novo_lancamento = Lancamento(
                id_usuario=usuario_db.id,
                descricao=dados.get('nome_estabelecimento', 'Lançamento via Áudio'),
                valor=valor_float,
                tipo=dados.get('tipo_transacao', 'Saída'),
                data_transacao=data_obj,
                forma_pagamento=_normalizar_forma_pagamento(dados.get('forma_pagamento')),
                id_categoria=id_categoria,
                id_subcategoria=id_subcategoria,
                origem="audio",
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
        AUDIO_FORMA_PAGAMENTO_STATE: [
            CallbackQueryHandler(audio_action_processor, pattern='^audio_')
        ],
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
