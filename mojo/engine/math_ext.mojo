"""
math_ext.mojo — Extended math and statistics. Zero Python imports.
Replaces: Python statistics module, scipy.stats basic functions.

Consolidates and extends statistical functions previously scattered across
expr.mojo (erf, norm_cdf, gamma) and stats.mojo (mean, variance).

Public API:
  Descriptive: mean, median, mode_approx, stdev, variance, skewness, kurtosis,
               covariance, correlation
  Percentiles: percentile, quantile, iqr
  Tests:       z_score, t_statistic, chi_squared
  Special:     erf, norm_cdf, norm_pdf, norm_ppf, gamma_fn, beta_fn, log_gamma
"""
from std.math import sqrt, exp, log, abs as fabs, pow, sin


# ── Internal sort (copy from stats.mojo to avoid circular deps) ──────────────


fn _ins_sort(mut a: List[Float64], lo: Int, hi: Int):
    for i in range(lo + 1, hi + 1):
        var k = a[i]
        var j = i - 1
        while j >= lo and a[j] > k:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = k


fn _sort_copy(data: List[Float64]) -> List[Float64]:
    """Return a sorted copy of data."""
    var sorted = List[Float64]()
    for i in range(len(data)):
        sorted.append(data[i])
    var n = len(sorted)
    if n <= 1:
        return sorted^
    _ins_sort(sorted, 0, n - 1)
    return sorted^


# ── Constants ─────────────────────────────────────────────────────────────────

comptime _PI = 3.141592653589793
comptime _SQRT_2PI = 2.5066282746310002
comptime _SQRT_2 = 1.4142135623730951
comptime _LN_SQRT_2PI = 0.9189385332046727


# ── Descriptive statistics ────────────────────────────────────────────────────


fn mean(data: List[Float64]) -> Float64:
    """Arithmetic mean."""
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
    return s / Float64(n)


