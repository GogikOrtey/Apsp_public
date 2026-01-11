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

    def _init_meta(self, *, uid: str, url: str, user_telegram_id: int | None = None, user_account: str | None = None) -> None:
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
        meta.setdefault("schema_version", self._meta_schema_version)
        meta.setdefault("uid", self._normalize_uid(uid))
        self._save_meta(uid, meta)
        return meta, True

    def _update_meta_on_finish(self, uid: str, *, runtime_status: str, error: str | None) -> None:
        now = self._now()
        meta = self._load_meta(uid) or {}
        meta["finished_at_human"] = self._dt_human(now)
        meta["finished_at_ts"] = self._dt_ts(now)
        meta["status"] = self._runtime_to_meta_status(runtime_status)
        meta["runtime_status"] = runtime_status
        meta["last_error"] = error
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
                self._update_meta_on_finish(uid, runtime_status="done", error=None)
            except Exception:
                pass

            # Best-effort: уведомление в Telegram + ZIP
            self._try_notify_task_finished_telegram(info2, ok=True, error_text=None)
            # runner больше не нужен
            with self._lock:
                self._runners.pop(uid, None)
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
                self._write_final_error_result_code(info2, f"🟠{final_reason}\n")
                try:
                    self._append_task_output_log(info2, f"[{self._dt_human(self._now())}] stopped by user: {final_reason}")
                except Exception:
                    pass

                try:
                    self._update_meta_on_finish(uid, runtime_status="error", error=final_reason)
                except Exception:
                    pass

                # Best-effort: уведомление в Telegram + ZIP
                self._try_notify_task_finished_telegram(info2, ok=False, error_text=final_reason)

                with self._lock:
                    self._runners.pop(uid, None)
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
                    self._update_meta_on_finish(uid, runtime_status="error", error=final_reason)
                except Exception:
                    pass

                # Best-effort: уведомление в Telegram + ZIP
                self._try_notify_task_finished_telegram(info2, ok=False, error_text=final_reason)

                with self._lock:
                    self._runners.pop(uid, None)
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
            error_text = "🟠 Ошибка генерации: 🟠\n\n" + "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )
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
                self._update_meta_on_finish(uid, runtime_status="error", error=err_str)
            except Exception:
                pass

            # Best-effort: уведомление в Telegram + ZIP
            self._try_notify_task_finished_telegram(info2, ok=False, error_text=err_str)

            with self._lock:
                self._runners.pop(uid, None)

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

    def create(self, url: str, *, user_telegram_id: int | None = None, user_account: str | None = None) -> TaskInfo:
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
            self._init_meta(uid=uid, url=str(url), user_telegram_id=user_telegram_id, user_account=user_account)
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

    def reconcile_orphaned_running_tasks(self) -> int:
        """
        На рестарте сервиса "живых" задач быть не может (они выполняются в этом же процессе).

        Но если процесс был остановлен/упал во время выполнения, в `meta.json` мог остаться
        `runtime_status="running"`. Это приводит к:
        - зависанию UI на `main_page_2` (задача "вечная"),
        - неверному счётчику активных задач.

        Здесь мы best-effort переводим такие задачи в финальный статус (обычно FAILED).
        Можно отключить через env `APSP_RECONCILE_ORPHANED_RUNNING_TASKS=0`.
        """
        try:
            enabled = (os.environ.get("APSP_RECONCILE_ORPHANED_RUNNING_TASKS", "1") or "").strip()
            if enabled in {"0", "false", "False", "no", "NO"}:
                return 0
        except Exception:
            # если не смогли распарсить — считаем включённым по умолчанию
            pass

        fixed = 0
        now = self._now()

        try:
            entries = list(self._result_tasks_dir.iterdir())
        except Exception:
            return 0

        for task_dir in entries:
            try:
                if not task_dir.is_dir():
                    continue
                uid = str(task_dir.name or "").strip()
                if not self._is_valid_uid(uid):
                    continue

                meta_path = task_dir / "meta.json"
                if not meta_path.is_file():
                    continue

                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if not isinstance(meta, dict):
                    continue

                runtime_status = str(meta.get("runtime_status") or "")
                if runtime_status != "running":
                    continue

                # Если уже есть finished_at_ts — не трогаем (возможно, просто неконсистентный meta).
                if meta.get("finished_at_ts") is not None:
                    continue

                has_success = (task_dir / "RESULT_SUCSESS.txt").is_file()
                has_failed = (task_dir / "RESULT_FAILED.txt").is_file()

                url = str(meta.get("url") or "")

                # Если есть явный маркер — просто приводим meta к нему.
                if has_success:
                    try:
                        self._update_meta_on_finish(uid, runtime_status="done", error=None)
                    except Exception:
                        pass
                    fixed += 1
                    continue

                # Иначе считаем "осиротевшей" задачей: процесс был перезапущен во время генерации.
                reason = "Сервис был перезапущен во время генерации. Задача остановлена."
                info = TaskInfo(
                    uid=self._normalize_uid(uid),
                    url=url,
                    task_dir=task_dir,
                    status="error",
                    error=reason,
                    created_at=None,
                    started_at=None,
                    finished_at=now,
                )

                # Обновляем meta (переводим в FAILED) — это главный источник истины для UI.
                try:
                    self._update_meta_on_finish(uid, runtime_status="error", error=reason)
                except Exception:
                    pass

                # Создаём статус-файл, если его ещё нет.
                try:
                    if not has_failed:
                        self._write_status_file(info, "failed")
                except Exception:
                    pass

                # Пишем текст ошибки в result_code.ts, но только если файла нет или он пустой.
                try:
                    rc = task_dir / "result_code.ts"
                    need_write = True
                    if rc.is_file():
                        try:
                            need_write = rc.stat().st_size <= 0
                        except Exception:
                            need_write = False
                    if need_write:
                        self._write_final_error_result_code(info, f"🟠{reason}\n")
                except Exception:
                    pass

                fixed += 1
            except Exception:
                # best-effort: не блокируем старт сервиса из-за одной плохой папки
                continue

        return fixed

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

    def shutdown(self) -> None:
        self._pool.close()
        self._pool.join(timeout=10)


