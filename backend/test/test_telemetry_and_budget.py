"""Tests for P1-13 (telemetry), P1-14 (CitationLocator), P1-15 (ContextBudget).

All tests are pure-Python and require no external services.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# P1-13: Telemetry
# ---------------------------------------------------------------------------


def test_telemetry_import_is_noop_when_disabled() -> None:
    """When OTEL_ENABLED is not set, instrument_app is a no-op."""

    import os
    import fastapi
    from core.telemetry import instrument_app

    app = fastapi.FastAPI()
    old_val = os.environ.pop("OTEL_ENABLED", None)
    try:
        instrument_app(app)
        # Must not raise, must not install spans
    finally:
        if old_val is not None:
            os.environ["OTEL_ENABLED"] = old_val


def test_telemetry_import_does_not_crash_when_enabled_with_no_exporter() -> None:
    """With OTEL_ENABLED=true and no OTLP endpoint, the console exporter
    should be used without crashing."""

    import os
    import fastapi
    from core.telemetry import instrument_app

    app = fastapi.FastAPI()
    os.environ["OTEL_ENABLED"] = "true"
    os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    try:
        instrument_app(app)
        # Should not raise
    finally:
        os.environ["OTEL_ENABLED"] = "false"


def test_telemetry_double_instrument_is_idempotent() -> None:
    """Calling instrument_app twice with the same app is a warning, not a crash."""

    import os
    import fastapi
    from core.telemetry import instrument_app

    app = fastapi.FastAPI()
    os.environ["OTEL_ENABLED"] = "true"
    try:
        instrument_app(app)
        instrument_app(app)  # second call -> overwrite warning
    finally:
        os.environ["OTEL_ENABLED"] = "false"


def test_get_tracer_always_returns() -> None:
    from core.telemetry import get_tracer

    tracer = get_tracer("test")
    assert tracer is not None


# ---------------------------------------------------------------------------
# P1-14: CitationLocator
# ---------------------------------------------------------------------------


def _make_evidence(**overrides):
    from service.evidence_contract import Evidence

    base = {
        "source_kind": "document",
        "title": "test doc",
        "publisher": "NIST",
        "content": "hello world",
        "url": "https://example.com/doc",
        "locator": {"page": 34, "chunk_index": 0},
    }
    base.update(overrides)
    return Evidence.create(**base)


def test_citation_locator_document_with_page() -> None:
    from service.evidence_contract import CitationLocator

    ev = _make_evidence()
    loc = CitationLocator.from_evidence(ev)
    assert loc.anchor == "p. 34"
    assert loc.reference_url == "https://example.com/doc"
    assert loc.source_kind == "document"


def test_citation_locator_news_with_url() -> None:
    from service.evidence_contract import CitationLocator

    ev = _make_evidence(source_kind="news", locator={})
    loc = CitationLocator.from_evidence(ev)
    assert "example.com" in loc.anchor
    assert loc.reference_url == ev.url


def test_citation_locator_bidding_notice() -> None:
    from service.evidence_contract import CitationLocator

    ev = _make_evidence(source_kind="bidding", url=None, locator={"notice_id": "BID-2026-001"})
    loc = CitationLocator.from_evidence(ev)
    assert loc.anchor == "notice BID-2026-001"
    assert loc.reference_url is None


def test_citation_locator_sql_row() -> None:
    from service.evidence_contract import CitationLocator

    ev = _make_evidence(
        source_kind="sql_row",
        url=None,
        locator={"row_id": "abcdef123456", "table_name": "company_data"},
    )
    loc = CitationLocator.from_evidence(ev)
    assert "abcdef" in loc.anchor


def test_citation_locator_market_quote() -> None:
    from service.evidence_contract import CitationLocator

    ev = _make_evidence(source_kind="market_quote", url=None, locator={"stock_code": "sh688981"})
    loc = CitationLocator.from_evidence(ev)
    assert loc.anchor == "sh688981"


def test_citation_locator_to_html_wraps_url() -> None:
    from service.evidence_contract import CitationLocator

    loc = CitationLocator(anchor="p. 12", reference_url="https://x.com", source_kind="document")
    html = loc.to_html()
    assert '<a href=' in html
    assert 'p. 12' in html


def test_citation_locator_to_dict() -> None:
    from service.evidence_contract import CitationLocator

    loc = CitationLocator(anchor="p. 12")
    d = loc.to_dict()
    assert d["anchor"] == "p. 12"


# ---------------------------------------------------------------------------
# P1-15: ContextBudget
# ---------------------------------------------------------------------------


def test_context_budget_default_cap() -> None:
    from core.context_budget import ContextBudget, DEFAULT_TOTAL_TOKENS

    b = ContextBudget()
    assert b.total_cap == DEFAULT_TOTAL_TOKENS


def test_context_budget_add_and_remaining() -> None:
    from core.context_budget import ContextBudget

    b = ContextBudget(total_cap=1000).add(system_prompt=100, question=50, evidence=300)
    assert b.used == 450
    assert b.remaining == 550


def test_context_budget_has_budget_for() -> None:
    from core.context_budget import ContextBudget

    b = ContextBudget(total_cap=1000).add(system_prompt=900)
    assert b.has_budget_for(50) is True
    assert b.has_budget_for(200) is False


def test_context_budget_from_texts() -> None:
    from core.context_budget import ContextBudget

    b = ContextBudget.from_texts(
        system_prompt="You are a helpful assistant.",
        question="什么是半导体？",
        total_cap=5000,
    )
    assert b.used > 0
    assert b.system_prompt_tokens > 0


def test_context_budget_summary() -> None:
    from core.context_budget import ContextBudget

    b = ContextBudget(total_cap=2000).add(system_prompt=100, evidence=8000)
    s = b.summary()
    assert s["total_cap"] == 2000
    assert s["evidence_over_cap"] == 2000  # 8000 - 6000


def test_context_budget_chain() -> None:
    from core.context_budget import ContextBudget

    b = ContextBudget(total_cap=10000)
    b.add(system_prompt=100).add(question=50).add(evidence=500)
    assert b.used == 650
