"""
tribology.mojo — Tribology (Friction & Wear) Library. Zero Python imports.

Pure Mojo implementations of friction, wear, lubrication, and contact mechanics
functions for engineering analysis.

Public API:
  coulomb_friction_force    — F = μ * N
  kinetic_friction          — F_k = μ_k * N
  static_friction_max       — F_s_max = μ_s * N
  coefficient_of_friction   — μ = F / N
  hertz_contact_pressure    — p0 = 3F / (2πa²)
  archard_wear_volume       — V = k*F*d / H
  bearing_pressure          — p = F / A
  sommerfeld_number         — S = (μ*N/P) * (R/c)²
  stribeck_parameter        — η*v / p
  flash_temperature_rise    — ΔT = μ*F*v / (k*L)
  lubrication_film_thickness — h ∝ (η*U/W)^(2/3)
  friction_power_loss       — P = F * v
"""
from std.math import exp, log, sqrt


# ── Constants ─────────────────────────────────────────────────────────────────

comptime PI: Float64 = 3.14159265358979323846


# ── coulomb_friction_force ────────────────────────────────────────────────────


def coulomb_friction_force(mu: Float64, normal_force: Float64) -> Float64:
    """Coulomb friction: F = μ * N."""
    return mu * normal_force


# ── kinetic_friction ──────────────────────────────────────────────────────────


def kinetic_friction(mu_k: Float64, normal_force: Float64) -> Float64:
    """Kinetic friction force: F_k = μ_k * N."""
    return mu_k * normal_force


# ── static_friction_max ───────────────────────────────────────────────────────


def static_friction_max(mu_s: Float64, normal_force: Float64) -> Float64:
    """Maximum static friction: F_s_max = μ_s * N."""
    return mu_s * normal_force


# ── coefficient_of_friction ───────────────────────────────────────────────────


def coefficient_of_friction(
    friction_force: Float64, normal_force: Float64
) -> Float64:
    """Coefficient of friction: μ = F / N."""
    return friction_force / normal_force


# ── hertz_contact_pressure ────────────────────────────────────────────────────


def hertz_contact_pressure(force: Float64, contact_radius: Float64) -> Float64:
    """Hertz max contact pressure: p0 = 3F / (2πa²)."""
    return 3.0 * force / (2.0 * PI * contact_radius * contact_radius)


# ── archard_wear_volume ──────────────────────────────────────────────────────


def archard_wear_volume(
    k: Float64, load: Float64, sliding_distance: Float64, hardness: Float64
) -> Float64:
    """Archard wear equation: V = k*F*d / H."""
    return k * load * sliding_distance / hardness


# ── bearing_pressure ─────────────────────────────────────────────────────────


def bearing_pressure(load: Float64, projected_area: Float64) -> Float64:
    """Bearing pressure: p = F / A."""
    return load / projected_area


# ── sommerfeld_number ─────────────────────────────────────────────────────────


def sommerfeld_number(
    viscosity: Float64,
    speed: Float64,
    load_per_area: Float64,
    clearance_ratio: Float64,
) -> Float64:
    """Sommerfeld number: S = (μ*N/P) * (R/c)² = (viscosity*speed/load_per_area) / (clearance_ratio²)."""
    return (viscosity * speed / load_per_area) / (
        clearance_ratio * clearance_ratio
    )


# ── stribeck_parameter ───────────────────────────────────────────────────────


def stribeck_parameter(
    viscosity: Float64, velocity: Float64, pressure: Float64
) -> Float64:
    """Stribeck parameter: η*v / p."""
    return viscosity * velocity / pressure


# ── flash_temperature_rise ────────────────────────────────────────────────────


def flash_temperature_rise(
    mu: Float64,
    load: Float64,
    velocity: Float64,
    thermal_conductivity: Float64,
    contact_length: Float64,
) -> Float64:
    """Flash temperature rise: ΔT = μ*F*v / (k*L)."""
    return mu * load * velocity / (thermal_conductivity * contact_length)


# ── lubrication_film_thickness ────────────────────────────────────────────────


def lubrication_film_thickness(
    viscosity: Float64, velocity: Float64, load_per_width: Float64
) -> Float64:
    """Simplified film thickness: h ∝ (η*U/W)^(2/3).
    Returns dimensionless proportional value."""
    var ratio = viscosity * velocity / load_per_width
    # (x)^(2/3) = exp((2/3)*ln(x))
    return exp(2.0 / 3.0 * log(ratio))


# ── friction_power_loss ───────────────────────────────────────────────────────


def friction_power_loss(friction_force: Float64, velocity: Float64) -> Float64:
    """Power dissipated by friction: P = F * v."""
    return friction_force * velocity
