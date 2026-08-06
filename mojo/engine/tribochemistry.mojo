"""
tribochemistry.mojo — Surface chemistry of sliding contacts. Zero Python imports.

Public API:
  friction_coefficient         — μ = F_friction / F_normal
  archard_wear_rate            — W = k * L * F / H
  hertz_contact_radius         — a = (3*F*R/(4*E*))^(1/3)
  hertz_max_pressure           — p0 = 3F / (2πa²)
  flash_temperature            — ΔT from frictional heating
  film_thickness_ehd           — central film thickness (Hamrock-Dowson)
  lambda_ratio                 — film/roughness ratio
  surface_energy_work          — W_adhesion = 2*gamma
  tribocorrosion_rate          — synergy of wear + corrosion
  wear_volume                  — V = k_wear * L * F / hardness
"""
from std.math import sqrt, pow, log


def friction_coefficient(friction_force: Float64, normal_force: Float64) -> Float64:
    """Coulomb friction coefficient: μ = Ff/Fn.

    Args:
        friction_force: Tangential friction force (N).
        normal_force: Normal (perpendicular) force (N).

    Returns:
        Coefficient of friction (dimensionless).
    """
    if normal_force <= 0.0:
        return 0.0
    return friction_force / normal_force


def archard_wear_rate(
    wear_coefficient: Float64, sliding_distance: Float64,
    normal_force: Float64, hardness: Float64
) -> Float64:
    """Archard's wear equation: W = k·L·F/H.

    Args:
        wear_coefficient: Archard dimensionless wear coefficient k.
        sliding_distance: Total sliding distance (m).
        normal_force: Normal force (N).
        hardness: Material hardness (Pa = N/m²).

    Returns:
        Wear volume (m³).
    """
    if hardness <= 0.0:
        return 0.0
    return wear_coefficient * sliding_distance * normal_force / hardness


def hertz_contact_radius(
    normal_force: Float64, effective_radius: Float64, effective_modulus: Float64
) -> Float64:
    """Hertz contact radius for sphere-on-flat: a = (3FR/4E*)^(1/3).

    Args:
        normal_force: Applied normal force (N).
        effective_radius: Effective contact radius R* (m).
        effective_modulus: Effective elastic modulus E* (Pa).

    Returns:
        Contact radius a (m).
    """
    if effective_modulus <= 0.0 or effective_radius <= 0.0:
        return 0.0
    return pow(3.0 * normal_force * effective_radius / (4.0 * effective_modulus), 1.0 / 3.0)


def hertz_max_pressure(normal_force: Float64, contact_radius: Float64) -> Float64:
    """Maximum Hertz contact pressure: p0 = 3F/(2πa²).

    Args:
        normal_force: Applied normal force (N).
        contact_radius: Contact radius a (m).

    Returns:
        Maximum contact pressure p0 (Pa).
    """
    if contact_radius <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    return 3.0 * normal_force / (2.0 * pi * contact_radius * contact_radius)


def flash_temperature(
    friction_coeff: Float64, normal_force: Float64, velocity: Float64,
    conductivity: Float64, contact_area: Float64
) -> Float64:
    """Approximate flash temperature rise at sliding contact.

    ΔT ≈ μ·Fn·v / (4·k·a)

    Args:
        friction_coeff: Coefficient of friction.
        normal_force: Normal force (N).
        velocity: Sliding velocity (m/s).
        conductivity: Thermal conductivity (W/m/K).
        contact_area: Nominal contact area radius (m).

    Returns:
        Flash temperature rise ΔT (°C or K).
    """
    var denom = 4.0 * conductivity * contact_area
    if denom <= 0.0:
        return 0.0
    return friction_coeff * normal_force * velocity / denom


def film_thickness_ehd(
    speed: Float64, viscosity: Float64, pressure_coeff: Float64,
    modulus: Float64, radius: Float64, force: Float64
) -> Float64:
    """Central film thickness (Hamrock-Dowson for point contact, simplified).

    h_c ∝ (U)^0.67 · (G)^0.53 · (W)^-0.067

    Args:
        speed: Entrainment speed parameter U = η₀·u/(E*·R).
        viscosity: Dynamic viscosity η₀ (Pa·s).
        pressure_coeff: Viscosity-pressure coefficient α (Pa⁻¹).
        modulus: Effective modulus E* (Pa).
        radius: Effective radius R (m).
        force: Applied load W (N).

    Returns:
        Dimensionless film thickness parameter (multiply by R for meters).
    """
    if modulus <= 0.0 or radius <= 0.0 or force <= 0.0:
        return 0.0
    var U_param = viscosity * speed / (modulus * radius)
    var G_param = pressure_coeff * modulus
    var W_param = force / (modulus * radius * radius)
    return 2.69 * pow(U_param, 0.67) * pow(G_param, 0.53) * pow(W_param, -0.067)


def lambda_ratio(film_thickness: Float64, combined_roughness: Float64) -> Float64:
    """Lambda ratio (specific film thickness): Λ = h / σ*.

    Args:
        film_thickness: Lubricant film thickness (μm).
        combined_roughness: Combined RMS roughness σ* (μm).

    Returns:
        Λ ratio (< 1 = boundary, 1–3 = mixed, > 3 = full film).
    """
    if combined_roughness <= 0.0:
        return 0.0
    return film_thickness / combined_roughness


def surface_energy_work(surface_energy: Float64) -> Float64:
    """Work of adhesion for identical surfaces: W = 2·γ.

    Args:
        surface_energy: Surface energy of each surface γ (mJ/m²).

    Returns:
        Thermodynamic work of adhesion W (mJ/m²).
    """
    return 2.0 * surface_energy


def tribocorrosion_rate(
    wear_rate: Float64, corrosion_rate: Float64, synergy_factor: Float64
) -> Float64:
    """Total tribocorrosion material loss rate with synergy.

    Total = wear_rate + corrosion_rate + synergy_factor·(wear_rate + corrosion_rate)

    Args:
        wear_rate: Mechanical wear rate (μg/h).
        corrosion_rate: Corrosion rate (μg/h).
        synergy_factor: Mutual acceleration factor (dimensionless).

    Returns:
        Total material loss rate (μg/h).
    """
    var mechanical_chem = wear_rate + corrosion_rate
    return mechanical_chem * (1.0 + synergy_factor)


def wear_volume(
    wear_coefficient: Float64, sliding_distance: Float64,
    normal_force: Float64, hardness_pa: Float64
) -> Float64:
    """Wear volume from Archard's equation.

    V = k · L · F / H

    Args:
        wear_coefficient: Dimensionless k.
        sliding_distance: Sliding distance (m).
        normal_force: Normal force (N).
        hardness_pa: Vickers or equivalent hardness (Pa).

    Returns:
        Wear volume (m³).
    """
    if hardness_pa <= 0.0:
        return 0.0
    return wear_coefficient * sliding_distance * normal_force / hardness_pa
