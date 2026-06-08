"""Submodule _endpoints_verify.py of apps.api_server.routers.query.

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
from apps.api_server.routers.query._endpoints_schema import *  # noqa: F401, F403
# Lazy facade-routed wrappers for monkey-patched / cross-layer names.
# Tests patch apps.api_server.routers.query.X = fake; each call here
# re-reads the attribute from the facade so the patch propagates.
def _graph_nodes_from_meta(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade._graph_nodes_from_meta
    if fn is _graph_nodes_from_meta:
        from apps.api_server.routers.query._schema_graph import _graph_nodes_from_meta as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


def execute(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.execute
    if fn is execute:
        from apps.api_server.routers.query._execute_main import execute as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


class VerifyRequest(BaseModel):
    """
    LLM-produced execution plan. All names are EXACT (from schema endpoint).
    Mojo checks: source exists, columns exist, aggregation is valid for the
    column role, and join keys have sufficient confidence.
    """

    source_name: str | None = Field(default=None, description="Exact source name from schema")
    dataset_id: str | None = Field(
        default=None,
        description=(
            "Public dataset ID alias for a registered source. "
            "When provided, verification is scoped to that one registered dataset."
        ),
    )
    metric_column: str | None = Field(default=None, description="Exact column name to aggregate")
    aggregation: str | None = Field(default=None, description="sum | avg | count | max | min")
    group_column: str | None = Field(default=None, description="Exact column name for group-by")
    # Optional cross-source join
    join_source_name: str | None = Field(default=None, description="Second source name for join")
    join_columns: list[str] | None = Field(
        default=None,
        description="[local_col, remote_col] — join key pair. Omit to auto-detect.",
    )
    min_join_confidence: float = Field(
        default=0.85,
        description=(
            "Reject join paths below this confidence threshold. "
            "Default 0.85 — only statistically solid joins are accepted. "
            "Lower to 0.50 to allow weaker joins at your own risk."
        ),
    )
    mode: str = Field(
        default="assist",
        description=(
            "strict — reject invalid plans with no suggestions (enterprise enforcement). "
            "assist — reject invalid plans AND return corrective suggestions "
            "(default, LLM-friendly)."
        ),
    )
    resolved_plan: ResolvedPlan | None = Field(
        default=None,
        description="Exact plan returned by POST /v1/resolve.",
    )

class VerifyResponse(BaseModel):
    valid: bool
    errors: list[str]
    suggestions: list[str]
    resolved: dict[str, str]  # what the engine would actually use
    valid_dimensions: list[str] = []  # columns suitable for group_by
    valid_measures: list[str] = []  # columns suitable for aggregation (excludes unit_measure)
    source_behavior: str = ""  # inferred source type: transaction|snapshot|master|ledger
    latency_ms: float
    verified: bool = False
    request_id: str | None = None
    schema_revision: str | None = None
    plan_hash: str | None = None
    verification_mode: str = "assist"
    rejection_reason: str | None = None

@router.post(
    "/v1/verify",
    summary="Validate a structured query plan before execution",
    description=(
        "**LLM calls this after reading /v1/sources/schema.**\n\n"
        "Submit the exact source + column names chosen by the LLM. "
        "The engine verifies:\n"
        "- Source exists in registry\n"
        "- metric_column exists and is numeric\n"
        "- aggregation is valid for the column's role\n"
        "- group_column exists (if given)\n"
        "- join path exists with sufficient confidence (if join_source_name given)\n\n"
        "Returns `valid: true` + resolved names on success, or `valid: false` + errors + "
        "suggestions on failure. **Call /v1/execute (or /v1/query with exact-spec) only after "
        "verify returns valid.**"
    ),
    tags=["Semantic Query"],
)
async def verify_plan(
    request: Request,
    payload: VerifyRequest,
    auth: AuthContext = Depends(get_current_org),
) -> VerifyResponse:
    t0 = time.monotonic()
    org_id = str(auth["org_id"])
    request_id = getattr(request.state, "request_id", None)
    from apps.api_server.services import source_registry as _sreg

    schema_revision = _sreg.schema_revision(org_id)
    if payload.resolved_plan is not None:
        schema_revision = _resolved_plan_current_schema_revision(
            org_id=org_id,
            resolved_plan=payload.resolved_plan,
            dataset_id=payload.dataset_id,
        )
        if payload.resolved_plan.schema_revision != schema_revision:
            return VerifyResponse(
                valid=False,
                errors=[
                    "resolved_plan schema_revision no longer matches the current registry state."
                ],
                suggestions=[],
                resolved={},
                verified=False,
                request_id=request_id,
                schema_revision=schema_revision,
                plan_hash=None,
                verification_mode=payload.mode,
                rejection_reason="plan_verification_failed",
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
            )
        payload.source_name = payload.resolved_plan.source_name
        payload.metric_column = payload.resolved_plan.metric_column
        payload.aggregation = payload.resolved_plan.aggregation
        payload.group_column = payload.resolved_plan.group_column
        if payload.resolved_plan.join_path and payload.resolved_plan.join_path.edges:
            last_edge = payload.resolved_plan.join_path.edges[-1]
            payload.join_source_name = last_edge.right_source
            payload.join_columns = [last_edge.left_key, last_edge.right_key]
            payload.min_join_confidence = max(
                payload.min_join_confidence,
                round(float(payload.resolved_plan.join_path.min_path_confidence or 0.0), 3),
            )
    if not payload.source_name or not payload.metric_column or not payload.aggregation:
        raise _http_error(
            422,
            code="invalid_verify_request",
            message=(
                "verify requires source_name, metric_column, and aggregation or a resolved_plan."
            ),
            request_id=request_id,
        )
    plan_hash = _query_plan_hash(
        decision_path="verify",
        schema_revision=schema_revision,
        basis={
            "source_name": payload.source_name,
            "metric_column": payload.metric_column,
            "aggregation": payload.aggregation,
            "group_column": payload.group_column or "",
            "join_source_name": payload.join_source_name or "",
            "min_join_confidence": round(payload.min_join_confidence, 3),
            "filter": _normalize_filter_spec(
                payload.resolved_plan.filter if payload.resolved_plan else None
            ),
        },
    )
    if payload.resolved_plan is not None:
        plan_hash = _immutable_plan_hash(
            schema_revision=schema_revision,
            basis=_exact_plan_basis(
                source_name=payload.source_name,
                metric_column=payload.metric_column,
                aggregation=payload.aggregation,
                group_column=payload.group_column,
                join_path=payload.resolved_plan.join_path,
                filter_spec=payload.resolved_plan.filter,
                limit=payload.resolved_plan.limit,
                order=payload.resolved_plan.order,
                constraints=payload.resolved_plan.constraints,
            ),
        )

    # ── Verify cache — fast path for repeated identical plans ─────────────────
    # Key includes min_join_confidence + mode so different thresholds/modes
    # don't collide: a cached "valid=True" at conf=0.50 must not be returned
    # to a caller requesting conf=0.85.  We always cache the full assist
    # response; suggestions are stripped at return time when mode=strict.
    _vkey = hashlib.sha256(
        json.dumps(
            {
                "org": org_id,
                "src": payload.source_name,
                "metric": payload.metric_column,
                "agg": payload.aggregation,
                "group": payload.group_column or "",
                "join_src": payload.join_source_name or "",
                "min_conf": round(payload.min_join_confidence, 3),
                "filter": _normalize_filter_spec(
                    payload.resolved_plan.filter if payload.resolved_plan else None
                ),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:20]

    _vcached = _VERIFY_CACHE.get(_vkey)
    if _vcached:
        _vresp, _vts = _vcached
        if time.monotonic() - _vts < _VERIFY_CACHE_TTL:
            resp_data = {
                **_vresp,
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "request_id": request_id,
                "schema_revision": schema_revision,
                "plan_hash": plan_hash,
                "verification_mode": payload.mode,
            }
            if payload.mode == "strict":
                resp_data["suggestions"] = []
            return VerifyResponse(**resp_data)

    errors: list[str] = []
    suggestions: list[str] = []
    resolved: dict[str, str] = {}

    # ── 1. Source exists? ──────────────────────────────────────────────────────
    from apps.api_server.services.data_visibility import (
        dataset_visible,
        filter_visible_datasets,
    )

    registered = filter_visible_datasets(_sreg.list_sources(org_id), auth)
    src_map = {s["name"]: s for s in registered}

    def _resolve_visible_source_entry(source_name: str) -> dict[str, Any] | None:
        entry = src_map.get(source_name)
        if entry is not None:
            return entry
        fallback = _sreg.get_source_entry_by_name(org_id, source_name)
        if fallback is None or not dataset_visible(fallback, auth):
            return None
        src_map[source_name] = fallback
        return fallback

    visible_ids = {s["id"] for s in registered}

    resolved_source_entry = _resolve_visible_source_entry(payload.source_name)
    if resolved_source_entry is None:
        errors.append(f"Source '{payload.source_name}' not found in registry.")
        # Offer closest match
        close = [
            n
            for n in src_map
            if payload.source_name.lower() in n.lower() or n.lower() in payload.source_name.lower()
        ]
        if close:
            suggestions.append(f"Did you mean: {', '.join(close)}?")
        else:
            suggestions.append(f"Available sources: {', '.join(src_map.keys())}")
        return VerifyResponse(
            valid=False,
            errors=errors,
            suggestions=suggestions,
            resolved=resolved,
            verified=False,
            request_id=request_id,
            schema_revision=schema_revision,
            plan_hash=plan_hash,
            verification_mode=payload.mode,
            rejection_reason="schema_incomplete",
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    src_entry = resolved_source_entry
    src_id = src_entry["id"]
    resolved["source"] = payload.source_name
    resolved["source_name"] = payload.source_name

    # ── 2. Load schema (cache or disk) ────────────────────────────────────────
    schema_meta: dict[str, Any] = {}
    async with _CACHE_LOCK:
        cached = _SOURCE_CACHE.get(src_id)
        if cached and cached.is_fresh():
            cached.touch()
            schema_meta = json.loads(cached.parquet_schema_meta)

    if not schema_meta:
        schema_meta = _sreg.get_source_meta(org_id, src_id) or {}

    columns_meta = {c["name"]: c for c in schema_meta.get("columns", [])}
    source_nodes = _graph_nodes_from_meta(schema_meta)

    # ── 3. metric_column exists? ───────────────────────────────────────────────
    if payload.metric_column not in columns_meta:
        errors.append(
            f"Column '{payload.metric_column}' not found in source '{payload.source_name}'."
        )
        numeric_cols = [
            c["name"]
            for c in schema_meta.get("columns", [])
            if c.get("is_numeric") and c.get("role") not in ("identifier", "time", "category")
        ]
        if numeric_cols:
            suggestions.append(
                f"Numeric columns in {payload.source_name}: {', '.join(numeric_cols[:10])}"
            )
    else:
        col_meta = columns_meta[payload.metric_column]
        resolved["metric_column"] = payload.metric_column
        resolved["metric_role"] = col_meta.get("role", "unknown")

        # ── 4. Aggregation valid for role? ────────────────────────────────────
        col_role = col_meta.get("role", "metric")
        is_numeric = col_meta.get("is_numeric", False)

        if payload.aggregation == "count":
            pass
        elif not is_numeric:
            errors.append(
                f"Column '{payload.metric_column}' is not numeric (role={col_role}). "
                f"Choose a numeric column for aggregation."
            )
        elif col_role in ("identifier", "category", "text", "time"):
            errors.append(
                f"Column '{payload.metric_column}' has role={col_role} — "
                f"not suitable for {payload.aggregation}. Use a measure column."
            )
        elif payload.aggregation not in ("sum", "avg", "count", "max", "min"):
            errors.append(
                f"Unknown aggregation '{payload.aggregation}'. "
                f"Valid values: sum, avg, count, max, min."
            )
        elif payload.aggregation == "sum" and col_role == "unit_measure":
            # Hard semantic rule: unit/rate columns cannot be summed.
            # sum(UNIT_PRICE) = meaningless arithmetic sum of prices, not total revenue.
            # Look for the derived_measure column produced by a multiply formula that uses
            # this unit_measure column as an operand (e.g. EXT_PRICE = QUANTITY × UNIT_PRICE).
            all_cols = schema_meta.get("columns", [])
            col_name = payload.metric_column

            # 1. Formula-aware: find derived_measure cols whose formula multiplies this column
            formula_derived = [
                c
                for c in all_cols
                if c.get("role") == "derived_measure"
                and col_name in c.get("formula", "")
                and " x " in c.get("formula", "")
            ]
            # 2. Also find cols where this col is operand in any formula mentioning it
            related_formulas = [
                c
                for c in all_cols
                if col_name in c.get("formula", "")
                and c["name"] != col_name
                and c.get("role") in ("derived_measure", "component")
            ]
            # 3. Generic derived_measure fallback (exclude identifier-looking names)
            generic_derived = [
                c["name"]
                for c in all_cols
                if c.get("role") == "derived_measure"
                and not any(
                    kw in c["name"].lower() for kw in ("_id", "id", "no", "number", "num", "code")
                )
            ]

            if formula_derived:
                best = formula_derived[0]
                errors.append(
                    f"Column '{col_name}' is a unit/rate (role=unit_measure) — "
                    f"cannot be summed. For totals, use '{best['name']}' "
                    f"({best.get('formula', 'derived from this column')})."
                )
                suggestions.append(
                    f"Use sum('{best['name']}') for totals — formula: {best.get('formula', '')}"
                )
            elif related_formulas:
                names = [c["name"] for c in related_formulas[:3]]
                formulas = [c.get("formula", "") for c in related_formulas[:3]]
                errors.append(
                    f"Column '{col_name}' is a unit/rate (role=unit_measure) — "
                    f"cannot be summed. Related columns: {', '.join(names)}."
                )
                suggestions.append(
                    f"avg('{col_name}') is valid. Related: "
                    + "; ".join(f"{n} ({f})" for n, f in zip(names, formulas, strict=False) if f)
                )
            elif generic_derived:
                errors.append(
                    f"Column '{col_name}' is a unit/rate (role=unit_measure) — "
                    f"cannot be summed. Use avg for unit prices, or pick a derived_measure column."
                )
                suggestions.append(
                    f"avg('{col_name}') is valid for average price. "
                    f"For totals, try: {', '.join(generic_derived[:5])}"
                )
            else:
                # No derived_measure alternative exists in this source — allow sum.
                # This occurs when formula detection found no multiply relationships
                # (e.g. POS sources where EXT_PRICE classification is statistical only).
                # The column is the best available measure; sum is accepted with a note.
                resolved["aggregation"] = payload.aggregation
                resolved["note"] = (
                    f"sum('{col_name}') allowed: no derived_measure exists in "
                    f"{payload.source_name} — treating this unit_measure as the best "
                    f"available total column. Consider re-registering for richer schema detection."
                )
        else:
            resolved["aggregation"] = payload.aggregation

    if payload.resolved_plan and payload.resolved_plan.filter:
        try:
            resolved_filter_conditions = _resolve_filter_conditions(
                source_name=payload.source_name,
                filter_spec=payload.resolved_plan.filter,
                graph_nodes=source_nodes,
                records=[],
            )
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if resolved_filter_conditions:
                resolved["filter_columns"] = ", ".join(
                    condition.column for condition in resolved_filter_conditions
                )

    # ── 5. group_column exists? ────────────────────────────────────────────────
    if payload.group_column:
        # Check primary source first, then join source
        if payload.group_column in columns_meta:
            resolved["group_column"] = payload.group_column
            resolved["group_source"] = payload.source_name
        elif payload.join_source_name:
            # Will validate when we check the join source below
            resolved["group_column"] = payload.group_column
            resolved["group_source"] = payload.join_source_name  # tentative
        else:
            dim_cols = [
                c["name"]
                for c in schema_meta.get("columns", [])
                if c.get("role") in ("category", "text", "identifier")
            ]
            errors.append(
                f"Column '{payload.group_column}' not found in source '{payload.source_name}'."
            )
            if dim_cols:
                suggestions.append(
                    f"Dimension columns in {payload.source_name}: {', '.join(dim_cols[:10])}"
                )

    # ── 6. Join source + join key validation ───────────────────────────────────
    if payload.join_source_name:
        join_src_entry = _resolve_visible_source_entry(payload.join_source_name)
        if join_src_entry is None:
            errors.append(f"Join source '{payload.join_source_name}' not found in registry.")
            suggestions.append(f"Available sources: {', '.join(src_map.keys())}")
        else:
            join_src_id = join_src_entry["id"]

            # Load join source schema
            join_schema_meta: dict[str, Any] = {}
            async with _CACHE_LOCK:
                join_cached = _SOURCE_CACHE.get(join_src_id)
                if join_cached and join_cached.is_fresh():
                    join_cached.touch()
                    join_schema_meta = json.loads(join_cached.parquet_schema_meta)
            if not join_schema_meta:
                join_schema_meta = _sreg.get_source_meta(org_id, join_src_id) or {}

            join_cols_meta = {c["name"]: c for c in join_schema_meta.get("columns", [])}

            # Validate group_column in join source (if not found in primary above)
            if (
                payload.group_column
                and payload.group_column not in columns_meta
                and payload.group_column not in join_cols_meta
            ):
                errors.append(
                    f"Column '{payload.group_column}' not found in "
                    f"'{payload.source_name}' or '{payload.join_source_name}'."
                )

            # Validate explicit join_columns
            if payload.join_columns:
                if len(payload.join_columns) != 2:
                    errors.append(
                        "join_columns must have exactly 2 elements: [local_col, remote_col]"
                    )
                else:
                    local_jc, remote_jc = payload.join_columns
                    if local_jc not in columns_meta:
                        errors.append(
                            f"Join column '{local_jc}' not found in '{payload.source_name}'."
                        )
                    if remote_jc not in join_cols_meta:
                        errors.append(
                            f"Join column '{remote_jc}' not found in '{payload.join_source_name}'."
                        )
                    if not errors:
                        resolved["join_key_local"] = local_jc
                        resolved["join_key_remote"] = remote_jc
            else:
                # Auto-detect join key from registry connections
                connections = [
                    conn
                    for conn in _sreg.get_connections(org_id)
                    if conn.get("source_a") in visible_ids and conn.get("source_b") in visible_ids
                ]
                jk = _find_best_join_key(
                    payload.source_name,
                    payload.join_source_name,
                    connections,
                    min_confidence=payload.min_join_confidence,
                )
                if jk:
                    col_a, col_b, conf, card = jk
                    resolved["join_key_local"] = col_a
                    resolved["join_key_remote"] = col_b
                    resolved["join_confidence"] = f"{conf:.3f}"
                    resolved["join_cardinality"] = card
                else:
                    errors.append(
                        f"No join path with confidence ≥ {payload.min_join_confidence:.2f} "
                        f"found between '{payload.source_name}' and '{payload.join_source_name}'. "
                        f"Register both sources and ensure they share common key values."
                    )
                    # List what we do have
                    any_conns = [
                        c
                        for c in connections
                        if {c.get("source_a_name"), c.get("source_b_name")}
                        == {payload.source_name, payload.join_source_name}
                    ]
                    if any_conns:
                        best_conf = max(c.get("confidence", 0) for c in any_conns)
                        best_c = max(any_conns, key=lambda c: c.get("confidence", 0))
                        suggestions.append(
                            f"Best available join: {best_c.get('col_a')} ↔ {best_c.get('col_b')} "
                            f"(conf={best_conf:.2f}). Try lowering min_join_confidence."
                        )

    valid = len(errors) == 0

    # Populate valid_measures (excludes unit_measure — those cannot be summed),
    # valid_dimensions, and source_behavior — always returned for LLM guidance.
    valid_measures = [
        c["name"]
        for c in schema_meta.get("columns", [])
        if c.get("is_numeric")
        and c.get("role") not in ("identifier", "time", "category", "text", "unit_measure")
    ][:20]
    valid_dimensions = [
        c["name"] for c in schema_meta.get("columns", []) if c.get("role") in ("category", "text")
    ][:20]
    source_behavior = _infer_source_behavior(schema_meta)
    resolved["source_behavior"] = source_behavior

    # Store in verify cache (always cache the full assist response with suggestions).
    _vcache_payload = {
        "valid": valid,
        "verified": valid,
        "errors": errors,
        "suggestions": suggestions,
        "resolved": resolved,
        "valid_measures": valid_measures,
        "valid_dimensions": valid_dimensions,
        "source_behavior": source_behavior,
        "request_id": request_id,
        "schema_revision": schema_revision,
        "plan_hash": plan_hash,
        "verification_mode": payload.mode,
        "rejection_reason": None if valid else _classify_query_rejection("; ".join(errors)),
    }
    if len(_VERIFY_CACHE) >= _VERIFY_CACHE_MAX:
        oldest = min(_VERIFY_CACHE.items(), key=lambda x: x[1][1])
        del _VERIFY_CACHE[oldest[0]]
    _VERIFY_CACHE[_vkey] = (_vcache_payload, time.monotonic())

    resp_data = {**_vcache_payload, "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    if payload.mode == "strict":
        resp_data["suggestions"] = []
    return VerifyResponse(**resp_data)

async def _run_query_internal(
    org_id: uuid.UUID,
    source_id: str,
    metric_hint: str,
    aggregation: str = "sum",
) -> float | None:
    """
    Internal helper: run a single aggregation against a registered source by source_id.
    Returns the numeric result or None if source/column cannot be resolved.

    Used by the trigger layer to evaluate threshold conditions without going
    through the full HTTP request/response cycle.
    """

    from apps.api_server.services import source_registry as _sreg

    parquet_bytes = _sreg.get_source_parquet(str(org_id), source_id)
    if not parquet_bytes:
        return None

    try:
        import io as _io

        import pyarrow.parquet as _pq

        initialize_pyarrow_parquet_runtime()
        table = _pq.read_table(_io.BytesIO(parquet_bytes))
        df_records = table.to_pydict()

        # Find the column that best matches the metric_hint
        col_names = list(df_records.keys())
        hint_lower = metric_hint.lower().replace("_", " ").replace("-", " ")
        matched_col: str | None = None
        for col in col_names:
            if hint_lower in col.lower().replace("_", " "):
                matched_col = col
                break
        if matched_col is None:
            # Fallback: first numeric column
            for col in col_names:
                vals = [v for v in df_records[col] if v is not None]
                if vals and isinstance(vals[0], int | float):
                    matched_col = col
                    break
        if matched_col is None:
            return None

        nums = [
            float(v)
            for v in df_records[matched_col]
            if v is not None and isinstance(v, int | float)
        ]
        if not nums:
            return None

        agg = aggregation.lower()
        if agg == "sum":
            return sum(nums)
        elif agg == "avg":
            return sum(nums) / len(nums)
        elif agg == "max":
            return max(nums)
        elif agg == "min":
            return min(nums)
        elif agg == "count":
            return float(len(nums))
        return sum(nums)
    except Exception:
        return None

