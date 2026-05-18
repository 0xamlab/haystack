"""
pharmacokinetics.mojo — Pharmacokinetics Library. Zero Python imports.

Models for drug absorption, distribution, and elimination including
one-compartment models, clearance, bioavailability, and dosing.

Public API:
  one_compartment_oral        — Oral one-compartment concentration
  one_compartment_iv          — IV bolus one-compartment concentration
  half_life                   — t½ from elimination rate
  elimination_rate            — ke from half-life
  clearance                   — Cl = ke * Vd
  bioavailability             — F = AUC_oral / AUC_iv
  loading_dose                — LD = Css * Vd
  maintenance_dose            — MD = Css * Cl * tau
  steady_state_concentration  — Css = dose / (tau * Cl)
  time_to_peak                — tmax for oral dosing
  accumulation_factor         — R = 1 / (1 - exp(-ke*tau))
  drug_auc_trapezoidal        — Trapezoidal AUC segment
"""
from std.math import log, exp


# ── Constants ─────────────────────────────────────────────────────────────────

comptime LN2: Float64 = 0.6931471805599453


# ── one_compartment_oral ──────────────────────────────────────────────────────


fn one_compartment_oral(
    dose: Float64, ka: Float64, ke: Float64, vd: Float64, t: Float64,
) -> Float64:
    """C(t) = (dose*ka) / (vd*(ka-ke)) * (exp(-ke*t) - exp(-ka*t))."""
    return (dose * ka) / (vd * (ka - ke)) * (exp(-ke * t) - exp(-ka * t))


# ── one_compartment_iv ────────────────────────────────────────────────────────


fn one_compartment_iv(
    dose: Float64, ke: Float64, vd: Float64, t: Float64,
) -> Float64:
    """C(t) = (dose / vd) * exp(-ke * t)."""
    return (dose / vd) * exp(-ke * t)


# ── half_life ─────────────────────────────────────────────────────────────────


fn half_life(ke: Float64) -> Float64:
    """t½ = ln(2) / ke."""
    return LN2 / ke


# ── elimination_rate ──────────────────────────────────────────────────────────


fn elimination_rate(half_life_val: Float64) -> Float64:
    """ke = ln(2) / t½."""
    return LN2 / half_life_val


# ── clearance ─────────────────────────────────────────────────────────────────


fn clearance(ke: Float64, vd: Float64) -> Float64:
    """Cl = ke * Vd."""
    return ke * vd


# ── bioavailability ───────────────────────────────────────────────────────────


fn bioavailability(auc_oral: Float64, auc_iv: Float64) -> Float64:
    """F = AUC_oral / AUC_iv."""
    return auc_oral / auc_iv


# ── loading_dose ──────────────────────────────────────────────────────────────


fn loading_dose(css: Float64, vd: Float64) -> Float64:
    """LD = Css * Vd."""
    return css * vd


# ── maintenance_dose ──────────────────────────────────────────────────────────


fn maintenance_dose(css: Float64, cl: Float64, tau: Float64) -> Float64:
    """MD = Css * Cl * τ."""
    return css * cl * tau


# ── steady_state_concentration ────────────────────────────────────────────────


fn steady_state_concentration(
    dose: Float64, tau: Float64, cl: Float64,
) -> Float64:
    """Css = dose / (tau * Cl)."""
    return dose / (tau * cl)


# ── time_to_peak ──────────────────────────────────────────────────────────────


fn time_to_peak(ka: Float64, ke: Float64) -> Float64:
    """tmax = ln(ka/ke) / (ka - ke)."""
    return log(ka / ke) / (ka - ke)


# ── accumulation_factor ───────────────────────────────────────────────────────


fn accumulation_factor(ke: Float64, tau: Float64) -> Float64:
    """R = 1 / (1 - exp(-ke * tau))."""
    return 1.0 / (1.0 - exp(-ke * tau))


# ── drug_auc_trapezoidal ─────────────────────────────────────────────────────


fn drug_auc_trapezoidal(
    c1: Float64, c2: Float64, t1: Float64, t2: Float64,
) -> Float64:
    """Trapezoidal AUC segment = (c1 + c2) / 2 * (t2 - t1)."""
    return (c1 + c2) / 2.0 * (t2 - t1)
