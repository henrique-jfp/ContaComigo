"""Serviço canônico de gamificação alinhado ao contacomigo_xp_sistema.md."""
import logging
from datetime import datetime, date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session
from gerente_financeiro.monetization import PLAN_PREMIUM_MONTHLY

# === PREMIAÇÃO MENSAL DE PREMIUM PARA TOP 2 XP ===
def get_monthly_xp_ranking(db: Session, year: int, month: int, limit: int = 2):
    """Retorna os top usuários com mais XP ganho no mês especificado."""
    from models import Usuario, XpEvent
    month_start = datetime(year, month, 1)
    if month == 12:
        month_end = datetime(year + 1, 1, 1) - timedelta(seconds=1)
    else:
        month_end = datetime(year, month + 1, 1) - timedelta(seconds=1)
    results = (
        db.query(Usuario, func.coalesce(func.sum(XpEvent.xp_gained), 0).label('xp_mes'))
        .join(XpEvent, XpEvent.id_usuario == Usuario.id)
        .filter(XpEvent.created_at >= month_start, XpEvent.created_at <= month_end)
        .group_by(Usuario.id)
        .order_by(func.sum(XpEvent.xp_gained).desc())
        .limit(limit)
        .all()
    )
    return results

def award_monthly_xp_competition_premium(db: Session, reference_date: date | None = None) -> int:
    """Premia os 2 primeiros do ranking mensal de XP com 1 mês de premium grátis."""
    reference_date = reference_date or date.today()
    if reference_date.day != 1:
        return 0
    year = reference_date.year
    month = reference_date.month - 1 if reference_date.month > 1 else 12
    year = year if reference_date.month > 1 else year - 1
    top_users = get_monthly_xp_ranking(db, year, month, limit=2)
    premiados = 0
    from telegram import Bot
    import os
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    bot = Bot(token=telegram_token) if telegram_token else None
    for usuario, xp_mes in top_users:
        # Só premia se não for premium vitalício
        if usuario.plan != PLAN_PREMIUM_MONTHLY or not usuario.premium_expires_at or usuario.premium_expires_at < reference_date:
            # Concede 1 mês de premium
            if not usuario.premium_expires_at or usuario.premium_expires_at < reference_date:
                usuario.premium_expires_at = datetime.combine(reference_date, datetime.min.time()) + timedelta(days=30)
            else:
                usuario.premium_expires_at += timedelta(days=30)
            usuario.plan = PLAN_PREMIUM_MONTHLY
            db.add(usuario)
            premiados += 1
            # Notificação via Telegram
            if bot:
                try:
                    bot.send_message(
                        chat_id=usuario.telegram_id,
                        text=(
                            f"🏆 Parabéns! Você ficou entre os 2 primeiros do ranking mensal de XP do Maestro Financeiro e ganhou 1 mês de Premium grátis!\n\n"
                            f"Continue usando o bot para manter sua liderança!"
                        )
                    )
                except Exception as e:
                    print(f"Falha ao notificar usuário {usuario.telegram_id}: {e}")
    db.commit()
    return premiados
from models import (
    Lancamento,
    MetaConfirmacao,
    Mission,
    MonthlyGamificationAward,
    Objetivo,
    PatrimonySnapshot,
    UserAchievement,
    UserMission,
    Usuario,
    XpDailyCounter,
    XpEvent,
    XpLevelDefinition,
)

logger = logging.getLogger(__name__)

# ============================================================================
# CANONICAL SPEC LAYER
# ============================================================================

SPEC_XP_ACTIONS = {
    'LANCAMENTO_CRIADO_TEXTO': 10,
    'LANCAMENTO_CRIADO_VOZ': 18,
    'LANCAMENTO_CRIADO_OCR': 25,
    'LANCAMENTO_CRIADO_PDF': 40,
    'LANCAMENTO_EDITADO': 5,
    'CONFIRMACAO_IA': 8,
    'META_CRIADA': 30,
    'META_CHECKIN': 20,
    'META_ATINGIDA': 100,
    'META_ATINGIDA_ANTES_PRAZO': 50,
    'AGENDAMENTO_CRIADO': 20,
    'INVESTIMENTO_ADICIONADO': 25,
    'PORTFOLIO_ATUALIZADO': 15,
    'PRIMEIRA_INTERACAO_DIA': 5,
    'PERGUNTA_ALFREDO': 8,
    'RELATORIO_GERADO': 35,
    'DASHBOARD_VISUALIZADO': 3,
    'MONTH_TURN_BLUE': 150,
    'WRAPPED_ANUAL': 200,
    'STREAK_DIAS_7': 50,
    'STREAK_DIAS_14': 80,
    'STREAK_DIAS_30': 200,
    'STREAK_DIAS_100': 500,
    'CONVITE_ACEITO': 80,
    'CATEGORIA_REDUCAO': 40,
    'PATRIMONIO_CRESCIMENTO': 80,
    'ECONOMIA_META_ATINGIDA': 60,
    'EVENTO_SAZONAL': 0,
    'CONQUISTA_DESBLOQUEADA': 50,
}

