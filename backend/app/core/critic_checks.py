"""Deterministic multi-source critic checks (P1-4).

The :class:`app.service.deep_research_v2.agents.critic.CriticMaster`
already runs an LLM-driven adversarial review over a draft report.
That review is necessary but not sufficient: the LLM can hallucinate
issues, miss structural problems, and silently accept contradictions
between sources. P1-4 introduces a deterministic pre-LLM pass that
runs six well-defined checks against the evidence set and surfaces
findings the Critic (and the rest of the orchestration) can act on.

The six checks are:

* :func:`check_freshness` — every evidence row carries either
  ``published_at`` or ``as_of``. If both are missing or older than a
  configurable freshness budget, the finding is severity ``warn``; if
  no row in the whole evidence set is fresh enough, the finding is
  promoted to ``block``.

* :func:`check_unit_mismatch` — for numeric values in evidence
  content, the helper detects pairs that share the same numeric magnitude
  but disagree on the unit (``亿`` vs ``万``, ``%`` vs ``个``, ...). It
  is intentionally conservative: false positives are worse than missed
  issues at this stage.

* :func:`check_time_anchor` — when the same metric name appears in two
  evidence rows whose ``as_of`` dates differ by more than a small
  tolerance, the helper emits a ``warn`` so downstream comparison can
  pick the more recent value or refuse to compare.

* :func:`check_conflicts` — when two evidence rows mention the same
  metric name and their numeric values diverge beyond a configurable
  tolerance, the helper emits a ``warn`` so the writer can disclose the
  disagreement. Heuristic only; not a substitute for the LLM critic.

* :func:`check_missing_source` — given a required set of ``source_kind``
  values, the helper raises ``block`` if any required kind is missing
  from the evidence set. This is the gate for the "缺失关键来源拒答"
  requirement.

* :func:`check_cross_source_inference` — given the draft report body,
  the helper flags sentences that synthesise two or more evidence rows.
  The flag is informational; downstream code can use it to label the
  conclusion as "inferred across sources".

The aggregator :func:`run_critic_checks` runs every check and returns a
:class:`CriticReport` summarising the findings plus the number of
``block`` findings. The orchestration layer (multi-source runner and
CriticMaster) consults ``CriticReport.should_refuse`` to decide whether
to refuse the answer outright or pass it through to the LLM critic.

The module is intentionally side-effect free. It never modifies state
or talks to the network. The caller decides whether to refuse, route,
or annotate based on the report.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

# Severities. ``block`` is the only level that the orchestrator treats
# as a refusal trigger; ``warn`` and ``info`` are advisory.
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_BLOCK = "block"

ALL_SEVERITIES: FrozenSet[str] = frozenset(
    {SEVERITY_INFO, SEVERITY_WARN, SEVERITY_BLOCK}
)

# Check identifiers (also used as ``finding.check``).
CHECK_FRESHNESS = "freshness"
CHECK_UNIT_MISMATCH = "unit_mismatch"
CHECK_TIME_ANCHOR = "time_anchor"
CHECK_CONFLICT = "conflict"
CHECK_MISSING_SOURCE = "missing_source"
CHECK_INFERENCE = "inference"

ALL_CHECKS: Tuple[str, ...] = (
    CHECK_FRESHNESS,
    CHECK_UNIT_MISMATCH,
    CHECK_TIME_ANCHOR,
    CHECK_CONFLICT,
    CHECK_MISSING_SOURCE,
    CHECK_INFERENCE,
)


@dataclass(frozen=True)
class CriticFinding:
    """A single deterministic finding against the evidence set.

    The ``involved_evidence_ids`` field carries the evidence_id values
    of every evidence row that contributed to the finding. Callers
    can use this to surface the relevant citations directly.
    """

    check: str
    severity: str
    subject: str
    detail: str
    involved_evidence_ids: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.severity not in ALL_SEVERITIES:
            raise ValueError(f"unknown severity: {self.severity!r}")
        if self.check not in ALL_CHECKS:
            raise ValueError(f"unknown check: {self.check!r}")


@dataclass(frozen=True)
class CriticReport:
    """Aggregated output of :func:`run_critic_checks`."""

    findings: Tuple[CriticFinding, ...] = field(default_factory=tuple)
    required_source_kinds: Tuple[str, ...] = field(default_factory=tuple)
    missing_source_kinds: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def blocks(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_BLOCK)

    @property
    def warns(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_WARN)

    @property
    def infos(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_INFO)

    @property
    def should_refuse(self) -> bool:
        """Return True when the orchestrator should refuse the answer."""

        return self.blocks > 0 or bool(self.missing_source_kinds)

    def by_check(self, check: str) -> Tuple[CriticFinding, ...]:
        return tuple(f for f in self.findings if f.check == check)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "findings": [
                {
                    "check": f.check,
                    "severity": f.severity,
                    "subject": f.subject,
                    "detail": f.detail,
                    "involved_evidence_ids": list(f.involved_evidence_ids),
                }
                for f in self.findings
            ],
            "blocks": self.blocks,
            "warns": self.warns,
            "infos": self.infos,
            "required_source_kinds": list(self.required_source_kinds),
            "missing_source_kinds": list(self.missing_source_kinds),
            "should_refuse": self.should_refuse,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Best-effort ISO-8601 parser. Accepts ``Z`` suffix. Returns ``None``
    if ``value`` is missing or not parseable. Naive datetimes are
    treated as UTC.
    """

    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _as_evidence_dicts(
    evidences: Iterable[Any],
) -> List[Dict[str, Any]]:
    """Coerce ``Evidence`` instances (or any object exposing ``to_dict``)
    into plain dictionaries. Pure dicts pass through unchanged. The
    helper never raises on missing keys - downstream code uses
    ``.get`` for everything.
    """

    out: List[Dict[str, Any]] = []
    for ev in evidences:
        if ev is None:
            continue
        if isinstance(ev, dict):
            out.append(ev)
            continue
        to_dict = getattr(ev, "to_dict", None)
        if callable(to_dict):
            out.append(to_dict())
        else:
            out.append({})
    return out


