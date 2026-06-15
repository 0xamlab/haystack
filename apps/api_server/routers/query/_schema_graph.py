"""Submodule _schema_graph.py of apps.api_server.routers.query.

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
def _infer_source_behavior(schema_meta: dict[str, Any]) -> str:
    """
    Infer source_type from structural roles in schema_meta.

    Priority order (highest wins):
    1. Strong snapshot signals (quantity/inventory/on_hand + base_measure) → snapshot
    2. Strong transaction signals (order/invoice/ship + time cols) → transaction
    3. Hard ledger signals (debit/credit/gl/journal — NOT accrl alone) → ledger
    4. time + multiplicative formula → transaction
    5. High category ratio, no time → master
    6. Any time columns → transaction
    7. Default → snapshot
    """
    cols = schema_meta.get("columns", [])
    roles = schema_meta.get("roles_summary", {})
    formulas = schema_meta.get("formulas", [])

    n_time = roles.get("time", 0)
    n_derived = roles.get("derived_measure", 0)
    n_component = roles.get("component", 0)
    n_category = roles.get("category", 0)
    n_base = roles.get("base_measure", 0)
    n_text = roles.get("text", 0)
    n_total = max(len(cols), 1)

    col_names_lower = [c.get("name", "").lower() for c in cols]

    # Multiplicative formulas (A × B ≈ C) → transaction signal
    has_mul_formula = any(
        "x" in f.get("formula", "").lower() or "×" in f.get("formula", "") for f in formulas
    )

    # Strong snapshot signals: inventory/on_hand/quantity-dominant data
    strong_snapshot_kws = (
        "on_hand",
        "inventory",
        "in_stock",
        "balance",
        "avail",
        "oh_",
        "qty_on",
        "units_on",
        "warehouse",
        "bin_",
    )
    has_strong_snapshot = any(any(kw in n for kw in strong_snapshot_kws) for n in col_names_lower)
    # Also snapshot if: lots of base_measure + quantity in names + few time cols
    quantity_kws = ("quantity", "qty", "count_")
    has_quantity_name = any(any(kw in n for kw in quantity_kws) for n in col_names_lower)
    is_snapshot_structure = (
        n_base >= 1 and has_quantity_name and n_derived >= 1 and n_component >= 1
    )

    # Strong transaction signals: event-row markers
    transaction_kws = (
        "order_number",
        "order_id",
        "invoice",
        "ship_to",
        "ship_date",
        "ship_year",
        "ship_month",
        "booking",
        "pos_",
        "receipt",
        "sale_date",
        "transaction_id",
        "txn_",
    )
    has_strong_transaction = any(any(kw in n for kw in transaction_kws) for n in col_names_lower)

    # Hard ledger signals (accounting entries — debit/credit/GL specific)
    hard_ledger_kws = (
        "debit",
        "credit",
        "gl_",
        "journal",
        "ledger",
        "ap_",
        "ar_",
        "payable",
        "receivable",
    )
    # Soft ledger: accrual/expense keywords (may appear in transactional POS data too)
    soft_ledger_kws = ("accrual", "accrl", "expense", "cost_center")
    has_hard_ledger = any(any(kw in n for kw in hard_ledger_kws) for n in col_names_lower)
    has_soft_ledger = any(any(kw in n for kw in soft_ledger_kws) for n in col_names_lower)

    # Master signals: mostly categorical, few time columns, no formulas
    category_ratio = (n_category + n_text) / n_total

    # ── Priority order ────────────────────────────────────────────────────────
    # 1. Strong snapshot overrides everything (even if accrl present)
    if has_strong_snapshot or is_snapshot_structure:
        return "snapshot"
    # 2. Hard ledger signals (not just accrual)
    if has_hard_ledger:
        return "ledger"
    # 3. Strong transaction signals
    if has_strong_transaction and n_time >= 1:
        return "transaction"
    # 4. Soft ledger only if no transaction signals
    if has_soft_ledger and not has_strong_transaction:
        return "ledger"
    # 5. time + multiplicative formula → transaction
    if n_time >= 1 and has_mul_formula:
        return "transaction"
    # 6. master: high category ratio, no time
    if category_ratio > 0.60 and n_time == 0:
        return "master"
    # 7. any time columns → transaction
    if n_time >= 1:
        return "transaction"
    return "snapshot"

def _arrow_physical_types(arrow_schema: Any | None) -> dict[str, str]:
    if arrow_schema is None:
        return {}
    physical_types: dict[str, str] = {}
    try:
        for field in arrow_schema:
            name = str(getattr(field, "name", "") or "")
            if not name:
                continue
            physical_types[name] = str(getattr(field, "type", "") or "")
    except Exception:
        return {}
    return physical_types

def _build_schema_metadata(
    src_name: str,
    graph_nodes: dict[str, ColumnNode],
    relations: list[dict[str, Any]],
    profile: dict[str, dict[str, Any]],
    profiling_status: dict[str, Any] | None = None,
    physical_types: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build the Codna schema metadata dict embedded into the Parquet file.
    This is what the LLM reads to understand the data before querying.

    Structure:
      source        — source name
      row_count     — number of rows profiled
      columns       — per-column: role, formula, semantic_type, cardinality,
                      magnitude, mean, std, sample_values (3 examples)
      formulas      — list of detected A×B≈C relationships
      roles_summary — counts per role (quick overview for the LLM)
      query_hints   — structured hints the LLM should use in POST /v1/query
    """
    columns: list[dict[str, Any]] = []
    role_counts: dict[str, int] = {}
    planner_profile: dict[str, dict[str, Any]] = {}

    ordered_columns: list[str]
    if physical_types:
        seen_columns: set[str] = set()
        ordered_columns = []
        for col in physical_types:
            if col in graph_nodes and col not in seen_columns:
                ordered_columns.append(col)
                seen_columns.add(col)
        for col in sorted(graph_nodes):
            if col not in seen_columns:
                ordered_columns.append(col)
    else:
        ordered_columns = sorted(graph_nodes)

    for col in ordered_columns:
        node = graph_nodes[col]
        role_counts[node.role] = role_counts.get(node.role, 0) + 1
        prof = profile.get(col, {})
        planner_profile[col] = {
            "is_numeric": bool(prof.get("is_numeric", node.is_numeric)),
            "strings": [str(v) for v in (prof.get("strings") or [])[:50]],
            "sample_values": [str(v) for v in (prof.get("sample_values") or [])[:50]],
            "unique_count": int(prof.get("unique_count", 0) or 0),
            "total_count": int(prof.get("total_count", 0) or 0),
            "fill_rate": round(
                float(prof.get("fill_rate", node.fill_rate) or node.fill_rate or 0.0), 4
            ),
            "mean": round(float(prof.get("mean", node.mean) or 0.0), 4),
            "std": round(float(prof.get("std", node.std) or 0.0), 4),
        }
        col_meta: dict[str, Any] = {
            "name": col,
            "role": node.role,
            "is_numeric": node.is_numeric,
            "semantic_type": node.semantic_type or None,
        }
        physical_type = str((physical_types or {}).get(col, "") or "").strip()
        if physical_type:
            col_meta["physical_type"] = physical_type
        if node.formula:
            col_meta["formula"] = node.formula
        col_meta["fill_rate"] = round(prof.get("fill_rate", 1.0), 4)
        if node.is_numeric:
            col_meta["magnitude"] = node.magnitude_class
            if node.mean:
                col_meta["mean"] = round(node.mean, 4)
        if not node.is_numeric:
            col_meta["cardinality"] = prof.get("unique_count", 0)
        # 5 representative non-empty values from anywhere in the dataset
        samples = (prof.get("sample_values") or [])[:5]
        if samples:
            col_meta["samples"] = [str(s) for s in samples]
        columns.append(col_meta)

    # Build query_hints: one entry per role, best column first (highest fill_rate).
    # The LLM uses this to pick metric.role — it does NOT need to know column names.
    role_labels = {
        "derived_measure": "total / aggregate value (revenue, spend, total cost...)",
        "base_measure": "count / quantity / discrete amount",
        "unit_measure": "rate / price / per-unit value",
        "ratio": "fraction or percentage (0–1 range)",
        "metric": "other numeric — specify role or let engine decide",
    }
    # Group columns by role, sorted by fill_rate desc within each group
    from collections import defaultdict

    role_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for col_meta in columns:
        role = col_meta["role"]
        if role in role_labels:
            role_groups[role].append(col_meta)
    for role in role_groups:
        role_groups[role].sort(key=lambda c: c.get("fill_rate", 0), reverse=True)

    hints: list[dict[str, Any]] = []
    # Emit in priority order: formula-detected roles first, then statistical
    for role in ("derived_measure", "unit_measure", "base_measure", "ratio", "metric"):
        cols = role_groups.get(role, [])
        if not cols:
            continue
        hint: dict[str, Any] = {
            "metric_role": role,
            "description": role_labels[role],
            "columns": [
                {
                    "name": c["name"],
                    "fill_rate": c.get("fill_rate", 1.0),
                    "samples": c.get("samples", []),
                    **({"formula": c["formula"]} if c.get("formula") else {}),
                    **({"mean": c["mean"]} if c.get("mean") else {}),
                }
                for c in cols
            ],
        }
        hints.append(hint)

    return {
        "source": src_name,
        "columns": columns,
        "formulas": [
            {"formula": r.get("formula"), "confidence": r.get("confidence")} for r in relations
        ],
        "roles_summary": role_counts,
        "query_hints": hints,
        "planner_profile": planner_profile,
        "mojo_profiling_status": profiling_status
        or _mojo_profiling_disabled_status("column_profile", "not_recorded"),
    }

