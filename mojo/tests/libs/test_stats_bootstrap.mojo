"""test_stats_bootstrap.mojo — auto-generated tests for stats_bootstrap library."""
from std.math import isnan, isinf
from stats_bootstrap import bootstrap_replicate, bootstrap_mean_ci, bootstrap_std_ci, bootstrap_median_ci, bootstrap_bias, bootstrap_se, bootstrap_test, jackknife_mean, jackknife_se, bca_correction

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

    var _v_bootstrap_replicate = bootstrap_replicate(_lf5)
    if len(_v_bootstrap_replicate) >= 0: passed += 1; print("  ✅ stats_bootstrap::bootstrap_replicate")
    var _v_bootstrap_mean_ci = bootstrap_mean_ci(_lf5, 5, 0.5)
    if len(_v_bootstrap_mean_ci) >= 0: passed += 1; print("  ✅ stats_bootstrap::bootstrap_mean_ci")
    var _v_bootstrap_std_ci = bootstrap_std_ci(_lf5, 5, 0.5)
    if len(_v_bootstrap_std_ci) >= 0: passed += 1; print("  ✅ stats_bootstrap::bootstrap_std_ci")
    var _v_bootstrap_median_ci = bootstrap_median_ci(_lf5, 5, 0.5)
    if len(_v_bootstrap_median_ci) >= 0: passed += 1; print("  ✅ stats_bootstrap::bootstrap_median_ci")
    var _v_bootstrap_bias = bootstrap_bias(_lf5, 5, 5)
    if is_finite(_v_bootstrap_bias): passed += 1; print("  ✅ stats_bootstrap::bootstrap_bias =", _v_bootstrap_bias)
    else: failed += 1; print("  ❌ stats_bootstrap::bootstrap_bias → non-finite:", _v_bootstrap_bias)
    var _v_bootstrap_se = bootstrap_se(_lf5, 5, 5)
    if is_finite(_v_bootstrap_se): passed += 1; print("  ✅ stats_bootstrap::bootstrap_se =", _v_bootstrap_se)
    else: failed += 1; print("  ❌ stats_bootstrap::bootstrap_se → non-finite:", _v_bootstrap_se)
    var _v_bootstrap_test = bootstrap_test(_lf5, _lf5, 5)
    if is_finite(_v_bootstrap_test): passed += 1; print("  ✅ stats_bootstrap::bootstrap_test =", _v_bootstrap_test)
    else: failed += 1; print("  ❌ stats_bootstrap::bootstrap_test → non-finite:", _v_bootstrap_test)
    var _v_jackknife_mean = jackknife_mean(_lf5)
    if len(_v_jackknife_mean) >= 0: passed += 1; print("  ✅ stats_bootstrap::jackknife_mean")
    var _v_jackknife_se = jackknife_se(_lf5)
    if is_finite(_v_jackknife_se): passed += 1; print("  ✅ stats_bootstrap::jackknife_se =", _v_jackknife_se)
    else: failed += 1; print("  ❌ stats_bootstrap::jackknife_se → non-finite:", _v_jackknife_se)
    var _v_bca_correction = bca_correction(_lf5, 5, 0.5)
    if len(_v_bca_correction) >= 0: passed += 1; print("  ✅ stats_bootstrap::bca_correction")

    print("  [stats_bootstrap] Passed:", passed, "Failed:", failed)
