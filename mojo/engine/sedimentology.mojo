"""
sedimentology.mojo — Sediment transport and deposition calculations. Zero Python imports.

Public API:
  settling_velocity_stokes      — terminal fall velocity of a grain
  shields_parameter             — dimensionless bed shear stress
  critical_shear_stress         — threshold for sediment motion
  bedload_transport             — Einstein bedload equation
  suspended_load_rouse          — Rouse concentration profile
  grain_size_phi                — phi scale from mm
  phi_to_mm                     — grain size from phi scale
  sorting_coefficient           — Folk and Ward sorting statistic
  skewness_folk_ward            — grain size distribution skewness
  sediment_budget               — supply minus loss
"""
from std.math import sqrt, log, exp, pow


def settling_velocity_stokes(
    grain_diameter_m: Float64, grain_density: Float64,
    fluid_density: Float64, kinematic_viscosity: Float64
) -> Float64:
    """Stokes settling velocity for small grains.

    w_s = (ρ_s - ρ_f) · g · d² / (18 · ν · ρ_f)

    Args:
        grain_diameter_m: Grain diameter (m).
        grain_density: Grain density (kg/m³, ~2650 for quartz).
        fluid_density: Fluid density (kg/m³, ~1000 for water).
        kinematic_viscosity: Kinematic viscosity (m²/s, ~1e-6).

    Returns:
        Settling velocity (m/s).
    """
    var g = 9.81
    var denom = 18.0 * kinematic_viscosity * fluid_density
    if denom <= 0.0:
        return 0.0
    return (grain_density - fluid_density) * g * grain_diameter_m * grain_diameter_m / denom


def shields_parameter(
    bed_shear_stress: Float64, grain_diameter_m: Float64,
    grain_density: Float64, fluid_density: Float64
) -> Float64:
    """Shields parameter (dimensionless shear stress).

    θ = τ / ((ρ_s - ρ_f) · g · d)

    Args:
        bed_shear_stress: Bed shear stress τ (Pa).
        grain_diameter_m: Median grain diameter (m).
        grain_density: Sediment density (kg/m³).
        fluid_density: Fluid density (kg/m³).

    Returns:
        Shields parameter θ.
    """
    var g = 9.81
    var denom = (grain_density - fluid_density) * g * grain_diameter_m
    if denom <= 0.0:
        return 0.0
    return bed_shear_stress / denom


def critical_shear_stress(
    grain_diameter_m: Float64, grain_density: Float64, fluid_density: Float64
) -> Float64:
    """Critical bed shear stress for incipient motion (Shields θ_c ≈ 0.047).

    τ_c = 0.047 · (ρ_s - ρ_f) · g · d

    Args:
        grain_diameter_m: Grain diameter (m).
        grain_density: Sediment density (kg/m³).
        fluid_density: Fluid density (kg/m³).

    Returns:
        Critical shear stress (Pa).
    """
    var g = 9.81
    return 0.047 * (grain_density - fluid_density) * g * grain_diameter_m


def bedload_transport(
    shields: Float64, critical_shields: Float64,
    grain_diameter_m: Float64, fluid_density: Float64, grain_density: Float64
) -> Float64:
    """Bedload transport rate (Meyer-Peter & Müller).

    q_b* = 8 · (θ - θ_c)^1.5

    Args:
        shields: Shields parameter θ.
        critical_shields: Critical Shields parameter θ_c (≈0.047).
        grain_diameter_m: Grain diameter (m).
        fluid_density: Fluid density (kg/m³).
        grain_density: Sediment density (kg/m³).

    Returns:
        Dimensionless bedload transport q_b*.
    """
    var excess = shields - critical_shields
    if excess <= 0.0:
        return 0.0
    return 8.0 * pow(excess, 1.5)


def suspended_load_rouse(
    reference_conc: Float64, reference_height: Float64,
    height: Float64, rouse_number: Float64, depth: Float64
) -> Float64:
    """Rouse suspended sediment concentration profile.

    C/Ca = ((a(H-z)) / (z(H-a)))^Z

    Args:
        reference_conc: Reference concentration Ca at height a (kg/m³).
        reference_height: Reference height a (m).
        height: Height z above bed (m).
        rouse_number: Rouse number Z = w_s / (κ · u*).
        depth: Total flow depth H (m).

    Returns:
        Suspended sediment concentration at height z (kg/m³).
    """
    if height <= 0.0 or height >= depth:
        return 0.0
    var ratio = (reference_height * (depth - height)) / (height * (depth - reference_height))
    if ratio <= 0.0:
        return 0.0
    return reference_conc * pow(ratio, rouse_number)


def grain_size_phi(diameter_mm: Float64) -> Float64:
    """Convert grain diameter to phi scale.

    φ = -log2(d_mm)

    Args:
        diameter_mm: Grain diameter (mm).

    Returns:
        Grain size in phi units.
    """
    if diameter_mm <= 0.0:
        return 0.0
    return -log(diameter_mm) / log(2.0)


def phi_to_mm(phi: Float64) -> Float64:
    """Convert phi scale to grain diameter.

    d_mm = 2^(-φ)

    Args:
        phi: Grain size in phi units.

    Returns:
        Diameter (mm).
    """
    return pow(2.0, -phi)


def sorting_coefficient(
    phi_84: Float64, phi_16: Float64, phi_95: Float64, phi_5: Float64
) -> Float64:
    """Folk and Ward inclusive graphic standard deviation (sorting).

    σI = (φ84 - φ16)/4 + (φ95 - φ5)/6.6

    Args:
        phi_84: Phi value at 84th percentile.
        phi_16: Phi value at 16th percentile.
        phi_95: Phi value at 95th percentile.
        phi_5: Phi value at 5th percentile.

    Returns:
        Sorting σI (phi; <0.35 = well sorted, >2 = very poorly sorted).
    """
    return (phi_84 - phi_16) / 4.0 + (phi_95 - phi_5) / 6.6


def skewness_folk_ward(
    phi_84: Float64, phi_16: Float64, phi_50: Float64,
    phi_95: Float64, phi_5: Float64
) -> Float64:
    """Folk and Ward inclusive graphic skewness.

    SkI = (φ16+φ84-2φ50)/(2(φ84-φ16)) + (φ5+φ95-2φ50)/(2(φ95-φ5))

    Args:
        phi_84: 84th percentile.
        phi_16: 16th percentile.
        phi_50: Median (50th percentile).
        phi_95: 95th percentile.
        phi_5: 5th percentile.

    Returns:
        Skewness SkI.
    """
    var d1 = phi_84 - phi_16
    var d2 = phi_95 - phi_5
    if d1 == 0.0 or d2 == 0.0:
        return 0.0
    return (phi_16 + phi_84 - 2.0 * phi_50) / (2.0 * d1) + (phi_5 + phi_95 - 2.0 * phi_50) / (2.0 * d2)


def sediment_budget(
    supply_rate: Float64, deposition_rate: Float64, erosion_rate: Float64
) -> Float64:
    """Sediment budget: net accumulation or loss.

    budget = supply - deposition + erosion  (all in m³/yr or t/yr)

    Args:
        supply_rate: Sediment input rate.
        deposition_rate: Deposition loss rate.
        erosion_rate: Erosion gain rate.

    Returns:
        Net budget (positive = accumulating).
    """
    return supply_rate - deposition_rate + erosion_rate
