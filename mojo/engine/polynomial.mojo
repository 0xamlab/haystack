"""
polynomial.mojo — Polynomial operations. Zero Python imports.

Replaces numpy.polynomial with pure Mojo implementations of polynomial
evaluation, arithmetic, calculus, root-finding, and composition.

Coefficients stored as List[Float64] where index i = coefficient of x^i
(constant first): [a0, a1, a2, ...] = a0 + a1*x + a2*x² + ...

Public API:
  poly_eval        — evaluate polynomial at x (Horner's method)
  poly_add         — add two polynomials
  poly_multiply    — multiply two polynomials (convolution)
  poly_derivative  — derivative of polynomial
  poly_integral    — indefinite integral with constant C
  poly_degree      — degree (index of highest non-zero coeff)
  quadratic_roots  — roots of ax² + bx + c
  poly_scale       — multiply all coefficients by scalar
  poly_compose     — compose f(g(x))
  poly_from_roots  — build polynomial from roots
"""

from std.math import abs as fabs, sqrt


# ── poly_eval ────────────────────────────────────────────────────────────────


def poly_eval(coeffs: List[Float64], x: Float64) -> Float64:
    """Evaluate polynomial at x using Horner's method."""
    var n = len(coeffs)
    if n == 0:
        return 0.0
    # Horner's: start from highest degree
    var result = coeffs[n - 1]
    var i = n - 2
    while i >= 0:
        result = result * x + coeffs[i]
        i -= 1
    return result


# ── poly_add ─────────────────────────────────────────────────────────────────


def poly_add(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Add two polynomials."""
    var na = len(a)
    var nb = len(b)
    var n = na if na > nb else nb
    var result = List[Float64]()
    for i in range(n):
        var va: Float64 = 0.0
        var vb: Float64 = 0.0
        if i < na:
            va = a[i]
        if i < nb:
            vb = b[i]
        result.append(va + vb)
    return result^


# ── poly_multiply ────────────────────────────────────────────────────────────


def poly_multiply(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Multiply two polynomials (convolution)."""
    var na = len(a)
    var nb = len(b)
    if na == 0 or nb == 0:
        return List[Float64]()
    var nc = na + nb - 1
    var result = List[Float64]()
    for _ in range(nc):
        result.append(0.0)
    for i in range(na):
        for j in range(nb):
            result[i + j] += a[i] * b[j]
    return result^


# ── poly_derivative ──────────────────────────────────────────────────────────


def poly_derivative(coeffs: List[Float64]) -> List[Float64]:
    """Derivative: d/dx of polynomial."""
    var n = len(coeffs)
    if n <= 1:
        var zero = List[Float64]()
        zero.append(0.0)
        return zero^
    var result = List[Float64]()
    for i in range(1, n):
        result.append(Float64(i) * coeffs[i])
    return result^


# ── poly_integral ────────────────────────────────────────────────────────────


def poly_integral(coeffs: List[Float64], C: Float64 = 0.0) -> List[Float64]:
    """Indefinite integral with constant C."""
    var n = len(coeffs)
    var result = List[Float64]()
    result.append(C)
    for i in range(n):
        result.append(coeffs[i] / Float64(i + 1))
    return result^


# ── poly_degree ──────────────────────────────────────────────────────────────


def poly_degree(coeffs: List[Float64]) -> Int:
    """Degree (index of highest non-zero coefficient)."""
    var n = len(coeffs)
    if n == 0:
        return -1
    var deg = n - 1
    while deg > 0 and fabs(coeffs[deg]) < 1e-15:
        deg -= 1
    return deg


# ── quadratic_roots ──────────────────────────────────────────────────────────


def quadratic_roots(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    """Roots of ax² + bx + c. Returns [r1, r2] or [] if complex."""
    var result = List[Float64]()
    if fabs(a) < 1e-15:
        # Linear or degenerate
        if fabs(b) > 1e-15:
            result.append(-c / b)
        return result^
    var disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return result^  # complex roots
    var sq = sqrt(disc)
    var r1 = (-b - sq) / (2.0 * a)
    var r2 = (-b + sq) / (2.0 * a)
    result.append(r1)
    result.append(r2)
    return result^


# ── poly_scale ───────────────────────────────────────────────────────────────


def poly_scale(coeffs: List[Float64], s: Float64) -> List[Float64]:
    """Multiply all coefficients by scalar."""
    var n = len(coeffs)
    var result = List[Float64]()
    for i in range(n):
        result.append(coeffs[i] * s)
    return result^


# ── poly_compose ─────────────────────────────────────────────────────────────


def poly_compose(f: List[Float64], g: List[Float64]) -> List[Float64]:
    """Compose f(g(x)): substitute g into f.

    Uses Horner-like approach: result = f[n-1], then
    result = result * g + f[n-2], etc.
    """
    var nf = len(f)
    if nf == 0:
        return List[Float64]()
    # Start with highest coefficient as a constant polynomial
    var result = List[Float64]()
    result.append(f[nf - 1])
    var i = nf - 2
    while i >= 0:
        # result = result * g + f[i]
        result = poly_multiply(result, g)
        # Add f[i] to constant term
        if len(result) == 0:
            result.append(f[i])
        else:
            result[0] += f[i]
        i -= 1
    return result^


# ── poly_from_roots ──────────────────────────────────────────────────────────


def poly_from_roots(roots: List[Float64]) -> List[Float64]:
    """Build polynomial from roots: (x-r1)(x-r2)...

    Each factor (x - ri) = [-ri, 1] in our representation.
    """
    var n = len(roots)
    if n == 0:
        var one = List[Float64]()
        one.append(1.0)
        return one^
    # Start with (x - roots[0]) = [-roots[0], 1]
    var result = List[Float64]()
    result.append(-roots[0])
    result.append(1.0)
    for i in range(1, n):
        var factor = List[Float64]()
        factor.append(-roots[i])
        factor.append(1.0)
        result = poly_multiply(result, factor)
    return result^
