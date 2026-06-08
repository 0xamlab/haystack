from __future__ import annotations

import re
from typing import Any

from apps.api_server.services.source_join_scan_policy import (
    estimated_join_pair_cost,
    join_candidate_limit,
    join_candidate_min_score,
    join_value_candidate_limit,
    should_use_scored_join_scan,
)

_estimated_join_pair_cost = estimated_join_pair_cost
_join_candidate_limit = join_candidate_limit
_join_candidate_min_score = join_candidate_min_score
_join_value_candidate_limit = join_value_candidate_limit
_should_use_scored_join_scan = should_use_scored_join_scan

_DEEP_JOIN_COLUMN_LIMIT = 8
_DEEP_JOIN_DIMENSION_EXTENSION_LIMIT = 2
_DECISIVE_ONE_TO_ONE_FAST_JOIN_OVERLAP = 0.05
_DECISIVE_DIRECTIONAL_FAST_JOIN_OVERLAP = 0.075
_METADATA_FAST_JOIN_MIN_SAMPLE_OVERLAP = 3
_SUFFICIENT_FAST_JOIN_MIN_CONFIDENCE = 0.72
_SUFFICIENT_FAST_JOIN_MIN_OVERLAP = 0.08
_MAX_FAST_JOIN_CONNECTIONS_PER_PAIR = 6
_JOIN_KEY_NAME_TOKENS = frozenset(
    {
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
    }
)
_JOIN_KEY_MODIFIER_TOKENS = frozenset(
    {
        "line",
        "lines",
        "status",
        "type",
        "types",
    }
)
_DIMENSION_FAMILY_TOKEN_MAP = {
    "branch": "store",
    "location": "store",
    "merchant": "store",
    "outlet": "store",
    "restaurant": "store",
    "site": "store",
    "store": "store",
}
_DIMENSION_JOIN_MODIFIER_TOKENS = frozenset(
    {
        "as",
        "eats",
        "external",
        "local",
        "manager",
        "name",
        "per",
        "uber",
        "ubereats",
    }
)
_LOW_CARDINALITY_DIMENSION_MAX_DOMAIN = 32
_LOW_CARDINALITY_DIMENSION_MIN_OVERLAP = 2
_LOW_CARDINALITY_DIMENSION_MIN_JACCARD = 0.95
_VERY_LARGE_SINGLE_KEY_FAST_JOIN_ROW_THRESHOLD = 10_000
_VERY_LARGE_SINGLE_KEY_FAST_JOIN_MIN_OVERLAP = 0.10
_VERY_LARGE_SINGLE_KEY_FAST_JOIN_MIN_CONFIDENCE = 0.62
_VERY_LARGE_WIDE_PAIR_FAST_JOIN_ROW_THRESHOLD = 10_000
_VERY_LARGE_WIDE_PAIR_FAST_JOIN_BLOCK_THRESHOLD = 8
_GENERIC_SOURCE_ALIGNED_KEY_TOKENS = frozenset(
    {"code", "guid", "id", "identifier", "key", "number", "ref", "uuid"}
)
_SOURCE_ALIGNED_METADATA_MIN_REFERENCED_UNIQUE_RATIO = 0.98


def _looks_like_entity_join_key(name: str) -> bool:
    lowered = name.lower()
    tokens = set(re.findall(r"[a-z0-9]+", lowered))
    if tokens & _JOIN_KEY_NAME_TOKENS:
        return True
    return any(token in lowered for token in ("_id", "_key", "_code", "_ref", "_uuid", "_guid"))


def _dimension_join_family(name: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    families = {
        _DIMENSION_FAMILY_TOKEN_MAP[token]
        for token in tokens
        if token in _DIMENSION_FAMILY_TOKEN_MAP
    }
    if len(families) != 1:
        return ""
    non_dimension = {
        token
        for token in tokens
        if token not in _DIMENSION_FAMILY_TOKEN_MAP and token not in _DIMENSION_JOIN_MODIFIER_TOKENS
    }
    if len(non_dimension) > 1:
        return ""
    return next(iter(families))


def _join_key_name_base_tokens(name: str) -> tuple[str, ...]:
    if not _looks_like_entity_join_key(name):
        return ()
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]+", name.lower())
        if token not in _JOIN_KEY_NAME_TOKENS
        and token not in _JOIN_KEY_MODIFIER_TOKENS
        and token not in _DIMENSION_JOIN_MODIFIER_TOKENS
    )


