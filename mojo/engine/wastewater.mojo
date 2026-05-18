"""
wastewater.mojo — Wastewater Treatment Library. Zero Python imports.

Pure Mojo implementations of fundamental wastewater treatment equations
including BOD removal, hydraulic and solids retention times, F/M ratio,
sludge volume index, disinfection, and biological treatment design.

Public API:
  bod_removal_efficiency           — η = (BOD_in - BOD_out)/BOD_in * 100
  hydraulic_retention_time         — HRT = V/Q
  solids_retention_time            — SRT = V*X/(Qw*Xw+Qe*Xe)
  food_to_microorganism_ratio      — F/M = Q*S0/(V*X)
  sludge_volume_index              — SVI = SV*1000/MLSS
  oxygen_demand                    — O2 = Q*(S0-Se)*f
  chlorine_demand                  — Demand = Dose - Residual
  ct_value                         — CT = C*T
  alkalinity_consumption           — Alk = 7.14 * NH4_removed
  sludge_production                — P = Y*ΔS - kd*X
  trickling_filter_efficiency      — E simplified NRC formula
  detention_time_settling          — t = depth/overflow_rate
"""
from std.math import sqrt, exp, log, abs as fabs


# ── bod_removal_efficiency ───────────────────────────────────────────────────


fn bod_removal_efficiency(bod_in: Float64, bod_out: Float64) -> Float64:
    """η = (BOD_in - BOD_out) / BOD_in * 100  (percent removal)."""
    if bod_in == 0.0:
        return 0.0
    return (bod_in - bod_out) / bod_in * 100.0


# ── hydraulic_retention_time ─────────────────────────────────────────────────


fn hydraulic_retention_time(volume: Float64, flow_rate: Float64) -> Float64:
    """HRT = V / Q  (hours, with consistent units)."""
    if flow_rate == 0.0:
        return 0.0
    return volume / flow_rate


# ── solids_retention_time ────────────────────────────────────────────────────


fn solids_retention_time(
    volume: Float64,
    mlss: Float64,
    waste_flow: Float64,
    waste_ss: Float64,
    effluent_flow: Float64,
    effluent_ss: Float64,
) -> Float64:
    """SRT = V*X / (Qw*Xw + Qe*Xe)  (days)."""
    var denom = waste_flow * waste_ss + effluent_flow * effluent_ss
    if denom == 0.0:
        return 0.0
    return (volume * mlss) / denom


# ── food_to_microorganism_ratio ──────────────────────────────────────────────


fn food_to_microorganism_ratio(
    q: Float64, s0: Float64, v: Float64, x: Float64
) -> Float64:
    """F/M = Q*S0 / (V*X)  (day^-1)."""
    var denom = v * x
    if denom == 0.0:
        return 0.0
    return (q * s0) / denom


# ── sludge_volume_index ─────────────────────────────────────────────────────


fn sludge_volume_index(
    settled_volume_ml: Float64, mlss_mg_l: Float64
) -> Float64:
    """SVI = (SV_mL/L * 1000) / MLSS_mg/L  (mL/g)."""
    if mlss_mg_l == 0.0:
        return 0.0
    return settled_volume_ml * 1000.0 / mlss_mg_l


# ── oxygen_demand ────────────────────────────────────────────────────────────


fn oxygen_demand(
    q: Float64, s0: Float64, se: Float64, f: Float64
) -> Float64:
    """O2 = Q * (S0 - Se) * f  (kg/day simplified)."""
    return q * (s0 - se) * f


# ── chlorine_demand ──────────────────────────────────────────────────────────


fn chlorine_demand(dose: Float64, residual: Float64) -> Float64:
    """Chlorine Demand = Dose - Residual  (mg/L)."""
    return dose - residual


# ── ct_value ─────────────────────────────────────────────────────────────────


fn ct_value(concentration: Float64, contact_time: Float64) -> Float64:
    """CT = C * T  (mg·min/L)."""
    return concentration * contact_time


# ── alkalinity_consumption ───────────────────────────────────────────────────


fn alkalinity_consumption(ammonia_removed: Float64) -> Float64:
    """Alkalinity consumed = 7.14 * NH4_removed  (mg/L as CaCO3)."""
    return 7.14 * ammonia_removed


# ── sludge_production ───────────────────────────────────────────────────────


fn sludge_production(
    yield_coeff: Float64,
    substrate_removed: Float64,
    decay_rate: Float64,
    biomass: Float64,
) -> Float64:
    """P = Y * ΔS - kd * X  (kg/day biomass production)."""
    return yield_coeff * substrate_removed - decay_rate * biomass


# ── trickling_filter_efficiency ──────────────────────────────────────────────


fn trickling_filter_efficiency(
    bod_in: Float64, recirculation_ratio: Float64
) -> Float64:
    """E = 1 / (1 + 0.4432 * sqrt(BOD_in / (1 + R)))  (simplified NRC).
    Returns fractional efficiency (0-1)."""
    if bod_in <= 0.0:
        return 0.0
    var inner = bod_in / (1.0 + recirculation_ratio)
    return 1.0 / (1.0 + 0.4432 * sqrt(inner))


# ── detention_time_settling ──────────────────────────────────────────────────


fn detention_time_settling(
    depth: Float64, overflow_rate: Float64
) -> Float64:
    """t = depth / overflow_rate  (hours)."""
    if overflow_rate == 0.0:
        return 0.0
    return depth / overflow_rate
