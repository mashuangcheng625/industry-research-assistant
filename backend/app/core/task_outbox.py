"""PostgreSQL transactional outbox for Redis background tasks.

Routers add an outbox row to the same SQLAlchemy transaction as their business
record. A separate dispatcher claims rows with ``SKIP LOCKED`` and projects
them into the idempotent Redis task protocol. A lease makes interrupted claims
recoverable; the stable task ID makes publish-then-crash safe to repeat.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.async_tasks import TaskQueue, get_task_queue
from core.database import SessionLocal
from models.task_outbox import TaskOutbox


OUTBOX_PENDING = "pending"
OUTBOX_DISPATCHING = "dispatching"
OUTBOX_PUBLISHED = "published"
OUTBOX_FAILED = "failed"
OUTBOX_CANCELLED = "cancelled"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class OutboxSettings:
    batch_size: int = 20
    poll_interval_seconds: float = 0.5
    lease_seconds: int = 30
    max_delivery_attempts: int = 8
    retry_base_seconds: float = 1.0
    heartbeat_ttl_seconds: int = 20
    max_payload_bytes: int = 256 * 1024
    retention_seconds: int = 30 * 24 * 3600
    cleanup_interval_seconds: int = 300

    @classmethod
    def from_env(cls) -> "OutboxSettings":
        return cls(
            batch_size=max(1, int(os.getenv("OUTBOX_BATCH_SIZE", cls.batch_size))),
            poll_interval_seconds=max(
                0.05,
                float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", cls.poll_interval_seconds)),
            ),
            lease_seconds=max(1, int(os.getenv("OUTBOX_LEASE_SECONDS", cls.lease_seconds))),
            max_delivery_attempts=max(
                1,
                int(os.getenv("OUTBOX_MAX_DELIVERY_ATTEMPTS", cls.max_delivery_attempts)),
            ),
            retry_base_seconds=max(
                0.0,
                float(os.getenv("OUTBOX_RETRY_BASE_SECONDS", cls.retry_base_seconds)),
            ),
            heartbeat_ttl_seconds=max(
                3,
                int(os.getenv("OUTBOX_HEARTBEAT_TTL_SECONDS", cls.heartbeat_ttl_seconds)),
            ),
            max_payload_bytes=max(
                1024,
                int(os.getenv("TASK_QUEUE_MAX_PAYLOAD_BYTES", cls.max_payload_bytes)),
            ),
            retention_seconds=max(
                3600,
                int(os.getenv("OUTBOX_RETENTION_SECONDS", cls.retention_seconds)),
            ),
            cleanup_interval_seconds=max(
                60,
                int(
                    os.getenv(
                        "OUTBOX_CLEANUP_INTERVAL_SECONDS",
                        cls.cleanup_interval_seconds,
                    )
                ),
            ),
        )


@dataclass(frozen=True)
class OutboxEnvelope:
    task_id: str
    task_type: str
    owner_id: str
    payload: dict[str, Any]
    max_retries: int
    timeout_seconds: int
    delivery_attempts: int


def create_task_outbox(
    db: Session,
    task_type: str,
    payload: Mapping[str, Any],
    *,
    owner_id: object,
    task_id: Optional[str] = None,
    max_retries: int = 2,
    timeout_seconds: int = 900,
    settings: Optional[OutboxSettings] = None,
) -> TaskOutbox:
    """Stage a task intent without committing the caller's transaction."""
    selected = settings or OutboxSettings.from_env()
    normalized_payload = dict(payload)
    payload_json = json.dumps(
        normalized_payload,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    if len(payload_json.encode("utf-8")) > selected.max_payload_bytes:
        raise ValueError("task payload exceeds TASK_QUEUE_MAX_PAYLOAD_BYTES")
    now = utc_now()
    row = TaskOutbox(
        task_id=task_id or f"task-{uuid.uuid4().hex}",
        task_type=task_type,
        owner_id=owner_id,
        payload=normalized_payload,
        max_retries=max(0, int(max_retries)),
        timeout_seconds=max(1, int(timeout_seconds)),
        status=OUTBOX_PENDING,
        delivery_attempts=0,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    return row


class OutboxDispatcher:
    """Claim and publish outbox rows without holding SQL locks across I/O."""

    def __init__(
        self,
        queue: Optional[TaskQueue] = None,
        *,
        settings: Optional[OutboxSettings] = None,
        dispatcher_id: Optional[str] = None,
        session_factory=SessionLocal,
    ):
        self.queue = queue or get_task_queue()
        self.settings = settings or OutboxSettings.from_env()
        self.dispatcher_id = dispatcher_id or (
            f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        )
        self.session_factory = session_factory
        self._last_cleanup = 0.0

    @property
    def heartbeat_key(self) -> str:
        return f"{self.queue.settings.prefix}:outbox-dispatcher:{self.dispatcher_id}"

    @property
    def dispatchers_key(self) -> str:
        return f"{self.queue.settings.prefix}:outbox-dispatchers"

    async def heartbeat(self) -> None:
        await self.queue.redis.set(
            self.heartbeat_key,
            utc_now().isoformat(),
            ex=self.settings.heartbeat_ttl_seconds,
        )
        await self.queue.redis.sadd(self.dispatchers_key, self.dispatcher_id)

    def _claim_batch(self) -> list[OutboxEnvelope]:
        now = utc_now()
        stale_before = now - timedelta(seconds=self.settings.lease_seconds)
        db = self.session_factory()
        try:
            rows = (
                db.query(TaskOutbox)
                .filter(
                    or_(
                        and_(
                            TaskOutbox.status == OUTBOX_PENDING,
                            TaskOutbox.available_at <= now,
                        ),
                        and_(
                            TaskOutbox.status == OUTBOX_DISPATCHING,
                            TaskOutbox.locked_at < stale_before,
                        ),
                    )
                )
                .order_by(TaskOutbox.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(self.settings.batch_size)
                .all()
            )
            envelopes: list[OutboxEnvelope] = []
            for row in rows:
                row.status = OUTBOX_DISPATCHING
                row.locked_at = now
                row.locked_by = self.dispatcher_id
                row.delivery_attempts = int(row.delivery_attempts or 0) + 1
                row.updated_at = now
                envelopes.append(
                    OutboxEnvelope(
                        task_id=row.task_id,
                        task_type=row.task_type,
                        owner_id=str(row.owner_id),
                        payload=dict(row.payload),
                        max_retries=row.max_retries,
                        timeout_seconds=row.timeout_seconds,
                        delivery_attempts=row.delivery_attempts,
                    )
                )
            db.commit()
            return envelopes
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _mark_published(self, task_id: str) -> bool:
        db = self.session_factory()
        try:
            row = (
                db.query(TaskOutbox)
                .filter(
                    TaskOutbox.task_id == task_id,
                    TaskOutbox.status == OUTBOX_DISPATCHING,
                    TaskOutbox.locked_by == self.dispatcher_id,
                )
                .with_for_update()
                .first()
            )
            if row is None:
                db.rollback()
                return False
            now = utc_now()
            row.status = OUTBOX_PUBLISHED
            row.published_at = now
            row.locked_at = None
            row.locked_by = None
            row.last_error = None
            row.updated_at = now
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _mark_delivery_failure(self, envelope: OutboxEnvelope, exc: Exception) -> str:
        db = self.session_factory()
        try:
            row = (
                db.query(TaskOutbox)
                .filter(
                    TaskOutbox.task_id == envelope.task_id,
                    TaskOutbox.status == OUTBOX_DISPATCHING,
                    TaskOutbox.locked_by == self.dispatcher_id,
                )
                .with_for_update()
                .first()
            )
            if row is None:
                db.rollback()
                return "lease_lost"
            now = utc_now()
            row.last_error = f"{type(exc).__name__}: {exc}"[:2000]
            row.locked_at = None
            row.locked_by = None
            if row.delivery_attempts >= self.settings.max_delivery_attempts:
                row.status = OUTBOX_FAILED
                outcome = OUTBOX_FAILED
            else:
                delay = self.settings.retry_base_seconds * (
                    2 ** max(0, row.delivery_attempts - 1)
                )
                row.status = OUTBOX_PENDING
                row.available_at = now + timedelta(seconds=delay)
                outcome = "retry"
            row.updated_at = now
            db.commit()
            return outcome
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def pending_count(self) -> int:
        db = self.session_factory()
        try:
            return int(
                db.query(func.count(TaskOutbox.id))
                .filter(TaskOutbox.status.in_((OUTBOX_PENDING, OUTBOX_DISPATCHING)))
                .scalar()
                or 0
            )
        finally:
            db.close()

    def _cleanup_terminal_rows(self) -> int:
        cutoff = utc_now() - timedelta(seconds=self.settings.retention_seconds)
        db = self.session_factory()
        try:
            deleted = (
                db.query(TaskOutbox)
                .filter(
                    TaskOutbox.status.in_(
                        (OUTBOX_PUBLISHED, OUTBOX_FAILED, OUTBOX_CANCELLED)
                    ),
                    TaskOutbox.updated_at < cutoff,
                )
                .delete(synchronize_session=False)
            )
            db.commit()
            return int(deleted)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def dispatch_once(self) -> int:
        if time.monotonic() - self._last_cleanup >= self.settings.cleanup_interval_seconds:
            await asyncio.to_thread(self._cleanup_terminal_rows)
            self._last_cleanup = time.monotonic()
        envelopes = await asyncio.to_thread(self._claim_batch)
        for envelope in envelopes:
            started_at = time.perf_counter()
            try:
                await self.queue.enqueue(
                    envelope.task_type,
                    envelope.payload,
                    owner_id=envelope.owner_id,
                    task_id=envelope.task_id,
                    max_retries=envelope.max_retries,
                    timeout_seconds=envelope.timeout_seconds,
                )
                marked = await asyncio.to_thread(self._mark_published, envelope.task_id)
                self._observe("published" if marked else "lease_lost", started_at)
            except Exception as exc:
                outcome = await asyncio.to_thread(
                    self._mark_delivery_failure,
                    envelope,
                    exc,
                )
                self._observe(outcome, started_at)
        self._set_pending_metric(await asyncio.to_thread(self.pending_count))
        return len(envelopes)

    @staticmethod
    def _observe(outcome: str, started_at: float) -> None:
        try:
            from core.metrics import OUTBOX_DELIVERIES, OUTBOX_DELIVERY_DURATION

            OUTBOX_DELIVERIES.labels(outcome=outcome).inc()
            OUTBOX_DELIVERY_DURATION.labels(outcome=outcome).observe(
                max(0.0, time.perf_counter() - started_at)
            )
        except Exception:
            # Metrics must never change delivery semantics.
            pass

    @staticmethod
    def _set_pending_metric(count: int) -> None:
        try:
            from core.metrics import OUTBOX_PENDING_EVENTS

            OUTBOX_PENDING_EVENTS.set(count)
        except Exception:
            pass


__all__ = [
    "OUTBOX_CANCELLED",
    "OUTBOX_DISPATCHING",
    "OUTBOX_FAILED",
    "OUTBOX_PENDING",
    "OUTBOX_PUBLISHED",
    "OutboxDispatcher",
    "OutboxEnvelope",
    "OutboxSettings",
    "create_task_outbox",
]
