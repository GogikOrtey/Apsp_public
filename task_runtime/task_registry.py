from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import os
import json
from pathlib import Path
import re
import threading
import traceback
from typing import Any
from uuid import uuid4
import zipfile

from task_runtime.playwright_pool import PlaywrightPool
from task_runtime.stop_store import UserStopException, clear_stop, get_stop_reason, USER_STOP_MESSAGE
from task_runtime.timeout_store import TaskTimeoutException, TASK_TIMEOUT_MESSAGE, _normalize_timeout_seconds


@dataclass
class TaskInfo:
    uid: str
    url: str
    task_dir: Path
    status: str  # created|running|done|error
    error: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class TaskRegistry:
    def __init__(
        self,
        *,
        result_tasks_dir: Path,
        max_workers: int = 10,
        headless: bool = True,
        max_attempts: int | None = None,
    ) -> None:
        self._result_tasks_dir = Path(result_tasks_dir)
        self._result_tasks_dir.mkdir(parents=True, exist_ok=True)
        self._pool = PlaywrightPool(max_workers=max_workers, headless=headless)
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.Lock()
        self._uid_re = re.compile(r"^[0-9a-f]{12}$", re.IGNORECASE)
        self._meta_schema_version = 1
        self._runners: dict[str, Any] = {}
        self._max_attempts = self._normalize_max_attempts(max_attempts)
        # Self-restart policy (для Docker): после N завершённых задач — перезапуск контейнера.
        self._finished_tasks_since_boot = 0
        self._restart_pending_reason: str | None = None
        self._restart_after_tasks = self._normalize_restart_after_tasks()

    def _normalize_restart_after_tasks(self) -> int:
        """
        После скольких завершённых задач просить рестарт контейнера.

        Управляется env `APSP_RESTART_AFTER_TASKS` (в docker-compose по умолчанию = 50).
        Вне контейнера по умолчанию выключено (0), чтобы не мешать локальной разработке.
        """
        try:
            from task_runtime.container_restart import is_running_in_container  # noqa: WPS433
        except Exception:
            is_running_in_container = lambda: False  # type: ignore

        default = 50 if bool(is_running_in_container()) else 0
        raw = os.environ.get("APSP_RESTART_AFTER_TASKS")
        if raw is None:
            return int(default)
        try:
            v = int(str(raw).strip())
        except Exception:
            v = int(default)
        return max(0, int(v))

    def _note_task_finished_and_maybe_restart(self, *, reason: str) -> None:
        """
        Учитывает факт финального завершения задачи и (опционально) инициирует рестарт контейнера.
        """
        threshold = int(self._restart_after_tasks or 0)
        if threshold <= 0:
            return

        should_restart_now = False
        restart_reason = ""
        with self._lock:
            self._finished_tasks_since_boot += 1
            finished = int(self._finished_tasks_since_boot)

            active = sum(1 for t in self._tasks.values() if t.status == "running")

            # Если ранее уже накопили рестарт — выполняем при первой возможности (когда активных 0).
            if self._restart_pending_reason and active <= 0:
                should_restart_now = True
                restart_reason = self._restart_pending_reason
                self._restart_pending_reason = None
            # Новый триггер: достигли порога.
            elif finished >= threshold:
                if active <= 0:
                    should_restart_now = True
                    restart_reason = f"restart_after_tasks reached: {finished}/{threshold}; last_reason={reason}"
                else:
                    # Ждём, пока активные задачи закончатся, чтобы не ронять их посередине.
                    self._restart_pending_reason = f"restart_after_tasks reached: {finished}/{threshold}; pending; last_reason={reason}"

        if should_restart_now:
            try:
                from task_runtime.container_restart import request_container_restart  # noqa: WPS433

                request_container_restart(restart_reason)
            except Exception:
                return

    def _normalize_max_attempts(self, max_attempts: int | None) -> int:
        """
        Максимальное количество попыток на один UID.

        По умолчанию — 1 (без автоповторов).
        Чтобы быстро вернуть ретраи: выставить env `APSP_TASK_MAX_ATTEMPTS=3`
        (или передать max_attempts при создании TaskRegistry).
        """
        if max_attempts is None:
            max_attempts = os.getenv("APSP_TASK_MAX_ATTEMPTS", "1")
        try:
            max_attempts = int(max_attempts)
        except Exception:
            max_attempts = 1
        return max(1, int(max_attempts))

    @property
    def max_attempts(self) -> int:
        return int(self._max_attempts)

    @property
    def max_workers(self) -> int:
        return self._pool._max_workers

    def get_active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if t.status == "running")

    def _now(self) -> datetime:
        return datetime.now()

    def _dt_human(self, dt: datetime) -> str:
        # Человекочитаемо и стабильно (без таймзон — проект сейчас работает локально).
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _dt_ts(self, dt: datetime) -> float:
        return float(dt.timestamp())

    def _normalize_uid(self, uid: str) -> str:
        return (uid or "").strip().lower()

    def _is_valid_uid(self, uid: str) -> bool:
        uid_norm = self._normalize_uid(uid)
        return bool(self._uid_re.match(uid_norm))

    def _task_dir_for_uid(self, uid: str) -> Path:
        return self._result_tasks_dir / self._normalize_uid(uid)

    def _meta_path_for_uid(self, uid: str) -> Path:
        return self._task_dir_for_uid(uid) / "meta.json"

    def _runtime_to_meta_status(self, runtime_status: str) -> str:
        # meta.json должен содержать только WORK/COMPLETED/FAILED
        if runtime_status in {"done"}:
            return "COMPLETED"
        if runtime_status in {"error"}:
            return "FAILED"
        return "WORK"

    def _load_meta(self, uid: str) -> dict[str, Any] | None:
        path = self._meta_path_for_uid(uid)
        try:
            if not path.is_file():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _save_meta(self, uid: str, meta: dict[str, Any]) -> None:
        path = self._meta_path_for_uid(uid)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Best-effort атомарность
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def _init_meta(
        self,
        *,
        uid: str,
        url: str,
        user_telegram_id: int | None = None,
        user_account: str | None = None,
        selected_fields: list[str] | None = None,
    ) -> None:
        now = self._now()
        meta = {
            "schema_version": self._meta_schema_version,
            "uid": self._normalize_uid(uid),
            "url": str(url or ""),
            "max_attempts": self.max_attempts,
            # Время создания/регистрации задачи (доп. поле)
            "created_at_human": self._dt_human(now),
            "created_at_ts": self._dt_ts(now),
            # Требуемые поля
            "started_at_human": "",
            "started_at_ts": None,
            "finished_at_human": "",
            "finished_at_ts": None,
            "status": "WORK",
            "attempts": 0,
            # Доп. полезные поля
            "runtime_status": "created",
            "last_error": None,
            # Причина завершения (для корректных сообщений в UI/логах/Telegram)
            # Возможные значения: success|error|timeout|user_stop (или None/пусто для старых задач)
            "finish_reason": None,
            "stopped_by_user": False,
        }
        # Связь с аккаунтом пользователя (best-effort, для уведомлений)
        if user_telegram_id is not None:
            try:
                meta["user_telegram_id"] = int(user_telegram_id)
            except Exception:
                meta["user_telegram_id"] = None
        if user_account is not None:
            try:
                meta["user_account"] = str(user_account)
            except Exception:
                meta["user_account"] = None

        # Выбранные пользователем поля (best-effort). Важно для фильтрации all_fields на этапе генерации.
        if selected_fields is not None:
            try:
                meta["selected_fields"] = [str(x).strip() for x in selected_fields if str(x).strip()]
            except Exception:
                meta["selected_fields"] = None
        self._save_meta(uid, meta)

    def _update_meta_on_start(self, uid: str) -> tuple[dict[str, Any], bool]:
        now = self._now()
        meta = self._load_meta(uid) or {}

        attempts = meta.get("attempts")
        try:
            attempts = int(attempts)
        except Exception:
            attempts = 0
        # Ограничение: 1..max_attempts попыток запуска (по умолчанию 1)
        if attempts >= self.max_attempts:
            meta["attempts"] = self.max_attempts
            meta["max_attempts"] = self.max_attempts
            meta.setdefault("schema_version", self._meta_schema_version)
            meta.setdefault("uid", self._normalize_uid(uid))
            self._save_meta(uid, meta)
            return meta, False

        attempts += 1

        # started_at — первый старт, last_started_at — последний (доп. поле)
        if not meta.get("started_at_ts"):
            meta["started_at_human"] = self._dt_human(now)
            meta["started_at_ts"] = self._dt_ts(now)
        meta["last_started_at_human"] = self._dt_human(now)
        meta["last_started_at_ts"] = self._dt_ts(now)

        meta["attempts"] = attempts
        meta["max_attempts"] = self.max_attempts
        meta["status"] = "WORK"
        meta["runtime_status"] = "running"
        # Сбрасываем причину завершения при новом старте (на случай ретраев/перезапусков)
        meta["finish_reason"] = None
        meta["stopped_by_user"] = False
        meta.setdefault("schema_version", self._meta_schema_version)
        meta.setdefault("uid", self._normalize_uid(uid))
        self._save_meta(uid, meta)
        return meta, True

    def _update_meta_on_finish(
        self,
        uid: str,
        *,
        runtime_status: str,
        error: str | None,
        finish_reason: str | None = None,
    ) -> None:
        now = self._now()
        meta = self._load_meta(uid) or {}
        meta["finished_at_human"] = self._dt_human(now)
        meta["finished_at_ts"] = self._dt_ts(now)
        meta["status"] = self._runtime_to_meta_status(runtime_status)
        meta["runtime_status"] = runtime_status
        meta["last_error"] = error
        meta["finish_reason"] = finish_reason
        meta["stopped_by_user"] = bool(finish_reason == "user_stop")
        meta.setdefault("schema_version", self._meta_schema_version)
        meta.setdefault("uid", self._normalize_uid(uid))
        self._save_meta(uid, meta)

    def _update_meta_last_error(self, uid: str, error: str | None) -> None:
        """
        Best-effort: обновляет last_error без смены runtime_status/status.
        Нужен для отображения причины падения между ретраями, не переводя задачу в FAILED.
        """
        meta = self._load_meta(uid) or {}
        meta["last_error"] = error
        meta.setdefault("schema_version", self._meta_schema_version)
        meta.setdefault("uid", self._normalize_uid(uid))
        try:
            self._save_meta(uid, meta)
        except Exception:
            pass

    def _write_final_error_result_code(self, info: TaskInfo, error_text: str) -> None:
        """
        Пишет текст ошибки в result_code.ts (в папку задачи), чтобы UI и скачивание работали предсказуемо.
        """
        try:
            from new_program.build_final_code import result_file_JS

            result_file_JS(error_text, task_dir=info.task_dir)
            return
        except Exception:
            pass

        try:
            info.task_dir.mkdir(parents=True, exist_ok=True)
            (info.task_dir / "result_code.ts").write_text(error_text, encoding="utf-8")
        except Exception:
            pass

    def _write_status_file(self, info: TaskInfo, status: str) -> None:
        """
        Creates a status text file in the task directory based on the outcome.
        status: "success" or "failed"
        """
        try:
            info.task_dir.mkdir(parents=True, exist_ok=True)
            if status == "success":
                (info.task_dir / "RESULT_SUCSESS.txt").write_text("RESULT_SUCSESS. Генерация успешна", encoding="utf-8")
            elif status == "failed":
                (info.task_dir / "RESULT_FAILED.txt").write_text("RESULT_FAILED. Генерация неудачна. Причины - описаны в result_code.ts", encoding="utf-8")
        except Exception:
            pass

    def _append_task_output_log(self, info: TaskInfo, text: str) -> None:
        try:
            info.task_dir.mkdir(parents=True, exist_ok=True)
            with open(info.task_dir / "output.log", "a", encoding="utf-8") as f:
                f.write(text)
                if not text.endswith("\n"):
                    f.write("\n")
                f.flush()
        except Exception:
            pass

    def _ensure_zip_required_files(self, info: TaskInfo) -> None:
        """
        Best-effort: гарантирует наличие файлов, которые считаются "обязательными" для ZIP.
        Это нужно, чтобы скачивание ZIP и отправка ZIP в Telegram были предсказуемыми даже при ранних падениях.
        """
        try:
            info.task_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

        # Логи могут отсутствовать при ранних исключениях — создаём пустые, чтобы ZIP не ломался.
        for name in ("output.log", "useful_log.log", "chat_output.log"):
            try:
                p = info.task_dir / name
                if not p.is_file():
                    p.write_text("", encoding="utf-8")
            except Exception:
                pass

        # result_code.ts должен существовать (и в успехе, и в фейле). Если нет — пишем заглушку.
        try:
            p = info.task_dir / "result_code.ts"
            if not p.is_file():
                p.write_text("// result_code.ts missing\n", encoding="utf-8")
        except Exception:
            pass

    def _build_task_zip_bytes(self, info: TaskInfo) -> bytes | None:
        """
        Собирает ZIP в памяти по тому же составу файлов, что `/download/all_files_zip/<uid>`.
        Возвращает bytes или None (если что-то пошло не так).
        """
        try:
            required = [
                ("result_code.ts", info.task_dir / "result_code.ts"),
                ("output.log", info.task_dir / "output.log"),
                ("useful_log.log", info.task_dir / "useful_log.log"),
                ("chat_output.log", info.task_dir / "chat_output.log"),
            ]
            optional = [
                ("meta.json", info.task_dir / "meta.json"),
                ("RESULT_SUCSESS.txt", info.task_dir / "RESULT_SUCSESS.txt"),
                ("RESULT_FAILED.txt", info.task_dir / "RESULT_FAILED.txt"),
            ]
            missing = [name for name, p in required if not p.is_file()]
            if missing:
                # после _ensure_zip_required_files() не должно случаться, но оставляем safety
                return None

            buf = BytesIO()
            with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
                for arcname, full_path in required:
                    zf.write(str(full_path), arcname=arcname)
                for arcname, full_path in optional:
                    try:
                        if full_path.is_file():
                            zf.write(str(full_path), arcname=arcname)
                    except Exception:
                        pass
            return buf.getvalue()
        except Exception:
            return None

    def _try_notify_task_finished_telegram(self, info: TaskInfo, *, ok: bool, error_text: str | None) -> None:
        """
        Best-effort: отправляет уведомление о завершении + ZIP в Telegram, если:
        - есть APSP_TELEGRAM_BOT_TOKEN
        - в meta.json есть user_telegram_id
        """
        try:
            bot_token = (os.environ.get("APSP_TELEGRAM_BOT_TOKEN", "") or "").strip()
            if not bot_token:
                return
            base_url = (os.environ.get("APSP_BASE_URL", "http://127.0.0.1:5000") or "").strip()

            self._ensure_zip_required_files(info)
            zip_bytes = self._build_task_zip_bytes(info)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            zip_name = f"APSP_gen_{info.uid}_{ts}.zip"

            import telegram_connect

            telegram_connect.try_notify_task_finished(
                task_dir=info.task_dir,
                uid=str(info.uid),
                site_url=str(info.url),
                ok=bool(ok),
                bot_token=bot_token,
                base_url=base_url,
                zip_bytes=zip_bytes,
                zip_filename=zip_name,
                error_text=error_text,
            )
        except Exception:
            return

    def _submit_run(self, uid: str, runner: Any, info: TaskInfo) -> None:
        fut = self._pool.submit(lambda browser: runner(browser, info))

        def _done_callback(f) -> None:
            self._on_future_done(uid, runner, f)

        fut.add_done_callback(_done_callback)

    def _on_future_done(self, uid: str, runner: Any, f) -> None:
        """
        Обработчик завершения попытки запуска.

        Важно: делаем до `max_attempts` попыток (по умолчанию 1, т.е. без ретраев).
        Между попытками задача остаётся в статусе running, чтобы UI не переходил на страницу результата раньше времени.
        """
        try:
            _ = f.result()
            with self._lock:
                info2 = self._tasks.get(uid)
                if info2 is None:
                    return
                info2.status = "done"
                info2.finished_at = self._now()
                info2.error = None
            
            self._write_status_file(info2, "success")

            try:
                self._update_meta_on_finish(uid, runtime_status="done", error=None, finish_reason="success")
            except Exception:
                pass

            # Best-effort: уведомление в Telegram + ZIP
            self._try_notify_task_finished_telegram(info2, ok=True, error_text=None)
            # runner больше не нужен
            with self._lock:
                self._runners.pop(uid, None)
            # Self-restart (docker): after N finished tasks
            self._note_task_finished_and_maybe_restart(reason="success")
            return
        except Exception as exc:  # noqa: BLE001
            err_str = str(exc)

            # Пользовательская остановка: без ретраев, сразу финальный error/FAILED.
            stop_reason = None
            try:
                stop_reason = get_stop_reason(uid)
            except Exception:
                stop_reason = None

            if isinstance(exc, UserStopException) or (stop_reason and stop_reason in err_str) or (err_str == USER_STOP_MESSAGE):
                final_reason = stop_reason or (err_str or USER_STOP_MESSAGE)
                print(f"[TaskRegistry] User stop detected for uid={uid}, setting status='error'")
                with self._lock:
                    info2 = self._tasks.get(uid)
                    if info2 is None:
                        print(f"[TaskRegistry] WARNING: info2 is None for uid={uid}, cannot set status")
                        return
                    info2.status = "error"
                    info2.finished_at = self._now()
                    info2.error = final_reason
                    print(f"[TaskRegistry] Status set to 'error' for uid={uid}")

                self._write_status_file(info2, "failed")

                # Пишем лаконичную ошибку в result_code.ts
                msg = str(final_reason or USER_STOP_MESSAGE).strip()
                if msg.startswith(USER_STOP_MESSAGE):
                    error_text = f"📍 {msg}\n"
                else:
                    error_text = f"📍 Остановлено пользователем: {msg}\n"
                self._write_final_error_result_code(info2, error_text)
                try:
                    self._append_task_output_log(info2, f"[{self._dt_human(self._now())}] Остановлено пользователем: {final_reason}")
                except Exception:
                    pass

                try:
                    self._update_meta_on_finish(uid, runtime_status="error", error=final_reason, finish_reason="user_stop")
                except Exception:
                    pass

                # Best-effort: уведомление в Telegram + ZIP
                self._try_notify_task_finished_telegram(info2, ok=False, error_text=final_reason)

                with self._lock:
                    self._runners.pop(uid, None)
                self._note_task_finished_and_maybe_restart(reason="user_stop")
                return

            # Таймаут выполнения: без ретраев, сразу финальный error/FAILED.
            if isinstance(exc, TaskTimeoutException) or (err_str == TASK_TIMEOUT_MESSAGE):
                # Добавляем инфо о длительности (в минутах)
                try:
                    limit_s = _normalize_timeout_seconds(None)
                    limit_min = int(limit_s / 60)
                    msg_suffix = f" ({limit_min} мин)"
                except Exception:
                    msg_suffix = ""

                base_reason = err_str or TASK_TIMEOUT_MESSAGE
                # Если в тексте ошибки уже есть минуты — не дублируем (на случай если текст поменяется в будущем)
                if "мин)" not in base_reason:
                    final_reason = f"{base_reason}{msg_suffix}"
                else:
                    final_reason = base_reason

                with self._lock:
                    info2 = self._tasks.get(uid)
                    if info2 is None:
                        return
                    info2.status = "error"
                    info2.finished_at = self._now()
                    info2.error = final_reason

                self._write_status_file(info2, "failed")

                # Пишем лаконичную ошибку в result_code.ts
                self._write_final_error_result_code(info2, f"🟠{final_reason}\n")

                try:
                    self._append_task_output_log(info2, f"[{self._dt_human(self._now())}] timeout: {final_reason}")
                except Exception:
                    pass

                try:
                    self._update_meta_on_finish(uid, runtime_status="error", error=final_reason, finish_reason="timeout")
                except Exception:
                    pass

                # Best-effort: уведомление в Telegram + ZIP
                self._try_notify_task_finished_telegram(info2, ok=False, error_text=final_reason)

                with self._lock:
                    self._runners.pop(uid, None)
                self._note_task_finished_and_maybe_restart(reason="timeout")
                return

            # Сохраняем причину последней ошибки, не переводя задачу в FAILED раньше времени
            self._update_meta_last_error(uid, err_str)

            # Запишем в per-task output.log маркер падения (чтобы в UI было видно, что была попытка/ошибка).
            try:
                info_tmp = self.get(uid)
                if info_tmp is not None:
                    meta_tmp = self._load_meta(uid) or {}
                    attempt_no = meta_tmp.get("attempts")
                    self._append_task_output_log(
                        info_tmp,
                        f"[{self._dt_human(self._now())}] attempt {attempt_no}/{self.max_attempts} failed: {err_str}",
                    )
            except Exception:
                pass

            # Пробуем ретрай (до max_attempts попыток суммарно)
            try:
                _, allowed = self._update_meta_on_start(uid)
            except Exception:
                allowed = False

            if allowed:
                # Оставляем задачу running и запускаем ещё раз
                with self._lock:
                    info2 = self._tasks.get(uid)
                    if info2 is None:
                        return
                    info2.status = "running"
                    info2.started_at = self._now()
                    info2.error = err_str
                try:
                    self._append_task_output_log(info2, f"[{self._dt_human(self._now())}] retrying...")
                except Exception:
                    pass
                self._submit_run(uid, runner, info2)
                return

            # Финальный фейл (попытки исчерпаны)
            prefix_block = ""
            try:
                prefix_block = str(getattr(exc, "apsp_prefix_block", "") or "").strip()
            except Exception:
                prefix_block = ""

            error_text = "🟠 Ошибка генерации: 🟠\n\n"
            if prefix_block:
                error_text += prefix_block + "\n\n"

            error_text += "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            with self._lock:
                info2 = self._tasks.get(uid)
                if info2 is None:
                    return
                info2.status = "error"
                info2.finished_at = self._now()
                info2.error = err_str

            self._write_status_file(info2, "failed")

            # Пишем результат-ошибку в result_code.ts (чтобы main_page_3 и скачивание работали)
            self._write_final_error_result_code(info2, error_text)
            try:
                self._append_task_output_log(info2, f"[{self._dt_human(self._now())}] final failure (attempts exhausted)")
            except Exception:
                pass

            try:
                self._update_meta_on_finish(uid, runtime_status="error", error=err_str, finish_reason="error")
            except Exception:
                pass

            # Best-effort: уведомление в Telegram + ZIP
            self._try_notify_task_finished_telegram(info2, ok=False, error_text=err_str)

            with self._lock:
                self._runners.pop(uid, None)
            self._note_task_finished_and_maybe_restart(reason="error")

    def _rehydrate_from_disk(self, uid: str) -> TaskInfo | None:
        """
        Best-effort восстановление TaskInfo по папке результатов.

        Нужен для сценария: сервер перезапустили, а RESULTS_TASKS/<uid> уже есть.
        """
        if not self._is_valid_uid(uid):
            return None
        task_dir = self._task_dir_for_uid(uid)
        if not task_dir.is_dir():
            return None

        meta = self._load_meta(uid) or {}
        url = str(meta.get("url") or "")
        runtime_status = str(meta.get("runtime_status") or "")
        if runtime_status not in {"created", "running", "done", "error"}:
            # fallback для старых задач без meta.json
            runtime_status = ""

        finished_at = None
        try:
            ts = meta.get("finished_at_ts")
            if isinstance(ts, (int, float)):
                finished_at = datetime.fromtimestamp(float(ts))
        except Exception:
            finished_at = None

        if finished_at is None:
            try:
                finished_at = datetime.fromtimestamp(task_dir.stat().st_mtime)
            except Exception:
                finished_at = None

        # Если статус неизвестен — считаем done (как раньше), чтобы UI мог открыть результаты.
        if not runtime_status:
            runtime_status = "done"

        info = TaskInfo(
            uid=self._normalize_uid(uid),
            url=url,
            task_dir=task_dir,
            status=runtime_status,
            created_at=None,
            started_at=None,
            finished_at=finished_at,
            error=(str(meta.get("last_error")) if meta.get("last_error") else None),
        )
        with self._lock:
            # Не перетираем существующий runtime-task, если он уже есть.
            self._tasks.setdefault(info.uid, info)
            return self._tasks.get(info.uid)

    @property
    def result_tasks_dir(self) -> Path:
        return self._result_tasks_dir

    def create(
        self,
        url: str,
        *,
        user_telegram_id: int | None = None,
        user_account: str | None = None,
        selected_fields: list[str] | None = None,
    ) -> TaskInfo:
        uid = uuid4().hex[:12]
        task_dir = self._result_tasks_dir / uid
        task_dir.mkdir(parents=True, exist_ok=True)
        # На всякий случай сбрасываем стоп-флаг для нового UID.
        try:
            clear_stop(uid)
        except Exception:
            pass
        # meta.json создаём сразу, чтобы задача была видна после рестарта.
        try:
            self._init_meta(
                uid=uid,
                url=str(url),
                user_telegram_id=user_telegram_id,
                user_account=user_account,
                selected_fields=selected_fields,
            )
        except Exception:
            pass

        info = TaskInfo(
            uid=uid,
            url=str(url),
            task_dir=task_dir,
            status="created",
            created_at=self._now(),
        )
        with self._lock:
            self._tasks[uid] = info
        return info

    def warmup(self) -> None:
        """Start Playwright pool so at least one browser is opened with the service."""
        self._pool.start()

    def get(self, uid: str) -> TaskInfo | None:
        uid_norm = self._normalize_uid(uid)
        with self._lock:
            info = self._tasks.get(uid_norm)
        if info is not None:
            return info
        return self._rehydrate_from_disk(uid_norm)

    def exists(self, uid: str) -> bool:
        uid_norm = self._normalize_uid(uid)
        with self._lock:
            if uid_norm in self._tasks:
                return True
        # fallback: после рестарта реестр в памяти пуст, но папка результатов может существовать
        if not self._is_valid_uid(uid_norm):
            return False
        return self._task_dir_for_uid(uid_norm).is_dir()

    def start(self, uid: str, runner: Any) -> None:
        """
        runner: Callable[[Browser, TaskInfo], Any]
        """
        uid = self._normalize_uid(uid)
        with self._lock:
            info = self._tasks.get(uid)
            if info is None:
                raise KeyError(uid)
            if info.status in {"running"}:
                return
            if info.status in {"done"}:
                return
            # Если задача была в error — разрешаем повторный старт по тому же uid (через новую попытку).
            # Ограничение количества попыток контролируется _update_meta_on_start().

            # Обновляем meta.json и считаем попытки запуска (1..max_attempts).
            try:
                _, allowed = self._update_meta_on_start(uid)
                if not allowed:
                    return
            except Exception:
                pass

            # Перед новой попыткой сбрасываем стоп-флаг, чтобы можно было рестартовать.
            try:
                clear_stop(uid)
            except Exception:
                pass

            info.status = "running"
            info.started_at = self._now()
            info.error = None
            self._runners[uid] = runner

        self._submit_run(uid, runner, info)

    def resume_stale_work_task(
        self,
        uid: str,
        runner: Any,
        *,
        max_total_attempts: int = 2,
        app_start_time_ts: float | None = None,
    ) -> str:
        """
        Форсированный "подхват" зависшей задачи после рестарта сервиса.

        Задача считается кандидатом на подхват снаружи (в Flask), если в meta.json:
        - status == "WORK"
        - last_started_at_ts < APP_START_TIME (время старта текущего процесса)

        Здесь мы дополнительно:
        - строго ограничиваем общее число запусков по meta["attempts"] (по умолчанию 2: старт + 1 перезапуск)
        - НЕ опираемся на TaskRegistry.max_attempts (он может быть = 1 и это ок)

        Returns:
            "restarted" | "failed" | "skipped"
        """
        uid = self._normalize_uid(uid)
        if not self._is_valid_uid(uid):
            return "skipped"

        # Подтянем задачу в память (best-effort).
        info = self.get(uid)
        if info is None:
            return "skipped"

        meta = self._load_meta(uid) or {}
        meta_status = str(meta.get("status") or "").strip().upper()
        if meta_status != "WORK":
            return "skipped"

        # Проверка "действительно stale": last_started_at_ts должен быть меньше старта текущего процесса.
        if app_start_time_ts is not None:
            try:
                last_started_at_ts = float(meta.get("last_started_at_ts") or 0)
            except Exception:
                last_started_at_ts = 0.0
            if not (last_started_at_ts > 0 and last_started_at_ts < float(app_start_time_ts)):
                return "skipped"

        try:
            max_total_attempts = int(max_total_attempts)
        except Exception:
            max_total_attempts = 2
        max_total_attempts = max(1, max_total_attempts)

        # attempts в meta — источник правды для этой логики.
        attempts = meta.get("attempts")
        try:
            attempts = int(attempts)
        except Exception:
            attempts = 0

        # Если уже был старт + перезапуск (attempts>=2) и задача всё ещё WORK — считаем сервис упал повторно.
        if attempts >= max_total_attempts:
            reason = (
                "Генерация неудачна по причине падения сервиса: "
                "задача была в статусе WORK при рестарте приложения и уже перезапускалась."
            )
            self._finalize_task_as_service_crash_failed(uid, info, reason)
            return "failed"

        # Иначе — делаем ровно один форсированный рестарт (attempts += 1).
        allowed = self._force_update_meta_on_start(uid, max_total_attempts=max_total_attempts)
        if not allowed:
            reason = (
                "Генерация неудачна по причине падения сервиса: "
                "не удалось выполнить перезапуск зависшей задачи."
            )
            self._finalize_task_as_service_crash_failed(uid, info, reason)
            return "failed"

        # Best-effort: уведомление пользователю (Telegram), что сервис перезапущен и задача стартует заново.
        try:
            bot_token = (os.environ.get("APSP_TELEGRAM_BOT_TOKEN", "") or "").strip()
            if bot_token:
                base_url = (os.environ.get("APSP_BASE_URL", "http://127.0.0.1:5000") or "").strip()
                import telegram_connect  # noqa: WPS433

                telegram_connect.try_notify_task_service_restarted_resume(
                    task_dir=info.task_dir,
                    uid=str(uid),
                    bot_token=bot_token,
                    base_url=base_url,
                )
        except Exception:
            pass

        # Перед рестартом сбрасываем stop-флаг, чтобы задача не упала мгновенно как user_stop.
        try:
            clear_stop(uid)
        except Exception:
            pass

        # Обходим защиту start(): у stale-задач meta.runtime_status часто "running",
        # и start() бы не запустил её повторно.
        with self._lock:
            info2 = self._tasks.get(uid) or info
            info2.status = "running"
            info2.started_at = self._now()
            info2.error = None
            self._tasks[uid] = info2
            self._runners[uid] = runner

        self._submit_run(uid, runner, info2)
        return "restarted"

    def _force_update_meta_on_start(self, uid: str, *, max_total_attempts: int) -> bool:
        """
        Инкрементирует meta["attempts"] и переводит задачу в WORK/running,
        ограничивая общее число попыток значением max_total_attempts.

        В отличие от _update_meta_on_start(), не опирается на self.max_attempts.
        """
        now = self._now()
        meta = self._load_meta(uid) or {}

        attempts = meta.get("attempts")
        try:
            attempts = int(attempts)
        except Exception:
            attempts = 0

        if attempts >= int(max_total_attempts):
            return False

        attempts += 1

        # started_at — первый старт, last_started_at — последний (доп. поле)
        if not meta.get("started_at_ts"):
            meta["started_at_human"] = self._dt_human(now)
            meta["started_at_ts"] = self._dt_ts(now)
        meta["last_started_at_human"] = self._dt_human(now)
        meta["last_started_at_ts"] = self._dt_ts(now)

        meta["attempts"] = attempts
        # Для отображения/отладки (best-effort): пусть в meta будет видно, что допускаем 2 попытки.
        try:
            prev_max = int(meta.get("max_attempts") or 0)
        except Exception:
            prev_max = 0
        meta["max_attempts"] = max(prev_max, int(max_total_attempts))

        meta["status"] = "WORK"
        meta["runtime_status"] = "running"
        meta["finish_reason"] = None
        meta["stopped_by_user"] = False
        meta.setdefault("schema_version", self._meta_schema_version)
        meta.setdefault("uid", self._normalize_uid(uid))
        try:
            self._save_meta(uid, meta)
            return True
        except Exception:
            return False

    def _finalize_task_as_service_crash_failed(self, uid: str, info: TaskInfo, reason: str) -> None:
        """
        Финализирует задачу как FAILED из-за рестарта/падения сервиса.
        """
        reason = str(reason or "").strip() or "Генерация неудачна по причине падения сервиса."

        with self._lock:
            info2 = self._tasks.get(uid) or info
            info2.status = "error"
            info2.finished_at = self._now()
            info2.error = reason
            self._tasks[uid] = info2

        self._write_status_file(info2, "failed")

        # Лаконичный текст, чтобы UI/Telegram показывали понятную причину.
        error_text = f"🟠 {reason}\n"
        self._write_final_error_result_code(info2, error_text)
        try:
            self._append_task_output_log(info2, f"[{self._dt_human(self._now())}] service_crash: {reason}")
        except Exception:
            pass

        try:
            self._update_meta_on_finish(uid, runtime_status="error", error=reason, finish_reason="error")
        except Exception:
            pass

        # Best-effort: уведомление в Telegram + ZIP (если настроено)
        self._try_notify_task_finished_telegram(info2, ok=False, error_text=reason)

        with self._lock:
            self._runners.pop(uid, None)
        self._note_task_finished_and_maybe_restart(reason="service_crash_failed")

    def shutdown(self) -> None:
        self._pool.close()
        self._pool.join(timeout=10)


