"""Add organizations.seats for per-seat Team billing.

Synced from the Stripe subscription item quantity by the billing webhook; drives the
Team seat cap (invite enforcement). Defaults to 1 (solo plans).

Revision ID: 0046
Revises: 0045
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("seats", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("organizations", "seats")
