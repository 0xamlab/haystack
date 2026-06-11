"""Generalize jobs for non-simulation kinds (repository decision-plan / pipeline).

Wave B1 of the enterprise-hardening roadmap: take long repository runs off the
request path by reusing the async job lifecycle. Adds job_kind (default 'simulation'),
request_payload and result_payload (JSONB, nullable) to jobs, and makes run_id nullable
so repository jobs — which have no SimulationRun — can use the same lifecycle. Additive
and reversible; existing rows backfill to job_kind='simulation' and keep their run_id.

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("job_kind", sa.String(length=64), nullable=False, server_default="simulation"),
    )
    op.add_column("jobs", sa.Column("request_payload", postgresql.JSONB(), nullable=True))
    op.add_column("jobs", sa.Column("result_payload", postgresql.JSONB(), nullable=True))
    op.alter_column(
        "jobs",
        "run_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_index("ix_jobs_job_kind", "jobs", ["job_kind"])


def downgrade() -> None:
    op.drop_index("ix_jobs_job_kind", table_name="jobs")
    # Repository jobs (run_id IS NULL) are incompatible with the NOT NULL constraint;
    # drop them first so the rollback can restore the original schema.
    op.execute("DELETE FROM jobs WHERE run_id IS NULL")
    op.alter_column(
        "jobs",
        "run_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_column("jobs", "result_payload")
    op.drop_column("jobs", "request_payload")
    op.drop_column("jobs", "job_kind")
