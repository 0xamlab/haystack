from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

_HINT_SYMBOL_MAP = {"%": "percent", "$": "dollar", "#": "number"}
_COLUMN_SYMBOL_MAP = {
    **_HINT_SYMBOL_MAP,
    "€": "euro",
    "£": "pound",
}
_ResolveMetricColumnFn = Callable[
    [Any, set[str], Any, str | None],
    tuple[str, str, float, list[dict[str, Any]]],
]
_MetricCandidateScoreFn = Callable[[Any, set[str], str, str, Any], tuple[float, Any, Any]]


def _normalized_metric_tokens(value: str, symbol_map: dict[str, str]) -> set[str]:
    normalized = value.lower()
    for symbol, word in symbol_map.items():
        normalized = normalized.replace(symbol, f" {word} ")
    return set(re.findall(r"[a-z0-9]+", normalized))


def resolve_from_query_hints(
    planner: Any,
    *,
    hint: str,
    preferred_source: str | None,
    agg: str,
    metric_tokens_fn: Callable[[str], set[str]],
    metric_concepts_fn: Callable[[set[str]], set[str]],
) -> tuple[str, str, float, str] | None:
    hint_tokens = metric_tokens_fn(hint)
    hint_concepts = metric_concepts_fn(hint_tokens)
    best_src, best_col, best_conf, best_role = "", "", 0.0, "metric"
    preferred_best: tuple[str, str, float, str] | None = None

    if agg in ("sum", "count"):
        role_order = ("derived_measure", "base_measure", "unit_measure", "ratio", "metric")
    elif agg == "avg":
        role_order = ("unit_measure", "ratio", "derived_measure", "base_measure", "metric")
    else:
        role_order = ("derived_measure", "unit_measure", "base_measure", "ratio", "metric")

    role_rank = {role: index for index, role in enumerate(role_order)}
    sources = (
        [preferred_source] + [src for src in planner._query_hints_by_src if src != preferred_source]
        if preferred_source
        else list(planner._query_hints_by_src.keys())
    )

    for src in sources:
        hints_list = planner._query_hints_by_src.get(src, [])
        for hint_entry in hints_list:
            role = hint_entry.get("metric_role", "metric")
            for col_meta in hint_entry.get("columns", []):
                col = col_meta.get("name", "")
                fill = col_meta.get("fill_rate", 1.0)
                if fill < 0.02:
                    continue

                col_tokens = metric_tokens_fn(col)
                if not col_tokens:
                    continue
                col_concepts = metric_concepts_fn(col_tokens)
                forward_overlap = len(hint_tokens & col_tokens) / len(col_tokens)
                backward_overlap = len(hint_tokens & col_tokens) / max(len(hint_tokens), 1)
                name_overlap = (forward_overlap + backward_overlap) / 2
                concept_overlap = (
                    len(hint_concepts & col_concepts) / max(len(hint_concepts), 1)
                    if hint_concepts
                    else 0.0
                )
                role_bonus = (
                    max(
                        0,
                        (len(role_order) - role_rank.get(role, len(role_order))) / len(role_order),
                    )
                    * 0.20
                )
                formula_bonus = 0.10 if col_meta.get("formula") else 0.0
                pref_bonus = 0.18 if preferred_source and src == preferred_source else 0.0

                identifier_tokens = {
                    "id",
                    "identifier",
                    "number",
                    "no",
                    "code",
                    "key",
                    "person",
                    "rep",
                }
                measure_tokens = {
                    "price",
                    "cost",
                    "amount",
                    "total",
                    "extended",
                    "value",
                    "revenue",
                    "sales",
                    "qty",
                    "quantity",
                }
                identifier_density = len(identifier_tokens & col_tokens) / max(len(col_tokens), 1)
                combined_tokens = col_tokens | col_concepts
                measure_density = len(measure_tokens & combined_tokens) / max(
                    len(combined_tokens),
                    1,
                )
                hint_requests_identifier = bool(identifier_tokens & (hint_tokens | hint_concepts))
                hint_requests_measure = bool(measure_tokens & (hint_tokens | hint_concepts))

                typed_penalty = 0.0
                if "unit" in hint_concepts and "total" in col_concepts:
                    typed_penalty -= 0.16
                if "total" in hint_concepts and "unit" in col_concepts:
                    typed_penalty -= 0.14
                if (
                    "overhead" in hint_concepts
                    and "overhead" not in col_concepts
                    and {"cost", "price"} & col_concepts
                ):
                    typed_penalty -= 0.22
                if (
                    "total" in hint_concepts
                    and role == "base_measure"
                    and not ({"total", "price", "cost"} & col_concepts)
                ):
                    typed_penalty -= 0.18
                if "sales" in hint_tokens and {"person", "rep", "number", "no", "id"} & col_tokens:
                    typed_penalty -= 0.24
                if (
                    {"sales", "revenue"} & hint_tokens
                    and "cost" in col_concepts
                    and "price" not in col_concepts
                    and not {"amount", "revenue", "sales", "value"} & combined_tokens
                ):
                    typed_penalty -= 0.24
                if {"sales", "revenue"} & hint_tokens and {
                    "price",
                    "amount",
                    "extended",
                    "revenue",
                    "sales",
                    "value",
                } & combined_tokens:
                    typed_penalty += 0.14
                    if role == "derived_measure":
                        typed_penalty += 0.04
                    if col_meta.get("formula"):
                        typed_penalty += 0.04
                if agg in ("sum", "avg") and not hint_requests_identifier:
                    typed_penalty -= max(identifier_density - 0.35 * measure_density, 0.0) * 0.90
                if (
                    agg in ("sum", "avg")
                    and hint_requests_measure
                    and role in {"derived_measure", "unit_measure", "base_measure"}
                ):
                    typed_penalty += measure_density * 0.18

                score = (
                    0.40 * name_overlap
                    + concept_overlap * 0.18
                    + role_bonus
                    + formula_bonus
                    + pref_bonus
                    + fill * 0.10
                    + typed_penalty
                )

                preferred_signal = max(
                    name_overlap,
                    concept_overlap,
                    measure_density if hint_requests_measure else 0.0,
                )
                if (
                    preferred_source
                    and src == preferred_source
                    and preferred_signal >= 0.18
                    and score >= 0.25
                    and (preferred_best is None or score > preferred_best[2])
                ):
                    preferred_best = (src, col, score, role)

                if score > best_conf:
                    best_conf = score
                    best_src = src
                    best_col = col
                    best_role = role

    if preferred_best is not None:
        pref_src, pref_col, pref_conf, pref_role = preferred_best
        same_metric_name = bool(best_col and pref_col and pref_col == best_col)
        hint_requests_measure = bool(
            {
                "price",
                "cost",
                "amount",
                "total",
                "extended",
                "value",
                "revenue",
                "sales",
                "qty",
                "quantity",
            }
            & (hint_tokens | hint_concepts)
        )
        if (
            pref_conf + 0.02 >= best_conf
            or (same_metric_name and pref_conf >= best_conf - 0.18)
            or (hint_requests_measure and pref_conf >= best_conf - 0.12)
        ):
            return pref_src, pref_col, round(pref_conf, 3), pref_role

    if best_src and best_conf > 0.15:
        return best_src, best_col, round(best_conf, 3), best_role
    return None