REPETITIVE_ACTIONS = {
    'LANCAMENTO_CRIADO_TEXTO',
    'LANCAMENTO_CRIADO_VOZ',
    'LANCAMENTO_CRIADO_OCR',
    'LANCAMENTO_CRIADO_PDF',
    'LANCAMENTO_EDITADO',
    'CONFIRMACAO_IA',
    'PERGUNTA_ALFREDO',
    'DASHBOARD_VISUALIZADO',
}

LEVEL_REQUIREMENTS = {
    1: (0, 'Caderneta Zerada', 'bronze'),
    2: (200, 'Anotador de Plantão', 'bronze'),
    3: (500, 'Controlador de Gastos', 'bronze'),
    4: (1000, 'Orçamentário Jr.', 'bronze'),
    5: (2000, 'Caçador de Sobras', 'silver'),
    6: (3500, 'Arquivista do Real', 'silver'),
    7: (5500, 'Analista de Bolso', 'silver'),
    8: (8000, 'Planejador Ativo', 'silver'),
    9: (12000, 'Mestre do Fluxo', 'gold'),
    10: (18000, 'Guardião do Patrimônio', 'gold'),
    11: (25000, 'CFO Pessoal', 'gold'),
    12: (35000, 'Arquiteto Financeiro', 'gold'),
    13: (50000, 'Visionário de Mercado', 'diamond'),
    14: (70000, 'Oráculo do Budget', 'diamond'),
    15: (95000, 'Alfredo Humano', 'legend'),
    16: (130000, 'Além do Budget', 'infinite'),
}

MISSION_TARGETS = {
    'caffeine_tracker': 3,
    'olho_vivo': 1,
    'clique_rapido': 1,
    'pergunta_dia': 1,
    'semana_limpa': 5,
    'detetive_nota': 2,
    'estrategista_metas': 1,
    'fatura_detonada': 1,
    'semana_azul': 1,
    'primeiro_passo': 1,
    'semana_sem_enrolacao': 7,
    'mes_chave_ouro': 1,
    'curador_portfolio': 3,
}

MISSION_TYPES = {
    'caffeine_tracker': 'daily',
    'olho_vivo': 'daily',
    'clique_rapido': 'daily',
    'pergunta_dia': 'daily',
    'semana_limpa': 'weekly',
    'detetive_nota': 'weekly',
    'estrategista_metas': 'weekly',
    'fatura_detonada': 'weekly',
    'semana_azul': 'weekly',
    'primeiro_passo': 'special',
    'semana_sem_enrolacao': 'special',
    'mes_chave_ouro': 'special',
    'curador_portfolio': 'special',
}

CANONICAL_MISSIONS = {
    'caffeine_tracker': {
        'name': 'Caffeine Tracker',
        'description': 'Registre 3 gastos hoje via texto, voz ou foto.',
        'mission_type': 'daily',
        'xp_reward': 30,
        'sort_order': 10,
    },
    'olho_vivo': {
        'name': 'Olho Vivo',
        'description': 'Verifique o dashboard e leia o card do Alfredo.',
        'mission_type': 'daily',
        'xp_reward': 15,
        'sort_order': 20,
    },
    'clique_rapido': {
        'name': 'Clique Rápido',
        'description': 'Registre um gasto via áudio (voz para texto).',
        'mission_type': 'daily',
        'xp_reward': 20,
        'sort_order': 30,
    },
    'pergunta_dia': {
        'name': 'Pergunta do Dia',
        'description': 'Faça uma pergunta ao Alfredo sobre seus gastos ou padrões.',
        'mission_type': 'daily',
        'xp_reward': 18,
        'sort_order': 40,
    },
    'semana_limpa': {
        'name': 'Semana Limpa',
        'description': 'Registre pelo menos 1 gasto em 5 dias diferentes durante a semana.',
        'mission_type': 'weekly',
        'xp_reward': 80,
        'sort_order': 50,
    },
    'detetive_nota': {
        'name': 'Detetive da Nota',
        'description': 'Use OCR de foto em pelo menos 2 notas fiscais na semana.',
        'mission_type': 'weekly',
        'xp_reward': 60,
        'sort_order': 60,
    },
    'estrategista_metas': {
        'name': 'Estrategista de Metas',
        'description': 'Faça check-in em pelo menos 1 meta financeira ativa.',
        'mission_type': 'weekly',
        'xp_reward': 50,
        'sort_order': 70,
    },
    'fatura_detonada': {
        'name': 'Fatura Detonada',
        'description': 'Importe e categorize um extrato ou PDF de fatura.',
        'mission_type': 'weekly',
        'xp_reward': 90,
        'sort_order': 80,
    },
    'semana_azul': {
        'name': 'Semana Azul',
        'description': 'Gaste menos do que entrou na semana.',
        'mission_type': 'weekly',
        'xp_reward': 100,
        'sort_order': 90,
    },
    'primeiro_passo': {
        'name': 'Primeiro Passo',
        'description': 'Registre seu primeiro gasto no ContaComigo.',
        'mission_type': 'special',
        'xp_reward': 50,
        'sort_order': 100,
    },
    'semana_sem_enrolacao': {
        'name': 'Semana Sem Enrolação',
        'description': 'Complete 7 dias de streak sem quebrar.',
        'mission_type': 'special',
        'xp_reward': 50,
        'sort_order': 110,
    },
    'mes_chave_ouro': {
        'name': 'Mês Fechado com Chave de Ouro',
        'description': 'Feche o mês com saldo positivo e 20+ lançamentos.',
        'mission_type': 'special',
        'xp_reward': 250,
        'sort_order': 120,
    },
    'curador_portfolio': {
        'name': 'Curador do Portfólio',
        'description': 'Adicione pelo menos 3 investimentos.',
        'mission_type': 'special',
        'xp_reward': 120,
        'sort_order': 130,
    },
}