fn median(data: List[Float64]) -> Float64:
    """Median (middle value). Copies and sorts."""
    var n = len(data)
    if n == 0:
        return 0.0
    var sorted = _sort_copy(data)
    if n % 2 == 1:
        return sorted[n // 2]
    return (sorted[n // 2 - 1] + sorted[n // 2]) / 2.0


fn mode_approx(data: List[Float64], bins: Int = 100) -> Float64:
    """Approximate mode using histogram binning."""
    var n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]

    var lo = data[0]
    var hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]

    if lo == hi:
        return lo

    var width = (hi - lo) / Float64(bins)
    var counts = List[Int]()
    for i in range(bins):
        counts.append(0)

    for i in range(n):
        var b = Int((data[i] - lo) / width)
        if b >= bins:
            b = bins - 1
        if b < 0:
            b = 0
        counts[b] = counts[b] + 1

    var max_count = 0
    var max_bin = 0
    for i in range(bins):
        if counts[i] > max_count:
            max_count = counts[i]
            max_bin = i

    return lo + (Float64(max_bin) + 0.5) * width


fn stdev(data: List[Float64]) -> Float64:
    """Sample standard deviation (ddof=1)."""
    return sqrt(variance(data))


fn variance(data: List[Float64]) -> Float64:
    """Sample variance (ddof=1)."""
    var n = len(data)
    if n <= 1:
        return 0.0
    var m = mean(data)
    var s: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        s += d * d
    return s / Float64(n - 1)


fn skewness(data: List[Float64]) -> Float64:
    """Sample skewness (Fisher's definition)."""
    var n = len(data)
    if n < 3:
        return 0.0
    var m = mean(data)
    var sd = stdev(data)
    if sd == 0.0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        var z = (data[i] - m) / sd
        s += z * z * z
    var nf = Float64(n)
    return (nf / ((nf - 1.0) * (nf - 2.0))) * s


fn kurtosis(data: List[Float64]) -> Float64:
    """Sample excess kurtosis (Fisher's definition)."""
    var n = len(data)
    if n < 4:
        return 0.0
    var m = mean(data)
    var sd = stdev(data)
    if sd == 0.0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        var z = (data[i] - m) / sd
        s += z * z * z * z
    var nf = Float64(n)
    var num = nf * (nf + 1.0) * s
    var den = (nf - 1.0) * (nf - 2.0) * (nf - 3.0)
    var correction = 3.0 * (nf - 1.0) * (nf - 1.0) / ((nf - 2.0) * (nf - 3.0))
    return num / den - correction


fn covariance(x: List[Float64], y: List[Float64]) -> Float64:
    """Sample covariance between two lists."""
    var n = len(x)
    if len(y) < n:
        n = len(y)
    if n <= 1:
        return 0.0
    var mx = mean(x)
    var my = mean(y)
    var s: Float64 = 0.0
    for i in range(n):
        s += (x[i] - mx) * (y[i] - my)
    return s / Float64(n - 1)


fn correlation(x: List[Float64], y: List[Float64]) -> Float64:
    """Pearson correlation coefficient."""
    var n = len(x)
    if len(y) < n:
        n = len(y)
    if n <= 1:
        return 0.0
    var mx = mean(x)
    var my = mean(y)
    var sxy: Float64 = 0.0
    var sxx: Float64 = 0.0
    var syy: Float64 = 0.0
    for i in range(n):
        var dx = x[i] - mx
        var dy = y[i] - my
        sxy += dx * dy
        sxx += dx * dx
        syy += dy * dy
    var denom = sqrt(sxx * syy)
    if denom == 0.0:
        return 0.0
    return sxy / denom


# ── Percentiles and quantiles ─────────────────────────────────────────────────


fn percentile(data: List[Float64], p: Float64) -> Float64:
    """p-th percentile (0-100). Linear interpolation."""
    return quantile(data, p / 100.0)


fn quantile(data: List[Float64], q: Float64) -> Float64:
    """q-th quantile (0-1). Linear interpolation."""
    var n = len(data)
    if n == 0:
        return 0.0
    if n == 1:
        return data[0]

    var sorted = _sort_copy(data)

    var qq = q
    if qq < 0.0:
        qq = 0.0
    if qq > 1.0:
        qq = 1.0

    var idx = qq * Float64(n - 1)
    var lo_idx = Int(idx)
    if lo_idx >= n - 1:
        return sorted[n - 1]
    if lo_idx < 0:
        return sorted[0]

    var frac = idx - Float64(lo_idx)
    return sorted[lo_idx] * (1.0 - frac) + sorted[lo_idx + 1] * frac


fn iqr(data: List[Float64]) -> Float64:
    """Interquartile range (Q3 - Q1)."""
    return quantile(data, 0.75) - quantile(data, 0.25)


# ── Statistical tests ──────────────────────────────────────────────────────────


fn z_score(value: Float64, mu: Float64, sigma: Float64) -> Float64:
    """Standard score (z-score)."""
    if sigma == 0.0:
        return 0.0
    return (value - mu) / sigma


fn t_statistic(sample_mean: Float64, pop_mean: Float64, sample_std: Float64, n: Int) -> Float64:
    """One-sample t-statistic."""
    if n <= 0 or sample_std == 0.0:
        return 0.0
    return (sample_mean - pop_mean) / (sample_std / sqrt(Float64(n)))


fn chi_squared(observed: List[Float64], expected: List[Float64]) -> Float64:
    """Chi-squared test statistic."""
    var n = len(observed)
    if len(expected) < n:
        n = len(expected)
    var s: Float64 = 0.0
    for i in range(n):
        if expected[i] != 0.0:
            var d = observed[i] - expected[i]
            s += d * d / expected[i]
    return s


# ── Special functions ──────────────────────────────────────────────────────────


fn erf(x: Float64) -> Float64:
    """Error function (Abramowitz & Stegun approximation, max error ~1.5e-7)."""
    var t = 1.0 / (1.0 + 0.3275911 * fabs(x))
    var y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * exp(-x * x)
    if x >= 0.0:
        return y
    return -y


fn norm_cdf(x: Float64) -> Float64:
    """Standard normal CDF via erf approximation."""
    return 0.5 * (1.0 + erf(x / _SQRT_2))


fn norm_pdf(x: Float64) -> Float64:
    """Standard normal PDF."""
    return exp(-0.5 * x * x) / _SQRT_2PI


fn norm_ppf(p: Float64) -> Float64:
    """Standard normal quantile function (inverse CDF / probit).

    Uses rational approximation by Peter Acklam.
    Accurate to ~1.15e-9 for p in (0, 1).
    """
    if p <= 0.0:
        return -1e300
    if p >= 1.0:
        return 1e300
    if p == 0.5:
        return 0.0

    # Coefficients for rational approximation
    var a1: Float64 = -3.969683028665376e+01
    var a2: Float64 = 2.209460984245205e+02
    var a3: Float64 = -2.759285104469687e+02
    var a4: Float64 = 1.383577518672690e+02
    var a5: Float64 = -3.066479806614716e+01
    var a6: Float64 = 2.506628277459239e+00

    var b1: Float64 = -5.447609879822406e+01
    var b2: Float64 = 1.615858368580409e+02
    var b3: Float64 = -1.556989798598866e+02
    var b4: Float64 = 6.680131188771972e+01
    var b5: Float64 = -1.328068155288572e+01

    var c1: Float64 = -7.784894002430293e-03
    var c2: Float64 = -3.223964580411365e-01
    var c3: Float64 = -2.400758277161838e+00
    var c4: Float64 = -2.549732539343734e+00
    var c5: Float64 = 4.374664141464968e+00
    var c6: Float64 = 2.938163982698783e+00

    var d1: Float64 = 7.784695709041462e-03
    var d2: Float64 = 3.224671290700398e-01
    var d3: Float64 = 2.445134137142996e+00
    var d4: Float64 = 3.754408661907416e+00

    var p_low: Float64 = 0.02425
    var p_high: Float64 = 1.0 - 0.02425

    if p < p_low:
        var q = sqrt(-2.0 * log(p))
        return (((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)
    elif p <= p_high:
        var q = p - 0.5
        var r = q * q
        return (((((a1 * r + a2) * r + a3) * r + a4) * r + a5) * r + a6) * q / (((((b1 * r + b2) * r + b3) * r + b4) * r + b5) * r + 1.0)
    else:
        var q = sqrt(-2.0 * log(1.0 - p))
        return -(((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)


fn log_gamma(x: Float64) -> Float64:
    """Log-gamma function (Lanczos approximation)."""
    if x <= 0.0:
        return 1e300

    var xx = x
    if xx < 0.5:
        return log(_PI / sin(_PI * xx)) - log_gamma(1.0 - xx)

    xx = xx - 1.0
    var b = xx + 7.5
    var c: Float64 = 0.99999999999980993
    c += 676.5203681218851 / (xx + 1.0)
    c += -1259.1392167224028 / (xx + 2.0)
    c += 771.32342877765313 / (xx + 3.0)
    c += -176.61502916214059 / (xx + 4.0)
    c += 12.507343278686905 / (xx + 5.0)
    c += -0.13857109526572012 / (xx + 6.0)
    c += 9.9843695780195716e-6 / (xx + 7.0)
    c += 1.5056327351493116e-7 / (xx + 8.0)

    return _LN_SQRT_2PI + (xx + 0.5) * log(b) - b + log(c)


fn gamma_fn(x: Float64) -> Float64:
    """Gamma function (Lanczos approximation)."""
    if x < 0.5:
        return _PI / (sin(_PI * x) * gamma_fn(1.0 - x))
    var xx = x - 1.0
    var b = xx + 7.5
    var c: Float64 = 0.99999999999980993
    c += 676.5203681218851 / (xx + 1.0)
    c += -1259.1392167224028 / (xx + 2.0)
    c += 771.32342877765313 / (xx + 3.0)
    c += -176.61502916214059 / (xx + 4.0)
    c += 12.507343278686905 / (xx + 5.0)
    c += -0.13857109526572012 / (xx + 6.0)
    c += 9.9843695780195716e-6 / (xx + 7.0)
    c += 1.5056327351493116e-7 / (xx + 8.0)
    return sqrt(2.0 * _PI) * pow(b, xx + 0.5) * exp(-b) * c


fn beta_fn(a: Float64, b: Float64) -> Float64:
    """Beta function = Gamma(a)*Gamma(b)/Gamma(a+b)."""
    return exp(log_gamma(a) + log_gamma(b) - log_gamma(a + b))
