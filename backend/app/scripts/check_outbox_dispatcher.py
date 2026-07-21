"""Container health probe for the transactional outbox dispatcher."""

from __future__ import annotations

import asyncio

from core.async_tasks import get_task_queue


async def main() -> None:
    queue = get_task_queue()
    dispatchers_key = f"{queue.settings.prefix}:outbox-dispatchers"
    dispatchers = await queue.redis.smembers(dispatchers_key)
    alive = False
    for dispatcher_id in dispatchers:
        key = f"{queue.settings.prefix}:outbox-dispatcher:{dispatcher_id}"
        if await queue.redis.exists(key):
            alive = True
            break
        await queue.redis.srem(dispatchers_key, dispatcher_id)
    await queue.redis.aclose()
    if not alive:
        raise SystemExit("no live transactional outbox dispatcher heartbeat")


if __name__ == "__main__":
    asyncio.run(main())
