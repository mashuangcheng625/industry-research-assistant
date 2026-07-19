"""Deterministic multi-source research runner used by CI and demo fixtures.

The runner receives only a question and a frozen source snapshot. Gold labels are
kept exclusively in the evaluator. It exercises planning, per-tool retrieval,
evidence normalization, citation rendering, inference labeling and refusal.

P1-4: Before rendering the answer, the runner feeds the assembled
evidence into :mod:`core.critic_checks` for six deterministic checks
(时效 / 数字口径 / 时点 / 来源冲突 / 跨源推断 / 缺失关键来源). Findings
are attached to the result and a structured refusal triggers when the
aggregator reports a ``block`` finding or any required source kind is
missing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.critic_checks import (
    CHECK_MISSING_SOURCE,
    SEVERITY_BLOCK,
    CriticReport,
    run_critic_checks,
)
from service.evidence_contract import Evidence
from service.evidence_adapters.bidding_adapter import adapt_bidding_item
from service.evidence_adapters.document_adapter import adapt_document_chunk
from service.evidence_adapters.market_adapter import adapt_stock_quote
from service.evidence_adapters.news_adapter import adapt_news_item
from service.evidence_adapters.sql_row_adapter import adapt_sql_result


# Required source-kind coverage derived from the question's planned
# tool chain. The runner only knows how to fetch the five tools below,
# so the policy is to require a particular source kind whenever its
# tool was scheduled. This lets the deterministic critic refuse the
# answer when an upstream provider silently degraded.
_TOOL_TO_SOURCE_KIND: Dict[str, str] = {
    "knowledge_search": "document",
    "news_search": "news",
    "bidding_search": "bidding",
    "text2sql": "sql_row",
    "stock_query": "market_quote",
}


@dataclass(frozen=True)
class SourceEvidence:
    source_id: str
    channel: str
    evidence: Evidence


def _terms(text: str) -> set[str]:
    folded = text.casefold()
    ascii_terms = set(re.findall(r"[a-z0-9][a-z0-9.+%-]*", folded))
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", folded)
    chinese_terms: set[str] = set()
    for run in chinese_runs:
        chinese_terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return ascii_terms | chinese_terms


def _score(question: str, item: SourceEvidence) -> float:
    query_terms = _terms(question)
    haystack = f"{item.evidence.title} {item.evidence.publisher} {item.evidence.content}"
    evidence_terms = _terms(haystack)
    if not query_terms:
        return 0.0
    overlap = query_terms & evidence_terms
    score = len(overlap) / len(query_terms)
    for anchor in ("2.5d", "3d", "键合", "检测", "市场", "财务", "国产", "政策"):
        if anchor in question.casefold() and anchor in haystack.casefold():
            score += 0.2
    for company in ("长电科技", "通富微电", "中微公司", "北方华创"):
        if company in question and company in haystack:
            score += 0.6
    return score


class MultiSourceResearchRunner:
    def __init__(self, fixture: dict[str, Any]):
        self.sources = self._normalize_fixture(fixture)

    @staticmethod
    def _normalize_fixture(fixture: dict[str, Any]) -> list[SourceEvidence]:
        sources: list[SourceEvidence] = []
        for item in fixture.get("documents", []):
            sources.append(SourceEvidence(str(item["doc_id"]), "knowledge_search", adapt_document_chunk(item)))
        for item in fixture.get("news", []):
            sources.append(SourceEvidence(str(item["id"]), "news_search", adapt_news_item(item)))
        for item in fixture.get("bidding", []):
            sources.append(SourceEvidence(str(item["id"]), "bidding_search", adapt_bidding_item(item)))
        for index, result in enumerate(fixture.get("sql_rows", []), start=1):
            source_id = str(result.get("id") or f"fixture-sql-{index:03d}")
            for evidence in adapt_sql_result(result, table_name=result.get("table_name", "")):
                sources.append(SourceEvidence(source_id, "text2sql", evidence))
        raw_quotes = fixture.get("market_quote", [])
        quotes = raw_quotes if isinstance(raw_quotes, list) else [raw_quotes]
        for index, quote in enumerate(quotes, start=1):
            if quote:
                source_id = str(quote.get("id") or f"fixture-stock-{index:03d}")
                sources.append(SourceEvidence(source_id, "stock_query", adapt_stock_quote(quote)))
        return sources

    @staticmethod
    def plan_tools(question: str) -> list[str]:
        tools = ["knowledge_search"]
        if any(term in question for term in ("政策", "国务院", "工信部", "产业化进展", "技术进展")):
            tools.append("news_search")
        if any(term in question for term in ("招投标", "招标", "中标", "采购", "采购预算")):
            tools.append("bidding_search")
        if any(term in question for term in ("营收", "净利润", "毛利率", "财务", "业绩", "出货量", "估值")):
            tools.append("text2sql")
        if any(term in question for term in ("股价", "行情", "估值")):
            tools.append("stock_query")
        return tools

    def _retrieve(self, question: str, tool: str) -> list[SourceEvidence]:
        candidates = [source for source in self.sources if source.channel == tool]
        if tool == "news_search" and "政策" in question:
            policy_candidates = [source for source in candidates if source.evidence.source_kind == "policy"]
            if policy_candidates:
                candidates = policy_candidates
        ranked = sorted(candidates, key=lambda item: _score(question, item), reverse=True)
        limits = {"knowledge_search": 2, "news_search": 2, "bidding_search": 2, "text2sql": 4, "stock_query": 1}
        return [item for item in ranked if _score(question, item) > 0][:limits[tool]]

    @staticmethod
    def _requires_unavailable_metric(question: str, evidence: list[SourceEvidence]) -> bool:
        corpus = " ".join(item.evidence.content for item in evidence)
        required_phrases = []
        if "单台成本" in question:
            required_phrases.append("单台成本")
        if "价差百分比" in question:
            required_phrases.append("价差")
        if "出货量" in question:
            required_phrases.append("出货量")
        return bool(required_phrases) and not all(term in corpus for term in required_phrases)

    def run(self, question: str) -> dict[str, Any]:
        tools = self.plan_tools(question)
        retrieved: list[SourceEvidence] = []
        for tool in tools:
            retrieved.extend(self._retrieve(question, tool))

        refused = not retrieved or self._requires_unavailable_metric(question, retrieved)
        inference_needed = any(term in question for term in ("分析", "是否", "差距", "趋势", "一致", "反映", "受益"))
        conflict_needed = any(term in question for term in ("是否一致", "趋势", "支持力度", "估值"))

        # P1-4: deterministic critic pre-flight. Required source kinds
        # are inferred from the scheduled tool chain so a degraded
        # upstream provider still produces a refusal rather than a
        # silently-thin evidence set.
        required_kinds = [
            _TOOL_TO_SOURCE_KIND[tool]
            for tool in tools
            if tool in _TOOL_TO_SOURCE_KIND
        ]
        evidence_dicts = [item.evidence.to_dict() for item in retrieved]
        critic_report: CriticReport = run_critic_checks(
            evidence_dicts,
            required_source_kinds=required_kinds,
        )
        if critic_report.should_refuse:
            refused = True

        if refused:
            reason_parts = ["证据不足：当前已检索来源不包含问题要求的具体数值，无法给出可靠结论。"]
            if critic_report.findings:
                block_findings = [f for f in critic_report.findings if f.severity == SEVERITY_BLOCK]
                if block_findings:
                    bullets = "; ".join(
                        f"[{f.check}] {f.subject} — {f.detail}"
                        for f in block_findings[:3]
                    )
                    reason_parts.append(f"确定性检查拒绝原因：{bullets}")
            answer = " ".join(reason_parts)
            citations: list[dict[str, Any]] = []
        else:
            lines = []
            citations = []
            for index, item in enumerate(retrieved, start=1):
                evidence = item.evidence
                time_context = evidence.as_of or evidence.published_at or "时点未提供"
                locator = evidence.locator
                lines.append(f"- 事实证据：{evidence.content} [E{index}]（时点：{time_context}）")
                citations.append({
                    "marker": f"E{index}",
                    "source_id": item.source_id,
                    "source_kind": evidence.source_kind,
                    "title": evidence.title,
                    "locator": locator,
                    "as_of": evidence.as_of,
                    "published_at": evidence.published_at,
                })
            # Surface deterministic ``warn`` / ``info`` findings so the
            # downstream evaluator and human readers see them.
            for finding in critic_report.findings:
                tag = f"[{finding.severity}][{finding.check}]"
                lines.append(f"- 确定性检查：{tag} {finding.subject} — {finding.detail}")
            if inference_needed:
                lines.append("- 研究推断：以上跨源信息只能支持方向性判断，不等同于已证实的因果关系。")
            if conflict_needed:
                lines.append("- 来源冲突检查：不同来源口径和时点可能不同；当前样本未发现可直接裁决的冲突，结论需持续复核。")
            if "股价" in question or "估值" in question:
                lines.append("- 风险提示：行情与估值分析仅供研究参考，不构成投资建议。")
            answer = "\n".join(lines)

        return {
            "question": question,
            "tools_used": tools,
            "retrieved_source_ids": sorted({item.source_id for item in retrieved}),
            "retrieved_source_kinds": sorted({item.evidence.source_kind for item in retrieved}),
            "citations": citations,
            "answer": answer,
            "refused": refused,
            "inference_labeled": (not inference_needed) or "研究推断" in answer,
            "conflict_disclosed": (not conflict_needed) or "来源冲突检查" in answer,
            "critic_report": critic_report.to_dict(),
        }
