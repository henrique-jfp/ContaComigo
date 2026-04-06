# === GERAR LINK DE PAGAMENTO MERCADO PAGO ===
def gerar_link_pagamento_mercadopago(user_id: int, plano: str) -> str:
    """
    Gera um link de pagamento Mercado Pago para o usuário e plano informados.
    O link é único por usuário/plano e pode ser usado para upgrade automático.
    """
    import os
    import uuid
    mp_access_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN")
    if not mp_access_token:
        raise RuntimeError("MERCADOPAGO_ACCESS_TOKEN não configurado nas variáveis de ambiente!")
    sdk = mercadopago.SDK(mp_access_token)

    # Definições do produto
    if plano == PLAN_PREMIUM_MONTHLY:
        title = "Premium Mensal Maestro Financeiro"
        price = PLAN_PRICES[PLAN_PREMIUM_MONTHLY]
        plan_id = "premium_mensal"
    elif plano == PLAN_PREMIUM_ANNUAL:
        title = "Premium Anual Maestro Financeiro"
        price = PLAN_PRICES[PLAN_PREMIUM_ANNUAL]
        plan_id = "premium_anual"
    else:
        raise ValueError(f"Plano inválido: {plano}")

    # Preferência de pagamento
    preference_data = {
        "items": [
            {
                "id": plan_id,
                "title": title,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(price),
                "description": f"Upgrade para {title} (Telegram ID: {user_id})"
            }
        ],
        "external_reference": f"telegram_{user_id}_{plano}_{uuid.uuid4().hex[:8]}",
        "notification_url": os.environ.get("MERCADOPAGO_WEBHOOK_URL", ""),
        "payer": {
            "name": str(user_id)
        },
        "back_urls": {
            "success": os.environ.get("MERCADOPAGO_SUCCESS_URL", "https://t.me/ContaComigoBot"),
            "failure": os.environ.get("MERCADOPAGO_FAILURE_URL", "https://t.me/ContaComigoBot"),
            "pending": os.environ.get("MERCADOPAGO_PENDING_URL", "https://t.me/ContaComigoBot")
        },
        "auto_return": "approved"
    }

    preference_response = sdk.preference().create(preference_data)
    if not preference_response["status"] == 201:
        raise RuntimeError(f"Erro ao criar link Mercado Pago: {preference_response}")
    return preference_response["response"]["init_point"]
def _to_utc_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, Optional

from sqlalchemy import and_, extract, func
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from database.database import get_db, get_or_create_user
from models import Lancamento, Objetivo, Usuario, UserPlanUsageMonthly
from apscheduler.schedulers.background import BackgroundScheduler
import mercadopago

logger = logging.getLogger(__name__)

PLAN_TRIAL = "trial"
PLAN_FREE = "free"
PLAN_PREMIUM_MONTHLY = "premium_monthly"
PLAN_PREMIUM_ANNUAL = "premium_annual"

ALL_PLANS = {PLAN_TRIAL, PLAN_FREE, PLAN_PREMIUM_MONTHLY, PLAN_PREMIUM_ANNUAL}

PLAN_PRICES = {
    PLAN_PREMIUM_MONTHLY: 12.90,
    PLAN_PREMIUM_ANNUAL: 129.00,
}

BLOCKED_ON_FREE = {
    "voice_input",
    "pdf_import",
    "relatorio_pdf",
    "dashboard_full",
}

FREE_LIMITS = {
    "lancamentos": 30,
    "ocr": 3,
    "ia_questions": 3,
    "metas_ativas": 1,
}

# === WHITELIST DE USUÁRIOS PREMIUM ===
import os
_WHITELIST_PATH = os.path.join(os.path.dirname(__file__), '..', 'whitelist.txt')
def load_whitelist():
    try:
        with open(_WHITELIST_PATH) as f:
            return set(int(line.strip()) for line in f if line.strip() and not line.startswith('#'))
    except Exception:
        return set()

WHITELIST = load_whitelist()

