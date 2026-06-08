from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from apps.api_server.services.auto_planner_semantics import (
    _dimension_semantic_evidence,
    _hint_requests_time,
    _semantic_token_set,
    _source_token_set,
    _tokenize_identifier,
    _value_semantic_score,
)
from apps.api_server.services.data_map_matching import rank_schema_dimension_columns

_DIMENSION_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def _source_hint_display_candidate(
    planner: Any,
    *,
    source_name: str,
    hint: str,
) -> tuple[str, float] | None:
    columns = list(planner.graph.get(source_name, {}))
    if not columns:
        return None
    ranked = rank_schema_dimension_columns(
        hint,
        columns,
        table_name=source_name,
    )
    if not ranked:
        return None
    top = ranked[0]
    return str(top["column"]), float(top["score"])


def dimension_hint_words(hint: str) -> tuple[list[str], set[str]]:
    raw_hint_words = re.findall(r"[a-z0-9]+", hint.lower())
    hint_words = [
        word for word in raw_hint_words if word not in _DIMENSION_STOP_WORDS
    ] or raw_hint_words
    return hint_words, _semantic_token_set(" ".join(hint_words))


def _dimension_role_base(
    node: Any,
    *,
    unique_count: int,
    total_count: int,
    category_role: Any,
    identifier_role: Any,
    text_role: Any,
    time_role: Any,
) -> float:
    is_low_card_numeric = bool(
        node.is_numeric
        and total_count >= 1
        and 1 < unique_count <= max(12, int(total_count * 0.05))
    )
    return {
        category_role: 0.50,
        text_role: 0.30,
        time_role: 0.50,
        identifier_role: 0.30,
    }.get(
        node.role,
        0.20 if not node.is_numeric else (0.16 if is_low_card_numeric else 0.0),
    )


