"""
scipy_stats_ops.mojo — Statistical distribution PDF/CDF/PPF calculations.
Zero Python imports.

Public API:
  normal_pdf                     — Normal / Gaussian PDF
  normal_cdf_approx              — Normal CDF approximation
  t_distribution_pdf             — Student's t PDF
  chi2_pdf                       — Chi-squared PDF
  exponential_pdf                — Exponential distribution PDF
  poisson_pmf                    — Poisson PMF (log-space friendly)
  beta_pdf_unnorm                — Beta distribution unnormalised PDF
  gamma_pdf_unnorm               — Gamma distribution unnormalised PDF
  logistic_pdf                   — Logistic distribution PDF
  weibull_pdf                    — Weibull distribution PDF
"""
from std.math import sqrt, log, exp


fn normal_pdf(x: Float64, mu: Float64, sigma: Float64) -> Float64:
    """Normal (Gaussian) PDF.

    f(x) = 1/(σ√2π) × exp(-(x-μ)²/(2σ²))

    Args:
        x: Value.
        mu: Mean μ.
        sigma: Standard deviation σ.

    Returns:
        PDF value.
    """
    if sigma <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    var z = (x - mu) / sigma
    return exp(-0.5 * z * z) / (sigma * sqrt(2.0 * pi))


fn normal_cdf_approx(x: Float64, mu: Float64, sigma: Float64) -> Float64:
    """Normal CDF approximation using tanh-based erf approximation.

    Φ(x) ≈ 0.5 × (1 + erf((x-μ)/(σ√2)))
    erf approximated via tanh(0.7978845608 × z × (1 + 0.044715z²))

    Args:
        x: Value.
        mu: Mean.
        sigma: Standard deviation.

    Returns:
        CDF value (0–1).
    """
    if sigma <= 0.0:
        if x >= mu:
            return 1.0
        return 0.0
    var z = (x - mu) / (sigma * 1.4142135623730951)
    var erf_approx = 0.7978845608 * z * (1.0 + 0.044715 * z * z)
    var tanh_val: Float64
    if erf_approx > 20.0:
        tanh_val = 1.0
    elif erf_approx < -20.0:
        tanh_val = -1.0
    else:
        var e2 = exp(2.0 * erf_approx)
        tanh_val = (e2 - 1.0) / (e2 + 1.0)
    return 0.5 * (1.0 + tanh_val)


fn t_distribution_pdf(x: Float64, df: Float64) -> Float64:
    """Student's t-distribution PDF (unnormalised proportional form).

    f(x) ∝ (1 + x²/ν)^(-(ν+1)/2)

    Args:
        x: Value.
        df: Degrees of freedom ν.

    Returns:
        Unnormalised PDF value.
    """
    if df <= 0.0:
        return 0.0
    var base = 1.0 + x * x / df
    return exp(-(df + 1.0) / 2.0 * log(base))


fn chi2_pdf(x: Float64, df: Float64) -> Float64:
    """Chi-squared PDF (unnormalised).

    f(x) ∝ x^(k/2 - 1) × exp(-x/2)

    Args:
        x: Value (must be > 0).
        df: Degrees of freedom k.

    Returns:
        Unnormalised chi-squared PDF.
    """
    if x <= 0.0 or df <= 0.0:
        return 0.0
    return exp((df / 2.0 - 1.0) * log(x) - x / 2.0)


fn exponential_pdf(x: Float64, rate: Float64) -> Float64:
    """Exponential distribution PDF.

    f(x) = λ × exp(-λx)  for x ≥ 0

    Args:
        x: Value.
        rate: Rate parameter λ.

    Returns:
        PDF value.
    """
    if x < 0.0 or rate <= 0.0:
        return 0.0
    return rate * exp(-rate * x)


fn poisson_pmf(k: Float64, lam: Float64) -> Float64:
    """Poisson PMF in log space: log P(X=k) = k log λ - λ - log(k!).

    Uses Stirling for log factorial.

    Args:
        k: Count (non-negative integer as Float64).
        lam: Rate parameter λ.

    Returns:
        Log PMF value (returns log probability).
    """
    if lam <= 0.0 or k < 0.0:
        return -1e300
    if k == 0.0:
        return -lam
    var log_k_fact = k * log(k) - k + 0.5 * log(6.283185307 * k)
    return k * log(lam) - lam - log_k_fact


fn beta_pdf_unnorm(x: Float64, alpha: Float64, beta: Float64) -> Float64:
    """Beta distribution unnormalised PDF.

    f(x) ∝ x^(α-1) × (1-x)^(β-1)

    Args:
        x: Value in (0, 1).
        alpha: α shape parameter.
        beta: β shape parameter.

    Returns:
        Unnormalised PDF value.
    """
    if x <= 0.0 or x >= 1.0 or alpha <= 0.0 or beta <= 0.0:
        return 0.0
    return exp((alpha - 1.0) * log(x) + (beta - 1.0) * log(1.0 - x))


fn gamma_pdf_unnorm(x: Float64, shape: Float64, rate: Float64) -> Float64:
    """Gamma distribution unnormalised PDF.

    f(x) ∝ x^(α-1) × exp(-β x)

    Args:
        x: Value (> 0).
        shape: Shape α.
        rate: Rate β.

    Returns:
        Unnormalised PDF value.
    """
    if x <= 0.0 or shape <= 0.0 or rate <= 0.0:
        return 0.0
    return exp((shape - 1.0) * log(x) - rate * x)


fn logistic_pdf(x: Float64, mu: Float64, s: Float64) -> Float64:
    """Logistic distribution PDF.

    f(x) = exp(-(x-μ)/s) / (s × (1 + exp(-(x-μ)/s))²)

    Args:
        x: Value.
        mu: Location.
        s: Scale (> 0).

    Returns:
        PDF value.
    """
    if s <= 0.0:
        return 0.0
    var z = (x - mu) / s
    var e = exp(-z)
    var denom = 1.0 + e
    return e / (s * denom * denom)


fn weibull_pdf(x: Float64, shape: Float64, scale: Float64) -> Float64:
    """Weibull distribution PDF.

    f(x) = (k/λ) × (x/λ)^(k-1) × exp(-(x/λ)^k)

    Args:
        x: Value (≥ 0).
        shape: Shape k.
        scale: Scale λ.

    Returns:
        PDF value.
    """
    if x < 0.0 or shape <= 0.0 or scale <= 0.0:
        return 0.0
    if x == 0.0:
        if shape < 1.0:
            return 1e300
        if shape == 1.0:
            return 1.0 / scale
        return 0.0
    var xs = x / scale
    return (shape / scale) * exp((shape - 1.0) * log(xs) - exp(shape * log(xs)))
