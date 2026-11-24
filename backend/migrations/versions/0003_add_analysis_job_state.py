"""track asynchronous age-analysis jobs

Revision ID: 0003
Revises: 006a0f379cef
Create Date: 2026-11-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "006a0f379cef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_postings",
        sa.Column(
            "analysis_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column(
        "job_postings",
        sa.Column("analysis_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("job_postings", sa.Column("analysis_error", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_job_postings_analysis_status",
        "job_postings",
        "analysis_status IN ('pending', 'processing', 'completed', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_job_postings_analysis_status", "job_postings", type_="check")
    op.drop_column("job_postings", "analysis_error")
    op.drop_column("job_postings", "analysis_attempts")
    op.drop_column("job_postings", "analysis_status")
