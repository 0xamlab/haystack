"""
numismatics.mojo — Numismatics (Coin Collecting) Library.

Provides valuation, grading, scarcity, and investment calculations
for numismatic analysis.

Public API:
  melt_value               — MV = weight * price
  premium_over_melt        — Premium = (market-melt)/melt * 100
  grade_numeric_to_scale   — Returns Sheldon grade (0–70)
  population_scarcity      — Scarcity = certified/mintage * 100
  annual_return            — R = ((current/purchase)^(1/years) - 1) * 100
  insurance_value          — IV = price * factor
  mintage_per_capita       — MPC = mintage/pop
  survival_rate_estimate   — SR = surviving/original * 100
  price_trend              — Trend = (new-old)/old * 100
  auction_fee              — Fee = hammer * premium/100
  total_cost_acquisition   — Total = hammer*(1+premium/100)*(1+tax/100)
  bullion_content_troy_oz  — Content = weight*purity/31.1035
"""
from std.math import abs as fabs, pow, log


# ── melt_value ───────────────────────────────────────────────────────────────


def melt_value(
    metal_weight_oz: Float64, metal_price_per_oz: Float64
) -> Float64:
    """Melt value: MV = weight * price.

    Args:
        metal_weight_oz: Weight of metal content (troy oz).
        metal_price_per_oz: Spot price per troy oz.

    Returns:
        Melt value in currency.
    """
    return metal_weight_oz * metal_price_per_oz


# ── premium_over_melt ────────────────────────────────────────────────────────


def premium_over_melt(
    market_price: Float64, melt_val: Float64
) -> Float64:
    """Premium over melt: Premium = (market - melt) / melt * 100 (%).

    Args:
        market_price: Market/collector price.
        melt_val: Melt value.

    Returns:
        Premium percentage.
    """
    if fabs(melt_val) < 1e-30:
        return 0.0
    return (market_price - melt_val) / melt_val * 100.0


# ── grade_numeric_to_scale ───────────────────────────────────────────────────


def grade_numeric_to_scale(sheldon_grade: Float64) -> Float64:
    """Return Sheldon grade directly (0–70 scale).

    Args:
        sheldon_grade: Numeric Sheldon grade (0–70).

    Returns:
        The Sheldon grade value (identity, clamped 0–70).
    """
    if sheldon_grade < 0.0:
        return 0.0
    if sheldon_grade > 70.0:
        return 70.0
    return sheldon_grade


# ── population_scarcity ──────────────────────────────────────────────────────


def population_scarcity(
    certified_count: Float64, total_mintage: Float64
) -> Float64:
    """Population scarcity: Scarcity = certified / mintage * 100 (%).

    Args:
        certified_count: Number of certified coins.
        total_mintage: Original mintage.

    Returns:
        Scarcity percentage.
    """
    if fabs(total_mintage) < 1e-30:
        return 0.0
    return certified_count / total_mintage * 100.0


# ── annual_return ────────────────────────────────────────────────────────────


def annual_return(
    purchase_price: Float64, current_price: Float64, years: Float64
) -> Float64:
    """Annualized return: R = ((current/purchase)^(1/years) - 1) * 100.

    Args:
        purchase_price: Original purchase price.
        current_price: Current market price.
        years: Holding period (years).

    Returns:
        Annualized return (%).
    """
    if fabs(purchase_price) < 1e-30 or fabs(years) < 1e-30:
        return 0.0
    var ratio = current_price / purchase_price
    if ratio <= 0.0:
        return 0.0
    return (pow(ratio, 1.0 / years) - 1.0) * 100.0


# ── insurance_value ──────────────────────────────────────────────────────────


def insurance_value(
    market_price: Float64, coverage_factor: Float64
) -> Float64:
    """Insurance value: IV = price * factor.

    Args:
        market_price: Current market price.
        coverage_factor: Coverage multiplier (e.g. 1.1 for 110%).

    Returns:
        Insurance value.
    """
    return market_price * coverage_factor


# ── mintage_per_capita ───────────────────────────────────────────────────────


def mintage_per_capita(
    mintage: Float64, population: Float64
) -> Float64:
    """Mintage per capita: MPC = mintage / population.

    Args:
        mintage: Total mintage.
        population: Population at time of minting.

    Returns:
        Coins per person.
    """
    if fabs(population) < 1e-30:
        return 0.0
    return mintage / population


# ── survival_rate_estimate ───────────────────────────────────────────────────


def survival_rate_estimate(
    surviving: Float64, original_mintage: Float64
) -> Float64:
    """Survival rate: SR = surviving / original * 100 (%).

    Args:
        surviving: Estimated surviving coins.
        original_mintage: Original mintage.

    Returns:
        Survival rate percentage.
    """
    if fabs(original_mintage) < 1e-30:
        return 0.0
    return surviving / original_mintage * 100.0


# ── price_trend ──────────────────────────────────────────────────────────────


def price_trend(
    prices_avg_old: Float64, prices_avg_new: Float64
) -> Float64:
    """Price trend: Trend = (new - old) / old * 100 (%).

    Args:
        prices_avg_old: Average price in earlier period.
        prices_avg_new: Average price in later period.

    Returns:
        Price trend percentage (positive = appreciation).
    """
    if fabs(prices_avg_old) < 1e-30:
        return 0.0
    return (prices_avg_new - prices_avg_old) / prices_avg_old * 100.0


# ── auction_fee ──────────────────────────────────────────────────────────────


def auction_fee(
    hammer_price: Float64, buyer_premium_pct: Float64
) -> Float64:
    """Auction buyer's premium: Fee = hammer * premium / 100.

    Args:
        hammer_price: Hammer (winning bid) price.
        buyer_premium_pct: Buyer's premium percentage.

    Returns:
        Fee amount.
    """
    return hammer_price * buyer_premium_pct / 100.0


# ── total_cost_acquisition ───────────────────────────────────────────────────


def total_cost_acquisition(
    hammer: Float64, premium: Float64, tax_rate: Float64
) -> Float64:
    """Total acquisition cost: Total = hammer*(1+premium/100)*(1+tax/100).

    Args:
        hammer: Hammer price.
        premium: Buyer's premium (%).
        tax_rate: Sales tax rate (%).

    Returns:
        Total cost including premium and tax.
    """
    return hammer * (1.0 + premium / 100.0) * (1.0 + tax_rate / 100.0)


# ── bullion_content_troy_oz ──────────────────────────────────────────────────


def bullion_content_troy_oz(
    weight_grams: Float64, purity: Float64
) -> Float64:
    """Bullion content in troy ounces: Content = weight * purity / 31.1035.

    Args:
        weight_grams: Coin weight (grams).
        purity: Metal purity (0–1).

    Returns:
        Pure metal content (troy ounces).
    """
    return weight_grams * purity / 31.1035
