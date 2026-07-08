from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping
from algenta.runtime_model_resolved_plan import ResolvedPlan


@dataclass(frozen=True)
class ResolveOutput:
    resolved_plan: ResolvedPlan | None
    confidence: float
    plan: list[str]
    explanation: list[str]
    latency_ms: float
    decision_path: str
    schema_revision: str
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    intent_signature: str = ""
    plan_hash: str | None = None
    source_set: list[str] = field(default_factory=list)
    join_path: list[dict[str, Any]] = field(default_factory=list)
    planner_mode: str | None = None
    resolved_source: str = ""
    resolved_column: str = ""
    resolved_role: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    source_scores: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> ResolveOutput:
        data = coerce_payload_mapping(payload)
        resolved_plan = data.get("resolved_plan")
        return cls(
            resolved_plan=ResolvedPlan.from_api(resolved_plan) if resolved_plan else None,
            confidence=data["confidence"],
            plan=data.get("plan") or [],
            explanation=data.get("explanation") or [],
            latency_ms=data["latency_ms"],
            decision_path=data["decision_path"],
            schema_revision=data["schema_revision"],
            validated=data["validated"],
            deterministic_scope=data["deterministic_scope"],
            confidence_source=data["confidence_source"],
            clarification_required=data.get("clarification_required", False),
            rejection_reason=data.get("rejection_reason"),
            request_id=data.get("request_id"),
            intent_signature=data.get("intent_signature", ""),
            plan_hash=data.get("plan_hash"),
            source_set=data.get("source_set") or [],
            join_path=data.get("join_path") or [],
            planner_mode=data.get("planner_mode"),
            resolved_source=data.get("resolved_source", ""),
            resolved_column=data.get("resolved_column", ""),
            resolved_role=data.get("resolved_role", ""),
            candidates=data.get("candidates") or [],
            source_scores=data.get("source_scores") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.resolved_plan is not None:
            data["resolved_plan"] = self.resolved_plan.to_dict()
        return data
