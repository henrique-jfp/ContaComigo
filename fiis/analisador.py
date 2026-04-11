import logging
from sqlalchemy.orm import Session
from models import CarteiraFII, Usuario
from fiis.brapi_client import BrapiClient

logger = logging.getLogger(__name__)

def scoring_fii(dados_brapi: dict) -> str:
    """
    Retorna uma avaliação qualitativa baseada em critérios objetivos.
    """
    # Plano Free pode não retornar DY em percentual direto ou pode vir nulo
    dy = (dados_brapi.get("dividendYield", 0) or 0) / 100.0 if "dividendYield" in dados_brapi else 0
    
    # Se não tiver bookValue, não calculamos P/VP real, usamos o que vier ou zero
    pvp = dados_brapi.get("pvp", 0) or 0
    
    if dy > 0:
        if dy >= 0.10 and (0.8 <= pvp <= 1.05 or pvp == 0):
            return "Excelente"
        elif dy >= 0.08:
            return "Bom"
        elif dy >= 0.06:
            return "Atenção"
    
    return "Revisar (Dados Limitados)"

def analisar_carteira(id_usuario: int, db: Session) -> dict:
    """
    Analisa a carteira de FIIs do usuário.
    """
    posicoes = db.query(CarteiraFII).filter(
        CarteiraFII.id_usuario == id_usuario,
        CarteiraFII.ativo == True
    ).all()
    
    if not posicoes:
        return {}

    client = BrapiClient()
    tickers = [p.ticker for p in posicoes]
    dados_mercado = client.get_fiis_em_lote(tickers)
    
    total_investido = 0.0
    valor_atual = 0.0
    rendimento_mensal_estimado = 0.0
    dy_ponderado_soma = 0.0
    
    segmentos = {}
    fiis_detalhes = []
    alertas = []

    for pos in posicoes:
        dados = dados_mercado.get(pos.ticker, {})
        cotacao = dados.get("regularMarketPrice", 0) or 0
        
        # Fallbacks para Plano Free
        dy = (dados.get("dividendYield", 0) or 0) / 100.0
        pvp = dados.get("pvp", 0) or 0
        
        # Último rendimento (Pode vir nulo no Free)
        ultimo_rend_valor = 0.0
        div_data = dados.get("dividendsData", {})
        if div_data and div_data.get("cashDividends"):
            ultimo_rend_valor = div_data["cashDividends"][-1].get("rate", 0)
        
        v_investido = float(pos.preco_medio * pos.quantidade_cotas)
        v_atual = float(cotacao) * float(pos.quantidade_cotas)
        rent_pct = ((v_atual - v_investido) / v_investido * 100) if v_investido > 0 else 0
        
        total_investido += v_investido
        valor_atual += v_atual
        rendimento_mensal_estimado += ultimo_rend_valor * float(pos.quantidade_cotas)
        dy_ponderado_soma += dy * v_atual
        
        # Segmento
        setor = dados.get("summaryProfile", {}).get("sector", "Outros") or "Outros"
        segmentos[setor] = segmentos.get(setor, 0.0) + v_atual
        
        fiis_detalhes.append({
            "ticker": pos.ticker,
            "quantidade": float(pos.quantidade_cotas),
            "preco_medio": float(pos.preco_medio),
            "cotacao_atual": float(cotacao),
            "valor_posicao": v_atual,
            "rentabilidade_pct": rent_pct,
            "dy": dy,
            "pvp": pvp,
            "ultimo_rendimento": ultimo_rend_valor,
            "segmento": setor,
            "avaliacao": scoring_fii(dados)
        })
        
        if pvp > 1.30:
            alertas.append(f"⚠️ {pos.ticker} pode estar caro (P/VP {pvp:.2f}).")
        
        if dy == 0:
            alertas.append(f"ℹ️ Dados de dividendos de {pos.ticker} não disponíveis no momento.")

    # Calcular % segmentos
    distribuicao_segmentos = {}
    if valor_atual > 0:
        for s, v in segmentos.items():
            distribuicao_segmentos[s] = (v / valor_atual) * 100

    return {
        "total_investido": total_investido,
        "valor_atual": valor_atual,
        "rentabilidade_total_pct": ((valor_atual - total_investido) / total_investido * 100) if total_investido > 0 else 0,
        "dy_medio_ponderado": (dy_ponderado_soma / valor_atual) if valor_atual > 0 else 0,
        "rendimento_mensal_estimado": rendimento_mensal_estimado,
        "distribuicao_segmentos": distribuicao_segmentos,
        "fiis": fiis_detalhes,
        "alertas": alertas
    }

