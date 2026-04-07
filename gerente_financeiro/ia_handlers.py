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
from calendar import monthrange
from collections import Counter
from html import escape
from urllib.parse import quote
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler
from sqlalchemy import and_, extract, func, or_
from database.database import get_db, get_or_create_user
from models import Lancamento, Usuario, Categoria, Agendamento, Objetivo, ItemLancamento, OrcamentoCategoria
import config
from gerente_financeiro.services import _categorizar_com_mapa_inteligente
from gerente_financeiro.prompts import PROMPT_ALFREDO_APRIMORADO
from gerente_financeiro.monetization import (
    consume_feature_quota,
    ensure_user_plan_state,
    plan_allows_feature,
    upgrade_prompt_for_feature,
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


def _inferir_tipo_lancamento(texto_usuario: str, categoria: str, tipo_ia: str | None = None) -> str:
    tipo_raw = str(tipo_ia or "").strip().lower()
    if tipo_raw in {"entrada", "receita"}:
        return "Entrada"
    if tipo_raw in {"saida", "saída", "despesa"}:
        return "Saída"

    texto = f"{texto_usuario} {categoria}".lower()
    sinais_entrada = ["receita", "entrada", "recebi", "ganhei", "salario", "salário", "venda", "reembolso"]
    sinais_saida = ["despesa", "saida", "saída", "gastei", "paguei", "compra", "debito", "débito"]

    tem_entrada = any(s in texto for s in sinais_entrada)
    tem_saida = any(s in texto for s in sinais_saida)

    if tem_entrada and not tem_saida:
        return "Entrada"
    if tem_saida and not tem_entrada:
        return "Saída"
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
                "description": "Define um limite (teto de gastos) mensal de orçamento para uma categoria.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "categoria": {"type": "string", "description": "Nome da categoria (ex: Lazer, Alimentação, Transporte)"},
                        "valor": {"type": "number", "description": "Valor monetário do limite"},
                    },
                    "required": ["categoria", "valor"],
                },
            },
        },
        {
        "type": "function",
        "function": {
            "name": "registrar_lancamento",
            "description": "Registra um lançamento financeiro de entrada ou saída.",
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
            "description": "Prepara um agendamento de despesa recorrente com validação explícita de valor, data de início e frequência.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "Descricao curta do compromisso financeiro. Ex.: 'Bike', 'Academia', 'Internet'.",
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor monetario unitario da parcela/evento. Extraia o numero exato citado pelo usuario (32 significa 32, nunca 12).",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do primeiro evento em YYYY-MM-DD. Converta datas brasileiras (DD/MM/AAAA) para YYYY-MM-DD.",
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
            "description": "Prepara um agendamento de receita recorrente com validação explícita de valor, data de início e frequência.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "Descricao curta da receita. Ex.: 'Salário', 'Freela fixo', 'Aluguel recebido'.",
                    },
                    "valor": {
                        "type": "number",
                        "description": "Valor monetario unitario da receita recorrente.",
                    },
                    "data": {
                        "type": "string",
                        "description": "Data do primeiro recebimento em YYYY-MM-DD.",
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
            "name": "criar_meta",
            "description": "Cria uma meta financeira para o usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "valor_alvo": {"type": "number"},
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
            "name": "categorizar_lancamentos_pendentes",
            "description": "Categoriza automaticamente todos os lançamentos financeiros do usuário que estão sem categoria registrada.",
            "parameters": {
                "type": "object",
                "properties": {},
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


def _groq_chat_completion(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    payload = {
        "model": config.GROQ_MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=45,
    )
    if response.status_code >= 400:
        logger.error("Groq HTTP %s: %s", response.status_code, response.text[:2000])
    response.raise_for_status()
    return response.json()


async def _groq_chat_completion_async(messages: list[dict], tools: list[dict] | None = None, tool_choice: str | dict | None = None) -> dict:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _groq_chat_completion, messages, tools, tool_choice)


def _groq_transcribe_voice(voice_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY nao configurada")

    files = {
        "file": ("voice.ogg", voice_bytes, mime_type),
    }
    data = {
        "model": "whisper-large-v3-turbo",
        "response_format": "json",
        "language": "pt",
    }
    response = requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        files=files,
        data=data,
        timeout=60,
    )
    response.raise_for_status()
    return (response.json() or {}).get("text", "").strip()


async def _groq_transcribe_voice_async(voice_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _groq_transcribe_voice, voice_bytes, mime_type)


def _resolve_categoria_id(db, categoria_nome: str) -> int | None:
    if not categoria_nome:
        return None
    categoria = db.query(Categoria).filter(Categoria.nome.ilike(categoria_nome.strip())).first()
    return categoria.id if categoria else None


def _usuario_e_saldo(db, telegram_user) -> tuple[Usuario, float, float, float]:
    usuario_db = get_or_create_user(db, telegram_user.id, telegram_user.full_name)
    lancamentos = db.query(Lancamento).filter(Lancamento.id_usuario == usuario_db.id).all()
    entradas = sum(float(l.valor or 0) for l in lancamentos if str(l.tipo).lower().startswith("entr"))
    saidas = sum(abs(float(l.valor or 0)) for l in lancamentos if not str(l.tipo).lower().startswith("entr"))
    saldo = entradas - saidas
    return usuario_db, saldo, entradas, saidas


def _formatar_valor_brasileiro(valor: float) -> str:
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_resposta_html(texto: str) -> str:
    texto = (texto or "").strip().replace("\r\n", "\n")
    texto = re.sub(r"```(?:html|json|markdown|md)?\s*", "", texto, flags=re.IGNORECASE)
    texto = texto.replace("```", "")
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = escape(texto)
    texto = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", texto, flags=re.MULTILINE)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", texto)
    texto = re.sub(r"^\s*[-*]\s+", "• ", texto, flags=re.MULTILINE)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


async def _enviar_resposta_html_segura(message, texto: str, **kwargs):
    texto_html = _formatar_resposta_html(texto)
    try:
        return await message.reply_html(texto_html, **kwargs)
    except Exception as exc:
        logger.warning("Falha ao enviar HTML seguro; usando texto simples: %s", exc)
        texto_plano = re.sub(r"<[^>]+>", "", texto_html)
        return await message.reply_text(texto_plano, **kwargs)


def _intencao_busca_compra(texto: str) -> bool:
    texto = (texto or "").lower()
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
            "🔎 <b>Busca de compras</b>\n\n"
            f"Não encontrei compras para <b>{termo_fmt}</b> no seu banco."
        )

    linhas = [
        "🔎 <b>Busca de compras</b>",
        "",
        f"Encontrei {len(lancamentos)} registro(s) para <b>{termo_fmt}</b>:",
    ]
    for lanc in lancamentos[:5]:
        data_txt = lanc.data_transacao.strftime("%d/%m/%Y") if getattr(lanc, "data_transacao", None) else "sem data"
        itens = [escape(item.nome_item) for item in (getattr(lanc, "itens", []) or []) if getattr(item, "nome_item", None)]
        itens_txt = f" | Itens: {', '.join(itens[:4])}" if itens else ""
        linhas.append(
            f"• {escape(lanc.descricao or 'Lançamento')} — {_formatar_valor_brasileiro(abs(float(lanc.valor or 0)))} em {data_txt}{itens_txt}"
        )
    return "\n".join(linhas)


def _montar_resposta_local_alfredo(texto_usuario: str, texto_normalizado: str, db, usuario_db, saldo: float, entradas: float, saidas: float) -> str:
    if _intencao_contas(texto_normalizado):
        return _resumo_contas_local(db, usuario_db.id)

    if _intencao_comparacao_financeira(texto_normalizado):
        return _resumo_comparacao_local(db, usuario_db.id)

    if _intencao_alerta_financeiro(texto_normalizado):
        return _resumo_alerta_local(db, usuario_db.id)

    if _intencao_previsao_financeira(texto_normalizado):
        return _resumo_previsao_local(db, usuario_db.id, saldo, entradas, saidas)

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
                "📊 <b>Categoria com maior gasto</b>",
                "",
                f"• <b>Maior gasto:</b> {escape(top_categorias[0][0])} ({_formatar_valor_brasileiro(top_categorias[0][1])})",
                "",
                "<b>Top 5 categorias:</b>",
            ]
            for nome, valor in top_categorias:
                linhas.append(f"• {escape(nome)}: {_formatar_valor_brasileiro(valor)}")
            return "\n".join(linhas)

    if _intencao_forma_pagamento_mais_usada(texto_normalizado):
        forma_top, qtd_top, base_util = _forma_pagamento_mais_usada(db, usuario_db.id)
        if forma_top:
            return (
                "💳 <b>Forma de pagamento mais utilizada</b>\n\n"
                f"• <b>Mais usada:</b> {escape(forma_top)}\n"
                f"• <b>Ocorrências:</b> {qtd_top} de {base_util} lançamentos com forma informada"
            )

    if _intencao_resumo_semana(texto_normalizado):
        return _resumo_semana_local(db, usuario_db.id)

    if _intencao_resumo_mes(texto_normalizado):
        return _resumo_mes_local(db, usuario_db.id)

    return (
        "🤖 <b>Alfredo no modo local</b>\n\n"
        "A IA está instável no momento, então respondi com os dados reais do seu banco:\n"
        f"• <b>Saldo:</b> <code>{_formatar_valor_brasileiro(saldo)}</code>\n"
        f"• <b>Entradas:</b> <code>{_formatar_valor_brasileiro(entradas)}</code>\n"
        f"• <b>Saídas:</b> <code>{_formatar_valor_brasileiro(saidas)}</code>\n\n"
        "Se quiser, eu posso buscar uma compra específica, o último lançamento, o saldo ou o resumo do mês."
    )


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
    hoje = datetime.now().date()
    fim_semana = hoje + timedelta(days=(6 - hoje.weekday()))
    vencidas: list[str] = []
    hoje_itens: list[str] = []
    semana_itens: list[str] = []

    for ag in agendamentos:
        data_ag = ag.proxima_data_execucao.date() if getattr(ag, "proxima_data_execucao", None) else None
        if not data_ag:
            continue
        item = f"{escape(ag.descricao)} ({_formatar_valor_brasileiro(float(ag.valor or 0))}) em {data_ag.strftime('%d/%m/%Y')}"
        if data_ag < hoje:
            vencidas.append(item)
        elif data_ag == hoje:
            hoje_itens.append(item)
        elif hoje < data_ag <= fim_semana:
            semana_itens.append(item)

    if not agendamentos:
        return (
            "✅ Hoje você está tranquilo: não encontrei contas fixas ativas no seu banco.\n\n"
            "👉 Insight: vale cadastrar as contas recorrentes para evitar susto de vencimento."
        )

    if hoje_itens:
        linhas = [
            f"⚠️ Sim, você tem {len(hoje_itens)} conta(s) vencendo hoje.",
            "\n".join(f"• {item}" for item in hoje_itens[:3]),
        ]
    else:
        linhas = ["✅ Hoje não tem conta vencendo."]

    if vencidas:
        linhas.append(f"⚠️ Tem {len(vencidas)} conta(s) em atraso, priorize isso primeiro.")
    elif semana_itens:
        linhas.append(f"📅 Até o fim da semana você ainda tem {len(semana_itens)} compromisso(s).")

    if semana_itens:
        linhas.append("👉 Insight: já separa esse valor agora para não apertar seu caixa no fim da semana.")
    else:
        linhas.append("👉 Insight: sem compromissos próximos, você ganha margem para focar nas metas.")
    return "\n".join(linhas)


