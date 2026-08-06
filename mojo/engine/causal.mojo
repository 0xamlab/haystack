"""
causal.mojo — Causal inference methods. Zero Python imports.
Replaces: dowhy / causalml basics

Public API:
  ate, att, propensity_score, ipw_estimate, diff_in_diff,
  regression_discontinuity, iv_estimate, stratified_ate,
  cohens_d, needed_sample_size_ate
"""
from std.math import sqrt, abs as fabs, exp, log


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mean(data: List[Float64]) -> Float64:
    """Compute mean of a list."""
    var n = len(data)
    if n == 0:
        return 0.0
    var s = 0.0
    for i in range(n):
        s += data[i]
    return s / Float64(n)


def _variance(data: List[Float64]) -> Float64:
    """Compute sample variance of a list."""
    var n = len(data)
    if n < 2:
        return 0.0
    var m = _mean(data)
    var s = 0.0
    for i in range(n):
        var d = data[i] - m
        s += d * d
    return s / Float64(n - 1)


def _std(data: List[Float64]) -> Float64:
    """Compute sample standard deviation."""
    return sqrt(_variance(data))


def _covariance(x: List[Float64], y: List[Float64]) -> Float64:
    """Compute sample covariance of two lists."""
    var n = len(x)
    if n < 2 or len(y) < 2:
        return 0.0
    var mn = n
    if len(y) < mn:
        mn = len(y)
    var mx = _mean(x)
    var my = _mean(y)
    var s = 0.0
    for i in range(mn):
        s += (x[i] - mx) * (y[i] - my)
    return s / Float64(mn - 1)


# ── Average Treatment Effect ────────────────────────────────────────────────


def ate(
    outcomes_treated: List[Float64], outcomes_control: List[Float64]
) -> Float64:
    """Average Treatment Effect: mean(treated) - mean(control)."""
    return _mean(outcomes_treated) - _mean(outcomes_control)


# ── Average Treatment Effect on the Treated ─────────────────────────────────


def att(
    outcomes_treated: List[Float64], counterfactual: List[Float64]
) -> Float64:
    """ATT: mean(treated) - mean(counterfactual)."""
    return _mean(outcomes_treated) - _mean(counterfactual)


# ── Propensity Score ─────────────────────────────────────────────────────────


def propensity_score(
    features: List[Float64], treatment: List[Int]
) -> List[Float64]:
    """Simple logistic-like propensity score.

    Score = 1/(1 + exp(-(feature - mean)/std)).
    Returns list of propensity scores in (0, 1).
    """
    var result = List[Float64]()
    var n = len(features)
    if n == 0:
        return result^
    var m = _mean(features)
    var s = _std(features)
    if s < 1e-15:
        s = 1.0  # avoid division by zero
    for i in range(n):
        var z = (features[i] - m) / s
        var p = 1.0 / (1.0 + exp(-z))
        # Clamp to avoid exact 0 or 1
        if p < 0.01:
            p = 0.01
        elif p > 0.99:
            p = 0.99
        result.append(p)
    return result^


# ── Inverse Propensity Weighting ─────────────────────────────────────────────


def ipw_estimate(
    outcomes: List[Float64],
    treatment: List[Int],
    propensity: List[Float64],
) -> Float64:
    """IPW ATE estimate.

    ATE = (1/n) * sum[ T_i * Y_i / p_i  -  (1-T_i) * Y_i / (1-p_i) ]
    """
    var n = len(outcomes)
    if n == 0:
        return 0.0
    if len(treatment) != n or len(propensity) != n:
        return 0.0
    var s = 0.0
    for i in range(n):
        var p = propensity[i]
        if p < 0.01:
            p = 0.01
        if p > 0.99:
            p = 0.99
        if treatment[i] == 1:
            s += outcomes[i] / p
        else:
            s -= outcomes[i] / (1.0 - p)
    return s / Float64(n)


# ── Difference-in-Differences ───────────────────────────────────────────────


def diff_in_diff(
    pre_treatment: List[Float64],
    post_treatment: List[Float64],
    pre_control: List[Float64],
    post_control: List[Float64],
) -> Float64:
    """Difference-in-differences estimator.

    DiD = (mean(post_treatment) - mean(pre_treatment))
        - (mean(post_control)   - mean(pre_control))
    """
    var d_treat = _mean(post_treatment) - _mean(pre_treatment)
    var d_ctrl = _mean(post_control) - _mean(pre_control)
    return d_treat - d_ctrl


