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
import unicodedata
from html import escape
import requests
from collections import defaultdict
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler
from sqlalchemy import and_, extract
from database.database import get_db, get_or_create_user, buscar_lancamentos_usuario
from models import Lancamento, Usuario, Categoria, Agendamento, Objetivo
import config

try:
    from .analises_ia import get_analisador
except ModuleNotFoundError:
    def get_analisador():
        raise RuntimeError("Modulo opcional analises_ia indisponivel neste ambiente")

logger = logging.getLogger(__name__)

_FORMAS_PAGAMENTO_VALIDAS = {"Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"}


class GroqAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


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


def _detectar_forma_pagamento_no_texto(texto: str) -> str:
    t = (texto or "").lower()
    if "pix" in t:
        return "Pix"
    if "credito" in t or "crédito" in t:
        return "Crédito"
    if "debito" in t or "débito" in t:
        return "Débito"
    if "boleto" in t:
        return "Boleto"
    if "dinheiro" in t or "espécie" in t or "especie" in t:
        return "Dinheiro"
    return "Nao_informado"


def _detectar_categoria_basica(texto: str) -> str:
    t = (texto or "").lower()
    mapa = {
        "aliment": "Alimentação",
        "mercado": "Alimentação",
        "farm": "Saúde",
        "uber": "Transporte",
        "combust": "Transporte",
        "gasolina": "Transporte",
        "aluguel": "Moradia",
        "condominio": "Moradia",
        "condomínio": "Moradia",
        "luz": "Moradia",
        "água": "Moradia",
        "agua": "Moradia",
        "internet": "Moradia",
        "salario": "Salário",
        "salário": "Salário",
        "freela": "Renda Extra",
        "recebi": "Renda",
        "ganhei": "Renda",
    }
    for chave, categoria in mapa.items():
        if chave in t:
            return categoria
    return "Outros"


def _intencao_registro_lancamento(texto: str) -> bool:
    texto = (texto or "").lower()
    gatilhos = [
        "gastei",
        "paguei",
        "comprei",
        "despesa",
        "gasto",
        "recebi",
        "ganhei",
        "entrada",
        "registra",
        "registrar",
        "lançar",
        "lancar",
        "lançamento",
        "lancamento",
    ]
    return any(g in texto for g in gatilhos)


def _extrair_valor_texto(texto: str) -> float | None:
    t = (texto or "").strip()
    if not t:
        return None

    moeda = re.search(r"r\$\s*(-?\d[\d\.,]*)", t, flags=re.IGNORECASE)
    bruto = moeda.group(1) if moeda else None

    if not bruto:
        numeros = re.findall(r"-?\d[\d\.,]*", t)
        if not numeros:
            return None
        bruto = numeros[-1]

    limpo = bruto.replace(".", "").replace(",", ".")
    try:
        valor = float(limpo)
    except ValueError:
        return None

    return abs(valor) if valor != 0 else None


def _extrair_lancamento_do_texto(texto: str) -> dict | None:
    valor = _extrair_valor_texto(texto)
    if valor is None:
        return None

    t = (texto or "").strip()
    t_lower = t.lower()
    tipo = "Saída"
    if any(k in t_lower for k in ["recebi", "ganhei", "entrada", "salário", "salario"]):
        tipo = "Entrada"

    descricao_limpa = re.sub(r"r\$\s*-?\d[\d\.,]*", "", t, flags=re.IGNORECASE)
    descricao_limpa = re.sub(r"-?\d[\d\.,]*", "", descricao_limpa)
    descricao_limpa = re.sub(r"\b(registra|registrar|lancar|lançar|lancamento|lançamento)\b", "", descricao_limpa, flags=re.IGNORECASE)
    descricao_limpa = re.sub(r"\s+", " ", descricao_limpa).strip(" .,:;-")

    return {
        "descricao": descricao_limpa or ("Entrada" if tipo == "Entrada" else "Despesa"),
        "valor": float(valor),
        "tipo": tipo,
        "categoria": _detectar_categoria_basica(t),
        "forma_pagamento": _detectar_forma_pagamento_no_texto(t),
    }


def _registrar_lancamento_local(db, usuario_db: Usuario, dados: dict) -> Lancamento:
    descricao = str(dados.get("descricao") or "Lançamento")
    valor = abs(float(dados.get("valor") or 0))
    tipo_raw = str(dados.get("tipo") or "Saída").strip().lower()
    tipo = "Entrada" if tipo_raw.startswith("entr") else "Saída"
    categoria = str(dados.get("categoria") or "Outros")
    forma_pagamento = _normalizar_forma_pagamento(dados.get("forma_pagamento"))
    id_categoria = _resolve_categoria_id(db, categoria)

    lanc = Lancamento(
        id_usuario=usuario_db.id,
        descricao=descricao,
        valor=valor,
        tipo=tipo,
        data_transacao=datetime.utcnow(),
        forma_pagamento=forma_pagamento if forma_pagamento in _FORMAS_PAGAMENTO_VALIDAS else "Nao_informado",
        id_categoria=id_categoria,
        origem="alfredo",
    )
    db.add(lanc)
    db.commit()
    return lanc


