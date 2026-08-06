"""
biomedical.mojo — Biomedical Engineering Library. Zero Python imports.

Provides cardiovascular, renal, respiratory, and pharmacokinetic calculations.

Public API:
  cardiac_output             — CO = SV * HR / 1000
  mean_arterial_pressure     — MAP = DBP + (SBP-DBP)/3
  body_surface_area_dubois   — BSA via Du Bois formula
  glomerular_filtration_rate — GFR via Cockcroft-Gault
  oxygen_delivery            — DO2 = CO * (1.34*Hb*SaO2/100 + 0.003*100)
  alveolar_gas_equation      — PAO2 = FiO2*(Patm-PH2O) - PaCO2/RQ
  bmi                        — BMI = weight / height^2
  drug_clearance             — Cl = Dose / AUC
  anion_gap                  — AG = Na - (Cl + HCO3)
  corrected_qt_bazett        — QTc = QT / sqrt(RR)
  fick_cardiac_output        — CO = VO2 / (CaO2 - CvO2)
  pulse_pressure             — PP = SBP - DBP
"""
from std.math import sqrt, exp, log, abs as fabs


# ── cardiac_output ───────────────────────────────────────────────────────────


def cardiac_output(stroke_volume_ml: Float64, heart_rate: Float64) -> Float64:
    """Cardiac output: CO = SV * HR / 1000 (L/min).

    Args:
        stroke_volume_ml: Stroke volume in mL.
        heart_rate: Heart rate in bpm.

    Returns:
        Cardiac output in L/min.
    """
    return stroke_volume_ml * heart_rate / 1000.0


# ── mean_arterial_pressure ───────────────────────────────────────────────────


def mean_arterial_pressure(systolic: Float64, diastolic: Float64) -> Float64:
    """Mean arterial pressure: MAP = DBP + (SBP - DBP) / 3.

    Args:
        systolic: Systolic blood pressure (mmHg).
        diastolic: Diastolic blood pressure (mmHg).

    Returns:
        MAP in mmHg.
    """
    return diastolic + (systolic - diastolic) / 3.0


# ── body_surface_area_dubois ─────────────────────────────────────────────────


def body_surface_area_dubois(weight_kg: Float64, height_cm: Float64) -> Float64:
    """Du Bois body surface area: BSA = 0.007184 * W^0.425 * H^0.725.

    Args:
        weight_kg: Body weight in kg.
        height_cm: Height in cm.

    Returns:
        BSA in m^2.
    """
    if weight_kg <= 0.0 or height_cm <= 0.0:
        return 0.0
    var w_part = exp(0.425 * log(weight_kg))
    var h_part = exp(0.725 * log(height_cm))
    return 0.007184 * w_part * h_part


# ── glomerular_filtration_rate ───────────────────────────────────────────────


def glomerular_filtration_rate(
    creatinine: Float64,
    age: Float64,
    weight: Float64,
    is_female: Bool,
) -> Float64:
    """Cockcroft-Gault GFR: ((140-age)*weight) / (72*creatinine) * factor.

    Args:
        creatinine: Serum creatinine (mg/dL).
        age: Patient age in years.
        weight: Body weight in kg.
        is_female: True if patient is female (applies 0.85 factor).

    Returns:
        Estimated GFR in mL/min.
    """
    if fabs(creatinine) < 1e-30:
        return 0.0
    var gfr = ((140.0 - age) * weight) / (72.0 * creatinine)
    if is_female:
        gfr = gfr * 0.85
    return gfr


# ── oxygen_delivery ──────────────────────────────────────────────────────────


def oxygen_delivery(
    co: Float64, hb: Float64, sao2: Float64
) -> Float64:
    """Oxygen delivery: DO2 = CO * (1.34 * Hb * SaO2/100 + 0.003 * 100).

    Simplified formula combining bound + dissolved O2.

    Args:
        co: Cardiac output (L/min).
        hb: Hemoglobin (g/dL).
        sao2: Arterial oxygen saturation (%).

    Returns:
        DO2 in mL O2/min (approximately).
    """
    var content = 1.34 * hb * sao2 / 100.0 + 0.003 * 100.0
    return co * content * 10.0


