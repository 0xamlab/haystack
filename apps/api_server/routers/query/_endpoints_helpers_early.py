"""Helpers extracted from query_sources endpoint — early group.

Originally extracted into _endpoints_resolve_query_helpers.py then split per
logical group so each file stays under 1000 lines.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import math
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from apps.api_server.services import source_registry as _sreg_visible
from apps.api_server.services.data_visibility import (
    filter_visible_datasets, get_visible_dataset_entry, get_visible_source_entry_by_name,
)

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.routers.data_map import (
    _call_mojo_column_profile, _clear_optional_mojo_engine_failure, _get_optional_mojo_engine_skip_reason, _invoke_optional_mojo_engine, _load_source, _load_source_table,
    _record_optional_mojo_engine_failure,
)
from apps.api_server.routers.query_contract import (
    _DECISION_AUTO_ACCEPT_CONFIDENCE, _MAX_JOIN_PATH_HOPS, ALL_ROLES, BASE_MEASURE, CATEGORY, COMPONENT,
    DERIVED_MEASURE, IDENTIFIER, METRIC, RATIO, TEXT, TIME,
    UNIT_MEASURE, CandidateColumn, ConstraintSpec, FilterConditionSpec, FilterSpec, JoinEdgeSpec,
    JoinPathSpec, QueryBatchDefaults, QueryBatchError, QueryBatchItemRequest, QueryBatchItemResponse, QueryBatchRequest,
    QueryBatchResponse, QueryExecutionMetadata, QueryRequest, QueryResponse, ResolvedPlan, ResolveRequest,
    ResolveResponse, SQLReportRequest, SQLReportResponse, _classify_query_rejection, _decision_contract_flags, _http_error,
    _query_plan_hash, _select_count_anchor_column,
)
from apps.api_server.routers.query_contract import (
    _DEFAULT_JOIN_PATH_HOPS as _QUERY_CONTRACT_DEFAULT_JOIN_PATH_HOPS,
)
from apps.api_server.routers.query_contract import (
    MetricSpec as _MetricSpec,
)
from apps.api_server.routers.query_contract import (
    QueryPayload as _QueryPayload,
)
from apps.api_server.routers.query_profiling import (
    _profile_arrow_table, _profile_records_and_arrow, _relation_detect_sample_limit,
)
from apps.api_server.routers.query_profiling import (
    _profile_records as _query_profile_records,
)
from apps.api_server.routers.query_profiling import (
    _try_numeric as _query_try_numeric,
)
from apps.api_server.routers.query_registry_planner import (
    get_registry_planner as _get_registry_planner_impl,
)
from apps.api_server.routers.query_registry_planner import (
    planner_auth_scope_key as _query_planner_auth_scope_key,
)
from apps.api_server.routers.query_registry_planner import (
    run_cached_planner_method as _query_run_cached_planner_method,
)
from apps.api_server.routers.query_registry_planner import (
    try_incremental_registry_planner_update as _try_incremental_registry_planner_update_impl,
)
from apps.api_server.routers.query_resolve_dataset_meta import (
    dataset_exact_column_lookup as _dataset_exact_column_lookup_impl,
)
from apps.api_server.routers.query_resolve_dataset_meta import (
    find_exact_dataset_column as _find_exact_dataset_column_impl,
)
from apps.api_server.routers.query_resolve_dataset_meta import (
    find_exact_dataset_column_cached as _find_exact_dataset_column_cached_impl,
)
from apps.api_server.routers.query_resolve_dataset_meta import (
    get_resolve_dataset_meta as _get_resolve_dataset_meta_impl,
)
from apps.api_server.routers.query_resolve_fast_path import (
    _dataset_candidate_payload as _query_dataset_candidate_payload,
)
from apps.api_server.routers.query_resolve_fast_path import (
    _resolve_entry_ready, _resolved_plan_current_schema_revision,
)
from apps.api_server.routers.query_resolve_fast_path import (
    _resolve_scope_entries as _query_resolve_scope_entries,
)
from apps.api_server.routers.query_resolve_fast_path import (
    resolve_single_dataset_fast_path as _resolve_single_dataset_fast_path_impl,
)
from apps.api_server.routers.query_resolve_registered import (
    resolve_registered_intent as _resolve_registered_intent_impl,
)
from apps.api_server.routers.query_response_helpers import (
    _MAX_RESOLVE_CANDIDATES, _build_query_response, _build_resolve_response, _compute_exact_confidence, _dedupe_source_values, _exact_plan_basis,
    _immutable_plan_hash, _normalize_constraint_spec, _normalize_filter_spec, _resolve_to_query_response,
)
from apps.api_server.routers.query_response_helpers import (
    _MAX_RESOLVE_SOURCE_SCORES as _QUERY_RESPONSE_MAX_RESOLVE_SOURCE_SCORES,
)
from apps.api_server.routers.query_response_helpers import (
    _normalize_candidates as _query_normalize_candidates,
)
from apps.api_server.routers.query_response_helpers import (
    _normalize_join_path as _query_normalize_join_path,
)
from apps.api_server.routers.query_response_helpers import (
    _normalize_join_path_spec as _query_normalize_join_path_spec,
)
from apps.api_server.routers.query_response_helpers import (
    _resolved_source_set as _query_resolved_source_set,
)
from apps.api_server.schemas.data_map import DataSource
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.data_map_errors import MojoInstrumentationError
from apps.api_server.services.data_map_mojo_profiles import (
    _build_mojo_column_profile_columns, _mojo_column_profile_sample_limits, _mojo_profiling_disabled_status, _mojo_profiling_status_from_result,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.sql_report_service import (
    SQLReportServiceError, execute_sql_report, normalize_sql_report_alias,
)


from apps.api_server.routers.query._state import *  # noqa: F401, F403
from apps.api_server.routers.query._state import (  # noqa: F401
    _ALLOW_QUERY_HINT_PLANNING_COMPAT,
    _CACHE_LOCK,
    _CACHE_MAX_SOURCES,
    _DATASET_EXACT_COLUMN_CACHE,
    _DATASET_EXACT_COLUMN_CACHE_MAX,
    _DEFAULT_JOIN_PATH_HOPS,
    _DF_CACHE,
    _DF_CACHE_MAX,
    _DIM_COUNT,
    _DIM_CURRENCY,
    _DIM_IDENTIFIER,
    _DIM_INVALID,
    _DIM_RATE,
    _DIM_RATIO,
    _DIM_TO_ROLE,
    _DIM_UNKNOWN,
    _GRAPH_NODE_CACHE,
    _GRAPH_NODE_CACHE_MAX,
    _MAX_RESOLVE_SOURCE_SCORES,
    _PATH_CACHE_TTL,
    _PLANNER_CACHE,
    _PLANNER_CACHE_MAX,
    _QUERY_RELATION_DETECT_COOLDOWN_S,
    _QUERY_RELATION_DETECT_FAILURE,
    _RESOLVE_BUDGET_MS,
    _RESOLVE_CACHE,
    _RESOLVE_CACHE_MAX,
    _RESOLVE_CACHE_TTL,
    _RESULT_CACHE,
    _RESULT_CACHE_MAX,
    _RESULT_CACHE_TTL,
    _ROLE_TO_DIM,
    _SOURCE_BEHAVIOR_RULES,
    _SOURCE_CACHE,
    _STOP_TOKENS,
    _VERIFY_CACHE,
    _VERIFY_CACHE_MAX,
    _VERIFY_CACHE_TTL,
    _clear_query_relation_detect_failure,
    _dataset_candidate_payload,
    _get_query_relation_detect_skip_reason,
    _normalize_candidates,
    _normalize_join_path,
    _normalize_join_path_spec,
    _planner_auth_scope_key,
    _profile_records,
    _record_query_relation_detect_failure,
    _resolve_scope_entries,
    _resolved_source_set,
    _run_cached_planner_method,
    _try_numeric,
)
from apps.api_server.routers.query._cache_classes import *  # noqa: F401, F403
from apps.api_server.routers.query._cache_classes import (  # noqa: F401
    _CachedFrame,
    _CachedPlanner,
    _CachedSource,
    _LoadedProfiledSource,
    _df_cache_get,
    _df_cache_put,
    _df_cache_records,
    _evict_lru,
    _evict_planner_lru,
    _get_registry_planner,
    _load_profiled_source,
    _planner_join_is_execution_safe,
    _planner_load_bearing_validation_notes,
    _planner_metric_candidate_payloads,
    _planner_query_confidence,
    _raise_empty_source,
    _source_cache_key,
    _source_cache_put,
    _source_cache_unique_entries,
    _try_incremental_registry_planner_update,
)
from apps.api_server.routers.query._schema_graph import *  # noqa: F401, F403
from apps.api_server.routers.query._schema_graph import (  # noqa: F401
    _arrow_physical_types,
    _build_schema_metadata,
    _col_name_signals_id,
    _dim_propagate,
    _graph_nodes_from_meta,
    _infer_source_behavior,
    _is_count_like,
    _looks_like_date,
)
from apps.api_server.routers.query._resolvers import *  # noqa: F401, F403
from apps.api_server.routers.query._resolvers import (  # noqa: F401
    _METRIC_CONCEPTS,
    _METRIC_HINT_STOPWORDS,
    _METRIC_TOKEN_CANON,
    _MIN_JOIN_CONFIDENCE,
    _SOURCE_PRIOR_TOKENS,
    _call_mojo_source_score,
    _find_best_join_key,
    _match_join_path_edge,
    _metric_candidate_score,
    _metric_concepts,
    _metric_source_prior_bonus,
    _metric_tokens,
    _resolve_join_path,
    _reverse_cardinality,
)
from apps.api_server.routers.query._execute_filters import *  # noqa: F401, F403
from apps.api_server.routers.query._execute_filters import (  # noqa: F401
    _FILTER_DIMENSION_ROLES,
    _FILTER_FALSE_VALUES,
    _FILTER_NULL_OPS,
    _FILTER_NUMERIC_OPS,
    _FILTER_TRUE_VALUES,
    _apply_filter_conditions,
    _blankish_value,
    _filter_boolean_like,
    _filter_field_match_score,
    _filter_number_like,
    _filter_value_equals,
    _filter_value_is_nullish,
    _has_populated_cell,
    _num,
    _parse_date,
    _preferred_filter_value_type,
    _quarter_bounds,
    _resolve_col_name,
    _resolve_filter_condition_column,
    _resolve_filter_conditions,
    _row_matches_filter_condition,
    _sample_boolean_field,
    _sample_numeric_field,
)
from apps.api_server.routers.query._execute_main import *  # noqa: F401, F403
from apps.api_server.routers.query._signatures import *  # noqa: F401, F403
from apps.api_server.routers.query._signatures import (  # noqa: F401
    _dataset_exact_column_cache_get,
    _dataset_exact_column_cache_put,
    _dataset_exact_column_lookup,
    _detect_relations,
    _exact_query_required_sources,
    _find_exact_dataset_column,
    _find_exact_dataset_column_cached,
    _get_resolve_dataset_meta,
    _graph_node_cache_get,
    _graph_node_cache_put,
    _graph_nodes_from_cached_meta,
    _inline_schema_revision,
    _intent_signature,
    _intent_signature_payload,
    _merge_query_batch_defaults,
    _normalize_hint_text,
    _prune_resolve_cache,
    _query_batch_error_from_exception,
    _query_execution_metadata,
    _query_uses_legacy_planning,
    _resolve_cache_get,
    _resolve_cache_put,
    _resolve_registered_intent,
    _resolve_single_dataset_fast_path,
    _stable_list,
    _weak_raw_text_intent,
)
# Lazy facade-routed wrappers for monkey-patched / cross-layer names.
# Tests patch apps.api_server.routers.query.X = fake; each call here
# re-reads the attribute from the facade so the patch propagates.
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


