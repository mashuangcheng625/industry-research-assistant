"""Security configuration, rate-limit and protected-route tests."""
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.rate_limit import SlidingWindowRateLimiter  # noqa: E402
from core.security import validate_security_config  # noqa: E402
from core.upload_security import file_signature_matches, safe_upload_filename  # noqa: E402

from core.text2sql_guard import (  # noqa: E402
    GUARD_COPY_DENIED,
    GUARD_COMMENT_DENIED,
    GUARD_DDL_DENIED,
    GUARD_DML_DENIED,
    GUARD_MULTI_STATEMENT,
    GUARD_PARSE_FAIL,
    GUARD_PROCEDURAL_DENIED,
    GUARD_SYSTEM_SCHEMA_DENIED,
)


def test_sliding_window_rate_limiter_releases_expired_events():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("user", now=0) == (True, 0)
    assert limiter.allow("user", now=1) == (True, 0)
    allowed, retry_after = limiter.allow("user", now=2)
    assert allowed is False
    assert retry_after > 0
    assert limiter.allow("user", now=11) == (True, 0)


def test_default_jwt_secret_is_rejected_without_explicit_demo_override():
    with patch("core.security.SECRET_KEY", "your-super-secret-key-change-in-production"), patch.dict(
        "os.environ", {"ALLOW_INSECURE_DEMO_SECRET": "false"}, clear=False
    ):
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            validate_security_config()


def test_explicit_local_demo_override_allows_demo_secret():
    with patch("core.security.SECRET_KEY", "local-demo-change-before-production"), patch.dict(
        "os.environ", {"ALLOW_INSECURE_DEMO_SECRET": "true"}, clear=False
    ):
        validate_security_config()


def test_expensive_routers_require_authentication():
    import app_main
    protected_prefixes = (
        "/chat", "/research", "/knowledge-bases", "/attachments", "/search"
    )
    for route in app_main.app.routes:
        path = getattr(route, "path", "")
        if not path.startswith(protected_prefixes):
            continue
        dependency_names = {
            dependency.call.__name__
            for dependency in route.dependant.dependencies
            if getattr(dependency.call, "__name__", None)
        }
        assert "get_current_user_required" in dependency_names, path


def test_upload_signature_check_rejects_extension_spoofing(tmp_path):
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"not a pdf")
    real_pdf = tmp_path / "real.pdf"
    real_pdf.write_bytes(b"%PDF-1.7\n")
    assert file_signature_matches(str(fake_pdf), ".pdf") is False
    assert file_signature_matches(str(real_pdf), ".pdf") is True


def test_upload_filename_discards_client_path_components():
    assert safe_upload_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert safe_upload_filename(r"..\..\secrets\report.pdf") == "report.pdf"
    assert safe_upload_filename("report.pdf") == "report.pdf"


# ---------------------------------------------------------------------------
# P2-20: content scanner
# ---------------------------------------------------------------------------


def test_scan_result_immutable():
    from core.upload_security import ScanResult
    r = ScanResult(ok=True, code="PASS", detail="clean")
    assert r.ok is True
    assert r.code == "PASS"
    assert r.detail == "clean"


def test_scanner_returns_skipped_when_not_configured():
    """Without CLAMAV_HOST the scanner must return a pass-through result."""
    import os, tempfile
    from core.upload_security import scanner_available, scan_file, SCAN_SKIPPED

    with patch.dict(os.environ, {}, clear=True):
        # force recheck on next call
        if hasattr(scanner_available, "_cached"):
            del scanner_available._cached
        assert scanner_available() is False

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tf.write("hello world\n")
        tf.close()
        try:
            result = scan_file(tf.name)
            assert result.ok is True
        finally:
            os.unlink(tf.name)


def test_scan_valid_text_passes_heuristics():
    import os, tempfile
    from core.upload_security import scan_file, SCAN_SKIPPED

    with patch.dict(os.environ, {}, clear=True):
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tf.write("这是一篇正常的Markdown文档\n# 标题\n正文内容\n")
        tf.close()
        try:
            result = scan_file(tf.name)
            assert result.ok is True
            assert result.backend == "heuristic"
        finally:
            os.unlink(tf.name)


def test_scan_text_with_high_ctrl_chars_rejected():
    import os, tempfile
    from core.upload_security import scan_file

    with patch.dict(os.environ, {}, clear=True):
        tf = tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False)
        # write a short header then a block of control chars
        tf.write(b"normal text\n")
        tf.write(b"\x03\x04\x05\x01\x02" * 200)  # 1000 control chars in a row
        tf.close()
        try:
            result = scan_file(tf.name)
            assert result.ok is False
            assert result.code == "HIGH_CTRL_CHARS"
        finally:
            os.unlink(tf.name)


def test_clamav_instance_called_when_available():
    """When CLAMAV_HOST is set, scan_file must try to connect."""
    import os, tempfile
    from core.upload_security import scanner_available, scan_file, _scan_clamav

    with patch.dict(os.environ, {"CLAMAV_HOST": "127.0.0.1"}, clear=True):
        if hasattr(scanner_available, "_cached"):
            del scanner_available._cached
        # ClamAV is not running locally, so scanner_available returns False.
        assert scanner_available() is False
        # Even when the env var is set, the connection attempt fails,
        # so we fall through to heuristics.
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tf.write("clean text\n")
        tf.close()
        try:
            result = scan_file(tf.name)
            assert result.ok is True
            assert result.backend == "heuristic"
        finally:
            os.unlink(tf.name)


# ---------------------------------------------------------------------------
# P2-16: Redis rate limiter
# ---------------------------------------------------------------------------


