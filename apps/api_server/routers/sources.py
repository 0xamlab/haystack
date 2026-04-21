"""
Source registry endpoints.

POST /v1/sources/register    — register a source: profile it, detect joins to all existing sources
GET  /v1/sources             — list all registered sources for this org
GET  /v1/sources/graph       — full connection graph between all registered sources
GET  /v1/sources/{id}        — schema for a specific registered source
DELETE /v1/sources/{id}      — remove a source and its connections

Flow:
  1. User uploads/points to data → POST /v1/sources/register
  2. Engine profiles every column (full scan, dynamic sparse detection)
  3. Mojo detects formulas (A×B≈C) within the source
  4. Mojo detects joins to EVERY existing registered source (pair-wise)
  5. Results cached in memory + persisted to disk as Parquet + JSON
  6. Subsequent queries use the hot cache — no re-profiling
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api_server.error_payloads import access_scope_denied_error
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.pagination import paginate_sequence
from apps.api_server.routers.data_map import (
    DataSource,
    MojoInstrumentationError,
    _build_mojo_column_profile_columns,
    _call_mojo_join_detect,
    _mojo_column_profile_sample_limits,
    _mojo_profiling_status_from_result,
)
from apps.api_server.routers.query import (
    _CACHE_LOCK,
    _SOURCE_CACHE,
    _build_schema_metadata,
    _CachedSource,
    _call_mojo_column_profile,
    _detect_relations,
    _evict_lru,
    _get_registry_planner,
    _http_error,
    _load_profiled_source,
    _source_cache_key,
    build_schema_graph,
)
from apps.api_server.services import source_registry as reg
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Source Registry"])

_DEEP_JOIN_COLUMN_LIMIT = 12
_JOIN_PROJECTION_CACHE_MAX = 128
_DECISIVE_ONE_TO_ONE_FAST_JOIN_OVERLAP = 0.05
_DECISIVE_DIRECTIONAL_FAST_JOIN_OVERLAP = 0.075
_METADATA_FAST_JOIN_MIN_SAMPLE_OVERLAP = 3
_DEFAULT_JOIN_CANDIDATE_MIN_SCORE = 4.5
_REDUCED_MEDIUM_JOIN_CANDIDATE_MIN_SCORE = 20.0
_REDUCED_WIDE_MEDIUM_JOIN_CANDIDATE_MIN_SCORE = 30.0
_SMALL_ORG_SINGLE_JOIN_PAIR_COST_BUDGET = 5_000_000
_SMALL_ORG_TOTAL_JOIN_PAIR_COST_BUDGET = 12_000_000
_JOIN_PROJECTION_CACHE: dict[tuple[str, str, str, tuple[str, ...]], pd.DataFrame] = {}
_JOIN_PROJECTION_CACHE_LOCK = threading.Lock()


# ── Register ────────────────────────────────────────────────────────────────────

_JOIN_KEY_NAME_TOKENS = frozenset({
    "account",
    "code",
    "guid",
    "id",
    "identifier",
    "key",
    "number",
    "ref",
    "serial",
    "uuid",
})


def _looks_like_entity_join_key(name: str) -> bool:
    lowered = name.lower()
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    if tokens & _JOIN_KEY_NAME_TOKENS:
        return True
    return any(token in lowered for token in ("_id", "_key", "_code", "_ref", "_uuid", "_guid"))


def _infer_shared_column_cardinality(
    left_counts: dict[str, int],
    right_counts: dict[str, int],
    shared_values: set[str],
) -> str:
    if not shared_values:
        return "many_to_many"

    left_max = max(int(left_counts.get(value, 0)) for value in shared_values)
    right_max = max(int(right_counts.get(value, 0)) for value in shared_values)

    if left_max <= 1 and right_max <= 1:
        return "one_to_one"
    if left_max <= 1:
        return "one_to_many"
    if right_max <= 1:
        return "many_to_one"
    return "many_to_many"


def _shared_name_join_confidence(jaccard: float, cardinality: str) -> float:
    if cardinality == "one_to_one":
        return round(min(0.99, 0.80 + jaccard * 0.25), 3)
    if cardinality in {"one_to_many", "many_to_one"}:
        return round(min(0.97, 0.74 + jaccard * 0.22), 3)
    return round(min(0.90, 0.60 + jaccard * 0.18), 3)


def _has_decisive_fast_join(connections: list[dict[str, Any]]) -> bool:
    for connection in connections:
        cardinality = str(connection.get("cardinality") or "")
        if cardinality not in {"one_to_one", "one_to_many", "many_to_one"}:
            continue
        col_a = str(connection.get("col_a") or "")
        col_b = str(connection.get("col_b") or "")
        if not (_looks_like_entity_join_key(col_a) or _looks_like_entity_join_key(col_b)):
            continue
        overlap = float(connection.get("overlap") or 0.0)
        if cardinality == "one_to_one" and overlap >= _DECISIVE_ONE_TO_ONE_FAST_JOIN_OVERLAP:
            return True
        if (
            cardinality in {"one_to_many", "many_to_one"}
            and overlap >= _DECISIVE_DIRECTIONAL_FAST_JOIN_OVERLAP
        ):
            return True
    return False


def _join_block_norm(block: dict[str, Any]) -> str:
    name = str(block.get("name") or "").strip()
    if not name:
        return ""
    return str(block.get("norm") or "".join(re.findall(r"[a-z0-9]+", name.lower())))


def _infer_join_block_cardinality(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_unique_ratio = float(left.get("unique_ratio", 0.0) or 0.0)
    right_unique_ratio = float(right.get("unique_ratio", 0.0) or 0.0)
    if left_unique_ratio >= 0.98 and right_unique_ratio >= 0.98:
        return "one_to_one"
    if left_unique_ratio >= 0.98:
        return "one_to_many"
    if right_unique_ratio >= 0.98:
        return "many_to_one"
    return "many_to_many"


def _metadata_fast_join_candidates(
    *,
    src_id: str,
    src_name: str,
    other_id: str,
    other_name: str,
    left_join_blocks: list[dict[str, Any]] | None,
    right_join_blocks: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not left_join_blocks or not right_join_blocks:
        return []

    candidates: list[dict[str, Any]] = []
    right_by_norm: dict[str, list[dict[str, Any]]] = {}
    for block in right_join_blocks:
        norm = _join_block_norm(block)
        if norm:
            right_by_norm.setdefault(norm, []).append(block)

    for left in left_join_blocks:
        left_name = str(left.get("name") or "").strip()
        left_norm = _join_block_norm(left)
        if not left_name or not left_norm:
            continue
        if not (
            bool(left.get("key_like"))
            or str(left.get("role") or "") == "identifier"
            or _looks_like_entity_join_key(left_name)
        ):
            continue

        left_samples = set(left.get("samples") or [])
        if not left_samples:
            continue

        for right in right_by_norm.get(left_norm, []):
            right_name = str(right.get("name") or "").strip()
            if not right_name:
                continue
            if not (
                bool(right.get("key_like"))
                or str(right.get("role") or "") == "identifier"
                or _looks_like_entity_join_key(right_name)
            ):
                continue

            right_samples = set(right.get("samples") or [])
            if not right_samples:
                continue

            sample_overlap = len(left_samples & right_samples)
            if sample_overlap < _METADATA_FAST_JOIN_MIN_SAMPLE_OVERLAP:
                continue

            cardinality = _infer_join_block_cardinality(left, right)
            if cardinality == "many_to_many":
                continue

            sample_union = left_samples | right_samples
            overlap = sample_overlap / max(len(sample_union), 1)
            candidates.append({
                "source_a": src_id,
                "source_a_name": src_name,
                "col_a": left_name,
                "source_b": other_id,
                "source_b_name": other_name,
                "col_b": right_name,
                "confidence": _shared_name_join_confidence(overlap, cardinality),
                "cardinality": cardinality,
                "overlap": round(overlap, 4),
            })

    return candidates


def _deep_join_projection_columns(
    join_blocks: list[dict[str, Any]] | None,
    *,
    limit: int = _DEEP_JOIN_COLUMN_LIMIT,
) -> list[str]:
    projected: list[str] = []
    seen: set[str] = set()
    for block in join_blocks or []:
        name = str(block.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        projected.append(name)
        if len(projected) >= limit:
            break
    return projected


def _load_join_projection(
    parquet_bytes: bytes | None,
    join_blocks: list[dict[str, Any]] | None,
    *,
    parquet_path: Path | None = None,
) -> pd.DataFrame:
    initialize_pyarrow_parquet_runtime()
    if parquet_path is not None:
        parquet_file = pq.ParquetFile(str(parquet_path))
    elif parquet_bytes is not None:
        parquet_file = pq.ParquetFile(io.BytesIO(parquet_bytes))
    else:
        raise ValueError("join projection requires parquet bytes or parquet path")
    projected = _deep_join_projection_columns(join_blocks)
    if projected:
        available = set(parquet_file.schema.names)
        selected = [name for name in projected if name in available]
    else:
        selected = []
    table = parquet_file.read(columns=selected or None)
    return table.to_pandas()


def _join_projection_signature(join_blocks: list[dict[str, Any]] | None) -> tuple[str, ...]:
    projected = _deep_join_projection_columns(join_blocks)
    return tuple(projected) if projected else ("*",)


def _join_projection_cache_get(
    cache_key: tuple[str, str, str, tuple[str, ...]],
) -> pd.DataFrame | None:
    with _JOIN_PROJECTION_CACHE_LOCK:
        cached = _JOIN_PROJECTION_CACHE.get(cache_key)
        if cached is None:
            return None
        _JOIN_PROJECTION_CACHE.pop(cache_key, None)
        _JOIN_PROJECTION_CACHE[cache_key] = cached
        return cached


def _join_projection_cache_put(
    cache_key: tuple[str, str, str, tuple[str, ...]],
    df: pd.DataFrame,
) -> pd.DataFrame:
    with _JOIN_PROJECTION_CACHE_LOCK:
        _JOIN_PROJECTION_CACHE.pop(cache_key, None)
        while len(_JOIN_PROJECTION_CACHE) >= _JOIN_PROJECTION_CACHE_MAX:
            _JOIN_PROJECTION_CACHE.pop(next(iter(_JOIN_PROJECTION_CACHE)))
        _JOIN_PROJECTION_CACHE[cache_key] = df
    return df


def _load_join_projection_cached(
    *,
    org_id: str,
    source_id: str,
    parquet_bytes: bytes | None = None,
    parquet_path: Path | None = None,
    join_blocks: list[dict[str, Any]] | None,
) -> pd.DataFrame:
    cache_key = (
        org_id,
        source_id,
        reg.source_schema_revision(org_id, source_id),
        _join_projection_signature(join_blocks),
    )
    cached = _join_projection_cache_get(cache_key)
    if cached is not None:
        return cached
    return _join_projection_cache_put(
        cache_key,
        _load_join_projection(parquet_bytes, join_blocks, parquet_path=parquet_path),
    )


def _estimated_join_pair_cost(
    *,
    row_count: int,
    join_block_count: int,
    entry: dict[str, Any],
) -> int:
    right_row_count = int(entry.get("row_count", 0) or 0)
    right_join_block_count = len(entry.get("join_blocks") or [])
    if (
        row_count <= 0
        or join_block_count <= 0
        or right_row_count <= 0
        or right_join_block_count <= 0
    ):
        return 0
    left_factor = min(join_block_count, 4)
    right_factor = min(right_join_block_count, 4)
    return row_count * min(right_row_count, 50_000) * left_factor * right_factor


def _should_use_scored_join_scan(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
    existing_sources: list[dict[str, Any]] | None = None,
) -> bool:
    if existing_total > 24:
        return True
    join_block_count = len(reg._build_join_blocks(schema_meta))
    pair_costs = [
        _estimated_join_pair_cost(
            row_count=row_count,
            join_block_count=join_block_count,
            entry=entry,
        )
        for entry in (existing_sources or [])
        if entry.get("row_count")
    ]
    if pair_costs and (
        max(pair_costs) >= _SMALL_ORG_SINGLE_JOIN_PAIR_COST_BUDGET
        or sum(pair_costs) >= _SMALL_ORG_TOTAL_JOIN_PAIR_COST_BUDGET
    ):
        return True
    if existing_total >= 12 and join_block_count >= 4 and row_count >= 3_000:
        return True
    if existing_total < 4:
        return False
    column_count = len(schema_meta.get("columns") or [])
    estimated_cells = row_count * max(column_count, 1)
    return row_count >= 5_000 or column_count >= 48 or estimated_cells >= 250_000


def _join_candidate_limit(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
) -> int:
    if existing_total <= 4:
        return 24
    column_count = len(schema_meta.get("columns") or [])
    estimated_cells = row_count * max(column_count, 1)
    if row_count >= 50_000 or estimated_cells >= 1_500_000:
        return 6
    if row_count >= 30_000 or column_count >= 96 or estimated_cells >= 750_000:
        return 8
    if row_count >= 10_000 or column_count >= 48 or estimated_cells >= 300_000:
        return 12
    if existing_total >= 24:
        return 16
    return 24


def _join_candidate_min_score(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
) -> float:
    join_block_count = len(reg._build_join_blocks(schema_meta))
    if existing_total >= 12 and 10_000 <= row_count < 30_000 and join_block_count >= 6:
        return _REDUCED_WIDE_MEDIUM_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 12 and 3_000 <= row_count < 30_000 and 3 <= join_block_count <= 4:
        return _REDUCED_MEDIUM_JOIN_CANDIDATE_MIN_SCORE
    return _DEFAULT_JOIN_CANDIDATE_MIN_SCORE


class RegisterRequest(BaseModel):
    source: DataSource
    description: str | None = Field(default=None, description="Optional human description")


async def _register_source_impl(
    payload: RegisterRequest,
    auth: AuthContext,
    *,
    dataset_name: str | None = None,
    connector_id: str | None = None,
    visibility: str | None = None,
    owner_user_id: str | None = None,
    owner_key_id: str | None = None,
    description: str | None = None,
    selection: dict[str, Any] | None = None,
    connection_type: str | None = None,
    provider: str | None = None,
    refreshable: bool | None = None,
    source_definition: dict[str, Any] | None = None,
) -> dict:
    import pyarrow.parquet as pq

    t0 = time.monotonic()
    src = payload.source
    org_id = str(auth["org_id"])

    # ── Cache key ──────────────────────────────────────────────────────────────
    cache_key, content_keyed = _source_cache_key(src)
    visibility_value = (visibility or "private").strip().lower()
    owner_scope = owner_user_id or (str(auth.get("user_id")) if auth.get("user_id") else None)
    owner_key_scope = owner_key_id or (str(auth.get("key_id")) if auth.get("key_id") else None)
    if visibility_value == "private" and (owner_scope or owner_key_scope):
        owner_marker = owner_scope or owner_key_scope or ""
        source_id = reg.source_id_for(f"{cache_key}:{owner_marker}")
    else:
        source_id = reg.source_id_for(cache_key)
    dataset_name_value = dataset_name or src.name
    dataset_description = description if description is not None else payload.description
    metadata_updates = {
        "dataset_name": dataset_name_value,
        "connector_id": connector_id,
        "visibility": visibility_value,
        "owner_user_id": owner_scope,
        "owner_key_id": owner_key_scope,
        "description": dataset_description,
        "selection": selection,
        "connection_type": connection_type,
        "provider": provider,
        "refreshable": refreshable,
        "source_definition": source_definition,
        "decision_mode": "deterministic_only",
    }

    cached_entry: _CachedSource | None = None
    schema_meta: dict[str, Any] | None = None
    parquet_bytes: bytes | None = None
    row_count = 0
    ingest_mode = "cache_reuse"
    cache_hit_schema: dict[str, Any] | None = None
    cache_hit_registered = False

    # ── Check if already registered and fresh ─────────────────────────────────
    async with _CACHE_LOCK:
        cached = _SOURCE_CACHE.get(source_id)
        if cached is None and cache_key != source_id:
            cached = _SOURCE_CACHE.get(cache_key)
        if cached and cached.is_fresh():
            cached.touch()
            cached_schema = json.loads(cached.parquet_schema_meta)
            existing_entry = reg.get_source_entry(org_id, source_id)
            if reg.get_source_meta(org_id, source_id) is not None:
                if existing_entry is not None:
                    reg.update_source_entry(org_id, source_id, metadata_updates)
                cache_hit_registered = True
                cache_hit_schema = cached_schema
            # Cache is global but registration is per-org. Reuse the profiled
            # content, then persist and join-index it for this org.
            cached_entry = cached
            schema_meta = cached_schema
            parquet_bytes = cached.parquet_bytes

    if cache_hit_registered and cache_hit_schema is not None:
        prewarm_t0 = time.monotonic()
        _, planner_cache_hit, schema_revision = await _get_registry_planner(
            org_id,
            llm_policy="never",
            auth=auth,
        )
        prewarm_ms = round((time.monotonic() - prewarm_t0) * 1000, 1)
        return {
            "source_id":   source_id,
            "dataset_id":  source_id,
            "name":        src.name,
            "dataset_name": dataset_name_value,
            "status":      "already_registered",
            "ingest_mode": "cache_reuse",
            "schema":      cache_hit_schema,
            "mojo_profiling_status": cache_hit_schema.get("mojo_profiling_status") or {},
            "planner_cache_hit": planner_cache_hit,
            "planner_schema_revision": schema_revision,
            "planner_prewarm_ms": prewarm_ms,
            "latency_ms":  round((time.monotonic() - t0) * 1000, 1),
        }

    if cached_entry is None:
        # ── Load + profile ─────────────────────────────────────────────────────
        loaded = await _load_profiled_source(src, org_id=org_id)
        if loaded.row_count <= 0 or loaded.arrow_table is None:
            raise HTTPException(status_code=400, detail={"error": {"code": "empty_source",
                "message": f"Source '{src.name}' returned no records."}})

        profile = loaded.profile
        arrow_table = loaded.arrow_table
        row_count = loaded.row_count
        ingest_mode = loaded.ingest_mode

        # ── Mojo: profile + relation detect (parallel) ────────────────────────
        try:
            value_limit, string_limit = _mojo_column_profile_sample_limits(len(profile))
            profiler_result, relations = await asyncio.gather(
                _call_mojo_column_profile(
                    _build_mojo_column_profile_columns(
                        profile,
                        value_limit=value_limit,
                        string_limit=string_limit,
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
        if profiling_status.get("status") != "enabled":
            logger.info(
                "source_registration_mojo_profiling_disabled",
                org=org_id,
                source=src.name,
                reason=profiling_status.get("reason"),
            )

        # ── Build schema graph ────────────────────────────────────────────────
        src_graph = build_schema_graph(
            {src.name: profile},
            {src.name: mojo_prof},
            {src.name: relations},
        )
        schema_meta = _build_schema_metadata(
            src.name,
            src_graph[src.name],
            relations,
            profile,
            profiling_status,
        )
        schema_meta["row_count"] = row_count
        schema_meta["artifact_format"] = "parquet"
        schema_meta["decision_mode"] = "deterministic_only"
        schema_meta["semantic_aliases"] = schema_meta.get("semantic_aliases") or {}
        schema_meta["provenance"] = {
            "captured_at": datetime.now(UTC).isoformat(),
            "connection_type": connection_type,
            "provider": provider,
            "selection": selection,
            "source_definition": source_definition,
            "dataset_name": dataset_name_value,
        }
        schema_meta["freshness_policy"] = {
            "refreshable": bool(refreshable),
            "mode": "manual_refresh" if refreshable else "immutable_snapshot",
        }

        # ── Serialize to Parquet with embedded metadata ───────────────────────
        arrow_table = arrow_table.replace_schema_metadata({
            **(arrow_table.schema.metadata or {}),
            b"algenta_schema": json.dumps(schema_meta).encode(),
        })
        buf = io.BytesIO()
        pq.write_table(arrow_table, buf)
        parquet_bytes = buf.getvalue()

        # ── Store in memory cache ─────────────────────────────────────────────
        entry = _CachedSource(
            parquet_bytes       = parquet_bytes,
            parquet_schema_meta = json.dumps(schema_meta).encode(),
            profile             = profile,
            mojo_profile        = mojo_prof,
            relations           = relations,
            graph_nodes         = src_graph[src.name],
            schema_meta         = schema_meta,
            mojo_profiling_status = profiling_status,
            content_keyed       = content_keyed,
        )
        async with _CACHE_LOCK:
            _evict_lru()
            _SOURCE_CACHE[source_id] = entry
            if cache_key != source_id:
                _SOURCE_CACHE[cache_key] = entry
    else:
        entry = cached_entry
        profile = entry.profile
        mojo_prof = entry.mojo_profile
        relations = entry.relations
        if schema_meta is None or parquet_bytes is None:
            raise HTTPException(status_code=500, detail={"error": {
                "code": "source_cache_error",
                "message": f"Cached source '{src.name}' could not be reused for org registration.",
            }})
        profiling_status = entry.mojo_profiling_status or (
            schema_meta.get("mojo_profiling_status") if schema_meta else {}
        ) or {}
        row_count = int(schema_meta.get("row_count", 0))

    # ── Persist to disk ────────────────────────────────────────────────────────
    registered_entry = reg.register_source(
        org_id      = org_id,
        source_id   = source_id,
        name        = src.name,
        parquet_bytes = parquet_bytes,
        schema_meta = schema_meta,
        graph_nodes = {},   # reconstructed from meta on reload
        profile     = {},   # not needed on disk
        **metadata_updates,
    )
    src_join_blocks = registered_entry.get("join_blocks") or []
    src_parquet_path = reg.get_source_parquet_path(org_id, source_id)
    if src_parquet_path is None:
        raise HTTPException(
            status_code=500,
            detail={"error": {
                "code": "source_persistence_error",
                "message": f"Registered source '{source_id}' is missing its parquet artifact.",
            }},
        )

    # ── Detect joins to all existing registered sources (async, parallel) ─────
    existing = reg.list_sources(org_id)
    new_connections: list[dict] = []
    existing_total = sum(1 for ex in existing if ex["id"] != source_id)
    scored_join_scan = _should_use_scored_join_scan(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
        existing_sources=existing,
    )
    join_candidate_limit = _join_candidate_limit(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
    )
    join_candidate_min_score = _join_candidate_min_score(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
    )
    join_candidates = reg.candidate_join_sources(
        org_id,
        source_id,
        schema_meta,
        limit=join_candidate_limit,
        exhaustive_threshold=0 if scored_join_scan else 24,
        min_score=join_candidate_min_score,
    )
    candidate_ids = {entry["id"] for entry in join_candidates}
    blocked_join_scan = scored_join_scan

    join_tasks = []
    src_df = _load_join_projection_cached(
        org_id=org_id,
        source_id=source_id,
        parquet_path=src_parquet_path,
        join_blocks=src_join_blocks,
    )
    for ex in existing:
        ex_id = ex["id"]
        if ex_id == source_id:
            continue
        if blocked_join_scan and ex_id not in candidate_ids:
            continue
        ex_parquet_path = reg.get_source_parquet_path(org_id, ex_id)
        if ex_parquet_path is None:
            continue
        join_tasks.append(_detect_joins_between(
            org_id,
            source_id,
            src.name,
            None,
            ex_id,
            ex["name"],
            None,
            src_parquet_path=src_parquet_path,
            other_parquet_path=ex_parquet_path,
            src_df=src_df,
            left_join_blocks=src_join_blocks,
            right_join_blocks=ex.get("join_blocks") or [],
        ))

    if join_tasks:
        join_results = await asyncio.gather(*join_tasks, return_exceptions=True)
        for result in join_results:
            if isinstance(result, list):
                new_connections.extend(result)
            elif isinstance(result, Exception):
                logger.debug("join_task_error", error=str(result))

    if new_connections:
        reg.upsert_connections(org_id, new_connections)
        logger.info("joins_detected", org=org_id, source=src.name,
                    count=len(new_connections))

    prewarm_t0 = time.monotonic()
    _, planner_cache_hit, schema_revision = await _get_registry_planner(
        org_id,
        llm_policy="never",
        auth=auth,
    )
    schema_meta = (
        reg.update_source_meta(org_id, source_id, {"schema_revision": schema_revision})
        or schema_meta
    )
    reg.update_source_entry(org_id, source_id, {"schema_revision": schema_revision})
    prewarm_ms = round((time.monotonic() - prewarm_t0) * 1000, 1)

    elapsed = round((time.monotonic() - t0) * 1000, 1)
    logger.info("source_registered_api", org=org_id, source_id=source_id,
                name=src.name, rows=row_count, joins=len(new_connections),
                join_candidates=len(join_candidates), join_existing_total=existing_total,
                join_scan_mode="scored" if scored_join_scan else "exhaustive",
                join_candidate_limit=join_candidate_limit,
                join_candidate_min_score=join_candidate_min_score,
                planner_cache_hit=planner_cache_hit,
                planner_prewarm_ms=prewarm_ms,
                mojo_profiling_status=profiling_status.get("status"),
                mojo_profiling_reason=profiling_status.get("reason"),
                ingest_mode=ingest_mode,
                latency_ms=elapsed)

    return {
        "source_id":        source_id,
        "dataset_id":       source_id,
        "name":             src.name,
        "dataset_name":     dataset_name_value,
        "status":           "registered",
        "ingest_mode":      ingest_mode,
        "row_count":        row_count,
        "schema":           schema_meta,
        "mojo_profiling_status": profiling_status,
        "connections_found": new_connections,
        "join_candidates_considered": len(join_candidates),
        "join_existing_total": existing_total,
        "join_scan_mode": "scored" if scored_join_scan else "exhaustive",
        "join_candidate_limit": join_candidate_limit,
        "join_candidate_min_score": join_candidate_min_score,
        "planner_cache_hit": planner_cache_hit,
        "planner_schema_revision": schema_revision,
        "planner_prewarm_ms": prewarm_ms,
        "latency_ms":       elapsed,
    }


@router.post(
    "/v1/sources/register",
    summary="Register a data source — profile, index, detect joins to all existing sources",
    description=(
        "**One-time registration per data source.**\n\n"
        "- Full column scan (handles sparse/late-appearing data)\n"
        "- Mojo detects A×B≈C formulas within the source\n"
        "- Mojo detects join keys to every already-registered source\n"
        "- Result cached in memory (hot) + persisted to disk (survives restarts)\n\n"
        "After registration, use `POST /v1/query` with `sources: []` to query "
        "all registered sources, or pass `source_ids` to target specific ones."
    ),
)
async def register_source(
    payload: RegisterRequest,
    auth: AuthContext = Depends(get_current_org),
) -> dict:
    return await _register_source_impl(
        payload,
        auth,
        dataset_name=payload.source.name,
        visibility="private",
        owner_user_id=str(auth.get("user_id")) if auth.get("user_id") else None,
        owner_key_id=str(auth.get("key_id")) if auth.get("key_id") else None,
        description=payload.description,
        refreshable=bool(payload.source.url or payload.source.connection),
        source_definition={"direct": {"url": payload.source.url}} if payload.source.url else None,
    )


async def _detect_joins_between(
    org_id: str,
    src_id: str, src_name: str,
    src_parquet: bytes | None,
    other_id: str, other_name: str,
    other_parquet: bytes | None,
    *,
    src_parquet_path: Path | None = None,
    other_parquet_path: Path | None = None,
    src_df: pd.DataFrame | None = None,
    other_df: pd.DataFrame | None = None,
    left_join_blocks: list[dict[str, Any]] | None = None,
    right_join_blocks: list[dict[str, Any]] | None = None,
) -> list[dict]:
    """
    Run Mojo join_detect between two sources.
    Loads BOTH sources fully from their Parquet bytes so we send ALL unique
    values to Mojo — critical for high-cardinality keys like PART_NUMBER
    where a 200-row sample would rarely show overlap across 12K-row tables.
    Returns connection dicts.
    """
    try:
        metadata_fast_connections = _metadata_fast_join_candidates(
            src_id=src_id,
            src_name=src_name,
            other_id=other_id,
            other_name=other_name,
            left_join_blocks=left_join_blocks,
            right_join_blocks=right_join_blocks,
        )
        if _has_decisive_fast_join(metadata_fast_connections):
            return metadata_fast_connections

        if src_df is not None and other_df is not None:
            projected_src_df = src_df
            projected_other_df = other_df
        elif src_df is not None:
            projected_src_df = src_df
            projected_other_df = _load_join_projection_cached(
                org_id=org_id,
                source_id=other_id,
                parquet_bytes=other_parquet,
                parquet_path=other_parquet_path,
                join_blocks=right_join_blocks,
            )
        elif other_df is not None:
            projected_other_df = other_df
            projected_src_df = _load_join_projection_cached(
                org_id=org_id,
                source_id=src_id,
                parquet_bytes=src_parquet,
                parquet_path=src_parquet_path,
                join_blocks=left_join_blocks,
            )
        else:
            projected_src_df = _load_join_projection_cached(
                org_id=org_id,
                source_id=src_id,
                parquet_bytes=src_parquet,
                parquet_path=src_parquet_path,
                join_blocks=left_join_blocks,
            )
            projected_other_df = _load_join_projection_cached(
                org_id=org_id,
                source_id=other_id,
                parquet_bytes=other_parquet,
                parquet_path=other_parquet_path,
                join_blocks=right_join_blocks,
            )

        # ── Fast path: column-name matching ──────────────────────────────────
        # Two columns with the same name (case-insensitive) across different
        # sources are almost certainly a join key. Confirm with value overlap.
        connections_fast: list[dict] = []
        src_col_lower   = {col.lower(): col for col in projected_src_df.columns}
        other_col_lower = {col.lower(): col for col in projected_other_df.columns}
        shared_names = set(src_col_lower) & set(other_col_lower)
        for name_lower in shared_names:
            src_col   = src_col_lower[name_lower]
            other_col = other_col_lower[name_lower]
            src_counts = projected_src_df[src_col].dropna().astype(str).value_counts().to_dict()
            other_counts = (
                projected_other_df[other_col].dropna().astype(str).value_counts().to_dict()
            )
            src_vals = set(src_counts)
            other_vals = set(other_counts)
            if not src_vals or not other_vals:
                continue
            intersection = src_vals & other_vals
            union = src_vals | other_vals
            jaccard = len(intersection) / len(union) if union else 0.0
            cardinality = _infer_shared_column_cardinality(src_counts, other_counts, intersection)
            src_ur = len(src_vals) / max(len(projected_src_df), 1)
            other_ur = len(other_vals) / max(len(projected_other_df), 1)
            looks_like_key = (
                _looks_like_entity_join_key(src_col)
                or _looks_like_entity_join_key(other_col)
            )
            # Any non-trivial overlap on a same-named column is a join
            enough_overlap = len(intersection) > 3 or (
                cardinality in {"one_to_one", "one_to_many", "many_to_one"}
                and len(intersection) >= 2
                and jaccard >= 0.50
            )
            if jaccard > 0.05 and enough_overlap:
                if (
                    cardinality == "many_to_many"
                    and not looks_like_key
                    and max(src_ur, other_ur) < 0.80
                ):
                    continue
                connections_fast.append({
                    "source_a":      src_id,
                    "source_a_name": src_name,
                    "col_a":         src_col,
                    "source_b":      other_id,
                    "source_b_name": other_name,
                    "col_b":         other_col,
                    "confidence":    _shared_name_join_confidence(jaccard, cardinality),
                    "cardinality":   cardinality,
                    "overlap":       round(jaccard, 4),
                })

        # A strong exact-name key join is already sufficient to connect the
        # sources. Do not spend additional time on value-based Mojo search.
        if _has_decisive_fast_join(connections_fast):
            return connections_fast

        # ── Mojo path: value-based join detection for remaining columns ───────
        # Cap at 20 highest-uniqueness columns per source to bound payload size.
        def _col_candidates(df: pd.DataFrame, label: str, limit: int = 20) -> dict[str, dict]:
            n = len(df)
            scored = []
            for col in df.columns:
                unique_vals = df[col].dropna().astype(str).unique()
                ur = len(unique_vals) / max(n, 1)
                if ur > 0.25 and len(unique_vals) > 5:
                    scored.append((ur, col, unique_vals))
            # Keep only top-limit by uniqueness ratio
            scored.sort(reverse=True)
            cols: dict[str, dict] = {}
            for ur, col, unique_vals in scored[:limit]:
                cols[f"{label}.{col}"] = {
                    "values":       unique_vals[:1000].tolist(),
                    "unique_ratio": round(ur, 4),
                    "sample_size":  n,
                }
            return cols

        columns: dict[str, dict] = {}
        columns.update(_col_candidates(projected_src_df, src_name))
        columns.update(_col_candidates(projected_other_df, other_name))

        if not columns:
            return connections_fast

        result = await _call_mojo_join_detect(src_name, other_name, columns, min_confidence=0.4)
        if not result:
            return connections_fast

        mojo_connections = []
        for jk in result.get("join_keys", []):
            field_a = jk.get("field_a", "")
            field_b = jk.get("field_b", "")
            mojo_connections.append({
                "source_a":      src_id,
                "source_a_name": src_name,
                "col_a":         field_a,
                "source_b":      other_id,
                "source_b_name": other_name,
                "col_b":         field_b,
                "confidence":    jk.get("confidence", 0.0),
                "cardinality":   jk.get("cardinality", "?"),
                "overlap":       jk.get("overlap", 0.0),
            })

        # Merge fast-path + Mojo, fast-path wins on ties (it uses exact overlap)
        seen: set[tuple] = {(c["col_a"], c["col_b"]) for c in connections_fast}
        for c in mojo_connections:
            key = (c["col_a"], c["col_b"])
            if key not in seen:
                connections_fast.append(c)
                seen.add(key)
        return connections_fast

    except Exception as exc:
        logger.debug("join_detect_failed", src=src_name, other=other_name, error=str(exc))
        return []


# ── List ────────────────────────────────────────────────────────────────────────

@router.get("/v1/sources", summary="List all registered sources for this org")
async def list_sources(
    auth: AuthContext = Depends(get_current_org),
    page: int = Query(default=1, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> dict:
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_connection_service import filter_visible_datasets

    sources = filter_visible_datasets(reg.list_sources(org_id), auth)
    paged = paginate_sequence(sources, page=page, limit=limit)
    return {
        "sources": paged.items,
        "count": len(paged.items),
        "total": paged.total,
        "page": paged.page,
        "limit": paged.limit,
        "pages": paged.pages,
    }


# ── Connection graph ────────────────────────────────────────────────────────────

@router.get(
    "/v1/sources/graph",
    summary="Connection graph — all detected join paths between registered sources",
)
async def get_graph(auth: AuthContext = Depends(get_current_org)) -> dict:
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_connection_service import filter_visible_datasets

    sources = filter_visible_datasets(reg.list_sources(org_id), auth)
    visible_ids = {source["id"] for source in sources}
    connections = [
        conn for conn in reg.get_connections(org_id)
        if conn.get("source_a") in visible_ids and conn.get("source_b") in visible_ids
    ]

    # Build adjacency summary
    adjacency: dict[str, list[str]] = {}
    for c in connections:
        a_name = c.get("source_a_name", c["source_a"])
        b_name = c.get("source_b_name", c["source_b"])
        adjacency.setdefault(a_name, []).append(
            f"{b_name}.{c['col_b']} via {a_name}.{c['col_a']} (conf={c['confidence']:.2f})"
        )

    return {
        "sources":     [s["name"] for s in sources],
        "connections": connections,
        "adjacency":   adjacency,
        "total_connections": len(connections),
    }


# ── Get one ─────────────────────────────────────────────────────────────────────

@router.get("/v1/sources/{source_id}", summary="Get schema for a registered source")
async def get_source(
    source_id: str,
    auth: AuthContext = Depends(get_current_org),
) -> dict:
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_connection_service import get_visible_dataset_entry

    entry = get_visible_dataset_entry(org_id, source_id, auth)
    if not entry:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found",
            "message": f"Source '{source_id}' not found in registry."}})
    meta = reg.get_source_meta(org_id, source_id)
    if not meta:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found",
            "message": f"Source '{source_id}' not found in registry."}})
    return {"source_id": source_id, "dataset_id": source_id, "entry": entry, "schema": meta}


# ── Delete ──────────────────────────────────────────────────────────────────────

@router.delete("/v1/sources/{source_id}", summary="Remove a registered source")
async def delete_source(
    source_id: str,
    auth: AuthContext = Depends(get_current_org),
) -> dict:
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_connection_service import (
        dataset_manageable,
        get_visible_dataset_entry,
    )

    entry = get_visible_dataset_entry(org_id, source_id, auth)
    if entry is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found",
            "message": f"Source '{source_id}' not found."}})
    if not dataset_manageable(entry, auth):
        raise HTTPException(
            status_code=403,
            detail=access_scope_denied_error(
                "You do not have permission to delete this dataset.",
            ),
        )
    existed = reg.delete_source(org_id, source_id)
    # Also evict from memory cache
    async with _CACHE_LOCK:
        _SOURCE_CACHE.pop(source_id, None)
    if not existed:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found",
            "message": f"Source '{source_id}' not found."}})
    return {"source_id": source_id, "status": "deleted"}
