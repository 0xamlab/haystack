"""
pulmonology.mojo — Respiratory physiology and lung function calculations.
Zero Python imports.

Public API:
  tidal_volume_predicted        — predicted TV from weight
  minute_ventilation            — VE = TV × RR
  alveolar_ventilation          — VA = (TV - dead_space) × RR
  fev1_fvc_ratio                — obstructive pattern index
  peak_expiratory_flow          — PEF % predicted
  alveolar_oxygen               — PAO2 from alveolar gas equation
  a_a_gradient                  — (A-a) O2 gradient
  respiratory_quotient          — RQ = VCO2 / VO2
  compliance_static             — Cs = ΔV / ΔP
  airway_resistance             — Raw = ΔP / flow
"""
from std.math import sqrt


fn tidal_volume_predicted(ideal_body_weight_kg: Float64) -> Float64:
    """ARDSnet predicted tidal volume: 6–8 mL/kg IBW.

    Args:
        ideal_body_weight_kg: Ideal body weight (kg).

    Returns:
        Predicted tidal volume (mL, 6 mL/kg target).
    """
    return 6.0 * ideal_body_weight_kg


fn minute_ventilation(tidal_volume_ml: Float64, resp_rate: Float64) -> Float64:
    """Minute ventilation: VE = TV × RR.

    Args:
        tidal_volume_ml: Tidal volume (mL).
        resp_rate: Respiratory rate (breaths/min).

    Returns:
        Minute ventilation (L/min).
    """
    return tidal_volume_ml * resp_rate / 1000.0


fn alveolar_ventilation(
    tidal_volume_ml: Float64, dead_space_ml: Float64, resp_rate: Float64
) -> Float64:
    """Alveolar ventilation: VA = (TV - VD) × RR.

    Args:
        tidal_volume_ml: Tidal volume (mL).
        dead_space_ml: Anatomical dead space (mL, ~150 mL in adults).
        resp_rate: Respiratory rate (breaths/min).

    Returns:
        Alveolar ventilation (L/min).
    """
    var alv_vol = tidal_volume_ml - dead_space_ml
    if alv_vol <= 0.0:
        return 0.0
    return alv_vol * resp_rate / 1000.0


fn fev1_fvc_ratio(fev1_l: Float64, fvc_l: Float64) -> Float64:
    """FEV1/FVC ratio — indicator of obstructive disease.

    Args:
        fev1_l: Forced expiratory volume in 1 s (L).
        fvc_l: Forced vital capacity (L).

    Returns:
        Ratio (<0.70 = obstruction per GOLD criteria).
    """
    if fvc_l <= 0.0:
        return 0.0
    return fev1_l / fvc_l


fn peak_expiratory_flow(
    measured_pef_l_min: Float64, predicted_pef_l_min: Float64
) -> Float64:
    """PEF as percentage of predicted.

    Args:
        measured_pef_l_min: Measured peak flow (L/min).
        predicted_pef_l_min: Age/sex/height predicted value (L/min).

    Returns:
        % predicted (<60% = severe asthma).
    """
    if predicted_pef_l_min <= 0.0:
        return 0.0
    return measured_pef_l_min / predicted_pef_l_min * 100.0


fn alveolar_oxygen(
    fio2: Float64, paco2_mmhg: Float64, barometric_mmhg: Float64
) -> Float64:
    """Alveolar gas equation: PAO2 = FiO2·(PB - 47) - PaCO2/0.8.

    Args:
        fio2: Inspired O2 fraction (0.21 = room air).
        paco2_mmhg: Arterial CO2 partial pressure (mmHg).
        barometric_mmhg: Barometric pressure (mmHg, ~760 at sea level).

    Returns:
        Alveolar PO2 (mmHg).
    """
    return fio2 * (barometric_mmhg - 47.0) - paco2_mmhg / 0.8


fn a_a_gradient(
    pao2_mmhg: Float64, pao2_arterial_mmhg: Float64
) -> Float64:
    """Alveolar-arterial O2 gradient.

    Args:
        pao2_mmhg: Alveolar PO2 (from alveolar gas equation, mmHg).
        pao2_arterial_mmhg: Arterial PO2 from ABG (mmHg).

    Returns:
        (A-a) gradient (mmHg; normal <15 mmHg, age-adjusted ~2.5+0.21×age).
    """
    return pao2_mmhg - pao2_arterial_mmhg


fn respiratory_quotient(vco2: Float64, vo2: Float64) -> Float64:
    """Respiratory quotient: RQ = VCO2 / VO2.

    Args:
        vco2: CO2 production rate (mL/min or L/min).
        vo2: O2 consumption rate (same units).

    Returns:
        RQ (0.7–1.0; 0.7 fat, 0.85 mixed, 1.0 carb).
    """
    if vo2 <= 0.0:
        return 0.0
    return vco2 / vo2


fn compliance_static(
    volume_change_ml: Float64, pressure_change_cmh2o: Float64
) -> Float64:
    """Static lung compliance: Cs = ΔV / ΔP.

    Args:
        volume_change_ml: Volume change (mL).
        pressure_change_cmh2o: Pressure change (cmH2O).

    Returns:
        Static compliance (mL/cmH2O; normal ~100).
    """
    if pressure_change_cmh2o <= 0.0:
        return 0.0
    return volume_change_ml / pressure_change_cmh2o


fn airway_resistance(
    pressure_diff_cmh2o: Float64, flow_l_per_s: Float64
) -> Float64:
    """Airway resistance: Raw = ΔP / V̇.

    Args:
        pressure_diff_cmh2o: Driving pressure (cmH2O).
        flow_l_per_s: Airflow rate (L/s).

    Returns:
        Airway resistance (cmH2O·s/L; normal <2).
    """
    if flow_l_per_s <= 0.0:
        return 0.0
    return pressure_diff_cmh2o / flow_l_per_s
