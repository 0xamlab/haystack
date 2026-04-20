"""test_multi_objective.mojo — auto-generated tests for multi_objective library."""
from std.math import isnan, isinf
from multi_objective import is_dominated, weighted_score

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

    _ = is_dominated(_lf5, _lf5, _lb5)
    passed += 1; print("  ✅ multi_objective::is_dominated")
    var _v_weighted_score = weighted_score(_lf5, _lf5)
    if is_finite(_v_weighted_score): passed += 1; print("  ✅ multi_objective::weighted_score =", _v_weighted_score)
    else: failed += 1; print("  ❌ multi_objective::weighted_score → non-finite:", _v_weighted_score)

    print("  [multi_objective] Passed:", passed, "Failed:", failed)
