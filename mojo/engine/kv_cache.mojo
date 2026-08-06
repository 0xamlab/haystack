"""
kv_cache.mojo — KV-cache memory math and incremental decoding primitives.
Zero Python imports.

Public API:
  kv_cache_memory_per_layer      — bytes per transformer layer KV cache
  kv_cache_total_memory          — total KV cache across all layers
  kv_cache_utilization           — fraction of KV cache slots used
  paged_attention_block_count    — number of blocks for sequence
  prefix_cache_hit_bytes         — bytes saved by prefix caching
  kv_eviction_score_lru          — LRU eviction priority score
  kv_eviction_score_h2o          — H2O attention-based eviction score
  incremental_decode_kv_append   — appended KV pairs per decode step
  radix_cache_shared_prefix_len  — shared prefix length for radix cache
  kv_quantization_error          — error from INT8 KV cache quantization
"""
from std.math import sqrt, log, exp


def kv_cache_memory_per_layer(
    batch_size: Float64, seq_len: Float64,
    n_heads: Float64, head_dim: Float64, dtype_bytes: Float64
) -> Float64:
    """KV cache memory for one transformer layer.

    memory = 2 (K+V) × batch × seq × n_heads × head_dim × dtype_bytes

    Args:
        batch_size: Number of sequences in batch.
        seq_len: Maximum sequence length cached.
        n_heads: Number of attention heads (KV heads for GQA).
        head_dim: Dimension per head.
        dtype_bytes: Bytes per element (2=FP16, 1=INT8).

    Returns:
        KV cache bytes for this layer.
    """
    return 2.0 * batch_size * seq_len * n_heads * head_dim * dtype_bytes


def kv_cache_total_memory(
    per_layer_bytes: Float64, n_layers: Float64
) -> Float64:
    """Total KV cache across all transformer layers.

    Args:
        per_layer_bytes: KV cache bytes per layer.
        n_layers: Number of transformer layers.

    Returns:
        Total KV cache memory in bytes.
    """
    return per_layer_bytes * n_layers


def kv_cache_utilization(
    cached_tokens: Float64, max_tokens: Float64
) -> Float64:
    """Fraction of KV cache slots currently occupied.

    Args:
        cached_tokens: Tokens currently in cache.
        max_tokens: Maximum cache capacity in tokens.

    Returns:
        Cache utilization (0–1).
    """
    if max_tokens <= 0.0:
        return 0.0
    var util = cached_tokens / max_tokens
    if util > 1.0:
        return 1.0
    return util


def paged_attention_block_count(
    seq_len: Float64, block_size: Float64
) -> Float64:
    """Number of paged attention blocks for a sequence.

    blocks = ceil(seq_len / block_size)

    Args:
        seq_len: Sequence length.
        block_size: Tokens per block (16 typical in vLLM).

    Returns:
        Number of blocks allocated.
    """
    if block_size <= 0.0:
        return seq_len
    return Float64(Int64((seq_len + block_size - 1.0) / block_size))


def prefix_cache_hit_bytes(
    shared_prefix_len: Float64, n_heads: Float64, head_dim: Float64,
    n_layers: Float64, dtype_bytes: Float64
) -> Float64:
    """Bytes saved by prefix caching for a shared prompt prefix.

    Args:
        shared_prefix_len: Number of shared prefix tokens.
        n_heads: KV heads per layer.
        head_dim: Head dimension.
        n_layers: Transformer layers.
        dtype_bytes: KV cache dtype bytes.

    Returns:
        Bytes saved (= computation avoided).
    """
    return 2.0 * shared_prefix_len * n_heads * head_dim * n_layers * dtype_bytes


def kv_eviction_score_lru(
    last_access_time: Float64, current_time: Float64
) -> Float64:
    """LRU eviction score: time since last access (evict highest).

    Args:
        last_access_time: Time of last access to this KV entry.
        current_time: Current time.

    Returns:
        Eviction priority (higher = evict sooner).
    """
    return current_time - last_access_time


def kv_eviction_score_h2o(
    attention_sum: Float64, recency_weight: Float64
) -> Float64:
    """H2O (Heavy-Hitter Oracle) KV eviction score.

    Keeps high-attention tokens; evicts low-attention + old tokens.
    Score = attention_sum × recency (lower = more likely to evict).

    Args:
        attention_sum: Accumulated attention score for this KV position.
        recency_weight: Recency factor (decay with age).

    Returns:
        Retention score (lower = evict sooner).
    """
    return attention_sum * recency_weight


def incremental_decode_kv_append(
    current_len: Float64
) -> Float64:
    """KV pairs appended per autoregressive decode step.

    Each decode step adds exactly 1 K and 1 V per layer per head.

    Args:
        current_len: Current cached sequence length.

    Returns:
        New length after appending one token.
    """
    return current_len + 1.0


def radix_cache_shared_prefix_len(
    prefix_a_len: Float64, prefix_b_len: Float64, match_len: Float64
) -> Float64:
    """Shared prefix length for radix tree KV cache.

    Args:
        prefix_a_len: Length of first sequence prefix.
        prefix_b_len: Length of second sequence prefix.
        match_len: Length of common prefix.

    Returns:
        Shared prefix length (capped at shorter sequence).
    """
    var min_len = prefix_a_len if prefix_a_len < prefix_b_len else prefix_b_len
    if match_len > min_len:
        return min_len
    return match_len


def kv_quantization_error(
    value: Float64, scale: Float64, zero_point: Float64
) -> Float64:
    """Round-trip error from INT8 KV cache quantization.

    Args:
        value: Original FP16/FP32 KV value.
        scale: Quantization scale.
        zero_point: Zero point offset.

    Returns:
        Absolute quantization error.
    """
    if scale <= 0.0:
        return 0.0
    var q = Float64(Int64((value / scale + zero_point) + 0.5))
    if q > 127.0:
        q = 127.0
    if q < -128.0:
        q = -128.0
    var reconstructed = (q - zero_point) * scale
    var err = value - reconstructed
    if err < 0.0:
        return -err
    return err
