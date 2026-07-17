"""运行半导体知识库的正样本与无证据负样本检索评测。"""
import argparse
import hashlib
import json
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from service.retrieval_service import retrieve_from_knowledge_base


def normalize_evidence_text(text: str) -> str:
    """规整 PDF 抽取导致的换行，避免同一短语被分行后误判为缺失。"""
    return re.sub(r"\s+", " ", text).strip().casefold()


def gold_document_names(case: dict) -> list[str]:
    """将 gold_sources 统一转换为文件名。

    同时支持简写字符串和带 heading 等审核信息的对象。
    """
    names: list[str] = []
    for source in case.get("gold_sources", []):
        if isinstance(source, str):
            name = source
        elif isinstance(source, dict):
            name = source.get("document", "")
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


def evaluate_gold_sources(case: dict, results: list[dict]) -> tuple[bool, list[str]]:
    """判断检索结果是否命中人工标注的证据文档。"""
    expected = gold_document_names(case)
    if not expected or not case.get("expected_retrieval", True):
        return True, []

    retrieved = {
        result.get("document_name")
        for result in results
        if result.get("document_name")
    }
    missing = [name for name in expected if name not in retrieved]
    match_mode = case.get("gold_source_match", "any")
    if match_mode == "all":
        return not missing, missing
    if match_mode != "any":
        raise ValueError(f"gold_source_match 仅支持 any/all: {match_mode}")
    matched = len(missing) < len(expected)
    return matched, ([] if matched else missing)


def gold_ranking_metrics(case: dict, results: list[dict], top_k: int) -> tuple[int | None, float, float]:
    """Return first relevant document rank, reciprocal rank, and document-level nDCG@K."""
    gold = set(gold_document_names(case))
    if not gold or not case.get("expected_retrieval", True):
        return None, 0.0, 0.0
    ranked_documents = list(dict.fromkeys(
        result.get("document_name")
        for result in results
        if result.get("document_name")
    ))[:top_k]
    relevant_ranks = [
        rank for rank, document in enumerate(ranked_documents, start=1)
        if document in gold
    ]
    first_rank = relevant_ranks[0] if relevant_ranks else None
    reciprocal_rank = 1.0 / first_rank if first_rank else 0.0
    dcg = sum(1.0 / math.log2(rank + 1) for rank in relevant_ranks)
    ideal_relevant = min(len(gold), top_k)
    ideal_dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank in range(1, ideal_relevant + 1)
    )
    return first_rank, reciprocal_rank, dcg / ideal_dcg if ideal_dcg else 0.0


