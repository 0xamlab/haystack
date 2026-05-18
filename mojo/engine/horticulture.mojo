"""
horticulture.mojo — Plant cultivation and crop production calculations. Zero Python imports.

Public API:
  photosynthesis_rate          — A from light-response curve
  crop_growth_rate             — CGR = NAR * LAI
  net_assimilation_rate        — NAR from biomass and LAI
  specific_leaf_area           — SLA = leaf_area / leaf_mass
  transplant_shock_index       — stress from root damage fraction
  fertigation_dose             — nutrient concentration from dilution
  vpd_plant                    — vapor pressure deficit for plant stress
  chilling_requirement         — hours below threshold (chill hours)
  pruning_efficiency           — yield increase from canopy light intercept
  rooting_hormone_index        — auxin dose-response for cuttings
"""
from std.math import exp, log, sqrt


fn photosynthesis_rate(
    light_intensity: Float64, pmax: Float64, light_saturation: Float64
) -> Float64:
    """Net photosynthesis from light-response curve (rectangular hyperbola).

    A = Pmax · I / (I50 + I)

    Args:
        light_intensity: PAR irradiance (μmol/m²/s).
        pmax: Maximum net photosynthesis (μmol CO2/m²/s).
        light_saturation: Half-saturation light intensity I50 (μmol/m²/s).

    Returns:
        Net photosynthesis A (μmol CO2/m²/s).
    """
    var denom = light_saturation + light_intensity
    if denom <= 0.0:
        return 0.0
    return pmax * light_intensity / denom


fn crop_growth_rate(
    net_assimilation_rate: Float64, leaf_area_index: Float64
) -> Float64:
    """Crop growth rate: CGR = NAR × LAI.

    Args:
        net_assimilation_rate: NAR (g DM/m² leaf/day).
        leaf_area_index: LAI (m² leaf / m² ground).

    Returns:
        Crop growth rate (g DM/m² ground/day).
    """
    return net_assimilation_rate * leaf_area_index


fn net_assimilation_rate(
    biomass_2: Float64, biomass_1: Float64,
    lai_2: Float64, lai_1: Float64, days: Float64
) -> Float64:
    """Net assimilation rate from sequential harvest data.

    NAR = (W2 - W1) / ((A2 - A1) / ln(A2/A1)) / Δt

    Args:
        biomass_2: Final dry mass (g/m²).
        biomass_1: Initial dry mass (g/m²).
        lai_2: Final LAI (m²/m²).
        lai_1: Initial LAI (m²/m²).
        days: Elapsed days.

    Returns:
        NAR (g/m²/day).
    """
    if days <= 0.0 or lai_1 <= 0.0 or lai_2 <= lai_1:
        return 0.0
    var mean_lai = (lai_2 - lai_1) / log(lai_2 / lai_1)
    if mean_lai <= 0.0:
        return 0.0
    return (biomass_2 - biomass_1) / (mean_lai * days)


fn specific_leaf_area(
    leaf_area_cm2: Float64, leaf_dry_mass_g: Float64
) -> Float64:
    """Specific leaf area: SLA = leaf area / leaf dry mass.

    Args:
        leaf_area_cm2: One-sided leaf area (cm²).
        leaf_dry_mass_g: Oven-dry leaf mass (g).

    Returns:
        SLA (cm²/g).
    """
    if leaf_dry_mass_g <= 0.0:
        return 0.0
    return leaf_area_cm2 / leaf_dry_mass_g


fn transplant_shock_index(
    root_damage_fraction: Float64, stomatal_conductance_ratio: Float64
) -> Float64:
    """Transplant shock index (combined root damage and stomatal closure).

    TSI = root_damage × (1 - gs_ratio)

    Args:
        root_damage_fraction: Fraction of root system damaged (0–1).
        stomatal_conductance_ratio: gs_stressed / gs_unstressed (0–1).

    Returns:
        Shock index (0 = no stress, 1 = maximum stress).
    """
    return root_damage_fraction * (1.0 - stomatal_conductance_ratio)


fn fertigation_dose(
    target_conc_mg_l: Float64, flow_rate_l_h: Float64, stock_conc_g_l: Float64
) -> Float64:
    """Fertigation injection rate to achieve target nutrient concentration.

    injection_rate = target × flow / stock

    Args:
        target_conc_mg_l: Target nutrient concentration (mg/L = ppm).
        flow_rate_l_h: Irrigation flow rate (L/h).
        stock_conc_g_l: Stock solution concentration (g/L).

    Returns:
        Injector flow rate (mL/h).
    """
    if stock_conc_g_l <= 0.0:
        return 0.0
    # mg/L × L/h / (g/L) × (1g/1000mg) × 1000 mL/L = mL/h
    return target_conc_mg_l * flow_rate_l_h / stock_conc_g_l


fn vpd_plant(leaf_temp: Float64, air_temp: Float64, relative_humidity: Float64) -> Float64:
    """Leaf-to-air vapour pressure deficit for plant stress assessment.

    VPD_leaf = es(T_leaf) - es(T_air) * RH/100

    Args:
        leaf_temp: Leaf temperature (°C).
        air_temp: Air temperature (°C).
        relative_humidity: Relative humidity (%).

    Returns:
        Leaf-to-air VPD (kPa).
    """
    var a = 17.27
    var b = 237.7
    var es_leaf = 0.6108 * exp(a * leaf_temp / (b + leaf_temp))
    var es_air = 0.6108 * exp(a * air_temp / (b + air_temp))
    return es_leaf - es_air * relative_humidity / 100.0


fn chilling_requirement(
    daily_temps: Float64, threshold_temp: Float64, days: Float64
) -> Float64:
    """Accumulated chill hours below threshold (simplified).

    CH = hours × days / 24  if daily_mean < threshold

    Args:
        daily_temps: Mean daily temperature (°C).
        threshold_temp: Chilling temperature threshold (°C, typically 7.2°C).
        days: Number of days.

    Returns:
        Accumulated chill hours.
    """
    if daily_temps >= threshold_temp:
        return 0.0
    # Simplified: assume 24 h/day all below threshold
    return days * 24.0


fn pruning_efficiency(
    pre_prune_lai: Float64, target_lai: Float64
) -> Float64:
    """Pruning efficiency in improving canopy light distribution.

    Removing LAI above target → PAR transmission improvement (Beer-Lambert).

    Args:
        pre_prune_lai: Pre-pruning LAI.
        target_lai: Target post-pruning LAI.

    Returns:
        Light interception improvement (fraction more PAR reaching lower canopy).
    """
    if pre_prune_lai <= 0.0:
        return 0.0
    var k = 0.5  # extinction coefficient
    var i_before = 1.0 - exp(-k * pre_prune_lai)
    var i_after  = 1.0 - exp(-k * target_lai)
    return i_before - i_after


fn rooting_hormone_index(
    auxin_concentration: Float64, optimal_conc: Float64
) -> Float64:
    """Rooting efficiency from auxin dose-response (bell curve).

    Rooting index = exp(-((C - C_opt)/sigma)²)

    Args:
        auxin_concentration: Applied auxin IBA/NAA concentration (ppm).
        optimal_conc: Optimal concentration for maximum rooting (ppm).

    Returns:
        Relative rooting index (0–1, 1 = maximum).
    """
    var sigma = optimal_conc / 2.0
    if sigma <= 0.0:
        return 0.0
    var ratio = (auxin_concentration - optimal_conc) / sigma
    return exp(-ratio * ratio)
