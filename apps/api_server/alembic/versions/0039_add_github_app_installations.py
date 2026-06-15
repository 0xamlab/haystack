"""GitHub App installations — bind a GitHub App install to a codna org.

Creates ``github_app_installations`` (org_id FK, unique installation_id, cached
encrypted installation token + expiry). Additive + reversible; the table is inert
until the GitHub App is configured (``GITHUB_APP_*`` settings).

Revision ID: 0039
Revises: 0038
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_app_installations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("account_login", sa.String(length=255), nullable=True),
        sa.Column("account_type", sa.String(length=32), nullable=True),
        sa.Column("workspace_id", sa.String(length=255), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_github_app_installations_org_id", "github_app_installations", ["org_id"]
    )
    op.create_index(
        "ix_github_app_installations_installation_id",
        "github_app_installations",
        ["installation_id"],
        unique=True,
    )

    # Durable, first-writer-wins dedup of webhook deliveries (survives a Redis outage
    # + the multi-replica race that the best-effort Redis SETNX cannot).
    op.create_table(
        "github_webhook_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("delivery_id", sa.String(length=255), nullable=False),
        sa.Column("installation_id", sa.BigInteger(), nullable=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_github_webhook_deliveries_delivery_id",
        "github_webhook_deliveries",
        ["delivery_id"],
        unique=True,
    )
    op.create_index(
        "ix_github_webhook_deliveries_installation_id",
        "github_webhook_deliveries",
        ["installation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_github_webhook_deliveries_installation_id",
        table_name="github_webhook_deliveries",
    )
    op.drop_index(
        "ix_github_webhook_deliveries_delivery_id",
        table_name="github_webhook_deliveries",
    )
    op.drop_table("github_webhook_deliveries")
    op.drop_index(
        "ix_github_app_installations_installation_id",
        table_name="github_app_installations",
    )
    op.drop_index(
        "ix_github_app_installations_org_id", table_name="github_app_installations"
    )
    op.drop_table("github_app_installations")
