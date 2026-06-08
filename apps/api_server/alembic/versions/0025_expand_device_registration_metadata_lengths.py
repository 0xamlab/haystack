"""Expand device registration metadata column lengths.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-19

Widen hostname_hash and sdk_version so realistic SDK/runtime registration
payloads do not fail with database truncation errors.
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "device_registrations",
        "hostname_hash",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        "device_registrations",
        "sdk_version",
        existing_type=sa.String(length=20),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "device_registrations",
        "sdk_version",
        existing_type=sa.String(length=128),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.alter_column(
        "device_registrations",
        "hostname_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
