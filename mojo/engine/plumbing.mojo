"""
plumbing.mojo — Plumbing Engineering Library. Zero Python imports.

Provides pipe flow velocity, Reynolds number, friction factor, head loss,
pump power, water demand, pipe sizing, and water hammer calculations.

Public API:
  pipe_flow_velocity           — v = 4*Q/(π*d²)
  reynolds_number              — Re = v*d/ν
  friction_factor_laminar      — f = 64/Re
  head_loss_darcy              — hf = f*L/d * v²/(2g)
  head_loss_minor              — hm = K*v²/(2g)
  total_dynamic_head           — TDH = static + friction + minor
  pump_power                   — P = ρ*g*Q*H/η (watts)
  water_demand_fixture_units   — FU = n * fu
  pipe_sizing_velocity_method  — d = sqrt(4*Q/(π*v_max))
  thermal_expansion_pipe       — ΔL = α*L*ΔT
  water_hammer_pressure        — ΔP = ρ*v*c
  drainage_slope_minimum       — slope based on diameter
"""
from std.math import sqrt, abs as fabs


# ── pipe_flow_velocity ───────────────────────────────────────────────────────


def pipe_flow_velocity(
    flow_rate: Float64, diameter: Float64
) -> Float64:
    """Flow velocity: v = 4*Q/(π*d²).

    Args:
        flow_rate: Volumetric flow rate (m³/s).
        diameter: Internal pipe diameter (m).

    Returns:
        Flow velocity (m/s), or 0 if diameter is zero.
    """
    comptime PI: Float64 = 3.141592653589793
    if fabs(diameter) < 1e-30:
        return 0.0
    return 4.0 * flow_rate / (PI * diameter * diameter)


# ── reynolds_number ──────────────────────────────────────────────────────────


def reynolds_number(
    velocity: Float64, diameter: Float64, viscosity: Float64
) -> Float64:
    """Reynolds number: Re = v*d/ν.

    Args:
        velocity: Flow velocity (m/s).
        diameter: Pipe diameter (m).
        viscosity: Kinematic viscosity (m²/s).

    Returns:
        Reynolds number (dimensionless), or 0 if viscosity is zero.
    """
    if fabs(viscosity) < 1e-30:
        return 0.0
    return velocity * diameter / viscosity


# ── friction_factor_laminar ──────────────────────────────────────────────────


def friction_factor_laminar(re: Float64) -> Float64:
    """Laminar friction factor: f = 64/Re.

    Args:
        re: Reynolds number.

    Returns:
        Darcy friction factor, or 0 if Re is zero.
    """
    if fabs(re) < 1e-30:
        return 0.0
    return 64.0 / re


# ── head_loss_darcy ──────────────────────────────────────────────────────────


def head_loss_darcy(
    f: Float64, length: Float64, diameter: Float64,
    velocity: Float64, g: Float64,
) -> Float64:
    """Darcy-Weisbach head loss: hf = f*L/d * v²/(2g).

    Args:
        f: Darcy friction factor.
        length: Pipe length (m).
        diameter: Pipe diameter (m).
        velocity: Flow velocity (m/s).
        g: Gravitational acceleration (m/s²).

    Returns:
        Friction head loss (m), or 0 if diameter or g is zero.
    """
    var denom = diameter * 2.0 * g
    if fabs(denom) < 1e-30:
        return 0.0
    return f * length / diameter * velocity * velocity / (2.0 * g)


# ── head_loss_minor ──────────────────────────────────────────────────────────


def head_loss_minor(
    k: Float64, velocity: Float64, g: Float64
) -> Float64:
    """Minor head loss: hm = K*v²/(2g).

    Args:
        k: Loss coefficient.
        velocity: Flow velocity (m/s).
        g: Gravitational acceleration (m/s²).

    Returns:
        Minor head loss (m), or 0 if g is zero.
    """
    if fabs(g) < 1e-30:
        return 0.0
    return k * velocity * velocity / (2.0 * g)


