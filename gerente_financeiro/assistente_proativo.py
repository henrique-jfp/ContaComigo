"""
🤖 Assistente Proativo - ContaComigo
===================================

Sistema de alertas inteligentes que analisa padrões financeiros
e notifica usuários proativamente sobre:
- Gastos acima da média histórica
- Assinaturas duplicadas ou inativas
- Metas em risco de não serem cumpridas

Autor: Henrique Freitas
Data: 18/11/2025
Versão: 3.1.0
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import func, and_, extract
from decimal import Decimal

from database.database import get_db
from models import Usuario, Lancamento, Objetivo, Categoria

logger = logging.getLogger(__name__)

TIPOS_DESPESA = ("Saída", "Despesa")


# ============================================================================
# ANÁLISE DE GASTOS ELEVADOS
# ============================================================================

def calcular_gastos_mes_atual(usuario_id: int) -> float:
    """Calcula o total de gastos do mês atual (filtrando transferências internas)"""
    db = next(get_db())
    try:
        hoje = datetime.now()
        
        lancamentos = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                Lancamento.tipo.in_(TIPOS_DESPESA),
                extract('year', Lancamento.data_transacao) == hoje.year,
                extract('month', Lancamento.data_transacao) == hoje.month
            )
        ).all()
        
        total = sum(float(l.valor) for l in lancamentos if not l.is_transferencia_interna)
        return float(total)
    finally:
        db.close()


def calcular_media_historica(usuario_id: int, meses: int = 6) -> float:
    """Calcula a média de gastos dos últimos N meses (excluindo o atual)"""
    db = next(get_db())
    try:
        hoje = datetime.now()
        data_inicio = hoje - timedelta(days=meses * 30)
        
        # Excluir mês atual
        primeiro_dia_mes_atual = hoje.replace(day=1)
        
        total = db.query(func.sum(Lancamento.valor)).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                Lancamento.tipo.in_(TIPOS_DESPESA),
                Lancamento.data_transacao >= data_inicio,
                Lancamento.data_transacao < primeiro_dia_mes_atual
            )
        ).scalar()
        
        total_float = float(total or 0)
        
        # Dividir pelo número de meses
        return total_float / meses if total_float > 0 else 0
    finally:
        db.close()


def identificar_categorias_infladas(usuario_id: int, percentual_minimo: float = 30.0) -> List[Dict]:
    """
    Identifica categorias que tiveram aumento significativo em relação à média histórica
    
    Args:
        usuario_id: ID do usuário
        percentual_minimo: Percentual mínimo de aumento para considerar (padrão: 30%)
    
    Returns:
        Lista de dicts com {categoria, valor_atual, valor_medio, percentual_aumento}
    """
    db = next(get_db())
    try:
        hoje = datetime.now()
        data_inicio_historico = hoje - timedelta(days=180)  # 6 meses
        primeiro_dia_mes_atual = hoje.replace(day=1)
        
        categorias_problema = []
        
        # Buscar todas as categorias usadas pelo usuário
        categorias = db.query(Categoria).join(
            Lancamento, Lancamento.id_categoria == Categoria.id
        ).filter(
            Lancamento.id_usuario == usuario_id
        ).distinct().all()
        
        for categoria in categorias:
            # Gasto atual (mês atual)
            gasto_atual = db.query(func.sum(Lancamento.valor)).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    Lancamento.tipo.in_(TIPOS_DESPESA),
                    Lancamento.id_categoria == categoria.id,
                    extract('year', Lancamento.data_transacao) == hoje.year,
                    extract('month', Lancamento.data_transacao) == hoje.month
                )
            ).scalar()
            
            gasto_atual = float(gasto_atual or 0)
            
            if gasto_atual == 0:
                continue
            
            # Média histórica (últimos 6 meses, excluindo atual)
            gasto_historico = db.query(func.sum(Lancamento.valor)).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    Lancamento.tipo.in_(TIPOS_DESPESA),
                    Lancamento.id_categoria == categoria.id,
                    Lancamento.data_transacao >= data_inicio_historico,
                    Lancamento.data_transacao < primeiro_dia_mes_atual
                )
            ).scalar()
            
            gasto_historico = float(gasto_historico or 0)
            media_mensal = gasto_historico / 6 if gasto_historico > 0 else 0
            
            if media_mensal == 0:
                continue
            
            # Calcular percentual de aumento
            percentual_aumento = ((gasto_atual - media_mensal) / media_mensal) * 100
            
            if percentual_aumento >= percentual_minimo:
                categorias_problema.append({
                    'categoria': categoria.nome,
                    'valor_atual': gasto_atual,
                    'valor_medio': media_mensal,
                    'percentual_aumento': percentual_aumento
                })
        
        # Ordenar por percentual de aumento (decrescente)
        categorias_problema.sort(key=lambda x: x['percentual_aumento'], reverse=True)
        
        return categorias_problema
    finally:
        db.close()


def analisar_gastos_usuario(usuario_id: int) -> Optional[Dict]:
    """
    Análise completa de gastos do usuário
    
    Returns:
        Dict com informações do alerta ou None se está tudo normal
    """
    try:
        gastos_mes = calcular_gastos_mes_atual(usuario_id)
        media_historica = calcular_media_historica(usuario_id, meses=6)
        
        # Se não tem histórico suficiente, não alertar
        if media_historica == 0:
            return None
        
        # Verificar se está 30% acima da média
        percentual_acima = ((gastos_mes - media_historica) / media_historica) * 100
        
        if percentual_acima >= 30:
            categorias_problema = identificar_categorias_infladas(usuario_id)
            
            return {
                'tipo': 'gastos_elevados',
                'gastos_mes': gastos_mes,
                'media_historica': media_historica,
                'percentual_acima': percentual_acima,
                'categorias_problema': categorias_problema[:3]  # Top 3
            }
        
        return None
    except Exception as e:
        logger.error(f"❌ Erro ao analisar gastos do usuário {usuario_id}: {e}")
        return None


# ============================================================================
# DETECÇÃO DE ASSINATURAS DUPLICADAS
# ============================================================================

def detectar_assinaturas_recorrentes(usuario_id: int, meses: int = 3) -> List[Dict]:
    """
    Detecta transações recorrentes (assinaturas, mensalidades)
    
    Critério: Mesma descrição aparecendo em pelo menos 2 dos últimos 3 meses
    com valores similares (±10%)
    """
    db = next(get_db())
    try:
        hoje = datetime.now()
        data_inicio = hoje - timedelta(days=meses * 30)
        
        # Buscar todas as saídas dos últimos N meses
        lancamentos = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                Lancamento.tipo.in_(TIPOS_DESPESA),
                Lancamento.data_transacao >= data_inicio
            )
        ).order_by(Lancamento.data_transacao).all()
        
        # Agrupar por descrição similar
        grupos_descricao = {}
        
        for lanc in lancamentos:
            # Normalizar descrição (minúsculas, sem números de fatura)
            desc_normalizada = (lanc.descricao or "").lower()
            
            # Remover números de fatura/parcela
            import re
            desc_normalizada = re.sub(r'\d+/\d+|\d{4,}', '', desc_normalizada).strip()
            
            if desc_normalizada not in grupos_descricao:
                grupos_descricao[desc_normalizada] = []
            
            grupos_descricao[desc_normalizada].append({
                'valor': float(lanc.valor),
                'data': lanc.data_transacao,
                'descricao_original': lanc.descricao,
                'categoria': lanc.categoria.nome if lanc.categoria else 'Outros'
            })
        
        # Identificar assinaturas (aparecem em pelo menos 2 meses)
        assinaturas = []
        
        for desc, transacoes in grupos_descricao.items():
            if len(transacoes) >= 2:
                meses_distintos = {
                    (t['data'].year, t['data'].month)
                    for t in transacoes
                    if t.get('data') is not None
                }
                if len(meses_distintos) < 2:
                    continue

                # Verificar se valores são similares (±10%)
                valores = [t['valor'] for t in transacoes]
                valor_medio = sum(valores) / len(valores)
                
                # Verificar se todos os valores estão dentro da tolerância
                valores_similares = all(
                    abs(v - valor_medio) / valor_medio <= 0.1 
                    for v in valores if valor_medio > 0
                )
                
                if valores_similares:
                    assinaturas.append({
                        'descricao': transacoes[0]['descricao_original'],
                        'valor_medio': valor_medio,
                        'frequencia': len(transacoes),
                        'categoria': transacoes[0]['categoria'],
                        'ultima_data': max(t['data'] for t in transacoes)
                    })
        
        return assinaturas
    finally:
        db.close()


def encontrar_duplicatas_assinaturas(assinaturas: List[Dict]) -> List[Dict]:
    """
    Identifica assinaturas duplicadas ou similares que podem ser canceladas
    
    Exemplos:
    - Netflix + Amazon Prime (ambos streaming)
    - Spotify + YouTube Premium (ambos música)
    - Vários serviços de cloud storage
    """
    # Palavras-chave por categoria de serviço
    servicos_similares = {
        'streaming_video': ['netflix', 'prime', 'disney', 'hbo', 'globoplay', 'paramount', 'apple tv'],
        'streaming_musica': ['spotify', 'youtube premium', 'deezer', 'apple music', 'amazon music'],
        'cloud_storage': ['google one', 'icloud', 'dropbox', 'onedrive', 'mega'],
        'academia': ['smartfit', 'bodytech', 'bluefit', 'academia'],
        'delivery': ['ifood', 'rappi', 'uber eats'],
    }
    
    duplicatas = []
    
    for categoria_servico, keywords in servicos_similares.items():
        encontrados = []
        
        for assinatura in assinaturas:
            desc_lower = assinatura['descricao'].lower()
            
            if any(keyword in desc_lower for keyword in keywords):
                encontrados.append(assinatura)
        
        # Se tem 2 ou mais do mesmo tipo, é duplicata
        if len(encontrados) >= 2:
            duplicatas.extend(encontrados)
    
    return duplicatas


def analisar_assinaturas_usuario(usuario_id: int) -> Optional[Dict]:
    """
    Análise completa de assinaturas do usuário
    
    Returns:
        Dict com informações do alerta ou None se não houver duplicatas
    """
    try:
        assinaturas = detectar_assinaturas_recorrentes(usuario_id, meses=3)
        
        if not assinaturas:
            return None
        
        duplicatas = encontrar_duplicatas_assinaturas(assinaturas)
        
        if duplicatas:
            economia_potencial = sum(a['valor_medio'] for a in duplicatas)
            
            return {
                'tipo': 'assinaturas_duplicadas',
                'duplicatas': duplicatas,
                'economia_potencial_mensal': economia_potencial,
                'economia_potencial_anual': economia_potencial * 12
            }
        
        return None
    except Exception as e:
        logger.error(f"❌ Erro ao analisar assinaturas do usuário {usuario_id}: {e}")
        return None


# ============================================================================
# VERIFICAÇÃO DE METAS EM RISCO
# ============================================================================

def calcular_progresso_esperado(objetivo: Objetivo) -> float:
    """
    Calcula o progresso esperado para a meta até a data atual
    
    Returns:
        Percentual esperado (0-100)
    """
    hoje = datetime.now().date()
    
    # Se a data já passou, deveria estar em 100%
    if not objetivo.data_meta:
        return 0.0
    if hoje >= objetivo.data_meta:
        return 100.0
    
    # Calcular dias desde a criação (compatível com campo criado_em do model).
    inicio = objetivo.criado_em.date() if getattr(objetivo, 'criado_em', None) else hoje
    dias_totais = (objetivo.data_meta - inicio).days
    dias_decorridos = (hoje - inicio).days
    
    if dias_totais <= 0:
        return 100.0
    
    progresso_esperado = (dias_decorridos / dias_totais) * 100
    
    return min(progresso_esperado, 100.0)


def calcular_aporte_corretivo(objetivo: Objetivo) -> float:
    """
    Calcula quanto o usuário precisa aportar por mês para recuperar a meta
    """
    hoje = datetime.now().date()
    if not objetivo.data_meta:
        falta_sem_prazo = float(objetivo.valor_meta - objetivo.valor_atual)
        return max(falta_sem_prazo, 0.0)
    
    # Se já passou o prazo
    if hoje >= objetivo.data_meta:
        return max(float(objetivo.valor_meta - objetivo.valor_atual), 0.0)
    
    # Calcular meses restantes
    meses_restantes = (objetivo.data_meta.year - hoje.year) * 12 + (objetivo.data_meta.month - hoje.month)
    
    if meses_restantes <= 0:
        meses_restantes = 1
    
    # Quanto falta para atingir a meta
    falta = float(objetivo.valor_meta - objetivo.valor_atual)
    
    # Aporte mensal necessário
    aporte_mensal = falta / meses_restantes
    
    return max(aporte_mensal, 0.0)


def analisar_metas_usuario(usuario_id: int) -> Optional[Dict]:
    """
    Análise de metas em risco do usuário
    
    Returns:
        Dict com informações do alerta ou None se metas estão ok
    """
    db = next(get_db())
    try:
        # Buscar metas válidas (sem depender de campo 'ativo', ausente no model atual).
        metas = db.query(Objetivo).filter(
            and_(
                Objetivo.id_usuario == usuario_id,
                Objetivo.data_meta.isnot(None),
                Objetivo.data_meta >= datetime.now().date()
            )
        ).all()
        
        if not metas:
            return None
        
        metas_em_risco = []
        
        for meta in metas:
            if float(meta.valor_meta or 0) <= 0:
                continue
            if float(meta.valor_atual or 0) >= float(meta.valor_meta or 0):
                continue

            progresso_esperado = calcular_progresso_esperado(meta)
            progresso_real = (float(meta.valor_atual) / float(meta.valor_meta)) * 100 if meta.valor_meta > 0 else 0
            
            # Se está 15% ou mais atrasado
            if progresso_real < (progresso_esperado - 15):
                aporte_necessario = calcular_aporte_corretivo(meta)
                
                metas_em_risco.append({
                    'descricao': meta.descricao,
                    'valor_meta': float(meta.valor_meta),
                    'valor_atual': float(meta.valor_atual),
                    'data_meta': meta.data_meta,
                    'progresso_esperado': progresso_esperado,
                    'progresso_real': progresso_real,
                    'aporte_corretivo': aporte_necessario
                })
        
        if metas_em_risco:
            return {
                'tipo': 'metas_em_risco',
                'metas': metas_em_risco
            }
        
        return None
    finally:
        db.close()


# ============================================================================
# FUNÇÃO PRINCIPAL - ANÁLISE COMPLETA
# ============================================================================

async def analisar_e_notificar_usuario(bot, usuario: Usuario) -> bool:
    """
    Executa todas as análises para um usuário e envia notificações se necessário
    
    Returns:
        True se algum alerta foi enviado, False caso contrário
    """
    try:
        alertas_enviados = False
        
        # 1. Análise de gastos elevados
        alerta_gastos = analisar_gastos_usuario(usuario.id)
        if alerta_gastos:
            await enviar_alerta_gastos_elevados(bot, usuario, alerta_gastos)
            alertas_enviados = True
        
        # 2. Análise de assinaturas duplicadas
        alerta_assinaturas = analisar_assinaturas_usuario(usuario.id)
        if alerta_assinaturas:
            await enviar_alerta_assinaturas(bot, usuario, alerta_assinaturas)
            alertas_enviados = True
        
        # 3. Análise de metas em risco
        alerta_metas = analisar_metas_usuario(usuario.id)
        if alerta_metas:
            await enviar_alerta_metas(bot, usuario, alerta_metas)
            alertas_enviados = True
        
        return alertas_enviados
    except Exception as e:
        logger.error(f"❌ Erro ao analisar usuário {usuario.id}: {e}", exc_info=True)
        return False


# ============================================================================
# FUNÇÕES DE ENVIO DE NOTIFICAÇÕES
# ============================================================================

async def enviar_alerta_gastos_elevados(bot, usuario: Usuario, alerta: Dict):
    """Envia notificação de gastos acima da média"""
    try:
        categorias_texto = ""
        for cat in alerta['categorias_problema']:
            categorias_texto += (
                f"  📌 <b>{cat['categoria']}</b>: "
                f"R$ {cat['valor_atual']:.2f} "
                f"(+{cat['percentual_aumento']:.0f}% vs média)\n"
            )
        
        mensagem = (
            f"⚠️ <b>Alerta de Gastos Elevados!</b>\n\n"
            f"Olá, {usuario.nome_completo}!\n\n"
            f"Você já gastou <b>R$ {alerta['gastos_mes']:.2f}</b> este mês.\n"
            f"Isso é <b>{alerta['percentual_acima']:.0f}% acima</b> da sua média histórica "
            f"(R$ {alerta['media_historica']:.2f}).\n\n"
            f"📊 <b>Categorias que mais cresceram:</b>\n"
            f"{categorias_texto}\n"
            f"💡 <b>Dica:</b> Use /insights para análise detalhada ou "
            f"/economia para receber sugestões personalizadas."
        )
        
        await bot.send_message(
            chat_id=usuario.telegram_id,
            text=mensagem,
            parse_mode='HTML'
        )
        
        logger.info(f"📨 Alerta de gastos enviado para usuário {usuario.telegram_id}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar alerta de gastos: {e}")


async def enviar_alerta_assinaturas(bot, usuario: Usuario, alerta: Dict):
    """Envia notificação sobre assinaturas duplicadas"""
    try:
        assinaturas_texto = ""
        for assinatura in alerta['duplicatas']:
            assinaturas_texto += (
                f"  💳 {assinatura['descricao']}: "
                f"R$ {assinatura['valor_medio']:.2f}/mês\n"
            )
        
        mensagem = (
            f"💰 <b>Oportunidade de Economia Detectada!</b>\n\n"
            f"Olá, {usuario.nome_completo}!\n\n"
            f"Identifiquei assinaturas similares ou duplicadas:\n\n"
            f"{assinaturas_texto}\n"
            f"💵 <b>Economia potencial:</b>\n"
            f"  • Mensal: R$ {alerta['economia_potencial_mensal']:.2f}\n"
            f"  • Anual: R$ {alerta['economia_potencial_anual']:.2f}\n\n"
            f"💡 <b>Dica:</b> Avalie se você realmente usa todos esses serviços. "
            f"Cancelando alguns, você pode economizar bastante!"
        )
        
        await bot.send_message(
            chat_id=usuario.telegram_id,
            text=mensagem,
            parse_mode='HTML'
        )
        
        logger.info(f"📨 Alerta de assinaturas enviado para usuário {usuario.telegram_id}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar alerta de assinaturas: {e}")


async def enviar_alerta_metas(bot, usuario: Usuario, alerta: Dict):
    """Envia notificação sobre metas em risco"""
    try:
        for meta in alerta['metas']:
            progresso_real = meta['progresso_real']
            progresso_esperado = meta['progresso_esperado']
            
            # Barra de progresso visual
            blocos_cheios = int(progresso_real // 10)
            barra = "🟩" * blocos_cheios + "⬜" * (10 - blocos_cheios)
            
            mensagem = (
                f"🎯 <b>Meta em Risco: {meta['descricao']}</b>\n\n"
                f"Olá, {usuario.nome_completo}!\n\n"
                f"Sua meta está atrasada:\n\n"
                f"{barra} {progresso_real:.1f}%\n\n"
                f"📊 <b>Situação:</b>\n"
                f"  • Progresso atual: {progresso_real:.1f}%\n"
                f"  • Progresso esperado: {progresso_esperado:.1f}%\n"
                f"  • Você acumulou: R$ {meta['valor_atual']:.2f}\n"
                f"  • Meta total: R$ {meta['valor_meta']:.2f}\n"
                f"  • Prazo: {meta['data_meta'].strftime('%d/%m/%Y')}\n\n"
                f"💡 <b>Para recuperar:</b>\n"
                f"Economize <b>R$ {meta['aporte_corretivo']:.2f}/mês</b> "
                f"a partir de agora.\n\n"
                f"Use /metas para ver todas as suas metas."
            )
            
            await bot.send_message(
                chat_id=usuario.telegram_id,
                text=mensagem,
                parse_mode='HTML'
            )
        
        logger.info(f"📨 Alerta de metas enviado para usuário {usuario.telegram_id}")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar alerta de metas: {e}")


# ============================================================================
# RESUMO SEMANAL - NOVO JOB
# ============================================================================

async def _gerar_dica_ia_semanal(dados_semana: dict) -> str:
    """Gera uma dica personalizada usando a IA baseada no resumo da semana"""
    import google.generativeai as genai
    import config
    
    if not config.GEMINI_API_KEY:
        return "Continue organizando suas finanças e mantendo tudo no controle!"
        
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        
        prompt = f"""Você é o Alfredo, o assistente financeiro do app ContaComigo.
