"""
🤖 Handlers para Análises Inteligentes com IA
==============================================

Comandos do bot que usam IA para análises avançadas de gastos.

Autor: Henrique Freitas
Data: 17/11/2025
"""

import logging
import json
import asyncio
import re
import os
import time
from jinja2 import Template
from calendar import monthrange
from collections import Counter
from html import escape
from urllib.parse import quote
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler
from sqlalchemy import and_, extract, func, or_, not_
from database.database import get_db, get_or_create_user
from models import Lancamento, Usuario, Categoria, Agendamento, Lembrete, Objetivo, ItemLancamento, OrcamentoCategoria, Subcategoria

def _sum_consistente(lista):
    """Soma consistente de lançamentos (Sincronizado com dashboard_app.py)"""
    e = 0.0
    s = 0.0
    for l in lista:
        t = str(l.tipo).lower()
        if t in ["transferencia", "transferência", "transfer"]: continue
        v = abs(float(l.valor or 0))
        if t.startswith(("entr", "recei")): e += v
        elif t.startswith(("desp", "saida", "saída", "pago", "enviado")): s += v
    return round(e, 2), round(s, 2)


def _get_subcats_ignore_ids(db) -> list[int]:
    """Retorna IDs de subcategorias que devem ser ignoradas para evitar duplicidade (Faturas e Transf. Internas)."""
    subcats = db.query(Subcategoria.id).filter(
        or_(
            Subcategoria.nome.ilike('%Pagamento de Fatura%'),
            Subcategoria.nome.ilike('%Transferência Interna%')
        )
    ).all()
    return [s[0] for s in subcats]

def _filtrar_saidas_reais(lancamentos: list[Lancamento], ignore_ids: list[int]) -> list[Lancamento]:
    """Retorna apenas os lançamentos que são saídas reais (não duplicatas). Sincronizado com MiniApp."""
    saidas = []
    for l in lancamentos:
        tipo = str(l.tipo).lower()
        # Filtro IDÊNTICO ao analytics/dashboard_app.py
        if tipo in ["transferencia", "transferência", "transfer"]:
            continue
        if tipo.startswith(("entr", "recei")):
            continue
        saidas.append(l)
    return saidas

def _calcular_saidas_reais(lancamentos: list[Lancamento], ignore_ids: list[int]) -> float:
    """Calcula a soma absoluta de saídas reais."""
    return round(sum(abs(float(l.valor or 0)) for l in _filtrar_saidas_reais(lancamentos, ignore_ids)), 2)
import config
from gerente_financeiro.services import _categorizar_com_mapa_inteligente
from gerente_financeiro.prompt_manager import PromptManager, PromptConfig
from pathlib import Path
from gerente_financeiro.prompts import PROMPT_ALFREDO_APRIMORADO
from gerente_financeiro.monetization import (
    consume_feature_quota,
    ensure_user_plan_state,
    plan_allows_feature,
    upgrade_prompt_for_feature,
)
from fiis.fii_handler import detect_fii_intent, route_fii_intent
from gerente_financeiro.ai_service import (
    _smart_ai_completion_async, 
    _groq_transcribe_voice_async, 
    _groq_chat_completion_async,
    _extrair_tool_calls_do_texto, 
    _contem_tool_call_json,
    _ALFREDO_TOOLS_NAMES
)

logger = logging.getLogger(__name__)

_FORMAS_PAGAMENTO_VALIDAS = {"Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"}


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
        "nao_informado": "Nao_informado",
        "não informado": "Nao_informado",
        "nao informado": "Nao_informado",
        "n/a": "Nao_informado",
        "": "Nao_informado",
    }
    return mapa.get(raw, "Nao_informado")


def _get_webapp_url(tab: str | None = None, draft: dict | None = None) -> str:
    base_url = os.getenv("DASHBOARD_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:5000"
    base_url = base_url.rstrip("/")
    url = f"{base_url}/webapp"
    params: list[str] = []
    if tab:
        params.append(f"tab={quote(tab, safe='')}")
    if draft:
        params.append(f"draft={quote(json.dumps(draft, ensure_ascii=False), safe='')}")
    if params:
        url = f"{url}?{'&'.join(params)}"
    return url


def _inferir_tipo_lancamento(texto_usuario: str, categoria: str, tipo_ia: str | None = None) -> str:
    """Inferência inteligente de tipo baseada em semântica e contexto."""
    tipo_raw = str(tipo_ia or "").strip().lower()
    if tipo_raw in {"entrada", "receita", "recebi", "credit"}:
        return "Entrada"
    if tipo_raw in {"saida", "saída", "despesa", "gastei", "debit"}:
        return "Saída"

    texto = f"{texto_usuario} {categoria}".lower()
    
    # Sinais semânticos fortes de entrada
    sinais_entrada = [
        "receita", "entrada", "recebi", "ganhei", "salario", "salário", "venda", 
        "reembolso", "estorno", "dividendo", "rendimento", "pix recebido", "ted recebida",
        "lucro", "comissao", "comissão", "bonus", "bônus", "ganho", "pro-labore"
    ]
    
    # Sinais semânticos fortes de saída
    sinais_saida = [
        "despesa", "saida", "saída", "gastei", "paguei", "compra", "debito", "débito",
        "pagamento", "transferi", "enviei", "pix enviado", "ted enviada", "custo",
        "perdi", "assinatura", "mensalidade", "fatura", "boleto", "tarifa"
    ]

    # Prioridade para sinais de entrada (mais raros de falar por engano)
    tem_entrada = any(s in texto for s in sinais_entrada)
    tem_saida = any(s in texto for s in sinais_saida)

    if tem_entrada and not tem_saida:
        return "Entrada"
    if tem_saida and not tem_entrada:
        return "Saída"
        
    # Se ambos ou nenhum, e a categoria for Financeiro/Salário, tende a ser Entrada
    if "salario" in texto or "rendimento" in texto:
        return "Entrada"
        
    return "Saída"


def _normalizar_data_lancamento(valor_data: str | None) -> str:
    raw = str(valor_data or "").strip()
    if not raw:
        return datetime.now().strftime("%d/%m/%Y")
    if raw.lower() == "hoje":
        return datetime.now().strftime("%d/%m/%Y")

    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", raw):
        return raw

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return datetime.now().strftime("%d/%m/%Y")

    try:
        return datetime.fromisoformat(raw).strftime("%d/%m/%Y")
    except ValueError:
        return datetime.now().strftime("%d/%m/%Y")


_ALFREDO_TOOLS = [
    {
            "type": "function",
            "function": {
                "name": "definir_limite_orcamento",
                "description": "Define um limite (teto de gastos) de orçamento para uma categoria em um período específico (diário, semanal ou mensal).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "categoria": {"type": "string", "description": "Nome da categoria (ex: Lazer, Alimentação, Transporte)"},
                        "valor": {"type": "number", "description": "Valor monetário do limite"},
                        "periodo": {
                            "type": "string", 
                            "enum": ["diário", "semanal", "mensal"],
                            "description": "Período do limite. Se o usuário não mencionar, deixe em branco."
                        },
                    },
                    "required": ["categoria", "valor"],
                },
            },
        },
        {
        "type": "function",
        "function": {
            "name": "registrar_lancamento",
            "description": "Registra um lançamento financeiro NOVO. Use APENAS quando o usuário der uma ORDEM DIRETA de registro (ex: 'gastei 50', 'recebi 100'). PROIBIDO usar para perguntas que começam com 'Quanto', 'Qual', 'Me mostra' ou 'Busque', que são consultas ao histórico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "valor": {"type": "number"},
                    "categoria": {"type": "string"},
                    "forma_pagamento": {
                        "type": "string",
                        "enum": ["Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"],
                    },
                },
                "required": ["descricao", "valor", "categoria", "forma_pagamento"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agendar_despesa",
            "description": "Prepara um agendamento de despesa recorrente. A DATA DE HOJE deve ser usada como referência para extrair a data correta (ex: 'quarta que vem').",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "O QUE o usuário está pagando. Extraia o nome da pessoa ou item (ex: 'Michel', 'Aluguel', 'Academia').",
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor monetario unitario da parcela/evento. Extraia o numero exato citado pelo usuario (32 significa 32, nunca 12).",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do primeiro evento em YYYY-MM-DD. Calcule com base em 'Hoje'.",
                    },
                    "frequencia": {
                        "type": "string",
                        "description": "Frequencia do agendamento: unico, semanal ou mensal. Se nao informado, usar mensal.",
                    },
                    "parcelas": {
                        "type": "number",
                        "description": "Quantidade de meses ou vezes (numero inteiro esperado). Se nao informado, assuma nulo/infinito.",
                    },
                },
                "required": ["descricao", "valor", "data", "frequencia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agendar_receita",
            "description": "Prepara um agendamento de receita recorrente. A DATA DE HOJE deve ser usada como referência para extrair a data correta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "DE ONDE vem a receita. Extraia o nome da fonte ou item (ex: 'Salário', 'Michel', 'Venda do Carro').",
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor monetario unitario da receita recorrente.",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do primeiro recebimento em YYYY-MM-DD. Calcule com base em 'Hoje'.",
                    },
                    "frequencia": {
                        "type": "string",
                        "description": "Frequencia do agendamento: unico, semanal ou mensal. Se nao informado, usar mensal.",
                    },
                    "parcelas": {
                        "type": "number",
                        "description": "Quantidade de meses ou vezes (inteiro). Se nao informado, assuma nulo/infinito.",
                    },
                },
                "required": ["descricao", "valor", "data", "frequencia"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_lembrete",
            "description": "Cria um lembrete financeiro ou pessoal. A DATA DE HOJE deve ser usada como referência para calcular datas relativas como 'quarta que vem'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "O conteúdo do lembrete. Extraia o nome da pessoa ou ação (ex: 'Pagar Michel', 'Comprar leite', 'Falar com gerente').",
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor mencionado pelo usuário, se houver.",
                    },
                    "tipo": {
                        "type": "string",
                        "enum": ["Receita", "Saída", "Despesa", "Entrada"],
                        "description": "Tipo do lembrete, se ficar claro no pedido.",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do lembrete em YYYY-MM-DD. Calcule com base em 'Hoje'.",
                    },
                    "frequencia": {
                        "type": "string",
                        "description": "Frequencia do lembrete: unico, semanal ou mensal. Se nao informado, usar unico.",
                    },
                    "parcelas": {
                        "type": "number",
                        "description": "Quantidade de repetições quando o usuário informar explicitamente.",
                    },
                },
                "required": ["descricao", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_meta",
            "description": "Cria uma meta financeira para o usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string", "description": "Descrição da meta (ex: Viagem, Carro, Reserva)"},
                    "valor_alvo": {"type": "number", "description": "Valor total que deseja atingir"},
                    "data_meta": {"type": "string", "description": "Data limite no formato YYYY-MM-DD"},
                },
                "required": ["descricao", "valor_alvo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "responder_duvida_financeira",
            "description": "Responde dúvidas financeiras gerais e sobre os dados do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pergunta": {"type": "string"},
                },
                "required": ["pergunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_historico_financeiro",
            "description": "Consulta o banco de dados para histórico, maiores gastos ou somas. Se o usuário usar termos como 'besteira', use 'tipo_busca=lista_por_termo' e busque por categorias de Lazer ou Alimentação.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_busca": {
                        "type": "string", 
                        "enum": ["maior_gasto", "maior_receita", "soma_categoria", "lista_por_termo", "detalhe_item"],
                        "description": "Obrigatório. Use 'maior_gasto' para o valor mais alto. 'soma_categoria' para totais."
                    },
                    "termo": {"type": "string", "description": "Termo de busca. Mapeie termos humanos: 'besteira' -> 'Lazer', 'mercado' -> 'Alimentação'."},
                    "limite": {"type": "number", "description": "Quantidade de registros."},
                    "periodo": {
                        "type": "string", 
                        "enum": ["esta_semana", "semana_passada", "este_mes", "mes_passado", "este_ano", "ultimos_7_dias", "ultimos_30_dias", "tudo"], 
                        "description": "Janela temporal. Use 'esta_semana' para 'essa semana', 'nessa semana' ou 'esta semana'."
                    }
                },
                "required": ["tipo_busca"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comparar_periodos_financeiros",
            "description": "Compara dois meses específicos do histórico financeiro do usuário. Útil para 'comparar abril com março'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mes_alvo": {"type": "number", "description": "Número do mês a comparar (1-12)."},
                    "ano_alvo": {"type": "number", "description": "Ano do mês a comparar (ex: 2026)."},
                    "mes_referencia": {"type": "number", "description": "Número do mês de referência (base) para comparação (1-12)."},
                    "ano_referencia": {"type": "number", "description": "Ano do mês de referência (ex: 2026)."}
                },
                "required": ["mes_alvo", "ano_alvo", "mes_referencia", "ano_referencia"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_compromissos_futuros",
            "description": "Consulta o que o usuário ainda tem para pagar ou receber (Agendamentos e Lembretes) no futuro próximo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {"type": "string", "enum": ["hoje", "esta_semana", "proximos_30_dias"], "description": "Janela de busca de compromissos."}
                },
                "required": ["periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "categorizar_lancamentos_pendentes",
            "description": "Categoriza automaticamente todos os lançamentos financeiros do usuário que estão sem categoria registrada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "executar": {
                        "type": "boolean",
                        "description": "Sempre true para executar a categorização."
                    }
                },
                "required": ["executar"]
            },
        },
    },
]


def _clear_pending_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    # Limpa estados pendentes de fluxos antigos para evitar conflito de botões/menu.
    keys = [
        "novo_lancamento",
        "dados_audio",
        "dados_ocr",
        "fatura_transacoes",
        "fatura_conta_id",
        "fatura_origem_label",
        "fatura_training_bytes",
        "fatura_training_name",
        "fatura_training_size",
        "fatura_training_pages",
        "fatura_training_text",
        "dados_quick",
    ]
    for key in keys:
        context.user_data.pop(key, None)


def _normalizar_tipo_compromisso(valor: str | None, fallback: str = "Saída") -> str:
    raw = str(valor or "").strip().lower()
    if raw in {"receita", "entrada"}:
        return "Receita"
    if raw in {"despesa", "saida", "saída"}:
        return "Saída"
    return fallback


def _emoji_compromisso(tipo: str | None) -> str:
    return "🟢" if str(tipo or "").lower() in {"receita", "entrada"} else "🔔"


def _rotulo_tipo_compromisso(acao: str) -> str:
    return "lembrete" if acao == "criar_lembrete" else "agendamento"


def _build_quick_compromisso_preview(dados_quick: dict) -> str:
    descricao = escape(str(dados_quick.get("descricao") or "Sem descrição"))
    valor = dados_quick.get("valor")
    data_str = str(dados_quick.get("data") or "").strip()
    frequencia = escape(str(dados_quick.get("frequencia") or "unico"))
    parcelas = dados_quick.get("parcelas")
    parcelas_texto = "indefinido" if parcelas is None else str(parcelas)
    acao = dados_quick.get("acao")
    eh_lembrete = acao == "criar_lembrete"
    titulo = "Confirme o lembrete" if eh_lembrete else (
        "Confirme o agendamento de receita" if acao == "agendar_receita" else "Confirme o agendamento"
    )
    emoji = _emoji_compromisso(dados_quick.get("tipo"))

    try:
        data_fmt = datetime.fromisoformat(data_str).strftime("%d/%m/%Y") if data_str else "Sem data"
    except ValueError:
        data_fmt = data_str or "Sem data"

    linhas = [
        f"{emoji} <b>{titulo}</b>",
        "",
        f"• <b>Descrição:</b> {descricao}",
    ]
    if valor is not None and valor != "":
        try:
            linhas.append(f"• <b>Valor:</b> <code>{_formatar_valor_brasileiro(float(valor))}</code>")
        except (TypeError, ValueError):
            pass
    if dados_quick.get("tipo"):
        linhas.append(f"• <b>Tipo:</b> {escape(str(dados_quick.get('tipo')))}")
    linhas.append(f"• <b>Data:</b> {escape(data_fmt)}")
    if dados_quick.get("frequencia"):
        linhas.append(f"• <b>Frequência:</b> {frequencia}")
    if not eh_lembrete or parcelas is not None:
        linhas.append(f"• <b>Parcelas:</b> {escape(parcelas_texto)}")
    if eh_lembrete:
        linhas.append("")
        linhas.append("<i>Esse lembrete não será salvo como lançamento financeiro.</i>")
    return "\n".join(linhas)


def _build_quick_compromisso_keyboard(dados_quick: dict) -> InlineKeyboardMarkup:
    acao = dados_quick.get("acao")
    if acao == "criar_lembrete":
        troca = InlineKeyboardButton("📅 Trocar para agendamento", callback_data="quick_toggle_agendamento")
    else:
        troca = InlineKeyboardButton("🔔 Trocar para lembrete", callback_data="quick_toggle_lembrete")

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
        [InlineKeyboardButton("✏️ Editar", callback_data="quick_edit")],
        [troca],
        [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
    ])