_ALFREDO_TOOLS = [
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
                    "tipo": {"type": "string", "enum": ["Entrada", "Saída"]},
                    "categoria": {"type": "string"},
                    "forma_pagamento": {
                        "type": "string",
                        "enum": ["Pix", "Crédito", "Débito", "Boleto", "Dinheiro", "Nao_informado"],
                    },
                },
                "required": ["descricao", "valor", "categoria"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "agendar_despesa",
            "description": "Agenda uma despesa futura com frequência.",
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {"type": "string"},
                    "valor": {"type": "number"},
                    "data": {"type": "string", "description": "Data no formato YYYY-MM-DD."},
                    "frequencia": {"type": "string", "description": "unico, semanal, mensal"},
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
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body_preview = (response.text or "")[:1500]
        logger.error(
            "Groq chat/completions retornou erro status=%s body=%s",
            response.status_code,
            body_preview,
        )
        raise GroqAPIError(
            f"Groq chat/completions falhou com status {response.status_code}",
            status_code=response.status_code,
            response_body=body_preview,
        ) from exc
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
    texto = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", texto, flags=re.MULTILINE)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", texto)
    texto = re.sub(r"^\s*[-*]\s+", "• ", texto, flags=re.MULTILINE)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


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
    return any(p in texto for p in ["saldo", "quanto tenho", "meu saldo", "saldo total", "quanto sobrou"])


def _normalizar_texto_busca(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto or "").lower())
    sem_acentos = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acentos).strip()


def _contains_any(texto: str, termos: list[str]) -> bool:
    return any(termo in texto for termo in termos)


