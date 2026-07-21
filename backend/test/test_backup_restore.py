import os

import pytest
from sqlalchemy.engine import make_url

from scripts.validate_backup_restore import (
    postgres_process_environment,
    validate_backup_restore,
    validate_database_url,
)


@pytest.mark.parametrize(
    "database_url",
    [
        "",
        "sqlite:///industry_assistant_backup_test.db",
        "postgresql://postgres:secret@localhost/industry_assistant",
        "postgresql://postgres:secret@localhost/postgres",
    ],
)
def test_backup_validation_rejects_unsafe_database_urls(database_url):
    with pytest.raises(ValueError):
        validate_database_url(database_url)


def test_backup_validation_accepts_dedicated_postgres_database():
    database_url = "postgresql://postgres:secret@localhost/industry_assistant_backup_test"
    assert validate_database_url(database_url).database == "industry_assistant_backup_test"


def test_postgres_process_environment_keeps_password_out_of_command_arguments():
    url = make_url(
        "postgresql://researcher:top-secret@db.example:5433/"
        "industry_assistant_backup_test?sslmode=require"
    )
    environment = postgres_process_environment(url)
    assert environment["PGHOST"] == "db.example"
    assert environment["PGPORT"] == "5433"
    assert environment["PGUSER"] == "researcher"
    assert environment["PGPASSWORD"] == "top-secret"
    assert environment["PGDATABASE"] == "industry_assistant_backup_test"
    assert environment["PGSSLMODE"] == "require"


@pytest.mark.integration
def test_postgres_backup_restore_drill():
    database_url = os.getenv("BACKUP_TEST_DATABASE_URL", "")
    if not database_url:
        pytest.skip("BACKUP_TEST_DATABASE_URL is not configured")
    result = validate_backup_restore(database_url)
    assert result["table_count"] == 15
    assert result["backup_size_bytes"] > 0
