"""
inference_engine.mojo — Model serving / inference engine primitives.
Zero Python imports.

Public API:
  batch_padding_mask             — padding mask for batch inference
  dynamic_batching_priority      — priority score for request batching
  kv_cache_hit_ratio             — KV-cache hit rate metric
  latency_percentile_estimate    — p99 latency from mean/std
  throughput_tokens_per_sec      — tokens/sec throughput metric
  speculative_decode_accept_rate — speculative decoding acceptance
  continuous_batching_capacity   — continuous batching token budget
  quantized_inference_speedup    — INT8 inference speedup estimate
  prefill_time_estimate          — prefill phase time estimate
  decode_time_per_token          — decode step time estimate
"""
from std.math import sqrt, log, exp


def batch_padding_mask(
    token_pos: Float64, sequence_length: Float64
) -> Float64:
    """Padding mask: 1.0 if valid token, 0.0 if padding.

    Args:
        token_pos: Token position (0-indexed).
        sequence_length: Actual (non-padded) sequence length.

    Returns:
        1.0 for valid, 0.0 for padding.
    """
    if token_pos < sequence_length:
        return 1.0
    return 0.0


def dynamic_batching_priority(
    wait_time: Float64, sequence_length: Float64,
    sla_deadline: Float64
) -> Float64:
    """Priority score for dynamic batching scheduler.

    Higher score → served sooner.
    priority = wait_time / sequence_length × urgency

    Args:
        wait_time: Time request has been waiting (ms).
        sequence_length: Input sequence length (proxy for compute cost).
        sla_deadline: Time until SLA deadline (ms).

    Returns:
        Priority score (higher = more urgent).
    """
    if sequence_length <= 0.0 or sla_deadline <= 0.0:
        return wait_time
    var urgency = 1.0 / sla_deadline
    return (wait_time / sequence_length) * urgency


def kv_cache_hit_ratio(
    cache_hits: Float64, total_requests: Float64
) -> Float64:
    """KV-cache hit ratio for prefix caching.

    Args:
        cache_hits: Requests served from cache.
        total_requests: Total inference requests.

    Returns:
        Hit ratio (0–1).
    """
    if total_requests <= 0.0:
        return 0.0
    return cache_hits / total_requests


def latency_percentile_estimate(
    mean_latency: Float64, std_latency: Float64, percentile: Float64
) -> Float64:
    """Estimate latency percentile assuming log-normal distribution.

    L_p ≈ exp(μ_log + z_p × σ_log)

    Simplified: mean + z × std (normal approximation).

    Args:
        mean_latency: Mean latency (ms).
        std_latency: Std of latency (ms).
        percentile: Target percentile (0–1, e.g. 0.99 for p99).

    Returns:
        Estimated latency at given percentile (ms).
    """
    if percentile <= 0.0:
        return mean_latency
    if percentile >= 1.0:
        return mean_latency + 5.0 * std_latency
    var z = -log(1.0 - percentile) * 1.2816  # approximation
    return mean_latency + z * std_latency


def throughput_tokens_per_sec(
    batch_size: Float64, tokens_per_request: Float64, latency_ms: Float64
) -> Float64:
    """Throughput in tokens/second.

    TPS = batch_size × tokens / (latency_ms / 1000)

    Args:
        batch_size: Number of requests in batch.
        tokens_per_request: Average tokens generated per request.
        latency_ms: Total batch latency in milliseconds.

    Returns:
        Tokens per second.
    """
    if latency_ms <= 0.0:
        return 0.0
    return batch_size * tokens_per_request / (latency_ms / 1000.0)


def speculative_decode_accept_rate(
    draft_accepted: Float64, draft_tokens: Float64
) -> Float64:
    """Speculative decoding acceptance rate α.

    Higher α → more speedup from draft model.

    Args:
        draft_accepted: Tokens accepted from draft model.
        draft_tokens: Total draft tokens proposed.

    Returns:
        Acceptance rate (0–1).
    """
    if draft_tokens <= 0.0:
        return 0.0
    return draft_accepted / draft_tokens


def continuous_batching_capacity(
    gpu_memory_bytes: Float64, kv_cache_per_token_bytes: Float64,
    model_weights_bytes: Float64
) -> Float64:
    """Maximum in-flight tokens for continuous batching.

    capacity = (GPU_mem - model_weights) / kv_bytes_per_token

    Args:
        gpu_memory_bytes: Total GPU memory.
        kv_cache_per_token_bytes: KV cache memory per token.
        model_weights_bytes: Static model weight memory.

    Returns:
        Maximum concurrent tokens.
    """
    if kv_cache_per_token_bytes <= 0.0:
        return 0.0
    var available = gpu_memory_bytes - model_weights_bytes
    if available <= 0.0:
        return 0.0
    return available / kv_cache_per_token_bytes


def quantized_inference_speedup(
    fp32_flops: Float64, int8_throughput_ratio: Float64,
    memory_bandwidth_ratio: Float64
) -> Float64:
    """Estimated INT8 inference speedup over FP32.

    speedup = min(compute_ratio, memory_ratio)

    Args:
        fp32_flops: FP32 TFLOPS.
        int8_throughput_ratio: INT8/FP32 compute ratio (typically 2–4×).
        memory_bandwidth_ratio: Bandwidth ratio after quantization.

    Returns:
        Effective speedup estimate.
    """
    if int8_throughput_ratio < memory_bandwidth_ratio:
        return int8_throughput_ratio
    return memory_bandwidth_ratio


def prefill_time_estimate(
    n_tokens: Float64, n_layers: Float64,
    d_model: Float64, flops_per_second: Float64
) -> Float64:
    """Prefill phase time estimate (ms).

    FLOPs ≈ 2 × n_tokens × n_layers × d_model² × 4 (attn + FFN)
    time = FLOPs / FLOPS_per_sec × 1000

    Args:
        n_tokens: Input sequence length.
        n_layers: Number of transformer layers.
        d_model: Model hidden dimension.
        flops_per_second: Hardware throughput (FP32/INT8 FLOPS).

    Returns:
        Estimated prefill time in milliseconds.
    """
    if flops_per_second <= 0.0:
        return 0.0
    var flops = 2.0 * n_tokens * n_layers * d_model * d_model * 4.0
    return flops / flops_per_second * 1000.0


def decode_time_per_token(
    n_layers: Float64, d_model: Float64, flops_per_second: Float64
) -> Float64:
    """Decode step time per token (ms).

    FLOPs per token ≈ 2 × n_layers × d_model² × 4

    Args:
        n_layers: Transformer layers.
        d_model: Hidden dimension.
        flops_per_second: Hardware throughput.

    Returns:
        Milliseconds per generated token.
    """
    if flops_per_second <= 0.0:
        return 0.0
    var flops = 2.0 * n_layers * d_model * d_model * 4.0
    return flops / flops_per_second * 1000.0
