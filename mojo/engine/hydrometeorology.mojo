"""
hydrometeorology.mojo — Precipitation and hydrological weather calculations.
Zero Python imports.

Public API:
  runoff_curve_number           — SCS-CN direct runoff
  rational_method_peak_flow     — Q = CiA
  time_of_concentration         — Kirpich formula
  green_ampt_infiltration       — cumulative infiltration
  palmer_drought_index          — PDSI from water balance
  actual_evapotranspiration     — Budyko-type AET
  snow_water_equivalent         — SWE from depth and density
  rain_intensity_from_depth     — mm/h from accumulation
  antecedent_moisture_condition — AMC class threshold
  flood_frequency_factor        — Gumbel EV-I frequency factor
"""
from std.math import log, sqrt, exp


fn runoff_curve_number(
    rainfall_mm: Float64, cn: Float64
) -> Float64:
    """SCS Curve Number direct runoff depth.

    Q = (P - Ia)² / (P - Ia + S)  where Ia = 0.2·S, S = 25400/CN - 254

    Args:
        rainfall_mm: Total storm rainfall P (mm).
        cn: Curve Number (0–100).

    Returns:
        Direct runoff depth Q (mm).
    """
    if cn <= 0.0 or cn > 100.0:
        return 0.0
    var s = 25400.0 / cn - 254.0
    var ia = 0.2 * s
    if rainfall_mm <= ia:
        return 0.0
    var numerator = (rainfall_mm - ia) * (rainfall_mm - ia)
    var denominator = rainfall_mm - ia + s
    if denominator <= 0.0:
        return 0.0
    return numerator / denominator


fn rational_method_peak_flow(
    runoff_coeff: Float64, intensity_mm_per_h: Float64, area_ha: Float64
) -> Float64:
    """Peak flow from rational method: Q = C·i·A / 360.

    Args:
        runoff_coeff: Rational method coefficient C (0–1).
        intensity_mm_per_h: Design rainfall intensity (mm/h).
        area_ha: Catchment area (ha).

    Returns:
        Peak discharge (m³/s).
    """
    return runoff_coeff * intensity_mm_per_h * area_ha / 360.0


fn time_of_concentration(
    length_m: Float64, slope: Float64
) -> Float64:
    """Kirpich time of concentration.

    Tc = 0.0195 · L^0.77 / S^0.385  (minutes)

    Args:
        length_m: Hydraulic length of watershed (m).
        slope: Average watershed slope (m/m).

    Returns:
        Time of concentration (min).
    """
    if slope <= 0.0:
        return 0.0
    return 0.0195 * (length_m ** 0.77) / (slope ** 0.385)


fn green_ampt_infiltration(
    saturated_conductivity: Float64, suction_head: Float64,
    delta_theta: Float64, time_h: Float64
) -> Float64:
    """Green-Ampt cumulative infiltration (iterative approximation).

    F ≈ Ks·t + ψ·Δθ·ln(1 + F/(ψ·Δθ))  — linearised first-order approx.

    Args:
        saturated_conductivity: Ks (mm/h).
        suction_head: Matric suction at wetting front ψ (mm).
        delta_theta: Soil moisture deficit Δθ (dimensionless).
        time_h: Elapsed time (h).

    Returns:
        Cumulative infiltration F (mm, linearised estimate).
    """
    return saturated_conductivity * time_h + suction_head * delta_theta * log(1.0 + saturated_conductivity * time_h / (suction_head * delta_theta + 1e-9))


fn palmer_drought_index(
    precip: Float64, pet: Float64, awc: Float64
) -> Float64:
    """Simplified Palmer Drought Severity Index water balance component.

    Z = (precip - PET) / AWC  (climatological departure)

    Args:
        precip: Monthly precipitation (mm).
        pet: Potential evapotranspiration (mm).
        awc: Available water capacity of soil (mm).

    Returns:
        Z-index (negative = drought, positive = moist).
    """
    if awc <= 0.0:
        return 0.0
    return (precip - pet) / awc


fn actual_evapotranspiration(
    pet: Float64, precipitation: Float64
) -> Float64:
    """Budyko-type actual evapotranspiration.

    AET = min(PET, P)  (simple water-limit)

    Args:
        pet: Potential evapotranspiration (mm/yr).
        precipitation: Mean annual precipitation (mm/yr).

    Returns:
        Actual evapotranspiration (mm/yr).
    """
    if pet < precipitation:
        return pet
    return precipitation


fn snow_water_equivalent(
    snow_depth_m: Float64, snow_density_kg_m3: Float64
) -> Float64:
    """Snow water equivalent from depth and density.

    SWE = depth × density / 1000  (mm)

    Args:
        snow_depth_m: Snow depth (m).
        snow_density_kg_m3: Snow bulk density (kg/m³, fresh ~100, old ~400).

    Returns:
        SWE (mm).
    """
    return snow_depth_m * snow_density_kg_m3


fn rain_intensity_from_depth(
    depth_mm: Float64, duration_h: Float64
) -> Float64:
    """Average rainfall intensity from accumulation over a period.

    Args:
        depth_mm: Total rainfall depth (mm).
        duration_h: Storm duration (h).

    Returns:
        Average intensity (mm/h).
    """
    if duration_h <= 0.0:
        return 0.0
    return depth_mm / duration_h


fn antecedent_moisture_condition(
    five_day_precip_mm: Float64, is_growing_season: Float64
) -> Float64:
    """AMC class from 5-day antecedent precipitation.

    Returns class I (dry=1), II (normal=2), III (wet=3).
    Growing season thresholds: <35 mm = I, 35-53 mm = II, >53 mm = III.

    Args:
        five_day_precip_mm: 5-day antecedent precipitation (mm).
        is_growing_season: 1.0 if growing season, 0.0 if dormant.

    Returns:
        AMC class (1, 2, or 3).
    """
    var dry_thresh = 12.5
    var wet_thresh = 27.5
    if is_growing_season > 0.5:
        dry_thresh = 35.0
        wet_thresh = 53.0
    if five_day_precip_mm < dry_thresh:
        return 1.0
    if five_day_precip_mm <= wet_thresh:
        return 2.0
    return 3.0


fn flood_frequency_factor(
    return_period_yr: Float64
) -> Float64:
    """Gumbel (EV-I) frequency factor K for flood frequency analysis.

    K = -sqrt(6)/π · (0.5772 + ln(ln(T/(T-1))))

    Args:
        return_period_yr: Return period T (years).

    Returns:
        Frequency factor K.
    """
    if return_period_yr <= 1.0:
        return 0.0
    var reduced_variate = -log(-log(1.0 - 1.0 / return_period_yr))
    return (reduced_variate - 0.5772) / 1.2825
