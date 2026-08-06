"""
entomology.mojo — Entomology (Insect Science) Library. Zero Python imports.

Pure Mojo implementations for insect population dynamics, degree-day
models, diversity indices, biocontrol efficacy, and metabolic rates.

Public API:
  degree_days                — DD = max(0, (Tmax+Tmin)/2 - Tbase)
  accumulated_degree_days    — ADD = daily_dd * days (avg estimate)
  population_growth_intrinsic — N = N0 * exp(r*t)
  net_reproductive_rate      — R0 = fecundity * survival
  generation_time            — T = ln(R0) / r
  doubling_time_population   — DT = ln(2) / r
  species_diversity_simpson  — D = 1 - Σ(pi²)
  trap_catch_index           — TCI = caught / (traps * days)
  infestation_rate           — IR = infested/total * 100
  biocontrol_efficacy        — E = (control-treated)/control * 100
  larval_mortality_rate      — MR = (initial-surviving)/initial * 100
  metabolic_rate_insect      — MR ≈ 0.01 * mass^0.75 * exp(0.07*temp)
"""
from std.math import sqrt, log, exp, abs as fabs


# ── degree_days ──────────────────────────────────────────────────────────────


def degree_days(
    t_max: Float64, t_min: Float64, t_base: Float64
) -> Float64:
    """Single-day degree days DD = max(0, (Tmax+Tmin)/2 - Tbase)."""
    var avg = (t_max + t_min) / 2.0
    var dd = avg - t_base
    if dd < 0.0:
        return 0.0
    return dd


# ── accumulated_degree_days ──────────────────────────────────────────────────


def accumulated_degree_days(
    daily_dd: Float64, days: Float64
) -> Float64:
    """Accumulated degree days ADD = daily_dd * days (average estimate)."""
    return daily_dd * days


# ── population_growth_intrinsic ──────────────────────────────────────────────


def population_growth_intrinsic(
    n0: Float64, r: Float64, t: Float64
) -> Float64:
    """Exponential population growth N = N0 * exp(r*t)."""
    return n0 * exp(r * t)


# ── net_reproductive_rate ────────────────────────────────────────────────────


def net_reproductive_rate(
    fecundity: Float64, survival: Float64
) -> Float64:
    """Net reproductive rate R0 = fecundity * survival."""
    return fecundity * survival


# ── generation_time ──────────────────────────────────────────────────────────


def generation_time(r0: Float64, r: Float64) -> Float64:
    """Generation time T = ln(R0) / r."""
    return log(r0) / r


# ── doubling_time_population ─────────────────────────────────────────────────


def doubling_time_population(r: Float64) -> Float64:
    """Population doubling time DT = ln(2) / r."""
    return log(2.0) / r


# ── species_diversity_simpson ────────────────────────────────────────────────


def species_diversity_simpson(p_squared_sum: Float64) -> Float64:
    """Simpson's diversity index D = 1 - Σ(pi²)."""
    return 1.0 - p_squared_sum


# ── trap_catch_index ─────────────────────────────────────────────────────────


def trap_catch_index(
    n_caught: Float64, n_traps: Float64, n_days: Float64
) -> Float64:
    """Trap catch index TCI = caught / (traps * days)."""
    return n_caught / (n_traps * n_days)


# ── infestation_rate ─────────────────────────────────────────────────────────


def infestation_rate(
    infested_units: Float64, total_units: Float64
) -> Float64:
    """Infestation rate IR = infested/total * 100 (percent)."""
    return infested_units / total_units * 100.0


# ── biocontrol_efficacy ──────────────────────────────────────────────────────


def biocontrol_efficacy(
    treated_pop: Float64, control_pop: Float64
) -> Float64:
    """Biocontrol efficacy E = (control-treated)/control * 100 (percent)."""
    return (control_pop - treated_pop) / control_pop * 100.0


# ── larval_mortality_rate ────────────────────────────────────────────────────


def larval_mortality_rate(
    initial_larvae: Float64, surviving_larvae: Float64
) -> Float64:
    """Larval mortality rate MR = (initial-surviving)/initial * 100 (pct)."""
    return (initial_larvae - surviving_larvae) / initial_larvae * 100.0


# ── metabolic_rate_insect ────────────────────────────────────────────────────


def metabolic_rate_insect(
    mass_mg: Float64, temperature_c: Float64
) -> Float64:
    """Simplified insect metabolic rate MR ≈ 0.01 * mass^0.75 * exp(0.07*T).
    Uses exp(0.75*log(mass)) for the fractional exponent.
    """
    var mass_term = exp(0.75 * log(mass_mg))
    var temp_term = exp(0.07 * temperature_c)
    return 0.01 * mass_term * temp_term
