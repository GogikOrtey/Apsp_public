from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
import json
from pathlib import Path
import re
import threading
import traceback
from typing import Any
from uuid import uuid4

from task_runtime.playwright_pool import PlaywrightPool
from task_runtime.stop_store import UserStopException, clear_stop, get_stop_reason, USER_STOP_MESSAGE


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

    def _init_meta(self, *, uid: str, url: str) -> None:
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
            try:
                self._update_meta_on_finish(uid, runtime_status="done", error=None)
            except Exception:
                pass
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
                with self._lock:
                    info2 = self._tasks.get(uid)
                    if info2 is None:
                        return
                    info2.status = "error"
                    info2.finished_at = self._now()
                    info2.error = final_reason

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

    def create(self, url: str) -> TaskInfo:
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
            self._init_meta(uid=uid, url=str(url))
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

    def shutdown(self) -> None:
        self._pool.close()
        self._pool.join(timeout=10)


