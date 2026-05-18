"""
observability.mojo — Per-op latency, memory pressure, throughput, and drift metrics.
Zero Python imports.

Public API:
  p99_latency_estimate           — p99 latency from histogram
  memory_pressure_score          — GPU memory pressure signal
  token_throughput_ema           — EMA tokens/sec tracking
  cache_miss_rate                — cache miss rate from counters
  batch_queue_wait_percentile    — queue wait time distribution
  gpu_utilization_rolling        — rolling GPU utilization
  request_success_rate           — rolling request success rate
  model_drift_alert_score        — composite drift alert signal
  cost_per_token_rolling         — rolling cost per output token
  health_check_score             — system health composite score
"""
from std.math import sqrt, log, exp


fn p99_latency_estimate(
    mean_latency: Float64, std_latency: Float64
) -> Float64:
    """P99 latency estimate assuming log-normal distribution.

    p99 ≈ mean + 2.326 × std  (normal approximation)

    Args:
        mean_latency: Mean request latency (ms).
        std_latency: Standard deviation (ms).

    Returns:
        Estimated p99 latency (ms).
    """
    return mean_latency + 2.326 * std_latency


fn memory_pressure_score(
    used_bytes: Float64, total_bytes: Float64,
    fragmentation: Float64
) -> Float64:
    """GPU memory pressure: utilization + fragmentation penalty.

    score = (used/total) + fragmentation × 0.2

    Args:
        used_bytes: GPU memory currently used.
        total_bytes: Total GPU memory.
        fragmentation: Fragmentation ratio (0–1).

    Returns:
        Pressure score (0–1; > 0.9 = critical).
    """
    if total_bytes <= 0.0:
        return 1.0
    var util = used_bytes / total_bytes
    if util > 1.0:
        util = 1.0
    var score = util + fragmentation * 0.2
    if score > 1.0:
        return 1.0
    return score


fn token_throughput_ema(
    current_ema: Float64, new_tokens: Float64,
    elapsed_ms: Float64, alpha: Float64
) -> Float64:
    """EMA tokens/sec tracking.

    new_rate = new_tokens / elapsed_ms × 1000
    ema_t = α × new_rate + (1-α) × ema_{t-1}

    Args:
        current_ema: Current EMA tokens/sec.
        new_tokens: Tokens generated in this interval.
        elapsed_ms: Interval duration (ms).
        alpha: EMA smoothing factor.

    Returns:
        Updated EMA tokens/sec.
    """
    if elapsed_ms <= 0.0:
        return current_ema
    var new_rate = new_tokens / elapsed_ms * 1000.0
    return alpha * new_rate + (1.0 - alpha) * current_ema


fn cache_miss_rate(
    total_accesses: Float64, cache_misses: Float64
) -> Float64:
    """Cache miss rate: misses / total accesses.

    Args:
        total_accesses: Total cache lookups.
        cache_misses: Lookups that missed the cache.

    Returns:
        Miss rate (0–1).
    """
    if total_accesses <= 0.0:
        return 0.0
    return cache_misses / total_accesses


fn batch_queue_wait_percentile(
    mean_wait: Float64, std_wait: Float64, percentile: Float64
) -> Float64:
    """Queue wait time percentile estimate.

    Args:
        mean_wait: Mean queue wait time (ms).
        std_wait: Std of wait times (ms).
        percentile: Target percentile (0–1).

    Returns:
        Estimated wait time at this percentile (ms).
    """
    if percentile <= 0.0:
        return 0.0
    if percentile >= 1.0:
        return mean_wait + 4.0 * std_wait
    var z = -log(1.0 - percentile + 1e-10) * 1.2816
    return mean_wait + z * std_wait


fn gpu_utilization_rolling(
    current_util: Float64, new_sample: Float64, alpha: Float64
) -> Float64:
    """Rolling EMA GPU SM utilization (0–1).

    Args:
        current_util: Current rolling utilization.
        new_sample: New utilization sample.
        alpha: EMA alpha.

    Returns:
        Updated rolling utilization.
    """
    return alpha * new_sample + (1.0 - alpha) * current_util


fn request_success_rate(
    successes: Float64, total_requests: Float64
) -> Float64:
    """Rolling request success rate.

    Args:
        successes: Successful requests.
        total_requests: Total requests handled.

    Returns:
        Success rate (0–1).
    """
    if total_requests <= 0.0:
        return 1.0
    return successes / total_requests


fn model_drift_alert_score(
    psi_score: Float64, accuracy_drop: Float64,
    calibration_ece: Float64
) -> Float64:
    """Composite model drift alert score.

    alert = w1×PSI + w2×acc_drop + w3×ECE
    > 0.5 → alert; > 1.0 → critical

    Args:
        psi_score: Population stability index.
        accuracy_drop: Fractional accuracy reduction.
        calibration_ece: Expected calibration error.

    Returns:
        Composite drift score.
    """
    return 0.4 * psi_score + 0.4 * accuracy_drop + 0.2 * calibration_ece


fn cost_per_token_rolling(
    current_cpt: Float64, new_cost: Float64,
    new_tokens: Float64, alpha: Float64
) -> Float64:
    """Rolling cost per output token ($).

    Args:
        current_cpt: Current rolling cost/token.
        new_cost: Cost of latest batch ($).
        new_tokens: Tokens in latest batch.
        alpha: EMA smoothing.

    Returns:
        Updated rolling cost/token.
    """
    if new_tokens <= 0.0:
        return current_cpt
    var new_rate = new_cost / new_tokens
    return alpha * new_rate + (1.0 - alpha) * current_cpt


fn health_check_score(
    memory_pressure: Float64, gpu_util: Float64,
    error_rate: Float64, queue_depth_ratio: Float64
) -> Float64:
    """Composite system health score (1.0 = fully healthy).

    score = 1 - (w1×mem_pressure + w2×error_rate + w3×queue_ratio)

    Args:
        memory_pressure: Memory pressure score (0–1).
        gpu_util: GPU utilization (0–1; high is good).
        error_rate: Request error rate (0–1).
        queue_depth_ratio: Queue saturation (0–1).

    Returns:
        Health score (0–1; lower = less healthy).
    """
    var issues = 0.3 * memory_pressure + 0.4 * error_rate + 0.3 * queue_depth_ratio
    var health = 1.0 - issues
    if health < 0.0:
        return 0.0
    return health
