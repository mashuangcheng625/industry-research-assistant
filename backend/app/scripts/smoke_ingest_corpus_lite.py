"""Run the approved corpus through the real parser/chunker and Milvus Lite.

This smoke test is deliberately credential-free. It replaces only the external
Embedding API with deterministic 1024-dimensional vectors; parsing, chunk IDs,
Milvus schema/index creation, insertion, flush, query, and vector search all use
the production code path. A temporary Lite database prevents accidental writes
to the configured Standalone service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pymilvus import connections

from config.industry_config import INDUSTRY_CONFIGS
from service.docmind_service import process_document_with_docmind
from service.milvus_service import MilvusService
from service.source_governance import read_jsonl, resolve_managed_path


VECTOR_DIMENSION = 1024


def deterministic_embeddings(texts: list[str]) -> list[list[float]]:
    """Create stable, non-semantic unit vectors for infrastructure validation."""
    vectors: list[list[float]] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [0.0] * VECTOR_DIMENSION
        for offset in range(0, len(digest), 4):
            index = int.from_bytes(digest[offset:offset + 2], "big") % VECTOR_DIMENSION
            value = (int.from_bytes(digest[offset + 2:offset + 4], "big") + 1) / 65536
            vector[index] += value
        norm = math.sqrt(sum(value * value for value in vector))
        vectors.append([value / norm for value in vector])
    return vectors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("data/semiconductor_sources/review/candidates-v2.jsonl"),
    )
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    queue = args.queue.resolve()
    source_root = queue.parent.parent
    candidates = read_jsonl(queue)
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    rows: list[dict[str, object]] = []
    expected_by_collection: Counter[str] = Counter()
    expected_documents: dict[str, set[str]] = defaultdict(set)
    failures: list[dict[str, str]] = []
    collection_audit: dict[str, dict[str, object]] = {}
    retrieval_probe: dict[str, object] = {}

    # On WSL, TEMP may point to /mnt/c where Unix-domain socket bind is not
    # supported. Milvus Lite needs that socket, so default to the Linux fs.
    lite_temp_root = Path(os.getenv("MILVUS_LITE_TEMP_DIR", "/tmp"))
    lite_temp_root.mkdir(parents=True, exist_ok=True)
    previous_tempdir = tempfile.tempdir
    tempfile.tempdir = str(lite_temp_root)
    with tempfile.TemporaryDirectory(
        prefix="semiconductor-milvus-lite-", dir=lite_temp_root,
    ) as temp_dir:
        lite_path = Path(temp_dir) / "corpus-smoke.db"
        # MilvusService reads the URI during construction. Direct assignment is
        # intentionally scoped to this process and never touches project .env.
        previous_uri = os.environ.get("MILVUS_URI")
        os.environ["MILVUS_URI"] = str(lite_path)
        try:
            milvus = MilvusService()
            for candidate in candidates:
                if candidate.review_status != "approved" or not candidate.local_normalized_path:
                    continue
                path = resolve_managed_path(source_root, candidate.local_normalized_path)
                for domain in candidate.domains:
                    collection = f"kb_{INDUSTRY_CONFIGS[domain].knowledge_base_name}"
                    item_started = time.perf_counter()
                    result = process_document_with_docmind(
                        file_path=str(path),
                        file_name=f"{candidate.candidate_id}.md",
                        index_name=collection,
                        chunk_size=args.chunk_size,
                        embedding_fn=deterministic_embeddings,
                        milvus_service=milvus,
                    )
                    row = {
                        "candidate_id": candidate.candidate_id,
                        "domain": domain,
                        "collection": collection,
                        "status": "completed" if result["success"] else "failed",
                        "chunk_count": int(result["document_count"]),
                        "elapsed_ms": round((time.perf_counter() - item_started) * 1000, 1),
                        "message": result["message"],
                    }
                    rows.append(row)
                    if result["success"]:
                        expected_by_collection[collection] += int(result["document_count"])
                        expected_documents[collection].add(f"{candidate.candidate_id}.md")
                    else:
                        failures.append({
                            "candidate_id": candidate.candidate_id,
                            "domain": domain,
                            "message": str(result["message"]),
                        })

            for collection, expected_chunks in sorted(expected_by_collection.items()):
                chunks = milvus.list_chunks(collection, limit=max(expected_chunks + 1, 1000))
                ids = [str(chunk["id"]) for chunk in chunks]
                documents = {str(chunk["filename"]) for chunk in chunks}
                stats = milvus.get_collection_stats(collection)
                actual_entities = int(stats.get("num_entities", 0))
                audit = {
                    "expected_chunks": expected_chunks,
                    "queried_chunks": len(chunks),
                    "num_entities": actual_entities,
                    "expected_documents": len(expected_documents[collection]),
                    "queried_documents": len(documents),
                    "duplicate_chunk_ids": len(ids) - len(set(ids)),
                    "passed": (
                        len(chunks) == expected_chunks
                        and actual_entities == expected_chunks
                        and documents == expected_documents[collection]
                        and len(ids) == len(set(ids))
                    ),
                }
                collection_audit[collection] = audit
                if chunks and not retrieval_probe:
                    query_vector = deterministic_embeddings([str(chunks[0]["content"])])[0]
                    hits = milvus.search(collection, query_vector, top_k=1)
                    retrieval_probe = {
                        "collection": collection,
                        "expected_chunk_id": chunks[0]["id"],
                        "returned_chunk_id": hits[0]["id"] if hits else None,
                        "returned": bool(hits),
                        "exact_top1": bool(hits and hits[0]["id"] == chunks[0]["id"]),
                    }
        finally:
            connections.disconnect("default")
            tempfile.tempdir = previous_tempdir
            if previous_uri is None:
                os.environ.pop("MILVUS_URI", None)
            else:
                os.environ["MILVUS_URI"] = previous_uri

    report = {
        "mode": "credential-free full-corpus Milvus Lite smoke",
        "embedding": "deterministic non-semantic 1024-dimensional test vectors",
        "started_at": started_at.replace(microsecond=0).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started_clock, 3),
        "queue": args.queue.as_posix(),
        "chunk_size": args.chunk_size,
        "approved_candidates": len({row["candidate_id"] for row in rows}),
        "document_domain_jobs": len(rows),
        "total_chunks": sum(expected_by_collection.values()),
        "failures": failures,
        "collection_audit": collection_audit,
        "retrieval_probe": retrieval_probe,
        "passed": (
            not failures
            and len(collection_audit) == len(INDUSTRY_CONFIGS)
            and all(audit["passed"] for audit in collection_audit.values())
            and bool(retrieval_probe.get("exact_top1"))
        ),
        "results": rows,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "approved_candidates": report["approved_candidates"],
        "document_domain_jobs": report["document_domain_jobs"],
        "total_chunks": report["total_chunks"],
        "failures": len(failures),
        "collection_audit": collection_audit,
        "retrieval_probe": retrieval_probe,
        "elapsed_seconds": report["elapsed_seconds"],
        "passed": report["passed"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
