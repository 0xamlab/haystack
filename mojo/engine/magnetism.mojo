"""
magnetism.mojo — Magnetic field and force calculations. Zero Python imports.

Public API:
  biot_savart_infinite_wire    — B from long straight current-carrying wire
  magnetic_force_wire          — F on current-carrying wire in B field
  solenoid_field               — B inside a solenoid
  toroid_field                 — B inside a toroidal coil
  magnetic_flux                — Φ = B·A·cos(θ)
  inductance_solenoid          — L = μ0·μr·N²·A/l
  magnetic_energy_density      — u = B²/(2·μ0)
  cyclotron_radius             — r = mv/(qB)
  larmor_frequency             — f = qB/(2π·m)
  hall_voltage                 — V_H = I·B/(n·q·t)
"""
from std.math import cos, sqrt


fn biot_savart_infinite_wire(current: Float64, distance: Float64) -> Float64:
    """Magnetic field from an infinite straight wire (Biot-Savart / Ampere).

    B = μ0·I / (2π·r)

    Args:
        current: Current in wire (A).
        distance: Perpendicular distance from wire (m).

    Returns:
        Magnetic field magnitude (T).
    """
    if distance <= 0.0:
        return 0.0
    var mu0 = 1.2566370614e-6  # H/m
    var pi = 3.141592653589793
    return mu0 * current / (2.0 * pi * distance)


fn magnetic_force_wire(
    current: Float64, length: Float64, field: Float64, angle_rad: Float64
) -> Float64:
    """Force on a current-carrying wire: F = I·L·B·sin(θ).

    Args:
        current: Current (A).
        length: Wire length (m).
        field: Magnetic field magnitude (T).
        angle_rad: Angle between wire and field (rad).

    Returns:
        Force (N).
    """
    from std.math import sin
    return current * length * field * sin(angle_rad)


fn solenoid_field(current: Float64, turns: Float64, length: Float64) -> Float64:
    """Magnetic field inside an ideal solenoid.

    B = μ0·n·I  where n = N/L

    Args:
        current: Current (A).
        turns: Number of turns (N).
        length: Solenoid length (m).

    Returns:
        Magnetic field (T).
    """
    if length <= 0.0:
        return 0.0
    var mu0 = 1.2566370614e-6
    return mu0 * (turns / length) * current


fn toroid_field(current: Float64, turns: Float64, radius: Float64) -> Float64:
    """Magnetic field inside a toroid at mean radius.

    B = μ0·N·I / (2π·R)

    Args:
        current: Current (A).
        turns: Number of turns.
        radius: Mean toroid radius (m).

    Returns:
        Magnetic field (T).
    """
    if radius <= 0.0:
        return 0.0
    var mu0 = 1.2566370614e-6
    var pi = 3.141592653589793
    return mu0 * turns * current / (2.0 * pi * radius)


fn magnetic_flux(field: Float64, area: Float64, angle_rad: Float64) -> Float64:
    """Magnetic flux: Φ = B·A·cos(θ).

    Args:
        field: Magnetic field (T).
        area: Area of surface (m²).
        angle_rad: Angle between field and surface normal (rad).

    Returns:
        Magnetic flux (Wb).
    """
    return field * area * cos(angle_rad)


fn inductance_solenoid(
    turns: Float64, area: Float64, length: Float64, mu_r: Float64
) -> Float64:
    """Inductance of a solenoid.

    L = μ0·μr·N²·A / l

    Args:
        turns: Number of turns.
        area: Cross-sectional area (m²).
        length: Solenoid length (m).
        mu_r: Relative permeability (1 for air).

    Returns:
        Inductance (H).
    """
    if length <= 0.0:
        return 0.0
    var mu0 = 1.2566370614e-6
    return mu0 * mu_r * turns * turns * area / length


fn magnetic_energy_density(field: Float64) -> Float64:
    """Energy density of a magnetic field: u = B²/(2μ0).

    Args:
        field: Magnetic flux density (T).

    Returns:
        Energy density (J/m³).
    """
    var mu0 = 1.2566370614e-6
    return field * field / (2.0 * mu0)


fn cyclotron_radius(
    mass: Float64, velocity: Float64, charge: Float64, field: Float64
) -> Float64:
    """Cyclotron (Larmor) radius of a charged particle.

    r = mv / (|q|B)

    Args:
        mass: Particle mass (kg).
        velocity: Particle speed perpendicular to B (m/s).
        charge: Particle charge magnitude (C).
        field: Magnetic field (T).

    Returns:
        Cyclotron radius (m).
    """
    if charge <= 0.0 or field <= 0.0:
        return 0.0
    return mass * velocity / (charge * field)


fn larmor_frequency(charge: Float64, field: Float64, mass: Float64) -> Float64:
    """Larmor (cyclotron) frequency: f = |q|B / (2π·m).

    Args:
        charge: Particle charge magnitude (C).
        field: Magnetic field (T).
        mass: Particle mass (kg).

    Returns:
        Cyclotron frequency (Hz).
    """
    if mass <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    return charge * field / (2.0 * pi * mass)


fn hall_voltage(
    current: Float64, field: Float64, carrier_density: Float64, thickness: Float64
) -> Float64:
    """Hall voltage in a conductor.

    V_H = I·B / (n·q·t)

    Args:
        current: Current (A).
        field: Magnetic field perpendicular to current (T).
        carrier_density: Charge carrier density (m⁻³).
        thickness: Conductor thickness (m).

    Returns:
        Hall voltage (V).
    """
    if carrier_density <= 0.0 or thickness <= 0.0:
        return 0.0
    var q = 1.60217663e-19  # elementary charge
    return current * field / (carrier_density * q * thickness)
