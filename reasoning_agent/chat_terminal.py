from __future__ import annotations

from pathlib import Path
from typing import Iterable

CHAT_LOG_PATH: Path | None = None


def init_chat_channel(log_path: str | Path | None = None, truncate: bool = True) -> Path:
    """
    Prepares a chat log file and returns the resolved log path.
    If truncate=True, clears the file on the first init call (per process).
    """
    global CHAT_LOG_PATH

    if CHAT_LOG_PATH is None:
        CHAT_LOG_PATH = Path(log_path) if log_path else Path(__file__).resolve().parent / "chat_output.log"
        CHAT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if truncate else "a"
        with open(CHAT_LOG_PATH, mode, encoding="utf-8"):
            pass

    return CHAT_LOG_PATH


def chat_print(*values: Iterable[object], sep: str = " ", end: str = "\n") -> None:
    """
    Lightweight analog of print that writes to the chat log.
    """
    if CHAT_LOG_PATH is None:
        init_chat_channel(truncate=False)

    message = sep.join(str(v) for v in values) + end
    with open(CHAT_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(message)
        log_file.flush()

