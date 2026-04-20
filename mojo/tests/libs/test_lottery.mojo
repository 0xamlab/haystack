"""test_lottery.mojo — auto-generated tests for lottery library."""
from std.math import isnan, isinf
from lottery import combinations, permutations, lottery_odds, expected_value, expected_value_net, house_edge, probability_at_least_one_win, annuity_vs_lump_sum, tax_after_winnings, odds_to_probability, probability_to_odds, jackpot_ev_threshold

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

    var _v_combinations = combinations(5, 5)
    if is_finite(_v_combinations): passed += 1; print("  ✅ lottery::combinations =", _v_combinations)
    else: failed += 1; print("  ❌ lottery::combinations → non-finite:", _v_combinations)
    var _v_permutations = permutations(5, 5)
    if is_finite(_v_permutations): passed += 1; print("  ✅ lottery::permutations =", _v_permutations)
    else: failed += 1; print("  ❌ lottery::permutations → non-finite:", _v_permutations)
    var _v_lottery_odds = lottery_odds(5, 5, 5)
    if is_finite(_v_lottery_odds): passed += 1; print("  ✅ lottery::lottery_odds =", _v_lottery_odds)
    else: failed += 1; print("  ❌ lottery::lottery_odds → non-finite:", _v_lottery_odds)
    var _v_expected_value = expected_value(0.5, 0.5)
    if is_finite(_v_expected_value): passed += 1; print("  ✅ lottery::expected_value =", _v_expected_value)
    else: failed += 1; print("  ❌ lottery::expected_value → non-finite:", _v_expected_value)
    var _v_expected_value_net = expected_value_net(0.5, 0.5)
    if is_finite(_v_expected_value_net): passed += 1; print("  ✅ lottery::expected_value_net =", _v_expected_value_net)
    else: failed += 1; print("  ❌ lottery::expected_value_net → non-finite:", _v_expected_value_net)
    var _v_house_edge = house_edge(0.5, 0.5)
    if is_finite(_v_house_edge): passed += 1; print("  ✅ lottery::house_edge =", _v_house_edge)
    else: failed += 1; print("  ❌ lottery::house_edge → non-finite:", _v_house_edge)
    var _v_probability_at_least_one_win = probability_at_least_one_win(0.5, 5)
    if is_finite(_v_probability_at_least_one_win): passed += 1; print("  ✅ lottery::probability_at_least_one_win =", _v_probability_at_least_one_win)
    else: failed += 1; print("  ❌ lottery::probability_at_least_one_win → non-finite:", _v_probability_at_least_one_win)
    var _v_annuity_vs_lump_sum = annuity_vs_lump_sum(0.5, 0.5, 0.5)
    if is_finite(_v_annuity_vs_lump_sum): passed += 1; print("  ✅ lottery::annuity_vs_lump_sum =", _v_annuity_vs_lump_sum)
    else: failed += 1; print("  ❌ lottery::annuity_vs_lump_sum → non-finite:", _v_annuity_vs_lump_sum)
    var _v_tax_after_winnings = tax_after_winnings(0.5, 0.5, 0.5)
    if is_finite(_v_tax_after_winnings): passed += 1; print("  ✅ lottery::tax_after_winnings =", _v_tax_after_winnings)
    else: failed += 1; print("  ❌ lottery::tax_after_winnings → non-finite:", _v_tax_after_winnings)
    var _v_odds_to_probability = odds_to_probability(0.5)
    if is_finite(_v_odds_to_probability): passed += 1; print("  ✅ lottery::odds_to_probability =", _v_odds_to_probability)
    else: failed += 1; print("  ❌ lottery::odds_to_probability → non-finite:", _v_odds_to_probability)
    var _v_probability_to_odds = probability_to_odds(0.5)
    if is_finite(_v_probability_to_odds): passed += 1; print("  ✅ lottery::probability_to_odds =", _v_probability_to_odds)
    else: failed += 1; print("  ❌ lottery::probability_to_odds → non-finite:", _v_probability_to_odds)
    var _v_jackpot_ev_threshold = jackpot_ev_threshold(0.5, 0.5)
    if is_finite(_v_jackpot_ev_threshold): passed += 1; print("  ✅ lottery::jackpot_ev_threshold =", _v_jackpot_ev_threshold)
    else: failed += 1; print("  ❌ lottery::jackpot_ev_threshold → non-finite:", _v_jackpot_ev_threshold)

    print("  [lottery] Passed:", passed, "Failed:", failed)
