"""
Утилиты для обновления текста на фронте (Flask на localhost).

Требование: функции НЕ должны выбрасывать ошибок, если фронт не запущен.
Поэтому любые сетевые ошибки перехватываются, а результат возвращается как bool.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

from task_runtime.task_context import get_current_task_uid, get_current_task_dir


DEFAULT_FRONT_BASE_URL = os.environ.get("APSP_FRONT_BASE_URL", "http://127.0.0.1:5000")
_DEBUG = os.environ.get("APSP_FRONT_CLIENT_DEBUG", "").strip() not in ("", "0", "false", "False")

# Файл состояния (fallback если HTTP POST не прошёл).
# В многозадачном режиме пишем в RESULT_TASKS/<uid>/new_page_2_state.json,
# иначе (legacy) — в result_code_gen/result/new_page_2_state.json.
_PROJECT_ROOT = Path(__file__).resolve().parent
_NEW_PAGE_2_ALLOWED_FIELDS = {
    "reflection_text",
    "goal_text",
    "action_text",
    "update_result_text",
    "current_step_title",
    "last_phase_result_text",
    "timer_reset_seq",
}


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return ""


def _post_json(
    path: str,
    payload: dict[str, Any],
    *,
    base_url: str = DEFAULT_FRONT_BASE_URL,
    timeout_s: float = 0.25,
) -> bool:
    """
    Отправляет JSON на фронт. Возвращает True если запрос дошёл и вернулся 2xx.
    Никогда не выбрасывает исключений наружу.
    """
    try:
        url = base_url.rstrip("/") + path
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            # Любой 2xx считаем успехом
            return 200 <= int(getattr(resp, "status", 200)) < 300
    except Exception as e:
        if _DEBUG:
            try:
                print(f"[front_client] POST {path} failed: {type(e).__name__}: {e}")
            except Exception:
                pass
        return False


def _resolve_state_file() -> Path:
    task_dir = get_current_task_dir()
    if task_dir:
        return Path(task_dir) / "new_page_2_state.json"
    return _PROJECT_ROOT / "result_code_gen" / "result" / "new_page_2_state.json"


def _load_new_page_2_state_file() -> dict[str, Any]:
    try:
        path = _resolve_state_file()
        if not path.is_file():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        if _DEBUG:
            try:
                print(f"[front_client] load state file failed: {type(e).__name__}: {e}")
            except Exception:
                pass
        return {}


def _save_new_page_2_state_file(state: dict[str, Any]) -> bool:
    try:
        path = _resolve_state_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.replace(path)
        return True
    except Exception as e:
        if _DEBUG:
            try:
                print(f"[front_client] save state file failed: {type(e).__name__}: {e}")
            except Exception:
                pass
        return False


def _fallback_update_state_file(field_id: str, text: Any) -> bool:
    # Пишем только "разрешённые" поля, чтобы не ломать фронт.
    if field_id not in _NEW_PAGE_2_ALLOWED_FIELDS:
        return False
    state = _load_new_page_2_state_file()
    # Подмешиваем/обновляем поле
    state[field_id] = _to_text(text)
    # На всякий случай не даём записать неожиданные ключи
    state = {k: state.get(k, "") for k in _NEW_PAGE_2_ALLOWED_FIELDS if k in state or k == field_id}
    return _save_new_page_2_state_file(state)


def push_browser_screenshot_png(
    png_bytes: bytes,
    *,
    base_url: str = DEFAULT_FRONT_BASE_URL,
    timeout_s: float = 0.5,
    uid: str | None = None,
) -> bool:
    """
    Пушит PNG-скриншот в Flask (в память процесса) на /api/browser_screenshot_push.

    Важно: как и остальные функции этого файла, не выбрасывает исключений наружу.
    """
    try:
        if not isinstance(png_bytes, (bytes, bytearray)) or not png_bytes:
            return False
        effective_uid = uid if uid else get_current_task_uid()
        url = base_url.rstrip("/") + ("/api/browser_screenshot_push" if not effective_uid else f"/api/task/{effective_uid}/browser_screenshot_push")
        req = urllib.request.Request(
            url,
            data=bytes(png_bytes),
            headers={"Content-Type": "image/png"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return 200 <= int(getattr(resp, "status", 200)) < 300
    except Exception:
        return False


def update_new_page_2_field(
    field_id: str,
    text: Any,
    *,
    base_url: str = DEFAULT_FRONT_BASE_URL,
    timeout_s: float = 0.25,
) -> bool:
    uid = get_current_task_uid()
    path = "/api/new_page_2_state" if not uid else f"/api/task/{uid}/new_page_2_state"
    ok = _post_json(
        path,
        {"field": field_id, "value": _to_text(text)},
        base_url=base_url,
        timeout_s=timeout_s,
    )
    if ok:
        return True
    return _fallback_update_state_file(field_id, text)


# --- Удобные обёртки под конкретные поля new_page_2.html ---

def update_content_front_reasoning(text: Any, *, base_url: str = DEFAULT_FRONT_BASE_URL, timeout_s: float = 0.25) -> bool:
    """`new_page_2.html`: обновляет поле 'Размышление' (id=`reflection_text`)."""
    return update_new_page_2_field("reflection_text", text, base_url=base_url, timeout_s=timeout_s)


def update_content_front_goal(text: Any, *, base_url: str = DEFAULT_FRONT_BASE_URL, timeout_s: float = 0.25) -> bool:
    """`new_page_2.html`: обновляет поле 'Цель' (id=`goal_text`)."""
    return update_new_page_2_field("goal_text", text, base_url=base_url, timeout_s=timeout_s)


def update_content_front_action(text: Any, *, base_url: str = DEFAULT_FRONT_BASE_URL, timeout_s: float = 0.25) -> bool:
    """`new_page_2.html`: обновляет поле 'Действие' (id=`action_text`)."""
    return update_new_page_2_field("action_text", text, base_url=base_url, timeout_s=timeout_s)


def update_content_front_update_result(text: Any, *, base_url: str = DEFAULT_FRONT_BASE_URL, timeout_s: float = 0.25) -> bool:
    """`new_page_2.html`: обновляет поле 'Update result' (id=`update_result_text`)."""
    return update_new_page_2_field("update_result_text", text, base_url=base_url, timeout_s=timeout_s)


def update_content_front_last_phase_result(text: Any, *, base_url: str = DEFAULT_FRONT_BASE_URL, timeout_s: float = 0.25) -> bool:
    """`new_page_2.html`: обновляет поле 'Результат последней фазы' (id=`last_phase_result_text`)."""
    return update_new_page_2_field("last_phase_result_text", text, base_url=base_url, timeout_s=timeout_s)


def update_content_front_current_step(text: Any, *, base_url: str = DEFAULT_FRONT_BASE_URL, timeout_s: float = 0.25) -> bool:
    """`new_page_2.html`: обновляет заголовок 'Текущий шаг' (id=`current_step_title`)."""
    return update_new_page_2_field("current_step_title", text, base_url=base_url, timeout_s=timeout_s)


