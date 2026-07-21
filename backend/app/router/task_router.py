"""Authenticated status and cancellation API for persistent tasks."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from core.async_tasks import TaskRecord, get_task_queue
from core.database import get_db
from core.research_control import request_research_cancel
from core.task_outbox import (
    OUTBOX_CANCELLED,
    OUTBOX_DISPATCHING,
    OUTBOX_FAILED,
    OUTBOX_PENDING,
)
from models.task_outbox import TaskOutbox
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


def _outbox_response(row: TaskOutbox) -> TaskResponse:
    status_value = {
        OUTBOX_FAILED: "failed",
        OUTBOX_CANCELLED: "cancelled",
    }.get(row.status, "queued")
    return TaskResponse(
        task_id=row.task_id,
        task_type=row.task_type,
        status=status_value,
        created_at=row.created_at.isoformat(),
        started_at=None,
        finished_at=(
            row.updated_at.isoformat()
            if row.status in {OUTBOX_FAILED, OUTBOX_CANCELLED}
            else None
        ),
        attempts=0,
        max_retries=row.max_retries,
        timeout_seconds=row.timeout_seconds,
        cancel_requested=row.status == OUTBOX_CANCELLED,
        error=row.last_error if row.status == OUTBOX_FAILED else None,
        has_result=False,
        result=None,
    )


def _visible_outbox_query(db: Session, owner_id: object):
    return db.query(TaskOutbox).filter(
        TaskOutbox.owner_id == owner_id,
        TaskOutbox.status.in_(
            (OUTBOX_PENDING, OUTBOX_DISPATCHING, OUTBOX_FAILED, OUTBOX_CANCELLED)
        ),
    )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    try:
        records = await get_task_queue().list_for_owner(str(current_user.id), limit=limit)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="persistent task store unavailable") from exc
    responses = {_record.task_id: _response(_record) for _record in records}
    outbox_rows = (
        _visible_outbox_query(db, current_user.id)
        .order_by(TaskOutbox.created_at.desc())
        .limit(limit)
        .all()
    )
    for row in outbox_rows:
        responses.setdefault(row.task_id, _outbox_response(row))
    ordered = sorted(responses.values(), key=lambda item: item.created_at, reverse=True)[:limit]
    return TaskListResponse(tasks=ordered, total=len(ordered))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    try:
        record = await get_task_queue().get(task_id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="persistent task store unavailable") from exc
    if record is not None:
        if record.owner_id != str(current_user.id):
            raise HTTPException(status_code=404, detail="task not found")
        return _response(record)
    row = _visible_outbox_query(db, current_user.id).filter(TaskOutbox.task_id == task_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="task not found")
    return _outbox_response(row)


@router.post("/{task_id}/cancel", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db),
):
    try:
        record = await get_task_queue().get(task_id)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="persistent task store unavailable") from exc
    if record is None:
        row = (
            _visible_outbox_query(db, current_user.id)
            .filter(TaskOutbox.task_id == task_id)
            .with_for_update()
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="task not found")
        if row.status == OUTBOX_PENDING:
            row.status = OUTBOX_CANCELLED
            row.updated_at = datetime.now(timezone.utc)
            row.last_error = None
            db.commit()
            return _outbox_response(row)
        if row.status == OUTBOX_DISPATCHING:
            raise HTTPException(
                status_code=409,
                detail="task is being dispatched; retry cancellation after publication",
            )
        return _outbox_response(row)
    if record.owner_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="task not found")
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
