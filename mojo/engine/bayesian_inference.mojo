"""
bayesian_inference.mojo — Probabilistic / Bayesian inference primitives.
Zero Python imports.

Public API:
  bayes_update_log               — log-space posterior update
  prior_predictive               — prior predictive density
  variational_elbo_term          — ELBO KL + reconstruction term
  mean_field_update_mean         — mean-field Gaussian mean update
  mean_field_update_var          — mean-field Gaussian variance update
  laplace_approx_log_posterior   — Laplace approximation log-posterior
  expected_information_gain      — EIG for Bayesian experimental design
  credible_interval_half_width   — Gaussian credible interval
  kl_gaussians                   — KL divergence between two Gaussians
  jeffreys_prior_gaussian        — Jeffreys prior for Gaussian σ
"""
from std.math import sqrt, log, exp


def bayes_update_log(
    log_prior: Float64, log_likelihood: Float64
) -> Float64:
    """Log-space posterior update: log P(θ|x) ∝ log P(x|θ) + log P(θ).

    Args:
        log_prior: Log prior probability log P(θ).
        log_likelihood: Log likelihood log P(x|θ).

    Returns:
        Unnormalised log posterior.
    """
    return log_prior + log_likelihood


def prior_predictive(
    likelihood: Float64, prior: Float64
) -> Float64:
    """Prior predictive density contribution: P(x) = Σ P(x|θ) P(θ).

    One term in the marginal likelihood sum.

    Args:
        likelihood: P(x|θ) at this θ.
        prior: P(θ) at this θ.

    Returns:
        Contribution to marginal likelihood.
    """
    return likelihood * prior


def variational_elbo_term(
    log_likelihood: Float64, kl_divergence: Float64
) -> Float64:
    """ELBO (Evidence Lower Bound): E_q[log p(x|z)] - KL(q||p).

    Args:
        log_likelihood: Reconstruction term E_q[log p(x|z)].
        kl_divergence: KL(q(z)||p(z)) regularisation term.

    Returns:
        ELBO (maximise this).
    """
    return log_likelihood - kl_divergence


def mean_field_update_mean(
    natural_grad_sum: Float64, precision: Float64
) -> Float64:
    """Mean-field Gaussian mean update: μ = Σ natural_grads / precision.

    Args:
        natural_grad_sum: Sum of natural gradient contributions.
        precision: Precision (1/σ²) of the variational factor.

    Returns:
        Updated mean.
    """
    if precision <= 0.0:
        return 0.0
    return natural_grad_sum / precision


def mean_field_update_var(
    expected_hessian: Float64
) -> Float64:
    """Mean-field Gaussian variance update: σ² = 1 / E[-∂²log p/∂θ²].

    Args:
        expected_hessian: Expected negative Hessian (precision).

    Returns:
        Updated variance.
    """
    if expected_hessian <= 0.0:
        return 1e6
    return 1.0 / expected_hessian


def laplace_approx_log_posterior(
    log_post_mode: Float64, hessian_at_mode: Float64,
    theta: Float64, theta_mode: Float64
) -> Float64:
    """Laplace approximation: Gaussian centred at MAP estimate.

    log q(θ) ≈ log p(θ_MAP|x) - 0.5 × H × (θ - θ_MAP)²

    Args:
        log_post_mode: Log posterior at MAP.
        hessian_at_mode: Negative Hessian (precision) at MAP.
        theta: Parameter value to evaluate.
        theta_mode: MAP estimate.

    Returns:
        Laplace log posterior.
    """
    var diff = theta - theta_mode
    return log_post_mode - 0.5 * hessian_at_mode * diff * diff


def expected_information_gain(
    posterior_entropy: Float64, prior_entropy: Float64
) -> Float64:
    """Expected Information Gain: EIG = H[p(θ)] - E[H[p(θ|x)]].

    Args:
        posterior_entropy: Expected posterior entropy E[H[p(θ|x)]].
        prior_entropy: Prior entropy H[p(θ)].

    Returns:
        EIG (bits of information from experiment).
    """
    return prior_entropy - posterior_entropy


def credible_interval_half_width(
    std: Float64, z_score: Float64
) -> Float64:
    """Gaussian credible interval half-width: z × σ.

    95% CI → z ≈ 1.96, 99% → z ≈ 2.576.

    Args:
        std: Posterior standard deviation.
        z_score: Standard normal quantile.

    Returns:
        Half-width of the credible interval.
    """
    return z_score * std


def kl_gaussians(
    mu1: Float64, sigma1: Float64, mu2: Float64, sigma2: Float64
) -> Float64:
    """KL divergence KL(N(μ1,σ1²) || N(μ2,σ2²)).

    KL = log(σ2/σ1) + (σ1² + (μ1-μ2)²) / (2σ2²) - 0.5

    Args:
        mu1: Mean of q distribution.
        sigma1: Std of q distribution.
        mu2: Mean of p distribution.
        sigma2: Std of p distribution.

    Returns:
        KL divergence (≥ 0).
    """
    if sigma1 <= 0.0 or sigma2 <= 0.0:
        return 0.0
    var mu_diff = mu1 - mu2
    return log(sigma2 / sigma1) + (sigma1 * sigma1 + mu_diff * mu_diff) / (2.0 * sigma2 * sigma2) - 0.5


def jeffreys_prior_gaussian(sigma: Float64) -> Float64:
    """Jeffreys prior for Gaussian σ: p(σ) ∝ 1/σ.

    Args:
        sigma: Standard deviation parameter.

    Returns:
        Jeffreys prior value.
    """
    if sigma <= 0.0:
        return 0.0
    return 1.0 / sigma
