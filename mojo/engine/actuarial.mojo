"""
actuarial.mojo — Actuarial Science Library. Zero Python imports.

Pure Mojo implementations of core actuarial functions including time-value
of money, annuities, mortality, life insurance premiums, and loss ratios.

Public API:
  present_value             — PV = FV / (1+r)^n
  future_value              — FV = PV * (1+r)^n
  annuity_present_value     — PV of ordinary annuity
  annuity_future_value      — FV of ordinary annuity
  life_expectancy_curtate   — Simplified curtate life expectancy
  mortality_rate            — qx = deaths / exposed
  survival_probability      — px = 1 - qx
  force_of_mortality        — μx ≈ -ln(1 - qx)
  net_single_premium        — NSP = benefit * v * px
  loss_ratio                — LR = claims / premiums
  combined_ratio            — CR = LR + ER
  reserve_prospective       — V = PVFB - PVFP
"""
from std.math import sqrt, abs as fabs, exp, log, pow


# ── Helper: power via exp/log ─────────────────────────────────────────────────


def _power(base: Float64, exponent: Float64) -> Float64:
    """Compute base^exponent via exp(exponent * ln(base))."""
    if exponent == 0.0:
        return 1.0
    if base <= 0.0:
        return 0.0
    return exp(exponent * log(base))


# ── present_value ─────────────────────────────────────────────────────────────


def present_value(
    future_value_amt: Float64, rate: Float64, periods: Float64
) -> Float64:
    """PV = FV / (1 + r)^n."""
    return future_value_amt / _power(1.0 + rate, periods)


# ── future_value ──────────────────────────────────────────────────────────────


def future_value(
    present_value_val: Float64, rate: Float64, periods: Float64
) -> Float64:
    """FV = PV * (1 + r)^n."""
    return present_value_val * _power(1.0 + rate, periods)


# ── annuity_present_value ─────────────────────────────────────────────────────


def annuity_present_value(
    payment: Float64, rate: Float64, periods: Float64
) -> Float64:
    """PV = PMT * (1 - (1+r)^(-n)) / r."""
    if rate == 0.0:
        return payment * periods
    return payment * (1.0 - _power(1.0 + rate, -periods)) / rate


# ── annuity_future_value ──────────────────────────────────────────────────────


def annuity_future_value(
    payment: Float64, rate: Float64, periods: Float64
) -> Float64:
    """FV = PMT * ((1+r)^n - 1) / r."""
    if rate == 0.0:
        return payment * periods
    return payment * (_power(1.0 + rate, periods) - 1.0) / rate


# ── life_expectancy_curtate ───────────────────────────────────────────────────


def life_expectancy_curtate(
    qx: Float64, age: Int, max_age: Int
) -> Float64:
    """Simplified curtate life expectancy using constant qx.

    e_x ≈ Σ_{k=1}^{max_age - age} (1-qx)^k.
    """
    var total: Float64 = 0.0
    var px = 1.0 - qx
    var cum_px: Float64 = 1.0
    for _ in range(1, max_age - age + 1):
        cum_px *= px
        total += cum_px
    return total


# ── mortality_rate ────────────────────────────────────────────────────────────


def mortality_rate(deaths: Float64, exposed: Float64) -> Float64:
    """qx = deaths / exposed."""
    return deaths / exposed


# ── survival_probability ──────────────────────────────────────────────────────


def survival_probability(qx: Float64) -> Float64:
    """px = 1 - qx."""
    return 1.0 - qx


# ── force_of_mortality ────────────────────────────────────────────────────────


def force_of_mortality(qx: Float64) -> Float64:
    """μx ≈ -ln(1 - qx)."""
    # qx >= 1 degenerates the log to inf/NaN, which cannot cross the wire.
    if qx >= 1.0:
        return 0.0
    return -log(1.0 - qx)


# ── net_single_premium ────────────────────────────────────────────────────────


def net_single_premium(
    benefit: Float64, v: Float64, px: Float64
) -> Float64:
    """One-year term NSP = benefit * v * px.

    v = discount factor = 1/(1+i).
    """
    return benefit * v * px


# ── loss_ratio ────────────────────────────────────────────────────────────────


def loss_ratio(claims: Float64, premiums: Float64) -> Float64:
    """LR = claims / premiums."""
    return claims / premiums


# ── combined_ratio ────────────────────────────────────────────────────────────


def combined_ratio(
    loss_ratio_val: Float64, expense_ratio: Float64
) -> Float64:
    """CR = LR + ER."""
    return loss_ratio_val + expense_ratio


# ── reserve_prospective ───────────────────────────────────────────────────────


def reserve_prospective(
    future_benefits_pv: Float64, future_premiums_pv: Float64
) -> Float64:
    """Prospective reserve: V = PVFB - PVFP."""
    return future_benefits_pv - future_premiums_pv
