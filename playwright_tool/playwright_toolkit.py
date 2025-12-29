"""
Набор инструментов для агента, для взаимодействия внутри Playwright.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Literal
from difflib import SequenceMatcher
import re

from playwright.sync_api import Page, Response


# region Импорты
# Чтобы при запуске файла из этой папки были видны модули из корня проекта (addedFunc.py и др.)
### Потом убрать, что бы было нормально
from pathlib import Path
import sys
import os
import json
import copy
import traceback
import time
from typing import Any
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Подключение всех библиотек и функций
from import_all_libraries import *
from ChatGPT.OpenAI_ChatGPT import send_message_to_ChatGPT

from reasoning_agent.agent_tools import tool 
from playwright_tool.browser_start import launch_browser, close_browser 
from playwright_tool.shared_page import (
    set_shared_page,
    get_shared_page,
    record_playwright_action,
)



"""
Все реализованные здесь инструменты:

find_elements:          Ищет элементы по селектору. Возвращает их количество и до max_results элементов
    с текстом и inner_html.
search_in_page_html:    Ищет подстроку в HTML страницы. Возвращает до max_results сниппетов ±context символов.
wait_for_navigation_or_content: Ждёт смену URL или изменение текстового контента более чем на change_threshold.
press_key:              Нажимает переданную клавишу через page.keyboard.press.
press_enter:            Эмулирует нажатие клавиши Enter на текущей странице
human_like_input:       Очищает поле и вводит текст посимвольно через press_sequentially
smart_focus:            Цикл Click -> Wait(1s) -> Click с обработкой перехвата клика (Escape + повтор)
validate_interactivity: Быстрая проверка селектора: isEditable, isVisible, isEnabled
check_url_status:       Проверяет, какой HTTP-код вернёт запрос по URL (без навигации)
goto_url:               Открывает указанную страницу по URL и возвращает код ответа
page_restart:           Перезагружает текущую страницу и возвращает код ответа
get_current_url:        Возвращает текущий URL открытой страницы
wait_ms:                Ожидание указанное количество миллисекунд (по умолчанию 10 секунд)
scroll_to_bottom:       Прокручивает страницу к низу
scroll_to_top:          Прокручивает страницу к верху
scroll_to_selector:     Прокручивает страницу к элементу по селектору (к первому совпадению)
click_element:          Кликает по элементу с заданным селектором. По умолчанию — по первому, можно выбрать индекс.
extract_selector_data_from_cached_pages: Возвращает начения по одному селектору и набору ссылок

"""





def _response_status(response: Response | None) -> int | None:
    """Удобный хелпер, чтобы не повторять проверку None."""
    return response.status if response is not None else None


def _strip_html_to_text(html: str) -> str:
    """
    Грубое извлечение текстового содержимого без тегов/скриптов/стилей.
    Нужно для оценки изменения контента.
    """
    clean = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.I | re.S)
    clean = re.sub(r"<style.*?>.*?</style>", "", clean, flags=re.I | re.S)
    clean = re.sub(r"<[^>]+>", " ", clean)
    return " ".join(clean.split())


def _change_fraction(old_text: str, new_text: str) -> float:
    """
    Возвращает долю отличий: 0.0 — тексты идентичны, 1.0 — полностью разные.
    """
    if not old_text and not new_text:
        return 0.0
    similarity = SequenceMatcher(None, old_text, new_text).ratio()
    return max(0.0, 1 - similarity)


def _require_page_or_error(extra: dict[str, Any] | None = None) -> tuple[Page | None, dict[str, Any] | None]:
    """
    Возвращает сохранённую страницу или готовый словарь ошибки, если страница не установлена.
    """
    try:
        return get_shared_page(), None
    except Exception as exc:  # noqa: BLE001
        payload: dict[str, Any] = {"status": "error", "error": str(exc)}
        if extra:
            payload.update(extra)
        return None, payload


def _safe_page_content(page: Page, timeout_ms: int = 1_000, poll_ms: int = 100) -> str:
    """
    Безопасно получает HTML через page.content(), переживая краткие периоды навигации.

    Playwright может бросать:
      "Page.content: Unable to retrieve content because the page is navigating..."
    В этом случае делаем короткие ретраи до timeout_ms.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    last_exc: Exception | None = None

    while time.monotonic() < deadline:
        try:
            return page.content()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            msg = str(exc).lower()
            # Самая частая причина в реальном использовании: момент навигации/перерендера.
            if "page.content" in msg and "navigat" in msg:
                remaining = max(0, int((deadline - time.monotonic()) * 1000))
                # Пробуем дождаться хоть какого-то состояния, но не блокируемся надолго.
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=min(300, remaining))
                except Exception:
                    pass
                page.wait_for_timeout(min(poll_ms, max(1, remaining)))
                continue

            # Для прочих ошибок делаем один короткий ретрай; если ошибка стабильная — выйдем по таймауту.
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            page.wait_for_timeout(min(poll_ms, max(1, remaining)))

    # Если совсем не получилось за отведённое время — пробрасываем последнюю ошибку.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Failed to read page.content()")


