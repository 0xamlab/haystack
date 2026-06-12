"""B10 PR11: per-tenant provider/engine key store (BYOK).

Creates ``tenant_provider_keys`` — one encrypted key per (org_id, backend). Provider backends
(openai/anthropic/...) plus the reserved ``algenta_engine`` backend for the single per-org engine
key. A UNIQUE (org_id, backend) constraint enforces one key per slot; ``encrypted_key`` holds
AES-256-GCM ciphertext (config_crypto). Additive + reversible; empty until an onboarding flow
(PR11c) populates it, so existing single-tenant/self-hosted deployments are unaffected.

Revision ID: 0035
Revises: 0034
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_provider_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("backend", sa.String(length=64), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_tenant_provider_keys_org_id", "tenant_provider_keys", ["org_id"]
    )
    op.create_unique_constraint(
        "uq_tenant_provider_keys_org_backend",
        "tenant_provider_keys",
        ["org_id", "backend"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_tenant_provider_keys_org_backend", "tenant_provider_keys", type_="unique"
    )
    op.drop_index("ix_tenant_provider_keys_org_id", table_name="tenant_provider_keys")
    op.drop_table("tenant_provider_keys")
