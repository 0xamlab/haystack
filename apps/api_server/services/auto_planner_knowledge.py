from __future__ import annotations

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import structlog

from apps.api_server.services.auto_planner_artifacts import (
    _discover_local_source_map,
    _load_records,
    _profile_records,
)
from apps.api_server.services.data_map_mojo_profiles import (
    _build_mojo_column_profile_columns,
)
from apps.api_server.services.mojo_column_rank_resolver import MojoColumnRankResolver
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

logger = structlog.get_logger(__name__)

_LAZY_VECTOR_RESOLVER_TOTAL_COLUMN_THRESHOLD = 1_500
_LAZY_VECTOR_RESOLVER_WIDE_SOURCE_COLUMN_THRESHOLD = 96


def cache_dir(planner: Any) -> Path:
    return cast(Path, planner.data_dir) / ".algenta_cache"


def discover_sources(planner: Any) -> list[str]:
    return list(_discover_local_source_map(planner.data_dir).keys())


def cache_fresh(
    planner: Any,
    name: str,
    csv_path: Path,
    *,
    cache_version: int,
) -> bool:
    meta_path = cache_dir(planner) / f"{name}.meta.json"
    parquet_path = cache_dir(planner) / f"{name}.parquet"
    if not meta_path.exists() or not parquet_path.exists():
        return False
    try:
        meta = json.loads(meta_path.read_text())
        if meta.get("cache_version") != cache_version:
            return False
    except Exception:
        return False
    csv_mtime = csv_path.stat().st_mtime
    cache_mtime = min(meta_path.stat().st_mtime, parquet_path.stat().st_mtime)
    return cache_mtime > csv_mtime


def load_from_cache(planner: Any, name: str) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    meta_raw = json.loads((cache_dir(planner) / f"{name}.meta.json").read_text())
    profile = meta_raw.get("profiles", {})
    mojo_profile = meta_raw.get("mojo_profiles", {})
    relations = meta_raw.get("relations", [])
    planner._parquet_paths[name] = cache_dir(planner) / f"{name}.parquet"
    return profile, mojo_profile, relations


def ensure_records(planner: Any, name: str) -> None:
    if name in planner.tables:
        return
    parquet_path = planner._parquet_paths.get(name)
    if parquet_path and parquet_path.exists():
        try:
            import pyarrow.parquet as pq

            initialize_pyarrow_parquet_runtime()
            table = pq.read_table(str(parquet_path))
            planner.tables[name] = table.to_pylist()
            logger.debug(
                "auto_planner_records_lazy_loaded",
                src=name,
                rows=len(planner.tables[name]),
            )
        except Exception as exc:
            logger.debug(
                "auto_planner_parquet_lazy_error",
                src=name,
                error=str(exc),
            )


def write_cache(
    planner: Any,
    name: str,
    records: list[dict[str, Any]],
    mojo_profiles: dict[str, Any],
    relations: list[Any],
    *,
    profiles: dict[str, Any] | None = None,
    cache_version: int,
) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        cache_path = cache_dir(planner)
        cache_path.mkdir(parents=True, exist_ok=True)

        if not records:
            return

        keys = list(records[0].keys())
        arrays: dict[str, pa.Array] = {}
        for key in keys:
            values: list[Any] = []
            for record in records:
                value = record.get(key)
                if isinstance(value, str) and value.strip().lower() in {
                    "",
                    "?",
                    "none",
                    "null",
                    "nan",
                }:
                    values.append(None)
                else:
                    values.append(value)
            try:
                arrays[key] = pa.array(values)
            except Exception:
                arrays[key] = pa.array(
                    [str(value) if value is not None else None for value in values],
                    type=pa.string(),
                )

        table = pa.table(arrays)
        buffer = io.BytesIO()
        pq.write_table(table, buffer)
        (cache_path / f"{name}.parquet").write_bytes(buffer.getvalue())
        (cache_path / f"{name}.meta.json").write_text(
            json.dumps(
                {
                    "cache_version": cache_version,
                    "profiles": profiles or {},
                    "mojo_profiles": mojo_profiles,
                    "relations": relations,
                }
            )
        )
        logger.debug("auto_planner_cache_written", src=name, rows=len(records))
    except Exception as exc:
        logger.debug("auto_planner_cache_write_error", src=name, error=str(exc))


