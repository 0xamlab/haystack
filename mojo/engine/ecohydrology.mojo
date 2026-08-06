"""
ecohydrology.mojo — Water-ecology interaction calculations. Zero Python imports.

Public API:
  interception_loss             — Gash model canopy interception
  transpiration_priestley_taylor — PT evapotranspiration
  root_water_uptake             — from soil moisture profile
  streamflow_baseflow_index     — BFI from hydrograph
  wetland_retention_time        — hydraulic RT from volume and flow
  riparian_buffer_efficiency    — nitrate removal in buffer
  ecohydrological_stress        — soil water deficit effect on GPP
  flood_pulse_benefit           — floodplain productivity index
  water_table_depth_et          — ET suppression below WT
  catchment_runoff_ratio        — annual Q/P
"""
from std.math import exp, log, sqrt


def interception_loss(
    rainfall: Float64, canopy_storage_mm: Float64, evaporation_rate: Float64
) -> Float64:
    """Rutter/Gash canopy interception loss.

    I = min(rainfall, S) + E_canopy_fraction

    Args:
        rainfall: Storm rainfall (mm).
        canopy_storage_mm: Canopy storage capacity S (mm, ~1–3 mm).
        evaporation_rate: Wet-canopy evaporation fraction of PET (0–1).

    Returns:
        Interception loss (mm).
    """
    var direct = rainfall if rainfall < canopy_storage_mm else canopy_storage_mm
    var evap_additional = (rainfall - direct) * evaporation_rate
    if evap_additional < 0.0:
        evap_additional = 0.0
    return direct + evap_additional


def transpiration_priestley_taylor(
    net_radiation_w_m2: Float64, soil_heat_w_m2: Float64,
    temperature_c: Float64, alpha: Float64
) -> Float64:
    """Priestley-Taylor transpiration.

    ET = α × Δ/(Δ+γ) × (Rn - G) / λ

    Args:
        net_radiation_w_m2: Net radiation Rn (W/m²).
        soil_heat_w_m2: Soil heat flux G (W/m²).
        temperature_c: Air temperature (°C).
        alpha: PT coefficient (1.26 for well-watered surface).

    Returns:
        ET rate (mm/day).
    """
    var delta = 4098.0 * 0.6108 * exp(17.27 * temperature_c / (temperature_c + 237.3)) / ((temperature_c + 237.3) ** 2)
    var gamma = 0.067  # kPa/°C at standard conditions
    var lambda_v = 2.45  # MJ/kg latent heat of vaporisation
    var rn_g = (net_radiation_w_m2 - soil_heat_w_m2) * 86400.0 / 1e6  # W/m² to MJ/m²/day
    return alpha * delta / (delta + gamma) * rn_g / lambda_v


def root_water_uptake(
    soil_moisture: Float64, field_capacity: Float64,
    wilting_point: Float64, max_uptake: Float64
) -> Float64:
    """Root water uptake as fraction of potential based on soil moisture.

    uptake = max_uptake × (θ - θ_wp) / (θ_fc - θ_wp)

    Args:
        soil_moisture: Volumetric soil water content (m³/m³).
        field_capacity: Field capacity θ_fc.
        wilting_point: Permanent wilting point θ_wp.
        max_uptake: Potential uptake at field capacity (mm/day).

    Returns:
        Actual root water uptake (mm/day).
    """
    var range = field_capacity - wilting_point
    if range <= 0.0:
        return 0.0
    var frac = (soil_moisture - wilting_point) / range
    if frac < 0.0:
        return 0.0
    if frac > 1.0:
        frac = 1.0
    return max_uptake * frac


def streamflow_baseflow_index(
    baseflow_mm: Float64, total_streamflow_mm: Float64
) -> Float64:
    """Baseflow Index: BFI = baseflow / total streamflow.

    Args:
        baseflow_mm: Estimated annual baseflow (mm/yr).
        total_streamflow_mm: Total annual streamflow (mm/yr).

    Returns:
        BFI (0–1; >0.5 = groundwater-dominated).
    """
    if total_streamflow_mm <= 0.0:
        return 0.0
    return baseflow_mm / total_streamflow_mm