def resolve_source_hint_match(
    planner: Any,
    *,
    hint_words: list[str],
    hint_token_set: set[str],
    category_role: Any,
    identifier_role: Any,
    text_role: Any,
    time_role: Any,
) -> tuple[set[str], tuple[str, str, float, str] | None]:
    hinted_sources = {src for src in planner.graph if hint_token_set & _source_token_set(src)}
    if not hinted_sources:
        return hinted_sources, None

    source_exact_best: tuple[str, str, float] | None = None
    for src in hinted_sources:
        source_tokens = _source_token_set(src)
        overlap = hint_token_set & source_tokens
        if not overlap:
            continue
        query_cov = len(overlap) / max(len(hint_token_set), 1)
        source_cov = len(overlap) / max(len(source_tokens), 1)
        exact_cover = min(query_cov, source_cov)
        if exact_cover < 0.95 and not (query_cov >= 0.95 and source_cov >= 0.66):
            continue
        display_candidate = _source_hint_display_candidate(
            planner,
            source_name=src,
            hint=" ".join(hint_words),
        )
        if display_candidate is None:
            continue
        candidate_col, candidate_score = display_candidate
        exact_score = round(
            1.45
            + exact_cover * 0.28
            + min(candidate_score, 1.2) * 0.18
            - max(len(source_tokens - hint_token_set), 0) * 0.05,
            3,
        )
        if source_exact_best is None or exact_score > source_exact_best[2]:
            source_exact_best = (src, candidate_col, exact_score)

    if source_exact_best is not None:
        return hinted_sources, (*source_exact_best, "source_hint_source_exact")

    source_hint_best: tuple[str, str, float] | None = None
    for src in hinted_sources:
        src_tokens = _source_token_set(src)
        remaining_tokens = [tok for tok in hint_words if tok not in src_tokens] or hint_words
        remaining_set = set(remaining_tokens)
        exact_named_candidate: tuple[str, str, float] | None = None
        for col, node in planner.graph.get(src, {}).items():
            col_tokens = _tokenize_identifier(col)
            if not col_tokens:
                continue

            exact_name_match = bool(remaining_set and remaining_set == col_tokens)
            if exact_name_match:
                fill = (
                    planner.profiles.get(src, {})
                    .get(col, {})
                    .get(
                        "fill_rate",
                        node.fill_rate,
                    )
                )
                total_count = planner.profiles.get(src, {}).get(col, {}).get("total_count", 0)
                if fill > 0.0 and total_count > 0:
                    score = round(1.65 + min(fill, 1.0) * 0.20, 3)
                    if exact_named_candidate is None or score > exact_named_candidate[2]:
                        exact_named_candidate = (src, col, score)
                continue

            prof_info = planner.profiles.get(src, {}).get(col, {})
            unique_count = prof_info.get("unique_count", 0)
            total_count = prof_info.get("total_count", 0)
            base = _dimension_role_base(
                node,
                unique_count=unique_count,
                total_count=total_count,
                category_role=category_role,
                identifier_role=identifier_role,
                text_role=text_role,
                time_role=time_role,
            )
            if base == 0.0:
                continue
            if node.role == time_role and not _hint_requests_time(hint_words):
                continue
            fill = prof_info.get("fill_rate", node.fill_rate)
            if fill < 0.02:
                continue
            if total_count >= 20 and unique_count <= 1:
                continue
            query_cov = len(remaining_set & col_tokens) / max(len(remaining_set), 1)
            col_cov = len(remaining_set & col_tokens) / max(len(col_tokens), 1)
            exact_cover = min(query_cov, col_cov)
            if query_cov < 0.60 or col_cov < 0.45:
                continue

            fuzzy, acro, val_sem = _dimension_semantic_evidence(
                remaining_tokens,
                col,
                prof_info.get("strings", [])[:30],
            )
            score = (base + max(fuzzy * 0.70, exact_cover * 1.10, acro * 0.50) + val_sem) * max(
                fill, 0.0
            )
            score += 0.35 + min(exact_cover, 1.0) * 0.25
            if source_hint_best is None or score > source_hint_best[2]:
                source_hint_best = (src, col, round(score, 3))

        if exact_named_candidate is not None:
            return hinted_sources, (*exact_named_candidate, "source_hint_exact")

    if source_hint_best is None:
        return hinted_sources, None
    return hinted_sources, (*source_hint_best, "source_hint")


def resolve_preferred_exact_match(
    planner: Any,
    *,
    hint_words: list[str],
    preferred_source: str | None,
    pref_bonus: float,
    category_role: Any,
    identifier_role: Any,
    text_role: Any,
    time_role: Any,
) -> tuple[str, str, float] | None:
    if not preferred_source or preferred_source not in planner.graph:
        return None

    pref_dim_tokens = _semantic_token_set(" ".join(hint_words))
    pref_exact: tuple[str, str, float] | None = None
    pref_src_tokens = _source_token_set(preferred_source)
    for col, node in planner.graph[preferred_source].items():
        col_tokens = _tokenize_identifier(col)
        if pref_dim_tokens and pref_dim_tokens == col_tokens:
            fill = (
                planner.profiles.get(preferred_source, {})
                .get(col, {})
                .get(
                    "fill_rate",
                    node.fill_rate,
                )
            )
            total_count = (
                planner.profiles.get(preferred_source, {})
                .get(
                    col,
                    {},
                )
                .get("total_count", 0)
            )
            if fill > 0.0 and total_count > 0:
                exact_score = round(1.55 + min(fill, 1.0) * 0.18 + pref_bonus, 3)
                if pref_exact is None or exact_score > pref_exact[2]:
                    pref_exact = (preferred_source, col, exact_score)
            continue

        prof_info = planner.profiles.get(preferred_source, {}).get(col, {})
        unique_count = prof_info.get("unique_count", 0)
        total_count = prof_info.get("total_count", 0)
        base = _dimension_role_base(
            node,
            unique_count=unique_count,
            total_count=total_count,
            category_role=category_role,
            identifier_role=identifier_role,
            text_role=text_role,
            time_role=time_role,
        )
        if base == 0.0:
            continue
        if node.role == time_role and not _hint_requests_time(hint_words):
            continue
        fill = prof_info.get("fill_rate", node.fill_rate)
        if fill < 0.02:
            continue
        if total_count >= 20 and unique_count <= 1:
            continue
        col_to_query = len(pref_dim_tokens & col_tokens) / len(col_tokens)
        query_to_col = len(pref_dim_tokens & col_tokens) / max(len(pref_dim_tokens), 1)
        exact_cover = min(col_to_query, query_to_col)
        if exact_cover < 0.95:
            continue
        source_bonus = 0.22 if pref_dim_tokens & pref_src_tokens else 0.0
        exact_score = round(
            (base + 0.70 + pref_bonus) * max(fill, 0.0) + source_bonus + exact_cover * 0.20,
            3,
        )
        if pref_exact is None or exact_score > pref_exact[2]:
            pref_exact = (preferred_source, col, exact_score)

    return pref_exact


