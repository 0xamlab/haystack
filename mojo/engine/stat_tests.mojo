"""
stat_tests.mojo — Statistical hypothesis tests. Zero Python imports.
Replaces: scipy.stats.ks_2samp, ttest_1samp, ttest_ind, pearsonr, spearmanr

P-value approximations use asymptotic formulas:
  - KS test: Kolmogorov asymptotic distribution
  - t-test:  Incomplete beta function approximation
  - chi²:   Incomplete gamma function (regularized)

Public API:
  TestResult struct
  ks_test_2sample, ks_test_normal, t_test_1sample, t_test_2sample,
  chi_squared_test, anderson_darling_normal, shapiro_wilk_approx,
  pearson_r, spearman_r, pearson_r_strict, spearman_r_strict

NaN/Inf safety
--------------
`pearson_r`/`spearman_r` are EXISTING-FROZEN (see `data_quality/leakage.mojo`'s
"Frozen kernels called" section, which documents and relies on their exact current
return-value contract for `n < 3` and a zero denominator). Neither function checks
its input for NaN/±Inf, so a single non-finite value silently poisons the running
mean and the pair returns `CorrResult(NaN, NaN)` with every internal guard
(`denom == 0.0`, the r-clamps, `r2 >= 1.0`, the p-value clamps) failing to fire,
because none of those comparisons is ever true against NaN under IEEE-754.
`pearson_r_strict`/`spearman_r_strict` are additive, NaN/Inf-safe siblings that
validate first and raise a typed error naming which input list and which index held
the non-finite value, rather than changing `pearson_r`/`spearman_r` themselves.
"""
from std.math import sqrt, exp, log, abs as fabs, pow, sin, isnan, isinf


# ── Constants ─────────────────────────────────────────────────────────────────

comptime _PI = 3.141592653589793
comptime _SQRT_2 = 1.4142135623730951
comptime _SQRT_2PI = 2.5066282746310002
comptime _LN_SQRT_2PI = 0.9189385332046727


# ── Result struct ─────────────────────────────────────────────────────────────


struct TestResult(Copyable, Movable):
    """Result of a statistical hypothesis test."""
    var statistic: Float64   # test statistic value
    var p_value: Float64     # approximate p-value
    var reject_h0: Bool      # reject null at alpha=0.05?

    fn __init__(out self, statistic: Float64, p_value: Float64, reject_h0: Bool):
        self.statistic = statistic
        self.p_value = p_value
        self.reject_h0 = reject_h0


# ── Internal helpers ──────────────────────────────────────────────────────────


fn _erf(x: Float64) -> Float64:
    """Error function (Abramowitz & Stegun approximation)."""
    var t = 1.0 / (1.0 + 0.3275911 * fabs(x))
    var y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * exp(-x * x)
    if x >= 0.0:
        return y
    return -y


fn _norm_cdf(x: Float64) -> Float64:
    """Standard normal CDF."""
    return 0.5 * (1.0 + _erf(x / _SQRT_2))


fn _norm_pdf(x: Float64) -> Float64:
    """Standard normal PDF."""
    return exp(-0.5 * x * x) / _SQRT_2PI


fn _log_gamma(x: Float64) -> Float64:
    """Log-gamma function (Lanczos approximation)."""
    if x <= 0.0:
        return 1e300
    var xx = x
    if xx < 0.5:
        return log(_PI / sin(_PI * xx)) - _log_gamma(1.0 - xx)
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


