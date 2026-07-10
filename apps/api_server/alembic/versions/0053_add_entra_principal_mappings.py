"""Entra principal mappings — validated Entra identities → engine org/workspace.

Mirrors apps/api_server/models/entra_principal.py. The unique (tenant_id, principal_oid)
index is the resolver's O(1) lookup key and prevents duplicate mappings for one principal.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entra_principal_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("principal_oid", sa.String(64), nullable=False),
        sa.Column("principal_type", sa.String(8), nullable=False, server_default="user"),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_entra_principal_mappings_id", "entra_principal_mappings", ["id"])
    op.create_index("ix_entra_principal_mappings_org_id", "entra_principal_mappings", ["org_id"])
    op.create_index(
        "ix_entra_principal_mappings_workspace_id", "entra_principal_mappings", ["workspace_id"]
    )
    op.create_index(
        "ix_entra_principal_mappings_tenant_id", "entra_principal_mappings", ["tenant_id"]
    )
    op.create_index(
        "ix_entra_principal_mappings_principal_oid", "entra_principal_mappings", ["principal_oid"]
    )
    op.create_index(
        "ix_entra_principal_mappings_status", "entra_principal_mappings", ["status"]
    )
    op.create_index(
        "uq_entra_principal_tenant_oid",
        "entra_principal_mappings",
        ["tenant_id", "principal_oid"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("entra_principal_mappings")