O usuário recebeu este resumo semanal:
- Receitas: R$ {dados_semana['receitas']:.2f}
- Despesas: R$ {dados_semana['despesas']:.2f}
- Saldo: R$ {dados_semana['saldo']:.2f}
- Top Categorias: {', '.join([f"{c['nome']} (R$ {c['valor']:.2f})" for c in dados_semana['categorias'][:2]])}

Baseado nisso, dê UMA dica curta (máximo 2 frases) de amigo/consultor para a próxima semana.
Seja direto, encorajador, use um emoji e assine como 'Alfredo'.
"""
        response = await model.generate_content_async(prompt)
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar dica semanal da IA: {e}")
        
    return "Lembre-se: o controle financeiro de hoje é a paz de espírito de amanhã!"

async def enviar_resumo_semanal_usuario(bot, usuario: Usuario):
    """Gera e envia o resumo semanal em HTML para o usuário"""
    db = next(get_db())
    try:
        from datetime import timezone as dt_timezone
        hoje = datetime.now(dt_timezone.utc)
        data_inicio = hoje - timedelta(days=7)
        
        logger.info(f"📊 Processando resumo semanal para {usuario.telegram_id} (id:{usuario.id})")
        
        lancamentos = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario.id,
                Lancamento.data_transacao >= data_inicio,
                Lancamento.data_transacao <= hoje,
                Lancamento.status != "ignorado"
            )
        ).all()
        
        if not lancamentos:
            logger.info(f"ℹ️ Usuário {usuario.id} não teve lançamentos nos últimos 7 dias. Pulando resumo.")
            return False
            
        receitas = sum(float(l.valor) for l in lancamentos if getattr(l, 'tipo', '') in ("Entrada", "Receita") or float(l.valor) > 0)
        despesas = sum(abs(float(l.valor)) for l in lancamentos if getattr(l, 'tipo', '') in ("Saída", "Despesa") or float(l.valor) < 0)
        
        if receitas == 0 and despesas == 0:
            logger.info(f"ℹ️ Usuário {usuario.id} teve lançamentos mas totais são zero. Pulando resumo.")
            return False

        saldo_semana = receitas - despesas
        logger.info(f"✅ Gerando resumo para {usuario.id}: rec={receitas}, desp={despesas}")

        # Top gastos
        gastos = [l for l in lancamentos if (getattr(l, 'tipo', '') in ("Saída", "Despesa") or float(l.valor) < 0)]
        gastos_ordenados = sorted(gastos, key=lambda x: abs(float(x.valor)), reverse=True)[:3]
        
        # Categorias
        cats = {}
        for g in gastos:
            cat_nome = g.categoria.nome if g.categoria else "Outros"
            cats[cat_nome] = cats.get(cat_nome, 0) + abs(float(g.valor))
            
        cats_ordenadas = [{"nome": k, "valor": v} for k, v in sorted(cats.items(), key=lambda item: item[1], reverse=True)]
        
        # Formas de pagamento
        formas = {}
        for g in gastos:
            fp = g.forma_pagamento or "Outros"
            formas[fp] = formas.get(fp, 0) + 1
        total_formas = sum(formas.values()) or 1
        formas_percent = [{"nome": k, "pct": (v/total_formas)*100} for k, v in sorted(formas.items(), key=lambda item: item[1], reverse=True)[:2]]

        dados_ia = {
            'receitas': receitas,
            'despesas': despesas,
            'saldo': saldo_semana,
            'categorias': cats_ordenadas
        }
        
        dica_alfredo = await _gerar_dica_ia_semanal(dados_ia)
        
        def fbrl(v):
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
        data_ini_str = data_inicio.strftime("%d/%m")
        data_fim_str = hoje.strftime("%d/%m")
        
        msg = f"📊 <b>Seu Resumo Semanal Chegou!</b> 🗓️ <i>({data_ini_str} a {data_fim_str})</i>\n\n"
        msg += f"Olá, {usuario.nome or 'Amigo'}! Aqui está o raio-x da sua semana financeira. Vamos ver como você se saiu?\n\n"
        msg += f"💰 <b>Movimentação Geral</b>\n"
        msg += f"🟢 <b>Recebeu:</b> <code>{fbrl(receitas)}</code>\n"
        msg += f"🔴 <b>Gastou:</b> <code>{fbrl(despesas)}</code>\n"
        
        sinal = "+" if saldo_semana >= 0 else "-"
        emoji_saldo = "✅" if saldo_semana >= 0 else "⚠️"
        msg += f"💳 <b>Saldo da Semana:</b> <code>{sinal} {fbrl(abs(saldo_semana))}</code> {emoji_saldo}\n\n"
        
        if gastos_ordenados:
            msg += f"🏆 <b>Top Maiores Gastos</b>\n"
            icones = ["1️⃣", "2️⃣", "3️⃣"]
            for i, g in enumerate(gastos_ordenados):
                desc = (g.descricao[:25] + "..") if len(g.descricao) > 25 else g.descricao
                msg += f"{icones[i]} {desc} - <code>{fbrl(abs(float(g.valor)))}</code>\n"
            msg += "\n"
            
        if cats_ordenadas:
            msg += f"🍕 <b>Onde seu dinheiro mais foi?</b>\n"
            for c in cats_ordenadas[:3]:
                pct = (c['valor'] / despesas * 100) if despesas > 0 else 0
                msg += f"• {c['nome']}: {pct:.0f}% (<code>{fbrl(c['valor'])}</code>)\n"
            msg += "\n"
            
        if formas_percent:
            msg += f"💳 <b>Como você mais pagou?</b>\n"
            for fp in formas_percent:
                msg += f"• {fp['nome'].replace('_', ' ').title()} ({fp['pct']:.0f}%)\n"
            msg += "\n"
            
        msg += f"🤖 <b>Dica do Alfredo:</b>\n<i>\"{dica_alfredo}\"</i>\n\n"
        msg += "Boa semana e conte comigo! 🚀"
        
        await bot.send_message(
            chat_id=usuario.telegram_id,
            text=msg,
            parse_mode='HTML'
        )
        return True
    except Exception as e:
        logger.error(f"Erro ao processar resumo semanal do usuário {usuario.id}: {e}")
        return False
    finally:
        db.close()

async def job_resumo_semanal(context):
    """Job que roda aos Domingos às 19h para enviar o resumo da semana"""
    try:
        logger.info("📊 Iniciando Job de Resumo Semanal...")
        db = next(get_db())
        # Notifica usuários ativos ou que pediram insights
        usuarios = db.query(Usuario).filter(Usuario.telegram_id.isnot(None)).all()
        
        logger.info(f"🔍 Candidatos ao resumo semanal: {len(usuarios)} usuários encontrados.")
        
        enviados = 0
        for usuario in usuarios:
            notif_insights = getattr(usuario, 'notif_insights', True)
            if notif_insights:
                if await enviar_resumo_semanal_usuario(context.bot, usuario):
                    enviados += 1
            else:
                logger.info(f"🚫 Usuário {usuario.id} desativou notif_insights. Pulando.")
                    
        logger.info(f"✅ Job Resumo Semanal finalizado: {enviados} usuários notificados.")
    except Exception as e:
        logger.error(f"Erro no job de resumo semanal: {e}")

# ============================================================================
# JOB PRINCIPAL - EXECUTADO DIARIAMENTE
# ============================================================================

async def job_assistente_proativo(context):
    """
    Job principal que roda diariamente às 20h
    Analisa todos os usuários ativos e envia alertas quando necessário
    """
    try:
        logger.info("🤖 Iniciando Assistente Proativo...")
        
        db = next(get_db())
        
        # Buscar usuários ativos (com atividade nos últimos 30 dias)
        data_limite = datetime.now() - timedelta(days=30)
        
        usuarios_ativos = db.query(Usuario).join(
            Lancamento, Usuario.id == Lancamento.id_usuario
        ).filter(
            Lancamento.data_transacao >= data_limite
        ).distinct().all()
        
        if not usuarios_ativos:
            logger.info("ℹ️  Nenhum usuário ativo para analisar")
            return
        
        total_usuarios = len(usuarios_ativos)
        alertas_enviados = 0
        
        logger.info(f"📊 Analisando {total_usuarios} usuários ativos...")
        
        for usuario in usuarios_ativos:
            # Trava de preferências de notificação
            notif_insights = getattr(usuario, 'notif_insights', True)
            notif_alertas_risco = getattr(usuario, 'notif_alertas_risco', True)
            if not notif_insights and not notif_alertas_risco:
                continue

            try:
                enviou_alerta = await analisar_e_notificar_usuario(context.bot, usuario)
                if enviou_alerta:
                    alertas_enviados += 1
            except Exception as e:
                logger.error(f"❌ Erro ao processar usuário {usuario.id}: {e}")
                continue
        
        logger.info(
            f"✅ Assistente Proativo concluído: "
            f"{alertas_enviados}/{total_usuarios} usuários notificados"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no job do assistente proativo: {e}", exc_info=True)
    finally:
        db.close()
