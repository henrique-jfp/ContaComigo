import json
import logging
import os
import re
import uuid
import asyncio
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote, urlencode, urlparse

import pdfplumber
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfplumber.utils.exceptions import PdfminerException
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
from .services import salvar_transacoes_generica
from .fatura_draft_store import create_fatura_draft, set_pending_editor_token
from .states import (
    FATURA_AWAIT_FILE,
    FATURA_CONFIRMATION_STATE,
    FATURA_TRAIN_CONSENT,
    FATURA_TRAIN_BANK,
)
from .gamification_utils import give_xp_for_action, touch_user_interaction

logger = logging.getLogger(__name__)

MAX_PDF_SIZE_MB = int(os.getenv("FATURA_MAX_PDF_SIZE_MB", "100"))
MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024
MAX_PDF_PARSE_SECONDS = int(os.getenv("FATURA_PARSE_TIMEOUT_SECONDS", "300"))
TRAINING_TEXT_MAX_LINES = 80
GENERIC_TEXT_MAX_LINES = 2000
GENERIC_MIN_TRANSACOES = 3
GENERIC_MIN_SCORE = 0.08
TRAINING_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "fatura_training")
)

_MONTH_MAP = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}


def _fmt_brl(value: float) -> str:
    normalized = f"{abs(float(value)):.2f}".replace(".", ",")
    return f"R$ {normalized}"


def _compact_desc(text: str, max_len: int = 42) -> str:
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1].rstrip() + "..."


def _parse_inter_transaction_line(line: str) -> Optional[Dict]:
    raw = (line or "").strip()
    if not raw:
        return None

    # Limpa glifos comuns do PDF e normaliza espaços
    compact = re.sub(r"[\ue000-\uf8ff]", " ", raw)
    compact = re.sub(r"\s+", " ", compact).strip()

    # Inter costuma vir sem espaços no início: 10denov.2025 ...
    pattern = re.compile(
        r"^(\d{1,2})\s*de\s*([A-Za-z]{3})\.?\s*(\d{4})\s+(.+?)\s*([+-])?\s*R\$\s*([\d\.]+,\d{2})$",
        re.IGNORECASE,
    )
    match = pattern.match(compact)
    if not match:
        return None

    if "****" in compact:
        return None

    day = int(match.group(1))
    month_token = match.group(2).lower()
    year = int(match.group(3))
    desc = match.group(4).strip(" -+")
    explicit_sign = (match.group(5) or "").strip()
    value_str = match.group(6)

    month = _MONTH_MAP.get(month_token)
    if not month:
        return None

    value = float(value_str.replace(".", "").replace(",", "."))

    sign = -1.0
    if explicit_sign == "+":
        sign = 1.0
    elif explicit_sign == "-":
        sign = -1.0

    if not desc:
        return None

    if "pagamento" in desc.lower() or "estorno" in desc.lower():
        return None

    try:
        date_obj = datetime(year, month, day)
    except ValueError:
        return None

    return {
        "descricao": desc,
        "valor": sign * value,
        "data_transacao": date_obj,
        "forma_pagamento": "Cartao de Credito",
        "origem": "fatura_pdf_inter",
    }


