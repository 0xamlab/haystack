"""add_usage_records_table

Adds usage_records table for per-request billing unit tracking and quota enforcement.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-20 20:40:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create usage_endpoint enum idempotently using a DO block.
    # PostgreSQL doesn't support CREATE TYPE IF NOT EXISTS, so we use an
    # exception handler. This is safe whether or not the type already exists.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE usage_endpoint AS ENUM
                ('simulate', 'recommend', 'score', 'batch', 'compare', 'job');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    # Create usage_records table using raw SQL to avoid SQLAlchemy ORM
    # auto-creating the enum type again via _on_table_create events.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_records (
            id          UUID NOT NULL DEFAULT gen_random_uuid(),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            api_key_id  UUID REFERENCES api_keys(id) ON DELETE SET NULL,
            simulation_run_id UUID REFERENCES simulation_runs(id) ON DELETE SET NULL,
            billing_period VARCHAR(7) NOT NULL,
            endpoint    usage_endpoint NOT NULL,
            billing_units INTEGER NOT NULL DEFAULT 1,
            scenarios_run INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (id)
        )
        """
    )

    # Indexes for fast quota queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_usage_records_org_id "
        "ON usage_records (org_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_usage_records_billing_period "
        "ON usage_records (billing_period)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_usage_records_org_period "
        "ON usage_records (org_id, billing_period)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_usage_records_org_period")
    op.execute("DROP INDEX IF EXISTS ix_usage_records_billing_period")
    op.execute("DROP INDEX IF EXISTS ix_usage_records_org_id")
    op.execute("DROP TABLE IF EXISTS usage_records")
    op.execute("DROP TYPE IF EXISTS usage_endpoint")
