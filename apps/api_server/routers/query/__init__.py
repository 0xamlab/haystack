"""
routers/query.py — Structured Query Execution Engine.

POST /v1/query

This is NOT a natural-language API. The language layer lives in the LLM
(ChatGPT, Claude, etc.) or in your application. This endpoint receives
structured intent and executes it with data-truth guarantees.

Architecture:
  LLM  →  structured intent  →  /v1/query  →  result + confidence
  LLM handles: language, ambiguity resolution, user interaction
  We  handle: schema understanding, math relationships, fast execution

Input contract (produced by the LLM):
  {
    "sources": [...],
    "metric": {"role": "derived_measure"},   // structural role
    "aggregation": "sum",                    // sum | avg | count | max | min
    "group_by": ["customer"],                // dimension hints
    "time_filter": "last_quarter",           // optional
    "limit": 5,                              // top-N
    "order": "desc"
  }

The engine resolves column meaning from three sources only:
  1. Mathematical relationships   A×B≈C detected by relation_detector
  2. Statistical structure        distribution, cardinality, entropy
  3. Structural role graph        derived purely from (1) + (2)

Universal structural roles (the only ontology):
  derived_measure  — column that equals a product or sum of other columns
  base_measure     — discrete count factor in a formula
  unit_measure     — continuous rate/price factor in a formula
  component        — additive component in a sum formula
  ratio            — bounded [0,1] column
  identifier       — high-uniqueness, low-aggregation-value
  time             — date/timestamp
  category         — low-cardinality string
  text             — medium-cardinality string
  metric           — numeric, role not yet determined
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


from apps.api_server.routers.query._state import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._state import (  # noqa: E402, F401
    _DEFAULT_JOIN_PATH_HOPS,
    _profile_records,
    _try_numeric,
    _MAX_RESOLVE_SOURCE_SCORES,
    _normalize_candidates,
    _normalize_join_path,
    _normalize_join_path_spec,
    _resolved_source_set,
    _dataset_candidate_payload,
    _planner_auth_scope_key,
    _run_cached_planner_method,
    _QUERY_RELATION_DETECT_COOLDOWN_S,
    _QUERY_RELATION_DETECT_FAILURE,
    _get_query_relation_detect_skip_reason,
    _record_query_relation_detect_failure,
    _clear_query_relation_detect_failure,
    _resolve_scope_entries,
    _PATH_CACHE_TTL,
    _CACHE_MAX_SOURCES,
    _SOURCE_CACHE,
    _CACHE_LOCK,
    _RESULT_CACHE,
    _RESULT_CACHE_MAX,
    _RESULT_CACHE_TTL,
    _RESOLVE_CACHE,
    _RESOLVE_CACHE_MAX,
    _RESOLVE_CACHE_TTL,
    _GRAPH_NODE_CACHE,
    _GRAPH_NODE_CACHE_MAX,
    _DATASET_EXACT_COLUMN_CACHE,
    _DATASET_EXACT_COLUMN_CACHE_MAX,
    _RESOLVE_BUDGET_MS,
    _ALLOW_QUERY_HINT_PLANNING_COMPAT,
    _STOP_TOKENS,
    _VERIFY_CACHE,
    _VERIFY_CACHE_MAX,
    _VERIFY_CACHE_TTL,
    _DF_CACHE,
    _DF_CACHE_MAX,
    _PLANNER_CACHE_MAX,
    _PLANNER_CACHE,
    _SOURCE_BEHAVIOR_RULES,
    _DIM_UNKNOWN,
    _DIM_COUNT,
    _DIM_CURRENCY,
    _DIM_RATE,
    _DIM_RATIO,
    _DIM_IDENTIFIER,
    _DIM_INVALID,
    _ROLE_TO_DIM,
    _DIM_TO_ROLE,
)
from apps.api_server.routers.query._cache_classes import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._cache_classes import (  # noqa: E402, F401
    _CachedSource,
    _CachedFrame,
    _CachedPlanner,
    _LoadedProfiledSource,
    _df_cache_get,
    _df_cache_put,
    _df_cache_records,
    _planner_query_confidence,
    _planner_load_bearing_validation_notes,
    _planner_join_is_execution_safe,
    _planner_metric_candidate_payloads,
    _evict_planner_lru,
    _get_registry_planner,
    _try_incremental_registry_planner_update,
    _load_profiled_source,
    _source_cache_key,
    _raise_empty_source,
    _source_cache_unique_entries,
    _evict_lru,
    _source_cache_put,
)
from apps.api_server.routers.query._schema_graph import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._schema_graph import (  # noqa: E402, F401
    _infer_source_behavior,
    _arrow_physical_types,
    _build_schema_metadata,
    _dim_propagate,
    _is_count_like,
    _col_name_signals_id,
    _looks_like_date,
    _graph_nodes_from_meta,
)
from apps.api_server.routers.query._resolvers import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._resolvers import (  # noqa: E402, F401
    _METRIC_HINT_STOPWORDS,
    _METRIC_TOKEN_CANON,
    _METRIC_CONCEPTS,
    _SOURCE_PRIOR_TOKENS,
    _metric_tokens,
    _metric_concepts,
    _metric_source_prior_bonus,
    _metric_candidate_score,
    _MIN_JOIN_CONFIDENCE,
    _find_best_join_key,
    _reverse_cardinality,
    _match_join_path_edge,
    _resolve_join_path,
    _call_mojo_source_score,
)
from apps.api_server.routers.query._execute_filters import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._execute_filters import (  # noqa: E402, F401
    _quarter_bounds,
    _parse_date,
    _num,
    _blankish_value,
    _has_populated_cell,
    _resolve_col_name,
    _FILTER_NUMERIC_OPS,
    _FILTER_NULL_OPS,
    _FILTER_DIMENSION_ROLES,
    _FILTER_TRUE_VALUES,
    _FILTER_FALSE_VALUES,
    _filter_number_like,
    _filter_boolean_like,
    _filter_value_is_nullish,
    _filter_value_equals,
    _sample_numeric_field,
    _sample_boolean_field,
    _filter_field_match_score,
    _preferred_filter_value_type,
    _resolve_filter_condition_column,
    _resolve_filter_conditions,
    _row_matches_filter_condition,
    _apply_filter_conditions,
)
from apps.api_server.routers.query._execute_main import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._signatures import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._signatures import (  # noqa: E402, F401
    _detect_relations,
    _normalize_hint_text,
    _weak_raw_text_intent,
    _stable_list,
    _exact_query_required_sources,
    _intent_signature_payload,
    _intent_signature,
    _prune_resolve_cache,
    _resolve_cache_get,
    _resolve_cache_put,
    _graph_node_cache_get,
    _graph_node_cache_put,
    _dataset_exact_column_cache_get,
    _dataset_exact_column_cache_put,
    _graph_nodes_from_cached_meta,
    _inline_schema_revision,
    _find_exact_dataset_column,
    _dataset_exact_column_lookup,
    _find_exact_dataset_column_cached,
    _get_resolve_dataset_meta,
    _resolve_single_dataset_fast_path,
    _resolve_registered_intent,
    _query_uses_legacy_planning,
    _query_execution_metadata,
    _merge_query_batch_defaults,
    _query_batch_error_from_exception,
)
from apps.api_server.routers.query._endpoints_resolve_query import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._endpoints_schema import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._endpoints_verify import *  # noqa: E402, F401, F403
from apps.api_server.routers.query._endpoints_verify import (  # noqa: E402, F401
    _run_query_internal,
)
