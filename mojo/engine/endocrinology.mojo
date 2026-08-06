"""
endocrinology.mojo — Hormone physiology calculations. Zero Python imports.

Public API:
  hormone_clearance_rate       — CL = dose / AUC
  receptor_binding_bmax        — max binding from saturation curve
  feedback_gain                — open-loop gain of hormone axis
  hormone_pulsatility          — pulse frequency from LH pulses
  cortisol_circadian           — cosine model for diurnal rhythm
  insulin_sensitivity_index    — HOMA-IR from glucose and insulin
  thyroid_free_fraction        — free T4 from total and binding
  growth_rate_igf              — linear growth response to IGF-1
  testosterone_free            — free T from total and SHBG
  negative_feedback_strength   — Hill coefficient for setpoint
"""
from std.math import cos, exp, log, pow


def hormone_clearance_rate(dose: Float64, auc: Float64) -> Float64:
    """Hormone metabolic clearance rate: CL = dose / AUC.

    Args:
        dose: Hormone bolus dose (ng or μg).
        auc: Area under concentration-time curve (ng·min/mL).

    Returns:
        Clearance rate (mL/min).
    """
    if auc <= 0.0:
        return 0.0
    return dose / auc


def receptor_binding_bmax(
    bound: Float64, free_conc: Float64, kd: Float64
) -> Float64:
    """Maximum binding capacity Bmax from Scatchard analysis.

    Bmax = bound + bound·Kd / free_conc

    Args:
        bound: Bound hormone (fmol/mg protein).
        free_conc: Free hormone concentration (nM).
        kd: Dissociation constant (nM).

    Returns:
        Bmax (fmol/mg protein).
    """
    if free_conc <= 0.0:
        return 0.0
    return bound + bound * kd / free_conc


def feedback_gain(
    open_loop_gain: Float64, feedback_fraction: Float64
) -> Float64:
    """Closed-loop gain of a hormonal feedback axis.

    G_cl = G_ol / (1 + G_ol·f)

    Args:
        open_loop_gain: Open-loop gain G_ol.
        feedback_fraction: Feedback fraction f (0–1).

    Returns:
        Closed-loop gain.
    """
    var denom = 1.0 + open_loop_gain * feedback_fraction
    if denom <= 0.0:
        return 0.0
    return open_loop_gain / denom


def hormone_pulsatility(
    n_pulses: Float64, observation_hours: Float64
) -> Float64:
    """Pulse frequency of a pulsatile hormone.

    frequency = n_pulses / time (pulses/hour)

    Args:
        n_pulses: Number of hormone pulses detected.
        observation_hours: Observation window (h).

    Returns:
        Pulse frequency (pulses/h).
    """
    if observation_hours <= 0.0:
        return 0.0
    return n_pulses / observation_hours


def cortisol_circadian(
    time_hours: Float64, peak_value: Float64, trough_value: Float64
) -> Float64:
    """Cortisol diurnal variation (cosine model, peak at 0800h).

    C(t) = mean + amplitude·cos(2π·(t-8)/24)

    Args:
        time_hours: Time of day (0–24 h).
        peak_value: Morning peak (nmol/L).
        trough_value: Evening trough (nmol/L).

    Returns:
        Cortisol concentration (nmol/L).
    """
    var mean = (peak_value + trough_value) / 2.0
    var amplitude = (peak_value - trough_value) / 2.0
    var pi = 3.141592653589793
    return mean + amplitude * cos(2.0 * pi * (time_hours - 8.0) / 24.0)


def insulin_sensitivity_index(
    fasting_glucose_mmol: Float64, fasting_insulin_pmol: Float64
) -> Float64:
    """HOMA-IR insulin resistance index.

    HOMA-IR = (glucose_mM × insulin_μU/mL) / 22.5

    Args:
        fasting_glucose_mmol: Fasting plasma glucose (mmol/L).
        fasting_insulin_pmol: Fasting serum insulin (pmol/L, converted: pmol ÷ 6 = μU/mL).

    Returns:
        HOMA-IR (>2.5 = insulin resistant).
    """
    var insulin_uIU = fasting_insulin_pmol / 6.0  # pmol/L → μU/mL
    return fasting_glucose_mmol * insulin_uIU / 22.5


def thyroid_free_fraction(
    total_t4: Float64, tbg_conc: Float64, binding_constant: Float64
) -> Float64:
    """Free fraction of T4 from total and TBG.

    f_free = 1 / (1 + Ka·[TBG])

    Args:
        total_t4: Total T4 (nmol/L).
        tbg_conc: Thyroxine-binding globulin concentration (nmol/L).
        binding_constant: Association constant Ka (L/nmol).

    Returns:
        Free T4 fraction (dimensionless).
    """
    var denom = 1.0 + binding_constant * tbg_conc
    if denom <= 0.0:
        return 1.0
    return 1.0 / denom


def growth_rate_igf(
    igf1_nmol: Float64, baseline_rate: Float64, sensitivity: Float64
) -> Float64:
    """Linear growth rate from IGF-1 stimulation.

    growth_rate = baseline + sensitivity × IGF-1

    Args:
        igf1_nmol: IGF-1 concentration (nmol/L).
        baseline_rate: Basal growth rate (cm/yr).
        sensitivity: Growth sensitivity (cm/yr per nmol/L IGF-1).

    Returns:
        Predicted growth rate (cm/yr).
    """
    return baseline_rate + sensitivity * igf1_nmol


def testosterone_free(
    total_t: Float64, shbg: Float64, albumin: Float64
) -> Float64:
    """Free testosterone from total, SHBG and albumin (Vermeulen 1999).

    Simplified: %Free ≈ 100 / (1 + Ka_SHBG·SHBG + Ka_Alb·Alb)

    Args:
        total_t: Total testosterone (nmol/L).
        shbg: SHBG concentration (nmol/L).
        albumin: Albumin concentration (g/dL, typical 4.3).

    Returns:
        Free testosterone (nmol/L).
    """
    var ka_shbg = 5.97e8 / 1e9  # L/nmol
    var ka_alb = 3.6e4 / 1e9   # L/nmol (albumin 66,500 g/mol)
    var alb_nmol = albumin / 66.5e-3 * 1000.0  # g/dL → nmol/L (approx)
    var denom = 1.0 + ka_shbg * shbg + ka_alb * alb_nmol
    if denom <= 0.0:
        return total_t
    return total_t / denom


def negative_feedback_strength(
    response_at_half_max: Float64, hill_n: Float64
) -> Float64:
    """Effective Hill coefficient for setpoint regulation strength.

    Strength index = n × (1/2)^(n-1) / (1 + (1/2)^n)²

    Args:
        response_at_half_max: Fractional response at EC50 (typically 0.5).
        hill_n: Hill coefficient n.

    Returns:
        Maximum slope of Hill curve (dimensionless, measure of switch sharpness).
    """
    var r = response_at_half_max
    return hill_n * pow(r, hill_n - 1.0) / pow(1.0 + pow(r, hill_n), 2.0)
