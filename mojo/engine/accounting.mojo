"""
accounting.mojo — Accounting & bookkeeping utilities. Zero Python imports.

Replaces custom accounting code with pure Mojo implementations for
depreciation, financial ratios, break-even analysis, and growth metrics.

Public API:
  straight_line_depreciation, declining_balance, sum_of_years_digits,
  future_value, present_value_single, gross_profit_margin,
  net_profit_margin, current_ratio, debt_to_equity, return_on_equity,
  break_even_units, compound_annual_growth
"""
from std.math import pow


# ── Depreciation Methods ─────────────────────────────────────────────────────


def straight_line_depreciation(
    cost: Float64, salvage: Float64, useful_life: Int
) -> Float64:
    """Annual depreciation: (cost - salvage) / useful_life."""
    if useful_life <= 0:
        return 0.0
    return (cost - salvage) / Float64(useful_life)


def declining_balance(cost: Float64, rate: Float64, year: Int) -> Float64:
    """Book value after year: cost * (1 - rate)^year."""
    if year < 0:
        return cost
    return cost * pow(1.0 - rate, Float64(year))


def sum_of_years_digits(
    cost: Float64, salvage: Float64, useful_life: Int, year: Int
) -> Float64:
    """Sum-of-years-digits depreciation for a given year (1-indexed).
    Depreciation_year = (cost - salvage) * remaining_life / SYD
    where SYD = n*(n+1)/2 and remaining_life = n - year + 1."""
    if useful_life <= 0 or year <= 0 or year > useful_life:
        return 0.0
    var n = Float64(useful_life)
    var syd = n * (n + 1.0) / 2.0
    var remaining = n - Float64(year) + 1.0
    return (cost - salvage) * remaining / syd


# ── Time Value of Money ──────────────────────────────────────────────────────


def future_value(pv: Float64, rate: Float64, periods: Int) -> Float64:
    """Future value: PV * (1 + rate)^periods."""
    return pv * pow(1.0 + rate, Float64(periods))


def present_value_single(fv: Float64, rate: Float64, periods: Int) -> Float64:
    """Present value of a single future amount: FV / (1 + rate)^periods."""
    return fv / pow(1.0 + rate, Float64(periods))


# ── Profitability Ratios ─────────────────────────────────────────────────────


def gross_profit_margin(revenue: Float64, cogs: Float64) -> Float64:
    """Gross profit margin: (revenue - COGS) / revenue."""
    if revenue == 0.0:
        return 0.0
    return (revenue - cogs) / revenue


def net_profit_margin(net_income: Float64, revenue: Float64) -> Float64:
    """Net profit margin: net_income / revenue."""
    if revenue == 0.0:
        return 0.0
    return net_income / revenue


# ── Liquidity & Leverage Ratios ──────────────────────────────────────────────


def current_ratio(
    current_assets: Float64, current_liabilities: Float64
) -> Float64:
    """Current ratio: current_assets / current_liabilities."""
    if current_liabilities == 0.0:
        return 0.0
    return current_assets / current_liabilities


def debt_to_equity(total_debt: Float64, total_equity: Float64) -> Float64:
    """Debt-to-equity ratio: total_debt / total_equity."""
    if total_equity == 0.0:
        return 0.0
    return total_debt / total_equity


# ── Return Ratios ────────────────────────────────────────────────────────────


def return_on_equity(net_income: Float64, equity: Float64) -> Float64:
    """Return on equity: net_income / equity."""
    if equity == 0.0:
        return 0.0
    return net_income / equity


# ── Break-Even Analysis ──────────────────────────────────────────────────────


def break_even_units(
    fixed_costs: Float64, price: Float64, variable_cost: Float64
) -> Float64:
    """Break-even units: fixed_costs / (price - variable_cost)."""
    var margin = price - variable_cost
    if margin == 0.0:
        return 0.0
    return fixed_costs / margin


# ── Growth Metrics ───────────────────────────────────────────────────────────


def compound_annual_growth(
    beginning: Float64, ending: Float64, years: Int
) -> Float64:
    """Compound annual growth rate: (ending/beginning)^(1/years) - 1."""
    if beginning == 0.0 or years <= 0:
        return 0.0
    return pow(ending / beginning, 1.0 / Float64(years)) - 1.0
