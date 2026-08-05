"""
combustion.mojo — Combustion Engineering Library. Zero Python imports.

Pure Mojo implementations of combustion thermodynamics, efficiency, flame
properties, and emissions functions.

Public API:
  stoichiometric_air_fuel_ratio — AFR_s simplified for CxHy fuels
  equivalence_ratio             — φ = AFR_s / AFR_actual
  excess_air_percentage         — EA = (1/φ - 1) * 100
  adiabatic_flame_temp_estimate — T_ad = T_r + Q/(m*cp)
  lower_heating_value_methane   — LHV of CH4 ≈ 50.0 MJ/kg
  thermal_efficiency            — η = W / Q_in
  carnot_efficiency             — η_c = 1 - T_c/T_h
  brake_specific_fuel_consumption — BSFC = m_fuel / P
  combustion_efficiency         — η_c = Q_rel / Q_theo
  flame_speed_laminar           — SL = SU0 * (T/T0)^α * (P/P0)^β
  nox_formation_rate            — rate ∝ O2_frac * exp(-const/T)
  heat_release_rate             — dQ = (γ/(γ-1))*p*dV + (1/(γ-1))*V*dp
"""
from std.math import exp, log


# ── Constants ─────────────────────────────────────────────────────────────────

comptime LN10: Float64 = 2.302585092994046


# ── stoichiometric_air_fuel_ratio ─────────────────────────────────────────────


fn stoichiometric_air_fuel_ratio(
    c: Float64, h: Float64, o_fuel: Float64
) -> Float64:
    """Simplified stoichiometric AFR for CxHy fuels.
    AFR_s = (c/12*32 + h/4*32 - o_fuel) / 0.233.
    c, h, o_fuel are mass fractions (kg per kg fuel)."""
    return (c / 12.0 * 32.0 + h / 4.0 * 32.0 - o_fuel) / 0.233


# ── equivalence_ratio ─────────────────────────────────────────────────────────


fn equivalence_ratio(actual_afr: Float64, stoich_afr: Float64) -> Float64:
    """Equivalence ratio: φ = AFR_s / AFR_actual.
    φ < 1 = lean, φ > 1 = rich, φ = 1 = stoichiometric."""
    return stoich_afr / actual_afr


# ── excess_air_percentage ─────────────────────────────────────────────────────


fn excess_air_percentage(phi: Float64) -> Float64:
    """Excess air percentage: EA = (1/φ - 1) * 100."""
    return (1.0 / phi - 1.0) * 100.0


# ── adiabatic_flame_temp_estimate ─────────────────────────────────────────────


fn adiabatic_flame_temp_estimate(
    t_reactants: Float64,
    heat_release: Float64,
    cp_products: Float64,
    mass_products: Float64,
) -> Float64:
    """Adiabatic flame temperature: T_ad = T_r + Q/(m*cp).
    All units SI (K, J, kg, J/(kg·K))."""
    return t_reactants + heat_release / (mass_products * cp_products)


# ── lower_heating_value_methane ───────────────────────────────────────────────


fn lower_heating_value_methane() -> Float64:
    """LHV of methane (CH4) ≈ 50.0 MJ/kg. Returns MJ/kg."""
    return 50.0


# ── thermal_efficiency ────────────────────────────────────────────────────────


fn thermal_efficiency(work_out: Float64, heat_in: Float64) -> Float64:
    """Thermal efficiency: η = W / Q_in."""
    return work_out / heat_in


# ── carnot_efficiency ─────────────────────────────────────────────────────────


fn carnot_efficiency(t_hot: Float64, t_cold: Float64) -> Float64:
    """Carnot efficiency: η_c = 1 - T_c/T_h. Temperatures in Kelvin."""
    return 1.0 - t_cold / t_hot


# ── brake_specific_fuel_consumption ───────────────────────────────────────────


fn brake_specific_fuel_consumption(
    fuel_rate: Float64, power: Float64
) -> Float64:
    """BSFC = m_fuel / P (kg/kWh when fuel_rate in kg/h, power in kW)."""
    return fuel_rate / power


# ── combustion_efficiency ─────────────────────────────────────────────────────


fn combustion_efficiency(
    heat_released: Float64, theoretical_heat: Float64
) -> Float64:
    """Combustion efficiency: η_c = Q_rel / Q_theo."""
    return heat_released / theoretical_heat


# ── flame_speed_laminar ───────────────────────────────────────────────────────


fn flame_speed_laminar(
    su0: Float64,
    t_ratio: Float64,
    pressure_ratio: Float64,
    alpha: Float64,
    beta: Float64,
) -> Float64:
    """Laminar flame speed: SL = SU0 * (T/T0)^α * (P/P0)^β.
    t_ratio = T/T0, pressure_ratio = P/P0."""
    # x^a = exp(a*ln(x))
    var t_term = exp(alpha * log(t_ratio))
    var p_term = exp(beta * log(pressure_ratio))
    return su0 * t_term * p_term


# ── nox_formation_rate ────────────────────────────────────────────────────────


fn nox_formation_rate(temp: Float64, oxygen_fraction: Float64) -> Float64:
    """Simplified NOx formation rate ∝ O2_frac * exp(-const/T).
    Uses Zeldovich-inspired constant = 38000 K."""
    return oxygen_fraction * exp(-38000.0 / temp)


# ── heat_release_rate ─────────────────────────────────────────────────────────


fn heat_release_rate(
    pressure: Float64,
    volume: Float64,
    gamma: Float64,
    dv: Float64,
    dp: Float64,
) -> Float64:
    """Simplified single-step heat release rate:
    dQ = (γ/(γ-1))*p*dV + (1/(γ-1))*V*dp."""
    var gm1 = gamma - 1.0
    if gm1 == 0.0:
        return 0.0  # γ=1 divides by zero; inf cannot cross the result wire
    return (gamma / gm1) * pressure * dv + (1.0 / gm1) * volume * dp
