"""
model_interop.mojo — Safetensors, GGUF, ONNX, HuggingFace compatibility math.
Zero Python imports.

Public API:
  safetensors_tensor_offset      — tensor byte offset in safetensors file
  gguf_kv_metadata_size          — GGUF metadata entry size estimate
  onnx_node_flops                — ONNX op FLOPs estimate
  hf_config_head_dim             — head dimension from HF config
  hf_rope_theta_scale            — RoPE theta from HF config
  dtype_convert_scale            — precision conversion scale factor
  checkpoint_version_compat      — version compatibility score
  weight_remap_cost              — weight tensor rename/reshape cost
  tokenizer_vocab_overlap        — vocab overlap between tokenizers
  model_card_perplexity          — perplexity-based model quality proxy
"""
from std.math import sqrt, log, exp


def safetensors_tensor_offset(
    prev_tensor_bytes: Float64, alignment: Float64
) -> Float64:
    """Byte offset for next tensor in safetensors file.

    Tensors are aligned to 'alignment' bytes (8 typical).

    Args:
        prev_tensor_bytes: Bytes occupied by previous tensor.
        alignment: Alignment boundary in bytes.

    Returns:
        Aligned byte offset.
    """
    if alignment <= 0.0:
        return prev_tensor_bytes
    var remainder = prev_tensor_bytes - Float64(Int64(prev_tensor_bytes / alignment)) * alignment
    if remainder == 0.0:
        return prev_tensor_bytes
    return prev_tensor_bytes + (alignment - remainder)


def gguf_kv_metadata_size(
    key_len: Float64, value_type: Float64, value_count: Float64
) -> Float64:
    """GGUF key-value metadata entry size estimate.

    size = key_len + type_tag (4B) + value_bytes

    value_type: 0=int32(4), 1=float32(4), 2=string(8+len), 3=bool(1)

    Args:
        key_len: String key length in bytes.
        value_type: Value type code.
        value_count: Number of values (array size).

    Returns:
        Estimated metadata entry size in bytes.
    """
    var base = key_len + 4.0  # key + type tag
    if value_type == 2.0:
        return base + 8.0 * value_count  # string: 8B len + chars
    if value_type == 3.0:
        return base + value_count  # bool: 1B each
    return base + 4.0 * value_count  # int32/float32: 4B each


def onnx_node_flops(
    op_type: Float64, batch: Float64, m: Float64, n: Float64, k: Float64
) -> Float64:
    """ONNX operator FLOPs estimate.

    op_type: 1=MatMul(2MNK), 2=Conv(approx), 3=Softmax(5N), 4=LayerNorm(5N).

    Args:
        op_type: Operator type code.
        batch: Batch size.
        m: First matrix dimension.
        n: Second matrix dimension.
        k: Inner dimension.

    Returns:
        FLOPs estimate.
    """
    if op_type == 1.0:
        return 2.0 * batch * m * n * k
    if op_type == 2.0:
        return 2.0 * batch * m * n * k * 9.0  # conv with 3×3 kernel approx
    if op_type == 3.0:
        return 5.0 * batch * m * n
    if op_type == 4.0:
        return 5.0 * batch * m * n
    return batch * m * n


def hf_config_head_dim(
    hidden_size: Float64, num_attention_heads: Float64
) -> Float64:
    """Head dimension from HuggingFace model config.

    head_dim = hidden_size / num_heads

    Args:
        hidden_size: Model hidden dimension.
        num_attention_heads: Number of attention heads.

    Returns:
        Per-head dimension.
    """
    if num_attention_heads <= 0.0:
        return hidden_size
    return hidden_size / num_attention_heads


def hf_rope_theta_scale(
    base_theta: Float64, rope_scaling_factor: Float64
) -> Float64:
    """Scaled RoPE theta for extended context (HF rope_scaling config).

    theta_scaled = base_theta × factor

    Args:
        base_theta: Base RoPE theta (10000 typical).
        rope_scaling_factor: Scaling factor from HF config.

    Returns:
        Scaled theta.
    """
    return base_theta * rope_scaling_factor


def dtype_convert_scale(
    src_max: Float64, dst_max: Float64
) -> Float64:
    """Scale factor for dtype conversion (e.g. FP32 → FP16).

    scale = dst_max / src_max

    Args:
        src_max: Maximum representable value in source dtype.
        dst_max: Maximum representable value in destination dtype.

    Returns:
        Conversion scale (values should be multiplied by this).
    """
    if src_max <= 0.0:
        return 1.0
    return dst_max / src_max


def checkpoint_version_compat(
    model_version: Float64, checkpoint_version: Float64
) -> Float64:
    """Checkpoint version compatibility score.

    1.0 = fully compatible; lower = migration needed.

    Args:
        model_version: Current model version.
        checkpoint_version: Checkpoint version.

    Returns:
        Compatibility score (1.0 if exact match).
    """
    var diff = model_version - checkpoint_version
    if diff < 0.0:
        diff = -diff
    if diff == 0.0:
        return 1.0
    return 1.0 / (1.0 + diff)


def weight_remap_cost(
    n_tensors_to_remap: Float64, avg_tensor_elements: Float64,
    remap_overhead_factor: Float64
) -> Float64:
    """Cost of weight tensor renaming/reshaping during model load.

    cost = n_tensors × avg_elements × overhead

    Args:
        n_tensors_to_remap: Tensors requiring key remapping.
        avg_tensor_elements: Average elements per tensor.
        remap_overhead_factor: Per-element remapping overhead.

    Returns:
        Estimated remapping cost (relative units).
    """
    return n_tensors_to_remap * avg_tensor_elements * remap_overhead_factor


def tokenizer_vocab_overlap(
    vocab_a_size: Float64, vocab_b_size: Float64, shared_tokens: Float64
) -> Float64:
    """Vocabulary overlap between two tokenizers (Jaccard).

    overlap = shared / (|A| + |B| - shared)

    Args:
        vocab_a_size: Size of first vocabulary.
        vocab_b_size: Size of second vocabulary.
        shared_tokens: Tokens present in both vocabularies.

    Returns:
        Jaccard overlap (0–1).
    """
    var union_size = vocab_a_size + vocab_b_size - shared_tokens
    if union_size <= 0.0:
        return 0.0
    return shared_tokens / union_size


def model_card_perplexity(
    log_likelihood_sum: Float64, n_tokens: Float64
) -> Float64:
    """Perplexity from sum of log likelihoods.

    PPL = exp(-1/N × Σ log p(x_i))

    Args:
        log_likelihood_sum: Σ log p(x_i) across evaluation tokens.
        n_tokens: Total evaluation tokens.

    Returns:
        Perplexity.
    """
    if n_tokens <= 0.0:
        return 1e9
    return exp(-log_likelihood_sum / n_tokens)
