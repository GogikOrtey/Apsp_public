"""
Telegram connect / auth helpers for APSP_public.

Флоу авторизации:
- фронт вызывает POST /api/telegram/auth/start -> получаем token и deep-link на бота: https://t.me/<bot>?start=<token>
- пользователь нажимает Start в Telegram
- бот получает /start <token> и шлёт апдейт в наш webhook
- сервер помечает token как authorized, сохраняет tg_user (id/username)
- браузер опрашивает /api/telegram/auth/status и затем /api/telegram/auth/finish, чтобы поставить куки
"""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode


DEFAULT_TOKEN_TTL_SECONDS = 30 * 60  # 30 минут


def _get_env_int(name: str) -> int | None:
    try:
        v = (os.environ.get(name, "") or "").strip()
        if not v:
            return None
        return int(v)
    except Exception:
        return None


def _is_diagnostic_chat_id(chat_id: int) -> bool:
    """
    Возвращает True, если chat_id совпадает с log_chat или info_chat из env.
    Нужно, чтобы:
    - не дублировать диагностические сообщения обратно в log_chat
    - не зациклиться (log_chat -> send_bot_message -> duplicate -> log_chat -> ...)
    """
    try:
        cid = int(chat_id)
    except Exception:
        return False
    log_id = _get_env_int("APSP_TELEGRAM_LOG_CHAT_ID")
    info_id = _get_env_int("APSP_TELEGRAM_INFO_CHAT_ID")
    return (log_id is not None and cid == log_id) or (info_id is not None and cid == info_id)


def _format_user_label(*, user_telegram_id: int, user_account: str | None = None) -> str:
    acct = (user_account or "").strip()
    if acct:
        return f"{acct} (tg_id={int(user_telegram_id)})"
    return f"tg_id={int(user_telegram_id)}"


def _dup_outgoing_to_log_chat(
    *,
    header: str,
    body: str | None = None,
    bot_token: str | None = None,
) -> None:
    """
    Централизованное best-effort дублирование исходящих уведомлений в log_chat.

    Формат выдерживаем простой и расширяемый:
    - первая строка: "Пользователь/Пользователю ..."
    - дальше (опционально) "body" (укороченный)
    """
    try:
        msg = (header or "").strip()
        if not msg:
            return
        if body:
            body_trim = _trim_to_max_chars(str(body), 1500).strip()
            if body_trim:
                msg = f"{msg}\n{body_trim}"
        try_send_to_log_chat(msg, bot_token=bot_token)
    except Exception:
        return


def _escape_html(text: str) -> str:
    if text is None:
        return ""
    s = str(text)
    # Минимальный набор для Telegram HTML
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _extract_error_snippet_from_text(text: str) -> str:
    """
    Похоже на логику в `Apsp_front/app.py` (tooltip на all_tasks):
    ищем последнюю строку с Error/Exception/... и берём её + всё что после (только непустые).
    """
    if not text or not isinstance(text, str):
        return ""
    lines = text.strip().split("\n")
    if not lines:
        return ""
    markers = ["Error:", "Exception:", "ValueError:", "TypeError:", "KeyError:", "AttributeError:"]
    exception_index = -1
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if line and any(m in line for m in markers):
            exception_index = i
            break
    if exception_index >= 0:
        out: list[str] = []
        for i in range(exception_index, len(lines)):
            if lines[i].strip():
                out.append(lines[i].strip())
        return "\n".join(out).strip()
    # fallback: последняя непустая строка
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return ""


def _trim_to_max_chars(text: str, max_chars: int) -> str:
    """
    Укорачивает строку до max_chars, добавляя '…' если было укорачивание.
    """
    if text is None:
        return ""
    s = str(text)
    if max_chars <= 0:
        return ""
    if len(s) <= max_chars:
        return s
    if max_chars <= 1:
        return "…"
    return s[: max_chars - 1] + "…"


def send_message_to_user(
    *,
    bot_token: str,
    user_telegram_id: int,
    text: str,
    dup_to_log: bool = True,
) -> dict[str, Any]:
    """
    Публичная функция-обёртка для отправки сообщения конкретному пользователю.

    - user_telegram_id: Telegram ID пользователя (число)
    - text: текст сообщения
    """
    try:
        chat_id = int(user_telegram_id)
    except Exception:
        return {"ok": False, "error": "bad_user_telegram_id"}
    return send_bot_message(bot_token=bot_token, chat_id=chat_id, text=text or "", dup_to_log=dup_to_log)


