"""Container health probe for persistent task workers."""

from __future__ import annotations

import asyncio

from core.async_tasks import get_task_queue


async def main() -> None:
    queue = get_task_queue()
    workers_key = f"{queue.settings.prefix}:workers"
    workers = await queue.redis.smembers(workers_key)
    alive = False
    for worker in workers:
        if await queue.redis.exists(f"{queue.settings.prefix}:worker:{worker}"):
            alive = True
            break
        await queue.redis.srem(workers_key, worker)
    await queue.redis.aclose()
    if not alive:
        raise SystemExit("no live persistent task consumer heartbeat")


if __name__ == "__main__":
    asyncio.run(main())
