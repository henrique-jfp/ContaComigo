# gerente_financeiro/gamification_service.py
import logging
import asyncio
from datetime import date, timedelta, datetime
from sqlalchemy.orm import Session
from models import Usuario, Lancamento, XpEvent, XpDailyCounter, MonthlyGamificationAward

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÕES DE GAMIFICAÇÃO ---

XP_ACTIONS = {
    # 📝 LANÇAMENTOS E REGISTROS
    "LANCAMENTO_MANUAL": 10,           # Registrar transação manualmente
    "LANCAMENTO_AUDIO": 15,            # Registrar transacao por audio
    "LANCAMENTO_OCR": 25,             # Usar OCR para extrair dados de cupom
    "FATURA_PROCESSADA": 50,          # Processar PDF de fatura completa
    "EDICAO_LANCAMENTO": 5,           # Editar/corrigir uma transação
    "EXCLUSAO_LANCAMENTO": 2,         # Excluir transacao
    "ITEM_LANCAMENTO": 3,             # Adicionar item específico
    
    # 💬 INTELIGÊNCIA E ANÁLISE  
    "PERGUNTA_IA_SIMPLES": 5,         # Pergunta básica para IA
    "PERGUNTA_IA_COMPLEXA": 15,       # Análise complexa/insights
    "CONVERSA_IA_LONGA": 25,          # Sessão longa com IA (5+ interações)
    
    # 📊 VISUALIZAÇÕES E RELATÓRIOS
    "GRAFICO_GERADO": 15,             # Gerar qualquer gráfico
    "RELATORIO_MENSAL": 30,           # Relatório mensal completo
    "RELATORIO_PERSONALIZADO": 25,    # Relatório com filtros específicos
    "DASHBOARD_ACESSADO": 8,          # Acessar dashboard web
    
    # 🎯 PLANEJAMENTO E METAS
    "META_CRIADA": 20,                # Criar nova meta financeira
    "META_CHECKIN_MENSAL": 35,        # Check-in mensal da meta
    "META_APORTE_CONFIRMADO": 25,     # Confirmar aporte mensal da meta
    "META_ATINGIDA": 200,             # Atingir uma meta
    "META_CONCLUIDA_100": 100,        # Bonus ao completar 100%
    "META_SUPERADA": 150,             # Superar meta em mais de 10%
    "AGENDAMENTO_CRIADO": 15,         # Criar novo agendamento
    "AGENDAMENTO_EXECUTADO": 10,      # Agendamento executado com sucesso
    
    # ⚙️ CONFIGURAÇÕES E FERRAMENTAS
    "PERFIL_ATUALIZADO": 10,          # Atualizar dados pessoais
    "CONTA_CADASTRADA": 15,           # Cadastrar nova conta/cartão
    "CATEGORIA_PERSONALIZADA": 8,     # Criar categoria personalizada
    "BACKUP_DADOS": 20,               # Fazer backup dos dados
    "CONFIGURACAO_ALTERADA": 5,      # Alterar configurações do bot
    
    # 🎮 SISTEMA SOCIAL E GAMIFICAÇÃO
    "RANKING_VISUALIZADO": 3,         # Ver ranking global
    "PERFIL_VISUALIZADO": 3,          # Ver perfil gamer
    "INTERACAO_BOT": 2,               # Interacao geral com o bot (com cooldown)
    "PERFIL_COMPARTILHADO": 10,       # Compartilhar perfil (futuro)
    "CONQUISTA_DESBLOQUEADA": 25,     # Desbloquear nova conquista
    "PRIMEIRA_INTERACAO_DIA": 15,     # Primeira interação do dia (streak)
    "SEQUENCIA_MANTIDA": 5,           # Manter sequência diária
    
    # 🔥 BÔNUS ESPECIAIS
    "USUARIO_NOVO": 50,               # Bônus de boas-vindas
    "PRIMEIRA_SEMANA": 100,           # Completar primeira semana
    "PRIMEIRO_MES": 250,              # Completar primeiro mês
    "FEEDBACK_DADO": 20,              # Dar feedback sobre o bot
    "BUG_REPORTADO": 30,              # Reportar bug útil
    "SUGESTAO_ACEITA": 50,            # Sugestão implementada
}

