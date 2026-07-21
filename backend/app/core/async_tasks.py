"""Redis Streams based persistent background-task execution.

The queue deliberately exposes a small application-owned protocol instead of
binding routers to a task framework. Redis provides durable storage, consumer
groups provide at-least-once delivery, and ``XAUTOCLAIM`` recovers work owned by
workers that disappeared before acknowledging it.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping, Optional

from redis.asyncio import Redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)

TaskHandler = Callable[["TaskContext", dict[str, Any]], Awaitable[Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


class TaskStatusEnum(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.CANCELLED}


@dataclass(frozen=True)
class TaskQueueSettings:
    prefix: str = "industry:tasks"
    group: str = "industry-workers"
    retention_seconds: int = 7 * 24 * 3600
    visibility_timeout_seconds: int = 960
    block_ms: int = 1000
    max_payload_bytes: int = 256 * 1024
    max_result_bytes: int = 2 * 1024 * 1024
    retry_base_seconds: float = 2.0
    heartbeat_ttl_seconds: int = 20

    @classmethod
    def from_env(cls) -> "TaskQueueSettings":
        return cls(
            prefix=os.getenv("TASK_QUEUE_PREFIX", cls.prefix),
            group=os.getenv("TASK_QUEUE_GROUP", cls.group),
            retention_seconds=int(os.getenv("TASK_QUEUE_RETENTION_SECONDS", cls.retention_seconds)),
            visibility_timeout_seconds=int(
                os.getenv("TASK_QUEUE_VISIBILITY_TIMEOUT_SECONDS", cls.visibility_timeout_seconds)
            ),
            block_ms=int(os.getenv("TASK_QUEUE_BLOCK_MS", cls.block_ms)),
            max_payload_bytes=int(os.getenv("TASK_QUEUE_MAX_PAYLOAD_BYTES", cls.max_payload_bytes)),
            max_result_bytes=int(os.getenv("TASK_QUEUE_MAX_RESULT_BYTES", cls.max_result_bytes)),
            retry_base_seconds=float(os.getenv("TASK_QUEUE_RETRY_BASE_SECONDS", cls.retry_base_seconds)),
            heartbeat_ttl_seconds=int(
                os.getenv("TASK_WORKER_HEARTBEAT_TTL_SECONDS", cls.heartbeat_ttl_seconds)
            ),
        )


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    task_type: str
    owner_id: str
    payload: dict[str, Any]
    status: TaskStatusEnum
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    attempts: int
    max_retries: int
    timeout_seconds: int
    cancel_requested: bool
    error: Optional[str]
    result: Any

    @classmethod
    def from_hash(cls, values: Mapping[str, str]) -> "TaskRecord":
        return cls(
            task_id=values["task_id"],
            task_type=values["task_type"],
            owner_id=values.get("owner_id", ""),
            payload=json.loads(values.get("payload") or "{}"),
            status=TaskStatusEnum(values["status"]),
            created_at=values["created_at"],
            started_at=values.get("started_at") or None,
            finished_at=values.get("finished_at") or None,
            attempts=int(values.get("attempts", 0)),
            max_retries=int(values.get("max_retries", 0)),
            timeout_seconds=int(values.get("timeout_seconds", 0)),
            cancel_requested=values.get("cancel_requested") == "1",
            error=values.get("error") or None,
            result=json.loads(values["result"]) if values.get("result") else None,
        )

    def to_dict(self, *, include_result: bool = True) -> dict[str, Any]:
        data = {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "owner_id": self.owner_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "cancel_requested": self.cancel_requested,
            "error": self.error,
            "has_result": self.result is not None,
        }
        if include_result:
            data["result"] = self.result
        return data


class TaskContext:
    """Per-attempt context exposed to registered task handlers."""

    def __init__(self, queue: "TaskQueue", task_id: str):
        self.queue = queue
        self.task_id = task_id

    async def is_cancel_requested(self) -> bool:
        value = await self.queue.redis.hget(self.queue.record_key(self.task_id), "cancel_requested")
        return value == "1"

    async def raise_if_cancelled(self) -> None:
        if await self.is_cancel_requested():
            raise asyncio.CancelledError


class TaskQueue:
    """Persistent task repository and Redis Streams transport."""

    _ENQUEUE_IF_ABSENT_SCRIPT = """
    if redis.call('EXISTS', KEYS[1]) == 1 then
      return 0
    end
    redis.call('HSET', KEYS[1], unpack(ARGV, 4))
    redis.call('EXPIRE', KEYS[1], ARGV[1])
    redis.call('ZADD', KEYS[2], ARGV[2], ARGV[3])
    redis.call('ZADD', KEYS[3], ARGV[2], ARGV[3])
    redis.call('XADD', KEYS[4], '*', 'task_id', ARGV[3])
    return 1
    """

    def __init__(self, redis: Redis, settings: Optional[TaskQueueSettings] = None):
        self.redis = redis
        self.settings = settings or TaskQueueSettings.from_env()
        self.stream_key = f"{self.settings.prefix}:stream"
        self.scheduled_key = f"{self.settings.prefix}:scheduled"
        self.all_tasks_key = f"{self.settings.prefix}:all"

    def record_key(self, task_id: str) -> str:
        return f"{self.settings.prefix}:record:{task_id}"

    def owner_key(self, owner_id: str) -> str:
        return f"{self.settings.prefix}:owner:{owner_id}"

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.stream_key, self.settings.group, id="0", mkstream=True
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(
        self,
        task_type: str,
        payload: Mapping[str, Any],
        *,
        owner_id: str,
        task_id: Optional[str] = None,
        max_retries: int = 2,
        timeout_seconds: int = 900,
    ) -> str:
        payload_json = _json(dict(payload))
        if len(payload_json.encode("utf-8")) > self.settings.max_payload_bytes:
            raise ValueError("task payload exceeds TASK_QUEUE_MAX_PAYLOAD_BYTES")
        task_id = task_id or f"task-{uuid.uuid4().hex}"
        now = _utc_now()
        score = time.time()
        record = {
            "task_id": task_id,
            "task_type": task_type,
            "owner_id": str(owner_id),
            "payload": payload_json,
            "status": TaskStatusEnum.QUEUED.value,
            "created_at": now,
            "started_at": "",
            "finished_at": "",
            "attempts": "0",
            "max_retries": str(max(0, int(max_retries))),
            "timeout_seconds": str(max(1, int(timeout_seconds))),
            "cancel_requested": "0",
            "error": "",
            "result": "",
            "worker_id": "",
        }
        key = self.record_key(task_id)
        hash_args: list[str] = []
        for field, value in record.items():
            hash_args.extend((field, value))
        created = await self.redis.eval(
            self._ENQUEUE_IF_ABSENT_SCRIPT,
            4,
            key,
            self.all_tasks_key,
            self.owner_key(str(owner_id)),
            self.stream_key,
            self.settings.retention_seconds,
            score,
            task_id,
            *hash_args,
        )
        if not created:
            existing = await self.redis.hmget(key, "task_type", "owner_id", "payload")
            same_identity = existing[:2] == [task_type, str(owner_id)]
            try:
                same_payload = json.loads(existing[2]) == json.loads(payload_json)
            except (TypeError, json.JSONDecodeError):
                same_payload = False
            if not same_identity or not same_payload:
                raise ValueError("task_id already exists with different task data")
        return task_id

    async def get(self, task_id: str) -> Optional[TaskRecord]:
        values = await self.redis.hgetall(self.record_key(task_id))
        return TaskRecord.from_hash(values) if values else None

    async def list_for_owner(self, owner_id: str, *, limit: int = 50) -> list[TaskRecord]:
        task_ids = await self.redis.zrevrange(self.owner_key(str(owner_id)), 0, max(0, limit - 1))
        if not task_ids:
            return []
        async with self.redis.pipeline(transaction=False) as pipe:
            for task_id in task_ids:
                pipe.hgetall(self.record_key(task_id))
            rows = await pipe.execute()
        stale = [task_id for task_id, row in zip(task_ids, rows) if not row]
        if stale:
            await self.redis.zrem(self.owner_key(str(owner_id)), *stale)
            await self.redis.zrem(self.all_tasks_key, *stale)
        return [TaskRecord.from_hash(row) for row in rows if row]

    async def cancel(self, task_id: str) -> bool:
        key = self.record_key(task_id)
        values = await self.redis.hmget(key, "status", "task_id")
        if not values[1]:
            return False
        status = TaskStatusEnum(values[0])
        update: dict[str, str] = {"cancel_requested": "1"}
        if status in {TaskStatusEnum.QUEUED, TaskStatusEnum.RETRYING}:
            update.update(status=TaskStatusEnum.CANCELLED.value, finished_at=_utc_now())
            await self.redis.zrem(self.scheduled_key, task_id)
        await self.redis.hset(key, mapping=update)
        return True

    async def ping(self) -> bool:
        return bool(await self.redis.ping())


class TaskWorker:
    """Consumer-group worker with timeout, retry, and crash recovery."""

    _PROMOTE_DUE_SCRIPT = """
    local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, ARGV[2])
    for _, id in ipairs(ids) do
      if redis.call('ZREM', KEYS[1], id) == 1 then
        redis.call('XADD', KEYS[2], '*', 'task_id', id)
      end
    end
    return ids
    """

    def __init__(
        self,
        queue: TaskQueue,
        handlers: Mapping[str, TaskHandler],
        *,
        consumer_name: Optional[str] = None,
    ):
        self.queue = queue
        self.handlers = dict(handlers)
        self.consumer_name = consumer_name or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self._last_stream_trim = 0.0

    async def promote_due(self, *, limit: int = 100) -> int:
        ids = await self.queue.redis.eval(
            self._PROMOTE_DUE_SCRIPT,
            2,
            self.queue.scheduled_key,
            self.queue.stream_key,
            time.time(),
            limit,
        )
        return len(ids)

    async def heartbeat(self) -> None:
        key = f"{self.queue.settings.prefix}:worker:{self.consumer_name}"
        await self.queue.redis.set(
            key,
            _utc_now(),
            ex=self.queue.settings.heartbeat_ttl_seconds,
        )
        await self.queue.redis.sadd(f"{self.queue.settings.prefix}:workers", self.consumer_name)
        try:
            from core.metrics import TASK_QUEUE_DEPTH

            groups = await self.queue.redis.xinfo_groups(self.queue.stream_key)
            group = next((item for item in groups if item.get("name") == self.queue.settings.group), None)
            if group:
                TASK_QUEUE_DEPTH.set(int(group.get("pending", 0)) + int(group.get("lag") or 0))
            if time.monotonic() - self._last_stream_trim >= 60:
                await self._trim_acknowledged_stream_entries(group)
                self._last_stream_trim = time.monotonic()
        except Exception:
            logger.debug("Unable to update task queue depth metric", exc_info=True)

    async def _trim_acknowledged_stream_entries(self, group: Optional[Mapping[str, Any]]) -> None:
        """Bound stream growth without deleting pending crash-recovery entries."""
        if not group:
            return
        pending = await self.queue.redis.xpending(self.queue.stream_key, self.queue.settings.group)
        boundary = pending.get("min") if pending.get("pending", 0) else group.get("last-delivered-id")
        if boundary and boundary != "0-0":
            await self.queue.redis.xtrim(self.queue.stream_key, minid=boundary, approximate=False)

    async def _claim_stale(self) -> list[tuple[str, dict[str, str]]]:
        claimed = await self.queue.redis.xautoclaim(
            self.queue.stream_key,
            self.queue.settings.group,
            self.consumer_name,
            min_idle_time=self.queue.settings.visibility_timeout_seconds * 1000,
            start_id="0-0",
            count=10,
        )
        return claimed[1] if len(claimed) > 1 else []

    async def run_once(self, *, block_ms: Optional[int] = None) -> bool:
        await self.queue.ensure_group()
        await self.heartbeat()
        await self.promote_due()
        messages = await self._claim_stale()
        if not messages:
            response = await self.queue.redis.xreadgroup(
                self.queue.settings.group,
                self.consumer_name,
                {self.queue.stream_key: ">"},
                count=1,
                block=self.queue.settings.block_ms if block_ms is None else block_ms,
            )
            messages = response[0][1] if response else []
        if not messages:
            return False
        for message_id, fields in messages:
            await self._execute(message_id, fields.get("task_id", ""))
        return True

    async def _execute(self, message_id: str, task_id: str) -> None:
        key = self.queue.record_key(task_id)
        values = await self.queue.redis.hgetall(key)
        if not values:
            await self._ack(message_id)
            return
        status = TaskStatusEnum(values["status"])
        if values.get("cancel_requested") == "1" or status == TaskStatusEnum.CANCELLED:
            await self._finish(key, TaskStatusEnum.CANCELLED)
            await self._ack(message_id)
            return

        attempts = int(values.get("attempts", 0)) + 1
        await self.queue.redis.hset(
            key,
            mapping={
                "status": TaskStatusEnum.RUNNING.value,
                "started_at": values.get("started_at") or _utc_now(),
                "attempts": str(attempts),
                "worker_id": self.consumer_name,
                "error": "",
            },
        )
        handler = self.handlers.get(values["task_type"])
        if handler is None:
            await self._fail_or_retry(
                message_id, key, task_id, values, attempts,
                RuntimeError(f"no handler registered for task type {values['task_type']!r}"),
            )
            return

        context = TaskContext(self.queue, task_id)
        attempt_started_at = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                handler(context, json.loads(values["payload"])),
                timeout=int(values["timeout_seconds"]),
            )
            if await context.is_cancel_requested():
                await self._finish(key, TaskStatusEnum.CANCELLED)
                outcome = "cancelled"
            else:
                result_json = _json(result)
                if len(result_json.encode("utf-8")) > self.queue.settings.max_result_bytes:
                    raise ValueError("task result exceeds TASK_QUEUE_MAX_RESULT_BYTES")
                await self._finish(key, TaskStatusEnum.SUCCEEDED, result=result_json)
                outcome = "succeeded"
            self._observe(values["task_type"], outcome, attempt_started_at)
            await self._ack(message_id)
        except asyncio.CancelledError:
            # Cooperative task cancellation is terminal; worker shutdown should
            # leave the stream entry pending so another worker can reclaim it.
            if await context.is_cancel_requested():
                await self._finish(key, TaskStatusEnum.CANCELLED)
                self._observe(values["task_type"], "cancelled", attempt_started_at)
                await self._ack(message_id)
                return
            raise
        except Exception as exc:
            await self._fail_or_retry(message_id, key, task_id, values, attempts, exc)
            self._observe(values["task_type"], "error", attempt_started_at)

    @staticmethod
    def _observe(task_type: str, outcome: str, started_at: float) -> None:
        try:
            from core.metrics import TASK_DURATION, TASK_RUNS

            TASK_RUNS.labels(task_type=task_type, outcome=outcome).inc()
            TASK_DURATION.labels(task_type=task_type, outcome=outcome).observe(
                max(0.0, time.perf_counter() - started_at)
            )
        except Exception:
            logger.warning("Task metrics observation failed", exc_info=True)

    async def _fail_or_retry(
        self,
        message_id: str,
        key: str,
        task_id: str,
        values: Mapping[str, str],
        attempts: int,
        exc: Exception,
    ) -> None:
        error = f"{type(exc).__name__}: {exc}"[:2000]
        cancel_requested = await self.queue.redis.hget(key, "cancel_requested") == "1"
        if cancel_requested:
            await self._finish(key, TaskStatusEnum.CANCELLED, error=error)
        elif attempts <= int(values.get("max_retries", 0)):
            delay = self.queue.settings.retry_base_seconds * (2 ** (attempts - 1))
            await self.queue.redis.hset(
                key,
                mapping={"status": TaskStatusEnum.RETRYING.value, "error": error, "worker_id": ""},
            )
            await self.queue.redis.zadd(self.queue.scheduled_key, {task_id: time.time() + delay})
        else:
            await self._finish(key, TaskStatusEnum.FAILED, error=error)
        await self._ack(message_id)

    async def _finish(
        self,
        key: str,
        status: TaskStatusEnum,
        *,
        result: str = "",
        error: str = "",
    ) -> None:
        await self.queue.redis.hset(
            key,
            mapping={
                "status": status.value,
                "finished_at": _utc_now(),
                "worker_id": "",
                "result": result,
                "error": error,
            },
        )
        await self.queue.redis.expire(key, self.queue.settings.retention_seconds)

    async def _ack(self, message_id: str) -> None:
        await self.queue.redis.xack(self.queue.stream_key, self.queue.settings.group, message_id)


_queue: Optional[TaskQueue] = None


def create_redis_client() -> Redis:
    return Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
        health_check_interval=30,
    )


def get_task_queue() -> TaskQueue:
    global _queue
    if _queue is None:
        _queue = TaskQueue(create_redis_client())
    return _queue


__all__ = [
    "TaskContext", "TaskQueue", "TaskQueueSettings", "TaskRecord",
    "TaskStatusEnum", "TaskWorker", "create_redis_client", "get_task_queue",
]
