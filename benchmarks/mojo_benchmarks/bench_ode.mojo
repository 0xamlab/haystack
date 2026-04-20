"""bench_ode.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ode import euler_step, euler_solve, rk4_step, rk4_solve, exponential_decay, logistic_growth, rk4_step_system, rk4_solve_system, ODEResult
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

    var _acc_euler_step: Float64 = 0.0
    var _t0_euler_step = perf_counter_ns()
    for _ in range(N):
        var _r_euler_step = euler_step(_lf5, _lf5, 0.5)
        _acc_euler_step += Float64(len(_r_euler_step))
    var _t1_euler_step = perf_counter_ns()
    var _ns_euler_step = Float64(_t1_euler_step - _t0_euler_step) / Float64(N)
    print("MOJO_TIMING ode::euler_step", _ns_euler_step, _acc_euler_step)
    var _acc_euler_solve: Float64 = 0.0
    var _t0_euler_solve = perf_counter_ns()
    for _ in range(N):
        var _r_euler_solve = euler_solve(_lf5, _lf5, 0.5, 0.5)
        _acc_euler_solve += Float64(len(_r_euler_solve))
    var _t1_euler_solve = perf_counter_ns()
    var _ns_euler_solve = Float64(_t1_euler_solve - _t0_euler_solve) / Float64(N)
    print("MOJO_TIMING ode::euler_solve", _ns_euler_solve, _acc_euler_solve)
    var _acc_rk4_step: Float64 = 0.0
    var _t0_rk4_step = perf_counter_ns()
    for _ in range(N):
        _acc_rk4_step += rk4_step(0.5, _lf5, 0.5, 0.5)
    var _t1_rk4_step = perf_counter_ns()
    var _ns_rk4_step = Float64(_t1_rk4_step - _t0_rk4_step) / Float64(N)
    print("MOJO_TIMING ode::rk4_step", _ns_rk4_step, _acc_rk4_step)
    var _keeper_rk4_solve = List[ODEResult]()
    _keeper_rk4_solve.append(rk4_solve(0.5, _lf5, 0.5, 0.5, 0.5))
    var _acc_rk4_solve: Float64 = 0.0
    var _t0_rk4_solve = perf_counter_ns()
    for _ in range(N):
        _keeper_rk4_solve[0] = rk4_solve(0.5, _lf5, 0.5, 0.5, 0.5)
        _acc_rk4_solve += Float64(len(_keeper_rk4_solve))
    var _t1_rk4_solve = perf_counter_ns()
    var _ns_rk4_solve = Float64(_t1_rk4_solve - _t0_rk4_solve) / Float64(N)
    print("MOJO_TIMING ode::rk4_solve", _ns_rk4_solve, _acc_rk4_solve)
    var _acc_exponential_decay: Float64 = 0.0
    var _t0_exponential_decay = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_decay += exponential_decay(0.5, 0.5, 0.5)
    var _t1_exponential_decay = perf_counter_ns()
    var _ns_exponential_decay = Float64(_t1_exponential_decay - _t0_exponential_decay) / Float64(N)
    print("MOJO_TIMING ode::exponential_decay", _ns_exponential_decay, _acc_exponential_decay)
    var _acc_logistic_growth: Float64 = 0.0
    var _t0_logistic_growth = perf_counter_ns()
    for _ in range(N):
        _acc_logistic_growth += logistic_growth(0.5, 0.5, 0.5, 0.5)
    var _t1_logistic_growth = perf_counter_ns()
    var _ns_logistic_growth = Float64(_t1_logistic_growth - _t0_logistic_growth) / Float64(N)
    print("MOJO_TIMING ode::logistic_growth", _ns_logistic_growth, _acc_logistic_growth)
    var _acc_rk4_step_system: Float64 = 0.0
    var _t0_rk4_step_system = perf_counter_ns()
    for _ in range(N):
        var _r_rk4_step_system = rk4_step_system(_lf5, _lf5, 0.5, 0.5)
        _acc_rk4_step_system += Float64(len(_r_rk4_step_system))
    var _t1_rk4_step_system = perf_counter_ns()
    var _ns_rk4_step_system = Float64(_t1_rk4_step_system - _t0_rk4_step_system) / Float64(N)
    print("MOJO_TIMING ode::rk4_step_system", _ns_rk4_step_system, _acc_rk4_step_system)
    var _acc_rk4_solve_system: Float64 = 0.0
    var _t0_rk4_solve_system = perf_counter_ns()
    for _ in range(N):
        var _r_rk4_solve_system = rk4_solve_system(_lf5, _lf5, 0.5, 0.5, 0.5)
        _acc_rk4_solve_system += Float64(len(_r_rk4_solve_system))
    var _t1_rk4_solve_system = perf_counter_ns()
    var _ns_rk4_solve_system = Float64(_t1_rk4_solve_system - _t0_rk4_solve_system) / Float64(N)
    print("MOJO_TIMING ode::rk4_solve_system", _ns_rk4_solve_system, _acc_rk4_solve_system)
