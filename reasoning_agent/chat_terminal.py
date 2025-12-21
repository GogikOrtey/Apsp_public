from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

CHAT_LOG_PATH: Path | None = None
_terminal_launched = False


def init_chat_channel(log_path: str | Path | None = None, launch_terminal: bool = True) -> Path:
    """
    Prepares a chat log file and optionally opens a second terminal that tails it.
    Returns the resolved log path.
    """
    global CHAT_LOG_PATH

    if CHAT_LOG_PATH is None:
        CHAT_LOG_PATH = Path(log_path) if log_path else Path(__file__).resolve().parent / "chat_output.log"
        CHAT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHAT_LOG_PATH.touch(exist_ok=True)

    if launch_terminal:
        _launch_chat_terminal(CHAT_LOG_PATH)

    return CHAT_LOG_PATH


def chat_print(*values: Iterable[object], sep: str = " ", end: str = "\n") -> None:
    """
    Lightweight analog of print that writes to the chat log.
    """
    if CHAT_LOG_PATH is None:
        init_chat_channel(launch_terminal=False)

    message = sep.join(str(v) for v in values) + end
    with open(CHAT_LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(message)
        log_file.flush()


def _launch_chat_terminal(log_path: Path) -> None:
    """
    Opens a new terminal window that streams the chat log.
    """
    global _terminal_launched
    if _terminal_launched:
        return

    viewer_script = Path(__file__).resolve().parent / "chat_viewer.py"
    cmd = f'start "" "{sys.executable}" -u "{viewer_script}" "{log_path}"'
    # shell=True is required for `start` on Windows cmd.
    subprocess.Popen(cmd, shell=True)
    _terminal_launched = True