def _resumo_comparacao_local(db, usuario_id: int) -> str:
    hoje = datetime.now()
    mes_atual_inicio = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mes_anterior_fim = mes_atual_inicio - timedelta(microseconds=1)
    mes_anterior_inicio = mes_anterior_fim.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    atual = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao >= mes_atual_inicio,
        )
        .all()
    )
    anterior = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao >= mes_anterior_inicio,
            Lancamento.data_transacao <= mes_anterior_fim,
        )
        .all()
    )
    total_atual = sum(abs(float(l.valor or 0)) for l in atual if not str(l.tipo).lower().startswith("entr"))
    total_anterior = sum(abs(float(l.valor or 0)) for l in anterior if not str(l.tipo).lower().startswith("entr"))
    delta = total_atual - total_anterior
    delta_pct = 0.0 if total_anterior <= 0 else (delta / total_anterior) * 100.0
    sinal = "aumentou" if delta > 0 else "caiu" if delta < 0 else "ficou igual"

    if total_atual > total_anterior:
        primeira = "⚠️ Sim, este mês você está gastando mais que no mês passado."
    elif total_atual < total_anterior:
        primeira = "✅ Você melhorou: este mês está gastando menos que no mês passado."
    else:
        primeira = "➡️ Seu gasto está praticamente igual ao mês passado."

    linhas = [
        primeira,
        f"Hoje: {_formatar_valor_brasileiro(total_atual)} | Mês passado: {_formatar_valor_brasileiro(total_anterior)} ({delta_pct:+.1f}%).",
    ]
    if total_atual > total_anterior:
        linhas.append("👉 Insight: se cortar 10% agora, você já volta para o patamar do mês anterior.")
    elif total_atual < total_anterior:
        linhas.append("👉 Insight: mantenha esse ritmo por mais 2 semanas para consolidar o ganho.")
    else:
        linhas.append("👉 Insight: o próximo salto vem de atacar sua categoria mais cara, não de cortes pequenos.")
    return "\n".join(linhas)


