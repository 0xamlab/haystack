"""Submodule _cache_classes.py of apps.api_server.routers.query.

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
# Lazy facade-routed wrappers for monkey-patched / cross-layer names.
# Tests patch apps.api_server.routers.query.X = fake; each call here
# re-reads the attribute from the facade so the patch propagates.
def resolve_metric_column(*args, **kwargs):
    from apps.api_server.routers import query as _facade
    fn = _facade.resolve_metric_column
    if fn is resolve_metric_column:
        from apps.api_server.routers.query._resolvers import resolve_metric_column as _real_impl
        return _real_impl(*args, **kwargs)
    return fn(*args, **kwargs)


@dataclass
class _CachedSource:
    parquet_bytes: bytes  # DataFrame serialized as Parquet (Arrow)
    parquet_schema_meta: bytes  # Arrow schema + embedded algenta metadata (JSON)
    profile: dict[str, dict[str, Any]]  # Python-computed column stats
    mojo_profile: dict[str, dict[str, Any]]  # Mojo semantic types
    relations: list[dict[str, Any]]  # detected A×B≈C formulas
    graph_nodes: dict[str, ColumnNode]  # fully-built schema nodes
    schema_meta: dict[str, Any] = field(default_factory=dict)
    mojo_profiling_status: dict[str, Any] = field(default_factory=dict)
    content_keyed: bool = True  # True → no TTL; False → path/connection TTL
    created_at: float = field(default_factory=time.monotonic)
    last_hit: float = field(default_factory=time.monotonic)

    def is_fresh(self) -> bool:
        if self.content_keyed:
            return True  # hash-keyed: same key = same content, always fresh
        return (time.monotonic() - self.created_at) < _PATH_CACHE_TTL

    def touch(self) -> None:
        self.last_hit = time.monotonic()

@dataclass
class _CachedFrame:
    df: Any
    records: list[dict[str, Any]] | None = None

@dataclass
class _CachedPlanner:
    planner: Any
    schema_revision: str
    llm_policy: str
    auth_scope_key: tuple[str, str, str] = ("", "", "")
    created_at: float = field(default_factory=time.monotonic)
    last_hit: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_hit = time.monotonic()

@dataclass(frozen=True)
class _LoadedProfiledSource:
    profile: dict[str, dict[str, Any]]
    arrow_table: Any | None
    row_count: int
    ingest_mode: str

def _df_cache_get(src_id: str) -> _CachedFrame | None:
    return _DF_CACHE.get(src_id)

def _df_cache_put(src_id: str, df: Any, records: list[dict[str, Any]] | None = None) -> None:
    if len(_DF_CACHE) >= _DF_CACHE_MAX:
        # evict one entry (oldest insertion)
        _DF_CACHE.pop(next(iter(_DF_CACHE)))
    _DF_CACHE[src_id] = _CachedFrame(df=df, records=records)

def _df_cache_records(src_id: str, cached_frame: _CachedFrame) -> list[dict[str, Any]]:
    if cached_frame.records is None:
        cached_frame.records = cached_frame.df.to_dict(orient="records")
    return cached_frame.records

def _planner_query_confidence(plan: Any) -> float:
    values = [max(0.0, float(getattr(plan, "metric_conf", 0.0) or 0.0))]
    group_col = getattr(plan, "group_col", None)
    if group_col:
        values.append(max(0.0, float(getattr(plan, "group_conf", 0.0) or 0.0)))
    join_hops = getattr(plan, "join_hops", []) or []
    if join_hops:
        join_conf = max(
            0.0,
            float(getattr(plan, "path_confidence", 0.0) or getattr(plan, "join_conf", 0.0) or 0.0),
        )
        if _planner_join_is_execution_safe(plan):
            values.append(1.0)
        else:
            values.append(join_conf)
    return round(min(values) if values else 0.0, 3)

def _planner_load_bearing_validation_notes(plan: Any) -> list[str]:
    notes = [str(note) for note in (getattr(plan, "validation_notes", []) or []) if note]
    join_hops = getattr(plan, "join_hops", []) or []
    if not join_hops:
        return notes

    load_bearing_tokens = (
        "no join path",
        "no safe join path",
        "ambiguous multi-hop",
        "fanout",
        "plan verification failed",
    )
    return [note for note in notes if any(token in note.lower() for token in load_bearing_tokens)]

def _planner_join_is_execution_safe(plan: Any) -> bool:
    join_hops = getattr(plan, "join_hops", []) or []
    if not join_hops:
        return True
    if getattr(plan, "error", None):
        return False
    return not _planner_load_bearing_validation_notes(plan)

def _planner_metric_candidate_payloads(
    *,
    plan: Any,
    graph: SchemaGraph,
    metric_hint: str,
    target_role: str,
    preferred_source: str | None,
) -> list[dict[str, Any]]:
    hint_tokens = set(re.findall(r"[a-z0-9]+", metric_hint.lower()))
    _cand_src, _cand_col, _cand_conf, metric_candidate_payloads = resolve_metric_column(
        target_role,
        hint_tokens,
        graph,
        preferred_source,
    )

    metric_src = getattr(plan, "metric_src", "") or ""
    metric_col = getattr(plan, "metric_col", "") or ""
    metric_conf = round(float(getattr(plan, "metric_conf", 0.0) or 0.0), 3)
    metric_node = graph.get(metric_src, {}).get(metric_col) if metric_src and metric_col else None
    selected_payload: dict[str, Any] | None = None
    if metric_node is not None:
        selected_payload = {
            "source": metric_src,
            "column": metric_col,
            "role": metric_node.role,
            "magnitude": metric_node.magnitude_class,
            "formula": metric_node.formula,
            "confidence": metric_conf,
            "score_components": {"planner_confidence": metric_conf},
            "notes": ["planner-selected"],
        }

    authoritative_prefixes = (
        "[query_hints/registry]",
        "[vector_resolver]",
        "[column_match] SELECTED",
    )
    authoritative_metric_selection = bool(
        selected_payload is not None
        and metric_conf >= _DECISION_AUTO_ACCEPT_CONFIDENCE
        and any(str(step).startswith(authoritative_prefixes) for step in getattr(plan, "steps", []))
    )
    if authoritative_metric_selection:
        if selected_payload is not None:
            selected_payload["notes"].append("planner-authoritative-selection")
            return [selected_payload]

    if not metric_candidate_payloads and selected_payload is not None:
        return [selected_payload]
    return metric_candidate_payloads

def _evict_planner_lru() -> None:
    from apps.api_server.routers.query_registry_planner import evict_planner_lru

    evict_planner_lru(
        planner_cache=_PLANNER_CACHE,
        planner_cache_max=_PLANNER_CACHE_MAX,
    )

async def _get_registry_planner(
    org_id: str,
    *,
    llm_policy: str = "never",
    auth: AuthContext | None,  # required (no default): forces every caller to decide scope —
    # passing auth scopes datasets to the caller's workspace; explicit None = trusted org-wide
    # internal planning. Prevents a future request handler from silently leaking org-wide data.
    visible_entries: list[dict[str, Any]] | None = None,
) -> tuple[Any, bool, str]:
    return await _get_registry_planner_impl(
        org_id,
        llm_policy=llm_policy,
        auth=auth,
        visible_entries=visible_entries,
        cache_lock=_CACHE_LOCK,
        planner_cache=_PLANNER_CACHE,
        planner_cache_max=_PLANNER_CACHE_MAX,
        cached_planner_cls=_CachedPlanner,
    )

async def _try_incremental_registry_planner_update(
    org_id: str,
    *,
    llm_policy: str,
    auth: AuthContext | None,
    source_id: str,
    source_name: str,
    schema_meta: dict[str, Any],
    source_schema_revision: str,
    parquet_path: Path | None,
    new_connections: list[dict[str, Any]],
) -> tuple[bool, str]:
    return await _try_incremental_registry_planner_update_impl(
        org_id,
        llm_policy=llm_policy,
        auth=auth,
        source_id=source_id,
        source_name=source_name,
        schema_meta=schema_meta,
        source_schema_revision=source_schema_revision,
        parquet_path=parquet_path,
        new_connections=new_connections,
        cache_lock=_CACHE_LOCK,
        planner_cache=_PLANNER_CACHE,
        planner_cache_max=_PLANNER_CACHE_MAX,
    )

async def _load_profiled_source(
    src: DataSource,
    *,
    org_id: str | None = None,
) -> _LoadedProfiledSource:
    """
    Prefer a native columnar path when the source proves it is suitable.

    This keeps Arrow/parquet-friendly inputs on the zero-copy-ish path while
    preserving the tolerant one-pass row fallback for messy CSV/JSON/API data.
    """
    table = await _load_source_table(src, org_id=org_id)
    if table is not None:
        row_count = int(getattr(table, "num_rows", 0) or 0)
        if row_count > 0:
            return _LoadedProfiledSource(
                profile=_profile_arrow_table(table),
                arrow_table=table,
                row_count=row_count,
                ingest_mode="columnar",
            )

    records = await _load_source(src, org_id=org_id)
    if not records:
        return _LoadedProfiledSource(
            profile={},
            arrow_table=None,
            row_count=0,
            ingest_mode="rows",
        )

    profile, arrow_table = _profile_records_and_arrow(records)
    return _LoadedProfiledSource(
        profile=profile,
        arrow_table=arrow_table,
        row_count=len(records),
        ingest_mode="rows",
    )

def _source_cache_key(
    src: DataSource,
    records: list[dict[str, Any]] | None = None,
) -> tuple[str, bool]:
    """
    Returns (cache_key, content_keyed).
    content_keyed=True  → hash of actual bytes; permanent, no TTL.
    content_keyed=False → url/connection identity; short TTL since content can change.
    """
    registered_id = src.dataset_id or src.source_id
    if registered_id:
        # Registry source — cache key IS the source_id.
        # Data is immutable once registered, so the id is content-keyed.
        return registered_id, True
    if src.csv:
        return hashlib.sha256(src.csv.encode()).hexdigest()[:32], True
    if src.json_str:
        return hashlib.sha256(src.json_str.encode()).hexdigest()[:32], True
    if src.excel_b64:
        return hashlib.sha256(src.excel_b64.encode()).hexdigest()[:32], True
    if src.parquet_b64:
        return hashlib.sha256(src.parquet_b64.encode()).hexdigest()[:32], True
    if records is not None:
        return hashlib.sha256(
            json.dumps(records, sort_keys=True, default=str).encode()
        ).hexdigest()[:32], True
    # File / URL / connection — keyed by identity, not content
    src_type = "url" if src.url else ("connection" if src.connection else "named")
    connection_fingerprint = (
        json.dumps(src.connection, sort_keys=True, default=str) if src.connection else ""
    )
    if src_type == "named":
        raw = f"{src_type}:{src.name}"
    else:
        raw = f"{src_type}:{src.url or ''}:{connection_fingerprint}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32], False

def _raise_empty_source(source_name: str) -> None:
    raise HTTPException(
        status_code=400,
        detail={
            "error": {
                "code": "empty_source",
                "message": f"Source '{source_name}' returned no records.",
            }
        },
    )

def _source_cache_unique_entries() -> list[tuple[_CachedSource, list[str]]]:
    grouped: dict[int, tuple[_CachedSource, list[str]]] = {}
    for key, entry in _SOURCE_CACHE.items():
        cached = grouped.get(id(entry))
        if cached is None:
            grouped[id(entry)] = (entry, [key])
            continue
        cached[1].append(key)
    return list(grouped.values())

def _evict_lru(exempt_entry: _CachedSource | None = None) -> None:
    """Remove least-recently-used cached source objects when the unique-entry cache is full."""
    # Read _CACHE_MAX_SOURCES via the facade so tests that monkey-patch
    # apps.api_server.routers.query._CACHE_MAX_SOURCES are honored.
    from apps.api_server.routers import query as _facade
    while True:
        unique_entries = _source_cache_unique_entries()
        if len(unique_entries) <= _facade._CACHE_MAX_SOURCES:
            return
        evictable = [
            (entry, keys)
            for entry, keys in unique_entries
            if exempt_entry is None or entry is not exempt_entry
        ]
        if not evictable:
            return
        oldest_entry, oldest_keys = min(evictable, key=lambda item: item[0].last_hit)
        for key in oldest_keys:
            _SOURCE_CACHE.pop(key, None)
        logger.debug(
            "source_cache_evict",
            key=oldest_keys[0][:8],
            alias_count=len(oldest_keys),
            last_hit=oldest_entry.last_hit,
        )

def _source_cache_put(entry: _CachedSource, *keys: str) -> None:
    unique_keys = [key for key in dict.fromkeys(keys) if key]
    if not unique_keys:
        raise ValueError("source cache insert requires at least one key")
    for key in unique_keys:
        _SOURCE_CACHE[key] = entry
    _evict_lru(exempt_entry=entry)

