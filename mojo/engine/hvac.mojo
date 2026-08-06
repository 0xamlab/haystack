"""
hvac.mojo — HVAC (Heating, Ventilation, Air Conditioning) Library.

Zero Python imports. Provides sensible/latent heat loads, cooling tonnage,
air changes, duct velocity, COP/EER conversion, and degree-day calculations
for the Codna Decision Engine.

Public API:
  sensible_heat_load     — Q = 1.08 * CFM * ΔT  (BTU/hr)
  latent_heat_load       — Q = 0.68 * CFM * ΔW  (BTU/hr)
  total_heat_load        — Q_total = Q_s + Q_l
  sensible_heat_ratio    — SHR = Q_s / Q_total
  cooling_tons           — Tons = BTU/hr / 12000
  btu_from_tons          — BTU/hr = tons * 12000
  air_changes_per_hour   — ACH = 60 * CFM / V
  duct_velocity          — v = CFM / A  (ft/min)
  cop_to_eer             — EER = COP * 3.412
  eer_to_cop             — COP = EER / 3.412
  heating_degree_days    — HDD = max(0, base - avg)
  cooling_degree_days    — CDD = max(0, avg - base)
"""


# ── Heat loads ───────────────────────────────────────────────────────────────


def sensible_heat_load(cfm: Float64, delta_t: Float64) -> Float64:
    """Sensible heat load Q = 1.08 * CFM * ΔT  (BTU/hr).

    cfm = airflow (cubic feet per minute).
    delta_t = temperature difference (°F).
    """
    return 1.08 * cfm * delta_t


def latent_heat_load(cfm: Float64, delta_w: Float64) -> Float64:
    """Latent heat load Q = 0.68 * CFM * ΔW  (BTU/hr).

    cfm = airflow (cubic feet per minute).
    delta_w = humidity ratio difference (grains/lb).
    """
    return 0.68 * cfm * delta_w


def total_heat_load(sensible: Float64, latent: Float64) -> Float64:
    """Total heat load Q_total = Q_sensible + Q_latent  (BTU/hr)."""
    return sensible + latent


def sensible_heat_ratio(sensible: Float64, total: Float64) -> Float64:
    """Sensible heat ratio SHR = Q_sensible / Q_total."""
    return sensible / total


# ── Cooling capacity ─────────────────────────────────────────────────────────


def cooling_tons(btu_per_hr: Float64) -> Float64:
    """Cooling capacity in tons = BTU/hr / 12000."""
    return btu_per_hr / 12000.0


def btu_from_tons(tons: Float64) -> Float64:
    """Convert cooling tons to BTU/hr = tons * 12000."""
    return tons * 12000.0


# ── Airflow & duct ───────────────────────────────────────────────────────────


def air_changes_per_hour(cfm: Float64, room_volume_cf: Float64) -> Float64:
    """Air changes per hour ACH = 60 * CFM / V.

    cfm = cubic feet per minute, room_volume_cf = room volume in cubic feet.
    """
    return 60.0 * cfm / room_volume_cf


def duct_velocity(cfm: Float64, duct_area_sqft: Float64) -> Float64:
    """Duct air velocity v = CFM / A  (ft/min).

    duct_area_sqft = cross-sectional area of duct in square feet.
    """
    return cfm / duct_area_sqft


# ── Efficiency conversions ───────────────────────────────────────────────────


def cop_to_eer(cop: Float64) -> Float64:
    """Convert COP to EER: EER = COP * 3.412."""
    return cop * 3.412


def eer_to_cop(eer: Float64) -> Float64:
    """Convert EER to COP: COP = EER / 3.412."""
    return eer / 3.412


# ── Degree days ──────────────────────────────────────────────────────────────


def heating_degree_days(base_temp: Float64, avg_temp: Float64) -> Float64:
    """Heating degree days HDD = max(0, base_temp - avg_temp)."""
    var diff = base_temp - avg_temp
    if diff > 0.0:
        return diff
    return 0.0


def cooling_degree_days(avg_temp: Float64, base_temp: Float64) -> Float64:
    """Cooling degree days CDD = max(0, avg_temp - base_temp)."""
    var diff = avg_temp - base_temp
    if diff > 0.0:
        return diff
    return 0.0
