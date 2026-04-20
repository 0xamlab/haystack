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
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.routers.data_map import (
    DataSource,
    MojoInstrumentationError,
    _build_mojo_column_profile_columns,
    _call_mojo_column_profile,
    _load_source,
    _load_source_table,
    _mojo_profiling_disabled_status,
    _mojo_profiling_status_from_result,
)
from apps.api_server.schemas.common import ErrorDetail, ErrorResponse
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Semantic Query"])


# ── Hot source cache ───────────────────────────────────────────────────────────
# Key strategy:
#   content-keyed (csv, json_str, records): hash of content → permanent, no TTL.
#     Same content always produces same result — the hash IS the freshness guarantee.
#   path/url/connection-keyed: path+mtime → TTL-based (data can change under same key).
#
# LRU eviction when > _CACHE_MAX_SOURCES entries.

_PATH_CACHE_TTL = 1800  # 30 min for file/url/connection sources (content can change)
_CACHE_MAX_SOURCES = 30  # evict LRU when exceeded


@dataclass
class _CachedSource:
    parquet_bytes: bytes  # DataFrame serialized as Parquet (Arrow)
    parquet_schema_meta: bytes  # Arrow schema + embedded algenta metadata (JSON)
    profile: dict[str, dict]  # Python-computed column stats
    mojo_profile: dict[str, dict]  # Mojo semantic types
    relations: list[dict]  # detected A×B≈C formulas
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


_SOURCE_CACHE: dict[str, _CachedSource] = {}  # cache_key → entry
_CACHE_LOCK = asyncio.Lock()

_RESULT_CACHE: dict[
    str, dict
] = {}  # plan_hash → {"result", "result_type", "row_count", "confidence", "explanation"}
_RESULT_CACHE_MAX = 200
_RESULT_CACHE_TTL = 3600.0  # 1 hour

_RESOLVE_CACHE: dict[str, dict[str, Any]] = {}
_RESOLVE_CACHE_MAX = 500
_RESOLVE_CACHE_TTL = 3600.0  # 1 hour
_GRAPH_NODE_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
_GRAPH_NODE_CACHE_MAX = 256
_DATASET_EXACT_COLUMN_CACHE: dict[tuple[str, str, str], dict[str, dict[str, Any] | None]] = {}
_DATASET_EXACT_COLUMN_CACHE_MAX = 256
_RESOLVE_BUDGET_MS = 500.0
_ALLOW_QUERY_HINT_PLANNING_COMPAT = True
_MAX_RESOLVE_SOURCE_SCORES = 32
_MAX_RESOLVE_CANDIDATES = 5
_STOP_TOKENS = frozenset({
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
})

_VERIFY_CACHE: dict[str, tuple[dict, float]] = {}  # plan_key → (response_dict, timestamp)
_VERIFY_CACHE_MAX = 500
_VERIFY_CACHE_TTL = 300.0  # 5 minutes (schema changes are rare; 5 min is safe)


@dataclass
class _CachedFrame:
    df: Any
    records: list[dict[str, Any]] | None = None


_DF_CACHE: dict[str, _CachedFrame] = {}
_DF_CACHE_MAX = 20  # keep top-20 most-accessed DataFrames hot
_PLANNER_CACHE_MAX = 24  # per-org registry planners


@dataclass
class _CachedPlanner:
    planner: Any
    schema_revision: str
    llm_policy: str
    created_at: float = field(default_factory=time.monotonic)
    last_hit: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_hit = time.monotonic()


_PLANNER_CACHE: dict[tuple[str, str, str], _CachedPlanner] = {}


@dataclass(frozen=True)
class _LoadedProfiledSource:
    profile: dict[str, dict]
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
            float(
                getattr(plan, "path_confidence", 0.0) or getattr(plan, "join_conf", 0.0) or 0.0
            ),
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
    return [
        note
        for note in notes
        if any(token in note.lower() for token in load_bearing_tokens)
    ]


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
        and any(
            str(step).startswith(authoritative_prefixes)
            for step in getattr(plan, "steps", [])
        )
    )
    if authoritative_metric_selection:
        selected_payload["notes"].append("planner-authoritative-selection")
        return [selected_payload]

    if not metric_candidate_payloads and selected_payload is not None:
        return [selected_payload]
    return metric_candidate_payloads


def _evict_planner_lru() -> None:
    if len(_PLANNER_CACHE) < _PLANNER_CACHE_MAX:
        return
    oldest_key = min(_PLANNER_CACHE.items(), key=lambda item: item[1].last_hit)[0]
    _PLANNER_CACHE.pop(oldest_key, None)


async def _get_registry_planner(
    org_id: str,
    *,
    llm_policy: str = "never",
    auth: AuthContext | None = None,
    visible_entries: list[dict[str, Any]] | None = None,
) -> tuple[Any, bool, str]:
    from apps.api_server.services import source_registry as _sreg
    from apps.api_server.services.auto_planner import AutoPlanner
    from apps.api_server.services.data_visibility import (
        filter_visible_datasets,
        visibility_hash,
    )

    schema_revision = _sreg.schema_revision(org_id)
    if visible_entries is None:
        all_entries = _sreg.list_sources(org_id)
        visible_entries = (
            filter_visible_datasets(all_entries, auth) if auth is not None else all_entries
        )
    visible_ids = {str(entry.get("id")) for entry in visible_entries if entry.get("id")}
    visibility_fingerprint = visibility_hash(visible_entries)
    cache_key = (org_id, llm_policy, visibility_fingerprint)

    async with _CACHE_LOCK:
        cached = _PLANNER_CACHE.get(cache_key)
        if cached and cached.schema_revision == schema_revision:
            cached.touch()
            return cached.planner, True, schema_revision

    planner = AutoPlanner.from_registry(
        org_id,
        llm_policy=llm_policy,
        allowed_source_ids=visible_ids,
    )
    built = _CachedPlanner(
        planner=planner,
        schema_revision=schema_revision,
        llm_policy=llm_policy,
    )

    async with _CACHE_LOCK:
        cached = _PLANNER_CACHE.get(cache_key)
        if cached and cached.schema_revision == schema_revision:
            cached.touch()
            return cached.planner, True, schema_revision
        _evict_planner_lru()
        _PLANNER_CACHE[cache_key] = built

    return planner, False, schema_revision


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


# ── Source behavior classification ────────────────────────────────────────────
# Inferred from structural roles in schema metadata.
# Used to enforce semantic rules (e.g. "on_hand" queries only valid on snapshot sources).
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


def _infer_source_behavior(schema_meta: dict) -> str:
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


