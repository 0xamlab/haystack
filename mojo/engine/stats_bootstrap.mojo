"""
stats_bootstrap.mojo — Bootstrap statistics. Zero Python imports.

Replaces scipy.stats bootstrap, scikit-learn resampling, and custom
bootstrap code with pure Mojo implementations of bootstrap CI, bias,
standard error, permutation tests, jackknife, and BCa intervals.

Public API:
  bootstrap_replicate  — generate one bootstrap replicate
  bootstrap_mean_ci    — bootstrap CI for mean
  bootstrap_std_ci     — bootstrap CI for standard deviation
  bootstrap_median_ci  — bootstrap CI for median
  bootstrap_bias       — bootstrap bias estimate
  bootstrap_se         — bootstrap standard error
  bootstrap_test       — bootstrap permutation test p-value
  jackknife_mean       — jackknife leave-one-out means
  jackknife_se         — jackknife standard error of mean
  bca_correction       — BCa confidence interval for mean
"""

from std.random import random_float64
from std.math import abs as fabs, sqrt, log


# ── helpers ──────────────────────────────────────────────────────────────────


fn _sort_floats(mut arr: List[Float64]):
    """Insertion sort for float list."""
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


fn _median(data: List[Float64]) -> Float64:
    var n = len(data)
    if n == 0:
        return 0.0
    var sorted_d = List[Float64]()
    for i in range(n):
        sorted_d.append(data[i])
    _sort_floats(sorted_d)
    if n % 2 == 1:
        return sorted_d[n // 2]
    return (sorted_d[n // 2 - 1] + sorted_d[n // 2]) / 2.0


fn _std(data: List[Float64]) -> Float64:
    var n = len(data)
    if n < 2:
        return 0.0
    var m = _mean(data)
    var ss: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        ss += d * d
    return sqrt(ss / Float64(n - 1))


# ── bootstrap_replicate ─────────────────────────────────────────────────────


fn bootstrap_replicate(data: List[Float64]) -> List[Float64]:
    """Generate one bootstrap replicate (sample with replacement, same size)."""
    var n = len(data)
    var result = List[Float64]()
    for _ in range(n):
        var idx = Int(random_float64() * Float64(n))
        if idx >= n:
            idx = n - 1
        result.append(data[idx])
    return result^


# ── bootstrap_mean_ci ────────────────────────────────────────────────────────


fn bootstrap_mean_ci(
    data: List[Float64], n_bootstrap: Int, confidence: Float64 = 0.95
) -> List[Float64]:
    """Bootstrap confidence interval for mean. Returns [lower, upper]."""
    if len(data) == 0 or n_bootstrap <= 0:
        return List[Float64]()
    var nb = n_bootstrap
    if nb > 10000:
        nb = 10000  # ceiling: the percentile sort below is O(nb^2)
    var means = List[Float64]()
    for _ in range(nb):
        var rep = bootstrap_replicate(data)
        means.append(_mean(rep))
    _sort_floats(means)
    var alpha = (1.0 - confidence) / 2.0
    var lo_idx = Int(alpha * Float64(nb))
    var hi_idx = Int((1.0 - alpha) * Float64(nb))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= nb:
        hi_idx = nb - 1
    var result = List[Float64]()
    result.append(means[lo_idx])
    result.append(means[hi_idx])
    return result^


# ── bootstrap_std_ci ─────────────────────────────────────────────────────────


fn bootstrap_std_ci(
    data: List[Float64], n_bootstrap: Int, confidence: Float64 = 0.95
) -> List[Float64]:
    """Bootstrap CI for standard deviation."""
    if len(data) == 0 or n_bootstrap <= 0:
        return List[Float64]()
    var nb = n_bootstrap
    if nb > 10000:
        nb = 10000  # ceiling: the percentile sort below is O(nb^2)
    var stds = List[Float64]()
    for _ in range(nb):
        var rep = bootstrap_replicate(data)
        stds.append(_std(rep))
    _sort_floats(stds)
    var alpha = (1.0 - confidence) / 2.0
    var lo_idx = Int(alpha * Float64(nb))
    var hi_idx = Int((1.0 - alpha) * Float64(nb))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= nb:
        hi_idx = nb - 1
    var result = List[Float64]()
    result.append(stds[lo_idx])
    result.append(stds[hi_idx])
    return result^


# ── bootstrap_median_ci ──────────────────────────────────────────────────────


fn bootstrap_median_ci(
    data: List[Float64], n_bootstrap: Int, confidence: Float64 = 0.95
) -> List[Float64]:
    """Bootstrap CI for median."""
    if len(data) == 0 or n_bootstrap <= 0:
        return List[Float64]()
    var nb = n_bootstrap
    if nb > 10000:
        nb = 10000  # ceiling: the percentile sort below is O(nb^2)
    var medians = List[Float64]()
    for _ in range(nb):
        var rep = bootstrap_replicate(data)
        medians.append(_median(rep))
    _sort_floats(medians)
    var alpha = (1.0 - confidence) / 2.0
    var lo_idx = Int(alpha * Float64(nb))
    var hi_idx = Int((1.0 - alpha) * Float64(nb))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= nb:
        hi_idx = nb - 1
    var result = List[Float64]()
    result.append(medians[lo_idx])
    result.append(medians[hi_idx])
    return result^


# ── bootstrap_bias ───────────────────────────────────────────────────────────


fn bootstrap_bias(
    data: List[Float64], n_bootstrap: Int, stat_type: Int = 0
) -> Float64:
    """Bootstrap bias estimate: E[θ*] - θ. stat_type: 0=mean, 1=median."""
    var orig_stat: Float64 = 0.0
    if stat_type == 1:
        orig_stat = _median(data)
    else:
        orig_stat = _mean(data)
    var boot_stats = List[Float64]()
    for _ in range(n_bootstrap):
        var rep = bootstrap_replicate(data)
        if stat_type == 1:
            boot_stats.append(_median(rep))
        else:
            boot_stats.append(_mean(rep))
    var boot_mean = _mean(boot_stats)
    return boot_mean - orig_stat


# ── bootstrap_se ─────────────────────────────────────────────────────────────


fn bootstrap_se(
    data: List[Float64], n_bootstrap: Int, stat_type: Int = 0
) -> Float64:
    """Bootstrap standard error of statistic."""
    var boot_stats = List[Float64]()
    for _ in range(n_bootstrap):
        var rep = bootstrap_replicate(data)
        if stat_type == 1:
            boot_stats.append(_median(rep))
        else:
            boot_stats.append(_mean(rep))
    return _std(boot_stats)


# ── bootstrap_test ───────────────────────────────────────────────────────────


fn bootstrap_test(
    data1: List[Float64], data2: List[Float64], n_bootstrap: Int
) -> Float64:
    """Bootstrap permutation test p-value: test if two groups have same mean."""
    var n1 = len(data1)
    var n2 = len(data2)
    var observed_diff = fabs(_mean(data1) - _mean(data2))

    # Pool the data
    var pooled = List[Float64]()
    for i in range(n1):
        pooled.append(data1[i])
    for i in range(n2):
        pooled.append(data2[i])
    var n_total = n1 + n2

    var count = 0
    for _ in range(n_bootstrap):
        # Shuffle pooled by generating random permutation
        var perm = List[Float64]()
        for i in range(n_total):
            perm.append(pooled[i])
        # Fisher-Yates shuffle
        for i in range(n_total - 1, 0, -1):
            var j = Int(random_float64() * Float64(i + 1))
            if j > i:
                j = i
            var tmp = perm[i]
            perm[i] = perm[j]
            perm[j] = tmp

        # Split into two groups
        var sum1: Float64 = 0.0
        for i in range(n1):
            sum1 += perm[i]
        var sum2: Float64 = 0.0
        for i in range(n1, n_total):
            sum2 += perm[i]
        var diff = fabs(sum1 / Float64(n1) - sum2 / Float64(n2))
        if diff >= observed_diff:
            count += 1
    return Float64(count) / Float64(n_bootstrap)


# ── jackknife_mean ───────────────────────────────────────────────────────────


fn jackknife_mean(data: List[Float64]) -> List[Float64]:
    """Jackknife leave-one-out means."""
    var n = len(data)
    var total = _mean(data) * Float64(n)
    var result = List[Float64]()
    for i in range(n):
        result.append((total - data[i]) / Float64(n - 1))
    return result^


# ── jackknife_se ─────────────────────────────────────────────────────────────


fn jackknife_se(data: List[Float64]) -> Float64:
    """Jackknife standard error of the mean."""
    var n = len(data)
    if n < 2:
        return 0.0
    var jk_means = jackknife_mean(data)
    var jk_bar = _mean(jk_means)
    var ss: Float64 = 0.0
    for i in range(n):
        var d = jk_means[i] - jk_bar
        ss += d * d
    return sqrt(Float64(n - 1) / Float64(n) * ss)


# ── bca_correction ───────────────────────────────────────────────────────────


fn bca_correction(
    data: List[Float64], n_bootstrap: Int, confidence: Float64 = 0.95
) -> List[Float64]:
    """BCa (bias-corrected and accelerated) CI for mean."""
    if len(data) == 0 or n_bootstrap <= 0:
        return List[Float64]()
    var nb = n_bootstrap
    if nb > 10000:
        nb = 10000  # ceiling: the percentile sort below is O(nb^2)
    var n = len(data)
    var orig_mean = _mean(data)

    # Generate bootstrap distribution
    var boot_means = List[Float64]()
    for _ in range(nb):
        var rep = bootstrap_replicate(data)
        boot_means.append(_mean(rep))
    _sort_floats(boot_means)

    # Bias correction factor z0
    var count_below = 0
    for i in range(nb):
        if boot_means[i] < orig_mean:
            count_below += 1
    var p0 = Float64(count_below) / Float64(nb)
    if p0 <= 0.0:
        p0 = 0.5 / Float64(nb)
    if p0 >= 1.0:
        p0 = 1.0 - 0.5 / Float64(nb)
    # Approximate z0 using simple inverse normal approx
    # Using rational approximation for probit
    var z0 = _probit(p0)

    # Acceleration factor a
    var jk_means = jackknife_mean(data)
    var jk_bar = _mean(jk_means)
    var num: Float64 = 0.0
    var den: Float64 = 0.0
    for i in range(n):
        var d = jk_bar - jk_means[i]
        num += d * d * d
        den += d * d
    var a_hat: Float64 = 0.0
    if den > 1e-15:
        a_hat = num / (6.0 * den * sqrt(den))

    # Adjusted percentiles
    var alpha = (1.0 - confidence) / 2.0
    var z_alpha = _probit(alpha)
    var z_1alpha = _probit(1.0 - alpha)

    var a1 = z0 + (z0 + z_alpha) / (1.0 - a_hat * (z0 + z_alpha))
    var a2 = z0 + (z0 + z_1alpha) / (1.0 - a_hat * (z0 + z_1alpha))

    var p1 = _normcdf(a1)
    var p2 = _normcdf(a2)

    var lo_idx = Int(p1 * Float64(nb))
    var hi_idx = Int(p2 * Float64(nb))
    if lo_idx < 0:
        lo_idx = 0
    if hi_idx >= nb:
        hi_idx = nb - 1
    if lo_idx > hi_idx:
        lo_idx = 0
        hi_idx = nb - 1

    var result = List[Float64]()
    result.append(boot_means[lo_idx])
    result.append(boot_means[hi_idx])
    return result^


fn _probit(p: Float64) -> Float64:
    """Approximate inverse normal CDF (probit). Abramowitz & Stegun."""
    # Clamp
    var pp = p
    if pp < 1e-10:
        pp = 1e-10
    if pp > 1.0 - 1e-10:
        pp = 1.0 - 1e-10
    if pp == 0.5:
        return 0.0
    var sign: Float64 = 1.0
    var q = pp
    if pp > 0.5:
        q = 1.0 - pp
        sign = -1.0
    else:
        sign = 1.0
    var t = sqrt(-2.0 * log(q))
    # Rational approximation
    var c0: Float64 = 2.515517
    var c1: Float64 = 0.802853
    var c2: Float64 = 0.010328
    var d1: Float64 = 1.432788
    var d2: Float64 = 0.189269
    var d3: Float64 = 0.001308
    var z = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
    return -sign * z


fn _normcdf(x: Float64) -> Float64:
    """Approximate normal CDF using logistic approximation."""
    # Approximation: Φ(x) ≈ 1 / (1 + exp(-1.7 * x))
    # Better: use Abramowitz & Stegun
    if x > 8.0:
        return 1.0
    if x < -8.0:
        return 0.0
    var t = 1.0 / (1.0 + 0.2316419 * fabs(x))
    var d = 0.3989422804014327  # 1/sqrt(2*pi)
    var p = d * _exp_neg_half_x2(x) * t * (
        0.319381530
        + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    if x >= 0.0:
        return 1.0 - p
    return p


fn _exp_neg_half_x2(x: Float64) -> Float64:
    """Compute exp(-x²/2) using log/exp from std.math."""
    from std.math import exp

    return exp(-0.5 * x * x)