fn _regularized_incomplete_beta(x: Float64, a: Float64, b: Float64) -> Float64:
    """Regularized incomplete beta function I_x(a,b) using continued fraction.
    Used for computing t-test p-values."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    # Use symmetry relation if x > (a+1)/(a+b+2)
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _regularized_incomplete_beta(1.0 - x, b, a)

    # Log of the prefactor: x^a * (1-x)^b / (a * B(a,b))
    var lbeta = _log_gamma(a) + _log_gamma(b) - _log_gamma(a + b)
    var front = exp(log(x) * a + log(1.0 - x) * b - lbeta) / a

    # Lentz's continued fraction algorithm
    var f: Float64 = 1.0
    var c: Float64 = 1.0
    var d: Float64 = 0.0

    for i in range(1, 201):
        var m = i // 2
        var numerator: Float64

        if i % 2 == 0:
            # Even term
            var mf = Float64(m)
            numerator = (mf * (b - mf) * x) / ((a + 2.0 * mf - 1.0) * (a + 2.0 * mf))
        else:
            # Odd term
            var mf = Float64(m)
            numerator = -((a + mf) * (a + b + mf) * x) / ((a + 2.0 * mf) * (a + 2.0 * mf + 1.0))

        d = 1.0 + numerator * d
        if fabs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d

        c = 1.0 + numerator / c
        if fabs(c) < 1e-30:
            c = 1e-30

        f *= c * d

        if fabs(c * d - 1.0) < 1e-10:
            break

    return front * (f - 1.0)


fn _t_cdf(t: Float64, df: Float64) -> Float64:
    """CDF of Student's t-distribution using incomplete beta function."""
    var x = df / (df + t * t)
    var ibeta = _regularized_incomplete_beta(x, df / 2.0, 0.5)
    if t >= 0.0:
        return 1.0 - 0.5 * ibeta
    else:
        return 0.5 * ibeta


fn _regularized_gamma_lower(s: Float64, x: Float64) -> Float64:
    """Lower regularized incomplete gamma function P(s, x) using series expansion.
    P(s, x) = gamma(s, x) / Gamma(s)
    Used for chi-squared p-values."""
    if x <= 0.0:
        return 0.0
    if x > s + 200.0:
        return 1.0  # asymptotic

    # Series expansion: P(s,x) = e^{-x} x^s / Gamma(s) * sum_{k=0}^inf x^k / (s*(s+1)*...*(s+k))
    var log_prefix = s * log(x) - x - _log_gamma(s)
    var prefix = exp(log_prefix)

    var sum_val: Float64 = 1.0 / s
    var term: Float64 = 1.0 / s
    for k in range(1, 300):
        term *= x / (s + Float64(k))
        sum_val += term
        if fabs(term) < 1e-12 * fabs(sum_val):
            break

    return prefix * sum_val


fn _chi2_cdf(x: Float64, df: Float64) -> Float64:
    """CDF of chi-squared distribution."""
    if x <= 0.0:
        return 0.0
    return _regularized_gamma_lower(df / 2.0, x / 2.0)


fn _ks_asymptotic_pvalue(d: Float64, n: Float64) -> Float64:
    """Asymptotic p-value for KS statistic.
    Uses the Kolmogorov distribution: P(D_n > d) ≈ 2 * sum_{k=1}^inf (-1)^{k-1} * exp(-2k²n*d²)
    """
    var lam = (sqrt(n) + 0.12 + 0.11 / sqrt(n)) * d
    if lam == 0.0:
        return 1.0

    var p: Float64 = 0.0
    for k in range(1, 101):
        var kf = Float64(k)
        var term = exp(-2.0 * kf * kf * lam * lam)
        if k % 2 == 0:
            p -= term
        else:
            p += term
    p = 2.0 * p

    if p < 0.0:
        p = 0.0
    if p > 1.0:
        p = 1.0
    return p


fn _insertion_sort(mut a: List[Float64]):
    """In-place insertion sort."""
    var n = len(a)
    for i in range(1, n):
        var k = a[i]
        var j = i - 1
        while j >= 0 and a[j] > k:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = k


fn _sort_copy(data: List[Float64]) -> List[Float64]:
    """Return a sorted copy."""
    var sorted = List[Float64]()
    for i in range(len(data)):
        sorted.append(data[i])
    _insertion_sort(sorted)
    return sorted^


fn _mean(data: List[Float64]) -> Float64:
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
    return s / Float64(n)


fn _stdev(data: List[Float64]) -> Float64:
    var n = len(data)
    if n <= 1:
        return 0.0
    var m = _mean(data)
    var s: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        s += d * d
    return sqrt(s / Float64(n - 1))


