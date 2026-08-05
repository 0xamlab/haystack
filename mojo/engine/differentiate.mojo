"""
differentiate.mojo — Numerical differentiation. Zero Python imports.
Replaces: scipy.misc.derivative

Public API:
  derivative_forward, derivative_central, derivative_backward,
  second_derivative, gradient, poly_derivative_coeffs
"""


fn _finite(v: Float64) -> Bool:
    """True when v is neither NaN nor infinite (v - v == 0.0 only for finite v)."""
    return v - v == 0.0


# ── Forward Difference ────────────────────────────────────────────────────────


fn derivative_forward(y: List[Float64], dx: Float64) -> List[Float64]:
    """Forward difference: dy[i] = (y[i+1] - y[i]) / dx.
    Returns a list of length n-1."""
    var n = len(y)
    var result = List[Float64]()
    if n < 2:
        return result^
    for i in range(n - 1):
        result.append((y[i + 1] - y[i]) / dx)
    return result^


# ── Central Difference ────────────────────────────────────────────────────────


fn derivative_central(y: List[Float64], dx: Float64) -> List[Float64]:
    """Central difference: dy[i] = (y[i+1] - y[i-1]) / (2*dx).
    For endpoints uses forward/backward difference.
    Returns a list of length n."""
    var n = len(y)
    var result = List[Float64]()
    if n < 2:
        if n == 1:
            result.append(0.0)
        return result^
    # Forward difference for first point
    result.append((y[1] - y[0]) / dx)
    # Central difference for interior points
    var two_dx = 2.0 * dx
    for i in range(1, n - 1):
        result.append((y[i + 1] - y[i - 1]) / two_dx)
    # Backward difference for last point
    result.append((y[n - 1] - y[n - 2]) / dx)
    return result^


# ── Backward Difference ──────────────────────────────────────────────────────


fn derivative_backward(y: List[Float64], dx: Float64) -> List[Float64]:
    """Backward difference: dy[i] = (y[i] - y[i-1]) / dx.
    Returns a list of length n-1 (starting from index 1)."""
    var n = len(y)
    var result = List[Float64]()
    if n < 2:
        return result^
    for i in range(1, n):
        result.append((y[i] - y[i - 1]) / dx)
    return result^


# ── Second Derivative ─────────────────────────────────────────────────────────


fn second_derivative(y: List[Float64], dx: Float64) -> List[Float64]:
    """Second derivative via central difference:
    d2y[i] = (y[i+1] - 2*y[i] + y[i-1]) / dx^2.
    Returns a list of length n-2 (interior points only)."""
    var n = len(y)
    var result = List[Float64]()
    if n < 3:
        return result^
    var dx2 = dx * dx
    for i in range(1, n - 1):
        result.append((y[i + 1] - 2.0 * y[i] + y[i - 1]) / dx2)
    return result^


# ── Gradient (non-uniform spacing) ───────────────────────────────────────────


fn gradient(y: List[Float64], x: List[Float64]) -> List[Float64]:
    """Numerical gradient for non-uniformly spaced data.
    Uses central differences for interior, forward/backward at ends.
    x and y must have the same length. Returns list of length n."""
    var n = len(y)
    var result = List[Float64]()
    if n < 2:
        if n == 1:
            result.append(0.0)
        return result^
    # x is indexed up to n-1 below; a shorter x is an uncatchable abort.
    if len(x) < n:
        return result^
    # Forward difference for first point
    var dx0 = x[1] - x[0]
    if dx0 != 0.0:
        var dy0 = (y[1] - y[0]) / dx0
        # NaN/inf payloads in x or y cannot cross the result wire; degrade
        # to the same 0.0 sentinel used for a zero denominator.
        if not _finite(dy0):
            dy0 = 0.0
        result.append(dy0)
    else:
        result.append(0.0)
    # Central difference for interior points
    for i in range(1, n - 1):
        var dx_forward = x[i + 1] - x[i]
        var dx_backward = x[i] - x[i - 1]
        var dx_total = x[i + 1] - x[i - 1]
        if dx_total != 0.0:
            # Weighted central difference for non-uniform spacing
            var dy = (
                dx_backward * dx_backward * y[i + 1]
                + (dx_forward * dx_forward - dx_backward * dx_backward) * y[i]
                - dx_forward * dx_forward * y[i - 1]
            ) / (dx_forward * dx_backward * dx_total)
            if not _finite(dy):
                dy = 0.0
            result.append(dy)
        else:
            result.append(0.0)
    # Backward difference for last point
    var dx_last = x[n - 1] - x[n - 2]
    if dx_last != 0.0:
        var dy_last = (y[n - 1] - y[n - 2]) / dx_last
        if not _finite(dy_last):
            dy_last = 0.0
        result.append(dy_last)
    else:
        result.append(0.0)
    return result^


# ── Polynomial Derivative Coefficients ────────────────────────────────────────


fn poly_derivative_coeffs(coeffs: List[Float64]) -> List[Float64]:
    """Analytical derivative of polynomial given as coefficients.
    Input: coeffs[0] + coeffs[1]*x + coeffs[2]*x^2 + ...
    Output: coeffs[1] + 2*coeffs[2]*x + 3*coeffs[3]*x^2 + ...
    Returns list of length n-1."""
    var n = len(coeffs)
    var result = List[Float64]()
    if n < 2:
        return result^
    for i in range(1, n):
        result.append(Float64(i) * coeffs[i])
    return result^
