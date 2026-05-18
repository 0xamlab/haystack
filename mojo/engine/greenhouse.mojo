"""
greenhouse.mojo — Greenhouse Engineering Library.

Provides thermal, ventilation, lighting, irrigation, and yield calculations
for controlled-environment greenhouse operations.

Public API:
  heat_loss_conduction         — Q = U*A*ΔT (watts)
  ventilation_rate             — Q = V*ACH/3600 (m³/s)
  solar_gain                   — Q = τ*A*G (watts)
  heating_requirement          — H = max(0, loss - gain)
  co2_enrichment_rate          — Rate = (target-current)*volume/1e6 + leak
  light_supplementation_hours  — Hours = (target-natural)*1e6/(ppfd*3600)
  irrigation_volume            — V = ET*A/eff (liters)
  growing_area_utilization     — U = planted/total * 100
  energy_cost_heating          — Cost = kWh * rate
  yield_per_sq_meter           — Y = kg/m²
  temperature_setpoint_night   — T_night = day - DIF
  shade_factor                 — Factor = 1 - shade/100
"""
from std.math import abs as fabs


# ── heat_loss_conduction ─────────────────────────────────────────────────────


fn heat_loss_conduction(
    u_value: Float64, area: Float64, delta_t: Float64
) -> Float64:
    """Heat loss by conduction: Q = U * A * ΔT (watts).

    Args:
        u_value: Overall heat transfer coefficient (W/m²·K).
        area: Surface area (m²).
        delta_t: Temperature difference (K or °C).

    Returns:
        Heat loss (watts).
    """
    return u_value * area * delta_t


# ── ventilation_rate ─────────────────────────────────────────────────────────


fn ventilation_rate(
    volume: Float64, air_changes_per_hour: Float64
) -> Float64:
    """Ventilation flow rate: Q = V * ACH / 3600 (m³/s).

    Args:
        volume: Greenhouse volume (m³).
        air_changes_per_hour: Air changes per hour.

    Returns:
        Volumetric flow rate (m³/s).
    """
    return volume * air_changes_per_hour / 3600.0


# ── solar_gain ───────────────────────────────────────────────────────────────


fn solar_gain(
    transmittance: Float64, area: Float64, radiation: Float64
) -> Float64:
    """Solar heat gain: Q = τ * A * G (watts).

    Args:
        transmittance: Glazing transmittance (0–1).
        area: Glazing area (m²).
        radiation: Solar radiation (W/m²).

    Returns:
        Solar gain (watts).
    """
    return transmittance * area * radiation


# ── heating_requirement ──────────────────────────────────────────────────────


fn heating_requirement(
    heat_loss: Float64, solar_gain_val: Float64
) -> Float64:
    """Net heating requirement: H = max(0, loss - gain).

    Args:
        heat_loss: Total heat loss (watts).
        solar_gain_val: Solar heat gain (watts).

    Returns:
        Heating requirement (watts). Zero if gain exceeds loss.
    """
    var diff = heat_loss - solar_gain_val
    if diff < 0.0:
        return 0.0
    return diff


# ── co2_enrichment_rate ──────────────────────────────────────────────────────


fn co2_enrichment_rate(
    target_ppm: Float64,
    current_ppm: Float64,
    volume: Float64,
    leak_rate: Float64,
) -> Float64:
    """CO₂ enrichment rate: Rate = (target-current)*volume/1e6 + leak.

    Args:
        target_ppm: Target CO₂ concentration (ppm).
        current_ppm: Current CO₂ concentration (ppm).
        volume: Greenhouse volume (m³).
        leak_rate: Leakage loss rate (m³/s or L/s).

    Returns:
        CO₂ injection rate.
    """
    return (target_ppm - current_ppm) * volume / 1e6 + leak_rate


# ── light_supplementation_hours ──────────────────────────────────────────────


fn light_supplementation_hours(
    target_dli: Float64, natural_dli: Float64, ppfd: Float64
) -> Float64:
    """Supplemental lighting hours: Hours = (target-natural)*1e6/(ppfd*3600).

    Args:
        target_dli: Target daily light integral (mol/m²/day).
        natural_dli: Natural DLI (mol/m²/day).
        ppfd: Supplemental PPFD (µmol/m²/s).

    Returns:
        Required supplemental hours. Zero if natural meets target.
    """
    var deficit = target_dli - natural_dli
    if deficit <= 0.0:
        return 0.0
    if fabs(ppfd) < 1e-30:
        return 0.0
    return deficit * 1e6 / (ppfd * 3600.0)


# ── irrigation_volume ────────────────────────────────────────────────────────


fn irrigation_volume(
    et_rate: Float64, area: Float64, efficiency: Float64
) -> Float64:
    """Irrigation volume: V = ET * A / eff (liters).

    Args:
        et_rate: Evapotranspiration rate (L/m²/day).
        area: Irrigated area (m²).
        efficiency: Irrigation efficiency (0–1).

    Returns:
        Required irrigation volume (liters).
    """
    if fabs(efficiency) < 1e-30:
        return 0.0
    return et_rate * area / efficiency


# ── growing_area_utilization ─────────────────────────────────────────────────


fn growing_area_utilization(
    planted_area: Float64, total_area: Float64
) -> Float64:
    """Growing area utilization: U = planted/total * 100 (%).

    Args:
        planted_area: Area under cultivation (m²).
        total_area: Total greenhouse floor area (m²).

    Returns:
        Utilization percentage.
    """
    if fabs(total_area) < 1e-30:
        return 0.0
    return planted_area / total_area * 100.0


# ── energy_cost_heating ──────────────────────────────────────────────────────


fn energy_cost_heating(kwh: Float64, rate: Float64) -> Float64:
    """Heating energy cost: Cost = kWh * rate.

    Args:
        kwh: Energy consumed (kWh).
        rate: Cost per kWh (currency unit).

    Returns:
        Total cost.
    """
    return kwh * rate


# ── yield_per_sq_meter ───────────────────────────────────────────────────────


fn yield_per_sq_meter(
    total_kg: Float64, area_m2: Float64
) -> Float64:
    """Yield per square metre: Y = kg / m².

    Args:
        total_kg: Total harvest weight (kg).
        area_m2: Growing area (m²).

    Returns:
        Yield (kg/m²).
    """
    if fabs(area_m2) < 1e-30:
        return 0.0
    return total_kg / area_m2


# ── temperature_setpoint_night ───────────────────────────────────────────────


fn temperature_setpoint_night(
    day_temp: Float64, dif: Float64
) -> Float64:
    """Night temperature setpoint: T_night = day_temp - DIF.

    Args:
        day_temp: Daytime temperature setpoint (°C).
        dif: DIF value (day − night difference, °C).

    Returns:
        Night temperature setpoint (°C).
    """
    return day_temp - dif


# ── shade_factor ─────────────────────────────────────────────────────────────


fn shade_factor(shade_pct: Float64) -> Float64:
    """Shade factor: Factor = 1 - shade/100.

    Args:
        shade_pct: Shade percentage (0–100).

    Returns:
        Light transmission factor (0–1).
    """
    return 1.0 - shade_pct / 100.0
