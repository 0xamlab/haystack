"""Add Cohenta plan values to the org_plan enum.

Cohenta joins the shared engine as a self-serve billable product with free/pro-runner/team tiers
(cohenta_free / cohenta_pro_runner / cohenta_team). ``organizations.plan`` is a NATIVE Postgres enum
(``org_plan``), so without this an attempt to set a Cohenta plan (e.g. a cohenta subscription's
checkout.session.completed setting org.plan='cohenta_pro_runner', or a lapse landing on
'cohenta_free') fails at the database with ``invalid input value for enum org_plan``. Unit tests
build a fresh DB from the models and so do not catch this — it only surfaces against the live
Supabase Postgres. Mirrors 0049_add_algenta_plans.py.

PostgreSQL requires ALTER TYPE ... ADD VALUE for enum extensions; IF NOT EXISTS makes it idempotent.

Revision ID: 0057
Revises: 0056
Create Date: 2026-07-14
"""

from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE is transactional in PG 12+. IF NOT EXISTS keeps it idempotent.
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'cohenta_free'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'cohenta_pro_runner'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'cohenta_team'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without a full type rebuild.
    # Downgrade is a no-op — the values simply won't be used.
    pass
