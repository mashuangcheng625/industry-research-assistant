"""Dependency readiness checks used by the deployment probe."""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from typing import Callable
from urllib.request import Request, urlopen

from core.runtime_config import env_bool


def _postgres() -> None:
    from sqlalchemy import text

    from core.database import engine

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def _redis() -> None:
    from core.redis_client import get_redis_client

    get_redis_client().ping()


def _milvus() -> None:
    from pymilvus import connections, utility

    alias = "readiness_probe"
    timeout = float(os.getenv("READINESS_TIMEOUT_SECONDS", "3"))
    uri = os.getenv("MILVUS_URI")
    if uri:
        connections.connect(alias=alias, uri=uri, timeout=timeout)
    else:
        connections.connect(
            alias=alias,
            host=os.getenv("MILVUS_HOST", "localhost"),
            port=int(os.getenv("MILVUS_PORT", "19530")),
            timeout=timeout,
        )
    try:
        utility.list_collections(
            using=alias,
            timeout=timeout,
        )
    finally:
        connections.disconnect(alias)


STORAGE_CHECKS: dict[str, Callable[[], None]] = {
    "postgres": _postgres,
    "redis": _redis,
    "milvus": _milvus,
}


def _openai_compatible_model(base_url: str, model: str, api_key: str) -> None:
    """Verify that an OpenAI-compatible endpoint advertises the configured model."""
    timeout = float(os.getenv("READINESS_TIMEOUT_SECONDS", "3"))
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(f"{base_url.rstrip('/')}/models", headers=headers)
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    model_ids = {
        str(item.get("id", ""))
        for item in payload.get("data", [])
        if isinstance(item, dict)
    }
    accepted_ids = {model}
    if ":" not in model:
        accepted_ids.add(f"{model}:latest")
    if model_ids.isdisjoint(accepted_ids):
        raise LookupError("configured model is not advertised by endpoint")


def readiness_checks() -> dict[str, Callable[[], None]]:
    """Build checks dynamically so tests and storage-only deployments stay offline-safe."""
    checks = dict(STORAGE_CHECKS)
    if env_bool("READINESS_CHECK_MODELS", False):
        llm_base = os.getenv("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
        llm_model = os.getenv("LOCAL_LLM_MODEL", "industry-qwen3:4b")
        llm_key = os.getenv("LOCAL_LLM_API_KEY", "ollama")
        embedding_base = os.getenv("EMBEDDING_BASE_URL", llm_base)
        embedding_model = os.getenv("EMBEDDING_MODEL", "bge-m3")
        embedding_key = os.getenv("EMBEDDING_API_KEY", "ollama")
        checks["generation_model"] = lambda: _openai_compatible_model(
            llm_base, llm_model, llm_key
        )
        checks["embedding_model"] = lambda: _openai_compatible_model(
            embedding_base, embedding_model, embedding_key
        )
    return checks


def _run_check(check: Callable[[], None]) -> dict[str, object]:
    started = time.perf_counter()
    try:
        check()
    except Exception as exc:
        return {
            "status": "error",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "error_type": type(exc).__name__,
        }
    return {
        "status": "ok",
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def check_readiness(
    checks: dict[str, Callable[[], None]] | None = None,
) -> dict[str, object]:
    selected = checks if checks is not None else readiness_checks()
    results: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max(len(selected), 1)) as executor:
        futures = {executor.submit(_run_check, check): name for name, check in selected.items()}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    ready = all(result["status"] == "ok" for result in results.values())
    return {"status": "ready" if ready else "not_ready", "checks": results}
