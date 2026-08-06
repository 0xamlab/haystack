"""
ecophysiology.mojo — Environmental physiology of organisms. Zero Python imports.

Public API:
  metabolic_rate_kleiber       — BMR = 70 * mass^0.75
  thermal_conductance          — C = heat_loss / (T_body - T_air)
  q10_temperature_coefficient  — Q10 = (R2/R1)^(10/(T2-T1))
  evaporative_water_loss       — EWL from vapor pressure gradient
  aerobic_scope                — scope = max_MR - resting_MR
  hypoxia_tolerance            — critical O2 (Pcrit)
  osmoregulation_cost          — energetic cost of ion regulation
  heart_rate_fick              — CO = VO2 / (O2_art - O2_ven)
  oxygen_consumption_rate      — MO2 from respirometry
  field_metabolic_rate         — FMR from mass and DLW method
"""
from std.math import sqrt, exp, log, pow


def metabolic_rate_kleiber(mass_kg: Float64) -> Float64:
    """Kleiber's law: BMR = 70 · M^0.75.

    Args:
        mass_kg: Body mass (kg).

    Returns:
        Basal metabolic rate (kcal/day).
    """
    if mass_kg <= 0.0:
        return 0.0
    return 70.0 * pow(mass_kg, 0.75)


def thermal_conductance(
    heat_loss: Float64, t_body: Float64, t_ambient: Float64
) -> Float64:
    """Thermal conductance of an animal.

    C = heat_loss / (T_body - T_ambient)

    Args:
        heat_loss: Rate of heat loss (W).
        t_body: Core body temperature (°C).
        t_ambient: Ambient temperature (°C).

    Returns:
        Thermal conductance (W/°C).
    """
    var dt = t_body - t_ambient
    if dt == 0.0:
        return 0.0
    return heat_loss / dt


def q10_temperature_coefficient(
    rate1: Float64, rate2: Float64, t1: Float64, t2: Float64
) -> Float64:
    """Q10 temperature coefficient: metabolic sensitivity to temperature.

    Q10 = (R2/R1)^(10/(T2-T1))

    Args:
        rate1: Metabolic rate at temperature T1.
        rate2: Metabolic rate at temperature T2.
        t1: Temperature 1 (°C).
        t2: Temperature 2 (°C, > T1).

    Returns:
        Q10 coefficient (typically 2–3 for biological processes).
    """
    if rate1 <= 0.0 or rate2 <= 0.0 or t2 == t1:
        return 0.0
    return pow(rate2 / rate1, 10.0 / (t2 - t1))


def evaporative_water_loss(
    surface_area: Float64, permeability: Float64,
    vpd: Float64
) -> Float64:
    """Cutaneous evaporative water loss.

    EWL = A · P_skin · VPD

    Args:
        surface_area: Body surface area (cm²).
        permeability: Skin permeability coefficient (g/cm²/h/kPa).
        vpd: Vapour pressure deficit (kPa).

    Returns:
        Evaporative water loss (g/h).
    """
    if surface_area < 0.0 or permeability < 0.0 or vpd < 0.0:
        return 0.0
    return surface_area * permeability * vpd


def aerobic_scope(
    max_metabolic_rate: Float64, resting_metabolic_rate: Float64
) -> Float64:
    """Aerobic scope: capacity above resting metabolism.

    AS = MMR - RMR

    Args:
        max_metabolic_rate: Maximum metabolic rate (mg O2/kg/h).
        resting_metabolic_rate: Resting metabolic rate (mg O2/kg/h).

    Returns:
        Aerobic scope (mg O2/kg/h).
    """
    var scope = max_metabolic_rate - resting_metabolic_rate
    if scope < 0.0:
        return 0.0
    return scope


def hypoxia_tolerance(
    resting_mr: Float64, mass_specific_o2: Float64
) -> Float64:
    """Critical oxygen partial pressure (Pcrit) estimate.

    Simplified: Pcrit ≈ RMR / (mass-specific O2 uptake coefficient)

    Args:
        resting_mr: Resting metabolic rate (μmol O2/h).
        mass_specific_o2: Oxygen uptake capacity coefficient.

    Returns:
        Critical PO2 (mmHg or kPa, dimensionally consistent).
    """
    if mass_specific_o2 <= 0.0:
        return 0.0
    return resting_mr / mass_specific_o2


def osmoregulation_cost(
    osmotic_gradient: Float64, membrane_permeability: Float64, body_mass: Float64
) -> Float64:
    """Energetic cost of osmoregulation.

    Cost ∝ ΔOsm · P · mass  (simplified proportionality model)

    Args:
        osmotic_gradient: Difference in osmotic concentration (mOsm).
        membrane_permeability: Water permeability (mL/h/mOsm).
        body_mass: Body mass (kg).

    Returns:
        Relative osmoregulatory cost (mW).
    """
    if osmotic_gradient < 0.0 or membrane_permeability < 0.0:
        return 0.0
    return osmotic_gradient * membrane_permeability * body_mass


def heart_rate_fick(
    vo2: Float64, o2_arterial: Float64, o2_venous: Float64
) -> Float64:
    """Cardiac output from Fick principle: CO = VO2 / (CaO2 - CvO2).

    Args:
        vo2: Oxygen consumption rate (mL O2/min).
        o2_arterial: Arterial O2 content (mL O2/100mL blood).
        o2_venous: Venous O2 content (mL O2/100mL blood).

    Returns:
        Cardiac output (L/min).
    """
    var diff = o2_arterial - o2_venous
    if diff <= 0.0:
        return 0.0
    return vo2 / (diff * 10.0)  # × 10 for mL → L and 100mL → mL conversion


def oxygen_consumption_rate(
    delta_o2_ppm: Float64, flow_rate_l_h: Float64, mass_kg: Float64
) -> Float64:
    """Mass-specific oxygen consumption from respirometry.

    MO2 = (ΔO2 × V_flow) / mass

    Args:
        delta_o2_ppm: Change in O2 concentration through chamber (ppm).
        flow_rate_l_h: Flow rate through respirometry chamber (L/h).
        mass_kg: Animal mass (kg).

    Returns:
        Mass-specific MO2 (mL O2/h/kg).
    """
    if mass_kg <= 0.0:
        return 0.0
    # Convert ppm (μL/L) × L/h → mL/h
    return (delta_o2_ppm * 1e-3) * flow_rate_l_h / mass_kg


def field_metabolic_rate(mass_kg: Float64, taxon_a: Float64, taxon_b: Float64) -> Float64:
    """Field metabolic rate from doubly-labelled water allometric equation.

    FMR = a · M^b  (where a and b are taxon-specific)

    Args:
        mass_kg: Body mass (kg).
        taxon_a: Allometric intercept (taxon-specific, e.g. 10.9 for eutherian mammals).
        taxon_b: Allometric slope (taxon-specific, e.g. 0.734).

    Returns:
        FMR (kJ/day).
    """
    if mass_kg <= 0.0 or taxon_a <= 0.0:
        return 0.0
    return taxon_a * pow(mass_kg, taxon_b)