def reload_whitelist():
    global WHITELIST
    WHITELIST = load_whitelist()
    return WHITELIST

def is_whitelisted(user_id):
    try:
        return int(user_id) in WHITELIST
    except Exception:
        return False

@dataclass
class PlanGateResult:
    allowed: bool
    message: Optional[str] = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _month_window(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    ref = now or _now_utc()
    start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _plan_label(plan: str) -> str:
    labels = {
        PLAN_TRIAL: "Trial Premium",
        PLAN_FREE: "Free Tier",
        PLAN_PREMIUM_MONTHLY: "Premium Mensal",
        PLAN_PREMIUM_ANNUAL: "Premium Anual",
    }
    return labels.get(plan, "Plano desconhecido")


def ensure_user_plan_state(db: Session, user: Usuario, *, commit: bool = True) -> Usuario:
    changed = False
    now = _now_utc()

    if not user.plan or user.plan not in ALL_PLANS:
        user.plan = PLAN_TRIAL
        changed = True

    if user.plan == PLAN_TRIAL and not user.trial_expires_at:
        user.trial_expires_at = now + timedelta(days=15)
        changed = True


    # Corrigir: usar user.premium_expires_at
    premium_exp = getattr(user, 'premium_expires_at', None)
    if user.plan == PLAN_PREMIUM_MONTHLY and premium_exp and _to_utc_aware(premium_exp) <= now:
        user.plan = PLAN_FREE
        changed = True

    if user.plan == PLAN_PREMIUM_ANNUAL and premium_exp and _to_utc_aware(premium_exp) <= now:
        user.plan = PLAN_FREE
        changed = True

    if user.plan == PLAN_TRIAL and _to_utc_aware(user.trial_expires_at) <= now:
        user.plan = PLAN_FREE
        changed = True

    if changed and commit:
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

    def _to_utc_aware(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


def get_effective_plan(db: Session, user: Usuario) -> str:
    user = ensure_user_plan_state(db, user, commit=True)
    return user.plan or PLAN_FREE


def get_or_create_monthly_usage(db: Session, user_id: int, *, year: int, month: int) -> UserPlanUsageMonthly:
    usage = (
        db.query(UserPlanUsageMonthly)
        .filter(
            UserPlanUsageMonthly.id_usuario == user_id,
            UserPlanUsageMonthly.ano == year,
            UserPlanUsageMonthly.mes == month,
        )
        .first()
    )
    if usage:
        return usage

    usage = UserPlanUsageMonthly(
        id_usuario=user_id,
        ano=year,
        mes=month,
        lancamentos_count=0,
        ocr_count=0,
        ia_questions_count=0,
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def _upgrade_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"💎 Premium Mensal — R$ {PLAN_PRICES[PLAN_PREMIUM_MONTHLY]:.2f}", callback_data="plan_choose_premium_monthly")],
            [InlineKeyboardButton(f"📅 Premium Anual — R$ {PLAN_PRICES[PLAN_PREMIUM_ANNUAL]:.2f}", callback_data="plan_choose_premium_annual")],
            [InlineKeyboardButton("Continuar no Free Tier", callback_data="plan_choose_free")],
        ]
    )


def upgrade_prompt_for_feature(feature: str) -> tuple[str, InlineKeyboardMarkup]:
    feature_map = {
        "voice_input": "entrada por voz",
        "pdf_import": "importação de fatura PDF",
        "relatorio_pdf": "relatório PDF exportável",
        "dashboard_full": "dashboard completo",
        "ocr": "OCR de nota fiscal",
        "ia_questions": "análise IA do Alfredo",
        "lancamentos": "mais lançamentos no mês",
        "metas_ativas": "mais metas ativas",
    }
    feature_label = feature_map.get(feature, "esta funcionalidade")
    text = (
        f"🔒 <b>{feature_label.title()} é recurso premium.</b>\n\n"
        "Você está no Free Tier.\n"
        "Escolha como quer continuar:"
    )
    return text, _upgrade_keyboard()


