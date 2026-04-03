import logging
import re
from datetime import datetime
from typing import List, Dict, Optional

import pdfplumber
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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
from .states import FATURA_AWAIT_FILE, FATURA_ASK_CONTA, FATURA_CONFIRMATION_STATE

logger = logging.getLogger(__name__)

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


def _parse_inter_transaction_line(line: str) -> Optional[Dict]:
    pattern = re.compile(r"^(\d{1,2}) de ([A-Za-z]{3})\.? (\d{4}) (.+)$")
    match = pattern.match(line.strip())
    if not match:
        return None

    if "****" in line:
        return None

    day = int(match.group(1))
    month_token = match.group(2).lower()
    year = int(match.group(3))
    rest = match.group(4).strip()

    month = _MONTH_MAP.get(month_token)
    if not month:
        return None

    value_matches = list(re.finditer(r"R\$\s*([\d\.]+,\d{2})", rest))
    if not value_matches:
        return None

    last_match = value_matches[-1]
    value_str = last_match.group(1)
    value = float(value_str.replace(".", "").replace(",", "."))

    sign = -1.0
    if "+ R$" in rest or "+R$" in rest:
        sign = 1.0
    elif " - R$" in rest or "- R$" in rest:
        sign = -1.0

    desc_part = rest[: last_match.start()].strip()
    desc = desc_part.strip(" -+")

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


def parse_inter_pdf_bytes(file_bytes: bytes) -> List[Dict]:
    transacoes: List[Dict] = []
    with pdfplumber.open(io_bytes_to_pdf(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                lower_line = line.lower()
                if "despesas da fatura" in lower_line or "data moviment" in lower_line:
                    continue
                item = _parse_inter_transaction_line(line)
                if item:
                    transacoes.append(item)
    return transacoes


def io_bytes_to_pdf(file_bytes: bytes):
    from io import BytesIO

    return BytesIO(file_bytes)


async def fatura_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Envie a fatura do Banco Inter em PDF para importar os lancamentos."
    )
    return FATURA_AWAIT_FILE


async def fatura_receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    document = update.message.document
    if not document or document.mime_type != "application/pdf":
        await update.message.reply_text("Envie um arquivo PDF valido.")
        return FATURA_AWAIT_FILE

    file_obj = await document.get_file()
    file_bytes = await file_obj.download_as_bytearray()

    transacoes = parse_inter_pdf_bytes(bytes(file_bytes))
    if not transacoes:
        await update.message.reply_text(
            "Nao consegui localizar as transacoes da fatura. "
            "Verifique se o PDF e do Banco Inter e tente novamente."
        )
        return ConversationHandler.END

    context.user_data["fatura_transacoes"] = transacoes

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

        botoes = [
            [InlineKeyboardButton(f"{c.nome}", callback_data=f"fatura_conta_{c.id}")]
            for c in contas
        ]
        await update.message.reply_text(
            "Selecione o cartao/conta para associar a fatura:",
            reply_markup=InlineKeyboardMarkup(botoes),
        )
        return FATURA_ASK_CONTA
    finally:
        db.close()


async def fatura_select_conta(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    conta_id = int(query.data.split("_")[-1])
    context.user_data["fatura_conta_id"] = conta_id

    transacoes = context.user_data.get("fatura_transacoes", [])
    total = len(transacoes)
    total_debito = sum(-t["valor"] for t in transacoes if t["valor"] < 0)
    total_credito = sum(t["valor"] for t in transacoes if t["valor"] > 0)

    resumo = (
        f"Resumo da fatura:\n"
        f"- Transacoes: {total}\n"
        f"- Total debitos: R$ {total_debito:.2f}\n"
        f"- Total creditos: R$ {total_credito:.2f}\n\n"
        "Deseja salvar esses lancamentos?"
    )

    keyboard = [
        [InlineKeyboardButton("Confirmar", callback_data="fatura_salvar")],
        [InlineKeyboardButton("Cancelar", callback_data="fatura_cancelar")],
    ]
    await query.edit_message_text(resumo, reply_markup=InlineKeyboardMarkup(keyboard))
    return FATURA_CONFIRMATION_STATE


async def fatura_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action = query.data
    if action == "fatura_cancelar":
        context.user_data.pop("fatura_transacoes", None)
        context.user_data.pop("fatura_conta_id", None)
        await query.edit_message_text("Importacao cancelada.")
        return ConversationHandler.END

    transacoes = context.user_data.get("fatura_transacoes", [])
    conta_id = context.user_data.get("fatura_conta_id")
    if not transacoes or not conta_id:
        await query.edit_message_text("Dados da fatura perdidos. Tente novamente.")
        return ConversationHandler.END

    db = next(get_db())
    try:
        usuario_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)
        ok, msg, _stats = await salvar_transacoes_generica(
            db, usuario_db, transacoes, conta_id, tipo_origem="fatura_pdf_inter"
        )
        await query.edit_message_text(msg, parse_mode="HTML")
        return ConversationHandler.END
    finally:
        db.close()
        context.user_data.pop("fatura_transacoes", None)
        context.user_data.pop("fatura_conta_id", None)


async def fatura_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Importacao cancelada.")
    elif update.message:
        await update.message.reply_text("Importacao cancelada.")
    context.user_data.pop("fatura_transacoes", None)
    context.user_data.pop("fatura_conta_id", None)
    return ConversationHandler.END


fatura_conv = ConversationHandler(
    entry_points=[CommandHandler("fatura", fatura_start)],
    states={
        FATURA_AWAIT_FILE: [
            MessageHandler(filters.Document.MimeType("application/pdf"), fatura_receive_file)
        ],
        FATURA_ASK_CONTA: [
            CallbackQueryHandler(fatura_select_conta, pattern="^fatura_conta_")
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
