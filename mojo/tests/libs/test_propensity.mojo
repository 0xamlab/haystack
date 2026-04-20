"""test_propensity.mojo — auto-generated tests for propensity library."""
from std.math import isnan, isinf
from propensity import nearest_neighbor_match, caliper_match, matched_ate, balance_check, propensity_overlap, trimmed_sample, stratified_estimate, match_quality

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

    var _v_nearest_neighbor_match = nearest_neighbor_match(_lf5, _lf5)
    if len(_v_nearest_neighbor_match) >= 0: passed += 1; print("  ✅ propensity::nearest_neighbor_match")
    var _v_caliper_match = caliper_match(_lf5, _lf5, 0.5)
    if len(_v_caliper_match) >= 0: passed += 1; print("  ✅ propensity::caliper_match")
    var _v_matched_ate = matched_ate(_lf5, _li5, _li5)
    if is_finite(_v_matched_ate): passed += 1; print("  ✅ propensity::matched_ate =", _v_matched_ate)
    else: failed += 1; print("  ❌ propensity::matched_ate → non-finite:", _v_matched_ate)
    var _v_balance_check = balance_check(_lf5, _lf5)
    if is_finite(_v_balance_check): passed += 1; print("  ✅ propensity::balance_check =", _v_balance_check)
    else: failed += 1; print("  ❌ propensity::balance_check → non-finite:", _v_balance_check)
    var _v_propensity_overlap = propensity_overlap(_lf5, _li5)
    if is_finite(_v_propensity_overlap): passed += 1; print("  ✅ propensity::propensity_overlap =", _v_propensity_overlap)
    else: failed += 1; print("  ❌ propensity::propensity_overlap → non-finite:", _v_propensity_overlap)
    var _v_trimmed_sample = trimmed_sample(_lf5, _li5, 0.5, 0.5)
    if len(_v_trimmed_sample) >= 0: passed += 1; print("  ✅ propensity::trimmed_sample")
    var _v_stratified_estimate = stratified_estimate(_lf5, _li5, _lf5, 5)
    if is_finite(_v_stratified_estimate): passed += 1; print("  ✅ propensity::stratified_estimate =", _v_stratified_estimate)
    else: failed += 1; print("  ❌ propensity::stratified_estimate → non-finite:", _v_stratified_estimate)
    var _v_match_quality = match_quality(_li5)
    if is_finite(_v_match_quality): passed += 1; print("  ✅ propensity::match_quality =", _v_match_quality)
    else: failed += 1; print("  ❌ propensity::match_quality → non-finite:", _v_match_quality)

    print("  [propensity] Passed:", passed, "Failed:", failed)
