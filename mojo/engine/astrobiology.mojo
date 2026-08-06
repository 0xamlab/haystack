"""
astrobiology.mojo — Life in extreme environments and habitability calculations.
Zero Python imports.

Public API:
  habitable_zone_inner          — stellar flux inner limit
  habitable_zone_outer          — stellar flux outer limit
  stellar_luminosity            — from radius and temperature
  planetary_equilibrium_temp    — from albedo and stellar flux
  water_activity                — aw from solute concentration
  radiation_dose_rate           — from particle flux
  metabolism_rate_q10           — temperature scaling for extremophiles
  pressure_tolerance_depth      — equivalent depth for piezophiles
  uv_penetration_depth          — in water column or ice
  panspermia_survival_fraction  — spore survival during transit
"""
from std.math import sqrt, exp, log, pow


def habitable_zone_inner(
    stellar_luminosity_lsun: Float64
) -> Float64:
    """Inner edge of habitable zone (runaway greenhouse).

    r_inner = sqrt(L/1.1) AU

    Args:
        stellar_luminosity_lsun: Stellar luminosity in solar units.

    Returns:
        Inner habitable zone radius (AU).
    """
    return sqrt(stellar_luminosity_lsun / 1.1)


def habitable_zone_outer(
    stellar_luminosity_lsun: Float64
) -> Float64:
    """Outer edge of habitable zone (maximum greenhouse limit).

    r_outer = sqrt(L/0.36) AU

    Args:
        stellar_luminosity_lsun: Stellar luminosity in solar units.

    Returns:
        Outer habitable zone radius (AU).
    """
    return sqrt(stellar_luminosity_lsun / 0.36)


def stellar_luminosity(
    radius_rsun: Float64, temperature_k: Float64
) -> Float64:
    """Stellar luminosity from Stefan-Boltzmann law.

    L/Lsun = (R/Rsun)² × (T/Tsun)⁴

    Args:
        radius_rsun: Stellar radius in solar radii.
        temperature_k: Stellar effective temperature (K).

    Returns:
        Luminosity (solar units).
    """
    var t_ratio = temperature_k / 5778.0  # T / T_sun
    return radius_rsun * radius_rsun * pow(t_ratio, 4.0)


def planetary_equilibrium_temp(
    stellar_flux_w_m2: Float64, albedo: Float64
) -> Float64:
    """Planetary equilibrium temperature from energy balance.

    T_eq = (S × (1-A) / (4σ))^0.25

    Args:
        stellar_flux_w_m2: Stellar irradiance at planet (W/m²).
        albedo: Bond albedo (0–1).

    Returns:
        Equilibrium temperature (K).
    """
    var sigma = 5.67e-8  # Stefan-Boltzmann
    var numerator = stellar_flux_w_m2 * (1.0 - albedo) / (4.0 * sigma)
    if numerator <= 0.0:
        return 0.0
    return pow(numerator, 0.25)


def water_activity(
    solute_molality: Float64, vant_hoff_factor: Float64
) -> Float64:
    """Water activity for extremophile habitability.

    aw ≈ 1 - i × m × 0.018  (van't Hoff approximation)

    Args:
        solute_molality: Solute concentration (mol/kg water).
        vant_hoff_factor: i factor for dissociation (1 for non-electrolyte, 2 for NaCl).

    Returns:
        Water activity aw (0–1; >0.6 required for most life).
    """
    var aw = 1.0 - vant_hoff_factor * solute_molality * 0.018
    if aw < 0.0:
        return 0.0
    return aw


def radiation_dose_rate(
    particle_flux: Float64, particle_energy_mev: Float64, linear_energy_transfer: Float64
) -> Float64:
    """Absorbed radiation dose rate from particle flux.

    dose_rate = flux × E × LET (simplified, in Gy/s units)

    Args:
        particle_flux: Particle flux (particles/cm²/s).
        particle_energy_mev: Particle energy (MeV).
        linear_energy_transfer: LET (MeV/cm in water, ~0.2 for protons).

    Returns:
        Dose rate (mGy/day, scaled).
    """
    return particle_flux * particle_energy_mev * linear_energy_transfer * 8.64e4 * 1e-3


def metabolism_rate_q10(
    rate_ref: Float64, temperature: Float64, temperature_ref: Float64, q10: Float64
) -> Float64:
    """Metabolic rate temperature scaling (Q10 rule).

    rate = rate_ref × Q10^((T-Tref)/10)

    Args:
        rate_ref: Reference metabolic rate.
        temperature: Actual temperature (°C).
        temperature_ref: Reference temperature (°C).
        q10: Temperature sensitivity coefficient (typically 2–3).

    Returns:
        Metabolic rate at temperature T.
    """
    return rate_ref * pow(q10, (temperature - temperature_ref) / 10.0)


def pressure_tolerance_depth(
    max_pressure_atm: Float64
) -> Float64:
    """Equivalent ocean depth for piezophile pressure tolerance.

    depth = (P_max - 1) × 10  m

    Args:
        max_pressure_atm: Maximum tolerated pressure (atm).

    Returns:
        Equivalent ocean depth (m; ~600 atm for known piezophiles = 6000 m).
    """
    return (max_pressure_atm - 1.0) * 10.0


def uv_penetration_depth(
    surface_irradiance: Float64, attenuation_coefficient: Float64
) -> Float64:
    """Depth at which UV is reduced to 1% of surface value.

    depth = ln(100) / k_uv = 4.6 / k

    Args:
        surface_irradiance: Surface UV irradiance (W/m²).
        attenuation_coefficient: UV attenuation k (m⁻¹).

    Returns:
        1% depth (m).
    """
    if attenuation_coefficient <= 0.0:
        return 0.0
    return log(100.0) / attenuation_coefficient


def panspermia_survival_fraction(
    transit_time_yr: Float64, inactivation_rate: Float64
) -> Float64:
    """Fraction of spores surviving interplanetary transit.

    f = exp(-k × t)

    Args:
        transit_time_yr: Transit duration (years).
        inactivation_rate: First-order inactivation rate (per year).

    Returns:
        Surviving fraction (0–1).
    """
    return exp(-inactivation_rate * transit_time_yr)
