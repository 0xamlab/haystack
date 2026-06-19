"""Repository-intelligence usage metering.

Adds the ``repository`` value to the ``usage_endpoint`` enum and two nullable
vertical-product dimensions (``product``, ``tool_name``) to ``usage_records`` so
the Codna coding-edition repo-intelligence tools can be metered and reported
per-product. Additive and backward-compatible (existing rows keep NULL dims).

Revision ID: 0040
Revises: 0039
Create Date: 2026-06-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Add 'repository' to the usage_endpoint enum (idempotent; mirrors 0021/0028).
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum
                    WHERE enumlabel = 'repository'
                      AND enumtypid = 'usage_endpoint'::regtype
                ) THEN
                    ALTER TYPE usage_endpoint ADD VALUE 'repository';
                END IF;
            END$$;
            """
        )
    # Vertical-product dimensions (nullable, additive). NULL for legacy/core rows.
    op.add_column("usage_records", sa.Column("product", sa.String(length=32), nullable=True))
    op.add_column("usage_records", sa.Column("tool_name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("usage_records", "tool_name")
    op.drop_column("usage_records", "product")
    # PostgreSQL does not support dropping an enum value in-place; 'repository' is left in place.
