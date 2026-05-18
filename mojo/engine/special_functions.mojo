"""
special_functions.mojo — Special mathematical functions.

Replaces Python's scipy.special with pure Mojo implementations of
gamma, beta, error, Bessel, and combinatorial functions using
Lanczos approximation, series expansions, and polynomial fits.

Public API:
  gamma_function        — Γ(x) via Lanczos approximation
  log_gamma             — ln(Γ(x))
  beta_function         — B(a,b) = Γ(a)Γ(b)/Γ(a+b)
  digamma               — ψ(x) = d/dx ln(Γ(x))
  incomplete_gamma_lower — Lower incomplete gamma γ(a,x)
  regularized_gamma     — P(a,x) = γ(a,x)/Γ(a)
  erf                   — Error function
  erfc                  — Complementary error function
  bessel_j0             — Bessel function J₀(x)
  factorial_float       — n! as Float64
  double_factorial      — n!! double factorial
  binomial_coefficient  — C(n,k) via log-gamma
"""

from std.math import sqrt, log, exp, abs as fabs, sin


# ── Constants ─────────────────────────────────────────────────────────────────

comptime _PI: Float64 = 3.14159265358979323846
comptime _EULER_MASCHERONI: Float64 = 0.5772156649015329


# ── Lanczos approximation coefficients (g=7, n=9) ────────────────────────────

fn _lanczos_coeffs() -> List[Float64]:
    """Lanczos coefficients for g=7."""
    var c = List[Float64]()
    c.append(0.99999999999980993)
    c.append(676.5203681218851)
    c.append(-1259.1392167224028)
    c.append(771.32342877765313)
    c.append(-176.61502916214059)
    c.append(12.507343278686905)
    c.append(-0.13857109526572012)
    c.append(9.9843695780195716e-6)
    c.append(1.5056327351493116e-7)
    return c^


# ── Gamma function ────────────────────────────────────────────────────────────


fn gamma_function(x: Float64) -> Float64:
    """Gamma function Γ(x) via Lanczos approximation.

    For positive integers: Γ(n) = (n-1)!
    """
    if x < 0.5:
        # Reflection formula: Γ(x)Γ(1-x) = π/sin(πx)
        var s = sin(_PI * x)
        if fabs(s) < 1e-15:
            return 1e308  # pole
        return _PI / (s * gamma_function(1.0 - x))

    var z = x - 1.0
    var g: Float64 = 7.0
    var coeffs = _lanczos_coeffs()
    var ag = coeffs[0]
    for i in range(1, 9):
        ag += coeffs[i] / (z + Float64(i))
    var t = z + g + 0.5
    return sqrt(2.0 * _PI) * (t ** (z + 0.5)) * exp(-t) * ag


fn log_gamma(x: Float64) -> Float64:
    """Log-gamma: ln(Γ(x)). More numerically stable for large x."""
    if x < 0.5:
        var s = sin(_PI * x)
        if fabs(s) < 1e-15:
            return 700.0  # large value for pole
        return log(_PI / fabs(s)) - log_gamma(1.0 - x)

    var z = x - 1.0
    var g: Float64 = 7.0
    var coeffs = _lanczos_coeffs()
    var ag = coeffs[0]
    for i in range(1, 9):
        ag += coeffs[i] / (z + Float64(i))
    var t = z + g + 0.5
    return 0.5 * log(2.0 * _PI) + (z + 0.5) * log(t) - t + log(ag)


# ── Beta function ─────────────────────────────────────────────────────────────


fn beta_function(a: Float64, b: Float64) -> Float64:
    """Beta function B(a,b) = Γ(a)Γ(b)/Γ(a+b).

    Uses log-gamma for numerical stability.
    """
    return exp(log_gamma(a) + log_gamma(b) - log_gamma(a + b))


# ── Digamma function ──────────────────────────────────────────────────────────


fn digamma(x: Float64) -> Float64:
    """Digamma function ψ(x) = d/dx ln(Γ(x)).

    Uses recurrence relation to shift x to large value, then asymptotic series.
    """
    var result: Float64 = 0.0
    var z = x

    # Use recurrence: ψ(x+1) = ψ(x) + 1/x to shift to large z
    while z < 6.0:
        result -= 1.0 / z
        z += 1.0

    # Asymptotic expansion for large z
    var z2 = 1.0 / (z * z)
    result += log(z) - 0.5 / z
    result -= z2 * (1.0 / 12.0 - z2 * (1.0 / 120.0 - z2 * (1.0 / 252.0
        - z2 * (1.0 / 240.0 - z2 * (1.0 / 132.0)))))
    return result


# ── Incomplete gamma ──────────────────────────────────────────────────────────


fn incomplete_gamma_lower(a: Float64, x: Float64) -> Float64:
    """Lower incomplete gamma γ(a,x) via series expansion.

    γ(a,x) = x^a * e^(-x) * Σ_{n=0}^∞ x^n / (a*(a+1)*...*(a+n))
    """
    if x < 0.0:
        return 0.0
    if x == 0.0:
        return 0.0

    var term = 1.0 / a
    var total = term
    for n in range(1, 200):
        term *= x / (a + Float64(n))
        total += term
        if fabs(term) < 1e-15 * fabs(total):
            break

    return total * exp(-x + a * log(x))