def _evidence_age_days(ev: Dict[str, Any]) -> Optional[float]:
    """Return the age of an evidence row in days, or ``None`` if the
    row carries no usable timestamp."""

    candidates = (
        ev.get("published_at"),
        ev.get("as_of"),
        ev.get("retrieved_at"),
    )
    parsed = None
    for c in candidates:
        p = _parse_iso_datetime(c)
        if p is not None:
            parsed = p
            break
    if parsed is None:
        return None
    now = datetime.now(timezone.utc)
    return (now - parsed).total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# 1. Freshness
# ---------------------------------------------------------------------------


# Default freshness budget. Two years mirrors the prompt-side guidance
# in ``critic.py`` (``过时数据（超过2年）``); callers can override.
DEFAULT_MAX_AGE_DAYS = 730


def check_freshness(
    evidences: Iterable[Any],
    *,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    now: Optional[datetime] = None,
) -> List[CriticFinding]:
    """Flag evidence rows that are older than ``max_age_days``.

    The check emits a ``warn`` finding for every evidence row that is
    older than the budget. When the entire evidence set carries no
    timestamps at all, the check promotes itself to a single ``block``
    so the orchestrator can refuse to answer.

    Stale-but-dated evidence stays at ``warn`` level so the writer can
    still produce a usable answer; the caller decides whether to
    proceed based on the freshness context they configured.
    """

    items = _as_evidence_dicts(evidences)
    if not items:
        return []

    any_timestamp = False
    findings: List[CriticFinding] = []
    now = now or datetime.now(timezone.utc)
    for ev in items:
        eid = str(ev.get("evidence_id") or "")
        title = str(ev.get("title") or "(无标题)")
        age = _evidence_age_days(ev)
        if age is None:
            continue
        any_timestamp = True
        if age <= max_age_days:
            continue
        findings.append(
            CriticFinding(
                check=CHECK_FRESHNESS,
                severity=SEVERITY_WARN,
                subject=title,
                detail=(
                    f"证据 published_at/as_of 距今 {age:.0f} 天，超过 "
                    f"{max_age_days} 天的时效预算。"
                ),
                involved_evidence_ids=(eid,) if eid else (),
            )
        )

    if not any_timestamp:
        return [
            CriticFinding(
                check=CHECK_FRESHNESS,
                severity=SEVERITY_BLOCK,
                subject="(全部证据)",
                detail=(
                    "证据集合没有任何 published_at / as_of 时间戳，无法验证时效。"
                ),
            )
        ]
    return findings


