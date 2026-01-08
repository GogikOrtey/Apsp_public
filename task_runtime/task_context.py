from __future__ import annotations

from pathlib import Path
import threading

_tls = threading.local()


def set_current_task(uid: str, task_dir: str | Path) -> None:
    _tls.uid = str(uid)
    _tls.task_dir = Path(task_dir)


def clear_current_task() -> None:
    if hasattr(_tls, "uid"):
        delattr(_tls, "uid")
    if hasattr(_tls, "task_dir"):
        delattr(_tls, "task_dir")


def get_current_task_uid() -> str | None:
    uid = getattr(_tls, "uid", None)
    return str(uid) if uid else None


def get_current_task_dir() -> Path | None:
    task_dir = getattr(_tls, "task_dir", None)
    return Path(task_dir) if task_dir else None