def python_field_map(hint: str) -> dict[str, Any]:
    lower_hint = hint.lower()
    if any(
        token in lower_hint for token in ("rate", "pct", "percent", "ratio", "margin_%", "share")
    ):
        unit = "percentage"
    elif any(
        token in lower_hint
        for token in (
            "revenue",
            "price",
            "cost",
            "amount",
            "sales",
            "margin",
            "spend",
            "invoice",
            "value",
            "ext",
            "total",
        )
    ):
        unit = "currency"
    elif any(token in lower_hint for token in ("qty", "quantity", "count", "units", "volume")):
        unit = "count"
    elif any(token in lower_hint for token in ("days", "time", "duration", "lead", "delivery")):
        unit = "time"
    else:
        unit = "unknown"

    polarity = (
        -1
        if any(token in lower_hint for token in ("cost", "expense", "loss", "return", "refund"))
        else 1
    )
    distribution = "lognormal" if unit in ("currency", "count") else "normal"
    if unit == "currency":
        semantic_type = "currency"
    elif unit == "count":
        semantic_type = "count"
    elif unit == "percentage":
        semantic_type = "percentage"
    else:
        semantic_type = "metric"

    return {
        "polarity": polarity,
        "distribution": distribution,
        "unit": unit,
        "semantic_type": semantic_type,
        "confidence": 0.60,
    }


