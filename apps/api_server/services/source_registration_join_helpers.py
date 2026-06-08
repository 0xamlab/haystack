from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from apps.api_server.services.source_join_cache import (
    load_join_name_stats_cached,
    load_join_projection,
    load_join_projection_cached,
    load_join_value_candidates_cached,
)
from apps.api_server.services.source_join_detection import detect_joins_between
from apps.api_server.services.source_join_scan_policy import (
    join_candidate_min_score as join_candidate_min_score_impl,
)
from apps.api_server.services.source_join_scan_policy import (
    should_use_scored_join_scan as should_use_scored_join_scan_impl,
)

_VERY_LARGE_JOIN_PROJECTION_ROW_THRESHOLD = 1_000_000
_VERY_LARGE_JOIN_PROJECTION_MAX_ROWS = 100_000


def should_use_scored_join_scan(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
    existing_sources: list[dict[str, Any]] | None = None,
    build_join_blocks_fn: Any,
) -> bool:
    return should_use_scored_join_scan_impl(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
        existing_sources=existing_sources,
        build_join_blocks_fn=build_join_blocks_fn,
    )


def join_candidate_min_score(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
    build_join_blocks_fn: Any,
) -> float:
    return join_candidate_min_score_impl(
        row_count=row_count,
        schema_meta=schema_meta,
        existing_total=existing_total,
        build_join_blocks_fn=build_join_blocks_fn,
    )


def load_join_projection_for_registration(
    parquet_bytes: bytes | None,
    join_blocks: list[dict[str, Any]] | None,
    *,
    parquet_path: Path | None = None,
    max_rows: int | None = None,
    deep_join_projection_columns_fn: Any,
) -> pd.DataFrame:
    return load_join_projection(
        parquet_bytes,
        join_blocks,
        parquet_path=parquet_path,
        max_rows=max_rows,
        deep_join_projection_columns_fn=deep_join_projection_columns_fn,
    )


def load_join_projection_cached_for_registration(
    *,
    org_id: str,
    source_id: str,
    parquet_bytes: bytes | None = None,
    parquet_path: Path | None = None,
    join_blocks: list[dict[str, Any]] | None,
    max_rows: int | None = None,
    load_join_projection_fn: Any,
    source_schema_revision_fn: Any,
    deep_join_projection_columns_fn: Any,
) -> pd.DataFrame:
    return load_join_projection_cached(
        org_id=org_id,
        source_id=source_id,
        parquet_bytes=parquet_bytes,
        parquet_path=parquet_path,
        join_blocks=join_blocks,
        max_rows=max_rows,
        load_join_projection_fn=load_join_projection_fn,
        source_schema_revision_fn=source_schema_revision_fn,
        deep_join_projection_columns_fn=deep_join_projection_columns_fn,
    )


def load_join_value_candidates_cached_for_registration(
    *,
    org_id: str,
    source_id: str,
    join_blocks: list[dict[str, Any]] | None,
    limit: int = 20,
    df: pd.DataFrame | None = None,
    parquet_bytes: bytes | None = None,
    parquet_path: Path | None = None,
    max_rows: int | None = None,
    load_join_projection_cached_fn: Any,
    build_join_value_candidates_fn: Any,
    source_schema_revision_fn: Any,
    deep_join_projection_columns_fn: Any,
) -> dict[str, dict[str, Any]]:
    return load_join_value_candidates_cached(
        org_id=org_id,
        source_id=source_id,
        join_blocks=join_blocks,
        limit=limit,
        df=df,
        parquet_bytes=parquet_bytes,
        parquet_path=parquet_path,
        max_rows=max_rows,
        load_join_projection_cached_fn=load_join_projection_cached_fn,
        build_join_value_candidates_fn=build_join_value_candidates_fn,
        source_schema_revision_fn=source_schema_revision_fn,
        deep_join_projection_columns_fn=deep_join_projection_columns_fn,
    )


def load_join_name_stats_cached_for_registration(
    *,
    org_id: str,
    source_id: str,
    join_blocks: list[dict[str, Any]] | None,
    df: pd.DataFrame | None = None,
    parquet_bytes: bytes | None = None,
    parquet_path: Path | None = None,
    max_rows: int | None = None,
    load_join_projection_cached_fn: Any,
    build_join_name_stats_fn: Any,
    source_schema_revision_fn: Any,
    deep_join_projection_columns_fn: Any,
) -> dict[str, dict[str, Any]]:
    return load_join_name_stats_cached(
        org_id=org_id,
        source_id=source_id,
        join_blocks=join_blocks,
        df=df,
        parquet_bytes=parquet_bytes,
        parquet_path=parquet_path,
        max_rows=max_rows,
        load_join_projection_cached_fn=load_join_projection_cached_fn,
        build_join_name_stats_fn=build_join_name_stats_fn,
        source_schema_revision_fn=source_schema_revision_fn,
        deep_join_projection_columns_fn=deep_join_projection_columns_fn,
    )


def join_projection_max_rows(*, row_count: int) -> int | None:
    if row_count >= _VERY_LARGE_JOIN_PROJECTION_ROW_THRESHOLD:
        return _VERY_LARGE_JOIN_PROJECTION_MAX_ROWS
    return None


async def detect_joins_between_for_registration(
    org_id: str,
    src_id: str,
    src_name: str,
    src_parquet: bytes | None,
    other_id: str,
    other_name: str,
    other_parquet: bytes | None,
    *,
    src_parquet_path: Path | None = None,
    other_parquet_path: Path | None = None,
    src_df: pd.DataFrame | None = None,
    other_df: pd.DataFrame | None = None,
    src_name_stats: dict[str, dict[str, Any]] | None = None,
    other_name_stats: dict[str, dict[str, Any]] | None = None,
    src_value_candidates: dict[str, dict[str, Any]] | None = None,
    other_value_candidates: dict[str, dict[str, Any]] | None = None,
    src_projection_max_rows: int | None = None,
    other_projection_max_rows: int | None = None,
    left_join_blocks: list[dict[str, Any]] | None = None,
    right_join_blocks: list[dict[str, Any]] | None = None,
    metadata_fast_join_candidates_fn: Any,
    load_join_projection_cached_fn: Any,
    load_join_name_stats_cached_fn: Any,
    load_join_value_candidates_cached_fn: Any,
    call_mojo_join_detect_fn: Any,
    logger: Any,
) -> list[dict[str, Any]]:
    return await detect_joins_between(
        org_id,
        src_id,
        src_name,
        src_parquet,
        other_id,
        other_name,
        other_parquet,
        src_parquet_path=src_parquet_path,
        other_parquet_path=other_parquet_path,
        src_df=src_df,
        other_df=other_df,
        src_name_stats=src_name_stats,
        other_name_stats=other_name_stats,
        src_value_candidates=src_value_candidates,
        other_value_candidates=other_value_candidates,
        src_projection_max_rows=src_projection_max_rows,
        other_projection_max_rows=other_projection_max_rows,
        left_join_blocks=left_join_blocks,
        right_join_blocks=right_join_blocks,
        metadata_fast_join_candidates_fn=metadata_fast_join_candidates_fn,
        load_join_projection_cached_fn=load_join_projection_cached_fn,
        load_join_name_stats_cached_fn=load_join_name_stats_cached_fn,
        load_join_value_candidates_cached_fn=load_join_value_candidates_cached_fn,
        call_mojo_join_detect_fn=call_mojo_join_detect_fn,
        logger=logger,
    )
