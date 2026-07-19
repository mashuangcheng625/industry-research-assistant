"""Async task queue scaffolding (P2-17).

The application currently runs document parsing and long-running
research tasks synchronously in the FastAPI event loop or thread pool.
This module provides a lightweight in-process task queue via
``asyncio.Queue`` + ``asyncio.Task`` that can be upgraded to Celery /
ARQ when the deployment moves to a multi-worker setup.

Features:
* ``enqueue(task_id, coro)`` — fire-and-forget; returns immediately.
* ``TaskStatus`` — tracks pending / running / done / failed per task.
* ``status(task_id)`` — polling endpoint for the frontend.
* ``cancel(task_id)`` — cooperative cancellation via ``asyncio.Event``.

All state is held in memory, which is acceptable for the single-worker
portfolio deployment. A production multi-worker deployment should
replace this module with a Redis-backed queue (Celery / ARQ / RQ).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRecord:
    task_id: str
    status: TaskStatusEnum = TaskStatusEnum.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    result: Any = None
    _cancel_event: Optional[asyncio.Event] = field(default=None, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "has_result": self.result is not None,
        }


class TaskQueue:
    """In-process async task queue. Singleton per process."""

    def __init__(self, max_concurrent: int = 3):
        self._records: Dict[str, TaskRecord] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def enqueue(self, coro_factory: Callable[[asyncio.Event], Awaitable[Any]], *, task_id: Optional[str] = None) -> str:
        tid = task_id or f"task-{uuid.uuid4().hex[:12]}"
        cancel_evt = asyncio.Event()
        record = TaskRecord(task_id=tid, _cancel_event=cancel_evt)
        self._records[tid] = record
        asyncio.create_task(self._runner(tid, coro_factory))
        return tid

    async def _runner(self, task_id: str, factory: Callable[[asyncio.Event], Awaitable[Any]]) -> None:
        record = self._records.get(task_id)
        if record is None:
            return
        async with self._semaphore:
            record.status = TaskStatusEnum.RUNNING
            record.started_at = datetime.now(timezone.utc).isoformat()
            try:
                result = await factory(record._cancel_event or asyncio.Event())
                record.result = result
                record.status = TaskStatusEnum.DONE
            except asyncio.CancelledError:
                record.status = TaskStatusEnum.CANCELLED
            except Exception as exc:
                record.status = TaskStatusEnum.FAILED
                record.error = f"{type(exc).__name__}: {exc}"
            finally:
                record.finished_at = datetime.now(timezone.utc).isoformat()

    def status(self, task_id: str) -> Optional[TaskRecord]:
        return self._records.get(task_id)

    async def cancel(self, task_id: str) -> bool:
        record = self._records.get(task_id)
        if record is None or record._cancel_event is None:
            return False
        record._cancel_event.set()
        return True

    def all_tasks(self) -> Dict[str, TaskRecord]:
        return dict(self._records)


# Process-wide singleton. Importers should call ``get_task_queue()``.
_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue


__all__ = ["TaskQueue", "TaskRecord", "TaskStatusEnum", "get_task_queue"]
