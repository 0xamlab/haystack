from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api_server.schemas.response import DecisionEnvelope, DecisionPlan


class RepositoryArtifactRef(BaseModel):
    model_config = ConfigDict(strict=False)

    artifact_id: str
    artifact_kind: str
    content_hash: str
    storage_path: str
    schema_revision: str | None = None
    created_at: datetime


class RepositoryDiagnostic(BaseModel):
    model_config = ConfigDict(strict=False)

    path: str | None = None
    line: int | None = Field(default=None, ge=1)
    severity: Literal["info", "warning", "error"] = "error"
    code: str | None = None
    message: str


class RepositorySignals(BaseModel):
    model_config = ConfigDict(strict=False)

    issue_text: str | None = None
    diagnostics: list[RepositoryDiagnostic] = Field(default_factory=list)
    failing_tests: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)
    workspace_context: list[str] = Field(default_factory=list)


class RepositorySnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    ref: str | None = None
    focus_paths: list[str] = Field(default_factory=list)
    prefer_concrete_focus_paths: bool = False
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    max_files: int = Field(default=20_000, ge=1, le=200_000)
    max_file_size_bytes: int = Field(default=1_000_000, ge=1024, le=10_000_000)
    max_total_bytes: int | None = Field(default=None, ge=1_024, le=500_000_000)


class RepositorySnapshotResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    repository_id: str
    snapshot_id: str
    connector_type: str
    ref: str | None = None
    resolved_revision: str
    content_hash: str
    status: Literal["created", "existing"]
    created_at: datetime
    file_count: int
    requested_focus_paths: list[str] = Field(default_factory=list)
    effective_focus_paths: list[str] = Field(default_factory=list)
    language_counts: dict[str, int]
    raw_repo_token_estimate: int
    repository_snapshot_artifact: RepositoryArtifactRef
    repository_graph_artifact: RepositoryArtifactRef
    symbol_graph_artifact: RepositoryArtifactRef
    dependency_graph_artifact: RepositoryArtifactRef
    # AR-OPT-2: optional so v1 snapshots created before the slim-manifest work
    # (which have no symbol-reference Parquet artifact) still validate.
    symbol_reference_artifact: RepositoryArtifactRef | None = None


class RepositoryLanguageSupportProgress(BaseModel):
    model_config = ConfigDict(strict=False)

    supported_real_language_count: int = Field(..., ge=0)
    ranked_target_language_count: int = Field(..., ge=1)
    progress_fraction: float = Field(..., ge=0.0, le=1.0)
    progress_label: str


class RepositoryIntelligenceCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    supported_languages: list[str] = Field(default_factory=list)
    support_progress: RepositoryLanguageSupportProgress


class RepositoryEvidenceItem(BaseModel):
    model_config = ConfigDict(strict=False)

    evidence_id: str
    rank: int = Field(..., ge=1)
    source_type: Literal[
        "diagnostic", "failing_test", "changed_file", "workspace_context", "repository_file"
    ]
    source_ref: str
    file_path: str | None = None
    symbol_name: str | None = None
    summary: str
    snippet: str
    token_count: int = Field(..., ge=0)
    score: float = Field(..., ge=0.0)


class RepositoryTriageRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    snapshot_id: str
    signals: RepositorySignals
    max_evidence_items: int = Field(default=16, ge=1, le=64)
    max_snippet_lines: int = Field(default=40, ge=5, le=200)
    token_budget: int = Field(default=6_000, ge=256, le=32_000)


class RepositoryTriageResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    repository_id: str
    snapshot_id: str
    workspace_evidence_bundle_ref: str
    created_at: datetime
    suspect_files: list[str] = Field(default_factory=list)
    suspect_symbols: list[str] = Field(default_factory=list)
    raw_repo_token_estimate: int = Field(..., ge=0)
    evidence_bundle_token_count: int = Field(..., ge=0)
    reduction_ratio: float = Field(..., ge=1.0)
    evidence_items: list[RepositoryEvidenceItem] = Field(default_factory=list)
    workspace_evidence_bundle_artifact: RepositoryArtifactRef


class RepositoryGraphQueryRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    snapshot_id: str | None = None
    file_path: str | None = None
    symbol_name: str | None = None
    workspace_evidence_bundle_ref: str | None = None
    direction: Literal["inbound", "outbound", "both"] = "both"
    max_depth: int = Field(default=2, ge=1, le=6)
    max_nodes: int = Field(default=128, ge=1, le=1024)

    @model_validator(mode="after")
    def _validate_seed_source(self) -> RepositoryGraphQueryRequest:
        if self.snapshot_id or self.workspace_evidence_bundle_ref:
            return self
        raise ValueError(
            "snapshot_id or workspace_evidence_bundle_ref is required for graph queries."
        )


class RepositoryGraphEdge(BaseModel):
    model_config = ConfigDict(strict=False)

    source_file: str
    target_file: str
    edge_type: str


class RepositoryGraphNode(BaseModel):
    model_config = ConfigDict(strict=False)

    file_path: str
    depth: int = Field(..., ge=0)
    is_seed: bool = False
    inbound_count: int = Field(..., ge=0)
    outbound_count: int = Field(..., ge=0)
    risk_score: float = Field(..., ge=0.0)
    contained_symbols: list[str] = Field(default_factory=list)
    parent_child_symbols: list[str] = Field(default_factory=list)


class RepositoryGraphImpactItem(BaseModel):
    model_config = ConfigDict(strict=False)

    file_path: str
    depth: int = Field(..., ge=0)
    relationship: Literal["seed", "dependent", "dependency", "connected"]
    risk_score: float = Field(..., ge=0.0)
    top_symbol: str | None = None


class RepositoryGraphQueryResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    repository_id: str
    snapshot_id: str
    created_at: datetime
    seed_file_paths: list[str] = Field(default_factory=list)
    seed_symbols: list[str] = Field(default_factory=list)
    direct_dependencies: list[str] = Field(default_factory=list)
    direct_dependents: list[str] = Field(default_factory=list)
    impacted_files: list[str] = Field(default_factory=list)
    impacted_symbols: list[str] = Field(default_factory=list)
    graph_nodes: list[RepositoryGraphNode] = Field(default_factory=list)
    graph_edges: list[RepositoryGraphEdge] = Field(default_factory=list)
    top_change_risk_files: list[RepositoryGraphImpactItem] = Field(default_factory=list)


class RepositoryDecisionPlanCreateRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    snapshot_id: str | None = None
    workspace_evidence_bundle_ref: str
    model: str | None = None


class RepositoryDecisionPlanResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    repository_id: str
    snapshot_id: str
    decision_plan_id: str
    created_at: datetime
    decision_plan: DecisionPlan
    planner_usage: dict[str, Any] = Field(default_factory=dict)
    agent_run_id: str | None = None
    session_id: str | None = None
    runtime_kind: str | None = None
    is_stub: bool | None = None
    runtime_provider: str | None = None
    runtime_model: str | None = None


class RepositorySimulationRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    snapshot_id: str | None = None
    decision_plan_id: str
    # None => the complexity-adaptive scenario count (_adaptive_simulation_runs);
    # an explicit value pins runs for this request (back-compat for callers that set it).
    runs: int | None = Field(default=None, ge=100, le=250_000)
    seed: int | None = Field(default=42, ge=0)


class RepositorySimulatePatchRequest(BaseModel):
    """Simulate an in-flight working-tree patch directly (no stored decision plan) —
    used by the verified_agentic agent's simulate_patch tool to verify mid-run."""

    model_config = ConfigDict(strict=False)

    snapshot_id: str
    patch_diff: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class RepositoryApplyMode(StrEnum):
    PATCH_ONLY = "patch_only"
    LOCAL_BRANCH = "local_branch"
    REMOTE_PR = "remote_pr"


class RepositoryApplyRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    snapshot_id: str | None = None
    decision_plan_id: str
    simulation_id: str
    mode: RepositoryApplyMode
    write_permission: bool = False
    branch_name: str | None = None
    commit_message: str | None = None
    base_branch: str | None = None
    pull_request_title: str | None = None
    pull_request_body: str | None = None


class RepositoryApplyResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    repository_id: str
    snapshot_id: str
    decision_plan_id: str
    simulation_id: str
    mode: RepositoryApplyMode
    applied: bool
    created_at: datetime
    patch: str
    branch_name: str | None = None
    commit_sha: str | None = None
    local_checkout_path: str | None = None
    pull_request_url: str | None = None
    apply_gate: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)


class RepositorySimulationEnvelope(BaseModel):
    """Compatibility wrapper for code paths that need a typed simulation envelope plus id."""

    model_config = ConfigDict(strict=False)

    simulation_id: str
    envelope: DecisionEnvelope


# AR-OPT-9: one-call orchestration of snapshot -> triage -> plan -> simulate.
# The stages form a strict dependency chain (each consumes the prior stage's id),
# so the win is one round-trip + cross-stage manifest reuse (the AR-OPT-2 triage
# LRU), not step parallelism. `stop_after` lets a caller halt before the LLM
# planner ("triage") or before the deterministic Mojo simulate ("plan").
RepositoryPipelineStage = Literal["snapshot", "triage", "plan", "simulate"]


class RepositoryPipelineRequest(BaseModel):
    model_config = ConfigDict(strict=False)

    # Reuse an existing snapshot by id, or create one from `snapshot` (defaults to
    # a snapshot of the connector's default ref when neither is supplied).
    snapshot_id: str | None = None
    snapshot: RepositorySnapshotCreateRequest | None = None
    signals: RepositorySignals = Field(default_factory=RepositorySignals)
    # Triage knobs (mirror RepositoryTriageRequest defaults).
    max_evidence_items: int = Field(default=16, ge=1, le=64)
    max_snippet_lines: int = Field(default=40, ge=5, le=200)
    token_budget: int = Field(default=6_000, ge=256, le=32_000)
    # Plan knob (the only LLM-touching stage).
    model: str | None = None
    # Simulate knobs (deterministic Mojo engine; no LLM). None => resolve through
    # the shared adaptive simulation-run policy, matching stored-plan simulate and
    # working-tree simulate-patch.
    runs: int | None = Field(default=None, ge=100, le=250_000)
    seed: int | None = Field(default=42, ge=0)
    # How far down the chain to run.
    stop_after: RepositoryPipelineStage = "simulate"


class RepositoryPipelineStageTiming(BaseModel):
    model_config = ConfigDict(strict=False)

    stage: RepositoryPipelineStage
    status: Literal["ok", "reused"]
    duration_ms: float = Field(..., ge=0.0)


class RepositoryPipelineResponse(BaseModel):
    model_config = ConfigDict(strict=False)

    repository_id: str
    snapshot_id: str
    stop_after: RepositoryPipelineStage
    completed_stage: RepositoryPipelineStage
    snapshot: RepositorySnapshotResponse
    triage: RepositoryTriageResponse | None = None
    decision_plan: RepositoryDecisionPlanResponse | None = None
    simulation: DecisionEnvelope | None = None
    stage_timings: list[RepositoryPipelineStageTiming] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)
