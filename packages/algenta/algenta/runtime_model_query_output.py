from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from algenta.runtime_model_common import coerce_payload_mapping, jsonable


@dataclass(frozen=True)
class QueryOutput:
    result: Any
    result_type: str
    confidence: float
    plan: list[str]
    resolved_column: str
    resolved_role: str
    resolved_source: str
    row_count: int
    ambiguous: bool
    exact_spec: bool
    explanation: list[str]
    latency_ms: float
    decision_path: str
    plan_hash: str
    validated: bool
    deterministic_scope: str
    confidence_source: str
    schema_revision: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    source_scores: dict[str, float] = field(default_factory=dict)
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    source_set: list[str] = field(default_factory=list)
    join_path: list[dict[str, Any]] = field(default_factory=list)
    planner_mode: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> QueryOutput:
        data = coerce_payload_mapping(payload)
        return cls(
            result=data.get("result"),
            result_type=data["result_type"],
            confidence=data["confidence"],
            plan=data.get("plan") or [],
            resolved_column=data["resolved_column"],
            resolved_role=data["resolved_role"],
            resolved_source=data["resolved_source"],
            row_count=data["row_count"],
            ambiguous=data["ambiguous"],
            exact_spec=data["exact_spec"],
            explanation=data.get("explanation") or [],
            latency_ms=data["latency_ms"],
            decision_path=data["decision_path"],
            plan_hash=data["plan_hash"],
            validated=data["validated"],
            deterministic_scope=data["deterministic_scope"],
            confidence_source=data["confidence_source"],
            schema_revision=data.get("schema_revision"),
            candidates=data.get("candidates") or [],
            source_scores=data.get("source_scores") or {},
            clarification_required=data.get("clarification_required", False),
            rejection_reason=data.get("rejection_reason"),
            request_id=data.get("request_id"),
            source_set=data.get("source_set") or [],
            join_path=data.get("join_path") or [],
            planner_mode=data.get("planner_mode"),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))