def _resumo_alerta_local(db, usuario_id: int) -> str:
    agora = datetime.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lanc_mes = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao >= inicio_mes,
        )
        .order_by(Lancamento.id.desc())
        .all()
    )
    saidas_mes = sum(abs(float(l.valor or 0)) for l in lanc_mes if not str(l.tipo).lower().startswith("entr"))
    entradas_mes = sum(float(l.valor or 0) for l in lanc_mes if str(l.tipo).lower().startswith("entr"))
    saldo_mes = entradas_mes - saidas_mes
    top_categorias = _resumo_categoria_gastos_por_lancamentos(lanc_mes, limite=3)
    risco = "alto" if saldo_mes < 0 else "moderado" if saidas_mes > entradas_mes * 0.85 else "baixo"

    if risco == "alto":
        primeira = "⚠️ Sim, agora você está gastando acima do saudável."
    elif risco == "moderado":
        primeira = "⚠️ Você está no limite, então vale frear um pouco já."
    else:
        primeira = "✅ Por enquanto, você não está gastando acima do que deveria."

    linhas = [
        primeira,
        f"Seu mês está em {_formatar_valor_brasileiro(saldo_mes)} (entradas {_formatar_valor_brasileiro(entradas_mes)} vs saídas {_formatar_valor_brasileiro(saidas_mes)}).",
    ]
    if top_categorias:
        nome_top, valor_top = top_categorias[0]
        linhas.append(f"👉 Insight: seu maior peso está em {escape(nome_top)} ({_formatar_valor_brasileiro(valor_top)}).")
    else:
        linhas.append("👉 Insight: mesmo sem categoria dominante, controlar gasto diário já melhora seu fechamento do mês.")
    return "\n".join(linhas)


def _resumo_previsao_local(db, usuario_id: int, saldo: float, entradas: float, saidas: float) -> str:
    agora = datetime.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lanc_mes = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao >= inicio_mes,
        )
        .all()
    )
    dias_passados = max(1, agora.day)
    dias_no_mes = monthrange(agora.year, agora.month)[1]
    dias_restantes = max(1, dias_no_mes - agora.day)
    saidas_mes = sum(abs(float(l.valor or 0)) for l in lanc_mes if not str(l.tipo).lower().startswith("entr"))
    entradas_mes = sum(float(l.valor or 0) for l in lanc_mes if str(l.tipo).lower().startswith("entr"))
    media_diaria_saida = saidas_mes / dias_passados
    proj_saida = media_diaria_saida * dias_no_mes
    saldo_projetado = entradas_mes - proj_saida
    base_disponivel = saldo if saldo > 0 else entradas_mes - saidas_mes
    limite_diario = max(0.0, base_disponivel / dias_restantes)

    if saldo_projetado < 0:
        primeira = f"⚠️ Nesse ritmo, você tende a fechar o mês no vermelho em {_formatar_valor_brasileiro(abs(saldo_projetado))}."
    elif saldo_projetado > 0:
        primeira = f"✅ Nesse ritmo, você deve fechar o mês no positivo em {_formatar_valor_brasileiro(saldo_projetado)}."
    else:
        primeira = "➡️ Nesse ritmo, o mês deve fechar no zero a zero."

    linhas = [
        primeira,
        f"Seu limite seguro diário agora é {_formatar_valor_brasileiro(limite_diario)}.",
        f"👉 Insight: sua média diária está em {_formatar_valor_brasileiro(media_diaria_saida)}; baixar isso um pouco já muda o fechamento.",
    ]
    return "\n".join(linhas)


def _resumo_analise_gastos_local(db, usuario_id: int) -> str:
    lancamentos = (
        db.query(Lancamento)
        .filter(Lancamento.id_usuario == usuario_id)
        .order_by(Lancamento.id.desc())
        .limit(180)
        .all()
    )
    saidas_lanc = [l for l in lancamentos if not str(l.tipo).lower().startswith("entr")]
    top_categorias = _resumo_categoria_gastos_por_lancamentos(saidas_lanc, limite=5)
    pequenos = [l for l in saidas_lanc if abs(float(l.valor or 0)) <= 30]
    recorrentes = Counter((l.descricao or "Lançamento").strip().lower() for l in pequenos)
    top_recorrentes = [item for item in recorrentes.most_common(3) if item[1] > 1]
    maior = max(saidas_lanc, key=lambda l: abs(float(l.valor or 0)), default=None)

    if top_categorias:
        nome_top, valor_top = top_categorias[0]
        linhas = [
            f"💸 Seu principal ralo hoje está em {escape(nome_top)} ({_formatar_valor_brasileiro(valor_top)}).",
        ]
    else:
        linhas = ["💸 Seu padrão ainda está pouco categorizado, mas dá para ajustar rápido."]

    if maior:
        linhas.append(
            f"O maior gasto recente foi {escape(maior.descricao or 'Lançamento')} em {_formatar_valor_brasileiro(abs(float(maior.valor or 0)))}."
        )

    if top_recorrentes:
        nome_rec, qtd_rec = top_recorrentes[0]
        linhas.append(f"👉 Insight: {escape(nome_rec)} aparece {qtd_rec}x em gastos pequenos e recorrentes.")
    else:
        linhas.append("👉 Insight: cortar a categoria mais alta em 10% costuma dar resultado mais rápido que vários cortes pequenos.")
    return "\n".join(linhas)


