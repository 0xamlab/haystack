"""
wood_science.mojo — Timber and wood material science calculations. Zero Python imports.

Public API:
  moisture_content             — MC = (wet - dry) / dry * 100
  fiber_saturation_point       — FSP ≈ 28-30% MC (species estimate)
  shrinkage_coefficient        — S = ΔD / (D * ΔMC)
  modulus_of_rupture           — MOR from beam bending
  modulus_of_elasticity        — MOE from deflection
  wood_density_at_mc           — density adjusted for moisture content
  thermal_conductivity_wood    — k from density and moisture
  charring_rate                — char depth from fire duration
  section_modulus              — Z = b*h² / 6
  wood_hardness_janka          — Janka hardness from density
"""
from std.math import sqrt, pow


def moisture_content(wet_mass: Float64, dry_mass: Float64) -> Float64:
    """Wood moisture content: MC = (m_wet - m_dry) / m_dry × 100%.

    Args:
        wet_mass: Wet mass of wood sample (g).
        dry_mass: Oven-dry mass of wood sample (g).

    Returns:
        Moisture content (%).
    """
    if dry_mass <= 0.0:
        return 0.0
    return (wet_mass - dry_mass) / dry_mass * 100.0


def fiber_saturation_point(basic_density: Float64) -> Float64:
    """Estimated fiber saturation point from basic density.

    FSP ≈ 30 - 5·(ρ - 0.4)  (approximate empirical fit)

    Args:
        basic_density: Basic wood density (g/cm³).

    Returns:
        Estimated FSP (% moisture content).
    """
    return 30.0 - 5.0 * (basic_density - 0.4)


def shrinkage_coefficient(
    dim_change: Float64, original_dim: Float64, mc_change: Float64
) -> Float64:
    """Dimensional shrinkage coefficient.

    S = ΔD / (D₀ · ΔMC)  (%/%)

    Args:
        dim_change: Change in dimension (mm).
        original_dim: Original green dimension (mm).
        mc_change: Change in moisture content (%).

    Returns:
        Shrinkage coefficient (%/%).
    """
    var denom = original_dim * mc_change
    if denom <= 0.0:
        return 0.0
    return dim_change / denom


def modulus_of_rupture(
    load_at_break: Float64, span: Float64, width: Float64, depth: Float64
) -> Float64:
    """Modulus of rupture from three-point bending test.

    MOR = 3·P·L / (2·b·d²)

    Args:
        load_at_break: Breaking load P (N).
        span: Test span L (mm).
        width: Beam width b (mm).
        depth: Beam depth d (mm).

    Returns:
        MOR (MPa).
    """
    var denom = 2.0 * width * depth * depth
    if denom <= 0.0:
        return 0.0
    return 3.0 * load_at_break * span / denom


def modulus_of_elasticity(
    load: Float64, span: Float64, width: Float64, depth: Float64, deflection: Float64
) -> Float64:
    """Modulus of elasticity from three-point bending.

    MOE = P·L³ / (4·b·d³·δ)

    Args:
        load: Applied load P (N).
        span: Test span L (mm).
        width: Beam width b (mm).
        depth: Beam depth d (mm).
        deflection: Mid-span deflection δ (mm).

    Returns:
        MOE (MPa).
    """
    var denom = 4.0 * width * pow(depth, 3.0) * deflection
    if denom <= 0.0:
        return 0.0
    return load * pow(span, 3.0) / denom


def wood_density_at_mc(
    basic_density: Float64, moisture_content_pct: Float64
) -> Float64:
    """Wood density at a given moisture content.

    ρ(MC) ≈ ρ_basic · (1 + MC/100) / (1 + MC/FSP)

    Args:
        basic_density: Basic density (g/cm³, oven-dry basis).
        moisture_content_pct: Moisture content (%).

    Returns:
        Density at MC (g/cm³).
    """
    var fsp = 30.0  # typical FSP %
    var denom = 1.0 + moisture_content_pct / fsp
    if denom <= 0.0:
        return basic_density
    return basic_density * (1.0 + moisture_content_pct / 100.0) / denom


def thermal_conductivity_wood(
    density_kg_m3: Float64, moisture_content_pct: Float64
) -> Float64:
    """Thermal conductivity of wood (MacLean's approximation).

    k ≈ 0.01864 · ρ · (1 + 0.024·MC)  (W/m/K, perpendicular to grain)

    Args:
        density_kg_m3: Wood density (kg/m³).
        moisture_content_pct: Moisture content (%).

    Returns:
        Thermal conductivity (W/m/K).
    """
    return 0.01864e-3 * density_kg_m3 * (1.0 + 0.024 * moisture_content_pct)


def charring_rate(
    duration_min: Float64, charring_coeff: Float64
) -> Float64:
    """Char depth in fire exposure (power law model).

    d_char = β₀ · t^0.813

    Args:
        duration_min: Fire exposure time (min).
        charring_coeff: Charring rate coefficient β₀ (mm/min^0.813, typically 0.6–1.0).

    Returns:
        Charring depth (mm).
    """
    if duration_min < 0.0 or charring_coeff < 0.0:
        return 0.0
    return charring_coeff * pow(duration_min, 0.813)


def section_modulus(width: Float64, depth: Float64) -> Float64:
    """Elastic section modulus of a rectangular beam.

    Z = b·h² / 6

    Args:
        width: Width b (mm).
        depth: Depth h (mm).

    Returns:
        Section modulus Z (mm³).
    """
    return width * depth * depth / 6.0


def wood_hardness_janka(density_g_cm3: Float64) -> Float64:
    """Estimated Janka hardness from wood density.

    Janka ≈ 6139 · ρ² − 766 · ρ + 35  (approximate, ρ in g/cm³)

    Args:
        density_g_cm3: Wood density (g/cm³).

    Returns:
        Estimated Janka hardness (lbf).
    """
    var r = density_g_cm3
    return 6139.0 * r * r - 766.0 * r + 35.0
