from __future__ import annotations

from typing import Any

import pandas as pd

DEFAULT_JOIN_VALUE_CANDIDATE_LIMIT = 20
FAST_JOIN_VALUE_CANDIDATE_LIMIT = 8
WIDE_LARGE_JOIN_VALUE_CANDIDATE_LIMIT = 6
DEFAULT_JOIN_CANDIDATE_MIN_SCORE = 4.5
REDUCED_MEDIUM_JOIN_CANDIDATE_MIN_SCORE = 20.0
REDUCED_WIDE_MEDIUM_JOIN_CANDIDATE_MIN_SCORE = 30.0
REDUCED_WIDE_LARGE_SPARSE_JOIN_CANDIDATE_MIN_SCORE = 25.0
REDUCED_ULTRA_WIDE_CROWDED_JOIN_CANDIDATE_MIN_SCORE = 30.0
REDUCED_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE = 20.0
REDUCED_VERY_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE = 20.0
REDUCED_VERY_WIDE_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE = 30.0
LOW_ROW_JOIN_CANDIDATE_MIN_SCORE = 6.0
VERY_LOW_ROW_JOIN_CANDIDATE_MIN_SCORE = 8.0
SMALL_ORG_SINGLE_JOIN_PAIR_COST_BUDGET = 5_000_000
SMALL_ORG_TOTAL_JOIN_PAIR_COST_BUDGET = 12_000_000


def estimated_join_pair_cost(
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


def should_use_scored_join_scan(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
    build_join_blocks_fn: Any,
    existing_sources: list[dict[str, Any]] | None = None,
) -> bool:
    if existing_total > 24:
        return True

    join_block_count = len(build_join_blocks_fn(schema_meta))
    pair_costs = [
        estimated_join_pair_cost(
            row_count=row_count,
            join_block_count=join_block_count,
            entry=entry,
        )
        for entry in (existing_sources or [])
        if entry.get("row_count")
    ]
    if pair_costs and (
        max(pair_costs) >= SMALL_ORG_SINGLE_JOIN_PAIR_COST_BUDGET
        or sum(pair_costs) >= SMALL_ORG_TOTAL_JOIN_PAIR_COST_BUDGET
    ):
        return True
    if existing_total >= 12 and join_block_count >= 4 and row_count >= 3_000:
        return True
    if existing_total < 4:
        return False

    column_count = len(schema_meta.get("columns") or [])
    estimated_cells = row_count * max(column_count, 1)
    return row_count >= 5_000 or column_count >= 48 or estimated_cells >= 250_000


def join_candidate_limit(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
) -> int:
    column_count = len(schema_meta.get("columns") or [])
    estimated_cells = row_count * max(column_count, 1)
    if existing_total >= 36 and row_count >= 30_000 and column_count >= 64:
        return 2
    if existing_total >= 36 and row_count >= 30_000:
        return 4
    if existing_total >= 32 and (
        column_count >= 2_048 or (column_count >= 1_024 and row_count >= 10_000)
    ):
        return 4
    if existing_total >= 4 and row_count >= 5_000 and column_count >= 192:
        return 4
    if existing_total >= 48 and row_count >= 10_000:
        return 4
    if existing_total >= 24 and column_count >= 1_024:
        return 6
    if (
        existing_total >= 48
        and row_count >= 30_000
        and (column_count >= 64 or estimated_cells >= 2_000_000)
    ):
        return 4
    if existing_total >= 8:
        if row_count <= 256:
            return 4 if existing_total >= 24 else 6
        if existing_total >= 48 and row_count <= 2_000:
            return 4
        if row_count <= 2_000:
            return 8
    if existing_total >= 24 and row_count >= 8_000 and column_count >= 96:
        return 4
    if existing_total >= 24 and row_count >= 8_000 and column_count >= 56:
        return 6
    if existing_total <= 4:
        return 24
    if row_count >= 50_000 or estimated_cells >= 1_500_000:
        return 6
    if row_count >= 30_000 or column_count >= 96 or estimated_cells >= 750_000:
        return 8
    if existing_total >= 24 and row_count >= 10_000:
        return 8
    if row_count >= 10_000 or column_count >= 48 or estimated_cells >= 300_000:
        return 12
    if existing_total >= 24:
        return 16
    return 24


def join_candidate_min_score(
    *,
    row_count: int,
    schema_meta: dict[str, Any],
    existing_total: int,
    build_join_blocks_fn: Any,
) -> float:
    join_block_count = len(build_join_blocks_fn(schema_meta))
    column_count = len(schema_meta.get("columns") or [])
    estimated_cells = row_count * max(column_count, 1)
    if existing_total >= 8 and row_count <= 256:
        return VERY_LOW_ROW_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 8 and row_count <= 2_000:
        return LOW_ROW_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 36 and row_count >= 30_000 and column_count >= 64:
        return REDUCED_VERY_WIDE_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 32 and (
        column_count >= 2_048 or (column_count >= 1_024 and row_count >= 10_000)
    ):
        return REDUCED_ULTRA_WIDE_CROWDED_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 4 and row_count >= 5_000 and column_count >= 192:
        return REDUCED_VERY_WIDE_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 24 and column_count >= 1_024:
        return REDUCED_WIDE_LARGE_SPARSE_JOIN_CANDIDATE_MIN_SCORE
    if (
        existing_total >= 48
        and row_count >= 30_000
        and (column_count >= 64 or estimated_cells >= 2_000_000)
    ):
        return REDUCED_VERY_WIDE_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 36 and row_count >= 30_000:
        return REDUCED_VERY_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 24 and row_count >= 8_000 and column_count >= 96:
        return REDUCED_WIDE_MEDIUM_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 12 and 10_000 <= row_count < 30_000 and join_block_count >= 6:
        return REDUCED_WIDE_MEDIUM_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 24 and row_count >= 8_000 and column_count >= 56:
        return REDUCED_WIDE_LARGE_SPARSE_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 24 and 10_000 <= row_count < 30_000:
        return REDUCED_LARGE_CROWDED_JOIN_CANDIDATE_MIN_SCORE
    if existing_total >= 12 and 3_000 <= row_count < 30_000 and 3 <= join_block_count <= 4:
        return REDUCED_MEDIUM_JOIN_CANDIDATE_MIN_SCORE
    return DEFAULT_JOIN_CANDIDATE_MIN_SCORE


def join_value_candidate_limit(
    *,
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    fast_connections: list[dict[str, Any]],
) -> int:
    if fast_connections:
        return FAST_JOIN_VALUE_CANDIDATE_LIMIT
    max_rows = max(len(left_df), len(right_df))
    max_columns = max(len(left_df.columns), len(right_df.columns))
    if max_rows >= 8_000 and max_columns >= 56:
        return WIDE_LARGE_JOIN_VALUE_CANDIDATE_LIMIT
    return DEFAULT_JOIN_VALUE_CANDIDATE_LIMIT
