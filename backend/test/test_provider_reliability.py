"""Tests for the provider reliability wrapper (P1-2).

The wrapper enforces a strict no-fabrication contract: every call that
raises or times out must produce an outcome with ``data=None`` and
``degraded=True``. The tests below drive the wrapper against synthetic
factories that simulate the failures a real upstream can throw
(timeouts, 5xx, 4xx, network errors, JSON parse errors) and assert
both the outcome shape and the retry/back-off behaviour.

The async tests use ``asyncio.run()`` so they run under the default
pytest plugin set without depending on ``pytest-asyncio``. ``httpx``
exceptions are constructed in-process so the classifier exercises
the same code path it does in production.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, List

import httpx
import pytest

from core.provider_reliability import (
    PROVIDER_OK,
    PROVIDER_TIMEOUT,
    PROVIDER_HTTP_ERROR,
    PROVIDER_PARSE_ERROR,
    PROVIDER_UNKNOWN,
    ProviderOutcome,
    run_provider_async,
    run_provider_sync,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _outcome(**overrides) -> ProviderOutcome:
    base = dict(
        ok=True,
        data=None,
        fetched_at="2026-01-01T00:00:00+00:00",
        attempts=1,
        degraded=False,
        error_code=PROVIDER_OK,
        latency_ms=10,
        last_error=None,
    )
    base.update(overrides)
    return ProviderOutcome(**base)


def _run(coro):
    """Run an awaitable synchronously inside pytest."""

    return asyncio.run(coro)


def _build_response(status_code: int) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://example.test/x"),
        text="server text",
    )


# ---------------------------------------------------------------------------
# Constructor invariants
# ---------------------------------------------------------------------------


def test_outcome_ok_requires_error_code_ok() -> None:
    with pytest.raises(ValueError):
        _outcome(ok=True, data=[], error_code=PROVIDER_TIMEOUT)


def test_outcome_failure_cannot_have_data() -> None:
    """No fabrication: ok=False forces data=None."""

    with pytest.raises(ValueError, match="fabricate"):
        _outcome(ok=False, data={"fake": True}, degraded=True, error_code=PROVIDER_UNKNOWN)


def test_outcome_failure_requires_degraded() -> None:
    with pytest.raises(ValueError, match="degraded"):
        _outcome(ok=False, data=None, degraded=False, error_code=PROVIDER_UNKNOWN)


def test_outcome_unknown_error_code_rejected() -> None:
    with pytest.raises(ValueError):
        _outcome(error_code="SOMETHING_NEW")


def test_outcome_to_dict_hides_payload() -> None:
    """``data`` is not serialised in ``to_dict`` - downstream logs /
    dashboards see only metadata, never the raw payload."""

    outcome = _outcome(ok=True, data={"secret": "value"})
    serialized = outcome.to_dict()
    assert "secret" not in serialized
    assert serialized["data_present"] is True


# ---------------------------------------------------------------------------
# Async happy path
# ---------------------------------------------------------------------------


def test_async_success_returns_data_on_first_attempt() -> None:
    async def factory() -> List[int]:
        return [1, 2, 3]

    outcome = _run(
        run_provider_async(factory, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    )
    assert outcome.ok is True
    assert outcome.degraded is False
    assert outcome.data == [1, 2, 3]
    assert outcome.error_code == PROVIDER_OK
    assert outcome.attempts == 1
    assert outcome.latency_ms >= 0


def test_async_attempts_increments_on_retry() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("first attempt fails")
        return "ok"

    outcome = _run(
        run_provider_async(flaky, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    )
    assert outcome.ok is True
    assert outcome.attempts == 2
    assert outcome.data == "ok"


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


def test_async_timeout_returns_degraded_without_data() -> None:
    async def slow() -> str:
        await asyncio.sleep(2.0)
        return "late"

    outcome = _run(
        run_provider_async(slow, timeout_seconds=0.05, max_attempts=1, backoff_seconds=0.0)
    )
    assert outcome.ok is False
    assert outcome.degraded is True
    assert outcome.data is None
    assert outcome.error_code == PROVIDER_TIMEOUT
    assert outcome.attempts == 1


def test_async_timeout_with_retry_then_success() -> None:
    """Two timeouts followed by a fast success - the wrapper should
    retry until the budget is exhausted."""

    calls = {"n": 0}

    async def eventually_fast() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            await asyncio.sleep(2.0)
        return f"call-{calls['n']}"

    outcome = _run(
        run_provider_async(
            eventually_fast,
            timeout_seconds=0.05,
            max_attempts=3,
            backoff_seconds=0.0,
        )
    )
    assert outcome.ok is True
    assert outcome.attempts == 3
    assert outcome.data == "call-3"


# ---------------------------------------------------------------------------
# HTTP errors
# ---------------------------------------------------------------------------


def test_async_http_5xx_retries_until_budget_exhausted() -> None:
    calls = {"n": 0}

    async def always_500() -> str:
        calls["n"] += 1
        raise httpx.HTTPStatusError(
            "boom",
            request=httpx.Request("GET", "https://example/"),
            response=_build_response(503),
        )

    outcome = _run(
        run_provider_async(always_500, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    )
    assert outcome.ok is False
    assert outcome.degraded is True
    assert outcome.data is None
    assert outcome.error_code == PROVIDER_HTTP_ERROR
    assert outcome.attempts == 3


def test_async_http_4xx_is_terminal_no_retry() -> None:
    """4xx is a caller error - retrying wastes the budget."""

    calls = {"n": 0}

    async def bad_request() -> str:
        calls["n"] += 1
        raise httpx.HTTPStatusError(
            "bad",
            request=httpx.Request("GET", "https://example/"),
            response=_build_response(400),
        )

    outcome = _run(
        run_provider_async(bad_request, timeout_seconds=1.0, max_attempts=5, backoff_seconds=0.0)
    )
    assert outcome.ok is False
    assert outcome.attempts == 1
    assert outcome.error_code == PROVIDER_HTTP_ERROR


def test_async_http_429_is_retryable() -> None:
    calls = {"n": 0}

    async def rate_limited() -> str:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.HTTPStatusError(
                "slow down",
                request=httpx.Request("GET", "https://example/"),
                response=_build_response(429),
            )
        return "ok"

    outcome = _run(
        run_provider_async(rate_limited, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    )
    assert outcome.ok is True
    assert outcome.attempts == 2


# ---------------------------------------------------------------------------
# JSON parse
# ---------------------------------------------------------------------------


def test_async_json_decode_error_is_terminal() -> None:
    calls = {"n": 0}

    async def returns_garbage() -> Any:
        calls["n"] += 1
        raise json.JSONDecodeError("bad json", "x", 0)

    outcome = _run(
        run_provider_async(returns_garbage, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    )
    assert outcome.ok is False
    assert outcome.error_code == PROVIDER_PARSE_ERROR
    assert outcome.attempts == 1  # parse errors are not retried


# ---------------------------------------------------------------------------
# Unknown exceptions
# ---------------------------------------------------------------------------


def test_async_unknown_exception_is_terminal() -> None:
    calls = {"n": 0}

    async def boom() -> str:
        calls["n"] += 1
        raise RuntimeError("kaboom")

    outcome = _run(
        run_provider_async(boom, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    )
    assert outcome.ok is False
    assert outcome.error_code == PROVIDER_UNKNOWN
    assert outcome.attempts == 1


# ---------------------------------------------------------------------------
# Sync wrapper
# ---------------------------------------------------------------------------


def test_sync_success() -> None:
    r = run_provider_sync(lambda: {"x": 1}, timeout_seconds=1.0)
    assert r.ok is True
    assert r.data == {"x": 1}
    assert r.attempts == 1


def test_sync_timeout_returns_degraded() -> None:
    def slow() -> int:
        time.sleep(2.0)
        return 1

    r = run_provider_sync(slow, timeout_seconds=0.1, max_attempts=1, backoff_seconds=0.0)
    assert r.ok is False
    assert r.error_code == PROVIDER_TIMEOUT
    assert r.data is None
    assert r.attempts == 1


def test_sync_json_error_is_terminal() -> None:
    def bad() -> Any:
        raise json.JSONDecodeError("bad", "x", 0)

    r = run_provider_sync(bad, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    assert r.ok is False
    assert r.error_code == PROVIDER_PARSE_ERROR
    assert r.attempts == 1


def test_sync_unknown_exception_is_terminal() -> None:
    def boom() -> Any:
        raise RuntimeError("kaboom")

    r = run_provider_sync(boom, timeout_seconds=1.0, max_attempts=3, backoff_seconds=0.0)
    assert r.ok is False
    assert r.error_code == PROVIDER_UNKNOWN
    assert r.attempts == 1


# ---------------------------------------------------------------------------
# Backoff & retry-budget
# ---------------------------------------------------------------------------


def test_async_backoff_waits_between_attempts() -> None:
    sleeps: List[float] = []

    async def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    async def always_5xx() -> str:
        raise httpx.HTTPStatusError(
            "x",
            request=httpx.Request("GET", "u"),
            response=_build_response(500),
        )

    outcome = _run(
        run_provider_async(
            always_5xx,
            timeout_seconds=1.0,
            max_attempts=3,
            backoff_seconds=0.1,
            sleep=fake_sleep,
        )
    )
    assert outcome.ok is False
    assert outcome.attempts == 3
    # backoff is linear: attempt 1 -> 0.1, attempt 2 -> 0.2, no third sleep
    assert sleeps == [0.1, 0.2]


def test_async_max_attempts_one_does_not_retry() -> None:
    calls = {"n": 0}

    async def fails_once() -> str:
        calls["n"] += 1
        raise httpx.ConnectError("nope")

    outcome = _run(
        run_provider_async(fails_once, timeout_seconds=1.0, max_attempts=1, backoff_seconds=0.0)
    )
    assert outcome.attempts == 1
    assert calls["n"] == 1


def test_async_zero_backoff_skips_sleep() -> None:
    sleeps: List[float] = []

    async def fake_sleep(duration: float) -> None:
        sleeps.append(duration)

    async def always_5xx() -> str:
        raise httpx.HTTPStatusError(
            "x",
            request=httpx.Request("GET", "u"),
            response=_build_response(500),
        )

    _run(
        run_provider_async(
            always_5xx,
            timeout_seconds=1.0,
            max_attempts=3,
            backoff_seconds=0.0,
            sleep=fake_sleep,
        )
    )
    assert sleeps == []


def test_async_rejects_invalid_arguments() -> None:
    async def factory() -> None:
        return None

    async def go() -> None:
        with pytest.raises(ValueError):
            await run_provider_async(factory, timeout_seconds=1.0, max_attempts=0)
        with pytest.raises(ValueError):
            await run_provider_async(factory, timeout_seconds=0.0, max_attempts=1)
        with pytest.raises(ValueError):
            await run_provider_async(
                factory, timeout_seconds=1.0, max_attempts=2, backoff_seconds=-1.0
            )

    _run(go())


# ---------------------------------------------------------------------------
# Classifier sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc,expected_code,retryable",
    [
        (asyncio.TimeoutError(), PROVIDER_TIMEOUT, True),
        (httpx.ConnectError("x"), PROVIDER_HTTP_ERROR, True),
        (httpx.ReadError("x"), PROVIDER_HTTP_ERROR, True),
        (
            httpx.HTTPStatusError("x", request=httpx.Request("GET", "u"), response=_build_response(503)),
            PROVIDER_HTTP_ERROR,
            True,
        ),
        (
            httpx.HTTPStatusError("x", request=httpx.Request("GET", "u"), response=_build_response(400)),
            PROVIDER_HTTP_ERROR,
            False,
        ),
        (
            httpx.HTTPStatusError("x", request=httpx.Request("GET", "u"), response=_build_response(429)),
            PROVIDER_HTTP_ERROR,
            True,
        ),
        (json.JSONDecodeError("x", "x", 0), PROVIDER_PARSE_ERROR, False),
        (RuntimeError("x"), PROVIDER_UNKNOWN, False),
    ],
)
def test_classify_exception(exc: BaseException, expected_code: str, retryable: bool) -> None:
    from core.provider_reliability import _classify_exception

    code, can_retry, detail = _classify_exception(exc)
    assert code == expected_code
    assert can_retry == retryable
    assert detail
