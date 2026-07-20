"""Stress evidence and request-wide context budgets without calling providers."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from service.chat_service import ChatService
from core.context_budget import ContextBudget, ContextBudgetExceeded


REQUEST_PATHS: dict[str, dict[str, float]] = {
    "chat": {"system_prompt": 0.2, "question": 0.1, "history": 0.2, "memory": 0.1, "evidence": 0.4},
    "research_agent": {"system_prompt": 0.35, "question": 0.15, "evidence": 0.5},
    "memory_summary": {"system_prompt": 0.2, "history": 0.8},
    "text2sql": {"system_prompt": 0.35, "question": 0.1, "evidence": 0.55},
    "semantic_judge": {"system_prompt": 0.3, "evidence": 0.7},
    "react_plan": {"system_prompt": 0.55, "question": 0.45},
    "react_think": {"system_prompt": 0.25, "question": 0.15, "history": 0.25, "evidence": 0.35},
    "react_reflect": {"system_prompt": 0.25, "question": 0.15, "history": 0.2, "evidence": 0.4},
    "drg_qwen": {"system_prompt": 0.3, "question": 0.7},
    "drg_report": {"system_prompt": 0.2, "question": 0.1, "memory": 0.1, "evidence": 0.6},
}
LOAD_RATIOS = (0.5, 0.9, 0.99, 1.01)


def build_request_wide_matrix(
    total_cap: int,
    requested_output: int = 2048,
    minimum_output: int = 256,
) -> dict:
    """Build an exact-token boundary matrix for every direct LLM call path."""
    results = []
    for path, weights in REQUEST_PATHS.items():
        for ratio in LOAD_RATIOS:
            target_input = int(total_cap * ratio)
            allocation = {
                bucket: int(target_input * weight)
                for bucket, weight in weights.items()
            }
            remainder = target_input - sum(allocation.values())
            first_bucket = next(iter(allocation))
            allocation[first_bucket] += remainder
            budget = ContextBudget(total_cap=total_cap).add(**allocation)
            rejected = False
            try:
                effective_output = budget.reserve_output(
                    requested_output,
                    minimum=minimum_output,
                )
            except ContextBudgetExceeded:
                effective_output = 0
                rejected = True
            results.append({
                "path": path,
                "input_ratio": ratio,
                "input_tokens": budget.used,
                "requested_output": requested_output,
                "effective_output": effective_output,
                "rejected": rejected,
                "summary": budget.summary(),
            })

    checks = {
        "all_paths_covered": {row["path"] for row in results} == set(REQUEST_PATHS),
        "accepted_requests_fit": all(
            row["rejected"] or row["summary"]["total_with_output"] <= total_cap
            for row in results
        ),
        "near_limit_output_is_capped": all(
            any(
                row["path"] == path
                and row["input_ratio"] == 0.99
                and 0 < row["effective_output"] < requested_output
                for row in results
            )
            for path in REQUEST_PATHS
        ),
        "overload_is_rejected": all(
            any(
                row["path"] == path
                and row["input_ratio"] == 1.01
                and row["rejected"]
                for row in results
            )
            for path in REQUEST_PATHS
        ),
    }
    return {
        "total_cap": total_cap,
        "requested_output": requested_output,
        "minimum_output": minimum_output,
        "paths": sorted(REQUEST_PATHS),
        "load_ratios": list(LOAD_RATIOS),
        "cases": results,
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="验证长文档集不会绕过 RAG 上下文预算")
    parser.add_argument("--documents", type=int, default=200)
    parser.add_argument("--repetitions-per-document", type=int, default=500)
    parser.add_argument("--budget", type=int, default=6000)
    parser.add_argument("--total-budget", type=int, default=32768)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (
        args.documents < 1
        or args.repetitions_per_document < 1
        or args.budget < 1
        or args.total_budget < 1024
    ):
        raise SystemExit("参数必须为正整数")

    service = ChatService(None, None)
    service.max_tokens = args.budget
    documents = [
        {
            "id": index + 1,
            "title": f"synthetic-long-document-{index + 1}",
            "content": (
                f"semiconductor evidence section {index + 1}. "
                * args.repetitions_per_document
            ),
            "weight": 1.0 - index / (args.documents * 2),
        }
        for index in range(args.documents)
    ]
    input_tokens = sum(
        len(service.encoding.encode(document["content"])) for document in documents
    )

    started_at = time.perf_counter()
    selected = service._filter_documents_by_token_limit(documents)
    elapsed = time.perf_counter() - started_at
    output_tokens = sum(
        len(service.encoding.encode(document["content"])) for document in selected
    )
    checks = {
        "token_budget_respected": output_tokens <= args.budget,
        "document_limit_respected": len(selected) <= 10,
        "input_was_larger_than_budget": input_tokens > args.budget,
    }
    request_wide = build_request_wide_matrix(args.total_budget)
    report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "method": "synthetic_deterministic_context_boundary",
            "documents": args.documents,
            "repetitions_per_document": args.repetitions_per_document,
            "context_token_budget": args.budget,
            "request_total_token_budget": args.total_budget,
        },
        "result": {
            "input_tokens": input_tokens,
            "selected_documents": len(selected),
            "selected_tokens": output_tokens,
            "elapsed_seconds": round(elapsed, 6),
            "checks": checks,
            "passed": all(checks.values()),
        },
        "request_wide_matrix": request_wide,
    }
    report["overall_pass"] = report["result"]["passed"] and request_wide["passed"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["result"], ensure_ascii=False, indent=2))
    if not report["overall_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
