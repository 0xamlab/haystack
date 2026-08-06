"""
finance.mojo — Financial mathematics. Zero Python imports.
Critical for the decision engine's finance/insurance use cases.

Public API:
  npv, irr, payback_period, roi, compound_interest,
  present_value, future_value, annuity_payment,
  sharpe_ratio, max_drawdown, cagr, wacc
"""
from std.math import sqrt, abs as fabs, pow, log


# ── Net Present Value ─────────────────────────────────────────────────────────


def npv(rate: Float64, cashflows: List[Float64]) -> Float64:
    """Net Present Value: sum of cashflows[t] / (1+rate)^t for t=0..n-1."""
    var total: Float64 = 0.0
    var n = len(cashflows)
    for t in range(n):
        var discount = pow(1.0 + rate, Float64(t))
        total += cashflows[t] / discount
    return total


# ── Internal Rate of Return ───────────────────────────────────────────────────


def _npv_derivative(rate: Float64, cashflows: List[Float64]) -> Float64:
    """Derivative of NPV w.r.t. rate: sum of -t * cashflows[t] / (1+rate)^(t+1)."""
    var total: Float64 = 0.0
    var n = len(cashflows)
    for t in range(1, n):
        var discount = pow(1.0 + rate, Float64(t + 1))
        total += -Float64(t) * cashflows[t] / discount
    return total


def irr(
    cashflows: List[Float64],
    guess: Float64 = 0.1,
    tol: Float64 = 1e-6,
    max_iter: Int = 100,
) -> Float64:
    """Internal Rate of Return via Newton's method.
    Finds rate r such that NPV(r, cashflows) ≈ 0."""
    var r = guess
    for _ in range(max_iter):
        var f = npv(r, cashflows)
        var df = _npv_derivative(r, cashflows)
        if fabs(df) < 1e-15:
            break
        var r_new = r - f / df
        if fabs(r_new - r) < tol:
            return r_new
        r = r_new
    return r


# ── Payback Period ────────────────────────────────────────────────────────────


def payback_period(cashflows: List[Float64]) -> Float64:
    """Time (in periods) to recover the initial investment.
    Returns -1.0 if investment is never recovered.
    Uses linear interpolation within the recovery period."""
    var n = len(cashflows)
    if n == 0:
        return -1.0
    var cumulative: Float64 = 0.0
    for t in range(n):
        cumulative += cashflows[t]
        if cumulative >= 0.0 and t > 0:
            # Linear interpolation: how far into this period did we break even?
            var prev = cumulative - cashflows[t]
            var frac = -prev / cashflows[t] if cashflows[t] != 0.0 else 0.0
            return Float64(t - 1) + frac
    return -1.0


# ── Return on Investment ──────────────────────────────────────────────────────


def roi(gain: Float64, cost: Float64) -> Float64:
    """Return on Investment: (gain - cost) / cost."""
    if fabs(cost) < 1e-15:
        return 0.0
    return (gain - cost) / cost


# ── Compound Interest ─────────────────────────────────────────────────────────


def compound_interest(principal: Float64, rate: Float64, periods: Int) -> Float64:
    """Future value with compound interest: P * (1 + r)^n."""
    return principal * pow(1.0 + rate, Float64(periods))


# ── Present Value ─────────────────────────────────────────────────────────────


def present_value(future_value: Float64, rate: Float64, periods: Int) -> Float64:
    """Present value of a future amount: FV / (1 + r)^n."""
    return future_value / pow(1.0 + rate, Float64(periods))


# ── Future Value ──────────────────────────────────────────────────────────────


def future_value(present_val: Float64, rate: Float64, periods: Int) -> Float64:
    """Future value of a present amount: PV * (1 + r)^n."""
    return present_val * pow(1.0 + rate, Float64(periods))


# ── Annuity Payment (PMT) ────────────────────────────────────────────────────


def annuity_payment(principal: Float64, rate: Float64, periods: Int) -> Float64:
    """PMT — periodic payment for an ordinary annuity.
    PMT = P * r / (1 - (1+r)^-n).
    If rate is 0, returns P / n."""
    if fabs(rate) < 1e-15:
        if periods == 0:
            return 0.0
        return principal / Float64(periods)
    var factor = pow(1.0 + rate, Float64(periods))
    return principal * rate * factor / (factor - 1.0)


# ── Sharpe Ratio ──────────────────────────────────────────────────────────────


def sharpe_ratio(returns: List[Float64], risk_free_rate: Float64) -> Float64:
    """Sharpe ratio: (mean_return - risk_free_rate) / std_dev(returns).
    Returns 0.0 if there are fewer than 2 returns or zero std dev."""
    var n = len(returns)
    if n < 2:
        return 0.0
    # Mean
    var sum_r: Float64 = 0.0
    for i in range(n):
        sum_r += returns[i]
    var mean = sum_r / Float64(n)
    # Standard deviation (population)
    var sum_sq: Float64 = 0.0
    for i in range(n):
        var diff = returns[i] - mean
        sum_sq += diff * diff
    var std_dev = sqrt(sum_sq / Float64(n))
    if std_dev < 1e-15:
        return 0.0
    return (mean - risk_free_rate) / std_dev


# ── Max Drawdown ──────────────────────────────────────────────────────────────


def max_drawdown(values: List[Float64]) -> Float64:
    """Maximum drawdown: largest peak-to-trough decline as a fraction.
    Returns 0.0 if fewer than 2 values or no decline."""
    var n = len(values)
    if n < 2:
        return 0.0
    var peak = values[0]
    var max_dd: Float64 = 0.0
    for i in range(1, n):
        if values[i] > peak:
            peak = values[i]
        var dd = (peak - values[i]) / peak if peak > 0.0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ── CAGR (Compound Annual Growth Rate) ───────────────────────────────────────


def cagr(start_value: Float64, end_value: Float64, years: Float64) -> Float64:
    """Compound Annual Growth Rate: (end/start)^(1/years) - 1.
    Returns 0.0 if start_value is zero or years is zero."""
    if fabs(start_value) < 1e-15 or fabs(years) < 1e-15:
        return 0.0
    return pow(end_value / start_value, 1.0 / years) - 1.0


# ── WACC (Weighted Average Cost of Capital) ───────────────────────────────────


def wacc(
    equity: Float64,
    debt: Float64,
    cost_equity: Float64,
    cost_debt: Float64,
    tax_rate: Float64,
) -> Float64:
    """Weighted Average Cost of Capital.
    WACC = (E/(E+D)) * Re + (D/(E+D)) * Rd * (1 - T)."""
    var total = equity + debt
    if fabs(total) < 1e-15:
        return 0.0
    var e_weight = equity / total
    var d_weight = debt / total
    return e_weight * cost_equity + d_weight * cost_debt * (1.0 - tax_rate)
