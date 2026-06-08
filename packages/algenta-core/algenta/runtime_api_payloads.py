from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from algenta.runtime_errors import RuntimeValidationError
from algenta.runtime_model_query_output import QueryOutput
from algenta.runtime_model_resolve_output import ResolveOutput
from algenta.runtime_model_resolved_plan import ResolvedPlan
from algenta.runtime_model_verify_output import VerifyOutput

_RUNTIME_DATASET_SCOPE_KEY = "__runtime_dataset_id__"


def coerce_api_resolve_payload(request: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(request)
    source_name = payload.pop("source_name", None)
    if isinstance(source_name, str) and source_name.strip():
        payload.setdefault("preferred_source", source_name.strip())
        payload.setdefault("allow_org_scope", True)

    metric = payload.get("metric")
    if isinstance(metric, str):
        payload["metric"] = {"role": "metric", "hint": metric.strip()}

    group_by = payload.get("group_by")
    if isinstance(group_by, str):
        payload["group_by"] = [group_by]
    elif group_by is None:
        group_column = payload.pop("group_column", None)
        if isinstance(group_column, str) and group_column.strip():
            payload["group_by"] = [group_column.strip()]
    else:
        payload.pop("group_column", None)

    payload.pop("metric_column", None)
    payload.pop("resolved_plan", None)
    return payload


def coerce_plan(request: Any, kwargs: Mapping[str, Any]) -> ResolvedPlan:
    if kwargs:
        payload = dict(kwargs)
    elif isinstance(request, ResolveOutput):
        resolved_plan = request.resolved_plan
        if resolved_plan is None:
            raise RuntimeValidationError(
                "query_requires_executable_plan",
                (
                    "Runtime.query() requires an executable plan. "
                    "Resolve returned clarification or rejection."
                ),
            )
        if isinstance(resolved_plan, ResolvedPlan):
            return resolved_plan
        return ResolvedPlan.from_api(resolved_plan)
    elif isinstance(request, Mapping) and "resolved_plan" in request:
        resolved = request.get("resolved_plan")
        if resolved is None:
            raise RuntimeValidationError(
                "query_requires_executable_plan",
                (
                    "Runtime.query() requires an executable plan. "
                    "The provided resolve payload is not executable."
                ),
            )
        return ResolvedPlan.from_api(resolved)
    elif isinstance(request, ResolvedPlan):
        return request
    elif isinstance(request, Mapping):
        payload = dict(request)
    else:
        raise RuntimeValidationError(
            "query_request_invalid",
            "Runtime.query() expects a ResolvedPlan, resolve output, or exact plan mapping.",
            {"received": type(request).__name__},
        )
    return ResolvedPlan.from_api(payload)


def coerce_api_query_payload(request: Any, kwargs: Mapping[str, Any]) -> dict[str, Any]:
    if kwargs:
        payload = dict(kwargs)
    elif isinstance(request, ResolveOutput):
        if request.resolved_plan is None:
            raise RuntimeValidationError(
                "query_requires_executable_plan",
                (
                    "Runtime query/verify requires an executable plan. "
                    "Resolve returned clarification or rejection."
                ),
            )
        payload = _exact_query_payload(request.resolved_plan.to_dict())
    elif isinstance(request, QueryOutput | VerifyOutput):
        payload = request.to_dict()
    elif isinstance(request, ResolvedPlan):
        payload = _exact_query_payload(request.to_dict())
    elif isinstance(request, Mapping):
        mapped = dict(request)
        if _is_exact_plan_mapping(mapped):
            payload = _exact_query_payload(mapped)
        else:
            payload = mapped
    elif request is None:
        payload = {}
    else:
        raise RuntimeValidationError(
            "api_request_invalid",
            "API mode expects a mapping, resolve output, or exact plan.",
            {"received": type(request).__name__},
        )
    resolved_plan = payload.get("resolved_plan")
    if resolved_plan is not None and hasattr(resolved_plan, "to_dict"):
        payload["resolved_plan"] = resolved_plan.to_dict()
        payload = _extract_runtime_dataset_scope(payload)
    return payload


def _exact_query_payload(resolved_plan: Mapping[str, Any]) -> dict[str, Any]:
    return _extract_runtime_dataset_scope({"resolved_plan": dict(resolved_plan)})


def _extract_runtime_dataset_scope(payload: dict[str, Any]) -> dict[str, Any]:
    resolved_plan = payload.get("resolved_plan")
    if not isinstance(resolved_plan, Mapping):
        return payload
    resolved_plan_dict = dict(resolved_plan)
    raw_constraints = resolved_plan_dict.get("constraints")
    if not isinstance(raw_constraints, Mapping):
        payload["resolved_plan"] = resolved_plan_dict
        return payload
    constraints = dict(raw_constraints)
    dataset_id = constraints.pop(_RUNTIME_DATASET_SCOPE_KEY, None)
    if dataset_id is not None and payload.get("dataset_id") is None:
        payload["dataset_id"] = dataset_id
    if constraints:
        resolved_plan_dict["constraints"] = constraints
    else:
        resolved_plan_dict["constraints"] = {}
    payload["resolved_plan"] = resolved_plan_dict
    return payload


def _is_exact_plan_mapping(payload: Mapping[str, Any]) -> bool:
    return (
        isinstance(payload.get("source_name"), str)
        and isinstance(payload.get("metric_column"), str)
        and isinstance(payload.get("schema_revision"), str)
    )


__all__ = [
    "coerce_api_query_payload",
    "coerce_api_resolve_payload",
    "coerce_plan",
]
