"""
cryology.mojo — Ice, permafrost, and frozen ground science calculations. Zero Python imports.

Public API:
  permafrost_thickness          — from mean annual temperature
  active_layer_depth            — Stefan equation seasonal thaw
  ground_ice_content            — volumetric excess ice fraction
  freeze_thaw_cycles            — estimate from temperature range
  thermal_conductivity_frozen   — Kersten mixing model
  ice_wedge_volume              — wedge geometry approximation
  thermokarst_subsidence        — from ice volume loss
  permafrost_carbon_release     — from RCP temperature scenario
  sea_ice_extent_anomaly        — deviation from climatology
  snow_ice_albedo_feedback      — climate feedback strength
"""
from std.math import sqrt, log, exp


fn permafrost_thickness(
    mean_annual_temp_c: Float64, geothermal_gradient: Float64
) -> Float64:
    """Permafrost thickness from linear thermal gradient.

    H = |MAAT| / geothermal_gradient  (simplified)

    Args:
        mean_annual_temp_c: Mean annual air temperature (°C, must be <0).
        geothermal_gradient: Geothermal gradient (°C/m, typical 0.01–0.03).

    Returns:
        Permafrost thickness (m).
    """
    if mean_annual_temp_c >= 0.0 or geothermal_gradient <= 0.0:
        return 0.0
    return (-mean_annual_temp_c) / geothermal_gradient


fn active_layer_depth(
    thawing_index_degree_days: Float64, thermal_conductivity: Float64,
    volumetric_heat_capacity: Float64
) -> Float64:
    """Active layer thickness from Stefan equation.

    ALT = sqrt(2 · k · It / (L · n))  simplified as sqrt(2k·It / (C))

    Args:
        thawing_index_degree_days: Accumulated thawing degree-days (°C·days).
        thermal_conductivity: Thermal conductivity of soil (W/m/K).
        volumetric_heat_capacity: Volumetric heat capacity (J/m³/K).

    Returns:
        Active layer thickness (m).
    """
    if volumetric_heat_capacity <= 0.0:
        return 0.0
    var numerator = 2.0 * thermal_conductivity * thawing_index_degree_days * 86400.0
    return sqrt(numerator / volumetric_heat_capacity)


fn ground_ice_content(
    total_water: Float64, total_volume: Float64
) -> Float64:
    """Volumetric ground ice content.

    θ_ice = V_ice / V_total

    Args:
        total_water: Volume of ice in sample (m³).
        total_volume: Total volume of sample (m³).

    Returns:
        Ice content fraction (0–1).
    """
    if total_volume <= 0.0:
        return 0.0
    return total_water / total_volume


fn freeze_thaw_cycles(
    daily_temp_range: Float64, season_length_days: Float64
) -> Float64:
    """Estimated annual freeze-thaw cycles from temperature range.

    cycles ≈ season_length × (1 / period)  where period ≈ range / crossing_rate

    Args:
        daily_temp_range: Mean daily temperature range (°C).
        season_length_days: Length of transitional season (days).

    Returns:
        Estimated freeze-thaw cycles per year.
    """
    if daily_temp_range <= 0.0:
        return 0.0
    var crossings_per_day = 1.0 if daily_temp_range > 1.0 else daily_temp_range
    return crossings_per_day * season_length_days


fn thermal_conductivity_frozen(
    mineral_k: Float64, ice_k: Float64, mineral_fraction: Float64
) -> Float64:
    """Geometric mean thermal conductivity of frozen soil.

    k_frozen = k_mineral^f × k_ice^(1-f)

    Args:
        mineral_k: Thermal conductivity of mineral grains (W/m/K, ~3).
        ice_k: Thermal conductivity of ice (W/m/K, ~2.2).
        mineral_fraction: Volume fraction of mineral grains (0–1).

    Returns:
        Effective thermal conductivity (W/m/K).
    """
    var ice_frac = 1.0 - mineral_fraction
    return (mineral_k ** mineral_fraction) * (ice_k ** ice_frac)


fn ice_wedge_volume(
    width_m: Float64, depth_m: Float64, length_m: Float64
) -> Float64:
    """Volume of a V-shaped ice wedge.

    V = 0.5 × width × depth × length

    Args:
        width_m: Wedge width at top (m).
        depth_m: Wedge depth (m).
        length_m: Wedge length (m).

    Returns:
        Ice wedge volume (m³).
    """
    return 0.5 * width_m * depth_m * length_m


fn thermokarst_subsidence(
    ice_content: Float64, layer_thickness_m: Float64
) -> Float64:
    """Ground subsidence from thaw of ice-rich permafrost.

    subsidence = θ_ice × thickness × (ρ_water / ρ_ice - 1) ≈ θ_ice × thickness × 0.09

    Args:
        ice_content: Volumetric ice content (0–1).
        layer_thickness_m: Thickness of thawing layer (m).

    Returns:
        Subsidence (m).
    """
    return ice_content * layer_thickness_m * 0.09


fn permafrost_carbon_release(
    carbon_pool_pg: Float64, warming_c: Float64, sensitivity: Float64
) -> Float64:
    """Permafrost carbon release estimate from warming.

    release = pool × sensitivity × ΔT

    Args:
        carbon_pool_pg: Permafrost carbon pool (Pg C, ~1500 Pg total).
        warming_c: Temperature increase scenario (°C).
        sensitivity: Release sensitivity (fraction per °C, ~0.02–0.05).

    Returns:
        Cumulative carbon release (Pg C).
    """
    return carbon_pool_pg * sensitivity * warming_c


fn sea_ice_extent_anomaly(
    observed_million_km2: Float64, climatology_million_km2: Float64
) -> Float64:
    """Sea ice extent anomaly relative to climatological mean.

    anomaly = observed - climatology

    Args:
        observed_million_km2: Observed extent (million km²).
        climatology_million_km2: Climatological mean (million km²).

    Returns:
        Anomaly (million km²; negative = below average).
    """
    return observed_million_km2 - climatology_million_km2


fn snow_ice_albedo_feedback(
    snow_area_change_million_km2: Float64, albedo_diff: Float64,
    solar_forcing_w_m2: Float64
) -> Float64:
    """Snow-ice albedo feedback radiative forcing.

    ΔF = ΔA × Δα × Q

    Args:
        snow_area_change_million_km2: Change in snow/ice area (10⁶ km²).
        albedo_diff: Albedo difference (snow/ice vs. open ocean/land, ~0.5).
        solar_forcing_w_m2: Incoming solar radiation (W/m², ~342 global mean).

    Returns:
        Radiative forcing (W/m² global mean; negative = cooling feedback).
    """
    var area_m2 = snow_area_change_million_km2 * 1e12
    var earth_area = 5.1e14  # m²
    return -(area_m2 / earth_area) * albedo_diff * solar_forcing_w_m2
