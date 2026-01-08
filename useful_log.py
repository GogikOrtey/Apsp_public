from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

USEFUL_LOG_PATH: Path | None = None


def init_useful_log(log_path: str | Path | None = None, truncate: bool = True) -> Path:
    """
    Prepares useful_log.log file and returns the resolved log path.
    If truncate=True, clears the file on the first init call (per process).
    """
    global USEFUL_LOG_PATH

    if USEFUL_LOG_PATH is None:
        USEFUL_LOG_PATH = Path(log_path) if log_path else Path(__file__).resolve().parent / "useful_log.log"
        USEFUL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if truncate else "a"
        with open(USEFUL_LOG_PATH, mode, encoding="utf-8") as f:
            if truncate:
                now = datetime.now()
                f.write(now.strftime("%d.%m.%Y %H:%M:%S") + "\n\n")
                f.flush()

    return USEFUL_LOG_PATH


def print_useful_log(*values: Iterable[object], sep: str = " ", end: str = "\n") -> None:
    """
    Lightweight analog of print that writes to useful_log.log (project root).
    """
    if USEFUL_LOG_PATH is None:
        init_useful_log(truncate=False)

    message = sep.join(str(v) for v in values) + end
    with open(USEFUL_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(message)
        log_file.flush()


def print_ul(*values: Iterable[object], sep: str = " ", end: str = "\n") -> None:
    """
    Alias for print_useful_log(...)
    """
    print_useful_log(*values, sep=sep, end=end)


# Ensure the log file is created/truncated on module import (once per process).
init_useful_log(truncate=True)


