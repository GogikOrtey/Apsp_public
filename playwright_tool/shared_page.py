"""Shared Playwright page holder to avoid circular imports.

Также хранит компактный runtime-стейт для reasoning-агента:
- текущий URL и HTTP status (по ответам document)
- последнее "изменение страницы" (navigation/dom_update/none)
- история действий агента в браузере (короткий список)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
import threading
from typing import Any, Literal

from playwright.sync_api import Page, Response, Request
from urllib.parse import urlparse, parse_qs
import copy

_current_page: Page | None = None
_listeners_page: Page | None = None

_network_records_since_load: list[dict[str, Any]] = []
_network_req_map_since_load: dict[int, dict[str, Any]] = {}
_NETWORK_MAX_RECORDS: int = 2000
_NETWORK_BODY_STORE_LIMIT: int = 1_000_000  # символов текста (best-effort), чтобы не раздувать память

# Screenshot cache (for UI preview)
_screenshot_lock = threading.Lock()
_last_screenshot_png: bytes | None = None
_last_screenshot_ts: float | None = None
_last_screenshot_error: str | None = None

# Background pusher: pushes screenshots to Flask when Playwright and Flask are in different processes.
_screenshot_pusher_lock = threading.Lock()
_screenshot_pusher_started = False


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


def get_cached_screenshot_png(
    *,
    min_interval_ms: int = 800,
    timeout_ms: int = 2_000,
    full_page: bool = False,
) -> tuple[bytes | None, dict[str, Any]]:
    """
    Возвращает PNG-скриншот текущей shared_page.

    - Кэширует последний удачный скриншот в памяти.
    - Не делает новый скриншот чаще, чем раз в min_interval_ms.
    - Если в момент вызова Playwright кидает исключение (например, навигация) —
      вернёт предыдущий скриншот (если он есть) + метаданные с ошибкой.

    Returns:
        (png_bytes, meta)
        meta: {ok, ts, age_ms, from_cache, error}
    """
    global _last_screenshot_png, _last_screenshot_ts, _last_screenshot_error

    now = time.time()
    with _screenshot_lock:
        age_ms: int | None = None
        if _last_screenshot_ts is not None:
            age_ms = int(max(0.0, (now - _last_screenshot_ts) * 1000))

        # Fresh enough -> return cache
        if _last_screenshot_png is not None and age_ms is not None and age_ms < int(min_interval_ms):
            return _last_screenshot_png, {
                "ok": True,
                "ts": _last_screenshot_ts,
                "age_ms": age_ms,
                "from_cache": True,
                "error": None,
            }

        # Need a refresh
        try:
            page = get_shared_page()
            png = page.screenshot(type="png", timeout=int(timeout_ms), full_page=bool(full_page))
            if not isinstance(png, (bytes, bytearray)):
                raise TypeError("page.screenshot() returned non-bytes")
            _last_screenshot_png = bytes(png)
            _last_screenshot_ts = time.time()
            _last_screenshot_error = None
            return _last_screenshot_png, {
                "ok": True,
                "ts": _last_screenshot_ts,
                "age_ms": 0,
                "from_cache": False,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            _last_screenshot_error = str(exc)
            # Fallback to previous screenshot if any
            if _last_screenshot_png is not None and _last_screenshot_ts is not None:
                fallback_age_ms = int(max(0.0, (now - _last_screenshot_ts) * 1000))
                return _last_screenshot_png, {
                    "ok": True,
                    "ts": _last_screenshot_ts,
                    "age_ms": fallback_age_ms,
                    "from_cache": True,
                    "error": _last_screenshot_error,
                }
            return None, {"ok": False, "ts": None, "age_ms": None, "from_cache": False, "error": _last_screenshot_error}


def start_screenshot_pusher_to_front(*, interval_s: float = 5.0) -> None:
    """
    Запускает daemon-поток, который периодически пушит скриншоты в Flask на
    /api/browser_screenshot_push.

    Зачем: когда Playwright и Flask живут в разных процессах, shared_page не разделяется,
    и единственный простой мост — отправлять PNG по HTTP.

    Важно: если Flask не запущен — поток будет "тихо" ждать и почти ничего не делать.
    """
    global _screenshot_pusher_started
    with _screenshot_pusher_lock:
        if _screenshot_pusher_started:
            return
        _screenshot_pusher_started = True

    def _runner() -> None:
        # Ленивые импорты: чтобы shared_page.py не тащил сеть при обычном использовании.
        from front_client import DEFAULT_FRONT_BASE_URL, push_browser_screenshot_png  # noqa: WPS433

        # Простейшая проверка, что Flask жив: дергаем существующий GET endpoint.
        import urllib.request  # noqa: WPS433
        import urllib.error  # noqa: WPS433

        base_url = DEFAULT_FRONT_BASE_URL.rstrip("/")
        ping_url = base_url + "/api/code_gen_status"

        def _front_alive() -> bool:
            try:
                req = urllib.request.Request(ping_url, method="GET")
                with urllib.request.urlopen(req, timeout=0.25) as resp:
                    return 200 <= int(getattr(resp, "status", 200)) < 300
            except Exception:
                return False

        while True:
            try:
                if not _front_alive():
                    time.sleep(1.5)
                    continue

                page = get_shared_page()
                png = page.screenshot(type="png", timeout=2_000, full_page=False)
                ok = push_browser_screenshot_png(png)
                # если не удалось — подождём чуть меньше, чтобы быстрее "подхватить" фронт
                time.sleep(interval_s if ok else 1.5)
            except Exception:
                time.sleep(1.5)

    threading.Thread(target=_runner, daemon=True).start()


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
    page_version: int = 0
    nav_count: int = 0
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

    load_state: str | None = None
    try:
        if _current_page is not None:
            # Единственный стабильный "геттер" состояния загрузки в sync API — через document.readyState.
            load_state = _current_page.evaluate("() => document.readyState")
            if not isinstance(load_state, str):
                load_state = str(load_state)
    except Exception:
        load_state = None

    return {
        "current_url": _state.current_url,
        "http_status": _state.http_status,
        "page_version": _state.page_version,
        "nav_count": _state.nav_count,
        "load_state": load_state,
        # Timestamp последнего document-ответа главного фрейма (top-level навигации).
        # По смыслу: "когда была загружена текущая версия страницы".
        "last_document_ts": _state._last_document_ts,
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

    # Новая Page (новый контекст) — начинаем с чистого сетевого буфера.
    _network_records_since_load.clear()
    _network_req_map_since_load.clear()

    def _cap_network_size() -> None:
        # Защита от бесконечного роста. Редко используется, но лучше иметь.
        if len(_network_records_since_load) <= _NETWORK_MAX_RECORDS:
            return
        # Оставляем хвост (последние записи)
        keep = _network_records_since_load[-_NETWORK_MAX_RECORDS:]
        _network_records_since_load[:] = keep
        _network_req_map_since_load.clear()
        for rec in _network_records_since_load:
            rid = rec.get("request_id")
            if isinstance(rid, int):
                _network_req_map_since_load[rid] = rec

    def _val(x: Any) -> Any:
        # В sync Playwright часть атрибутов — свойства, часть — методы.
        # Нам нужны значения, а не bound-method объекты.
        try:
            return x() if callable(x) else x
        except Exception:
            return None

    def _mk_request_record(req: Request) -> dict[str, Any]:
        try:
            req_url = _val(getattr(req, "url", None))
            parsed = urlparse(req_url if isinstance(req_url, str) else "")
            query = parse_qs(parsed.query, keep_blank_values=True)
        except Exception:
            req_url = _val(getattr(req, "url", None))
            parsed = None
            query = {}

        post_data = None
        try:
            post_data = _val(getattr(req, "post_data", None))
        except Exception:
            post_data = None

        return {
            "ts": time.time(),
            "request_id": id(req),
            "resource_type": _val(getattr(req, "resource_type", None)),
            "is_navigation_request": _val(getattr(req, "is_navigation_request", None)),
            "method": _val(getattr(req, "method", None)),
            "url": req_url,
            "url_parsed": {
                "scheme": getattr(parsed, "scheme", None),
                "netloc": getattr(parsed, "netloc", None),
                "path": getattr(parsed, "path", None),
                "params": getattr(parsed, "params", None),
                "query": getattr(parsed, "query", None),
                "fragment": getattr(parsed, "fragment", None),
                "query_params": query,
            }
            if parsed is not None
            else None,
            "request": {
                "headers": _val(getattr(req, "headers", None)),
                "post_data": post_data,
            },
            "response": None,
            "failure": None,
        }

    def _upsert_request(req: Request) -> dict[str, Any]:
        rid = id(req)
        rec = _network_req_map_since_load.get(rid)
        if rec is None:
            rec = _mk_request_record(req)
            _network_records_since_load.append(rec)
            _network_req_map_since_load[rid] = rec
            _cap_network_size()
        return rec

    def _try_read_response_text(resp: Response) -> tuple[str | None, dict[str, Any] | None]:
        """
        Возвращает текст ответа (best-effort) и метаданные.

        Важно: некоторые ответы бинарные/очень большие — тогда вернём укороченный текст и флаг truncated.
        """
        meta: dict[str, Any] = {"truncated": False, "store_limit": _NETWORK_BODY_STORE_LIMIT}
        try:
            txt = resp.text()
            if not isinstance(txt, str):
                txt = str(txt)
        except Exception as exc:
            # Fallback: попробуем body() и декодирование.
            try:
                raw = resp.body()
                if isinstance(raw, (bytes, bytearray)):
                    txt = raw.decode("utf-8", errors="replace")
                    meta["decoded_from_bytes"] = True
                else:
                    txt = str(raw)
            except Exception:
                return None, {"error": str(exc)}

        if txt is None:
            return None, None

        if len(txt) > _NETWORK_BODY_STORE_LIMIT:
            meta["truncated"] = True
            meta["original_len"] = len(txt)
            txt = txt[:_NETWORK_BODY_STORE_LIMIT]
        else:
            meta["original_len"] = len(txt)

        return txt, meta

    def _on_request(req: Request) -> None:
        try:
            _upsert_request(req)
        except Exception:
            return

    def _on_request_failed(req: Request) -> None:
        try:
            rec = _upsert_request(req)
            failure = None
            try:
                failure = _val(getattr(req, "failure", None))
            except Exception:
                failure = None
            rec["failure"] = failure
        except Exception:
            return

    def _on_response(resp: Response) -> None:
        try:
            req = resp.request

            is_document_main_frame = False
            try:
                is_document_main_frame = (req.resource_type == "document") and (req.frame == page.main_frame)
            except Exception:
                is_document_main_frame = False

            url = resp.url
            status = resp.status

            # Любой document-ответ главного фрейма = новая версия страницы.
            if is_document_main_frame:
                _state.page_version += 1
                _state.nav_count += 1

                # Сбрасываем историю "since load" на каждую новую версию (включая reload/переход на тот же URL).
                _state.actions_since_load = []
                _state._last_trigger_candidate = None
                _state._last_document_url = url

                _state._last_document_ts = time.time()
                _state.current_url = url
                _state.http_status = status

                # С момента "перезагрузки страницы" начинаем новый сетевой буфер.
                _network_records_since_load.clear()
                _network_req_map_since_load.clear()

            rec = _upsert_request(req)
            body_text, body_meta = _try_read_response_text(resp)
            rec["response"] = {
                "url": url,
                "status": status,
                "ok": _val(getattr(resp, "ok", None)),
                "headers": _val(getattr(resp, "headers", None)),
                "from_service_worker": _val(getattr(resp, "from_service_worker", None)),
                "body_text": body_text,
                "body_meta": body_meta,
            }
        except Exception:
            # Контекстный лог — не должен ломать работу.
            return

    page.on("request", _on_request)
    page.on("requestfailed", _on_request_failed)
    page.on("response", _on_response)
    _listeners_page = page


def get_network_requests_since_load() -> list[dict[str, Any]]:
    """
    Возвращает список сетевых записей (request/response/failure) с момента
    последней top-level навигации/перезагрузки (document response главного фрейма).

    Возвращаем копию, чтобы потребители не могли случайно испортить внутренний буфер.
    """
    try:
        return copy.deepcopy(_network_records_since_load)
    except Exception:
        # Fallback: лучше вернуть хоть что-то, чем упасть.
        return list(_network_records_since_load)

