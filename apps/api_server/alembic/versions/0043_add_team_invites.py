"""Add team_invites table for real seat-based team membership.

Revision ID: 0043
Revises: 0042
Create Date: 2026-07-01

Backs the /v1/team/invite + /v1/team/accept flow: an org admin invites an email
to a role; a pending row is created and an invite email is sent (Resend); the
invitee accepts via token and becomes a User(member) in the org. Seat limits are
enforced per plan (solo plans = 1 seat; team = per-seat; enterprise = unlimited).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        # opaque single-use accept token (store the value; it is not a secret beyond the email)
        sa.Column("token", sa.String(64), nullable=False),
        # pending | accepted | revoked | expired
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_team_invite_token"),
        # at most one live (pending) invite per email per org — partial unique index below
    )
    op.create_index("ix_team_invites_org_id", "team_invites", ["org_id"])
    op.create_index("ix_team_invites_email", "team_invites", ["email"])
    op.create_index(
        "uq_team_invite_pending_email",
        "team_invites",
        ["org_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_team_invite_pending_email", table_name="team_invites")
    op.drop_index("ix_team_invites_email", table_name="team_invites")
    op.drop_index("ix_team_invites_org_id", table_name="team_invites")
    op.drop_table("team_invites")
