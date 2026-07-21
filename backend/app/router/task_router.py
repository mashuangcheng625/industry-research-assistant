"""Authenticated status and cancellation API for persistent tasks."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from core.async_tasks import TaskRecord, get_task_queue
from core.research_control import request_research_cancel
from models.user import User
from router.auth_router import get_current_user_required

router = APIRouter(prefix="/tasks", tags=["background-tasks"])


class TaskResponse(BaseModel):
    task_id: str
    task_type: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    attempts: int
    max_retries: int
    timeout_seconds: int
    cancel_requested: bool
    error: str | None = None
    has_result: bool
    result: object | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse] = Field(default_factory=list)
    total: int


def _response(record: TaskRecord) -> TaskResponse:
    values = record.to_dict()
    values.pop("owner_id", None)
    return TaskResponse(**values)


async def _owned_task(task_id: str, current_user: User) -> TaskRecord:
    try:
        record = await get_task_queue().get(task_id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="persistent task store unavailable") from exc
    if record is None or record.owner_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="task not found")
    return record


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user_required),
):
    try:
        records = await get_task_queue().list_for_owner(str(current_user.id), limit=limit)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="persistent task store unavailable") from exc
    return TaskListResponse(tasks=[_response(record) for record in records], total=len(records))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, current_user: User = Depends(get_current_user_required)):
    return _response(await _owned_task(task_id, current_user))


@router.post("/{task_id}/cancel", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(task_id: str, current_user: User = Depends(get_current_user_required)):
    record = await _owned_task(task_id, current_user)
    if record.status.terminal:
        return _response(record)
    if record.status.value == "running" and record.task_type != "research.run":
        raise HTTPException(
            status_code=409,
            detail="this task type cannot be cancelled after processing has started",
        )
    if record.task_type == "research.run":
        session_id = str(record.payload.get("session_id", ""))
        if session_id and not request_research_cancel(session_id, expire=300):
            raise HTTPException(status_code=503, detail="research cancellation could not be persisted")
    try:
        await get_task_queue().cancel(task_id)
        updated = await get_task_queue().get(task_id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="cancellation could not be persisted") from exc
    return _response(updated or record)
