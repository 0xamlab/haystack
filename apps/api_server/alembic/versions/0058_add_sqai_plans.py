"""Add SQAI runtime plan values to the org_plan enum.

SQAI registers as a product edition of the shared engine (product_registry "sqai" row) with
its own plan namespace (sqai_developer/sqai_pro/sqai_team). ``organizations.plan`` is a NATIVE
Postgres enum (``org_plan``), so without this an attempt to set an SQAI plan (e.g. onboarding
landing an org on sqai_developer, or a future SQAI subscription's checkout.session.completed
setting org.plan='sqai_pro') fails at the database with ``invalid input value for enum
org_plan``. Unit tests build a fresh DB from the models and so do not catch this — it only
surfaces against the live Postgres.

Mirrors 0042_add_telys_plans.py. PostgreSQL requires ALTER TYPE ... ADD VALUE for enum
extensions; IF NOT EXISTS makes it idempotent and safe to re-run.

Revision ID: 0058
Revises: 0057
Create Date: 2026-07-24
"""

from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE is transactional in PG 12+. IF NOT EXISTS keeps it idempotent.
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'sqai_developer'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'sqai_pro'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'sqai_team'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without a full type rebuild.
    # Downgrade is a no-op — the values simply won't be used.
    pass
