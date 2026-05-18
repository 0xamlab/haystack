"""
rheology.mojo — Flow and deformation of matter calculations. Zero Python imports.

Public API:
  shear_stress                 — τ = F/A
  shear_rate                   — γ_dot = dv/dy
  dynamic_viscosity            — η = τ / γ_dot
  power_law_viscosity          — η = K * γ_dot^(n-1)
  bingham_yield_stress         — τ_y = τ - η_pl * γ_dot
  reynolds_number_non_newton   — Re = ρ * v^(2-n) * D^n / K
  creep_compliance             — J(t) = J0 * (1 - exp(-t/τ))
  stress_relaxation_modulus    — G(t) = G0 * exp(-t/τ)
  viscosity_arrhenius          — η = η0 * exp(Ea/(R*T))
  thixotropy_index             — TI from low vs. high shear viscosity
"""
from std.math import exp, log, pow


fn shear_stress(force: Float64, area: Float64) -> Float64:
    """Shear stress: τ = F/A.

    Args:
        force: Shear force (N).
        area: Cross-sectional area (m²).

    Returns:
        Shear stress (Pa).
    """
    if area <= 0.0:
        return 0.0
    return force / area


fn shear_rate(velocity: Float64, gap: Float64) -> Float64:
    """Shear rate in simple shear: γ̇ = v/h.

    Args:
        velocity: Relative velocity of surfaces (m/s).
        gap: Gap between surfaces (m).

    Returns:
        Shear rate (s⁻¹).
    """
    if gap <= 0.0:
        return 0.0
    return velocity / gap


fn dynamic_viscosity(shear_stress_pa: Float64, shear_rate_s: Float64) -> Float64:
    """Dynamic (Newtonian) viscosity: η = τ/γ̇.

    Args:
        shear_stress_pa: Shear stress (Pa).
        shear_rate_s: Shear rate (s⁻¹).

    Returns:
        Dynamic viscosity (Pa·s).
    """
    if shear_rate_s <= 0.0:
        return 0.0
    return shear_stress_pa / shear_rate_s


fn power_law_viscosity(
    consistency_k: Float64, shear_rate_s: Float64, flow_index_n: Float64
) -> Float64:
    """Apparent viscosity of a power-law fluid: η = K·γ̇^(n-1).

    Args:
        consistency_k: Consistency index K (Pa·s^n).
        shear_rate_s: Shear rate (s⁻¹).
        flow_index_n: Flow behaviour index n (1 = Newtonian, <1 = shear-thinning).

    Returns:
        Apparent viscosity (Pa·s).
    """
    if consistency_k <= 0.0 or shear_rate_s <= 0.0:
        return 0.0
    return consistency_k * pow(shear_rate_s, flow_index_n - 1.0)


fn bingham_yield_stress(
    total_stress: Float64, plastic_viscosity: Float64, shear_rate_s: Float64
) -> Float64:
    """Bingham plastic yield stress: τ_y = τ - η_pl·γ̇.

    Args:
        total_stress: Applied shear stress (Pa).
        plastic_viscosity: Plastic viscosity (Pa·s).
        shear_rate_s: Shear rate (s⁻¹).

    Returns:
        Yield stress (Pa).
    """
    var ty = total_stress - plastic_viscosity * shear_rate_s
    if ty < 0.0:
        return 0.0
    return ty


fn reynolds_number_non_newton(
    density: Float64, velocity: Float64, diameter: Float64,
    consistency_k: Float64, flow_index_n: Float64
) -> Float64:
    """Generalised Reynolds number for power-law fluids.

    Re_gen = ρ·v^(2-n)·D^n / K

    Args:
        density: Fluid density (kg/m³).
        velocity: Mean flow velocity (m/s).
        diameter: Pipe diameter (m).
        consistency_k: Consistency index K (Pa·s^n).
        flow_index_n: Flow index n.

    Returns:
        Generalised Reynolds number.
    """
    if consistency_k <= 0.0 or diameter <= 0.0:
        return 0.0
    return (density * pow(velocity, 2.0 - flow_index_n)
            * pow(diameter, flow_index_n) / consistency_k)


fn creep_compliance(
    j0: Float64, time: Float64, retardation_time: Float64
) -> Float64:
    """Viscoelastic creep compliance: J(t) = J0·(1 - exp(-t/τ)).

    Args:
        j0: Instantaneous compliance (Pa⁻¹).
        time: Time (s).
        retardation_time: Retardation time τ (s).

    Returns:
        Creep compliance J(t) (Pa⁻¹).
    """
    if retardation_time <= 0.0:
        return j0
    return j0 * (1.0 - exp(-time / retardation_time))


fn stress_relaxation_modulus(
    g0: Float64, time: Float64, relaxation_time: Float64
) -> Float64:
    """Maxwell stress relaxation: G(t) = G0·exp(-t/τ).

    Args:
        g0: Instantaneous modulus (Pa).
        time: Time (s).
        relaxation_time: Relaxation time τ (s).

    Returns:
        Relaxation modulus G(t) (Pa).
    """
    if relaxation_time <= 0.0:
        return 0.0
    return g0 * exp(-time / relaxation_time)


fn viscosity_arrhenius(
    eta0: Float64, activation_energy: Float64, temperature: Float64
) -> Float64:
    """Temperature dependence of viscosity (Arrhenius model).

    η = η0 · exp(Ea / (R·T))

    Args:
        eta0: Pre-exponential viscosity factor (Pa·s).
        activation_energy: Flow activation energy (J/mol).
        temperature: Temperature (K).

    Returns:
        Viscosity (Pa·s).
    """
    if temperature <= 0.0 or eta0 < 0.0:
        return 0.0
    var R = 8.314
    return eta0 * exp(activation_energy / (R * temperature))


fn thixotropy_index(
    viscosity_low_shear: Float64, viscosity_high_shear: Float64
) -> Float64:
    """Thixotropy index: ratio of low to high shear viscosity.

    Args:
        viscosity_low_shear: Viscosity at low shear rate (Pa·s).
        viscosity_high_shear: Viscosity at high shear rate (Pa·s).

    Returns:
        Thixotropy index (>1 for shear-thinning materials).
    """
    if viscosity_high_shear <= 0.0:
        return 0.0
    return viscosity_low_shear / viscosity_high_shear
