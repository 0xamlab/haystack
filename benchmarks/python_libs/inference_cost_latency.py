"""Manual Python reference for inference_cost_latency.mojo."""

from __future__ import annotations


def _clamp_non_negative_int(value: int) -> int:
    return value if value >= 0 else 0


def _clamp_non_negative_float(value: float) -> float:
    return value if value >= 0.0 else 0.0


def _ceil_positive_ratio(numerator: int, denominator: float) -> int:
    if numerator <= 0 or denominator <= 0.0:
        return 0
    return int((float(numerator) + denominator - 1.0) / denominator)


def prompt_token_estimate(char_count: int, chars_per_token: float) -> int:
    return _ceil_positive_ratio(char_count, chars_per_token)


def completion_token_estimate(char_count: int, chars_per_token: float) -> int:
    return _ceil_positive_ratio(char_count, chars_per_token)


def kv_cache_bytes(
    batch_size: int,
    sequence_length: int,
    num_layers: int,
    hidden_size: int,
    bytes_per_element: int,
) -> float:
    safe_batch = _clamp_non_negative_int(batch_size)
    safe_sequence = _clamp_non_negative_int(sequence_length)
    safe_layers = _clamp_non_negative_int(num_layers)
    safe_hidden = _clamp_non_negative_int(hidden_size)
    safe_bytes = _clamp_non_negative_int(bytes_per_element)
    return (
        float(safe_batch)
        * float(safe_sequence)
        * float(safe_layers)
        * float(safe_hidden)
        * float(safe_bytes)
        * 2.0
    )


def attention_flops(
    batch_size: int,
    sequence_length: int,
    num_layers: int,
    num_heads: int,
    head_dim: int,
) -> float:
    safe_batch = _clamp_non_negative_int(batch_size)
    safe_sequence = _clamp_non_negative_int(sequence_length)
    safe_layers = _clamp_non_negative_int(num_layers)
    safe_heads = _clamp_non_negative_int(num_heads)
    safe_head_dim = _clamp_non_negative_int(head_dim)
    return (
        4.0
        * float(safe_batch)
        * float(safe_layers)
        * float(safe_heads)
        * float(safe_sequence)
        * float(safe_sequence)
        * float(safe_head_dim)
    )


def prefill_latency_estimate(
    prompt_tokens: int,
    tokens_per_second: float,
    fixed_overhead_ms: float,
) -> float:
    if tokens_per_second <= 0.0:
        return 0.0
    safe_prompt_tokens = _clamp_non_negative_int(prompt_tokens)
    safe_overhead = _clamp_non_negative_float(fixed_overhead_ms)
    return safe_overhead + float(safe_prompt_tokens) * 1000.0 / tokens_per_second


def decode_latency_estimate(
    completion_tokens: int,
    tokens_per_second: float,
    fixed_overhead_ms: float,
) -> float:
    if tokens_per_second <= 0.0:
        return 0.0
    safe_completion_tokens = _clamp_non_negative_int(completion_tokens)
    safe_overhead = _clamp_non_negative_float(fixed_overhead_ms)
    return safe_overhead + float(safe_completion_tokens) * 1000.0 / tokens_per_second


def request_cost_estimate(
    prompt_tokens: int,
    completion_tokens: int,
    prompt_price_per_1k: float,
    completion_price_per_1k: float,
) -> float:
    safe_prompt = _clamp_non_negative_int(prompt_tokens)
    safe_completion = _clamp_non_negative_int(completion_tokens)
    safe_prompt_price = _clamp_non_negative_float(prompt_price_per_1k)
    safe_completion_price = _clamp_non_negative_float(completion_price_per_1k)
    return (
        float(safe_prompt) * safe_prompt_price + float(safe_completion) * safe_completion_price
    ) / 1000.0


def cost_latency_frontier_score(
    cost_usd: float,
    latency_ms: float,
    cost_weight: float,
    latency_weight: float,
) -> float:
    safe_cost = _clamp_non_negative_float(cost_usd)
    safe_latency = _clamp_non_negative_float(latency_ms)
    safe_cost_weight = _clamp_non_negative_float(cost_weight)
    safe_latency_weight = _clamp_non_negative_float(latency_weight)
    return 1.0 / (1.0 + safe_cost * safe_cost_weight + safe_latency * safe_latency_weight)


def batch_efficiency_estimate(batch_size: int, saturation_batch_size: int) -> float:
    safe_batch = _clamp_non_negative_int(batch_size)
    safe_saturation = _clamp_non_negative_int(saturation_batch_size)
    if safe_batch == 0 or safe_saturation == 0:
        return 0.0
    ratio = float(safe_batch) / float(safe_saturation)
    return 1.0 if ratio > 1.0 else ratio


def queue_delay_estimate(queue_depth: int, service_rate_rps: float, concurrency: int) -> float:
    safe_queue = _clamp_non_negative_int(queue_depth)
    safe_concurrency = _clamp_non_negative_int(concurrency)
    if safe_queue == 0 or safe_concurrency == 0 or service_rate_rps <= 0.0:
        return 0.0
    return float(safe_queue) * 1000.0 / (service_rate_rps * float(safe_concurrency))


def speculative_decode_gain_estimate(
    acceptance_rate: float,
    draft_tokens_per_step: int,
    base_decode_tps: float,
    draft_decode_tps: float,
) -> float:
    safe_acceptance = min(1.0, max(0.0, acceptance_rate))
    safe_draft_tokens = _clamp_non_negative_int(draft_tokens_per_step)
    if safe_draft_tokens == 0 or base_decode_tps <= 0.0 or draft_decode_tps <= 0.0:
        return 0.0
    accepted_tokens = safe_acceptance * float(safe_draft_tokens)
    if accepted_tokens <= 0.0:
        return 0.0
    baseline_seconds = accepted_tokens / base_decode_tps
    speculative_seconds = (
        float(safe_draft_tokens) / draft_decode_tps
        + (float(safe_draft_tokens) - accepted_tokens) / base_decode_tps
    )
    if speculative_seconds <= 0.0:
        return 0.0
    return baseline_seconds / speculative_seconds
