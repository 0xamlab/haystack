"""
toxicology.mojo — Toxicology Library. Zero Python imports.

Pure Mojo implementations of fundamental toxicology and risk-assessment
equations including LD50 dosing, therapeutic index, hazard quotient,
cancer risk, dose-response (Hill equation), and reference dose derivation.

Public API:
  ld50_dose                       — lethal dose from LD50 and body weight
  therapeutic_index               — TI = TD50 / ED50
  margin_of_safety                — MOS = TD01 / ED99
  bioconcentration_factor         — BCF = Corg / Cwater
  hazard_quotient                 — HQ = exposure dose / reference dose
  hazard_index                    — HI = Σ(HQi) (pre-summed)
  cancer_risk                     — Risk = CDI * slope factor
  average_daily_dose              — ADD = (C*IR*EF*ED) / (BW*AT)
  no_observed_adverse_effect_level — NOAEL ≈ LOAEL / UF
  reference_dose                  — RfD = NOAEL / UF
  dose_response_hill              — E = Emax*D^n / (EC50^n + D^n)
  acute_exposure_ratio            — AER = Cmeas / ATV
"""
from std.math import sqrt, exp, log, abs as fabs


# ── ld50_dose ────────────────────────────────────────────────────────────────


def ld50_dose(ld50_mg_kg: Float64, body_weight_kg: Float64) -> Float64:
    """Lethal dose: Dose = LD50 * BW (mg)."""
    return ld50_mg_kg * body_weight_kg


# ── therapeutic_index ────────────────────────────────────────────────────────


def therapeutic_index(td50: Float64, ed50: Float64) -> Float64:
    """Therapeutic index: TI = TD50 / ED50."""
    return td50 / ed50


# ── margin_of_safety ─────────────────────────────────────────────────────────


def margin_of_safety(td01: Float64, ed99: Float64) -> Float64:
    """Margin of safety: MOS = TD01 / ED99."""
    return td01 / ed99


# ── bioconcentration_factor ──────────────────────────────────────────────────


def bioconcentration_factor(conc_organism: Float64, conc_water: Float64) -> Float64:
    """Bioconcentration factor: BCF = Corg / Cwater."""
    return conc_organism / conc_water


# ── hazard_quotient ──────────────────────────────────────────────────────────


def hazard_quotient(exposure_dose: Float64, reference_dose: Float64) -> Float64:
    """Hazard quotient: HQ = exposure dose / reference dose."""
    return exposure_dose / reference_dose


# ── hazard_index ─────────────────────────────────────────────────────────────


def hazard_index(hq_values_sum: Float64) -> Float64:
    """Hazard index: HI = Σ(HQi). Pass the pre-summed total."""
    return hq_values_sum


# ── cancer_risk ──────────────────────────────────────────────────────────────


def cancer_risk(cdi: Float64, slope_factor: Float64) -> Float64:
    """Cancer risk: Risk = CDI * SF."""
    return cdi * slope_factor


# ── average_daily_dose ───────────────────────────────────────────────────────


def average_daily_dose(
    conc: Float64,
    intake_rate: Float64,
    exposure_freq: Float64,
    exposure_dur: Float64,
    body_weight: Float64,
    averaging_time: Float64,
) -> Float64:
    """Average daily dose: ADD = (C * IR * EF * ED) / (BW * AT)."""
    return (conc * intake_rate * exposure_freq * exposure_dur) / (
        body_weight * averaging_time
    )


# ── no_observed_adverse_effect_level ─────────────────────────────────────────


def no_observed_adverse_effect_level(
    loael: Float64, uncertainty_factor: Float64
) -> Float64:
    """NOAEL ≈ LOAEL / UF."""
    return loael / uncertainty_factor


# ── reference_dose_calc ──────────────────────────────────────────────────────


def reference_dose(noael: Float64, total_uf: Float64) -> Float64:
    """Reference dose: RfD = NOAEL / total UF."""
    return noael / total_uf


# ── dose_response_hill ───────────────────────────────────────────────────────


def dose_response_hill(
    dose: Float64, emax: Float64, ec50: Float64, n: Float64
) -> Float64:
    """Hill equation: E = Emax * D^n / (EC50^n + D^n).

    Uses exp/log to handle fractional exponents safely.
    """
    if dose <= 0.0:
        return 0.0
    var dn = exp(n * log(dose))
    var ecn = exp(n * log(ec50))
    return emax * dn / (ecn + dn)


# ── acute_exposure_ratio ─────────────────────────────────────────────────────


def acute_exposure_ratio(
    measured_conc: Float64, acute_toxicity_value: Float64
) -> Float64:
    """Acute exposure ratio: AER = Cmeas / ATV."""
    return measured_conc / acute_toxicity_value
