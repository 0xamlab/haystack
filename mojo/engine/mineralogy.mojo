"""
mineralogy.mojo — Mineral science and crystal chemistry calculations. Zero Python imports.

Public API:
  mineral_density              — ρ = mass / volume
  mohs_hardness_scratch        — can mineral A scratch mineral B?
  crystal_d_spacing            — Bragg's law: nλ = 2d·sin(θ)
  mineral_formula_weight       — sum of atomic weights
  solubility_product           — Ksp from ion concentrations
  geochemical_activity         — ion activity from concentration and γ
  mineral_saturation_index     — SI = log(IAP / Ksp)
  specific_gravity_ratio       — SG = ρ_mineral / ρ_water
  thermal_conductivity_mixing  — κ_mix from volume fractions
  birefringence                — Δn = |n_e - n_o|
"""
from std.math import log, sin, sqrt, pow


fn _log10(x: Float64) -> Float64:
    return log(x) / log(10.0)


fn mineral_density(mass_g: Float64, volume_cm3: Float64) -> Float64:
    """Mineral density: ρ = m/V.

    Args:
        mass_g: Mass (g).
        volume_cm3: Volume (cm³).

    Returns:
        Density (g/cm³).
    """
    if volume_cm3 <= 0.0:
        return 0.0
    return mass_g / volume_cm3


fn mohs_hardness_scratch(hardness_a: Float64, hardness_b: Float64) -> Float64:
    """Mohs hardness difference (positive: A scratches B).

    Args:
        hardness_a: Mohs hardness of mineral A.
        hardness_b: Mohs hardness of mineral B.

    Returns:
        Hardness difference (positive = A scratches B).
    """
    return hardness_a - hardness_b


fn crystal_d_spacing(n: Float64, wavelength_angstrom: Float64, theta_rad: Float64) -> Float64:
    """Bragg's law d-spacing: d = nλ / (2·sin(θ)).

    Args:
        n: Diffraction order (integer, typically 1).
        wavelength_angstrom: X-ray wavelength (Å).
        theta_rad: Bragg angle θ (rad).

    Returns:
        Interplanar spacing d (Å).
    """
    var s = sin(theta_rad)
    if s <= 0.0:
        return 0.0
    return n * wavelength_angstrom / (2.0 * s)


fn mineral_formula_weight(
    atomic_weight1: Float64, count1: Float64,
    atomic_weight2: Float64, count2: Float64
) -> Float64:
    """Formula weight from two atom types.

    FW = n1·Aw1 + n2·Aw2

    Args:
        atomic_weight1: Atomic weight of first element (g/mol).
        count1: Number of atoms of first element.
        atomic_weight2: Atomic weight of second element (g/mol).
        count2: Number of atoms of second element.

    Returns:
        Formula weight (g/mol).
    """
    return count1 * atomic_weight1 + count2 * atomic_weight2


fn solubility_product(
    cation_conc: Float64, anion_conc: Float64,
    cation_stoich: Float64, anion_stoich: Float64
) -> Float64:
    """Ion activity product: IAP = [M+]^m · [X-]^x.

    Args:
        cation_conc: Cation concentration (mol/L).
        anion_conc: Anion concentration (mol/L).
        cation_stoich: Stoichiometric coefficient of cation.
        anion_stoich: Stoichiometric coefficient of anion.

    Returns:
        Ion activity product.
    """
    if cation_conc < 0.0 or anion_conc < 0.0:
        return 0.0
    return pow(cation_conc, cation_stoich) * pow(anion_conc, anion_stoich)


fn geochemical_activity(
    concentration: Float64, activity_coefficient: Float64
) -> Float64:
    """Ion activity: a = γ·c.

    Args:
        concentration: Ion concentration (mol/L).
        activity_coefficient: Activity coefficient γ (Debye-Hückel).

    Returns:
        Ion activity.
    """
    return activity_coefficient * concentration


fn mineral_saturation_index(
    ion_activity_product: Float64, ksp: Float64
) -> Float64:
    """Saturation index: SI = log10(IAP/Ksp).

    Args:
        ion_activity_product: Measured IAP.
        ksp: Equilibrium solubility product.

    Returns:
        SI. Positive = supersaturated (precipitation), negative = undersaturated.
    """
    if ion_activity_product <= 0.0 or ksp <= 0.0:
        return 0.0
    return _log10(ion_activity_product / ksp)


fn specific_gravity_ratio(mineral_density_g_cm3: Float64) -> Float64:
    """Specific gravity relative to water at 4°C.

    SG = ρ_mineral / 1.0 g/cm³

    Args:
        mineral_density_g_cm3: Mineral density (g/cm³).

    Returns:
        Specific gravity (dimensionless).
    """
    return mineral_density_g_cm3  # / 1.0 g/cm³ water


fn thermal_conductivity_mixing(
    k1: Float64, k2: Float64, vol_fraction1: Float64
) -> Float64:
    """Effective thermal conductivity of two-mineral mixture (geometric mean).

    κ_mix = κ1^f · κ2^(1-f)

    Args:
        k1: Conductivity of mineral 1 (W/m/K).
        k2: Conductivity of mineral 2 (W/m/K).
        vol_fraction1: Volume fraction of mineral 1 (0–1).

    Returns:
        Effective thermal conductivity (W/m/K).
    """
    if k1 <= 0.0 or k2 <= 0.0:
        return 0.0
    var f = vol_fraction1
    return pow(k1, f) * pow(k2, 1.0 - f)


fn birefringence(n_extraordinary: Float64, n_ordinary: Float64) -> Float64:
    """Optical birefringence: Δn = |ne - no|.

    Args:
        n_extraordinary: Extraordinary refractive index.
        n_ordinary: Ordinary refractive index.

    Returns:
        Birefringence magnitude.
    """
    var dn = n_extraordinary - n_ordinary
    if dn < 0.0:
        return -dn
    return dn
