"""
hematology.mojo — Blood science and haematological calculations. Zero Python imports.

Public API:
  hematocrit                   — HCT from RBC volume and total
  mean_corpuscular_volume      — MCV from HCT and RBC count
  mean_corpuscular_hemoglobin  — MCH from Hgb and RBC count
  mchc                         — MCHC from Hgb and HCT
  red_cell_distribution_width  — RDW from CV of MCV
  oxygen_carrying_capacity     — capacity from Hgb
  coagulation_inr              — INR from PT ratio
  platelet_count_index         — mean platelet volume × count
  blood_viscosity_relative     — relative to water from HCT
  erythrocyte_sedimentation    — ESR estimate from plasma protein
"""
from std.math import sqrt, pow, log


def hematocrit(rbc_volume: Float64, total_blood_volume: Float64) -> Float64:
    """Hematocrit (packed cell volume): HCT = V_RBC / V_total.

    Args:
        rbc_volume: Volume of red blood cells (mL or any unit).
        total_blood_volume: Total blood volume (same unit).

    Returns:
        Hematocrit (fraction 0–1, multiply by 100 for %).
    """
    if total_blood_volume <= 0.0:
        return 0.0
    return rbc_volume / total_blood_volume


def mean_corpuscular_volume(
    hematocrit_fraction: Float64, rbc_count_millions: Float64
) -> Float64:
    """Mean corpuscular volume: MCV = HCT / RBC_count × 10.

    Args:
        hematocrit_fraction: Hematocrit (fraction, e.g. 0.45 for 45%).
        rbc_count_millions: RBC count (×10⁶/μL).

    Returns:
        MCV (fL, femtolitres).
    """
    if rbc_count_millions <= 0.0:
        return 0.0
    return hematocrit_fraction * 10.0 / rbc_count_millions * 1000.0


def mean_corpuscular_hemoglobin(
    hemoglobin_g_dl: Float64, rbc_count_millions: Float64
) -> Float64:
    """Mean corpuscular haemoglobin: MCH = Hgb / RBC × 10.

    Args:
        hemoglobin_g_dl: Haemoglobin concentration (g/dL).
        rbc_count_millions: RBC count (×10⁶/μL).

    Returns:
        MCH (pg).
    """
    if rbc_count_millions <= 0.0:
        return 0.0
    return hemoglobin_g_dl / rbc_count_millions * 10.0


def mchc(hemoglobin_g_dl: Float64, hematocrit_fraction: Float64) -> Float64:
    """Mean corpuscular haemoglobin concentration: MCHC = Hgb / HCT.

    Args:
        hemoglobin_g_dl: Haemoglobin (g/dL).
        hematocrit_fraction: Hematocrit fraction.

    Returns:
        MCHC (g/dL).
    """
    if hematocrit_fraction <= 0.0:
        return 0.0
    return hemoglobin_g_dl / hematocrit_fraction


def red_cell_distribution_width(
    std_mcv: Float64, mean_mcv: Float64
) -> Float64:
    """RDW-CV: coefficient of variation of MCV.

    RDW = (std / mean) × 100

    Args:
        std_mcv: Standard deviation of MCV distribution (fL).
        mean_mcv: Mean MCV (fL).

    Returns:
        RDW (%).
    """
    if mean_mcv <= 0.0:
        return 0.0
    return (std_mcv / mean_mcv) * 100.0


def oxygen_carrying_capacity(hemoglobin_g_dl: Float64) -> Float64:
    """Oxygen carrying capacity from haemoglobin.

    O2_cap = 1.34 × Hgb  (mL O2 / dL blood, Huffner's constant)

    Args:
        hemoglobin_g_dl: Haemoglobin concentration (g/dL).

    Returns:
        O2 carrying capacity (mL O2/dL).
    """
    return 1.34 * hemoglobin_g_dl


def coagulation_inr(
    patient_pt: Float64, mean_normal_pt: Float64, isi: Float64
) -> Float64:
    """International Normalised Ratio for coagulation monitoring.

    INR = (PT_patient / PT_mean_normal)^ISI

    Args:
        patient_pt: Patient prothrombin time (s).
        mean_normal_pt: Mean normal prothrombin time (s).
        isi: International Sensitivity Index of thromboplastin.

    Returns:
        INR.
    """
    if mean_normal_pt <= 0.0:
        return 0.0
    return pow(patient_pt / mean_normal_pt, isi)


def platelet_count_index(
    mean_platelet_volume: Float64, platelet_count_k: Float64
) -> Float64:
    """Platelet large cell ratio index.

    PLT_index = MPV × PLT_count / 100

    Args:
        mean_platelet_volume: Mean platelet volume MPV (fL).
        platelet_count_k: Platelet count (×10³/μL).

    Returns:
        Platelet index.
    """
    return mean_platelet_volume * platelet_count_k / 100.0


def blood_viscosity_relative(hematocrit_fraction: Float64) -> Float64:
    """Relative blood viscosity from hematocrit (Charm-Kurland).

    η_rel ≈ (1 - HCT)^(-2.5)

    Args:
        hematocrit_fraction: Hematocrit fraction (0–0.6).

    Returns:
        Relative viscosity (compared to plasma).
    """
    if hematocrit_fraction < 0.0 or hematocrit_fraction >= 1.0:
        return 1.0
    return pow(1.0 - hematocrit_fraction, -2.5)


def erythrocyte_sedimentation(
    fibrinogen_g_l: Float64, age: Float64, sex_factor: Float64
) -> Float64:
    """Estimated ESR from fibrinogen and demographics.

    ESR ≈ fibrinogen × 0.4 + age × 0.065 + sex_factor  (simplified)

    Args:
        fibrinogen_g_l: Plasma fibrinogen concentration (g/L).
        age: Patient age (years).
        sex_factor: 10 for female, 0 for male (Westergren correction).

    Returns:
        Estimated ESR (mm/h).
    """
    var esr = fibrinogen_g_l * 0.4 + age * 0.065 + sex_factor
    if esr < 0.0:
        return 0.0
    return esr