def _resumo_consultoria_local(db, usuario_id: int, saldo: float, entradas: float, saidas: float) -> str:
    top_categorias = _resumo_categoria_gastos(db, usuario_id, limite=3)
    if saldo < 0 or saidas > entradas:
        linhas = [
            "⚠️ Meu direcionamento direto: corta gastos variáveis agora e protege seu caixa esta semana.",
            "Comece travando compras não essenciais até voltar para margem positiva.",
        ]
    else:
        linhas = [
            "✅ Você está no controle, então a jogada certa agora é consistência e acúmulo.",
            "Reserve parte do saldo positivo antes de aumentar gasto de estilo de vida.",
        ]

    if top_categorias:
        nome_top, valor_top = top_categorias[0]
        linhas.append(f"👉 Insight: sua maior alavanca hoje é {escape(nome_top)} ({_formatar_valor_brasileiro(valor_top)}).")
    else:
        linhas.append("👉 Insight: o maior ganho agora vem de categorizar melhor seus lançamentos para cortar com precisão.")
    return "\n".join(linhas)


def _resumo_semana_local(db, usuario_id: int) -> str:
    agora = datetime.now()
    inicio_semana = agora - timedelta(days=6)
    lancamentos = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao >= inicio_semana,
        )
        .order_by(Lancamento.id.desc())
        .all()
    )
    entradas_sem = sum(float(l.valor or 0) for l in lancamentos if str(l.tipo).lower().startswith("entr"))
    saidas_sem = sum(abs(float(l.valor or 0)) for l in lancamentos if not str(l.tipo).lower().startswith("entr"))
    saldo_sem = entradas_sem - saidas_sem
    top_categorias = _resumo_categoria_gastos_por_lancamentos(lancamentos, limite=3)

    linhas = [
        f"📊 Nessa semana você gastou {_formatar_valor_brasileiro(saidas_sem)} e entrou {_formatar_valor_brasileiro(entradas_sem)}.",
        f"Seu saldo semanal ficou em {_formatar_valor_brasileiro(saldo_sem)}.",
    ]
    if top_categorias:
        nome_top, valor_top = top_categorias[0]
        linhas.append(f"👉 Insight: {escape(nome_top)} foi a categoria que mais pesou na semana ({_formatar_valor_brasileiro(valor_top)}).")
    else:
        linhas.append("👉 Insight: com mais lançamentos categorizados, seus cortes ficam muito mais assertivos.")
    return "\n".join(linhas)


def _resumo_saldo_local(saldo: float, entradas: float, saidas: float) -> str:
    if saldo < 0:
        primeira = f"⚠️ Hoje você está no negativo em {_formatar_valor_brasileiro(abs(saldo))}."
    else:
        primeira = f"✅ Hoje você tem {_formatar_valor_brasileiro(saldo)} disponível."

    return (
        f"{primeira}\n"
        f"Entrou {_formatar_valor_brasileiro(entradas)} e saiu {_formatar_valor_brasileiro(saidas)} no acumulado.\n"
        "👉 Insight: manter seu saldo positivo depende mais de controlar as maiores categorias do que dos gastos pequenos."
    )


def _resumo_metas_local(db, usuario_id: int) -> str:
    objetivos_ativos = (
        db.query(Objetivo)
        .filter(
            Objetivo.id_usuario == usuario_id,
            func.coalesce(Objetivo.valor_atual, 0) < func.coalesce(Objetivo.valor_meta, 0),
        )
        .order_by(Objetivo.criado_em.desc(), Objetivo.id.desc())
        .all()
    )

    if not objetivos_ativos:
        return (
            "📌 Hoje você ainda não tem meta ativa com progresso pendente.\n"
            "👉 Insight: criar uma meta com valor mensal automático aumenta muito sua chance de concluir."
        )

    objetivo = objetivos_ativos[0]
    valor_atual = float(objetivo.valor_atual or 0)
    valor_meta = float(objetivo.valor_meta or 0)
    faltante = max(0.0, valor_meta - valor_atual)
    percentual = 0 if valor_meta <= 0 else int((valor_atual / valor_meta) * 100)

    return (
        f"🎯 Você está no caminho da meta <b>{escape(objetivo.descricao or objetivo.nome or 'Meta')}</b>: {percentual}% concluído.\n"
        f"Faltam {_formatar_valor_brasileiro(faltante)} para bater o alvo de {_formatar_valor_brasileiro(valor_meta)}.\n"
        "👉 Insight: definir um aporte fixo semanal acelera mais do que tentar compensar no fim do mês."
    )


