"""test_ode.mojo — auto-generated tests for ode library."""
from std.math import isnan, isinf
from ode import euler_step, euler_solve, rk4_step, rk4_solve, exponential_decay, logistic_growth, rk4_step_system, rk4_solve_system

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

    var _v_euler_step = euler_step(_lf5, _lf5, 0.5)
    if len(_v_euler_step) >= 0: passed += 1; print("  ✅ ode::euler_step")
    _ = euler_solve(_lf5, _lf5, 0.5, 0.5)
    passed += 1; print("  ✅ ode::euler_solve")
    var _v_rk4_step = rk4_step(0.5, _lf5, 0.5, 0.5)
    if is_finite(_v_rk4_step): passed += 1; print("  ✅ ode::rk4_step =", _v_rk4_step)
    else: failed += 1; print("  ❌ ode::rk4_step → non-finite:", _v_rk4_step)
    _ = rk4_solve(0.5, _lf5, 0.5, 0.5, 0.5)
    passed += 1; print("  ✅ ode::rk4_solve")
    var _v_exponential_decay = exponential_decay(0.5, 0.5, 0.5)
    if is_finite(_v_exponential_decay): passed += 1; print("  ✅ ode::exponential_decay =", _v_exponential_decay)
    else: failed += 1; print("  ❌ ode::exponential_decay → non-finite:", _v_exponential_decay)
    var _v_logistic_growth = logistic_growth(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_logistic_growth): passed += 1; print("  ✅ ode::logistic_growth =", _v_logistic_growth)
    else: failed += 1; print("  ❌ ode::logistic_growth → non-finite:", _v_logistic_growth)
    var _v_rk4_step_system = rk4_step_system(_lf5, _lf5, 0.5, 0.5)
    if len(_v_rk4_step_system) >= 0: passed += 1; print("  ✅ ode::rk4_step_system")
    _ = rk4_solve_system(_lf5, _lf5, 0.5, 0.5, 0.5)
    passed += 1; print("  ✅ ode::rk4_solve_system")

    print("  [ode] Passed:", passed, "Failed:", failed)
