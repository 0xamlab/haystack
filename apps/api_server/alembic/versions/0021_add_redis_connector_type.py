"""Add redis connector_type enum value.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-17
"""

from alembic import op

revision = "0021"
down_revision = "0020"
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
                WHERE enumlabel = 'redis'
                  AND enumtypid = 'connector_type'::regtype
            ) THEN
                ALTER TYPE connector_type ADD VALUE 'redis';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values in-place.
    return