def _dim_propagate(op: str, dim_a: int, dim_b: int) -> int:
    """
    Dimensional algebra: (dim_a  op  dim_b) → result dimension.

    Returns _DIM_INVALID when the combination is dimensionally inconsistent.
    Returns _DIM_UNKNOWN when context is insufficient.

    Mirrors dimensions.mojo::propagate exactly.
    """
    if dim_a == _DIM_IDENTIFIER or dim_b == _DIM_IDENTIFIER:
        return _DIM_INVALID

    op = op.lower().strip()

    # ── Multiply ──────────────────────────────────────────────────────────────
    if op in ("multiply", "mul", "*", "x", "×"):
        a, b = min(dim_a, dim_b), max(dim_a, dim_b)  # commutative normalise

        if (a, b) == (_DIM_COUNT, _DIM_RATE):
            return _DIM_CURRENCY
        if (a, b) == (_DIM_COUNT, _DIM_CURRENCY):
            return _DIM_CURRENCY
        if (a, b) == (_DIM_COUNT, _DIM_RATIO):
            return _DIM_COUNT
        if (a, b) == (_DIM_CURRENCY, _DIM_RATIO):
            return _DIM_CURRENCY
        if (a, b) == (_DIM_RATE, _DIM_RATIO):
            return _DIM_RATE
        if (a, b) == (_DIM_RATE, _DIM_RATE):
            return _DIM_INVALID
        if (a, b) == (_DIM_CURRENCY, _DIM_CURRENCY):
            return _DIM_INVALID
        if (a, b) == (_DIM_RATIO, _DIM_RATIO):
            return _DIM_RATIO
        return _DIM_UNKNOWN

    # ── Add / Subtract ────────────────────────────────────────────────────────
    if op in ("add", "+", "subtract", "-"):
        if dim_a == dim_b:
            return dim_a  # same dimension always valid

        a, b = min(dim_a, dim_b), max(dim_a, dim_b)

        # All cross-dimension additions except same-dim are INVALID
        if _DIM_UNKNOWN not in (a, b):
            return _DIM_INVALID  # Currency+Rate, Rate+Ratio, Currency+Count, etc.

        return _DIM_UNKNOWN

    # ── Divide ────────────────────────────────────────────────────────────────
    if op in ("divide", "/"):
        if dim_a == _DIM_CURRENCY and dim_b == _DIM_COUNT:
            return _DIM_RATE
        if dim_a == _DIM_CURRENCY and dim_b == _DIM_CURRENCY:
            return _DIM_RATIO
        if dim_a == _DIM_COUNT and dim_b == _DIM_COUNT:
            return _DIM_RATIO
        if dim_a == _DIM_RATE and dim_b == _DIM_RATE:
            return _DIM_RATIO
        if dim_a == _DIM_RATE and dim_b == _DIM_COUNT:
            return _DIM_RATE
        return _DIM_UNKNOWN

    return _DIM_UNKNOWN

