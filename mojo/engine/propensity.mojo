"""
propensity.mojo — Propensity score matching for causal inference. Zero Python imports.

Extends causal inference capabilities with pure Mojo implementations of
propensity score estimation, nearest-neighbor and caliper matching,
average treatment effect estimation, balance diagnostics, and trimming.

Public API:
  propensity_scores      — Simple logistic propensity score per sample
  nearest_neighbor_match — For each treated, find nearest control index
  caliper_match          — Match within caliper; -1 if no match
  matched_ate            — ATE from matched pairs
  balance_check          — Standardized mean difference
  propensity_overlap     — Overlap measure between treated/control scores
  trimmed_sample         — Indices of samples within propensity [lo, hi]
  stratified_estimate    — Stratified ATE by propensity strata
  match_quality          — Fraction of successful matches (non -1)
"""
from std.math import abs as fabs, exp, log, sqrt


# ── _sigmoid ────────────────────────────────────────────────────────────────


def _sigmoid(x: Float64) -> Float64:
    """Logistic sigmoid: 1 / (1 + exp(-x))."""
    if x > 500.0:
        return 1.0
    if x < -500.0:
        return 0.0
    return 1.0 / (1.0 + exp(-x))


# ── propensity_scores ───────────────────────────────────────────────────────


def propensity_scores(features: List[List[Float64]], treatment: List[Int]) -> List[Float64]:
    """Compute simple logistic propensity scores.

    Fits a single-pass logistic model using feature means to produce
    a propensity score in (0, 1) for each sample. Uses a simplified
    approach: score = sigmoid(sum of standardized features weighted
    by correlation with treatment).

    Args:
        features:  n×d feature matrix.
        treatment: Binary treatment indicator (0 or 1) per sample.

    Returns:
        List of propensity scores in (0, 1).
    """
    var n = len(features)
    if n == 0:
        return List[Float64]()
    # Parallel lists: treatment[i] is read per row, and every row must cover
    # the first row's width; short inputs abort (uncatchable).
    if len(treatment) < n:
        return List[Float64]()
    var d = len(features[0])
    for i in range(n):
        if len(features[i]) < d:
            return List[Float64]()

    # Compute feature means and stds
    var means = List[Float64]()
    var stds = List[Float64]()
    for j in range(d):
        var s: Float64 = 0.0
        for i in range(n):
            s += features[i][j]
        var m = s / Float64(n)
        means.append(m)
        var ss: Float64 = 0.0
        for i in range(n):
            var diff = features[i][j] - m
            ss += diff * diff
        var sd = sqrt(ss / Float64(n))
        if sd < 1e-12:
            sd = 1.0
        stds.append(sd)

    # Compute weights as correlation with treatment
    var treat_mean: Float64 = 0.0
    for i in range(n):
        treat_mean += Float64(treatment[i])
    treat_mean /= Float64(n)

    var weights = List[Float64]()
    for j in range(d):
        var cov: Float64 = 0.0
        for i in range(n):
            cov += (features[i][j] - means[j]) * (Float64(treatment[i]) - treat_mean)
        cov /= Float64(n)
        weights.append(cov / (stds[j] * stds[j]))

    # Compute scores
    var scores = List[Float64]()
    for i in range(n):
        var z: Float64 = 0.0
        for j in range(d):
            z += weights[j] * (features[i][j] - means[j]) / stds[j]
        var s = _sigmoid(z)
        # Clamp to (0, 1)
        if s < 1e-6:
            s = 1e-6
        if s > 1.0 - 1e-6:
            s = 1.0 - 1e-6
        scores.append(s)
    return scores^


# ── nearest_neighbor_match ──────────────────────────────────────────────────


def nearest_neighbor_match(scores_treated: List[Float64], scores_control: List[Float64]) -> List[Int]:
    """For each treated unit, find the nearest control unit by propensity score.

    Args:
        scores_treated: Propensity scores of treated units.
        scores_control: Propensity scores of control units.

    Returns:
        List of control indices (one per treated unit).
    """
    var matches = List[Int]()
    # An empty control pool has no nearest neighbor to offer.
    if len(scores_control) == 0:
        return matches^
    for i in range(len(scores_treated)):
        var best_idx = 0
        var best_dist = fabs(scores_treated[i] - scores_control[0])
        for j in range(1, len(scores_control)):
            var d = fabs(scores_treated[i] - scores_control[j])
            if d < best_dist:
                best_dist = d
                best_idx = j
        matches.append(best_idx)
    return matches^


