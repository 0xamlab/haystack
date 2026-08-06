"""
procurement.mojo — Procurement & Supply Management Library. Zero Python imports.

Pure Mojo implementations of fundamental procurement and supply chain
management calculations including TCO, price variance, inventory
turnover, EOQ, reorder points, safety stock, and supplier scoring.

Public API:
  total_cost_of_ownership        — TCO = P+O+M+D
  price_variance                 — PV = (AP-SP)*Q
  purchase_price_variance_pct    — PPV% = (actual-standard)/standard*100
  inventory_turnover             — IT = COGS/AvgInv
  days_inventory_outstanding     — DIO = 365/IT
  economic_order_quantity        — EOQ = sqrt(2*D*S/H)
  reorder_point                  — ROP = d*LT + SS
  safety_stock                   — SS = z * σ_d * sqrt(LT)
  supplier_score_weighted        — Score = Σ(s*w)/Σ(w)
  savings_percentage             — Savings = (old-new)/old * 100
  maverick_spend_ratio           — MSR = off_contract/total * 100
  payment_discount_annualized    — APR approximation for early pay
"""
from std.math import sqrt, abs as fabs


# ── total_cost_of_ownership ──────────────────────────────────────────────────


def total_cost_of_ownership(
    purchase: Float64, operating: Float64, maintenance: Float64, disposal: Float64
) -> Float64:
    """TCO = purchase + operating + maintenance + disposal."""
    return purchase + operating + maintenance + disposal


# ── price_variance ───────────────────────────────────────────────────────────


def price_variance(
    actual_price: Float64, standard_price: Float64, quantity: Float64
) -> Float64:
    """PV = (actual_price - standard_price) * quantity."""
    return (actual_price - standard_price) * quantity


# ── purchase_price_variance_pct ──────────────────────────────────────────────


def purchase_price_variance_pct(actual: Float64, standard: Float64) -> Float64:
    """PPV% = (actual - standard) / standard * 100."""
    if standard == 0.0:
        return 0.0
    return (actual - standard) / standard * 100.0


# ── inventory_turnover ───────────────────────────────────────────────────────


def inventory_turnover(cogs: Float64, avg_inventory: Float64) -> Float64:
    """IT = COGS / average_inventory."""
    if avg_inventory == 0.0:
        return 0.0
    return cogs / avg_inventory


# ── days_inventory_outstanding ───────────────────────────────────────────────


def days_inventory_outstanding(inventory_turnover_val: Float64) -> Float64:
    """DIO = 365 / inventory_turnover."""
    if inventory_turnover_val == 0.0:
        return 0.0
    return 365.0 / inventory_turnover_val


# ── economic_order_quantity ──────────────────────────────────────────────────


def economic_order_quantity(
    demand: Float64, ordering_cost: Float64, holding_cost: Float64
) -> Float64:
    """EOQ = sqrt(2 * D * S / H)."""
    if holding_cost == 0.0:
        return 0.0
    return sqrt(2.0 * demand * ordering_cost / holding_cost)


# ── reorder_point ────────────────────────────────────────────────────────────


def reorder_point(
    daily_demand: Float64, lead_time: Float64, safety_stock_val: Float64
) -> Float64:
    """ROP = daily_demand * lead_time + safety_stock."""
    return daily_demand * lead_time + safety_stock_val


# ── safety_stock ─────────────────────────────────────────────────────────────


def safety_stock(
    z_score: Float64, demand_std: Float64, lead_time: Float64
) -> Float64:
    """SS = z_score * demand_std * sqrt(lead_time)."""
    return z_score * demand_std * sqrt(lead_time)


# ── supplier_score_weighted ──────────────────────────────────────────────────


def supplier_score_weighted(scores_sum: Float64, weights_sum: Float64) -> Float64:
    """Weighted score = sum(scores*weights) / sum(weights)."""
    if weights_sum == 0.0:
        return 0.0
    return scores_sum / weights_sum


# ── savings_percentage ───────────────────────────────────────────────────────


def savings_percentage(old_price: Float64, new_price: Float64) -> Float64:
    """Savings% = (old - new) / old * 100."""
    if old_price == 0.0:
        return 0.0
    return (old_price - new_price) / old_price * 100.0


# ── maverick_spend_ratio ─────────────────────────────────────────────────────


def maverick_spend_ratio(off_contract: Float64, total_spend: Float64) -> Float64:
    """MSR = off_contract / total_spend * 100."""
    if total_spend == 0.0:
        return 0.0
    return off_contract / total_spend * 100.0


# ── payment_discount_annualized ──────────────────────────────────────────────


def payment_discount_annualized(
    discount_pct: Float64, full_days: Float64, discount_days: Float64
) -> Float64:
    """APR ≈ (discount/(1-discount)) * (365/(full_days-discount_days)).
    discount_pct is in percentage (e.g. 2 for 2%)."""
    var d = discount_pct / 100.0
    var day_diff = full_days - discount_days
    if day_diff == 0.0 or d >= 1.0:
        return 0.0
    return (d / (1.0 - d)) * (365.0 / day_diff) * 100.0