# region page_restart
@tool(
    name="page_restart",
    description="Перезагружает текущую страницу и возвращает код ответа. Этот инструмент взаимодействует с текущей страницей открытой в Playwright",
    args=[
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
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout: int = 30_000,
) -> dict[str, str | int | None]:
    """
    Перезагружает текущую страницу.
    """
    args = {"wait_until": wait_until, "timeout": timeout}
    page, err = _require_page_or_error({"code": None, "url": None})
    if err:
        record_playwright_action("page_restart", args=args, result=err)
        return err
    try:
        response = page.reload(wait_until=wait_until, timeout=timeout)
        res = {"status": "ok", "code": _response_status(response), "url": page.url, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "code": None, "url": page.url, "error": str(exc)}
    record_playwright_action("page_restart", args=args, result=res)
    return res


# region goto_url
@tool(
    name="goto_url",
    description="Открывает указанную страницу по URL в текущей вкладке Playwright и возвращает код ответа",
    args=[
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
    url: str,
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "load",
    timeout: int = 30_000,
) -> dict[str, str | int | None]:
    """
    Открывает указанную страницу по URL.
    """
    args = {"url": url, "wait_until": wait_until, "timeout": timeout}
    page, err = _require_page_or_error({"code": None, "url": url})
    if err:
        record_playwright_action("goto_url", args=args, result=err)
        return err
    try:
        response = page.goto(url, wait_until=wait_until, timeout=timeout)
        res = {"status": "ok", "code": _response_status(response), "url": page.url, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "code": None, "url": url, "error": str(exc)}
    record_playwright_action("goto_url", args=args, result=res)
    return res


# region get_current_url
@tool(
    name="get_current_url",
    description="Возвращает текущий URL открытой страницы, открытой в Playwright",
    args=[
    ],
    returns={
        "status": "ok|error",
        "url": "str|null",
        "error": "Описание ошибки, если была"
    },
    example_args={},
)
def get_current_url() -> dict[str, str | None]:
    """
    Возвращает URL текущей страницы.
    """
    args: dict[str, Any] = {}
    page, err = _require_page_or_error({"url": None})
    if err:
        record_playwright_action("get_current_url", args=args, result=err)
        return err
    try:
        res = {"status": "ok", "url": page.url, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "url": None, "error": str(exc)}
    record_playwright_action("get_current_url", args=args, result=res)
    return res


# region wait_ms
@tool(
    name="wait_ms",
    description="Ожидание указанное количество миллисекунд (по умолчанию 10 секунд) на текущей странице, открытой в Playwright",
    args=[
        {
            "name": "ms",
            "type": "int",
            "required": False,
            "description": "Сколько миллисекунд ждать (по умолчанию 10000)"
        }
    ],
    returns={
        "status": "ok|error",
        "ms": "int|null",
        "error": "Описание ошибки, если была"
    },
    example_args={"ms": 10_000},
)
def wait_ms(ms: int = 10_000) -> dict[str, str | int | None]:
    """
    Ждёт указанное количество миллисекунд.
    """
    args: dict[str, Any] = {"ms": ms}
    page, err = _require_page_or_error({"ms": None})
    if err:
        record_playwright_action("wait_ms", args=args, result=err)
        return err
    try:
        if not isinstance(ms, int):
            raise TypeError("ms должен быть int")
        if ms < 0:
            raise ValueError("ms должен быть >= 0")
        page.wait_for_timeout(ms)
        res = {"status": "ok", "ms": ms, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "ms": None, "error": str(exc)}
    record_playwright_action("wait_ms", args=args, result=res)
    return res


# region check_url_status
@tool(
    name="check_url_status",
    description="Проверяет, какой HTTP-код вернёт запрос по URL (Выполняет запрос через API-контекст Playwright и возвращает HTTP-код). Этот метод не открывает страницу в активной вкладке Playwright, а только возвращает статус который вернётся при обращении на указанный URL",
    args=[
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
    url: str,
    method: Literal["GET", "HEAD"] = "GET",
    timeout: int = 10_000,
) -> dict[str, str | int | None]:
    """
    Выполняет запрос через API-контекст Playwright и возвращает HTTP-код.
    """
    args = {"url": url, "method": method, "timeout": timeout}
    page, err = _require_page_or_error({"code": None, "url": url})
    if err:
        record_playwright_action("check_url_status", args=args, result=err)
        return err
    try:
        method_upper = method.upper()
        request_ctx = page.context.request

        if method_upper == "HEAD":
            response = request_ctx.head(url, timeout=timeout)
        else:
            response = request_ctx.get(url, timeout=timeout)

        res = {"status": "ok", "code": response.status, "url": url, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "code": None, "url": url, "error": str(exc)}
    record_playwright_action("check_url_status", args=args, result=res)
    return res


# region validate_interactivity
@tool(
    name="validate_interactivity",
    description="Быстрая проверка селектора: isEditable, isVisible, isEnabled. На текущей странице открытой в Playwright",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS/XPath селектор элемента"
        }
    ],
    returns={
        "status": "ok|error",
        "selector": "str",
        "editable": "bool|null",
        "visible": "bool|null",
        "enabled": "bool|null",
        "error": "Описание ошибки, если была"
    },
    example_args={"selector": "input[name='q']"}
)
def validate_interactivity(selector: str) -> dict[str, str | bool | None]:
    """Вызывает isEditable(), isVisible() и isEnabled() для локатора."""
    args = {"selector": selector}
    page, err = _require_page_or_error(
        {
            "selector": selector,
            "editable": None,
            "visible": None,
            "enabled": None,
        }
    )
    if err:
        record_playwright_action("validate_interactivity", args=args, result=err)
        return err
    locator = page.locator(selector)
    try:
        editable = locator.is_editable()
        visible = locator.is_visible()
        enabled = locator.is_enabled()
        res = {
            "status": "ok",
            "selector": selector,
            "editable": editable,
            "visible": visible,
            "enabled": enabled,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        res = {
            "status": "error",
            "selector": selector,
            "editable": None,
            "visible": None,
            "enabled": None,
            "error": str(exc),
        }
    record_playwright_action("validate_interactivity", args=args, result=res)
    return res


# region smart_focus
@tool(
    name="smart_focus",
    description="Пытается сфокусироваться: Click -> Wait(timeout) -> Click. При перехвате клика нажимает Escape и повторяет попытку. На текущей странице открытой в Playwright",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS/XPath селектор элемента"
        },
        {
            "name": "timeout",
            "type": "int",
            "required": False,
            "description": "Таймаут ожиданий между действиями в миллисекундах"
        }
    ],
    returns={
        "status": "ok|error",
        "selector": "str",
        "attempts": "int",
        "error": "Описание ошибки, если была"
    },
    example_args={"selector": "input[name='q']", "timeout": 1000}
)
def smart_focus(selector: str, timeout: int = 1_000) -> dict[str, str | int | None]:
    """
    Пытается сфокусироваться: Click -> Wait(timeout) -> Click.
    При перехвате клика нажимает Escape и повторяет попытку.
    """
    args = {"selector": selector, "timeout": timeout}
    page, err = _require_page_or_error({"selector": selector, "attempts": 0})
    if err:
        record_playwright_action("smart_focus", args=args, result=err)
        return err
    locator = page.locator(selector)
    last_error: str | None = None

    for attempt in range(1, 3):  # максимум 2 попытки
        try:
            locator.click()
            page.wait_for_timeout(timeout)
            locator.click()
            res = {"status": "ok", "selector": selector, "attempts": attempt, "error": None}
            record_playwright_action("smart_focus", args=args, result=res)
            return res
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

    res = {"status": "error", "selector": selector, "attempts": 2, "error": last_error}
    record_playwright_action("smart_focus", args=args, result=res)
    return res


