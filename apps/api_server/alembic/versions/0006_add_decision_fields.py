"""add_decision_fields_to_simulation_runs

Adds recommended_action, confidence, expected_value, probability_of_loss
to simulation_runs so the runs browser and analytics have real data.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-21
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use VARCHAR(20) — no custom enum needed; values are: proceed, caution, reject
    op.execute("""
        ALTER TABLE simulation_runs
            ADD COLUMN IF NOT EXISTS recommended_action VARCHAR(20),
            ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS expected_value DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS probability_of_loss DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS std_deviation DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS rationale TEXT
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE simulation_runs
            DROP COLUMN IF EXISTS recommended_action,
            DROP COLUMN IF EXISTS confidence,
            DROP COLUMN IF EXISTS expected_value,
            DROP COLUMN IF EXISTS probability_of_loss,
            DROP COLUMN IF EXISTS std_deviation,
            DROP COLUMN IF EXISTS rationale
    """)
