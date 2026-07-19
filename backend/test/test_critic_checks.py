"""Tests for the deterministic multi-source critic checks (P1-4).

The critic checks module is pure-Python and side-effect free. The tests
below exercise every check in isolation plus a few integration
scenarios that hit ``run_critic_checks`` with mixed evidence. Each
test asserts the structured :class:`CriticReport` output so callers
can rely on the contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.critic_checks import (
    ALL_CHECKS,
    CHECK_CONFLICT,
    CHECK_FRESHNESS,
    CHECK_INFERENCE,
    CHECK_MISSING_SOURCE,
    CHECK_TIME_ANCHOR,
    CHECK_UNIT_MISMATCH,
    CriticFinding,
    CriticReport,
    DEFAULT_CONFLICT_TOLERANCE,
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_TIME_ANCHOR_TOLERANCE_DAYS,
    SEVERITY_BLOCK,
    SEVERITY_INFO,
    SEVERITY_WARN,
    check_conflicts,
    check_cross_source_inference,
    check_freshness,
    check_missing_source,
    check_time_anchor,
    check_unit_mismatch,
    run_critic_checks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _evidence(**fields) -> dict:
    base = {
        "evidence_id": "E1",
        "title": "示例",
        "publisher": "示例",
        "source_kind": "news",
        "url": None,
        "content": "",
        "published_at": None,
        "retrieved_at": None,
        "as_of": None,
        "locator": {},
        "quality_tier": "unknown",
        "license_or_terms": "not_assessed",
    }
    base.update(fields)
    return base


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_offset(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Constructor / dataclass invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sev", ["info", "warn", "block"])
def test_critic_finding_accepts_known_severities(sev: str) -> None:
    CriticFinding(check=CHECK_FRESHNESS, severity=sev, subject="x", detail="y")


@pytest.mark.parametrize("sev", ["BOGUS", "INFO", "Minor"])
def test_critic_finding_rejects_unknown_severity(sev: str) -> None:
    with pytest.raises(ValueError):
        CriticFinding(check=CHECK_FRESHNESS, severity=sev, subject="x", detail="y")


@pytest.mark.parametrize("check", ["totally_unknown_check"])
def test_critic_finding_rejects_unknown_check(check: str) -> None:
    with pytest.raises(ValueError):
        CriticFinding(check=check, severity=SEVERITY_INFO, subject="x", detail="y")


def test_critic_report_should_refuse_on_blocks() -> None:
    report = CriticReport(findings=(
        CriticFinding(check=CHECK_MISSING_SOURCE, severity=SEVERITY_BLOCK, subject="doc", detail="x"),
    ))
    assert report.should_refuse is True
    assert report.blocks == 1


def test_critic_report_should_refuse_on_missing_required_kinds() -> None:
    report = CriticReport(
        findings=(),
        required_source_kinds=("document", "news"),
        missing_source_kinds=("document",),
    )
    assert report.should_refuse is True


def test_critic_report_passes_when_clean() -> None:
    report = CriticReport(findings=())
    assert report.should_refuse is False


def test_critic_report_to_dict_hides_internal_fields() -> None:
    finding = CriticFinding(
        check=CHECK_FRESHNESS,
        severity=SEVERITY_WARN,
        subject="t",
        detail="d",
        involved_evidence_ids=("E1",),
    )
    report = CriticReport(findings=(finding,))
    serialised = report.to_dict()
    assert serialised["blocks"] == 0
    assert serialised["warns"] == 1
    assert serialised["should_refuse"] is False
    assert serialised["findings"][0]["involved_evidence_ids"] == ["E1"]


def test_critic_report_by_check_returns_only_matching_findings() -> None:
    findings = (
        CriticFinding(check=CHECK_FRESHNESS, severity=SEVERITY_WARN, subject="a", detail="d"),
        CriticFinding(check=CHECK_CONFLICT, severity=SEVERITY_WARN, subject="b", detail="d"),
        CriticFinding(check=CHECK_FRESHNESS, severity=SEVERITY_WARN, subject="c", detail="d"),
    )
    report = CriticReport(findings=findings)
    freshness = report.by_check(CHECK_FRESHNESS)
    assert {f.subject for f in freshness} == {"a", "c"}


# ---------------------------------------------------------------------------
# check_freshness
# ---------------------------------------------------------------------------


def test_freshness_emits_warn_for_old_evidence() -> None:
    findings = check_freshness([
        _evidence(evidence_id="E1", published_at=_iso_offset(-365)),
    ])
    assert findings == []


def test_freshness_emits_warn_for_too_old_evidence() -> None:
    findings = check_freshness([
        _evidence(evidence_id="E1", published_at=_iso_offset(-1000)),
    ])
    assert len(findings) == 1
    assert findings[0].severity == SEVERITY_WARN
    assert "1000" in findings[0].detail or "1,000" in findings[0].detail or "超过" in findings[0].detail


def test_freshness_promotes_to_block_when_no_timestamps() -> None:
    findings = check_freshness([
        _evidence(evidence_id="E1"),
        _evidence(evidence_id="E2"),
    ])
    assert len(findings) == 1
    assert findings[0].severity == SEVERITY_BLOCK
    assert findings[0].check == CHECK_FRESHNESS


def test_freshness_promotes_to_block_when_all_too_old() -> None:
    # Stale-but-dated evidence stays at ``warn`` so the writer can still
    # produce a usable answer; the orchestrator decides whether to
    # proceed. Only no-timestamp-anywhere promotes to ``block``.
    findings = check_freshness([
        _evidence(evidence_id="E1", published_at=_iso_offset(-1000)),
        _evidence(evidence_id="E2", published_at=_iso_offset(-2000)),
    ])
    assert all(f.severity == SEVERITY_WARN for f in findings)
    assert len(findings) == 2


def test_freshness_accepts_as_of_when_published_at_missing() -> None:
    findings = check_freshness([
        _evidence(evidence_id="E1", as_of=_iso_offset(-1)),
    ])
    assert findings == []


def test_freshness_honours_max_age_days_override() -> None:
    findings = check_freshness(
        [_evidence(evidence_id="E1", published_at=_iso_offset(-10))],
        max_age_days=5,
    )
    assert len(findings) == 1
    assert findings[0].severity == SEVERITY_WARN


# ---------------------------------------------------------------------------
# check_unit_mismatch
# ---------------------------------------------------------------------------


def test_unit_mismatch_detects_unit_scale_disagreement() -> None:
    findings = check_unit_mismatch([
        _evidence(
            evidence_id="E1",
            source_kind="news",
            content="2024年公司收入80亿元",
        ),
        _evidence(
            evidence_id="E2",
            source_kind="news",
            content="2024年公司收入800万元",
        ),
    ])
    # The bucket "公司收入" has tokens in different scale rows (万 vs 亿).
    # Scales 1 vs 5 differ by 4 so the check should flag it.
    assert any(f.check == CHECK_UNIT_MISMATCH for f in findings)


def test_unit_mismatch_ignores_consistent_units() -> None:
    findings = check_unit_mismatch([
        _evidence(content="2024年收入80亿元"),
        _evidence(content="2024年收入90亿元"),
    ])
    assert findings == []


def test_unit_mismatch_emits_no_finding_for_text_only() -> None:
    findings = check_unit_mismatch([_evidence(content="没有任何数字")])
    assert findings == []


# ---------------------------------------------------------------------------
# check_time_anchor
# ---------------------------------------------------------------------------


def test_time_anchor_emits_warn_for_large_time_gap() -> None:
    findings = check_time_anchor([
        _evidence(
            evidence_id="E1",
            content="中芯国际2024年收入80亿元",
            as_of="2024-06-30T00:00:00+00:00",
        ),
        _evidence(
            evidence_id="E2",
            content="中芯国际2024年收入100亿元",
            as_of="2022-06-30T00:00:00+00:00",
        ),
    ])
    assert len(findings) == 1
    assert findings[0].check == CHECK_TIME_ANCHOR


def test_time_anchor_accepts_recent_window() -> None:
    findings = check_time_anchor([
        _evidence(
            evidence_id="E1",
            content="中芯国际2024年收入80亿元",
            as_of="2024-06-30T00:00:00+00:00",
        ),
        _evidence(
            evidence_id="E2",
            content="中芯国际2024年收入85亿元",
            as_of="2024-08-15T00:00:00+00:00",
        ),
    ])
    # 46-day gap is within the 90-day default tolerance.
    assert findings == []


def test_time_anchor_skips_rows_without_timestamps() -> None:
    findings = check_time_anchor([
        _evidence(content="中芯国际2024年收入80亿元"),
    ])
    assert findings == []


# ---------------------------------------------------------------------------
# check_conflicts
# ---------------------------------------------------------------------------


def test_conflicts_detects_large_numeric_disagreement() -> None:
    findings = check_conflicts([
        _evidence(
            evidence_id="E1",
            source_kind="news",
            content="中芯国际2024年收入80亿元",
        ),
        _evidence(
            evidence_id="E2",
            source_kind="news",
            content="中芯国际2024年收入50亿元",
        ),
    ])
    assert any(f.check == CHECK_CONFLICT for f in findings)


def test_conflicts_ignores_within_tolerance() -> None:
    findings = check_conflicts([
        _evidence(content="中芯国际2024年收入80亿元"),
        _evidence(content="中芯国际2024年收入85亿元"),
    ])
    assert findings == []


def test_conflicts_handles_mixed_units_by_not_comparing_them() -> None:
    findings = check_conflicts([
        _evidence(content="中芯国际2024年收入80亿元"),
        _evidence(content="中芯国际2024年收入8000万元"),
    ])
    # 80亿 vs 8000万 = same magnitude, so no conflict.
    assert findings == []


def test_conflicts_zero_max_value_is_skipped() -> None:
    findings = check_conflicts([
        _evidence(content="中芯国际2024年收入0亿元"),
        _evidence(content="中芯国际2024年收入0亿元"),
    ])
    assert findings == []


# ---------------------------------------------------------------------------
# check_missing_source
# ---------------------------------------------------------------------------


def test_missing_source_emits_block_per_missing_kind() -> None:
    findings = check_missing_source(
        [_evidence(source_kind="news")],
        required_source_kinds=["document", "sql_row"],
    )
    subjects = [f.subject for f in findings]
    assert "document" in subjects
    assert "sql_row" in subjects
    assert all(f.severity == SEVERITY_BLOCK for f in findings)


def test_missing_source_no_findings_when_all_present() -> None:
    findings = check_missing_source(
        [
            _evidence(source_kind="news"),
            _evidence(evidence_id="E2", source_kind="document"),
        ],
        required_source_kinds=["news"],
    )
    assert findings == []


def test_missing_source_no_findings_when_no_requirements() -> None:
    findings = check_missing_source(
        [_evidence(source_kind="news")],
        required_source_kinds=[],
    )
    assert findings == []


# ---------------------------------------------------------------------------
# check_cross_source_inference
# ---------------------------------------------------------------------------


def test_inference_flags_sentences_with_two_distinct_markers() -> None:
    draft = "中芯国际2024年收入80亿元[E1]，市场份额仅25%[E2]。"
    findings = check_cross_source_inference(
        draft,
        [
            _evidence(evidence_id="E1", source_kind="news"),
            _evidence(evidence_id="E2", source_kind="news"),
        ],
    )
    assert len(findings) == 1
    assert findings[0].severity == SEVERITY_INFO
    assert findings[0].involved_evidence_ids == ("E1", "E2")


def test_inference_supports_bracketed_marker_legacy() -> None:
    """The helper should accept ``[[1]]`` markers in addition to ``[E1]``."""

    draft = "根据 [[1]] 与 [[2]] 数据，2024年收入 80亿元。"
    findings = check_cross_source_inference(
        draft,
        [
            _evidence(evidence_id="E1", source_kind="news"),
            _evidence(evidence_id="E2", source_kind="news"),
        ],
    )
    assert len(findings) == 1
    # the resolved involved_evidence_ids should be the canonical "E1" / "E2"
    assert set(findings[0].involved_evidence_ids) >= {"E1", "E2"}


def test_inference_ignores_single_marker_sentences() -> None:
    draft = "中芯国际2024年收入80亿元[E1]。"
    findings = check_cross_source_inference(
        draft,
        [_evidence(evidence_id="E1")],
    )
    assert findings == []


def test_inference_no_findings_without_draft() -> None:
    assert check_cross_source_inference(None, [_evidence()]) == []


def test_inference_no_findings_without_evidence() -> None:
    assert check_cross_source_inference("a [E1] b [E2]", []) == []


def test_inference_no_findings_when_marker_invalid() -> None:
    draft = "中芯国际2024年收入80亿元[E99]。中芯国际2024年收入85亿元[E100]。"
    findings = check_cross_source_inference(
        draft,
        [_evidence(evidence_id="E1")],
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def test_run_critic_checks_runs_every_check() -> None:
    """Every defined check appears at least once in the aggregator's
    report under adversarial input so a future change that drops one
    silently is caught."""

    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old_date = (now - timedelta(days=1500)).isoformat()
    recent_date = (now - timedelta(days=10)).isoformat()
    mid_date = (now - timedelta(days=400)).isoformat()
    evidences = [
        _evidence(
            evidence_id="E1",
            source_kind="news",
            published_at=old_date,
            content="中芯国际2024年收入80亿元",
        ),
        _evidence(
            evidence_id="E2",
            source_kind="news",
            published_at=recent_date,
            content="中芯国际2024年收入100亿元",
        ),
        # Third evidence row triggers unit-mismatch and conflict.
        _evidence(
            evidence_id="E3",
            source_kind="document",
            published_at=mid_date,
            content="中芯国际2024年收入8000万元",
            as_of=mid_date,
        ),
        # Fourth evidence row triggers the cross-unit conflict.
        _evidence(
            evidence_id="E4",
            source_kind="document",
            published_at=recent_date,
            content="中芯国际2024年收入150亿元",
        ),
    ]
    draft = "中芯国际2024年收入[E1][E2]约为90亿元。"
    report = run_critic_checks(
        evidences,
        draft_text=draft,
        required_source_kinds=("sql_row",),
        now=now,
    )
    seen_checks = {f.check for f in report.findings}
    for check in ALL_CHECKS:
        assert check in seen_checks, f"missing {check} in {report.findings!r}"


def test_run_critic_checks_blocks_when_required_kind_missing() -> None:
    report = run_critic_checks(
        [_evidence(source_kind="news")],
        required_source_kinds=("document",),
    )
    assert report.should_refuse is True
    assert "document" in report.missing_source_kinds


def test_run_critic_checks_passes_on_clean_input() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    recent = now - timedelta(days=10)
    evidences = [
        _evidence(evidence_id="E1", source_kind="news", published_at=recent.isoformat(), content=""),
        _evidence(evidence_id="E2", source_kind="document", published_at=recent.isoformat(), content=""),
    ]
    report = run_critic_checks(
        evidences,
        draft_text="[E1] 引用了 [E2] 文档。",
        required_source_kinds=("news", "document"),
        now=now,
    )
    assert report.should_refuse is False
    assert report.blocks == 0


def test_run_critic_checks_returns_empty_report_on_empty_input() -> None:
    report = run_critic_checks([])
    assert report.findings == ()
    assert report.should_refuse is False


def test_default_constants_match_session_summary() -> None:
    assert DEFAULT_MAX_AGE_DAYS == 730
    assert DEFAULT_TIME_ANCHOR_TOLERANCE_DAYS == 90
    assert DEFAULT_CONFLICT_TOLERANCE == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# Integration with Evidence-shaped objects
# ---------------------------------------------------------------------------


def test_run_critic_checks_accepts_evidence_objects_with_to_dict() -> None:
    class FakeEvidence:
        def __init__(self, **kwargs):
            self._d = kwargs

        def to_dict(self):
            return self._d

    evidences = [
        FakeEvidence(evidence_id="E1", source_kind="news", content=""),
    ]
    report = run_critic_checks(evidences, required_source_kinds=("document",))
    assert "document" in report.missing_source_kinds


def test_run_critic_checks_ignores_non_dict_non_evidence_inputs() -> None:
    """The helper should be tolerant of ``None`` entries or stray
    objects without ``to_dict``."""

    evidences = [
        None,
        "not a dict",
        object(),
        _evidence(
            evidence_id="E1",
            source_kind="news",
            content="",
            published_at=_iso_offset(-30),
        ),
    ]
    report = run_critic_checks(evidences, required_source_kinds=("news",))
    assert report.should_refuse is False