LEVELS = {
    1: {"xp_necessario": 0, "titulo": "Iniciante do Cofrinho", "multiplicador": 1.00},
    2: {"xp_necessario": 220, "titulo": "Guardião do Troco", "multiplicador": 1.04},
    3: {"xp_necessario": 520, "titulo": "Caçador de Desperdícios", "multiplicador": 1.07},
    4: {"xp_necessario": 920, "titulo": "Arquiteto do Orçamento", "multiplicador": 1.10},
    5: {"xp_necessario": 1450, "titulo": "Domador de Faturas", "multiplicador": 1.13},
    6: {"xp_necessario": 2100, "titulo": "Estrategista da Receita", "multiplicador": 1.16},
    7: {"xp_necessario": 2900, "titulo": "Mestre da Rotina", "multiplicador": 1.19},
    8: {"xp_necessario": 3850, "titulo": "Navegador de Metas", "multiplicador": 1.22},
    9: {"xp_necessario": 4950, "titulo": "Alquimista de Patrimônio", "multiplicador": 1.25},
    10: {"xp_necessario": 6200, "titulo": "Comandante Financeiro", "multiplicador": 1.28},
    11: {"xp_necessario": 7700, "titulo": "Lorde do Fluxo de Caixa", "multiplicador": 1.31},
    12: {"xp_necessario": 9500, "titulo": "Titã da Disciplina", "multiplicador": 1.34},
    13: {"xp_necessario": 11600, "titulo": "Visionário de Longo Prazo", "multiplicador": 1.37},
    14: {"xp_necessario": 14000, "titulo": "Conselheiro de Ouro", "multiplicador": 1.40},
    15: {"xp_necessario": 16800, "titulo": "Lenda do ContaComigo", "multiplicador": 1.45},
}

_MAX_LEVEL = max(LEVELS.keys())

# Limites por dia para XP por ação (mantém o jogo competitivo e evita farm grátis).
DAILY_XP_CAPS = {
    "INTERACAO_BOT": 10,
    "LANCAMENTO_MANUAL": 20,
    "LANCAMENTO_AUDIO": 20,
    "LANCAMENTO_OCR": 15,
    "FATURA_PROCESSADA": 4,
    "EDICAO_LANCAMENTO": 15,
    "EXCLUSAO_LANCAMENTO": 10,
    "GRAFICO_GERADO": 8,
    "RELATORIO_MENSAL": 3,
    "RELATORIO_PERSONALIZADO": 4,
    "META_CRIADA": 4,
    "META_CHECKIN_MENSAL": 4,
    "META_APORTE_CONFIRMADO": 4,
    "META_ATINGIDA": 2,
    "META_CONCLUIDA_100": 2,
    "META_SUPERADA": 2,
    "AGENDAMENTO_CRIADO": 8,
    "AGENDAMENTO_EXECUTADO": 20,
    "PERGUNTA_IA_SIMPLES": 20,
    "PERGUNTA_IA_COMPLEXA": 10,
    "CONVERSA_IA_LONGA": 6,
    "DASHBOARD_ACESSADO": 10,
    "RANKING_VISUALIZADO": 8,
    "PERFIL_VISUALIZADO": 8,
    "PRIMEIRA_INTERACAO_DIA": 1,
    "SEQUENCIA_MANTIDA": 1,
}

MONTHLY_AWARD_BLUE = 180
MONTHLY_PENALTY_RED = -60

STREAK_BONUS = {
    3: 100,
    7: 200,
    30: 500,
}


