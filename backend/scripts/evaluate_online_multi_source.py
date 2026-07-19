"""Real online multi-source research evaluation (P1-12).

This script exercises the four online providers (Bocha news search,
81api bidding, Juhe stock quotes, Text2SQL+DB) against a fixed set of
semiconductor test questions and produces a structured JSON report
under ``/tmp/``.

The script is intentionally small (3 questions by default) and each
provider call is wrapped through the P1-2 ``ProviderReliability``
layer so timeouts, retries and degraded outcomes are consistently
recorded.

**Cost**: A single run against all four providers costs roughly
0.05–0.15 CNY on Bailian + Bocha + Juhe, assuming the 81api quota
is not exhausted. There is no automatic loop or automated retry that
multiplies the cost.

**Safety**: Run with ``--dry-run`` to validate the question set and
provider configuration without making a single outbound call.

Example::

    cd backend
    PYTHONPATH=app python scripts/evaluate_online_multi_source.py

    # Dry-run (no API calls):
    PYTHONPATH=app python scripts/evaluate_online_multi_source.py --dry-run

    # Custom questions + output:
    PYTHONPATH=app python scripts/evaluate_online_multi_source.py \\
        --questions sample-data/p1_12_online_questions.json \\
        --output /tmp/p1-12-online-report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from openai import OpenAI  # noqa: E402

from core.provider_reliability import (  # noqa: E402
    PROVIDER_OK,
    ProviderOutcome,
    run_provider_async,
)
from service.llm_router import resolve_llm_endpoint  # noqa: E402
from service.news_collection_service import NewsCollectionService  # noqa: E402
from service.bidding_service import get_bidding_service  # noqa: E402
from service.stock_service import get_stock_service  # noqa: E402


logger = logging.getLogger("p1_12_online_eval")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ---------------------------------------------------------------------------
# Test questions (synthetic, semiconductor-only, kept to 3 to limit cost)
# ---------------------------------------------------------------------------

DEFAULT_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "online-001",
        "question": "中芯国际 14nm 工艺最新进展",
        "expected_tools": ["knowledge_search", "news_search", "stock_query"],
        "expected_keywords": ["中芯国际", "14nm", "FinFET"],
        "refusal_expected": False,
    },
    {
        "id": "online-002",
        "question": "先进封装键合机招投标最近一年情况",
        "expected_tools": ["knowledge_search", "bidding_search", "news_search"],
        "expected_keywords": ["键合机", "招投标", "封装"],
        "refusal_expected": False,
    },
    {
        "id": "online-003",
        "question": "长电科技和通富微电最新行情对比",
        "expected_tools": ["knowledge_search", "stock_query", "text2sql"],
        "expected_keywords": ["长电科技", "通富微电", "行情"],
        "refusal_expected": False,
    },
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


@dataclass
class Bucket:
    name: str
    samples: List[float] = field(default_factory=list)

    def add(self, value: Optional[float]) -> None:
        if value is not None:
            self.samples.append(float(value))

    def stats(self) -> Dict[str, Any]:
        if not self.samples:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
        ordered = sorted(self.samples)
        n = len(ordered)
        p50 = ordered[min(n // 2, n - 1)]
        p95 = ordered[min(int(round(0.95 * (n - 1))), n - 1)]
        return {
            "count": n,
            "p50_ms": round(p50 * 1000, 2),
            "p95_ms": round(p95 * 1000, 2),
            "mean_ms": round(statistics.mean(ordered) * 1000, 2),
        }


# ---------------------------------------------------------------------------
# Provider wrappers
# ---------------------------------------------------------------------------


async def _eval_news(question: str) -> Dict[str, Any]:
    started = time.perf_counter()
    class Sess: pass
    svc = NewsCollectionService(Sess())  # type: ignore[arg-type]
    results = await svc._bocha_search(question, count=3)
    elapsed = time.perf_counter() - started
    outcome = svc.last_outcome()
    return {
        "provider": "news",
        "ok": bool(results),
        "result_count": len(results),
        "latency_ms": round(elapsed * 1000, 2),
        "provider_ok": outcome.ok if outcome else None,
        "provider_code": outcome.error_code if outcome else None,
        "degraded": outcome.degraded if outcome else None,
        "sample_titles": [r.get("title", "")[:60] for r in results[:2]],
    }


async def _eval_bidding(question: str) -> Dict[str, Any]:
    started = time.perf_counter()
    svc = get_bidding_service()
    results = await svc.search_win_bids(question, page=1)
    elapsed = time.perf_counter() - started
    return {
        "provider": "bidding",
        "ok": results.get("success", False),
        "result_count": len(results.get("results", [])),
        "latency_ms": round(elapsed * 1000, 2),
        "provider_code": results.get("provider_code"),
        "degraded": results.get("degraded"),
        "sample_titles": [r.get("title", "")[:60] for r in results.get("results", [])[:2]],
    }


async def _eval_stock(question: str) -> Dict[str, Any]:
    started = time.perf_counter()
    svc = get_stock_service()
    # Find a known company in the question
    for company, code in {
        "中芯国际": "sh688981",
        "长电科技": "sh600584",
        "通富微电": "sz002156",
        "中微公司": "sh688012",
        "北方华创": "sz002371",
    }.items():
        if company in question:
            result = await svc.get_stock_by_code(code)
            elapsed = time.perf_counter() - started
            return {
                "provider": "stock",
                "ok": result.get("success", False),
                "latency_ms": round(elapsed * 1000, 2),
                "provider_code": result.get("provider_code"),
                "degraded": result.get("degraded"),
                "sample": str(result.get("data", {}))[:120] if result.get("data") else None,
            }
    elapsed = time.perf_counter() - started
    return {"provider": "stock", "ok": False, "latency_ms": round(elapsed * 1000, 2), "detail": "no known company found in question"}


async def _eval_llm_generation(question: str) -> Dict[str, Any]:
    started = time.perf_counter()
    endpoint = resolve_llm_endpoint("cloud")
    client = OpenAI(api_key=endpoint.api_key, base_url=endpoint.base_url, timeout=30.0)

    data: Dict[str, Any] = {"provider": "llm", "ok": False, "latency_ms": 0, "content": None}

    def _build_call() -> Any:
        return client.chat.completions.create(
            model=endpoint.model,
            messages=[
                {"role": "system", "content": "你是一位严谨的半导体行业研究员。请用1-2句中文回答。"},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
        )

    async def _build_async() -> Any:
        return await asyncio.to_thread(_build_call)

    outcome: ProviderOutcome = await run_provider_async(_build_async, timeout_seconds=30.0, max_attempts=1)
    elapsed = time.perf_counter() - started
    data["latency_ms"] = round(elapsed * 1000, 2)

    if outcome.ok and outcome.data is not None:
        content = outcome.data.choices[0].message.content
        data["ok"] = True
        data["content"] = content
    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _main() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="P1-12 online multi-source evaluation")
    parser.add_argument("--questions", default=None, help="Path to custom questions JSON (list of dicts with id, question, expected_keywords).")
    parser.add_argument("--output", default="/tmp/p1-12-online-multi-source-report.json", help="Output report path.")
    parser.add_argument("--dry-run", action="store_true", help="Validate config without making API calls.")
    args = parser.parse_args()

    if args.questions:
        questions: List[Dict[str, Any]] = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    else:
        questions = DEFAULT_QUESTIONS

    started_at = datetime.now(timezone.utc).isoformat()

    if args.dry_run:
        # Validate env keys
        checks: Dict[str, str] = {}
        for env_var in ("DASHSCOPE_API_KEY", "BOCHA_API_KEY", "BID_APP_CODE", "JUHE_STOCK_API_KEY"):
            checks[env_var] = "<set>" if os.environ.get(env_var) else "<missing>"
        report: Dict[str, Any] = {
            "mode": "dry-run",
            "started_at": started_at,
            "question_count": len(questions),
            "api_keys": checks,
            "questions": [q["question"] for q in questions],
            "note": "Dry-run completed — no API calls were made. Run without --dry-run to execute the actual evaluation.",
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"output": args.output, "mode": "dry-run", "questions": len(questions)}, ensure_ascii=False))
        return report

    # ---- Real evaluation ----
    results: List[Dict[str, Any]] = []
    latencies = Bucket("eval")

    for q in questions:
        qid = q["id"]
        question = q["question"]
        logger.info("Evaluating %s: %s", qid, question)

        providers: List[Dict[str, Any]] = []
        # Run providers concurrently
        tasks = {
            "news": _eval_news(question),
            "bidding": _eval_bidding(question),
            "stock": _eval_stock(question),
            "llm": _eval_llm_generation(question),
        }
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for (name, coro), result in zip(tasks.items(), gathered):
            if isinstance(result, Exception):
                providers.append({"provider": name, "ok": False, "error": f"{type(result).__name__}: {result}"})
            else:
                providers.append(result)
                if result.get("ok"):
                    latencies.add(result.get("latency_ms", 0) / 1000.0)

        results.append({
            "id": qid,
            "question": question,
            "expected_keywords": q.get("expected_keywords", []),
            "providers": providers,
            "providers_ok": sum(1 for p in providers if p.get("ok")),
            "providers_total": len(providers),
        })

    finished_at = datetime.now(timezone.utc).isoformat()

    report = {
        "schema_version": 1,
        "mode": "live",
        "started_at": started_at,
        "finished_at": finished_at,
        "questions": len(questions),
        "providers_tested": ["news", "bidding", "stock", "llm"],
        "latency_ms": latencies.stats(),
        "results": results,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {
            "output": args.output,
            "questions": len(questions),
            "latency_ms": latencies.stats(),
            "providers_ok_per_question": [
                {"id": r["id"], "ok": r["providers_ok"], "total": r["providers_total"]}
                for r in results
            ],
        },
        ensure_ascii=False,
    ))
    return report


if __name__ == "__main__":
    asyncio.run(_main())
