from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

from algenta.runtime_errors import RuntimeValidationError
from algenta.runtime_local_execution import (
    LocalSource,
    build_local_candidates,
    is_exact_field_match,
    local_plan_steps,
    rank_local_fields,
    select_local_source,
)
from algenta.runtime_model_resolve_output import ResolveOutput
from algenta.runtime_model_resolved_plan import ResolvedPlan

_MIN_MATCH_SCORE = 0.70
_MIN_DECISIVE_SCORE = 0.85
_MIN_SCORE_GAP = 0.10


def resolve_local_request(
    local_sources: Mapping[str, LocalSource],
    request: Mapping[str, Any],
    *,
    started_at: float,
    resolve_aggregation: Callable[[Mapping[str, Any]], str],
    intent_signature: Callable[[str, Mapping[str, Any], str], str],
    plan_hash: Callable[[ResolvedPlan], str],
) -> ResolveOutput:
    source = select_local_source(local_sources, request)
    metric_hint = request.get("metric")
    group_hint = request.get("group_by")
    if not isinstance(metric_hint, str) or not metric_hint.strip():
        raise RuntimeValidationError(
            "metric_required",
            "Local Runtime.resolve() requires a structured metric field.",
            {"request": dict(request)},
        )

    aggregation = resolve_aggregation(request)
    metric_ranked = rank_local_fields(source, metric_hint, numeric_only=True)
    if not metric_ranked:
        return _rejected_resolve(
            source,
            request,
            "schema_unresolved",
            [f"No numeric field matched metric '{metric_hint}'."],
            started_at,
            intent_signature=intent_signature,
        )

    metric_choice = metric_ranked[0]
    metric_candidates = build_local_candidates(source, metric_ranked, "measure")
    metric_gap = _score_gap(metric_ranked)
    if metric_choice.score < _MIN_MATCH_SCORE:
        return _rejected_resolve(
            source,
            request,
            "schema_unresolved",
            [f"Top metric match '{metric_choice.field}' scored below the 0.70 threshold."],
            started_at,
            candidates=metric_candidates,
            intent_signature=intent_signature,
        )
    if metric_choice.score < _MIN_DECISIVE_SCORE or metric_gap < _MIN_SCORE_GAP:
        return _clarify_resolve(
            source,
            request,
            [f"Metric mapping for '{metric_hint}' is not decisive enough for execution."],
            started_at,
            candidates=metric_candidates,
            intent_signature=intent_signature,
        )

    resolved_group: str | None = None
    group_candidates: list[dict[str, Any]] = []
    if isinstance(group_hint, str) and group_hint.strip():
        group_ranked = rank_local_fields(source, group_hint, numeric_only=False)
        group_candidates = build_local_candidates(source, group_ranked, "dimension")
        if not group_ranked:
            return _rejected_resolve(
                source,
                request,
                "schema_unresolved",
                [f"No field matched group_by '{group_hint}'."],
                started_at,
                candidates=metric_candidates,
                intent_signature=intent_signature,
            )
        group_choice = group_ranked[0]
        group_gap = _score_gap(group_ranked)
        if group_choice.score < _MIN_MATCH_SCORE:
            return _rejected_resolve(
                source,
                request,
                "schema_unresolved",
                [f"Top group_by match '{group_choice.field}' scored below the 0.70 threshold."],
                started_at,
                candidates=[*metric_candidates, *group_candidates],
                intent_signature=intent_signature,
            )
        if group_choice.score < _MIN_DECISIVE_SCORE or group_gap < _MIN_SCORE_GAP:
            return _clarify_resolve(
                source,
                request,
                [f"Group_by mapping for '{group_hint}' is not decisive enough for execution."],
                started_at,
                candidates=[*metric_candidates, *group_candidates],
                intent_signature=intent_signature,
            )
        resolved_group = group_choice.field

    plan = ResolvedPlan(
        source_name=source.name,
        metric_column=metric_choice.field,
        aggregation=aggregation,
        group_column=resolved_group,
        filter=request.get("filter"),
        limit=request.get("limit"),
        order=str(request.get("order", "desc")),
        constraints=dict(request.get("constraints") or {}),
        schema_revision=source.schema_revision,
    )
    resolved_plan_hash = plan_hash(plan)
    resolved_intent_signature = intent_signature(source.name, request, source.schema_revision)
    resolved_candidates = [*metric_candidates, *group_candidates]
    latency_ms = _latency_ms(started_at)
    decision_path = (
        "exact_spec"
        if is_exact_field_match(metric_choice.field, metric_hint)
        and (resolved_group is None or is_exact_field_match(resolved_group, str(group_hint)))
        else "planner_hint"
    )
    explanation = [
        f"Resolved metric '{metric_hint}' to '{metric_choice.field}'.",
        *([f"Resolved group_by '{group_hint}' to '{resolved_group}'."] if resolved_group else []),
    ]
    return ResolveOutput(
        resolved_plan=plan,
        confidence=1.0,
        plan=local_plan_steps(
            source_name=source.name,
            metric_column=metric_choice.field,
            aggregation=aggregation,
            group_column=resolved_group,
        ),
        explanation=explanation,
        latency_ms=latency_ms,
        decision_path=decision_path,
        schema_revision=source.schema_revision,
        validated=True,
        deterministic_scope="local_registered_source",
        confidence_source="local_schema_match",
        request_id=f"local_{resolved_intent_signature[:12]}",
        intent_signature=resolved_intent_signature,
        plan_hash=resolved_plan_hash,
        source_set=[source.name],
        join_path=[],
        planner_mode="local_structured_intent",
        resolved_source=source.name,
        resolved_column=metric_choice.field,
        resolved_role="measure",
        candidates=resolved_candidates,
        source_scores={source.name: 1.0},
    )


