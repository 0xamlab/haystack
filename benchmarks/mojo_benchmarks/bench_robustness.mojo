"""bench_robustness.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from robustness import eval_test_func, perturbation_test, sensitivity_one_at_a_time, morris_screening, sobol_first_order_estimate, input_range_sweep, tornado_data, robustness_score
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

    var _acc_eval_test_func: Float64 = 0.0
    var _t0_eval_test_func = perf_counter_ns()
    for _ in range(N):
        _acc_eval_test_func += eval_test_func(_lf5, 5)
    var _t1_eval_test_func = perf_counter_ns()
    var _ns_eval_test_func = Float64(_t1_eval_test_func - _t0_eval_test_func) / Float64(N)
    print("MOJO_TIMING robustness::eval_test_func", _ns_eval_test_func, _acc_eval_test_func)
    var _acc_perturbation_test: Float64 = 0.0
    var _t0_perturbation_test = perf_counter_ns()
    for _ in range(N):
        var _r_perturbation_test = perturbation_test(_lf5, 0.5)
        _acc_perturbation_test += Float64(len(_r_perturbation_test))
    var _t1_perturbation_test = perf_counter_ns()
    var _ns_perturbation_test = Float64(_t1_perturbation_test - _t0_perturbation_test) / Float64(N)
    print("MOJO_TIMING robustness::perturbation_test", _ns_perturbation_test, _acc_perturbation_test)
    var _acc_sensitivity_one_at_a_time: Float64 = 0.0
    var _t0_sensitivity_one_at_a_time = perf_counter_ns()
    for _ in range(N):
        _acc_sensitivity_one_at_a_time += sensitivity_one_at_a_time(_lf5, 5, 0.5, 5)
    var _t1_sensitivity_one_at_a_time = perf_counter_ns()
    var _ns_sensitivity_one_at_a_time = Float64(_t1_sensitivity_one_at_a_time - _t0_sensitivity_one_at_a_time) / Float64(N)
    print("MOJO_TIMING robustness::sensitivity_one_at_a_time", _ns_sensitivity_one_at_a_time, _acc_sensitivity_one_at_a_time)
    var _acc_morris_screening: Float64 = 0.0
    var _t0_morris_screening = perf_counter_ns()
    for _ in range(N):
        var _r_morris_screening = morris_screening(5, 5, 5, 0.5)
        _acc_morris_screening += Float64(len(_r_morris_screening))
    var _t1_morris_screening = perf_counter_ns()
    var _ns_morris_screening = Float64(_t1_morris_screening - _t0_morris_screening) / Float64(N)
    print("MOJO_TIMING robustness::morris_screening", _ns_morris_screening, _acc_morris_screening)
    var _acc_sobol_first_order_estimate: Float64 = 0.0
    var _t0_sobol_first_order_estimate = perf_counter_ns()
    for _ in range(N):
        var _r_sobol_first_order_estimate = sobol_first_order_estimate(5, 5, 5)
        _acc_sobol_first_order_estimate += Float64(len(_r_sobol_first_order_estimate))
    var _t1_sobol_first_order_estimate = perf_counter_ns()
    var _ns_sobol_first_order_estimate = Float64(_t1_sobol_first_order_estimate - _t0_sobol_first_order_estimate) / Float64(N)
    print("MOJO_TIMING robustness::sobol_first_order_estimate", _ns_sobol_first_order_estimate, _acc_sobol_first_order_estimate)
    var _acc_input_range_sweep: Float64 = 0.0
    var _t0_input_range_sweep = perf_counter_ns()
    for _ in range(N):
        var _r_input_range_sweep = input_range_sweep(_lf5, 5, 0.5, 0.5, 5, 5)
        _acc_input_range_sweep += Float64(len(_r_input_range_sweep))
    var _t1_input_range_sweep = perf_counter_ns()
    var _ns_input_range_sweep = Float64(_t1_input_range_sweep - _t0_input_range_sweep) / Float64(N)
    print("MOJO_TIMING robustness::input_range_sweep", _ns_input_range_sweep, _acc_input_range_sweep)
    var _acc_tornado_data: Float64 = 0.0
    var _t0_tornado_data = perf_counter_ns()
    for _ in range(N):
        var _r_tornado_data = tornado_data(_lf5, _lf5, 5)
        _acc_tornado_data += Float64(len(_r_tornado_data))
    var _t1_tornado_data = perf_counter_ns()
    var _ns_tornado_data = Float64(_t1_tornado_data - _t0_tornado_data) / Float64(N)
    print("MOJO_TIMING robustness::tornado_data", _ns_tornado_data, _acc_tornado_data)
    var _acc_robustness_score: Float64 = 0.0
    var _t0_robustness_score = perf_counter_ns()
    for _ in range(N):
        _acc_robustness_score += robustness_score(_lf5)
    var _t1_robustness_score = perf_counter_ns()
    var _ns_robustness_score = Float64(_t1_robustness_score - _t0_robustness_score) / Float64(N)
    print("MOJO_TIMING robustness::robustness_score", _ns_robustness_score, _acc_robustness_score)
