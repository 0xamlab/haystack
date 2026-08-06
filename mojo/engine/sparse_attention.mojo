"""
sparse_attention.mojo — Sparse, local, and long-context attention variants.
Zero Python imports.

Public API:
  local_window_mask              — local window attention mask
  longformer_global_score        — Longformer global token score
  bigbird_random_block_select    — BigBird random block selection
  streaming_llm_sink_score       — StreamingLLM attention sink
  landmark_token_score           — landmark/retrieval-augmented attention
  chunk_cross_attention_weight   — cross-chunk attention weight
  linear_attention_kernel        — linear attention kernel φ(q)φ(k)
  recurrent_memory_update        — recurrent memory attention update
  block_sparse_density           — block-sparse attention density
  hyper_attention_estimate       — HyperAttention importance sampling
"""
from std.math import sqrt, log, exp


def local_window_mask(
    query_pos: Float64, key_pos: Float64,
    window_left: Float64, window_right: Float64
) -> Float64:
    """Local window attention: attend only within [pos-L, pos+R].

    Args:
        query_pos: Query position.
        key_pos: Key position.
        window_left: Left context window size.
        window_right: Right context window size (0 for causal).

    Returns:
        0.0 if within window, -1e9 if masked.
    """
    var dist = key_pos - query_pos
    if dist >= -window_left and dist <= window_right:
        return 0.0
    return -1e9


def longformer_global_score(
    query: Float64, key: Float64, head_dim: Float64,
    is_global: Float64
) -> Float64:
    """Longformer global token attention (e.g. [CLS] attends to all).

    Global tokens attend to and receive attention from all positions.

    Args:
        query: Query element.
        key: Key element.
        head_dim: Head dimension for scaling.
        is_global: 1.0 if either query or key is a global token.

    Returns:
        Attention score (always computed for global tokens).
    """
    if head_dim <= 0.0:
        return 0.0
    return query * key / sqrt(head_dim)


def bigbird_random_block_select(
    block_id: Float64, n_blocks: Float64,
    random_seed: Float64, n_random: Float64
) -> Float64:
    """BigBird random attention: block selected if in random subset.

    Returns 1.0 if this block is randomly attended to.

    Args:
        block_id: Block index to evaluate.
        n_blocks: Total blocks.
        random_seed: Seed for deterministic random selection.
        n_random: Number of random blocks to select.

    Returns:
        1.0 if block is in random attention set.
    """
    var hash = Float64(Int64(block_id * 31.0 + random_seed) % Int64(n_blocks))
    if hash < n_random:
        return 1.0
    return 0.0


def streaming_llm_sink_score(
    position: Float64, n_sink_tokens: Float64,
    window_size: Float64, seq_len: Float64
) -> Float64:
    """StreamingLLM: attention to sink tokens + sliding window.

    Returns 1.0 if position is attended (sink or window).

    Args:
        position: Key position to check.
        n_sink_tokens: Number of initial sink tokens.
        window_size: Recent context window size.
        seq_len: Current sequence length.

    Returns:
        1.0 if position is attended.
    """
    if position < n_sink_tokens:
        return 1.0
    if position >= seq_len - window_size:
        return 1.0
    return 0.0


def landmark_token_score(
    landmark_attention: Float64, block_attention: Float64,
    is_landmark: Float64
) -> Float64:
    """Landmark attention (LM-Infinite): two-level retrieval score.

    Args:
        landmark_attention: Attention to landmark token (block summary).
        block_attention: Attention within selected block.
        is_landmark: 1.0 if token is a landmark.

    Returns:
        Combined retrieval-augmented attention score.
    """
    if is_landmark > 0.5:
        return landmark_attention
    return landmark_attention * block_attention


def chunk_cross_attention_weight(
    chunk_query: Float64, chunk_key: Float64,
    n_chunks: Float64, head_dim: Float64
) -> Float64:
    """Cross-chunk attention weight for chunked attention schemes.

    Args:
        chunk_query: Chunk query representation element.
        chunk_key: Chunk key element from another chunk.
        n_chunks: Total number of chunks.
        head_dim: Head dimension.

    Returns:
        Cross-chunk attention score element.
    """
    if head_dim <= 0.0:
        return 0.0
    return chunk_query * chunk_key / sqrt(head_dim * n_chunks)


def linear_attention_kernel(x: Float64) -> Float64:
    """Linear attention feature map φ(x) = elu(x) + 1.

    Replaces softmax for O(N) attention complexity.

    Args:
        x: Input value (query or key element).

    Returns:
        Feature map value φ(x).
    """
    if x >= 0.0:
        return x + 1.0
    return exp(x)  # ELU(x) + 1 = exp(x) for x < 0


def recurrent_memory_update(
    memory: Float64, new_key: Float64,
    new_value: Float64, decay: Float64
) -> Float64:
    """Recurrent memory attention update (linear recurrence).

    M_t = decay × M_{t-1} + k × v

    Args:
        memory: Current memory state.
        new_key: New key element.
        new_value: New value element.
        decay: Memory decay factor.

    Returns:
        Updated memory state.
    """
    return decay * memory + new_key * new_value


def block_sparse_density(
    n_attended_blocks: Float64, total_blocks: Float64
) -> Float64:
    """Block-sparse attention density (fraction of blocks attended).

    Args:
        n_attended_blocks: Blocks actually computed.
        total_blocks: Total possible blocks (seq²/block_size²).

    Returns:
        Sparsity (0 = fully sparse, 1 = dense).
    """
    if total_blocks <= 0.0:
        return 1.0
    return n_attended_blocks / total_blocks


def hyper_attention_estimate(
    high_attn_score: Float64, random_sample_score: Float64,
    n_high: Float64, n_random: Float64, seq_len: Float64
) -> Float64:
    """HyperAttention importance sampling attention estimate.

    Combines heavy hitter and random sample attention.

    Args:
        high_attn_score: Attention score from high-importance tokens.
        random_sample_score: Attention score from random sample.
        n_high: Number of high-attention tokens.
        n_random: Number of randomly sampled tokens.
        seq_len: Total sequence length.

    Returns:
        Estimated full attention score.
    """
    if seq_len <= 0.0:
        return high_attn_score + random_sample_score
    var random_scale = (seq_len - n_high) / (n_random + 1e-6)
    return high_attn_score + random_scale * random_sample_score
