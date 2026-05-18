"""
paged_kv_cache.mojo — Paged KV cache: virtualization, compaction, prefix sharing.
Zero Python imports.

Public API:
  page_table_lookup              — virtual → physical block mapping
  cache_compaction_gain          — memory recovered from compaction
  prefix_sharing_savings         — bytes saved by prefix tree sharing
  speculative_branch_memory      — KV memory for speculative branches
  cache_eviction_lru_score       — LRU eviction score
  cache_eviction_beladys_score   — Belady optimal eviction score
  block_copy_cost                — cost of copying KV block
  cache_hit_latency_saving       — latency saved by cache hit
  dynamic_ntk_rope_scale         — NTK-aware RoPE context extension
  context_extension_factor       — rope scaling for extended context
"""
from std.math import sqrt, log, exp


fn page_table_lookup(
    virtual_block_id: Float64, page_table_entry: Float64
) -> Float64:
    """Virtual-to-physical KV block mapping.

    Returns physical block ID from page table entry.

    Args:
        virtual_block_id: Logical block index in sequence.
        page_table_entry: Physical block assigned to this virtual block.

    Returns:
        Physical block ID.
    """
    return page_table_entry


fn cache_compaction_gain(
    fragmented_blocks: Float64, block_size_tokens: Float64,
    dtype_bytes: Float64, n_layers: Float64,
    n_heads: Float64, head_dim: Float64
) -> Float64:
    """Memory recovered by compacting fragmented KV cache blocks.

    Args:
        fragmented_blocks: Number of partially-filled blocks.
        block_size_tokens: Tokens per block.
        dtype_bytes: Bytes per KV element.
        n_layers: Transformer layers.
        n_heads: KV heads.
        head_dim: Head dimension.

    Returns:
        Bytes recoverable by compaction.
    """
    var bytes_per_block = block_size_tokens * n_layers * n_heads * head_dim * dtype_bytes * 2.0
    return fragmented_blocks * bytes_per_block * 0.5  # avg 50% wasted per block


fn prefix_sharing_savings(
    shared_prefix_tokens: Float64, n_sequences: Float64,
    n_layers: Float64, n_heads: Float64,
    head_dim: Float64, dtype_bytes: Float64
) -> Float64:
    """Memory saved by sharing KV cache for common prompt prefixes.

    Without sharing: each sequence stores its own prefix.
    Savings = (n_sequences - 1) × prefix_kv_bytes

    Args:
        shared_prefix_tokens: Number of shared prefix tokens.
        n_sequences: Sequences sharing this prefix.
        n_layers: Transformer layers.
        n_heads: KV heads.
        head_dim: Head dimension.
        dtype_bytes: Bytes per element.

    Returns:
        Bytes saved by prefix sharing.
    """
    var prefix_bytes = 2.0 * shared_prefix_tokens * n_layers * n_heads * head_dim * dtype_bytes
    if n_sequences <= 1.0:
        return 0.0
    return (n_sequences - 1.0) * prefix_bytes


fn speculative_branch_memory(
    n_branches: Float64, speculation_depth: Float64,
    n_layers: Float64, n_heads: Float64,
    head_dim: Float64, dtype_bytes: Float64
) -> Float64:
    """KV memory required for speculative decoding branches.

    Args:
        n_branches: Number of speculative branches (draft tokens).
        speculation_depth: Max tokens to speculate ahead.
        n_layers: Transformer layers.
        n_heads: KV heads per layer.
        head_dim: Head dimension.
        dtype_bytes: Bytes per KV element.

    Returns:
        Additional KV cache bytes for speculative branches.
    """
    return n_branches * speculation_depth * n_layers * n_heads * head_dim * dtype_bytes * 2.0


fn cache_eviction_lru_score(
    last_access_step: Float64, current_step: Float64
) -> Float64:
    """LRU eviction score: steps since last access (higher = evict sooner).

    Args:
        last_access_step: Training/inference step of last access.
        current_step: Current step.

    Returns:
        Eviction priority (higher = evict first).
    """
    return current_step - last_access_step


fn cache_eviction_beladys_score(
    next_access_step: Float64, current_step: Float64
) -> Float64:
    """Belady's optimal eviction: evict block used farthest in future.

    Args:
        next_access_step: Next step this block will be needed.
        current_step: Current step.

    Returns:
        Distance to next use (higher = evict first).
    """
    if next_access_step < current_step:
        return 1e9  # Never accessed again → evict
    return next_access_step - current_step


fn block_copy_cost(
    block_size_tokens: Float64, n_layers: Float64,
    n_heads: Float64, head_dim: Float64,
    dtype_bytes: Float64, bandwidth_gbs: Float64
) -> Float64:
    """Cost of copying one KV block (for preemption/migration, ms).

    Args:
        block_size_tokens: Tokens per block.
        n_layers: Transformer layers.
        n_heads: KV heads.
        head_dim: Head dimension.
        dtype_bytes: Bytes per element.
        bandwidth_gbs: Memory bandwidth (GB/s).

    Returns:
        Copy time in milliseconds.
    """
    var block_bytes = 2.0 * block_size_tokens * n_layers * n_heads * head_dim * dtype_bytes
    if bandwidth_gbs <= 0.0:
        return 0.0
    return block_bytes / (bandwidth_gbs * 1e9) * 1000.0


fn cache_hit_latency_saving(
    prompt_tokens: Float64, prefill_throughput_tps: Float64
) -> Float64:
    """Latency saving from KV cache hit (skipped prefill).

    Args:
        prompt_tokens: Tokens in cached prefix.
        prefill_throughput_tps: Prefill throughput (tokens/sec).

    Returns:
        Time saved in seconds.
    """
    if prefill_throughput_tps <= 0.0:
        return 0.0
    return prompt_tokens / prefill_throughput_tps


fn dynamic_ntk_rope_scale(
    seq_len: Float64, base_context: Float64, alpha: Float64
) -> Float64:
    """NTK-aware RoPE scaling factor for extended context.

    scale = (α × seq_len / base_context - (α-1))^(d/(d-2))
    Simplified: scale = (seq_len / base_context)^α

    Args:
        seq_len: Current sequence length.
        base_context: Original training context length.
        alpha: NTK scaling alpha (typically 2.0 for 2× extension).

    Returns:
        RoPE base scaling factor.
    """
    if base_context <= 0.0:
        return 1.0
    var ratio = seq_len / base_context
    if ratio <= 1.0:
        return 1.0
    return exp(alpha * log(ratio))


fn context_extension_factor(
    original_max_len: Float64, target_max_len: Float64
) -> Float64:
    """Rope scaling factor for simple context length extension.

    scale = target / original (linear position scaling)

    Args:
        original_max_len: Model's trained context length.
        target_max_len: Desired extended context length.

    Returns:
        Position scaling factor.
    """
    if original_max_len <= 0.0:
        return 1.0
    return target_max_len / original_max_len
