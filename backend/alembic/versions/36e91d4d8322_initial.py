"""initial

Revision ID: 36e91d4d8322
Revises: 
Create Date: 2026-07-19 19:35:32.596208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '36e91d4d8322'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_superuser", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # chat_sessions (FK -> users)
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(255)),
        sa.Column("session_type", sa.String(50)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # knowledge_bases (FK -> users)
    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("document_count", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # research_checkpoints (FK -> users)
    op.create_table(
        "research_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("iteration", sa.Integer()),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("ui_state_json", sa.JSON()),
        sa.Column("final_report", sa.Text()),
        sa.Column("status", sa.String(16)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # chat_messages (FK -> chat_sessions)
    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE")),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("thinking", sa.Text()),
        sa.Column("references_data", sa.JSON()),
        sa.Column("image_results", sa.JSON()),
        sa.Column("created_at", sa.DateTime()),
    )
    # documents (FK -> knowledge_bases + users)
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50)),
        sa.Column("file_size", sa.BigInteger()),
        sa.Column("file_path", sa.String(500)),
        sa.Column("source_name", sa.String(255)),
        sa.Column("source_url", sa.Text()),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("document_version", sa.String(64)),
        sa.Column("authority_level", sa.String(32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("license_name", sa.String(255)),
        sa.Column("license_url", sa.Text()),
        sa.Column("doi", sa.String(255)),
        sa.Column("external_id", sa.String(255)),
        sa.Column("retrieved_at", sa.DateTime()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("review_status", sa.String(32), nullable=False),
        sa.Column("claim_type", sa.String(64), nullable=False),
        sa.Column("is_open_access", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(50)),
        sa.Column("chunk_count", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # long_term_memories (FK -> users + chat_sessions)
    op.create_table(
        "long_term_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL")),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_insights", sa.JSON()),
        sa.Column("milvus_ids", sa.ARRAY(sa.Text())),
        sa.Column("token_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime()),
    )
    # chat_attachments (FK -> chat_messages + chat_sessions + users)
    op.create_table(
        "chat_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_messages.id", ondelete="CASCADE")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("content_text", sa.Text()),
        sa.Column("status", sa.String(20)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # ---- domain tables (no FK dependencies) ----
    op.create_table(
        "industry_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("industry_name", sa.String(100), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(50)),
        sa.Column("year", sa.Integer()),
        sa.Column("quarter", sa.Integer()),
        sa.Column("month", sa.Integer()),
        sa.Column("region", sa.String(50)),
        sa.Column("source", sa.String(200)),
        sa.Column("source_url", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "company_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("stock_code", sa.String(20)),
        sa.Column("industry", sa.String(100)),
        sa.Column("sub_industry", sa.String(100)),
        sa.Column("revenue", sa.Float()),
        sa.Column("net_profit", sa.Float()),
        sa.Column("gross_margin", sa.Float()),
        sa.Column("market_cap", sa.Float()),
        sa.Column("employees", sa.Integer()),
        sa.Column("market_share", sa.Float()),
        sa.Column("year", sa.Integer()),
        sa.Column("quarter", sa.Integer()),
        sa.Column("data_source", sa.String(200)),
        sa.Column("extra_data", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "policy_data",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_name", sa.String(500), nullable=False),
        sa.Column("policy_number", sa.String(100)),
        sa.Column("department", sa.String(200), nullable=False),
        sa.Column("level", sa.String(50)),
        sa.Column("publish_date", sa.Date()),
        sa.Column("effective_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("category", sa.String(100)),
        sa.Column("industry", sa.String(100)),
        sa.Column("summary", sa.Text()),
        sa.Column("key_points", postgresql.JSONB()),
        sa.Column("full_text_url", sa.Text()),
        sa.Column("impact_level", sa.String(20)),
        sa.Column("affected_entities", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "industry_news",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("industry_id", sa.String(50)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("source", sa.String(200)),
        sa.Column("source_url", sa.Text()),
        sa.Column("category", sa.String(50)),
        sa.Column("department", sa.String(200)),
        sa.Column("publish_time", sa.DateTime()),
        sa.Column("collected_at", sa.DateTime()),
        sa.Column("keywords", sa.String(500)),
        sa.Column("dedup_key", sa.String(64)),
        sa.Column("is_read", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "bidding_info",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("industry_id", sa.String(50)),
        sa.Column("bid_id", sa.String(100)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("notice_type", sa.String(50)),
        sa.Column("province", sa.String(50)),
        sa.Column("city", sa.String(50)),
        sa.Column("content", sa.Text()),
        sa.Column("publish_time", sa.DateTime()),
        sa.Column("source", sa.String(200)),
        sa.Column("collected_at", sa.DateTime()),
        sa.Column("dedup_key", sa.String(64)),
        sa.Column("parties", postgresql.JSONB()),
        sa.Column("is_read", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "news_collection_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20)),
        sa.Column("total_collected", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
    )
    # ---- indexes ----
    op.create_index("ix_bidding_info_bid_id", "bidding_info", ["bid_id"], unique=True)
    op.create_index("ix_bidding_info_notice_type", "bidding_info", ["notice_type"])
    op.create_index("ix_bidding_info_province", "bidding_info", ["province"])
    op.create_index("ix_bidding_info_publish_time", "bidding_info", ["publish_time"])
    op.create_index("ix_bidding_info_industry_id", "bidding_info", ["industry_id"])
    op.create_index("ix_bidding_info_dedup_key", "bidding_info", ["dedup_key"])
    op.create_index("ix_company_data_company_name", "company_data", ["company_name"])
    op.create_index("ix_company_data_industry", "company_data", ["industry"])
    op.create_index("ix_company_data_year", "company_data", ["year"])
    op.create_index("ix_industry_news_category", "industry_news", ["category"])
    op.create_index("ix_industry_news_industry_id", "industry_news", ["industry_id"])
    op.create_index("ix_industry_news_publish_time", "industry_news", ["publish_time"])
    op.create_index("ix_industry_news_dedup_key", "industry_news", ["dedup_key"])
    op.create_index("ix_industry_stats_industry_name", "industry_stats", ["industry_name"])
    op.create_index("ix_industry_stats_metric_name", "industry_stats", ["metric_name"])
    op.create_index("ix_industry_stats_year", "industry_stats", ["year"])
    op.create_index("ix_policy_data_department", "policy_data", ["department"])
    op.create_index("ix_policy_data_publish_date", "policy_data", ["publish_date"])
    op.create_index("ix_policy_data_category", "policy_data", ["category"])
    op.create_index("ix_policy_data_industry", "policy_data", ["industry"])


def downgrade() -> None:
    op.drop_table("chat_attachments")
    op.drop_table("long_term_memories")
    op.drop_table("documents")
    op.drop_table("chat_messages")
    op.drop_table("research_checkpoints")
    op.drop_table("knowledge_bases")
    op.drop_table("chat_sessions")
    op.drop_table("news_collection_tasks")
    op.drop_table("bidding_info")
    op.drop_table("industry_news")
    op.drop_table("policy_data")
    op.drop_table("company_data")
    op.drop_table("industry_stats")
    op.drop_table("users")
