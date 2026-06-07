"""Add capability_authorization_sessions.workspace_id for durable sub-tenancy scoping.

The OAuth/authorization session previously carried only org_id, so the cross-workspace
guard on the complete-authorization path relied transitively on the binding's workspace
gate. This adds an independent workspace_id (nullable for legacy rows) so the session is
directly workspace-scoped, matching every other org-scoped resource. Additive + nullable;
existing rows stay NULL (org-wide / pre-migration).

Revision ID: 0032
Revises: 0031
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capability_authorization_sessions",
        sa.Column("workspace_id", sa.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_capability_authorization_sessions_org_workspace",
        "capability_authorization_sessions",
        ["org_id", "workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_capability_authorization_sessions_org_workspace",
        table_name="capability_authorization_sessions",
    )
    op.drop_column("capability_authorization_sessions", "workspace_id")
