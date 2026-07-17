"""Read-only reconciliation of PostgreSQL document metadata and Milvus chunks."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from config.industry_config import INDUSTRY_CONFIGS
from core.database import SessionLocal
from models.knowledge import Document, KnowledgeBase
from models.user import User
from service.milvus_service import get_milvus_service


def expected_doc_id(filename: str) -> str:
    return hashlib.md5(filename.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--limit", type=int, default=20000)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        if not user:
            raise ValueError(f"用户不存在: {args.username}")
        milvus = get_milvus_service()
        audits: dict[str, dict[str, object]] = {}
        for config in INDUSTRY_CONFIGS.values():
            kb = db.query(KnowledgeBase).filter(
                KnowledgeBase.user_id == user.id,
                KnowledgeBase.name == config.knowledge_base_name,
            ).first()
            if not kb:
                audits[config.knowledge_base_name] = {
                    "passed": False,
                    "error": "PostgreSQL 知识库不存在",
                }
                continue

            documents = db.query(Document).filter(Document.knowledge_base_id == kb.id).all()
            expected_counts = {
                document.filename: int(document.chunk_count or 0)
                for document in documents
                if document.status == "completed"
            }
            status_counts = Counter(document.status for document in documents)
            collection = f"kb_{config.knowledge_base_name}"
            chunks = milvus.list_chunks(collection, limit=args.limit)
            actual_counts = Counter(str(chunk.get("filename")) for chunk in chunks)
            chunk_ids = [str(chunk.get("id")) for chunk in chunks]
            doc_chunk_keys = [
                (str(chunk.get("doc_id")), int(chunk.get("chunk_index", -1)))
                for chunk in chunks
            ]
            invalid_doc_ids = sum(
                str(chunk.get("doc_id")) != expected_doc_id(str(chunk.get("filename")))
                for chunk in chunks
            )
            per_document_mismatch = [
                {
                    "filename": filename,
                    "postgres_chunks": expected_counts.get(filename, 0),
                    "milvus_chunks": actual_counts.get(filename, 0),
                }
                for filename in sorted(set(expected_counts) | set(actual_counts))
                if expected_counts.get(filename, 0) != actual_counts.get(filename, 0)
            ]
            stats = milvus.get_collection_stats(collection)
            entity_count = int(stats.get("num_entities", 0))
            expected_total = sum(expected_counts.values())
            audit = {
                "collection": collection,
                "postgres_status_counts": dict(sorted(status_counts.items())),
                "postgres_completed_documents": len(expected_counts),
                "postgres_chunks": expected_total,
                "milvus_documents": len(actual_counts),
                "milvus_queried_chunks": len(chunks),
                "milvus_num_entities": entity_count,
                "duplicate_chunk_ids": len(chunk_ids) - len(set(chunk_ids)),
                "duplicate_doc_chunk_keys": len(doc_chunk_keys) - len(set(doc_chunk_keys)),
                "invalid_doc_ids": invalid_doc_ids,
                "per_document_mismatch": per_document_mismatch,
                "limit_reached": len(chunks) >= args.limit,
            }
            audit["passed"] = (
                set(status_counts) <= {"completed"}
                and expected_total == len(chunks) == entity_count
                and not audit["duplicate_chunk_ids"]
                and not audit["duplicate_doc_chunk_keys"]
                and not invalid_doc_ids
                and not per_document_mismatch
                and not audit["limit_reached"]
            )
            audits[config.knowledge_base_name] = audit
    finally:
        db.close()

    report = {
        "audited_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "username": args.username,
        "read_only": True,
        "knowledge_bases": audits,
        "passed": len(audits) == len(INDUSTRY_CONFIGS) and all(
            bool(audit.get("passed")) for audit in audits.values()
        ),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
