"""Exercise pg_dump/pg_restore against a dedicated disposable database."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import URL, make_url

from core.database import Base
import models  # noqa: F401 -- register all ORM tables
from scripts.validate_migration_roundtrip import build_alembic_config


SAFE_DATABASE_SUFFIX = "_backup_test"
SENTINEL_USER_ID = uuid.UUID("8caee7d7-b837-4f54-8e0b-cbdba97f4285")


def validate_database_url(database_url: str) -> URL:
    if not database_url:
        raise ValueError("BACKUP_TEST_DATABASE_URL is required")

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("backup/restore validation requires PostgreSQL")
    if not (url.database or "").endswith(SAFE_DATABASE_SUFFIX):
        raise ValueError(
            f"test database name must end with {SAFE_DATABASE_SUFFIX!r}; "
            "refusing destructive restore validation"
        )
    return url


def postgres_process_environment(url: URL) -> dict[str, str]:
    """Build libpq environment variables without putting secrets in argv."""
    environment = os.environ.copy()
    values = {
        "PGHOST": url.host,
        "PGPORT": str(url.port) if url.port else None,
        "PGUSER": url.username,
        "PGPASSWORD": url.password,
        "PGDATABASE": url.database,
        "PGSSLMODE": url.query.get("sslmode"),
    }
    environment.update({key: value for key, value in values.items() if value})
    return environment


def _require_postgres_tools() -> tuple[str, str]:
    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        raise RuntimeError("pg_dump and pg_restore must both be installed")
    return pg_dump, pg_restore


def _assert_empty_database(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        tables = inspect(engine).get_table_names()
    finally:
        engine.dispose()
    if tables:
        raise RuntimeError(
            "backup test database must be empty; found: " + ", ".join(sorted(tables))
        )


def _snapshot(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return {
                table.name: connection.scalar(
                    select(func.count()).select_from(table)
                )
                for table in Base.metadata.sorted_tables
            }
    finally:
        engine.dispose()


def _insert_sentinel(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, username, email, hashed_password, is_active, is_superuser) "
                    "VALUES (:id, :username, :email, :password, true, false)"
                ),
                {
                    "id": SENTINEL_USER_ID,
                    "username": "backup_restore_sentinel",
                    "email": "backup-restore@example.invalid",
                    "password": "not-a-real-password-hash",
                },
            )
    finally:
        engine.dispose()


def _damage_database(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": SENTINEL_USER_ID})
            connection.execute(text("DROP TABLE company_data"))
    finally:
        engine.dispose()


def _assert_sentinel(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            restored = connection.execute(
                text("SELECT username, email FROM users WHERE id = :id"),
                {"id": SENTINEL_USER_ID},
            ).one_or_none()
    finally:
        engine.dispose()
    if restored is None or tuple(restored) != (
        "backup_restore_sentinel",
        "backup-restore@example.invalid",
    ):
        raise AssertionError("restored database does not contain the sentinel row")


def validate_backup_restore(database_url: str) -> dict[str, object]:
    url = validate_database_url(database_url)
    pg_dump, pg_restore = _require_postgres_tools()
    _assert_empty_database(database_url)

    alembic_config = build_alembic_config(database_url)
    command.upgrade(alembic_config, "head")
    _insert_sentinel(database_url)
    expected_snapshot = _snapshot(database_url)

    process_environment = postgres_process_environment(url)
    with tempfile.TemporaryDirectory(prefix="industry-backup-restore-") as temp_dir:
        backup_path = Path(temp_dir) / "database.dump"
        subprocess.run(
            [
                pg_dump,
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                f"--file={backup_path}",
            ],
            check=True,
            env=process_environment,
        )
        backup_size = backup_path.stat().st_size
        if backup_size == 0:
            raise AssertionError("pg_dump created an empty backup")
        backup_sha256 = hashlib.sha256(backup_path.read_bytes()).hexdigest()

        _damage_database(database_url)
        subprocess.run(
            [
                pg_restore,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                url.database or "",
                str(backup_path),
            ],
            check=True,
            env=process_environment,
        )

    restored_snapshot = _snapshot(database_url)
    if restored_snapshot != expected_snapshot:
        raise AssertionError(
            f"row-count snapshot changed after restore: "
            f"expected={expected_snapshot}, actual={restored_snapshot}"
        )
    _assert_sentinel(database_url)
    command.check(alembic_config)
    return {
        "database": url.database,
        "backup_size_bytes": backup_size,
        "backup_sha256": backup_sha256,
        "table_count": len(restored_snapshot),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("BACKUP_TEST_DATABASE_URL", ""),
        help="Dedicated PostgreSQL URL; database name must end in _backup_test.",
    )
    args = parser.parse_args()
    result = validate_backup_restore(args.database_url)
    print(
        "PostgreSQL backup/restore drill passed: "
        f"database={result['database']!r}, tables={result['table_count']}, "
        f"bytes={result['backup_size_bytes']}, sha256={result['backup_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
