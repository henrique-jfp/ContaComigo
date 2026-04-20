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
        cached = item.get("result")
        if not cached:
            return None
        transacoes, ignoradas, origem_label, total_pdf = cached
        return _deserialize_parse_transacoes(transacoes), int(ignoradas), str(origem_label), float(total_pdf)


def _set_cached_parse_result(file_bytes: bytes, result: tuple[List[Dict], int, str, float]) -> None:
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

    # Telegram exige HTTPS fora de localhost para abrir web_app.
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
    "jan": 1,
    "janeiro": 1,
    "feb": 2,
    "fev": 2,
    "fevereiro": 2,
    "mar": 3,
    "marco": 3,
    "março": 3,
    "apr": 4,
    "abr": 4,
    "abril": 4,
    "may": 5,
    "mai": 5,
    "maio": 5,
    "jun": 6,
    "junho": 6,
    "jul": 7,
    "julho": 7,
    "aug": 8,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "set": 9,
    "setembro": 9,
    "oct": 10,
    "out": 10,
    "outubro": 10,
    "nov": 11,
    "novembro": 11,
    "dec": 12,
    "dez": 12,
    "dezembro": 12,
}

_SECAO_ANCORAS = {
    "compras": [
        "compras (cartão",
        "compras (cartao",
        "despesas da fatura",
        "transações de",
        "transacoes de",
        "lançamentos",
        "lancamentos",
        "detalhamento",
        "gastos do mes",
        "gastos do mês",
        "movimentacao",
        "movimentação",
        "compras nacionais",
        "compras internacionais",
        "servicos nps",
    ],
    "parceladas": [
        "compras parceladas",
        "parceladas (cartão",
        "parceladas (cartao",
        "parcelamentos",
        "transações parceladas",
        "lancamentos parcelados",
        "compras parceladas nps",
    ],
    "outros": [
        "outros (cartão",
        "outros (cartao",
        "encargos",
        "anuidade",
        "taxas",
        "tarifas",
        "serviços",
        "servicos",
        "movimentacoes de encargos",
        "encargos e tarifas",
    ],
}

_SECAO_FIM = [
    "total compras",
    "total compras parceladas",
    "total outros",
    "total final",
    "total a pagar",
    "pagamento minimo",
]

_DESC_BLOQUEADA = [
    "obrigado pelo pagamento",
    "pagamento efetuado",
    "pagamento recebido",
    "total da fatura anterior",
    "saldo anterior",
    "saldo credito rotativo",
    "saldo crédito rotativo",
    "valor do pagamento",
    "saldo a pagar",
    "limite",
    "demonstrativo",
]


