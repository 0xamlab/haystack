"""Add Algenta engine plan values to the org_plan enum.

Algenta goes live as a first-class product with free/pro/team tiers (algenta_free / algenta_pro /
algenta_team). ``organizations.plan`` is a NATIVE Postgres enum (``org_plan``), so without this an attempt
to set an Algenta plan (e.g. a fresh ``algenta login`` landing an org on ``algenta_free``, or an Algenta
subscription's checkout.session.completed setting org.plan='algenta_pro') fails at the database with
``invalid input value for enum org_plan``. Unit tests build a fresh DB from the models and so do not catch
this — it only surfaces against the live Supabase Postgres. Mirrors 0042_add_telys_plans.py.

PostgreSQL requires ALTER TYPE ... ADD VALUE for enum extensions; IF NOT EXISTS makes it idempotent.

Revision ID: 0049
Revises: 0048
Create Date: 2026-07-08
"""

from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE is transactional in PG 12+. IF NOT EXISTS keeps it idempotent.
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'algenta_free'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'algenta_pro'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'algenta_team'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without a full type rebuild.
    # Downgrade is a no-op — the values simply won't be used.
    pass
