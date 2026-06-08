"""Helpers extracted from query_sources endpoint — early group.

Originally extracted into _endpoints_resolve_query_helpers.py then split per
logical group so each file stays under 1000 lines.
"""
from __future__ import annotations
import time
from typing import Any, Callable
from fastapi import HTTPException
from apps.api_server.services.data_visibility import get_visible_dataset_entry
from apps.api_server.routers.data_map import _call_mojo_column_profile
from apps.api_server.routers.query_contract import QueryRequest, QueryResponse, ResolveRequest, _http_error
from apps.api_server.routers.query_resolve_fast_path import _resolved_plan_current_schema_revision
from apps.api_server.routers.query_response_helpers import _build_query_response, _exact_plan_basis, _immutable_plan_hash, _resolve_to_query_response
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.routers.query._state import _ALLOW_QUERY_HINT_PLANNING_COMPAT, _RESULT_CACHE, _RESULT_CACHE_TTL
from apps.api_server.routers.query._cache_classes import _get_registry_planner, _load_profiled_source
from apps.api_server.routers.query._schema_graph import _graph_nodes_from_meta
from apps.api_server.routers.query._signatures import _detect_relations, _query_uses_legacy_planning, _resolve_registered_intent

def _build_query_response(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    return _facade._build_query_response(*args, **kwargs)


def _call_mojo_column_profile(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    return _facade._call_mojo_column_profile(*args, **kwargs)


def _detect_relations(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._detect_relations
    if fn is _detect_relations:
        from apps.api_server.routers.query._signatures import _detect_relations as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def _get_registry_planner(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._get_registry_planner
    if fn is _get_registry_planner:
        from apps.api_server.routers.query._cache_classes import _get_registry_planner as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def _graph_nodes_from_meta(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._graph_nodes_from_meta
    if fn is _graph_nodes_from_meta:
        from apps.api_server.routers.query._schema_graph import _graph_nodes_from_meta as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def _load_profiled_source(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._load_profiled_source
    if fn is _load_profiled_source:
        from apps.api_server.routers.query._cache_classes import _load_profiled_source as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def execute(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.execute
    if fn is execute:
        from apps.api_server.routers.query._execute_main import execute as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def execute_cross_source(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.execute_cross_source
    if fn is execute_cross_source:
        from apps.api_server.routers.query._execute_main import execute_cross_source as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def execute_join_path(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.execute_join_path
    if fn is execute_join_path:
        from apps.api_server.routers.query._execute_main import execute_join_path as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def find_time_column(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.find_time_column
    if fn is find_time_column:
        from apps.api_server.routers.query._execute_filters import find_time_column as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def time_range(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.time_range
    if fn is time_range:
        from apps.api_server.routers.query._execute_filters import time_range as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)



# ════════════════════════════════════════════════════════════════════════
# Helpers extracted from ``query_sources`` (see _endpoints_resolve_query.py).
# Each helper preserves the original semantics; the endpoint dispatches into
# these in the same order as the original inline code.

def _owner_resolved_plan_fast_path(
    payload: QueryRequest,
    auth: AuthContext,
    org_id: str,
    request_id: str | None,
    query_id: str,
    plan: list[str],
    t0: float,
) -> tuple[QueryResponse | None, str | None]:
    """Owner-only resolved_plan fast path.

    Returns ``(response_or_None, schema_revision_or_None)``.
    * When the entry conditions are not met, returns ``(None, None)``.
    * When the resolved_plan + result-cache HIT is reached, returns
      ``(QueryResponse, schema_revision)``.
    * On a cache miss after entry, returns ``(None, schema_revision)`` so the
      caller can carry the schema_revision into downstream computations.
    Raises ``HTTPException`` 409 on schema_revision mismatch.

    Mutates ``plan`` (list[str]) in place by appending step descriptions.
    """
    if not (
        payload.resolved_plan is not None
        and not payload.dataset_id
        and str(auth.get("role", "")).lower() == "owner"
    ):
        return None, None

    current_schema_revision = _resolved_plan_current_schema_revision(
        org_id=org_id,
        resolved_plan=payload.resolved_plan,
    )
    if payload.resolved_plan.schema_revision != current_schema_revision:
        raise _http_error(
            409,
            code="schema_revision_mismatch",
            message=(
                "resolved_plan schema_revision no longer matches the current registry state."
            ),
            request_id=request_id,
        )

    owner_plan_basis = _exact_plan_basis(
        source_name=payload.resolved_plan.source_name,
        metric_column=payload.resolved_plan.metric_column,
        aggregation=payload.resolved_plan.aggregation,
        group_column=payload.resolved_plan.group_column,
        join_path=payload.resolved_plan.join_path,
        filter_spec=payload.resolved_plan.filter,
        limit=payload.resolved_plan.limit,
        order=payload.resolved_plan.order,
        constraints=payload.resolved_plan.constraints,
    )
    owner_plan_hash = _immutable_plan_hash(
        schema_revision=current_schema_revision,
        basis=owner_plan_basis,
    )
    owner_cached_result = _RESULT_CACHE.get(owner_plan_hash)
    if (
        owner_cached_result
        and (time.monotonic() - owner_cached_result.get("_ts", 0)) < _RESULT_CACHE_TTL
    ):
        plan.extend(
            [
                f"Resolved plan accepted [{payload.resolved_plan.schema_revision[:8]}]",
                f"Result cache HIT [{owner_plan_hash[:8]}] — zero I/O",
            ]
        )
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=owner_cached_result["result"],
            result_type=owner_cached_result["result_type"],
            confidence=owner_cached_result["confidence"],
            plan=plan,
            resolved_column=payload.resolved_plan.metric_column,
            resolved_role=owner_cached_result.get("resolved_role", ""),
            resolved_source=owner_cached_result.get(
                "resolved_source",
                payload.resolved_plan.source_name,
            ),
            row_count=owner_cached_result["row_count"],
            candidates=[],
            source_scores={},
            ambiguous=False,
            exact_spec=True,
            explanation=owner_cached_result.get("explanation", []),
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="exact_spec",
            schema_revision=current_schema_revision,
            validated=True,
            confidence_source="exact_spec_validation",
            plan_basis=owner_plan_basis,
            plan_hash_override=owner_plan_hash,
            log_response=False,
        ), current_schema_revision

    return None, current_schema_revision


def _apply_dataset_scope(
    payload: QueryRequest,
    auth: AuthContext,
    org_id: str,
    request_id: str | None,
    plan: list[str],
) -> list[dict[str, Any]] | None:
    """Validate dataset scoping and seed defaults from the dataset entry.

    Returns the single-element ``visible_registry_entries`` list scoped to the
    dataset when ``payload.dataset_id`` is set; ``None`` otherwise. Mutates
    ``payload.source_name`` / ``payload.preferred_source`` and appends to
    ``plan``. Raises ``HTTPException`` 422 (inline-sources mix) or 404
    (dataset not visible).
    """
    if not payload.dataset_id:
        return None
    if payload.sources:
        raise _http_error(
            422,
            code="invalid_query_request",
            message="dataset_id cannot be combined with inline sources.",
            request_id=request_id,
        )
    dataset_entry = get_visible_dataset_entry(org_id, payload.dataset_id, auth)
    if dataset_entry is None:
        raise _http_error(
            404,
            code="not_found",
            message=f"Dataset '{payload.dataset_id}' not found.",
            request_id=request_id,
        )
    if payload.source_name is None:
        payload.source_name = str(dataset_entry.get("name") or "")
    if payload.preferred_source is None:
        payload.preferred_source = str(dataset_entry.get("name") or "")
    plan.append(
        f"Dataset scope: {payload.dataset_id} -> "
        f"{payload.source_name or payload.preferred_source}"
    )
    return [dataset_entry]


def _apply_resolved_plan(
    payload: QueryRequest,
    auth: AuthContext,
    org_id: str,
    request_id: str | None,
    plan: list[str],
    visible_registry_entries_loader: Callable[[], list[dict[str, Any]]],
) -> str | None:
    """Validate ``payload.resolved_plan`` and overlay it onto the payload.

    Returns the live ``current_schema_revision`` when a resolved_plan was
    accepted (so the caller can update its
    ``resolved_plan_schema_revision`` local), ``None`` otherwise. Mutates
    ``payload`` by copying fields from ``payload.resolved_plan`` and appends a
    plan step. Raises ``HTTPException`` 409 (schema mismatch) or 422
    (dataset_scope_violation).
    """
    if payload.resolved_plan is None:
        return None
    visible_entries_for_resolved_plan: list[dict[str, Any]] | None = None
    if not payload.dataset_id and str(auth.get("role", "")).lower() != "owner":
        visible_entries_for_resolved_plan = visible_registry_entries_loader()
    current_schema_revision = _resolved_plan_current_schema_revision(
        org_id=org_id,
        resolved_plan=payload.resolved_plan,
        dataset_id=payload.dataset_id,
        visible_entries=visible_entries_for_resolved_plan,
    )
    if payload.resolved_plan.schema_revision != current_schema_revision:
        raise _http_error(
            409,
            code="schema_revision_mismatch",
            message=(
                "resolved_plan schema_revision no longer matches the current registry state."
            ),
            request_id=request_id,
        )
    if payload.dataset_id:
        allowed_sources = {
            str(entry.get("name") or "") for entry in visible_registry_entries_loader()
        }
        if payload.resolved_plan.source_name not in allowed_sources:
            raise _http_error(
                422,
                code="dataset_scope_violation",
                message=("resolved_plan source_name is outside the requested dataset scope."),
                request_id=request_id,
            )
    payload.source_name = payload.resolved_plan.source_name
    payload.metric_column = payload.resolved_plan.metric_column
    payload.group_column = payload.resolved_plan.group_column
    payload.join_path = payload.resolved_plan.join_path
    payload.aggregation = payload.resolved_plan.aggregation
    payload.filter = payload.resolved_plan.filter
    payload.limit = payload.resolved_plan.limit
    payload.order = payload.resolved_plan.order
    payload.constraints = payload.resolved_plan.constraints
    plan.append(f"Resolved plan accepted [{payload.resolved_plan.schema_revision[:8]}]")
    return current_schema_revision


async def _apply_legacy_planning_fallback(
    payload: QueryRequest,
    auth: AuthContext,
    request_id: str | None,
    query_id: str,
    plan: list[str],
) -> QueryResponse | None:
    """Deprecated query-planning-compat shim.

    Runs ``_resolve_registered_intent`` when the payload trips the legacy
    planning condition. Returns a short-circuit ``QueryResponse`` when no
    resolved_plan came back (the endpoint must return it immediately);
    returns ``None`` after mutating the payload with the resolved plan so the
    exact-spec branch can proceed. Raises ``HTTPException`` 422 when legacy
    compat is disabled.
    """
    if not _query_uses_legacy_planning(payload):
        return None
    if not _ALLOW_QUERY_HINT_PLANNING_COMPAT:
        raise _http_error(
            422,
            code="planning_not_allowed_on_query",
            message="Use POST /v1/resolve before POST /v1/query.",
            request_id=request_id,
        )
    resolve_response = await _resolve_registered_intent(
        ResolveRequest(
            dataset_id=payload.dataset_id,
            metric=payload.metric,
            group_by=payload.group_by,
            preferred_source=payload.preferred_source,
            reject_on_ambiguity=payload.reject_on_ambiguity,
            min_source_confidence=payload.min_source_confidence,
            aggregation=payload.aggregation,
            filter=payload.filter,
            limit=payload.limit,
            order=payload.order,
            constraints=payload.constraints,
            allow_org_scope=True,
            include_explanation=False,
        ),
        auth=auth,
        request_id=request_id,
    )
    plan.append("Deprecated query planning compatibility used; prefer POST /v1/resolve.")
    if resolve_response.resolved_plan is None:
        resolve_query_response = _resolve_to_query_response(
            query_id=query_id,
            resolve_response=resolve_response,
        )
        resolve_query_response.plan.insert(0, plan[-1])
        return resolve_query_response
    payload.source_name = resolve_response.resolved_plan.source_name
    payload.metric_column = resolve_response.resolved_plan.metric_column
    payload.group_column = resolve_response.resolved_plan.group_column
    payload.join_path = resolve_response.resolved_plan.join_path
    payload.aggregation = resolve_response.resolved_plan.aggregation
    payload.filter = resolve_response.resolved_plan.filter
    payload.limit = resolve_response.resolved_plan.limit
    payload.order = resolve_response.resolved_plan.order
    payload.constraints = resolve_response.resolved_plan.constraints
    plan.extend(resolve_response.plan)
    return None