fn _variance(data: List[Float64]) -> Float64:
    var n = len(data)
    if n <= 1:
        return 0.0
    var m = _mean(data)
    var s: Float64 = 0.0
    for i in range(n):
        var d = data[i] - m
        s += d * d
    return s / Float64(n - 1)


# ── KS tests ─────────────────────────────────────────────────────────────────


fn ks_test_2sample(sample1: List[Float64], sample2: List[Float64]) -> TestResult:
    """Two-sample Kolmogorov-Smirnov test.
    Tests if two samples come from the same distribution.
    KS statistic = max |F1(x) - F2(x)| over all x."""
    var n1 = len(sample1)
    var n2 = len(sample2)
    if n1 == 0 or n2 == 0:
        return TestResult(0.0, 1.0, False)

    var s1 = _sort_copy(sample1)
    var s2 = _sort_copy(sample2)

    # Merge and compute maximum ECDF difference
    var d_max: Float64 = 0.0
    var i1 = 0
    var i2 = 0

    while i1 < n1 and i2 < n2:
        if s1[i1] < s2[i2]:
            i1 += 1
        elif s2[i2] < s1[i1]:
            i2 += 1
        else:
            # Equal values: advance both
            i1 += 1
            i2 += 1
        var ecdf1 = Float64(i1) / Float64(n1)
        var ecdf2 = Float64(i2) / Float64(n2)
        var diff = fabs(ecdf1 - ecdf2)
        if diff > d_max:
            d_max = diff

    # Effective sample size for the asymptotic formula
    var n_eff = Float64(n1 * n2) / Float64(n1 + n2)
    var p_val = _ks_asymptotic_pvalue(d_max, n_eff)

    return TestResult(d_max, p_val, p_val < 0.05)


fn ks_test_normal(sample: List[Float64]) -> TestResult:
    """One-sample KS test against normal distribution.
    Tests if sample comes from N(sample_mean, sample_std)."""
    var n = len(sample)
    if n == 0:
        return TestResult(0.0, 1.0, False)

    var sorted = _sort_copy(sample)
    var mu = _mean(sample)
    var sd = _stdev(sample)
    if sd == 0.0:
        sd = 1.0

    var d_max: Float64 = 0.0
    for i in range(n):
        var z = (sorted[i] - mu) / sd
        var cdf_val = _norm_cdf(z)
        var ecdf_upper = Float64(i + 1) / Float64(n)
        var ecdf_lower = Float64(i) / Float64(n)

        var d1 = fabs(ecdf_upper - cdf_val)
        var d2 = fabs(cdf_val - ecdf_lower)

        if d1 > d_max:
            d_max = d1
        if d2 > d_max:
            d_max = d2

    var p_val = _ks_asymptotic_pvalue(d_max, Float64(n))
    return TestResult(d_max, p_val, p_val < 0.05)


# ── t-tests ──────────────────────────────────────────────────────────────────


fn t_test_1sample(sample: List[Float64], mu0: Float64) -> TestResult:
    """One-sample t-test: test if sample mean equals mu0.
    t = (x̄ - μ₀) / (s / √n), df = n - 1"""
    var n = len(sample)
    if n < 2:
        return TestResult(0.0, 1.0, False)

    var m = _mean(sample)
    var s = _stdev(sample)
    if s == 0.0:
        if m == mu0:
            return TestResult(0.0, 1.0, False)
        else:
            return TestResult(1e10, 0.0, True)

    var t = (m - mu0) / (s / sqrt(Float64(n)))
    var df = Float64(n - 1)

    # Two-tailed p-value
    var p_val = 2.0 * (1.0 - _t_cdf(fabs(t), df))
    if p_val > 1.0:
        p_val = 1.0
    if p_val < 0.0:
        p_val = 0.0

    return TestResult(t, p_val, p_val < 0.05)


