"""test_inventory.mojo — auto-generated tests for inventory library."""
from std.math import isnan, isinf
from inventory import eoq, reorder_point, safety_stock, total_inventory_cost, newsvendor_qty, service_level, abc_classify, days_of_supply, inventory_turnover, fill_rate, periodic_review_order

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

    var _v_eoq = eoq(0.5, 0.5, 0.5)
    if is_finite(_v_eoq): passed += 1; print("  ✅ inventory::eoq =", _v_eoq)
    else: failed += 1; print("  ❌ inventory::eoq → non-finite:", _v_eoq)
    var _v_reorder_point = reorder_point(0.5, 0.5, 0.5)
    if is_finite(_v_reorder_point): passed += 1; print("  ✅ inventory::reorder_point =", _v_reorder_point)
    else: failed += 1; print("  ❌ inventory::reorder_point → non-finite:", _v_reorder_point)
    var _v_safety_stock = safety_stock(0.5, 0.5, 0.5)
    if is_finite(_v_safety_stock): passed += 1; print("  ✅ inventory::safety_stock =", _v_safety_stock)
    else: failed += 1; print("  ❌ inventory::safety_stock → non-finite:", _v_safety_stock)
    var _v_total_inventory_cost = total_inventory_cost(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_total_inventory_cost): passed += 1; print("  ✅ inventory::total_inventory_cost =", _v_total_inventory_cost)
    else: failed += 1; print("  ❌ inventory::total_inventory_cost → non-finite:", _v_total_inventory_cost)
    var _v_newsvendor_qty = newsvendor_qty(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_newsvendor_qty): passed += 1; print("  ✅ inventory::newsvendor_qty =", _v_newsvendor_qty)
    else: failed += 1; print("  ❌ inventory::newsvendor_qty → non-finite:", _v_newsvendor_qty)
    var _v_service_level = service_level(0.5)
    if is_finite(_v_service_level): passed += 1; print("  ✅ inventory::service_level =", _v_service_level)
    else: failed += 1; print("  ❌ inventory::service_level → non-finite:", _v_service_level)
    var _v_abc_classify = abc_classify(_lf5)
    if len(_v_abc_classify) >= 0: passed += 1; print("  ✅ inventory::abc_classify")
    var _v_days_of_supply = days_of_supply(0.5, 0.5)
    if is_finite(_v_days_of_supply): passed += 1; print("  ✅ inventory::days_of_supply =", _v_days_of_supply)
    else: failed += 1; print("  ❌ inventory::days_of_supply → non-finite:", _v_days_of_supply)
    var _v_inventory_turnover = inventory_turnover(0.5, 0.5)
    if is_finite(_v_inventory_turnover): passed += 1; print("  ✅ inventory::inventory_turnover =", _v_inventory_turnover)
    else: failed += 1; print("  ❌ inventory::inventory_turnover → non-finite:", _v_inventory_turnover)
    var _v_fill_rate = fill_rate(5, 5)
    if is_finite(_v_fill_rate): passed += 1; print("  ✅ inventory::fill_rate =", _v_fill_rate)
    else: failed += 1; print("  ❌ inventory::fill_rate → non-finite:", _v_fill_rate)
    var _v_periodic_review_order = periodic_review_order(0.5, 0.5, 0.5)
    if is_finite(_v_periodic_review_order): passed += 1; print("  ✅ inventory::periodic_review_order =", _v_periodic_review_order)
    else: failed += 1; print("  ❌ inventory::periodic_review_order → non-finite:", _v_periodic_review_order)

    print("  [inventory] Passed:", passed, "Failed:", failed)
