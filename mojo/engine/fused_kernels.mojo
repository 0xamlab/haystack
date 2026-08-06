"""
fused_kernels.mojo — Fused kernel math: attention, layernorm, matmul+bias+activation.
Zero Python imports.

Public API:
  fused_attention_score          — QK^T/√d + mask in one step
  fused_softmax_mask             — stable softmax with causal mask fused
  fused_layernorm_element        — layernorm + scale + shift fused
  fused_matmul_bias_relu         — linear + bias + ReLU fused
  fused_matmul_bias_gelu         — linear + bias + GELU fused
  fused_rope_attention           — RoPE rotation fused into attention
  fused_add_norm                 — residual + layernorm fused
  fused_scale_shift              — affine transform fused
  fused_dropout_residual         — dropout + residual add fused
  kernel_fusion_savings          — estimated memory traffic savings from fusion
"""
from std.math import sqrt, log, exp


def fused_attention_score(
    q: Float64, k: Float64, head_dim: Float64,
    mask_value: Float64, is_masked: Float64
) -> Float64:
    """Fused QK attention score with scaling and masking in one pass.

    score = q × k / √d + mask

    Fusing avoids two separate memory round-trips for scale and mask.

    Args:
        q: Query element.
        k: Key element.
        head_dim: Head dimension d (for 1/√d scaling).
        mask_value: Mask additive value (-1e9 for causal).
        is_masked: 1.0 if this position is masked, 0.0 otherwise.

    Returns:
        Scaled and masked attention logit.
    """
    if head_dim <= 0.0:
        return 0.0
    var score = q * k / sqrt(head_dim)
    if is_masked > 0.5:
        return score + mask_value
    return score


def fused_softmax_mask(
    logit: Float64, logit_max: Float64,
    sum_exp: Float64, is_valid: Float64
) -> Float64:
    """Fused numerically stable softmax with validity masking.

    Combines max subtraction, exp, and normalisation in one pass.

    Args:
        logit: Raw attention logit.
        logit_max: Row-wise maximum (for numerical stability).
        sum_exp: Σ exp(logit - max) over valid positions.
        is_valid: 1.0 if position is valid, 0.0 if masked.

    Returns:
        Softmax probability (0 if masked).
    """
    if is_valid < 0.5 or sum_exp <= 0.0:
        return 0.0
    return exp(logit - logit_max) / sum_exp


def fused_layernorm_element(
    x: Float64, mean: Float64, inv_std: Float64,
    gamma: Float64, beta: Float64
) -> Float64:
    """Fused LayerNorm: normalise + scale + shift in one expression.

    y = γ × (x - μ) × (1/σ) + β

    Fused avoids storing the intermediate normalised value.

    Args:
        x: Input element.
        mean: Layer mean μ.
        inv_std: Inverse standard deviation 1/σ.
        gamma: Scale parameter γ.
        beta: Shift parameter β.

    Returns:
        Normalised and affine-transformed element.
    """
    return gamma * (x - mean) * inv_std + beta


def fused_matmul_bias_relu(
    dot_product: Float64, bias: Float64
) -> Float64:
    """Fused linear layer + bias + ReLU.

    y = max(0, dot(x, W) + b)

    Args:
        dot_product: Pre-computed x·W element.
        bias: Bias term b.

    Returns:
        ReLU-activated output.
    """
    var pre_act = dot_product + bias
    if pre_act > 0.0:
        return pre_act
    return 0.0


def fused_matmul_bias_gelu(
    dot_product: Float64, bias: Float64
) -> Float64:
    """Fused linear + bias + GELU activation.

    y = GELU(dot(x, W) + b)

    Args:
        dot_product: Pre-computed x·W element.
        bias: Bias term b.

    Returns:
        GELU-activated output.
    """
    var x = dot_product + bias
    var inner = 0.7978845608 * (x + 0.044715 * x * x * x)
    var e2 = exp(2.0 * inner)
    var tanh_val = (e2 - 1.0) / (e2 + 1.0)
    return 0.5 * x * (1.0 + tanh_val)


def fused_rope_attention(
    q: Float64, k: Float64, cos_val: Float64, sin_val: Float64,
    q_pair: Float64, k_pair: Float64, head_dim: Float64
) -> Float64:
    """RoPE rotation fused into QK attention score computation.

    Rotates q and k then computes scaled dot product in one pass.

    Args:
        q: Query element (even dim).
        k: Key element (even dim).
        cos_val: cos(θ) for this position-dimension pair.
        sin_val: sin(θ) for this position-dimension pair.
        q_pair: Query paired (odd) dimension element.
        k_pair: Key paired dimension element.
        head_dim: Head dimension for scaling.

    Returns:
        Rotated and scaled attention score contribution.
    """
    if head_dim <= 0.0:
        return 0.0
    var q_rot = q * cos_val - q_pair * sin_val
    var k_rot = k * cos_val - k_pair * sin_val
    return q_rot * k_rot / sqrt(head_dim)


def fused_add_norm(
    x: Float64, sublayer: Float64,
    mean: Float64, inv_std: Float64,
    gamma: Float64, beta: Float64
) -> Float64:
    """Fused residual add + LayerNorm (post-norm pattern).

    y = LayerNorm(x + sublayer)

    Args:
        x: Input to sublayer (residual bypass).
        sublayer: Sublayer output.
        mean: Mean of (x + sublayer) across the layer dimension.
        inv_std: Inverse std of (x + sublayer).
        gamma: LayerNorm scale.
        beta: LayerNorm shift.

    Returns:
        Post-norm residual element.
    """
    var residual = x + sublayer
    return gamma * (residual - mean) * inv_std + beta


def fused_scale_shift(
    x: Float64, scale: Float64, shift: Float64
) -> Float64:
    """Fused affine transform: y = scale × x + shift.

    Used for conditional normalisation (AdaLN, FiLM).

    Args:
        x: Input.
        scale: Multiplicative scale.
        shift: Additive shift.

    Returns:
        Affine-transformed value.
    """
    return scale * x + shift


def fused_dropout_residual(
    x: Float64, sublayer: Float64,
    keep_prob: Float64, is_kept: Float64
) -> Float64:
    """Fused dropout + residual add.

    y = x + (sublayer / keep_prob) × is_kept

    Args:
        x: Residual input.
        sublayer: Sublayer output before dropout.
        keep_prob: Keep probability (1 - dropout_rate).
        is_kept: 1.0 if neuron kept, 0.0 if dropped.

    Returns:
        Residual with dropped sublayer applied.
    """
    if keep_prob <= 0.0 or is_kept < 0.5:
        return x
    return x + sublayer / keep_prob


def kernel_fusion_savings(
    n_fused_ops: Float64, bytes_per_intermediate: Float64,
    n_elements: Float64
) -> Float64:
    """Estimated HBM traffic savings from kernel fusion.

    Savings = n_fused_ops × bytes_per_intermediate × n_elements

    Fusing eliminates intermediate tensor reads/writes.

    Args:
        n_fused_ops: Number of operations fused together.
        bytes_per_intermediate: Bytes per intermediate tensor element.
        n_elements: Number of tensor elements.

    Returns:
        Bytes of memory traffic eliminated.
    """
    if n_fused_ops <= 1.0:
        return 0.0
    return (n_fused_ops - 1.0) * bytes_per_intermediate * n_elements