def _canonical_source_tokens(name: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
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
    left_tokens = set(re.findall(r"[a-z0-9]+", left_key.lower()))
    right_tokens = set(re.findall(r"[a-z0-9]+", right_key.lower()))
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


def _join_key_names_are_compatible(left_name: str, right_name: str) -> bool:
    left_normalized = _normalized_join_key_name(left_name)
    right_normalized = _normalized_join_key_name(right_name)
    if left_normalized and right_normalized:
        if left_normalized == right_normalized:
            return True
        left_base = _join_key_name_base_tokens(left_name)
        right_base = _join_key_name_base_tokens(right_name)
        return bool(left_base and left_base == right_base)
    if bool(left_normalized) != bool(right_normalized):
        return False

    left_family = _dimension_join_family(left_name)
    if left_family and left_family == _dimension_join_family(right_name):
        return True

    return True


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


def _infer_shared_column_cardinality_from_stats(
    left_stats: dict[str, Any],
    right_stats: dict[str, Any],
    shared_values: set[str],
) -> str:
    if not shared_values:
        return "many_to_many"

    left_all_unique = bool(left_stats.get("all_unique"))
    right_all_unique = bool(right_stats.get("all_unique"))
    if left_all_unique and right_all_unique:
        return "one_to_one"
    if left_all_unique:
        return "one_to_many"
    if right_all_unique:
        return "many_to_one"

    return _infer_shared_column_cardinality(
        left_stats.get("counts") or {},
        right_stats.get("counts") or {},
        shared_values,
    )


def _shared_name_join_confidence(jaccard: float, cardinality: str) -> float:
    if cardinality == "one_to_one":
        return round(min(0.99, 0.80 + jaccard * 0.25), 3)
    if cardinality in {"one_to_many", "many_to_one"}:
        return round(min(0.97, 0.74 + jaccard * 0.22), 3)
    return round(min(0.90, 0.60 + jaccard * 0.18), 3)


def _dimension_family_join_confidence(jaccard: float) -> float:
    return round(min(0.79, 0.55 + jaccard * 0.20), 3)


def _is_low_cardinality_dimension_join(
    left_name: str,
    left_stats: dict[str, Any],
    right_name: str,
    right_stats: dict[str, Any],
    shared_values: set[str],
    jaccard: float,
    cardinality: str,
) -> bool:
    if cardinality != "many_to_many":
        return False
    left_family = _dimension_join_family(left_name)
    if not left_family or left_family != _dimension_join_family(right_name):
        return False
    if len(shared_values) < _LOW_CARDINALITY_DIMENSION_MIN_OVERLAP:
        return False
    if jaccard < _LOW_CARDINALITY_DIMENSION_MIN_JACCARD:
        return False
    left_domain = len(left_stats.get("values") or ())
    right_domain = len(right_stats.get("values") or ())
    if left_domain < 2 or right_domain < 2:
        return False
    return max(left_domain, right_domain) <= _LOW_CARDINALITY_DIMENSION_MAX_DOMAIN


def _dimension_family_columns(
    stats_by_column: dict[str, dict[str, Any]],
) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    families: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for column_name, column_stats in stats_by_column.items():
        family = _dimension_join_family(column_name)
        if not family:
            continue
        domain_size = len(column_stats.get("values") or ())
        if 2 <= domain_size <= _LOW_CARDINALITY_DIMENSION_MAX_DOMAIN:
            families.setdefault(family, []).append((column_name, column_stats))
    return families


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


def _sorted_fast_join_connections(
    connections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        connections,
        key=lambda connection: (
            float(connection.get("confidence") or 0.0),
            float(connection.get("overlap") or 0.0),
            str(connection.get("col_a") or ""),
            str(connection.get("col_b") or ""),
        ),
        reverse=True,
    )


def _bounded_fast_join_connections(
    connections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _sorted_fast_join_connections(connections)[:_MAX_FAST_JOIN_CONNECTIONS_PER_PAIR]


def _has_sufficient_fast_join_evidence(
    connections: list[dict[str, Any]],
) -> bool:
    strong_key_like = 0
    strong_total = 0
    for connection in connections:
        confidence = float(connection.get("confidence") or 0.0)
        overlap = float(connection.get("overlap") or 0.0)
        if (
            confidence < _SUFFICIENT_FAST_JOIN_MIN_CONFIDENCE
            and overlap < _SUFFICIENT_FAST_JOIN_MIN_OVERLAP
        ):
            continue
        strong_total += 1
        col_a = str(connection.get("col_a") or "")
        col_b = str(connection.get("col_b") or "")
        if _looks_like_entity_join_key(col_a) or _looks_like_entity_join_key(col_b):
            strong_key_like += 1
            if strong_key_like >= 2:
                return True
        if strong_total >= 4:
            return True
    return False


def _has_wide_pair_fast_join_evidence(
    connections: list[dict[str, Any]],
    *,
    left_join_blocks: list[dict[str, Any]] | None,
    right_join_blocks: list[dict[str, Any]] | None,
    left_rows: int,
    right_rows: int,
) -> bool:
    max_join_blocks = max(len(left_join_blocks or []), len(right_join_blocks or []))
    max_rows = max(left_rows, right_rows)
    if max_join_blocks < 12 and max_rows < 5_000:
        return False

    strong_key_like = 0
    strong_total = 0
    for connection in connections:
        confidence = float(connection.get("confidence") or 0.0)
        overlap = float(connection.get("overlap") or 0.0)
        if (
            confidence < _SUFFICIENT_FAST_JOIN_MIN_CONFIDENCE
            and overlap < _SUFFICIENT_FAST_JOIN_MIN_OVERLAP
        ):
            continue

        strong_total += 1
        col_a = str(connection.get("col_a") or "")
        col_b = str(connection.get("col_b") or "")
        if _looks_like_entity_join_key(col_a) or _looks_like_entity_join_key(col_b):
            strong_key_like += 1

        if (
            strong_key_like >= 1
            and strong_total >= 1
            and max_rows >= _VERY_LARGE_WIDE_PAIR_FAST_JOIN_ROW_THRESHOLD
            and max_join_blocks >= _VERY_LARGE_WIDE_PAIR_FAST_JOIN_BLOCK_THRESHOLD
        ):
            return True
        if strong_key_like >= 1 and strong_total >= 2:
            return True

    return False


def _has_very_large_pair_single_normalized_key_fast_join_evidence(
    connections: list[dict[str, Any]],
    *,
    left_rows: int,
    right_rows: int,
) -> bool:
    if max(left_rows, right_rows) < _VERY_LARGE_SINGLE_KEY_FAST_JOIN_ROW_THRESHOLD:
        return False

    for connection in connections:
        col_a = str(connection.get("col_a") or "")
        col_b = str(connection.get("col_b") or "")
        norm_a = _normalized_join_key_name(col_a)
        norm_b = _normalized_join_key_name(col_b)
        if not norm_a or norm_a != norm_b:
            continue

        confidence = float(connection.get("confidence") or 0.0)
        overlap = float(connection.get("overlap") or 0.0)
        if confidence < _VERY_LARGE_SINGLE_KEY_FAST_JOIN_MIN_CONFIDENCE:
            continue
        if overlap < _VERY_LARGE_SINGLE_KEY_FAST_JOIN_MIN_OVERLAP:
            continue
        return True

    return False


def _should_accept_fast_join_connections(
    connections: list[dict[str, Any]],
    *,
    left_join_blocks: list[dict[str, Any]] | None,
    right_join_blocks: list[dict[str, Any]] | None,
    left_rows: int,
    right_rows: int,
) -> bool:
    if _has_decisive_fast_join(connections):
        return True
    if _has_sufficient_fast_join_evidence(connections):
        return True
    if _has_very_large_pair_single_normalized_key_fast_join_evidence(
        connections,
        left_rows=left_rows,
        right_rows=right_rows,
    ):
        return True
    return _has_wide_pair_fast_join_evidence(
        connections,
        left_join_blocks=left_join_blocks,
        right_join_blocks=right_join_blocks,
        left_rows=left_rows,
        right_rows=right_rows,
    )


def _should_collect_fast_join_name_stats(
    *,
    left_join_blocks: list[dict[str, Any]] | None,
    right_join_blocks: list[dict[str, Any]] | None,
) -> bool:
    """
    Determine whether expensive shared-name stats can plausibly add value.

    This stays conservative: if join metadata is missing, keep the old behavior.
    When both sides have explicit join blocks, only build shared-name stats when
    those blocks show some realistic name-level join signal.
    """
    if left_join_blocks is None or right_join_blocks is None:
        return True
    if not left_join_blocks or not right_join_blocks:
        return False

    left_norms = {
        normalized
        for normalized in (_join_block_norm(block) for block in left_join_blocks)
        if normalized
    }
    right_norms = {
        normalized
        for normalized in (_join_block_norm(block) for block in right_join_blocks)
        if normalized
    }
    if left_norms & right_norms:
        return True

    left_tails = {
        str(block.get("tail") or "").strip().lower()
        for block in left_join_blocks
        if str(block.get("tail") or "").strip()
    }
    right_tails = {
        str(block.get("tail") or "").strip().lower()
        for block in right_join_blocks
        if str(block.get("tail") or "").strip()
    }
    if left_tails & right_tails:
        return True

    left_dimension_families = {
        family
        for family in (
            _dimension_join_family(str(block.get("name") or "")) for block in left_join_blocks
        )
        if family
    }
    right_dimension_families = {
        family
        for family in (
            _dimension_join_family(str(block.get("name") or "")) for block in right_join_blocks
        )
        if family
    }
    return bool(left_dimension_families & right_dimension_families)


def _join_block_norm(block: dict[str, Any]) -> str:
    name = str(block.get("name") or "").strip()
    if not name:
        return ""
    normalized_key = _normalized_join_key_name(name)
    if normalized_key:
        return normalized_key
    return str(block.get("norm") or "".join(re.findall(r"[a-z0-9]+", name.lower())))


def _normalized_join_key_name(name: str) -> str:
    if not _looks_like_entity_join_key(name):
        return ""
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", name.lower())
        if token not in _DIMENSION_JOIN_MODIFIER_TOKENS
    ]
    return "".join(tokens)


def _build_shared_value_fast_connection(
    *,
    src_id: str,
    src_name: str,
    src_col: str,
    src_stats: dict[str, Any],
    other_id: str,
    other_name: str,
    other_col: str,
    other_stats: dict[str, Any],
) -> dict[str, Any] | None:
    src_vals = src_stats.get("values") or set()
    other_vals = other_stats.get("values") or set()
    if not src_vals or not other_vals:
        return None
    intersection = src_vals & other_vals
    union = src_vals | other_vals
    jaccard = len(intersection) / len(union) if union else 0.0
    cardinality = _infer_shared_column_cardinality_from_stats(
        src_stats,
        other_stats,
        intersection,
    )
    dimension_like = _is_low_cardinality_dimension_join(
        src_col,
        src_stats,
        other_col,
        other_stats,
        intersection,
        jaccard,
        cardinality,
    )
    src_ur = float(src_stats.get("unique_ratio") or 0.0)
    other_ur = float(other_stats.get("unique_ratio") or 0.0)
    looks_like_key = _looks_like_entity_join_key(src_col) or _looks_like_entity_join_key(other_col)
    enough_overlap = (
        len(intersection) > 3
        or (
            cardinality in {"one_to_one", "one_to_many", "many_to_one"}
            and len(intersection) >= 2
            and jaccard >= 0.50
        )
        or dimension_like
    )
    if jaccard <= 0.05 or not enough_overlap:
        return None
    if (
        cardinality == "many_to_many"
        and not looks_like_key
        and max(src_ur, other_ur) < 0.80
        and not dimension_like
    ):
        return None
    foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
        _source_aligned_foreign_key_flags(
            src_name,
            other_name,
            src_col,
            other_col,
        )
    )
    if generic_bare_id_pair and not (foreign_key_to_right or foreign_key_to_left):
        return None
    return {
        "source_a": src_id,
        "source_a_name": src_name,
        "col_a": src_col,
        "source_b": other_id,
        "source_b_name": other_name,
        "col_b": other_col,
        "method": "fast_shared_value_join",
        "confidence": (
            _dimension_family_join_confidence(jaccard)
            if dimension_like
            else _shared_name_join_confidence(jaccard, cardinality)
        ),
        "cardinality": cardinality,
        "overlap": round(jaccard, 4),
    }


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
            foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
                _source_aligned_foreign_key_flags(
                    src_name,
                    other_name,
                    left_name,
                    right_name,
                )
            )
            if generic_bare_id_pair and not (foreign_key_to_right or foreign_key_to_left):
                continue
            if generic_bare_id_pair:
                referenced = right if foreign_key_to_right else left
                if (
                    float(referenced.get("unique_ratio") or 0.0)
                    < _SOURCE_ALIGNED_METADATA_MIN_REFERENCED_UNIQUE_RATIO
                ):
                    continue

            sample_union = left_samples | right_samples
            overlap = sample_overlap / max(len(sample_union), 1)
            candidates.append(
                {
                    "source_a": src_id,
                    "source_a_name": src_name,
                    "col_a": left_name,
                    "source_b": other_id,
                    "source_b_name": other_name,
                    "col_b": right_name,
                    "method": "metadata_fast_join",
                    "confidence": _shared_name_join_confidence(overlap, cardinality),
                    "cardinality": cardinality,
                    "overlap": round(overlap, 4),
                }
            )

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
    dimension_extensions = 0
    for block in join_blocks or []:
        if dimension_extensions >= _DEEP_JOIN_DIMENSION_EXTENSION_LIMIT:
            break
        name = str(block.get("name") or "").strip()
        if not name or name in seen:
            continue
        if not _dimension_join_family(name):
            continue
        projected.append(name)
        seen.add(name)
        dimension_extensions += 1
    return projected
