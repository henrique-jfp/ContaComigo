
from .analytics_utils import track_analytics

import logging
import json
import os
from urllib.parse import quote
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    MessageHandler,
    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

# --- CORREÇÃO: Importamos as funções do ocr_handler, mas não os estados ---
from .ocr_handler import ocr_action_processor, ocr_iniciar_como_subprocesso
from .handlers import cancel, criar_teclado_colunas
from .menu_botoes import BOTAO_FATURA
from .utils_validation import (
    validar_valor_monetario, validar_descricao,
    ask_valor_generico, ask_descricao_generica
)

from database.database import get_db, get_or_create_user
from models import Categoria, Subcategoria, Lancamento, Usuario
from .gamification_utils import give_xp_for_action, touch_user_interaction
from .states import (
    AWAITING_LAUNCH_ACTION, ASK_DESCRIPTION, ASK_VALUE, ASK_FORMA_PAGAMENTO,
    ASK_CATEGORY, ASK_SUBCATEGORY, ASK_DATA, MANUAL_CONFIRMATION_STATE, OCR_CONFIRMATION_STATE
)

logger = logging.getLogger(__name__)

_FORMAS_PAGAMENTO = ["Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"]


def _get_webapp_url(tab: str | None = None, draft: dict | None = None) -> str:
    """Gera URL do miniapp com parâmetros de rascunho para edição."""
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



# --- FUNÇÃO DE MENU REUTILIZÁVEL ---
async def show_launch_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None, new_message: bool = False):
    """
    Exibe o menu principal de lançamento de forma consistente.
    """
    text = message_text or (
        "💰 <b>Novo Lançamento</b>\n\n"
        "Como você quer registrar esta transação?\n\n"
        "📸 <b>Mais fácil:</b> Envie uma foto do cupom\n"
        "⌨️ <b>Manual:</b> Digite os dados passo a passo"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🟢 Entrada", callback_data="manual_type_Entrada"),
            InlineKeyboardButton("🔴 Saída", callback_data="manual_type_Saída")
        ],
        [InlineKeyboardButton("✅ Finalizar", callback_data="manual_finish")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Se for forçado a enviar uma nova mensagem ou se não houver um callback_query para editar
    if new_message or not (hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message):
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=text, 
            parse_mode='HTML', 
            reply_markup=reply_markup
        )
    else: # Se houver um callback_query válido, tenta editar a mensagem
        try:
            await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
        except Exception as e:
            # Fallback: se a edição falhar (ex: mensagem muito antiga), envia uma nova.
            logger.warning(f"Falha ao editar mensagem no show_launch_menu, enviando nova. Erro: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=text, 
                parse_mode='HTML', 
                reply_markup=reply_markup
            )


# --- PONTO DE ENTRADA E FLUXO PRINCIPAL ---
async def manual_entry_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o fluxo de lançamento unificado."""
    # Limpa dados de lançamentos anteriores para começar uma nova "sessão"
    context.user_data.clear()
    await touch_user_interaction(update.effective_user.id, context)
    
    await show_launch_menu(update, context)
    return AWAITING_LAUNCH_ACTION


# --- FLUXO MANUAL (INICIADO PELOS BOTÕES) ---
@track_analytics("manual_entry")
async def start_manual_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o fluxo manual após clique em 'Entrada' ou 'Saída'."""
    query = update.callback_query
    await query.answer()
    
    # Salva o tipo (Entrada/Saída)
    tipo = query.data.split('_')[-1]
    context.user_data['novo_lancamento'] = {'tipo': tipo}
    
    # Emoji baseado no tipo
    emoji = "🟢" if tipo == "Entrada" else "🔴"
    
    await query.edit_message_text(
        f"{emoji} <b>{tipo}</b>\n\n"
        f"📝 <b>Descrição:</b>\n"
        f"O que foi esta {tipo.lower()}?\n\n"
        f"💡 <i>Exemplos: Almoço no restaurante, Salário, Uber para casa</i>",
        parse_mode='HTML'
    )
    
    return ASK_DESCRIPTION

