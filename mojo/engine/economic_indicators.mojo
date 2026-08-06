"""
economic_indicators.mojo — Economic indicator calculations. Pure Mojo, zero Python imports.

Public API:
  gdp_growth, inflation_rate, unemployment_rate, real_gdp, gini_coefficient,
  phillips_curve, okuns_law, velocity_of_money, fisher_equation,
  trade_balance, gdp_per_capita, purchasing_power_parity
"""
from std.math import abs as fabs


# ── GDP Growth ────────────────────────────────────────────────────────────────


def gdp_growth(gdp_current: Float64, gdp_previous: Float64) -> Float64:
    """GDP growth rate = (current - previous) / previous."""
    if fabs(gdp_previous) < 1e-15:
        return 0.0
    return (gdp_current - gdp_previous) / gdp_previous


# ── Inflation Rate ────────────────────────────────────────────────────────────


def inflation_rate(cpi_current: Float64, cpi_previous: Float64) -> Float64:
    """Inflation rate = (CPI_current - CPI_previous) / CPI_previous."""
    if fabs(cpi_previous) < 1e-15:
        return 0.0
    return (cpi_current - cpi_previous) / cpi_previous


# ── Unemployment Rate ─────────────────────────────────────────────────────────


def unemployment_rate(unemployed: Float64, labor_force: Float64) -> Float64:
    """Unemployment rate = unemployed / labor_force."""
    if fabs(labor_force) < 1e-15:
        return 0.0
    return unemployed / labor_force


# ── Real GDP ──────────────────────────────────────────────────────────────────


def real_gdp(nominal_gdp: Float64, gdp_deflator: Float64) -> Float64:
    """Real GDP = (nominal_gdp / gdp_deflator) * 100."""
    if fabs(gdp_deflator) < 1e-15:
        return 0.0
    return (nominal_gdp / gdp_deflator) * 100.0


# ── Gini Coefficient ─────────────────────────────────────────────────────────


def gini_coefficient(incomes: List[Float64]) -> Float64:
    """Gini coefficient from income distribution.
    G = (Σ_i Σ_j |y_i - y_j|) / (2 * n * Σ y_i).
    Returns 0 for empty or all-zero incomes."""
    var n = len(incomes)
    if n <= 1:
        return 0.0

    # Sort a copy (simple insertion sort for correctness)
    var sorted = List[Float64]()
    for i in range(n):
        sorted.append(incomes[i])
    for i in range(1, n):
        var key = sorted[i]
        var j = i - 1
        while j >= 0 and sorted[j] > key:
            sorted[j + 1] = sorted[j]
            j -= 1
        sorted[j + 1] = key

    var total_sum: Float64 = 0.0
    for i in range(n):
        total_sum += sorted[i]

    if fabs(total_sum) < 1e-15:
        return 0.0

    # Using the sorted formula: G = (2·Σ(i·y_i) - (n+1)·Σ(y_i)) / (n·Σ(y_i))
    var weighted_sum: Float64 = 0.0
    for i in range(n):
        weighted_sum += Float64(i + 1) * sorted[i]

    var gini = (2.0 * weighted_sum - Float64(n + 1) * total_sum) / (
        Float64(n) * total_sum
    )
    return gini


# ── Phillips Curve ────────────────────────────────────────────────────────────


def phillips_curve(
    unemployment: Float64, natural_rate: Float64, sensitivity: Float64
) -> Float64:
    """Phillips curve: inflation = sensitivity * (natural_rate - unemployment)."""
    return sensitivity * (natural_rate - unemployment)


# ── Okun's Law ────────────────────────────────────────────────────────────────


def okuns_law(
    gdp_gap: Float64, okun_coefficient: Float64 = 2.0
) -> Float64:
    """Okun's law: unemployment_gap = gdp_gap / okun_coefficient."""
    if fabs(okun_coefficient) < 1e-15:
        return 0.0
    return gdp_gap / okun_coefficient


# ── Velocity of Money ─────────────────────────────────────────────────────────


def velocity_of_money(
    nominal_gdp: Float64, money_supply: Float64
) -> Float64:
    """Velocity of money: V = GDP / M."""
    if fabs(money_supply) < 1e-15:
        return 0.0
    return nominal_gdp / money_supply


# ── Fisher Equation ───────────────────────────────────────────────────────────


def fisher_equation(nominal_rate: Float64, inflation: Float64) -> Float64:
    """Fisher equation: real_rate ≈ nominal_rate - inflation."""
    return nominal_rate - inflation


# ── Trade Balance ─────────────────────────────────────────────────────────────


def trade_balance(exports: Float64, imports: Float64) -> Float64:
    """Trade balance = exports - imports."""
    return exports - imports


# ── GDP Per Capita ────────────────────────────────────────────────────────────


def gdp_per_capita(gdp: Float64, population: Float64) -> Float64:
    """GDP per capita = GDP / population."""
    if fabs(population) < 1e-15:
        return 0.0
    return gdp / population


# ── Purchasing Power Parity ───────────────────────────────────────────────────


def purchasing_power_parity(
    price_domestic: Float64, price_foreign: Float64
) -> Float64:
    """PPP exchange rate = P_domestic / P_foreign."""
    if fabs(price_foreign) < 1e-15:
        return 0.0
    return price_domestic / price_foreign
