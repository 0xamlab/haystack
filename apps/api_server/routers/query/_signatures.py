"""Submodule _signatures.py of apps.api_server.routers.query.

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
# Lazy facade-routed wrappers for monkey-patched / cross-layer names.
# Tests patch apps.api_server.routers.query.X = fake; each call here
# re-reads the attribute from the facade so the patch propagates.
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


async def _detect_relations(
    source: str,
    profiles: dict[str, dict[str, Any]],
    min_confidence: float = 0.70,
) -> list[dict[str, Any]]:
    prof = profiles.get(source, {})
    # Only columns with a meaningful fill rate — skips columns that were all-empty
    numeric_cols = {
        f: info
        for f, info in prof.items()
        if info.get("is_numeric") and info.get("fill_rate", 1.0) > 0.01
    }
    if len(numeric_cols) < 3:
        return []

    # Use all collected numeric values (up to _TARGET_SAMPLES per column)
    # Take the minimum length across columns so vectors are aligned
    col_nums = {col: info.get("numeric", []) for col, info in numeric_cols.items()}
    n_sample = min(
        min((len(v) for v in col_nums.values() if v), default=0),
        _relation_detect_sample_limit(len(col_nums)),
    )
    if n_sample < 3:
        return []

    cols_payload: dict[str, list[float]] = {
        col: nums[:n_sample] for col, nums in col_nums.items() if nums
    }
    skip_reason = _get_query_relation_detect_skip_reason()
    if skip_reason is not None:
        logger.debug(
            "query_relation_detect_circuit_open",
            cooldown_s=_QUERY_RELATION_DETECT_COOLDOWN_S,
            reason=skip_reason,
        )
        return []
    payload = {
        "engine_type": "relation_detect",
        "source": source,
        "min_confidence": min_confidence,
        "columns": cols_payload,
    }
    result, engine_status = await _invoke_optional_mojo_engine(
        "relation_detect",
        payload,
    )
    if result is None:
        if engine_status["reason"] == "engine_circuit_open":
            logger.debug(
                "query_relation_detect_circuit_open",
                cooldown_s=_QUERY_RELATION_DETECT_COOLDOWN_S,
                reason=str(engine_status.get("message") or engine_status["reason"]),
            )
            return []
        _record_query_relation_detect_failure(
            str(engine_status.get("message") or engine_status["reason"]),
        )
        logger.debug("query_relation_detect_error", engine_status=engine_status)
        return []
    _clear_query_relation_detect_failure()
    relationships = result.get("relationships", [])
    return relationships if isinstance(relationships, list) else []

def _normalize_hint_text(value: str | None) -> str:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").casefold())
        if token not in _STOP_TOKENS
    ]
    if not tokens:
        return ""
    return " ".join(sorted(dict.fromkeys(tokens)))

def _weak_raw_text_intent(raw_text: str | None) -> tuple[str, list[str]]:
    normalized = " ".join(re.findall(r"[a-z0-9]+", (raw_text or "").casefold()))
    if not normalized:
        return "", []
    if " by " in normalized:
        metric_text, group_text = normalized.split(" by ", 1)
        metric_hint = _normalize_hint_text(metric_text)
        group_hint = _normalize_hint_text(group_text)
        return metric_hint, ([group_hint] if group_hint else [])
    return _normalize_hint_text(normalized), []

def _stable_list(values: list[str]) -> list[str]:
    normalized = [_normalize_hint_text(value) for value in values]
    return sorted({value for value in normalized if value})

def _exact_query_required_sources(payload: QueryRequest) -> list[str]:
    names: list[str] = []

    def _append(name: str | None) -> None:
        normalized = str(name or "").strip()
        if normalized and normalized not in names:
            names.append(normalized)

    _append(payload.source_name)
    if payload.join_path is None:
        return names

    _append(payload.join_path.base_source)
    _append(payload.join_path.group_source)
    for edge in payload.join_path.edges or []:
        _append(edge.left_source)
        _append(edge.right_source)
    return names

def _intent_signature_payload(
    *,
    dataset_id: str | None,
    allow_org_scope: bool,
    metric_role: str,
    metric_hint: str,
    group_by: list[str],
    preferred_source: str | None,
    aggregation: str,
    filter_spec: FilterSpec | None,
    limit: int | None,
    order: str,
    constraints: ConstraintSpec,
    raw_text: str | None,
    schema_revision: str,
) -> dict[str, Any]:
    normalized_metric_hint = _normalize_hint_text(metric_hint)
    normalized_group_by = _stable_list(group_by)
    raw_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", (raw_text or "").casefold())
        if token not in _STOP_TOKENS
    }
    for token in re.findall(r"[a-z0-9]+", normalized_metric_hint):
        raw_tokens.discard(token)
    for normalized_group in normalized_group_by:
        for token in re.findall(r"[a-z0-9]+", normalized_group):
            raw_tokens.discard(token)
    return {
        "schema_revision": schema_revision,
        "dataset_scope": dataset_id or "",
        "allow_org_scope": bool(allow_org_scope),
        "metric_role": metric_role,
        "metric_hint": normalized_metric_hint,
        "group_by": normalized_group_by,
        "preferred_source": (preferred_source or "").strip(),
        "aggregation": aggregation,
        "filter": _normalize_filter_spec(filter_spec),
        "limit": limit,
        "order": order,
        "constraints": _normalize_constraint_spec(constraints),
        "raw_tokens": sorted(raw_tokens),
    }

def _intent_signature(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[
        :24
    ]

def _prune_resolve_cache(org_id: str, schema_revision: str) -> None:
    stale_keys = [
        key
        for key, value in _RESOLVE_CACHE.items()
        if value.get("org_id") == org_id and value.get("schema_revision") != schema_revision
    ]
    for key in stale_keys:
        _RESOLVE_CACHE.pop(key, None)

def _resolve_cache_get(key: str) -> dict[str, Any] | None:
    cached = _RESOLVE_CACHE.get(key)
    if not cached:
        return None
    if (time.monotonic() - float(cached.get("_ts", 0.0))) >= _RESOLVE_CACHE_TTL:
        _RESOLVE_CACHE.pop(key, None)
        return None
    return cached

def _resolve_cache_put(key: str, value: dict[str, Any]) -> None:
    if len(_RESOLVE_CACHE) >= _RESOLVE_CACHE_MAX:
        oldest_key = min(_RESOLVE_CACHE.items(), key=lambda item: item[1].get("_ts", 0.0))[0]
        _RESOLVE_CACHE.pop(oldest_key, None)
    _RESOLVE_CACHE[key] = {**value, "_ts": time.monotonic()}

def _graph_node_cache_get(
    key: tuple[str, str, str],
) -> dict[str, ColumnNode] | None:
    cached = _GRAPH_NODE_CACHE.get(key)
    if not cached:
        return None
    cached["_ts"] = time.monotonic()
    nodes = cached.get("nodes")
    return nodes if isinstance(nodes, dict) else None

def _graph_node_cache_put(
    key: tuple[str, str, str],
    nodes: dict[str, ColumnNode],
) -> dict[str, ColumnNode]:
    if len(_GRAPH_NODE_CACHE) >= _GRAPH_NODE_CACHE_MAX:
        oldest_key = min(_GRAPH_NODE_CACHE.items(), key=lambda item: item[1].get("_ts", 0.0))[0]
        _GRAPH_NODE_CACHE.pop(oldest_key, None)
    _GRAPH_NODE_CACHE[key] = {"nodes": nodes, "_ts": time.monotonic()}
    return nodes

def _dataset_exact_column_cache_get(
    key: tuple[str, str, str],
) -> dict[str, dict[str, Any] | None] | None:
    cached = _DATASET_EXACT_COLUMN_CACHE.get(key)
    if cached is None:
        return None
    cached["_ts"] = time.monotonic()
    lookup = cached.get("lookup")
    return lookup if isinstance(lookup, dict) else None

def _dataset_exact_column_cache_put(
    key: tuple[str, str, str],
    lookup: dict[str, dict[str, Any] | None],
) -> dict[str, dict[str, Any] | None]:
    if len(_DATASET_EXACT_COLUMN_CACHE) >= _DATASET_EXACT_COLUMN_CACHE_MAX:
        oldest_key = min(
            _DATASET_EXACT_COLUMN_CACHE.items(),
            key=lambda item: float(item[1].get("_ts", 0.0) or 0.0),
        )[0]
        _DATASET_EXACT_COLUMN_CACHE.pop(oldest_key, None)
    _DATASET_EXACT_COLUMN_CACHE[key] = {"lookup": lookup, "_ts": time.monotonic()}
    return lookup

def _graph_nodes_from_cached_meta(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    schema_meta: dict[str, Any],
) -> dict[str, ColumnNode]:
    cache_key = (org_id, dataset_id, schema_revision)
    cached = _graph_node_cache_get(cache_key)
    if cached is not None:
        return cached
    return _graph_node_cache_put(cache_key, _graph_nodes_from_meta(schema_meta))

def _inline_schema_revision(graph: SchemaGraph) -> str:
    payload = {
        src: [
            {
                "name": col,
                "role": node.role,
                "formula": node.formula,
                "semantic_type": node.semantic_type,
                "magnitude": node.magnitude_class,
                "confidence": round(float(node.confidence or 0.0), 3),
            }
            for col, node in sorted(nodes.items())
        ]
        for src, nodes in sorted(graph.items())
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[
        :24
    ]

def _find_exact_dataset_column(
    schema_meta: dict[str, Any],
    normalized_hint: str,
) -> dict[str, Any] | None:
    return _find_exact_dataset_column_impl(
        schema_meta=schema_meta,
        normalized_hint=normalized_hint,
        normalize_hint_text=_normalize_hint_text,
    )

def _dataset_exact_column_lookup(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    schema_meta: dict[str, Any],
) -> dict[str, dict[str, Any] | None]:
    return _dataset_exact_column_lookup_impl(
        org_id=org_id,
        dataset_id=dataset_id,
        schema_revision=schema_revision,
        schema_meta=schema_meta,
        dataset_exact_column_cache_get=_dataset_exact_column_cache_get,
        dataset_exact_column_cache_put=_dataset_exact_column_cache_put,
        normalize_hint_text=_normalize_hint_text,
    )

def _find_exact_dataset_column_cached(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    schema_meta: dict[str, Any],
    normalized_hint: str,
) -> dict[str, Any] | None:
    return _find_exact_dataset_column_cached_impl(
        org_id=org_id,
        dataset_id=dataset_id,
        schema_revision=schema_revision,
        schema_meta=schema_meta,
        normalized_hint=normalized_hint,
        dataset_exact_column_lookup_fn=_dataset_exact_column_lookup,
    )

async def _get_resolve_dataset_meta(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
) -> tuple[dict[str, Any] | None, dict[str, ColumnNode] | None]:
    from apps.api_server.services import source_registry as _sreg_dataset_meta

    return await _get_resolve_dataset_meta_impl(
        org_id=org_id,
        dataset_id=dataset_id,
        schema_revision=schema_revision,
        cache_lock=_CACHE_LOCK,
        source_cache=_SOURCE_CACHE,
        graph_nodes_from_cached_meta=_graph_nodes_from_cached_meta,
        get_source_meta_fn=_sreg_dataset_meta.get_source_meta,
    )

def _resolve_single_dataset_fast_path(
    *,
    org_id: str,
    payload: ResolveRequest,
    dataset_entry: dict[str, Any],
    dataset_id: str,
    schema_meta: dict[str, Any] | None,
    cached_nodes: dict[str, ColumnNode] | None,
    schema_revision: str,
    metric_hint: str,
    combined_group_by: list[str],
    request_id: str | None,
    intent_signature: str,
    started_at: float,
) -> ResolveResponse:
    return _resolve_single_dataset_fast_path_impl(
        org_id=org_id,
        payload=payload,
        dataset_entry=dataset_entry,
        dataset_id=dataset_id,
        schema_meta=schema_meta,
        cached_nodes=cached_nodes,
        schema_revision=schema_revision,
        metric_hint=metric_hint,
        combined_group_by=combined_group_by,
        request_id=request_id,
        intent_signature=intent_signature,
        started_at=started_at,
        graph_nodes_from_meta=_graph_nodes_from_meta,
        normalize_hint_text=_normalize_hint_text,
        stable_list=_stable_list,
        find_exact_dataset_column_cached=_find_exact_dataset_column_cached,
        select_count_anchor_column=_select_count_anchor_column,
        decision_contract_flags=_decision_contract_flags,
        resolve_metric_column_fn=resolve_metric_column,
        resolve_group_column_graph_fn=resolve_group_column_graph,
        build_resolve_response_fn=_build_resolve_response,
        http_error_fn=_http_error,
        max_resolve_candidates=_MAX_RESOLVE_CANDIDATES,
        resolve_budget_ms=_RESOLVE_BUDGET_MS,
    )

async def _resolve_registered_intent(
    payload: ResolveRequest,
    *,
    auth: AuthContext,
    request_id: str | None,
) -> ResolveResponse:
    from apps.api_server.services import source_registry as _sreg_visible

    return await _resolve_registered_intent_impl(
        payload,
        auth=auth,
        request_id=request_id,
        resolve_scope_entries_fn=_resolve_scope_entries,
        resolve_entry_ready_fn=_resolve_entry_ready,
        schema_revision_fn=_sreg_visible.schema_revision,
        source_schema_revision_fn=_sreg_visible.source_schema_revision,
        get_source_meta_fn=_sreg_visible.get_source_meta,
        normalize_hint_text_fn=_normalize_hint_text,
        stable_list_fn=_stable_list,
        weak_raw_text_intent_fn=_weak_raw_text_intent,
        intent_signature_payload_fn=_intent_signature_payload,
        intent_signature_fn=_intent_signature,
        prune_resolve_cache_fn=_prune_resolve_cache,
        resolve_cache_get_fn=_resolve_cache_get,
        resolve_cache_put_fn=_resolve_cache_put,
        get_resolve_dataset_meta_fn=_get_resolve_dataset_meta,
        resolve_single_dataset_fast_path_fn=_resolve_single_dataset_fast_path,
        get_registry_planner_fn=_get_registry_planner,
        run_cached_planner_method_fn=_run_cached_planner_method,
        planner_query_confidence_fn=_planner_query_confidence,
        planner_metric_candidate_payloads_fn=_planner_metric_candidate_payloads,
        planner_load_bearing_validation_notes_fn=_planner_load_bearing_validation_notes,
        decision_contract_flags_fn=_decision_contract_flags,
        build_resolve_response_fn=_build_resolve_response,
        dedupe_source_values_fn=_dedupe_source_values,
        resolved_plan_current_schema_revision_fn=_resolved_plan_current_schema_revision,
        select_count_anchor_column_fn=_select_count_anchor_column,
        http_error_fn=_http_error,
        max_resolve_candidates=_MAX_RESOLVE_CANDIDATES,
        max_join_path_hops=_MAX_JOIN_PATH_HOPS,
        resolve_budget_ms=_RESOLVE_BUDGET_MS,
    )

def _query_uses_legacy_planning(payload: QueryRequest) -> bool:
    if payload.resolved_plan is not None:
        return False
    if payload.source_name and payload.metric_column:
        return False
    return not payload.sources

def _query_execution_metadata(response: QueryResponse) -> QueryExecutionMetadata:
    return QueryExecutionMetadata(
        request_id=response.request_id,
        latency_ms=response.latency_ms,
    )

def _merge_query_batch_defaults(
    defaults: QueryBatchDefaults | None,
    item: QueryBatchItemRequest,
) -> QueryRequest:
    if defaults is None:
        return item.request
    default_payload = defaults.model_dump(mode="python", exclude_none=True)
    request_payload = item.request.model_dump(mode="python")
    for field_name, value in default_payload.items():
        if field_name not in item.request.model_fields_set:
            request_payload[field_name] = value
    return QueryRequest.model_validate(request_payload)

def _query_batch_error_from_exception(exc: HTTPException) -> QueryBatchError:
    detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
    error: dict[str, Any] = detail.get("error", {}) if isinstance(detail, dict) else {}
    details = error.get("details") if isinstance(error, dict) else None
    if isinstance(details, list):
        normalized_details: dict[str, Any] = {"items": details}
    elif isinstance(details, dict):
        normalized_details = details
    else:
        normalized_details = {}
    return QueryBatchError(
        code=str(error.get("code") or "query_batch_item_failed"),
        message=str(error.get("message") or str(exc.detail)),
        details=normalized_details,
    )

