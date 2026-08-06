"""
glaciology.mojo — Ice and glacier science calculations. Zero Python imports.

Public API:
  glacier_mass_balance         — B = accumulation - ablation
  ice_velocity_internal        — u = A * τ^n * h (Glen's flow law)
  basal_shear_stress           — τ = ρ_ice * g * h * sin(α)
  ablation_degree_day          — melt = DDF * PDD
  ice_thickness_from_surface   — h from surface slope (Nye's formula)
  snow_water_equivalent        — SWE = depth * density / 1000
  equilibrium_line_altitude    — ELA estimate from AAR and hypsometry
  calving_flux                 — F = U * H * W (terminus)
  sea_level_equivalent         — SLE = mass / (ocean_area * rho_ocean)
  albedo_feedback              — radiative forcing from albedo change
"""
from std.math import sin, sqrt, pow, log


def glacier_mass_balance(accumulation: Float64, ablation: Float64) -> Float64:
    """Net glacier mass balance.

    Args:
        accumulation: Annual snow/ice gain (m w.e./yr).
        ablation: Annual melt/calving loss (m w.e./yr).

    Returns:
        Net mass balance (m w.e./yr). Positive = growing.
    """
    return accumulation - ablation


def ice_velocity_internal(
    rate_factor: Float64, shear_stress: Float64, glen_n: Float64, thickness: Float64
) -> Float64:
    """Surface velocity from Glen's flow law (internal deformation only).

    u_d = 2·A/(n+1) · τ^n · h

    Args:
        rate_factor: Glen's flow law rate factor A (Pa⁻ⁿ s⁻¹).
        shear_stress: Driving shear stress (Pa).
        glen_n: Glen's flow law exponent (typically 3).
        thickness: Ice thickness (m).

    Returns:
        Deformational surface velocity (m/s).
    """
    if rate_factor <= 0.0 or shear_stress <= 0.0 or thickness <= 0.0:
        return 0.0
    return 2.0 * rate_factor / (glen_n + 1.0) * pow(shear_stress, glen_n) * thickness


def basal_shear_stress(
    ice_thickness: Float64, surface_slope_rad: Float64
) -> Float64:
    """Driving (basal) shear stress: τ = ρ_ice·g·h·sin(α).

    Args:
        ice_thickness: Ice thickness (m).
        surface_slope_rad: Ice surface slope (rad).

    Returns:
        Basal shear stress (Pa).
    """
    var rho_ice = 917.0  # kg/m³
    var g = 9.81
    return rho_ice * g * ice_thickness * sin(surface_slope_rad)


def ablation_degree_day(
    degree_day_factor: Float64, positive_degree_days: Float64
) -> Float64:
    """Ice/snow melt from positive degree-day model.

    melt = DDF · PDD

    Args:
        degree_day_factor: Degree-day factor (mm w.e./°C/day).
        positive_degree_days: Sum of daily positive temperatures (°C·day).

    Returns:
        Melt water (mm w.e.).
    """
    if degree_day_factor < 0.0 or positive_degree_days < 0.0:
        return 0.0
    return degree_day_factor * positive_degree_days


def ice_thickness_from_surface(
    surface_slope_rad: Float64, yield_stress: Float64
) -> Float64:
    """Estimate ice thickness from surface slope (Nye 1952).

    h = τ_y / (ρ·g·sin(α))

    Args:
        surface_slope_rad: Surface slope (rad).
        yield_stress: Basal yield stress (Pa, ~100 kPa typical).

    Returns:
        Ice thickness (m).
    """
    var rho_ice = 917.0
    var g = 9.81
    var denom = rho_ice * g * sin(surface_slope_rad)
    if denom <= 0.0:
        return 0.0
    return yield_stress / denom


def snow_water_equivalent(
    snow_depth_m: Float64, snow_density_kg_m3: Float64
) -> Float64:
    """Snow water equivalent: SWE = depth · density / rho_water.

    Args:
        snow_depth_m: Snow depth (m).
        snow_density_kg_m3: Snow density (kg/m³).

    Returns:
        SWE (m w.e.).
    """
    if snow_depth_m < 0.0 or snow_density_kg_m3 < 0.0:
        return 0.0
    return snow_depth_m * snow_density_kg_m3 / 1000.0


def equilibrium_line_altitude(
    accumulation_area_ratio: Float64, max_elev: Float64, min_elev: Float64
) -> Float64:
    """ELA estimate from accumulation area ratio (linear hypsometry).

    ELA ≈ max_elev - AAR·(max_elev - min_elev)

    Args:
        accumulation_area_ratio: Fraction of glacier in accumulation zone (0–1).
        max_elev: Maximum glacier elevation (m).
        min_elev: Minimum glacier elevation (m, terminus).

    Returns:
        Estimated ELA (m).
    """
    return max_elev - accumulation_area_ratio * (max_elev - min_elev)


def calving_flux(
    terminus_velocity: Float64, ice_thickness: Float64, terminus_width: Float64
) -> Float64:
    """Ice calving flux at glacier terminus: F = U·H·W.

    Args:
        terminus_velocity: Ice speed at terminus (m/yr).
        ice_thickness: Ice thickness at terminus (m).
        terminus_width: Width of calving front (m).

    Returns:
        Calving flux (m³/yr).
    """
    if terminus_velocity < 0.0 or ice_thickness < 0.0 or terminus_width < 0.0:
        return 0.0
    return terminus_velocity * ice_thickness * terminus_width


def sea_level_equivalent(
    ice_mass_kg: Float64, ocean_area_m2: Float64
) -> Float64:
    """Sea level equivalent of a given ice mass.

    SLE = mass / (A_ocean · ρ_ocean)

    Args:
        ice_mass_kg: Ice mass (kg).
        ocean_area_m2: Total ocean area (m²).

    Returns:
        Sea level rise equivalent (m).
    """
    if ocean_area_m2 <= 0.0:
        return 0.0
    var rho_ocean = 1028.0  # kg/m³
    return ice_mass_kg / (ocean_area_m2 * rho_ocean)


def albedo_feedback(
    delta_albedo: Float64, solar_constant: Float64, latitude_factor: Float64
) -> Float64:
    """Radiative forcing from surface albedo change.

    ΔF = -S₀/4 · (1 - latitude_factor) · Δα

    Args:
        delta_albedo: Change in surface albedo (fraction, + = brighter).
        solar_constant: Solar constant S₀ (W/m², ~1361).
        latitude_factor: Fractional area weighting for latitude.

    Returns:
        Radiative forcing (W/m², negative = cooling).
    """
    return -solar_constant / 4.0 * (1.0 - latitude_factor) * delta_albedo
