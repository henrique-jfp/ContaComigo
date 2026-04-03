
from .analytics_utils import track_analytics

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    MessageHandler,
    ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

# --- CORREÇÃO: Importamos as funções do ocr_handler, mas não os estados ---
from .ocr_handler import ocr_action_processor, ocr_iniciar_como_subprocesso
from .handlers import cancel, criar_teclado_colunas
from .utils_validation import (
    validar_valor_monetario, validar_descricao,
    ask_valor_generico, ask_descricao_generica
)

from database.database import get_db, get_or_create_user
from models import Categoria, Subcategoria, Lancamento, Conta, Usuario
from .states import (
    AWAITING_LAUNCH_ACTION, ASK_DESCRIPTION, ASK_VALUE, ASK_CONTA,
    ASK_CATEGORY, ASK_SUBCATEGORY, ASK_DATA, OCR_CONFIRMATION_STATE
)

logger = logging.getLogger(__name__)



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
    """Processa o valor e vai para seleção de conta"""
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
    
    # Busca contas do usuário
    db = next(get_db())
    try:
        user_db = db.query(Usuario).filter(Usuario.telegram_id == update.effective_user.id).first()
        if not user_db:
            await update.message.reply_text("❌ Usuário não encontrado. Use /start para se cadastrar.")
            return ConversationHandler.END
            
        # Filtrar contas baseado no tipo de lançamento
        tipo_lancamento = context.user_data['novo_lancamento']['tipo']
        
        if tipo_lancamento == "Entrada":
            # Para entrada, só contas bancárias (não cartões)
            contas = db.query(Conta).filter(
                Conta.id_usuario == user_db.id,
                Conta.tipo == "Conta"
            ).all()
            tipo_texto = "contas bancárias"
        else:
            # Para saída, todas as opções (contas e cartões)
            contas = db.query(Conta).filter(Conta.id_usuario == user_db.id).all()
            tipo_texto = "contas/cartões"
        
        if not contas:
            await update.message.reply_text(
                f"❌ <b>Nenhuma {tipo_texto} cadastrada</b>\n\n"
                "Use /configurar para adicionar suas contas primeiro.",
                parse_mode='HTML'
            )
            return ConversationHandler.END

        # Cria botões para as contas de forma mais organizada
        botoes = []
        for conta in contas:
            # Emoji baseado no tipo
            emoji = "🏦" if conta.tipo == "Conta" else "💳"
            botoes.append(InlineKeyboardButton(
                f"{emoji} {conta.nome}", 
                callback_data=f"manual_conta_{conta.id}"
            ))
        
        # Organiza em 2 colunas
        teclado = criar_teclado_colunas(botoes, 2)
        
        descricao = context.user_data['novo_lancamento']['descricao']
        tipo = context.user_data['novo_lancamento']['tipo']
        emoji_tipo = "🟢" if tipo == "Entrada" else "�"
        
        await update.message.reply_text(
            f"{emoji_tipo} <b>{descricao}</b>\n"
            f"💰 R$ {valor:.2f}\n\n"
            f"🏦 <b>Qual {tipo_texto}?</b>\n"
            f"Selecione de onde {'entrou' if tipo_lancamento == 'Entrada' else 'saiu'} o dinheiro:",
            reply_markup=InlineKeyboardMarkup(teclado),
            parse_mode='HTML'
        )
        
        return ASK_CONTA
        
    finally:
        db.close()

async def ask_conta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa seleção de conta e vai para categorias"""
    query = update.callback_query
    await query.answer()
    
    conta_id = int(query.data.split('_')[-1])
    context.user_data['novo_lancamento']['id_conta'] = conta_id
    
    # Busca info da conta e categorias
    db = next(get_db())
    try:
        conta_obj = db.query(Conta).filter(Conta.id == conta_id).first()
        context.user_data['novo_lancamento']['forma_pagamento'] = conta_obj.nome
        
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
        emoji_conta = "🏦" if conta_obj.tipo == "Conta" else "💳"
        
        await query.edit_message_text(
            f"{emoji_tipo} <b>{dados['descricao']}</b>\n"
            f"💰 R$ {dados['valor']:.2f}\n"
            f"{emoji_conta} {conta_obj.nome}\n\n"
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
    """Salva o lançamento manual e exibe confirmação elegante."""
    if 'novo_lancamento' not in context.user_data:
        # Se os dados não existem mais no context, avisa o usuário
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

    # Salvar no banco
    db = next(get_db())
    try:
        user_info = update.effective_user
        usuario_db = get_or_create_user(db, user_info.id, user_info.full_name)
        dados = context.user_data['novo_lancamento']
        
        novo_lancamento = Lancamento(id_usuario=usuario_db.id, **dados)
        db.add(novo_lancamento)
        db.commit()
        
        # Confirmação elegante
        tipo = dados['tipo']
        emoji_tipo = "🟢" if tipo == "Entrada" else "🔴"
        data_formatada = data_transacao.strftime('%d/%m/%Y')
        
        confirmacao = (
            f"✅ <b>Lançamento Salvo!</b>\n\n"
            f"{emoji_tipo} <b>{dados['descricao']}</b>\n"
            f"💰 R$ {dados['valor']:.2f}\n"
            f"🏦 {dados['forma_pagamento']}\n"
            f"📅 {data_formatada}\n\n"
            f"💡 <i>Quer adicionar outro lançamento?</i>"
        )
        
        await update.message.reply_text(confirmacao, parse_mode='HTML')
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar lançamento manual: {e}", exc_info=True)
        await update.message.reply_text(
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
        ASK_CONTA: [CallbackQueryHandler(ask_conta, pattern='^manual_conta_')],
        ASK_CATEGORY: [CallbackQueryHandler(ask_category, pattern='^manual_cat_')],
        ASK_SUBCATEGORY: [CallbackQueryHandler(ask_subcategory, pattern='^manual_subcat_')],
        ASK_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_manual_lancamento_and_return)],
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