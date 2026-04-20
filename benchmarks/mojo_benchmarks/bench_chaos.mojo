"""bench_chaos.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from chaos import logistic_map, lorenz_step, lorenz_simulate, lyapunov_exponent_logistic, henon_map, tent_map, bifurcation_diagram, sensitivity_to_initial, feigenbaum_ratio, is_chaotic
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

    var _acc_logistic_map: Float64 = 0.0
    var _t0_logistic_map = perf_counter_ns()
    for _ in range(N):
        var _r_logistic_map = logistic_map(0.5, 0.5, 5)
        _acc_logistic_map += Float64(len(_r_logistic_map))
    var _t1_logistic_map = perf_counter_ns()
    var _ns_logistic_map = Float64(_t1_logistic_map - _t0_logistic_map) / Float64(N)
    print("MOJO_TIMING chaos::logistic_map", _ns_logistic_map, _acc_logistic_map)
    var _acc_lorenz_step: Float64 = 0.0
    var _t0_lorenz_step = perf_counter_ns()
    for _ in range(N):
        var _r_lorenz_step = lorenz_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        _acc_lorenz_step += Float64(len(_r_lorenz_step))
    var _t1_lorenz_step = perf_counter_ns()
    var _ns_lorenz_step = Float64(_t1_lorenz_step - _t0_lorenz_step) / Float64(N)
    print("MOJO_TIMING chaos::lorenz_step", _ns_lorenz_step, _acc_lorenz_step)
    var _acc_lorenz_simulate: Float64 = 0.0
    var _t0_lorenz_simulate = perf_counter_ns()
    for _ in range(N):
        var _r_lorenz_simulate = lorenz_simulate(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 5)
        _acc_lorenz_simulate += Float64(len(_r_lorenz_simulate))
    var _t1_lorenz_simulate = perf_counter_ns()
    var _ns_lorenz_simulate = Float64(_t1_lorenz_simulate - _t0_lorenz_simulate) / Float64(N)
    print("MOJO_TIMING chaos::lorenz_simulate", _ns_lorenz_simulate, _acc_lorenz_simulate)
    var _acc_lyapunov_exponent_logistic: Float64 = 0.0
    var _t0_lyapunov_exponent_logistic = perf_counter_ns()
    for _ in range(N):
        _acc_lyapunov_exponent_logistic += lyapunov_exponent_logistic(0.5, 5, 5)
    var _t1_lyapunov_exponent_logistic = perf_counter_ns()
    var _ns_lyapunov_exponent_logistic = Float64(_t1_lyapunov_exponent_logistic - _t0_lyapunov_exponent_logistic) / Float64(N)
    print("MOJO_TIMING chaos::lyapunov_exponent_logistic", _ns_lyapunov_exponent_logistic, _acc_lyapunov_exponent_logistic)
    var _acc_henon_map: Float64 = 0.0
    var _t0_henon_map = perf_counter_ns()
    for _ in range(N):
        var _r_henon_map = henon_map(0.5, 0.5, 0.5, 0.5, 5)
        _acc_henon_map += Float64(len(_r_henon_map))
    var _t1_henon_map = perf_counter_ns()
    var _ns_henon_map = Float64(_t1_henon_map - _t0_henon_map) / Float64(N)
    print("MOJO_TIMING chaos::henon_map", _ns_henon_map, _acc_henon_map)
    var _acc_tent_map: Float64 = 0.0
    var _t0_tent_map = perf_counter_ns()
    for _ in range(N):
        var _r_tent_map = tent_map(0.5, 0.5, 5)
        _acc_tent_map += Float64(len(_r_tent_map))
    var _t1_tent_map = perf_counter_ns()
    var _ns_tent_map = Float64(_t1_tent_map - _t0_tent_map) / Float64(N)
    print("MOJO_TIMING chaos::tent_map", _ns_tent_map, _acc_tent_map)
    var _acc_bifurcation_diagram: Float64 = 0.0
    var _t0_bifurcation_diagram = perf_counter_ns()
    for _ in range(N):
        var _r_bifurcation_diagram = bifurcation_diagram(0.5, 0.5, 5, 5, 5)
        _acc_bifurcation_diagram += Float64(len(_r_bifurcation_diagram))
    var _t1_bifurcation_diagram = perf_counter_ns()
    var _ns_bifurcation_diagram = Float64(_t1_bifurcation_diagram - _t0_bifurcation_diagram) / Float64(N)
    print("MOJO_TIMING chaos::bifurcation_diagram", _ns_bifurcation_diagram, _acc_bifurcation_diagram)
    var _acc_sensitivity_to_initial: Float64 = 0.0
    var _t0_sensitivity_to_initial = perf_counter_ns()
    for _ in range(N):
        var _r_sensitivity_to_initial = sensitivity_to_initial(0.5, 0.5, 0.5, 5)
        _acc_sensitivity_to_initial += Float64(len(_r_sensitivity_to_initial))
    var _t1_sensitivity_to_initial = perf_counter_ns()
    var _ns_sensitivity_to_initial = Float64(_t1_sensitivity_to_initial - _t0_sensitivity_to_initial) / Float64(N)
    print("MOJO_TIMING chaos::sensitivity_to_initial", _ns_sensitivity_to_initial, _acc_sensitivity_to_initial)
    var _acc_feigenbaum_ratio: Float64 = 0.0
    var _t0_feigenbaum_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_feigenbaum_ratio += feigenbaum_ratio(0.5, 0.5, 0.5)
    var _t1_feigenbaum_ratio = perf_counter_ns()
    var _ns_feigenbaum_ratio = Float64(_t1_feigenbaum_ratio - _t0_feigenbaum_ratio) / Float64(N)
    print("MOJO_TIMING chaos::feigenbaum_ratio", _ns_feigenbaum_ratio, _acc_feigenbaum_ratio)
    var _acc_is_chaotic: Float64 = 0.0
    var _t0_is_chaotic = perf_counter_ns()
    for _ in range(N):
        _acc_is_chaotic += Float64(is_chaotic(0.5))
    var _t1_is_chaotic = perf_counter_ns()
    var _ns_is_chaotic = Float64(_t1_is_chaotic - _t0_is_chaotic) / Float64(N)
    print("MOJO_TIMING chaos::is_chaotic", _ns_is_chaotic, _acc_is_chaotic)
