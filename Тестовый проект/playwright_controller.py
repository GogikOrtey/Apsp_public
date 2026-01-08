import asyncio
import threading
import time
from typing import Optional


class PlaywrightController:
    """
    Один headless Chromium + одна вкладка (Page) на всё приложение.
    Flask-эндпойнты дергают async-логику через отдельный event-loop в фоне.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ready = threading.Event()
        self._init_error: Optional[str] = None

        self._playwright = None
        self._browser = None
        self._context = None
        self._pages = []
        self._active_page = None
        self._op_lock = None

        self._last_screenshot_ts: float = 0.0
        self._last_screenshot: Optional[bytes] = None
        self._cache_ttl_sec = 1.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._ready.clear()
        self._init_error = None

        t = threading.Thread(target=self._thread_main, name="playwright-loop", daemon=True)
        self._thread = t
        t.start()

        # Подождём инициализацию, чтобы ошибки были понятны сразу.
        if not self._ready.wait(timeout=60):
            raise RuntimeError("Playwright не успел инициализироваться за 60 секунд")
        if self._init_error:
            raise RuntimeError(self._init_error)

    def _thread_main(self) -> None:
        try:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._async_init())
            self._ready.set()
            loop.run_forever()
            # Аккуратный shutdown event-loop (важно для Windows/Proactor).
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass
        except Exception as e:  # pragma: no cover
            self._init_error = str(e)
            self._ready.set()

    async def _async_init(self) -> None:
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        # В Docker часто нужно отключать sandbox.
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
        )
        self._pages = []
        self._active_page = None
        self._op_lock = asyncio.Lock()

    def _run(self, coro, timeout: float = 60):
        self.start()
        if not self._loop:
            raise RuntimeError("Playwright loop не инициализирован")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = (url or "").strip()
        if not url:
            raise ValueError("Пустой адрес")
        if "://" not in url:
            url = "https://" + url
        return url

    async def _ensure_active_page(self) -> None:
        if self._active_page and not self._active_page.is_closed():
            return
        if not self._context:
            raise RuntimeError("Playwright context не инициализирован")
        page = await self._context.new_page()
        self._pages.append(page)
        self._active_page = page

    def get_open_pages_count(self) -> int:
        return int(self._run(self._count_pages_async(), timeout=10))

    async def _count_pages_async(self) -> int:
        # Чистим закрытые страницы, чтобы счётчик не разрастался.
        if self._op_lock:
            async with self._op_lock:
                self._pages = [p for p in self._pages if p and not p.is_closed()]
                return len(self._pages)
        self._pages = [p for p in self._pages if p and not p.is_closed()]
        return len(self._pages)

    async def _open_async(self, url: str) -> str:
        if not self._context:
            raise RuntimeError("Playwright context не инициализирован")
        if not self._op_lock:
            raise RuntimeError("Playwright lock не инициализирован")

        async with self._op_lock:
            url = self._normalize_url(url)
            # Требование: каждый новый адрес открываем в новой вкладке (Page).
            prev_active = self._active_page
            page = await self._context.new_page()
            self._pages.append(page)
            self._active_page = page

            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                # Иногда resp может быть None (например, about:blank), но это ок.
                _ = resp
                return page.url
            except Exception:
                # Если открыть не удалось — вкладку закрываем, чтобы счётчик не рос.
                try:
                    await page.close()
                except Exception:
                    pass
                self._pages = [p for p in self._pages if p and not p.is_closed()]
                if prev_active and not prev_active.is_closed():
                    self._active_page = prev_active
                else:
                    self._active_page = None
                raise

    def open_url(self, url: str) -> str:
        final_url = self._run(self._open_async(url), timeout=70)
        # Сброс кэша скрина, чтобы следующий запрос сразу перерисовал.
        self._last_screenshot = None
        self._last_screenshot_ts = 0.0
        return final_url

    async def _screenshot_async(self) -> bytes:
        if not self._op_lock:
            raise RuntimeError("Playwright lock не инициализирован")

        async with self._op_lock:
            await self._ensure_active_page()
            if not self._active_page:
                raise RuntimeError("Playwright page не инициализирован")
            return await self._active_page.screenshot(type="png", full_page=True)

    def get_screenshot_png(self) -> bytes:
        now = time.time()
        if self._last_screenshot and (now - self._last_screenshot_ts) < self._cache_ttl_sec:
            return self._last_screenshot

        data = self._run(self._screenshot_async(), timeout=70)
        self._last_screenshot = data
        self._last_screenshot_ts = now
        return data

    async def _close_async(self) -> None:
        # Закрытие контекста закрывает все вкладки.
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._context = None
        self._browser = None
        self._playwright = None
        self._pages = []
        self._active_page = None
        self._op_lock = None

    def stop(self) -> None:
        # Можно вызывать многократно, в том числе если start() так и не был вызван.
        loop = self._loop
        if not loop:
            return

        try:
            fut = asyncio.run_coroutine_threadsafe(self._close_async(), loop)
            fut.result(timeout=30)
        except Exception:
            pass

        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass

        t = self._thread
        if t and t.is_alive():
            try:
                t.join(timeout=5)
            except Exception:
                pass

        self._loop = None


