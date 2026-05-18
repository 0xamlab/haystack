"""
soil_mechanics.mojo — Geotechnical engineering calculations. Zero Python imports.

Public API:
  bearing_capacity_terzaghi    — Terzaghi ultimate bearing capacity
  settlement_elastic           — elastic settlement of footing
  consolidation_degree         — degree of consolidation (Terzaghi 1D)
  void_ratio                   — e from specific gravity and water content
  relative_density             — Dr from e, e_max, e_min
  liquid_limit_plasticity      — Atterberg plasticity index PI = LL - PL
  shear_strength_mohr_coulomb  — τ = c + σ·tan(φ)
  lateral_earth_pressure_ka    — active Ka = tan²(45 - φ/2)
  compression_index            — Cc from liquid limit (empirical)
  hydraulic_conductivity_hazen — k from D10 grain size (Hazen's rule)
"""
from std.math import sqrt, pow, log, exp


fn bearing_capacity_terzaghi(
    cohesion: Float64, unit_weight: Float64, depth: Float64,
    width: Float64, phi_rad: Float64
) -> Float64:
    """Terzaghi ultimate bearing capacity for strip footing.

    qu = c·Nc + γ·Df·Nq + 0.5·γ·B·Nγ

    Args:
        cohesion: Soil cohesion c (kPa).
        unit_weight: Soil unit weight γ (kN/m³).
        depth: Footing depth Df (m).
        width: Footing width B (m).
        phi_rad: Internal friction angle φ (rad).

    Returns:
        Ultimate bearing capacity qu (kPa).
    """
    from std.math import tan, cos, sin
    # Terzaghi bearing capacity factors (approximate)
    var tan_phi = tan(phi_rad)
    var pi = 3.141592653589793
    var Nq = exp(pi * tan_phi) / (2.0 * cos(pi / 4.0 + phi_rad / 2.0) ** 2.0)
    var Nc = (Nq - 1.0) / tan_phi if tan_phi > 1e-10 else 5.7
    var Ng = (Nq - 1.0) * tan_phi
    return cohesion * Nc + unit_weight * depth * Nq + 0.5 * unit_weight * width * Ng


fn settlement_elastic(
    pressure: Float64, width: Float64, modulus: Float64, poisson: Float64
) -> Float64:
    """Elastic settlement of a uniformly loaded flexible footing.

    Se = q·B·(1-ν²) / E · Iw  (Iw ≈ π/4 for circular; use 0.82 for square)

    Args:
        pressure: Contact pressure q (kPa).
        width: Footing width B (m).
        modulus: Elastic modulus of soil E (kPa).
        poisson: Poisson's ratio ν.

    Returns:
        Elastic settlement Se (m).
    """
    if modulus <= 0.0:
        return 0.0
    var iw = 0.82  # influence factor for square footing
    return pressure * width * (1.0 - poisson * poisson) * iw / modulus


fn consolidation_degree(time_factor: Float64) -> Float64:
    """Average degree of consolidation from Terzaghi 1D theory.

    U = 1 - (8/π²)·exp(-π²·Tv/4)  (simplified, valid for Tv > 0.2)

    Args:
        time_factor: Dimensionless time factor Tv = cv·t/H².

    Returns:
        Degree of consolidation U (0–1).
    """
    if time_factor < 0.0:
        return 0.0
    if time_factor < 0.217:
        # Parabolic approximation for early time
        return sqrt(4.0 * time_factor / 3.14159)
    var pi = 3.141592653589793
    return 1.0 - (8.0 / (pi * pi)) * exp(-pi * pi * time_factor / 4.0)


fn void_ratio(
    specific_gravity: Float64, water_content: Float64, saturation: Float64
) -> Float64:
    """Void ratio: e = Gs·w / Sr.

    Args:
        specific_gravity: Specific gravity of solids Gs (typically 2.65–2.75).
        water_content: Water content w (fraction, not %).
        saturation: Degree of saturation Sr (fraction, 1 = saturated).

    Returns:
        Void ratio e.
    """
    if saturation <= 0.0:
        return 0.0
    return specific_gravity * water_content / saturation


fn relative_density(
    void_ratio_e: Float64, e_max: Float64, e_min: Float64
) -> Float64:
    """Relative density: Dr = (e_max - e) / (e_max - e_min).

    Args:
        void_ratio_e: Current void ratio e.
        e_max: Maximum (loosest) void ratio.
        e_min: Minimum (densest) void ratio.

    Returns:
        Relative density Dr (0 = loosest, 1 = densest).
    """
    var denom = e_max - e_min
    if denom <= 0.0:
        return 0.0
    var dr = (e_max - void_ratio_e) / denom
    if dr < 0.0:
        return 0.0
    if dr > 1.0:
        return 1.0
    return dr


fn liquid_limit_plasticity(liquid_limit: Float64, plastic_limit: Float64) -> Float64:
    """Plasticity index: PI = LL - PL.

    Args:
        liquid_limit: Liquid limit LL (%).
        plastic_limit: Plastic limit PL (%).

    Returns:
        Plasticity index PI (%).
    """
    var pi = liquid_limit - plastic_limit
    if pi < 0.0:
        return 0.0
    return pi


fn shear_strength_mohr_coulomb(
    cohesion: Float64, normal_stress: Float64, phi_rad: Float64
) -> Float64:
    """Shear strength from Mohr-Coulomb criterion: τ = c + σ·tan(φ).

    Args:
        cohesion: Cohesion c (kPa).
        normal_stress: Effective normal stress σ' (kPa).
        phi_rad: Effective friction angle φ' (rad).

    Returns:
        Shear strength τ (kPa).
    """
    from std.math import tan
    return cohesion + normal_stress * tan(phi_rad)


fn lateral_earth_pressure_ka(phi_rad: Float64) -> Float64:
    """Rankine active earth pressure coefficient: Ka = tan²(45° - φ/2).

    Args:
        phi_rad: Internal friction angle (rad).

    Returns:
        Active earth pressure coefficient Ka.
    """
    from std.math import tan
    var pi = 3.141592653589793
    var angle = pi / 4.0 - phi_rad / 2.0
    var t = tan(angle)
    return t * t


fn compression_index(liquid_limit: Float64) -> Float64:
    """Compression index Cc from liquid limit (Skempton's correlation).

    Cc ≈ 0.009 · (LL - 10)

    Args:
        liquid_limit: Liquid limit LL (%).

    Returns:
        Compression index Cc.
    """
    var cc = 0.009 * (liquid_limit - 10.0)
    if cc < 0.0:
        return 0.0
    return cc


fn hydraulic_conductivity_hazen(d10_mm: Float64) -> Float64:
    """Hydraulic conductivity from Hazen's empirical rule.

    k = C · D10²  (C ≈ 1.0 for cm/s with D10 in mm)

    Args:
        d10_mm: D10 effective grain size (mm).

    Returns:
        Hydraulic conductivity k (cm/s).
    """
    if d10_mm <= 0.0:
        return 0.0
    return d10_mm * d10_mm  # Hazen C ≈ 1
