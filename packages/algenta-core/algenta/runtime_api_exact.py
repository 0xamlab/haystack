from __future__ import annotations

import time
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any

from algenta.runtime_model_resolve_output import ResolveOutput
from algenta.runtime_model_resolved_plan import ResolvedPlan
from algenta.runtime_model_source_registration import SourceRegistration

_RUNTIME_DATASET_SCOPE_KEY = "__runtime_dataset_id__"


def registration_fields(registration: SourceRegistration) -> list[str]:
    if not isinstance(registration.source_schema, dict):
        return []
    raw_fields = registration.source_schema.get("fields", [])
    if isinstance(raw_fields, list):
        direct_fields = [str(field) for field in raw_fields if str(field).strip()]
        if direct_fields:
            return direct_fields
    raw_columns = registration.source_schema.get("columns", [])
    if not isinstance(raw_columns, list):
        return []
    fields: list[str] = []
    for column in raw_columns:
        if not isinstance(column, Mapping):
            continue
        name_value = column.get("name")
        if isinstance(name_value, str) and name_value.strip():
            fields.append(name_value)
    return fields


def remember_api_registration(
    registrations_by_name: MutableMapping[str, SourceRegistration],
    registrations_by_dataset: MutableMapping[str, SourceRegistration],
    registration: SourceRegistration,
) -> None:
    if registration.name:
        registrations_by_name[registration.name] = registration
    if registration.dataset_id:
        registrations_by_dataset[registration.dataset_id] = registration


def forget_api_registration(
    registrations_by_name: MutableMapping[str, SourceRegistration],
    registrations_by_dataset: MutableMapping[str, SourceRegistration],
    source_schema_revision_cache: MutableMapping[str, str],
    dataset_id: str,
) -> None:
    registration = registrations_by_dataset.pop(dataset_id, None)
    if registration is None:
        source_schema_revision_cache.pop(dataset_id, None)
        return
    if registration.name:
        cached = registrations_by_name.get(registration.name)
        if cached is registration:
            registrations_by_name.pop(registration.name, None)
    source_key = _registration_cache_key(registration)
    if source_key is not None:
        source_schema_revision_cache.pop(source_key, None)


def lookup_api_registration(
    registrations_by_name: Mapping[str, SourceRegistration],
    registrations_by_dataset: Mapping[str, SourceRegistration],
    request: Mapping[str, Any],
) -> SourceRegistration | None:
    dataset_id = request.get("dataset_id")
    if isinstance(dataset_id, str) and dataset_id.strip():
        registration = registrations_by_dataset.get(dataset_id.strip())
        if registration is not None:
            return registration
    source_name = request.get("source_name")
    if isinstance(source_name, str) and source_name.strip():
        return registrations_by_name.get(source_name.strip())
    return None


def try_exact_api_resolve(
    request: Mapping[str, Any],
    *,
    registrations_by_name: Mapping[str, SourceRegistration],
    registrations_by_dataset: Mapping[str, SourceRegistration],
    source_schema_revision_cache: MutableMapping[str, str],
    client_factory: Callable[[], Any],
    resolve_aggregation: Callable[[Mapping[str, Any]], str],
    intent_signature: Callable[[str, Mapping[str, Any], str], str],
    plan_hash: Callable[[ResolvedPlan], str],
    started_at: float,
) -> ResolveOutput | None:
    registration = lookup_api_registration(
        registrations_by_name,
        registrations_by_dataset,
        request,
    )
    if registration is None or not registration.name:
        return None

    fields = set(registration_fields(registration))
    if not fields:
        return None

    metric_column = _exact_metric_column(request, fields)
    if metric_column is None:
        return None
    group_column = _exact_group_column(request, fields)
    if group_column is _INVALID_EXACT_GROUP:
        return None

    schema_revision = _resolve_source_schema_revision(
        registration,
        source_schema_revision_cache,
        client_factory=client_factory,
    )
    if not schema_revision:
        return None

    resolved_source_name = _registration_resolved_source_name(registration)
    constraints = dict(request.get("constraints") or {})
    dataset_scope = _registration_cache_key(registration)
    if dataset_scope:
        constraints.setdefault(_RUNTIME_DATASET_SCOPE_KEY, dataset_scope)

    plan = ResolvedPlan(
        source_name=resolved_source_name,
        metric_column=metric_column,
        aggregation=resolve_aggregation(request),
        group_column=group_column,
        join_path=request.get("join_path"),
        filter=request.get("filter"),
        limit=request.get("limit"),
        order=str(request.get("order", "desc")),
        constraints=constraints,
        schema_revision=schema_revision,
    )
    latency_ms = round((time.perf_counter() - started_at) * 1000, 3)
    resolved_intent_signature = intent_signature(
        resolved_source_name,
        request,
        schema_revision,
    )
    resolved_plan_hash = plan_hash(plan)
    explanation = [
        f"Using registered source '{resolved_source_name}' as an exact source.",
        f"Using exact metric column '{metric_column}'.",
        *([f"Using exact group column '{group_column}'."] if group_column else []),
    ]
    return ResolveOutput(
        resolved_plan=plan,
        confidence=1.0,
        plan=[
            f"Use exact source '{resolved_source_name}'.",
            f"Use exact metric column '{metric_column}'.",
            *([f"Group by exact column '{group_column}'."] if group_column else []),
        ],
        explanation=explanation,
        latency_ms=latency_ms,
        decision_path="exact_spec",
        schema_revision=schema_revision,
        validated=True,
        deterministic_scope="api_registered_source",
        confidence_source="runtime_exact_spec",
        request_id=f"runtime_exact_{resolved_intent_signature[:12]}",
        intent_signature=resolved_intent_signature,
        plan_hash=resolved_plan_hash,
        source_set=[resolved_source_name],
        join_path=[],
        planner_mode="runtime_exact_spec",
        resolved_source=resolved_source_name,
        resolved_column=metric_column,
        resolved_role="measure",
        candidates=[],
        source_scores={resolved_source_name: 1.0},
    )


