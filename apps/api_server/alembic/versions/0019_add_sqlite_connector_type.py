"""Add sqlite connector_type enum value.

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-18
"""
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum
                WHERE enumlabel = 'sqlite'
                  AND enumtypid = 'connector_type'::regtype
            ) THEN
                ALTER TYPE connector_type ADD VALUE 'sqlite';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values in-place.
    return
