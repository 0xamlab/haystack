"""
mixture_of_experts.mojo — Mixture-of-Experts routing and load balancing.
Zero Python imports.

Public API:
  topk_gate_score                — top-k gating score (softmax input)
  expert_load_fraction           — fraction of tokens to an expert
  load_balance_loss              — auxiliary load balancing loss
  router_z_loss                  — router z-loss (Zoph et al. 2022)
  expert_capacity                — expert capacity with buffer
  token_dispatch_weight          — token→expert dispatch weight
  sparse_gate_entropy            — routing entropy
  soft_moe_slot_score            — Soft-MoE slot score
  expert_utilization             — expert utilization ratio
  moe_ffn_output                 — weighted expert FFN combination
"""
from std.math import sqrt, log, exp


fn topk_gate_score(logit: Float64, temperature: Float64) -> Float64:
    """Gating logit scaled by temperature before softmax.

    Args:
        logit: Raw router logit for an expert.
        temperature: Temperature (1.0 = standard softmax).

    Returns:
        Temperature-scaled logit.
    """
    if temperature <= 0.0:
        return logit
    return logit / temperature


fn expert_load_fraction(
    tokens_to_expert: Float64, total_tokens: Float64
) -> Float64:
    """Fraction of tokens dispatched to a given expert.

    Args:
        tokens_to_expert: Tokens routed to this expert.
        total_tokens: Total tokens in batch.

    Returns:
        Load fraction (0–1).
    """
    if total_tokens <= 0.0:
        return 0.0
    return tokens_to_expert / total_tokens


fn load_balance_loss(
    router_prob: Float64, load_fraction: Float64,
    n_experts: Float64
) -> Float64:
    """Switch Transformer auxiliary load balancing loss.

    L_aux = n_experts × Σ f_i × P_i

    One term (f_i × P_i); sum and multiply by n_experts outside.

    Args:
        router_prob: Mean router probability for this expert.
        load_fraction: Fraction of tokens routed here.
        n_experts: Total number of experts.

    Returns:
        One term of the load balance loss.
    """
    return n_experts * load_fraction * router_prob


fn router_z_loss(logit: Float64, n_tokens: Float64) -> Float64:
    """Router z-loss: log²(Σ exp(logit)) / n_tokens.

    This function computes the per-logit contribution assuming
    the caller sums exp(logit) externally.

    Args:
        logit: Router logit.
        n_tokens: Number of tokens (for normalisation).

    Returns:
        exp(logit) to accumulate in log-sum-exp.
    """
    if n_tokens <= 0.0:
        return 0.0
    return exp(logit)


fn expert_capacity(
    n_tokens: Float64, n_experts: Float64, capacity_factor: Float64
) -> Float64:
    """Expert capacity: ceil(capacity_factor × n_tokens / n_experts).

    Args:
        n_tokens: Sequence length × batch size.
        n_experts: Number of experts.
        capacity_factor: Buffer multiplier (1.25 typical).

    Returns:
        Maximum tokens per expert.
    """
    if n_experts <= 0.0:
        return n_tokens
    var cap = capacity_factor * n_tokens / n_experts
    return Float64(Int64(cap + 1.0))


fn token_dispatch_weight(
    gate_prob: Float64, is_selected: Float64
) -> Float64:
    """Token dispatch weight to expert: gate_prob if selected, else 0.

    Args:
        gate_prob: Softmax probability from router.
        is_selected: 1.0 if token dispatched to this expert, else 0.0.

    Returns:
        Effective dispatch weight.
    """
    if is_selected < 0.5:
        return 0.0
    return gate_prob


fn sparse_gate_entropy(probs_sum_log: Float64, n_experts: Float64) -> Float64:
    """Routing entropy: -Σ p_i log(p_i) / log(n_experts) (normalised).

    This is the per-expert contribution assuming caller sums p_i × log(p_i).

    Args:
        probs_sum_log: Accumulated Σ p_i × log(p_i).
        n_experts: Number of experts.

    Returns:
        Normalised routing entropy.
    """
    if n_experts <= 1.0:
        return 0.0
    return -probs_sum_log / log(n_experts)


fn soft_moe_slot_score(
    query_dot_phi: Float64, n_slots: Float64
) -> Float64:
    """Soft-MoE slot score: exp(q·φ) / n_slots for dispatch weights.

    Args:
        query_dot_phi: Dot product of token query with slot embedding.
        n_slots: Number of slots per expert.

    Returns:
        Unnormalised slot score.
    """
    if n_slots <= 0.0:
        return 0.0
    return exp(query_dot_phi) / n_slots


fn expert_utilization(
    active_tokens: Float64, capacity: Float64
) -> Float64:
    """Expert utilization: tokens_processed / capacity.

    Args:
        active_tokens: Tokens actually processed (not overflowed).
        capacity: Expert capacity from expert_capacity().

    Returns:
        Utilization ratio (0–1; overflow → capped to 1).
    """
    if capacity <= 0.0:
        return 0.0
    var u = active_tokens / capacity
    if u > 1.0:
        return 1.0
    return u


fn moe_ffn_output(
    expert_output: Float64, gate_weight: Float64
) -> Float64:
    """Weighted combination of expert FFN output.

    y = Σ_k gate_k × FFN_k(x) — one term contribution.

    Args:
        expert_output: Output value from one expert FFN.
        gate_weight: Gating weight for this expert.

    Returns:
        Weighted contribution to final output.
    """
    return gate_weight * expert_output