fn regularized_gamma(a: Float64, x: Float64) -> Float64:
    """P(a,x) = γ(a,x)/Γ(a). Regularized lower incomplete gamma."""
    if x <= 0.0:
        return 0.0
    return incomplete_gamma_lower(a, x) / gamma_function(a)


# ── Error function ────────────────────────────────────────────────────────────


fn erf(x: Float64) -> Float64:
    """Error function via Abramowitz & Stegun approximation (eq 7.1.26).

    Maximum error: |ε| < 1.5×10⁻⁷.
    """
    var sign: Float64 = 1.0
    var ax = x
    if x < 0.0:
        sign = -1.0
        ax = -x

    # Constants
    var p: Float64 = 0.3275911
    var a1: Float64 = 0.254829592
    var a2: Float64 = -0.284496736
    var a3: Float64 = 1.421413741
    var a4: Float64 = -1.453152027
    var a5: Float64 = 1.061405429

    var t = 1.0 / (1.0 + p * ax)
    var t2 = t * t
    var t3 = t2 * t
    var t4 = t3 * t
    var t5 = t4 * t

    var y = 1.0 - (a1 * t + a2 * t2 + a3 * t3 + a4 * t4 + a5 * t5) * exp(
        -ax * ax
    )
    return sign * y


fn erfc(x: Float64) -> Float64:
    """Complementary error function: 1 - erf(x)."""
    return 1.0 - erf(x)


# ── Bessel function J0 ───────────────────────────────────────────────────────


fn bessel_j0(x: Float64) -> Float64:
    """Bessel function J₀(x) via polynomial approximation for |x| ≤ 8,
    asymptotic form for larger x.

    Uses series: J₀(x) = Σ_{m=0}^∞ (-1)^m (x/2)^(2m) / (m!)²
    """
    var ax = fabs(x)

    if ax < 8.0:
        # Power series: J0(x) = sum_{m=0}^inf (-1)^m * (x/2)^{2m} / (m!)^2
        var x2 = x * x
        var term: Float64 = 1.0
        var total: Float64 = 1.0
        for m in range(1, 30):
            term *= -x2 / (4.0 * Float64(m) * Float64(m))
            total += term
            if fabs(term) < 1e-15:
                break
        return total
    else:
        # Asymptotic approximation for large x
        var z = 8.0 / ax
        var z2 = z * z
        var p0 = 1.0 - 0.1098628627e-2 * z2 + 0.2734510407e-4 * z2 * z2
        var q0 = -0.1562499995e-1 * z + 0.1430488765e-3 * z * z2
        var theta = ax - 0.7853981634
        return sqrt(0.636619772 / ax) * (p0 * _cos_approx(theta)
            - q0 * _sin_approx(theta))


fn _cos_approx(x: Float64) -> Float64:
    """Cosine approximation using Taylor series."""
    # Reduce to [0, 2π]
    var two_pi: Float64 = 2.0 * _PI
    var z = x
    while z > two_pi:
        z -= two_pi
    while z < 0.0:
        z += two_pi
    # Taylor series around 0
    var x2 = z * z
    return 1.0 - x2 / 2.0 + x2 * x2 / 24.0 - x2 * x2 * x2 / 720.0 + x2 * x2 * x2 * x2 / 40320.0


fn _sin_approx(x: Float64) -> Float64:
    """Sine approximation using Taylor series."""
    var two_pi: Float64 = 2.0 * _PI
    var z = x
    while z > two_pi:
        z -= two_pi
    while z < 0.0:
        z += two_pi
    var x2 = z * z
    return z * (1.0 - x2 / 6.0 + x2 * x2 / 120.0 - x2 * x2 * x2 / 5040.0)


# ── Factorial functions ───────────────────────────────────────────────────────


fn factorial_float(n: Int) -> Float64:
    """n! as Float64. Uses direct multiplication for small n, gamma for large."""
    if n < 0:
        return 0.0
    if n <= 1:
        return 1.0
    if n <= 20:
        var result: Float64 = 1.0
        for i in range(2, n + 1):
            result *= Float64(i)
        return result
    # For large n, use Γ(n+1) = n!
    return gamma_function(Float64(n) + 1.0)


fn double_factorial(n: Int) -> Float64:
    """n!! = n*(n-2)*(n-4)*...*1 (or 2).

    Double factorial: product of all integers from n down stepping by 2.
    """
    if n <= 0:
        return 1.0
    var result: Float64 = 1.0
    var k = n
    while k > 0:
        result *= Float64(k)
        k -= 2
    return result


# ── Binomial coefficient ─────────────────────────────────────────────────────


fn binomial_coefficient(n: Int, k: Int) -> Float64:
    """C(n,k) = n! / (k! * (n-k)!) via log-gamma for numerical stability."""
    if k < 0 or k > n:
        return 0.0
    if k == 0 or k == n:
        return 1.0
    var fn_val = Float64(n) + 1.0
    var fk = Float64(k) + 1.0
    var fnk = Float64(n - k) + 1.0
    var log_binom = log_gamma(fn_val) - log_gamma(fk) - log_gamma(fnk)
    return exp(log_binom)
