"""Wave-C: exactly-once billing — usage_key + partial-unique index on usage_records.

Adds a nullable ``usage_key`` (a logical-run idempotency key, e.g. ``sim:<run_id>``) and a PARTIAL
UNIQUE index over the non-NULL rows, so a retried persist upserts exactly ONE UsageRecord per
logical run (closing the Celery-retry under-bill + the fire-and-forget Stripe double-bill). NULL-
keyed rows (heartbeat / credits writers) are exempt from the constraint. The all-NULL new column
makes the index build instant, so no CONCURRENTLY is needed (and alembic wraps each migration in a
transaction, which CONCURRENTLY forbids). Additive + reversible.

Revision ID: 0034
Revises: 0033
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usage_records", sa.Column("usage_key", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_usage_records_usage_key",
        "usage_records",
        ["usage_key"],
        unique=True,
        postgresql_where=sa.text("usage_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_usage_records_usage_key", table_name="usage_records")
    op.drop_column("usage_records", "usage_key")
