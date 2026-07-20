"""Apply Alembic migrations after rejecting unversioned legacy schemas."""

from __future__ import annotations

from alembic import command
from sqlalchemy import inspect

from core.database import engine
from scripts.validate_migration_roundtrip import build_alembic_config


def main() -> int:
    existing_tables = set(inspect(engine).get_table_names())
    if existing_tables and "alembic_version" not in existing_tables:
        raise RuntimeError(
            "database contains an unversioned legacy schema; refusing to guess its "
            "migration state. Back up the PostgreSQL volume, then either migrate the "
            "legacy schema explicitly or recreate the local demo volume. Do not stamp "
            "head without comparing the schema."
        )

    command.upgrade(build_alembic_config(""), "head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
