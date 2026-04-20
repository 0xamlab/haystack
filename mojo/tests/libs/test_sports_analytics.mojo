"""test_sports_analytics.mojo — auto-generated tests for sports_analytics library."""
from std.math import isnan, isinf
from sports_analytics import batting_average, on_base_percentage, slugging_percentage, ops, era, whip, passer_rating_nfl, pythagorean_wins, elo_expected_score, elo_new_rating, true_shooting_percentage, player_efficiency_rating_approx

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

    var _v_batting_average = batting_average(0.5, 0.5)
    if is_finite(_v_batting_average): passed += 1; print("  ✅ sports_analytics::batting_average =", _v_batting_average)
    else: failed += 1; print("  ❌ sports_analytics::batting_average → non-finite:", _v_batting_average)
    var _v_on_base_percentage = on_base_percentage(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_on_base_percentage): passed += 1; print("  ✅ sports_analytics::on_base_percentage =", _v_on_base_percentage)
    else: failed += 1; print("  ❌ sports_analytics::on_base_percentage → non-finite:", _v_on_base_percentage)
    var _v_slugging_percentage = slugging_percentage(0.5, 0.5)
    if is_finite(_v_slugging_percentage): passed += 1; print("  ✅ sports_analytics::slugging_percentage =", _v_slugging_percentage)
    else: failed += 1; print("  ❌ sports_analytics::slugging_percentage → non-finite:", _v_slugging_percentage)
    var _v_ops = ops(0.5, 0.5)
    if is_finite(_v_ops): passed += 1; print("  ✅ sports_analytics::ops =", _v_ops)
    else: failed += 1; print("  ❌ sports_analytics::ops → non-finite:", _v_ops)
    var _v_era = era(0.5, 0.5)
    if is_finite(_v_era): passed += 1; print("  ✅ sports_analytics::era =", _v_era)
    else: failed += 1; print("  ❌ sports_analytics::era → non-finite:", _v_era)
    var _v_whip = whip(0.5, 0.5, 0.5)
    if is_finite(_v_whip): passed += 1; print("  ✅ sports_analytics::whip =", _v_whip)
    else: failed += 1; print("  ❌ sports_analytics::whip → non-finite:", _v_whip)
    var _v_passer_rating_nfl = passer_rating_nfl(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_passer_rating_nfl): passed += 1; print("  ✅ sports_analytics::passer_rating_nfl =", _v_passer_rating_nfl)
    else: failed += 1; print("  ❌ sports_analytics::passer_rating_nfl → non-finite:", _v_passer_rating_nfl)
    var _v_pythagorean_wins = pythagorean_wins(0.5, 0.5, 0.5)
    if is_finite(_v_pythagorean_wins): passed += 1; print("  ✅ sports_analytics::pythagorean_wins =", _v_pythagorean_wins)
    else: failed += 1; print("  ❌ sports_analytics::pythagorean_wins → non-finite:", _v_pythagorean_wins)
    var _v_elo_expected_score = elo_expected_score(0.5, 0.5)
    if is_finite(_v_elo_expected_score): passed += 1; print("  ✅ sports_analytics::elo_expected_score =", _v_elo_expected_score)
    else: failed += 1; print("  ❌ sports_analytics::elo_expected_score → non-finite:", _v_elo_expected_score)
    var _v_elo_new_rating = elo_new_rating(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_elo_new_rating): passed += 1; print("  ✅ sports_analytics::elo_new_rating =", _v_elo_new_rating)
    else: failed += 1; print("  ❌ sports_analytics::elo_new_rating → non-finite:", _v_elo_new_rating)
    var _v_true_shooting_percentage = true_shooting_percentage(0.5, 0.5, 0.5)
    if is_finite(_v_true_shooting_percentage): passed += 1; print("  ✅ sports_analytics::true_shooting_percentage =", _v_true_shooting_percentage)
    else: failed += 1; print("  ❌ sports_analytics::true_shooting_percentage → non-finite:", _v_true_shooting_percentage)
    var _v_player_efficiency_rating_approx = player_efficiency_rating_approx(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_player_efficiency_rating_approx): passed += 1; print("  ✅ sports_analytics::player_efficiency_rating_approx =", _v_player_efficiency_rating_approx)
    else: failed += 1; print("  ❌ sports_analytics::player_efficiency_rating_approx → non-finite:", _v_player_efficiency_rating_approx)

    print("  [sports_analytics] Passed:", passed, "Failed:", failed)
