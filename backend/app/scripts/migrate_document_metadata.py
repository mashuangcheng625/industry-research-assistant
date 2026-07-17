"""为现有 PostgreSQL documents 表幂等增加文档治理元数据列。"""
import sys
from pathlib import Path

from sqlalchemy import text

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.database import engine


MIGRATION_STATEMENTS = [
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_name VARCHAR(255)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_url TEXT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_type VARCHAR(50) NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS published_at TIMESTAMP",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS document_version VARCHAR(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS authority_level VARCHAR(32) NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS license_name VARCHAR(255)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS license_url TEXT",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS doi VARCHAR(255)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS external_id VARCHAR(255)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMP",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS review_status VARCHAR(32) NOT NULL DEFAULT 'pending'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS claim_type VARCHAR(64) NOT NULL DEFAULT 'unknown'",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_open_access BOOLEAN NOT NULL DEFAULT FALSE",
    "CREATE INDEX IF NOT EXISTS ix_documents_content_hash ON documents(content_hash)",
    "CREATE INDEX IF NOT EXISTS ix_documents_doi ON documents(doi)",
]


def main() -> None:
    with engine.begin() as connection:
        for statement in MIGRATION_STATEMENTS:
            connection.execute(text(statement))
    print(f"文档元数据迁移完成，共检查 {len(MIGRATION_STATEMENTS)} 列")


if __name__ == "__main__":
    main()
