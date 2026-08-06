"""
cost_router.mojo — Cost-aware inference routing: latency/cost tradeoff, GPU/CPU, precision.
Zero Python imports.

Public API:
  request_cost_estimate          — estimated cost of serving one request
  latency_cost_tradeoff          — Pareto score balancing latency and cost
  gpu_vs_cpu_routing_score       — score for routing to GPU vs CPU
  batch_vs_single_decision       — benefit of batching vs immediate serving
  quantized_vs_full_routing      — route to quantized or full-precision model
  moe_vs_dense_routing           — MoE vs dense model selection score
  cascade_model_routing          — small-then-large model cascade score
  budget_remaining_fraction      — fraction of compute budget remaining
  sla_headroom_score             — margin between predicted and SLA latency
  cost_per_output_token          — cost normalised per output token
"""
from std.math import sqrt, log, exp


def request_cost_estimate(
    input_tokens: Float64, output_tokens: Float64,
    cost_per_input_token: Float64, cost_per_output_token: Float64
) -> Float64:
    """Estimated monetary cost of serving one request.

    Args:
        input_tokens: Input prompt length.
        output_tokens: Generated output length.
        cost_per_input_token: Cost per input token.
        cost_per_output_token: Cost per output token.

    Returns:
        Total cost estimate.
    """
    return input_tokens * cost_per_input_token + output_tokens * cost_per_output_token


def latency_cost_tradeoff(
    predicted_latency_ms: Float64, latency_budget_ms: Float64,
    predicted_cost: Float64, cost_budget: Float64
) -> Float64:
    """Pareto score balancing latency and cost vs budgets.

    score = 1 - 0.5 × (latency/budget + cost/budget)

    Args:
        predicted_latency_ms: Estimated request latency.
        latency_budget_ms: SLA latency budget.
        predicted_cost: Estimated request cost.
        cost_budget: Per-request cost budget.

    Returns:
        Tradeoff score (1 = perfect, negative = infeasible).
    """
    var lat_ratio = predicted_latency_ms / (latency_budget_ms + 1e-9)
    var cost_ratio = predicted_cost / (cost_budget + 1e-9)
    return 1.0 - 0.5 * (lat_ratio + cost_ratio)


def gpu_vs_cpu_routing_score(
    model_flops: Float64, gpu_flops: Float64,
    cpu_flops: Float64, gpu_cost_per_ms: Float64,
    cpu_cost_per_ms: Float64
) -> Float64:
    """Score for routing to GPU (positive) vs CPU (negative).

    score = (cpu_time × cpu_cost - gpu_time × gpu_cost)

    Args:
        model_flops: FLOPs required for this request.
        gpu_flops: GPU FLOP/s.
        cpu_flops: CPU FLOP/s.
        gpu_cost_per_ms: GPU cost per millisecond.
        cpu_cost_per_ms: CPU cost per millisecond.

    Returns:
        Positive = prefer GPU; negative = prefer CPU.
    """
    if gpu_flops <= 0.0 or cpu_flops <= 0.0:
        return 0.0
    var gpu_time = model_flops / gpu_flops
    var cpu_time = model_flops / cpu_flops
    return cpu_time * cpu_cost_per_ms - gpu_time * gpu_cost_per_ms


def batch_vs_single_decision(
    wait_time_ms: Float64, batch_throughput_gain: Float64,
    latency_budget_ms: Float64, queue_depth: Float64
) -> Float64:
    """Benefit of waiting to batch vs serving immediately.

    Positive = batch; negative = serve now.

    Args:
        wait_time_ms: Time to wait for more requests.
        batch_throughput_gain: Throughput multiplier from batching.
        latency_budget_ms: Latency SLA remaining.
        queue_depth: Current queue depth.

    Returns:
        Batching benefit score.
    """
    if latency_budget_ms <= wait_time_ms:
        return -1.0
    var time_slack = latency_budget_ms - wait_time_ms
    return batch_throughput_gain * time_slack / latency_budget_ms * log(queue_depth + 2.0)


