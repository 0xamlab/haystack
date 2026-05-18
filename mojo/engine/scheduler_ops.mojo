"""
scheduler_ops.mojo — Execution scheduler: queue, priority, backpressure, async math.
Zero Python imports.

Public API:
  priority_fair_score            — fair queuing priority score
  weighted_fair_queue_credit     — WFQ credit accumulation
  backpressure_load_factor       — backpressure signal from queue depth
  token_bucket_tokens            — token bucket leaky rate
  rate_limiter_wait_time         — wait time for rate limiting
  work_stealing_threshold        — work-stealing trigger condition
  request_timeout_score          — timeout priority escalation
  pipeline_stage_utilization     — pipeline stage busy fraction
  latency_sla_headroom           — SLA headroom remaining
  exponential_backoff_delay      — backoff retry delay
"""
from std.math import sqrt, log, exp


fn priority_fair_score(
    priority: Float64, wait_time: Float64,
    base_priority_weight: Float64
) -> Float64:
    """Fair queuing priority score: priority + age bonus.

    score = base_weight × priority + wait_time

    Args:
        priority: Request priority class (higher = more important).
        wait_time: Time request has been queued (ms).
        base_priority_weight: Multiplier for priority class.

    Returns:
        Combined scheduling score (higher = serve first).
    """
    return base_priority_weight * priority + wait_time


fn weighted_fair_queue_credit(
    current_credit: Float64, weight: Float64, tick: Float64
) -> Float64:
    """WFQ (Weighted Fair Queuing) virtual time credit.

    credit += weight × tick

    Args:
        current_credit: Current accumulated credit.
        weight: Queue weight (higher = more bandwidth share).
        tick: Time quantum elapsed.

    Returns:
        Updated credit.
    """
    return current_credit + weight * tick


fn backpressure_load_factor(
    queue_depth: Float64, max_queue_depth: Float64
) -> Float64:
    """Backpressure signal: queue utilization (→1 = saturated).

    Args:
        queue_depth: Current number of queued requests.
        max_queue_depth: Maximum queue capacity.

    Returns:
        Load factor (0–1; > 0.8 triggers backpressure).
    """
    if max_queue_depth <= 0.0:
        return 1.0
    var load = queue_depth / max_queue_depth
    if load > 1.0:
        return 1.0
    return load


fn token_bucket_tokens(
    current_tokens: Float64, refill_rate: Float64,
    elapsed_ms: Float64, max_tokens: Float64
) -> Float64:
    """Token bucket: compute tokens available after elapsed time.

    tokens = min(max, current + rate × time)

    Args:
        current_tokens: Current token count.
        refill_rate: Tokens added per millisecond.
        elapsed_ms: Time elapsed since last refill.
        max_tokens: Bucket capacity.

    Returns:
        Available tokens.
    """
    var new_tokens = current_tokens + refill_rate * elapsed_ms
    if new_tokens > max_tokens:
        return max_tokens
    return new_tokens


fn rate_limiter_wait_time(
    tokens_needed: Float64, current_tokens: Float64, refill_rate: Float64
) -> Float64:
    """Time to wait for token bucket to refill enough tokens.

    wait = (needed - available) / rate

    Args:
        tokens_needed: Tokens required for this request.
        current_tokens: Tokens currently available.
        refill_rate: Refill rate (tokens/ms).

    Returns:
        Wait time in ms (0 if sufficient tokens available).
    """
    var deficit = tokens_needed - current_tokens
    if deficit <= 0.0:
        return 0.0
    if refill_rate <= 0.0:
        return 1e9
    return deficit / refill_rate


fn work_stealing_threshold(
    local_queue_depth: Float64, remote_queue_depth: Float64,
    steal_ratio: Float64
) -> Float64:
    """Work-stealing trigger: 1.0 if should steal from remote.

    Args:
        local_queue_depth: Tasks in local worker queue.
        remote_queue_depth: Tasks in remote worker queue.
        steal_ratio: Steal when remote/local > ratio (2.0 typical).

    Returns:
        1.0 if work-stealing beneficial, 0.0 otherwise.
    """
    if local_queue_depth <= 0.0 and remote_queue_depth > 0.0:
        return 1.0
    if local_queue_depth <= 0.0:
        return 0.0
    if remote_queue_depth / local_queue_depth > steal_ratio:
        return 1.0
    return 0.0


fn request_timeout_score(
    elapsed_ms: Float64, timeout_ms: Float64, priority: Float64
) -> Float64:
    """Timeout-adjusted priority: escalate priority as deadline approaches.

    score = priority × (elapsed / timeout)^2

    Args:
        elapsed_ms: Time since request arrived.
        timeout_ms: Request timeout (SLA deadline).
        priority: Base request priority.

    Returns:
        Escalated priority score.
    """
    if timeout_ms <= 0.0:
        return priority
    var urgency = elapsed_ms / timeout_ms
    if urgency > 1.0:
        urgency = 1.0
    return priority * (1.0 + urgency * urgency)


fn pipeline_stage_utilization(
    busy_time_ms: Float64, total_time_ms: Float64
) -> Float64:
    """Pipeline stage utilization: fraction of time processing.

    Args:
        busy_time_ms: Time stage was actively processing.
        total_time_ms: Total elapsed time.

    Returns:
        Utilization (0–1).
    """
    if total_time_ms <= 0.0:
        return 0.0
    var util = busy_time_ms / total_time_ms
    if util > 1.0:
        return 1.0
    return util


fn latency_sla_headroom(
    sla_budget_ms: Float64, elapsed_ms: Float64, remaining_stages: Float64,
    avg_stage_latency_ms: Float64
) -> Float64:
    """SLA headroom: budget remaining minus estimated remaining work.

    Args:
        sla_budget_ms: Total latency SLA (ms).
        elapsed_ms: Time already elapsed.
        remaining_stages: Number of processing stages left.
        avg_stage_latency_ms: Average stage processing time.

    Returns:
        Headroom in ms (negative = behind SLA).
    """
    var remaining_budget = sla_budget_ms - elapsed_ms
    var remaining_work = remaining_stages * avg_stage_latency_ms
    return remaining_budget - remaining_work


fn exponential_backoff_delay(
    attempt: Float64, base_delay_ms: Float64,
    max_delay_ms: Float64, jitter: Float64
) -> Float64:
    """Exponential backoff retry delay with jitter.

    delay = min(base × 2^attempt, max) × (1 + jitter)

    Args:
        attempt: Retry attempt number (0-indexed).
        base_delay_ms: Base delay (ms).
        max_delay_ms: Maximum delay cap (ms).
        jitter: Jitter factor (0–0.5 typical).

    Returns:
        Delay before next retry (ms).
    """
    var delay = base_delay_ms * exp(attempt * 0.6931471805599453)  # × 2^attempt
    if delay > max_delay_ms:
        delay = max_delay_ms
    return delay * (1.0 + jitter)
