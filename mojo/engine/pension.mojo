"""
pension.mojo — Pension & Retirement Planning Library. Zero Python imports.

Provides replacement ratio, defined benefit/contribution calculations,
annuity factors, funding ratios, and Social Security bend point formulas.

Public API:
  replacement_ratio              — RR = pension/salary * 100
  defined_benefit_pension        — P = years * salary * rate
  defined_contribution_value     — FV = C * ((1+r)^n - 1)/r
  annuity_factor                 — AF = (1-(1+r)^(-n))/r
  pension_lump_sum_from_annuity  — LS = P * AF
  funding_ratio                  — FR = assets/liabilities * 100
  contribution_rate_required     — CR = target/(salary*((1+r)^n-1)/r)*100
  inflation_adjusted_pension     — Real = nominal/(1+i)^n
  pension_gap                    — Gap = required - expected
  social_security_bend_points    — PIA formula with bend points
  years_to_full_vesting          — Vested% = min(100, service/schedule*100)
  withdrawal_rate                — WR = withdrawal/portfolio * 100
"""
from std.math import abs as fabs


# ── helpers ──────────────────────────────────────────────────────────────────


def _pow(base: Float64, n: Int) -> Float64:
    """Integer power via repeated multiplication."""
    if n == 0:
        return 1.0
    var result = 1.0
    var b = base
    var exp = n
    if exp < 0:
        b = 1.0 / b
        exp = -exp
    for _ in range(exp):
        result *= b
    return result


# ── replacement_ratio ────────────────────────────────────────────────────────


def replacement_ratio(
    pension_income: Float64, final_salary: Float64
) -> Float64:
    """Replacement ratio: RR = pension / salary * 100.

    Args:
        pension_income: Annual pension income.
        final_salary: Final annual salary.

    Returns:
        Replacement ratio (%).
    """
    if fabs(final_salary) < 1e-30:
        return 0.0
    return pension_income / final_salary * 100.0


# ── defined_benefit_pension ──────────────────────────────────────────────────


def defined_benefit_pension(
    years: Float64, salary: Float64, accrual_rate: Float64
) -> Float64:
    """Defined benefit pension: P = years * salary * accrual_rate.

    Args:
        years: Years of service.
        salary: Final or average salary.
        accrual_rate: Accrual rate per year (e.g. 1/60 = 0.01667).

    Returns:
        Annual pension benefit.
    """
    return years * salary * accrual_rate


# ── defined_contribution_value ───────────────────────────────────────────────


def defined_contribution_value(
    contributions: Float64, return_rate: Float64, years: Int
) -> Float64:
    """Defined contribution FV: C * ((1+r)^n - 1)/r.

    Args:
        contributions: Annual contribution amount.
        return_rate: Annual return rate (e.g. 0.07 for 7%).
        years: Number of years.

    Returns:
        Future value of contributions.
    """
    if fabs(return_rate) < 1e-30:
        return contributions * Float64(years)
    var growth = _pow(1.0 + return_rate, years) - 1.0
    return contributions * growth / return_rate


# ── annuity_factor ───────────────────────────────────────────────────────────


def annuity_factor(rate: Float64, years: Int) -> Float64:
    """Annuity factor: AF = (1 - (1+r)^(-n)) / r.

    Args:
        rate: Discount rate per period.
        years: Number of periods.

    Returns:
        Present value annuity factor.
    """
    if fabs(rate) < 1e-30:
        return Float64(years)
    var pv = 1.0 - _pow(1.0 + rate, -years)
    return pv / rate


# ── pension_lump_sum_from_annuity ────────────────────────────────────────────


def pension_lump_sum_from_annuity(
    annual_pension: Float64, annuity_factor_val: Float64
) -> Float64:
    """Lump sum from annuity: LS = pension * annuity_factor.

    Args:
        annual_pension: Annual pension payment.
        annuity_factor_val: Annuity factor.

    Returns:
        Equivalent lump sum.
    """
    return annual_pension * annuity_factor_val


# ── funding_ratio ────────────────────────────────────────────────────────────


def funding_ratio(
    plan_assets: Float64, plan_liabilities: Float64
) -> Float64:
    """Funding ratio: FR = assets / liabilities * 100.

    Args:
        plan_assets: Total plan assets.
        plan_liabilities: Total plan liabilities.

    Returns:
        Funding ratio (%).
    """
    if fabs(plan_liabilities) < 1e-30:
        return 0.0
    return plan_assets / plan_liabilities * 100.0


