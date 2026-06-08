from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DecisionLogResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    id: str
    org_id: str
    run_id: str | None = None
    context: str | None = None
    chosen_action: str
    options_considered: list[str] | None = None
    expected_value: float | None = None
    confidence: float | None = None
    rationale: str | None = None
    risk_p5: float | None = None
    risk_p95: float | None = None
    risk_pol: float | None = None
    request_hash: str | None = None
    result_hash: str | None = None
    policy_snapshot_id: str | None = None
    schema_snapshot_id: str | None = None
    manifest_version: str | None = None
    actual_outcome: float | None = None
    outcome_delta: float | None = None
    outcome_notes: str | None = None
    outcome_recorded_at: datetime | None = None
    executed_at: datetime | None = None
    execution_status: str | None = None
    execution_webhook_url: str | None = None
    execution_response_code: int | None = None
    created_at: datetime
    updated_at: datetime


class DecisionListResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    decisions: list[DecisionLogResult] = Field(default_factory=list)
    total: int
    page: int
    limit: int
    pages: int
    page_size: int


class ExecutionReceiptResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    decision_id: str
    webhook_url: str
    execution_status: str
    response_code: int | None = None
    executed_at: datetime
    policy_snapshot_id: str
    schema_snapshot_id: str
    manifest_version: str
    payload_summary: dict[str, Any]
    safety_overridden: bool = False
