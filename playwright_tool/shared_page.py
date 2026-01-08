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

_contexts_lock = threading.Lock()
_contexts: dict[int, dict[str, Any]] = {}


def _ctx() -> dict[str, Any]:
    """
    Per-thread storage for Playwright objects/state.

    Sync Playwright objects are thread-affine, so each worker thread MUST keep its own page/state.
    """
    tid = threading.get_ident()
    with _contexts_lock:
        c = _contexts.get(tid)
        if c is None:
            c = {
                "current_page": None,
                "listeners_page": None,
                "network_records_since_load": [],
                "network_req_map_since_load": {},
                "last_screenshot_png": None,
                "last_screenshot_ts": None,
                "last_screenshot_error": None,
                "playwright_owner_thread_id": None,
                "last_pushed_screenshot_ts": None,
                "state": None,  # PlaywrightContextState (lazy)
            }
            _contexts[tid] = c
        if c.get("state") is None:
            c["state"] = PlaywrightContextState()
        return c
_NETWORK_MAX_RECORDS: int = 2000
_NETWORK_BODY_STORE_LIMIT: int = 1_000_000  # символов текста (best-effort), чтобы не раздувать память

# Screenshot cache (per-thread, stored in _ctx()).
_screenshot_lock = threading.Lock()


def set_shared_page(page: Page) -> None:
    """Store Playwright page for reuse across toolkit helpers."""
    c = _ctx()
    c["current_page"] = page
    # Playwright sync objects must be used only from the thread that created them.
    c["playwright_owner_thread_id"] = threading.get_ident()
    _ensure_listeners(page)


def get_shared_page() -> Page:
    """Return stored Playwright page or raise if it is not set."""
    page = _ctx().get("current_page")
    if page is None:
        raise RuntimeError(
            "Playwright page is not initialized. Call set_shared_page(page) before using toolkit tools."
        )
    return page


