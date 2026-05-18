"""
composites.mojo — Composite Materials Library. Zero Python imports.

Provides rule-of-mixtures modulus, inverse ROM, composite density, fiber
volume fraction, laminate thickness, specific stiffness/strength, Halpin-Tsai
model, critical fiber length, shear-lag stress transfer, Charpy impact energy,
and void content calculations.

Public API:
  rule_of_mixtures_modulus   — E1 = Vf*Ef + (1-Vf)*Em
  inverse_rule_of_mixtures   — E2 from inverse ROM
  composite_density          — ρ = Vf*ρf + (1-Vf)*ρm
  fiber_volume_fraction      — Vf from masses & densities
  laminate_thickness         — t = n * t_ply
  specific_stiffness         — E / ρ
  specific_strength          — σ / ρ
  halpin_tsai                — Halpin-Tsai transverse modulus
  critical_fiber_length      — Lc = σf*d / (2*τ)
  shear_lag_stress_transfer  — σf = σ_app*(1 + aspect*vf/2)
  impact_energy_charpy       — IE = E / A  (J/m²)
  void_content               — Void% = (ρ_theo - ρ_meas)/ρ_theo * 100
"""


# ── Rule of mixtures ─────────────────────────────────────────────────────────


fn rule_of_mixtures_modulus(vf: Float64, ef: Float64, em: Float64) -> Float64:
    """Longitudinal modulus (Voigt): E1 = Vf*Ef + (1-Vf)*Em."""
    return vf * ef + (1.0 - vf) * em


fn inverse_rule_of_mixtures(vf: Float64, ef: Float64, em: Float64) -> Float64:
    """Transverse modulus (Reuss): 1/E2 = Vf/Ef + (1-Vf)/Em → E2."""
    if ef <= 0.0 or em <= 0.0:
        return 0.0
    var inv = vf / ef + (1.0 - vf) / em
    if inv <= 0.0:
        return 0.0
    return 1.0 / inv


fn composite_density(
    vf: Float64, rho_f: Float64, rho_m: Float64
) -> Float64:
    """Composite density: ρ = Vf*ρf + (1-Vf)*ρm."""
    return vf * rho_f + (1.0 - vf) * rho_m


# ── Fiber volume fraction ────────────────────────────────────────────────────


fn fiber_volume_fraction(
    fiber_mass: Float64,
    fiber_density: Float64,
    matrix_mass: Float64,
    matrix_density: Float64,
) -> Float64:
    """Fiber volume fraction: Vf = (mf/ρf) / ((mf/ρf) + (mm/ρm))."""
    if fiber_density <= 0.0 or matrix_density <= 0.0:
        return 0.0
    var vf_vol = fiber_mass / fiber_density
    var vm_vol = matrix_mass / matrix_density
    var total = vf_vol + vm_vol
    if total <= 0.0:
        return 0.0
    return vf_vol / total


# ── Laminate geometry ─────────────────────────────────────────────────────────


fn laminate_thickness(n_plies: Float64, ply_thickness: Float64) -> Float64:
    """Laminate thickness: t = n * t_ply."""
    return n_plies * ply_thickness


# ── Specific properties ──────────────────────────────────────────────────────


fn specific_stiffness(modulus: Float64, density: Float64) -> Float64:
    """Specific stiffness: E / ρ."""
    if density <= 0.0:
        return 0.0
    return modulus / density


fn specific_strength(strength: Float64, density: Float64) -> Float64:
    """Specific strength: σ / ρ."""
    if density <= 0.0:
        return 0.0
    return strength / density


# ── Halpin-Tsai model ────────────────────────────────────────────────────────


fn halpin_tsai(
    vf: Float64, ef: Float64, em: Float64, xi: Float64
) -> Float64:
    """Halpin-Tsai: E = Em*(1+ξ*η*Vf)/(1-η*Vf).

    η = (Ef/Em - 1) / (Ef/Em + ξ).
    """
    if em <= 0.0:
        return 0.0
    var ratio = ef / em
    var denom_eta = ratio + xi
    if denom_eta <= 0.0:
        return 0.0
    var eta = (ratio - 1.0) / denom_eta
    var denom = 1.0 - eta * vf
    if denom <= 0.0:
        return 0.0
    return em * (1.0 + xi * eta * vf) / denom


# ── Critical fiber length ────────────────────────────────────────────────────


fn critical_fiber_length(
    fiber_strength: Float64,
    fiber_diameter: Float64,
    interfacial_shear: Float64,
) -> Float64:
    """Critical fiber length: Lc = σf * d / (2 * τ)."""
    if interfacial_shear <= 0.0:
        return 0.0
    return fiber_strength * fiber_diameter / (2.0 * interfacial_shear)


# ── Shear lag stress transfer ─────────────────────────────────────────────────


fn shear_lag_stress_transfer(
    applied_stress: Float64,
    aspect_ratio: Float64,
    vf: Float64,
) -> Float64:
    """Shear-lag fiber stress: σf = σ_app * (1 + aspect * vf / 2)."""
    return applied_stress * (1.0 + aspect_ratio * vf / 2.0)


# ── Impact energy ─────────────────────────────────────────────────────────────


fn impact_energy_charpy(
    absorbed_energy: Float64, cross_section_area: Float64
) -> Float64:
    """Charpy impact energy: IE = E / A  (J/m²)."""
    if cross_section_area <= 0.0:
        return 0.0
    return absorbed_energy / cross_section_area


# ── Void content ──────────────────────────────────────────────────────────────


fn void_content(
    theoretical_density: Float64, measured_density: Float64
) -> Float64:
    """Void content: Void% = (ρ_theo - ρ_meas) / ρ_theo * 100."""
    if theoretical_density <= 0.0:
        return 0.0
    return (theoretical_density - measured_density) / theoretical_density * 100.0
