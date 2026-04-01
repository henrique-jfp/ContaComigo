# --- PAINEL DE NOTIFICAÇÕES (STUB) ---
def painel_notificacoes(update=None, context=None):
    """
    Painel de notificações centralizado. (Stub: retorna mensagem padrão)
    """
    if update and hasattr(update, 'message'):
        return update.message.reply_text(
            "🔔 Painel de notificações em construção! Em breve você verá todos os alertas, lembretes e novidades aqui."
        )
    return "Painel de notificações em construção!"
import json
import logging
import random
import re
import time
import functools
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from typing import List, Tuple, Dict, Any
import os
from .services import preparar_contexto_financeiro_completo
import google.generativeai as genai
from sqlalchemy.orm import Session, joinedload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler,
    MessageHandler, filters
)

# --- IMPORTS DO PROJETO (precisa ser antes de configurar genai) ---
import config

# Configurar Gemini API (CRÍTICO - deve ser feito logo após importar config)
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\"")) if config.GEMINI_API_KEY else None
    logging.info("✅ Gemini API configurada em handlers.py")
else:
    logging.error("❌ GEMINI_API_KEY não encontrada - /gerente não funcionará!")

# Importar analytics

# Importa analytics e decorator centralizado
try:
    from analytics.bot_analytics import BotAnalytics
    analytics = BotAnalytics()
    ANALYTICS_ENABLED = True
except Exception as e:
    logging.warning(f"Analytics desabilitado: {e}")
    ANALYTICS_ENABLED = False

from .analytics_utils import track_analytics

# --- IMPORTS RESTANTES DO PROJETO ---

from database.database import get_db, get_or_create_user, buscar_lancamentos_usuario
from models import Categoria, Lancamento, Subcategoria, Usuario, ItemLancamento, Conta
from .prompts import PROMPT_GERENTE_VDM, PROMPT_INSIGHT_FINAL
from .states import (
    AWAIT_GERENTE_QUESTION, ASK_OBJETIVO_DESCRICAO, ASK_OBJETIVO_VALOR, ASK_OBJETIVO_PRAZO,
    AWAIT_EMAIL_NOTIFICACAO
)

# Importando explicitamente as funções de 'services'
from .services import (
    analisar_comportamento_financeiro,
    buscar_lancamentos_com_relacionamentos,
    detectar_intencao_e_topico,
    obter_dados_externos,
    preparar_contexto_json
)

# ============================================================================
# 🛡️ SISTEMA DE RATE LIMITING (Anti-Spam)
# ============================================================================

# Armazena timestamp da última requisição por usuário
_user_last_request_time = {}

# Configurações de rate limiting
RATE_LIMIT_SECONDS = 3  # Cooldown entre requisições
RATE_LIMIT_WARNING_EMOJI = "⏱️"

def check_rate_limit(user_id: int) -> Tuple[bool, float]:
    """
    Verifica se o usuário está respeitando o rate limit.
    
    Args:
        user_id: ID do usuário no Telegram
        
    Returns:
        Tupla (pode_prosseguir, tempo_restante)
        - pode_prosseguir: True se pode fazer a requisição
        - tempo_restante: Segundos que ainda faltam para poder fazer nova requisição
    """
    agora = time.time()
    ultima_requisicao = _user_last_request_time.get(user_id, 0)
    tempo_decorrido = agora - ultima_requisicao
    
    if tempo_decorrido < RATE_LIMIT_SECONDS:
        tempo_restante = RATE_LIMIT_SECONDS - tempo_decorrido
        return False, tempo_restante
    
    # Atualiza timestamp da última requisição
    _user_last_request_time[user_id] = agora
    return True, 0.0

def limpar_rate_limit_antigo():
    """
    Remove entradas antigas do rate limit (> 5 minutos).
    Chamado periodicamente para evitar memory leak.
    """
    agora = time.time()
    usuarios_para_remover = [
        user_id for user_id, timestamp in _user_last_request_time.items()
        if agora - timestamp > 300  # 5 minutos
    ]
    for user_id in usuarios_para_remover:
        del _user_last_request_time[user_id]
    
    if usuarios_para_remover:
        logging.info(f"🧹 Rate limit: Removidas {len(usuarios_para_remover)} entradas antigas")

# ============================================================================

# ============================================================================
# 🚀 SISTEMA DE ATALHOS INTELIGENTES
# ============================================================================

# Mapeamento de atalhos para perguntas completas
ATALHOS_INTELIGENTES = {
    # Saldos e valores
    'saldo': 'Qual é meu saldo total atual?',
    'saldo total': 'Qual é meu saldo total atual?',
    'quanto tenho': 'Qual é meu saldo total atual?',
    'meu saldo': 'Qual é meu saldo total atual?',
    
    # Gastos
    'gastos': 'Quanto gastei este mês?',
    'gastos mes': 'Quanto gastei este mês?',
    'gastos mês': 'Quanto gastei este mês?',
    'despesas': 'Quanto gastei este mês?',
    'despesas mes': 'Quanto gastei este mês?',
    'gastei': 'Quanto gastei este mês?',
    
    # Receitas
    'receitas': 'Quanto recebi este mês?',
    'receitas mes': 'Quanto recebi este mês?',
    'receitas mês': 'Quanto recebi este mês?',
    'entradas': 'Quanto recebi este mês?',
    'recebi': 'Quanto recebi este mês?',
    'ganhei': 'Quanto recebi este mês?',
    
    # Lançamentos
    'lancamentos': 'Mostre meus últimos 5 lançamentos',
    'lançamentos': 'Mostre meus últimos 5 lançamentos',
    'ultimos lancamentos': 'Mostre meus últimos 10 lançamentos',
    'últimos lançamentos': 'Mostre meus últimos 10 lançamentos',
    'extrato': 'Mostre meus últimos 10 lançamentos',
    
    # Resumos
    'resumo': 'Como está minha situação financeira este mês?',
    'situacao': 'Como está minha situação financeira este mês?',
    'situação': 'Como está minha situação financeira este mês?',
    'panorama': 'Como está minha situação financeira este mês?',
    
    # Comparações rápidas
    'comparar': 'Compare meus gastos deste mês com o mês passado',
    'comparacao': 'Compare meus gastos deste mês com o mês passado',
    'comparação': 'Compare meus gastos deste mês com o mês passado',
    
    # Metas
    'metas': 'Como estão minhas metas?',
    'objetivos': 'Como estão minhas metas?',
    'economia': 'Quanto consegui economizar este mês?',
}

def processar_atalho(texto: str) -> Tuple[bool, str]:
    """
    Verifica se o texto é um atalho e retorna a pergunta expandida.
    
    Args:
        texto: Texto do usuário
        
    Returns:
        Tupla (é_atalho, pergunta_expandida)
    """
    texto_limpo = texto.lower().strip()
    
    # Busca exata primeiro
    if texto_limpo in ATALHOS_INTELIGENTES:
        pergunta_expandida = ATALHOS_INTELIGENTES[texto_limpo]
        logger.info(f"🚀 Atalho detectado: '{texto_limpo}' → '{pergunta_expandida}'")
        return True, pergunta_expandida
    
    # Busca parcial (começa com)
    for atalho, pergunta in ATALHOS_INTELIGENTES.items():
        if texto_limpo.startswith(atalho):
            logger.info(f"🚀 Atalho parcial detectado: '{texto_limpo}' → '{pergunta}'")
            return True, pergunta
    
    return False, texto

# ============================================================================

from . import services


logger = logging.getLogger(__name__)

# --- CONSTANTES PARA DETECÇÃO DE INTENÇÕES ---
PALAVRAS_LISTA = {
    'lançamentos', 'lancamentos', 'lançamento', 'lancamento', 'transações', 'transacoes', 
    'transacao', 'transação', 'gastos', 'receitas', 'entradas', 'saidas', 'saídas',
    'despesas', 'historico', 'histórico', 'movimentação', 'movimentacao', 'extrato'
}

