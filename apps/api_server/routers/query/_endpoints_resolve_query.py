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


# Helpers extracted from query_sources, split across multiple submodules so
# each helper file stays close to or under 1000 lines.
from apps.api_server.routers.query._endpoints_helpers_early import (  # noqa: E402
    _apply_dataset_scope,
    _apply_legacy_planning_fallback,
    _apply_resolved_plan,
    _owner_resolved_plan_fast_path,
)
from apps.api_server.routers.query._endpoints_helpers_exact import (  # noqa: E402
    _run_exact_spec_path,
)
from apps.api_server.routers.query._endpoints_helpers_paths import (  # noqa: E402
    _ingest_and_profile_inline_sources,
    _run_registry_planner_hint_path,
)
from apps.api_server.routers.query._endpoints_helpers_inline import (  # noqa: E402
    _execute_inline_and_build_response,
    _resolve_inline_anchor_metric_group,
)


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
    from apps.api_server.services.data_visibility import filter_visible_datasets

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

    # ── Owner-only resolved_plan + result-cache fast path ─────────────────
    early, owner_schema_revision = _owner_resolved_plan_fast_path(
        payload=payload,
        auth=auth,
        org_id=org_id,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
        t0=t0,
    )
    if early is not None:
        return early
    if owner_schema_revision is not None:
        resolved_plan_schema_revision = owner_schema_revision

    # ── Dataset scope (mutates payload / seeds visible_registry_entries) ──
    scoped = _apply_dataset_scope(
        payload=payload,
        auth=auth,
        org_id=org_id,
        request_id=request_id,
        plan=plan,
    )
    if scoped is not None:
        visible_registry_entries = scoped

    # ── Resolved plan overlay ─────────────────────────────────────────────
    revision = _apply_resolved_plan(
        payload=payload,
        auth=auth,
        org_id=org_id,
        request_id=request_id,
        plan=plan,
        visible_registry_entries_loader=_visible_registry_entries,
    )
    if revision is not None:
        resolved_plan_schema_revision = revision

    # ── Legacy query-planning compatibility shim ──────────────────────────
    legacy_response = await _apply_legacy_planning_fallback(
        payload=payload,
        auth=auth,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
    )
    if legacy_response is not None:
        return legacy_response

    # ══════════════════════════════════════════════════════════════════════
    # EXACT-SPEC PATH — LLM supplied source_name + metric_column explicitly.
    # Mojo verifies and executes: no source resolver, no column resolver,
    # no semantic guessing. This is the correct production path.
    # ══════════════════════════════════════════════════════════════════════
    if payload.source_name and payload.metric_column:
        return _run_exact_spec_path(
            payload=payload,
            auth=auth,
            org_id=org_id,
            request_id=request_id,
            query_id=query_id,
            plan=plan,
            t0=t0,
            visible_registry_entries=visible_registry_entries,
            resolved_plan_schema_revision=resolved_plan_schema_revision,
            visible_registry_entries_loader=_visible_registry_entries,
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
        return await _run_registry_planner_hint_path(
            payload=payload,
            auth=auth,
            org_id=org_id,
            request_id=request_id,
            query_id=query_id,
            plan=plan,
            t0=t0,
            target_role=target_role,
            visible_registry_entries_loader=_visible_registry_entries,
        )

    # ── Load + profile all inline sources (cache-aware) ───────────────────
    (
        cache_entries,
        cache_hits,
        parsed_tables,
        profiles,
        _reg_connections,
    ) = await _ingest_and_profile_inline_sources(
        payload=payload,
        org_id=org_id,
        plan=plan,
        request_id=request_id,
    )

    # ── Inline-graph anchor / metric / group resolution ───────────────────
    (
        anchor_response,
        graph,
        schema_revision_inline,
        src_name,
        metric_col,
        metric_node,
        metric_conf,
        all_candidates,
        all_src_scores,
        ambiguous,
        group_col,
        group_src,
        decision_confidence,
    ) = await _resolve_inline_anchor_metric_group(
        payload=payload,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
        t0=t0,
        target_role=target_role,
        cache_entries=cache_entries,
        cache_hits=cache_hits,
    )
    if anchor_response is not None:
        return anchor_response

    # ── Final execution + response assembly ───────────────────────────────
    return _execute_inline_and_build_response(
        payload=payload,
        request_id=request_id,
        query_id=query_id,
        plan=plan,
        t0=t0,
        graph=graph,
        cache_entries=cache_entries,
        parsed_tables=parsed_tables,
        _reg_connections=_reg_connections,
        src_name=src_name,
        metric_col=metric_col,
        metric_node=metric_node,
        metric_conf=metric_conf,
        all_candidates=all_candidates,
        all_src_scores=all_src_scores,
        ambiguous=ambiguous,
        group_col=group_col,
        group_src=group_src,
        decision_confidence=decision_confidence,
        schema_revision_inline=schema_revision_inline,
    )
