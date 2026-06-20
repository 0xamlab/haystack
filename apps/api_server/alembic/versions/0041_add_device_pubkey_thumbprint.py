"""Device activation binding — public-key thumbprint.

Adds a nullable-default ``device_pubkey_thumbprint`` column to ``device_registrations`` so
an activation can be bound to a per-machine Ed25519 keypair (the private key never leaves
the device; renewal proves possession by signing a nonce). Additive and backward-compatible
— existing rows default to '' (unbound / legacy fingerprint-only clients).

Revision ID: 0041
Revises: 0040
Create Date: 2026-06-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "device_registrations",
        sa.Column(
            "device_pubkey_thumbprint",
            sa.String(length=128),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("device_registrations", "device_pubkey_thumbprint")