# Usando funções genéricas do utils_validation para eliminar duplicação
async def ask_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a descrição e vai direto para o valor"""
    if update.message.text.strip() == BOTAO_FATURA:
        await update.message.reply_text(
            "ℹ️ Você estava em um lançamento. Fluxo encerrado.\n"
            "Toque em 🧾 Fatura novamente para importar o PDF."
        )
        return ConversationHandler.END
    descricao_texto = update.message.text.strip()
    
    # Validação simples de descrição
    if len(descricao_texto) < 2 or len(descricao_texto) > 200:
        await update.message.reply_text(
            "⚠️ <b>Descrição muito curta ou longa</b>\n\n"
            "Use entre 2 e 200 caracteres\n"
            "💡 <i>Exemplo: Almoço no restaurante</i>",
            parse_mode='HTML'
        )
        return ASK_DESCRIPTION
    
    # Salva a descrição
    context.user_data['novo_lancamento']['descricao'] = descricao_texto
    
    # Pergunta o valor de forma mais atrativa
    tipo = context.user_data['novo_lancamento']['tipo']
    emoji = "🟢" if tipo == "Entrada" else "🔴"
    
    await update.message.reply_text(
        f"{emoji} <b>{descricao_texto}</b>\n\n"
        f"💰 <b>Qual o valor?</b>\n\n"
        f"💡 <i>Exemplos:</i>\n"
        f"• <code>150</code>\n"
        f"• <code>25.50</code>\n"
        f"• <code>1500.00</code>",
        parse_mode='HTML'
    )
    
    return ASK_VALUE

async def ask_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa o valor e vai para seleção de forma de pagamento"""
    if update.message.text.strip() == BOTAO_FATURA:
        await update.message.reply_text(
            "ℹ️ Você estava em um lançamento. Fluxo encerrado.\n"
            "Toque em 🧾 Fatura novamente para importar o PDF."
        )
        return ConversationHandler.END
    # Validação mais robusta do valor
    valor_texto = update.message.text.strip().replace('R$', '').replace(' ', '').replace(',', '.')
    
    try:
        valor = float(valor_texto)
        if valor <= 0:
            raise ValueError("Valor deve ser positivo")
    except ValueError:
        await update.message.reply_text(
            "⚠️ <b>Valor inválido</b>\n\n"
            "Digite apenas números\n\n"
            "💡 <i>Exemplos válidos:</i>\n"
            "• <code>150</code>\n"
            "• <code>25.50</code>\n"
            "• <code>1500.00</code>",
            parse_mode='HTML'
        )
        return ASK_VALUE
    
    # Salva o valor
    context.user_data['novo_lancamento']['valor'] = valor
    
    descricao = context.user_data['novo_lancamento']['descricao']
    tipo = context.user_data['novo_lancamento']['tipo']
    emoji_tipo = "🟢" if tipo == "Entrada" else "🔴"

    botoes = [InlineKeyboardButton(forma, callback_data=f"manual_pag_{forma}") for forma in _FORMAS_PAGAMENTO]
    teclado = criar_teclado_colunas(botoes, 2)

    await update.message.reply_text(
        f"{emoji_tipo} <b>{descricao}</b>\n"
        f"💰 R$ {valor:.2f}\n\n"
        "💳 <b>Qual a forma de pagamento?</b>\n"
        "Se não souber, escolha Nao_informado.",
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode='HTML'
    )

    return ASK_FORMA_PAGAMENTO

