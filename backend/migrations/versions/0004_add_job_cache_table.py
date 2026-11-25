"""add job_cache table for dynamic job search

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_cache",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_platform", sa.String(length=50), nullable=False),
        sa.Column("search_query_hash", sa.String(length=64), nullable=False),
        sa.Column("job_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_platform", "search_query_hash", name="uq_job_cache_source_query"),
    )
    op.create_index(
        "ix_job_cache_created_at",
        "job_cache",
        ["created_at"],
        postgresql_where=sa.text("created_at > now() - interval '1 hour'"),
    )


def downgrade() -> None:
    op.drop_index("ix_job_cache_created_at", table_name="job_cache")
    op.drop_table("job_cache")
