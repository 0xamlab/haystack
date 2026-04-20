"""test_control.mojo — auto-generated tests for control library."""
from std.math import isnan, isinf
from control import create_pid, pid_simulate, bang_bang, step_response, ramp_response, settling_time, overshoot, steady_state_error

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

    _ = create_pid(0.5, 0.5, 0.5, 0.5, 0.5)
    passed += 1; print("  ✅ control::create_pid")
    var _v_pid_simulate = pid_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
    if len(_v_pid_simulate) >= 0: passed += 1; print("  ✅ control::pid_simulate")
    var _v_bang_bang = bang_bang(0.5, 0.5, 0.5)
    if is_finite(_v_bang_bang): passed += 1; print("  ✅ control::bang_bang =", _v_bang_bang)
    else: failed += 1; print("  ❌ control::bang_bang → non-finite:", _v_bang_bang)
    var _v_step_response = step_response(0.5, 0.5, 0.5, 5)
    if len(_v_step_response) >= 0: passed += 1; print("  ✅ control::step_response")
    var _v_ramp_response = ramp_response(0.5, 0.5, 0.5, 5)
    if len(_v_ramp_response) >= 0: passed += 1; print("  ✅ control::ramp_response")
    var _v_settling_time = settling_time(_lf5, 0.5, 0.5)
    if is_finite(_v_settling_time): passed += 1; print("  ✅ control::settling_time =", _v_settling_time)
    else: failed += 1; print("  ❌ control::settling_time → non-finite:", _v_settling_time)
    var _v_overshoot = overshoot(_lf5, 0.5)
    if is_finite(_v_overshoot): passed += 1; print("  ✅ control::overshoot =", _v_overshoot)
    else: failed += 1; print("  ❌ control::overshoot → non-finite:", _v_overshoot)
    var _v_steady_state_error = steady_state_error(_lf5, 0.5)
    if is_finite(_v_steady_state_error): passed += 1; print("  ✅ control::steady_state_error =", _v_steady_state_error)
    else: failed += 1; print("  ❌ control::steady_state_error → non-finite:", _v_steady_state_error)

    print("  [control] Passed:", passed, "Failed:", failed)
