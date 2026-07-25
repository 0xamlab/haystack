"""
model_compare.mojo — Statistically rigorous paired model comparison. Zero Python imports.

Replaces scipy.stats (binomtest/McNemar), statsmodels (Diebold-Mariano),
and hand-rolled A/B comparisons on accuracy scalars with pure Mojo paired
bootstrap CIs, exact McNemar, and DM forecast-comparison tests.

Public API:
  paired_bootstrap_diff_ci — paired bootstrap percentile CI on mean(a-b)
  mcnemar_exact_p          — exact two-sided binomial McNemar p-value
  diebold_mariano          — DM test on squared-error loss differentials (Newey-West)
  sharpe_diff_bootstrap_ci — paired bootstrap CI on Sharpe(a) - Sharpe(b)
"""

from std.math import sqrt, log, exp, erf, abs as fabs


# ── result structs ───────────────────────────────────────────────────────────


struct DiffCI(Copyable, Movable):
    """Confidence interval on a difference: [lo, hi] plus the point estimate."""

    var lo: Float64
    var hi: Float64
    var point: Float64

    fn __init__(out self, lo: Float64 = 0.0, hi: Float64 = 0.0, point: Float64 = 0.0):
        self.lo = lo
        self.hi = hi
        self.point = point


struct DMResult(Copyable, Movable):
    """Diebold-Mariano test result: statistic and two-sided normal p-value."""

    var dm_stat: Float64
    var p_two_sided: Float64

    fn __init__(out self, dm_stat: Float64 = 0.0, p_two_sided: Float64 = 1.0):
        self.dm_stat = dm_stat
        self.p_two_sided = p_two_sided


# ── helpers ──────────────────────────────────────────────────────────────────


fn _sort_floats(mut arr: List[Float64]):
    """Insertion sort for float list (bootstrap replicate arrays)."""
    var n = len(arr)
    for i in range(1, n):
        var key = arr[i]
        var j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key


fn _mean(data: List[Float64]) -> Float64:
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
    return s / Float64(n)


fn _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


fn _xr_f64(state: UInt64) -> Float64:
    return Float64(state >> 11) * (1.0 / 9007199254740992.0)


fn _seed_state(seed: Int) -> UInt64:
    """Mix an explicit user seed into a well-dispersed xorshift64 state."""
    var s = UInt64(seed) * UInt64(6364136223846793005) + UInt64(0xA341316CAABB3D29)
    s = _xorshift64(s)
    s = _xorshift64(s)
    s = _xorshift64(s)
    return s


fn _normal_cdf(x: Float64) -> Float64:
    """Standard normal CDF via erf: Φ(x) = (1 + erf(x/√2)) / 2."""
    return 0.5 * (1.0 + erf(x / 1.4142135623730951))


fn _percentile_bounds(mut boot: List[Float64], alpha: Float64) -> List[Float64]:
    """Percentile-method bounds [alpha/2, 1-alpha/2] from a bootstrap distribution.
    Sorts boot in place; returns [lo, hi]."""
    var n_boot = len(boot)
    var result = List[Float64]()
    if n_boot == 0:
        result.append(0.0)
        result.append(0.0)
        return result^
    _sort_floats(boot)
    var half = alpha / 2.0
    var lo_idx = Int(half * Float64(n_boot))
    var hi_idx = Int((1.0 - half) * Float64(n_boot))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= n_boot:
        hi_idx = n_boot - 1
    if lo_idx > hi_idx:
        lo_idx = hi_idx
    result.append(boot[lo_idx])
    result.append(boot[hi_idx])
    return result^


fn _pop_std(data: List[Float64]) -> Float64:
    """Population standard deviation (divide by n)."""
    var n = len(data)
    if n == 0:
        return 0.0
    var m = _mean(data)
    var ss: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        ss += d * d
    return sqrt(ss / Float64(n))


