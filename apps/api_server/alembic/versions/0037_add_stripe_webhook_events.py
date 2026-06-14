"""Add stripe_webhook_events — exactly-once Stripe webhook processing ledger.

The event_id PK gives idempotency: a duplicate webhook delivery conflicts on insert, so a billing
state transition is applied exactly once even though Stripe delivers at-least-once and retries.

Revision ID: 0037
Revises: 0036
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_webhook_events",
        sa.Column("event_id", sa.String(length=255), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")