def _get_or_create_daily_counter(db: Session, usuario_id: int, action: str, day_ref: date) -> XpDailyCounter:
    counter = (
        db.query(XpDailyCounter)
        .filter(
            XpDailyCounter.id_usuario == usuario_id,
            XpDailyCounter.action == action,
            XpDailyCounter.day_ref == day_ref,
        )
        .first()
    )
    if counter:
        return counter

    counter = XpDailyCounter(
        id_usuario=usuario_id,
        action=action,
        day_ref=day_ref,
        count=0,
        xp_gained=0,
    )
    db.add(counter)
    db.flush()
    return counter


def _log_xp_event(
    db: Session,
    usuario_id: int,
    action: str,
    xp_base: int,
    xp_gained: int,
    details: dict | None = None,
) -> None:
    db.add(
        XpEvent(
            id_usuario=usuario_id,
            action=action,
            xp_base=max(0, int(xp_base or 0)),
            xp_gained=int(xp_gained or 0),
            details=details or {},
        )
    )


def get_level_progress_payload(usuario: Usuario) -> dict:
    level = int(usuario.level or 1)
    xp_total = int(usuario.xp or 0)
    current_info = LEVELS.get(level, LEVELS[1])
    next_info = LEVELS.get(level + 1)
    current_floor = int(current_info.get("xp_necessario", 0))
    next_floor = int(next_info.get("xp_necessario", current_floor)) if next_info else current_floor
    xp_in_level = max(0, xp_total - current_floor)
    xp_needed = max(1, next_floor - current_floor) if next_info else 1
    progress_pct = 100 if not next_info else int(min(100, (xp_in_level / xp_needed) * 100))

    return {
        "level": level,
        "title": current_info.get("titulo", "ContaComigo"),
        "xp_total": xp_total,
        "xp_in_level": xp_in_level,
        "xp_needed": xp_needed,
        "xp_to_next": 0 if not next_info else max(0, next_floor - xp_total),
        "next_level": level if not next_info else level + 1,
        "next_title": current_info.get("titulo", "ContaComigo") if not next_info else next_info.get("titulo", "ContaComigo"),
        "progress_pct": progress_pct,
    }


def _last_month_window(today: date) -> tuple[datetime, datetime, int, int]:
    first_this_month = date(today.year, today.month, 1)
    last_day_prev = first_this_month - timedelta(days=1)
    first_prev = date(last_day_prev.year, last_day_prev.month, 1)
    start_dt = datetime.combine(first_prev, datetime.min.time())
    end_dt = datetime.combine(last_day_prev, datetime.max.time())
    return start_dt, end_dt, first_prev.year, first_prev.month


def _apply_month_turn_adjustment(db: Session, usuario: Usuario, context) -> int:
    today = date.today()
    if today.day > 5:
        return 0

    start_prev, end_prev, ano_ref, mes_ref = _last_month_window(today)
    already = (
        db.query(MonthlyGamificationAward)
        .filter(
            MonthlyGamificationAward.id_usuario == usuario.id,
            MonthlyGamificationAward.ano_ref == ano_ref,
            MonthlyGamificationAward.mes_ref == mes_ref,
            MonthlyGamificationAward.motivo == "monthly_balance",
        )
        .first()
    )
    if already:
        return 0

    lancamentos = (
        db.query(Lancamento)
        .filter(Lancamento.id_usuario == usuario.id)
        .filter(Lancamento.data_transacao >= start_prev)
        .filter(Lancamento.data_transacao <= end_prev)
        .all()
    )
    if not lancamentos:
        return 0

    entradas = 0.0
    saidas = 0.0
    for lanc in lancamentos:
        valor = float(lanc.valor or 0)
        if str(lanc.tipo).lower().startswith("entr"):
            entradas += max(0.0, valor)
        else:
            saidas += abs(valor)
    saldo = entradas - saidas
    ajuste = MONTHLY_AWARD_BLUE if saldo >= 0 else MONTHLY_PENALTY_RED

    if ajuste != 0:
        usuario.xp = max(0, int(usuario.xp or 0) + ajuste)

    db.add(
        MonthlyGamificationAward(
            id_usuario=usuario.id,
            ano_ref=ano_ref,
            mes_ref=mes_ref,
            ajuste_xp=ajuste,
            motivo="monthly_balance",
        )
    )
    _log_xp_event(
        db,
        usuario.id,
        "MONTH_TURN_BLUE" if ajuste > 0 else "MONTH_TURN_RED",
        abs(ajuste),
        ajuste,
        {
            "ano_ref": ano_ref,
            "mes_ref": mes_ref,
            "saldo": round(saldo, 2),
            "entradas": round(entradas, 2),
            "saidas": round(saidas, 2),
        },
    )
    db.commit()

    try:
        texto = (
            f"🏁 Bônus de virada aplicado: +{ajuste} XP! Você fechou o mês no azul."
            if ajuste > 0
            else f"⚠️ Ajuste mensal: {ajuste} XP. Você fechou o mês no vermelho, bora recuperar este mês!"
        )
        asyncio.create_task(
            context.bot.send_message(
                chat_id=usuario.telegram_id,
                text=texto,
                disable_notification=True,
            )
        )
    except Exception:
        pass
    return ajuste