DAILY_REPETITIVE_XP_CAP = 200


def normalize_action(action: str) -> str:
    return action


def get_level_info(level: int) -> dict:
    if level < 1:
        level = 1
    if level > 16:
        return {
            'level': level,
            'name': f'Além do Budget +{level - 16}',
            'required_xp': 130000 + (level - 16) * 35000,
            'tier': 'infinite',
        }
    xp_req, name, tier = LEVEL_REQUIREMENTS[level]
    return {'level': level, 'name': name, 'required_xp': xp_req, 'tier': tier}


def get_level_multiplier(current_level: int) -> float:
    if current_level >= 16:
        return 0.20
    if current_level >= 13:
        return 0.15
    if current_level >= 9:
        return 0.10
    if current_level >= 5:
        return 0.05
    return 0.0


def get_streak_multiplier(streak_dias: int) -> float:
    if streak_dias >= 100:
        return 1.60
    if streak_dias >= 30:
        return 1.40
    if streak_dias >= 14:
        return 1.25
    if streak_dias >= 7:
        return 1.15
    return 1.0


def _get_achievement_bonus(db: Session, usuario_id: int) -> float:
    try:
        total = db.query(func.coalesce(func.sum(UserAchievement.permanent_multiplier), 0.0)).filter(
            UserAchievement.id_usuario == usuario_id
        ).scalar()
        return float(total or 0.0)
    except Exception:
        return 0.0


def get_total_multiplier(usuario: Usuario, db: Session | None = None) -> float:
    streak_mult = get_streak_multiplier(int(usuario.streak_dias or 0))
    level_bonus = get_level_multiplier(int(usuario.level or 1))
    achievement_bonus = _get_achievement_bonus(db, usuario.id) if db is not None else 0.0
    return streak_mult + level_bonus + achievement_bonus


def _current_week_key(today: date) -> tuple[int, int]:
    return today.isocalendar().year, today.isocalendar().week


def _canonical_mission_rows(db: Session) -> list:
    # Bootstrap idempotente para garantir que o MiniApp sempre tenha missões.
    existing_rows = db.query(Mission).all()
    existing_by_key = {row.mission_key: row for row in existing_rows}
    changed = False

    for key, spec in CANONICAL_MISSIONS.items():
        row = existing_by_key.get(key)
        if not row:
            db.add(Mission(
                mission_key=key,
                name=spec['name'],
                description=spec['description'],
                mission_type=spec['mission_type'],
                xp_reward=int(spec['xp_reward']),
                bonus_multiplier=1,
                unlock_level=0,
                sort_order=int(spec['sort_order']),
                active=True,
            ))
            changed = True
            continue

        row.name = spec['name']
        row.description = spec['description']
        row.mission_type = spec['mission_type']
        row.xp_reward = int(spec['xp_reward'])
        row.sort_order = int(spec['sort_order'])
        row.active = True
        changed = True

    if changed:
        db.flush()

    rows = db.query(Mission).filter(Mission.active == True).order_by(Mission.sort_order.asc(), Mission.id.asc()).all()  # noqa: E712
    return rows


def _ensure_user_missions(db: Session, usuario: Usuario) -> list[UserMission]:
    missions = _canonical_mission_rows(db)
    existing = {um.id_mission: um for um in db.query(UserMission).filter(UserMission.id_usuario == usuario.id).all()}
    created = []
    for mission in missions:
        um = existing.get(mission.id)
        if not um:
            um = UserMission(
                id_usuario=usuario.id,
                id_mission=mission.id,
                progress=0,
                current_value=0,
                target_value=int(MISSION_TARGETS.get(mission.mission_key, 1)),
                status='active',
            )
            db.add(um)
            created.append(um)
        else:
            if not um.target_value:
                um.target_value = int(MISSION_TARGETS.get(mission.mission_key, 1))
        # Keep relation available
        um.mission = mission
    if created:
        db.flush()
    return list(existing.values()) + created


def _week_bounds(current_date: date) -> tuple[datetime, datetime]:
    start = current_date - timedelta(days=current_date.weekday())
    end = start + timedelta(days=6)
    return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())


def _day_bounds(current_date: date) -> tuple[datetime, datetime]:
    return datetime.combine(current_date, datetime.min.time()), datetime.combine(current_date, datetime.max.time())


