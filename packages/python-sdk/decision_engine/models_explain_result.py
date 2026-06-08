from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExplainResult(BaseModel):
    model_config = ConfigDict(extra="allow", defer_build=True)

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
