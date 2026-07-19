"""Provider reliability primitives (P1-2).

Every multi-source adapter in this project talks to an upstream that can
time out, return 5xx, or fail to parse JSON. Before P1-2 each adapter
either swallowed the error silently or returned a fabricated empty list.
Both behaviours mask the failure and let the multi-source orchestrator
treat absent data as real evidence.

This module provides a small, well-typed wrapper that runs any callable
against the upstream with:

* explicit per-attempt timeout;
* bounded retry (default: one retry on transient errors only);
* a structured :class:`ProviderOutcome` that always reports
  ``ok`` / ``degraded`` / ``error_code`` / ``attempts`` / ``latency_ms``;
* a hard guarantee that ``data`` is ``None`` whenever ``ok`` is
  ``False`` - i.e. no fabricated payload ever escapes a failed call.

Two flavours are provided:

* :func:`run_provider_async` wraps an ``async`` callable. The async
  path is used by the news, bidding, and stock adapters, which today
  all rely on ``httpx.AsyncClient``.
* :func:`run_provider_sync` wraps a synchronous callable. The sync
  path is kept around for adapters that do not need IO (or that wrap
  the IO in a thread). Timeouts here are advisory - a busy
  non-yielding call may still overrun; the wrapper only reports
  ``PROVIDER_TIMEOUT`` when the underlying ``concurrent.futures``
  future cancels cleanly. SQLAlchemy-style adapters are expected to
  set ``statement_timeout`` at the connection level instead of using
  this path.

The ProviderOutcome dataclass is intentionally narrow - it does not
attempt to model every provider. Callers adapt the ``data`` field to
the provider-specific shape (a list of news items, a market quote, a
set of bidding rows, etc.).

The error code constants are exported so callers and tests can build
shared assertions and dashboards without referring to magic strings.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Outcome codes
# ---------------------------------------------------------------------------

PROVIDER_OK = "PROVIDER_OK"
PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
PROVIDER_HTTP_ERROR = "PROVIDER_HTTP_ERROR"
PROVIDER_PARSE_ERROR = "PROVIDER_PARSE_ERROR"
PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
PROVIDER_UNKNOWN = "PROVIDER_UNKNOWN"

_PROVIDER_CODES = frozenset(
    {
        PROVIDER_OK,
        PROVIDER_TIMEOUT,
        PROVIDER_HTTP_ERROR,
        PROVIDER_PARSE_ERROR,
        PROVIDER_NOT_CONFIGURED,
        PROVIDER_UNKNOWN,
    }
)


# ---------------------------------------------------------------------------
# Outcome type
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProviderOutcome:
    """Structured outcome of a provider call.

    Contract (must hold for every instance returned by ``run_provider_*``):

    * ``ok`` is True iff the call returned real data; in that case
      ``data`` carries that data and ``error_code == PROVIDER_OK``.
    * If ``ok`` is False, ``data`` MUST be ``None`` and ``degraded`` MUST
      be True - the wrapper never fabricates a payload to paper over a
      failure.
    * ``attempts`` records how many upstream calls were made. ``1`` means
      no retry was needed; ``max_attempts`` means we ran out of retries.
    * ``latency_ms`` is the wall-clock time the wrapper spent, including
      backoff between retries.
    """

    ok: bool
    data: Any
    fetched_at: str
    attempts: int
    degraded: bool
    error_code: str
    latency_ms: int
    last_error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.error_code not in _PROVIDER_CODES:
            raise ValueError(f"unknown provider code: {self.error_code!r}")
        if self.ok:
            if self.error_code != PROVIDER_OK:
                raise ValueError("ok=True requires error_code == PROVIDER_OK")
            if self.degraded:
                raise ValueError("ok=True cannot also be degraded")
        else:
            if self.data is not None:
                raise ValueError(
                    "ok=False must come with data=None - never fabricate payload"
                )
            if not self.degraded:
                raise ValueError("ok=False must also be degraded=True")

    # ---- convenience accessors ----

    @property
    def is_timeout(self) -> bool:
        return self.error_code == PROVIDER_TIMEOUT

    @property
    def is_http_error(self) -> bool:
        return self.error_code == PROVIDER_HTTP_ERROR

    @property
    def is_parse_error(self) -> bool:
        return self.error_code == PROVIDER_PARSE_ERROR

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "degraded": self.degraded,
            "error_code": self.error_code,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "fetched_at": self.fetched_at,
            "last_error": self.last_error,
            "data_present": self.data is not None,
        }


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------


def _retryable_http_status(status_code: int) -> bool:
    """5xx and 408 / 429 are worth retrying; 4xx are caller errors."""

    if 500 <= status_code < 600:
        return True
    return status_code in (408, 425, 429)


def _classify_exception(exc: BaseException) -> tuple[str, bool, Optional[str]]:
    """Return ``(error_code, retryable, detail)`` for a given exception.

    ``retryable`` is True when the wrapper should try again; ``detail``
    is a short human-readable summary suitable for logs and tests.
    """

    import httpx  # local import - keeps provider_reliability importable
    # even when httpx is not installed (e.g., minimal CI sanity checks).

    if isinstance(exc, asyncio.TimeoutError):
        return PROVIDER_TIMEOUT, True, "asyncio.TimeoutError"
    if isinstance(exc, httpx.TimeoutException):
        return PROVIDER_TIMEOUT, True, f"httpx.TimeoutException: {exc}"
    if isinstance(exc, httpx.HTTPStatusError):
        retryable = _retryable_http_status(exc.response.status_code)
        return PROVIDER_HTTP_ERROR, retryable, f"HTTP {exc.response.status_code}"
    if isinstance(exc, (httpx.ConnectError, httpx.ReadError, httpx.WriteError)):
        return PROVIDER_HTTP_ERROR, True, f"network: {exc!r}"
    if isinstance(exc, json.JSONDecodeError):
        return PROVIDER_PARSE_ERROR, False, f"json: {exc}"
    return PROVIDER_UNKNOWN, False, f"{type(exc).__name__}: {exc}"


async def run_provider_async(
    factory: Callable[[], Awaitable[T]],
    *,
    timeout_seconds: float,
    max_attempts: int = 2,
    backoff_seconds: float = 0.2,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> ProviderOutcome:
    """Run an async ``factory`` with bounded retry + per-attempt timeout.

    ``factory`` must be an awaitable-producing zero-argument callable;
    it is invoked once per attempt. The wrapper never fabricates data:
    when ``factory`` raises or times out, ``data`` is ``None`` and
    ``degraded`` is ``True``.

    Args:
        factory: callable that returns an awaitable producing the
            provider payload.
        timeout_seconds: per-attempt timeout. Set comfortably above the
            provider's P99 to avoid spurious timeouts but tight enough
            to keep the orchestrator responsive.
        max_attempts: total attempts including the initial call. The
            default of 2 means one retry on top of the first attempt.
        backoff_seconds: linear backoff between attempts. Set to 0 to
            retry immediately.
        sleep: injectable sleep coroutine (tests).
        monotonic: injectable monotonic clock (tests).
    """

    if max_attempts <= 0:
        raise ValueError("max_attempts must be >= 1")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds must be >= 0")

    started = monotonic()
    last_error: Optional[str] = None
    last_code: str = PROVIDER_UNKNOWN
    last_retryable = False
    attempts_used = 0

    for attempt in range(1, max_attempts + 1):
        attempts_used = attempt
        try:
            data = await asyncio.wait_for(factory(), timeout=timeout_seconds)
            return ProviderOutcome(
                ok=True,
                data=data,
                fetched_at=_now_iso(),
                attempts=attempt,
                degraded=False,
                error_code=PROVIDER_OK,
                latency_ms=int((monotonic() - started) * 1000),
                last_error=None,
            )
        except BaseException as exc:  # noqa: BLE001 - explicit error funnel
            code, retryable, detail = _classify_exception(exc)
            last_error = detail
            last_code = code
            last_retryable = retryable
            logger.warning(
                "provider attempt %d/%d failed: %s",
                attempt,
                max_attempts,
                detail,
            )
            if not retryable or attempt >= max_attempts:
                break
            # back off before retrying
            if backoff_seconds:
                await sleep(backoff_seconds * attempt)

    return ProviderOutcome(
        ok=False,
        data=None,
        fetched_at=_now_iso(),
        attempts=attempts_used,
        degraded=True,
        error_code=last_code,
        latency_ms=int((monotonic() - started) * 1000),
        last_error=last_error,
    )


# ---------------------------------------------------------------------------
# Sync wrapper (used when an adapter has no async surface)
# ---------------------------------------------------------------------------


def run_provider_sync(
    callable_: Callable[[], T],
    *,
    timeout_seconds: float,
    max_attempts: int = 2,
    backoff_seconds: float = 0.2,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> ProviderOutcome:
    """Sync counterpart to :func:`run_provider_async`.

    The timeout is enforced via a worker thread. Use this only for
    providers that cannot be made async (DB drivers without async
    support, pure-Python processors, ...). For SQL execution prefer a
    ``statement_timeout`` set on the connection instead - thread-based
    timeouts cannot interrupt non-yielding native code.
    """

    if max_attempts <= 0:
        raise ValueError("max_attempts must be >= 1")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be > 0")

    import concurrent.futures

    started = monotonic()
    last_error: Optional[str] = None
    last_code: str = PROVIDER_UNKNOWN
    attempts_used = 0

    for attempt in range(1, max_attempts + 1):
        attempts_used = attempt
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(callable_)
                data = future.result(timeout=timeout_seconds)
            return ProviderOutcome(
                ok=True,
                data=data,
                fetched_at=_now_iso(),
                attempts=attempt,
                degraded=False,
                error_code=PROVIDER_OK,
                latency_ms=int((monotonic() - started) * 1000),
                last_error=None,
            )
        except concurrent.futures.TimeoutError:
            last_error = f"timeout after {timeout_seconds}s"
            last_code = PROVIDER_TIMEOUT
            logger.warning("provider sync attempt %d timed out", attempt)
        except json.JSONDecodeError as exc:
            last_error = f"json: {exc}"
            last_code = PROVIDER_PARSE_ERROR
            break
        except Exception as exc:  # noqa: BLE001 - funnel
            last_error = f"{type(exc).__name__}: {exc}"
            last_code = PROVIDER_UNKNOWN
            logger.warning("provider sync attempt %d failed: %s", attempt, last_error)
            break
        if backoff_seconds and attempt < max_attempts:
            sleep(backoff_seconds * attempt)

    return ProviderOutcome(
        ok=False,
        data=None,
        fetched_at=_now_iso(),
        attempts=attempts_used,
        degraded=True,
        error_code=last_code,
        latency_ms=int((monotonic() - started) * 1000),
        last_error=last_error,
    )


__all__ = [
    "PROVIDER_OK",
    "PROVIDER_TIMEOUT",
    "PROVIDER_HTTP_ERROR",
    "PROVIDER_PARSE_ERROR",
    "PROVIDER_NOT_CONFIGURED",
    "PROVIDER_UNKNOWN",
    "ProviderOutcome",
    "run_provider_async",
    "run_provider_sync",
]
