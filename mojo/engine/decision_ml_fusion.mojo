"""
decision_ml_fusion.mojo — Decision + ML fusion layer: ML→simulation→optimization pipeline.
Zero Python imports.

Public API:
  ml_to_simulation_weight        — map ML probability to simulation weight
  simulation_to_objective        — simulation outcome → optimisation objective
  expected_value_under_model     — model-weighted expected value
  regret_from_prediction         — decision regret from ML prediction error
  counterfactual_utility         — counterfactual outcome utility
  policy_gradient_advantage      — advantage estimate for policy gradient
  reward_shaping_potential       — potential-based reward shaping
  multi_objective_scalarize      — weighted Chebyshev scalarisation
  model_confidence_gate          — gate decision on model confidence
  adaptive_exploration_rate      — UCB-style exploration rate
"""
from std.math import sqrt, log, exp


def ml_to_simulation_weight(
    ml_probability: Float64, temperature: Float64
) -> Float64:
    """Map ML output probability to Monte Carlo simulation weight.

    weight = p^(1/T)  (temperature sharpening/softening)

    Args:
        ml_probability: Model predicted probability.
        temperature: Sharpening temperature (1=unchanged, <1=sharper).

    Returns:
        Reweighted simulation probability.
    """
    if ml_probability <= 0.0:
        return 0.0
    if temperature <= 0.0:
        return 1.0 if ml_probability >= 0.5 else 0.0
    return exp(log(ml_probability) / temperature)


def simulation_to_objective(
    sim_mean: Float64, sim_std: Float64, risk_aversion: Float64
) -> Float64:
    """Convert simulation statistics to optimisation objective.

    objective = mean - risk_aversion × std  (mean-variance utility)

    Args:
        sim_mean: Monte Carlo mean outcome.
        sim_std: Monte Carlo standard deviation.
        risk_aversion: Risk aversion coefficient λ (0=risk-neutral).

    Returns:
        Scalar objective (higher = better).
    """
    return sim_mean - risk_aversion * sim_std


def expected_value_under_model(
    outcome: Float64, model_weight: Float64,
    prior_weight: Float64, model_confidence: Float64
) -> Float64:
    """Model-weighted expected value blending model and prior.

    E[v] = conf × model_weight × outcome + (1-conf) × prior_weight × outcome

    Args:
        outcome: Outcome value.
        model_weight: ML model probability weight.
        prior_weight: Prior / baseline weight.
        model_confidence: Model confidence (0–1).

    Returns:
        Blended expected value contribution.
    """
    var blend = model_confidence * model_weight + (1.0 - model_confidence) * prior_weight
    return blend * outcome


def regret_from_prediction(
    true_outcome: Float64, predicted_outcome: Float64,
    decision_cost: Float64
) -> Float64:
    """Decision regret from prediction error.

    regret = |true - predicted| × decision_cost

    Args:
        true_outcome: Actual observed outcome.
        predicted_outcome: ML model prediction.
        decision_cost: Cost multiplier for prediction error.

    Returns:
        Regret value.
    """
    var error = true_outcome - predicted_outcome
    if error < 0.0:
        error = -error
    return error * decision_cost


def counterfactual_utility(
    chosen_outcome: Float64, best_alternative: Float64
) -> Float64:
    """Counterfactual utility: regret vs best alternative.

    utility = chosen - best_alternative (negative = regret)

    Args:
        chosen_outcome: Utility of chosen action.
        best_alternative: Utility of best available alternative.

    Returns:
        Relative utility (negative = regret).
    """
    return chosen_outcome - best_alternative


def policy_gradient_advantage(
    reward: Float64, baseline: Float64
) -> Float64:
    """Advantage estimate A(s,a) = R - b(s) for policy gradient.

    Args:
        reward: Observed return R.
        baseline: Baseline value estimate b(s) (e.g., V(s)).

    Returns:
        Advantage (positive = better than expected).
    """
    return reward - baseline


def reward_shaping_potential(
    gamma: Float64, next_potential: Float64, current_potential: Float64
) -> Float64:
    """Potential-based reward shaping: F = γ Φ(s') - Φ(s).

    Guarantees policy invariance.

    Args:
        gamma: Discount factor.
        next_potential: Potential Φ(s') at next state.
        current_potential: Potential Φ(s) at current state.

    Returns:
        Shaping reward F(s, a, s').
    """
    return gamma * next_potential - current_potential


def multi_objective_scalarize(
    objectives: Float64, ideal: Float64,
    weight: Float64, nadir: Float64
) -> Float64:
    """Weighted Chebyshev scalarisation for multi-objective optimisation.

    max_i { w_i × |f_i - z*_i| / (nadir_i - ideal_i) }

    This returns the contribution for one objective.

    Args:
        objectives: Objective value f_i.
        ideal: Ideal point z*_i (best possible).
        weight: Objective weight w_i.
        nadir: Nadir point (worst) for normalisation.

    Returns:
        Weighted normalised deviation for this objective.
    """
    var range = nadir - ideal
    if range <= 0.0:
        return 0.0
    var deviation = objectives - ideal
    if deviation < 0.0:
        deviation = -deviation
    return weight * deviation / range


def model_confidence_gate(
    model_output: Float64, confidence: Float64,
    threshold: Float64, fallback: Float64
) -> Float64:
    """Gate decision on model confidence; fall back if uncertain.

    Args:
        model_output: ML model recommendation.
        confidence: Model confidence score.
        threshold: Minimum confidence to trust the model.
        fallback: Fallback decision value if below threshold.

    Returns:
        model_output if confident, fallback otherwise.
    """
    if confidence >= threshold:
        return model_output
    return fallback


def adaptive_exploration_rate(
    q_value: Float64, visit_count: Float64,
    total_visits: Float64, ucb_c: Float64
) -> Float64:
    """UCB1-style adaptive exploration rate.

    score = Q(a) + c × sqrt(log(N) / n(a))

    Args:
        q_value: Estimated action value Q(a).
        visit_count: Number of times this action was taken n(a).
        total_visits: Total steps N.
        ucb_c: Exploration constant c (√2 typical).

    Returns:
        UCB score (higher = explore this action).
    """
    if visit_count <= 0.0:
        return q_value + 1e9
    if total_visits <= 0.0:
        return q_value
    return q_value + ucb_c * sqrt(log(total_visits) / visit_count)
