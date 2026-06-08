"""Submodule _execute_filters.py of apps.api_server.routers.query.

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
# Lazy facade-routed wrappers for monkey-patched / cross-layer names.
# Tests patch apps.api_server.routers.query.X = fake; each call here
# re-reads the attribute from the facade so the patch propagates.
def _normalize_hint_text(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._normalize_hint_text
    if fn is _normalize_hint_text:
        from apps.api_server.routers.query._signatures import _normalize_hint_text as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def _quarter_bounds(d: date) -> tuple[date, date]:
    q = (d.month - 1) // 3
    start = date(d.year, q * 3 + 1, 1)
    end_m = start.month + 2
    ey = start.year
    if end_m > 12:
        end_m -= 12
        ey += 1
    end = date(ey, 12, 31) if end_m == 12 else date(ey, end_m + 1, 1) - timedelta(days=1)
    return start, end

def time_range(tf: str) -> tuple[date, date] | None:
    today = date.today()
    if tf == "last_quarter":
        s, _ = _quarter_bounds(today)
        return _quarter_bounds(s - timedelta(days=1))
    if tf == "this_quarter":
        return _quarter_bounds(today)
    if tf == "last_month":
        last = today.replace(day=1) - timedelta(days=1)
        return last.replace(day=1), last
    if tf == "this_month":
        return today.replace(day=1), today
    if tf == "last_year":
        y = today.year - 1
        return date(y, 1, 1), date(y, 12, 31)
    if tf == "this_year":
        return date(today.year, 1, 1), today
    return None

def find_time_column(source: str, graph: SchemaGraph) -> str | None:
    return next(
        (col for col, node in graph.get(source, {}).items() if node.role == TIME),
        None,
    )

def _parse_date(v: Any) -> date | None:
    if v is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%Y-%m"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            pass
    return None

def _num(r: dict[str, Any], col: str) -> float | None:
    v = r.get(col)
    try:
        if v is None:
            return None
        num = float(v)
        if not math.isfinite(num):
            return None
        return num
    except (TypeError, ValueError):
        return None

def _blankish_value(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        text = str(v)
        return text
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        try:
            if not math.isfinite(v):
                return None
            if v.is_integer():
                return str(int(v))
        except (TypeError, ValueError):
            return None
        return str(v)
    text = str(v).strip()
    if not text or text.lower() in {"?", "none", "null", "nan"}:
        return None
    return text

def _has_populated_cell(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        text = v.strip()
        return bool(text) and text.lower() not in {"?", "none", "null", "nan"}
    if isinstance(v, float):
        try:
            return math.isfinite(v)
        except (TypeError, ValueError):
            return False
    if isinstance(v, list | tuple | set | dict):
        return len(v) > 0
    size = getattr(v, "size", None)
    if size is not None:
        try:
            return int(size) > 0
        except (TypeError, ValueError):
            return True
    return True

def _resolve_col_name(col: str, records: list[dict[str, Any]]) -> str:
    """
    Resolve a column name to the actual key in the records, applying two fallbacks:

    1. Exact match exists but column is empty (fill_rate ~ 0)
       → look for a non-empty variant with the same normalized name
         (spaces ↔ underscores, case-insensitive).
         Fixes: PRODUCT_LINE (empty) → Product Line (100% filled).

    2. No exact match at all
       → case-insensitive / underscore↔space normalized lookup.
         Fixes: "unit cost" → "Unit Cost".
    """
    if not records:
        return col
    first = records[0]
    sample = records[:100]

    def _norm(value: str) -> str:
        return value.lower().replace("_", " ").replace("-", " ").strip()

    if col in first:
        # Exact key exists — check whether it is populated
        non_empty = sum(1 for r in sample if _has_populated_cell(r.get(col)))
        if non_empty > 0:
            return col  # populated: use as-is
        # Column exists but is empty — look for a non-empty normalized variant
        col_norm = _norm(col)
        for k in first:
            if k == col:
                continue
            if _norm(k) == col_norm:
                alt_non_empty = sum(1 for r in sample if _has_populated_cell(r.get(k)))
                if alt_non_empty > 0:
                    return k
        return col  # no populated alternative; caller gets empty groups (expected)

    # No exact match — try normalized lookup
    col_norm = _norm(col)
    for k in first:
        if _norm(k) == col_norm:
            return k
    return col  # unknown column; caller handles the miss

_FILTER_NUMERIC_OPS = frozenset({"gt", "gte", "lt", "lte"})

_FILTER_NULL_OPS = frozenset({"is_null", "is_not_null"})

_FILTER_DIMENSION_ROLES = frozenset({CATEGORY, TEXT, IDENTIFIER, TIME})

_FILTER_TRUE_VALUES = frozenset({"1", "true", "t", "yes", "y"})

_FILTER_FALSE_VALUES = frozenset({"0", "false", "f", "no", "n"})

@dataclass(frozen=True)
class ResolvedFilterCondition:
    source_name: str
    column: str
    op: str
    value: Any | None = None
    values: tuple[Any, ...] = field(default_factory=tuple)

def _filter_number_like(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None

def _filter_boolean_like(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, float) and math.isfinite(value) and value in {0.0, 1.0}:
        return bool(int(value))
    if value is None:
        return None
    normalized = str(value).strip().casefold()
    if normalized in _FILTER_TRUE_VALUES:
        return True
    if normalized in _FILTER_FALSE_VALUES:
        return False
    return None

def _filter_value_is_nullish(value: Any) -> bool:
    return not _has_populated_cell(value)

def _filter_value_equals(row_value: Any, expected: Any) -> bool:
    row_bool = _filter_boolean_like(row_value)
    expected_bool = _filter_boolean_like(expected)
    if row_bool is not None and expected_bool is not None:
        return row_bool is expected_bool

    row_number = _filter_number_like(row_value)
    expected_number = _filter_number_like(expected)
    if row_number is not None and expected_number is not None:
        return row_number == expected_number

    row_text = _blankish_value(row_value)
    expected_text = _blankish_value(expected)
    if row_text is None or expected_text is None:
        return False
    return row_text.casefold() == expected_text.casefold()

def _sample_numeric_field(records: list[dict[str, Any]], field_name: str) -> bool:
    observed = 0
    for row in records[:50]:
        value = row.get(field_name)
        if _filter_value_is_nullish(value):
            continue
        observed += 1
        if _filter_number_like(value) is None:
            return False
    return observed > 0

def _sample_boolean_field(records: list[dict[str, Any]], field_name: str) -> bool:
    observed = 0
    for row in records[:50]:
        value = row.get(field_name)
        if _filter_value_is_nullish(value):
            continue
        observed += 1
        if _filter_boolean_like(value) is None:
            return False
    return observed > 0

def _filter_field_match_score(field_name: str, normalized_hint: str) -> tuple[float, bool]:
    normalized_field = _normalize_hint_text(field_name)
    if not normalized_field or not normalized_hint:
        return 0.0, False
    if normalized_field == normalized_hint:
        return 1.0, True
    if normalized_field.startswith(normalized_hint) or normalized_hint.startswith(normalized_field):
        return 0.95, False
    if normalized_hint in normalized_field or normalized_field in normalized_hint:
        return 0.9, False

    hint_tokens = set(normalized_hint.split())
    field_tokens = set(normalized_field.split())
    if not hint_tokens or not field_tokens:
        return 0.0, False
    overlap_forward = len(hint_tokens & field_tokens) / len(field_tokens)
    overlap_backward = len(hint_tokens & field_tokens) / len(hint_tokens)
    overlap = (overlap_forward + overlap_backward) / 2
    return round(overlap, 4), False

def _preferred_filter_value_type(
    condition: FilterConditionSpec,
) -> str | None:
    if condition.op in _FILTER_NUMERIC_OPS:
        return "numeric"
    if condition.op in _FILTER_NULL_OPS:
        return None
    if condition.op == "in":
        values = list(condition.values or [])
        if values and all(_filter_boolean_like(value) is not None for value in values):
            return "boolean"
        if values and all(_filter_number_like(value) is not None for value in values):
            return "numeric"
        return None
    if _filter_boolean_like(condition.value) is not None:
        return "boolean"
    if _filter_number_like(condition.value) is not None:
        return "numeric"
    return None

def _resolve_filter_condition_column(
    *,
    condition: FilterConditionSpec,
    source_name: str,
    graph_nodes: dict[str, ColumnNode],
    records: list[dict[str, Any]],
) -> str:
    first_row = records[0] if records else {}
    if condition.column:
        if records:
            resolved = _resolve_col_name(condition.column, records)
            if resolved in first_row:
                return resolved
        for field_name in graph_nodes:
            if _normalize_hint_text(field_name) == _normalize_hint_text(condition.column):
                return field_name
        raise ValueError(
            f"Filter column '{condition.column}' was not found in source '{source_name}'."
        )

    normalized_hint = _normalize_hint_text(condition.dimension_hint)
    if not normalized_hint:
        raise ValueError(
            f"Filter dimension_hint for source '{source_name}' is empty after normalization."
        )

    field_names: list[str] = []
    for field_name in graph_nodes:
        if field_name not in field_names:
            field_names.append(field_name)
    for field_name in first_row:
        if field_name not in field_names:
            field_names.append(field_name)

    value_type = _preferred_filter_value_type(condition)
    candidates: list[tuple[float, bool, str]] = []
    for field_name in field_names:
        lexical_score, exact_match = _filter_field_match_score(field_name, normalized_hint)
        if lexical_score <= 0.0:
            continue
        node = graph_nodes.get(field_name)
        is_numeric = (
            bool(node.is_numeric)
            if node is not None
            else _sample_numeric_field(records, field_name)
        )
        is_boolean = _sample_boolean_field(records, field_name)
        suitability = 0.0
        if value_type == "numeric":
            suitability = 0.35 if is_numeric else -0.25
        elif value_type == "boolean":
            if is_boolean:
                suitability = 0.35
            elif is_numeric:
                suitability = -0.10
        elif condition.op in {"eq", "in"}:
            suitability = (
                0.12
                if (not is_numeric or (node and node.role in _FILTER_DIMENSION_ROLES))
                else -0.08
            )
        elif condition.op in _FILTER_NULL_OPS:
            suitability = (
                0.08 if (not is_numeric or (node and node.role in _FILTER_DIMENSION_ROLES)) else 0.0
            )
        overall_score = round(lexical_score + suitability, 4)
        if overall_score < 0.60 and not exact_match:
            continue
        candidates.append((overall_score, exact_match, field_name))

    if not candidates:
        raise ValueError(
            f"Filter dimension_hint '{condition.dimension_hint}' did not resolve in source "
            f"'{source_name}'."
        )

    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    best_score, best_exact, best_field = candidates[0]
    if len(candidates) > 1 and not best_exact:
        second_score = candidates[1][0]
        if second_score >= best_score - 0.05:
            ambiguous_fields = ", ".join(candidate[2] for candidate in candidates[:3])
            raise ValueError(
                f"Filter dimension_hint '{condition.dimension_hint}' is ambiguous in source "
                f"'{source_name}'. Candidates: {ambiguous_fields}."
            )
    return best_field

def _resolve_filter_conditions(
    *,
    source_name: str,
    filter_spec: FilterSpec | None,
    graph_nodes: dict[str, ColumnNode],
    records: list[dict[str, Any]],
) -> list[ResolvedFilterCondition]:
    if filter_spec is None or not filter_spec.conditions:
        return []
    resolved: list[ResolvedFilterCondition] = []
    for condition in filter_spec.conditions:
        resolved_column = _resolve_filter_condition_column(
            condition=condition,
            source_name=source_name,
            graph_nodes=graph_nodes,
            records=records,
        )
        preferred_value_type = _preferred_filter_value_type(condition)
        resolved_node = graph_nodes.get(resolved_column)
        is_numeric = (
            bool(resolved_node.is_numeric)
            if resolved_node is not None
            else _sample_numeric_field(records, resolved_column)
        )
        if preferred_value_type == "numeric" and not is_numeric:
            raise ValueError(
                f"Filter column '{resolved_column}' in source '{source_name}' is not numeric."
            )
        resolved.append(
            ResolvedFilterCondition(
                source_name=source_name,
                column=resolved_column,
                op=condition.op,
                value=condition.value,
                values=tuple(condition.values or ()),
            )
        )
    return resolved

def _row_matches_filter_condition(
    row: dict[str, Any],
    condition: ResolvedFilterCondition,
) -> bool:
    row_value = row.get(condition.column)
    if condition.op == "eq":
        return _filter_value_equals(row_value, condition.value)
    if condition.op == "in":
        return any(_filter_value_equals(row_value, candidate) for candidate in condition.values)
    if condition.op == "gt":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number > expected_number
        )
    if condition.op == "gte":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number >= expected_number
        )
    if condition.op == "lt":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number < expected_number
        )
    if condition.op == "lte":
        row_number = _filter_number_like(row_value)
        expected_number = _filter_number_like(condition.value)
        return (
            row_number is not None and expected_number is not None and row_number <= expected_number
        )
    if condition.op == "is_null":
        return _filter_value_is_nullish(row_value)
    if condition.op == "is_not_null":
        return not _filter_value_is_nullish(row_value)
    return False

def _apply_filter_conditions(
    rows: list[dict[str, Any]],
    conditions: list[ResolvedFilterCondition],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not conditions:
        return rows, []
    filtered_rows = rows
    plan: list[str] = []
    for condition in conditions:
        before = len(filtered_rows)
        filtered_rows = [
            row for row in filtered_rows if _row_matches_filter_condition(row, condition)
        ]
        value_repr = (
            list(condition.values)
            if condition.op == "in"
            else condition.value
            if condition.op not in _FILTER_NULL_OPS
            else None
        )
        if condition.op in _FILTER_NULL_OPS:
            description = f"{condition.column} {condition.op}"
        else:
            description = f"{condition.column} {condition.op} {value_repr!r}"
        plan.append(f"Filter `{description}`: {before}->{len(filtered_rows)} rows")
    return filtered_rows, plan

