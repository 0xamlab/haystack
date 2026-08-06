"""
allocation.mojo — Portfolio/resource allocation. Zero Python imports.

Replaces pypfopt with pure Mojo implementations for equal weight,
inverse variance, risk parity, Kelly criterion, and efficient frontier.

Public API:
  equal_weight            — 1/n allocation
  inverse_variance        — Weight proportional to 1/variance
  risk_parity_simple      — Weight proportional to 1/sqrt(variance)
  max_sharpe_2asset       — Analytical max Sharpe for 2-asset portfolio
  min_variance_2asset     — Min variance 2-asset weights
  portfolio_return        — Weighted portfolio return
  portfolio_variance_2asset — Portfolio variance for 2 assets
  kelly_criterion         — Kelly fraction
  efficient_frontier_2asset — Generate risk/return pairs for 2-asset frontier
  rebalance_threshold     — Check if weight drift exceeds threshold
"""
from std.math import sqrt, abs as fabs


# ── Equal weight ───────────────────────────────────────────────────────────────


def equal_weight(n_assets: Int) -> List[Float64]:
    """1/n allocation across n assets."""
    var w = List[Float64]()
    if n_assets <= 0:
        return w^
    var wt = 1.0 / Float64(n_assets)
    for _ in range(n_assets):
        w.append(wt)
    return w^


# ── Inverse variance ──────────────────────────────────────────────────────────


def inverse_variance(variances: List[Float64]) -> List[Float64]:
    """Weight proportional to 1/variance. Higher variance → lower weight."""
    var n = len(variances)
    var w = List[Float64]()
    if n == 0:
        return w^
    var total: Float64 = 0.0
    for i in range(n):
        var v = variances[i]
        if v <= 0.0:
            v = 1e-10
        total += 1.0 / v
    for i in range(n):
        var v = variances[i]
        if v <= 0.0:
            v = 1e-10
        w.append((1.0 / v) / total)
    return w^


# ── Risk parity (simple) ──────────────────────────────────────────────────────


def risk_parity_simple(variances: List[Float64]) -> List[Float64]:
    """Weight proportional to 1/sqrt(variance) (risk parity approximation)."""
    var n = len(variances)
    var w = List[Float64]()
    if n == 0:
        return w^
    var total: Float64 = 0.0
    for i in range(n):
        var v = variances[i]
        if v <= 0.0:
            v = 1e-10
        total += 1.0 / sqrt(v)
    for i in range(n):
        var v = variances[i]
        if v <= 0.0:
            v = 1e-10
        w.append((1.0 / sqrt(v)) / total)
    return w^


# ── Max Sharpe 2-asset ────────────────────────────────────────────────────────


def max_sharpe_2asset(
    r1: Float64,
    r2: Float64,
    s1: Float64,
    s2: Float64,
    rho: Float64,
    rf: Float64,
) -> List[Float64]:
    """Analytical max Sharpe ratio weights for a 2-asset portfolio.

    r1, r2: expected returns; s1, s2: std devs; rho: correlation; rf: risk-free.
    Returns [w1, w2] summing to 1.
    """
    var er1 = r1 - rf
    var er2 = r2 - rf
    var cov12 = rho * s1 * s2
    var num = er1 * s2 * s2 - er2 * cov12
    var den = er1 * s2 * s2 + er2 * s1 * s1 - (er1 + er2) * cov12
    var w1: Float64 = 0.5
    if fabs(den) > 1e-15:
        w1 = num / den
    # Clamp to [0,1]
    if w1 < 0.0:
        w1 = 0.0
    if w1 > 1.0:
        w1 = 1.0
    var w = List[Float64]()
    w.append(w1)
    w.append(1.0 - w1)
    return w^


# ── Min variance 2-asset ──────────────────────────────────────────────────────


def min_variance_2asset(
    s1: Float64, s2: Float64, rho: Float64
) -> List[Float64]:
    """Minimum variance 2-asset weights.

    w1 = (s2² - ρ·s1·s2) / (s1² + s2² - 2ρ·s1·s2)
    Returns [w1, w2] summing to 1.
    """
    var cov12 = rho * s1 * s2
    var num = s2 * s2 - cov12
    var den = s1 * s1 + s2 * s2 - 2.0 * cov12
    var w1: Float64 = 0.5
    if fabs(den) > 1e-15:
        w1 = num / den
    if w1 < 0.0:
        w1 = 0.0
    if w1 > 1.0:
        w1 = 1.0
    var w = List[Float64]()
    w.append(w1)
    w.append(1.0 - w1)
    return w^


# ── Portfolio return ───────────────────────────────────────────────────────────


def portfolio_return(
    weights: List[Float64], returns: List[Float64]
) -> Float64:
    """Weighted portfolio return: Σ w_i * r_i."""
    var n = len(weights)
    var m = len(returns)
    var sz = n if n < m else m
    var total: Float64 = 0.0
    for i in range(sz):
        total += weights[i] * returns[i]
    return total


# ── Portfolio variance 2-asset ─────────────────────────────────────────────────


def portfolio_variance_2asset(
    w1: Float64, s1: Float64, s2: Float64, rho: Float64
) -> Float64:
    """Portfolio variance: w1²s1² + (1-w1)²s2² + 2w1(1-w1)ρs1s2."""
    var w2 = 1.0 - w1
    return (
        w1 * w1 * s1 * s1
        + w2 * w2 * s2 * s2
        + 2.0 * w1 * w2 * rho * s1 * s2
    )


# ── Kelly criterion ───────────────────────────────────────────────────────────


def kelly_criterion(win_prob: Float64, win_ratio: Float64) -> Float64:
    """Kelly fraction: p - (1-p)/b where b = win_ratio.

    Returns the optimal fraction of capital to bet.
    """
    if win_ratio <= 0.0:
        return 0.0
    return win_prob - (1.0 - win_prob) / win_ratio


# ── Efficient frontier 2-asset ─────────────────────────────────────────────────


def efficient_frontier_2asset(
    r1: Float64,
    r2: Float64,
    s1: Float64,
    s2: Float64,
    rho: Float64,
    n_points: Int,
) -> List[List[Float64]]:
    """Generate [[return, risk], ...] for 2-asset efficient frontier.

    Sweeps w1 from 0 to 1 in n_points steps.
    """
    var frontier = List[List[Float64]]()
    if n_points <= 0:
        return frontier^
    var step: Float64 = 1.0
    if n_points > 1:
        step = 1.0 / Float64(n_points - 1)
    for i in range(n_points):
        var w1 = Float64(i) * step
        if w1 > 1.0:
            w1 = 1.0
        var w2 = 1.0 - w1
        var ret = w1 * r1 + w2 * r2
        var var_ = portfolio_variance_2asset(w1, s1, s2, rho)
        var risk = sqrt(var_)
        var point = List[Float64]()
        point.append(ret)
        point.append(risk)
        frontier.append(point^)
    return frontier^


# ── Rebalance threshold ───────────────────────────────────────────────────────


def rebalance_threshold(
    current_weights: List[Float64],
    target_weights: List[Float64],
    threshold: Float64,
) -> Bool:
    """Check if any weight drifted beyond threshold.

    Returns True if max |current - target| > threshold.
    """
    var n = len(current_weights)
    var m = len(target_weights)
    var sz = n if n < m else m
    for i in range(sz):
        if fabs(current_weights[i] - target_weights[i]) > threshold:
            return True
    return False
