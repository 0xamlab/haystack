"""AR-OPT-2 slim-manifest reader + in-process hydration cache.

v1 snapshot manifests inline per-file ``symbols``/``dependencies``/``symbol_references``
in ``files[]``. v2 manifests drop those arrays (slim JSON, ~10-50x smaller) and rely on
the Parquet artifacts the snapshot workflow already writes. ``hydrate_snapshot_manifest``
repopulates the inline arrays from Parquet for v2 (no-op for v1) so the ~15 downstream
graph/decision consumers read an IDENTICAL dict shape regardless of manifest_version.

Parity is exact because hydrated dicts are projected to the precise v1 inline key sets —
notably the inline ``_Symbol`` has NO ``file_path``, so resolving a reference target via a
symbol's ``file_path`` stays a no-op in v2 exactly as it was in v1.

The grouped hydration index is memoized in a small bounded LRU keyed by the artifacts'
content hashes (content-addressed -> never stale), so a warm second load of the same
snapshot skips the Parquet read + grouping entirely (the AR-OPT-2 cache win). A cold read
is timed into the ``parquet_read_ms`` telemetry span.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from apps.api_server.services import repository_intelligence_telemetry as telemetry
from apps.api_server.services.runtime_internal_contracts import (
    DependencyGraphRecord,
    SymbolGraphRecord,
    SymbolReferenceRecord,
    table_from_parquet_bytes_tolerant,
    validate_table_schema,
)

# Exact v1 inline key sets. Hydrated dicts MUST match these so v2 == v1 behavior.
# Source of truth: _Symbol / _Dependency dataclasses and the writer's inline
# symbol_references dict in repository_intelligence_snapshot_workflow.py.
_SYMBOL_KEYS = (
    "symbol_id",
    "symbol_name",
    "symbol_kind",
    "start_line",
    "end_line",
    "parent_symbol_id",
    "signature",
)
_DEPENDENCY_KEYS = (
    "dependency_edge_id",
    "source_file",
    "target_file",
    "target_symbol",
    "dependency_type",
)
_REFERENCE_KEYS = (
    "source_symbol_id",
    "target_symbol_id",
    "target_file",
    "reference_type",
)

_HYDRATION_CACHE_MAXSIZE = 6
# snapshot content-hash key -> {"symbols"|"dependencies"|"symbol_references": {path: [dict]}}
_hydration_cache: "OrderedDict[tuple[str, ...], dict[str, dict[str, list[dict[str, Any]]]]]" = (
    OrderedDict()
)


def manifest_version(manifest: dict[str, Any]) -> int:
    return int(manifest.get("manifest_version", 1) or 1)


def _read_grouped(
    storage_path: str,
    record_type: type,
    *,
    group_key: str,
    project_keys: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    table = table_from_parquet_bytes_tolerant(Path(storage_path).read_bytes(), record_type)
    validate_table_schema(table, record_type)
    # Project to only the columns we keep BEFORE materializing to Python — the
    # records carry 8–12 columns but hydration keeps 4–8, so to_pylist() was
    # converting unused columns (repository_id/snapshot_id/created_at datetime/…)
    # to Python objects for every row, then discarding them. select() is a
    # zero-copy column projection; dedupe in case the group key is also a project
    # key (dependency source_file).
    wanted = list(dict.fromkeys((group_key, *project_keys)))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in table.select(wanted).to_pylist():
        grouped.setdefault(str(row[group_key]), []).append(
            {key: row.get(key) for key in project_keys}
        )
    return grouped


def _cache_key(manifest: dict[str, Any]) -> tuple[str, ...]:
    def content_hash(artifact_name: str) -> str:
        artifact = manifest.get(artifact_name) or {}
        return str(artifact.get("content_hash", ""))

    return (
        str(manifest.get("snapshot_id", "")),
        content_hash("symbol_graph_artifact"),
        content_hash("dependency_graph_artifact"),
        content_hash("symbol_reference_artifact"),
    )


def _hydration_index(manifest: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    key = _cache_key(manifest)
    cached = _hydration_cache.get(key)
    if cached is not None:
        _hydration_cache.move_to_end(key)
        return cached
    with telemetry.span("parquet_read_ms"):
        index = {
            "symbols": _read_grouped(
                manifest["symbol_graph_artifact"]["storage_path"],
                SymbolGraphRecord,
                group_key="file_path",
                project_keys=_SYMBOL_KEYS,
            ),
            "dependencies": _read_grouped(
                manifest["dependency_graph_artifact"]["storage_path"],
                DependencyGraphRecord,
                group_key="source_file",
                project_keys=_DEPENDENCY_KEYS,
            ),
            "symbol_references": _read_grouped(
                manifest["symbol_reference_artifact"]["storage_path"],
                SymbolReferenceRecord,
                group_key="source_file",
                project_keys=_REFERENCE_KEYS,
            ),
        }
    _hydration_cache[key] = index
    _hydration_cache.move_to_end(key)
    while len(_hydration_cache) > _HYDRATION_CACHE_MAXSIZE:
        _hydration_cache.popitem(last=False)
    return index


def hydrate_snapshot_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Repopulate files[].symbols/dependencies/symbol_references for v2 manifests.

    v1 manifests (inline arrays present) are returned unchanged. Idempotent: a manifest
    whose files already carry the arrays is left as-is. Mutates ``manifest`` in place and
    returns it (the loader hands out a fresh dict per call, so no shared state is touched).
    """
    if manifest_version(manifest) < 2:
        return manifest
    files = manifest.get("files") or []
    if not files or "symbols" in files[0]:
        return manifest
    index = _hydration_index(manifest)
    symbols = index["symbols"]
    dependencies = index["dependencies"]
    references = index["symbol_references"]
    for file_entry in files:
        file_path = str(file_entry.get("file_path", ""))
        file_entry["symbols"] = symbols.get(file_path, [])
        file_entry["dependencies"] = dependencies.get(file_path, [])
        file_entry["symbol_references"] = references.get(file_path, [])
    return manifest


def clear_hydration_cache() -> None:
    """Test/maintenance hook to drop the in-process hydration LRU."""
    _hydration_cache.clear()
