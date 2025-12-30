from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

from pathlib import Path
import sys
import os
import json

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from playwright_tool.shared_page import set_shared_page, maybe_push_screenshot_to_front

# region Запуск браузера

def launch_browser(headless: bool = True) -> tuple[Playwright, Browser, Page]:
    """
    Запускает браузер Chromium и возвращает Playwright, Browser и Page.
    """
    print("Запускаем браузер")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    set_shared_page(page)
    # Пушим первый кадр (если Flask запущен) — дальше кадры будут пушиться после действий (goto/click/wait).
    maybe_push_screenshot_to_front(min_interval_ms=0)
    print("Браузер успешно запущен")
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
    print("Переходим на страницу", url)
    page.goto(url, wait_until=wait_until, timeout=timeout)
    return page


def get_page_html(page: Page) -> str:
    """
    Возвращает полный HTML-код текущей страницы.
    """
    print("Получаем html страницы")
    return page.content()


def save_page_html(html: str, filename: str = "page_html.html") -> str:
    """
    Сохраняет HTML в файл рядом со скриптом и возвращает путь к файлу.
    
    Args:
        html: html-содержимое страницы
    """
    print("Сохраняем html страницы в файл", filename)
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

def fetch_page_html(
    url: str,
    *,
    headless: bool = True,
    wait_until: str = "load",
    timeout: int = 30_000,
    keep_open: bool = False,
) -> str:
    """
    Общая функция: запускает браузер, открывает страницу и возвращает её HTML.

    Args:
        url: адрес страницы.
        headless: запуск без UI. Чтобы увидеть окно — передайте False.
        wait_until: условие завершения загрузки.
        timeout: таймаут перехода.
        keep_open: если True и headless = False, после загрузки ждём ввода пользователя, прежде чем закрыть окно браузера

    Returns:
        html: html открытой страницы
    """

    headless = False # Запускаю с видимым окном
    pw, browser, page = launch_browser(headless=headless)

    try:        
        goto_page(page, url, wait_until=wait_until, timeout=timeout)        
        html = get_page_html(page)        
        save_page_html(html)

        print("Работа fetch_page_html завершена ✅")

        # Не закрываю окно браузера после выполнения задачи, пока не получу ввод в консоли
        if keep_open and not headless:
            input("Нажмите Enter, чтобы закрыть браузер...")

        return html

    finally:
        close_browser(pw, browser)


# link_html = "https://makitaclub.ru/"
# fetch_page_html( link_html, keep_open=True)