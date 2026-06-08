from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from apps.api_server.services.auto_planner_semantics import (
    _normalize_match_value,
    _semantic_token_set,
    _source_token_set,
)

_GENERIC_KEY_TOKENS = frozenset({"id", "identifier", "key"})


def _canonical_semantic_tokens(text: str) -> set[str]:
    tokens = set(_semantic_token_set(text))
    expanded = set(tokens)
    for token in tokens:
        if len(token) > 4 and token.endswith("ies"):
            expanded.add(f"{token[:-3]}y")
        elif len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            expanded.add(token[:-1])
    return expanded


def _source_alignment_score(column_tokens: set[str], source_tokens: set[str]) -> float:
    informative_column_tokens = column_tokens - _GENERIC_KEY_TOKENS
    informative_source_tokens = source_tokens - _GENERIC_KEY_TOKENS
    if not informative_column_tokens or not informative_source_tokens:
        return 0.0
    return len(informative_column_tokens & informative_source_tokens) / max(
        len(informative_source_tokens),
        1,
    )


def find_join_keys(
    planner: Any,
    src_a: str,
    src_b: str,
    *,
    python_join_keys_fn: Callable[[str, str], list[dict[str, Any]]],
    join_candidates_for_source_fn: Callable[[str], dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    cache_key = (min(src_a, src_b), max(src_a, src_b))
    if cache_key in planner._join_cache:
        cached_keys = planner._join_cache[cache_key]
        if isinstance(cached_keys, list):
            return cached_keys
        return []

    if "join_detect" not in planner.mojo_engines:
        result = python_join_keys_fn(src_a, src_b)
        planner._join_cache[cache_key] = result
        return result

    prof_a = planner.profiles.get(src_a, {})
    prof_b = planner.profiles.get(src_b, {})

    if not prof_a or not prof_b:
        planner._join_cache[cache_key] = []
        return []

    columns: dict[str, dict[str, Any]] = {}
    columns.update(join_candidates_for_source_fn(src_a))
    columns.update(join_candidates_for_source_fn(src_b))

    if not columns:
        planner._join_cache[cache_key] = []
        return []

    result = planner._call_mojo(
        {
            "engine_type": "join_detect",
            "source_a": src_a,
            "source_b": src_b,
            "min_confidence": planner._join_min_conf,
            "columns": columns,
        }
    )

    if isinstance(result, dict):
        join_keys = result.get("join_keys")
    else:
        join_keys = None
    if isinstance(join_keys, list) and join_keys:
        keys = sorted(
            [item for item in join_keys if isinstance(item, dict)],
            key=lambda item: item.get("confidence", 0),
            reverse=True,
        )
        planner._join_cache[cache_key] = keys
        return keys

    fallback = python_join_keys_fn(src_a, src_b)
    planner._join_cache[cache_key] = fallback
    return fallback


def join_candidates_for_source(planner: Any, src: str) -> dict[str, dict[str, Any]]:
    cached = planner._join_candidate_columns.get(src)
    if isinstance(cached, dict):
        return cached

    prof = planner.profiles.get(src, {})
    columns: dict[str, dict[str, Any]] = {}
    for col, info in prof.items():
        unique_ratio = info.get("unique_count", 0) / max(info.get("total_count", 1), 1)
        fill = info.get("fill_rate", 1.0)
        if fill < 0.05:
            continue
        if not info.get("is_numeric") or unique_ratio > 0.85:
            samples = [
                str(value) for value in (info.get("strings") or info.get("sample_values", []))[:30]
            ]
            if samples:
                columns[f"{src}.{col}"] = {
                    "values": samples,
                    "unique_ratio": round(unique_ratio, 4),
                    "sample_size": info.get("total_count", 0),
                }

    planner._join_candidate_columns[src] = columns
    return columns


def sample_edge_evidence(
    planner: Any,
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
    *,
    sample_limit: int = 400,
) -> dict[str, float]:
    cache_key = (left_source, left_key, right_source, right_key)
    cached = planner._join_evidence_cache.get(cache_key)
    if cached is not None:
        return dict(cached)

    planner._ensure_records(left_source)
    planner._ensure_records(right_source)
    left_rows = planner.tables.get(left_source, [])
    right_rows = planner.tables.get(right_source, [])
    if not left_rows or not right_rows:
        evidence = {"coverage": 1.0, "single_match_ratio": 1.0, "fanout_risk": 0.0}
        planner._join_evidence_cache[cache_key] = evidence
        return dict(evidence)

    if len(left_rows) > sample_limit:
        step = max(len(left_rows) // sample_limit, 1)
        sampled_left = left_rows[::step][:sample_limit]
    else:
        sampled_left = left_rows

    right_index: dict[str, int] = {}
    for row in right_rows:
        key = _normalize_match_value(row.get(right_key))
        if not key:
            continue
        right_index[key] = right_index.get(key, 0) + 1

    eligible = 0
    matched = 0
    single = 0
    fanout_hits = 0
    for row in sampled_left:
        key = _normalize_match_value(row.get(left_key))
        if not key:
            continue
        eligible += 1
        count = right_index.get(key, 0)
        if count <= 0:
            continue
        matched += 1
        if count == 1:
            single += 1
        elif count > 1:
            fanout_hits += 1

    coverage = matched / max(eligible, 1)
    single_ratio = single / max(matched, 1)
    fanout_risk = fanout_hits / max(matched, 1)
    evidence = {
        "coverage": round(coverage, 4),
        "single_match_ratio": round(single_ratio, 4),
        "fanout_risk": round(fanout_risk, 4),
    }
    planner._join_evidence_cache[cache_key] = evidence
    return dict(evidence)


def sample_group_edge_evidence(
    planner: Any,
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
    group_col: str,
    *,
    sample_limit: int = 400,
) -> dict[str, float]:
    cache_key = (left_source, left_key, right_source, right_key, group_col)
    cached = planner._group_join_evidence_cache.get(cache_key)
    if cached is not None:
        return dict(cached)

    planner._ensure_records(left_source)
    planner._ensure_records(right_source)
    left_rows = planner.tables.get(left_source, [])
    right_rows = planner.tables.get(right_source, [])
    if not left_rows or not right_rows or not group_col:
        evidence = {"coverage": 1.0, "stable_ratio": 1.0, "conflict_ratio": 0.0}
        planner._group_join_evidence_cache[cache_key] = evidence
        return dict(evidence)

    if len(left_rows) > sample_limit:
        step = max(len(left_rows) // sample_limit, 1)
        sampled_left = left_rows[::step][:sample_limit]
    else:
        sampled_left = left_rows

    group_map: dict[str, str] = {}
    conflict_keys: set[str] = set()
    for row in right_rows:
        key = _normalize_match_value(row.get(right_key))
        group_value = _normalize_match_value(row.get(group_col))
        if not key or not group_value:
            continue
        existing = group_map.get(key)
        if existing is None:
            group_map[key] = group_value
            continue
        if existing != group_value:
            conflict_keys.add(key)

    for key in conflict_keys:
        group_map.pop(key, None)

    eligible = 0
    matched = 0
    stable = 0
    conflicts = 0
    for row in sampled_left:
        key = _normalize_match_value(row.get(left_key))
        if not key:
            continue
        eligible += 1
        if key in conflict_keys:
            conflicts += 1
            continue
        if key in group_map:
            matched += 1
            stable += 1

    observed = matched + conflicts
    evidence = {
        "coverage": round(matched / max(eligible, 1), 4),
        "stable_ratio": round(stable / max(observed, 1), 4),
        "conflict_ratio": round(conflicts / max(observed, 1), 4),
    }
    planner._group_join_evidence_cache[cache_key] = evidence
    return dict(evidence)


def build_source_distinctiveness(
    planner: Any,
    source: str,
    *,
    join_only: bool,
) -> list[tuple[float, int]]:
    values: list[tuple[float, int]] = []
    for _col, info in planner.profiles.get(source, {}).items():
        total_count = int(info.get("total_count", 0) or 0)
        unique_count = int(info.get("unique_count", 0) or 0)
        fill = float(info.get("fill_rate", 0.0) or 0.0)
        if total_count <= 0 or unique_count <= 0 or fill < 0.05:
            continue
        unique_ratio = unique_count / max(total_count, 1)
        if join_only:
            is_numeric = bool(info.get("is_numeric", False))
            has_values = bool(info.get("strings") or info.get("sample_values") or [])
            if not has_values:
                continue
            if is_numeric and unique_ratio < 0.70:
                continue
        values.append((unique_ratio, unique_count))

    values.sort()
    return values


def rebuild_adaptive_context(
    planner: Any,
    *,
    adaptive_source_context_cls: type[Any],
    build_source_distinctiveness_fn: Callable[[str, bool], list[tuple[float, int]]],
) -> None:
    context: dict[str, Any] = {}
    for source in planner.profiles:
        context[source] = adaptive_source_context_cls(
            join_distinctiveness=tuple(build_source_distinctiveness_fn(source, True)),
            column_distinctiveness=tuple(build_source_distinctiveness_fn(source, False)),
        )
    planner._adaptive_source_context = context


def source_distinctiveness_distribution(
    planner: Any,
    source: str,
    *,
    join_only: bool,
    rebuild_adaptive_context_fn: Callable[[], None],
) -> list[tuple[float, int]]:
    source_context = planner._adaptive_source_context.get(source)
    if source_context is None:
        rebuild_adaptive_context_fn()
        source_context = planner._adaptive_source_context.get(source)
    if source_context is None:
        return []
    values = (
        source_context.join_distinctiveness if join_only else source_context.column_distinctiveness
    )
    return list(values)


def rank_fraction(value: float, population: list[float]) -> float:
    if not population:
        return 0.5
    below = sum(1 for item in population if item < value)
    equal = sum(1 for item in population if item == value)
    return (below + 0.5 * equal) / len(population)


def join_key_distinctiveness(
    planner: Any,
    source: str,
    key: str,
    *,
    source_distinctiveness_distribution_fn: Callable[[str, bool], list[tuple[float, int]]],
    rank_fraction_fn: Callable[[float, list[float]], float],
) -> tuple[float, int, float]:
    info = planner.profiles.get(source, {}).get(key, {})
    total_count = int(info.get("total_count", 0) or 0)
    unique_count = int(info.get("unique_count", 0) or 0)
    if total_count <= 0 or unique_count <= 0:
        return 1.0, unique_count, 0.0

    unique_ratio = unique_count / max(total_count, 1)
    distribution = source_distinctiveness_distribution_fn(source, True)
    ratio_rank = rank_fraction_fn(unique_ratio, [ratio for ratio, _count in distribution])
    count_rank = rank_fraction_fn(
        float(unique_count),
        [float(count) for _ratio, count in distribution],
    )
    fallback_ratio = min(unique_ratio / 0.50, 1.0)
    fallback_count = min(
        math.log(unique_count + 1.0, 2) / max(math.log(total_count + 1.0, 2), 1.0),
        1.0,
    )
    ratio_signal = 0.65 * ratio_rank + 0.35 * fallback_ratio
    count_signal = 0.65 * count_rank + 0.35 * fallback_count
    strength = 0.35 + 0.40 * ratio_signal + 0.25 * count_signal
    return round(min(max(strength, 0.30), 1.0), 6), unique_count, round(unique_ratio, 6)


def python_join_keys(planner: Any, src_a: str, src_b: str) -> list[dict[str, Any]]:
    prof_a = planner.profiles.get(src_a, {})
    prof_b = planner.profiles.get(src_b, {})
    results: list[dict[str, Any]] = []
    source_tokens_a = _canonical_semantic_tokens(" ".join(_source_token_set(src_a)))
    source_tokens_b = _canonical_semantic_tokens(" ".join(_source_token_set(src_b)))

    for col_a, info_a in prof_a.items():
        if info_a.get("fill_rate", 1.0) < 0.05:
            continue
        unique_ratio_a = 1.0
        if info_a.get("is_numeric"):
            unique_ratio_a = info_a.get("unique_count", 0) / max(info_a.get("total_count", 1), 1)
        tokens_a = _canonical_semantic_tokens(col_a)
        if not tokens_a:
            continue
        for col_b, info_b in prof_b.items():
            if info_b.get("fill_rate", 1.0) < 0.05:
                continue
            unique_ratio_b = 1.0
            if info_b.get("is_numeric"):
                unique_ratio_b = info_b.get("unique_count", 0) / max(
                    info_b.get("total_count", 1),
                    1,
                )
            tokens_b = _canonical_semantic_tokens(col_b)
            if not tokens_b:
                continue
            both = tokens_a & tokens_b
            union = tokens_a | tokens_b
            name_sim = len(both) / max(len(union), 1)
            if name_sim < 0.30:
                continue

            values_a = {
                str(value)
                for value in (info_a.get("strings") or info_a.get("sample_values", []))[:50]
                if value
            }
            values_b = {
                str(value)
                for value in (info_b.get("strings") or info_b.get("sample_values", []))[:50]
                if value
            }
            if values_a and values_b:
                overlap = len(values_a & values_b) / max(len(values_a | values_b), 1)
            else:
                overlap = 0.0

            left_to_right_source_alignment = _source_alignment_score(tokens_a, source_tokens_b)
            right_to_left_source_alignment = _source_alignment_score(tokens_b, source_tokens_a)
            bare_left_key = tokens_a <= _GENERIC_KEY_TOKENS
            bare_right_key = tokens_b <= _GENERIC_KEY_TOKENS
            foreign_key_to_right = bare_right_key and left_to_right_source_alignment >= 0.50
            foreign_key_to_left = bare_left_key and right_to_left_source_alignment >= 0.50
            if info_a.get("is_numeric") and unique_ratio_a < 0.80 and not foreign_key_to_right:
                continue
            if info_b.get("is_numeric") and unique_ratio_b < 0.80 and not foreign_key_to_left:
                continue

            confidence = name_sim * 0.60 + overlap * 0.40
            cardinality = "many_to_many"
            if foreign_key_to_right or foreign_key_to_left:
                alignment = max(
                    left_to_right_source_alignment,
                    right_to_left_source_alignment,
                )
                confidence = max(
                    confidence,
                    0.72 + 0.18 * alignment + 0.10 * min(overlap * 2.0, 1.0),
                )
                cardinality = "many_to_one" if foreign_key_to_right else "one_to_many"
            elif bare_left_key and bare_right_key:
                confidence *= 0.55

            if confidence >= planner._join_min_conf:
                results.append(
                    {
                        "field_a": col_a,
                        "source_a": src_a,
                        "field_b": col_b,
                        "source_b": src_b,
                        "confidence": round(confidence, 3),
                        "overlap": round(overlap, 3),
                        "cardinality": cardinality,
                    }
                )

    results.sort(key=lambda item: item["confidence"], reverse=True)
    return results
