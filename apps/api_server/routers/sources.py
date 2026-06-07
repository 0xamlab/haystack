"""Source registry endpoints."""

from __future__ import annotations

import asyncio
import io
import json
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api_server.error_payloads import access_scope_denied_error
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.pagination import paginate_sequence
from apps.api_server.routers.data_map import (
    _call_mojo_column_profile,
    _call_mojo_join_detect,
)
from apps.api_server.routers.query import (
    _CACHE_LOCK,
    _SOURCE_CACHE,
    _arrow_physical_types,
    _build_schema_metadata,
    _CachedSource,
    _detect_relations,
    _get_registry_planner,
    _load_profiled_source,
    _source_cache_key,
    _source_cache_put,
    _try_incremental_registry_planner_update,
    build_schema_graph,
)
from apps.api_server.routers.query_contract import _http_error
from apps.api_server.schemas.data_map import DataSource
from apps.api_server.services import source_registry as reg
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.data_connection_discovery import (
    build_discovery_labels,
    build_discovery_metadata,
)
from apps.api_server.services.data_map_errors import MojoInstrumentationError
from apps.api_server.services.data_map_mojo_profiles import (
    _build_mojo_column_profile_columns,
    _mojo_column_profile_sample_limits,
    _mojo_profiling_status_from_result,
)
from apps.api_server.services.source_join_cache import (
    _JOIN_NAME_STATS_CACHE,
    _JOIN_PROJECTION_CACHE,
    _JOIN_VALUE_CANDIDATE_CACHE,
)
from apps.api_server.services.source_join_cache import (
    build_join_name_stats as _build_join_name_stats,
)
from apps.api_server.services.source_join_cache import (
    build_join_value_candidates as _build_join_value_candidates,
)
from apps.api_server.services.source_join_policy import (
    _bounded_fast_join_connections,
    _deep_join_projection_columns,
    _has_sufficient_fast_join_evidence,
    _infer_shared_column_cardinality_from_stats,
    _join_candidate_limit,
    _metadata_fast_join_candidates,
    _should_accept_fast_join_connections,
    _should_collect_fast_join_name_stats,
)
from apps.api_server.services.source_registration_join_helpers import (
    detect_joins_between_for_registration as _detect_joins_between_support,
)
from apps.api_server.services.source_registration_join_helpers import (
    join_candidate_min_score as _join_candidate_min_score_support,
)
from apps.api_server.services.source_registration_join_helpers import (
    join_projection_max_rows as _join_projection_max_rows_support,
)
from apps.api_server.services.source_registration_join_helpers import (
    load_join_name_stats_cached_for_registration as _load_join_name_stats_cached_support,
)
from apps.api_server.services.source_registration_join_helpers import (
    load_join_projection_cached_for_registration as _load_join_projection_cached_support,
)
from apps.api_server.services.source_registration_join_helpers import (
    load_join_projection_for_registration as _load_join_projection_support,
)
from apps.api_server.services.source_registration_join_helpers import (
    load_join_value_candidates_cached_for_registration as _load_join_candidates_support,
)
from apps.api_server.services.source_registration_join_helpers import (
    should_use_scored_join_scan as _should_use_scored_join_scan_support,
)
from apps.api_server.services.source_registration_responses import (
    build_already_registered_response,
    build_freshness_policy,
    build_registered_source_response,
    build_registration_metadata_updates,
    build_registration_provenance,
)
from apps.api_server.services.source_registration_scope import (
    resolve_registration_scopes,
)
from apps.api_server.services.workspace_scope import workspace_id_for_write

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Source Registry"])
_COMPAT_TEST_EXPORTS = (
    _JOIN_NAME_STATS_CACHE,
    _JOIN_PROJECTION_CACHE,
    _JOIN_VALUE_CANDIDATE_CACHE,
    _has_sufficient_fast_join_evidence,
    _infer_shared_column_cardinality_from_stats,
)


def _should_use_scored_join_scan(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
    existing_sources: list[dict[str, Any]] | None = None,
    build_join_blocks_fn: Any | None = None,
) -> bool:
    return _should_use_scored_join_scan_support(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
        existing_sources=existing_sources,
        build_join_blocks_fn=build_join_blocks_fn or reg._build_join_blocks,
    )


def _join_candidate_min_score(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
    build_join_blocks_fn: Any | None = None,
) -> float:
    return _join_candidate_min_score_support(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
        build_join_blocks_fn=build_join_blocks_fn or reg._build_join_blocks,
    )


def _load_join_projection(*args: Any, **kwargs: Any) -> Any:
    return _load_join_projection_support(
        *args,
        **kwargs,
        deep_join_projection_columns_fn=_deep_join_projection_columns,
    )


