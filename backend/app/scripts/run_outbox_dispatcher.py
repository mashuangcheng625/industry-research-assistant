"""Run the PostgreSQL-to-Redis outbox dispatcher."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from prometheus_client import start_http_server

from core.task_outbox import OutboxDispatcher


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("outbox-dispatcher")


async def run() -> None:
    dispatcher = OutboxDispatcher()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop.set)

    start_http_server(int(os.getenv("OUTBOX_METRICS_PORT", "8002")))

    async def maintain_heartbeat() -> None:
        interval = max(1, dispatcher.settings.heartbeat_ttl_seconds // 3)
        while not stop.is_set():
            try:
                await dispatcher.heartbeat()
            except Exception:
                logger.exception("Outbox heartbeat failed")
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def dispatch() -> None:
        logger.info("Outbox dispatcher %s started", dispatcher.dispatcher_id)
        while not stop.is_set():
            try:
                claimed = await dispatcher.dispatch_once()
                if claimed:
                    continue
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=dispatcher.settings.poll_interval_seconds,
                )
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Outbox dispatch loop failed; retrying")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2)
                except asyncio.TimeoutError:
                    pass

    tasks = [
        asyncio.create_task(maintain_heartbeat()),
        asyncio.create_task(dispatch()),
    ]
    await stop.wait()
    logger.info("Stopping outbox dispatcher")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await dispatcher.queue.redis.aclose()


if __name__ == "__main__":
    asyncio.run(run())
