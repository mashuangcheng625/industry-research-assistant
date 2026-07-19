"""P1-11 blind-v2 offline evaluation.

Runs the blind-v2 question set against the cloud LLM and RAG pipeline
WITHOUT requiring a running API server. Each question is answered by:

1. Retrieving relevant document chunks from the Milvus knowledge base
2. Sending the question + evidence to the cloud LLM (Bailian)
3. Checking the answer against the pre-baked answer key for keyword
   presence and refusal behaviour

The answer key (private) is read from
``data/evaluation-private/semiconductor_rag_eval_blind_v2_answers.json``.

The report is written to ``/tmp/`` so it never enters the public repo.

Cost: ~25 LLM calls + ~25 embedding calls. Total < 0.5 CNY.

Example:
    cd backend
    PYTHONPATH=app python scripts/evaluate_blind_v2.py
    PYTHONPATH=app python scripts/evaluate_blind_v2.py --dry-run  # no API calls
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

APP_DIR = Path(__file__).resolve().parents[1] / "app"
BACKEND_DIR = APP_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# Load .env from backend/ so DASHSCOPE_API_KEY etc. are available
from dotenv import load_dotenv
_dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_dotenv_path)

# pymilvus Config rejects file paths at import time — clear the env
# var before any `import pymilvus` happens, then set it back inside
# the function that actually connects.
_previous_milvus_uri = os.environ.pop("MILVUS_URI", None)

from openai import OpenAI  # noqa: E402

_MILVUS_LITE_PATH = (
    _previous_milvus_uri
    or os.environ.get("MILVUS_LITE_DB", "/tmp/industry-research-milvus.db")
)
from core.provider_reliability import run_provider_async  # noqa: E402
from service.retrieval_service import retrieve_from_knowledge_base  # noqa: E402


ALL_KNOWLEDGE_BASES = (
    "semiconductor_chip_design_eda_ip",
    "semiconductor_materials_equipment",
    "semiconductor_process",
    "semiconductor_packaging_testing",
)


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _ask_llm(client: OpenAI, model: str, question: str, evidence: str) -> Dict[str, Any]:
    """Send a single question + evidence to the LLM and return the answer."""

    if evidence and evidence != "(直接回答，无检索证据)":
        prompt = f"""你是一位严谨的半导体行业研究员。根据以下证据回答问题。
如果证据不足，请明确说"当前知识库未检索到足够相关的资料"。

证据:
{evidence[:3000]}

问题: {question}

请用1-3句中文回答。"""
    else:
        prompt = f"""你是一位严谨的半导体行业研究员。请根据你的知识回答问题。
如果你不知道答案，请明确说"我无法回答这个问题"。

问题: {question}

请用1-3句中文回答。"""

    def _call() -> Any:
        return client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )

    async def _async_call() -> Any:
        return await asyncio.to_thread(_call)

    outcome = await run_provider_async(_async_call, timeout_seconds=60, max_attempts=1)
    if outcome.ok and outcome.data is not None:
        content = outcome.data.choices[0].message.content or ""
        return {"ok": True, "content": content, "latency_ms": 0}
    return {"ok": False, "content": None, "error": outcome.last_error}


async def _retrieve_evidence(
    knowledge_base: str,
    query: str,
    *,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Run production retrieval and return evidence plus diagnostics."""
    # Set the file URI now that pymilvus imports are past.
    if _MILVUS_LITE_PATH:
        os.environ["MILVUS_URI"] = _MILVUS_LITE_PATH
    try:
        targets = ALL_KNOWLEDGE_BASES if knowledge_base == "all" else (knowledge_base,)
        collected: list[Dict[str, Any]] = []
        for target in targets:
            items = retrieve_from_knowledge_base(
                kb_name=target,
                question=query,
                top_k=top_k,
                min_score=0.0,
            )
            for item in items:
                if not isinstance(item, dict):
                    continue
                collected.append({**item, "knowledge_base": target})

        # Cross-domain cases can return the same chunk through more than one
        # path. Preserve the best score while keeping the evaluation input
        # independent of the private answer key.
        deduplicated: dict[str, Dict[str, Any]] = {}
        for item in collected:
            key = str(
                item.get("chunk_id")
                or f"{item.get('document_id', '')}:{item.get('chunk_index', '')}"
            )
            existing = deduplicated.get(key)
            if existing is None or float(item.get("score", 0)) > float(
                existing.get("score", 0)
            ):
                deduplicated[key] = item
        ranked = sorted(
            deduplicated.values(),
            key=lambda item: float(item.get("score", 0)),
            reverse=True,
        )[:top_k]
        parts = []
        diagnostics = []
        for index, item in enumerate(ranked, start=1):
            content = str(
                item.get("content_with_weight")
                or item.get("content")
                or item.get("text")
                or ""
            ).strip()
            if not content:
                continue
            document_name = str(item.get("document_name") or item.get("filename") or "N/A")
            chunk_index = item.get("chunk_index")
            parts.append(
                f"[{index}] {document_name} chunk={chunk_index}\n{content[:1200]}"
            )
            diagnostics.append({
                "document_name": document_name,
                "chunk_index": chunk_index,
                "score": round(float(item.get("score", 0)), 6),
                "retrieval_routes": item.get("retrieval_routes", []),
                "knowledge_base": item.get("knowledge_base"),
            })
        return {
            "ok": True,
            "evidence": "\n\n".join(parts),
            "items": diagnostics,
            "target_knowledge_bases": list(targets),
            "error": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "evidence": "",
            "items": [],
            "target_knowledge_bases": [],
            "error": f"{type(e).__name__}: {e}",
        }


