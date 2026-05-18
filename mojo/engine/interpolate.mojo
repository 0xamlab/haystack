"""
interpolate.mojo — Interpolation and curve fitting. Zero Python imports.
Replaces scipy.interpolate basics for the decision engine.

Public API:
  linear_interp        — linear interpolation between data points
  nearest_interp       — nearest neighbor interpolation
  cubic_spline_natural — natural cubic spline interpolation
  lagrange_interp      — Lagrange polynomial interpolation
  interp_array         — interpolate an array of points with selectable method
  extrapolate_linear   — linear extrapolation beyond data bounds
"""
from std.math import abs as fabs


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _find_interval(x_data: List[Float64], x: Float64) -> Int:
    """Binary search for the interval index i such that x_data[i] <= x < x_data[i+1].
    Returns clamped index in [0, n-2]."""
    var n = len(x_data)
    if n <= 1:
        return 0
    if x <= x_data[0]:
        return 0
    if x >= x_data[n - 1]:
        return n - 2
    var lo = 0
    var hi = n - 2
    while lo < hi:
        var mid = (lo + hi) // 2
        if x_data[mid + 1] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lo


# ── Linear interpolation ─────────────────────────────────────────────────────


fn linear_interp(x_data: List[Float64], y_data: List[Float64], x: Float64) -> Float64:
    """Linear interpolation. Clamps to boundary values if x is outside data range."""
    var n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    # Clamp
    if x <= x_data[0]:
        return y_data[0]
    if x >= x_data[n - 1]:
        return y_data[n - 1]
    var i = _find_interval(x_data, x)
    var dx = x_data[i + 1] - x_data[i]
    if fabs(dx) < 1e-15:
        return y_data[i]
    var t = (x - x_data[i]) / dx
    return y_data[i] + t * (y_data[i + 1] - y_data[i])


# ── Nearest neighbor interpolation ───────────────────────────────────────────


fn nearest_interp(x_data: List[Float64], y_data: List[Float64], x: Float64) -> Float64:
    """Nearest neighbor interpolation. Returns value of closest data point."""
    var n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    if x <= x_data[0]:
        return y_data[0]
    if x >= x_data[n - 1]:
        return y_data[n - 1]
    var i = _find_interval(x_data, x)
    var d_left = fabs(x - x_data[i])
    var d_right = fabs(x_data[i + 1] - x)
    if d_left <= d_right:
        return y_data[i]
    return y_data[i + 1]


# ── Natural cubic spline interpolation ───────────────────────────────────────


fn cubic_spline_natural(x_data: List[Float64], y_data: List[Float64], x: Float64) -> Float64:
    """Natural cubic spline interpolation (second derivatives = 0 at endpoints).
    Falls back to linear for n < 3."""
    var n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    if n == 2:
        return linear_interp(x_data, y_data, x)

    # Clamp to range
    var x_eval = x
    if x_eval < x_data[0]:
        x_eval = x_data[0]
    if x_eval > x_data[n - 1]:
        x_eval = x_data[n - 1]

    # Step 1: Compute h[i] = x[i+1] - x[i]
    var h = List[Float64]()
    for i in range(n - 1):
        h.append(x_data[i + 1] - x_data[i])

    # Step 2: Set up tridiagonal system for second derivatives (c)
    # Natural spline: c[0] = c[n-1] = 0
    # For i=1..n-2: h[i-1]*c[i-1] + 2*(h[i-1]+h[i])*c[i] + h[i]*c[i+1]
    #   = 3*((y[i+1]-y[i])/h[i] - (y[i]-y[i-1])/h[i-1])
    var c = List[Float64]()
    for i in range(n):
        c.append(0.0)

    if n > 2:
        # Tridiagonal solve
        var alpha = List[Float64]()
        for i in range(n):
            alpha.append(0.0)
        for i in range(1, n - 1):
            alpha[i] = 3.0 * ((y_data[i + 1] - y_data[i]) / h[i] - (y_data[i] - y_data[i - 1]) / h[i - 1])

        var l = List[Float64]()
        var mu = List[Float64]()
        var z = List[Float64]()
        for i in range(n):
            l.append(0.0)
            mu.append(0.0)
            z.append(0.0)
        l[0] = 1.0

        for i in range(1, n - 1):
            l[i] = 2.0 * (x_data[i + 1] - x_data[i - 1]) - h[i - 1] * mu[i - 1]
            if fabs(l[i]) < 1e-15:
                l[i] = 1e-15
            mu[i] = h[i] / l[i]
            z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i]

        l[n - 1] = 1.0
        # Back substitution
        for j in range(n - 2, -1, -1):
            c[j] = z[j] - mu[j] * c[j + 1]

    # Step 3: Compute b and d coefficients for each segment
    var b = List[Float64]()
    var d = List[Float64]()
    for i in range(n - 1):
        b.append(0.0)
        d.append(0.0)

    for i in range(n - 1):
        if fabs(h[i]) < 1e-15:
            b[i] = 0.0
            d[i] = 0.0
        else:
            b[i] = (y_data[i + 1] - y_data[i]) / h[i] - h[i] * (c[i + 1] + 2.0 * c[i]) / 3.0
            d[i] = (c[i + 1] - c[i]) / (3.0 * h[i])

    # Step 4: Evaluate at x
    var idx = _find_interval(x_data, x_eval)
    var dx = x_eval - x_data[idx]
    return y_data[idx] + b[idx] * dx + c[idx] * dx * dx + d[idx] * dx * dx * dx


