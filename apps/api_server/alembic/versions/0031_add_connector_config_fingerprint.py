"""Add data_connectors.config_fingerprint for encryption-safe create-or-reuse dedupe.

config_json is now envelope-encrypted (random IV), so the old equality dedupe on
config_json no longer works. A deterministic SHA-256 fingerprint of the canonical
config provides a stable dedupe key. Additive + nullable; existing rows get a
fingerprint on next write.

Revision ID: 0031
Revises: 0030
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "data_connectors",
        sa.Column("config_fingerprint", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_data_connectors_config_fingerprint",
        "data_connectors",
        ["org_id", "config_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_connectors_config_fingerprint", table_name="data_connectors")
    op.drop_column("data_connectors", "config_fingerprint")