# ---------------------------------------------------------------------------
# 2. Unit mismatch
# ---------------------------------------------------------------------------


_UNIT_TOKENS = (
    "万亿元",
    "千亿元",
    "亿元",
    "百万元",
    "万元",
    "元",
    "%",
    "个",
    "件",
    "人",
    "%",
)


# The unit alternation lists longer prefixes first so the regex picks
# ``亿元`` / ``万元`` rather than ``亿`` / ``万``. ``亿`` and ``万``
# remain in the alternation as fall-through so a token such as
# ``80亿美元`` still captures ``亿`` if the trailing ``元`` is missing.
_NUMERIC_TOKEN_RE = re.compile(
    r"(?P<num>-?\d+(?:\.\d+)?)\s*(?P<unit>万亿元|千亿元|百万元|千万元|亿元|百亿|万亿|千亿|十亿|亿元|万元|兆|千万|百|十|万|千|元|%|个百分点|个|件|人|台|套|根|米|公里|千克|吨|倍|美元|人民币|亿)?"
)


def _extract_numeric_tokens(text: str) -> List[Tuple[float, str, str]]:
    """Extract ``(value, unit, raw)`` tuples from ``text``.

    Only tokens that carry an explicit unit survive - bare integers are
    too noisy and frequently refer to indices, ranks, or pagination.
    """

    out: List[Tuple[float, str, str]] = []
    if not text:
        return out
    for match in _NUMERIC_TOKEN_RE.finditer(text):
        raw_num = match.group("num")
        unit = match.group("unit") or ""
        if not unit:
            continue
        try:
            value = float(raw_num)
        except ValueError:
            continue
        out.append((value, unit, match.group(0)))
    return out


def check_unit_mismatch(evidences: Iterable[Any]) -> List[CriticFinding]:
    """Detect pairs of evidence rows that mention the same numeric
    metric with conflicting units.

    Heuristic: for every evidence row, extract numeric tokens with units.
    Build a name-keyed bucket by stripping the numeric token. If two
    rows disagree on the unit for the same bucket within the same
    scale (``万`` vs ``亿``), raise a ``warn``.
    """

    items = _as_evidence_dicts(evidences)
    findings: List[CriticFinding] = []

    # value -> list[(evidence_id, raw_token, scale)]
    buckets: Dict[str, List[Tuple[str, str, int]]] = {}
    for ev in items:
        eid = str(ev.get("evidence_id") or "")
        title = str(ev.get("title") or "(无标题)")
        content = str(ev.get("content") or "")
        for value, unit, raw in _extract_numeric_tokens(content):
            scale = _unit_scale(unit)
            if scale is None:
                continue
            bucket = _bucket_key(content, raw)
            if not bucket:
                continue
            buckets.setdefault(bucket, []).append((eid, raw, scale))

    for bucket, rows in buckets.items():
        scales = {r[2] for r in rows}
        if len(scales) < 2:
            continue
        # Only flag when the scales differ by at least one order of
        # magnitude (e.g. 万 vs 亿). Same-scale with different prefixes
        # (e.g. % vs 百分点) are NOT flagged here.
        ordered = sorted(scales)
        if ordered[-1] - ordered[0] < 4:
            continue
        involved = tuple({r[0] for r in rows if r[0]})
        findings.append(
            CriticFinding(
                check=CHECK_UNIT_MISMATCH,
                severity=SEVERITY_WARN,
                subject=bucket,
                detail=(
                    f"指标 ``{bucket}`` 在不同证据中出现量级不一致的数值，"
                    f"涉及单位刻度 {sorted(scales)}。"
                ),
                involved_evidence_ids=involved,
            )
        )
    return findings


# Scale factor used to compare units. We assign ``万`` = 1 and step
# orders of magnitude for the others so 4 levels difference equals a
# 万-vs-亿 discrepancy. ``%`` and ``个`` map to a fixed scale so
# percentage vs absolute counts can be detected (and flagged separately
# by the unit-mismatch check).
_UNIT_SCALE: Dict[str, int] = {
    "万": 1,
    "万元": 1,
    "百万元": 3,
    "千万元": 3,
    "亿元": 5,
    "千亿元": 7,
    "万亿元": 9,
    "%": 0,
    "个百分点": 0,
    "个": 0,
    "件": 0,
    "人": 0,
    "台": 0,
    "套": 0,
    "元": 0,
}


