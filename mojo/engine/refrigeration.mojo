"""
refrigeration.mojo — Refrigeration Engineering Library. Zero Python imports.

Pure Mojo implementations of refrigeration cycle calculations including COP,
Carnot limits, superheat/subcooling, compressor work, and efficiency ratings.

Public API:
  cop_refrigeration           — COP = Qc/W
  cop_heat_pump               — COP_hp = Qh/W
  carnot_cop_refrigeration    — COP_carnot = Tc/(Th-Tc) (Kelvin)
  carnot_cop_heat_pump        — COP_hp = Th/(Th-Tc) (Kelvin)
  refrigeration_capacity_tons — Tons = BTU/12000
  superheat                   — SH = T_suction - T_sat
  subcooling                  — SC = T_sat - T_liquid
  mass_flow_rate              — m_dot = Q/Δh
  compressor_work             — W = m_dot*(h2-h1)
  energy_efficiency_ratio     — EER = BTU/W
  seer_to_cop                 — COP ≈ SEER/3.412
  refrigerant_charge_estimate — Charge = V*ρ (kg)
"""
from std.math import abs as fabs


# ── cop_refrigeration ────────────────────────────────────────────────────────


def cop_refrigeration(qc: Float64, w: Float64) -> Float64:
    """Coefficient of Performance (cooling): COP = Qc / W.

    Args:
        qc: Cooling capacity (W or kW).
        w:  Work input (same units as qc).

    Returns:
        COP (dimensionless).
    """
    if fabs(w) < 1e-30:
        return 0.0
    return qc / w


# ── cop_heat_pump ────────────────────────────────────────────────────────────


def cop_heat_pump(qh: Float64, w: Float64) -> Float64:
    """Coefficient of Performance (heating): COP_hp = Qh / W.

    Args:
        qh: Heating capacity (W or kW).
        w:  Work input (same units as qh).

    Returns:
        COP_hp (dimensionless).
    """
    if fabs(w) < 1e-30:
        return 0.0
    return qh / w


# ── carnot_cop_refrigeration ─────────────────────────────────────────────────


def carnot_cop_refrigeration(tc: Float64, th: Float64) -> Float64:
    """Carnot COP for refrigeration: COP = Tc / (Th - Tc).

    Args:
        tc: Cold reservoir temperature (K).
        th: Hot reservoir temperature (K).

    Returns:
        Carnot COP (dimensionless).
    """
    var dt = th - tc
    if fabs(dt) < 1e-30:
        return 0.0
    return tc / dt


# ── carnot_cop_heat_pump ─────────────────────────────────────────────────────


def carnot_cop_heat_pump(th: Float64, tc: Float64) -> Float64:
    """Carnot COP for heat pump: COP_hp = Th / (Th - Tc).

    Args:
        th: Hot reservoir temperature (K).
        tc: Cold reservoir temperature (K).

    Returns:
        Carnot COP_hp (dimensionless).
    """
    var dt = th - tc
    if fabs(dt) < 1e-30:
        return 0.0
    return th / dt


# ── refrigeration_capacity_tons ──────────────────────────────────────────────


def refrigeration_capacity_tons(btu_per_hr: Float64) -> Float64:
    """Convert BTU/hr to tons of refrigeration: Tons = BTU/hr / 12000.

    Args:
        btu_per_hr: Cooling capacity in BTU/hr.

    Returns:
        Capacity in tons of refrigeration.
    """
    return btu_per_hr / 12000.0


# ── superheat ────────────────────────────────────────────────────────────────


def superheat(t_suction: Float64, t_saturation: Float64) -> Float64:
    """Superheat: SH = T_suction - T_saturation.

    Args:
        t_suction:    Suction line temperature.
        t_saturation: Saturation temperature at suction pressure.

    Returns:
        Superheat (same units as inputs).
    """
    return t_suction - t_saturation


# ── subcooling ───────────────────────────────────────────────────────────────


def subcooling(t_saturation: Float64, t_liquid: Float64) -> Float64:
    """Subcooling: SC = T_saturation - T_liquid.

    Args:
        t_saturation: Saturation temperature at condensing pressure.
        t_liquid:     Liquid line temperature.

    Returns:
        Subcooling (same units as inputs).
    """
    return t_saturation - t_liquid


# ── mass_flow_rate ───────────────────────────────────────────────────────────


def mass_flow_rate(capacity: Float64, enthalpy_diff: Float64) -> Float64:
    """Refrigerant mass flow rate: m_dot = Q / Δh.

    Args:
        capacity:     Cooling/heating capacity (W or kW).
        enthalpy_diff: Enthalpy difference across evaporator/condenser.

    Returns:
        Mass flow rate (kg/s or appropriate units).
    """
    if fabs(enthalpy_diff) < 1e-30:
        return 0.0
    return capacity / enthalpy_diff


# ── compressor_work ──────────────────────────────────────────────────────────


def compressor_work(m_dot: Float64, h2: Float64, h1: Float64) -> Float64:
    """Compressor work: W = m_dot * (h2 - h1).

    Args:
        m_dot: Mass flow rate (kg/s).
        h2:    Discharge enthalpy (kJ/kg).
        h1:    Suction enthalpy (kJ/kg).

    Returns:
        Compressor work (kW or W, matching input units).
    """
    return m_dot * (h2 - h1)


# ── energy_efficiency_ratio ──────────────────────────────────────────────────


def energy_efficiency_ratio(cooling_btu: Float64, power_watts: Float64) -> Float64:
    """Energy Efficiency Ratio: EER = BTU/hr / W.

    Args:
        cooling_btu:  Cooling capacity in BTU/hr.
        power_watts:  Electrical power input in watts.

    Returns:
        EER (BTU/hr per watt).
    """
    if fabs(power_watts) < 1e-30:
        return 0.0
    return cooling_btu / power_watts


# ── seer_to_cop ──────────────────────────────────────────────────────────────


def seer_to_cop(seer: Float64) -> Float64:
    """Convert SEER to COP: COP ≈ SEER / 3.412.

    Args:
        seer: Seasonal Energy Efficiency Ratio.

    Returns:
        Approximate COP.
    """
    return seer / 3.412


# ── refrigerant_charge_estimate ──────────────────────────────────────────────


def refrigerant_charge_estimate(system_volume: Float64, density: Float64) -> Float64:
    """Estimate refrigerant charge: Charge = V * ρ.

    Args:
        system_volume: Internal volume of the system (m³ or L).
        density:       Refrigerant density (kg/m³ or kg/L).

    Returns:
        Estimated charge in kg.
    """
    return system_volume * density
