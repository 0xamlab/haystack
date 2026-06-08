"""add_result_hash_to_simulation_runs

Adds SHA-256 result_hash column to simulation_runs for decision integrity.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-20 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add result_hash column — nullable (existing rows will have NULL, new rows get hash)
    op.add_column(
        "simulation_runs",
        sa.Column(
            "result_hash",
            sa.String(64),
            nullable=True,
            comment="SHA-256 fingerprint of decision output for tamper detection",
        ),
    )
    op.create_index("ix_simulation_runs_result_hash", "simulation_runs", ["result_hash"])


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_result_hash", "simulation_runs")
    op.drop_column("simulation_runs", "result_hash")
