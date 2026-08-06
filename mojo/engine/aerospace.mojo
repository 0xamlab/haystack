"""
aerospace.mojo — Aerospace Engineering Library. Zero Python imports.

Provides functions for aerodynamics, propulsion, orbital mechanics, and
flight performance calculations.

Public API:
  dynamic_pressure      — q = 0.5 * ρ * v²
  lift_force            — L = Cl * q * S
  drag_force            — D = Cd * q * S
  lift_to_drag_ratio    — L/D ratio
  thrust_required       — T = W / (L/D)
  specific_impulse      — Isp = T / (m_dot * g0)
  tsiolkovsky_delta_v   — ΔV = Isp * g0 * ln(m0/mf)
  mach_number           — M = v / a
  speed_of_sound        — a = sqrt(γ * R * T)
  orbital_velocity      — v = sqrt(μ / r)
  escape_velocity       — v_esc = sqrt(2 * μ / r)
  hohmann_delta_v       — Total ΔV for Hohmann transfer
"""

from std.math import sqrt, log as _ln


# ── Constants ────────────────────────────────────────────────────────────────


comptime G0: Float64 = 9.80665  # standard gravity m/s²


# ── dynamic_pressure ─────────────────────────────────────────────────────────


def dynamic_pressure(density: Float64, velocity: Float64) -> Float64:
    """Dynamic pressure: q = 0.5 * ρ * v²."""
    return 0.5 * density * velocity * velocity


# ── lift_force ───────────────────────────────────────────────────────────────


def lift_force(cl: Float64, q: Float64, wing_area: Float64) -> Float64:
    """Lift force: L = Cl * q * S."""
    return cl * q * wing_area


# ── drag_force ───────────────────────────────────────────────────────────────


def drag_force(cd: Float64, q: Float64, wing_area: Float64) -> Float64:
    """Drag force: D = Cd * q * S."""
    return cd * q * wing_area


# ── lift_to_drag_ratio ───────────────────────────────────────────────────────


def lift_to_drag_ratio(cl: Float64, cd: Float64) -> Float64:
    """Lift-to-drag ratio: L/D = Cl / Cd."""
    if cd == 0.0:
        return 0.0
    return cl / cd


# ── thrust_required ──────────────────────────────────────────────────────────


def thrust_required(weight: Float64, ld_ratio: Float64) -> Float64:
    """Thrust required for level flight: T = W / (L/D)."""
    if ld_ratio == 0.0:
        return 0.0
    return weight / ld_ratio


# ── specific_impulse ─────────────────────────────────────────────────────────


def specific_impulse(
    thrust: Float64, mass_flow_rate: Float64
) -> Float64:
    """Specific impulse: Isp = T / (m_dot * g0)."""
    var denom = mass_flow_rate * G0
    if denom == 0.0:
        return 0.0
    return thrust / denom


# ── tsiolkovsky_delta_v ──────────────────────────────────────────────────────


def tsiolkovsky_delta_v(
    isp: Float64, mass_initial: Float64, mass_final: Float64
) -> Float64:
    """Tsiolkovsky rocket equation: ΔV = Isp * g0 * ln(m0/mf)."""
    if mass_final <= 0.0 or mass_initial <= 0.0:
        return 0.0
    return isp * G0 * _ln(mass_initial / mass_final)


# ── mach_number ──────────────────────────────────────────────────────────────


def mach_number(velocity: Float64, speed_of_sound_val: Float64) -> Float64:
    """Mach number: M = v / a."""
    if speed_of_sound_val == 0.0:
        return 0.0
    return velocity / speed_of_sound_val


# ── speed_of_sound ───────────────────────────────────────────────────────────


def speed_of_sound(
    gamma: Float64, gas_constant: Float64, temperature: Float64
) -> Float64:
    """Speed of sound in ideal gas: a = sqrt(γ * R * T)."""
    return sqrt(gamma * gas_constant * temperature)


# ── orbital_velocity ─────────────────────────────────────────────────────────


def orbital_velocity(mu: Float64, radius: Float64) -> Float64:
    """Circular orbital velocity: v = sqrt(μ / r)."""
    if radius <= 0.0:
        return 0.0
    return sqrt(mu / radius)


# ── escape_velocity ──────────────────────────────────────────────────────────


def escape_velocity(mu: Float64, radius: Float64) -> Float64:
    """Escape velocity: v_esc = sqrt(2 * μ / r)."""
    if radius <= 0.0:
        return 0.0
    return sqrt(2.0 * mu / radius)


# ── hohmann_delta_v ──────────────────────────────────────────────────────────


def hohmann_delta_v(mu: Float64, r1: Float64, r2: Float64) -> Float64:
    """Total ΔV for Hohmann transfer orbit between two circular orbits.

    ΔV1 = sqrt(μ/r1) * (sqrt(2*r2/(r1+r2)) - 1)
    ΔV2 = sqrt(μ/r2) * (1 - sqrt(2*r1/(r1+r2)))
    Total = |ΔV1| + |ΔV2|
    """
    if r1 <= 0.0 or r2 <= 0.0:
        return 0.0
    var v1 = sqrt(mu / r1)
    var v2 = sqrt(mu / r2)
    var sum_r = r1 + r2
    var dv1 = v1 * (sqrt(2.0 * r2 / sum_r) - 1.0)
    var dv2 = v2 * (1.0 - sqrt(2.0 * r1 / sum_r))
    # Take absolute values
    if dv1 < 0.0:
        dv1 = -dv1
    if dv2 < 0.0:
        dv2 = -dv2
    return dv1 + dv2