def _resposta_deterministica_financeira(db, usuario_db: Usuario, texto_usuario: str, saldo: float) -> str | None:
    t = _normalizar_texto_busca(texto_usuario)
    hoje = datetime.utcnow().date()

    # 1) Quanto gastei essa semana?
    if _contains_any(t, ["gastei essa semana", "gastos essa semana", "quanto eu gastei essa semana"]):
        inicio_semana = hoje - timedelta(days=hoje.weekday())
        lancs = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario_db.id,
            Lancamento.data_transacao >= datetime.combine(inicio_semana, datetime.min.time()),
            Lancamento.data_transacao <= datetime.combine(hoje, datetime.max.time()),
        ).all()
        saida = sum(abs(float(l.valor or 0)) for l in lancs if not str(l.tipo).lower().startswith("entr"))
        entrada = sum(float(l.valor or 0) for l in lancs if str(l.tipo).lower().startswith("entr"))
        return (
            "📅 <b>Semana atual</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Saídas:</b> <code>{_formatar_valor_brasileiro(saida)}</code>\n"
            f"<b>Entradas:</b> <code>{_formatar_valor_brasileiro(entrada)}</code>\n"
            f"<b>Resultado da semana:</b> <code>{_formatar_valor_brasileiro(entrada - saida)}</code>"
        )

    # 2) Maior gasto recente
    if _contains_any(t, ["maior gasto recente", "maior gasto", "gasto mais alto"]):
        corte = datetime.combine(hoje - timedelta(days=45), datetime.min.time())
        maior = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario_db.id,
            Lancamento.data_transacao >= corte,
        ).order_by(Lancamento.valor.desc()).first()
        if not maior or str(maior.tipo).lower().startswith("entr"):
            saidas = db.query(Lancamento).filter(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.data_transacao >= corte,
            ).all()
            saidas = [l for l in saidas if not str(l.tipo).lower().startswith("entr")]
            maior = max(saidas, key=lambda x: abs(float(x.valor or 0)), default=None)

        if not maior:
            return "🔎 Não encontrei gastos recentes para analisar."

        return (
            "💥 <b>Maior gasto recente</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Descrição:</b> {escape(maior.descricao or 'Sem descrição')}\n"
            f"<b>Valor:</b> <code>{_formatar_valor_brasileiro(abs(float(maior.valor or 0)))}</code>\n"
            f"<b>Data:</b> {maior.data_transacao.strftime('%d/%m/%Y')}"
        )

    # 3) Dias em que mais gasta
    if _contains_any(t, ["dias eu mais gasto", "quais dias eu mais gasto", "dia da semana"]):
        corte = datetime.combine(hoje - timedelta(days=90), datetime.min.time())
        lancs = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario_db.id,
            Lancamento.data_transacao >= corte,
        ).all()
        saidas = [l for l in lancs if not str(l.tipo).lower().startswith("entr")]
        if not saidas:
            return "📉 Ainda não há gastos suficientes para identificar seus dias de maior consumo."

        dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
        total_por_dia = defaultdict(float)
        for l in saidas:
            total_por_dia[l.data_transacao.weekday()] += abs(float(l.valor or 0))

        ranking = sorted(total_por_dia.items(), key=lambda x: x[1], reverse=True)[:3]
        linhas = [f"• {dias[idx]}: <code>{_formatar_valor_brasileiro(v)}</code>" for idx, v in ranking]
        return "🗓️ <b>Dias com maior gasto</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(linhas)

    # 4) Contas e compromissos de agendamento
    if _contains_any(t, ["conta vencendo hoje", "vencendo hoje", "pagar hoje", "contas tenho pra pagar hoje"]):
        ags = db.query(Agendamento).filter(
            Agendamento.id_usuario == usuario_db.id,
            Agendamento.ativo == True,
            Agendamento.proxima_data_execucao == hoje,
        ).all()
        if not ags:
            return "✅ Hoje não encontrei compromissos agendados para vencimento."
        linhas = [f"• {escape(a.descricao)} — <code>{_formatar_valor_brasileiro(float(a.valor or 0))}</code>" for a in ags]
        total = sum(float(a.valor or 0) for a in ags)
        return "⏰ <b>Vence hoje</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(linhas) + f"\n\n<b>Total:</b> <code>{_formatar_valor_brasileiro(total)}</code>"

    if _contains_any(t, ["vence essa semana", "pagar essa semana", "falta pagar essa semana", "ainda preciso pagar essa semana"]):
        fim = hoje + timedelta(days=7)
        ags = db.query(Agendamento).filter(
            Agendamento.id_usuario == usuario_db.id,
            Agendamento.ativo == True,
            Agendamento.proxima_data_execucao >= hoje,
            Agendamento.proxima_data_execucao <= fim,
        ).order_by(Agendamento.proxima_data_execucao.asc()).all()
        if not ags:
            return "✅ Não há compromissos agendados para os próximos 7 dias."
        linhas = [
            f"• {a.proxima_data_execucao.strftime('%d/%m')} — {escape(a.descricao)} — <code>{_formatar_valor_brasileiro(float(a.valor or 0))}</code>"
            for a in ags
        ]
        total = sum(float(a.valor or 0) for a in ags)
        return "📌 <b>Compromissos da semana</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(linhas) + f"\n\n<b>Total:</b> <code>{_formatar_valor_brasileiro(total)}</code>"

    if _contains_any(t, ["contas atrasadas", "conta que esqueci", "esqueci"]) and "meta" not in t:
        atrasadas = db.query(Agendamento).filter(
            Agendamento.id_usuario == usuario_db.id,
            Agendamento.ativo == True,
            Agendamento.proxima_data_execucao < hoje,
        ).order_by(Agendamento.proxima_data_execucao.asc()).all()
        if not atrasadas:
            return "✅ Não encontrei compromissos atrasados no seu agendamento."
        linhas = [
            f"• {a.proxima_data_execucao.strftime('%d/%m')} — {escape(a.descricao)} — <code>{_formatar_valor_brasileiro(float(a.valor or 0))}</code>"
            for a in atrasadas
        ]
        total = sum(float(a.valor or 0) for a in atrasadas)
        return "🚨 <b>Compromissos atrasados</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(linhas) + f"\n\n<b>Total em atraso:</b> <code>{_formatar_valor_brasileiro(total)}</code>"

    if _contains_any(t, ["contas fixas", "total de contas desse mes", "comprometido", "sobra depois das contas", "o que ainda falta pagar"]):
        fim_mes = datetime(hoje.year + (1 if hoje.month == 12 else 0), 1 if hoje.month == 12 else hoje.month + 1, 1).date() - timedelta(days=1)
        ags_mes = db.query(Agendamento).filter(
            Agendamento.id_usuario == usuario_db.id,
            Agendamento.ativo == True,
            Agendamento.proxima_data_execucao >= hoje,
            Agendamento.proxima_data_execucao <= fim_mes,
        ).all()
        total_comprometido = sum(float(a.valor or 0) for a in ags_mes)
        fixas = [a for a in ags_mes if (a.frequencia or "").lower() in {"mensal", "semanal"}]
        sobra = saldo - total_comprometido
        return (
            "🧾 <b>Compromissos até o fim do mês</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Total agendado:</b> <code>{_formatar_valor_brasileiro(total_comprometido)}</code>\n"
            f"<b>Contas fixas (recorrentes):</b> <code>{len(fixas)}</code>\n"
            f"<b>Sobra estimada após compromissos:</b> <code>{_formatar_valor_brasileiro(sobra)}</code>"
        )

    if _contains_any(t, ["ja paguei aluguel", "ja paguei luz", "ja paguei internet"]):
        inicio_mes = datetime(hoje.year, hoje.month, 1)
        lancs_mes = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario_db.id,
            Lancamento.data_transacao >= inicio_mes,
        ).all()
        descs = [str(l.descricao or "").lower() for l in lancs_mes]
        checks = {
            "aluguel": any("aluguel" in d for d in descs),
            "luz": any("luz" in d or "energia" in d for d in descs),
            "internet": any("internet" in d or "wifi" in d or "wi-fi" in d for d in descs),
        }
        linhas = [f"• {k.title()}: {'✅ Pago' if v else '⚠️ Não encontrado'}" for k, v in checks.items()]
        return "🏠 <b>Status de contas básicas no mês</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(linhas)

    # 5) Gastos por comportamento
    if _contains_any(t, ["ifood", "lanche", "besteira"]):
        inicio_mes = datetime(hoje.year, hoje.month, 1)
        lancs = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario_db.id,
            Lancamento.data_transacao >= inicio_mes,
        ).all()
        gastos = [
            l for l in lancs
            if not str(l.tipo).lower().startswith("entr")
            and any(k in str(l.descricao or "").lower() for k in ["ifood", "lanche", "snack", "delivery", "burg", "pizza"])
        ]
        total = sum(abs(float(l.valor or 0)) for l in gastos)
        return (
            "🍔 <b>Gastos com iFood/lanche no mês</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Transações:</b> <code>{len(gastos)}</code>\n"
            f"<b>Total:</b> <code>{_formatar_valor_brasileiro(total)}</code>"
        )

    if _contains_any(t, ["gastos invisiveis", "pequenos e recorrentes"]):
        corte = datetime.combine(hoje - timedelta(days=60), datetime.min.time())
        lancs = db.query(Lancamento).filter(
            Lancamento.id_usuario == usuario_db.id,
            Lancamento.data_transacao >= corte,
        ).all()
        saidas = [l for l in lancs if not str(l.tipo).lower().startswith("entr") and abs(float(l.valor or 0)) <= 60]
        by_desc = defaultdict(lambda: {"count": 0, "total": 0.0})
        for l in saidas:
            desc = (l.descricao or "sem descricao").strip().lower()
            by_desc[desc]["count"] += 1
            by_desc[desc]["total"] += abs(float(l.valor or 0))

        recorrentes = [(d, v) for d, v in by_desc.items() if v["count"] >= 2]
        recorrentes = sorted(recorrentes, key=lambda x: x[1]["total"], reverse=True)[:5]
        if not recorrentes:
            return "🔎 Não encontrei microgastos recorrentes relevantes nos últimos 60 dias."

        linhas = [
            f"• {escape(desc[:30])} — {dados['count']}x — <code>{_formatar_valor_brasileiro(dados['total'])}</code>"
            for desc, dados in recorrentes
        ]
        return "🕵️ <b>Gastos invisíveis (pequenos e recorrentes)</b>\n━━━━━━━━━━━━━━━━━━\n\n" + "\n".join(linhas)

    return None