def _resumo_mes_local(db, usuario_id: int) -> str:
    agora = datetime.now()
    inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    lanc_mes = (
        db.query(Lancamento)
        .filter(
            Lancamento.id_usuario == usuario_id,
            Lancamento.data_transacao >= inicio_mes,
        )
        .order_by(Lancamento.id.desc())
        .all()
    )
    entradas_mes = sum(float(l.valor or 0) for l in lanc_mes if str(l.tipo).lower().startswith("entr"))
    saidas_mes = sum(abs(float(l.valor or 0)) for l in lanc_mes if not str(l.tipo).lower().startswith("entr"))
    saldo_mes = entradas_mes - saidas_mes
    top_categorias_mes = _resumo_categoria_gastos_por_lancamentos(lanc_mes, limite=1)

    if saldo_mes >= 0:
        primeira = f"✅ Seu mês está positivo em {_formatar_valor_brasileiro(saldo_mes)}."
    else:
        primeira = f"⚠️ Seu mês está negativo em {_formatar_valor_brasileiro(abs(saldo_mes))}."

    linhas = [
        primeira,
        f"Entradas {_formatar_valor_brasileiro(entradas_mes)} vs saídas {_formatar_valor_brasileiro(saidas_mes)}.",
    ]
    if top_categorias_mes:
        nome_top, valor_top = top_categorias_mes[0]
        linhas.append(f"👉 Insight: {escape(nome_top)} é o principal peso do mês ({_formatar_valor_brasileiro(valor_top)}).")
    else:
        linhas.append("👉 Insight: categorizando melhor os lançamentos, você descobre rápido onde cortar.")
    return "\n".join(linhas)


def _formatar_lancamento_card(lanc: Lancamento) -> str:
    descricao = escape(lanc.descricao or "Lançamento")
    categoria = escape(lanc.categoria.nome if lanc.categoria else "Sem categoria")
    pagamento = escape(lanc.forma_pagamento or "Não informado")
    tipo = escape(lanc.tipo or "Não informado")
    data_formatada = lanc.data_transacao.strftime("%d/%m/%Y")
    hora_formatada = lanc.data_transacao.strftime("%H:%M")
    valor = _formatar_valor_brasileiro(abs(float(lanc.valor or 0)))
    tipo_emoji = "🟢" if str(lanc.tipo).lower().startswith("entr") else "🔴"

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
            "lançamento mais recente",
            "lancamento mais recente",
            "último gasto",
            "ultimo gasto",
        ]
    )


def _intencao_saldo(texto: str) -> bool:
    texto = (texto or "").lower()
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
    sinais = [
        "conta",
        "contas",
        "venc",
        "pagar",
        "paguei",
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
    ]
    return any(s in texto for s in sinais)


def _intencao_analise_gastos(texto: str) -> bool:
    texto = (texto or "").lower()
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
    return (
        ("categoria" in texto and "gasto" in texto and "mais" in texto)
        or "categoria eu mais" in texto
        or "categoria de gasto mais alta" in texto
    )


def _intencao_forma_pagamento_mais_usada(texto: str) -> bool:
    texto = (texto or "").lower()
    sinais_pagamento = ["forma de pagamento", "pagamento", "crédito", "credito", "pix", "débito", "debito"]
    sinais_uso = ["mais", "utilizo", "uso", "utilizada", "utilizo"]
    return any(s in texto for s in sinais_pagamento) and any(s in texto for s in sinais_uso)


def _intencao_resumo_mes(texto: str) -> bool:
    texto = (texto or "").lower()
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
    return any(
        s in texto
        for s in [
            "essa semana",
            "semana inteira",
            "resumo da semana",
            "quanto gastei essa semana",
            "gastei essa semana",
        ]
    )


def _intencao_agendamentos(texto: str) -> bool:
    texto = (texto or "").lower()
    return any(s in texto for s in ["agendamentos", "lancamentos programados", "lançamentos programados", "recorrente", "recorrentes", "para pagar de forma recorrente"])


def _intencao_score_financeiro(texto: str) -> bool:
    texto = (texto or "").lower()
    return "score" in texto and any(s in texto for s in ["financeir", "saúde financeira", "saude financeira"])


def _intencao_cotacao_externa(texto: str) -> bool:
    texto = (texto or "").lower()
    return any(s in texto for s in ["valor do dolar", "valor do dólar", "cotação", "cotacao", "crypto", "criptomoeda", "bitcoin", "ethereum"])


def _categorizar_lancamentos_sem_categoria(db, usuario_id: int) -> tuple[int, int]:
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
    for lanc in pendentes:
        descricao = (lanc.descricao or "").strip().lower()
        if not descricao:
            continue
        tipo_transacao = "Receita" if str(lanc.tipo).lower().startswith("entr") else "Despesa"
        cat_id, subcat_id = _categorizar_com_mapa_inteligente(descricao, tipo_transacao, db)
        if cat_id:
            lanc.id_categoria = cat_id
            lanc.id_subcategoria = subcat_id
            atualizados += 1

    if atualizados:
        db.commit()
    return atualizados, len(pendentes)


def _resumo_categoria_gastos(db, usuario_id: int, limite: int = 5) -> list[tuple[str, float]]:
    lancamentos = (
        db.query(Lancamento)
        .filter(Lancamento.id_usuario == usuario_id)
        .order_by(Lancamento.id.desc())
        .limit(300)
        .all()
    )
    return _resumo_categoria_gastos_por_lancamentos(lancamentos, limite=limite)


