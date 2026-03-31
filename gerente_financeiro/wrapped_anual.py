"""
🎊 Wrapped Financeiro Anual - MaestroFin
========================================

Sistema que gera uma retrospectiva emocionante do ano financeiro do usuário,
similar ao Spotify Wrapped, com estatísticas, curiosidades e mensagem inspiradora.

Enviado automaticamente no dia 31 de dezembro às 13h.

Autor: Henrique Freitas
Data: 18/11/2025
Versão: 3.2.0
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, and_, extract, desc
from sqlalchemy.orm import joinedload
from decimal import Decimal
import calendar

from database.database import get_db
from models import Usuario, Lancamento, Objetivo, Categoria, ConquistaUsuario

logger = logging.getLogger(__name__)

# ============================
# Normalização e inferência
# ============================
import unicodedata
from typing import Any


def _normalize_text(s: Optional[str]) -> str:
    """Remove acentos e normaliza texto para matching simples."""
    if not s:
        return ""
    s = str(s)
    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ASCII', 'ignore').decode('ascii')
    return s.lower()


_KEYWORD_CATEGORY_MAP = {
    'mercado': 'Alimentação', 'supermercado': 'Alimentação', 'panific': 'Alimentação',
    'padaria': 'Alimentação', 'ifood': 'Alimentação', 'rappi': 'Alimentação', 'ubereats': 'Alimentação',
    'restaurante': 'Alimentação', 'uber': 'Transporte', '99': 'Transporte', 'posto': 'Transporte',
    'gasolina': 'Transporte', 'farmacia': 'Saúde', 'cinema': 'Lazer', 'netflix': 'Assinaturas',
    'spotify': 'Assinaturas', 'renner': 'Vestuário', 'rendimento': 'Investimentos', 'investimento': 'Investimentos',
    'boleto': 'Pagamentos', 'pix': 'Pix', 'transferencia': 'Transferência'
}


def infer_category_from_description(description: Optional[str]) -> Optional[str]:
    desc = _normalize_text(description)
    if not desc:
        return None
    for kw, cat in _KEYWORD_CATEGORY_MAP.items():
        if kw in desc:
            return cat
    # heurísticas adicionais
    if 'mercad' in desc or 'mercato' in desc:
        return 'Alimentação'
    if 'formiguinha' in desc:
        return 'Alimentação'
    return None


def infer_payment_method(origem: Optional[str], descricao: Optional[str]) -> str:
    o_raw = origem or ''
    d = _normalize_text(descricao)
    o = _normalize_text(o_raw)

    # Se a origem já veio formatada pelo serviço (ex: 'Cartão de Crédito • Nubank'), preserva
    if o_raw and '•' in str(o_raw):
        return str(o_raw)

    # Detectores principais
    if 'pix' in o or 'pix' in d:
        return 'Pix'

    # Cartões: detectar presença de palavras-chave e, se possível, manter o nome do emissor
    if 'cartao' in o or 'credito' in o or 'debito' in o or 'visa' in d or 'master' in d or 'elo' in d or 'amex' in d:
        # Se a origem textual contiver o nome do banco, tenta preservar
        if o_raw and len(o_raw) > 3:
            # Normaliza capitalização mínima
            return o_raw
        # Caso contrário, decide entre crédito/débito por palavras-chave
        if 'debito' in o:
            return 'Cartão de Débito'
        return 'Cartão de Crédito'

    # Transferências e boletos
    if 'transfer' in o or 'ted' in o or 'doc' in o or 'transferência' in d or 'transferencia' in d:
        return 'Transferência'
    if 'boleto' in d or 'boleto' in o:
        return 'Boleto'

    # Nunca retornar origem bancária como forma de pagamento
    # Caso a origem contenha algum termo de integração removida, ignorar
        return o_raw

    # Fallback: se a origem contém algo plausível, title-case; senão 'Desconhecido'
    if o:
        return o.title()
    return 'Desconhecido'


def derive_lancamento_meta(lanc: Any) -> Tuple[str, str, str]:
    """Deriva (tipo, categoria, metodo_pagamento) a partir do objeto Lancamento."""
    tipo_reg = getattr(lanc, 'tipo', None) or ''
    tipo_norm = str(tipo_reg).title() if tipo_reg else ''
    # categoria registrada
    try:
        cat_reg = lanc.categoria.nome if getattr(lanc, 'categoria', None) else None
    except Exception:
        cat_reg = None

    cat_inferida = infer_category_from_description(getattr(lanc, 'descricao', None))
    pay_method = infer_payment_method(getattr(lanc, 'meio_pagamento', None) or getattr(lanc, 'origem', None), getattr(lanc, 'descricao', None))

    if cat_reg:
        cat_reg_norm = _normalize_text(cat_reg)
        if tipo_norm == 'Despesa' and ('receita' in cat_reg_norm or 'receitas' in cat_reg_norm):
            categoria_effective = cat_inferida or 'Outros'
        else:
            categoria_effective = cat_reg
    else:
        categoria_effective = cat_inferida or 'Outros'

    tipo_effective = tipo_norm or ('Receita' if (cat_inferida and cat_inferida == 'Investimentos') else 'Despesa')
    return tipo_effective, categoria_effective, pay_method



# ============================================================================
# CÁLCULOS DE ESTATÍSTICAS ANUAIS
# ============================================================================

def calcular_resumo_financeiro(db, usuario_id: int, ano: int) -> Dict:
    """Calcula resumo geral de receitas e despesas do ano"""
    try:
        # Usar INNER JOIN para garantir que apenas lançamentos com categoria sejam considerados
        # e filtrar 'Transferência' diretamente na query para eficiência.
        lancamentos_financeiros = db.query(Lancamento).join(Categoria).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                extract('year', Lancamento.data_transacao) == ano,
                func.lower(Categoria.nome) != 'transferência'
            )
        ).all()

        # Calcular receitas e despesas apenas dos lançamentos financeiros
        # Usar meta derivada para corrigir categorias/tipos inconsistentes
        receitas = 0.0
        despesas = 0.0
        for l in lancamentos_financeiros:
            tipo_eff, _, _ = derive_lancamento_meta(l)
            try:
                val = float(l.valor)
            except Exception:
                val = 0.0
            if tipo_eff == 'Receita':
                receitas += val
            else:
                despesas += val
        
        economia = receitas - despesas
        taxa_poupanca = (economia / receitas * 100) if receitas > 0 else 0
        
        return {
            'receitas_total': receitas,
            'despesas_total': despesas,
            'economia_total': economia,
            'taxa_poupanca': taxa_poupanca
        }
    except Exception as e:
        logger.error(f"Erro em calcular_resumo_financeiro: {e}", exc_info=True)
        raise

def calcular_categorias_top(db, usuario_id: int, ano: int, limit: int = 5) -> List[Dict]:
    """Retorna as categorias com maiores gastos do ano"""
    try:
        # Usar INNER JOIN e filtrar 'Transferência' na query
        lancamentos_financeiros = db.query(Lancamento).join(Categoria).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                extract('year', Lancamento.data_transacao) == ano,
                func.lower(Categoria.nome) != 'transferência'
            )
        ).all()

        # Agrupar por categoria efetiva usando heurísticas
        gastos_por_categoria: Dict[str, Dict[str, object]] = {}
        for l in lancamentos_financeiros:
            tipo_eff, cat_eff, _ = derive_lancamento_meta(l)
            if tipo_eff != 'Despesa':
                continue
            cat_nome = cat_eff or (l.categoria.nome if getattr(l, 'categoria', None) else 'Sem Categoria')
            if cat_nome not in gastos_por_categoria:
                gastos_por_categoria[cat_nome] = {'total': 0.0, 'quantidade': 0}
            try:
                gastos_por_categoria[cat_nome]['total'] += float(l.valor)
            except Exception:
                pass
            gastos_por_categoria[cat_nome]['quantidade'] += 1
        
        # Ordenar e limitar
        categorias_ordenadas = sorted(
            [{'categoria': cat, **dados} for cat, dados in gastos_por_categoria.items()],
            key=lambda x: x['total'],
            reverse=True
        )[:limit]
        
        return categorias_ordenadas
    except Exception as e:
        logger.error(f"Erro em calcular_categorias_top: {e}", exc_info=True)
        raise

def calcular_evolucao_mensal(db, usuario_id: int, ano: int) -> Dict:
    """Calcula receitas e despesas mês a mês"""
    try:
        meses_dados = {}
        
        for mes in range(1, 13):            
            lancamentos_financeiros = db.query(Lancamento).join(Categoria).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    extract('year', Lancamento.data_transacao) == ano,
                    extract('month', Lancamento.data_transacao) == mes,
                    func.lower(Categoria.nome) != 'transferência'
                )
            ).all()
            
            # Calcular receitas e despesas usando tipo efetivo
            receitas = 0.0
            despesas = 0.0
            for l in lancamentos_financeiros:
                tipo_eff, _, _ = derive_lancamento_meta(l)
                try:
                    val = float(l.valor)
                except Exception:
                    val = 0.0
                if tipo_eff == 'Receita':
                    receitas += val
                else:
                    despesas += val
            
            mes_nome = calendar.month_name[mes]
            meses_dados[mes_nome] = {
                'receitas': float(receitas),
                'despesas': float(despesas),
                'saldo': float(receitas) - float(despesas)
            }
        
        return meses_dados
    except Exception as e:
        logger.error(f"Erro em calcular_evolucao_mensal: {e}", exc_info=True)
        raise

def encontrar_melhor_mes(db, usuario_id: int, ano: int) -> Dict:
    """Encontra o mês com maior economia"""
    try:
        melhor_mes = None
        maior_economia = float('-inf')
        
        for mes in range(1, 13):
            # Usar INNER JOIN e filtrar 'Transferência' na query
            lancamentos_financeiros = db.query(Lancamento).join(Categoria).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    extract('year', Lancamento.data_transacao) == ano,
                    extract('month', Lancamento.data_transacao) == mes,
                    func.lower(Categoria.nome) != 'transferência'
                )
            ).all()

            # Calcular economia usando tipo efetivo
            receitas = 0.0
            despesas = 0.0
            for l in lancamentos_financeiros:
                tipo_eff, _, _ = derive_lancamento_meta(l)
                try:
                    val = float(l.valor)
                except Exception:
                    val = 0.0
                if tipo_eff == 'Receita':
                    receitas += val
                else:
                    despesas += val
            economia = float(receitas) - float(despesas)
            
            if economia > maior_economia:
                maior_economia = economia
                melhor_mes = calendar.month_name[mes]
        
        return {
            'nome': melhor_mes,
            'economia': maior_economia
        }
    except Exception as e:
        logger.error(f"Erro em encontrar_melhor_mes: {e}", exc_info=True)
        raise

def encontrar_maior_gasto(db, usuario_id: int, ano: int) -> Dict:
    """Encontra a transação de maior valor do ano"""
    try:
        # Usar INNER JOIN e filtrar 'Transferência' na query (traz todos e aplica filtro local)
        lancamentos_financeiros = db.query(Lancamento).join(Categoria).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                extract('year', Lancamento.data_transacao) == ano,
                func.lower(Categoria.nome) != 'transferência'
            )
        ).all()

        # Encontrar o maior gasto considerando tipo efetivo
        gastos = []
        for l in lancamentos_financeiros:
            tipo_eff, cat_eff, _ = derive_lancamento_meta(l)
            if tipo_eff != 'Despesa':
                continue
            try:
                gastos.append((float(l.valor), l, cat_eff))
            except Exception:
                continue

        if gastos:
            maior_val, maior_obj, maior_cat = max(gastos, key=lambda x: x[0])
            return {
                'descricao': getattr(maior_obj, 'descricao', None) or '',
                'valor': float(maior_val),
                'data': getattr(maior_obj, 'data_transacao').strftime('%d/%m/%Y') if getattr(maior_obj, 'data_transacao', None) else '',
                'categoria': maior_cat or (maior_obj.categoria.nome if getattr(maior_obj, 'categoria', None) else 'Outros')
            }
        
        return None
    except Exception as e:
        logger.error(f"Erro em encontrar_maior_gasto: {e}", exc_info=True)
        raise

def calcular_metas_ano(db, usuario_id: int, ano: int) -> Dict:
    """Analisa metas criadas e atingidas no ano"""
    try:
        # Metas criadas no ano
        metas_criadas = db.query(Objetivo).filter(
            and_(
                Objetivo.id_usuario == usuario_id,
                extract('year', Objetivo.criado_em) == ano
            )
        ).all()
        
        # Metas atingidas (valor_atual >= valor_meta)
        metas_atingidas = [
            meta for meta in metas_criadas
            if meta.valor_atual >= meta.valor_meta
        ]
        
        return {
            'metas_totais': len(metas_criadas),
            'metas_atingidas': len(metas_atingidas),
            'taxa_sucesso': (len(metas_atingidas) / len(metas_criadas) * 100) if metas_criadas else 0,
            'metas_detalhes': [
                {
                    'descricao': meta.descricao,
                    'valor_meta': float(meta.valor_meta),
                    'valor_atual': float(meta.valor_atual),
                    'atingida': meta.valor_atual >= meta.valor_meta
                }
                for meta in metas_criadas
            ]
        }
    except Exception as e:
        logger.error(f"Erro em calcular_metas_ano: {e}", exc_info=True)
        raise

def calcular_estatisticas_uso(db, usuario_id: int, ano: int) -> Dict:
    """Calcula estatísticas de uso do bot no ano"""
    try:
        # Total de transações registradas
        total_lancamentos = db.query(func.count(Lancamento.id)).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                extract('year', Lancamento.data_transacao) == ano
            )
        ).scalar() or 0
        
        # Dias com atividade
        dias_ativos = db.query(
            func.count(func.distinct(func.date(Lancamento.data_transacao)))
        ).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                extract('year', Lancamento.data_transacao) == ano
            )
        ).scalar() or 0
        
        # Conquistas desbloqueadas no ano
        conquistas = db.query(func.count(ConquistaUsuario.id)).filter(
            and_(
                ConquistaUsuario.id_usuario == usuario_id,
                extract('year', ConquistaUsuario.data_conquista) == ano
            )
        ).scalar() or 0
        
        # XP total (se tiver campo de XP)
        usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
        xp_total = usuario.xp if hasattr(usuario, 'xp') else 0
        nivel_atual = usuario.nivel if hasattr(usuario, 'nivel') else 0
        
        return {
            'total_lancamentos': total_lancamentos,
            'dias_ativos': dias_ativos,
            'conquistas': conquistas,
            'xp_total': xp_total,
            'nivel_atual': nivel_atual
        }
    except Exception as e:
        logger.error(f"Erro em calcular_estatisticas_uso: {e}", exc_info=True)
        raise

# ============================================================================
# GERAÇÃO DE CURIOSIDADES
# ============================================================================

def gerar_curiosidades(db, usuario_id: int, ano: int) -> List[str]:
    """Gera insights curiosos sobre os gastos do usuário"""
    curiosidades = []
    
    try:
        # Palavras-chave para buscar em descrições
        palavras_interesse = {
            'pizza': '🍕 pizza',
            'café': '☕ café',
            'uber': '🚗 Uber',
            '99': '🚗 99',
            'ifood': '🍔 iFood',
            'rappi': '🍔 Rappi',
            'netflix': '🎬 Netflix',
            'spotify': '🎵 Spotify',
            'amazon': '📦 Amazon',
            'cinema': '🎬 cinema',
            'academia': '💪 academia',
            'viagem': '✈️ viagens'
        }
        
        for palavra, emoji_texto in palavras_interesse.items():
            count = db.query(func.count(Lancamento.id)).filter(
                and_(
                    Lancamento.id_usuario == usuario_id,
                    Lancamento.tipo == 'Despesa',
                    extract('year', Lancamento.data_transacao) == ano,
                    Lancamento.descricao.ilike(f'%{palavra}%')
                )
            ).scalar() or 0
            
            if count > 0:
                frequencia = count / 12  # Média por mês
                if frequencia >= 1:
                    curiosidades.append(
                        f"{emoji_texto}: {count} vezes no ano ({frequencia:.1f}x por mês em média)"
                    )
        
        # Dia da semana preferido para gastar
        # (necessita de análise mais complexa - simplificado)
        
        # Categoria mais frequente
        categoria_freq = db.query(
            Categoria.nome,
            func.count(Lancamento.id).label('vezes')
        ).join(
            Lancamento, Lancamento.id_categoria == Categoria.id
        ).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                Lancamento.tipo == 'Despesa',
                extract('year', Lancamento.data_transacao) == ano
            )
        ).group_by(Categoria.nome).order_by(desc('vezes')).first()
        
        if categoria_freq:
            curiosidades.append(
                f"📊 Sua categoria favorita: {categoria_freq.nome} ({categoria_freq.vezes} transações)"
            )
        
        return curiosidades
    except Exception as e:
        logger.error(f"Erro em gerar_curiosidades: {e}", exc_info=True)
        raise

def comparar_com_ano_anterior(db, usuario_id: int, ano_atual: int) -> Optional[Dict]:
    """Compara estatísticas com o ano anterior"""
    try:
        ano_anterior = ano_atual - 1
        
        # Verificar se há dados do ano anterior
        tem_dados_anterior = db.query(func.count(Lancamento.id)).filter(
            and_(
                Lancamento.id_usuario == usuario_id,
                extract('year', Lancamento.data_transacao) == ano_anterior
            )
        ).scalar() > 0
        
        if not tem_dados_anterior:
            return None
        
        # Calcular estatísticas de ambos os anos
        stats_atual = calcular_resumo_financeiro(db, usuario_id, ano_atual)
        stats_anterior = calcular_resumo_financeiro(db, usuario_id, ano_anterior)
        
        # Calcular variações percentuais
        var_receitas = ((stats_atual['receitas_total'] - stats_anterior['receitas_total']) / 
                       stats_anterior['receitas_total'] * 100) if stats_anterior['receitas_total'] > 0 else 0
        
        var_despesas = ((stats_atual['despesas_total'] - stats_anterior['despesas_total']) / 
                       stats_anterior['despesas_total'] * 100) if stats_anterior['despesas_total'] > 0 else 0
        
        var_economia = ((stats_atual['economia_total'] - stats_anterior['economia_total']) / 
                       abs(stats_anterior['economia_total']) * 100) if stats_anterior['economia_total'] != 0 else 0
        
        return {
            'ano_anterior': ano_anterior,
            'var_receitas': var_receitas,
            'var_despesas': var_despesas,
            'var_economia': var_economia,
            'stats_anterior': stats_anterior,
            'melhorou': stats_atual['taxa_poupanca'] > stats_anterior['taxa_poupanca']
        }
    except Exception as e:
        logger.error(f"Erro em comparar_com_ano_anterior: {e}", exc_info=True)
        raise

# ============================================================================
# FORMATAÇÃO DA MENSAGEM WRAPPED
# ============================================================================

def avaliar_performance_poupanca(taxa: float) -> Tuple[str, str]:
    """Retorna emoji e avaliação baseado na taxa de poupança"""
    if taxa >= 30:
        return "🏆", "EXCEPCIONAL"
    elif taxa >= 20:
        return "🌟", "EXCELENTE"
    elif taxa >= 10:
        return "👏", "MUITO BOM"
    elif taxa >= 5:
        return "👍", "BOM"
    elif taxa > 0:
        return "💪", "PODE MELHORAR"
    else:
        return "⚠️", "ATENÇÃO NECESSÁRIA"


def formatar_wrapped_completo(usuario: Usuario, ano: int) -> str:
    """
    Gera a mensagem completa do Wrapped Anual
    Esta é a mensagem ÉPICA que será enviada aos usuários!
    """
    try:
        db = next(get_db())
        # Coletar todas as estatísticas
        # Todas as funções agora recebem a mesma sessão 'db'
        resumo = calcular_resumo_financeiro(db, usuario.id, ano)
        uso = calcular_estatisticas_uso(db, usuario.id, ano) # Movido para cima para ter o total de lançamentos
        
        categorias_top = calcular_categorias_top(db, usuario.id, ano, 5)
        melhor_mes = encontrar_melhor_mes(db, usuario.id, ano)
        maior_gasto = encontrar_maior_gasto(db, usuario.id, ano)
        metas = calcular_metas_ano(db, usuario.id, ano)
        curiosidades = gerar_curiosidades(db, usuario.id, ano)
        comparacao = comparar_com_ano_anterior(db, usuario.id, ano)
        
        # Avaliar performance
        emoji_perf, avaliacao_perf = avaliar_performance_poupanca(resumo['taxa_poupanca'])
        
        # Construir mensagem épica
        mensagem = f"""
