import json
import logging
import os
import re
import uuid
import asyncio
import time
import unicodedata
import io
import hashlib
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote, urlencode, urlparse

import google.generativeai as genai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from database.database import get_db, get_or_create_user
from models import Conta
from .services import salvar_transacoes_generica, limpar_cache_usuario
from .fatura_draft_store import create_fatura_draft, set_pending_editor_token, get_fatura_draft, pop_fatura_draft
from .states import (
    FATURA_AWAIT_FILE,
    FATURA_CONFIRMATION_STATE,
    FATURA_TRAIN_CONSENT,
    FATURA_TRAIN_BANK,
)
from .gamification_utils import give_xp_for_action, touch_user_interaction
from .monetization import ensure_user_plan_state, plan_allows_feature, upgrade_prompt_for_feature

logger = logging.getLogger(__name__)

MAX_PDF_SIZE_MB = int(os.getenv("FATURA_MAX_PDF_SIZE_MB", "100"))
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024
MAX_PDF_PARSE_SECONDS = int(os.getenv("FATURA_PARSE_TIMEOUT_SECONDS", "300"))
_PARSE_CACHE_TTL_SECONDS = int(os.getenv("FATURA_PARSE_CACHE_TTL_SECONDS", "1800"))
_PARSE_CACHE_LOCK = threading.Lock()
_PARSE_CACHE: dict[str, dict] = {}

# ─────────────────────────────────────────────────────────────────────────────
# Modelos Gemini em ordem de preferência.
# IDs validados contra a API pública de 2025/2026.
# ─────────────────────────────────────────────────────────────────────────────
_GEMINI_MODEL_CANDIDATES = [
    "gemini-2.5-flash",           # Flash 2.5 – melhor custo/benefício com alta cota
    "gemini-2.0-flash",           # Flash 2.0 – fallback estável
    "gemini-2.5-pro",             # Pro 2.5  – mais inteligente, cota menor
    "gemini-1.5-flash",           # Flash 1.5 – último recurso, amplamente disponível
]

# Tolerância percentual para validação matemática.
# 25 % é razoável pois faturas incluem IOF, ajustes de câmbio e itens
# que o banco omite do detalhamento mas inclui no total.
_MATH_TOLERANCE_PCT = 0.25


def _fmt_brl(value: float) -> str:
    normalized = f"{abs(float(value)):.2f}".replace(".", ",")
    return f"R$ {normalized}"


