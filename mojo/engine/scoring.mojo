"""
scoring.mojo — Scoring Models. Zero Python imports.

Replaces custom Python credit/risk scoring code with pure Mojo
implementations of sigmoid, logit, WoE, IV, Gini, KS, score bands,
linear scoring, and normalization.

Public API:
  sigmoid            — Logistic sigmoid
  logit              — Inverse sigmoid (log-odds)
  log_odds_to_score  — Convert log-odds to credit score
  score_to_log_odds  — Convert credit score to log-odds
  woe                — Weight of Evidence
  iv                 — Information Value
  gini_coefficient   — Gini from AUC
  ks_statistic       — Kolmogorov-Smirnov statistic
  score_band         — Assign score to labelled band
  linear_score       — Weighted linear scoring
  normalize_score    — Normalize to [0, 1]
"""

from std.math import exp, log, abs as fabs


# ── sigmoid ──────────────────────────────────────────────────────────────────


fn sigmoid(x: Float64) -> Float64:
    """Logistic sigmoid: 1 / (1 + exp(-x)).

    Args:
        x: Input value.

    Returns:
        Value in (0, 1).
    """
    return 1.0 / (1.0 + exp(-x))


# ── logit ────────────────────────────────────────────────────────────────────


fn logit(p: Float64) -> Float64:
    """Logit (inverse sigmoid): log(p / (1-p)).

    Clamps p to [1e-15, 1-1e-15] to avoid log(0).

    Args:
        p: Probability in (0, 1).

    Returns:
        Log-odds.
    """
    var pp = p
    if pp < 1e-15:
        pp = 1e-15
    if pp > 1.0 - 1e-15:
        pp = 1.0 - 1e-15
    return log(pp / (1.0 - pp))


# ── log_odds_to_score ────────────────────────────────────────────────────────


fn log_odds_to_score(log_odds: Float64, base_score: Float64 = 600.0,
                     pdo: Float64 = 20.0) -> Float64:
    """Convert log-odds to a credit score.

    Formula: base_score - pdo * log_odds / ln(2).

    Args:
        log_odds: Log-odds value.
        base_score: Score at even odds (default 600).
        pdo: Points to double the odds (default 20).

    Returns:
        Credit score.
    """
    var ln2 = log(2.0)
    return base_score - pdo * log_odds / ln2


# ── score_to_log_odds ────────────────────────────────────────────────────────


fn score_to_log_odds(score: Float64, base_score: Float64 = 600.0,
                     pdo: Float64 = 20.0) -> Float64:
    """Convert a credit score back to log-odds.

    Formula: (base_score - score) * ln(2) / pdo.

    Args:
        score: Credit score.
        base_score: Score at even odds (default 600).
        pdo: Points to double the odds (default 20).

    Returns:
        Log-odds.
    """
    var ln2 = log(2.0)
    return (base_score - score) * ln2 / pdo


# ── woe ──────────────────────────────────────────────────────────────────────


fn woe(events: Int, non_events: Int, total_events: Int,
       total_non_events: Int) -> Float64:
    """Weight of Evidence: ln(dist_non_events / dist_events).

    Args:
        events: Number of events in this bin.
        non_events: Number of non-events in this bin.
        total_events: Total events across all bins.
        total_non_events: Total non-events across all bins.

    Returns:
        WoE value.
    """
    var dist_e = Float64(events) / Float64(total_events)
    var dist_ne = Float64(non_events) / Float64(total_non_events)
    # Clamp to avoid log(0)
    if dist_e < 1e-15:
        dist_e = 1e-15
    if dist_ne < 1e-15:
        dist_ne = 1e-15
    return log(dist_ne / dist_e)


# ── iv ───────────────────────────────────────────────────────────────────────


fn iv(woe_values: List[Float64], dist_events: List[Float64],
      dist_non_events: List[Float64]) -> Float64:
    """Information Value: Σ(dist_non_events_i - dist_events_i) * woe_i.

    Args:
        woe_values: WoE for each bin.
        dist_events: Distribution of events per bin.
        dist_non_events: Distribution of non-events per bin.

    Returns:
        IV (non-negative for valid inputs).
    """
    var total = 0.0
    var n = len(woe_values)
    # Short or empty distributions would be read past their end below (uncatchable abort).
    if len(dist_events) != n or len(dist_non_events) != n:
        return 0.0
    for i in range(n):
        total += (dist_non_events[i] - dist_events[i]) * woe_values[i]
    return total


# ── gini_coefficient ─────────────────────────────────────────────────────────