fn _sharpe(data: List[Float64]) -> Float64:
    """Sharpe ratio = mean / population std; 0.0 when std is 0."""
    var s = _pop_std(data)
    if s <= 0.0:
        return 0.0
    return _mean(data) / s


fn _log_binom_cdf_terms(n: Int, k_lo: Int, k_hi: Int) -> Float64:
    """Sum of Binomial(n, 0.5) pmf for k in [k_lo, k_hi], each term computed
    in log space: log pmf(k) = log C(n,k) - n·log(2), with log C built
    incrementally to avoid factorial overflow."""
    if n <= 0 or k_hi < k_lo:
        return 0.0
    var lo = k_lo
    if lo < 0:
        lo = 0
    var hi = k_hi
    if hi > n:
        hi = n
    var log_half_n = Float64(n) * log(2.0)  # -log(0.5^n)
    # log C(n, k) built incrementally from k = 0
    var log_c: Float64 = 0.0
    var total: Float64 = 0.0
    for k in range(0, hi + 1):
        if k > 0:
            log_c += log(Float64(n - k + 1)) - log(Float64(k))
        if k >= lo:
            total += exp(log_c - log_half_n)
    return total


# ── paired_bootstrap_diff_ci ─────────────────────────────────────────────────


fn paired_bootstrap_diff_ci(
    metric_a: List[Float64],
    metric_b: List[Float64],
    n_boot: Int,
    alpha: Float64,
    seed: Int,
) -> DiffCI:
    """Paired bootstrap percentile CI on mean(a - b).

    metric_a/metric_b are per-sample paired metric contributions (e.g. 1.0/0.0
    correctness per prediction, or per-trade pnl). Pairs are resampled with
    replacement together; CI is [alpha/2, 1-alpha/2] percentiles of the
    replicate means of (a - b). Deterministic given seed.
    """
    var n = len(metric_a)
    if len(metric_b) < n:
        n = len(metric_b)
    if n == 0 or n_boot <= 0:
        return DiffCI(0.0, 0.0, 0.0)

    var diffs = List[Float64](capacity=n)
    for i in range(n):
        diffs.append(metric_a[i] - metric_b[i])
    var point = _mean(diffs)

    var s = _seed_state(seed)
    var nf = Float64(n)
    var boot = List[Float64](capacity=n_boot)
    for _ in range(n_boot):
        var acc: Float64 = 0.0
        for _ in range(n):
            s = _xorshift64(s)
            var idx = Int(_xr_f64(s) * nf)
            if idx >= n:
                idx = n - 1
            acc += diffs[idx]
        boot.append(acc / nf)

    var bounds = _percentile_bounds(boot, alpha)
    return DiffCI(bounds[0], bounds[1], point)


# ── mcnemar_exact_p ──────────────────────────────────────────────────────────


fn mcnemar_exact_p(b01: Int, b10: Int) -> Float64:
    """Exact two-sided binomial McNemar test p-value.

    b01 = count of samples model A got wrong and model B got right;
    b10 = the converse. Under H0 the discordant counts follow
    Binomial(b01 + b10, 0.5). Two-sided:
      p = min(1, 2·min(P(X ≤ min(b01,b10)), P(X ≥ max(b01,b10)))).
    Returns 1.0 when there are no discordant pairs.
    """
    if b01 < 0 or b10 < 0:
        return 1.0
    var n = b01 + b10
    if n == 0:
        return 1.0
    var k_min = b01
    var k_max = b10
    if k_min > k_max:
        k_min = b10
        k_max = b01
    var p_low = _log_binom_cdf_terms(n, 0, k_min)  # P(X <= k_min)
    var p_high = _log_binom_cdf_terms(n, k_max, n)  # P(X >= k_max)
    var p_tail = p_low
    if p_high < p_tail:
        p_tail = p_high
    var p = 2.0 * p_tail
    if p > 1.0:
        p = 1.0
    return p


# ── diebold_mariano ──────────────────────────────────────────────────────────


