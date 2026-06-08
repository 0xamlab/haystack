from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from .models_decision_plan import DecisionPlanResult
from .models_simulation_common import MetricsSummary, PercentileSummary, RunMetadata


class DecisionEnvelope(BaseModel):
    """Full decision output returned by simulate, recommend, and score endpoints."""

    model_config = ConfigDict(extra="allow", protected_namespaces=(), defer_build=True)

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
    decision_plan: DecisionPlanResult | None = None
