"""通过真实聊天 API 评测 RAG 回答的证据覆盖、引用、拒答和延迟。"""
import argparse
import hashlib
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CITATION_PATTERN = re.compile(r"\[\[(\d+)\]\]")
DEFAULT_REFUSAL = "当前知识库未检索到足够相关的资料"
CLAIM_SENTENCE_PATTERN = re.compile(r"[^\n。！？.!?]+(?:[。！？.!?]|$)")


def normalize_match_text(text: str) -> str:
    """忽略大小写和排版空白，避免 3D结构/3D 结构这类伪失败。"""
    return re.sub(r"\s+", "", text).casefold()


def answer_gold_document_names(case: dict) -> list[str]:
    """读取端到端用例中人工标注的核心证据文档。"""
    names: list[str] = []
    for source in case.get("gold_sources", []):
        name = source if isinstance(source, str) else source.get("document", "")
        if name and name not in names:
            names.append(name)
    return names


def evaluate_gold_citations(
    case: dict,
    documents: list[dict[str, Any]],
    citations: list[int],
) -> tuple[bool, bool, list[str], list[str]]:
    """返回（金标文档已召回，金标文档已引用，召回文档，被引用文档）。"""
    document_names = [
        document.get("document_name") or document.get("filename") or ""
        for document in documents
    ]
    cited_document_names = list(dict.fromkeys(
        document_names[citation - 1]
        for citation in citations
        if 1 <= citation <= len(document_names) and document_names[citation - 1]
    ))
    expected = set(answer_gold_document_names(case))
    if not expected:
        return True, True, document_names, cited_document_names
    retrieved_ok = bool(expected & set(document_names))
    cited_ok = bool(expected & set(cited_document_names))
    return retrieved_ok, cited_ok, document_names, cited_document_names


