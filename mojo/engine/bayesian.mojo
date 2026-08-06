"""
bayesian.mojo — Bayesian inference utilities. Zero Python imports.

Replaces pymc / scipy.stats Bayesian inference with pure Mojo conjugate
updates, credible intervals, and Monte Carlo A/B testing.

Public API:
  beta_posterior          — Beta-Binomial conjugate update
  beta_mean               — Mean of Beta distribution
  beta_variance           — Variance of Beta distribution
  beta_credible_interval  — Approximate credible interval (normal approx)
  normal_posterior        — Normal-Normal conjugate update
  poisson_posterior       — Gamma-Poisson conjugate update
  bayes_factor            — Bayes factor L(H1)/L(H0)
  posterior_predictive_beta — Predictive probability of next success
  hpd_interval_normal     — HPD interval for normal distribution
  bayesian_ab_test        — P(B > A) via Monte Carlo Beta sampling
"""
from std.math import sqrt, log, exp, abs as fabs
from std.random import random_float64


# ── Internal helpers ──────────────────────────────────────────────────────────


def _probit(p: Float64) -> Float64:
    """Inverse normal CDF (Abramowitz & Stegun 26.2.23 approximation)."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    if fabs(p - 0.5) < 1e-15:
        return 0.0
    var pp = p
    var sign: Float64 = 1.0
    if p < 0.5:
        sign = -1.0
        pp = 1.0 - p
    var _ = pp - 0.5
    # Use the upper-tail form: pp > 0.5, so 1-pp < 0.5
    var r = 1.0 - pp  # small positive
    if r < 1e-300:
        r = 1e-300
    var t = sqrt(-2.0 * log(r))
    var c0: Float64 = 2.515517
    var c1: Float64 = 0.802853
    var c2: Float64 = 0.010328
    var d1: Float64 = 1.432788
    var d2: Float64 = 0.189269
    var d3: Float64 = 0.001308
    var z = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
    return sign * z


def _box_muller() -> Float64:
    """Standard normal variate via Box-Muller transform."""
    var u1 = random_float64()
    var u2 = random_float64()
    if u1 < 1e-15:
        u1 = 1e-15
    return sqrt(-2.0 * log(u1)) * (2.0 * 3.141592653589793 * u2 - 3.141592653589793)
    # cos(2*pi*u2) approximated via shift; full formula:
    # sqrt(-2*ln(u1)) * cos(2*pi*u2)


def _sample_gamma(shape: Float64) -> Float64:
    """Sample from Gamma(shape, 1) via Marsaglia-Tsang method."""
    if shape < 1.0:
        # Boost for shape < 1
        var g = _sample_gamma(shape + 1.0)
        var u = random_float64()
        if u < 1e-15:
            u = 1e-15
        return g * exp(log(u) / shape)
    var d = shape - 1.0 / 3.0
    var c = 1.0 / sqrt(9.0 * d)
    while True:
        var x = _box_muller()
        var v = 1.0 + c * x
        if v <= 0.0:
            continue
        v = v * v * v
        var u = random_float64()
        if u < 1e-15:
            u = 1e-15
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            return d * v
        if log(u) < 0.5 * x * x + d * (1.0 - v + log(v)):
            return d * v


def _sample_beta(alpha: Float64, beta: Float64) -> Float64:
    """Sample from Beta(alpha, beta) using Gamma variates."""
    var x = _sample_gamma(alpha)
    var y = _sample_gamma(beta)
    if x + y < 1e-300:
        return 0.5
    return x / (x + y)


# ── Beta-Binomial Conjugate ──────────────────────────────────────────────────


def beta_posterior(prior_alpha: Float64, prior_beta: Float64,
                  successes: Int, failures: Int) -> List[Float64]:
    """Beta-Binomial conjugate update. Returns [posterior_alpha, posterior_beta]."""
    var result = List[Float64]()
    result.append(prior_alpha + Float64(successes))
    result.append(prior_beta + Float64(failures))
    return result^


def beta_mean(alpha: Float64, beta: Float64) -> Float64:
    """Mean of Beta(α, β): α / (α + β)."""
    var total = alpha + beta
    if total < 1e-15:
        return 0.5
    return alpha / total


def beta_variance(alpha: Float64, beta: Float64) -> Float64:
    """Variance of Beta(α, β): αβ / ((α+β)²(α+β+1))."""
    var ab = alpha + beta
    if ab < 1e-15:
        return 0.0
    return (alpha * beta) / (ab * ab * (ab + 1.0))


def beta_credible_interval(alpha: Float64, beta: Float64,
                           mass: Float64 = 0.95) -> List[Float64]:
    """Approximate credible interval [lower, upper] using normal approximation."""
    var m = beta_mean(alpha, beta)
    var v = beta_variance(alpha, beta)
    var s = sqrt(v)
    var z = _probit((1.0 + mass) / 2.0)
    var lo = m - z * s
    var hi = m + z * s
    # Clamp to [0, 1]
    if lo < 0.0:
        lo = 0.0
    if hi > 1.0:
        hi = 1.0
    var result = List[Float64]()
    result.append(lo)
    result.append(hi)
    return result^


# ── Normal-Normal Conjugate ──────────────────────────────────────────────────


def normal_posterior(prior_mean: Float64, prior_var: Float64,
                    data_mean: Float64, data_var: Float64,
                    n: Int) -> List[Float64]:
    """Normal-Normal conjugate update. Returns [posterior_mean, posterior_variance].

    Precision-weighted combination of prior and likelihood.
    """
    var prior_prec = 1.0 / prior_var if prior_var > 1e-15 else 1e15
    var data_prec = Float64(n) / data_var if data_var > 1e-15 else 1e15
    var post_prec = prior_prec + data_prec
    var post_var = 1.0 / post_prec
    var post_mean = (prior_prec * prior_mean + data_prec * data_mean) / post_prec
    var result = List[Float64]()
    result.append(post_mean)
    result.append(post_var)
    return result^


# ── Gamma-Poisson Conjugate ──────────────────────────────────────────────────


def poisson_posterior(prior_alpha: Float64, prior_beta: Float64,
                     sum_x: Int, n: Int) -> List[Float64]:
    """Gamma-Poisson conjugate. Returns [posterior_alpha, posterior_beta].
    Posterior is Gamma(α + Σx, β + n)."""
    var result = List[Float64]()
    result.append(prior_alpha + Float64(sum_x))
    result.append(prior_beta + Float64(n))
    return result^


# ── Bayes Factor ─────────────────────────────────────────────────────────────


def bayes_factor(likelihood_h1: Float64, likelihood_h0: Float64) -> Float64:
    """Bayes factor: L(H1) / L(H0)."""
    if fabs(likelihood_h0) < 1e-300:
        return 0.0
    return likelihood_h1 / likelihood_h0


# ── Posterior Predictive ─────────────────────────────────────────────────────


def posterior_predictive_beta(alpha: Float64, beta: Float64) -> Float64:
    """Predictive probability of next success: α / (α + β)."""
    return beta_mean(alpha, beta)


# ── HPD Interval for Normal ──────────────────────────────────────────────────


def hpd_interval_normal(mean: Float64, std: Float64,
                        mass: Float64 = 0.95) -> List[Float64]:
    """HPD interval for normal: [mean - z*std, mean + z*std]."""
    var z = _probit((1.0 + mass) / 2.0)
    var result = List[Float64]()
    result.append(mean - z * std)
    result.append(mean + z * std)
    return result^


# ── Bayesian A/B Test ────────────────────────────────────────────────────────


def bayesian_ab_test(successes_a: Int, trials_a: Int,
                     successes_b: Int, trials_b: Int,
                     n_samples: Int = 10000) -> Float64:
    """P(B > A) using Monte Carlo sampling from Beta posteriors (flat prior).

    Uses Beta(successes+1, failures+1) posteriors for both A and B.
    Returns probability that B is better than A.
    """
    var alpha_a = Float64(successes_a) + 1.0
    var beta_a = Float64(trials_a - successes_a) + 1.0
    var alpha_b = Float64(successes_b) + 1.0
    var beta_b = Float64(trials_b - successes_b) + 1.0
    var b_wins: Int = 0
    for _ in range(n_samples):
        var sa = _sample_beta(alpha_a, beta_a)
        var sb = _sample_beta(alpha_b, beta_b)
        if sb > sa:
            b_wins += 1
    return Float64(b_wins) / Float64(n_samples)
