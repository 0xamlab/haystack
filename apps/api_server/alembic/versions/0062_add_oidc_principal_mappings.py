"""OIDC principal mappings — validated generic-OIDC identities → engine org/workspace.

Mirrors apps/api_server/models/oidc_principal.py. The unique (issuer, subject) index is the
resolver's O(1) lookup key. Unlike Entra's (tenant_id, principal_oid), there is no separate
tenant dimension: a generic OIDC issuer URL already encodes the full tenant/realm identity.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oidc_principal_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("principal_type", sa.String(8), nullable=False, server_default="user"),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_oidc_principal_mappings_id", "oidc_principal_mappings", ["id"])
    op.create_index("ix_oidc_principal_mappings_org_id", "oidc_principal_mappings", ["org_id"])
    op.create_index(
        "ix_oidc_principal_mappings_workspace_id", "oidc_principal_mappings", ["workspace_id"]
    )
    op.create_index("ix_oidc_principal_mappings_issuer", "oidc_principal_mappings", ["issuer"])
    op.create_index("ix_oidc_principal_mappings_subject", "oidc_principal_mappings", ["subject"])
    op.create_index("ix_oidc_principal_mappings_status", "oidc_principal_mappings", ["status"])
    op.create_index(
        "uq_oidc_principal_issuer_subject",
        "oidc_principal_mappings",
        ["issuer", "subject"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("oidc_principal_mappings")
