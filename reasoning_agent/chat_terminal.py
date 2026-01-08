from __future__ import annotations

from pathlib import Path
from typing import Iterable
import threading

from task_runtime.task_context import get_current_task_dir

_tls = threading.local()


def _resolve_log_path(log_path: str | Path | None = None) -> Path:
    if log_path:
        return Path(log_path)
    task_dir = get_current_task_dir()
    if task_dir:
        return task_dir / "chat_output.log"
    return Path(__file__).resolve().parent / "chat_output.log"


def init_chat_channel(log_path: str | Path | None = None, truncate: bool = True) -> Path:
    """
    Prepares a chat log file and returns the resolved log path.
    If truncate=True, clears the file on the first init call (per process).
    """
    path = getattr(_tls, "path", None)
    if path is None:
        path = _resolve_log_path(log_path)
        setattr(_tls, "path", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if truncate else "a"
        with open(path, mode, encoding="utf-8"):
            pass

    return path


def chat_print(*values: Iterable[object], sep: str = " ", end: str = "\n") -> None:
    """
    Lightweight analog of print that writes to the chat log.
    """
    path = getattr(_tls, "path", None)
    if path is None:
        path = init_chat_channel(truncate=False)

    message = sep.join(str(v) for v in values) + end
    with open(path, "a", encoding="utf-8") as log_file:
        log_file.write(message)
        log_file.flush()

