# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueryCandidate(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    source: str
    column: str
    role: str
    magnitude: str | None = None
    formula: str | None = None
    confidence: float
    score_components: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class QueryResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

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
