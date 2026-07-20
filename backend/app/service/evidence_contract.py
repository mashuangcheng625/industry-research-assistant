"""
统一多源证据契约 (Unified Multi-Source Evidence Contract)

定义所有数据源适配器必须遵循的证据数据结构，使 Writer、Critic、前端引用和评测器
都能以统一方式回答：这条结论来自哪里、什么时间、哪个定位、是否允许使用、用户如何复核。

目标不是让所有来源长得一样，而是让每个事实都具备可追溯的 provenance。

参考：docs/MULTI_SOURCE_RESEARCH_PLATFORM.md §6
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 允许的来源类型
# ---------------------------------------------------------------------------
VALID_SOURCE_KINDS = frozenset({
    "document",       # PDF / 知识库文档片段
    "news",           # 行业资讯
    "policy",         # 政策文件 / 公告
    "bidding",        # 招投标公告
    "sql_row",        # 结构化数据库行
    "market_quote",   # 股票 / 市场行情
    "web_search",     # 通用网络搜索结果
})

# ---------------------------------------------------------------------------
# 允许的质量层级
# ---------------------------------------------------------------------------
VALID_QUALITY_TIERS = frozenset({
    "official",       # 政府、标准组织、官方统计数据
    "primary",        # 一手资料：学术论文、公司财报、专利
    "secondary",      # 二手资料：行业报告、券商研报、权威媒体
    "unknown",        # 无法判断来源质量
})


def _compute_hash(content: str) -> str:
    """对证据内容计算 SHA-256 哈希，用于去重和完整性校验。"""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def _now_utc_iso() -> str:
    """返回当前 UTC 时间的 ISO-8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Evidence:
    """统一证据对象。

    所有要求:
    - evidence_id: 稳定标识，基于内容和来源的哈希
    - source_kind: 枚举值，见 VALID_SOURCE_KINDS
    - title: 人类可读标签
    - publisher: 发布方或数据提供方
    - url: 可选原始链接
    - published_at: 可选发布时间 (ISO-8601)
    - retrieved_at: 采集时间 (ISO-8601)
    - as_of: 行情或统计口径时点 (ISO-8601)，可为 None
    - locator: 定位信息，如 {"page": 12, "row_ids": [], "notice_id": null}
    - content: 支持结论的最小证据内容
    - content_hash: content 的 SHA-256
    - quality_tier: 质量层级，见 VALID_QUALITY_TIERS
    - license_or_terms: 许可或使用条款判断
    """

    evidence_id: str
    source_kind: str
    title: str
    publisher: str
    url: Optional[str]
    published_at: Optional[str]
    retrieved_at: str
    as_of: Optional[str]
    locator: dict
    content: str
    content_hash: str
    quality_tier: str
    license_or_terms: str

    # ---- 工厂方法 ----

    @classmethod
    def create(
        cls,
        source_kind: str,
        title: str,
        publisher: str,
        content: str,
        *,
        url: Optional[str] = None,
        published_at: Optional[str] = None,
        retrieved_at: Optional[str] = None,
        as_of: Optional[str] = None,
        locator: Optional[dict] = None,
        quality_tier: str = "unknown",
        license_or_terms: str = "not_assessed",
    ) -> "Evidence":
        """创建一条 Evidence 并自动计算 evidence_id 和 content_hash。

        evidence_id 基于 (source_kind, publisher, title, content) 的复合哈希，
        确保相同内容不产生重复 evidence_id。
        """
        content_hash = _compute_hash(content)
        id_seed = f"{source_kind}|{publisher}|{title}|{content_hash}"
        evidence_id = hashlib.sha256(id_seed.encode("utf-8")).hexdigest()[:24]

        return cls(
            evidence_id=evidence_id,
            source_kind=source_kind,
            title=title,
            publisher=publisher,
            url=url,
            published_at=published_at,
            retrieved_at=retrieved_at or _now_utc_iso(),
            as_of=as_of,
            locator=locator or {},
            content=content,
            content_hash=content_hash,
            quality_tier=quality_tier,
            license_or_terms=license_or_terms,
        )

    # ---- 便利方法 ----

    def to_dict(self) -> dict:
        """转为字典，用于 JSON 序列化和 API 响应。"""
        payload = asdict(self)
        payload["citation_locator"] = CitationLocator.from_evidence(self).to_dict()
        return payload

    def to_json(self, indent: int = 2) -> str:
        """转为格式化的 JSON 字符串。"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @property
    def is_timely(self) -> bool:
        """如果具备发布时间或统计时点则返回 True。"""
        return self.published_at is not None or self.as_of is not None

    @property
    def can_locate(self) -> bool:
        """如果 locator 包含足够信息让用户找到原始证据则返回 True。"""
        loc = self.locator
        if not loc:
            return False
        return bool(
            loc.get("page")
            or loc.get("row_ids")
            or loc.get("notice_id")
            or loc.get("chunk_index") is not None
            or loc.get("line_numbers")
        )

    @property
    def short_ref(self) -> str:
        """生成一个简短的引用字符串，用于报告中提及。"""
        parts = [self.publisher or self.title]
        if self.published_at:
            parts.append(self.published_at[:4])
        if self.url:
            parts.append(self.url[:60])
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# 契约校验
# ---------------------------------------------------------------------------


def validate_evidence(evidence: Evidence) -> list[str]:
    """验证一条 Evidence 对象是否满足契约要求。

    返回一个错误消息列表；空列表表示通过。
    """
    errors: list[str] = []

    if not evidence.evidence_id:
        errors.append("evidence_id 不能为空")
    if evidence.source_kind not in VALID_SOURCE_KINDS:
        errors.append(
            f"source_kind '{evidence.source_kind}' 无效，允许值: {sorted(VALID_SOURCE_KINDS)}"
        )
    if not evidence.title.strip():
        errors.append("title 不能为空")
    if not evidence.publisher.strip():
        errors.append("publisher 不能为空")
    if not evidence.content.strip():
        errors.append("content 不能为空")
    if evidence.quality_tier not in VALID_QUALITY_TIERS:
        errors.append(
            f"quality_tier '{evidence.quality_tier}' 无效，允许值: {sorted(VALID_QUALITY_TIERS)}"
        )

    # 验证 content_hash 一致性
    expected_hash = _compute_hash(evidence.content)
    if evidence.content_hash != expected_hash:
        errors.append(
            f"content_hash 不匹配: 预期 {expected_hash[:12]}..., 实际 {evidence.content_hash[:12]}..."
        )

    # 验证 locator 结构
    loc = evidence.locator
    if not isinstance(loc, dict):
        errors.append("locator 必须是 dict")

    # 对特定 source_kind 的校验
    if evidence.source_kind == "document" and loc:
        if not (loc.get("page") or loc.get("chunk_index") is not None):
            errors.append("document 类型的 locator 需包含 page 或 chunk_index")
    elif evidence.source_kind == "bidding":
        if not loc.get("notice_id"):
            errors.append("bidding 类型的 locator 需包含 notice_id")
    elif evidence.source_kind == "market_quote":
        if not evidence.as_of:
            errors.append("market_quote 类型建议包含 as_of 时间戳")

    return errors


def validate_evidence_collection(evidences: list[Evidence]) -> dict:
    """验证一组 Evidence 对象，返回汇总报告。"""
    results = []
    for evidence in evidences:
        issues = validate_evidence(evidence)
        results.append({
            "evidence_id": evidence.evidence_id,
            "source_kind": evidence.source_kind,
            "title": evidence.title,
            "valid": len(issues) == 0,
            "issues": issues,
        })

    valid_count = sum(1 for r in results if r["valid"])
    invalid_count = len(results) - valid_count

    return {
        "total": len(results),
        "valid": valid_count,
        "invalid": invalid_count,
        "details": results,
        "timestamp": _now_utc_iso(),
    }


# ---------------------------------------------------------------------------
# 来源类型的文本描述映射
# ---------------------------------------------------------------------------

SOURCE_KIND_LABELS: dict[str, str] = {
    "document": "专业文档",
    "news": "行业资讯",
    "policy": "政策文件",
    "bidding": "招投标",
    "sql_row": "结构化数据",
    "market_quote": "市场行情",
    "web_search": "网络搜索",
}

QUALITY_TIER_LABELS: dict[str, str] = {
    "official": "官方来源",
    "primary": "一手资料",
    "secondary": "二手资料",
    "unknown": "未知来源",
}


# ---------------------------------------------------------------------------
# Unified citation locator (P1-14)
# ---------------------------------------------------------------------------
# Every source kind carries its own locator shape (page number for PDFs,
# row_id for sql_rows, notice_id for bidding, stock_code for market
# quotes). ``CitationLocator`` normalises each shape into a single
# machine-readable anchor so the front-end evidence panel and the
# deterministic critic can reason about provenance without switching on
# ``source_kind``.
#
# Usage::
#
#     loc = CitationLocator.from_evidence(evidence)
#     print(loc.anchor)        # "page 34" or "row abcd1234..."
#     print(loc.reference_url) # publisher link or None
#     print(loc.to_html())     # "<a href=...>p. 34</a>" — display-safe


from dataclasses import dataclass


@dataclass(frozen=True)
class CitationLocator:
    """Unified provenance anchor that works across all source kinds.

    The ``anchor`` field is the primary human-readable locator
    (``"page 34"`` / ``"row abcd"`` / ``"notice 2024-8173"`` /
    ``"sh688012"``). ``reference_url`` is a verification link when
    the source exposes a public URL; it is ``None`` when the source
    is internal (database row, local document).
    """

    anchor: str
    reference_url: Optional[str] = None
    source_kind: str = "unknown"

    def to_html(self) -> str:
        label = f"[{SOURCE_KIND_LABELS.get(self.source_kind, self.source_kind)}] {self.anchor}"
        if self.reference_url:
            return f'<a href="{self.reference_url}" target="_blank" rel="noopener">{label}</a>'
        return label

    def to_dict(self) -> dict:
        return {
            "anchor": self.anchor,
            "reference_url": self.reference_url,
            "source_kind": self.source_kind,
        }

    @classmethod
    def from_evidence(cls, evidence: Evidence) -> "CitationLocator":
        """Build a ``CitationLocator`` from a single ``Evidence`` row.

        The mapping is deterministic per ``source_kind`` so the
        front-end can render familiar labels and the critic can
        compare locator precision across sources.
        """

        kind = evidence.source_kind
        loc = evidence.locator or {}

        if kind == "document":
            page = loc.get("page")
            chunk = loc.get("chunk_index")
            if page is not None:
                anchor = f"p. {page}"
            elif chunk is not None:
                anchor = f"chunk {chunk}"
            else:
                anchor = evidence.title[:50]
            return cls(anchor=anchor, reference_url=evidence.url, source_kind=kind)

        if kind in ("news", "policy", "web_search"):
            if evidence.url:
                domain = _domain_from_url(evidence.url)
                anchor = f"{domain} — {evidence.title[:40]}"
            else:
                anchor = evidence.title[:50]
            return cls(anchor=anchor, reference_url=evidence.url, source_kind=kind)

        if kind == "bidding":
            notice_id = loc.get("notice_id", "")
            anchor = f"notice {notice_id}" if notice_id else evidence.title[:50]
            return cls(anchor=anchor, reference_url=None, source_kind=kind)

        if kind == "sql_row":
            row_id = loc.get("row_id", loc.get("row_hash", ""))
            table = loc.get("table_name", "")
            anchor = f"row {row_id[:12]}" if row_id else f"table {table}"
            return cls(anchor=anchor, reference_url=None, source_kind=kind)

        if kind == "market_quote":
            code = loc.get("stock_code", "")
            anchor = code if code else evidence.title[:50]
            return cls(anchor=anchor, reference_url=None, source_kind=kind)

        return cls(anchor=evidence.title[:50], reference_url=evidence.url, source_kind=kind)

    @classmethod
    def from_reference(cls, reference: dict[str, Any]) -> "CitationLocator":
        """Normalize an existing API/fact reference without removing legacy fields."""
        existing = reference.get("citation_locator")
        if isinstance(existing, dict) and existing.get("anchor"):
            return cls(
                anchor=str(existing["anchor"]),
                reference_url=existing.get("reference_url"),
                source_kind=str(existing.get("source_kind") or "unknown"),
            )

        metadata = reference.get("metadata") or reference.get("_source_metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        raw_locator = reference.get("locator") or {}
        locator = dict(raw_locator) if isinstance(raw_locator, dict) else {}
        for key in (
            "page", "chunk_index", "doc_id", "kb_id", "notice_id",
            "row_id", "row_hash", "table_name", "stock_code",
        ):
            value = reference.get(key, metadata.get(key))
            if value is not None and key not in locator:
                locator[key] = value

        url = reference.get("url") or reference.get("link") or reference.get("source_url")
        source_kind = reference.get("source_kind")
        if source_kind not in VALID_SOURCE_KINDS:
            origin = metadata.get("evidence_origin")
            source = reference.get("source")
            if source == "knowledge" or origin == "local_knowledge_base" or str(url or "").startswith("local://"):
                source_kind = "document"
            else:
                source_kind = "web_search"

        title = str(
            reference.get("title")
            or reference.get("document_name")
            or reference.get("source_name")
            or "未命名来源"
        )
        evidence = Evidence.create(
            source_kind=str(source_kind),
            title=title,
            publisher=str(reference.get("publisher") or reference.get("source_name") or title),
            content=str(reference.get("content") or reference.get("snippet") or title),
            url=str(url) if url else None,
            locator=locator,
        )
        return cls.from_evidence(evidence)


def with_citation_locator(reference: dict[str, Any]) -> dict[str, Any]:
    """Return an additive, JSON-safe reference carrying unified provenance."""
    payload = dict(reference)
    citation_locator = CitationLocator.from_reference(payload)
    if payload.get("source_kind") not in VALID_SOURCE_KINDS:
        payload["source_kind"] = citation_locator.source_kind
    payload["citation_locator"] = citation_locator.to_dict()
    return payload


def _domain_from_url(url: str) -> str:
    import re
    m = re.search(r"https?://([^/]+)", url)
    return m.group(1) if m else url[:40]