fn gini_coefficient(actual: List[Float64], predicted: List[Float64]) -> Float64:
    """Gini coefficient from AUC: 2 * AUC - 1.

    Computes AUC via trapezoidal rule on sorted predictions.
    Assumes actual values are 0.0 or 1.0.

    Args:
        actual: True labels (0.0 or 1.0).
        predicted: Predicted scores.

    Returns:
        Gini coefficient in [-1, 1].
    """
    var n = len(actual)
    # predicted is indexed below via sorted positions; a short list aborts (uncatchable).
    if n == 0 or len(predicted) != n:
        return 0.0

    # Create index array sorted by predicted descending
    var indices = List[Int](capacity=n)
    for i in range(n):
        indices.append(i)

    # Simple insertion sort by predicted descending
    for i in range(1, n):
        var key = indices[i]
        var j = i - 1
        while j >= 0 and predicted[indices[j]] < predicted[key]:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key

    # Compute AUC using sorted order
    var total_pos = 0.0
    var total_neg = 0.0
    for i in range(n):
        if actual[i] > 0.5:
            total_pos += 1.0
        else:
            total_neg += 1.0

    if total_pos < 1.0 or total_neg < 1.0:
        return 0.0

    var tp = 0.0
    var fp = 0.0
    var auc = 0.0
    var prev_fpr = 0.0
    var prev_tpr = 0.0

    for i in range(n):
        var idx = indices[i]
        if actual[idx] > 0.5:
            tp += 1.0
        else:
            fp += 1.0
        var tpr = tp / total_pos
        var fpr = fp / total_neg
        # Trapezoidal rule
        auc += (fpr - prev_fpr) * (tpr + prev_tpr) / 2.0
        prev_fpr = fpr
        prev_tpr = tpr

    return 2.0 * auc - 1.0


# ── ks_statistic ─────────────────────────────────────────────────────────────


fn ks_statistic(actual: List[Float64], predicted: List[Float64]) -> Float64:
    """Kolmogorov-Smirnov statistic: max |CDF_good - CDF_bad|.

    Args:
        actual: True labels (0.0 or 1.0).
        predicted: Predicted scores.

    Returns:
        KS statistic in [0, 1].
    """
    var n = len(actual)
    # predicted is indexed below via sorted positions; a short list aborts (uncatchable).
    if n == 0 or len(predicted) != n:
        return 0.0

    # Sort by predicted ascending
    var indices = List[Int](capacity=n)
    for i in range(n):
        indices.append(i)
    for i in range(1, n):
        var key = indices[i]
        var j = i - 1
        while j >= 0 and predicted[indices[j]] > predicted[key]:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key

    var total_pos = 0.0
    var total_neg = 0.0
    for i in range(n):
        if actual[i] > 0.5:
            total_pos += 1.0
        else:
            total_neg += 1.0

    if total_pos < 1.0 or total_neg < 1.0:
        return 0.0

    var cum_pos = 0.0
    var cum_neg = 0.0
    var max_ks = 0.0

    for i in range(n):
        var idx = indices[i]
        if actual[idx] > 0.5:
            cum_pos += 1.0
        else:
            cum_neg += 1.0
        var diff = fabs(cum_pos / total_pos - cum_neg / total_neg)
        if diff > max_ks:
            max_ks = diff

    return max_ks


# ── score_band ───────────────────────────────────────────────────────────────


fn score_band(score: Float64, boundaries: List[Float64],
              labels: List[String]) -> String:
    """Assign a score to a band based on boundaries.

    Boundaries define upper limits for each band. Score falls into the
    first band where score <= boundary.

    Args:
        score: Score value.
        boundaries: Upper boundary for each band (ascending).
        labels: Label for each band (len = len(boundaries) + 1).

    Returns:
        Band label.
    """
    # With fewer labels than boundaries+1 a read past labels' end (or labels[-1]) aborts (uncatchable).
    if len(labels) <= len(boundaries):
        return ""
    for i in range(len(boundaries)):
        if score <= boundaries[i]:
            return labels[i]
    return labels[len(labels) - 1]


# ── linear_score ─────────────────────────────────────────────────────────────


fn linear_score(features: List[Float64], weights: List[Float64],
                intercept: Float64) -> Float64:
    """Linear scoring: Σ(feature_i * weight_i) + intercept.

    Args:
        features: Feature values.
        weights: Feature weights (same length as features).
        intercept: Bias term.

    Returns:
        Scalar score.
    """
    var n = len(features)
    # A short or empty weights list would be read past its end below (uncatchable abort).
    if len(weights) != n:
        return 0.0
    var total = intercept
    for i in range(n):
        total += features[i] * weights[i]
    return total


# ── normalize_score ──────────────────────────────────────────────────────────


fn normalize_score(score: Float64, min_score: Float64,
                   max_score: Float64) -> Float64:
    """Normalize score to [0, 1]: (score - min) / (max - min).

    Args:
        score: Raw score.
        min_score: Minimum possible score.
        max_score: Maximum possible score.

    Returns:
        Normalized score in [0, 1]. Returns 0.0 if min == max.
    """
    var denom = max_score - min_score
    if fabs(denom) < 1e-15:
        return 0.0
    var result = (score - min_score) / denom
    if result < 0.0:
        return 0.0
    if result > 1.0:
        return 1.0
    return result
