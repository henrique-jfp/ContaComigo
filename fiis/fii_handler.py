import logging
import re
import json
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from sqlalchemy.orm import Session
from database.database import get_db, get_or_create_user
from models import Usuario, CarteiraFII
from fiis.brapi_client import BrapiClient
from fiis.analisador import analisar_carteira, scoring_fii, recomendar_fiis, explicar_conceito

logger = logging.getLogger(__name__)

# Estados para ConversationHandler
TICKER, QUANTIDADE, PRECO_MEDIO = range(3)

def _formatar_valor_br(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- HANDLERS DE COMANDOS ---

async def cmd_carteira_fii(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe o resumo da carteira de FIIs do usuário."""
    db = next(get_db())
    try:
        user = update.effective_user
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        analise = analisar_carteira(usuario_db.id, db)
        
        if not analise:
            await update.message.reply_html(
                "🏢 <b>Sua Carteira de FIIs</b>\n\n"
                "Você ainda não tem FIIs registrados. Que tal começar agora?\n"
                "Use <b>'adicionar fii'</b> para registrar seu primeiro fundo!"
            )
            return

        msg = [
            "📊 <b>Sua Carteira de FIIs</b>\n",
            "💰 <b>Resumo:</b>",
            f"• Total investido: <b>{_formatar_valor_br(analise['total_investido'])}</b>",
            f"• Valor atual: <b>{_formatar_valor_br(analise['valor_atual'])}</b>",
            f"• Rentabilidade: <b>{analise['rentabilidade_total_pct']:+.2f}%</b>",
            f"• DY médio: <b>{analise['dy_medio_ponderado']*100:.1f}%</b>",
            f"• Renda mensal est.: <b>{_formatar_valor_br(analise['rendimento_mensal_estimado'])}</b>\n",
            "🏢 <b>Distribuição:</b>"
        ]
        
        for seg, pct in analise['distribuicao_segmentos'].items():
            msg.append(f"• {seg}: {pct:.1f}%")
            
        msg.append("\n📋 <b>Posições:</b>")
        for f in analise['fiis']:
            emoji = "🟢" if f['avaliacao'] in ["Excelente", "Bom"] else "🟡"
            msg.append(f"{emoji} <b>{f['ticker']}</b>: {f['quantidade']:.0f} cotas | DY {f['dy']*100:.1f}% | Eval: <i>{f['avaliacao']}</i>")

        if analise['alertas']:
            msg.append("\n⚠️ <b>Alertas:</b>")
            for a in analise['alertas'][:3]:
                msg.append(f"• {a}")

        await update.message.reply_html("\n".join(msg))
    finally:
        db.close()

async def cmd_recomendar_fii_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recomenda FIIs baseados no perfil do usuário."""
    db = next(get_db())
    try:
        user = update.effective_user
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        # Pegar tickers que ele já tem
        posicoes = db.query(CarteiraFII).filter(CarteiraFII.id_usuario == usuario_db.id, CarteiraFII.ativo == True).all()
        excluir = [p.ticker for p in posicoes]
        
        await update.message.reply_chat_action("typing")
        recoms = recomendar_fiis(usuario_db.perfil_investidor, db, excluir_tickers=excluir)
        
        if not recoms:
            await update.message.reply_text("No momento não encontrei novas recomendações que se encaixem perfeitamente no seu perfil. Continue acompanhando!")
            return
            
        msg = [f"🎯 <b>Recomendações para seu perfil {usuario_db.perfil_investidor or 'moderado'}</b>\n"]
        
        for r in recoms:
            msg.append(f"✅ <b>{r['ticker']}</b> ({r['segmento']})")
            msg.append(f"• DY est.: {r['dy']*100:.1f}% | P/VP: {r['pvp']:.2f}")
            msg.append(f"• <i>{r['justificativa']}</i>\n")
            
        msg.append("<i>ℹ️ Isso é uma análise baseada em dados públicos, não uma recomendação direta de investimento.</i>")
        
        await update.message.reply_html("\n".join(msg))
    finally:
        db.close()

async def cmd_analisar_fii_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ticker: str):
    """Analisa um FII específico via IA."""
    client = BrapiClient()
    dados = client.get_fii(ticker)
    
    if not dados:
        await update.message.reply_text(f"Não encontrei dados para o ticker {ticker}. Verifique se ele está correto.")
        return

    # Usar Alfredo para gerar análise
    from gerente_financeiro.ia_handlers import _smart_ai_completion_async
    
    db = next(get_db())
    usuario_db = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
    db.close()

    prompt = f"""Você é o Alfredo, um mordomo de elite especialista em investimentos e FIIs. 
    Analise o FII abaixo com base nos dados reais fornecidos da API Brapi.
    Seja elegante, direto e objetivo. Use HTML para formatação básica (<b>, <i>).
    Não use jargão excessivo. Se o P/VP estiver muito alto, avise.
    
    Dados do FII {ticker}:
    {json.dumps(dados, ensure_ascii=False)}
    
    Perfil do Usuário: {usuario_db.perfil_investidor or 'moderado'}
    """
    
    messages = [
        {"role": "system", "content": "Você é o Alfredo, especialista em FIIs brasileiros."},
        {"role": "user", "content": prompt}
    ]
    
    await update.message.reply_chat_action("typing")
    resposta = await _smart_ai_completion_async(messages)
    
    if isinstance(resposta, dict): # se retornou tool calls ou algo assim
        texto = "Desculpe, tive um problema ao processar a análise agora."
    else:
        texto = resposta or "Não consegui gerar a análise agora. Tente novamente em instantes."
        
    # Garantir que a nota de rodapé esteja presente
    if "recomendação" not in texto.lower():
        texto += "\n\n<i>ℹ️ Isso é uma análise baseada em dados públicos, não uma recomendação de investimento.</i>"

    await update.message.reply_html(texto)

# --- CONVERSATION HANDLER: ADICIONAR FII ---

async def start_add_fii(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verificar se o ticker foi passado direto (ex: /adicionar_fii KNRI11)
    if context.args:
        context.user_data['fii_ticker'] = context.args[0].upper()
        return await ask_quantidade(update, context)
        
    await update.message.reply_text("Qual o ticker do FII que você quer adicionar? (ex: KNRI11)")
    return TICKER

async def receive_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.upper().strip()
    if not re.match(r'^[A-Z]{4}11$', ticker):
        await update.message.reply_text("Ticker inválido. Use o formato XXXX11 (ex: HGLG11).")
        return TICKER
        
    client = BrapiClient()
    dados = client.get_fii(ticker)
    if not dados:
        await update.message.reply_text(f"Não encontrei o FII {ticker}. Tem certeza que o ticker está correto?")
        return TICKER
        
    context.user_data['fii_ticker'] = ticker
    return await ask_quantidade(update, context)

async def ask_quantidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Quantas cotas de {context.user_data['fii_ticker']} você possui?")
    return QUANTIDADE

async def receive_quantidade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qtd = float(update.message.text.replace(',', '.'))
        if qtd <= 0: raise ValueError()
        context.user_data['fii_qtd'] = qtd
    except ValueError:
        await update.message.reply_text("Quantidade inválida. Por favor, digite um número positivo.")
        return QUANTIDADE
        
    await update.message.reply_text(f"Qual o seu preço médio de compra para {context.user_data['fii_ticker']}?")
    return PRECO_MEDIO

async def receive_preco(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        preco = float(update.message.text.replace(',', '.').replace('R$', '').strip())
        if preco <= 0: raise ValueError()
        context.user_data['fii_preco'] = preco
    except ValueError:
        await update.message.reply_text("Preço inválido. Por favor, digite um valor numérico.")
        return PRECO_MEDIO
        
    # Salvar no banco
    db = next(get_db())
    try:
        user = update.effective_user
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        ticker = context.user_data['fii_ticker']
        qtd = context.user_data['fii_qtd']
        preco = context.user_data['fii_preco']
        
        # Verificar se já existe
        posicao = db.query(CarteiraFII).filter(
            CarteiraFII.id_usuario == usuario_db.id,
            CarteiraFII.ticker == ticker
        ).first()
        
        if posicao:
            # Atualizar média ponderada ou substituir? 
            # O prompt pediu UPDATE da quantidade e preço médio.
            total_antigo = float(posicao.quantidade_cotas * posicao.preco_medio)
            total_novo = float(qtd * preco)
            nova_qtd = float(posicao.quantidade_cotas) + qtd
            novo_pm = (total_antigo + total_novo) / nova_qtd
            
            posicao.quantidade_cotas = nova_qtd
            posicao.preco_medio = novo_pm
            posicao.ativo = True
        else:
            posicao = CarteiraFII(
                id_usuario=usuario_db.id,
                ticker=ticker,
                quantidade_cotas=qtd,
                preco_medio=preco,
                data_entrada=datetime.now(timezone.utc).date()
            )
            db.add(posicao)
            
        db.commit()
        
        # Mostrar Card de Confirmação
        client = BrapiClient()
        dados = client.get_fii(ticker)
        cotacao = dados.get("regularMarketPrice", 0)
        dy = (dados.get("dividendYield", 0) or 0)
        pvp = dados.get("pvp", 0)
        eval_fii = scoring_fii(dados)
        
        rend_est = 0
        div_data = dados.get("dividendsData", {})
        if div_data and div_data.get("cashDividends"):
            rend_est = div_data["cashDividends"][-1].get("rate", 0) * float(posicao.quantidade_cotas)

        msg = (
            f"✅ <b>{ticker}</b> adicionado à sua carteira!\n\n"
            f"📊 <b>Sua posição:</b>\n"
            f"• Cotas: <b>{posicao.quantidade_cotas:.0f}</b>\n"
            f"• Preço médio: <b>{_formatar_valor_br(float(posicao.preco_medio))}</b>\n"
            f"• Total investido: <b>{_formatar_valor_br(float(posicao.quantidade_cotas * posicao.preco_medio))}</b>\n\n"
            f"📈 <b>Dados de mercado:</b>\n"
            f"• Cotação atual: <b>{_formatar_valor_br(cotacao)}</b>\n"
            f"• DY 12m: <b>{dy:.1f}%</b>\n"
            f"• P/VP: <b>{pvp:.2f}</b>\n"
            f"• Rend. mensal est.: <b>{_formatar_valor_br(rend_est)}</b>\n\n"
            f"💡 Avaliação: <b>{eval_fii}</b>"
        )
        
        await update.message.reply_html(msg)
    finally:
        db.close()
        context.user_data.clear()
        
    return ConversationHandler.END

async def cancel_fii(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada.")
    context.user_data.clear()
    return ConversationHandler.END

# Handler de Conversa
add_fii_conv = ConversationHandler(
    entry_points=[
        CommandHandler("adicionar_fii", start_add_fii),
        MessageHandler(filters.Regex(r'^(?i)(adicionar fii|comprei fii)'), start_add_fii)
    ],
    states={
        TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticker)],
        QUANTIDADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_quantidade)],
        PRECO_MEDIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_preco)],
    },
    fallbacks=[CommandHandler("cancelar", cancel_fii)]
)

