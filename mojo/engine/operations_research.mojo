"""
operations_research.mojo — Operations Research Library. Zero Python imports.

Pure Mojo implementations of core OR functions including linear programming
helpers, inventory models, queueing theory, and Little's Law.

Public API:
  simplex_objective_value      — Z = Σ(c_i * x_i)
  transportation_cost          — Single cell cost * allocation
  total_transportation_cost_2x2 — Σ(c_i * a_i) for 4 cells
  assignment_cost              — Σ(costs[i] * assignment[i]) for n tasks
  eoq_quantity                 — EOQ = sqrt(2*D*S/H)
  eoq_total_cost               — TC = sqrt(2*D*S*H)
  newsvendor_critical_ratio    — CR = cu / (cu + co)
  little_law_l                 — L = λ * W
  little_law_w                 — W = L / λ
  utilization_factor           — ρ = λ / μ
  mm1_expected_queue_length    — Lq = ρ² / (1 - ρ)
  mm1_expected_wait_time       — Wq = ρ / (μ*(1-ρ))
"""
from std.math import sqrt, abs as fabs, isnan, isinf


# ── simplex_objective_value ───────────────────────────────────────────────────


fn simplex_objective_value_2(
    c1: Float64, x1: Float64, c2: Float64, x2: Float64
) -> Float64:
    """Z = c1*x1 + c2*x2 — objective for 2 variables."""
    return c1 * x1 + c2 * x2


fn simplex_objective_value_3(
    c1: Float64, x1: Float64,
    c2: Float64, x2: Float64,
    c3: Float64, x3: Float64,
) -> Float64:
    """Z = c1*x1 + c2*x2 + c3*x3 — objective for 3 variables."""
    return c1 * x1 + c2 * x2 + c3 * x3


# ── transportation_cost ───────────────────────────────────────────────────────


fn transportation_cost(cost: Float64, allocation: Float64) -> Float64:
    """Single cell: cost * allocation."""
    return cost * allocation


# ── total_transportation_cost_2x2 ────────────────────────────────────────────


fn total_transportation_cost_2x2(
    c1: Float64, a1: Float64,
    c2: Float64, a2: Float64,
    c3: Float64, a3: Float64,
    c4: Float64, a4: Float64,
) -> Float64:
    """Total cost for a 2x2 transportation tableau: Σ(c_i * a_i)."""
    return c1 * a1 + c2 * a2 + c3 * a3 + c4 * a4


# ── assignment_cost ───────────────────────────────────────────────────────────


fn assignment_cost_3(
    c1: Float64, c2: Float64, c3: Float64
) -> Float64:
    """Total assignment cost for 3 tasks (costs already matched)."""
    return c1 + c2 + c3


# ── eoq_quantity ──────────────────────────────────────────────────────────────


fn eoq_quantity(
    demand: Float64, ordering_cost: Float64, holding_cost: Float64
) -> Float64:
    """EOQ = sqrt(2*D*S/H)."""
    return sqrt(2.0 * demand * ordering_cost / holding_cost)


# ── eoq_total_cost ────────────────────────────────────────────────────────────


fn eoq_total_cost(
    demand: Float64, ordering_cost: Float64, holding_cost: Float64
) -> Float64:
    """TC = sqrt(2*D*S*H) — total annual inventory cost at EOQ."""
    return sqrt(2.0 * demand * ordering_cost * holding_cost)


# ── newsvendor_critical_ratio ─────────────────────────────────────────────────


fn newsvendor_critical_ratio(cu: Float64, co: Float64) -> Float64:
    """CR = cu / (cu + co) — critical ratio for newsvendor model."""
    return cu / (cu + co)


# ── little_law_l ──────────────────────────────────────────────────────────────


fn little_law_l(lambda_rate: Float64, w: Float64) -> Float64:
    """L = λ * W — expected number in system."""
    return lambda_rate * w


# ── little_law_w ──────────────────────────────────────────────────────────────


fn little_law_w(l: Float64, lambda_rate: Float64) -> Float64:
    """W = L / λ — expected time in system."""
    return l / lambda_rate


# ── utilization_factor ────────────────────────────────────────────────────────


fn utilization_factor(
    arrival_rate: Float64, service_rate: Float64
) -> Float64:
    """ρ = λ / μ — server utilization."""
    return arrival_rate / service_rate


# ── mm1_expected_queue_length ─────────────────────────────────────────────────


fn mm1_expected_queue_length(rho: Float64) -> Float64:
    """Lq = ρ² / (1 - ρ) — expected queue length in M/M/1."""
    # ρ outside [0, 1) zeroes or flips the divisor, and the resulting
    # inf/nan cannot cross the result wire; report the degenerate value.
    if isnan(rho) or isinf(rho) or rho < 0.0 or rho >= 1.0:
        return 0.0
    return rho * rho / (1.0 - rho)


# ── mm1_expected_wait_time ────────────────────────────────────────────────────


fn mm1_expected_wait_time(rho: Float64, mu: Float64) -> Float64:
    """Wq = ρ / (μ*(1-ρ)) — expected waiting time in queue (M/M/1)."""
    # ρ outside [0, 1) or a non-positive μ zeroes or flips the divisor, and
    # the resulting inf/nan cannot cross the result wire; report degenerate.
    if isnan(rho) or isinf(rho) or isnan(mu) or isinf(mu) or mu <= 0.0:
        return 0.0
    if rho < 0.0 or rho >= 1.0:
        return 0.0
    return rho / (mu * (1.0 - rho))
