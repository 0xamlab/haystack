"""
execution_planner.mojo — Global execution planner: batching, fusion, device placement, KV policy.
Zero Python imports.

Public API:
  fusion_opportunity_score       — score for fusing two adjacent ops
  device_placement_score         — score for placing op on device type
  kv_policy_eviction_priority    — KV cache eviction priority score
  batching_strategy_score        — score for batching strategy selection
  scheduling_priority_score      — global scheduling priority
  prefetch_benefit_estimate      — estimated benefit of prefetching weights
  graph_rewrite_gain             — expected gain from graph rewrite rule
  memory_placement_affinity      — affinity of tensor to memory tier
  pipeline_depth_optimal         — optimal pipeline depth for throughput
  adaptive_batch_size            — dynamically adapt batch size to load
"""
from std.math import sqrt, log, exp


fn fusion_opportunity_score(
    op_a_flops: Float64, op_b_flops: Float64,
    memory_traffic_saved: Float64
) -> Float64:
    """Score for fusing two adjacent ops (higher = more beneficial).

    score = memory_saved / (op_a_flops + op_b_flops)

    Args:
        op_a_flops: FLOPs of first op.
        op_b_flops: FLOPs of second op.
        memory_traffic_saved: Bytes of memory traffic eliminated.

    Returns:
        Fusion benefit score.
    """
    var total_flops = op_a_flops + op_b_flops
    if total_flops <= 0.0:
        return 0.0
    return memory_traffic_saved / total_flops


fn device_placement_score(
    op_arithmetic_intensity: Float64, device_ridge_point: Float64,
    device_peak_flops: Float64
) -> Float64:
    """Score for placing op on a device (roofline-based).

    Higher score = device is better fit for this op's intensity.

    Args:
        op_arithmetic_intensity: Op FLOPs per byte.
        device_ridge_point: Device ridge point (peak_flops / peak_bandwidth).
        device_peak_flops: Device peak FLOP/s.

    Returns:
        Placement suitability score.
    """
    if device_ridge_point <= 0.0:
        return 0.0
    var utilization = op_arithmetic_intensity / device_ridge_point
    if utilization > 1.0:
        utilization = 1.0
    return utilization * device_peak_flops


fn kv_policy_eviction_priority(
    last_access_step: Float64, current_step: Float64,
    attention_score: Float64, seq_remaining: Float64
) -> Float64:
    """KV cache eviction priority (lower = evict first).

    Combines recency, attention importance, and remaining sequence length.

    Args:
        last_access_step: Step when this KV block was last accessed.
        current_step: Current decoding step.
        attention_score: Maximum attention weight this block received.
        seq_remaining: Estimated remaining tokens to generate.

    Returns:
        Retention priority (higher = keep longer).
    """
    var staleness = current_step - last_access_step + 1.0
    return attention_score * seq_remaining / staleness


fn batching_strategy_score(
    request_latency_budget_ms: Float64, current_batch_size: Float64,
    throughput_gain_per_request: Float64, latency_cost_per_request: Float64
) -> Float64:
    """Score for including one more request in batch.

    Positive = batch it; negative = send immediately.

    Args:
        request_latency_budget_ms: SLA latency budget for request.
        current_batch_size: Current batch size.
        throughput_gain_per_request: Throughput improvement from batching.
        latency_cost_per_request: Added latency from batching.

    Returns:
        Batching benefit score.
    """
    if latency_cost_per_request >= request_latency_budget_ms:
        return -1.0
    return throughput_gain_per_request - latency_cost_per_request / request_latency_budget_ms


fn scheduling_priority_score(
    queue_wait_ms: Float64, sla_budget_ms: Float64,
    request_value: Float64, estimated_compute_ms: Float64
) -> Float64:
    """Global scheduling priority: urgency × value / cost.

    Args:
        queue_wait_ms: Time request has waited in queue.
        sla_budget_ms: Total SLA latency budget.
        request_value: Business value of this request.
        estimated_compute_ms: Estimated compute time.

    Returns:
        Scheduling priority score (higher = run first).
    """
    if sla_budget_ms <= 0.0 or estimated_compute_ms <= 0.0:
        return 0.0
    var urgency = (queue_wait_ms + 1.0) / sla_budget_ms
    return urgency * request_value / estimated_compute_ms


