"""
optimize.mojo — Numerical optimization. Zero Python imports.
Replaces: scipy.optimize.minimize_scalar, brentq, newton, golden_section

Public API:
  OptResult struct
  minimize_scalar_golden, minimize_brent, root_bisection, root_newton,
  gradient_descent_1d, eval_poly, eval_poly_deriv, linear_regression
"""
from std.math import sqrt, abs as fabs, pow


# ── Constants ─────────────────────────────────────────────────────────────────

comptime _PHI = 1.6180339887498949          # golden ratio
comptime _RESPHI = 0.3819660112501051       # 2 - phi  (= 1/phi^2)


# ── Result struct ─────────────────────────────────────────────────────────────


struct OptResult(Copyable, Movable):
    """Result of an optimization or root-finding routine."""
    var x: Float64          # optimal x
    var fun: Float64        # function value at x
    var iterations: Int     # iterations used
    var converged: Bool     # whether convergence was achieved

    def __init__(out self, x: Float64, fun: Float64, iterations: Int, converged: Bool):
        self.x = x
        self.fun = fun
        self.iterations = iterations
        self.converged = converged


# ── Polynomial evaluation ─────────────────────────────────────────────────────


def eval_poly(coeffs: List[Float64], x: Float64) -> Float64:
    """Evaluate polynomial: coeffs[0] + coeffs[1]*x + coeffs[2]*x^2 + ...
    Uses Horner's method for numerical stability."""
    var n = len(coeffs)
    if n == 0:
        return 0.0
    var result = coeffs[n - 1]
    var i = n - 2
    while i >= 0:
        result = result * x + coeffs[i]
        i -= 1
    return result


def eval_poly_deriv(coeffs: List[Float64], x: Float64) -> Float64:
    """Evaluate polynomial derivative: coeffs[1] + 2*coeffs[2]*x + 3*coeffs[3]*x^2 + ...
    Uses Horner's method."""
    var n = len(coeffs)
    if n <= 1:
        return 0.0
    # Derivative coefficients: i * coeffs[i] for i = 1..n-1
    # Horner: start from highest degree
    var result = Float64(n - 1) * coeffs[n - 1]
    var i = n - 2
    while i >= 1:
        result = result * x + Float64(i) * coeffs[i]
        i -= 1
    return result


def _eval_poly_deriv2(coeffs: List[Float64], x: Float64) -> Float64:
    """Evaluate second derivative of polynomial."""
    var n = len(coeffs)
    if n <= 2:
        return 0.0
    var result = Float64(n - 1) * Float64(n - 2) * coeffs[n - 1]
    var i = n - 2
    while i >= 2:
        result = result * x + Float64(i) * Float64(i - 1) * coeffs[i]
        i -= 1
    return result


# ── Golden section search ─────────────────────────────────────────────────────


def minimize_scalar_golden(f_coeffs: List[Float64], a: Float64, b: Float64,
                          tol: Float64 = 1e-8, max_iter: Int = 1000) -> OptResult:
    """Golden section search for minimum of f(x) on [a,b].
    f_coeffs: polynomial coefficients [a0, a1, a2, ...] for f(x) = a0 + a1*x + a2*x^2 + ...
    """
    var lo = a
    var hi = b
    # x1 = left interior point, x2 = right interior point
    var x1 = lo + _RESPHI * (hi - lo)
    var x2 = hi - _RESPHI * (hi - lo)
    var f1 = eval_poly(f_coeffs, x1)
    var f2 = eval_poly(f_coeffs, x2)

    var iters = 0
    while iters < max_iter and (hi - lo) > tol:
        if f1 < f2:
            # Minimum is in [lo, x2]
            hi = x2
            x2 = x1
            f2 = f1
            x1 = lo + _RESPHI * (hi - lo)
            f1 = eval_poly(f_coeffs, x1)
        else:
            # Minimum is in [x1, hi]
            lo = x1
            x1 = x2
            f1 = f2
            x2 = hi - _RESPHI * (hi - lo)
            f2 = eval_poly(f_coeffs, x2)
        iters += 1

    var x_opt = (lo + hi) / 2.0
    var f_opt = eval_poly(f_coeffs, x_opt)
    var converged = (hi - lo) <= tol
    return OptResult(x_opt, f_opt, iters, converged)


# ── Brent's method for minimization ──────────────────────────────────────────


