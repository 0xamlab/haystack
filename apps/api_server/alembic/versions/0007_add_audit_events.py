"""add_audit_events_table

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-21
"""
from alembic import op

revision = "0007"
down_revision = "0006b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            actor_email VARCHAR(255) NOT NULL DEFAULT 'system',
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100),
            resource_id VARCHAR(64),
            ip_address VARCHAR(50),
            result VARCHAR(20) NOT NULL DEFAULT 'success',
            metadata_json TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_events_org_id ON audit_events (org_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_events_action ON audit_events (action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events (created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_events")
