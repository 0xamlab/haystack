"""Add execution tracking columns to decision_logs.

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-15

Enables the execution adapter: POST /v1/decisions/{id}/execute fires the
decision to a webhook and records the receipt here for full audit trails.
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decision_logs", sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("decision_logs", sa.Column("execution_status", sa.String(20), nullable=True))
    op.add_column(
        "decision_logs", sa.Column("execution_webhook_url", sa.String(2048), nullable=True)
    )
    op.add_column(
        "decision_logs", sa.Column("execution_response_code", sa.Integer(), nullable=True)
    )
    op.add_column("decision_logs", sa.Column("execution_receipt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("decision_logs", "execution_receipt")
    op.drop_column("decision_logs", "execution_response_code")
    op.drop_column("decision_logs", "execution_webhook_url")
    op.drop_column("decision_logs", "execution_status")
    op.drop_column("decision_logs", "executed_at")
