"""test_copula.mojo — auto-generated tests for copula."""
from std.math import isnan, isinf
from copula import norm_cdf_approx, norm_ppf_approx, gaussian_copula_sample, rank_correlation, kendall_tau

def is_finite(x: Float64) -> Bool:
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

    var _v_norm_cdf_approx = norm_cdf_approx(0.5)
    if is_finite(_v_norm_cdf_approx): passed += 1; print("  ✅ copula::norm_cdf_approx =", _v_norm_cdf_approx)
    else: failed += 1; print("  ❌ copula::norm_cdf_approx → non-finite:", _v_norm_cdf_approx)
    var _v_norm_ppf_approx = norm_ppf_approx(0.5)
    if is_finite(_v_norm_ppf_approx): passed += 1; print("  ✅ copula::norm_ppf_approx =", _v_norm_ppf_approx)
    else: failed += 1; print("  ❌ copula::norm_ppf_approx → non-finite:", _v_norm_ppf_approx)
    _ = gaussian_copula_sample(5, 0.5)
    passed += 1; print("  ✅ copula::gaussian_copula_sample")
    var _v_rank_correlation = rank_correlation(_lf5, _lf5)
    if is_finite(_v_rank_correlation): passed += 1; print("  ✅ copula::rank_correlation =", _v_rank_correlation)
    else: failed += 1; print("  ❌ copula::rank_correlation → non-finite:", _v_rank_correlation)
    var _v_kendall_tau = kendall_tau(_lf5, _lf5)
    if is_finite(_v_kendall_tau): passed += 1; print("  ✅ copula::kendall_tau =", _v_kendall_tau)
    else: failed += 1; print("  ❌ copula::kendall_tau → non-finite:", _v_kendall_tau)

    print("  [copula] Passed:", passed, "Failed:", failed)
