from __future__ import annotations

import functools
import math
import statistics
from typing import Any

from .data_map_matching_common import (
    GENERIC_MATCH_TOKENS,
    IDENTIFIER_TOKENS,
    _common_prefix_length,
    _format_token_reason,
    _identifier_concepts,
    _identifier_tokens,
    _is_identifier_dominant,
    _normalize,
)


def _ngrams(value: str, n: int = 2) -> set[str]:
    """Character n-grams for fuzzy matching."""
    padded = f"_{value}_"
    return {padded[index : index + n] for index in range(len(padded) - n + 1)}


def _dice_coefficient(a: str, b: str, n: int = 2) -> float:
    """Sørensen-Dice coefficient on character bigrams [0, 1]."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ngrams_a = _ngrams(a, n)
    ngrams_b = _ngrams(b, n)
    intersection = len(ngrams_a & ngrams_b)
    return 2 * intersection / (len(ngrams_a) + len(ngrams_b))


@functools.lru_cache(maxsize=131072)
def _semantic_similarity_cached(name_a: str, name_b: str) -> tuple[float, tuple[str, ...]]:
    """Compute semantic similarity between two field names."""
    if not name_a or not name_b:
        return 0.0, ()

    normalized_a = _normalize(name_a)
    normalized_b = _normalize(name_b)
    reasons: list[str] = []

    if normalized_a == normalized_b:
        return 1.0, ("exact name match",)

    score = 0.0
    tokens_a = set(_identifier_tokens(name_a))
    tokens_b = set(_identifier_tokens(name_b))
    informative_a = tokens_a - GENERIC_MATCH_TOKENS
    informative_b = tokens_b - GENERIC_MATCH_TOKENS
    shared_tokens = informative_a & informative_b
    generic_overlap = (tokens_a & tokens_b) - shared_tokens
    generic_only_overlap = bool(generic_overlap) and not shared_tokens
    if shared_tokens:
        token_coverage = len(shared_tokens) / max(min(len(informative_a), len(informative_b)), 1)
        token_score = min(0.95, 0.72 + token_coverage * 0.2 + 0.03 * min(len(shared_tokens), 3))
        score = max(score, token_score)
        reasons.append(_format_token_reason("token overlap", shared_tokens))
        smaller_informative, larger_informative = sorted(
            (informative_a, informative_b),
            key=len,
        )
        if len(smaller_informative) >= 2 and smaller_informative <= larger_informative:
            subset_score = min(0.97, 0.9 + 0.02 * min(len(smaller_informative), 3))
            score = max(score, subset_score)
            reasons.append(_format_token_reason("full token coverage", smaller_informative))

    shared_concepts = set(_identifier_concepts(name_a) & _identifier_concepts(name_b))
    if shared_concepts:
        concept_coverage = len(shared_concepts) / max(
            min(len(_identifier_concepts(name_a)), len(_identifier_concepts(name_b))),
            1,
        )
        concept_score = min(
            0.9,
            0.7 + concept_coverage * 0.16 + 0.02 * min(len(shared_concepts), 3),
        )
        score = max(score, concept_score)
        reasons.append(_format_token_reason("semantic concept", shared_concepts))

    bigram_similarity = _dice_coefficient(normalized_a, normalized_b)
    if (
        bigram_similarity > 0.5
        and not generic_only_overlap
        and min(len(normalized_a), len(normalized_b)) >= 5
        and _common_prefix_length(normalized_a, normalized_b) >= 2
    ):
        score = max(score, bigram_similarity)
        reasons.append(f"string similarity ({bigram_similarity:.0%})")

    if (
        not generic_only_overlap
        and min(len(normalized_a), len(normalized_b)) >= 4
        and (normalized_a in normalized_b or normalized_b in normalized_a)
    ):
        shorter, longer = sorted((normalized_a, normalized_b), key=len)
        if len(shorter) / len(longer) >= 0.72:
            score = max(score, 0.80)
            reasons.append("name substring match")

    if score == 0.0 and generic_overlap:
        generic_score = min(0.34, 0.2 + 0.04 * len(generic_overlap))
        score = max(score, generic_score)
        reasons.append(_format_token_reason("generic token overlap", generic_overlap))

    identifier_penalty_applied = False
    if score > 0.0 and _is_identifier_dominant(tokens_a) != _is_identifier_dominant(tokens_b):
        if not (tokens_a & IDENTIFIER_TOKENS and tokens_b & IDENTIFIER_TOKENS):
            score *= 0.84
            identifier_penalty_applied = True

    deduped_reasons = list(dict.fromkeys(reasons))
    if identifier_penalty_applied:
        deduped_reasons.append("identifier label penalty")
    return min(score, 1.0), tuple(deduped_reasons)


def _semantic_similarity(name_a: str, name_b: str) -> tuple[float, list[str]]:
    score, reasons = _semantic_similarity_cached(name_a, name_b)
    return score, list(reasons)


def _value_distribution_similarity(
    values_a: list[float],
    values_b: list[float],
) -> tuple[float, list[str]]:
    """Compare statistical distributions of two numeric field value sets."""
    if len(values_a) < 3 or len(values_b) < 3:
        return 0.0, []

    reasons: list[str] = []
    score = 0.0

    mean_a = statistics.mean(values_a)
    mean_b = statistics.mean(values_b)
    std_a = statistics.stdev(values_a) if len(values_a) > 1 else 0.0
    std_b = statistics.stdev(values_b) if len(values_b) > 1 else 0.0

    if mean_a > 0 and mean_b > 0:
        magnitude_ratio = max(mean_a, mean_b) / max(min(mean_a, mean_b), 1)
        if magnitude_ratio < 3:
            magnitude_similarity = 1 - (magnitude_ratio - 1) / 2
            score = max(score, magnitude_similarity * 0.4)
            reasons.append(f"similar value range ({magnitude_similarity:.0%})")

    coefficient_of_variation_a = std_a / max(abs(mean_a), 1)
    coefficient_of_variation_b = std_b / max(abs(mean_b), 1)
    cv_diff = abs(coefficient_of_variation_a - coefficient_of_variation_b)
    if cv_diff < 0.2:
        score = max(score, 0.35)
        reasons.append("same spread pattern")

    set_a = {round(value, 2) for value in values_a[:200]}
    set_b = {round(value, 2) for value in values_b[:200]}
    if set_a and set_b:
        overlap = len(set_a & set_b) / max(len(set_a | set_b), 1)
        if overlap > 0.3:
            score = max(score, overlap)
            reasons.append(f"value overlap ({overlap:.0%})")

    return min(score, 1.0), reasons


def _match_tier(score: float) -> str:
    """Categorise a match score into action tiers."""
    if score >= 0.85:
        return "strong"
    if score >= 0.60:
        return "suggested"
    if score >= 0.40:
        return "weak"
    return "rejected"


def _build_match_reasons(match: dict[str, Any]) -> list[str]:
    """Convert Mojo sub-scores into human-readable reasons."""
    reasons: list[str] = []
    name_score = match.get("name_score", 0.0)
    type_score = match.get("type_score", 0.0)
    polarity_score = match.get("polarity_score", 0.0)
    distribution_score = match.get("dist_score", 0.0)
    if name_score >= 0.99:
        reasons.append("exact name match")
    elif name_score >= 0.70:
        reasons.append(f"name similarity ({name_score:.0%})")
    if type_score >= 0.90:
        reasons.append("same semantic type")
    elif type_score >= 0.50:
        reasons.append("compatible types")
    if distribution_score >= 0.50:
        reasons.append("similar distribution")
    if polarity_score >= 0.90 and not reasons:
        reasons.append("same polarity")
    return reasons or [f"combined score {match.get('score', 0):.2f}"]


def _build_matcher_input(
    python_profile: dict[str, dict[str, Any]],
    mojo_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build columns_a / columns_b list for Mojo column matcher from profiler output."""
    mojo_fields = mojo_profile.get("profiles", {}) if mojo_profile else {}
    result: list[dict[str, Any]] = []
    for field, info in python_profile.items():
        mojo_field = mojo_fields.get(field, {})
        result.append(
            {
                "name": field,
                "semantic_type": mojo_field.get(
                    "semantic_type",
                    "metric" if info["is_numeric"] else "category",
                ),
                "polarity": mojo_field.get("polarity", 0),
                "distribution": mojo_field.get("distribution", ""),
                "mean": info.get("mean", 0.0),
                "std": info.get("std", 0.0),
            }
        )
    return result


