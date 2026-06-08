"""Add hosted device binding token storage.

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-19

Persist a per-device hosted binding token hash so finite per-key hosted API
traffic can require a server-issued binding token after the first successful
device bind.
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_registrations",
        sa.Column(
            "binding_token_hash",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("device_registrations", "binding_token_hash")
