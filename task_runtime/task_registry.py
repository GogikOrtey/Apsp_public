from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import threading
from typing import Any
from uuid import uuid4

from task_runtime.playwright_pool import PlaywrightPool


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
    def __init__(self, *, result_tasks_dir: Path, max_workers: int = 10, headless: bool = True) -> None:
        self._result_tasks_dir = Path(result_tasks_dir)
        self._result_tasks_dir.mkdir(parents=True, exist_ok=True)
        self._pool = PlaywrightPool(max_workers=max_workers, headless=headless)
        self._tasks: dict[str, TaskInfo] = {}
        self._lock = threading.Lock()
        self._uid_re = re.compile(r"^[0-9a-f]{12}$", re.IGNORECASE)

    def _normalize_uid(self, uid: str) -> str:
        return (uid or "").strip().lower()

    def _is_valid_uid(self, uid: str) -> bool:
        uid_norm = self._normalize_uid(uid)
        return bool(self._uid_re.match(uid_norm))

    def _task_dir_for_uid(self, uid: str) -> Path:
        return self._result_tasks_dir / self._normalize_uid(uid)

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

        # Мы не знаем точный статус (done/error) без отдельного мета-файла,
        # поэтому считаем, что задача завершена и даём UI доступ к артефактам.
        try:
            mtime = datetime.fromtimestamp(task_dir.stat().st_mtime)
        except Exception:
            mtime = None

        info = TaskInfo(
            uid=self._normalize_uid(uid),
            url="",
            task_dir=task_dir,
            status="done",
            created_at=None,
            started_at=None,
            finished_at=mtime,
            error=None,
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

        info = TaskInfo(
            uid=uid,
            url=str(url),
            task_dir=task_dir,
            status="created",
            created_at=datetime.now(),
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
            info.status = "running"
            info.started_at = datetime.now()
            info.error = None

        fut = self._pool.submit(lambda browser: runner(browser, info))

        def _done_callback(f) -> None:
            try:
                _ = f.result()
                with self._lock:
                    info2 = self._tasks.get(uid)
                    if info2 is None:
                        return
                    info2.status = "done"
                    info2.finished_at = datetime.now()
                    info2.error = None
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    info2 = self._tasks.get(uid)
                    if info2 is None:
                        return
                    info2.status = "error"
                    info2.finished_at = datetime.now()
                    info2.error = str(exc)

        fut.add_done_callback(_done_callback)

    def shutdown(self) -> None:
        self._pool.close()
        self._pool.join(timeout=10)


