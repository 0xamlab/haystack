from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def list_sources(
    *,
    org_id: str,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
) -> list[dict[str, Any]]:
    directory = org_dir_fn(org_id)
    index = read_json_fn(directory / "index.json") or {}
    return list(index.values())


def get_source_entry(
    *,
    org_id: str,
    source_id: str,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    path_fingerprint_fn: Callable[[Path], tuple[int, int]],
    source_entry_cache: dict[tuple[str, str], tuple[tuple[Any, ...], dict[str, Any] | None]],
    source_entry_cache_key_fn: Callable[[str, str], tuple[str, str]],
) -> dict[str, Any] | None:
    directory = org_dir_fn(org_id)
    index_path = directory / "index.json"
    fingerprint = (path_fingerprint_fn(index_path),)
    cache_key = source_entry_cache_key_fn(org_id, source_id)
    cached = source_entry_cache.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]

    index = read_json_fn(index_path) or {}
    entry = index.get(source_id)
    normalized = entry if isinstance(entry, dict) else None
    source_entry_cache[cache_key] = (fingerprint, normalized)
    return normalized


def get_source_entry_by_name(
    *,
    org_id: str,
    source_name: str,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    path_fingerprint_fn: Callable[[Path], tuple[int, int]],
    source_entry_by_name_cache: dict[
        tuple[str, str],
        tuple[tuple[Any, ...], dict[str, Any] | None],
    ],
) -> dict[str, Any] | None:
    directory = org_dir_fn(org_id)
    index_path = directory / "index.json"
    fingerprint = (path_fingerprint_fn(index_path),)
    cache_key = (org_id, source_name)
    cached = source_entry_by_name_cache.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]

    index = read_json_fn(index_path) or {}
    match = next(
        (
            entry
            for entry in index.values()
            if isinstance(entry, dict) and str(entry.get("name") or "") == source_name
        ),
        None,
    )
    source_entry_by_name_cache[cache_key] = (fingerprint, match)
    return match


def update_source_entry(
    *,
    org_id: str,
    source_id: str,
    updates: dict[str, Any],
    touch_schema: bool,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    write_json_fn: Callable[[Path, Any], None],
    set_source_entry_cache_fn: Callable[[str, str, dict[str, Any] | None], None],
    touch_schema_stamp_fn: Callable[[Path], None],
    schema_revision_cache: dict[str, tuple[tuple[Any, ...], str]],
) -> dict[str, Any] | None:
    directory = org_dir_fn(org_id)
    index = read_json_fn(directory / "index.json") or {}
    entry = index.get(source_id)
    if not isinstance(entry, dict):
        return None
    if all(entry.get(key) == value for key, value in updates.items()):
        set_source_entry_cache_fn(org_id, source_id, entry)
        return entry
    entry.update(updates)
    index[source_id] = entry
    write_json_fn(directory / "index.json", index)
    if touch_schema:
        touch_schema_stamp_fn(directory)
    else:
        schema_revision_cache.pop(org_id, None)
    return entry


def candidate_join_sources(
    *,
    org_id: str,
    source_id: str,
    schema_meta: dict[str, Any],
    source_name: str | None,
    limit: int,
    exhaustive_threshold: int,
    min_score: float,
    list_sources_fn: Callable[[str], list[dict[str, Any]]],
    build_join_blocks_fn: Callable[[dict[str, Any]], list[dict[str, Any]]],
    score_candidate_source_fn: Callable[..., float],
) -> list[dict[str, Any]]:
    existing = [entry for entry in list_sources_fn(org_id) if entry.get("id") != source_id]
    if len(existing) <= exhaustive_threshold:
        return existing

    left_blocks = build_join_blocks_fn(schema_meta)
    if not left_blocks:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in existing:
        right_blocks = entry.get("join_blocks") or []
        if not right_blocks:
            continue
        score = score_candidate_source_fn(
            left_blocks,
            right_blocks,
            left_source_name=source_name,
            right_source_name=str(entry.get("name") or ""),
        )
        if score >= min_score:
            scored.append((score, entry))

    scored.sort(key=lambda item: (item[0], item[1].get("row_count", 0)), reverse=True)
    return [entry for _score, entry in scored[:limit]]


