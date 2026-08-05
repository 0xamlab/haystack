"""
Cholesky decomposition for correlated Normal sampling + inverse CDF for QMC/LHS.
"""
from std.random import randn_float64
from std.math import sqrt, exp, log, pow


def cholesky_lower(corr: List[List[Float64]], n: Int) -> List[List[Float64]]:
    """
    Cholesky decomposition of correlation matrix.
    Returns lower triangular L such that L * L^T = corr.
    O(n³) at startup; O(n) per sample in the hot loop.
    """
    var L = List[List[Float64]]()
    for _ in range(n):
        var row = List[Float64](capacity=n)
        for _j in range(n): row.append(0.0)
        L.append(row.copy())

    for i in range(n):
        for j in range(i+1):
            var s: Float64 = 0.0
            for k in range(j): s += L[i][k] * L[j][k]
            if i == j:
                var diag = corr[i][i] - s
                L[i][j] = sqrt(max(diag, 0.0))
            else:
                if L[j][j] > 1e-10:
                    L[i][j] = (corr[i][j] - s) / L[j][j]
                else:
                    L[i][j] = 0.0
    return L^


def sample_correlated_normal(L: List[List[Float64]], n_vars: Int) -> List[Float64]:
    """
    Generate correlated standard normals using precomputed Cholesky L.
    z = L * iid_normals → correlated standard normals.
    """
    # A negative count or a ragged/short Cholesky factor has no valid sample; an unguarded
    # L[i][j] read aborts the worker (uncatchable), so refuse with an empty result.
    if n_vars < 1 or len(L) < n_vars:
        return List[Float64]()
    for i in range(n_vars):
        if len(L[i]) < i + 1:
            return List[Float64]()
    var iid = List[Float64](capacity=n_vars)
    for _ in range(n_vars): iid.append(randn_float64())

    var z = List[Float64](capacity=n_vars)
    for i in range(n_vars):
        var s: Float64 = 0.0
        for j in range(i+1): s += L[i][j] * iid[j]
        z.append(s)
    return z^


# ── Inverse CDF (QMC / LHS — maps uniform [0,1] → distribution quantile) ─────

def probit(u: Float64) -> Float64:
    """Rational approximation to the standard normal quantile function."""
    var uu   = max(1e-10, min(1.0 - 1e-10, u))
    var sign: Float64 = 1.0 if uu >= 0.5 else -1.0
    var p    = uu if uu < 0.5 else 1.0 - uu
    var t    = sqrt(-2.0 * log(p))
    var z    = t - (2.515517 + 0.802853*t + 0.010328*t*t) / (1.0 + 1.432788*t + 0.189269*t*t + 0.001308*t*t*t)
    return sign * z

def icdf(u: Float64, dt: Int, p0: Float64, p1: Float64, p2: Float64) -> Float64:
    """Inverse CDF for stratified/QMC sampling. Supports the most common distributions."""
    var uu = max(1e-10, min(1.0 - 1e-10, u))
    if dt == 0:   return p0 + p1 * probit(uu)
    elif dt == 1: return p0 + (p1 - p0) * uu
    elif dt == 2:
        var r = p2 - p0
        if r == 0.0: return p0
        var fc = (p1 - p0) / r
        if uu < fc: return p0 + sqrt(uu * r * (p1 - p0))
        return p2 - sqrt((1.0 - uu) * r * (p2 - p1))
    elif dt == 3: return exp(p0 + p1 * probit(uu))
    elif dt == 7: return -log(1.0 - uu) / p0
    elif dt == 8: return p1 * pow(-log(1.0 - uu), 1.0 / p0)
    elif dt == 4: return p0
    return uu
