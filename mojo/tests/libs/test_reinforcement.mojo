"""test_reinforcement.mojo — auto-generated tests for reinforcement library."""
from std.math import isnan, isinf
from reinforcement import epsilon_greedy_action, td_error, discounted_return

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

    _ = epsilon_greedy_action(_lf5, 0.5)
    passed += 1; print("  ✅ reinforcement::epsilon_greedy_action")
    var _v_td_error = td_error(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_td_error): passed += 1; print("  ✅ reinforcement::td_error =", _v_td_error)
    else: failed += 1; print("  ❌ reinforcement::td_error → non-finite:", _v_td_error)
    var _v_discounted_return = discounted_return(_lf5, 0.5)
    if is_finite(_v_discounted_return): passed += 1; print("  ✅ reinforcement::discounted_return =", _v_discounted_return)
    else: failed += 1; print("  ❌ reinforcement::discounted_return → non-finite:", _v_discounted_return)

    print("  [reinforcement] Passed:", passed, "Failed:", failed)
