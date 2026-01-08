from __future__ import annotations

import sys
import threading
from typing import TextIO


class ThreadDispatchWriter:
    """
    Route writes to a per-thread target file, while still mirroring to base.
    """

    def __init__(self, base: TextIO) -> None:
        self._base = base
        self._lock = threading.Lock()
        self._targets: dict[int, TextIO] = {}

    def register(self, target: TextIO) -> None:
        with self._lock:
            self._targets[threading.get_ident()] = target

    def unregister(self) -> None:
        with self._lock:
            self._targets.pop(threading.get_ident(), None)

    def write(self, data: str) -> int:
        tid = threading.get_ident()
        target = None
        with self._lock:
            target = self._targets.get(tid)
        if target is not None:
            target.write(data)
            target.flush()
        self._base.write(data)
        self._base.flush()
        return len(data)

    def flush(self) -> None:
        with self._lock:
            for t in self._targets.values():
                try:
                    t.flush()
                except Exception:
                    pass
        try:
            self._base.flush()
        except Exception:
            pass


_router_stdout: ThreadDispatchWriter | None = None
_router_stderr: ThreadDispatchWriter | None = None


def install_print_router() -> None:
    """
    Install a per-thread dispatching stdout/stderr.
    Safe to call multiple times.
    """
    global _router_stdout, _router_stderr
    if _router_stdout is None:
        _router_stdout = ThreadDispatchWriter(sys.__stdout__)
        sys.stdout = _router_stdout  # type: ignore[assignment]
    if _router_stderr is None:
        _router_stderr = ThreadDispatchWriter(sys.__stderr__)
        sys.stderr = _router_stderr  # type: ignore[assignment]


def register_thread_io(out_file: TextIO, err_file: TextIO | None = None) -> None:
    install_print_router()
    if _router_stdout:
        _router_stdout.register(out_file)
    if err_file is not None and _router_stderr:
        _router_stderr.register(err_file)


def unregister_thread_io() -> None:
    if _router_stdout:
        _router_stdout.unregister()
    if _router_stderr:
        _router_stderr.unregister()


