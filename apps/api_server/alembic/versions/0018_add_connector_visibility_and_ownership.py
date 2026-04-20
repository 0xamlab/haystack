"""Add visibility and ownership metadata to data_connectors.

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-18
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("data_connectors", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "data_connectors",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="private"),
    )
    op.add_column(
        "data_connectors",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "data_connectors",
        sa.Column("owner_key_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_data_connectors_owner_user_id",
        "data_connectors",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_data_connectors_owner_key_id",
        "data_connectors",
        ["owner_key_id"],
        unique=False,
    )
    op.execute("UPDATE data_connectors SET visibility = 'private' WHERE visibility IS NULL")
    op.alter_column("data_connectors", "visibility", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_data_connectors_owner_key_id", table_name="data_connectors")
    op.drop_index("ix_data_connectors_owner_user_id", table_name="data_connectors")
    op.drop_column("data_connectors", "owner_key_id")
    op.drop_column("data_connectors", "owner_user_id")
    op.drop_column("data_connectors", "visibility")
    op.drop_column("data_connectors", "description")
