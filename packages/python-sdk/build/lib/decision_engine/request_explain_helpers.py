from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .model_loader import validate_model
from .request_query_helpers import _request_source_set, _split_resolved_sources

if TYPE_CHECKING:
    from .models_query import ExplainResult, QueryResult


def _build_explain_result(request: dict[str, Any], result: QueryResult) -> ExplainResult:
    join_path_payload = request.get("join_path")
    join_path: list[dict[str, Any]] = list(result.join_path)
    if isinstance(join_path_payload, dict):
        edges = join_path_payload.get("edges")
        if not join_path and isinstance(edges, list):
            join_path = [dict(edge) for edge in edges if isinstance(edge, dict)]

    source_set = (
        result.source_set
        or _split_resolved_sources(result.resolved_source)
        or _request_source_set(request)
    )
    if not join_path and len(source_set) > 1:
        join_path = [
            {"left_source": source_set[index], "right_source": source_set[index + 1]}
            for index in range(len(source_set) - 1)
        ]

    planner_mode = result.planner_mode or (
        "exact_spec" if result.exact_spec else result.decision_path
    )
    return validate_model(
        "ExplainResult",
        {
            "source_set": source_set,
            "join_path": join_path,
            "planner_mode": planner_mode,
            "decision_path": result.decision_path,
            "plan_hash": result.plan_hash,
            "schema_revision": result.schema_revision,
            "validated": result.validated,
            "clarification_required": result.clarification_required,
            "rejection_reason": result.rejection_reason,
            "resolved_source": result.resolved_source,
            "resolved_column": result.resolved_column,
            "resolved_role": result.resolved_role,
            "confidence": result.confidence,
            "confidence_source": result.confidence_source,
            "deterministic_scope": result.deterministic_scope,
            "plan": result.plan,
            "explanation": result.explanation,
            "request_id": result.request_id,
        },
    )


__all__ = ["_build_explain_result"]
