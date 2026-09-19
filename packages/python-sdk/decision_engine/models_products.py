# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductDecisionResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    decision_id: str
    action: str
    confidence: float
    reasoning: str
    why: list[str] = Field(default_factory=list)
    expected_outcome: float
    downside_risk: float
    upside_potential: float
    probability_of_loss: float
    scenarios_evaluated: int
    latency_ms: float


class ProductAgentStepResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    step: int
    action: str
    tool: str | None = None
    result: str | None = None
    status: str = "completed"


class ProductAgentRunResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    run_id: str
    status: str
    result: str | dict[str, Any]
    steps: list[ProductAgentStepResult] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    latency_ms: float


class ProductOptimizeResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    optimization_id: str
    status: str
    optimal_values: dict[str, float] = Field(default_factory=dict)
    objective_value: float
    improvement_vs_midpoint: float
    constraints_satisfied: bool
    iterations_run: int
    latency_ms: float


class ProductRetrieveHitResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    rank: int
    document_id: str | None = None
    content: str
    relevance_score: float
    snippet: str


class ProductRetrieveResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    retrieval_id: str
    query: str
    results: list[ProductRetrieveHitResult] = Field(default_factory=list)
    total_searched: int
    latency_ms: float


class ProductForecastPeriodResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    period: int
    forecast: float
    lower_bound: float
    upper_bound: float
    trend: str


class ProductForecastResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    forecast_id: str
    metric: str
    baseline: float
    forecast_mean: float
    total_change_pct: float
    periods: list[ProductForecastPeriodResult] = Field(default_factory=list)
    scenarios_evaluated: int
    latency_ms: float
