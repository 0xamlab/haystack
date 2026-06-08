from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

import structlog

from apps.api_server.routers.query_contract import (
    CandidateColumn,
    ConstraintSpec,
    FilterSpec,
    JoinPathSpec,
    QueryResponse,
    ResolvedPlan,
    ResolveResponse,
    _query_plan_hash,
)

if TYPE_CHECKING:
    from apps.api_server.routers.query import ColumnNode

logger = structlog.get_logger("apps.api_server.routers.query")

_MAX_RESOLVE_SOURCE_SCORES = 32
_MAX_RESOLVE_CANDIDATES = 5


def _normalize_filter_spec(filter_spec: FilterSpec | None) -> dict[str, Any] | None:
    if filter_spec is None:
        return None
    data = filter_spec.model_dump(mode="python")
    normalized = {
        key: value
        for key, value in data.items()
        if value is not None and not (key == "conditions" and value == [])
    }
    return normalized or None


def _normalize_constraint_spec(constraints: ConstraintSpec | None) -> dict[str, Any]:
    if constraints is None:
        return {}
    return constraints.model_dump(mode="python")


def _normalize_join_path_spec(join_path: JoinPathSpec | None) -> dict[str, Any] | None:
    if join_path is None:
        return None
    return join_path.model_dump(mode="python")


def _exact_plan_basis(
    *,
    source_name: str,
    metric_column: str,
    aggregation: str,
    group_column: str | None,
    join_path: JoinPathSpec | None,
    filter_spec: FilterSpec | None,
    limit: int | None,
    order: str,
    constraints: ConstraintSpec,
) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "metric_column": metric_column,
        "aggregation": aggregation,
        "group_column": group_column or "",
        "join_path": _normalize_join_path_spec(join_path),
        "filter": _normalize_filter_spec(filter_spec),
        "limit": limit,
        "order": order,
        "constraints": _normalize_constraint_spec(constraints),
    }