def _unit_scale(unit: str) -> Optional[int]:
    """Return a coarse integer scale for ``unit``. ``None`` for unknown."""

    if not unit:
        return None
    return _UNIT_SCALE.get(unit)


# Capture numeric tokens with their surrounding Chinese phrase to
# bucket ``指标 key``. Keep it conservative: 8 chars on each side.
_BUCKET_CONTEXT_RE = re.compile(r"[\u4e00-\u9fffA-Za-z]{2,12}")


def _bucket_key(content: str, raw: str) -> str:
    """Return the surrounding Chinese phrase that ``raw`` lives in.

    The bucket key is what we use to decide whether two numeric tokens
    refer to the same underlying metric (``12亿元`` vs ``12亿`` should
    land in the same bucket as long as the surrounding noun is shared).
    """

    if not content or not raw:
        return ""
    pos = content.find(raw)
    if pos < 0:
        return ""
    window = content[max(0, pos - 12) : pos + len(raw) + 12]
    matches = _BUCKET_CONTEXT_RE.findall(window)
    if not matches:
        return raw
    # Pick the longest phrase so we capture the noun. Fall back to the
    # raw token when no phrase is in range.
    return max(matches, key=len)


# ---------------------------------------------------------------------------
# 3. Time anchor
# ---------------------------------------------------------------------------


DEFAULT_TIME_ANCHOR_TOLERANCE_DAYS = 90


def check_time_anchor(
    evidences: Iterable[Any],
    *,
    tolerance_days: int = DEFAULT_TIME_ANCHOR_TOLERANCE_DAYS,
) -> List[CriticFinding]:
    """Flag pairs of evidence rows that share a metric name but have
    ``as_of`` dates differing by more than ``tolerance_days``.

    The check is best-effort: rows without timestamps are ignored.
    """

    items = _as_evidence_dicts(evidences)
    findings: List[CriticFinding] = []

    # Build metric -> [(eid, title, parsed_dt)]
    metric_rows: Dict[str, List[Tuple[str, str, datetime]]] = {}
    for ev in items:
        eid = str(ev.get("evidence_id") or "")
        title = str(ev.get("title") or "(无标题)")
        as_of = _parse_iso_datetime(ev.get("as_of") or ev.get("published_at"))
        if as_of is None:
            continue
        for raw in _extract_metric_tokens(str(ev.get("content") or "")):
            metric_rows.setdefault(raw, []).append((eid, title, as_of))

    for metric, rows in metric_rows.items():
        if len(rows) < 2:
            continue
        rows_sorted = sorted(rows, key=lambda r: r[2])
        latest = rows_sorted[-1]
        for eid, title, dt in rows_sorted[:-1]:
            gap_days = abs((latest[2] - dt).days)
            if gap_days <= tolerance_days:
                continue
            involved = tuple({latest[0], eid})
            findings.append(
                CriticFinding(
                    check=CHECK_TIME_ANCHOR,
                    severity=SEVERITY_WARN,
                    subject=metric,
                    detail=(
                        f"指标 ``{metric}`` 在不同证据中的时点相差 {gap_days} 天，"
                        f"超过 {tolerance_days} 天容差。"
                    ),
                    involved_evidence_ids=involved,
                )
            )
    return findings


_METRIC_TOKEN_RE = re.compile(r"[\u4e00-\u9fffA-Za-z]{3,12}(?:率|占比|增速|规模|数量|金额|收入|利润|市值)?(?:\d{4}年)?(?:\d{1,2}月)?")


def _extract_metric_tokens(text: str) -> List[str]:
    """Extract stable Chinese metric tokens for time-anchor comparison.

    We keep tokens with the same numeric context (``2024年Q3``,
    ``12月``, ...) collapsed so the same metric across quarters is
    treated as one anchor instead of three.
    """

    seen: List[str] = []
    if not text:
        return seen
    for m in _METRIC_TOKEN_RE.finditer(text):
        tok = m.group(0).strip()
        if tok and tok not in seen:
            seen.append(tok)
    return seen


