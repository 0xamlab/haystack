from __future__ import annotations

import io
import math
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

_JOIN_PROJECTION_CACHE_MAX = 128
_JOIN_PROJECTION_CACHE: dict[tuple[str, str, str, tuple[str, ...]], pd.DataFrame] = {}
_JOIN_PROJECTION_CACHE_LOCK = threading.Lock()
_JOIN_VALUE_CANDIDATE_CACHE_MAX = 128
_JOIN_VALUE_CANDIDATE_CACHE: dict[
    tuple[str, str, str, tuple[str, ...]],
    dict[str, dict[str, Any]],
] = {}
_JOIN_VALUE_CANDIDATE_CACHE_LOCK = threading.Lock()
_JOIN_NAME_STATS_CACHE_MAX = 128
_JOIN_NAME_STATS_CACHE: dict[
    tuple[str, str, str, tuple[str, ...]],
    dict[str, dict[str, Any]],
] = {}
_JOIN_NAME_STATS_CACHE_LOCK = threading.Lock()
_JOIN_PROJECTION_ROW_GROUP_SAMPLE_CAP = 128
_JOIN_PROJECTION_BATCH_SIZE = 65_536
_LOW_RATIO_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_COUNT = 32
_LOW_RATIO_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY = 1.5
_LOW_RATIO_KEYLIKE_RELAXED_MIN_UNIQUE_COUNT = 128
_LOW_RATIO_KEYLIKE_RELAXED_MIN_JOINABILITY = 1.30
_MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_COUNT = 8
_MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT = 32
_MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY = 1.40
_MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE = 0.75
_CONSTANT_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT = 1
_CONSTANT_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY = 1.35
_CONSTANT_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE = 0.5
_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT = 8
_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_RATIO = 0.95
_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY = 1.10
_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE = 0.95
_SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT = 8
_SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_COUNT = 2
_SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY = 1.20
_SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE = 0.05

DeepJoinProjectionColumnsFn = Callable[..., list[str]]
LoadJoinProjectionFn = Callable[..., pd.DataFrame]
BuildJoinValueCandidatesFn = Callable[..., dict[str, dict[str, Any]]]
BuildJoinNameStatsFn = Callable[[pd.DataFrame], dict[str, dict[str, Any]]]
SourceSchemaRevisionFn = Callable[[str, str], str]


