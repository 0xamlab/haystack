"""Submodule _endpoints_schema.py of apps.api_server.routers.query.

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
from apps.api_server.routers.query._endpoints_resolve_query import *  # noqa: F401, F403
# Lazy facade-routed wrappers for monkey-patched / cross-layer names.
# Tests patch apps.api_server.routers.query.X = fake; each call here
# re-reads the attribute from the facade so the patch propagates.
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


class SchemaRequest(BaseModel):
    sources: list[DataSource] = Field(
        default=[],
        description=(
            "Data sources to profile. Pass an empty list (or omit) to return schemas for "
            "ALL sources registered for this org via POST /v1/sources/register."
        ),
    )

@router.post(
    "/v1/sources/schema",
    summary="Infer and return the structural schema of data sources",
    description=(
        "**Call this once when a user connects a data source.**\n\n"
        "Returns the full Algenta structural schema: column roles, detected formulas, "
        "cardinality, and `query_hints` the LLM should use when calling `POST /v1/query`.\n\n"
        "The schema is also embedded as Arrow metadata in the returned Parquet bytes "
        "(`parquet_b64`), "
        "which the LLM agent can store and reuse — no re-profiling on subsequent queries.\n\n"
        "**Flow:**\n"
        "1. User connects data source\n"
        "2. Call `POST /v1/sources/schema` — ~1-2s, runs once\n"
        "3. LLM reads `schema` JSON and `query_hints`\n"
        "4. User asks questions → LLM produces structured intent → "
        "`POST /v1/query` (~200ms, cached)"
    ),
    tags=["Semantic Query"],
)
async def infer_schema(
    payload: SchemaRequest,
    auth: AuthContext = Depends(get_current_org),
) -> dict[str, Any]:
    import base64

    import pyarrow.parquet as pq

    t0 = time.monotonic()
    result: list[dict[str, Any]] = []
    org_id = str(auth["org_id"])

    # ── Registry mode: no sources given → return all registered schemas ──────
    if not payload.sources:
        from apps.api_server.services import source_registry as _sreg
        from apps.api_server.services.data_visibility import filter_visible_datasets

        registered = filter_visible_datasets(_sreg.list_sources(org_id), auth)
        for reg_entry in registered:
            src_id = reg_entry["id"]
            src_name = reg_entry["name"]
            # Check memory cache first
            async with _CACHE_LOCK:
                cached = _SOURCE_CACHE.get(src_id)
                if cached and cached.is_fresh():
                    cached.touch()
                    sm = json.loads(cached.parquet_schema_meta)
                    result.append(
                        {
                            "source": src_name,
                            "source_id": src_id,
                            "cached": True,
                            "schema": sm,
                            "mojo_profiling_status": sm.get("mojo_profiling_status") or {},
                            "parquet_b64": base64.b64encode(cached.parquet_bytes).decode(),
                        }
                    )
                    continue
            # Fall back to disk
            schema_meta_dict = _sreg.get_source_meta(org_id, src_id) or {}
            parquet_bytes = _sreg.get_source_parquet(org_id, src_id)
            if parquet_bytes:
                result.append(
                    {
                        "source": src_name,
                        "source_id": src_id,
                        "cached": False,
                        "schema": schema_meta_dict,
                        "mojo_profiling_status": (
                            schema_meta_dict.get("mojo_profiling_status") or {}
                        ),
                        "parquet_b64": base64.b64encode(parquet_bytes).decode(),
                    }
                )
        return {
            "sources": result,
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
        }

    for src in payload.sources:
        # Check cache first
        cache_key, content_keyed = _source_cache_key(src, org_id=org_id)
        async with _CACHE_LOCK:
            entry = _SOURCE_CACHE.get(cache_key)
            if entry and entry.is_fresh():
                entry.touch()
                schema_meta = json.loads(entry.parquet_schema_meta)
                result.append(
                    {
                        "source": src.name,
                        "cached": True,
                        "schema": schema_meta,
                        "mojo_profiling_status": schema_meta.get("mojo_profiling_status") or {},
                        "parquet_b64": base64.b64encode(entry.parquet_bytes).decode(),
                    }
                )
                continue

        # Cache miss — adaptively load, profile, detect
        loaded = await _load_profiled_source(src, org_id=org_id)
        if loaded.row_count <= 0 or loaded.arrow_table is None:
            _raise_empty_source(src.name)
        profile = loaded.profile
        arrow_table = loaded.arrow_table
        assert arrow_table is not None

        try:
            value_limit, string_limit = _mojo_column_profile_sample_limits(len(profile))
            profiler_result, rels = await asyncio.gather(
                _call_mojo_column_profile(
                    _build_mojo_column_profile_columns(
                        profile,
                        value_limit=value_limit,
                        string_limit=string_limit,
                        include_fill_rate=True,
                    )
                ),
                _detect_relations(src.name, {src.name: profile}),
            )
        except MojoInstrumentationError as exc:
            raise _http_error(
                503,
                code="mojo_instrumentation_unavailable",
                message=(
                    "Mojo column profiling is unavailable while strict runtime "
                    "fallbacks are disabled."
                ),
                details=[("engine_type", exc.engine_type)],
            ) from exc

        profiling_status = _mojo_profiling_status_from_result(profiler_result)
        mojo_prof = (profiler_result or {}).get("profiles", {})
        src_graph = build_schema_graph({src.name: profile}, {src.name: mojo_prof}, {src.name: rels})
        schema_meta = _build_schema_metadata(
            src.name,
            src_graph[src.name],
            rels,
            profile,
            profiling_status,
            _arrow_physical_types(arrow_table.schema),
        )

        # Serialize Parquet with embedded metadata
        arrow_table = arrow_table.replace_schema_metadata(
            {
                **(arrow_table.schema.metadata or {}),
                b"algenta_schema": json.dumps(schema_meta).encode(),
            }
        )
        buf = io.BytesIO()
        pq.write_table(arrow_table, buf)
        parquet_bytes = buf.getvalue()

        entry = _CachedSource(
            parquet_bytes=parquet_bytes,
            parquet_schema_meta=json.dumps(schema_meta).encode(),
            profile=profile,
            mojo_profile=mojo_prof,
            relations=rels,
            graph_nodes=src_graph[src.name],
            schema_meta=schema_meta,
            mojo_profiling_status=profiling_status,
            content_keyed=content_keyed,
        )
        async with _CACHE_LOCK:
            _source_cache_put(entry, cache_key)

        result.append(
            {
                "source": src.name,
                "cached": False,
                "schema": schema_meta,
                "mojo_profiling_status": profiling_status,
                "parquet_b64": base64.b64encode(parquet_bytes).decode(),
            }
        )

    return {
        "sources": result,
        "latency_ms": round((time.monotonic() - t0) * 1000, 1),
    }

@router.post(
    "/v1/query/batch",
    response_model=QueryBatchResponse,
    summary="Execute multiple governed exact queries in one request",
)
async def query_batch(
    payload: QueryBatchRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
) -> QueryBatchResponse:
    request_id = getattr(request.state, "request_id", None)
    defaults = payload.defaults
    items = payload.queries
    seen_keys: set[str] = set()
    for item in items:
        if item.key in seen_keys:
            raise _http_error(
                422,
                code="invalid_query_batch",
                message=f"Duplicate query batch key '{item.key}'.",
                request_id=request_id,
            )
        seen_keys.add(item.key)

    results: list[QueryBatchItemResponse] = []
    for item in items:
        try:
            merged_request = _merge_query_batch_defaults(defaults, item)
            query_result = await query_sources(
                payload=merged_request,
                request=request,
                auth=auth,
            )
            results.append(
                QueryBatchItemResponse(
                    key=item.key,
                    data=query_result,
                    metadata=_query_execution_metadata(query_result),
                )
            )
        except HTTPException as exc:
            results.append(
                QueryBatchItemResponse(
                    key=item.key,
                    error=_query_batch_error_from_exception(exc),
                )
            )
        except Exception as exc:  # pragma: no cover - defensive conversion
            logger.exception("query_batch_item_failed", key=item.key, request_id=request_id)
            results.append(
                QueryBatchItemResponse(
                    key=item.key,
                    error=QueryBatchError(
                        code="internal_error",
                        message="Query batch item failed unexpectedly.",
                        details={"reason": str(exc)},
                    ),
                )
            )

    return QueryBatchResponse(results=results, request_id=request_id)

@router.post(
    "/v1/query/sql-report",
    response_model=SQLReportResponse,
    summary="Execute a constrained read-only SQL report over authorized datasets",
)
async def query_sql_report(
    payload: SQLReportRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
) -> SQLReportResponse:
    request_id = getattr(request.state, "request_id", None)
    t0 = time.monotonic()
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_visibility import get_visible_dataset_entry

    source_bindings: list[tuple[str, str]] = []
    seen_aliases: set[str] = set()
    for source in payload.sources:
        entry = get_visible_dataset_entry(org_id, source.dataset_id, auth)
        if entry is None:
            raise _http_error(
                404,
                code="not_found",
                message=f"Dataset '{source.dataset_id}' not found.",
                request_id=request_id,
            )
        alias = normalize_sql_report_alias(source.dataset_id, source.alias)
        if alias in seen_aliases:
            raise _http_error(
                422,
                code="sql_report_duplicate_source_alias",
                message=f"Duplicate SQL report alias '{alias}'.",
                request_id=request_id,
            )
        seen_aliases.add(alias)
        source_bindings.append((alias, source.dataset_id))

    try:
        result = execute_sql_report(
            org_id=org_id,
            sources=source_bindings,
            sql=payload.sql,
            max_rows=payload.max_rows,
        )
    except SQLReportServiceError as exc:
        raise _http_error(
            exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            details=[(None, str(exc.details or {}))] if exc.details else None,
        ) from exc

    return SQLReportResponse(
        columns=result["columns"],
        rows=result["rows"],
        row_count=result["row_count"],
        truncated=result["truncated"],
        request_id=request_id,
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
    )