🎆✨ <b>SEU ANO FINANCEIRO {ano} EM NÚMEROS!</b> ✨🎆

Olá, <b>{usuario.nome_completo}</b>! 

Que jornada incrível você teve neste ano! 🚀
Vamos relembrar tudo que você conquistou?

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>RESUMO GERAL</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Receitas: <code>R$ {resumo['receitas_total']:,.2f}</code>
📉 Despesas: <code>R$ {resumo['despesas_total']:,.2f}</code>
✨ Você economizou: <code>R$ {resumo['economia_total']:,.2f}</code>

{emoji_perf} Sua taxa de poupança foi <b>{avaliacao_perf}</b>: {resumo['taxa_poupanca']:.1f}%
"""

        # Comparação com ano anterior
        if comparacao:
            emoji_trend = "📈" if comparacao['melhorou'] else "📊"
            mensagem += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
{emoji_trend} <b>COMPARAÇÃO COM {comparacao['ano_anterior']}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            if comparacao['var_receitas'] > 0:
                mensagem += f"📈 Receitas: +{comparacao['var_receitas']:.1f}% (cresceu!)\n"
            else:
                mensagem += f"📉 Receitas: {comparacao['var_receitas']:.1f}%\n"
            
            if comparacao['var_despesas'] < 0:
                mensagem += f"💚 Despesas: {comparacao['var_despesas']:.1f}% (economizou!)\n"
            else:
                mensagem += f"📊 Despesas: +{comparacao['var_despesas']:.1f}%\n"
            
            if comparacao['melhorou']:
                mensagem += f"\n🎉 <b>Parabéns! Você melhorou sua saúde financeira em {ano}!</b>\n"
        
        # Categorias top
        if categorias_top:
            mensagem += """
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>ONDE FOI SEU DINHEIRO</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for idx, cat in enumerate(categorias_top, 1):
                percentual = (cat['total'] / resumo['despesas_total'] * 100) if resumo['despesas_total'] > 0 else 0
                mensagem += f"{idx}. <b>{cat['categoria']}</b>\n"
                mensagem += f"   💰 R$ {cat['total']:,.2f} ({percentual:.1f}% do total)\n"
                mensagem += f"   🔢 {cat['quantidade']} transações\n\n"
        
        # Momentos marcantes
        mensagem += """
━━━━━━━━━━━━━━━━━━━━━━━━━━
😱 <b>MOMENTOS MARCANTES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        if maior_gasto:
            mensagem += f"💸 <b>Maior gasto do ano:</b>\n"
            mensagem += f"   {maior_gasto['descricao']}\n"
            mensagem += f"   R$ {maior_gasto['valor']:,.2f} em {maior_gasto['data']}\n\n"
        
        if melhor_mes['economia'] > 0:
            mensagem += f"💰 <b>Mês que mais economizou:</b>\n"
            mensagem += f"   {melhor_mes['nome']} (R$ {melhor_mes['economia']:,.2f})\n\n"
        
        # Metas
        if metas['metas_totais'] > 0:
            mensagem += """
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>METAS E CONQUISTAS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            mensagem += f"Você criou <b>{metas['metas_totais']} metas</b> em {ano}\n"
            mensagem += f"✅ Atingiu <b>{metas['metas_atingidas']}</b> delas ({metas['taxa_sucesso']:.0f}% de sucesso)\n\n"
            
            if metas['metas_atingidas'] > 0:
                mensagem += "<b>Metas conquistadas:</b>\n"
                for meta in metas['metas_detalhes']:
                    if meta['atingida']:
                        mensagem += f"  ✅ {meta['descricao']} - R$ {meta['valor_meta']:,.2f}\n"
                mensagem += "\n"
        
        # Curiosidades
        if curiosidades:
            mensagem += """
━━━━━━━━━━━━━━━━━━━━━━━━━━
🤯 <b>CURIOSIDADES SOBRE VOCÊ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for curiosidade in curiosidades[:5]:  # Máximo 5
                mensagem += f"• {curiosidade}\n"
            mensagem += "\n"
        
        # Estatísticas de uso
        mensagem += """
