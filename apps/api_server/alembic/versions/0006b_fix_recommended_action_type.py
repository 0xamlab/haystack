"""fix_recommended_action_type_enum_to_varchar

The original migration 0006 created recommended_action as a PostgreSQL ENUM.
The SQLAlchemy model uses String(20) (VARCHAR). This migration casts the column
back to VARCHAR so inserts work correctly.

Revision ID: 0006b
Revises: 0006
Create Date: 2026-03-21
"""
from alembic import op

revision = "0006b"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cast recommended_action from custom ENUM type to VARCHAR if it exists as ENUM
    op.execute("""
        DO $$ BEGIN
            -- Only alter if the column is still the old ENUM type
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'simulation_runs'
                  AND column_name = 'recommended_action'
                  AND udt_name = 'recommended_action'
            ) THEN
                ALTER TABLE simulation_runs
                    ALTER COLUMN recommended_action TYPE VARCHAR(20)
                    USING recommended_action::TEXT;
            END IF;
        END $$
    """)
    # Drop the now-unused enum type (safe even if it doesn't exist)
    op.execute("DROP TYPE IF EXISTS recommended_action CASCADE")


def downgrade() -> None:
    # Nothing to do — VARCHAR is more permissive
    pass
