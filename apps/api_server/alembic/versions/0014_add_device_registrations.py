"""Add device_registrations table for multi-device SDK licensing.

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-13

Tracks which machines have registered under each API key.
Used for:
  - per-plan device limit enforcement
  - counting active devices per org
  - owner-initiated device revocation
  - 24h heartbeat tracking
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision      = "0014"
down_revision = "0013"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "device_registrations",
        sa.Column("id",               postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at",       sa.DateTime(timezone=True),    nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at",       sa.DateTime(timezone=True),    nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("org_id",           postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id",       postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id",        sa.String(64),  nullable=False),
        sa.Column("platform",         sa.String(50),  nullable=False, server_default=""),
        sa.Column("platform_version", sa.String(50),  nullable=False, server_default=""),
        sa.Column("hostname_hash",    sa.String(32),  nullable=False, server_default=""),
        sa.Column("sdk_version",      sa.String(20),  nullable=False, server_default=""),
        sa.Column("status",           sa.String(20),  nullable=False, server_default="active"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_count",  sa.Integer,     nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["org_id"],     ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"],      ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_id", "device_id", name="uq_device_per_api_key"),
    )
    op.create_index("ix_device_registrations_org_id",     "device_registrations", ["org_id"])
    op.create_index("ix_device_registrations_api_key_id", "device_registrations", ["api_key_id"])
    op.create_index("ix_device_registrations_device_id",  "device_registrations", ["device_id"])
    op.create_index("ix_device_org_status",               "device_registrations", ["org_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_device_org_status",               "device_registrations")
    op.drop_index("ix_device_registrations_device_id",  "device_registrations")
    op.drop_index("ix_device_registrations_api_key_id", "device_registrations")
    op.drop_index("ix_device_registrations_org_id",     "device_registrations")
    op.drop_table("device_registrations")
