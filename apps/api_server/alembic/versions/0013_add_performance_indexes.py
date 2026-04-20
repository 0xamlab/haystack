"""Add performance indexes for 100k org workloads.

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-21

Indexes added:
  simulation_runs: (org_id, created_at DESC)  — list/filter by org, latest first
  simulation_runs: (org_id, status)           — status filter in runs list
  jobs:            (org_id, status)           — jobs list filter
  usage_records:   (org_id, billing_period)   — quota COUNT queries
  audit_events:    (org_id, created_at DESC)  — audit log pagination
  data_connectors: (org_id)                   — connector list
"""
from alembic import op

revision        = "0013"
down_revision   = "0012"
branch_labels   = None
depends_on      = None


def upgrade() -> None:
    # simulation_runs — most accessed table
    # Use raw SQL for DESC indexes since op.create_index doesn't support sort direction
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_simulation_runs_org_created "
        "ON simulation_runs USING btree (org_id, created_at DESC)"
    )
    op.create_index(
        "ix_simulation_runs_org_status",
        "simulation_runs",
        ["org_id", "status"],
        postgresql_using="btree",
        if_not_exists=True,
    )

    # jobs
    op.create_index(
        "ix_jobs_org_status",
        "jobs",
        ["org_id", "status"],
        postgresql_using="btree",
        if_not_exists=True,
    )

    # usage_records — quota COUNT queries hit this constantly
    op.create_index(
        "ix_usage_records_org_period",
        "usage_records",
        ["org_id", "billing_period"],
        postgresql_using="btree",
        if_not_exists=True,
    )

    # audit_events
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_events_org_created "
        "ON audit_events USING btree (org_id, created_at DESC)"
    )

    # data_connectors
    op.create_index(
        "ix_data_connectors_org",
        "data_connectors",
        ["org_id"],
        postgresql_using="btree",
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_data_connectors_org",        table_name="data_connectors")
    op.drop_index("ix_audit_events_org_created",   table_name="audit_events")
    op.drop_index("ix_usage_records_org_period",   table_name="usage_records")
    op.drop_index("ix_jobs_org_status",            table_name="jobs")
    op.drop_index("ix_simulation_runs_org_status", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_org_created",table_name="simulation_runs")
