"""
inference_security.mojo — Inference-level security: injection detection, output filtering, sandboxing.
Zero Python imports.

Public API:
  prompt_injection_score         — likelihood of prompt injection attack
  token_level_safety_score       — safety score for an output token
  tool_call_validation_score     — validate tool call arguments
  data_leakage_risk_score        — risk of training data memorization leak
  jailbreak_pattern_score        — jailbreak attempt detection score
  output_toxicity_estimate       — estimated toxicity of generation
  pii_token_risk                 — PII exposure risk for a token
  sandboxed_exec_trust_score     — trust score for sandboxed tool execution
  rate_limit_violation_score     — rate limiting violation severity
  adversarial_input_score        — adversarial perturbation detection
"""
from std.math import sqrt, log, exp


fn prompt_injection_score(
    instruction_override_tokens: Float64, system_prompt_distance: Float64,
    role_switch_probability: Float64
) -> Float64:
    """Likelihood of prompt injection attack in user input.

    score = override_tokens × role_switch_prob / (system_distance + 1)

    Args:
        instruction_override_tokens: Tokens that look like instruction overrides.
        system_prompt_distance: Semantic distance from system prompt.
        role_switch_probability: Probability of role-switching directive.

    Returns:
        Injection risk score (0 = safe, higher = more suspicious).
    """
    return instruction_override_tokens * role_switch_probability / (system_prompt_distance + 1.0)


fn token_level_safety_score(
    token_harm_logit: Float64, context_harm_factor: Float64,
    refusal_trained_weight: Float64
) -> Float64:
    """Safety score for an output token (lower = safer to generate).

    Combines token harm logit with context and training signal.

    Args:
        token_harm_logit: Raw harm logit from safety classifier.
        context_harm_factor: Context-level harm amplification.
        refusal_trained_weight: Strength of refusal training signal.

    Returns:
        Harm score (0 = safe, higher = more harmful).
    """
    var raw_harm = exp(token_harm_logit) * context_harm_factor
    return raw_harm * (1.0 - refusal_trained_weight)


fn tool_call_validation_score(
    arg_type_match: Float64, arg_range_valid: Float64,
    permission_granted: Float64, rate_limit_ok: Float64
) -> Float64:
    """Validate tool call arguments — all gates must pass.

    Args:
        arg_type_match: Arguments match expected types (0 or 1).
        arg_range_valid: Arguments within allowed range (0 or 1).
        permission_granted: Caller has permission for this tool (0 or 1).
        rate_limit_ok: Within rate limit (0 or 1).

    Returns:
        Validation score (1 = valid, 0 = reject).
    """
    return arg_type_match * arg_range_valid * permission_granted * rate_limit_ok


fn data_leakage_risk_score(
    token_memorization_score: Float64, training_data_similarity: Float64,
    privacy_sensitivity: Float64
) -> Float64:
    """Risk of training data memorisation leaking in output.

    risk = memorization × similarity × sensitivity

    Args:
        token_memorization_score: Evidence of verbatim memorisation.
        training_data_similarity: Similarity to known training examples.
        privacy_sensitivity: Sensitivity of potential leaked data.

    Returns:
        Leakage risk score (higher = higher risk).
    """
    return token_memorization_score * training_data_similarity * privacy_sensitivity


fn jailbreak_pattern_score(
    roleplay_frame_depth: Float64, hypothetical_nesting: Float64,
    constraint_negation_count: Float64
) -> Float64:
    """Jailbreak attempt detection score.

    Detects roleplay framing, hypothetical nesting, constraint negation.

    Args:
        roleplay_frame_depth: Depth of roleplay/persona framing.
        hypothetical_nesting: Depth of hypothetical scenario nesting.
        constraint_negation_count: Number of constraint-negating phrases.

    Returns:
        Jailbreak risk score (higher = more suspicious).
    """
    return (roleplay_frame_depth * 0.4 + hypothetical_nesting * 0.3 +
            constraint_negation_count * 0.3)


fn output_toxicity_estimate(
    toxicity_classifier_logit: Float64, generation_temperature: Float64,
    safety_steering_strength: Float64
) -> Float64:
    """Estimated toxicity of generated output.

    Args:
        toxicity_classifier_logit: Toxicity classifier output.
        generation_temperature: Sampling temperature (higher = more random).
        safety_steering_strength: Strength of safety steering (0–1).

    Returns:
        Estimated toxicity probability (0–1).
    """
    var base_toxicity = 1.0 / (1.0 + exp(-toxicity_classifier_logit))
    var temperature_amplification = 1.0 + (generation_temperature - 1.0) * 0.2
    var steered = base_toxicity * temperature_amplification * (1.0 - safety_steering_strength)
    if steered < 0.0:
        return 0.0
    if steered > 1.0:
        return 1.0
    return steered


fn pii_token_risk(
    token_pii_classifier_prob: Float64, context_pii_density: Float64,
    user_consent_level: Float64
) -> Float64:
    """PII exposure risk for a generated token.

    risk = classifier_prob × density × (1 - consent)

    Args:
        token_pii_classifier_prob: PII classifier probability for token.
        context_pii_density: Density of PII in surrounding context.
        user_consent_level: User consent for PII processing (0–1).

    Returns:
        PII exposure risk (higher = higher risk).
    """
    return token_pii_classifier_prob * context_pii_density * (1.0 - user_consent_level)


fn sandboxed_exec_trust_score(
    tool_signature_valid: Float64, execution_timeout_ok: Float64,
    resource_limit_ok: Float64, output_schema_valid: Float64
) -> Float64:
    """Trust score for sandboxed tool execution output.

    All security gates must pass.

    Args:
        tool_signature_valid: Tool signature verification (0 or 1).
        execution_timeout_ok: Execution completed within timeout (0 or 1).
        resource_limit_ok: Resource usage within limits (0 or 1).
        output_schema_valid: Output matches expected schema (0 or 1).

    Returns:
        Trust score (1 = trusted, 0 = reject output).
    """
    return tool_signature_valid * execution_timeout_ok * resource_limit_ok * output_schema_valid


fn rate_limit_violation_score(
    requests_in_window: Float64, rate_limit: Float64,
    window_fraction_elapsed: Float64
) -> Float64:
    """Rate limiting violation severity.

    Args:
        requests_in_window: Requests made so far in window.
        rate_limit: Maximum allowed requests per window.
        window_fraction_elapsed: Fraction of rate limit window elapsed.

    Returns:
        Violation severity (0 = within limit, positive = exceeding).
    """
    if rate_limit <= 0.0:
        return 1.0
    var projected = requests_in_window / (window_fraction_elapsed + 1e-6)
    return (projected - rate_limit) / rate_limit


fn adversarial_input_score(
    input_perplexity: Float64, baseline_perplexity: Float64,
    perturbation_budget: Float64
) -> Float64:
    """Adversarial perturbation detection based on input perplexity spike.

    Args:
        input_perplexity: Perplexity of input under reference LM.
        baseline_perplexity: Expected perplexity for this domain.
        perturbation_budget: Known adversarial perturbation budget (epsilon).

    Returns:
        Adversarial suspicion score (higher = more likely adversarial).
    """
    if baseline_perplexity <= 0.0:
        return 0.0
    var ppl_ratio = input_perplexity / baseline_perplexity
    return (ppl_ratio - 1.0) * (1.0 + perturbation_budget)