def quantized_vs_full_routing(
    request_quality_requirement: Float64, quantization_quality_loss: Float64,
    speedup_factor: Float64, cost_reduction: Float64
) -> Float64:
    """Route to quantized model if quality loss is acceptable.

    score > 0 → quantized; score < 0 → full precision.

    Args:
        request_quality_requirement: Minimum quality needed (0–1).
        quantization_quality_loss: Quality degradation from quantization (0–1).
        speedup_factor: Latency speedup from quantization.
        cost_reduction: Cost reduction from quantization (0–1).

    Returns:
        Routing score (positive = use quantized).
    """
    var available_quality = 1.0 - quantization_quality_loss
    if available_quality < request_quality_requirement:
        return -1.0
    return (speedup_factor - 1.0) + cost_reduction


def moe_vs_dense_routing(
    sequence_length: Float64, active_expert_fraction: Float64,
    moe_communication_overhead: Float64, dense_flop_ratio: Float64
) -> Float64:
    """MoE vs dense model selection score.

    Positive = prefer MoE; negative = prefer dense.

    Args:
        sequence_length: Input sequence length.
        active_expert_fraction: Fraction of experts activated per token.
        moe_communication_overhead: MoE all-to-all overhead factor.
        dense_flop_ratio: Dense FLOPs / MoE active FLOPs.

    Returns:
        Score (positive = MoE better for this request).
    """
    var moe_efficiency = active_expert_fraction / (1.0 + moe_communication_overhead)
    var moe_advantage = dense_flop_ratio * moe_efficiency
    return (moe_advantage - 1.0) * log(sequence_length + 1.0)


def cascade_model_routing(
    small_model_confidence: Float64, confidence_threshold: Float64,
    small_model_cost: Float64, large_model_cost: Float64
) -> Float64:
    """Small-then-large cascade routing score.

    Returns expected cost savings from cascade vs always large.

    Args:
        small_model_confidence: Confidence of small model answer (0–1).
        confidence_threshold: Threshold to accept small model output.
        small_model_cost: Cost of small model inference.
        large_model_cost: Cost of large model inference.

    Returns:
        Expected cost saving (positive = cascade cheaper).
    """
    var accept_prob = 1.0 if small_model_confidence >= confidence_threshold else 0.0
    var cascade_cost = small_model_cost + (1.0 - accept_prob) * large_model_cost
    return large_model_cost - cascade_cost


def budget_remaining_fraction(
    total_budget: Float64, spent_budget: Float64
) -> Float64:
    """Fraction of compute/cost budget remaining.

    Args:
        total_budget: Total allocated budget.
        spent_budget: Budget consumed so far.

    Returns:
        Remaining fraction (0–1).
    """
    if total_budget <= 0.0:
        return 0.0
    var remaining = (total_budget - spent_budget) / total_budget
    if remaining < 0.0:
        return 0.0
    if remaining > 1.0:
        return 1.0
    return remaining


def sla_headroom_score(
    predicted_latency_ms: Float64, sla_latency_ms: Float64
) -> Float64:
    """Margin between predicted latency and SLA deadline.

    headroom = (SLA - predicted) / SLA

    Args:
        predicted_latency_ms: Expected serving latency.
        sla_latency_ms: SLA deadline.

    Returns:
        Headroom fraction (negative = SLA at risk).
    """
    if sla_latency_ms <= 0.0:
        return 0.0
    return (sla_latency_ms - predicted_latency_ms) / sla_latency_ms


def cost_per_output_token(
    total_cost: Float64, n_output_tokens: Float64
) -> Float64:
    """Cost normalised per generated output token.

    Args:
        total_cost: Total serving cost for this request.
        n_output_tokens: Number of output tokens generated.

    Returns:
        Cost per token.
    """
    if n_output_tokens <= 0.0:
        return total_cost
    return total_cost / n_output_tokens
