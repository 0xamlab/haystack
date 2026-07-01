"""Make users.email unique PER ORG instead of globally (cross-org membership).

One person (single identity in Supabase) can now be a member of multiple orgs —
their own + any team they're invited to — and hold subscriptions across them.
Drops the global `users_email_key` unique constraint and adds a composite unique
constraint on (org_id, email). The non-unique `ix_users_email` index is kept.

Revision ID: 0044
Revises: 0043
Create Date: 2026-07-01
"""

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.create_unique_constraint("uq_users_org_email", "users", ["org_id", "email"])


def downgrade() -> None:
    # NOTE: reverting will FAIL if any email is now duplicated across orgs (expected
    # once cross-org membership is in use). De-dup first if you must roll back.
    op.drop_constraint("uq_users_org_email", "users", type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"])