def _normalize_join_value(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    lowered = text.lower()
    if not text or lowered in {"none", "null", "nan", "n/a", "na", "?"}:
        return ""
    text = re.sub(r"\s+", " ", text)
    if re.fullmatch(r"[-+]?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _join_projection_signature(
    join_blocks: list[dict[str, Any]] | None,
    *,
    max_rows: int | None,
    deep_join_projection_columns_fn: DeepJoinProjectionColumnsFn,
) -> tuple[str, ...]:
    projected = deep_join_projection_columns_fn(join_blocks)
    signature = tuple(projected) if projected else ("*",)
    return signature + (f"rows:{max_rows or '*'}",)


def _join_value_candidate_signature(
    join_blocks: list[dict[str, Any]] | None,
    *,
    limit: int,
    max_rows: int | None,
    deep_join_projection_columns_fn: DeepJoinProjectionColumnsFn,
) -> tuple[str, ...]:
    return _join_projection_signature(
        join_blocks,
        max_rows=max_rows,
        deep_join_projection_columns_fn=deep_join_projection_columns_fn,
    ) + (f"limit:{limit}",)


def load_join_projection(
    parquet_bytes: bytes | None,
    join_blocks: list[dict[str, Any]] | None,
    *,
    parquet_path: Path | None = None,
    max_rows: int | None = None,
    deep_join_projection_columns_fn: DeepJoinProjectionColumnsFn,
) -> pd.DataFrame:
    initialize_pyarrow_parquet_runtime()
    if parquet_path is not None:
        parquet_file = pq.ParquetFile(str(parquet_path))
    elif parquet_bytes is not None:
        parquet_file = pq.ParquetFile(io.BytesIO(parquet_bytes))
    else:
        raise ValueError("join projection requires parquet bytes or parquet path")
    projected = deep_join_projection_columns_fn(join_blocks)
    if projected:
        available = set(parquet_file.schema.names)
        selected = [name for name in projected if name in available]
    else:
        selected = []
    if max_rows is None:
        table = parquet_file.read(columns=selected or None)
    else:
        import pyarrow as pa

        remaining = max(int(max_rows), 0)
        if remaining <= 0:
            table = pa.table({})
        else:
            total_rows = int(parquet_file.metadata.num_rows or 0)
            row_group_count = int(parquet_file.num_row_groups or 0)
            if total_rows > remaining and row_group_count > 1:

                def _evenly_spaced_indexes(total_count: int, sample_count: int) -> list[int]:
                    if sample_count >= total_count:
                        return list(range(total_count))
                    if sample_count <= 1:
                        return [0]
                    return [
                        min(
                            total_count - 1,
                            (position * (total_count - 1)) // (sample_count - 1),
                        )
                        for position in range(sample_count)
                    ]

                sampled_group_count = min(
                    row_group_count,
                    remaining,
                    _JOIN_PROJECTION_ROW_GROUP_SAMPLE_CAP,
                )
                sampled_indexes = _evenly_spaced_indexes(
                    row_group_count,
                    sampled_group_count,
                )
                per_group_limit = max(1, math.ceil(remaining / len(sampled_indexes)))
                sampled_tables: list[pa.Table] = []
                for row_group_index in sampled_indexes:
                    if remaining <= 0:
                        break
                    row_group_table = parquet_file.read_row_group(
                        row_group_index,
                        columns=selected or None,
                    )
                    take = min(int(row_group_table.num_rows), per_group_limit, remaining)
                    if take <= 0:
                        continue
                    sampled_tables.append(row_group_table.slice(0, take))
                    remaining -= take
                if not sampled_tables:
                    table = pa.table({})
                elif len(sampled_tables) == 1:
                    table = sampled_tables[0]
                else:
                    table = pa.concat_tables(sampled_tables, promote_options="permissive")
            elif total_rows > remaining:
                batch_size = _JOIN_PROJECTION_BATCH_SIZE
                estimated_batch_count = max(1, math.ceil(total_rows / batch_size))
                sampled_batch_count = min(
                    estimated_batch_count,
                    remaining,
                    _JOIN_PROJECTION_ROW_GROUP_SAMPLE_CAP,
                )
                if sampled_batch_count >= estimated_batch_count:
                    sampled_batch_indexes = set(range(estimated_batch_count))
                elif sampled_batch_count <= 1:
                    sampled_batch_indexes = {0}
                else:
                    sampled_batch_indexes = {
                        min(
                            estimated_batch_count - 1,
                            (position * (estimated_batch_count - 1)) // (sampled_batch_count - 1),
                        )
                        for position in range(sampled_batch_count)
                    }
                per_batch_limit = max(1, math.ceil(remaining / len(sampled_batch_indexes)))
                sampled_batches = []
                for batch_index, batch in enumerate(
                    parquet_file.iter_batches(
                        columns=selected or None,
                        batch_size=batch_size,
                    )
                ):
                    if batch_index not in sampled_batch_indexes:
                        continue
                    take = min(batch.num_rows, per_batch_limit, remaining)
                    if take <= 0:
                        continue
                    sampled_batches.append(batch.slice(0, take))
                    remaining -= take
                    if remaining <= 0:
                        break
                table = (
                    sampled_batches[0]
                    if len(sampled_batches) == 1
                    else pa.Table.from_batches(sampled_batches)
                    if sampled_batches
                    else pa.table({})
                )
            else:
                batches = []
                for batch in parquet_file.iter_batches(
                    columns=selected or None,
                    batch_size=min(max(remaining, 1), _JOIN_PROJECTION_BATCH_SIZE),
                ):
                    if remaining <= 0:
                        break
                    if batch.num_rows > remaining:
                        batch = batch.slice(0, remaining)
                    batches.append(batch)
                    remaining -= batch.num_rows
                    if remaining <= 0:
                        break
                table = batches[0] if len(batches) == 1 else None
                if table is None:
                    table = pa.Table.from_batches(batches) if batches else pa.table({})
    return table.to_pandas()


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


def load_join_projection_cached(
    *,
    org_id: str,
    source_id: str,
    parquet_bytes: bytes | None = None,
    parquet_path: Path | None = None,
    join_blocks: list[dict[str, Any]] | None,
    max_rows: int | None = None,
    load_join_projection_fn: LoadJoinProjectionFn,
    source_schema_revision_fn: SourceSchemaRevisionFn,
    deep_join_projection_columns_fn: DeepJoinProjectionColumnsFn,
) -> pd.DataFrame:
    cache_key = (
        org_id,
        source_id,
        source_schema_revision_fn(org_id, source_id),
        _join_projection_signature(
            join_blocks,
            max_rows=max_rows,
            deep_join_projection_columns_fn=deep_join_projection_columns_fn,
        ),
    )
    cached = _join_projection_cache_get(cache_key)
    if cached is not None:
        return cached
    return _join_projection_cache_put(
        cache_key,
        load_join_projection_fn(
            parquet_bytes,
            join_blocks,
            parquet_path=parquet_path,
            max_rows=max_rows,
        ),
    )


def _join_value_candidate_cache_get(
    cache_key: tuple[str, str, str, tuple[str, ...]],
) -> dict[str, dict[str, Any]] | None:
    with _JOIN_VALUE_CANDIDATE_CACHE_LOCK:
        cached = _JOIN_VALUE_CANDIDATE_CACHE.get(cache_key)
        if cached is None:
            return None
        _JOIN_VALUE_CANDIDATE_CACHE.pop(cache_key, None)
        _JOIN_VALUE_CANDIDATE_CACHE[cache_key] = cached
        return cached


def _join_value_candidate_cache_put(
    cache_key: tuple[str, str, str, tuple[str, ...]],
    candidates: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    with _JOIN_VALUE_CANDIDATE_CACHE_LOCK:
        _JOIN_VALUE_CANDIDATE_CACHE.pop(cache_key, None)
        while len(_JOIN_VALUE_CANDIDATE_CACHE) >= _JOIN_VALUE_CANDIDATE_CACHE_MAX:
            _JOIN_VALUE_CANDIDATE_CACHE.pop(next(iter(_JOIN_VALUE_CANDIDATE_CACHE)))
        _JOIN_VALUE_CANDIDATE_CACHE[cache_key] = candidates
    return candidates


def build_join_value_candidates(
    df: pd.DataFrame,
    join_blocks: list[dict[str, Any]] | None,
    *,
    limit: int = 20,
) -> dict[str, dict[str, Any]]:
    n_rows = len(df)
    joinability_by_name = {
        str(block.get("name") or ""): float(block.get("joinability") or 0.0)
        for block in (join_blocks or [])
        if block.get("name")
    }
    fill_rate_by_name = {
        str(block.get("name") or ""): float(block.get("fill_rate") or 0.0)
        for block in (join_blocks or [])
        if block.get("name")
    }
    key_like_by_name = {
        str(block.get("name") or ""): bool(block.get("key_like"))
        or str(block.get("role") or "") == "identifier"
        for block in (join_blocks or [])
        if block.get("name")
    }
    scored: list[tuple[float, float, str, list[str]]] = []
    for col in df.columns:
        normalized_values = [
            normalized
            for normalized in (_normalize_join_value(value) for value in df[col].dropna())
            if normalized
        ]
        unique_vals = list(dict.fromkeys(normalized_values))
        unique_count = len(unique_vals)
        unique_ratio = unique_count / max(n_rows, 1)
        joinability = joinability_by_name.get(col, 0.0)
        fill_rate = fill_rate_by_name.get(col, 0.0)
        constant_key_like = (
            key_like_by_name.get(col, False)
            and unique_count == _CONSTANT_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT
            and fill_rate >= _CONSTANT_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE
            and joinability >= _CONSTANT_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY
        )
        small_domain_key_like = (
            key_like_by_name.get(col, False)
            and unique_count <= _SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT
            and unique_ratio >= _SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_RATIO
            and fill_rate >= _SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE
            and joinability >= _SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY
        )
        sparse_small_domain_key_like = (
            key_like_by_name.get(col, False)
            and _SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_COUNT
            <= unique_count
            <= _SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT
            and fill_rate >= _SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE
            and joinability >= _SPARSE_SMALL_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY
        )
        if (
            unique_count <= 5
            and not constant_key_like
            and not small_domain_key_like
            and not sparse_small_domain_key_like
        ):
            continue
        substantial_sparse_dimension = (
            unique_count >= _LOW_RATIO_KEYLIKE_RELAXED_MIN_UNIQUE_COUNT
            and joinability >= _LOW_RATIO_KEYLIKE_RELAXED_MIN_JOINABILITY
        )
        moderate_domain_key_like = (
            key_like_by_name.get(col, False)
            and _MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_COUNT
            <= unique_count
            <= _MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MAX_UNIQUE_COUNT
            and fill_rate >= _MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_FILL_RATE
            and joinability >= _MODERATE_DOMAIN_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY
        )
        allow_low_ratio_key = key_like_by_name.get(col, False) and (
            constant_key_like
            or small_domain_key_like
            or sparse_small_domain_key_like
            or moderate_domain_key_like
            or (
                unique_count >= _LOW_RATIO_KEYLIKE_VALUE_CANDIDATE_MIN_UNIQUE_COUNT
                and joinability >= _LOW_RATIO_KEYLIKE_VALUE_CANDIDATE_MIN_JOINABILITY
            )
            or substantial_sparse_dimension
        )
        if unique_ratio <= 0.25 and not allow_low_ratio_key:
            continue
        scored.append(
            (
                joinability,
                unique_ratio,
                col,
                unique_vals[:1000],
            )
        )

    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return {
        col: {
            "values": values,
            "unique_ratio": round(unique_ratio, 4),
            "sample_size": n_rows,
        }
        for _joinability, unique_ratio, col, values in scored[:limit]
    }


def load_join_value_candidates_cached(
    *,
    org_id: str,
    source_id: str,
    join_blocks: list[dict[str, Any]] | None,
    limit: int,
    df: pd.DataFrame | None = None,
    parquet_bytes: bytes | None = None,
    parquet_path: Path | None = None,
    max_rows: int | None = None,
    load_join_projection_cached_fn: Callable[..., pd.DataFrame],
    build_join_value_candidates_fn: BuildJoinValueCandidatesFn,
    source_schema_revision_fn: SourceSchemaRevisionFn,
    deep_join_projection_columns_fn: DeepJoinProjectionColumnsFn,
) -> dict[str, dict[str, Any]]:
    cache_key = (
        org_id,
        source_id,
        source_schema_revision_fn(org_id, source_id),
        _join_value_candidate_signature(
            join_blocks,
            limit=limit,
            max_rows=max_rows,
            deep_join_projection_columns_fn=deep_join_projection_columns_fn,
        ),
    )
    cached = _join_value_candidate_cache_get(cache_key)
    if cached is not None:
        return cached
    projected_df = df
    if projected_df is None:
        projected_df = load_join_projection_cached_fn(
            org_id=org_id,
            source_id=source_id,
            parquet_bytes=parquet_bytes,
            parquet_path=parquet_path,
            join_blocks=join_blocks,
            max_rows=max_rows,
        )
    return _join_value_candidate_cache_put(
        cache_key,
        build_join_value_candidates_fn(projected_df, join_blocks, limit=limit),
    )


def _join_name_stats_cache_get(
    cache_key: tuple[str, str, str, tuple[str, ...]],
) -> dict[str, dict[str, Any]] | None:
    with _JOIN_NAME_STATS_CACHE_LOCK:
        cached = _JOIN_NAME_STATS_CACHE.get(cache_key)
        if cached is None:
            return None
        _JOIN_NAME_STATS_CACHE.pop(cache_key, None)
        _JOIN_NAME_STATS_CACHE[cache_key] = cached
        return cached


def _join_name_stats_cache_put(
    cache_key: tuple[str, str, str, tuple[str, ...]],
    stats: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    with _JOIN_NAME_STATS_CACHE_LOCK:
        _JOIN_NAME_STATS_CACHE.pop(cache_key, None)
        while len(_JOIN_NAME_STATS_CACHE) >= _JOIN_NAME_STATS_CACHE_MAX:
            _JOIN_NAME_STATS_CACHE.pop(next(iter(_JOIN_NAME_STATS_CACHE)))
        _JOIN_NAME_STATS_CACHE[cache_key] = stats
    return stats


def build_join_name_stats(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    row_count = len(df)
    stats: dict[str, dict[str, Any]] = {}
    for col in df.columns:
        normalized_values = [
            normalized
            for normalized in (_normalize_join_value(value) for value in df[col].dropna())
            if normalized
        ]
        non_null = pd.Series(normalized_values, dtype="string")
        unique_values = non_null.unique().tolist()
        values = set(unique_values)
        unique_count = len(values)
        non_null_count = len(non_null)
        all_unique = non_null_count > 0 and unique_count == non_null_count
        counts = {} if all_unique else non_null.value_counts().to_dict()
        stats[col] = {
            "counts": counts,
            "values": values,
            "unique_ratio": unique_count / max(row_count, 1),
            "all_unique": all_unique,
        }
    return stats


def load_join_name_stats_cached(
    *,
    org_id: str,
    source_id: str,
    join_blocks: list[dict[str, Any]] | None,
    df: pd.DataFrame | None = None,
    parquet_bytes: bytes | None = None,
    parquet_path: Path | None = None,
    max_rows: int | None = None,
    load_join_projection_cached_fn: Callable[..., pd.DataFrame],
    build_join_name_stats_fn: BuildJoinNameStatsFn,
    source_schema_revision_fn: SourceSchemaRevisionFn,
    deep_join_projection_columns_fn: DeepJoinProjectionColumnsFn,
) -> dict[str, dict[str, Any]]:
    cache_key = (
        org_id,
        source_id,
        source_schema_revision_fn(org_id, source_id),
        _join_projection_signature(
            join_blocks,
            max_rows=max_rows,
            deep_join_projection_columns_fn=deep_join_projection_columns_fn,
        ),
    )
    cached = _join_name_stats_cache_get(cache_key)
    if cached is not None:
        return cached
    projected_df = df
    if projected_df is None:
        projected_df = load_join_projection_cached_fn(
            org_id=org_id,
            source_id=source_id,
            parquet_bytes=parquet_bytes,
            parquet_path=parquet_path,
            join_blocks=join_blocks,
            max_rows=max_rows,
        )
    return _join_name_stats_cache_put(cache_key, build_join_name_stats_fn(projected_df))