# ── caliper_match ───────────────────────────────────────────────────────────


def caliper_match(scores_treated: List[Float64], scores_control: List[Float64], caliper: Float64) -> List[Int]:
    """Match treated to control within a caliper distance.

    Args:
        scores_treated: Propensity scores of treated units.
        scores_control: Propensity scores of control units.
        caliper:        Maximum allowed distance for a match.

    Returns:
        List of control indices; -1 if no match within caliper.
    """
    var matches = List[Int]()
    for i in range(len(scores_treated)):
        var best_idx = -1
        var best_dist: Float64 = caliper + 1.0
        for j in range(len(scores_control)):
            var d = fabs(scores_treated[i] - scores_control[j])
            if d <= caliper and d < best_dist:
                best_dist = d
                best_idx = j
        matches.append(best_idx)
    return matches^


# ── matched_ate ─────────────────────────────────────────────────────────────


def matched_ate(outcomes: List[Float64], treatment: List[Int], matches: List[Int]) -> Float64:
    """Average Treatment Effect from matched pairs.

    For each treated unit i with match matches[treated_idx] into controls,
    compute ATE = mean(Y_treated - Y_matched_control).

    Args:
        outcomes:  Outcome values for all units.
        treatment: Binary treatment indicator per unit.
        matches:   Control indices matched to each treated unit.

    Returns:
        Estimated ATE.
    """
    # Parallel lists: outcomes[i] is read for each treatment entry.
    if len(outcomes) < len(treatment):
        return 0.0

    # Separate treated and control outcomes
    var treated_outcomes = List[Float64]()
    var control_outcomes_list = List[Float64]()
    var control_indices = List[Int]()

    for i in range(len(treatment)):
        if treatment[i] == 1:
            treated_outcomes.append(outcomes[i])
        else:
            control_outcomes_list.append(outcomes[i])
            control_indices.append(i)

    if len(treated_outcomes) == 0:
        return 0.0

    var total: Float64 = 0.0
    var count = 0
    for i in range(len(treated_outcomes)):
        if i < len(matches) and matches[i] >= 0 and matches[i] < len(control_outcomes_list):
            total += treated_outcomes[i] - control_outcomes_list[matches[i]]
            count += 1
    if count == 0:
        return 0.0
    return total / Float64(count)


# ── balance_check ───────────────────────────────────────────────────────────


def balance_check(features_treated: List[Float64], features_control: List[Float64]) -> Float64:
    """Standardized mean difference for balance assessment.

    SMD = |mean_t - mean_c| / pooled_sd.

    Args:
        features_treated: Feature values for treated group.
        features_control: Feature values for control group.

    Returns:
        Absolute standardized mean difference.
    """
    var nt = len(features_treated)
    var nc = len(features_control)
    if nt == 0 or nc == 0:
        return 0.0

    var mean_t: Float64 = 0.0
    for i in range(nt):
        mean_t += features_treated[i]
    mean_t /= Float64(nt)

    var mean_c: Float64 = 0.0
    for i in range(nc):
        mean_c += features_control[i]
    mean_c /= Float64(nc)

    var var_t: Float64 = 0.0
    for i in range(nt):
        var diff = features_treated[i] - mean_t
        var_t += diff * diff
    if nt > 1:
        var_t /= Float64(nt - 1)

    var var_c: Float64 = 0.0
    for i in range(nc):
        var diff = features_control[i] - mean_c
        var_c += diff * diff
    if nc > 1:
        var_c /= Float64(nc - 1)

    var pooled_sd = sqrt((var_t + var_c) / 2.0)
    if pooled_sd < 1e-12:
        return 0.0
    return fabs(mean_t - mean_c) / pooled_sd


# ── propensity_overlap ──────────────────────────────────────────────────────


