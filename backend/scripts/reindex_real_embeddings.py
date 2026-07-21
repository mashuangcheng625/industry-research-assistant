"""Rebuild the approved corpus with real cloud Embeddings.

The script deliberately reuses the production ingestion path instead of
maintaining a second OpenAI batching implementation.  It writes the corpus to
the route-qualified ``text-embedding-v4`` collections used by online retrieval
and fails closed on provider errors, count mismatches, invalid dimensions, or
zero vectors.

The target database is destructive when ``--drop-existing`` is supplied.  A
real Embedding preflight runs before any collection is dropped.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
APP_DIR = BACKEND_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

# pymilvus reads Config.MILVUS_URI while importing.  File paths are assigned
# only inside main(), following the Milvus Lite smoke-test contract.
_configured_milvus_uri = os.environ.pop("MILVUS_URI", None)

from config.industry_config import INDUSTRY_CONFIGS  # noqa: E402
from service.embedding_router import (  # noqa: E402
    collection_name_for_route,
    get_embedding_route,
)
from service.embedding_service import generate_embedding  # noqa: E402
from service.source_governance import (  # noqa: E402
    read_jsonl,
    resolve_managed_path,
)


def _vector_norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _validate_vector(
    vector: Sequence[float] | None,
    *,
    dimensions: int,
    label: str,
) -> None:
    if vector is None:
        raise RuntimeError(f"{label}: Embedding provider returned no vector")
    if len(vector) != dimensions:
        raise RuntimeError(
            f"{label}: expected {dimensions} dimensions, got {len(vector)}"
        )
    if not all(math.isfinite(float(value)) for value in vector):
        raise RuntimeError(f"{label}: vector contains a non-finite value")
    if _vector_norm(vector) <= 0:
        raise RuntimeError(f"{label}: provider returned a zero vector")


def _cloud_embedding_preflight() -> dict[str, Any]:
    """Call the configured cloud route once before destructive operations."""
    route = get_embedding_route("cloud")
    vector = generate_embedding(
        "semiconductor embedding reindex preflight",
        api_key=route.api_key,
        base_url=route.base_url,
        model_name=route.model,
        dimensions=route.dimensions,
    )
    if not isinstance(vector, list) or (vector and isinstance(vector[0], list)):
        raise RuntimeError("Embedding preflight returned an invalid response shape")
    _validate_vector(vector, dimensions=route.dimensions, label="preflight")
    return {
        "provider": route.provider,
        "model": route.model,
        "dimensions": route.dimensions,
        "vector_norm": round(_vector_norm(vector), 6),
    }


def _audit_collection_vectors(
    collection: Any,
    *,
    expected_dimensions: int,
) -> dict[str, Any]:
    """Read every vector in a small evaluation collection and reject zeros."""
    entity_count = int(collection.num_entities)
    rows = collection.query(
        expr="",
        output_fields=["vector"],
        limit=max(entity_count, 1),
    )
    invalid_dimensions = 0
    zero_vectors = 0
    non_finite_vectors = 0
    for row in rows:
        vector = row.get("vector") or []
        if len(vector) != expected_dimensions:
            invalid_dimensions += 1
            continue
        if not all(math.isfinite(float(value)) for value in vector):
            non_finite_vectors += 1
            continue
        if _vector_norm(vector) <= 0:
            zero_vectors += 1
    return {
        "num_entities": entity_count,
        "queried_vectors": len(rows),
        "invalid_dimensions": invalid_dimensions,
        "zero_vectors": zero_vectors,
        "non_finite_vectors": non_finite_vectors,
        "passed": (
            len(rows) == entity_count
            and invalid_dimensions == 0
            and zero_vectors == 0
            and non_finite_vectors == 0
        ),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        type=Path,
        default=ROOT_DIR / "data/semiconductor_sources/review/candidates-v2.jsonl",
    )
    parser.add_argument("--limit", type=int, default=0, help="0 processes all documents")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument(
        "--milvus-uri",
        default=(
            _configured_milvus_uri
            or os.getenv("MILVUS_LITE_DB")
            or "/tmp/industry-research-milvus.db"
        ),
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Required when target collections already exist.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/reindex-real-embeddings-report.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()

    # The production helper already honors EMBEDDING_BATCH_SIZE=10 and retries.
    # Force this reindex job to build only the cloud route needed by the blind
    # evaluation; it must not depend on the availability of local Ollama.
    previous_ingest_mode = os.environ.get("EMBEDDING_INGEST_MODE")
    previous_tempdir = tempfile.tempdir
    os.environ["EMBEDDING_INGEST_MODE"] = "cloud"
    os.environ["MILVUS_URI"] = str(args.milvus_uri)
    tempfile.tempdir = "/tmp"

    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": started_at.replace(microsecond=0).isoformat(),
        "milvus_uri": str(args.milvus_uri),
        "queue": str(args.queue),
        "chunk_size": args.chunk_size,
        "preflight": None,
        "processed_jobs": [],
        "failures": [],
        "collection_audit": {},
        "retrieval_probe": {},
        "passed": False,
    }

    try:
        # This paid but tiny request must succeed before any data is removed.
        print("Preflight...", flush=True)
        report["preflight"] = _cloud_embedding_preflight()
        print("Preflight OK", flush=True)

        from pymilvus import Collection, connections, utility
        from service.docmind_service import process_document_with_docmind
        from service.milvus_service import MilvusService

        print("Imports done", flush=True)
        try:
            connections.disconnect("default")
        except Exception:  # noqa: BLE001 — may not exist yet
            pass

        milvus = MilvusService()
        print(f"Milvus connected. Collections: {len(utility.list_collections())} total.", flush=True)
        print("Milvus connected", flush=True)
        route = get_embedding_route("cloud")
        queue = args.queue.resolve()
        candidates = read_jsonl(queue)
        source_root = queue.parent.parent
        collection_names = {
            collection_name_for_route(
                f"kb_{config.knowledge_base_name}",
                route,
            )
            for config in INDUSTRY_CONFIGS.values()
        }
        legacy_names = {
            f"kb_{config.knowledge_base_name}"
            for config in INDUSTRY_CONFIGS.values()
        }
        existing_targets = sorted(
            name
            for name in utility.list_collections()
            if name in collection_names or name in legacy_names
        )
        if existing_targets and not args.drop_existing:
            raise RuntimeError(
                "Target collections already exist; rerun with --drop-existing after "
                f"reviewing the target URI. Existing: {', '.join(existing_targets)}"
            )
        for name in existing_targets:
            print(f"Dropping {name}...")
            utility.drop_collection(name)

        expected_by_collection: Counter[str] = Counter()
        processed_documents = 0
        for candidate in candidates:
            if candidate.review_status != "approved" or not candidate.local_normalized_path:
                continue
            if args.limit and processed_documents >= args.limit:
                break
            processed_documents += 1
            path = resolve_managed_path(source_root, candidate.local_normalized_path)
            for domain in candidate.domains:
                collection_base = f"kb_{INDUSTRY_CONFIGS[domain].knowledge_base_name}"
                target_collection = collection_name_for_route(collection_base, route)
                job_started = time.perf_counter()
                result = process_document_with_docmind(
                    file_path=str(path),
                    file_name=f"{candidate.candidate_id}.md",
                    index_name=collection_base,
                    chunk_size=args.chunk_size,
                    milvus_service=milvus,
                )
                row = {
                    "candidate_id": candidate.candidate_id,
                    "domain": domain,
                    "collection": target_collection,
                    "success": bool(result.get("success")),
                    "chunk_count": int(result.get("document_count", 0)),
                    "embedding_routes": result.get("embedding_routes", []),
                    "message": str(result.get("message", "")),
                    "elapsed_ms": round(
                        (time.perf_counter() - job_started) * 1000,
                        1,
                    ),
                }
                report["processed_jobs"].append(row)
                if not row["success"]:
                    report["failures"].append(row)
                    continue
                if row["chunk_count"] <= 0:
                    row["success"] = False
                    row["message"] = "Successful ingestion returned zero chunks"
                    report["failures"].append(row)
                    continue
                if row["embedding_routes"] != ["cloud"]:
                    row["success"] = False
                    row["message"] = (
                        "Expected only the cloud route, got "
                        f"{row['embedding_routes']}"
                    )
                    report["failures"].append(row)
                    continue
                expected_by_collection[target_collection] += row["chunk_count"]

        for name, expected_count in sorted(expected_by_collection.items()):
            collection = Collection(name)
            collection.load()
            audit = _audit_collection_vectors(
                collection,
                expected_dimensions=route.dimensions,
            )
            audit["expected_entities"] = expected_count
            audit["passed"] = bool(
                audit["passed"] and audit["num_entities"] == expected_count
            )
            report["collection_audit"][name] = audit

        probe_base = "kb_semiconductor_chip_design_eda_ip"
        probe_collection = collection_name_for_route(probe_base, route)
        probe_text = "RISC-V defines machine supervisor and user privilege modes"
        query_vector = generate_embedding(
            probe_text,
            api_key=route.api_key,
            base_url=route.base_url,
            model_name=route.model,
            dimensions=route.dimensions,
        )
        if not isinstance(query_vector, list) or (
            query_vector and isinstance(query_vector[0], list)
        ):
            raise RuntimeError("Retrieval probe returned an invalid vector shape")
        _validate_vector(
            query_vector,
            dimensions=route.dimensions,
            label="retrieval probe",
        )
        hits = milvus.search(probe_collection, query_vector, top_k=3)
        report["retrieval_probe"] = {
            "collection": probe_collection,
            "returned": len(hits),
            "top_score": round(float(hits[0]["score"]), 6) if hits else None,
            "passed": bool(hits),
        }
        expected_collection_count = (
            len(collection_names) if not args.limit else len(expected_by_collection)
        )
        report["expected_collection_count"] = expected_collection_count
        report["passed"] = bool(
            not report["failures"]
            and len(report["collection_audit"]) == expected_collection_count
            and all(
                audit["passed"]
                for audit in report["collection_audit"].values()
            )
            and report["retrieval_probe"].get("passed")
        )
    except Exception as exc:  # noqa: BLE001
        report["failures"].append({
            "stage": "reindex",
            "error": f"{type(exc).__name__}: {exc}",
        })
        print(f"Reindex failed: {type(exc).__name__}: {exc}")
    finally:
        try:
            from pymilvus import connections

            connections.disconnect("default")
        except Exception:  # noqa: BLE001
            pass
        tempfile.tempdir = previous_tempdir
        if previous_ingest_mode is None:
            os.environ.pop("EMBEDDING_INGEST_MODE", None)
        else:
            os.environ["EMBEDDING_INGEST_MODE"] = previous_ingest_mode
        report["finished_at"] = datetime.now(timezone.utc).replace(
            microsecond=0,
        ).isoformat()
        report["elapsed_seconds"] = round(
            time.perf_counter() - started_clock,
            3,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "output": str(args.output),
        "processed_jobs": len(report["processed_jobs"]),
        "failures": len(report["failures"]),
        "collection_audit": report["collection_audit"],
        "retrieval_probe": report["retrieval_probe"],
        "elapsed_seconds": report["elapsed_seconds"],
        "passed": report["passed"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