def get_source_meta(
    *,
    org_id: str,
    source_id: str,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    path_fingerprint_fn: Callable[[Path], tuple[int, int]],
    source_meta_cache: dict[tuple[str, str], tuple[tuple[Any, ...], dict[str, Any] | None]],
    source_meta_cache_key_fn: Callable[[str, str], tuple[str, str]],
) -> dict[str, Any] | None:
    directory = org_dir_fn(org_id)
    path = directory / f"{source_id}.meta.json"
    fingerprint = (path_fingerprint_fn(path),)
    cache_key = source_meta_cache_key_fn(org_id, source_id)
    cached = source_meta_cache.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]

    meta = read_json_fn(path)
    normalized = meta if isinstance(meta, dict) else None
    source_meta_cache[cache_key] = (fingerprint, normalized)
    return normalized


def update_source_meta(
    *,
    org_id: str,
    source_id: str,
    updates: dict[str, Any],
    touch_schema: bool,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    write_json_fn: Callable[[Path, Any], None],
    set_source_meta_cache_fn: Callable[[str, str, dict[str, Any] | None], None],
    set_source_entry_cache_fn: Callable[[str, str, dict[str, Any] | None], None],
    touch_schema_stamp_fn: Callable[[Path], None],
    source_schema_revision_fn: Callable[[str, str], str],
    schema_revision_cache: dict[str, tuple[tuple[Any, ...], str]],
) -> dict[str, Any] | None:
    directory = org_dir_fn(org_id)
    path = directory / f"{source_id}.meta.json"
    meta = read_json_fn(path)
    if not isinstance(meta, dict):
        return None
    if all(meta.get(key) == value for key, value in updates.items()):
        set_source_meta_cache_fn(org_id, source_id, meta)
        return meta

    meta.update(updates)
    write_json_fn(path, meta)
    if touch_schema:
        touch_schema_stamp_fn(directory)
    else:
        schema_revision_cache.pop(org_id, None)
    set_source_meta_cache_fn(org_id, source_id, meta)

    source_revision = source_schema_revision_fn(org_id, source_id)
    index = read_json_fn(directory / "index.json") or {}
    entry = index.get(source_id)
    if isinstance(entry, dict):
        entry["source_schema_revision"] = source_revision
        index[source_id] = entry
        write_json_fn(directory / "index.json", index)
        set_source_entry_cache_fn(org_id, source_id, entry)
    return meta


def get_source_parquet(
    *,
    org_id: str,
    source_id: str,
    org_dir_fn: Callable[[str], Path],
) -> bytes | None:
    path = org_dir_fn(org_id) / f"{source_id}.parquet"
    return path.read_bytes() if path.exists() else None


def get_source_parquet_path(
    *,
    org_id: str,
    source_id: str,
    org_dir_fn: Callable[[str], Path],
) -> Path | None:
    path = org_dir_fn(org_id) / f"{source_id}.parquet"
    return path if path.exists() else None


def get_connections(
    *,
    org_id: str,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
) -> list[dict[str, Any]]:
    directory = org_dir_fn(org_id)
    return read_json_fn(directory / "connections.json") or []


