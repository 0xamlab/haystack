"""
lora_adapters.mojo — LoRA, QLoRA, and adapter fine-tuning math.
Zero Python imports.

Public API:
  lora_forward                   — LoRA low-rank forward pass
  lora_merge_weight              — merge LoRA into base weight
  qlora_dequant_forward          — QLoRA: dequant + LoRA forward
  lora_gradient_a                — gradient w.r.t. LoRA A matrix
  lora_gradient_b                — gradient w.r.t. LoRA B matrix
  adapter_scaling_factor         — LoRA α/r scaling
  prefix_tuning_key_aug          — prefix tuning key augmentation
  prompt_tuning_embed            — soft prompt embedding contribution
  dora_magnitude_scale           — DoRA direction + magnitude decomp
  adapter_param_efficiency       — trainable parameter ratio
"""
from std.math import sqrt, log, exp


fn lora_forward(
    x: Float64, a_row: Float64, b_col: Float64,
    scaling: Float64
) -> Float64:
    """LoRA low-rank forward pass: Δy = (x A B) × scale.

    Full: y = W₀x + BAx × (α/r)

    This computes one term of the BAx product.

    Args:
        x: Input activation element.
        a_row: LoRA A matrix element (d_model × r).
        b_col: LoRA B matrix element (r × d_out).
        scaling: α/r scaling factor.

    Returns:
        LoRA output contribution.
    """
    return x * a_row * b_col * scaling


fn lora_merge_weight(
    base_weight: Float64, lora_a: Float64,
    lora_b: Float64, scaling: Float64
) -> Float64:
    """Merge LoRA adapters into base weight for deployment.

    W_merged = W₀ + B × A × (α/r)

    Args:
        base_weight: Original pre-trained weight element.
        lora_a: LoRA A element.
        lora_b: LoRA B element.
        scaling: α/r scaling.

    Returns:
        Merged weight element.
    """
    return base_weight + lora_b * lora_a * scaling


fn qlora_dequant_forward(
    quantized_weight: Float64, quant_scale: Float64, zero_point: Float64,
    lora_delta: Float64
) -> Float64:
    """QLoRA: dequantize 4-bit weight + apply LoRA delta.

    y = (q - zp) × scale + LoRA_delta

    Args:
        quantized_weight: INT4 quantized weight value.
        quant_scale: Quantization scale.
        zero_point: Zero-point offset.
        lora_delta: LoRA low-rank update.

    Returns:
        Effective weight for forward pass.
    """
    var dequant = (quantized_weight - zero_point) * quant_scale
    return dequant + lora_delta


fn lora_gradient_a(
    upstream_grad: Float64, b_element: Float64,
    x_element: Float64, scaling: Float64
) -> Float64:
    """Gradient w.r.t. LoRA A matrix: ∂L/∂A = Bᵀ × ∂L/∂Y × xᵀ.

    Args:
        upstream_grad: Upstream gradient ∂L/∂Y element.
        b_element: LoRA B matrix element.
        x_element: Input x element.
        scaling: α/r scaling factor.

    Returns:
        Gradient contribution for A element.
    """
    return upstream_grad * b_element * x_element * scaling


fn lora_gradient_b(
    upstream_grad: Float64, ax_element: Float64, scaling: Float64
) -> Float64:
    """Gradient w.r.t. LoRA B matrix: ∂L/∂B = ∂L/∂Y × (Ax)ᵀ.

    Args:
        upstream_grad: Upstream gradient element.
        ax_element: A×x intermediate element.
        scaling: α/r scaling factor.

    Returns:
        Gradient contribution for B element.
    """
    return upstream_grad * ax_element * scaling


fn adapter_scaling_factor(alpha: Float64, rank: Float64) -> Float64:
    """LoRA scaling factor: α/r.

    Args:
        alpha: LoRA alpha hyperparameter.
        rank: LoRA rank r.

    Returns:
        Scaling factor α/r.
    """
    if rank <= 0.0:
        return alpha
    return alpha / rank


fn prefix_tuning_key_aug(
    original_key: Float64, prefix_key: Float64,
    prefix_len: Float64, seq_len: Float64
) -> Float64:
    """Prefix tuning: augment key sequence with trainable prefix.

    Concatenates prefix keys to actual keys; attention sees both.

    Args:
        original_key: Actual sequence key element.
        prefix_key: Trainable prefix key element.
        prefix_len: Number of prefix tokens.
        seq_len: Original sequence length.

    Returns:
        Augmented key contribution.
    """
    return original_key + prefix_key * prefix_len / (seq_len + prefix_len)


fn prompt_tuning_embed(
    token_embed: Float64, soft_prompt_embed: Float64,
    position: Float64, n_soft_tokens: Float64
) -> Float64:
    """Soft prompt embedding: inject trainable tokens at the start.

    For positions < n_soft_tokens, use soft prompt embedding.

    Args:
        token_embed: Original token embedding element.
        soft_prompt_embed: Trainable soft prompt element.
        position: Token position.
        n_soft_tokens: Number of soft prompt tokens.

    Returns:
        Effective embedding (soft prompt or original).
    """
    if position < n_soft_tokens:
        return soft_prompt_embed
    return token_embed


fn dora_magnitude_scale(
    weight_norm: Float64, lora_delta_norm: Float64,
    magnitude_param: Float64
) -> Float64:
    """DoRA (Weight-Decomposed LoRA) magnitude scaling.

    W = m × (W₀ + ΔW) / ||W₀ + ΔW||

    Returns the scale to apply: m / ||W₀ + ΔW||

    Args:
        weight_norm: ||W₀ + ΔW|| (norm of adapted weight direction).
        lora_delta_norm: ||ΔW|| for reference.
        magnitude_param: Trainable magnitude m.

    Returns:
        DoRA scale factor.
    """
    if weight_norm <= 0.0:
        return magnitude_param
    return magnitude_param / weight_norm


fn adapter_param_efficiency(
    lora_params: Float64, total_params: Float64
) -> Float64:
    """Fraction of parameters that are trainable (adapter efficiency).

    Args:
        lora_params: Trainable adapter parameter count.
        total_params: Total model parameter count.

    Returns:
        Trainable ratio (lower = more parameter-efficient).
    """
    if total_params <= 0.0:
        return 1.0
    return lora_params / total_params
