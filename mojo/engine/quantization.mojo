"""
quantization.mojo — Neural network quantization math (INT8/INT4/FP16).
Zero Python imports.

Public API:
  quantize_symmetric             — symmetric INT8 quantization
  dequantize_symmetric           — INT8 → float reconstruction
  quantize_asymmetric            — asymmetric min/max quantization
  dequantize_asymmetric          — asymmetric dequantization
  quantization_error             — round-trip error
  scale_from_range               — compute scale factor
  zero_point_from_range          — compute zero point
  clamp_to_int8                  — clamp to [-128, 127]
  fp16_to_fp32_scale             — FP16 dynamic range scale
  int4_pack_error                — INT4 quantization error estimate
"""
from std.math import sqrt, log, exp


fn quantize_symmetric(x: Float64, scale: Float64) -> Float64:
    """Symmetric INT8 quantization: q = round(x / scale), clipped to [-127, 127].

    Args:
        x: Float value to quantize.
        scale: Quantization scale factor.

    Returns:
        Quantized integer value as Float64.
    """
    if scale <= 0.0:
        return 0.0
    var q = x / scale
    if q > 127.0:
        return 127.0
    if q < -127.0:
        return -127.0
    if q >= 0.0:
        return Float64(Int64(q + 0.5))
    return Float64(Int64(q - 0.5))


fn dequantize_symmetric(q: Float64, scale: Float64) -> Float64:
    """Dequantize symmetric INT8: x_hat = q × scale.

    Args:
        q: Quantized integer value.
        scale: Quantization scale factor.

    Returns:
        Reconstructed float value.
    """
    return q * scale


fn quantize_asymmetric(
    x: Float64, scale: Float64, zero_point: Float64
) -> Float64:
    """Asymmetric quantization: q = round(x/scale + zero_point), clipped to [0, 255].

    Args:
        x: Float value.
        scale: Scale factor.
        zero_point: Zero-point offset.

    Returns:
        Quantized UINT8 value.
    """
    if scale <= 0.0:
        return zero_point
    var q = x / scale + zero_point
    if q > 255.0:
        return 255.0
    if q < 0.0:
        return 0.0
    return Float64(Int64(q + 0.5))


fn dequantize_asymmetric(
    q: Float64, scale: Float64, zero_point: Float64
) -> Float64:
    """Asymmetric dequantization: x_hat = (q - zero_point) × scale.

    Args:
        q: Quantized value.
        scale: Scale factor.
        zero_point: Zero-point offset.

    Returns:
        Reconstructed float.
    """
    return (q - zero_point) * scale


fn quantization_error(x: Float64, scale: Float64) -> Float64:
    """Quantization round-trip error for symmetric INT8.

    Args:
        x: Original float.
        scale: Scale factor.

    Returns:
        Absolute reconstruction error.
    """
    var q = quantize_symmetric(x, scale)
    var x_hat = dequantize_symmetric(q, scale)
    var err = x - x_hat
    if err < 0.0:
        return -err
    return err


fn scale_from_range(x_max: Float64, n_bits: Float64) -> Float64:
    """Compute symmetric quantization scale from max absolute value.

    scale = x_max / (2^(n_bits-1) - 1)

    Args:
        x_max: Maximum absolute value in tensor.
        n_bits: Number of bits (e.g., 8 for INT8).

    Returns:
        Scale factor.
    """
    if n_bits <= 0.0:
        return 1.0
    var qmax = exp(n_bits * 0.6931471805599453) / 2.0 - 1.0  # 2^(n-1) - 1
    if qmax <= 0.0:
        return 1.0
    return x_max / qmax


fn zero_point_from_range(
    x_min: Float64, x_max: Float64, scale: Float64
) -> Float64:
    """Compute asymmetric quantization zero-point.

    zp = round(-x_min / scale)

    Args:
        x_min: Minimum float value.
        x_max: Maximum float value.
        scale: Scale factor.

    Returns:
        Zero-point (clipped to [0, 255]).
    """
    if scale <= 0.0:
        return 0.0
    var zp = -x_min / scale
    if zp > 255.0:
        return 255.0
    if zp < 0.0:
        return 0.0
    return Float64(Int64(zp + 0.5))


fn clamp_to_int8(x: Float64) -> Float64:
    """Clamp float to INT8 range [-128, 127].

    Args:
        x: Input value.

    Returns:
        Clamped value.
    """
    if x > 127.0:
        return 127.0
    if x < -128.0:
        return -128.0
    return x


fn fp16_to_fp32_scale(fp16_max: Float64) -> Float64:
    """FP16 dynamic range scale relative to FP32.

    FP16 max ≈ 65504; scale = fp16_value / 65504

    Args:
        fp16_max: Maximum value representable in FP16 context.

    Returns:
        Scale factor (≤ 1.0).
    """
    var fp16_abs_max = 65504.0
    if fp16_abs_max <= 0.0:
        return 1.0
    return fp16_max / fp16_abs_max


fn int4_pack_error(x: Float64, scale: Float64) -> Float64:
    """INT4 quantization error estimate (4-bit: [-8, 7] range).

    Args:
        x: Float value.
        scale: Scale factor for INT4.

    Returns:
        Absolute quantization error.
    """
    if scale <= 0.0:
        return 0.0
    var q = x / scale
    if q > 7.0:
        q = 7.0
    if q < -8.0:
        q = -8.0
    var q_rounded: Float64
    if q >= 0.0:
        q_rounded = Float64(Int64(q + 0.5))
    else:
        q_rounded = Float64(Int64(q - 0.5))
    var x_hat = q_rounded * scale
    var err = x - x_hat
    if err < 0.0:
        return -err
    return err