def minimize_brent(f_coeffs: List[Float64], a: Float64, b: Float64,
                  tol: Float64 = 1e-8, max_iter: Int = 200) -> OptResult:
    """Brent's method for function minimization on [a,b].
    Combines golden section with parabolic interpolation."""
    var lo = a
    var hi = b
    var x_best = lo + _RESPHI * (hi - lo)
    var w = x_best
    var v = x_best
    var f_best = eval_poly(f_coeffs, x_best)
    var fw = f_best
    var fv = f_best

    var d: Float64 = 0.0
    var e: Float64 = 0.0  # distance moved in the step before last

    var iters = 0
    while iters < max_iter:
        var mid = 0.5 * (lo + hi)
        var tol1 = tol * fabs(x_best) + 1e-10
        var tol2 = 2.0 * tol1

        # Convergence check
        if fabs(x_best - mid) <= (tol2 - 0.5 * (hi - lo)):
            return OptResult(x_best, f_best, iters, True)

        # Try parabolic interpolation
        var do_golden = True
        if fabs(e) > tol1:
            # Fit parabola
            var r = (x_best - w) * (f_best - fv)
            var q = (x_best - v) * (f_best - fw)
            var p = (x_best - v) * q - (x_best - w) * r
            q = 2.0 * (q - r)
            if q > 0.0:
                p = -p
            else:
                q = -q
            var r2 = e
            e = d

            if fabs(p) < fabs(0.5 * q * r2) and p > q * (lo - x_best) and p < q * (hi - x_best):
                # Parabolic step
                d = p / q
                var u = x_best + d
                if (u - lo) < tol2 or (hi - u) < tol2:
                    if x_best < mid:
                        d = tol1
                    else:
                        d = -tol1
                do_golden = False

        if do_golden:
            if x_best < mid:
                e = hi - x_best
            else:
                e = lo - x_best
            d = _RESPHI * e

        var u: Float64
        if fabs(d) >= tol1:
            u = x_best + d
        else:
            if d > 0.0:
                u = x_best + tol1
            else:
                u = x_best - tol1

        var fu = eval_poly(f_coeffs, u)

        if fu <= f_best:
            if u < x_best:
                hi = x_best
            else:
                lo = x_best
            v = w
            fv = fw
            w = x_best
            fw = f_best
            x_best = u
            f_best = fu
        else:
            if u < x_best:
                lo = u
            else:
                hi = u
            if fu <= fw or w == x_best:
                v = w
                fv = fw
                w = u
                fw = fu
            elif fu <= fv or v == x_best or v == w:
                v = u
                fv = fu

        iters += 1

    return OptResult(x_best, f_best, iters, False)


# ── Bisection root finding ────────────────────────────────────────────────────


def root_bisection(f_coeffs: List[Float64], a: Float64, b: Float64,
                  tol: Float64 = 1e-10, max_iter: Int = 100) -> OptResult:
    """Bisection method for root finding: find x where f(x)=0.
    Requires f(a) and f(b) to have opposite signs."""
    var lo = a
    var hi = b
    var f_lo = eval_poly(f_coeffs, lo)
    var f_hi = eval_poly(f_coeffs, hi)

    # Ensure f(lo) < 0 and f(hi) > 0, or swap
    if f_lo > 0.0:
        var tmp = lo
        lo = hi
        hi = tmp
        var ftmp = f_lo
        f_lo = f_hi
        f_hi = ftmp

    var iters = 0
    while iters < max_iter:
        var mid = (lo + hi) / 2.0
        var f_mid = eval_poly(f_coeffs, mid)

        if fabs(f_mid) < tol or (hi - lo) / 2.0 < tol:
            return OptResult(mid, f_mid, iters, True)

        if f_mid < 0.0:
            lo = mid
            f_lo = f_mid
        else:
            hi = mid
            f_hi = f_mid

        iters += 1

    var x_final = (lo + hi) / 2.0
    return OptResult(x_final, eval_poly(f_coeffs, x_final), iters, False)


# ── Newton-Raphson root finding ───────────────────────────────────────────────