def clear_shared_page() -> None:
    """Clears per-thread stored page and related caches (best-effort)."""
    c = _ctx()
    c["current_page"] = None
    c["listeners_page"] = None
    c["network_records_since_load"] = []
    c["network_req_map_since_load"] = {}
    c["last_screenshot_png"] = None
    c["last_screenshot_ts"] = None
    c["last_screenshot_error"] = None
    c["last_pushed_screenshot_ts"] = None
    c["state"] = PlaywrightContextState()


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
    c = _ctx()

    now = time.time()
    with _screenshot_lock:
        age_ms: int | None = None
        if c.get("last_screenshot_ts") is not None:
            age_ms = int(max(0.0, (now - float(c.get("last_screenshot_ts"))) * 1000))

        # Fresh enough -> return cache
        if c.get("last_screenshot_png") is not None and age_ms is not None and age_ms < int(min_interval_ms):
            return c.get("last_screenshot_png"), {
                "ok": True,
                "ts": c.get("last_screenshot_ts"),
                "age_ms": age_ms,
                "from_cache": True,
                "error": None,
            }

        # Need a refresh
        try:
            # Важно: sync Playwright нельзя дергать из другого thread (greenlet.error).
            if c.get("playwright_owner_thread_id") is not None and threading.get_ident() != c.get("playwright_owner_thread_id"):
                raise RuntimeError("playwright_screenshot_wrong_thread")
            page = get_shared_page()
            png = page.screenshot(type="png", timeout=int(timeout_ms), full_page=bool(full_page))
            if not isinstance(png, (bytes, bytearray)):
                raise TypeError("page.screenshot() returned non-bytes")
            c["last_screenshot_png"] = bytes(png)
            c["last_screenshot_ts"] = time.time()
            c["last_screenshot_error"] = None
            return c.get("last_screenshot_png"), {
                "ok": True,
                "ts": c.get("last_screenshot_ts"),
                "age_ms": 0,
                "from_cache": False,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            c["last_screenshot_error"] = str(exc)
            # Fallback to previous screenshot if any
            if c.get("last_screenshot_png") is not None and c.get("last_screenshot_ts") is not None:
                fallback_age_ms = int(max(0.0, (now - float(c.get("last_screenshot_ts"))) * 1000))
                return c.get("last_screenshot_png"), {
                    "ok": True,
                    "ts": c.get("last_screenshot_ts"),
                    "age_ms": fallback_age_ms,
                    "from_cache": True,
                    "error": c.get("last_screenshot_error"),
                }
            return None, {"ok": False, "ts": None, "age_ms": None, "from_cache": False, "error": c.get("last_screenshot_error")}


def maybe_push_screenshot_to_front(
    *,
    min_interval_ms: int = 1500,
    timeout_ms: int = 2_000,
    full_page: bool = False,
    base_url: str | None = None,
) -> bool:
    """
    Делает (или берёт из кэша) PNG-скриншот и пушит его в Flask (/api/browser_screenshot_push).

    Важно: вызывать только из owner-thread Playwright (того же, где создавался browser/page),
    иначе sync Playwright упадёт с greenlet.error.

    Возвращает True, если "в целом ок" (уже было запушено / удалось запушить), иначе False.
    """
    c = _ctx()

    png, meta = get_cached_screenshot_png(min_interval_ms=min_interval_ms, timeout_ms=timeout_ms, full_page=full_page)
    if not png or not isinstance(meta, dict) or not meta.get("ok"):
        return False

    ts = meta.get("ts")
    if isinstance(ts, (int, float)) and c.get("last_pushed_screenshot_ts") == float(ts):
        return True  # этот кадр уже отправляли

    try:
        # Ленивая загрузка, чтобы не тянуть сеть при импорте.
        from front_client import DEFAULT_FRONT_BASE_URL, push_browser_screenshot_png  # noqa: WPS433

        ok = push_browser_screenshot_png(png, base_url=(base_url or DEFAULT_FRONT_BASE_URL), timeout_s=0.5)
        if ok and isinstance(ts, (int, float)):
            c["last_pushed_screenshot_ts"] = float(ts)
        return ok
    except Exception:
        return False


def sleep_with_screenshot_push(
    seconds: float,
    *,
    interval_s: float = 5.0,
    base_url: str | None = None,
    full_page: bool = False,
    timeout_ms: int = 2_000,
) -> None:
    """
    "Безопасный sleep" для отладки/ожиданий: пока мы ждём, каждые interval_s секунд
    делаем новый PNG-скриншот и пушим его на фронт.

    Зачем это нужно:
    - когда в коде есть длинный time.sleep(...) (например, чтобы оставить окно браузера открытым)
    - чтобы картинка на new_page_2.html продолжала обновляться каждые 5 секунд
      даже без действий агента, и отражала ручные взаимодействия (скролл/клик) в окне.

    Важно:
    - вызывать ТОЛЬКО из owner-thread Playwright (того же, где создавался page),
      иначе Playwright sync API может упасть/вернуть stale кадр.
    """
    try:
        total = float(seconds)
    except Exception:
        total = 0.0
    if total <= 0:
        return

    try:
        interval = float(interval_s)
    except Exception:
        interval = 5.0
    if interval <= 0:
        interval = 5.0

    deadline = time.time() + total
    # Первый пуш сразу — чтобы UI не ждал 5 секунд
    try:
        maybe_push_screenshot_to_front(
            min_interval_ms=0,
            timeout_ms=int(timeout_ms),
            full_page=bool(full_page),
            base_url=base_url,
        )
    except Exception:
        pass

    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
        try:
            maybe_push_screenshot_to_front(
                min_interval_ms=0,
                timeout_ms=int(timeout_ms),
                full_page=bool(full_page),
                base_url=base_url,
            )
        except Exception:
            # Не мешаем основному коду: это отладочный/сервисный хелпер
            pass


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


def reset_playwright_context_state() -> None:
    """Сбрасывает историю действий и last_change (полезно для тестов/перезапусков)."""
    _ctx()["state"] = PlaywrightContextState()


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
    state: PlaywrightContextState = _ctx()["state"]
    # История
    call = _format_action_call(action, args)
    state.actions_since_load.append(call)
    if len(state.actions_since_load) > max_actions:
        state.actions_since_load = state.actions_since_load[-max_actions:]

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
        state._last_trigger_candidate = call

    # last_change: выставляем на wait_for_navigation_or_content (или сразу на явную навигацию)
    if action in {"goto_url", "page_restart"}:
        state.last_change = PlaywrightLastChange(
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

        trigger = state._last_trigger_candidate or "unknown"
        state.last_change = PlaywrightLastChange(
            type=change_type,
            trigger=trigger,
            delta_text=delta_text,
            reason=str(reason) if reason is not None else None,
        )


def get_playwright_context_snapshot(*, max_actions: int = 10) -> dict[str, Any]:
    """Возвращает снапшот state в простом dict-формате (удобно для промптов)."""
    state: PlaywrightContextState = _ctx()["state"]
    actions = state.actions_since_load[-max_actions:] if max_actions > 0 else []

    load_state: str | None = None
    try:
        page = _ctx().get("current_page")
        if page is not None:
            # Единственный стабильный "геттер" состояния загрузки в sync API — через document.readyState.
            load_state = page.evaluate("() => document.readyState")
            if not isinstance(load_state, str):
                load_state = str(load_state)
    except Exception:
        load_state = None

    return {
        "current_url": state.current_url,
        "http_status": state.http_status,
        "page_version": state.page_version,
        "nav_count": state.nav_count,
        "load_state": load_state,
        # Timestamp последнего document-ответа главного фрейма (top-level навигации).
        # По смыслу: "когда была загружена текущая версия страницы".
        "last_document_ts": state._last_document_ts,
        "last_change": {
            "type": state.last_change.type,
            "trigger": state.last_change.trigger,
            "delta_text": state.last_change.delta_text,
            "reason": state.last_change.reason,
            "ts": state.last_change.ts,
        },
        "actions_since_load": actions,
    }


def _ensure_listeners(page: Page) -> None:
    c = _ctx()
    state: PlaywrightContextState = c["state"]
    # Если page уже та же самая — не вешаем второй раз.
    if c.get("listeners_page") is page:
        return

    # Новая Page (новый контекст) — начинаем с чистого сетевого буфера.
    c["network_records_since_load"] = []
    c["network_req_map_since_load"] = {}

    def _cap_network_size() -> None:
        # Защита от бесконечного роста. Редко используется, но лучше иметь.
        if len(c["network_records_since_load"]) <= _NETWORK_MAX_RECORDS:
            return
        # Оставляем хвост (последние записи)
        keep = c["network_records_since_load"][-_NETWORK_MAX_RECORDS:]
        c["network_records_since_load"] = list(keep)
        c["network_req_map_since_load"].clear()
        for rec in c["network_records_since_load"]:
            rid = rec.get("request_id")
            if isinstance(rid, int):
                c["network_req_map_since_load"][rid] = rec

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
        rec = c["network_req_map_since_load"].get(rid)
        if rec is None:
            rec = _mk_request_record(req)
            c["network_records_since_load"].append(rec)
            c["network_req_map_since_load"][rid] = rec
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
                state.page_version += 1
                state.nav_count += 1

                # Сбрасываем историю "since load" на каждую новую версию (включая reload/переход на тот же URL).
                state.actions_since_load = []
                state._last_trigger_candidate = None
                state._last_document_url = url

                state._last_document_ts = time.time()
                state.current_url = url
                state.http_status = status

                # С момента "перезагрузки страницы" начинаем новый сетевой буфер.
                c["network_records_since_load"] = []
                c["network_req_map_since_load"] = {}

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
    c["listeners_page"] = page


def get_network_requests_since_load() -> list[dict[str, Any]]:
    """
    Возвращает список сетевых записей (request/response/failure) с момента
    последней top-level навигации/перезагрузки (document response главного фрейма).

    Возвращаем копию, чтобы потребители не могли случайно испортить внутренний буфер.
    """
    c = _ctx()
    buf = c.get("network_records_since_load") or []
    try:
        return copy.deepcopy(buf)
    except Exception:
        # Fallback: лучше вернуть хоть что-то, чем упасть.
        return list(buf)

