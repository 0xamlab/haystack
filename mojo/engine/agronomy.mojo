"""
agronomy.mojo — Crop and soil science calculations. Zero Python imports.

Public API:
  crop_yield_potential         — yield = radiation * rue * harvest_index
  nitrogen_uptake_efficiency   — NUE = grain_N / soil_N_available
  soil_organic_matter_decay    — SOM(t) = SOM0 * exp(-k*t)
  evapotranspiration_penman    — simplified Penman ET estimation
  leaf_area_index              — LAI = leaf_area / ground_area
  light_use_efficiency         — LUE = biomass / intercepted_radiation
  crop_water_stress_index      — CWSI = (Tc - Ta) / (Tc_ll - Ta)
  irrigation_requirement       — IR = ET - rainfall - soil_moisture_change
  soil_cation_exchange         — CEC estimate from clay and OM content
  growing_degree_days          — GDD = max(0, (T_max+T_min)/2 - T_base)
"""
from std.math import exp, log


fn crop_yield_potential(radiation: Float64, rue: Float64, harvest_index: Float64) -> Float64:
    """Yield potential = radiation use efficiency model.

    Args:
        radiation: Intercepted photosynthetically active radiation (MJ/m²).
        rue: Radiation use efficiency (g/MJ).
        harvest_index: Fraction of biomass in grain (0–1).

    Returns:
        Crop yield (g/m²).
    """
    if radiation < 0.0 or rue < 0.0:
        return 0.0
    return radiation * rue * harvest_index


fn nitrogen_uptake_efficiency(grain_n: Float64, soil_n: Float64) -> Float64:
    """Nitrogen use efficiency (NUE) of a crop.

    Args:
        grain_n: Nitrogen in grain at harvest (kg/ha).
        soil_n: Total plant-available soil nitrogen (kg/ha).

    Returns:
        NUE (dimensionless fraction).
    """
    if soil_n <= 0.0:
        return 0.0
    return grain_n / soil_n


fn soil_organic_matter_decay(som0: Float64, k: Float64, t: Float64) -> Float64:
    """First-order decay of soil organic matter.

    Args:
        som0: Initial SOM content (%).
        k: Decomposition rate constant (yr⁻¹).
        t: Time elapsed (years).

    Returns:
        Remaining SOM (%).
    """
    if t < 0.0 or k < 0.0:
        return som0
    return som0 * exp(-k * t)


fn evapotranspiration_penman(
    rn: Float64, temp: Float64, wind: Float64, vpd: Float64
) -> Float64:
    """Simplified Penman-Monteith reference ET (mm/day).

    Args:
        rn: Net radiation (MJ/m²/day).
        temp: Mean air temperature (°C).
        wind: Wind speed at 2m (m/s).
        vpd: Vapour pressure deficit (kPa).

    Returns:
        Reference ET (mm/day).
    """
    var delta = 4098.0 * (0.6108 * exp(17.27 * temp / (temp + 237.3))) / ((temp + 237.3) ** 2.0)
    var gamma = 0.0665  # psychrometric constant kPa/°C at ~20°C
    var num = 0.408 * delta * rn + gamma * (900.0 / (temp + 273.0)) * wind * vpd
    var den = delta + gamma * (1.0 + 0.34 * wind)
    if den <= 0.0:
        return 0.0
    return num / den


fn leaf_area_index(leaf_area: Float64, ground_area: Float64) -> Float64:
    """Leaf Area Index (LAI).

    Args:
        leaf_area: Total one-sided leaf area (m²).
        ground_area: Ground area below canopy (m²).

    Returns:
        LAI (m²/m²).
    """
    if ground_area <= 0.0:
        return 0.0
    return leaf_area / ground_area


fn light_use_efficiency(biomass: Float64, intercepted_radiation: Float64) -> Float64:
    """Light use efficiency: LUE = biomass / intercepted PAR.

    Args:
        biomass: Dry matter produced (g/m²).
        intercepted_radiation: Intercepted PAR (MJ/m²).

    Returns:
        LUE (g/MJ).
    """
    if intercepted_radiation <= 0.0:
        return 0.0
    return biomass / intercepted_radiation


fn crop_water_stress_index(
    tc: Float64, ta: Float64, tc_ll: Float64
) -> Float64:
    """Crop Water Stress Index (CWSI).

    Args:
        tc: Canopy temperature (°C).
        ta: Air temperature (°C).
        tc_ll: Lower limit canopy temperature (°C, fully-irrigated baseline).

    Returns:
        CWSI (0 = no stress, 1 = full stress).
    """
    var denom = tc_ll - ta
    if denom <= 0.0:
        return 0.0
    var cwsi = (tc - ta) / denom
    if cwsi < 0.0:
        return 0.0
    if cwsi > 1.0:
        return 1.0
    return cwsi


fn irrigation_requirement(
    et: Float64, rainfall: Float64, soil_moisture_change: Float64
) -> Float64:
    """Net irrigation requirement (mm).

    Args:
        et: Crop evapotranspiration (mm).
        rainfall: Effective rainfall (mm).
        soil_moisture_change: Change in soil water storage (mm, + = depletion).

    Returns:
        Irrigation requirement (mm); 0 if rain + soil water is sufficient.
    """
    var ir = et - rainfall - soil_moisture_change
    if ir < 0.0:
        return 0.0
    return ir


fn soil_cation_exchange(clay_pct: Float64, om_pct: Float64) -> Float64:
    """Estimate cation exchange capacity (CEC) from texture and organic matter.

    Empirical approximation: CEC ≈ 0.7*clay + 3.5*OM (cmol/kg).

    Args:
        clay_pct: Clay content (% by weight).
        om_pct: Organic matter content (% by weight).

    Returns:
        CEC (cmol(+)/kg).
    """
    if clay_pct < 0.0 or om_pct < 0.0:
        return 0.0
    return 0.7 * clay_pct + 3.5 * om_pct


fn growing_degree_days(t_max: Float64, t_min: Float64, t_base: Float64) -> Float64:
    """Growing degree days accumulated in one day.

    Args:
        t_max: Daily maximum temperature (°C).
        t_min: Daily minimum temperature (°C).
        t_base: Base temperature for crop development (°C).

    Returns:
        GDD for the day (°C·day).
    """
    var t_mean = (t_max + t_min) / 2.0
    var gdd = t_mean - t_base
    if gdd < 0.0:
        return 0.0
    return gdd
