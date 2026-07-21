"""Transactional outbox atomicity, recovery, and concurrency tests."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models  # noqa: F401 -- register relationship targets
from core.task_outbox import (
    OUTBOX_CANCELLED,
    OUTBOX_FAILED,
    OUTBOX_PENDING,
    OUTBOX_PUBLISHED,
    OutboxDispatcher,
    OutboxSettings,
    create_task_outbox,
)
from models.task_outbox import TaskOutbox
from models.user import User
from router.task_router import cancel_task, get_task
from scripts.validate_migration_roundtrip import build_alembic_config


def _run(coro):
    return asyncio.run(coro)


class FakeQueue:
    def __init__(self, *, fail: bool = False):
        self.settings = SimpleNamespace(prefix="test:outbox")
        self.fail = fail
        self.calls: list[str] = []
        self.unique_tasks: set[str] = set()

    async def enqueue(self, _task_type, _payload, *, task_id, **_kwargs):
        self.calls.append(task_id)
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.unique_tasks.add(task_id)
        return task_id

    async def get(self, _task_id):
        return None


@pytest.fixture
def outbox_db():
    database_url = os.getenv("OUTBOX_TEST_DATABASE_URL", "")
    if not database_url:
        pytest.skip("OUTBOX_TEST_DATABASE_URL is not configured")
    command.upgrade(build_alembic_config(database_url), "head")
    engine = create_engine(database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    db.query(TaskOutbox).delete()
    db.query(User).filter(User.username.like("outbox-test-%")).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()
    try:
        yield factory
    finally:
        db = factory()
        db.query(TaskOutbox).delete()
        db.query(User).filter(User.username.like("outbox-test-%")).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()
        engine.dispose()


def _user(factory, suffix: str = "owner") -> User:
    db = factory()
    user = User(
        username=f"outbox-test-{suffix}",
        email=f"outbox-test-{suffix}@example.com",
        hashed_password="unused",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.expunge(user)
    db.close()
    return user


def _stage(factory, user: User, count: int = 1) -> list[str]:
    db = factory()
    task_ids = []
    for index in range(count):
        row = create_task_outbox(
            db,
            "echo",
            {"index": index},
            owner_id=user.id,
            max_retries=1,
            timeout_seconds=30,
        )
        task_ids.append(row.task_id)
    db.commit()
    db.close()
    return task_ids


@pytest.mark.integration
def test_outbox_row_obeys_callers_database_transaction(outbox_db):
    user = _user(outbox_db, "atomic")
    db = outbox_db()
    row = create_task_outbox(db, "echo", {"value": 1}, owner_id=user.id)
    task_id = row.task_id
    db.flush()
    db.rollback()
    assert db.query(TaskOutbox).filter(TaskOutbox.task_id == task_id).first() is None
    db.close()


@pytest.mark.integration
def test_dispatcher_publishes_and_marks_row(outbox_db):
    user = _user(outbox_db, "publish")
    task_id = _stage(outbox_db, user)[0]
    queue = FakeQueue()
    dispatcher = OutboxDispatcher(
        queue,
        settings=OutboxSettings(retry_base_seconds=0),
        dispatcher_id="dispatcher-a",
        session_factory=outbox_db,
    )

    assert _run(dispatcher.dispatch_once()) == 1
    db = outbox_db()
    row = db.query(TaskOutbox).filter(TaskOutbox.task_id == task_id).one()
    assert row.status == OUTBOX_PUBLISHED
    assert row.delivery_attempts == 1
    assert row.published_at is not None
    assert queue.unique_tasks == {task_id}
    db.close()


@pytest.mark.integration
def test_publish_then_crash_retries_without_duplicate_executable_task(outbox_db):
    user = _user(outbox_db, "crash")
    task_id = _stage(outbox_db, user)[0]
    queue = FakeQueue()
    dispatcher = OutboxDispatcher(
        queue,
        settings=OutboxSettings(retry_base_seconds=0),
        dispatcher_id="dispatcher-a",
        session_factory=outbox_db,
    )
    original_mark = dispatcher._mark_published
    first = True

    def crash_once(selected_task_id):
        nonlocal first
        if first:
            first = False
            raise RuntimeError("process exited after Redis publish")
        return original_mark(selected_task_id)

    with patch.object(dispatcher, "_mark_published", side_effect=crash_once):
        assert _run(dispatcher.dispatch_once()) == 1
        assert _run(dispatcher.dispatch_once()) == 1

    db = outbox_db()
    row = db.query(TaskOutbox).filter(TaskOutbox.task_id == task_id).one()
    assert row.status == OUTBOX_PUBLISHED
    assert row.delivery_attempts == 2
    assert queue.calls == [task_id, task_id]
    assert queue.unique_tasks == {task_id}
    db.close()


@pytest.mark.integration
def test_delivery_failure_has_finite_retry_and_keeps_error_record(outbox_db):
    user = _user(outbox_db, "failure")
    task_id = _stage(outbox_db, user)[0]
    dispatcher = OutboxDispatcher(
        FakeQueue(fail=True),
        settings=OutboxSettings(max_delivery_attempts=2, retry_base_seconds=0),
        dispatcher_id="dispatcher-a",
        session_factory=outbox_db,
    )

    assert _run(dispatcher.dispatch_once()) == 1
    assert _run(dispatcher.dispatch_once()) == 1
    db = outbox_db()
    row = db.query(TaskOutbox).filter(TaskOutbox.task_id == task_id).one()
    assert row.status == OUTBOX_FAILED
    assert row.delivery_attempts == 2
    assert "redis unavailable" in row.last_error
    db.close()


@pytest.mark.integration
def test_concurrent_dispatchers_claim_disjoint_batches(outbox_db):
    user = _user(outbox_db, "concurrent")
    expected = set(_stage(outbox_db, user, count=10))
    settings = OutboxSettings(batch_size=5)
    first = OutboxDispatcher(
        FakeQueue(),
        settings=settings,
        dispatcher_id="dispatcher-a",
        session_factory=outbox_db,
    )
    second = OutboxDispatcher(
        FakeQueue(),
        settings=settings,
        dispatcher_id="dispatcher-b",
        session_factory=outbox_db,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        batches = list(executor.map(lambda item: item._claim_batch(), (first, second)))
    claimed = [{row.task_id for row in batch} for batch in batches]
    assert claimed[0].isdisjoint(claimed[1])
    assert claimed[0] | claimed[1] == expected


@pytest.mark.integration
def test_expired_dispatch_lease_is_reclaimed_after_process_crash(outbox_db):
    user = _user(outbox_db, "lease")
    task_id = _stage(outbox_db, user)[0]
    first = OutboxDispatcher(
        FakeQueue(),
        settings=OutboxSettings(lease_seconds=5),
        dispatcher_id="dead-dispatcher",
        session_factory=outbox_db,
    )
    claimed = first._claim_batch()
    assert [item.task_id for item in claimed] == [task_id]

    db = outbox_db()
    row = db.query(TaskOutbox).filter(TaskOutbox.task_id == task_id).one()
    row.locked_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()
    db.close()

    replacement = OutboxDispatcher(
        FakeQueue(),
        settings=OutboxSettings(lease_seconds=5),
        dispatcher_id="replacement-dispatcher",
        session_factory=outbox_db,
    )
    reclaimed = replacement._claim_batch()
    assert [item.task_id for item in reclaimed] == [task_id]
    assert reclaimed[0].delivery_attempts == 2


@pytest.mark.integration
def test_pending_outbox_task_is_queryable_and_cancellable_before_publish(outbox_db):
    user = _user(outbox_db, "api")
    task_id = _stage(outbox_db, user)[0]
    queue = FakeQueue()
    db = outbox_db()
    with patch("router.task_router.get_task_queue", return_value=queue):
        response = _run(get_task(task_id, user, db))
        assert response.status == "queued"
        cancelled = _run(cancel_task(task_id, user, db))
    assert cancelled.status == "cancelled"
    assert cancelled.cancel_requested is True
    row = db.query(TaskOutbox).filter(TaskOutbox.task_id == task_id).one()
    assert row.status == OUTBOX_CANCELLED
    db.close()
