"""Validate the complete Alembic chain against an isolated PostgreSQL database."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from core.database import Base
import models  # noqa: F401  -- register every ORM table on Base.metadata


SAFE_DATABASE_SUFFIX = "_migration_test"


def validate_database_url(database_url: str) -> str:
    """Return the database name after enforcing the destructive-test guard."""
    if not database_url:
        raise ValueError("MIGRATION_TEST_DATABASE_URL is required")

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("migration round-trip validation requires PostgreSQL")

    database_name = url.database or ""
    if not database_name.endswith(SAFE_DATABASE_SUFFIX):
        raise ValueError(
            f"test database name must end with {SAFE_DATABASE_SUFFIX!r}; "
            "refusing to run destructive migration validation"
        )
    return database_name


def build_alembic_config(database_url: str) -> Config:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _assert_clean_database(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        existing_tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    if existing_tables:
        raise RuntimeError(
            "migration test database must be empty; found: "
            + ", ".join(sorted(existing_tables))
        )


def _assert_head_and_tables(database_url: str, config: Config) -> None:
    expected_tables = set(Base.metadata.tables)
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names()) - {"alembic_version"}
        if actual_tables != expected_tables:
            missing = sorted(expected_tables - actual_tables)
            unexpected = sorted(actual_tables - expected_tables)
            raise AssertionError(
                f"migration table mismatch: missing={missing}, unexpected={unexpected}"
            )

        with engine.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
        expected_revision = ScriptDirectory.from_config(config).get_current_head()
        if current_revision != expected_revision:
            raise AssertionError(
                f"database revision {current_revision!r} != Alembic head {expected_revision!r}"
            )
    finally:
        engine.dispose()


def _assert_downgraded_to_base(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        remaining = set(inspect(engine).get_table_names()) - {"alembic_version"}
    finally:
        engine.dispose()
    if remaining:
        raise AssertionError(
            "downgrade base left application tables behind: "
            + ", ".join(sorted(remaining))
        )


def validate_roundtrip(database_url: str) -> None:
    """Run upgrade, drift detection, downgrade, and a second clean upgrade."""
    validate_database_url(database_url)
    _assert_clean_database(database_url)
    config = build_alembic_config(database_url)

    command.upgrade(config, "head")
    _assert_head_and_tables(database_url, config)
    command.check(config)

    command.downgrade(config, "base")
    _assert_downgraded_to_base(database_url)

    command.upgrade(config, "head")
    _assert_head_and_tables(database_url, config)
    command.check(config)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("MIGRATION_TEST_DATABASE_URL", ""),
        help="Dedicated PostgreSQL URL; database name must end in _migration_test.",
    )
    args = parser.parse_args()
    database_name = validate_database_url(args.database_url)
    validate_roundtrip(args.database_url)
    print(f"Alembic round-trip validation passed on isolated database {database_name!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
