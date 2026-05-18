"""
etiology.mojo — Disease causation and epidemiological risk calculations. Zero Python imports.

Public API:
  relative_risk                 — RR from cohort study
  odds_ratio                    — OR from case-control study
  attributable_risk             — AR = incidence_exposed - incidence_unexposed
  population_attributable_risk  — PAR from prevalence and RR
  number_needed_to_treat        — NNT from ARR
  sensitivity_test              — TP / (TP + FN)
  specificity_test              — TN / (TN + FP)
  positive_predictive_value     — PPV from Bayes
  negative_predictive_value     — NPV from Bayes
  likelihood_ratio_positive     — LR+ from sensitivity and specificity
"""
from std.math import log


fn relative_risk(
    incidence_exposed: Float64, incidence_unexposed: Float64
) -> Float64:
    """Relative risk from cohort study: RR = I_e / I_u.

    Args:
        incidence_exposed: Incidence in exposed group.
        incidence_unexposed: Incidence in unexposed group.

    Returns:
        Relative risk (>1 = increased risk, <1 = protective).
    """
    if incidence_unexposed <= 0.0:
        return 0.0
    return incidence_exposed / incidence_unexposed


fn odds_ratio(
    cases_exposed: Float64, cases_unexposed: Float64,
    controls_exposed: Float64, controls_unexposed: Float64
) -> Float64:
    """Odds ratio from 2×2 contingency table.

    OR = (a/b) / (c/d) = a×d / (b×c)

    Args:
        cases_exposed: Cases with exposure (a).
        cases_unexposed: Cases without exposure (b).
        controls_exposed: Controls with exposure (c).
        controls_unexposed: Controls without exposure (d).

    Returns:
        Odds ratio.
    """
    var denom = cases_unexposed * controls_exposed
    if denom <= 0.0:
        return 0.0
    return (cases_exposed * controls_unexposed) / denom


fn attributable_risk(
    incidence_exposed: Float64, incidence_unexposed: Float64
) -> Float64:
    """Attributable (absolute) risk: AR = I_e - I_u.

    Args:
        incidence_exposed: Incidence in exposed group (per 1000 or fraction).
        incidence_unexposed: Incidence in unexposed group.

    Returns:
        Attributable risk (same units as incidence).
    """
    return incidence_exposed - incidence_unexposed


fn population_attributable_risk(
    exposure_prevalence: Float64, relative_risk: Float64
) -> Float64:
    """Population attributable risk fraction.

    PAF = p(RR-1) / (p(RR-1)+1)

    Args:
        exposure_prevalence: Prevalence of exposure in population (0–1).
        relative_risk: Relative risk of disease given exposure.

    Returns:
        Population attributable fraction (0–1).
    """
    var numerator = exposure_prevalence * (relative_risk - 1.0)
    var denom = numerator + 1.0
    if denom <= 0.0:
        return 0.0
    return numerator / denom


fn number_needed_to_treat(
    control_event_rate: Float64, treatment_event_rate: Float64
) -> Float64:
    """Number needed to treat: NNT = 1 / ARR.

    Args:
        control_event_rate: Event rate without treatment.
        treatment_event_rate: Event rate with treatment.

    Returns:
        NNT (patients treated per prevented event).
    """
    var arr = control_event_rate - treatment_event_rate
    if arr <= 0.0:
        return 0.0
    return 1.0 / arr


fn sensitivity_test(true_positive: Float64, false_negative: Float64) -> Float64:
    """Diagnostic sensitivity: Se = TP / (TP + FN).

    Args:
        true_positive: True positive test results.
        false_negative: False negative test results.

    Returns:
        Sensitivity (0–1; probability of positive test given disease).
    """
    var denom = true_positive + false_negative
    if denom <= 0.0:
        return 0.0
    return true_positive / denom


fn specificity_test(true_negative: Float64, false_positive: Float64) -> Float64:
    """Diagnostic specificity: Sp = TN / (TN + FP).

    Args:
        true_negative: True negative test results.
        false_positive: False positive test results.

    Returns:
        Specificity (0–1; probability of negative test given no disease).
    """
    var denom = true_negative + false_positive
    if denom <= 0.0:
        return 0.0
    return true_negative / denom


fn positive_predictive_value(
    sensitivity: Float64, specificity: Float64, prevalence: Float64
) -> Float64:
    """Positive predictive value from Bayes' theorem.

    PPV = Se×p / (Se×p + (1-Sp)×(1-p))

    Args:
        sensitivity: Test sensitivity (0–1).
        specificity: Test specificity (0–1).
        prevalence: Disease prevalence in population (0–1).

    Returns:
        PPV (0–1).
    """
    var tp_rate = sensitivity * prevalence
    var fp_rate = (1.0 - specificity) * (1.0 - prevalence)
    var denom = tp_rate + fp_rate
    if denom <= 0.0:
        return 0.0
    return tp_rate / denom


fn negative_predictive_value(
    sensitivity: Float64, specificity: Float64, prevalence: Float64
) -> Float64:
    """Negative predictive value from Bayes' theorem.

    NPV = Sp×(1-p) / (Sp×(1-p) + (1-Se)×p)

    Args:
        sensitivity: Test sensitivity (0–1).
        specificity: Test specificity (0–1).
        prevalence: Disease prevalence (0–1).

    Returns:
        NPV (0–1).
    """
    var tn_rate = specificity * (1.0 - prevalence)
    var fn_rate = (1.0 - sensitivity) * prevalence
    var denom = tn_rate + fn_rate
    if denom <= 0.0:
        return 0.0
    return tn_rate / denom


fn likelihood_ratio_positive(
    sensitivity: Float64, specificity: Float64
) -> Float64:
    """Positive likelihood ratio: LR+ = sensitivity / (1 - specificity).

    Args:
        sensitivity: Test sensitivity (0–1).
        specificity: Test specificity (0–1).

    Returns:
        LR+ (>10 = strong evidence for disease).
    """
    var denominator = 1.0 - specificity
    if denominator <= 0.0:
        return 0.0
    return sensitivity / denominator
