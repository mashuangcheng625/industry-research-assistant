"""Stress the deterministic RAG context budget with a synthetic long corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from service.chat_service import ChatService


def main() -> None:
    parser = argparse.ArgumentParser(description="验证长文档集不会绕过 RAG 上下文预算")
    parser.add_argument("--documents", type=int, default=200)
    parser.add_argument("--repetitions-per-document", type=int, default=500)
    parser.add_argument("--budget", type=int, default=6000)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.documents < 1 or args.repetitions_per_document < 1 or args.budget < 1:
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
    report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "method": "synthetic_deterministic_context_boundary",
            "documents": args.documents,
            "repetitions_per_document": args.repetitions_per_document,
            "context_token_budget": args.budget,
        },
        "result": {
            "input_tokens": input_tokens,
            "selected_documents": len(selected),
            "selected_tokens": output_tokens,
            "elapsed_seconds": round(elapsed, 6),
            "checks": checks,
            "passed": all(checks.values()),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["result"], ensure_ascii=False, indent=2))
    if not report["result"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
