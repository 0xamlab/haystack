"""
mycology.mojo — Fungal biology and spore dispersal calculations. Zero Python imports.

Public API:
  spore_dispersal_distance     — Gaussian plume dispersion estimate
  mycelial_growth_rate         — radial extension rate (mm/day)
  fungal_biomass               — dry weight estimate from ergosterol
  sporulation_index            — spores per unit colony area
  infection_efficiency         — fraction of spores causing infection
  latent_period                — time from infection to sporulation
  epidemic_progress_rate       — Vanderplank's logistic rate r
  spore_germination_prob       — temperature-humidity response
  colony_diameter              — from growth rate and time
  competitive_exclusion_index  — Lotka-Volterra competition ratio
"""
from std.math import exp, log, sqrt, pow


def spore_dispersal_distance(
    release_height: Float64, wind_speed: Float64, settling_velocity: Float64
) -> Float64:
    """Horizontal dispersal distance for a spore released at height h.

    x = U·h / v_s  (simplified ballistic model, no turbulence)

    Args:
        release_height: Release height (m).
        wind_speed: Horizontal wind speed (m/s).
        settling_velocity: Spore terminal settling velocity (m/s).

    Returns:
        Mean dispersal distance (m).
    """
    if settling_velocity <= 0.0:
        return 0.0
    return wind_speed * release_height / settling_velocity


def mycelial_growth_rate(
    colony_diam_t2: Float64, colony_diam_t1: Float64, time_days: Float64
) -> Float64:
    """Radial mycelial extension rate.

    r = (D2 - D1) / (2 * Δt)

    Args:
        colony_diam_t2: Colony diameter at time 2 (mm).
        colony_diam_t1: Colony diameter at time 1 (mm).
        time_days: Elapsed time (days).

    Returns:
        Radial extension rate (mm/day).
    """
    if time_days <= 0.0:
        return 0.0
    return (colony_diam_t2 - colony_diam_t1) / (2.0 * time_days)


def fungal_biomass(ergosterol_ug_g: Float64, conversion_factor: Float64) -> Float64:
    """Fungal biomass from ergosterol content.

    Biomass = ergosterol / conversion_factor

    Args:
        ergosterol_ug_g: Ergosterol concentration (μg/g substrate).
        conversion_factor: μg ergosterol per mg fungal biomass (typically 5–9).

    Returns:
        Fungal biomass (mg/g substrate).
    """
    if conversion_factor <= 0.0:
        return 0.0
    return ergosterol_ug_g / conversion_factor


def sporulation_index(
    spore_count: Float64, colony_area_cm2: Float64
) -> Float64:
    """Sporulation density: spores per cm² colony area.

    Args:
        spore_count: Total spore count from colony.
        colony_area_cm2: Colony area (cm²).

    Returns:
        Spores per cm².
    """
    if colony_area_cm2 <= 0.0:
        return 0.0
    return spore_count / colony_area_cm2


def infection_efficiency(
    successful_infections: Float64, spores_deposited: Float64
) -> Float64:
    """Fraction of deposited spores causing infection (infection efficiency).

    Args:
        successful_infections: Number of infection sites established.
        spores_deposited: Total spores deposited on host.

    Returns:
        Infection efficiency (0–1).
    """
    if spores_deposited <= 0.0:
        return 0.0
    return successful_infections / spores_deposited


def latent_period(
    temperature: Float64, t_min: Float64, t_opt: Float64
) -> Float64:
    """Thermal latent period estimate (Analytis-type model).

    LP ∝ 1 / ((T - Tmin) · (Topt - T))  → simplified

    Args:
        temperature: Ambient temperature (°C).
        t_min: Minimum temperature for fungal development (°C).
        t_opt: Optimum temperature (°C).

    Returns:
        Relative latent period (lower = faster sporulation).
    """
    if temperature <= t_min or temperature >= 2.0 * t_opt - t_min:
        return 1e9  # no growth
    var activity = (temperature - t_min) * (t_opt - temperature)
    if activity <= 0.0:
        return 1e9
    return 1.0 / activity


def epidemic_progress_rate(
    x1: Float64, x2: Float64, t1: Float64, t2: Float64
) -> Float64:
    """Logistic epidemic rate r (Vanderplank).

    r = ln(x2/(1-x2)) - ln(x1/(1-x1)) / (t2-t1)

    Args:
        x1: Disease intensity (fraction) at time t1.
        x2: Disease intensity (fraction) at time t2.
        t1: Time 1 (days).
        t2: Time 2 (days, > t1).

    Returns:
        Apparent infection rate r (per day).
    """
    var dt = t2 - t1
    if dt <= 0.0 or x1 <= 0.0 or x1 >= 1.0 or x2 <= 0.0 or x2 >= 1.0:
        return 0.0
    return (log(x2 / (1.0 - x2)) - log(x1 / (1.0 - x1))) / dt


def spore_germination_prob(
    temperature: Float64, t_opt: Float64, relative_humidity: Float64
) -> Float64:
    """Probability of spore germination based on temperature and humidity.

    Simplified Gaussian temperature response × linear RH requirement.

    Args:
        temperature: Ambient temperature (°C).
        t_opt: Optimum temperature for germination (°C).
        relative_humidity: Relative humidity (%).

    Returns:
        Germination probability (0–1).
    """
    if relative_humidity < 80.0:
        return 0.0  # most fungi need >80% RH
    var rh_factor = (relative_humidity - 80.0) / 20.0
    if rh_factor > 1.0:
        rh_factor = 1.0
    var sigma = 5.0  # temperature range
    var temp_factor = exp(-0.5 * ((temperature - t_opt) / sigma) ** 2.0)
    return temp_factor * rh_factor


def colony_diameter(growth_rate_mm_day: Float64, time_days: Float64) -> Float64:
    """Colony diameter from linear extension rate.

    D = 2 * r * t  (starting from small inoculum)

    Args:
        growth_rate_mm_day: Radial extension rate (mm/day).
        time_days: Incubation time (days).

    Returns:
        Colony diameter (mm).
    """
    if growth_rate_mm_day < 0.0 or time_days < 0.0:
        return 0.0
    return 2.0 * growth_rate_mm_day * time_days


def competitive_exclusion_index(
    alpha12: Float64, alpha21: Float64
) -> Float64:
    """Lotka-Volterra competitive exclusion ratio.

    CE = α12 · α21  (< 1 = coexistence, > 1 = exclusion)

    Args:
        alpha12: Competition coefficient (effect of species 2 on 1).
        alpha21: Competition coefficient (effect of species 1 on 2).

    Returns:
        Competitive exclusion index.
    """
    return alpha12 * alpha21