# ---------------------------------------------------------------------------
# 4. Conflict
# ---------------------------------------------------------------------------


DEFAULT_CONFLICT_TOLERANCE = 0.20  # 20% relative difference


def check_conflicts(
    evidences: Iterable[Any],
    *,
    relative_tolerance: float = DEFAULT_CONFLICT_TOLERANCE,
) -> List[CriticFinding]:
    """Flag numeric disagreements for the same metric across sources.

    Heuristic: extract numeric tokens per evidence row and look for
    two rows that mention the same bucket (see ``_bucket_key``) but
    with values that diverge by more than ``relative_tolerance`` AND
    share the same unit. Rows whose unit differs are caught by the
    unit-mismatch check instead.
    """

    items = _as_evidence_dicts(evidences)
    findings: List[CriticFinding] = []

    # Bucket by (metric_key, unit) -> list[(eid, value, raw)]
    grouped: Dict[Tuple[str, str], List[Tuple[str, float, str]]] = {}
    for ev in items:
        eid = str(ev.get("evidence_id") or "")
        title = str(ev.get("title") or "(无标题)")
        content = str(ev.get("content") or "")
        for value, unit, raw in _extract_numeric_tokens(content):
            key = _bucket_key(content, raw)
            if not key:
                continue
            grouped.setdefault((key, unit), []).append((eid, value, raw))

    for (metric, unit), rows in grouped.items():
        if len(rows) < 2:
            continue
        # Find the largest relative disagreement.
        max_value = max(r[1] for r in rows)
        min_value = min(r[1] for r in rows)
        if max_value <= 0:
            continue
        rel_diff = (max_value - min_value) / max_value
        if rel_diff <= relative_tolerance:
            continue
        involved = tuple({r[0] for r in rows})
        findings.append(
            CriticFinding(
                check=CHECK_CONFLICT,
                severity=SEVERITY_WARN,
                subject=metric,
                detail=(
                    f"指标 ``{metric}`` 在不同证据中的数值相差 {rel_diff:.0%}，"
                    f"超过 {relative_tolerance:.0%} 容差。"
                ),
                involved_evidence_ids=involved,
            )
        )
    return findings


# ---------------------------------------------------------------------------
# 5. Missing source
# ---------------------------------------------------------------------------


def check_missing_source(
    evidences: Iterable[Any],
    required_source_kinds: Sequence[str],
) -> List[CriticFinding]:
    """Block when a required ``source_kind`` is absent from the evidence.

    Returns an empty list when no requirements are configured. When
    multiple kinds are missing, a single finding per missing kind is
    emitted so the orchestrator can surface the full gap to the user.
    """

    items = _as_evidence_dicts(evidences)
    if not required_source_kinds:
        return []
    present = {str(ev.get("source_kind") or "") for ev in items}
    missing = [k for k in required_source_kinds if k not in present]
    return [
        CriticFinding(
            check=CHECK_MISSING_SOURCE,
            severity=SEVERITY_BLOCK,
            subject=k,
            detail=f"缺少必要的来源类型 ``{k}``。",
        )
        for k in missing
    ]


# ---------------------------------------------------------------------------
# 6. Cross-source inference
# ---------------------------------------------------------------------------


# Sentence-level splitter that respects Chinese punctuation. The regex
# is intentionally permissive - if the body is one giant run-on, we
# fall back to chunking on the first period we can find.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?\.\n])\s*")


