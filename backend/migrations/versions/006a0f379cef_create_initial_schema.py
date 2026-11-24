"""Reconcile the initial schema with the SQLAlchemy models.

Revision ID: 006a0f379cef
Revises: 0002
Create Date: 2026-11-24

"""
from collections.abc import Sequence

# Revision identifiers, used by Alembic.
revision: str = "006a0f379cef"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No schema changes were needed; revision 0002 already matches the models."""


def downgrade() -> None:
    """No schema changes were made by this reconciliation revision."""
