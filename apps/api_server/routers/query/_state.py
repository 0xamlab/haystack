"""Submodule _state.py of apps.api_server.routers.query.

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


logger = structlog.get_logger(__name__)

MetricSpec = _MetricSpec

QueryPayload = _QueryPayload

_DEFAULT_JOIN_PATH_HOPS = _QUERY_CONTRACT_DEFAULT_JOIN_PATH_HOPS

_profile_records = _query_profile_records

_try_numeric = _query_try_numeric

_MAX_RESOLVE_SOURCE_SCORES = _QUERY_RESPONSE_MAX_RESOLVE_SOURCE_SCORES

_normalize_candidates = _query_normalize_candidates

_normalize_join_path = _query_normalize_join_path

_normalize_join_path_spec = _query_normalize_join_path_spec

_resolved_source_set = _query_resolved_source_set

_dataset_candidate_payload = _query_dataset_candidate_payload

_planner_auth_scope_key = _query_planner_auth_scope_key

_run_cached_planner_method = _query_run_cached_planner_method

_QUERY_RELATION_DETECT_COOLDOWN_S = 60.0

_QUERY_RELATION_DETECT_FAILURE: tuple[float, str] | None = None

def _get_query_relation_detect_skip_reason() -> str | None:
    return _get_optional_mojo_engine_skip_reason("relation_detect")

def _record_query_relation_detect_failure(reason: BaseException | str) -> None:
    _record_optional_mojo_engine_failure("relation_detect", reason)

def _clear_query_relation_detect_failure() -> None:
    global _QUERY_RELATION_DETECT_FAILURE

    _QUERY_RELATION_DETECT_FAILURE = None
    _clear_optional_mojo_engine_failure("relation_detect")

def _resolve_scope_entries(
    *,
    org_id: str,
    auth: AuthContext,
    dataset_id: str | None,
    allow_org_scope: bool,
    request_id: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    return _query_resolve_scope_entries(
        org_id=org_id,
        auth=auth,
        dataset_id=dataset_id,
        allow_org_scope=allow_org_scope,
        request_id=request_id,
        http_error_fn=_http_error,
    )

router = APIRouter(tags=["Semantic Query"])

_PATH_CACHE_TTL = 1800  # 30 min for file/url/connection sources (content can change)

_CACHE_MAX_SOURCES = int(
    os.environ.get("ALGENTA_SOURCE_CACHE_MAX_SOURCES", "96")
)  # keep medium-size multi-source corpora hot

_SOURCE_CACHE: dict[str, _CachedSource] = {}  # source/cache alias key → entry

_CACHE_LOCK = asyncio.Lock()

_RESULT_CACHE: dict[
    str, dict[str, Any]
] = {}  # plan_hash → {"result", "result_type", "row_count", "confidence", "explanation"}

_RESULT_CACHE_MAX = 200

_RESULT_CACHE_TTL = 3600.0  # 1 hour

_RESOLVE_CACHE: dict[str, dict[str, Any]] = {}

_RESOLVE_CACHE_MAX = 500

_RESOLVE_CACHE_TTL = 3600.0  # 1 hour

_GRAPH_NODE_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}

_GRAPH_NODE_CACHE_MAX = 256

_DATASET_EXACT_COLUMN_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}

_DATASET_EXACT_COLUMN_CACHE_MAX = 256

_RESOLVE_BUDGET_MS = 500.0

_ALLOW_QUERY_HINT_PLANNING_COMPAT = True

_STOP_TOKENS = frozenset(
    {
        "a",
        "an",
        "and",
        "by",
        "for",
        "from",
        "in",
        "of",
        "on",
        "the",
        "to",
        "with",
    }
)

_VERIFY_CACHE: dict[str, tuple[dict[str, Any], float]] = {}  # plan_key → (response_dict, timestamp)

_VERIFY_CACHE_MAX = 500

_VERIFY_CACHE_TTL = 300.0  # 5 minutes (schema changes are rare; 5 min is safe)

_DF_CACHE: dict[str, _CachedFrame] = {}

_DF_CACHE_MAX = 20  # keep top-20 most-accessed DataFrames hot

_PLANNER_CACHE_MAX = 24  # per-org registry planners

_PLANNER_CACHE: dict[tuple[str, str, str], _CachedPlanner] = {}

_SOURCE_BEHAVIOR_RULES: dict[str, dict[str, str]] = {
    # source_type → description + allowed query intents
    "transaction": {
        "description": "Event-based rows (orders, POS, bookings). Supports revenue/volume queries.",
        "valid_intents": "revenue, bookings, orders, sales, quantity_sold",
    },
    "snapshot": {
        "description": (
            "Point-in-time state (inventory, headcount). Supports on-hand/balance queries."
        ),
        "valid_intents": "on_hand, balance, inventory, headcount, current",
    },
    "master": {
        "description": (
            "Reference data (employees, products, customers). Supports lookup/dimension queries."
        ),
        "valid_intents": "lookup, dimension, attributes",
    },
    "ledger": {
        "description": "Accounting entries (expenses, GL). Supports cost/spend queries.",
        "valid_intents": "cost, spend, expense, debit, credit",
    },
}

_DIM_UNKNOWN = 0

_DIM_COUNT = 1  # non-negative integers       [unit]

_DIM_CURRENCY = 2  # monetary total              [$]

_DIM_RATE = 3  # per-unit value              [$/unit]

_DIM_RATIO = 4  # proportion 0–1 or 0–100     [%]

_DIM_IDENTIFIER = 5  # surrogate key, no arithmetic

_DIM_INVALID = -1

_ROLE_TO_DIM = {
    DERIVED_MEASURE: _DIM_CURRENCY,
    BASE_MEASURE: _DIM_COUNT,
    UNIT_MEASURE: _DIM_RATE,
    RATIO: _DIM_RATIO,
    IDENTIFIER: _DIM_IDENTIFIER,
    COMPONENT: _DIM_UNKNOWN,  # component = additive piece, context-dependent
    METRIC: _DIM_UNKNOWN,
    TIME: _DIM_UNKNOWN,
    CATEGORY: _DIM_UNKNOWN,
    TEXT: _DIM_UNKNOWN,
}

_DIM_TO_ROLE = {
    _DIM_CURRENCY: DERIVED_MEASURE,
    _DIM_COUNT: BASE_MEASURE,
    _DIM_RATE: UNIT_MEASURE,
    _DIM_RATIO: RATIO,
    _DIM_IDENTIFIER: IDENTIFIER,
    _DIM_UNKNOWN: METRIC,
    _DIM_INVALID: METRIC,
}

