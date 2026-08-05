"""
geotechnical.mojo — Geotechnical Engineering Library. Zero Python imports.

Provides bearing capacity (Terzaghi), effective stress, earth pressure
coefficients (Rankine), elastic settlement, slope stability, and soil
phase relationships (void ratio, porosity, saturation).

Public API:
  bearing_capacity_terzaghi   — Terzaghi ultimate bearing capacity
  effective_stress             — Effective stress σ' = σ - u
  overburden_pressure          — Vertical overburden σ_v = γ*z
  coefficient_of_earth_pressure_at_rest — K0 = 1 - sin(φ)
  active_earth_pressure        — σa = Ka*σv - 2c*√Ka
  rankine_ka                   — Active earth pressure coefficient
  rankine_kp                   — Passive earth pressure coefficient
  settlement_elastic           — Simplified elastic settlement
  factor_of_safety_slope       — FS = resisting / driving
  void_ratio                   — e = n/(1-n)
  porosity_from_void_ratio     — n = e/(1+e)
  degree_of_saturation         — S = w*Gs/e
"""
from std.math import sin, sqrt


# ── Bearing capacity ─────────────────────────────────────────────────────────


fn bearing_capacity_terzaghi(
    c: Float64,
    gamma: Float64,
    d: Float64,
    b: Float64,
    nc: Float64,
    nq: Float64,
    ngamma: Float64,
) -> Float64:
    """Terzaghi ultimate bearing capacity (strip footing).

    q_ult = c*Nc + γ*D*Nq + 0.5*γ*B*Nγ
    """
    return c * nc + gamma * d * nq + 0.5 * gamma * b * ngamma


# ── Stress calculations ─────────────────────────────────────────────────────


fn effective_stress(total_stress: Float64, pore_pressure: Float64) -> Float64:
    """Effective stress: σ' = σ - u."""
    return total_stress - pore_pressure


fn overburden_pressure(depth: Float64, unit_weight: Float64) -> Float64:
    """Vertical overburden pressure: σ_v = γ * z."""
    return unit_weight * depth


# ── Earth pressure ───────────────────────────────────────────────────────────


fn coefficient_of_earth_pressure_at_rest(phi: Float64) -> Float64:
    """Jaky's at-rest earth pressure coefficient: K0 = 1 - sin(φ).

    phi in radians.
    """
    return 1.0 - sin(phi)


fn rankine_ka(phi: Float64) -> Float64:
    """Rankine active earth pressure coefficient.

    Ka = (1 - sin(φ)) / (1 + sin(φ)).  phi in radians.
    """
    return (1.0 - sin(phi)) / (1.0 + sin(phi))


fn rankine_kp(phi: Float64) -> Float64:
    """Rankine passive earth pressure coefficient.

    Kp = (1 + sin(φ)) / (1 - sin(φ)).  phi in radians.
    """
    return (1.0 + sin(phi)) / (1.0 - sin(phi))


fn active_earth_pressure(
    ka: Float64, sigma_v: Float64, cohesion: Float64
) -> Float64:
    """Active earth pressure: σa = Ka*σv - 2*c*√Ka."""
    return ka * sigma_v - 2.0 * cohesion * sqrt(ka)


# ── Settlement ───────────────────────────────────────────────────────────────


fn settlement_elastic(
    load: Float64,
    width: Float64,
    modulus: Float64,
    poisson: Float64,
) -> Float64:
    """Simplified elastic settlement: s = q*B*(1 - ν²) / E."""
    return load * width * (1.0 - poisson * poisson) / modulus


# ── Slope stability ──────────────────────────────────────────────────────────


fn factor_of_safety_slope(
    resisting_force: Float64, driving_force: Float64
) -> Float64:
    """Factor of safety for slope stability: FS = R / D."""
    return resisting_force / driving_force


# ── Soil phase relationships ─────────────────────────────────────────────────


fn void_ratio(porosity: Float64) -> Float64:
    """Void ratio from porosity: e = n / (1 - n)."""
    # The denominator zeroes at n = 1 (inf cannot cross the result wire); the
    # self-comparison rejects NaN payloads.
    if porosity >= 1.0 or porosity != porosity:
        return 0.0
    return porosity / (1.0 - porosity)


fn porosity_from_void_ratio(e: Float64) -> Float64:
    """Porosity from void ratio: n = e / (1 + e)."""
    return e / (1.0 + e)


fn degree_of_saturation(
    water_content: Float64, e: Float64, gs: Float64
) -> Float64:
    """Degree of saturation: S = w * Gs / e.

    water_content (w) as decimal, gs = specific gravity of solids.
    """
    return water_content * gs / e
