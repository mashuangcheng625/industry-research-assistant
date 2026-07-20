"""Align indexes and PostgreSQL JSON types with the ORM metadata.

Revision ID: 8c6f1f6e71c2
Revises: 36e91d4d8322
Create Date: 2026-07-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8c6f1f6e71c2"
down_revision: Union[str, Sequence[str], None] = "36e91d4d8322"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_JSONB_COLUMNS = (
    ("chat_messages", "references_data", True),
    ("chat_messages", "image_results", True),
    ("long_term_memories", "key_insights", True),
    ("research_checkpoints", "state_json", False),
    ("research_checkpoints", "ui_state_json", True),
)


def upgrade() -> None:
    for table_name, column_name, nullable in _JSONB_COLUMNS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.JSON(),
            type_=postgresql.JSONB(),
            existing_nullable=nullable,
            postgresql_using=f"{column_name}::jsonb",
        )

    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index(
        "ix_research_checkpoints_session_id",
        "research_checkpoints",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_research_checkpoints_session_id", table_name="research_checkpoints")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")

    for table_name, column_name, nullable in reversed(_JSONB_COLUMNS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=postgresql.JSONB(),
            type_=sa.JSON(),
            existing_nullable=nullable,
            postgresql_using=f"{column_name}::json",
        )
