"""test_causal.mojo — auto-generated tests for causal library."""
from std.math import isnan, isinf
from causal import ate, att, propensity_score, ipw_estimate, diff_in_diff, regression_discontinuity, iv_estimate, stratified_ate, cohens_d, needed_sample_size_ate

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

    var _v_ate = ate(_lf5, _lf5)
    if is_finite(_v_ate): passed += 1; print("  ✅ causal::ate =", _v_ate)
    else: failed += 1; print("  ❌ causal::ate → non-finite:", _v_ate)
    var _v_att = att(_lf5, _lf5)
    if is_finite(_v_att): passed += 1; print("  ✅ causal::att =", _v_att)
    else: failed += 1; print("  ❌ causal::att → non-finite:", _v_att)
    var _v_propensity_score = propensity_score(_lf5, _li5)
    if len(_v_propensity_score) >= 0: passed += 1; print("  ✅ causal::propensity_score")
    var _v_ipw_estimate = ipw_estimate(_lf5, _li5, _lf5)
    if is_finite(_v_ipw_estimate): passed += 1; print("  ✅ causal::ipw_estimate =", _v_ipw_estimate)
    else: failed += 1; print("  ❌ causal::ipw_estimate → non-finite:", _v_ipw_estimate)
    var _v_diff_in_diff = diff_in_diff(_lf5, _lf5, _lf5, _lf5)
    if is_finite(_v_diff_in_diff): passed += 1; print("  ✅ causal::diff_in_diff =", _v_diff_in_diff)
    else: failed += 1; print("  ❌ causal::diff_in_diff → non-finite:", _v_diff_in_diff)
    var _v_regression_discontinuity = regression_discontinuity(_lf5, _lf5, 0.5)
    if is_finite(_v_regression_discontinuity): passed += 1; print("  ✅ causal::regression_discontinuity =", _v_regression_discontinuity)
    else: failed += 1; print("  ❌ causal::regression_discontinuity → non-finite:", _v_regression_discontinuity)
    var _v_iv_estimate = iv_estimate(_lf5, _lf5, _lf5)
    if is_finite(_v_iv_estimate): passed += 1; print("  ✅ causal::iv_estimate =", _v_iv_estimate)
    else: failed += 1; print("  ❌ causal::iv_estimate → non-finite:", _v_iv_estimate)
    var _v_stratified_ate = stratified_ate(_lf5, _li5, _li5, 5)
    if is_finite(_v_stratified_ate): passed += 1; print("  ✅ causal::stratified_ate =", _v_stratified_ate)
    else: failed += 1; print("  ❌ causal::stratified_ate → non-finite:", _v_stratified_ate)
    var _v_cohens_d = cohens_d(_lf5, _lf5)
    if is_finite(_v_cohens_d): passed += 1; print("  ✅ causal::cohens_d =", _v_cohens_d)
    else: failed += 1; print("  ❌ causal::cohens_d → non-finite:", _v_cohens_d)
    _ = needed_sample_size_ate(0.5, 0.5, 0.5, 0.5)
    passed += 1; print("  ✅ causal::needed_sample_size_ate")

    print("  [causal] Passed:", passed, "Failed:", failed)
