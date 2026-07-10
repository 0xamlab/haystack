"""The versioned decision aggregate.

A business decision is an *object graph with immutable versions*, not a mutable record — so
it can be audited and reproduced, and so editing an assumption creates a NEW revision/run
rather than rewriting a decision that was already reviewed or approved.

    DecisionPack        reusable template (data contract, model, UI definition)
    DecisionCase        one actual business decision (mutable pointers: status, current revision)
    DecisionRevision    IMMUTABLE framing (objective, horizon, levers, constraints, assumptions)
    EvidenceSnapshot    exact sources + versions used for a run (retention-mode aware)
    AnalysisRun         IMMUTABLE model version + inputs + scenarios + computed outputs
    Recommendation      ranked result + structured explanation for a run
    Approval            separately-authenticated human sign-off (plan hash + nonce + role)
    ExecutionPlan       IMMUTABLE actions covered by an approval (lifecycle-tracked)
    Outcome             actual result + calibration feedback

Immutable entities are never updated in place; a material change spawns a new revision/run
and invalidates any prior approval. Enforced at the service layer; the schema records it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api_server.db.base import Base, TimestampMixin, UUIDMixin
from apps.api_server.models._mixins import OrgWorkspaceScopedMixin


class CaseStatus(StrEnum):
    draft = "draft"
    analyzing = "analyzing"
    recommended = "recommended"
    approved = "approved"
    executing = "executing"
    monitoring = "monitoring"
    closed = "closed"
    reopened = "reopened"


class AnalysisRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class RetentionMode(StrEnum):
    exploratory = "exploratory"  # no data snapshot; refs + hashes only
    governed = "governed"  # immutable evidence snapshot retained in the customer's Azure


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class ExecutionLifecycleState(StrEnum):
    draft = "draft"
    proposed = "proposed"
    approved = "approved"
    scheduled = "scheduled"
    executed = "executed"
    reconciled = "reconciled"
    failed_compensated = "failed_compensated"


class ChangeClass(StrEnum):
    material = "material"  # invalidates a prior approval; requires reapproval
    non_material = "non_material"


class DecisionPack(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """A registered, reusable Decision Pack template."""

    __tablename__ = "decision_packs"

    pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    descriptor: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="objective/levers/constraints/uncertainties/outcome_metrics"
    )
    model_version_ref: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    evidence_contract_version: Mapped[str | None] = mapped_column(String(256), nullable=True)


class DecisionCase(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """One actual business decision. Mutable pointers only — history lives in the revisions."""

    __tablename__ = "decision_cases"

    pack_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CaseStatus.draft.value, index=True
    )
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    current_revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<DecisionCase {self.id} status={self.status} rev={self.current_revision_number}>"


class DecisionRevision(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """IMMUTABLE framing snapshot. A material change creates a new revision, never a mutation."""

    __tablename__ = "decision_revisions"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pack_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    pack_input: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Full validated pack request payload (the reproducible framing)"
    )
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    levers: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    constraints: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    assumptions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    uncertainties: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    candidate_options: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    change_class: Mapped[str | None] = mapped_column(
        String(20), nullable=True, doc="material | non_material vs the prior revision"
    )
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class EvidenceSnapshot(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """Exact sources + versions used for a run. Retention-mode aware (exploratory vs governed)."""

    __tablename__ = "decision_evidence_snapshots"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    retention_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RetentionMode.exploratory.value
    )
    sources: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Source refs + versions + freshness (governed adds a blob ref)"
    )
    snapshot_ref: Mapped[str | None] = mapped_column(
        String(512), nullable=True, doc="Optional encrypted-snapshot object ref (governed mode)"
    )
    data_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_notes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class AnalysisRun(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """IMMUTABLE analysis run: model version + inputs + scenarios + computed outputs."""

    __tablename__ = "decision_analysis_runs"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    evidence_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    model_version_ref: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AnalysisRunStatus.queued.value, index=True
    )
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Host-independent result object (e.g. RenewalAllocationResult)"
    )
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reproducibility_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Recommendation(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """Ranked result + structured explanation derived from an AnalysisRun."""

    __tablename__ = "decision_recommendations"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    recommended_scenario_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ranked_options: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class Approval(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """Separately-authenticated human sign-off. Bound to an exact plan hash + revision + run.

    Never created by the LM/model. Requires plan_hash + single-use nonce + authenticated principal
    + role + idempotency key + expiration (+ optional step-up). A material revision after approval
    invalidates it (``status`` moves to ``expired``/``rejected`` and a new approval is required).
    """

    __tablename__ = "decision_approvals"
    __table_args__ = (
        # Idempotency keys are unique per org (when present) — see migration 0052.
        Index(
            "uq_decision_approvals_org_idempotency",
            "org_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, doc="The ExecutionPlan this approval covers"
    )
    plan_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nonce: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Single-use approval challenge"
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    approver_principal: Mapped[str | None] = mapped_column(String(256), nullable=True)
    approver_tenant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    required_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    step_up_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ApprovalStatus.pending.value, index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExecutionPlan(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """IMMUTABLE set of actions covered by an approval. Lifecycle-tracked; approve != execute."""

    __tablename__ = "decision_execution_plans"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True, doc="Revision the plan was proposed against"
    )
    actions: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Safe MVP actions: task list, export, worksheet, memo, Teams"
    )
    lifecycle_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ExecutionLifecycleState.draft.value, index=True
    )
    plan_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    nonce: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="Single-use approval challenge issued at propose time"
    )
    nonce_consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    receipt: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class Outcome(UUIDMixin, TimestampMixin, OrgWorkspaceScopedMixin, Base):
    """Actual result + calibration feedback recorded after the decision took effect."""

    __tablename__ = "decision_outcomes"

    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actual_metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    delta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
