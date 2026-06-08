"""add result_url to simulation_runs for object storage

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-21
"""

from alembic import op
from sqlalchemy import text

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        text("""
        ALTER TABLE simulation_runs
        ADD COLUMN IF NOT EXISTS result_url TEXT
    """)
    )


def downgrade() -> None:
    op.drop_column("simulation_runs", "result_url")