# region click_element
@tool(
    name="click_element",
    description="Кликает по элементу с заданным селектором. По умолчанию — по первому, можно выбрать индекс. На текущей странице открытой в Playwright",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS/XPath селектор элемента",
        },
        {
            "name": "element_index",
            "type": "int",
            "required": False,
            "description": "Номер элемента, если их несколько (0 — первый по умолчанию)",
        },
    ],
    returns={
        "status": "ok|error",
        "selector": "str",
        "element_index": "int",
        "total_count": "int|null",
        "error": "Описание ошибки, если была",
    },
    example_args={"selector": "button.submit", "element_index": 0},
)
def click_element(
    selector: str,
    element_index: int = 0,
) -> dict[str, str | int | None]:
    """
    Кликает по element_index-му элементу по селектору (0 — первый).
    """
    args = {"selector": selector, "index": element_index}
    page, err = _require_page_or_error(
        {"selector": selector, "element_index": element_index, "total_count": None}
    )
    if err:
        record_playwright_action("click_element", args=args, result=err)
        return err
    locator = page.locator(selector)
    try:
        count = locator.count()
        if count == 0:
            res = {
                "status": "error",
                "selector": selector,
                "element_index": element_index,
                "total_count": 0,
                "error": "Элементы по селектору не найдены",
            }
            record_playwright_action("click_element", args=args, result=res)
            return res

        if element_index < 0 or element_index >= count:
            res = {
                "status": "error",
                "selector": selector,
                "element_index": element_index,
                "total_count": count,
                "error": f"Индекс {element_index} вне диапазона [0, {count - 1}]",
            }
            record_playwright_action("click_element", args=args, result=res)
            return res

        locator.nth(element_index).click()
        res = {
            "status": "ok",
            "selector": selector,
            "element_index": element_index,
            "total_count": count,
            "error": None,
        }
        record_playwright_action("click_element", args=args, result=res)
        return res
    except Exception as exc:  # noqa: BLE001
        res = {
            "status": "error",
            "selector": selector,
            "element_index": element_index,
            "total_count": None,
            "error": str(exc),
        }
        record_playwright_action("click_element", args=args, result=res)
        return res


# region scroll_to_bottom
@tool(
    name="scroll_to_bottom",
    description="Прокручивает страницу к низу. На текущей странице открытой в Playwright",
    args=[],
    returns={
        "status": "ok|error",
        "position": "bottom",
        "error": "Описание ошибки, если была",
    },
    example_args={},
)
def scroll_to_bottom() -> dict[str, str | None]:
    """
    Прокрутка страницы к низу.
    """
    args: dict[str, Any] = {}
    page, err = _require_page_or_error({"position": "bottom"})
    if err:
        record_playwright_action("scroll_to_bottom", args=args, result=err)
        return err
    try:
        page.evaluate(
            """
            () => {
                const el = document.scrollingElement || document.documentElement || document.body;
                window.scrollTo(0, el.scrollHeight);
            }
            """
        )
        res = {"status": "ok", "position": "bottom", "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "position": "bottom", "error": str(exc)}
    record_playwright_action("scroll_to_bottom", args=args, result=res)
    return res


# region scroll_to_top
@tool(
    name="scroll_to_top",
    description="Прокручивает страницу к верху. На текущей странице открытой в Playwright",
    args=[],
    returns={
        "status": "ok|error",
        "position": "top",
        "error": "Описание ошибки, если была",
    },
    example_args={},
)
def scroll_to_top() -> dict[str, str | None]:
    """
    Прокрутка страницы к верху.
    """
    args: dict[str, Any] = {}
    page, err = _require_page_or_error({"position": "top"})
    if err:
        record_playwright_action("scroll_to_top", args=args, result=err)
        return err
    try:
        page.evaluate("() => window.scrollTo(0, 0)")
        res = {"status": "ok", "position": "top", "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "position": "top", "error": str(exc)}
    record_playwright_action("scroll_to_top", args=args, result=res)
    return res


# region scroll_to_selector
@tool(
    name="scroll_to_selector",
    description="Прокручивает страницу к элементу по селектору (к первому совпадению). На текущей странице открытой в Playwright",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS/XPath селектор элемента",
        }
    ],
    returns={
        "status": "ok|error",
        "selector": "str",
        "total_count": "int|null",
        "error": "Описание ошибки, если была",
    },
    example_args={"selector": "form button[type='submit']"},
)
def scroll_to_selector(selector: str) -> dict[str, str | int | None]:
    """
    Прокрутка к элементу по селектору (к первому совпадению).
    """
    args = {"selector": selector}
    page, err = _require_page_or_error({"selector": selector, "total_count": None})
    if err:
        record_playwright_action("scroll_to_selector", args=args, result=err)
        return err
    locator = page.locator(selector)
    try:
        count = locator.count()
        if count == 0:
            res = {
                "status": "error",
                "selector": selector,
                "total_count": 0,
                "error": "Элементы по селектору не найдены",
            }
        else:
            locator.first.scroll_into_view_if_needed()
            res = {"status": "ok", "selector": selector, "total_count": count, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "selector": selector, "total_count": None, "error": str(exc)}
    record_playwright_action("scroll_to_selector", args=args, result=res)
    return res