def _montar_contexto_financeiro_detalhado(db, usuario_db: Usuario, saldo: float, entradas: float, saidas: float) -> str:
    hoje = datetime.utcnow().date()
    inicio_mes = datetime(hoje.year, hoje.month, 1)
    inicio_mes_passado = (inicio_mes - timedelta(days=1)).replace(day=1)
    fim_mes_passado = inicio_mes - timedelta(seconds=1)

    lancs_mes = db.query(Lancamento).filter(
        Lancamento.id_usuario == usuario_db.id,
        Lancamento.data_transacao >= inicio_mes,
    ).all()
    lancs_mes_passado = db.query(Lancamento).filter(
        Lancamento.id_usuario == usuario_db.id,
        Lancamento.data_transacao >= inicio_mes_passado,
        Lancamento.data_transacao <= fim_mes_passado,
    ).all()

    despesa_mes = sum(abs(float(l.valor or 0)) for l in lancs_mes if not str(l.tipo).lower().startswith("entr"))
    receita_mes = sum(float(l.valor or 0) for l in lancs_mes if str(l.tipo).lower().startswith("entr"))
    despesa_mes_passado = sum(abs(float(l.valor or 0)) for l in lancs_mes_passado if not str(l.tipo).lower().startswith("entr"))

    top_categoria = defaultdict(float)
    pagamento_count = defaultdict(int)
    for l in lancs_mes:
        if not str(l.tipo).lower().startswith("entr"):
            nome_cat = (l.categoria.nome if l.categoria and l.categoria.nome else "Sem categoria")
            top_categoria[nome_cat] += abs(float(l.valor or 0))
        pagamento_count[_normalizar_forma_pagamento(l.forma_pagamento)] += 1

    top_categoria_ordenada = sorted(top_categoria.items(), key=lambda x: x[1], reverse=True)[:4]
    top_pagamentos = sorted(pagamento_count.items(), key=lambda x: x[1], reverse=True)[:3]

    inicio_semana = hoje - timedelta(days=hoje.weekday())
    gastos_semana = sum(
        abs(float(l.valor or 0)) for l in lancs_mes
        if not str(l.tipo).lower().startswith("entr") and l.data_transacao.date() >= inicio_semana
    )

    fim_7_dias = hoje + timedelta(days=7)
    ags_prox_7 = db.query(Agendamento).filter(
        Agendamento.id_usuario == usuario_db.id,
        Agendamento.ativo == True,
        Agendamento.proxima_data_execucao >= hoje,
        Agendamento.proxima_data_execucao <= fim_7_dias,
    ).all()
    ags_atrasados = db.query(Agendamento).filter(
        Agendamento.id_usuario == usuario_db.id,
        Agendamento.ativo == True,
        Agendamento.proxima_data_execucao < hoje,
    ).all()

    metas = db.query(Objetivo).filter(Objetivo.id_usuario == usuario_db.id).all()
    metas_resumo = [
        f"{m.descricao}: atual R$ {float(m.valor_atual or 0):.2f} / meta R$ {float(m.valor_meta or 0):.2f}"
        for m in metas[:3]
    ]

    top_categoria_txt = ", ".join(f"{nome} (R$ {valor:.2f})" for nome, valor in top_categoria_ordenada) or "Sem dados"
    top_pagamento_txt = ", ".join(f"{nome} ({q}x)" for nome, q in top_pagamentos) or "Sem dados"

    return (
        f"Saldo acumulado: R$ {saldo:.2f}\n"
        f"Entradas acumuladas: R$ {entradas:.2f}\n"
        f"Saídas acumuladas: R$ {saidas:.2f}\n"
        f"Receita no mês atual: R$ {receita_mes:.2f}\n"
        f"Despesa no mês atual: R$ {despesa_mes:.2f}\n"
        f"Despesa no mês passado: R$ {despesa_mes_passado:.2f}\n"
        f"Gasto na semana atual: R$ {gastos_semana:.2f}\n"
        f"Top categorias do mês: {top_categoria_txt}\n"
        f"Formas de pagamento mais usadas: {top_pagamento_txt}\n"
        f"Agendamentos vencendo em 7 dias: {len(ags_prox_7)}\n"
        f"Agendamentos atrasados: {len(ags_atrasados)}\n"
        f"Resumo de metas: {', '.join(metas_resumo) if metas_resumo else 'Sem metas cadastradas'}"
    )


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

        texto_normalizado = texto_usuario.strip().lower()

        if _intencao_ultimo_lancamento(texto_normalizado):
            ultimos = buscar_lancamentos_usuario(telegram_user_id=update.effective_user.id, limit=1)
            if not ultimos:
                await update.message.reply_html(
                    "🔎 <b>Nenhum lançamento encontrado</b>\n\n"
                    "Você ainda não tem lançamentos registrados no seu banco."
                )
                return ConversationHandler.END

            await update.message.reply_html(_formatar_lancamento_card(ultimos[0]))
            return ConversationHandler.END

        if _intencao_saldo(texto_normalizado):
            saldo_msg = (
                "💰 <b>Seu saldo atual</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Saldo:</b> <code>{_formatar_valor_brasileiro(saldo)}</code>\n"
                f"<b>Entradas acumuladas:</b> <code>{_formatar_valor_brasileiro(entradas)}</code>\n"
                f"<b>Saídas acumuladas:</b> <code>{_formatar_valor_brasileiro(saidas)}</code>"
            )
            await update.message.reply_html(saldo_msg)
            return ConversationHandler.END

        resposta_deterministica = _resposta_deterministica_financeira(db, usuario_db, texto_usuario, saldo)
        if resposta_deterministica:
            await update.message.reply_html(_formatar_resposta_html(resposta_deterministica))
            return ConversationHandler.END

        system_prompt = (
            "Você é Alfredo, um Despachante Financeiro. "
            "Sempre escolha UMA tool quando houver intenção acionável. "
            "Use responder_duvida_financeira para perguntas gerais. "
            "Responda em português do Brasil usando HTML simples para Telegram. "
            "Nunca use markdown com asteriscos. "
            "Não invente valores, datas, categorias ou lançamentos ausentes. "
            "Se faltar dado no contexto ou no banco, diga claramente que não encontrou a informação. "
            "Tente deduzir a forma de pagamento da mensagem do usuário. "
            "Se não houver indicação explícita, preencha obrigatoriamente como Nao_informado."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_usuario},
        ]

        intencao_registro = _intencao_registro_lancamento(texto_normalizado)

        try:
            completion = await _groq_chat_completion_async(messages, tools=_ALFREDO_TOOLS, tool_choice="auto")
        except Exception as exc:
            logger.error("Falha no Groq com tools no Alfredo: %s", exc, exc_info=True)

            if intencao_registro:
                extraido = _extrair_lancamento_do_texto(texto_usuario)
                if extraido and extraido.get("valor", 0) > 0:
                    _registrar_lancamento_local(db, usuario_db, extraido)
                    await update.message.reply_text(
                        f"✅ Lançamento de R$ {extraido['valor']:.2f} em {escape(extraido['categoria'])} registrado!"
                    )
                    return ConversationHandler.END

            fallback_messages = [
                {
                    "role": "system",
                    "content": (
                        "Você é Alfredo. O modo de tools está indisponível agora. "
                        "Responda sem inventar números, lançamentos ou confirmações de ações. "
                        "Se o usuário pedir para registrar algo, peça os dados faltantes de forma objetiva."
                    ),
                },
                {"role": "user", "content": texto_usuario},
            ]
            fallback_completion = await _groq_chat_completion_async(fallback_messages)
            fallback_choice = ((fallback_completion or {}).get("choices") or [{}])[0]
            fallback_message = fallback_choice.get("message") or {}
            fallback_text = (fallback_message.get("content") or "Não consegui processar agora. Tente novamente.").strip()
            await update.message.reply_html(_formatar_resposta_html(fallback_text))
            return ConversationHandler.END

        choice = ((completion or {}).get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            if intencao_registro:
                extraido = _extrair_lancamento_do_texto(texto_usuario)
                if extraido and extraido.get("valor", 0) > 0:
                    _registrar_lancamento_local(db, usuario_db, extraido)
                    await update.message.reply_text(
                        f"✅ Lançamento de R$ {extraido['valor']:.2f} em {escape(extraido['categoria'])} registrado!"
                    )
                    return ConversationHandler.END

                await update.message.reply_text(
                    "❌ Não consegui registrar automaticamente. Me envie no formato: "
                    "'gastei 120,50 no mercado no pix'."
                )
                return ConversationHandler.END

            resposta_direta = (message.get("content") or "Não consegui processar agora. Tente novamente.").strip()
            await update.message.reply_html(_formatar_resposta_html(resposta_direta))
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
            valor = float(args.get("valor") or 0)
            if valor == 0:
                await update.message.reply_text("❌ Preciso de um valor maior que zero para registrar o lançamento.")
                return ConversationHandler.END

            dados_lancamento = {
                "descricao": str(args.get("descricao") or "Lançamento"),
                "valor": abs(valor),
                "tipo": str(args.get("tipo") or ("Entrada" if valor < 0 else "Saída")),
                "categoria": str(args.get("categoria") or "Outros"),
                "forma_pagamento": str(args.get("forma_pagamento") or "Nao_informado"),
            }
            _registrar_lancamento_local(db, usuario_db, dados_lancamento)
            await update.message.reply_text(
                f"✅ Lançamento de R$ {abs(valor):.2f} em {escape(dados_lancamento['categoria'])} registrado!"
            )
            return ConversationHandler.END

        if fn_name == "agendar_despesa":
            descricao = str(args.get("descricao") or "Despesa agendada")
            valor = float(args.get("valor") or 0)
            data_str = str(args.get("data") or "").strip()
            frequencia = str(args.get("frequencia") or "mensal").strip().lower()

            if valor <= 0 or not data_str:
                await update.message.reply_text("❌ Para agendar, preciso de descrição, valor e data (YYYY-MM-DD).")
                return ConversationHandler.END

            try:
                data_primeiro = datetime.fromisoformat(data_str).date()
            except ValueError:
                await update.message.reply_text("❌ Data inválida. Use o formato YYYY-MM-DD.")
                return ConversationHandler.END

            ag = Agendamento(
                id_usuario=usuario_db.id,
                descricao=descricao,
                valor=valor,
                tipo="Saída",
                frequencia=frequencia if frequencia in {"unico", "semanal", "mensal"} else "mensal",
                data_primeiro_evento=data_primeiro,
                proxima_data_execucao=data_primeiro,
                ativo=True,
                parcela_atual=0,
            )
            db.add(ag)
            db.commit()
            await update.message.reply_text(f"✅ Despesa '{escape(descricao)}' agendada para {data_primeiro.strftime('%d/%m/%Y')} ({ag.frequencia}).")
            return ConversationHandler.END

        if fn_name == "criar_meta":
            descricao = str(args.get("descricao") or "Meta")
            valor_alvo = float(args.get("valor_alvo") or 0)
            if valor_alvo <= 0:
                await update.message.reply_text("❌ Preciso de um valor alvo maior que zero para criar a meta.")
                return ConversationHandler.END

            hoje = datetime.utcnow().date()
            meta = Objetivo(
                id_usuario=usuario_db.id,
                descricao=descricao,
                valor_meta=valor_alvo,
                valor_atual=0,
                data_meta=datetime(hoje.year, 12, 31).date(),
            )
            db.add(meta)
            db.commit()
            await update.message.reply_text(f"🎯 Meta '{escape(descricao)}' criada com alvo de R$ {valor_alvo:.2f}.")
            return ConversationHandler.END

        if fn_name == "responder_duvida_financeira":
            pergunta = str(args.get("pergunta") or texto_usuario)
            contexto_detalhado = _montar_contexto_financeiro_detalhado(db, usuario_db, saldo, entradas, saidas)
            contextual_messages = [
                {
                    "role": "system",
                    "content": (
                        "Responda em português do Brasil, objetivo e útil. "
                        "Use apenas os dados informados no contexto financeiro. "
                        "Não invente números, contas ou transações. "
                        "Se um dado não estiver disponível, diga que não encontrou no banco. "
                        "Use formatação curta amigável para Telegram em HTML simples. "
                        "Sempre priorize conclusões quantitativas quando houver dados no contexto."
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
                        f"- Contexto detalhado:\n{contexto_detalhado}\n"
                    ),
                },
            ]
            answer_completion = await _groq_chat_completion_async(contextual_messages)
            answer = (((answer_completion or {}).get("choices") or [{}])[0].get("message") or {}).get("content")
            answer = (answer or "Não consegui responder agora, tente novamente.").strip()
            await update.message.reply_html(_formatar_resposta_html(answer))
            return ConversationHandler.END

        await update.message.reply_text("Não consegui entender essa ação ainda. Tente reformular a mensagem.")
        return ConversationHandler.END
    except Exception as exc:
        logger.error("Erro no roteador Alfredo: %s", exc, exc_info=True)
        await update.message.reply_text("❌ Tive um problema ao processar sua mensagem. Tente novamente em instantes.")
        return ConversationHandler.END
    finally:
        db.close()


async def comando_insights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /insights - Análise inteligente dos gastos do mês
    """
    user = update.effective_user
    await update.message.reply_text("🤖 Analisando seus gastos com IA... Aguarde um momento.")
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        # Buscar transações do mês atual
        hoje = datetime.now()
        transacoes = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                extract('year', Lancamento.data_transacao) == hoje.year,
                extract('month', Lancamento.data_transacao) == hoje.month
            )
        ).all()
        
        if not transacoes:
            await update.message.reply_html(
                "📊 <b>Sem dados para análise</b>\n\n"
                "Você ainda não tem gastos registrados este mês.\n"
                "Use /lancamento para adicionar transações!"
            )
            return
        
        # Converter para formato dict
        transacoes_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes
        ]
        
        # Gerar análise com IA
        analisador = get_analisador()
        analise = analisador.analisar_padrao_gastos(transacoes_dict, periodo_dias=30)
        
        await update.message.reply_html(
            f"🤖 <b>Análise Inteligente - {hoje.strftime('%B/%Y')}</b>\n\n"
            f"{analise}\n\n"
            f"💡 <i>Use /economia para receber sugestões personalizadas!</i>"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no comando insights: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao gerar a análise. Tente novamente mais tarde."
        )
    finally:
        db.close()


async def comando_economia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /economia [valor] - Sugestões de como economizar
    Exemplo: /economia 500
    """
    user = update.effective_user
    
    # Verificar se foi passado o valor meta
    meta_economia = 300.0  # Valor padrão
    if context.args:
        try:
            meta_economia = float(context.args[0].replace(',', '.'))
        except ValueError:
            await update.message.reply_text(
                "❌ Valor inválido! Use: /economia 500 (para economizar R$ 500)"
            )
            return
    
    await update.message.reply_text(
        f"💡 Gerando sugestões para economizar R$ {meta_economia:.2f}..."
    )
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        # Buscar transações dos últimos 30 dias
        hoje = datetime.now()
        data_inicio = hoje - timedelta(days=30)
        
        transacoes = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                Lancamento.data_transacao >= data_inicio
            )
        ).all()
        
        if not transacoes:
            await update.message.reply_html(
                "📊 <b>Sem dados para análise</b>\n\n"
                "Você ainda não tem gastos registrados.\n"
                "Use /lancamento para adicionar transações!"
            )
            return
        
        # Converter para formato dict
        transacoes_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes
        ]
        
        # Gerar sugestões com IA
        analisador = get_analisador()
        sugestoes = analisador.sugerir_economia(transacoes_dict, meta_economia)
        
        await update.message.reply_html(
            f"💡 <b>Sugestões Personalizadas de Economia</b>\n"
            f"🎯 Meta: R$ {meta_economia:.2f}/mês\n\n"
            f"{sugestoes}\n\n"
            f"💪 <i>Pequenas mudanças fazem grande diferença!</i>"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no comando economia: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao gerar sugestões. Tente novamente mais tarde."
        )
    finally:
        db.close()


