"""将 sample-data 中的四份合成演示文档幂等导入对应知识库。"""
import argparse
import hashlib
from datetime import datetime
from pathlib import Path

from config.industry_config import INDUSTRY_CONFIGS
from core.database import SessionLocal
from models.knowledge import Document, KnowledgeBase
from models.user import User
from service.docmind_service import process_document_with_docmind
from service.embedding_router import collection_name_for_route, routes_for_ingestion
from service.milvus_service import get_milvus_service


SAMPLE_FILES = {
    "chip_design_eda_ip": "chip_design_ppa_regression_demo.md",
    "materials_equipment": "materials_equipment_traceability_demo.md",
    "wafer_fabrication": "semiconductor_process_anomaly_demo.md",
    "packaging_testing": "packaging_test_yield_demo.md",
}

SAMPLE_METADATA = {
    "source_name": "项目合成演示语料",
    "source_url": None,
    "document_type": "synthetic_case",
    "published_at": datetime(2026, 7, 15),
    "document_version": "demo-v1",
    "authority_level": "synthetic",
    "is_synthetic": True,
}


def ingest_sample(username: str, sample_dir: Path, direction_id: str, force: bool = False) -> str:
    config = INDUSTRY_CONFIGS[direction_id]
    file_path = sample_dir / SAMPLE_FILES[direction_id]
    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError(f"用户不存在: {username}")

        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.user_id == user.id,
            KnowledgeBase.name == config.knowledge_base_name,
        ).first()
        if not kb:
            raise ValueError(f"知识库不存在: {config.knowledge_base_name}")

        document = db.query(Document).filter(
            Document.knowledge_base_id == kb.id,
            Document.filename == file_path.name,
        ).first()
        if document and document.status == "completed" and not force:
            for field, value in SAMPLE_METADATA.items():
                setattr(document, field, value)
            db.commit()
            return f"{config.knowledge_base_name}: 已存在，跳过"

        if not document:
            document = Document(
                knowledge_base_id=kb.id,
                user_id=user.id,
                filename=file_path.name,
                file_type="md",
                file_size=file_path.stat().st_size,
                file_path=str(file_path),
                **SAMPLE_METADATA,
                status="processing",
            )
            db.add(document)
            kb.document_count = (kb.document_count or 0) + 1
        else:
            for field, value in SAMPLE_METADATA.items():
                setattr(document, field, value)
            document.status = "processing"
            document.error_message = None
        db.commit()

        if force:
            document_hash = hashlib.md5(file_path.name.encode()).hexdigest()
            base_collection = f"kb_{config.knowledge_base_name}"
            for route in routes_for_ingestion():
                get_milvus_service().delete_by_doc_id(
                    collection_name_for_route(base_collection, route),
                    document_hash,
                )

        result = process_document_with_docmind(
            file_path=str(file_path),
            file_name=file_path.name,
            index_name=f"kb_{config.knowledge_base_name}",
        )
        document.status = "completed" if result["success"] else "failed"
        document.chunk_count = result["document_count"]
        document.error_message = None if result["success"] else result["message"]
        db.commit()

        if not result["success"]:
            raise RuntimeError(f"{config.knowledge_base_name}: {result['message']}")
        return f"{config.knowledge_base_name}: {result['document_count']} 个切片"
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="导入半导体 RAG 合成演示文档")
    parser.add_argument("--username", required=True)
    parser.add_argument("--sample-dir", required=True, type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="删除同名旧切片后重新解析和向量化",
    )
    parser.add_argument(
        "--directions",
        nargs="+",
        choices=list(SAMPLE_FILES),
        default=list(SAMPLE_FILES),
    )
    args = parser.parse_args()

    for direction_id in args.directions:
        print(ingest_sample(
            args.username,
            args.sample_dir.resolve(),
            direction_id,
            force=args.force,
        ))


if __name__ == "__main__":
    main()
