"""
root_finding.mojo — Numerical root-finding methods. Zero Python imports.
Replaces: scipy.optimize.root_scalar, brentq, newton

Test functions identified by func_id:
  0 = x²-2  (root = √2)
  1 = x³-x-2
  2 = cos(x)-x
  3 = exp(x)-3x

Public API:
  eval_func, eval_deriv, bisection, newton_raphson, secant_method,
  fixed_point, regula_falsi, bracket_root, convergence_order
"""
from std.math import sqrt, abs as fabs, cos, sin, exp, log


# ── Function evaluation ──────────────────────────────────────────────────────


fn eval_func(x: Float64, func_id: Int) -> Float64:
    """Evaluate test function identified by func_id."""
    if func_id == 0:
        return x * x - 2.0
    elif func_id == 1:
        return x * x * x - x - 2.0
    elif func_id == 2:
        return cos(x) - x
    elif func_id == 3:
        return exp(x) - 3.0 * x
    return 0.0


fn eval_deriv(x: Float64, func_id: Int) -> Float64:
    """Evaluate derivative of test function identified by func_id."""
    if func_id == 0:
        return 2.0 * x
    elif func_id == 1:
        return 3.0 * x * x - 1.0
    elif func_id == 2:
        return -sin(x) - 1.0
    elif func_id == 3:
        return exp(x) - 3.0
    return 0.0


# ── Bisection method ────────────────────────────────────────────────────────


fn bisection(
    a: Float64,
    b: Float64,
    func_id: Int,
    tol: Float64 = 1e-10,
    max_iter: Int = 100,
) -> Float64:
    """Bisection method for root finding.

    Requires f(a) and f(b) have opposite signs.
    Returns midpoint approximation to root.
    """
    var lo = a
    var hi = b
    var fa = eval_func(lo, func_id)
    if fa * eval_func(hi, func_id) > 0.0:
        return (lo + hi) / 2.0  # fallback if bracket invalid

    for _ in range(max_iter):
        var mid = (lo + hi) / 2.0
        var fm = eval_func(mid, func_id)
        if fabs(fm) < tol or (hi - lo) / 2.0 < tol:
            return mid
        if fa * fm < 0.0:
            hi = mid
        else:
            lo = mid
            fa = fm
    return (lo + hi) / 2.0


# ── Newton-Raphson method ───────────────────────────────────────────────────


fn newton_raphson(
    x0: Float64,
    func_id: Int,
    tol: Float64 = 1e-10,
    max_iter: Int = 100,
) -> Float64:
    """Newton-Raphson root finding: x_{n+1} = x_n - f(x_n)/f'(x_n)."""
    var x = x0
    for _ in range(max_iter):
        var fx = eval_func(x, func_id)
        if fabs(fx) < tol:
            return x
        var dfx = eval_deriv(x, func_id)
        if fabs(dfx) < 1e-15:
            break
        x = x - fx / dfx
    return x


# ── Secant method ───────────────────────────────────────────────────────────


fn secant_method(
    x0: Float64,
    x1: Float64,
    func_id: Int,
    tol: Float64 = 1e-10,
    max_iter: Int = 100,
) -> Float64:
    """Secant method: uses two previous points to approximate derivative."""
    var xp = x0
    var xc = x1
    var fp = eval_func(xp, func_id)
    var fc = eval_func(xc, func_id)

    for _ in range(max_iter):
        if fabs(fc) < tol:
            return xc
        var denom = fc - fp
        if fabs(denom) < 1e-15:
            break
        var xn = xc - fc * (xc - xp) / denom
        xp = xc
        fp = fc
        xc = xn
        fc = eval_func(xc, func_id)
    return xc


# ── Fixed-point iteration ───────────────────────────────────────────────────


fn fixed_point(
    x0: Float64,
    func_id: Int,
    tol: Float64 = 1e-10,
    max_iter: Int = 100,
) -> Float64:
    """Fixed-point iteration using Newton form: g(x) = x - f(x)/f'(x)."""
    var x = x0
    for _ in range(max_iter):
        var fx = eval_func(x, func_id)
        if fabs(fx) < tol:
            return x
        var dfx = eval_deriv(x, func_id)
        if fabs(dfx) < 1e-15:
            break
        var xn = x - fx / dfx
        if fabs(xn - x) < tol:
            return xn
        x = xn
    return x


# ── Regula Falsi (False Position) ───────────────────────────────────────────


fn regula_falsi(
    a: Float64,
    b: Float64,
    func_id: Int,
    tol: Float64 = 1e-10,
    max_iter: Int = 100,
) -> Float64:
    """False position method (regula falsi) for root finding."""
    var lo = a
    var hi = b
    var flo = eval_func(lo, func_id)
    var fhi = eval_func(hi, func_id)
    if flo * fhi > 0.0:
        return (lo + hi) / 2.0

    for _ in range(max_iter):
        var c = (lo * fhi - hi * flo) / (fhi - flo)
        var fc = eval_func(c, func_id)
        if fabs(fc) < tol:
            return c
        if flo * fc < 0.0:
            hi = c
            fhi = fc
        else:
            lo = c
            flo = fc
    return (lo * fhi - hi * flo) / (fhi - flo)


# ── Bracket finding ─────────────────────────────────────────────────────────


fn bracket_root(
    func_id: Int,
    start: Float64 = 0.0,
    step: Float64 = 0.5,
    max_steps: Int = 100,
) -> List[Float64]:
    """Find bracket [a,b] where f(a)*f(b) < 0.

    Searches outward from start in both directions using given step.
    Returns list of two floats [a, b].
    """
    var result = List[Float64]()
    var a = start
    var fa = eval_func(a, func_id)

    for i in range(1, max_steps + 1):
        var b = start + Float64(i) * step
        var fb = eval_func(b, func_id)
        if fa * fb < 0.0:
            result.append(a)
            result.append(b)
            return result^
        # Also try negative direction
        var c = start - Float64(i) * step
        var fc = eval_func(c, func_id)
        if fa * fc < 0.0:
            result.append(c)
            result.append(a)
            return result^
        a = b
        fa = fb

    # Fallback: return start and start+step
    result.append(start)
    result.append(start + step)
    return result^


# ── Convergence order estimation ─────────────────────────────────────────────


fn convergence_order(errors: List[Float64]) -> Float64:
    """Estimate convergence order from error sequence.

    Uses log(e_{n+1}/e_n) / log(e_n/e_{n-1}) for last valid triple.
    """
    var n = len(errors)
    if n < 3:
        return 0.0

    # Find the last valid triple with positive errors
    var i = n - 3
    while i >= 0:
        var e0 = errors[i]
        var e1 = errors[i + 1]
        var e2 = errors[i + 2]
        if e0 > 1e-15 and e1 > 1e-15 and e2 > 1e-15:
            var r1 = e1 / e0
            var r2 = e2 / e1
            if r1 > 1e-15 and r2 > 1e-15:
                return log(r2) / log(r1)
        i -= 1
    return 0.0