PALAVRAS_RESUMO = {
    'resumo', 'relatorio', 'relatório', 'balanço', 'balanco', 'situacao', 'situação',
    'status', 'como estou', 'como está', 'como tá', 'como ta', 'panorama'
}

PERGUNTAS_ESPECIFICAS = {
    'quanto': ['gastei', 'gasto', 'recebi', 'tenho', 'sobrou', 'economizei'],
    'onde': ['gastei', 'comprei', 'paguei'],
    'quando': ['foi', 'comprei', 'paguei', 'gastei']
}

# --- PROMPT PARA ANÁLISE DE IMPACTO ---
PROMPT_ANALISE_IMPACTO = """
**TAREFA:** Você é o **Maestro Financeiro**, um assistente de finanças. O usuário pediu uma informação de mercado e agora quer entender o impacto dela.
Seja conciso e direto. Forneça uma análise útil e sugestões práticas.

**NOME DO USUÁRIO:** {user_name}
**PERFIL DE INVESTIDOR:** {perfil_investidor}
**INFORMAÇÃO DE MERCADO:**
{informacao_externa}

**DADOS FINANCEIROS DO USUÁRIO (JSON):**
{contexto_json}

**SUA RESPOSTA:**
Gere uma análise em 2 seções: "Impacto para Seu Perfil" e "Recomendações", usando o perfil do usuário para personalizar a resposta. Use formatação HTML para Telegram (`<b>`, `<i>`, `<code>`).
**NUNCA use a tag <br>. Use quebras de linha normais.**
"""

# --- CLASSES PARA CONTEXTO MELHORADO ---
class ContextoConversa:
    def __init__(self):
        self.historico: List[Dict[str, str]] = []
        self.topicos_recorrentes: Dict[str, int] = {}
        self.ultima_pergunta_tipo: str = ""
        self.dados_cache: Dict[str, Any] = {}
    
    def adicionar_interacao(self, pergunta: str, resposta: str, tipo: str = "geral"):
        self.historico.append({
            'pergunta': pergunta,
            'resposta': resposta[:300],  # Limita o tamanho
            'tipo': tipo,
            'timestamp': datetime.now().isoformat()
        })
        
        if len(self.historico) > 10:
            self.historico = self.historico[-10:]
        
        palavras_chave = self._extrair_palavras_chave(pergunta)
        for palavra in palavras_chave:
            self.topicos_recorrentes[palavra] = self.topicos_recorrentes.get(palavra, 0) + 1
        
        self.ultima_pergunta_tipo = tipo
    
    def _extrair_palavras_chave(self, texto: str) -> List[str]:
        palavras = re.findall(r'\b\w+\b', texto.lower())
        palavras_relevantes = ['uber', 'ifood', 'supermercado', 'lazer', 'restaurante', 
                              'transporte', 'alimentacao', 'alimentação', 'conta', 'salario', 'salário']
        return [p for p in palavras if p in palavras_relevantes or len(p) > 5]
    
    def get_contexto_formatado(self) -> str:
        if not self.historico:
            return ""
        
        contexto = []
        for item in self.historico[-5:]:
            contexto.append(f"Usuário: {item['pergunta']}")
            contexto.append(f"Maestro: {item['resposta']}")
        
        return "\n".join(contexto)
    
    def tem_topico_recorrente(self, topico: str) -> bool:
        return self.topicos_recorrentes.get(topico.lower(), 0) >= 2

class AnalisadorIntencao:
    @staticmethod
    def detectar_tipo_pergunta(pergunta: str) -> str:
        pergunta_lower = pergunta.lower()

        if "maior despesa" in pergunta_lower or "maior gasto" in pergunta_lower:
            return "maior_despesa"
        
        if any(palavra in pergunta_lower for palavra in ['dolar', 'dólar', 'bitcoin', 'btc', 'selic', 'cotacao', 'cotação', 'euro', 'eur']):
            return "dados_externos"
        
        if any(palavra in pergunta_lower for palavra in PALAVRAS_LISTA):
            return "lista_lancamentos"
        
        if any(palavra in pergunta_lower for palavra in PALAVRAS_RESUMO):
            return "resumo_completo"
        
        for interrogativo, verbos in PERGUNTAS_ESPECIFICAS.items():
            if interrogativo in pergunta_lower and any(verbo in pergunta_lower for verbo in verbos):
                return "pergunta_especifica"
        
        if any(palavra in pergunta_lower for palavra in ['oi', 'olá', 'bom dia', 'boa tarde', 'e ai', 'e aí', 'tudo bem', 'blz']):
            return "conversacional"
        
        
        return "analise_geral"
    
    @staticmethod
    def extrair_limite_lista(pergunta: str) -> int:
        match = re.search(r'\b(\d+)\b', pergunta)
        if match:
            return min(int(match.group(1)), 50)
        
        if any(palavra in pergunta.lower() for palavra in ['último', 'ultimo', 'última', 'ultima']):
            return 1
        
        return 10

# --- FUNÇÕES UTILITÁRIAS MELHORADAS ---

