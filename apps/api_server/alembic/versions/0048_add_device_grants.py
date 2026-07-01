"""Add device_grants — OAuth 2.0 Device Authorization Grant (RFC 8628) state for CLI logins."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("device_code", sa.String(128), nullable=False),
        sa.Column("user_code", sa.String(16), nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code", name="uq_device_grants_device_code"),
        sa.UniqueConstraint("user_code", name="uq_device_grants_user_code"),
    )
    op.create_index("ix_device_grants_device_code", "device_grants", ["device_code"])
    op.create_index("ix_device_grants_user_code", "device_grants", ["user_code"])
    op.create_index("ix_device_grants_expires_at", "device_grants", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_device_grants_expires_at", table_name="device_grants")
    op.drop_index("ix_device_grants_user_code", table_name="device_grants")
    op.drop_index("ix_device_grants_device_code", table_name="device_grants")
    op.drop_table("device_grants")
