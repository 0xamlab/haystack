"""Manual Python reference for rerank_eval.mojo."""

from __future__ import annotations

import math


def _min_int(a: int, b: int) -> int:
    return a if a < b else b


def _is_relevant(value: int) -> bool:
    return value > 0


def _clamp_non_negative(value: float) -> float:
    return value if value >= 0.0 else 0.0


def _discount(rank_index: int) -> float:
    return math.log(float(rank_index + 2))


def precision_at_k(relevance: list[int], k: int) -> float:
    if k <= 0 or not relevance:
        return 0.0
    limit = _min_int(k, len(relevance))
    hits = sum(1 for item in relevance[:limit] if _is_relevant(item))
    return float(hits) / float(limit)


def recall_at_k(relevance: list[int], total_relevant: int, k: int) -> float:
    if total_relevant <= 0 or k <= 0 or not relevance:
        return 0.0
    limit = _min_int(k, len(relevance))
    hits = sum(1 for item in relevance[:limit] if _is_relevant(item))
    return float(hits) / float(total_relevant)


def hit_rate_at_k(relevance: list[int], k: int) -> float:
    if k <= 0 or not relevance:
        return 0.0
    limit = _min_int(k, len(relevance))
    return 1.0 if any(_is_relevant(item) for item in relevance[:limit]) else 0.0


def mrr_at_k(relevance: list[int], k: int) -> float:
    if k <= 0 or not relevance:
        return 0.0
    limit = _min_int(k, len(relevance))
    for index, item in enumerate(relevance[:limit]):
        if _is_relevant(item):
            return 1.0 / float(index + 1)
    return 0.0


def map_at_k(relevance: list[int], k: int) -> float:
    if k <= 0 or not relevance:
        return 0.0
    limit = _min_int(k, len(relevance))
    hits = 0
    precision_sum = 0.0
    for index, item in enumerate(relevance[:limit]):
        if _is_relevant(item):
            hits += 1
            precision_sum += float(hits) / float(index + 1)
    if hits == 0:
        return 0.0
    return precision_sum / float(hits)


def ndcg_at_k(gains: list[float], ideal_gains: list[float], k: int) -> float:
    if k <= 0 or not gains or not ideal_gains:
        return 0.0
    limit = _min_int(k, len(gains))
    ideal_limit = _min_int(k, len(ideal_gains))
    dcg = 0.0
    for index, gain in enumerate(gains[:limit]):
        dcg += _clamp_non_negative(gain) / _discount(index)
    ideal_dcg = 0.0
    for index, gain in enumerate(ideal_gains[:ideal_limit]):
        ideal_dcg += _clamp_non_negative(gain) / _discount(index)
    if ideal_dcg <= 0.0:
        return 0.0
    return dcg / ideal_dcg


def pairwise_margin_accuracy(
    positive_scores: list[float],
    negative_scores: list[float],
    margin: float,
) -> float:
    limit = _min_int(len(positive_scores), len(negative_scores))
    if limit == 0:
        return 0.0
    wins = 0
    for index in range(limit):
        if positive_scores[index] >= negative_scores[index] + margin:
            wins += 1
    return float(wins) / float(limit)


def score_separation(positive_scores: list[float], negative_scores: list[float]) -> float:
    if not positive_scores or not negative_scores:
        return 0.0
    pos_mean = sum(positive_scores) / float(len(positive_scores))
    neg_mean = sum(negative_scores) / float(len(negative_scores))
    return pos_mean - neg_mean


def latency_weighted_quality(
    quality_score: float,
    latency_ms: float,
    target_latency_ms: float,
) -> float:
    if target_latency_ms <= 0.0:
        return 0.0
    quality = _clamp_non_negative(quality_score)
    latency = _clamp_non_negative(latency_ms)
    return quality / (1.0 + latency / target_latency_ms)
