from __future__ import annotations

import os
from pathlib import Path
import threading
import time


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return bool(default)
    v = str(v).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def is_running_in_container() -> bool:
    """
    Best-effort определение, что код запущен внутри Docker.

    Важно: на Windows (os.name == "nt") контейнерный рестарт делать нельзя.
    """
    if os.name == "nt":
        return False
    # Common Docker marker
    try:
        if Path("/.dockerenv").is_file():
            return True
    except Exception:
        pass
    # Explicit override (если нужно)
    return _env_bool("APSP_IN_DOCKER", False)


def request_container_restart(reason: str, *, delay_s: float = 0.75) -> bool:
    """
    Завершает PID=1 внутри контейнера (обычно gunicorn), чтобы Docker поднял контейнер заново
    по restart-policy.

    Возвращает True если рестарт был запрошен (или уже в процессе), иначе False.
    """
    # Без контейнера (локальный запуск) — не делаем ничего.
    if not is_running_in_container():
        return False

    # Глобальный флажок "выключить" (на всякий случай).
    if not _env_bool("APSP_ENABLE_SELF_RESTART", True):
        return False

    reason = str(reason or "").strip() or "unknown_reason"

    def _killer() -> None:
        time.sleep(max(0.0, float(delay_s)))
        try:
            import signal  # noqa: WPS433

            # В контейнере PID 1 — это обычно gunicorn master (см. docker-entrypoint.sh).
            os.kill(1, signal.SIGTERM)
            return
        except Exception:
            # Fallback: жёсткий выход текущего процесса (best-effort).
            try:
                os._exit(0)  # noqa: WPS437
            except Exception:
                return

    try:
        print(f"[APSP] REQUEST CONTAINER RESTART: {reason}", flush=True)
    except Exception:
        pass

    t = threading.Thread(target=_killer, name="apsp_container_restart", daemon=True)
    t.start()
    return True


