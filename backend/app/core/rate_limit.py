"""Small process-local sliding-window limiter for API abuse protection.

This is a single-process safety boundary for the portfolio deployment. A
multi-worker deployment must replace it with the existing Redis service.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


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


def _request_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.casefold().startswith("bearer "):
        return "token:" + hashlib.sha256(authorization.encode()).hexdigest()[:24]
    host = request.client.host if request.client else "unknown"
    return f"ip:{host}"


_standard_limiter = SlidingWindowRateLimiter(
    int(os.getenv("RATE_LIMIT_STANDARD_PER_MINUTE", "60"))
)
_research_limiter = SlidingWindowRateLimiter(
    int(os.getenv("RATE_LIMIT_RESEARCH_PER_MINUTE", "10"))
)
_auth_limiter = SlidingWindowRateLimiter(
    int(os.getenv("RATE_LIMIT_AUTH_PER_MINUTE", "10"))
)


def _enforce(request: Request, limiter: SlidingWindowRateLimiter) -> None:
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
    _enforce(request, _standard_limiter)


def enforce_research_rate_limit(request: Request) -> None:
    _enforce(request, _research_limiter)


def enforce_auth_rate_limit(request: Request) -> None:
    _enforce(request, _auth_limiter)
