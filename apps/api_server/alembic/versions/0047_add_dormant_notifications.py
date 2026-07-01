"""Add dormant_notifications — tracks dormant-account warning emails already sent (no double-send).

Revision ID: 0047
Revises: 0046
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dormant_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("notice_type", sa.String(20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", "notice_type", name="uq_dormant_notice"),
    )
    op.create_index("ix_dormant_notifications_email", "dormant_notifications", ["email"])


def downgrade() -> None:
    op.drop_index("ix_dormant_notifications_email", table_name="dormant_notifications")
    op.drop_table("dormant_notifications")
