"""add subscriptions table for Stripe subscription tracking

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-21
"""
from alembic import op
from sqlalchemy import text

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            stripe_subscription_id VARCHAR(128) UNIQUE,
            stripe_customer_id VARCHAR(128),
            plan VARCHAR(32) NOT NULL DEFAULT 'free',
            status VARCHAR(32) NOT NULL DEFAULT 'active',
            current_period_start TIMESTAMPTZ,
            current_period_end TIMESTAMPTZ,
            cancel_at_period_end BOOLEAN NOT NULL DEFAULT false,
            canceled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_org_id ON subscriptions (org_id)"))
    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_stripe_subscription_id ON subscriptions (stripe_subscription_id)"))
    bind.execute(text("CREATE INDEX IF NOT EXISTS ix_subscriptions_stripe_customer_id ON subscriptions (stripe_customer_id)"))


def downgrade() -> None:
    op.drop_table("subscriptions")