@dataclass
class ColumnNode:
    name: str
    role: str = METRIC
    formula: str | None = None
    mean: float = 0.0
    std: float = 0.0
    is_numeric: bool = False
    magnitude_class: str = "medium"  # large | medium | small
    semantic_type: str = ""
    confidence: float = 0.0  # role assignment confidence
    fill_rate: float = 1.0  # fraction of non-empty values (0–1)

SchemaGraph = dict[str, dict[str, ColumnNode]]  # source → col → node

def _is_count_like(nums: list[float]) -> bool:
    """
    True if the column looks like a discrete count: non-negative integers.
    No upper bound cap — counts can be arbitrarily large (e.g. population, inventory).
    Only the integer + non-negative properties are required.
    """
    if not nums:
        return False
    sample = nums[:50]
    return all(v >= 0 for v in sample) and all(abs(v - round(v)) < 1e-6 for v in sample)

def _col_name_signals_id(name: str) -> bool:
    n = name.lower().strip()
    # Exact short names that are always identifiers (plain "id", "no", etc.)
    if n in ("id", "no", "num", "nbr"):
        return True
    # Suffix/substring patterns: "bltitm_id", "vendor_no", "part_number",
    # "order_code", "row_wid", "serial_key", "po.vendno", "emp_seq"
    return any(
        kw in n
        for kw in (
            "_id",
            "_no",
            ".id",
            ".no",
            "number",
            "code",
            "ref",
            " id",
            "key",
            "_wid",
            "_seq",
            "_idx",
            "_nbr",
            "vendno",
            "vend_",
        )
    )

