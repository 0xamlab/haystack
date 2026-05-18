"""
transformer_attention.mojo — Transformer attention mechanism calculations. Zero Python imports.

Public API:
  scaled_dot_product_attention  — QKV attention score
  attention_softmax_stable      — numerically stable softmax for attention
  multi_head_split               — head dimension scaling
  causal_mask_value              — causal mask for autoregressive models
  attention_entropy              — entropy of attention distribution
  kv_cache_memory_bytes         — KV cache size estimate
  flash_attention_block_score   — block-level flash attention approximation
  rope_rotation_angle           — RoPE angle for position and dimension
  relative_position_bias        — T5-style relative position bias
  cross_attention_score         — encoder-decoder cross-attention
"""
from std.math import sqrt, log, exp


fn scaled_dot_product_attention(
    q_dot_k: Float64, d_k: Float64
) -> Float64:
    """Scaled dot-product attention score: score = QK^T / sqrt(d_k).

    Args:
        q_dot_k: Dot product of query and key vectors.
        d_k: Key/query dimension.

    Returns:
        Scaled attention logit.
    """
    if d_k <= 0.0:
        return 0.0
    return q_dot_k / sqrt(d_k)


fn attention_softmax_stable(
    score: Float64, max_score: Float64, sum_exp: Float64
) -> Float64:
    """Numerically stable softmax for a single attention weight.

    w_i = exp(score - max_score) / sum_exp

    Args:
        score: Raw attention logit.
        max_score: Maximum logit in the row (for stability).
        sum_exp: Sum of exp(score - max) across all keys.

    Returns:
        Attention weight (0–1).
    """
    if sum_exp <= 0.0:
        return 0.0
    return exp(score - max_score) / sum_exp


fn multi_head_split(d_model: Float64, n_heads: Float64) -> Float64:
    """Per-head dimension: d_k = d_model / n_heads.

    Args:
        d_model: Model embedding dimension.
        n_heads: Number of attention heads.

    Returns:
        Head dimension d_k.
    """
    if n_heads <= 0.0:
        return 0.0
    return d_model / n_heads


fn causal_mask_value(query_pos: Float64, key_pos: Float64) -> Float64:
    """Causal (autoregressive) mask: -inf if key > query position.

    Args:
        query_pos: Query token position index.
        key_pos: Key token position index.

    Returns:
        0.0 if key_pos <= query_pos (attend), -1e9 otherwise (mask).
    """
    if key_pos > query_pos:
        return -1e9
    return 0.0


fn attention_entropy(
    attention_weight: Float64, n_keys: Float64
) -> Float64:
    """Per-token attention entropy contribution: -w * log(w).

    Args:
        attention_weight: Attention weight for one key (0–1).
        n_keys: Total number of keys (for normalisation reference).

    Returns:
        Entropy contribution (nats).
    """
    if attention_weight <= 0.0:
        return 0.0
    return -attention_weight * log(attention_weight)


fn kv_cache_memory_bytes(
    n_layers: Float64, n_heads: Float64,
    d_head: Float64, seq_len: Float64, batch_size: Float64
) -> Float64:
    """KV cache memory footprint in bytes (float16 assumed).

    bytes = 2 (K+V) × layers × heads × d_head × seq_len × batch × 2 (fp16)

    Args:
        n_layers: Number of transformer layers.
        n_heads: Number of attention heads.
        d_head: Head dimension.
        seq_len: Sequence length.
        batch_size: Batch size.

    Returns:
        KV cache size (bytes).
    """
    return 2.0 * n_layers * n_heads * d_head * seq_len * batch_size * 2.0


fn flash_attention_block_score(
    q_dot_k_sum: Float64, block_size: Float64, d_k: Float64
) -> Float64:
    """Flash attention block-level score approximation.

    block_score = sum(q·k) / (block_size × sqrt(d_k))

    Args:
        q_dot_k_sum: Sum of dot products in the block.
        block_size: Number of keys in the block.
        d_k: Key dimension.

    Returns:
        Block attention score estimate.
    """
    var denom = block_size * sqrt(d_k)
    if denom <= 0.0:
        return 0.0
    return q_dot_k_sum / denom


fn rope_rotation_angle(
    position: Float64, dimension_idx: Float64, d_model: Float64, base: Float64
) -> Float64:
    """RoPE rotation angle: θ = position × base^(-2i/d).

    Args:
        position: Token position in sequence.
        dimension_idx: Dimension pair index i (0, 1, 2, ...).
        d_model: Model dimension.
        base: RoPE base (10000 by default).

    Returns:
        Rotation angle θ (radians).
    """
    if d_model <= 0.0:
        return 0.0
    var theta = pow_approx(base, -2.0 * dimension_idx / d_model)
    return position * theta


fn pow_approx(base: Float64, exponent: Float64) -> Float64:
    return exp(exponent * log(base))


fn relative_position_bias(
    query_pos: Float64, key_pos: Float64, num_buckets: Float64, max_distance: Float64
) -> Float64:
    """T5-style relative position bias bucket index.

    bucket = log(|q-k|) / log(max_dist) × num_buckets/2

    Args:
        query_pos: Query position.
        key_pos: Key position.
        num_buckets: Total number of relative position buckets.
        max_distance: Maximum distance for log-scale bucketing.

    Returns:
        Bucket index (used to look up bias embedding).
    """
    var dist = query_pos - key_pos
    if dist < 0.0:
        dist = -dist
    if dist == 0.0:
        return 0.0
    if max_distance <= 1.0:
        return 0.0
    var log_bucket = log(dist) / log(max_distance) * (num_buckets / 2.0)
    if log_bucket > num_buckets / 2.0:
        return num_buckets / 2.0
    return log_bucket


fn cross_attention_score(
    decoder_q: Float64, encoder_k: Float64, d_k: Float64
) -> Float64:
    """Encoder-decoder cross-attention scaled score.

    score = (q · k) / sqrt(d_k)

    Args:
        decoder_q: Decoder query projection value.
        encoder_k: Encoder key projection value.
        d_k: Key dimension.

    Returns:
        Cross-attention score.
    """
    if d_k <= 0.0:
        return 0.0
    return decoder_q * encoder_k / sqrt(d_k)
