"""Real Redis contract test for the atomic sliding-window limiter."""

from concurrent.futures import ThreadPoolExecutor
import os
import time
import uuid

import pytest


@pytest.mark.integration
def test_redis_limiter_is_atomic_across_concurrent_callers() -> None:
    redis_url = os.getenv("REDIS_RATE_LIMIT_TEST_URL", "").strip()
    if not redis_url:
        pytest.skip("REDIS_RATE_LIMIT_TEST_URL is not configured")

    import redis

    from core.rate_limit import RedisSlidingWindowLimiter

    client = redis.Redis.from_url(redis_url)
    client.ping()

    logical_key = f"integration:{uuid.uuid4().hex}"
    redis_key = f"ratelimit:{logical_key}"
    limiter = RedisSlidingWindowLimiter(limit=5, window_seconds=10, redis_client=client)
    current = time.time()

    try:
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(lambda _: limiter.allow(logical_key, now=current), range(20)))

        assert sum(allowed for allowed, _retry in results) == 5
        assert client.zcard(redis_key) == 5
        assert 1 <= client.ttl(redis_key) <= 10

        # Advancing the score clock beyond the window must remove the old
        # entries and admit a new request without waiting in wall-clock time.
        assert limiter.allow(logical_key, now=current + 11) == (True, 0)
        assert client.zcard(redis_key) == 1
    finally:
        client.delete(redis_key)
