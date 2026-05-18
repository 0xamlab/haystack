"""
fluid.mojo — Fluid dynamics basics. Zero Python imports.

Replaces custom CFD code with pure Mojo implementations of Reynolds number,
Bernoulli equation, Darcy-Weisbach, drag, buoyancy, and related computations.

Public API:
  reynolds_number        — Re = v*L/ν
  is_turbulent           — Re > 4000
  bernoulli_velocity     — Velocity from pressure difference
  friction_factor_laminar — f = 64/Re
  darcy_weisbach         — Pressure drop ΔP
  flow_rate              — Q = v*A
  pipe_velocity          — v = Q / (π*d²/4)
  hydraulic_diameter     — D_h = 4*A/P for rectangular duct
  mach_number            — M = v/c
  drag_force             — F_d = 0.5*cd*ρ*v²*A
  buoyancy_force         — F_b = ρ*V*g
  stokes_drag            — F = 6πμrv
"""
from std.math import sqrt


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime G_ACCEL: Float64 = 9.81


# ── reynolds_number ──────────────────────────────────────────────────────────


fn reynolds_number(velocity: Float64, length: Float64, viscosity: Float64) -> Float64:
    """Reynolds number: Re = v*L/ν (kinematic viscosity, density=1)."""
    return velocity * length / viscosity


# ── is_turbulent ─────────────────────────────────────────────────────────────


fn is_turbulent(re: Float64) -> Bool:
    """Flow is turbulent if Re > 4000."""
    return re > 4000.0


# ── bernoulli_velocity ───────────────────────────────────────────────────────


fn bernoulli_velocity(
    p1: Float64, p2: Float64, rho: Float64, z1: Float64 = 0.0, z2: Float64 = 0.0
) -> Float64:
    """Velocity from Bernoulli: v = sqrt(2*(p1-p2)/rho + 2*g*(z1-z2))."""
    var term = 2.0 * (p1 - p2) / rho + 2.0 * G_ACCEL * (z1 - z2)
    if term < 0.0:
        return 0.0
    return sqrt(term)


# ── friction_factor_laminar ──────────────────────────────────────────────────


fn friction_factor_laminar(re: Float64) -> Float64:
    """Laminar friction factor: f = 64/Re."""
    return 64.0 / re


# ── darcy_weisbach ───────────────────────────────────────────────────────────


fn darcy_weisbach(
    f: Float64, L: Float64, D: Float64, v: Float64, rho: Float64
) -> Float64:
    """Darcy-Weisbach pressure drop: ΔP = f*(L/D)*(ρv²/2)."""
    return f * (L / D) * (rho * v * v / 2.0)


# ── flow_rate ────────────────────────────────────────────────────────────────


fn flow_rate(velocity: Float64, area: Float64) -> Float64:
    """Volume flow rate: Q = v*A."""
    return velocity * area


# ── pipe_velocity ────────────────────────────────────────────────────────────


fn pipe_velocity(flow_rate: Float64, diameter: Float64) -> Float64:
    """Pipe velocity: v = Q / (π*d²/4)."""
    var area = PI * diameter * diameter / 4.0
    return flow_rate / area


# ── hydraulic_diameter ───────────────────────────────────────────────────────


fn hydraulic_diameter(width: Float64, height: Float64) -> Float64:
    """Hydraulic diameter for rectangular duct: D_h = 4*A/P."""
    var area = width * height
    var perimeter = 2.0 * (width + height)
    return 4.0 * area / perimeter


# ── mach_number ──────────────────────────────────────────────────────────────


fn mach_number(velocity: Float64, speed_of_sound: Float64 = 343.0) -> Float64:
    """Mach number: M = v/c."""
    return velocity / speed_of_sound


# ── drag_force ───────────────────────────────────────────────────────────────


fn drag_force(cd: Float64, rho: Float64, v: Float64, area: Float64) -> Float64:
    """Drag force: F_d = 0.5*cd*ρ*v²*A."""
    return 0.5 * cd * rho * v * v * area


# ── buoyancy_force ───────────────────────────────────────────────────────────


fn buoyancy_force(
    rho_fluid: Float64, volume: Float64, g: Float64 = 9.81
) -> Float64:
    """Buoyancy force: F_b = ρ*V*g."""
    return rho_fluid * volume * g


# ── stokes_drag ──────────────────────────────────────────────────────────────


fn stokes_drag(mu: Float64, radius: Float64, velocity: Float64) -> Float64:
    """Stokes drag on a sphere: F = 6πμrv."""
    return 6.0 * PI * mu * radius * velocity
