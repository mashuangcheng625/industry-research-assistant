"""Run the persistent Redis task worker as a standalone process."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from prometheus_client import start_http_server

from core.async_tasks import TaskWorker, get_task_queue
from service.task_handlers import get_task_handlers

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("task-worker")


async def run() -> None:
    queue = get_task_queue()
    await queue.ensure_group()
    start_http_server(int(os.getenv("TASK_WORKER_METRICS_PORT", "8001")))
    concurrency = max(1, int(os.getenv("TASK_WORKER_CONCURRENCY", "2")))
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop.set)

    async def maintain_heartbeat() -> None:
        supervisor = TaskWorker(
            queue,
            {},
            consumer_name=f"worker-{os.getpid()}-supervisor",
        )
        interval = max(1, queue.settings.heartbeat_ttl_seconds // 3)
        while not stop.is_set():
            await supervisor.heartbeat()
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def consume(slot: int) -> None:
        worker = TaskWorker(queue, get_task_handlers(), consumer_name=f"worker-{os.getpid()}-{slot}")
        logger.info("Persistent task consumer %s started", worker.consumer_name)
        while not stop.is_set():
            try:
                await worker.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Task consumer loop failed; retrying")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2)
                except asyncio.TimeoutError:
                    pass

    heartbeat = asyncio.create_task(maintain_heartbeat())
    consumers = [asyncio.create_task(consume(slot)) for slot in range(concurrency)]
    await stop.wait()
    logger.info("Stopping persistent task worker after current Redis read")
    for consumer in consumers:
        consumer.cancel()
    heartbeat.cancel()
    await asyncio.gather(heartbeat, *consumers, return_exceptions=True)
    await queue.redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