def _rejected_resolve(
    source: LocalSource,
    request: Mapping[str, Any],
    reason: str,
    explanation: list[str],
    started_at: float,
    *,
    intent_signature: Callable[[str, Mapping[str, Any], str], str],
    candidates: list[dict[str, Any]] | None = None,
) -> ResolveOutput:
    resolved_intent_signature = intent_signature(source.name, request, source.schema_revision)
    return ResolveOutput(
        resolved_plan=None,
        confidence=0.0,
        plan=[],
        explanation=explanation,
        latency_ms=_latency_ms(started_at),
        decision_path="planner_hint",
        schema_revision=source.schema_revision,
        validated=False,
        deterministic_scope="local_registered_source",
        confidence_source="local_schema_match",
        clarification_required=False,
        rejection_reason=reason,
        request_id=f"local_{resolved_intent_signature[:12]}",
        intent_signature=resolved_intent_signature,
        source_set=[source.name],
        join_path=[],
        planner_mode="local_structured_intent",
        resolved_source=source.name,
        candidates=candidates or [],
        source_scores={source.name: 1.0},
    )


def _clarify_resolve(
    source: LocalSource,
    request: Mapping[str, Any],
    explanation: list[str],
    started_at: float,
    *,
    candidates: list[dict[str, Any]],
    intent_signature: Callable[[str, Mapping[str, Any], str], str],
) -> ResolveOutput:
    resolved_intent_signature = intent_signature(source.name, request, source.schema_revision)
    return ResolveOutput(
        resolved_plan=None,
        confidence=0.75,
        plan=[],
        explanation=explanation,
        latency_ms=_latency_ms(started_at),
        decision_path="planner_hint",
        schema_revision=source.schema_revision,
        validated=False,
        deterministic_scope="local_registered_source",
        confidence_source="local_schema_match",
        clarification_required=True,
        rejection_reason=None,
        request_id=f"local_{resolved_intent_signature[:12]}",
        intent_signature=resolved_intent_signature,
        source_set=[source.name],
        join_path=[],
        planner_mode="local_structured_intent",
        resolved_source=source.name,
        candidates=candidates,
        source_scores={source.name: 1.0},
    )


def _latency_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 3)


def _score_gap(ranked) -> float:
    top_score = ranked[0].score
    second_score = ranked[1].score if len(ranked) > 1 else 0.0
    return round(top_score - second_score, 4)
