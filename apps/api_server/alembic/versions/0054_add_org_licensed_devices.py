"""Per-device licensing — organizations.licensed_devices.

Per-device plans (algenta_pro / algenta_team) are billed by Stripe with usage=licensed, so the
subscription-item quantity IS the number of licensed devices. The webhook syncs that quantity into
this column and device-cap enforcement reads it as the org ceiling. Distinct from `seats` (people).

Default 0 = "not synced yet" → enforcement falls back to the static plan device cap, never a lockout;
existing paid algenta orgs re-sync their real quantity on the next customer.subscription.updated.
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "licensed_devices",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "licensed_devices")
