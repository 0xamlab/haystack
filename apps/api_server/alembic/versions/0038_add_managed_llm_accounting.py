"""D3 managed-LLM accounting: org managed-LLM columns + the llm_usage_records spend ledger.

Adds two columns to ``organizations`` (``managed_llm_enabled``, ``managed_llm_quota_usd_month``)
and creates ``llm_usage_records`` — one row per platform-routed LLM call, recording dollar cost in
micro-dollars for per-org managed-spend attribution + capping. Additive + reversible; every column
defaults to off/0 so existing single-tenant + BYOK deployments are unaffected until an org is
explicitly opted into managed-LLM mode.

Revision ID: 0038
Revises: 0037
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "managed_llm_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "managed_llm_quota_usd_month",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "llm_usage_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "api_key_id",
            UUID(as_uuid=True),
            sa.ForeignKey("api_keys.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("billing_period", sa.String(length=7), nullable=False),
        sa.Column("backend", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("key_type", sa.String(length=16), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
        # Money column summed over a month — BigInteger to never risk an int4 overflow.
        sa.Column("cost_usd_micros", sa.BigInteger(), nullable=False, server_default="0"),
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
    op.create_index("ix_llm_usage_records_org_id", "llm_usage_records", ["org_id"])
    op.create_index(
        "ix_llm_usage_records_billing_period", "llm_usage_records", ["billing_period"]
    )
    # The hot read is "monthly managed spend for this org" — a composite index serves the SUM.
    op.create_index(
        "ix_llm_usage_records_org_period",
        "llm_usage_records",
        ["org_id", "billing_period"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_records_org_period", table_name="llm_usage_records")
    op.drop_index("ix_llm_usage_records_billing_period", table_name="llm_usage_records")
    op.drop_index("ix_llm_usage_records_org_id", table_name="llm_usage_records")
    op.drop_table("llm_usage_records")
    op.drop_column("organizations", "managed_llm_quota_usd_month")
    op.drop_column("organizations", "managed_llm_enabled")
