"""
generation_loop.mojo — LLM generation loop: sampling, stopping, penalties.
Zero Python imports.

Public API:
  temperature_logit_scale        — temperature-scaled logit
  top_k_accept                   — accept token if in top-k
  top_p_cumulative_accept        — nucleus sampling acceptance
  min_p_accept                   — min-p sampling acceptance
  repetition_penalty_logit       — repetition penalty adjustment
  presence_penalty_logit         — presence penalty (binary penalty)
  frequency_penalty_logit        — frequency penalty (count-scaled)
  eos_stop_score                 — stopping criterion score
  eta_sampling_accept            — eta (entropy-adaptive) sampling
  typical_sampling_accept        — locally typical sampling acceptance
"""
from std.math import sqrt, log, exp


def temperature_logit_scale(logit: Float64, temperature: Float64) -> Float64:
    """Scale logit by generation temperature.

    logit_scaled = logit / T

    Args:
        logit: Raw model logit.
        temperature: Sampling temperature (→0 = greedy, 1 = standard).

    Returns:
        Temperature-scaled logit.
    """
    if temperature <= 0.0:
        return logit * 1e9  # Greedy: extreme sharpening
    return logit / temperature


def top_k_accept(rank: Float64, k: Float64) -> Float64:
    """Accept token if its rank ≤ k (top-k sampling).

    Args:
        rank: Token rank by probability (1 = highest prob).
        k: Top-k cutoff.

    Returns:
        1.0 if accepted, 0.0 if rejected.
    """
    if rank <= k:
        return 1.0
    return 0.0


def top_p_cumulative_accept(
    cumulative_prob: Float64, token_prob: Float64, p: Float64
) -> Float64:
    """Nucleus (top-p) sampling: accept if cumulative mass < p before this token.

    Args:
        cumulative_prob: Cumulative probability mass of tokens already accepted.
        token_prob: Probability of current token.
        p: Nucleus threshold (0.9–0.95 typical).

    Returns:
        1.0 if token within nucleus, 0.0 otherwise.
    """
    if cumulative_prob < p:
        return 1.0
    return 0.0


def min_p_accept(
    token_prob: Float64, max_prob: Float64, min_p: Float64
) -> Float64:
    """Min-p sampling: accept if prob ≥ min_p × max_prob.

    Args:
        token_prob: Probability of this token.
        max_prob: Probability of the most likely token.
        min_p: Min-p threshold (0.05–0.1 typical).

    Returns:
        1.0 if accepted, 0.0 if rejected.
    """
    if token_prob >= min_p * max_prob:
        return 1.0
    return 0.0


def repetition_penalty_logit(
    logit: Float64, penalty: Float64, was_generated: Float64
) -> Float64:
    """Apply repetition penalty to previously generated token logits.

    If logit > 0: logit /= penalty; if logit < 0: logit *= penalty.

    Args:
        logit: Original logit for this token.
        penalty: Repetition penalty (1.0 = none, 1.3 typical).
        was_generated: 1.0 if token was in recent context, else 0.0.

    Returns:
        Penalised logit.
    """
    if was_generated < 0.5 or penalty <= 0.0:
        return logit
    if logit > 0.0:
        return logit / penalty
    return logit * penalty


def presence_penalty_logit(
    logit: Float64, penalty: Float64, is_present: Float64
) -> Float64:
    """Presence penalty: subtract flat penalty if token appeared at all.

    Args:
        logit: Original logit.
        penalty: Presence penalty α (−2 to 2 typical).
        is_present: 1.0 if token appeared anywhere in context.

    Returns:
        Adjusted logit.
    """
    if is_present < 0.5:
        return logit
    return logit - penalty


def frequency_penalty_logit(
    logit: Float64, penalty: Float64, token_count: Float64
) -> Float64:
    """Frequency penalty: subtract penalty × occurrence count.

    Args:
        logit: Original logit.
        penalty: Frequency penalty β (−2 to 2 typical).
        token_count: Number of times token appeared in context.

    Returns:
        Adjusted logit.
    """
    return logit - penalty * token_count


def eos_stop_score(
    eos_prob: Float64, eos_threshold: Float64
) -> Float64:
    """Stopping criterion: stop if EOS probability exceeds threshold.

    Returns 1.0 (stop) or 0.0 (continue).

    Args:
        eos_prob: Softmax probability of EOS token.
        eos_threshold: Minimum probability to stop (0.5 typical).

    Returns:
        1.0 if generation should stop.
    """
    if eos_prob >= eos_threshold:
        return 1.0
    return 0.0


def eta_sampling_accept(
    token_prob: Float64, entropy: Float64, eta: Float64
) -> Float64:
    """Eta (entropy-adaptive) sampling acceptance.

    Accept if prob ≥ min(η, √η × exp(-entropy)) / Z.
    Simplified: accept if prob ≥ η × exp(-entropy/2).

    Args:
        token_prob: Token probability.
        entropy: Current distribution entropy H.
        eta: Eta parameter (0.003 typical).

    Returns:
        1.0 if accepted.
    """
    var threshold = eta * exp(-entropy / 2.0)
    if token_prob >= threshold:
        return 1.0
    return 0.0


def typical_sampling_accept(
    token_log_prob: Float64, entropy: Float64, tau: Float64
) -> Float64:
    """Locally typical sampling: accept if |−log p − H| ≤ τ.

    Args:
        token_log_prob: Log probability of this token.
        entropy: Shannon entropy of distribution.
        tau: Typicality threshold (0.2 typical).

    Returns:
        1.0 if token is locally typical.
    """
    var surprise = -token_log_prob
    var diff = surprise - entropy
    if diff < 0.0:
        diff = -diff
    if diff <= tau:
        return 1.0
    return 0.0
