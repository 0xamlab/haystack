"""test_scoring.mojo — auto-generated tests for scoring library."""
from std.math import isnan, isinf
from scoring import sigmoid, logit, log_odds_to_score, score_to_log_odds, woe, iv, gini_coefficient, ks_statistic, linear_score, normalize_score

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

    var _v_sigmoid = sigmoid(0.5)
    if is_finite(_v_sigmoid): passed += 1; print("  ✅ scoring::sigmoid =", _v_sigmoid)
    else: failed += 1; print("  ❌ scoring::sigmoid → non-finite:", _v_sigmoid)
    var _v_logit = logit(0.5)
    if is_finite(_v_logit): passed += 1; print("  ✅ scoring::logit =", _v_logit)
    else: failed += 1; print("  ❌ scoring::logit → non-finite:", _v_logit)
    var _v_log_odds_to_score = log_odds_to_score(0.5, 0.5, 0.5)
    if is_finite(_v_log_odds_to_score): passed += 1; print("  ✅ scoring::log_odds_to_score =", _v_log_odds_to_score)
    else: failed += 1; print("  ❌ scoring::log_odds_to_score → non-finite:", _v_log_odds_to_score)
    var _v_score_to_log_odds = score_to_log_odds(0.5, 0.5, 0.5)
    if is_finite(_v_score_to_log_odds): passed += 1; print("  ✅ scoring::score_to_log_odds =", _v_score_to_log_odds)
    else: failed += 1; print("  ❌ scoring::score_to_log_odds → non-finite:", _v_score_to_log_odds)
    var _v_woe = woe(5, 5, 5, 5)
    if is_finite(_v_woe): passed += 1; print("  ✅ scoring::woe =", _v_woe)
    else: failed += 1; print("  ❌ scoring::woe → non-finite:", _v_woe)
    var _v_iv = iv(_lf5, _lf5, _lf5)
    if is_finite(_v_iv): passed += 1; print("  ✅ scoring::iv =", _v_iv)
    else: failed += 1; print("  ❌ scoring::iv → non-finite:", _v_iv)
    var _v_gini_coefficient = gini_coefficient(_lf5, _lf5)
    if is_finite(_v_gini_coefficient): passed += 1; print("  ✅ scoring::gini_coefficient =", _v_gini_coefficient)
    else: failed += 1; print("  ❌ scoring::gini_coefficient → non-finite:", _v_gini_coefficient)
    var _v_ks_statistic = ks_statistic(_lf5, _lf5)
    if is_finite(_v_ks_statistic): passed += 1; print("  ✅ scoring::ks_statistic =", _v_ks_statistic)
    else: failed += 1; print("  ❌ scoring::ks_statistic → non-finite:", _v_ks_statistic)
    var _v_linear_score = linear_score(_lf5, _lf5, 0.5)
    if is_finite(_v_linear_score): passed += 1; print("  ✅ scoring::linear_score =", _v_linear_score)
    else: failed += 1; print("  ❌ scoring::linear_score → non-finite:", _v_linear_score)
    var _v_normalize_score = normalize_score(0.5, 0.5, 0.5)
    if is_finite(_v_normalize_score): passed += 1; print("  ✅ scoring::normalize_score =", _v_normalize_score)
    else: failed += 1; print("  ❌ scoring::normalize_score → non-finite:", _v_normalize_score)

    print("  [scoring] Passed:", passed, "Failed:", failed)
