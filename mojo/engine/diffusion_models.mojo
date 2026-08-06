"""
diffusion_models.mojo — Diffusion model noise schedules and denoising calculations.
Zero Python imports.

Public API:
  linear_beta_schedule          — linear noise schedule
  cosine_beta_schedule          — cosine noise schedule (Nichol & Dhariwal)
  alpha_from_beta               — cumulative product of (1-beta)
  forward_diffusion_sample      — q(x_t | x_0)
  ddpm_reverse_mean             — posterior mean for DDPM
  ddpm_posterior_variance       — posterior variance
  ddim_step                     — DDIM deterministic step
  snr                           — signal-to-noise ratio at timestep
  noise_prediction_to_x0        — convert epsilon prediction to x0
  edm_preconditioning           — EDM sigma/c_skip/c_out scaling
"""
from std.math import sqrt, log, exp, cos


def linear_beta_schedule(
    t: Float64, t_max: Float64,
    beta_start: Float64, beta_end: Float64
) -> Float64:
    """Linear beta (noise) schedule.

    beta(t) = beta_start + (beta_end - beta_start) × t/T

    Args:
        t: Current timestep.
        t_max: Maximum timestep T (e.g. 1000).
        beta_start: Starting noise level (0.0001 typical).
        beta_end: Ending noise level (0.02 typical).

    Returns:
        Beta at timestep t.
    """
    return beta_start + (beta_end - beta_start) * t / t_max


def cosine_beta_schedule(
    t: Float64, t_max: Float64, s: Float64
) -> Float64:
    """Cosine beta schedule (Improved DDPM, Nichol & Dhariwal 2021).

    alpha_bar(t) = cos((t/T + s)/(1+s) × π/2)²

    Args:
        t: Current timestep.
        t_max: Total timesteps.
        s: Offset parameter (0.008 default).

    Returns:
        Cumulative alpha_bar at timestep t.
    """
    var pi = 3.141592653589793
    var f_t = cos((t / t_max + s) / (1.0 + s) * pi / 2.0)
    var f_0 = cos((s / (1.0 + s)) * pi / 2.0)
    var alpha_bar = (f_t * f_t) / (f_0 * f_0)
    if alpha_bar < 0.0:
        return 0.0
    if alpha_bar > 1.0:
        return 1.0
    return alpha_bar


def alpha_from_beta(beta: Float64, prev_alpha_bar: Float64) -> Float64:
    """Cumulative alpha: ᾱ_t = ᾱ_{t-1} × (1 - β_t).

    Args:
        beta: Current timestep beta.
        prev_alpha_bar: Cumulative alpha from previous step.

    Returns:
        Updated cumulative alpha_bar.
    """
    return prev_alpha_bar * (1.0 - beta)


def forward_diffusion_sample(
    x0: Float64, noise: Float64, alpha_bar: Float64
) -> Float64:
    """Forward diffusion: q(x_t | x_0) = sqrt(ᾱ_t)×x0 + sqrt(1-ᾱ_t)×ε.

    Args:
        x0: Clean data value.
        noise: Gaussian noise sample ε ~ N(0,1).
        alpha_bar: Cumulative noise level ᾱ_t.

    Returns:
        Noisy sample x_t.
    """
    return sqrt(alpha_bar) * x0 + sqrt(1.0 - alpha_bar) * noise


def ddpm_reverse_mean(
    x_t: Float64, predicted_noise: Float64,
    alpha_t: Float64, alpha_bar_t: Float64, beta_t: Float64
) -> Float64:
    """DDPM reverse process posterior mean.

    μ̃_t = 1/sqrt(α_t) × (x_t - β_t/sqrt(1-ᾱ_t) × ε_θ)

    Args:
        x_t: Noisy sample at timestep t.
        predicted_noise: Model noise prediction ε_θ.
        alpha_t: 1 - beta_t.
        alpha_bar_t: Cumulative alpha at t.
        beta_t: Noise schedule value.

    Returns:
        Posterior mean.
    """
    # sqrt(1 - ᾱ_t) is a denominator: zero at ᾱ_t = 1, NaN beyond it.
    if alpha_t <= 0.0 or alpha_bar_t >= 1.0:
        return x_t
    var coeff = beta_t / sqrt(1.0 - alpha_bar_t)
    return (1.0 / sqrt(alpha_t)) * (x_t - coeff * predicted_noise)


