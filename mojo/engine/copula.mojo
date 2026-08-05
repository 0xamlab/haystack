"""
copula.mojo — Copula functions for correlated sampling. Zero Python imports.

Replaces scipy.stats copula utilities with pure Mojo implementations.

Public API:
  norm_cdf_approx         — Abramowitz & Stegun approximation for Φ(x)
  norm_ppf_approx         — Rational approximation for inverse normal CDF
  gaussian_copula_sample  — Bivariate Gaussian copula samples
  rank_correlation        — Spearman rank correlation
  kendall_tau             — Kendall's tau-b
"""
from std.math import sqrt, exp, abs as fabs, log
from std.random import random_float64


# ── Constants ─────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.141592653589793
comptime SQRT2: Float64 = 1.4142135623730951


# ── norm_cdf_approx ──────────────────────────────────────────────────────────


fn norm_cdf_approx(x: Float64) -> Float64:
    """Abramowitz & Stegun approximation for the standard normal CDF Φ(x).

    Uses formula 26.2.17 with maximum error < 7.5e-8.
    """
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0

    # For negative x, use symmetry: Φ(-x) = 1 - Φ(x)
    var ax = x
    if ax < 0.0:
        ax = -ax

    # Constants for Abramowitz & Stegun 26.2.17
    var p: Float64 = 0.2316419
    var b1: Float64 = 0.319381530
    var b2: Float64 = -0.356563782
    var b3: Float64 = 1.781477937
    var b4: Float64 = -1.821255978
    var b5: Float64 = 1.330274429

    var t = 1.0 / (1.0 + p * ax)
    var t2 = t * t
    var t3 = t2 * t
    var t4 = t3 * t
    var t5 = t4 * t

    var pdf = exp(-0.5 * ax * ax) / sqrt(2.0 * PI)
    var cdf = 1.0 - pdf * (b1 * t + b2 * t2 + b3 * t3 + b4 * t4 + b5 * t5)

    if x < 0.0:
        return 1.0 - cdf
    return cdf


# ── norm_ppf_approx ──────────────────────────────────────────────────────────