async def ask_forma_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa seleção de forma de pagamento e vai para categorias"""
    query = update.callback_query
    await query.answer()

    forma_pagamento = query.data.replace('manual_pag_', '').strip()
    context.user_data['novo_lancamento']['forma_pagamento'] = forma_pagamento if forma_pagamento in _FORMAS_PAGAMENTO else 'Nao_informado'

    # Busca categorias
    db = next(get_db())
    try:
        categorias = db.query(Categoria).order_by(Categoria.nome).all()
        
        # Cria botões para categorias
        botoes = []
        for categoria in categorias:
            botoes.append(InlineKeyboardButton(
                categoria.nome, 
                callback_data=f"manual_cat_{categoria.id}"
            ))
        
        # Adiciona opção "Sem categoria"
        botoes.append(InlineKeyboardButton("🏷️ Sem Categoria", callback_data="manual_cat_0"))
        
        teclado = criar_teclado_colunas(botoes, 2)
        
        # Resumo do que foi preenchido
        dados = context.user_data['novo_lancamento']
        tipo = dados['tipo']
        emoji_tipo = "🟢" if tipo == "Entrada" else "🔴"
        
        await query.edit_message_text(
            f"{emoji_tipo} <b>{dados['descricao']}</b>\n"
            f"💰 R$ {dados['valor']:.2f}\n"
            f"💳 {dados.get('forma_pagamento', 'Nao_informado')}\n\n"
            f"📂 <b>Categoria:</b>\n"
            f"Em que categoria se encaixa?",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode='HTML'
        )
        
        return ASK_CATEGORY
        
    finally:
        db.close()

async def ask_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa categoria e vai para subcategoria"""
    query = update.callback_query
    await query.answer()
    
    category_id = int(query.data.split('_')[-1])
    
    if category_id == 0:
        # Sem categoria - pula para data
        context.user_data['novo_lancamento']['id_categoria'] = None
        context.user_data['novo_lancamento']['id_subcategoria'] = None
        return await ask_data_directly(update, context)
    
    context.user_data['novo_lancamento']['id_categoria'] = category_id
    
    # Busca subcategorias da categoria selecionada
    db = next(get_db())
    try:
        categoria = db.query(Categoria).filter(Categoria.id == category_id).first()
        subcategorias = db.query(Subcategoria).filter(Subcategoria.id_categoria == category_id).order_by(Subcategoria.nome).all()
        
        if not subcategorias:
            # Sem subcategorias - pula para data
            context.user_data['novo_lancamento']['id_subcategoria'] = None
            return await ask_data_directly(update, context, categoria.nome)
        
        # Cria botões para subcategorias
        botoes = []
        for subcategoria in subcategorias:
            botoes.append(InlineKeyboardButton(
                subcategoria.nome, 
                callback_data=f"manual_subcat_{subcategoria.id}"
            ))
        
        # Adiciona opção "Sem subcategoria"
        botoes.append(InlineKeyboardButton("🏷️ Sem Subcategoria", callback_data="manual_subcat_0"))
        
        teclado = criar_teclado_colunas(botoes, 2)
        
        # Resumo do que foi preenchido
        dados = context.user_data['novo_lancamento']
        tipo = dados['tipo']
        emoji_tipo = "🟢" if tipo == "Entrada" else "🔴"
        
        await query.edit_message_text(
            f"{emoji_tipo} <b>{dados['descricao']}</b>\n"
            f"💰 R$ {dados['valor']:.2f}\n"
            f"📂 {categoria.nome}\n\n"
            f"🏷️ <b>Subcategoria:</b>\n"
            f"Escolha uma subcategoria mais específica:",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode='HTML'
        )
        
        return ASK_SUBCATEGORY
        
    finally:
        db.close()

