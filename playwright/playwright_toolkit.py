"""
Набор инструментов для агента, для взаимодействия внутри Playwright.

Реализованы базовые операции:
    - page_restart() — перезагрузка текущей страницы.
    - goto_url() — переход на переданный URL.
    - check_url_status() — получение HTTP-кода ответа по URL без навигации.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Literal

from playwright.sync_api import Page, Response

# Декоратор аннотаций берём из reasoning_agent, чтобы формат совпадал
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from reasoning_agent.agent_tools import tool  # noqa: E402









"""
    Понадобятся такие функции инструменты:
    
    - page_restart()
        - Перезагружает текущую страницу
    - Переход на указанную страницу по url
    - Проверка, какой код вернёт запрос на указанный URL (проверка валидности)

    - validate_interactivity(selector):
        - Что делает: Вызывает isEditable(), isVisible() и isEnabled()
        - Зачем: Быстрая проверка, стоит ли вообще пытаться взаимодействовать с этим селектором.
    - smart_focus(selector):
        - Логика: Реализует цикл Click -> Wait(1s) -> Click.
        - Встроенная обработка ошибок: Если клик перехвачен (interception), процедура должна автоматически выполнить page.keyboard.press('Escape') и попробовать снова.
        - Если не получилось, то возвращаем подробную ошибку
    - human_like_input(selector, text):
        - Логика: Очистка поля -> Ввод через locator.pressSequentially(text, { delay: 100 }).
        - Зачем: Посимвольный ввод активирует скрипты валидации на сайте, которые «не видят» обычную вставку текста.
    - wait_for_navigation_or_content(old_url, timeout):
        - Ждёт изменения URL и прогрузку страницы
        - Либо если после таймаута html поменялось более чем на 20% (но считать от текстового содержания страниц, без учёта html тегов)
    - Поиск на текущей html странице по подстроке (вернёт максимум 5 вхождений +- 200 символов вокруг, также вернёт кол-во вхождений)
    - Найти и вернуть элемент по селектору (также max 5, + кол-во найденных. Можно запросить только кол-во)
    
"""









def _response_status(response: Response | None) -> int | None:
    """Удобный хелпер, чтобы не повторять проверку None."""
    return response.status if response is not None else None


@tool(
    name="page_restart",
    description="Перезагружает текущую страницу и возвращает код ответа",
    args=[
        {
            "name": "page",
            "type": "Page",
            "required": True,
            "description": "Экземпляр страницы Playwright"
        },
        {
            "name": "wait_until",
            "type": "str",
            "required": False,
            "description": "Событие завершения перезагрузки (load|domcontentloaded|networkidle)"
        },
        {
            "name": "timeout",
            "type": "int",
            "required": False,
            "description": "Таймаут операции в миллисекундах"
        }
    ],
    returns={
        "status": "ok|error",
        "code": "HTTP-код ответа или null",
        "url": "str",
        "error": "Описание ошибки, если она была"
    },
    example_args={"wait_until": "load", "timeout": 30000}
)
def page_restart(
    page: Page,
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout: int = 30_000,
) -> dict[str, str | int | None]:
    """
    Перезагружает текущую страницу.
    """
    try:
        response = page.reload(wait_until=wait_until, timeout=timeout)
        return {"status": "ok", "code": _response_status(response), "url": page.url, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "code": None, "url": page.url, "error": str(exc)}


@tool(
    name="goto_url",
    description="Открывает указанную страницу по URL и возвращает код ответа",
    args=[
        {
            "name": "page",
            "type": "Page",
            "required": True,
            "description": "Экземпляр страницы Playwright"
        },
        {
            "name": "url",
            "type": "str",
            "required": True,
            "description": "Адрес страницы для перехода"
        },
        {
            "name": "wait_until",
            "type": "str",
            "required": False,
            "description": "Событие завершения загрузки (load|domcontentloaded|networkidle)"
        },
        {
            "name": "timeout",
            "type": "int",
            "required": False,
            "description": "Таймаут операции в миллисекундах"
        }
    ],
    returns={
        "status": "ok|error",
        "code": "HTTP-код ответа или null",
        "url": "str",
        "error": "Описание ошибки, если она была"
    },
    example_args={"url": "https://example.com", "wait_until": "load", "timeout": 30000}
)
def goto_url(
    page: Page,
    url: str,
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout: int = 30_000,
) -> dict[str, str | int | None]:
    """
    Открывает указанную страницу по URL.
    """
    try:
        response = page.goto(url, wait_until=wait_until, timeout=timeout)
        return {"status": "ok", "code": _response_status(response), "url": page.url, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "code": None, "url": url, "error": str(exc)}


@tool(
    name="check_url_status",
    description="Проверяет, какой HTTP-код вернёт запрос по URL (без навигации)",
    args=[
        {
            "name": "page",
            "type": "Page",
            "required": True,
            "description": "Экземпляр страницы Playwright (используется request-контекст)"
        },
        {
            "name": "url",
            "type": "str",
            "required": True,
            "description": "Адрес, для которого нужно узнать код ответа"
        },
        {
            "name": "method",
            "type": "str",
            "required": False,
            "description": "HTTP-метод: GET или HEAD"
        },
        {
            "name": "timeout",
            "type": "int",
            "required": False,
            "description": "Таймаут запроса в миллисекундах"
        }
    ],
    returns={
        "status": "ok|error",
        "code": "HTTP-код ответа или null",
        "url": "str",
        "error": "Описание ошибки, если она была"
    },
    example_args={"url": "https://example.com", "method": "HEAD", "timeout": 10000}
)
def check_url_status(
    page: Page,
    url: str,
    method: Literal["GET", "HEAD"] = "GET",
    timeout: int = 10_000,
) -> dict[str, str | int | None]:
    """
    Выполняет запрос через API-контекст Playwright и возвращает HTTP-код.
    """
    try:
        method_upper = method.upper()
        request_ctx = page.context.request

        if method_upper == "HEAD":
            response = request_ctx.head(url, timeout=timeout)
        else:
            response = request_ctx.get(url, timeout=timeout)

        return {"status": "ok", "code": response.status, "url": url, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "code": None, "url": url, "error": str(exc)}


if __name__ == "__main__":
    # Небольшой пример использования
    # Важно: чтобы импорт работал корректно, добавляем ROOT_DIR в sys.path выше
    from playwright.browser_start import launch_browser, close_browser  # type: ignore  # noqa: E402

    pw, browser, page = launch_browser(headless=True)
    try:
        print("Проверяем статус без навигации:", check_url_status(page, "https://example.com"))
        print("Навигируемся на страницу:", goto_url(page, "https://example.com"))
        print("Перезагружаем страницу:", page_restart(page))
    finally:
        close_browser(pw, browser)