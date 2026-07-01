"""Add proplus + ultra to the org_plan enum (the $60/$200 solo tiers).

`organizations.plan` is a NATIVE Postgres enum (org_plan); adding the Python
OrgPlan.PROPLUS/ULTRA values without this migration would fail at the DB with
``invalid input value for enum org_plan`` when a checkout sets the plan. Mirrors
0042_add_telys_plans.

Revision ID: 0045
Revises: 0044
Create Date: 2026-07-01
"""

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE is transactional in PG 12+. IF NOT EXISTS keeps it idempotent.
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'proplus'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'ultra'")


def downgrade() -> None:
    # Postgres cannot drop enum values; leaving them is harmless (no-op downgrade).
    pass
