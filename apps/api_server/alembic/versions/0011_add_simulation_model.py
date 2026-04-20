"""add simulation_model column to simulation_runs

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-21
"""
from alembic import op
from sqlalchemy import text

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("""
        ALTER TABLE simulation_runs
        ADD COLUMN IF NOT EXISTS simulation_model VARCHAR(30) NOT NULL DEFAULT 'monte_carlo'
    """))
    bind.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_simulation_runs_simulation_model
        ON simulation_runs (simulation_model)
    """))


def downgrade() -> None:
    op.drop_index("ix_simulation_runs_simulation_model", "simulation_runs")
    op.drop_column("simulation_runs", "simulation_model")
