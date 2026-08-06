"""
continuous_batching.mojo — Continuous batching, admission control, streaming delivery.
Zero Python imports.

Public API:
  iteration_level_batch_size     — max tokens in one iteration
  preemption_score               — request preemption priority
  admission_control_accept       — admit request given memory budget
  chunked_prefill_chunks         — chunked prefill split count
  decode_throughput_tokens       — decode iteration throughput
  streaming_first_token_latency  — time to first token estimate
  sequence_completion_fraction   — fraction of sequences completed
  head_of_line_blocking_score    — HOL blocking severity
  beam_memory_per_request        — memory per beam search request
  batching_efficiency            — batch utilization ratio
"""
from std.math import sqrt, log, exp


def iteration_level_batch_size(
    available_kv_tokens: Float64, avg_seq_remaining: Float64
) -> Float64:
    """Maximum concurrent sequences in one decode iteration.

    batch = available_kv_tokens / avg_seq_remaining

    Args:
        available_kv_tokens: KV cache tokens available.
        avg_seq_remaining: Average remaining tokens per sequence.

    Returns:
        Maximum batch size for this iteration.
    """
    if avg_seq_remaining <= 0.0:
        return 0.0
    return Float64(Int64(available_kv_tokens / avg_seq_remaining))


def preemption_score(
    seq_priority: Float64, tokens_generated: Float64,
    kv_cache_tokens: Float64
) -> Float64:
    """Sequence preemption priority: preempt low-priority long sequences.

    score = kv_cache_tokens / (seq_priority × tokens_generated + 1)

    Higher score = more beneficial to preempt.

    Args:
        seq_priority: Request priority (higher = more important).
        tokens_generated: Tokens already generated.
        kv_cache_tokens: KV cache slots this sequence occupies.

    Returns:
        Preemption score (higher = preempt first).
    """
    var denom = seq_priority * (tokens_generated + 1.0)
    if denom <= 0.0:
        return kv_cache_tokens
    return kv_cache_tokens / denom


def admission_control_accept(
    request_kv_tokens: Float64, available_kv_tokens: Float64,
    safety_margin: Float64
) -> Float64:
    """Accept new request if sufficient KV cache available.

    Args:
        request_kv_tokens: KV tokens needed for this request.
        available_kv_tokens: Currently available KV slots.
        safety_margin: Keep this fraction of slots as reserve.

    Returns:
        1.0 if request admitted, 0.0 if rejected.
    """
    var effective_available = available_kv_tokens * (1.0 - safety_margin)
    if request_kv_tokens <= effective_available:
        return 1.0
    return 0.0


def chunked_prefill_chunks(
    prompt_len: Float64, chunk_size: Float64
) -> Float64:
    """Number of chunks for chunked prefill.

    Splits long prompts to interleave with decode for fairness.

    Args:
        prompt_len: Prompt length in tokens.
        chunk_size: Maximum tokens per prefill chunk.

    Returns:
        Number of prefill chunks.
    """
    if chunk_size <= 0.0:
        return 1.0
    return Float64(Int64((prompt_len + chunk_size - 1.0) / chunk_size))


def decode_throughput_tokens(
    batch_size: Float64, decode_latency_ms: Float64
) -> Float64:
    """Decode-phase token throughput (tokens/sec).

    Each iteration produces batch_size tokens (one per sequence).

    Args:
        batch_size: Concurrent sequences in decode batch.
        decode_latency_ms: Time per decode iteration (ms).

    Returns:
        Tokens per second.
    """
    if decode_latency_ms <= 0.0:
        return 0.0
    return batch_size / (decode_latency_ms / 1000.0)


def streaming_first_token_latency(
    prompt_len: Float64, prefill_throughput_tps: Float64
) -> Float64:
    """Time-to-first-token (TTFT) estimate.

    TTFT ≈ prompt_len / prefill_throughput

    Args:
        prompt_len: Number of input tokens.
        prefill_throughput_tps: Prefill tokens-per-second.

    Returns:
        First token latency in seconds.
    """
    if prefill_throughput_tps <= 0.0:
        return 0.0
    return prompt_len / prefill_throughput_tps


def sequence_completion_fraction(
    completed: Float64, total_running: Float64
) -> Float64:
    """Fraction of running sequences completed this iteration.

    Args:
        completed: Sequences that generated EOS this iteration.
        total_running: Total sequences in current batch.

    Returns:
        Completion rate (0–1).
    """
    if total_running <= 0.0:
        return 0.0
    return completed / total_running


def head_of_line_blocking_score(
    longest_wait_ms: Float64, avg_wait_ms: Float64
) -> Float64:
    """Head-of-line blocking severity.

    HOL = longest_wait / avg_wait (1 = no blocking, higher = worse).

    Args:
        longest_wait_ms: Maximum wait time in queue.
        avg_wait_ms: Average wait time.

    Returns:
        HOL blocking score (lower = fairer scheduling).
    """
    if avg_wait_ms <= 0.0:
        return 1.0
    return longest_wait_ms / avg_wait_ms


def beam_memory_per_request(
    beam_width: Float64, max_seq_len: Float64,
    n_layers: Float64, n_heads: Float64,
    head_dim: Float64, dtype_bytes: Float64
) -> Float64:
    """KV cache memory per request for beam search.

    memory = beam_width × kv_cache_per_sequence

    Args:
        beam_width: Number of beams.
        max_seq_len: Maximum sequence length.
        n_layers: Transformer layers.
        n_heads: KV heads.
        head_dim: Head dimension.
        dtype_bytes: Bytes per element.

    Returns:
        Total KV cache bytes for this beam search request.
    """
    var per_beam = 2.0 * max_seq_len * n_layers * n_heads * head_dim * dtype_bytes
    return beam_width * per_beam


def batching_efficiency(
    actual_compute: Float64, theoretical_max_compute: Float64
) -> Float64:
    """Batch compute utilization: actual vs maximum possible.

    Args:
        actual_compute: FLOPs actually performed.
        theoretical_max_compute: FLOPs if batch were fully packed.

    Returns:
        Efficiency ratio (0–1; 1 = perfect batching).
    """
    if theoretical_max_compute <= 0.0:
        return 0.0
    var eff = actual_compute / theoretical_max_compute
    if eff > 1.0:
        return 1.0
    return eff
