from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Iterable

CHAT_LOG_PATH: Path | None = None
_terminal_launched = False
_terminal_pid_file = Path(__file__).resolve().parent / "chat_terminal.pid"


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

    _terminate_previous_terminal()

    viewer_script = Path(__file__).resolve().parent / "chat_viewer.py"
    creationflags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    proc = subprocess.Popen(
        [sys.executable, "-u", str(viewer_script), str(log_path)],
        creationflags=creationflags,
    )
    _terminal_launched = True
    try:
        _terminal_pid_file.write_text(str(proc.pid), encoding="utf-8")
    except Exception:
        pass


def _terminate_previous_terminal() -> None:
    """
    Closes the previously launched chat viewer if it is still running.
    Ensures we keep only one extra console per run.
    """
    if not _terminal_pid_file.exists():
        return

    try:
        pid_text = _terminal_pid_file.read_text(encoding="utf-8").strip()
        pid = int(pid_text)
    except Exception:
        _terminal_pid_file.unlink(missing_ok=True)
        return

    # Try graceful termination; fall back to taskkill on Windows.
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
    finally:
        _terminal_pid_file.unlink(missing_ok=True)

