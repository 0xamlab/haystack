"""Provider-agnostic identity → org pointer (identity_org_links).

Maps a Supabase user (stable top-level JWT ``sub``) to their personal engine org, so GitHub / Google
/ Apple / Microsoft logins for the SAME Supabase account converge on ONE org. The unique
``supabase_uid`` index is the O(1) resolver key and makes first-login provisioning race-safe under
multi-replica (INSERT → IntegrityError → re-select the winner). Mirrors
apps/api_server/models/identity_org_link.py.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identity_org_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("supabase_uid", sa.String(64), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_identity_org_links_id", "identity_org_links", ["id"])
    op.create_index(
        "ix_identity_org_links_supabase_uid", "identity_org_links", ["supabase_uid"], unique=True
    )
    op.create_index("ix_identity_org_links_org_id", "identity_org_links", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_identity_org_links_org_id", table_name="identity_org_links")
    op.drop_index("ix_identity_org_links_supabase_uid", table_name="identity_org_links")
    op.drop_index("ix_identity_org_links_id", table_name="identity_org_links")
    op.drop_table("identity_org_links")