async def comando_comparar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /comparar - Compara gastos do mês atual com o anterior
    """
    user = update.effective_user
    await update.message.reply_text("📊 Comparando seus gastos com o mês anterior...")
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        hoje = datetime.now()
        
        # Mês atual
        transacoes_atual = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                extract('year', Lancamento.data_transacao) == hoje.year,
                extract('month', Lancamento.data_transacao) == hoje.month
            )
        ).all()
        
        # Mês anterior
        mes_anterior = hoje.replace(day=1) - timedelta(days=1)
        transacoes_anterior = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                extract('year', Lancamento.data_transacao) == mes_anterior.year,
                extract('month', Lancamento.data_transacao) == mes_anterior.month
            )
        ).all()
        
        if not transacoes_atual and not transacoes_anterior:
            await update.message.reply_html(
                "📊 <b>Sem dados para comparação</b>\n\n"
                "Você ainda não tem gastos registrados nos últimos 2 meses."
            )
            return
        
        # Converter para formato dict
        atual_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes_atual
        ]
        
        anterior_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes_anterior
        ]
        
        # Gerar comparação com IA
        analisador = get_analisador()
        comparacao = analisador.comparar_periodos(atual_dict, anterior_dict)
        
        mes_atual_nome = hoje.strftime('%B')
        mes_anterior_nome = mes_anterior.strftime('%B')
        
        await update.message.reply_html(
            f"📊 <b>Comparação de Gastos</b>\n"
            f"📅 {mes_anterior_nome} vs {mes_atual_nome}\n\n"
            f"{comparacao}\n\n"
            f"💡 <i>Use /insights para análise detalhada do mês atual!</i>"
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no comando comparar: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao comparar períodos. Tente novamente mais tarde."
        )
    finally:
        db.close()


async def comando_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /alertas - Detecta gastos anormais ou suspeitos
    """
    user = update.effective_user
    await update.message.reply_text("🔍 Analisando padrões e procurando anomalias...")
    
    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, user.id, user.full_name)
        
        hoje = datetime.now()
        
        # Transações dos últimos 30 dias (recentes)
        data_inicio_recente = hoje - timedelta(days=30)
        transacoes_recentes = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                Lancamento.data_transacao >= data_inicio_recente
            )
        ).all()
        
        # Histórico dos últimos 6 meses (para comparação)
        data_inicio_historico = hoje - timedelta(days=180)
        historico = db.query(Lancamento).filter(
            and_(
                Lancamento.id_usuario == usuario_db.id,
                Lancamento.tipo == 'Saída',
                Lancamento.data_transacao >= data_inicio_historico,
                Lancamento.data_transacao < data_inicio_recente
            )
        ).all()
        
        if not transacoes_recentes:
            await update.message.reply_html(
                "📊 <b>Sem dados recentes</b>\n\n"
                "Você não tem gastos registrados nos últimos 30 dias."
            )
            return
        
        if not historico:
            await update.message.reply_html(
                "📊 <b>Sem histórico para comparação</b>\n\n"
                "Preciso de pelo menos 2 meses de dados para detectar anomalias.\n"
                "Continue usando o bot e em breve terei insights para você!"
            )
            return
        
        # Converter para formato dict
        recentes_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in transacoes_recentes
        ]
        
        historico_dict = [
            {
                'data': t.data_transacao.strftime('%d/%m/%Y'),
                'descricao': t.descricao,
                'valor': float(t.valor),
                'categoria': t.categoria.nome if t.categoria else 'Outros'
            }
            for t in historico
        ]
        
        # Detectar anomalias
        analisador = get_analisador()
        anomalias = analisador.detectar_anomalias(recentes_dict, historico_dict)
        
        if not anomalias:
            await update.message.reply_html(
                "✅ <b>Tudo Normal!</b>\n\n"
                "Não detectei nenhum gasto anormal nos últimos 30 dias.\n"
                "Seus gastos estão dentro do padrão esperado. 👍"
            )
        else:
            texto_alertas = "🚨 <b>Alertas Detectados</b>\n\n"
            texto_alertas += f"Encontrei <b>{len(anomalias)}</b> gasto(s) fora do padrão:\n\n"
            
            for idx, anomalia in enumerate(anomalias[:5], 1):  # Máximo 5 alertas
                t = anomalia['transacao']
                motivo = anomalia['motivo']
                severidade = anomalia['severidade']
                
                emoji = "🔴" if severidade == 'alta' else "🟡"
                
                texto_alertas += (
                    f"{emoji} <b>{idx}. {t['descricao']}</b>\n"
                    f"   Valor: R$ {t['valor']:.2f}\n"
                    f"   {motivo}\n\n"
                )
            
            if len(anomalias) > 5:
                texto_alertas += f"... e mais {len(anomalias) - 5} alertas.\n\n"
            
            texto_alertas += "💡 <i>Verifique se estes gastos estão corretos!</i>"
            
            await update.message.reply_html(texto_alertas)
        
    except Exception as e:
        logger.error(f"❌ Erro no comando alertas: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Ops! Ocorreu um erro ao analisar alertas. Tente novamente mais tarde."
        )
    finally:
        db.close()


# Handlers para registrar no bot
insights_handler = CommandHandler('insights', comando_insights)
economia_handler = CommandHandler('economia', comando_economia)
comparar_handler = CommandHandler('comparar', comando_comparar)
alertas_handler = CommandHandler('alertas', comando_alertas)
