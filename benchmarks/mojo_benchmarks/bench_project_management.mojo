"""bench_project_management.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from project_management import earned_value, schedule_variance, cost_variance, schedule_performance_index, cost_performance_index, estimate_at_completion, estimate_to_complete, variance_at_completion, to_complete_performance_index, critical_path_duration, float_time, pert_estimate
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

    var _acc_earned_value: Float64 = 0.0
    var _t0_earned_value = perf_counter_ns()
    for _ in range(N):
        _acc_earned_value += earned_value(0.5, 0.5)
    var _t1_earned_value = perf_counter_ns()
    var _ns_earned_value = Float64(_t1_earned_value - _t0_earned_value) / Float64(N)
    print("MOJO_TIMING project_management::earned_value", _ns_earned_value, _acc_earned_value)
    var _acc_schedule_variance: Float64 = 0.0
    var _t0_schedule_variance = perf_counter_ns()
    for _ in range(N):
        _acc_schedule_variance += schedule_variance(0.5, 0.5)
    var _t1_schedule_variance = perf_counter_ns()
    var _ns_schedule_variance = Float64(_t1_schedule_variance - _t0_schedule_variance) / Float64(N)
    print("MOJO_TIMING project_management::schedule_variance", _ns_schedule_variance, _acc_schedule_variance)
    var _acc_cost_variance: Float64 = 0.0
    var _t0_cost_variance = perf_counter_ns()
    for _ in range(N):
        _acc_cost_variance += cost_variance(0.5, 0.5)
    var _t1_cost_variance = perf_counter_ns()
    var _ns_cost_variance = Float64(_t1_cost_variance - _t0_cost_variance) / Float64(N)
    print("MOJO_TIMING project_management::cost_variance", _ns_cost_variance, _acc_cost_variance)
    var _acc_schedule_performance_index: Float64 = 0.0
    var _t0_schedule_performance_index = perf_counter_ns()
    for _ in range(N):
        _acc_schedule_performance_index += schedule_performance_index(0.5, 0.5)
    var _t1_schedule_performance_index = perf_counter_ns()
    var _ns_schedule_performance_index = Float64(_t1_schedule_performance_index - _t0_schedule_performance_index) / Float64(N)
    print("MOJO_TIMING project_management::schedule_performance_index", _ns_schedule_performance_index, _acc_schedule_performance_index)
    var _acc_cost_performance_index: Float64 = 0.0
    var _t0_cost_performance_index = perf_counter_ns()
    for _ in range(N):
        _acc_cost_performance_index += cost_performance_index(0.5, 0.5)
    var _t1_cost_performance_index = perf_counter_ns()
    var _ns_cost_performance_index = Float64(_t1_cost_performance_index - _t0_cost_performance_index) / Float64(N)
    print("MOJO_TIMING project_management::cost_performance_index", _ns_cost_performance_index, _acc_cost_performance_index)
    var _acc_estimate_at_completion: Float64 = 0.0
    var _t0_estimate_at_completion = perf_counter_ns()
    for _ in range(N):
        _acc_estimate_at_completion += estimate_at_completion(0.5, 0.5)
    var _t1_estimate_at_completion = perf_counter_ns()
    var _ns_estimate_at_completion = Float64(_t1_estimate_at_completion - _t0_estimate_at_completion) / Float64(N)
    print("MOJO_TIMING project_management::estimate_at_completion", _ns_estimate_at_completion, _acc_estimate_at_completion)
    var _acc_estimate_to_complete: Float64 = 0.0
    var _t0_estimate_to_complete = perf_counter_ns()
    for _ in range(N):
        _acc_estimate_to_complete += estimate_to_complete(0.5, 0.5)
    var _t1_estimate_to_complete = perf_counter_ns()
    var _ns_estimate_to_complete = Float64(_t1_estimate_to_complete - _t0_estimate_to_complete) / Float64(N)
    print("MOJO_TIMING project_management::estimate_to_complete", _ns_estimate_to_complete, _acc_estimate_to_complete)
    var _acc_variance_at_completion: Float64 = 0.0
    var _t0_variance_at_completion = perf_counter_ns()
    for _ in range(N):
        _acc_variance_at_completion += variance_at_completion(0.5, 0.5)
    var _t1_variance_at_completion = perf_counter_ns()
    var _ns_variance_at_completion = Float64(_t1_variance_at_completion - _t0_variance_at_completion) / Float64(N)
    print("MOJO_TIMING project_management::variance_at_completion", _ns_variance_at_completion, _acc_variance_at_completion)
    var _acc_to_complete_performance_index: Float64 = 0.0
    var _t0_to_complete_performance_index = perf_counter_ns()
    for _ in range(N):
        _acc_to_complete_performance_index += to_complete_performance_index(0.5, 0.5, 0.5)
    var _t1_to_complete_performance_index = perf_counter_ns()
    var _ns_to_complete_performance_index = Float64(_t1_to_complete_performance_index - _t0_to_complete_performance_index) / Float64(N)
    print("MOJO_TIMING project_management::to_complete_performance_index", _ns_to_complete_performance_index, _acc_to_complete_performance_index)
    var _acc_critical_path_duration: Float64 = 0.0
    var _t0_critical_path_duration = perf_counter_ns()
    for _ in range(N):
        _acc_critical_path_duration += critical_path_duration(0.5)
    var _t1_critical_path_duration = perf_counter_ns()
    var _ns_critical_path_duration = Float64(_t1_critical_path_duration - _t0_critical_path_duration) / Float64(N)
    print("MOJO_TIMING project_management::critical_path_duration", _ns_critical_path_duration, _acc_critical_path_duration)
    var _acc_float_time: Float64 = 0.0
    var _t0_float_time = perf_counter_ns()
    for _ in range(N):
        _acc_float_time += float_time(0.5, 0.5)
    var _t1_float_time = perf_counter_ns()
    var _ns_float_time = Float64(_t1_float_time - _t0_float_time) / Float64(N)
    print("MOJO_TIMING project_management::float_time", _ns_float_time, _acc_float_time)
    var _acc_pert_estimate: Float64 = 0.0
    var _t0_pert_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_pert_estimate += pert_estimate(0.5, 0.5, 0.5)
    var _t1_pert_estimate = perf_counter_ns()
    var _ns_pert_estimate = Float64(_t1_pert_estimate - _t0_pert_estimate) / Float64(N)
    print("MOJO_TIMING project_management::pert_estimate", _ns_pert_estimate, _acc_pert_estimate)