def required_group_coverage(case: dict, combined_content: str) -> tuple[float, list[list[str]]]:
    groups = case.get("required_term_groups") or []
    if not groups:
        return 1.0, []
    missing = [
        group for group in groups
        if not any(normalize_evidence_text(str(term)) in combined_content for term in group)
    ]
    return (len(groups) - len(missing)) / len(groups), missing


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def evaluate_case(case: dict, top_k: int) -> dict:
    started = time.perf_counter()
    results = retrieve_from_knowledge_base(
        kb_name=case["knowledge_base"],
        question=case["question"],
        top_k=top_k,
    )
    expected_retrieval = case.get("expected_retrieval", True)
    expected_terms = case.get("expected_terms", [])
    combined_content = normalize_evidence_text("\n".join(
        result["content_with_weight"] for result in results
    ))
    missing_terms = [
        term for term in expected_terms
        if normalize_evidence_text(term) not in combined_content
    ]
    group_coverage, missing_term_groups = required_group_coverage(case, combined_content)
    minimum_group_coverage = float(case.get("min_group_coverage", 1.0))
    group_coverage_ok = group_coverage >= minimum_group_coverage

    retrieval_ok = bool(results) == expected_retrieval
    terms_ok = not missing_terms
    gold_source_ok, missing_gold_sources = evaluate_gold_sources(case, results)
    gold_rank, reciprocal_rank, ndcg_at_k = gold_ranking_metrics(case, results, top_k)
    return {
        "id": case["id"],
        "domain": case.get("domain"),
        "category": case.get("category"),
        "knowledge_base": case["knowledge_base"],
        "expected_retrieval": expected_retrieval,
        "passed": retrieval_ok and terms_ok and group_coverage_ok and gold_source_ok,
        "retrieval_ok": retrieval_ok,
        "terms_ok": terms_ok,
        "gold_source_ok": gold_source_ok,
        "group_coverage_ok": group_coverage_ok,
        "group_coverage": round(group_coverage, 4),
        "minimum_group_coverage": minimum_group_coverage,
        "result_count": len(results),
        "top_score": results[0]["score"] if results else None,
        "top_document": results[0]["document_name"] if results else None,
        "retrieved_documents": list(dict.fromkeys(
            result["document_name"] for result in results
        )),
        "missing_terms": missing_terms,
        "missing_term_groups": missing_term_groups,
        "missing_gold_sources": missing_gold_sources,
        "gold_rank": gold_rank,
        "reciprocal_rank": round(reciprocal_rank, 6),
        "ndcg_at_k": round(ndcg_at_k, 6),
        "neighbor_count": sum(bool(result.get("is_neighbor")) for result in results),
        "query_variant_count": max(
            (int(result.get("query_variant_count", 1)) for result in results),
            default=1,
        ),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="评测 RAG 检索与低分过滤")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--output", type=Path, help="可选的 JSON 报告输出路径")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    results = [evaluate_case(case, args.top_k) for case in cases]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        score = (
            f"{result['top_score']:.4f}"
            if result["top_score"] is not None
            else "-"
        )
        print(
            f"{result['id']}: {status} | count={result['result_count']} "
            f"| top_score={score} | top_document={result['top_document']}"
        )
        if result["missing_terms"]:
            print(f"  missing_terms={result['missing_terms']}")
        if result["missing_gold_sources"]:
            print(f"  missing_gold_sources={result['missing_gold_sources']}")

    passed = sum(result["passed"] for result in results)
    positive = [r for r in results if r["expected_retrieval"]]
    negative = [r for r in results if not r["expected_retrieval"]]
    positive_hits = sum(r["retrieval_ok"] for r in positive)
    negative_rejections = sum(r["retrieval_ok"] for r in negative)
    cases_by_id = {case["id"]: case for case in cases}
    gold_cases = [
        result for result in positive
        if gold_document_names(cases_by_id[result["id"]])
    ]
    gold_source_hits = sum(r["gold_source_ok"] for r in gold_cases)
    mean_reciprocal_rank = (
        sum(result["reciprocal_rank"] for result in gold_cases) / len(gold_cases)
        if gold_cases else 0.0
    )
    mean_ndcg = (
        sum(result["ndcg_at_k"] for result in gold_cases) / len(gold_cases)
        if gold_cases else 0.0
    )
    positive_group_coverage = (
        sum(result["group_coverage"] for result in positive) / len(positive)
        if positive else 0.0
    )
    latencies = [float(result["elapsed_ms"]) for result in results]

    grouped = defaultdict(list)
    for result in results:
        grouped[result["knowledge_base"]].append(result)

    print("by_knowledge_base:")
    for knowledge_base, group in sorted(grouped.items()):
        group_passed = sum(result["passed"] for result in group)
        print(f"  {knowledge_base}: {group_passed}/{len(group)} passed")

    grouped_categories = defaultdict(list)
    for result in results:
        grouped_categories[result.get("category") or "uncategorized"].append(result)
    print("by_category:")
    for category, group in sorted(grouped_categories.items()):
        group_passed = sum(result["passed"] for result in group)
        print(f"  {category}: {group_passed}/{len(group)} passed")

    print(
        f"summary: {passed}/{len(results)} passed | "
        f"positive_hit_rate={positive_hits}/{len(positive)} | "
        f"negative_rejection_rate={negative_rejections}/{len(negative)} | "
        f"gold_source_hit_rate={gold_source_hits}/{len(gold_cases)} | "
        f"MRR={mean_reciprocal_rank:.4f} | nDCG@{args.top_k}={mean_ndcg:.4f} | "
        f"P95={percentile(latencies, 0.95):.1f}ms"
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "summary": {
                "passed": passed,
                "total": len(results),
                "positive_hits": positive_hits,
                "positive_total": len(positive),
                "negative_rejections": negative_rejections,
                "negative_total": len(negative),
                "gold_source_hits": gold_source_hits,
                "gold_source_total": len(gold_cases),
                "mrr": round(mean_reciprocal_rank, 6),
                "ndcg_at_k": round(mean_ndcg, 6),
                "mean_group_coverage": round(positive_group_coverage, 6),
                "average_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
                "first_case_latency_ms": round(latencies[0], 1) if latencies else 0.0,
                "p50_latency_ms": round(percentile(latencies, 0.50), 1),
                "p95_latency_ms": round(percentile(latencies, 0.95), 1),
                "max_latency_ms": round(max(latencies), 1) if latencies else 0.0,
                "total_neighbors": sum(result["neighbor_count"] for result in results),
                "average_query_variants": round(
                    (
                        sum(result["query_variant_count"] for result in results) / len(results)
                        if results else 0.0
                    ),
                    3,
                ),
            },
            "metadata": {
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "dataset": args.cases.as_posix(),
                "dataset_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                "top_k": args.top_k,
                "retrieval_configuration": {
                    key: os.getenv(key)
                    for key in (
                        "RAG_HYBRID_ENABLED",
                        "RAG_MULTI_QUERY_ENABLED",
                        "RAG_NEIGHBOR_ENABLED",
                        "RAG_VECTOR_WEIGHT",
                        "RAG_LEXICAL_WEIGHT",
                        "RAG_QUERY_FOCUS_WEIGHT",
                        "RAG_DOCUMENT_COVERAGE_WEIGHT",
                        "RAG_MIN_SCORE",
                        "RAG_MIN_LEXICAL_SCORE",
                    )
                },
            },
            "results": results,
        }
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    raise SystemExit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
