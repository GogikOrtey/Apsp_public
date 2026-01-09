"""
Background screenshot pusher.

Goal:
- Update preview image on the front every N seconds regardless of Playwright actions.

Important:
- We DO NOT call Playwright from this thread (sync Playwright is thread-bound).
- Instead, we capture an OS-level screenshot (desktop) via Pillow ImageGrab and push it as PNG
  to Flask endpoint: /api/browser_screenshot_push.

This is primarily for Windows debugging (visible browser window).
"""

from __future__ import annotations

import io
import os
import threading
import time
from typing import Optional


_state_lock = threading.Lock()
# key -> {"stop_event": threading.Event, "thread": threading.Thread}
_pushers: dict[str, dict[str, object]] = {}


def _pusher_key(uid: str | None) -> str:
    u = (uid or "").strip()
    return f"uid:{u}" if u else "__global__"


def _grab_desktop_png_bytes(*, max_width: int = 1280) -> bytes | None:
    """
    Returns PNG bytes of the desktop screenshot, optionally downscaled to max_width.
    """
    try:
        from PIL import ImageGrab, Image  # type: ignore
    except Exception:
        return None

    try:
        img = ImageGrab.grab(all_screens=True)
        if img is None:
            return None

        # Downscale (best-effort) to reduce payload/CPU
        try:
            w, h = img.size
            if isinstance(w, int) and w > max_width and max_width > 0:
                ratio = max_width / float(w)
                new_size = (max_width, max(1, int(h * ratio)))
                img = img.resize(new_size, resample=getattr(Image, "LANCZOS", Image.BICUBIC))
        except Exception:
            pass

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _push_loop(*, stop_event: threading.Event, interval_s: float, uid: str | None) -> None:
    # Lazy import: keeps import graph light and avoids hard failures if front_client isn't used.
    try:
        from front_client import DEFAULT_FRONT_BASE_URL, push_browser_screenshot_png
    except Exception:
        return

    base_url = os.environ.get("APSP_FRONT_BASE_URL", DEFAULT_FRONT_BASE_URL)

    # First push immediately (so UI doesn't wait 5s)
    last_push_ts = 0.0
    while not stop_event.is_set():
        now = time.time()
        if last_push_ts == 0.0 or (now - last_push_ts) >= max(0.1, float(interval_s)):
            png = _grab_desktop_png_bytes(max_width=1280)
            if png:
                try:
                    push_browser_screenshot_png(png, base_url=base_url, timeout_s=0.5, uid=uid)
                except Exception:
                    pass
            last_push_ts = now

        # Sleep in small increments to react faster to stop_event
        stop_event.wait(timeout=0.2)


def start_screenshot_pusher(*, interval_s: float = 5.0, uid: str | None = None) -> None:
    """
    Starts a daemon background thread that pushes screenshots every interval_s seconds.
    Safe to call multiple times (will only start once).
    """
    key = _pusher_key(uid)
    with _state_lock:
        existing = _pushers.get(key) or {}
        th = existing.get("thread")
        if isinstance(th, threading.Thread) and th.is_alive():
            return

        stop_event = threading.Event()
        thread = threading.Thread(
            target=_push_loop,
            kwargs={"stop_event": stop_event, "interval_s": float(interval_s), "uid": uid},
            daemon=True,
            name=("apsp_screenshot_pusher" if not uid else f"apsp_screenshot_pusher_{uid}"),
        )
        _pushers[key] = {"stop_event": stop_event, "thread": thread}
        thread.start()


def stop_screenshot_pusher(*, uid: str | None = None) -> None:
    """
    Stops the background screenshot pusher thread (best-effort).
    """
    key = _pusher_key(uid)
    stop_event: threading.Event | None = None
    with _state_lock:
        st = _pushers.pop(key, None) or {}
        ev = st.get("stop_event")
        if isinstance(ev, threading.Event):
            stop_event = ev
    if stop_event is not None:
        try:
            stop_event.set()
        except Exception:
            pass