def send_message_to_log_chat(*, bot_token: str, log_chat_id: int, text: str) -> dict[str, Any]:
    """
    Отправка сообщения в диагностический чат log_chat.

    Важно: нужен числовой chat_id (в группах/супергруппах часто отрицательный, например -100...).
    """
    try:
        chat_id = int(log_chat_id)
    except Exception:
        return {"ok": False, "error": "bad_log_chat_id"}
    return send_bot_message(bot_token=bot_token, chat_id=chat_id, text=text or "", dup_to_log=False)


def send_message_to_info_chat(*, bot_token: str, info_chat_id: int, text: str) -> dict[str, Any]:
    """
    Отправка сообщения в диагностический чат info_chat.
    """
    try:
        chat_id = int(info_chat_id)
    except Exception:
        return {"ok": False, "error": "bad_info_chat_id"}
    return send_bot_message(bot_token=bot_token, chat_id=chat_id, text=text or "", dup_to_log=False)


def try_send_to_log_chat(text: str, *, bot_token: str | None = None, log_chat_id: int | None = None) -> None:
    """
    Best-effort: отправляет сообщение в log_chat, значения берёт из аргументов или env.
    Ничего не рейзит.

    Env:
      - APSP_TELEGRAM_BOT_TOKEN
      - APSP_TELEGRAM_LOG_CHAT_ID
    """
    try:
        if bot_token is None:
            bot_token = (os.environ.get("APSP_TELEGRAM_BOT_TOKEN", "") or "").strip()
        if not bot_token:
            return
        if log_chat_id is None:
            v = (os.environ.get("APSP_TELEGRAM_LOG_CHAT_ID", "") or "").strip()
            if not v:
                return
            log_chat_id = int(v)
        send_message_to_log_chat(bot_token=bot_token, log_chat_id=int(log_chat_id), text=text or "")
    except Exception:
        return


def try_send_to_info_chat(text: str, *, bot_token: str | None = None, info_chat_id: int | None = None) -> None:
    """
    Best-effort: отправляет сообщение в info_chat, значения берёт из аргументов или env.
    Ничего не рейзит.

    Env:
      - APSP_TELEGRAM_BOT_TOKEN
      - APSP_TELEGRAM_INFO_CHAT_ID
    """
    try:
        if bot_token is None:
            bot_token = (os.environ.get("APSP_TELEGRAM_BOT_TOKEN", "") or "").strip()
        if not bot_token:
            return
        if info_chat_id is None:
            v = (os.environ.get("APSP_TELEGRAM_INFO_CHAT_ID", "") or "").strip()
            if not v:
                return
            info_chat_id = int(v)
        send_message_to_info_chat(bot_token=bot_token, info_chat_id=int(info_chat_id), text=text or "")
    except Exception:
        return


def send_document_to_user(
    *,
    bot_token: str,
    user_telegram_id: int,
    filename: str,
    content: bytes,
    caption: str | None = None,
    parse_mode: str | None = None,
    dup_to_log: bool = True,
) -> dict[str, Any]:
    """
    Публичная функция-обёртка для отправки файла (document) конкретному пользователю.

    Использует Telegram Bot API: sendDocument.
    """
    try:
        chat_id = int(user_telegram_id)
    except Exception:
        return {"ok": False, "error": "bad_user_telegram_id"}
    return send_bot_document(
        bot_token=bot_token,
        chat_id=chat_id,
        filename=str(filename or "file.bin"),
        content=content or b"",
        caption=caption,
        parse_mode=parse_mode,
        dup_to_log=dup_to_log,
    )