def schema_revision(
    *,
    org_id: str,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    path_fingerprint_fn: Callable[[Path], tuple[int, int]],
    schema_stamp_path_fn: Callable[[Path], Path],
    schema_stamp_value_fn: Callable[[Path], str],
    schema_revision_cache: dict[str, tuple[tuple[Any, ...], str]],
) -> str:
    directory = org_dir_fn(org_id)
    index = read_json_fn(directory / "index.json") or {}
    stamp_path = schema_stamp_path_fn(directory)
    fingerprint = (
        path_fingerprint_fn(directory / "index.json"),
        path_fingerprint_fn(directory / "connections.json"),
        path_fingerprint_fn(stamp_path),
    )
    cached = schema_revision_cache.get(org_id)
    if cached and cached[0] == fingerprint:
        return cached[1]
    stamp_value = schema_stamp_value_fn(directory)
    payload = {
        "schema_stamp_value": stamp_value,
        "source_ids": sorted(index),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    revision = hashlib.sha256(raw).hexdigest()[:24]
    schema_revision_cache[org_id] = (fingerprint, revision)
    return revision


def source_schema_revision(
    *,
    org_id: str,
    source_id: str,
    org_dir_fn: Callable[[str], Path],
    path_fingerprint_fn: Callable[[Path], tuple[int, int]],
    source_schema_revision_cache: dict[tuple[str, str], tuple[tuple[Any, ...], str]],
) -> str:
    directory = org_dir_fn(org_id)
    fingerprint = (
        path_fingerprint_fn(directory / f"{source_id}.meta.json"),
        path_fingerprint_fn(directory / f"{source_id}.parquet"),
    )
    cache_key = (org_id, source_id)
    cached = source_schema_revision_cache.get(cache_key)
    if cached and cached[0] == fingerprint:
        return cached[1]
    raw = json.dumps(
        {"meta": fingerprint[0], "parquet": fingerprint[1]},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    revision = hashlib.sha256(raw).hexdigest()[:24]
    source_schema_revision_cache[cache_key] = (fingerprint, revision)
    return revision


def register_source(
    *,
    org_id: str,
    source_id: str,
    name: str,
    parquet_bytes: bytes,
    schema_meta: dict[str, Any],
    entry_meta: dict[str, Any],
    org_dir_fn: Callable[[str], Path],
    write_json_fn: Callable[[Path, Any], None],
    read_json_fn: Callable[[Path], Any],
    set_source_meta_cache_fn: Callable[[str, str, dict[str, Any] | None], None],
    build_join_blocks_fn: Callable[[dict[str, Any]], list[dict[str, Any]]],
    source_schema_revision_fn: Callable[[str, str], str],
    set_source_entry_cache_fn: Callable[[str, str, dict[str, Any] | None], None],
    touch_schema_stamp_fn: Callable[[Path], None],
    logger: Any,
) -> dict[str, Any]:
    directory = org_dir_fn(org_id)
    (directory / f"{source_id}.parquet").write_bytes(parquet_bytes)

    write_json_fn(directory / f"{source_id}.meta.json", schema_meta)
    set_source_meta_cache_fn(org_id, source_id, schema_meta)

    index = read_json_fn(directory / "index.json") or {}
    join_blocks = build_join_blocks_fn(schema_meta)
    source_revision = source_schema_revision_fn(org_id, source_id)
    entry: dict[str, Any] = {
        "id": source_id,
        "name": name,
        "registered_at": datetime.now(UTC).isoformat(),
        "row_count": schema_meta.get("row_count", 0),
        "roles_summary": schema_meta.get("roles_summary", {}),
        "columns": len(schema_meta.get("columns", [])),
        "source_schema_revision": source_revision,
        "join_blocks": join_blocks,
    }
    for key, value in entry_meta.items():
        if value is not None:
            entry[key] = value
    index[source_id] = entry
    write_json_fn(directory / "index.json", index)
    set_source_entry_cache_fn(org_id, source_id, entry)
    touch_schema_stamp_fn(directory)

    logger.info("source_registered", org=org_id, source_id=source_id, name=name)
    return entry


def delete_source(
    *,
    org_id: str,
    source_id: str,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    write_json_fn: Callable[[Path, Any], None],
    get_connections_fn: Callable[[str], list[dict[str, Any]]],
    touch_schema_stamp_fn: Callable[[Path], None],
    clear_source_meta_cache_fn: Callable[[str, str], None],
    set_source_entry_cache_fn: Callable[[str, str, dict[str, Any] | None], None],
    logger: Any,
) -> bool:
    directory = org_dir_fn(org_id)
    existed = False
    for suffix in (".parquet", ".meta.json"):
        path = directory / f"{source_id}{suffix}"
        if path.exists():
            path.unlink()
            existed = True

    index = read_json_fn(directory / "index.json") or {}
    if source_id in index:
        del index[source_id]
        write_json_fn(directory / "index.json", index)
        existed = True

    connections = [
        connection
        for connection in get_connections_fn(org_id)
        if connection.get("source_a") != source_id and connection.get("source_b") != source_id
    ]
    write_json_fn(directory / "connections.json", connections)
    if existed:
        touch_schema_stamp_fn(directory)
        clear_source_meta_cache_fn(org_id, source_id)
        set_source_entry_cache_fn(org_id, source_id, None)
        logger.info("source_deleted", org=org_id, source_id=source_id)
    return existed


def upsert_connections(
    *,
    org_id: str,
    new_conns: list[dict[str, Any]],
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    write_json_fn: Callable[[Path, Any], None],
    touch_schema_stamp_fn: Callable[[Path], None],
) -> None:
    directory = org_dir_fn(org_id)
    existing = read_json_fn(directory / "connections.json") or []

    def _key(connection: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            connection["source_a"],
            connection["col_a"],
            connection["source_b"],
            connection["col_b"],
        )

    seen = {_key(connection) for connection in existing}
    merged = list(existing)
    for connection in new_conns:
        key = _key(connection)
        if key not in seen:
            merged.append(connection)
            seen.add(key)

    if len(merged) != len(existing):
        write_json_fn(directory / "connections.json", merged)
        touch_schema_stamp_fn(directory)


def get_connection_graph(
    *,
    org_id: str,
    get_connections_fn: Callable[[str], list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    connections = get_connections_fn(org_id)
    graph: dict[str, list[dict[str, Any]]] = {}
    for connection in connections:
        for src, other_src, col, other_col in [
            (
                connection["source_a"],
                connection["source_b"],
                connection["col_a"],
                connection["col_b"],
            ),
            (
                connection["source_b"],
                connection["source_a"],
                connection["col_b"],
                connection["col_a"],
            ),
        ]:
            graph.setdefault(src, []).append(
                {
                    "to_source": other_src,
                    "local_col": col,
                    "remote_col": other_col,
                    "confidence": connection.get("confidence", 0.0),
                    "cardinality": connection.get("cardinality", "?"),
                }
            )
    return graph


def load_all_into_cache(
    *,
    org_id: str,
    cache: dict[str, Any],
    cached_source_cls: type,
    org_dir_fn: Callable[[str], Path],
    read_json_fn: Callable[[Path], Any],
    set_source_meta_cache_fn: Callable[[str, str, dict[str, Any] | None], None],
    dict_to_node_fn: Callable[[dict[str, Any]], Any],
    logger: Any,
) -> int:
    import json as _json

    directory = org_dir_fn(org_id)
    index = read_json_fn(directory / "index.json") or {}
    loaded = 0

    for source_id, _entry in index.items():
        parquet_path = directory / f"{source_id}.parquet"
        meta_path = directory / f"{source_id}.meta.json"
        if not parquet_path.exists():
            continue
        try:
            parquet_bytes = parquet_path.read_bytes()
            schema_meta = read_json_fn(meta_path) or {}
            set_source_meta_cache_fn(org_id, source_id, schema_meta)

            graph_nodes: dict[str, Any] = {}
            corrected_cols: list[tuple[str, Any, Any]] = []
            for column in schema_meta.get("columns", []):
                node = dict_to_node_fn(column)
                graph_nodes[column["name"]] = node
                if column.get("role") != node.role:
                    corrected_cols.append((column["name"], column.get("role"), node.role))

            if corrected_cols:
                corrected_map = {name: role for name, _old_role, role in corrected_cols}
                schema_meta = {
                    **schema_meta,
                    "columns": [
                        {**column, "role": corrected_map[column["name"]]}
                        if column["name"] in corrected_map
                        else column
                        for column in schema_meta.get("columns", [])
                    ],
                }

            entry_obj = cached_source_cls(
                parquet_bytes=parquet_bytes,
                parquet_schema_meta=_json.dumps(schema_meta).encode(),
                profile={},
                mojo_profile={},
                relations=schema_meta.get("formulas", []),
                graph_nodes=graph_nodes,
                schema_meta=schema_meta,
                mojo_profiling_status=schema_meta.get("mojo_profiling_status") or {},
                content_keyed=True,
            )
            cache[source_id] = entry_obj
            loaded += 1
        except Exception as exc:
            logger.warning(
                "source_cache_load_failed",
                source_id=source_id,
                error=str(exc),
            )

    return loaded
