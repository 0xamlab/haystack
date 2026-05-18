"""
security_governance.mojo — Model provenance, audit, policy, tenant isolation.
Zero Python imports.

Public API:
  model_provenance_hash          — weight + config hash for provenance
  prompt_policy_score            — policy violation severity score
  output_safety_score            — output toxicity/safety estimate
  tenant_quota_remaining         — per-tenant rate limit remaining
  audit_log_hash                 — tamper-evident audit chain hash
  pii_sensitivity_score          — PII detection confidence
  differential_privacy_noise     — DP Gaussian noise magnitude
  permission_access_check        — RBAC permission check score
  data_retention_decay           — time-based data retention score
  governance_compliance_score    — composite compliance metric
"""
from std.math import sqrt, log, exp


fn model_provenance_hash(
    weight_hash: Float64, config_hash: Float64,
    dataset_hash: Float64, step: Float64
) -> Float64:
    """Composite model provenance hash for lineage tracking.

    hash = weight_hash × p1 + config_hash × p2 + dataset_hash + step

    Args:
        weight_hash: Hash of model weights.
        config_hash: Hash of training config.
        dataset_hash: Hash of training dataset version.
        step: Training step at checkpoint.

    Returns:
        Combined provenance hash.
    """
    var p1 = 1000003.0
    var p2 = 999983.0
    return weight_hash * p1 + config_hash * p2 + dataset_hash + step


fn prompt_policy_score(
    toxicity_signal: Float64, jailbreak_signal: Float64,
    pii_signal: Float64
) -> Float64:
    """Policy violation severity: composite input screening score.

    score > 0.5 → flag for review; > 0.8 → block.

    Args:
        toxicity_signal: Toxicity classifier score (0–1).
        jailbreak_signal: Jailbreak pattern match score (0–1).
        pii_signal: PII presence score (0–1).

    Returns:
        Violation severity score (0–1).
    """
    var score = 0.4 * toxicity_signal + 0.4 * jailbreak_signal + 0.2 * pii_signal
    if score > 1.0:
        return 1.0
    return score


fn output_safety_score(
    toxicity: Float64, hallucination_risk: Float64,
    factual_consistency: Float64
) -> Float64:
    """Output safety composite: lower = safer.

    score = 0.5 × toxicity + 0.3 × hallucination + 0.2 × (1 - factual)

    Args:
        toxicity: Output toxicity score (0–1).
        hallucination_risk: Hallucination probability estimate.
        factual_consistency: Factual accuracy score (0–1; higher = better).

    Returns:
        Safety risk score (0–1; higher = more risky).
    """
    var score = 0.5 * toxicity + 0.3 * hallucination_risk + 0.2 * (1.0 - factual_consistency)
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


fn tenant_quota_remaining(
    quota_tokens: Float64, used_tokens: Float64,
    quota_period_ms: Float64, elapsed_ms: Float64
) -> Float64:
    """Per-tenant token quota remaining in current period.

    Args:
        quota_tokens: Total tokens allowed per period.
        used_tokens: Tokens used so far this period.
        quota_period_ms: Quota period length (ms).
        elapsed_ms: Time elapsed in current period (ms).

    Returns:
        Remaining token quota.
    """
    var remaining = quota_tokens - used_tokens
    if remaining < 0.0:
        return 0.0
    return remaining


fn audit_log_hash(
    prev_hash: Float64, event_type: Float64,
    timestamp: Float64, tenant_id: Float64
) -> Float64:
    """Tamper-evident audit log chain hash.

    hash_n = hash(hash_{n-1} || event || timestamp || tenant)

    Args:
        prev_hash: Previous entry hash (chain).
        event_type: Event type code.
        timestamp: Unix timestamp.
        tenant_id: Tenant identifier.

    Returns:
        New chain hash entry.
    """
    var prime = 1000003.0
    return prev_hash * prime + event_type * 997.0 + timestamp + tenant_id


fn pii_sensitivity_score(
    n_email_matches: Float64, n_phone_matches: Float64,
    n_ssn_matches: Float64, n_credit_card_matches: Float64
) -> Float64:
    """PII sensitivity score based on pattern match counts.

    score = clipped weighted sum of PII signal counts.

    Args:
        n_email_matches: Email address pattern matches.
        n_phone_matches: Phone number matches.
        n_ssn_matches: SSN pattern matches.
        n_credit_card_matches: Credit card number matches.

    Returns:
        PII sensitivity score (0–1).
    """
    var score = (n_email_matches * 0.2 + n_phone_matches * 0.2 +
                 n_ssn_matches * 0.4 + n_credit_card_matches * 0.4)
    if score > 1.0:
        return 1.0
    return score


fn differential_privacy_noise(
    sensitivity: Float64, epsilon: Float64, delta: Float64
) -> Float64:
    """Gaussian DP noise standard deviation.

    σ = sensitivity × sqrt(2 log(1.25/δ)) / ε

    Args:
        sensitivity: L2 sensitivity of query.
        epsilon: Privacy parameter ε.
        delta: Failure probability δ.

    Returns:
        Required noise standard deviation for (ε,δ)-DP.
    """
    if epsilon <= 0.0 or delta <= 0.0:
        return 1e9
    return sensitivity * sqrt(2.0 * log(1.25 / delta)) / epsilon


fn permission_access_check(
    user_role_level: Float64, resource_required_level: Float64,
    time_based_restriction: Float64
) -> Float64:
    """RBAC permission check: 1.0 if access granted.

    Args:
        user_role_level: User's permission level (higher = more access).
        resource_required_level: Resource's minimum required level.
        time_based_restriction: 1.0 if time restriction active (block).

    Returns:
        1.0 if access permitted, 0.0 if denied.
    """
    if time_based_restriction > 0.5:
        return 0.0
    if user_role_level >= resource_required_level:
        return 1.0
    return 0.0


fn data_retention_decay(
    data_age_days: Float64, retention_days: Float64
) -> Float64:
    """Data retention score: 1.0 = retain, 0.0 = should delete.

    Linearly decays from 1 to 0 as data approaches retention limit.

    Args:
        data_age_days: Age of data record in days.
        retention_days: Maximum retention period.

    Returns:
        Retention score (0 = delete, 1 = fully within retention).
    """
    if retention_days <= 0.0:
        return 0.0
    var ratio = data_age_days / retention_days
    if ratio >= 1.0:
        return 0.0
    return 1.0 - ratio


fn governance_compliance_score(
    data_lineage_coverage: Float64, audit_completeness: Float64,
    policy_adherence: Float64, privacy_budget_remaining: Float64
) -> Float64:
    """Composite governance compliance score (1.0 = fully compliant).

    Args:
        data_lineage_coverage: Fraction of data with lineage tracked.
        audit_completeness: Fraction of events audited.
        policy_adherence: Policy rule adherence rate.
        privacy_budget_remaining: DP epsilon budget remaining (0–1).

    Returns:
        Compliance score (0–1).
    """
    return 0.25 * data_lineage_coverage + 0.25 * audit_completeness + 0.25 * policy_adherence + 0.25 * privacy_budget_remaining
