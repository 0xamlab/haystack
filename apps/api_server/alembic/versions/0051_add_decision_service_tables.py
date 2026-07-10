"""Add Decision Service tables — model registry + versioned decision aggregate.

Model registry (governed model provenance): model_artifacts, model_versions.
Versioned decision aggregate (immutable revisions/runs): decision_packs, decision_cases,
decision_revisions, decision_evidence_snapshots, decision_analysis_runs,
decision_recommendations, decision_approvals, decision_execution_plans, decision_outcomes.

Mirrors apps/api_server/models/{model_registry,decision_aggregate}.py exactly (org_id +
optional workspace_id sub-tenancy scoping; UUID PKs; JSONB payloads).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def _base_cols() -> list[sa.Column]:
    """id + timestamps + org/workspace scoping, shared by every Decision Service table."""
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    ]


def _scope_indexes(table: str) -> None:
    # UUIDMixin declares the id PK column with index=True, so SQLAlchemy emits a separate
    # ix_<table>_id index alongside the PK; mirror it here to match the model metadata exactly.
    op.create_index(f"ix_{table}_id", table, ["id"])
    op.create_index(f"ix_{table}_org_id", table, ["org_id"])
    op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])


def upgrade() -> None:
    # ── model registry ───────────────────────────────────────────────────────────────
    op.create_table(
        "model_artifacts",
        *_base_cols(),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("owner", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("model_artifacts")
    op.create_index("ix_model_artifacts_key", "model_artifacts", ["key"])

    op.create_table(
        "model_versions",
        *_base_cols(),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_ref", sa.String(256), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("pack_id", sa.String(128), nullable=True),
        sa.Column("input_schema", postgresql.JSONB(), nullable=True),
        sa.Column("output_schema", postgresql.JSONB(), nullable=True),
        sa.Column("units", postgresql.JSONB(), nullable=True),
        sa.Column("validity_ranges", postgresql.JSONB(), nullable=True),
        sa.Column("assumption_defaults", postgresql.JSONB(), nullable=True),
        sa.Column("calibration_dataset_ref", sa.String(256), nullable=True),
        sa.Column("calibration_status", sa.String(32), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False),
        sa.Column("known_limitations", postgresql.JSONB(), nullable=True),
        sa.Column("golden_test_result", postgresql.JSONB(), nullable=True),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("model_versions")
    op.create_index("ix_model_versions_artifact_id", "model_versions", ["artifact_id"])
    op.create_index("ix_model_versions_version_ref", "model_versions", ["version_ref"])
    op.create_index("ix_model_versions_pack_id", "model_versions", ["pack_id"])
    op.create_index("ix_model_versions_validation_status", "model_versions", ["validation_status"])
    op.create_index("ix_model_versions_content_hash", "model_versions", ["content_hash"])

    # ── versioned decision aggregate ─────────────────────────────────────────────────
    op.create_table(
        "decision_packs",
        *_base_cols(),
        sa.Column("pack_id", sa.String(128), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("descriptor", postgresql.JSONB(), nullable=True),
        sa.Column("model_version_ref", sa.String(256), nullable=True),
        sa.Column("evidence_contract_version", sa.String(256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_packs")
    op.create_index("ix_decision_packs_pack_id", "decision_packs", ["pack_id"])
    op.create_index("ix_decision_packs_model_version_ref", "decision_packs", ["model_version_ref"])

    op.create_table(
        "decision_cases",
        *_base_cols(),
        sa.Column("pack_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("owner", sa.String(200), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_revision_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_cases")
    op.create_index("ix_decision_cases_pack_id", "decision_cases", ["pack_id"])
    op.create_index("ix_decision_cases_status", "decision_cases", ["status"])

    op.create_table(
        "decision_revisions",
        *_base_cols(),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=True),
        sa.Column("levers", postgresql.JSONB(), nullable=True),
        sa.Column("constraints", postgresql.JSONB(), nullable=True),
        sa.Column("assumptions", postgresql.JSONB(), nullable=True),
        sa.Column("uncertainties", postgresql.JSONB(), nullable=True),
        sa.Column("candidate_options", postgresql.JSONB(), nullable=True),
        sa.Column("change_class", sa.String(20), nullable=True),
        sa.Column("inputs_hash", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_revisions")
    op.create_index("ix_decision_revisions_case_id", "decision_revisions", ["case_id"])
    op.create_index("ix_decision_revisions_inputs_hash", "decision_revisions", ["inputs_hash"])

    op.create_table(
        "decision_evidence_snapshots",
        *_base_cols(),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retention_mode", sa.String(20), nullable=False),
        sa.Column("sources", postgresql.JSONB(), nullable=True),
        sa.Column("snapshot_ref", sa.String(512), nullable=True),
        sa.Column("data_quality_score", sa.Integer(), nullable=True),
        sa.Column("evidence_notes", postgresql.JSONB(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_evidence_snapshots")
    op.create_index(
        "ix_decision_evidence_snapshots_case_id", "decision_evidence_snapshots", ["case_id"]
    )
    op.create_index(
        "ix_decision_evidence_snapshots_revision_id", "decision_evidence_snapshots", ["revision_id"]
    )
    op.create_index(
        "ix_decision_evidence_snapshots_content_hash", "decision_evidence_snapshots", ["content_hash"]
    )

    op.create_table(
        "decision_analysis_runs",
        *_base_cols(),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_version_ref", sa.String(256), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("inputs_hash", sa.String(64), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("result_hash", sa.String(64), nullable=True),
        sa.Column("reproducibility_id", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_analysis_runs")
    op.create_index("ix_decision_analysis_runs_case_id", "decision_analysis_runs", ["case_id"])
    op.create_index(
        "ix_decision_analysis_runs_revision_id", "decision_analysis_runs", ["revision_id"]
    )
    op.create_index(
        "ix_decision_analysis_runs_model_version_ref", "decision_analysis_runs", ["model_version_ref"]
    )
    op.create_index("ix_decision_analysis_runs_status", "decision_analysis_runs", ["status"])
    op.create_index(
        "ix_decision_analysis_runs_inputs_hash", "decision_analysis_runs", ["inputs_hash"]
    )
    op.create_index(
        "ix_decision_analysis_runs_result_hash", "decision_analysis_runs", ["result_hash"]
    )
    op.create_index(
        "ix_decision_analysis_runs_reproducibility_id",
        "decision_analysis_runs",
        ["reproducibility_id"],
    )

    op.create_table(
        "decision_recommendations",
        *_base_cols(),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommended_scenario_id", sa.String(64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ranked_options", postgresql.JSONB(), nullable=True),
        sa.Column("explanation", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.String(20), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_recommendations")
    op.create_index("ix_decision_recommendations_case_id", "decision_recommendations", ["case_id"])
    op.create_index("ix_decision_recommendations_run_id", "decision_recommendations", ["run_id"])
    op.create_index(
        "ix_decision_recommendations_content_hash", "decision_recommendations", ["content_hash"]
    )

    op.create_table(
        "decision_approvals",
        *_base_cols(),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("approver_principal", sa.String(256), nullable=True),
        sa.Column("approver_tenant", sa.String(128), nullable=True),
        sa.Column("required_role", sa.String(64), nullable=True),
        sa.Column("step_up_required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_approvals")
    op.create_index("ix_decision_approvals_case_id", "decision_approvals", ["case_id"])
    op.create_index("ix_decision_approvals_revision_id", "decision_approvals", ["revision_id"])
    op.create_index("ix_decision_approvals_plan_hash", "decision_approvals", ["plan_hash"])
    op.create_index(
        "ix_decision_approvals_idempotency_key", "decision_approvals", ["idempotency_key"]
    )
    op.create_index("ix_decision_approvals_status", "decision_approvals", ["status"])

    op.create_table(
        "decision_execution_plans",
        *_base_cols(),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actions", postgresql.JSONB(), nullable=True),
        sa.Column("lifecycle_state", sa.String(24), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=True),
        sa.Column("receipt", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_execution_plans")
    op.create_index(
        "ix_decision_execution_plans_case_id", "decision_execution_plans", ["case_id"]
    )
    op.create_index(
        "ix_decision_execution_plans_approval_id", "decision_execution_plans", ["approval_id"]
    )
    op.create_index(
        "ix_decision_execution_plans_lifecycle_state",
        "decision_execution_plans",
        ["lifecycle_state"],
    )
    op.create_index(
        "ix_decision_execution_plans_plan_hash", "decision_execution_plans", ["plan_hash"]
    )

    op.create_table(
        "decision_outcomes",
        *_base_cols(),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actual_metrics", postgresql.JSONB(), nullable=True),
        sa.Column("delta", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(200), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    _scope_indexes("decision_outcomes")
    op.create_index("ix_decision_outcomes_case_id", "decision_outcomes", ["case_id"])


def downgrade() -> None:
    for table in (
        "decision_outcomes",
        "decision_execution_plans",
        "decision_approvals",
        "decision_recommendations",
        "decision_analysis_runs",
        "decision_evidence_snapshots",
        "decision_revisions",
        "decision_cases",
        "decision_packs",
        "model_versions",
        "model_artifacts",
    ):
        op.drop_table(table)
