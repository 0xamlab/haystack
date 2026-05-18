"""
electrostatics.mojo — Electrostatic field and energy calculations. Zero Python imports.

Public API:
  coulomb_force              — F = k*q1*q2/r²
  electric_field_point       — E = k*q/r²
  electric_potential         — V = k*q/r
  capacitance_parallel_plate — C = ε0*εr*A/d
  energy_stored_capacitor    — U = 0.5*C*V²
  electric_flux              — Φ = E*A*cos(θ)
  surface_charge_density     — σ = Q/A
  dielectric_polarization    — P = ε0*(εr-1)*E
  breakdown_voltage          — V_bd = E_bd * d
  image_charge_force         — F = -k*q²/(4*h²)
"""
from std.math import cos, sqrt


fn coulomb_force(q1: Float64, q2: Float64, r: Float64) -> Float64:
    """Coulomb's law: force between two point charges.

    Args:
        q1: First charge (C).
        q2: Second charge (C).
        r: Separation distance (m).

    Returns:
        Force (N). Positive = repulsive.
    """
    if r <= 0.0:
        return 0.0
    var k = 8.9875517923e9  # N·m²/C²
    return k * q1 * q2 / (r * r)


fn electric_field_point(q: Float64, r: Float64) -> Float64:
    """Electric field magnitude from a point charge.

    Args:
        q: Charge (C).
        r: Distance from charge (m).

    Returns:
        Electric field (N/C = V/m).
    """
    if r <= 0.0:
        return 0.0
    var k = 8.9875517923e9
    return k * q / (r * r)


fn electric_potential(q: Float64, r: Float64) -> Float64:
    """Electric potential from a point charge.

    Args:
        q: Charge (C).
        r: Distance (m).

    Returns:
        Potential (V).
    """
    if r <= 0.0:
        return 0.0
    var k = 8.9875517923e9
    return k * q / r


fn capacitance_parallel_plate(
    area: Float64, separation: Float64, epsilon_r: Float64
) -> Float64:
    """Capacitance of a parallel-plate capacitor.

    Args:
        area: Plate area (m²).
        separation: Plate separation (m).
        epsilon_r: Relative permittivity (dimensionless).

    Returns:
        Capacitance (F).
    """
    if separation <= 0.0 or area <= 0.0:
        return 0.0
    var epsilon0 = 8.854187817e-12  # F/m
    return epsilon0 * epsilon_r * area / separation


fn energy_stored_capacitor(capacitance: Float64, voltage: Float64) -> Float64:
    """Energy stored in a capacitor: U = ½CV².

    Args:
        capacitance: Capacitance (F).
        voltage: Voltage across capacitor (V).

    Returns:
        Stored energy (J).
    """
    if capacitance < 0.0:
        return 0.0
    return 0.5 * capacitance * voltage * voltage


fn electric_flux(field: Float64, area: Float64, angle_rad: Float64) -> Float64:
    """Electric flux through a surface: Φ = E·A·cos(θ).

    Args:
        field: Electric field magnitude (V/m).
        area: Surface area (m²).
        angle_rad: Angle between field and surface normal (rad).

    Returns:
        Electric flux (V·m = N·m²/C).
    """
    return field * area * cos(angle_rad)


fn surface_charge_density(charge: Float64, area: Float64) -> Float64:
    """Surface charge density: σ = Q/A.

    Args:
        charge: Total charge (C).
        area: Surface area (m²).

    Returns:
        Surface charge density (C/m²).
    """
    if area <= 0.0:
        return 0.0
    return charge / area


fn dielectric_polarization(epsilon_r: Float64, electric_field: Float64) -> Float64:
    """Electric polarization of a dielectric: P = ε₀(εr-1)E.

    Args:
        epsilon_r: Relative permittivity.
        electric_field: Applied electric field (V/m).

    Returns:
        Polarization (C/m²).
    """
    var epsilon0 = 8.854187817e-12
    return epsilon0 * (epsilon_r - 1.0) * electric_field


fn breakdown_voltage(dielectric_strength: Float64, thickness: Float64) -> Float64:
    """Dielectric breakdown voltage: V_bd = E_bd × d.

    Args:
        dielectric_strength: Dielectric strength (V/m).
        thickness: Insulator thickness (m).

    Returns:
        Breakdown voltage (V).
    """
    if thickness < 0.0:
        return 0.0
    return dielectric_strength * thickness


fn image_charge_force(charge: Float64, height: Float64) -> Float64:
    """Force on a charge above a grounded conductor (method of images).

    F = -k·q²/(4h²)

    Args:
        charge: Charge magnitude (C).
        height: Height above conductor (m).

    Returns:
        Attractive force toward conductor (N, negative = attractive).
    """
    if height <= 0.0:
        return 0.0
    var k = 8.9875517923e9
    return -k * charge * charge / (4.0 * height * height)
