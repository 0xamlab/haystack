"""
positional_encoding.mojo — Positional encodings for transformers.
Zero Python imports.

Public API:
  sinusoidal_pe                  — Vaswani et al. sinusoidal PE
  rope_cos_component             — RoPE cosine component
  rope_sin_component             — RoPE sine component
  rope_apply_cos                 — apply RoPE cos rotation
  rope_apply_sin                 — apply RoPE sin rotation
  alibi_slope                    — ALiBi attention slope
  alibi_bias                     — ALiBi position bias
  learned_pe_init                — Xavier initialisation scale for learned PE
  relative_pe_bucket             — T5 relative position bucket
  xpos_scale                     — xPos position-dependent scale
"""
from std.math import sqrt, log, exp, cos, sin


fn sinusoidal_pe(pos: Float64, dim: Float64, d_model: Float64) -> Float64:
    """Sinusoidal positional encoding (Vaswani et al. 2017).

    PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))

    Uses sin for even dim, cos for odd dim.

    Args:
        pos: Position index.
        dim: Dimension index (0-indexed).
        d_model: Model embedding dimension.

    Returns:
        PE value at (pos, dim).
    """
    if d_model <= 0.0:
        return 0.0
    var i = Float64(Int64(dim / 2.0))
    var angle = pos / exp(2.0 * i * log(10000.0) / d_model)
    var mod2 = dim - 2.0 * Float64(Int64(dim / 2.0))
    if mod2 < 0.5:
        return sin(angle)
    return cos(angle)


fn rope_cos_component(pos: Float64, dim: Float64, base: Float64) -> Float64:
    """RoPE cosine component for dimension dim at position pos.

    theta_i = pos / base^(2i/d)

    Args:
        pos: Sequence position.
        dim: Dimension index (pair index i = dim//2).
        base: RoPE base (10000 default).

    Returns:
        Cosine of the rotation angle.
    """
    var i = Float64(Int64(dim / 2.0))
    var theta = pos / exp(2.0 * i * log(base))
    return cos(theta)


fn rope_sin_component(pos: Float64, dim: Float64, base: Float64) -> Float64:
    """RoPE sine component for dimension dim at position pos.

    Args:
        pos: Sequence position.
        dim: Dimension index.
        base: RoPE base (10000 default).

    Returns:
        Sine of the rotation angle.
    """
    var i = Float64(Int64(dim / 2.0))
    var theta = pos / exp(2.0 * i * log(base))
    return sin(theta)


fn rope_apply_cos(x: Float64, cos_val: Float64) -> Float64:
    """Apply RoPE cosine rotation to even dimension: x × cos.

    Args:
        x: Input value.
        cos_val: Cosine of rotation angle.

    Returns:
        Rotated value (cos part).
    """
    return x * cos_val


fn rope_apply_sin(
    x: Float64, x_pair: Float64, sin_val: Float64, is_even: Float64
) -> Float64:
    """Apply RoPE sine rotation using paired dimension.

    For even dim: x_even×cos - x_odd×sin
    For odd dim:  x_even×sin + x_odd×cos

    This function returns the sin contribution only.

    Args:
        x: Current dimension value.
        x_pair: Paired dimension value.
        sin_val: Sine of rotation angle.
        is_even: 1.0 if even dimension, 0.0 if odd.

    Returns:
        Sine rotation contribution.
    """
    if is_even > 0.5:
        return -x_pair * sin_val
    return x_pair * sin_val


fn alibi_slope(head: Float64, n_heads: Float64) -> Float64:
    """ALiBi attention slope for head h (Press et al. 2022).

    slope_h = 2^(-8h/n_heads)

    Args:
        head: Head index (1-indexed).
        n_heads: Total attention heads.

    Returns:
        ALiBi slope for this head.
    """
    if n_heads <= 0.0:
        return 1.0
    return exp(-8.0 * head / n_heads * 0.6931471805599453)


fn alibi_bias(
    query_pos: Float64, key_pos: Float64, slope: Float64
) -> Float64:
    """ALiBi position bias: -slope × |query_pos - key_pos|.

    Args:
        query_pos: Query token position.
        key_pos: Key token position.
        slope: Head-specific slope from alibi_slope.

    Returns:
        Additive attention bias.
    """
    var dist = query_pos - key_pos
    if dist < 0.0:
        dist = -dist
    return -slope * dist


fn learned_pe_init(d_model: Float64) -> Float64:
    """Xavier uniform init scale for learned positional embeddings.

    scale = sqrt(6 / d_model)

    Args:
        d_model: Embedding dimension.

    Returns:
        Uniform distribution bound for initialisation.
    """
    if d_model <= 0.0:
        return 1.0
    return sqrt(6.0 / d_model)


fn relative_pe_bucket(
    relative_pos: Float64, num_buckets: Float64, max_distance: Float64
) -> Float64:
    """T5 relative position bucket index.

    Args:
        relative_pos: Relative position (query - key).
        num_buckets: Total number of buckets.
        max_distance: Maximum distance for logarithmic buckets.

    Returns:
        Bucket index as Float64.
    """
    var ret = 0.0
    var rp = relative_pos
    var half_buckets = Float64(Int64(num_buckets / 2.0))
    if rp < 0.0:
        rp = -rp
        ret = half_buckets
    var max_exact = half_buckets / 2.0
    if rp < max_exact:
        return ret + rp
    var log_ratio = log(rp / max_exact) / log(max_distance / max_exact)
    var bucket = max_exact + log_ratio * (half_buckets - max_exact)
    if bucket > half_buckets - 1.0:
        bucket = half_buckets - 1.0
    return ret + bucket


fn xpos_scale(
    pos: Float64, dim: Float64, base: Float64, scale: Float64
) -> Float64:
    """xPos position-dependent scale factor (Sun et al. 2022).

    scale(pos, dim) = scale^(pos × dim/d_model)

    Args:
        pos: Sequence position.
        dim: Dimension index.
        base: xPos base (512 default).
        scale: Scale factor (0.95 typical).

    Returns:
        Position-dimension scale.
    """
    if base <= 0.0:
        return 1.0
    return exp(pos * dim / base * log(scale))
