"""
hydroponics.mojo — Hydroponics / Controlled Environment Agriculture Library.

Provides nutrient, lighting, climate, and yield calculations for CEA systems.

Public API:
  ec_from_tds              — EC = TDS * conversion_factor / 1000
  tds_from_ec              — TDS = EC / conversion_factor * 1000
  nutrient_concentration   — C = stock / (volume * 1000) * 1000 (ppm)
  ph_adjustment_acid       — acid_ml = (current - target) * buffer
  light_daily_integral     — DLI = PPFD * hours * 3600 / 1e6
  vpd                      — VPD = (1 - RH/100) * SVP
  water_consumption_rate   — Rate = transpiration * area
  nutrient_uptake_rate     — Rate = (start - end) * volume / time
  grow_light_efficiency    — Eff = PPF / watts
  reservoir_dilution       — water_add = volume * (current/target - 1)
  yield_per_area           — Y = kg / m²
  crop_cycle_roi           — ROI = (revenue - costs) / costs * 100
"""
from std.math import exp, abs as fabs


# ── ec_from_tds ──────────────────────────────────────────────────────────────


fn ec_from_tds(tds_ppm: Float64, conversion_factor: Float64) -> Float64:
    """Convert TDS (ppm) to EC (mS/cm): EC = TDS * factor / 1000.

    Args:
        tds_ppm: Total dissolved solids (ppm).
        conversion_factor: Conversion factor (typically 0.5–0.7).

    Returns:
        Electrical conductivity (mS/cm).
    """
    return tds_ppm * conversion_factor / 1000.0


# ── tds_from_ec ──────────────────────────────────────────────────────────────


fn tds_from_ec(ec_ms: Float64, conversion_factor: Float64) -> Float64:
    """Convert EC (mS/cm) to TDS (ppm): TDS = EC / factor * 1000.

    Args:
        ec_ms: Electrical conductivity (mS/cm).
        conversion_factor: Conversion factor (typically 0.5–0.7).

    Returns:
        Total dissolved solids (ppm).
    """
    if fabs(conversion_factor) < 1e-30:
        return 0.0
    return ec_ms / conversion_factor * 1000.0


# ── nutrient_concentration ───────────────────────────────────────────────────


fn nutrient_concentration(
    stock_ml: Float64, dilution_volume_l: Float64
) -> Float64:
    """Nutrient concentration: C = stock_ml / (volume_L * 1000) * 1000 (ppm).

    Simplified: C = stock_ml / volume_L.

    Args:
        stock_ml: Volume of stock solution (mL).
        dilution_volume_l: Total dilution volume (L).

    Returns:
        Concentration (ppm).
    """
    if fabs(dilution_volume_l) < 1e-30:
        return 0.0
    return stock_ml / dilution_volume_l


# ── ph_adjustment_acid ───────────────────────────────────────────────────────


fn ph_adjustment_acid(
    current_ph: Float64, target_ph: Float64, buffer_capacity: Float64
) -> Float64:
    """Acid needed to lower pH: acid_ml = (current - target) * buffer.

    Args:
        current_ph: Current pH value.
        target_ph: Target pH value.
        buffer_capacity: Buffer capacity (mL acid per pH unit).

    Returns:
        Volume of acid needed (mL). Returns 0 if target >= current.
    """
    var diff = current_ph - target_ph
    if diff <= 0.0:
        return 0.0
    return diff * buffer_capacity


# ── light_daily_integral ─────────────────────────────────────────────────────


fn light_daily_integral(ppfd: Float64, hours: Float64) -> Float64:
    """Daily light integral: DLI = PPFD * hours * 3600 / 1e6 (mol/m²/day).

    Args:
        ppfd: Photosynthetic photon flux density (µmol/m²/s).
        hours: Photoperiod (hours).

    Returns:
        DLI (mol/m²/day).
    """
    return ppfd * hours * 3600.0 / 1e6


# ── vpd ──────────────────────────────────────────────────────────────────────


fn vpd(temperature: Float64, humidity: Float64) -> Float64:
    """Vapour pressure deficit: VPD = (1 - RH/100) * SVP.

    SVP = 0.6108 * exp(17.27 * T / (T + 237.3)) (kPa).

    Args:
        temperature: Temperature (°C).
        humidity: Relative humidity (%).

    Returns:
        VPD (kPa).
    """
    var svp = 0.6108 * exp(17.27 * temperature / (temperature + 237.3))
    return (1.0 - humidity / 100.0) * svp


# ── water_consumption_rate ───────────────────────────────────────────────────


fn water_consumption_rate(
    transpiration: Float64, area: Float64
) -> Float64:
    """Water consumption rate: Rate = transpiration * area (L/day).

    Args:
        transpiration: Transpiration rate per unit area (L/m²/day).
        area: Growing area (m²).

    Returns:
        Water consumption (L/day).
    """
    return transpiration * area


# ── nutrient_uptake_rate ─────────────────────────────────────────────────────


fn nutrient_uptake_rate(
    conc_start: Float64,
    conc_end: Float64,
    volume: Float64,
    time_hours: Float64,
) -> Float64:
    """Nutrient uptake rate: Rate = (start - end) * volume / time.

    Args:
        conc_start: Starting concentration (ppm).
        conc_end: Ending concentration (ppm).
        volume: Reservoir volume (L).
        time_hours: Time elapsed (hours).

    Returns:
        Uptake rate (ppm·L/h).
    """
    if fabs(time_hours) < 1e-30:
        return 0.0
    return (conc_start - conc_end) * volume / time_hours


# ── grow_light_efficiency ────────────────────────────────────────────────────


fn grow_light_efficiency(ppf: Float64, watts: Float64) -> Float64:
    """Grow light efficacy: Eff = PPF / W (µmol/J).

    Args:
        ppf: Photosynthetic photon flux (µmol/s).
        watts: Power draw (W).

    Returns:
        Efficacy (µmol/J).
    """
    if fabs(watts) < 1e-30:
        return 0.0
    return ppf / watts


# ── reservoir_dilution ───────────────────────────────────────────────────────


fn reservoir_dilution(
    current_ec: Float64, target_ec: Float64, volume: Float64
) -> Float64:
    """Water to add for dilution: water_add = volume * (current/target - 1).

    Args:
        current_ec: Current EC (mS/cm).
        target_ec: Target EC (mS/cm).
        volume: Current reservoir volume (L).

    Returns:
        Volume of water to add (L). Returns 0 if target >= current.
    """
    if fabs(target_ec) < 1e-30:
        return 0.0
    var ratio = current_ec / target_ec
    if ratio <= 1.0:
        return 0.0
    return volume * (ratio - 1.0)


# ── yield_per_area ───────────────────────────────────────────────────────────


fn yield_per_area(harvest_kg: Float64, grow_area_m2: Float64) -> Float64:
    """Yield per area: Y = harvest_kg / grow_area_m² (kg/m²).

    Args:
        harvest_kg: Harvest weight (kg).
        grow_area_m2: Growing area (m²).

    Returns:
        Yield (kg/m²).
    """
    if fabs(grow_area_m2) < 1e-30:
        return 0.0
    return harvest_kg / grow_area_m2


# ── crop_cycle_roi ───────────────────────────────────────────────────────────


fn crop_cycle_roi(revenue: Float64, costs: Float64) -> Float64:
    """Crop cycle ROI: ROI = (revenue - costs) / costs * 100 (%).

    Args:
        revenue: Revenue from crop sale.
        costs: Total production costs.

    Returns:
        ROI (%).
    """
    if fabs(costs) < 1e-30:
        return 0.0
    return (revenue - costs) / costs * 100.0