fn t_test_2sample(sample1: List[Float64], sample2: List[Float64]) -> TestResult:
    """Two-sample (independent) t-test: test if means are equal.
    Uses Welch's t-test (unequal variances).
    t = (x̄₁ - x̄₂) / √(s₁²/n₁ + s₂²/n₂)
    df from Welch-Satterthwaite equation."""
    var n1 = len(sample1)
    var n2 = len(sample2)
    if n1 < 2 or n2 < 2:
        return TestResult(0.0, 1.0, False)

    var m1 = _mean(sample1)
    var m2 = _mean(sample2)
    var v1 = _variance(sample1)
    var v2 = _variance(sample2)

    var se = sqrt(v1 / Float64(n1) + v2 / Float64(n2))
    if se == 0.0:
        if m1 == m2:
            return TestResult(0.0, 1.0, False)
        else:
            return TestResult(1e10, 0.0, True)

    var t = (m1 - m2) / se

    # Welch-Satterthwaite degrees of freedom
    var num = (v1 / Float64(n1) + v2 / Float64(n2)) * (v1 / Float64(n1) + v2 / Float64(n2))
    var den = (v1 * v1) / (Float64(n1 * n1) * Float64(n1 - 1)) + (v2 * v2) / (Float64(n2 * n2) * Float64(n2 - 1))
    var df: Float64
    if den > 0.0:
        df = num / den
    else:
        df = Float64(n1 + n2 - 2)

    var p_val = 2.0 * (1.0 - _t_cdf(fabs(t), df))
    if p_val > 1.0:
        p_val = 1.0
    if p_val < 0.0:
        p_val = 0.0

    return TestResult(t, p_val, p_val < 0.05)


# ── Chi-squared test ─────────────────────────────────────────────────────────


fn chi_squared_test(observed: List[Float64], expected: List[Float64]) -> TestResult:
    """Chi-squared goodness-of-fit test.
    χ² = Σ (O_i - E_i)² / E_i
    df = k - 1 where k is the number of categories."""
    var n = len(observed)
    if len(expected) < n:
        n = len(expected)
    if n == 0:
        return TestResult(0.0, 1.0, False)

    var chi2: Float64 = 0.0
    for i in range(n):
        if expected[i] > 0.0:
            var d = observed[i] - expected[i]
            chi2 += d * d / expected[i]

    var df = Float64(n - 1)
    if df < 1.0:
        df = 1.0

    # P-value: P(χ² > chi2) = 1 - CDF_chi2(chi2, df)
    var p_val = 1.0 - _chi2_cdf(chi2, df)
    if p_val < 0.0:
        p_val = 0.0
    if p_val > 1.0:
        p_val = 1.0

    return TestResult(chi2, p_val, p_val < 0.05)


# ── Anderson-Darling test for normality ───────────────────────────────────────


fn anderson_darling_normal(sample: List[Float64]) -> TestResult:
    """Anderson-Darling test for normality.
    A² = -n - (1/n) * Σ (2i-1)[ln(Φ(z_i)) + ln(1-Φ(z_{n+1-i}))]
    Modified statistic: A²* = A²(1 + 0.75/n + 2.25/n²)
    Critical values: 0.631 (15%), 0.752 (10%), 0.873 (5%), 1.035 (2.5%), 1.159 (1%)
    """
    var n = len(sample)
    if n < 3:
        return TestResult(0.0, 1.0, False)

    var sorted = _sort_copy(sample)
    var mu = _mean(sample)
    var sd = _stdev(sample)
    if sd == 0.0:
        return TestResult(0.0, 1.0, False)

    var nf = Float64(n)
    var s: Float64 = 0.0

    for i in range(n):
        var z = (sorted[i] - mu) / sd
        var cdf_i = _norm_cdf(z)
        # Clamp to avoid log(0)
        if cdf_i < 1e-15:
            cdf_i = 1e-15
        if cdf_i > 1.0 - 1e-15:
            cdf_i = 1.0 - 1e-15

        var z_rev = (sorted[n - 1 - i] - mu) / sd
        var cdf_rev = _norm_cdf(z_rev)
        if cdf_rev < 1e-15:
            cdf_rev = 1e-15
        if cdf_rev > 1.0 - 1e-15:
            cdf_rev = 1.0 - 1e-15

        var weight = Float64(2 * (i + 1) - 1)
        s += weight * (log(cdf_i) + log(1.0 - cdf_rev))

    var a2 = -nf - s / nf

    # Modified statistic
    var a2_star = a2 * (1.0 + 0.75 / nf + 2.25 / (nf * nf))

    # Approximate p-value using critical value interpolation
    # Based on D'Agostino & Stephens (1986)
    var p_val: Float64
    if a2_star < 0.2:
        p_val = 1.0 - exp(-13.436 + 101.14 * a2_star - 223.73 * a2_star * a2_star)
    elif a2_star < 0.34:
        p_val = 1.0 - exp(-8.318 + 42.796 * a2_star - 59.938 * a2_star * a2_star)
    elif a2_star < 0.6:
        p_val = exp(0.9177 - 4.279 * a2_star - 1.38 * a2_star * a2_star)
    elif a2_star < 13.0:
        p_val = exp(1.2937 - 5.709 * a2_star + 0.0186 * a2_star * a2_star)
    else:
        p_val = 0.0

    if p_val < 0.0:
        p_val = 0.0
    if p_val > 1.0:
        p_val = 1.0

    return TestResult(a2_star, p_val, p_val < 0.05)