# region human_like_input
@tool(
    name="human_like_input",
    description="Очищает поле и вводит текст посимвольно используя press_sequentially, иммитируя человеческий ввод. На текущей странице открытой в Playwright",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS/XPath селектор поля ввода"
        },
        {
            "name": "text",
            "type": "str",
            "required": True,
            "description": "Текст для ввода"
        },
        {
            "name": "delay_ms",
            "type": "int",
            "required": False,
            "description": "Задержка между символами в миллисекундах"
        }
    ],
    returns={
        "status": "ok|error",
        "selector": "str",
        "text_len": "int",
        "error": "Описание ошибки, если была"
    },
    example_args={"selector": "input[name='q']", "text": "hello world", "delay_ms": 100}
)
def human_like_input(
    selector: str,
    text: str,
    delay_ms: int = 100,
) -> dict[str, str | int | None]:
    """
    Очистка поля -> посимвольный ввод через press_sequentially (активирует фронтовую валидацию).
    """
    args = {"selector": selector, "text": text, "delay_ms": delay_ms}
    page, err = _require_page_or_error({"selector": selector, "text_len": 0})
    if err:
        record_playwright_action("human_like_input", args=args, result=err)
        return err
    locator = page.locator(selector)
    try:
        locator.click()
        locator.fill("")  # очистка
        # press_sequentially доступен в Playwright Python (аналог JS pressSequentially)
        locator.press_sequentially(text, delay=delay_ms)
        res = {"status": "ok", "selector": selector, "text_len": len(text), "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "selector": selector, "text_len": 0, "error": str(exc)}
    record_playwright_action("human_like_input", args=args, result=res)
    return res


# region press_enter
@tool(
    name="press_enter",
    description="Эмулирует нажатие клавиши Enter на текущей странице открытой в Playwright",
    args=[
    ],
    returns={
        "status": "ok|error",
        "error": "Описание ошибки, если была",
    },
    example_args={},
)
def press_enter() -> dict[str, str | None]:
    """
    Простое нажатие Enter через page.keyboard.press.
    """
    args: dict[str, Any] = {}
    page, err = _require_page_or_error({})
    if err:
        record_playwright_action("press_enter", args=args, result=err)
        return err
    try:
        page.keyboard.press("Enter")
        res = {"status": "ok", "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "error": str(exc)}
    record_playwright_action("press_enter", args=args, result=res)
    return res


# region press_key
@tool(
    name="press_key",
    description="Эмулирует нажатие указанной клавиши на текущей странице открытой в Playwright",
    args=[
        {
            "name": "key",
            "type": "str",
            "required": True,
            "description": "Название клавиши в формате Playwright (например, 'Enter', 'Tab', 'ArrowDown')",
        },
    ],
    returns={
        "status": "ok|error",
        "pressed_key": "str|null",
        "error": "Описание ошибки, если была",
    },
    example_args={"key": "Enter"},
)
def press_key(key: str) -> dict[str, str | None]:
    """
    Нажимает переданную клавишу через page.keyboard.press.
    """
    args = {"key": key}
    page, err = _require_page_or_error({"pressed_key": None})
    if err:
        record_playwright_action("press_key", args=args, result=err)
        return err
    try:
        page.keyboard.press(key)
        res = {"status": "ok", "pressed_key": key, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "pressed_key": None, "error": str(exc)}
    record_playwright_action("press_key", args=args, result=res)
    return res


# region wait_for_navigation_or_content
@tool(
    name="wait_for_navigation_or_content",
    description="Ждёт смену URL или существенное изменение контента (>20% текста) за таймаут. На текущей вкладке Playwright",
    args=[
        {
            "name": "old_url",
            "type": "str",
            "required": True,
            "description": "URL, который считаем исходным"
        },
        {
            "name": "timeout",
            "type": "int",
            "required": False,
            "description": "Таймаут ожидания в миллисекундах"
        },
        {
            "name": "change_threshold",
            "type": "float",
            "required": False,
            "description": "Порог доли изменения текста (по умолчанию 0.2 = 20%)"
        }
    ],
    returns={
        "status": "ok|timeout|error",
        "reason": "url_changed|content_changed|no_change",
        "new_url": "str",
        "change_fraction": "float|null",
        "error": "Описание ошибки, если была"
    },
    example_args={"old_url": "https://example.com", "timeout": 15000, "change_threshold": 0.2}
)
def wait_for_navigation_or_content(
    old_url: str,
    timeout: int = 30_000,
    change_threshold: float = 0.2,
) -> dict[str, str | float | None]:
    """
    Ждёт смену URL или изменение текстового контента более чем на change_threshold.
    """
    args = {"old_url": old_url, "timeout": timeout, "change_threshold": change_threshold}
    page, err = _require_page_or_error(
        {
            "reason": "no_change",
            "new_url": None,
            "change_fraction": None,
        }
    )
    if err:
        record_playwright_action("wait_for_navigation_or_content", args=args, result=err)
        return err
    deadline = time.monotonic() + timeout / 1000
    start_text: str | None = None
    last_fraction: float | None = None

    try:
        while time.monotonic() < deadline:
            remaining = max(0, int((deadline - time.monotonic()) * 1000))

            if page.url != old_url:
                try:
                    page.wait_for_load_state("load", timeout=remaining)
                except Exception:
                    pass
                res = {
                    "status": "ok",
                    "reason": "url_changed",
                    "new_url": page.url,
                    "change_fraction": None,
                    "error": None,
                }
                record_playwright_action("wait_for_navigation_or_content", args=args, result=res)
                return res

            # Пытаемся зафиксировать baseline. Если страница в навигации — подождём и продолжим.
            if start_text is None:
                try:
                    html = _safe_page_content(page, timeout_ms=min(1_000, max(50, remaining)))
                    start_text = _strip_html_to_text(html)
                except Exception:
                    page.wait_for_timeout(200)
                    continue
            else:
                try:
                    html = _safe_page_content(page, timeout_ms=min(1_000, max(50, remaining)))
                    new_text = _strip_html_to_text(html)
                    fraction = _change_fraction(start_text, new_text)
                    last_fraction = fraction
                    if fraction > change_threshold:
                        res = {
                            "status": "ok",
                            "reason": "content_changed",
                            "new_url": page.url,
                            "change_fraction": round(fraction, 3),
                            "error": None,
                        }
                        record_playwright_action("wait_for_navigation_or_content", args=args, result=res)
                        return res
                except Exception:
                    # Если контент не удаётся прочитать (например, опять навигация) — просто ждём дальше.
                    pass

            page.wait_for_timeout(500)

        res = {
            "status": "timeout",
            "reason": "no_change",
            "new_url": page.url,
            "change_fraction": (round(last_fraction, 3) if last_fraction is not None else None),
            "error": None,
        }
        record_playwright_action("wait_for_navigation_or_content", args=args, result=res)
        return res
    except Exception as exc:  # noqa: BLE001
        res = {
            "status": "error",
            "reason": "no_change",
            "new_url": page.url,
            "change_fraction": None,
            "error": str(exc),
        }
        record_playwright_action("wait_for_navigation_or_content", args=args, result=res)
        return res


# region search_in_page_html
@tool(
    name="search_in_page_html",
    description="Ищет подстроку в текущем HTML страницы (до 5 вхождений, 200 символов контекста перед и после найденного элемента). На текущей странице открытой в Playwright",
    args=[
        {
            "name": "substring",
            "type": "str",
            "required": True,
            "description": "Подстрока для поиска"
        },
        {
            "name": "max_results",
            "type": "int",
            "required": False,
            "description": "Максимальное число сниппетов (по умолчанию 5)"
        },
        {
            "name": "context",
            "type": "int",
            "required": False,
            "description": "Длина контекста вокруг совпадения (по умолчанию 200 символов)"
        }
    ],
    returns={
        "status": "ok|error",
        "count": "int",
        "matches": "list[str]|null",
        "error": "Описание ошибки, если была"
    },
    example_args={"substring": "Example Domain", "max_results": 3, "context": 120}
)
def search_in_page_html(
    substring: str,
    max_results: int = 5,
    context: int = 200,
) -> dict[str, str | int | list[str] | None]:
    """
    Ищет подстроку в HTML страницы. Возвращает до max_results сниппетов ±context символов.
    """
    args = {"substring": substring, "max_results": max_results, "context": context}
    page, err = _require_page_or_error({"count": 0, "matches": None})
    if err:
        record_playwright_action("search_in_page_html", args=args, result=err)
        return err
    try:
        html = _safe_page_content(page, timeout_ms=2_000)
        haystack = html.lower()
        needle = substring.lower()

        matches: list[str] = []
        count = 0
        start = 0

        while True:
            idx = haystack.find(needle, start)
            if idx == -1:
                break
            count += 1
            if len(matches) < max_results:
                snippet_start = max(0, idx - context)
                snippet_end = min(len(html), idx + len(substring) + context)
                matches.append(html[snippet_start:snippet_end])
            start = idx + len(substring)

        res = {"status": "ok", "count": count, "matches": matches, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "count": 0, "matches": None, "error": str(exc)}
    record_playwright_action("search_in_page_html", args=args, result=res)
    return res


# region find_elements
@tool(
    name="find_elements",
    description="Возвращает элементы по селектору (max 5) и их количество. Можно запросить только count. Для каждого элемента возвращает inner_text/inner_html и все атрибуты (attrs).",
    args=[
        {
            "name": "selector",
            "type": "str",
            "required": True,
            "description": "CSS/XPath селектор"
        },
        {
            "name": "only_count",
            "type": "bool",
            "required": False,
            "description": "Если True — вернуть только количество без данных элементов"
        },
        {
            "name": "max_results",
            "type": "int",
            "required": False,
            "description": "Максимум элементов в выдаче (по умолчанию 5)"
        }
    ],
    returns={
        "status": "ok|error",
        "count": "int",
        "elements": "list[dict]|null",
        "error": "Описание ошибки, если была"
    },
    example_args={"selector": "a", "only_count": False, "max_results": 3}
)
def find_elements(
    selector: str,
    only_count: bool = False,
    max_results: int = 5,
) -> dict[str, str | int | list[dict[str, Any]] | None]:
    """
    Ищет элементы по селектору. Возвращает их количество и до max_results элементов
    с текстом и inner_html.
    """
    args = {"selector": selector, "only_count": only_count, "max_results": max_results}
    page, err = _require_page_or_error({"count": 0, "elements": None})
    if err:
        record_playwright_action("find_elements", args=args, result=err)
        return err
    locator = page.locator(selector)
    try:
        count = locator.count()
        elements: list[dict[str, Any]] | None = None

        if not only_count:
            elements = []
            for i in range(min(count, max_results)):
                el = locator.nth(i)
                try:
                    text = el.inner_text(timeout=1_000)
                except Exception:
                    text = None
                try:
                    html = el.inner_html(timeout=1_000)
                except Exception:
                    html = None
                try:
                    href = el.get_attribute("href", timeout=1_000)
                except Exception:
                    href = None
                # Все атрибуты элемента (включая data-*, aria-*, href, class, id, ...)
                try:
                    attrs = el.evaluate(
                        "e => Object.fromEntries(Array.from(e.attributes).map(a => [a.name, a.value]))",
                        timeout=1_000,
                    )
                except Exception:
                    attrs = None
                elements.append({"index": i, "text": text, "html": html, "href": href, "attrs": attrs})

        res = {"status": "ok", "count": count, "elements": elements, "error": None}
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "count": 0, "elements": None, "error": str(exc)}
    record_playwright_action("find_elements", args=args, result=res)
    return res


def _looks_like_xpath(selector: str) -> bool:
    s = (selector or "").strip()
    # Достаточно надёжные эвристики для XPath в реальных сценариях.
    return s.startswith(("/", "./", "../", ".//", "(.//", "//*[", "("))


def _extract_element_value(el: Any) -> str:
    """
    Универсально извлекает "значение" из элемента.

    Приоритет:
    - нормализованный text_content / get_text
    - value/content/href/src (если текст пустой)
    """
    text = ""
    try:
        # lxml element
        if hasattr(el, "text_content"):
            text = " ".join((el.text_content() or "").split())
    except Exception:
        text = ""

    if not text:
        try:
            # bs4 Tag
            if hasattr(el, "get_text"):
                text = " ".join((el.get_text(" ", strip=True) or "").split())
        except Exception:
            text = ""

    if text:
        return text

    # Fallback to common attrs
    for attr in ("value", "content", "href", "src"):
        try:
            if hasattr(el, "get") and callable(el.get):
                v = el.get(attr)
            else:
                v = None
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            continue

    return ""


# region extract_selector_data_from_cached_pages
@tool(
    name="extract_selector_data_from_cached_pages",
    description=(
        "Принимает CSS/XPath селектор и массив ссылок, берёт HTML каждой страницы "
        "и возвращает массив результатов: count найденных элементов, main_result/все результаты (до 30) и "
        "html_frame_main_result (get_html_frame для первого совпадения; строится только для CSS-селекторов)."
        "Данный инструмент не взаимодействует с браузером Playwright, а получает html страниц обычным запросом."
    ),
    args=[
        {"name": "selector", "type": "str", "required": True, "description": "CSS или XPath селектор"},
        {"name": "links", "type": "list[str]", "required": True, "description": "Ссылки на страницы"},
        {"name": "max_all_results", "type": "int", "required": False, "description": "Лимит для all_results (по умолчанию 30)"},
        {"name": "print_cache_msgs", "type": "bool", "required": False, "description": "Печатать сообщения cache (по умолчанию False)"},
    ],
    returns={
        "results": "list[dict]: [{link, used_selector, count_of_elements, main_result, all_results, html_frame_main_result}]"
    },
    example_args={
        "selector": ".price",
        "links": ["https://example.com/a", "https://example.com/b"],
        "max_all_results": 30,
        "print_cache_msgs": False,
    },
)
def extract_selector_data_from_cached_pages(
    selector: str,
    links: list[str],
    max_all_results: int = 30,
    print_cache_msgs: bool = False,
) -> list[dict[str, Any]]:
    # Поддержка playwight-like префиксов.
    raw_selector = selector
    sel = (selector or "").strip()
    sel_lower = sel.lower()
    if sel_lower.startswith("css="):
        selector = sel[4:].strip()
    elif sel_lower.startswith("xpath="):
        selector = sel[6:].strip()

    args = {
        "selector": selector,
        "raw_selector": raw_selector,
        "links_count": (len(links) if isinstance(links, list) else None),
        "max_all_results": max_all_results,
        "print_cache_msgs": print_cache_msgs,
    }

    results: list[dict[str, Any]] = []
    used_selector = selector
    is_xpath = _looks_like_xpath(selector)

    # Импортируем лениво, чтобы не тащить тяжёлые зависимости при старте.
    try:
        import lxml.html  # type: ignore

        lxml_available = True
    except Exception:
        lxml_available = False

    # get_html_frame нужен для html_frame_main_result (только CSS).
    get_html_frame_fn = None
    if not is_xpath:
        try:
            from new_program.html_toolkit import get_html_frame as _get_html_frame  # noqa: WPS433

            get_html_frame_fn = _get_html_frame
        except Exception:
            get_html_frame_fn = None

    for link in (links or []):
        item: dict[str, Any] = {
            "link": link,
            "used_selector": used_selector,
            "count_of_elements": 0,
            "main_result": None,
            "all_results": [],
            "html_frame_main_result": "",
        }

        try:
            html = get_html_from_cache(link, print_msg=print_cache_msgs)
        except Exception:  # noqa: BLE001
            # Формат результата без поля error — оставляем значения по умолчанию.
            results.append(item)
            continue

        if not html:
            results.append(item)
            continue

        try:
            if lxml_available:
                doc = lxml.html.fromstring(html)  # type: ignore[attr-defined]
                if is_xpath:
                    found = doc.xpath(selector)
                else:
                    found = doc.cssselect(selector)

                # Оставляем только элементы (на XPath могут вернуться строки/атрибуты/числа)
                elements = [x for x in found if hasattr(x, "tag")]
            else:
                # Fallback: BeautifulSoup поддерживает только CSS.
                if is_xpath:
                    elements = []
                else:
                    from bs4 import BeautifulSoup  # noqa: WPS433

                    soup = BeautifulSoup(html, "html.parser")
                    elements = soup.select(selector) or []

            item["count_of_elements"] = len(elements)

            limit = 30 if max_all_results is None else int(max_all_results)
            limit = max(0, min(30, limit))

            all_vals: list[str] = []
            for el in elements[:limit]:
                all_vals.append(_extract_element_value(el))

            item["all_results"] = all_vals
            item["main_result"] = (all_vals[0] if all_vals else None)

            if item["count_of_elements"] > 0 and (get_html_frame_fn is not None):
                try:
                    item["html_frame_main_result"] = get_html_frame_fn(html=html, selector=selector) or ""
                except Exception:
                    item["html_frame_main_result"] = ""

        except Exception:  # noqa: BLE001
            # Без поля error — оставляем дефолты, но сохраняем link/selector.
            item["count_of_elements"] = 0
            item["main_result"] = None
            item["all_results"] = []
            item["html_frame_main_result"] = ""

        results.append(item)

    # # Логируем как действие (для единообразия), хотя Playwright page тут не используется.
    # try:
    #     record_playwright_action("extract_selector_data_from_cached_pages", args=args, result={"count": len(results)})
    # except Exception:
    #     pass

    return results









# region search_in_page_network_requests
@tool(
    name="search_in_page_network_requests",
    description=(
        "Ищет подстроку по всем сетевым запросам (request/response), которые были выполнены "
        "на текущей странице Playwright с момента последней перезагрузки/навигации (top-level document). "
        "Ищет вхождения подстроки в URL/методе/параметрах/заголовках/теле запроса и в ответе."
    ),
    args=[
        {
            "name": "substring",
            "type": "str",
            "required": True,
            "description": "Подстрока для поиска по истории запросов",
        },
        {
            "name": "max_results",
            "type": "int",
            "required": False,
            "description": "Максимум результатов (всё равно будет ограничено 5)",
        },
        {
            "name": "response_head_chars",
            "type": "int",
            "required": False,
            "description": "Сколько символов брать с начала body ответа (по умолчанию 300)",
        },
        {
            "name": "response_tail_chars",
            "type": "int",
            "required": False,
            "description": "Сколько символов брать с конца body ответа (по умолчанию 100)",
        },
        {
            "name": "response_match_context_chars",
            "type": "int",
            "required": False,
            "description": (
                "Если подстрока найдена в body ответа и находится в середине (не попадает в head/tail), "
                "то добавляем окно вокруг вхождения: N символов до и N символов после (по умолчанию 200)"
            ),
        },
        {
            "name": "case_sensitive",
            "type": "bool",
            "required": False,
            "description": "Искать с учётом регистра (по умолчанию False)",
        },
    ],
    returns={
        "status": "ok|error",
        "count": "int",
        "results": "array[json]",
        "scanned": "int",
        "error": "str|null",
    },
    example_args={
        "substring": "diginetica",
        "max_results": 5,
        "response_head_chars": 300,
        "response_tail_chars": 100,
        "response_match_context_chars": 200,
        "case_sensitive": False,
    },
)
def search_in_page_network_requests(
    substring: str,
    max_results: int = 5,
    response_head_chars: int = 300,
    response_tail_chars: int = 100,
    response_match_context_chars: int = 200,
    case_sensitive: bool = False,
) -> dict[str, Any]:
    """
    Возвращает первые совпадения по истории сетевых запросов со страницы (с момента последнего reload/навигации).

    Важно: для ответа возвращается усечённый body (head+tail), границы задаются параметрами.
    """
    args = {
        "substring": substring,
        "max_results": max_results,
        "response_head_chars": response_head_chars,
        "response_tail_chars": response_tail_chars,
        "response_match_context_chars": response_match_context_chars,
        "case_sensitive": case_sensitive,
    }

    page, err = _require_page_or_error({"count": 0, "results": None, "scanned": 0})
    if err:
        record_playwright_action("search_in_page_network_requests", args=args, result=err)
        return err

    # Импортируем лениво, чтобы избежать циклических импортов на старте.
    from playwright_tool.shared_page import get_network_requests_since_load  # noqa: WPS433

    try:
        entries = get_network_requests_since_load()
    except Exception as exc:  # noqa: BLE001
        res = {"status": "error", "count": 0, "results": None, "scanned": 0, "error": str(exc)}
        record_playwright_action("search_in_page_network_requests", args=args, result=res)
        return res

    try:
        limit = int(max_results)
    except Exception:
        limit = 5
    limit = max(0, min(5, limit))

    try:
        head_n = int(response_head_chars)
    except Exception:
        head_n = 300
    try:
        tail_n = int(response_tail_chars)
    except Exception:
        tail_n = 100
    try:
        ctx_n = int(response_match_context_chars)
    except Exception:
        ctx_n = 200
    head_n = max(0, head_n)
    tail_n = max(0, tail_n)
    ctx_n = max(0, ctx_n)

    needle = substring if case_sensitive else substring.lower()

    def _to_text(obj: Any) -> str:
        try:
            return json.dumps(obj, ensure_ascii=False, default=str)
        except Exception:
            try:
                return str(obj)
            except Exception:
                return ""

    def _trim_body(text: str | None, *, needle_raw: str) -> tuple[str | None, dict[str, Any]]:
        if text is None:
            return None, {"mode": "none"}
        if not isinstance(text, str):
            try:
                text = str(text)
            except Exception:
                return None, {"mode": "none"}
        if head_n == 0 and tail_n == 0:
            return "", {"mode": "head_tail", "match_in_body": False}

        n = len(text)
        if n <= head_n + tail_n:
            return text, {"mode": "full", "match_in_body": (needle_raw != "" and (needle_raw in (text if case_sensitive else text.lower())))}

        # Ищем подстроку внутри body (если задана)
        match_idx = -1
        if needle_raw:
            try:
                hay_for_match = text if case_sensitive else text.lower()
                ndl_for_match = needle_raw if case_sensitive else needle_raw.lower()
                match_idx = hay_for_match.find(ndl_for_match)
            except Exception:
                match_idx = -1

        # Базовый вариант: только head/tail
        head_part = text[:head_n] if head_n > 0 else ""
        tail_part = text[-tail_n:] if tail_n > 0 else ""

        if match_idx < 0 or ctx_n == 0 or not needle_raw:
            return f"{head_part}\n...<trimmed>...\n{tail_part}", {"mode": "head_tail", "match_in_body": False}

        match_end = match_idx + len(needle_raw)
        tail_start = max(0, n - tail_n)
        in_head = match_end <= head_n
        in_tail = match_idx >= tail_start

        # Если совпадение уже попадает в head или tail — дополнительных вставок не нужно
        if in_head or in_tail:
            return f"{head_part}\n...<trimmed>...\n{tail_part}", {"mode": "head_tail", "match_in_body": True, "match_index": match_idx}

        # Совпадение "в середине" — вставляем контекстное окно вокруг него
        ctx_start = max(0, match_idx - ctx_n)
        ctx_end = min(n, match_end + ctx_n)
        mid_part = text[ctx_start:ctx_end]

        return (
            f"{head_part}\n...<trimmed>...\n{mid_part}\n...<trimmed>...\n{tail_part}",
            {"mode": "head_mid_tail", "match_in_body": True, "match_index": match_idx, "context_chars": ctx_n, "context_range": [ctx_start, ctx_end]},
        )

    results: list[dict[str, Any]] = []
    scanned = 0

    for entry in entries:
        scanned += 1
        hay = _to_text(entry)
        if not case_sensitive:
            hay = hay.lower()

        if needle and (needle not in hay):
            continue

        def _json_safe(obj: Any, _depth: int = 0) -> Any:
            # Защита от странных объектов Playwright/asyncio в логах: всё приводим к JSON-friendly структуре.
            if _depth > 20:
                return str(obj)
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return obj
            if isinstance(obj, dict):
                out_d: dict[str, Any] = {}
                for k, v in obj.items():
                    try:
                        key = k if isinstance(k, str) else str(k)
                    except Exception:
                        key = "key"
                    out_d[key] = _json_safe(v, _depth + 1)
                return out_d
            if isinstance(obj, (list, tuple)):
                return [_json_safe(x, _depth + 1) for x in obj]
            try:
                return str(obj)
            except Exception:
                return "<unserializable>"

        out = _json_safe(entry) if isinstance(entry, dict) else {"value": _json_safe(entry)}

        # Усечение body ответа в выдаче
        try:
            resp = out.get("response") if isinstance(out, dict) else None
            if isinstance(resp, dict) and ("body_text" in resp):
                original = resp.get("body_text")
                if isinstance(original, str):
                    resp["body_len"] = len(original)
                trimmed, meta = _trim_body(original if isinstance(original, str) else None, needle_raw=substring)
                resp["body_text"] = trimmed
                resp["body_preview"] = {"head_chars": head_n, "tail_chars": tail_n, "match_context_chars": ctx_n, **meta}
        except Exception:
            pass

        results.append(out)
        if len(results) >= limit:
            break

    res = {
        "status": "ok",
        "count": len(results),
        "results": results,
        "scanned": scanned,
        "error": None,
        "page_url": getattr(page, "url", None),
    }
    record_playwright_action("search_in_page_network_requests", args=args, result={"count": len(results)})
    return res


if __name__ == "__main__":
    # Запускаю браузер с видимым окном
    launch_browser(headless = False)

    goto_url( 
        url = "https://apelsin.ru/?digiSearch=true&term=плитка&params=%7Csort%3DDEFAULT",
        wait_until = "load",
        timeout = 30_000
    )

    wait_ms(5000)

    result = search_in_page_network_requests("Плитка базовая CERSANIT Mont blanc Белый 29,7*59,8 см")
    print_json(result)










###### Надо установить страницу 1 раз через
# set_shared_page(page)
# Иначе инструменты вернут ошибку



# if __name__ == "__main__":
#     # Небольшой пример использования

#     pw, browser, page = launch_browser(headless = False)
#     try:
#         print("Проверяем статус без навигации:", check_url_status(page, "https://makitaclub.ru/"))
#         print("Навигируемся на страницу:", goto_url(page, "https://makitaclub.ru/"))

#         time.sleep(5)
#         print("Ищем 'makita' в html:", search_in_page_html(page, "makita"))
#         time.sleep(5)
#         print("Ищем ссылки на странице:", find_elements(page, "a", max_results=3))

#         time.sleep(5)
#         print("Smart focus для первого input:", smart_focus(page, "#woocommerce-product-search-field-0"))

#         time.sleep(5)
#         print("Проверяем интерактивность body:", validate_interactivity(page, "#woocommerce-product-search-field-0"))
        
#         time.sleep(5)
#         print("Human-like input:", human_like_input(page, "#woocommerce-product-search-field-0", "инструмент", delay_ms=80))
#         time.sleep(5)

#         # Нажать Enter
#         old_url = page.url
#         print("Нажимаем Enter:", press_enter(page))
#         # print("Нажимаем Tab через универсальную функцию:", press_key(page, "Tab"))

#         print("Ожидаем изменение URL или контента:", wait_for_navigation_or_content(page, old_url, timeout=5000))
#         # print("Перезагружаем страницу:", page_restart(page))
#         time.sleep(5)
#     finally:
#         close_browser(pw, browser)




# # Запускаю браузер с видимым окном
# launch_browser(headless = False)

# goto_url( 
#     url = "https://makitaclub.ru/?s=%D0%B8%D0%BD%D1%81%D1%82%D1%80%D1%83%D0%BC%D0%B5%D0%BD%D1%82&post_type=product",
#     wait_until = "load",
#     timeout = 30_000
# )

# print(find_elements(".products .product-card a.stretched-link[href*='/products/']", False, 5))

