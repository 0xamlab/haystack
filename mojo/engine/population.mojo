"""
population.mojo — Population dynamics models. Zero Python imports.

Replaces custom ecology code with pure-Mojo implementations.

Public API:
  fn logistic_growth(N, r, K)               — Single logistic step
  fn logistic_simulate(N0, r, K, n_steps)   — Logistic simulation
  fn lotka_volterra_step(...)               — One predator-prey step
  fn lotka_volterra_simulate(...)           — Full predator-prey sim
  fn exponential_growth(N0, r, t)           — Exponential growth
  fn carrying_capacity_estimate(pops)       — Estimate K from data
  fn growth_rate_estimate(N_t, N_t1, K)     — Estimate r from two points
  fn competition_model(N1, N2, ...)         — Lotka-Volterra competition
  fn population_doubling_time(r)            — ln(2)/r
  fn extinction_risk(population, threshold) — Population below threshold?
"""

from std.math import log, exp


# ── Exponential Growth ────────────────────────────────────────────────────────


fn exponential_growth(N0: Float64, r: Float64, t: Float64) -> Float64:
    """N = N0 * e^(rt). Continuous exponential growth."""
    return N0 * exp(r * t)


# ── Logistic Growth ──────────────────────────────────────────────────────────


fn logistic_growth(N: Float64, r: Float64, K: Float64) -> Float64:
    """Discrete logistic growth step: N' = N + r*N*(1 - N/K), dt=1."""
    return N + r * N * (1.0 - N / K)


fn logistic_simulate(
    N0: Float64, r: Float64, K: Float64, n_steps: Int
) -> List[Float64]:
    """Simulate logistic growth for n_steps. Returns population at each step."""
    var result = List[Float64]()
    var N = N0
    result.append(N)
    for i in range(n_steps):
        N = logistic_growth(N, r, K)
        if N < 0.0:
            N = 0.0
        result.append(N)
    return result^


# ── Lotka-Volterra Predator-Prey ─────────────────────────────────────────────


fn lotka_volterra_step(
    prey: Float64,
    pred: Float64,
    alpha: Float64,
    beta: Float64,
    delta: Float64,
    gamma: Float64,
    dt: Float64,
) -> List[Float64]:
    """One Euler step of the Lotka-Volterra equations.
    dx/dt = alpha*x - beta*x*y
    dy/dt = delta*x*y - gamma*y
    Returns [prey', pred']."""
    var dx = alpha * prey - beta * prey * pred
    var dy = delta * prey * pred - gamma * pred
    var new_prey = prey + dx * dt
    var new_pred = pred + dy * dt
    if new_prey < 0.0:
        new_prey = 0.0
    if new_pred < 0.0:
        new_pred = 0.0
    var result = List[Float64]()
    result.append(new_prey)
    result.append(new_pred)
    return result^


fn lotka_volterra_simulate(
    prey0: Float64,
    pred0: Float64,
    alpha: Float64,
    beta: Float64,
    delta: Float64,
    gamma: Float64,
    dt: Float64,
    n_steps: Int,
) -> List[List[Float64]]:
    """Full Lotka-Volterra simulation. Returns [[prey, pred], ...]."""
    var result = List[List[Float64]]()
    var initial = List[Float64]()
    initial.append(prey0)
    initial.append(pred0)
    result.append(initial^)
    var prey = prey0
    var pred = pred0
    for i in range(n_steps):
        var step = lotka_volterra_step(prey, pred, alpha, beta, delta, gamma, dt)
        prey = step[0]
        pred = step[1]
        result.append(step^)
    return result^


# ── Carrying Capacity Estimation ─────────────────────────────────────────────


fn carrying_capacity_estimate(populations: List[Float64]) -> Float64:
    """Estimate K from population data as max(observed) * 1.1."""
    if len(populations) == 0:
        return 0.0
    var max_val = populations[0]
    for i in range(1, len(populations)):
        if populations[i] > max_val:
            max_val = populations[i]
    return max_val * 1.1


# ── Growth Rate Estimation ───────────────────────────────────────────────────


fn growth_rate_estimate(
    N_t: Float64, N_t1: Float64, K: Float64
) -> Float64:
    """Estimate r from two consecutive populations using logistic model.
    r = (N_t1 - N_t) / (N_t * (1 - N_t/K))."""
    var denom = N_t * (1.0 - N_t / K)
    if denom == 0.0:
        return 0.0
    return (N_t1 - N_t) / denom


# ── Lotka-Volterra Competition ───────────────────────────────────────────────


fn competition_model(
    N1: Float64,
    N2: Float64,
    r1: Float64,
    r2: Float64,
    K1: Float64,
    K2: Float64,
    alpha12: Float64,
    alpha21: Float64,
) -> List[Float64]:
    """Lotka-Volterra competition model (one Euler step, dt=1).
    dN1/dt = r1*N1*(1 - (N1 + alpha12*N2)/K1)
    dN2/dt = r2*N2*(1 - (N2 + alpha21*N1)/K2)
    Returns [N1', N2']."""
    var dN1 = r1 * N1 * (1.0 - (N1 + alpha12 * N2) / K1)
    var dN2 = r2 * N2 * (1.0 - (N2 + alpha21 * N1) / K2)
    var new_N1 = N1 + dN1
    var new_N2 = N2 + dN2
    if new_N1 < 0.0:
        new_N1 = 0.0
    if new_N2 < 0.0:
        new_N2 = 0.0
    var result = List[Float64]()
    result.append(new_N1)
    result.append(new_N2)
    return result^


# ── Population Doubling Time ─────────────────────────────────────────────────


fn population_doubling_time(r: Float64) -> Float64:
    """Time for population to double: ln(2)/r."""
    return log(2.0) / r


# ── Extinction Risk ──────────────────────────────────────────────────────────


fn extinction_risk(population: Float64, threshold: Float64) -> Bool:
    """Returns True if population is below threshold."""
    return population < threshold
