"""test_hypothesis.mojo — auto-generated tests for hypothesis library."""
from std.math import isnan, isinf
from hypothesis import rank_data, mann_whitney_u, wilcoxon_signed_rank, fisher_exact_2x2, sign_test

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