fn diebold_mariano(err_a: List[Float64], err_b: List[Float64], h: Int) -> DMResult:
    """Diebold-Mariano forecast comparison test under squared-error loss.

    Loss differentials d_t = err_a[t]² - err_b[t]². Long-run variance of the
    mean uses Newey-West (Bartlett kernel) with lags 1..h-1 for forecast
    horizon h. Returns (dm_stat, two-sided normal-approx p). Zero-variance
    differentials (e.g. identical errors) return (0.0, 1.0).
    """
    var n = len(err_a)
    if len(err_b) < n:
        n = len(err_b)
    if n == 0:
        return DMResult(0.0, 1.0)

    var d = List[Float64](capacity=n)
    for i in range(n):
        d.append(err_a[i] * err_a[i] - err_b[i] * err_b[i])
    var d_bar = _mean(d)

    var nf = Float64(n)
    # gamma_0
    var gamma0: Float64 = 0.0
    for i in range(n):
        var dev = d[i] - d_bar
        gamma0 += dev * dev
    gamma0 /= nf

    # Newey-West long-run variance: gamma_0 + 2 * sum_{k=1}^{h-1} w_k gamma_k
    var lrv = gamma0
    var max_lag = h - 1
    if max_lag > n - 1:
        max_lag = n - 1
    if max_lag >= 1:
        var hf = Float64(h)
        for k in range(1, max_lag + 1):
            var gk: Float64 = 0.0
            for t in range(k, n):
                gk += (d[t] - d_bar) * (d[t - k] - d_bar)
            gk /= nf
            var w = 1.0 - Float64(k) / hf  # Bartlett weight
            lrv += 2.0 * w * gk

    if lrv <= 1e-15:
        return DMResult(0.0, 1.0)

    var dm = d_bar / sqrt(lrv / nf)
    var p = 2.0 * (1.0 - _normal_cdf(fabs(dm)))
    if p > 1.0:
        p = 1.0
    if p < 0.0:
        p = 0.0
    return DMResult(dm, p)


# ── sharpe_diff_bootstrap_ci ─────────────────────────────────────────────────


fn sharpe_diff_bootstrap_ci(
    returns_a: List[Float64],
    returns_b: List[Float64],
    n_boot: Int,
    alpha: Float64,
    seed: Int,
) -> DiffCI:
    """Paired bootstrap percentile CI on Sharpe(a) - Sharpe(b).

    Sharpe = mean / population std, no annualization (caller scales).
    Return pairs (returns_a[i], returns_b[i]) are resampled together so the
    dependence between the two strategies is preserved. Deterministic given
    seed.
    """
    var n = len(returns_a)
    if len(returns_b) < n:
        n = len(returns_b)
    if n == 0 or n_boot <= 0:
        return DiffCI(0.0, 0.0, 0.0)

    # Point estimate on the (aligned) originals.
    var a0 = List[Float64](capacity=n)
    var b0 = List[Float64](capacity=n)
    for i in range(n):
        a0.append(returns_a[i])
        b0.append(returns_b[i])
    var point = _sharpe(a0) - _sharpe(b0)

    var s = _seed_state(seed)
    var nf = Float64(n)
    var boot = List[Float64](capacity=n_boot)
    var rep_a = List[Float64](capacity=n)
    var rep_b = List[Float64](capacity=n)
    for _ in range(n):
        rep_a.append(0.0)
        rep_b.append(0.0)
    for _ in range(n_boot):
        for j in range(n):
            s = _xorshift64(s)
            var idx = Int(_xr_f64(s) * nf)
            if idx >= n:
                idx = n - 1
            rep_a[j] = returns_a[idx]
            rep_b[j] = returns_b[idx]
        boot.append(_sharpe(rep_a) - _sharpe(rep_b))

    var bounds = _percentile_bounds(boot, alpha)
    return DiffCI(bounds[0], bounds[1], point)