fn norm_ppf_approx(p: Float64) -> Float64:
    """Rational approximation for the inverse standard normal CDF (quantile).

    Uses the Beasley-Springer-Moro algorithm. Accurate to ~1e-9.
    Input p must be in (0, 1). Returns x such that Φ(x) ≈ p.
    """
    if p <= 0.0:
        return -1e10
    if p >= 1.0:
        return 1e10

    # Rational approximation (Peter Acklam's algorithm)
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
    var p_high: Float64 = 1.0 - p_low

    var result: Float64

    if p < p_low:
        # Lower tail
        var q = sqrt(-2.0 * log(p))
        result = (((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)
    elif p <= p_high:
        # Central region
        var q = p - 0.5
        var r = q * q
        result = (((((a1 * r + a2) * r + a3) * r + a4) * r + a5) * r + a6) * q / (((((b1 * r + b2) * r + b3) * r + b4) * r + b5) * r + 1.0)
    else:
        # Upper tail
        var q = sqrt(-2.0 * log(1.0 - p))
        result = -(((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / ((((d1 * q + d2) * q + d3) * q + d4) * q + 1.0)

    return result


# ── Box-Muller normal RNG ─────────────────────────────────────────────────────


fn _box_muller_pair() -> List[Float64]:
    """Generate a pair of independent standard normal variates via Box-Muller."""
    var u1 = random_float64()
    var u2 = random_float64()
    # Avoid log(0)
    if u1 < 1e-15:
        u1 = 1e-15
    var r = sqrt(-2.0 * log(u1))
    var theta = 2.0 * PI * u2
    # Use manual sin/cos via Taylor series (sufficient precision)
    var z0 = r * _cos_approx(theta)
    var z1 = r * _sin_approx(theta)
    var result = List[Float64]()
    result.append(z0)
    result.append(z1)
    return result^


fn _sin_approx(x: Float64) -> Float64:
    """Sin approximation via range reduction + Taylor series."""
    # Reduce to [-PI, PI]
    var v = x
    while v > PI:
        v -= 2.0 * PI
    while v < -PI:
        v += 2.0 * PI
    # Taylor: sin(x) ≈ x - x³/6 + x⁵/120 - x⁷/5040 + x⁹/362880
    var x2 = v * v
    var x3 = v * x2
    var x5 = x3 * x2
    var x7 = x5 * x2
    var x9 = x7 * x2
    var x11 = x9 * x2
    return v - x3 / 6.0 + x5 / 120.0 - x7 / 5040.0 + x9 / 362880.0 - x11 / 39916800.0


fn _cos_approx(x: Float64) -> Float64:
    """Cos approximation via range reduction + Taylor series."""
    var v = x
    while v > PI:
        v -= 2.0 * PI
    while v < -PI:
        v += 2.0 * PI
    var x2 = v * v
    var x4 = x2 * x2
    var x6 = x4 * x2
    var x8 = x6 * x2
    var x10 = x8 * x2
    return 1.0 - x2 / 2.0 + x4 / 24.0 - x6 / 720.0 + x8 / 40320.0 - x10 / 3628800.0


# ── gaussian_copula_sample ────────────────────────────────────────────────────


fn gaussian_copula_sample(n: Int, rho: Float64) -> List[List[Float64]]:
    """Generate n bivariate samples from a Gaussian copula with correlation rho.

    Uses Box-Muller for normal RNG and Cholesky factorisation for correlation.
    Returns list of [u1, u2] pairs where each u is in [0, 1].
    """
    var result = List[List[Float64]]()

    # Cholesky: L = [[1, 0], [rho, sqrt(1-rho²)]]
    var rho2 = rho * rho
    var chol_21 = rho
    var chol_22 = sqrt(1.0 - rho2) if rho2 < 1.0 else 0.0

    for _ in range(n):
        var pair = _box_muller_pair()
        var z1 = pair[0]
        var z2_raw = pair[1]

        # Correlate: x1 = z1, x2 = rho*z1 + sqrt(1-rho²)*z2
        var x1 = z1
        var x2 = chol_21 * z1 + chol_22 * z2_raw

        # Transform to uniform via CDF
        var u1 = norm_cdf_approx(x1)
        var u2 = norm_cdf_approx(x2)

        # Clamp to [0,1]
        if u1 < 0.0:
            u1 = 0.0
        if u1 > 1.0:
            u1 = 1.0
        if u2 < 0.0:
            u2 = 0.0
        if u2 > 1.0:
            u2 = 1.0

        var sample = List[Float64]()
        sample.append(u1)
        sample.append(u2)
        result.append(sample^)

    return result^


# ── rank_correlation ──────────────────────────────────────────────────────────


fn _rank(values: List[Float64]) -> List[Float64]:
    """Compute ranks (1-based, with average ranks for ties)."""
    var n = len(values)
    var indices = List[Int]()
    for i in range(n):
        indices.append(i)

    # Sort indices by value (insertion sort — fine for typical sizes)
    for i in range(1, n):
        var key_idx = indices[i]
        var key_val = values[key_idx]
        var j = i - 1
        while j >= 0 and values[indices[j]] > key_val:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key_idx

    # Assign ranks with average for ties
    var ranks = List[Float64]()
    for _ in range(n):
        ranks.append(0.0)

    var i = 0
    while i < n:
        var j = i
        while j < n - 1 and fabs(values[indices[j + 1]] - values[indices[i]]) < 1e-12:
            j += 1
        var avg_rank = Float64(i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indices[k]] = avg_rank
        i = j + 1

    return ranks^


fn rank_correlation(x: List[Float64], y: List[Float64]) -> Float64:
    """Spearman rank correlation coefficient.

    Computes Pearson correlation on rank-transformed data.
    """
    var n = len(x)
    # A correlation needs two equal-length series; a short/empty y would be read past its
    # end below (uncatchable abort), so refuse with the same sentinel used for n < 2.
    if n < 2 or len(y) != n:
        return 0.0

    var rx = _rank(x)
    var ry = _rank(y)

    # Pearson on ranks
    var sum_rx: Float64 = 0.0
    var sum_ry: Float64 = 0.0
    for i in range(n):
        sum_rx += rx[i]
        sum_ry += ry[i]
    var mean_rx = sum_rx / Float64(n)
    var mean_ry = sum_ry / Float64(n)

    var num: Float64 = 0.0
    var den_x: Float64 = 0.0
    var den_y: Float64 = 0.0
    for i in range(n):
        var dx = rx[i] - mean_rx
        var dy = ry[i] - mean_ry
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy

    var denom = sqrt(den_x * den_y)
    if denom < 1e-15:
        return 0.0
    return num / denom


# ── kendall_tau ───────────────────────────────────────────────────────────────


fn kendall_tau(x: List[Float64], y: List[Float64]) -> Float64:
    """Kendall's tau-b rank correlation.

    tau-b = (concordant - discordant) / sqrt((n0-n1)*(n0-n2))
    where n0 = n*(n-1)/2, n1 = ties in x, n2 = ties in y.
    """
    var n = len(x)
    # A correlation needs two equal-length series; a short/empty y would be read past its
    # end in the pair loop below (uncatchable abort), so refuse with the n < 2 sentinel.
    if n < 2 or len(y) != n:
        return 0.0

    var concordant: Int = 0
    var discordant: Int = 0
    var ties_x: Int = 0
    var ties_y: Int = 0

    for i in range(n):
        for j in range(i + 1, n):
            var dx = x[j] - x[i]
            var dy = y[j] - y[i]
            var sign_x = 0
            var sign_y = 0
            if dx > 1e-12:
                sign_x = 1
            elif dx < -1e-12:
                sign_x = -1
            if dy > 1e-12:
                sign_y = 1
            elif dy < -1e-12:
                sign_y = -1

            var product = sign_x * sign_y
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
            else:
                if sign_x == 0:
                    ties_x += 1
                if sign_y == 0:
                    ties_y += 1

    var n0 = n * (n - 1) // 2
    var denom = sqrt(Float64(n0 - ties_x) * Float64(n0 - ties_y))
    if denom < 1e-15:
        return 0.0
    return Float64(concordant - discordant) / denom