def propensity_overlap(scores: List[Float64], treatment: List[Int]) -> Float64:
    """Overlap measure between treated and control propensity distributions.

    Overlap = min(max(treated), max(control)) - max(min(treated), min(control)).

    Args:
        scores:    Propensity scores for all units.
        treatment: Binary treatment indicator per unit.

    Returns:
        Overlap measure (can be negative if no overlap).
    """
    # Parallel lists: treatment[i] is read for each score.
    if len(treatment) < len(scores):
        return 0.0

    var min_t: Float64 = 1e18
    var max_t: Float64 = -1e18
    var min_c: Float64 = 1e18
    var max_c: Float64 = -1e18
    var has_t = False
    var has_c = False

    for i in range(len(scores)):
        if treatment[i] == 1:
            has_t = True
            if scores[i] < min_t:
                min_t = scores[i]
            if scores[i] > max_t:
                max_t = scores[i]
        else:
            has_c = True
            if scores[i] < min_c:
                min_c = scores[i]
            if scores[i] > max_c:
                max_c = scores[i]

    if not has_t or not has_c:
        return 0.0

    var upper = max_t
    if max_c < upper:
        upper = max_c
    var lower = min_t
    if min_c > lower:
        lower = min_c
    return upper - lower


# ── trimmed_sample ──────────────────────────────────────────────────────────


def trimmed_sample(scores: List[Float64], treatment: List[Int], lo: Float64, hi: Float64) -> List[Int]:
    """Indices of samples with propensity scores within [lo, hi].

    Args:
        scores:    Propensity scores for all units.
        treatment: Binary treatment indicator (unused but kept for API consistency).
        lo:        Lower bound.
        hi:        Upper bound.

    Returns:
        List of indices where lo <= score <= hi.
    """
    var indices = List[Int]()
    for i in range(len(scores)):
        if scores[i] >= lo and scores[i] <= hi:
            indices.append(i)
    return indices^


# ── stratified_estimate ─────────────────────────────────────────────────────


def stratified_estimate(outcomes: List[Float64], treatment: List[Int], scores: List[Float64], n_strata: Int) -> Float64:
    """Stratified ATE by propensity score strata.

    Divides the score range into n_strata equal-width bins and computes
    the within-stratum treatment effect, then averages across strata.

    Args:
        outcomes:  Outcome values per unit.
        treatment: Binary treatment indicator per unit.
        scores:    Propensity scores per unit.
        n_strata:  Number of strata (e.g. 5 for quintiles).

    Returns:
        Stratified ATE estimate.
    """
    var n = len(scores)
    if n == 0 or n_strata <= 0:
        return 0.0
    # Parallel lists: outcomes[i] and treatment[i] are read per score.
    if len(outcomes) < n or len(treatment) < n:
        return 0.0

    # Find score range
    var smin: Float64 = scores[0]
    var smax: Float64 = scores[0]
    for i in range(1, n):
        if scores[i] < smin:
            smin = scores[i]
        if scores[i] > smax:
            smax = scores[i]

    var width = (smax - smin) / Float64(n_strata)
    if width < 1e-12:
        # All scores identical; just compute simple difference
        var sum_t: Float64 = 0.0
        var cnt_t = 0
        var sum_c: Float64 = 0.0
        var cnt_c = 0
        for i in range(n):
            if treatment[i] == 1:
                sum_t += outcomes[i]
                cnt_t += 1
            else:
                sum_c += outcomes[i]
                cnt_c += 1
        if cnt_t == 0 or cnt_c == 0:
            return 0.0
        return sum_t / Float64(cnt_t) - sum_c / Float64(cnt_c)

    var total_ate: Float64 = 0.0
    var strata_count = 0

    for s in range(n_strata):
        var lo = smin + Float64(s) * width
        var hi = lo + width
        if s == n_strata - 1:
            hi = smax + 1e-12  # Include the max value

        var sum_t: Float64 = 0.0
        var cnt_t = 0
        var sum_c: Float64 = 0.0
        var cnt_c = 0

        for i in range(n):
            if scores[i] >= lo and scores[i] < hi:
                if treatment[i] == 1:
                    sum_t += outcomes[i]
                    cnt_t += 1
                else:
                    sum_c += outcomes[i]
                    cnt_c += 1

        if cnt_t > 0 and cnt_c > 0:
            total_ate += sum_t / Float64(cnt_t) - sum_c / Float64(cnt_c)
            strata_count += 1

    if strata_count == 0:
        return 0.0
    return total_ate / Float64(strata_count)


# ── match_quality ───────────────────────────────────────────────────────────


def match_quality(matches: List[Int]) -> Float64:
    """Fraction of successful matches (non -1).

    Args:
        matches: List of match indices; -1 means unmatched.

    Returns:
        Fraction in [0, 1].
    """
    var n = len(matches)
    if n == 0:
        return 0.0
    var good = 0
    for i in range(n):
        if matches[i] >= 0:
            good += 1
    return Float64(good) / Float64(n)