def filter_initial_dimension_candidate(
    planner: Any,
    *,
    src: str,
    col: str,
    score: float,
    hint_words: list[str],
    hint_token_set: set[str],
    hinted_sources: set[str],
    steps: list[str],
    time_role: Any,
) -> tuple[str, str, float]:
    if not src or not col:
        return src, col, score

    prof_info = planner.profiles.get(src, {}).get(col, {})
    fuzzy, acro, _ = _dimension_semantic_evidence(
        hint_words,
        col,
        prof_info.get("strings", [])[:30],
    )
    col_tokens = _semantic_token_set(col)
    query_cov = len(hint_token_set & col_tokens) / max(len(hint_token_set), 1)
    col_cov = len(hint_token_set & col_tokens) / max(len(col_tokens), 1)
    node = planner.graph.get(src, {}).get(col)
    if node and node.role == time_role and not _hint_requests_time(hint_words):
        steps.append(
            f"[resolve_group/filter] rejected {src}.{col} — time dimension for non-time hint"
        )
        return "", "", 0.0

    if (
        len(hint_words) >= 2
        and max(query_cov, col_cov) < 0.50
        and acro < 0.50
        and not (hinted_sources and src in hinted_sources)
    ):
        steps.append(f"[resolve_group/filter] rejected {src}.{col} — low token coverage")
        return "", "", 0.0

    if (
        len(hint_words) == 1
        and query_cov == 0.0
        and fuzzy < 0.55
        and acro < 0.50
        and not (hinted_sources and src in hinted_sources)
    ):
        steps.append(f"[resolve_group/filter] rejected {src}.{col} — weak semantic evidence")
        return "", "", 0.0

    return src, col, score