def field_map_hint(
    planner: Any,
    *,
    hint: str,
    preferred_source: str | None,
    python_field_map_fn: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    if hint in planner._field_map_cache:
        cached = planner._field_map_cache[hint]
        if isinstance(cached, dict):
            return cached
        return {}

    best_col_vals: list[float] = []
    best_overlap = 0.0
    hint_tokens = set(re.findall(r"[a-z0-9]+", hint.lower()))
    sources = (
        [preferred_source] + [src for src in planner.profiles if src != preferred_source]
        if preferred_source
        else list(planner.profiles.keys())
    )

    for src in sources:
        if src not in planner.profiles:
            continue
        for col, info in planner.profiles[src].items():
            if not info.get("is_numeric") or not info.get("numeric"):
                continue
            col_tokens = set(re.findall(r"[a-z0-9]+", col.lower()))
            if not col_tokens:
                continue
            forward_overlap = len(hint_tokens & col_tokens) / len(col_tokens)
            backward_overlap = len(hint_tokens & col_tokens) / max(len(hint_tokens), 1)
            overlap = (forward_overlap + backward_overlap) / 2
            if overlap > best_overlap:
                best_overlap = overlap
                best_col_vals = info["numeric"][:30]

    if "field_map" in planner.mojo_engines and best_col_vals:
        result = planner._call_mojo(
            {
                "engine_type": "field_map",
                "data": {hint: best_col_vals},
            }
        )
        if isinstance(result, dict):
            field_analysis = result.get("field_analysis")
            if isinstance(field_analysis, dict):
                analysis = field_analysis.get(hint, {})
            else:
                analysis = {}
            if isinstance(analysis, dict):
                planner._field_map_cache[hint] = analysis
                return analysis

    fallback_analysis: dict[str, Any] = python_field_map_fn(hint)
    planner._field_map_cache[hint] = fallback_analysis
    return fallback_analysis


def resolve_metric_vector_short_circuit(
    planner: Any,
    *,
    hint: str,
    preferred_source: str | None,
    sem_type: str,
    steps: list[str],
    derived_measure_role: Any,
) -> tuple[str, str, float, Any] | None:
    ensure_ready = getattr(planner, "_ensure_vector_resolver_ready", None)
    if callable(ensure_ready):
        ensure_ready()
    if planner._vector_resolver is None:
        return None

    from mojo.engine.vector_kernels.resolver import ResolverOutcome

    semantic_role_map = {
        "currency": "derived_measure",
        "amount": "derived_measure",
        "count": "base_measure",
        "quantity": "base_measure",
        "percentage": "ratio",
        "ratio": "ratio",
    }
    hint_tokens = set(re.findall(r"[a-z0-9]+", hint.lower()))
    role_hint = semantic_role_map.get(sem_type, "derived_measure")
    if hint_tokens & {"unit", "rate", "per"}:
        role_hint = "unit_measure"

    result = planner._vector_resolver.resolve(hint, preferred_source, role_hint)
    if result is None:
        return None

    if result.outcome == ResolverOutcome.META_QUERY:
        try:
            from mojo.engine.vector_kernels.meta_executor import (
                interpret_meta_query,
                meta_op_to_sql_fragment,
            )

            meta_op = interpret_meta_query(hint, result)
            steps.append(
                f"[meta_executor] {meta_op.op_type.value.upper()}  "
                f"entity={meta_op.entity!r}  "
                f"col={meta_op.column or 'N/A'}  "
                f"sql_expr={meta_op_to_sql_fragment(meta_op)}  "
                f"reason={result.reason.value}"
            )
        except Exception:
            steps.append(
                f"[vector_resolver] META_QUERY hint={hint!r}  "
                f"reason={result.reason.value}  score={result.score:.3f}"
            )
        return None

    if result.outcome == ResolverOutcome.WEAK_MATCH:
        weak_is_metric = sem_type in ("currency", "amount", "ratio", "percentage")
        if weak_is_metric:
            return None
        node = planner.graph.get(result.source, {}).get(result.column)
        role = node.role if node else derived_measure_role
        steps.append(
            f"[vector_resolver/weak] {result.source}.{result.column}  "
            f"score={result.score:.3f}  gap={result.confidence_gap:.3f}"
        )
        return result.source, result.column, result.score, role

    if result.outcome == ResolverOutcome.COLUMN_MATCH:
        node = planner.graph.get(result.source, {}).get(result.column)
        role = node.role if node else derived_measure_role
        steps.append(
            f"[vector_resolver] {result.source}.{result.column}  "
            f"score={result.score:.3f}  gap={result.confidence_gap:.3f}  "
            f"tok_overlap={result.token_overlap}"
        )
        return result.source, result.column, result.score, role

    return None


def resolve_metric_column_match(
    planner: Any,
    *,
    hint: str,
    sem_type: str,
    polarity: int,
    dist: str,
    preferred_source: str | None,
    steps: list[str],
    metric_role: Any,
    derived_measure_role: Any,
    base_measure_role: Any,
    unit_measure_role: Any,
    ratio_role: Any,
) -> tuple[str, str, float, Any] | None:
    if "column_match" not in planner.mojo_engines:
        return None

    best_src, best_col, best_conf, best_role = "", "", 0.0, metric_role
    query_col = {
        "name": hint,
        "semantic_type": sem_type,
        "polarity": polarity,
        "distribution": dist,
        "mean": 0.0,
        "std": 0.0,
    }
    sources = (
        [preferred_source] + [src for src in planner.graph if src != preferred_source]
        if preferred_source
        else list(planner.graph.keys())
    )
    hint_tokens = _normalized_metric_tokens(hint, _HINT_SYMBOL_MAP)

    for src in sources:
        if src not in planner.profiles:
            continue

        candidates = []
        for col, info in planner.profiles[src].items():
            if not info.get("is_numeric"):
                continue
            if info.get("fill_rate", 1.0) < 0.02:
                continue
            mojo_profile = planner._mojo_profiles.get(src, {}).get(col, {})
            candidates.append(
                {
                    "name": col,
                    "semantic_type": mojo_profile.get("semantic_type", ""),
                    "polarity": 1,
                    "distribution": "lognormal",
                    "mean": info.get("mean", 0.0),
                    "std": info.get("std", 0.0),
                }
            )
        if not candidates:
            continue

        result = planner._call_mojo(
            {
                "engine_type": "column_match",
                "source_a": "_query",
                "source_b": src,
                "columns_a": [query_col],
                "columns_b": candidates,
                "min_confidence": 0.10,
            }
        )
        if not (result and result.get("matches")):
            continue

        for match in result["matches"]:
            col_name = match.get("field_b", "")
            score = float(match.get("score", 0.0))
            col_tokens = _normalized_metric_tokens(col_name, _COLUMN_SYMBOL_MAP)
            if col_tokens:
                forward_similarity = len(hint_tokens & col_tokens) / len(col_tokens)
                backward_similarity = len(hint_tokens & col_tokens) / max(len(hint_tokens), 1)
                name_similarity = (forward_similarity + backward_similarity) / 2
            else:
                name_similarity = 0.0

            if name_similarity >= 0.80:
                score = max(score, 0.50) + name_similarity * 0.40
            elif name_similarity >= 0.40:
                score += name_similarity * 0.20

            node = planner.graph.get(src, {}).get(col_name)
            role = node.role if node else metric_role
            if name_similarity < 0.70:
                if role == derived_measure_role:
                    score += 0.15
                    if node and node.formula:
                        score += 0.05
                    if node and node.magnitude_class == "large":
                        score += 0.15
                    elif node and node.magnitude_class == "medium":
                        score += 0.06
                elif role in (base_measure_role, unit_measure_role):
                    score += 0.08
                    if node and node.magnitude_class == "large":
                        score += 0.08
                elif role == ratio_role and sem_type in ("percentage", "ratio"):
                    score += 0.12

            if preferred_source and src == preferred_source:
                score += 0.20
            if score > best_conf:
                best_conf = score
                best_src = src
                best_col = col_name
                best_role = role
                steps.append(f"[column_match] {src}.{col_name}  score={score:.3f}  role={role}")

    if best_src and best_conf > 0.10:
        steps.append(
            f"[column_match] SELECTED  {best_src}.{best_col}  "
            f"conf={best_conf:.3f}  role={best_role}"
        )
        return best_src, best_col, round(best_conf, 3), best_role

    return None


def resolve_metric_python_fallback(
    planner: Any,
    *,
    hint: str,
    sem_type: str,
    preferred_source: str | None,
    agg: str,
    steps: list[str],
    metric_role: Any,
    derived_measure_role: Any,
    base_measure_role: Any,
    unit_measure_role: Any,
    ratio_role: Any,
    resolve_metric_column_fn: _ResolveMetricColumnFn,
    metric_candidate_score_fn: _MetricCandidateScoreFn,
) -> tuple[str, str, float, Any, list[str]]:
    hint_tokens = set(re.findall(r"[a-z0-9]+", hint.lower()))
    hint_role_tokens = set(re.findall(r"[a-z0-9]+", hint.lower()))
    if hint_role_tokens & {"unit", "rate", "per"}:
        target_role = unit_measure_role
    elif sem_type == "count":
        target_role = base_measure_role
    elif sem_type in ("percentage", "ratio"):
        target_role = ratio_role
    elif sem_type == "currency":
        target_role = derived_measure_role
    else:
        target_role = derived_measure_role

    src, col, conf, candidates = resolve_metric_column_fn(
        target_role,
        hint_tokens,
        planner.graph,
        preferred_source,
    )
    if src:
        node = planner.graph.get(src, {}).get(col)
        role = node.role if node else metric_role
        if len(candidates) >= 2:
            gap = candidates[0]["confidence"] - candidates[1]["confidence"]
            steps.append(
                "[resolve_metric_column/gap] "
                f"top={candidates[0]['column']} "
                f"second={candidates[1]['column']} gap={gap:.3f}"
            )
        else:
            cross_best_col, cross_best_score = "", float("-inf")
            search_sources = [preferred_source] if preferred_source else list(planner.graph.keys())
            for alt_src in search_sources:
                if alt_src not in planner.graph:
                    continue
                for alt_col, alt_node in planner.graph[alt_src].items():
                    if not alt_node.is_numeric or alt_col == col:
                        continue
                    if alt_node.fill_rate < 0.02:
                        continue
                    alt_score, _, _ = metric_candidate_score_fn(
                        target_role,
                        hint_tokens,
                        alt_src,
                        alt_col,
                        alt_node,
                    )
                    if alt_score > cross_best_score:
                        cross_best_score = alt_score
                        cross_best_col = alt_col
            if cross_best_col:
                gap = conf - cross_best_score
                steps.append(
                    f"[resolve_metric_column/gap] top={col} second={cross_best_col} gap={gap:.3f}"
                )

        steps.append(f"[resolve_metric_column] {src}.{col}  conf={conf:.3f}  role={role}")
        return src, col, conf, role, list(steps)

    if preferred_source:
        fallback_src, fallback_col, fallback_conf, fallback_role, fallback_steps = (
            planner.resolve_metric(hint, None, agg)
        )
        if fallback_src:
            steps.append(
                f"[resolve_metric/preferred_source_miss] broadened search beyond {preferred_source}"
            )
            steps.extend(step for step in fallback_steps if step not in steps)
            return fallback_src, fallback_col, fallback_conf, fallback_role, list(steps)

    return "", "", 0.0, metric_role, list(steps + ["[resolve_metric_column] no match found"])
