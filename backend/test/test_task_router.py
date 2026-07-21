from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from core.async_tasks import TaskRecord, TaskStatusEnum
from router.task_router import cancel_task, get_task


def _record(*, owner: str = "user-1", task_type: str = "document.process") -> TaskRecord:
    return TaskRecord(
        task_id="task-1",
        task_type=task_type,
        owner_id=owner,
        payload={"session_id": "session-1"},
        status=TaskStatusEnum.RUNNING,
        created_at="2026-07-20T00:00:00+00:00",
        started_at="2026-07-20T00:00:01+00:00",
        finished_at=None,
        attempts=1,
        max_retries=1,
        timeout_seconds=30,
        cancel_requested=False,
        error=None,
        result=None,
    )


class FakeQueue:
    def __init__(self, record: TaskRecord):
        self.record = record
        self.cancelled = False

    async def get(self, _task_id: str):
        return self.record

    async def cancel(self, _task_id: str):
        self.cancelled = True
        return True


def test_task_lookup_hides_other_users_task_existence():
    queue = FakeQueue(_record(owner="someone-else"))
    with patch("router.task_router.get_task_queue", return_value=queue):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_task("task-1", SimpleNamespace(id="user-1")))
    assert exc.value.status_code == 404


def test_running_non_cooperative_task_rejects_cancellation():
    queue = FakeQueue(_record(task_type="document.process"))
    with patch("router.task_router.get_task_queue", return_value=queue):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(cancel_task("task-1", SimpleNamespace(id="user-1")))
    assert exc.value.status_code == 409
    assert queue.cancelled is False


def test_running_research_cancellation_updates_both_control_planes():
    queue = FakeQueue(_record(task_type="research.run"))
    with (
        patch("router.task_router.get_task_queue", return_value=queue),
        patch("router.task_router.request_research_cancel", return_value=True) as request_cancel,
    ):
        response = asyncio.run(cancel_task("task-1", SimpleNamespace(id="user-1")))
    request_cancel.assert_called_once_with("session-1", expire=300)
    assert queue.cancelled is True
    assert response.task_id == "task-1"