async def _unlock_achievements(db: Session, usuario: Usuario, current_date: date) -> list[dict]:
    from models import Lancamento, Investment

    unlocked = []

    def already(key: str) -> bool:
        return db.query(UserAchievement.id).filter(UserAchievement.id_usuario == usuario.id, UserAchievement.achievement_key == key).first() is not None

    def grant(key: str, name: str, desc: str, xp_reward: int = 0, permanent_multiplier: float = 0.0, badges=None):
        if already(key):
            return
        db.add(UserAchievement(
            id_usuario=usuario.id,
            achievement_key=key,
            achievement_name=name,
            achievement_description=desc,
            xp_reward=xp_reward,
            permanent_multiplier=permanent_multiplier,
            badges=badges or [],
            unlocked_at=datetime.utcnow(),
        ))
        usuario.xp = int(usuario.xp or 0) + int(xp_reward or 0)
        unlocked.append({'achievement_key': key, 'xp_reward': xp_reward, 'permanent_multiplier': permanent_multiplier})

    total_lancamentos = db.query(func.count(Lancamento.id)).filter(Lancamento.id_usuario == usuario.id).scalar() or 0
    total_perguntas = db.query(func.count(XpEvent.id)).filter(XpEvent.id_usuario == usuario.id, XpEvent.action == 'PERGUNTA_ALFREDO').scalar() or 0
    total_investments = db.query(func.count(Investment.id)).filter(Investment.id_usuario == usuario.id).scalar() or 0

    if total_lancamentos >= 1:
        grant('primeiro_passo', 'Primeiro Passo', 'Primeiro gasto registrado.', 50)
    if int(usuario.streak_dias or 0) >= 7:
        grant('semana_sem_enrolacao', 'Semana Sem Enrolação', '7 dias de streak sem quebrar.', 50, 0.05)
    if total_investments >= 3:
        grant('curador_portfolio', 'Curador do Portfólio', '3 investimentos cadastrados.', 120)
    if total_perguntas >= 50:
        grant('alfredo_fa_clube', 'Alfredo Fã Clube', '50 perguntas ao Alfredo.', 60)

    # Mês fechado com chave de ouro / trimestre limpo dependem de verificação mensal.
    if unlocked:
        db.flush()
    return unlocked