def try_notify_task_finished(
    *,
    task_dir: Path,
    uid: str,
    site_url: str,
    ok: bool,
    bot_token: str,
    base_url: str,
    zip_bytes: bytes | None,
    zip_filename: str | None = None,
    error_text: str | None = None,
) -> None:
    """
    Best-effort: читает RESULT_TASKS/<uid>/meta.json и отправляет пользователю сообщение о завершении генерации.
    В обоих случаях пытается прикрепить ZIP-архив (document).
    Ничего не рейзит.
    """
    try:
        meta_path = Path(task_dir) / "meta.json"
        if not meta_path.is_file():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            return
        tg_id = meta.get("user_telegram_id")
        if tg_id is None:
            return
        tg_id_int = int(tg_id)
        user_account = meta.get("user_account")

        domain = str(site_url or "").strip()
        base_url_norm = str(base_url or "").strip() or "http://127.0.0.1:5000"
        base_url_norm = base_url_norm.rstrip("/")

        status_line = "🟩 Генерация успешно завершена" if ok else "🟠 Генерация завершилась с ошибкой"
        user_label = _format_user_label(user_telegram_id=tg_id_int, user_account=str(user_account) if user_account else None)
        _dup_outgoing_to_log_chat(
            header=f"Пользователь {user_label} завершил генерацию:",
            body=f"{status_line}\nСайт: {domain}\nUID: {uid}",
            bot_token=bot_token,
        )

        extracted_err = ""
        if not ok:
            # 1) Пробуем извлечь из result_code.ts (наиболее информативно)
            try:
                rc_path = Path(task_dir) / "result_code.ts"
                if rc_path.is_file():
                    extracted_err = _extract_error_snippet_from_text(rc_path.read_text(encoding="utf-8"))
            except Exception:
                extracted_err = ""
            # 2) fallback: из переданного error_text
            if not extracted_err and error_text:
                extracted_err = _extract_error_snippet_from_text(str(error_text))

        # Telegram ограничивает длину caption для документов, поэтому:
        # - успех: обычный короткий caption (plain text)
        # - ошибка: HTML caption с <pre>...</pre>, но с обрезанием
        if ok:
            caption_lines = [
                status_line,
                f"Сайт: {domain}",
                f"UID задачи: {uid}",
                f"Результат: {base_url_norm}/main_page_3/{uid}/",
                # f"ZIP (ссылка): {base_url_norm}/download/all_files_zip/{uid}",
            ]
            caption = "\n".join(caption_lines).strip()
            caption_parse_mode = None
        else:
            # Базовая часть caption (HTML)
            base_caption = "\n".join(
                [
                    _escape_html(status_line),
                    f"Сайт: {_escape_html(domain)}",
                    f"UID задачи: {_escape_html(uid)}",
                    f"Результат: {_escape_html(base_url_norm + '/main_page_3/' + str(uid) + '/')}",
                    # f"ZIP (ссылка): {_escape_html(base_url_norm + '/download/all_files_zip/' + str(uid))}",
                ]
            ).strip()

            err_for_block = extracted_err or (str(error_text).strip() if error_text else "")
            err_for_block = err_for_block.strip()
            # Держим запас под теги <pre></pre> и остальной текст.
            # Лимит Telegram caption ≈ 1024 символа; берём чуть меньше, чтобы точно влезло.
            max_caption = 950
            overhead = len(base_caption) + len("\n\nОшибка:\n<pre></pre>")
            remaining = max(0, max_caption - overhead)
            err_trimmed = _trim_to_max_chars(err_for_block, remaining)
            caption = f"{base_caption}\n\nОшибка:\n<pre>{_escape_html(err_trimmed)}</pre>".strip()
            caption_parse_mode = "HTML"

        if zip_bytes:
            fname = str(zip_filename or f"APSP_gen_{uid}.zip")
            resp = send_document_to_user(
                bot_token=bot_token,
                user_telegram_id=tg_id_int,
                filename=fname,
                content=zip_bytes,
                caption=caption,
                parse_mode=caption_parse_mode,
                dup_to_log=False,
            )
            # если документ не ушёл — хотя бы текст
            if not isinstance(resp, dict) or not resp.get("ok"):
                send_bot_message(
                    bot_token=bot_token,
                    chat_id=tg_id_int,
                    text=caption,
                    parse_mode=caption_parse_mode,
                    dup_to_log=False,
                )
        else:
            send_bot_message(
                bot_token=bot_token,
                chat_id=tg_id_int,
                text=caption,
                parse_mode=caption_parse_mode,
                dup_to_log=False,
            )
    except Exception:
        return


