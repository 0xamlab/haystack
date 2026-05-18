"""
epidemiology.mojo — Epidemiological models. Zero Python imports.

Replaces custom epi code with pure Mojo implementations for SIR, SEIR,
basic reproduction number, herd immunity, and related metrics.

Public API:
  sir_step                   — One SIR Euler step
  sir_simulate               — Full SIR simulation
  seir_step                  — One SEIR Euler step
  basic_reproduction_number  — R0 = beta / gamma
  herd_immunity_threshold    — HIT = 1 - 1/R0
  effective_reproduction     — Re = R0 * (1 - vaccinated)
  doubling_time              — ln(2) / growth_rate
  attack_rate                — Final epidemic size (iterative)
  case_fatality_rate         — CFR = deaths / cases
  incidence_rate             — new_cases / (population * time)
"""
from std.math import log, exp


# ── sir_step ──────────────────────────────────────────────────────────────────


fn sir_step(
    S: Float64, I: Float64, R: Float64,
    beta: Float64, gamma: Float64, dt: Float64,
) -> List[Float64]:
    """One SIR Euler step. Returns [S', I', R']. N = S+I+R."""
    var N = S + I + R
    var dS = -beta * S * I / N * dt
    var dI = (beta * S * I / N - gamma * I) * dt
    var dR = gamma * I * dt
    var result = List[Float64]()
    result.append(S + dS)
    result.append(I + dI)
    result.append(R + dR)
    return result^


# ── sir_simulate ──────────────────────────────────────────────────────────────


fn sir_simulate(
    S0: Float64, I0: Float64, R0: Float64,
    beta: Float64, gamma: Float64, dt: Float64, n_steps: Int,
) -> List[List[Float64]]:
    """Full SIR simulation. Returns [[S,I,R], ...] for each step."""
    var result = List[List[Float64]]()
    var init = List[Float64]()
    init.append(S0); init.append(I0); init.append(R0)
    result.append(init^)
    var S = S0
    var I = I0
    var R = R0
    for _ in range(n_steps):
        var step = sir_step(S, I, R, beta, gamma, dt)
        S = step[0]
        I = step[1]
        R = step[2]
        var row = List[Float64]()
        row.append(S); row.append(I); row.append(R)
        result.append(row^)
    return result^


# ── seir_step ─────────────────────────────────────────────────────────────────


fn seir_step(
    S: Float64, E: Float64, I: Float64, R: Float64,
    beta: Float64, sigma: Float64, gamma: Float64, dt: Float64,
) -> List[Float64]:
    """One SEIR Euler step. Returns [S', E', I', R']."""
    var N = S + E + I + R
    var dS = -beta * S * I / N * dt
    var dE = (beta * S * I / N - sigma * E) * dt
    var dI = (sigma * E - gamma * I) * dt
    var dR = gamma * I * dt
    var result = List[Float64]()
    result.append(S + dS)
    result.append(E + dE)
    result.append(I + dI)
    result.append(R + dR)
    return result^


# ── basic_reproduction_number ─────────────────────────────────────────────────


fn basic_reproduction_number(beta: Float64, gamma: Float64) -> Float64:
    """R0 = beta / gamma."""
    if gamma == 0.0:
        return 0.0
    return beta / gamma


# ── herd_immunity_threshold ───────────────────────────────────────────────────


fn herd_immunity_threshold(R0: Float64) -> Float64:
    """HIT = 1 - 1/R0."""
    if R0 <= 0.0:
        return 0.0
    return 1.0 - 1.0 / R0


# ── effective_reproduction ────────────────────────────────────────────────────


fn effective_reproduction(
    R0: Float64, vaccinated_fraction: Float64
) -> Float64:
    """Re = R0 * (1 - vaccinated_fraction)."""
    return R0 * (1.0 - vaccinated_fraction)


# ── doubling_time ─────────────────────────────────────────────────────────────


fn doubling_time(growth_rate: Float64) -> Float64:
    """ln(2) / growth_rate."""
    if growth_rate == 0.0:
        return 0.0
    return log(2.0) / growth_rate


# ── attack_rate ───────────────────────────────────────────────────────────────


fn attack_rate(R0: Float64) -> Float64:
    """Final size of epidemic via iterative solution of z = 1 - exp(-R0*z)."""
    if R0 <= 1.0:
        return 0.0
    var z: Float64 = 0.99  # initial guess
    for _ in range(200):
        z = 1.0 - exp(-R0 * z)
    return z


# ── case_fatality_rate ────────────────────────────────────────────────────────


fn case_fatality_rate(deaths: Int, cases: Int) -> Float64:
    """CFR = deaths / cases."""
    if cases == 0:
        return 0.0
    return Float64(deaths) / Float64(cases)


# ── incidence_rate ────────────────────────────────────────────────────────────


fn incidence_rate(
    new_cases: Int, population: Int, time_period: Float64
) -> Float64:
    """Incidence rate = new_cases / (population * time_period)."""
    var denom = Float64(population) * time_period
    if denom == 0.0:
        return 0.0
    return Float64(new_cases) / denom