# ── contribution_rate_required ───────────────────────────────────────────────


def contribution_rate_required(
    target_fund: Float64, years: Int, salary: Float64, return_rate: Float64
) -> Float64:
    """Required contribution rate: CR = target / (salary * FV_factor) * 100.

    Args:
        target_fund: Target retirement fund.
        years: Years until retirement.
        salary: Annual salary.
        return_rate: Expected annual return.

    Returns:
        Required contribution rate (% of salary).
    """
    if fabs(salary) < 1e-30:
        return 0.0
    if fabs(return_rate) < 1e-30:
        var denom = salary * Float64(years)
        if fabs(denom) < 1e-30:
            return 0.0
        return target_fund / denom * 100.0
    var fv_factor = (_pow(1.0 + return_rate, years) - 1.0) / return_rate
    var denom = salary * fv_factor
    if fabs(denom) < 1e-30:
        return 0.0
    return target_fund / denom * 100.0


# ── inflation_adjusted_pension ───────────────────────────────────────────────


def inflation_adjusted_pension(
    nominal: Float64, inflation_rate: Float64, years: Int
) -> Float64:
    """Real pension: Real = nominal / (1+i)^n.

    Args:
        nominal: Nominal pension value.
        inflation_rate: Annual inflation rate (e.g. 0.03).
        years: Number of years.

    Returns:
        Inflation-adjusted (real) pension value.
    """
    var divisor = _pow(1.0 + inflation_rate, years)
    if fabs(divisor) < 1e-30:
        return 0.0
    return nominal / divisor


# ── pension_gap ──────────────────────────────────────────────────────────────


def pension_gap(
    required_income: Float64, expected_pension: Float64
) -> Float64:
    """Pension gap: Gap = required - expected.

    Args:
        required_income: Required annual retirement income.
        expected_pension: Expected annual pension income.

    Returns:
        Annual pension gap (positive = shortfall).
    """
    return required_income - expected_pension


# ── social_security_bend_points ──────────────────────────────────────────────


def social_security_bend_points(
    aime: Float64, bp1: Float64, bp2: Float64
) -> Float64:
    """Social Security PIA from AIME and bend points.

    PIA = 0.9*min(aime,bp1) + 0.32*max(0,min(aime,bp2)-bp1)
          + 0.15*max(0,aime-bp2)

    Args:
        aime: Average Indexed Monthly Earnings.
        bp1: First bend point.
        bp2: Second bend point.

    Returns:
        Primary Insurance Amount (monthly).
    """
    var part1 = aime
    if part1 > bp1:
        part1 = bp1
    var mid = aime
    if mid > bp2:
        mid = bp2
    var part2 = mid - bp1
    if part2 < 0.0:
        part2 = 0.0
    var part3 = aime - bp2
    if part3 < 0.0:
        part3 = 0.0
    return 0.9 * part1 + 0.32 * part2 + 0.15 * part3


# ── years_to_full_vesting ────────────────────────────────────────────────────


def years_to_full_vesting(
    service_years: Float64, vesting_schedule: Float64
) -> Float64:
    """Vested percentage: min(100, service/schedule*100).

    Args:
        service_years: Years of service.
        vesting_schedule: Years required for full vesting.

    Returns:
        Vested percentage (0-100).
    """
    if fabs(vesting_schedule) < 1e-30:
        return 100.0
    var pct = service_years / vesting_schedule * 100.0
    if pct > 100.0:
        pct = 100.0
    if pct < 0.0:
        pct = 0.0
    return pct


# ── withdrawal_rate ──────────────────────────────────────────────────────────


def withdrawal_rate(
    annual_withdrawal: Float64, portfolio_value: Float64
) -> Float64:
    """Withdrawal rate: WR = withdrawal / portfolio * 100.

    Args:
        annual_withdrawal: Annual withdrawal amount.
        portfolio_value: Total portfolio value.

    Returns:
        Withdrawal rate (%).
    """
    if fabs(portfolio_value) < 1e-30:
        return 0.0
    return annual_withdrawal / portfolio_value * 100.0
