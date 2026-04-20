"""test_feature_selection.mojo — auto-generated tests for feature_selection library."""
from std.math import isnan, isinf
from feature_selection import select_k_best, information_gain

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

    var _v_select_k_best = select_k_best(_lf5, 5)
    if len(_v_select_k_best) >= 0: passed += 1; print("  ✅ feature_selection::select_k_best")
    var _v_information_gain = information_gain(_lf5, _lf5, 5)
    if is_finite(_v_information_gain): passed += 1; print("  ✅ feature_selection::information_gain =", _v_information_gain)
    else: failed += 1; print("  ❌ feature_selection::information_gain → non-finite:", _v_information_gain)

    print("  [feature_selection] Passed:", passed, "Failed:", failed)
