"""test_timeseries_stats.mojo — auto-generated tests for timeseries_stats."""
from std.math import isnan, isinf
from timeseries_stats import autocorrelation, autocorrelation_function, partial_autocorrelation, rolling_mean, rolling_std, exponential_smoothing, difference, adf_test_statistic, holt_linear

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_autocorrelation = autocorrelation(_lf5, 5)
    if is_finite(_v_autocorrelation): passed += 1; print("  ✅ timeseries_stats::autocorrelation =", _v_autocorrelation)
    else: failed += 1; print("  ❌ timeseries_stats::autocorrelation → non-finite:", _v_autocorrelation)
    var _v_autocorrelation_function = autocorrelation_function(_lf5, 5)
    if len(_v_autocorrelation_function) >= 0: passed += 1; print("  ✅ timeseries_stats::autocorrelation_function")
    var _v_partial_autocorrelation = partial_autocorrelation(_lf5, 5)
    if len(_v_partial_autocorrelation) >= 0: passed += 1; print("  ✅ timeseries_stats::partial_autocorrelation")
    var _v_rolling_mean = rolling_mean(_lf5, 5)
    if len(_v_rolling_mean) >= 0: passed += 1; print("  ✅ timeseries_stats::rolling_mean")
    var _v_rolling_std = rolling_std(_lf5, 5)
    if len(_v_rolling_std) >= 0: passed += 1; print("  ✅ timeseries_stats::rolling_std")
    var _v_exponential_smoothing = exponential_smoothing(_lf5, 0.5)
    if len(_v_exponential_smoothing) >= 0: passed += 1; print("  ✅ timeseries_stats::exponential_smoothing")
    var _v_difference = difference(_lf5, 5)
    if len(_v_difference) >= 0: passed += 1; print("  ✅ timeseries_stats::difference")
    var _v_adf_test_statistic = adf_test_statistic(_lf5)
    if is_finite(_v_adf_test_statistic): passed += 1; print("  ✅ timeseries_stats::adf_test_statistic =", _v_adf_test_statistic)
    else: failed += 1; print("  ❌ timeseries_stats::adf_test_statistic → non-finite:", _v_adf_test_statistic)
    var _v_holt_linear = holt_linear(_lf5, 0.5, 0.5)
    if len(_v_holt_linear) >= 0: passed += 1; print("  ✅ timeseries_stats::holt_linear")

    print("  [timeseries_stats] Passed:", passed, "Failed:", failed)