async def ask_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa subcategoria e vai para data"""
    query = update.callback_query
    await query.answer()
    
    subcategory_id = int(query.data.split('_')[-1])
    
    if subcategory_id == 0:
        context.user_data['novo_lancamento']['id_subcategoria'] = None
        subcategoria_nome = None
    else:
        context.user_data['novo_lancamento']['id_subcategoria'] = subcategory_id
        # Busca nome da subcategoria
        db = next(get_db())
        try:
            subcategoria = db.query(Subcategoria).filter(Subcategoria.id == subcategory_id).first()
            subcategoria_nome = subcategoria.nome if subcategoria else None
        finally:
            db.close()
    
    return await ask_data_directly(update, context, subcategoria_nome)

async def ask_data_directly(update, context, categoria_nome=None, subcategoria_nome=None):
    """Função auxiliar para pedir a data diretamente"""
    dados = context.user_data['novo_lancamento']
    tipo = dados['tipo']
    emoji_tipo = "🟢" if tipo == "Entrada" else "🔴"
    
    # Busca nome da categoria se não foi fornecido
    if categoria_nome is None and dados.get('id_categoria'):
        db = next(get_db())
        try:
            categoria = db.query(Categoria).filter(Categoria.id == dados['id_categoria']).first()
            categoria_nome = categoria.nome if categoria else "Sem categoria"
        finally:
            db.close()
    elif categoria_nome is None:
        categoria_nome = "Sem categoria"
    
    # Monta texto da categoria/subcategoria
    categoria_texto = categoria_nome
    if subcategoria_nome:
        categoria_texto += f" → {subcategoria_nome}"
    
    # Pergunta a data
    texto = (
        f"{emoji_tipo} <b>{dados['descricao']}</b>\n"
        f"💰 R$ {dados['valor']:.2f}\n"
        f"📂 {categoria_texto}\n\n"
        f"📅 <b>Data da transação:</b>\n"
        f"Digite a data ou 'hoje' para usar hoje\n\n"
        f"💡 <i>Formato: DD/MM/AAAA</i>\n"
        f"Exemplo: <code>15/01/2025</code> ou <code>hoje</code>"
    )
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(texto, parse_mode='HTML')
    else:
        await update.message.reply_text(texto, parse_mode='HTML')
    
    return ASK_DATA

async def save_manual_lancamento_and_return(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida a data e mostra um card de confirmação antes de salvar."""
    if 'novo_lancamento' not in context.user_data:
        await update.message.reply_text("❌ Fluxo expirado ou corrompido. Use /cancelar e tente novamente.")
        return ConversationHandler.END

    data_texto = update.message.text.lower().strip()
    
    try:
        if data_texto == 'hoje':
            data_transacao = datetime.now()
        else:
            data_transacao = datetime.strptime(data_texto, '%d/%m/%Y')
        context.user_data['novo_lancamento']['data_transacao'] = data_transacao
    except ValueError:
        await update.message.reply_text(
            "⚠️ <b>Data inválida</b>\n\n"
            "Use o formato <code>DD/MM/AAAA</code> ou digite <code>hoje</code>\n\n"
            "💡 <i>Exemplos:</i>\n"
            "• <code>15/01/2025</code>\n"
            "• <code>hoje</code>",
            parse_mode='HTML'
        )
        return ASK_DATA

    # Mostra card de confirmação antes de salvar
    dados = context.user_data['novo_lancamento']
    tipo = dados['tipo']
    emoji_tipo = "🟢" if tipo == "Entrada" else "🔴"
    data_formatada = data_transacao.strftime('%d/%m/%Y')
    
    msg_confirmacao = (
        f"🧾 <b>Confirmar Lançamento?</b>\n\n"
        f"{emoji_tipo} <b>{dados['descricao']}</b>\n"
        f"💰 <code>R$ {dados['valor']:.2f}</code>\n"
        f"💳 {dados['forma_pagamento']}\n"
        f"🏷️ {dados.get('categoria_nome', 'Sem categoria')}\n"
        f"📅 {data_formatada}"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data="manual_confirmar")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="manual_cancelar")],
        [InlineKeyboardButton("✍️ Editar no Miniapp", web_app=WebAppInfo(url=_get_webapp_url("editar", draft=dados)))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg_confirmacao, parse_mode='HTML', reply_markup=reply_markup)
    return MANUAL_CONFIRMATION_STATE


