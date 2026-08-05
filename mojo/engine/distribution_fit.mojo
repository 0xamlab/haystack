"""
distribution_fit.mojo — Distribution Fitting. Zero Python imports.

Replaces scipy.stats.fit with pure Mojo implementations of MLE fitting
for normal, exponential, uniform, and Weibull distributions, plus
log-likelihood, AIC/BIC model selection, and QQ residuals.

Public API:
  fit_normal                — Fit normal distribution (returns [mean, std])
  fit_exponential           — Fit exponential distribution (returns rate λ)
  fit_uniform               — Fit uniform distribution (returns [min, max])
  fit_weibull               — Fit Weibull via method of moments (returns [shape, scale])
  log_likelihood_normal     — Log-likelihood for normal
  log_likelihood_exponential — Log-likelihood for exponential
  aic                       — Akaike Information Criterion
  bic                       — Bayesian Information Criterion
  best_fit                  — Compare normal/exponential/uniform by AIC
  qq_residuals              — QQ plot residuals vs expected normal quantiles
"""

from std.math import sqrt, log, abs as fabs, exp


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime TWO_PI: Float64 = 6.283185307179586
comptime LOG_TWO_PI: Float64 = 1.8378770664093453


# ── fit_normal ───────────────────────────────────────────────────────────────


fn fit_normal(data: List[Float64]) -> List[Float64]:
    """Fit normal distribution via MLE. Returns [mean, std]."""
    var n = len(data)
    # Empty data would divide by n == 0 and return NaN, which cannot cross
    # the result wire.
    if n == 0:
        return List[Float64]()
    var mean: Float64 = 0.0
    for i in range(n):
        mean += data[i]
    mean /= Float64(n)
    var var_sum: Float64 = 0.0
    for i in range(n):
        var d = data[i] - mean
        var_sum += d * d
    var std = sqrt(var_sum / Float64(n))
    var result = List[Float64]()
    result.append(mean)
    result.append(std)
    return result^


# ── fit_exponential ──────────────────────────────────────────────────────────


fn fit_exponential(data: List[Float64]) -> Float64:
    """Fit exponential distribution via MLE. Returns λ (rate = 1/mean)."""
    var n = len(data)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += data[i]
    var mean = s / Float64(n)
    if mean <= 0.0:
        return 1.0
    return 1.0 / mean


# ── fit_uniform ──────────────────────────────────────────────────────────────


fn fit_uniform(data: List[Float64]) -> List[Float64]:
    """Fit uniform distribution via MLE. Returns [min, max]."""
    if len(data) == 0:
        return List[Float64]()
    var lo = data[0]
    var hi = data[0]
    for i in range(1, len(data)):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]
    var result = List[Float64]()
    result.append(lo)
    result.append(hi)
    return result^


# ── fit_weibull ──────────────────────────────────────────────────────────────


fn fit_weibull(data: List[Float64]) -> List[Float64]:
    """Fit Weibull distribution via method of moments approximation.
    Returns [shape_beta, scale_eta].
    Uses iterative estimation: CV -> shape, then scale from mean.
    """
    var n = len(data)
    if n == 0:
        return List[Float64]()
    var mean: Float64 = 0.0
    for i in range(n):
        mean += data[i]
    mean /= Float64(n)
    var var_sum: Float64 = 0.0
    for i in range(n):
        var d = data[i] - mean
        var_sum += d * d
    var std = sqrt(var_sum / Float64(n))
    # Coefficient of variation
    var cv = std / mean if mean > 0.0 else 1.0
    # Approximate shape from CV: beta ≈ 1.2 / CV (simple approximation)
    var shape = 1.2 / cv if cv > 0.0 else 1.0
    if shape < 0.1:
        shape = 0.1
    # Gamma(1 + 1/beta) approximation using Stirling for scale
    # scale = mean / Gamma(1 + 1/beta)
    # For simplicity, use Gamma(1+x) ≈ exp(-0.5772*x) for small x
    var inv_shape = 1.0 / shape
    var gamma_approx = _gamma_approx(1.0 + inv_shape)
    var scale = mean / gamma_approx if gamma_approx > 0.0 else mean
    var result = List[Float64]()
    result.append(shape)
    result.append(scale)
    return result^


fn _gamma_approx(x: Float64) -> Float64:
    """Lanczos-style gamma approximation for x > 0."""
    # For x in [1,2], use simple polynomial approximation
    # Gamma(1) = 1, Gamma(1.5) ≈ 0.8862, Gamma(2) = 1
    if x <= 0.0:
        return 1.0
    if x < 1.0:
        return _gamma_approx(x + 1.0) / x
    if x < 2.0:
        var t = x - 1.0
        # Interpolation: Gamma(1)=1, Gamma(1.5)=0.8862, Gamma(2)=1
        # Quadratic fit through these 3 points
        return 1.0 - 0.4552 * t + 0.4552 * t * t
    # For x >= 2, use recursion: Gamma(x) = (x-1)*Gamma(x-1)
    return (x - 1.0) * _gamma_approx(x - 1.0)


# ── log_likelihood_normal ────────────────────────────────────────────────────


