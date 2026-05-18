"""
moe_routing.mojo — Expanded MoE: dynamic gating networks and expert parallelism.
Zero Python imports.

Public API:
  noisy_top_k_gate               — noisy top-k gating (with noise)
  switch_transformer_gate        — Switch Transformer top-1 gating
  expert_parallel_shard_id       — which device holds this expert
  gshard_gate_weight             — GShard smooth top-2 gating
  expert_dropout_mask            — training-time expert dropout
  combined_jitter_noise          — gating noise for exploration
  aux_loss_coefficient           — dynamic aux loss coefficient
  expert_choice_gate             — expert-choice routing score
  cosine_router_score            — cosine-similarity-based router
  heterogeneous_expert_capacity  — variable capacity per expert
"""
from std.math import sqrt, log, exp


fn noisy_top_k_gate(
    logit: Float64, noise: Float64, epsilon: Float64
) -> Float64:
    """Noisy top-k gating: logit + noise × softplus(W_noise).

    Shazeer et al. 2017: add tunable Gaussian noise before softmax.

    Args:
        logit: Raw router logit for this expert.
        noise: Standard normal noise sample.
        epsilon: Noise scale (0.1 typical).

    Returns:
        Noisy logit.
    """
    var softplus_eps = log(1.0 + exp(epsilon))
    return logit + noise * softplus_eps


fn switch_transformer_gate(
    logit: Float64, max_logit: Float64, sum_exp: Float64
) -> Float64:
    """Switch Transformer top-1 gating: softmax probability.

    g = exp(logit - max) / Σ exp(logit_i - max)

    Args:
        logit: Router logit for this expert.
        max_logit: Maximum logit (numerical stability).
        sum_exp: Σ exp(logit_i - max_logit).

    Returns:
        Gating probability (softmax).
    """
    if sum_exp <= 0.0:
        return 0.0
    return exp(logit - max_logit) / sum_exp


fn expert_parallel_shard_id(
    expert_id: Float64, n_devices: Float64
) -> Float64:
    """Map expert to device for expert parallelism.

    device = expert_id % n_devices

    Args:
        expert_id: Expert index.
        n_devices: Number of devices (GPUs).

    Returns:
        Device ID for this expert.
    """
    if n_devices <= 0.0:
        return 0.0
    return Float64(Int64(expert_id) % Int64(n_devices))


fn gshard_gate_weight(
    gate_score: Float64, threshold: Float64, is_top1: Float64
) -> Float64:
    """GShard smooth top-2 gating: gate weight with threshold smoothing.

    For top-1 expert: weight = gate_score.
    For top-2 expert: weight = 1 - gate_score if above threshold, else 0.

    Args:
        gate_score: Softmax gate probability for this expert.
        threshold: Routing threshold for secondary expert.
        is_top1: 1.0 if this is the primary expert.

    Returns:
        Effective gate weight.
    """
    if is_top1 > 0.5:
        return gate_score
    if gate_score >= threshold:
        return 1.0 - gate_score
    return 0.0


fn expert_dropout_mask(
    expert_id: Float64, dropout_rate: Float64, random_val: Float64
) -> Float64:
    """Training-time expert dropout: drop expert with probability p.

    Args:
        expert_id: Expert index.
        dropout_rate: Probability of dropping an expert (0.1 typical).
        random_val: Uniform random value in [0, 1].

    Returns:
        1.0 if expert is active, 0.0 if dropped.
    """
    if random_val < dropout_rate:
        return 0.0
    return 1.0


fn combined_jitter_noise(
    base_logit: Float64, noise_std: Float64, noise_sample: Float64
) -> Float64:
    """Jitter noise for MoE exploration during training.

    noisy_logit = base_logit × (1 + noise_std × noise_sample)

    Args:
        base_logit: Gating logit.
        noise_std: Noise standard deviation.
        noise_sample: N(0,1) sample.

    Returns:
        Jittered logit.
    """
    return base_logit * (1.0 + noise_std * noise_sample)


fn aux_loss_coefficient(
    step: Float64, warmup_steps: Float64, target_coeff: Float64
) -> Float64:
    """Dynamic auxiliary loss coefficient: linearly warm up.

    coeff = target × min(1, step / warmup_steps)

    Args:
        step: Current training step.
        warmup_steps: Steps to reach full coefficient.
        target_coeff: Final coefficient value (0.01 typical).

    Returns:
        Current aux loss coefficient.
    """
    if warmup_steps <= 0.0:
        return target_coeff
    var ratio = step / warmup_steps
    if ratio > 1.0:
        ratio = 1.0
    return target_coeff * ratio


fn expert_choice_gate(
    token_score: Float64, capacity: Float64, n_tokens: Float64
) -> Float64:
    """Expert-choice routing: expert selects top-k tokens.

    k = capacity × n_tokens  (typically capacity_factor = 1/n_experts)

    Args:
        token_score: Affinity score of token for this expert.
        capacity: Fraction of tokens each expert processes.
        n_tokens: Total tokens.

    Returns:
        Effective capacity (tokens this expert processes).
    """
    if n_tokens <= 0.0:
        return 0.0
    return Float64(Int64(capacity * n_tokens + 0.5))


fn cosine_router_score(
    token_dot_expert: Float64, token_norm: Float64, expert_norm: Float64
) -> Float64:
    """Cosine-similarity router: route to most similar expert.

    score = (token · expert) / (||token|| × ||expert||)

    Args:
        token_dot_expert: Dot product of token and expert embeddings.
        token_norm: L2 norm of token representation.
        expert_norm: L2 norm of expert embedding.

    Returns:
        Cosine similarity routing score.
    """
    var denom = token_norm * expert_norm
    if denom <= 0.0:
        return 0.0
    return token_dot_expert / denom


fn heterogeneous_expert_capacity(
    base_capacity: Float64, expert_speed_ratio: Float64
) -> Float64:
    """Variable capacity for heterogeneous experts (different hardware).

    capacity_i = base_capacity × speed_ratio_i

    Args:
        base_capacity: Default tokens per expert.
        expert_speed_ratio: Relative speed of this expert (GPU vs CPU).

    Returns:
        Adjusted capacity for this expert.
    """
    return base_capacity * expert_speed_ratio