def _looks_like_date(s: str) -> bool:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            datetime.strptime(str(s).strip(), fmt)
            return True
        except ValueError:
            pass
    return False

def build_schema_graph(
    profiles: dict[str, dict[str, dict[str, Any]]],
    mojo_profiles: dict[str, dict[str, Any]],
    relations_by_source: dict[str, list[dict[str, Any]]],
) -> SchemaGraph:
    """
    Build structural graph for all sources.
    Role assignment: math relationships first, statistical patterns second.
    Column names are NEVER used for role assignment — only for output.
    """
    graph: SchemaGraph = {}

    for src_name, profile in profiles.items():
        nodes: dict[str, ColumnNode] = {}

        for col, info in profile.items():
            mp = mojo_profiles.get(src_name, {}).get(col, {})
            node = ColumnNode(
                name=col,
                is_numeric=info.get("is_numeric", False),
                mean=info.get("mean", 0.0),
                std=info.get("std", 0.0),
                semantic_type=mp.get("semantic_type", ""),
                fill_rate=info.get("fill_rate", 1.0),
            )
            nodes[col] = node

        # ── Step 1: Formula relationships — dimensional algebra ─────────────
        #
        # Dimensions are inferred from numeric samples (no column names used).
        # Propagation rules mirror dimensions.mojo exactly.
        rels = relations_by_source.get(src_name, [])
        for rel in rels:
            result_col = rel.get("field_result", "")
            a_col = rel.get("field_a", "")
            b_col = rel.get("field_b", "")
            op = rel.get("operation", "")
            rel_conf = float(rel.get("confidence", 0.0))

            if result_col in nodes:
                nodes[result_col].formula = rel.get("formula")
                nodes[result_col].confidence = rel_conf

            pa = profile.get(a_col, {})
            pb = profile.get(b_col, {})

            # Infer operand dimensions from numeric samples (data-driven, no names)
            a_count = _is_count_like(pa.get("numeric", []))
            b_count = _is_count_like(pb.get("numeric", []))
            a_ratio = (
                not a_count
                and pa.get("numeric")
                and all(0.0 <= v <= 1.001 for v in pa["numeric"][:50])
            )
            b_ratio = (
                not b_count
                and pb.get("numeric")
                and all(0.0 <= v <= 1.001 for v in pb["numeric"][:50])
            )

            dim_a = _DIM_COUNT if a_count else _DIM_RATIO if a_ratio else _DIM_UNKNOWN
            dim_b = _DIM_COUNT if b_count else _DIM_RATIO if b_ratio else _DIM_UNKNOWN

            # For multiply: if one operand is Count and the other is not, the
            # non-count one must be Rate (that's how quantity × price works).
            # Assign operand roles first, then propagate for the result.
            if op == "multiply":
                if a_count and not b_count:
                    if a_col in nodes and nodes[a_col].role == METRIC:
                        nodes[a_col].role = BASE_MEASURE
                        nodes[a_col].confidence = rel_conf
                    if b_col in nodes and nodes[b_col].role == METRIC:
                        nodes[b_col].role = UNIT_MEASURE
                        nodes[b_col].confidence = rel_conf
                    dim_b = _DIM_RATE  # now known: the non-count factor is a rate
                elif b_count and not a_count:
                    if b_col in nodes and nodes[b_col].role == METRIC:
                        nodes[b_col].role = BASE_MEASURE
                        nodes[b_col].confidence = rel_conf
                    if a_col in nodes and nodes[a_col].role == METRIC:
                        nodes[a_col].role = UNIT_MEASURE
                        nodes[a_col].confidence = rel_conf
                    dim_a = _DIM_RATE
                else:
                    # Both non-integer or both integer — use magnitude to guess
                    ma = pa.get("mean", 0.0)
                    mb = pb.get("mean", 0.0)
                    if a_col in nodes and nodes[a_col].role == METRIC:
                        nodes[a_col].role = UNIT_MEASURE if ma <= mb else BASE_MEASURE
                        nodes[a_col].confidence = rel_conf
                    if b_col in nodes and nodes[b_col].role == METRIC:
                        nodes[b_col].role = BASE_MEASURE if ma <= mb else UNIT_MEASURE
                        nodes[b_col].confidence = rel_conf
                    dim_a = _DIM_RATE if ma <= mb else _DIM_COUNT
                    dim_b = _DIM_COUNT if ma <= mb else _DIM_RATE

            elif op == "add":
                # Operands of an additive formula become components
                for col in (a_col, b_col):
                    if col in nodes and nodes[col].role == METRIC:
                        nodes[col].role = COMPONENT
                        nodes[col].confidence = rel_conf

            # Propagate dimensions → determine result role.
            #
            # Preferred path: use the role_result field emitted by Mojo's
            # relation_detector (which already ran dimensions.mojo at detection time).
            # This is the single-source-of-truth path — no re-implementation.
            #
            # Fallback path: _dim_propagate() when running against an older binary
            # that does not yet emit role_result (forward-compatible migration).
            mojo_role = rel.get("role_result")  # present only in new binary

            # Strict derived_measure rule:
            #   derived_measure = proven by MULTIPLY (A × B = C) only.
            #   Add formulas produce many numerical coincidences in wide datasets —
            #   their result is at most "component", never "derived_measure".
            #   This prevents large-integer IDs (BLTITM_ID = PARENT_BLTITM_ID + NBV)
            #   from being promoted to derived_measure via false-positive detections.
            is_multiply = op == "multiply"

            if result_col in nodes:
                if mojo_role:
                    # ── Mojo is the authority — but enforce the strict rule ───
                    if not is_multiply and mojo_role == "derived_measure":
                        mojo_role = "component"
                    nodes[result_col].role = mojo_role
                else:
                    # ── Python fallback (old binary) ─────────────────────────
                    result_dim = _dim_propagate(op, dim_a, dim_b)
                    if result_dim == _DIM_CURRENCY and is_multiply:
                        nodes[result_col].role = DERIVED_MEASURE
                    elif result_dim == _DIM_RATE:
                        nodes[result_col].role = UNIT_MEASURE
                    elif result_dim == _DIM_COUNT:
                        nodes[result_col].role = BASE_MEASURE
                    elif result_dim == _DIM_RATIO:
                        nodes[result_col].role = RATIO
                    elif result_dim == _DIM_INVALID:
                        nodes[result_col].role = METRIC
                    else:
                        # DIM_UNKNOWN fallback
                        if is_multiply:
                            nodes[result_col].role = DERIVED_MEASURE  # could be currency
                        elif not a_count and not b_count:
                            nodes[result_col].role = UNIT_MEASURE  # additive continuous
                        else:
                            nodes[result_col].role = COMPONENT  # additive integer

        # ── Step 2: Statistical roles for remaining METRIC columns ─────────
        #
        # Rules are purely mathematical — no domain knowledge, no column name logic.
        # When in doubt: leave as METRIC. The LLM's metric.role field disambiguates.
        #
        # Confidence levels:
        #   formula-assigned (Step 1): 0.85–1.00   ← math proof
        #   fraction ratio [-1,1]:     0.80         ← very constrained range
        #   count/integer:             0.65         ← count_like heuristic
        #   time/date:                 0.80         ← format detection
        #   identifier:                0.65         ← uniqueness ratio
        #   category:                  0.70         ← low cardinality
        #   text:                      0.50         ← medium cardinality
        #   metric (default):          0.00         ← unresolved, LLM decides

        for col, node in nodes.items():
            if node.role != METRIC:
                continue
            info = profile.get(col, {})
            nums = info.get("numeric", [])
            strs = info.get("strings", [])
            ur = info.get("unique_count", 0) / max(info.get("total_count", 1), 1)
            mojo_sem = mojo_profiles.get(src_name, {}).get(col, {}).get("semantic_type", "")

            if node.is_numeric and nums:
                mn = min(nums)
                mx = max(nums)
                distinct = len({round(v, 3) for v in nums[:200]})
                # Has decimal precision — at least 10% of values are non-integer
                has_decimals = sum(1 for v in nums[:50] if abs(v - round(v)) > 1e-4) >= max(
                    len(nums[:50]) // 10, 1
                )

                # Fraction ratio: strict bound [-1, 1] + decimal precision required.
                # We do NOT try to detect percent-format (0-100) — that range is
                # indistinguishable from small counts, ages, scores, etc.
                # The LLM supplies role="ratio" when it knows from context.
                if mn >= -1.05 and mx <= 1.05 and has_decimals and distinct > 4:
                    node.role = RATIO
                    node.confidence = 0.80

                # Count/quantity: non-negative integers — universally unambiguous.
                elif _is_count_like(nums):
                    node.role = BASE_MEASURE
                    node.confidence = 0.65

                # High-uniqueness numeric: likely an ID or surrogate key.
                # Require ur > 0.95 AND integer-like (count_like) — decimal columns
                # with high cardinality are monetary amounts or rates, not identifiers.
                # e.g. AMOUNT=[$123.45, $2891.00, ...] is a measure; EMP_ID=[1,2,3...] is an ID.
                elif ur > 0.95 and _is_count_like(nums):
                    node.role = IDENTIFIER
                    node.confidence = 0.60

                # Decimal non-count, non-ratio column — classify as unit_measure.
                # These are continuous monetary values (prices, rates, costs, extended amounts)
                # that formula detection didn't catch (e.g. POS sources where multiply formulas
                # aren't detected but EXT_PRICE/UNIT_PRICE are clearly measures).
                # Step 3b below will further promote the highest-magnitude one to derived_measure
                # in sources where no formula-proven derived_measure exists.
                elif has_decimals:
                    node.role = UNIT_MEASURE
                    node.confidence = (
                        0.55  # low confidence: statistical inference, not formula proof
                    )

            elif strs:
                is_date = mojo_sem == "date" or any(_looks_like_date(s) for s in strs[:10])
                if is_date:
                    node.role = TIME
                    node.confidence = 0.80
                elif ur > 0.90:
                    node.role = IDENTIFIER
                    node.confidence = 0.65
                elif ur < 0.10:
                    node.role = CATEGORY
                    node.confidence = 0.70
                else:
                    node.role = TEXT
                    node.confidence = 0.50

        # ── Step 2b: Demote false-positive derived_measure columns ─────────
        # derived_measure is a proven label — it MUST come from a detected formula.
        # Three demotion rules (applied in priority order):
        #   1. No formula attached → formula detection never fired → metric
        #   2. Name signals identifier → identifier
        #   3. All-integer + high uniqueness → surrogate key → identifier
        for col, node in nodes.items():
            if node.role != DERIVED_MEASURE:
                continue
            info = profile.get(col, {})
            nums = info.get("numeric", [])
            ur = info.get("unique_count", 0) / max(info.get("total_count", 1), 1)

            # Rule 1: No formula → cannot be derived_measure (classification error)
            if node.formula is None:
                node.role = METRIC
                node.confidence = 0.0
                continue

            # Rule 2: Name signals an identifier (BLTITM_ID, GRPTAG_ID, etc.)
            if _col_name_signals_id(col):
                node.role = IDENTIFIER
                node.confidence = 0.65
                continue

            # Rule 3: All-integer + high uniqueness → surrogate key
            # Financial columns (EXT_PRICE) are safe: decimal values fail _is_count_like.
            if nums and _is_count_like(nums) and ur > 0.90:
                node.role = IDENTIFIER
                node.confidence = 0.60

        # ── Step 3: Magnitude ranking (all numeric roles) ─────────────────
        # Within each numeric role group, rank by mean magnitude so the resolver
        # can prefer the "biggest" column when multiple columns share a role.
        for role in (DERIVED_MEASURE, BASE_MEASURE, UNIT_MEASURE, METRIC):
            group = [
                (col, node.mean)
                for col, node in nodes.items()
                if node.role == role and node.mean > 0
            ]
            group.sort(key=lambda x: x[1], reverse=True)
            for rank, (col, _) in enumerate(group):
                nodes[col].magnitude_class = (
                    "large" if rank == 0 else "medium" if rank <= 2 else "small"
                )

        # ── Step 3b: Statistical derived_measure promotion ────────────────
        # For sources where formula detection found NO derived_measure, promote
        # the highest-magnitude (rank-0) statistically-inferred unit_measure column
        # to derived_measure. This handles cases like POS where EXT_PRICE = qty × price
        # was not detected by the Mojo binary but the data clearly has a "total revenue"
        # column with the highest mean.
        #
        # Guarding condition: only when zero formula-proven derived_measures exist.
        # When formulas ARE detected (Bookings, Inventory), this pass does nothing.
        has_formula_dm = any(n.role == DERIVED_MEASURE and n.formula for n in nodes.values())
        if not has_formula_dm:
            for col, node in nodes.items():
                col_tokens = set(re.findall(r"[a-z0-9]+", col.lower()))
                if (
                    node.role == UNIT_MEASURE
                    and node.confidence <= 0.55  # statistically inferred, not formula
                    and not node.formula
                    and node.magnitude_class == "large"
                    and not (col_tokens & {"unit", "rate"})
                ):
                    node.role = DERIVED_MEASURE
                    node.confidence = 0.65  # moderate: magnitude-based inference, no formula proof

        graph[src_name] = nodes

    return graph

def _graph_nodes_from_meta(schema_meta: dict[str, Any]) -> dict[str, ColumnNode]:
    """Reconstruct ColumnNode dict from persisted schema metadata."""
    nodes: dict[str, ColumnNode] = {}
    for col in schema_meta.get("columns", []):
        nodes[col["name"]] = ColumnNode(
            name=col["name"],
            role=col.get("role", METRIC),
            formula=col.get("formula"),
            mean=col.get("mean", 0.0),
            std=0.0,
            is_numeric=col.get("is_numeric", False),
            magnitude_class=col.get("magnitude", "medium"),
            semantic_type=col.get("semantic_type") or "",
            confidence=0.6,
            fill_rate=float(col.get("fill_rate", 1.0) or 1.0),
        )
    return nodes