def build_knowledge(
    planner: Any,
    source_map: dict[str, str] | None = None,
) -> None:
    start = time.perf_counter()
    if planner._mojo_binary:
        planner.mojo_engines = planner._probe_engines()
        logger.debug("auto_planner_engines", engines=planner.mojo_engines)

    if source_map is None:
        source_map = _discover_local_source_map(planner.data_dir)

    planner.tables = {}
    planner.profiles = {}
    planner._mojo_profiles = {}
    planner._relations = {}
    planner._plan_cache = {}
    planner._join_candidate_columns = {}
    planner._join_evidence_cache = {}
    planner._group_join_evidence_cache = {}
    planner._adaptive_source_context = {}
    planner._metric_resolution_cache = {}
    planner._dimension_resolution_cache = {}

    need_mojo: list[str] = []
    for name, filename in source_map.items():
        source_path = planner.data_dir / filename
        if not source_path.exists():
            continue

        if planner._cache_fresh(name, source_path):
            try:
                profile, mojo_profile, relations = planner._load_from_cache(name)
                planner.profiles[name] = profile
                planner._mojo_profiles[name] = mojo_profile
                planner._relations[name] = relations
                logger.debug("auto_planner_cache_hit", src=name)
                continue
            except Exception as exc:
                logger.debug("auto_planner_cache_load_error", src=name, error=str(exc))

        records = _load_records(source_path, max_rows=planner.max_rows)
        if records:
            planner.tables[name] = records
            planner.profiles[name] = _profile_records(records)
            need_mojo.append(name)

    if need_mojo:
        need_items = [
            (name, planner.profiles[name]) for name in need_mojo if name in planner.profiles
        ]
        if "column_profile" in planner.mojo_engines and "relation_detect" in planner.mojo_engines:
            with ThreadPoolExecutor(max_workers=max(len(need_items) * 2, 1)) as executor:
                mojo_profiles = list(executor.map(planner._mojo_profile_source, need_items))
                relations = list(executor.map(planner._mojo_relations_source, need_items))
            for name, mojo_profile in mojo_profiles:
                planner._mojo_profiles[name] = mojo_profile
            for name, relation_list in relations:
                planner._relations[name] = relation_list
        elif "column_profile" in planner.mojo_engines:
            for name, mojo_profile in (planner._mojo_profile_source(item) for item in need_items):
                planner._mojo_profiles[name] = mojo_profile
            for name in need_mojo:
                planner._relations.setdefault(name, [])
        else:
            for name in need_mojo:
                planner._mojo_profiles.setdefault(name, {})
                planner._relations.setdefault(name, [])

        for name in need_mojo:
            if name in planner.tables:
                planner._write_cache(
                    name,
                    planner.tables[name],
                    planner._mojo_profiles.get(name, {}),
                    planner._relations.get(name, []),
                    profiles=planner.profiles.get(name, {}),
                )

    from apps.api_server.routers.query import build_schema_graph

    planner.graph = build_schema_graph(
        planner.profiles,
        planner._mojo_profiles,
        planner._relations,
    )
    planner._rebuild_adaptive_context()
    elapsed = (time.perf_counter() - start) * 1000
    logger.debug(
        "auto_planner_knowledge_built",
        sources=list(planner.tables.keys()),
        engines=planner.mojo_engines,
        elapsed_ms=round(elapsed, 1),
    )
    planner._build_vector_resolver()


def build_vector_resolver(
    planner: Any,
    *,
    mojo_column_rank_mode: str,
) -> None:
    if not planner.graph:
        planner._vector_resolver_dirty = False
        return
    try:
        from mojo.engine.vector_kernels.resolver import ColumnVectorResolver

        base_resolver = ColumnVectorResolver.from_planner_graph(planner.graph)
        fill_rates: dict[tuple[str, str], float] = {}
        for source_name, columns in planner.graph.items():
            for column_name, node in columns.items():
                fill_rates[(source_name, column_name)] = float(
                    getattr(node, "fill_rate", 1.0) or 1.0
                )
        use_mojo_column_rank = "column_rank" in planner.mojo_engines and mojo_column_rank_mode in {
            "auto",
            "force",
        }
        if use_mojo_column_rank:
            planner._vector_resolver = MojoColumnRankResolver(
                base_resolver,
                call_mojo=planner._call_mojo,
                fill_rates=fill_rates,
                binary_path=planner._mojo_binary,
            )
            resolver_mode = "mojo_column_rank"
        else:
            planner._vector_resolver = base_resolver
            resolver_mode = "python"
        n_cols = sum(len(list(columns.keys())) for columns in planner.graph.values())
        logger.debug(
            "auto_planner_vector_resolver_built",
            sources=list(planner.graph.keys()),
            n_columns=n_cols,
            mode=resolver_mode,
        )
    except Exception as exc:
        logger.debug("auto_planner_vector_resolver_skip", reason=str(exc))
        planner._vector_resolver = None
    finally:
        planner._vector_resolver_dirty = False


