"""
cardiology.mojo — Cardiac physiology calculations. Zero Python imports.

Public API:
  cardiac_output                — CO = HR × SV
  stroke_volume                 — SV = EDV - ESV
  ejection_fraction             — EF = SV / EDV
  mean_arterial_pressure        — MAP from systolic/diastolic
  pulse_pressure                — PP = systolic - diastolic
  systemic_vascular_resistance  — SVR from pressures and CO
  rate_pressure_product         — double product for O2 demand
  left_ventricular_work         — LVW per beat
  coronary_perfusion_pressure   — CPP = diastolic - LVEDP
  fick_cardiac_output           — from O2 consumption and difference
"""
from std.math import sqrt


fn cardiac_output(heart_rate: Float64, stroke_volume_ml: Float64) -> Float64:
    """Cardiac output: CO = HR × SV.

    Args:
        heart_rate: Heart rate (beats/min).
        stroke_volume_ml: Stroke volume (mL/beat).

    Returns:
        Cardiac output (L/min).
    """
    return heart_rate * stroke_volume_ml / 1000.0


fn stroke_volume(edv_ml: Float64, esv_ml: Float64) -> Float64:
    """Stroke volume: SV = EDV - ESV.

    Args:
        edv_ml: End-diastolic volume (mL).
        esv_ml: End-systolic volume (mL).

    Returns:
        Stroke volume (mL).
    """
    var sv = edv_ml - esv_ml
    if sv < 0.0:
        return 0.0
    return sv


fn ejection_fraction(edv_ml: Float64, esv_ml: Float64) -> Float64:
    """Left ventricular ejection fraction: EF = SV / EDV.

    Args:
        edv_ml: End-diastolic volume (mL).
        esv_ml: End-systolic volume (mL).

    Returns:
        Ejection fraction (0–1; normal >0.55).
    """
    if edv_ml <= 0.0:
        return 0.0
    return (edv_ml - esv_ml) / edv_ml


fn mean_arterial_pressure(
    systolic_mmhg: Float64, diastolic_mmhg: Float64
) -> Float64:
    """Mean arterial pressure: MAP = DBP + 1/3 × PP.

    Args:
        systolic_mmhg: Systolic blood pressure (mmHg).
        diastolic_mmhg: Diastolic blood pressure (mmHg).

    Returns:
        MAP (mmHg).
    """
    return diastolic_mmhg + (systolic_mmhg - diastolic_mmhg) / 3.0


fn pulse_pressure(systolic_mmhg: Float64, diastolic_mmhg: Float64) -> Float64:
    """Pulse pressure: PP = SBP - DBP.

    Args:
        systolic_mmhg: Systolic BP (mmHg).
        diastolic_mmhg: Diastolic BP (mmHg).

    Returns:
        Pulse pressure (mmHg).
    """
    return systolic_mmhg - diastolic_mmhg


fn systemic_vascular_resistance(
    map_mmhg: Float64, cvp_mmhg: Float64, co_l_per_min: Float64
) -> Float64:
    """Systemic vascular resistance: SVR = (MAP - CVP) / CO × 80.

    Args:
        map_mmhg: Mean arterial pressure (mmHg).
        cvp_mmhg: Central venous pressure (mmHg).
        co_l_per_min: Cardiac output (L/min).

    Returns:
        SVR (dyne·s/cm⁵; normal 800–1200).
    """
    if co_l_per_min <= 0.0:
        return 0.0
    return (map_mmhg - cvp_mmhg) / co_l_per_min * 80.0


fn rate_pressure_product(
    heart_rate: Float64, systolic_mmhg: Float64
) -> Float64:
    """Rate-pressure product (double product) — myocardial O2 demand index.

    RPP = HR × SBP

    Args:
        heart_rate: Heart rate (beats/min).
        systolic_mmhg: Systolic blood pressure (mmHg).

    Returns:
        Rate-pressure product (beats·mmHg/min; >20 000 = high demand).
    """
    return heart_rate * systolic_mmhg


fn left_ventricular_work(
    stroke_volume_l: Float64, map_mmhg: Float64
) -> Float64:
    """Left ventricular stroke work: LSW = SV × MAP × 0.0136.

    Args:
        stroke_volume_l: Stroke volume (L).
        map_mmhg: Mean arterial pressure (mmHg).

    Returns:
        Stroke work (g·m per beat; normal 60–80).
    """
    return stroke_volume_l * map_mmhg * 0.0136 * 1000.0


fn coronary_perfusion_pressure(
    diastolic_mmhg: Float64, lvedp_mmhg: Float64
) -> Float64:
    """Coronary perfusion pressure: CPP = DBP - LVEDP.

    Args:
        diastolic_mmhg: Diastolic blood pressure (mmHg).
        lvedp_mmhg: Left ventricular end-diastolic pressure (mmHg).

    Returns:
        CPP (mmHg; normal >50).
    """
    return diastolic_mmhg - lvedp_mmhg


fn fick_cardiac_output(
    vo2_ml_per_min: Float64, cao2: Float64, cvo2: Float64
) -> Float64:
    """Cardiac output by Fick principle: CO = VO2 / (CaO2 - CvO2).

    Args:
        vo2_ml_per_min: Oxygen consumption (mL O2/min).
        cao2: Arterial O2 content (mL O2/dL).
        cvo2: Mixed venous O2 content (mL O2/dL).

    Returns:
        Cardiac output (L/min).
    """
    var diff = cao2 - cvo2
    if diff <= 0.0:
        return 0.0
    return vo2_ml_per_min / (diff * 10.0)
