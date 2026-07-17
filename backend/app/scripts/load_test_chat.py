"""Closed-loop concurrent load test for the evidence-grounded chat API."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any

from scripts.evaluate_rag_answers import evaluate_case


def percentile(values: list[float], quantile: float) -> float:
    """Nearest-rank percentile, including small-sample behavior."""
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(len(ordered) * min(1.0, max(0.0, quantile))))
    return ordered[rank - 1]


def summarize_load(
    results: list[dict[str, Any]],
    *,
    wall_seconds: float,
    max_p95_seconds: float,
    max_error_rate: float,
    min_quality_pass_rate: float,
) -> dict[str, Any]:
    latencies = [float(result["latency_seconds"]) for result in results]
    error_count = sum(bool(result.get("errors")) for result in results)
    quality_count = sum(bool(result.get("quality_passed")) for result in results)
    total = len(results)
    error_rate = error_count / total if total else 1.0
    quality_rate = quality_count / total if total else 0.0
    p95 = percentile(latencies, 0.95)
    thresholds = {
        "p95_latency": p95 <= max_p95_seconds,
        "error_rate": error_rate <= max_error_rate,
        "quality_pass_rate": quality_rate >= min_quality_pass_rate,
    }
    return {
        "requests": total,
        "successful_responses": total - error_count,
        "error_count": error_count,
        "error_rate": round(error_rate, 4),
        "quality_passed": quality_count,
        "quality_pass_rate": round(quality_rate, 4),
        "wall_seconds": round(wall_seconds, 3),
        "throughput_requests_per_second": round(
            total / wall_seconds if wall_seconds > 0 else 0.0, 4
        ),
        "average_latency_seconds": round(
            sum(latencies) / len(latencies) if latencies else 0.0, 3
        ),
        "p50_latency_seconds": round(percentile(latencies, 0.50), 3),
        "p95_latency_seconds": round(p95, 3),
        "p99_latency_seconds": round(percentile(latencies, 0.99), 3),
        "max_latency_seconds": round(max(latencies) if latencies else 0.0, 3),
        "thresholds": thresholds,
        "passed": all(thresholds.values()),
    }


def load_cases(path: Path, selected_ids: list[str] | None) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if selected_ids:
        selected = set(selected_ids)
        rows = [row for row in rows if row.get("id") in selected]
        missing = selected - {row.get("id") for row in rows}
        if missing:
            raise SystemExit(f"未找到压测用例: {sorted(missing)}")
    if not rows:
        raise SystemExit("压测用例不能为空")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="并发评测 RAG 回答延迟、错误与质量")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/chat/completion")
    parser.add_argument("--model-mode", choices=["local", "cloud", "auto"], default="local")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--requests", type=int, default=8)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-latency", type=float, default=20.0)
    parser.add_argument("--max-p95", type=float, default=30.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--min-quality-pass-rate", type=float, default=0.0)
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.concurrency < 1 or args.requests < 1 or args.warmup < 0:
        raise SystemExit("concurrency/requests 必须为正整数，warmup 不能为负")

    cases = load_cases(args.cases, args.case_id)
    warmup_results = []
    for index in range(args.warmup):
        case = cases[index % len(cases)]
        warmup_results.append(evaluate_case(
            args.api_url,
            case,
            args.model_mode,
            args.timeout,
            args.max_latency,
        ))

    assignments = [
        (request_index, cases[request_index % len(cases)])
        for request_index in range(args.requests)
    ]
    started_at = time.perf_counter()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_map = {
            executor.submit(
                evaluate_case,
                args.api_url,
                case,
                args.model_mode,
                args.timeout,
                args.max_latency,
            ): (request_index, case["id"])
            for request_index, case in assignments
        }
        for future in as_completed(future_map):
            request_index, case_id = future_map[future]
            result = future.result()
            result["request_index"] = request_index
            results.append(result)
            print(
                f"request={request_index} case={case_id} "
                f"latency={result['latency_seconds']:.3f}s "
                f"errors={len(result['errors'])} quality={result['quality_passed']}"
            )
    wall_seconds = time.perf_counter() - started_at
    results.sort(key=lambda item: item["request_index"])
    summary = summarize_load(
        results,
        wall_seconds=wall_seconds,
        max_p95_seconds=args.max_p95,
        max_error_rate=args.max_error_rate,
        min_quality_pass_rate=args.min_quality_pass_rate,
    )
    report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "dataset": args.cases.as_posix(),
            "dataset_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
            "api_url": args.api_url,
            "model_mode": args.model_mode,
            "concurrency": args.concurrency,
            "requests": args.requests,
            "warmup": args.warmup,
            "timeout_seconds": args.timeout,
            "max_latency_seconds": args.max_latency,
            "max_p95_seconds": args.max_p95,
            "max_error_rate": args.max_error_rate,
            "min_quality_pass_rate": args.min_quality_pass_rate,
        },
        "summary": summary,
        "warmup_results": warmup_results,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
