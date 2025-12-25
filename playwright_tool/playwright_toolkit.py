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
from playwright_tool.shared_page import set_shared_page, get_shared_page






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
    - Функция, которая нажимает Enter
    - Функция, через которую можно нажать любую клавишу
"""




"""

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
click_element:          Кликает по элементу с заданным селектором. По умолчанию — по первому, можно выбрать индекс.

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


@tool(
    name="page_restart",
    description="Перезагружает текущую страницу и возвращает код ответа",
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
    page, err = _require_page_or_error({"code": None, "url": None})
    if err:
        return err
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
    page, err = _require_page_or_error({"code": None, "url": url})
    if err:
        return err
    try:
        response = page.goto(url, wait_until=wait_until, timeout=timeout)
        return {"status": "ok", "code": _response_status(response), "url": page.url, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "code": None, "url": url, "error": str(exc)}


@tool(
    name="get_current_url",
    description="Возвращает текущий URL открытой страницы",
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
    page, err = _require_page_or_error({"url": None})
    if err:
        return err
    try:
        return {"status": "ok", "url": page.url, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "url": None, "error": str(exc)}


@tool(
    name="check_url_status",
    description="Проверяет, какой HTTP-код вернёт запрос по URL (Выполняет запрос через API-контекст Playwright и возвращает HTTP-код)",
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
    page, err = _require_page_or_error({"code": None, "url": url})
    if err:
        return err
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


@tool(
    name="validate_interactivity",
    description="Быстрая проверка селектора: isEditable, isVisible, isEnabled",
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
    page, err = _require_page_or_error(
        {
            "selector": selector,
            "editable": None,
            "visible": None,
            "enabled": None,
        }
    )
    if err:
        return err
    locator = page.locator(selector)
    try:
        editable = locator.is_editable()
        visible = locator.is_visible()
        enabled = locator.is_enabled()
        return {
            "status": "ok",
            "selector": selector,
            "editable": editable,
            "visible": visible,
            "enabled": enabled,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "selector": selector,
            "editable": None,
            "visible": None,
            "enabled": None,
            "error": str(exc),
        }


@tool(
    name="smart_focus",
    description="Пытается сфокусироваться: Click -> Wait(timeout) -> Click. При перехвате клика нажимает Escape и повторяет попытку.",
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
    page, err = _require_page_or_error({"selector": selector, "attempts": 0})
    if err:
        return err
    locator = page.locator(selector)
    last_error: str | None = None

    for attempt in range(1, 3):  # максимум 2 попытки
        try:
            locator.click()
            page.wait_for_timeout(timeout)
            locator.click()
            return {"status": "ok", "selector": selector, "attempts": attempt, "error": None}
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

    return {"status": "error", "selector": selector, "attempts": 2, "error": last_error}


@tool(
    name="click_element",
    description="Кликает по элементу с заданным селектором. По умолчанию — по первому, можно выбрать индекс.",
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
    page, err = _require_page_or_error(
        {"selector": selector, "element_index": element_index, "total_count": None}
    )
    if err:
        return err
    locator = page.locator(selector)
    try:
        count = locator.count()
        if count == 0:
            return {
                "status": "error",
                "selector": selector,
                "element_index": element_index,
                "total_count": 0,
                "error": "Элементы по селектору не найдены",
            }

        if element_index < 0 or element_index >= count:
            return {
                "status": "error",
                "selector": selector,
                "element_index": element_index,
                "total_count": count,
                "error": f"Индекс {element_index} вне диапазона [0, {count - 1}]",
            }

        locator.nth(element_index).click()
        return {
            "status": "ok",
            "selector": selector,
            "element_index": element_index,
            "total_count": count,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "selector": selector,
            "element_index": element_index,
            "total_count": None,
            "error": str(exc),
        }


@tool(
    name="human_like_input",
    description="Очищает поле и вводит текст посимвольно используя press_sequentially, иммитируя человеческий ввод",
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
    page, err = _require_page_or_error({"selector": selector, "text_len": 0})
    if err:
        return err
    locator = page.locator(selector)
    try:
        locator.click()
        locator.fill("")  # очистка
        # press_sequentially доступен в Playwright Python (аналог JS pressSequentially)
        locator.press_sequentially(text, delay=delay_ms)
        return {"status": "ok", "selector": selector, "text_len": len(text), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "selector": selector, "text_len": 0, "error": str(exc)}


@tool(
    name="press_enter",
    description="Эмулирует нажатие клавиши Enter на текущей странице",
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
    page, err = _require_page_or_error({})
    if err:
        return err
    try:
        page.keyboard.press("Enter")
        return {"status": "ok", "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)}


@tool(
    name="press_key",
    description="Эмулирует нажатие указанной клавиши на текущей странице",
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
    page, err = _require_page_or_error({"pressed_key": None})
    if err:
        return err
    try:
        page.keyboard.press(key)
        return {"status": "ok", "pressed_key": key, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "pressed_key": None, "error": str(exc)}


@tool(
    name="wait_for_navigation_or_content",
    description="Ждёт смену URL или существенное изменение контента (>20% текста) за таймаут",
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
    page, err = _require_page_or_error(
        {
            "reason": "no_change",
            "new_url": None,
            "change_fraction": None,
        }
    )
    if err:
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
                return {
                    "status": "ok",
                    "reason": "url_changed",
                    "new_url": page.url,
                    "change_fraction": None,
                    "error": None,
                }

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
                        return {
                            "status": "ok",
                            "reason": "content_changed",
                            "new_url": page.url,
                            "change_fraction": round(fraction, 3),
                            "error": None,
                        }
                except Exception:
                    # Если контент не удаётся прочитать (например, опять навигация) — просто ждём дальше.
                    pass

            page.wait_for_timeout(500)

        return {
            "status": "timeout",
            "reason": "no_change",
            "new_url": page.url,
            "change_fraction": (round(last_fraction, 3) if last_fraction is not None else None),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "reason": "no_change",
            "new_url": page.url,
            "change_fraction": None,
            "error": str(exc),
        }


@tool(
    name="search_in_page_html",
    description="Ищет подстроку в текущем HTML страницы (до 5 вхождений, 200 символов контекста перед и после найденного элемента)",
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
    page, err = _require_page_or_error({"count": 0, "matches": None})
    if err:
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

        return {"status": "ok", "count": count, "matches": matches, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "count": 0, "matches": None, "error": str(exc)}


@tool(
    name="find_elements",
    description="Возвращает элементы по селектору (max 5) и их количество. Можно запросить только count.",
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
    page, err = _require_page_or_error({"count": 0, "elements": None})
    if err:
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
                elements.append({"index": i, "text": text, "html": html})

        return {"status": "ok", "count": count, "elements": elements, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "count": 0, "elements": None, "error": str(exc)}





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