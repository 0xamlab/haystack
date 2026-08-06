"""
speculative_decoding.mojo — Speculative decoding, constrained decoding, structured output.
Zero Python imports.

Public API:
  speculative_accept_prob        — token acceptance probability
  speculative_expected_tokens    — expected tokens accepted per step
  draft_model_speedup            — theoretical speedup from speculation
  json_grammar_logit_mask        — JSON grammar constraint logit mask
  structured_repair_score        — repair probability for malformed output
  constrained_beam_score         — grammar-constrained beam score
  token_healing_overlap          — token healing boundary adjustment
  watermark_green_list_bias      — LLM watermarking logit bias
  contrastive_decode_score       — contrastive decoding amateur penalty
  medusa_head_acceptance         — Medusa multi-head acceptance prob
"""
from std.math import sqrt, log, exp


def speculative_accept_prob(
    target_prob: Float64, draft_prob: Float64
) -> Float64:
    """Speculative decoding token acceptance probability.

    p_accept = min(1, p_target / p_draft)

    Args:
        target_prob: Target model probability for this token.
        draft_prob: Draft model probability for this token.

    Returns:
        Acceptance probability (0–1).
    """
    if draft_prob <= 0.0:
        return 1.0
    var ratio = target_prob / draft_prob
    if ratio > 1.0:
        return 1.0
    return ratio


def speculative_expected_tokens(
    acceptance_rate: Float64, speculation_depth: Float64
) -> Float64:
    """Expected tokens accepted per speculative step.

    E[tokens] = (1 - α^(γ+1)) / (1 - α)  where α = accept rate, γ = depth.

    Args:
        acceptance_rate: Per-token acceptance rate α.
        speculation_depth: Number of draft tokens γ.

    Returns:
        Expected accepted tokens per step.
    """
    if acceptance_rate >= 1.0:
        return speculation_depth + 1.0
    if acceptance_rate <= 0.0:
        return 1.0
    var numer = 1.0 - exp((speculation_depth + 1.0) * log(acceptance_rate))
    var denom = 1.0 - acceptance_rate
    return numer / denom


def draft_model_speedup(
    expected_tokens: Float64, target_latency_ms: Float64,
    draft_latency_ms: Float64, speculation_depth: Float64
) -> Float64:
    """Theoretical speculative decoding speedup.

    speedup = E[tokens] / (draft_lat × depth + target_lat) × target_lat

    Args:
        expected_tokens: E[accepted tokens] per speculative step.
        target_latency_ms: Target model forward pass latency.
        draft_latency_ms: Draft model forward pass latency.
        speculation_depth: Draft tokens γ.

    Returns:
        Speedup factor vs naive target-only decoding.
    """
    var total_time = draft_latency_ms * speculation_depth + target_latency_ms
    if total_time <= 0.0:
        return 1.0
    return expected_tokens * target_latency_ms / total_time


def json_grammar_logit_mask(
    token_id: Float64, is_valid_next: Float64
) -> Float64:
    """JSON grammar constraint: mask invalid next tokens.

    Args:
        token_id: Token ID to evaluate.
        is_valid_next: 1.0 if token is valid given current JSON state.

    Returns:
        0.0 if valid (no mask), -1e9 if invalid (mask out).
    """
    if is_valid_next > 0.5:
        return 0.0
    return -1e9


def structured_repair_score(
    output_validity: Float64, repair_attempts: Float64,
    max_repair_attempts: Float64
) -> Float64:
    """Probability of successfully repairing malformed structured output.

    score = validity × (1 - attempts/max_attempts)

    Args:
        output_validity: Current partial output validity (0–1).
        repair_attempts: Number of repair attempts so far.
        max_repair_attempts: Maximum allowed repair attempts.

    Returns:
        Repair confidence score.
    """
    if max_repair_attempts <= 0.0:
        return output_validity
    var attempt_penalty = repair_attempts / max_repair_attempts
    return output_validity * (1.0 - attempt_penalty)


def constrained_beam_score(
    beam_log_prob: Float64, grammar_valid: Float64,
    length: Float64, alpha: Float64
) -> Float64:
    """Grammar-constrained beam search score.

    -inf for invalid sequences; length-normalised for valid.

    Args:
        beam_log_prob: Beam accumulated log probability.
        grammar_valid: 1.0 if beam is grammatically valid.
        length: Sequence length so far.
        alpha: Length normalisation factor.

    Returns:
        Constrained beam score.
    """
    if grammar_valid < 0.5:
        return -1e9
    if length <= 0.0:
        return beam_log_prob
    return beam_log_prob / exp(alpha * log(length))


def token_healing_overlap(
    prefix_last_token: Float64, new_first_token: Float64,
    overlap_chars: Float64
) -> Float64:
    """Token healing: adjust logits at prompt/continuation boundary.

    Returns adjustment score based on character overlap.

    Args:
        prefix_last_token: Last token in prompt.
        new_first_token: First candidate continuation token.
        overlap_chars: Characters shared at boundary.

    Returns:
        Healing boost (positive = prefer this token at boundary).
    """
    return overlap_chars


def watermark_green_list_bias(
    token_id: Float64, green_list_hash: Float64,
    bias_strength: Float64
) -> Float64:
    """LLM watermarking: add logit bias to green-list tokens.

    Green list determined by hash of previous token.

    Args:
        token_id: Token to evaluate.
        green_list_hash: Hash determining green list membership.
        bias_strength: Logit bias δ for green tokens.

    Returns:
        Logit bias to add (δ if green, 0 if red).
    """
    # Simplified: token in green list if (token_id + green_list_hash) % 2 == 0
    var in_green = Float64(Int64(token_id + green_list_hash) % 2)
    if in_green == 0.0:
        return bias_strength
    return 0.0


def contrastive_decode_score(
    expert_log_prob: Float64, amateur_log_prob: Float64,
    alpha: Float64
) -> Float64:
    """Contrastive decoding: amplify expert vs amateur differences.

    score = expert_log_prob - α × amateur_log_prob
    Only applied when exp(amateur) > threshold.

    Args:
        expert_log_prob: Large model log probability.
        amateur_log_prob: Small/amateur model log probability.
        alpha: Amplification factor (0.1 typical).

    Returns:
        Contrastive score.
    """
    return expert_log_prob - alpha * amateur_log_prob


def medusa_head_acceptance(
    medusa_prob: Float64, target_prob: Float64, head_id: Float64
) -> Float64:
    """Medusa multi-head acceptance probability for head_id lookahead.

    Acceptance = min(1, p_target(t+h) / p_medusa_h(t+h))

    Args:
        medusa_prob: Medusa head probability for this token.
        target_prob: Target model probability for same token.
        head_id: Which lookahead head (unused here).

    Returns:
        Acceptance probability.
    """
    if medusa_prob <= 0.0:
        return 1.0
    var ratio = target_prob / medusa_prob
    if ratio > 1.0:
        return 1.0
    return ratio