def _count_user_lancamentos_current_month(db: Session, user_id: int) -> int:
    start, end = _month_window()
    total = (
        db.query(func.count(Lancamento.id))
        .filter(
            Lancamento.id_usuario == user_id,
            Lancamento.data_transacao >= start,
            Lancamento.data_transacao < end,
        )
        .scalar()
        or 0
    )
    return int(total)


def _count_active_goals(db: Session, user_id: int) -> int:
    total = (
        db.query(func.count(Objetivo.id))
        .filter(
            Objetivo.id_usuario == user_id,
            func.coalesce(Objetivo.valor_atual, 0) < func.coalesce(Objetivo.valor_meta, 0),
        )
        .scalar()
        or 0
    )
    return int(total)


def plan_allows_feature(db: Session, user: Usuario, feature: str) -> PlanGateResult:
    plan = get_effective_plan(db, user)
    if plan in {PLAN_TRIAL, PLAN_PREMIUM_MONTHLY, PLAN_PREMIUM_ANNUAL}:
        return PlanGateResult(True)

    if feature in BLOCKED_ON_FREE:
        text, _ = upgrade_prompt_for_feature(feature)
        return PlanGateResult(False, text)

    now = _now_utc()
    usage = get_or_create_monthly_usage(db, user.id, year=now.year, month=now.month)

    if feature == "ocr" and usage.ocr_count >= FREE_LIMITS["ocr"]:
        text, _ = upgrade_prompt_for_feature("ocr")
        return PlanGateResult(False, text)

    if feature == "ia_questions" and usage.ia_questions_count >= FREE_LIMITS["ia_questions"]:
        text, _ = upgrade_prompt_for_feature("ia_questions")
        return PlanGateResult(False, text)

    if feature == "lancamentos" and _count_user_lancamentos_current_month(db, user.id) >= FREE_LIMITS["lancamentos"]:
        text, _ = upgrade_prompt_for_feature("lancamentos")
        return PlanGateResult(False, text)

    if feature == "metas_ativas" and _count_active_goals(db, user.id) >= FREE_LIMITS["metas_ativas"]:
        text, _ = upgrade_prompt_for_feature("metas_ativas")
        return PlanGateResult(False, text)

    return PlanGateResult(True)


def consume_feature_quota(db: Session, user: Usuario, feature: str, amount: int = 1) -> None:
    if amount <= 0:
        return

    plan = get_effective_plan(db, user)
    if plan in {PLAN_TRIAL, PLAN_PREMIUM_MONTHLY, PLAN_PREMIUM_ANNUAL}:
        return

    now = _now_utc()
    usage = get_or_create_monthly_usage(db, user.id, year=now.year, month=now.month)

    if feature == "ocr":
        usage.ocr_count = int(usage.ocr_count or 0) + amount
    elif feature == "ia_questions":
        usage.ia_questions_count = int(usage.ia_questions_count or 0) + amount
    elif feature == "lancamentos":
        usage.lancamentos_count = int(usage.lancamentos_count or 0) + amount

    db.add(usage)
    db.commit()


