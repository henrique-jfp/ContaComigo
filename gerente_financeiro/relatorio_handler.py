# gerente_financeiro/relatorio_handler.py


from .analytics_utils import track_analytics

import logging
from datetime import datetime
from io import BytesIO
import os
import io
from dateutil.relativedelta import relativedelta
import re
import base64

from telegram import Update, InputFile
from telegram.ext import ContextTypes, CommandHandler
from jinja2 import Environment, FileSystemLoader

# Import ReportLab para geração de PDFs (WeasyPrint removido - incompatível com Railway)
try:
    from .pdf_generator import generate_financial_pdf
    REPORTLAB_AVAILABLE = True
    print("✅ ReportLab disponível para geração de PDFs")
except ImportError as e:
    print(f"❌ ReportLab não disponível: {e}")
    print("⚠️ Relatórios PDF não poderão ser gerados!")
    REPORTLAB_AVAILABLE = False
    generate_financial_pdf = None

from database.database import get_db
from .services import (
    gerar_contexto_relatorio,
    gerar_grafico_para_relatorio,
    gerar_grafico_evolucao_mensal,
    limpar_cache_usuario,
)
from . import services as services_module
from .gamification_utils import give_xp_for_action, touch_user_interaction
from database.database import get_or_create_user
from .monetization import ensure_user_plan_state, plan_allows_feature, upgrade_prompt_for_feature
from .ai_service import _smart_ai_completion_async

logger = logging.getLogger(__name__)


# =============================================================================
#  CONFIGURAÇÃO DO AMBIENTE JINJA2 E FILTROS CUSTOMIZADOS
#  (Esta seção deve ser executada apenas uma vez, quando o módulo é importado)
# =============================================================================

def nl2br_filter(s):
    """Filtro Jinja2 para converter quebras de linha em tags <br>."""
    if s is None:
        return ""
    return re.sub(r'\r\n|\r|\n', '<br>\n', str(s))

def color_palette_filter(index):
    """Filtro Jinja2 que retorna uma cor de uma paleta predefinida baseado no índice."""
    colors = ["#3498db", "#e74c3c", "#2ecc71", "#f1c40f", "#9b59b6", "#1abc9c", "#e67e22"]
    return colors[int(index) % len(colors)]

