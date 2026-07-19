"""P1-5 model smoke test (opt-in live).

Runs a fixed sample of generation, embedding, rerank and
hybrid-retrieval tasks against the cloud (Bailian) and the local
Ollama providers. Captures latency / token / cost metrics and emits
a single JSON report under ``reports/`` for offline review.

Run on a dev machine with ``DASHSCOPE_API_KEY`` set and Ollama
running locally. The cloud calls consume a small but real amount of
API quota; the local calls are free. The default invocation performs
roughly:

* 5 cloud + 5 local generation calls;
* 20 cloud + 20 local embedding calls;
* 5 cloud rerank calls;
* 10 LLM-judge calls (one per generation output);
* 5 hybrid retrieval cycles against Milvus Lite (no LLM cost).

The script deliberately keeps the sample small so the run finishes in
under 90 seconds and the cumulative spend stays under 0.5 CNY on
Bailian.

The script never hard-fails on a single provider error. Each
provider's failures are recorded under ``provider_failures`` in the
output so the user can re-run after fixing the local environment
without re-paying for the cloud half.

Examples:

    # full run (cloud + local)
    python scripts/p1_5_model_smoke.py

    # cloud-only (faster, cheaper)
    python scripts/p1_5_model_smoke.py --skip-local

    # custom sample + output
    python scripts/p1_5_model_smoke.py \\
        --inputs sample-data/p1_5_model_smoke_inputs.json \\
        --output reports/p1-5-model-smoke.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import logging
import os
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# Local application imports. ``backend/app`` must be on sys.path.
APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from openai import OpenAI  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# Load the repository's ignored runtime configuration without requiring the
# caller to source it in the shell. The report never serializes API keys.
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

from core.provider_reliability import (  # noqa: E402
    PROVIDER_OK,
    PROVIDER_TIMEOUT,
    PROVIDER_UNKNOWN,
    run_provider_async,
    ProviderOutcome,
)
from service.llm_router import (  # noqa: E402
    LLMEndpoint,
    resolve_llm_endpoint,
)


logger = logging.getLogger("p1_5_smoke")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


@dataclass
class Bucket:
    name: str
    samples: List[float] = field(default_factory=list)

    def add(self, value: Optional[float]) -> None:
        if value is None:
            return
        self.samples.append(float(value))

    def stats(self) -> Dict[str, Any]:
        if not self.samples:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
        ordered = sorted(self.samples)
        n = len(ordered)
        p50 = ordered[min(n // 2, n - 1)]
        p95_index = min(int(round(0.95 * (n - 1))), n - 1)
        p95 = ordered[p95_index]
        return {
            "count": n,
            "p50_ms": round(p50 * 1000, 2),
            "p95_ms": round(p95 * 1000, 2),
            "mean_ms": round(statistics.mean(ordered) * 1000, 2),
            "min_ms": round(ordered[0] * 1000, 2),
            "max_ms": round(ordered[-1] * 1000, 2),
        }


def _endpoint_dict(endpoint: LLMEndpoint) -> Dict[str, str]:
    """Return a safe dict for the report (no API keys)."""

    return {
        "mode": endpoint.mode,
        "provider": endpoint.provider,
        "base_url": endpoint.base_url,
        "model": endpoint.model,
    }


# ---------------------------------------------------------------------------
# Generation smoke
# ---------------------------------------------------------------------------


async def _run_generation(
    endpoint: LLMEndpoint,
    prompt: Dict[str, str],
    *,
    task_id: str,
    provider_label: str,
) -> Dict[str, Any]:
    """Call the LLM via :func:`run_provider_async` so the smoke test
    shares the P1-2 reliability contract with the rest of the
    codebase.
    """

    started = time.perf_counter()
    client = OpenAI(api_key=endpoint.api_key, base_url=endpoint.base_url, timeout=30.0)

    def _build_call() -> Any:
        return client.chat.completions.create(
            model=endpoint.model,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            temperature=0.0,
        )

    async def _build_async() -> Any:
        return await asyncio.to_thread(_build_call)

    outcome: ProviderOutcome = await run_provider_async(
        _build_async,
        timeout_seconds=30.0,
        max_attempts=1,
        backoff_seconds=0.0,
    )
    elapsed = time.perf_counter() - started

    record: Dict[str, Any] = {
        "task_id": task_id,
        "provider": provider_label,
        "ok": outcome.ok,
        "error_code": outcome.error_code,
        "latency_ms": round(elapsed * 1000, 2),
        "attempts": outcome.attempts,
        "last_error": outcome.last_error,
        "content": None,
        "content_length": 0,
        "tokens": None,
    }
    if outcome.ok and outcome.data is not None:
        try:
            record["content"] = outcome.data.choices[0].message.content
        except (AttributeError, IndexError, KeyError):
            record["content"] = None
        record["content_length"] = len(record["content"] or "")
        usage = getattr(outcome.data, "usage", None)
        if usage is not None:
            record["tokens"] = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
    return record


async def _run_judge(
    endpoint: LLMEndpoint,
    *,
    task_id: str,
    user_prompt: str,
    candidate: str,
    expected_keywords: Sequence[str],
    provider_label: str,
    rubric: str,
) -> Dict[str, Any]:
    """Score ``candidate`` against ``user_prompt`` / expected keywords.

    The judge uses the cloud ``deepseek-v4-flash`` to keep scoring
    consistent across the smoke test.
    """

    keyword_list = "、".join(expected_keywords) if expected_keywords else "（无）"
    judge_prompt = (
        "你是一位严苛的半导体行业评审员,按以下评分细则给候选答案打分,只输出 1-5 之间的整数:\n"
        f"{rubric}\n\n"
        f"问题: {user_prompt}\n"
        f"期望关键词: {keyword_list}\n"
        f"候选答案: {candidate}\n\n"
        "请只输出 1-5 之间的整数:"
    )
    started = time.perf_counter()
    client = OpenAI(api_key=endpoint.api_key, base_url=endpoint.base_url, timeout=20.0)

    def _build_call() -> Any:
        return client.chat.completions.create(
            model=endpoint.model,
            messages=[
                {"role": "system", "content": "你只输出 1-5 之间的整数,不要解释。"},
                {"role": "user", "content": judge_prompt},
            ],
            temperature=0.0,
        )

    async def _build_async() -> Any:
        return await asyncio.to_thread(_build_call)

    outcome: ProviderOutcome = await run_provider_async(
        _build_async,
        timeout_seconds=20.0,
        max_attempts=1,
        backoff_seconds=0.0,
    )
    elapsed = time.perf_counter() - started
    score: Optional[int] = None
    raw_content: Optional[str] = None
    if outcome.ok and outcome.data is not None:
        try:
            raw_content = (outcome.data.choices[0].message.content or "").strip()
        except (AttributeError, IndexError):
            raw_content = None
        if raw_content is not None:
            digits = "".join(ch for ch in raw_content if ch.isdigit())
            if digits:
                try:
                    score = int(digits[0])
                    score = max(1, min(5, score))
                except ValueError:
                    score = None
    return {
        "task_id": task_id,
        "provider": provider_label,
        "ok": outcome.ok,
        "score": score,
        "raw": raw_content,
        "latency_ms": round(elapsed * 1000, 2),
        "error_code": outcome.error_code if not outcome.ok else None,
    }


# ---------------------------------------------------------------------------
# Embedding smoke
# ---------------------------------------------------------------------------


async def _embed(
    text: str,
    *,
    api_key: str,
    base_url: str,
    model_name: str,
    dim: int,
    provider_label: str,
) -> Dict[str, Any]:
    started = time.perf_counter()
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=20.0)

    def _build_call() -> Any:
        return client.embeddings.create(
            model=model_name,
            input=text,
            dimensions=dim,
            encoding_format="float",
        )

    async def _build_async() -> Any:
        return await asyncio.to_thread(_build_call)

    outcome: ProviderOutcome = await run_provider_async(
        _build_async,
        timeout_seconds=20.0,
        max_attempts=1,
        backoff_seconds=0.0,
    )
    elapsed = time.perf_counter() - started
    record: Dict[str, Any] = {
        "provider": provider_label,
        "ok": outcome.ok,
        "error_code": outcome.error_code,
        "last_error": outcome.last_error,
        "latency_ms": round(elapsed * 1000, 2),
        "vector_dim": None,
        "vector_norm": None,
    }
    if outcome.ok and outcome.data is not None:
        items = getattr(outcome.data, "data", None) or []
        if items:
            first = items[0]
            vec = getattr(first, "embedding", None) or []
            if isinstance(vec, list):
                record["_vector"] = list(vec)
                record["vector_dim"] = len(vec)
                if vec:
                    record["vector_norm"] = round(
                        sum(x * x for x in vec) ** 0.5, 4
                    )
    return record


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    den_a = sum(x * x for x in a) ** 0.5
    den_b = sum(y * y for y in b) ** 0.5
    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)


# ---------------------------------------------------------------------------
# Rerank smoke
# ---------------------------------------------------------------------------


async def _rerank(
    *,
    query: str,
    documents: Sequence[str],
    api_key: str,
    base_url: str,
    model_name: str,
    provider_label: str,
) -> Dict[str, Any]:
    started = time.perf_counter()
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)

    def _build_call() -> Any:
        return client.post(
            "/reranks",
            body={
                "model": model_name,
                "query": query,
                "documents": list(documents),
                "top_n": len(documents),
                "instruct": os.environ.get(
                    "RERANK_INSTRUCT",
                    "Given a web search query, retrieve relevant passages that answer the query.",
                ),
            },
            cast_to=object,
        )

    async def _build_async() -> Any:
        return await asyncio.to_thread(_build_call)

    outcome: ProviderOutcome = await run_provider_async(
        _build_async,
        timeout_seconds=30.0,
        max_attempts=1,
        backoff_seconds=0.0,
    )
    elapsed = time.perf_counter() - started
    record: Dict[str, Any] = {
        "provider": provider_label,
        "ok": outcome.ok,
        "error_code": outcome.error_code,
        "last_error": outcome.last_error,
        "latency_ms": round(elapsed * 1000, 2),
        "ranking": None,
    }
    if outcome.ok and outcome.data is not None:
        payload = (
            outcome.data
            if isinstance(outcome.data, dict)
            else getattr(outcome.data, "__dict__", None) or {}
        )
        results = payload.get("results")
        if isinstance(results, list):
            record["ranking"] = [
                {
                    "index": int(item.get("index")),
                    "score": float(item.get("relevance_score", 0.0)),
                }
                for item in results
                if isinstance(item, dict)
            ]
    return record


def _ndcg(ranking: Optional[List[Dict[str, Any]]], relevant: List[int], k: int) -> Optional[float]:
    """Compute nDCG@k against a binary relevance vector.

    ``ranking`` is the model's output (a list of ``{"index", "score"}``
    dicts sorted by score descending). ``relevant`` is the list of
    ground-truth relevant document indices.
    """

    if not ranking or not relevant:
        return None
    rel_set = set(relevant)
    # DCG@k
    dcg = 0.0
    for rank, item in enumerate(ranking[:k], start=1):
        idx = int(item.get("index"))
        gain = 1.0 if idx in rel_set else 0.0
        dcg += gain / (1.0 if rank == 1 else math.log2(rank + 1))
    # iDCG@k
    ideal = min(len(relevant), k)
    if ideal == 0:
        return 0.0
    idcg = 0.0
    for rank in range(1, ideal + 1):
        idcg += 1.0 / (1.0 if rank == 1 else math.log2(rank + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


# ---------------------------------------------------------------------------
# Hybrid retrieval
# ---------------------------------------------------------------------------


def _hybrid_retrieval(
    *,
    knowledge_base: str,
    query: str,
    top_k: int,
    expected_document_ids: Sequence[str],
) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        from service.retrieval_service import retrieve_from_knowledge_base
        items = retrieve_from_knowledge_base(
            kb_name=knowledge_base,
            question=query,
            top_k=top_k,
            min_score=0.0,
        )
        elapsed = time.perf_counter() - started
        expected = {str(item) for item in expected_document_ids}
        returned_ids = [str(item.get("document_id", "")) for item in items]
        route_coverage = sorted({
            str(route)
            for item in items
            for route in item.get("retrieval_routes", [])
        })
        gold_hit = bool(expected & set(returned_ids))
        dual_route_hit = any(
            set(item.get("retrieval_routes", [])) == {"cloud", "local"}
            and str(item.get("document_id", "")) in expected
            for item in items
        )
        degraded_routes = sorted({
            str(route)
            for item in items
            for route in (item.get("degraded_route") or [])
        })
        ok = bool(items) and gold_hit and dual_route_hit and not degraded_routes
        return {
            "ok": ok,
            "latency_ms": round(elapsed * 1000, 2),
            "count": len(items),
            "first_score": items[0].get("score") if items else None,
            "expected_document_ids": sorted(expected),
            "returned_document_ids": returned_ids,
            "route_coverage": route_coverage,
            "gold_hit": gold_hit,
            "dual_route_hit": dual_route_hit,
            "degraded_routes": degraded_routes,
            "error": None if ok else "Hybrid retrieval contract was not satisfied",
        }
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        return {
            "ok": False,
            "latency_ms": round(elapsed * 1000, 2),
            "count": 0,
            "first_score": None,
            "expected_document_ids": sorted(str(item) for item in expected_document_ids),
            "returned_document_ids": [],
            "route_coverage": [],
            "gold_hit": False,
            "dual_route_hit": False,
            "degraded_routes": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_hybrid_benchmark(
    *,
    cases: Sequence[Dict[str, Any]],
    corpus: Sequence[str],
    cloud_vectors: Sequence[Sequence[float]],
    local_vectors: Sequence[Sequence[float]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Build isolated dual indexes in Milvus Lite and execute real Hybrid retrieval."""
    if not cases:
        raise ValueError("hybrid_cases must not be empty")
    if not (len(corpus) == len(cloud_vectors) == len(local_vectors)):
        raise ValueError(
            "Hybrid corpus and cloud/local vector counts must match: "
            f"corpus={len(corpus)}, cloud={len(cloud_vectors)}, local={len(local_vectors)}"
        )

    from pymilvus import connections
    from service import milvus_service as milvus_module
    from service.embedding_router import collection_name_for_route, get_embedding_route
    from service.milvus_service import MilvusService

    managed_keys = {
        "MILVUS_URI": None,
        "EMBEDDING_ROUTING_MODE": "hybrid",
        "RAG_HYBRID_ENABLED": "false",
        "RAG_MULTI_QUERY_ENABLED": "false",
        "RAG_NEIGHBOR_ENABLED": "false",
        "RAG_MIN_SCORE": "0",
        "RAG_MIN_LEXICAL_SCORE": "0",
        "HYBRID_CLOUD_TOP_K": str(max(top_k, 5)),
        "HYBRID_LOCAL_TOP_K": str(max(top_k, 5)),
        "HYBRID_RERANK_TOP_K": str(max(top_k, 5)),
        "RERANK_ENABLED": "true",
    }
    previous_env = {key: os.environ.get(key) for key in managed_keys}
    previous_service = milvus_module._milvus_service
    previous_tempdir = tempfile.tempdir
    records: List[Dict[str, Any]] = []

    tempfile.tempdir = "/tmp"
    try:
        with tempfile.TemporaryDirectory(prefix="p1-5-hybrid-", dir="/tmp") as temp_dir:
            managed_keys["MILVUS_URI"] = str(Path(temp_dir) / "hybrid.db")
            connections.disconnect("default")
            for key, value in managed_keys.items():
                os.environ[key] = str(value)

            service = MilvusService()
            milvus_module._milvus_service = service
            knowledge_base = "p1_5_smoke"
            collection_base = f"kb_{knowledge_base}"

            for route_name, vectors in (
                ("cloud", cloud_vectors),
                ("local", local_vectors),
            ):
                route = get_embedding_route(route_name)  # type: ignore[arg-type]
                collection_name = collection_name_for_route(collection_base, route)
                documents = []
                for index, (content, vector) in enumerate(zip(corpus, vectors)):
                    doc_id = f"smoke-doc-{index:03d}"
                    documents.append({
                        "id": doc_id,
                        "doc_id": doc_id,
                        "kb_id": knowledge_base,
                        "filename": f"{doc_id}.md",
                        "content": str(content),
                        "chunk_index": 0,
                        "content_hash": "",
                        "embedding_provider": route.provider,
                        "embedding_model": route.model,
                        "embedding_version": route.version,
                        "vector": list(vector),
                    })
                service.insert_documents(collection_name, documents)

            try:
                for case in cases:
                    record = _hybrid_retrieval(
                        knowledge_base=knowledge_base,
                        query=str(case["query"]),
                        top_k=top_k,
                        expected_document_ids=case.get("expected_document_ids", []),
                    )
                    record["task_id"] = str(case["id"])
                    records.append(record)
            finally:
                connections.disconnect("default")
    finally:
        tempfile.tempdir = previous_tempdir
        milvus_module._milvus_service = previous_service
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return records


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _main() -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description="P1-5 model smoke test")
    parser.add_argument(
        "--inputs",
        default="sample-data/p1_5_model_smoke_inputs.json",
        help="Path to the smoke test input JSON.",
    )
    parser.add_argument(
        "--output",
        default="reports/p1-5-model-smoke.json",
        help="Path to write the JSON report.",
    )
    parser.add_argument(
        "--hybrid-top-k",
        type=int,
        default=5,
        help="Top-k for the hybrid retrieval step.",
    )
    parser.add_argument(
        "--skip-local",
        action="store_true",
        help="Skip the local Ollama pass (saves CPU when no GPU is available).",
    )
    args = parser.parse_args()

    inputs_path = Path(args.inputs)
    if not inputs_path.is_absolute():
        inputs_path = Path(__file__).resolve().parents[1] / inputs_path
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))

    generation_prompts: List[Dict[str, str]] = inputs["generation_prompts"]
    embedding_texts: List[str] = inputs["embedding_texts"]
    hybrid_cases: List[Dict[str, Any]] = inputs["hybrid_cases"]
    rerank_cases: List[Dict[str, Any]] = inputs["rerank_cases"]
    rubric: str = inputs["judge_rubric"]["criteria"]

    cloud_gen = resolve_llm_endpoint("cloud")
    try:
        local_gen = resolve_llm_endpoint("local") if not args.skip_local else None
    except Exception:  # noqa: BLE001
        local_gen = None
    rerank_endpoint = LLMEndpoint(
        mode="cloud",
        provider="bailian",
        api_key=os.environ.get("RERANK_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY", ""),
        base_url=os.environ.get(
            "RERANK_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-api/v1",
        ),
        model=os.environ.get("RERANK_MODEL", "qwen3-rerank"),
    )

    emb_cloud_key = os.environ.get("EMBEDDING_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", "")
    emb_cloud_url = os.environ.get("EMBEDDING_BASE_URL") or os.environ.get(
        "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    emb_cloud_model = os.environ.get("EMBEDDING_MODEL", "text-embedding-v4")
    emb_dim = int(os.environ.get("EMBEDDING_DIMENSIONS", "1024"))
    emb_local_key = os.environ.get("LOCAL_EMBEDDING_API_KEY", "ollama")
    emb_local_url = os.environ.get("LOCAL_EMBEDDING_BASE_URL", "http://127.0.0.1:11434/v1")
    emb_local_model = os.environ.get("LOCAL_EMBEDDING_MODEL", "bge-m3")
    skip_local = args.skip_local or local_gen is None

    started_at = datetime.now(timezone.utc).isoformat()

    # ---------- generation ----------
    gen_records: List[Dict[str, Any]] = []
    gen_latency = Bucket("gen")
    gen_token_in = 0
    gen_token_out = 0
    for prompt in generation_prompts:
        cloud_record = await _run_generation(
            cloud_gen, prompt, task_id=prompt["id"], provider_label="cloud"
        )
        gen_records.append(cloud_record)
        if cloud_record["ok"]:
            gen_latency.add(cloud_record["latency_ms"] / 1000.0)
            tokens = cloud_record["tokens"] or {}
            if isinstance(tokens, dict):
                gen_token_in += int(tokens.get("prompt_tokens") or 0)
                gen_token_out += int(tokens.get("completion_tokens") or 0)

        if not skip_local:
            try:
                local_record = await _run_generation(
                    local_gen,
                    prompt,
                    task_id=prompt["id"],
                    provider_label="local",
                )
            except Exception as exc:  # noqa: BLE001
                local_record = {
                    "task_id": prompt["id"],
                    "provider": "local",
                    "ok": False,
                    "error_code": PROVIDER_UNKNOWN,
                    "last_error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": None,
                }
            gen_records.append(local_record)
            if local_record.get("ok"):
                gen_latency.add(local_record["latency_ms"] / 1000.0)

    # ---------- judge (LLM-as-judge) ----------
    judge_records: List[Dict[str, Any]] = []
    for record in gen_records:
        if not record.get("ok"):
            continue
        task_id = f"{record['task_id']}-{record['provider']}"
        prompt = next(
            (p for p in generation_prompts if p["id"] == record["task_id"]),
            None,
        )
        if prompt is None:
            continue
        judge = await _run_judge(
            cloud_gen,
            task_id=task_id,
            user_prompt=prompt["user"],
            candidate=record.get("content") or "",
            expected_keywords=prompt.get("expected_keywords", []),
            provider_label="judge-cloud",
            rubric=rubric,
        )
        judge_records.append(judge)

    # ---------- embedding ----------
    emb_records: List[Dict[str, Any]] = []
    emb_latency_cloud = Bucket("emb-cloud")
    emb_latency_local = Bucket("emb-local")
    cloud_vectors: List[List[float]] = []
    local_vectors: List[List[float]] = []
    for text in embedding_texts:
        cloud_rec = await _embed(
            text,
            api_key=emb_cloud_key,
            base_url=emb_cloud_url,
            model_name=emb_cloud_model,
            dim=emb_dim,
            provider_label="cloud",
        )
        emb_records.append(cloud_rec)
        if cloud_rec["ok"]:
            emb_latency_cloud.add(cloud_rec["latency_ms"] / 1000.0)
            vector = cloud_rec.pop("_vector", None)
            if isinstance(vector, list):
                cloud_vectors.append(vector)

        if not skip_local:
            try:
                local_rec = await _embed(
                    text,
                    api_key=emb_local_key,
                    base_url=emb_local_url,
                    model_name=emb_local_model,
                    dim=emb_dim,
                    provider_label="local",
                )
            except Exception as exc:  # noqa: BLE001
                local_rec = {
                    "provider": "local",
                    "ok": False,
                    "error_code": PROVIDER_UNKNOWN,
                    "last_error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": None,
                }
            emb_records.append(local_rec)
            if local_rec.get("ok") and not args.skip_local:
                emb_latency_local.add(local_rec["latency_ms"] / 1000.0)
                vector = local_rec.pop("_vector", None)
                if isinstance(vector, list):
                    local_vectors.append(vector)

    # Similarity sanity: average pairwise cosine on same-provider vectors.
    def _avg_pairwise(vectors: List[List[float]]) -> Optional[float]:
        if len(vectors) < 2:
            return None
        sims: List[float] = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                sims.append(_cosine(vectors[i], vectors[j]))
        return round(sum(sims) / len(sims), 4) if sims else None

    sim_cloud = _avg_pairwise(cloud_vectors)
    sim_local = _avg_pairwise(local_vectors)

    # ---------- rerank ----------
    rerank_records: List[Dict[str, Any]] = []
    rerank_latency = Bucket("rerank")
    for case in rerank_cases:
        try:
            record = await _rerank(
                query=case["query"],
                documents=case["documents"],
                api_key=rerank_endpoint.api_key,
                base_url=rerank_endpoint.base_url,
                model_name=rerank_endpoint.model,
                provider_label="cloud",
            )
        except Exception as exc:  # noqa: BLE001
            record = {
                "id": case["id"],
                "provider": "cloud",
                "ok": False,
                "error_code": PROVIDER_UNKNOWN,
                "last_error": f"{type(exc).__name__}: {exc}",
                "latency_ms": None,
            }
        record["id"] = case["id"]
        record["relevant_indices"] = case.get("relevant_indices", [])
        record["ndcg_at_3"] = _ndcg(record.get("ranking"), case.get("relevant_indices", []), 3)
        rerank_records.append(record)
        if record.get("ok"):
            rerank_latency.add(record["latency_ms"] / 1000.0)

    # ---------- hybrid retrieval ----------
    hybrid_records: List[Dict[str, Any]] = []
    hybrid_latency = Bucket("hybrid")
    try:
        if skip_local:
            raise RuntimeError("Hybrid benchmark requires the local provider")
        hybrid_records = _run_hybrid_benchmark(
            cases=hybrid_cases,
            corpus=embedding_texts,
            cloud_vectors=cloud_vectors,
            local_vectors=local_vectors,
            top_k=args.hybrid_top_k,
        )
    except Exception as exc:  # noqa: BLE001
        hybrid_records = [
            {
                "task_id": str(case["id"]),
                "ok": False,
                "latency_ms": None,
                "count": 0,
                "first_score": None,
                "expected_document_ids": case.get("expected_document_ids", []),
                "returned_document_ids": [],
                "route_coverage": [],
                "gold_hit": False,
                "dual_route_hit": False,
                "degraded_routes": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
            for case in hybrid_cases
        ]
    for result in hybrid_records:
        if result["ok"]:
            hybrid_latency.add(result["latency_ms"] / 1000.0)

    # ---------- per-task judge + dedup scoring ----------
    judge_by_key = {(r["task_id"], r["provider"]): r for r in judge_records}
    for gen_rec in gen_records:
        key = (gen_rec["task_id"], gen_rec["provider"])
        gen_rec["judge_score"] = judge_by_key.get(key, {}).get("score")
        gen_rec["judge_raw"] = judge_by_key.get(key, {}).get("raw")

    finished_at = datetime.now(timezone.utc).isoformat()

    # ---------- aggregate ----------
    report: Dict[str, Any] = {
        "schema_version": 1,
        "started_at": started_at,
        "finished_at": finished_at,
        "config": {
            "cloud_gen": _endpoint_dict(cloud_gen),
            "local_gen": _endpoint_dict(local_gen) if local_gen else None,
            "cloud_emb_model": emb_cloud_model,
            "local_emb_model": emb_local_model if not skip_local else None,
            "rerank_model": rerank_endpoint.model,
            "emb_dim": emb_dim,
            "skip_local": skip_local,
        },
        "generation": {
            "latency_ms": gen_latency.stats(),
            "tokens_in": gen_token_in,
            "tokens_out": gen_token_out,
            "records": gen_records,
        },
        "judge": {
            "records": judge_records,
            "count": len(judge_records),
            "ok_count": sum(1 for r in judge_records if r.get("ok")),
        },
        "embedding": {
            "latency_ms_cloud": emb_latency_cloud.stats(),
            "latency_ms_local": emb_latency_local.stats(),
            "avg_pairwise_cosine_cloud": sim_cloud,
            "avg_pairwise_cosine_local": sim_local,
            "records": emb_records,
        },
        "rerank": {
            "latency_ms": rerank_latency.stats(),
            "records": rerank_records,
        },
        "hybrid": {
            "latency_ms": hybrid_latency.stats(),
            "records": hybrid_records,
        },
    }
    report["gates"] = _build_gates(
        report,
        generation_expected=len(generation_prompts) * (1 if skip_local else 2),
        judge_expected=len(generation_prompts) * (1 if skip_local else 2),
        embedding_expected=len(embedding_texts) * (1 if skip_local else 2),
        rerank_expected=len(rerank_cases),
        hybrid_expected=len(hybrid_cases),
        embedding_dimensions=emb_dim,
    )
    report["overall_pass"] = all(gate["pass"] for gate in report["gates"].values())

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parents[2] / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output": str(out_path),
                "overall_pass": report["overall_pass"],
                "gates": report["gates"],
                "generation_count": len(gen_records),
                "generation_ok": sum(1 for r in gen_records if r["ok"]),
                "judge_count": len(judge_records),
                "judge_avg_score": _average_score(judge_records),
                "embedding_count": len(emb_records),
                "embedding_ok": sum(1 for r in emb_records if r["ok"]),
                "rerank_count": len(rerank_records),
                "rerank_ok": sum(1 for r in rerank_records if r["ok"]),
                "rerank_avg_ndcg_at_3": _avg(rerank_records, "ndcg_at_3"),
                "hybrid_count": len(hybrid_records),
                "hybrid_ok": sum(1 for r in hybrid_records if r["ok"]),
                "gen_latency_ms": gen_latency.stats(),
                "emb_cloud_latency_ms": emb_latency_cloud.stats(),
                "emb_local_latency_ms": emb_latency_local.stats(),
                "rerank_latency_ms": rerank_latency.stats(),
                "hybrid_latency_ms": hybrid_latency.stats(),
                "emb_sim_cloud": sim_cloud,
                "emb_sim_local": sim_local,
            },
            ensure_ascii=False,
        )
    )
    return report


