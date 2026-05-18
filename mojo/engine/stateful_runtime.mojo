"""
stateful_runtime.mojo — Stateful AI runtime: session memory, long-term memory, state transitions.
Zero Python imports.

Public API:
  session_memory_relevance       — relevance of stored memory to current query
  memory_decay_score             — recency-weighted memory decay
  state_transition_validity      — valid state machine transition check
  replay_buffer_priority         — prioritised experience replay score
  memory_consolidation_score     — when to consolidate short→long term memory
  working_memory_capacity_used   — fraction of working memory in use
  long_term_retrieval_score      — score for long-term memory retrieval
  state_compression_ratio        — compression ratio for state checkpoint
  replayability_score            — how faithfully a state can be replayed
  session_continuity_score       — continuity between session chunks
"""
from std.math import sqrt, log, exp


fn session_memory_relevance(
    memory_embedding: Float64, query_embedding: Float64,
    recency_weight: Float64, access_count: Float64
) -> Float64:
    """Relevance of stored memory to current query (BM25-style + recency).

    score = embedding_sim × recency_weight × log(1 + access_count)

    Args:
        memory_embedding: Memory representation element.
        query_embedding: Current query representation element.
        recency_weight: Recency weight (1=fresh, 0=old).
        access_count: Times this memory has been accessed.

    Returns:
        Memory relevance score.
    """
    var sim = memory_embedding * query_embedding
    if sim < 0.0:
        sim = 0.0
    return sim * recency_weight * log(1.0 + access_count)


fn memory_decay_score(
    memory_strength: Float64, elapsed_steps: Float64,
    decay_rate: Float64
) -> Float64:
    """Ebbinghaus-style memory decay over time.

    strength(t) = S₀ × exp(-decay × t)

    Args:
        memory_strength: Initial memory strength.
        elapsed_steps: Steps since memory was formed.
        decay_rate: Decay rate constant.

    Returns:
        Current memory strength after decay.
    """
    return memory_strength * exp(-decay_rate * elapsed_steps)


fn state_transition_validity(
    from_state: Float64, to_state: Float64,
    n_states: Float64, transition_mask_bit: Float64
) -> Float64:
    """Valid state machine transition check.

    Returns 1.0 if transition is valid per transition mask.

    Args:
        from_state: Current state index.
        to_state: Target state index.
        n_states: Total number of states.
        transition_mask_bit: 1.0 if this transition is allowed.

    Returns:
        1.0 if valid, 0.0 if invalid.
    """
    if from_state < 0.0 or to_state < 0.0:
        return 0.0
    if from_state >= n_states or to_state >= n_states:
        return 0.0
    return transition_mask_bit


fn replay_buffer_priority(
    td_error: Float64, priority_alpha: Float64,
    max_priority: Float64
) -> Float64:
    """Prioritised experience replay: priority = |TD error|^α.

    Args:
        td_error: Temporal difference error for this experience.
        priority_alpha: Priority exponent (0=uniform, 1=proportional).
        max_priority: Maximum priority cap.

    Returns:
        Replay priority.
    """
    var abs_error = td_error if td_error >= 0.0 else -td_error
    var priority = exp(priority_alpha * log(abs_error + 1e-6))
    if priority > max_priority:
        return max_priority
    return priority


fn memory_consolidation_score(
    access_frequency: Float64, memory_importance: Float64,
    short_term_capacity_pressure: Float64
) -> Float64:
    """When to consolidate short→long-term memory.

    score > 0 → consolidate to long-term.

    Args:
        access_frequency: How often this memory is accessed.
        memory_importance: Importance score of this memory.
        short_term_capacity_pressure: How full short-term memory is (0–1).

    Returns:
        Consolidation score (positive = move to long-term).
    """
    return memory_importance * access_frequency * (1.0 + short_term_capacity_pressure) - 1.0


fn working_memory_capacity_used(
    active_tokens: Float64, context_window: Float64,
    reserved_output_tokens: Float64
) -> Float64:
    """Fraction of working memory (context window) in use.

    Args:
        active_tokens: Tokens currently in context.
        context_window: Maximum context window size.
        reserved_output_tokens: Tokens reserved for output.

    Returns:
        Working memory utilization (0–1).
    """
    var usable = context_window - reserved_output_tokens
    if usable <= 0.0:
        return 1.0
    var used = active_tokens / usable
    if used > 1.0:
        return 1.0
    return used


fn long_term_retrieval_score(
    semantic_similarity: Float64, temporal_relevance: Float64,
    importance_weight: Float64
) -> Float64:
    """Score for long-term memory retrieval (semantic + temporal + importance).

    Args:
        semantic_similarity: Cosine-like similarity to query.
        temporal_relevance: Recency weight.
        importance_weight: Stored importance of this memory.

    Returns:
        Retrieval ranking score.
    """
    return semantic_similarity * 0.5 + temporal_relevance * 0.3 + importance_weight * 0.2


fn state_compression_ratio(
    raw_state_bytes: Float64, compressed_state_bytes: Float64
) -> Float64:
    """Compression ratio for state checkpoint storage.

    Args:
        raw_state_bytes: Uncompressed state size.
        compressed_state_bytes: Compressed state size.

    Returns:
        Compression ratio (higher = more compressed).
    """
    if compressed_state_bytes <= 0.0:
        return 1.0
    return raw_state_bytes / compressed_state_bytes


fn replayability_score(
    deterministic_ops_fraction: Float64, external_state_captured: Float64,
    rng_seed_fixed: Float64
) -> Float64:
    """How faithfully a state can be replayed.

    Args:
        deterministic_ops_fraction: Fraction of ops that are deterministic.
        external_state_captured: Fraction of external state saved (0–1).
        rng_seed_fixed: 1.0 if RNG seed is fixed.

    Returns:
        Replayability score (1.0 = perfectly replayable).
    """
    return deterministic_ops_fraction * external_state_captured * (0.5 + 0.5 * rng_seed_fixed)


fn session_continuity_score(
    overlap_tokens: Float64, session_chunk_tokens: Float64,
    context_coverage: Float64
) -> Float64:
    """Continuity between session chunks (e.g. long conversation windows).

    Args:
        overlap_tokens: Shared tokens between chunks.
        session_chunk_tokens: Tokens per chunk.
        context_coverage: Fraction of prior context retained.

    Returns:
        Continuity score (1 = seamless, 0 = no continuity).
    """
    if session_chunk_tokens <= 0.0:
        return 1.0
    var overlap_ratio = overlap_tokens / session_chunk_tokens
    if overlap_ratio > 1.0:
        overlap_ratio = 1.0
    return 0.5 * overlap_ratio + 0.5 * context_coverage
