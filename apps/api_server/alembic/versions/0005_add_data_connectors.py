"""add_data_connectors_table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-21

"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types idempotently, then create table via pure SQL
    # (avoids SQLAlchemy triggering CREATE TYPE again in create_table)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE connector_type AS ENUM (
                's3','gcs','azure','bigquery','snowflake','redshift',
                'postgres','mysql','mssql','rest','file'
            );
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE connector_status AS ENUM ('untested','live','error');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS data_connectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            connector_type connector_type NOT NULL,
            config_json TEXT,
            status connector_status NOT NULL DEFAULT 'untested',
            last_tested_at TIMESTAMPTZ,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_data_connectors_org_id
        ON data_connectors (org_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS data_connectors")
    op.execute("DROP TYPE IF EXISTS connector_status")
    op.execute("DROP TYPE IF EXISTS connector_type")
