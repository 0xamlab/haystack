"""
limnology.mojo — Freshwater lake science calculations. Zero Python imports.

Public API:
  lake_volume_ellipsoid        — V = (4/3)π·a·b·h
  hydraulic_retention_time     — HRT = V / Q
  thermal_stratification_index — TSI from surface vs. bottom temperature
  secchi_depth_estimate        — Secchi depth from chlorophyll-a
  trophic_state_index          — Carlson TSI from Secchi depth
  phosphorus_loading            — P-load = sum(Ci*Qi)
  oxygen_saturation            — DO_sat at given T and salinity
  attenuation_coefficient      — Kd from Secchi depth
  lake_flushing_rate           — FR = Q / V (yr⁻¹)
  nitrogen_fixation_rate       — modeled N-fix from temperature
"""
from std.math import exp, log, sqrt


def lake_volume_ellipsoid(
    semi_axis_a: Float64, semi_axis_b: Float64, mean_depth: Float64
) -> Float64:
    """Volume of an ellipsoidal lake basin.

    Args:
        semi_axis_a: Semi-major axis of lake surface (m).
        semi_axis_b: Semi-minor axis of lake surface (m).
        mean_depth: Mean lake depth (m).

    Returns:
        Lake volume (m³).
    """
    if semi_axis_a <= 0.0 or semi_axis_b <= 0.0 or mean_depth <= 0.0:
        return 0.0
    var pi = 3.141592653589793
    return (4.0 / 3.0) * pi * semi_axis_a * semi_axis_b * mean_depth


def hydraulic_retention_time(volume: Float64, outflow: Float64) -> Float64:
    """Hydraulic retention time: HRT = V / Q.

    Args:
        volume: Lake volume (m³).
        outflow: Volumetric outflow rate (m³/day).

    Returns:
        Retention time (days).
    """
    if outflow <= 0.0:
        return 0.0
    return volume / outflow


def thermal_stratification_index(
    surface_temp: Float64, bottom_temp: Float64, depth: Float64
) -> Float64:
    """Thermal stratification index: temperature gradient per meter.

    Args:
        surface_temp: Epilimnion temperature (°C).
        bottom_temp: Hypolimnion temperature (°C).
        depth: Total depth (m).

    Returns:
        Temperature gradient (°C/m).
    """
    if depth <= 0.0:
        return 0.0
    return (surface_temp - bottom_temp) / depth


def secchi_depth_estimate(chlorophyll_a: Float64) -> Float64:
    """Secchi depth from chlorophyll-a concentration (Carlson 1977).

    Zs ≈ 4.6 / (0.025·chl + 0.177·√chl)

    Args:
        chlorophyll_a: Chlorophyll-a concentration (μg/L).

    Returns:
        Estimated Secchi depth (m).
    """
    if chlorophyll_a <= 0.0:
        return 10.0  # oligotrophic default
    var denom = 0.025 * chlorophyll_a + 0.177 * sqrt(chlorophyll_a)
    if denom <= 0.0:
        return 0.0
    return 4.6 / denom


def trophic_state_index(secchi_depth_m: Float64) -> Float64:
    """Carlson Trophic State Index from Secchi depth.

    TSI(SD) = 60 - 14.41·ln(SD)

    Args:
        secchi_depth_m: Secchi disk depth (m).

    Returns:
        TSI (0 = ultra-oligotrophic, 100+ = hyper-eutrophic).
    """
    if secchi_depth_m <= 0.0:
        return 100.0
    return 60.0 - 14.41 * log(secchi_depth_m)


def phosphorus_loading(
    concentration: Float64, flow_rate: Float64
) -> Float64:
    """Annual phosphorus loading from a single input.

    Args:
        concentration: Total phosphorus concentration (mg/L = g/m³).
        flow_rate: Annual flow volume (m³/yr).

    Returns:
        Annual P-load (kg/yr).
    """
    if concentration < 0.0 or flow_rate < 0.0:
        return 0.0
    return concentration * flow_rate / 1000.0  # mg/L * m³/yr → kg/yr


def oxygen_saturation(temperature: Float64, salinity: Float64) -> Float64:
    """Dissolved oxygen saturation at given temperature and salinity.

    Benson & Krause (1984) approximation.

    Args:
        temperature: Water temperature (°C).
        salinity: Salinity (g/kg, 0 for fresh water).

    Returns:
        DO saturation (mg/L).
    """
    var t = temperature
    var ln_do = (
        -139.34411
        + 157570.1 / (t + 273.15)
        - 66423080.0 / ((t + 273.15) ** 2.0)
        + 12438000000.0 / ((t + 273.15) ** 3.0)
        - 862194900000.0 / ((t + 273.15) ** 4.0)
        - salinity * (0.017674 - 10.754 / (t + 273.15) + 2140.7 / ((t + 273.15) ** 2.0))
    )
    return exp(ln_do)


def attenuation_coefficient(secchi_depth_m: Float64) -> Float64:
    """Diffuse vertical attenuation coefficient Kd from Secchi depth.

    Kd ≈ 1.7 / Zs  (Poole & Atkins 1929 approximation)

    Args:
        secchi_depth_m: Secchi depth (m).

    Returns:
        Kd (m⁻¹).
    """
    if secchi_depth_m <= 0.0:
        return 0.0
    return 1.7 / secchi_depth_m


def lake_flushing_rate(volume: Float64, annual_inflow: Float64) -> Float64:
    """Lake flushing rate (number of volume replacements per year).

    Args:
        volume: Lake volume (m³).
        annual_inflow: Annual water input (m³/yr).

    Returns:
        Flushing rate (yr⁻¹).
    """
    if volume <= 0.0:
        return 0.0
    return annual_inflow / volume


def nitrogen_fixation_rate(temperature: Float64, light: Float64) -> Float64:
    """Modeled N-fixation rate (simplified cyanobacteria model).

    Args:
        temperature: Water temperature (°C).
        light: Surface irradiance (μmol/m²/s PAR).

    Returns:
        N-fixation rate (μg N/L/day).
    """
    if temperature < 15.0 or light <= 0.0:
        return 0.0
    var t_factor = exp(0.07 * (temperature - 25.0))
    var l_factor = light / (light + 100.0)  # Michaelis-Menten light response
    return 10.0 * t_factor * l_factor
