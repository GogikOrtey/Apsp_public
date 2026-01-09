from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from task_runtime.task_context import get_current_task_uid


USER_STOP_MESSAGE = "Генерация была остановлена пользователем"


class UserStopException(RuntimeError):
    """
    Специальное исключение для "остановки пользователем".

    Важно:
    - его удобно детектировать в TaskRegistry, чтобы НЕ делать ретраи
    - текст исключения должен быть коротким и человекочитаемым
    """


@dataclass
class _StopEntry:
    reason: str
    ts: float


_LOCK = threading.Lock()
_STOP: dict[str, _StopEntry] = {}


def request_stop(uid: str, *, reason: str | None = None) -> None:
    uid_norm = str(uid or "").strip().lower()
    if not uid_norm:
        return
    entry = _StopEntry(reason=str(reason or USER_STOP_MESSAGE), ts=time.time())
    with _LOCK:
        _STOP[uid_norm] = entry


def clear_stop(uid: str) -> None:
    uid_norm = str(uid or "").strip().lower()
    if not uid_norm:
        return
    with _LOCK:
        _STOP.pop(uid_norm, None)


def get_stop_reason(uid: str) -> str | None:
    uid_norm = str(uid or "").strip().lower()
    if not uid_norm:
        return None
    with _LOCK:
        entry = _STOP.get(uid_norm)
    return str(entry.reason) if entry else None


def get_stop_reason_current_task() -> str | None:
    uid = None
    try:
        uid = get_current_task_uid()
    except Exception:
        uid = None
    return get_stop_reason(uid) if uid else None


def raise_if_stop_requested(uid: str | None) -> None:
    reason = get_stop_reason(uid) if uid else get_stop_reason_current_task()
    if reason:
        raise UserStopException(reason)


