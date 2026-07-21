"""Transactional outbox rows for durable background-task publication."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskOutbox(Base):
    """A task intent committed atomically with its business record.

    The Redis task record is a delivery projection of this row. ``task_id`` is
    stable across dispatcher retries so a crash after Redis publication cannot
    create a second executable task.
    """

    __tablename__ = "task_outbox"
    __table_args__ = (
        Index("ix_task_outbox_claim", "status", "available_at", "created_at"),
        Index("ix_task_outbox_owner_created", "owner_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(64), unique=True, nullable=False)
    task_type = Column(String(64), nullable=False)
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    payload = Column(JSONB, nullable=False)
    max_retries = Column(Integer, nullable=False, default=2)
    timeout_seconds = Column(Integer, nullable=False, default=900)
    status = Column(String(20), nullable=False, default="pending")
    delivery_attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime(timezone=True), nullable=False)
    locked_at = Column(DateTime(timezone=True))
    locked_by = Column(String(128))
    published_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )
