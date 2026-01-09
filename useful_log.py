from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable
import threading

from task_runtime.task_context import get_current_task_dir

_tls = threading.local()


def _resolve_log_path(log_path: str | Path | None = None) -> Path:
    """
    Choose log path:
    - explicit log_path if provided
    - else task-local path RESULT_TASKS/<uid>/useful_log.log if task_context is set
    - else fallback to module directory useful_log.log
    """
    if log_path:
        return Path(log_path)

    task_dir = get_current_task_dir()
    if task_dir:
        return task_dir / "useful_log.log"
    return Path(__file__).resolve().parent / "useful_log.log"


def init_useful_log(log_path: str | Path | None = None, truncate: bool = True) -> Path:
    """
    Prepares useful_log.log file and returns the resolved log path.
    If truncate=True, clears the file on the first init call (per process).
    """
    path = getattr(_tls, "path", None)
    if path is None:
        path = _resolve_log_path(log_path)
        setattr(_tls, "path", path)

    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if truncate else "a"
    with open(path, mode, encoding="utf-8") as f:
        if truncate:
            now = datetime.now()
            f.write(now.strftime("%d.%m.%Y %H:%M:%S") + "\n\n")
            f.flush()

    return path


def print_useful_log(*values: Iterable[object], sep: str = " ", end: str = "\n") -> None:
    """
    Lightweight analog of print that writes to useful_log.log (project root).
    """
    path = getattr(_tls, "path", None)
    if path is None:
        path = init_useful_log(truncate=False)
    else:
        # ensure file exists
        path.parent.mkdir(parents=True, exist_ok=True)

    start_str = "> "
    message = start_str + sep.join(str(v) for v in values) + end
    with open(path, "a", encoding="utf-8") as log_file:
        log_file.write(message)
        log_file.flush()


def print_ul(*values: Iterable[object], sep: str = " ", end: str = "\n") -> None:
    """
    Alias for print_useful_log(...)
    """
    print_useful_log(*values, sep=sep, end=end)


"""
Важно:
Раньше модуль создавал/трунил useful_log.log на import.
Для многозадачности это плохо (можно затереть логи другой задачи), поэтому инициализацию
делаем лениво при первом вызове print_ul/print_useful_log в конкретном task-thread.
"""


