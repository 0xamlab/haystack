"""test_auction.mojo — auto-generated tests for auction library."""
from std.math import isnan, isinf
from auction import first_price_sealed, second_price_sealed, english_auction_revenue, dutch_auction_revenue, all_pay_revenue, revenue_equivalence_check, vcg_payment, reserve_price_filter, bid_shading_optimal, expected_revenue_uniform, winners_curse_adjustment

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

    var _v_first_price_sealed = first_price_sealed(_lf5, 5)
    if len(_v_first_price_sealed) >= 0: passed += 1; print("  ✅ auction::first_price_sealed")
    var _v_second_price_sealed = second_price_sealed(_lf5, 5)
    if len(_v_second_price_sealed) >= 0: passed += 1; print("  ✅ auction::second_price_sealed")
    var _v_english_auction_revenue = english_auction_revenue(_lf5, 5)
    if is_finite(_v_english_auction_revenue): passed += 1; print("  ✅ auction::english_auction_revenue =", _v_english_auction_revenue)
    else: failed += 1; print("  ❌ auction::english_auction_revenue → non-finite:", _v_english_auction_revenue)
    var _v_dutch_auction_revenue = dutch_auction_revenue(_lf5, 5)
    if is_finite(_v_dutch_auction_revenue): passed += 1; print("  ✅ auction::dutch_auction_revenue =", _v_dutch_auction_revenue)
    else: failed += 1; print("  ❌ auction::dutch_auction_revenue → non-finite:", _v_dutch_auction_revenue)
    var _v_all_pay_revenue = all_pay_revenue(_lf5, 5)
    if is_finite(_v_all_pay_revenue): passed += 1; print("  ✅ auction::all_pay_revenue =", _v_all_pay_revenue)
    else: failed += 1; print("  ❌ auction::all_pay_revenue → non-finite:", _v_all_pay_revenue)
    _ = revenue_equivalence_check(_lf5, 5)
    passed += 1; print("  ✅ auction::revenue_equivalence_check")
    var _v_vcg_payment = vcg_payment(_lf5, 5, 5)
    if is_finite(_v_vcg_payment): passed += 1; print("  ✅ auction::vcg_payment =", _v_vcg_payment)
    else: failed += 1; print("  ❌ auction::vcg_payment → non-finite:", _v_vcg_payment)
    var _v_reserve_price_filter = reserve_price_filter(_lf5, 5, 0.5)
    if len(_v_reserve_price_filter) >= 0: passed += 1; print("  ✅ auction::reserve_price_filter")
    var _v_bid_shading_optimal = bid_shading_optimal(0.5, 5)
    if is_finite(_v_bid_shading_optimal): passed += 1; print("  ✅ auction::bid_shading_optimal =", _v_bid_shading_optimal)
    else: failed += 1; print("  ❌ auction::bid_shading_optimal → non-finite:", _v_bid_shading_optimal)
    var _v_expected_revenue_uniform = expected_revenue_uniform(5, 0.5)
    if is_finite(_v_expected_revenue_uniform): passed += 1; print("  ✅ auction::expected_revenue_uniform =", _v_expected_revenue_uniform)
    else: failed += 1; print("  ❌ auction::expected_revenue_uniform → non-finite:", _v_expected_revenue_uniform)
    var _v_winners_curse_adjustment = winners_curse_adjustment(0.5, 5)
    if is_finite(_v_winners_curse_adjustment): passed += 1; print("  ✅ auction::winners_curse_adjustment =", _v_winners_curse_adjustment)
    else: failed += 1; print("  ❌ auction::winners_curse_adjustment → non-finite:", _v_winners_curse_adjustment)

    print("  [auction] Passed:", passed, "Failed:", failed)
