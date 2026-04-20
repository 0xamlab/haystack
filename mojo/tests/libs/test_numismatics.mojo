"""test_numismatics.mojo — auto-generated tests for numismatics library."""
from std.math import isnan, isinf
from numismatics import melt_value, premium_over_melt, grade_numeric_to_scale, population_scarcity, annual_return, insurance_value, mintage_per_capita, survival_rate_estimate, price_trend, auction_fee, total_cost_acquisition, bullion_content_troy_oz

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

    var _v_melt_value = melt_value(0.5, 0.5)
    if is_finite(_v_melt_value): passed += 1; print("  ✅ numismatics::melt_value =", _v_melt_value)
    else: failed += 1; print("  ❌ numismatics::melt_value → non-finite:", _v_melt_value)
    var _v_premium_over_melt = premium_over_melt(0.5, 0.5)
    if is_finite(_v_premium_over_melt): passed += 1; print("  ✅ numismatics::premium_over_melt =", _v_premium_over_melt)
    else: failed += 1; print("  ❌ numismatics::premium_over_melt → non-finite:", _v_premium_over_melt)
    var _v_grade_numeric_to_scale = grade_numeric_to_scale(0.5)
    if is_finite(_v_grade_numeric_to_scale): passed += 1; print("  ✅ numismatics::grade_numeric_to_scale =", _v_grade_numeric_to_scale)
    else: failed += 1; print("  ❌ numismatics::grade_numeric_to_scale → non-finite:", _v_grade_numeric_to_scale)
    var _v_population_scarcity = population_scarcity(0.5, 0.5)
    if is_finite(_v_population_scarcity): passed += 1; print("  ✅ numismatics::population_scarcity =", _v_population_scarcity)
    else: failed += 1; print("  ❌ numismatics::population_scarcity → non-finite:", _v_population_scarcity)
    var _v_annual_return = annual_return(0.5, 0.5, 0.5)
    if is_finite(_v_annual_return): passed += 1; print("  ✅ numismatics::annual_return =", _v_annual_return)
    else: failed += 1; print("  ❌ numismatics::annual_return → non-finite:", _v_annual_return)
    var _v_insurance_value = insurance_value(0.5, 0.5)
    if is_finite(_v_insurance_value): passed += 1; print("  ✅ numismatics::insurance_value =", _v_insurance_value)
    else: failed += 1; print("  ❌ numismatics::insurance_value → non-finite:", _v_insurance_value)
    var _v_mintage_per_capita = mintage_per_capita(0.5, 0.5)
    if is_finite(_v_mintage_per_capita): passed += 1; print("  ✅ numismatics::mintage_per_capita =", _v_mintage_per_capita)
    else: failed += 1; print("  ❌ numismatics::mintage_per_capita → non-finite:", _v_mintage_per_capita)
    var _v_survival_rate_estimate = survival_rate_estimate(0.5, 0.5)
    if is_finite(_v_survival_rate_estimate): passed += 1; print("  ✅ numismatics::survival_rate_estimate =", _v_survival_rate_estimate)
    else: failed += 1; print("  ❌ numismatics::survival_rate_estimate → non-finite:", _v_survival_rate_estimate)
    var _v_price_trend = price_trend(0.5, 0.5)
    if is_finite(_v_price_trend): passed += 1; print("  ✅ numismatics::price_trend =", _v_price_trend)
    else: failed += 1; print("  ❌ numismatics::price_trend → non-finite:", _v_price_trend)
    var _v_auction_fee = auction_fee(0.5, 0.5)
    if is_finite(_v_auction_fee): passed += 1; print("  ✅ numismatics::auction_fee =", _v_auction_fee)
    else: failed += 1; print("  ❌ numismatics::auction_fee → non-finite:", _v_auction_fee)
    var _v_total_cost_acquisition = total_cost_acquisition(0.5, 0.5, 0.5)
    if is_finite(_v_total_cost_acquisition): passed += 1; print("  ✅ numismatics::total_cost_acquisition =", _v_total_cost_acquisition)
    else: failed += 1; print("  ❌ numismatics::total_cost_acquisition → non-finite:", _v_total_cost_acquisition)
    var _v_bullion_content_troy_oz = bullion_content_troy_oz(0.5, 0.5)
    if is_finite(_v_bullion_content_troy_oz): passed += 1; print("  ✅ numismatics::bullion_content_troy_oz =", _v_bullion_content_troy_oz)
    else: failed += 1; print("  ❌ numismatics::bullion_content_troy_oz → non-finite:", _v_bullion_content_troy_oz)

    print("  [numismatics] Passed:", passed, "Failed:", failed)
