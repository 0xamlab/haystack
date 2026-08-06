"""
speleology.mojo — Cave science and karst calculations. Zero Python imports.

Public API:
  cave_passage_volume           — elliptical cross-section estimate
  stalactite_growth_rate        — from drip rate and calcite saturation
  drip_water_calcite_saturation — saturation index SI
  cave_climate_temperature      — annual mean at depth
  turbulent_flow_cave           — Reynolds number in passage
  karst_spring_discharge        — from tank model
  cave_radio_signal_depth       — penetration from surface
  dissolution_rate_limestone    — from saturation index
  age_uranium_series            — 230Th/234U age
  radon_in_cave_air             — equilibrium radon concentration
"""
from std.math import log, exp, sqrt, pow


def cave_passage_volume(
    length_m: Float64, width_m: Float64, height_m: Float64
) -> Float64:
    """Cave passage volume approximated as elliptical cross section.

    V = π/4 × W × H × L

    Args:
        length_m: Passage length (m).
        width_m: Passage width (m).
        height_m: Passage height (m).

    Returns:
        Volume (m³).
    """
    var pi = 3.141592653589793
    return pi / 4.0 * width_m * height_m * length_m


def stalactite_growth_rate(
    drip_rate_ml_per_min: Float64, calcite_per_ml_mg: Float64, density_g_cm3: Float64
) -> Float64:
    """Linear stalactite growth rate from deposition.

    growth = (drip_rate × calcite_per_drop) / (ρ × π × r²)  approximate mm/yr

    Args:
        drip_rate_ml_per_min: Drip water flow (mL/min).
        calcite_per_ml_mg: Mass of calcite deposited per mL (mg/mL).
        density_g_cm3: Calcite density (g/cm³, ~2.71).

    Returns:
        Growth rate (mm/yr, simplified assuming 1 mm² tip area).
    """
    var mg_per_yr = drip_rate_ml_per_min * calcite_per_ml_mg * 525960.0  # min/yr
    var cm3_per_yr = mg_per_yr / (density_g_cm3 * 1000.0)
    return cm3_per_yr * 10.0  # cm3 to mm, assuming 1 cm² area


def drip_water_calcite_saturation(
    ca_mmol_l: Float64, co3_mmol_l: Float64, ksp: Float64
) -> Float64:
    """Saturation index SI = log10([Ca²⁺][CO₃²⁻] / Ksp).

    Args:
        ca_mmol_l: Calcium concentration (mmol/L).
        co3_mmol_l: Carbonate ion concentration (mmol/L).
        ksp: Solubility product of calcite (mol²/L², ~3.3×10⁻⁹).

    Returns:
        Saturation index SI (>0 = supersaturated → deposition).
    """
    if ksp <= 0.0:
        return 0.0
    var ip = ca_mmol_l * 1e-3 * co3_mmol_l * 1e-3
    if ip <= 0.0:
        return 0.0
    return log(ip / ksp) / log(10.0)


def cave_climate_temperature(
    surface_maat: Float64, depth_m: Float64, lapse_rate: Float64
) -> Float64:
    """Cave air temperature ≈ surface MAAT (adjusted for deep caves).

    T_cave = MAAT + depth × lapse_rate

    Args:
        surface_maat: Surface mean annual air temperature (°C).
        depth_m: Cave depth below surface (m).
        lapse_rate: Geothermal lapse rate (°C/m, typical 0.02–0.03).

    Returns:
        Cave temperature (°C).
    """
    return surface_maat + depth_m * lapse_rate


def turbulent_flow_cave(
    velocity: Float64, hydraulic_diameter: Float64, kinematic_viscosity: Float64
) -> Float64:
    """Reynolds number for cave passage flow.

    Re = v × Dh / ν

    Args:
        velocity: Mean flow velocity (m/s).
        hydraulic_diameter: Hydraulic diameter of passage (m).
        kinematic_viscosity: Kinematic viscosity of water (m²/s, ~1e-6).

    Returns:
        Reynolds number (>2000 = turbulent flow).
    """
    if kinematic_viscosity <= 0.0:
        return 0.0
    return velocity * hydraulic_diameter / kinematic_viscosity


def karst_spring_discharge(
    storage_m3: Float64, recession_coefficient: Float64
) -> Float64:
    """Karst spring discharge by exponential recession.

    Q = Q0 × exp(-α·t)  — returns Q for normalised t=1 (rate per day)

    Args:
        storage_m3: Initial groundwater storage (m³).
        recession_coefficient: Recession constant α (day⁻¹).

    Returns:
        Spring discharge (m³/day).
    """
    return storage_m3 * recession_coefficient


def cave_radio_signal_depth(
    frequency_hz: Float64, conductivity: Float64
) -> Float64:
    """Radio signal skin depth in rock: δ = sqrt(2 / (ω·μ·σ)).

    Args:
        frequency_hz: Radio frequency (Hz).
        conductivity: Rock electrical conductivity (S/m, ~0.01 for limestone).

    Returns:
        Skin depth (m; useful range for cave radio communication).
    """
    var mu0 = 1.2566e-6  # permeability of free space
    var omega = 2.0 * 3.141592653589793 * frequency_hz
    var denom = omega * mu0 * conductivity
    if denom <= 0.0:
        return 0.0
    return sqrt(2.0 / denom)


def dissolution_rate_limestone(
    saturation_index: Float64, rate_constant: Float64
) -> Float64:
    """Limestone dissolution rate from saturation state (PWP model simplified).

    r = k × (1 - Ω)  where Ω = 10^SI

    Args:
        saturation_index: SI (negative = undersaturated).
        rate_constant: Dissolution rate constant (mol/m²/s, ~10⁻⁷).

    Returns:
        Dissolution rate (mol/m²/s; 0 if already saturated).
    """
    var omega = pow(10.0, saturation_index)
    var undersaturation = 1.0 - omega
    if undersaturation <= 0.0:
        return 0.0
    return rate_constant * undersaturation


def age_uranium_series(
    activity_ratio_230_234: Float64
) -> Float64:
    """Simplified 230Th/234U age for speleothems (secular equilibrium model).

    Assumes initial 230Th = 0; age ≈ -ln(1 - ratio) / λ230

    Args:
        activity_ratio_230_234: Measured (230Th/234U) activity ratio (0–1).

    Returns:
        Approximate age (years).
    """
    if activity_ratio_230_234 >= 1.0 or activity_ratio_230_234 <= 0.0:
        return 0.0
    var lambda230 = 9.158e-6  # per year (half-life 75,380 yr)
    return -log(1.0 - activity_ratio_230_234) / lambda230


def radon_in_cave_air(
    radon_flux: Float64, ventilation_rate: Float64, decay_constant: Float64
) -> Float64:
    """Equilibrium radon concentration in cave air.

    Rn_eq = flux / (ventilation + λ_Rn)

    Args:
        radon_flux: Rn emanation from walls (Bq/m³/s).
        ventilation_rate: Cave air exchange rate (per second).
        decay_constant: Rn radioactive decay constant (per second, 2.1×10⁻⁶).

    Returns:
        Equilibrium Rn concentration (Bq/m³).
    """
    var removal = ventilation_rate + decay_constant
    if removal <= 0.0:
        return 0.0
    return radon_flux / removal
