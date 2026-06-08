from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pandas as pd

from apps.api_server.services.source_join_policy import (
    _bounded_fast_join_connections,
    _build_shared_value_fast_connection,
    _dimension_family_columns,
    _has_decisive_fast_join,
    _infer_shared_column_cardinality_from_stats,
    _is_low_cardinality_dimension_join,
    _join_key_names_are_compatible,
    _normalized_join_key_name,
    _should_accept_fast_join_connections,
    _should_collect_fast_join_name_stats,
)
from apps.api_server.services.source_join_scan_policy import (
    join_value_candidate_limit as _join_value_candidate_limit,
)

MetadataFastJoinCandidatesFn = Callable[..., list[dict[str, Any]]]
LoadJoinProjectionCachedFn = Callable[..., pd.DataFrame]
LoadJoinNameStatsCachedFn = Callable[..., dict[str, dict[str, Any]]]
LoadJoinValueCandidatesCachedFn = Callable[..., dict[str, dict[str, Any]]]
CallMojoJoinDetectFn = Callable[
    [str, str, dict[str, dict[str, Any]], float],
    Awaitable[dict[str, Any] | None],
]

_GENERIC_SOURCE_ALIGNED_KEY_TOKENS = frozenset(
    {"code", "id", "identifier", "key", "number", "ref", "type", "uuid"}
)
_SOURCE_ALIGNED_FK_MIN_REFERENCED_UNIQUE_RATIO = 0.98
_SOURCE_ALIGNED_FK_MIN_FILL_RATE = 0.25
_SOURCE_ALIGNED_FK_SMALL_DIMENSION_MAX_UNIQUE_COUNT = 8
_SOURCE_ALIGNED_FK_SMALL_DIMENSION_MIN_REFERENCING_FILL_RATE = 0.05
_SOURCE_ALIGNED_FK_SMALL_DIMENSION_MIN_OVERLAP_COUNT = 2
_SOURCE_ALIGNED_FK_SMALL_DIMENSION_MIN_OVERLAP_RATIO = 0.67
_SOURCE_ALIGNED_FK_ZERO_OVERLAP_MIN_SAMPLE_SIZE = 50_000
_SOURCE_ALIGNED_FK_ZERO_OVERLAP_MIN_UNIQUE_COUNT = 128


def _canonical_source_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", str(text or "").lower()))
    expanded = set(tokens)
    for token in tokens:
        if len(token) > 4 and token.endswith("ies"):
            expanded.add(f"{token[:-3]}y")
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            expanded.add(token[:-1])
    return expanded