def _get_parse_cache_key(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _cleanup_parse_cache() -> None:
    now = time.time()
    expired = [key for key, item in _PARSE_CACHE.items() if item.get("expires_at", 0) <= now]
    for key in expired:
        _PARSE_CACHE.pop(key, None)


def _serialize_parse_transacoes(transacoes: List[Dict]) -> List[Dict]:
    serializadas: List[Dict] = []
    for item in transacoes:
        novo = dict(item)
        if isinstance(novo.get("data_transacao"), datetime):
            novo["data_transacao"] = novo["data_transacao"].isoformat()
        serializadas.append(novo)
    return serializadas


def _deserialize_parse_transacoes(transacoes: List[Dict]) -> List[Dict]:
    desserializadas: List[Dict] = []
    for item in transacoes:
        novo = dict(item)
        data_raw = novo.get("data_transacao")
        if isinstance(data_raw, str):
            try:
                novo["data_transacao"] = datetime.fromisoformat(data_raw)
            except Exception:
                pass
        desserializadas.append(novo)
    return desserializadas


def _get_cached_parse_result(file_bytes: bytes) -> tuple[List[Dict], int, str, float] | None:
    cache_key = _get_parse_cache_key(file_bytes)
    with _PARSE_CACHE_LOCK:
        _cleanup_parse_cache()
        item = _PARSE_CACHE.get(cache_key)
        if not item:
            return None
        # Só reutiliza cache de resultados não-parciais
        if item.get("is_partial"):
            return None
        cached = item.get("result")
        if not cached:
            return None
        transacoes, ignoradas, origem_label, total_pdf = cached
        return _deserialize_parse_transacoes(transacoes), int(ignoradas), str(origem_label), float(total_pdf)


def _set_cached_parse_result(
    file_bytes: bytes,
    result: tuple[List[Dict], int, str, float],
    is_partial: bool = False,
) -> None:
    cache_key = _get_parse_cache_key(file_bytes)
    transacoes, ignoradas, origem_label, total_pdf = result
    with _PARSE_CACHE_LOCK:
        _cleanup_parse_cache()
        _PARSE_CACHE[cache_key] = {
            "result": (
                _serialize_parse_transacoes(transacoes),
                int(ignoradas),
                str(origem_label),
                float(total_pdf),
            ),
            "is_partial": is_partial,
            "expires_at": time.time() + _PARSE_CACHE_TTL_SECONDS,
        }


def _compact_desc(text: str, max_len: int = 42) -> str:
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "..."


def _get_fatura_webapp_url(page: str, token: str) -> str:
    base_url = os.getenv("DASHBOARD_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:5000"
    base_url = str(base_url).strip().rstrip("/")

    if not base_url.startswith(("http://", "https://")):
        if base_url.startswith(("localhost", "127.0.0.1")):
            base_url = f"http://{base_url}"
        else:
            base_url = f"https://{base_url}"

    parsed = urlparse(base_url)
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
        base_url = base_url.replace("http://", "https://", 1)

    params = {
        "entry": "fatura_edit",
        "page": page,
        "fatura_token": token,
        "v": str(int(time.time())),
    }
    return f"{base_url}/webapp?{urlencode(params)}"


_MESES_MAP = {
    "jan": 1, "janeiro": 1,
    "feb": 2, "fev": 2, "fevereiro": 2,
    "mar": 3, "marco": 3, "março": 3,
    "apr": 4, "abr": 4, "abril": 4,
    "may": 5, "mai": 5, "maio": 5,
    "jun": 6, "junho": 6,
    "jul": 7, "julho": 7,
    "aug": 8, "ago": 8, "agosto": 8,
    "sep": 9, "set": 9, "setembro": 9,
    "oct": 10, "out": 10, "outubro": 10,
    "nov": 11, "novembro": 11,
    "dec": 12, "dez": 12, "dezembro": 12,
}

_SECAO_ANCORAS = {
    "compras": [
        "compras (cartão", "compras (cartao", "despesas da fatura",
        "transações de", "transacoes de", "lançamentos", "lancamentos",
        "detalhamento", "gastos do mes", "gastos do mês", "movimentacao",
        "movimentação", "compras nacionais", "compras internacionais", "servicos nps",
    ],
    "parceladas": [
        "compras parceladas", "parceladas (cartão", "parceladas (cartao",
        "parcelamentos", "transações parceladas", "lancamentos parcelados",
        "compras parceladas nps",
    ],
    "outros": [
        "outros (cartão", "outros (cartao", "encargos", "anuidade", "taxas",
        "tarifas", "serviços", "servicos", "movimentacoes de encargos",
        "encargos e tarifas",
    ],
}

_SECAO_FIM = [
    "total compras", "total compras parceladas", "total outros",
    "total final", "total a pagar", "pagamento minimo",
]

_DESC_BLOQUEADA = [
    "obrigado pelo pagamento", "pagamento efetuado", "pagamento recebido",
    "total da fatura anterior", "saldo anterior", "saldo credito rotativo",
    "saldo crédito rotativo", "valor do pagamento", "saldo a pagar",
    "limite", "demonstrativo",
]


def _normalizar_texto_parser(valor: str) -> str:
    texto = (valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", texto)


def _extrair_linhas_com_pdfplumber(file_bytes: bytes) -> list[str]:
    import pdfplumber
    linhas: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(
                keep_blank_chars=False,
                use_text_flow=True,
                x_tolerance=2,
                y_tolerance=3,
                extra_attrs=["x0", "top"],
            ) or []

            if words:
                grupos: list[dict] = []
                for word in sorted(words, key=lambda w: (round(float(w["top"]), 1), float(w["x0"]))):
                    top = float(word["top"])
                    texto = str(word.get("text") or "").strip()
                    if not texto:
                        continue
                    grupo = None
                    for existente in grupos:
                        if abs(existente["top"] - top) <= 3:
                            grupo = existente
                            break
                    if grupo is None:
                        grupo = {"top": top, "words": []}
                        grupos.append(grupo)
                    grupo["words"].append((float(word["x0"]), texto))

                for grupo in grupos:
                    textos = [texto for _, texto in sorted(grupo["words"], key=lambda item: item[0])]
                    linha = re.sub(r"\s+", " ", " ".join(textos)).strip()
                    if linha:
                        linhas.append(linha)
                continue

            page_text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            for line in page_text.splitlines():
                clean = re.sub(r"\s+", " ", line).strip()
                if clean:
                    linhas.append(clean)
    return linhas


def _extrair_texto_pdf_local(file_bytes: bytes) -> list[str]:
    try:
        return _extrair_linhas_com_pdfplumber(file_bytes)
    except Exception as exc:
        logger.warning("Falha no parser visual com pdfplumber; usando fallback fitz: %s", exc)

    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    linhas: list[str] = []
    try:
        for page in doc:
            page_text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE) or ""
            for line in page_text.splitlines():
                clean = re.sub(r"\s+", " ", line).strip()
                if clean:
                    linhas.append(clean)
    finally:
        doc.close()
    return linhas


def _detectar_referencia_fatura(linhas: list[str]) -> tuple[int, int]:
    texto = "\n".join(linhas[:200]).lower()
    match_venc = re.search(r"vencimento:?\s*(\d{2})/(\d{2})/(\d{4})", texto)
    if match_venc:
        return int(match_venc.group(2)), int(match_venc.group(3))

    ano_fatura = datetime.now().year
    match_ano = re.search(r"\b(20\d{2})\b", texto)
    if match_ano:
        ano_fatura = int(match_ano.group(1))

    for nome_mes, num_mes in _MESES_MAP.items():
        if f"{nome_mes}/{ano_fatura}" in texto or f"{nome_mes} {ano_fatura}" in texto:
            return num_mes, ano_fatura

    return datetime.now().month, ano_fatura


def _resolver_ano_transacao(dia: int, mes: int, mes_ref: int, ano_ref: int) -> int:
    if mes == 12 and mes_ref == 1:
        return ano_ref - 1
    return ano_ref


def _detectar_banco_fatura(texto: str) -> str:
    texto_norm = _normalizar_texto_parser(texto)
    bancos = [
        ("Nubank", ["nubank"]),
        ("Inter", ["inter"]),
        ("Caixa", ["caixa", "cartoes caixa", "cartões caixa"]),
        ("Bradesco", ["bradesco"]),
        ("Itaú", ["itau", "itaú"]),
        ("Santander", ["santander"]),
        ("C6", ["c6 bank", "c6bank"]),
        ("XP", ["xp investimentos", "xp card"]),
    ]
    for nome, termos in bancos:
        if any(termo in texto_norm for termo in termos):
            return nome
    return "Desconhecido"


def _detectar_secao_linha(linha: str) -> str | None:
    linha_norm = _normalizar_texto_parser(linha)
    for secao, ancoras in _SECAO_ANCORAS.items():
        if any(ancora in linha_norm for ancora in ancoras):
            return secao
    return None


def _linha_indica_fim_secao(linha: str) -> bool:
    linha_norm = _normalizar_texto_parser(linha)
    return any(marcador in linha_norm for marcador in _SECAO_FIM)


def _parse_valor_fatura(raw_amount: str, descricao: str) -> float | None:
    bruto = (raw_amount or "").strip()
    if not bruto:
        return None

    marker = None
    if bruto.upper().endswith(("D", "C")):
        marker = bruto[-1].upper()
        bruto = bruto[:-1].strip()

    bruto = bruto.replace("R$", "").replace("US$", "").replace("U$$", "").strip()
    negativo_expresso = bruto.startswith("-")
    bruto = bruto.lstrip("+-").strip()
    bruto = bruto.replace(".", "").replace(",", ".")
    try:
        valor = float(bruto)
    except Exception:
        return None

    descricao_norm = _normalizar_texto_parser(descricao)
    if marker == "C":
        return abs(valor)
    if marker == "D":
        return -abs(valor)
    if negativo_expresso:
        return -abs(valor)
    if any(token in descricao_norm for token in ["estorno", "ajuste cred", "credito", "crédito", "cashback"]):
        return abs(valor)
    return -abs(valor)


def _parse_data_fatura_local(raw_data: str, mes_ref: int, ano_ref: int) -> datetime | None:
    data = (raw_data or "").strip().replace(".", "")
    if not data:
        return None

    if re.fullmatch(r"\d{2}/\d{2}(?:/\d{2,4})?", data):
        partes = data.split("/")
        dia = int(partes[0])
        mes = int(partes[1])
        if len(partes) == 3:
            ano = int(partes[2])
            if ano < 100:
                ano += 2000
        else:
            ano = _resolver_ano_transacao(dia, mes, mes_ref, ano_ref)
        try:
            return datetime(ano, mes, dia)
        except Exception:
            return None

    match_dd_mmm = re.fullmatch(r"(\d{2})\s+([A-Za-zÇç]{3,9})\.?", data)
    if match_dd_mmm:
        dia = int(match_dd_mmm.group(1))
        mes_txt = _normalizar_texto_parser(match_dd_mmm.group(2))
        mes = _MESES_MAP.get(mes_txt)
        if mes:
            ano = _resolver_ano_transacao(dia, mes, mes_ref, ano_ref)
            try:
                return datetime(ano, mes, dia)
            except Exception:
                return None

    match_ext = re.fullmatch(
        r"(\d{2})\s+de\s+([A-Za-zÇç]{3,9})(?:\s+de\s+(\d{4}))?", data, flags=re.IGNORECASE
    )
    if match_ext:
        dia = int(match_ext.group(1))
        mes_txt = _normalizar_texto_parser(match_ext.group(2))
        mes = _MESES_MAP.get(mes_txt)
        ano = int(match_ext.group(3)) if match_ext.group(3) else _resolver_ano_transacao(dia, mes, mes_ref, ano_ref)
        if mes:
            try:
                return datetime(ano, mes, dia)
            except Exception:
                return None

    return None


def _extrair_parcela_da_descricao(descricao: str) -> tuple[str, str | None]:
    desc = (descricao or "").strip()
    match_parenteses = re.search(r"\(parcela\s+(\d{1,2})\s+de\s+(\d{1,2})\)", desc, flags=re.IGNORECASE)
    if match_parenteses:
        parcela = f"{int(match_parenteses.group(1))}/{int(match_parenteses.group(2))}"
        desc = re.sub(r"\(parcela\s+\d{1,2}\s+de\s+\d{1,2}\)", "", desc, flags=re.IGNORECASE).strip()
        return desc, parcela

    match_de = re.search(r"\b(\d{1,2})\s+DE\s+(\d{1,2})\b", desc, flags=re.IGNORECASE)
    if match_de:
        parcela = f"{int(match_de.group(1))}/{int(match_de.group(2))}"
        desc = re.sub(r"\b\d{1,2}\s+DE\s+\d{1,2}\b", "", desc, flags=re.IGNORECASE).strip()
        return desc, parcela

    match_barra = re.search(r"\b(\d{1,2})/(\d{1,2})\b", desc)
    if match_barra:
        parcela = f"{int(match_barra.group(1))}/{int(match_barra.group(2))}"
        desc = re.sub(r"\b\d{1,2}/\d{1,2}\b", "", desc).strip()
        return desc, parcela

    return desc, None


def _limpar_descricao_fatura(descricao: str) -> str:
    desc = re.sub(r"\s+", " ", (descricao or "")).strip(" -|:")
    desc = re.sub(
        r"\b(?:rio de janeir|rio de janeiro|sao paulo|so paulo|r de janeiro)\b.*$",
        "", desc, flags=re.IGNORECASE,
    )
    desc = re.sub(r"\b(?:cartao|cartão)\s+\d{4}\b", "", desc, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", desc).strip(" -|:")


def _descricao_deve_ser_ignoradas(descricao: str) -> bool:
    desc_norm = _normalizar_texto_parser(descricao)
    if not desc_norm:
        return True
    return any(token in desc_norm for token in _DESC_BLOQUEADA)


def _parse_linha_transacao_fatura(linha: str, mes_ref: int, ano_ref: int) -> dict | None:
    padroes = [
        re.compile(
            r"(?P<data>\d{2}/\d{2}(?:/\d{2,4})?)\s+(?P<corpo>.+?)\s+(?P<valor>-?R?\$?\s?[0-9\.\,]+\s*(?:[DCdc])?)$"
        ),
        re.compile(
            r"(?P<data>\d{2}\s+de\s+[A-Za-zÇç]{3,9}\.?(?:\s+\d{4})?)\s+(?P<corpo>.+?)\s+(?P<valor>-?R?\$?\s?[0-9\.\,]+\s*(?:[DCdc])?)$",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?P<data>\d{2}\s+[A-Za-zÇç]{3,9}\.?)\s+(?P<corpo>.+?)\s+(?P<valor>-?R?\$?\s?[0-9\.\,]+\s*(?:[DCdc])?)$",
            re.IGNORECASE,
        ),
    ]

    linha_limpa = linha.strip()
    for padrao in padroes:
        match = padrao.search(linha_limpa)
        if not match:
            continue

        dt_obj = _parse_data_fatura_local(match.group("data"), mes_ref, ano_ref)
        if not dt_obj:
            continue

        corpo = match.group("corpo").strip()
        corpo = re.sub(r"\s+\d{6,}\s*$", "", corpo)
        descricao, parcela = _extrair_parcela_da_descricao(corpo)
        descricao = _limpar_descricao_fatura(descricao)

        if _descricao_deve_ser_ignoradas(descricao):
            return None

        valor = _parse_valor_fatura(match.group("valor"), descricao)
        if valor is None or abs(valor) < 0.009:
            return None

        return {
            "descricao": descricao,
            "valor": valor,
            "data_transacao": dt_obj,
            "forma_pagamento": "Crédito",
            "parcela": parcela,
        }
    return None


def _deduplicar_transacoes_fatura(transacoes: list[dict]) -> tuple[list[dict], int]:
    deduped: list[dict] = []
    seen: set[tuple[str, str, float, str]] = set()
    ignoradas = 0
    for item in transacoes:
        key = (
            item["data_transacao"].strftime("%Y-%m-%d"),
            _normalizar_texto_parser(item.get("descricao", "")),
            round(float(item.get("valor", 0.0)), 2),
            str(item.get("parcela") or ""),
        )
        if key in seen:
            ignoradas += 1
            continue
        seen.add(key)
        deduped.append(item)
    return deduped, ignoradas


def _detectar_total_fatura_local(linhas: list[str]) -> float:
    padroes = [
        r"total final .*?([0-9\.\,]+)\s*[dD]\b",
        r"total\s+(?:da\s+)?fatura.*?([0-9\.\,]+)\s*[dD]?\b",
        r"total a pagar.*?([0-9\.\,]+)",
    ]
    texto = "\n".join(linhas)
    for padrao in padroes:
        match = re.search(padrao, texto, flags=re.IGNORECASE)
        if match:
            valor = match.group(1).replace(".", "").replace(",", ".")
            try:
                return abs(float(valor))
            except Exception:
                continue
    return 0.0


def _parse_fatura_pdf_local(file_bytes: bytes) -> Tuple[List[Dict], int, str, float]:
    linhas = _extrair_texto_pdf_local(file_bytes)
    if not linhas:
        return [], 0, "Desconhecido", 0.0

    mes_ref, ano_ref = _detectar_referencia_fatura(linhas)
    banco = _detectar_banco_fatura("\n".join(linhas[:160]))
    total_pdf = _detectar_total_fatura_local(linhas)

    secao_ativa: str | None = None
    transacoes: list[dict] = []
    ignoradas = 0
    for linha in linhas:
        secao_detectada = _detectar_secao_linha(linha)
        if secao_detectada:
            secao_ativa = secao_detectada
            continue
        if secao_ativa and _linha_indica_fim_secao(linha):
            secao_ativa = None
            continue
        if secao_ativa is None:
            continue

        parsed = _parse_linha_transacao_fatura(linha, mes_ref, ano_ref)
        if not parsed:
            continue
        parsed["origem"] = f"fatura_parser_{banco.lower().replace(' ', '_')}"
        parsed["secao_origem"] = secao_ativa
        transacoes.append(parsed)

    transacoes, ignoradas_dedup = _deduplicar_transacoes_fatura(transacoes)
    ignoradas += ignoradas_dedup
    return transacoes, ignoradas, banco, total_pdf


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS DE VALIDAÇÃO MATEMÁTICA
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_erro_percentual(transacoes: List[Dict], total_pdf: float) -> float:
    """
    Retorna o erro percentual entre o valor líquido extraído e o total do PDF.

    Faturas de crédito:
      - Despesas → valores NEGATIVOS
      - Créditos/estornos → valores POSITIVOS
      - total_pdf = valor absoluto a pagar (positivo)
      - valor_liquido = soma_debitos - soma_creditos
    """
    if not transacoes or total_pdf <= 0:
        return 0.0

    soma_debitos = sum(abs(float(t["valor"])) for t in transacoes if float(t.get("valor", 0)) < 0)
    soma_creditos = sum(float(t["valor"]) for t in transacoes if float(t.get("valor", 0)) > 0)
    valor_liquido = soma_debitos - soma_creditos

    diferenca = abs(valor_liquido - total_pdf)
    return diferenca / total_pdf


def _resultado_e_aceitavel(transacoes: List[Dict], total_pdf: float) -> bool:
    """Retorna True se o resultado pode ser considerado matematicamente confiável."""
    if not transacoes:
        return False
    # Sem total do PDF para comparar: aceita desde que haja transações
    if total_pdf <= 0:
        return len(transacoes) > 0
    return _calcular_erro_percentual(transacoes, total_pdf) <= _MATH_TOLERANCE_PCT


# ─────────────────────────────────────────────────────────────────────────────
# PROMPTS GEMINI
# ─────────────────────────────────────────────────────────────────────────────

def _build_gemini_prompt(mes_ref: int, ano_ref: int, total_esperado: float | None = None, texto_fatura: str = "") -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    ref = f"{mes_ref:02d}/{ano_ref}"
    total_hint = (
        f"\n    TOTAL ESPERADO DA FATURA: R$ {total_esperado:.2f} – a soma dos débitos extraídos DEVE fechar próximo a esse valor."
        if total_esperado and total_esperado > 0
        else ""
    )
    return f"""Você é um sistema de extração financeira de alta precisão.
Leia o CONTEÚDO EXTRAÍDO DA FATURA de cartão de crédito abaixo e extraia TODAS as transações.

DATA ATUAL: {hoje}
REFERÊNCIA DA FATURA: {ref}{total_hint}

═══ REGRAS OBRIGATÓRIAS ═══

1. COBERTURA TOTAL – Percorra TODAS as páginas e seções:
   "Compras Nacionais", "Compras Internacionais", "Parcelamentos",
   "Encargos", "IOF", "Serviços", "Anuidade", "Ajustes".
   NÃO pule nenhuma seção. Se estiver em dúvida se é uma transação, INCLUA.

2. SINAIS DOS VALORES (CRÍTICO):
   - Compras, IOF, juros, encargos, anuidade → valor NEGATIVO  (ex: -150.40)
   - Pagamentos, estornos, créditos, cashback → valor POSITIVO (ex:  500.00)
   Nunca inverta os sinais.

3. DATAS:
   - Use o formato "YYYY-MM-DD".
   - Para transações sem ano explícito, use {ano_ref} como padrão.
   - Se o mês da transação for 12 e a fatura é de Janeiro, use {ano_ref - 1}.

4. DESCRIÇÃO LIMPA:
   - Extraia apenas o nome do estabelecimento/serviço.
   - Remova: códigos de documento, nomes de cidade, nomes de país,
     sufixos como "BR", "US", "SAO PAULO", "RJ".

5. PARCELAS:
   - Se houver indicação de parcela (ex: "3/12", "Parc 3 de 12"), preencha o
     campo "parcela" com o formato "X/Y" (ex: "3/12").
   - Se não houver, deixe null.

6. INTEGRIDADE MATEMÁTICA:
   - Ao final, some todos os valores negativos (débitos).
   - Esse total deve ser próximo ao "total a pagar" indicado na fatura.
   - Se houver diferença > 10%, revise e adicione os itens faltantes.

7. EXCLUSÕES (não inclua):
   - Linhas de cabeçalho/rodapé sem valor monetário.
   - "Limite disponível", "Limite total", "Saldo anterior" isolados.
   - Valores duplicados de totalizadores de seção.

FORMATO DE RESPOSTA (JSON puro, sem markdown):
{{
  "banco": "Nome do banco/emissor",
  "total_fatura": 1234.56,
  "transacoes": [
    {{
      "data": "YYYY-MM-DD",
      "descricao": "NOME DO ESTABELECIMENTO",
      "valor": -123.45,
      "parcela": "1/12"
    }}
  ]
}}

═══ CONTEÚDO DA FATURA ═══
{texto_fatura}
"""


def _build_gemini_prompt_retry(
    mes_ref: int, ano_ref: int, total_esperado: float, soma_atual: float, texto_fatura: str = ""
) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    faltante = abs(total_esperado - soma_atual)
    return f"""Você já extraiu parte das transações desta fatura, mas a soma dos débitos
(R$ {soma_atual:.2f}) ainda está R$ {faltante:.2f} ABAIXO do total da fatura (R$ {total_esperado:.2f}).

DATA ATUAL: {hoje}
REFERÊNCIA: {mes_ref:02d}/{ano_ref}
TOTAL ESPERADO: R$ {total_esperado:.2f}
SOMA ATUAL DOS DÉBITOS: R$ {soma_atual:.2f}
DIFERENÇA: R$ {faltante:.2f}

Revise o CONTEÚDO EXTRAÍDO DA FATURA abaixo mais uma vez e encontre os itens que faltaram.
Procure especialmente:
  - Encargos financeiros (juros, IOF, mora, multa)
  - Anuidades ou mensalidades
  - Compras internacionais (podem ter IOF separado)
  - Parcelas de compras anteriores em seções distintas
  - Qualquer linha com valor monetário que ainda não foi extraída

Retorne APENAS os itens ADICIONAIS que estavam faltando (não repita os já encontrados).
Formato JSON (sem markdown):
{{
  "banco": "Nome do banco",
  "total_fatura": {total_esperado:.2f},
  "transacoes": [
    {{ "data": "YYYY-MM-DD", "descricao": "...", "valor": -123.45, "parcela": null }}
  ]
}}

═══ CONTEÚDO DA FATURA ═══
{texto_fatura}
"""


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZAÇÃO DO RESULTADO DO GEMINI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict | None:
    if not text:
        return None
    text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _parse_data_gemini(raw_data: str, mes_ref: int, ano_ref: int) -> datetime | None:
    raw = str(raw_data or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d/%m"):
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt == "%d/%m":
                ano = _resolver_ano_transacao(dt.day, dt.month, mes_ref, ano_ref)
                dt = dt.replace(year=ano)
            elif dt.year < 100:
                dt = dt.replace(year=2000 + dt.year)
            return dt
        except Exception:
            continue
    return None


def _normalizar_resultado_gemini(
    data: dict,
    mes_ref: int,
    ano_ref: int,
    origem_prefixo: str,
) -> Tuple[List[Dict], int, str, float]:
    transacoes_finais: List[Dict] = []
    ignoradas_count = 0
    banco = str(data.get("banco") or "Desconhecido").strip()
    total_pdf = float(data.get("total_fatura") or 0.0)

    blacklist_totalizadores = {
        "saldo anterior", "total da fatura", "limite", "demonstrativo",
        "fatura anterior", "saldo a pagar", "pagamento recebido",
        "valor do pagamento", "total de compras", "total de lançamentos",
        "total parcelamentos",
    }

    for item in data.get("transacoes", []):
        try:
            descricao = str(item.get("descricao") or "").strip()
            if not descricao:
                ignoradas_count += 1
                continue

            desc_norm = _normalizar_texto_parser(descricao)
            if any(term in desc_norm for term in blacklist_totalizadores):
                ignoradas_count += 1
                continue

            valor_raw = item.get("valor")
            if valor_raw is None:
                ignoradas_count += 1
                continue

            try:
                valor = float(str(valor_raw).replace(",", "."))
            except Exception:
                ignoradas_count += 1
                continue

            if abs(valor) < 0.01:
                ignoradas_count += 1
                continue

            dt_obj = _parse_data_gemini(item.get("data"), mes_ref, ano_ref)
            if not dt_obj:
                ignoradas_count += 1
                continue

            descricao_limpa = _limpar_descricao_fatura(descricao)
            if not descricao_limpa:
                ignoradas_count += 1
                continue

            parcela_raw = item.get("parcela")
            parcela = str(parcela_raw).strip() if parcela_raw else None

            transacoes_finais.append({
                "descricao": descricao_limpa,
                "valor": valor,
                "data_transacao": dt_obj,
                "forma_pagamento": "Crédito",
                "origem": f"{origem_prefixo}_{banco.lower().replace(' ', '_')}",
                "parcela": parcela,
            })
        except Exception as exc:
            logger.debug("Erro ao normalizar item do Gemini: %s | item=%s", exc, item)
            ignoradas_count += 1

    # Deduplicação
    deduped: List[Dict] = []
    seen: set = set()
    for t in transacoes_finais:
        key = (
            t["data_transacao"].strftime("%Y-%m-%d"),
            _normalizar_texto_parser(t["descricao"]),
            round(t["valor"], 2),
        )
        if key in seen:
            ignoradas_count += 1
            continue
        seen.add(key)
        deduped.append(t)

    return deduped, ignoradas_count, banco, total_pdf


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL DE EXTRAÇÃO COM GEMINI
# ─────────────────────────────────────────────────────────────────────────────

async def _parse_fatura_pdf_with_gemini(file_bytes: bytes) -> Tuple[List[Dict], int, str, float]:
    import config

    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    cached = _get_cached_parse_result(file_bytes)
    if cached:
        logger.info("♻️ Reutilizando resultado em cache para este PDF de fatura.")
        return cached

    try:
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\""))
    except Exception as e:
        logger.warning("Erro ao configurar genai: %s", e)

    # Extrai metadados básicos via parser local (leve, sem IA)
    linhas_preview = _extrair_texto_pdf_local(file_bytes)
    mes_ref, ano_ref = _detectar_referencia_fatura(linhas_preview)
    total_local = _detectar_total_fatura_local(linhas_preview)
    
    # 📝 NOVO: Em vez de mandar o PDF (multimodal), mandamos o texto extraído.
    # Isso evita confusão com o layout complexo do PDF de bancos.
    texto_completo_pdf = "\n".join(linhas_preview)

    melhor_resultado: Tuple[List[Dict], int, str, float] | None = None
    melhor_erro: float = float("inf")

    # ── Fase 1: Tentativas por modelo ────────────────────────────────────────
    for model_name in _GEMINI_MODEL_CANDIDATES:
        logger.info("🤖 Tentando extração de texto com %s", model_name)
        prompt_v1 = _build_gemini_prompt(mes_ref, ano_ref, total_local or None, texto_completo_pdf)

        try:
            model = genai.GenerativeModel(model_name)
            # 🚀 Chamada simplificada: apenas o prompt com o texto injetado
            response = await model.generate_content_async(
                [prompt_v1],
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                    "max_output_tokens": 8192,
                },
                request_options={"timeout": 120},
            )
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "quota" in err_msg.lower() or "RESOURCE_EXHAUSTED" in err_msg:
                logger.warning("⏸ Cota atingida no modelo %s. Tentando próximo.", model_name)
                continue
            if "404" in err_msg or "not found" in err_msg.lower():
                logger.warning("❓ Modelo %s não disponível nesta região/conta.", model_name)
                continue
            logger.warning("❌ Falha inesperada com %s: %s", model_name, err_msg)
            continue

        resp_text = getattr(response, "text", "") or ""
        if not resp_text:
            logger.warning("Resposta vazia de %s", model_name)
            continue

        json_data = _parse_json_response(resp_text)
        if not json_data:
            logger.warning("JSON inválido retornado por %s", model_name)
            continue

        transacoes, ignoradas, banco, total_pdf = _normalizar_resultado_gemini(
            json_data, mes_ref, ano_ref, "fatura_pdf"
        )

        # Usa total do PDF detectado localmente se o Gemini não retornou
        if total_pdf <= 0 and total_local > 0:
            total_pdf = total_local

        if not transacoes:
            logger.warning("Nenhuma transação extraída por %s", model_name)
            continue

        erro = _calcular_erro_percentual(transacoes, total_pdf)
        logger.info(
            "📊 %s → %d transações | total_pdf=%.2f | erro=%.1f%%",
            model_name, len(transacoes), total_pdf, erro * 100,
        )

        # ── Fase 2: Retry com prompt de completude se erro alto ──────────────
        if erro > _MATH_TOLERANCE_PCT and total_pdf > 0:
            soma_debitos = sum(abs(float(t["valor"])) for t in transacoes if float(t.get("valor", 0)) < 0)
            soma_creditos = sum(float(t["valor"]) for t in transacoes if float(t.get("valor", 0)) > 0)
            soma_liquida = soma_debitos - soma_creditos

            # Só faz retry se estamos claramente abaixo do esperado (não apenas arredondamento)
            if soma_liquida < total_pdf * 0.85:
                logger.info("🔄 Erro alto (%.1f%%). Iniciando retry com prompt de completude (TEXTO).", erro * 100)
                prompt_v2 = _build_gemini_prompt_retry(mes_ref, ano_ref, total_pdf, soma_liquida, texto_completo_pdf)
                try:
                    # 🚀 Chamada simplificada para o retry também
                    response2 = await model.generate_content_async(
                        [prompt_v2],
                        generation_config={
                            "response_mime_type": "application/json",
                            "temperature": 0,
                            "max_output_tokens": 4096,
                        },
                        request_options={"timeout": 90},
                    )
                    resp_text2 = getattr(response2, "text", "") or ""
                    json_data2 = _parse_json_response(resp_text2) if resp_text2 else None
                    if json_data2:
                        extra_t, extra_i, _, _ = _normalizar_resultado_gemini(
                            json_data2, mes_ref, ano_ref, "fatura_pdf_retry"
                        )
                        if extra_t:
                            chaves_existentes = {
                                (
                                    t["data_transacao"].strftime("%Y-%m-%d"),
                                    _normalizar_texto_parser(t["descricao"]),
                                    round(t["valor"], 2),
                                )
                                for t in transacoes
                            }
                            novos = [
                                t for t in extra_t
                                if (
                                    t["data_transacao"].strftime("%Y-%m-%d"),
                                    _normalizar_texto_parser(t["descricao"]),
                                    round(t["valor"], 2),
                                ) not in chaves_existentes
                            ]
                            if novos:
                                transacoes = transacoes + novos
                                ignoradas += extra_i
                                erro_novo = _calcular_erro_percentual(transacoes, total_pdf)
                                logger.info(
                                    "✅ Retry adicionou %d itens. Novo erro: %.1f%%",
                                    len(novos), erro_novo * 100,
                                )
                                erro = erro_novo
                except Exception as exc2:
                    logger.warning("Retry falhou com %s: %s", model_name, exc2)

        # Guarda o melhor resultado acumulado
        if erro < melhor_erro:
            melhor_erro = erro
            melhor_resultado = (transacoes, ignoradas, banco, total_pdf)

        # Aceita imediatamente se dentro da tolerância
        if _resultado_e_aceitavel(transacoes, total_pdf):
            logger.info("✅ Extração aceita com %s (erro=%.1f%%)", model_name, erro * 100)
            _set_cached_parse_result(file_bytes, melhor_resultado, is_partial=False)
            return melhor_resultado

        logger.warning(
            "⚠️ %s fora da tolerância (erro=%.1f%%). Tentando próximo modelo.", model_name, erro * 100
        )

    # ── Fase 3: Retorna o melhor resultado Gemini mesmo que parcial ──────────
    if melhor_resultado and melhor_resultado[0]:
        transacoes, ignoradas, banco, total_pdf = melhor_resultado
        is_partial = melhor_erro > _MATH_TOLERANCE_PCT

        if is_partial:
            logger.warning(
                "⚠️ Melhor resultado Gemini é parcial (erro=%.1f%%). Marcando origem.",
                melhor_erro * 100,
            )
            for t in transacoes:
                t["origem"] = t.get("origem", "fatura_pdf") + "_parcial"

        _set_cached_parse_result(file_bytes, melhor_resultado, is_partial=is_partial)
        return melhor_resultado

    # ── Fase 4: Fallback para parser local heurístico ────────────────────────
    logger.info("⚠️ Gemini falhou em todos os modelos. Ativando fallback: Parser Local.")
    transacoes_local, ignoradas_local, banco_local, total_local_fb = _parse_fatura_pdf_local(file_bytes)

    if transacoes_local:
        is_partial_local = not _resultado_e_aceitavel(transacoes_local, total_local_fb)
        if is_partial_local:
            for t in transacoes_local:
                t["origem"] = t.get("origem", "fatura_local") + "_parcial"
        result = (transacoes_local, ignoradas_local, banco_local, total_local_fb)
        _set_cached_parse_result(file_bytes, result, is_partial=is_partial_local)
        logger.info(
            "✅ Parser local retornou %d transações (parcial=%s)", len(transacoes_local), is_partial_local
        )
        return result

    raise RuntimeError(
        "Não foi possível extrair transações desta fatura. "
        "O PDF foi lido, mas nenhum lançamento confiável foi encontrado."
    )


