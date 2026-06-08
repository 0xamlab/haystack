from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


def find_exact_dataset_column(
    *,
    schema_meta: dict[str, Any],
    normalized_hint: str,
    normalize_hint_text: Callable[[str | None], str],
) -> dict[str, Any] | None:
    if not normalized_hint:
        return None

    matches: list[dict[str, Any]] = [
        column
        for column in (schema_meta.get("columns") or [])
        if normalize_hint_text(str(column.get("name", ""))) == normalized_hint
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def dataset_exact_column_lookup(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    schema_meta: dict[str, Any],
    dataset_exact_column_cache_get: Callable[
        [tuple[str, str, str]], dict[str, dict[str, Any] | None] | None
    ],
    dataset_exact_column_cache_put: Callable[
        [tuple[str, str, str], dict[str, dict[str, Any] | None]],
        dict[str, dict[str, Any] | None],
    ],
    normalize_hint_text: Callable[[str | None], str],
) -> dict[str, dict[str, Any] | None]:
    cache_key = (org_id, dataset_id, schema_revision)
    cached = dataset_exact_column_cache_get(cache_key)
    if cached is not None:
        return cached

    lookup: dict[str, dict[str, Any] | None] = {}
    for column in schema_meta.get("columns") or []:
        normalized_name = normalize_hint_text(str(column.get("name", "")))
        if not normalized_name:
            continue
        existing = lookup.get(normalized_name)
        if existing is None and normalized_name in lookup:
            continue
        if existing is None and normalized_name not in lookup:
            lookup[normalized_name] = column
        else:
            lookup[normalized_name] = None
    return dataset_exact_column_cache_put(cache_key, lookup)


def find_exact_dataset_column_cached(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    schema_meta: dict[str, Any],
    normalized_hint: str,
    dataset_exact_column_lookup_fn: Callable[..., dict[str, dict[str, Any] | None]],
) -> dict[str, Any] | None:
    if not normalized_hint:
        return None
    lookup = dataset_exact_column_lookup_fn(
        org_id=org_id,
        dataset_id=dataset_id,
        schema_revision=schema_revision,
        schema_meta=schema_meta,
    )
    return lookup.get(normalized_hint)


async def get_resolve_dataset_meta(
    *,
    org_id: str,
    dataset_id: str,
    schema_revision: str,
    cache_lock: Any,
    source_cache: dict[str, Any],
    graph_nodes_from_cached_meta: Callable[..., dict[str, Any]],
    get_source_meta_fn: Callable[[str, str], dict[str, Any] | None],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    async with cache_lock:
        cached = source_cache.get(dataset_id)
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
                graph_nodes = graph_nodes_from_cached_meta(
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

    schema_meta = get_source_meta_fn(org_id, dataset_id)
    if not isinstance(schema_meta, dict):
        return None, None
    return (
        schema_meta,
        graph_nodes_from_cached_meta(
            org_id=org_id,
            dataset_id=dataset_id,
            schema_revision=schema_revision,
            schema_meta=schema_meta,
        ),
    )


__all__ = [
    "dataset_exact_column_lookup",
    "find_exact_dataset_column",
    "find_exact_dataset_column_cached",
    "get_resolve_dataset_meta",
]
