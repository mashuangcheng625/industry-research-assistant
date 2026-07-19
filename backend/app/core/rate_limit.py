"""Rate limiter with process-local + Redis distributed backends (P2-16).

The module provides two sliding-window implementations that share the same
``allow(key) -> (bool, retry_seconds)`` contract:

* ``SlidingWindowRateLimiter`` — single-process, suitable for local dev
  and the portfolio deployment.
* ``RedisSlidingWindowLimiter`` — multi-worker safe, uses Redis sorted
  sets for atomic sliding-window counting.

A factory ``get_rate_limiter()`` picks the Redis variant when the Redis
client is reachable, falling back to the local variant otherwise.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import defaultdict, deque
from typing import Optional, Protocol

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


class RateLimiterProto(Protocol):
    limit: int
    window_seconds: int

    def allow(self, key: str, *, now: float | None = ...) -> tuple[bool, int]: ...


# ---------------------------------------------------------------------------
# Process-local (single-worker) implementation
# ---------------------------------------------------------------------------


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (current - events[0])))
                return False, retry_after
            events.append(current)
            return True, 0


# ---------------------------------------------------------------------------
# Redis (multi-worker) implementation — P2-16
# ---------------------------------------------------------------------------


class RedisSlidingWindowLimiter:
    """Sliding-window rate limiter backed by a Redis sorted set.

    Each ``key`` maps to a sorted set in Redis whose members are
    nanosecond-precision timestamps. The window is enforced by
    ``ZREMRANGEBYSCORE`` before ``ZCARD`` is checked, so every call
    is atomic from the limiter's perspective (two Redis commands per
    ``allow`` invocation).
    """

    SCRIPT_ZADD_COUNT = """
    redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
    local n = redis.call('ZCARD', KEYS[1])
    if tonumber(n) >= tonumber(ARGV[2]) then
        local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')[2]
        return {1, math.ceil(tonumber(ARGV[3]) - (tonumber(ARGV[4]) - tonumber(oldest)))}
    end
    redis.call('ZADD', KEYS[1], ARGV[4], ARGV[4] .. ':' .. redis.call('INCR', KEYS[1] .. ':seq'))
    return {0, 0}
    """

    def __init__(self, limit: int, window_seconds: int = 60, redis_client=None):
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._redis = redis_client
        self._enabled = redis_client is not None

    def allow(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        if not self._enabled:
            return True, 0  # fail-open when Redis is not configured
        current = now or time.time()
        cutoff = current - self.window_seconds
        try:
            redis_key = f"ratelimit:{key}"
            self._redis.zremrangebyscore(redis_key, "-inf", cutoff)
            count = self._redis.zcard(redis_key)
            if count >= self.limit:
                oldest = float((self._redis.zrange(redis_key, 0, 0, withscores=True) or [(b"", cutoff)])[0][1])
                retry_after = max(1, int(self.window_seconds - (current - oldest)))
                return False, retry_after
            self._redis.zadd(redis_key, {f"{current}:{self._redis.incr(redis_key + ':seq')}": current})
            return True, 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis rate limit check failed, falling back to pass: %s", exc)
            return True, 0  # fail-open on Redis errors


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_rate_limiter(limit: int, window_seconds: int = 60, *, name: str = "default") -> RateLimiterProto:
    """Return a Redis-backed limiter when Redis is available, otherwise
    a process-local one. Call once per limiter class (standard /
    research / auth) and hold the returned instance.
    """

    try:
        from core.redis_client import get_redis_client
        client = get_redis_client()
        if client is not None:
            client.ping()
            return RedisSlidingWindowLimiter(limit, window_seconds, client)
    except Exception:
        pass
    return SlidingWindowRateLimiter(limit, window_seconds)


# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------


def _request_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.casefold().startswith("bearer "):
        return "token:" + hashlib.sha256(authorization.encode()).hexdigest()[:24]
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


# ---------------------------------------------------------------------------
# Limiter instances (lazily initialised so tests don't block on Redis)
# ---------------------------------------------------------------------------


_standard_limiter: Optional[RateLimiterProto] = None
_research_limiter: Optional[RateLimiterProto] = None
_auth_limiter: Optional[RateLimiterProto] = None


def _get_standard_limiter() -> RateLimiterProto:
    global _standard_limiter
    if _standard_limiter is None:
        _standard_limiter = get_rate_limiter(
            int(os.getenv("RATE_LIMIT_STANDARD_PER_MINUTE", "60")),
            name="standard",
        )
    return _standard_limiter


def _get_research_limiter() -> RateLimiterProto:
    global _research_limiter
    if _research_limiter is None:
        _research_limiter = get_rate_limiter(
            int(os.getenv("RATE_LIMIT_RESEARCH_PER_MINUTE", "10")),
            name="research",
        )
    return _research_limiter


def _get_auth_limiter() -> RateLimiterProto:
    global _auth_limiter
    if _auth_limiter is None:
        _auth_limiter = get_rate_limiter(
            int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10")),
            name="auth",
        )
    return _auth_limiter


# ---------------------------------------------------------------------------
# Enforcement helpers
# ---------------------------------------------------------------------------


def _enforce(request: Request, limiter: RateLimiterProto) -> None:
    if os.getenv("RATE_LIMIT_ENABLED", "true").strip().casefold() in {"0", "false", "no", "off"}:
        return
    allowed, retry_after = limiter.allow(_request_key(request))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后重试",
            headers={"Retry-After": str(retry_after)},
        )


def enforce_standard_rate_limit(request: Request) -> None:
    _enforce(request, _get_standard_limiter())


def enforce_research_rate_limit(request: Request) -> None:
    _enforce(request, _get_research_limiter())


def enforce_auth_rate_limit(request: Request) -> None:
    _enforce(request, _get_auth_limiter())