def test_redis_sliding_window_limiter_uses_local_fallback_without_client() -> None:
    """A directly constructed Redis limiter must not become unbounded."""

    from core.rate_limit import RedisSlidingWindowLimiter

    limiter = RedisSlidingWindowLimiter(1, window_seconds=10, redis_client=None)
    assert limiter.allow("user", now=1) == (True, 0)
    allowed, retry = limiter.allow("user", now=2)
    assert allowed is False
    assert retry > 0


def test_redis_sliding_window_limiter_executes_one_atomic_script() -> None:
    """The shared quota check must be one Redis operation, not a
    check-then-write sequence that races across workers.
    """

    from core.rate_limit import RedisSlidingWindowLimiter

    client = Mock()
    client.eval.return_value = [1, 0]
    limiter = RedisSlidingWindowLimiter(2, window_seconds=10, redis_client=client)

    assert limiter.allow("user", now=100) == (True, 0)
    client.eval.assert_called_once()
    args = client.eval.call_args.args
    assert args[1] == 1
    assert args[2] == "ratelimit:user"
    assert "ZREMRANGEBYSCORE" in args[0]
    assert "ZADD" in args[0]
    assert "EXPIRE" in args[0]
    client.zremrangebyscore.assert_not_called()
    client.zcard.assert_not_called()
    client.zadd.assert_not_called()


def test_redis_sliding_window_limiter_propagates_script_retry_after() -> None:
    from core.rate_limit import RedisSlidingWindowLimiter

    client = Mock()
    client.eval.return_value = [0, 7]
    limiter = RedisSlidingWindowLimiter(2, window_seconds=10, redis_client=client)

    assert limiter.allow("user", now=100) == (False, 7)


def test_redis_sliding_window_limiter_degrades_to_local_limit_on_error() -> None:
    """Redis failure reduces the guarantee to one process, but must not
    disable rate limiting or reset the process-local window.
    """

    from core.rate_limit import RedisSlidingWindowLimiter

    client = Mock()
    client.eval.side_effect = ([1, 0], RuntimeError("redis unavailable"))
    limiter = RedisSlidingWindowLimiter(1, window_seconds=10, redis_client=client)

    assert limiter.allow("user", now=1) == (True, 0)
    allowed, retry = limiter.allow("user", now=2)
    assert allowed is False
    assert retry > 0


def test_get_rate_limiter_returns_local_when_no_redis() -> None:
    """An unavailable Redis client must select the process-local variant."""

    from core.rate_limit import get_rate_limiter, SlidingWindowRateLimiter

    with patch("core.redis_client.get_redis_client", return_value=None):
        limiter = get_rate_limiter(10)
    assert isinstance(limiter, SlidingWindowRateLimiter)


def test_sliding_window_limiter_can_exhaust_and_recover() -> None:
    """The local limiter must exhaust after ``limit`` calls and release
    after the window passes."""

    from core.rate_limit import SlidingWindowRateLimiter

    limiter = SlidingWindowRateLimiter(2, window_seconds=10)
    assert limiter.allow("u", now=0) == (True, 0)
    assert limiter.allow("u", now=1) == (True, 0)
    allowed, retry = limiter.allow("u", now=2)
    assert allowed is False
    assert retry > 0
    assert limiter.allow("u", now=11) == (True, 0)


def test_removed_legacy_document_routes_are_not_registered():
    import app_main
    paths = {getattr(route, "path", "") for route in app_main.app.routes}
    assert not any(path.startswith("/documents") for path in paths)
    assert "/chat/completion/v1" not in paths


# ---------------------------------------------------------------------------
# Text2SQL safety guard: end-to-end through the service.
# ---------------------------------------------------------------------------


def _make_text2sql_service(max_rows: int = 50):
    """Build a ``Text2SQLService`` with a dummy LLM client and a guard
    sized for these tests."""

    from service.text2sql_service import Text2SQLService

    return Text2SQLService(
        llm_api_key="dummy-key-for-tests",
        llm_base_url="http://localhost/v1",
        db_connection_string=None,
        max_rows=max_rows,
    )


@pytest.mark.parametrize(
    "sql,expected_code",
    [
        ("DROP TABLE industry_stats", GUARD_DDL_DENIED),
        ("DELETE FROM company_data", GUARD_DML_DENIED),
        ("SELECT 1; DROP TABLE industry_stats", GUARD_MULTI_STATEMENT),
        ("SELECT 1 -- comment", GUARD_COMMENT_DENIED),
        ("SELECT * FROM pg_sleep(1)", GUARD_SYSTEM_SCHEMA_DENIED),
        ("COPY industry_stats TO '/tmp/x'", GUARD_COPY_DENIED),
        ("DO $$ BEGIN RAISE NOTICE 'x'; END $$", GUARD_PROCEDURAL_DENIED),
        ("SELEKT 1", GUARD_PARSE_FAIL),
    ],
)
def test_text2sql_service_rejects_injections(sql: str, expected_code: str) -> None:
    """The legacy keyword validator is gone. These smoke cases assert that
    the AST-based guard now sits behind ``Text2SQLService.validate_sql``."""

    svc = _make_text2sql_service()
    ok, message = svc.validate_sql(sql)
    assert not ok, f"{sql!r} unexpectedly accepted"
    assert expected_code in message, f"missing guard code in: {message!r}"


def test_text2sql_service_appends_row_cap_to_legitimate_select() -> None:
    svc = _make_text2sql_service(max_rows=10)
    ok, _msg = svc.validate_sql("SELECT industry_name FROM industry_stats")
    assert ok
    normalized = svc.sql_guard.check("SELECT industry_name FROM industry_stats").sql_normalized
    assert normalized is not None
    # the guard's normalized SQL is what ``execute_sql`` would actually run
    assert normalized.endswith("LIMIT 10")
