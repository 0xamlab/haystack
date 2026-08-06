"""
physics.mojo — Classical physics equations. Zero Python imports.

Replaces custom physics/engineering code with pure Mojo implementations
of kinematics, energy, momentum, projectile motion, work/power, and
elastic collisions.

Public API:
  kinematic_distance     — d = v0*t + 0.5*a*t²
  kinematic_velocity     — v = v0 + a*t
  kinetic_energy         — KE = 0.5*m*v²
  potential_energy       — PE = m*g*h
  momentum               — p = m*v
  gravitational_force    — F = G*m1*m2/r²
  projectile_range       — R = v0²*sin(2θ)/g
  projectile_max_height  — H = v0²*sin²(θ)/(2g)
  projectile_time        — T = 2*v0*sin(θ)/g
  work                   — W = F*d*cos(θ)
  power                  — P = W/t
  elastic_collision_v1   — Post-collision velocity of m1
"""
from std.math import sin, cos, sqrt


# ── Constants ────────────────────────────────────────────────────────────────


comptime PI: Float64 = 3.141592653589793
comptime G_CONST: Float64 = 6.674e-11


# ── _deg_to_rad ──────────────────────────────────────────────────────────────


def _deg_to_rad(deg: Float64) -> Float64:
    """Convert degrees to radians."""
    return deg * PI / 180.0


# ── kinematic_distance ───────────────────────────────────────────────────────


def kinematic_distance(v0: Float64, a: Float64, t: Float64) -> Float64:
    """Distance under constant acceleration: d = v0*t + 0.5*a*t²."""
    return v0 * t + 0.5 * a * t * t


# ── kinematic_velocity ───────────────────────────────────────────────────────


def kinematic_velocity(v0: Float64, a: Float64, t: Float64) -> Float64:
    """Velocity under constant acceleration: v = v0 + a*t."""
    return v0 + a * t


# ── kinetic_energy ───────────────────────────────────────────────────────────


def kinetic_energy(mass: Float64, velocity: Float64) -> Float64:
    """Kinetic energy: KE = 0.5*m*v²."""
    return 0.5 * mass * velocity * velocity


# ── potential_energy ─────────────────────────────────────────────────────────


def potential_energy(mass: Float64, height: Float64, g: Float64 = 9.81) -> Float64:
    """Gravitational potential energy: PE = m*g*h."""
    return mass * g * height


# ── momentum ─────────────────────────────────────────────────────────────────


def momentum(mass: Float64, velocity: Float64) -> Float64:
    """Linear momentum: p = m*v."""
    return mass * velocity


# ── gravitational_force ──────────────────────────────────────────────────────


def gravitational_force(m1: Float64, m2: Float64, r: Float64) -> Float64:
    """Newton's law of gravitation: F = G*m1*m2/r²."""
    return G_CONST * m1 * m2 / (r * r)


# ── projectile_range ─────────────────────────────────────────────────────────


def projectile_range(v0: Float64, angle_deg: Float64, g: Float64 = 9.81) -> Float64:
    """Projectile range on flat ground: R = v0²*sin(2θ)/g."""
    var theta2 = _deg_to_rad(2.0 * angle_deg)
    return v0 * v0 * sin(theta2) / g


# ── projectile_max_height ────────────────────────────────────────────────────


def projectile_max_height(v0: Float64, angle_deg: Float64, g: Float64 = 9.81) -> Float64:
    """Projectile maximum height: H = v0²*sin²(θ)/(2g)."""
    var s = sin(_deg_to_rad(angle_deg))
    return v0 * v0 * s * s / (2.0 * g)


# ── projectile_time ──────────────────────────────────────────────────────────


def projectile_time(v0: Float64, angle_deg: Float64, g: Float64 = 9.81) -> Float64:
    """Total flight time: T = 2*v0*sin(θ)/g."""
    return 2.0 * v0 * sin(_deg_to_rad(angle_deg)) / g


# ── work ─────────────────────────────────────────────────────────────────────


def work(force: Float64, distance: Float64, angle_deg: Float64 = 0.0) -> Float64:
    """Work done: W = F*d*cos(θ)."""
    return force * distance * cos(_deg_to_rad(angle_deg))


# ── power ────────────────────────────────────────────────────────────────────


def power(work: Float64, time: Float64) -> Float64:
    """Power: P = W/t."""
    return work / time


# ── elastic_collision_v1 ─────────────────────────────────────────────────────


def elastic_collision_v1(m1: Float64, m2: Float64, v1: Float64, v2: Float64) -> Float64:
    """Post-collision velocity of m1 in a 1D elastic collision.

    v1' = ((m1 - m2)*v1 + 2*m2*v2) / (m1 + m2)
    """
    return ((m1 - m2) * v1 + 2.0 * m2 * v2) / (m1 + m2)