# ── alveolar_gas_equation ────────────────────────────────────────────────────


def alveolar_gas_equation(
    fio2: Float64,
    patm: Float64,
    ph2o: Float64,
    paco2: Float64,
    rq: Float64,
) -> Float64:
    """Alveolar gas equation: PAO2 = FiO2*(Patm-PH2O) - PaCO2/RQ.

    Args:
        fio2: Fraction of inspired oxygen (0-1).
        patm: Atmospheric pressure (mmHg).
        ph2o: Water vapor pressure (mmHg).
        paco2: Arterial CO2 partial pressure (mmHg).
        rq: Respiratory quotient.

    Returns:
        Alveolar O2 partial pressure (mmHg).
    """
    if fabs(rq) < 1e-30:
        return 0.0
    return fio2 * (patm - ph2o) - paco2 / rq


# ── bmi ──────────────────────────────────────────────────────────────────────


def bmi(weight_kg: Float64, height_m: Float64) -> Float64:
    """Body Mass Index: BMI = weight / height^2.

    Args:
        weight_kg: Body weight in kg.
        height_m: Height in meters.

    Returns:
        BMI in kg/m^2.
    """
    if fabs(height_m) < 1e-30:
        return 0.0
    return weight_kg / (height_m * height_m)


# ── drug_clearance ───────────────────────────────────────────────────────────


def drug_clearance(dose: Float64, auc: Float64) -> Float64:
    """Drug clearance: Cl = Dose / AUC.

    Args:
        dose: Drug dose administered (mg).
        auc: Area under the curve (mg*h/L).

    Returns:
        Clearance (L/h).
    """
    if fabs(auc) < 1e-30:
        return 0.0
    return dose / auc


# ── anion_gap ────────────────────────────────────────────────────────────────


def anion_gap(na: Float64, cl: Float64, hco3: Float64) -> Float64:
    """Anion gap: AG = Na - (Cl + HCO3).

    Args:
        na: Sodium (mEq/L).
        cl: Chloride (mEq/L).
        hco3: Bicarbonate (mEq/L).

    Returns:
        Anion gap (mEq/L).
    """
    return na - (cl + hco3)


# ── corrected_qt_bazett ─────────────────────────────────────────────────────


def corrected_qt_bazett(qt_ms: Float64, rr_s: Float64) -> Float64:
    """Bazett corrected QT: QTc = QT / sqrt(RR).

    Args:
        qt_ms: QT interval in ms.
        rr_s: RR interval in seconds.

    Returns:
        Corrected QT interval in ms.
    """
    if rr_s <= 0.0:
        return 0.0
    return qt_ms / sqrt(rr_s)


# ── fick_cardiac_output ──────────────────────────────────────────────────────


def fick_cardiac_output(
    vo2: Float64, cao2: Float64, cvo2: Float64
) -> Float64:
    """Fick cardiac output: CO = VO2 / (CaO2 - CvO2).

    Args:
        vo2: Oxygen consumption (mL/min).
        cao2: Arterial oxygen content (mL O2/dL blood).
        cvo2: Venous oxygen content (mL O2/dL blood).

    Returns:
        Cardiac output (L/min).
    """
    var diff = cao2 - cvo2
    if fabs(diff) < 1e-30:
        return 0.0
    return vo2 / (diff * 10.0)


# ── pulse_pressure ───────────────────────────────────────────────────────────


def pulse_pressure(systolic: Float64, diastolic: Float64) -> Float64:
    """Pulse pressure: PP = SBP - DBP.

    Args:
        systolic: Systolic blood pressure (mmHg).
        diastolic: Diastolic blood pressure (mmHg).

    Returns:
        Pulse pressure (mmHg).
    """
    return systolic - diastolic