async def _update_mission_progress(db: Session, usuario: Usuario, action: str, current_date: date) -> list:
    action = normalize_action(action)
    _ensure_user_missions(db, usuario)
    missions = db.query(UserMission).filter(UserMission.id_usuario == usuario.id).all()
    progress_list = []

    from models import Lancamento, Investment

    day_start, day_end = _day_bounds(current_date)
    week_start, week_end = _week_bounds(current_date)

    launch_actions = ['LANCAMENTO_CRIADO_TEXTO', 'LANCAMENTO_CRIADO_VOZ', 'LANCAMENTO_CRIADO_OCR', 'LANCAMENTO_CRIADO_PDF']

    launches_today = db.query(func.count(XpEvent.id)).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action.in_(launch_actions),
        XpEvent.created_at >= day_start,
        XpEvent.created_at <= day_end,
    ).scalar() or 0

    voice_today = db.query(func.count(XpEvent.id)).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action == 'LANCAMENTO_CRIADO_VOZ',
        XpEvent.created_at >= day_start,
        XpEvent.created_at <= day_end,
    ).scalar() or 0

    questions_today = db.query(func.count(XpEvent.id)).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action == 'PERGUNTA_ALFREDO',
        XpEvent.created_at >= day_start,
        XpEvent.created_at <= day_end,
    ).scalar() or 0

    dashboard_today = db.query(func.count(XpEvent.id)).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action == 'DASHBOARD_VISUALIZADO',
        XpEvent.created_at >= day_start,
        XpEvent.created_at <= day_end,
    ).scalar() or 0

    weekly_unique_days = db.query(func.count(func.distinct(func.date(XpEvent.created_at)))).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action.in_(launch_actions),
        XpEvent.created_at >= week_start,
        XpEvent.created_at <= week_end,
    ).scalar() or 0

    weekly_ocr = db.query(func.count(XpEvent.id)).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action == 'LANCAMENTO_CRIADO_OCR',
        XpEvent.created_at >= week_start,
        XpEvent.created_at <= week_end,
    ).scalar() or 0

    weekly_checkins = db.query(func.count(XpEvent.id)).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action == 'META_CHECKIN',
        XpEvent.created_at >= week_start,
        XpEvent.created_at <= week_end,
    ).scalar() or 0

    weekly_pdf = db.query(func.count(XpEvent.id)).filter(
        XpEvent.id_usuario == usuario.id,
        XpEvent.action == 'LANCAMENTO_CRIADO_PDF',
        XpEvent.created_at >= week_start,
        XpEvent.created_at <= week_end,
    ).scalar() or 0

    weekly_entries = db.query(func.coalesce(func.sum(Lancamento.valor), 0)).filter(
        Lancamento.id_usuario == usuario.id,
        Lancamento.data_transacao >= week_start,
        Lancamento.data_transacao <= week_end,
        func.lower(Lancamento.tipo).like('entr%'),
    ).scalar() or 0

    weekly_outputs = db.query(func.coalesce(func.sum(Lancamento.valor), 0)).filter(
        Lancamento.id_usuario == usuario.id,
        Lancamento.data_transacao >= week_start,
        Lancamento.data_transacao <= week_end,
        ~func.lower(Lancamento.tipo).like('entr%'),
    ).scalar() or 0

    month_start = datetime(current_date.year, current_date.month, 1)
    month_end = datetime(current_date.year + (1 if current_date.month == 12 else 0), 1 if current_date.month == 12 else current_date.month + 1, 1) - timedelta(seconds=1)
    month_entries = db.query(func.coalesce(func.sum(Lancamento.valor), 0)).filter(
        Lancamento.id_usuario == usuario.id,
        Lancamento.data_transacao >= month_start,
        Lancamento.data_transacao <= month_end,
        func.lower(Lancamento.tipo).like('entr%'),
    ).scalar() or 0
    month_outputs = db.query(func.coalesce(func.sum(Lancamento.valor), 0)).filter(
        Lancamento.id_usuario == usuario.id,
        Lancamento.data_transacao >= month_start,
        Lancamento.data_transacao <= month_end,
        ~func.lower(Lancamento.tipo).like('entr%'),
    ).scalar() or 0
    month_launch_count = db.query(func.count(Lancamento.id)).filter(
        Lancamento.id_usuario == usuario.id,
        Lancamento.data_transacao >= month_start,
        Lancamento.data_transacao <= month_end,
    ).scalar() or 0

    total_lancamentos = db.query(func.count(Lancamento.id)).filter(Lancamento.id_usuario == usuario.id).scalar() or 0
    total_investments = db.query(func.count(Investment.id)).filter(Investment.id_usuario == usuario.id).scalar() or 0

    def set_progress(um: UserMission, current_value: int, target: int | None = None):
        if target is not None:
            um.target_value = int(target)
        um.current_value = max(0, int(current_value or 0))
        target = int(um.target_value or 1)
        um.progress = min(100, int((int(um.current_value or 0) / max(target, 1)) * 100))
        if um.current_value >= target and um.status != 'claimed':
            um.status = 'completed'
            if not um.completed_at:
                um.completed_at = datetime.utcnow()
        um.updated_at = datetime.utcnow()
        progress_list.append({
            'mission_key': um.mission.mission_key,
            'progress': um.progress,
            'current_value': int(um.current_value or 0),
            'target_value': target,
            'status': um.status,
        })

    for um in missions:
        key = um.mission.mission_key
        if key == 'caffeine_tracker':
            set_progress(um, launches_today, target=3)
        elif key == 'olho_vivo':
            set_progress(um, 1 if dashboard_today > 0 else 0, target=1)
        elif key == 'clique_rapido':
            set_progress(um, 1 if voice_today > 0 else 0, target=1)
        elif key == 'pergunta_dia':
            set_progress(um, 1 if questions_today > 0 else 0, target=1)
        elif key == 'semana_limpa':
            set_progress(um, weekly_unique_days, target=5)
        elif key == 'detetive_nota':
            set_progress(um, weekly_ocr, target=2)
        elif key == 'estrategista_metas':
            set_progress(um, weekly_checkins, target=1)
        elif key == 'fatura_detonada':
            set_progress(um, weekly_pdf, target=1)
        elif key == 'semana_azul':
            weekly_balance_ok = 1 if float(weekly_entries or 0) > float(abs(weekly_outputs or 0)) else 0
            set_progress(um, weekly_balance_ok, target=1)
        elif key == 'primeiro_passo':
            set_progress(um, 1 if total_lancamentos >= 1 else 0, target=1)
        elif key == 'semana_sem_enrolacao':
            set_progress(um, min(int(usuario.streak_dias or 0), 7), target=7)
        elif key == 'mes_chave_ouro':
            month_ok = 1 if (float(month_entries or 0) > float(abs(month_outputs or 0)) and int(month_launch_count or 0) >= 20) else 0
            set_progress(um, month_ok, target=1)
        elif key == 'curador_portfolio':
            set_progress(um, min(int(total_investments or 0), 3), target=3)

    return progress_list


def _calculate_level_from_xp(total_xp: int) -> int:
    level = 1
    for lvl, (threshold, _, _) in LEVEL_REQUIREMENTS.items():
        if total_xp >= threshold:
            level = lvl
    while total_xp >= 130000 + (level - 16) * 35000 and level >= 16:
        level += 1
    return level


