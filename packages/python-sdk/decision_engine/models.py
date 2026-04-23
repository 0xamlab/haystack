"""Pydantic response models for the Decision Engine SDK."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricsSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    expected_value: float
    median: float
    std_deviation: float
    variance: float
    probability_of_loss: float
    var_95: float | None = None
    cvar_95: float | None = None


class PercentileSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class RunMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    mode: str
    seed: int | None = None
    billing_units: int
    engine_version: str


class DecisionEnvelope(BaseModel):
    """Full decision output returned by simulate, recommend, and score endpoints."""

    model_config = ConfigDict(extra="allow", protected_namespaces=())

    run_id: uuid.UUID
    status: str
    engine_version: str
    recommended_action: str
    confidence: float
    rationale: str
    metrics: MetricsSummary
    percentiles: PercentileSummary
    scenarios_run: int
    execution_ms: int
    metadata: RunMetadata
    simulation_model: str | None = None
    engine_type: str | None = None
    simulation_class: str | None = None
    model_revision: str | None = None
    assumptions_hash: str | None = None
    validated_inputs: dict[str, Any] | None = None
    confidence_interval: dict[str, Any] | None = None
    request_id: str | None = None
    score: float | None = None
    score_breakdown: dict[str, Any] | None = None
    scenario_ranking: list[dict[str, Any]] | None = None
    sensitivity_ranking: list[dict[str, Any]] | None = None
    request_hash: str | None = None
    result_hash: str | None = None
    created_at: datetime | None = None


class QueryCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    column: str
    role: str
    magnitude: str | None = None
    formula: str | None = None
    confidence: float
    score_components: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ResolvedPlan(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_name: str
    metric_column: str
    aggregation: str
    group_column: str | None = None
    join_path: dict[str, Any] | None = None
    filter: dict[str, Any] | None = None
    limit: int | None = None
    order: str = "desc"
    constraints: dict[str, Any] = Field(default_factory=dict)
    schema_revision: str


class QueryResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    query_id: str
    result: Any = None
    result_type: str
    confidence: float
    plan: list[str]
    resolved_column: str
    resolved_role: str
    resolved_source: str
    row_count: int
    candidates: list[QueryCandidate] = Field(default_factory=list)
    source_scores: dict[str, float] = Field(default_factory=dict)
    ambiguous: bool
    exact_spec: bool
    explanation: list[str] = Field(default_factory=list)
    latency_ms: float
    decision_path: str
    plan_hash: str
    schema_revision: str | None = None
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    source_set: list[str] = Field(default_factory=list)
    join_path: list[dict[str, Any]] = Field(default_factory=list)
    planner_mode: str | None = None


class ResolveResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    resolved_plan: ResolvedPlan | None = None
    confidence: float
    plan: list[str]
    explanation: list[str] = Field(default_factory=list)
    resolved_column: str = ""
    resolved_role: str = ""
    resolved_source: str = ""
    candidates: list[QueryCandidate] = Field(default_factory=list)
    source_scores: dict[str, float] = Field(default_factory=dict)
    latency_ms: float
    decision_path: str
    plan_hash: str | None = None
    schema_revision: str
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    intent_signature: str
    source_set: list[str] = Field(default_factory=list)
    join_path: list[dict[str, Any]] = Field(default_factory=list)
    planner_mode: str | None = None


class VerifyResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    valid: bool
    errors: list[str]
    suggestions: list[str]
    resolved: dict[str, str]
    valid_dimensions: list[str] = Field(default_factory=list)
    valid_measures: list[str] = Field(default_factory=list)
    source_behavior: str = ""
    latency_ms: float
    verified: bool = False
    request_id: str | None = None
    schema_revision: str | None = None
    plan_hash: str | None = None
    verification_mode: str = "assist"
    rejection_reason: str | None = None


class SourceRegistrationResult(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    source_id: str | None = None
    dataset_id: str | None = None
    name: str | None = None
    dataset_name: str | None = None
    status: str
    ingest_mode: str | None = None
    source_schema: dict[str, Any] | None = Field(default=None, alias="schema")
    planner_cache_hit: bool | None = None
    planner_schema_revision: str | None = None
    planner_prewarm_ms: float | None = None
    latency_ms: float | None = None


class ExplainResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_set: list[str] = Field(default_factory=list)
    join_path: list[dict[str, Any]] = Field(default_factory=list)
    planner_mode: str
    decision_path: str
    plan_hash: str | None = None
    schema_revision: str | None = None
    validated: bool
    clarification_required: bool = False
    rejection_reason: str | None = None
    resolved_source: str = ""
    resolved_column: str = ""
    resolved_role: str = ""
    confidence: float = 0.0
    confidence_source: str | None = None
    deterministic_scope: str | None = None
    plan: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    request_id: str | None = None


class JobStatus(BaseModel):
    """Job status returned by poll endpoint."""

    model_config = ConfigDict(extra="allow")

    job_id: uuid.UUID
    run_id: uuid.UUID
    org_id: uuid.UUID
    status: str
    queue_name: str
    retry_count: int
    callback_url: str | None = None
    callback_status: str
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    ttl_expires_at: datetime | None = None
    poll_url: str


class JobSubmitResponse(BaseModel):
    """Returned immediately on async job submission."""

    model_config = ConfigDict(extra="allow")

    job_id: uuid.UUID
    run_id: uuid.UUID
    status: str
    poll_url: str
    message: str = ""


class BatchItemResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    index: int
    success: bool
    envelope: DecisionEnvelope | None = None
    error: str | None = None


class BatchResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    total: int
    succeeded: int
    failed: int
    results: list[BatchItemResult]


class APIKeyInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: uuid.UUID
    label: str
    key_prefix: str
    status: str
    created_at: datetime
    last_used_at: datetime | None = None


class UsageInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    org_id: uuid.UUID
    billing_period: str
    simulations_run: int
    api_calls: int
    quota_limit: int
    quota_used_pct: float
