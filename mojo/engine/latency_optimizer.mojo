"""
latency_optimizer.mojo — Latency micro-optimizations: early exit, adaptive depth, async speculation.
Zero Python imports.

Public API:
  early_exit_confidence          — confidence for early exit from layer stack
  adaptive_depth_score           — score for skipping remaining layers
  prefill_decode_split_latency   — latency model for prefill/decode split
  async_speculation_gain         — gain from speculative async branches
  token_streaming_headroom       — buffer fullness for streaming output
  layer_skip_quality_cost        — quality loss from skipping a layer
  partial_forward_savings        — savings from partial forward pass
  kv_prefetch_overlap            — overlap of KV prefetch with decode
  attention_skip_score           — score for skipping attention in a layer
  output_caching_hit_benefit     — benefit of output caching for repeated prompts
"""
from std.math import sqrt, log, exp


fn early_exit_confidence(
    intermediate_logit_entropy: Float64, exit_threshold: Float64,
    layer_depth_fraction: Float64
) -> Float64:
    """Confidence score for early exit from transformer layer stack.

    Exit if entropy is low enough relative to layer depth reached.

    Args:
        intermediate_logit_entropy: Entropy of intermediate output logits.
        exit_threshold: Maximum entropy to trigger early exit.
        layer_depth_fraction: Fraction of layers processed (0–1).

    Returns:
        Early exit score (positive = exit now, negative = continue).
    """
    var entropy_margin = exit_threshold - intermediate_logit_entropy
    return entropy_margin * layer_depth_fraction


fn adaptive_depth_score(
    token_difficulty: Float64, available_compute_budget: Float64,
    full_model_compute: Float64
) -> Float64:
    """Score for skipping remaining layers based on token difficulty and budget.

    Args:
        token_difficulty: Estimated difficulty of this token (0–1).
        available_compute_budget: Remaining compute budget.
        full_model_compute: Full model compute requirement.

    Returns:
        Fraction of layers to use (0–1).
    """
    if full_model_compute <= 0.0:
        return 1.0
    var budget_fraction = available_compute_budget / full_model_compute
    var depth = token_difficulty * budget_fraction
    if depth > 1.0:
        return 1.0
    return depth


fn prefill_decode_split_latency(
    prefill_tokens: Float64, decode_tokens: Float64,
    prefill_throughput_tps: Float64, decode_throughput_tps: Float64
) -> Float64:
    """Total latency model for prefill/decode split serving.

    Args:
        prefill_tokens: Number of prefill (prompt) tokens.
        decode_tokens: Number of tokens to generate.
        prefill_throughput_tps: Prefill throughput (tokens/sec).
        decode_throughput_tps: Decode throughput (tokens/sec).

    Returns:
        Total estimated latency (seconds).
    """
    var prefill_time = 0.0
    var decode_time = 0.0
    if prefill_throughput_tps > 0.0:
        prefill_time = prefill_tokens / prefill_throughput_tps
    if decode_throughput_tps > 0.0:
        decode_time = decode_tokens / decode_throughput_tps
    return prefill_time + decode_time


fn async_speculation_gain(
    accepted_tokens: Float64, total_speculated: Float64,
    speculation_overhead: Float64
) -> Float64:
    """Net gain from asynchronous speculative branching.

    gain = accepted_tokens - overhead × total_speculated

    Args:
        accepted_tokens: Tokens accepted from speculative branch.
        total_speculated: Total tokens speculatively generated.
        speculation_overhead: Overhead per speculated token.

    Returns:
        Net token gain (positive = speculation helped).
    """
    return accepted_tokens - speculation_overhead * total_speculated


fn token_streaming_headroom(
    buffer_tokens: Float64, generation_rate_tps: Float64,
    consumption_rate_tps: Float64
) -> Float64:
    """Buffer headroom (seconds) before streaming starvation.

    Args:
        buffer_tokens: Tokens currently buffered for streaming.
        generation_rate_tps: Tokens being generated per second.
        consumption_rate_tps: Tokens being consumed per second.

    Returns:
        Headroom in seconds (negative = starvation).
    """
    var net_rate = generation_rate_tps - consumption_rate_tps
    if net_rate <= 0.0:
        if consumption_rate_tps <= 0.0:
            return 1e9
        return buffer_tokens / consumption_rate_tps
    return buffer_tokens / consumption_rate_tps + net_rate


fn layer_skip_quality_cost(
    layer_importance_score: Float64, n_skipped_layers: Float64,
    model_depth: Float64
) -> Float64:
    """Estimated quality loss from skipping layers.

    cost = importance × (skipped / total)²

    Args:
        layer_importance_score: Average importance of skipped layers.
        n_skipped_layers: Number of layers skipped.
        model_depth: Total model depth.

    Returns:
        Quality degradation estimate (0 = no loss).
    """
    if model_depth <= 0.0:
        return 0.0
    var skip_fraction = n_skipped_layers / model_depth
    return layer_importance_score * skip_fraction * skip_fraction


fn partial_forward_savings(
    full_forward_flops: Float64, partial_forward_flops: Float64,
    quality_degradation: Float64, quality_threshold: Float64
) -> Float64:
    """Compute savings from partial forward pass (acceptable quality loss).

    Returns 0 if quality loss is unacceptable.

    Args:
        full_forward_flops: FLOPs for full forward pass.
        partial_forward_flops: FLOPs for partial forward pass.
        quality_degradation: Quality loss from partial pass.
        quality_threshold: Maximum acceptable quality loss.

    Returns:
        FLOPs saved (0 if quality threshold violated).
    """
    if quality_degradation > quality_threshold:
        return 0.0
    return full_forward_flops - partial_forward_flops


fn kv_prefetch_overlap(
    decode_step_latency_ms: Float64, kv_load_latency_ms: Float64
) -> Float64:
    """Overlap fraction of KV prefetch with decode computation.

    Args:
        decode_step_latency_ms: Time for one decode step.
        kv_load_latency_ms: Time to prefetch next KV block.

    Returns:
        Overlap fraction (1 = fully overlapped, 0 = sequential).
    """
    if decode_step_latency_ms <= 0.0:
        return 0.0
    var overlap = decode_step_latency_ms - kv_load_latency_ms
    if overlap <= 0.0:
        return 0.0
    var fraction = overlap / decode_step_latency_ms
    if fraction > 1.0:
        return 1.0
    return fraction


fn attention_skip_score(
    layer_attention_entropy: Float64, skip_entropy_threshold: Float64,
    positional_importance: Float64
) -> Float64:
    """Score for skipping attention computation in a layer (sliding window proxy).

    Args:
        layer_attention_entropy: Entropy of attention distribution.
        skip_entropy_threshold: Entropy below which skip is safe.
        positional_importance: Importance of position (e.g. higher for recent).

    Returns:
        Skip score (positive = safe to skip, negative = must compute).
    """
    return (skip_entropy_threshold - layer_attention_entropy) * positional_importance


fn output_caching_hit_benefit(
    cache_hit_rate: Float64, full_generation_latency_ms: Float64,
    cache_lookup_latency_ms: Float64
) -> Float64:
    """Benefit of output caching for repeated/similar prompts.

    benefit = hit_rate × (generation - lookup) latency

    Args:
        cache_hit_rate: Fraction of requests served from cache.
        full_generation_latency_ms: Latency for full generation.
        cache_lookup_latency_ms: Latency for cache lookup + serve.

    Returns:
        Expected latency savings per request (ms).
    """
    return cache_hit_rate * (full_generation_latency_ms - cache_lookup_latency_ms)
