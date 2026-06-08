from __future__ import annotations

from typing import Any

from apps.api_server.services.auto_planner_semantics import (
    _JOIN_KEY_ENTITY_TOKENS,
    _JOIN_KEY_MEASURE_TOKENS,
    _MEASURE_LIKE_ROLES,
    _semantic_token_set,
)

_GENERIC_JOIN_KEY_TOKENS = frozenset({"code", "id", "identifier", "key", "name", "number", "type"})
_STRONG_QUALIFIED_FOREIGN_KEY_TOKENS = frozenset(
    {"billing", "headquarters", "home", "hq", "lessor", "resident", "shipping"}
)
_MILD_QUALIFIED_FOREIGN_KEY_TOKENS = frozenset(
    {"branch", "destination", "manager", "office", "origin", "primary", "secondary"}
)


def _canonical_source_tokens(text: str) -> set[str]:
    tokens = _semantic_token_set(text)
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
    left_tokens = _semantic_token_set(left_key)
    right_tokens = _semantic_token_set(right_key)
    left_source_tokens = _canonical_source_tokens(left_source)
    right_source_tokens = _canonical_source_tokens(right_source)
    bare_left_id = left_tokens <= _GENERIC_JOIN_KEY_TOKENS
    bare_right_id = right_tokens <= _GENERIC_JOIN_KEY_TOKENS
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


def _source_aligned_foreign_key_extra_tokens(
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
) -> set[str]:
    foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
        _source_aligned_foreign_key_flags(left_source, right_source, left_key, right_key)
    )
    if generic_bare_id_pair or foreign_key_to_right == foreign_key_to_left:
        return set()
    if foreign_key_to_right:
        foreign_key_tokens = _semantic_token_set(left_key)
        referenced_source_tokens = _canonical_source_tokens(right_source)
    else:
        foreign_key_tokens = _semantic_token_set(right_key)
        referenced_source_tokens = _canonical_source_tokens(left_source)
    return {
        token
        for token in foreign_key_tokens
        if token not in referenced_source_tokens and token not in _GENERIC_JOIN_KEY_TOKENS
    }


def _hop_selection_multiplier(hop: Any) -> float:
    left_source = str(getattr(hop, "left_source", "") or "")
    right_source = str(getattr(hop, "right_source", "") or "")
    left_key = str(getattr(hop, "left_key", "") or "")
    right_key = str(getattr(hop, "right_key", "") or "")
    foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
        _source_aligned_foreign_key_flags(left_source, right_source, left_key, right_key)
    )
    if generic_bare_id_pair or foreign_key_to_right == foreign_key_to_left:
        return 1.0
    extra_tokens = _source_aligned_foreign_key_extra_tokens(
        left_source,
        right_source,
        left_key,
        right_key,
    )
    if not extra_tokens:
        return 1.05
    if extra_tokens & _STRONG_QUALIFIED_FOREIGN_KEY_TOKENS:
        return 0.55
    if extra_tokens & _MILD_QUALIFIED_FOREIGN_KEY_TOKENS:
        return 0.72
    extra_count = min(len(extra_tokens), 3)
    return max(0.72, 0.88 - 0.08 * extra_count)


def _hop_has_qualified_foreign_key(hop: Any) -> bool:
    return bool(
        _source_aligned_foreign_key_extra_tokens(
            str(getattr(hop, "left_source", "") or ""),
            str(getattr(hop, "right_source", "") or ""),
            str(getattr(hop, "left_key", "") or ""),
            str(getattr(hop, "right_key", "") or ""),
        )
    )