def require_plan(feature: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_tg = update.effective_user
            if not user_tg:
                return await func(update, context, *args, **kwargs)

            # Se está na whitelist, libera tudo
            if is_whitelisted(user_tg.id):
                return await func(update, context, *args, **kwargs)

            db = next(get_db())
            try:
                user_db = get_or_create_user(db, user_tg.id, user_tg.full_name)
                ensure_user_plan_state(db, user_db, commit=True)
                gate = plan_allows_feature(db, user_db, feature)
                if gate.allowed:
                    return await func(update, context, *args, **kwargs)

                text, keyboard = upgrade_prompt_for_feature(feature)
                if update.message:
                    await update.message.reply_html(text, reply_markup=keyboard)
                elif update.callback_query:
                    await update.callback_query.answer()
                    await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
                return None
            finally:
                db.close()

        return wrapper

    return decorator


def trial_users_expiring_in(db: Session, days: int) -> list[Usuario]:
    now = _now_utc()
    target_start = now + timedelta(days=days)
    target_end = target_start + timedelta(days=1)
    return (
        db.query(Usuario)
        .filter(
            Usuario.plan == PLAN_TRIAL,
            Usuario.trial_expires_at >= target_start,
            Usuario.trial_expires_at < target_end,
        )
        .all()
    )


def trial_users_expired(db: Session) -> list[Usuario]:
    now = _now_utc()
    return (
        db.query(Usuario)
        .filter(
            Usuario.plan == PLAN_TRIAL,
            Usuario.trial_expires_at.isnot(None),
            Usuario.trial_expires_at <= now,
        )
        .all()
    )


def build_trial_usage_summary(db: Session, user: Usuario) -> dict:
    trial_start = user.criado_em or (_now_utc() - timedelta(days=15))
    lancamentos = (
        db.query(func.count(Lancamento.id))
        .filter(
            Lancamento.id_usuario == user.id,
            Lancamento.data_transacao >= trial_start,
        )
        .scalar()
        or 0
    )
    metas = (
        db.query(func.count(Objetivo.id))
        .filter(
            Objetivo.id_usuario == user.id,
            Objetivo.criado_em >= trial_start,
        )
        .scalar()
        or 0
    )

    ia_total = (
        db.query(func.sum(UserPlanUsageMonthly.ia_questions_count))
        .filter(UserPlanUsageMonthly.id_usuario == user.id)
        .scalar()
        or 0
    )

    return {
        "lancamentos": int(lancamentos),
        "metas": int(metas),
        "ia_questions": int(ia_total),
    }


def downgrade_expired_trials_to_free(db: Session) -> list[Usuario]:
    expired = trial_users_expired(db)
    changed: list[Usuario] = []
    for user in expired:
        user.plan = PLAN_FREE
        db.add(user)
        changed.append(user)
    if changed:
        db.commit()
    return changed


async def handle_plan_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action = query.data
    db = next(get_db())
    try:
        user_db = get_or_create_user(db, query.from_user.id, query.from_user.full_name)
        ensure_user_plan_state(db, user_db, commit=True)

        if action == "plan_choose_free":
            user_db.plan = PLAN_FREE
            db.add(user_db)
            db.commit()
            await query.edit_message_text(
                "👍 Você ficou no Free Tier. Seus dados continuam intactos.",
                parse_mode="HTML",
            )
            return

        if action in {"plan_choose_premium_monthly", "plan_choose_premium_annual"}:
            plano = PLAN_PREMIUM_MONTHLY if action.endswith("monthly") else PLAN_PREMIUM_ANNUAL
            link = gerar_link_pagamento_mercadopago(query.from_user.id, plano)
            valor = PLAN_PRICES[plano]
            await query.edit_message_text(
                f"💎 <b>{'Premium Mensal' if plano == PLAN_PREMIUM_MONTHLY else 'Premium Anual'}</b> selecionado.\n"
                f"Valor: <b>R$ {valor:.2f}</b>\n\n"
                f"Clique no botão abaixo para pagar com Mercado Pago e ativar seu premium instantaneamente!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Pagar com Mercado Pago", url=link)],
                    [InlineKeyboardButton("Continuar no Free Tier", callback_data="plan_choose_free")],
                ])
            )
            return

        await query.edit_message_text("Ação de plano inválida.")
    finally:
        db.close()

def reload_whitelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reload_whitelist()
    update.message.reply_text("✅ Whitelist recarregada com sucesso!")

scheduler = BackgroundScheduler()

@scheduler.scheduled_job('interval', hours=3)
def scheduled_reload_whitelist():
    reload_whitelist()
    logger.info("✅ Whitelist recarregada automaticamente pelo scheduler.")

# No final do arquivo, garantir que o scheduler está rodando:
scheduler.start()