def _load_join_projection_cached(**kwargs: Any) -> Any:
    return _load_join_projection_cached_support(
        **kwargs,
        load_join_projection_fn=_load_join_projection,
        source_schema_revision_fn=reg.source_schema_revision,
        deep_join_projection_columns_fn=_deep_join_projection_columns,
    )


def _load_join_value_candidates_cached(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return _load_join_candidates_support(
        **kwargs,
        load_join_projection_cached_fn=_load_join_projection_cached,
        build_join_value_candidates_fn=_build_join_value_candidates,
        source_schema_revision_fn=reg.source_schema_revision,
        deep_join_projection_columns_fn=_deep_join_projection_columns,
    )


def _load_join_name_stats_cached(**kwargs: Any) -> dict[str, dict[str, Any]]:
    return _load_join_name_stats_cached_support(
        **kwargs,
        load_join_projection_cached_fn=_load_join_projection_cached,
        build_join_name_stats_fn=_build_join_name_stats,
        source_schema_revision_fn=reg.source_schema_revision,
        deep_join_projection_columns_fn=_deep_join_projection_columns,
    )


def _join_projection_max_rows(*, row_count: int) -> int | None:
    return _join_projection_max_rows_support(row_count=row_count)


async def _detect_joins_between(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    kwargs.setdefault("metadata_fast_join_candidates_fn", _metadata_fast_join_candidates)
    kwargs.setdefault("load_join_projection_cached_fn", _load_join_projection_cached)
    kwargs.setdefault("load_join_name_stats_cached_fn", _load_join_name_stats_cached)
    kwargs.setdefault(
        "load_join_value_candidates_cached_fn",
        _load_join_value_candidates_cached,
    )
    kwargs.setdefault("call_mojo_join_detect_fn", _call_mojo_join_detect)
    kwargs.setdefault("logger", logger)
    return await _detect_joins_between_support(*args, **kwargs)


class RegisterRequest(BaseModel):
    source: DataSource
    description: str | None = Field(default=None, description="Optional human description")


def _source_registration_failed_error(
    source_name: str,
    *,
    stage: str,
    exc: Exception,
    status_code: int = 400,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": "source_registration_failed",
                "message": (
                    f"Source '{source_name}' could not be registered during {stage}: {exc}"
                ),
                "details": {
                    "stage": stage,
                    "error_type": type(exc).__name__,
                },
            }
        },
    )


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
    discovery_labels: dict[str, Any] | None = None,
    discovery_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import pyarrow.parquet as pq

    t0 = time.monotonic()
    src = payload.source
    org_id = str(auth["org_id"])
    # Sub-tenancy scope: stamp + dedup datasets per workspace (None → org-wide/legacy).
    _ws = workspace_id_for_write(auth)
    workspace_scope_id = str(_ws) if _ws is not None else None

    # ── Cache key ──────────────────────────────────────────────────────────────
    cache_key, content_keyed = _source_cache_key(src)
    visibility_value, owner_scope, owner_key_scope, source_id = resolve_registration_scopes(
        cache_key=cache_key,
        visibility=visibility,
        auth_user_id=str(auth.get("user_id")) if auth.get("user_id") else None,
        auth_key_id=str(auth.get("key_id")) if auth.get("key_id") else None,
        owner_user_id=owner_user_id,
        owner_key_id=owner_key_id,
        source_id_for_fn=reg.source_id_for,
        workspace_id=workspace_scope_id,
    )
    dataset_name_value = dataset_name or src.name
    dataset_description = description if description is not None else payload.description
    metadata_updates = build_registration_metadata_updates(
        dataset_name=dataset_name_value,
        connector_id=connector_id,
        visibility=visibility_value,
        owner_user_id=owner_scope,
        owner_key_id=owner_key_scope,
        description=dataset_description,
        selection=selection,
        connection_type=connection_type,
        provider=provider,
        refreshable=refreshable,
        source_definition=source_definition,
        discovery_labels=discovery_labels
        or build_discovery_labels(provider or connection_type or "file"),
        discovery_metadata=discovery_metadata
        or build_discovery_metadata(provider or connection_type or "file"),
        workspace_id=workspace_scope_id,
    )

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
        return build_already_registered_response(
            source_id=source_id,
            source_name=src.name,
            dataset_name=dataset_name_value,
            schema=cache_hit_schema,
            row_count=int(cache_hit_schema.get("row_count"))
            if isinstance(cache_hit_schema.get("row_count"), int)
            else None,
            planner_cache_hit=planner_cache_hit,
            planner_schema_revision=schema_revision,
            planner_prewarm_ms=prewarm_ms,
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    if cached_entry is None:
        # ── Load + profile ─────────────────────────────────────────────────────
        loaded = await _load_profiled_source(src, org_id=org_id)
        if loaded.row_count <= 0 or loaded.arrow_table is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "empty_source",
                        "message": f"Source '{src.name}' returned no records.",
                    }
                },
            )

        profile = loaded.profile
        arrow_table = loaded.arrow_table
        row_count = loaded.row_count
        ingest_mode = loaded.ingest_mode

        try:
            stage = "mojo_profile"
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
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "source_registration_processing_failed",
                org=org_id,
                source=src.name,
                stage=stage,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise _source_registration_failed_error(src.name, stage=stage, exc=exc) from exc
        profiling_status = _mojo_profiling_status_from_result(profiler_result)
        mojo_prof = (profiler_result or {}).get("profiles", {})
        if profiling_status.get("status") != "enabled":
            logger.info(
                "source_registration_mojo_profiling_disabled",
                org=org_id,
                source=src.name,
                reason=profiling_status.get("reason"),
            )

        try:
            stage = "build_schema_graph"
            src_graph = build_schema_graph(
                {src.name: profile},
                {src.name: mojo_prof},
                {src.name: relations},
            )
            stage = "build_schema_metadata"
            schema_meta = _build_schema_metadata(
                src.name,
                src_graph[src.name],
                relations,
                profile,
                profiling_status,
                _arrow_physical_types(arrow_table.schema),
            )
            schema_meta["row_count"] = row_count
            schema_meta["artifact_format"] = "parquet"
            schema_meta["decision_mode"] = "deterministic_only"
            schema_meta["semantic_aliases"] = schema_meta.get("semantic_aliases") or {}
            schema_meta["provenance"] = build_registration_provenance(
                captured_at=datetime.now(UTC).isoformat(),
                connection_type=connection_type,
                provider=provider,
                selection=selection,
                source_definition=source_definition,
                dataset_name=dataset_name_value,
            )
            schema_meta["freshness_policy"] = build_freshness_policy(refreshable)

            stage = "serialize_parquet"
            arrow_table = arrow_table.replace_schema_metadata(
                {
                    **(arrow_table.schema.metadata or {}),
                    b"algenta_schema": json.dumps(schema_meta).encode(),
                }
            )
            buf = io.BytesIO()
            pq.write_table(arrow_table, buf)
            parquet_bytes = buf.getvalue()

            stage = "cache_source"
            entry = _CachedSource(
                parquet_bytes=parquet_bytes,
                parquet_schema_meta=json.dumps(schema_meta).encode(),
                profile=profile,
                mojo_profile=mojo_prof,
                relations=relations,
                graph_nodes=src_graph[src.name],
                schema_meta=schema_meta,
                mojo_profiling_status=profiling_status,
                content_keyed=content_keyed,
            )
            async with _CACHE_LOCK:
                _source_cache_put(entry, source_id, cache_key)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "source_registration_processing_failed",
                org=org_id,
                source=src.name,
                stage=stage,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise _source_registration_failed_error(src.name, stage=stage, exc=exc) from exc
    else:
        entry = cached_entry
        profile = entry.profile
        mojo_prof = entry.mojo_profile
        relations = entry.relations
        if schema_meta is None or parquet_bytes is None:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": "source_cache_error",
                        "message": (
                            f"Cached source '{src.name}' could not be reused for org registration."
                        ),
                    }
                },
            )
        profiling_status = (
            entry.mojo_profiling_status
            or (schema_meta.get("mojo_profiling_status") if schema_meta else {})
            or {}
        )
        row_count = int(schema_meta.get("row_count", 0))

    # ── Persist to disk ────────────────────────────────────────────────────────
    try:
        registered_entry = reg.register_source(
            org_id=org_id,
            source_id=source_id,
            name=src.name,
            parquet_bytes=parquet_bytes,
            schema_meta=schema_meta,
            graph_nodes={},  # reconstructed from meta on reload
            profile={},  # not needed on disk
            **metadata_updates,
        )
    except Exception as exc:
        logger.warning(
            "source_registration_persistence_failed",
            org=org_id,
            source=src.name,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise _source_registration_failed_error(
            src.name,
            stage="persist_source",
            exc=exc,
            status_code=503,
        ) from exc
    src_join_blocks = registered_entry.get("join_blocks") or []
    src_parquet_path = reg.get_source_parquet_path(org_id, source_id)
    if src_parquet_path is None:
        raise _source_registration_failed_error(
            src.name,
            stage="persist_source",
            exc=RuntimeError(f"Registered source '{source_id}' is missing its parquet artifact."),
            status_code=503,
        )

    # ── Detect joins to existing registered sources (async, parallel) ─────────
    # Scope join detection to datasets the caller's workspace can see, so a workspace-scoped
    # registration never creates cross-workspace join edges in the org-wide connections graph.
    # An unscoped (org-wide) platform registration keeps the full org view (gate passes for all).
    from apps.api_server.services.data_visibility import dataset_in_workspace_scope

    existing = [
        entry
        for entry in reg.list_sources(org_id)
        if dataset_in_workspace_scope(entry, auth)
    ]
    new_connections: list[dict[str, Any]] = []
    existing_total = sum(1 for ex in existing if ex["id"] != source_id)
    scored_join_scan = _should_use_scored_join_scan(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
        build_join_blocks_fn=reg._build_join_blocks,
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
        build_join_blocks_fn=reg._build_join_blocks,
    )
    join_candidates = reg.candidate_join_sources(
        org_id,
        source_id,
        schema_meta,
        source_name=src.name,
        limit=join_candidate_limit,
        exhaustive_threshold=0 if scored_join_scan else 24,
        min_score=join_candidate_min_score,
    )
    candidate_ids = {entry["id"] for entry in join_candidates}
    blocked_join_scan = scored_join_scan

    join_tasks = []
    pending_join_sources: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for ex in existing:
        ex_id = ex["id"]
        if ex_id == source_id:
            continue
        if blocked_join_scan and ex_id not in candidate_ids:
            continue
        ex_join_blocks = ex.get("join_blocks") or []
        metadata_fast_connections = _metadata_fast_join_candidates(
            src_id=source_id,
            src_name=src.name,
            other_id=ex_id,
            other_name=ex["name"],
            left_join_blocks=src_join_blocks,
            right_join_blocks=ex_join_blocks,
        )
        if _should_accept_fast_join_connections(
            metadata_fast_connections,
            left_join_blocks=src_join_blocks,
            right_join_blocks=ex_join_blocks,
            left_rows=row_count,
            right_rows=int(ex.get("row_count", 0) or 0),
        ):
            new_connections.extend(_bounded_fast_join_connections(metadata_fast_connections))
            continue
        pending_join_sources.append((ex, ex_join_blocks))

    requires_src_name_stats = any(
        _should_collect_fast_join_name_stats(
            left_join_blocks=src_join_blocks,
            right_join_blocks=ex_join_blocks,
        )
        for _ex, ex_join_blocks in pending_join_sources
    )
    src_projection_max_rows = _join_projection_max_rows(row_count=row_count)

    if pending_join_sources:
        src_df = _load_join_projection_cached(
            org_id=org_id,
            source_id=source_id,
            parquet_path=src_parquet_path,
            join_blocks=src_join_blocks,
            max_rows=src_projection_max_rows,
        )
        src_name_stats = (
            _load_join_name_stats_cached(
                org_id=org_id,
                source_id=source_id,
                join_blocks=src_join_blocks,
                df=src_df,
                parquet_path=src_parquet_path,
                max_rows=src_projection_max_rows,
            )
            if requires_src_name_stats
            else None
        )
    else:
        src_df = None
        src_name_stats = None

    for ex, ex_join_blocks in pending_join_sources:
        ex_id = ex["id"]
        ex_parquet_path = reg.get_source_parquet_path(org_id, ex_id)
        if ex_parquet_path is None:
            continue
        join_tasks.append(
            _detect_joins_between(
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
                src_name_stats=src_name_stats,
                src_projection_max_rows=src_projection_max_rows,
                other_projection_max_rows=_join_projection_max_rows(
                    row_count=int(ex.get("row_count", 0) or 0)
                ),
                left_join_blocks=src_join_blocks,
                right_join_blocks=ex_join_blocks,
            )
        )

    if join_tasks:
        join_results = await asyncio.gather(*join_tasks, return_exceptions=True)
        for result in join_results:
            if isinstance(result, list):
                new_connections.extend(result)
            elif isinstance(result, Exception):
                logger.debug("join_task_error", error=str(result))

    if new_connections:
        reg.upsert_connections(org_id, new_connections)
        logger.info("joins_detected", org=org_id, source=src.name, count=len(new_connections))

    prewarm_t0 = time.monotonic()
    source_schema_revision = str(
        registered_entry.get("source_schema_revision")
        or reg.source_schema_revision(org_id, source_id)
    )
    planner_cache_hit = False
    schema_revision = source_schema_revision
    try:
        planner_cache_hit, schema_revision = await _try_incremental_registry_planner_update(
            org_id,
            llm_policy="never",
            auth=auth,
            source_id=source_id,
            source_name=src.name,
            schema_meta=schema_meta,
            source_schema_revision=source_schema_revision,
            parquet_path=src_parquet_path,
            new_connections=new_connections,
        )
        if not planner_cache_hit:
            _, planner_cache_hit, schema_revision = await _get_registry_planner(
                org_id,
                llm_policy="never",
                auth=auth,
            )
        reg.update_source_entry(
            org_id,
            source_id,
            {"schema_revision": schema_revision},
            touch_schema=False,
        )
    except Exception as exc:
        logger.warning(
            "source_registration_planner_prewarm_failed",
            org=org_id,
            source=src.name,
            source_id=source_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        planner_cache_hit = False
        schema_revision = source_schema_revision
    prewarm_ms = round((time.monotonic() - prewarm_t0) * 1000, 1)

    elapsed = round((time.monotonic() - t0) * 1000, 1)
    logger.info(
        "source_registered_api",
        org=org_id,
        source_id=source_id,
        name=src.name,
        rows=row_count,
        joins=len(new_connections),
        join_candidates=len(join_candidates),
        join_existing_total=existing_total,
        join_scan_mode="scored" if scored_join_scan else "exhaustive",
        join_candidate_limit=join_candidate_limit,
        join_candidate_min_score=join_candidate_min_score,
        planner_cache_hit=planner_cache_hit,
        planner_prewarm_ms=prewarm_ms,
        mojo_profiling_status=profiling_status.get("status"),
        mojo_profiling_reason=profiling_status.get("reason"),
        ingest_mode=ingest_mode,
        latency_ms=elapsed,
    )

    return build_registered_source_response(
        source_id=source_id,
        source_name=src.name,
        dataset_name=dataset_name_value,
        ingest_mode=ingest_mode,
        row_count=row_count,
        schema=schema_meta,
        mojo_profiling_status=profiling_status,
        connections_found=new_connections,
        join_candidates_considered=len(join_candidates),
        join_existing_total=existing_total,
        join_scan_mode="scored" if scored_join_scan else "exhaustive",
        join_candidate_limit=join_candidate_limit,
        join_candidate_min_score=join_candidate_min_score,
        planner_cache_hit=planner_cache_hit,
        planner_schema_revision=schema_revision,
        planner_prewarm_ms=prewarm_ms,
        latency_ms=elapsed,
    )


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
) -> dict[str, Any]:
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


# ── List ────────────────────────────────────────────────────────────────────────


@router.get("/v1/sources", summary="List all registered sources for this org")
async def list_sources(
    auth: AuthContext = Depends(get_current_org),
    page: int = Query(default=1, ge=1),
    limit: int | None = Query(default=None, ge=1, le=200),
) -> dict[str, Any]:
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
async def get_graph(auth: AuthContext = Depends(get_current_org)) -> dict[str, Any]:
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_connection_service import filter_visible_datasets

    sources = filter_visible_datasets(reg.list_sources(org_id), auth)
    visible_ids = {source["id"] for source in sources}
    connections = [
        conn
        for conn in reg.get_connections(org_id)
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
        "sources": [s["name"] for s in sources],
        "connections": connections,
        "adjacency": adjacency,
        "total_connections": len(connections),
    }


# ── Get one ─────────────────────────────────────────────────────────────────────


@router.get("/v1/sources/{source_id}", summary="Get schema for a registered source")
async def get_source(
    source_id: str,
    auth: AuthContext = Depends(get_current_org),
) -> dict[str, Any]:
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_connection_service import get_visible_dataset_entry

    entry = get_visible_dataset_entry(org_id, source_id, auth)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": f"Source '{source_id}' not found in registry.",
                }
            },
        )
    meta = reg.get_source_meta(org_id, source_id)
    if not meta:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "not_found",
                    "message": f"Source '{source_id}' not found in registry.",
                }
            },
        )
    return {"source_id": source_id, "dataset_id": source_id, "entry": entry, "schema": meta}


# ── Delete ──────────────────────────────────────────────────────────────────────


@router.delete("/v1/sources/{source_id}", summary="Remove a registered source")
async def delete_source(
    source_id: str,
    auth: AuthContext = Depends(get_current_org),
) -> dict[str, Any]:
    org_id = str(auth["org_id"])
    from apps.api_server.services.data_connection_service import (
        dataset_manageable,
        get_visible_dataset_entry,
    )

    entry = get_visible_dataset_entry(org_id, source_id, auth)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Source '{source_id}' not found."}},
        )
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
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": f"Source '{source_id}' not found."}},
        )
    return {"source_id": source_id, "status": "deleted"}
