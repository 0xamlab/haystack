"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-03-20 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ENUMS ──────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE org_plan AS ENUM ('free', 'developer', 'pro', 'enterprise')")
    op.execute("CREATE TYPE org_status AS ENUM ('active', 'suspended', 'deleted')")
    op.execute("CREATE TYPE user_role AS ENUM ('owner', 'admin', 'member', 'viewer')")
    op.execute("CREATE TYPE user_status AS ENUM ('active', 'invited', 'suspended')")
    op.execute("CREATE TYPE api_key_status AS ENUM ('active', 'revoked')")
    op.execute("CREATE TYPE run_status AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled')")
    op.execute("CREATE TYPE execution_type AS ENUM ('sync', 'async')")
    op.execute("CREATE TYPE simulation_mode AS ENUM ('auto', 'expert')")

    # ── organizations ─────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "plan",
            postgresql.ENUM("free", "developer", "pro", "enterprise", name="org_plan", create_type=False),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("active", "suspended", "deleted", name="org_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"])

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("owner", "admin", "member", "viewer", name="user_role", create_type=False),
            nullable=False,
            server_default="owner",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("active", "invited", "suspended", name="user_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── api_keys ──────────────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(255), nullable=False, server_default="Default"),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("hashed_key", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "status",
            postgresql.ENUM("active", "revoked", name="api_key_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])
    op.create_index("ix_api_keys_hashed_key", "api_keys", ["hashed_key"])
    op.create_index("ix_api_keys_status", "api_keys", ["status"])

    # ── simulation_runs ───────────────────────────────────────────────────────
    op.create_table(
        "simulation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "mode",
            postgresql.ENUM("auto", "expert", name="simulation_mode", create_type=False),
            nullable=False,
        ),
        sa.Column("engine_version", sa.String(50), nullable=False, server_default="0.1.0"),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM("queued", "running", "completed", "failed", "cancelled", name="run_status", create_type=False),
            nullable=False,
            server_default="running",
        ),
        sa.Column(
            "execution_type",
            postgresql.ENUM("sync", "async", name="execution_type", create_type=False),
            nullable=False,
            server_default="sync",
        ),
        sa.Column("input_blob_ref", sa.String(512), nullable=True),
        sa.Column("output_blob_ref", sa.String(512), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("scenarios_run", sa.Integer, nullable=True),
        sa.Column("billing_units", sa.Integer, nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_simulation_runs_org_id", "simulation_runs", ["org_id"])
    op.create_index("ix_simulation_runs_status", "simulation_runs", ["status"])
    op.create_index("ix_simulation_runs_request_hash", "simulation_runs", ["request_hash"])


def downgrade() -> None:
    op.drop_table("simulation_runs")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("organizations")

    op.execute("DROP TYPE IF EXISTS simulation_mode")
    op.execute("DROP TYPE IF EXISTS execution_type")
    op.execute("DROP TYPE IF EXISTS run_status")
    op.execute("DROP TYPE IF EXISTS api_key_status")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("DROP TYPE IF EXISTS org_status")
    op.execute("DROP TYPE IF EXISTS org_plan")
