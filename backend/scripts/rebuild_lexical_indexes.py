"""Build versioned Milvus BM25 indexes from existing dense collections.

This migration is non-destructive for dense vectors and never calls an
embedding provider. Existing BM25 targets require ``--drop-existing`` so an
operator cannot silently replace a reviewed index.
"""

from __future__ import annotations

import argparse
import json
import os
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

from config.industry_config import INDUSTRY_CONFIGS  # noqa: E402
from service.embedding_router import (  # noqa: E402
    collection_name_for_route,
    get_embedding_route,
)
from service.milvus_service import (  # noqa: E402
    MilvusService,
    lexical_collection_name,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-route", choices=("cloud", "local"), default="cloud")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--drop-existing", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT_DIR / "reports" / "lexical_index_build_latest.json",
    )
    return parser.parse_args()


def _business_collection_names() -> list[str]:
    return sorted({
        f"kb_{config.knowledge_base_name}"
        for config in INDUSTRY_CONFIGS.values()
    })


def main() -> int:
    args = _parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")

    from pymilvus import Collection, utility

    service = MilvusService()
    route = get_embedding_route(args.source_route)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_route": route.name,
        "source_model": route.model,
        "collection_suffix": os.getenv("RAG_LEXICAL_COLLECTION_SUFFIX", "_bm25_v1"),
        "collections": [],
        "passed": False,
    }

    try:
        for base_name in _business_collection_names():
            source_name = collection_name_for_route(base_name, route)
            target_name = lexical_collection_name(base_name)
            if not utility.has_collection(source_name):
                raise RuntimeError(f"dense source collection is missing: {source_name}")
            if utility.has_collection(target_name):
                if not args.drop_existing:
                    raise RuntimeError(
                        f"BM25 target exists: {target_name}; review it before using --drop-existing"
                    )
                utility.drop_collection(target_name)

            expected = int(Collection(source_name).num_entities)
            if expected <= 0:
                raise RuntimeError(f"dense source collection is empty: {source_name}")
            started = time.perf_counter()
            chunks = service.list_chunks(source_name, limit=expected)
            if len(chunks) != expected:
                raise RuntimeError(
                    f"source read mismatch for {source_name}: expected={expected}, actual={len(chunks)}"
                )

            try:
                service.create_lexical_collection(target_name)
                for offset in range(0, len(chunks), args.batch_size):
                    service.insert_lexical_documents(
                        target_name,
                        chunks[offset:offset + args.batch_size],
                        flush=False,
                    )
                target = Collection(target_name)
                target.flush()
                target.load()
                actual = int(target.num_entities)
                if actual != expected:
                    raise RuntimeError(
                        f"BM25 entity mismatch for {target_name}: expected={expected}, actual={actual}"
                    )
                probe = service.search_lexical(
                    target_name,
                    "semiconductor technology",
                    top_k=1,
                )
                report["collections"].append({
                    "base_collection": base_name,
                    "source_collection": source_name,
                    "target_collection": target_name,
                    "entity_count": actual,
                    "probe_hit_count": len(probe),
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                })
            except Exception:
                if utility.has_collection(target_name):
                    utility.drop_collection(target_name)
                raise

        report["passed"] = True
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
