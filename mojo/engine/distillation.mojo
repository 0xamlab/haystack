"""Distillation / Separation Engineering Library.

Provides functions for distillation column design, vapor-liquid equilibrium,
and separation process calculations.
"""

from std.math import sqrt, log, exp, abs


def relative_volatility(y1: Float64, x1: Float64) -> Float64:
    """Compute relative volatility α = (y/(1-y)) / (x/(1-x))."""
    if x1 <= 0.0 or x1 >= 1.0 or y1 <= 0.0 or y1 >= 1.0:
        return 0.0
    return (y1 / (1.0 - y1)) / (x1 / (1.0 - x1))


def min_reflux_underwood(alpha: Float64, xd: Float64, xf: Float64, q: Float64) -> Float64:
    """Minimum reflux ratio (Underwood, simplified for q=1).

    Rmin ≈ (α*xd - xf) / (α - 1).
    """
    if abs(alpha - 1.0) < 1e-15:
        return 0.0
    return (alpha * xd - xf) / (alpha - 1.0)


def actual_reflux(rmin: Float64, factor: Float64) -> Float64:
    """Actual reflux ratio R = Rmin * factor (typically 1.2–1.5)."""
    return rmin * factor


def fenske_min_stages(xd: Float64, xb: Float64, alpha: Float64) -> Float64:
    """Fenske equation for minimum number of stages.

    Nmin = log((xd/(1-xd))*((1-xb)/xb)) / log(α).
    """
    if alpha <= 1.0 or xd <= 0.0 or xd >= 1.0 or xb <= 0.0 or xb >= 1.0:
        return 0.0
    var numerator = log((xd / (1.0 - xd)) * ((1.0 - xb) / xb))
    var denominator = log(alpha)
    if abs(denominator) < 1e-15:
        return 0.0
    return numerator / denominator


def gilliland_stages(nmin: Float64, rmin: Float64, r: Float64) -> Float64:
    """Gilliland correlation for actual number of stages.

    N ≈ Nmin + (Nmin+1) * (0.75 * (1 - (R-Rmin)/(R+1))^0.566) simplified.
    """
    if r + 1.0 == 0.0:
        return nmin
    var x_val = (r - rmin) / (r + 1.0)
    if x_val < 0.0:
        x_val = 0.0
    if x_val > 1.0:
        x_val = 1.0
    var y_val = 0.75 * exp(0.566 * log(1.0 - x_val)) if (1.0 - x_val) > 0.0 else 0.0
    return nmin + (nmin + 1.0) * y_val


def mccabe_thiele_operating_line_enriching(r: Float64, xd: Float64, x: Float64) -> Float64:
    """McCabe-Thiele enriching section operating line.

    y = R/(R+1)*x + xd/(R+1).
    """
    if r + 1.0 == 0.0:
        return 0.0
    return (r / (r + 1.0)) * x + xd / (r + 1.0)


def mccabe_thiele_operating_line_stripping(
    r: Float64, xd: Float64, xb: Float64, x: Float64, f_ratio: Float64
) -> Float64:
    """McCabe-Thiele stripping section operating line (simplified).

    y = ((R+f_ratio)/(R+1))*x - (xb*(f_ratio-1))/(R+1).
    """
    if r + 1.0 == 0.0:
        return 0.0
    return ((r + f_ratio) / (r + 1.0)) * x - (xb * (f_ratio - 1.0)) / (r + 1.0)


def boiling_point_elevation(kb: Float64, molality: Float64) -> Float64:
    """Boiling point elevation ΔTb = Kb * m."""
    return kb * molality


def raoults_law_partial_pressure(x: Float64, psat: Float64) -> Float64:
    """Raoult's law partial pressure p = x * Psat."""
    return x * psat


def daltons_law_total_pressure(p1: Float64, p2: Float64) -> Float64:
    """Dalton's law total pressure P = p1 + p2."""
    return p1 + p2


def stage_efficiency(y_actual: Float64, y_equilibrium: Float64, y_in: Float64) -> Float64:
    """Murphree stage efficiency E = (y_actual - y_in)/(y_eq - y_in) * 100."""
    var denom = y_equilibrium - y_in
    if abs(denom) < 1e-15:
        return 0.0
    return (y_actual - y_in) / denom * 100.0


def heat_duty_condenser(v_rate: Float64, latent_heat: Float64) -> Float64:
    """Heat duty of condenser Q = V * λ."""
    return v_rate * latent_heat