━━━━━━━━━━━━━━━━━━━━━━━━━━
🎮 <b>SUA JORNADA NO MAESTROFIN</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        mensagem += f"📝 Você registrou <b>{uso['total_lancamentos']} transações</b>\n"
        mensagem += f"📅 Usou o bot em <b>{uso['dias_ativos']} dias</b> (de 365)\n"
        
        if uso['conquistas'] > 0:
            mensagem += f"🏅 Desbloqueou <b>{uso['conquistas']} conquistas</b>\n"
        
        if uso['xp_total'] > 0:
            mensagem += f"⭐ Acumulou <b>{uso['xp_total']} XP</b> (Nível {uso['nivel_atual']})\n"
        
        # Mensagem inspiradora final
        ano_novo = ano + 1
        mensagem += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━
💝 <b>NOSSA MENSAGEM PARA VOCÊ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

Caro(a) {usuario.nome_completo},

<b>Obrigado por confiar em nós!</b> ❤️

Ter você conosco nesta jornada foi uma honra. 
Cada número que você viu aqui representa não apenas 
dinheiro, mas suas escolhas, seus sonhos e seu 
crescimento pessoal.

Você tomou o controle da sua vida financeira, e isso 
é algo <b>extraordinário</b>! 🌟

Enquanto muitos apenas sonham, você AGIU. Registrou 
gastos, criou metas, economizou, aprendeu. Isso te 
coloca entre os <b>poucos que realmente se importam</b> 
com o próprio futuro.