# ── Shapiro-Wilk approximate test ────────────────────────────────────────────


fn shapiro_wilk_approx(sample: List[Float64]) -> TestResult:
    """Approximate Shapiro-Wilk test for normality (for n <= 5000).
    Uses a simplified version based on the correlation between
    sample order statistics and expected normal order statistics.
    W ≈ (Σ a_i * x_(i))² / Σ(x_i - x̄)²
    For large n, we approximate a_i using normal quantiles.
    """
    var n = len(sample)
    if n < 3:
        return TestResult(1.0, 1.0, False)

    var sorted = _sort_copy(sample)
    var mu = _mean(sample)

    # Sum of squared deviations
    var ss: Float64 = 0.0
    for i in range(n):
        var d = sorted[i] - mu
        ss += d * d

    if ss == 0.0:
        return TestResult(1.0, 1.0, False)

    # Compute expected normal order statistics (approximate)
    var nf = Float64(n)
    var a = List[Float64]()
    for i in range(n):
        var p = (Float64(i + 1) - 0.375) / (nf + 0.25)
        # Approximate inverse normal CDF using rational approximation
        a.append(_norm_ppf_approx(p))

    # Normalize a_i coefficients
    var a_ss: Float64 = 0.0
    for i in range(n):
        a_ss += a[i] * a[i]
    var a_norm = sqrt(a_ss)
    if a_norm == 0.0:
        a_norm = 1.0
    for i in range(n):
        a[i] = a[i] / a_norm

    # W statistic
    var num: Float64 = 0.0
    for i in range(n):
        num += a[i] * sorted[i]
    var w = (num * num) / ss

    # Approximate p-value using Royston's normality transformation
    # For moderate n, W is approximately normally distributed after transformation
    var log_n = log(nf)
    var mu_w: Float64
    var sigma_w: Float64

    if n <= 11:
        # Small sample approximation
        mu_w = -1.2725 + 1.0521 * log_n
        sigma_w = 1.0308 - 0.26758 * log_n
    else:
        # Larger sample
        mu_w = -1.2725 + 1.0521 * log_n - 0.001 * log_n * log_n
        sigma_w = 1.0308 - 0.26758 * log_n + 0.003 * log_n * log_n

    if sigma_w <= 0.0:
        sigma_w = 0.01

    var z = (log(1.0 - w) - mu_w) / sigma_w
    var p_val = 1.0 - _norm_cdf(z)

    if p_val < 0.0:
        p_val = 0.0
    if p_val > 1.0:
        p_val = 1.0

    return TestResult(w, p_val, p_val < 0.05)


fn _norm_ppf_approx(p: Float64) -> Float64:
    """Approximate inverse normal CDF (Acklam's rational approximation)."""
    if p <= 0.0:
        return -1e300
    if p >= 1.0:
        return 1e300
    if p == 0.5:
        return 0.0

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


# ── Correlation result struct ─────────────────────────────────────────────────


