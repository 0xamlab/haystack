"""
game_physics.mojo — Game physics engine equations. Zero Python imports.

Pure Mojo implementations of common game-physics formulas including
kinematics, collisions, forces, projectiles, drag, springs, and
rotational dynamics.

Public API:
  position_update               — x + v*dt + 0.5*a*dt²
  velocity_update               — v + a*dt
  verlet_position               — 2*x - x_prev + a*dt²
  elastic_collision_1d          — post-collision velocity
  coefficient_of_restitution    — e = v_sep / v_approach
  kinetic_energy                — 0.5*m*v²
  gravitational_force           — G*m1*m2/r²
  projectile_range              — v0²*sin(2θ)/g
  drag_force_quadratic          — 0.5*Cd*ρ*A*v²
  spring_force                  — k*|x|
  angular_velocity_from_linear  — v/r
  moment_of_inertia_sphere      — (2/5)*m*r²
"""
from std.math import sin, abs as fabs


# ── position_update ──────────────────────────────────────────────────────────


fn position_update(
    x: Float64, v: Float64, a: Float64, dt: Float64,
) -> Float64:
    """Euler position update: x_new = x + v*dt + 0.5*a*dt².

    Args:
        x:  Current position.
        v:  Current velocity.
        a:  Acceleration.
        dt: Time step.

    Returns:
        Updated position.
    """
    return x + v * dt + 0.5 * a * dt * dt


# ── velocity_update ──────────────────────────────────────────────────────────


fn velocity_update(v: Float64, a: Float64, dt: Float64) -> Float64:
    """Euler velocity update: v_new = v + a*dt.

    Args:
        v:  Current velocity.
        a:  Acceleration.
        dt: Time step.

    Returns:
        Updated velocity.
    """
    return v + a * dt


# ── verlet_position ──────────────────────────────────────────────────────────


fn verlet_position(
    x: Float64, x_prev: Float64, a: Float64, dt: Float64,
) -> Float64:
    """Störmer-Verlet position: x_new = 2*x - x_prev + a*dt².

    Args:
        x:      Current position.
        x_prev: Previous position.
        a:      Acceleration.
        dt:     Time step.

    Returns:
        Next position.
    """
    return 2.0 * x - x_prev + a * dt * dt


# ── elastic_collision_1d ─────────────────────────────────────────────────────


fn elastic_collision_1d(
    m1: Float64, v1: Float64, m2: Float64, v2: Float64,
) -> Float64:
    """1-D elastic collision — post-collision velocity of object 1.

    v1' = ((m1-m2)*v1 + 2*m2*v2) / (m1+m2).

    Args:
        m1: Mass of object 1.
        v1: Velocity of object 1.
        m2: Mass of object 2.
        v2: Velocity of object 2.

    Returns:
        Post-collision velocity of object 1.
    """
    var total = m1 + m2
    if fabs(total) < 1e-30:
        return 0.0
    return ((m1 - m2) * v1 + 2.0 * m2 * v2) / total


# ── coefficient_of_restitution ───────────────────────────────────────────────


fn coefficient_of_restitution(
    v_sep: Float64, v_approach: Float64,
) -> Float64:
    """Coefficient of restitution: e = v_sep / v_approach.

    Args:
        v_sep:      Separation speed after collision.
        v_approach: Approach speed before collision.

    Returns:
        Coefficient of restitution e.
    """
    if fabs(v_approach) < 1e-30:
        return 0.0
    return v_sep / v_approach


# ── kinetic_energy ───────────────────────────────────────────────────────────


fn kinetic_energy(mass: Float64, velocity: Float64) -> Float64:
    """Kinetic energy: KE = 0.5 * m * v².

    Args:
        mass:     Mass (kg).
        velocity: Speed (m/s).

    Returns:
        Kinetic energy (J).
    """
    return 0.5 * mass * velocity * velocity


# ── gravitational_force ──────────────────────────────────────────────────────


fn gravitational_force(
    m1: Float64, m2: Float64, r: Float64, g: Float64,
) -> Float64:
    """Gravitational force: F = G*m1*m2/r².

    Args:
        m1: Mass 1 (kg).
        m2: Mass 2 (kg).
        r:  Distance between centres (m).
        g:  Gravitational constant G.

    Returns:
        Gravitational force (N).
    """
    if fabs(r) < 1e-30:
        return 0.0
    return g * m1 * m2 / (r * r)


# ── projectile_range ─────────────────────────────────────────────────────────


fn projectile_range(
    v0: Float64, angle: Float64, g: Float64,
) -> Float64:
    """Projectile range on flat ground: R = v0² * sin(2θ) / g.

    Args:
        v0:    Launch speed (m/s).
        angle: Launch angle (radians).
        g:     Gravitational acceleration (m/s²).

    Returns:
        Horizontal range (m).
    """
    if fabs(g) < 1e-30:
        return 0.0
    return v0 * v0 * sin(2.0 * angle) / g


# ── drag_force_quadratic ─────────────────────────────────────────────────────


fn drag_force_quadratic(
    cd: Float64, rho: Float64, a: Float64, v: Float64,
) -> Float64:
    """Quadratic drag force: F_d = 0.5 * Cd * ρ * A * v².

    Args:
        cd:  Drag coefficient.
        rho: Fluid density (kg/m³).
        a:   Reference area (m²).
        v:   Speed (m/s).

    Returns:
        Drag force magnitude (N).
    """
    return 0.5 * cd * rho * a * v * v


# ── spring_force ─────────────────────────────────────────────────────────────


fn spring_force(k: Float64, displacement: Float64) -> Float64:
    """Spring force magnitude: |F| = k * |x|.

    Args:
        k:            Spring constant (N/m).
        displacement: Displacement from equilibrium (m).

    Returns:
        Force magnitude (N).
    """
    return k * fabs(displacement)


# ── angular_velocity_from_linear ─────────────────────────────────────────────


fn angular_velocity_from_linear(v: Float64, r: Float64) -> Float64:
    """Angular velocity: ω = v / r.

    Args:
        v: Linear (tangential) speed (m/s).
        r: Radius (m).

    Returns:
        Angular velocity ω (rad/s).
    """
    if fabs(r) < 1e-30:
        return 0.0
    return v / r


# ── moment_of_inertia_sphere ────────────────────────────────────────────────


fn moment_of_inertia_sphere(mass: Float64, radius: Float64) -> Float64:
    """Moment of inertia of a solid sphere: I = (2/5) * m * r².

    Args:
        mass:   Mass (kg).
        radius: Radius (m).

    Returns:
        Moment of inertia (kg·m²).
    """
    return 0.4 * mass * radius * radius
