"""Facade de compatibilidade para o sistema canônico de gamificação.

Este módulo mantém nomes legados usados em outros pontos do projeto,
mas delega toda regra de XP, níveis e missões para
`gamification_missions_service.py`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from models import Usuario
from .gamification_missions_service import (
    LEVEL_REQUIREMENTS,
    award_xp_with_missions,
    get_level_multiplier,
    get_level_progress_payload as _canonical_level_payload,
)


# Compatibilidade para telas legadas que esperam LEVELS[level][...].
LEVELS = {
    lvl: {
        "xp_necessario": int(req_xp),
        "titulo": name,
        "multiplicador": 1.0 + float(get_level_multiplier(lvl)),
        "tier": tier,
    }
    for lvl, (req_xp, name, tier) in LEVEL_REQUIREMENTS.items()
}


async def award_xp(db: Session, user_id: int, action: str, context, custom_amount: int | None = None) -> dict:
    """Concede XP usando o sistema canônico, recebendo `telegram_id` legado."""
    usuario = db.query(Usuario).filter(Usuario.telegram_id == int(user_id)).first()
    if not usuario:
        return {
            "xp_gained": 0,
            "level_up": False,
            "new_level": 0,
            "reason": "usuario_nao_encontrado",
        }

    result = await award_xp_with_missions(db, usuario, action, custom_amount)
    return {
        "xp_gained": int(result.get("xp_ganho", 0)),
        "level_up": bool(result.get("level_up", False)),
        "old_level": int(result.get("old_level", usuario.level or 1)),
        "new_level": int(result.get("new_level", usuario.level or 1)),
        "missions_progress": result.get("missions_progress", []),
        "achievements": result.get("achievements", []),
        "action": result.get("action", action),
        "reason": result.get("reason"),
    }


def get_level_progress_payload(usuario: Usuario) -> dict:
    """Retorna payload canônico de progresso de nível."""
    return _canonical_level_payload(usuario)


def get_level_progress(usuario: Usuario) -> dict:
    """Alias de compatibilidade para chamadas antigas."""
    return _canonical_level_payload(usuario)
