"""Submodule _execute_main.py of apps.api_server.routers.query.

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
def execute_join_path(
    records_by_source: dict[str, list[dict[str, Any]]],
    base_source: str,
    metric_col: str,
    group_source: str,
    group_col: str,
    ordered_edges: list[JoinEdgeSpec],
    agg: str,
    limit: int | None,
    order: str,
    reject_on_ambiguity: bool = True,
) -> tuple[Any, int, list[str]]:
    plan: list[str] = [
        f"Join-path execution: {base_source} -> {group_source} ({len(ordered_edges)} hops)"
    ]
    base_records = records_by_source.get(base_source, [])
    if not base_records:
        return None, 0, plan + [f"No rows loaded for base source '{base_source}'"]

    resolved_metric_col = _resolve_col_name(metric_col, base_records)
    if resolved_metric_col != metric_col:
        plan.append(f"metric_col '{metric_col}' -> resolved to '{resolved_metric_col}'")
        metric_col = resolved_metric_col

    current_rows: list[dict[str, Any]] = []
    if agg == "count":
        current_rows = [{"row": row} for row in base_records]
    else:
        for row in base_records:
            value = _num(row, metric_col)
            if value is None:
                continue
            current_rows.append({"metric": value, "row": row})

    if not current_rows:
        if agg == "count":
            return None, 0, plan + ["No rows available for join-path count"]
        return None, 0, plan + [f"No numeric rows available for metric '{metric_col}'"]

    resolved_group_col = group_col
    for idx, edge in enumerate(ordered_edges, start=1):
        left_records = records_by_source.get(edge.left_source, [])
        right_records = records_by_source.get(edge.right_source, [])
        if not right_records:
            return None, 0, plan + [f"No rows loaded for join source '{edge.right_source}'"]

        resolved_left_key = (
            _resolve_col_name(edge.left_key, left_records) if left_records else edge.left_key
        )
        resolved_right_key = (
            _resolve_col_name(edge.right_key, right_records) if right_records else edge.right_key
        )

        if idx == len(ordered_edges):
            resolved_group_col = _resolve_col_name(group_col, right_records)
            if resolved_group_col != group_col:
                plan.append(f"group_col '{group_col}' -> resolved to '{resolved_group_col}'")

        collapse_field = resolved_group_col
        collapse_label = f"group value '{resolved_group_col}'"
        if idx < len(ordered_edges):
            next_edge = ordered_edges[idx]
            collapse_field = _resolve_col_name(next_edge.left_key, right_records)
            collapse_label = f"downstream key '{collapse_field}'"

        right_index: dict[str, list[dict[str, Any]]] = {}
        for right_row in right_records:
            key = _blankish_value(right_row.get(resolved_right_key))
            if key is not None:
                right_index.setdefault(key, []).append(right_row)

        collapsed_keys = 0
        collapsed_match_by_key: dict[str, dict[str, Any]] = {}
        ambiguous_key_details: dict[str, tuple[int, list[str]]] = {}
        if reject_on_ambiguity:
            for join_key, matches in right_index.items():
                if len(matches) <= 1:
                    continue
                projected_values: list[str] = []
                projected_seen: set[str] = set()
                representative = matches[0]
                for match in matches:
                    projected = _blankish_value(match.get(collapse_field))
                    normalized = projected or "<blank>"
                    if normalized not in projected_seen:
                        projected_seen.add(normalized)
                        if len(projected_values) < 3:
                            projected_values.append(normalized)
                    if projected is not None:
                        representative = match
                non_blank_values = {value for value in projected_seen if value != "<blank>"}
                if len(non_blank_values) <= 1:
                    collapsed_match_by_key[join_key] = representative
                    collapsed_keys += 1
                else:
                    ambiguous_key_details[join_key] = (len(matches), projected_values)

        plan.append(
            f"Hop {idx}: {edge.left_source}.{resolved_left_key} = "
            f"{edge.right_source}.{resolved_right_key}"
        )
        if collapsed_keys:
            plan.append(
                f"Hop {idx}: collapsed {collapsed_keys} duplicate key(s) in '{edge.right_source}' "
                f"by consistent {collapse_label}"
            )

        next_rows: list[dict[str, Any]] = []
        for item in current_rows:
            left_row = item["row"]
            join_val = _blankish_value(left_row.get(resolved_left_key))
            if join_val is None:
                continue
            matches = right_index.get(join_val, [])
            if not matches:
                continue
            if len(matches) > 1 and reject_on_ambiguity:
                collapsed = collapsed_match_by_key.get(join_val)
                if collapsed is not None:
                    matches = [collapsed]
                else:
                    match_count, projected_values = ambiguous_key_details.get(
                        join_val,
                        (len(matches), []),
                    )
                    sample = ", ".join(projected_values) if projected_values else "multiple values"
                    return (
                        None,
                        0,
                        plan
                        + [
                            f"Ambiguous join fanout at hop {idx}: key '{join_val}' matched "
                            f"{match_count} rows in '{edge.right_source}' with conflicting "
                            f"{collapse_label} values ({sample})"
                        ],
                    )
            selected = matches[:1] if reject_on_ambiguity else matches
            for match in selected:
                next_item = {"row": match}
                if "metric" in item:
                    next_item["metric"] = item["metric"]
                next_rows.append(next_item)

        current_rows = next_rows
        plan.append(f"Hop {idx}: matched {len(current_rows)} projected rows")
        if not current_rows:
            return None, 0, plan + [f"No rows matched at hop {idx}"]

    buckets: dict[str, list[float]] = {}
    matched = 0
    for item in current_rows:
        grp = _blankish_value(item["row"].get(resolved_group_col))
        if grp is None:
            continue
        matched += 1
        if agg == "count":
            buckets.setdefault(grp, []).append(1.0)
        else:
            buckets.setdefault(grp, []).append(float(item["metric"]))

    if not buckets:
        return None, matched, plan + ["No rows matched in join-path execution"]

    if agg == "count":
        count_result: list[dict[str, str | float]] = [
            {"group": k, "value": float(len(v))} for k, v in buckets.items()
        ]
        count_result.sort(key=lambda x: cast(float, x["value"]), reverse=(order == "desc"))
        if limit:
            count_result = count_result[:limit]
        plan.append(f"COUNT(*) BY `{resolved_group_col}` (join-path) -> {len(count_result)} groups")
        return count_result, matched, plan

    def _agg_fn(vals: list[float]) -> float:
        if not vals:
            return 0.0
        if agg == "sum":
            return sum(vals)
        if agg == "avg":
            return sum(vals) / len(vals)
        if agg == "max":
            return max(vals)
        if agg == "min":
            return min(vals)
        return sum(vals)

    result: list[dict[str, str | float]] = [
        {"group": k, "value": round(_agg_fn(v), 4)} for k, v in buckets.items()
    ]
    result.sort(key=lambda x: cast(float, x["value"]), reverse=(order == "desc"))
    if limit:
        result = result[:limit]

    plan.append(
        f"{agg.upper()}(`{metric_col}`) BY `{resolved_group_col}` "
        f"(join-path) -> {len(result)} groups"
    )
    return result, matched, plan

def execute_cross_source(
    metric_records: list[dict[str, Any]],
    metric_col: str,
    group_records: list[dict[str, Any]],
    group_col: str,
    join_metric_col: str,  # column in metric_records used for join
    join_group_col: str,  # column in group_records used for join
    agg: str,
    limit: int | None,
    order: str,
    join_cardinality: str = "",  # cardinality hint from connections.json
) -> tuple[Any, int, list[str]]:
    """
    Hash-join metric_records ↔ group_records on join keys, then aggregate.
    Returns (result, matched_row_count, plan_steps).
    """
    plan: list[str] = []

    # Resolve column names against actual record keys (handles empty columns + case variants)
    if metric_records:
        resolved = _resolve_col_name(metric_col, metric_records)
        if resolved != metric_col:
            plan.append(f"metric_col '{metric_col}' → resolved to '{resolved}'")
            metric_col = resolved
        resolved = _resolve_col_name(join_metric_col, metric_records)
        if resolved != join_metric_col:
            plan.append(f"join_metric_col '{join_metric_col}' → resolved to '{resolved}'")
            join_metric_col = resolved
    if group_records:
        resolved = _resolve_col_name(group_col, group_records)
        if resolved != group_col:
            plan.append(f"group_col '{group_col}' → resolved to '{resolved}'")
            group_col = resolved
        resolved = _resolve_col_name(join_group_col, group_records)
        if resolved != join_group_col:
            plan.append(f"join_group_col '{join_group_col}' → resolved to '{resolved}'")
            join_group_col = resolved

    plan.append(
        f"Cross-source join: {metric_col} via {join_metric_col}={join_group_col} → {group_col}"
    )

    # Detect empty join key columns before attempting the join
    _jk_metric_sample = [str(r.get(join_metric_col, "")).strip() for r in metric_records[:100]]
    _jk_metric_fill = sum(1 for v in _jk_metric_sample if v) / max(len(_jk_metric_sample), 1)
    if _jk_metric_fill < 0.01:
        plan.append(
            f"⚠ Join key `{join_metric_col}` is ~empty in metric records "
            f"({_jk_metric_fill:.0%} fill) — join will produce 0 matches"
        )
        return None, 0, plan

    # Cardinality warning: many_to_many joins on sum may produce incomplete results
    # because the join_map takes the LAST group value per key (no duplication/fan-out).
    # Results are still valid aggregations — just note the join type.
    if join_cardinality == "many_to_many" and agg == "sum":
        plan.append(
            f"⚠ Join cardinality: many_to_many — each {join_metric_col} key maps to one "
            f"{group_col} value (last seen). Rows with ambiguous key assignment are included once."
        )

    # Build hash map: join_group_col value → group dimension value
    join_map: dict[str, str] = {}
    for r in group_records:
        k = str(r.get(join_group_col, "")).strip()
        group_value = str(r.get(group_col, "?")).strip()
        if k:
            join_map[k] = group_value

    plan.append(f"Join map size: {len(join_map)} keys from {len(group_records)} group rows")

    buckets: dict[str, list[float]] = {}
    matched = 0
    for r in metric_records:
        k = str(r.get(join_metric_col, "")).strip()
        v = _num(r, metric_col)
        if v is None:
            continue
        grp = join_map.get(k)
        if grp is None:
            continue
        matched += 1
        # Filter out empty/null group dimension values — these produce misleading aggregates
        if not grp or grp.lower() in ("none", "null", "nan", ""):
            continue
        buckets.setdefault(grp, []).append(v)

    plan.append(f"Matched {matched}/{len(metric_records)} rows after join")

    if not buckets:
        return None, matched, plan + ["No rows matched in cross-source join"]

    def _agg_fn(vals: list[float]) -> float:
        if not vals:
            return 0.0
        if agg == "sum":
            return sum(vals)
        if agg == "avg":
            return sum(vals) / len(vals)
        if agg == "max":
            return max(vals)
        if agg == "min":
            return min(vals)
        return sum(vals)

    result: list[dict[str, str | float]] = [
        {"group": k, "value": round(_agg_fn(v), 4)} for k, v in buckets.items()
    ]
    result.sort(key=lambda x: cast(float, x["value"]), reverse=(order == "desc"))
    if limit:
        result = result[:limit]

    plan.append(f"{agg.upper()}(`{metric_col}`) BY `{group_col}` (joined) → {len(result)} groups")
    return result, matched, plan

def execute(
    records: list[dict[str, Any]],
    metric_col: str,
    agg: str,
    group_col: str | None,
    date_col: str | None,
    tr: tuple[date, date] | None,
    limit: int | None,
    order: str,
) -> tuple[Any, int, list[str]]:
    plan: list[str] = []
    rows = records

    # Resolve column names: handle empty columns and case/underscore variants
    if records:
        resolved_metric = _resolve_col_name(metric_col, records)
        if resolved_metric != metric_col:
            plan.append(f"Column '{metric_col}' → resolved to '{resolved_metric}'")
            metric_col = resolved_metric
        if group_col:
            resolved_group = _resolve_col_name(group_col, records)
            if resolved_group != group_col:
                plan.append(f"Group column '{group_col}' → resolved to '{resolved_group}'")
                group_col = resolved_group

    if tr and date_col:
        lo, hi = tr
        rows = [r for r in rows if (d := _parse_date(r.get(date_col))) and lo <= d <= hi]
        plan.append(f"Date filter `{date_col}` {lo}→{hi}: {len(records)}→{len(rows)} rows")

    if not rows:
        return None, 0, plan + ["No rows after filtering"]

    if agg == "count" and not group_col:
        plan.append(f"COUNT: {len(rows):,} rows")
        return len(rows), len(rows), plan

    if group_col:
        if agg == "count":
            # count: bucket ALL rows by group key — metric_col is irrelevant
            count_buckets: dict[str, int] = {}
            for r in rows:
                k = _blankish_value(r.get(group_col))
                if k is None:
                    continue
                count_buckets[k] = count_buckets.get(k, 0) + 1
            table_result: list[dict[str, str | float]] = [
                {"group": k, "value": float(v)} for k, v in count_buckets.items()
            ]
            table_result.sort(
                key=lambda x: cast(float, x["value"]),
                reverse=(order == "desc"),
            )
            if limit:
                table_result = table_result[:limit]
            plan.append(f"COUNT(*) BY `{group_col}` → {len(table_result)} groups")
            return table_result, len(rows), plan

        buckets: dict[str, list[float]] = {}
        excluded_null_group_rows = 0
        for r in rows:
            k = _blankish_value(r.get(group_col))
            v = _num(r, metric_col)
            if k is None:
                if v is not None:
                    excluded_null_group_rows += 1
                continue
            if v is not None:
                buckets.setdefault(k, []).append(v)

        if excluded_null_group_rows:
            plan.append(
                f"⚠ {excluded_null_group_rows} rows have empty/null `{group_col}` value — "
                f"excluded from results"
            )

        def _agg_fn(vals: list[float]) -> float:
            if not vals:
                return 0.0
            if agg == "sum":
                return sum(vals)
            if agg == "avg":
                return sum(vals) / len(vals)
            if agg == "max":
                return max(vals)
            if agg == "min":
                return min(vals)
            return sum(vals)  # should never reach here

        grouped_table_result: list[dict[str, str | float]] = [
            {"group": k, "value": round(_agg_fn(v), 4)} for k, v in buckets.items()
        ]
        grouped_table_result.sort(
            key=lambda x: cast(float, x["value"]),
            reverse=(order == "desc"),
        )
        if limit:
            grouped_table_result = grouped_table_result[:limit]
        plan.append(
            f"{agg.upper()}(`{metric_col}`) BY `{group_col}` → {len(grouped_table_result)} groups"
        )
        return grouped_table_result, len(rows), plan

    vals = [v for r in rows if (v := _num(r, metric_col)) is not None]
    if not vals:
        return None, len(rows), plan + [f"No numeric values in `{metric_col}`"]

    result: float
    if agg == "sum":
        result = sum(vals)
    elif agg == "avg":
        result = sum(vals) / len(vals)
    elif agg == "max":
        result = max(vals)
    elif agg == "min":
        result = min(vals)
    else:
        result = sum(vals)

    plan.append(f"{agg.upper()}(`{metric_col}`) over {len(vals):,} values = {result:.4f}")
    return round(result, 4), len(rows), plan