def _average_score(records: Iterable[Dict[str, Any]]) -> Optional[float]:
    scores = [r["score"] for r in records if r.get("score") is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _avg(records: Iterable[Dict[str, Any]], key: str) -> Optional[float]:
    vals = [r[key] for r in records if r.get(key) is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _build_gates(
    report: Dict[str, Any],
    *,
    generation_expected: int,
    judge_expected: int,
    embedding_expected: int,
    rerank_expected: int,
    hybrid_expected: int,
    embedding_dimensions: int,
) -> Dict[str, Dict[str, Any]]:
    generation_records = report["generation"]["records"]
    judge_records = report["judge"]["records"]
    embedding_records = report["embedding"]["records"]
    rerank_records = report["rerank"]["records"]
    hybrid_records = report["hybrid"]["records"]

    generation_ok = sum(bool(record.get("ok")) for record in generation_records)
    judge_ok = sum(
        bool(record.get("ok")) and record.get("score") is not None
        for record in judge_records
    )
    embedding_ok = sum(
        bool(record.get("ok"))
        and record.get("vector_dim") == embedding_dimensions
        for record in embedding_records
    )
    rerank_ok = sum(
        bool(record.get("ok")) and bool(record.get("ranking"))
        for record in rerank_records
    )
    hybrid_ok = sum(bool(record.get("ok")) for record in hybrid_records)

    return {
        "generation": {
            "pass": generation_ok == generation_expected,
            "ok": generation_ok,
            "expected": generation_expected,
        },
        "judge": {
            "pass": judge_ok == judge_expected,
            "ok": judge_ok,
            "expected": judge_expected,
        },
        "embedding": {
            "pass": embedding_ok == embedding_expected,
            "ok": embedding_ok,
            "expected": embedding_expected,
            "dimensions": embedding_dimensions,
        },
        "rerank": {
            "pass": rerank_ok == rerank_expected,
            "ok": rerank_ok,
            "expected": rerank_expected,
        },
        "hybrid": {
            "pass": hybrid_ok == hybrid_expected,
            "ok": hybrid_ok,
            "expected": hybrid_expected,
        },
    }


if __name__ == "__main__":
    result = asyncio.run(_main())
    raise SystemExit(0 if result["overall_pass"] else 1)
