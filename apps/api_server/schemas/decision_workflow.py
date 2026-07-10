"""Request/response schemas for the Decision Workflow API (/v1/decision-cases…).

Host-independent shapes: the M365/Excel/Foundry adapters render these objects; they are not
tied to any Microsoft surface. The analysis contract is async (202 + poll) so slow packs can
move to a worker later without changing clients.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CreateDecisionCaseRequest",
    "DecisionCaseResponse",
    "StartAnalysisRequest",
    "AnalysisRunAccepted",
    "AnalysisRunStatusResponse",
    "AnalysisResultResponse",
    "EvidenceResponse",
    "ExecutionPlanResponse",
    "ApproveRequest",
    "ApprovalResponse",
    "RecordOutcomeRequest",
    "OutcomeResponse",
]


class CreateDecisionCaseRequest(BaseModel):
    pack_id: str = Field(
        ..., min_length=1, max_length=128, examples=["renewal_capacity_allocation"]
    )
    title: str = Field(..., min_length=1, max_length=200)
    pack_input: dict[str, Any] = Field(..., description="The pack's contract input (validated)")
    owner: str | None = Field(None, max_length=200)
    objective: str | None = None
    horizon_days: int | None = Field(None, ge=1, le=730)


class DecisionCaseResponse(BaseModel):
    case_id: uuid.UUID
    pack_id: str
    title: str
    owner: str | None
    status: str
    current_revision_id: uuid.UUID | None
    current_revision_number: int
    inputs_hash: str | None = None


class StartAnalysisRequest(BaseModel):
    retention_mode: str = Field(
        "exploratory",
        pattern="^(exploratory|governed)$",
        description="exploratory = refs + hashes only; governed = retain inputs for reproduction",
    )


class AnalysisRunAccepted(BaseModel):
    run_id: uuid.UUID
    case_id: uuid.UUID
    status: str
    poll_url: str
    result_url: str


class AnalysisRunStatusResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    run_id: uuid.UUID
    case_id: uuid.UUID
    revision_id: uuid.UUID
    status: str
    model_version: str | None = None
    reproducibility_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class AnalysisResultResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    status: str
    reproducibility_id: str | None = None
    model_version: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class EvidenceResponse(BaseModel):
    evidence: dict[str, Any] | None
    provenance: dict[str, Any] | None
    reproducibility_id: str | None


class ExecutionPlanResponse(BaseModel):
    plan_id: uuid.UUID
    case_id: uuid.UUID
    run_id: uuid.UUID | None
    lifecycle_state: str
    plan_hash: str | None
    nonce: str | None = Field(
        None, description="Single-use approval challenge (present only at propose time)"
    )
    actions: dict[str, Any] | None
    receipt: dict[str, Any] | None = None


class ApproveRequest(BaseModel):
    plan_hash: str = Field(..., min_length=16, max_length=64)
    nonce: str = Field(..., min_length=8, max_length=64)
    idempotency_key: str | None = Field(None, max_length=128)


class ApprovalResponse(BaseModel):
    approval_id: uuid.UUID
    case_id: uuid.UUID
    plan_id: uuid.UUID | None
    status: str
    approver_principal: str | None
    decided_at: datetime | None


class RecordOutcomeRequest(BaseModel):
    run_id: uuid.UUID | None = None
    actual_metrics: dict[str, Any] = Field(..., description="e.g. {'retained_arr': 400000}")
    notes: str | None = None


class OutcomeResponse(BaseModel):
    outcome_id: uuid.UUID
    case_id: uuid.UUID
    run_id: uuid.UUID | None
    actual_metrics: dict[str, Any] | None
    delta: dict[str, Any] | None
    recorded_at: datetime | None