# ── Lagrange polynomial interpolation ────────────────────────────────────────


fn lagrange_interp(x_data: List[Float64], y_data: List[Float64], x: Float64) -> Float64:
    """Lagrange polynomial interpolation through all data points.
    Warning: high-degree polynomials may oscillate (Runge's phenomenon)."""
    var n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    var result: Float64 = 0.0
    for i in range(n):
        var basis: Float64 = 1.0
        for j in range(n):
            if j != i:
                var denom = x_data[i] - x_data[j]
                if fabs(denom) < 1e-15:
                    continue
                basis *= (x - x_data[j]) / denom
        result += y_data[i] * basis
    return result


# ── Interpolate array of points ──────────────────────────────────────────────


fn interp_array(
    x_data: List[Float64],
    y_data: List[Float64],
    x_new: List[Float64],
    method: String,
) -> List[Float64]:
    """Interpolate an array of x_new points using the specified method.
    Methods: "linear", "nearest", "cubic", "lagrange".
    Defaults to linear for unknown methods."""
    var result = List[Float64]()
    for i in range(len(x_new)):
        var xi = x_new[i]
        if method == "nearest":
            result.append(nearest_interp(x_data, y_data, xi))
        elif method == "cubic":
            result.append(cubic_spline_natural(x_data, y_data, xi))
        elif method == "lagrange":
            result.append(lagrange_interp(x_data, y_data, xi))
        else:
            # Default: linear
            result.append(linear_interp(x_data, y_data, xi))
    return result^


# ── Linear extrapolation ─────────────────────────────────────────────────────


fn extrapolate_linear(x_data: List[Float64], y_data: List[Float64], x: Float64) -> Float64:
    """Linear extrapolation beyond data bounds.
    Uses slope from first two points (left) or last two points (right).
    Within data range, uses linear interpolation."""
    var n = len(x_data)
    if n == 0:
        return 0.0
    if n == 1:
        return y_data[0]
    # If within range, use linear interp
    if x >= x_data[0] and x <= x_data[n - 1]:
        return linear_interp(x_data, y_data, x)
    # Extrapolate left
    if x < x_data[0]:
        var dx = x_data[1] - x_data[0]
        if fabs(dx) < 1e-15:
            return y_data[0]
        var slope = (y_data[1] - y_data[0]) / dx
        return y_data[0] + slope * (x - x_data[0])
    # Extrapolate right
    var dx = x_data[n - 1] - x_data[n - 2]
    if fabs(dx) < 1e-15:
        return y_data[n - 1]
    var slope = (y_data[n - 1] - y_data[n - 2]) / dx
    return y_data[n - 1] + slope * (x - x_data[n - 1])
