"""test_finance.mojo — auto-generated tests for finance library."""
from std.math import isnan, isinf
from finance import npv, irr, payback_period, roi, compound_interest, present_value, future_value, annuity_payment, sharpe_ratio, max_drawdown, cagr, wacc

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

    var _v_npv = npv(0.5, _lf5)
    if is_finite(_v_npv): passed += 1; print("  ✅ finance::npv =", _v_npv)
    else: failed += 1; print("  ❌ finance::npv → non-finite:", _v_npv)
    var _v_irr = irr(_lf5, 0.5, 0.5, 5)
    if is_finite(_v_irr): passed += 1; print("  ✅ finance::irr =", _v_irr)
    else: failed += 1; print("  ❌ finance::irr → non-finite:", _v_irr)
    var _v_payback_period = payback_period(_lf5)
    if is_finite(_v_payback_period): passed += 1; print("  ✅ finance::payback_period =", _v_payback_period)
    else: failed += 1; print("  ❌ finance::payback_period → non-finite:", _v_payback_period)
    var _v_roi = roi(0.5, 0.5)
    if is_finite(_v_roi): passed += 1; print("  ✅ finance::roi =", _v_roi)
    else: failed += 1; print("  ❌ finance::roi → non-finite:", _v_roi)
    var _v_compound_interest = compound_interest(0.5, 0.5, 5)
    if is_finite(_v_compound_interest): passed += 1; print("  ✅ finance::compound_interest =", _v_compound_interest)
    else: failed += 1; print("  ❌ finance::compound_interest → non-finite:", _v_compound_interest)
    var _v_present_value = present_value(0.5, 0.5, 5)
    if is_finite(_v_present_value): passed += 1; print("  ✅ finance::present_value =", _v_present_value)
    else: failed += 1; print("  ❌ finance::present_value → non-finite:", _v_present_value)
    var _v_future_value = future_value(0.5, 0.5, 5)
    if is_finite(_v_future_value): passed += 1; print("  ✅ finance::future_value =", _v_future_value)
    else: failed += 1; print("  ❌ finance::future_value → non-finite:", _v_future_value)
    var _v_annuity_payment = annuity_payment(0.5, 0.5, 5)
    if is_finite(_v_annuity_payment): passed += 1; print("  ✅ finance::annuity_payment =", _v_annuity_payment)
    else: failed += 1; print("  ❌ finance::annuity_payment → non-finite:", _v_annuity_payment)
    var _v_sharpe_ratio = sharpe_ratio(_lf5, 0.5)
    if is_finite(_v_sharpe_ratio): passed += 1; print("  ✅ finance::sharpe_ratio =", _v_sharpe_ratio)
    else: failed += 1; print("  ❌ finance::sharpe_ratio → non-finite:", _v_sharpe_ratio)
    var _v_max_drawdown = max_drawdown(_lf5)
    if is_finite(_v_max_drawdown): passed += 1; print("  ✅ finance::max_drawdown =", _v_max_drawdown)
    else: failed += 1; print("  ❌ finance::max_drawdown → non-finite:", _v_max_drawdown)
    var _v_cagr = cagr(0.5, 0.5, 0.5)
    if is_finite(_v_cagr): passed += 1; print("  ✅ finance::cagr =", _v_cagr)
    else: failed += 1; print("  ❌ finance::cagr → non-finite:", _v_cagr)
    var _v_wacc = wacc(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_wacc): passed += 1; print("  ✅ finance::wacc =", _v_wacc)
    else: failed += 1; print("  ❌ finance::wacc → non-finite:", _v_wacc)

    print("  [finance] Passed:", passed, "Failed:", failed)
