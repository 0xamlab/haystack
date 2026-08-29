"""Add capability_execution_plans -- approval-gate for execute_capability_service.

Track C1b of the ecosystem partnership plan: a capability whose catalog entry has
approval_required=True previously executed with no gate at all. This table gives
execute_capability_service a propose/approve/execute workflow (mirrors
decision_execution_plans + decision_approvals, collapsed into one row since there is no
revision/case concept for a single capability invocation to justify two tables).

Mirrors apps/api_server/models/capability_plane.py's CapabilityExecutionPlan exactly.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capability_execution_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("capability_id", sa.String(255), nullable=False),
        sa.Column("provider_id", sa.String(128), nullable=False),
        sa.Column("binding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("execution_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("input_json", postgresql.JSON(), nullable=True),
        sa.Column("manifest_hash", sa.String(128), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column(
            "nonce_consumed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("lifecycle_state", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("approver_principal", sa.String(256), nullable=True),
        sa.Column("required_role", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_json", postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["binding_id"], ["capability_bindings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["execution_session_id"], ["capability_execution_sessions.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_capability_execution_plans_id", "capability_execution_plans", ["id"])
    op.create_index(
        "ix_capability_execution_plans_org_id", "capability_execution_plans", ["org_id"]
    )
    op.create_index(
        "ix_capability_execution_plans_workspace_id",
        "capability_execution_plans",
        ["workspace_id"],
    )
    op.create_index(
        "ix_capability_execution_plans_capability_id",
        "capability_execution_plans",
        ["capability_id"],
    )
    op.create_index(
        "ix_capability_execution_plans_binding_id", "capability_execution_plans", ["binding_id"]
    )
    op.create_index(
        "ix_capability_execution_plans_execution_session_id",
        "capability_execution_plans",
        ["execution_session_id"],
    )
    op.create_index(
        "ix_capability_execution_plans_plan_hash", "capability_execution_plans", ["plan_hash"]
    )
    op.create_index(
        "ix_capability_execution_plans_lifecycle_state",
        "capability_execution_plans",
        ["lifecycle_state"],
    )
    op.create_index(
        "ix_capability_execution_plans_idempotency_key",
        "capability_execution_plans",
        ["idempotency_key"],
    )
    op.create_index(
        "uq_capability_execution_plans_org_idempotency",
        "capability_execution_plans",
        ["org_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("capability_execution_plans")