def _alternar_tipo_compromisso(dados_quick: dict, destino: str) -> dict:
    novo = dict(dados_quick)
    if destino == "lembrete":
        novo["acao"] = "criar_lembrete"
        novo["tipo"] = _normalizar_tipo_compromisso(novo.get("tipo"))
        novo["frequencia"] = str(novo.get("frequencia") or "unico").strip().lower()
        return novo

    tipo = _normalizar_tipo_compromisso(novo.get("tipo"))
    novo["acao"] = "agendar_receita" if tipo == "Receita" else "agendar_despesa"
    novo["tipo"] = tipo
    novo["frequencia"] = str(novo.get("frequencia") or "mensal").strip().lower()
    if not novo.get("valor"):
        novo["valor"] = 0.0
    return novo


def _resolve_categoria_id(db, categoria_nome: str) -> int | None:
    if not categoria_nome:
        return None
    categoria = db.query(Categoria).filter(Categoria.nome.ilike(categoria_nome.strip())).first()
    return categoria.id if categoria else None


def _usuario_e_saldo(db, telegram_user) -> tuple[Usuario, float, float, float]:
    usuario_db = get_or_create_user(db, telegram_user.id, telegram_user.full_name)
    ignore_ids = _get_subcats_ignore_ids(db)
    
    # Busca TODOS os lançamentos para o Saldo Acumulado (Patrimônio)
    todos_lanc = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id).all()
    
    # Lógica de soma sincronizada
    def _calc_totals(lista):
        ent = 0.0
        sai = 0.0
        for l in lista:
            tipo = str(l.tipo).lower()
            if tipo in ["transferencia", "transferência", "transfer"]: continue
            val = abs(float(l.valor or 0))
            if tipo.startswith(("entr", "recei")): ent += val
            elif tipo.startswith(("desp", "saida")): sai += val
        return round(ent, 2), round(sai, 2)

    ent_total, sai_total = _calc_totals(todos_lanc)
    saldo_acumulado = round(ent_total - sai_total, 2)

    # Busca lançamentos do MÊS ATUAL para bater com a Home do MiniApp
    hoje = datetime.now()
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lanc_mes = [l for l in todos_lanc if l.data_transacao >= inicio_mes]
    ent_mes, sai_mes = _calc_totals(lanc_mes)
                 
    # Retornamos os dados do MÊS ATUAL como padrão para as análises rápidas
    # Mas mantemos o objeto usuario_db e o saldo_acumulado acessíveis
    return usuario_db, saldo_acumulado, ent_mes, sai_mes


def _formatar_valor_brasileiro(valor: float) -> str:
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_resposta_html(texto: str) -> str:
    texto = (texto or "").strip().replace("\r\n", "\n")
    
    # 1. Limpeza total: Remover blocos de código e caracteres que o Telegram confunde com tags
    texto = re.sub(r"```(?:html|json|markdown|md)?\s*", "", texto, flags=re.IGNORECASE)
    texto = texto.replace("```", "")
    
    # 2. Remover tags HTML que a IA possa ter inventado (limpeza bruta)
    texto = texto.replace("<", "&lt;").replace(">", "&gt;")
    
    # 3. Converter Markdown para o NOSSO HTML seguro (re-adicionando as tags permitidas)
    # Títulos
    texto = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", texto, flags=re.MULTILINE)
    # Negrito (Markdown ** ou __)
    texto = re.sub(r"(\*\*|__)(.+?)\1", r"<b>\2</b>", texto)
    # Itálico (Markdown * ou _)
    texto = re.sub(r"(?<!\w)([*_])(.+?)\1(?!\w)", r"<i>\2</i>", texto)
    # Listas
    texto = re.sub(r"^\s*[-*]\s+", "• ", texto, flags=re.MULTILINE)
    # Espaçamento
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    
    # 4. Des-escapar as tags que NÓS colocamos (reverter apenas o necessário)
    texto = texto.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    texto = texto.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    texto = texto.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
    
    return texto.strip()


async def _enviar_resposta_html_segura(message, texto: str, **kwargs):
    """
    Formata e envia uma resposta em HTML para o usuário.
    Garante que se a mensagem for muito longa, ela seja fatiada para evitar erro 400 do Telegram.
    Se falhar o parse do HTML, envia como texto simples.
    """
    texto_html = _formatar_resposta_html(texto)
    
    # Se for pequeno, envia direto (caminho rápido)
    if len(texto_html) <= 4000:
        try:
            return await message.reply_html(texto_html, **kwargs)
        except Exception as exc:
            if "Message is too long" in str(exc):
                return await _enviar_mensagem_fatiada(message, texto_html, is_html=True, **kwargs)
            
            if "Can't parse entities" in str(exc) or "unsupported" in str(exc).lower():
                logger.warning("Falha no parse HTML (entidades); tentando texto simples...")
                # Remover tags HTML para enviar plano
                texto_plano = re.sub(r"<[^>]+>", "", texto_html)
                try:
                    return await message.reply_text(texto_plano, **kwargs)
                except Exception as e2:
                    logger.error("Erro fatal ao enviar texto simples: %s", e2)
                    return None
                
            logger.warning("Falha genérica ao enviar HTML seguro; usando texto simples: %s", exc)
            texto_plano = re.sub(r"<[^>]+>", "", texto_html)
            try:
                return await message.reply_text(texto_plano, **kwargs)
            except Exception as e2:
                logger.error("Erro ao enviar texto simples: %s", e2)
                return await _enviar_mensagem_fatiada(message, texto_plano, is_html=False, **kwargs)

    # Se for longo (> 4000), fatiar
    logger.info(f"Mensagem longa detectada ({len(texto_html)} chars). Fatiando...")
    return await _enviar_mensagem_fatiada(message, texto_html, is_html=True, **kwargs)


async def _enviar_mensagem_fatiada(message, texto: str, is_html: bool = True, **kwargs):
    """Divide a mensagem em pedaços menores de 4000 caracteres, garantindo HTML válido se necessário."""
    limite = 4000
    pedaços = []
    tags_abertas = []
    temp_texto = texto
    
    while temp_texto:
        if len(temp_texto) <= limite:
            fatia = temp_texto
            temp_texto = ""
        else:
            quebra = temp_texto.rfind('\n', 0, limite)
            if quebra == -1:
                quebra = limite
            fatia = temp_texto[:quebra]
            temp_texto = temp_texto[quebra:].lstrip()
            
        if is_html:
            # Reabre as tags que ficaram abertas da fatia anterior
            prefixo = "".join([f"<{t}>" for t in tags_abertas])
            fatia_atual = prefixo + fatia
            
            # Analisa tags nesta fatia para atualizar a lista de abertas para a próxima
            tags_re = re.compile(r'<(b|i|code|a)(?:\s+[^>]*?)?>|</(b|i|code|a)>', re.IGNORECASE)
            for match in tags_re.finditer(fatia):
                tag_name = match.group(1)
                if tag_name: # Abertura
                    tags_abertas.append(tag_name.lower())
                else: # Fechamento
                    tag_fechou = match.group().lower()[2:-1]
                    if tags_abertas and tags_abertas[-1] == tag_fechou:
                        tags_abertas.pop()
            
            # Fecha as tags abertas no final desta fatia para garantir HTML válido na mensagem
            sufixo = "".join([f"</{t}>" for t in reversed(tags_abertas)])
            fatia_atual += sufixo
            pedaços.append(fatia_atual)
        else:
            pedaços.append(fatia)
    
    for p in pedaços:
        if not p.strip(): continue
        try:
            if is_html:
                # IMPORTANTE: Usar reply_html direto aqui para evitar recursão infinita
                await message.reply_html(p, **kwargs)
            else:
                await message.reply_text(p, **kwargs)
        except Exception as e:
            logger.error("Erro ao enviar fatia: %s", e)
            if is_html:
                # Fallback para texto plano se falhar o HTML da fatia
                p_plano = re.sub(r"<[^>]+>", "", p)
                try:
                    await message.reply_text(p_plano, **kwargs)
                except Exception:
                    pass


def _is_intencao_de_criacao(texto: str) -> bool:
    """Detecta se o texto indica uma intenção de criar, agendar ou lembrar algo."""
    t = (texto or "").lower()
    # Verbos e substantivos que indicam criação/ação futura
    gatilhos = [
        "criar", "crie", "nova", "novo", "adicionar", "definir", "registra", "registre", 
        "anota", "anote", "coloca", "coloque", "agendar", "agende", "me lembre", "lembra", 
        "meta", "lembrete", "agendamento", "programar", "programe"
    ]
    # Se tem verbo de ação e não é uma pergunta de consulta
    tem_verbo = any(v in t for v in gatilhos)
    eh_consulta = any(c in t for c in ["quais", "como", "onde", "quando", "tenho", "tem", "qual o", "qual a"])
    
    return tem_verbo and not eh_consulta


def _parse_br_money(val_str: str, texto_contexto: str = "") -> float | None:
    """Converte string de valor monetário brasileiro para float de forma robusta, lidando com multiplicadores."""
    if not val_str:
        return None
    
    # Limpeza básica
    v = val_str.replace("R$", "").replace("$", "").replace(" ", "").lower().strip()
    
    # Se o valor vier acompanhado de "mil" ou "k" no texto próximo ou na própria string
    multiplicador = 1.0
    texto_para_checar = (v + " " + texto_contexto.lower()).strip()
    
    if "milhão" in texto_para_checar or "milhões" in texto_para_checar or "mi" in texto_para_checar.split():
        multiplicador = 1000000.0
    elif "mil" in texto_para_checar or " k" in texto_para_checar or v.endswith("k"):
        multiplicador = 1000.0

    # Remove caracteres não numéricos exceto , e .
    v = re.sub(r'[^0-9,.]', '', v)
    if not v: return None

    # Lógica de vírgula e ponto
    if "," in v and "." in v:
        v = v.replace(".", "").replace(",", ".")
    elif "," in v:
        v = v.replace(",", ".")
    elif "." in v:
        partes = v.split(".")
        if len(partes[-1]) == 3: # Provável milhar (ex: 7.500)
            v = v.replace(".", "")
    
    try:
        valor_final = float(v) * multiplicador
        return valor_final
    except ValueError:
        return None


def _limpar_sujeira_string(s: str) -> str:
    """Remove pontuação comum no final de capturas de regex gulosos."""
    if not s: return s
    return s.strip(" \t\n\r?.!,;:\"'").strip()


def _intencao_busca_compra(texto: str) -> bool:
    texto = (texto or "").lower()
    
    # Se for intenção de criar algo, não é busca simples
    if _is_intencao_de_criacao(texto):
        return False
    
    # Se a pergunta pede agregação, análise ou envolve juros, ignorar busca simples para deixar para a IA
    if any(ex in texto for ex in ["quanto", "total", "juros", "taxa", "rendimento", "score"]):
        return False

    gatilhos = [
        "comprei",
        "comprou",
        "comprado",
        "compra de",
        "gastei com",
        "tem registro de",
        "procura",
        "buscar",
        "pesquisar",
    ]
    return any(g in texto for g in gatilhos)


def _extrair_termo_busca_compra(texto: str) -> str | None:
    texto = (texto or "").strip()
    if not texto:
        return None

    padroes = [
        r"(?:comprei|comprou|comprado|compra de|gastei com|tem registro de|procura(?:r)?|buscar|pesquisar)\s+(?:o|a|os|as|um|uma|uns|umas)?\s*(.+)$",
        r"(?:ache|acha|encontre|encontrou)\s+(?:o|a|os|as|um|uma|uns|umas)?\s*(.+)$",
    ]
    for padrao in padroes:
        match = re.search(padrao, texto, flags=re.IGNORECASE)
        if match:
            termo = match.group(1).strip(" \t\n\r?.!,;:\"'()").strip()
            if termo:
                return termo
    return None


def _buscar_compras_por_termo(db, usuario_id: int, termo: str, limite: int = 5) -> list[Lancamento]:
    if not termo:
        return []
    return (
        db.query(Lancamento)
        .filter(Lancamento.id_usuario == usuario_id)
        .filter(
            or_(
                Lancamento.descricao.ilike(f"%{termo}%"),
                Lancamento.itens.any(ItemLancamento.nome_item.ilike(f"%{termo}%")),
            )
        )
        .order_by(Lancamento.data_transacao.desc(), Lancamento.id.desc())
        .limit(limite)
        .all()
    )


def _formatar_busca_compras(lancamentos: list[Lancamento], termo: str) -> str:
    termo_fmt = escape(termo or "")
    if not lancamentos:
        return (
            f"Henrique, dei uma olhada geral no seu banco e não encontrei nenhum registro para <b>{termo_fmt}</b> este mês. "
            "Se você pagou em dinheiro ou esqueceu de anotar, quer que eu registre agora?"
        )

    linhas = [
        f"Encontrei esses registros para <b>{termo_fmt}</b>:",
        "",
    ]
    for lanc in lancamentos[:5]:
        data_txt = lanc.data_transacao.strftime("%d/%m/%Y") if getattr(lanc, "data_transacao", None) else "sem data"
        linhas.append(
            f"• {escape(lanc.descricao or 'Lançamento')} — <code>{_formatar_valor_brasileiro(abs(float(lanc.valor or 0)))}</code> em {data_txt}"
        )
    
    linhas.append("\n<i>Dica: Você pode ver o detalhamento completo no MiniApp!</i>")
    return "\n".join(linhas)


def _extrair_valor_regex(texto: str) -> float | None:
    """Extrai o primeiro valor numérico que parece monetário."""
    # Pega qualquer sequência de dígitos, pontos e vírgulas que pareça um número, 
    # opcionalmente seguido de mil/milhão
    match = re.search(r'(\d[\d.,]*)\s*(mil(?:h[õo]es|ão)?|k)?', texto, re.IGNORECASE)
    if match:
        v_str = match.group(1)
        suffix = match.group(2) or ""
        return _parse_br_money(v_str + " " + suffix)
    return None


