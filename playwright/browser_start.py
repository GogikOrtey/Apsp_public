from playwright.sync_api import sync_playwright, Page, Browser, Playwright


def launch_browser(headless: bool = True) -> tuple[Playwright, Browser, Page]:
    """
    Запускает браузер Chromium и возвращает Playwright, Browser и Page.
    """
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    return pw, browser, page


def goto_page(page: Page, url: str, wait_until: str = "load", timeout: int = 30_000) -> Page:
    """
    Открывает страницу по указанному URL.
    """
    page.goto(url, wait_until=wait_until, timeout=timeout)
    return page


def get_page_html(page: Page) -> str:
    """
    Возвращает полный HTML-код текущей страницы.
    """
    return page.content()


def close_browser(playwright: Playwright, browser: Browser) -> None:
    """
    Закрывает браузер и останавливает Playwright.
    """
    try:
        browser.close()
    finally:
        playwright.stop()


def fetch_page_html(url: str, *, headless: bool = True, wait_until: str = "load", timeout: int = 30_000) -> str:
    """
    Общая функция: запускает браузер, открывает страницу и возвращает её HTML.
    """
    pw, browser, page = launch_browser(headless=headless)
    try:
        goto_page(page, url, wait_until=wait_until, timeout=timeout)
        return get_page_html(page)
    finally:
        close_browser(pw, browser)

