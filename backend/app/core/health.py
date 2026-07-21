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


def _task_worker() -> None:
    """Require at least one unexpired worker heartbeat."""
    from core.redis_client import get_redis_client

    client = get_redis_client()
    prefix = os.getenv("TASK_QUEUE_PREFIX", "industry:tasks")
    workers_key = f"{prefix}:workers"
    workers = client.smembers(workers_key)
    for worker in workers:
        if client.exists(f"{prefix}:worker:{worker}"):
            return
        client.srem(workers_key, worker)
    raise ConnectionError("no live persistent task worker heartbeat")


def _outbox_dispatcher() -> None:
    """Require at least one unexpired transactional outbox heartbeat."""
    from core.redis_client import get_redis_client

    client = get_redis_client()
    prefix = os.getenv("TASK_QUEUE_PREFIX", "industry:tasks")
    dispatchers_key = f"{prefix}:outbox-dispatchers"
    dispatchers = client.smembers(dispatchers_key)
    for dispatcher_id in dispatchers:
        if client.exists(f"{prefix}:outbox-dispatcher:{dispatcher_id}"):
            return
        client.srem(dispatchers_key, dispatcher_id)
    raise ConnectionError("no live transactional outbox dispatcher heartbeat")


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


def _openai_compatible_embedding(
    base_url: str,
    model: str,
    api_key: str,
    dimensions: int,
) -> None:
    """Verify an embedding endpoint through the operation used by the application.

    Some OpenAI-compatible providers, including Bailian, do not expose embedding
    models through ``GET /models``. A minimal embedding request therefore gives a
    more accurate readiness signal than model discovery.
    """
    timeout = float(os.getenv("READINESS_TIMEOUT_SECONDS", "3"))
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = json.dumps({
        "model": model,
        "input": "readiness probe",
        "dimensions": dimensions,
        "encoding_format": "float",
    }).encode("utf-8")
    request = Request(
        f"{base_url.rstrip('/')}/embeddings",
        data=body,
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data", [])
    embedding = data[0].get("embedding") if data and isinstance(data[0], dict) else None
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("embedding endpoint returned no vector")


def readiness_checks() -> dict[str, Callable[[], None]]:
    """Build checks dynamically so tests and storage-only deployments stay offline-safe."""
    checks = dict(STORAGE_CHECKS)
    if env_bool("READINESS_CHECK_TASK_WORKER", False):
        checks["task_worker"] = _task_worker
    if env_bool("READINESS_CHECK_OUTBOX_DISPATCHER", False):
        checks["outbox_dispatcher"] = _outbox_dispatcher
    if env_bool("READINESS_CHECK_MODELS", False):
        from service.embedding_router import get_embedding_route
        from service.llm_router import resolve_llm_endpoint

        llm_endpoint = resolve_llm_endpoint()
        embedding_endpoint = get_embedding_route("cloud")
        checks["generation_model"] = lambda: _openai_compatible_model(
            llm_endpoint.base_url, llm_endpoint.model, llm_endpoint.api_key
        )
        checks["embedding_model"] = lambda: _openai_compatible_embedding(
            embedding_endpoint.base_url,
            embedding_endpoint.model,
            embedding_endpoint.api_key,
            embedding_endpoint.dimensions,
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