# ── Regression Discontinuity ────────────────────────────────────────────────


def regression_discontinuity(
    x: List[Float64], y: List[Float64], cutoff: Float64
) -> Float64:
    """Simplified RD: difference in mean(y) just above vs below cutoff."""
    var sum_above = 0.0
    var n_above = 0
    var sum_below = 0.0
    var n_below = 0
    var n = len(x)
    if len(y) != n:
        return 0.0
    for i in range(n):
        if x[i] >= cutoff:
            sum_above += y[i]
            n_above += 1
        else:
            sum_below += y[i]
            n_below += 1
    if n_above == 0 or n_below == 0:
        return 0.0
    return (sum_above / Float64(n_above)) - (sum_below / Float64(n_below))


# ── Instrumental Variable (Wald estimator) ──────────────────────────────────


def iv_estimate(
    z: List[Float64], x: List[Float64], y: List[Float64]
) -> Float64:
    """Instrumental variable Wald estimator: cov(z,y) / cov(z,x)."""
    var cov_zy = _covariance(z, y)
    var cov_zx = _covariance(z, x)
    if fabs(cov_zx) < 1e-15:
        return 0.0
    return cov_zy / cov_zx


# ── Stratified ATE ──────────────────────────────────────────────────────────


def stratified_ate(
    outcomes: List[Float64],
    treatment: List[Int],
    strata: List[Int],
    n_strata: Int,
) -> Float64:
    """Stratified ATE: weighted average of within-stratum ATEs.

    Each stratum's ATE is weighted by stratum size / total size.
    """
    var n = len(outcomes)
    if n == 0:
        return 0.0
    if len(treatment) != n or len(strata) != n:
        return 0.0

    var total_ate = 0.0
    for s in range(n_strata):
        var sum_t = 0.0
        var cnt_t = 0
        var sum_c = 0.0
        var cnt_c = 0
        for i in range(n):
            if strata[i] == s:
                if treatment[i] == 1:
                    sum_t += outcomes[i]
                    cnt_t += 1
                else:
                    sum_c += outcomes[i]
                    cnt_c += 1
        if cnt_t > 0 and cnt_c > 0:
            var stratum_ate = (sum_t / Float64(cnt_t)) - (sum_c / Float64(cnt_c))
            var stratum_size = cnt_t + cnt_c
            total_ate += stratum_ate * Float64(stratum_size) / Float64(n)
    return total_ate


# ── Cohen's d ────────────────────────────────────────────────────────────────


def cohens_d(group1: List[Float64], group2: List[Float64]) -> Float64:
    """Cohen's d effect size: (mean1-mean2) / pooled_std."""
    var n1 = len(group1)
    var n2 = len(group2)
    if n1 < 2 or n2 < 2:
        return 0.0
    var m1 = _mean(group1)
    var m2 = _mean(group2)
    var v1 = _variance(group1)
    var v2 = _variance(group2)
    var pooled = sqrt(
        (Float64(n1 - 1) * v1 + Float64(n2 - 1) * v2)
        / Float64(n1 + n2 - 2)
    )
    if pooled < 1e-15:
        return 0.0
    return (m1 - m2) / pooled


# ── Needed sample size ──────────────────────────────────────────────────────


def needed_sample_size_ate(
    effect_size: Float64,
    std: Float64,
    alpha: Float64 = 0.05,
    power: Float64 = 0.8,
) -> Int:
    """Sample size per group to detect ATE.

    Uses formula: n = 2 * (z_alpha/2 + z_beta)^2 * std^2 / effect_size^2
    z_alpha/2 ≈ 1.96 for alpha=0.05, z_beta ≈ 0.842 for power=0.8.
    """
    # Approximate z-values for common alpha/power
    var z_alpha: Float64
    if alpha <= 0.01:
        z_alpha = 2.576
    elif alpha <= 0.05:
        z_alpha = 1.96
    else:
        z_alpha = 1.645

    var z_beta: Float64
    if power >= 0.95:
        z_beta = 1.645
    elif power >= 0.9:
        z_beta = 1.282
    elif power >= 0.8:
        z_beta = 0.842
    else:
        z_beta = 0.524

    if fabs(effect_size) < 1e-15:
        return 1000000  # very large if no effect

    var z_sum = z_alpha + z_beta
    var n_float = 2.0 * z_sum * z_sum * std * std / (effect_size * effect_size)
    var n = Int(n_float) + 1  # ceiling
    if n < 2:
        n = 2
    return n
