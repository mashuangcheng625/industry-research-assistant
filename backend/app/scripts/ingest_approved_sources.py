"""将已批准且已本地归档的公开资料导入四个半导体知识库。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from config.industry_config import INDUSTRY_CONFIGS  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from models.knowledge import Document, KnowledgeBase  # noqa: E402
from models.user import User  # noqa: E402
from service.docmind_service import process_document_with_docmind  # noqa: E402
from service.milvus_service import get_milvus_service  # noqa: E402
from service.source_governance import read_jsonl, resolve_managed_path  # noqa: E402


def parse_published_at(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def ingest_candidate(
    db,
    user: User,
    candidate,
    domain: str,
    force: bool,
    chunk_size: int,
    retry_incomplete: bool = False,
    source_root: Path | None = None,
) -> dict[str, object]:
    config = INDUSTRY_CONFIGS[domain]

    def outcome(status: str, message: str, chunk_count: int = 0) -> dict[str, object]:
        return {
            "candidate_id": candidate.candidate_id,
            "domain": domain,
            "collection": f"kb_{config.knowledge_base_name}",
            "document": f"{candidate.candidate_id}.md",
            "status": status,
            "chunk_count": chunk_count,
            "message": message,
        }

    if candidate.review_status != "approved" or not candidate.local_normalized_path:
        return outcome("skipped", "未批准或无本地全文")
    file_path = resolve_managed_path(
        source_root or Path.cwd(), candidate.local_normalized_path
    )
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.user_id == user.id,
        KnowledgeBase.name == config.knowledge_base_name,
    ).first()
    if not kb:
        raise ValueError(f"知识库不存在: {config.knowledge_base_name}")

    filename = f"{candidate.candidate_id}.md"
    document = db.query(Document).filter(
        Document.knowledge_base_id == kb.id,
        Document.filename == filename,
    ).first()
    existing_document = document is not None
    if document and document.status == "completed" and (not force or retry_incomplete):
        return outcome("skipped", "已完成，未要求强制重建", document.chunk_count or 0)
    values = {
        "source_name": candidate.source_name,
        "source_url": candidate.source_url,
        "document_type": candidate.document_type,
        "published_at": parse_published_at(candidate.published_at),
        "document_version": candidate.document_version,
        "authority_level": candidate.authority_level,
        "is_synthetic": False,
        "license_name": candidate.license_name,
        "license_url": candidate.license_url,
        "doi": candidate.doi,
        "external_id": candidate.external_id or candidate.candidate_id,
        "retrieved_at": datetime.fromisoformat(candidate.retrieved_at),
        "content_hash": candidate.content_hash,
        "review_status": candidate.review_status,
        "claim_type": candidate.claim_type,
        "is_open_access": candidate.is_open_access,
    }
    if not document:
        document = Document(
            knowledge_base_id=kb.id,
            user_id=user.id,
            filename=filename,
            file_type="md",
            file_size=file_path.stat().st_size,
            file_path=str(file_path),
            status="processing",
            **values,
        )
        db.add(document)
        kb.document_count = (kb.document_count or 0) + 1
    else:
        for key, value in values.items():
            setattr(document, key, value)
        document.file_size = file_path.stat().st_size
        document.file_path = str(file_path)
        document.status = "processing"
        document.error_message = None
    db.commit()

    collection_name = f"kb_{config.knowledge_base_name}"
    try:
        # Any pre-existing incomplete record may have orphaned vectors. Clear it
        # before retrying so a rerun cannot silently duplicate chunks.
        if existing_document:
            doc_id = hashlib.md5(filename.encode()).hexdigest()
            deleted = get_milvus_service().delete_by_doc_id(collection_name, doc_id)
            if not deleted:
                raise RuntimeError("旧向量删除失败，为避免重复切片已中止重建")

        result = process_document_with_docmind(
            file_path=str(file_path),
            file_name=filename,
            index_name=collection_name,
            chunk_size=chunk_size,
        )
        if not result["success"]:
            raise RuntimeError(str(result["message"]))
        document.status = "completed"
        document.chunk_count = int(result["document_count"])
        document.error_message = None
        db.commit()
        return outcome(
            "completed",
            str(result["message"]),
            int(result["document_count"]),
        )
    except Exception as exc:
        # `processing` was committed deliberately so hard process termination is
        # detectable. Recoverable exceptions are converted to an explicit failed
        # state and can be retried with --retry-incomplete.
        db.rollback()
        document.status = "failed"
        document.chunk_count = 0
        document.error_message = str(exc)
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="导入已批准的真实半导体公开资料")
    parser.add_argument("--username", required=True)
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--retry-incomplete",
        action="store_true",
        help="只重试 processing/failed 文档，已完成文档保持不变",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1200,
        help="真实长文档切片长度，默认 1200 字符",
    )
    parser.add_argument("--domains", nargs="+", choices=list(INDUSTRY_CONFIGS))
    parser.add_argument("--candidate-ids", nargs="+", help="只导入指定 candidate_id")
    parser.add_argument("--report", type=Path, help="写入机器可读 JSON 入库报告")
    parser.add_argument("--fail-fast", action="store_true", help="首个失败后立即停止")
    args = parser.parse_args()

    candidates = read_jsonl(args.queue.resolve())
    source_root = args.queue.resolve().parent.parent
    selected_domains = set(args.domains or INDUSTRY_CONFIGS)
    selected_candidate_ids = set(args.candidate_ids or [])
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    rows: list[dict[str, object]] = []
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == args.username).first()
        if not user:
            raise ValueError(f"用户不存在: {args.username}")
        stop = False
        for candidate in candidates:
            if selected_candidate_ids and candidate.candidate_id not in selected_candidate_ids:
                continue
            for domain in candidate.domains:
                if domain in selected_domains:
                    item_started = time.perf_counter()
                    try:
                        row = ingest_candidate(
                            db,
                            user,
                            candidate,
                            domain,
                            args.force,
                            args.chunk_size,
                            args.retry_incomplete,
                            source_root,
                        )
                    except Exception as exc:
                        db.rollback()
                        row = {
                            "candidate_id": candidate.candidate_id,
                            "domain": domain,
                            "collection": f"kb_{INDUSTRY_CONFIGS[domain].knowledge_base_name}",
                            "document": f"{candidate.candidate_id}.md",
                            "status": "failed",
                            "chunk_count": 0,
                            "message": str(exc),
                        }
                    row["elapsed_ms"] = round((time.perf_counter() - item_started) * 1000, 1)
                    rows.append(row)
                    print(json.dumps(row, ensure_ascii=False))
                    if row["status"] == "failed" and args.fail_fast:
                        stop = True
                        break
            if stop:
                break
    finally:
        db.close()

    status_counts = Counter(str(row["status"]) for row in rows)
    finished_at = datetime.now(timezone.utc)
    report = {
        "started_at": started_at.replace(microsecond=0).isoformat(),
        "finished_at": finished_at.replace(microsecond=0).isoformat(),
        "elapsed_seconds": round(time.perf_counter() - started_clock, 3),
        "queue": args.queue.as_posix(),
        "chunk_size": args.chunk_size,
        "force": args.force,
        "retry_incomplete": args.retry_incomplete,
        "selected_domains": sorted(selected_domains),
        "selected_candidate_ids": sorted(selected_candidate_ids),
        "attempted": len(rows),
        "status_counts": dict(sorted(status_counts.items())),
        "total_chunks": sum(int(row["chunk_count"]) for row in rows),
        "results": rows,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({key: report[key] for key in (
        "attempted", "status_counts", "total_chunks", "elapsed_seconds"
    )}, ensure_ascii=False, indent=2))
    return 1 if status_counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