def evaluate_term_group_citation_support(
    case: dict,
    answer: str,
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """Align labelled answer concepts with sentence citations and cited chunks.

    This is an auditable lexical support check, not an entailment judge. It proves
    that a sentence mentioning a required concept cites an in-range chunk that
    contains at least one accepted term/synonym from the same concept group.
    """
    groups = case.get("required_term_groups") or []
    if not groups:
        return {
            "group_count": 0,
            "matched_group_count": 0,
            "cited_group_count": 0,
            "supported_group_count": 0,
            "citation_completeness": 1.0,
            "citation_support_coverage": 1.0,
            "details": [],
        }

    # Models commonly emit `claim。[[1]]`; attach that marker to the preceding
    # sentence before splitting so punctuation style does not create a false miss.
    citation_attached_answer = re.sub(
        r"([。！？.!?])[ \t]*((?:\[\[\d+\]\][ \t]*)+)",
        r"\2\1",
        answer,
    )
    sentences = [
        sentence.strip()
        for sentence in CLAIM_SENTENCE_PATTERN.findall(citation_attached_answer)
        if sentence.strip()
    ]
    details: list[dict[str, Any]] = []
    for group in groups:
        normalized_terms = [normalize_match_text(str(term)) for term in group]
        matched_sentences = [
            sentence for sentence in sentences
            if any(term in normalize_match_text(sentence) for term in normalized_terms)
        ]
        citation_numbers = list(dict.fromkeys(
            int(value)
            for sentence in matched_sentences
            for value in CITATION_PATTERN.findall(sentence)
        ))
        cited_contents = [
            str(
                documents[number - 1].get("content")
                or documents[number - 1].get("content_with_weight")
                or ""
            )
            for number in citation_numbers
            if 1 <= number <= len(documents)
        ]
        supported = bool(matched_sentences and citation_numbers and any(
            term in normalize_match_text(content)
            for content in cited_contents
            for term in normalized_terms
        ))
        details.append({
            "term_group": group,
            "answer_matched": bool(matched_sentences),
            "citation_numbers": citation_numbers,
            "citation_present": bool(citation_numbers),
            "supported_by_cited_chunk": supported,
        })

    matched_count = sum(detail["answer_matched"] for detail in details)
    cited_count = sum(
        detail["answer_matched"] and detail["citation_present"] for detail in details
    )
    supported_count = sum(detail["supported_by_cited_chunk"] for detail in details)
    return {
        "group_count": len(groups),
        "matched_group_count": matched_count,
        "cited_group_count": cited_count,
        "supported_group_count": supported_count,
        "citation_completeness": cited_count / len(groups),
        "citation_support_coverage": supported_count / len(groups),
        "details": details,
    }


def parse_sse(body: str) -> tuple[str, list[dict[str, Any]], dict | None, list[Any]]:
    answer_parts: list[str] = []
    documents: list[dict[str, Any]] = []
    model_info = None
    errors: list[Any] = []
    for block in body.split("\n\n"):
        lines = block.splitlines()
        if len(lines) < 2 or not lines[0].startswith("event:"):
            continue
        event = lines[0].split(":", 1)[1].strip()
        raw = lines[1].split(":", 1)[1].strip()
        if raw == "[DONE]":
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = raw
        if event == "message" and isinstance(data, dict):
            answer_parts.append(data.get("content", ""))
            documents = data.get("documents", documents)
            model_info = data.get("model_info", model_info)
        elif event == "error":
            errors.append(data)
    return "".join(answer_parts), documents, model_info, errors


def call_chat_api(
    api_url: str,
    case: dict,
    model_mode: str,
    timeout: float,
) -> tuple[str, list[dict[str, Any]], dict | None, list[Any], float]:
    payload = {
        "question": case["question"],
        "kb_name": case["knowledge_base"],
        "search_knowledge": True,
        "search_web": False,
        "model_mode": model_mode,
    }
    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    latency = time.perf_counter() - started
    answer, documents, model_info, errors = parse_sse(body)
    return answer, documents, model_info, errors, latency


def evaluate_case(
    api_url: str,
    case: dict,
    model_mode: str,
    timeout: float,
    max_latency: float,
) -> dict:
    started = time.perf_counter()
    try:
        answer, documents, model_info, errors, latency = call_chat_api(
            api_url=api_url,
            case=case,
            model_mode=model_mode,
            timeout=timeout,
        )
    except Exception as exc:
        answer, documents, model_info = "", [], None
        errors = [{"type": type(exc).__name__, "message": str(exc)}]
        latency = time.perf_counter() - started
    folded_answer = normalize_match_text(answer)
    groups = case.get("required_term_groups", [])
    matched_groups = [
        any(normalize_match_text(term) in folded_answer for term in group)
        for group in groups
    ]
    coverage = sum(matched_groups) / len(groups) if groups else 1.0
    missing_groups = [
        group for group, matched in zip(groups, matched_groups) if not matched
    ]

    expected_retrieval = case.get("expected_retrieval", True)
    retrieval_ok = bool(documents) == expected_retrieval
    citations = [int(value) for value in CITATION_PATTERN.findall(answer)]
    citations_in_range = all(1 <= value <= len(documents) for value in citations)
    must_cite = case.get("must_cite", expected_retrieval)
    must_not_cite = case.get("must_not_cite", not expected_retrieval)
    citation_ok = citations_in_range
    if must_cite:
        citation_ok = citation_ok and bool(citations)
    if must_not_cite:
        citation_ok = citation_ok and not citations
    (
        gold_source_retrieved,
        raw_gold_citation_ok,
        document_names,
        cited_document_names,
    ) = evaluate_gold_citations(case, documents, citations)
    gold_citation_required = case.get("must_cite_gold_source", False)
    gold_citation_gate_ok = raw_gold_citation_ok or not gold_citation_required
    citation_support = evaluate_term_group_citation_support(case, answer, documents)
    minimum_citation_support = float(case.get(
        "min_citation_support_coverage",
        case.get("min_group_coverage", 1.0) if must_cite else 1.0,
    ))
    citation_support_ok = (
        citation_support["citation_support_coverage"] >= minimum_citation_support
    )
    grounding_audit = (
        model_info.get("grounding", {})
        if isinstance(model_info, dict) else {}
    )
    structured_grounding_used = bool(grounding_audit)
    structured_grounding_ok = (
        grounding_audit.get("status") == "grounded"
        and int(grounding_audit.get("accepted_claim_count", 0)) > 0
    ) if expected_retrieval and structured_grounding_used else True
    semantic_verification = str(
        grounding_audit.get("semantic_entailment_verification", "not_used")
    )
    semantic_rejection_reasons = [
        str(item.get("reason"))
        for item in grounding_audit.get("rejected_claims", [])
        if str(item.get("reason", "")).startswith("semantic_")
    ]
    refusal_ok = not case.get("must_refuse", False) or DEFAULT_REFUSAL in answer
    forbidden_hits = [
        term for term in case.get("forbidden_terms", [])
        if normalize_match_text(term) in folded_answer
    ]
    latency_ok = latency <= case.get("max_latency_seconds", max_latency)
    coverage_ok = coverage >= case.get("min_group_coverage", 1.0)
    quality_passed = all([
        not errors,
        retrieval_ok,
        coverage_ok,
        citation_ok,
        citation_support_ok,
        gold_source_retrieved,
        gold_citation_gate_ok,
        refusal_ok,
        not forbidden_hits,
    ])
    passed = quality_passed and latency_ok
    return {
        "id": case["id"],
        "domain": case["domain"],
        "category": case["category"],
        "passed": passed,
        "quality_passed": quality_passed,
        "latency_seconds": round(latency, 3),
        "latency_ok": latency_ok,
        "retrieval_ok": retrieval_ok,
        "document_count": len(documents),
        "term_group_coverage": round(coverage, 3),
        "coverage_ok": coverage_ok,
        "missing_term_groups": missing_groups,
        "citations": citations,
        "citation_ok": citation_ok,
        "gold_source_retrieved": gold_source_retrieved,
        "gold_citation_ok": raw_gold_citation_ok,
        "gold_citation_required": gold_citation_required,
        "citation_completeness": round(citation_support["citation_completeness"], 3),
        "citation_support_coverage": round(
            citation_support["citation_support_coverage"], 3
        ),
        "minimum_citation_support_coverage": minimum_citation_support,
        "citation_support_ok": citation_support_ok,
        "citation_support_details": citation_support["details"],
        "structured_grounding_used": structured_grounding_used,
        "structured_grounding_ok": structured_grounding_ok,
        "structured_candidate_claims": int(
            grounding_audit.get("candidate_claim_count", 0)
        ),
        "structured_accepted_claims": int(
            grounding_audit.get("accepted_claim_count", 0)
        ),
        "structured_rejected_claims": int(
            grounding_audit.get("rejected_claim_count", 0)
        ),
        "verified_evidence_quotes": int(
            grounding_audit.get("verified_quote_count", 0)
        ),
        "semantic_entailment_verification": semantic_verification,
        "semantic_entailment_verified_claims": int(
            grounding_audit.get("semantic_entailment_verified_count", 0)
        ),
        "semantic_entailment_rejected_claims": int(
            grounding_audit.get("semantic_entailment_rejected_count", 0)
        ),
        "semantic_verifier_error": grounding_audit.get("semantic_verifier_error"),
        "semantic_rejection_reasons": semantic_rejection_reasons,
        "document_names": document_names,
        "cited_document_names": cited_document_names,
        "refusal_ok": refusal_ok,
        "forbidden_hits": forbidden_hits,
        "model_info": model_info,
        "errors": errors,
        "answer": answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="评测端到端 RAG 回答")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000/chat/completion",
    )
    parser.add_argument("--model-mode", choices=["local", "cloud", "auto"], default="auto")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-latency", type=float, default=20.0)
    parser.add_argument("--case-id", action="append", help="只运行指定 ID，可重复")
    parser.add_argument("--output", type=Path, help="可选的 JSON 报告输出路径")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.case_id:
        selected = set(args.case_id)
        cases = [case for case in cases if case["id"] in selected]
        missing = selected - {case["id"] for case in cases}
        if missing:
            raise SystemExit(f"未找到评测用例: {sorted(missing)}")

    results = []
    for case in cases:
        result = evaluate_case(
            api_url=args.api_url,
            case=case,
            model_mode=args.model_mode,
            timeout=args.timeout,
            max_latency=args.max_latency,
        )
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        quality_status = "PASS" if result["quality_passed"] else "FAIL"
        sla_status = "PASS" if result["latency_ok"] else "FAIL"
        print(
            f"{result['id']}: {status} | latency={result['latency_seconds']:.2f}s "
            f"| docs={result['document_count']} | coverage={result['term_group_coverage']:.0%} "
            f"| citations={result['citations']} | quality={quality_status} | sla={sla_status}"
        )
        if not result["passed"]:
            print(f"  missing_groups={result['missing_term_groups']}")
            print(f"  forbidden_hits={result['forbidden_hits']}")
            print(f"  gold_source_retrieved={result['gold_source_retrieved']}")
            print(f"  gold_citation_ok={result['gold_citation_ok']}")
            print(f"  citation_support_ok={result['citation_support_ok']}")
            print(f"  citation_support_details={result['citation_support_details']}")
            print(f"  cited_document_names={result['cited_document_names']}")
            print(f"  errors={result['errors']}")
            print(f"  answer={result['answer']}")

    grouped = defaultdict(list)
    for result in results:
        grouped[result["domain"]].append(result)
    print("by_domain:")
    for domain, group in sorted(grouped.items()):
        passed = sum(result["passed"] for result in group)
        print(f"  {domain}: {passed}/{len(group)} passed")

    passed = sum(result["passed"] for result in results)
    quality_passed = sum(result["quality_passed"] for result in results)
    sla_passed = sum(result["latency_ok"] for result in results)
    gold_results = [
        result for result in results
        if answer_gold_document_names(
            next(case for case in cases if case["id"] == result["id"])
        )
    ]
    gold_retrieval_hits = sum(result["gold_source_retrieved"] for result in gold_results)
    gold_citation_hits = sum(result["gold_citation_ok"] for result in gold_results)
    positive_results = [
        result for result in results
        if next(case for case in cases if case["id"] == result["id"]).get(
            "expected_retrieval", True
        )
    ]
    refusal_results = [
        result for result in results
        if next(case for case in cases if case["id"] == result["id"]).get(
            "must_refuse", False
        )
    ]
    latencies = [result["latency_seconds"] for result in results]
    average_latency = sum(latencies) / len(latencies) if latencies else 0.0
    sorted_latencies = sorted(latencies)
    p95_index = max(0, int(len(sorted_latencies) * 0.95 + 0.999) - 1)
    p95_latency = sorted_latencies[p95_index] if sorted_latencies else 0.0
    semantic_reason_counts = Counter(
        reason
        for result in results
        for reason in result["semantic_rejection_reasons"]
    )
    summary = {
        "passed": passed,
        "strict_passed": passed,
        "quality_passed": quality_passed,
        "sla_passed": sla_passed,
        "total": len(results),
        "pass_rate": passed / len(results) if results else 0.0,
        "quality_pass_rate": quality_passed / len(results) if results else 0.0,
        "sla_pass_rate": sla_passed / len(results) if results else 0.0,
        "average_latency_seconds": round(average_latency, 3),
        "p95_latency_seconds": round(p95_latency, 3),
        "first_case_latency_seconds": round(latencies[0], 3) if latencies else 0.0,
        "p50_latency_seconds": round(
            sorted_latencies[max(0, (len(sorted_latencies) - 1) // 2)], 3
        ) if sorted_latencies else 0.0,
        "max_latency_seconds": round(max(latencies), 3) if latencies else 0.0,
        "gold_source_retrieval_hits": gold_retrieval_hits,
        "gold_source_total": len(gold_results),
        "gold_citation_hits": gold_citation_hits,
        "citation_support_passed": sum(
            result["citation_support_ok"] for result in positive_results
        ),
        "citation_support_total": len(positive_results),
        "average_citation_completeness": round(
            sum(result["citation_completeness"] for result in positive_results)
            / len(positive_results), 3
        ) if positive_results else 0.0,
        "average_citation_support_coverage": round(
            sum(result["citation_support_coverage"] for result in positive_results)
            / len(positive_results), 3
        ) if positive_results else 0.0,
        "refusal_hits": sum(result["refusal_ok"] for result in refusal_results),
        "refusal_total": len(refusal_results),
        "error_cases": sum(bool(result["errors"]) for result in results),
        "structured_grounding_cases": sum(
            result["structured_grounding_used"] for result in results
        ),
        "structured_grounding_passed": sum(
            result["structured_grounding_used"] and result["structured_grounding_ok"]
            for result in results
        ),
        "structured_candidate_claims": sum(
            result["structured_candidate_claims"] for result in results
        ),
        "structured_accepted_claims": sum(
            result["structured_accepted_claims"] for result in results
        ),
        "structured_rejected_claims": sum(
            result["structured_rejected_claims"] for result in results
        ),
        "verified_evidence_quotes": sum(
            result["verified_evidence_quotes"] for result in results
        ),
        "semantic_judge_cases": sum(
            result["semantic_entailment_verification"] in {
                "llm_judge_performed", "llm_judge_failed_closed"
            }
            for result in results
        ),
        "semantic_judge_completed_cases": sum(
            result["semantic_entailment_verification"] == "llm_judge_performed"
            for result in results
        ),
        "semantic_judge_failed_closed_cases": sum(
            result["semantic_entailment_verification"] == "llm_judge_failed_closed"
            for result in results
        ),
        "semantic_entailment_verified_claims": sum(
            result["semantic_entailment_verified_claims"] for result in results
        ),
        "semantic_entailment_rejected_claims": sum(
            result["semantic_entailment_rejected_claims"] for result in results
        ),
        "semantic_verifier_error_cases": sum(
            bool(result["semantic_verifier_error"]) for result in results
        ),
        "semantic_rejection_reason_counts": dict(sorted(semantic_reason_counts.items())),
    }
    print(
        f"summary: strict={passed}/{len(results)} | quality={quality_passed}/{len(results)} "
        f"| sla={sla_passed}/{len(results)} | "
        f"avg_latency={average_latency:.2f}s | p95_latency={p95_latency:.2f}s"
        f" | gold_retrieval={gold_retrieval_hits}/{len(gold_results)}"
        f" | gold_citation={gold_citation_hits}/{len(gold_results)}"
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({
                "metadata": {
                    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "dataset": args.cases.as_posix(),
                    "dataset_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
                    "api_url": args.api_url,
                    "model_mode": args.model_mode,
                    "timeout_seconds": args.timeout,
                    "max_latency_seconds": args.max_latency,
                },
                "summary": summary,
                "results": results,
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    raise SystemExit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
