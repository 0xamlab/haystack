"""
model_router.mojo — Model routing layer: best model per request, fallback, ensemble, hybrid.
Zero Python imports.

Public API:
  capability_match_score         — request-model capability alignment
  model_load_score               — current load on a model endpoint
  fallback_trigger_score         — when to trigger fallback to another model
  ensemble_weight                — weight for one model in ensemble output
  hybrid_pipeline_stage_score    — score for routing to ML vs retrieval stage
  model_selection_utility        — expected utility of choosing a model
  routing_uncertainty            — uncertainty in routing decision
  latency_tier_assignment        — assign request to latency tier
  model_freshness_score          — recency of model weights (staleness)
  shadow_routing_fraction        — fraction of traffic to shadow model
"""
from std.math import sqrt, log, exp


fn capability_match_score(
    request_task_embedding: Float64, model_task_embedding: Float64,
    model_max_context: Float64, request_context_len: Float64
) -> Float64:
    """Request-model capability alignment score.

    score = task_similarity × context_feasibility

    Args:
        request_task_embedding: Task embedding element for request.
        model_task_embedding: Task embedding element for model.
        model_max_context: Maximum context length supported.
        request_context_len: Required context length.

    Returns:
        Capability match score (0–1).
    """
    var task_sim = request_task_embedding * model_task_embedding
    if task_sim < 0.0:
        task_sim = 0.0
    var context_ok = 1.0 if request_context_len <= model_max_context else 0.0
    return task_sim * context_ok


fn model_load_score(
    active_requests: Float64, max_capacity: Float64,
    queue_depth: Float64
) -> Float64:
    """Current load on a model endpoint (lower = less loaded = prefer).

    score = (active + queue) / max_capacity

    Args:
        active_requests: Requests currently being served.
        max_capacity: Maximum concurrent requests.
        queue_depth: Requests waiting in queue.

    Returns:
        Load fraction (0 = idle, 1+ = overloaded).
    """
    if max_capacity <= 0.0:
        return 1.0
    return (active_requests + queue_depth) / max_capacity


fn fallback_trigger_score(
    primary_error_rate: Float64, primary_latency_p99: Float64,
    sla_latency_ms: Float64, error_threshold: Float64
) -> Float64:
    """Score indicating whether to trigger fallback to secondary model.

    Positive = trigger fallback; negative = stay with primary.

    Args:
        primary_error_rate: Recent error rate on primary (0–1).
        primary_latency_p99: P99 latency of primary (ms).
        sla_latency_ms: SLA latency budget (ms).
        error_threshold: Maximum acceptable error rate.

    Returns:
        Fallback trigger score.
    """
    var error_pressure = (primary_error_rate - error_threshold) / (error_threshold + 1e-9)
    var latency_pressure = (primary_latency_p99 - sla_latency_ms) / (sla_latency_ms + 1e-9)
    return error_pressure + latency_pressure


fn ensemble_weight(
    model_accuracy: Float64, model_latency_ms: Float64,
    latency_budget_ms: Float64, total_model_accuracy: Float64
) -> Float64:
    """Weight for one model in an ensemble output mix.

    weight = accuracy / total_accuracy × latency_feasibility

    Args:
        model_accuracy: This model's accuracy score.
        model_latency_ms: This model's latency.
        latency_budget_ms: SLA latency budget.
        total_model_accuracy: Sum of all ensemble model accuracies.

    Returns:
        Normalised ensemble weight (0–1).
    """
    if total_model_accuracy <= 0.0:
        return 0.0
    var feasible = 1.0 if model_latency_ms <= latency_budget_ms else 0.0
    return (model_accuracy / total_model_accuracy) * feasible


fn hybrid_pipeline_stage_score(
    retrieval_relevance: Float64, generation_confidence: Float64,
    use_retrieval_threshold: Float64
) -> Float64:
    """Score for routing to retrieval stage vs pure generation.

    Positive = route to retrieval; negative = pure LLM generation.

    Args:
        retrieval_relevance: Expected retrieval relevance for query.
        generation_confidence: LLM confidence without retrieval.
        use_retrieval_threshold: Minimum retrieval benefit to invoke it.

    Returns:
        Routing score (positive = retrieval augmented).
    """
    var retrieval_benefit = retrieval_relevance - generation_confidence
    return retrieval_benefit - use_retrieval_threshold


fn model_selection_utility(
    model_quality: Float64, model_cost: Float64,
    user_quality_weight: Float64
) -> Float64:
    """Expected utility of choosing a model given quality/cost preferences.

    utility = quality_weight × quality - (1 - quality_weight) × cost

    Args:
        model_quality: Model quality score (0–1).
        model_cost: Normalised model cost (0–1).
        user_quality_weight: User preference for quality vs cost (0–1).

    Returns:
        Expected utility.
    """
    return user_quality_weight * model_quality - (1.0 - user_quality_weight) * model_cost


fn routing_uncertainty(
    top_model_score: Float64, second_model_score: Float64
) -> Float64:
    """Uncertainty in routing decision (margin between top two choices).

    Low margin = uncertain; high margin = confident routing.

    Args:
        top_model_score: Score of best model candidate.
        second_model_score: Score of second-best candidate.

    Returns:
        Routing confidence (0 = uncertain, 1 = highly confident).
    """
    var total = top_model_score + second_model_score
    if total <= 0.0:
        return 0.0
    return (top_model_score - second_model_score) / total


fn latency_tier_assignment(
    request_latency_budget_ms: Float64,
    tier_interactive_ms: Float64, tier_batch_ms: Float64
) -> Float64:
    """Assign request to latency tier (0=interactive, 1=standard, 2=batch).

    Args:
        request_latency_budget_ms: Request SLA budget.
        tier_interactive_ms: Interactive tier threshold.
        tier_batch_ms: Batch tier threshold.

    Returns:
        Tier index (0, 1, or 2).
    """
    if request_latency_budget_ms <= tier_interactive_ms:
        return 0.0
    if request_latency_budget_ms <= tier_batch_ms:
        return 1.0
    return 2.0


fn model_freshness_score(
    model_training_step: Float64, current_step: Float64,
    decay_half_life_steps: Float64
) -> Float64:
    """Recency/freshness of model weights relative to current data.

    score = exp(-staleness / half_life)

    Args:
        model_training_step: Step at which model was trained.
        current_step: Current system step.
        decay_half_life_steps: Half-life of freshness decay.

    Returns:
        Freshness score (1 = fresh, near 0 = stale).
    """
    if decay_half_life_steps <= 0.0:
        return 1.0
    var staleness = current_step - model_training_step
    if staleness < 0.0:
        staleness = 0.0
    return exp(-staleness * 0.693 / decay_half_life_steps)


fn shadow_routing_fraction(
    shadow_experiment_budget: Float64, total_traffic: Float64,
    statistical_power_needed: Float64
) -> Float64:
    """Fraction of traffic to route to shadow/challenger model.

    Balances experiment budget with statistical power requirements.

    Args:
        shadow_experiment_budget: Maximum fraction to divert (0–1).
        total_traffic: Total request volume.
        statistical_power_needed: Required sample size for significance.

    Returns:
        Shadow routing fraction (0–1).
    """
    if total_traffic <= 0.0:
        return 0.0
    var needed_fraction = statistical_power_needed / total_traffic
    if needed_fraction > shadow_experiment_budget:
        return shadow_experiment_budget
    return needed_fraction
