"""Submodule _endpoints_resolve_query.py of apps.api_server.routers.query.

Extracted from apps/api_server/routers/query.py during modularization.
Items in this submodule are listed in /tmp/query_split_assignments.json.
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
from typing import Any, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.routers.data_map import (
    _call_mojo_column_profile,
    _clear_optional_mojo_engine_failure,
    _get_optional_mojo_engine_skip_reason,
    _invoke_optional_mojo_engine,
    _load_source,
    _load_source_table,
    _record_optional_mojo_engine_failure,
)
from apps.api_server.routers.query_contract import (
    _DECISION_AUTO_ACCEPT_CONFIDENCE,
    _MAX_JOIN_PATH_HOPS,
    ALL_ROLES,
    BASE_MEASURE,
    CATEGORY,
    COMPONENT,
    DERIVED_MEASURE,
    IDENTIFIER,
    METRIC,
    RATIO,
    TEXT,
    TIME,
    UNIT_MEASURE,
    CandidateColumn,
    ConstraintSpec,
    FilterConditionSpec,
    FilterSpec,
    JoinEdgeSpec,
    JoinPathSpec,
    QueryBatchDefaults,
    QueryBatchError,
    QueryBatchItemRequest,
    QueryBatchItemResponse,
    QueryBatchRequest,
    QueryBatchResponse,
    QueryExecutionMetadata,
    QueryRequest,
    QueryResponse,
    ResolvedPlan,
    ResolveRequest,
    ResolveResponse,
    SQLReportRequest,
    SQLReportResponse,
    _classify_query_rejection,
    _decision_contract_flags,
    _http_error,
    _query_plan_hash,
    _select_count_anchor_column,
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
    _profile_arrow_table,
    _profile_records_and_arrow,
    _relation_detect_sample_limit,
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
    _resolve_entry_ready,
    _resolved_plan_current_schema_revision,
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
    _MAX_RESOLVE_CANDIDATES,
    _build_query_response,
    _build_resolve_response,
    _compute_exact_confidence,
    _dedupe_source_values,
    _exact_plan_basis,
    _immutable_plan_hash,
    _normalize_constraint_spec,
    _normalize_filter_spec,
    _resolve_to_query_response,
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
    _build_mojo_column_profile_columns,
    _mojo_column_profile_sample_limits,
    _mojo_profiling_disabled_status,
    _mojo_profiling_status_from_result,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime
from apps.api_server.services.sql_report_service import (
    SQLReportServiceError,
    execute_sql_report,
    normalize_sql_report_alias,
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


@router.post(
    "/v1/resolve",
    response_model=ResolveResponse,
    summary="Resolve structured intent into an exact executable plan",
    description=(
        "**Bounded deterministic planner.**\n\n"
        "This endpoint resolves structured intent into an exact plan for `POST /v1/query`.\n"
        "It only uses registered-source metadata, join graph metadata, planner cache, and "
        "precomputed statistics. It does not scan datasets or execute queries.\n\n"
        "**Scope rules:**\n"
        "- Provide `dataset_id` for dataset-scoped planning, or\n"
        "- set `allow_org_scope=true` to plan across all visible datasets.\n\n"
        "**Deterministic guarantees:**\n"
        "- identical intent_signature + schema_revision + scope => identical output\n"
        "- ambiguity clarifies or rejects; it never expands search\n"
        "- no fallback to slower planning paths exists\n"
    ),
)
async def resolve_sources(
    payload: ResolveRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
) -> ResolveResponse:
    request_id = getattr(request.state, "request_id", None)
    return await _resolve_registered_intent(payload, auth=auth, request_id=request_id)

@router.post(
    "/v1/query",
    response_model=QueryResponse,
    summary="Execute a structured query — schema-free, zero domain assumptions",
    description=(
        "**Structured query execution engine.**\n\n"
        "This endpoint takes structured intent — produced by an LLM from the user's "
        "natural-language question. It does NOT accept raw text.\n\n"
        "**Separation of concerns:**\n"
        "- LLM: language → structured intent, ambiguity resolution, user interaction\n"
        "- Algenta: schema understanding, math relationships, fast execution, correctness\n\n"
        "**Role resolution:**\n"
        "1. Detect derived formulas across all numeric column triples (Mojo, ~100ms)\n"
        "2. Assign structural roles: derived_measure, base_measure, unit_measure…\n"
        "3. Match requested role → best column\n"
        "4. Execute aggregation, return result + all candidates for LLM disambiguation\n\n"
        "**Ambiguity handling:**\n"
        "If confidence < 0.7, check `candidates` — multiple columns may match the role. "
        "The LLM can present options to the user or pick the most contextually appropriate one."
    ),
)
async def query_sources(
    payload: QueryRequest,
    request: Request = cast(Request, None),
    auth: AuthContext = Depends(get_current_org),
) -> QueryResponse:
    t0 = time.monotonic()
    query_id = str(uuid.uuid4())
    plan: list[str] = []
    org_id = str(auth["org_id"])
    request_id = getattr(request.state, "request_id", None) if request is not None else None
    from apps.api_server.services import source_registry as _sreg_visible
    from apps.api_server.services.data_visibility import (
        filter_visible_datasets,
        get_visible_dataset_entry,
        get_visible_source_entry_by_name,
    )

    visible_registry_entries: list[dict[str, Any]] | None = None
    resolved_plan_schema_revision: str | None = None

    def _visible_registry_entries() -> list[dict[str, Any]]:
        nonlocal visible_registry_entries
        if visible_registry_entries is None:
            visible_registry_entries = filter_visible_datasets(
                _sreg_visible.list_sources(org_id),
                auth,
            )
        return visible_registry_entries

    if (
        payload.resolved_plan is not None
        and not payload.dataset_id
        and str(auth.get("role", "")).lower() == "owner"
    ):
        current_schema_revision = _resolved_plan_current_schema_revision(
            org_id=org_id,
            resolved_plan=payload.resolved_plan,
        )
        resolved_plan_schema_revision = current_schema_revision
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
            )

    if payload.dataset_id:
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
        visible_registry_entries = [dataset_entry]
        if payload.source_name is None:
            payload.source_name = str(dataset_entry.get("name") or "")
        if payload.preferred_source is None:
            payload.preferred_source = str(dataset_entry.get("name") or "")
        plan.append(
            f"Dataset scope: {payload.dataset_id} -> "
            f"{payload.source_name or payload.preferred_source}"
        )

    if payload.resolved_plan is not None:
        visible_entries_for_resolved_plan: list[dict[str, Any]] | None = None
        if not payload.dataset_id and str(auth.get("role", "")).lower() != "owner":
            visible_entries_for_resolved_plan = _visible_registry_entries()
        current_schema_revision = _resolved_plan_current_schema_revision(
            org_id=org_id,
            resolved_plan=payload.resolved_plan,
            dataset_id=payload.dataset_id,
            visible_entries=visible_entries_for_resolved_plan,
        )
        resolved_plan_schema_revision = current_schema_revision
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
                str(entry.get("name") or "") for entry in _visible_registry_entries()
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

    if _query_uses_legacy_planning(payload):
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

    # ══════════════════════════════════════════════════════════════════════
    # EXACT-SPEC PATH — LLM supplied source_name + metric_column explicitly.
    # Mojo verifies and executes: no source resolver, no column resolver,
    # no semantic guessing. This is the correct production path.
    # ══════════════════════════════════════════════════════════════════════
    if payload.source_name and payload.metric_column:
        plan.append(
            f"Exact-spec: source={payload.source_name}  metric={payload.metric_column}"
            + (f"  group={payload.group_column}" if payload.group_column else "")
            + (f"  join_hops={len(payload.join_path.edges)}" if payload.join_path else "")
        )

        import pandas as pd

        from apps.api_server.services import source_registry as _sreg_ex

        if resolved_plan_schema_revision is not None:
            schema_revision_exact = resolved_plan_schema_revision
        elif payload.dataset_id and not payload.join_path:
            dataset_source_revision = ""
            if visible_registry_entries:
                dataset_source_revision = str(
                    visible_registry_entries[0].get("source_schema_revision") or ""
                )
            schema_revision_exact = dataset_source_revision or _sreg_ex.source_schema_revision(
                org_id, str(payload.dataset_id)
            )
        elif payload.join_path:
            schema_revision_exact = _sreg_ex.schema_revision(org_id)
        else:
            exact_visible_entries = visible_registry_entries
            if exact_visible_entries is None and str(auth.get("role", "")).lower() != "owner":
                exact_visible_entries = _visible_registry_entries()
            schema_revision_exact = _resolved_plan_current_schema_revision(
                org_id=org_id,
                resolved_plan=ResolvedPlan(
                    source_name=payload.source_name,
                    metric_column=payload.metric_column,
                    aggregation=payload.aggregation,
                    group_column=payload.group_column,
                    join_path=payload.join_path,
                    filter=payload.filter,
                    limit=payload.limit,
                    order=payload.order,
                    constraints=payload.constraints,
                    schema_revision="",
                ),
                dataset_id=payload.dataset_id,
                visible_entries=exact_visible_entries,
            )
        exact_plan_basis = _exact_plan_basis(
            source_name=payload.source_name,
            metric_column=payload.metric_column,
            aggregation=payload.aggregation,
            group_column=payload.group_column,
            join_path=payload.join_path,
            filter_spec=payload.filter,
            limit=payload.limit,
            order=payload.order,
            constraints=payload.constraints,
        )
        exact_plan_hash = _immutable_plan_hash(
            schema_revision=schema_revision_exact,
            basis=exact_plan_basis,
        )

        # ── Result cache check (BEFORE any I/O) ───────────────────────────────
        # Plan key is built from request payload — no source I/O needed.
        _plan_key_early = exact_plan_hash

        _cached_early = _RESULT_CACHE.get(_plan_key_early)
        if _cached_early and (time.monotonic() - _cached_early.get("_ts", 0)) < _RESULT_CACHE_TTL:
            plan.append(f"Result cache HIT [{_plan_key_early[:8]}] — zero I/O")
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=_cached_early["result"],
                result_type=_cached_early["result_type"],
                confidence=_cached_early["confidence"],
                plan=plan,
                resolved_column=payload.metric_column,
                resolved_role=_cached_early.get("resolved_role", ""),
                resolved_source=_cached_early.get("resolved_source", payload.source_name),
                row_count=_cached_early["row_count"],
                candidates=[],
                source_scores={},
                ambiguous=False,
                exact_spec=True,
                explanation=_cached_early.get("explanation", []),
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="exact_spec",
                schema_revision=schema_revision_exact,
                validated=True,
                confidence_source="exact_spec_validation",
                plan_basis=exact_plan_basis,
                plan_hash_override=exact_plan_hash,
                log_response=False,
            )

        if payload.dataset_id and visible_registry_entries is not None:
            registered_ex = {
                str(entry.get("name") or ""): entry for entry in visible_registry_entries
            }
        elif str(auth.get("role", "")).lower() == "owner" and payload.source_name:
            # Workspace/visibility-gated by-name lookup (was an unscoped cross-tenant read).
            owner_entry = get_visible_source_entry_by_name(org_id, payload.source_name, auth)
            registered_ex = (
                {str(owner_entry.get("name") or ""): owner_entry} if owner_entry is not None else {}
            )
        else:
            registered_ex = {
                str(entry.get("name") or ""): entry for entry in _visible_registry_entries()
            }
        for exact_source_name in _exact_query_required_sources(payload):
            if exact_source_name in registered_ex:
                continue
            extra_entry = get_visible_source_entry_by_name(org_id, exact_source_name, auth)
            if extra_entry is not None:
                registered_ex[exact_source_name] = extra_entry
        if payload.source_name not in registered_ex:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "source_not_found",
                        "message": f"Source '{payload.source_name}' not registered. "
                        f"Available: {sorted(registered_ex)}",
                    }
                },
            )

        metric_entry_meta = registered_ex[payload.source_name]
        metric_source_id = str(metric_entry_meta["id"])
        metric_cached_source = _SOURCE_CACHE.get(metric_source_id)
        metric_schema_meta = _sreg_ex.get_source_meta(org_id, metric_source_id) or {}
        if (
            metric_cached_source
            and metric_cached_source.is_fresh()
            and metric_cached_source.graph_nodes
        ):
            metric_cached_source.touch()
            metric_nodes = metric_cached_source.graph_nodes
        else:
            metric_nodes = _graph_nodes_from_cached_meta(
                org_id=org_id,
                dataset_id=metric_source_id,
                schema_revision=str(metric_entry_meta.get("schema_revision", "") or ""),
                schema_meta=metric_schema_meta,
            )

        # Validate metric column exists
        if payload.metric_column not in metric_nodes:
            available = sorted(metric_nodes.keys())
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "column_not_found",
                        "message": (
                            f"Column '{payload.metric_column}' not in "
                            f"'{payload.source_name}'. Available columns: {available[:20]}"
                        ),
                        "suggestions": [
                            c for c in available if payload.metric_column.lower() in c.lower()
                        ][:5],
                    }
                },
            )

        metric_node = metric_nodes[payload.metric_column]

        # ── Constraint enforcement ────────────────────────────────────────────────
        if payload.constraints.requires_derived and metric_node.role != "derived_measure":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "constraint_violated",
                        "constraint": "requires_derived",
                        "reason": (
                            f"Column '{payload.metric_column}' has role "
                            f"'{metric_node.role}', not 'derived_measure'."
                        ),
                        "suggestion": (
                            "Use a column with role=derived_measure. "
                            f"Available in {payload.source_name}: "
                        )
                        + str(
                            [c for c, n in metric_nodes.items() if n.role == "derived_measure"][:5]
                        ),
                    }
                },
            )

        if payload.constraints.no_cross_source and payload.join_path and payload.join_path.edges:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "constraint_violated",
                        "constraint": "no_cross_source",
                        "reason": "Cross-source join requested but no_cross_source=true.",
                    }
                },
            )

        direct_count_fast_path = (
            payload.aggregation == "count"
            and payload.group_column is None
            and payload.join_path is None
            and not (payload.filter and (payload.filter.time_filter or payload.filter.conditions))
        )
        if direct_count_fast_path:
            row_count_exact = int(
                metric_entry_meta.get("row_count") or metric_schema_meta.get("row_count") or 0
            )
            result_ex = float(row_count_exact)
            result_type_ex = "scalar"
            computed_confidence, col_conf, agg_conf = _compute_exact_confidence(
                metric_node,
                payload.aggregation,
                1.0,
            )
            if col_conf < payload.constraints.min_column_confidence:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "constraint_violated",
                            "constraint": "min_column_confidence",
                            "reason": (
                                f"Column '{payload.metric_column}' has "
                                f"column_confidence={col_conf:.2f}, which is below "
                                "min_column_confidence="
                                f"{payload.constraints.min_column_confidence:.2f}."
                            ),
                        }
                    },
                )

            explanation = [
                f"Source: {payload.source_name}",
                f"Column: {payload.metric_column}  role={metric_node.role}"
                + (f"  formula={metric_node.formula}" if metric_node.formula else ""),
                f"Aggregation: {payload.aggregation}",
                f"Result: {result_type_ex}  = {result_ex}",
                "Confidence: "
                f"{computed_confidence:.3f} = col({col_conf:.2f}) × agg({agg_conf:.2f})",
            ]
            if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
                oldest = min(_RESULT_CACHE.items(), key=lambda x: x[1].get("_ts", 0))
                del _RESULT_CACHE[oldest[0]]
            _RESULT_CACHE[exact_plan_hash] = {
                "result": result_ex,
                "result_type": result_type_ex,
                "row_count": row_count_exact,
                "confidence": computed_confidence,
                "resolved_role": metric_node.role,
                "resolved_source": payload.source_name,
                "explanation": explanation,
                "_ts": time.monotonic(),
            }
            plan.append(f"COUNT: {row_count_exact:,} rows (metadata fast path)")
            plan.append(f"Result cache STORED [{exact_plan_hash[:8]}]")
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=result_ex,
                result_type=result_type_ex,
                confidence=computed_confidence,
                plan=plan,
                resolved_column=payload.metric_column,
                resolved_role=metric_node.role,
                resolved_source=payload.source_name,
                row_count=row_count_exact,
                candidates=[],
                source_scores={},
                ambiguous=False,
                exact_spec=True,
                explanation=explanation,
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="exact_spec",
                schema_revision=schema_revision_exact,
                validated=True,
                confidence_source="exact_spec_validation",
                plan_basis=exact_plan_basis,
                source_set=[payload.source_name],
                join_path=[],
                planner_mode="exact_spec",
                plan_hash_override=exact_plan_hash,
            )

        def _load_exact(name: str) -> tuple[list[dict[str, Any]], dict[str, ColumnNode]]:
            """Load records + graph nodes for an exact-spec source.
            Three-tier cache: DataFrame cache → Parquet bytes cache → disk.
            """
            entry_meta = registered_ex.get(name)
            if not entry_meta:
                raise ValueError(f"Source '{name}' not registered")
            src_id = entry_meta["id"]

            # Tier 1: DataFrame cache — fastest, no deserialization
            cached_df = _df_cache_get(src_id)
            if cached_df is not None:
                plan.append(f"DF cache HIT [{name}] — DataFrame hot")
                nodes = _SOURCE_CACHE[src_id].graph_nodes if src_id in _SOURCE_CACHE else {}
                if not nodes:
                    schema_meta = _sreg_ex.get_source_meta(org_id, src_id) or {}
                    nodes = _graph_nodes_from_cached_meta(
                        org_id=org_id,
                        dataset_id=src_id,
                        schema_revision=str(entry_meta.get("schema_revision", "") or ""),
                        schema_meta=schema_meta,
                    )
                return _df_cache_records(src_id, cached_df), nodes

            # Tier 2: Parquet bytes in memory — parse once, store DataFrame
            cached = _SOURCE_CACHE.get(src_id)
            if cached and cached.is_fresh():
                cached.touch()
                plan.append(f"Parquet cache HIT [{name}] — parsing bytes")
                buf = io.BytesIO(cached.parquet_bytes)
                initialize_pyarrow_parquet_runtime()
                df = pd.read_parquet(buf)
                _df_cache_put(src_id, df)
                cached_frame = _df_cache_get(src_id)
                assert cached_frame is not None
                return _df_cache_records(src_id, cached_frame), cached.graph_nodes

            # Tier 3: Disk fallback
            plan.append(f"Cache MISS [{name}] — reading from disk")
            parquet_bytes = _sreg_ex.get_source_parquet(org_id, src_id)
            if not parquet_bytes:
                raise ValueError(f"No data for source '{name}'")
            schema_meta = _sreg_ex.get_source_meta(org_id, src_id) or {}
            nodes = _graph_nodes_from_cached_meta(
                org_id=org_id,
                dataset_id=src_id,
                schema_revision=str(entry_meta.get("schema_revision", "") or ""),
                schema_meta=schema_meta,
            )
            buf = io.BytesIO(parquet_bytes)
            initialize_pyarrow_parquet_runtime()
            df = pd.read_parquet(buf)
            _df_cache_put(src_id, df)
            cached_frame = _df_cache_get(src_id)
            assert cached_frame is not None
            return _df_cache_records(src_id, cached_frame), nodes

        try:
            metric_records, metric_nodes = _load_exact(payload.source_name)
        except ValueError as _e:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "load_error", "message": str(_e)}},
            ) from _e

        try:
            resolved_filter_conditions_ex = _resolve_filter_conditions(
                source_name=payload.source_name,
                filter_spec=payload.filter,
                graph_nodes=metric_nodes,
                records=metric_records,
            )
        except ValueError as _e:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_filter_condition",
                        "message": str(_e),
                    }
                },
            ) from _e

        metric_records, filter_plan_ex = _apply_filter_conditions(
            metric_records,
            resolved_filter_conditions_ex,
        )
        plan.extend(filter_plan_ex)

        # Validate group column if given
        group_col_ex: str | None = payload.group_column
        cross_ex = False
        join_confidence_ex: float = 1.0
        join_path_edges_ex: list[JoinEdgeSpec] = []
        join_group_source_ex: str | None = None
        join_edge_meta_ex: list[tuple[float, str]] = []
        join_records_ex: dict[str, list[dict[str, Any]]] = {payload.source_name: metric_records}

        if group_col_ex:
            if group_col_ex in metric_nodes:
                # Same source — no join needed
                pass
            elif payload.join_path:
                try:
                    _reg_conns_ex = _sreg_ex.get_connections(org_id)
                    (
                        join_path_edges_ex,
                        join_group_source_ex,
                        join_confidence_ex,
                        join_edge_meta_ex,
                    ) = _resolve_join_path(
                        payload.source_name,
                        payload.join_path,
                        _reg_conns_ex,
                    )
                except ValueError as _e:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": {
                                "code": "join_path_invalid",
                                "message": str(_e),
                            }
                        },
                    ) from _e

                for source_name in [edge.right_source for edge in join_path_edges_ex]:
                    if source_name in join_records_ex:
                        continue
                    try:
                        records_ex, _nodes_ex = _load_exact(source_name)
                    except ValueError as _e:
                        raise HTTPException(
                            status_code=404,
                            detail={
                                "error": {
                                    "code": "join_source_error",
                                    "message": str(_e),
                                }
                            },
                        ) from _e
                    join_records_ex[source_name] = records_ex

                if join_group_source_ex is None:
                    join_group_source_ex = payload.source_name
                terminal_nodes_ex = (
                    metric_nodes
                    if join_group_source_ex == payload.source_name
                    else _graph_nodes_from_cached_meta(
                        org_id=org_id,
                        dataset_id=registered_ex[join_group_source_ex]["id"],
                        schema_revision=str(
                            registered_ex[join_group_source_ex].get("schema_revision", "") or ""
                        ),
                        schema_meta=_sreg_ex.get_source_meta(
                            org_id,
                            registered_ex[join_group_source_ex]["id"],
                        )
                        or {},
                    )
                )
                if group_col_ex not in terminal_nodes_ex:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": {
                                "code": "group_column_not_found",
                                "message": (
                                    f"Column '{group_col_ex}' not found in terminal "
                                    f"join source '{join_group_source_ex}'."
                                ),
                            }
                        },
                    )

                for idx, (edge_ex, (edge_conf_ex, edge_card_ex)) in enumerate(
                    zip(join_path_edges_ex, join_edge_meta_ex, strict=False), start=1
                ):
                    plan.append(
                        f"Join hop {idx}: {edge_ex.left_source}.{edge_ex.left_key} = "
                        f"{edge_ex.right_source}.{edge_ex.right_key} "
                        f"(conf={edge_conf_ex:.2f}  card={edge_card_ex or '?'})"
                    )
                cross_ex = bool(join_path_edges_ex)
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "group_column_not_found",
                            "message": (
                                f"Column '{group_col_ex}' not found in '{payload.source_name}'. "
                                "Cross-source grouping now requires join_path."
                            ),
                        }
                    },
                )

        if payload.join_path and not group_col_ex:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "join_path_requires_group_column",
                        "message": "join_path requires group_column for exact-spec execution.",
                    }
                },
            )

        # Time filter
        date_col_ex: str | None = find_time_column(
            payload.source_name, {payload.source_name: metric_nodes}
        )
        tr_ex = (
            time_range(payload.filter.time_filter)
            if payload.filter and payload.filter.time_filter
            else None
        )

        # Build a stable plan key — content-keyed sources are permanent so hash is safe
        _plan_key = exact_plan_hash

        _cached_result = _RESULT_CACHE.get(_plan_key)
        if _cached_result and (time.monotonic() - _cached_result.get("_ts", 0)) < _RESULT_CACHE_TTL:
            plan.append(f"Result cache HIT [{_plan_key[:8]}]")
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=_cached_result["result"],
                result_type=_cached_result["result_type"],
                confidence=_cached_result["confidence"],
                plan=plan,
                resolved_column=payload.metric_column,
                resolved_role=_cached_result.get("resolved_role", ""),
                resolved_source=_cached_result.get("resolved_source", payload.source_name),
                row_count=_cached_result["row_count"],
                candidates=[],
                source_scores={},
                ambiguous=False,
                exact_spec=True,
                explanation=_cached_result.get("explanation", []),
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="exact_spec",
                schema_revision=schema_revision_exact,
                validated=True,
                confidence_source="exact_spec_validation",
                plan_basis=exact_plan_basis,
                source_set=(
                    [payload.source_name] + [edge.right_source for edge in join_path_edges_ex]
                ),
                join_path=[edge.model_dump(mode="python") for edge in join_path_edges_ex],
                planner_mode="exact_spec",
                plan_hash_override=exact_plan_hash,
                log_response=False,
            )

        # Execute
        if cross_ex and join_group_source_ex and group_col_ex:
            result_ex, row_count_ex, exec_plan_ex = execute_join_path(
                records_by_source=join_records_ex,
                base_source=payload.source_name,
                metric_col=payload.metric_column,
                group_source=join_group_source_ex,
                group_col=group_col_ex,
                ordered_edges=join_path_edges_ex,
                agg=payload.aggregation,
                limit=payload.limit,
                order=payload.order,
                reject_on_ambiguity=payload.join_path.reject_on_ambiguity
                if payload.join_path
                else True,
            )
            resolved_src_ex = " ⋈ ".join(
                [payload.source_name] + [edge.right_source for edge in join_path_edges_ex]
            )
        else:
            result_ex, row_count_ex, exec_plan_ex = execute(
                records=metric_records,
                metric_col=payload.metric_column,
                agg=payload.aggregation,
                group_col=group_col_ex,
                date_col=date_col_ex,
                tr=tr_ex,
                limit=payload.limit,
                order=payload.order,
            )
            resolved_src_ex = payload.source_name

        plan.extend(exec_plan_ex)
        result_type_ex = (
            "table"
            if isinstance(result_ex, list)
            else ("scalar" if result_ex is not None else "none")
        )

        # Compute confidence
        computed_confidence, col_conf, agg_conf = _compute_exact_confidence(
            metric_node, payload.aggregation, join_confidence_ex
        )

        # Constraint: min_column_confidence check
        if col_conf < payload.constraints.min_column_confidence:
            from fastapi import HTTPException as _HTTPExc

            raise _HTTPExc(
                status_code=400,
                detail={
                    "error": {
                        "code": "constraint_violated",
                        "constraint": "min_column_confidence",
                        "reason": (
                            f"Column '{payload.metric_column}' has "
                            f"column_confidence={col_conf:.2f}, which is below "
                            "min_column_confidence="
                            f"{payload.constraints.min_column_confidence:.2f}."
                        ),
                    }
                },
            )

        # Build explanation
        exact_explanation: list[str] = [
            f"Source: {payload.source_name}",
            f"Column: {payload.metric_column}  role={metric_node.role}"
            + (f"  formula={metric_node.formula}" if metric_node.formula else ""),
            f"Aggregation: {payload.aggregation}",
        ]
        if group_col_ex:
            if cross_ex:
                hop_text = " -> ".join(
                    f"{edge.left_source}.{edge.left_key}={edge.right_source}.{edge.right_key}"
                    for edge in join_path_edges_ex
                )
                exact_explanation.append(
                    f"Group by: {group_col_ex} from {join_group_source_ex} "
                    f"via join_path ({hop_text})"
                )
            else:
                exact_explanation.append(f"Group by: {group_col_ex} (same source)")
        if tr_ex:
            exact_explanation.append(
                f"Time filter: {payload.filter.time_filter if payload.filter else '?'} → {tr_ex}"
            )
        exact_explanation.append(
            f"Result: {result_type_ex}"
            + (f"  {row_count_ex} groups" if result_type_ex == "table" else f"  = {result_ex}")
        )
        exact_explanation.append(
            f"Confidence: {computed_confidence:.3f} = col({col_conf:.2f}) × agg({agg_conf:.2f})"
            + (f" × join({join_confidence_ex:.2f})" if cross_ex else "")
        )

        # Store in result cache
        if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
            oldest = min(_RESULT_CACHE.items(), key=lambda x: x[1].get("_ts", 0))
            del _RESULT_CACHE[oldest[0]]

        _RESULT_CACHE[_plan_key] = {
            "result": result_ex,
            "result_type": result_type_ex,
            "row_count": row_count_ex,
            "confidence": computed_confidence,
            "resolved_role": metric_node.role,
            "resolved_source": resolved_src_ex,
            "explanation": exact_explanation,
            "_ts": time.monotonic(),
        }
        plan.append(f"Result cache STORED [{_plan_key[:8]}]")

        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=result_ex,
            result_type=result_type_ex,
            confidence=computed_confidence,
            plan=plan,
            resolved_column=payload.metric_column,
            resolved_role=metric_node.role,
            resolved_source=resolved_src_ex,
            row_count=row_count_ex,
            candidates=[],
            source_scores={},
            ambiguous=False,
            exact_spec=True,
            explanation=exact_explanation,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="exact_spec",
            schema_revision=schema_revision_exact,
            validated=True,
            confidence_source="exact_spec_validation",
            plan_basis=exact_plan_basis,
            source_set=([payload.source_name] + [edge.right_source for edge in join_path_edges_ex]),
            join_path=[edge.model_dump(mode="python") for edge in join_path_edges_ex],
            planner_mode="exact_spec",
            plan_hash_override=exact_plan_hash,
        )

    # ══════════════════════════════════════════════════════════════════════
    # HINT PATH (fallback) — LLM did not supply exact column names.
    # Source resolver + column resolver run. Result has ambiguous flag.
    # Migrate to exact-spec once schema is known.
    # ══════════════════════════════════════════════════════════════════════

    # Validate role
    target_role = payload.metric.role
    if target_role not in ALL_ROLES:
        target_role = DERIVED_MEASURE
        plan.append(f"Unknown role '{payload.metric.role}' — defaulting to derived_measure")

    plan.append(
        f"Request: agg={payload.aggregation}  role={target_role}  "
        f"group_by={payload.group_by}  limit={payload.limit}  "
        f"time={payload.filter.time_filter if payload.filter else None}"
    )

    if not payload.sources:
        registered = _visible_registry_entries()
        if not registered:
            empty_schema_revision = _sreg_visible.schema_revision(org_id)
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=None,
                result_type="none",
                confidence=0.0,
                plan=plan
                + [
                    "No registered sources found for this org. Use POST /v1/sources/register first."
                ],
                resolved_column="",
                resolved_role="",
                resolved_source="",
                row_count=0,
                candidates=[],
                source_scores={},
                ambiguous=True,
                exact_spec=False,
                explanation=[],
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=empty_schema_revision,
                validated=False,
                confidence_source="planner_query_confidence",
                clarification_required=False,
                rejection_reason="schema_incomplete",
                plan_basis={"reason": "no_registered_sources"},
            )

        planner, planner_cache_hit, schema_revision = await _get_registry_planner(
            org_id,
            llm_policy="never",
            auth=auth,
            visible_entries=registered,
        )
        metric_hint = (payload.metric.hint or "").strip() or target_role.replace("_", " ")
        dim_hint = (
            " ".join(part.strip() for part in payload.group_by if part and part.strip()) or None
        )
        normalized_filter_spec = _normalize_filter_spec(payload.filter)
        time_filter = payload.filter.time_filter if payload.filter else None

        hint_result_key = hashlib.sha256(
            json.dumps(
                {
                    "org": org_id,
                    "rev": schema_revision,
                    "metric_hint": metric_hint,
                    "dim_hint": dim_hint or "",
                    "preferred_source": payload.preferred_source or "",
                    "agg": payload.aggregation,
                    "limit": payload.limit,
                    "order": payload.order,
                    "filter": normalized_filter_spec or {},
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:24]

        cached_hint = _RESULT_CACHE.get(hint_result_key)
        if cached_hint and (time.monotonic() - cached_hint.get("_ts", 0)) < _RESULT_CACHE_TTL:
            warm_plan = list(plan)
            warm_plan.append(
                f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]"
            )
            warm_plan.append(f"Hint result cache HIT [{hint_result_key[:8]}]")
            warm_plan.extend(cached_hint.get("plan_body", []))
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=cached_hint["result"],
                result_type=cached_hint["result_type"],
                confidence=cached_hint["confidence"],
                plan=warm_plan,
                resolved_column=cached_hint["resolved_column"],
                resolved_role=cached_hint["resolved_role"],
                resolved_source=cached_hint["resolved_source"],
                row_count=cached_hint["row_count"],
                candidates=[CandidateColumn(**cand) for cand in cached_hint.get("candidates", [])],
                source_scores=cached_hint.get("source_scores", {}),
                ambiguous=cached_hint.get("ambiguous", False),
                exact_spec=False,
                explanation=cached_hint.get("explanation", []),
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=schema_revision,
                validated=True,
                confidence_source="planner_query_confidence",
                plan_basis={"cache_key": hint_result_key},
                deterministic_scope="planned_execution",
                source_set=cached_hint.get("source_set", []),
                join_path=cached_hint.get("join_path", []),
                planner_mode="registry_planner",
                log_response=False,
            )

        plan.append(f"Registry: {len(registered)} registered sources for org {org_id}")
        plan.append(
            f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]"
        )

        qplan = await _run_cached_planner_method(
            planner,
            "plan",
            metric_hint=metric_hint,
            dim_hint=dim_hint,
            agg=payload.aggregation,
            preferred_source=payload.preferred_source,
        )
        plan.extend(qplan.steps)

        confidence = _planner_query_confidence(qplan)
        ambiguous = bool(qplan.error) or confidence < _DECISION_AUTO_ACCEPT_CONFIDENCE
        metric_candidate_payloads = _planner_metric_candidate_payloads(
            plan=qplan,
            graph=planner.graph,
            metric_hint=metric_hint,
            target_role=qplan.metric_role or target_role,
            preferred_source=payload.preferred_source,
        )

        plan_error_text = (
            "; ".join(
                note
                for note in [qplan.error or "", *_planner_load_bearing_validation_notes(qplan)]
                if note
            )
            or None
        )
        validated, clarification_required, rejection_reason = _decision_contract_flags(
            confidence,
            metric_candidate_payloads,
            error_text=plan_error_text,
        )
        source_scores_hint = (
            {qplan.metric_src: round(qplan.metric_conf, 3)} if qplan.metric_src else {}
        )
        if not validated:
            if clarification_required:
                plan.append(
                    "Clarification required: planner confidence or candidate separation "
                    "did not meet deterministic execution threshold."
                )
            else:
                plan.append(f"Rejected: {rejection_reason or 'schema_unresolved'} before execution")
            explanation = [
                f"Metric hint: {metric_hint}",
                f"Planner confidence: {confidence:.3f}",
            ]
            if plan_error_text:
                explanation.append(f"Planner note: {plan_error_text}")
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=None,
                result_type="none",
                confidence=confidence,
                plan=plan,
                resolved_column=qplan.metric_col or "",
                resolved_role=qplan.metric_role or "",
                resolved_source=qplan.metric_src or "",
                row_count=0,
                candidates=metric_candidate_payloads[:5],
                source_scores=source_scores_hint,
                ambiguous=True,
                exact_spec=False,
                explanation=explanation,
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=schema_revision,
                validated=False,
                confidence_source="planner_query_confidence",
                clarification_required=clarification_required,
                rejection_reason=rejection_reason,
                plan_basis={
                    "cache_key": hint_result_key,
                    "metric_hint": metric_hint,
                    "dim_hint": dim_hint or "",
                    "aggregation": payload.aggregation,
                },
                source_set=_dedupe_source_values(
                    [
                        qplan.metric_src or "",
                        qplan.group_src or "",
                        *[hop.right_source for hop in qplan.join_hops],
                    ]
                ),
                join_path=[
                    {
                        "left_source": hop.left_source,
                        "left_key": hop.left_key,
                        "right_source": hop.right_source,
                        "right_key": hop.right_key,
                        "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                        "cardinality": getattr(hop, "cardinality", None),
                    }
                    for hop in qplan.join_hops
                ],
                planner_mode="registry_planner",
            )

        try:
            result, row_count, exec_plan = await _run_cached_planner_method(
                planner,
                "execute_plan",
                qplan,
                limit=payload.limit,
                order=payload.order,
                time_filter=time_filter,
                filter_spec=payload.filter,
            )
        except ValueError as _e:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_filter_condition",
                        "message": str(_e),
                    }
                },
            ) from _e
        plan.extend(exec_plan)

        if result is None:
            result_type = "none"
        elif isinstance(result, list):
            result_type = "table"
        else:
            result_type = "scalar"

        resolved_source = (
            " ⋈ ".join([qplan.metric_src] + [hop.right_source for hop in qplan.join_hops])
            if qplan.join_hops
            else qplan.metric_src
        )
        metric_node = planner.graph.get(qplan.metric_src, {}).get(qplan.metric_col)
        candidates: list[CandidateColumn] = []
        for cand in metric_candidate_payloads[:5]:
            candidates.append(CandidateColumn(**cand))
        if not candidates and metric_node is not None and qplan.metric_src and qplan.metric_col:
            candidates.append(
                CandidateColumn(
                    source=qplan.metric_src,
                    column=qplan.metric_col,
                    role=metric_node.role,
                    magnitude=metric_node.magnitude_class,
                    formula=metric_node.formula,
                    confidence=qplan.metric_conf,
                )
            )

        explanation = [
            f"Metric hint: {metric_hint}",
            f"Resolved metric: {qplan.metric_src}.{qplan.metric_col}"
            if qplan.metric_src and qplan.metric_col
            else "Resolved metric: none",
            f"Aggregation: {payload.aggregation}",
        ]
        if qplan.group_col and qplan.group_src:
            explanation.append(f"Group by: {qplan.group_src}.{qplan.group_col}")
        if qplan.join_hops:
            hop_text = " -> ".join(
                f"{hop.left_source}.{hop.left_key}={hop.right_source}.{hop.right_key}"
                for hop in qplan.join_hops
            )
            explanation.append(f"Join path: {hop_text}")
        if time_filter:
            explanation.append(f"Time filter: {time_filter}")
        explanation.append(
            f"Confidence: {confidence:.3f}" + (f"  error={qplan.error}" if qplan.error else "")
        )

        plan_body = list(qplan.steps) + list(exec_plan)
        if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
            oldest = min(_RESULT_CACHE.items(), key=lambda item: item[1].get("_ts", 0))
            del _RESULT_CACHE[oldest[0]]
        _RESULT_CACHE[hint_result_key] = {
            "result": result,
            "result_type": result_type,
            "confidence": confidence,
            "resolved_column": qplan.metric_col or "",
            "resolved_role": qplan.metric_role or "",
            "resolved_source": resolved_source or "",
            "row_count": row_count,
            "candidates": [cand.model_dump() for cand in candidates],
            "source_scores": source_scores_hint,
            "ambiguous": ambiguous,
            "explanation": explanation,
            "source_set": _dedupe_source_values(
                [
                    qplan.metric_src or "",
                    qplan.group_src or "",
                    *[hop.right_source for hop in qplan.join_hops],
                ]
            ),
            "join_path": [
                {
                    "left_source": hop.left_source,
                    "left_key": hop.left_key,
                    "right_source": hop.right_source,
                    "right_key": hop.right_key,
                    "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                    "cardinality": getattr(hop, "cardinality", None),
                }
                for hop in qplan.join_hops
            ],
            "plan_body": plan_body,
            "_ts": time.monotonic(),
        }
        plan.append(f"Hint result cache STORED [{hint_result_key[:8]}]")

        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=result,
            result_type=result_type,
            confidence=confidence,
            plan=plan,
            resolved_column=qplan.metric_col or "",
            resolved_role=qplan.metric_role or "",
            resolved_source=resolved_source or "",
            row_count=row_count,
            candidates=candidates,
            source_scores=source_scores_hint,
            ambiguous=ambiguous,
            exact_spec=False,
            explanation=explanation,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision,
            validated=True,
            confidence_source="planner_query_confidence",
            plan_basis={
                "cache_key": hint_result_key,
                "resolved_source": resolved_source or "",
                "resolved_column": qplan.metric_col or "",
                "aggregation": payload.aggregation,
            },
            deterministic_scope="planned_execution",
            source_set=_dedupe_source_values(
                [
                    qplan.metric_src or "",
                    qplan.group_src or "",
                    *[hop.right_source for hop in qplan.join_hops],
                ]
            ),
            join_path=[
                {
                    "left_source": hop.left_source,
                    "left_key": hop.left_key,
                    "right_source": hop.right_source,
                    "right_key": hop.right_key,
                    "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                    "cardinality": getattr(hop, "cardinality", None),
                }
                for hop in qplan.join_hops
            ],
            planner_mode="registry_planner",
        )

    # ── Load + profile all sources (cache-aware) ─────────────────────────────
    parsed_tables: dict[str, Any] = {}
    profiles: dict[str, dict[str, dict[str, Any]]] = {}
    cache_hits: set[str] = set()
    cache_entries: dict[str, _CachedSource] = {}  # src.name → cached entry
    # Registry connections (populated when loading from registry; used for cross-source joins)
    _reg_connections: list[dict[str, Any]] = []

    for src in payload.sources:
        cache_key, content_keyed = _source_cache_key(src)
        async with _CACHE_LOCK:
            entry = _SOURCE_CACHE.get(cache_key)
            if entry and entry.is_fresh():
                entry.touch()
                cache_entries[src.name] = entry
                cache_hits.add(src.name)
                plan.append(f"Cache HIT [{src.name}] — skipping load+profile")
                continue
        # source_id miss — load from registry (parquet on disk)
        registered_id = src.dataset_id or src.source_id
        if registered_id:
            from apps.api_server.services import source_registry as _sreg

            parquet_bytes = _sreg.get_source_parquet(org_id, registered_id)
            if parquet_bytes:
                schema_meta_dict = _sreg.get_source_meta(org_id, registered_id) or {}
                graph_nodes = _graph_nodes_from_meta(schema_meta_dict)
                reg_entry = _CachedSource(
                    parquet_bytes=parquet_bytes,
                    parquet_schema_meta=json.dumps(schema_meta_dict).encode(),
                    profile={},
                    mojo_profile={},
                    relations=schema_meta_dict.get("formulas", []),
                    graph_nodes=graph_nodes,
                    schema_meta=schema_meta_dict,
                    mojo_profiling_status=schema_meta_dict.get("mojo_profiling_status") or {},
                    content_keyed=True,
                )
                async with _CACHE_LOCK:
                    _source_cache_put(reg_entry, registered_id)
                cache_entries[src.name] = reg_entry
                plan.append(f"Registry HIT (dataset/source id) [{src.name}]")
                continue
            plan.append(
                f"WARNING: source_id={registered_id} not found in registry for [{src.name}]"
            )
        # Cache miss — adaptively load on the fastest safe path for this source
        loaded = await _load_profiled_source(src, org_id=org_id)
        if loaded.row_count <= 0 or loaded.arrow_table is None:
            _raise_empty_source(src.name)
        profiles[src.name] = loaded.profile
        parsed_tables[src.name] = loaded.arrow_table
        plan.append(f"Ingest [{src.name}] mode={loaded.ingest_mode}")

    # ── Mojo: profiling + relation detection (concurrent, only for misses) ──
    miss_names = list(parsed_tables.keys())
    if miss_names:

        def _adaptive_profile_payload(name: str) -> dict[str, dict[str, Any]]:
            value_limit, string_limit = _mojo_column_profile_sample_limits(len(profiles[name]))
            return _build_mojo_column_profile_columns(
                profiles[name],
                value_limit=value_limit,
                string_limit=string_limit,
                include_fill_rate=True,
            )

        profiler_coros = [
            _call_mojo_column_profile(_adaptive_profile_payload(name)) for name in miss_names
        ]
        relation_coros = [_detect_relations(name, profiles) for name in miss_names]
        try:
            profiler_results, relation_results = await asyncio.gather(
                asyncio.gather(*profiler_coros),
                asyncio.gather(*relation_coros),
            )
        except MojoInstrumentationError as exc:
            raise _http_error(
                503,
                code="mojo_instrumentation_unavailable",
                message=(
                    "Mojo column profiling is unavailable while strict runtime "
                    "fallbacks are disabled."
                ),
                request_id=request_id,
                details=[("engine_type", exc.engine_type)],
            ) from exc
        for i, name in enumerate(miss_names):
            profiling_status = _mojo_profiling_status_from_result(profiler_results[i])
            mojo_prof = (profiler_results[i] or {}).get("profiles", {})
            rels = relation_results[i]
            if rels:
                plan.append(f"Formulas in {name}: {len(rels)} detected (top: {rels[0]['formula']})")
            if profiling_status.get("status") != "enabled":
                plan.append(
                    "Mojo profiling disabled "
                    f"[{name}] reason={profiling_status.get('reason') or 'unknown'}"
                )
            # Build graph nodes for this source
            src_graph = build_schema_graph(
                {name: profiles[name]},
                {name: mojo_prof},
                {name: rels},
            )
            import pyarrow.parquet as pq

            schema_meta = _build_schema_metadata(
                name,
                src_graph[name],
                rels,
                profiles[name],
                profiling_status,
                _arrow_physical_types(parsed_tables[name].schema),
            )
            arrow_table = parsed_tables[name]
            # Embed schema metadata in Arrow custom_metadata
            existing_meta = arrow_table.schema.metadata or {}
            new_meta = {
                **existing_meta,
                b"algenta_schema": json.dumps(schema_meta).encode(),
            }
            arrow_table = arrow_table.replace_schema_metadata(new_meta)
            buf = io.BytesIO()
            pq.write_table(arrow_table, buf)
            parquet_bytes = buf.getvalue()
            # Also store just the schema metadata bytes (cheap to extract)
            schema_meta_bytes = json.dumps(schema_meta).encode()

            # Find original DataSource to get cache key + content_keyed flag
            for src in payload.sources:
                if src.name == name:
                    ck, ck_content = _source_cache_key(src)
                    entry = _CachedSource(
                        parquet_bytes=parquet_bytes,
                        parquet_schema_meta=schema_meta_bytes,
                        profile=profiles[name],
                        mojo_profile=mojo_prof,
                        relations=rels,
                        graph_nodes=src_graph[name],
                        schema_meta=schema_meta,
                        mojo_profiling_status=profiling_status,
                        content_keyed=ck_content,
                    )
                    async with _CACHE_LOCK:
                        _source_cache_put(entry, ck)
                    cache_entries[name] = entry
                    break

    # ── Assemble graph from cache entries ─────────────────────────────────────
    graph: SchemaGraph = {name: e.graph_nodes for name, e in cache_entries.items()}
    schema_revision_inline = _inline_schema_revision(graph)

    for src_name, nodes in graph.items():
        hit_label = "HIT" if src_name in cache_hits else "MISS"
        role_counts: dict[str, int] = {}
        for node in nodes.values():
            role_counts[node.role] = role_counts.get(node.role, 0) + 1
        plan.append(
            f"Graph [{src_name}] ({hit_label}): "
            + ", ".join(f"{r}:{n}" for r, n in sorted(role_counts.items()))
        )

    # ── SOURCE RESOLVER — runs before column resolution ───────────────────────
    #
    # Determine WHICH source this query is about before picking columns.
    # This prevents Bookings from winning every query just because it happens
    # to have the globally highest-confidence derived_measure column.
    #
    # Flow:
    #   1. Score all sources (metric role + hint overlap + group dimension overlap)
    #   2. Select the anchored source
    #   3. Resolve metric column WITHIN the anchored source
    #   4. If anchored source has no suitable metric → find globally, cross-source join
    #   5. Resolve group column (prefer anchored source, fall back to others → cross-source)
    #
    hint_tokens = set(re.findall(r"[a-z0-9]+", (payload.metric.hint or "").lower()))

    # Source resolver — Mojo-first, Python fallback
    mojo_src = await _call_mojo_source_score(
        target_role=target_role,
        metric_hint_tokens=hint_tokens,
        group_tokens=payload.group_by,
        preferred_source=payload.preferred_source,
        graph=graph,
    )
    if mojo_src:
        anchored_src, src_score, all_src_scores = mojo_src
        plan.append("Source resolver: mojo")
    else:
        anchored_src, src_score, all_src_scores = resolve_source(
            target_role=target_role,
            metric_hint_tokens=hint_tokens,
            group_tokens=payload.group_by,
            preferred_source=payload.preferred_source,
            graph=graph,
        )

    # Hard lock: when the LLM explicitly names a source it knows is right,
    # don't let the resolver override it. The score is kept for transparency.
    if payload.preferred_source and payload.preferred_source in graph:
        anchored_src = payload.preferred_source
        src_score = max(src_score, all_src_scores.get(payload.preferred_source, 0.50))
        plan.append(f"Source resolver: locked to preferred_source={anchored_src}")

    ambiguous = src_score < _DECISION_AUTO_ACCEPT_CONFIDENCE
    plan.append(
        f"Source resolver: {anchored_src} (score={src_score:.2f})"
        + ("  [AMBIGUOUS — low confidence]" if ambiguous else "")
        + f"  all={dict(sorted(all_src_scores.items(), key=lambda x: -x[1]))}"
    )

    # Resolve metric WITHIN the anchored source first
    src_name, metric_col, metric_conf, all_candidates = resolve_metric_column(
        target_role, hint_tokens, graph, preferred_source=anchored_src
    )

    # If anchored source has no suitable metric → try METRIC fallback within same source,
    # then (if preferred_source is NOT set) try global.
    # When preferred_source IS set, stay within that source even with METRIC fallback —
    # the user named this source intentionally.
    if not metric_col and anchored_src:
        plan.append(f"No {target_role} in {anchored_src} — trying METRIC fallback within source")
        _, mc2, mconf2, cands2 = resolve_metric_column(
            METRIC, hint_tokens, graph, preferred_source=anchored_src
        )
        if mc2:
            src_name, metric_col, metric_conf, all_candidates = (
                anchored_src,
                mc2,
                round(mconf2 * 0.5, 3),
                cands2,
            )

    # Last resort global fallback — only when no preferred_source lock
    if not metric_col and not payload.preferred_source:
        plan.append(f"No metric in {anchored_src} — global fallback")
        src_name, metric_col, metric_conf, all_candidates = resolve_metric_column(
            target_role, hint_tokens, graph
        )

    if not metric_col:
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=None,
            result_type="none",
            confidence=0.0,
            plan=plan + [f"No column with role={target_role} found in any source"],
            resolved_column="",
            resolved_role="",
            resolved_source="",
            row_count=0,
            candidates=[],
            source_scores=all_src_scores,
            ambiguous=True,
            exact_spec=False,
            explanation=[],
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision_inline,
            validated=False,
            confidence_source="min(source_resolver, metric_resolver, group_resolver)",
            clarification_required=False,
            rejection_reason="schema_incomplete",
            plan_basis={"reason": "metric_not_found", "aggregation": payload.aggregation},
            source_set=_dedupe_source_values([anchored_src]),
            planner_mode="inline_graph",
        )

    metric_node = graph[src_name][metric_col]
    if len(all_candidates) >= 2:
        metric_gap = all_candidates[0]["confidence"] - all_candidates[1]["confidence"]
        if metric_gap < 0.08:
            plan.append(
                "Metric ambiguity: "
                f"top={all_candidates[0]['column']} "
                f"second={all_candidates[1]['column']} gap={metric_gap:.3f}"
            )
    plan.append(
        f"Metric: `{metric_col}` in {src_name}  "
        f"role={metric_node.role}  magnitude={metric_node.magnitude_class}  "
        f"conf={metric_conf:.2f}"
        + (f"  formula={metric_node.formula}" if metric_node.formula else "")
    )

    # ── Group column — prefer anchored source, fall back to any source ────────
    group_col: str | None = None
    group_src: str = src_name
    gc_conf: float = 0.0

    if payload.group_by:
        group_src, group_col, gc_conf = resolve_group_column_graph(
            payload.group_by,
            src_name,
            graph,  # prefer metric's source first
        )
        if group_col:
            cross = group_src != src_name
            plan.append(
                f"Group-by: `{group_col}` in {group_src} (score={gc_conf:.2f})"
                + (" [cross-source join required]" if cross else "")
            )
        else:
            plan.append(f"Group-by {payload.group_by}: no matching column found")
            group_src = src_name

    group_confidence = gc_conf if payload.group_by else 1.0
    if payload.group_by and not group_col:
        group_confidence = 0.0
    decision_confidence = round(min(src_score, metric_conf, group_confidence), 3)
    contract_error_text = (
        "dimension metadata missing for requested group_by"
        if payload.group_by and not group_col
        else None
    )
    validated, clarification_required, rejection_reason = _decision_contract_flags(
        decision_confidence,
        all_candidates,
        error_text=contract_error_text,
    )
    if not validated:
        if clarification_required:
            plan.append(
                "Clarification required: source, metric, or group resolution did not meet "
                "deterministic execution threshold."
            )
        else:
            plan.append(f"Rejected: {rejection_reason or 'schema_unresolved'} before execution")
        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=None,
            result_type="none",
            confidence=decision_confidence,
            plan=plan,
            resolved_column=metric_col,
            resolved_role=metric_node.role,
            resolved_source=src_name,
            row_count=0,
            candidates=all_candidates[:5],
            source_scores=all_src_scores,
            ambiguous=True,
            exact_spec=False,
            explanation=[],
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision_inline,
            validated=False,
            confidence_source="min(source_resolver, metric_resolver, group_resolver)",
            clarification_required=clarification_required,
            rejection_reason=rejection_reason,
            plan_basis={
                "source": src_name,
                "metric_column": metric_col,
                "aggregation": payload.aggregation,
                "group_by": payload.group_by,
            },
            source_set=_dedupe_source_values([src_name, group_src]),
            planner_mode="inline_graph",
        )

    # ── Time filter ───────────────────────────────────────────────────────────
    date_col: str | None = None
    tr: tuple[date, date] | None = None
    if payload.filter and payload.filter.time_filter:
        date_col = find_time_column(src_name, graph)
        tr = time_range(payload.filter.time_filter)
        if date_col:
            plan.append(f"Time column: `{date_col}`  range: {payload.filter.time_filter}")
        else:
            plan.append("No TIME-role column found — time filter skipped")

    # ── Load records for execution (from cache or parsed) ────────────────────
    import pandas as pd

    def _load_records(name: str) -> list[dict[str, Any]]:
        if name in parsed_tables:
            records: list[dict[str, Any]] = parsed_tables[name].to_pylist()
            return records
        buf = io.BytesIO(cache_entries[name].parquet_bytes)
        initialize_pyarrow_parquet_runtime()
        records = pd.read_parquet(buf).to_dict(orient="records")
        return records

    exec_records = _load_records(src_name)
    try:
        resolved_filter_conditions = _resolve_filter_conditions(
            source_name=src_name,
            filter_spec=payload.filter,
            graph_nodes=graph.get(src_name, {}),
            records=exec_records,
        )
    except ValueError as _e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_filter_condition",
                    "message": str(_e),
                }
            },
        ) from _e
    exec_records, filter_plan = _apply_filter_conditions(
        exec_records,
        resolved_filter_conditions,
    )
    plan.extend(filter_plan)

    # ── Execute (same-source or cross-source join) ────────────────────────────
    cross_source = bool(group_col and group_src != src_name)

    if cross_source:
        # Find the join key between metric source and group source (confidence-filtered)
        join_triplet = _find_best_join_key(src_name, group_src, _reg_connections)
        if join_triplet:
            join_metric_col, join_group_col, join_conf, join_card = join_triplet
            if join_conf < _DECISION_AUTO_ACCEPT_CONFIDENCE:
                plan.append(
                    f"Rejected: join confidence {join_conf:.2f} is below "
                    f"{_DECISION_AUTO_ACCEPT_CONFIDENCE:.2f}"
                )
                return _build_query_response(
                    query_id=query_id,
                    request_id=request_id,
                    result=None,
                    result_type="none",
                    confidence=round(min(decision_confidence, join_conf), 3),
                    plan=plan,
                    resolved_column=metric_col,
                    resolved_role=metric_node.role,
                    resolved_source=f"{src_name} ⋈ {group_src}",
                    row_count=0,
                    candidates=all_candidates[:5],
                    source_scores=all_src_scores,
                    ambiguous=True,
                    exact_spec=False,
                    explanation=[],
                    latency_ms=round((time.monotonic() - t0) * 1000, 1),
                    decision_path="planner_hint",
                    schema_revision=schema_revision_inline,
                    validated=False,
                    confidence_source=(
                        "min(source_resolver, metric_resolver, group_resolver, join_confidence)"
                    ),
                    clarification_required=False,
                    rejection_reason="join_ambiguity",
                    plan_basis={
                        "source": src_name,
                        "group_source": group_src,
                        "metric_column": metric_col,
                        "group_column": group_col,
                    },
                    source_set=_dedupe_source_values([src_name, group_src]),
                    join_path=[
                        {
                            "left_source": src_name,
                            "left_key": join_metric_col,
                            "right_source": group_src,
                            "right_key": join_group_col,
                            "confidence": round(join_conf, 3),
                            "cardinality": join_card,
                        }
                    ],
                    planner_mode="inline_graph",
                )
            plan.append(
                f"Join key: {src_name}.{join_metric_col} = {group_src}.{join_group_col}"
                f"  (conf={join_conf:.2f}  card={join_card or '?'})"
            )
            group_records = _load_records(group_src)
            assert group_col is not None
            result, row_count, exec_plan = execute_cross_source(
                metric_records=exec_records,
                metric_col=metric_col,
                group_records=group_records,
                group_col=group_col,
                join_metric_col=join_metric_col,
                join_group_col=join_group_col,
                agg=payload.aggregation,
                limit=payload.limit,
                order=payload.order,
                join_cardinality=join_card,
            )
        else:
            plan.append(
                f"Rejected: no deterministic join key found between {src_name} and {group_src}"
            )
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=None,
                result_type="none",
                confidence=decision_confidence,
                plan=plan,
                resolved_column=metric_col,
                resolved_role=metric_node.role,
                resolved_source=f"{src_name} ⋈ {group_src}",
                row_count=0,
                candidates=all_candidates[:5],
                source_scores=all_src_scores,
                ambiguous=True,
                exact_spec=False,
                explanation=[],
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=schema_revision_inline,
                validated=False,
                confidence_source="min(source_resolver, metric_resolver, group_resolver)",
                clarification_required=False,
                rejection_reason="join_ambiguity",
                plan_basis={
                    "source": src_name,
                    "group_source": group_src,
                    "metric_column": metric_col,
                    "group_column": group_col,
                },
                source_set=_dedupe_source_values([src_name, group_src]),
                planner_mode="inline_graph",
            )
    else:
        join_conf = 1.0
        result, row_count, exec_plan = execute(
            records=exec_records,
            metric_col=metric_col,
            agg=payload.aggregation,
            group_col=group_col,
            date_col=date_col,
            tr=tr,
            limit=payload.limit,
            order=payload.order,
        )
    plan.extend(exec_plan)

    # ── Response ──────────────────────────────────────────────────────────────
    if result is None:
        result_type = "none"
    elif isinstance(result, list):
        result_type = "table"
    else:
        result_type = "scalar"

    # resolved_source: show both if cross-source join was used
    resolved_src_label = f"{src_name} ⋈ {group_src}" if cross_source and group_col else src_name
    final_confidence = round(min(decision_confidence, join_conf), 3)

    return _build_query_response(
        query_id=query_id,
        request_id=request_id,
        result=result,
        result_type=result_type,
        confidence=final_confidence,
        plan=plan,
        resolved_column=metric_col,
        resolved_role=metric_node.role,
        resolved_source=resolved_src_label,
        row_count=row_count,
        candidates=[CandidateColumn(**c) for c in all_candidates[:5]],
        source_scores=all_src_scores,
        ambiguous=ambiguous,
        exact_spec=False,
        explanation=[],
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
        decision_path="planner_hint",
        schema_revision=schema_revision_inline,
        validated=True,
        confidence_source="min(source_resolver, metric_resolver, group_resolver, join_confidence)",
        plan_basis={
            "source": src_name,
            "metric_column": metric_col,
            "group_column": group_col,
            "aggregation": payload.aggregation,
        },
        deterministic_scope="planned_execution",
        source_set=_dedupe_source_values([src_name, group_src]),
        join_path=(
            [
                {
                    "left_source": src_name,
                    "left_key": join_metric_col,
                    "right_source": group_src,
                    "right_key": join_group_col,
                    "confidence": round(join_conf, 3),
                    "cardinality": join_card,
                }
            ]
            if cross_source
            else []
        ),
        planner_mode="inline_graph",
    )