def wetland_retention_time(
    volume_m3: Float64, inflow_m3_per_day: Float64
) -> Float64:
    """Wetland hydraulic retention time.

    HRT = V / Q

    Args:
        volume_m3: Wetland water volume (m³).
        inflow_m3_per_day: Inflow rate (m³/day).

    Returns:
        Hydraulic retention time (days).
    """
    if inflow_m3_per_day <= 0.0:
        return 0.0
    return volume_m3 / inflow_m3_per_day


def riparian_buffer_efficiency(
    width_m: Float64, slope: Float64, saturated_conductivity: Float64
) -> Float64:
    """Nitrate removal efficiency in riparian buffer (first-order decay model).

    eff = 1 - exp(-k × HRT)  where HRT = width × slope / Ks

    Args:
        width_m: Buffer width (m).
        slope: Groundwater flow gradient (dimensionless).
        saturated_conductivity: Hydraulic conductivity (m/day).

    Returns:
        N removal efficiency (0–1).
    """
    if saturated_conductivity <= 0.0:
        return 0.0
    var hrt = width_m * slope / saturated_conductivity
    var k_removal = 0.1  # typical first-order N removal rate (day⁻¹)
    var eff = 1.0 - exp(-k_removal * hrt)
    if eff < 0.0:
        return 0.0
    return eff


def ecohydrological_stress(
    soil_moisture: Float64, field_capacity: Float64, wilting_point: Float64
) -> Float64:
    """Water stress factor for GPP reduction (linear model).

    β = (θ - θ_wp) / (θ_fc - θ_wp)  clamped 0–1

    Args:
        soil_moisture: Soil water content (m³/m³).
        field_capacity: Field capacity.
        wilting_point: Wilting point.

    Returns:
        Water availability factor β (1 = no stress, 0 = full stress).
    """
    var range = field_capacity - wilting_point
    if range <= 0.0:
        return 0.0
    var beta = (soil_moisture - wilting_point) / range
    if beta < 0.0:
        return 0.0
    if beta > 1.0:
        return 1.0
    return beta


def flood_pulse_benefit(
    flood_duration_days: Float64, nutrient_input: Float64, productivity_rate: Float64
) -> Float64:
    """Floodplain productivity bonus from flood pulse (Junk et al.).

    benefit = duration × nutrient_input × productivity_rate

    Args:
        flood_duration_days: Days of inundation.
        nutrient_input: Nutrient loading from flood (g N/m²).
        productivity_rate: Biomass production per nutrient (g DW/g N).

    Returns:
        Additional floodplain biomass (g DW/m²).
    """
    return flood_duration_days * nutrient_input * productivity_rate / 365.0


def water_table_depth_et(
    water_table_m: Float64, extinction_depth_m: Float64, pet: Float64
) -> Float64:
    """ET from shallow groundwater, declining with depth (linear extinction).

    ET_gw = PET × max(0, 1 - WT / extinction_depth)

    Args:
        water_table_m: Water table depth below surface (m).
        extinction_depth_m: Depth below which groundwater contribution = 0 (m).
        pet: Potential evapotranspiration (mm/day).

    Returns:
        Groundwater-sourced ET (mm/day).
    """
    if extinction_depth_m <= 0.0:
        return 0.0
    var factor = 1.0 - water_table_m / extinction_depth_m
    if factor < 0.0:
        return 0.0
    return pet * factor


def catchment_runoff_ratio(
    annual_runoff_mm: Float64, annual_precipitation_mm: Float64
) -> Float64:
    """Annual runoff coefficient (Q/P).

    Args:
        annual_runoff_mm: Mean annual streamflow (mm/yr).
        annual_precipitation_mm: Mean annual precipitation (mm/yr).

    Returns:
        Runoff ratio (0–1).
    """
    if annual_precipitation_mm <= 0.0:
        return 0.0
    return annual_runoff_mm / annual_precipitation_mm
