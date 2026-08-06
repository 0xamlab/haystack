"""
moe_production.mojo — Production MoE: dispatch, load balancing, expert sharding.
Zero Python imports.

Public API:
  token_drop_fraction            — tokens dropped due to capacity overflow
  expert_load_imbalance          — load imbalance across experts
  communication_efficiency_moe   — MoE all-to-all efficiency
  expert_affinity_score          — token-expert affinity for locality
  capacity_overflow_penalty      — penalty for overloaded experts
  expert_shard_memory_bytes      — memory per expert shard
  routing_entropy_balance        — routing entropy for load balance
  gradient_through_router        — router gradient (straight-through)
  expert_activation_sparsity     — fraction of active experts per token
  dynamic_capacity_factor        — adaptive capacity factor
"""
from std.math import sqrt, log, exp


def token_drop_fraction(
    tokens_to_expert: Float64, expert_capacity: Float64
) -> Float64:
    """Fraction of tokens dropped due to expert capacity overflow.

    Args:
        tokens_to_expert: Tokens routed to this expert this batch.
        expert_capacity: Maximum tokens this expert can process.

    Returns:
        Drop fraction (0 = no dropping, 1 = all dropped).
    """
    if tokens_to_expert <= expert_capacity:
        return 0.0
    return (tokens_to_expert - expert_capacity) / tokens_to_expert


def expert_load_imbalance(
    max_load: Float64, mean_load: Float64
) -> Float64:
    """Load imbalance: max / mean (1.0 = perfectly balanced).

    Args:
        max_load: Maximum tokens to any single expert.
        mean_load: Mean tokens per expert.

    Returns:
        Imbalance factor (higher = more imbalanced).
    """
    if mean_load <= 0.0:
        return 1.0
    return max_load / mean_load


def communication_efficiency_moe(
    useful_bytes: Float64, total_bytes: Float64
) -> Float64:
    """MoE all-to-all communication efficiency.

    Efficiency drops when tokens are duplicated or dropped.

    Args:
        useful_bytes: Bytes carrying actual expert inputs.
        total_bytes: Total bytes in all-to-all communication.

    Returns:
        Communication efficiency (0–1).
    """
    if total_bytes <= 0.0:
        return 1.0
    var eff = useful_bytes / total_bytes
    if eff > 1.0:
        return 1.0
    return eff


def expert_affinity_score(
    token_embedding: Float64, expert_centroid: Float64,
    history_weight: Float64
) -> Float64:
    """Token-expert affinity combining current and historical routing.

    score = token · centroid + history_weight

    Args:
        token_embedding: Token representation element.
        expert_centroid: Expert centroid embedding element.
        history_weight: Historical routing affinity bonus.

    Returns:
        Affinity score.
    """
    return token_embedding * expert_centroid + history_weight


def capacity_overflow_penalty(
    tokens_routed: Float64, capacity: Float64, penalty_factor: Float64
) -> Float64:
    """Auxiliary loss penalty for exceeding expert capacity.

    penalty = max(0, tokens - capacity)² × factor

    Args:
        tokens_routed: Tokens sent to this expert.
        capacity: Expert capacity.
        penalty_factor: Penalty strength.

    Returns:
        Overflow penalty term.
    """
    var overflow = tokens_routed - capacity
    if overflow <= 0.0:
        return 0.0
    return overflow * overflow * penalty_factor


def expert_shard_memory_bytes(
    expert_ffn_params: Float64, n_experts_per_device: Float64,
    dtype_bytes: Float64
) -> Float64:
    """Memory per device for expert sharding.

    Args:
        expert_ffn_params: Parameters per expert FFN.
        n_experts_per_device: Experts hosted on this device.
        dtype_bytes: Bytes per parameter.

    Returns:
        Expert parameter bytes on this device.
    """
    return expert_ffn_params * n_experts_per_device * dtype_bytes


def routing_entropy_balance(
    router_probs_entropy: Float64, max_entropy: Float64
) -> Float64:
    """Routing entropy as fraction of maximum: 1.0 = perfectly uniform.

    Args:
        router_probs_entropy: Entropy of routing distribution.
        max_entropy: Maximum entropy log(n_experts).

    Returns:
        Normalised routing entropy (higher = more balanced).
    """
    if max_entropy <= 0.0:
        return 1.0
    return router_probs_entropy / max_entropy


def gradient_through_router(
    upstream_grad: Float64, gate_prob: Float64
) -> Float64:
    """Straight-through gradient for discrete routing decisions.

    For the selected expert, pass gradient through gate probability.

    Args:
        upstream_grad: Gradient from expert output.
        gate_prob: Gate probability (used as STE weight).

    Returns:
        Gradient for router parameters.
    """
    return upstream_grad * gate_prob


def expert_activation_sparsity(
    active_experts: Float64, total_experts: Float64
) -> Float64:
    """Fraction of experts active for a given token.

    Args:
        active_experts: Experts selected for this token (top-k).
        total_experts: Total experts in layer.

    Returns:
        Activation sparsity (lower = sparser).
    """
    if total_experts <= 0.0:
        return 1.0
    return active_experts / total_experts


def dynamic_capacity_factor(
    target_drop_rate: Float64, current_drop_rate: Float64,
    current_factor: Float64, adjust_rate: Float64
) -> Float64:
    """Adaptively adjust capacity factor to hit target drop rate.

    If dropping too much → increase capacity.
    If under-utilizing → decrease capacity.

    Args:
        target_drop_rate: Desired token drop rate (e.g. 0.01).
        current_drop_rate: Observed token drop rate.
        current_factor: Current capacity factor.
        adjust_rate: Rate of adjustment.

    Returns:
        Updated capacity factor.
    """
    var error = current_drop_rate - target_drop_rate
    return current_factor + adjust_rate * error