━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 <b>DESAFIO PARA {ano_novo}</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

Com base nos seus dados, nossa IA sugere:
"""
        
        # Sugestão personalizada baseada nos dados
        if resumo['taxa_poupanca'] < 10:
            sugestao_meta = resumo['receitas_total'] * 0.15 / 12  # 15% anual dividido por 12
            mensagem += f"""
💡 <b>Meta de Poupança:</b>
   Tente economizar R$ {sugestao_meta:,.2f} por mês
   = R$ {sugestao_meta * 12:,.2f} no ano
   (15% da sua receita média)
"""
        elif resumo['taxa_poupanca'] < 20:
            sugestao_meta = resumo['receitas_total'] * 0.25 / 12  # 25% anual
            mensagem += f"""
💡 <b>Próximo Nível:</b>
   Você já economiza bem! Que tal aumentar para 
   R$ {sugestao_meta:,.2f} por mês?
   = R$ {sugestao_meta * 12:,.2f} no ano (25%)
"""
        else:
            mensagem += """
🏆 <b>Você é um MESTRE!</b>
   Sua disciplina financeira é inspiradora!
   Continue assim e considere investir suas economias
   para fazer o dinheiro trabalhar por você! 💰
"""
        
        # Encerramento épico
        mensagem += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ Que {ano_novo} seja o ano dos seus sonhos realizados!
✨ Que você alcance metas ainda maiores!
✨ Que a prosperidade esteja sempre ao seu lado!

Nós estaremos aqui, todos os dias, te apoiando 
nessa jornada. 🤝

<b>Feliz Ano Novo!</b> 🎊🎉
Com carinho e gratidão,
🎼 Equipe MaestroFin

───────────────────────────
<i>💡 Use /metas para criar seus objetivos de {ano_novo}!</i>
"""
        
        return mensagem
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar wrapped para usuário {usuario.id}: {e}", exc_info=True)
        if 'db' in locals():
            db.close()
        return None


