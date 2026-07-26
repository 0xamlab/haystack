"""Add server (deployment-scope) plans + the deployment_license_registrations table.

Server/enterprise licensing is organization-DEPLOYMENT scope (Compute Units), distinct from the
per-device path. This migration:
  1. Extends the ``org_plan`` native enum with ``<edition>_server`` values so an org can hold a
     server plan (mirrors 0058's ADD VALUE pattern — IF NOT EXISTS = idempotent).
  2. Creates ``deployment_license_registrations`` — one row per licensed server deployment,
     bound to a deployment key thumbprint, carrying the purchased Compute-Unit ceiling. Kept
     separate from ``device_registrations`` so the two scopes never mix.

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None

_SERVER_PLANS = (
    "algenta_server",
    "codna_server",
    "telys_server",
    "sqai_server",
    "cohenta_server",
)


def upgrade() -> None:
    for plan in _SERVER_PLANS:
        op.execute(f"ALTER TYPE org_plan ADD VALUE IF NOT EXISTS '{plan}'")

    op.create_table(
        "deployment_license_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deployment_id", sa.String(128), nullable=False),
        sa.Column("product", sa.String(32), nullable=False, server_default=""),
        sa.Column("max_concurrent_units", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "deployment_pubkey_thumbprint", sa.String(128), nullable=False, server_default=""
        ),
        sa.Column("license_jti", sa.String(64), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "org_id", "deployment_id", name="uq_deployment_license_org_deployment_id"
        ),
    )
    op.create_index(
        "ix_deployment_license_registrations_org_id",
        "deployment_license_registrations",
        ["org_id"],
    )
    op.create_index(
        "ix_deployment_license_registrations_api_key_id",
        "deployment_license_registrations",
        ["api_key_id"],
    )
    op.create_index(
        "ix_deployment_license_registrations_deployment_id",
        "deployment_license_registrations",
        ["deployment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deployment_license_registrations_deployment_id", "deployment_license_registrations"
    )
    op.drop_index(
        "ix_deployment_license_registrations_api_key_id", "deployment_license_registrations"
    )
    op.drop_index(
        "ix_deployment_license_registrations_org_id", "deployment_license_registrations"
    )
    op.drop_table("deployment_license_registrations")
    # PostgreSQL cannot drop enum values without a full type rebuild — leave the plan values.
