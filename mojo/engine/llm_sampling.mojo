"""
llm_sampling.mojo — LLM token sampling and decoding calculations. Zero Python imports.

Public API:
  temperature_scale              — logit / temperature
  top_k_threshold                — min logit to remain in top-k
  top_p_cumulative               — cumulative prob for nucleus sampling
  greedy_token_id                — argmax over logits (index)
  beam_score_update              — log-prob accumulation for beam search
  repetition_penalty_scale       — logit scaling for repeated tokens
  length_penalty                 — beam search length normalisation
  min_p_threshold                — min-p dynamic threshold
  typical_p_score                — locally typical sampling entropy score
  token_frequency_penalty        — OpenAI-style frequency penalty
"""
from std.math import log, exp, sqrt


fn temperature_scale(logit: Float64, temperature: Float64) -> Float64:
    """Scale logit by temperature: l' = l / T.

    Args:
        logit: Raw logit from model output.
        temperature: Sampling temperature (1.0 = unchanged, <1 = sharper).

    Returns:
        Temperature-scaled logit.
    """
    if temperature <= 0.0:
        return logit * 1e9  # approaching greedy
    return logit / temperature


fn top_k_threshold(
    k_th_logit: Float64
) -> Float64:
    """Logit threshold for top-k filtering.

    Tokens with logit < k_th_logit are masked to -inf.

    Args:
        k_th_logit: The k-th largest logit value.

    Returns:
        Threshold (tokens below this are filtered).
    """
    return k_th_logit


fn top_p_cumulative(
    sorted_prob: Float64, cumulative_so_far: Float64, p: Float64
) -> Float64:
    """Nucleus (top-p) sampling: include token if cumulative < p.

    Returns:
        1.0 if token should be kept, 0.0 if filtered.
    """
    if cumulative_so_far < p:
        return 1.0
    return 0.0


fn greedy_token_id(
    max_logit: Float64, current_logit: Float64, current_id: Float64
) -> Float64:
    """Check if current token is the greedy choice.

    Args:
        max_logit: Maximum logit seen so far.
        current_logit: Current token logit.
        current_id: Current token index.

    Returns:
        current_id if current_logit >= max_logit, else -1.
    """
    if current_logit >= max_logit:
        return current_id
    return -1.0


fn beam_score_update(
    current_score: Float64, next_log_prob: Float64
) -> Float64:
    """Accumulate beam search score: score += log P(token).

    Args:
        current_score: Current beam log-probability.
        next_log_prob: Log-probability of next token.

    Returns:
        Updated beam score.
    """
    return current_score + next_log_prob


fn repetition_penalty_scale(
    logit: Float64, penalty: Float64, token_appeared: Float64
) -> Float64:
    """Apply repetition penalty (Keskar et al. 2019).

    If token appeared: logit /= penalty (if > 0) or *= penalty (if < 0)

    Args:
        logit: Token logit.
        penalty: Repetition penalty factor (>1 reduces probability).
        token_appeared: 1.0 if token already in context, 0.0 otherwise.

    Returns:
        Penalised logit.
    """
    if token_appeared <= 0.0 or penalty <= 0.0:
        return logit
    if logit > 0.0:
        return logit / penalty
    return logit * penalty


fn length_penalty(
    log_prob_sum: Float64, length: Float64, alpha: Float64
) -> Float64:
    """Beam search length penalty (Wu et al. 2016 Google NMT).

    score = log_prob_sum / ((5 + length)^alpha / (5 + 1)^alpha)

    Args:
        log_prob_sum: Accumulated log-probabilities.
        length: Sequence length.
        alpha: Length penalty exponent (0 = no penalty, 1 = full).

    Returns:
        Length-normalised beam score.
    """
    var lp = pow_approx((5.0 + length) / 6.0, alpha)
    if lp <= 0.0:
        return log_prob_sum
    return log_prob_sum / lp


fn pow_approx(base: Float64, exponent: Float64) -> Float64:
    if base <= 0.0:
        return 1.0
    return exp(exponent * log(base))


fn min_p_threshold(
    max_prob: Float64, min_p: Float64
) -> Float64:
    """Min-p dynamic threshold: threshold = max_prob × min_p.

    Args:
        max_prob: Maximum token probability in distribution.
        min_p: Min-p hyperparameter (e.g. 0.05).

    Returns:
        Probability threshold (tokens below are filtered).
    """
    return max_prob * min_p


fn typical_p_score(
    token_log_prob: Float64, entropy: Float64
) -> Float64:
    """Locally typical sampling: |log p(x) + H| for each token.

    Args:
        token_log_prob: Log probability of token.
        entropy: Entropy of the full distribution.

    Returns:
        Typicality score (lower = more typical).
    """
    var diff = token_log_prob + entropy
    if diff < 0.0:
        diff = -diff
    return diff


fn token_frequency_penalty(
    logit: Float64, token_count: Float64,
    frequency_penalty: Float64, presence_penalty: Float64
) -> Float64:
    """OpenAI-style frequency + presence penalty.

    adjusted = logit - count × freq_penalty - (count > 0) × presence_penalty

    Args:
        logit: Raw token logit.
        token_count: Number of times token appeared in context.
        frequency_penalty: Per-occurrence penalty (0–2).
        presence_penalty: One-time penalty if token appeared (0–2).

    Returns:
        Adjusted logit.
    """
    var presence = 0.0
    if token_count > 0.0:
        presence = presence_penalty
    return logit - token_count * frequency_penalty - presence