def score_dimension_candidates(
    planner: Any,
    *,
    src: str,
    col: str,
    score: float,
    hint_words: list[str],
    hint_token_set: set[str],
    hinted_sources: set[str],
    preferred_source: str | None,
    pref_bonus: float,
    steps: list[str],
    category_role: Any,
    identifier_role: Any,
    text_role: Any,
    time_role: Any,
) -> tuple[str, str, float]:
    candidates: list[tuple[str, str, object, float, float]] = []
    for candidate_source in planner.graph:
        if (
            hinted_sources
            and candidate_source not in hinted_sources
            and preferred_source not in {None, candidate_source}
        ):
            continue
        for candidate_col, node in planner.graph[candidate_source].items():
            prof_info = planner.profiles.get(candidate_source, {}).get(candidate_col, {})
            unique_count = prof_info.get("unique_count", 0)
            total_count = prof_info.get("total_count", 0)
            base = _dimension_role_base(
                node,
                unique_count=unique_count,
                total_count=total_count,
                category_role=category_role,
                identifier_role=identifier_role,
                text_role=text_role,
                time_role=time_role,
            )
            if base == 0.0:
                continue
            if node.role == time_role and not _hint_requests_time(hint_words):
                continue
            fill = getattr(node, "fill_rate", 1.0)
            if fill < 0.02:
                continue
            if total_count >= 20 and unique_count <= 1:
                continue
            candidates.append((candidate_source, candidate_col, node, base, fill))

    mojo_name_scores: dict[str, tuple[float, float]] = {}
    if "string_similarity" in planner.mojo_engines and candidates:
        unique_cols = list({candidate_col for _, candidate_col, _, _, _ in candidates})
        mojo_result = planner._call_mojo(
            {
                "engine_type": "string_similarity",
                "hint_words": hint_words,
                "columns": unique_cols,
                "threshold": 0.0,
            }
        )
        if mojo_result and "matches" in mojo_result:
            for match in mojo_result["matches"]:
                mojo_name_scores[match["column"]] = (match["fuzzy"], match["acronym"])

    best_src, best_col, best_score = src, col, score
    for candidate_source, candidate_col, _node, base, fill in candidates:
        if candidate_col in mojo_name_scores:
            fuzzy, acro = mojo_name_scores[candidate_col]
        else:
            fuzzy, acro, _ = _dimension_semantic_evidence(hint_words, candidate_col, [])

        prof_info = planner.profiles.get(candidate_source, {}).get(candidate_col, {})
        sample_vals = prof_info.get("strings", [])[:30]
        val_sem = _value_semantic_score(hint_words, sample_vals)
        col_tokens = _semantic_token_set(candidate_col)
        source_tokens = _source_token_set(candidate_source)
        query_cov = len(hint_token_set & col_tokens) / max(len(hint_token_set), 1)
        col_cov = len(hint_token_set & col_tokens) / max(len(col_tokens), 1)
        exact_cover = min(query_cov, col_cov)
        source_bonus = 0.22 if hint_token_set & source_tokens else 0.0

        if (
            len(hint_words) >= 2
            and max(query_cov, col_cov) < 0.50
            and acro < 0.50
            and source_bonus <= 0.0
        ):
            continue
        if (
            len(hint_words) == 1
            and query_cov == 0.0
            and acro < 0.50
            and fuzzy < 0.55
            and source_bonus <= 0.0
        ):
            continue

        name_sig = max(acro * 0.50, fuzzy * 0.70, exact_cover * 1.05)
        exact_bonus = 0.0
        if exact_cover >= 0.95:
            exact_bonus = 0.55
        elif query_cov >= 0.60 and col_cov >= 0.45:
            exact_bonus = 0.18
        if (
            preferred_source
            and candidate_source == preferred_source
            and query_cov >= 0.95
            and col_cov >= 0.66
        ):
            exact_bonus += 0.22
        aug_score = (base + name_sig + val_sem) * max(fill, 0.0)
        pref_aug = (
            pref_bonus if (preferred_source and candidate_source == preferred_source) else 0.0
        )
        if not hinted_sources and preferred_source and candidate_source == preferred_source:
            pref_aug += 0.18
        unique_count = prof_info.get("unique_count", 0)
        total_count = prof_info.get("total_count", 0)
        low_card_penalty = 0.0
        if total_count >= 20 and unique_count <= 3 and exact_cover < 0.95:
            low_card_penalty += 0.18
        elif total_count >= 20 and unique_count <= 5 and exact_cover < 0.60:
            low_card_penalty += 0.08
        if hinted_sources and candidate_source not in hinted_sources:
            low_card_penalty += 0.22

        aug_score += pref_aug + exact_bonus + source_bonus - low_card_penalty

        if aug_score > best_score:
            best_src, best_col, best_score = candidate_source, candidate_col, aug_score
            steps.append(
                f"[fuzzy/acro/val] {candidate_source}.{candidate_col}  "
                f"fuzzy={fuzzy:.2f}  acro={acro:.2f}  "
                f"val_sem={val_sem:.3f}  score={aug_score:.3f}"
            )

    return best_src, best_col, best_score


