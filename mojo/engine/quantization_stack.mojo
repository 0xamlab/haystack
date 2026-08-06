"""
quantization_stack.mojo — Full quantization stack: FP16/BF16/INT8/INT4, calibration.
Zero Python imports.

Public API:
  bf16_to_fp32_round             — BF16 round-trip precision loss
  fp16_overflow_check            — detect FP16 overflow
  absmax_calibration_scale       — absmax calibration for INT8
  percentile_calibration_scale   — percentile-based calibration
  smooth_quant_scale             — SmoothQuant per-channel scale
  gptq_hessian_update            — GPTQ Hessian diagonal update
  awq_activation_scale           — AWQ activation-weighted scale
  bnb_double_quant_scale         — bitsandbytes double quantization
  kv_cache_int8_scale            — dynamic KV cache INT8 scale
  quant_aware_straight_through   — STE gradient for quantization
"""
from std.math import sqrt, log, exp


def bf16_to_fp32_round(x: Float64) -> Float64:
    """BF16 precision: truncate FP32 mantissa to 7 bits.

    BF16 keeps the upper 16 bits of FP32; loses 16 mantissa bits.
    Simulated by quantising to BF16 grid.

    Args:
        x: FP32 value.

    Returns:
        BF16-representable FP32 value (precision loss simulated).
    """
    # BF16 has ~2 decimal digits of precision; quantise to that grid
    if x == 0.0:
        return 0.0
    var scale = exp(Float64(Int64(log(x if x > 0.0 else -x) / 0.6931471805)) * 0.6931471805)
    var quantised = Float64(Int64(x / scale * 128.0 + 0.5)) / 128.0
    return quantised * scale


def fp16_overflow_check(x: Float64) -> Float64:
    """Check if value overflows FP16 range (max ≈ 65504).

    Returns 1.0 if overflow, 0.0 if representable.

    Args:
        x: Value to check.

    Returns:
        1.0 if |x| > 65504, else 0.0.
    """
    var abs_x = x if x >= 0.0 else -x
    if abs_x > 65504.0:
        return 1.0
    return 0.0


def absmax_calibration_scale(
    abs_max: Float64, n_bits: Float64
) -> Float64:
    """Absmax calibration: scale = abs_max / (2^(n_bits-1) - 1).

    Args:
        abs_max: Maximum absolute value in calibration dataset.
        n_bits: Quantization bits (8 for INT8, 4 for INT4).

    Returns:
        Quantization scale factor.
    """
    var qmax = exp((n_bits - 1.0) * 0.6931471805599453) - 1.0
    if qmax <= 0.0:
        return 1.0
    return abs_max / qmax


def percentile_calibration_scale(
    percentile_value: Float64, n_bits: Float64
) -> Float64:
    """Percentile calibration: clip outliers before scaling.

    Avoids absmax inflation from outliers (99th/99.9th percentile).

    Args:
        percentile_value: e.g. 99th percentile of absolute values.
        n_bits: Quantization bits.

    Returns:
        Scale with outlier-robust clipping.
    """
    var qmax = exp((n_bits - 1.0) * 0.6931471805599453) - 1.0
    if qmax <= 0.0:
        return 1.0
    return percentile_value / qmax


def smooth_quant_scale(
    activation_max: Float64, weight_max: Float64, alpha: Float64
) -> Float64:
    """SmoothQuant per-channel migration scale.

    s = max(X)^α / max(W)^(1-α)

    Migrates quantization difficulty from activations to weights.

    Args:
        activation_max: Per-channel activation maximum.
        weight_max: Corresponding weight maximum.
        alpha: Migration strength (0.5 typical).

    Returns:
        Channel smoothing scale s.
    """
    if weight_max <= 0.0:
        return 1.0
    return exp(alpha * log(activation_max + 1e-8)) / exp((1.0 - alpha) * log(weight_max + 1e-8))


def gptq_hessian_update(
    h_diag: Float64, activation: Float64, n_samples: Float64
) -> Float64:
    """GPTQ Hessian diagonal update: H += 2/n × x × xᵀ (diagonal).

    Args:
        h_diag: Current Hessian diagonal element.
        activation: Input activation for this column.
        n_samples: Number of calibration samples.

    Returns:
        Updated Hessian diagonal.
    """
    if n_samples <= 0.0:
        return h_diag
    return h_diag + 2.0 * activation * activation / n_samples


def awq_activation_scale(
    activation_abs_mean: Float64, weight_abs_mean: Float64
) -> Float64:
    """AWQ (Activation-aware Weight Quantization) per-channel scale.

    Scales weights to compensate for high-activation channels.

    s = sqrt(mean|X| / mean|W|)

    Args:
        activation_abs_mean: Mean absolute activation for channel.
        weight_abs_mean: Mean absolute weight for channel.

    Returns:
        AWQ scaling factor.
    """
    if weight_abs_mean <= 0.0:
        return 1.0
    return sqrt(activation_abs_mean / weight_abs_mean)


def bnb_double_quant_scale(
    block_scale: Float64, super_block_scale: Float64
) -> Float64:
    """bitsandbytes double quantization: quantize the scale factors.

    Saves ~0.5 bits/weight by quantizing quantization scales.

    scale_final = block_scale × super_block_scale

    Args:
        block_scale: Per-block INT8 scale.
        super_block_scale: Scale of the block scale (double quant).

    Returns:
        Effective dequantization scale.
    """
    return block_scale * super_block_scale


def kv_cache_int8_scale(
    kv_tensor_max: Float64
) -> Float64:
    """Dynamic per-tensor INT8 scale for KV cache quantization.

    scale = max(|KV|) / 127

    Args:
        kv_tensor_max: Maximum absolute value in KV tensor.

    Returns:
        INT8 quantization scale.
    """
    if kv_tensor_max <= 0.0:
        return 1.0
    return kv_tensor_max / 127.0


def quant_aware_straight_through(
    upstream_grad: Float64, x: Float64,
    x_min: Float64, x_max: Float64
) -> Float64:
    """Straight-through estimator (STE) for quantization-aware training.

    Passes gradient through if x is within clipping range, else 0.

    Args:
        upstream_grad: Gradient from above.
        x: Original (pre-quantized) value.
        x_min: Quantizer lower clip bound.
        x_max: Quantizer upper clip bound.

    Returns:
        STE gradient.
    """
    if x >= x_min and x <= x_max:
        return upstream_grad
    return 0.0
