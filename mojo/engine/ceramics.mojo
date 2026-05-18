"""
ceramics.mojo — Ceramics & Glass Engineering Library. Zero Python imports.

Provides Weibull statistics, thermal shock, porosity, sintering,
and dielectric property calculations.

Public API:
  weibull_failure_probability        — P = 1 - exp(-(σ/σ0)^m)
  weibull_characteristic_strength    — σ0 ≈ mean * 1.1 (m≈10)
  thermal_shock_resistance           — R = σ*(1-ν)/(E*α)
  youngs_modulus_porosity            — E = E0 * exp(-b*P)
  sintering_shrinkage                — S = (L0-Lf)/L0 * 100
  density_from_archimedes            — ρ = dry*ρ_fluid/(wet-suspended)
  relative_density                   — RD = actual/theoretical * 100
  porosity_from_density              — P = (1 - actual/theoretical)*100
  fracture_toughness_indentation     — KIc simplified
  dielectric_constant_mixture        — K_mix = v1*k1 + v2*k2
  coefficient_of_thermal_expansion   — CTE = ΔL/(L0*ΔT)
  glass_transition_estimate          — Tg ≈ 2/3 * Tm
"""
from std.math import exp, log, abs as fabs


# ── weibull_failure_probability ──────────────────────────────────────────────


fn weibull_failure_probability(
    stress: Float64, sigma0: Float64, m: Float64
) -> Float64:
    """Weibull failure probability: P = 1 - exp(-(σ/σ0)^m).

    Args:
        stress: Applied stress (MPa).
        sigma0: Characteristic strength (MPa).
        m: Weibull modulus.

    Returns:
        Probability of failure (0-1).
    """
    if fabs(sigma0) < 1e-30:
        return 0.0
    var ratio = stress / sigma0
    if ratio < 0.0:
        return 0.0
    var exponent = exp(m * log(ratio))
    return 1.0 - exp(-exponent)


# ── weibull_characteristic_strength ──────────────────────────────────────────


fn weibull_characteristic_strength(
    mean_strength: Float64, m: Float64
) -> Float64:
    """Characteristic strength: σ0 ≈ mean * 1.1 (simplified for m≈10).

    Args:
        mean_strength: Mean measured strength (MPa).
        m: Weibull modulus (used for reference only in simplified form).

    Returns:
        Estimated characteristic strength (MPa).
    """
    return mean_strength * 1.1


# ── thermal_shock_resistance ─────────────────────────────────────────────────


fn thermal_shock_resistance(
    strength: Float64,
    modulus: Float64,
    alpha: Float64,
    poisson: Float64,
) -> Float64:
    """Thermal shock resistance: R = σ*(1-ν)/(E*α).

    Args:
        strength: Tensile strength (MPa).
        modulus: Young's modulus (MPa).
        alpha: Thermal expansion coefficient (1/K).
        poisson: Poisson's ratio.

    Returns:
        Thermal shock resistance parameter (K).
    """
    var denom = modulus * alpha
    if fabs(denom) < 1e-30:
        return 0.0
    return strength * (1.0 - poisson) / denom


# ── youngs_modulus_porosity ──────────────────────────────────────────────────


fn youngs_modulus_porosity(
    e0: Float64, porosity: Float64, b: Float64
) -> Float64:
    """Young's modulus with porosity: E = E0 * exp(-b*P).

    Args:
        e0: Dense material modulus (GPa).
        porosity: Volume fraction of porosity (0-1).
        b: Empirical constant (~2-4 for ceramics).

    Returns:
        Effective Young's modulus (GPa).
    """
    return e0 * exp(-b * porosity)


# ── sintering_shrinkage ─────────────────────────────────────────────────────


fn sintering_shrinkage(
    initial_length: Float64, final_length: Float64
) -> Float64:
    """Sintering shrinkage: S = (L0 - Lf) / L0 * 100.

    Args:
        initial_length: Length before sintering.
        final_length: Length after sintering.

    Returns:
        Linear shrinkage (%).
    """
    if fabs(initial_length) < 1e-30:
        return 0.0
    return (initial_length - final_length) / initial_length * 100.0


