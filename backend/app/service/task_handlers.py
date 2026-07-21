"""Application task handlers registered by the persistent worker."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from core.async_tasks import TaskContext, TaskHandler
from core.database import SessionLocal
from models.chat import ChatAttachment
from models.knowledge import Document

logger = logging.getLogger(__name__)


def _process_document(payload: dict[str, Any]) -> dict[str, Any]:
    from service.docmind_service import process_document_with_docmind

    document_id = payload["document_id"]
    file_path = payload["file_path"]
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None:
            raise LookupError(f"document {document_id} no longer exists")
        document.status = "processing"
        document.error_message = None
        db.commit()
        try:
            result = process_document_with_docmind(
                file_path=file_path,
                file_name=document.filename,
                index_name=f"kb_{payload['kb_name']}".lower().replace(" ", "_"),
            )
            if not result.get("success"):
                raise RuntimeError(result.get("message") or "document processing failed")
            document.status = "completed"
            document.chunk_count = int(result.get("document_count", 0))
            document.error_message = None
            db.commit()
            Path(file_path).unlink(missing_ok=True)
            return {"document_id": document_id, "chunk_count": document.chunk_count}
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)[:2000]
            db.commit()
            raise
    finally:
        db.close()


async def process_document_task(context: TaskContext, payload: dict[str, Any]) -> dict[str, Any]:
    await context.raise_if_cancelled()
    return await asyncio.to_thread(_process_document, payload)


def _process_attachment(payload: dict[str, Any]) -> dict[str, Any]:
    attachment_id = payload["attachment_id"]
    file_path = payload["file_path"]
    db = SessionLocal()
    try:
        attachment = db.query(ChatAttachment).filter(ChatAttachment.id == attachment_id).first()
        if attachment is None:
            raise LookupError(f"attachment {attachment_id} no longer exists")
        attachment.status = "processing"
        attachment.error_message = None
        db.commit()
        try:
            extension = os.path.splitext(attachment.filename)[1].lower()
            if extension in {'.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.xml', '.csv', '.html'}:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                    content = handle.read()
            elif extension == ".pdf":
                content = f"[PDF 文件: {attachment.filename}]"
            elif extension in {".docx", ".doc"}:
                content = f"[Word 文件: {attachment.filename}]"
            elif extension in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
                content = f"[图片: {attachment.filename}]"
            else:
                content = f"[文件: {attachment.filename}]"
            attachment.content_text = content[:50000] + ("\n...[内容已截断]" if len(content) > 50000 else "")
            attachment.status = "completed"
            attachment.error_message = None
            db.commit()
            Path(file_path).unlink(missing_ok=True)
            return {"attachment_id": attachment_id, "content_chars": len(attachment.content_text)}
        except Exception as exc:
            attachment.status = "failed"
            attachment.error_message = str(exc)[:2000]
            db.commit()
            raise
    finally:
        db.close()


async def process_attachment_task(context: TaskContext, payload: dict[str, Any]) -> dict[str, Any]:
    await context.raise_if_cancelled()
    return await asyncio.to_thread(_process_attachment, payload)


async def run_research_task(context: TaskContext, payload: dict[str, Any]) -> dict[str, Any]:
    from router.research_router import acquire_research_run_lock, release_research_run_lock
    from service.deep_research_v2.service import DeepResearchV2Service

    await context.raise_if_cancelled()
    session_id = payload["session_id"]
    lock_token = await asyncio.to_thread(acquire_research_run_lock, session_id)
    try:
        service = DeepResearchV2Service(max_iterations=int(payload.get("max_iterations", 3)))
        return await service.research_sync(
            query=payload["query"],
            session_id=session_id,
            kb_name=payload.get("kb_name"),
            search_web=bool(payload.get("search_web", True)),
            search_local=bool(payload.get("search_local", False)),
        )
    finally:
        await asyncio.to_thread(release_research_run_lock, session_id, lock_token)


def get_task_handlers() -> dict[str, TaskHandler]:
    return {
        "document.process": process_document_task,
        "attachment.process": process_attachment_task,
        "research.run": run_research_task,
    }


__all__ = ["get_task_handlers"]