def safe_float_filter(value, default=0.0):
    """Filtro Jinja2 para converter valores para float de forma segura."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_format_currency(value):
    """Filtro Jinja2 para formatar valores monetários de forma segura."""
    try:
        return "%.2f" % float(value) if value is not None else "0.00"
    except (ValueError, TypeError):
        return "0.00"

# Define os caminhos para as pastas de templates e arquivos estáticos
templates_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
static_path = os.path.join(os.path.dirname(__file__), '..', 'static')

# Cria e configura o ambiente do Jinja2
env = Environment(
    loader=FileSystemLoader(templates_path),
    autoescape=True  # Ativa o autoescaping para segurança
)

# Adiciona os filtros customizados ao ambiente
env.filters['nl2br'] = nl2br_filter
env.filters['color_palette'] = color_palette_filter
env.filters['safe_float'] = safe_float_filter
env.filters['safe_currency'] = safe_format_currency


# =============================================================================
#  FUNÇÕES AUXILIARES PARA PROCESSAMENTO DE DADOS
# =============================================================================

def validar_e_completar_contexto(contexto_dados):
    """Valida e completa o contexto de dados para garantir que todos os campos necessários existam."""
    
    # Campos obrigatórios com valores padrão
    campos_padrao = {
        'mes_nome': 'Mês Atual',
        'ano': datetime.now().year,
        'receita_total': 0.0,
        'despesa_total': 0.0,
        'saldo_mes': 0.0,
        'taxa_poupanca': 0.0,
        'gastos_agrupados': [],
        'gastos_por_categoria_dict': {},
        'metas': [],
        'analise_ia': None,
        'has_data': False
    }
    
    # Aplica valores padrão para campos ausentes
    for campo, valor_padrao in campos_padrao.items():
        if campo not in contexto_dados or contexto_dados[campo] is None:
            contexto_dados[campo] = valor_padrao
    
    # Garante que valores numéricos sejam float
    campos_numericos = ['receita_total', 'despesa_total', 'saldo_mes', 'taxa_poupanca']
    for campo in campos_numericos:
        try:
            contexto_dados[campo] = float(contexto_dados[campo])
        except (ValueError, TypeError):
            contexto_dados[campo] = 0.0
    
    # Processa metas para garantir campos necessários
    if contexto_dados['metas']:
        for meta in contexto_dados['metas']:
            # Garante que todos os campos da meta existam
            meta_campos_padrao = {
                'descricao': 'Meta sem descrição',
                'valor_atual': 0.0,
                'valor_meta': 0.0,
                'progresso_percent': 0.0
            }
            
            for campo, valor_padrao in meta_campos_padrao.items():
                if campo not in meta or meta[campo] is None:
                    meta[campo] = valor_padrao
            
            # Converte valores numéricos
            try:
                meta['valor_atual'] = float(meta['valor_atual'])
                meta['valor_meta'] = float(meta['valor_meta'])
                
                # Calcula progresso se não estiver definido
                if meta['valor_meta'] > 0:
                    meta['progresso_percent'] = (meta['valor_atual'] / meta['valor_meta']) * 100
                else:
                    meta['progresso_percent'] = 0.0
                
                # Cria campo para display da barra de progresso (limitado a 100%)
                meta['progresso_percent_display'] = min(meta['progresso_percent'], 100.0)
                
            except (ValueError, TypeError):
                meta['valor_atual'] = 0.0
                meta['valor_meta'] = 0.0
                meta['progresso_percent'] = 0.0
                meta['progresso_percent_display'] = 0.0
    
    # Garante que usuario existe
    if 'usuario' not in contexto_dados or not contexto_dados['usuario']:
        class UsuarioMock:
            nome_completo = "Usuário"
        contexto_dados['usuario'] = UsuarioMock()
    
    return contexto_dados

def debug_contexto(contexto_dados):
    """Função para debug - registra informações do contexto no log."""
    logger.info("=== DEBUG CONTEXTO RELATÓRIO ===")
    logger.info(f"Has data: {contexto_dados.get('has_data', False)}")
    logger.info(f"Mês/Ano: {contexto_dados.get('mes_nome', 'N/A')} {contexto_dados.get('ano', 'N/A')}")
    logger.info(f"Receita: R$ {contexto_dados.get('receita_total', 0):.2f}")
    logger.info(f"Despesa: R$ {contexto_dados.get('despesa_total', 0):.2f}")
    logger.info(f"Saldo: R$ {contexto_dados.get('saldo_mes', 0):.2f}")
    logger.info(f"Taxa poupança: {contexto_dados.get('taxa_poupanca', 0):.1f}%")
    logger.info(f"Categorias: {len(contexto_dados.get('gastos_agrupados', []))}")
    logger.info(f"Metas: {len(contexto_dados.get('metas', []))}")
    logger.info(f"Análise IA: {'Sim' if contexto_dados.get('analise_ia') else 'Não'}")
    logger.info(f"Gráfico: {'Sim' if contexto_dados.get('grafico_pizza_base64') else 'Não'}")
    logger.info("===============================")


# =============================================================================
#  LÓGICA CORE DE GERAÇÃO E ENVIO DE RELATÓRIO PDF
# =============================================================================

async def enviar_relatorio_pdf_usuario(bot, usuario, db, mes_alvo, ano_alvo, periodo_str, context_tg=None):
    """
    Geração e envio do relatório PDF isolada para ser usada por comandos ou jobs.
    """
    user_id = usuario.telegram_id
    try:
        # 1. Desativar temporariamente o sistema de cache
        old_cache_ttl = getattr(services_module, 'CACHE_TTL', None)
        old_cache_max = getattr(services_module, 'CACHE_MAX_SIZE', None)
        try:
            services_module.CACHE_TTL = 0
            services_module.CACHE_MAX_SIZE = 0
        except Exception: pass

        # Limpa cache residual
        try: limpar_cache_usuario(user_id)
        except Exception: pass

        logger.info(f"Gerando relatório para {user_id}, período: {mes_alvo}/{ano_alvo}")
        contexto_dados = gerar_contexto_relatorio(db, user_id, mes_alvo, ano_alvo)
        
        if not contexto_dados:
            logger.warning(f"Contexto vazio para usuário {user_id}")
            return False
        
        contexto_dados = validar_e_completar_contexto(contexto_dados)
        
        # 3.1 Gerar Análise de IA
        try:
            resumo_dados = (
                f"Usuário: {getattr(contexto_dados.get('usuario'), 'nome_completo', 'Usuário')}\n"
                f"Período: {contexto_dados.get('mes_nome')} de {contexto_dados.get('ano')}\n"
                f"Receitas: R$ {contexto_dados.get('receita_total'):.2f}\n"
                f"Despesas: R$ {contexto_dados.get('despesa_total'):.2f}\n"
                f"Saldo: R$ {contexto_dados.get('saldo_mes'):.2f}\n"
                f"Taxa de Poupança: {contexto_dados.get('taxa_poupanca'):.1f}%\n"
            )
            gastos = contexto_dados.get('gastos_agrupados', [])
            if gastos:
                resumo_dados += "\nMaiores Gastos por Categoria:\n"
                for cat, val in gastos[:5]:
                    resumo_dados += f"- {cat}: R$ {val:.2f}\n"
            
            prompt_ia = [
                {"role": "system", "content": "Você é o Alfredo, um assistente financeiro inteligente e direto. Analise os dados e forneça 3 a 4 insights curtos."},
                {"role": "user", "content": f"Dados:\n{resumo_dados}"}
            ]
            analise_resultado = await _smart_ai_completion_async(prompt_ia)
            if analise_resultado:
                if isinstance(analise_resultado, str): contexto_dados["analise_ia"] = analise_resultado
                else: contexto_dados["analise_ia"] = analise_resultado.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Erro IA relatório: {e}")
            contexto_dados["analise_ia"] = "Continue acompanhando seus gastos pelo Alfredo!"

        if not contexto_dados.get("has_data"):
            logger.info(f"Usuário {user_id} sem dados para o período.")
            return False

        # 4. Gráficos
        try:
            grafico_buffer = gerar_grafico_para_relatorio(contexto_dados.get("gastos_por_categoria_dict", {}))
            if grafico_buffer:
                contexto_dados["grafico_pizza_png_bytes"] = grafico_buffer.getvalue()
        except Exception as e: logger.error(f"Erro gráfico pizza: {e}")

        try:
            grafico_evolucao = gerar_grafico_evolucao_mensal(contexto_dados.get("lancamentos_historico", []))
            if grafico_evolucao: contexto_dados["grafico_evolucao_png_bytes"] = grafico_evolucao.getvalue()
        except Exception as e: logger.error(f"Erro gráfico evolução: {e}")

        try:
            from .services import gerar_grafico_perfil_semanal
            financeiros_full = contexto_dados.get('lista_despesas', []) + contexto_dados.get('lista_receitas', [])
            grafico_semanal = gerar_grafico_perfil_semanal(financeiros_full)
            if grafico_semanal: contexto_dados["grafico_semanal_png_bytes"] = grafico_semanal.getvalue()
        except Exception as e: logger.error(f"Erro gráfico semanal: {e}")

        # 5. Render HTML
        contexto_dados['now'] = datetime.now
        template = env.get_template('relatorio_inspiracao.html')
        html_renderizado = template.render(contexto_dados)

        # 6. PDF ReportLab
        data_referencia = datetime(ano_alvo, mes_alvo, 1)
        pdf_context = {
            'periodo_inicio': data_referencia.strftime('01/%m/%Y'),
            'periodo_fim': (data_referencia + relativedelta(day=31)).strftime('%d/%m/%Y'),
            'usuario_nome': usuario.nome_completo or 'Você',
            'periodo_extenso': f"{contexto_dados.get('mes_nome')} de {ano_alvo}",
            'total_receitas': contexto_dados.get('receita_total', 0),
            'total_gastos': contexto_dados.get('despesa_total', 0),
            'saldo_periodo': contexto_dados.get('saldo_mes', 0),
            'taxa_poupanca': contexto_dados.get('taxa_poupanca', 0),
            'score_financeiro': contexto_dados.get('score_financeiro'),
            'gastos_agrupados': contexto_dados.get('gastos_agrupados', []),
            'grafico_pizza_png': contexto_dados.get('grafico_pizza_png_bytes'),
            'grafico_evolucao_png': contexto_dados.get('grafico_evolucao_png_bytes'),
            'grafico_semanal_png': contexto_dados.get('grafico_semanal_png_bytes'),
            'top_gastos': contexto_dados.get('lista_despesas', [])[:10],
            'top_receitas': contexto_dados.get('lista_receitas', [])[:10],
            'analise_ia': contexto_dados.get('analise_ia'),
            'metas': contexto_dados.get('metas', []),
        }
        
        pdf_bytes = generate_financial_pdf(pdf_context)
        if not pdf_bytes: return False

        # Enviar
        pdf_filename = f"relatorio_{ano_alvo}_{mes_alvo}_{user_id}.pdf"
        from telegram import InputFile
        import io
        await bot.send_document(
            chat_id=user_id,
            document=InputFile(io.BytesIO(pdf_bytes), filename=pdf_filename),
            caption=f"📊 <b>Seu Relatório Financeiro</b>\nPeríodo: {periodo_str}\n\nAlfredo cuidando das suas finanças! 🚀",
            parse_mode='HTML'
        )

        if context_tg:
            try: await give_xp_for_action(user_id, "RELATORIO_GERADO", context_tg)
            except: pass
        
        return True

    finally:
        # Restaura cache
        try:
            if old_cache_ttl is not None: services_module.CACHE_TTL = old_cache_ttl
            if old_cache_max is not None: services_module.CACHE_MAX_SIZE = old_cache_max
        except: pass

# =============================================================================
#  HANDLER DO COMANDO /relatorio
# =============================================================================

async def gerar_relatorio_comando(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera e envia um relatório financeiro detalhado em PDF."""
    await touch_user_interaction(update.effective_user.id, context)
    hoje = datetime.now()
    if context.args and context.args[0].lower() in ['passado', 'anterior']:
        data_alvo = hoje - relativedelta(months=1)
        periodo_str = f"do mês passado ({data_alvo.strftime('%B/%Y')})"
    else:
        data_alvo = hoje
        periodo_str = "deste mês"

    await update.message.reply_text(f"Gerando seu relatório {periodo_str}... 🎥")

    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
        ensure_user_plan_state(db, usuario_db, commit=True)
        if not plan_allows_feature(db, usuario_db, "relatorio_pdf").allowed:
            text, keyboard = upgrade_prompt_for_feature("relatorio_pdf")
            await update.message.reply_html(text, reply_markup=keyboard)
            return

        success = await enviar_relatorio_pdf_usuario(
            context.bot, usuario_db, db, data_alvo.month, data_alvo.year, periodo_str, context
        )
        if not success:
            await update.message.reply_text("Não encontrei dados suficientes para gerar o relatório agora.")
    finally:
        db.close()

# Cria o handler para ser importado no bot.py
relatorio_handler = CommandHandler('relatorio', gerar_relatorio_comando)