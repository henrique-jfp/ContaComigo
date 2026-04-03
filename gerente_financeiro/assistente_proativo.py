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


# ============================================================================
# ANÁLISE DE GASTOS ELEVADOS
# ============================================================================

def calcular_gastos_mes_atual(usuario_id: int) -> float:
    """Calcula o total de gastos do mês atual"""
    db = next(get_db())
    try:
        hoje = datetime.now()
        
        total = db.query(func.sum(Lancamento.valor)).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                Lancamento.tipo == 'Saída',
                extract('year', Lancamento.data_transacao) == hoje.year,
                extract('month', Lancamento.data_transacao) == hoje.month
            )
        ).scalar()
        
        return float(total or 0)
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
                Lancamento.tipo == 'Saída',
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
                    Lancamento.tipo == 'Saída',
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
                    Lancamento.tipo == 'Saída',
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
                Lancamento.tipo == 'Saída',
                Lancamento.data_transacao >= data_inicio
            )
        ).order_by(Lancamento.data_transacao).all()
        
        # Agrupar por descrição similar
        grupos_descricao = {}
        
        for lanc in lancamentos:
            # Normalizar descrição (minúsculas, sem números de fatura)
            desc_normalizada = lanc.descricao.lower()
            
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
    if hoje >= objetivo.data_meta:
        return 100.0
    
    # Calcular dias desde a criação
    dias_totais = (objetivo.data_meta - objetivo.data_criacao).days
    dias_decorridos = (hoje - objetivo.data_criacao).days
    
    if dias_totais <= 0:
        return 100.0
    
    progresso_esperado = (dias_decorridos / dias_totais) * 100
    
    return min(progresso_esperado, 100.0)


def calcular_aporte_corretivo(objetivo: Objetivo) -> float:
    """
    Calcula quanto o usuário precisa aportar por mês para recuperar a meta
    """
    hoje = datetime.now().date()
    
    # Se já passou o prazo
    if hoje >= objetivo.data_meta:
        return float(objetivo.valor_meta - objetivo.valor_atual)
    
    # Calcular meses restantes
    meses_restantes = (objetivo.data_meta.year - hoje.year) * 12 + (objetivo.data_meta.month - hoje.month)
    
    if meses_restantes <= 0:
        meses_restantes = 1
    
    # Quanto falta para atingir a meta
    falta = float(objetivo.valor_meta - objetivo.valor_atual)
    
    # Aporte mensal necessário
    aporte_mensal = falta / meses_restantes
    
    return aporte_mensal


def analisar_metas_usuario(usuario_id: int) -> Optional[Dict]:
    """
    Análise de metas em risco do usuário
    
    Returns:
        Dict com informações do alerta ou None se metas estão ok
    """
    db = next(get_db())
    try:
        # Buscar metas ativas
        metas = db.query(Objetivo).filter(
            and_(
                Objetivo.id_usuario == usuario_id,
                Objetivo.ativo == True,
                Objetivo.data_meta >= datetime.now().date()
            )
        ).all()
        
        if not metas:
            return None
        
        metas_em_risco = []
        
        for meta in metas:
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
