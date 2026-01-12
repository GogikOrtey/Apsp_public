from __future__ import annotations

from concurrent.futures import Future
import os
import queue
import threading
from typing import Callable, Any

from playwright.sync_api import sync_playwright, Browser, Playwright, Error as PlaywrightError


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return bool(default)
    v = str(v).strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _maybe_request_container_restart(reason: str) -> None:
    """
    Best-effort: если включено, просим Docker перезапустить контейнер.
    """
    try:
        from task_runtime.container_restart import is_running_in_container, request_container_restart  # noqa: WPS433

        # По умолчанию включаем только в контейнере.
        default = True if is_running_in_container() else False
        if not _env_bool("APSP_RESTART_ON_PLAYWRIGHT_FAIL", default):
            return
        request_container_restart(f"playwright_fatal: {reason}")
    except Exception:
        return


def _is_playwright_fatal_error(exc: BaseException) -> bool:
    """
    Эвристика: отличаем "обычную ошибку задачи" от состояния, когда сам Playwright/Browser отвалился.
    """
    msg = (str(exc) or "").strip().lower()

    # Наши внутренние сигналы из пула.
    if isinstance(exc, RuntimeError) and (
        msg == "pool_not_started"
        or msg == "worker is closed"
        or msg.startswith("browser_not_started")
    ):
        return True

    if isinstance(exc, PlaywrightError):
        fatal_substrings = [
            "target page, context or browser has been closed",
            "browser has been closed",
            "playwright connection closed",
            "connection closed",
            "browser closed",
            "crashed",
        ]
        return any(s in msg for s in fatal_substrings)

    return False


class _Worker:
    def __init__(self, *, headless: bool) -> None:
        self._headless = bool(headless)
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._ready = threading.Event()
        self._closed = False
        self._startup_error: BaseException | None = None

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(timeout=60)

    def submit(self, fn: Callable[[Browser], Any]) -> Future:
        fut: Future = Future()
        if self._closed:
            fut.set_exception(RuntimeError("Worker is closed"))
            return fut
        self._q.put((fut, fn))
        return fut

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._q.put(None)

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        pw: Playwright | None = None
        browser: Browser | None = None
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=self._headless)
        except Exception as exc:  # noqa: BLE001
            # Это уже инфраструктурная ошибка: Playwright/Chromium не стартанул.
            self._startup_error = exc
            _maybe_request_container_restart(f"startup_failed: {exc}")
        finally:
            self._ready.set()

        try:
            while True:
                item = self._q.get()
                if item is None:
                    break
                fut, fn = item
                try:
                    if browser is None:
                        if self._startup_error is not None:
                            raise RuntimeError(f"browser_not_started: {self._startup_error}") from self._startup_error
                        raise RuntimeError("browser_not_started")
                    res = fn(browser)
                    fut.set_result(res)
                except Exception as exc:  # noqa: BLE001
                    if _is_playwright_fatal_error(exc):
                        _maybe_request_container_restart(str(exc))
                    fut.set_exception(exc)
        finally:
            try:
                if browser is not None:
                    browser.close()
            finally:
                if pw is not None:
                    pw.stop()


class PlaywrightPool:
    """
    Pool of worker threads, each owning its own Playwright+Browser instance.

    This allows true parallel tasks with sync Playwright (thread-affinity safe).
    """

    def __init__(self, *, max_workers: int = 10, headless: bool = True) -> None:
        self._max_workers = int(max_workers)
        self._headless = bool(headless)
        self._workers: list[_Worker] = []
        self._rr = 0
        self._lock = threading.Lock()
        self._started = False

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            # Start with 1 worker (keeps 1 browser opened on service start),
            # scale up on demand in submit().
            w = _Worker(headless=self._headless)
            w.start()
            self._workers = [w]
            self._started = True

    def submit(self, fn: Callable[[Browser], Any]) -> Future:
        self.start()
        with self._lock:
            if not self._workers:
                fut: Future = Future()
                fut.set_exception(RuntimeError("pool_not_started"))
                return fut
            # scale up (best-effort): start a new worker per submitted task until max_workers
            if len(self._workers) < self._max_workers:
                nw = _Worker(headless=self._headless)
                nw.start()
                self._workers.append(nw)
            w = self._workers[self._rr % len(self._workers)]
            self._rr += 1
        return w.submit(fn)

    def close(self) -> None:
        with self._lock:
            for w in self._workers:
                w.close()

    def join(self, timeout: float | None = None) -> None:
        with self._lock:
            workers = list(self._workers)
        for w in workers:
            w.join(timeout=timeout)


