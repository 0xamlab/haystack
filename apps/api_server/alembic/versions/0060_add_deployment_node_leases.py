"""Add deployment_node_leases — the L3 connected-pool authority's per-node unit lease table.

For a CONNECTED server deployment, the control plane counts each engine node's leased Compute
Units against the deployment's pool (server-side, DB-backed — the connected equivalent of the
customer-run Relay ledger). A node is active while its heartbeat is within the census window; the
control plane admits a node only if the sum of active nodes' units stays within the deployment's
purchased ceiling.

Revision ID: 0060
Revises: 0059
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployment_node_leases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deployment_registration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_thumbprint", sa.String(128), nullable=False),
        sa.Column("granted_units", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["deployment_registration_id"],
            ["deployment_license_registrations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deployment_registration_id", "node_thumbprint", name="uq_deployment_node_lease"
        ),
    )
    op.create_index(
        "ix_deployment_node_leases_registration",
        "deployment_node_leases",
        ["deployment_registration_id"],
    )
    op.create_index(
        "ix_deployment_node_leases_node_thumbprint",
        "deployment_node_leases",
        ["node_thumbprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_deployment_node_leases_node_thumbprint", "deployment_node_leases")
    op.drop_index("ix_deployment_node_leases_registration", "deployment_node_leases")
    op.drop_table("deployment_node_leases")
