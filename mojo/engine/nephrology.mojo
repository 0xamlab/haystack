"""
nephrology.mojo — Kidney function and renal physiology calculations. Zero Python imports.

Public API:
  gfr_ckd_epi                  — eGFR from creatinine (CKD-EPI simplified)
  creatinine_clearance_cockroft — Cockcroft-Gault formula
  fractional_excretion_sodium   — FENa for AKI classification
  urine_anion_gap               — UAG for metabolic acidosis
  transtubular_potassium_gradient — TTKG for K regulation
  renal_plasma_flow             — from PAH clearance
  filtration_fraction           — FF = GFR / RPF
  osmolar_clearance             — Cosm from urine/plasma
  free_water_clearance          — CH2O from osmolar clearance
  protein_creatinine_ratio      — PCR from spot urine
"""
from std.math import log, exp, pow


def gfr_ckd_epi(
    creatinine_mg_dl: Float64, age: Float64, is_female: Float64
) -> Float64:
    """Estimated GFR using simplified CKD-EPI equation.

    eGFR = 141 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^(-1.209) × 0.993^Age [× 1.018 female]

    Args:
        creatinine_mg_dl: Serum creatinine (mg/dL).
        age: Age (years).
        is_female: 1.0 for female, 0.0 for male.

    Returns:
        eGFR (mL/min/1.73m²).
    """
    var kappa = 0.9
    var alpha = -0.411
    if is_female > 0.5:
        kappa = 0.7
        alpha = -0.329
    var ratio = creatinine_mg_dl / kappa
    var min_ratio = ratio if ratio < 1.0 else 1.0
    var max_ratio = ratio if ratio > 1.0 else 1.0
    var egfr = 141.0 * pow(min_ratio, alpha) * pow(max_ratio, -1.209) * pow(0.993, age)
    if is_female > 0.5:
        egfr = egfr * 1.018
    return egfr


def creatinine_clearance_cockroft(
    age: Float64, weight_kg: Float64, creatinine_mg_dl: Float64, is_female: Float64
) -> Float64:
    """Cockcroft-Gault creatinine clearance.

    CrCl = (140-age) × weight / (72 × Scr) [× 0.85 female]

    Args:
        age: Age (years).
        weight_kg: Body weight (kg).
        creatinine_mg_dl: Serum creatinine (mg/dL).
        is_female: 1.0 for female, 0.0 for male.

    Returns:
        CrCl (mL/min).
    """
    if creatinine_mg_dl <= 0.0:
        return 0.0
    var crcl = (140.0 - age) * weight_kg / (72.0 * creatinine_mg_dl)
    if is_female > 0.5:
        crcl = crcl * 0.85
    return crcl


def fractional_excretion_sodium(
    urine_na: Float64, plasma_na: Float64,
    urine_cr: Float64, plasma_cr: Float64
) -> Float64:
    """Fractional excretion of sodium: FENa = (UNa × PCr) / (PNa × UCr) × 100.

    Args:
        urine_na: Urine sodium (mEq/L).
        plasma_na: Plasma sodium (mEq/L).
        urine_cr: Urine creatinine (mg/dL).
        plasma_cr: Plasma creatinine (mg/dL).

    Returns:
        FENa (%; <1% = prerenal AKI, >2% = intrinsic).
    """
    var denom = plasma_na * urine_cr
    if denom <= 0.0:
        return 0.0
    return urine_na * plasma_cr / denom * 100.0


def urine_anion_gap(
    urine_na: Float64, urine_k: Float64, urine_cl: Float64
) -> Float64:
    """Urine anion gap: UAG = Na + K - Cl.

    Args:
        urine_na: Urine sodium (mEq/L).
        urine_k: Urine potassium (mEq/L).
        urine_cl: Urine chloride (mEq/L).

    Returns:
        UAG (mEq/L; negative = diarrhoea, positive = RTA).
    """
    return urine_na + urine_k - urine_cl


def transtubular_potassium_gradient(
    urine_k: Float64, plasma_k: Float64,
    urine_osm: Float64, plasma_osm: Float64
) -> Float64:
    """TTKG for assessing distal K secretion.

    TTKG = (UK / PK) / (Uosm / Posm)

    Args:
        urine_k: Urine potassium (mEq/L).
        plasma_k: Plasma potassium (mEq/L).
        urine_osm: Urine osmolality (mOsm/kg).
        plasma_osm: Plasma osmolality (mOsm/kg).

    Returns:
        TTKG (normal 7-12 for hyperkalemia investigation).
    """
    if plasma_k <= 0.0 or plasma_osm <= 0.0:
        return 0.0
    var correction = urine_osm / plasma_osm
    if correction <= 0.0:
        return 0.0
    return (urine_k / plasma_k) / correction


def renal_plasma_flow(
    urine_pah_conc: Float64, plasma_pah_conc: Float64,
    urine_volume_ml_per_min: Float64
) -> Float64:
    """Effective renal plasma flow from para-aminohippurate clearance.

    ERPF = (U_PAH × V) / P_PAH

    Args:
        urine_pah_conc: Urine PAH concentration (mg/dL).
        plasma_pah_conc: Plasma PAH concentration (mg/dL).
        urine_volume_ml_per_min: Urine flow rate (mL/min).

    Returns:
        ERPF (mL/min; normal ~600).
    """
    if plasma_pah_conc <= 0.0:
        return 0.0
    return urine_pah_conc * urine_volume_ml_per_min / plasma_pah_conc


def filtration_fraction(gfr: Float64, rpf: Float64) -> Float64:
    """Filtration fraction: FF = GFR / RPF.

    Args:
        gfr: Glomerular filtration rate (mL/min).
        rpf: Renal plasma flow (mL/min).

    Returns:
        FF (normal ~0.20).
    """
    if rpf <= 0.0:
        return 0.0
    return gfr / rpf


def osmolar_clearance(
    urine_osm: Float64, urine_flow: Float64, plasma_osm: Float64
) -> Float64:
    """Osmolar clearance: Cosm = Uosm × V / Posm.

    Args:
        urine_osm: Urine osmolality (mOsm/kg).
        urine_flow: Urine flow rate (mL/min).
        plasma_osm: Plasma osmolality (mOsm/kg).

    Returns:
        Cosm (mL/min).
    """
    if plasma_osm <= 0.0:
        return 0.0
    return urine_osm * urine_flow / plasma_osm


def free_water_clearance(
    urine_flow: Float64, cosm: Float64
) -> Float64:
    """Free water clearance: CH2O = V - Cosm.

    Args:
        urine_flow: Urine flow rate (mL/min).
        cosm: Osmolar clearance (mL/min).

    Returns:
        Free water clearance (mL/min; negative in ADH excess).
    """
    return urine_flow - cosm


def protein_creatinine_ratio(
    urine_protein_mg_dl: Float64, urine_creatinine_mg_dl: Float64
) -> Float64:
    """Spot urine protein-to-creatinine ratio.

    PCR ≈ 24-h protein excretion (g/day)

    Args:
        urine_protein_mg_dl: Urine protein concentration (mg/dL).
        urine_creatinine_mg_dl: Urine creatinine concentration (mg/dL).

    Returns:
        PCR (mg/mg; >0.2 = significant proteinuria).
    """
    if urine_creatinine_mg_dl <= 0.0:
        return 0.0
    return urine_protein_mg_dl / urine_creatinine_mg_dl
