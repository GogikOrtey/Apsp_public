from __future__ import annotations

from concurrent.futures import Future
import queue
import threading
from typing import Callable, Any

from playwright.sync_api import sync_playwright, Browser, Playwright


class _Worker:
    def __init__(self, *, headless: bool) -> None:
        self._headless = bool(headless)
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._ready = threading.Event()
        self._closed = False

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
                        raise RuntimeError("browser_not_started")
                    res = fn(browser)
                    fut.set_result(res)
                except Exception as exc:  # noqa: BLE001
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


