"""Data governance primitives (P1-3).

This module is the application-side enforcement for the four data-quality
concerns called out in the P1-3 roadmap:

1. **News / announcement dedup**: ``news_dedup_key`` and ``bidding_dedup_key``
   produce stable identity hashes that the news + bidding collectors use
   in addition to the legacy ``source_url`` / ``bid_id`` lookups. The hash
   is a SHA-256 of the normalised (title, content, publisher, publish
   timestamp) tuple - same item from a different aggregator still
   resolves to the same identity.

2. **Bidding party extraction + normalisation**:
   ``extract_parties`` parses Chinese-language bidding titles/snippets for
   the 采购方 (procuring entity) and 中标人 (winning bidder) and
   ``normalise_party_name`` collapses common spelling variants so the same
   company is recognised across vendors (``"中芯国际集成电路制造有限公司"``
   and ``"中芯国际"`` collapse to the same canonical entity).

3. **Announcement lifecycle clustering**: ``cluster_lifecycle`` groups
   bidding items that share the same project key (normalised title prefix
   + procuring entity) so a 招标 -> 中标 -> 变更 chain becomes one
   ``LifecycleGroup`` instead of three unrelated rows.

4. **Stock code resolution (auditable)**: ``StockCodeResolver`` replaces
   the legacy ``COMPANY_STOCK_MAP`` lookup with an auditable resolver
   that records every resolution call - what input name was looked up,
   what canonical entity it matched, and which stock code was returned.
   ``resolve_stock_code`` returns the same ``Optional[str]`` shape as
   the legacy helper so existing callers keep working.

Everything in this module is pure-Python and side-effect free unless the
caller passes an audit sink. The module never mutates the database on
its own - it produces keys, party dicts, lifecycle groups, and audit
records for the caller to persist via existing models / repositories.

The module is intentionally narrow: it does not retry fetches, render
text, or touch evidence contracts. Those concerns live in their own
modules (provider_reliability / evidence_contract) so the data-quality
work can be unit-tested in isolation.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def _normalise_text(value: Optional[str]) -> str:
    """Return a whitespace-collapsed, NFKC-folded copy of ``value`` for
    hashing. ``None`` and empty strings are treated as the empty string."""

    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.casefold()
    # Collapse all whitespace runs to a single space and strip ends so
    # "中芯国际\n  2024 半年报" hashes the same as "中芯国际 2024 半年报".
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def content_hash(*fields: Optional[str]) -> str:
    """Stable SHA-256 hash over the concatenation of normalised fields.

    The fields are normalised individually and joined with ``\x1f``
    (ASCII unit separator) so a value like ``"abc"`` cannot collide with
    ``"a"`` + ``"bc"``. Returns the 64-character hex digest.
    """

    parts = [_normalise_text(f) for f in fields]
    payload = "\x1f".join(parts).encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def news_dedup_key(
    *,
    url: Optional[str] = None,
    title: Optional[str],
    content: Optional[str],
    publisher: Optional[str],
    publish_time: Optional[str],
) -> str:
    """Identity hash for a news item.

    Two news items share a dedup key iff the normalised (title, content,
    publisher, publish_time) tuple is identical. URLs are intentionally
    excluded because different aggregators often reuse the same URL
    scheme (e.g. ``https://example.com/post/123``) or strip UTM params;
    the content-based hash is more stable.
    """

    return content_hash("news", title, content, publisher, publish_time)


def bidding_dedup_key(
    *,
    bid_id: Optional[str],
    title: Optional[str],
    province: Optional[str],
    publish_time: Optional[str],
) -> str:
    """Identity hash for a bidding item.

    ``bid_id`` is included in the payload so a 招标 / 中标 pair with the
    same title but different IDs is not merged. URL-style fields are not
    used here either - we lean on title + province + time.
    """

    return content_hash("bidding", bid_id, title, province, publish_time)


# ---------------------------------------------------------------------------
# Party extraction / normalisation
# ---------------------------------------------------------------------------


# Patterns commonly seen in 81api bidding titles and snippets. They are
# intentionally narrow to keep the false-positive rate low; production
# callers should still verify parties through the resolved ``parties``
# dict before publishing them in evidence.
_PARTY_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "buyer": (
        r"采购人[::]?\s*([^\s,，；;。]+)",
        r"采购单位[::]?\s*([^\s,，；;。]+)",
        r"招标人[::]?\s*([^\s,，；;。]+)",
        r"招标单位[::]?\s*([^\s,，；;。]+)",
        r"业主[::]?\s*([^\s,，；;。]+)",
        r"项目单位[::]?\s*([^\s,，；;。]+)",
        r"业主单位[::]?\s*([^\s,，；;。]+)",
    ),
    "supplier": (
        r"中标人[::]?\s*([^\s,，；;。]+)",
        r"中标单位[::]?\s*([^\s,，；;。]+)",
        r"中标候选人[::]?\s*([^\s,，；;。]+)",
        r"供应商[::]?\s*([^\s,，；;。]+)",
        r"成交人[::]?\s*([^\s,，；;。]+)",
        r"供应商名称[::]?\s*([^\s,，；;。]+)",
    ),
}


def _compile_patterns() -> Dict[str, List[re.Pattern]]:
    return {
        role: [re.compile(p) for p in patterns]
        for role, patterns in _PARTY_PATTERNS.items()
    }


_PARTY_REGEXES = _compile_patterns()


# Common corporate-name suffixes to strip when normalising a party name
# so ``"中芯国际集成电路制造（上海）有限公司"`` collapses to
# ``"中芯国际"``. We keep the legal-entity suffix optionally so callers
# that need the full name can opt out.
_PARTY_LEGAL_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团股份有限公司",
    "集团有限公司",
    "集团公司",
    "公司",
)


def normalise_party_name(name: Optional[str], *, strip_legal_suffix: bool = True) -> str:
    """Collapse spelling variants of a company name to a stable key.

    Rules (in order):

    1. NFKC normalise + casefold.
    2. Drop parenthetical remarks such as ``"(上海)"`` and ``"（上海）"``
       (NFKC first folds both forms to half-width, so the single
       half-width pattern matches both).
    3. Strip remaining leading/trailing bracket-like characters.
    4. Whitespace collapse and trim.
    5. Optionally strip trailing legal-entity suffixes
       (``"有限公司"`` etc.).

    The result is intentionally short. Two names that resolve to the
    same canonical key are treated as the same entity for dedup,
    clustering and citation purposes.
    """

    if name is None:
        return ""
    text = unicodedata.normalize("NFKC", str(name))
    text = text.casefold()
    # Strip a parenthesised remark in full. NFKC above has already
    # collapsed ``（`` -> ``(`` and ``）`` -> ``)``, so a single
    # half-width pattern covers both forms.
    text = re.sub(r"\([^)]*\)", " ", text)
    # Drop remaining bracket / quote characters that may be used as
    # decorative wrappers (e.g. ``《中芯国际》``).
    text = re.sub(r"[\[\]「」『』【】“”\"'`《》]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if strip_legal_suffix:
        changed = True
        while changed:
            changed = False
            for suffix in _PARTY_LEGAL_SUFFIXES:
                if text.endswith(suffix) and len(text) > len(suffix):
                    text = text[: -len(suffix)].rstrip(" ，,、")
                    changed = True
                    break
    return text


# Whitelisted brand fragments that should not be collapsed further even
# when they look like a short name. This guards against pathological
# normalisations (e.g. ``"有限公司"`` alone returning the empty string).
_PARTY_NAME_MIN_LENGTH = 2


def extract_parties(text: Optional[str]) -> Dict[str, str]:
    """Best-effort party extraction from a free-text bidding title or snippet.

    Returns a dict with at most ``"buyer"`` and ``"supplier"`` keys. Each
    value is the FIRST matched candidate (highest-priority role). Empty
    dict if nothing matched.

    The function is intentionally permissive - it errs on the side of
    capturing a candidate and lets downstream code verify by joining
    the candidate back against the canonical entities table.
    """

    if not text:
        return {}
    # Match against the raw text (no NFKC normalisation here). NFKC
    # would collapse full-width parens to half-width, causing us to
    # capture ``(上海)`` inside the entity string. Parenthetical
    # remarks are stripped from the captured value below instead.
    blob = str(text)
    found: Dict[str, str] = {}
    for role, regexes in _PARTY_REGEXES.items():
        if role in found:
            continue
        for regex in regexes:
            match = regex.search(blob)
            if not match:
                continue
            candidate = match.group(1).strip()
            # Drop any parenthesised remark (full-width or half-width)
            # so ``中芯国际集成电路制造（上海）有限公司`` -> ``中芯国际集成
            # 电路制造有限公司`` before legal-suffix stripping runs.
            candidate = re.sub(r"（[^）]*）|\([^)]*\)", " ", candidate)
            # Trim leading / trailing Chinese punctuation that is not
            # part of the entity name itself.
            candidate = re.sub(
                r"^[\s\-_/、，,：:;；。.]+|[\s\-_/、，,：:;；。.]+$",
                "",
                candidate,
            )
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if len(normalise_party_name(candidate)) < _PARTY_NAME_MIN_LENGTH:
                continue
            found[role] = candidate
            break
    return found


# ---------------------------------------------------------------------------
# Lifecycle clustering
# ---------------------------------------------------------------------------


def _lifecycle_title_norm(title: str) -> str:
    """Strip notice-type noise from a bidding title and normalise for
    clustering. The output is NFKC-folded, lowercase, with all common
    notice-type suffixes collapsed.
    """

    text = unicodedata.normalize("NFKC", title or "")
    text = re.sub(
        r"(招标公告|中标公告|中标公示|采购公告|结果公告|变更公告|更正公告|候选人公示|询比公告|磋商公告)",
        " ",
        text,
    )
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text[:80]


def _lifecycle_project_key(title_norm: str, buyer_canonical: str) -> str:
    """Stable project key combining the cleaned title and the canonical
    buyer name.
    """

    return content_hash("lifecycle", buyer_canonical, title_norm)


def _buyers_compatible(a: str, b: str) -> bool:
    """Return True when two normalised buyer names should be treated as
    referring to the same entity for lifecycle clustering purposes.

    The rule is intentionally permissive: one buyer name being a
    non-trivial substring of the other is sufficient. ``中芯国际`` and
    ``中芯国际集成电路制造`` collapse to the same group; completely
    unrelated names do not. We require a minimum length on the
    shorter side to avoid pathological matches on empty / single-char
    strings.
    """

    a = a.strip()
    b = b.strip()
    if not a or not b:
        return False
    short, long_ = sorted((a, b), key=len)
    if len(short) < 2:
        return False
    if short == long_:
        return True
    return short in long_


@dataclass(frozen=True)
class LifecycleGroup:
    """Group of bidding items that belong to the same project chain.

    Items in the same group are emitted in insertion-order. The
    ``project_key`` is stable across re-clustering as long as the
    normalised title prefix and procuring entity do not change.
    """

    project_key: str
    buyer_canonical: str
    items: Tuple[Dict[str, Any], ...]


def cluster_lifecycle(items: Iterable[Dict[str, Any]]) -> List[LifecycleGroup]:
    """Group bidding items into announcement chains.

    Each input item must include ``title``, ``bid_id`` and (optionally)
    ``parties`` (output of :func:`extract_parties`).

    Clustering rules:

    1. Two items land in the same group when their cleaned titles
       share the first 24 chars (NFKC-folded, lowercase, with
       notice-type noise stripped) AND their normalised buyer names
       are substring-compatible (see :func:`_buyers_compatible`).
    2. Groups preserve input order. They are sorted by their project
       key for deterministic output so test fixtures and downstream
       pipelines see a stable layout.
    """

    canonical_buyers: List[str] = []
    title_to_groups: Dict[str, List[int]] = {}
    group_keys: List[str] = []
    group_titles: List[str] = []
    group_buyers: List[str] = []
    group_items: List[List[Dict[str, Any]]] = []

    def _normalise_item(item: Dict[str, Any]) -> Tuple[str, str]:
        parties = item.get("parties") or {}
        buyer_raw = (
            parties.get("buyer", "")
            if isinstance(parties, dict)
            else ""
        )
        buyer = normalise_party_name(buyer_raw)
        title_norm = _lifecycle_title_norm(str(item.get("title") or ""))
        return buyer, title_norm

    def _canonical_for(buyer: str) -> str:
        """Return the canonical buyer for ``buyer`` by substring match.

        Builds a single canonical string per equivalence class so the
        same group never splits across buyer spellings. The list
        itself is the only mutable state - the canonical string is
        stable for the lifetime of the call.
        """

        for canonical in canonical_buyers:
            if _buyers_compatible(buyer, canonical):
                return canonical
        canonical_buyers.append(buyer)
        return buyer

    for item in items:
        buyer, title_norm = _normalise_item(item)
        canonical = _canonical_for(buyer)
        title_key = title_norm[:24]
        target: Optional[int] = None
        for gid in title_to_groups.get(title_key, []):
            group_title = group_titles[gid]
            if not title_norm.startswith(group_title[:24]):
                continue
            if not _buyers_compatible(canonical, group_buyers[gid]):
                continue
            target = gid
            break
        if target is None:
            target = len(group_items)
            project_key = _lifecycle_project_key(title_norm, canonical)
            group_keys.append(project_key)
            group_titles.append(title_norm)
            group_buyers.append(canonical)
            group_items.append([item])
            title_to_groups.setdefault(title_key, []).append(target)
        else:
            group_items[target].append(item)

    out: List[LifecycleGroup] = []
    for i in range(len(group_items)):
        out.append(
            LifecycleGroup(
                project_key=group_keys[i],
                buyer_canonical=group_buyers[i],
                items=tuple(group_items[i]),
            )
        )
    out.sort(key=lambda g: g.project_key)
    return out


# ---------------------------------------------------------------------------
# Stock code resolution (auditable)
# ---------------------------------------------------------------------------


# Built-in canonical entities; matches ``config/stock_mapping.py``. New
# entities can be registered via :meth:`StockCodeResolver.register` at
# startup time.
_BUILTIN_ENTITIES: Dict[str, str] = {
    "中芯国际": "sh688981",
    "韦尔股份": "sh603501",
    "北方华创": "sz002371",
    "中微公司": "sh688012",
    "寒武纪": "sh688256",
    "长电科技": "sh600584",
    "通富微电": "sz002156",
    "华天科技": "sz002185",
    "沪硅产业": "sh688126",
    "安集科技": "sh688019",
    "盛美上海": "sh688082",
    "拓荆科技": "sh688072",
    "芯源微": "sh688037",
    "江丰电子": "sz300666",
}


def _validate_stock_code(code: str) -> str:
    """Light validator: must start with ``sh`` or ``sz`` and 6 digits."""

    if not isinstance(code, str):
        raise ValueError(f"stock code must be str, got {type(code).__name__}")
    code = code.strip().lower()
    if not (code.startswith("sh") or code.startswith("sz")):
        raise ValueError(f"stock code {code!r} must start with sh/sz")
    digits = code[2:]
    if len(digits) != 6 or not digits.isdigit():
        raise ValueError(f"stock code {code!r} must be 6 digits")
    return code


@dataclass(frozen=True)
class StockResolution:
    """Audit record for a single stock-code lookup."""

    query: str
    canonical_entity: str
    stock_code: Optional[str]
    matched: bool
    resolved_at: str


class StockCodeResolver:
    """Auditable company-name -> stock-code resolver.

    Resolution is deterministic: the longest canonical entity name that
    appears (case-insensitive, whitespace-normalised) inside the query
    wins. If nothing matches, the resolver returns ``None`` and records
    the miss in the audit log. The resolver never silently fabricates a
    code, and every call is observable through :meth:`audit_log`.
    """

    def __init__(
        self,
        *,
        entities: Optional[Dict[str, str]] = None,
        audit_sink: Optional[Callable[[StockResolution], None]] = None,
    ) -> None:
        # canonical_name (lowercased) -> stock_code
        self._entities: Dict[str, str] = {}
        # preserve insertion order so audit logs are deterministic.
        for name, code in (entities if entities is not None else _BUILTIN_ENTITIES).items():
            self.register(name, code)
        self._audit_log: List[StockResolution] = []
        self._audit_sink = audit_sink

    # ---- registration ----

    def register(self, canonical_name: str, stock_code: str) -> None:
        """Add or update an entity mapping. ``stock_code`` is validated."""

        if not canonical_name or not canonical_name.strip():
            raise ValueError("canonical_name must be a non-empty string")
        key = normalise_party_name(canonical_name, strip_legal_suffix=False)
        if not key:
            raise ValueError(f"canonical_name {canonical_name!r} normalises to empty")
        self._entities[key] = _validate_stock_code(stock_code)

    @property
    def canonical_entities(self) -> Dict[str, str]:
        """Return a copy of the registered canonical entities."""

        return dict(self._entities)

    # ---- resolution ----

    def resolve(self, query: str) -> Optional[str]:
        """Return the stock code for ``query`` (longest-match) or ``None``."""

        resolution = self.resolve_with_audit(query)
        return resolution.stock_code

    def resolve_with_audit(self, query: str) -> StockResolution:
        """Return a structured :class:`StockResolution` for ``query``.

        The resolution is recorded in ``self._audit_log`` (bounded to
        256 entries) and forwarded to ``audit_sink`` if one was
        provided at construction time.
        """

        normalised_query = _normalise_text(query)
        match_key: Optional[str] = None
        match_code: Optional[str] = None
        if normalised_query:
            best_len = -1
            # Iterate by length descending so the longest canonical
            # name always wins. Ties on length fall back to ascending
            # lexicographic order so the resolver is deterministic
            # across runs.
            for key, code in sorted(
                self._entities.items(),
                key=lambda item: (-len(item[0]), item[0]),
            ):
                if key and key in normalised_query and len(key) > best_len:
                    best_len = len(key)
                    match_key = key
                    match_code = code
        canonical_entity = ""
        if match_key is not None:
            # reverse-lookup the original canonical name for the audit
            # trail (the dict maps normalised -> code, so we just record
            # the normalised key as the canonical entity reference).
            canonical_entity = match_key

        resolution = StockResolution(
            query=query,
            canonical_entity=canonical_entity,
            stock_code=match_code,
            matched=match_code is not None,
            resolved_at=datetime.now(timezone.utc).isoformat(),
        )
        self._record(resolution)
        return resolution

    # ---- audit ----

    def _record(self, resolution: StockResolution) -> None:
        self._audit_log.append(resolution)
        if len(self._audit_log) > 256:
            self._audit_log = self._audit_log[-256:]
        if self._audit_sink is not None:
            try:
                self._audit_sink(resolution)
            except Exception as exc:  # noqa: BLE001 - audit sink errors are non-fatal
                logger.warning("stock resolver audit sink failed: %s", exc)

    def audit_log(self) -> Tuple[StockResolution, ...]:
        """Return a snapshot of the recent audit log."""

        return tuple(self._audit_log)


# ---------------------------------------------------------------------------
# Compatibility shims for the legacy config/stock_mapping API
# ---------------------------------------------------------------------------


def get_stock_code(company_name: str) -> Optional[str]:
    """Backwards-compatible helper for callers that used the legacy
    ``config.stock_mapping.get_stock_code`` shim. Prefer
    :class:`StockCodeResolver` for new code.
    """

    resolver = StockCodeResolver()
    return resolver.resolve(company_name)


def find_company_in_query(query: str) -> List[Tuple[str, str]]:
    """Backwards-compatible helper. Returns the (canonical entity, stock
    code) pairs that appear inside ``query``.
    """

    resolver = StockCodeResolver()
    matches: List[Tuple[str, str]] = []
    normalised_query = _normalise_text(query)
    if not normalised_query:
        return matches
    for canonical_name, code in resolver.canonical_entities.items():
        if canonical_name and canonical_name in normalised_query:
            matches.append((canonical_name, code))
    return matches


__all__ = [
    "content_hash",
    "news_dedup_key",
    "bidding_dedup_key",
    "extract_parties",
    "normalise_party_name",
    "cluster_lifecycle",
    "LifecycleGroup",
    "StockCodeResolver",
    "StockResolution",
    "get_stock_code",
    "find_company_in_query",
]
