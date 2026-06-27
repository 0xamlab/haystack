"""Add Telys runtime plan values to the org_plan enum.

PR #265 added TELYS_DEVELOPER/TELYS_PRO/TELYS_TEAM to the Python OrgPlan enum but
shipped no DB migration. ``organizations.plan`` is a NATIVE Postgres enum
(``org_plan``), so without this an attempt to set a Telys plan (e.g. when a Telys
subscription's checkout.session.completed sets org.plan='telys_pro') fails at the
database with ``invalid input value for enum org_plan``. Unit tests build a fresh
DB from the models and so do not catch this — it only surfaces against the live
Supabase Postgres.

Mirrors 0015_add_team_plan.py. PostgreSQL requires ALTER TYPE ... ADD VALUE for
enum extensions; IF NOT EXISTS makes it idempotent and safe to re-run.

Revision ID: 0042
Revises: 0041
Create Date: 2026-06-27
"""

from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE is transactional in PG 12+. IF NOT EXISTS keeps it idempotent.
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'telys_developer'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'telys_pro'")
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'telys_team'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without a full type rebuild.
    # Downgrade is a no-op — the values simply won't be used.
    pass
