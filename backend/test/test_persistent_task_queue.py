"""Failure-semantics tests for the Redis Streams task queue."""

from __future__ import annotations

import asyncio
import os
import time
import uuid

import pytest
from redis.asyncio import Redis

from core.async_tasks import (
    TaskQueue,
    TaskQueueSettings,
    TaskStatusEnum,
    TaskWorker,
)


def _run(coro):
    return asyncio.run(coro)


def _test_url() -> str:
    return os.getenv("REDIS_TASK_QUEUE_TEST_URL", "redis://127.0.0.1:6379/15")


async def _fixture():
    prefix = f"test:tasks:{uuid.uuid4().hex}"
    redis = Redis.from_url(_test_url(), decode_responses=True)
    queue = TaskQueue(
        redis,
        TaskQueueSettings(
            prefix=prefix,
            group="test-workers",
            retention_seconds=60,
            visibility_timeout_seconds=0,
            block_ms=1,
            retry_base_seconds=0,
            heartbeat_ttl_seconds=5,
        ),
    )
    return redis, queue, prefix


async def _cleanup(redis: Redis, prefix: str) -> None:
    keys = [key async for key in redis.scan_iter(match=f"{prefix}*")]
    if keys:
        await redis.delete(*keys)
    await redis.aclose()


@pytest.mark.integration
def test_task_survives_queue_reconstruction_and_returns_result():
    async def exercise():
        redis, queue, prefix = await _fixture()
        try:
            task_id = await queue.enqueue("echo", {"value": 7}, owner_id="user-1")
            reconstructed = TaskQueue(redis, queue.settings)

            async def echo(_context, payload):
                return {"value": payload["value"]}

            worker = TaskWorker(reconstructed, {"echo": echo}, consumer_name="worker-a")
            assert await worker.run_once(block_ms=1)
            record = await reconstructed.get(task_id)
            assert record is not None
            assert record.status == TaskStatusEnum.SUCCEEDED
            assert record.attempts == 1
            assert record.result == {"value": 7}
        finally:
            await _cleanup(redis, prefix)

    _run(exercise())


@pytest.mark.integration
def test_failed_attempt_is_durably_scheduled_and_retried():
    async def exercise():
        redis, queue, prefix = await _fixture()
        calls = 0
        try:
            task_id = await queue.enqueue("flaky", {}, owner_id="user-1", max_retries=1)

            async def flaky(_context, _payload):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("transient")
                return "ok"

            worker = TaskWorker(queue, {"flaky": flaky}, consumer_name="worker-a")
            assert await worker.run_once(block_ms=1)
            retrying = await queue.get(task_id)
            assert retrying is not None and retrying.status == TaskStatusEnum.RETRYING
            assert "transient" in (retrying.error or "")

            assert await worker.run_once(block_ms=1)
            completed = await queue.get(task_id)
            assert completed is not None and completed.status == TaskStatusEnum.SUCCEEDED
            assert completed.attempts == 2
            assert completed.result == "ok"
        finally:
            await _cleanup(redis, prefix)

    _run(exercise())


@pytest.mark.integration
def test_timeout_becomes_terminal_failure_after_retry_budget():
    async def exercise():
        redis, queue, prefix = await _fixture()
        try:
            task_id = await queue.enqueue(
                "slow", {}, owner_id="user-1", max_retries=0, timeout_seconds=1
            )

            async def slow(_context, _payload):
                await asyncio.sleep(2)

            worker = TaskWorker(queue, {"slow": slow}, consumer_name="worker-a")
            assert await worker.run_once(block_ms=1)
            record = await queue.get(task_id)
            assert record is not None and record.status == TaskStatusEnum.FAILED
            assert "TimeoutError" in (record.error or "")
        finally:
            await _cleanup(redis, prefix)

    _run(exercise())


@pytest.mark.integration
def test_queued_task_can_be_cancelled_without_running_handler():
    async def exercise():
        redis, queue, prefix = await _fixture()
        called = False
        try:
            task_id = await queue.enqueue("side-effect", {}, owner_id="user-1")
            assert await queue.cancel(task_id)

            async def handler(_context, _payload):
                nonlocal called
                called = True

            worker = TaskWorker(queue, {"side-effect": handler}, consumer_name="worker-a")
            assert await worker.run_once(block_ms=1)
            record = await queue.get(task_id)
            assert record is not None and record.status == TaskStatusEnum.CANCELLED
            assert not called
        finally:
            await _cleanup(redis, prefix)

    _run(exercise())


@pytest.mark.integration
def test_stale_unacked_delivery_is_claimed_after_worker_crash():
    async def exercise():
        redis, queue, prefix = await _fixture()
        try:
            await queue.ensure_group()
            task_id = await queue.enqueue("recover", {}, owner_id="user-1")
            delivered = await redis.xreadgroup(
                queue.settings.group, "dead-worker", {queue.stream_key: ">"}, count=1
            )
            assert delivered

            async def recover(_context, _payload):
                return {"recovered": True}

            worker = TaskWorker(queue, {"recover": recover}, consumer_name="replacement")
            assert await worker.run_once(block_ms=1)
            record = await queue.get(task_id)
            assert record is not None and record.status == TaskStatusEnum.SUCCEEDED
            assert record.result == {"recovered": True}
        finally:
            await _cleanup(redis, prefix)

    _run(exercise())


@pytest.mark.integration
def test_owner_listing_is_isolated_and_newest_first():
    async def exercise():
        redis, queue, prefix = await _fixture()
        try:
            first = await queue.enqueue("noop", {}, owner_id="owner-a")
            await asyncio.sleep(0.002)
            second = await queue.enqueue("noop", {}, owner_id="owner-a")
            await queue.enqueue("noop", {}, owner_id="owner-b")
            records = await queue.list_for_owner("owner-a")
            assert [record.task_id for record in records] == [second, first]
        finally:
            await _cleanup(redis, prefix)

    _run(exercise())


def test_payload_size_is_rejected_before_redis_write():
    async def exercise():
        redis = Redis.from_url(_test_url(), decode_responses=True)
        queue = TaskQueue(
            redis,
            TaskQueueSettings(prefix="unused", max_payload_bytes=8),
        )
        try:
            with pytest.raises(ValueError, match="payload exceeds"):
                await queue.enqueue("large", {"value": "too large"}, owner_id="owner")
        finally:
            await redis.aclose()

    _run(exercise())
