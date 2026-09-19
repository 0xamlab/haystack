# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models_decision_plan import DecisionPlanResult


class RepositoryArtifactRefResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    artifact_id: str
    artifact_kind: str
    content_hash: str
    storage_path: str
    schema_revision: str | None = None
    created_at: datetime


class RepositoryLanguageSupportProgressResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    supported_real_language_count: int
    ranked_target_language_count: int
    progress_fraction: float
    progress_label: str


class RepositoryIntelligenceCapabilitiesResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    supported_languages: list[str] = Field(default_factory=list)
    support_progress: RepositoryLanguageSupportProgressResult


class RepositoryEvidenceItemResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    evidence_id: str
    rank: int
    source_type: str
    source_ref: str
    file_path: str | None = None
    symbol_name: str | None = None
    summary: str
    snippet: str
    token_count: int
    score: float


class RepositorySnapshotResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    repository_id: str
    snapshot_id: str
    connector_type: str
    ref: str | None = None
    resolved_revision: str
    content_hash: str
    status: str
    created_at: datetime
    file_count: int
    language_counts: dict[str, int] = Field(default_factory=dict)
    raw_repo_token_estimate: int
    repository_snapshot_artifact: RepositoryArtifactRefResult
    repository_graph_artifact: RepositoryArtifactRefResult
    symbol_graph_artifact: RepositoryArtifactRefResult
    dependency_graph_artifact: RepositoryArtifactRefResult


class RepositoryTriageResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    repository_id: str
    snapshot_id: str
    workspace_evidence_bundle_ref: str
    created_at: datetime
    suspect_files: list[str] = Field(default_factory=list)
    suspect_symbols: list[str] = Field(default_factory=list)
    raw_repo_token_estimate: int
    evidence_bundle_token_count: int
    reduction_ratio: float
    evidence_items: list[RepositoryEvidenceItemResult] = Field(default_factory=list)
    workspace_evidence_bundle_artifact: RepositoryArtifactRefResult


class RepositoryGraphEdgeResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    source_file: str
    target_file: str
    edge_type: str


class RepositoryGraphNodeResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    file_path: str
    depth: int
    is_seed: bool = False
    inbound_count: int
    outbound_count: int
    risk_score: float
    contained_symbols: list[str] = Field(default_factory=list)
    parent_child_symbols: list[str] = Field(default_factory=list)


class RepositoryGraphImpactItemResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    file_path: str
    depth: int
    relationship: str
    risk_score: float
    top_symbol: str | None = None


class RepositoryGraphQueryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    repository_id: str
    snapshot_id: str
    created_at: datetime
    seed_file_paths: list[str] = Field(default_factory=list)
    seed_symbols: list[str] = Field(default_factory=list)
    direct_dependencies: list[str] = Field(default_factory=list)
    direct_dependents: list[str] = Field(default_factory=list)
    impacted_files: list[str] = Field(default_factory=list)
    impacted_symbols: list[str] = Field(default_factory=list)
    graph_nodes: list[RepositoryGraphNodeResult] = Field(default_factory=list)
    graph_edges: list[RepositoryGraphEdgeResult] = Field(default_factory=list)
    top_change_risk_files: list[RepositoryGraphImpactItemResult] = Field(default_factory=list)


class RepositoryDecisionPlanRevisionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    repository_id: str
    snapshot_id: str
    decision_plan_id: str
    created_at: datetime
    decision_plan: DecisionPlanResult


class RepositoryApplyResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    repository_id: str
    snapshot_id: str
    decision_plan_id: str
    simulation_id: str
    mode: str
    applied: bool
    created_at: datetime
    patch: str
    branch_name: str | None = None
    commit_sha: str | None = None
    local_checkout_path: str | None = None
    pull_request_url: str | None = None
    apply_gate: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