struct CorrResult(Copyable, Movable):
    """Result of a correlation computation."""
    var r: Float64       # correlation coefficient
    var p_value: Float64 # p-value

    fn __init__(out self, r: Float64, p_value: Float64):
        self.r = r
        self.p_value = p_value


# ── Correlation functions ─────────────────────────────────────────────────────


fn pearson_r(x: List[Float64], y: List[Float64]) -> CorrResult:
    """Pearson correlation coefficient and p-value.
    Returns CorrResult(r, p_value).
    p-value uses the t-distribution: t = r * sqrt(n-2) / sqrt(1-r²), df = n-2"""
    var n = len(x)
    if len(y) < n:
        n = len(y)
    if n < 3:
        return CorrResult(0.0, 1.0)

    var mx = _mean(x)
    var my = _mean(y)
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
        return CorrResult(0.0, 1.0)

    var r = sxy / denom

    # Clamp r to [-1, 1] for numerical safety
    if r > 1.0:
        r = 1.0
    if r < -1.0:
        r = -1.0

    # Compute p-value via t-distribution
    var r2 = r * r
    if r2 >= 1.0:
        return CorrResult(r, 0.0)

    var t = r * sqrt(Float64(n - 2)) / sqrt(1.0 - r2)
    var df = Float64(n - 2)
    var p_val = 2.0 * (1.0 - _t_cdf(fabs(t), df))
    if p_val > 1.0:
        p_val = 1.0
    if p_val < 0.0:
        p_val = 0.0

    return CorrResult(r, p_val)


fn spearman_r(x: List[Float64], y: List[Float64]) -> CorrResult:
    """Spearman rank correlation coefficient and p-value.
    Returns CorrResult(rho, p_value).
    Ranks ties by averaging. P-value uses the t-distribution approximation."""
    var n = len(x)
    if len(y) < n:
        n = len(y)
    if n < 3:
        return CorrResult(0.0, 1.0)

    # Compute ranks
    var rx = _rank(x, n)
    var ry = _rank(y, n)

    # Pearson correlation of ranks
    var result = pearson_r(rx, ry)
    return CorrResult(result.r, result.p_value)


# ── NaN/Inf-safe siblings (additive; see the module docstring) ────────────────


fn _first_non_finite_index(values: List[Float64], limit: Int) -> Int:
    """Index of the first NaN/±Inf in `values[0:limit]`, or -1 if none.

    `limit` lets a caller check exactly the range the frozen function actually reads
    -- `pearson_r` runs `_mean` over the WHOLE list (even past `n = min(len(x),
    len(y))`), while `spearman_r`'s `_rank` only ever touches the first `n` -- so one
    helper serves both call sites honestly rather than over- or under-checking either.
    """
    for i in range(limit):
        if isnan(values[i]) or isinf(values[i]):
            return i
    return -1