async def award_xp(db: Session, user_id: int, action: str, context, custom_amount: int = None) -> dict:
    """
    Concede XP a um usuário com multiplicadores de nível e streak.
    
    Returns:
        dict: {"xp_gained": int, "level_up": bool, "new_level": int, "streak_bonus": int}
    """
    base_xp = custom_amount or XP_ACTIONS.get(action, 0)
    if base_xp == 0:
        return {"xp_gained": 0, "level_up": False, "new_level": 0, "streak_bonus": 0}

    usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
    if not usuario:
        return {"xp_gained": 0, "level_up": False, "new_level": 0, "streak_bonus": 0}

    hoje = date.today()
    daily_counter = _get_or_create_daily_counter(db, usuario.id, action, hoje)
    daily_counter.count += 1
    cap = DAILY_XP_CAPS.get(action)
    cap_reached = bool(cap and daily_counter.count > cap)

    # 🎯 APLICAR MULTIPLICADORES
    level_info = LEVELS.get(usuario.level, {"multiplicador": 1.0})
    level_multiplier = level_info.get("multiplicador", 1.0)
    
    # 🔥 MULTIPLICADOR DE STREAK
    streak_multiplier = 1.0
    if usuario.streak_dias >= 30:
        streak_multiplier = 2.0  # +100% XP
    elif usuario.streak_dias >= 14:
        streak_multiplier = 1.5  # +50% XP
    elif usuario.streak_dias >= 7:
        streak_multiplier = 1.25 # +25% XP
    
    # 🧮 CALCULAR XP FINAL
    final_xp = 0 if cap_reached else int(base_xp * level_multiplier * streak_multiplier)
    streak_bonus = final_xp - int(base_xp * level_multiplier) if streak_multiplier > 1.0 else 0
    
    # 💰 APLICAR XP
    old_xp = usuario.xp
    usuario.xp += final_xp
    daily_counter.xp_gained += max(0, final_xp)
    
    # 📊 VERIFICAR LEVEL UP
    old_level = usuario.level
    new_level = old_level
    level_up = False
    
    # Verificar se subiu múltiplos níveis
    while new_level < _MAX_LEVEL:
        next_level_info = LEVELS.get(new_level + 1)
        if next_level_info and usuario.xp >= next_level_info["xp_necessario"]:
            new_level += 1
            level_up = True
        else:
            break
    
    usuario.level = new_level
    _log_xp_event(
        db,
        usuario.id,
        action,
        base_xp,
        final_xp,
        {
            "level_multiplier": level_multiplier,
            "streak_multiplier": streak_multiplier,
            "count_today": daily_counter.count,
            "daily_cap": cap,
            "cap_reached": cap_reached,
        },
    )
    db.commit()
    
    # 📢 NOTIFICAÇÃO DE XP
    action_names = {
        "LANCAMENTO_MANUAL": "registrar transação",
        "LANCAMENTO_AUDIO": "registrar por áudio",
        "LANCAMENTO_OCR": "usar OCR automático",
        "FATURA_PROCESSADA": "processar fatura completa",
        "PERGUNTA_IA_SIMPLES": "usar IA do Gerente",
        "PERGUNTA_IA_COMPLEXA": "análise avançada com IA",
        "GRAFICO_GERADO": "gerar gráfico",
        "RELATORIO_MENSAL": "gerar relatório",
        "META_CRIADA": "criar meta financeira",
        "META_CHECKIN_MENSAL": "confirmar check-in da meta",
        "META_ATINGIDA": "atingir sua meta",
        "META_CONCLUIDA_100": "concluir meta 100%",
        "AGENDAMENTO_CRIADO": "criar agendamento",
        "DASHBOARD_ACESSADO": "acessar dashboard",
        "PRIMEIRA_INTERACAO_DIA": "manter sequência diária",
        "RANKING_VISUALIZADO": "ver ranking",
        "PERFIL_VISUALIZADO": "ver perfil",
        "EXCLUSAO_LANCAMENTO": "apagar transação"
    }
    
    action_display = action_names.get(action, action.lower().replace("_", " "))
    
    # 🎉 NOTIFICAÇÃO DETALHADA
    notification = f"⭐ +{final_xp} XP por {action_display}!"
    if cap_reached:
        notification = f"⏱️ Limite diário para {action_display} atingido. Sem XP nesta interação."
    
    if level_multiplier > 1.0:
        notification += f"\n🏆 +{int((level_multiplier - 1) * 100)}% bonus de nível!"
    
    if streak_bonus > 0:
        notification += f"\n🔥 +{streak_bonus} XP bonus de streak ({usuario.streak_dias} dias)!"
    
    async def _send_temp_message(text: str, parse_mode: str | None = None, ttl_seconds: float = 0.7) -> None:
        try:
            msg = await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode=parse_mode,
                disable_notification=True
            )
        except Exception:
            return

        async def _delete_later():
            try:
                await asyncio.sleep(max(ttl_seconds, 0.2))
                await context.bot.delete_message(chat_id=user_id, message_id=msg.message_id)
            except Exception:
                return

        asyncio.create_task(_delete_later())

    # Enviar notificação de XP (silenciosa e temporária)
    try:
        await _send_temp_message(notification, ttl_seconds=0.7)
    except Exception:
        pass
    
    # 🎉 NOTIFICAÇÃO DE LEVEL UP (com som)
    if level_up:
        level_info = LEVELS.get(new_level, {"titulo": "Champion"})
        mensagem_levelup = (
            f"🎉🚀 **LEVEL UP!** 🚀🎉\n\n"
            f"**PARABÉNS!** Você alcançou o **Nível {new_level}**!\n"
            f"🏅 Agora você é um(a) **{level_info['titulo']}**!\n\n"
            f"💫 **Novos benefícios desbloqueados:**\n"
            f"⚡ +{int((level_info.get('multiplicador', 1.0) - 1) * 100)}% XP em todas as ações!\n"
            f"🎯 Acesso a funcionalidades exclusivas!\n\n"
            f"🔥 **Continue dominando suas finanças!**"
        )
        
        try:
            await _send_temp_message(mensagem_levelup, parse_mode='Markdown', ttl_seconds=1.2)
        except Exception:
            pass
    
    logger.info(f"XP concedido: Usuário {user_id} | Ação: {action} | XP: +{final_xp} | Level: {old_level}->{new_level}")
    
    return {
        "xp_gained": final_xp,
        "level_up": level_up,
        "new_level": new_level,
        "streak_bonus": streak_bonus,
        "old_xp": old_xp,
        "new_xp": usuario.xp
    }