def ensure_vector_resolver_ready(planner: Any) -> None:
    if not bool(getattr(planner, "_vector_resolver_dirty", False)):
        return
    planner._build_vector_resolver()


def append_vector_resolver_source(planner: Any, source_name: str) -> bool:
    resolver = planner._vector_resolver
    if resolver is None:
        return False
    graph_cols = planner.graph.get(source_name)
    if not graph_cols:
        return True
    append_source = getattr(resolver, "append_planner_graph_source", None)
    if not callable(append_source):
        return False
    fill_rates = {
        (source_name, column_name): float(getattr(node, "fill_rate", 1.0) or 1.0)
        for column_name, node in graph_cols.items()
        if getattr(node, "is_numeric", True)
        and float(getattr(node, "fill_rate", 1.0) or 1.0) >= 0.02
    }
    handled = bool(
        append_source(
            source_name,
            graph_cols,
            fill_rates=fill_rates,
        )
    )
    if handled:
        logger.debug(
            "auto_planner_vector_resolver_appended",
            source=source_name,
            n_columns=sum(len(columns) for columns in planner.graph.values()),
            mode=resolver.__class__.__name__,
        )
    return handled


def _planner_graph_column_count(planner: Any) -> int:
    return sum(len(columns) for columns in planner.graph.values())


