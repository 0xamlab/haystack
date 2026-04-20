"""Add decision_logs table for Decision Memory.

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-15

Stores every logged decision with its expected outcome and (later) actual outcome.
Enables the self-improving feedback loop: compare predicted vs. actual performance.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision      = "0016"
down_revision = "0015"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    op.create_table(
        "decision_logs",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("org_id",        UUID(as_uuid=True), nullable=False),  # no FK — auth layer enforces isolation
        sa.Column("run_id",        UUID(as_uuid=True), nullable=True),

        sa.Column("context",       sa.Text,            nullable=True),
        sa.Column("chosen_action", sa.String(200),     nullable=False),
        sa.Column("options_considered", sa.Text,       nullable=True),
        sa.Column("expected_value",    sa.Float,       nullable=True),
        sa.Column("confidence",        sa.Float,       nullable=True),
        sa.Column("rationale",         sa.Text,        nullable=True),

        sa.Column("risk_p5",  sa.Float, nullable=True),
        sa.Column("risk_p95", sa.Float, nullable=True),
        sa.Column("risk_pol", sa.Float, nullable=True),

        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("result_hash",  sa.String(64), nullable=True),

        sa.Column("actual_outcome",       sa.Float,                  nullable=True),
        sa.Column("outcome_delta",        sa.Float,                  nullable=True),
        sa.Column("outcome_notes",        sa.Text,                   nullable=True),
        sa.Column("outcome_recorded_at",  sa.DateTime(timezone=True), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_decision_logs_org_id",       "decision_logs", ["org_id"])
    op.create_index("ix_decision_logs_run_id",        "decision_logs", ["run_id"])
    op.create_index("ix_decision_logs_chosen_action", "decision_logs", ["chosen_action"])
    op.create_index("ix_decision_logs_request_hash",  "decision_logs", ["request_hash"])
    op.create_index("ix_decision_logs_result_hash",   "decision_logs", ["result_hash"])


def downgrade() -> None:
    op.drop_table("decision_logs")
