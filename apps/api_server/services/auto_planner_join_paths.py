from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.api_server.services.auto_planner_join_scoring import (
    _GENERIC_JOIN_KEY_TOKENS,
    _hop_has_qualified_foreign_key,
    _path_selection_multiplier,
    _source_aligned_foreign_key_extra_tokens,
    _source_aligned_foreign_key_flags,
)
from apps.api_server.services.auto_planner_join_scoring import (
    group_dimension_join_key_multiplier as _group_dimension_join_key_multiplier,
)
from apps.api_server.services.auto_planner_join_scoring import (
    join_key_semantic_multiplier as _join_key_semantic_multiplier,
)
from apps.api_server.services.auto_planner_semantics import _semantic_token_set


def group_dimension_join_key_multiplier(
    group_col: str | None,
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
) -> float:
    return _group_dimension_join_key_multiplier(
        group_col,
        left_source,
        right_source,
        left_key,
        right_key,
    )


def join_key_semantic_multiplier(
    planner: Any,
    left_source: str,
    right_source: str,
    left_key: str,
    right_key: str,
) -> tuple[float, bool]:
    return _join_key_semantic_multiplier(
        planner,
        left_source,
        right_source,
        left_key,
        right_key,
    )


def join_candidate_effective_conf(
    planner: Any,
    candidate: dict[str, Any],
    *,
    group_col: str | None = None,
    cardinality_penalty_fn: Callable[[str], float],
    group_dimension_join_key_multiplier_fn: Callable[[str | None, str, str, str, str], float],
    join_key_semantic_multiplier_fn: Callable[[str, str, str, str], tuple[float, bool]],
) -> float:
    raw_conf = float(candidate.get("confidence", 0.0) or 0.0)
    card = str(candidate.get("cardinality", "") or "")
    penalty = cardinality_penalty_fn(card)
    effective = raw_conf * penalty
    left_source = str(candidate.get("source_a", "") or "")
    right_source = str(candidate.get("source_b", "") or "")
    left_key_raw = str(candidate.get("field_a", "") or "").strip()
    right_key_raw = str(candidate.get("field_b", "") or "").strip()
    left_key = left_key_raw.lower()
    right_key = right_key_raw.lower()
    metadata_only = str(candidate.get("evidence_source", "") or "") == "registry"
    foreign_key_to_right = False
    foreign_key_to_left = False
    generic_bare_id_pair = False
    if left_source and right_source and left_key_raw and right_key_raw:
        (
            foreign_key_to_right,
            foreign_key_to_left,
            generic_bare_id_pair,
        ) = _source_aligned_foreign_key_flags(
            left_source,
            right_source,
            left_key_raw,
            right_key_raw,
        )
        if metadata_only:
            overlap = max(0.0, min(float(candidate.get("overlap", 0.5) or 0.5), 1.0))
            effective *= 0.72 + 0.28 * overlap
            if card in {"", "one_to_one", "many_to_one"}:
                stability = 1.0
                fanout_risk = 0.0
            elif card == "one_to_many":
                stability = 0.82
                fanout_risk = 0.18
            else:
                stability = 0.64
                fanout_risk = 0.36
            if group_col:
                group_profile = planner.profiles.get(right_source, {}).get(group_col, {})
                group_fill = max(
                    0.0,
                    min(float(group_profile.get("fill_rate", 1.0) or 1.0), 1.0),
                )
                effective *= 0.80 + 0.20 * group_fill
            if generic_bare_id_pair and not (foreign_key_to_right or foreign_key_to_left):
                evidence = planner._sample_edge_evidence(
                    left_source,
                    right_source,
                    left_key_raw,
                    right_key_raw,
                )
                if evidence["coverage"] <= 0.0 and not group_col:
                    return 0.0
                effective *= evidence["coverage"]
                stability = min(stability, max(evidence["single_match_ratio"], 0.25))
                fanout_risk = max(fanout_risk, evidence["fanout_risk"])
        else:
            evidence = planner._sample_edge_evidence(
                left_source,
                right_source,
                left_key_raw,
                right_key_raw,
            )
            if evidence["coverage"] <= 0.0 and not group_col:
                return 0.0
            effective *= 0.60 + 0.40 * evidence["coverage"]
            stability = evidence["single_match_ratio"]
            fanout_risk = evidence["fanout_risk"]
            if group_col:
                group_evidence = planner._sample_group_edge_evidence(
                    left_source,
                    right_source,
                    left_key_raw,
                    right_key_raw,
                    group_col,
                )
                if evidence["coverage"] <= 0.0 and group_evidence["coverage"] <= 0.0:
                    return 0.0
                stability = max(stability, group_evidence["stable_ratio"])
                fanout_risk = max(0.0, fanout_risk - 0.80 * group_evidence["stable_ratio"])
                effective *= 0.70 + 0.30 * group_evidence["coverage"]
                effective *= 1.00 - 0.20 * group_evidence["conflict_ratio"]
        effective *= 0.70 + 0.30 * stability
        effective *= 1.00 - 0.25 * fanout_risk
        left_strength, left_unique_count, _left_unique_ratio = planner._join_key_distinctiveness(
            left_source, left_key_raw
        )
        right_strength, right_unique_count, _right_unique_ratio = planner._join_key_distinctiveness(
            right_source, right_key_raw
        )
        strength_multiplier = min(left_strength, right_strength)
        if foreign_key_to_right:
            strength_multiplier = max(
                strength_multiplier,
                0.55 + 0.45 * right_strength,
            )
        elif foreign_key_to_left:
            strength_multiplier = max(
                strength_multiplier,
                0.55 + 0.45 * left_strength,
            )
        effective *= strength_multiplier
        effective *= group_dimension_join_key_multiplier_fn(
            group_col,
            left_source,
            right_source,
            left_key_raw,
            right_key_raw,
        )
        join_key_multiplier, both_measure_like = join_key_semantic_multiplier_fn(
            left_source,
            right_source,
            left_key_raw,
            right_key_raw,
        )
        effective *= join_key_multiplier
        known_unique_counts = [
            count for count in (left_unique_count, right_unique_count) if count > 0
        ]
        if (
            known_unique_counts
            and not (foreign_key_to_right or foreign_key_to_left)
            and max(known_unique_counts) <= 20
        ):
            effective *= 0.82
        elif (
            known_unique_counts
            and not (foreign_key_to_right or foreign_key_to_left)
            and max(known_unique_counts) <= 100
        ):
            effective *= 0.92
    else:
        both_measure_like = False
    if penalty < 1.0 and left_key and right_key and left_key == right_key and not both_measure_like:
        effective += 0.06
    return round(min(effective, 1.0), 6)


