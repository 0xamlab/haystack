"""add_jobs_table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-20 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE job_status AS ENUM ('queued', 'validating', 'running', 'completed', 'failed', 'cancelled', 'expired')"
    )
    op.execute(
        "CREATE TYPE webhook_status AS ENUM ('pending', 'delivered', 'failed', 'not_configured')"
    )

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("simulation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("queue_name", sa.String(100), nullable=False, server_default="default"),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "validating",
                "running",
                "completed",
                "failed",
                "cancelled",
                "expired",
                name="job_status",
                create_type=False,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column("callback_url", sa.String(2048), nullable=True),
        sa.Column(
            "callback_status",
            postgresql.ENUM(
                "pending",
                "delivered",
                "failed",
                "not_configured",
                name="webhook_status",
                create_type=False,
            ),
            nullable=False,
            server_default="not_configured",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("ttl_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_jobs_run_id", "jobs", ["run_id"])
    op.create_index("ix_jobs_org_id", "jobs", ["org_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    # Add QUEUED status to simulation_runs
    op.execute("ALTER TYPE run_status ADD VALUE IF NOT EXISTS 'queued'")


def downgrade() -> None:
    op.drop_table("jobs")
    op.execute("DROP TYPE IF EXISTS webhook_status")
    op.execute("DROP TYPE IF EXISTS job_status")