def _check_refusal(answer: str) -> bool:
    """Heuristic: does the answer look like a refusal?"""
    refusal_hints = [
        "未检索到", "无法回答", "证据不足", "信息不足",
        "没有找到", "暂无", "未找到相关", "不包含",
    ]
    return any(hint in answer for hint in refusal_hints)


def _check_keywords(answer: str, keywords: List[str]) -> Dict[str, Any]:
    """Count how many expected keywords appear in the answer."""
    lower = answer.lower()
    if not keywords:
        return {"total": 0, "found": [], "missing": [], "coverage": None}
    found = [k for k in keywords if k.lower() in lower]
    return {
        "total": len(keywords),
        "found": found,
        "missing": [k for k in keywords if k not in found],
        "coverage": len(found) / len(keywords) if keywords else None,
    }


def _expected_source_names(question: Dict[str, Any]) -> List[str]:
    """Extract public gold document names without reading the private labels."""
    source = str(question.get("source_document") or "")
    if source == "无":
        return []
    return list(dict.fromkeys(re.findall(r"[\w.-]+\.md", source)))


def _source_retrieval_metrics(
    question: Dict[str, Any],
    retrieved_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    expected = _expected_source_names(question)
    retrieved = list(dict.fromkeys(
        str(item.get("document_name") or "")
        for item in retrieved_items
        if item.get("document_name")
    ))
    ranks = {
        name: next(
            (index for index, item in enumerate(retrieved_items, start=1)
             if item.get("document_name") == name),
            None,
        )
        for name in expected
    }
    matched = [name for name in expected if ranks[name] is not None]
    return {
        "expected_documents": expected,
        "retrieved_documents": retrieved,
        "matched_documents": matched,
        "hit": bool(matched) if expected else None,
        "first_hit_rank": min(
            (rank for rank in ranks.values() if rank is not None),
            default=None,
        ),
    }


def _initialise_milvus_lite() -> None:
    """Create the shared service only after pymilvus imported with an empty URI."""
    if not _MILVUS_LITE_PATH:
        raise RuntimeError("MILVUS_LITE_DB is not configured")
    # WSL may inherit a Windows TEMP directory that cannot host Unix sockets.
    tempfile.tempdir = os.getenv("MILVUS_LITE_TEMP_DIR", "/tmp")
    os.environ["MILVUS_URI"] = _MILVUS_LITE_PATH
    from pymilvus import connections
    from service import milvus_service as milvus_module

    connections.disconnect("default")
    milvus_module._milvus_service = milvus_module.MilvusService()


async def _main() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="Blind-v2 offline evaluation")
    parser.add_argument(
        "--questions",
        type=Path,
        default=ROOT_DIR / "sample-data/semiconductor_rag_eval_blind_v2.json",
    )
    parser.add_argument(
        "--answers",
        type=Path,
        default=(
            ROOT_DIR
            / "data/evaluation-private/semiconductor_rag_eval_blind_v2_answers.json"
        ),
    )
    parser.add_argument("--output", default="/tmp/blind-v2-eval-report.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-retrieval", action="store_true", help="Test LLM knowledge without RAG retrieval")
    parser.add_argument("--limit", type=int, default=0, help="Number of questions to evaluate (0=all)")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    questions = _load_json(args.questions)
    answer_key = _load_json(args.answers)
    answers_by_id = {c["id"]: c for c in answer_key["cases"]}

    if args.dry_run:
        print(json.dumps({
            "mode": "dry-run",
            "question_count": len(questions),
            "answer_key_count": len(answer_key["cases"]),
            "matched": sum(1 for q in questions if q["id"] in answers_by_id),
        }, ensure_ascii=False))
        return {}

    # Cloud client
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("CLOUD_LLM_API_KEY", "")
    base_url = os.environ.get("DASHSCOPE_BASE_URL", os.environ.get("CLOUD_LLM_BASE_URL", ""))
    model = os.environ.get("CLOUD_LLM_MODEL", "deepseek-v4-flash")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)

    # The real-embedding rebuild creates the cloud route-qualified
    # collections. Keep the evaluation deterministic and independent of local
    # Ollama availability.
    os.environ["EMBEDDING_ROUTING_MODE"] = "cloud"
    if not args.no_retrieval:
        _initialise_milvus_lite()

    subset = questions[: args.limit] if args.limit else questions
    started_at = datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []

    for i, q in enumerate(subset):
        qid = q["id"]
        answer = answers_by_id.get(qid)
        if answer is None:
            results.append({"id": qid, "error": "no answer key entry"})
            continue

        print(f"[{i+1}/{len(subset)}] {qid}: {q['question'][:40]}...", end=" ", flush=True)

        # Retrieve (skipped in --no-retrieval mode)
        t0 = time.perf_counter()
        if args.no_retrieval:
            evidence = "(直接回答，无检索证据)"
            retrieval = {
                "ok": True,
                "items": [],
                "target_knowledge_bases": [],
                "error": None,
            }
            t_retrieve = 0
        else:
            retrieval = await _retrieve_evidence(
                q.get("knowledge_base", "all"),
                q["question"],
                top_k=args.top_k,
            )
            evidence = str(retrieval["evidence"])
            t_retrieve = time.perf_counter() - t0

        # Generate
        if not retrieval["ok"]:
            llm_result = {
                "ok": False,
                "content": None,
                "error": retrieval["error"],
            }
        elif not args.no_retrieval and not evidence:
            llm_result = {
                "ok": True,
                "content": "当前知识库未检索到足够相关的资料。",
                "deterministic_refusal": True,
            }
        else:
            llm_result = await _ask_llm(client, model, q["question"], evidence)
        t_total = time.perf_counter() - t0

        content = llm_result.get("content") or ""
        is_refusal = _check_refusal(content)
        expected_refusal = answer.get("refusal_expected", False)
        kw = _check_keywords(content, answer.get("expected_keywords", []))
        source_retrieval = _source_retrieval_metrics(q, retrieval["items"])

        # Scoring
        if not retrieval["ok"] or not llm_result.get("ok"):
            score = 0.0
            verdict = "fail_pipeline"
        elif expected_refusal:
            score = 1.0 if is_refusal else 0.0
            verdict = "pass" if is_refusal else "fail_refusal_missed"
        else:
            cov = kw["coverage"] or 0.0
            score = min(1.0, cov * 1.2)  # 80% keyword coverage = full score
            verdict = "pass" if score >= 0.6 else "fail_keywords"

        r = {
            "id": qid,
            "question": q["question"],
            "expected_refusal": expected_refusal,
            "actual_refusal": is_refusal,
            "keywords": kw,
            "score": round(score, 2),
            "verdict": verdict,
            "retrieve_latency_ms": round(t_retrieve * 1000, 2),
            "total_latency_ms": round(t_total * 1000, 2),
            "answer_preview": content[:200] if content else None,
            "retrieval_ok": retrieval["ok"],
            "retrieval_error": retrieval["error"],
            "retrieved_items": retrieval["items"],
            "target_knowledge_bases": retrieval["target_knowledge_bases"],
            "source_retrieval": source_retrieval,
        }
        results.append(r)
        print(f"verdict={verdict} score={score:.2f}")

    finished_at = datetime.now(timezone.utc).isoformat()
    passed = sum(1 for r in results if r["verdict"] == "pass")
    positive_results = [
        result
        for result in results
        if result.get("source_retrieval", {}).get("expected_documents")
    ]
    source_hits = sum(
        result["source_retrieval"]["hit"] is True for result in positive_results
    )
    report = {
        "schema_version": 1,
        "started_at": started_at,
        "finished_at": finished_at,
        "total": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 3) if results else None,
        "source_retrieval_at_k": {
            "k": args.top_k,
            "hits": source_hits,
            "total": len(positive_results),
            "hit_rate": (
                round(source_hits / len(positive_results), 3)
                if positive_results else None
            ),
        },
        "results": results,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. {passed}/{len(results)} passed. Report: {args.output}")
    return report


if __name__ == "__main__":
    asyncio.run(_main())
