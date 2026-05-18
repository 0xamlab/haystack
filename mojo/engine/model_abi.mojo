"""
model_abi.mojo — Universal model ABI: unified tensor layout, execution, attention interface.
Zero Python imports.

Public API:
  tensor_layout_stride            — stride for a dimension in a canonical layout
  dtype_byte_width                — bytes per element for standard dtype codes
  attention_head_dim              — head dimension from model config
  rope_theta_scale                — RoPE theta scaling for context extension
  weight_shard_offset             — byte offset for a weight shard in ABI layout
  activation_layout_index         — flat index for NHWC vs NCHW layouts
  model_config_head_count         — number of attention heads from config params
  kv_head_group_size              — GQA/MQA KV head grouping factor
  ffn_dim_from_model_dim          — FFN intermediate dimension from model dim
  abi_version_compatible          — check ABI version compatibility
"""
from std.math import sqrt, log, exp


fn tensor_layout_stride(
    dim_size: Float64, element_size_bytes: Float64,
    outer_stride: Float64
) -> Float64:
    """Stride for a dimension in a packed row-major (C-contiguous) tensor.

    stride_i = outer_stride × dim_size × element_size

    Args:
        dim_size: Size of this dimension.
        element_size_bytes: Bytes per element.
        outer_stride: Stride of the next outer dimension.

    Returns:
        Stride in bytes for this dimension.
    """
    return outer_stride * dim_size * element_size_bytes


fn dtype_byte_width(dtype_code: Float64) -> Float64:
    """Bytes per element for standard dtype codes.

    Codes: 0=fp32(4), 1=fp16(2), 2=bf16(2), 3=int8(1), 4=int4(0.5), 5=fp64(8)

    Args:
        dtype_code: Numeric dtype code.

    Returns:
        Bytes per element.
    """
    if dtype_code == 0.0:
        return 4.0  # fp32
    if dtype_code == 1.0:
        return 2.0  # fp16
    if dtype_code == 2.0:
        return 2.0  # bf16
    if dtype_code == 3.0:
        return 1.0  # int8
    if dtype_code == 4.0:
        return 0.5  # int4 (packed)
    if dtype_code == 5.0:
        return 8.0  # fp64
    return 4.0  # default fp32


fn attention_head_dim(
    model_dim: Float64, n_heads: Float64
) -> Float64:
    """Head dimension from model config.

    head_dim = model_dim / n_heads

    Args:
        model_dim: Total model hidden dimension.
        n_heads: Number of attention heads.

    Returns:
        Per-head dimension.
    """
    if n_heads <= 0.0:
        return model_dim
    return model_dim / n_heads


fn rope_theta_scale(
    base_theta: Float64, original_context: Float64,
    target_context: Float64
) -> Float64:
    """RoPE theta scaling for context length extension (NTK-aware).

    theta_scaled = base × (target / original) ^ (dim / (dim - 2))

    Simplified: scale = (target / original)^scaling_factor

    Args:
        base_theta: Original RoPE base theta (e.g. 10000).
        original_context: Original maximum context length.
        target_context: Target extended context length.

    Returns:
        Scaled theta value.
    """
    if original_context <= 0.0:
        return base_theta
    var scale_ratio = target_context / original_context
    return base_theta * scale_ratio * scale_ratio


fn weight_shard_offset(
    shard_index: Float64, shard_size_bytes: Float64,
    header_bytes: Float64
) -> Float64:
    """Byte offset for a weight shard in unified model ABI layout.

    offset = header + shard_index × shard_size

    Args:
        shard_index: Index of this weight shard.
        shard_size_bytes: Size of each shard in bytes.
        header_bytes: Header/metadata size.

    Returns:
        Byte offset into the model file.
    """
    return header_bytes + shard_index * shard_size_bytes


fn activation_layout_index(
    n: Float64, c: Float64, h: Float64, w: Float64,
    c_size: Float64, h_size: Float64, w_size: Float64,
    is_nhwc: Float64
) -> Float64:
    """Flat index for NHWC vs NCHW activation layouts.

    Args:
        n: Batch index.
        c: Channel index.
        h: Height index.
        w: Width index.
        c_size: Number of channels.
        h_size: Height size.
        w_size: Width size.
        is_nhwc: 1.0 for NHWC, 0.0 for NCHW.

    Returns:
        Flat memory index.
    """
    if is_nhwc > 0.5:
        return n * h_size * w_size * c_size + h * w_size * c_size + w * c_size + c
    return n * c_size * h_size * w_size + c * h_size * w_size + h * w_size + w


fn model_config_head_count(
    model_dim: Float64, head_dim: Float64
) -> Float64:
    """Number of attention heads from model config parameters.

    Args:
        model_dim: Total hidden dimension.
        head_dim: Per-head dimension.

    Returns:
        Number of attention heads.
    """
    if head_dim <= 0.0:
        return 1.0
    return model_dim / head_dim


fn kv_head_group_size(
    n_query_heads: Float64, n_kv_heads: Float64
) -> Float64:
    """GQA/MQA KV head grouping factor (query heads per KV head).

    Args:
        n_query_heads: Number of query heads.
        n_kv_heads: Number of KV heads (< n_query_heads for GQA).

    Returns:
        Grouping factor (1 = MHA, n_query/n_kv = GQA, n_query = MQA).
    """
    if n_kv_heads <= 0.0:
        return n_query_heads
    return n_query_heads / n_kv_heads


fn ffn_dim_from_model_dim(
    model_dim: Float64, ffn_multiplier: Float64,
    round_to: Float64
) -> Float64:
    """FFN intermediate dimension from model dim and multiplier.

    Rounds to nearest multiple of round_to for hardware efficiency.

    Args:
        model_dim: Model hidden dimension.
        ffn_multiplier: FFN expansion factor (e.g. 4 for GPT, 8/3 for LLaMA).
        round_to: Round result to multiple of this value.

    Returns:
        FFN intermediate dimension.
    """
    var raw = model_dim * ffn_multiplier
    if round_to <= 0.0:
        return raw
    return Float64(Int64(raw / round_to) + 1) * round_to


fn abi_version_compatible(
    model_abi_version: Float64, runtime_abi_version: Float64,
    breaking_version_threshold: Float64
) -> Float64:
    """Check ABI version compatibility between model and runtime.

    Returns 1.0 if compatible, 0.0 if breaking incompatibility.

    Args:
        model_abi_version: ABI version the model was saved with.
        runtime_abi_version: ABI version of the current runtime.
        breaking_version_threshold: Version difference that causes breaking change.

    Returns:
        1.0 if compatible.
    """
    var diff = runtime_abi_version - model_abi_version
    if diff < 0.0:
        diff = -diff
    if diff >= breaking_version_threshold:
        return 0.0
    return 1.0