def _immutable_plan_hash(*, schema_revision: str | None, basis: dict[str, Any]) -> str:
    payload = {
        "schema_revision": schema_revision or "",
        "basis": basis,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[
        :24
    ]


def _normalize_candidates(
    candidates: list[CandidateColumn] | list[dict[str, Any]],
) -> list[CandidateColumn]:
    normalized: list[CandidateColumn] = []
    for candidate in candidates:
        normalized.append(
            candidate if isinstance(candidate, CandidateColumn) else CandidateColumn(**candidate)
        )
    return normalized


def _dedupe_source_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _resolved_source_set(resolved_source: str) -> list[str]:
    return _dedupe_source_values(resolved_source.split("⋈"))


def _normalize_join_path(join_path: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(hop) for hop in (join_path or []) if isinstance(hop, dict)]


def _build_query_response(
    *,
    query_id: str,
    request_id: str | None,
    result: Any,
    result_type: str,
    confidence: float,
    plan: list[str],
    resolved_column: str,
    resolved_role: str,
    resolved_source: str,
    row_count: int,
    candidates: list[CandidateColumn] | list[dict[str, Any]],
    source_scores: dict[str, float],
    ambiguous: bool,
    exact_spec: bool,
    explanation: list[str] | None,
    latency_ms: float,
    decision_path: str,
    schema_revision: str | None,
    validated: bool,
    confidence_source: str,
    plan_basis: dict[str, Any],
    clarification_required: bool = False,
    rejection_reason: str | None = None,
    deterministic_scope: str | None = None,
    source_set: list[str] | None = None,
    join_path: list[dict[str, Any]] | None = None,
    planner_mode: str | None = None,
    plan_hash_override: str | None = None,
    log_response: bool = True,
) -> QueryResponse:
    normalized_candidates = _normalize_candidates(candidates)
    resolved_sources = source_set or _resolved_source_set(resolved_source)
    normalized_join_path = _normalize_join_path(join_path)
    response_planner_mode = planner_mode or ("exact_spec" if exact_spec else decision_path)
    plan_hash = plan_hash_override or _query_plan_hash(
        decision_path=decision_path,
        schema_revision=schema_revision,
        basis=plan_basis,
    )
    response = QueryResponse(
        query_id=query_id,
        result=result,
        result_type=result_type,
        confidence=confidence,
        plan=plan,
        resolved_column=resolved_column,
        resolved_role=resolved_role,
        resolved_source=resolved_source,
        row_count=row_count,
        candidates=normalized_candidates,
        source_scores=source_scores,
        ambiguous=ambiguous,
        exact_spec=exact_spec,
        explanation=explanation or [],
        latency_ms=latency_ms,
        decision_path=decision_path,
        plan_hash=plan_hash,
        schema_revision=schema_revision,
        validated=validated,
        deterministic_scope=(
            deterministic_scope or ("verified_execution" if validated else "planning_only")
        ),
        confidence_source=confidence_source,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        request_id=request_id,
        source_set=resolved_sources,
        join_path=normalized_join_path,
        planner_mode=response_planner_mode,
    )
    if log_response:
        logger.info(
            "query_response",
            request_id=request_id,
            query_id=query_id,
            plan_hash=plan_hash,
            schema_revision=schema_revision,
            decision_path=decision_path,
            validated=validated,
            clarification_required=clarification_required,
            rejection_reason=rejection_reason,
            confidence=round(confidence, 3),
            exact_spec=exact_spec,
            resolved_source=resolved_source,
            source_set=resolved_sources,
            planner_mode=response_planner_mode,
        )
    return response


def _build_resolve_response(
    *,
    resolved_plan: ResolvedPlan | None,
    confidence: float,
    plan: list[str],
    explanation: list[str] | None,
    resolved_column: str,
    resolved_role: str,
    resolved_source: str,
    candidates: list[CandidateColumn] | list[dict[str, Any]],
    source_scores: dict[str, float],
    latency_ms: float,
    schema_revision: str,
    validated: bool,
    confidence_source: str,
    request_id: str | None,
    intent_signature: str,
    clarification_required: bool = False,
    rejection_reason: str | None = None,
    source_set: list[str] | None = None,
    join_path: list[dict[str, Any]] | None = None,
    planner_mode: str = "registry_planner",
) -> ResolveResponse:
    normalized_candidates = _normalize_candidates(candidates)[:_MAX_RESOLVE_CANDIDATES]
    normalized_source_scores = dict(
        sorted(
            source_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:_MAX_RESOLVE_SOURCE_SCORES]
    )
    exact_basis = (
        _exact_plan_basis(
            source_name=resolved_plan.source_name,
            metric_column=resolved_plan.metric_column,
            aggregation=resolved_plan.aggregation,
            group_column=resolved_plan.group_column,
            join_path=resolved_plan.join_path,
            filter_spec=resolved_plan.filter,
            limit=resolved_plan.limit,
            order=resolved_plan.order,
            constraints=resolved_plan.constraints,
        )
        if resolved_plan is not None
        else None
    )
    return ResolveResponse(
        resolved_plan=resolved_plan,
        confidence=confidence,
        plan=plan,
        explanation=explanation or [],
        resolved_column=resolved_column,
        resolved_role=resolved_role,
        resolved_source=resolved_source,
        candidates=normalized_candidates,
        source_scores=normalized_source_scores,
        latency_ms=latency_ms,
        decision_path="resolve",
        plan_hash=(
            _immutable_plan_hash(schema_revision=schema_revision, basis=exact_basis)
            if exact_basis is not None
            else None
        ),
        schema_revision=schema_revision,
        validated=validated,
        deterministic_scope="resolved_execution_plan" if validated else "planning_only",
        confidence_source=confidence_source,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        request_id=request_id,
        intent_signature=intent_signature,
        source_set=source_set or _resolved_source_set(resolved_source),
        join_path=_normalize_join_path(join_path),
        planner_mode=planner_mode,
    )


def _resolve_to_query_response(
    *,
    query_id: str,
    resolve_response: ResolveResponse,
) -> QueryResponse:
    return _build_query_response(
        query_id=query_id,
        request_id=resolve_response.request_id,
        result=None,
        result_type="none",
        confidence=resolve_response.confidence,
        plan=resolve_response.plan,
        resolved_column=resolve_response.resolved_column,
        resolved_role=resolve_response.resolved_role,
        resolved_source=resolve_response.resolved_source,
        row_count=0,
        candidates=resolve_response.candidates,
        source_scores=resolve_response.source_scores,
        ambiguous=True,
        exact_spec=False,
        explanation=resolve_response.explanation,
        latency_ms=resolve_response.latency_ms,
        decision_path="resolve",
        schema_revision=resolve_response.schema_revision,
        validated=False,
        confidence_source=resolve_response.confidence_source,
        plan_basis={"intent_signature": resolve_response.intent_signature},
        clarification_required=resolve_response.clarification_required,
        rejection_reason=resolve_response.rejection_reason,
        deterministic_scope="planning_only",
        source_set=resolve_response.source_set,
        join_path=resolve_response.join_path,
        planner_mode=resolve_response.planner_mode,
        plan_hash_override=resolve_response.plan_hash,
    )


def _compute_exact_confidence(
    metric_node: ColumnNode,
    aggregation: str,
    join_confidence: float = 1.0,
) -> tuple[float, float, float]:
    role = metric_node.role
    has_formula = bool(metric_node.formula)

    if role == "derived_measure":
        col_conf = 1.00 if has_formula else 0.90
    elif role in ("base_measure", "unit_measure"):
        col_conf = 0.85
    elif role == "component":
        col_conf = 0.80
    elif role == "metric":
        col_conf = 0.75
    else:
        col_conf = 0.65

    agg = aggregation.lower()
    if agg == "count":
        agg_conf = 0.95
    elif agg in ("max", "min"):
        agg_conf = 0.95
    elif agg == "sum":
        if role in ("derived_measure", "component"):
            agg_conf = 1.00
        elif role in ("base_measure", "unit_measure"):
            agg_conf = 0.90
        else:
            agg_conf = 0.85
    elif agg == "avg":
        if role in ("unit_measure", "metric"):
            agg_conf = 1.00
        elif role == "derived_measure":
            agg_conf = 0.85
        else:
            agg_conf = 0.80
    else:
        agg_conf = 0.80

    final = round(col_conf * agg_conf * join_confidence, 3)
    return final, col_conf, agg_conf


__all__ = [
    "_MAX_RESOLVE_CANDIDATES",
    "_MAX_RESOLVE_SOURCE_SCORES",
    "_build_query_response",
    "_build_resolve_response",
    "_compute_exact_confidence",
    "_dedupe_source_values",
    "_exact_plan_basis",
    "_immutable_plan_hash",
    "_normalize_candidates",
    "_normalize_constraint_spec",
    "_normalize_filter_spec",
    "_normalize_join_path",
    "_normalize_join_path_spec",
    "_resolve_to_query_response",
    "_resolved_source_set",
]