def root_newton(x0: Float64, f_coeffs: List[Float64],
               tol: Float64 = 1e-10, max_iter: Int = 50) -> OptResult:
    """Newton-Raphson root finding using polynomial derivative.
    Finds x where f(x)=0 starting from initial guess x0."""
    var x = x0

    var iters = 0
    while iters < max_iter:
        var fx = eval_poly(f_coeffs, x)
        var fpx = eval_poly_deriv(f_coeffs, x)

        if fabs(fpx) < 1e-15:
            # Derivative too small, can't continue
            return OptResult(x, fx, iters, False)

        var x_new = x - fx / fpx

        if fabs(x_new - x) < tol:
            return OptResult(x_new, eval_poly(f_coeffs, x_new), iters + 1, True)

        x = x_new
        iters += 1

    return OptResult(x, eval_poly(f_coeffs, x), iters, False)


# ── 1D Gradient descent ──────────────────────────────────────────────────────


# Divergent iterates overflow eval_poly to ±inf (or NaN); non-finite values cannot cross
# the JSON result wire, so a result value is replaced with 0.0 when it is not finite.
def _wire_finite(v: Float64) -> Float64:
    if v - v != 0.0:
        return 0.0
    if v > 1e300 or v < -1e300:
        return 0.0
    return v


def gradient_descent_1d(f_coeffs: List[Float64], x0: Float64,
                       lr: Float64 = 0.01, tol: Float64 = 1e-8,
                       max_iter: Int = 1000) -> OptResult:
    """1D gradient descent using polynomial derivative.
    Minimizes f(x) starting from x0 with given learning rate."""
    if len(f_coeffs) == 0:
        return OptResult(x0, 0.0, 0, True)
    # Untrusted count: max_iter drives the loop; clamp to a documented ceiling.
    var iters_limit = max_iter
    if iters_limit > 100000:
        iters_limit = 100000
    var x = x0

    var iters = 0
    while iters < iters_limit:
        var grad = eval_poly_deriv(f_coeffs, x)

        if fabs(grad) < tol:
            return OptResult(x, _wire_finite(eval_poly(f_coeffs, x)), iters, True)

        var x_new = x - lr * grad
        # Divergence drives x_new inf/NaN, which cannot cross the result wire.
        if x_new - x_new != 0.0:
            return OptResult(x, _wire_finite(eval_poly(f_coeffs, x)), iters + 1, False)

        if fabs(x_new - x) < tol:
            return OptResult(x_new, _wire_finite(eval_poly(f_coeffs, x_new)), iters + 1, True)

        x = x_new
        iters += 1

    return OptResult(x, _wire_finite(eval_poly(f_coeffs, x)), iters, False)


# ── Linear regression ─────────────────────────────────────────────────────────


struct LinRegResult(Copyable, Movable):
    """Result of linear regression."""
    var slope: Float64
    var intercept: Float64
    var r_squared: Float64

    def __init__(out self, slope: Float64, intercept: Float64, r_squared: Float64):
        self.slope = slope
        self.intercept = intercept
        self.r_squared = r_squared


def linear_regression(x: List[Float64], y: List[Float64]) -> LinRegResult:
    """Simple linear regression. Returns LinRegResult(slope, intercept, r_squared).
    Uses the least-squares formula:
      slope = Σ(xi - x̄)(yi - ȳ) / Σ(xi - x̄)²
      intercept = ȳ - slope * x̄
      r² = [Σ(xi - x̄)(yi - ȳ)]² / [Σ(xi - x̄)² * Σ(yi - ȳ)²]
    """
    var n = len(x)
    if n < 2 or len(y) < 2:
        return LinRegResult(0.0, 0.0, 0.0)
    if len(y) < n:
        n = len(y)

    # Compute means
    var sum_x: Float64 = 0.0
    var sum_y: Float64 = 0.0
    for i in range(n):
        sum_x += x[i]
        sum_y += y[i]
    var mean_x = sum_x / Float64(n)
    var mean_y = sum_y / Float64(n)

    # Compute sums of squares
    var ss_xy: Float64 = 0.0
    var ss_xx: Float64 = 0.0
    var ss_yy: Float64 = 0.0
    for i in range(n):
        var dx = x[i] - mean_x
        var dy = y[i] - mean_y
        ss_xy += dx * dy
        ss_xx += dx * dx
        ss_yy += dy * dy

    if ss_xx == 0.0:
        return LinRegResult(0.0, mean_y, 0.0)

    var slope = ss_xy / ss_xx
    var intercept = mean_y - slope * mean_x

    var r_squared: Float64 = 0.0
    if ss_yy > 0.0:
        r_squared = (ss_xy * ss_xy) / (ss_xx * ss_yy)

    return LinRegResult(slope, intercept, r_squared)
