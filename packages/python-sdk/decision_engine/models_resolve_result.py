# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models_query_result import QueryCandidate

_FILTER_SUPPORTED_OPS = frozenset({"eq", "in", "gt", "gte", "lt", "lte", "is_null", "is_not_null"})
_FILTER_NULL_OPS = frozenset({"is_null", "is_not_null"})


class QueryFilterCondition(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    column: str | None = None
    dimension_hint: str | None = None
    op: str
    value: Any | None = None
    values: list[Any] | None = None

    @model_validator(mode="after")
    def _validate_condition(self) -> QueryFilterCondition:
        column = (self.column or "").strip() or None
        dimension_hint = (self.dimension_hint or "").strip() or None
        if column is None and dimension_hint is None:
            raise ValueError("filter condition requires column or dimension_hint")
        op = self.op.strip()
        if not op:
            raise ValueError("filter condition op is required")
        if op not in _FILTER_SUPPORTED_OPS:
            raise ValueError(f"Unsupported filter operator '{op}'.")
        self.column = column
        self.dimension_hint = dimension_hint
        self.op = op
        if op == "in":
            if self.value is not None:
                raise ValueError("filter condition op='in' does not accept value")
            if not self.values:
                raise ValueError("filter condition op='in' requires non-empty values")
        elif op in _FILTER_NULL_OPS:
            if self.value is not None or self.values is not None:
                raise ValueError("filter condition null checks do not accept value or values")
        else:
            if self.values is not None:
                raise ValueError(f"filter condition op='{op}' does not accept values")
            if self.value is None:
                raise ValueError(f"filter condition op='{op}' requires value")
        return self


class QueryFilterSpec(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    time_filter: str | None = None
    conditions: list[QueryFilterCondition] = Field(default_factory=list)


class ResolvedPlan(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

    source_name: str
    metric_column: str
    aggregation: str
    group_column: str | None = None
    join_path: dict[str, Any] | None = None
    filter: QueryFilterSpec | None = None
    limit: int | None = None
    order: str = "desc"
    constraints: dict[str, Any] = Field(default_factory=dict)
    schema_revision: str


class ResolveResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

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
