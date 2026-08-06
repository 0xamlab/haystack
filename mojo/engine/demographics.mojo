"""
demographics.mojo — Demographics Library. Zero Python imports.

Provides crude birth/death rates, natural increase, total fertility rate,
infant mortality, life expectancy approximation, dependency ratio, sex ratio,
population growth rate, doubling time, urbanization rate, and median age
estimate.

Public API:
  crude_birth_rate         — CBR = births/pop * 1000
  crude_death_rate         — CDR = deaths/pop * 1000
  natural_increase_rate    — NIR = CBR - CDR
  total_fertility_rate     — TFR = Σ(ASFR) * interval
  infant_mortality_rate    — IMR = deaths/births * 1000
  life_expectancy_approx   — e0 ≈ PY / pop
  dependency_ratio         — DR = (young+old)/working * 100
  sex_ratio                — SR = males/females * 100
  population_growth_rate   — GR = (B-D+NM)/P * 100
  doubling_time            — DT = 70 / rate (rule of 70)
  urbanization_rate        — UR = urban/total * 100
  median_age_estimate      — MA ≈ 15 + 50*(1-young_pct/100) - 10*(old_pct/100)
"""


# ── Birth & death rates ──────────────────────────────────────────────────────


def crude_birth_rate(births: Float64, population: Float64) -> Float64:
    """Crude birth rate: CBR = births / population * 1000."""
    if population <= 0.0:
        return 0.0
    return births / population * 1000.0


def crude_death_rate(deaths: Float64, population: Float64) -> Float64:
    """Crude death rate: CDR = deaths / population * 1000."""
    if population <= 0.0:
        return 0.0
    return deaths / population * 1000.0


def natural_increase_rate(cbr: Float64, cdr: Float64) -> Float64:
    """Natural increase rate: NIR = CBR - CDR (per 1000)."""
    return cbr - cdr


# ── Fertility & mortality ─────────────────────────────────────────────────────


def total_fertility_rate(
    age_specific_rates_sum: Float64, interval: Float64
) -> Float64:
    """Total fertility rate: TFR = Σ(ASFR) * interval (simplified)."""
    return age_specific_rates_sum * interval


def infant_mortality_rate(
    infant_deaths: Float64, live_births: Float64
) -> Float64:
    """Infant mortality rate: IMR = infant_deaths / live_births * 1000."""
    if live_births <= 0.0:
        return 0.0
    return infant_deaths / live_births * 1000.0


def life_expectancy_approx(
    total_person_years: Float64, population: Float64
) -> Float64:
    """Life expectancy approximation: e0 ≈ PY / pop."""
    if population <= 0.0:
        return 0.0
    return total_person_years / population


# ── Population structure ──────────────────────────────────────────────────────


def dependency_ratio(
    young: Float64, old: Float64, working_age: Float64
) -> Float64:
    """Dependency ratio: DR = (young + old) / working_age * 100."""
    if working_age <= 0.0:
        return 0.0
    return (young + old) / working_age * 100.0


def sex_ratio(males: Float64, females: Float64) -> Float64:
    """Sex ratio: SR = males / females * 100."""
    if females <= 0.0:
        return 0.0
    return males / females * 100.0


# ── Growth & doubling ─────────────────────────────────────────────────────────


def population_growth_rate(
    births: Float64,
    deaths: Float64,
    net_migration: Float64,
    population: Float64,
) -> Float64:
    """Population growth rate: GR = (B - D + NM) / P * 100 (%)."""
    if population <= 0.0:
        return 0.0
    return (births - deaths + net_migration) / population * 100.0


def doubling_time(growth_rate_pct: Float64) -> Float64:
    """Doubling time (rule of 70): DT = 70 / growth_rate_pct (years)."""
    if growth_rate_pct <= 0.0:
        return 0.0
    return 70.0 / growth_rate_pct


# ── Urbanization & age ────────────────────────────────────────────────────────


def urbanization_rate(urban_pop: Float64, total_pop: Float64) -> Float64:
    """Urbanization rate: UR = urban_pop / total_pop * 100 (%)."""
    if total_pop <= 0.0:
        return 0.0
    return urban_pop / total_pop * 100.0


def median_age_estimate(
    young_pct: Float64, old_pct: Float64
) -> Float64:
    """Simplified median age estimate.

    MA ≈ 15 + 50*(1 - young_pct/100) - 10*(old_pct/100).
    """
    return 15.0 + 50.0 * (1.0 - young_pct / 100.0) - 10.0 * (old_pct / 100.0)
