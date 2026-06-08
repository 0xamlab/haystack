"""
rerank_eval.mojo — deterministic reranking quality metrics. Zero Python imports.

Public API:
  precision_at_k            — fraction of relevant items in top-k
  recall_at_k               — fraction of all relevant items recovered in top-k
  hit_rate_at_k             — 1 if any relevant item appears in top-k
  mrr_at_k                  — reciprocal rank of first relevant item in top-k
  map_at_k                  — average precision across relevant hits in top-k
  ndcg_at_k                 — discounted cumulative gain normalized by ideal DCG
  pairwise_margin_accuracy  — fraction of positive/negative pairs beating a margin
  score_separation          — mean positive score minus mean negative score
  latency_weighted_quality  — quality score discounted by latency pressure
"""

from std.math import log


fn _min_int(a: Int, b: Int) -> Int:
    return a if a < b else b


fn _is_relevant(value: Int) -> Bool:
    return value > 0


fn _clamp_non_negative(value: Float64) -> Float64:
    if value < 0.0:
        return 0.0
    return value


fn _discount(rank_index: Int) -> Float64:
    return log(Float64(rank_index + 2))


fn precision_at_k(relevance: List[Int], k: Int) -> Float64:
    if k <= 0 or len(relevance) == 0:
        return 0.0
    var limit = _min_int(k, len(relevance))
    var hits = 0
    for i in range(limit):
        if _is_relevant(relevance[i]):
            hits += 1
    return Float64(hits) / Float64(limit)


fn recall_at_k(relevance: List[Int], total_relevant: Int, k: Int) -> Float64:
    if total_relevant <= 0 or k <= 0 or len(relevance) == 0:
        return 0.0
    var limit = _min_int(k, len(relevance))
    var hits = 0
    for i in range(limit):
        if _is_relevant(relevance[i]):
            hits += 1
    return Float64(hits) / Float64(total_relevant)


fn hit_rate_at_k(relevance: List[Int], k: Int) -> Float64:
    if k <= 0 or len(relevance) == 0:
        return 0.0
    var limit = _min_int(k, len(relevance))
    for i in range(limit):
        if _is_relevant(relevance[i]):
            return 1.0
    return 0.0


fn mrr_at_k(relevance: List[Int], k: Int) -> Float64:
    if k <= 0 or len(relevance) == 0:
        return 0.0
    var limit = _min_int(k, len(relevance))
    for i in range(limit):
        if _is_relevant(relevance[i]):
            return 1.0 / Float64(i + 1)
    return 0.0


fn map_at_k(relevance: List[Int], k: Int) -> Float64:
    if k <= 0 or len(relevance) == 0:
        return 0.0
    var limit = _min_int(k, len(relevance))
    var hits = 0
    var precision_sum = 0.0
    for i in range(limit):
        if _is_relevant(relevance[i]):
            hits += 1
            precision_sum += Float64(hits) / Float64(i + 1)
    if hits == 0:
        return 0.0
    return precision_sum / Float64(hits)


fn ndcg_at_k(gains: List[Float64], ideal_gains: List[Float64], k: Int) -> Float64:
    if k <= 0 or len(gains) == 0 or len(ideal_gains) == 0:
        return 0.0
    var limit = _min_int(k, len(gains))
    var ideal_limit = _min_int(k, len(ideal_gains))
    var dcg = 0.0
    for i in range(limit):
        var gain = _clamp_non_negative(gains[i])
        dcg += gain / _discount(i)
    var ideal_dcg = 0.0
    for i in range(ideal_limit):
        var gain = _clamp_non_negative(ideal_gains[i])
        ideal_dcg += gain / _discount(i)
    if ideal_dcg <= 0.0:
        return 0.0
    return dcg / ideal_dcg


fn pairwise_margin_accuracy(
    positive_scores: List[Float64],
    negative_scores: List[Float64],
    margin: Float64,
) -> Float64:
    var limit = _min_int(len(positive_scores), len(negative_scores))
    if limit == 0:
        return 0.0
    var wins = 0
    for i in range(limit):
        if positive_scores[i] >= negative_scores[i] + margin:
            wins += 1
    return Float64(wins) / Float64(limit)


fn score_separation(positive_scores: List[Float64], negative_scores: List[Float64]) -> Float64:
    if len(positive_scores) == 0 or len(negative_scores) == 0:
        return 0.0
    var pos_sum = 0.0
    for i in range(len(positive_scores)):
        pos_sum += positive_scores[i]
    var neg_sum = 0.0
    for i in range(len(negative_scores)):
        neg_sum += negative_scores[i]
    return pos_sum / Float64(len(positive_scores)) - neg_sum / Float64(len(negative_scores))


fn latency_weighted_quality(
    quality_score: Float64,
    latency_ms: Float64,
    target_latency_ms: Float64,
) -> Float64:
    if target_latency_ms <= 0.0:
        return 0.0
    var quality = _clamp_non_negative(quality_score)
    var latency = _clamp_non_negative(latency_ms)
    return quality / (1.0 + latency / target_latency_ms)
