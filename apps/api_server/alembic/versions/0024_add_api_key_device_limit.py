"""add_api_key_device_limit

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-19 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("device_limit", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "device_limit")
