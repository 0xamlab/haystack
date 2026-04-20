"""add deployments table for per-org cloud isolation

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-21
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="algenta_shared"),
        sa.Column("region", sa.String(64), nullable=False, server_default="algenta-shared"),
        sa.Column("status", sa.String(32), nullable=False, server_default="requested"),
        sa.Column("endpoint_url", sa.String(512), nullable=True),
        sa.Column("provisioning_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provisioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cloud_resource_ids", JSONB, nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("cost_usd_month_cents", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("billing_markup_pct", sa.Numeric(5, 2), nullable=False, server_default="20.0"),
        sa.Column("stripe_meter_event_id", sa.String(128), nullable=True),
        sa.Column("requested_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
    )

    # Index for fast org deployment lookup
    op.create_index("ix_deployments_org_id_status", "deployments", ["org_id", "status"])

    # Partial unique index: only one ACTIVE deployment per org
    op.execute("""
        CREATE UNIQUE INDEX uq_deployments_org_active
        ON deployments (org_id)
        WHERE status = 'active'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_deployments_org_active")
    op.drop_index("ix_deployments_org_id_status", "deployments")
    op.drop_table("deployments")