# ============================================================================
# JOB PRINCIPAL - EXECUTADO 31/DEZ ÀS 13H
# ============================================================================

async def job_wrapped_anual(context):
    """
    Job que roda automaticamente no dia 31 de dezembro às 13h
    Envia o Wrapped Financeiro para todos os usuários ativos
    """
    try:
        ano_atual = datetime.now().year
        logger.info(f"🎊 Iniciando envio do Wrapped Financeiro {ano_atual}...")
        
        db = next(get_db())
        
        # Buscar usuários com atividade no ano atual
        usuarios_ativos = db.query(Usuario).join(
            Lancamento, Usuario.id == Lancamento.id_usuario
        ).filter(
            extract('year', Lancamento.data_transacao) == ano_atual
        ).distinct().all()
        
        if not usuarios_ativos:
            logger.info("ℹ️  Nenhum usuário ativo para enviar wrapped")
            return
        
        total_usuarios = len(usuarios_ativos)
        enviados_sucesso = 0
        
        logger.info(f"📊 Gerando wrapped para {total_usuarios} usuários...")
        
        for usuario in usuarios_ativos:
            try:
                # Gerar mensagem personalizada
                mensagem = formatar_wrapped_completo(usuario, ano_atual)
                
                if mensagem:
                    # Enviar mensagem
                    await context.bot.send_message(
                        chat_id=usuario.telegram_id,
                        text=mensagem,
                        parse_mode='HTML'
                    )
                    enviados_sucesso += 1
                    
                    logger.info(f"✅ Wrapped enviado para {usuario.nome_completo}")
                    
                    # Pequeno delay para não sobrecarregar a API do Telegram
                    await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Erro ao enviar wrapped para usuário {usuario.id}: {e}")
                continue
        
        logger.info(
            f"🎊 Wrapped Financeiro {ano_atual} concluído: "
            f"{enviados_sucesso}/{total_usuarios} enviados com sucesso"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no job wrapped anual: {e}", exc_info=True)
    finally:
        db.close()


# ============================================================================
# FUNÇÃO DE TESTE MANUAL
# ============================================================================

async def enviar_wrapped_manual(bot, usuario: Usuario, ano: int = None):
    """
    Envia o wrapped para um usuário específico (para testes)
    Se ano não especificado, usa ano atual
    """
    try:
        db = next(get_db())
        if ano is None:
            ano = datetime.now().year
        
        # A função formatar_wrapped_completo agora gerencia sua própria sessão
        # Vamos chamar a versão antiga da lógica aqui para teste manual
        mensagem = formatar_wrapped_completo(usuario, ano) # Esta função agora cria sua própria sessão
        
        if mensagem:
            await bot.send_message(
                chat_id=usuario.telegram_id,
                text=mensagem,
                parse_mode='HTML'
            )
            return True
        
        return False
    except Exception as e:
        if 'db' in locals():
            db.close()
        logger.error(f"❌ Erro ao enviar wrapped manual: {e}", exc_info=True)
        return False