async def check_and_update_streak(db: Session, user_id: int, context) -> None:
    """
    Verifica e atualiza a sequência de logins diários do usuário.
    """
    usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
    if not usuario:
        return

    _apply_month_turn_adjustment(db, usuario, context)

    hoje = date.today()
    ultimo_login = usuario.ultimo_login

    if ultimo_login == hoje: # Já fez login hoje
        return

    # Conceder XP pela primeira interação do dia
    await award_xp(db, user_id, "PRIMEIRA_INTERACAO_DIA", context)

    if ultimo_login == hoje - timedelta(days=1): # Continua a sequência
        usuario.streak_dias += 1
        bonus = STREAK_BONUS.get(usuario.streak_dias)
        if bonus:
            usuario.xp += bonus
            _log_xp_event(
                db,
                usuario.id,
                "SEQUENCIA_BONUS",
                bonus,
                bonus,
                {"streak_dias": usuario.streak_dias},
            )
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔥 **SEQUÊNCIA DE {usuario.streak_dias} DIAS!**\n\nVocê ganhou +{bonus} XP de bônus por sua consistência! Continue assim!",
                parse_mode='Markdown'
            )
    else: # Quebrou a sequência
        usuario.streak_dias = 1
    
    usuario.ultimo_login = hoje
    db.commit()


