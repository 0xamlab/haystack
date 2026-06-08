"""
inference_cost_latency.mojo — deterministic LLM serving cost and latency estimates.

Public API:
  prompt_token_estimate          — ceil(char_count / chars_per_token)
  completion_token_estimate      — ceil(char_count / chars_per_token)
  kv_cache_bytes                 — approximate KV cache footprint in bytes
  attention_flops                — approximate dense attention FLOP count
  prefill_latency_estimate       — prefill latency in ms from token throughput
  decode_latency_estimate        — decode latency in ms from token throughput
  request_cost_estimate          — total USD estimate from prompt/completion prices
  cost_latency_frontier_score    — scalar score favoring lower cost and latency
  batch_efficiency_estimate      — utilization ratio against a saturation batch size
  queue_delay_estimate           — queueing delay in ms from depth and service rate
  speculative_decode_gain_estimate — estimated speculative decoding speedup factor
"""


fn _clamp_non_negative_int(value: Int) -> Int:
    if value < 0:
        return 0
    return value


fn _clamp_non_negative_float(value: Float64) -> Float64:
    if value < 0.0:
        return 0.0
    return value


fn _ceil_positive_ratio(numerator: Int, denominator: Float64) -> Int:
    if numerator <= 0 or denominator <= 0.0:
        return 0
    return Int((Float64(numerator) + denominator - 1.0) / denominator)


fn prompt_token_estimate(char_count: Int, chars_per_token: Float64) -> Int:
    return _ceil_positive_ratio(char_count, chars_per_token)


fn completion_token_estimate(char_count: Int, chars_per_token: Float64) -> Int:
    return _ceil_positive_ratio(char_count, chars_per_token)


fn kv_cache_bytes(
    batch_size: Int,
    sequence_length: Int,
    num_layers: Int,
    hidden_size: Int,
    bytes_per_element: Int,
) -> Float64:
    var safe_batch = _clamp_non_negative_int(batch_size)
    var safe_sequence = _clamp_non_negative_int(sequence_length)
    var safe_layers = _clamp_non_negative_int(num_layers)
    var safe_hidden = _clamp_non_negative_int(hidden_size)
    var safe_bytes = _clamp_non_negative_int(bytes_per_element)
    return (
        Float64(safe_batch)
        * Float64(safe_sequence)
        * Float64(safe_layers)
        * Float64(safe_hidden)
        * Float64(safe_bytes)
        * 2.0
    )


fn attention_flops(
    batch_size: Int,
    sequence_length: Int,
    num_layers: Int,
    num_heads: Int,
    head_dim: Int,
) -> Float64:
    var safe_batch = _clamp_non_negative_int(batch_size)
    var safe_sequence = _clamp_non_negative_int(sequence_length)
    var safe_layers = _clamp_non_negative_int(num_layers)
    var safe_heads = _clamp_non_negative_int(num_heads)
    var safe_head_dim = _clamp_non_negative_int(head_dim)
    return (
        4.0
        * Float64(safe_batch)
        * Float64(safe_layers)
        * Float64(safe_heads)
        * Float64(safe_sequence)
        * Float64(safe_sequence)
        * Float64(safe_head_dim)
    )


fn prefill_latency_estimate(
    prompt_tokens: Int,
    tokens_per_second: Float64,
    fixed_overhead_ms: Float64,
) -> Float64:
    if tokens_per_second <= 0.0:
        return 0.0
    var safe_prompt_tokens = _clamp_non_negative_int(prompt_tokens)
    var safe_overhead = _clamp_non_negative_float(fixed_overhead_ms)
    return safe_overhead + Float64(safe_prompt_tokens) * 1000.0 / tokens_per_second


fn decode_latency_estimate(
    completion_tokens: Int,
    tokens_per_second: Float64,
    fixed_overhead_ms: Float64,
) -> Float64:
    if tokens_per_second <= 0.0:
        return 0.0
    var safe_completion_tokens = _clamp_non_negative_int(completion_tokens)
    var safe_overhead = _clamp_non_negative_float(fixed_overhead_ms)
    return safe_overhead + Float64(safe_completion_tokens) * 1000.0 / tokens_per_second


fn request_cost_estimate(
    prompt_tokens: Int,
    completion_tokens: Int,
    prompt_price_per_1k: Float64,
    completion_price_per_1k: Float64,
) -> Float64:
    var safe_prompt = _clamp_non_negative_int(prompt_tokens)
    var safe_completion = _clamp_non_negative_int(completion_tokens)
    var safe_prompt_price = _clamp_non_negative_float(prompt_price_per_1k)
    var safe_completion_price = _clamp_non_negative_float(completion_price_per_1k)
    return (
        Float64(safe_prompt) * safe_prompt_price
        + Float64(safe_completion) * safe_completion_price
    ) / 1000.0


fn cost_latency_frontier_score(
    cost_usd: Float64,
    latency_ms: Float64,
    cost_weight: Float64,
    latency_weight: Float64,
) -> Float64:
    var safe_cost = _clamp_non_negative_float(cost_usd)
    var safe_latency = _clamp_non_negative_float(latency_ms)
    var safe_cost_weight = _clamp_non_negative_float(cost_weight)
    var safe_latency_weight = _clamp_non_negative_float(latency_weight)
    return 1.0 / (1.0 + safe_cost * safe_cost_weight + safe_latency * safe_latency_weight)


fn batch_efficiency_estimate(batch_size: Int, saturation_batch_size: Int) -> Float64:
    var safe_batch = _clamp_non_negative_int(batch_size)
    var safe_saturation = _clamp_non_negative_int(saturation_batch_size)
    if safe_batch == 0 or safe_saturation == 0:
        return 0.0
    var ratio = Float64(safe_batch) / Float64(safe_saturation)
    if ratio > 1.0:
        return 1.0
    return ratio


fn queue_delay_estimate(queue_depth: Int, service_rate_rps: Float64, concurrency: Int) -> Float64:
    var safe_queue = _clamp_non_negative_int(queue_depth)
    var safe_concurrency = _clamp_non_negative_int(concurrency)
    if safe_queue == 0 or safe_concurrency == 0 or service_rate_rps <= 0.0:
        return 0.0
    return Float64(safe_queue) * 1000.0 / (service_rate_rps * Float64(safe_concurrency))


fn speculative_decode_gain_estimate(
    acceptance_rate: Float64,
    draft_tokens_per_step: Int,
    base_decode_tps: Float64,
    draft_decode_tps: Float64,
) -> Float64:
    var safe_acceptance = acceptance_rate
    if safe_acceptance < 0.0:
        safe_acceptance = 0.0
    if safe_acceptance > 1.0:
        safe_acceptance = 1.0
    var safe_draft_tokens = _clamp_non_negative_int(draft_tokens_per_step)
    if safe_draft_tokens == 0 or base_decode_tps <= 0.0 or draft_decode_tps <= 0.0:
        return 0.0
    var accepted_tokens = safe_acceptance * Float64(safe_draft_tokens)
    if accepted_tokens <= 0.0:
        return 0.0
    var baseline_seconds = accepted_tokens / base_decode_tps
    var speculative_seconds = (
        Float64(safe_draft_tokens) / draft_decode_tps
        + (Float64(safe_draft_tokens) - accepted_tokens) / base_decode_tps
    )
    if speculative_seconds <= 0.0:
        return 0.0
    return baseline_seconds / speculative_seconds
