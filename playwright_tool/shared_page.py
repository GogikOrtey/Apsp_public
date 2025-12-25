"""Shared Playwright page holder to avoid circular imports.

Также хранит компактный runtime-стейт для reasoning-агента:
- текущий URL и HTTP status (по ответам document)
- последнее "изменение страницы" (navigation/dom_update/none)
- история действий агента в браузере (короткий список)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Literal

from playwright.sync_api import Page, Response

_current_page: Page | None = None
_listeners_page: Page | None = None


def set_shared_page(page: Page) -> None:
    """Store Playwright page for reuse across toolkit helpers."""
    global _current_page
    _current_page = page
    _ensure_listeners(page)


def get_shared_page() -> Page:
    """Return stored Playwright page or raise if it is not set."""
    if _current_page is None:
        raise RuntimeError(
            "Playwright page is not initialized. Call set_shared_page(page) before using toolkit tools."
        )
    return _current_page


ChangeType = Literal["navigation", "dom_update", "none"]


@dataclass
class PlaywrightLastChange:
    type: ChangeType = "none"
    trigger: str | None = None
    delta_text: str | None = None  # например "18%"
    reason: str | None = None      # например "url_changed|content_changed|no_change"
    ts: float = field(default_factory=lambda: time.time())


@dataclass
class PlaywrightContextState:
    current_url: str | None = None
    http_status: int | None = None
    actions_since_load: list[str] = field(default_factory=list)
    last_change: PlaywrightLastChange = field(default_factory=PlaywrightLastChange)
    _last_trigger_candidate: str | None = None
    _last_document_url: str | None = None
    _last_document_ts: float | None = None


_state = PlaywrightContextState()


def reset_playwright_context_state() -> None:
    """Сбрасывает историю действий и last_change (полезно для тестов/перезапусков)."""
    global _state
    _state = PlaywrightContextState()


def _format_action_call(action: str, args: dict[str, Any] | None) -> str:
    if not args:
        return f"{action}()"

    # Чуть более "человечный" формат, похожий на пример в промпте.
    key_order_by_action: dict[str, list[str]] = {
        "smart_focus": ["selector"],
        "validate_interactivity": ["selector"],
        "click_element": ["selector", "index"],
        "human_like_input": ["selector", "text"],
        "press_key": ["key"],
        "goto_url": ["url"],
        "check_url_status": ["url"],
        "wait_for_navigation_or_content": ["old_url"],
        "search_in_page_html": ["substring"],
        "find_elements": ["selector"],
        "get_current_url": [],
        "press_enter": [],
        "page_restart": [],
    }

    ordered_keys = key_order_by_action.get(action)
    if ordered_keys is None:
        # Fallback: стабильный порядок ключей
        ordered_keys = sorted(args.keys())

    vals: list[str] = []
    for k in ordered_keys:
        if k not in args:
            continue
        v = args.get(k)
        if isinstance(v, str):
            vals.append(json_escape(v))
        else:
            vals.append(str(v))

    # Если ключей нет (например, get_current_url) — всё равно печатаем ()
    return f"{action}({', '.join(vals)})" if vals else f"{action}()"


def json_escape(s: str) -> str:
    # Минимальная "экранизация" как в JSON-строке, но без зависимости от json.dumps в каждом месте.
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def record_playwright_action(
    action: str,
    *,
    args: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    max_actions: int = 50,
) -> None:
    """
    Записывает действие агента в state.

    Важно: это чисто диагностическая/контекстная история для промпта, не для персистентного логирования.
    """
    # История
    call = _format_action_call(action, args)
    _state.actions_since_load.append(call)
    if len(_state.actions_since_load) > max_actions:
        _state.actions_since_load = _state.actions_since_load[-max_actions:]

    # Кандидат на trigger для последующего wait_for_navigation_or_content
    interactive = {
        "click_element",
        "press_key",
        "press_enter",
        "human_like_input",
        "smart_focus",
        "goto_url",
        "page_restart",
    }
    if action in interactive:
        _state._last_trigger_candidate = call

    # last_change: выставляем на wait_for_navigation_or_content (или сразу на явную навигацию)
    if action in {"goto_url", "page_restart"}:
        _state.last_change = PlaywrightLastChange(
            type="navigation",
            trigger=call,
            delta_text=None,
            reason="navigation",
        )

    if action == "wait_for_navigation_or_content" and isinstance(result, dict):
        status = result.get("status")
        reason = result.get("reason")
        change_fraction = result.get("change_fraction")

        if status == "ok" and reason == "url_changed":
            change_type: ChangeType = "navigation"
            delta_text = None
        elif status == "ok" and reason == "content_changed":
            change_type = "dom_update"
            if isinstance(change_fraction, (int, float)):
                delta_text = f"{int(round(float(change_fraction) * 100))}%"
            else:
                delta_text = None
        else:
            change_type = "none"
            if isinstance(change_fraction, (int, float)):
                delta_text = f"{int(round(float(change_fraction) * 100))}%"
            else:
                delta_text = None

        trigger = _state._last_trigger_candidate or "unknown"
        _state.last_change = PlaywrightLastChange(
            type=change_type,
            trigger=trigger,
            delta_text=delta_text,
            reason=str(reason) if reason is not None else None,
        )


def get_playwright_context_snapshot(*, max_actions: int = 10) -> dict[str, Any]:
    """Возвращает снапшот state в простом dict-формате (удобно для промптов)."""
    actions = _state.actions_since_load[-max_actions:] if max_actions > 0 else []
    return {
        "current_url": _state.current_url,
        "http_status": _state.http_status,
        "last_change": {
            "type": _state.last_change.type,
            "trigger": _state.last_change.trigger,
            "delta_text": _state.last_change.delta_text,
            "reason": _state.last_change.reason,
            "ts": _state.last_change.ts,
        },
        "actions_since_load": actions,
    }


def _ensure_listeners(page: Page) -> None:
    global _listeners_page
    # Если page уже та же самая — не вешаем второй раз.
    if _listeners_page is page:
        return

    def _on_response(resp: Response) -> None:
        try:
            req = resp.request
            # Интересуют только document-ответы главного фрейма (top-level навигации).
            if req.resource_type != "document":
                return
            if req.frame != page.main_frame:
                return

            url = resp.url
            status = resp.status

            # Если это действительно новый документ (URL изменился) — сбрасываем историю "since load".
            if _state._last_document_url is None or url != _state._last_document_url:
                _state.actions_since_load = []
                _state._last_trigger_candidate = None
                _state._last_document_url = url

            _state._last_document_ts = time.time()
            _state.current_url = url
            _state.http_status = status
        except Exception:
            # Контекстный лог — не должен ломать работу.
            return

    page.on("response", _on_response)
    _listeners_page = page

