"""
risk.mojo — Risk metrics for portfolio/investment analysis. Zero Python imports.

Replaces riskfolio-lib / custom risk code with pure Mojo implementations
for VaR, CVaR, drawdown, Sharpe, Sortino, beta, alpha, information ratio,
Calmar ratio, and downside deviation.

Public API:
  value_at_risk       — Historical VaR
  conditional_var     — CVaR / Expected Shortfall
  max_drawdown        — Maximum drawdown fraction
  drawdown_series     — Drawdown at each point
  sortino_ratio       — Sortino ratio
  sharpe_ratio        — Sharpe ratio
  beta                — CAPM beta
  alpha               — Jensen's alpha
  information_ratio   — Information ratio vs benchmark
  calmar_ratio        — Calmar ratio
  downside_deviation  — Downside deviation
"""
from std.math import sqrt, abs as fabs


# ── Sorting helper ────────────────────────────────────────────────────────────


fn _sort_copy(data: List[Float64]) -> List[Float64]:
    """Return a sorted copy (insertion sort)."""
    var out = data.copy()
    var n = len(out)
    for i in range(1, n):
        var k = out[i]
        var j = i - 1
        while j >= 0 and out[j] > k:
            out[j + 1] = out[j]
            j -= 1
        out[j + 1] = k
    return out^


# ── Stats helpers ─────────────────────────────────────────────────────────────


fn _mean(data: List[Float64]) -> Float64:
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
    return s / Float64(n)


fn _std(data: List[Float64]) -> Float64:
    var n = len(data)
    if n < 2:
        return 0.0
    var m = _mean(data)
    var ss: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        ss += d * d
    return sqrt(ss / Float64(n))


fn _cov(a: List[Float64], b: List[Float64]) -> Float64:
    var n = len(a)
    if n < 2:
        return 0.0
    var ma = _mean(a)
    var mb = _mean(b)
    var s: Float64 = 0.0
    for i in range(n):
        s += (a[i] - ma) * (b[i] - mb)
    return s / Float64(n)


fn _var(data: List[Float64]) -> Float64:
    var n = len(data)
    if n < 2:
        return 0.0
    var m = _mean(data)
    var ss: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        ss += d * d
    return ss / Float64(n)


# ── value_at_risk ─────────────────────────────────────────────────────────────


fn value_at_risk(returns: List[Float64], confidence: Float64) -> Float64:
    """Historical VaR at given confidence level (e.g. 0.95).

    Returns the loss at the (1-confidence) percentile of returns.
    Negative return = loss, so VaR is the negative of that percentile.
    """
    var n = len(returns)
    if n == 0:
        return 0.0
    var sorted = _sort_copy(returns)
    var idx_f = (1.0 - confidence) * Float64(n - 1)
    var lo = Int(idx_f)
    var hi = lo + 1
    if hi >= n:
        return -sorted[n - 1]
    var frac = idx_f - Float64(lo)
    var val = sorted[lo] * (1.0 - frac) + sorted[hi] * frac
    return -val


# ── conditional_var ───────────────────────────────────────────────────────────


fn conditional_var(returns: List[Float64], confidence: Float64) -> Float64:
    """CVaR (Expected Shortfall): average of returns below VaR threshold."""
    var n = len(returns)
    if n == 0:
        return 0.0
    var var_val = value_at_risk(returns, confidence)
    var threshold = -var_val  # The return level
    var total: Float64 = 0.0
    var count: Int = 0
    for i in range(n):
        if returns[i] <= threshold:
            total += returns[i]
            count += 1
    if count == 0:
        return var_val
    return -(total / Float64(count))


# ── max_drawdown ──────────────────────────────────────────────────────────────


fn max_drawdown(values: List[Float64]) -> Float64:
    """Maximum drawdown from peak to trough (as fraction)."""
    var n = len(values)
    if n < 2:
        return 0.0
    var peak = values[0]
    var max_dd: Float64 = 0.0
    for i in range(1, n):
        if values[i] > peak:
            peak = values[i]
        var dd = (peak - values[i]) / peak if peak > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ── drawdown_series ───────────────────────────────────────────────────────────


fn drawdown_series(values: List[Float64]) -> List[Float64]:
    """Drawdown at each point (fraction below running peak)."""
    var n = len(values)
    var result = List[Float64]()
    if n == 0:
        return result^
    var peak = values[0]
    for i in range(n):
        if values[i] > peak:
            peak = values[i]
        var dd = (peak - values[i]) / peak if peak > 0.0 else 0.0
        result.append(dd)
    return result^


# ── sortino_ratio ─────────────────────────────────────────────────────────────


fn sortino_ratio(returns: List[Float64], target: Float64 = 0.0) -> Float64:
    """Sortino ratio: (mean - target) / downside_std."""
    var m = _mean(returns)
    var dd = downside_deviation(returns, target)
    if dd < 1e-15:
        return 0.0
    return (m - target) / dd


# ── sharpe_ratio ──────────────────────────────────────────────────────────────


fn sharpe_ratio(returns: List[Float64], risk_free: Float64 = 0.0) -> Float64:
    """Sharpe ratio: (mean - rf) / std."""
    var m = _mean(returns)
    var s = _std(returns)
    if s < 1e-15:
        return 0.0
    return (m - risk_free) / s


# ── beta ──────────────────────────────────────────────────────────────────────


fn beta(asset_returns: List[Float64], market_returns: List[Float64]) -> Float64:
    """Beta = cov(asset, market) / var(market)."""
    var v = _var(market_returns)
    if v < 1e-15:
        return 0.0
    return _cov(asset_returns, market_returns) / v


# ── alpha ─────────────────────────────────────────────────────────────────────


fn alpha(
    asset_returns: List[Float64],
    market_returns: List[Float64],
    risk_free: Float64 = 0.0,
) -> Float64:
    """Jensen's alpha: mean(asset) - rf - beta*(mean(market) - rf)."""
    var b = beta(asset_returns, market_returns)
    var ma = _mean(asset_returns)
    var mm = _mean(market_returns)
    return ma - risk_free - b * (mm - risk_free)


# ── information_ratio ─────────────────────────────────────────────────────────


fn information_ratio(returns: List[Float64], benchmark: List[Float64]) -> Float64:
    """Information ratio: mean(excess) / std(excess)."""
    var n = len(returns)
    if n == 0:
        return 0.0
    var excess = List[Float64]()
    for i in range(n):
        excess.append(returns[i] - benchmark[i])
    var m = _mean(excess)
    var s = _std(excess)
    if s < 1e-15:
        return 0.0
    return m / s


# ── calmar_ratio ──────────────────────────────────────────────────────────────


fn calmar_ratio(returns: List[Float64], values: List[Float64]) -> Float64:
    """Calmar ratio: annualized_return / max_drawdown. Annualize = mean*252."""
    var mdd = max_drawdown(values)
    if mdd < 1e-15:
        return 0.0
    var ann_ret = _mean(returns) * 252.0
    return ann_ret / mdd


# ── downside_deviation ────────────────────────────────────────────────────────


fn downside_deviation(returns: List[Float64], target: Float64 = 0.0) -> Float64:
    """Downside deviation: sqrt(mean(min(r-target, 0)²))."""
    var n = len(returns)
    if n == 0:
        return 0.0
    var ss: Float64 = 0.0
    for i in range(n):
        var d = returns[i] - target
        if d < 0.0:
            ss += d * d
    return sqrt(ss / Float64(n))
