"""
hybrid_reasoning.mojo — Hybrid ML + simulation + optimization + rules engine.
Zero Python imports.

Public API:
  ml_simulation_blend            — blend ML prediction with simulation output
  optimization_objective_gate    — gate optimization based on ML feasibility
  rule_violation_penalty         — constraint violation penalty from rules
  simulation_rollout_value       — value estimate from simulation rollout
  ml_confidence_simulation_cost  — decide when to run expensive simulation
  counterfactual_reasoning_score — score of counterfactual scenario
  symbolic_constraint_score      — symbolic rule constraint satisfaction
  reasoning_chain_coherence      — coherence of multi-step reasoning chain
  hybrid_uncertainty_estimate    — combined epistemic + aleatoric uncertainty
  meta_reasoning_switch          — switch between reasoning modes
"""
from std.math import sqrt, log, exp


def ml_simulation_blend(
    ml_prediction: Float64, simulation_output: Float64,
    ml_confidence: Float64
) -> Float64:
    """Blend ML prediction with simulation output weighted by ML confidence.

    output = confidence × ML + (1 - confidence) × simulation

    Args:
        ml_prediction: ML model's prediction.
        simulation_output: Physics/simulation model output.
        ml_confidence: ML model confidence (0–1).

    Returns:
        Blended prediction.
    """
    return ml_confidence * ml_prediction + (1.0 - ml_confidence) * simulation_output


def optimization_objective_gate(
    ml_feasibility_score: Float64, feasibility_threshold: Float64,
    objective_value: Float64
) -> Float64:
    """Gate optimization objective by ML feasibility prediction.

    If ML predicts infeasible, penalise objective heavily.

    Args:
        ml_feasibility_score: ML probability that solution is feasible.
        feasibility_threshold: Minimum feasibility to proceed.
        objective_value: Raw optimization objective.

    Returns:
        Gated objective (penalised if infeasible).
    """
    if ml_feasibility_score < feasibility_threshold:
        return objective_value * ml_feasibility_score
    return objective_value


def rule_violation_penalty(
    constraint_value: Float64, constraint_limit: Float64,
    penalty_coefficient: Float64
) -> Float64:
    """Quadratic penalty for hard constraint violations.

    penalty = coefficient × max(0, value - limit)²

    Args:
        constraint_value: Current constraint value.
        constraint_limit: Maximum allowed value.
        penalty_coefficient: Penalty strength.

    Returns:
        Constraint violation penalty.
    """
    var violation = constraint_value - constraint_limit
    if violation <= 0.0:
        return 0.0
    return penalty_coefficient * violation * violation


def simulation_rollout_value(
    immediate_reward: Float64, rollout_return: Float64,
    discount: Float64, ml_value_estimate: Float64,
    blend_weight: Float64
) -> Float64:
    """Value estimate blending simulation rollout with ML value head.

    V = blend × (r + γ × rollout) + (1 - blend) × ML_V

    Args:
        immediate_reward: Immediate reward at this step.
        rollout_return: Discounted return from simulation.
        discount: Discount factor γ.
        ml_value_estimate: ML model value head estimate.
        blend_weight: Weight on simulation vs ML estimate.

    Returns:
        Blended value estimate.
    """
    var sim_value = immediate_reward + discount * rollout_return
    return blend_weight * sim_value + (1.0 - blend_weight) * ml_value_estimate


def ml_confidence_simulation_cost(
    ml_confidence: Float64, simulation_cost: Float64,
    expected_gain_from_simulation: Float64
) -> Float64:
    """Decide benefit of running expensive simulation given ML confidence.

    benefit = (1 - confidence) × expected_gain - simulation_cost

    Args:
        ml_confidence: ML model confidence in its prediction.
        simulation_cost: Compute cost of running simulation.
        expected_gain_from_simulation: Expected accuracy improvement.

    Returns:
        Net benefit (positive = run simulation).
    """
    return (1.0 - ml_confidence) * expected_gain_from_simulation - simulation_cost


def counterfactual_reasoning_score(
    factual_outcome: Float64, counterfactual_outcome: Float64,
    intervention_cost: Float64
) -> Float64:
    """Score of a counterfactual scenario (what-if analysis).

    score = (counterfactual - factual) / (intervention_cost + 1)

    Args:
        factual_outcome: Observed outcome without intervention.
        counterfactual_outcome: Predicted outcome with intervention.
        intervention_cost: Cost of the intervention.

    Returns:
        Counterfactual value score.
    """
    return (counterfactual_outcome - factual_outcome) / (intervention_cost + 1.0)


def symbolic_constraint_score(
    predicate_value: Float64, lower_bound: Float64,
    upper_bound: Float64
) -> Float64:
    """Symbolic rule constraint satisfaction score.

    1.0 = fully satisfied, 0.0 = violated.

    Args:
        predicate_value: Value to check against constraint.
        lower_bound: Minimum allowed value.
        upper_bound: Maximum allowed value.

    Returns:
        Constraint satisfaction (1.0 = satisfied, 0.0 = violated).
    """
    if predicate_value >= lower_bound and predicate_value <= upper_bound:
        return 1.0
    var dist_low = lower_bound - predicate_value
    var dist_high = predicate_value - upper_bound
    var dist = dist_low if dist_low > dist_high else dist_high
    return exp(-dist)


def reasoning_chain_coherence(
    step_confidence: Float64, n_steps: Float64,
    dependency_strength: Float64
) -> Float64:
    """Coherence of a multi-step reasoning chain.

    coherence = step_confidence^n × dependency_strength

    Args:
        step_confidence: Average confidence per reasoning step.
        n_steps: Number of reasoning steps.
        dependency_strength: How tightly steps depend on each other (0–1).

    Returns:
        Chain coherence score (0–1).
    """
    if step_confidence <= 0.0:
        return 0.0
    var base = step_confidence if step_confidence <= 1.0 else 1.0
    var chain_prob = exp(n_steps * log(base + 1e-9))
    return chain_prob * dependency_strength


def hybrid_uncertainty_estimate(
    epistemic_uncertainty: Float64, aleatoric_uncertainty: Float64,
    model_disagreement: Float64
) -> Float64:
    """Combined epistemic + aleatoric uncertainty for hybrid system.

    total = sqrt(epistemic² + aleatoric²) + model_disagreement

    Args:
        epistemic_uncertainty: Model/knowledge uncertainty.
        aleatoric_uncertainty: Data/environment uncertainty.
        model_disagreement: Disagreement between ML and simulation.

    Returns:
        Total uncertainty estimate.
    """
    var combined = sqrt(epistemic_uncertainty * epistemic_uncertainty +
                        aleatoric_uncertainty * aleatoric_uncertainty)
    return combined + model_disagreement


def meta_reasoning_switch(
    problem_complexity: Float64, time_budget_ms: Float64,
    ml_latency_ms: Float64, sim_latency_ms: Float64
) -> Float64:
    """Switch between reasoning modes based on problem complexity and time.

    Returns 0=fast ML, 1=hybrid ML+sim, 2=full simulation.

    Args:
        problem_complexity: Estimated problem complexity (0–1).
        time_budget_ms: Available time budget.
        ml_latency_ms: ML inference latency.
        sim_latency_ms: Simulation latency.

    Returns:
        Reasoning mode (0, 1, or 2).
    """
    if time_budget_ms < ml_latency_ms:
        return 0.0  # Only fast approximation fits
    if problem_complexity < 0.3:
        return 0.0  # Simple problem: ML only
    if time_budget_ms >= ml_latency_ms + sim_latency_ms and problem_complexity > 0.7:
        return 2.0  # Full simulation
    return 1.0  # Hybrid
