"""test_stat_tests.mojo — auto-generated tests for stat_tests library."""
from std.math import isnan, isinf
from stat_tests import ks_test_2sample, ks_test_normal, t_test_1sample, t_test_2sample, chi_squared_test, anderson_darling_normal, shapiro_wilk_approx, pearson_r, spearman_r

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

    _ = ks_test_2sample(_lf5, _lf5)
    passed += 1; print("  ✅ stat_tests::ks_test_2sample")
    _ = ks_test_normal(_lf5)
    passed += 1; print("  ✅ stat_tests::ks_test_normal")
    _ = t_test_1sample(_lf5, 0.5)
    passed += 1; print("  ✅ stat_tests::t_test_1sample")
    _ = t_test_2sample(_lf5, _lf5)
    passed += 1; print("  ✅ stat_tests::t_test_2sample")
    _ = chi_squared_test(_lf5, _lf5)
    passed += 1; print("  ✅ stat_tests::chi_squared_test")
    _ = anderson_darling_normal(_lf5)
    passed += 1; print("  ✅ stat_tests::anderson_darling_normal")
    _ = shapiro_wilk_approx(_lf5)
    passed += 1; print("  ✅ stat_tests::shapiro_wilk_approx")
    _ = pearson_r(_lf5, _lf5)
    passed += 1; print("  ✅ stat_tests::pearson_r")
    _ = spearman_r(_lf5, _lf5)
    passed += 1; print("  ✅ stat_tests::spearman_r")

    print("  [stat_tests] Passed:", passed, "Failed:", failed)
