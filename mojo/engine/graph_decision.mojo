"""
graph_decision.mojo — Graph-based decision engine: multi-constraint routing, flow, dynamic graphs.
Zero Python imports.

Public API:
  multi_constraint_relax         — multi-objective edge relaxation
  flow_residual_capacity         — max-flow residual edge capacity
  flow_augment_amount            — bottleneck augmenting path flow
  dynamic_edge_weight_decay      — time-decayed edge weight
  probabilistic_route_score      — stochastic routing combined score
  resource_constrained_cost      — resource-aware path cost update
  temporal_edge_validity         — time-window edge validity
  network_criticality            — edge criticality index
  supply_chain_slack             — supply chain slack time
  decision_graph_utility         — expected utility for decision node
"""
from std.math import sqrt, log, exp


def multi_constraint_relax(
    dist_u: Float64, edge_cost: Float64, edge_risk: Float64,
    dist_v_cost: Float64, dist_v_risk: Float64,
    alpha: Float64
) -> Float64:
    """Multi-objective Pareto-weighted edge relaxation.

    score = α × cost + (1-α) × risk

    Args:
        dist_u: Combined score at node u.
        edge_cost: Monetary/time cost of edge u→v.
        edge_risk: Risk/uncertainty of edge u→v.
        dist_v_cost: Current cost component at v (unused, for context).
        dist_v_risk: Current risk component at v.
        alpha: Weight for cost vs risk (0=risk only, 1=cost only).

    Returns:
        Candidate combined score at v.
    """
    var candidate = dist_u + alpha * edge_cost + (1.0 - alpha) * edge_risk
    return candidate


def flow_residual_capacity(
    capacity: Float64, current_flow: Float64
) -> Float64:
    """Residual capacity in max-flow: c_f(u,v) = c(u,v) - f(u,v).

    Args:
        capacity: Edge capacity c(u,v).
        current_flow: Current flow f(u,v).

    Returns:
        Residual capacity.
    """
    var residual = capacity - current_flow
    if residual < 0.0:
        return 0.0
    return residual


def flow_augment_amount(
    path_min_residual: Float64, new_edge_residual: Float64
) -> Float64:
    """Bottleneck residual along augmenting path.

    b = min(current_min, edge_residual)

    Args:
        path_min_residual: Current minimum residual along path.
        new_edge_residual: Residual capacity of next edge.

    Returns:
        Updated minimum (bottleneck).
    """
    if new_edge_residual < path_min_residual:
        return new_edge_residual
    return path_min_residual


def dynamic_edge_weight_decay(
    base_weight: Float64, time_elapsed: Float64, decay_rate: Float64
) -> Float64:
    """Time-decayed edge weight for dynamic graphs.

    w(t) = w_0 × exp(-λ × t)

    Args:
        base_weight: Original edge weight.
        time_elapsed: Time since last update.
        decay_rate: Exponential decay rate λ.

    Returns:
        Current effective edge weight.
    """
    return base_weight * exp(-decay_rate * time_elapsed)


def probabilistic_route_score(
    deterministic_cost: Float64, probability: Float64,
    risk_penalty: Float64
) -> Float64:
    """Stochastic routing: expected cost including risk penalty.

    score = cost + risk_penalty × (1 - probability)

    Args:
        deterministic_cost: Deterministic path cost.
        probability: Route success probability.
        risk_penalty: Penalty for route failure.

    Returns:
        Risk-adjusted route score (lower = better).
    """
    return deterministic_cost + risk_penalty * (1.0 - probability)


def resource_constrained_cost(
    current_cost: Float64, edge_cost: Float64,
    resource_used: Float64, resource_budget: Float64,
    penalty: Float64
) -> Float64:
    """Resource-constrained shortest path cost update.

    Applies soft penalty for exceeding resource budget.

    Args:
        current_cost: Accumulated cost at source.
        edge_cost: Edge traversal cost.
        resource_used: Resource consumed along path so far.
        resource_budget: Maximum resource budget.
        penalty: Penalty per unit resource over budget.

    Returns:
        Updated cost with resource violation penalty.
    """
    var new_cost = current_cost + edge_cost
    var violation = resource_used - resource_budget
    if violation > 0.0:
        new_cost += penalty * violation
    return new_cost


def temporal_edge_validity(
    current_time: Float64, edge_open: Float64, edge_close: Float64
) -> Float64:
    """Check if edge is valid at current_time within time window.

    Args:
        current_time: Current time t.
        edge_open: Time window open.
        edge_close: Time window close.

    Returns:
        1.0 if valid, 0.0 if outside window.
    """
    if current_time >= edge_open and current_time <= edge_close:
        return 1.0
    return 0.0


def network_criticality(
    edge_betweenness: Float64, flow: Float64, capacity: Float64
) -> Float64:
    """Edge criticality: betweenness × utilisation.

    criticality = BC × (flow / capacity)

    Args:
        edge_betweenness: Normalised edge betweenness centrality.
        flow: Current flow on edge.
        capacity: Edge capacity.

    Returns:
        Criticality index (0–1).
    """
    if capacity <= 0.0:
        return edge_betweenness
    var utilisation = flow / capacity
    if utilisation > 1.0:
        utilisation = 1.0
    return edge_betweenness * utilisation


def supply_chain_slack(
    deadline: Float64, current_time: Float64, remaining_duration: Float64
) -> Float64:
    """Supply chain slack time: deadline - now - remaining_duration.

    Args:
        deadline: Target completion time.
        current_time: Current time.
        remaining_duration: Sum of remaining activity durations.

    Returns:
        Slack (negative = behind schedule).
    """
    return deadline - current_time - remaining_duration


def decision_graph_utility(
    outcome_value: Float64, probability: Float64,
    discount_factor: Float64, time_steps: Float64
) -> Float64:
    """Expected discounted utility for a decision node outcome.

    U = probability × value × discount^t

    Args:
        outcome_value: Utility value of outcome.
        probability: Probability of this outcome.
        discount_factor: Temporal discount factor γ (0–1).
        time_steps: Number of time steps to outcome.

    Returns:
        Discounted expected utility.
    """
    return probability * outcome_value * exp(time_steps * log(discount_factor if discount_factor > 0.0 else 1e-300))
