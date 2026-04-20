"""bench_control.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from control import create_pid, pid_simulate, bang_bang, step_response, ramp_response, settling_time, overshoot, steady_state_error
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_create_pid: Float64 = 0.0
    var _t0_create_pid = perf_counter_ns()
    for _ in range(N):
        var _r_create_pid = create_pid(0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_create_pid += Float64(_r_create_pid.kp)
    var _t1_create_pid = perf_counter_ns()
    var _ns_create_pid = Float64(_t1_create_pid - _t0_create_pid) / Float64(N)
    print("MOJO_TIMING control::create_pid", _ns_create_pid, _acc_create_pid)
    var _acc_pid_simulate: Float64 = 0.0
    var _t0_pid_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_pid_simulate = pid_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_pid_simulate += Float64(len(_r_pid_simulate))
    var _t1_pid_simulate = perf_counter_ns()
    var _ns_pid_simulate = Float64(_t1_pid_simulate - _t0_pid_simulate) / Float64(N)
    print("MOJO_TIMING control::pid_simulate", _ns_pid_simulate, _acc_pid_simulate)
    var _acc_bang_bang: Float64 = 0.0
    var _t0_bang_bang = perf_counter_ns()
    for _ in range(N):
        _acc_bang_bang += bang_bang(0.5, 0.5, 0.5)
    var _t1_bang_bang = perf_counter_ns()
    var _ns_bang_bang = Float64(_t1_bang_bang - _t0_bang_bang) / Float64(N)
    print("MOJO_TIMING control::bang_bang", _ns_bang_bang, _acc_bang_bang)
    var _acc_step_response: Float64 = 0.0
    var _t0_step_response = perf_counter_ns()
    for _ in range(N):
        var _r_step_response = step_response(0.5, 0.5, 0.5, 5)
        _acc_step_response += Float64(len(_r_step_response))
    var _t1_step_response = perf_counter_ns()
    var _ns_step_response = Float64(_t1_step_response - _t0_step_response) / Float64(N)
    print("MOJO_TIMING control::step_response", _ns_step_response, _acc_step_response)
    var _acc_ramp_response: Float64 = 0.0
    var _t0_ramp_response = perf_counter_ns()
    for _ in range(N):
        var _r_ramp_response = ramp_response(0.5, 0.5, 0.5, 5)
        _acc_ramp_response += Float64(len(_r_ramp_response))
    var _t1_ramp_response = perf_counter_ns()
    var _ns_ramp_response = Float64(_t1_ramp_response - _t0_ramp_response) / Float64(N)
    print("MOJO_TIMING control::ramp_response", _ns_ramp_response, _acc_ramp_response)
    var _acc_settling_time: Float64 = 0.0
    var _t0_settling_time = perf_counter_ns()
    for _ in range(N):
        _acc_settling_time += settling_time(_lf5, 0.5, 0.5)
    var _t1_settling_time = perf_counter_ns()
    var _ns_settling_time = Float64(_t1_settling_time - _t0_settling_time) / Float64(N)
    print("MOJO_TIMING control::settling_time", _ns_settling_time, _acc_settling_time)
    var _acc_overshoot: Float64 = 0.0
    var _t0_overshoot = perf_counter_ns()
    for _ in range(N):
        _acc_overshoot += overshoot(_lf5, 0.5)
    var _t1_overshoot = perf_counter_ns()
    var _ns_overshoot = Float64(_t1_overshoot - _t0_overshoot) / Float64(N)
    print("MOJO_TIMING control::overshoot", _ns_overshoot, _acc_overshoot)
    var _acc_steady_state_error: Float64 = 0.0
    var _t0_steady_state_error = perf_counter_ns()
    for _ in range(N):
        _acc_steady_state_error += steady_state_error(_lf5, 0.5)
    var _t1_steady_state_error = perf_counter_ns()
    var _ns_steady_state_error = Float64(_t1_steady_state_error - _t0_steady_state_error) / Float64(N)
    print("MOJO_TIMING control::steady_state_error", _ns_steady_state_error, _acc_steady_state_error)
