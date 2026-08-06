"""
marine.mojo — Marine Science / Oceanography Library. Zero Python imports.

Pure Mojo implementations of fundamental oceanographic equations including
wave mechanics, tidal dynamics, Coriolis effects, density estimation,
and pressure calculations.

Public API:
  seawater_density               — simplified density from T, S
  wave_speed_deep                — deep-water wave speed
  wave_speed_shallow             — shallow-water wave speed
  wave_period                    — T = λ / c
  significant_wave_height        — Hs = 4*sqrt(energy_density)
  tidal_range                    — Range = high - low
  mixed_layer_depth_estimate     — MLD ≈ 0.5*wind² + 10
  ekman_depth                    — D_E = π*sqrt(2*Av/f)
  coriolis_parameter             — f = 2*Ω*sin(φ)
  buoyancy_frequency             — N = sqrt(-g/ρ0 * dρ/dz)
  salinity_from_conductivity     — simplified PSU from C, T
  ocean_pressure_at_depth        — P = ρ*g*d
"""
from std.math import sqrt, sin, abs as fabs

comptime PI: Float64 = 3.141592653589793
comptime OMEGA: Float64 = 7.2921e-5


# ── seawater_density ─────────────────────────────────────────────────────────


def seawater_density(temperature: Float64, salinity: Float64) -> Float64:
    """ρ ≈ 1025 + 0.7*(S-35) - 0.15*(T-10)  (simplified kg/m³)."""
    return 1025.0 + 0.7 * (salinity - 35.0) - 0.15 * (temperature - 10.0)


# ── wave_speed_deep ──────────────────────────────────────────────────────────


def wave_speed_deep(wavelength: Float64, g: Float64) -> Float64:
    """Deep-water wave speed: c = sqrt(g*λ/(2π))."""
    return sqrt(g * wavelength / (2.0 * PI))


# ── wave_speed_shallow ───────────────────────────────────────────────────────


def wave_speed_shallow(depth: Float64, g: Float64) -> Float64:
    """Shallow-water wave speed: c = sqrt(g*d)."""
    return sqrt(g * depth)


# ── wave_period ──────────────────────────────────────────────────────────────


def wave_period(wavelength: Float64, speed: Float64) -> Float64:
    """T = λ / c."""
    if speed == 0.0:
        return 0.0
    return wavelength / speed


# ── significant_wave_height ──────────────────────────────────────────────────


def significant_wave_height(energy_density: Float64) -> Float64:
    """Hs = 4 * sqrt(energy_density)  (simplified)."""
    return 4.0 * sqrt(energy_density)


# ── tidal_range ──────────────────────────────────────────────────────────────


def tidal_range(high_tide: Float64, low_tide: Float64) -> Float64:
    """Range = high_tide - low_tide."""
    return high_tide - low_tide


# ── mixed_layer_depth_estimate ───────────────────────────────────────────────


def mixed_layer_depth_estimate(
    wind_speed: Float64, latitude: Float64
) -> Float64:
    """MLD ≈ 0.5 * wind² + 10  (simplified metres)."""
    return 0.5 * wind_speed * wind_speed + 10.0


# ── ekman_depth ──────────────────────────────────────────────────────────────


def ekman_depth(
    wind_stress: Float64, coriolis: Float64, eddy_viscosity: Float64
) -> Float64:
    """D_E = π * sqrt(2 * Av / f).

    Uses eddy_viscosity (Av) and coriolis parameter (f).
    wind_stress is accepted for API consistency but not used in the
    simplified Ekman depth formula.
    """
    if coriolis == 0.0:
        return 0.0
    var f_abs = fabs(coriolis)
    return PI * sqrt(2.0 * eddy_viscosity / f_abs)


# ── coriolis_parameter ───────────────────────────────────────────────────────


def coriolis_parameter(latitude_deg: Float64) -> Float64:
    """f = 2 * Ω * sin(φ)  where Ω = 7.2921e-5 rad/s."""
    var phi = latitude_deg * PI / 180.0
    return 2.0 * OMEGA * sin(phi)


# ── buoyancy_frequency ───────────────────────────────────────────────────────


def buoyancy_frequency(
    drho_dz: Float64, rho0: Float64, g: Float64
) -> Float64:
    """N = sqrt(-g/ρ0 * dρ/dz).

    drho_dz is typically negative (density decreases upward),
    so -g/ρ0 * drho_dz should be positive for a stable water column.
    Returns 0 if the argument would be negative (unstable).
    """
    var val = -g / rho0 * drho_dz
    if val < 0.0:
        return 0.0
    return sqrt(val)


# ── salinity_from_conductivity ───────────────────────────────────────────────


def salinity_from_conductivity(
    conductivity: Float64, temperature: Float64
) -> Float64:
    """S ≈ 0.5 * C * (1 - 0.02*(T-25))  (simplified PSU)."""
    return 0.5 * conductivity * (1.0 - 0.02 * (temperature - 25.0))


# ── ocean_pressure_at_depth ──────────────────────────────────────────────────


def ocean_pressure_at_depth(
    depth: Float64, density: Float64, g: Float64
) -> Float64:
    """P = ρ * g * d  (hydrostatic pressure in Pa)."""
    return density * g * depth
