"""Add runtime lineage columns to decision_logs.

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-24

Persists manifest/policy/schema lineage directly on decision log records so
historical executions and logged decisions are queryable without parsing the
execution receipt blob.
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decision_logs",
        sa.Column("policy_snapshot_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "decision_logs",
        sa.Column("schema_snapshot_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "decision_logs",
        sa.Column("manifest_version", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_decision_logs_policy_snapshot_id",
        "decision_logs",
        ["policy_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_decision_logs_schema_snapshot_id",
        "decision_logs",
        ["schema_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "ix_decision_logs_manifest_version",
        "decision_logs",
        ["manifest_version"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_decision_logs_manifest_version", table_name="decision_logs")
    op.drop_index("ix_decision_logs_schema_snapshot_id", table_name="decision_logs")
    op.drop_index("ix_decision_logs_policy_snapshot_id", table_name="decision_logs")
    op.drop_column("decision_logs", "manifest_version")
    op.drop_column("decision_logs", "schema_snapshot_id")
    op.drop_column("decision_logs", "policy_snapshot_id")