def recomendar_fiis(perfil_investidor: str, db: Session, excluir_tickers: list[str] = []) -> list[dict]:
    """
    Busca FIIs recomendados baseado no perfil.
    """
    client = BrapiClient()
    perfil = (perfil_investidor or "moderado").lower()
    
    # Critérios base
    dy_min = 0.08
    pvp_max = 1.15
    
    if perfil == "conservador":
        dy_min = 0.09
        pvp_max = 1.05
    elif perfil == "arrojado":
        dy_min = 0.07
        pvp_max = 1.25

    fiis_lista = client.buscar_fiis_por_criterio(dy_minimo=dy_min, pvp_maximo=pvp_max)
    
    recomendacoes = []
    excluir_set = set(t.upper() for t in excluir_tickers)
    
    for item in fiis_lista:
        ticker = item.get("stock", "").upper()
        if ticker in excluir_set:
            continue
            
        # Buscar detalhes para validar P/VP real e Segmento
        detalhes = client.get_fii(ticker)
        if not detalhes:
            continue
            
        pvp = detalhes.get("pvp", 0)
        dy = (detalhes.get("dividendYield", 0) or 0) / 100.0
        setor = detalhes.get("summaryProfile", {}).get("sector", "Outros") or "Outros"
        
        if dy < dy_min or pvp > pvp_max:
            continue
            
        # Filtro por segmento baseado no perfil (simplificado)
        if perfil == "conservador" and setor in ["Desenvolvimento", "Híbrido"]:
            continue
            
        justificativa = ""
        if pvp < 1.0:
            justificativa = f"Negociado com desconto (P/VP {pvp:.2f}) e ótimo DY de {dy*100:.1f}%."
        else:
            justificativa = f"Fundo sólido com DY de {dy*100:.1f}% em linha com seu perfil {perfil}."
            
        recomendacoes.append({
            "ticker": ticker,
            "dy": dy,
            "pvp": pvp,
            "segmento": setor,
            "justificativa": justificativa
        })
        
        if len(recomendacoes) >= 5:
            break
            
    return recomendacoes

def explicar_conceito(conceito: str) -> str:
    """
    Retorna explicação curta e direta de conceitos de FII.
    """
    conceito = conceito.lower().strip()
    
    mapa = {
        "dy": "O DY (Dividend Yield) é quanto o fundo paga de rendimento em relação ao seu preço. Um DY de 10% significa que para cada R$100 investidos, você recebe R$10/ano em rendimentos. FIIs pagam mensalmente, então divide por 12: ~R$0,83 por mês para cada R$100 investidos.",
        "pvp": "O P/VP compara o preço de mercado com o valor real dos ativos do fundo. P/VP < 1.0 = você está comprando R$1 de imóvel por menos de R$1 (desconto). P/VP > 1.2 = você está pagando prêmio acima do valor dos imóveis. Ideal: entre 0.9 e 1.1.",
        "vacância": "Vacância é o percentual de imóveis do fundo que estão desocupados (sem gerar aluguel). Vacância 0% = 100% dos imóveis alugados, máxima eficiência. Vacância acima de 15% é sinal de alerta — menos receita, menos rendimento.",
        "rendimento": "É o valor distribuído mensalmente por cota. Se o fundo paga R$1,20/cota e você tem 100 cotas, recebe R$120 por mês direto na conta da corretora. É isento de IR para pessoa física.",
        "liquidez": "Volume médio negociado por dia. Liquidez baixa = difícil vender sem impactar o preço. Prefira FIIs com liquidez diária acima de R$500 mil.",
        "papel": "<b>FII de Papel (Recebíveis):</b> Investe em títulos de dívida imobiliária, como o CRI (Certificado de Recebíveis Imobiliários). É como se você emprestasse dinheiro para o setor imobiliário em troca de juros e correção monetária. Geralmente pagam dividendos mais altos, mas não possuem o imóvel físico.",
        "tijolo": "<b>FII de Tijolo:</b> Investe diretamente em imóveis físicos reais (shoppings, galpões logísticos, prédios de escritórios). O rendimento vem do aluguel pago pelos inquilinos. É um investimento mais tangível e focado na valorização dos imóveis e renda constante.",
        "fof": "<b>FOF (Fundo de Fundos):</b> É um fundo que compra cotas de outros FIIs. É ótimo para diversificar com pouco dinheiro, pois com uma cota você se torna dono de pedacinhos de dezenas de outros fundos.",
    }
    
    # Busca por palavra-chave parcial
    for k, v in mapa.items():
        if k in conceito:
            return v
            
    return "Desculpe, ainda não sei explicar esse conceito específico de FII. Tente perguntar sobre DY, P/VP, Vacância, FII de Tijolo ou FII de Papel."
