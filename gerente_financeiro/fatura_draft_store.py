import threading
import time
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional

_DRAFT_TTL_SECONDS = 60 * 60
_LOCK = threading.Lock()
_DRAFTS: Dict[str, Dict[str, Any]] = {}
_PENDING_EDITOR_TOKEN_BY_USER: Dict[int, Dict[str, Any]] = {}


def _now() -> float:
    return time.time()


def _cleanup_expired() -> None:
    now = _now()
    expired = [token for token, item in _DRAFTS.items() if item.get("expires_at", 0) <= now]
    for token in expired:
        _DRAFTS.pop(token, None)

    expired_pending = [
        uid
        for uid, item in _PENDING_EDITOR_TOKEN_BY_USER.items()
        if item.get("expires_at", 0) <= now or item.get("token") not in _DRAFTS
    ]
    for uid in expired_pending:
        _PENDING_EDITOR_TOKEN_BY_USER.pop(uid, None)


def create_fatura_draft(
    telegram_user_id: int,
    conta_id: int,
    conta_nome: str,
    transacoes: List[Dict[str, Any]],
    origem_label: str,
) -> str:
    token = uuid.uuid4().hex
    payload = {
        "token": token,
        "telegram_user_id": int(telegram_user_id),
        "conta_id": int(conta_id),
        "conta_nome": conta_nome,
        "origem_label": origem_label,
        "transacoes": deepcopy(transacoes),
        "created_at": _now(),
        "expires_at": _now() + _DRAFT_TTL_SECONDS,
    }
    with _LOCK:
        _cleanup_expired()
        _DRAFTS[token] = payload
    return token


def get_fatura_draft(token: str, telegram_user_id: int) -> Optional[Dict[str, Any]]:
    with _LOCK:
        _cleanup_expired()
        item = _DRAFTS.get(token)
        if not item:
            return None
        if int(item.get("telegram_user_id", 0)) != int(telegram_user_id):
            return None
        return deepcopy(item)


def pop_fatura_draft(token: str, telegram_user_id: int) -> Optional[Dict[str, Any]]:
    with _LOCK:
        _cleanup_expired()
        item = _DRAFTS.get(token)
        if not item:
            return None
        if int(item.get("telegram_user_id", 0)) != int(telegram_user_id):
            return None
        _DRAFTS.pop(token, None)
        return deepcopy(item)


def set_pending_editor_token(telegram_user_id: int, token: str) -> None:
    with _LOCK:
        _cleanup_expired()
        _PENDING_EDITOR_TOKEN_BY_USER[int(telegram_user_id)] = {
            "token": token,
            "expires_at": _now() + _DRAFT_TTL_SECONDS,
        }


def pop_pending_editor_token(telegram_user_id: int) -> Optional[str]:
    with _LOCK:
        _cleanup_expired()
        payload = _PENDING_EDITOR_TOKEN_BY_USER.pop(int(telegram_user_id), None)
        if not payload:
            return None
        token = str(payload.get("token") or "")
        if not token or token not in _DRAFTS:
            return None
        return token