def _detectar_e_extrair_acao_direta(texto: str) -> tuple[str, dict] | None:
    """
    Tenta detectar intenções de ação (Lançamento, Meta, Agendamento) via Regex.
    Retorna (nome_funcao, argumentos) ou None.
    
    DESATIVADO: O interceptor via regex estava capturando incorretamente intenções 
    complexas (como metas e limites) como se fossem lançamentos financeiros simples.
    Agora o Alfredo confia 100% no LLM para o roteamento (Function Calling), 
    garantindo precisão máxima.
    """
    return None

    # 2. LANÇAMENTO (Gastei, Paguei, Recebi, Lança, Comprei, Registra)
    # 2. LANÇAMENTO
    verbos = r'\b(?:gastei|paguei|recebi|lanç[ao]r?|registra?r?|coloque?i?|comprei|compras?|adiciona?r?|anota?r?|gastar|gastou|comprar|pagar|receber|recebeu)\b'
    fillers = r'(?:\s+(?:um|uma|o|a|os|as|do|da|no|na|em|com|de|valor|compra|gasto|despesa|receita|para|pra))*'

    # Padrao A: Verbo + (Fillers) + Valor + (reais/real opcional) + (Fillers preposicionais) + Descrição
    p_lanc_a = verbos + fillers + r'\s+' + valor_re + r'\s*(?:reais|real)?\s*(?:no|na|em|com|de|para|pra)?\s*(.+)'
    # Padrao B: Verbo + (Fillers) + Descrição + (Fillers) + Valor no final
    p_lanc_b = verbos + fillers + r'\s+(.+?)\s+(?:por|de|foi|valor de|custou|r\$?\s*)?\s*' + valor_re + r'\s*(?:reais|real)?$'
    
    # Lista de palavras que sugerem recorrência (devemos deixar para a IA lidar com Agendamentos de receitas/despesas)
    # Mas NÃO deve bloquear limites de orçamento (que também usam semanal/mensal)
    recorrencia_keywords = ["recorrente", "todo mês", "todo mes", "fixo", "todo dia"]
    if any(w in t for w in recorrencia_keywords) and "limite" not in t:
        # Tenta capturar agendamentos simples com parcelas (ex: "300 reais por 12 meses" ou "receita de 300 mensal por 12 meses")
        # Padrao mais flexível para capturar Valor e Parcelas
        p_agend = r'\b(?:agendamento|agendar?|recorrente)\b.*?' + valor_re + r'.*?(?:por|durante|são|vão ser)?\s*(\d+)\s+(m[êe]s(?:es)?|semana(?:s)?|dia(?:s)?|ano(?:s)?)'
        m_ag = re.search(p_agend, t)
        if m_ag:
            valor = _parse_br_money(m_ag.group(1) + " " + (m_ag.group(2) or ""))
            parcelas = int(m_ag.group(3))
            periodo = (m_ag.group(3) or "").lower()
            
            freq = "mensal"
            if "seman" in periodo: freq = "semanal"
            elif "dia" in periodo: freq = "diário"
            
            fn = "agendar_receita" if "recei" in t else "agendar_despesa"
            
            if valor:
                return fn, {
                    "valor": valor,
                    "frequencia": freq,
                    "descricao": "Agendamento Recorrente",
                    "data": datetime.now().strftime("%Y-%m-%d"),
                    "parcelas": parcelas,
                    "_origem": "regex"
                }
        
        # Fallback para agendamento sem parcelas explícitas no mesmo padrão
        p_agend_simples = r'\b(?:agendamento|agendar?|recorrente)\b.*?' + valor_re
        m_ag_s = re.search(p_agend_simples, t)
        if m_ag_s:
            valor = _parse_br_money(m_ag_s.group(1) + " " + (m_ag_s.group(2) or ""))
            fn = "agendar_receita" if "recei" in t else "agendar_despesa"
            if valor:
                return fn, {
                    "valor": valor,
                    "frequencia": "mensal",
                    "descricao": "Agendamento Recorrente",
                    "data": datetime.now().strftime("%Y-%m-%d"),
                    "_origem": "regex"
                }
        return None

    # Lista de palavras que caracterizam uma entrada
    palavras_entrada = ["recebi", "ganhei", "vendi", "salário", "salario", "reembolso", "receita", "entrada"]

    m_a = re.search(p_lanc_a, t)
    if m_a:
        valor = _parse_br_money(m_a.group(1) + " " + (m_a.group(2) or ""))
        if valor is not None:
            desc = _limpar_sujeira_string(m_a.group(3))
            tipo = "Entrada" if any(x in t for x in palavras_entrada) else "Saída"
            return "registrar_lancamento", {
                "valor": valor,
                "descricao": desc.capitalize(),
                "categoria": "Outros",
                "forma_pagamento": "Nao_informado",
                "tipo": tipo
            }
        
    m_b = re.search(p_lanc_b, t)
    if m_b:
        desc = _limpar_sujeira_string(m_b.group(1))
        valor = _parse_br_money(m_b.group(2) + " " + (m_b.group(3) or ""))
        if valor is not None:
            tipo = "Entrada" if any(x in t for x in palavras_entrada) else "Saída"
            return "registrar_lancamento", {
                "valor": valor,
                "descricao": desc.capitalize(),
                "categoria": "Outros",
                "forma_pagamento": "Nao_informado",
                "tipo": tipo
            }

    # 3. META (Meta de X para Y)
    # "Quero criar uma nova meta para comprar uma bicicleta elétrica. São 7.500 reais"
    p_meta = r'\b(?:criar?|nova|novo?|definir?|adiciona?r?)\b\s+meta\s+(?:para\s+)?(?:comprar\s+|ter\s+|um[aa]?\s+)?(.+?)\s+(?:de\s+|são\s+|valor\s+|no valor de\s+)?' + valor_re
    m_meta = re.search(p_meta, t)
    if m_meta:
        valor = _parse_br_money(m_meta.group(2) + " " + (m_meta.group(3) or ""))
        if valor is not None:
            desc = _limpar_sujeira_string(m_meta.group(1))
            desc = re.sub(r'^(?:a|o|um|uma|comprar|pagar|ter)\s+', '', desc, flags=re.IGNORECASE).capitalize()
            return "criar_meta", {"valor_alvo": valor, "descricao": desc}

    # 4. LIMITE (Limite de X em Y OU Limite em Y de X)
    # "Crie um limite semanal de 300 reais para alimentação"
    periodos_re = r'(diário|semanal|mensal|mensais|diária|semanais|anual)'
    p_limite_c = r'\blimite\s+' + periodos_re + r'\s+(?:de\s+)?' + valor_re + r'\s*(?:reais|real)?\s*(?:para|pra|em|na|de)?\s*(.+)'
    
    m_lim_c = re.search(p_limite_c, t)
    if m_lim_c:
        periodo = m_lim_c.group(1).lower()
        if "seman" in periodo: periodo = "semanal"
        elif "diár" in periodo or "diar" in periodo: periodo = "diário"
        else: periodo = "mensal"
        
        valor = _parse_br_money(m_lim_c.group(2) + " " + (m_lim_c.group(3) or ""))
        if valor is not None:
            cat = _limpar_sujeira_string(m_lim_c.group(4))
            return "definir_limite_orcamento", {"valor": valor, "categoria": cat.capitalize(), "periodo": periodo}

    # Fallback para os limites simples existentes
    p_limite_a = r'\b(?:definir?|criar?|novo?|limita?r?)\b\s+limite\s+(?:de\s+)?' + valor_re + r'\s*(?:reais|real)?\s*(?:para|pra|em|na|categoria)?\s*(.+)'
    p_limite_b = r'\b(?:definir?|criar?|novo?|limita?r?)\b\s+limite\s+(?:para|pra|em|na|categoria)?\s*(.+?)\s+(?:de|valor de|em|no valor de|r\$?\s*)?' + valor_re + r'\s*(?:reais|real)?$'
    
    m_lim_a = re.search(p_limite_a, t)
    if m_lim_a:
        valor = _parse_br_money(m_lim_a.group(1) + " " + (m_lim_a.group(2) or ""))
        if valor is not None:
            cat = _limpar_sujeira_string(m_lim_a.group(3))
            return "definir_limite_orcamento", {"valor": valor, "categoria": cat.capitalize()}

    m_lim_b = re.search(p_limite_b, t)
    if m_lim_b:
        cat = _limpar_sujeira_string(m_lim_b.group(1))
        valor = _parse_br_money(m_lim_b.group(2) + " " + (m_lim_b.group(3) or ""))
        if valor is not None:
            return "definir_limite_orcamento", {"valor": valor, "categoria": cat.capitalize()}

    return None


def _montar_resposta_local_alfredo(texto_usuario: str, texto_normalizado: str, db, usuario_db, saldo: float, entradas: float, saidas: float) -> str:
    # Este método é o fallback quando a IA falha.
    # Ele deve ser elegante e informativo, mantendo a persona do Alfredo.
    
    # --- INTELIGÊNCIA LOCAL PARA GASTOS (Fallback Robusto) ---
    texto_limpo = texto_normalizado.replace('"', '').replace("'", "").strip()
    gatilhos_gastos = ["quanto gastei", "quanto eu gastei", "meus gastos", "valor de", "total de", "quanto foi", "total em"]
    
    if any(x in texto_limpo for x in gatilhos_gastos):
        # Tenta extrair um termo de categoria do texto
        termo = None
        # Palavras para ignorar na busca do termo
        ignore = ["quanto", "gastei", "com", "essa", "esse", "esta", "nesta", "neste", "semana", "mes", "mês", "eu", "foi", "total", "valor", "de", "em"]
        for chunk in texto_limpo.split():
            chunk_limpo = chunk.strip("?.,!")
            if len(chunk_limpo) > 3 and chunk_limpo not in ignore:
                termo = chunk_limpo
                break
        
        if termo:
            # Busca no banco usando a lógica da ferramenta, mas de forma simplificada
            pm_inicio = datetime.now().replace(day=1, hour=0, minute=0, second=0)
            if "semana" in texto_normalizado:
                pm_inicio = datetime.now() - timedelta(days=datetime.now().weekday())
            
            soma = db.query(func.sum(Lancamento.valor)).filter(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.data_transacao >= pm_inicio,
                or_(
                    Lancamento.descricao.ilike(f"%{termo}%"),
                    Lancamento.categoria.has(Categoria.nome.ilike(f"%{termo}%"))
                )
            ).scalar() or 0
            
            if abs(soma) > 0:
                periodo_txt = "nesta semana" if "semana" in texto_normalizado else "neste mês"
                return (
                    f"📊 <b>Análise Rápida (Modo de Segurança)</b>\n\n"
                    f"Identifiquei que você gastou <code>{_formatar_valor_brasileiro(abs(float(soma)))}</code> com <b>{termo.capitalize()}</b> {periodo_txt}.\n\n"
                    f"<i>Nota: Estou operando em modo simplificado devido a uma instabilidade momentânea nos meus servidores de IA.</i>"
                )

    if _intencao_contas(texto_normalizado):
        return _resumo_contas_local(db, usuario_db.id)

    if _intencao_comparacao_financeira(texto_normalizado):
        return _resumo_comparacao_local(db, usuario_db.id)

    if _intencao_previsao_financeira(texto_normalizado):
        return _resumo_previsao_local(db, usuario_db.id, saldo, entradas, saidas)

    if _intencao_alerta_financeiro(texto_normalizado):
        return _resumo_alerta_local(db, usuario_db.id)

    if _intencao_analise_gastos(texto_normalizado):
        return _resumo_analise_gastos_local(db, usuario_db.id)

    if _intencao_consultoria_financeira(texto_normalizado):
        return _resumo_consultoria_local(db, usuario_db.id, saldo, entradas, saidas)

    if _intencao_busca_compra(texto_normalizado):
        termo = _extrair_termo_busca_compra(texto_usuario) or texto_usuario
        compras = _buscar_compras_por_termo(db, usuario_db.id, termo)
        return _formatar_busca_compras(compras, termo)

    if _intencao_ultimo_lancamento(texto_normalizado):
        ultimo = _buscar_ultimo_lancamento_sem_futuro(db, usuario_db.id)
        if ultimo:
            return _formatar_lancamento_card(ultimo)

    if _intencao_saldo(texto_normalizado):
        return _resumo_saldo_local(saldo, entradas, saidas)

    if _intencao_metas(texto_normalizado):
        return _resumo_metas_local(db, usuario_db.id)

    if _intencao_categoria_mais_gasto(texto_normalizado):
        top_categorias = _resumo_categoria_gastos(db, usuario_db.id, limite=5)
        if top_categorias:
            linhas = [
                "📊 <b>Principais Categorias de Gasto</b>\n",
                f"A categoria que mais pesou foi <b>{escape(top_categorias[0][0])}</b>, com um total de <code>{_formatar_valor_brasileiro(top_categorias[0][1])}</code>.\n",
                "<b>Top 5 categorias:</b>"
            ]
            for nome, valor in top_categorias:
                linhas.append(f"• {escape(nome)}: <code>{_formatar_valor_brasileiro(valor)}</code>")
            return "\n".join(linhas)

    if _intencao_forma_pagamento_mais_usada(texto_normalizado):
        forma_top, qtd_top, base_util = _forma_pagamento_mais_usada(db, usuario_db.id)
        if forma_top:
            return (
                "💳 <b>Preferências de Pagamento</b>\n\n"
                f"Sua forma de pagamento mais utilizada é o <b>{escape(forma_top)}</b>, "
                f"presente em {qtd_top} dos seus últimos {base_util} lançamentos."
            )

    if _intencao_resumo_semana(texto_normalizado):
        return _resumo_semana_local(db, usuario_db.id)

    if _intencao_resumo_mes(texto_normalizado):
        return _resumo_mes_local(db, usuario_db.id)

    # Se nada bater, retorna um resumo geral elegante
    return (
        "🤖 <b>Resumo dos Seus Números</b>\n\n"
        f"• <b>Saldo Disponível:</b> <code>{_formatar_valor_brasileiro(saldo)}</code>\n"
        f"• <b>Entradas:</b> <code>{_formatar_valor_brasileiro(entradas)}</code>\n"
        f"• <b>Saídas:</b> <code>{_formatar_valor_brasileiro(saidas)}</code>\n\n"
        "Como posso ajudar agora?"
    )


def _deve_responder_localmente(texto_normalizado: str) -> bool:
    """
    Atalho defensivo para comandos de status super objetivos.
    DESATIVADO: Agora priorizamos a IA para todas as consultas de saldo, contas e metas
    para garantir respostas humanizadas e contextuais.
    O motor local agora serve apenas como fallback de segurança caso a IA falhe.
    """
    return False



def _resumo_contas_local(db, usuario_id: int) -> str:
    agendamentos = (
        db.query(Agendamento)
        .filter(
            Agendamento.id_usuario == usuario_id,
            Agendamento.ativo.is_(True),
        )
        .order_by(Agendamento.proxima_data_execucao.asc(), Agendamento.id.asc())
        .limit(20)
        .all()
    )
    lembretes = (
        db.query(Lembrete)
        .filter(
            Lembrete.id_usuario == usuario_id,
            Lembrete.ativo.is_(True),
        )
        .order_by(Lembrete.proxima_data_execucao.asc(), Lembrete.id.asc())
        .limit(20)
        .all()
    )
    hoje = datetime.now().date()
    fim_semana = hoje + timedelta(days=(6 - hoje.weekday()))
    vencidas: list[str] = []
    hoje_itens: list[str] = []
    semana_itens: list[str] = []

    for ag in agendamentos:
        data_ag = ag.proxima_data_execucao.date() if getattr(ag, "proxima_data_execucao", None) else None
        if not data_ag:
            continue
        item = f"{escape(ag.descricao)} (<code>{_formatar_valor_brasileiro(float(ag.valor or 0))}</code>) em {data_ag.strftime('%d/%m/%Y')}"
        if data_ag < hoje:
            vencidas.append(item)
        elif data_ag == hoje:
            hoje_itens.append(item)
        elif hoje < data_ag <= fim_semana:
            semana_itens.append(item)

    for lembrete in lembretes:
        data_ag = getattr(lembrete, "proxima_data_execucao", None)
        if not data_ag:
            continue
        valor_txt = (
            f" (<code>{_formatar_valor_brasileiro(float(lembrete.valor or 0))}</code>)"
            if getattr(lembrete, "valor", None) is not None else ""
        )
        item = f"{escape(lembrete.descricao)}{valor_txt} em {data_ag.strftime('%d/%m/%Y')}"
        if data_ag == hoje:
            hoje_itens.append(item)
        elif hoje < data_ag <= fim_semana:
            semana_itens.append(item)

    if not agendamentos and not lembretes:
        return (
            "✅ <b>Tudo em dia!</b>\n\n"
            "Não encontrei compromissos pendentes no momento."
        )

    linhas = ["🗓️ <b>Compromissos Financeiros</b>\n"]

    if hoje_itens:
        linhas.append(f"⚠️ <b>Vencendo hoje:</b> {len(hoje_itens)}")
        for item in hoje_itens[:3]:
            linhas.append(f"• {item}")
        linhas.append("")

    if vencidas:
        linhas.append(f"🚨 <b>Atrasados:</b> {len(vencidas)}")
        for item in vencidas[:3]:
            linhas.append(f"• {item}")
        linhas.append("")

    if semana_itens:
        linhas.append(f"📅 <b>Até o fim da semana:</b> {len(semana_itens)}")
        for item in semana_itens[:3]:
            linhas.append(f"• {item}")
        linhas.append("")

    linhas.append("💡 <i>Organizar o fluxo para essas datas garante que seu saldo permaneça saudável.</i>")
    return "\n".join(linhas)


def _resumo_comparacao_local(db, usuario_id: int) -> str:
    hoje = datetime.now()
    inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mes_anterior_inicio = (inicio_mes - timedelta(days=1)).replace(day=1)
    mes_anterior_fim = inicio_mes - timedelta(microseconds=1)

    lanc_mes = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_id, Lancamento.data_transacao >= inicio_mes).all()
    _, sai_mes = _sum_consistente(lanc_mes)

    lanc_anterior = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_id, Lancamento.data_transacao >= mes_anterior_inicio, Lancamento.data_transacao <= mes_anterior_fim).all()
    _, sai_ant = _sum_consistente(lanc_anterior)
    
    delta = sai_mes - sai_ant
    delta_pct = 0.0 if sai_ant <= 0 else (delta / sai_ant) * 100.0

    if sai_mes > sai_ant:
        status = f"⚠️ Henrique, notei que seus gastos estão <b>{delta_pct:.1f}% acima</b> do mês passado. Quer que eu te ajude a ver onde está a diferença?"
    elif sai_mes < sai_ant:
        status = f"✅ Excelente! Você reduziu seus gastos em <b>{abs(delta_pct):.1f}%</b> comparado ao mês passado. Ótimo progresso!"
    else:
        status = "📊 Seus gastos estão bem equilibrados em relação ao mês passado."

    return (
        f"🔍 <b>Comparativo Mensal</b>\n\n"
        f"• <b>Este Mês:</b> <code>{_formatar_valor_brasileiro(sai_mes)}</code>\n"
        f"• <b>Mês Passado:</b> <code>{_formatar_valor_brasileiro(sai_ant)}</code>\n\n"
        f"{status}"
    )


