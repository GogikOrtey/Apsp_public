from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

# region Запуск браузера

def launch_browser(headless: bool = True) -> tuple[Playwright, Browser, Page]:
    """
    Запускает браузер Chromium и возвращает Playwright, Browser и Page.
    """
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    return pw, browser, page


# region Инструменты

def goto_page(page: Page, url: str, wait_until: str = "load", timeout: int = 30_000) -> Page:
    """
    Открывает страницу по указанному URL

    Args:
        page (Page): Экземпляр страницы Playwright
        url (str): URL страницы для перехода
        wait_until (str): Событие, при котором переход считается завершённым
            (например: "load", "domcontentloaded", "networkidle")
        timeout (int): Максимальное время ожидания в миллисекундах

    Returns:
        Page: Страница после перехода по URL
    """
    page.goto(url, wait_until=wait_until, timeout=timeout)
    return page


def get_page_html(page: Page) -> str:
    """
    Возвращает полный HTML-код текущей страницы.
    """
    return page.content()


def save_page_html(html: str, filename: str = "page_html.html") -> str:
    """
    Сохраняет HTML в файл рядом со скриптом и возвращает путь к файлу.
    
    Args:
        html: html-содержимое страницы
    """
    output_path = Path(__file__).resolve().parent / filename
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


def close_browser(playwright: Playwright, browser: Browser) -> None:
    """
    Закрывает браузер и останавливает Playwright.
    """
    try:
        browser.close()
    finally:
        playwright.stop()


# region Использование

def fetch_page_html(url: str, *, headless: bool = True, wait_until: str = "load", timeout: int = 30_000) -> str:
    """
    Общая функция: запускает браузер, открывает страницу и возвращает её HTML.

    Args:
        url: адрес страницы.
        headless: запуск без UI. Чтобы увидеть окно — передайте False.
        wait_until: условие завершения загрузки.
        timeout: таймаут перехода.
        keep_open: если True и headless=False, после загрузки ждём,
            пока пользователь сам закроет окно браузера.
    """

    headless = False # Показываем окно браузера
    pw, browser, page = launch_browser(headless=headless)
    try:
        goto_page(page, url, wait_until=wait_until, timeout=timeout)
        html = get_page_html(page)
        save_page_html(html)
        return html
    finally:
        close_browser(pw, browser)

link_html = "https://makitaclub.ru/"
fetch_page_html(link_html)