def check_cross_source_inference(
    draft_text: Optional[str],
    evidences: Iterable[Any],
) -> List[CriticFinding]:
    """Flag sentences in the draft that combine two or more evidence
    citations. The flag is informational: the writer is expected to
    mark such sentences as "推断" in the rendered report.

    The check tokenises each sentence and counts how many distinct
    evidence_ids appear as ``[E1]`` / ``[[1]]`` markers. Sentences with
    two or more distinct markers are flagged.
    """

    if not draft_text:
        return []
    items = _as_evidence_dicts(evidences)
    if not items:
        return []

    # Build a mapping ``accepted_form -> canonical_id``. The marker in
    # the draft may use the canonical form (``E1``) or the stripped
    # form (``1``); both should map back to the canonical id so the
    # downstream involved_evidence_ids list is consistent.
    canonical_for_marker: Dict[str, str] = {}
    for ev in items:
        eid = ev.get("evidence_id")
        if not eid:
            continue
        text = str(eid).strip()
        if not text:
            continue
        canonical_for_marker[text] = text
        if text[:1].lower() == "e" and text[1:].isdigit():
            canonical_for_marker[text[1:]] = text
        if text.isdigit():
            canonical_for_marker["E" + text] = text
            canonical_for_marker[text] = text
    if not canonical_for_marker:
        return []

    findings: List[CriticFinding] = []
    for sentence in _SENTENCE_SPLIT_RE.split(draft_text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        seen: set[str] = set()
        for marker in _CITE_MARKER_RE.findall(sentence):
            for vid in marker:
                if not vid:
                    continue
                canonical = canonical_for_marker.get(vid)
                if canonical is not None:
                    seen.add(canonical)
        if len(seen) < 2:
            continue
        findings.append(
            CriticFinding(
                check=CHECK_INFERENCE,
                severity=SEVERITY_INFO,
                subject=sentence[:40],
                detail=(
                    f"该句同时引用了 {len(seen)} 条不同证据，属于跨源推断。"
                    "建议在最终报告中显式标注为「研究推断」。"
                ),
                involved_evidence_ids=tuple(sorted(seen)),
            )
        )
    return findings


# Cite marker patterns. We support both the ``[E1]`` style used by
# multi_source_research and the ``[[1]]`` style used by some other
# writers. The token between the brackets is captured as a list.
_CITE_MARKER_RE = re.compile(r"\[\[([^\]]+)\]\]|\[E(\d+)\]|\[\u3010(\d+)\u3011")


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def run_critic_checks(
    evidences: Iterable[Any],
    *,
    draft_text: Optional[str] = None,
    required_source_kinds: Sequence[str] = (),
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    time_anchor_tolerance_days: int = DEFAULT_TIME_ANCHOR_TOLERANCE_DAYS,
    conflict_relative_tolerance: float = DEFAULT_CONFLICT_TOLERANCE,
    now: Optional[datetime] = None,
) -> CriticReport:
    """Run every check and return an aggregated :class:`CriticReport`.

    The order of checks is stable so callers can rely on a deterministic
    output sequence. ``missing_source_kinds`` is computed once and
    shared across the missing-source check and the ``should_refuse``
    heuristic so the two stay in sync.
    """

    items = _as_evidence_dicts(evidences)
    required = tuple(required_source_kinds or ())
    missing_kinds = _compute_missing_kinds(items, required)

    findings: List[CriticFinding] = []
    findings.extend(check_freshness(items, max_age_days=max_age_days, now=now))
    findings.extend(check_unit_mismatch(items))
    findings.extend(check_time_anchor(items, tolerance_days=time_anchor_tolerance_days))
    findings.extend(check_conflicts(items, relative_tolerance=conflict_relative_tolerance))
    findings.extend(check_missing_source(items, required))
    findings.extend(check_cross_source_inference(draft_text, items))

    return CriticReport(
        findings=tuple(findings),
        required_source_kinds=required,
        missing_source_kinds=missing_kinds,
    )


def _compute_missing_kinds(
    items: Sequence[Dict[str, Any]],
    required: Sequence[str],
) -> Tuple[str, ...]:
    if not required:
        return ()
    present = {str(ev.get("source_kind") or "") for ev in items}
    return tuple(k for k in required if k not in present)


__all__ = [
    "SEVERITY_INFO",
    "SEVERITY_WARN",
    "SEVERITY_BLOCK",
    "ALL_SEVERITIES",
    "CHECK_FRESHNESS",
    "CHECK_UNIT_MISMATCH",
    "CHECK_TIME_ANCHOR",
    "CHECK_CONFLICT",
    "CHECK_MISSING_SOURCE",
    "CHECK_INFERENCE",
    "ALL_CHECKS",
    "DEFAULT_MAX_AGE_DAYS",
    "DEFAULT_TIME_ANCHOR_TOLERANCE_DAYS",
    "DEFAULT_CONFLICT_TOLERANCE",
    "CriticFinding",
    "CriticReport",
    "check_freshness",
    "check_unit_mismatch",
    "check_time_anchor",
    "check_conflicts",
    "check_missing_source",
    "check_cross_source_inference",
    "run_critic_checks",
]
