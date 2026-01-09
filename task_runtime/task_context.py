from __future__ import annotations

from pathlib import Path
import threading

_tls = threading.local()


def set_current_task(uid: str, task_dir: str | Path, started_at_ts: float | None = None) -> None:
    _tls.uid = str(uid)
    _tls.task_dir = Path(task_dir)
    if started_at_ts is not None:
        try:
            _tls.started_at_ts = float(started_at_ts)
        except Exception:
            # best-effort
            pass


def clear_current_task() -> None:
    if hasattr(_tls, "uid"):
        delattr(_tls, "uid")
    if hasattr(_tls, "task_dir"):
        delattr(_tls, "task_dir")
    if hasattr(_tls, "started_at_ts"):
        delattr(_tls, "started_at_ts")


def get_current_task_uid() -> str | None:
    uid = getattr(_tls, "uid", None)
    return str(uid) if uid else None


def get_current_task_dir() -> Path | None:
    task_dir = getattr(_tls, "task_dir", None)
    return Path(task_dir) if task_dir else None


def get_current_task_started_at_ts() -> float | None:
    v = getattr(_tls, "started_at_ts", None)
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


