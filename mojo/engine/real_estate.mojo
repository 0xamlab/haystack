"""
real_estate.mojo — Real estate analysis equations. Zero Python imports.

Pure Mojo implementations of common real-estate investment metrics
including cap rate, GRM, cash-on-cash, DSCR, LTV, NOI, mortgage
payment, price per sqft, break-even ratio, IRR, equity, and
appreciation.

Public API:
  cap_rate                     — NOI / Value * 100
  gross_rent_multiplier        — Price / Rent
  cash_on_cash_return          — CF / Invested * 100
  debt_service_coverage        — NOI / ADS
  loan_to_value                — Loan / Value * 100
  net_operating_income         — GI*(1-VR) - OE
  mortgage_payment             — PMT formula
  price_per_sqft               — Price / SqFt
  break_even_ratio             — (OE+DS)/GI * 100
  internal_rate_of_return_approx — simplified IRR
  equity_buildup               — Original - Remaining
  appreciation_value           — PV * (1+r)^n
"""
from std.math import exp, log, abs as fabs


# ── cap_rate ─────────────────────────────────────────────────────────────────


fn cap_rate(noi: Float64, property_value: Float64) -> Float64:
    """Capitalisation rate: Cap = NOI / Value * 100.

    Args:
        noi:            Net operating income ($).
        property_value: Current market value ($).

    Returns:
        Cap rate (%).
    """
    if fabs(property_value) < 1e-30:
        return 0.0
    return noi / property_value * 100.0


# ── gross_rent_multiplier ────────────────────────────────────────────────────


fn gross_rent_multiplier(price: Float64, annual_rent: Float64) -> Float64:
    """Gross rent multiplier: GRM = Price / Annual Rent.

    Args:
        price:       Purchase price ($).
        annual_rent: Gross annual rent ($).

    Returns:
        GRM (dimensionless).
    """
    if fabs(annual_rent) < 1e-30:
        return 0.0
    return price / annual_rent


# ── cash_on_cash_return ──────────────────────────────────────────────────────


fn cash_on_cash_return(
    annual_cashflow: Float64, total_invested: Float64,
) -> Float64:
    """Cash-on-cash return: CoC = CF / Invested * 100.

    Args:
        annual_cashflow: Annual pre-tax cash flow ($).
        total_invested:  Total cash invested ($).

    Returns:
        Cash-on-cash return (%).
    """
    if fabs(total_invested) < 1e-30:
        return 0.0
    return annual_cashflow / total_invested * 100.0


# ── debt_service_coverage ────────────────────────────────────────────────────


fn debt_service_coverage(
    noi: Float64, annual_debt_service: Float64,
) -> Float64:
    """Debt service coverage ratio: DSCR = NOI / ADS.

    Args:
        noi:                 Net operating income ($).
        annual_debt_service: Annual debt service ($).

    Returns:
        DSCR (dimensionless).
    """
    if fabs(annual_debt_service) < 1e-30:
        return 0.0
    return noi / annual_debt_service


# ── loan_to_value ────────────────────────────────────────────────────────────


fn loan_to_value(loan_amount: Float64, property_value: Float64) -> Float64:
    """Loan-to-value ratio: LTV = Loan / Value * 100.

    Args:
        loan_amount:    Loan principal ($).
        property_value: Appraised value ($).

    Returns:
        LTV (%).
    """
    if fabs(property_value) < 1e-30:
        return 0.0
    return loan_amount / property_value * 100.0


# ── net_operating_income ─────────────────────────────────────────────────────


fn net_operating_income(
    gross_income: Float64, vacancy_rate: Float64,
    operating_expenses: Float64,
) -> Float64:
    """Net operating income: NOI = GI*(1-VR) - OE.

    Args:
        gross_income:       Potential gross income ($).
        vacancy_rate:       Vacancy & credit loss rate (0..1).
        operating_expenses: Total operating expenses ($).

    Returns:
        NOI ($).
    """
    return gross_income * (1.0 - vacancy_rate) - operating_expenses


# ── mortgage_payment ─────────────────────────────────────────────────────────


fn mortgage_payment(
    principal: Float64, monthly_rate: Float64, n_months: Int,
) -> Float64:
    """Fixed-rate mortgage payment: PMT = P*r*(1+r)^n / ((1+r)^n - 1).

    Args:
        principal:    Loan principal ($).
        monthly_rate: Monthly interest rate (decimal).
        n_months:     Total number of payments.

    Returns:
        Monthly payment ($).
    """
    if monthly_rate <= 0.0 or n_months <= 0:
        if n_months > 0:
            return principal / Float64(n_months)
        return 0.0
    var rn = exp(Float64(n_months) * log(1.0 + monthly_rate))
    return principal * monthly_rate * rn / (rn - 1.0)


# ── price_per_sqft ───────────────────────────────────────────────────────────


fn price_per_sqft(price: Float64, sqft: Float64) -> Float64:
    """Price per square foot: PPSF = Price / SqFt.

    Args:
        price: Total price ($).
        sqft:  Area (sq ft).

    Returns:
        Price per sq ft ($/sqft).
    """
    if fabs(sqft) < 1e-30:
        return 0.0
    return price / sqft


# ── break_even_ratio ─────────────────────────────────────────────────────────


fn break_even_ratio(
    operating_expenses: Float64, debt_service: Float64,
    gross_income: Float64,
) -> Float64:
    """Break-even ratio: BER = (OE + DS) / GI * 100.

    Args:
        operating_expenses: Annual operating expenses ($).
        debt_service:       Annual debt service ($).
        gross_income:       Gross income ($).

    Returns:
        Break-even ratio (%).
    """
    if fabs(gross_income) < 1e-30:
        return 0.0
    return (operating_expenses + debt_service) / gross_income * 100.0


# ── internal_rate_of_return_approx ───────────────────────────────────────────


fn internal_rate_of_return_approx(
    initial: Float64, cashflow: Float64, years: Int,
) -> Float64:
    """Simplified IRR: IRR ≈ (cashflow/initial)^(1/years) - 1.

    Args:
        initial:  Initial investment ($).
        cashflow: Total exit value / terminal cashflow ($).
        years:    Holding period (years).

    Returns:
        Approximate IRR (decimal).
    """
    if fabs(initial) < 1e-30 or years <= 0:
        return 0.0
    var ratio = cashflow / initial
    if ratio <= 0.0:
        return 0.0
    return exp((1.0 / Float64(years)) * log(ratio)) - 1.0


# ── equity_buildup ───────────────────────────────────────────────────────────


fn equity_buildup(
    original_loan: Float64, remaining_loan: Float64,
) -> Float64:
    """Equity build-up from amortisation: Equity = Original - Remaining.

    Args:
        original_loan:  Original loan balance ($).
        remaining_loan: Current remaining balance ($).

    Returns:
        Equity built ($).
    """
    return original_loan - remaining_loan


# ── appreciation_value ───────────────────────────────────────────────────────


fn appreciation_value(
    initial_value: Float64, annual_rate: Float64, years: Int,
) -> Float64:
    """Future value via appreciation: FV = PV * (1+r)^n.

    Args:
        initial_value: Present value ($).
        annual_rate:   Annual appreciation rate (decimal).
        years:         Number of years.

    Returns:
        Future value ($).
    """
    if years <= 0:
        return initial_value
    return initial_value * exp(Float64(years) * log(1.0 + annual_rate))
