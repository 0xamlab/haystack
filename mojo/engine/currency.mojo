"""
currency.mojo — Currency Math. Zero Python imports.

Replaces forex-python/custom finance with pure Mojo implementations of
compound interest, continuous compounding, amortization, present/future value,
annuities, effective annual rate, discount factor, and rule of 72.

Public API:
  round_currency          — Round to specified decimal places
  compound_interest       — FV = P * (1 + r)^n
  continuous_compound     — FV = P * e^(rt)
  amortization_payment    — Monthly payment for amortizing loan
  amortization_schedule   — Full amortization schedule
  present_value           — PV = FV / (1+r)^n
  present_value_annuity   — PV of annuity
  future_value_annuity    — FV of annuity
  effective_annual_rate   — EAR = (1 + r/n)^n - 1
  discount_factor         — DF = 1 / (1+r)^n
  rule_of_72              — Approximate doubling time
  loan_balance_after      — Remaining balance after k payments
"""

from std.math import exp, pow, floor, abs as fabs


# ── round_currency ───────────────────────────────────────────────────────────


def round_currency(amount: Float64, decimals: Int = 2) -> Float64:
    """Round to specified decimal places (banker's rounding)."""
    var mult: Float64 = 1.0
    for _ in range(decimals):
        mult *= 10.0
    var shifted = amount * mult
    # Standard rounding: floor(x + 0.5)
    var rounded = floor(shifted + 0.5)
    return rounded / mult


# ── compound_interest ────────────────────────────────────────────────────────


def compound_interest(principal: Float64, rate: Float64, periods: Int) -> Float64:
    """FV = P * (1 + r)^n."""
    return principal * pow(1.0 + rate, Float64(periods))


# ── continuous_compound ──────────────────────────────────────────────────────


def continuous_compound(principal: Float64, rate: Float64, time: Float64) -> Float64:
    """FV = P * e^(rt)."""
    return principal * exp(rate * time)


# ── amortization_payment ─────────────────────────────────────────────────────


def amortization_payment(principal: Float64, rate: Float64, periods: Int) -> Float64:
    """Monthly payment: P * r / (1 - (1+r)^-n).
    If rate is 0, returns principal / periods."""
    if rate == 0.0:
        return principal / Float64(periods)
    var factor = pow(1.0 + rate, Float64(periods))
    return principal * rate * factor / (factor - 1.0)


# ── amortization_schedule ────────────────────────────────────────────────────


def amortization_schedule(
    principal: Float64, rate: Float64, periods: Int,
) -> List[List[Float64]]:
    """Full schedule: [[payment, interest, principal_portion, remaining], ...]."""
    var pmt = amortization_payment(principal, rate, periods)
    var balance = principal
    var result = List[List[Float64]]()

    for _ in range(periods):
        var interest = balance * rate
        var princ_portion = pmt - interest
        balance -= princ_portion
        if fabs(balance) < 1e-6:
            balance = 0.0
        var row = List[Float64]()
        row.append(pmt)
        row.append(interest)
        row.append(princ_portion)
        row.append(balance)
        result.append(row^)
    return result^


# ── present_value ────────────────────────────────────────────────────────────


def present_value(future_value: Float64, rate: Float64, periods: Int) -> Float64:
    """PV = FV / (1+r)^n."""
    return future_value / pow(1.0 + rate, Float64(periods))


# ── present_value_annuity ────────────────────────────────────────────────────


def present_value_annuity(payment: Float64, rate: Float64, periods: Int) -> Float64:
    """PV of annuity: PMT * (1 - (1+r)^-n) / r."""
    if rate == 0.0:
        return payment * Float64(periods)
    var factor = pow(1.0 + rate, Float64(periods))
    return payment * (1.0 - 1.0 / factor) / rate


# ── future_value_annuity ────────────────────────────────────────────────────


def future_value_annuity(payment: Float64, rate: Float64, periods: Int) -> Float64:
    """FV of annuity: PMT * ((1+r)^n - 1) / r."""
    if rate == 0.0:
        return payment * Float64(periods)
    var factor = pow(1.0 + rate, Float64(periods))
    return payment * (factor - 1.0) / rate


# ── effective_annual_rate ────────────────────────────────────────────────────


def effective_annual_rate(nominal_rate: Float64, compounding_periods: Int) -> Float64:
    """EAR = (1 + r/n)^n - 1."""
    var n = Float64(compounding_periods)
    return pow(1.0 + nominal_rate / n, n) - 1.0


# ── discount_factor ──────────────────────────────────────────────────────────


def discount_factor(rate: Float64, periods: Int) -> Float64:
    """DF = 1 / (1+r)^n."""
    return 1.0 / pow(1.0 + rate, Float64(periods))


# ── rule_of_72 ───────────────────────────────────────────────────────────────


def rule_of_72(rate: Float64) -> Float64:
    """Approximate doubling time: 72 / (rate * 100)."""
    if rate <= 0.0:
        return 1e30
    return 72.0 / (rate * 100.0)


# ── loan_balance_after ───────────────────────────────────────────────────────


def loan_balance_after(
    principal: Float64, rate: Float64, periods: Int, payments_made: Int,
) -> Float64:
    """Remaining balance after k payments.
    B_k = P*(1+r)^k - PMT*((1+r)^k - 1)/r."""
    if rate == 0.0:
        var pmt = principal / Float64(periods)
        var bal = principal - pmt * Float64(payments_made)
        if fabs(bal) < 1e-6:
            bal = 0.0
        return bal
    var pmt = amortization_payment(principal, rate, periods)
    var factor = pow(1.0 + rate, Float64(payments_made))
    var balance = principal * factor - pmt * (factor - 1.0) / rate
    if fabs(balance) < 1e-6:
        balance = 0.0
    return balance
