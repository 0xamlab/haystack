# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiskProfileResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    p5: float
    p95: float
    probability_of_loss: float
    var_95: float | None = None


class DecisionOptionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    name: str
    rank: int
    expected_value: float
    risk: RiskProfileResult
    score: float | None = None


class TokenReductionMetricsResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    raw_repo_token_estimate: int
    evidence_bundle_token_count: int
    reduction_ratio: float


class RepositoryAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    root_cause: str
    planner_model_id: str
    planner_execution_mode: str
    planner_provider_backend: str | None = None
    candidate_fixes: list[str] = Field(default_factory=list)
    impacted_services: list[str] = Field(default_factory=list)
    impacted_symbols: list[str] = Field(default_factory=list)
    likely_failing_tests: list[str] = Field(default_factory=list)
    rollback_complexity: str
    blast_radius: str
    workspace_evidence_refs: list[str] = Field(default_factory=list)
    generated_patch_ref: str | None = None
    patch_impact_report_ref: str | None = None
    token_reduction_metrics: TokenReductionMetricsResult


class DecisionPlanResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    recommended_action: str
    confidence: float
    expected_value: float
    risk: RiskProfileResult
    options: list[DecisionOptionResult] = Field(default_factory=list)
    rationale: str
    integrity: dict[str, Any] | None = None
    calibration: str | None = None
    repository_analysis: RepositoryAnalysisResult | None = None