# --- DETECÇÃO DE INTENÇÕES ---

def detect_fii_intent(message: str) -> str | None:
    m = message.lower()
    
    # 1. Analisar FII específico
    match_analisar = re.search(r'(?i)(analisa|o que acha de|vale a pena|sobre o) ([a-z]{4}11)', m)
    if match_analisar:
        return f"analisar_fii:{match_analisar.group(2).upper()}"
    
    # 2. Carteira
    if any(p in m for p in ["meus fiis", "carteira de fii", "minha carteira fii", "meus fundos"]):
        return "carteira_fii"
        
    # 3. Recomendações
    if any(p in m for p in ["recomenda", "quais fiis", "bons fiis", "sugestão de fii"]):
        return "recomendar_fii"
        
    # 4. Conceitos
    if any(p in m for p in ["o que é dy", "o que é pvp", "explica pvp", "explica dy", "o que é vacância", "o que é vacancia"]):
        return "explicar_conceito"
        
    # 5. Adicionar (Interceptado pelo ConvHandler, mas útil para o roteador saber)
    if any(p in m for p in ["adicionar fii", "comprei fii"]):
        return "adicionar_fii"

    # 6. Remover
    match_remover = re.search(r'(?i)(remover|vendi) ([a-z]{4}11)', m)
    if match_remover:
        return f"remover_fii:{match_remover.group(2).upper()}"

    return None

