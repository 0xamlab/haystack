"""
psychometrics.mojo — Psychometrics & Test Theory Library. Zero Python imports.

Provides functions for classical test theory, item response theory,
reliability estimation, and score transformations.

Public API:
  item_difficulty              — p = correct / total
  item_discrimination          — D = p_upper - p_lower
  point_biserial               — rpb correlation
  kuder_richardson_20          — KR-20 reliability
  cronbach_alpha               — Cronbach's alpha
  spearman_brown_prophecy      — Prophecy formula
  standard_error_of_measurement — SEM = SD * sqrt(1 - r)
  z_score                      — z = (x - μ) / σ
  t_score                      — T = 50 + 10*z
  stanine                      — Map z to stanine (1-9)
  irt_1pl_probability          — 1PL IRT model
  irt_2pl_probability          — 2PL IRT model
"""

from std.math import sqrt, exp


# ── item_difficulty ──────────────────────────────────────────────────────────


fn item_difficulty(n_correct: Float64, n_total: Float64) -> Float64:
    """Item difficulty: p = correct / total."""
    if n_total == 0.0:
        return 0.0
    return n_correct / n_total


# ── item_discrimination ──────────────────────────────────────────────────────


fn item_discrimination(
    upper_correct: Float64,
    upper_total: Float64,
    lower_correct: Float64,
    lower_total: Float64,
) -> Float64:
    """Item discrimination: D = p_upper - p_lower."""
    var p_upper = item_difficulty(upper_correct, upper_total)
    var p_lower = item_difficulty(lower_correct, lower_total)
    return p_upper - p_lower


# ── point_biserial ───────────────────────────────────────────────────────────


fn point_biserial(
    mean_correct: Float64,
    mean_total: Float64,
    sd_total: Float64,
    p: Float64,
) -> Float64:
    """Point-biserial: rpb = (M1 - M0) / SD * sqrt(p * q)."""
    var q = 1.0 - p
    if sd_total == 0.0:
        return 0.0
    return (mean_correct - mean_total) / sd_total * sqrt(p * q)


# ── kuder_richardson_20 ─────────────────────────────────────────────────────


fn kuder_richardson_20(
    n_items: Float64, variance_total: Float64, p_sum_pq: Float64
) -> Float64:
    """KR-20 = (n/(n-1)) * (1 - Σpq/σ²)."""
    if n_items <= 1.0 or variance_total == 0.0:
        return 0.0
    return (n_items / (n_items - 1.0)) * (1.0 - p_sum_pq / variance_total)


# ── cronbach_alpha ───────────────────────────────────────────────────────────


fn cronbach_alpha(
    n_items: Float64, sum_item_variance: Float64, total_variance: Float64
) -> Float64:
    """Cronbach's α = (n/(n-1)) * (1 - Σσi²/σt²)."""
    if n_items <= 1.0 or total_variance == 0.0:
        return 0.0
    return (n_items / (n_items - 1.0)) * (1.0 - sum_item_variance / total_variance)


# ── spearman_brown_prophecy ──────────────────────────────────────────────────


fn spearman_brown_prophecy(r: Float64, n: Float64) -> Float64:
    """Spearman-Brown prophecy: r_new = n*r / (1 + (n-1)*r)."""
    var denom = 1.0 + (n - 1.0) * r
    if denom == 0.0:
        return 0.0
    return n * r / denom


# ── standard_error_of_measurement ────────────────────────────────────────────


fn standard_error_of_measurement(sd: Float64, reliability: Float64) -> Float64:
    """SEM = SD * sqrt(1 - reliability)."""
    var val = 1.0 - reliability
    if val < 0.0:
        val = 0.0
    return sd * sqrt(val)


# ── z_score ──────────────────────────────────────────────────────────────────


fn z_score(raw: Float64, mean: Float64, sd: Float64) -> Float64:
    """z = (x - μ) / σ."""
    if sd == 0.0:
        return 0.0
    return (raw - mean) / sd


# ── t_score ──────────────────────────────────────────────────────────────────


fn t_score(z: Float64) -> Float64:
    """T-score = 50 + 10*z."""
    return 50.0 + 10.0 * z


# ── stanine ──────────────────────────────────────────────────────────────────


fn stanine(z: Float64) -> Int:
    """Map z-score to stanine (1-9 scale, approximate boundaries)."""
    if z < -1.75:
        return 1
    if z < -1.25:
        return 2
    if z < -0.75:
        return 3
    if z < -0.25:
        return 4
    if z < 0.25:
        return 5
    if z < 0.75:
        return 6
    if z < 1.25:
        return 7
    if z < 1.75:
        return 8
    return 9


# ── irt_1pl_probability ─────────────────────────────────────────────────────


fn irt_1pl_probability(theta: Float64, b: Float64) -> Float64:
    """1PL IRT: P(θ) = 1 / (1 + exp(-(θ - b)))."""
    return 1.0 / (1.0 + exp(-(theta - b)))


# ── irt_2pl_probability ─────────────────────────────────────────────────────


fn irt_2pl_probability(theta: Float64, a: Float64, b: Float64) -> Float64:
    """2PL IRT: P(θ) = 1 / (1 + exp(-a*(θ - b)))."""
    return 1.0 / (1.0 + exp(-a * (theta - b)))
