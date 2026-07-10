"""Decision workflow columns — wire the aggregate to the DecisionService.

Adds the columns the workflow orchestration (services/decision_service) persists:
  * decision_revisions.pack_id + pack_input        — the reproducible framing payload
  * decision_execution_plans.revision_id           — staleness guard (plan vs current revision)
  * decision_execution_plans.nonce + nonce_consumed — single-use approval challenge
  * decision_approvals.plan_id                     — the plan an approval covers

Mirrors apps/api_server/models/decision_aggregate.py exactly.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("decision_revisions", sa.Column("pack_id", sa.String(128), nullable=True))
    op.add_column("decision_revisions", sa.Column("pack_input", postgresql.JSONB(), nullable=True))
    op.create_index("ix_decision_revisions_pack_id", "decision_revisions", ["pack_id"])

    op.add_column(
        "decision_execution_plans",
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("decision_execution_plans", sa.Column("nonce", sa.String(64), nullable=True))
    op.add_column(
        "decision_execution_plans",
        sa.Column("nonce_consumed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_decision_execution_plans_revision_id", "decision_execution_plans", ["revision_id"]
    )

    op.add_column(
        "decision_approvals", sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_decision_approvals_plan_id", "decision_approvals", ["plan_id"])
    # Idempotency keys are unique per org (when present) — closes the concurrent
    # find-then-create race in the approval flow.
    op.create_index(
        "uq_decision_approvals_org_idempotency",
        "decision_approvals",
        ["org_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_decision_approvals_org_idempotency", table_name="decision_approvals")
    op.drop_index("ix_decision_approvals_plan_id", table_name="decision_approvals")
    op.drop_column("decision_approvals", "plan_id")
    op.drop_index(
        "ix_decision_execution_plans_revision_id", table_name="decision_execution_plans"
    )
    op.drop_column("decision_execution_plans", "nonce_consumed")
    op.drop_column("decision_execution_plans", "nonce")
    op.drop_column("decision_execution_plans", "revision_id")
    op.drop_index("ix_decision_revisions_pack_id", table_name="decision_revisions")
    op.drop_column("decision_revisions", "pack_input")
    op.drop_column("decision_revisions", "pack_id")
