"""Add workspace sub-tenancy (workspace_id on org-scoped resources) + platform key flag.

Phase 1 (additive, non-breaking): nullable workspace_id on each org-scoped resource
table + composite (org_id, workspace_id) index, and is_platform on api_keys. NULL
workspace_id = org-wide (current behavior). Mission's company key becomes the
platform key and sends X-Workspace-Id; the engine partitions by it once enforced.

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

# Org-scoped tenant-RESOURCE tables (identity tables — users/api_keys/devices —
# stay org-level; workspace is a per-request runtime scope, not key ownership).
_RESOURCE_TABLES = [
    "data_connectors",
    "capability_bindings",
    "simulation_runs",
    "decision_logs",
    "jobs",
    "usage_records",
    "deployments",
    "audit_events",
]


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "is_platform",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    for table in _RESOURCE_TABLES:
        op.add_column(
            table,
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index(
            f"ix_{table}_org_workspace",
            table,
            ["org_id", "workspace_id"],
        )


def downgrade() -> None:
    for table in _RESOURCE_TABLES:
        op.drop_index(f"ix_{table}_org_workspace", table_name=table)
        op.drop_column(table, "workspace_id")
    op.drop_column("api_keys", "is_platform")
