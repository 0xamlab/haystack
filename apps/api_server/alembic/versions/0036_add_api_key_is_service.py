"""Add is_service flag to api_keys — least-privilege service keys.

A service key (e.g. the agent's engine-callback key) is forced to the `viewer` role at
auth time (denied api-key/provider-key/member/billing management) AND granted a narrow,
org-scoped visibility allowance over REPOSITORY connectors only, so it can run the agent
callback without being attributed to (or carrying the privileges of) any human owner.

Phase 1 (additive, non-breaking): nullable=False with server_default false, so every
existing key reads back as a normal (non-service) key.

Revision ID: 0036
Revises: 0035
"""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "is_service",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "is_service")