def parse_inter_pdf_bytes(file_bytes: bytes) -> Tuple[List[Dict], int]:
    transacoes: List[Dict] = []
    ignoradas = 0
    in_section = False
    with pdfplumber.open(io_bytes_to_pdf(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                lower_line = re.sub(r"\s+", "", line.lower())
                if "despesasdafatura" in lower_line:
                    in_section = True
                    continue
                if not in_section:
                    continue
                if "datamoviment" in lower_line:
                    continue
                item = _parse_inter_transaction_line(line)
                if item:
                    transacoes.append(item)
                elif "pagamento" in lower_line or "estorno" in lower_line:
                    ignoradas += 1

    # Remove duplicados por descricao+data+valor
    unique: Dict[Tuple[str, str, float], Dict] = {}
    for item in transacoes:
        key = (item["descricao"], item["data_transacao"].strftime("%Y-%m-%d"), float(item["valor"]))
        unique[key] = item
    return list(unique.values()), ignoradas


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


def io_bytes_to_pdf(file_bytes: bytes):
    from io import BytesIO

    return BytesIO(file_bytes)


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_") or "desconhecido"


def _extract_pdf_text_sample(file_bytes: bytes, max_lines: int = TRAINING_TEXT_MAX_LINES) -> List[str]:
    lines: List[str] = []
    try:
        with pdfplumber.open(io_bytes_to_pdf(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    if line.strip():
                        lines.append(line.strip())
                    if len(lines) >= max_lines:
                        return lines
    except Exception:
        return []
    return lines


def _extract_pdf_text_lines(file_bytes: bytes, max_lines: int = GENERIC_TEXT_MAX_LINES) -> List[str]:
    lines: List[str] = []
    try:
        with pdfplumber.open(io_bytes_to_pdf(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    if line.strip():
                        lines.append(line.strip())
                    if len(lines) >= max_lines:
                        return lines
    except Exception:
        return []
    return lines


def _extract_reference_year(lines: List[str]) -> int:
    for line in lines:
        match = re.search(r"\b(20\d{2})\b", line)
        if match:
            return int(match.group(1))
    return datetime.now().year


def _is_pdf_password_error(exc: Exception) -> bool:
    if isinstance(exc, PDFPasswordIncorrect):
        return True
    if isinstance(exc, PdfminerException):
        cause = getattr(exc, "__cause__", None)
        if isinstance(cause, PDFPasswordIncorrect):
            return True
    message = str(exc).lower()
    return "password" in message and "pdf" in message


def _parse_fatura_pipeline(file_bytes: bytes) -> Tuple[List[Dict], int, str]:
    transacoes, ignoradas = parse_inter_pdf_bytes(file_bytes)
    origem_label = "Inter"
    if transacoes:
        return transacoes, ignoradas, origem_label

    text_lines = _extract_pdf_text_lines(file_bytes)
    if _is_bradesco_pdf(text_lines):
        transacoes, ignoradas = _parse_bradesco_pdf_lines(text_lines)
        if transacoes:
            return transacoes, ignoradas, "Bradesco"

    bank_name, _score = _match_bank_from_samples(text_lines)
    transacoes, ignoradas = _parse_generic_transactions(text_lines, bank_name)
    if transacoes and len(transacoes) >= GENERIC_MIN_TRANSACOES:
        return transacoes, ignoradas, bank_name or "Outros"

    return [], 0, "Inter"


def _is_bradesco_pdf(lines: List[str]) -> bool:
    for line in lines[:120]:
        if "bradesco" in line.lower():
            return True
    return False


def _parse_bradesco_pdf_lines(lines: List[str]) -> Tuple[List[Dict], int]:
    transacoes: List[Dict] = []
    ignoradas = 0
    in_section = False
    year_ref = _extract_reference_year(lines)

    for raw_line in lines:
        line = raw_line.strip()
        lower_line = line.lower()

        if "historico de lancamentos" in lower_line or "histórico de lançamentos" in lower_line:
            in_section = True
            continue

        if not in_section:
            continue

        if not re.match(r"^\d{2}/\d{2}\b", line):
            continue

        if "iof" not in lower_line:
            if any(token in lower_line for token in [
                "total utilizado",
                "disponivel",
                "limites",
                "compras r$",
                "saque r$",
                "taxa",
                "rotativo",
            ]):
                continue

        date_match = re.match(r"^(\d{2})/(\d{2})\s+(.*)$", line)
        if not date_match:
            continue

        day = int(date_match.group(1))
        month = int(date_match.group(2))
        rest = date_match.group(3).strip()

        value_matches = list(re.finditer(r"(\d{1,3}(?:\.\d{3})*,\d{2})(-?)", rest))
        value_match = None
        for match in reversed(value_matches):
            end_index = match.end()
            if end_index < len(rest) and rest[end_index] == "%":
                continue
            value_match = match
            break

        if not value_match:
            continue

        value_str = value_match.group(1)
        value = float(value_str.replace(".", "").replace(",", "."))
        sign = -1.0
        if value_match.group(2) == "-":
            sign = -1.0
        elif "credito" in lower_line or "estorno" in lower_line:
            sign = 1.0

        desc = rest[: value_match.start()].strip()
        desc = re.sub(r"\b\d{2}/\d{2}(?:/\d{2,4})?\b", "", desc).strip()
        desc = desc.strip("- ")

        if not desc:
            continue

        if "pag boleto" in lower_line or "pagamento" in lower_line:
            ignoradas += 1
            continue

        try:
            date_obj = datetime(year_ref, month, day)
        except ValueError:
            continue

        transacoes.append(
            {
                "descricao": desc,
                "valor": sign * value,
                "data_transacao": date_obj,
                "forma_pagamento": "Cartao de Credito",
                "origem": "fatura_pdf_bradesco",
            }
        )

    unique: Dict[Tuple[str, str, float], Dict] = {}
    for item in transacoes:
        key = (item["descricao"], item["data_transacao"].strftime("%Y-%m-%d"), item["valor"])
        unique[key] = item

    return list(unique.values()), ignoradas


def _tokenize_lines(lines: List[str]) -> set[str]:
    tokens: set[str] = set()
    for line in lines:
        normalized = re.sub(r"\d+", " ", line.lower())
        for token in re.split(r"[^a-z]+", normalized):
            if len(token) >= 4:
                tokens.add(token)
    return tokens


def _load_training_samples() -> List[Dict]:
    samples: List[Dict] = []
    if not os.path.isdir(TRAINING_DIR):
        return samples

    for name in os.listdir(TRAINING_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(TRAINING_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as meta_file:
                meta = json.load(meta_file)
        except Exception:
            continue

        token_sample = meta.get("token_sample")
        text_sample = meta.get("text_sample", []) or []
        bank_name = meta.get("bank_name")
        if not bank_name or not text_sample:
            continue

        samples.append(
            {
                "bank_name": bank_name,
                "tokens": set(token_sample) if token_sample else _tokenize_lines(text_sample),
            }
        )
    return samples


def _match_bank_from_samples(lines: List[str]) -> Tuple[Optional[str], float]:
    tokens = _tokenize_lines(lines)
    if not tokens:
        return None, 0.0

    best_score = 0.0
    best_bank: Optional[str] = None
    for sample in _load_training_samples():
        sample_tokens = sample.get("tokens") or set()
        if not sample_tokens:
            continue
        intersection = tokens.intersection(sample_tokens)
        score = len(intersection) / max(len(sample_tokens), 1)
        if score > best_score:
            best_score = score
            best_bank = sample.get("bank_name")

    if best_score < GENERIC_MIN_SCORE:
        return None, best_score

    return best_bank, best_score


def _parse_generic_transactions(lines: List[str], bank_name: Optional[str]) -> Tuple[List[Dict], int]:
    transacoes: List[Dict] = []
    ignoradas = 0
    now = datetime.now()
    origem = f"fatura_pdf_{_safe_slug(bank_name)}" if bank_name else "fatura_pdf_generic"

    for line in lines:
        lower_line = line.lower()
        if any(token in lower_line for token in [
            "pagamento", "estorno", "total", "saldo", "vencimento", "resumo"
        ]):
            if "pagamento" in lower_line or "estorno" in lower_line:
                ignoradas += 1
            continue

        date_match = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", line)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year_raw = date_match.group(3)
            if year_raw:
                year = int(year_raw)
                if year < 100:
                    year += 2000
            else:
                year = now.year
        else:
            alt_match = re.search(r"(\d{1,2})\s+de\s+([A-Za-z]{3})", line, re.IGNORECASE)
            if not alt_match:
                continue
            day = int(alt_match.group(1))
            month = _MONTH_MAP.get(alt_match.group(2).lower())
            if not month:
                continue
            year = now.year

        value_matches = list(re.finditer(r"R\$\s*([\d\.]+,\d{2})", line))
        if not value_matches:
            value_matches = list(re.finditer(r"\b([\d\.]+,\d{2})\b", line))
        if not value_matches:
            continue

        value_str = value_matches[-1].group(1)
        value = float(value_str.replace(".", "").replace(",", "."))
        sign = -1.0
        if "credito" in lower_line or "+" in line:
            sign = 1.0

        desc = line
        if value_matches:
            desc = line[: value_matches[-1].start()].strip()
        desc = desc.strip("-+ ")
        if not desc:
            continue

        try:
            date_obj = datetime(year, month, day)
        except ValueError:
            continue

        transacoes.append(
            {
                "descricao": desc,
                "valor": sign * value,
                "data_transacao": date_obj,
                "forma_pagamento": "Cartao de Credito",
                "origem": origem,
            }
        )

    return transacoes, ignoradas


def _store_training_sample(file_bytes: bytes, meta: Dict) -> str:
    os.makedirs(TRAINING_DIR, exist_ok=True)
    bank_slug = _safe_slug(meta.get("bank_name", "desconhecido"))
    sample_id = meta.get("sample_id") or str(uuid.uuid4())
    base_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{bank_slug}_{sample_id}"
    pdf_path = os.path.join(TRAINING_DIR, f"{base_name}.pdf")
    meta_path = os.path.join(TRAINING_DIR, f"{base_name}.json")

    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(file_bytes)

    with open(meta_path, "w", encoding="utf-8") as meta_file:
        json.dump(meta, meta_file, ensure_ascii=True, indent=2)

    return base_name


def _clear_training_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("fatura_training_bytes", None)
    context.user_data.pop("fatura_training_name", None)
    context.user_data.pop("fatura_training_size", None)
    context.user_data.pop("fatura_training_pages", None)
    context.user_data.pop("fatura_training_text", None)


async def fatura_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await touch_user_interaction(update.effective_user.id, context)
    await update.message.reply_text(
        "Envie a fatura do Banco Inter em PDF para importar os lancamentos.\n"
        f"Limite de tamanho: {MAX_PDF_SIZE_MB}MB."
    )
    return FATURA_AWAIT_FILE


async def fatura_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        "📄 PDF detectado! Estou processando a fatura.\n"
        "Se o arquivo for grande, pode demorar um pouco."
    )

    try:
        transacoes, ignoradas, origem_label = await asyncio.wait_for(
            asyncio.to_thread(_parse_fatura_pipeline, bytes(file_bytes)),
            timeout=MAX_PDF_PARSE_SECONDS,
        )
    except asyncio.TimeoutError:
        await process_msg.edit_text(
            "⏱️ O processamento da fatura excedeu o tempo limite.\n"
            "Tente enviar novamente ou exportar em partes por período."
        )
        return FATURA_AWAIT_FILE
    except Exception as exc:
        logger.exception("Erro ao processar fatura PDF", exc_info=True)
        if _is_pdf_password_error(exc):
            await process_msg.edit_text(
                "🔒 Este PDF está protegido por senha.\n"
                "Remova a senha no app do banco e envie novamente."
            )
        else:
            await process_msg.edit_text(
                "❌ Nao consegui ler esse PDF de fatura.\n"
                "Verifique se o arquivo nao está corrompido e tente novamente."
            )
        return FATURA_AWAIT_FILE
    else:
        try:
            await process_msg.delete()
        except Exception:
            pass

    if not transacoes:
        await update.message.reply_text(
            "Nao consegui localizar as transacoes da fatura. "
            "Verifique se o PDF e do Banco Inter e tente novamente.\n\n"
            "Quer ajudar a ensinar novos bancos? Posso guardar esse PDF "
            "(somente para treino interno)."
        )
        context.user_data["fatura_training_bytes"] = bytes(file_bytes)
        context.user_data["fatura_training_name"] = document.file_name or "fatura.pdf"
        context.user_data["fatura_training_size"] = document.file_size or len(file_bytes)
        try:
            with pdfplumber.open(io_bytes_to_pdf(bytes(file_bytes))) as pdf:
                context.user_data["fatura_training_pages"] = len(pdf.pages)
        except Exception:
            context.user_data["fatura_training_pages"] = None
        context.user_data["fatura_training_text"] = _extract_pdf_text_sample(bytes(file_bytes))

        keyboard = [
            [InlineKeyboardButton("Quero ajudar", callback_data="fatura_treino_sim")],
            [InlineKeyboardButton("Nao agora", callback_data="fatura_treino_nao")],
        ]
        await update.message.reply_text(
            "Deseja enviar este PDF para treino?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return FATURA_TRAIN_CONSENT

    context.user_data["fatura_transacoes"] = transacoes
    context.user_data["fatura_ignoradas"] = ignoradas
    context.user_data["fatura_origem_label"] = origem_label

    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, update.effective_user.id, update.effective_user.full_name)
        contas_cartao = db.query(Conta).filter(
            Conta.id_usuario == usuario_db.id,
            Conta.tipo.ilike("%cartao%")
        ).all()

        contas = contas_cartao or db.query(Conta).filter(
            Conta.id_usuario == usuario_db.id
        ).all()

        if not contas:
            await update.message.reply_text(
                "Nenhuma conta/cartao cadastrado. Use /configurar primeiro."
            )
            return ConversationHandler.END

        # Use first available account automatically
        primeira_conta = contas[0]
        context.user_data["fatura_conta_id"] = primeira_conta.id
        
        # Show summary directly with Confirm/Edit/Cancel buttons
        total = len(transacoes)
        total_debito = sum(-t["valor"] for t in transacoes if t["valor"] < 0)
        total_credito = sum(t["valor"] for t in transacoes if t["valor"] > 0)

        preview_lines = []
        for item in transacoes[:8]:
            data = item["data_transacao"].strftime("%d/%m")
            valor_label = _fmt_brl(item["valor"])
            desc = _compact_desc(item.get("descricao", ""))
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
        ignored_text = f"\n• Ignoradas (pagamentos/estornos): {ignoradas}" if ignoradas else ""
        conta_text = f" na conta <b>{primeira_conta.nome}</b>"

        origem_label = context.user_data.get("fatura_origem_label", "Inter")
        resumo = (
            f"<b>Resumo da fatura ({origem_label})</b>\n"
            f"• Transacoes detectadas: <b>{total}</b>{ignored_text}\n"
            f"• Total debitos: <b>{_fmt_brl(total_debito)}</b>\n"
            f"• Total creditos: {_fmt_brl(total_credito)}\n\n"
            f"<b>Maiores gastos detectados:</b>\n{maiores_text}\n\n"
            f"<b>Preview de lancamentos:</b>\n{preview_text}\n\n"
            f"<b>Acao:</b> Importar{conta_text}?\n"
            "Toque em <b>Editar</b> para revisar e corrigir antes de salvar."
        )

        keyboard = [
            [InlineKeyboardButton("✅ Confirmar e Salvar", callback_data="fatura_salvar")],
            [InlineKeyboardButton("✏️ Editar", callback_data="fatura_editar_inline")],
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
        await query.answer(timeout=5)
    except Exception as e:
        logger.warning("Falha ao responder callback imediatamente: %s", e)

    # Processar ação
    try:
        action = query.data
        logger.info(f"fatura_confirm: action={action}, user={query.from_user.id}")
        
        if action == "fatura_cancelar":
            context.user_data.pop("fatura_transacoes", None)
            context.user_data.pop("fatura_conta_id", None)
            await query.edit_message_text("❌ Importacao cancelada.")
            return ConversationHandler.END

        if action == "fatura_editar_inline":
            logger.info("Processando fatura_editar_inline para user=%s", query.from_user.id)
            transacoes = context.user_data.get("fatura_transacoes", [])
            conta_id = context.user_data.get("fatura_conta_id")
            origem_label = context.user_data.get("fatura_origem_label", "Inter")

            if not transacoes or not conta_id:
                logger.warning("Dados de fatura expirados: transacoes=%s, conta_id=%s", bool(transacoes), conta_id)
                await query.edit_message_text("❌ Dados da fatura expiraram. Envie o PDF novamente.")
                return ConversationHandler.END

            db = next(get_db())
            try:
                conta_obj = db.query(Conta).filter(Conta.id == conta_id).first()
                conta_nome = conta_obj.nome if conta_obj else "Cartao de Credito"
            finally:
                db.close()

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
            transacoes = context.user_data.get("fatura_transacoes", [])
            conta_id = context.user_data.get("fatura_conta_id")
            if not transacoes or not conta_id:
                await query.edit_message_text("❌ Dados da fatura perdidos. Tente novamente.")
                return ConversationHandler.END

            db = next(get_db())
            try:
                conta_obj = db.query(Conta).filter(Conta.id == conta_id).first()
                conta_nome = conta_obj.nome if conta_obj else "Cartao de Credito"
                for item in transacoes:
                    item["forma_pagamento"] = conta_nome

                usuario_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)
                tipo_origem = transacoes[0].get("origem", "fatura_pdf_generic") if transacoes else "fatura_pdf_generic"
                ok, msg, _stats = await salvar_transacoes_generica(
                    db, usuario_db, transacoes, conta_id, tipo_origem=tipo_origem
                )
                if ok:
                    try:
                        await give_xp_for_action(query.from_user.id, "FATURA_PROCESSADA", context)
                    except Exception:
                        logger.debug("Falha ao conceder XP da fatura (nao critico).")
                
                await query.edit_message_text(msg, parse_mode="HTML")
                return ConversationHandler.END
            finally:
                db.close()
                context.user_data.pop("fatura_transacoes", None)
                context.user_data.pop("fatura_conta_id", None)
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


async def fatura_training_consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "fatura_treino_nao":
        _clear_training_context(context)
        await query.edit_message_text("Tudo bem. Se quiser ajudar no futuro, me avise.")
        return ConversationHandler.END

    await query.edit_message_text(
        "Perfeito! Qual o banco/cartao dessa fatura?\n"
        "Ex: Nubank, Itau, C6, Bradesco"
    )
    return FATURA_TRAIN_BANK


async def fatura_training_receive_bank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    bank_name = (update.message.text or "").strip()
    if len(bank_name) < 2:
        await update.message.reply_text("Me diga apenas o nome do banco/cartao, por favor.")
        return FATURA_TRAIN_BANK

    file_bytes = context.user_data.get("fatura_training_bytes")
    if not file_bytes:
        await update.message.reply_text("Nao encontrei o PDF. Tente enviar novamente.")
        _clear_training_context(context)
        return ConversationHandler.END

    meta = {
        "sample_id": str(uuid.uuid4()),
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
        "bank_name": bank_name,
        "user_telegram_id": update.effective_user.id,
        "original_filename": context.user_data.get("fatura_training_name"),
        "file_size_bytes": context.user_data.get("fatura_training_size"),
        "page_count": context.user_data.get("fatura_training_pages"),
        "text_sample": context.user_data.get("fatura_training_text", []),
        "source": "fatura_training",
    }

    try:
        meta["token_sample"] = sorted(_tokenize_lines(meta.get("text_sample", [])))
        _store_training_sample(file_bytes, meta)
        await update.message.reply_text(
            "Obrigado! Seu PDF foi salvo para treino e vai ajudar a liberar novos bancos."
        )
    except Exception:
        await update.message.reply_text(
            "Ops, houve um erro ao salvar o treino. Tente novamente depois."
        )
    finally:
        _clear_training_context(context)

    return ConversationHandler.END


async def fatura_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Importacao cancelada.")
    elif update.message:
        await update.message.reply_text("Importacao cancelada.")
    context.user_data.pop("fatura_transacoes", None)
    context.user_data.pop("fatura_conta_id", None)
    context.user_data.pop("fatura_origem_label", None)
    _clear_training_context(context)
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
        FATURA_TRAIN_CONSENT: [
            CallbackQueryHandler(fatura_training_consent, pattern="^fatura_treino_")
        ],
        FATURA_TRAIN_BANK: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, fatura_training_receive_bank)
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