def _should_defer_vector_resolver_refresh(
    planner: Any,
    *,
    source_name: str,
) -> bool:
    if planner._vector_resolver is None:
        return False
    source_columns = len(planner.graph.get(source_name) or {})
    total_columns = _planner_graph_column_count(planner)
    if total_columns >= _LAZY_VECTOR_RESOLVER_TOTAL_COLUMN_THRESHOLD:
        return True
    return (
        total_columns >= (_LAZY_VECTOR_RESOLVER_TOTAL_COLUMN_THRESHOLD // 2)
        and source_columns >= _LAZY_VECTOR_RESOLVER_WIDE_SOURCE_COLUMN_THRESHOLD
    )


def _registry_join_cache_key(connection: dict[str, Any]) -> tuple[str, str] | None:
    src_a = str(connection.get("source_a_name") or "")
    src_b = str(connection.get("source_b_name") or "")
    if not src_a or not src_b:
        return None
    return (min(src_a, src_b), max(src_a, src_b))


def _registry_join_cache_entry(connection: dict[str, Any]) -> dict[str, Any] | None:
    cache_key = _registry_join_cache_key(connection)
    if cache_key is None:
        return None
    return {
        "field_a": connection["col_a"],
        "source_a": str(connection["source_a_name"]),
        "field_b": connection["col_b"],
        "source_b": str(connection["source_b_name"]),
        "confidence": connection.get("confidence", 0.70),
        "overlap": connection.get("overlap", 0.5),
        "cardinality": connection.get("cardinality", "many_to_many"),
    }


def _connection_matches_source(
    connection: dict[str, Any],
    *,
    source_id: str,
    source_name: str,
) -> bool:
    return (
        connection.get("source_a") == source_id
        or connection.get("source_b") == source_id
        or connection.get("source_a_name") == source_name
        or connection.get("source_b_name") == source_name
    )


def _build_registry_join_cache(
    connections: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    join_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for connection in connections:
        cache_key = _registry_join_cache_key(connection)
        cache_entry = _registry_join_cache_entry(connection)
        if cache_key is None or cache_entry is None:
            continue
        join_cache.setdefault(cache_key, []).append(cache_entry)
    return join_cache


def _refresh_registry_join_cache_for_source(
    planner: Any,
    *,
    source_id: str,
    source_name: str,
    new_connections: list[dict[str, Any]],
) -> None:
    retained_connections: list[dict[str, Any]] = []
    affected_pairs: set[tuple[str, str]] = set()

    for connection in planner._connections:
        if _connection_matches_source(
            connection,
            source_id=source_id,
            source_name=source_name,
        ):
            cache_key = _registry_join_cache_key(connection)
            if cache_key is not None:
                affected_pairs.add(cache_key)
            continue
        retained_connections.append(connection)

    for connection in new_connections:
        cache_key = _registry_join_cache_key(connection)
        if cache_key is not None:
            affected_pairs.add(cache_key)

    if new_connections:
        retained_connections.extend(new_connections)
    planner._connections = retained_connections

    if not planner._join_cache:
        return

    stale_cache_keys = {cache_key for cache_key in planner._join_cache if source_name in cache_key}
    stale_cache_keys.update(affected_pairs)
    for cache_key in stale_cache_keys:
        planner._join_cache.pop(cache_key, None)

    for connection in new_connections:
        cache_key = _registry_join_cache_key(connection)
        cache_entry = _registry_join_cache_entry(connection)
        if cache_key is None or cache_entry is None:
            continue
        planner._join_cache.setdefault(cache_key, []).append(cache_entry)


def refresh_registry_source(
    planner: Any,
    *,
    org_id: str,
    source_id: str,
    source_name: str,
    schema_meta: dict[str, Any],
    source_schema_revision: str,
    parquet_path: Path | None,
    new_connections: list[dict[str, Any]],
    registry_source_artifacts_from_meta_fn: Any,
) -> None:
    had_graph_source = source_name in planner.graph
    artifacts = registry_source_artifacts_from_meta_fn(
        org_id=org_id,
        source_id=source_id,
        schema_revision=source_schema_revision,
        meta=schema_meta,
    )

    if artifacts.nodes:
        planner.graph[source_name] = artifacts.nodes
    planner.profiles[source_name] = artifacts.profile
    if artifacts.query_hints:
        planner._query_hints_by_src[source_name] = artifacts.query_hints
    else:
        planner._query_hints_by_src.pop(source_name, None)

    planner.tables.pop(source_name, None)
    planner._mojo_profiles.pop(source_name, None)
    planner._relations.pop(source_name, None)
    if parquet_path is not None:
        planner._parquet_paths[source_name] = parquet_path
    else:
        planner._parquet_paths.pop(source_name, None)

    planner._plan_cache.clear()
    planner._metric_resolution_cache.clear()
    planner._dimension_resolution_cache.clear()
    planner._join_candidate_columns.clear()
    planner._join_evidence_cache.clear()
    planner._group_join_evidence_cache.clear()

    _refresh_registry_join_cache_for_source(
        planner,
        source_id=source_id,
        source_name=source_name,
        new_connections=new_connections,
    )

    planner._adaptive_source_context.pop(source_name, None)
    if had_graph_source:
        planner._build_vector_resolver()
        return
    if _should_defer_vector_resolver_refresh(planner, source_name=source_name):
        planner._vector_resolver_dirty = True
        logger.debug(
            "auto_planner_vector_resolver_deferred",
            source=source_name,
            n_columns=_planner_graph_column_count(planner),
        )
        return
    if not planner._append_vector_resolver_source(source_name):
        planner._build_vector_resolver()


def mojo_profile_source(planner: Any, args: tuple[Any, Any]) -> tuple[str, dict[str, Any]]:
    name, profile = args
    result = planner._call_mojo(
        {
            "engine_type": "column_profile",
            "columns": _build_mojo_column_profile_columns(
                profile,
                value_limit=30,
                string_limit=20,
            ),
        }
    )
    return name, (result or {}).get("profiles", {})


def mojo_relations_source(planner: Any, args: tuple[Any, Any]) -> tuple[str, list[Any]]:
    name, profile = args
    numeric = {
        field_name: info
        for field_name, info in profile.items()
        if info.get("is_numeric") and info.get("numeric")
    }
    if len(numeric) < 3:
        return name, []
    sample_count = min(min(len(info["numeric"]) for info in numeric.values()), 500)
    result = planner._call_mojo(
        {
            "engine_type": "relation_detect",
            "source": name,
            "min_confidence": 0.70,
            "columns": {
                column_name: info["numeric"][:sample_count] for column_name, info in numeric.items()
            },
        }
    )
    return name, (result or {}).get("relationships", [])
