"""Timber / Wood Science Library — board feet, moisture, structural, fire charring."""

from std.math import sqrt, log, exp, abs


fn board_feet(thickness_in: Float64, width_in: Float64, length_ft: Float64) -> Float64:
    """BF = T * W * L / 12."""
    return thickness_in * width_in * length_ft / 12.0


fn moisture_content(wet_weight: Float64, oven_dry_weight: Float64) -> Float64:
    """MC = (wet - dry) / dry * 100."""
    if oven_dry_weight == 0.0:
        return 0.0
    return (wet_weight - oven_dry_weight) / oven_dry_weight * 100.0


fn allowable_stress(
    base_stress: Float64,
    duration_factor: Float64,
    size_factor: Float64,
    wet_factor: Float64,
) -> Float64:
    """F' = Fb * CD * CF * CM."""
    return base_stress * duration_factor * size_factor * wet_factor


fn modulus_of_rupture_adjusted(mor: Float64, moisture_factor: Float64) -> Float64:
    """MOR' = MOR * factor."""
    return mor * moisture_factor


fn section_modulus_beam(width: Float64, depth: Float64) -> Float64:
    """S = b * d^2 / 6."""
    return width * depth * depth / 6.0


fn moment_capacity(allowable_stress_val: Float64, section_modulus: Float64) -> Float64:
    """M = F' * S."""
    return allowable_stress_val * section_modulus


fn column_slenderness(length: Float64, dimension: Float64) -> Float64:
    """L/d ratio."""
    if dimension == 0.0:
        return 0.0
    return length / dimension


fn wood_density_from_sg(specific_gravity: Float64, water_density: Float64) -> Float64:
    """rho = SG * rho_water."""
    return specific_gravity * water_density


fn shrinkage_estimate(
    mc_initial: Float64,
    mc_final: Float64,
    total_shrinkage_pct: Float64,
    fsp: Float64,
) -> Float64:
    """S = total_shrinkage * (MCi - MCf) / FSP (simplified)."""
    if fsp == 0.0:
        return 0.0
    return total_shrinkage_pct * (mc_initial - mc_final) / fsp


fn fire_char_rate(time_min: Float64, char_rate_mm_per_min: Float64) -> Float64:
    """Depth = time * rate (mm)."""
    return time_min * char_rate_mm_per_min


fn remaining_section(original_dim: Float64, char_depth: Float64) -> Float64:
    """Remaining = original - 2 * char_depth (both sides)."""
    return original_dim - 2.0 * char_depth


fn log_volume_doyle(diameter_in: Float64, length_ft: Float64) -> Float64:
    """V = (D - 4)^2 * L / 16 (Doyle rule)."""
    var d_minus_4 = diameter_in - 4.0
    return d_minus_4 * d_minus_4 * length_ft / 16.0
