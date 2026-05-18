"""
pharmacology.mojo — Drug action and dose-response calculations. Zero Python imports.

Public API:
  hill_equation                — E = Emax*C^n / (EC50^n + C^n)
  therapeutic_index            — TI = TD50 / ED50
  drug_bioavailability         — F = AUC_oral / AUC_iv * dose_ratio
  receptor_occupancy           — RO = [D] / (Kd + [D])
  drug_protein_binding         — free fraction = 1 - bound_fraction
  volume_of_distribution       — Vd = dose / C0
  clearance_from_halflife       — CL = 0.693 * Vd / t_half
  steady_state_concentration    — Css = bioavailability * dose / (CL * tau)
  loading_dose                 — LD = Vd * Css_target
  drug_interaction_index       — CI = Da/Dm_a + Db/Dm_b (combination index)
"""
from std.math import exp, log, pow


fn hill_equation(
    emax: Float64, concentration: Float64, ec50: Float64, hill_n: Float64
) -> Float64:
    """Hill (sigmoidal Emax) dose-response equation.

    E = Emax · C^n / (EC50^n + C^n)

    Args:
        emax: Maximum effect.
        concentration: Drug concentration (same units as EC50).
        ec50: Concentration producing 50% of Emax.
        hill_n: Hill coefficient (slope factor).

    Returns:
        Effect (same units as Emax).
    """
    if concentration <= 0.0 or ec50 <= 0.0:
        return 0.0
    var cn = pow(concentration, hill_n)
    var ec50n = pow(ec50, hill_n)
    return emax * cn / (ec50n + cn)


fn therapeutic_index(td50: Float64, ed50: Float64) -> Float64:
    """Therapeutic index: TI = TD50 / ED50.

    Args:
        td50: Dose producing toxicity in 50% of subjects.
        ed50: Dose producing therapeutic effect in 50% of subjects.

    Returns:
        Therapeutic index (dimensionless). Higher = safer.
    """
    if ed50 <= 0.0:
        return 0.0
    return td50 / ed50


fn drug_bioavailability(
    auc_oral: Float64, auc_iv: Float64, dose_oral: Float64, dose_iv: Float64
) -> Float64:
    """Absolute bioavailability from AUC comparison.

    F = (AUC_oral / AUC_iv) · (dose_iv / dose_oral)

    Args:
        auc_oral: Area under curve after oral dosing.
        auc_iv: Area under curve after IV dosing.
        dose_oral: Oral dose (mg).
        dose_iv: IV dose (mg).

    Returns:
        Bioavailability (0–1 fraction).
    """
    if auc_iv <= 0.0 or dose_oral <= 0.0:
        return 0.0
    return (auc_oral / auc_iv) * (dose_iv / dose_oral)


fn receptor_occupancy(drug_conc: Float64, kd: Float64) -> Float64:
    """Receptor occupancy fraction: RO = [D] / (Kd + [D]).

    Args:
        drug_conc: Drug concentration at receptor (nM).
        kd: Equilibrium dissociation constant (nM).

    Returns:
        Receptor occupancy fraction (0–1).
    """
    var denom = kd + drug_conc
    if denom <= 0.0:
        return 0.0
    return drug_conc / denom


fn drug_protein_binding(bound_fraction: Float64) -> Float64:
    """Free (unbound) fraction of drug in plasma.

    Args:
        bound_fraction: Fraction bound to plasma proteins (0–1).

    Returns:
        Free fraction (0–1).
    """
    if bound_fraction < 0.0 or bound_fraction > 1.0:
        return 1.0
    return 1.0 - bound_fraction


fn volume_of_distribution(dose: Float64, c_plasma_zero: Float64) -> Float64:
    """Apparent volume of distribution: Vd = Dose / C₀.

    Args:
        dose: Administered dose (mg).
        c_plasma_zero: Plasma concentration at t=0 extrapolated (mg/L).

    Returns:
        Volume of distribution (L).
    """
    if c_plasma_zero <= 0.0:
        return 0.0
    return dose / c_plasma_zero


fn clearance_from_halflife(volume_of_dist: Float64, half_life: Float64) -> Float64:
    """Drug clearance from half-life and Vd.

    CL = 0.693 · Vd / t½

    Args:
        volume_of_dist: Volume of distribution (L).
        half_life: Elimination half-life (h).

    Returns:
        Clearance (L/h).
    """
    if half_life <= 0.0:
        return 0.0
    return 0.693 * volume_of_dist / half_life


fn steady_state_concentration(
    bioavailability: Float64, dose: Float64, clearance: Float64, tau: Float64
) -> Float64:
    """Average steady-state plasma concentration.

    Css = F · dose / (CL · τ)

    Args:
        bioavailability: Bioavailability fraction (0–1).
        dose: Dose per interval (mg).
        clearance: Total clearance (L/h).
        tau: Dosing interval (h).

    Returns:
        Average Css (mg/L).
    """
    var denom = clearance * tau
    if denom <= 0.0:
        return 0.0
    return bioavailability * dose / denom


fn loading_dose(volume_of_dist: Float64, target_conc: Float64) -> Float64:
    """Loading dose to achieve target plasma concentration.

    LD = Vd · Css_target

    Args:
        volume_of_dist: Volume of distribution (L).
        target_conc: Target concentration (mg/L).

    Returns:
        Loading dose (mg).
    """
    return volume_of_dist * target_conc


fn drug_interaction_index(
    dose_a: Float64, dm_a: Float64, dose_b: Float64, dm_b: Float64
) -> Float64:
    """Combination index (Chou-Talalay method).

    CI = Da/Dm_a + Db/Dm_b
    CI < 1 = synergy, CI = 1 = additivity, CI > 1 = antagonism.

    Args:
        dose_a: Dose of drug A in combination (same units as dm_a).
        dm_a: ED50 (or equipotent dose) of drug A alone.
        dose_b: Dose of drug B in combination.
        dm_b: ED50 of drug B alone.

    Returns:
        Combination index.
    """
    if dm_a <= 0.0 or dm_b <= 0.0:
        return 0.0
    return dose_a / dm_a + dose_b / dm_b