def _path_selection_multiplier(hops: list[Any]) -> float:
    if not hops:
        return 1.0
    multiplier = 1.0
    aligned_hops = 0
    clean_aligned_hops = 0
    for hop in hops:
        hop_multiplier = _hop_selection_multiplier(hop)
        multiplier *= hop_multiplier
        left_source = str(getattr(hop, "left_source", "") or "")
        right_source = str(getattr(hop, "right_source", "") or "")
        left_key = str(getattr(hop, "left_key", "") or "")
        right_key = str(getattr(hop, "right_key", "") or "")
        foreign_key_to_right, foreign_key_to_left, generic_bare_id_pair = (
            _source_aligned_foreign_key_flags(left_source, right_source, left_key, right_key)
        )
        if generic_bare_id_pair or foreign_key_to_right == foreign_key_to_left:
            continue
        aligned_hops += 1
        if not _source_aligned_foreign_key_extra_tokens(
            left_source,
            right_source,
            left_key,
            right_key,
        ):
            clean_aligned_hops += 1
    if len(hops) > 1 and aligned_hops == len(hops):
        multiplier *= 1.08
        if clean_aligned_hops == len(hops):
            multiplier *= 1.12
    return multiplier


def group_dimension_join_key_multiplier(
    group_col: str | None,
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
) -> float:
    if not group_col:
        return 1.0

    group_text = str(group_col or "").lower()
    group_is_inventory_dimension = any(
        token in group_text
        for token in (
            "inventory",
            "product",
            "vendor",
            "vend",
            "warehouse",
            "part",
            "item",
            "line",
            "type",
        )
    )
    if not group_is_inventory_dimension:
        return 1.0

    key_text = f"{left_key} {right_key}".lower()
    source_text = f"{left_source} {right_source}".lower()
    multiplier = 1.0
    if any(token in key_text for token in ("part", "item", "sku", "product", "catalog")):
        multiplier *= 1.10
    if any(token in key_text for token in ("order", "quote", "booking", "invoice", "request")):
        multiplier *= 0.90
    if (
        any(token in source_text for token in ("booking", "bookings", "order", "orders"))
        and "order" in key_text
    ):
        multiplier *= 1.35
    return multiplier


def join_key_semantic_multiplier(
    planner: Any,
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
) -> tuple[float, bool]:
    left_tokens = _semantic_token_set(left_key)
    right_tokens = _semantic_token_set(right_key)
    left_source_tokens = _semantic_token_set(left_source)
    right_source_tokens = _semantic_token_set(right_source)
    left_node = planner.graph.get(left_source, {}).get(left_key)
    right_node = planner.graph.get(right_source, {}).get(right_key)
    left_measure_like = bool(
        _JOIN_KEY_MEASURE_TOKENS & left_tokens
        or (left_node and left_node.role in _MEASURE_LIKE_ROLES)
    )
    right_measure_like = bool(
        _JOIN_KEY_MEASURE_TOKENS & right_tokens
        or (right_node and right_node.role in _MEASURE_LIKE_ROLES)
    )
    multiplier = 1.0
    if left_measure_like and right_measure_like:
        multiplier *= 0.52
    elif left_measure_like or right_measure_like:
        multiplier *= 0.76

    left_entity_like = bool(_JOIN_KEY_ENTITY_TOKENS & left_tokens)
    right_entity_like = bool(_JOIN_KEY_ENTITY_TOKENS & right_tokens)
    if left_entity_like and right_entity_like:
        multiplier *= 1.12
    elif left_entity_like or right_entity_like:
        multiplier *= 1.04

    if (
        left_node
        and right_node
        and left_node.is_numeric
        and right_node.is_numeric
        and not (left_entity_like or right_entity_like)
    ):
        multiplier *= 0.82

    bare_left_id = left_tokens <= {"id"}
    bare_right_id = right_tokens <= {"id"}
    if bare_left_id and bare_right_id:
        multiplier *= 0.42

    left_to_right_overlap = len(left_tokens & right_source_tokens) / max(
        len(right_source_tokens),
        1,
    )
    right_to_left_overlap = len(right_tokens & left_source_tokens) / max(
        len(left_source_tokens),
        1,
    )
    if left_to_right_overlap >= 0.5:
        multiplier *= 1.28
        if bare_right_id:
            multiplier *= 1.16
    if right_to_left_overlap >= 0.5:
        multiplier *= 1.28
        if bare_left_id:
            multiplier *= 1.16

    return multiplier, left_measure_like and right_measure_like