def try_notify_task_started(*, task_dir: Path, uid: str, site_url: str, bot_token: str, base_url: str) -> None:
    """
    Best-effort: читает RESULT_TASKS/<uid>/meta.json и отправляет пользователю сообщение о старте генерации.
    Ничего не рейзит.
    """
    try:
        meta_path = Path(task_dir) / "meta.json"
        if not meta_path.is_file():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            return
        tg_id = meta.get("user_telegram_id")
        if tg_id is None:
            return
        tg_id_int = int(tg_id)
        user_account = meta.get("user_account")
        domain = str(site_url or "").strip()
        base_url_norm = str(base_url or "").strip() or "http://127.0.0.1:5000"
        base_url_norm = base_url_norm.rstrip("/")
        task_url = f"{base_url_norm}/main_page_2/{uid}/"
        # Важно: для корректного отображения inline-code используем HTML parse_mode.
        # Также экранируем переменные, т.к. URL может содержать &, <, > и т.п.
        msg = "\n".join(
            [
                f"🚀 Запустили генерацию парсера для: {_escape_html(domain)}",
                f"UID задачи: <code>{_escape_html(uid)}</code>",
                "Ожидаемое время генерации ~15 минут",
                f"Наблюдать за прогрессом можно по ссылке: {_escape_html(task_url)}",
                "После завершения генерации в этот чат придёт сообщение с результатом",
            ]
        ).strip()
        user_label = _format_user_label(user_telegram_id=tg_id_int, user_account=str(user_account) if user_account else None)
        _dup_outgoing_to_log_chat(
            header=f"Пользователь {user_label} начал генерацию:",
            body=f"Сайт: {domain}\nUID: {uid}",
            bot_token=bot_token,
        )
        send_bot_message(
            bot_token=bot_token,
            chat_id=tg_id_int,
            text=msg,
            parse_mode="HTML",
            dup_to_log=False,
        )
    except Exception:
        return


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


def send_bot_message(
    *,
    bot_token: str,
    chat_id: int,
    text: str,
    parse_mode: str | None = None,
    dup_to_log: bool = True,
) -> dict[str, Any]:
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
    payload = {
        "chat_id": str(int(chat_id)),
        "text": text,
        "disable_web_page_preview": "true",
    }
    if parse_mode:
        payload["parse_mode"] = str(parse_mode)
    body = urlencode(payload).encode("utf-8")

    # best-effort: дубль в log_chat (для всех сообщений "не в диагностические чаты")
    if dup_to_log and not _is_diagnostic_chat_id(chat_id):
        _dup_outgoing_to_log_chat(
            header=f"Пользователю tg_id={int(chat_id)} ушло сообщение:",
            body=text,
            bot_token=bot_token,
        )

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


def send_bot_document(
    *,
    bot_token: str,
    chat_id: int,
    filename: str,
    content: bytes,
    caption: str | None = None,
    parse_mode: str | None = None,
    content_type: str = "application/zip",
    dup_to_log: bool = True,
) -> dict[str, Any]:
    """
    Отправка файла (document) через Telegram Bot API без внешних зависимостей (requests не нужен).
    """
    if not bot_token:
        return {"ok": False, "error": "bot_token_missing"}
    if not chat_id:
        return {"ok": False, "error": "chat_id_missing"}
    if content is None:
        content = b""

    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    boundary = "----apsp_boundary_" + secrets.token_hex(16)

    # best-effort: дубль в log_chat (для всех документов "не в диагностические чаты")
    if dup_to_log and not _is_diagnostic_chat_id(chat_id):
        cap = (caption or "").strip()
        body = f"Файл: {filename}"
        if cap:
            body += f"\nCaption:\n{cap}"
        _dup_outgoing_to_log_chat(
            header=f"Пользователю tg_id={int(chat_id)} ушёл документ:",
            body=body,
            bot_token=bot_token,
        )

    def _field(name: str, value: str | None) -> bytes:
        v = "" if value is None else str(value)
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{v}\r\n"
        ).encode("utf-8")

    head = b"".join(
        [
            _field("chat_id", str(int(chat_id))),
            (_field("caption", caption) if caption else b""),
            (_field("parse_mode", parse_mode) if parse_mode else b""),
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8"),
        ]
    )
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + content + tail

    req = urllib_request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=30) as resp:
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