def _source_cache_key(src: DataSource, records: list[dict] | None = None) -> tuple[str, bool]:
    """
    Returns (cache_key, content_keyed).
    content_keyed=True  → hash of actual bytes; permanent, no TTL.
    content_keyed=False → path/name/type; short TTL since content can change.
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
    raw = f"{src_type}:{src.url or ''}:{src.name}:{connection_fingerprint}"
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


def _evict_lru() -> None:
    """Remove least-recently-used entry when cache is full."""
    if len(_SOURCE_CACHE) >= _CACHE_MAX_SOURCES:
        oldest = min(_SOURCE_CACHE, key=lambda k: _SOURCE_CACHE[k].last_hit)
        del _SOURCE_CACHE[oldest]
        logger.debug("source_cache_evict", key=oldest[:8])


def _build_schema_metadata(
    src_name: str,
    graph_nodes: dict[str, ColumnNode],
    relations: list[dict],
    profile: dict[str, dict],
    profiling_status: dict[str, Any] | None = None,
) -> dict:
    """
    Build the Algenta schema metadata dict embedded into the Parquet file.
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
    columns: list[dict] = []
    role_counts: dict[str, int] = {}
    planner_profile: dict[str, dict[str, Any]] = {}

    for col, node in sorted(graph_nodes.items()):
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
        col_meta: dict = {
            "name": col,
            "role": node.role,
            "is_numeric": node.is_numeric,
            "semantic_type": node.semantic_type or None,
        }
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

    role_groups: dict[str, list[dict]] = defaultdict(list)
    for col_meta in columns:
        role = col_meta["role"]
        if role in role_labels:
            role_groups[role].append(col_meta)
    for role in role_groups:
        role_groups[role].sort(key=lambda c: c.get("fill_rate", 0), reverse=True)

    hints: list[dict] = []
    # Emit in priority order: formula-detected roles first, then statistical
    for role in ("derived_measure", "unit_measure", "base_measure", "ratio", "metric"):
        cols = role_groups.get(role, [])
        if not cols:
            continue
        hint: dict = {
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


BINARY = Path(__file__).parent.parent.parent.parent / "mojo_build" / "simulate"


# ── Universal structural roles ─────────────────────────────────────────────────

DERIVED_MEASURE = "derived_measure"
BASE_MEASURE = "base_measure"
UNIT_MEASURE = "unit_measure"
COMPONENT = "component"
RATIO = "ratio"
IDENTIFIER = "identifier"
TIME = "time"
CATEGORY = "category"
TEXT = "text"
METRIC = "metric"

ALL_ROLES = {
    DERIVED_MEASURE,
    BASE_MEASURE,
    UNIT_MEASURE,
    COMPONENT,
    RATIO,
    IDENTIFIER,
    TIME,
    CATEGORY,
    TEXT,
    METRIC,
}

# ── Dimensional algebra (mirrors dimensions.mojo exactly — no column names) ────
#
# Dimension constants
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


# ── Schema graph ───────────────────────────────────────────────────────────────


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
    profiles: dict[str, dict[str, dict]],
    mojo_profiles: dict[str, dict],
    relations_by_source: dict[str, list[dict]],
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


# ── Column resolver ────────────────────────────────────────────────────────────

_METRIC_HINT_STOPWORDS = {
    "a",
    "an",
    "and",
    "avg",
    "average",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "sum",
    "the",
    "to",
}

_METRIC_TOKEN_CANON = {
    "amt": "amount",
    "avg": "average",
    "costs": "cost",
    "ext": "extended",
    "gm": "margin",
    "oh": "overhead",
    "pct": "percent",
    "qty": "quantity",
    "rev": "revenue",
}

_METRIC_CONCEPTS: dict[str, set[str]] = {
    "unit": {"average", "each", "per", "rate", "unit"},
    "total": {"amount", "extended", "gross", "revenue", "sales", "sum", "total", "value"},
    "overhead": {"burden", "indirect", "oh", "overhead"},
    "cost": {"cogs", "cost", "expense", "spend"},
    "price": {"price", "pricing"},
    "count": {"count", "quantity", "units", "volume"},
}

_SOURCE_PRIOR_TOKENS: dict[str, dict[str, set[str]]] = {
    "unit": {
        "source": {"pos", "price", "pricing", "quote", "quotes"},
        "column": {"price", "unit", "cost", "rate"},
    },
    "total": {
        "source": {"backlog", "booking", "bookings", "order", "orders", "sales"},
        "column": {"extended", "amount", "total", "value", "revenue", "sales"},
    },
}


def _metric_tokens(text: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", text.lower())
    tokens: set[str] = set()
    for tok in raw:
        if not tok or tok in _METRIC_HINT_STOPWORDS:
            continue
        canon = _METRIC_TOKEN_CANON[tok] if tok in _METRIC_TOKEN_CANON else tok
        tokens.add(canon)
    expanded = set(tokens)
    if "extended" in tokens:
        expanded.update({"ext", "total"})
    if "total" in tokens:
        expanded.update({"extended", "sum"})
    if "unit" in tokens:
        expanded.update({"each", "per", "rate"})
    if "overhead" in tokens:
        expanded.add("oh")
    return expanded


def _metric_concepts(tokens: set[str]) -> set[str]:
    concepts: set[str] = set()
    for concept, concept_tokens in _METRIC_CONCEPTS.items():
        if tokens & concept_tokens:
            concepts.add(concept)
    return concepts


def _metric_source_prior_bonus(
    source: str, col_tokens: set[str], hint_concepts: set[str]
) -> tuple[float, list[str]]:
    bonus = 0.0
    notes: list[str] = []
    src_tokens = _metric_tokens(source)
    for concept in sorted(hint_concepts):
        prior = _SOURCE_PRIOR_TOKENS.get(concept)
        if not prior:
            continue
        if src_tokens & prior["source"]:
            bonus += 0.04
            notes.append(f"source-prior:{concept}")
        if col_tokens & prior["column"]:
            bonus += 0.03
            notes.append(f"column-prior:{concept}")
    return min(bonus, 0.10), notes


def _metric_candidate_score(
    target_role: str,
    hint_tokens: set[str],
    src: str,
    col: str,
    node: ColumnNode,
) -> tuple[float, dict[str, float], list[str]]:
    col_tokens = _metric_tokens(col)
    hint_concepts = _metric_concepts(hint_tokens)
    col_concepts = _metric_concepts(col_tokens)
    components: dict[str, float] = {}
    notes: list[str] = []

    components["role"] = 0.58 + min(max(node.confidence, 0.0), 1.0) * 0.12
    if target_role == DERIVED_MEASURE:
        components["magnitude"] = (
            0.16
            if node.magnitude_class == "large"
            else 0.07
            if node.magnitude_class == "medium"
            else 0.0
        )
    else:
        components["magnitude"] = (
            0.07
            if node.magnitude_class == "large"
            else 0.03
            if node.magnitude_class == "medium"
            else 0.0
        )

    if hint_tokens and col_tokens:
        fwd = len(hint_tokens & col_tokens) / len(col_tokens)
        bwd = len(hint_tokens & col_tokens) / max(len(hint_tokens), 1)
        overlap = (fwd + bwd) / 2
    else:
        overlap = 0.0
    components["name_overlap"] = overlap * (0.28 if target_role == DERIVED_MEASURE else 0.24)

    concept_overlap = (
        len(hint_concepts & col_concepts) / max(len(hint_concepts), 1) if hint_concepts else 0.0
    )
    components["typed_intent"] = concept_overlap * 0.18
    if concept_overlap > 0:
        notes.append("typed-intent-match")

    contradictory = 0.0
    if "unit" in hint_concepts and "total" in col_concepts:
        contradictory -= 0.16
        notes.append("penalty:unit-vs-total")
    if "total" in hint_concepts and "unit" in col_concepts:
        contradictory -= 0.14
        notes.append("penalty:total-vs-unit")
    if (
        "overhead" in hint_concepts
        and "overhead" not in col_concepts
        and {"cost", "price"} & col_concepts
    ):
        contradictory -= 0.08
        notes.append("penalty:missing-overhead")
    components["typed_penalty"] = contradictory

    source_bonus, source_notes = _metric_source_prior_bonus(src, col_tokens, hint_concepts)
    components["source_prior"] = source_bonus
    notes.extend(source_notes)
    components["fill_rate"] = max(min(node.fill_rate, 1.0), 0.0) * 0.04

    if _col_name_signals_id(col):
        components["id_penalty"] = -0.40
        notes.append("penalty:identifier-like")
    else:
        components["id_penalty"] = 0.0

    score = sum(components.values())
    return score, {k: round(v, 3) for k, v in components.items()}, list(dict.fromkeys(notes))


def resolve_metric_column(
    target_role: str,
    hint_tokens: set[str],  # weak signal from user question / LLM semantic hint
    graph: SchemaGraph,
    preferred_source: str | None = None,
) -> tuple[str, str, float, list[dict]]:
    """
    Returns (source, column, confidence, all_candidates).
    Primary: structural role match.
    Secondary: magnitude class (for derived_measure).
    Tiebreaker: token overlap with hint_tokens (weak, 15% weight max).
    """
    best = ("", "", 0.0)
    candidates: list[dict] = []

    sources = [preferred_source] if preferred_source else list(graph.keys())

    for src in sources:
        if src not in graph:
            continue
        for col, node in graph[src].items():
            if not node.is_numeric:
                continue
            if node.role != target_role:
                continue

            # Hard-skip columns with near-zero fill — they can't produce results
            if node.fill_rate < 0.02:
                continue

            score, components, notes = _metric_candidate_score(
                target_role=target_role,
                hint_tokens=hint_tokens,
                src=src,
                col=col,
                node=node,
            )

            candidates.append(
                {
                    "source": src,
                    "column": col,
                    "role": node.role,
                    "magnitude": node.magnitude_class,
                    "formula": node.formula,
                    "confidence": round(score, 3),
                    "score_components": components,
                    "notes": notes,
                }
            )
            if score > best[2]:
                best = (src, col, score)

    # Fallback: broaden to METRIC if no exact role match OR best score too low
    # (< 0.40 means only ID-penalized columns matched — nothing semantically useful)
    if (not best[0] or best[2] < 0.40) and target_role != METRIC:
        src2, col2, conf2, cands2 = resolve_metric_column(
            METRIC, hint_tokens, graph, preferred_source
        )
        if src2:
            return src2, col2, round(conf2 * 0.5, 3), cands2  # penalty for fallback

    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    if len(candidates) >= 2:
        gap = round(candidates[0]["confidence"] - candidates[1]["confidence"], 3)
        if gap < 0.08:
            penalty = round((0.08 - gap) * 0.5 + 0.01, 3)
            reduced = max(
                candidates[1]["confidence"] + 0.001, candidates[0]["confidence"] - penalty
            )
            candidates[0]["confidence"] = round(reduced, 3)
            candidates[0].setdefault("notes", []).append(f"ambiguous-top2-gap:{gap:.3f}")
            candidates[1].setdefault("notes", []).append(
                f"close-second-to:{candidates[0]['column']}"
            )
    if candidates:
        best = (
            candidates[0]["source"],
            candidates[0]["column"],
            float(candidates[0]["confidence"]),
        )
    return best[0], best[1], round(best[2], 3), candidates


def resolve_group_column(
    dimension_hints: list[str],  # tokens from the LLM's group_by field
    source: str,
    graph: SchemaGraph,
) -> tuple[str, float]:
    """
    Find the best group-by column within a single source.
    Base score by role: CATEGORY=0.50, TIME=0.50, TEXT=0.30, IDENTIFIER=0.30.
    Name token overlap can overcome role difference.
    """
    if source not in graph:
        return "", 0.0

    dim_tokens = set(re.findall(r"[a-z0-9]+", " ".join(dimension_hints).lower()))
    role_base = {CATEGORY: 0.50, TEXT: 0.30, TIME: 0.50, IDENTIFIER: 0.30}

    best_col, best_score = "", 0.0
    for col, node in graph[source].items():
        base = role_base.get(node.role, 0.0)
        if base == 0.0:
            continue
        col_tokens = set(re.findall(r"[a-z0-9]+", col.lower()))
        if not col_tokens:
            continue
        # Bidirectional overlap: column must cover query tokens AND query tokens must cover column
        # col_to_query: how much of the column's meaning is in the query hint
        # query_to_col: how many of the query hint tokens appear in the column name
        # Bidirectional penalizes "CUSTOMER" when user says "customer masked" vs "CUSTOMER_MASKED"
        col_to_query = len(dim_tokens & col_tokens) / len(col_tokens)
        query_to_col = len(dim_tokens & col_tokens) / max(len(dim_tokens), 1)
        overlap = (col_to_query + query_to_col) / 2
        score = base + overlap * 0.70
        # Penalize columns with low fill rate — a 0%-filled column is useless
        # even if its name matches perfectly.  Scale score by fill_rate so
        # "Product Line" (fill=1.0) wins over "PRODUCT_LINE" (fill=0.0) even
        # when token overlap is identical.
        score *= max(node.fill_rate, 0.0)
        if score > best_score:
            best_score, best_col = score, col

    return best_col, round(best_score, 3)


def resolve_group_column_graph(
    dimension_hints: list[str],
    preferred_source: str,
    graph: SchemaGraph,
) -> tuple[str, str, float]:
    """
    Search ALL sources in the graph for the best group-by column.
    If preferred_source is non-empty, tries it first.
    Returns (source_name, column, score).
    """
    best_src, best_col, best_score = "", "", 0.0

    # Build search order: preferred first (if given), then all others
    sources = list(graph.keys())
    if preferred_source and preferred_source in graph:
        sources = [preferred_source] + [s for s in sources if s != preferred_source]

    for src_name in sources:
        col, score = resolve_group_column(dimension_hints, src_name, graph)
        if score > best_score:
            best_src, best_col, best_score = src_name, col, score

    return best_src, best_col, round(best_score, 3)


def _graph_nodes_from_meta(schema_meta: dict) -> dict[str, ColumnNode]:
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


_MIN_JOIN_CONFIDENCE = 0.85  # default threshold — only statistically solid entity joins


def _find_best_join_key(
    src_a_name: str,
    src_b_name: str,
    connections: list[dict],
    min_confidence: float = _MIN_JOIN_CONFIDENCE,
) -> tuple[str, str, float, str] | None:
    """
    Given the raw connections list from the registry, find the best join key
    between src_a and src_b with confidence >= min_confidence.
    Returns (col_in_a, col_in_b, confidence, cardinality) or None.

    Preference order (highest first):
      1. category / text / identifier column pair — true entity join
      2. Any other pair meeting the confidence threshold

    Hard reject: both columns are pure measures (base_measure / unit_measure /
    derived_measure / component / metric) — joining on shared numeric values
    produces spurious matches (e.g. Quantity=5 in Bookings ≠ Quantity=5 in Inventory).
    """
    measure_roles = frozenset(
        {
            "base_measure",
            "unit_measure",
            "derived_measure",
            "component",
            "metric",
        }
    )
    entity_roles = frozenset({"category", "text", "identifier"})

    def _col_role(c: dict, side: str) -> str:
        # connections.json may store col_a_role/col_b_role if present; otherwise unknown
        return c.get(f"{side}_role", "")

    entity_best: tuple[str, str, float, str] | None = None
    entity_conf = min_confidence
    fallback_best: tuple[str, str, float, str] | None = None
    fallback_conf = min_confidence

    for c in connections:
        a_name = c.get("source_a_name", "")
        b_name = c.get("source_b_name", "")
        conf = c.get("confidence", 0.0)
        cardinality = c.get("cardinality", "")

        if conf <= min_confidence:
            continue

        if a_name == src_a_name and b_name == src_b_name:
            col_a, col_b = c["col_a"], c["col_b"]
        elif a_name == src_b_name and b_name == src_a_name:
            col_a, col_b = c["col_b"], c["col_a"]
        else:
            continue

        role_a = _col_role(c, "col_a")
        role_b = _col_role(c, "col_b")
        both_measures = role_a in measure_roles and role_b in measure_roles
        either_entity = role_a in entity_roles or role_b in entity_roles

        # Hard reject: measure↔measure joins (spurious numeric overlap)
        if both_measures:
            continue

        # Name-based signal: if no role stored, check name for entity characteristics
        if not role_a and not role_b:
            a_looks_entity = (
                not _is_count_like([])  # can't check without samples
                and not any(
                    kw in col_a.lower()
                    for kw in ("price", "cost", "ext_", "amount", "qty", "quant")
                )
            )
            b_looks_entity = not any(
                kw in col_b.lower() for kw in ("price", "cost", "ext_", "amount", "qty", "quant")
            )
            if not a_looks_entity and not b_looks_entity:
                continue  # both look like measures — skip

        if either_entity and conf > entity_conf:
            entity_best, entity_conf = (col_a, col_b, conf, cardinality), conf
        elif not both_measures and conf > fallback_conf:
            fallback_best, fallback_conf = (col_a, col_b, conf, cardinality), conf

    return entity_best or fallback_best


def _reverse_cardinality(cardinality: str) -> str:
    if cardinality == "one_to_many":
        return "many_to_one"
    if cardinality == "many_to_one":
        return "one_to_many"
    return cardinality


def _match_join_path_edge(edge: JoinEdgeSpec, connections: list[dict]) -> tuple[float, str]:
    for conn in connections:
        src_a = conn.get("source_a_name", "")
        src_b = conn.get("source_b_name", "")
        col_a = conn.get("col_a", "")
        col_b = conn.get("col_b", "")
        conf = float(conn.get("confidence", 0.0) or 0.0)
        card = str(conn.get("cardinality", "") or "")

        if (
            src_a == edge.left_source
            and src_b == edge.right_source
            and col_a == edge.left_key
            and col_b == edge.right_key
        ):
            return conf, card

        if (
            src_a == edge.right_source
            and src_b == edge.left_source
            and col_a == edge.right_key
            and col_b == edge.left_key
        ):
            return conf, _reverse_cardinality(card)

    raise ValueError(
        "Join edge not found in registry: "
        f"{edge.left_source}.{edge.left_key} -> {edge.right_source}.{edge.right_key}"
    )


def _resolve_join_path(
    metric_source: str,
    join_path: JoinPathSpec,
    connections: list[dict],
) -> tuple[list[JoinEdgeSpec], str, float, list[tuple[float, str]]]:
    if join_path.base_source != metric_source:
        raise ValueError(
            "join_path.base_source="
            f"'{join_path.base_source}' must match source_name='{metric_source}'"
        )

    if len(join_path.edges) > join_path.max_hops:
        raise ValueError(
            f"join_path has {len(join_path.edges)} edges but max_hops={join_path.max_hops}"
        )

    if not join_path.edges:
        terminal = join_path.group_source or join_path.base_source
        if terminal != join_path.base_source:
            raise ValueError("join_path.group_source requires at least one join edge")
        return [], terminal, 1.0, []

    ordered: list[JoinEdgeSpec] = []
    current = join_path.base_source
    visited = {current}
    edge_meta: list[tuple[float, str]] = []
    path_conf = 1.0

    for idx, edge in enumerate(join_path.edges, start=1):
        if edge.join_type != "inner":
            raise ValueError(f"join_path edge {idx} uses unsupported join_type='{edge.join_type}'")
        if edge.left_source != current:
            raise ValueError(
                f"join_path edge {idx} must continue from '{current}', got '{edge.left_source}'"
            )
        if edge.right_source in visited:
            raise ValueError(f"join_path edge {idx} introduces a cycle at '{edge.right_source}'")

        conf, card = _match_join_path_edge(edge, connections)
        if conf < edge.min_confidence:
            raise ValueError(
                f"join_path edge {idx} confidence {conf:.2f} "
                f"is below min_confidence {edge.min_confidence:.2f}"
            )
        if edge.expected_cardinality and card and edge.expected_cardinality != card:
            raise ValueError(
                f"join_path edge {idx} expected cardinality "
                f"'{edge.expected_cardinality}' but registry reports '{card}'"
            )
        if card == "many_to_many" and not edge.allow_many_to_many:
            raise ValueError(f"join_path edge {idx} rejects many_to_many fanout")
        if join_path.reject_on_fanout and card in {"one_to_many", "many_to_many"}:
            raise ValueError(
                f"join_path edge {idx} has fanout cardinality '{card}' and reject_on_fanout=true"
            )

        ordered.append(edge)
        edge_meta.append((conf, card))
        path_conf *= conf
        current = edge.right_source
        visited.add(current)

    if join_path.group_source and current != join_path.group_source:
        raise ValueError(
            "join_path.group_source="
            f"'{join_path.group_source}' does not match terminal source '{current}'"
        )

    if path_conf < join_path.min_path_confidence:
        raise ValueError(
            f"join_path confidence {path_conf:.3f} is below "
            f"min_path_confidence {join_path.min_path_confidence:.3f}"
        )

    return ordered, current, round(path_conf, 3), edge_meta


def execute_join_path(
    records_by_source: dict[str, list[dict]],
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
    for row in base_records:
        value = _num(row, metric_col)
        if value is None:
            continue
        current_rows.append({"metric": value, "row": row})

    if not current_rows:
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

        right_index: dict[str, list[dict]] = {}
        for right_row in right_records:
            key = str(right_row.get(resolved_right_key, "")).strip()
            if key:
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
            join_val = str(left_row.get(resolved_left_key, "")).strip()
            if not join_val:
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
                next_rows.append({"metric": item["metric"], "row": match})

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
        buckets.setdefault(grp, []).append(float(item["metric"]))

    if not buckets:
        return None, matched, plan + ["No rows matched in join-path execution"]

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

    result = [{"group": k, "value": round(_agg_fn(v), 4)} for k, v in buckets.items()]
    result.sort(key=lambda x: x["value"], reverse=(order == "desc"))
    if limit:
        result = result[:limit]

    plan.append(
        f"{agg.upper()}(`{metric_col}`) BY `{resolved_group_col}` "
        f"(join-path) -> {len(result)} groups"
    )
    return result, matched, plan


def execute_cross_source(
    metric_records: list[dict],
    metric_col: str,
    group_records: list[dict],
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
        v = str(r.get(group_col, "?")).strip()
        if k:
            join_map[k] = v

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

    result = [{"group": k, "value": round(_agg_fn(v), 4)} for k, v in buckets.items()]
    result.sort(key=lambda x: x["value"], reverse=(order == "desc"))
    if limit:
        result = result[:limit]

    plan.append(f"{agg.upper()}(`{metric_col}`) BY `{group_col}` (joined) → {len(result)} groups")
    return result, matched, plan


def resolve_source(
    target_role: str,
    metric_hint_tokens: set[str],
    group_tokens: list[str],
    preferred_source: str | None,
    graph: SchemaGraph,
) -> tuple[str, float, dict[str, float]]:
    """
    SOURCE RESOLVER — runs before column resolution.

    Score every registered source to find which one the query is ABOUT,
    not just which one has the globally best column.

    Scoring (0–1 each, weighted):
      0.35 — Has the requested metric role
      0.25 — Column names match metric hint tokens
      0.25 — Column names match group_by dimension tokens
      0.15 — Explicit preferred_source from LLM

    Returns (best_source_name, best_score, all_scores_dict).
    Score >= 0.60 → confident; < 0.40 → ambiguous.
    """
    group_dim_tokens = set(re.findall(r"[a-z0-9]+", " ".join(group_tokens).lower()))
    source_scores: dict[str, float] = {}

    for src_name, nodes in graph.items():
        s = 0.0

        # 1. Has the requested metric role (or usable fallback)
        has_exact = any(n.role == target_role for n in nodes.values())
        has_numeric = any(n.is_numeric for n in nodes.values())
        if has_exact:
            s += 0.35
        elif has_numeric:
            s += 0.10  # partial credit — might work via METRIC fallback

        # 2. Column names match metric hint
        if metric_hint_tokens:
            best_mh = 0.0
            for col, node in nodes.items():
                if not node.is_numeric:
                    continue
                col_tok = set(re.findall(r"[a-z0-9]+", col.lower()))
                if not col_tok:
                    continue
                fwd = len(metric_hint_tokens & col_tok) / len(col_tok)
                bwd = len(metric_hint_tokens & col_tok) / max(len(metric_hint_tokens), 1)
                best_mh = max(best_mh, (fwd + bwd) / 2)
            s += best_mh * 0.25

        # 3. Column names match group dimension
        if group_dim_tokens:
            best_gd = 0.0
            for col, _node in nodes.items():
                col_tok = set(re.findall(r"[a-z0-9]+", col.lower()))
                if not col_tok:
                    continue
                fwd = len(group_dim_tokens & col_tok) / len(col_tok)
                bwd = len(group_dim_tokens & col_tok) / max(len(group_dim_tokens), 1)
                best_gd = max(best_gd, (fwd + bwd) / 2)
            s += best_gd * 0.25

        # 4. Explicit LLM preference
        if preferred_source and src_name.lower() == preferred_source.lower():
            s += 0.15

        source_scores[src_name] = round(s, 4)

    if not source_scores:
        return "", 0.0, {}

    best_src = max(source_scores, key=lambda k: source_scores[k])
    return best_src, source_scores[best_src], source_scores


async def _call_mojo_source_score(
    target_role: str,
    metric_hint_tokens: set[str],
    group_tokens: list[str],
    preferred_source: str | None,
    graph: SchemaGraph,
) -> tuple[str, float, dict[str, float]] | None:
    """
    Ask the Mojo engine to score all sources for this query.
    Falls back to Python resolve_source() if the engine doesn't support
    engine_type=source_score yet (returns None on any failure).

    Mojo payload schema:
      {
        "engine_type": "source_score",
        "target_role": "derived_measure",
        "metric_hint_tokens": ["cost"],
        "group_tokens": ["division"],
        "preferred_source": "",
        "sources": {
          "Inventory": {
            "columns": [{"name": "Unit Cost", "role": "metric", "is_numeric": true}, ...]
          }
        }
      }

    Expected Mojo response:
      {"scores": {"Inventory": 0.82, "Bookings": 0.55, ...}}
    """
    if not graph:
        return None

    sources_payload: dict[str, dict] = {}
    for src_name, nodes in graph.items():
        sources_payload[src_name] = {
            "columns": [
                {
                    "name": node.name,
                    "role": node.role,
                    "is_numeric": node.is_numeric,
                }
                for node in nodes.values()
            ]
        }

    payload = {
        "engine_type": "source_score",
        "target_role": target_role,
        "metric_hint_tokens": sorted(metric_hint_tokens),
        "group_tokens": group_tokens,
        "preferred_source": preferred_source or "",
        "sources": sources_payload,
    }

    try:
        from apps.api_server.compute.mojo_adapter import invoke_engine

        result = await invoke_engine(payload)
        scores = result.get("scores")
        if not scores or not isinstance(scores, dict):
            return None
        best_src = max(scores, key=lambda k: scores[k])
        return best_src, float(scores[best_src]), {k: float(v) for k, v in scores.items()}
    except Exception as exc:
        logger.debug("mojo_source_score_fallback", reason=str(exc)[:120])
        return None


# ── Time helpers ───────────────────────────────────────────────────────────────


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


# ── Executor ───────────────────────────────────────────────────────────────────


def _parse_date(v: Any) -> date | None:
    if v is None:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d", "%Y-%m"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            pass
    return None


def _num(r: dict, col: str) -> float | None:
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


def _resolve_col_name(col: str, records: list[dict]) -> str:
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


def execute(
    records: list[dict],
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
            table_result = [{"group": k, "value": float(v)} for k, v in count_buckets.items()]
            table_result.sort(key=lambda x: x["value"], reverse=(order == "desc"))
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

        table_result = [{"group": k, "value": round(_agg_fn(v), 4)} for k, v in buckets.items()]
        table_result.sort(key=lambda x: x["value"], reverse=(order == "desc"))
        if limit:
            table_result = table_result[:limit]
        plan.append(f"{agg.upper()}(`{metric_col}`) BY `{group_col}` → {len(table_result)} groups")
        return table_result, len(rows), plan

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


# ── Mojo helpers ───────────────────────────────────────────────────────────────


async def _detect_relations(
    source: str,
    profiles: dict[str, dict],
    min_confidence: float = 0.70,
) -> list[dict]:
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
        _TARGET_SAMPLES,
    )
    if n_sample < 3:
        return []

    cols_payload: dict[str, list[float]] = {
        col: nums[:n_sample] for col, nums in col_nums.items() if nums
    }
    payload = {
        "engine_type": "relation_detect",
        "source": source,
        "min_confidence": min_confidence,
        "columns": cols_payload,
    }
    loop = asyncio.get_event_loop()

    def _run() -> list[dict]:
        try:
            r = subprocess.run(  # noqa: S603 - fixed local Mojo binary path
                [str(BINARY)],
                input=json.dumps(payload).encode(),
                capture_output=True,
                timeout=30,
            )
            if r.returncode == 0:
                return json.loads(r.stdout).get("relationships", [])
        except Exception as exc:
            logger.debug("query_relation_detect_error", error=str(exc))
        return []

    return await loop.run_in_executor(None, _run)


_FAST_SCAN_ROWS = 200  # rows checked in fast path
_SPARSE_THRESHOLD = 10  # if fewer non-empty values in fast scan → deep scan
_TARGET_SAMPLES = 500  # non-empty values to collect per column (stop early)
_NUM_COERCE_CHARS = str.maketrans("", "", ",$% \t")  # strip before float() attempt


def _try_numeric(v: object) -> float | None:
    """Return float if v is numeric or a string that parses as a number, else None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(v, str):
        s = v.strip().translate(_NUM_COERCE_CHARS)
        if not s:
            return None
        try:
            f = float(s)
            return None if math.isnan(f) or math.isinf(f) else f
        except ValueError:
            return None
    return None


def _profile_records(records: list[dict]) -> dict[str, dict]:
    """
    Column-first profiler with lazy deep scan.

    Strategy per column:
      Fast path  — scan first _FAST_SCAN_ROWS rows.
      Deep scan  — if fewer than _SPARSE_THRESHOLD non-empty values found,
                   scan the entire dataset.  Stops once _TARGET_SAMPLES collected.

    This handles columns where data only appears further down the file
    (sparse columns, late-loaded enrichments, etc.).
    """
    if not records:
        return {}

    n_total = len(records)
    fields = list(records[0].keys())
    profile: dict[str, dict] = {}

    for f in fields:
        nums: list[float] = []
        strs: list[str] = []
        non_empty_count = 0  # true fill counter — keeps going after sample target
        unique_values: set[str] = set()

        def _ingest(
            v: object,
            *,
            unique_values_ref: set[str] = unique_values,
            nums_ref: list[float] = nums,
            strs_ref: list[str] = strs,
        ) -> None:
            nonlocal non_empty_count
            if v is None:
                return
            s = str(v).strip() if not isinstance(v, int | float) else None
            if s == "":
                return
            non_empty_count += 1
            fn = _try_numeric(v)
            if fn is not None:
                unique_values_ref.add(str(int(fn)) if float(fn).is_integer() else str(fn))
            else:
                unique_values_ref.add(s if s is not None else str(v))
            if len(nums_ref) + len(strs_ref) >= _TARGET_SAMPLES:
                return  # still counting non_empty, but don't store the sample
            if fn is not None:
                nums_ref.append(fn)
            else:
                strs_ref.append(s if s is not None else str(v))

        # ── Fast path ──────────────────────────────────────────────────────
        fast_limit = min(_FAST_SCAN_ROWS, n_total)
        for i in range(fast_limit):
            _ingest(records[i].get(f))

        # ── Extend scan if sparse OR haven't hit sample target ─────────────
        # Always scan remaining rows: samples stop at _TARGET_SAMPLES,
        # but non_empty_count continues so fill_rate is always exact.
        if n_total > fast_limit:
            for i in range(fast_limit, n_total):
                _ingest(records[i].get(f))

        entry: dict = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": len(nums) > len(strs),
            "sample_values": [str(v) for v in nums[:50]] + strs[:50],
            "unique_count": len(unique_values),
            "total_count": non_empty_count,
            "non_empty": non_empty_count,
            "fill_rate": round(non_empty_count / n_total, 4),
        }
        if nums:
            mean = sum(nums) / len(nums)
            entry["mean"] = mean
            entry["std"] = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1))
        profile[f] = entry

    return profile


def _profile_records_and_arrow(records: list[dict]) -> tuple[dict[str, dict], Any]:
    """
    Build planner profile stats and Arrow columns in one pass over row records.

    The upload/register path previously did two full Python scans after parse:
      1. `_profile_records(records)`
      2. build per-column Arrow arrays for Parquet serialization

    Combining them keeps the same profiling semantics while removing the second
    row-scale walk from hot registration paths.
    """
    import pyarrow as pa

    if not records:
        return {}, pa.table({})

    n_total = len(records)
    fields = list(records[0].keys())

    numeric_samples: dict[str, list[float]] = {field: [] for field in fields}
    string_samples: dict[str, list[str]] = {field: [] for field in fields}
    non_empty_counts: dict[str, int] = dict.fromkeys(fields, 0)
    unique_values: dict[str, set[str]] = {field: set() for field in fields}
    column_values: dict[str, list[Any]] = {field: [] for field in fields}

    for row in records:
        for field_name in fields:
            value = row.get(field_name)

            if value is None:
                column_values[field_name].append(None)
                continue

            stripped: str | None = None
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.lower() in {"", "?", "none", "null", "nan"}:
                    column_values[field_name].append(None)
                else:
                    column_values[field_name].append(value)
            else:
                column_values[field_name].append(value)

            if stripped == "":
                continue

            non_empty_counts[field_name] += 1

            numeric_value = _try_numeric(value)
            if numeric_value is not None:
                unique_values[field_name].add(
                    str(int(numeric_value))
                    if float(numeric_value).is_integer()
                    else str(numeric_value)
                )
                if (
                    len(numeric_samples[field_name]) + len(string_samples[field_name])
                    < _TARGET_SAMPLES
                ):
                    numeric_samples[field_name].append(numeric_value)
                continue

            string_value = stripped if stripped is not None else str(value)
            unique_values[field_name].add(string_value)
            if len(numeric_samples[field_name]) + len(string_samples[field_name]) < _TARGET_SAMPLES:
                string_samples[field_name].append(string_value)

    profile: dict[str, dict] = {}
    arrays: dict[str, Any] = {}

    for field_name in fields:
        nums = numeric_samples[field_name]
        strs = string_samples[field_name]
        entry: dict[str, Any] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": len(nums) > len(strs),
            "sample_values": [str(v) for v in nums[:50]] + strs[:50],
            "unique_count": len(unique_values[field_name]),
            "total_count": non_empty_counts[field_name],
            "non_empty": non_empty_counts[field_name],
            "fill_rate": round(non_empty_counts[field_name] / n_total, 4),
        }
        if nums:
            mean = sum(nums) / len(nums)
            entry["mean"] = mean
            entry["std"] = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1))
        profile[field_name] = entry

        try:
            arrays[field_name] = pa.array(column_values[field_name])
        except Exception:
            arrays[field_name] = pa.array(
                [str(value) if value is not None else None for value in column_values[field_name]],
                type=pa.string(),
            )

    return profile, pa.table(arrays)


def _profile_arrow_table(table: Any) -> dict[str, dict]:
    import pyarrow as pa
    import pyarrow.compute as pc

    if table is None or getattr(table, "num_rows", 0) == 0:
        return {}

    n_total = int(table.num_rows)
    profile: dict[str, dict] = {}

    def _distinct_count(array: Any) -> int:
        try:
            return int(pc.count_distinct(array, mode="only_valid").as_py() or 0)
        except Exception:
            return len({value for value in array.to_pylist() if value is not None})

    def _sample_non_null_values(array: Any, limit: int) -> list[Any]:
        if limit <= 0:
            return []
        sample_values: list[Any] = []
        chunks = array.iterchunks() if hasattr(array, "iterchunks") else (array,)
        for chunk in chunks:
            valid_chunk = pc.drop_null(chunk)
            if len(valid_chunk) == 0:
                continue
            remaining = limit - len(sample_values)
            sample_values.extend(valid_chunk.slice(0, remaining).to_pylist())
            if len(sample_values) >= limit:
                break
        return sample_values

    for field_name in table.column_names:
        column = table[field_name]
        if pa.types.is_dictionary(column.type):
            column = pc.dictionary_decode(column)

        total_count = int(pc.count(column, mode="only_valid").as_py() or 0)
        fill_rate = round(total_count / n_total, 4) if n_total else 0.0
        sample_values = _sample_non_null_values(column, _TARGET_SAMPLES)

        is_numeric = (
            pa.types.is_integer(column.type)
            or pa.types.is_floating(column.type)
            or pa.types.is_decimal(column.type)
        )

        nums: list[float] = []
        strs: list[str] = []
        if is_numeric:
            for value in sample_values:
                try:
                    fv = float(value)
                except (TypeError, ValueError):
                    continue
                if not math.isnan(fv) and not math.isinf(fv):
                    nums.append(fv)
        else:
            strs = [str(value) for value in sample_values if value is not None]

        entry: dict[str, Any] = {
            "numeric": nums,
            "strings": strs,
            "is_numeric": is_numeric,
            "sample_values": [str(v) for v in sample_values[:50]],
            "unique_count": _distinct_count(column),
            "total_count": total_count,
            "non_empty": total_count,
            "fill_rate": fill_rate,
        }
        if nums:
            mean = sum(nums) / len(nums)
            entry["mean"] = mean
            entry["std"] = math.sqrt(sum((x - mean) ** 2 for x in nums) / max(len(nums) - 1, 1))
        profile[field_name] = entry

    return profile


# ── Request / Response schemas ─────────────────────────────────────────────────


def _error_details(items: list[tuple[str | None, str]] | None) -> list[ErrorDetail]:
    return [
        ErrorDetail(field=field, issue=issue)
        for field, issue in (items or [])
    ]


def _http_error(
    status_code: int,
    *,
    code: str,
    message: str,
    request_id: str | None = None,
    details: list[tuple[str | None, str]] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse.make(
            code=code,
            message=message,
            request_id=request_id,
            details=_error_details(details),
        ).model_dump(mode="python"),
    )


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


def _normalize_filter_spec(filter_spec: FilterSpec | None) -> dict[str, Any] | None:
    if filter_spec is None:
        return None
    data = filter_spec.model_dump(mode="python")
    return {key: value for key, value in data.items() if value is not None}


def _normalize_constraint_spec(constraints: ConstraintSpec | None) -> dict[str, Any]:
    if constraints is None:
        return {}
    return constraints.model_dump(mode="python")


def _normalize_join_path_spec(join_path: JoinPathSpec | None) -> dict[str, Any] | None:
    if join_path is None:
        return None
    return join_path.model_dump(mode="python")


def _exact_plan_basis(
    *,
    source_name: str,
    metric_column: str,
    aggregation: str,
    group_column: str | None,
    join_path: JoinPathSpec | None,
    filter_spec: FilterSpec | None,
    limit: int | None,
    order: str,
    constraints: ConstraintSpec,
) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "metric_column": metric_column,
        "aggregation": aggregation,
        "group_column": group_column or "",
        "join_path": _normalize_join_path_spec(join_path),
        "filter": _normalize_filter_spec(filter_spec),
        "limit": limit,
        "order": order,
        "constraints": _normalize_constraint_spec(constraints),
    }


def _immutable_plan_hash(*, schema_revision: str | None, basis: dict[str, Any]) -> str:
    payload = {
        "schema_revision": schema_revision or "",
        "basis": basis,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:24]


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
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:24]


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
    cached["_ts"] = time.monotonic()  # type: ignore[index]
    lookup = cached.get("lookup")  # type: ignore[assignment]
    return lookup if isinstance(lookup, dict) else None


def _dataset_exact_column_cache_put(
    key: tuple[str, str, str],
    lookup: dict[str, dict[str, Any] | None],
) -> dict[str, dict[str, Any] | None]:
    if len(_DATASET_EXACT_COLUMN_CACHE) >= _DATASET_EXACT_COLUMN_CACHE_MAX:
        oldest_key = min(
            _DATASET_EXACT_COLUMN_CACHE.items(),
            key=lambda item: item[1].get("_ts", 0.0),
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


class ConstraintSpec(BaseModel):
    requires_derived: bool = Field(
        default=False,
        description="Reject if metric column is not a derived_measure (formula-proven).",
    )
    no_cross_source: bool = Field(
        default=False,
        description="Reject if query requires a cross-source join.",
    )
    min_column_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Reject if column_confidence component < this value.",
    )


class MetricSpec(BaseModel):
    """
    Structural role target. The LLM selects based on what the user wants.

    Use 'derived_measure' for revenue, spend, total value — the computed aggregate.
    Use 'base_measure' for counts, quantities, discrete amounts.
    Use 'unit_measure' for prices, rates, per-unit values.
    Use 'ratio' for percentages, margins, fill rates.
    Use 'metric' to let the engine pick the best numeric column.
    """

    role: str = Field(
        default=DERIVED_MEASURE,
        description=(
            f"Structural role. One of: {', '.join(sorted(ALL_ROLES))}. "
            "derived_measure = computed aggregate (revenue, total value). "
            "base_measure = count/quantity. unit_measure = price/rate. "
            "ratio = percentage/margin. metric = best numeric column."
        ),
    )
    hint: str | None = Field(
        default=None,
        description=(
            "Optional weak signal — a word from the user's question. "
            "Used only as a tiebreaker when multiple columns share the same role. "
            "Never the primary signal. Examples: 'revenue', 'quantity', 'price'."
        ),
    )


class FilterSpec(BaseModel):
    """Time or value filter."""

    time_filter: str | None = Field(
        default=None,
        description=(
            "Relative time window. One of: last_quarter, this_quarter, "
            "last_month, this_month, last_year, this_year."
        ),
    )


class JoinEdgeSpec(BaseModel):
    """One explicit edge in a multi-hop join path."""

    model_config = ConfigDict(extra="forbid")

    left_source: str = Field(..., description="Source on the left side of the join edge.")
    right_source: str = Field(..., description="Source on the right side of the join edge.")
    left_key: str = Field(..., description="Exact join key column in left_source.")
    right_key: str = Field(..., description="Exact join key column in right_source.")
    join_type: str = Field(
        default="inner", description="Join type. Initial implementation supports inner."
    )
    min_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum acceptable confidence for this hop."
    )
    expected_cardinality: str | None = Field(
        default=None,
        description=(
            "Optional expected cardinality such as one_to_many, many_to_one, or many_to_many."
        ),
    )
    allow_many_to_many: bool = Field(
        default=False,
        description="If false, planner/executor must reject many_to_many fanout on this hop.",
    )


class JoinPathSpec(BaseModel):
    """Explicit multi-hop join contract replacing single-hop join fields."""

    model_config = ConfigDict(extra="forbid")

    base_source: str = Field(
        ..., description="Source that owns the metric column and anchors the path."
    )
    group_source: str | None = Field(
        default=None,
        description=(
            "Final source expected to provide the group column, if different from base_source."
        ),
    )
    edges: list[JoinEdgeSpec] = Field(
        default_factory=list,
        description="Ordered join edges from base_source toward the dimension source.",
    )
    max_hops: int = Field(
        default=4, ge=1, le=4, description="Maximum allowed join hops for this request."
    )
    min_path_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum acceptable composed confidence across the full join path.",
    )
    reject_on_ambiguity: bool = Field(
        default=True,
        description=(
            "Reject if more than one viable path exists with insufficient score separation."
        ),
    )
    reject_on_fanout: bool = Field(
        default=True,
        description="Reject if estimated path fanout exceeds safe execution thresholds.",
    )


class ResolvedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    metric_column: str
    aggregation: str = Field(default="sum", description="sum | avg | count | max | min")
    group_column: str | None = None
    join_path: JoinPathSpec | None = None
    filter: FilterSpec | None = None
    limit: int | None = None
    order: str = Field(default="desc", description="desc | asc")
    constraints: ConstraintSpec = Field(default_factory=ConstraintSpec)
    schema_revision: str


class ResolveRequest(BaseModel):
    """Bounded planning request that returns an exact executable plan."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = Field(
        default=None,
        description=(
            "Public dataset ID alias for a registered source. "
            "Required unless allow_org_scope=true or only one visible dataset exists."
        ),
    )
    metric: MetricSpec = Field(default_factory=MetricSpec)
    group_by: list[str] = Field(default_factory=list)
    preferred_source: str | None = Field(default=None)
    reject_on_ambiguity: bool = Field(default=False)
    min_source_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    aggregation: str = Field(default="sum", description="sum | avg | count | max | min")
    filter: FilterSpec | None = None
    limit: int | None = Field(default=None, description="Top-N limit")
    order: str = Field(default="desc", description="desc | asc")
    constraints: ConstraintSpec = Field(default_factory=ConstraintSpec)
    raw_text: str | None = Field(
        default=None,
        description=(
            "Optional non-authoritative raw text hint. "
            "Structured intent remains the source of truth."
        ),
    )
    include_explanation: bool = Field(default=False)
    allow_org_scope: bool = Field(
        default=False,
        description="When true, resolve can consider all visible datasets in the org.",
    )


class QueryRequest(BaseModel):
    """
    Structured query execution request.

    ═══════════════════════════════════════════════════════════
    PRIMARY PATH  —  Exact spec  (use after reading the schema)
    ═══════════════════════════════════════════════════════════
    The correct flow:
      1. Call POST /v1/sources/register or POST /v1/sources/schema
      2. LLM reads the returned schema (column names, roles, formulas)
      3. LLM sends exact column names — Mojo validates and executes

    Example (top 5 customers by revenue):
      {
        "source_name": "S0",
        "metric_column": "measure_total",
        "group_column": "dimension_label",
        "aggregation": "sum",
        "limit": 5
      }

    For multi-hop joins:
      {
        "source_name": "S0",
        "metric_column": "measure_total",
        "group_column": "dimension_label",
        "join_path": {
          "base_source": "S0",
          "group_source": "S2",
          "edges": [
            {
              "left_source": "S0",
              "right_source": "S1",
              "left_key": "k01_left",
              "right_key": "k01_right"
            },
            {
              "left_source": "S1",
              "right_source": "S2",
              "left_key": "k12_left",
              "right_key": "k12_right"
            }
          ]
        },
        "aggregation": "sum"
      }

    ═══════════════════════════════════════════════════════════
    FALLBACK PATH  —  Hint spec  (when schema is not yet known)
    ═══════════════════════════════════════════════════════════
    The engine resolves source and columns from structural role hints.
    Use this ONLY for exploratory queries. Always migrate to exact spec
    once you have the schema — it is faster and never ambiguous.

    Example:
      {
        "metric": {"role": "derived_measure", "hint": "total value"},
        "group_by": ["segment"],
        "aggregation": "sum",
        "limit": 5
      }
    """

    model_config = ConfigDict(extra="forbid")

    dataset_id: str | None = Field(
        default=None,
        description=(
            "Public dataset ID alias for a registered source. "
            "When provided, query execution is scoped to that one registered dataset."
        ),
    )

    # ── Exact spec (primary path) ─────────────────────────────────────────
    source_name: str | None = Field(
        default=None,
        description=(
            "EXACT source name from the registry "
            "(e.g. 'Bookings'). Bypasses source resolver entirely. "
            "Get this from POST /v1/sources/schema or the registration response."
        ),
    )
    metric_column: str | None = Field(
        default=None,
        description=(
            "EXACT column name for the metric "
            "(e.g. 'EXT_PRICE'). Bypasses column resolver. "
            "The engine validates this column exists in source_name."
        ),
    )
    group_column: str | None = Field(
        default=None,
        description=(
            "EXACT column name for group-by "
            "(e.g. 'CUSTOMER'). Bypasses group resolver. "
            "Can be in source_name or in the terminal source of join_path."
        ),
    )
    join_path: JoinPathSpec | None = Field(
        default=None,
        description=(
            "Explicit multi-hop join graph. Breaking replacement for single-hop join fields. "
            "Supports 1-hop to 4-hop paths with per-edge constraints "
            "and path-level confidence gates."
        ),
    )

    # ── Fallback / hint spec ──────────────────────────────────────────────
    sources: list[DataSource] = Field(
        default=[],
        description="Raw data sources (inline CSV/JSON). Usually empty — use registry.",
    )
    metric: MetricSpec = Field(default_factory=MetricSpec)
    group_by: list[str] = Field(
        default=[],
        description=(
            "Hint mode only: dimension words from the user's question "
            "(e.g. ['customer', 'region']). Ignored when group_column is set."
        ),
    )
    preferred_source: str | None = Field(
        default=None,
        description=(
            "Hint mode only: source name the LLM believes is correct. "
            "Hard-locks the source resolver. Ignored when source_name is set."
        ),
    )
    reject_on_ambiguity: bool = Field(
        default=False,
        description=(
            "Hint mode only: when True and resolver confidence < 0.40, "
            "return null result with source candidates instead of guessing."
        ),
    )
    min_source_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Hint mode only: minimum resolver confidence threshold.",
    )

    # ── Execution spec (shared) ──────────────────────────────────────────
    aggregation: str = Field(default="sum", description="sum | avg | count | max | min")
    filter: FilterSpec | None = None
    limit: int | None = Field(default=None, description="Top-N limit")
    order: str = Field(default="desc", description="desc | asc")
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    constraints: ConstraintSpec = Field(default_factory=ConstraintSpec)
    resolved_plan: ResolvedPlan | None = Field(
        default=None,
        description="Exact plan returned by POST /v1/resolve.",
    )


class CandidateColumn(BaseModel):
    source: str
    column: str
    role: str
    magnitude: str
    formula: str | None
    confidence: float
    score_components: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    query_id: str
    result: Any
    result_type: str  # scalar | table | none
    confidence: float
    plan: list[str]  # reasoning chain
    resolved_column: str
    resolved_role: str
    resolved_source: str
    row_count: int
    candidates: list[CandidateColumn]  # all scored column candidates
    source_scores: dict[str, float]  # source resolver scores — for LLM disambiguation
    ambiguous: bool  # True when source resolver confidence < 0.40
    exact_spec: bool  # True when LLM provided exact source+column names
    explanation: list[str] = []  # human-readable execution explanation
    latency_ms: float
    decision_path: str
    plan_hash: str
    schema_revision: str | None = None
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    source_set: list[str] = []
    join_path: list[dict[str, Any]] = []
    planner_mode: str = "planner_hint"


class ResolveResponse(BaseModel):
    resolved_plan: ResolvedPlan | None = None
    confidence: float
    plan: list[str]
    explanation: list[str] = Field(default_factory=list)
    resolved_column: str = ""
    resolved_role: str = ""
    resolved_source: str = ""
    candidates: list[CandidateColumn] = Field(default_factory=list)
    source_scores: dict[str, float] = Field(default_factory=dict)
    latency_ms: float
    decision_path: str
    plan_hash: str | None = None
    schema_revision: str
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    intent_signature: str
    source_set: list[str] = Field(default_factory=list)
    join_path: list[dict[str, Any]] = Field(default_factory=list)
    planner_mode: str = "registry_planner"


QueryPayload = QueryRequest


_DECISION_AUTO_ACCEPT_CONFIDENCE = 0.85
_DECISION_CLARIFY_CONFIDENCE = 0.70
_DECISION_MIN_CANDIDATE_GAP = 0.10
_COUNT_ANCHOR_ROLE_PRIORITY = (
    "identifier",
    "base_measure",
    "metric",
    "derived_measure",
    "unit_measure",
    "text",
    "category",
    "time",
)


def _candidate_confidence(candidate: CandidateColumn | dict[str, Any]) -> float:
    if isinstance(candidate, CandidateColumn):
        return float(candidate.confidence)
    return float(candidate.get("confidence", 0.0) or 0.0)


def _candidate_confidence_gap(
    candidates: list[CandidateColumn] | list[dict[str, Any]],
) -> float | None:
    if len(candidates) < 2:
        return None
    ordered = sorted(candidates, key=_candidate_confidence, reverse=True)
    return round(_candidate_confidence(ordered[0]) - _candidate_confidence(ordered[1]), 3)


def _classify_query_rejection(error_text: str | None) -> str | None:
    if not error_text:
        return None

    lowered = error_text.lower()
    if any(token in lowered for token in ("stale", "freshness")):
        return "stale_source"
    if any(token in lowered for token in ("verify", "verification", "constraint")):
        return "plan_verification_failed"
    if any(
        token in lowered
        for token in (
            "fanout",
            "many_to_many",
            "join path",
            "join_path",
            "join key",
            "join candidates",
            "no join path",
            "ambiguous multi-hop",
            "cross-source",
        )
    ):
        return "join_ambiguity"
    if any(token in lowered for token in ("schema", "column", "dimension", "source", "metadata")):
        return "schema_incomplete"
    return "schema_unresolved"


def _decision_contract_flags(
    confidence: float,
    candidates: list[CandidateColumn] | list[dict[str, Any]],
    *,
    error_text: str | None = None,
) -> tuple[bool, bool, str | None]:
    rejection_reason = _classify_query_rejection(error_text)
    if rejection_reason is not None:
        return False, False, rejection_reason
    if confidence < _DECISION_CLARIFY_CONFIDENCE:
        return False, False, "schema_unresolved"
    gap = _candidate_confidence_gap(candidates)
    if confidence < _DECISION_AUTO_ACCEPT_CONFIDENCE:
        return False, True, None
    if gap is not None and gap < _DECISION_MIN_CANDIDATE_GAP:
        return False, True, None
    return True, False, None


def _select_count_anchor_column(schema_meta: dict[str, Any]) -> tuple[str, str] | None:
    columns = schema_meta.get("columns") or []
    normalized = [
        column
        for column in columns
        if str(column.get("name", "")).strip()
    ]
    if not normalized:
        return None

    for role in _COUNT_ANCHOR_ROLE_PRIORITY:
        for column in normalized:
            if str(column.get("role", "")).strip() == role:
                return str(column["name"]), role

    first = normalized[0]
    fallback_role = str(first.get("role", "")).strip() or "metric"
    if fallback_role not in _COUNT_ANCHOR_ROLE_PRIORITY:
        fallback_role = "metric"
    return str(first["name"]), fallback_role


def _query_plan_hash(
    *,
    decision_path: str,
    schema_revision: str | None,
    basis: dict[str, Any],
) -> str:
    payload = {
        "decision_path": decision_path,
        "schema_revision": schema_revision or "",
        "basis": basis,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:24]


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
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:24]


def _normalize_candidates(
    candidates: list[CandidateColumn] | list[dict[str, Any]],
) -> list[CandidateColumn]:
    normalized: list[CandidateColumn] = []
    for candidate in candidates:
        normalized.append(
            candidate
            if isinstance(candidate, CandidateColumn)
            else CandidateColumn(**candidate)
        )
    return normalized


def _resolved_source_set(resolved_source: str) -> list[str]:
    return _dedupe_source_values(resolved_source.split("⋈"))


def _dedupe_source_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _normalize_join_path(join_path: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(hop) for hop in (join_path or []) if isinstance(hop, dict)]


def _build_query_response(
    *,
    query_id: str,
    request_id: str | None,
    result: Any,
    result_type: str,
    confidence: float,
    plan: list[str],
    resolved_column: str,
    resolved_role: str,
    resolved_source: str,
    row_count: int,
    candidates: list[CandidateColumn] | list[dict[str, Any]],
    source_scores: dict[str, float],
    ambiguous: bool,
    exact_spec: bool,
    explanation: list[str] | None,
    latency_ms: float,
    decision_path: str,
    schema_revision: str | None,
    validated: bool,
    confidence_source: str,
    plan_basis: dict[str, Any],
    clarification_required: bool = False,
    rejection_reason: str | None = None,
    deterministic_scope: str | None = None,
    source_set: list[str] | None = None,
    join_path: list[dict[str, Any]] | None = None,
    planner_mode: str | None = None,
    plan_hash_override: str | None = None,
) -> QueryResponse:
    normalized_candidates = _normalize_candidates(candidates)
    resolved_sources = source_set or _resolved_source_set(resolved_source)
    normalized_join_path = _normalize_join_path(join_path)
    response_planner_mode = planner_mode or ("exact_spec" if exact_spec else decision_path)
    plan_hash = plan_hash_override or _query_plan_hash(
        decision_path=decision_path,
        schema_revision=schema_revision,
        basis=plan_basis,
    )
    response = QueryResponse(
        query_id=query_id,
        result=result,
        result_type=result_type,
        confidence=confidence,
        plan=plan,
        resolved_column=resolved_column,
        resolved_role=resolved_role,
        resolved_source=resolved_source,
        row_count=row_count,
        candidates=normalized_candidates,
        source_scores=source_scores,
        ambiguous=ambiguous,
        exact_spec=exact_spec,
        explanation=explanation or [],
        latency_ms=latency_ms,
        decision_path=decision_path,
        plan_hash=plan_hash,
        schema_revision=schema_revision,
        validated=validated,
        deterministic_scope=(
            deterministic_scope
            or ("verified_execution" if validated else "planning_only")
        ),
        confidence_source=confidence_source,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        request_id=request_id,
        source_set=resolved_sources,
        join_path=normalized_join_path,
        planner_mode=response_planner_mode,
    )
    logger.info(
        "query_response",
        request_id=request_id,
        query_id=query_id,
        plan_hash=plan_hash,
        schema_revision=schema_revision,
        decision_path=decision_path,
        validated=validated,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        confidence=round(confidence, 3),
        exact_spec=exact_spec,
        resolved_source=resolved_source,
        source_set=resolved_sources,
        planner_mode=response_planner_mode,
    )
    return response


def _build_resolve_response(
    *,
    resolved_plan: ResolvedPlan | None,
    confidence: float,
    plan: list[str],
    explanation: list[str] | None,
    resolved_column: str,
    resolved_role: str,
    resolved_source: str,
    candidates: list[CandidateColumn] | list[dict[str, Any]],
    source_scores: dict[str, float],
    latency_ms: float,
    schema_revision: str,
    validated: bool,
    confidence_source: str,
    request_id: str | None,
    intent_signature: str,
    clarification_required: bool = False,
    rejection_reason: str | None = None,
    source_set: list[str] | None = None,
    join_path: list[dict[str, Any]] | None = None,
    planner_mode: str = "registry_planner",
) -> ResolveResponse:
    normalized_candidates = _normalize_candidates(candidates)[:_MAX_RESOLVE_CANDIDATES]
    normalized_source_scores = dict(
        sorted(
            source_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:_MAX_RESOLVE_SOURCE_SCORES]
    )
    exact_basis = (
        _exact_plan_basis(
            source_name=resolved_plan.source_name,
            metric_column=resolved_plan.metric_column,
            aggregation=resolved_plan.aggregation,
            group_column=resolved_plan.group_column,
            join_path=resolved_plan.join_path,
            filter_spec=resolved_plan.filter,
            limit=resolved_plan.limit,
            order=resolved_plan.order,
            constraints=resolved_plan.constraints,
        )
        if resolved_plan is not None
        else None
    )
    return ResolveResponse(
        resolved_plan=resolved_plan,
        confidence=confidence,
        plan=plan,
        explanation=explanation or [],
        resolved_column=resolved_column,
        resolved_role=resolved_role,
        resolved_source=resolved_source,
        candidates=normalized_candidates,
        source_scores=normalized_source_scores,
        latency_ms=latency_ms,
        decision_path="resolve",
        plan_hash=(
            _immutable_plan_hash(schema_revision=schema_revision, basis=exact_basis)
            if exact_basis is not None
            else None
        ),
        schema_revision=schema_revision,
        validated=validated,
        deterministic_scope="resolved_execution_plan" if validated else "planning_only",
        confidence_source=confidence_source,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        request_id=request_id,
        intent_signature=intent_signature,
        source_set=source_set or _resolved_source_set(resolved_source),
        join_path=_normalize_join_path(join_path),
        planner_mode=planner_mode,
    )


def _resolve_to_query_response(
    *,
    query_id: str,
    resolve_response: ResolveResponse,
) -> QueryResponse:
    return _build_query_response(
        query_id=query_id,
        request_id=resolve_response.request_id,
        result=None,
        result_type="none",
        confidence=resolve_response.confidence,
        plan=resolve_response.plan,
        resolved_column=resolve_response.resolved_column,
        resolved_role=resolve_response.resolved_role,
        resolved_source=resolve_response.resolved_source,
        row_count=0,
        candidates=resolve_response.candidates,
        source_scores=resolve_response.source_scores,
        ambiguous=True,
        exact_spec=False,
        explanation=resolve_response.explanation,
        latency_ms=resolve_response.latency_ms,
        decision_path="resolve",
        schema_revision=resolve_response.schema_revision,
        validated=False,
        confidence_source=resolve_response.confidence_source,
        plan_basis={"intent_signature": resolve_response.intent_signature},
        clarification_required=resolve_response.clarification_required,
        rejection_reason=resolve_response.rejection_reason,
        deterministic_scope="planning_only",
        source_set=resolve_response.source_set,
        join_path=resolve_response.join_path,
        planner_mode=resolve_response.planner_mode,
        plan_hash_override=resolve_response.plan_hash,
    )


def _compute_exact_confidence(
    metric_node: ColumnNode,
    aggregation: str,
    join_confidence: float = 1.0,
) -> tuple[float, float, float]:
    """
    Returns (final_confidence, col_conf, agg_conf).

    Confidence = column_confidence × aggregation_confidence × join_confidence

    column_confidence — how structurally certain we are this is the right column:
      derived_measure with formula → 1.00
      derived_measure no formula   → 0.90
      base_measure / unit_measure  → 0.85
      component                    → 0.80
      metric (unclassified)        → 0.75
      anything else                → 0.65

    aggregation_confidence — does the aggregation make sense for this role:
      sum   on derived_measure / component  → 1.00
      sum   on base_measure / unit_measure  → 0.90
      sum   on metric                       → 0.85
      avg   on unit_measure / metric        → 1.00
      avg   on derived_measure              → 0.85
      avg   on base_measure                 → 0.80
      count (always valid)                  → 0.95
      max/min (always valid)                → 0.95
      anything else                         → 0.80

    join_confidence — from the join key registry confidence (0.0–1.0).
      No join → 1.0
    """
    role = metric_node.role
    has_formula = bool(metric_node.formula)

    # column_confidence
    if role == "derived_measure":
        col_conf = 1.00 if has_formula else 0.90
    elif role in ("base_measure", "unit_measure"):
        col_conf = 0.85
    elif role == "component":
        col_conf = 0.80
    elif role == "metric":
        col_conf = 0.75
    else:
        col_conf = 0.65

    # aggregation_confidence
    agg = aggregation.lower()
    if agg == "count":
        agg_conf = 0.95
    elif agg in ("max", "min"):
        agg_conf = 0.95
    elif agg == "sum":
        if role in ("derived_measure", "component"):
            agg_conf = 1.00
        elif role in ("base_measure", "unit_measure"):
            agg_conf = 0.90
        else:
            agg_conf = 0.85
    elif agg == "avg":
        if role in ("unit_measure", "metric"):
            agg_conf = 1.00
        elif role == "derived_measure":
            agg_conf = 0.85
        else:
            agg_conf = 0.80
    else:
        agg_conf = 0.80

    final = round(col_conf * agg_conf * join_confidence, 3)
    return final, col_conf, agg_conf


def _resolve_entry_ready(entry: dict[str, Any]) -> bool:
    return bool(entry.get("schema_revision")) and bool(entry.get("decision_mode"))


def _resolve_scope_entries(
    *,
    org_id: str,
    auth: AuthContext,
    dataset_id: str | None,
    allow_org_scope: bool,
    request_id: str | None,
) -> tuple[list[dict[str, Any]], str | None]:
    from apps.api_server.services import source_registry as _sreg_visible
    from apps.api_server.services.data_visibility import (
        filter_visible_datasets,
        get_visible_dataset_entry,
    )

    if dataset_id:
        dataset_entry = get_visible_dataset_entry(org_id, dataset_id, auth)
        if dataset_entry is None:
            raise _http_error(
                404,
                code="not_found",
                message=f"Dataset '{dataset_id}' not found.",
                request_id=request_id,
            )
        return [dataset_entry], dataset_id
    visible_entries = filter_visible_datasets(_sreg_visible.list_sources(org_id), auth)
    if allow_org_scope:
        return visible_entries, None
    if len(visible_entries) == 1:
        only_entry = visible_entries[0]
        return [only_entry], str(only_entry.get("id") or "")
    raise _http_error(
        422,
        code="dataset_scope_required",
        message=(
            "resolve requires dataset_id unless allow_org_scope=true "
            "or only one visible dataset exists."
        ),
        request_id=request_id,
    )


def _resolved_plan_current_schema_revision(
    *,
    org_id: str,
    resolved_plan: ResolvedPlan,
    dataset_id: str | None = None,
    visible_entries: list[dict[str, Any]] | None = None,
) -> str:
    from apps.api_server.services import source_registry as _sreg_resolved

    join_edges = getattr(resolved_plan.join_path, "edges", None)
    if join_edges:
        return _sreg_resolved.schema_revision(org_id)

    source_id = dataset_id
    if not source_id:
        matched_entry: dict[str, Any] | None = None
        if visible_entries is not None:
            matched_entry = next(
                (
                    entry
                    for entry in visible_entries
                    if str(entry.get("name") or "") == resolved_plan.source_name
                ),
                None,
            )
        else:
            matched_entry = _sreg_resolved.get_source_entry_by_name(
                org_id,
                resolved_plan.source_name,
            )
        if matched_entry is not None:
            source_id = str(matched_entry.get("id") or "")

    if source_id:
        return _sreg_resolved.source_schema_revision(org_id, source_id)
    return _sreg_resolved.schema_revision(org_id)


def _find_exact_dataset_column(
    schema_meta: dict[str, Any],
    normalized_hint: str,
) -> dict[str, Any] | None:
    if not normalized_hint:
        return None

    matches = [
        column
        for column in (schema_meta.get("columns") or [])
        if _normalize_hint_text(str(column.get("name", ""))) == normalized_hint
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _dataset_exact_column_lookup(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    schema_meta: dict[str, Any],
) -> dict[str, dict[str, Any] | None]:
    cache_key = (org_id, dataset_id, schema_revision)
    cached = _dataset_exact_column_cache_get(cache_key)
    if cached is not None:
        return cached

    lookup: dict[str, dict[str, Any] | None] = {}
    for column in schema_meta.get("columns") or []:
        normalized_name = _normalize_hint_text(str(column.get("name", "")))
        if not normalized_name:
            continue
        existing = lookup.get(normalized_name)
        if existing is None and normalized_name in lookup:
            continue
        if existing is None and normalized_name not in lookup:
            lookup[normalized_name] = column
        else:
            lookup[normalized_name] = None
    return _dataset_exact_column_cache_put(cache_key, lookup)


def _find_exact_dataset_column_cached(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    schema_meta: dict[str, Any],
    normalized_hint: str,
) -> dict[str, Any] | None:
    if not normalized_hint:
        return None
    return _dataset_exact_column_lookup(
        org_id=org_id,
        dataset_id=dataset_id,
        schema_revision=schema_revision,
        schema_meta=schema_meta,
    ).get(normalized_hint)


def _dataset_candidate_payload(
    *,
    source_name: str,
    column_name: str,
    node: ColumnNode,
    confidence: float,
    notes: list[str],
    score_components: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "source": source_name,
        "column": column_name,
        "role": node.role,
        "magnitude": node.magnitude_class,
        "formula": node.formula,
        "confidence": round(confidence, 3),
        "score_components": score_components or {},
        "notes": list(dict.fromkeys(notes)),
    }


async def _get_resolve_dataset_meta(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
) -> tuple[dict[str, Any] | None, dict[str, ColumnNode] | None]:
    async with _CACHE_LOCK:
        cached = _SOURCE_CACHE.get(dataset_id)
        if cached and cached.is_fresh():
            cached.touch()
            schema_meta = cached.schema_meta
            if not schema_meta and cached.parquet_schema_meta:
                parsed = json.loads(cached.parquet_schema_meta)
                if isinstance(parsed, dict):
                    cached.schema_meta = parsed
                    schema_meta = parsed
            graph_nodes = cached.graph_nodes or None
            if graph_nodes is None and isinstance(schema_meta, dict):
                graph_nodes = _graph_nodes_from_cached_meta(
                    org_id=org_id,
                    dataset_id=dataset_id,
                    schema_revision=schema_revision,
                    schema_meta=schema_meta,
                )
                cached.graph_nodes = graph_nodes
            return (
                schema_meta if isinstance(schema_meta, dict) else None,
                graph_nodes,
            )

    from apps.api_server.services import source_registry as _sreg_dataset_meta

    schema_meta = _sreg_dataset_meta.get_source_meta(org_id, dataset_id)
    if not isinstance(schema_meta, dict):
        return None, None
    return (
        schema_meta,
        _graph_nodes_from_cached_meta(
            org_id=org_id,
            dataset_id=dataset_id,
            schema_revision=schema_revision,
            schema_meta=schema_meta,
        ),
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
    source_name = str(dataset_entry.get("name", "") or "")
    plan = [
        f"Resolve scope: dataset={dataset_id}",
        "Planner mode: dataset_meta_fast_path",
    ]

    if not source_name or not isinstance(schema_meta, dict):
        return _build_resolve_response(
            resolved_plan=None,
            confidence=0.0,
            plan=plan + ["Dataset metadata missing for single-source resolve."],
            explanation=[],
            resolved_column="",
            resolved_role="",
            resolved_source=source_name,
            candidates=[],
            source_scores={source_name: 1.0} if source_name else {},
            latency_ms=round((time.monotonic() - started_at) * 1000, 1),
            schema_revision=schema_revision,
            validated=False,
            confidence_source="dataset_metadata_confidence",
            request_id=request_id,
            intent_signature=intent_signature,
            clarification_required=False,
            rejection_reason="schema_incomplete",
            source_set=[source_name] if source_name else [],
            join_path=[],
            planner_mode="dataset_meta_fast_path",
        )

    graph_nodes = cached_nodes or _graph_nodes_from_meta(schema_meta)
    graph = {source_name: graph_nodes}
    nodes = graph.get(source_name, {})
    if not nodes:
        return _build_resolve_response(
            resolved_plan=None,
            confidence=0.0,
            plan=plan + ["Dataset schema graph is empty."],
            explanation=[],
            resolved_column="",
            resolved_role="",
            resolved_source=source_name,
            candidates=[],
            source_scores={source_name: 1.0},
            latency_ms=round((time.monotonic() - started_at) * 1000, 1),
            schema_revision=schema_revision,
            validated=False,
            confidence_source="dataset_metadata_confidence",
            request_id=request_id,
            intent_signature=intent_signature,
            clarification_required=False,
            rejection_reason="schema_incomplete",
            source_set=[source_name],
            join_path=[],
            planner_mode="dataset_meta_fast_path",
        )

    normalized_metric_hint = _normalize_hint_text(metric_hint)
    normalized_group_hints = _stable_list(combined_group_by)
    metric_candidates: list[dict[str, Any]] = []
    validation_notes: list[str] = []

    metric_col = ""
    metric_role = payload.metric.role
    metric_conf = 0.0

    if payload.aggregation == "count":
        count_anchor = _select_count_anchor_column(schema_meta)
        if count_anchor is None:
            validation_notes.append("Dataset metadata is missing a COUNT anchor column.")
        else:
            metric_col, metric_role = count_anchor
            metric_conf = 1.0
            metric_node = nodes.get(metric_col)
            if metric_node is not None:
                metric_candidates = [
                    _dataset_candidate_payload(
                        source_name=source_name,
                        column_name=metric_col,
                        node=metric_node,
                        confidence=1.0,
                        notes=["count-anchor", "dataset-scope"],
                        score_components={"count_anchor": 1.0},
                    )
                ]
            plan.append(f"COUNT anchor fallback: {source_name}.{metric_col} ({metric_role})")
    else:
        exact_metric = _find_exact_dataset_column_cached(
            org_id=org_id,
            dataset_id=dataset_id,
            schema_revision=schema_revision,
            schema_meta=schema_meta,
            normalized_hint=normalized_metric_hint,
        )
        if exact_metric is not None:
            exact_metric_name = str(exact_metric.get("name", "") or "")
            exact_metric_node = nodes.get(exact_metric_name)
            if exact_metric_node is None:
                validation_notes.append(
                    "Dataset metadata column "
                    f"'{exact_metric_name}' is not available in the schema graph."
                )
            elif not exact_metric_node.is_numeric:
                validation_notes.append(
                    f"Dataset column '{exact_metric_name}' is not numeric "
                    "and cannot be used as a metric."
                )
            else:
                metric_col = exact_metric_name
                metric_role = exact_metric_node.role
                metric_conf = 1.0
                metric_candidates = [
                    _dataset_candidate_payload(
                        source_name=source_name,
                        column_name=metric_col,
                        node=exact_metric_node,
                        confidence=1.0,
                        notes=["exact-column-match", "dataset-scope"],
                        score_components={"exact_match": 1.0},
                    )
                ]
                plan.append(
                    f"Metric exact match: {source_name}.{metric_col} ({metric_role})"
                )
        if not metric_col:
            hint_tokens = set(re.findall(r"[a-z0-9]+", normalized_metric_hint.lower()))
            metric_src, resolved_metric_col, resolved_metric_conf, metric_candidates = (
                resolve_metric_column(
                    payload.metric.role,
                    hint_tokens,
                    graph,
                    source_name,
                )
            )
            if metric_src and resolved_metric_col:
                metric_col = resolved_metric_col
                metric_conf = resolved_metric_conf
                metric_role = (
                    str(metric_candidates[0]["role"])
                    if metric_candidates
                    else payload.metric.role
                )
                plan.append(
                    f"Metric resolved: {metric_src}.{metric_col} ({metric_role})"
                )
            else:
                validation_notes.append(
                    "No dataset-scoped metric column found for "
                    f"hint='{metric_hint or payload.metric.role}'."
                )

    group_col: str | None = None
    group_conf = 1.0
    if normalized_group_hints:
        exact_group = _find_exact_dataset_column_cached(
            org_id=org_id,
            dataset_id=dataset_id,
            schema_revision=schema_revision,
            schema_meta=schema_meta,
            normalized_hint=normalized_group_hints[0],
        )
        if exact_group is not None:
            exact_group_name = str(exact_group.get("name", "") or "")
            exact_group_node = nodes.get(exact_group_name)
            allowed_group_roles = {CATEGORY, TEXT, TIME, IDENTIFIER}
            if exact_group_node is None or exact_group_node.role not in allowed_group_roles:
                validation_notes.append(
                    f"Dataset column '{exact_group_name}' is not a valid group-by dimension."
                )
            else:
                group_col = exact_group_name
                group_conf = 1.0
                plan.append(f"Group exact match: {source_name}.{group_col}")
        if group_col is None:
            group_src, resolved_group_col, resolved_group_conf = resolve_group_column_graph(
                normalized_group_hints,
                source_name,
                graph,
            )
            if group_src and resolved_group_col:
                group_col = resolved_group_col
                group_conf = resolved_group_conf
                plan.append(f"Group resolved: {group_src}.{group_col}")
            else:
                validation_notes.append(
                    "No dataset-scoped group column found for the requested dimension hint."
                )

    confidence = round(
        min(
            metric_conf,
            group_conf if normalized_group_hints else 1.0,
        ),
        3,
    )
    plan_error_text = "; ".join(validation_notes) or None
    validated, clarification_required, rejection_reason = _decision_contract_flags(
        confidence,
        metric_candidates[:_MAX_RESOLVE_CANDIDATES],
        error_text=plan_error_text,
    )

    if (time.monotonic() - started_at) * 1000 > _RESOLVE_BUDGET_MS:
        raise _http_error(
            503,
            code="resolve_budget_exceeded",
            message="resolve exceeded the bounded 500ms planning budget.",
            request_id=request_id,
        )

    explanation: list[str] = []
    if payload.include_explanation:
        explanation = [
            f"Metric hint: {metric_hint}",
            (
                f"Resolved metric: {source_name}.{metric_col}"
                if metric_col
                else "Resolved metric: none"
            ),
            f"Aggregation: {payload.aggregation}",
        ]
        if group_col:
            explanation.append(f"Group by: {source_name}.{group_col}")
        explanation.append(f"Confidence: {confidence:.3f}")

    resolved_plan: ResolvedPlan | None = None
    if validated and metric_col:
        resolved_plan = ResolvedPlan(
            source_name=source_name,
            metric_column=metric_col,
            aggregation=payload.aggregation,
            group_column=group_col,
            join_path=None,
            filter=payload.filter,
            limit=payload.limit,
            order=payload.order,
            constraints=payload.constraints,
            schema_revision=schema_revision,
        )

    return _build_resolve_response(
        resolved_plan=resolved_plan,
        confidence=confidence,
        plan=plan,
        explanation=explanation,
        resolved_column=metric_col,
        resolved_role=metric_role if metric_col else "",
        resolved_source=source_name,
        candidates=metric_candidates[:_MAX_RESOLVE_CANDIDATES],
        source_scores={source_name: 1.0},
        latency_ms=round((time.monotonic() - started_at) * 1000, 1),
        schema_revision=schema_revision,
        validated=resolved_plan is not None,
        confidence_source="dataset_metadata_confidence",
        request_id=request_id,
        intent_signature=intent_signature,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        source_set=[source_name],
        join_path=[],
        planner_mode="dataset_meta_fast_path",
    )


async def _resolve_registered_intent(
    payload: ResolveRequest,
    *,
    auth: AuthContext,
    request_id: str | None,
) -> ResolveResponse:
    t0 = time.monotonic()
    org_id = str(auth["org_id"])
    from apps.api_server.services import source_registry as _sreg_visible

    scoped_entries, scoped_dataset_id = _resolve_scope_entries(
        org_id=org_id,
        auth=auth,
        dataset_id=payload.dataset_id,
        allow_org_scope=payload.allow_org_scope,
        request_id=request_id,
    )
    ready_entries = [entry for entry in scoped_entries if _resolve_entry_ready(entry)]
    if payload.dataset_id and not ready_entries:
        raise _http_error(
            409,
            code="source_not_ready",
            message=f"Dataset '{payload.dataset_id}' is not ready for resolve.",
            request_id=request_id,
        )
    if not payload.dataset_id:
        scoped_entries = ready_entries
    if not scoped_entries:
        schema_revision_empty = _sreg_visible.schema_revision(org_id)
        signature_payload = _intent_signature_payload(
            dataset_id=scoped_dataset_id,
            allow_org_scope=payload.allow_org_scope,
            metric_role=payload.metric.role,
            metric_hint=payload.metric.hint or "",
            group_by=payload.group_by,
            preferred_source=payload.preferred_source,
            aggregation=payload.aggregation,
            filter_spec=payload.filter,
            limit=payload.limit,
            order=payload.order,
            constraints=payload.constraints,
            raw_text=payload.raw_text,
            schema_revision=schema_revision_empty,
        )
        signature = _intent_signature(signature_payload)
        return _build_resolve_response(
            resolved_plan=None,
            confidence=0.0,
            plan=["No ready registered sources found. Use POST /v1/sources/register first."],
            explanation=[],
            resolved_column="",
            resolved_role="",
            resolved_source="",
            candidates=[],
            source_scores={},
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            schema_revision=schema_revision_empty,
            validated=False,
            confidence_source="planner_query_confidence",
            request_id=request_id,
            intent_signature=signature,
            clarification_required=False,
            rejection_reason="schema_incomplete",
            source_set=[],
            join_path=[],
        )

    single_dataset_fast_path = bool(payload.dataset_id and len(scoped_entries) == 1)
    if single_dataset_fast_path:
        schema_revision = _sreg_visible.source_schema_revision(
            org_id,
            scoped_dataset_id or str(payload.dataset_id),
        )
    else:
        schema_revision = _sreg_visible.schema_revision(org_id)
        _prune_resolve_cache(org_id, schema_revision)

    raw_metric_hint, raw_group_by = _weak_raw_text_intent(payload.raw_text)
    metric_hint = _normalize_hint_text(payload.metric.hint) or raw_metric_hint or (
        payload.metric.role.replace("_", " ")
    )
    combined_group_by = payload.group_by or raw_group_by
    dim_hint = " ".join(_stable_list(combined_group_by)) or None
    signature_payload = _intent_signature_payload(
        dataset_id=scoped_dataset_id,
        allow_org_scope=payload.allow_org_scope,
        metric_role=payload.metric.role,
        metric_hint=metric_hint,
        group_by=combined_group_by,
        preferred_source=payload.preferred_source,
        aggregation=payload.aggregation,
        filter_spec=payload.filter,
        limit=payload.limit,
        order=payload.order,
        constraints=payload.constraints,
        raw_text=payload.raw_text,
        schema_revision=schema_revision,
    )
    signature = _intent_signature(signature_payload)
    resolve_cache_key = hashlib.sha256(
        json.dumps(
            {
                "org": org_id,
                "scope": scoped_dataset_id or "__org__",
                "signature": signature,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:24]

    cached = _resolve_cache_get(resolve_cache_key)
    if cached is not None:
        cached_plan = list(cached.get("plan", []))
        cached_plan.insert(0, f"Resolve cache HIT [{resolve_cache_key[:8]}]")
        return ResolveResponse(
            **{
                **cached["response"],
                "plan": cached_plan,
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "request_id": request_id,
            }
        )

    if single_dataset_fast_path:
        dataset_meta, cached_nodes = await _get_resolve_dataset_meta(
            org_id=org_id,
            dataset_id=str(payload.dataset_id),
            schema_revision=schema_revision,
        )
        dataset_response = _resolve_single_dataset_fast_path(
            org_id=org_id,
            payload=payload,
            dataset_entry=scoped_entries[0],
            dataset_id=scoped_dataset_id or payload.dataset_id,
            schema_meta=dataset_meta,
            cached_nodes=cached_nodes,
            schema_revision=schema_revision,
            metric_hint=metric_hint,
            combined_group_by=combined_group_by,
            request_id=request_id,
            intent_signature=signature,
            started_at=t0,
        )
        _resolve_cache_put(
            resolve_cache_key,
            {
                "org_id": org_id,
                "schema_revision": schema_revision,
                "response": dataset_response.model_dump(mode="python"),
                "plan": list(dataset_response.plan),
            },
        )
        return dataset_response

    planner, planner_cache_hit, schema_revision = await _get_registry_planner(
        org_id,
        llm_policy="never",
        auth=auth,
        visible_entries=scoped_entries,
    )
    plan = [
        (
            f"Resolve scope: dataset={scoped_dataset_id}"
            if scoped_dataset_id
            else f"Resolve scope: org_visible={len(scoped_entries)}"
        ),
        f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]",
    ]

    qplan = planner.plan(
        metric_hint=metric_hint,
        dim_hint=dim_hint,
        agg=payload.aggregation,
        preferred_source=payload.preferred_source,
    )
    plan.extend(qplan.steps)

    if payload.aggregation == "count" and payload.dataset_id and not combined_group_by:
        dataset_entry = scoped_entries[0] if scoped_entries else None
        dataset_meta = (
            _sreg_visible.get_source_meta(org_id, str(payload.dataset_id))
            if payload.dataset_id
            else None
        )
        count_anchor = (
            _select_count_anchor_column(dataset_meta)
            if isinstance(dataset_meta, dict)
            else None
        )
        source_name = str(dataset_entry.get("name", "") if dataset_entry else "")
        if count_anchor and source_name:
            anchor_col, anchor_role = count_anchor
            qplan.metric_src = source_name
            qplan.metric_col = anchor_col
            qplan.metric_role = anchor_role
            qplan.metric_conf = 1.0
            qplan.error = None
            qplan.steps.append(
                f"COUNT anchor: {source_name}.{anchor_col} ({anchor_role})"
            )
            plan.append(qplan.steps[-1])

    confidence = _planner_query_confidence(qplan)
    metric_candidate_payloads = _planner_metric_candidate_payloads(
        plan=qplan,
        graph=planner.graph,
        metric_hint=metric_hint,
        target_role=qplan.metric_role or payload.metric.role,
        preferred_source=payload.preferred_source,
    )

    plan_error_text = "; ".join(
        note
        for note in [qplan.error or "", *_planner_load_bearing_validation_notes(qplan)]
        if note
    ) or None
    validated, clarification_required, rejection_reason = _decision_contract_flags(
        confidence,
        metric_candidate_payloads[:_MAX_RESOLVE_CANDIDATES],
        error_text=plan_error_text,
    )
    source_scores = (
        {qplan.metric_src: round(qplan.metric_conf, 3)}
        if qplan.metric_src
        else {}
    )
    if payload.preferred_source and source_scores:
        source_scores[payload.preferred_source] = max(
            source_scores.get(payload.preferred_source, 0.0),
            source_scores.get(qplan.metric_src or "", 0.0),
        )

    if (time.monotonic() - t0) * 1000 > _RESOLVE_BUDGET_MS:
        raise _http_error(
            503,
            code="resolve_budget_exceeded",
            message="resolve exceeded the bounded 500ms planning budget.",
            request_id=request_id,
        )

    join_path_payload = [
        {
            "left_source": hop.left_source,
            "left_key": hop.left_key,
            "right_source": hop.right_source,
            "right_key": hop.right_key,
            "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
            "cardinality": getattr(hop, "cardinality", None),
        }
        for hop in qplan.join_hops[:4]
    ]
    explanation: list[str] = []
    if payload.include_explanation:
        explanation = [
            f"Metric hint: {metric_hint}",
            f"Resolved metric: {qplan.metric_src}.{qplan.metric_col}"
            if qplan.metric_src and qplan.metric_col
            else "Resolved metric: none",
            f"Aggregation: {payload.aggregation}",
        ]
        if qplan.group_col and qplan.group_src:
            explanation.append(f"Group by: {qplan.group_src}.{qplan.group_col}")
        if qplan.join_hops:
            explanation.append(
                "Join path: "
                + " -> ".join(
                    f"{hop.left_source}.{hop.left_key}={hop.right_source}.{hop.right_key}"
                    for hop in qplan.join_hops[:4]
                )
            )
        explanation.append(f"Confidence: {confidence:.3f}")

    resolved_plan: ResolvedPlan | None = None
    if validated and qplan.metric_src and qplan.metric_col:
        join_path_spec = None
        if qplan.join_hops:
            planner_path_has_fanout = any(
                str(getattr(hop, "cardinality", "") or "").lower()
                in {"one_to_many", "many_to_many", "1:n", "n:n"}
                for hop in qplan.join_hops[:4]
            )
            join_path_spec = JoinPathSpec(
                base_source=qplan.metric_src,
                group_source=qplan.group_src or qplan.metric_src,
                edges=[
                    JoinEdgeSpec(
                        left_source=hop.left_source,
                        right_source=hop.right_source,
                        left_key=hop.left_key,
                        right_key=hop.right_key,
                        min_confidence=round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                        expected_cardinality=(
                            str(getattr(hop, "cardinality", "") or "") or None
                        ),
                        allow_many_to_many=(
                            str(getattr(hop, "cardinality", "") or "").lower() == "many_to_many"
                        ),
                    )
                    for hop in qplan.join_hops[:4]
                ],
                max_hops=4,
                min_path_confidence=round(
                    float(
                        getattr(qplan, "path_confidence", 0.0)
                        or getattr(qplan, "join_conf", 0.0)
                        or 0.0
                    ),
                    3,
                ),
                reject_on_ambiguity=True,
                reject_on_fanout=not planner_path_has_fanout,
            )
        resolved_plan = ResolvedPlan(
            source_name=qplan.metric_src,
            metric_column=qplan.metric_col,
            aggregation=payload.aggregation,
            group_column=qplan.group_col,
            join_path=join_path_spec,
            filter=payload.filter,
            limit=payload.limit,
            order=payload.order,
            constraints=payload.constraints,
            schema_revision=schema_revision,
        )

    response_schema_revision = schema_revision
    if resolved_plan is not None:
        response_schema_revision = _resolved_plan_current_schema_revision(
            org_id=org_id,
            resolved_plan=resolved_plan,
            dataset_id=scoped_dataset_id,
            visible_entries=scoped_entries,
        )
        if resolved_plan.schema_revision != response_schema_revision:
            resolved_plan = resolved_plan.model_copy(
                update={"schema_revision": response_schema_revision}
            )

    response = _build_resolve_response(
        resolved_plan=resolved_plan,
        confidence=confidence,
        plan=plan,
        explanation=explanation,
        resolved_column=qplan.metric_col or "",
        resolved_role=qplan.metric_role or "",
        resolved_source=qplan.metric_src or "",
        candidates=metric_candidate_payloads[:_MAX_RESOLVE_CANDIDATES],
        source_scores=source_scores,
        latency_ms=round((time.monotonic() - t0) * 1000, 1),
        schema_revision=response_schema_revision,
        validated=resolved_plan is not None,
        confidence_source="planner_query_confidence",
        request_id=request_id,
        intent_signature=signature,
        clarification_required=clarification_required,
        rejection_reason=rejection_reason,
        source_set=_dedupe_source_values(
            [
                qplan.metric_src or "",
                qplan.group_src or "",
                *[hop.right_source for hop in qplan.join_hops[:4]],
            ]
        ),
        join_path=join_path_payload,
        planner_mode="registry_planner",
    )

    _resolve_cache_put(
        resolve_cache_key,
        {
            "org_id": org_id,
            "schema_revision": schema_revision,
            "response": response.model_dump(mode="python"),
            "plan": list(plan),
        },
    )
    return response


def _query_uses_legacy_planning(payload: QueryRequest) -> bool:
    if payload.resolved_plan is not None:
        return False
    if payload.source_name and payload.metric_column:
        return False
    return not payload.sources


# ── Endpoint ───────────────────────────────────────────────────────────────────


@router.post(
    "/v1/resolve",
    response_model=ResolveResponse,
    summary="Resolve structured intent into an exact executable plan",
    description=(
        "**Bounded deterministic planner.**\n\n"
        "This endpoint resolves structured intent into an exact plan for `POST /v1/query`.\n"
        "It only uses registered-source metadata, join graph metadata, planner cache, and "
        "precomputed statistics. It does not scan datasets or execute queries.\n\n"
        "**Scope rules:**\n"
        "- Provide `dataset_id` for dataset-scoped planning, or\n"
        "- set `allow_org_scope=true` to plan across all visible datasets.\n\n"
        "**Deterministic guarantees:**\n"
        "- identical intent_signature + schema_revision + scope => identical output\n"
        "- ambiguity clarifies or rejects; it never expands search\n"
        "- no fallback to slower planning paths exists\n"
    ),
)
async def resolve_sources(
    payload: ResolveRequest,
    request: Request,
    auth: AuthContext = Depends(get_current_org),
) -> ResolveResponse:
    request_id = getattr(request.state, "request_id", None)
    return await _resolve_registered_intent(payload, auth=auth, request_id=request_id)


@router.post(
    "/v1/query",
    response_model=QueryResponse,
    summary="Execute a structured query — schema-free, zero domain assumptions",
    description=(
        "**Structured query execution engine.**\n\n"
        "This endpoint takes structured intent — produced by an LLM from the user's "
        "natural-language question. It does NOT accept raw text.\n\n"
        "**Separation of concerns:**\n"
        "- LLM: language → structured intent, ambiguity resolution, user interaction\n"
        "- Algenta: schema understanding, math relationships, fast execution, correctness\n\n"
        "**Role resolution:**\n"
        "1. Detect derived formulas across all numeric column triples (Mojo, ~100ms)\n"
        "2. Assign structural roles: derived_measure, base_measure, unit_measure…\n"
        "3. Match requested role → best column\n"
        "4. Execute aggregation, return result + all candidates for LLM disambiguation\n\n"
        "**Ambiguity handling:**\n"
        "If confidence < 0.7, check `candidates` — multiple columns may match the role. "
        "The LLM can present options to the user or pick the most contextually appropriate one."
    ),
)
async def query_sources(
    payload: QueryRequest,
    request: Request = None,
    auth: AuthContext = Depends(get_current_org),
) -> QueryResponse:
    t0 = time.monotonic()
    query_id = str(uuid.uuid4())
    plan: list[str] = []
    org_id = str(auth["org_id"])
    request_id = getattr(request.state, "request_id", None) if request is not None else None
    from apps.api_server.services import source_registry as _sreg_visible
    from apps.api_server.services.data_visibility import (
        filter_visible_datasets,
        get_visible_dataset_entry,
    )
    visible_registry_entries: list[dict[str, Any]] | None = None
    resolved_plan_schema_revision: str | None = None

    def _visible_registry_entries() -> list[dict[str, Any]]:
        nonlocal visible_registry_entries
        if visible_registry_entries is None:
            visible_registry_entries = filter_visible_datasets(
                _sreg_visible.list_sources(org_id),
                auth,
            )
        return visible_registry_entries

    if (
        payload.resolved_plan is not None
        and not payload.dataset_id
        and str(auth.get("role", "")).lower() == "owner"
    ):
        current_schema_revision = _resolved_plan_current_schema_revision(
            org_id=org_id,
            resolved_plan=payload.resolved_plan,
        )
        resolved_plan_schema_revision = current_schema_revision
        if payload.resolved_plan.schema_revision != current_schema_revision:
            raise _http_error(
                409,
                code="schema_revision_mismatch",
                message=(
                    "resolved_plan schema_revision no longer matches the current registry state."
                ),
                request_id=request_id,
            )

        owner_plan_basis = _exact_plan_basis(
            source_name=payload.resolved_plan.source_name,
            metric_column=payload.resolved_plan.metric_column,
            aggregation=payload.resolved_plan.aggregation,
            group_column=payload.resolved_plan.group_column,
            join_path=payload.resolved_plan.join_path,
            filter_spec=payload.resolved_plan.filter,
            limit=payload.resolved_plan.limit,
            order=payload.resolved_plan.order,
            constraints=payload.resolved_plan.constraints,
        )
        owner_plan_hash = _immutable_plan_hash(
            schema_revision=current_schema_revision,
            basis=owner_plan_basis,
        )
        owner_cached_result = _RESULT_CACHE.get(owner_plan_hash)
        if owner_cached_result and (
            time.monotonic() - owner_cached_result.get("_ts", 0)
        ) < _RESULT_CACHE_TTL:
            plan.extend(
                [
                    f"Resolved plan accepted [{payload.resolved_plan.schema_revision[:8]}]",
                    f"Result cache HIT [{owner_plan_hash[:8]}] — zero I/O",
                ]
            )
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=owner_cached_result["result"],
                result_type=owner_cached_result["result_type"],
                confidence=owner_cached_result["confidence"],
                plan=plan,
                resolved_column=payload.resolved_plan.metric_column,
                resolved_role=owner_cached_result.get("resolved_role", ""),
                resolved_source=owner_cached_result.get(
                    "resolved_source",
                    payload.resolved_plan.source_name,
                ),
                row_count=owner_cached_result["row_count"],
                candidates=[],
                source_scores={},
                ambiguous=False,
                exact_spec=True,
                explanation=owner_cached_result.get("explanation", []),
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="exact_spec",
                schema_revision=current_schema_revision,
                validated=True,
                confidence_source="exact_spec_validation",
                plan_basis=owner_plan_basis,
                plan_hash_override=owner_plan_hash,
            )

    if payload.dataset_id:
        if payload.sources:
            raise _http_error(
                422,
                code="invalid_query_request",
                message="dataset_id cannot be combined with inline sources.",
                request_id=request_id,
            )
        dataset_entry = get_visible_dataset_entry(org_id, payload.dataset_id, auth)
        if dataset_entry is None:
            raise _http_error(
                404,
                code="not_found",
                message=f"Dataset '{payload.dataset_id}' not found.",
                request_id=request_id,
            )
        visible_registry_entries = [dataset_entry]
        if payload.source_name is None:
            payload.source_name = str(dataset_entry.get("name") or "")
        if payload.preferred_source is None:
            payload.preferred_source = str(dataset_entry.get("name") or "")
        plan.append(
            f"Dataset scope: {payload.dataset_id} -> "
            f"{payload.source_name or payload.preferred_source}"
        )

    if payload.resolved_plan is not None:
        visible_entries_for_resolved_plan: list[dict[str, Any]] | None = None
        if not payload.dataset_id and str(auth.get("role", "")).lower() != "owner":
            visible_entries_for_resolved_plan = _visible_registry_entries()
        current_schema_revision = _resolved_plan_current_schema_revision(
            org_id=org_id,
            resolved_plan=payload.resolved_plan,
            dataset_id=payload.dataset_id,
            visible_entries=visible_entries_for_resolved_plan,
        )
        resolved_plan_schema_revision = current_schema_revision
        if payload.resolved_plan.schema_revision != current_schema_revision:
            raise _http_error(
                409,
                code="schema_revision_mismatch",
                message=(
                    "resolved_plan schema_revision no longer matches the current registry state."
                ),
                request_id=request_id,
            )
        if payload.dataset_id:
            allowed_sources = {
                str(entry.get("name") or "")
                for entry in _visible_registry_entries()
            }
            if payload.resolved_plan.source_name not in allowed_sources:
                raise _http_error(
                    422,
                    code="dataset_scope_violation",
                    message=(
                        "resolved_plan source_name is outside the requested dataset scope."
                    ),
                    request_id=request_id,
                )
        payload.source_name = payload.resolved_plan.source_name
        payload.metric_column = payload.resolved_plan.metric_column
        payload.group_column = payload.resolved_plan.group_column
        payload.join_path = payload.resolved_plan.join_path
        payload.aggregation = payload.resolved_plan.aggregation
        payload.filter = payload.resolved_plan.filter
        payload.limit = payload.resolved_plan.limit
        payload.order = payload.resolved_plan.order
        payload.constraints = payload.resolved_plan.constraints
        plan.append(
            f"Resolved plan accepted [{payload.resolved_plan.schema_revision[:8]}]"
        )

    if _query_uses_legacy_planning(payload):
        if not _ALLOW_QUERY_HINT_PLANNING_COMPAT:
            raise _http_error(
                422,
                code="planning_not_allowed_on_query",
                message="Use POST /v1/resolve before POST /v1/query.",
                request_id=request_id,
            )
        resolve_response = await _resolve_registered_intent(
            ResolveRequest(
                dataset_id=payload.dataset_id,
                metric=payload.metric,
                group_by=payload.group_by,
                preferred_source=payload.preferred_source,
                reject_on_ambiguity=payload.reject_on_ambiguity,
                min_source_confidence=payload.min_source_confidence,
                aggregation=payload.aggregation,
                filter=payload.filter,
                limit=payload.limit,
                order=payload.order,
                constraints=payload.constraints,
                allow_org_scope=True,
                include_explanation=False,
            ),
            auth=auth,
            request_id=request_id,
        )
        plan.append("Deprecated query planning compatibility used; prefer POST /v1/resolve.")
        if resolve_response.resolved_plan is None:
            resolve_query_response = _resolve_to_query_response(
                query_id=query_id,
                resolve_response=resolve_response,
            )
            resolve_query_response.plan.insert(0, plan[-1])
            return resolve_query_response
        payload.source_name = resolve_response.resolved_plan.source_name
        payload.metric_column = resolve_response.resolved_plan.metric_column
        payload.group_column = resolve_response.resolved_plan.group_column
        payload.join_path = resolve_response.resolved_plan.join_path
        payload.aggregation = resolve_response.resolved_plan.aggregation
        payload.filter = resolve_response.resolved_plan.filter
        payload.limit = resolve_response.resolved_plan.limit
        payload.order = resolve_response.resolved_plan.order
        payload.constraints = resolve_response.resolved_plan.constraints
        plan.extend(resolve_response.plan)

    # ══════════════════════════════════════════════════════════════════════
    # EXACT-SPEC PATH — LLM supplied source_name + metric_column explicitly.
    # Mojo verifies and executes: no source resolver, no column resolver,
    # no semantic guessing. This is the correct production path.
    # ══════════════════════════════════════════════════════════════════════
    if payload.source_name and payload.metric_column:
        plan.append(
            f"Exact-spec: source={payload.source_name}  metric={payload.metric_column}"
            + (f"  group={payload.group_column}" if payload.group_column else "")
            + (f"  join_hops={len(payload.join_path.edges)}" if payload.join_path else "")
        )

        import pandas as pd

        from apps.api_server.services import source_registry as _sreg_ex
        if resolved_plan_schema_revision is not None:
            schema_revision_exact = resolved_plan_schema_revision
        elif payload.dataset_id and not payload.join_path:
            schema_revision_exact = _sreg_ex.source_schema_revision(org_id, str(payload.dataset_id))
        elif payload.join_path:
            schema_revision_exact = _sreg_ex.schema_revision(org_id)
        else:
            exact_visible_entries = visible_registry_entries
            if exact_visible_entries is None and str(auth.get("role", "")).lower() != "owner":
                exact_visible_entries = _visible_registry_entries()
            schema_revision_exact = _resolved_plan_current_schema_revision(
                org_id=org_id,
                resolved_plan=ResolvedPlan(
                    source_name=payload.source_name,
                    metric_column=payload.metric_column,
                    aggregation=payload.aggregation,
                    group_column=payload.group_column,
                    join_path=payload.join_path,
                    filter=payload.filter,
                    limit=payload.limit,
                    order=payload.order,
                    constraints=payload.constraints,
                    schema_revision="",
                ),
                dataset_id=payload.dataset_id,
                visible_entries=exact_visible_entries,
            )
        exact_plan_basis = _exact_plan_basis(
            source_name=payload.source_name,
            metric_column=payload.metric_column,
            aggregation=payload.aggregation,
            group_column=payload.group_column,
            join_path=payload.join_path,
            filter_spec=payload.filter,
            limit=payload.limit,
            order=payload.order,
            constraints=payload.constraints,
        )
        exact_plan_hash = _immutable_plan_hash(
            schema_revision=schema_revision_exact,
            basis=exact_plan_basis,
        )

        # ── Result cache check (BEFORE any I/O) ───────────────────────────────
        # Plan key is built from request payload — no source I/O needed.
        _plan_key_early = exact_plan_hash

        _cached_early = _RESULT_CACHE.get(_plan_key_early)
        if _cached_early and (time.monotonic() - _cached_early.get("_ts", 0)) < _RESULT_CACHE_TTL:
            plan.append(f"Result cache HIT [{_plan_key_early[:8]}] — zero I/O")
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=_cached_early["result"],
                result_type=_cached_early["result_type"],
                confidence=_cached_early["confidence"],
                plan=plan,
                resolved_column=payload.metric_column,
                resolved_role=_cached_early.get("resolved_role", ""),
                resolved_source=_cached_early.get("resolved_source", payload.source_name),
                row_count=_cached_early["row_count"],
                candidates=[],
                source_scores={},
                ambiguous=False,
                exact_spec=True,
                explanation=_cached_early.get("explanation", []),
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="exact_spec",
                schema_revision=schema_revision_exact,
                validated=True,
                confidence_source="exact_spec_validation",
                plan_basis=exact_plan_basis,
                plan_hash_override=exact_plan_hash,
            )

        if payload.dataset_id and visible_registry_entries is not None:
            registered_ex = {
                str(entry.get("name") or ""): entry
                for entry in visible_registry_entries
            }
        elif str(auth.get("role", "")).lower() == "owner" and payload.source_name:
            owner_entry = _sreg_visible.get_source_entry_by_name(org_id, payload.source_name)
            registered_ex = (
                {str(owner_entry.get("name") or ""): owner_entry}
                if owner_entry is not None
                else {}
            )
        else:
            registered_ex = {
                str(entry.get("name") or ""): entry
                for entry in _visible_registry_entries()
            }
        for exact_source_name in _exact_query_required_sources(payload):
            if exact_source_name in registered_ex:
                continue
            extra_entry = _sreg_visible.get_source_entry_by_name(org_id, exact_source_name)
            if extra_entry is not None:
                registered_ex[exact_source_name] = extra_entry
        if payload.source_name not in registered_ex:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "source_not_found",
                        "message": f"Source '{payload.source_name}' not registered. "
                        f"Available: {sorted(registered_ex)}",
                    }
                },
            )

        def _load_exact(name: str) -> tuple[list[dict], dict[str, ColumnNode]]:
            """Load records + graph nodes for an exact-spec source.
            Three-tier cache: DataFrame cache → Parquet bytes cache → disk.
            """
            entry_meta = registered_ex.get(name)
            if not entry_meta:
                raise ValueError(f"Source '{name}' not registered")
            src_id = entry_meta["id"]

            # Tier 1: DataFrame cache — fastest, no deserialization
            cached_df = _df_cache_get(src_id)
            if cached_df is not None:
                plan.append(f"DF cache HIT [{name}] — DataFrame hot")
                nodes = _SOURCE_CACHE[src_id].graph_nodes if src_id in _SOURCE_CACHE else {}
                if not nodes:
                    schema_meta = _sreg_ex.get_source_meta(org_id, src_id) or {}
                    nodes = _graph_nodes_from_cached_meta(
                        org_id=org_id,
                        dataset_id=src_id,
                        schema_revision=str(entry_meta.get("schema_revision", "") or ""),
                        schema_meta=schema_meta,
                    )
                return _df_cache_records(src_id, cached_df), nodes

            # Tier 2: Parquet bytes in memory — parse once, store DataFrame
            cached = _SOURCE_CACHE.get(src_id)
            if cached and cached.is_fresh():
                cached.touch()
                plan.append(f"Parquet cache HIT [{name}] — parsing bytes")
                buf = io.BytesIO(cached.parquet_bytes)
                initialize_pyarrow_parquet_runtime()
                df = pd.read_parquet(buf)
                _df_cache_put(src_id, df)
                cached_frame = _df_cache_get(src_id)
                assert cached_frame is not None
                return _df_cache_records(src_id, cached_frame), cached.graph_nodes

            # Tier 3: Disk fallback
            plan.append(f"Cache MISS [{name}] — reading from disk")
            parquet_bytes = _sreg_ex.get_source_parquet(org_id, src_id)
            if not parquet_bytes:
                raise ValueError(f"No data for source '{name}'")
            schema_meta = _sreg_ex.get_source_meta(org_id, src_id) or {}
            nodes = _graph_nodes_from_cached_meta(
                org_id=org_id,
                dataset_id=src_id,
                schema_revision=str(entry_meta.get("schema_revision", "") or ""),
                schema_meta=schema_meta,
            )
            buf = io.BytesIO(parquet_bytes)
            initialize_pyarrow_parquet_runtime()
            df = pd.read_parquet(buf)
            _df_cache_put(src_id, df)
            cached_frame = _df_cache_get(src_id)
            assert cached_frame is not None
            return _df_cache_records(src_id, cached_frame), nodes

        try:
            metric_records, metric_nodes = _load_exact(payload.source_name)
        except ValueError as _e:
            raise HTTPException(
                status_code=404,
                detail={"error": {"code": "load_error", "message": str(_e)}},
            ) from _e

        # Validate metric column exists
        if payload.metric_column not in metric_nodes:
            available = sorted(metric_nodes.keys())
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "column_not_found",
                        "message": (
                            f"Column '{payload.metric_column}' not in "
                            f"'{payload.source_name}'. Available columns: {available[:20]}"
                        ),
                        "suggestions": [
                            c for c in available if payload.metric_column.lower() in c.lower()
                        ][:5],
                    }
                },
            )

        metric_node = metric_nodes[payload.metric_column]

        # ── Constraint enforcement ────────────────────────────────────────────────
        if payload.constraints.requires_derived and metric_node.role != "derived_measure":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "constraint_violated",
                        "constraint": "requires_derived",
                        "reason": (
                            f"Column '{payload.metric_column}' has role "
                            f"'{metric_node.role}', not 'derived_measure'."
                        ),
                        "suggestion": (
                            "Use a column with role=derived_measure. "
                            f"Available in {payload.source_name}: "
                        )
                        + str(
                            [c for c, n in metric_nodes.items() if n.role == "derived_measure"][:5]
                        ),
                    }
                },
            )

        if payload.constraints.no_cross_source and payload.join_path and payload.join_path.edges:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "constraint_violated",
                        "constraint": "no_cross_source",
                        "reason": "Cross-source join requested but no_cross_source=true.",
                    }
                },
            )

        # Validate group column if given
        group_col_ex: str | None = payload.group_column
        cross_ex = False
        join_confidence_ex: float = 1.0
        join_path_edges_ex: list[JoinEdgeSpec] = []
        join_group_source_ex: str | None = None
        join_edge_meta_ex: list[tuple[float, str]] = []
        join_records_ex: dict[str, list[dict]] = {payload.source_name: metric_records}

        if group_col_ex:
            if group_col_ex in metric_nodes:
                # Same source — no join needed
                pass
            elif payload.join_path:
                try:
                    _reg_conns_ex = _sreg_ex.get_connections(org_id)
                    (
                        join_path_edges_ex,
                        join_group_source_ex,
                        join_confidence_ex,
                        join_edge_meta_ex,
                    ) = _resolve_join_path(
                        payload.source_name,
                        payload.join_path,
                        _reg_conns_ex,
                    )
                except ValueError as _e:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": {
                                "code": "join_path_invalid",
                                "message": str(_e),
                            }
                        },
                    ) from _e

                for source_name in [edge.right_source for edge in join_path_edges_ex]:
                    if source_name in join_records_ex:
                        continue
                    try:
                        records_ex, _nodes_ex = _load_exact(source_name)
                    except ValueError as _e:
                        raise HTTPException(
                            status_code=404,
                            detail={
                                "error": {
                                    "code": "join_source_error",
                                    "message": str(_e),
                                }
                            },
                        ) from _e
                    join_records_ex[source_name] = records_ex

                if join_group_source_ex is None:
                    join_group_source_ex = payload.source_name
                terminal_nodes_ex = (
                    metric_nodes
                    if join_group_source_ex == payload.source_name
                    else _graph_nodes_from_cached_meta(
                        org_id=org_id,
                        dataset_id=registered_ex[join_group_source_ex]["id"],
                        schema_revision=str(
                            registered_ex[join_group_source_ex].get("schema_revision", "") or ""
                        ),
                        schema_meta=_sreg_ex.get_source_meta(
                            org_id,
                            registered_ex[join_group_source_ex]["id"],
                        )
                        or {},
                    )
                )
                if group_col_ex not in terminal_nodes_ex:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": {
                                "code": "group_column_not_found",
                                "message": (
                                    f"Column '{group_col_ex}' not found in terminal "
                                    f"join source '{join_group_source_ex}'."
                                ),
                            }
                        },
                    )

                for idx, (edge_ex, (edge_conf_ex, edge_card_ex)) in enumerate(
                    zip(join_path_edges_ex, join_edge_meta_ex, strict=False), start=1
                ):
                    plan.append(
                        f"Join hop {idx}: {edge_ex.left_source}.{edge_ex.left_key} = "
                        f"{edge_ex.right_source}.{edge_ex.right_key} "
                        f"(conf={edge_conf_ex:.2f}  card={edge_card_ex or '?'})"
                    )
                cross_ex = bool(join_path_edges_ex)
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "group_column_not_found",
                            "message": (
                                f"Column '{group_col_ex}' not found in '{payload.source_name}'. "
                                "Cross-source grouping now requires join_path."
                            ),
                        }
                    },
                )

        if payload.join_path and not group_col_ex:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "join_path_requires_group_column",
                        "message": "join_path requires group_column for exact-spec execution.",
                    }
                },
            )

        # Time filter
        date_col_ex: str | None = find_time_column(
            payload.source_name, {payload.source_name: metric_nodes}
        )
        tr_ex = (
            time_range(payload.filter.time_filter)
            if payload.filter and payload.filter.time_filter
            else None
        )

        # Build a stable plan key — content-keyed sources are permanent so hash is safe
        _plan_key = exact_plan_hash

        _cached_result = _RESULT_CACHE.get(_plan_key)
        if _cached_result and (time.monotonic() - _cached_result.get("_ts", 0)) < _RESULT_CACHE_TTL:
            plan.append(f"Result cache HIT [{_plan_key[:8]}]")
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=_cached_result["result"],
                result_type=_cached_result["result_type"],
                confidence=_cached_result["confidence"],
                plan=plan,
                resolved_column=payload.metric_column,
                resolved_role=_cached_result.get("resolved_role", ""),
                resolved_source=_cached_result.get("resolved_source", payload.source_name),
                row_count=_cached_result["row_count"],
                candidates=[],
                source_scores={},
                ambiguous=False,
                exact_spec=True,
                explanation=_cached_result.get("explanation", []),
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="exact_spec",
                schema_revision=schema_revision_exact,
                validated=True,
                confidence_source="exact_spec_validation",
                plan_basis=exact_plan_basis,
                source_set=(
                    [payload.source_name]
                    + [edge.right_source for edge in join_path_edges_ex]
                ),
                join_path=[
                    edge.model_dump(mode="python") for edge in join_path_edges_ex
                ],
                planner_mode="exact_spec",
                plan_hash_override=exact_plan_hash,
            )

        # Execute
        if cross_ex and join_group_source_ex and group_col_ex:
            result_ex, row_count_ex, exec_plan_ex = execute_join_path(
                records_by_source=join_records_ex,
                base_source=payload.source_name,
                metric_col=payload.metric_column,
                group_source=join_group_source_ex,
                group_col=group_col_ex,
                ordered_edges=join_path_edges_ex,
                agg=payload.aggregation,
                limit=payload.limit,
                order=payload.order,
                reject_on_ambiguity=payload.join_path.reject_on_ambiguity
                if payload.join_path
                else True,
            )
            resolved_src_ex = " ⋈ ".join(
                [payload.source_name] + [edge.right_source for edge in join_path_edges_ex]
            )
        else:
            result_ex, row_count_ex, exec_plan_ex = execute(
                records=metric_records,
                metric_col=payload.metric_column,
                agg=payload.aggregation,
                group_col=group_col_ex,
                date_col=date_col_ex,
                tr=tr_ex,
                limit=payload.limit,
                order=payload.order,
            )
            resolved_src_ex = payload.source_name

        plan.extend(exec_plan_ex)
        result_type_ex = (
            "table"
            if isinstance(result_ex, list)
            else ("scalar" if result_ex is not None else "none")
        )

        # Compute confidence
        computed_confidence, col_conf, agg_conf = _compute_exact_confidence(
            metric_node, payload.aggregation, join_confidence_ex
        )

        # Constraint: min_column_confidence check
        if col_conf < payload.constraints.min_column_confidence:
            from fastapi import HTTPException as _HTTPExc

            raise _HTTPExc(
                status_code=400,
                detail={
                    "error": {
                        "code": "constraint_violated",
                        "constraint": "min_column_confidence",
                        "reason": (
                            f"Column '{payload.metric_column}' has "
                            f"column_confidence={col_conf:.2f}, which is below "
                            "min_column_confidence="
                            f"{payload.constraints.min_column_confidence:.2f}."
                        ),
                    }
                },
            )

        # Build explanation
        explanation: list[str] = [
            f"Source: {payload.source_name}",
            f"Column: {payload.metric_column}  role={metric_node.role}"
            + (f"  formula={metric_node.formula}" if metric_node.formula else ""),
            f"Aggregation: {payload.aggregation}",
        ]
        if group_col_ex:
            if cross_ex:
                hop_text = " -> ".join(
                    f"{edge.left_source}.{edge.left_key}={edge.right_source}.{edge.right_key}"
                    for edge in join_path_edges_ex
                )
                explanation.append(
                    f"Group by: {group_col_ex} from {join_group_source_ex} "
                    f"via join_path ({hop_text})"
                )
            else:
                explanation.append(f"Group by: {group_col_ex} (same source)")
        if tr_ex:
            explanation.append(
                f"Time filter: {payload.filter.time_filter if payload.filter else '?'} → {tr_ex}"
            )
        explanation.append(
            f"Result: {result_type_ex}"
            + (f"  {row_count_ex} groups" if result_type_ex == "table" else f"  = {result_ex}")
        )
        explanation.append(
            f"Confidence: {computed_confidence:.3f} = col({col_conf:.2f}) × agg({agg_conf:.2f})"
            + (f" × join({join_confidence_ex:.2f})" if cross_ex else "")
        )

        # Store in result cache
        if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
            oldest = min(_RESULT_CACHE.items(), key=lambda x: x[1].get("_ts", 0))
            del _RESULT_CACHE[oldest[0]]

        _RESULT_CACHE[_plan_key] = {
            "result": result_ex,
            "result_type": result_type_ex,
            "row_count": row_count_ex,
            "confidence": computed_confidence,
            "resolved_role": metric_node.role,
            "resolved_source": resolved_src_ex,
            "explanation": explanation,
            "_ts": time.monotonic(),
        }
        plan.append(f"Result cache STORED [{_plan_key[:8]}]")

        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=result_ex,
            result_type=result_type_ex,
            confidence=computed_confidence,
            plan=plan,
            resolved_column=payload.metric_column,
            resolved_role=metric_node.role,
            resolved_source=resolved_src_ex,
            row_count=row_count_ex,
            candidates=[],
            source_scores={},
            ambiguous=False,
            exact_spec=True,
            explanation=explanation,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="exact_spec",
            schema_revision=schema_revision_exact,
            validated=True,
            confidence_source="exact_spec_validation",
            plan_basis=exact_plan_basis,
            source_set=(
                [payload.source_name]
                + [edge.right_source for edge in join_path_edges_ex]
            ),
            join_path=[edge.model_dump(mode="python") for edge in join_path_edges_ex],
            planner_mode="exact_spec",
            plan_hash_override=exact_plan_hash,
        )

    # ══════════════════════════════════════════════════════════════════════
    # HINT PATH (fallback) — LLM did not supply exact column names.
    # Source resolver + column resolver run. Result has ambiguous flag.
    # Migrate to exact-spec once schema is known.
    # ══════════════════════════════════════════════════════════════════════

    # Validate role
    target_role = payload.metric.role
    if target_role not in ALL_ROLES:
        target_role = DERIVED_MEASURE
        plan.append(f"Unknown role '{payload.metric.role}' — defaulting to derived_measure")

    plan.append(
        f"Request: agg={payload.aggregation}  role={target_role}  "
        f"group_by={payload.group_by}  limit={payload.limit}  "
        f"time={payload.filter.time_filter if payload.filter else None}"
    )

    if not payload.sources:
        registered = _visible_registry_entries()
        if not registered:
            empty_schema_revision = _sreg_visible.schema_revision(org_id)
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=None,
                result_type="none",
                confidence=0.0,
                plan=plan
                + [
                    "No registered sources found for this org. Use POST /v1/sources/register first."
                ],
                resolved_column="",
                resolved_role="",
                resolved_source="",
                row_count=0,
                candidates=[],
                source_scores={},
                ambiguous=True,
                exact_spec=False,
                explanation=[],
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=empty_schema_revision,
                validated=False,
                confidence_source="planner_query_confidence",
                clarification_required=False,
                rejection_reason="schema_incomplete",
                plan_basis={"reason": "no_registered_sources"},
            )

        planner, planner_cache_hit, schema_revision = await _get_registry_planner(
            org_id,
            llm_policy="never",
            auth=auth,
            visible_entries=registered,
        )
        metric_hint = (payload.metric.hint or "").strip() or target_role.replace("_", " ")
        dim_hint = (
            " ".join(part.strip() for part in payload.group_by if part and part.strip()) or None
        )
        time_filter = payload.filter.time_filter if payload.filter else None

        hint_result_key = hashlib.sha256(
            json.dumps(
                {
                    "org": org_id,
                    "rev": schema_revision,
                    "metric_hint": metric_hint,
                    "dim_hint": dim_hint or "",
                    "preferred_source": payload.preferred_source or "",
                    "agg": payload.aggregation,
                    "limit": payload.limit,
                    "order": payload.order,
                    "time_filter": time_filter or "",
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()[:24]

        cached_hint = _RESULT_CACHE.get(hint_result_key)
        if cached_hint and (time.monotonic() - cached_hint.get("_ts", 0)) < _RESULT_CACHE_TTL:
            warm_plan = list(plan)
            warm_plan.append(
                f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]"
            )
            warm_plan.append(f"Hint result cache HIT [{hint_result_key[:8]}]")
            warm_plan.extend(cached_hint.get("plan_body", []))
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=cached_hint["result"],
                result_type=cached_hint["result_type"],
                confidence=cached_hint["confidence"],
                plan=warm_plan,
                resolved_column=cached_hint["resolved_column"],
                resolved_role=cached_hint["resolved_role"],
                resolved_source=cached_hint["resolved_source"],
                row_count=cached_hint["row_count"],
                candidates=[CandidateColumn(**cand) for cand in cached_hint.get("candidates", [])],
                source_scores=cached_hint.get("source_scores", {}),
                ambiguous=cached_hint.get("ambiguous", False),
                exact_spec=False,
                explanation=cached_hint.get("explanation", []),
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=schema_revision,
                validated=True,
                confidence_source="planner_query_confidence",
                plan_basis={"cache_key": hint_result_key},
                deterministic_scope="planned_execution",
                source_set=cached_hint.get("source_set", []),
                join_path=cached_hint.get("join_path", []),
                planner_mode="registry_planner",
            )

        plan.append(f"Registry: {len(registered)} registered sources for org {org_id}")
        plan.append(
            f"Planner cache {'HIT' if planner_cache_hit else 'MISS'} [{schema_revision[:8]}]"
        )

        qplan = planner.plan(
            metric_hint=metric_hint,
            dim_hint=dim_hint,
            agg=payload.aggregation,
            preferred_source=payload.preferred_source,
        )
        plan.extend(qplan.steps)

        confidence = _planner_query_confidence(qplan)
        ambiguous = bool(qplan.error) or confidence < _DECISION_AUTO_ACCEPT_CONFIDENCE
        metric_candidate_payloads = _planner_metric_candidate_payloads(
            plan=qplan,
            graph=planner.graph,
            metric_hint=metric_hint,
            target_role=qplan.metric_role or target_role,
            preferred_source=payload.preferred_source,
        )

        plan_error_text = "; ".join(
            note
            for note in [qplan.error or "", *_planner_load_bearing_validation_notes(qplan)]
            if note
        ) or None
        validated, clarification_required, rejection_reason = _decision_contract_flags(
            confidence,
            metric_candidate_payloads,
            error_text=plan_error_text,
        )
        source_scores_hint = (
            {qplan.metric_src: round(qplan.metric_conf, 3)}
            if qplan.metric_src
            else {}
        )
        if not validated:
            if clarification_required:
                plan.append(
                    "Clarification required: planner confidence or candidate separation "
                    "did not meet deterministic execution threshold."
                )
            else:
                plan.append(
                    f"Rejected: {rejection_reason or 'schema_unresolved'} before execution"
                )
            explanation = [
                f"Metric hint: {metric_hint}",
                f"Planner confidence: {confidence:.3f}",
            ]
            if plan_error_text:
                explanation.append(f"Planner note: {plan_error_text}")
            return _build_query_response(
                query_id=query_id,
                request_id=request_id,
                result=None,
                result_type="none",
                confidence=confidence,
                plan=plan,
                resolved_column=qplan.metric_col or "",
                resolved_role=qplan.metric_role or "",
                resolved_source=qplan.metric_src or "",
                row_count=0,
                candidates=metric_candidate_payloads[:5],
                source_scores=source_scores_hint,
                ambiguous=True,
                exact_spec=False,
                explanation=explanation,
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                decision_path="planner_hint",
                schema_revision=schema_revision,
                validated=False,
                confidence_source="planner_query_confidence",
                clarification_required=clarification_required,
                rejection_reason=rejection_reason,
                plan_basis={
                    "cache_key": hint_result_key,
                    "metric_hint": metric_hint,
                    "dim_hint": dim_hint or "",
                    "aggregation": payload.aggregation,
                },
                source_set=_dedupe_source_values(
                    [
                        qplan.metric_src or "",
                        qplan.group_src or "",
                        *[hop.right_source for hop in qplan.join_hops],
                    ]
                ),
                join_path=[
                    {
                        "left_source": hop.left_source,
                        "left_key": hop.left_key,
                        "right_source": hop.right_source,
                        "right_key": hop.right_key,
                        "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                        "cardinality": getattr(hop, "cardinality", None),
                    }
                    for hop in qplan.join_hops
                ],
                planner_mode="registry_planner",
            )

        result, row_count, exec_plan = planner.execute_plan(
            qplan,
            limit=payload.limit,
            order=payload.order,
            time_filter=time_filter,
        )
        plan.extend(exec_plan)

        if result is None:
            result_type = "none"
        elif isinstance(result, list):
            result_type = "table"
        else:
            result_type = "scalar"

        resolved_source = (
            " ⋈ ".join([qplan.metric_src] + [hop.right_source for hop in qplan.join_hops])
            if qplan.join_hops
            else qplan.metric_src
        )
        metric_node = planner.graph.get(qplan.metric_src, {}).get(qplan.metric_col)
        candidates: list[CandidateColumn] = []
        for cand in metric_candidate_payloads[:5]:
            candidates.append(CandidateColumn(**cand))
        if not candidates and metric_node is not None and qplan.metric_src and qplan.metric_col:
            candidates.append(
                CandidateColumn(
                    source=qplan.metric_src,
                    column=qplan.metric_col,
                    role=metric_node.role,
                    magnitude=metric_node.magnitude_class,
                    formula=metric_node.formula,
                    confidence=qplan.metric_conf,
                )
            )

        explanation = [
            f"Metric hint: {metric_hint}",
            f"Resolved metric: {qplan.metric_src}.{qplan.metric_col}"
            if qplan.metric_src and qplan.metric_col
            else "Resolved metric: none",
            f"Aggregation: {payload.aggregation}",
        ]
        if qplan.group_col and qplan.group_src:
            explanation.append(f"Group by: {qplan.group_src}.{qplan.group_col}")
        if qplan.join_hops:
            hop_text = " -> ".join(
                f"{hop.left_source}.{hop.left_key}={hop.right_source}.{hop.right_key}"
                for hop in qplan.join_hops
            )
            explanation.append(f"Join path: {hop_text}")
        if time_filter:
            explanation.append(f"Time filter: {time_filter}")
        explanation.append(
            f"Confidence: {confidence:.3f}" + (f"  error={qplan.error}" if qplan.error else "")
        )

        plan_body = list(qplan.steps) + list(exec_plan)
        if len(_RESULT_CACHE) >= _RESULT_CACHE_MAX:
            oldest = min(_RESULT_CACHE.items(), key=lambda item: item[1].get("_ts", 0))
            del _RESULT_CACHE[oldest[0]]
        _RESULT_CACHE[hint_result_key] = {
            "result": result,
            "result_type": result_type,
            "confidence": confidence,
            "resolved_column": qplan.metric_col or "",
            "resolved_role": qplan.metric_role or "",
            "resolved_source": resolved_source or "",
            "row_count": row_count,
            "candidates": [cand.model_dump() for cand in candidates],
            "source_scores": source_scores_hint,
            "ambiguous": ambiguous,
            "explanation": explanation,
            "source_set": _dedupe_source_values(
                [
                    qplan.metric_src or "",
                    qplan.group_src or "",
                    *[hop.right_source for hop in qplan.join_hops],
                ]
            ),
            "join_path": [
                {
                    "left_source": hop.left_source,
                    "left_key": hop.left_key,
                    "right_source": hop.right_source,
                    "right_key": hop.right_key,
                    "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                    "cardinality": getattr(hop, "cardinality", None),
                }
                for hop in qplan.join_hops
            ],
            "plan_body": plan_body,
            "_ts": time.monotonic(),
        }
        plan.append(f"Hint result cache STORED [{hint_result_key[:8]}]")

        return _build_query_response(
            query_id=query_id,
            request_id=request_id,
            result=result,
            result_type=result_type,
            confidence=confidence,
            plan=plan,
            resolved_column=qplan.metric_col or "",
            resolved_role=qplan.metric_role or "",
            resolved_source=resolved_source or "",
            row_count=row_count,
            candidates=candidates,
            source_scores=source_scores_hint,
            ambiguous=ambiguous,
            exact_spec=False,
            explanation=explanation,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
            decision_path="planner_hint",
            schema_revision=schema_revision,
            validated=True,
            confidence_source="planner_query_confidence",
            plan_basis={
                "cache_key": hint_result_key,
                "resolved_source": resolved_source or "",
                "resolved_column": qplan.metric_col or "",
                "aggregation": payload.aggregation,
            },
            deterministic_scope="planned_execution",
            source_set=_dedupe_source_values(
                [
                    qplan.metric_src or "",
                    qplan.group_src or "",
                    *[hop.right_source for hop in qplan.join_hops],
                ]
            ),
            join_path=[
                {
                    "left_source": hop.left_source,
                    "left_key": hop.left_key,
                    "right_source": hop.right_source,
                    "right_key": hop.right_key,
                    "confidence": round(float(getattr(hop, "confidence", 0.0) or 0.0), 3),
                    "cardinality": getattr(hop, "cardinality", None),
                }
                for hop in qplan.join_hops
            ],
            planner_mode="registry_planner",
        )

    # ── Load + profile all sources (cache-aware) ─────────────────────────────
    parsed_tables: dict[str, Any] = {}
    profiles: dict[str, dict[str, dict]] = {}
    cache_hits: set[str] = set()
    cache_entries: dict[str, _CachedSource] = {}  # src.name → cached entry
    # Registry connections (populated when loading from registry; used for cross-source joins)
    _reg_connections: list[dict] = []

    for src in payload.sources:
        cache_key, content_keyed = _source_cache_key(src)
        async with _CACHE_LOCK:
            entry = _SOURCE_CACHE.get(cache_key)
            if entry and entry.is_fresh():
                entry.touch()
                cache_entries[src.name] = entry
                cache_hits.add(src.name)
                plan.append(f"Cache HIT [{src.name}] — skipping load+profile")
                continue
        # source_id miss — load from registry (parquet on disk)
        registered_id = src.dataset_id or src.source_id
        if registered_id:
            from apps.api_server.services import source_registry as _sreg

            parquet_bytes = _sreg.get_source_parquet(org_id, registered_id)
            if parquet_bytes:
                schema_meta_dict = _sreg.get_source_meta(org_id, registered_id) or {}
                graph_nodes = _graph_nodes_from_meta(schema_meta_dict)
                reg_entry = _CachedSource(
                    parquet_bytes=parquet_bytes,
                    parquet_schema_meta=json.dumps(schema_meta_dict).encode(),
                    profile={},
                    mojo_profile={},
                    relations=schema_meta_dict.get("formulas", []),
                    graph_nodes=graph_nodes,
                    schema_meta=schema_meta_dict,
                    mojo_profiling_status=schema_meta_dict.get("mojo_profiling_status") or {},
                    content_keyed=True,
                )
                async with _CACHE_LOCK:
                    _evict_lru()
                    _SOURCE_CACHE[registered_id] = reg_entry
                cache_entries[src.name] = reg_entry
                plan.append(f"Registry HIT (dataset/source id) [{src.name}]")
                continue
            plan.append(
                f"WARNING: source_id={registered_id} not found in registry for [{src.name}]"
            )
        # Cache miss — adaptively load on the fastest safe path for this source
        loaded = await _load_profiled_source(src, org_id=org_id)
        if loaded.row_count <= 0 or loaded.arrow_table is None:
            _raise_empty_source(src.name)
        profiles[src.name] = loaded.profile
        parsed_tables[src.name] = loaded.arrow_table
        plan.append(f"Ingest [{src.name}] mode={loaded.ingest_mode}")

    # ── Mojo: profiling + relation detection (concurrent, only for misses) ──
    miss_names = list(parsed_tables.keys())
    if miss_names:
        profiler_coros = [
            _call_mojo_column_profile(
                _build_mojo_column_profile_columns(
                    profiles[name],
                    value_limit=50,
                    string_limit=50,
                    include_fill_rate=True,
                )
            )
            for name in miss_names
        ]
        relation_coros = [_detect_relations(name, profiles) for name in miss_names]
        try:
            profiler_results, relation_results = await asyncio.gather(
                asyncio.gather(*profiler_coros),
                asyncio.gather(*relation_coros),
            )
        except MojoInstrumentationError as exc:
            raise _http_error(
                503,
                code="mojo_instrumentation_unavailable",
                message=(
                    "Mojo column profiling is unavailable while strict runtime "
                    "fallbacks are disabled."
                ),
                request_id=request_id,
                details=[("engine_type", exc.engine_type)],
            ) from exc
        for i, name in enumerate(miss_names):
            profiling_status = _mojo_profiling_status_from_result(profiler_results[i])
            mojo_prof = (profiler_results[i] or {}).get("profiles", {})
            rels = relation_results[i]
            if rels:
                plan.append(f"Formulas in {name}: {len(rels)} detected (top: {rels[0]['formula']})")
            if profiling_status.get("status") != "enabled":
                plan.append(
                    "Mojo profiling disabled "
                    f"[{name}] reason={profiling_status.get('reason') or 'unknown'}"
                )
            # Build graph nodes for this source
            src_graph = build_schema_graph(
                {name: profiles[name]},
                {name: mojo_prof},
                {name: rels},
            )
            import pyarrow.parquet as pq

            schema_meta = _build_schema_metadata(
                name,
                src_graph[name],
                rels,
                profiles[name],
                profiling_status,
            )
            arrow_table = parsed_tables[name]
            # Embed schema metadata in Arrow custom_metadata
            existing_meta = arrow_table.schema.metadata or {}
            new_meta = {
                **existing_meta,
                b"algenta_schema": json.dumps(schema_meta).encode(),
            }
            arrow_table = arrow_table.replace_schema_metadata(new_meta)
            buf = io.BytesIO()
            pq.write_table(arrow_table, buf)
            parquet_bytes = buf.getvalue()
            # Also store just the schema metadata bytes (cheap to extract)
            schema_meta_bytes = json.dumps(schema_meta).encode()

            # Find original DataSource to get cache key + content_keyed flag
            for src in payload.sources:
                if src.name == name:
                    ck, ck_content = _source_cache_key(src)
                    entry = _CachedSource(
                        parquet_bytes=parquet_bytes,
                        parquet_schema_meta=schema_meta_bytes,
                        profile=profiles[name],
                        mojo_profile=mojo_prof,
                        relations=rels,
                        graph_nodes=src_graph[name],
                        schema_meta=schema_meta,
                        mojo_profiling_status=profiling_status,
                        content_keyed=ck_content,
                    )
                    async with _CACHE_LOCK:
                        _evict_lru()
                        _SOURCE_CACHE[ck] = entry
                    cache_entries[name] = entry
                    break

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
        return _build_query_response(
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
        )

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
        return _build_query_response(
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
        )

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

    def _load_records(name: str) -> list[dict]:
        if name in parsed_tables:
            return parsed_tables[name].to_pylist()
        buf = io.BytesIO(cache_entries[name].parquet_bytes)
        initialize_pyarrow_parquet_runtime()
        return pd.read_parquet(buf).to_dict(orient="records")

    exec_records = _load_records(src_name)

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
                        "min(source_resolver, metric_resolver, "
                        "group_resolver, join_confidence)"
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


# ── Schema endpoint — call this before querying to give the LLM full context ──


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
) -> dict:
    import base64

    import pyarrow.parquet as pq

    t0 = time.monotonic()
    result: list[dict] = []
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
        cache_key, content_keyed = _source_cache_key(src)
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

        try:
            profiler_result, rels = await asyncio.gather(
                _call_mojo_column_profile(
                    _build_mojo_column_profile_columns(
                        profile,
                        value_limit=50,
                        string_limit=50,
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
            _evict_lru()
            _SOURCE_CACHE[cache_key] = entry

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


# ── Plan verification — LLM submits exact plan, Mojo validates before executing ──


class VerifyRequest(BaseModel):
    """
    LLM-produced execution plan. All names are EXACT (from schema endpoint).
    Mojo checks: source exists, columns exist, aggregation is valid for the
    column role, and join keys have sufficient confidence.
    """

    source_name: str | None = Field(default=None, description="Exact source name from schema")
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
        if payload.resolved_plan.schema_revision != schema_revision:
            return VerifyResponse(
                valid=False,
                errors=[
                    "resolved_plan schema_revision no longer matches "
                    "the current registry state."
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
                "verify requires source_name, metric_column, and aggregation "
                "or a resolved_plan."
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
    from apps.api_server.services.data_visibility import filter_visible_datasets

    registered = filter_visible_datasets(_sreg.list_sources(org_id), auth)
    src_map = {s["name"]: s for s in registered}
    visible_ids = {s["id"] for s in registered}

    if payload.source_name not in src_map:
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

    src_entry = src_map[payload.source_name]
    src_id = src_entry["id"]
    resolved["source"] = payload.source_name

    # ── 2. Load schema (cache or disk) ────────────────────────────────────────
    schema_meta: dict = {}
    async with _CACHE_LOCK:
        cached = _SOURCE_CACHE.get(src_id)
        if cached and cached.is_fresh():
            cached.touch()
            schema_meta = json.loads(cached.parquet_schema_meta)

    if not schema_meta:
        schema_meta = _sreg.get_source_meta(org_id, src_id) or {}

    columns_meta = {c["name"]: c for c in schema_meta.get("columns", [])}

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

        if not is_numeric:
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
        if payload.join_source_name not in src_map:
            errors.append(f"Join source '{payload.join_source_name}' not found in registry.")
            suggestions.append(f"Available sources: {', '.join(src_map.keys())}")
        else:
            join_src_entry = src_map[payload.join_source_name]
            join_src_id = join_src_entry["id"]

            # Load join source schema
            join_schema_meta: dict = {}
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