async def route_fii_intent(intent: str, update: Update, context: ContextTypes.DEFAULT_TYPE, db: Session):
    """Roteia a intenção para a função correta."""
    if intent == "carteira_fii":
        await cmd_carteira_fii(update, context)
    elif intent == "recomendar_fii":
        await cmd_recomendar_fii_handler(update, context)
    elif intent == "explicar_conceito":
        explica = explicar_conceito(update.message.text)
        await update.message.reply_html(f"🏢 <b>Alfredo Explica:</b>\n\n{explica}")
    elif intent.startswith("analisar_fii:"):
        ticker = intent.split(":")[1]
        await cmd_analisar_fii_handler(update, context, ticker)
    elif intent.startswith("remover_fii:"):
        ticker = intent.split(":")[1]
        await cmd_remover_fii_handler(update, context, ticker, db)
    elif intent == "adicionar_fii":
        # Deixar o ConversationHandler lidar ou iniciar manualmente se necessário
        pass

async def cmd_remover_fii_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ticker: str, db: Session):
    usuario_db = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
    posicao = db.query(CarteiraFII).filter(
        CarteiraFII.id_usuario == usuario_db.id,
        CarteiraFII.ticker == ticker,
        CarteiraFII.ativo == True
    ).first()
    
    if posicao:
        posicao.ativo = False
        db.commit()
        await update.message.reply_html(f"✅ <b>{ticker}</b> removido da sua carteira ativa.")
    else:
        await update.message.reply_text(f"Você não tem {ticker} na sua carteira ativa.")