fn prefetch_benefit_estimate(
    weight_bytes: Float64, bandwidth_bytes_per_ms: Float64,
    compute_ms_until_needed: Float64
) -> Float64:
    """Estimated benefit of prefetching weights ahead of time.

    benefit = max(0, compute_gap - load_time) / compute_gap

    Args:
        weight_bytes: Bytes to prefetch.
        bandwidth_bytes_per_ms: Memory bandwidth.
        compute_ms_until_needed: Time until weights are needed.

    Returns:
        Prefetch benefit (0 = no benefit, 1 = full overlap).
    """
    if bandwidth_bytes_per_ms <= 0.0 or compute_ms_until_needed <= 0.0:
        return 0.0
    var load_time_ms = weight_bytes / bandwidth_bytes_per_ms
    var benefit = (compute_ms_until_needed - load_time_ms) / compute_ms_until_needed
    if benefit < 0.0:
        return 0.0
    if benefit > 1.0:
        return 1.0
    return benefit


fn graph_rewrite_gain(
    original_flops: Float64, rewritten_flops: Float64,
    original_memory: Float64, rewritten_memory: Float64,
    flop_weight: Float64
) -> Float64:
    """Expected gain from applying a graph rewrite rule.

    gain = flop_weight × (1 - rewritten/original_flops) +
           (1 - flop_weight) × (1 - rewritten/original_memory)

    Args:
        original_flops: FLOPs before rewrite.
        rewritten_flops: FLOPs after rewrite.
        original_memory: Memory traffic before rewrite.
        rewritten_memory: Memory traffic after rewrite.
        flop_weight: Weight given to FLOPs vs memory (0–1).

    Returns:
        Estimated gain (positive = improvement).
    """
    var flop_gain = 0.0
    var mem_gain = 0.0
    if original_flops > 0.0:
        flop_gain = 1.0 - rewritten_flops / original_flops
    if original_memory > 0.0:
        mem_gain = 1.0 - rewritten_memory / original_memory
    return flop_weight * flop_gain + (1.0 - flop_weight) * mem_gain


fn memory_placement_affinity(
    access_frequency: Float64, tensor_bytes: Float64,
    tier_bandwidth: Float64, tier_capacity: Float64
) -> Float64:
    """Affinity of tensor to a memory tier (HBM vs DRAM vs NVMe).

    affinity = access_frequency × bandwidth / (bytes × capacity)

    Args:
        access_frequency: Accesses per second.
        tensor_bytes: Tensor size in bytes.
        tier_bandwidth: Bandwidth of target tier (bytes/s).
        tier_capacity: Capacity of target tier (bytes).

    Returns:
        Placement affinity score (higher = place here).
    """
    if tensor_bytes <= 0.0 or tier_capacity <= 0.0:
        return 0.0
    return access_frequency * tier_bandwidth / (tensor_bytes * tier_capacity)


fn pipeline_depth_optimal(
    stage_latency_ms: Float64, bubble_fraction: Float64,
    n_microbatches: Float64
) -> Float64:
    """Optimal pipeline depth that maximises throughput given bubble overhead.

    throughput ∝ (1 - bubble) / stage_latency

    Args:
        stage_latency_ms: Latency of one pipeline stage.
        bubble_fraction: Fraction of time wasted in pipeline bubble.
        n_microbatches: Micro-batches in flight.

    Returns:
        Effective throughput score (higher = better pipeline config).
    """
    if stage_latency_ms <= 0.0:
        return 0.0
    var useful = 1.0 - bubble_fraction
    if useful < 0.0:
        useful = 0.0
    return useful * n_microbatches / stage_latency_ms


fn adaptive_batch_size(
    current_batch: Float64, gpu_utilization: Float64,
    target_utilization: Float64, max_batch: Float64,
    adjust_rate: Float64
) -> Float64:
    """Dynamically adapt batch size to hit target GPU utilization.

    Args:
        current_batch: Current batch size.
        gpu_utilization: Observed GPU utilization (0–1).
        target_utilization: Target GPU utilization.
        max_batch: Maximum allowed batch size.
        adjust_rate: Rate of adjustment.

    Returns:
        New recommended batch size.
    """
    var error = target_utilization - gpu_utilization
    var new_batch = current_batch + adjust_rate * error * current_batch
    if new_batch < 1.0:
        return 1.0
    if new_batch > max_batch:
        return max_batch
    return new_batch