def _hungarian_greedy(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Greedy bipartite matching: each column A and each column B gets at most one partner.
    Sorts by score descending and assigns first-come-first-served.
    """
    used_a: set[str] = set()
    used_b: set[str] = set()
    result: list[dict[str, Any]] = []
    for match in sorted(matches, key=lambda item: item["score"], reverse=True):
        field_a, field_b = match["field_a"], match["field_b"]
        if field_a not in used_a and field_b not in used_b:
            used_a.add(field_a)
            used_b.add(field_b)
            result.append(match)
    return result


def _pearson_correlation(a: list[float], b: list[float]) -> float:
    count = len(a)
    if count < 3:
        return 0.0
    mean_a = sum(a) / count
    mean_b = sum(b) / count
    numerator = sum((a[index] - mean_a) * (b[index] - mean_b) for index in range(count))
    denominator_a = math.sqrt(sum((value - mean_a) ** 2 for value in a))
    denominator_b = math.sqrt(sum((value - mean_b) ** 2 for value in b))
    if denominator_a < 1e-10 or denominator_b < 1e-10:
        return 0.0
    return numerator / (denominator_a * denominator_b)


def _check_approx(predicted: list[float], actual: list[float], threshold: float = 0.05) -> bool:
    """True if predicted ≈ actual in >= 85 percent of non-zero rows."""
    count = min(len(predicted), len(actual))
    if count < 3:
        return False
    matches = 0
    valid = 0
    for index in range(count):
        if abs(actual[index]) < 1e-9:
            continue
        valid += 1
        if abs(predicted[index] - actual[index]) / abs(actual[index]) <= threshold:
            matches += 1
    return valid >= 3 and matches / valid >= 0.85


def _detect_derived_relationships(
    records: list[dict[str, Any]],
    numeric_fields: list[str],
    source: str = "",
    sample_size: int = 500,
    min_confidence: float = 0.70,
) -> list[dict[str, Any]]:
    """
    Detect A×B≈C and A+B≈C formulaic relationships between numeric columns.

    No arbitrary row cap — every relationship above min_confidence is returned.
    The O(n^3) triple scan is bounded by numeric column count per source, not row count.
    """
    count = min(len(records), sample_size)
    if count < 3 or len(numeric_fields) < 3:
        return []

    columns: dict[str, list[float]] = {}
    for field in numeric_fields:
        values: list[float] = []
        for index in range(count):
            value = records[index].get(field)
            try:
                values.append(float(value))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                values.append(0.0)
        columns[field] = values

    seen: set[frozenset[str]] = set()
    results: list[dict[str, Any]] = []

    for field_result in numeric_fields:
        values_c = columns[field_result]
        if all(abs(value) < 1e-9 for value in values_c):
            continue

        for index_a, field_a in enumerate(numeric_fields):
            if field_a == field_result:
                continue
            values_a = columns[field_a]

            for index_b in range(index_a + 1, len(numeric_fields)):
                field_b = numeric_fields[index_b]
                if field_b == field_result:
                    continue
                triple = frozenset([field_a, field_b, field_result])
                if triple in seen:
                    continue
                seen.add(triple)

                values_b = columns[field_b]

                products = [values_a[index] * values_b[index] for index in range(count)]
                if _check_approx(products, values_c):
                    confidence = abs(_pearson_correlation(products, values_c))
                    if confidence >= min_confidence:
                        results.append(
                            {
                                "formula": f"{field_result} = {field_a} × {field_b}",
                                "source": source,
                                "field_result": field_result,
                                "field_a": field_a,
                                "field_b": field_b,
                                "operation": "multiply",
                                "confidence": round(confidence, 3),
                            }
                        )

                sums = [values_a[index] + values_b[index] for index in range(count)]
                if _check_approx(sums, values_c):
                    confidence = abs(_pearson_correlation(sums, values_c))
                    if confidence >= min_confidence:
                        results.append(
                            {
                                "formula": f"{field_result} = {field_a} + {field_b}",
                                "source": source,
                                "field_result": field_result,
                                "field_a": field_a,
                                "field_b": field_b,
                                "operation": "add",
                                "confidence": round(confidence, 3),
                            }
                        )

    results.sort(key=lambda relationship: relationship["confidence"], reverse=True)
    return results
