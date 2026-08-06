"""
normalization_layers.mojo — Neural network normalization calculations. Zero Python imports.

Public API:
  layer_norm                    — LN: (x - mean) / std × gamma + beta
  rms_norm                      — RMSNorm (no mean subtraction)
  batch_norm_inference          — BN at inference time
  group_norm_scale              — per-group normalisation factor
  instance_norm                 — per-sample per-channel norm
  weight_norm_magnitude         — weight reparameterisation
  spectral_norm_estimate        — power iteration approximation
  adaptive_layer_norm           — AdaLN from diffusion models
  deep_norm_alpha               — DeepNorm residual scaling
  pre_norm_residual             — pre-LN transformer residual
"""
from std.math import sqrt, exp, log


def layer_norm(
    x: Float64, mean: Float64, variance: Float64,
    gamma: Float64, beta: Float64, eps: Float64
) -> Float64:
    """Layer normalisation: y = (x - μ) / sqrt(σ² + ε) × γ + β.

    Args:
        x: Input activation.
        mean: Mean of the layer activations.
        variance: Variance of the layer activations.
        gamma: Learnable scale parameter.
        beta: Learnable shift parameter.
        eps: Numerical stability epsilon (1e-5 typical).

    Returns:
        Normalised activation.
    """
    return (x - mean) / sqrt(variance + eps) * gamma + beta


def rms_norm(
    x: Float64, rms: Float64, gamma: Float64, eps: Float64
) -> Float64:
    """RMSNorm (Zhang & Sennrich 2019): y = x / RMS(x) × γ.

    RMS = sqrt(mean(x²))

    Args:
        x: Input activation.
        rms: Root mean square of input vector.
        gamma: Learnable scale.
        eps: Stability epsilon.

    Returns:
        RMS-normalised activation.
    """
    return x / sqrt(rms * rms + eps) * gamma


def batch_norm_inference(
    x: Float64, running_mean: Float64, running_var: Float64,
    gamma: Float64, beta: Float64, eps: Float64
) -> Float64:
    """Batch normalisation at inference (frozen statistics).

    y = (x - μ_running) / sqrt(σ²_running + ε) × γ + β

    Args:
        x: Input activation.
        running_mean: Exponential moving average of batch means.
        running_var: Exponential moving average of batch variances.
        gamma: Learnable scale.
        beta: Learnable shift.
        eps: Stability epsilon.

    Returns:
        Batch-normalised activation.
    """
    return (x - running_mean) / sqrt(running_var + eps) * gamma + beta


def group_norm_scale(
    x: Float64, group_mean: Float64, group_var: Float64,
    gamma: Float64, beta: Float64, eps: Float64
) -> Float64:
    """Group normalisation per-group scaling.

    Args:
        x: Input activation.
        group_mean: Mean within the normalisation group.
        group_var: Variance within the group.
        gamma: Scale parameter.
        beta: Shift parameter.
        eps: Stability epsilon.

    Returns:
        Group-normalised activation.
    """
    return (x - group_mean) / sqrt(group_var + eps) * gamma + beta


def instance_norm(
    x: Float64, instance_mean: Float64, instance_var: Float64,
    gamma: Float64, beta: Float64, eps: Float64
) -> Float64:
    """Instance normalisation (per-sample, per-channel).

    Args:
        x: Input value.
        instance_mean: Per-instance channel mean.
        instance_var: Per-instance channel variance.
        gamma: Scale.
        beta: Shift.
        eps: Epsilon.

    Returns:
        Instance-normalised value.
    """
    return (x - instance_mean) / sqrt(instance_var + eps) * gamma + beta


def weight_norm_magnitude(
    weight_vector_norm: Float64, g_param: Float64
) -> Float64:
    """Weight normalisation magnitude: w = g × v / ||v||.

    Args:
        weight_vector_norm: L2 norm of weight direction vector.
        g_param: Learnable magnitude scalar g.

    Returns:
        Effective weight magnitude.
    """
    if weight_vector_norm <= 0.0:
        return 0.0
    return g_param / weight_vector_norm


def spectral_norm_estimate(
    sigma_prev: Float64, u_dot_w_v: Float64
) -> Float64:
    """One power-iteration step for spectral norm estimation.

    σ_new ≈ u^T W v  (after normalisation)

    Args:
        sigma_prev: Previous spectral norm estimate.
        u_dot_w_v: u^T × W × v product.

    Returns:
        Updated spectral norm estimate.
    """
    return u_dot_w_v


def adaptive_layer_norm(
    x: Float64, mean: Float64, variance: Float64,
    gamma_cond: Float64, beta_cond: Float64, eps: Float64
) -> Float64:
    """Adaptive Layer Norm (AdaLN) from diffusion transformers.

    y = LN(x) × (1 + γ_cond) + β_cond

    Args:
        x: Input activation.
        mean: Layer mean.
        variance: Layer variance.
        gamma_cond: Conditioning-derived scale (shift from 1).
        beta_cond: Conditioning-derived shift.
        eps: Stability epsilon.

    Returns:
        AdaLN output.
    """
    var ln = (x - mean) / sqrt(variance + eps)
    return ln * (1.0 + gamma_cond) + beta_cond


def deep_norm_alpha(n_layers: Float64) -> Float64:
    """DeepNorm residual scaling factor alpha.

    alpha = (2N)^(1/4)  for encoder, (8N)^(1/4) for decoder

    Args:
        n_layers: Number of transformer layers N.

    Returns:
        Alpha scaling for residual connection.
    """
    return exp(log(2.0 * n_layers) / 4.0)


def pre_norm_residual(
    x: Float64, sublayer_out: Float64
) -> Float64:
    """Pre-LN residual connection: output = x + sublayer(LN(x)).

    Args:
        x: Residual (unnormalised input).
        sublayer_out: Output of sublayer applied to LN(x).

    Returns:
        Residual connection output.
    """
    return x + sublayer_out