fn pearson_r_strict(x: List[Float64], y: List[Float64]) raises -> CorrResult:
    """`pearson_r`, but NaN/±Inf in `x` or `y` raises instead of returning
    `CorrResult(NaN, NaN)`.

    Checks the WHOLE of both lists, matching what `pearson_r` itself reads: its mean
    is taken over the full list, not just the first `min(len(x), len(y))` entries the
    covariance loop uses. Raises naming which list (`x` or `y`) and which index held
    the first non-finite value, and how many values that list has -- the same
    "typed error naming the offending position" shape `query.plan`'s
    `reject_non_json_literals` already uses for a non-finite JSON literal (naming row
    and column there; naming list and index here), and the same policy
    `numeric.reduce`/`numeric.__init__` already state for aggregation: "NaN and ±Inf
    are rejected at ingest, never aggregated."

    Does NOT change `pearson_r` -- that function is EXISTING-FROZEN (see the module
    docstring) and its current return-value contract for `n < 3` / a zero denominator
    is documented and relied upon elsewhere (`data_quality/leakage.mojo`). This is a
    new, separate entry point for a caller that wants the NaN/Inf case to raise.

    Also raises on `len(x) != len(y)`. `pearson_r` bounds its own loop to
    `min(len(x), len(y))` rather than crashing on a length mismatch -- correct for a
    caller who already aligned two columns, but a second silent-wrong-answer trap for
    one who didn't: two columns fetched independently (e.g. each with its own
    per-column null filter applied) can end up different lengths, and pairing the
    first `min(len(x), len(y))` entries of each correlates the wrong rows against each
    other without any error. A caller must align both lists to the same index space
    (the same rows) before calling this -- an equal length is necessary for that, not
    sufficient, but a mismatch is proof it wasn't done and is rejected here.
    """
    if len(x) != len(y):
        raise Error(
            "pearson_r_strict: x has "
            + String(len(x))
            + " values but y has "
            + String(len(y))
            + "; both must be aligned to the same rows before correlating -- pass"
            " values from the same index space, not two independently-filtered"
            " columns"
        )
    var bad_x = _first_non_finite_index(x, len(x))
    if bad_x >= 0:
        raise Error(
            "pearson_r_strict: x["
            + String(bad_x)
            + "] is not finite (of "
            + String(len(x))
            + " values in x); NaN and ±Inf are rejected at ingest, never"
            " aggregated into r or p_value"
        )
    var bad_y = _first_non_finite_index(y, len(y))
    if bad_y >= 0:
        raise Error(
            "pearson_r_strict: y["
            + String(bad_y)
            + "] is not finite (of "
            + String(len(y))
            + " values in y); NaN and ±Inf are rejected at ingest, never"
            " aggregated into r or p_value"
        )
    return pearson_r(x, y)


fn spearman_r_strict(x: List[Float64], y: List[Float64]) raises -> CorrResult:
    """`spearman_r`, but NaN/±Inf in `x` or `y` raises instead of returning
    `CorrResult(NaN, NaN)`.

    Checks only the first `n = min(len(x), len(y))` entries of each list, matching
    what `spearman_r` itself reads (`_rank` never looks past `n`) -- a non-finite
    value past `n` is never read by `spearman_r` and so is not this function's
    concern either. See `pearson_r_strict` for the full rationale; this is the same
    fix applied to the rank-based sibling, including the same `len(x) != len(y)`
    misalignment check.
    """
    if len(x) != len(y):
        raise Error(
            "spearman_r_strict: x has "
            + String(len(x))
            + " values but y has "
            + String(len(y))
            + "; both must be aligned to the same rows before correlating -- pass"
            " values from the same index space, not two independently-filtered"
            " columns"
        )
    var n = len(x)
    if len(y) < n:
        n = len(y)
    var bad_x = _first_non_finite_index(x, n)
    if bad_x >= 0:
        raise Error(
            "spearman_r_strict: x["
            + String(bad_x)
            + "] is not finite (of "
            + String(n)
            + " compared values); NaN and ±Inf are rejected at ingest, never"
            " aggregated into rho or p_value"
        )
    var bad_y = _first_non_finite_index(y, n)
    if bad_y >= 0:
        raise Error(
            "spearman_r_strict: y["
            + String(bad_y)
            + "] is not finite (of "
            + String(n)
            + " compared values); NaN and ±Inf are rejected at ingest, never"
            " aggregated into rho or p_value"
        )
    return spearman_r(x, y)


fn _rank(data: List[Float64], n: Int) -> List[Float64]:
    """Compute ranks with average tie-breaking."""
    # Create (value, index) pairs via parallel sorted lists
    var indices = List[Int]()
    for i in range(n):
        indices.append(i)

    # Sort indices by data values (insertion sort for simplicity)
    for i in range(1, n):
        var key_idx = indices[i]
        var key_val = data[key_idx]
        var j = i - 1
        while j >= 0 and data[indices[j]] > key_val:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key_idx

    # Assign ranks with tie averaging
    var ranks = List[Float64]()
    for i in range(n):
        ranks.append(0.0)

    var i = 0
    while i < n:
        var j = i
        # Find all tied values
        while j < n - 1 and data[indices[j + 1]] == data[indices[i]]:
            j += 1
        # Average rank for ties
        var avg_rank = Float64(i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indices[k]] = avg_rank
        i = j + 1

    return ranks^