def _resumo_categoria_gastos_por_lancamentos(lancamentos: list[Lancamento], limite: int = 5) -> list[tuple[str, float]]:
    categorias: dict[str, float] = {}
    for lanc in lancamentos:
        if str(lanc.tipo).lower().startswith("entr"):
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
        wait_msg = await update.message.reply_text("🎙️ Entendi seu áudio, processando com o Alfredo...")
        try:
            voice = update.message.voice
            tg_file = await voice.get_file()
            voice_bytes = bytes(await tg_file.download_as_bytearray())
            texto_usuario = await _groq_transcribe_voice_async(voice_bytes, voice.mime_type or "audio/ogg")
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
        usuario_db, saldo, entradas, saidas = _usuario_e_saldo(db, update.effective_user)
        ensure_user_plan_state(db, usuario_db, commit=True)

        gate_ia = plan_allows_feature(db, usuario_db, "ia_questions")
        if not gate_ia.allowed:
            text, keyboard = upgrade_prompt_for_feature("ia_questions")
            await update.message.reply_html(text, reply_markup=keyboard)
            return ConversationHandler.END

        consume_feature_quota(db, usuario_db, "ia_questions", amount=1)

        texto_normalizado = texto_usuario.strip().lower()

        if _intencao_ultimo_lancamento(texto_normalizado):
            ultimo = _buscar_ultimo_lancamento_sem_futuro(db, usuario_db.id)
            if not ultimo:
                await update.message.reply_html(
                    "🔎 <b>Nenhum lançamento encontrado</b>\n\n"
                    "Você ainda não tem lançamentos registrados no seu banco."
                )
                return ConversationHandler.END

            await update.message.reply_html(_formatar_lancamento_card(ultimo))
            return ConversationHandler.END

        if _intencao_saldo(texto_normalizado):
            saldo_msg = _resumo_saldo_local(saldo, entradas, saidas)
            await update.message.reply_html(saldo_msg)
            return ConversationHandler.END

        if _intencao_metas(texto_normalizado):
            await update.message.reply_html(_resumo_metas_local(db, usuario_db.id))
            return ConversationHandler.END

        if _intencao_categorizar_sem_categoria(texto_normalizado):
            atualizados, total_pendentes = _categorizar_lancamentos_sem_categoria(db, usuario_db.id)
            if total_pendentes == 0:
                await update.message.reply_html(
                    "🏷️ <b>Categorização automática</b>\n\n"
                    "Não encontrei lançamentos pendentes sem categoria."
                )
                return ConversationHandler.END

            nao_classificados = max(0, total_pendentes - atualizados)
            await update.message.reply_html(
                "🏷️ <b>Categorização automática concluída</b>\n\n"
                f"• <b>Pendentes analisados:</b> {total_pendentes}\n"
                f"• <b>Categorizados:</b> {atualizados}\n"
                f"• <b>Ainda sem categoria:</b> {nao_classificados}\n\n"
                "Se quiser, eu também posso listar os que ainda ficaram pendentes para revisão manual."
            )
            return ConversationHandler.END

        if _intencao_categoria_mais_gasto(texto_normalizado):
            top_categorias = _resumo_categoria_gastos(db, usuario_db.id, limite=5)
            if not top_categorias:
                await update.message.reply_html(
                    "📊 <b>Categoria com maior gasto</b>\n\n"
                    "Não encontrei despesas suficientes para calcular isso agora."
                )
                return ConversationHandler.END

            topo_nome, topo_valor = top_categorias[0]
            linhas = [
                "📊 <b>Categoria com maior gasto</b>",
                "",
                f"• <b>Maior gasto:</b> {escape(topo_nome)} ({_formatar_valor_brasileiro(topo_valor)})",
                "",
                "<b>Top 5 categorias:</b>",
            ]
            for nome, valor in top_categorias:
                linhas.append(f"• {escape(nome)}: {_formatar_valor_brasileiro(valor)}")
            await update.message.reply_html("\n".join(linhas))
            return ConversationHandler.END

        if _intencao_forma_pagamento_mais_usada(texto_normalizado):
            forma_top, qtd_top, base_util = _forma_pagamento_mais_usada(db, usuario_db.id)
            if not forma_top:
                await update.message.reply_html(
                    "💳 <b>Forma de pagamento mais utilizada</b>\n\n"
                    "Não encontrei pagamentos com forma informada no seu histórico recente."
                )
                return ConversationHandler.END

            await update.message.reply_html(
                "💳 <b>Forma de pagamento mais utilizada</b>\n\n"
                f"• <b>Mais usada:</b> {escape(forma_top)}\n"
                f"• <b>Ocorrências:</b> {qtd_top} de {base_util} lançamentos com forma informada"
            )
            return ConversationHandler.END

        if _intencao_resumo_mes(texto_normalizado):
            await update.message.reply_html(_resumo_mes_local(db, usuario_db.id))
            return ConversationHandler.END

        if _intencao_agendamentos(texto_normalizado):
            agendamentos = (
                db.query(Agendamento)
                .filter(
                    Agendamento.id_usuario == usuario_db.id,
                    Agendamento.ativo.is_(True),
                )
                .order_by(Agendamento.proxima_data_execucao.asc(), Agendamento.id.asc())
                .limit(8)
                .all()
            )
            if not agendamentos:
                await update.message.reply_html(
                    "🗓️ <b>Agendamentos</b>\n\n"
                    "• Receitas previstas: Não encontrei no banco.\n"
                    "• Despesas previstas: Não encontrei no banco.\n"
                    "• Lançamentos programados: Não encontrei no banco."
                )
                return ConversationHandler.END

            receitas = [a for a in agendamentos if str(a.tipo).lower().startswith("entr")]
            despesas = [a for a in agendamentos if not str(a.tipo).lower().startswith("entr")]
            linhas = [
                "🗓️ <b>Agendamentos ativos</b>",
                "",
                f"• <b>Receitas previstas:</b> {len(receitas)}",
                f"• <b>Despesas previstas:</b> {len(despesas)}",
                "",
                "<b>Próximos lançamentos programados:</b>",
            ]
            for ag in agendamentos[:5]:
                data_txt = ag.proxima_data_execucao.strftime("%d/%m/%Y") if ag.proxima_data_execucao else "sem data"
                linhas.append(
                    f"• {escape(ag.descricao)} ({escape(ag.tipo)}): {_formatar_valor_brasileiro(float(ag.valor or 0))} em {escape(data_txt)}"
                )
            await update.message.reply_html("\n".join(linhas))
            return ConversationHandler.END

        if _intencao_score_financeiro(texto_normalizado):
            await update.message.reply_html(
                "📈 <b>Score de saúde financeira</b>\n\n"
                "Ainda não encontrei um score calculado no seu banco. "
                "Posso te mostrar um diagnóstico rápido com saldo, regularidade e concentração de gastos."
            )
            return ConversationHandler.END

        if _intencao_cotacao_externa(texto_normalizado):
            await update.message.reply_html(
                "🌐 <b>Cotações em tempo real</b>\n\n"
                "Não tenho integração ativa de cotação externa neste ambiente agora. "
                "Se quiser, eu sigo com análise baseada só nos seus lançamentos internos."
            )
            return ConversationHandler.END

        contexto_financeiro_str = json.dumps(
            {
                "saldo_disponivel": round(float(saldo or 0), 2),
                "entradas_acumuladas": round(float(entradas or 0), 2),
                "saidas_acumuladas": round(float(saidas or 0), 2),
                "top_categorias": [
                    {"nome": nome, "valor": round(float(valor), 2)}
                    for nome, valor in _resumo_categoria_gastos(db, usuario_db.id, limite=5)
                ],
            },
            ensure_ascii=False,
        )

        system_prompt = PROMPT_ALFREDO_APRIMORADO.format(
            user_name=(usuario_db.nome_completo or update.effective_user.first_name or "usuário"),
            pergunta_usuario=texto_usuario,
            contexto_financeiro_completo=contexto_financeiro_str,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_usuario},
        ]

        completion = None
        try:
            completion = await _groq_chat_completion_async(messages, tools=_ALFREDO_TOOLS, tool_choice="auto")
        except Exception as groq_err:
            logger.warning("Falha na chamada Groq com tools; tentando fallback sem tools: %s", groq_err)
            try:
                completion = await _groq_chat_completion_async(messages)
            except Exception as groq_err_sem_tools:
                logger.warning("Fallback Groq sem tools também falhou: %s", groq_err_sem_tools)

        if not completion:
            resposta_local = _montar_resposta_local_alfredo(texto_usuario, texto_normalizado, db, usuario_db, saldo, entradas, saidas)
            await _enviar_resposta_html_segura(update.message, resposta_local)
            return ConversationHandler.END

        choice = ((completion or {}).get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            resposta_direta = (message.get("content") or "Não consegui processar agora. Tente novamente.").strip()

            # Fallback para capturar vazamentos de JSON na string (ex: registrar_lancamento>{"valor":...})
            if ">" in resposta_direta and "{" in resposta_direta:
                try:
                    intent, json_str = resposta_direta.split(">", 1)
                    json_str = json_str[json_str.find("{"):]
                    args_parse = json.loads(json_str)
                    
                    if "limite" in intent.lower() or "limite" in str(args_parse.get("descricao", "")).lower():
                        fake_fn = "definir_limite_orcamento"
                        if "valor" not in args_parse and "valor_limite" in args_parse:
                            args_parse["valor"] = args_parse["valor_limite"]
                    else:
                        fake_fn = "registrar_lancamento"
                        
                    tool_calls = [{"function": {"name": fake_fn, "arguments": json.dumps(args_parse)}}]
                except Exception:
                    pass

            if not tool_calls:
                await _enviar_resposta_html_segura(update.message, resposta_direta)
                return ConversationHandler.END

        tool_call = tool_calls[0]
        fn = (tool_call.get("function") or {})
        fn_name = fn.get("name")
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}

        if fn_name == "registrar_lancamento":
            descricao = str(args.get("descricao") or "Lançamento").strip()
            categoria = str(args.get("categoria") or "Outros").strip()
            forma_pagamento = _normalizar_forma_pagamento(args.get("forma_pagamento"))
            tipo_transacao = _inferir_tipo_lancamento(texto_usuario, categoria, args.get("tipo"))
            data_lancamento = _normalizar_data_lancamento(args.get("data"))
            try:
                valor = float(str(args.get("valor") or 0).replace(",", "."))
            except (ValueError, TypeError):
                valor = 0.0

            if valor <= 0:
                await update.message.reply_html(
                    "❌ <b>Valor inválido</b>\n\n"
                    "Preciso de um valor maior que zero para preparar o lançamento."
                )
                return ConversationHandler.END

            gate_lanc = plan_allows_feature(db, usuario_db, "lancamentos")
            if not gate_lanc.allowed:
                text, keyboard = upgrade_prompt_for_feature("lancamentos")
                await update.message.reply_html(text, reply_markup=keyboard)
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
            await update.message.reply_html(preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name in {"agendar_despesa", "agendar_receita"}:
            eh_receita = fn_name == "agendar_receita"
            descricao_default = "Receita agendada" if eh_receita else "Despesa agendada"
            descricao = str(args.get("descricao") or descricao_default).strip()
            try:
                valor = float(str(args.get("valor") or 0).replace(",", "."))
            except (ValueError, TypeError):
                valor = 0.0
            data_str = str(args.get("data") or "").strip()
            frequencia = str(args.get("frequencia") or "mensal").strip().lower()
            parcelas = args.get("parcelas")
            try:
                parcelas = int(parcelas) if parcelas is not None else None
            except (ValueError, TypeError):
                parcelas = None

            if valor <= 0 or not data_str:
                await update.message.reply_html(
                    "❌ <b>Dados incompletos</b>\n\n"
                    "Informe descrição, valor (&gt; 0) e data de início em <code>YYYY-MM-DD</code>."
                )
                return ConversationHandler.END

            try:
                data_primeiro = datetime.fromisoformat(data_str).date()
            except ValueError:
                await update.message.reply_html(
                    "❌ <b>Data inválida</b>\n\n"
                    "Use <code>YYYY-MM-DD</code> (ex.: <code>2026-12-12</code>)."
                )
                return ConversationHandler.END

            frequencia_normalizada = frequencia if frequencia in {"unico", "semanal", "mensal"} else "mensal"
            acao_agendamento = "agendar_receita" if eh_receita else "agendar_despesa"

            dados_quick = {
                "acao": acao_agendamento,
                "descricao": descricao,
                "valor": valor,
                "data": data_str,
                "frequencia": frequencia_normalizada,
                "parcelas": parcelas,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick

            parcelas_texto = "indefinido" if parcelas is None else str(parcelas)
            emoji = "💸" if eh_receita else "🗓️"
            titulo = "Confirme o agendamento de receita" if eh_receita else "Confirme o agendamento"
            preview = (
                f"{emoji} <b>{titulo}</b>\n\n"
                f"• <b>Descrição:</b> {escape(descricao)}\n"
                f"• <b>Valor:</b> <code>{_formatar_valor_brasileiro(valor)}</code>\n"
                f"• <b>Início:</b> {data_primeiro.strftime('%d/%m/%Y')}\n"
                f"• <b>Frequência:</b> {escape(frequencia_normalizada)}\n"
                f"• <b>Parcelas:</b> {escape(parcelas_texto)}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                [InlineKeyboardButton("✏️ Editar", callback_data="quick_edit")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
            ])
            await update.message.reply_html(preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name == "criar_meta":
            descricao = str(args.get("descricao") or "Meta").strip()
            try:
                valor_alvo = float(str(args.get("valor_alvo") or 0).replace(",", "."))
            except (ValueError, TypeError):
                valor_alvo = 0.0
            data_meta_str = str(args.get("data_meta") or "").strip()

            if valor_alvo <= 0:
                await update.message.reply_html(
                    "❌ <b>Valor inválido</b>\n\n"
                    "Preciso de um valor alvo maior que zero."
                )
                return ConversationHandler.END

            data_meta = None
            if data_meta_str:
                try:
                    data_meta = datetime.fromisoformat(data_meta_str).date()
                except ValueError:
                    await update.message.reply_html(
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
            await update.message.reply_html(preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name == "definir_limite_orcamento":
            categoria = str(args.get("categoria") or "").strip()
            try:
                valor = float(str(args.get("valor") or 0).replace(",", "."))
            except (ValueError, TypeError):
                valor = 0.0

            if not categoria or valor <= 0:
                await update.message.reply_html(
                    "❌ <b>Dados incompletos</b>\n\n"
                    "Preciso do nome da categoria e um valor maior que zero para criar o limite."
                )
                return ConversationHandler.END

            dados_quick = {
                "acao": "definir_limite_orcamento",
                "categoria": categoria,
                "valor_limite": valor,
                "origem": "alfredo",
            }
            context.user_data["dados_quick"] = dados_quick

            preview = (
                "🚧 <b>Confirme o Limite de Orçamento</b>\n\n"
                f"• <b>Categoria:</b> {escape(categoria)}\n"
                f"• <b>Limite Mensal:</b> <code>{_formatar_valor_brasileiro(valor)}</code>"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Confirmar", callback_data="quick_confirm")],
                [InlineKeyboardButton("❌ Cancelar", callback_data="quick_cancel")],
            ])
            await update.message.reply_html(preview, reply_markup=keyboard)
            return ConversationHandler.END

        if fn_name == "categorizar_lancamentos_pendentes":
            atualizados, total_pendentes = _categorizar_lancamentos_sem_categoria(db, usuario_db.id)
            if total_pendentes == 0:
                await update.message.reply_html(
                    "🏷️ <b>Categorização automática</b>\n\n"
                    "Não encontrei lançamentos pendentes sem categoria no seu histórico."
                )
                return ConversationHandler.END

            nao_classificados = max(0, total_pendentes - atualizados)
            await update.message.reply_html(
                "🏷️ <b>Categorização automática concluída!</b>\n\n"
                f"• <b>Lançamentos analisados:</b> {total_pendentes}\n"
                f"• <b>Categorizados com sucesso:</b> {atualizados}\n"
                f"• <b>Ainda sem categoria:</b> {nao_classificados}\n\n"
                "Pronto! Alfredo organizou os lançamentos usando regras inteligentes."
            )
            return ConversationHandler.END

        if fn_name == "responder_duvida_financeira":
            pergunta = str(args.get("pergunta") or texto_usuario)

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
                sinal = "+" if str(lanc.tipo).lower().startswith("entr") else "-"
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
                if str(lanc.tipo).lower().startswith("entr"):
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

        await update.message.reply_text("Não consegui entender essa ação ainda. Tente reformular a mensagem.")
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

                novo_lanc = Lancamento(
                    id_usuario=usuario_db.id,
                    descricao=dados_quick.get("descricao"),
                    valor=dados_quick.get("valor"),
                    tipo=dados_quick.get("tipo_transacao"),
                    data_transacao=data_tx,
                    forma_pagamento=dados_quick.get("forma_pagamento"),
                    id_categoria=cat_id,
                    id_subcategoria=subcat_id,
                    origem=dados_quick.get("origem", "alfredo")
                )
                db.add(novo_lanc)
                db.commit()
                
                from gerente_financeiro.gamification_utils import give_xp_for_action
                try:
                    await give_xp_for_action(query.from_user.id, "LANCAMENTO_CRIADO_TEXTO", context)
                except Exception:
                    pass
                    
                await query.edit_message_text("✅ Lançamento registrado com sucesso!")
                
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
                cat_nome = dados_quick.get("categoria")
                valor = dados_quick.get("valor_limite")
                
                cat = db.query(Categoria).filter(Categoria.nome.ilike(f"%{cat_nome}%")).first()
                if not cat:
                    await query.edit_message_text(f"❌ Não encontrei a categoria '{cat_nome}'. Tente criar pelo MiniApp.")
                    return ConversationHandler.END
                    
                orc = db.query(OrcamentoCategoria).filter(
                    OrcamentoCategoria.id_usuario == usuario_db.id, 
                    OrcamentoCategoria.id_categoria == cat.id
                ).first()
                
                if orc:
                    orc.valor_limite = valor
                else:
                    db.add(OrcamentoCategoria(
                        id_usuario=usuario_db.id, 
                        id_categoria=cat.id, 
                        valor_limite=valor
                    ))
                db.commit()
                
                from gerente_financeiro.services import limpar_cache_usuario
                try:
                    limpar_cache_usuario(query.from_user.id)
                except Exception:
                    pass
                    
                await query.edit_message_text(
                    f"🚧 <b>Limite Configurado!</b>\n\nAgora você tem um teto de <b>{_formatar_valor_brasileiro(valor)}</b> para <i>{cat.nome}</i>.", 
                    parse_mode='HTML'
                )

        except Exception as e:
            db.rollback()
            logger.error("Erro no quick_action_handler: %s", e, exc_info=True)
            await query.edit_message_text("❌ Ocorreu um erro ao salvar os dados. Tente novamente.")
        finally:
            db.close()
            context.user_data.pop("dados_quick", None)
            context.user_data.pop("quick_lancamento", None)

    return ConversationHandler.END