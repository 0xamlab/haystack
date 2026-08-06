"""
volcanology.mojo — Volcanology Library. Zero Python imports.

Pure Mojo implementations of simplified volcanological equations including
VEI energy estimation, lava flow velocity, eruption column height,
tephra fallout, magma viscosity, effusion rate, lahar velocity,
gas emissions, recurrence interval, alert level, pyroclastic flow
runout, and caldera collapse volume.

Public API:
  vei_energy_estimate          — energy from VEI (joules)
  lava_flow_velocity           — simplified lava flow speed
  eruption_column_height       — Morton-based column height (km)
  tephra_fallout_thickness     — thickness from volume/area
  magma_viscosity_estimate     — viscosity from SiO₂ content
  effusion_rate                — volumetric effusion rate
  lahar_velocity               — simplified lahar speed
  volcanic_gas_emission_rate   — gas emission rate
  recurrence_interval          — average recurrence interval
  alert_level                  — max of 3 indicators (0-4)
  pyroclastic_flow_runout      — runout distance (km)
  caldera_collapse_volume      — caldera volume (km³)
"""
from std.math import sqrt, sin, pow, abs as fabs


# ── vei_energy_estimate ──────────────────────────────────────────────────────


def vei_energy_estimate(vei: Float64) -> Float64:
    """E ≈ 10^(vei + 7)  joules (simplified)."""
    return pow(10.0, vei + 7.0)


# ── lava_flow_velocity ───────────────────────────────────────────────────────


def lava_flow_velocity(slope_deg: Float64, viscosity: Float64, thickness: Float64,
                      density: Float64, g: Float64) -> Float64:
    """v = ρ·g·sin(θ)·h² / (3·μ)  (simplified Jeffreys equation)."""
    comptime PI: Float64 = 3.141592653589793
    var theta_rad = slope_deg * PI / 180.0
    return density * g * sin(theta_rad) * thickness * thickness / (3.0 * viscosity)


# ── eruption_column_height ───────────────────────────────────────────────────


def eruption_column_height(mass_rate: Float64, g: Float64) -> Float64:
    """H ≈ 0.25 * mass_rate^0.25  (km, simplified Morton model)."""
    return 0.25 * pow(mass_rate, 0.25)


# ── tephra_fallout_thickness ─────────────────────────────────────────────────


def tephra_fallout_thickness(volume: Float64, area: Float64) -> Float64:
    """T = V / A  (metres)."""
    return volume / area


# ── magma_viscosity_estimate ─────────────────────────────────────────────────


def magma_viscosity_estimate(sio2_pct: Float64) -> Float64:
    """η ≈ 10^((sio2 - 40) * 0.1)  (Pa·s, highly simplified)."""
    return pow(10.0, (sio2_pct - 40.0) * 0.1)


# ── effusion_rate ────────────────────────────────────────────────────────────


def effusion_rate(volume: Float64, time_seconds: Float64) -> Float64:
    """Q = V / t  (m³/s)."""
    return volume / time_seconds


# ── lahar_velocity ───────────────────────────────────────────────────────────


def lahar_velocity(slope: Float64, depth: Float64) -> Float64:
    """v ≈ sqrt(g · depth · slope)  (simplified)."""
    return sqrt(9.81 * depth * slope)


# ── volcanic_gas_emission_rate ───────────────────────────────────────────────


def volcanic_gas_emission_rate(concentration: Float64, plume_flux: Float64) -> Float64:
    """Rate = concentration * plume_flux  (tonnes/day)."""
    return concentration * plume_flux


# ── recurrence_interval ──────────────────────────────────────────────────────


def recurrence_interval(n_events: Float64, time_span: Float64) -> Float64:
    """RI = span / events  (years)."""
    return time_span / n_events


# ── alert_level ──────────────────────────────────────────────────────────────


def alert_level(seismicity: Float64, deformation: Float64, gas_emission: Float64) -> Float64:
    """Level = max of 3 indicators  (0-4 scale)."""
    var m = seismicity
    if deformation > m:
        m = deformation
    if gas_emission > m:
        m = gas_emission
    return m


# ── pyroclastic_flow_runout ──────────────────────────────────────────────────


def pyroclastic_flow_runout(column_height: Float64, density_ratio: Float64) -> Float64:
    """R ≈ height * density_ratio * 10  (km, simplified)."""
    return column_height * density_ratio * 10.0


# ── caldera_collapse_volume ──────────────────────────────────────────────────


def caldera_collapse_volume(diameter_km: Float64, depth_km: Float64) -> Float64:
    """V = π * (d/2)² * depth  (km³)."""
    comptime PI: Float64 = 3.141592653589793
    var r = diameter_km / 2.0
    return PI * r * r * depth_km
