"""Add repository connector_type enum values.

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-29
"""

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for enum_value in (
        "github_repo",
        "gitlab_repo",
        "bitbucket_repo",
        "local_repo",
        "repo_archive",
    ):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum
                    WHERE enumlabel = '{enum_value}'
                      AND enumtypid = 'connector_type'::regtype
                ) THEN
                    ALTER TYPE connector_type ADD VALUE '{enum_value}';
                END IF;
            END$$;
            """
        )


def downgrade() -> None:
    # PostgreSQL does not support dropping enum values in-place.
    return
