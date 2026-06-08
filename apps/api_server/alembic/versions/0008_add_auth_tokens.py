"""add email verification and password reset tokens

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return (result.scalar() or 0) > 0


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        text("SELECT COUNT(*) FROM pg_indexes WHERE indexname = :idx"), {"idx": index_name}
    )
    return (result.scalar() or 0) > 0


def upgrade() -> None:
    # Add columns only if they don't already exist (idempotent)
    if not _column_exists("users", "email_verification_token"):
        op.add_column("users", sa.Column("email_verification_token", sa.String(128), nullable=True))

    if not _column_exists("users", "email_verification_expires_at"):
        op.add_column(
            "users",
            sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists("users", "password_reset_token"):
        op.add_column("users", sa.Column("password_reset_token", sa.String(128), nullable=True))

    if not _column_exists("users", "password_reset_expires_at"):
        op.add_column(
            "users",
            sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Create indexes only if they don't already exist
    if not _index_exists("ix_users_email_verification_token"):
        op.create_index("ix_users_email_verification_token", "users", ["email_verification_token"])

    if not _index_exists("ix_users_password_reset_token"):
        op.create_index("ix_users_password_reset_token", "users", ["password_reset_token"])


def downgrade() -> None:
    if _index_exists("ix_users_password_reset_token"):
        op.drop_index("ix_users_password_reset_token", "users")
    if _index_exists("ix_users_email_verification_token"):
        op.drop_index("ix_users_email_verification_token", "users")
    if _column_exists("users", "password_reset_expires_at"):
        op.drop_column("users", "password_reset_expires_at")
    if _column_exists("users", "password_reset_token"):
        op.drop_column("users", "password_reset_token")
    if _column_exists("users", "email_verification_expires_at"):
        op.drop_column("users", "email_verification_expires_at")
    if _column_exists("users", "email_verification_token"):
        op.drop_column("users", "email_verification_token")
