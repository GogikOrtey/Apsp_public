from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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

    def get(self, uid: str) -> TaskInfo | None:
        with self._lock:
            return self._tasks.get(uid)

    def exists(self, uid: str) -> bool:
        with self._lock:
            return uid in self._tasks

    def start(self, uid: str, runner: Any) -> None:
        """
        runner: Callable[[Browser, TaskInfo], Any]
        """
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


