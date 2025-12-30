"""
Утилиты для обновления текста на фронте (Flask на localhost).

Требование: функции НЕ должны выбрасывать ошибок, если фронт не запущен.
Поэтому любые сетевые ошибки перехватываются, а результат возвращается как bool.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional


DEFAULT_FRONT_BASE_URL = "http://127.0.0.1:5000"


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
    except Exception:
        return False


def push_browser_screenshot_png(
    png_bytes: bytes,
    *,
    base_url: str = DEFAULT_FRONT_BASE_URL,
    timeout_s: float = 0.5,
) -> bool:
    """
    Пушит PNG-скриншот в Flask (в память процесса) на /api/browser_screenshot_push.

    Важно: как и остальные функции этого файла, не выбрасывает исключений наружу.
    """
    try:
        if not isinstance(png_bytes, (bytes, bytearray)) or not png_bytes:
            return False
        url = base_url.rstrip("/") + "/api/browser_screenshot_push"
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
    return _post_json(
        "/api/new_page_2_state",
        {"field": field_id, "value": _to_text(text)},
        base_url=base_url,
        timeout_s=timeout_s,
    )


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


