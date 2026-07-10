"""Persistence-agnostic value objects for the Decision Service workflow.

These mirror the versioned decision aggregate (apps/api_server/models/decision_aggregate.py)
but are plain Pydantic records so the service logic and its unit tests do not depend on
SQLAlchemy or a database. The SQLAlchemy-backed repository maps between these and the ORM
rows; the in-memory repository stores them directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "DecisionCaseRecord",
    "RevisionRecord",
    "EvidenceRecord",
    "RunRecord",
    "RecommendationRecord",
    "ExecutionPlanRecord",
    "ApprovalRecord",
    "OutcomeRecord",
]


class _Base(BaseModel):
    # model_ fields (model_version_ref) collide with pydantic's protected namespace otherwise.
    model_config = ConfigDict(protected_namespaces=())

    id: uuid.UUID
    org_id: uuid.UUID
    workspace_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class DecisionCaseRecord(_Base):
    pack_id: str
    title: str
    owner: str | None = None
    status: str
    current_revision_id: uuid.UUID | None = None
    current_revision_number: int = 0


class RevisionRecord(_Base):
    case_id: uuid.UUID
    revision_number: int
    pack_id: str
    objective: str | None = None
    horizon_days: int | None = None
    levers: dict[str, Any] | None = None
    constraints: dict[str, Any] | None = None
    assumptions: dict[str, Any] | None = None
    uncertainties: dict[str, Any] | None = None
    candidate_options: dict[str, Any] | None = None
    pack_input: dict[str, Any] = Field(
        default_factory=dict, description="Full pack request payload"
    )
    change_class: str | None = None
    inputs_hash: str | None = None
    created_by: str | None = None


class EvidenceRecord(_Base):
    case_id: uuid.UUID
    revision_id: uuid.UUID
    retention_mode: str
    sources: dict[str, Any] | None = None
    snapshot_ref: str | None = None
    data_quality_score: int | None = None
    evidence_notes: list[str] | None = None
    content_hash: str | None = None


class RunRecord(_Base):
    case_id: uuid.UUID
    revision_id: uuid.UUID
    evidence_snapshot_id: uuid.UUID | None = None
    model_version_ref: str | None = None
    status: str
    inputs_hash: str | None = None
    result: dict[str, Any] | None = None
    result_hash: str | None = None
    reproducibility_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class RecommendationRecord(_Base):
    case_id: uuid.UUID
    run_id: uuid.UUID
    recommended_scenario_id: str | None = None
    summary: str | None = None
    ranked_options: dict[str, Any] | None = None
    explanation: dict[str, Any] | None = None
    confidence: str | None = None
    content_hash: str | None = None


class ExecutionPlanRecord(_Base):
    case_id: uuid.UUID
    run_id: uuid.UUID | None = None
    revision_id: uuid.UUID | None = None
    approval_id: uuid.UUID | None = None
    actions: dict[str, Any] | None = None
    lifecycle_state: str
    plan_hash: str | None = None
    # single-use approval challenge issued at propose time (not persisted to the ORM plan row;
    # the ORM stores it on the Approval when consumed)
    nonce: str | None = None
    nonce_consumed: bool = False
    receipt: dict[str, Any] | None = None


class ApprovalRecord(_Base):
    case_id: uuid.UUID
    revision_id: uuid.UUID
    run_id: uuid.UUID | None = None
    recommendation_id: uuid.UUID | None = None
    plan_id: uuid.UUID | None = None
    plan_hash: str
    nonce: str
    idempotency_key: str | None = None
    approver_principal: str | None = None
    approver_tenant: str | None = None
    required_role: str | None = None
    step_up_required: bool = False
    status: str
    expires_at: datetime | None = None
    decided_at: datetime | None = None


class OutcomeRecord(_Base):
    case_id: uuid.UUID
    run_id: uuid.UUID | None = None
    actual_metrics: dict[str, Any] | None = None
    delta: dict[str, Any] | None = None
    notes: str | None = None
    recorded_by: str | None = None
    recorded_at: datetime | None = None