def _resumo_alerta_local(db, usuario_id: int) -> str:
    agora = datetime.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lanc_mes = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_id, Lancamento.data_transacao >= inicio_mes).all()
    ent_mes, sai_mes = _sum_consistente(lanc_mes)
    saldo_mes = ent_mes - sai_mes
    
    if saldo_mes < 0:
        titulo = "🚨 <b>Alerta de Atenção Máxima</b>"
        msg = f"Seu mês está fechando no negativo em <code>{_formatar_valor_brasileiro(abs(saldo_mes))}</code>."
    elif sai_mes > ent_mes * 0.85 and ent_mes > 0:
        titulo = "⚠️ <b>Alerta de Margem Estreita</b>"
        msg = "Seus gastos já consumiram mais de 85% das suas entradas deste mês."
    else:
        titulo = "✅ <b>Saúde Financeira sob Controle</b>"
        msg = "Seu padrão de gastos atual está dentro de uma margem segura."

    return f"{titulo}\n\n{msg}"


def _resumo_previsao_local(db, usuario_id: int, saldo: float, entradas: float, saidas: float) -> str:
    agora = datetime.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lanc_mes = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_id, Lancamento.data_transacao >= inicio_mes).all()
    ent_mes, sai_mes = _sum_consistente(lanc_mes)
    
    dias_passados = max(1, agora.day)
    dias_no_mes = monthrange(agora.year, agora.month)[1]
    dias_restantes = max(1, dias_no_mes - agora.day)
    
    media_diaria_saida = sai_mes / dias_passados
    proj_saida = media_diaria_saida * dias_no_mes
    saldo_projetado = ent_mes - proj_saida
    
    limite_diario = max(0, (ent_mes - sai_mes)) / dias_restantes

    if saldo_projetado < 0:
        status = f"🔴 <b>Atenção:</b> No ritmo atual, você pode fechar o mês com um déficit de <code>{_formatar_valor_brasileiro(abs(saldo_projetado))}</code>."
    elif saldo_projetado > 0:
        status = f"🟢 <b>Tudo certo:</b> Você está em rota para fechar o mês com <code>{_formatar_valor_brasileiro(saldo_projetado)}</code> de folga!"
    else:
        status = "➡️ <b>Equilíbrio:</b> Você está fechando exatamente o que ganha."

    return (
        f"📊 <b>Previsão de Fechamento</b>\n\n"
        f"{status}\n\n"
        f"💰 <b>Gasto Médio:</b> <code>{_formatar_valor_brasileiro(media_diaria_saida)}</code>/dia\n"
        f"🎯 <b>Para fechar no azul:</b> Gaste no máximo <code>{_formatar_valor_brasileiro(limite_diario)}</code>/dia"
    )


def _resumo_analise_gastos_local(db, usuario_id: int) -> str:
    ignore_ids = _get_subcats_ignore_ids(db)
    lancamentos = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_id).order_by(Lancamento.id.desc()).limit(180).all()
    saidas_lanc = _filtrar_saidas_reais(lancamentos, ignore_ids)
    top_categorias = _resumo_categoria_gastos_por_lancamentos(saidas_lanc, ignore_ids=ignore_ids, limite=3)
    maior = max(saidas_lanc, key=lambda l: abs(float(l.valor or 0)), default=None)

    if not top_categorias:
        return "Henrique, ainda não tenho gastos categorizados suficientes este mês para fazer uma análise. Continue registrando para eu te ajudar!"

    linhas = ["🧐 <b>Análise de Impacto</b>\n"]
    for cat, val in top_categorias:
        linhas.append(f"• <b>{cat}:</b> <code>{_formatar_valor_brasileiro(val)}</code>")
    
    if maior:
        linhas.append(f"\nSeu maior gasto individual recente foi <b>{escape(maior.descricao)}</b> (<code>{_formatar_valor_brasileiro(abs(float(maior.valor)))}</code>).")
    
    linhas.append("\n<i>Dica: No MiniApp você consegue ver o gráfico completo e onde economizar!</i>")
    return "\n".join(linhas)


def _resumo_consultoria_local(db, usuario_id: int, saldo: float, entradas: float, saidas: float) -> str:
    top_categorias = _resumo_categoria_gastos(db, usuario_id, limite=3)
    res_mes = entradas - saidas
    
    if res_mes < 0:
        status = "⚠️ Henrique, seu balanço do mês está no negativo. É um bom momento para revisar as categorias mais pesadas e evitar gastos não essenciais por uns dias."
    else:
        status = "✅ Henrique, suas contas estão equilibradas este mês! Você está gastando menos do que recebe, o que é ótimo para sua saúde financeira."

    linhas = [status, ""]
    if top_categorias:
        nome_top, valor_top = top_categorias[0]
        linhas.append(f"Hoje, sua maior alavanca de gasto é <b>{escape(nome_top)}</b> ({_formatar_valor_brasileiro(valor_top)}).")
    
    linhas.append("\n<i>No MiniApp eu preparei um dashboard detalhado para você planejar os próximos meses!</i>")
    return "\n".join(linhas)


def _resumo_semana_local(db, usuario_id: int) -> str:
    agora = datetime.now()
    inicio_semana = agora - timedelta(days=6)
    lancamentos = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_id, Lancamento.data_transacao >= inicio_semana).all()
    ent_sem, sai_sem = _sum_consistente(lancamentos)
    
    msg = f"Nesta semana você teve <code>{_formatar_valor_brasileiro(sai_sem)}</code> em saídas e <code>{_formatar_valor_brasileiro(ent_sem)}</code> em entradas."
    if sai_sem > ent_sem:
        status = "\n\n⚠️ O fluxo da semana está negativo. Recomendo segurar um pouco os gastos variáveis até domingo."
    else:
        status = "\n\n✅ Boa! Você está fechando a semana no azul. Continue assim!"
        
    return f"📅 <b>Resumo da Semana</b>\n\n{msg}{status}"


def _resumo_saldo_local(saldo: float, entradas: float, saidas: float) -> str:
    res_mes = round(entradas - saidas, 2)
    status_mes = "🟢" if res_mes >= 0 else "🔴"
    status_pat = "🟢" if saldo >= 0 else "🔴"
    
    return (
        f"💰 <b>Resumo das Suas Contas</b>\n\n"
        f"<b>Mês Atual:</b>\n"
        f"• Entradas: <code>{_formatar_valor_brasileiro(entradas)}</code>\n"
        f"• Saídas: <code>{_formatar_valor_brasileiro(saidas)}</code>\n"
        f"• Resultado: <code>{_formatar_valor_brasileiro(res_mes)}</code> {status_mes}\n\n"
        f"<b>Geral (Patrimônio):</b>\n"
        f"• Disponível Total: <code>{_formatar_valor_brasileiro(saldo)}</code> {status_pat}\n\n"
        f"<i>Os números acima ignoram transferências internas para refletir seus gastos reais.</i>"
    )


def _resumo_metas_local(db, usuario_id: int) -> str:
    objetivos_ativos = db.query(Objetivo).filter(
        Objetivo.id_usuario == usuario_id,
        func.coalesce(Objetivo.valor_atual, 0) < func.coalesce(Objetivo.valor_meta, 0)
    ).order_by(Objetivo.criado_em.desc(), Objetivo.id.desc()).all()

    if not objetivos_ativos:
        return "🎯 <b>Metas</b>\n\nVocê não tem metas ativas no momento."

    linhas = ["🎯 <b>Progresso das Metas</b>\n"]
    for obj in objetivos_ativos[:3]:
        v_meta = float(obj.valor_meta or 0)
        v_atual = float(obj.valor_atual or 0)
        perc = (v_atual / v_meta * 100) if v_meta > 0 else 0
        linhas.append(f"• <b>{escape(obj.descricao)}:</b> {perc:.0f}% (<code>{_formatar_valor_brasileiro(v_atual)}</code> de <code>{_formatar_valor_brasileiro(v_meta)}</code>)")

    return "\n".join(linhas)


def _resumo_mes_local(db, usuario_id: int) -> str:
    agora = datetime.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lanc_mes = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_id, Lancamento.data_transacao >= inicio_mes).all()
    ent_mes, sai_mes = _sum_consistente(lanc_mes)
    res_mes = ent_mes - sai_mes

    status = "🟢 Você está no azul" if res_mes >= 0 else "🔴 Você está no vermelho"

    return (
        f"📊 <b>Balanço de {agora.strftime('%B')}</b>\n\n"
        f"Até agora, você recebeu <code>{_formatar_valor_brasileiro(ent_mes)}</code> e gastou <code>{_formatar_valor_brasileiro(sai_mes)}</code>.\n\n"
        f"<b>Resultado:</b> <code>{_formatar_valor_brasileiro(res_mes)}</code>\n"
        f"{status}. No MiniApp você vê o detalhamento por categoria!"
    )

def _formatar_lancamento_card(lanc: Lancamento) -> str:
    descricao = escape(lanc.descricao or "Lançamento")
    categoria = escape(lanc.categoria.nome if lanc.categoria else "Sem categoria")
    pagamento = escape(lanc.forma_pagamento or "Não informado")
    tipo = escape(lanc.tipo or "Não informado")
    data_formatada = lanc.data_transacao.strftime("%d/%m/%Y")
    hora_formatada = lanc.data_transacao.strftime("%H:%M")
    valor = _formatar_valor_brasileiro(abs(float(lanc.valor or 0)))
    tipo_emoji = "🟢" if str(lanc.tipo).lower().startswith(("entr", "recei")) else "🔴"

    return (
        f"📌 <b>Seu último lançamento</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{tipo_emoji} <b>{descricao}</b>\n\n"
        f"<b>💰 Valor:</b> <code>{valor}</code>\n"
        f"<b>📅 Data:</b> {data_formatada} às {hora_formatada}\n"
        f"<b>📂 Categoria:</b> {categoria}\n"
        f"<b>💳 Pagamento:</b> {pagamento}\n"
        f"<b>🏷️ Tipo:</b> {tipo}"
    )