# ── total_dynamic_head ───────────────────────────────────────────────────────


def total_dynamic_head(
    static_head: Float64, friction_loss: Float64, minor_loss: Float64
) -> Float64:
    """Total dynamic head: TDH = static + friction + minor.

    Args:
        static_head: Static head (m).
        friction_loss: Friction head loss (m).
        minor_loss: Minor head loss (m).

    Returns:
        Total dynamic head (m).
    """
    return static_head + friction_loss + minor_loss


# ── pump_power ───────────────────────────────────────────────────────────────


def pump_power(
    flow_rate: Float64, head: Float64, density: Float64,
    gravity: Float64, efficiency: Float64,
) -> Float64:
    """Pump power: P = ρ*g*Q*H/η (watts).

    Args:
        flow_rate: Flow rate (m³/s).
        head: Total head (m).
        density: Fluid density (kg/m³).
        gravity: Gravitational acceleration (m/s²).
        efficiency: Pump efficiency (0-1).

    Returns:
        Power in watts, or 0 if efficiency is zero.
    """
    if fabs(efficiency) < 1e-30:
        return 0.0
    return density * gravity * flow_rate * head / efficiency


# ── water_demand_fixture_units ───────────────────────────────────────────────


def water_demand_fixture_units(
    n_fixtures: Float64, fu_per_fixture: Float64
) -> Float64:
    """Water demand in fixture units: FU = n * fu.

    Args:
        n_fixtures: Number of fixtures.
        fu_per_fixture: Fixture units per fixture.

    Returns:
        Total fixture units.
    """
    return n_fixtures * fu_per_fixture


# ── pipe_sizing_velocity_method ──────────────────────────────────────────────


def pipe_sizing_velocity_method(
    flow_rate: Float64, max_velocity: Float64
) -> Float64:
    """Pipe diameter from velocity: d = sqrt(4*Q/(π*v_max)).

    Args:
        flow_rate: Design flow rate (m³/s).
        max_velocity: Maximum allowable velocity (m/s).

    Returns:
        Minimum pipe diameter (m), or 0 if max_velocity is zero.
    """
    comptime PI: Float64 = 3.141592653589793
    if fabs(max_velocity) < 1e-30:
        return 0.0
    return sqrt(4.0 * flow_rate / (PI * max_velocity))


# ── thermal_expansion_pipe ───────────────────────────────────────────────────


def thermal_expansion_pipe(
    alpha: Float64, length: Float64, delta_t: Float64
) -> Float64:
    """Thermal expansion: ΔL = α*L*ΔT.

    Args:
        alpha: Coefficient of thermal expansion (1/°C).
        length: Pipe length (m).
        delta_t: Temperature change (°C).

    Returns:
        Change in length (m).
    """
    return alpha * length * delta_t


# ── water_hammer_pressure ────────────────────────────────────────────────────


def water_hammer_pressure(
    density: Float64, velocity: Float64, wave_speed: Float64
) -> Float64:
    """Water hammer pressure: ΔP = ρ*v*c.

    Args:
        density: Fluid density (kg/m³).
        velocity: Flow velocity change (m/s).
        wave_speed: Pressure wave speed (m/s).

    Returns:
        Pressure surge (Pa).
    """
    return density * velocity * wave_speed


# ── drainage_slope_minimum ───────────────────────────────────────────────────


def drainage_slope_minimum(pipe_diameter_inches: Float64) -> Float64:
    """Minimum drainage slope (simplified).

    slope = 0.125 in/ft for pipes < 3 inches,
    slope = 0.25 in/ft for pipes >= 3 inches.

    Args:
        pipe_diameter_inches: Pipe diameter in inches.

    Returns:
        Minimum slope (inches per foot).
    """
    if pipe_diameter_inches >= 3.0:
        return 0.25
    return 0.125