# ── density_from_archimedes ──────────────────────────────────────────────────


fn density_from_archimedes(
    dry_mass: Float64,
    wet_mass: Float64,
    suspended_mass: Float64,
    fluid_density: Float64,
) -> Float64:
    """Archimedes density: ρ = dry * ρ_fluid / (wet - suspended).

    Args:
        dry_mass: Dry mass of sample (g).
        wet_mass: Mass after saturation (g).
        suspended_mass: Mass suspended in fluid (g).
        fluid_density: Density of immersion fluid (g/cm³).

    Returns:
        Bulk density (g/cm³).
    """
    var denom = wet_mass - suspended_mass
    if fabs(denom) < 1e-30:
        return 0.0
    return dry_mass * fluid_density / denom


# ── relative_density ─────────────────────────────────────────────────────────


fn relative_density(
    actual: Float64, theoretical: Float64
) -> Float64:
    """Relative density: RD = actual / theoretical * 100.

    Args:
        actual: Measured density.
        theoretical: Theoretical maximum density.

    Returns:
        Relative density (%).
    """
    if fabs(theoretical) < 1e-30:
        return 0.0
    return actual / theoretical * 100.0


# ── porosity_from_density ────────────────────────────────────────────────────


fn porosity_from_density(
    actual_density: Float64, theoretical_density: Float64
) -> Float64:
    """Porosity from density: P = (1 - actual/theoretical) * 100.

    Args:
        actual_density: Measured density.
        theoretical_density: Theoretical density.

    Returns:
        Porosity (%).
    """
    if fabs(theoretical_density) < 1e-30:
        return 0.0
    return (1.0 - actual_density / theoretical_density) * 100.0


# ── fracture_toughness_indentation ───────────────────────────────────────────


fn fracture_toughness_indentation(
    hardness: Float64,
    crack_length: Float64,
    load: Float64,
    c_factor: Float64,
    modulus: Float64,
) -> Float64:
    """Fracture toughness (indentation): KIc = c*(E/H)^0.5 * P/c^1.5.

    Simplified Anstis equation.

    Args:
        hardness: Vickers hardness (GPa).
        crack_length: Radial crack length (m).
        load: Indentation load (N).
        c_factor: Calibration constant (~0.016).
        modulus: Young's modulus (GPa).

    Returns:
        Fracture toughness KIc (MPa·√m).
    """
    if fabs(hardness) < 1e-30 or crack_length <= 0.0:
        return 0.0
    var eh_ratio = exp(0.5 * log(modulus / hardness))
    var c15 = exp(1.5 * log(crack_length))
    if fabs(c15) < 1e-30:
        return 0.0
    return c_factor * eh_ratio * load / c15


# ── dielectric_constant_mixture ──────────────────────────────────────────────


fn dielectric_constant_mixture(
    v1: Float64, k1: Float64, v2: Float64, k2: Float64
) -> Float64:
    """Lichtenecker linear mixture rule: K_mix = v1*k1 + v2*k2.

    Args:
        v1: Volume fraction of phase 1.
        k1: Dielectric constant of phase 1.
        v2: Volume fraction of phase 2.
        k2: Dielectric constant of phase 2.

    Returns:
        Mixture dielectric constant.
    """
    return v1 * k1 + v2 * k2


# ── coefficient_of_thermal_expansion ─────────────────────────────────────────


fn coefficient_of_thermal_expansion(
    delta_l: Float64, l0: Float64, delta_t: Float64
) -> Float64:
    """CTE = ΔL / (L0 * ΔT).

    Args:
        delta_l: Change in length.
        l0: Original length.
        delta_t: Change in temperature.

    Returns:
        Coefficient of thermal expansion (1/K).
    """
    var denom = l0 * delta_t
    if fabs(denom) < 1e-30:
        return 0.0
    return delta_l / denom


# ── glass_transition_estimate ────────────────────────────────────────────────


fn glass_transition_estimate(melting_point: Float64) -> Float64:
    """Kauzmann estimate: Tg ≈ 2/3 * Tm.

    Args:
        melting_point: Melting temperature (K).

    Returns:
        Estimated glass transition temperature (K).
    """
    return (2.0 / 3.0) * melting_point
