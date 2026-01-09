from __future__ import annotations

import os
import time

from task_runtime.task_context import get_current_task_started_at_ts


TASK_TIMEOUT_MESSAGE = "Время работы задачи превышено"


class TaskTimeoutException(RuntimeError):
    """
    Специальное исключение для "таймаут выполнения задачи".

    Важно:
    - его удобно детектировать в TaskRegistry, чтобы НЕ делать ретраи
      (даже если max_attempts > 1)
    - текст исключения должен быть коротким и человекочитаемым
    """


def _normalize_timeout_seconds(timeout_seconds: float | int | None) -> float:
    if timeout_seconds is None:
        # По умолчанию 30 минут.
        env_v = os.getenv("APSP_TASK_TIMEOUT_SECONDS")
        if env_v is not None:
            try:
                timeout_seconds = float(env_v)
            except Exception:
                timeout_seconds = 30.0 * 60.0
        else:
            timeout_seconds = 30.0 * 60.0
    try:
        timeout_f = float(timeout_seconds)
    except Exception:
        timeout_f = 30.0 * 60.0
    # Минимум 1 секунда, чтобы не сломать сценарии тестов.
    return max(1.0, timeout_f)


def raise_if_timeout(
    *,
    uid: str | None = None,  # uid сейчас не нужен, оставлен для будущей диагностики
    started_at_ts: float | None = None,
    timeout_seconds: float | int | None = None,
    now_ts: float | None = None,
) -> None:
    """
    Кооперативная проверка таймаута задачи.

    Важно: это НЕ "жёсткое убийство" потока. Это guard, который нужно вызывать
    в длинных операциях/циклах (main_processer, ожидание LLM и т.д.).
    """
    timeout_s = _normalize_timeout_seconds(timeout_seconds)
    if started_at_ts is None:
        try:
            started_at_ts = get_current_task_started_at_ts()
        except Exception:
            started_at_ts = None
    if started_at_ts is None:
        # Если контекст не выставлен (legacy режим) — таймаут не проверяем.
        return

    now = float(time.time() if now_ts is None else now_ts)
    if now - float(started_at_ts) >= timeout_s:
        # Сообщение специально короткое — его пишет UI/meta/result_code.
        raise TaskTimeoutException(TASK_TIMEOUT_MESSAGE)


