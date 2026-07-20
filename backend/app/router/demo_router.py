"""Demo scenario router — deterministic, pre-baked interview showcase.

The four scenarios run entirely from frozen fixtures, never calling live
APIs during a demo. This keeps the page fast and predictable for an
interviewer who may be seeing the product for the first time.

Every scenario response includes a ``retrieval_trace`` section that
documents the cloud/local routing, RRF fusion, rerank scores,
degradation flags and document metadata so the interviewer can see
exactly how each piece of evidence maps to the rendered answer.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text

router = APIRouter(prefix="/demo", tags=["demo"])

# FIXTURE_DIR points to pre-baked scenario definitions. Each .json
# file defines one scenario with its question, expected answer, and the
# retrieval trace that supports it.
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "sample-data" / "demo_scenarios"
SYNC_PROBE_TIMEOUT_SECONDS = 2.5


# ---------------------------------------------------------------------------
# GET /demo/scenarios — return all four pre-baked demo scenarios
# ---------------------------------------------------------------------------


@router.get("/scenarios")
async def list_scenarios() -> JSONResponse:
    """Return all four pre-baked demo scenarios.

    Each scenario carries a ``retrieval_trace`` array that the frontend
    renders as an expandable evidence panel (document name, page, source
    kind, cloud/local routing, RRF scores, rerank status, degraded flag).
    """

    if not FIXTURE_DIR.is_dir():
        raise HTTPException(status_code=503, detail="Demo scenario fixtures not found")

    scenarios: List[Dict[str, Any]] = []
    for scenario_file in sorted(FIXTURE_DIR.glob("*.json")):
        try:
            payload = json.loads(scenario_file.read_text(encoding="utf-8"))
            payload.setdefault("id", scenario_file.stem)
            scenarios.append(payload)
        except Exception as exc:
            scenarios.append(
                {
                    "id": scenario_file.stem,
                    "error": f"Failed to parse scenario: {type(exc).__name__}: {exc}",
                    "title": f"[无法解析] {scenario_file.stem}",
                    "category": "broken",
                    "order": 99,
                }
            )

    scenarios.sort(key=lambda s: s.get("order", 99))
    return JSONResponse(content={"scenarios": scenarios, "count": len(scenarios)})


# ---------------------------------------------------------------------------
# GET /demo/ready — preflight check: DB, Redis, Milvus, Ollama, Bailian, etc.
# ---------------------------------------------------------------------------


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """Check whether the major infrastructure components are reachable.

    The preflight is intentionally lightweight (< 5 s on a healthy
    machine). Each check returns ``ok`` / ``detail`` / ``latency_ms``
    so the frontend can colour-code the dashboard.

    A skipped check (e.g., ``--skip-local`` env var) returns
    ``ok=null`` with a ``detail`` explaining why.
    """

    # These clients are synchronous. Run them concurrently off the event loop
    # so a slow dependency can never starve the fixture endpoint on a
    # single-worker demo server.
    probe_names = ("postgresql", "redis", "milvus")
    probe_results = await asyncio.gather(
        *(
            _run_sync_probe(probe)
            for probe in (_probe_postgresql, _probe_redis, _probe_milvus)
        )
    )
    checks: Dict[str, Dict[str, Any]] = dict(zip(probe_names, probe_results))

    # Ollama (optional local provider)
    t0 = time.perf_counter()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(os.environ.get("LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1") + "/models")
        if resp.status_code == 200:
            models = [
                m.get("name") or m.get("id", "")
                for m in resp.json().get("data", [])[:5]
            ]
            checks["ollama"] = {"ok": True, "detail": f"models={models}", "latency_ms": _ms(t0)}
        else:
            checks["ollama"] = {"ok": False, "detail": f"HTTP {resp.status_code}", "latency_ms": _ms(t0)}
    except Exception as exc:
        checks["ollama"] = {"ok": None, "detail": "not running (local path does not require Ollama)", "latency_ms": _ms(t0)}

    # Bailian (cloud provider)
    t0 = time.perf_counter()
    try:
        import httpx
        api_key = os.environ.get("DASHSCOPE_API_KEY", os.environ.get("CLOUD_LLM_API_KEY", ""))
        base_url = os.environ.get("DASHSCOPE_BASE_URL", os.environ.get("CLOUD_LLM_BASE_URL", ""))
        if api_key and base_url:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            if resp.status_code in (200, 401):
                # 401 means the endpoint is reachable but auth may need
                # a different token — still counts as "alive".
                checks["bailian"] = {"ok": True, "detail": "reachable", "latency_ms": _ms(t0)}
            else:
                checks["bailian"] = {"ok": False, "detail": f"HTTP {resp.status_code}", "latency_ms": _ms(t0)}
        else:
            checks["bailian"] = {"ok": None, "detail": "API key not configured", "latency_ms": _ms(t0)}
    except Exception as exc:
        checks["bailian"] = {"ok": None, "detail": "not needed for pre-baked demo", "latency_ms": _ms(t0)}

    # Retrieval / Rerank readiness
    t0 = time.perf_counter()
    try:
        rerank_enabled = os.environ.get("RERANK_ENABLED", "false").lower() in ("1", "true", "yes", "on")
        rerank_model = os.environ.get("RERANK_MODEL", "qwen3-rerank")
        emb_mode = os.environ.get("EMBEDDING_ROUTING_MODE", "cloud")
        checks["retrieval"] = {
            "ok": True,
            "detail": f"embedding={emb_mode} rerank={rerank_enabled}",
            "rerank_model": rerank_model if rerank_enabled else None,
            "embedding_mode": emb_mode,
            "latency_ms": _ms(t0),
        }
    except Exception as exc:
        checks["retrieval"] = {"ok": False, "detail": f"{type(exc).__name__}", "latency_ms": _ms(t0)}

    # Knowledge-base user permissions (currently single-user, always ok)
    checks["knowledge_base_access"] = {
        "ok": True,
        "detail": "demo user has access to all knowledge bases",
        "latency_ms": 0,
    }

    # Overall determination
    mandatory = {k for k in checks if checks[k].get("ok") is not None}
    all_ok = all(checks[k]["ok"] for k in mandatory)
    return JSONResponse(
        content={
            "overall": "ready" if all_ok else "degraded",
            "checks": checks,
            "checked_at": _now_iso(),
        }
    )


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def _run_sync_probe(
    probe: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    """Run a blocking readiness probe without blocking FastAPI's event loop."""
    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(probe),
            timeout=SYNC_PROBE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        result = {"ok": False, "detail": "timeout"}
    except Exception as exc:
        result = {"ok": False, "detail": type(exc).__name__}
    return {**result, "latency_ms": _ms(started)}


def _probe_postgresql() -> Dict[str, Any]:
    from core.database import engine

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True, "detail": "connected"}


def _probe_redis() -> Dict[str, Any]:
    from core.redis_client import get_redis_client

    client = get_redis_client()
    if client is None:
        return {"ok": None, "detail": "not configured"}
    client.ping()
    return {"ok": True, "detail": "connected"}


def _probe_milvus() -> Dict[str, Any]:
    from service.milvus_service import MilvusService

    collections = MilvusService().list_collections()
    return {
        "ok": True,
        "detail": f"collections={len(collections)}",
        "collections": collections[:10],
    }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
