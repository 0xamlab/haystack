"""Helpers extracted from query_sources endpoint — inline group.

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

async def _resolve_inline_anchor_metric_group(
    payload: QueryRequest,
    request_id: str | None,
    query_id: str,
    plan: list[str],
    t0: float,
    target_role: str,
    cache_entries: dict[str, "_CachedSource"],
    cache_hits: set[str],
) -> tuple[
    QueryResponse | None,
    "SchemaGraph",
    str,
    str,
    str,
    "ColumnNode",
    float,
    list[dict[str, Any]],
    dict[str, float],
    bool,
    str | None,
    str,
    float,
]:
    """Inline-graph anchor/metric/group resolution stage.

    Builds the inline ``SchemaGraph``, runs Mojo source resolution (with the
    ``preferred_source`` hard-lock), resolves the metric column (with METRIC
    role fallback and global fallback), resolves the group column, and
    enforces decision-contract validation. When the metric is unresolvable
    or the decision contract rejects the request, the first tuple element
    is a short-circuit ``QueryResponse`` and the caller must return it
    immediately. Otherwise the first element is ``None`` and the remaining
    fields describe the resolved state for downstream execution.
    """
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
        return (_build_query_response(
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
        ), cast("SchemaGraph", {}), "", "", "", cast("ColumnNode", None), 0.0, [], {}, False, None, "", 0.0)

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
        return (_build_query_response(
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
        ), cast("SchemaGraph", {}), "", "", "", cast("ColumnNode", None), 0.0, [], {}, False, None, "", 0.0)
    return (
        None,
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
    )


def _execute_inline_and_build_response(
    payload: QueryRequest,
    request_id: str | None,
    query_id: str,
    plan: list[str],
    t0: float,
    graph: "SchemaGraph",
    cache_entries: dict[str, "_CachedSource"],
    parsed_tables: dict[str, Any],
    _reg_connections: list[dict[str, Any]],
    src_name: str,
    metric_col: str,
    metric_node: "ColumnNode",
    metric_conf: float,
    all_candidates: list[dict[str, Any]],
    all_src_scores: dict[str, float],
    ambiguous: bool,
    group_col: str | None,
    group_src: str,
    decision_confidence: float,
    schema_revision_inline: str,
) -> QueryResponse:
    """Final inline-path execution + response assembly.

    Handles time-filter resolution, record loading, filter application,
    cross-source join key resolution (with rejection paths for ambiguous /
    missing joins), execute()/execute_cross_source() dispatch, and the
    final ``QueryResponse``. Raises ``HTTPException`` 422 on
    ``invalid_filter_condition``.
    """
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


