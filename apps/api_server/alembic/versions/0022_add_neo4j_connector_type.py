"""Add neo4j connector_type enum value.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-17
"""

from alembic import op

revision = "0022"
down_revision = "0021"
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
                WHERE enumlabel = 'neo4j'
                  AND enumtypid = 'connector_type'::regtype
            ) THEN
                ALTER TYPE connector_type ADD VALUE 'neo4j';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values in-place.
    return