async def manual_confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a confirmação do lançamento manual."""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "manual_cancelar":
        await query.edit_message_text("❌ Lançamento cancelado.")
        await show_launch_menu(update, context, new_message=True)
        return AWAITING_LAUNCH_ACTION
    
    if action != "manual_confirmar":
        return MANUAL_CONFIRMATION_STATE
    
    # Salvar no banco
    db = next(get_db())
    try:
        user_info = update.effective_user
        usuario_db = get_or_create_user(db, user_info.id, user_info.full_name)
        dados = context.user_data['novo_lancamento']
        
        novo_lancamento = Lancamento(id_usuario=usuario_db.id, origem="manual", **dados)
        db.add(novo_lancamento)
        db.commit()
        
        try:
            await give_xp_for_action(update.effective_user.id, "LANCAMENTO_MANUAL", context)
        except Exception:
            logger.debug("Falha ao conceder XP do lancamento manual (nao critico).")
        
        tipo = dados['tipo']
        emoji_tipo = "🟢" if tipo == "Entrada" else "🔴"
        
        confirmacao = (
            f"✅ <b>Lançamento Salvo com Sucesso!</b>\n\n"
            f"{emoji_tipo} <b>{dados['descricao']}</b>\n"
            f"💰 R$ {dados['valor']:.2f}\n"
            f"📅 {dados['data_transacao'].strftime('%d/%m/%Y')}"
        )
        
        await query.edit_message_text(confirmacao, parse_mode='HTML')
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar lançamento manual: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ <b>Erro ao salvar</b>\n\n"
            "Algo deu errado. Tente novamente.",
            parse_mode='HTML'
        )
    finally:
        db.close()
        context.user_data.pop('novo_lancamento', None)

    # Volta para o menu principal
    await show_launch_menu(update, context, new_message=True)
    return AWAITING_LAUNCH_ACTION


# --- FLUXO DE OCR (INICIADO POR ARQUIVO) ---
async def ocr_flow_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ponto de entrada para o fluxo de OCR quando um arquivo é enviado."""
    # Chama a função de processamento do OCR
    await ocr_action_processor(update, context)

async def ocr_confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    action = query.data
    await ocr_action_processor(update, context)
    
    if action in ["ocr_salvar", "ocr_cancelar"]:
        await query.message.delete()
        msg = "✅ Lançamento por OCR salvo! O que vamos registrar agora?" if action == "ocr_salvar" else "Lançamento por OCR cancelado. O que deseja fazer?"
        await show_launch_menu(update, context, message_text=msg, new_message=True)
        return AWAITING_LAUNCH_ACTION
    
    return OCR_CONFIRMATION_STATE


# --- FUNÇÃO DE ENCERRAMENTO ---
async def finish_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Sessão de lançamentos concluída.")
    context.user_data.clear()
    return ConversationHandler.END


# --- HANDLER UNIFICADO ---
manual_entry_conv = ConversationHandler(
    entry_points=[CommandHandler('lancamento', manual_entry_start)
, MessageHandler(filters.Regex(r"^💳 Lançamento$"), manual_entry_start)],
    states={
        AWAITING_LAUNCH_ACTION: [
            CallbackQueryHandler(start_manual_flow, pattern='^manual_type_'),
            CallbackQueryHandler(finish_flow, pattern='^manual_finish$'),
            MessageHandler(filters.PHOTO | filters.Document.IMAGE | filters.Document.MimeType("application/pdf"), ocr_iniciar_como_subprocesso),
        ],
        ASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_description)],
        ASK_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_value)],
        ASK_FORMA_PAGAMENTO: [CallbackQueryHandler(ask_forma_pagamento, pattern='^manual_pag_')],
        ASK_CATEGORY: [CallbackQueryHandler(ask_category, pattern='^manual_cat_')],
        ASK_SUBCATEGORY: [CallbackQueryHandler(ask_subcategory, pattern='^manual_subcat_')],
        ASK_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_manual_lancamento_and_return)],
        MANUAL_CONFIRMATION_STATE: [CallbackQueryHandler(manual_confirmation_handler, pattern='^manual_')],
        OCR_CONFIRMATION_STATE: [CallbackQueryHandler(ocr_confirmation_handler, pattern='^ocr_')]
    },
    fallbacks=[
        CommandHandler(['cancelar', 'cancel', 'sair', 'parar'], cancel),
        MessageHandler(filters.Regex(r'(?i)^/?\s*(cancelar|cancel|sair|parar)$'), cancel)
    ],
    per_message=False,
    per_user=True,
    per_chat=True
)