fn log_likelihood_normal(data: List[Float64], mean: Float64, std: Float64) -> Float64:
    """Log-likelihood for normal distribution."""
    var n = len(data)
    var s = std
    if s <= 0.0:
        s = 1e-10
    var ll: Float64 = -Float64(n) * 0.5 * LOG_TWO_PI - Float64(n) * log(s)
    var inv_2s2 = 1.0 / (2.0 * s * s)
    for i in range(n):
        var d = data[i] - mean
        ll -= d * d * inv_2s2
    return ll


# ── log_likelihood_exponential ───────────────────────────────────────────────


fn log_likelihood_exponential(data: List[Float64], rate: Float64) -> Float64:
    """Log-likelihood for exponential distribution."""
    var n = len(data)
    var r = rate
    if r <= 0.0:
        r = 1e-10
    var ll = Float64(n) * log(r)
    for i in range(n):
        ll -= r * data[i]
    return ll


# ── aic ──────────────────────────────────────────────────────────────────────


fn aic(log_likelihood: Float64, k: Int) -> Float64:
    """Akaike Information Criterion: 2k - 2*LL."""
    return 2.0 * Float64(k) - 2.0 * log_likelihood


# ── bic ──────────────────────────────────────────────────────────────────────


fn bic(log_likelihood: Float64, k: Int, n: Int) -> Float64:
    """Bayesian Information Criterion: k*ln(n) - 2*LL."""
    return Float64(k) * log(Float64(n)) - 2.0 * log_likelihood


# ── _log_likelihood_uniform ──────────────────────────────────────────────────


fn _log_likelihood_uniform(data: List[Float64], lo: Float64, hi: Float64) -> Float64:
    """Log-likelihood for uniform distribution."""
    var n = len(data)
    var rng = hi - lo
    if rng <= 0.0:
        return -1e18
    for i in range(n):
        if data[i] < lo or data[i] > hi:
            return -1e18
    return -Float64(n) * log(rng)


# ── best_fit ─────────────────────────────────────────────────────────────────


fn best_fit(data: List[Float64]) -> Int:
    """Compare normal(0) vs exponential(1) vs uniform(2) by AIC.
    Returns index of best fit (lowest AIC).
    """
    # Empty data makes every fit return an empty parameter list, which the
    # [0]/[1] reads below would abort on.
    if len(data) == 0:
        return -1
    # Normal fit
    var norm_params = fit_normal(data)
    var ll_norm = log_likelihood_normal(data, norm_params[0], norm_params[1])
    var aic_norm = aic(ll_norm, 2)

    # Exponential fit
    var rate = fit_exponential(data)
    var ll_exp = log_likelihood_exponential(data, rate)
    var aic_exp = aic(ll_exp, 1)

    # Uniform fit
    var uni_params = fit_uniform(data)
    var ll_uni = _log_likelihood_uniform(data, uni_params[0], uni_params[1])
    var aic_uni = aic(ll_uni, 2)

    # Find minimum AIC
    var best_idx = 0
    var best_aic = aic_norm
    if aic_exp < best_aic:
        best_aic = aic_exp
        best_idx = 1
    if aic_uni < best_aic:
        best_aic = aic_uni
        best_idx = 2
    return best_idx


# ── _erfinv_approx ──────────────────────────────────────────────────────────


fn _erfinv_approx(p: Float64) -> Float64:
    """Approximate inverse error function using rational approximation."""
    # Clamp to avoid infinities
    var x = p
    if x <= -1.0:
        x = -0.9999
    if x >= 1.0:
        x = 0.9999
    var a: Float64 = 0.147
    var ln_term = log(1.0 - x * x)
    var b = 2.0 / (PI * a) + ln_term / 2.0
    var sgn: Float64 = 1.0
    if x < 0.0:
        sgn = -1.0
    var val = sqrt(sqrt(b * b - ln_term / a) - b)
    return sgn * val


fn _normal_quantile(p: Float64) -> Float64:
    """Inverse normal CDF (quantile function) via inverse erf."""
    return sqrt(2.0) * _erfinv_approx(2.0 * p - 1.0)


# ── qq_residuals ─────────────────────────────────────────────────────────────


fn qq_residuals(data: List[Float64], mean: Float64, std: Float64) -> List[Float64]:
    """QQ plot residuals: sorted data vs expected normal quantiles.
    residual[i] = sorted_data[i] - (mean + std * Phi^-1((i+0.5)/n))
    """
    var n = len(data)
    # Sort data (insertion sort)
    var sorted_data = List[Float64]()
    for i in range(n):
        sorted_data.append(data[i])
    for i in range(1, n):
        var key = sorted_data[i]
        var j = i - 1
        while j >= 0 and sorted_data[j] > key:
            sorted_data[j + 1] = sorted_data[j]
            j -= 1
        sorted_data[j + 1] = key

    var residuals = List[Float64]()
    for i in range(n):
        var p = (Float64(i) + 0.5) / Float64(n)
        var expected = mean + std * _normal_quantile(p)
        residuals.append(sorted_data[i] - expected)
    return residuals^
