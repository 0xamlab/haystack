"""
cryogenics.mojo — Cryogenics Library. Zero Python imports.

Pure Mojo implementations of cryogenic engineering equations
including ideal gas density, Joule-Thomson cooling, Carnot COP,
liquefaction yield, boil-off rate, and superconductor estimates.

Public API:
  ideal_gas_density                — ρ = P*M/(R*T)
  joule_thomson_cooling            — ΔT = μ_JT * ΔP
  carnot_cop_cooling               — COP = Tc/(Th-Tc)
  liquefaction_yield               — y = (h1-h2)/h_g
  boiloff_rate                     — BOR = Q/(L*m)*100  (%/day)
  thermal_contraction              — ΔL = α * ΔT * L
  heat_leak_through_wall           — Q = k*A*(Th-Tc)/d
  superconductor_critical_temp_estimate — Tc(H) = Tc0*sqrt(1-H/Hc2)
  residual_resistivity_ratio       — RRR = R(300K)/R(low)
  cryocooler_input_power           — P_in = Q/COP
  vacuum_insulation_heat_flux      — radiative heat flux
  helium_lambda_point              — returns 2.17 K
"""
from std.math import sqrt, exp, log, abs as fabs


# ── ideal_gas_density ────────────────────────────────────────────────────────


fn ideal_gas_density(pressure: Float64, molar_mass: Float64, r: Float64, temperature: Float64) -> Float64:
    """ρ = P * M / (R * T)."""
    return pressure * molar_mass / (r * temperature)


# ── joule_thomson_cooling ────────────────────────────────────────────────────


fn joule_thomson_cooling(mu_jt: Float64, delta_p: Float64) -> Float64:
    """ΔT = μ_JT * ΔP."""
    return mu_jt * delta_p


# ── carnot_cop_cooling ───────────────────────────────────────────────────────


fn carnot_cop_cooling(t_cold: Float64, t_hot: Float64) -> Float64:
    """COP = Tc / (Th - Tc)."""
    # A zero temperature lift has no finite COP; the division yields inf, which cannot cross
    # the JSON result wire (the worker aborts serializing it), so answer with the sentinel.
    if fabs(t_hot - t_cold) < 1e-15:
        return 0.0
    return t_cold / (t_hot - t_cold)


# ── liquefaction_yield ───────────────────────────────────────────────────────


fn liquefaction_yield(h1: Float64, h2: Float64, h_f: Float64, h_g: Float64) -> Float64:
    """y = (h1 - h2) / h_g  (simplified Linde cycle yield)."""
    return (h1 - h2) / h_g


# ── boiloff_rate ─────────────────────────────────────────────────────────────


fn boiloff_rate(heat_leak: Float64, latent_heat: Float64, mass: Float64) -> Float64:
    """BOR = Q / (L * m) * 100  (%/day)."""
    return heat_leak / (latent_heat * mass) * 100.0


# ── thermal_contraction ─────────────────────────────────────────────────────


fn thermal_contraction(alpha: Float64, delta_t: Float64, length: Float64) -> Float64:
    """ΔL = α * ΔT * L."""
    return alpha * delta_t * length


# ── heat_leak_through_wall ───────────────────────────────────────────────────


fn heat_leak_through_wall(k: Float64, area: Float64, t_hot: Float64, t_cold: Float64, thickness: Float64) -> Float64:
    """Q = k * A * (Th - Tc) / d  (watts)."""
    return k * area * (t_hot - t_cold) / thickness


# ── superconductor_critical_temp_estimate ────────────────────────────────────


fn superconductor_critical_temp_estimate(tc0: Float64, field: Float64, hc2: Float64) -> Float64:
    """Tc(H) = Tc0 * sqrt(1 - H/Hc2)."""
    return tc0 * sqrt(1.0 - field / hc2)


# ── residual_resistivity_ratio ───────────────────────────────────────────────


fn residual_resistivity_ratio(r_300k: Float64, r_low: Float64) -> Float64:
    """RRR = R(300K) / R(low temperature)."""
    return r_300k / r_low


# ── cryocooler_input_power ───────────────────────────────────────────────────


fn cryocooler_input_power(cooling_power: Float64, cop: Float64) -> Float64:
    """P_in = Q / COP."""
    return cooling_power / cop


# ── vacuum_insulation_heat_flux ──────────────────────────────────────────────


fn vacuum_insulation_heat_flux(
    emissivity1: Float64,
    emissivity2: Float64,
    sigma: Float64,
    t_hot: Float64,
    t_cold: Float64,
) -> Float64:
    """q = σ*(T_h⁴ - T_c⁴) / (1/ε1 + 1/ε2 - 1)."""
    var th4 = t_hot * t_hot * t_hot * t_hot
    var tc4 = t_cold * t_cold * t_cold * t_cold
    var denom = 1.0 / emissivity1 + 1.0 / emissivity2 - 1.0
    return sigma * (th4 - tc4) / denom


# ── helium_lambda_point ──────────────────────────────────────────────────────


fn helium_lambda_point() -> Float64:
    """Returns the helium lambda point: 2.17 K."""
    return 2.17
