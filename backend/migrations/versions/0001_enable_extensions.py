"""enable postgres extensions

Revision ID: 0001
Revises:
Create Date: 2026-11-24

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTENSIONS = ("pg_trgm", "pgcrypto", "vector")


def upgrade() -> None:
    """Upgrade schema."""
    for extension in EXTENSIONS:
        op.execute(f'CREATE EXTENSION IF NOT EXISTS "{extension}"')


def downgrade() -> None:
    """Keep shared PostgreSQL extensions installed when rolling back the app schema."""