def calculate_xp_for_action(db: Session, usuario: Usuario, action: str, custom_amount: int = None, current_date: date = None) -> dict:
    current_date = current_date or date.today()
    canonical_action = normalize_action(action)
    xp_base = int(custom_amount if custom_amount is not None else SPEC_XP_ACTIONS.get(canonical_action, 0))
    if xp_base <= 0:
        return {'xp_base': 0, 'xp_ganho': 0, 'motivo': 'acao_desconhecida', 'multiplier': 1.0}

    total_multiplier = get_total_multiplier(usuario, db)
    xp_ganho = int(xp_base * total_multiplier)
    motivo = 'normal'
    seasonal_multiplier = 1.0

    # Evento sazonal: Detox Financeiro (1a semana de janeiro) => 2x em lancamentos.
    if current_date.month == 1 and current_date.day <= 7 and canonical_action in {
        'LANCAMENTO_CRIADO_TEXTO', 'LANCAMENTO_CRIADO_VOZ', 'LANCAMENTO_CRIADO_OCR', 'LANCAMENTO_CRIADO_PDF'
    }:
        seasonal_multiplier = 2.0
        xp_ganho = int(xp_ganho * seasonal_multiplier)
        motivo = 'evento_sazonal_detox'

    if canonical_action in REPETITIVE_ACTIONS:
        today_total = db.query(func.coalesce(func.sum(XpDailyCounter.xp_gained), 0)).filter(
            XpDailyCounter.id_usuario == usuario.id,
            XpDailyCounter.day_ref == current_date,
            XpDailyCounter.action.in_(list(REPETITIVE_ACTIONS)),
        ).scalar() or 0
        remaining = max(0, DAILY_REPETITIVE_XP_CAP - int(today_total or 0))
        xp_ganho = min(xp_ganho, remaining)
        if xp_ganho <= 0:
            motivo = 'limite_diario_atingido'

    return {
        'xp_base': xp_base,
        'xp_ganho': xp_ganho,
        'motivo': motivo,
        'multiplier': total_multiplier,
        'seasonal_multiplier': seasonal_multiplier,
        'action': canonical_action,
    }


async def award_xp_with_missions(db: Session, usuario: Usuario, action: str, custom_amount: int = None) -> dict:
    current_date = date.today()
    canonical_action = normalize_action(action)
    calc_result = calculate_xp_for_action(db, usuario, canonical_action, custom_amount, current_date)
    xp_ganho = calc_result['xp_ganho']

    if xp_ganho <= 0:
        return {'xp_ganho': 0, 'level_up': False, 'new_level': usuario.level, 'reason': calc_result.get('motivo', 'sem_xp')}

    usuario.xp = int(usuario.xp or 0) + xp_ganho
    old_level = int(usuario.level or 1)
    new_level = _calculate_level_from_xp(int(usuario.xp or 0))
    usuario.level = new_level

    if usuario.ultimo_login != current_date:
        usuario.ultimo_login = current_date
        usuario.streak_dias = int(usuario.streak_dias or 0) + 1

    db.add(XpEvent(
        id_usuario=usuario.id,
        action=canonical_action,
        xp_base=calc_result['xp_base'],
        xp_gained=xp_ganho,
        details={'multiplier': calc_result['multiplier'], 'level': new_level, 'streak': usuario.streak_dias, 'canonical_action': canonical_action},
    ))

    counter = db.query(XpDailyCounter).filter(
        XpDailyCounter.id_usuario == usuario.id,
        XpDailyCounter.action == canonical_action,
        XpDailyCounter.day_ref == current_date,
    ).first()
    if not counter:
        counter = XpDailyCounter(id_usuario=usuario.id, action=canonical_action, day_ref=current_date, count=0, xp_gained=0)
        db.add(counter)
    counter.count += 1
    counter.xp_gained += xp_ganho

    db.flush()

    # Evento sazonal: aniversário no app (+200 XP, 1x por ano)
    if usuario.criado_em and usuario.criado_em.month == current_date.month and usuario.criado_em.day == current_date.day:
        birthday_exists = db.query(XpEvent.id).filter(
            XpEvent.id_usuario == usuario.id,
            XpEvent.action == 'EVENTO_SAZONAL',
            XpEvent.created_at >= datetime.combine(current_date, datetime.min.time()),
            XpEvent.created_at <= datetime.combine(current_date, datetime.max.time()),
        ).first()
        if not birthday_exists:
            usuario.xp = int(usuario.xp or 0) + 200
            db.add(XpEvent(
                id_usuario=usuario.id,
                action='EVENTO_SAZONAL',
                xp_base=200,
                xp_gained=200,
                details={'event': 'anniversary', 'description': 'Aniversário no app'},
            ))
            new_level = _calculate_level_from_xp(int(usuario.xp or 0))
            usuario.level = new_level

    missions_progress = await _update_mission_progress(db, usuario, canonical_action, current_date)
    achievements = await _unlock_achievements(db, usuario, current_date)

    db.commit()
    return {
        'xp_ganho': xp_ganho,
        'level_up': new_level > old_level,
        'old_level': old_level,
        'new_level': new_level,
        'missions_progress': missions_progress,
        'achievements': achievements,
        'action': canonical_action,
    }


def get_user_active_missions(db: Session, usuario_id: int) -> list:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        return []
    before_new = len(db.new)
    _ensure_user_missions(db, usuario)
    # Garante persistencia do bootstrap em chamadas de leitura do MiniApp.
    if len(db.new) > before_new:
        db.commit()
    user_missions = db.query(UserMission).join(Mission).filter(
        UserMission.id_usuario == usuario_id,
        Mission.active == True,  # noqa: E712
    ).order_by(Mission.sort_order.asc(), UserMission.id.asc()).all()

    missions_data = []
    for um in user_missions:
        target = int(um.target_value or MISSION_TARGETS.get(um.mission.mission_key, 1))
        missions_data.append({
            'id': um.id,
            'mission_key': um.mission.mission_key,
            'name': um.mission.name,
            'description': um.mission.description,
            'type': um.mission.mission_type,
            'xp_reward': int(um.mission.xp_reward or 0),
            'progress': int(um.progress or 0),
            'current_value': int(um.current_value or 0),
            'target_value': target,
            'status': um.status,
            'completed_at': um.completed_at.isoformat() if um.completed_at else None,
            'claimed_at': um.claimed_at.isoformat() if um.claimed_at else None,
        })
    return missions_data


