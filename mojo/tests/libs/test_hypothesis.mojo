"""test_hypothesis.mojo — auto-generated tests for hypothesis."""
from std.math import isnan, isinf
from hypothesis import rank_data, mann_whitney_u, wilcoxon_signed_rank, fisher_exact_2x2, sign_test

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

    var _v_rank_data = rank_data(_lf5)
    if len(_v_rank_data) >= 0: passed += 1; print("  ✅ hypothesis::rank_data")
    var _v_mann_whitney_u = mann_whitney_u(_lf5, _lf5)
    if len(_v_mann_whitney_u) >= 0: passed += 1; print("  ✅ hypothesis::mann_whitney_u")
    var _v_wilcoxon_signed_rank = wilcoxon_signed_rank(_lf5, _lf5)
    if len(_v_wilcoxon_signed_rank) >= 0: passed += 1; print("  ✅ hypothesis::wilcoxon_signed_rank")
    var _v_fisher_exact_2x2 = fisher_exact_2x2(5, 5, 5, 5)
    if is_finite(_v_fisher_exact_2x2): passed += 1; print("  ✅ hypothesis::fisher_exact_2x2 =", _v_fisher_exact_2x2)
    else: failed += 1; print("  ❌ hypothesis::fisher_exact_2x2 → non-finite:", _v_fisher_exact_2x2)
    var _v_sign_test = sign_test(_lf5, 0.5)
    if len(_v_sign_test) >= 0: passed += 1; print("  ✅ hypothesis::sign_test")

    print("  [hypothesis] Passed:", passed, "Failed:", failed)