def normalize_join_candidate(
    left_source: str,
    right_source: str,
    candidate: dict[str, Any],
    *,
    reverse_join_cardinality_fn: Callable[[str], str],
) -> dict[str, Any]:
    source_a = candidate.get("source_a", "")
    source_b = candidate.get("source_b", "")
    field_a = candidate.get("field_a", "")
    field_b = candidate.get("field_b", "")
    card = str(candidate.get("cardinality", "") or "")

    if source_a == left_source and source_b == right_source:
        return {
            "field_a": field_a,
            "source_a": left_source,
            "field_b": field_b,
            "source_b": right_source,
            "confidence": float(candidate.get("confidence", 0.0) or 0.0),
            "cardinality": card,
            "overlap": float(candidate.get("overlap", 0.0) or 0.0),
        }

    return {
        "field_a": field_b,
        "source_a": left_source,
        "field_b": field_a,
        "source_b": right_source,
        "confidence": float(candidate.get("confidence", 0.0) or 0.0),
        "cardinality": reverse_join_cardinality_fn(card),
        "overlap": float(candidate.get("overlap", 0.0) or 0.0),
    }


def registry_join_candidates(
    planner: Any,
    left_source: str,
    right_source: str,
    *,
    reverse_join_cardinality_fn: Callable[[str], str],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for conn in planner._connections:
        src_a = conn.get("source_a_name", "")
        src_b = conn.get("source_b_name", "")
        if src_a == left_source and src_b == right_source:
            matches.append(
                {
                    "field_a": conn.get("col_a", ""),
                    "source_a": left_source,
                    "field_b": conn.get("col_b", ""),
                    "source_b": right_source,
                    "confidence": float(conn.get("confidence", 0.0) or 0.0),
                    "cardinality": str(conn.get("cardinality", "") or ""),
                    "overlap": float(conn.get("overlap", 0.5) or 0.5),
                    "evidence_source": "registry",
                }
            )
        elif src_a == right_source and src_b == left_source:
            matches.append(
                {
                    "field_a": conn.get("col_b", ""),
                    "source_a": left_source,
                    "field_b": conn.get("col_a", ""),
                    "source_b": right_source,
                    "confidence": float(conn.get("confidence", 0.0) or 0.0),
                    "cardinality": reverse_join_cardinality_fn(
                        str(conn.get("cardinality", "") or "")
                    ),
                    "overlap": float(conn.get("overlap", 0.5) or 0.5),
                    "evidence_source": "registry",
                }
            )
    matches.sort(key=lambda item: item.get("confidence", 0.0), reverse=True)
    return matches


def direct_join_candidates(
    planner: Any,
    left_source: str,
    right_source: str,
    *,
    registry_join_candidates_fn: Callable[[str, str], list[dict[str, Any]]],
    normalize_join_candidate_fn: Callable[[str, str, dict[str, Any]], dict[str, Any]],
    find_join_keys_fn: Callable[[str, str], list[dict[str, Any]]],
    probe_join_keys_fn: Callable[[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    registry_matches = registry_join_candidates_fn(left_source, right_source)
    runtime_probe_needed = bool(registry_matches) and all(
        _semantic_token_set(str(candidate.get("field_a", "") or "")) <= _GENERIC_JOIN_KEY_TOKENS
        and _semantic_token_set(str(candidate.get("field_b", "") or "")) <= _GENERIC_JOIN_KEY_TOKENS
        for candidate in registry_matches
    )
    if registry_matches and not runtime_probe_needed:
        return registry_matches

    runtime_matches = [
        normalize_join_candidate_fn(left_source, right_source, candidate)
        for candidate in probe_join_keys_fn(left_source, right_source)
    ]
    if not registry_matches:
        if not runtime_matches:
            runtime_matches = [
                normalize_join_candidate_fn(left_source, right_source, candidate)
                for candidate in find_join_keys_fn(left_source, right_source)
            ]
        runtime_matches.sort(key=lambda item: item.get("confidence", 0.0), reverse=True)
        return runtime_matches

    runtime_has_source_aligned_fk = any(
        any(
            _source_aligned_foreign_key_flags(
                left_source,
                right_source,
                str(candidate.get("field_a", "") or ""),
                str(candidate.get("field_b", "") or ""),
            )[:2]
        )
        for candidate in runtime_matches
    )
    if runtime_has_source_aligned_fk:
        registry_matches = [
            candidate
            for candidate in registry_matches
            if not _source_aligned_foreign_key_flags(
                left_source,
                right_source,
                str(candidate.get("field_a", "") or ""),
                str(candidate.get("field_b", "") or ""),
            )[2]
        ]
        runtime_matches = [
            candidate
            for candidate in runtime_matches
            if not _source_aligned_foreign_key_flags(
                left_source,
                right_source,
                str(candidate.get("field_a", "") or ""),
                str(candidate.get("field_b", "") or ""),
            )[2]
            or any(
                _source_aligned_foreign_key_flags(
                    left_source,
                    right_source,
                    str(candidate.get("field_a", "") or ""),
                    str(candidate.get("field_b", "") or ""),
                )[:2]
            )
        ]

    combined: dict[tuple[str, str], dict[str, Any]] = {
        (
            str(candidate.get("field_a", "") or ""),
            str(candidate.get("field_b", "") or ""),
        ): candidate
        for candidate in registry_matches
    }
    for candidate in runtime_matches:
        key = (
            str(candidate.get("field_a", "") or ""),
            str(candidate.get("field_b", "") or ""),
        )
        existing = combined.get(key)
        if existing is None or float(candidate.get("confidence", 0.0) or 0.0) > float(
            existing.get("confidence", 0.0) or 0.0
        ):
            combined[key] = candidate
    matches = list(combined.values())
    matches.sort(key=lambda item: item.get("confidence", 0.0), reverse=True)
    return matches


# Fix #1: hard ceiling on edge evaluations per search pass. The cross-source fallback
# fan-out is ~all known sources at every node to depth max_hops, which on a dense registry
# (hundreds of sources / edges) explodes into tens of thousands of _rank_candidates calls
# (and the speculative parquet sampling behind them). A generous cap (real star/snowflake
# joins resolve in well under this) bounds the cold-query cost without dropping legitimate
# shallow paths; we still return the best path found within budget.
_JOIN_SEARCH_MAX_EXPANSIONS = 2500


def search_join_path(
    planner: Any,
    metric_src: str,
    group_src: str,
    *,
    group_col: str | None = None,
    max_hops: int = 4,
    direct_join_candidates_fn: Callable[[str, str], list[dict[str, Any]]],
    join_candidate_effective_conf_fn: Callable[[dict[str, Any], str | None], float],
    join_hop_cls: type[Any],
) -> tuple[list[Any], float, list[str], str | None]:
    # Fix #3: memoize the (expensive) join-path search on the planner instance. The planner
    # is rebuilt + re-cached whenever the workspace's visible-dataset set / schema changes
    # (the query_registry_planner cache key includes the visibility hash), so the planner's
    # lifetime IS the schema version — the in-instance cache needs no extra schema key.
    cache = getattr(planner, "_join_path_cache", None)
    if cache is None:
        cache = {}
        try:
            planner._join_path_cache = cache
        except Exception:
            cache = None
    key = (metric_src, group_src, group_col)
    if cache is not None and key in cache:
        return cache[key]
    result = _search_join_path_impl(
        planner,
        metric_src,
        group_src,
        group_col=group_col,
        max_hops=max_hops,
        direct_join_candidates_fn=direct_join_candidates_fn,
        join_candidate_effective_conf_fn=join_candidate_effective_conf_fn,
        join_hop_cls=join_hop_cls,
    )
    if cache is not None:
        cache[key] = result
    return result


def _search_join_path_impl(
    planner: Any,
    metric_src: str,
    group_src: str,
    *,
    group_col: str | None = None,
    max_hops: int = 4,
    direct_join_candidates_fn: Callable[[str, str], list[dict[str, Any]]],
    join_candidate_effective_conf_fn: Callable[[dict[str, Any], str | None], float],
    join_hop_cls: type[Any],
) -> tuple[list[Any], float, list[str], str | None]:
    if metric_src == group_src:
        return [], 1.0, [], None

    known_sources = list(planner.graph.keys())
    if metric_src not in known_sources or group_src not in known_sources:
        msg = f"Unknown source in join path search: {metric_src} -> {group_src}"
        return [], 0.0, [msg], msg

    registry_adjacency: dict[str, set[str]] = {}
    for connection in getattr(planner, "_connections", []):
        src_a = str(connection.get("source_a_name") or "")
        src_b = str(connection.get("source_b_name") or "")
        if not src_a or not src_b:
            continue
        registry_adjacency.setdefault(src_a, set()).add(src_b)
        registry_adjacency.setdefault(src_b, set()).add(src_a)

    def _path_min_safe_conf(hops: list[Any]) -> float:
        path_has_many_to_many = any(h.cardinality == "many_to_many" for h in hops)
        path_has_expansion = any(
            h.cardinality in {"one_to_many", "1:N", "many_to_many", "N:N"} for h in hops
        )
        path_is_non_expanding = all(
            h.cardinality in {"", "one_to_one", "many_to_one"} for h in hops
        )
        path_is_source_aligned = all(
            not _source_aligned_foreign_key_flags(
                str(getattr(hop, "left_source", "") or ""),
                str(getattr(hop, "right_source", "") or ""),
                str(getattr(hop, "left_key", "") or ""),
                str(getattr(hop, "right_key", "") or ""),
            )[2]
            and _source_aligned_foreign_key_flags(
                str(getattr(hop, "left_source", "") or ""),
                str(getattr(hop, "right_source", "") or ""),
                str(getattr(hop, "left_key", "") or ""),
                str(getattr(hop, "right_key", "") or ""),
            )[:2]
            != (False, False)
            for hop in hops
        )
        path_has_qualified_hops = any(
            _source_aligned_foreign_key_extra_tokens(
                str(getattr(hop, "left_source", "") or ""),
                str(getattr(hop, "right_source", "") or ""),
                str(getattr(hop, "left_key", "") or ""),
                str(getattr(hop, "right_key", "") or ""),
            )
            for hop in hops
        )
        exact_key_path = all(
            h.left_key.strip().lower() == h.right_key.strip().lower()
            for h in hops
            if h.left_key and h.right_key
        )
        if path_has_many_to_many:
            return 0.22 if exact_key_path else 0.48
        if exact_key_path:
            return 0.18
        if path_is_non_expanding and len(hops) > 1:
            min_hop_conf = min(float(getattr(h, "confidence", 0.0) or 0.0) for h in hops)
            if path_is_source_aligned and min_hop_conf >= 0.75:
                return 0.12 if not path_has_qualified_hops else 0.14
            if min_hop_conf >= 0.80:
                return 0.18
            return 0.20
        if path_has_expansion:
            return 0.28
        return 0.24

    def _rank_candidates(
        current: str,
        next_src: str,
    ) -> tuple[list[dict[str, Any]], float, list[str], Any] | None:
        direct_candidates = direct_join_candidates_fn(current, next_src)
        if not direct_candidates:
            return None

        def _effective_conf_for_candidate(
            candidate: dict[str, Any],
            current_next_src: str = next_src,
        ) -> float:
            target_group_col = group_col if current_next_src == group_src else None
            return join_candidate_effective_conf_fn(candidate, target_group_col)

        ranked_candidates = sorted(
            direct_candidates,
            key=_effective_conf_for_candidate,
            reverse=True,
        )
        top = ranked_candidates[0]
        top_conf = float(top.get("confidence", 0.0) or 0.0)
        card = str(top.get("cardinality", "") or "")
        edge_effective_conf = _effective_conf_for_candidate(top)
        edge_notes: list[str] = []
        if len(ranked_candidates) > 1:
            second_effective_conf = _effective_conf_for_candidate(ranked_candidates[1])
            if second_effective_conf >= edge_effective_conf - 0.03:
                edge_notes.append(f"ambiguous join candidates between {current} and {next_src}")

        hop = join_hop_cls(
            left_source=current,
            right_source=next_src,
            left_key=str(top.get("field_a", "") or ""),
            right_key=str(top.get("field_b", "") or ""),
            confidence=round(top_conf, 3),
            cardinality=card,
            notes=list(edge_notes),
        )
        return ranked_candidates, edge_effective_conf, edge_notes, hop

    def _candidate_targets(
        current: str,
        visited: set[str],
        *,
        registry_only: bool,
    ) -> list[str]:
        if registry_only and registry_adjacency:
            registry_neighbors = [
                source
                for source in sorted(registry_adjacency.get(current, set()))
                if source not in visited and source != current
            ]
            if not registry_neighbors:
                return []
            ordered: list[str] = []
            if group_src in registry_neighbors:
                ordered.append(group_src)
            ordered.extend(source for source in registry_neighbors if source != group_src)
            return ordered
        return [group_src] + [
            source
            for source in known_sources
            if source not in visited and source != current and source != group_src
        ]

    def _search_candidates(
        *,
        registry_only: bool,
    ) -> tuple[list[Any], float, list[str], str | None] | None:
        candidate_paths: list[tuple[float, float, float, list[Any], list[str]]] = []
        expansions = 0  # Fix #1: edge-evaluation budget for this pass (see _JOIN_SEARCH_MAX_EXPANSIONS)

        should_try_direct = (
            not registry_only
            or not registry_adjacency
            or group_src in registry_adjacency.get(metric_src, set())
        )
        if should_try_direct:
            direct_path = _rank_candidates(metric_src, group_src)
            if direct_path is not None:
                _ranked_candidates, direct_effective_conf, direct_notes, direct_hop = direct_path
                direct_hops = [direct_hop]
                direct_rank_score = direct_effective_conf * _path_selection_multiplier(direct_hops)
                candidate_paths.append(
                    (
                        round(direct_rank_score, 6),
                        round(direct_effective_conf, 6),
                        round(float(getattr(direct_hop, "confidence", 0.0) or 0.0), 6),
                        direct_hops,
                        list(dict.fromkeys(direct_notes)),
                    )
                )
                if direct_effective_conf >= _path_min_safe_conf(
                    direct_hops
                ) and not _hop_has_qualified_foreign_key(direct_hop):
                    return (
                        direct_hops,
                        round(direct_effective_conf, 3),
                        list(dict.fromkeys(direct_notes)),
                        None,
                    )

        def _dfs(
            current: str,
            visited: set[str],
            hops: list[Any],
            raw_conf: float,
            effective_conf: float,
            notes: list[str],
        ) -> None:
            nonlocal expansions
            if len(hops) >= max_hops:
                return

            for next_src in _candidate_targets(current, visited, registry_only=registry_only):
                if expansions >= _JOIN_SEARCH_MAX_EXPANSIONS:
                    return
                expansions += 1
                ranked = _rank_candidates(current, next_src)
                if ranked is None:
                    continue
                ranked_candidates, edge_effective_conf, ranked_notes, hop = ranked
                top_conf = float(ranked_candidates[0].get("confidence", 0.0) or 0.0)
                edge_notes = list(notes) + list(ranked_notes)
                next_raw_conf = raw_conf * max(top_conf, 1e-6)
                next_effective_conf = effective_conf * max(edge_effective_conf, 1e-6)
                next_hops = hops + [hop]

                if next_src == group_src:
                    path_notes = list(edge_notes)
                    if len(next_hops) > 1:
                        path_notes.append(
                            "multi-hop path via "
                            + ", ".join(h.right_source for h in next_hops[:-1])
                        )
                    path_rank_score = next_effective_conf * _path_selection_multiplier(next_hops)
                    candidate_paths.append(
                        (
                            round(path_rank_score, 6),
                            round(next_effective_conf, 6),
                            round(next_raw_conf, 6),
                            next_hops,
                            list(dict.fromkeys(path_notes)),
                        )
                    )
                    continue

                _dfs(
                    next_src,
                    visited | {next_src},
                    next_hops,
                    next_raw_conf,
                    next_effective_conf,
                    edge_notes,
                )

        _dfs(metric_src, {metric_src}, [], 1.0, 1.0, [])

        if not candidate_paths:
            return None

        candidate_paths.sort(
            key=lambda item: (item[0], item[1], item[2], -len(item[3])),
            reverse=True,
        )
        _best_rank_score, best_effective_conf, _best_raw_conf, best_hops, best_notes = (
            candidate_paths[0]
        )
        notes = list(best_notes)

        if len(candidate_paths) > 1 and abs(candidate_paths[0][0] - candidate_paths[1][0]) <= 0.02:
            notes.append(f"ambiguous multi-hop path candidates from {metric_src} to {group_src}")

        min_safe_conf = _path_min_safe_conf(best_hops)
        if best_effective_conf < min_safe_conf:
            msg = (
                f"No safe join path from '{metric_src}' to '{group_src}' "
                f"(best confidence={best_effective_conf:.3f})"
            )
            notes.append(msg)
            return best_hops, round(best_effective_conf, 3), list(dict.fromkeys(notes)), msg

        return best_hops, round(best_effective_conf, 3), list(dict.fromkeys(notes)), None

    focused_result = _search_candidates(registry_only=bool(registry_adjacency))
    if focused_result is not None and focused_result[3] is None:
        return focused_result

    broad_result = _search_candidates(registry_only=False)
    if broad_result is not None:
        return broad_result
    if focused_result is not None:
        return focused_result

    msg = f"No join path from '{metric_src}' to '{group_src}'"
    return [], 0.0, [msg], msg
