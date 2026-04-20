"""test_procurement.mojo — auto-generated tests for procurement library."""
from std.math import isnan, isinf
from procurement import total_cost_of_ownership, price_variance, purchase_price_variance_pct, inventory_turnover, days_inventory_outstanding, economic_order_quantity, reorder_point, safety_stock, supplier_score_weighted, savings_percentage, maverick_spend_ratio, payment_discount_annualized

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_total_cost_of_ownership = total_cost_of_ownership(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_total_cost_of_ownership): passed += 1; print("  ✅ procurement::total_cost_of_ownership =", _v_total_cost_of_ownership)
    else: failed += 1; print("  ❌ procurement::total_cost_of_ownership → non-finite:", _v_total_cost_of_ownership)
    var _v_price_variance = price_variance(0.5, 0.5, 0.5)
    if is_finite(_v_price_variance): passed += 1; print("  ✅ procurement::price_variance =", _v_price_variance)
    else: failed += 1; print("  ❌ procurement::price_variance → non-finite:", _v_price_variance)
    var _v_purchase_price_variance_pct = purchase_price_variance_pct(0.5, 0.5)
    if is_finite(_v_purchase_price_variance_pct): passed += 1; print("  ✅ procurement::purchase_price_variance_pct =", _v_purchase_price_variance_pct)
    else: failed += 1; print("  ❌ procurement::purchase_price_variance_pct → non-finite:", _v_purchase_price_variance_pct)
    var _v_inventory_turnover = inventory_turnover(0.5, 0.5)
    if is_finite(_v_inventory_turnover): passed += 1; print("  ✅ procurement::inventory_turnover =", _v_inventory_turnover)
    else: failed += 1; print("  ❌ procurement::inventory_turnover → non-finite:", _v_inventory_turnover)
    var _v_days_inventory_outstanding = days_inventory_outstanding(0.5)
    if is_finite(_v_days_inventory_outstanding): passed += 1; print("  ✅ procurement::days_inventory_outstanding =", _v_days_inventory_outstanding)
    else: failed += 1; print("  ❌ procurement::days_inventory_outstanding → non-finite:", _v_days_inventory_outstanding)
    var _v_economic_order_quantity = economic_order_quantity(0.5, 0.5, 0.5)
    if is_finite(_v_economic_order_quantity): passed += 1; print("  ✅ procurement::economic_order_quantity =", _v_economic_order_quantity)
    else: failed += 1; print("  ❌ procurement::economic_order_quantity → non-finite:", _v_economic_order_quantity)
    var _v_reorder_point = reorder_point(0.5, 0.5, 0.5)
    if is_finite(_v_reorder_point): passed += 1; print("  ✅ procurement::reorder_point =", _v_reorder_point)
    else: failed += 1; print("  ❌ procurement::reorder_point → non-finite:", _v_reorder_point)
    var _v_safety_stock = safety_stock(0.5, 0.5, 0.5)
    if is_finite(_v_safety_stock): passed += 1; print("  ✅ procurement::safety_stock =", _v_safety_stock)
    else: failed += 1; print("  ❌ procurement::safety_stock → non-finite:", _v_safety_stock)
    var _v_supplier_score_weighted = supplier_score_weighted(0.5, 0.5)
    if is_finite(_v_supplier_score_weighted): passed += 1; print("  ✅ procurement::supplier_score_weighted =", _v_supplier_score_weighted)
    else: failed += 1; print("  ❌ procurement::supplier_score_weighted → non-finite:", _v_supplier_score_weighted)
    var _v_savings_percentage = savings_percentage(0.5, 0.5)
    if is_finite(_v_savings_percentage): passed += 1; print("  ✅ procurement::savings_percentage =", _v_savings_percentage)
    else: failed += 1; print("  ❌ procurement::savings_percentage → non-finite:", _v_savings_percentage)
    var _v_maverick_spend_ratio = maverick_spend_ratio(0.5, 0.5)
    if is_finite(_v_maverick_spend_ratio): passed += 1; print("  ✅ procurement::maverick_spend_ratio =", _v_maverick_spend_ratio)
    else: failed += 1; print("  ❌ procurement::maverick_spend_ratio → non-finite:", _v_maverick_spend_ratio)
    var _v_payment_discount_annualized = payment_discount_annualized(0.5, 0.5, 0.5)
    if is_finite(_v_payment_discount_annualized): passed += 1; print("  ✅ procurement::payment_discount_annualized =", _v_payment_discount_annualized)
    else: failed += 1; print("  ❌ procurement::payment_discount_annualized → non-finite:", _v_payment_discount_annualized)

    print("  [procurement] Passed:", passed, "Failed:", failed)
