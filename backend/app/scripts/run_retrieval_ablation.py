"""Run reproducible development-set retrieval ablations in isolated processes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCENARIOS = {
    "dense_single": {
        "RAG_HYBRID_ENABLED": "false",
        "RAG_MULTI_QUERY_ENABLED": "false",
        "RAG_NEIGHBOR_ENABLED": "false",
    },
    "dense_multi": {
        "RAG_HYBRID_ENABLED": "false",
        "RAG_MULTI_QUERY_ENABLED": "true",
        "RAG_NEIGHBOR_ENABLED": "false",
    },
    "hybrid_multi": {
        "RAG_HYBRID_ENABLED": "true",
        "RAG_MULTI_QUERY_ENABLED": "true",
        "RAG_NEIGHBOR_ENABLED": "false",
    },
    "hybrid_multi_neighbor": {
        "RAG_HYBRID_ENABLED": "true",
        "RAG_MULTI_QUERY_ENABLED": "true",
        "RAG_NEIGHBOR_ENABLED": "true",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--scenario", action="append", choices=SCENARIOS)
    args = parser.parse_args()

    selected = args.scenario or list(SCENARIOS)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    evaluator = Path(__file__).with_name("evaluate_rag_retrieval.py")
    aggregated: dict[str, dict] = {}
    execution_errors: list[dict[str, object]] = []

    for name in selected:
        output = args.output_dir / f"{name}.json"
        environment = os.environ.copy()
        environment.update(SCENARIOS[name])
        process = subprocess.run(
            [
                sys.executable,
                str(evaluator),
                "--cases",
                str(args.cases),
                "--top-k",
                str(args.top_k),
                "--output",
                str(output),
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        summary_line = next(
            (line for line in reversed(process.stdout.splitlines()) if line.startswith("summary:")),
            f"exit={process.returncode}",
        )
        print(f"{name}: {summary_line}")
        if not output.is_file():
            execution_errors.append({
                "scenario": name,
                "return_code": process.returncode,
                "stderr": process.stderr[-2000:],
            })
            continue
        payload = json.loads(output.read_text(encoding="utf-8"))
        aggregated[name] = {
            "configuration": SCENARIOS[name],
            "return_code": process.returncode,
            "summary": payload["summary"],
            "report": output.name,
        }

    baseline = aggregated.get(selected[0], {}).get("summary", {})
    for scenario in aggregated.values():
        summary = scenario["summary"]
        scenario["delta_vs_first"] = {
            "passed": summary.get("passed", 0) - baseline.get("passed", 0),
            "mrr": round(summary.get("mrr", 0) - baseline.get("mrr", 0), 6),
            "ndcg_at_k": round(
                summary.get("ndcg_at_k", 0) - baseline.get("ndcg_at_k", 0), 6
            ),
            "p95_latency_ms": round(
                summary.get("p95_latency_ms", 0) - baseline.get("p95_latency_ms", 0), 1
            ),
        }

    aggregate_report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataset": args.cases.as_posix(),
        "top_k": args.top_k,
        "first_scenario_is_baseline": selected[0],
        "note": (
            "hybrid scenarios use deterministic weighted dense/lexical/facet fusion; "
            "they do not use a cross-encoder reranker"
        ),
        "scenarios": aggregated,
        "execution_errors": execution_errors,
    }
    aggregate_path = args.output_dir / "summary.json"
    aggregate_path.write_text(
        json.dumps(aggregate_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"aggregate: {aggregate_path}")
    return 1 if execution_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