def apply_cardinality_filter(
    planner: Any,
    src: str,
    col: str,
    score: float,
    *,
    dim_hints: list[str],
    preferred_source: str | None,
    pref_bonus: float,
    resolve_group_column_fn: Callable[[list[str], str, Any], tuple[str, float]],
    resolve_group_column_graph_fn: Callable[[list[str], str, Any], tuple[str, str, float]],
) -> tuple[str, str, float]:
    if not src or not col:
        return src, col, score

    info = planner.profiles.get(src, {}).get(col, {})
    unique_count = info.get("unique_count", 99)
    total_count = info.get("total_count", 1)

    if total_count >= 20 and unique_count <= 1:
        saved = planner.graph.get(src, {}).get(col)
        if saved is not None:
            del planner.graph[src][col]

        next_src, next_col, next_score = resolve_group_column_graph_fn(
            dim_hints,
            preferred_source or "",
            planner.graph,
        )
        if preferred_source and preferred_source in planner.graph:
            preferred_col, preferred_score = resolve_group_column_fn(
                dim_hints,
                preferred_source,
                planner.graph,
            )
            if preferred_col and preferred_score + pref_bonus >= next_score:
                next_src, next_col, next_score = (
                    preferred_source,
                    preferred_col,
                    preferred_score + pref_bonus,
                )

        planner.graph[src][col] = saved

        if next_src and next_col:
            return next_src, next_col, next_score

    return src, col, score


def same_source_dimension_candidate(
    planner: Any,
    source: str,
    hint: str,
    *,
    category_role: Any,
    identifier_role: Any,
    text_role: Any,
    time_role: Any,
) -> tuple[str, str, float, list[str]]:
    if source not in planner.graph:
        return "", "", 0.0, []

    hint_words, hint_token_set = dimension_hint_words(hint)
    best_src, best_col, best_score = "", "", 0.0
    steps: list[str] = []

    for col, node in planner.graph[source].items():
        prof = planner.profiles.get(source, {}).get(col, {})
        unique_count = prof.get("unique_count", 0)
        total_count = prof.get("total_count", 0)
        is_low_card_numeric = bool(
            node.is_numeric
            and total_count >= 1
            and 1 < unique_count <= max(12, int(total_count * 0.05))
        )
        base = {
            category_role: 0.50,
            text_role: 0.30,
            time_role: 0.50,
            identifier_role: 0.30,
        }.get(
            node.role,
            0.20 if not node.is_numeric else (0.16 if is_low_card_numeric else 0.0),
        )
        if base == 0.0:
            continue
        if node.role == time_role and not _hint_requests_time(hint_words):
            continue
        fill = prof.get("fill_rate", node.fill_rate)
        if fill < 0.02:
            continue

        col_tokens = _semantic_token_set(col)
        if not col_tokens:
            continue
        query_cov = len(hint_token_set & col_tokens) / max(len(hint_token_set), 1)
        col_cov = len(hint_token_set & col_tokens) / max(len(col_tokens), 1)
        exact_cover = min(query_cov, col_cov)
        fuzzy, acro, val_sem = _dimension_semantic_evidence(
            hint_words,
            col,
            prof.get("strings", [])[:30],
        )
        if query_cov < 0.60 and acro < 0.80 and fuzzy < 0.55:
            continue
        if col_cov < 0.40 and acro < 0.95:
            continue

        score = (base + max(fuzzy * 0.70, exact_cover * 1.05, acro * 0.50) + val_sem) * max(
            fill, 0.0
        )
        score += 0.40
        if score > best_score:
            best_src, best_col, best_score = source, col, round(score, 3)
            steps = [
                "[resolve_group/self_correct_same_source] "
                f"'{hint}' → {source}.{col}  score={best_score:.3f}"
            ]

    return best_src, best_col, best_score, steps