# ─────────────────────────────────────────────────────────────────────────────
# HANDLERS DO TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

async def fatura_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await touch_user_interaction(update.effective_user.id, context)

    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
        ensure_user_plan_state(db, usuario_db, commit=True)
        gate = plan_allows_feature(db, usuario_db, "pdf_import")
        if not gate.allowed:
            text, keyboard = upgrade_prompt_for_feature("pdf_import")
            await update.message.reply_html(text, reply_markup=keyboard)
            return ConversationHandler.END
    finally:
        db.close()

    await update.message.reply_text(
        "Envie sua fatura de cartão de crédito em PDF para importar os lançamentos.\n"
        "O sistema extrai datas individuais e parcelamentos com alta precisão."
    )
    return FATURA_AWAIT_FILE


async def fatura_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    db_plan = next(get_db())
    try:
        usuario_db = get_or_create_user(db_plan, update.effective_user.id, update.effective_user.full_name)
        ensure_user_plan_state(db_plan, usuario_db, commit=True)
        gate = plan_allows_feature(db_plan, usuario_db, "pdf_import")
        if not gate.allowed:
            text, keyboard = upgrade_prompt_for_feature("pdf_import")
            await update.message.reply_html(text, reply_markup=keyboard)
            return ConversationHandler.END
    finally:
        db_plan.close()

    document = update.message.document
    if not document or document.mime_type != "application/pdf":
        await update.message.reply_text("Envie um arquivo PDF válido.")
        return FATURA_AWAIT_FILE

    if document.file_size and document.file_size > MAX_PDF_SIZE_BYTES:
        await update.message.reply_text(
            f"❌ Arquivo muito grande. Tamanho máximo: {MAX_PDF_SIZE_MB}MB.\n"
            "Dica: exporte a fatura em partes menores."
        )
        return FATURA_AWAIT_FILE

    try:
        file_obj = await document.get_file()
        file_bytes = await file_obj.download_as_bytearray()
    except Exception:
        await update.message.reply_text("❌ Não consegui baixar esse PDF. Tente novamente.")
        return FATURA_AWAIT_FILE

    process_msg = await update.message.reply_text(
        "📄 PDF recebido! Extraindo lançamentos com IA...\n"
        "Isso pode levar até 30 segundos."
    )

    try:
        transacoes, ignoradas, origem_label, total_pdf = await asyncio.wait_for(
            _parse_fatura_pdf_with_gemini(bytes(file_bytes)),
            timeout=MAX_PDF_PARSE_SECONDS,
        )
    except asyncio.TimeoutError:
        await process_msg.edit_text(
            "⏱️ O processamento excedeu o tempo limite.\n"
            "Tente enviar novamente ou dividir o PDF em partes menores."
        )
        return FATURA_AWAIT_FILE
    except Exception as exc:
        logger.exception("Erro ao processar fatura PDF")
        error_str = str(exc)
        if "password" in error_str.lower() or "encrypted" in error_str.lower():
            await process_msg.edit_text(
                "🔒 Este PDF está protegido por senha.\n"
                "Remova a senha no app do banco e envie novamente."
            )
        elif "Não foi possível extrair" in error_str:
            await process_msg.edit_text(
                "❌ <b>Não consegui extrair dados deste PDF.</b>\n\n"
                "O formato parece incompatível ou o arquivo não contém texto legível.\n"
                "<b>Dica:</b> Tente /lancamento com uma foto da fatura.",
                parse_mode="HTML",
            )
        else:
            await process_msg.edit_text(
                "❌ <b>Erro no Processamento</b>\n\nFalha técnica ao analisar o arquivo.",
                parse_mode="HTML",
            )
        return FATURA_AWAIT_FILE
    else:
        try:
            await process_msg.delete()
        except Exception:
            pass

    if not transacoes:
        await update.message.reply_text(
            "❌ Não identifiquei transações válidas nesta fatura.\n"
            "Verifique se o arquivo contém compras detalhadas e tente novamente."
        )
        return ConversationHandler.END

    context.user_data["fatura_transacoes"] = transacoes
    context.user_data["fatura_ignoradas"] = ignoradas
    context.user_data["fatura_origem_label"] = origem_label
    context.user_data["fatura_valor_total_pdf"] = total_pdf

    db = next(get_db())
    try:
        context.user_data["fatura_conta_id"] = 0

        # ── Cálculo correto do ajuste de centavos ──────────────────────────
        soma_debitos = sum(abs(float(t["valor"])) for t in transacoes if float(t.get("valor", 0)) < 0)
        soma_creditos = sum(float(t["valor"]) for t in transacoes if float(t.get("valor", 0)) > 0)
        valor_liquido = soma_debitos - soma_creditos

        ajuste_pdf_abs = 0.0
        if isinstance(total_pdf, (int, float)) and total_pdf > 0:
            diferenca = round(total_pdf - valor_liquido, 2)
            # Aplica ajuste apenas para diferenças ínfimas (centavos de arredondamento)
            if 0.01 <= abs(diferenca) < 2.00:
                data_ajuste = max(
                    (t["data_transacao"] for t in transacoes), default=datetime.now()
                )
                transacoes.append({
                    "data_transacao": data_ajuste,
                    "descricao": "Ajuste de centavos (Fatura)",
                    "valor": -abs(diferenca),
                    "forma_pagamento": "Crédito",
                    "origem": "fatura_ajuste_pdf",
                })
                ajuste_pdf_abs = abs(diferenca)
                context.user_data["fatura_ajuste_pdf"] = ajuste_pdf_abs
                context.user_data["fatura_transacoes"] = transacoes

        total = len(transacoes)
        total_debito = sum(abs(float(t["valor"])) for t in transacoes if float(t.get("valor", 0)) < 0)
        total_credito = sum(float(t["valor"]) for t in transacoes if float(t.get("valor", 0)) > 0)
        is_parcial = any("_parcial" in str(t.get("origem", "")) for t in transacoes)

        sorted_transacoes = sorted(transacoes, key=lambda x: x["data_transacao"])
        preview_lines = []
        for item in sorted_transacoes[:10]:
            data = item["data_transacao"].strftime("%d/%m")
            valor_label = _fmt_brl(item["valor"])
            parcela = f" ({item['parcela']})" if item.get("parcela") else ""
            desc = _compact_desc(f"{item.get('descricao', '')}{parcela}")
            preview_lines.append(f"• {data} | {desc} | {valor_label}")

        top_debitos = sorted(
            [t for t in transacoes if float(t.get("valor", 0)) < 0],
            key=lambda t: abs(float(t.get("valor", 0))),
            reverse=True,
        )[:3]
        top_lines = [
            f"• {_compact_desc(t.get('descricao', ''), 34)} ({_fmt_brl(t['valor'])})"
            for t in top_debitos
        ]

        preview_text = "\n".join(preview_lines) or "• Sem itens para preview"
        maiores_text = "\n".join(top_lines) or "• Sem débitos"

        resumo_linhas = [f"🧾 <b>Resumo da Fatura ({origem_label})</b>", ""]
        if is_parcial:
            resumo_linhas += [
                "⚠️ <b>ATENÇÃO: Extração parcial.</b>",
                "<i>A soma dos itens pode não fechar com o total do PDF. Revise antes de salvar.</i>",
                "",
            ]
        resumo_linhas += [
            f"📌 <b>Transações detectadas:</b> <code>{total}</code>",
            f"↩️ <b>Itens ignorados:</b> <code>{ignoradas}</code>",
            f"💸 <b>Total débitos:</b> <code>{_fmt_brl(total_debito)}</code>",
            f"💰 <b>Total créditos:</b> <code>{_fmt_brl(total_credito)}</code>",
        ]
        if isinstance(total_pdf, (int, float)) and total_pdf > 0:
            resumo_linhas.append(f"🧮 <b>Total no PDF:</b> <code>{_fmt_brl(total_pdf)}</code>")
        if ajuste_pdf_abs >= 0.01:
            resumo_linhas.append(f"⚖️ <b>Ajuste aplicado:</b> <code>{_fmt_brl(ajuste_pdf_abs)}</code>")

        resumo_linhas += [
            "",
            "🔥 <b>Maiores gastos</b>",
            maiores_text,
            "",
            "👀 <b>Preview de lançamentos</b>",
            preview_text,
            "",
            "━━━━━━━━━━━━━━━━━━",
            "✅ <b>Ação:</b> Importar lançamentos?",
            "Toque em <b>Editar</b> para revisar antes de salvar.",
        ]
        resumo = "\n".join(resumo_linhas)

        draft_token = create_fatura_draft(
            telegram_user_id=update.effective_user.id,
            conta_id=0,
            conta_nome="Cartao de Credito",
            transacoes=transacoes,
            origem_label=origem_label,
        )
        context.user_data["fatura_draft_token"] = draft_token

        keyboard = [
            [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data=f"fatura_salvar:{draft_token}")],
            [InlineKeyboardButton("✏️ Editar", callback_data=f"fatura_editar_inline:{draft_token}")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="fatura_cancelar")],
        ]
        await update.message.reply_text(resumo, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return FATURA_CONFIRMATION_STATE
    finally:
        db.close()


async def fatura_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    try:
        await query.answer()
    except Exception as e:
        logger.warning("Falha ao responder callback: %s", e)

    try:
        raw_action = query.data or ""
        action_parts = raw_action.split(":", 1)
        action = action_parts[0]
        draft_token = action_parts[1] if len(action_parts) > 1 else (context.user_data.get("fatura_draft_token") or "")
        logger.info("fatura_confirm: action=%s, user=%s", action, query.from_user.id)

        if action == "fatura_cancelar":
            context.user_data.pop("fatura_transacoes", None)
            context.user_data.pop("fatura_conta_id", None)
            context.user_data.pop("fatura_ajuste_pdf", None)
            context.user_data.pop("fatura_draft_token", None)
            await query.edit_message_text("❌ Importação cancelada.")
            return ConversationHandler.END

        if action == "fatura_editar_inline":
            draft_data = get_fatura_draft(draft_token, query.from_user.id) if draft_token else None
            transacoes = (draft_data or {}).get("transacoes") or context.user_data.get("fatura_transacoes", [])
            conta_id = (draft_data or {}).get("conta_id")
            origem_label = (draft_data or {}).get("origem_label") or context.user_data.get("fatura_origem_label", "Inter")

            if not transacoes:
                await query.edit_message_text("❌ Dados da fatura expiraram. Envie o PDF novamente.")
                return ConversationHandler.END

            token = create_fatura_draft(
                telegram_user_id=query.from_user.id,
                conta_id=conta_id,
                conta_nome="Sem conta",
                transacoes=transacoes,
                origem_label=origem_label,
            )
            set_pending_editor_token(query.from_user.id, token)

            try:
                webapp_url = _get_fatura_webapp_url("fatura_editor", token)
            except Exception as e:
                logger.error("Falha ao gerar webapp_url: %s", e, exc_info=True)
                raise

            await query.edit_message_text("✅ Rascunho preparado. Abrindo o editor...", parse_mode="HTML")
            await query.message.reply_text(
                "📱 <b>Editar lançamentos da fatura</b>\n\nToque no botão abaixo para abrir o editor.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Abrir Editor da Fatura", web_app=WebAppInfo(url=webapp_url))],
                ]),
            )
            return FATURA_CONFIRMATION_STATE

        if action == "fatura_salvar":
            if draft_token and context.user_data.get("fatura_save_in_progress_token") == draft_token:
                await query.answer("⏳ Já estou salvando essa fatura.", show_alert=False)
                return ConversationHandler.END

            if draft_token and context.user_data.get("fatura_save_completed_token") == draft_token:
                await query.answer("✅ Essa fatura já foi processada.", show_alert=False)
                return ConversationHandler.END

            draft_data = get_fatura_draft(draft_token, query.from_user.id) if draft_token else None
            transacoes = (draft_data or {}).get("transacoes") or context.user_data.get("fatura_transacoes", [])
            conta_id = int((draft_data or {}).get("conta_id") or context.user_data.get("fatura_conta_id", 0))

            if not transacoes:
                logger.error("Transações não encontradas para user=%s", query.from_user.id)
                try:
                    await query.edit_message_text(
                        "❌ <b>Dados da fatura perdidos.</b>\n\nEnvie o PDF novamente.",
                        parse_mode="HTML",
                    )
                except Exception:
                    await query.answer("❌ Dados da fatura perdidos. Envie o PDF novamente.", show_alert=True)
                return ConversationHandler.END

            context.user_data["fatura_save_in_progress_token"] = draft_token
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass

            db = next(get_db())
            try:
                conta_obj = db.query(Conta).filter(Conta.id == conta_id).first()
                conta_nome = conta_obj.nome if conta_obj else "Cartao de Credito"
                for item in transacoes:
                    item["forma_pagamento"] = "Crédito"

                usuario_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)
                tipo_origem = transacoes[0].get("origem", "fatura_pdf_generic") if transacoes else "fatura_pdf_generic"
                ok, msg, _stats = await salvar_transacoes_generica(
                    db, usuario_db, transacoes, conta_id, tipo_origem=tipo_origem
                )
                if ok:
                    if draft_token:
                        pop_fatura_draft(draft_token, query.from_user.id)
                    context.user_data["fatura_save_completed_token"] = draft_token
                    try:
                        await give_xp_for_action(query.from_user.id, "LANCAMENTO_CRIADO_PDF", context)
                    except Exception:
                        logger.debug("Falha ao conceder XP (não crítico).")
                    try:
                        limpar_cache_usuario(int(query.from_user.id))
                    except Exception:
                        logger.debug("Falha ao limpar cache (não crítico).")

                await query.edit_message_text(msg, parse_mode="HTML")
                return ConversationHandler.END
            finally:
                db.close()
                context.user_data.pop("fatura_save_in_progress_token", None)
                context.user_data.pop("fatura_transacoes", None)
                context.user_data.pop("fatura_conta_id", None)
                context.user_data.pop("fatura_ajuste_pdf", None)
                context.user_data.pop("fatura_origem_label", None)
                context.user_data.pop("fatura_pending_edit", None)

        logger.warning("Ação desconhecida em fatura_confirm: %s", action)
        await query.answer("Ação inválida", show_alert=True)
        return FATURA_CONFIRMATION_STATE

    except Exception as e:
        logger.error("ERRO NO FATURA_CONFIRM: action=%s | error=%s", query.data, e, exc_info=True)
        try:
            await query.answer(f"❌ Erro: {str(e)[:50]}", show_alert=True)
        except Exception as e2:
            logger.error("Falha ao enviar erro ao user: %s", e2)
        return FATURA_CONFIRMATION_STATE


async def fatura_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Importação cancelada.")
    elif update.message:
        await update.message.reply_text("Importação cancelada.")
    context.user_data.pop("fatura_transacoes", None)
    context.user_data.pop("fatura_conta_id", None)
    context.user_data.pop("fatura_origem_label", None)
    return ConversationHandler.END


fatura_conv = ConversationHandler(
    entry_points=[
        CommandHandler("fatura", fatura_start),
        MessageHandler(filters.Regex(r"^🧾 Fatura$"), fatura_start),
    ],
    states={
        FATURA_AWAIT_FILE: [
            MessageHandler(filters.Document.MimeType("application/pdf"), fatura_receive_file)
        ],
        FATURA_CONFIRMATION_STATE: [
            CallbackQueryHandler(fatura_confirm, pattern="^fatura_")
        ],
    },
    fallbacks=[
        CommandHandler(["cancelar", "cancel", "sair", "parar"], fatura_cancel),
        MessageHandler(filters.Regex(r"(?i)^/?\s*(cancelar|cancel|sair|parar)$"), fatura_cancel),
    ],
    per_message=False,
    per_user=True,
    per_chat=True,
)