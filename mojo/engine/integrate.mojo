"""
integrate.mojo — Numerical integration. Zero Python imports.
Replaces: scipy.integrate (trapezoid, simpson, romberg, Gauss-Legendre)

Public API:
  trapezoid, simpson, romberg, cumulative_trapezoid,
  integrate_poly, quad_gauss_legendre
"""
from std.math import abs as fabs


# ── Trapezoidal rule ──────────────────────────────────────────────────────────


def trapezoid(y: List[Float64], dx: Float64) -> Float64:
    """Trapezoidal rule for equally-spaced data.
    ∫ ≈ dx * (y[0]/2 + y[1] + y[2] + ... + y[n-1]/2)"""
    var n = len(y)
    if n < 2:
        return 0.0
    var s: Float64 = 0.5 * (y[0] + y[n - 1])
    for i in range(1, n - 1):
        s += y[i]
    return s * dx


# ── Simpson's 1/3 rule ───────────────────────────────────────────────────────


def simpson(y: List[Float64], dx: Float64) -> Float64:
    """Simpson's 1/3 rule for equally-spaced data.
    Requires an odd number of points (even number of intervals).
    If even number of points, falls back to composite Simpson + trapezoid for last interval."""
    var n = len(y)
    if n < 3:
        return trapezoid(y, dx)

    var s: Float64 = 0.0
    # Number of full Simpson pairs we can use
    var m = n
    if n % 2 == 0:
        # Even number of points: use Simpson on n-1 points, trap on last interval
        m = n - 1

    # Composite Simpson on m points (m is odd)
    s = y[0] + y[m - 1]
    for i in range(1, m - 1):
        if i % 2 == 1:
            s += 4.0 * y[i]
        else:
            s += 2.0 * y[i]
    s *= dx / 3.0

    # If we had an even number of points, add the last interval with trapezoid
    if n % 2 == 0:
        s += 0.5 * dx * (y[n - 2] + y[n - 1])

    return s


# ── Romberg integration ──────────────────────────────────────────────────────


def romberg(y: List[Float64], dx: Float64, max_iter: Int = 10) -> Float64:
    """Romberg integration using Richardson extrapolation on trapezoidal estimates.
    y: equally-spaced data, dx: spacing.
    Uses as many levels as possible given the data length."""
    var n = len(y)
    if n < 2:
        return 0.0

    # Determine max levels possible: we need at least 2^k + 1 points for level k
    var max_levels = 1
    var pts = 2
    while pts < n and max_levels < max_iter:
        pts *= 2
        max_levels += 1
    if max_levels > max_iter:
        max_levels = max_iter

    # Flat 2D table stored as 1D: r[i * max_levels + j]
    var table_size = max_levels * max_levels
    var r = List[Float64]()
    for _i in range(table_size):
        r.append(0.0)

    # R[0][0]: coarsest trapezoid (just endpoints)
    r[0] = 0.5 * Float64(n - 1) * dx * (y[0] + y[n - 1])

    for k in range(1, max_levels):
        # Compute trapezoid with 2^k intervals (step = (n-1)*dx / 2^k)
        var num_intervals = 1
        for _p in range(k):
            num_intervals *= 2
        var step_idx = (n - 1) // num_intervals
        if step_idx < 1:
            step_idx = 1

        # Trapezoidal rule using every step_idx-th point
        var s: Float64 = 0.5 * (y[0] + y[n - 1])
        var idx = step_idx
        while idx < n - 1:
            s += y[idx]
            idx += step_idx
        r[k * max_levels + 0] = s * Float64(step_idx) * dx

        # Richardson extrapolation
        var four_j: Float64 = 1.0
        for j in range(1, k + 1):
            four_j *= 4.0
            r[k * max_levels + j] = (four_j * r[k * max_levels + j - 1] - r[(k - 1) * max_levels + j - 1]) / (four_j - 1.0)

    # Best estimate is the last diagonal element
    var best_level = max_levels - 1
    return r[best_level * max_levels + best_level]


# ── Cumulative trapezoid ──────────────────────────────────────────────────────


def cumulative_trapezoid(y: List[Float64], dx: Float64) -> List[Float64]:
    """Cumulative integral using the trapezoidal rule.
    Returns a list of length len(y)-1 with running integral values."""
    var n = len(y)
    var result = List[Float64]()
    if n < 2:
        return result^

    var cum: Float64 = 0.0
    for i in range(1, n):
        cum += 0.5 * dx * (y[i - 1] + y[i])
        result.append(cum)

    return result^


# ── Polynomial integration ────────────────────────────────────────────────────


def integrate_poly(coeffs: List[Float64], a: Float64, b: Float64) -> Float64:
    """Exact integral of a polynomial from a to b.
    coeffs[i] is the coefficient of x^i, so:
      p(x) = coeffs[0] + coeffs[1]*x + coeffs[2]*x^2 + ...
    Integral = sum_i coeffs[i] * (b^(i+1) - a^(i+1)) / (i+1)"""
    var n = len(coeffs)
    var result: Float64 = 0.0
    for i in range(n):
        var power = i + 1
        # Compute b^power and a^power
        var bp: Float64 = 1.0
        var ap: Float64 = 1.0
        for _j in range(power):
            bp *= b
            ap *= a
        result += coeffs[i] * (bp - ap) / Float64(power)
    return result


# ── Gauss-Legendre quadrature (5-point) ──────────────────────────────────────


def quad_gauss_legendre(y_values: List[Float64], a: Float64, b: Float64) -> Float64:
    """5-point Gauss-Legendre quadrature approximation.
    y_values: function values sampled at the 5 Gauss-Legendre nodes mapped to [a, b].
    
    The 5 nodes on [-1, 1] are:
      0, ±0.538469310105683, ±0.906179845938664
    The corresponding weights are:
      0.568888888888889, 0.478628670499366, 0.236926885056189
    
    If y_values has exactly 5 entries, they are assumed to be at the GL nodes.
    Otherwise, linearly interpolates from the equally-spaced y_values."""
    # GL 5-point nodes and weights on [-1, 1]
    var nodes = List[Float64]()
    nodes.append(-0.906179845938664)
    nodes.append(-0.538469310105683)
    nodes.append(0.0)
    nodes.append(0.538469310105683)
    nodes.append(0.906179845938664)

    var weights = List[Float64]()
    weights.append(0.236926885056189)
    weights.append(0.478628670499366)
    weights.append(0.568888888888889)
    weights.append(0.478628670499366)
    weights.append(0.236926885056189)

    var half_width = (b - a) / 2.0
    var mid = (a + b) / 2.0
    var n = len(y_values)

    if n == 5:
        # Direct: y_values are at the GL nodes
        var result: Float64 = 0.0
        for i in range(5):
            result += weights[i] * y_values[i]
        return result * half_width

    # Interpolate from equally-spaced data
    if n < 2:
        return 0.0

    var result: Float64 = 0.0
    for i in range(5):
        # Map GL node to [a, b]
        var x = mid + half_width * nodes[i]
        # Map x to index in y_values
        var t = (x - a) / (b - a) * Float64(n - 1)
        var idx = Int(t)
        if idx < 0:
            idx = 0
        if idx >= n - 1:
            idx = n - 2
        var frac = t - Float64(idx)
        var yval = y_values[idx] * (1.0 - frac) + y_values[idx + 1] * frac
        result += weights[i] * yval

    return result * half_width
