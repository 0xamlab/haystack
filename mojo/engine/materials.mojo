"""
materials.mojo — Materials science equations. Zero Python imports.

Replaces custom materials code with pure Mojo implementations of
elastic moduli, stress/strain, thermal expansion, fatigue life,
beam deflection, and safety factors.

Public API:
  youngs_modulus            — E = σ/ε
  shear_modulus             — G = E/(2*(1+ν))
  bulk_modulus              — K = E/(3*(1-2ν))
  stress_from_force         — σ = F/A
  strain_from_deformation   — ε = ΔL/L₀
  thermal_expansion         — ΔL = L₀·α·ΔT
  safety_factor             — SF = σ_ult/σ_work
  stress_concentration      — σ_max = Kt·σ_nom
  fatigue_life              — Basquin's law: N = (σ_a/σ_f)^(1/b)
  beam_deflection_cantilever — δ = PL³/(3EI)
  moment_of_inertia_rect   — I = bh³/12
  poisson_ratio_from_moduli — ν = E/(2G) - 1
"""
from std.math import pow, abs as fabs


# ── youngs_modulus ───────────────────────────────────────────────────────────


fn youngs_modulus(stress: Float64, strain: Float64) -> Float64:
    """Young's modulus: E = σ/ε.

    Args:
        stress: Applied stress (Pa).
        strain: Resulting strain (dimensionless).

    Returns:
        Young's modulus E in Pa.
    """
    if fabs(strain) < 1e-30:
        return 0.0
    return stress / strain


# ── shear_modulus ────────────────────────────────────────────────────────────


fn shear_modulus(E: Float64, poisson: Float64) -> Float64:
    """Shear modulus: G = E / (2*(1+ν)).

    Args:
        E:       Young's modulus (Pa).
        poisson: Poisson's ratio (dimensionless).

    Returns:
        Shear modulus G in Pa.
    """
    var denom = 2.0 * (1.0 + poisson)
    if fabs(denom) < 1e-30:
        return 0.0
    return E / denom


# ── bulk_modulus ─────────────────────────────────────────────────────────────


fn bulk_modulus(E: Float64, poisson: Float64) -> Float64:
    """Bulk modulus: K = E / (3*(1-2ν)).

    Args:
        E:       Young's modulus (Pa).
        poisson: Poisson's ratio (dimensionless).

    Returns:
        Bulk modulus K in Pa.
    """
    var denom = 3.0 * (1.0 - 2.0 * poisson)
    if fabs(denom) < 1e-30:
        return 0.0
    return E / denom


# ── stress_from_force ────────────────────────────────────────────────────────


fn stress_from_force(force: Float64, area: Float64) -> Float64:
    """Stress from force and area: σ = F/A.

    Args:
        force: Applied force (N).
        area:  Cross-sectional area (m²).

    Returns:
        Stress in Pa.
    """
    if fabs(area) < 1e-30:
        return 0.0
    return force / area


# ── strain_from_deformation ─────────────────────────────────────────────────


fn strain_from_deformation(delta_l: Float64, original_l: Float64) -> Float64:
    """Engineering strain: ε = ΔL/L₀.

    Args:
        delta_l:    Change in length (m).
        original_l: Original length (m).

    Returns:
        Strain (dimensionless).
    """
    if fabs(original_l) < 1e-30:
        return 0.0
    return delta_l / original_l


# ── thermal_expansion ───────────────────────────────────────────────────────


fn thermal_expansion(original_l: Float64, alpha: Float64, delta_t: Float64) -> Float64:
    """Thermal expansion: ΔL = L₀·α·ΔT.

    Args:
        original_l: Original length (m).
        alpha:      Coefficient of thermal expansion (1/K).
        delta_t:    Temperature change (K or °C).

    Returns:
        Change in length ΔL (m).
    """
    return original_l * alpha * delta_t


# ── safety_factor ────────────────────────────────────────────────────────────


fn safety_factor(ultimate_stress: Float64, working_stress: Float64) -> Float64:
    """Safety factor: SF = σ_ult / σ_work.

    Args:
        ultimate_stress: Ultimate stress (Pa).
        working_stress:  Working/design stress (Pa).

    Returns:
        Safety factor (dimensionless).
    """
    if fabs(working_stress) < 1e-30:
        return 0.0
    return ultimate_stress / working_stress


# ── stress_concentration ────────────────────────────────────────────────────


fn stress_concentration(nominal_stress: Float64, kt: Float64) -> Float64:
    """Stress concentration: σ_max = Kt·σ_nom.

    Args:
        nominal_stress: Nominal stress (Pa).
        kt:            Stress concentration factor (dimensionless).

    Returns:
        Maximum stress at concentration (Pa).
    """
    return kt * nominal_stress


# ── fatigue_life ─────────────────────────────────────────────────────────────


fn fatigue_life(sigma_a: Float64, sigma_f: Float64, b: Float64) -> Float64:
    """Basquin's law fatigue life: N = (σ_a/σ_f)^(1/b).

    Args:
        sigma_a: Stress amplitude (Pa).
        sigma_f: Fatigue strength coefficient (Pa).
        b:       Basquin exponent (negative, dimensionless).

    Returns:
        Number of cycles to failure N.
    """
    if fabs(sigma_f) < 1e-30 or fabs(b) < 1e-30:
        return 0.0
    return pow(sigma_a / sigma_f, 1.0 / b)


# ── beam_deflection_cantilever ──────────────────────────────────────────────


fn beam_deflection_cantilever(force: Float64, length: Float64, E: Float64, I: Float64) -> Float64:
    """Cantilever beam deflection: δ = PL³/(3EI).

    Args:
        force:  Applied tip load P (N).
        length: Beam length L (m).
        E:      Young's modulus (Pa).
        I:      Second moment of area (m⁴).

    Returns:
        Tip deflection δ (m).
    """
    var denom = 3.0 * E * I
    if fabs(denom) < 1e-30:
        return 0.0
    return force * length * length * length / denom


# ── moment_of_inertia_rect ─────────────────────────────────────────────────


fn moment_of_inertia_rect(width: Float64, height: Float64) -> Float64:
    """Second moment of area for a rectangular cross-section: I = bh³/12.

    Args:
        width:  Section width b (m).
        height: Section height h (m).

    Returns:
        Moment of inertia I (m⁴).
    """
    return width * height * height * height / 12.0


# ── poisson_ratio_from_moduli ───────────────────────────────────────────────


fn poisson_ratio_from_moduli(E: Float64, G: Float64) -> Float64:
    """Poisson's ratio from elastic moduli: ν = E/(2G) - 1.

    Args:
        E: Young's modulus (Pa).
        G: Shear modulus (Pa).

    Returns:
        Poisson's ratio (dimensionless).
    """
    if fabs(G) < 1e-30:
        return 0.0
    return E / (2.0 * G) - 1.0
