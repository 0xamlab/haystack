from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

from algenta.runtime_errors import AlgentaRuntimeError
from algenta.runtime_local_execution import (
    collect_local_plan_errors,
    execute_local_plan,
    local_plan_steps,
    validate_local_plan,
)
from algenta.runtime_model_query_output import QueryOutput
from algenta.runtime_model_verify_output import VerifyOutput


def query_local_request(
    local_sources: Mapping[str, Any],
    request: Any,
    kwargs: Mapping[str, Any],
    *,
    coerce_plan: Callable[[Any, Mapping[str, Any]], Any],
    ensure_local_execution_entitlement: Callable[[], None],
    consume_local_credit: Callable[[], None],
    plan_hash: Callable[[Any], str],
) -> QueryOutput:
    start = time.perf_counter()
    plan = coerce_plan(request, kwargs)
    source = validate_local_plan(local_sources, plan)
    ensure_local_execution_entitlement()
    consume_local_credit()
    execution = execute_local_plan(source, plan)
    resolved_plan_hash = plan_hash(plan)

    latency_ms = round((time.perf_counter() - start) * 1000, 3)
    return QueryOutput(
        result=execution.value,
        result_type=execution.result_type,
        confidence=1.0,
        plan=local_plan_steps(
            source_name=source.name,
            metric_column=plan.metric_column,
            aggregation=plan.aggregation,
            group_column=plan.group_column,
            filter_steps=list(execution.plan_steps),
        ),
        resolved_column=plan.metric_column,
        resolved_role="measure",
        resolved_source=source.name,
        row_count=execution.row_count,
        ambiguous=False,
        exact_spec=True,
        explanation=["Executed deterministic local plan."],
        latency_ms=latency_ms,
        decision_path="exact_spec",
        plan_hash=resolved_plan_hash,
        validated=True,
        deterministic_scope="local_registered_source",
        confidence_source="local_exact_execution",
        schema_revision=source.schema_revision,
        candidates=[],
        source_scores={source.name: 1.0},
        clarification_required=False,
        rejection_reason=None,
        request_id=f"local_query_{resolved_plan_hash[:12]}",
        source_set=[source.name],
        join_path=[],
        planner_mode="local_structured_intent",
    )


def verify_local_request(
    local_sources: Mapping[str, Any],
    request: Any,
    kwargs: Mapping[str, Any],
    *,
    coerce_plan: Callable[[Any, Mapping[str, Any]], Any],
    plan_hash: Callable[[Any], str],
) -> VerifyOutput:
    start = time.perf_counter()
    try:
        plan = coerce_plan(request, kwargs)
    except AlgentaRuntimeError as exc:
        return _invalid_verify_output(
            start,
            errors=[str(exc)],
            rejection_reason=exc.code,
        )

    errors = collect_local_plan_errors(local_sources, plan)
    resolved_plan_hash = plan_hash(plan)
    latency_ms = round((time.perf_counter() - start) * 1000, 3)
    valid = not errors
    return VerifyOutput(
        valid=valid,
        errors=errors,
        suggestions=[]
        if valid
        else ["Reconnect the source or rerun resolve against the current schema."],
        resolved={
            "source_name": plan.source_name,
            "metric_column": plan.metric_column,
            "group_column": plan.group_column or "",
        },
        latency_ms=latency_ms,
        verified=valid,
        request_id=f"local_verify_{resolved_plan_hash[:12]}",
        schema_revision=plan.schema_revision,
        plan_hash=resolved_plan_hash,
        verification_mode="local",
        rejection_reason=None if valid else "plan_verification_failed",
        valid_dimensions=[plan.group_column] if plan.group_column else [],
        valid_measures=[plan.metric_column],
        source_behavior="local_registered_source",
    )


def _invalid_verify_output(
    started_at: float,
    *,
    errors: list[str],
    rejection_reason: str,
) -> VerifyOutput:
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    return VerifyOutput(
        valid=False,
        errors=errors,
        suggestions=["Run Runtime.resolve(...) again with a more explicit metric or source."],
        resolved={},
        latency_ms=latency_ms,
        verified=False,
        rejection_reason=rejection_reason,
        verification_mode="local",
    )
