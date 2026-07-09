"""Add the Algenta self-hosted (per-active-node) plan value to the org_plan enum.

Algenta self-hosting is priced PER ACTIVE NODE (not per seat) — once a customer runs the engine binary,
seats are unenforceable and the only enforceable unit is the running node (capped by the active-node-cap).
The new ``algenta_selfhost`` tier ($199/node) carries that model. ``organizations.plan`` is a NATIVE Postgres
enum (``org_plan``), so without this an attempt to set ``org.plan='algenta_selfhost'`` (a self-host
checkout's checkout.session.completed, or an admin provisioning a self-host org) fails at the database with
``invalid input value for enum org_plan``. Unit tests build a fresh DB from the models and so do not catch
this — it only surfaces against the live Supabase Postgres. Mirrors 0049_add_algenta_plans.py.

PostgreSQL requires ALTER TYPE ... ADD VALUE for enum extensions; IF NOT EXISTS makes it idempotent.

Revision ID: 0050
Revises: 0049
Create Date: 2026-07-08
"""

from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE is transactional in PG 12+. IF NOT EXISTS keeps it idempotent.
    op.execute("ALTER TYPE org_plan ADD VALUE IF NOT EXISTS 'algenta_selfhost'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without a full type rebuild.
    # Downgrade is a no-op — the value simply won't be used.
    pass
