"""
oceanography.mojo — Ocean science calculations. Zero Python imports.

Public API:
  seawater_density             — UNESCO EOS-80 simplified density
  buoyancy_frequency           — Brunt-Väisälä N² (stability)
  tidal_force                  — differential tidal acceleration
  geostrophic_velocity         — from pressure gradient and Coriolis
  ekman_depth                  — frictional depth of wind-driven layer
  mixed_layer_heat_flux        — Q = ρ·cp·h·ΔT/Δt
  salinity_from_chlorinity     — S = 1.80655 · Cl
  wave_celerity_shallow        — c = √(g·h)
  wave_celerity_deep           — c = g·T/(2π)
  freshwater_flux              — FW = (E - P) · A
"""
from std.math import sqrt, exp


def seawater_density(temperature: Float64, salinity: Float64) -> Float64:
    """Seawater density (simplified UNESCO EOS-80 linear fit).

    Args:
        temperature: Temperature (°C, 0–30).
        salinity: Practical salinity (PSU, 0–40).

    Returns:
        Density (kg/m³).
    """
    # Simplified from linear fit to EOS-80 at surface pressure
    return (1000.0
            - 0.0682 * temperature
            + 0.00817 * temperature * temperature * 0.01
            + 0.7814 * salinity * 0.01)


def buoyancy_frequency(
    rho_upper: Float64, rho_lower: Float64, layer_thickness: Float64
) -> Float64:
    """Brunt-Väisälä frequency: N = √(-g/ρ · ∂ρ/∂z).

    Args:
        rho_upper: Density at top of layer (kg/m³).
        rho_lower: Density at bottom of layer (kg/m³).
        layer_thickness: Layer thickness (m).

    Returns:
        Buoyancy frequency N (rad/s). Positive = stable.
    """
    if layer_thickness <= 0.0 or rho_upper <= 0.0:
        return 0.0
    var g = 9.81
    var drho_dz = (rho_lower - rho_upper) / layer_thickness
    var n2 = -g / rho_upper * drho_dz  # N² = -g/ρ * dρ/dz
    if n2 <= 0.0:
        return 0.0
    return sqrt(n2)


def tidal_force(mass_moon: Float64, distance_m: Float64, radius_earth: Float64) -> Float64:
    """Differential tidal force per unit mass at Earth's surface.

    a_tidal ≈ 2G·M·r / d³

    Args:
        mass_moon: Mass of Moon (kg).
        distance_m: Earth-Moon distance (m).
        radius_earth: Earth radius (m).

    Returns:
        Tidal acceleration (m/s²).
    """
    if distance_m <= 0.0:
        return 0.0
    var G = 6.674e-11
    return 2.0 * G * mass_moon * radius_earth / (distance_m * distance_m * distance_m)


def geostrophic_velocity(
    pressure_gradient: Float64, density: Float64, coriolis: Float64
) -> Float64:
    """Geostrophic velocity from horizontal pressure gradient.

    u_g = -(1/ρf) · ∂P/∂y

    Args:
        pressure_gradient: Pressure gradient (Pa/m).
        density: Water density (kg/m³).
        coriolis: Coriolis parameter f = 2Ω·sin(φ) (rad/s).

    Returns:
        Geostrophic velocity (m/s).
    """
    if density <= 0.0 or coriolis == 0.0:
        return 0.0
    return -pressure_gradient / (density * coriolis)


def ekman_depth(wind_stress: Float64, coriolis: Float64) -> Float64:
    """Ekman layer depth from wind stress and Coriolis.

    D_E ≈ π * √(2 A_v / f)  (simplified, using A_v ~ τ/ρ/u*)

    Args:
        wind_stress: Surface wind stress (N/m²).
        coriolis: Coriolis parameter (rad/s).

    Returns:
        Ekman depth (m).
    """
    if coriolis <= 0.0 or wind_stress <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    var rho = 1025.0  # typical seawater density
    var Av = 0.01  # eddy viscosity m²/s (typical)
    return pi * sqrt(2.0 * Av / abs(coriolis))


def mixed_layer_heat_flux(
    density: Float64, heat_capacity: Float64,
    depth: Float64, delta_temp: Float64, delta_time: Float64
) -> Float64:
    """Heat flux stored in the mixed layer: Q = ρ·cp·h·ΔT/Δt.

    Args:
        density: Seawater density (kg/m³).
        heat_capacity: Specific heat capacity (J/kg/°C).
        depth: Mixed layer depth (m).
        delta_temp: Temperature change (°C).
        delta_time: Time period (s).

    Returns:
        Heat flux (W/m²). Positive = warming.
    """
    if delta_time <= 0.0:
        return 0.0
    return density * heat_capacity * depth * delta_temp / delta_time


def salinity_from_chlorinity(chlorinity: Float64) -> Float64:
    """Practical salinity from chlorinity (Knudsen 1901).

    S = 1.80655 · Cl

    Args:
        chlorinity: Chlorinity (g/kg).

    Returns:
        Salinity (PSU).
    """
    return 1.80655 * chlorinity


def wave_celerity_shallow(depth: Float64) -> Float64:
    """Shallow-water wave celerity: c = √(g·h).

    Args:
        depth: Water depth (m).

    Returns:
        Wave speed (m/s).
    """
    if depth <= 0.0:
        return 0.0
    var g = 9.81
    return sqrt(g * depth)


def wave_celerity_deep(period: Float64) -> Float64:
    """Deep-water wave celerity: c = g·T/(2π).

    Args:
        period: Wave period (s).

    Returns:
        Phase velocity (m/s).
    """
    if period <= 0.0:
        return 0.0
    var g = 9.81
    var pi = 3.141592653589793
    return g * period / (2.0 * pi)


def freshwater_flux(
    evaporation: Float64, precipitation: Float64, area: Float64
) -> Float64:
    """Net freshwater flux from ocean surface.

    FW = (E - P) · A

    Args:
        evaporation: Evaporation rate (m/s).
        precipitation: Precipitation rate (m/s).
        area: Ocean surface area (m²).

    Returns:
        Net freshwater volume flux (m³/s). Positive = net evaporation.
    """
    return (evaporation - precipitation) * area
