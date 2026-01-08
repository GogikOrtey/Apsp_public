from __future__ import annotations

import threading
from datetime import datetime
from typing import Any


TASK_SCREENSHOTS_STATE: dict[str, dict[str, Any]] = {}
TASK_SCREENSHOTS_LOCK = threading.Lock()


def set_task_screenshot(uid: str, png: bytes, *, ts: float | None = None) -> None:
    if not uid:
        return
    if not isinstance(png, (bytes, bytearray)) or not png:
        return
    with TASK_SCREENSHOTS_LOCK:
        TASK_SCREENSHOTS_STATE[str(uid)] = {
            "png": bytes(png),
            "ts": float(ts) if isinstance(ts, (int, float)) else datetime.now().timestamp(),
        }


def get_task_screenshot(uid: str) -> tuple[bytes | None, float | None]:
    if not uid:
        return None, None
    with TASK_SCREENSHOTS_LOCK:
        entry = TASK_SCREENSHOTS_STATE.get(str(uid)) or {}
        png = entry.get("png")
        ts = entry.get("ts")
    if not isinstance(png, (bytes, bytearray)) or not png:
        return None, None
    try:
        ts_f = float(ts) if isinstance(ts, (int, float, str)) and str(ts) else None
    except Exception:
        ts_f = None
    return bytes(png), ts_f


