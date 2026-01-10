"""
Telegram connect / auth helpers for APSP_public.

Флоу авторизации:
- фронт вызывает POST /api/telegram/auth/start -> получаем token и deep-link на бота: https://t.me/<bot>?start=<token>
- пользователь нажимает Start в Telegram
- бот получает /start <token> и шлёт апдейт в наш webhook
- сервер помечает token как authorized, сохраняет tg_user (id/username)
- браузер опрашивает /api/telegram/auth/status и затем /api/telegram/auth/finish, чтобы поставить куки



Имя и usernamne бота = auto_gen_parsers_info_bot

Use this token to access the HTTP API:
ТОКЕН

"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode


DEFAULT_TOKEN_TTL_SECONDS = 30 * 60  # 30 минут


@dataclass(frozen=True)
class TelegramUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


def create_auth_token() -> str:
    """
    Генерирует token, который можно безопасно использовать как payload для /start.
    Ограничение Telegram: payload до 64 символов (мы используем 32 hex).
    """
    return secrets.token_hex(16)  # 32 chars


def _safe_token(token: str) -> str | None:
    if not token or not isinstance(token, str):
        return None
    t = token.strip()
    if not t:
        return None
    # Разрешаем только hex как в create_auth_token()
    if len(t) != 32:
        return None
    for ch in t:
        if ch not in "0123456789abcdefABCDEF":
            return None
    return t.lower()


def _token_path(auth_dir: Path, token: str) -> Path:
    return auth_dir / f"{token}.json"


def create_pending_auth(auth_dir: Path, token: str, *, ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS) -> None:
    auth_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    payload = {
        "token": token,
        "status": "pending",
        "created_at_ts": now,
        "expires_at_ts": now + float(ttl_seconds),
        "authorized_at_ts": None,
        "tg_user": None,
    }
    _token_path(auth_dir, token).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_auth_record(auth_dir: Path, token: str) -> dict[str, Any] | None:
    p = _token_path(auth_dir, token)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_auth_record(auth_dir: Path, token: str, record: dict[str, Any]) -> None:
    auth_dir.mkdir(parents=True, exist_ok=True)
    _token_path(auth_dir, token).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def get_auth_status(auth_dir: Path, token: str) -> dict[str, Any]:
    """
    Возвращает объект статуса, который удобно отдавать фронту.

    Формат:
      { ok: true, status: 'pending'|'authorized'|'expired'|'not_found', user?: {...} }
    """
    t = _safe_token(token)
    if not t:
        return {"ok": True, "status": "not_found"}

    rec = _read_auth_record(auth_dir, t)
    if not rec:
        return {"ok": True, "status": "not_found"}

    status = (rec.get("status") or "pending").lower()
    expires_at_ts = rec.get("expires_at_ts")
    now = time.time()
    try:
        expires_at_ts_f = float(expires_at_ts) if expires_at_ts is not None else None
    except Exception:
        expires_at_ts_f = None

    if status != "authorized" and expires_at_ts_f is not None and now > expires_at_ts_f:
        return {"ok": True, "status": "expired"}

    if status == "authorized":
        user = rec.get("tg_user") or {}
        if isinstance(user, dict):
            return {"ok": True, "status": "authorized", "user": user}
        return {"ok": True, "status": "authorized"}

    return {"ok": True, "status": "pending"}


def mark_authorized(auth_dir: Path, token: str, tg_user: TelegramUser) -> bool:
    t = _safe_token(token)
    if not t:
        return False

    rec = _read_auth_record(auth_dir, t)
    if not rec:
        return False

    now = time.time()
    expires_at_ts = rec.get("expires_at_ts")
    try:
        if expires_at_ts is not None and now > float(expires_at_ts):
            return False
    except Exception:
        pass

    rec["status"] = "authorized"
    rec["authorized_at_ts"] = now
    rec["tg_user"] = {
        "id": int(tg_user.id),
        "username": tg_user.username,
        "first_name": tg_user.first_name,
        "last_name": tg_user.last_name,
    }
    _write_auth_record(auth_dir, t, rec)
    return True


def consume_auth_token(auth_dir: Path, token: str) -> None:
    t = _safe_token(token)
    if not t:
        return
    p = _token_path(auth_dir, t)
    try:
        if p.is_file():
            p.unlink()
    except Exception:
        pass


def store_telegram_user(users_dir: Path, tg_user: TelegramUser) -> None:
    users_dir.mkdir(parents=True, exist_ok=True)
    path = users_dir / f"tg_{int(tg_user.id)}.json"
    payload = {
        "id": int(tg_user.id),
        "username": tg_user.username,
        "first_name": tg_user.first_name,
        "last_name": tg_user.last_name,
        "updated_at_ts": time.time(),
    }
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def send_bot_message(*, bot_token: str, chat_id: int, text: str) -> dict[str, Any]:
    """
    Отправка сообщения через Telegram Bot API без внешних зависимостей (requests не нужен).
    """
    if not bot_token:
        return {"ok": False, "error": "bot_token_missing"}
    if not chat_id:
        return {"ok": False, "error": "chat_id_missing"}
    if text is None:
        text = ""

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = urlencode(
        {
            "chat_id": str(int(chat_id)),
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    req = urllib_request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        return {"ok": False, "error": f"http_{getattr(e, 'code', '')}", "raw": raw}
    except URLError as e:
        return {"ok": False, "error": "network_error", "details": str(e)}
    except Exception as e:
        return {"ok": False, "error": "send_failed", "details": str(e)}

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"ok": False, "error": "bad_response", "raw": raw}


def _parse_start_payload(text: str) -> str | None:
    if not text or not isinstance(text, str):
        return None
    t = text.strip()
    if not t:
        return None
    if not t.startswith("/start"):
        return None
    parts = t.split(maxsplit=1)
    if len(parts) < 2:
        return None
    payload = parts[1].strip()
    if not payload:
        return None
    return payload


def handle_telegram_update(
    update: dict[str, Any],
    *,
    auth_dir: Path,
    users_dir: Path,
    bot_token: str,
    base_url: str = "http://127.0.0.1:5000",
) -> dict[str, Any]:
    """
    Обрабатывает Telegram update (webhook payload).
    Сейчас поддерживаем только /start <token> для авторизации.
    """
    if not isinstance(update, dict):
        return {"ok": True, "handled": False}

    msg = update.get("message")
    if not isinstance(msg, dict):
        # callback_query и др. пока игнорируем
        return {"ok": True, "handled": False}

    text = msg.get("text")
    token = _parse_start_payload(text) if isinstance(text, str) else None
    if not token:
        return {"ok": True, "handled": False}

    t = _safe_token(token)
    if not t:
        return {"ok": True, "handled": True, "status": "bad_token"}

    from_user = msg.get("from") or {}
    chat = msg.get("chat") or {}
    try:
        tg_id = int(from_user.get("id"))
    except Exception:
        tg_id = None

    if not tg_id:
        return {"ok": True, "handled": True, "status": "no_user_id"}

    tg_user = TelegramUser(
        id=tg_id,
        username=from_user.get("username"),
        first_name=from_user.get("first_name"),
        last_name=from_user.get("last_name"),
    )

    ok = mark_authorized(auth_dir, t, tg_user)
    store_telegram_user(users_dir, tg_user)

    # В личном чате chat.id == user.id (обычно), но берём из апдейта.
    try:
        chat_id = int(chat.get("id")) if chat.get("id") is not None else int(tg_id)
    except Exception:
        chat_id = int(tg_id)

    if ok:
        text_ok = "Авторизация успешна"
        # лёгкий UX: подсказываем вернуться на сайт
        if base_url:
            text_ok += f"\n\nВернитесь в браузер: {base_url}/login_page"
        send_bot_message(bot_token=bot_token, chat_id=chat_id, text=text_ok)
        return {"ok": True, "handled": True, "status": "authorized", "token": t, "tg_id": tg_id}

    send_bot_message(
        bot_token=bot_token,
        chat_id=chat_id,
        text="Не удалось подтвердить авторизацию (возможно, токен истёк). Вернитесь на сайт и нажмите кнопку ещё раз.",
    )
    return {"ok": True, "handled": True, "status": "not_authorized", "token": t, "tg_id": tg_id}


