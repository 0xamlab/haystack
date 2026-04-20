"""bench_online_learning.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from online_learning import exponential_moving_average, exponential_moving_variance, river_sgd_update, perceptron_update, passive_aggressive_step, adagrad_online_update, ftrl_step, streaming_mean_update, streaming_variance_update, concept_drift_ddm_error
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

    var _acc_exponential_moving_average: Float64 = 0.0
    var _t0_exponential_moving_average = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_moving_average += exponential_moving_average(0.5, 0.5, 0.5)
    var _t1_exponential_moving_average = perf_counter_ns()
    var _ns_exponential_moving_average = Float64(_t1_exponential_moving_average - _t0_exponential_moving_average) / Float64(N)
    print("MOJO_TIMING online_learning::exponential_moving_average", _ns_exponential_moving_average, _acc_exponential_moving_average)
    var _acc_exponential_moving_variance: Float64 = 0.0
    var _t0_exponential_moving_variance = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_moving_variance += exponential_moving_variance(0.5, 0.5, 0.5, 0.5)
    var _t1_exponential_moving_variance = perf_counter_ns()
    var _ns_exponential_moving_variance = Float64(_t1_exponential_moving_variance - _t0_exponential_moving_variance) / Float64(N)
    print("MOJO_TIMING online_learning::exponential_moving_variance", _ns_exponential_moving_variance, _acc_exponential_moving_variance)
    var _acc_river_sgd_update: Float64 = 0.0
    var _t0_river_sgd_update = perf_counter_ns()
    for _ in range(N):
        _acc_river_sgd_update += river_sgd_update(0.5, 0.5, 0.5)
    var _t1_river_sgd_update = perf_counter_ns()
    var _ns_river_sgd_update = Float64(_t1_river_sgd_update - _t0_river_sgd_update) / Float64(N)
    print("MOJO_TIMING online_learning::river_sgd_update", _ns_river_sgd_update, _acc_river_sgd_update)
    var _acc_perceptron_update: Float64 = 0.0
    var _t0_perceptron_update = perf_counter_ns()
    for _ in range(N):
        _acc_perceptron_update += perceptron_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_perceptron_update = perf_counter_ns()
    var _ns_perceptron_update = Float64(_t1_perceptron_update - _t0_perceptron_update) / Float64(N)
    print("MOJO_TIMING online_learning::perceptron_update", _ns_perceptron_update, _acc_perceptron_update)
    var _acc_passive_aggressive_step: Float64 = 0.0
    var _t0_passive_aggressive_step = perf_counter_ns()
    for _ in range(N):
        _acc_passive_aggressive_step += passive_aggressive_step(0.5, 0.5, 0.5)
    var _t1_passive_aggressive_step = perf_counter_ns()
    var _ns_passive_aggressive_step = Float64(_t1_passive_aggressive_step - _t0_passive_aggressive_step) / Float64(N)
    print("MOJO_TIMING online_learning::passive_aggressive_step", _ns_passive_aggressive_step, _acc_passive_aggressive_step)
    var _acc_adagrad_online_update: Float64 = 0.0
    var _t0_adagrad_online_update = perf_counter_ns()
    for _ in range(N):
        _acc_adagrad_online_update += adagrad_online_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adagrad_online_update = perf_counter_ns()
    var _ns_adagrad_online_update = Float64(_t1_adagrad_online_update - _t0_adagrad_online_update) / Float64(N)
    print("MOJO_TIMING online_learning::adagrad_online_update", _ns_adagrad_online_update, _acc_adagrad_online_update)
    var _acc_ftrl_step: Float64 = 0.0
    var _t0_ftrl_step = perf_counter_ns()
    for _ in range(N):
        _acc_ftrl_step += ftrl_step(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_ftrl_step = perf_counter_ns()
    var _ns_ftrl_step = Float64(_t1_ftrl_step - _t0_ftrl_step) / Float64(N)
    print("MOJO_TIMING online_learning::ftrl_step", _ns_ftrl_step, _acc_ftrl_step)
    var _acc_streaming_mean_update: Float64 = 0.0
    var _t0_streaming_mean_update = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_mean_update += streaming_mean_update(0.5, 0.5, 0.5)
    var _t1_streaming_mean_update = perf_counter_ns()
    var _ns_streaming_mean_update = Float64(_t1_streaming_mean_update - _t0_streaming_mean_update) / Float64(N)
    print("MOJO_TIMING online_learning::streaming_mean_update", _ns_streaming_mean_update, _acc_streaming_mean_update)
    var _acc_streaming_variance_update: Float64 = 0.0
    var _t0_streaming_variance_update = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_variance_update += streaming_variance_update(0.5, 0.5, 0.5, 0.5)
    var _t1_streaming_variance_update = perf_counter_ns()
    var _ns_streaming_variance_update = Float64(_t1_streaming_variance_update - _t0_streaming_variance_update) / Float64(N)
    print("MOJO_TIMING online_learning::streaming_variance_update", _ns_streaming_variance_update, _acc_streaming_variance_update)
    var _acc_concept_drift_ddm_error: Float64 = 0.0
    var _t0_concept_drift_ddm_error = perf_counter_ns()
    for _ in range(N):
        _acc_concept_drift_ddm_error += concept_drift_ddm_error(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_concept_drift_ddm_error = perf_counter_ns()
    var _ns_concept_drift_ddm_error = Float64(_t1_concept_drift_ddm_error - _t0_concept_drift_ddm_error) / Float64(N)
    print("MOJO_TIMING online_learning::concept_drift_ddm_error", _ns_concept_drift_ddm_error, _acc_concept_drift_ddm_error)