def _resolve_source_schema_revision(
    registration: SourceRegistration,
    source_schema_revision_cache: MutableMapping[str, str],
    *,
    client_factory: Callable[[], Any],
) -> str | None:
    source_key = _registration_cache_key(registration)
    if source_key is not None:
        cached = source_schema_revision_cache.get(source_key)
        if isinstance(cached, str) and cached.strip():
            return cached

    fetched_revision = _fetch_api_source_schema_revision(
        registration,
        client_factory=client_factory,
    )
    resolved_revision = fetched_revision or registration.planner_schema_revision
    if source_key is not None and isinstance(resolved_revision, str) and resolved_revision.strip():
        source_schema_revision_cache[source_key] = resolved_revision
    if isinstance(resolved_revision, str) and resolved_revision.strip():
        return resolved_revision
    return None


def _fetch_api_source_schema_revision(
    registration: SourceRegistration,
    *,
    client_factory: Callable[[], Any],
) -> str | None:
    source_id = registration.dataset_id or registration.source_id
    if not source_id:
        return None
    client = client_factory()
    fetcher = getattr(client, "_request", None)
    if not callable(fetcher):
        return None
    try:
        payload = fetcher("GET", f"/v1/sources/{source_id}")
    except Exception:
        return None
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    if not isinstance(payload, Mapping):
        return None
    entry = payload.get("entry")
    if isinstance(entry, Mapping):
        entry_revision = entry.get("source_schema_revision") or entry.get("schema_revision")
        if isinstance(entry_revision, str) and entry_revision.strip():
            return entry_revision
    schema = payload.get("schema")
    if isinstance(schema, Mapping):
        schema_revision = schema.get("schema_revision")
        if isinstance(schema_revision, str) and schema_revision.strip():
            return schema_revision
    return None


def _exact_metric_column(request: Mapping[str, Any], fields: set[str]) -> str | None:
    metric_value = request.get("metric_column")
    if isinstance(metric_value, str) and metric_value in fields:
        return metric_value
    metric_hint = request.get("metric")
    if isinstance(metric_hint, str) and metric_hint in fields:
        return metric_hint
    return None


_INVALID_EXACT_GROUP = object()


def _exact_group_column(request: Mapping[str, Any], fields: set[str]) -> str | None | object:
    group_value = request.get("group_column")
    if isinstance(group_value, str):
        return group_value if group_value in fields else _INVALID_EXACT_GROUP
    group_hint = request.get("group_by")
    if isinstance(group_hint, str):
        return group_hint if group_hint in fields else _INVALID_EXACT_GROUP
    if isinstance(group_hint, list):
        group_candidates = [
            item.strip() for item in group_hint if isinstance(item, str) and item.strip()
        ]
        if len(group_candidates) > 1:
            return _INVALID_EXACT_GROUP
        if not group_candidates:
            return None
        return group_candidates[0] if group_candidates[0] in fields else _INVALID_EXACT_GROUP
    return None


def _registration_cache_key(registration: SourceRegistration) -> str | None:
    for candidate in (registration.dataset_id, registration.source_id):
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return None


def _registration_resolved_source_name(registration: SourceRegistration) -> str:
    if isinstance(registration.source_schema, Mapping):
        source_name = registration.source_schema.get("source")
        if isinstance(source_name, str) and source_name.strip():
            return source_name.strip()
    if isinstance(registration.name, str) and registration.name.strip():
        return registration.name.strip()
    raise ValueError("API exact resolve requires a registration name.")
