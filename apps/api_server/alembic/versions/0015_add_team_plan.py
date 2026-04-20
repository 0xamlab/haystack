"""Add 'team' value to org_plan enum.

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-13

Adds the TEAM pricing tier to the org_plan Postgres enum.
PostgreSQL requires ALTER TYPE ... ADD VALUE for enum extensions.
"""
from alembic import op

revision      = "0015"
down_revision = "0014"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # PostgreSQL ALTER TYPE ADD VALUE is transactional in PG 12+
    # but cannot be run inside a transaction block in older versions.
    # Use execute_if to be safe.
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'team'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without a full type rebuild.
    # Downgrade is a no-op — the value simply won't be used.
    pass