def get_level_progress_payload(usuario: Usuario) -> dict:
    xp_total = int(usuario.xp or 0)
    # O nível canônico vem sempre do XP acumulado para evitar inconsistências
    # em usuários migrados do modelo legado.
    level = _calculate_level_from_xp(xp_total)
    current_info = get_level_info(level)
    next_info = get_level_info(level + 1)
    current_floor = int(current_info.get('required_xp', 0))
    next_floor = int(next_info.get('required_xp', current_floor))
    xp_in_level = max(0, xp_total - current_floor)
    xp_needed = max(1, next_floor - current_floor)
    progress_pct = 100 if level >= 16 and xp_total >= current_floor else int(min(100, (xp_in_level / xp_needed) * 100))
    return {
        'level': level,
        'title': current_info.get('name', 'ContaComigo'),
        'xp_total': xp_total,
        'xp_in_level': xp_in_level,
        'xp_needed': xp_needed,
        'xp_to_next': 0 if level >= 16 else max(0, next_floor - xp_total),
        'next_level': level if level >= 16 else level + 1,
        'next_title': current_info.get('name', 'ContaComigo') if level >= 16 else next_info.get('name', 'ContaComigo'),
        'progress_pct': progress_pct,
        'level_name': current_info.get('name', 'ContaComigo'),
        'tier': current_info.get('tier', 'bronze'),
    }


def get_level_progress(usuario: Usuario) -> dict:
    """Compatibilidade com chamadas antigas para progresso de nível."""
    return get_level_progress_payload(usuario)


def reset_daily_missions_for_all_users(db: Session, reference_date: date | None = None) -> int:
    """Reseta missões diárias para todos os usuários."""
    reference_date = reference_date or date.today()
    daily_keys = [k for k, t in MISSION_TYPES.items() if t == 'daily']
    if not daily_keys:
        return 0

    rows = db.query(UserMission).join(Mission).filter(Mission.mission_key.in_(daily_keys)).all()
    for um in rows:
        um.progress = 0
        um.current_value = 0
        um.status = 'active'
        um.completed_at = None
        um.claimed_at = None
        um.updated_at = datetime.utcnow()
    db.commit()
    return len(rows)


def reset_weekly_missions_for_all_users(db: Session, reference_date: date | None = None) -> int:
    """Reseta missões semanais para todos os usuários."""
    reference_date = reference_date or date.today()
    weekly_keys = [k for k, t in MISSION_TYPES.items() if t == 'weekly']
    if not weekly_keys:
        return 0

    rows = db.query(UserMission).join(Mission).filter(Mission.mission_key.in_(weekly_keys)).all()
    for um in rows:
        um.progress = 0
        um.current_value = 0
        um.status = 'active'
        um.completed_at = None
        um.claimed_at = None
        um.updated_at = datetime.utcnow()
    db.commit()
    return len(rows)


