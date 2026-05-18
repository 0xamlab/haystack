"""
toxicokinetics.mojo — Toxicant absorption, distribution, metabolism, elimination.
Zero Python imports.

Public API:
  internal_dose                — dose × bioavailability
  peak_plasma_concentration    — Cmax from dose and Vd
  time_to_peak                 — Tmax for first-order absorption
  plasma_auc                   — trapezoidal AUC from two points
  apparent_volume_distribution — Vd = dose / C0
  elimination_half_life        — t½ = 0.693 / ke
  systemic_clearance           — CL = ke × Vd
  bioconcentration_factor      — BCF from exposure
  toxic_equivalency_factor     — TEF-weighted TEQ
  margin_of_exposure           — MOE = NOAEL / human_dose
"""
from std.math import log, exp


fn internal_dose(
    external_dose: Float64, bioavailability: Float64
) -> Float64:
    """Internal (absorbed) dose: ID = D_ext × F.

    Args:
        external_dose: Exposure dose (mg/kg).
        bioavailability: Absorption fraction F (0–1).

    Returns:
        Internal dose (mg/kg).
    """
    return external_dose * bioavailability


fn peak_plasma_concentration(
    dose_mg: Float64, volume_of_distribution_l: Float64
) -> Float64:
    """Theoretical peak plasma concentration at t=0 (IV bolus).

    C0 = dose / Vd

    Args:
        dose_mg: Administered dose (mg).
        volume_of_distribution_l: Volume of distribution (L).

    Returns:
        C0 (mg/L).
    """
    if volume_of_distribution_l <= 0.0:
        return 0.0
    return dose_mg / volume_of_distribution_l


fn time_to_peak(
    absorption_rate: Float64, elimination_rate: Float64
) -> Float64:
    """Time to peak plasma concentration for one-compartment oral model.

    Tmax = ln(ka/ke) / (ka - ke)

    Args:
        absorption_rate: First-order absorption rate constant ka (h⁻¹).
        elimination_rate: First-order elimination rate constant ke (h⁻¹).

    Returns:
        Tmax (h).
    """
    if absorption_rate <= elimination_rate or elimination_rate <= 0.0:
        return 0.0
    return log(absorption_rate / elimination_rate) / (absorption_rate - elimination_rate)


fn plasma_auc(
    c1: Float64, c2: Float64, t1: Float64, t2: Float64
) -> Float64:
    """Trapezoidal AUC between two time points.

    AUC = (C1 + C2) / 2 × (t2 - t1)

    Args:
        c1: Plasma concentration at t1 (mg/L).
        c2: Plasma concentration at t2 (mg/L).
        t1: First time point (h).
        t2: Second time point (h).

    Returns:
        AUC for this interval (mg·h/L).
    """
    if t2 <= t1:
        return 0.0
    return (c1 + c2) / 2.0 * (t2 - t1)


fn apparent_volume_distribution(
    dose_mg: Float64, c0_mg_per_l: Float64
) -> Float64:
    """Apparent volume of distribution: Vd = dose / C0.

    Args:
        dose_mg: IV dose (mg).
        c0_mg_per_l: Extrapolated t=0 concentration (mg/L).

    Returns:
        Vd (L).
    """
    if c0_mg_per_l <= 0.0:
        return 0.0
    return dose_mg / c0_mg_per_l


fn elimination_half_life(elimination_rate: Float64) -> Float64:
    """Elimination half-life: t½ = ln2 / ke.

    Args:
        elimination_rate: First-order elimination rate ke (h⁻¹).

    Returns:
        Half-life (h).
    """
    if elimination_rate <= 0.0:
        return 0.0
    return log(2.0) / elimination_rate


fn systemic_clearance(
    elimination_rate: Float64, volume_of_distribution: Float64
) -> Float64:
    """Total systemic clearance: CL = ke × Vd.

    Args:
        elimination_rate: ke (h⁻¹).
        volume_of_distribution: Vd (L).

    Returns:
        Clearance (L/h).
    """
    return elimination_rate * volume_of_distribution


fn bioconcentration_factor(
    tissue_conc: Float64, water_conc: Float64
) -> Float64:
    """Bioconcentration factor: BCF = C_tissue / C_water.

    Args:
        tissue_conc: Toxicant in organism tissue (μg/kg).
        water_conc: Toxicant in ambient water (μg/L).

    Returns:
        BCF (L/kg).
    """
    if water_conc <= 0.0:
        return 0.0
    return tissue_conc / water_conc


fn toxic_equivalency_factor(
    congener_conc: Float64, tef: Float64
) -> Float64:
    """Toxic equivalency: TEQ = concentration × TEF.

    Args:
        congener_conc: Congener concentration (pg/g).
        tef: Toxic equivalency factor relative to TCDD (0–1).

    Returns:
        TEQ contribution (pg TEQ/g).
    """
    return congener_conc * tef


fn margin_of_exposure(
    noael_mg_per_kg: Float64, human_dose_mg_per_kg: Float64
) -> Float64:
    """Margin of exposure: MOE = NOAEL / human exposure.

    Args:
        noael_mg_per_kg: No-observed-adverse-effect level (mg/kg/day).
        human_dose_mg_per_kg: Human daily dose estimate (mg/kg/day).

    Returns:
        MOE (dimensionless; MOE > 10 000 is generally acceptable).
    """
    if human_dose_mg_per_kg <= 0.0:
        return 0.0
    return noael_mg_per_kg / human_dose_mg_per_kg