def ddpm_posterior_variance(
    beta_t: Float64, alpha_bar_t: Float64, alpha_bar_prev: Float64
) -> Float64:
    """DDPM posterior variance: β̃_t = (1-ᾱ_{t-1})/(1-ᾱ_t) × β_t.

    Args:
        beta_t: Current noise schedule value.
        alpha_bar_t: Cumulative alpha at t.
        alpha_bar_prev: Cumulative alpha at t-1.

    Returns:
        Posterior variance.
    """
    # (1 - ᾱ_t) is a denominator: zero at ᾱ_t = 1 (0/0 -> NaN).
    if alpha_bar_t <= 0.0 or alpha_bar_t >= 1.0:
        return beta_t
    return (1.0 - alpha_bar_prev) / (1.0 - alpha_bar_t) * beta_t


def ddim_step(
    x_t: Float64, predicted_noise: Float64,
    alpha_bar_t: Float64, alpha_bar_prev: Float64, eta: Float64
) -> Float64:
    """DDIM deterministic sampling step (Song et al. 2021).

    x_{t-1} = sqrt(ᾱ_{t-1}) × x0_pred + sqrt(1-ᾱ_{t-1}-σ²) × ε_θ

    Args:
        x_t: Current noisy sample.
        predicted_noise: Model noise prediction.
        alpha_bar_t: Current cumulative alpha.
        alpha_bar_prev: Previous cumulative alpha.
        eta: Stochasticity (0 = deterministic DDIM, 1 = DDPM).

    Returns:
        Denoised sample x_{t-1}.
    """
    # Both cumulative alphas appear in denominators/sqrts: outside (0, 1) the
    # step produces inf/NaN that cannot cross the result wire.
    if alpha_bar_t <= 0.0 or alpha_bar_t >= 1.0 or alpha_bar_prev <= 0.0 or alpha_bar_prev >= 1.0:
        return x_t
    var x0_pred = (x_t - sqrt(1.0 - alpha_bar_t) * predicted_noise) / sqrt(alpha_bar_t)
    var sigma = eta * sqrt((1.0 - alpha_bar_prev) / (1.0 - alpha_bar_t) * (1.0 - alpha_bar_t / alpha_bar_prev))
    var dir_xt = sqrt(1.0 - alpha_bar_prev - sigma * sigma) * predicted_noise
    return sqrt(alpha_bar_prev) * x0_pred + dir_xt


def snr(alpha_bar: Float64) -> Float64:
    """Signal-to-noise ratio at timestep: SNR = ᾱ / (1 - ᾱ).

    Args:
        alpha_bar: Cumulative alpha at timestep.

    Returns:
        SNR (high early in diffusion, ~0 at full noise).
    """
    var denom = 1.0 - alpha_bar
    if denom <= 0.0:
        return 1e9
    return alpha_bar / denom


def noise_prediction_to_x0(
    x_t: Float64, predicted_noise: Float64, alpha_bar: Float64
) -> Float64:
    """Convert epsilon prediction to x0 estimate.

    x0 = (x_t - sqrt(1-ᾱ) × ε) / sqrt(ᾱ)

    Args:
        x_t: Noisy input.
        predicted_noise: Predicted noise ε.
        alpha_bar: Cumulative alpha.

    Returns:
        Estimated clean x0.
    """
    if alpha_bar <= 0.0:
        return x_t
    return (x_t - sqrt(1.0 - alpha_bar) * predicted_noise) / sqrt(alpha_bar)


def edm_preconditioning(
    sigma: Float64, sigma_data: Float64
) -> Float64:
    """EDM c_skip skip connection scaling (Karras et al. 2022).

    c_skip = σ_data² / (σ² + σ_data²)

    Args:
        sigma: Current noise level.
        sigma_data: Data standard deviation (≈0.5 for normalised images).

    Returns:
        c_skip scaling factor.
    """
    return sigma_data * sigma_data / (sigma * sigma + sigma_data * sigma_data)
