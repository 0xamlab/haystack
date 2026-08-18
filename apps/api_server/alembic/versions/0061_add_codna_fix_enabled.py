"""Add codna_fix_enabled — per-org kill switch for Codna's automatic fix pipeline.

Adds one column to ``organizations`` (``codna_fix_enabled``) so an org admin can turn off Codna's
automatic fix automation without disconnecting the GitHub App. Defaults ON (server_default true)
so existing installs keep their current behavior unchanged. Additive + reversible.

Revision ID: 0061
Revises: 0060
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "codna_fix_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "codna_fix_enabled")