def _intencao_ultimo_lancamento(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    return any(
        frase in texto
        for frase in [
            "último lançamento",
            "ultimo lançamento",
            "ultimo lancamento",
            "última transação",
            "ultima transacao",
            "última compra",
            "ultima compra",
            "última despesa",
            "ultima despesa",
            "última receita",
            "ultima receita",
            "lançamento mais recente",
            "lancamento mais recente",
            "último gasto",
            "ultimo gasto",
        ]
    )


def _intencao_saldo(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    return any(
        p in texto
        for p in [
            "saldo",
            "quanto tenho",
            "meu saldo",
            "saldo total",
            "quanto sobrou",
            "quanto eu tenho hoje",
            "quanto tenho hoje",
            "quanto eu tenho na conta",
            "na conta agora",
            "disponível",
            "disponivel",
            "positivo ou negativo",
            "tô no positivo",
            "to no positivo",
            "tô no negativo",
            "to no negativo",
            "salário",
            "salario",
        ]
    )


def _intencao_metas(texto: str) -> bool:
    texto = (texto or "").lower()
    # Se contém verbos de ação para criação, deixa passar para a IA processar
    if _is_intencao_de_criacao(texto):
        return False

    return any(
        p in texto
        for p in [
            "meta ativa",
            "meta ativas",
            "metas ativas",
            "minhas metas",
            "quais metas",
            "tenho metas",
            "metas",
            "guardando dinheiro",
            "guardar dinheiro",
            "economizar",
            "economia",
            "objetivo",
            "caminho certo",
            "falhando",
            "acelerar minha meta",
            "quanto falta pra minha meta",
            "quanto preciso guardar por mês",
            "quanto preciso guardar por mes",
            "chegar lá",
            "chegar la",
            "vale a pena continuar com essa meta",
            "vale a pena eu continuar com essa meta",
        ]
    )

def _intencao_contas(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    # Desambiguação: "Quanto tenho na conta" NÃO é intenção de listar boletos (contas a pagar)
    if "quanto" in texto and "conta" in texto:
        return False
    if "saldo" in texto:
        return False

    sinais = [
        "minhas contas",
        "venc",
        "contas a pagar",
        "contas do mes",
        "boletos",
        "atrasad",
        "aluguel",
        "luz",
        "internet",
        "fixas",
        "comprometido",
        "falta pagar",
        "sobra depois das contas",
        "o que eu ainda preciso pagar",
        "já paguei",
        "ja paguei",
        "me lembra do que preciso pagar",
    ]
    return any(s in texto for s in sinais)


def _intencao_comparacao_financeira(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    sinais = [
        "compar",
        "se compara",
        "mês passado",
        "mes passado",
        "mês anterior",
        "mes anterior",
        "mudou",
        "evoluindo",
        "piorando",
        "aumentou",
        "distribuído",
        "distribuido",
        "tendência",
        "tendencia",
        "mesma coisa",
    ]
    return any(s in texto for s in sinais)


def _intencao_alerta_financeiro(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    sinais = [
        "alerta",
        "risco",
        "preocup",
        "vermelho",
        "perigoso",
        "fora do normal",
        "suspeito",
        "anormal",
        "estourar",
        "mais do que deveria",
        "mais do que ganho",
        "gasto fora do padrão",
        "fora do padrão",
        "fora do padrao",
        "padrão atual",
        "precisa de atenção",
        "atenção agora",
        "sem dinheiro",
        "ficar sem grana",
        "gastando muito",
        "gastei muito",
        "mais do que o normal",
        "fora do meu comportamento comum",
        "compromete meu mês",
        "aceitável pra mim",
        "dentro do esperado",
    ]
    return any(s in texto for s in sinais)


def _intencao_previsao_financeira(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    sinais = [
        "se eu continuar",
        "quanto posso gastar",
        "limite seguro",
        "vou ficar sem dinheiro",
        "quanto preciso reduzir",
        "até o fim do mês",
        "fechar o mês",
        "impactar",
        "se eu gastar",
        "posso fazer essa compra",
        "apertar o orçamento",
        "quanto por dia",
        "gastar hoje",
        "gastando hoje",
        "sem me ferrar",
        "melhor segurar",
        "dar pra eu comprar",
        "dá pra eu comprar",
        "fechar no vermelho",
        "risco de fechar",
        "fechar esse mês",
        "fechar este mês",
        "fechar o mes",
        "fechar esse mes",
        "fechar este mes",
    ]
    return any(s in texto for s in sinais)


def _intencao_analise_gastos(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    sinais = [
        "onde eu mais estou gastando",
        "categoria mais pesa",
        "cortar agora",
        "gasto fora do normal",
        "gastos desnecessários",
        "gastos desnecessarios",
        "ifood",
        "lanche",
        "besteira",
        "gastos invisíveis",
        "gastos invisiveis",
        "maior gasto recente",
        "padrões de desperdício",
        "padroes de desperdicio",
        "desperdício",
        "desperdicio",
        "onde gasto dinheiro",
        "me mostra meus gastos",
        "acabando rápido",
        "acabando rapido",
        "meu dinheiro tá acabando",
        "meu dinheiro ta acabando",
        "comprando por impulso",
        "padrão ruim",
        "padrao ruim",
        "meus hábitos",
        "meus habitos",
        "meu estilo de vida",
        "momento eu mais gasto",
        "quais dias eu mais gasto",
        "quais gastos são desnecessários",
        "quais gastos sao desnecessarios",
        "por que meu dinheiro está acabando tão rápido",
        "por que meu dinheiro esta acabando tao rapido",
        "em que momentos eu mais gasto",
        "tem algum hábito financeiro me prejudicando",
        "tem algum habito financeiro me prejudicando",
        "onde estou me sabotando financeiramente",
    ]
    return any(s in texto for s in sinais)


def _intencao_consultoria_financeira(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    sinais = [
        "se você fosse meu gerente",
        "se voce fosse meu gerente",
        "maior erro",
        "3 ações práticas",
        "3 acoes praticas",
        "plano simples",
        "organizar minha vida financeira",
        "vivendo acima",
        "decisão financeira",
        "decisao financeira",
        "ignorando",
        "me dá a real",
        "me fala a real",
        "o que eu deveria fazer agora",
        "o que eu mudaria",
        "onde posso melhorar",
        "tô meio perdido",
        "to meio perdido",
        "me ajuda a organizar",
        "tô sem dinheiro",
        "to sem dinheiro",
        "fui irresponsável",
        "fui irresponsavel",
        "tô indo bem ou mal",
        "to indo bem ou mal",
        "tô preocupado",
        "to preocupado",
        "confere isso",
        "sem filtro",
        "meu padrão de gastos tá saudável",
        "meu padrao de gastos ta saudável",
        "meu padrão de gastos ta saudável",
        "eu deveria ter feito essa compra",
        "esse gasto foi consciente ou impulsivo",
        "isso tá alinhado com minhas metas",
        "isso esta alinhado com minhas metas",
    ]
    return any(s in texto for s in sinais)


def _intencao_categorizar_sem_categoria(texto: str) -> bool:
    texto = (texto or "").lower()
    gatilhos = [
        "categorize todos",
        "categoriza todos",
        "categorizar todos",
        "categorizar os lançamentos",
        "categorizar os lancamentos",
        "sem categoria",
        "lançamentos sem categoria",
        "lancamentos sem categoria",
    ]
    return ("categoriz" in texto) and any(g in texto for g in gatilhos)


def _intencao_categoria_mais_gasto(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    return (
        ("categoria" in texto and "gasto" in texto and "mais" in texto)
        or "categoria eu mais" in texto
        or "categoria de gasto mais alta" in texto
    )


def _intencao_forma_pagamento_mais_usada(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    sinais_pagamento = ["forma de pagamento", "pagamento", "crédito", "credito", "pix", "débito", "debito"]
    sinais_uso = ["mais", "utilizo", "uso", "utilizada", "utilizo"]
    return any(s in texto for s in sinais_pagamento) and any(s in texto for s in sinais_uso)


def _intencao_resumo_mes(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    return any(
        s in texto
        for s in [
            "resumo do meu mes",
            "resumo do meu mês",
            "resumo do mês",
            "resumo mes",
            "fechamento do mês",
            "fechamento do mes",
            "como estão minhas finanças esse mês",
            "como estao minhas finanças esse mês",
            "como estão minhas finanças",
            "resumo geral",
            "geral de tudo",
            "me dá um resumo geral",
            "me da um resumo geral",
        ]
    )


def _intencao_resumo_semana(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    # Deixamos a IA cuidar de resumos para que a resposta seja personalizada
    return False


def _intencao_agendamentos(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    return any(s in texto for s in ["agendamentos", "lancamentos programados", "lançamentos programados", "recorrente", "recorrentes", "para pagar de forma recorrente"])


def _intencao_score_financeiro(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    return "score" in texto and any(s in texto for s in ["financeir", "saúde financeira", "saude financeira"])


def _intencao_cotacao_externa(texto: str) -> bool:
    texto = (texto or "").lower()
    if _is_intencao_de_criacao(texto):
        return False
    return any(s in texto for s in ["valor do dolar", "valor do dólar", "cotação", "cotacao", "crypto", "criptomoeda", "bitcoin", "ethereum"])


async def _categorizar_lancamentos_sem_categoria_async(db, usuario_id: int) -> tuple[int, int]:
    pendentes = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.id_categoria.is_(None),
        )
        .order_by(Lancamento.id.asc())
        .all()
    )

    atualizados = 0
    ainda_pendentes = []
    for lanc in pendentes:
        descricao = (lanc.descricao or "").strip().lower()
        if not descricao:
            continue
        tipo_transacao = "Receita" if str(lanc.tipo).lower().startswith(("entr", "recei")) else "Despesa"
        cat_id, subcat_id = _categorizar_com_mapa_inteligente(descricao, tipo_transacao, db)
        if cat_id:
            lanc.id_categoria = cat_id
            lanc.id_subcategoria = subcat_id
            atualizados += 1
        else:
            ainda_pendentes.append(lanc)

    if ainda_pendentes and config.GROQ_API_KEY:
        try:
            categorias = db.query(Categoria).all()
            cat_nomes = [c.nome for c in categorias if c.nome]
            cat_map_nome_para_id = {c.nome.lower(): c.id for c in categorias if c.nome}

            itens_para_categorizar = [
                {"id": idx, "descricao": l.descricao, "valor": float(l.valor or 0)} 
                for idx, l in enumerate(ainda_pendentes)
            ]
            
            prompt = f"Você é um categorizador financeiro automático. Analise e categorize as transações.\nCATEGORIAS PERMITIDAS: {json.dumps(cat_nomes, ensure_ascii=False)}\nTRANSAÇÕES: {json.dumps(itens_para_categorizar, ensure_ascii=False)}\nRetorne APENAS um JSON onde as chaves são os 'id' numéricos e os valores são os nomes EXATOS das categorias. Sem markdown."
            messages = [
                {"role": "system", "content": "You are a JSON-only bot. Return strictly a raw JSON object and nothing else."},
                {"role": "user", "content": prompt}
            ]
            resp = await _groq_chat_completion_async(messages)
            content = resp["choices"][0]["message"]["content"]
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                for idx_str, cat_nome in result.items():
                    try:
                        idx = int(idx_str)
                        cat_id = cat_map_nome_para_id.get(str(cat_nome).strip().lower())
                        if cat_id is not None:
                            ainda_pendentes[idx].id_categoria = cat_id
                            atualizados += 1
                    except (ValueError, KeyError):
                        pass
        except Exception as e:
            logger.warning("Groq categorização lote falhou no fallback: %s", e)

    if atualizados:
        db.commit()
    return atualizados, len(pendentes)


def _resumo_categoria_gastos(db, usuario_id: int, limite: int = 5) -> list[tuple[str, float]]:
    ignore_ids = _get_subcats_ignore_ids(db)
    lancamentos = (
        db.query(Lancamento)
        .filter(Lancamento.id_usuario == usuario_id)
        .order_by(Lancamento.id.desc())
        .limit(300)
        .all()
    )
    return _resumo_categoria_gastos_por_lancamentos(lancamentos, ignore_ids=ignore_ids, limite=limite)


def _resumo_categoria_gastos_por_lancamentos(lancamentos: list[Lancamento], ignore_ids: list[int] = None, limite: int = 5) -> list[tuple[str, float]]:
    categorias: dict[str, float] = {}
    for lanc in lancamentos:
        if str(lanc.tipo).lower().startswith(("entr", "recei")):
            continue
        # Ignora se for subcategoria de duplicidade
        if ignore_ids and lanc.id_subcategoria in ignore_ids:
            continue
            
        nome = lanc.categoria.nome if getattr(lanc, "categoria", None) and lanc.categoria else "Sem categoria"
        categorias[nome] = categorias.get(nome, 0.0) + abs(float(lanc.valor or 0))
    return sorted(categorias.items(), key=lambda x: x[1], reverse=True)[:limite]


def _forma_pagamento_mais_usada(db, usuario_id: int) -> tuple[str | None, int, int]:
    lancamentos = (
        db.query(Lancamento)
        .filter(Lancamento.id_usuario == usuario_id)
        .order_by(Lancamento.id.desc())
        .limit(400)
        .all()
    )
    contagem: dict[str, int] = {}
    total = 0
    for lanc in lancamentos:
        forma = _normalizar_forma_pagamento(lanc.forma_pagamento)
        if forma == "Nao_informado":
            continue
        contagem[forma] = contagem.get(forma, 0) + 1
        total += 1
    if not contagem:
        return None, 0, len(lancamentos)
    forma_top, qtd = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[0]
    return forma_top, qtd, total


def _buscar_ultimo_lancamento_sem_futuro(db, usuario_id: int) -> Lancamento | None:
    """
    Regra de prioridade:
    1) Busca o último inserido de hoje.
    2) Se não houver, busca o último inserido de ontem.
    3) Se não houver, busca o último inserido de qualquer dia <= hoje.
    Nunca retorna transações futuras.
    """
    agora = datetime.now()
    hoje_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    hoje_fim = agora.replace(hour=23, minute=59, second=59, microsecond=999999)
    ontem_inicio = hoje_inicio - timedelta(days=1)
    ontem_fim = hoje_inicio - timedelta(microseconds=1)

    base = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao <= hoje_fim,
        )
        .order_by(Lancamento.id.desc())
    )

    hoje = base.filter(Lancamento.data_transacao >= hoje_inicio).first()
    if hoje:
        return hoje

    ontem = base.filter(
        Lancamento.data_transacao >= ontem_inicio,
        Lancamento.data_transacao <= ontem_fim,
    ).first()
    if ontem:
        return ontem

    return base.first()


def _formatar_metas_ativas(objetivos: list[Objetivo]) -> str:
    if not objetivos:
        return (
            "🎯 <b>Metas ativas</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Não encontrei metas ativas no seu banco neste momento."
        )

    linhas = ["🎯 <b>Metas ativas</b>", "━━━━━━━━━━━━━━━━━━", ""]
    for objetivo in objetivos[:8]:
        valor_meta = float(objetivo.valor_meta or 0)
        valor_atual = float(objetivo.valor_atual or 0)
        progresso = 0.0 if valor_meta <= 0 else min(100.0, max(0.0, (valor_atual / valor_meta) * 100.0))
        prazo = objetivo.data_meta.strftime("%d/%m/%Y") if objetivo.data_meta else "sem prazo"
        linhas.append(
            f"• <b>{escape(objetivo.descricao or 'Meta')}</b>\n"
            f"  { _formatar_valor_brasileiro(valor_atual) } de { _formatar_valor_brasileiro(valor_meta) }"
            f" ({progresso:.0f}%) | prazo: {escape(prazo)}"
        )
    return "\n".join(linhas)


def _carregar_historico_recente_ia(db, user_id: int, limite: int = 5) -> list[dict]:
    """Busca as últimas trocas de mensagens do usuário para dar memória à IA."""
    from models import Base
    # Importação dinâmica para evitar circularidade se necessário
    from sqlalchemy import text
    
    try:
        # Busca histórico ordenado pelo ID decrescente (mais recentes primeiro)
        # Retorna lista de dicts no formato esperado pela OpenAI/Groq/Gemini
        rows = db.execute(text(
            "SELECT user_message, ai_response FROM chat_history "
            "WHERE id_usuario = :uid ORDER BY id DESC LIMIT :lim"
        ), {"uid": user_id, "lim": limite}).fetchall()
        
        history = []
        # Inverte para que fiquem em ordem cronológica (antiga -> nova)
        for row in reversed(rows):
            if row[0]: # user_message
                history.append({"role": "user", "content": row[0]})
            if row[1]: # ai_response
                history.append({"role": "assistant", "content": row[1]})
        return history
    except Exception as e:
        logger.warning(f"Erro ao carregar histórico do chat: {e}")
        return []

def _registrar_historico_ia(db, user_id: int, user_msg: str, ai_msg: str):
    """Salva a interação no banco para memória futura."""
    from sqlalchemy import text
    try:
        db.execute(text(
            "INSERT INTO chat_history (id_usuario, user_message, ai_response, created_at) "
            "VALUES (:uid, :umsg, :amsg, :now)"
        ), {
            "uid": user_id, 
            "umsg": user_msg[:4000], # Limite de segurança
            "amsg": ai_msg[:4000], 
            "now": datetime.now(timezone.utc)
        })
        db.commit()
    except Exception as e:
        logger.warning(f"Erro ao registrar histórico do chat: {e}")

def _sum_consistente(lista):
    """Soma consistente de lançamentos (Sincronizado com dashboard_app.py)"""
    e = 0.0
    s = 0.0
    for l in lista:
        t = str(l.tipo).lower()
        if t in ["transferencia", "transferência", "transfer"]: continue
        v = abs(float(l.valor or 0))
        if t.startswith(("entr", "recei")): e += v
        elif t.startswith(("desp", "saida")): s += v
    return round(e, 2), round(s, 2)

async def processar_mensagem_com_alfredo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roteador sempre ativo: texto/voz -> Groq tools -> execução local."""
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    if not config.GROQ_API_KEY:
        await update.message.reply_text("❌ GROQ_API_KEY não configurada no servidor.")
        return ConversationHandler.END

    _clear_pending_context(context)

    texto_usuario = ""
    if update.message.voice:
        wait_msg = await update.message.reply_text("🎙️ Ouvindo seu áudio...")
        try:
            voice = update.message.voice
            tg_file = await voice.get_file()
            voice_bytes = bytes(await tg_file.download_as_bytearray())
            texto_usuario = await _groq_transcribe_voice_async(voice_bytes, voice.mime_type or "audio/ogg")
            # Log visual para o usuário saber o que foi entendido
            logger.info(f"🎙️ [VOICE] Transcrição: {texto_usuario}")
            if texto_usuario:
                await _enviar_resposta_html_segura(update.message, f"<i>\"{(texto_usuario[:100] + '...') if len(texto_usuario) > 100 else texto_usuario}\"</i>")
        except Exception as exc:
            logger.error("Falha ao transcrever áudio com Groq: %s", exc, exc_info=True)
            await wait_msg.edit_text("❌ Não consegui transcrever seu áudio. Tente novamente.")
            return ConversationHandler.END
        finally:
            try:
                await wait_msg.delete()
            except Exception:
                pass
    else:
        texto_usuario = (update.message.text or "").strip()

    if not texto_usuario:
        await update.message.reply_text("Não consegui entender sua mensagem. Pode tentar de novo?")
        return ConversationHandler.END

    db = next(get_db())
    try:
        # --- NOVO: INTERCEPTOR DE FIIs ---
        fii_intent = detect_fii_intent(texto_usuario)
        if fii_intent:
            await route_fii_intent(fii_intent, update, context, db)
            return ConversationHandler.END

        usuario_db, saldo, entradas, saidas = _usuario_e_saldo(db, update.effective_user)
        ensure_user_plan_state(db, usuario_db, commit=True)

        gate_ia = plan_allows_feature(db, usuario_db, "ia_questions")
        if not gate_ia.allowed:
            text, keyboard = upgrade_prompt_for_feature("ia_questions")
            await _enviar_resposta_html_segura(update.message, text, reply_markup=keyboard)
            return ConversationHandler.END

        consume_feature_quota(db, usuario_db, "ia_questions", amount=1)

        texto_normalizado = texto_usuario.strip().lower()

        # --- NOVO: INTERCEPTOR DE AÇÃO DIRETA (ZERO ATRITO) ---
        acao_direta = _detectar_e_extrair_acao_direta(texto_usuario)
        tool_calls = []
        if acao_direta:
            fn_name, args = acao_direta
            tool_calls = [{"type": "function", "function": {"name": fn_name, "arguments": json.dumps(args)}}]
            logger.info(f"⚡ [ALFREDO] Interceptação direta: {fn_name}")

        # Interceptações que são comandos funcionais ou fora do escopo da IA de análise direta
        if not tool_calls and _intencao_categorizar_sem_categoria(texto_normalizado):
            atualizados, total_pendentes = await _categorizar_lancamentos_sem_categoria_async(db, usuario_db.id)
            if total_pendentes == 0:
                await _enviar_resposta_html_segura(update.message, 
                    "🏷️ <b>Categorização automática</b>\n\n"
                    "Não encontrei lançamentos pendentes sem categoria."
                )
                return ConversationHandler.END

            nao_classificados = max(0, total_pendentes - atualizados)
            await _enviar_resposta_html_segura(update.message, 
                "🏷️ <b>Categorização automática concluída</b>\n\n"
                f"• <b>Pendentes analisados:</b> {total_pendentes}\n"
                f"• <b>Categorizados:</b> {atualizados}\n"
                f"• <b>Ainda sem categoria:</b> {nao_classificados}\n\n"
                "Se quiser, eu também posso listar os que ainda ficaram pendentes para revisão manual."
            )
            return ConversationHandler.END

        if not tool_calls and _deve_responder_localmente(texto_normalizado):
            resposta_local = _montar_resposta_local_alfredo(
                texto_usuario, texto_normalizado, db, usuario_db, saldo, entradas, saidas
            )
            await _enviar_resposta_html_segura(update.message, resposta_local)
            return ConversationHandler.END

        # --- PREPARAÇÃO DE CONTEXTO SINCRONIZADO COM MINIAPP ---
        hoje = datetime.now()
        hoje_str = hoje.strftime("%A, %d de %B de %Y às %H:%M")
        ignore_ids = _get_subcats_ignore_ids(db)

        # Mês Atual
        inicio_mes = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        lanc_mes = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id, Lancamento.data_transacao >= inicio_mes).all()
        ent_mes, sai_mes = _sum_consistente(lanc_mes)
        
        # Hoje
        inicio_hoje = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
        lanc_hoje = [l for l in lanc_mes if l.data_transacao >= inicio_hoje]
        
        # Ontem
        ontem = hoje - timedelta(days=1)
        inicio_ontem = ontem.replace(hour=0, minute=0, second=0, microsecond=0)
        fim_ontem = ontem.replace(hour=23, minute=59, second=59, microsecond=999999)
        lanc_ontem = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id, Lancamento.data_transacao >= inicio_ontem, Lancamento.data_transacao <= fim_ontem).all()

        # Soma total (incluindo transferências) para o resumo diário de ontem/hoje para evitar 'zero' em dias de Pix
        def _sum_bruta(lista):
            s = 0.0
            for l in lista:
                tipo = str(l.tipo).lower()
                if tipo.startswith(("desp", "saida", "saída", "pago", "enviado", "transf")):
                    s += abs(float(l.valor or 0))
            return round(s, 2)

        sai_hoje_bruto = _sum_bruta(lanc_hoje)
        sai_ontem_bruto = _sum_bruta(lanc_ontem)

        # Semana
        inicio_semana = hoje.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=hoje.weekday())
        lanc_semana = [l for l in lanc_mes if l.data_transacao >= inicio_semana]
        _, sai_semana = _sum_consistente(lanc_semana)

        # --- ÚLTIMOS LANÇAMENTOS (SUPER TRUNCADOS) ---
        limit_lanc = 5
        base_lanc = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id).order_by(Lancamento.data_transacao.desc(), Lancamento.id.desc()).limit(limit_lanc * 3).all()
        
        def _fmt_l(l):
            # Incluímos o final do ID para a IA não achar que é duplicado se os valores forem iguais
            id_curto = str(l.id)[-3:]
            return {
                "id": id_curto,
                "d": l.data_transacao.strftime('%d/%m'), 
                "desc": (l.descricao[:15] + '..') if l.descricao and len(l.descricao) > 15 else l.descricao, 
                "v": float(l.valor or 0), 
                "cat": (l.categoria.nome[:12]) if l.categoria else "Outros"
            }

        # Filtro de transações reais (Sincronizado com os totais)
        def _is_real_transacao(l):
            t = str(l.tipo).lower()
            if t in ["transferencia", "transferência", "transfer"] and (l.id_categoria is None and l.id_subcategoria is None): 
                return False
            return True

        ultimas_receitas = [_fmt_l(l) for l in base_lanc if str(l.tipo).lower().startswith(('entr', 'recei')) and _is_real_transacao(l)][:3]
        ultimas_despesas = [_fmt_l(l) for l in base_lanc if not str(l.tipo).lower().startswith(('entr', 'recei')) and _is_real_transacao(l) and l.id_subcategoria not in ignore_ids][:5]

        # --- MEMÓRIA HISTÓRICA (MÊS ANTERIOR) ---
        mes_anterior_inicio = (inicio_mes - timedelta(days=1)).replace(day=1)
        mes_anterior_fim = inicio_mes - timedelta(microseconds=1)
        lanc_anterior = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id, Lancamento.data_transacao >= mes_anterior_inicio, Lancamento.data_transacao <= mes_anterior_fim).all()
        ent_anterior, sai_anterior = _sum_consistente(lanc_anterior)
        breakdown_anterior = _resumo_categoria_gastos_por_lancamentos(lanc_anterior, ignore_ids=ignore_ids, limite=3)

        # --- METAS ---
        metas_ativas = db.query(Objetivo).filter(Objetivo.id_usuario == usuario_db.id, func.coalesce(Objetivo.valor_atual, 0) < func.coalesce(Objetivo.valor_meta, 0)).all()
        resumo_metas = [f"{m.descricao[:12]}: {int((float(m.valor_atual or 0)/float(m.valor_meta or 0.01))*100)}%" for m in metas_ativas if m.valor_meta and m.valor_meta > 0]

        # --- BREAKDOWN CATEGORIAS (MÊS ATUAL) ---
        breakdown_atual = _resumo_categoria_gastos_por_lancamentos(lanc_mes, ignore_ids=ignore_ids, limite=5)

        contexto_financeiro_str = json.dumps(
            {
                "data_hoje": hoje.strftime("%Y-%m-%d"),
                "mes_atual": {
                    "receitas": ent_mes,
                    "gastos": sai_mes,
                    "gastos_semana_total_bruto": sai_semana,
                    "hoje": sai_hoje_bruto,
                    "ontem": sai_ontem_bruto,
                    "categorias_RESUMO_MES_INTEIRO": [{"c": c, "v": round(v, 2)} for c, v in breakdown_atual]
                },
                "mes_anterior": {
                    "receitas": ent_anterior,
                    "gastos": sai_anterior,
                    "top_cats": [{"c": c, "v": round(v, 2)} for c, v in breakdown_anterior]
                },
                "ultimas_desp": ultimas_despesas,
                "metas": resumo_metas,
                "saldo": saldo
            },
            ensure_ascii=False
        )

        # Bypass PromptManager para usar o prompt compacto (Evita Rate Limit Groq/Cerebras de 8K tokens)
        system_prompt = Template(PROMPT_ALFREDO_APRIMORADO).render(
            user_name=(usuario_db.nome_completo or update.effective_user.first_name or "usuário"),
            pergunta_usuario=texto_usuario,
            contexto_financeiro_completo=contexto_financeiro_str,
            data_hora_atual=hoje_str
        )

        completion = None
        # Só chamamos a IA se o interceptor de Regex não capturou uma ação direta
        if not tool_calls:
            # Carrega histórico recente (memória de curto prazo) - Reduzido para economizar tokens
            chat_history_messages = _carregar_historico_recente_ia(db, usuario_db.id, limite=3)
            
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            
            # Adiciona o histórico antes da pergunta atual
            if chat_history_messages:
                messages.extend(chat_history_messages)
                
            messages.append({"role": "user", "content": texto_usuario})

            # Feature Secreta: Injeção do Open Finance
            tools_para_ia = list(_ALFREDO_TOOLS)
            if hasattr(usuario_db, 'pierre_api_key') and usuario_db.pierre_api_key:
                from pierre_finance.ai_tools import obter_tools_pierre
                tools_para_ia.extend(obter_tools_pierre())
                hoje_agora = datetime.now().strftime("%Y-%m-%d")
                messages[0]["content"] += (
                    f"\n\n**INSTRUÇÕES OPEN FINANCE (PIERRE) - REFERÊNCIA HOJE: {hoje_agora}**\n"
                    "Você é um Consultor Open Finance. REGRAS DE OURO:\n"
                    f"1. A DATA DE HOJE É {hoje_agora}. Use-a para calcular meses (ex: se hoje é Abril/2026, Fevereiro é 2026-02).\n"
                    "2. PROIBIDO retornar JSON bruto no chat. Seus pensamentos internos de tool calling devem ser convertidos em frases humanas.\n"
                    "3. Para JUROS, use 'consultar_extrato_bancario_real' com clientMessage='juros' e as datas CORRETAS do mês solicitado.\n"
                    "4. Se o usuário pedir fatura de Abril e hoje for Abril, use 'consultar_faturas_cartao_real' (fatura aberta).\n"
                    "5. Se pedir fatura de mês PASSADO, use 'consultar_faturas_passadas'."
                )

            # Orquestrador inteligente tenta Cerebras -> Groq -> Gemini
            completion = await _smart_ai_completion_async(messages, tools=tools_para_ia, tool_choice="auto")
        if not completion and not tool_calls:
            logger.warning(f"⚠️ [ALFREDO] Todos os modelos de IA falharam para query: '{texto_usuario}'. Usando motor local.")
            resposta_local = _montar_resposta_local_alfredo(texto_usuario, texto_normalizado, db, usuario_db, saldo, entradas, saidas)
            await _enviar_resposta_html_segura(update.message, resposta_local)
            return ConversationHandler.END

        # Extração de dados da resposta (seja dict ou string do Gemini)
        ia_message = {}
        if not tool_calls and completion:
            if isinstance(completion, str):
                # Caso o Gemini ou Cerebras/Groq tenham retornado tool calls na string de conteúdo
                tool_calls = _extrair_tool_calls_do_texto(completion)
                
                if not tool_calls:
                    # Trava de segurança: Se o texto contém JSON que parece tool call, não envia
                    if _contem_tool_call_json(completion):
                        logger.error(f"⚠️ [ALFREDO] Tool call detectada mas falhou no parse: {completion[:200]}")
                        await update.message.reply_text("Não consegui processar sua pergunta agora. Tente reformular.")
                        return ConversationHandler.END

                    await _enviar_resposta_html_segura(update.message, completion)
                    return ConversationHandler.END
            else:
                choice = ((completion or {}).get("choices") or [{}])[0]
                ia_message = choice.get("message") or {}
                tool_calls = ia_message.get("tool_calls") or []
                
                # Se não veio tool_calls nativos, tenta extrair do content como fallback
                if not tool_calls and ia_message.get("content"):
                    tool_calls = _extrair_tool_calls_do_texto(ia_message["content"])

        if not tool_calls:
            resposta_direta = (ia_message.get("content") or "Não consegui processar agora. Tente novamente.").strip()

            # Trava de segurança final contra vazamento de JSON
            if _contem_tool_call_json(resposta_direta):
                logger.error(f"⚠️ [ALFREDO] JSON de tool call vazou para a resposta final: {resposta_direta[:200]}")
                await update.message.reply_text("Não consegui processar sua pergunta agora. Tente reformular.")
                return ConversationHandler.END

            # Tenta extrair do formato legado ou de texto que contenha JSON no meio (fallback final)
            tool_calls = _extrair_tool_calls_do_texto(resposta_direta)
            
            if not tool_calls:
                # Salva no histórico para memória
                _registrar_historico_ia(db, usuario_db.id, texto_usuario, resposta_direta)
                await _enviar_resposta_html_segura(update.message, resposta_direta)
                return ConversationHandler.END

        # Se chegamos aqui, temos tool_calls para processar
        tool_call = tool_calls[0]
        fn = (tool_call.get("function") or {})
        fn_name = fn.get("name")
        
        # Garante que a tool_call tenha um ID (obrigatório para Cerebras/Groq)
        if not tool_call.get("id"):
            tool_call["id"] = f"call_{fn_name}_{int(time.time())}"
            
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}

        if not fn_name:
            resposta_local = _montar_resposta_local_alfredo(
                texto_usuario, texto_normalizado, db, usuario_db, saldo, entradas, saidas
            )
            await _enviar_resposta_html_segura(update.message, resposta_local)
            return ConversationHandler.END

        PIERRE_TOOLS_LIST = [
            "consultar_saldos_bancarios_reais", 
            "consultar_extrato_bancario_real",
            "consultar_saldo_consolidado_real",
            "consultar_faturas_cartao_real",
            "forcar_sincronizacao_bancaria",
            "consultar_faturas_passadas",
            "consultar_parcelamentos",
            "gerenciar_data_fechamento_cartao",
            "consultar_maiores_gastos",
            "consultar_livro_caixa_analitico",
            "consultar_memorias_ia"
        ]
        
        # --- FERRAMENTAS ANALÍTICAS (INTERPRETADAS PELA IA) ---
        ANALYTIC_TOOLS = ["consultar_historico_financeiro", "categorizar_lancamentos_pendentes", "responder_duvida_financeira", "comparar_periodos_financeiros"]
        
        if fn_name in ANALYTIC_TOOLS or fn_name in PIERRE_TOOLS_LIST:
            try:
                await update.message.reply_chat_action(action="typing")
            except Exception:
                pass
            
            res_str = ""
            if fn_name == "consultar_historico_financeiro":
                tipo_busca = args.get("tipo_busca")
                termo = (args.get("termo") or "").strip().lower()
                limite = int(args.get("limite") or 40)
                periodo = args.get("periodo") or "tudo"
                
                # --- DICIONÁRIO DE SINÔNIMOS (HUMANO -> CATEGORIA) ---
                mapa_sinonimos = {
                    "comida": "Alimentação",
                    "lanche": "Alimentação",
                    "restaurante": "Alimentação",
                    "mercado": "Alimentação",
                    "supermercado": "Alimentação",
                    "gasolina": "Transporte",
                    "combustivel": "Transporte",
                    "combustível": "Transporte",
                    "uber": "Transporte",
                    "99": "Transporte",
                    "carro": "Transporte",
                    "lazer": "Lazer",
                    "besteira": "Lazer",
                    "shopping": "Compras",
                    "online": "Compras Online",
                    "amazon": "Compras Online",
                    "ifood": "Alimentação"
                }
                
                # Se o termo for um sinônimo, buscamos pela categoria real também
                termo_busca = termo
                if termo in mapa_sinonimos:
                    termo_busca = mapa_sinonimos[termo]

                query = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id)
                query = query.filter(not_(func.lower(Lancamento.tipo).in_(["transferencia", "transferência", "transfer"])))
                
                if periodo == "este_mes":
                    query = query.filter(Lancamento.data_transacao >= inicio_mes)
                elif periodo == "esta_semana":
                    # Garante que 'esta_semana' comece no domingo para pegar o final de semana passado
                    inicio_semana = hoje.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=hoje.weekday() + 1)
                    query = query.filter(Lancamento.data_transacao >= inicio_semana)
                elif periodo == "semana_passada":
                    inicio_esta = hoje.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=hoje.weekday() + 1)
                    inicio_passada = inicio_esta - timedelta(days=7)
                    query = query.filter(Lancamento.data_transacao >= inicio_passada, Lancamento.data_transacao < inicio_esta)
                elif periodo == "mes_passado":
                    pm_inicio = (inicio_mes - timedelta(days=1)).replace(day=1)
                    query = query.filter(Lancamento.data_transacao >= pm_inicio, Lancamento.data_transacao < inicio_mes)
                elif periodo == "este_ano":
                    query = query.filter(Lancamento.data_transacao >= hoje.replace(month=1, day=1))
                elif periodo == "ultimos_7_dias":
                    query = query.filter(Lancamento.data_transacao >= hoje - timedelta(days=7))
                elif periodo == "ultimos_30_dias":
                    query = query.filter(Lancamento.data_transacao >= hoje - timedelta(days=30))

                # Filtro por termo (Categoria/Subcategoria/Descrição) se fornecido
                if termo:
                    query = query.filter(or_(
                        Lancamento.categoria.has(Categoria.nome.ilike(f"%{termo_busca}%")),
                        Lancamento.subcategoria.has(Subcategoria.nome.ilike(f"%{termo_busca}%")),
                        Lancamento.descricao.ilike(f"%{termo}%"),
                        Lancamento.descricao.ilike(f"%{termo_busca}%")
                    ))

                if tipo_busca == "maior_gasto":
                    res = query.filter(or_(
                        Lancamento.tipo.ilike("saida%"),
                        Lancamento.tipo.ilike("desp%"),
                        Lancamento.tipo.ilike("%pago%"),
                        Lancamento.tipo.ilike("%enviado%")
                    )).order_by(func.abs(Lancamento.valor).desc()).limit(limite).all()
                elif tipo_busca == "maior_receita":
                    res = query.filter(or_(
                        Lancamento.tipo.ilike("entr%"),
                        Lancamento.tipo.ilike("recei%"),
                        Lancamento.tipo.ilike("%recebido%")
                    )).order_by(func.abs(Lancamento.valor).desc()).limit(limite).all()
                elif tipo_busca == "soma_categoria" and termo:
                    soma = query.with_entities(func.sum(Lancamento.valor)).scalar() or 0
                    res_str = f"Soma total para '{termo}': {_formatar_valor_brasileiro(abs(float(soma)))}"
                elif tipo_busca == "lista_por_termo" and termo:
                    res = query.order_by(Lancamento.data_transacao.desc()).limit(limite).all()
                else:
                    res = query.order_by(Lancamento.data_transacao.desc()).limit(limite).all()

                if not res_str:
                    if isinstance(res, list):
                        if not res: res_str = f"Nenhum registro encontrado para '{termo or tipo_busca}'."
                        else: res_str = "\n".join([f"• {l.descricao}: {_formatar_valor_brasileiro(abs(float(l.valor or 0)))} ({l.data_transacao.strftime('%d/%m/%Y')})" for l in res])
                    else: res_str = str(res)

            elif fn_name == "comparar_periodos_financeiros":
                try:
                    mes_a = int(args.get("mes_alvo"))
                    ano_a = int(args.get("ano_alvo"))
                    mes_r = int(args.get("mes_referencia"))
                    ano_r = int(args.get("ano_referencia"))

                    def _get_stats_mes(m, a):
                        start = datetime(a, m, 1)
                        _, last_day = monthrange(a, m)
                        end = datetime(a, m, last_day, 23, 59, 59)
                        
                        base_q = db.query(Lancamento).filter(
                            Lancamento.id_usuario == usuario_db.id,
                            Lancamento.data_transacao >= start,
                            Lancamento.data_transacao <= end
                        ).filter(not_(func.lower(Lancamento.tipo).in_(["transferencia", "transferência", "transfer"])))
                        
                        todos_mes = base_q.all()
                        ent, sai = _sum_consistente(todos_mes)
                        
                        top_sai = base_q.filter(or_(Lancamento.tipo.ilike("saida%"), Lancamento.tipo.ilike("desp%"), Lancamento.tipo.ilike("%pago%"), Lancamento.tipo.ilike("%enviado%"))).order_by(func.abs(Lancamento.valor).desc()).limit(3).all()
                        top_ent = base_q.filter(or_(Lancamento.tipo.ilike("entr%"), Lancamento.tipo.ilike("recei%"), Lancamento.tipo.ilike("%recebido%"))).order_by(func.abs(Lancamento.valor).desc()).limit(3).all()
                        
                        cats = _resumo_categoria_gastos_por_lancamentos(todos_mes, ignore_ids=ignore_ids, limite=3)
                        
                        return {
                            "mes_ano": f"{m}/{a}",
                            "receitas": ent,
                            "despesas": sai,
                            "maiores_saidas": [{"desc": l.descricao, "v": float(l.valor)} for l in top_sai],
                            "maiores_entradas": [{"desc": l.descricao, "v": float(l.valor)} for l in top_ent],
                            "top_categorias": [{"c": c, "v": v} for c, v in cats]
                        }
                    
                    stats_alvo = _get_stats_mes(mes_a, ano_a)
                    stats_ref = _get_stats_mes(mes_r, ano_r)
                    
                    res_str = json.dumps({
                        "periodo_alvo": stats_alvo,
                        "periodo_referencia": stats_ref
                    }, ensure_ascii=False)
                except Exception as e:
                    res_str = f"Erro ao comparar períodos: {str(e)}"
            
            elif fn_name == "consultar_compromissos_futuros":
                periodo = args.get("periodo") or "esta_semana"
                fim_busca = hoje + timedelta(days=7)
                if periodo == "hoje": fim_busca = hoje.replace(hour=23, minute=59)
                elif periodo == "proximos_30_dias": fim_busca = hoje + timedelta(days=30)
                
                # 1. Busca Agendamentos (Controle)
                agends = db.query(Agendamento).filter(
                    Agendamento.id_usuario == usuario_db.id,
                    Agendamento.ativo == True,
                    Agendamento.proxima_data_execucao >= hoje.date(),
                    Agendamento.proxima_data_execucao <= fim_busca.date()
                ).all()
                
                # 2. Busca Lembretes (Controle)
                lembretes = db.query(Lembrete).filter(
                    Lembrete.id_usuario == usuario_db.id,
                    Lembrete.concluido == False,
                    Lembrete.data_lembrete >= hoje.date(),
                    Lembrete.data_lembrete <= fim_busca.date()
                ).all()
                
                res_parts = []
                if agends:
                    res_parts.append("Agendamentos:")
                    res_parts.extend([f"• {a.descricao}: {_formatar_valor_brasileiro(abs(float(a.valor or 0)))} em {a.proxima_data_execucao.strftime('%d/%m')}" for a in agends])
                if lembretes:
                    res_parts.append("\nLembretes:")
                    res_parts.extend([f"• {l.descricao}: {l.data_lembrete.strftime('%d/%m')}" for l in lembretes])
                
                res_str = "\n".join(res_parts) if res_parts else "Nenhum compromisso pendente para o período."

            elif fn_name == "categorizar_lancamentos_pendentes":
                atualizados, total = await _categorizar_lancamentos_sem_categoria_async(db, usuario_db.id)
                res_str = f"Categorização concluída. Analisados: {total}, Atualizados: {atualizados}."
            
            elif fn_name == "responder_duvida_financeira":
                res_str = "Responda baseando-se nos dados de resumo financeiro já enviados no contexto de sistema."

            elif fn_name in PIERRE_TOOLS_LIST and hasattr(usuario_db, 'pierre_api_key') and usuario_db.pierre_api_key:
                from pierre_finance.ai_tools import executar_tool_pierre
                resultado_bruto = executar_tool_pierre(fn_name, args, usuario_db.pierre_api_key)
                res_str = json.dumps(resultado_bruto, ensure_ascii=False) if not isinstance(resultado_bruto, str) else resultado_bruto
                if len(res_str) > 12000: res_str = res_str[:12000] + "... [Truncado]"

            # Adiciona o ciclo de interpretação pela IA
            messages.append({"role": "assistant", "tool_calls": tool_calls})
            messages.append({"role": "tool", "tool_call_id": tool_call["id"], "name": fn_name, "content": res_str})
            
            logger.info(f"🧠 [ALFREDO] Ciclo de interpretação humana para tool: {fn_name}")
            
            prompt_humanizar = f"""
            Você é o Alfredo, o braço direito financeiro do {usuario_db.nome_completo}.
            
            DIRETRIZES DE OURO:
            1. Use emojis de forma parceira. Varie o formato das respostas (não use sempre a mesma lista de tópicos).
            2. TRADUZA CONCEITOS: "Besteira/Lanche" -> Lazer/Snacks. "Impulso" -> Gastos não planejados.
            3. COMPARATIVO REAL: Use 'principais_gastos' do 'mes_anterior' para comparar. NUNCA invente números que não estão no JSON.
            4. CATEGORIAS: Use o campo 'cat' dos dados (ex: Alimentação).
            5. ESTILO: Seja direto. Se o usuário perguntou algo simples, responda em 1 parágrafo humano.
            6. DATA HOJE: {hoje_str}
            
            DADOS REAIS DO BANCO:
            {res_str}
            """
            
            messages_human = [{"role": "system", "content": prompt_humanizar}, {"role": "user", "content": texto_usuario}]
            completion_h = await _smart_ai_completion_async(messages_human)
            
            if not completion_h:
                from gerente_financeiro.ai_service import _gemini_chat_completion_async
                completion_h = await _gemini_chat_completion_async(messages_human)

            if completion_h:
                if isinstance(completion_h, str): final_text = completion_h
                else: final_text = (((completion_h or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
                
                if final_text:
                    final_text = re.sub(r'\{.*\}', '', final_text, flags=re.DOTALL).strip()
                    await _enviar_resposta_html_segura(update.message, final_text)
                    _registrar_historico_ia(db, usuario_db.id, texto_usuario, final_text)
                    return ConversationHandler.END

            await _enviar_resposta_html_segura(update.message, f"Aqui está o que encontrei:\n\n{res_str}")
            return ConversationHandler.END

        if fn_name == "registrar_lancamento":
            descricao = str(args.get("descricao") or "Lançamento").strip()
            categoria_original = str(args.get("categoria") or "Outros").strip()
            
            # Tenta categorização inteligente se a categoria for genérica
            categoria = categoria_original
            if categoria_original.lower() in {"outros", "sem categoria", "despesa", "gasto"}:
                # Note: _categorizar_com_mapa_inteligente retorna (cat_id, subcat_id)
                temp_tipo = _inferir_tipo_lancamento(texto_usuario, "", args.get("tipo"))
                cat_id, subcat_id = _categorizar_com_mapa_inteligente(descricao, temp_tipo, db)
                if cat_id:
                    cat_obj = db.query(Categoria).get(cat_id)
                    if cat_obj:
                        categoria = cat_obj.nome
            
            # Evita descrições genéricas se a IA puder extrair algo melhor do texto_usuario
            forma_pagamento = _normalizar_forma_pagamento(args.get("forma_pagamento"))
            tipo_transacao = _inferir_tipo_lancamento(texto_usuario, categoria, args.get("tipo"))
            data_lancamento = _normalizar_data_lancamento(args.get("data"))
            try:
                valor_raw = args.get("valor") or args.get("valor_alvo") or 0
                if isinstance(valor_raw, (int, float)):
                    valor = float(valor_raw)
                else:
                    valor = _parse_br_money(str(valor_raw))
            except (ValueError, TypeError):
                valor = 0.0

            if valor <= 0:
                await _enviar_resposta_html_segura(update.message, 
                    "❌ <b>Valor inválido</b>\n\n"
                    "Preciso de um valor maior que zero para preparar o lançamento."
                )
                return ConversationHandler.END

            gate_lanc = plan_allows_feature(db, usuario_db, "lancamentos")
            if not gate_lanc.allowed:
                text, keyboard = upgrade_prompt_for_feature("lancamentos")
                await _enviar_resposta_html_segura(update.message, text, reply_markup=keyboard)
                return ConversationHandler.END

            dados_quick = {
                "acao": "registrar_lancamento",
                "descricao": descricao,
                "valor": valor,
                "categoria": categoria,
                "categoria_sugerida": categoria,
                "subcategoria_sugerida": "N/A",
                "forma_pagamento": forma_pagamento,
                "tipo_transacao": tipo_transacao,
                "data": data_lancamento,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick
            # Compatibilidade com quick_action_handler legado
            context.user_data["quick_lancamento"] = dados_quick

            preview = (
                "🧾 <b>Confirme o lançamento</b>\n\n"
                f"• <b>Descrição:</b> {escape(descricao)}\n"
                f"• <b>Valor:</b> <code>{_formatar_valor_brasileiro(valor)}</code>\n"
                f"• <b>Tipo:</b> {escape(tipo_transacao)}\n"
                f"• <b>Data:</b> {escape(data_lancamento)}\n"
                f"• <b>Categoria:</b> {escape(categoria)}\n"
                f"• <b>Pagamento:</b> {escape(forma_pagamento)}"
            )
            webapp_url = _get_webapp_url("editar", draft=dados_quick)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                [InlineKeyboardButton("✏️ Editar", web_app=WebAppInfo(url=webapp_url))],
                [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
            ])
            await _enviar_resposta_html_segura(update.message, preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name in {"agendar_despesa", "agendar_receita", "criar_lembrete"}:
            eh_lembrete = fn_name == "criar_lembrete"
            eh_receita = fn_name == "agendar_receita"
            logger.info(f"🛠️ [ALFREDO] Processando {fn_name} com args: {args}")
            
            descricao_default = (
                "Novo lembrete" if eh_lembrete else ("Receita agendada" if eh_receita else "Despesa agendada")
            )
            descricao = str(args.get("descricao") or descricao_default).strip()
            
            # Limpeza de descrição para agendamentos via Regex
            if descricao == "Agendamento Recorrente" and args.get("_origem") == "regex":
                 # Tenta melhorar a descrição baseada no texto original se possível
                 # (A IA já faz um trabalho melhor, aqui é para o interceptor rápido)
                 if "recei" in t: descricao = "Receita Recorrente"
                 else: descricao = "Despesa Recorrente"
            
            # Remove prefixos redundantes que a IA às vezes coloca
            for prefix in ["Lembrete de ", "Lembrete: ", "Agendamento de ", "Pagar "]:
                if descricao.startswith(prefix) and len(descricao) > len(prefix):
                    # Mantém o prefixo "Pagar" se for lembrete
                    if prefix == "Pagar " and eh_lembrete: continue
                    # Caso contrário, simplifica
                    # descricao = descricao[len(prefix):].strip().capitalize()
                    pass

            try:
                valor_raw = args.get("valor")
                if valor_raw is not None and valor_raw != "":
                    # Se já for float/int, usa direto
                    if isinstance(valor_raw, (int, float)):
                        valor = float(valor_raw)
                    else:
                        valor = _parse_br_money(str(valor_raw))
                else:
                    valor = None
            except (ValueError, TypeError):
                valor = None
            
            data_str = str(args.get("data") or "").strip()
            # Fallback para hoje se a IA ou Regex não enviaram data mas temos o resto
            if not data_str and (eh_lembrete or (valor and valor > 0)):
                data_str = datetime.now().strftime("%Y-%m-%d")
                logger.info(f"📅 [ALFREDO] Data não informada, assumindo HOJE: {data_str}")

            frequencia = str(args.get("frequencia") or ("unico" if eh_lembrete else "mensal")).strip().lower()
            parcelas = args.get("parcelas")
            try:
                parcelas = int(parcelas) if parcelas is not None else None
            except (ValueError, TypeError):
                parcelas = None
            tipo_compromisso = _normalizar_tipo_compromisso(args.get("tipo"), "Receita" if eh_receita else "Saída")

            if (not eh_lembrete and (valor is None or valor <= 0)) or not data_str:
                logger.warning(f"⚠️ [ALFREDO] Dados insuficientes para {fn_name}: valor={valor}, data={data_str}")
                await _enviar_resposta_html_segura(update.message, 
                    "❌ <b>Dados incompletos</b>\n\n"
                    + (
                        "Informe descrição e data em <code>YYYY-MM-DD</code>."
                        if eh_lembrete else
                        "Informe descrição, valor (&gt; 0) e data de início em <code>YYYY-MM-DD</code>."
                    )
                )
                return ConversationHandler.END

            try:
                data_primeiro = datetime.fromisoformat(data_str).date()
            except ValueError:
                await _enviar_resposta_html_segura(update.message, 
                    "❌ <b>Data inválida</b>\n\n"
                    "Use <code>YYYY-MM-DD</code> (ex.: <code>2026-12-12</code>)."
                )
                return ConversationHandler.END

            frequencia_default = "unico" if eh_lembrete else "mensal"
            frequencia_normalizada = frequencia if frequencia in {"unico", "semanal", "mensal"} else frequencia_default
            acao_agendamento = "criar_lembrete" if eh_lembrete else ("agendar_receita" if eh_receita else "agendar_despesa")

            dados_quick = {
                "acao": acao_agendamento,
                "descricao": descricao,
                "valor": valor,
                "data": data_str,
                "frequencia": frequencia_normalizada,
                "parcelas": parcelas,
                "tipo": tipo_compromisso,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick

            preview = _build_quick_compromisso_preview(dados_quick)
            keyboard = _build_quick_compromisso_keyboard(dados_quick)
            await _enviar_resposta_html_segura(update.message, preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name == "criar_meta":
            descricao = str(args.get("descricao") or "Nova meta").strip()
            try:
                # Usa o motor robusto para converter valor da IA ou Regex
                v_raw = args.get("valor_alvo") or args.get("valor") or 0
                valor_alvo = _parse_br_money(str(v_raw)) or 0.0
            except (ValueError, TypeError):
                valor_alvo = 0.0
            data_meta_str = str(args.get("data_meta") or "").strip()

            if valor_alvo <= 0:
                await _enviar_resposta_html_segura(update.message, 
                    "❌ <b>Valor inválido</b>\n\n"
                    "Preciso de um valor alvo maior que zero."
                )
                return ConversationHandler.END

            data_meta = None
            if data_meta_str:
                try:
                    data_meta = datetime.fromisoformat(data_meta_str).date()
                except ValueError:
                    await _enviar_resposta_html_segura(update.message, 
                        "❌ <b>Prazo inválido</b>\n\n"
                        "Use <code>YYYY-MM-DD</code> para data da meta."
                    )
                    return ConversationHandler.END

            dados_quick = {
                "acao": "criar_meta",
                "descricao": descricao,
                "valor_alvo": valor_alvo,
                "data_meta": data_meta_str if data_meta_str else None,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick

            prazo_txt = data_meta.strftime("%d/%m/%Y") if data_meta else "Sem prazo definido"
            preview = (
                "🎯 <b>Confirme a meta</b>\n\n"
                f"• <b>Descrição:</b> {escape(descricao)}\n"
                f"• <b>Valor alvo:</b> <code>{_formatar_valor_brasileiro(valor_alvo)}</code>\n"
                f"• <b>Prazo:</b> {escape(prazo_txt)}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                [InlineKeyboardButton("✏️ Editar", callback_data="quick_edit")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
            ])
            await _enviar_resposta_html_segura(update.message, preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name == "definir_limite_orcamento":
            categoria = str(args.get("categoria") or "").strip()
            try:
                valor_raw = args.get("valor") or args.get("valor_alvo") or 0
                if isinstance(valor_raw, (int, float)):
                    valor = float(valor_raw)
                else:
                    valor = _parse_br_money(str(valor_raw))
            except (ValueError, TypeError):
                valor = 0.0
            
            periodo = args.get("periodo") # diário, semanal, mensal

            if not categoria or valor <= 0:
                await _enviar_resposta_html_segura(update.message, 
                    "❌ <b>Dados incompletos</b>\n\n"
                    "Preciso do nome da categoria e um valor maior que zero para criar o limite."
                )
                return ConversationHandler.END

            dados_quick = {
                "acao": "definir_limite_orcamento",
                "categoria": categoria,
                "valor_limite": valor,
                "periodo": periodo,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick

            if periodo:
                periodo_txt = periodo.capitalize()
                preview = (
                    "🚧 <b>Confirme o Limite de Orçamento</b>\n\n"
                    f"• <b>Categoria:</b> {escape(categoria)}\n"
                    f"• <b>Valor:</b> <code>{_formatar_valor_brasileiro(valor)}</code>\n"
                    f"• <b>Período:</b> {escape(periodo_txt)}"
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
                ])
                await _enviar_resposta_html_segura(update.message, preview, reply_markup=keyboard)
            else:
                # Se não informou o período, pergunta com botões
                texto_pergunta = (
                    "🚧 <b>Quase lá!</b>\n\n"
                    f"Você quer definir um limite de <code>{_formatar_valor_brasileiro(valor)}</code> para <b>{escape(categoria)}</b>.\n\n"
                    "Qual a frequência desse limite?"
                )
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📅 Diário", callback_data="limite_periodo_diário"),
                        InlineKeyboardButton("🗓️ Semanal", callback_data="limite_periodo_semanal"),
                        InlineKeyboardButton("📊 Mensal", callback_data="limite_periodo_mensal")
                    ],
                    [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")]
                ])
                await _enviar_resposta_html_segura(update.message, texto_pergunta, reply_markup=keyboard)
            
            return ConversationHandler.END

        if fn_name == "responder_duvida_financeira":
            pergunta = str(args.get("pergunta") or texto_usuario)
            pergunta_low = pergunta.lower()

            # Caso especial: Pergunta sobre os últimos lançamentos
            if any(x in pergunta_low for x in ["ultimo", "último", "recente", "mais novo", "extrato", "lista"]) and any(x in pergunta_low for x in ["lançamento", "lancamento", "transação", "transacao", "gasto", "compra"]):
                # Se for plural ou pedir lista/extrato, mostra 5. Se for singular, mostra 1.
                limite = 5 if any(x in pergunta_low for x in ["s", "lista", "extrato"]) else 1
                
                lancamentos = (
                    db.query(Lancamento)
                    .filter(Lancamento.id_usuario == usuario_db.id)
                    .order_by(Lancamento.id.desc())
                    .limit(limite)
                    .all()
                )
                
                if lancamentos:
                    if len(lancamentos) == 1:
                        card = _formatar_lancamento_card(lancamentos[0])
                        await _enviar_resposta_html_segura(update.message, card)
                    else:
                        texto_lista = "<b>📋 Seus lançamentos recentes:</b>\n\n"
                        for l in lancamentos:
                            valor_f = _formatar_valor_brasileiro(abs(float(l.valor or 0)))
                            emoji = "🟢" if str(l.tipo).lower().startswith(("entr", "recei")) else "🔴"
                            texto_lista += f"{emoji} {l.data_transacao.strftime('%d/%m')} | {l.descricao[:15]} | <code>{valor_f}</code>\n"
                        await _enviar_resposta_html_segura(update.message, texto_lista)
                    return ConversationHandler.END

            ultimos_lanc = (
                db.query(Lancamento)
                .filter(Lancamento.id_usuario == usuario_db.id)
                .order_by(Lancamento.id.desc())
                .limit(5)
                .all()
            )

            resumo_ultimos = []
            for lanc in ultimos_lanc:
                valor = float(lanc.valor or 0)
                sinal = "+" if str(lanc.tipo).lower().startswith(("entr", "recei")) else "-"
                resumo_ultimos.append(
                    f"{lanc.data_transacao.strftime('%d/%m/%Y')} | {lanc.descricao or 'Lançamento'} | {sinal}R$ {abs(valor):.2f}"
                )

            categorias_saida: dict[str, float] = {}
            for lanc in (
                db.query(Lancamento)
                .filter(Lancamento.id_usuario == usuario_db.id)
                .order_by(Lancamento.id.desc())
                .limit(120)
                .all()
            ):
                if str(lanc.tipo).lower().startswith(("entr", "recei")):
                    continue
                chave = "Sem categoria"
                if getattr(lanc, "categoria", None) and lanc.categoria:
                    chave = lanc.categoria.nome or chave
                categorias_saida[chave] = categorias_saida.get(chave, 0.0) + abs(float(lanc.valor or 0))

            top_categorias = sorted(categorias_saida.items(), key=lambda x: x[1], reverse=True)[:5]
            resumo_categorias = [f"{nome}: R$ {valor:.2f}" for nome, valor in top_categorias]

            metas_ativas = (
                db.query(Objetivo)
                .filter(
                    Objetivo.id_usuario == usuario_db.id,
                    func.coalesce(Objetivo.valor_atual, 0) < func.coalesce(Objetivo.valor_meta, 0),
                )
                .order_by(Objetivo.criado_em.desc(), Objetivo.id.desc())
                .limit(5)
                .all()
            )
            resumo_metas = [
                f"{(m.descricao or 'Meta')} ({float(m.valor_atual or 0):.2f}/{float(m.valor_meta or 0):.2f})"
                for m in metas_ativas
            ]

            contextual_messages = [
                {
                    "role": "system",
                    "content": (
                        "Responda ESTRITAMENTE à pergunta do usuário. "
                        "Se ele perguntar de metas, fale SÓ de metas. "
                        "Use o contexto financeiro apenas como base de conhecimento silenciosa, "
                        "não repita os dados a menos que seja solicitado. "
                        "Responda em português do Brasil, objetivo e útil. "
                        "Seja curto e escaneável para mobile. "
                        "NUNCA ultrapasse 3 parágrafos curtos e prefira bullet points. "
                        "Use apenas os dados informados no contexto financeiro. "
                        "Não invente números, contas ou transações. "
                        "Se um dado não estiver disponível, diga que não encontrou no banco. "
                        "Os números no contexto abaixo são dados reais do usuário e devem ser priorizados. "
                        "Use formatação curta amigável para Telegram em HTML simples."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Pergunta: {pergunta}\n"
                        f"Contexto financeiro atual do usuário:\n"
                        f"- Saldo: R$ {saldo:.2f}\n"
                        f"- Entradas acumuladas: R$ {entradas:.2f}\n"
                        f"- Saídas acumuladas: R$ {saidas:.2f}\n"
                        f"- Últimos lançamentos reais: {('; '.join(resumo_ultimos)) if resumo_ultimos else 'nenhum lançamento encontrado'}\n"
                        f"- Top categorias de gasto reais: {('; '.join(resumo_categorias)) if resumo_categorias else 'sem categorias suficientes'}\n"
                        f"- Metas ativas reais: {('; '.join(resumo_metas)) if resumo_metas else 'nenhuma meta ativa encontrada'}\n"
                    ),
                },
            ]
            try:
                answer_completion = await _groq_chat_completion_async(contextual_messages)
                answer = (((answer_completion or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
                answer = (answer or "Não consegui responder agora, tente novamente.").strip()
            except Exception as exc:
                logger.warning("Falha ao responder dúvida financeira com Groq; usando fallback local: %s", exc)
                answer = _montar_resposta_local_alfredo(texto_usuario, texto_normalizado, db, usuario_db, saldo, entradas, saidas)

            await _enviar_resposta_html_segura(update.message, answer)
            return ConversationHandler.END

        resposta_local = _montar_resposta_local_alfredo(
            texto_usuario, texto_normalizado, db, usuario_db, saldo, entradas, saidas
        )
        await _enviar_resposta_html_segura(update.message, resposta_local)
        return ConversationHandler.END
    except Exception as exc:
        logger.error("Erro no roteador Alfredo: %s", exc, exc_info=True)
        await update.message.reply_text("❌ Tive um problema ao processar sua mensagem. Tente novamente em instantes.")
        return ConversationHandler.END
    finally:
        db.close()


async def quick_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data
    dados_quick = context.user_data.get("dados_quick") or context.user_data.get("quick_lancamento")

    if not dados_quick and action != "quick_cancel":
        await query.edit_message_text("❌ Dados expirados. Tente novamente.")
        return ConversationHandler.END

    if action == "quick_cancel":
        context.user_data.pop("dados_quick", None)
        context.user_data.pop("quick_lancamento", None)
        await query.edit_message_text("❌ Ação cancelada.")
        return ConversationHandler.END

    if action == "quick_edit":
        await query.edit_message_text("✏️ Para editar, por favor reformule sua mensagem ou abra o MiniApp.")
        return ConversationHandler.END

    if action in {"quick_toggle_lembrete", "quick_toggle_agendamento"}:
        destino = "lembrete" if action.endswith("lembrete") else "agendamento"
        dados_quick = _alternar_tipo_compromisso(dados_quick, destino)
        context.user_data["dados_quick"] = dados_quick
        await query.edit_message_text(
            _build_quick_compromisso_preview(dados_quick),
            parse_mode='HTML',
            reply_markup=_build_quick_compromisso_keyboard(dados_quick),
        )
        return ConversationHandler.END

    if action == "quick_confirm":
        tipo_acao = dados_quick.get("acao")
        db = next(get_db())
        try:
            usuario_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)
            
            if tipo_acao == "registrar_lancamento":
                data_str = dados_quick.get("data")
                try:
                    data_tx = datetime.strptime(data_str, "%d/%m/%Y")
                except Exception:
                    data_tx = datetime.now()
                    
                cat_id, subcat_id = _categorizar_com_mapa_inteligente(dados_quick.get("descricao"), dados_quick.get("tipo_transacao"), db)
                if cat_id is None and dados_quick.get("categoria"):
                    cat = db.query(Categoria).filter(Categoria.nome.ilike(dados_quick.get("categoria"))).first()
                    if cat:
                        cat_id = cat.id

                # Funil para Conta Digital via ReconciliationService
                from gerente_financeiro.reconciliation_service import ReconciliationService
                
                # Normaliza valor (Entrada = +, Saída = -) para o serviço
                valor_final = float(dados_quick.get("valor"))
                if dados_quick.get("tipo_transacao") == "Despesa":
                    valor_final = -abs(valor_final)
                else:
                    valor_final = abs(valor_final)

                novo_lanc, criado = ReconciliationService.register_transaction(
                    db=db,
                    user_id=usuario_db.id,
                    valor=valor_final,
                    data=data_tx,
                    descricao=dados_quick.get("descricao"),
                    categoria_id=cat_id,
                    origem=dados_quick.get("origem", "alfredo")
                )
                
                # Configurações adicionais se foi criado agora
                if criado:
                    novo_lanc.id_subcategoria = subcat_id
                    novo_lanc.forma_pagamento = dados_quick.get("forma_pagamento")
                    db.commit()
                
                from gerente_financeiro.gamification_utils import give_xp_for_action
                try:
                    await give_xp_for_action(query.from_user.id, "LANCAMENTO_CRIADO_TEXTO", context)
                except Exception:
                    pass
                    
                status_msg = "✅ Lançamento registrado com sucesso!" if criado else "⚠️ Este lançamento já foi registrado anteriormente (duplicidade evitada)."
                await query.edit_message_text(status_msg)
                
            elif tipo_acao in ["agendar_receita", "agendar_despesa"]:
                data_str = dados_quick.get("data")
                try:
                    data_primeiro = datetime.fromisoformat(data_str).date()
                except Exception:
                    data_primeiro = datetime.now().date()
                    
                novo_agendamento = Agendamento(
                    id_usuario=usuario_db.id,
                    descricao=dados_quick.get("descricao"),
                    valor=dados_quick.get("valor"),
                    tipo="Receita" if tipo_acao == "agendar_receita" else "Saída",
                    data_primeiro_evento=data_primeiro,
                    proxima_data_execucao=data_primeiro,
                    frequencia=dados_quick.get("frequencia", "mensal"),
                    total_parcelas=dados_quick.get("parcelas"),
                    ativo=True
                )
                db.add(novo_agendamento)
                db.commit()
                
                from gerente_financeiro.gamification_utils import give_xp_for_action
                try:
                    await give_xp_for_action(query.from_user.id, "AGENDAMENTO_CRIADO", context)
                except Exception:
                    pass
                    
                await query.edit_message_text("✅ Agendamento criado com sucesso!")

            elif tipo_acao == "criar_lembrete":
                data_str = dados_quick.get("data")
                try:
                    data_primeiro = datetime.fromisoformat(data_str).date()
                except Exception:
                    data_primeiro = datetime.now().date()

                novo_lembrete = Lembrete(
                    id_usuario=usuario_db.id,
                    descricao=dados_quick.get("descricao"),
                    valor=dados_quick.get("valor"),
                    tipo=_normalizar_tipo_compromisso(dados_quick.get("tipo")),
                    data_primeiro_evento=data_primeiro,
                    proxima_data_execucao=data_primeiro,
                    frequencia=dados_quick.get("frequencia", "unico"),
                    total_parcelas=dados_quick.get("parcelas"),
                    parcela_atual=0,
                    ativo=True,
                    status="ativo",
                )
                db.add(novo_lembrete)
                db.commit()

                await query.edit_message_text("✅ Lembrete criado com sucesso!")
                
            elif tipo_acao == "criar_meta":
                data_meta_str = dados_quick.get("data_meta")
                data_meta = None
                if data_meta_str:
                    try:
                        data_meta = datetime.fromisoformat(data_meta_str).date()
                    except Exception:
                        pass
                        
                nova_meta = Objetivo(
                    id_usuario=usuario_db.id,
                    descricao=dados_quick.get("descricao"),
                    valor_meta=dados_quick.get("valor_alvo"),
                    valor_atual=0.0,
                    data_meta=data_meta
                )
                db.add(nova_meta)
                db.commit()
                
                from gerente_financeiro.gamification_utils import give_xp_for_action
                try:
                    await give_xp_for_action(query.from_user.id, "META_CRIADA", context)
                except Exception:
                    pass
                    
                await query.edit_message_text("✅ Meta financeira criada com sucesso!")

            elif tipo_acao == "definir_limite_orcamento":
                cat_nome = str(dados_quick.get("categoria") or "").strip()
                # Limpeza de ruídos comuns enviados pela IA
                cat_nome = re.sub(r'\s+(neste|nesse|esse|do|pro)\s+mês$', '', cat_nome, flags=re.IGNORECASE)
                valor = dados_quick.get("valor_limite")

                # Busca categoria com maior flexibilidade
                cat = db.query(Categoria).filter(Categoria.nome.ilike(f"{cat_nome}")).first()
                if not cat:
                    cat = db.query(Categoria).filter(Categoria.nome.ilike(f"{cat_nome}%")).first()
                if not cat:
                    cat = db.query(Categoria).filter(Categoria.nome.ilike(f"%{cat_nome}%")).first()

                if not cat:
                    # Se não achou, lista as disponíveis para ajudar o usuário
                    cats_disponiveis = [c.nome for c in db.query(Categoria).all()]
                    sugestao = ", ".join(cats_disponiveis[:5])
                    await query.edit_message_text(
                        f"❌ Não encontrei a categoria '<b>{cat_nome}</b>'.\n\n"
                        f"Categorias comuns: {sugestao}...\n"
                        "Por favor, verifique o nome ou crie no MiniApp.", 
                        parse_mode='HTML'
                    )
                    return ConversationHandler.END
                orc = db.query(OrcamentoCategoria).filter(
                    OrcamentoCategoria.id_usuario == usuario_db.id,
                    OrcamentoCategoria.id_categoria == cat.id
                ).first()

                if orc:
                    old_valor = orc.valor_limite
                    orc.valor_limite = valor
                    # Atualiza período se fornecido
                    if dados_quick.get("periodo"):
                        orc.periodo = dados_quick.get("periodo")
                    
                    periodo_txt = str(orc.periodo or "mensal").capitalize()
                    msg_sucesso = f"🚧 <b>Limite Atualizado!</b>\n\nO teto {periodo_txt} para <i>{cat.nome}</i> mudou de {_formatar_valor_brasileiro(old_valor)} para <b>{_formatar_valor_brasileiro(valor)}</b>."
                else:
                    periodo = dados_quick.get("periodo") or "mensal"
                    db.add(OrcamentoCategoria(
                        id_usuario=usuario_db.id,
                        id_categoria=cat.id,
                        valor_limite=valor,
                        periodo=periodo
                    ))
                    periodo_txt = periodo.capitalize()
                    msg_sucesso = f"🚧 <b>Limite Configurado!</b>\n\nAgora você tem um teto <b>{periodo_txt}</b> de <b>{_formatar_valor_brasileiro(valor)}</b> para <i>{cat.nome}</i>."

                db.commit()
                from gerente_financeiro.services import limpar_cache_usuario
                try:
                    limpar_cache_usuario(query.from_user.id)
                except Exception:
                    pass
                    
                await query.edit_message_text(msg_sucesso, parse_mode='HTML')
        except Exception as e:
            db.rollback()
            logger.error("Erro no quick_action_handler: %s", e, exc_info=True)
            await query.edit_message_text("❌ Ocorreu um erro ao salvar os dados. Tente novamente.")
        finally:
            db.close()
            context.user_data.pop("dados_quick", None)
            context.user_data.pop("quick_lancamento", None)

    return ConversationHandler.END


async def limite_periodo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para escolha de período de limite via botão."""
    query = update.callback_query
    await query.answer()
    
    # Callback data: limite_periodo_diário, limite_periodo_semanal, limite_periodo_mensal
    periodo = query.data.split("_")[-1]
    
    dados_quick = context.user_data.get("dados_quick")
    if not dados_quick or dados_quick.get("acao") != "definir_limite_orcamento":
        await query.edit_message_text("❌ Sessão expirada. Por favor, peça para definir o limite novamente.")
        return ConversationHandler.END
    
    # Atualiza o período nos dados temporários
    dados_quick["periodo"] = periodo
    context.user_data["dados_quick"] = dados_quick
    
    categoria = dados_quick.get("categoria")
    valor = dados_quick.get("valor_limite")
    periodo_txt = periodo.capitalize()
    
    preview = (
        "🚧 <b>Confirme o Limite de Orçamento</b>\n\n"
        f"• <b>Categoria:</b> {escape(categoria)}\n"
        f"• <b>Valor:</b> <code>{_formatar_valor_brasileiro(valor)}</code>\n"
        f"• <b>Período:</b> {escape(periodo_txt)}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
    ])
    await query.edit_message_text(preview, reply_markup=keyboard, parse_mode='HTML')
    return ConversationHandler.END