def _normalizar_texto_parser(valor: str) -> str:
    texto = (valor or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", texto)


def _extrair_linhas_com_pdfplumber(file_bytes: bytes) -> list[str]:
    """Extrai linhas preservando a geometria visual do PDF via bounding boxes."""
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
    """Detecta mês e ano de referência da fatura analisando o início do texto."""
    texto = "\n".join(linhas[:200]).lower()
    
    # 1. Tenta encontrar "Vencimento: DD/MM/AAAA"
    match_venc = re.search(r"vencimento:?\s*(\d{2})/(\d{2})/(\d{4})", texto)
    if match_venc:
        return int(match_venc.group(2)), int(match_venc.group(3))
        
    # 2. Tenta encontrar Ano
    ano_fatura = datetime.now().year
    match_ano = re.search(r"\b(20\d{2})\b", texto)
    if match_ano:
        ano_fatura = int(match_ano.group(1))
        
    # 3. Tenta encontrar Nome do Mês
    for nome_mes, num_mes in _MESES_MAP.items():
        if f"{nome_mes}/{ano_fatura}" in texto or f"{nome_mes} {ano_fatura}" in texto:
            return num_mes, ano_fatura
            
    return datetime.now().month, ano_fatura


def _resolver_ano_transacao(dia: int, mes: int, mes_ref: int, ano_ref: int) -> int:
    """Resolve o ano de uma transação considerando a virada de ano."""
    # Se a fatura é de Janeiro (1) e o lançamento é de Dezembro (12)
    if mes == 12 and mes_ref == 1:
        return ano_ref - 1
    # Se o lançamento é de um mês muito a frente da fatura (improvável, mas segurança)
    if mes > mes_ref + 1 and mes != 12:
         # Pode ser uma fatura antiga sendo lida no ano atual
         pass
    return ano_ref


def _detectar_banco_fatura(texto: str) -> str:
    texto_norm = _normalizar_texto_parser(texto)
    bancos = [
        ("Nubank", ["nubank"]),
        ("Inter", ["inter"]),
        ("Caixa", ["caixa", "cartoes caixa", "cartões caixa"]),
        ("Bradesco", ["bradesco"]),
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

    # Formato DD/MM ou DD/MM/AAAA
    if re.fullmatch(r"\d{2}/\d{2}(?:/\d{2,4})?", data):
        partes = data.split("/")
        dia = int(partes[0])
        mes = int(partes[1])
        if len(partes) == 3:
            ano = int(partes[2])
            if ano < 100: ano += 2000
        else:
            ano = _resolver_ano_transacao(dia, mes, mes_ref, ano_ref)
        try:
            return datetime(ano, mes, dia)
        except Exception:
            return None

    # Formato DD MMM (ex: 25 MAR)
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

    # Formato DD de MES de AAAA
    match_ext = re.fullmatch(r"(\d{2})\s+de\s+([A-Za-zÇç]{3,9})(?:\s+de\s+(\d{4}))?", data, flags=re.IGNORECASE)
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
    desc = re.sub(r"\b(?:rio de janeir|rio de janeiro|sao paulo|so paulo|r de janeiro)\b.*$", "", desc, flags=re.IGNORECASE)
    desc = re.sub(r"\b(?:cartao|cartão)\s+\d{4}\b", "", desc, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", desc).strip(" -|:")


def _descricao_deve_ser_ignoradas(descricao: str) -> bool:
    desc_norm = _normalizar_texto_parser(descricao)
    if not desc_norm:
        return True
    return any(token in desc_norm for token in _DESC_BLOQUEADA)


def _parse_linha_transacao_fatura(linha: str, mes_ref: int, ano_ref: int) -> dict | None:
    # Regexes ultra-flexíveis: procuram data em qualquer lugar e valor no final, 
    # permitindo ruído (como número de documento da Caixa) no meio.
    padroes = [
        # Formato: DD/MM (opcional /AAAA) ... Ruído ... Valor
        re.compile(r"(?P<data>\d{2}/\d{2}(?:/\d{2,4})?)\s+(?P<corpo>.+?)\s+(?P<valor>-?R?\$?\s?[0-9\.\,]+\s*(?:[DCdc])?)$"),
        # Formato: DD de MÊS ... Ruído ... Valor
        re.compile(r"(?P<data>\d{2}\s+de\s+[A-Za-zÇç]{3,9}\.?(?:\s+\d{4})?)\s+(?P<corpo>.+?)\s+(?P<valor>-?R?\$?\s?[0-9\.\,]+\s*(?:[DCdc])?)$", re.IGNORECASE),
        # Formato: DD MÊS (ex: 25 MAR) ... Ruído ... Valor
        re.compile(r"(?P<data>\d{2}\s+[A-Za-zÇç]{3,9}\.?)\s+(?P<corpo>.+?)\s+(?P<valor>-?R?\$?\s?[0-9\.\,]+\s*(?:[DCdc])?)$", re.IGNORECASE),
    ]

    linha_limpa = linha.strip()
    for padrao in padroes:
        match = padrao.search(linha_limpa) # search em vez de match para ignorar prefixos inúteis
        if not match:
            continue
            
        dt_obj = _parse_data_fatura_local(match.group("data"), mes_ref, ano_ref)
        if not dt_obj:
            continue

        corpo = match.group("corpo").strip()
        
        # Especial Caixa: Se o corpo terminar com um número longo (documento), removemos
        # Ex: "LOJA XPTO 123456789" -> "LOJA XPTO"
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

async def _parse_fatura_pdf_with_gemini(file_bytes: bytes) -> Tuple[List[Dict], int, str, float]:
    import config
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    cached = _get_cached_parse_result(file_bytes)
    if cached:
        logger.info("♻️ Reutilizando resultado em cache para este PDF de fatura.")
        return cached

    api_key_debug = config.GEMINI_API_KEY or ""
    masked_key = f"{api_key_debug[:4]}...{api_key_debug[-4:]}" if len(api_key_debug) > 8 else "NAO_CONFIGURADA"
    logger.info(f"🔑 [DEBUG] Chave API Ativa: {masked_key} | Modelo: {config.GEMINI_MODEL_NAME}")

    try:
        genai.configure(api_key=config.GEMINI_API_KEY.strip().strip("'\""))
    except Exception as e:
        logger.warning(f"Erro ao re-configurar genai no fatura_handler: {e}")

    linhas_preview = _extrair_texto_pdf_local(file_bytes)
    mes_ref, ano_ref = _detectar_referencia_fatura(linhas_preview)
    
    # Prioridade para o modelo 1.5 Flash: Mais estável e com maior cota gratuita (1500 RPD)
    model_candidates = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]

    logger.info("Pipeline de fatura: Gemini Multimodal (Prioridade 1.5 Flash) -> Auditoria Universal")

    prompt = f"""
    Você é um SISTEMA DE AUDITORIA FINANCEIRA de ALTA PRECISÃO.
    Sua tarefa é ler este PDF de fatura de cartão de crédito e extrair TODAS as transações sem exceção.

    DATA ATUAL: {datetime.now().strftime('%d/%m/%Y')}
    REFERÊNCIA: {mes_ref:02d}/{ano_ref}

    DIRETRIZES UNIVERSAIS:
    1. BUSCA EXAUSTIVA: Procure transações em todas as seções: 'Compras Nacionais', 'Compras Internacionais', 'Movimentações', 'Serviços', 'Parcelamentos' e 'Encargos'.
    2. LIMPEZA DE DESCRIÇÃO: 
       - Extraia apenas o nome do estabelecimento comercial.
       - Remova números de documento, cidades ou códigos que venham após o nome (especialmente comum na CAIXA).
       - Exemplo: 'MERCADO EXTRA 123456 RIO DE JANEIRO' -> 'MERCADO EXTRA'.
    3. VALORES E SINAIS:
       - Gastos, Compras, IOF, Juros: Valor NEGATIVO (ex: -150.40).
       - Pagamentos de Fatura, Estornos, Créditos, Cashback: Valor POSITIVO (ex: 500.00).
       - Ignore as letras 'D' ou 'C', use-as apenas para confirmar o sinal.
    4. INTEGRIDADE MATEMÁTICA: 
       - Localize o valor de 'TOTAL DA FATURA' ou 'VALOR A PAGAR' no documento.
       - A soma de todas as transações (positivas e negativas) deve chegar o mais próximo possível deste total.

    JSON OBRIGATÓRIO:
    {{
        "banco": "Nome da Instituição",
        "total_fatura": 0.0,
        "transacoes": [
            {{
                "data": "YYYY-MM-DD",
                "descricao": "NOME LIMPO",
                "valor": -123.45,
                "parcela": "01/10 (se houver)"
            }}
        ]
    }}
    """

    def _parse_json_response(text: str) -> dict | None:
        if not text: return None
        # Limpa blocos de código markdown se existirem
        text = re.sub(r'```json\s*|\s*```', '', text)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match: return None
        try: return json.loads(match.group(0))
        except Exception: return None

    def _parse_data_fatura(raw_data: str) -> datetime | None:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d/%m"):
            try:
                dt = datetime.strptime(str(raw_data), fmt)
                if fmt == "%d/%m":
                    ano = _resolver_ano_transacao(dt.day, dt.month, mes_ref, ano_ref)
                    dt = dt.replace(year=ano)
                elif dt.year < 100:
                    dt = dt.replace(year=2000 + dt.year)
                return dt
            except Exception:
                continue
        return None

    def _normalizar_resultado_bruto(data: dict, origem_prefixo: str) -> Tuple[List[Dict], int, str, float]:
        transacoes_finais: List[Dict] = []
        ignoradas_count = 0
        banco = str(data.get("banco", "Desconhecido") or "Desconhecido")
        total_pdf = float(data.get("total_fatura", 0.0) or 0.0)
        
        # Blacklist reduzida: Ignora apenas o 'Total' da fatura para não duplicar, 
        # mas mantém itens que parecem transações de serviço.
        blacklist = [
            "saldo anterior",
            "total da fatura",
            "limite",
            "demonstrativo",
            "fatura anterior",
            "saldo a pagar",
            "pagamento recebido",
            "valor do pagamento",
        ]

        for item in data.get("transacoes", []):
            try:
                descricao = str(item.get("descricao", "") or "").strip()
                if not descricao or any(term in descricao.lower() for term in blacklist):
                    continue

                valor = float(item.get("valor", 0.0) or 0.0)
                if abs(valor) < 0.01: continue

                dt_obj = _parse_data_fatura(item.get("data"))
                if not dt_obj: continue

                transacoes_finais.append({
                    "descricao": descricao,
                    "valor": valor,
                    "data_transacao": dt_obj,
                    "forma_pagamento": "Crédito",
                    "origem": f"{origem_prefixo}_{banco.lower().replace(' ', '_')}",
                    "parcela": item.get("parcela"),
                })
            except Exception:
                ignoradas_count += 1

        # Deduplicação Final
        deduped: List[Dict] = []
        seen = set()
        for t in transacoes_finais:
            key = (t["data_transacao"].strftime("%Y-%m-%d"), t["descricao"].lower(), round(t["valor"], 2))
            if key in seen: continue
            seen.add(key)
            deduped.append(t)

        return deduped, ignoradas_count, banco, total_pdf

    def _resultado_parece_valido(transacoes: List[Dict], total_pdf: float) -> bool:
        if not transacoes: return False
        
        # Saldo líquido extraído (soma algébrica)
        saldo_extraido = sum(float(t["valor"]) for t in transacoes)
        
        # Se temos o total do PDF, o rigor é de 90% (alguns centavos/IOF podem variar)
        if total_pdf > 0:
            # Em faturas, o total declarado é o que o usuário deve pagar (geralmente saldo negativo)
            # Mas o PDF costuma mostrar o valor absoluto.
            diferenca = abs(abs(saldo_extraido) - abs(total_pdf))
            percentual_erro = (diferenca / abs(total_pdf)) if total_pdf != 0 else 0
            
            if percentual_erro > 0.15: # Erro maior que 15% rejeita
                logger.warning(f"Extração Rejeitada: Soma R$ {saldo_extraido:.2f} vs PDF R$ {total_pdf:.2f} (Erro: {percentual_erro:.1%})")
                return False
                
        return True

    # 1. TENTATIVA PRINCIPAL: GEMINI MULTIMODAL
    pdf_part = {"mime_type": "application/pdf", "data": file_bytes}
    for model_name in model_candidates:
        try:
            logger.info("🤖 Tentando extração multimodal direta com %s", model_name)
            model = genai.GenerativeModel(model_name)
            response = await model.generate_content_async(
                [prompt, pdf_part],
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                },
            )
            
            resp_text = getattr(response, "text", "")
            if not resp_text:
                logger.warning(f"Resposta vazia de {model_name}")
                continue

            json_data = _parse_json_response(resp_text)
            if not json_data:
                logger.warning("Resposta do Gemini sem JSON utilizável com %s", model_name)
                continue
                
            transacoes, ignoradas, banco, total_pdf = _normalizar_resultado_bruto(json_data, "fatura_pdf")
            if _resultado_parece_valido(transacoes, total_pdf):
                logger.info("✅ Extração Gemini Multimodal funcionou com %s (%s transações)", model_name, len(transacoes))
                result = (transacoes, ignoradas, banco, total_pdf)
                _set_cached_parse_result(file_bytes, result)
                return result
            logger.warning("Resultado do Gemini com %s foi descartado por inconsistência matemática.", model_name)
        except Exception as exc:
            err_msg = str(exc)
            if "429" in err_msg or "quota" in err_msg.lower():
                logger.error("🛑 Cota atingida (429) no modelo %s. Interrompendo loop para tentar fallbacks.", model_name)
                break
            logger.warning("Falha na extração multimodal direta com %s: %s", model_name, err_msg)

    # 2. FALLBACK: PARSER LOCAL HEURÍSTICO
    logger.info("⚠️ Gemini falhou ou foi inconsistente. Acionando fallback: Parser Local Heurístico.")
    transacoes_local, ignoradas_local, banco_local, total_local = _parse_fatura_pdf_local(file_bytes)
    if _resultado_parece_valido(transacoes_local, total_local):
        logger.info(
            "✅ Parser local aprovou a fatura (%s transações, banco=%s, total=%s)",
            len(transacoes_local),
            banco_local,
            total_local,
        )
        result = (transacoes_local, ignoradas_local, banco_local, total_local)
        _set_cached_parse_result(file_bytes, result)
        return result

    if transacoes_local:
        logger.warning(
            "⚠️ Parser local também é impreciso matematicamente, mas retornando melhor esforço (%s transações).",
            len(transacoes_local),
        )
        result = (transacoes_local, ignoradas_local, banco_local, total_local)
        _set_cached_parse_result(file_bytes, result)
        return result

    from .invoice_processor import UniversalInvoiceExtractor

    extractor = UniversalInvoiceExtractor()
    logger.info("🧩 Fallback para parser local do UniversalInvoiceExtractor")
    texto_pdf = extractor._extract_pdf_text(file_bytes)
    regex_invoice = extractor._build_regex_invoice_schema(texto_pdf)
    if not regex_invoice or not regex_invoice.itens:
        raise RuntimeError("Não foi possível extrair transações desta fatura. O PDF foi lido, mas nenhum lançamento confiável foi encontrado.")

    total_pdf = float(regex_invoice.valor_total or 0.0)
    transacoes_finais: List[Dict] = []
    ignoradas_count = 0
    for item in regex_invoice.itens:
        try:
            dt_obj = datetime.strptime(item.data or regex_invoice.data, "%Y-%m-%d")
            transacoes_finais.append({
                "descricao": str(item.descricao).strip(),
                "valor": float(item.valor),
                "data_transacao": dt_obj,
                "forma_pagamento": "Crédito",
                "origem": "fatura_regex",
                "parcela": item.parcela
            })
        except Exception as e:
            logger.warning("Erro ao processar item do parser local da fatura: %s", e)
            ignoradas_count += 1

    if not _resultado_parece_valido(transacoes_finais, total_pdf):
        raise RuntimeError("A fatura foi lida, mas os dados extraídos ficaram incoerentes com o total do PDF.")

    result = (transacoes_finais, ignoradas_count, regex_invoice.estabelecimento, total_pdf)
    _set_cached_parse_result(file_bytes, result)
    return result

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
        "O sistema agora extrai datas individuais e parcelamentos com alta precisão."
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
        await update.message.reply_text("Envie um arquivo PDF valido.")
        return FATURA_AWAIT_FILE

    if document.file_size and document.file_size > MAX_PDF_SIZE_BYTES:
        await update.message.reply_text(
            "❌ Arquivo muito grande para importar aqui.\n"
            f"Tamanho maximo: {MAX_PDF_SIZE_MB}MB.\n"
            "Dica: se passar desse limite, exporte em partes (mesmo banco/cartao)."
        )
        return FATURA_AWAIT_FILE

    try:
        file_obj = await document.get_file()
        file_bytes = await file_obj.download_as_bytearray()
    except Exception:
        await update.message.reply_text(
            "❌ Nao consegui baixar esse PDF.\n"
            f"Tente enviar um arquivo menor que {MAX_PDF_SIZE_MB}MB."
        )
        return FATURA_AWAIT_FILE

    process_msg = await update.message.reply_text(
        "📄 PDF detectado! Extraindo lançamentos com IA visual...\n"
        "Isso pode levar alguns segundos."
    )

    try:
        transacoes, ignoradas, origem_label, total_pdf = await asyncio.wait_for(
            _parse_fatura_pdf_with_gemini(bytes(file_bytes)),
            timeout=MAX_PDF_PARSE_SECONDS,
        )
    except asyncio.TimeoutError:
        await process_msg.edit_text(
            "⏱️ O processamento da fatura excedeu o tempo limite.\n"
            "Tente enviar novamente ou exportar em partes menores."
        )
        return FATURA_AWAIT_FILE
    except Exception as exc:
        logger.exception("Erro ao processar fatura PDF", exc_info=True)
        error_str = str(exc)
        
        if "password" in error_str.lower() or "senha" in error_str.lower() or "encrypted" in error_str.lower():
            await process_msg.edit_text(
                "🔒 Este PDF está protegido por senha.\n"
                "Remova a senha no app do banco e envie novamente."
            )
        else:
            await process_msg.edit_text(
                f"❌ <b>Erro no Processamento IA</b>\n\nOcorreu uma falha ao analisar o PDF. Verifique se o arquivo está legível.",
                parse_mode="HTML"
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

        total_pdf = context.user_data.get("fatura_valor_total_pdf")
        # Soma algébrica (despesas são negativas, créditos positivos)
        saldo_extraido = sum(float(t["valor"]) for t in transacoes)
        
        ajuste_pdf = 0.0
        # Ajuste automático apenas se a diferença for pequena (possíveis centavos de arredondamento)
        # Se a diferença for grande, é melhor NÃO ajustar para não poluir com valores mágicos.
        if isinstance(total_pdf, (int, float)):
            diferenca = round(float(total_pdf) + float(saldo_extraido), 2) # saldo_extraido já é negativo para despesas
            if 0.01 <= abs(diferenca) < 5.00:
                data_ajuste = max((t["data_transacao"] for t in transacoes), default=datetime.now())
                transacoes.append({
                    "data_transacao": data_ajuste,
                    "descricao": "Ajuste de centavos (Fatura)",
                    "valor": -diferenca,
                    "forma_pagamento": "Crédito",
                    "origem": "fatura_ajuste_pdf",
                })
                context.user_data["fatura_ajuste_pdf"] = abs(diferenca)
                context.user_data["fatura_transacoes"] = transacoes
        
        total = len(transacoes)
        total_debito = sum(-t["valor"] for t in transacoes if t["valor"] < 0)
        total_credito = sum(t["valor"] for t in transacoes if t["valor"] > 0)
        ajuste_pdf_abs = context.user_data.get("fatura_ajuste_pdf")

        preview_lines = []
        # Sort transactions by date for the preview
        sorted_transacoes = sorted(transacoes, key=lambda x: x["data_transacao"])
        for item in sorted_transacoes[:10]:
            data = item["data_transacao"].strftime("%d/%m")
            valor_label = _fmt_brl(item["valor"])
            parcela = f" ({item['parcela']})" if item.get('parcela') else ""
            desc = _compact_desc(f"{item.get('descricao', '')}{parcela}")
            preview_lines.append(f"• {data} | {desc} | {valor_label}")

        top_debitos = sorted(
            [t for t in transacoes if float(t.get("valor", 0)) < 0],
            key=lambda t: abs(float(t.get("valor", 0))),
            reverse=True,
        )[:3]
        top_lines = []
        for item in top_debitos:
            top_lines.append(f"• {_compact_desc(item.get('descricao', ''), 34)} ({_fmt_brl(item['valor'])})")

        preview_text = "\n".join(preview_lines) if preview_lines else "• Sem itens para preview"
        maiores_text = "\n".join(top_lines) if top_lines else "• Sem debitos"
        origem_label = context.user_data.get("fatura_origem_label", "Desconhecido")

        resumo_linhas = [
            f"🧾 <b>Resumo da Fatura ({origem_label})</b>",
            "",
            f"📌 <b>Transações detectadas:</b> <code>{total}</code>",
            f"↩️ <b>Itens ignorados:</b> <code>{ignoradas}</code>",
            f"💸 <b>Total débitos:</b> <code>{_fmt_brl(total_debito)}</code>",
            f"💰 <b>Total créditos:</b> <code>{_fmt_brl(total_credito)}</code>",
        ]
        if isinstance(total_pdf, (int, float)):
            resumo_linhas.append(f"🧮 <b>Total no PDF:</b> <code>{_fmt_brl(total_pdf)}</code>")
        if isinstance(ajuste_pdf_abs, (int, float)) and ajuste_pdf_abs >= 0.01:
            resumo_linhas.append(f"⚖️ <b>Ajuste aplicado:</b> <code>{_fmt_brl(ajuste_pdf_abs)}</code>")
        
        resumo_linhas.extend([
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
        ])
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
    """
    Handler para callbacks de confirmação de fatura.
    Trata: fatura_cancelar, fatura_editar_inline, fatura_salvar
    """
    query = update.callback_query
    
    # Responder ao callback imediatamente
    try:
        await query.answer()
    except Exception as e:
        logger.warning("Falha ao responder callback imediatamente: %s", e)

    # Processar ação
    try:
        raw_action = query.data or ""
        action_parts = raw_action.split(":", 1)
        action = action_parts[0]
        draft_token = action_parts[1] if len(action_parts) > 1 else (context.user_data.get("fatura_draft_token") or "")
        logger.info(f"fatura_confirm: action={action}, user={query.from_user.id}")
        
        if action == "fatura_cancelar":
            context.user_data.pop("fatura_transacoes", None)
            context.user_data.pop("fatura_conta_id", None)
            context.user_data.pop("fatura_ajuste_pdf", None)
            context.user_data.pop("fatura_draft_token", None)
            await query.edit_message_text("❌ Importacao cancelada.")
            return ConversationHandler.END

        if action == "fatura_editar_inline":
            logger.info("Processando fatura_editar_inline para user=%s", query.from_user.id)
            draft_data = get_fatura_draft(draft_token, query.from_user.id) if draft_token else None
            transacoes = (draft_data or {}).get("transacoes") or context.user_data.get("fatura_transacoes", [])
            conta_id = (draft_data or {}).get("conta_id")
            origem_label = (draft_data or {}).get("origem_label") or context.user_data.get("fatura_origem_label", "Inter")

            if not transacoes:
                logger.warning("Dados de fatura expirados: transacoes=%s, conta_id=%s", bool(transacoes), conta_id)
                await query.edit_message_text("❌ Dados da fatura expiraram. Envie o PDF novamente.")
                return ConversationHandler.END

            conta_nome = "Sem conta"

            token = create_fatura_draft(
                telegram_user_id=query.from_user.id,
                conta_id=conta_id,
                conta_nome=conta_nome,
                transacoes=transacoes,
                origem_label=origem_label,
            )
            set_pending_editor_token(query.from_user.id, token)

            try:
                webapp_url = _get_fatura_webapp_url("fatura_editor", token)
                logger.info("URL do editor gerada: %s (truncado)", webapp_url[:80])
            except Exception as e:
                logger.error("Falha ao gerar webapp_url: %s", e, exc_info=True)
                raise

            # Evita problemas em alguns clientes ao tentar substituir o teclado inline por um botão web_app.
            await query.edit_message_text(
                "✅ Rascunho preparado. Vou te enviar o botao para abrir o editor no MiniApp.",
                parse_mode="HTML",
            )
            logger.info("Enviando botão de editor para user=%s", query.from_user.id)
            await query.message.reply_text(
                "📱 <b>Editar lancamentos da fatura</b>\n\n"
                "Toque no botao abaixo para abrir o editor.\n"
                "Se o Telegram nao abrir por esse botao, toque em <b>🚀 Abrir o App</b> no teclado que o editor abre automaticamente.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Abrir Editor da Fatura", web_app=WebAppInfo(url=webapp_url))],
                ]),
            )
            logger.info("Botão de editor enviado com sucesso")
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
                logger.error(f"❌ Transações não encontradas no user_data para o usuário {query.from_user.id}. Dados perdidos.")
                try:
                    await query.edit_message_text(
                        "❌ <b>Dados da fatura perdidos.</b>\n\n"
                        "Infelizmente o sistema reiniciou ou a sessão expirou. Por favor, envie o PDF novamente para processar.",
                        parse_mode="HTML"
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
                        logger.debug("Falha ao conceder XP da fatura (nao critico).")
                    # Garante consistencia imediata no chat/miniapp apos importacao da fatura.
                    try:
                        limpar_cache_usuario(int(query.from_user.id))
                    except Exception:
                        logger.debug("Falha ao limpar cache do usuario apos importacao de fatura.")
                
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

        # Ação desconhecida
        logger.warning(f"Acao desconhecida em fatura_confirm: {action}")
        await query.answer("Acao invalida", show_alert=True)
        return FATURA_CONFIRMATION_STATE
        
    except Exception as e:
        logger.error(f"ERRO NO FATURA_CONFIRM: action={query.data}, error={str(e)}", exc_info=True)
        try:
            await query.answer(f"❌ Erro: {str(e)[:50]}", show_alert=True)
        except Exception as e2:
            logger.error(f"Falha ao enviar erro ao user: {e2}")
        return FATURA_CONFIRMATION_STATE


async def fatura_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Importacao cancelada.")
    elif update.message:
        await update.message.reply_text("Importacao cancelada.")
    context.user_data.pop("fatura_transacoes", None)
    context.user_data.pop("fatura_conta_id", None)
    context.user_data.pop("fatura_origem_label", None)
    return ConversationHandler.END


fatura_conv = ConversationHandler(
    entry_points=[CommandHandler("fatura", fatura_start), MessageHandler(filters.Regex(r"^🧾 Fatura$"), fatura_start)],
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
