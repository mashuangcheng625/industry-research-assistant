import os

import pytest

from scripts.validate_migration_roundtrip import (
    validate_database_url,
    validate_roundtrip,
)


@pytest.mark.parametrize(
    "database_url",
    [
        "",
        "sqlite:///industry_assistant_migration_test.db",
        "postgresql://postgres:secret@localhost/industry_assistant",
        "postgresql://postgres:secret@localhost/postgres",
    ],
)
def test_migration_validation_rejects_unsafe_database_urls(database_url):
    with pytest.raises(ValueError):
        validate_database_url(database_url)


def test_migration_validation_accepts_dedicated_postgres_database():
    database_url = (
        "postgresql://postgres:secret@localhost/industry_assistant_migration_test"
    )
    assert validate_database_url(database_url) == "industry_assistant_migration_test"


@pytest.mark.integration
def test_alembic_upgrade_downgrade_upgrade_roundtrip():
    database_url = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not database_url:
        pytest.skip("MIGRATION_TEST_DATABASE_URL is not configured")
    validate_roundtrip(database_url)