def _source_aligned_foreign_key_flags(
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
) -> tuple[bool, bool, bool]:
    left_tokens = set(re.findall(r"[a-z0-9]+", str(left_key or "").lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", str(right_key or "").lower()))
    left_source_tokens = _canonical_source_tokens(left_source)
    right_source_tokens = _canonical_source_tokens(right_source)
    bare_left_id = bool(left_tokens) and left_tokens <= _GENERIC_SOURCE_ALIGNED_KEY_TOKENS
    bare_right_id = bool(right_tokens) and right_tokens <= _GENERIC_SOURCE_ALIGNED_KEY_TOKENS
    left_to_right_overlap = len(left_tokens & right_source_tokens) / max(
        len(right_source_tokens),
        1,
    )
    right_to_left_overlap = len(right_tokens & left_source_tokens) / max(
        len(left_source_tokens),
        1,
    )
    foreign_key_to_right = bare_right_id and left_to_right_overlap >= 0.5
    foreign_key_to_left = bare_left_id and right_to_left_overlap >= 0.5
    generic_bare_id_pair = bare_left_id and bare_right_id
    return foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair


def _join_block_cardinality_from_unique_ratios(
    left_unique_ratio: float,
    right_unique_ratio: float,
) -> str:
    if left_unique_ratio >= 0.98 and right_unique_ratio >= 0.98:
        return "one_to_one"
    if left_unique_ratio >= 0.98:
        return "one_to_many"
    if right_unique_ratio >= 0.98:
        return "many_to_one"
    return "many_to_many"


def _source_aligned_fk_confidence(
    *,
    cardinality: str,
    sample_overlap_count: int,
    sparse_zero_overlap: bool,
) -> float:
    if cardinality == "one_to_one":
        base = 0.82
    else:
        base = 0.76
    if sample_overlap_count >= 3:
        return round(min(0.92, base + 0.08), 3)
    if sample_overlap_count == 2:
        return round(min(0.90, base + 0.06), 3)
    if sample_overlap_count == 1:
        return round(min(0.88, base + 0.03), 3)
    if sparse_zero_overlap:
        return round(base, 3)
    return 0.0


def _meets_source_aligned_fk_fill_requirements(
    *,
    referenced_fill_rate: float,
    referencing_fill_rate: float,
    referenced_unique_ratio: float,
    referenced_unique_count: int,
    sample_overlap_count: int,
) -> bool:
    if referenced_fill_rate < _SOURCE_ALIGNED_FK_MIN_FILL_RATE:
        return False
    if referencing_fill_rate >= _SOURCE_ALIGNED_FK_MIN_FILL_RATE:
        return True
    if referenced_unique_ratio < _SOURCE_ALIGNED_FK_MIN_REFERENCED_UNIQUE_RATIO:
        return False
    if referenced_unique_count > _SOURCE_ALIGNED_FK_SMALL_DIMENSION_MAX_UNIQUE_COUNT:
        return False
    if referencing_fill_rate < _SOURCE_ALIGNED_FK_SMALL_DIMENSION_MIN_REFERENCING_FILL_RATE:
        return False
    required_overlap = min(
        _SOURCE_ALIGNED_FK_SMALL_DIMENSION_MIN_OVERLAP_COUNT,
        referenced_unique_count,
    )
    if sample_overlap_count < required_overlap:
        return False
    overlap_ratio = sample_overlap_count / max(referenced_unique_count, 1)
    return overlap_ratio >= _SOURCE_ALIGNED_FK_SMALL_DIMENSION_MIN_OVERLAP_RATIO


def _build_source_aligned_foreign_key_connections(
    *,
    src_id: str,
    src_name: str,
    other_id: str,
    other_name: str,
    left_join_blocks: list[dict[str, Any]] | None,
    right_join_blocks: list[dict[str, Any]] | None,
    src_value_candidates: dict[str, dict[str, Any]] | None,
    other_value_candidates: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not left_join_blocks or not right_join_blocks:
        return []
    if not src_value_candidates or not other_value_candidates:
        return []

    left_blocks = {
        str(block.get("name") or "").strip(): block
        for block in left_join_blocks
        if str(block.get("name") or "").strip()
    }
    right_blocks = {
        str(block.get("name") or "").strip(): block
        for block in right_join_blocks
        if str(block.get("name") or "").strip()
    }

    connections: list[dict[str, Any]] = []
    for left_name, left_block in left_blocks.items():
        left_candidate = src_value_candidates.get(left_name)
        if left_candidate is None:
            continue
        left_fill_rate = float(left_block.get("fill_rate") or 0.0)
        left_unique_ratio = float(
            left_block.get("unique_ratio") or left_candidate.get("unique_ratio") or 0.0
        )
        left_unique_count = int(left_block.get("unique_count") or 0)
        left_values = {
            str(value) for value in (left_candidate.get("values") or []) if str(value).strip()
        }
        left_sample_size = int(left_candidate.get("sample_size") or 0)
        for right_name, right_block in right_blocks.items():
            right_candidate = other_value_candidates.get(right_name)
            if right_candidate is None:
                continue
            if _join_key_names_are_compatible(left_name, right_name):
                continue

            foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
                _source_aligned_foreign_key_flags(src_name, other_name, left_name, right_name)
            )
            if generic_bare_id_pair or foreign_key_to_right == foreign_key_to_left:
                continue

            right_fill_rate = float(right_block.get("fill_rate") or 0.0)
            right_unique_ratio = float(
                right_block.get("unique_ratio") or right_candidate.get("unique_ratio") or 0.0
            )
            right_unique_count = int(right_block.get("unique_count") or 0)
            right_values = {
                str(value) for value in (right_candidate.get("values") or []) if str(value).strip()
            }
            right_sample_size = int(right_candidate.get("sample_size") or 0)
            if not left_values or not right_values:
                continue

            sample_intersection = left_values & right_values
            sample_union = left_values | right_values
            sample_overlap_count = len(sample_intersection)
            sample_overlap = round(sample_overlap_count / max(len(sample_union), 1), 4)

            if foreign_key_to_right:
                referenced_unique_ratio = right_unique_ratio
                referenced_unique_count = right_unique_count
                referenced_fill_rate = right_fill_rate
                referencing_fill_rate = left_fill_rate
                cardinality = _join_block_cardinality_from_unique_ratios(
                    left_unique_ratio,
                    right_unique_ratio,
                )
            else:
                referenced_unique_ratio = left_unique_ratio
                referenced_unique_count = left_unique_count
                referenced_fill_rate = left_fill_rate
                referencing_fill_rate = right_fill_rate
                cardinality = _join_block_cardinality_from_unique_ratios(
                    left_unique_ratio,
                    right_unique_ratio,
                )

            if cardinality == "many_to_many":
                continue
            if not _meets_source_aligned_fk_fill_requirements(
                referenced_fill_rate=referenced_fill_rate,
                referencing_fill_rate=referencing_fill_rate,
                referenced_unique_ratio=referenced_unique_ratio,
                referenced_unique_count=referenced_unique_count,
                sample_overlap_count=sample_overlap_count,
            ):
                continue
            if referenced_unique_ratio < _SOURCE_ALIGNED_FK_MIN_REFERENCED_UNIQUE_RATIO:
                continue

            sparse_zero_overlap = (
                sample_overlap_count == 0
                and max(left_sample_size, right_sample_size)
                >= _SOURCE_ALIGNED_FK_ZERO_OVERLAP_MIN_SAMPLE_SIZE
                and min(left_unique_count, right_unique_count)
                >= _SOURCE_ALIGNED_FK_ZERO_OVERLAP_MIN_UNIQUE_COUNT
                and referenced_unique_count >= _SOURCE_ALIGNED_FK_ZERO_OVERLAP_MIN_UNIQUE_COUNT
            )
            confidence = _source_aligned_fk_confidence(
                cardinality=cardinality,
                sample_overlap_count=sample_overlap_count,
                sparse_zero_overlap=sparse_zero_overlap,
            )
            if confidence <= 0.0:
                continue

            connections.append(
                {
                    "source_a": src_id,
                    "source_a_name": src_name,
                    "col_a": left_name,
                    "source_b": other_id,
                    "source_b_name": other_name,
                    "col_b": right_name,
                    "method": "source_aligned_foreign_key_join",
                    "confidence": confidence,
                    "cardinality": cardinality,
                    "overlap": sample_overlap,
                }
            )
    return connections


async def detect_joins_between(
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
    metadata_fast_join_candidates_fn: MetadataFastJoinCandidatesFn,
    load_join_projection_cached_fn: LoadJoinProjectionCachedFn,
    load_join_name_stats_cached_fn: LoadJoinNameStatsCachedFn,
    load_join_value_candidates_cached_fn: LoadJoinValueCandidatesCachedFn,
    call_mojo_join_detect_fn: CallMojoJoinDetectFn,
    logger: Any,
) -> list[dict[str, Any]]:
    """
    Run Mojo join_detect between two sources.
    Loads BOTH sources fully from their Parquet bytes so we send ALL unique
    values to Mojo — critical for high-cardinality keys like PART_NUMBER
    where a 200-row sample would rarely show overlap across 12K-row tables.
    Returns connection dicts.
    """
    try:
        metadata_fast_connections = metadata_fast_join_candidates_fn(
            src_id=src_id,
            src_name=src_name,
            other_id=other_id,
            other_name=other_name,
            left_join_blocks=left_join_blocks,
            right_join_blocks=right_join_blocks,
        )
        if _has_decisive_fast_join(metadata_fast_connections):
            return _bounded_fast_join_connections(metadata_fast_connections)

        if src_df is not None and other_df is not None:
            projected_src_df = src_df
            projected_other_df = other_df
        elif src_df is not None:
            projected_src_df = src_df
            projected_other_df = load_join_projection_cached_fn(
                org_id=org_id,
                source_id=other_id,
                parquet_bytes=other_parquet,
                parquet_path=other_parquet_path,
                join_blocks=right_join_blocks,
                max_rows=other_projection_max_rows,
            )
        elif other_df is not None:
            projected_other_df = other_df
            projected_src_df = load_join_projection_cached_fn(
                org_id=org_id,
                source_id=src_id,
                parquet_bytes=src_parquet,
                parquet_path=src_parquet_path,
                join_blocks=left_join_blocks,
                max_rows=src_projection_max_rows,
            )
        else:
            projected_src_df = load_join_projection_cached_fn(
                org_id=org_id,
                source_id=src_id,
                parquet_bytes=src_parquet,
                parquet_path=src_parquet_path,
                join_blocks=left_join_blocks,
                max_rows=src_projection_max_rows,
            )
            projected_other_df = load_join_projection_cached_fn(
                org_id=org_id,
                source_id=other_id,
                parquet_bytes=other_parquet,
                parquet_path=other_parquet_path,
                join_blocks=right_join_blocks,
                max_rows=other_projection_max_rows,
            )

        connections_fast: list[dict[str, Any]] = []
        seen_fast_pairs: set[tuple[str, str]] = set()
        should_collect_name_stats = _should_collect_fast_join_name_stats(
            left_join_blocks=left_join_blocks,
            right_join_blocks=right_join_blocks,
        )
        if should_collect_name_stats:
            if src_name_stats is None:
                src_name_stats = load_join_name_stats_cached_fn(
                    org_id=org_id,
                    source_id=src_id,
                    join_blocks=left_join_blocks,
                    df=projected_src_df,
                    parquet_bytes=src_parquet,
                    parquet_path=src_parquet_path,
                    max_rows=src_projection_max_rows,
                )
            if other_name_stats is None:
                other_name_stats = load_join_name_stats_cached_fn(
                    org_id=org_id,
                    source_id=other_id,
                    join_blocks=right_join_blocks,
                    df=projected_other_df,
                    parquet_bytes=other_parquet,
                    parquet_path=other_parquet_path,
                    max_rows=other_projection_max_rows,
                )
            src_col_lower = {col.lower(): col for col in projected_src_df.columns}
            other_col_lower = {col.lower(): col for col in projected_other_df.columns}
            shared_names = set(src_col_lower) & set(other_col_lower)
            for name_lower in shared_names:
                src_col = src_col_lower[name_lower]
                other_col = other_col_lower[name_lower]
                src_stats = src_name_stats.get(src_col)
                other_stats = other_name_stats.get(other_col)
                if src_stats is None or other_stats is None:
                    continue
                connection = _build_shared_value_fast_connection(
                    src_id=src_id,
                    src_name=src_name,
                    src_col=src_col,
                    src_stats=src_stats,
                    other_id=other_id,
                    other_name=other_name,
                    other_col=other_col,
                    other_stats=other_stats,
                )
                if connection is None:
                    continue
                connections_fast.append(connection)
                seen_fast_pairs.add((src_col, other_col))

            src_key_norms: dict[str, list[str]] = {}
            other_key_norms: dict[str, list[str]] = {}
            for column_name in projected_src_df.columns:
                normalized = _normalized_join_key_name(column_name)
                if normalized:
                    src_key_norms.setdefault(normalized, []).append(column_name)
            for column_name in projected_other_df.columns:
                normalized = _normalized_join_key_name(column_name)
                if normalized:
                    other_key_norms.setdefault(normalized, []).append(column_name)
            for normalized_name in set(src_key_norms) & set(other_key_norms):
                for src_col in src_key_norms[normalized_name]:
                    for other_col in other_key_norms[normalized_name]:
                        if (src_col, other_col) in seen_fast_pairs:
                            continue
                        src_stats = src_name_stats.get(src_col)
                        other_stats = other_name_stats.get(other_col)
                        if src_stats is None or other_stats is None:
                            continue
                        connection = _build_shared_value_fast_connection(
                            src_id=src_id,
                            src_name=src_name,
                            src_col=src_col,
                            src_stats=src_stats,
                            other_id=other_id,
                            other_name=other_name,
                            other_col=other_col,
                            other_stats=other_stats,
                        )
                        if connection is None:
                            continue
                        connections_fast.append(connection)
                        seen_fast_pairs.add((src_col, other_col))

            src_family_columns = _dimension_family_columns(src_name_stats)
            other_family_columns = _dimension_family_columns(other_name_stats)
            for family in set(src_family_columns) & set(other_family_columns):
                for src_col, src_stats in src_family_columns[family]:
                    for other_col, other_stats in other_family_columns[family]:
                        if (src_col, other_col) in seen_fast_pairs:
                            continue
                        src_values = src_stats.get("values") or set()
                        other_values = other_stats.get("values") or set()
                        intersection = src_values & other_values
                        union = src_values | other_values
                        jaccard = len(intersection) / max(len(union), 1)
                        cardinality = _infer_shared_column_cardinality_from_stats(
                            src_stats,
                            other_stats,
                            intersection,
                        )
                        if not _is_low_cardinality_dimension_join(
                            src_col,
                            src_stats,
                            other_col,
                            other_stats,
                            intersection,
                            jaccard,
                            cardinality,
                        ):
                            continue
                        connection = _build_shared_value_fast_connection(
                            src_id=src_id,
                            src_name=src_name,
                            src_col=src_col,
                            src_stats=src_stats,
                            other_id=other_id,
                            other_name=other_name,
                            other_col=other_col,
                            other_stats=other_stats,
                        )
                        if connection is None:
                            continue
                        connections_fast.append(connection)
                        seen_fast_pairs.add((src_col, other_col))

        if _has_decisive_fast_join(connections_fast):
            return _bounded_fast_join_connections(connections_fast)
        if _should_accept_fast_join_connections(
            connections_fast,
            left_join_blocks=left_join_blocks,
            right_join_blocks=right_join_blocks,
            left_rows=len(projected_src_df),
            right_rows=len(projected_other_df),
        ):
            return _bounded_fast_join_connections(connections_fast)

        value_candidate_limit = _join_value_candidate_limit(
            left_df=projected_src_df,
            right_df=projected_other_df,
            fast_connections=connections_fast,
        )
        if src_value_candidates is None:
            src_value_candidates = load_join_value_candidates_cached_fn(
                org_id=org_id,
                source_id=src_id,
                join_blocks=left_join_blocks,
                limit=value_candidate_limit,
                df=projected_src_df,
                parquet_bytes=src_parquet,
                parquet_path=src_parquet_path,
                max_rows=src_projection_max_rows,
            )
        if other_value_candidates is None:
            other_value_candidates = load_join_value_candidates_cached_fn(
                org_id=org_id,
                source_id=other_id,
                join_blocks=right_join_blocks,
                limit=value_candidate_limit,
                df=projected_other_df,
                parquet_bytes=other_parquet,
                parquet_path=other_parquet_path,
                max_rows=other_projection_max_rows,
            )

        source_aligned_fk_connections = _build_source_aligned_foreign_key_connections(
            src_id=src_id,
            src_name=src_name,
            other_id=other_id,
            other_name=other_name,
            left_join_blocks=left_join_blocks,
            right_join_blocks=right_join_blocks,
            src_value_candidates=src_value_candidates,
            other_value_candidates=other_value_candidates,
        )
        for connection in source_aligned_fk_connections:
            key = (str(connection.get("col_a") or ""), str(connection.get("col_b") or ""))
            if key in seen_fast_pairs:
                continue
            connections_fast.append(connection)
            seen_fast_pairs.add(key)

        columns: dict[str, dict[str, Any]] = {
            f"{src_name}.{col_name}": payload for col_name, payload in src_value_candidates.items()
        }
        columns.update(
            {
                f"{other_name}.{col_name}": payload
                for col_name, payload in other_value_candidates.items()
            }
        )

        if not columns:
            return connections_fast

        result = await call_mojo_join_detect_fn(
            src_name,
            other_name,
            columns,
            0.4,
        )
        if not result:
            return connections_fast

        mojo_connections: list[dict[str, Any]] = []
        for join_key in result.get("join_keys", []):
            field_a = str(join_key.get("field_a", "") or "")
            field_b = str(join_key.get("field_b", "") or "")
            confidence = float(join_key.get("confidence", 0.0) or 0.0)
            overlap = float(join_key.get("overlap", 0.0) or 0.0)
            if overlap <= 0.0:
                logger.debug(
                    "join_detect_rejected_zero_overlap",
                    src=src_name,
                    other=other_name,
                    field_a=field_a,
                    field_b=field_b,
                    confidence=confidence,
                )
                continue
            if not _join_key_names_are_compatible(field_a, field_b):
                logger.debug(
                    "join_detect_rejected_semantic_key_mismatch",
                    src=src_name,
                    other=other_name,
                    field_a=field_a,
                    field_b=field_b,
                )
                continue
            foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
                _source_aligned_foreign_key_flags(
                    src_name,
                    other_name,
                    field_a,
                    field_b,
                )
            )
            if generic_bare_id_pair and not (foreign_key_to_right or foreign_key_to_left):
                logger.debug(
                    "join_detect_rejected_generic_bare_id_pair",
                    src=src_name,
                    other=other_name,
                    field_a=field_a,
                    field_b=field_b,
                )
                continue
            mojo_connections.append(
                {
                    "source_a": src_id,
                    "source_a_name": src_name,
                    "col_a": field_a,
                    "source_b": other_id,
                    "source_b_name": other_name,
                    "col_b": field_b,
                    "method": "mojo_join_detect",
                    "confidence": confidence,
                    "cardinality": join_key.get("cardinality", "?"),
                    "overlap": overlap,
                }
            )

        seen: set[tuple[str, str]] = {
            (connection["col_a"], connection["col_b"]) for connection in connections_fast
        }
        for connection in mojo_connections:
            key = (connection["col_a"], connection["col_b"])
            if key not in seen:
                connections_fast.append(connection)
                seen.add(key)
        return connections_fast

    except Exception as exc:
        logger.debug(
            "join_detect_failed",
            src=src_name,
            other=other_name,
            error=str(exc),
        )
        return []