async def enviar_texto_em_blocos(bot, chat_id, texto: str, reply_markup=None):
    """
    Envia texto em blocos, com tratamento robusto de HTML malformado
    """
    # Limpeza básica
    texto_limpo = texto.strip().replace('<br>', '\n').replace('<br/>', '\n')
    
    # Remove HTML malformado antes de enviar
    texto_limpo = _limpar_resposta_ia(texto_limpo)
    
    if len(texto_limpo) <= 4096:
        # Tenta enviar com HTML primeiro
        try:
            await bot.send_message(
                chat_id=chat_id, 
                text=texto_limpo, 
                parse_mode="HTML", 
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            return
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem HTML: {e}")
            # Fallback: remove todas as tags HTML e envia como texto simples
            try:
                texto_sem_html = re.sub('<[^<]+?>', '', texto_limpo)
                await bot.send_message(
                    chat_id=chat_id, 
                    text=texto_sem_html, 
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
                return
            except Exception as e2:
                logger.error(f"Erro ao enviar mensagem sem HTML: {e2}")
                return
    
    # Para mensagens longas, divide em partes
    partes = []
    while len(texto_limpo) > 0:
        if len(texto_limpo) <= 4096:
            partes.append(texto_limpo)
            break
        
        corte = texto_limpo[:4096].rfind("\n\n")
        if corte == -1: corte = texto_limpo[:4096].rfind("\n")
        if corte == -1: corte = 4096
        
        partes.append(texto_limpo[:corte])
        texto_limpo = texto_limpo[corte:].strip()
    
    for i, parte in enumerate(partes):
        is_last_part = (i == len(partes) - 1)
        try:
            await bot.send_message(
                chat_id=chat_id, 
                text=parte, 
                parse_mode="HTML", 
                reply_markup=reply_markup if is_last_part else None,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Erro ao enviar parte {i}: {e}")
            # Fallback para parte sem HTML
            try:
                parte_sem_html = re.sub('<[^<]+?>', '', parte)
                await bot.send_message(
                    chat_id=chat_id, 
                    text=parte_sem_html,
                    reply_markup=reply_markup if is_last_part else None,
                    disable_web_page_preview=True
                )
            except Exception as e2:
                logger.error(f"Erro fatal ao enviar parte {i}: {e2}")
                # Em último caso, envia mensagem de erro
                if i == 0:  # Só envia erro na primeira tentativa para não spammar
                    await bot.send_message(
                        chat_id=chat_id,
                        text="Ops! Houve um problema na formatação da resposta. Pode tentar novamente?",
                        reply_markup=reply_markup if is_last_part else None
                    )

def parse_action_buttons(text: str) -> tuple[str, InlineKeyboardMarkup | None]:
    match = re.search(r'\[ACTION_BUTTONS:\s*(.*?)\]', text, re.DOTALL | re.IGNORECASE)
    if not match:
        return text, None
    
    clean_text = text[:match.start()].strip()
    button_data_str = match.group(1)
    
    try:
        button_pairs = [pair.strip() for pair in button_data_str.split(';') if pair.strip()]
        keyboard = []
        row = []
        
        for pair in button_pairs:
            parts = pair.split('|')
            if len(parts) == 2:
                button_text, callback_data = parts[0].strip(), parts[1].strip()
                if len(button_text) <= 40:
                    row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
                    if len(row) == 2:
                        keyboard.append(row)
                        row = []
        if row:
            keyboard.append(row)
        
        if keyboard:
            return clean_text, InlineKeyboardMarkup(keyboard)
    
    except Exception as e:
        logger.error(f"Erro ao parsear botões: {e}")
    
    return clean_text, None

def formatar_lancamento_detalhado(lanc: Lancamento) -> str:
    """
    Formata um lançamento no modelo de card limpo e profissional - VERSÃO 2.0
    """
    # Emojis por tipo
    tipo_emoji = "�" if lanc.tipo == 'Entrada' else "�"
    tipo_cor = "🟢" if lanc.tipo == 'Entrada' else "🔴"
    
    # Formatação da data
    data_formatada = lanc.data_transacao.strftime('%d/%m/%Y')
    hora_formatada = lanc.data_transacao.strftime('%H:%M')
    
    # Descrição limpa (máximo 50 caracteres)
    descricao = lanc.descricao or 'Transação'
    if len(descricao) > 50:
        descricao = descricao[:47] + "..."
    
    # Card limpo e profissional
    card = (
        f"{tipo_emoji} <b>{descricao}</b>\n\n"
        f"<b>💰 Valor:</b> <code>R$ {lanc.valor:.2f}</code>\n"
        f"<b>📅 Data:</b> {data_formatada} às {hora_formatada}\n"
        f"<b>📂 Categoria:</b> {lanc.categoria.nome if lanc.categoria else 'Sem categoria'}\n"
        f"<b>💳 Pagamento:</b> {lanc.forma_pagamento or 'Não informado'}\n"
        f"<b>🏷️ Tipo:</b> {tipo_cor} {lanc.tipo}"
    )
    return card

async def handle_lista_lancamentos(chat_id: int, context: ContextTypes.DEFAULT_TYPE, parametros: dict):
    """
    Busca e exibe lançamentos com base nos parâmetros da IA, incluindo data.
    """
    logger.info(f"Executando handle_lista_lancamentos com parâmetros: {parametros}")
    db = next(get_db())
    try:
        # Converte datas de string para objeto datetime, se existirem
        if 'data_inicio' in parametros:
            parametros['data_inicio'] = datetime.strptime(parametros['data_inicio'], '%Y-%m-%d')
        if 'data_fim' in parametros:
            parametros['data_fim'] = datetime.strptime(parametros['data_fim'], '%Y-%m-%d')

        lancamentos = buscar_lancamentos_usuario(telegram_user_id=chat_id, **parametros)
        
        if not lancamentos:
            await context.bot.send_message(chat_id, "🔍 Nenhum lançamento encontrado com esses critérios. Tente outros filtros!")
            return

        # Cabeçalho profissional
        total_valor = sum(float(l.valor) for l in lancamentos)
        sinal = "+" if any(l.tipo == 'Entrada' for l in lancamentos) and len([l for l in lancamentos if l.tipo == 'Entrada']) == len(lancamentos) else ""
        
        cabecalho = (
            f"📋 <b>Seus Lançamentos</b>\n\n"
            f"<b>📊 Resumo:</b>\n"
            f"• <b>Total encontrado:</b> {len(lancamentos)} lançamento(s)\n"
            f"• <b>Valor total:</b> <code>{sinal}R$ {total_valor:.2f}</code>\n\n"
            f"<b>🗂️ Detalhes:</b>\n"
        )
        
        cards_formatados = [formatar_lancamento_detalhado(lanc) for lanc in lancamentos]
        resposta_final = cabecalho + "\n━━━━━━━━━━━━━━━━━━\n\n".join(cards_formatados)

        await enviar_texto_em_blocos(context.bot, chat_id, resposta_final)
    finally:
        db.close()


def criar_teclado_colunas(botoes: list, colunas: int):
    if not botoes: return []
    return [botoes[i:i + colunas] for i in range(0, len(botoes), colunas)]

def obter_contexto_usuario(context: ContextTypes.DEFAULT_TYPE) -> ContextoConversa:
    if 'contexto_conversa' not in context.user_data:
        context.user_data['contexto_conversa'] = ContextoConversa()
    return context.user_data['contexto_conversa']

# --- HANDLER DE START / HELP (ONBOARDING) ---
HELP_TEXTS = {
    "main": (
        "Olá, <b>{user_name}</b>! 👋\n\n"
        "Bem-vindo ao <b>Maestro Financeiro</b>, seu assistente pessoal para dominar suas finanças. "
        "Sou um bot completo, com inteligência artificial, gráficos, relatórios e muito mais.\n\n"
        "Navegue pelas seções abaixo para descobrir tudo que posso fazer por você:"
    ),
    "lancamentos": (
        "<b>📝 Lançamentos e Registros</b>\n\n"
        "A forma mais fácil de manter suas finanças em dia.\n\n"
        "📸  <b>Leitura Automática (OCR)</b>\n"
        "   • Dentro do comando <code>/lancamento</code>, envie uma <b>foto ou PDF</b> de um cupom fiscal e eu extraio os dados para você.\n\n"
        "⌨️  <code>/lancamento</code>\n"
        "   • Use para registrar uma <b>Entrada</b> ou <b>Saída</b> manualmente através de um guia passo a passo.\n\n"
        "✏️  <code>/editar</code>\n"
        "   • Use para <b>editar ou apagar</b> um lançamento recente ou buscá-lo pelo nome."
    ),
    "analise": (
        "<b>🧠 Análise e Inteligência</b>\n\n"
        "Transforme seus dados em decisões inteligentes.\n\n"
        "💬  <code>/gerente</code>\n"
        "   • Converse comigo em linguagem natural! Sou uma IA avançada que entende suas perguntas sobre finanças, tem memória e te ajuda com insights práticos.\n\n"
        "   <b>📝 Exemplos de perguntas:</b>\n"
        "   • <i>\"Qual meu saldo total?\"</i>\n"
        "   • <i>\"Quanto gastei com alimentação este mês?\"</i>\n"
        "   • <i>\"Comparar gastos de outubro e novembro\"</i>\n"
        "   • <i>\"Mostre meus últimos 5 lançamentos\"</i>\n"
        "   • <i>\"Como está minha wishlist de viagem?\"</i>\n"
        "   • <i>\"Cotação do dólar hoje\"</i>\n"
        "   • <i>\"Quanto gastei com lazer na última semana?\"</i>\n\n"
        "   <b>💡 Dicas de uso:</b>\n"
        "   • Seja específico e natural\n"
        "   • Posso comparar períodos, categorias e contas\n"
        "   • Aguarde 3 segundos entre perguntas (evita spam)\n"
        "   • Se eu não entender, reformule de forma mais simples\n\n"
        "📈  <code>/grafico</code>\n"
        "   • Gere gráficos visuais e interativos de despesas, fluxo de caixa e projeções.\n\n"
        "📄  <code>/relatorio</code>\n"
        "   • Gere um <b>relatório profissional em PDF</b> com o resumo completo do seu mês."
    ),
    "planejamento": (
        "<b>🎯 Wishlist e Agendamentos</b>\n\n"
        "Planeje seu futuro e automatize sua vida financeira.\n\n"
        "�  <code>/wishlist</code>\n"
        "   • Crie sua lista de desejos financeiros! Eu analiso sua situação atual, calculo viabilidade, sugiro cortes de gastos e monto até 3 planos de ação personalizados para você conquistar seu objetivo.\n\n"
        "�  <code>/minhas_wishlists</code>\n"
        "   • Veja todas as suas wishlists ativas com análise de viabilidade, progresso e planos de ação atualizados.\n\n"
        "🗓️  <code>/agendar</code>\n"
        "   • Automatize suas contas! Agende despesas e receitas recorrentes (salário, aluguel) ou parcelamentos. Eu te lembrarei e lançarei tudo automaticamente.\n\n"
        "💡  <b>Diferenciais da Wishlist:</b>\n"
        "   • 🧠 Análise de viabilidade com IA\n"
        "   • ✂️ Sugestões inteligentes de economia\n"
        "   • 📊 Até 3 planos de ação (conservador, moderado, agressivo)\n"
        "   • 🎯 Acompanhamento de progresso automático\n"
        "   • 💰 Cálculo de impacto real nas suas finanças"
    ),
    "config": (
        "<b>⚙️ Configurações e Ferramentas</b>\n\n"
        "Deixe o bot com a sua cara e gerencie suas preferências.\n\n"
        "👤  <code>/configurar</code>\n"
        "   • Gerencie suas <b>contas</b>, <b>cartões</b>, defina seu <b>perfil de investidor</b> para receber dicas personalizadas e altere o <b>horário dos lembretes</b>.\n\n"
        "🧯  <code>/categorizar</code>\n"
        "   • <b>EXTINTOR DE INCÊNDIO!</b> Categoriza automaticamente TODOS os lançamentos sem categoria usando IA. Perfeito para corrigir falhas de categorização do OCR ou lançamento manual.\n\n"
        "🚨  <code>/alerta [valor]</code>\n"
        "   • Defina um limite de gastos mensal (ex: <code>/alerta 1500</code>). Eu te avisarei se você ultrapassar esse valor.\n\n"
        "💬  <code>/contato</code>\n" 
        "   • Fale com o desenvolvedor! Envie <b>sugestões</b>, <b>dúvidas</b> ou me pague um <b>café via PIX</b> para apoiar o projeto.\n\n"
        "🗑️  <code>/apagartudo</code>\n"
        "   • <b>Exclui permanentemente todos os seus dados</b> do bot. Use com extrema cautela!\n\n"
        "↩️  <code>/cancelar</code>\n"
        "   • Use a qualquer momento para interromper uma operação em andamento."
    ),
    "gamificacao": (
        "<b>🎮 Sistema de Gamificação ULTRA</b>\n\n"
        "Transforme suas finanças em uma experiência VICIANTE!\n\n"
        "🏆  <code>/perfil</code>\n"
        "   • Veja seu <b>perfil gamer completo</b> com barras de progresso animadas, títulos épicos, conquistas desbloqueadas e estatísticas personalizadas.\n\n"
        "📊  <code>/ranking</code>\n"
        "   • Consulte o <b>Hall da Fama Global</b> e veja sua posição no ranking mundial de XP.\n\n"
        "⭐  <b>Como ganhar XP:</b>\n"
        "   • 📝 Registrar transação: +10 XP\n"
        "   • 💬 Usar IA do Gerente: +5 XP\n"
        "   • 🎯 Atingir meta: +25 XP\n"
        "   • 📊 Gerar gráfico: +8 XP\n"
        "   • 📄 Gerar relatório: +15 XP\n"
        "   • 🔥 Streak diário: +2 XP extra\n\n"
        "🎯  <b>Funcionalidades exclusivas:</b>\n"
        "   • 🏅 Sistema de conquistas personalizadas\n"
        "   • 🎯 Desafios diários com recompensas\n"
        "   • 💎 Títulos épicos baseados no desempenho\n"
        "   • 🔥 Multiplicadores de streak (até +200% XP!)\n"
        "   • 📊 Estatísticas ultra detalhadas\n"
        "   • � Loja de XP (em desenvolvimento)\n\n"
        "💪  <b>Dica Pro:</b> Mantenha seu streak diário para acelerar sua evolução!"
    ),
    "investimentos": (
        "<b>📈 Investimentos e Patrimônio</b>\n\n"
        "Acompanhe seus investimentos e veja seu patrimônio crescer!\n\n"
        "💰  <code>/investimentos</code>\n"
        "   • Lista completa de todos os seus investimentos com valores atualizados e rentabilidade.\n\n"
        "📊  <code>/dashboard_investimentos</code>\n"
        "   • Dashboard visual com rentabilidade total, performance mensal e distribuição por tipo (CDB, LCI, Ações, etc.)\n\n"
        "💎  <code>/patrimonio</code>\n"
        "   • Visão consolidada do seu patrimônio total (contas bancárias + investimentos) com evolução histórica dos últimos 6 meses.\n\n"
        "✨  <b>Funcionalidades:</b>\n"
        # "   • 📈 Acompanhamento automático bancário\n"
        "   • 💹 Cálculo de rentabilidade mensal\n"
        "   • 📉 Comparação com CDI e IPCA\n"
        "   • 🎯 Sistema de metas de investimento\n"
        "   • 📊 Histórico completo com snapshots mensais\n"
        "   • 🏆 Ranking dos seus melhores investimentos\n\n"
        "💡  <b>Tipos suportados:</b>\n"
        "   • 💎 CDB, LCI, LCA\n"
        "   • 🏛 Tesouro Direto\n"
        "   • 📊 Ações e Fundos\n"
        "   • 🐷 Poupança\n"
        "   • 🪙 Cofrinhos digitais\n\n"
        # "🔥  <b>Dica Pro:</b> Conecte seu banco com <code>/conectar_banco</code> para importar investimentos automaticamente!"
    )
}

def get_help_keyboard(current_section: str = "main") -> InlineKeyboardMarkup:
    """
    Gera o teclado de navegação interativo para o menu de ajuda.
    Os botões são dispostos de forma inteligente para melhor visualização.
    """
    keyboard = [
        [
            InlineKeyboardButton("📝 Lançamentos", callback_data="help_lancamentos"),
            InlineKeyboardButton("🧠 Análise", callback_data="help_analise"),
        ],
        [
            InlineKeyboardButton("🎯 Planejamento", callback_data="help_planejamento"),
            InlineKeyboardButton("🎮 Gamificação", callback_data="help_gamificacao"),
        ],
        [
            InlineKeyboardButton("📈 Investimentos", callback_data="help_investimentos"),
        ],
        [
            InlineKeyboardButton("⚙️ Ferramentas", callback_data="help_config"),
        ]
    ]
    
    # Adiciona o botão de "Voltar" apenas se não estivermos no menu principal
    if current_section != "main":
        keyboard.append([InlineKeyboardButton("↩️ Voltar ao Menu Principal", callback_data="help_main")])
    
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Envia a mensagem de ajuda principal e interativa ao receber o comando /help.
    Busca o nome do usuário para uma saudação personalizada.
    """
    user = update.effective_user
    db = next(get_db())
    try:
        # Busca o nome do usuário no banco para personalizar a mensagem
        usuario_db = db.query(Usuario).filter(Usuario.telegram_id == user.id).first()
        # Se não encontrar no DB, usa o nome do Telegram como fallback
        user_name = usuario_db.nome_completo.split(' ')[0] if usuario_db and usuario_db.nome_completo else user.first_name
        
        text = HELP_TEXTS["main"].format(user_name=user_name)
        keyboard = get_help_keyboard("main")
        
        await update.message.reply_html(text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Erro no help_command para o usuário {user.id}: {e}", exc_info=True)
        # Mensagem de fallback caso ocorra um erro
        await update.message.reply_text("Olá! Sou seu Maestro Financeiro. Use os botões para explorar minhas funções.")
    finally:
        db.close()

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa os cliques nos botões do menu de ajuda, editando a mensagem
    para mostrar a seção correspondente.
    """
    query = update.callback_query
    await query.answer() # Responde ao clique para o Telegram saber que foi processado

    try:
        # Extrai a seção do callback_data (ex: "help_analise" -> "analise")
        section = query.data.split('_')[1]

        if section in HELP_TEXTS:
            text = HELP_TEXTS[section]
            
            # Se a seção for a principal, personaliza com o nome do usuário novamente
            if section == "main":
                user = query.from_user
                db = next(get_db())
                try:
                    usuario_db = db.query(Usuario).filter(Usuario.telegram_id == user.id).first()
                    user_name = usuario_db.nome_completo.split(' ')[0] if usuario_db and usuario_db.nome_completo else user.first_name
                    text = text.format(user_name=user_name)
                finally:
                    db.close()

            keyboard = get_help_keyboard(section)
            
            # Edita a mensagem original com o novo texto e teclado
            await query.edit_message_text(text, parse_mode='HTML', reply_markup=keyboard)
            
    except (IndexError, KeyError) as e:
        logger.error(f"Erro no help_callback: Seção não encontrada. query.data: {query.data}. Erro: {e}")
        await query.answer("Erro: Seção de ajuda não encontrada.", show_alert=True)
    except Exception as e:
        logger.error(f"Erro inesperado no help_callback: {e}", exc_info=True)
        await query.answer("Ocorreu um erro ao carregar a ajuda. Tente novamente.", show_alert=True)

# --- COMANDO /start REMOVIDO - AGORA ESTÁ NO ONBOARDING_HANDLER.PY ---

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message or (update.callback_query and update.callback_query.message)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Operação cancelada. ✅")
    else:
        await message.reply_text("Operação cancelada. ✅")
    context.user_data.clear()
    return ConversationHandler.END

# --- HANDLER DE GERENTE FINANCEIRO (IA) - VERSÃO MELHORADA ---

@track_analytics("gerente")
async def start_gerente(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db = next(get_db())
    try:
        user = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
        user_name = user.nome_completo.split(' ')[0] if user.nome_completo else "você"
        contexto = obter_contexto_usuario(context)
        
        if contexto.historico:
            mensagem = f"Oi de novo, {user_name}! 😊 No que posso te ajudar hoje?"
        else:
            # Saudação épica e profissional
            mensagem = f"""
🎩 <b>Olá, {user_name}!</b>

Sou seu <b>Maestro Financeiro</b> - um analista sênior especializado em transformar seus dados em decisões inteligentes. 

<b>💡 O que posso fazer por você:</b>
• Analisar padrões nos seus gastos
• Calcular seu score de saúde financeira
• Comparar períodos e detectar tendências
• Sugerir estratégias personalizadas
• Projetar cenários futuros

<b>🎯 Exemplos do que você pode perguntar:</b>
<i>"Qual meu score de saúde financeira?"</i>
<i>"Compare meus gastos de abril com março"</i>
<i>"Onde posso economizar este mês?"</i>
<i>"Como está minha maior meta?"</i>

Estou aqui para ser muito mais que um consultor - sou seu parceiro estratégico rumo à prosperidade! 

<b>Por onde começamos?</b> 🚀
"""
                        
        await update.message.reply_html(mensagem)
        return AWAIT_GERENTE_QUESTION
    finally:
        db.close()

async def handle_natural_language(update: Update, context: ContextTypes.DEFAULT_TYPE, custom_question: str = None) -> int:
    """
    Handler principal para o /gerente (V4).
    1. Despacha para cotações externas.
    2. Envia para a IA.
    3. Executa funções com base na resposta da IA (JSON) ou envia a análise de texto.
    """
    # --- Correção do Bug de Botão (AttributeError) ---
    is_callback = update.callback_query is not None
    if is_callback:
        effective_message = update.callback_query.message
        user_question = custom_question or ""
        effective_user = update.callback_query.from_user
    else:
        effective_message = update.message
        user_question = effective_message.text
        effective_user = update.effective_user

    chat_id = effective_message.chat_id
    user_id = effective_user.id
    
    # --- � ATALHOS INTELIGENTES: Verificar se é atalho ---
    eh_atalho, pergunta_processada = processar_atalho(user_question)
    if eh_atalho:
        # Mostra feedback visual ao usuário
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"💡 <i>Interpretei como:</i> \"{pergunta_processada}\"",
            parse_mode='HTML'
        )
        user_question = pergunta_processada
    
    # --- �🛡️ RATE LIMITING: Verificar cooldown ---
    pode_prosseguir, tempo_restante = check_rate_limit(user_id)
    if not pode_prosseguir:
        mensagem_rate_limit = (
            f"{RATE_LIMIT_WARNING_EMOJI} <b>Calma aí!</b>\n\n"
            f"Você está fazendo perguntas muito rápido. "
            f"Aguarde <b>{int(tempo_restante) + 1} segundos</b> e tente novamente.\n\n"
            f"<i>Isso ajuda a manter o sistema rápido para todos! 🚀</i>"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensagem_rate_limit,
            parse_mode='HTML'
        )
        logger.warning(f"⏱️ Rate limit ativado para user {user_id} (faltam {tempo_restante:.1f}s)")
        return AWAIT_GERENTE_QUESTION
    
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')

    # --- Despachante: Verifica primeiro se é uma cotação ---
    flag_dado_externo, topico_dado_externo = detectar_intencao_e_topico(user_question)
    if flag_dado_externo:
        logger.info(f"Intenção de dado externo detectada: {topico_dado_externo}")
        dados = await obter_dados_externos(flag_dado_externo)
        await enviar_texto_em_blocos(context.bot, chat_id, dados.get("texto_html", "Não encontrei a informação."))
        return AWAIT_GERENTE_QUESTION

    # --- Se não for cotação, continua com a IA financeira ---
    db = next(get_db())
    contexto_conversa = obter_contexto_usuario(context)
    
    try:
        usuario_db = get_or_create_user(db, chat_id, effective_user.full_name)
        
        contexto_financeiro_str = await preparar_contexto_financeiro_completo(db, usuario_db)
        historico_conversa_str = contexto_conversa.get_contexto_formatado()

        # --- NOVO: VERIFICAR CACHE DE RESPOSTA DA IA ---
        from .services import _gerar_chave_resposta_ia, _obter_resposta_ia_cache, _salvar_resposta_ia_cache, _gerar_hash_dados_financeiros
        
        hash_dados = _gerar_hash_dados_financeiros(contexto_financeiro_str)
        chave_cache_ia = _gerar_chave_resposta_ia(usuario_db.id, user_question, hash_dados)
        
        resposta_cache = _obter_resposta_ia_cache(chave_cache_ia)
        if resposta_cache:
            logger.info(f"✨ Resposta da IA obtida do cache para usuário {usuario_db.id}")
            resposta_ia = resposta_cache
        else:
            # --- 🔄 INDICADOR DE PROGRESSO: Envia mensagem inicial ---
            mensagem_progresso = await context.bot.send_message(
                chat_id=chat_id,
                text="🔍 <b>Analisando seus dados financeiros...</b>\n<i>Isso pode levar alguns segundos.</i>",
                parse_mode='HTML'
            )
            
            # Gera nova resposta
            prompt_final = PROMPT_GERENTE_VDM.format(
                user_name=usuario_db.nome_completo.split(' ')[0] if usuario_db.nome_completo else "você",
                pergunta_usuario=user_question,
                contexto_financeiro_completo=contexto_financeiro_str,
                contexto_conversa=historico_conversa_str
            )
            
            # Tentar com o modelo configurado, se falhar usar fallback
            try:
                # Re-configura a API key logo antes da chamada para ter 100% de certeza que não se perdeu e limpando aspas
                import os
                raw_key = os.getenv("GEMINI_API_KEY", "")
                genai.configure(api_key=raw_key.strip().strip('"\''))
                model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
                response = await model.generate_content_async(prompt_final)
                resposta_ia = _limpar_resposta_ia(response.text)
            except Exception as model_error:
                logger.error(f"⚠️ Erro com modelo '{config.GEMINI_MODEL_NAME}': {model_error}")
                logger.info("🔄 Tentando fallback para 'gemini-flash-latest'...")
                
                # Atualizar mensagem de progresso
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=mensagem_progresso.message_id,
                    text="🔄 <b>Tentando método alternativo...</b>",
                    parse_mode='HTML'
                )
                
                # Fallback para modelo mais estável (alias oficial)
                import os
                raw_key = os.getenv("GEMINI_API_KEY", "")
                genai.configure(api_key=raw_key.strip().strip('"\''))
                model = genai.GenerativeModel('gemini-flash-latest')
                response = await model.generate_content_async(prompt_final)
                resposta_ia = _limpar_resposta_ia(response.text)
            
            # --- 🔄 INDICADOR DE PROGRESSO: Remove mensagem inicial ---
            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=mensagem_progresso.message_id
                )
            except Exception:
                pass  # Se falhar ao deletar, não é crítico
            
            # Salva no cache
            _salvar_resposta_ia_cache(chave_cache_ia, resposta_ia)
        
        # --- Lógica de Decisão: É uma chamada de função (JSON) ou uma análise (texto)? ---
        try:
            # Tenta decodificar a resposta como JSON
            dados_funcao = json.loads(resposta_ia)
            if isinstance(dados_funcao, dict) and "funcao" in dados_funcao:
                nome_funcao = dados_funcao.get("funcao")
                parametros = dados_funcao.get("parametros", {})
                
                if nome_funcao == "listar_lancamentos":
                    await handle_lista_lancamentos(chat_id, context, parametros)
                else:
                    logger.warning(f"IA tentou chamar uma função desconhecida: {nome_funcao}")
                    await context.bot.send_message(chat_id, "A IA tentou uma ação que não conheço.")
            else:
                # Se não for um JSON de função, trata como texto normal.
                raise json.JSONDecodeError("Não é um JSON de função", resposta_ia, 0)

        except json.JSONDecodeError:
            # Se não for JSON, é uma análise de texto. Envia para o usuário.
            resposta_texto, reply_markup = parse_action_buttons(resposta_ia)
            await enviar_texto_em_blocos(context.bot, chat_id, resposta_texto, reply_markup=reply_markup)
            contexto_conversa.adicionar_interacao(user_question, resposta_texto, tipo="gerente_vdm_analise")

    except Exception as e:
        erro_detalhado = f"Erro CRÍTICO em handle_natural_language (V4): {str(e)}"
        logger.error(f"{erro_detalhado} para user {chat_id}", exc_info=True)
        await enviar_resposta_erro(context.bot, chat_id, erro_tecnico=erro_detalhado)
    finally:
        db.close()
        # Limpar rate limit antigo periodicamente
        limpar_rate_limit_antigo()
    
    return AWAIT_GERENTE_QUESTION

async def handle_dados_externos(update, context, user_question, usuario_db, contexto):
    flag, topico = detectar_intencao_e_topico(user_question)
    
    if flag:
        dados = await obter_dados_externos(flag)
        keyboard = [[InlineKeyboardButton("📈 Como isso me afeta?", callback_data=f"analise_{flag}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        resposta_texto = dados.get("texto_html", "Não encontrei a informação.")
        await enviar_texto_em_blocos(context.bot, usuario_db.telegram_id, resposta_texto, reply_markup=reply_markup)
        contexto.adicionar_interacao(user_question, resposta_texto, "dados_externos")

def _parse_filtros_lancamento(texto: str, db: Session, user_id: int) -> dict:
    """
    Extrai filtros de tipo, categoria, conta/forma de pagamento e data de um texto.
    """
    filtros = {}
    texto_lower = texto.lower()
    
    # --- CORREÇÃO: Definimos a lista no escopo principal da função ---
    formas_pagamento_comuns = ['pix', 'crédito', 'debito', 'dinheiro']

    # --- Filtro de TIPO ---
    PALAVRAS_GASTOS = ['gastos', 'despesas', 'saídas', 'saidas', 'paguei']
    PALAVRAS_RECEITAS = ['receitas', 'entradas', 'ganhei', 'recebi']

    if any(palavra in texto_lower for palavra in PALAVRAS_GASTOS):
        filtros['tipo'] = 'Saída'
    elif any(palavra in texto_lower for palavra in PALAVRAS_RECEITAS):
        filtros['tipo'] = 'Entrada'
    
    # --- Filtro de DATA ---
    hoje = datetime.now()
    if "mês passado" in texto_lower:
        primeiro_dia_mes_passado = (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)
        ultimo_dia_mes_passado = hoje.replace(day=1) - timedelta(days=1)
        filtros['data_inicio'] = primeiro_dia_mes_passado.replace(hour=0, minute=0, second=0)
        filtros['data_fim'] = ultimo_dia_mes_passado.replace(hour=23, minute=59, second=59)
    # ... (outros filtros de data)

    # --- LÓGICA UNIFICADA PARA CONTA E FORMA DE PAGAMENTO ---
    filtro_conta_encontrado = False
    contas_usuario = db.query(Conta).filter(Conta.id_usuario == user_id).all()
    
    for conta in contas_usuario:
        padrao_conta = r'\b' + re.escape(conta.nome.lower()) + r'\b'
        if re.search(padrao_conta, texto_lower):
            filtros['id_conta'] = conta.id
            filtro_conta_encontrado = True
            logging.info(f"Filtro de CONTA específica detectado: '{conta.nome}' (ID: {conta.id})")
            break 
    
    if not filtro_conta_encontrado:
        for fp in formas_pagamento_comuns: # Agora a variável já existe
            padrao_fp = r'\b' + re.escape(fp) + r'\b'
            if fp == 'crédito' and 'cartão' not in texto_lower:
                continue
            if re.search(padrao_fp, texto_lower):
                filtros['forma_pagamento'] = fp
                logging.info(f"Filtro de FORMA DE PAGAMENTO genérica detectado: '{fp}'")
                break

    # --- Filtro de CATEGORIA ---
    categorias_comuns = ['lazer', 'alimentação', 'transporte', 'moradia', 'saúde', 'receitas', 'compras']
    for cat in categorias_comuns:
        padrao_cat = r'\b' + re.escape(cat) + r'\b'
        if re.search(padrao_cat, texto_lower):
            filtros['categoria_nome'] = cat
            break
            
    # --- Filtro de busca por texto geral (QUERY) ---
    match = re.search(r'com\s+([a-zA-Z0-9çãáéíóúâêô\s]+)', texto_lower)
    if match:
        termo_busca = match.group(1).strip()
        # A variável 'formas_pagamento_comuns' agora está sempre acessível
        eh_fp_ou_conta = any(fp in termo_busca for fp in formas_pagamento_comuns) or \
                         any(conta.nome.lower() in termo_busca for conta in contas_usuario)
        
        if not eh_fp_ou_conta:
             filtros['query'] = termo_busca
             logging.info(f"Filtro de QUERY por texto detectado: '{termo_busca}'")

    return filtros

def _limpar_resposta_ia(texto: str) -> str:
    """Remove os blocos de código markdown e HTML malformado que a IA às vezes adiciona."""
    # Remove ```html, ```json, ```
    texto_limpo = re.sub(r'^```(html|json)?\n', '', texto, flags=re.MULTILINE)
    texto_limpo = re.sub(r'```$', '', texto_limpo, flags=re.MULTILINE)
    
    # Remove DOCTYPE e outras tags HTML problemáticas
    texto_limpo = re.sub(r'<!DOCTYPE[^>]*>', '', texto_limpo, flags=re.IGNORECASE)
    texto_limpo = re.sub(r'<html[^>]*>', '', texto_limpo, flags=re.IGNORECASE)
    texto_limpo = re.sub(r'</html>', '', texto_limpo, flags=re.IGNORECASE)
    texto_limpo = re.sub(r'<head[^>]*>.*?</head>', '', texto_limpo, flags=re.IGNORECASE | re.DOTALL)
    texto_limpo = re.sub(r'<body[^>]*>', '', texto_limpo, flags=re.IGNORECASE)
    texto_limpo = re.sub(r'</body>', '', texto_limpo, flags=re.IGNORECASE)
    
    # Remove tags <p> abertas sem fechamento
    texto_limpo = re.sub(r'<p\s*>', '\n', texto_limpo, flags=re.IGNORECASE)
    texto_limpo = re.sub(r'</p>', '\n', texto_limpo, flags=re.IGNORECASE)
    
    # Remove quebras de linha excessivas
    texto_limpo = re.sub(r'\n{3,}', '\n\n', texto_limpo)
    
    return texto_limpo.strip()

async def enviar_resposta_erro(bot, user_id, erro_tecnico: str = None):
    """
    Envia uma mensagem de erro amigável e profissional para o usuário.
    
    Args:
        bot: Instância do bot do Telegram
        user_id: ID do usuário
        erro_tecnico: Detalhes técnicos do erro (opcional, para logs)
    """
    # Mensagens de erro contextualizadas e profissionais
    mensagens_erro = [
        "🔧 <b>Ops! Algo inesperado aconteceu.</b>\n\n"
        "Minha IA está temporariamente indisponível. Tente novamente em alguns instantes.\n\n"
        "<i>💡 Dica: Enquanto isso, você pode usar os comandos diretos como /saldo ou /lancamentos</i>",
        
        "⚠️ <b>Desculpe pelo transtorno!</b>\n\n"
        "Não consegui processar sua pergunta no momento. "
        "Por favor, aguarde alguns segundos e tente novamente.\n\n"
        "<i>Se o problema persistir, tente reformular sua pergunta de forma mais simples.</i>",
        
        "🤖 <b>Houston, temos um problema!</b>\n\n"
        "Meu sistema de análise deu uma pausa inesperada. "
        "Mas não se preocupe, já estou me recuperando!\n\n"
        "<i>Tente novamente em 5 segundos. �</i>"
    ]
    
    try:
        mensagem_escolhida = random.choice(mensagens_erro)
        await bot.send_message(
            chat_id=user_id,
            text=mensagem_escolhida,
            parse_mode='HTML'
        )
        
        # Log detalhado para debug (sem expor ao usuário)
        if erro_tecnico:
            logger.error(f"❌ Erro detalhado para user {user_id}: {erro_tecnico}")
            
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO: Falha ao enviar mensagem de erro para user {user_id}: {e}")


async def handle_action_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa cliques em botões de ação gerados pela IA."""
    query = update.callback_query
    await query.answer()

    pergunta_simulada = query.data.replace("_", " ").capitalize()
    logger.info(f"Botão de ação clicado. Pergunta simulada para a IA: '{pergunta_simulada}'")
    
    if pergunta_simulada:
        await query.message.delete()
        # Chama a função principal de linguagem natural, passando a query e a pergunta simulada.
        await handle_natural_language(update, context, custom_question=pergunta_simulada)
            
    return AWAIT_GERENTE_QUESTION


async def handle_conversacional(update: Update, context: ContextTypes.DEFAULT_TYPE, user_question: str, usuario_db: Usuario, contexto: ContextoConversa):
    """
    Lida com saudações e interações casuais.
    """
    user_name = usuario_db.nome_completo.split(' ')[0] if usuario_db.nome_completo else "amigo"
    
    respostas = {
        "saudacao": [
            f"Olá, {user_name}! Como posso te ajudar a organizar suas finanças hoje?",
            f"E aí, {user_name}! Pronto pra deixar as contas em dia?",
            f"Opa, {user_name}! O que manda?"
        ],
        "agradecimento": [
            "De nada! Se precisar de mais alguma coisa, é só chamar.",
            "Disponha! Estou aqui pra isso.",
            "Tranquilo! Qualquer coisa, tô na área."
        ],
        "despedida": [
            "Até mais! Precisando, é só chamar.",
            "Falou! Se cuida.",
            "Tchau, tchau! Boas economias!"
        ]
    }
    
    pergunta_lower = user_question.lower()
    resposta_final = ""

    if any(s in pergunta_lower for s in ['oi', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'tudo bem', 'blz', 'e aí']):
        resposta_final = random.choice(respostas['saudacao'])
    elif any(s in pergunta_lower for s in ['obrigado', 'vlw', 'valeu', 'obg']):
        resposta_final = random.choice(respostas['agradecimento'])
    elif any(s in pergunta_lower for s in ['tchau', 'até mais', 'falou']):
        resposta_final = random.choice(respostas['despedida'])
    else:
        # Fallback para caso a intenção seja conversacional, mas não mapeada
        resposta_final = f"Entendido, {user_name}! Se tiver alguma pergunta específica sobre suas finanças, pode mandar."
        
    await update.message.reply_text(resposta_final)
    contexto.adicionar_interacao(user_question, resposta_final, "conversacional")

async def handle_maior_despesa(update, context, user_question, usuario_db, contexto, db):
    """Encontra e exibe o maior gasto em um período."""
    filtros = _parse_filtros_lancamento(user_question)
    
    # Força o tipo para 'Saída' e limita a 1 resultado
    filtros['tipo'] = 'Saída'
    
    # A busca agora é por valor, não por data
    maior_gasto = db.query(Lancamento).filter(
        Lancamento.id_usuario == usuario_db.id,
        Lancamento.tipo == 'Saída'
    )
    if filtros.get('data_inicio'):
        maior_gasto = maior_gasto.filter(Lancamento.data_transacao >= filtros['data_inicio'])
    if filtros.get('data_fim'):
        maior_gasto = maior_gasto.filter(Lancamento.data_transacao <= filtros['data_fim'])

    maior_gasto = maior_gasto.order_by(Lancamento.valor.desc()).first()

    if not maior_gasto:
        await update.message.reply_text("Não encontrei nenhuma despesa para o período que você pediu.")
        return

    resposta_texto = (
        f"Sua maior despesa no período foi:\n\n"
        f"{formatar_lancamento_detalhado(maior_gasto)}"
    )
    await enviar_texto_em_blocos(context.bot, usuario_db.telegram_id, resposta_texto)
    contexto.adicionar_interacao(user_question, f"Mostrou maior despesa: {maior_gasto.descricao}", "maior_despesa")


async def handle_analise_geral(update, context, user_question, usuario_db, contexto, db):
    tipo_filtro = None
    if any(palavra in user_question.lower() for palavra in ['gastei', 'gasto', 'despesa']):
        tipo_filtro = 'Saída'
    elif any(palavra in user_question.lower() for palavra in ['ganhei', 'recebi', 'receita']):
        tipo_filtro = 'Entrada'

    # --- MUDANÇA: APLICAMOS O FILTRO DE CONTA AQUI TAMBÉM ---
    filtros_iniciais = _parse_filtros_lancamento(user_question, db, usuario_db.id)
    if tipo_filtro:
        filtros_iniciais['tipo'] = tipo_filtro

    # Buscamos todos os lançamentos que correspondem aos filtros iniciais
    lancamentos = buscar_lancamentos_usuario(
        telegram_user_id=usuario_db.telegram_id,
        limit=200, # Pegamos um limite alto para a análise
        **filtros_iniciais
    )
    
    if not lancamentos:
        await update.message.reply_text("Não encontrei nenhum lançamento para sua pergunta.")
        return
    
     # --- NOVA LÓGICA PARA DEFINIR O PERÍODO DA ANÁLISE ---
    data_mais_antiga = min(l.data_transacao for l in lancamentos)
    data_mais_recente = max(l.data_transacao for l in lancamentos)
    periodo_analise_str = f"de {data_mais_antiga.strftime('%d/%m/%Y')} a {data_mais_recente.strftime('%d/%m/%Y')}"
    # ---------------------------------------------------------

    # --- NOVO: PRÉ-CÁLCULO DO VALOR TOTAL ---
    valor_total_calculado = sum(float(l.valor) for l in lancamentos)

    contexto_json = preparar_contexto_json(lancamentos)
    analise_comportamental = analisar_comportamento_financeiro(lancamentos)
    analise_json = json.dumps(analise_comportamental, indent=2, ensure_ascii=False)
    
    # Passamos o valor pré-calculado para o prompt
    prompt_usado = PROMPT_GERENTE_VDM.format(
        user_name=usuario_db.nome_completo or "você",
        perfil_investidor=usuario_db.perfil_investidor or "Não definido",
        pergunta_usuario=user_question,
        contexto_json=contexto_json,
        analise_comportamental_json=analise_json,
        periodo_analise=periodo_analise_str,
        valor_total_pre_calculado=valor_total_calculado 
    )
    
    await gerar_resposta_ia(update, context, prompt_usado, user_question, usuario_db, contexto, "analise_geral")


async def gerar_resposta_ia(update, context, prompt, user_question, usuario_db, contexto, tipo_interacao):
    try:
        # Tentar com o modelo configurado, se falhar usar fallback
        try:
            model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
            response = await model.generate_content_async(prompt)
        except Exception as model_error:
            logger.error(f"⚠️ Erro com modelo '{config.GEMINI_MODEL_NAME}': {model_error}")
            logger.info("🔄 Tentando fallback para 'gemini-flash-latest'...")
            model = genai.GenerativeModel('gemini-flash-latest')
            response = await model.generate_content_async(prompt)
        
        # --- NOVA LÓGICA DE PROCESSAMENTO JSON (MAIS SEGURA) ---
        
        # 1. Tenta encontrar o bloco JSON na resposta da IA
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        
        # 2. Se NÃO encontrar um JSON, trata o erro elegantemente
        if not json_match:
            logger.error(f"A IA não retornou um JSON válido. Resposta recebida: {response.text}")
            # Usa a resposta em texto livre da IA como um fallback, se fizer sentido
            # ou envia uma mensagem de erro padrão.
            await update.message.reply_text(
                "Hmm, não consegui estruturar a resposta. Aqui está o que a IA disse:\n\n"
                f"<i>{response.text}</i>",
                parse_mode='HTML'
            )
            # Adiciona ao contexto para não perder o histórico
            contexto.adicionar_interacao(user_question, response.text, tipo_interacao)
            return # Sai da função

        # 3. Se encontrou um JSON, tenta decodificá-lo
        try:
            dados_ia = json.loads(json_match.group(0))
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON da IA: {e}\nString Tentada: {json_match.group(0)}")
            await enviar_resposta_erro(context.bot, usuario_db.telegram_id)
            return

        # 4. Se o JSON foi decodificado, monta a mensagem formatada
        # (O código de formatação que fizemos antes continua aqui, sem alterações)
        titulo = dados_ia.get("titulo_resposta", "Análise Rápida")
        valor_total = dados_ia.get("valor_total", 0.0)
        comentario = dados_ia.get("comentario_maestro", "Aqui está o que encontrei.")
        detalhamento = dados_ia.get("detalhamento", [])
        proximo_passo = dados_ia.get("proximo_passo", {})

        mensagem_formatada = f"<b>{titulo}</b>\n"
        mensagem_formatada += f"━━━━━━━━━━━━━━━━━━\n\n"
        
        # Adiciona o valor total apenas se for maior que zero
        if valor_total > 0:
            mensagem_formatada += f"O valor total foi de <code>R$ {valor_total:.2f}</code>.\n\n"
        
        if detalhamento:
            mensagem_formatada += "Aqui está o detalhamento:\n"
            for item in detalhamento:
                emoji = item.get("emoji", "🔹")
                nome_item = item.get("item", "N/A")
                valor_item = item.get("valor", 0.0)
                mensagem_formatada += f"{emoji} <b>{nome_item}:</b> <code>R$ {valor_item:.2f}</code>\n"
            mensagem_formatada += "\n"

        mensagem_formatada += f"<i>{comentario}</i>\n"

        keyboard = None
        if proximo_passo and proximo_passo.get("botao_texto"):
            mensagem_formatada += f"\n💡 <b>Próximo Passo:</b> {proximo_passo.get('texto', '')}"
            keyboard = [[
                InlineKeyboardButton(
                    proximo_passo["botao_texto"], 
                    callback_data=proximo_passo["botao_callback"]
                )
            ]]
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        await enviar_texto_em_blocos(
            context.bot, 
            usuario_db.telegram_id, 
            mensagem_formatada, 
            reply_markup=reply_markup
        )
        contexto.adicionar_interacao(user_question, mensagem_formatada, tipo_interacao)
        
    except Exception as e:
        logger.error(f"Erro geral e inesperado em gerar_resposta_ia: {e}", exc_info=True)
        await enviar_resposta_erro(context.bot, usuario_db.telegram_id)

import traceback

def self_healing_decorator(func):
    """Decorator que captura exceções, formata o traceback e envia para o usuário."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            error_details = traceback.format_exc()
            user_message = (
                "💣 *BOOM!* Algo quebrou no comando que você usou.\n\n"
                "*RELATÓRIO DE AUTO-DESTRUIÇÃO:*\n"
                f"```\n{error_details}\n```\n\n"
                "O dev já foi notificado (mentira, mas ele vai ver isso eventualmente). Tente de novo, talvez com mais fé."
            )
            await update.message.reply_text(user_message, parse_mode='Markdown')
            logger.error(f"Erro auto-reportado no comando {func.__name__}: {error_details}")
    return wrapper




# --- EXPORTS PARA IMPORTS EXPLÍCITOS ---

def create_gerente_conversation_handler():
    from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, filters
    return ConversationHandler(
        entry_points=[CommandHandler("gerente", start_gerente)],
        states={
            AWAIT_GERENTE_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_natural_language)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

# --- STUB PARA CORRIGIR IMPORTAÇÃO DO EMAIL ---
def create_cadastro_email_conversation_handler():
    """
    Stub para cadastro de email. Implemente a lógica real conforme necessário.
    """
    from telegram.ext import ConversationHandler, CommandHandler
    async def start_email(update, context):
        await update.message.reply_text("Fluxo de cadastro de email não implementado.")
        return ConversationHandler.END
    return ConversationHandler(
        entry_points=[CommandHandler("cadastro_email", start_email)],
        states={},
        fallbacks=[CommandHandler("cancel", start_email)],
    )

__all__ = [
    "create_gerente_conversation_handler",
    "create_cadastro_email_conversation_handler",
    "painel_notificacoes",
    # Adicione outros exports necessários aqui
]