# ---------------------------------------------------------------------------
# Canonical spec wrappers (override legacy behavior above)
# ---------------------------------------------------------------------------

from .gamification_missions_service import (  # noqa: E402
    SPEC_XP_ACTIONS as XP_ACTIONS,
    LEVEL_REQUIREMENTS,
    get_level_progress as _spec_get_level_progress,
    get_level_progress_payload as _spec_get_level_progress_payload,
    award_xp_with_missions as _spec_award_xp_with_missions,
)

LEVELS = {
    level: {
        'xp_necessario': xp_req,
        'titulo': name,
        'multiplicador': {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.05, 6: 1.05, 7: 1.05, 8: 1.05, 9: 1.10, 10: 1.10, 11: 1.10, 12: 1.10, 13: 1.15, 14: 1.15, 15: 1.15, 16: 1.20}.get(level, 1.20),
    }
    for level, (xp_req, name, _tier) in LEVEL_REQUIREMENTS.items()
}


def _spec_get_level_info(level: int) -> dict:
    if level > 16:
        return {
            'level': level,
            'titulo': f'Além do Budget +{level - 16}',
            'multiplicador': 1.20,
            'xp_necessario': 130000 + (level - 16) * 35000,
        }
    xp_req, name, _tier = LEVEL_REQUIREMENTS.get(level, LEVEL_REQUIREMENTS[1])
    return {'level': level, 'titulo': name, 'multiplicador': {1:1.0,2:1.0,3:1.0,4:1.0,5:1.05,6:1.05,7:1.05,8:1.05,9:1.10,10:1.10,11:1.10,12:1.10,13:1.15,14:1.15,15:1.15,16:1.20}.get(level, 1.20), 'xp_necessario': xp_req}


async def award_xp(db: Session, user_id: int, action: str, context, custom_amount: int = None) -> dict:
    from models import Usuario
    usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
    if not usuario:
        return {"xp_gained": 0, "level_up": False, "new_level": 0, "streak_bonus": 0}
    return await _spec_award_xp_with_missions(db, usuario, action, custom_amount)


async def check_and_update_streak(db: Session, user_id: int, context) -> None:
    from models import Usuario
    usuario = db.query(Usuario).filter(Usuario.telegram_id == user_id).first()
    if not usuario:
        return

    hoje = date.today()
    if usuario.ultimo_login == hoje:
        return
    if usuario.ultimo_login == hoje - timedelta(days=1):
        usuario.streak_dias = int(usuario.streak_dias or 0) + 1
    else:
        usuario.streak_dias = 1
    usuario.ultimo_login = hoje
    db.commit()


def get_level_progress_payload(usuario: Usuario) -> dict:
    return _spec_get_level_progress_payload(usuario)


def get_level_progress(usuario: Usuario) -> dict:
    return _spec_get_level_progress(usuario)