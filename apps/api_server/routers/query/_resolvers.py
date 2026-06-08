"""Submodule _resolvers.py of apps.api_server.routers.query.

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
) -> tuple[str, str, float, list[dict[str, Any]]]:
    """
    Returns (source, column, confidence, all_candidates).
    Primary: structural role match.
    Secondary: magnitude class (for derived_measure).
    Tiebreaker: token overlap with hint_tokens (weak, 15% weight max).
    """
    best = ("", "", 0.0)
    candidates: list[dict[str, Any]] = []

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

_MIN_JOIN_CONFIDENCE = 0.85  # default threshold — only statistically solid entity joins

def _find_best_join_key(
    src_a_name: str,
    src_b_name: str,
    connections: list[dict[str, Any]],
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

    def _col_role(c: dict[str, Any], side: str) -> str:
        # connections.json may store col_a_role/col_b_role if present; otherwise unknown
        return str(c.get(f"{side}_role", "") or "")

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

def _match_join_path_edge(
    edge: JoinEdgeSpec,
    connections: list[dict[str, Any]],
) -> tuple[float, str]:
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
    connections: list[dict[str, Any]],
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

    sources_payload: dict[str, dict[str, Any]] = {}
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