def apply_monthly_performance_awards(db: Session, reference_date: date | None = None) -> int:
    """Aplica bônus mensais principais da especificação para todos os usuários."""
    reference_date = reference_date or date.today()
    if reference_date.day != 1:
        return 0

    last_month_end = reference_date.replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    start_dt = datetime.combine(last_month_start, datetime.min.time())
    end_dt = datetime.combine(last_month_end, datetime.max.time())

    prev_month_end = last_month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    prev_start_dt = datetime.combine(prev_month_start, datetime.min.time())
    prev_end_dt = datetime.combine(prev_month_end, datetime.max.time())

    users = db.query(Usuario).all()
    total_awarded = 0
    for usuario in users:
        entries = db.query(func.coalesce(func.sum(Lancamento.valor), 0)).filter(
            Lancamento.id_usuario == usuario.id,
            Lancamento.data_transacao >= start_dt,
            Lancamento.data_transacao <= end_dt,
            func.lower(Lancamento.tipo).like('entr%'),
        ).scalar() or 0
        outputs = db.query(func.coalesce(func.sum(Lancamento.valor), 0)).filter(
            Lancamento.id_usuario == usuario.id,
            Lancamento.data_transacao >= start_dt,
            Lancamento.data_transacao <= end_dt,
            ~func.lower(Lancamento.tipo).like('entr%'),
        ).scalar() or 0

        if float(entries or 0) > float(abs(outputs or 0)):
            usuario.xp = int(usuario.xp or 0) + int(SPEC_XP_ACTIONS['MONTH_TURN_BLUE'])
            db.add(XpEvent(
                id_usuario=usuario.id,
                action='MONTH_TURN_BLUE',
                xp_base=int(SPEC_XP_ACTIONS['MONTH_TURN_BLUE']),
                xp_gained=int(SPEC_XP_ACTIONS['MONTH_TURN_BLUE']),
                details={'month_start': start_dt.isoformat(), 'month_end': end_dt.isoformat(), 'reason': 'monthly_blue'},
            ))
            total_awarded += 1

        # Redução de gastos por categoria (+40 por categoria, max 2)
        current_cat_rows = db.query(
            Lancamento.id_categoria,
            func.coalesce(func.sum(func.abs(Lancamento.valor)), 0).label('sum_val'),
        ).filter(
            Lancamento.id_usuario == usuario.id,
            Lancamento.data_transacao >= start_dt,
            Lancamento.data_transacao <= end_dt,
            ~func.lower(Lancamento.tipo).like('entr%'),
            Lancamento.id_categoria.isnot(None),
        ).group_by(Lancamento.id_categoria).all()
        prev_cat_rows = db.query(
            Lancamento.id_categoria,
            func.coalesce(func.sum(func.abs(Lancamento.valor)), 0).label('sum_val'),
        ).filter(
            Lancamento.id_usuario == usuario.id,
            Lancamento.data_transacao >= prev_start_dt,
            Lancamento.data_transacao <= prev_end_dt,
            ~func.lower(Lancamento.tipo).like('entr%'),
            Lancamento.id_categoria.isnot(None),
        ).group_by(Lancamento.id_categoria).all()

        current_by_cat = {int(row.id_categoria): float(row.sum_val or 0) for row in current_cat_rows if row.id_categoria is not None}
        prev_by_cat = {int(row.id_categoria): float(row.sum_val or 0) for row in prev_cat_rows if row.id_categoria is not None}
        reduced_categories = [cid for cid, prev_val in prev_by_cat.items() if prev_val > 0 and current_by_cat.get(cid, 0.0) < prev_val]
        reduced_categories = reduced_categories[:2]
        for cid in reduced_categories:
            usuario.xp = int(usuario.xp or 0) + int(SPEC_XP_ACTIONS['CATEGORIA_REDUCAO'])
            db.add(XpEvent(
                id_usuario=usuario.id,
                action='CATEGORIA_REDUCAO',
                xp_base=int(SPEC_XP_ACTIONS['CATEGORIA_REDUCAO']),
                xp_gained=int(SPEC_XP_ACTIONS['CATEGORIA_REDUCAO']),
                details={'category_id': cid, 'month': start_dt.strftime('%Y-%m')},
            ))
            total_awarded += 1

        # Crescimento patrimonial (+80 ou +120 se >=10%)
        patrimony_rows = db.query(PatrimonySnapshot).filter(
            PatrimonySnapshot.id_usuario == usuario.id
        ).order_by(PatrimonySnapshot.mes_referencia.desc()).limit(2).all()
        if len(patrimony_rows) == 2:
            latest = float(patrimony_rows[0].total_patrimonio or 0)
            previous = float(patrimony_rows[1].total_patrimonio or 0)
            if previous > 0 and latest > previous:
                growth_pct = (latest - previous) / previous
                patrimony_xp = 120 if growth_pct >= 0.10 else 80
                usuario.xp = int(usuario.xp or 0) + patrimony_xp
                db.add(XpEvent(
                    id_usuario=usuario.id,
                    action='PATRIMONIO_CRESCIMENTO',
                    xp_base=patrimony_xp,
                    xp_gained=patrimony_xp,
                    details={'growth_pct': round(growth_pct, 4), 'latest': latest, 'previous': previous},
                ))
                total_awarded += 1

        # Economia acima do planejado: usa confirmação mensal de metas existente.
        # Regra: se o usuário tinha metas até o fim do mês e confirmou todas no mês,
        # recebe bônus da ação ECONOMIA_META_ATINGIDA.
        active_goal_ids = [
            row.id for row in db.query(Objetivo.id).filter(
                Objetivo.id_usuario == usuario.id,
                Objetivo.criado_em <= end_dt,
            ).all()
        ]
        if active_goal_ids:
            confirmed_goal_count = db.query(func.count(func.distinct(MetaConfirmacao.id_objetivo))).filter(
                MetaConfirmacao.id_usuario == usuario.id,
                MetaConfirmacao.ano == last_month_start.year,
                MetaConfirmacao.mes == last_month_start.month,
                MetaConfirmacao.valor_confirmado > 0,
                MetaConfirmacao.id_objetivo.in_(active_goal_ids),
            ).scalar() or 0

            if int(confirmed_goal_count) >= len(active_goal_ids):
                economia_xp = int(SPEC_XP_ACTIONS['ECONOMIA_META_ATINGIDA'])
                usuario.xp = int(usuario.xp or 0) + economia_xp
                db.add(XpEvent(
                    id_usuario=usuario.id,
                    action='ECONOMIA_META_ATINGIDA',
                    xp_base=economia_xp,
                    xp_gained=economia_xp,
                    details={
                        'month': start_dt.strftime('%Y-%m'),
                        'active_goals': len(active_goal_ids),
                        'confirmed_goals': int(confirmed_goal_count),
                        'rule': 'monthly_goal_confirmations',
                    },
                ))
                total_awarded += 1

    db.commit()
    return total_awarded
