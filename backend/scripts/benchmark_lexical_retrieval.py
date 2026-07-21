"""Benchmark legacy lexical scanning against Milvus server-side BM25."""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
APP_DIR = BACKEND_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

from service.embedding_router import collection_name_for_route, get_embedding_route  # noqa: E402
from service.milvus_service import MilvusService, lexical_collection_name  # noqa: E402
from service.retrieval_service import _build_query_plan, _collect_lexical_candidates  # noqa: E402


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[max(0, math.ceil(quantile * len(ordered)) - 1)]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT_DIR / "sample-data" / "semiconductor_rag_eval_development.json",
    )
    parser.add_argument("--source-route", choices=("cloud", "local"), default="local")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "reports" / "lexical_backend_benchmark_latest.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.iterations < 1 or args.top_k < 1:
        raise SystemExit("--iterations and --top-k must be positive")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    service = MilvusService()
    route = get_embedding_route(args.source_route)

    # Warm the legacy snapshot cache once per dense collection. The comparison
    # therefore measures its best steady-state behavior, not initial I/O.
    collection_sizes: dict[str, int] = {}
    for case in cases:
        base = f"kb_{case['knowledge_base']}"
        dense = collection_name_for_route(base, route)
        if dense in collection_sizes:
            continue
        size = int(service.get_collection_stats(dense).get("num_entities", 0))
        if size <= 0:
            raise RuntimeError(f"dense source is missing or empty: {dense}")
        service.list_chunks(dense, limit=int(os.getenv("RAG_LEXICAL_SCAN_LIMIT", "10000")))
        collection_sizes[dense] = size

    timings: dict[str, list[float]] = {"scan": [], "milvus": []}
    candidate_counts: dict[str, list[int]] = {"scan": [], "milvus": []}
    for backend in ("scan", "milvus"):
        os.environ["RAG_LEXICAL_BACKEND"] = backend
        os.environ["RAG_LEXICAL_FALLBACK_ENABLED"] = "false"
        os.environ["RAG_LEXICAL_TOP_K"] = str(args.top_k)
        for _ in range(args.iterations):
            for case in cases:
                base = f"kb_{case['knowledge_base']}"
                query_plan = _build_query_plan(case["question"])
                started = time.perf_counter()
                candidates, selected_backend, degradation = _collect_lexical_candidates(
                    service,
                    dense_collection_name=collection_name_for_route(base, route),
                    bm25_collection_name=lexical_collection_name(base),
                    query_variants=[variant for variant, _ in query_plan],
                    query_focus_terms=[focus for _, focus in query_plan],
                    question=case["question"],
                    candidate_k=args.top_k,
                    kb_id=None,
                )
                elapsed_ms = (time.perf_counter() - started) * 1000
                if degradation:
                    raise RuntimeError(f"unexpected lexical degradation: {degradation}")
                expected_backend = "milvus_bm25" if backend == "milvus" else "scan"
                if selected_backend != expected_backend:
                    raise RuntimeError(
                        f"backend mismatch: expected={expected_backend}, actual={selected_backend}"
                    )
                timings[backend].append(elapsed_ms)
                candidate_counts[backend].append(len(candidates))

    summaries: dict[str, dict[str, Any]] = {}
    for backend, values in timings.items():
        summaries[backend] = {
            "requests": len(values),
            "average_latency_ms": round(statistics.fmean(values), 3),
            "p50_latency_ms": round(_percentile(values, 0.50), 3),
            "p95_latency_ms": round(_percentile(values, 0.95), 3),
            "max_latency_ms": round(max(values), 3),
            "average_candidates": round(statistics.fmean(candidate_counts[backend]), 2),
            "max_candidates": max(candidate_counts[backend]),
        }

    scan_p95 = summaries["scan"]["p95_latency_ms"]
    bm25_p95 = summaries["milvus"]["p95_latency_ms"]
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset": (
            args.cases.resolve().relative_to(ROOT_DIR.resolve()).as_posix()
            if args.cases.resolve().is_relative_to(ROOT_DIR.resolve())
            else args.cases.name
        ),
        "case_count": len(cases),
        "iterations": args.iterations,
        "source_route": route.name,
        "source_model": route.model,
        "indexed_chunk_count": sum(collection_sizes.values()),
        "collection_sizes": collection_sizes,
        "backends": summaries,
        "p95_speedup": round(scan_p95 / bm25_p95, 3) if bm25_p95 else None,
        "passed": bm25_p95 < scan_p95,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
