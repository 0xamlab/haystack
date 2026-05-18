"""
hydrogeology.mojo — Groundwater flow and aquifer science calculations. Zero Python imports.

Public API:
  darcy_velocity               — q = K * i (Darcy's law)
  transmissivity               — T = K * b
  storativity                  — S from specific storage and thickness
  theis_drawdown               — s(r,t) from Theis well function (approx)
  dupuit_discharge             — Q from unconfined aquifer
  hydraulic_gradient           — i = Δh / L
  specific_yield               — from porosity and residual moisture
  capillary_rise_height        — h = 2γ*cos(θ) / (ρ*g*r)
  leakance_factor              — B = sqrt(T*b'/K')
  groundwater_age_mixing       — binary mixing age from tracer
"""
from std.math import sqrt, log, exp


fn darcy_velocity(hydraulic_conductivity: Float64, gradient: Float64) -> Float64:
    """Darcy flux (specific discharge): q = K·i.

    Args:
        hydraulic_conductivity: K (m/s).
        gradient: Hydraulic gradient i = Δh/L (dimensionless).

    Returns:
        Darcy velocity (m/s). Not actual pore velocity.
    """
    return hydraulic_conductivity * gradient


fn transmissivity(hydraulic_conductivity: Float64, aquifer_thickness: Float64) -> Float64:
    """Aquifer transmissivity: T = K·b.

    Args:
        hydraulic_conductivity: K (m/s).
        aquifer_thickness: Saturated thickness b (m).

    Returns:
        Transmissivity T (m²/s).
    """
    return hydraulic_conductivity * aquifer_thickness


fn storativity(
    specific_storage: Float64, aquifer_thickness: Float64
) -> Float64:
    """Storativity of a confined aquifer: S = Ss·b.

    Args:
        specific_storage: Specific storage Ss (m⁻¹).
        aquifer_thickness: Aquifer thickness b (m).

    Returns:
        Storativity S (dimensionless).
    """
    return specific_storage * aquifer_thickness


fn theis_drawdown(
    pumping_rate: Float64, transmissivity: Float64, well_function: Float64
) -> Float64:
    """Theis drawdown: s = Q/(4πT) · W(u).

    Args:
        pumping_rate: Pumping rate Q (m³/s).
        transmissivity: Aquifer transmissivity T (m²/s).
        well_function: Theis well function W(u) (use approximation below).

    Returns:
        Drawdown s (m).
    """
    if transmissivity <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    return pumping_rate / (4.0 * pi * transmissivity) * well_function


fn dupuit_discharge(
    hydraulic_conductivity: Float64, h1: Float64, h2: Float64, length: Float64
) -> Float64:
    """Dupuit discharge for unconfined aquifer (per unit width).

    Q' = K·(h1² - h2²) / (2·L)

    Args:
        hydraulic_conductivity: K (m/s).
        h1: Upstream saturated thickness (m).
        h2: Downstream saturated thickness (m).
        length: Flow path length L (m).

    Returns:
        Discharge per unit width (m²/s).
    """
    if length <= 0.0:
        return 0.0
    return hydraulic_conductivity * (h1 * h1 - h2 * h2) / (2.0 * length)


fn hydraulic_gradient(head_diff: Float64, flow_length: Float64) -> Float64:
    """Hydraulic gradient: i = Δh / L.

    Args:
        head_diff: Head difference (m).
        flow_length: Distance between measurement points (m).

    Returns:
        Hydraulic gradient (m/m, dimensionless).
    """
    if flow_length <= 0.0:
        return 0.0
    return head_diff / flow_length


fn specific_yield(porosity: Float64, residual_moisture: Float64) -> Float64:
    """Specific yield of an unconfined aquifer.

    Sy ≈ n - θ_r

    Args:
        porosity: Total porosity n (fraction).
        residual_moisture: Residual volumetric moisture content θ_r.

    Returns:
        Specific yield Sy (fraction).
    """
    var sy = porosity - residual_moisture
    if sy < 0.0:
        return 0.0
    return sy


fn capillary_rise_height(
    surface_tension: Float64, contact_angle_rad: Float64,
    density: Float64, pore_radius: Float64
) -> Float64:
    """Capillary rise height in porous media: h = 2γ·cos(θ)/(ρ·g·r).

    Args:
        surface_tension: Surface tension γ (N/m).
        contact_angle_rad: Contact angle θ (rad).
        density: Fluid density ρ (kg/m³).
        pore_radius: Effective pore radius r (m).

    Returns:
        Capillary rise height (m).
    """
    from std.math import cos
    if density <= 0.0 or pore_radius <= 0.0:
        return 0.0
    var g = 9.81
    return 2.0 * surface_tension * cos(contact_angle_rad) / (density * g * pore_radius)


fn leakance_factor(
    transmissivity: Float64, confining_thickness: Float64, confining_k: Float64
) -> Float64:
    """Leakance factor B for leaky confined aquifer.

    B = sqrt(T·b'/K')

    Args:
        transmissivity: Aquifer transmissivity T (m²/s).
        confining_thickness: Confining layer thickness b' (m).
        confining_k: Confining layer K' (m/s).

    Returns:
        Leakance factor B (m).
    """
    if confining_k <= 0.0:
        return 0.0
    return sqrt(transmissivity * confining_thickness / confining_k)


fn groundwater_age_mixing(
    tracer_young: Float64, tracer_sample: Float64, tracer_old: Float64
) -> Float64:
    """Binary mixing fraction of young water in a groundwater sample.

    f_young = (C_sample - C_old) / (C_young - C_old)

    Args:
        tracer_young: Tracer concentration in young end-member.
        tracer_sample: Tracer concentration in sample.
        tracer_old: Tracer concentration in old end-member.

    Returns:
        Fraction of young water (0–1).
    """
    var denom = tracer_young - tracer_old
    if denom == 0.0:
        return 0.5
    var f = (tracer_sample - tracer_old) / denom
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f
