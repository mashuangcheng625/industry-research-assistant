"""Security configuration, rate-limit and protected-route tests."""
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.rate_limit import SlidingWindowRateLimiter  # noqa: E402
from core.security import validate_security_config  # noqa: E402
from router.document_router import _file_signature_matches  # noqa: E402


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
    protected_prefixes = ("/chat", "/research", "/documents", "/search")
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
    assert _file_signature_matches(str(fake_pdf), ".pdf") is False
    assert _file_signature_matches(str(real_pdf), ".pdf") is True
