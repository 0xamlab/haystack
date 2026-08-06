"""bench_project_management.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from project_management import earned_value, schedule_variance, cost_variance, schedule_performance_index, cost_performance_index, estimate_at_completion, estimate_to_complete, variance_at_completion, to_complete_performance_index, critical_path_duration, float_time, pert_estimate
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_earned_value = earned_value(0.5, 0.5)
    var _summary_earned_value = _summary_float64(_result_earned_value)
    print("MOJO_RESULT project_management::earned_value", _summary_earned_value)
    var _acc_schedule_variance: Float64 = 0.0
    var _t0_schedule_variance = perf_counter_ns()
    for _ in range(N):
        _acc_schedule_variance += schedule_variance(0.5, 0.5)
    var _t1_schedule_variance = perf_counter_ns()
    var _ns_schedule_variance = Float64(_t1_schedule_variance - _t0_schedule_variance) / Float64(N)
    print("MOJO_TIMING project_management::schedule_variance", _ns_schedule_variance, _acc_schedule_variance)
    var _result_schedule_variance = schedule_variance(0.5, 0.5)
    var _summary_schedule_variance = _summary_float64(_result_schedule_variance)
    print("MOJO_RESULT project_management::schedule_variance", _summary_schedule_variance)
    var _acc_cost_variance: Float64 = 0.0
    var _t0_cost_variance = perf_counter_ns()
    for _ in range(N):
        _acc_cost_variance += cost_variance(0.5, 0.5)
    var _t1_cost_variance = perf_counter_ns()
    var _ns_cost_variance = Float64(_t1_cost_variance - _t0_cost_variance) / Float64(N)
    print("MOJO_TIMING project_management::cost_variance", _ns_cost_variance, _acc_cost_variance)
    var _result_cost_variance = cost_variance(0.5, 0.5)
    var _summary_cost_variance = _summary_float64(_result_cost_variance)
    print("MOJO_RESULT project_management::cost_variance", _summary_cost_variance)
    var _acc_schedule_performance_index: Float64 = 0.0
    var _t0_schedule_performance_index = perf_counter_ns()
    for _ in range(N):
        _acc_schedule_performance_index += schedule_performance_index(0.5, 0.5)
    var _t1_schedule_performance_index = perf_counter_ns()
    var _ns_schedule_performance_index = Float64(_t1_schedule_performance_index - _t0_schedule_performance_index) / Float64(N)
    print("MOJO_TIMING project_management::schedule_performance_index", _ns_schedule_performance_index, _acc_schedule_performance_index)
    var _result_schedule_performance_index = schedule_performance_index(0.5, 0.5)
    var _summary_schedule_performance_index = _summary_float64(_result_schedule_performance_index)
    print("MOJO_RESULT project_management::schedule_performance_index", _summary_schedule_performance_index)
    var _acc_cost_performance_index: Float64 = 0.0
    var _t0_cost_performance_index = perf_counter_ns()
    for _ in range(N):
        _acc_cost_performance_index += cost_performance_index(0.5, 0.5)
    var _t1_cost_performance_index = perf_counter_ns()
    var _ns_cost_performance_index = Float64(_t1_cost_performance_index - _t0_cost_performance_index) / Float64(N)
    print("MOJO_TIMING project_management::cost_performance_index", _ns_cost_performance_index, _acc_cost_performance_index)
    var _result_cost_performance_index = cost_performance_index(0.5, 0.5)
    var _summary_cost_performance_index = _summary_float64(_result_cost_performance_index)
    print("MOJO_RESULT project_management::cost_performance_index", _summary_cost_performance_index)
    var _acc_estimate_at_completion: Float64 = 0.0
    var _t0_estimate_at_completion = perf_counter_ns()
    for _ in range(N):
        _acc_estimate_at_completion += estimate_at_completion(0.5, 0.5)
    var _t1_estimate_at_completion = perf_counter_ns()
    var _ns_estimate_at_completion = Float64(_t1_estimate_at_completion - _t0_estimate_at_completion) / Float64(N)
    print("MOJO_TIMING project_management::estimate_at_completion", _ns_estimate_at_completion, _acc_estimate_at_completion)
    var _result_estimate_at_completion = estimate_at_completion(0.5, 0.5)
    var _summary_estimate_at_completion = _summary_float64(_result_estimate_at_completion)
    print("MOJO_RESULT project_management::estimate_at_completion", _summary_estimate_at_completion)
    var _acc_estimate_to_complete: Float64 = 0.0
    var _t0_estimate_to_complete = perf_counter_ns()
    for _ in range(N):
        _acc_estimate_to_complete += estimate_to_complete(0.5, 0.5)
    var _t1_estimate_to_complete = perf_counter_ns()
    var _ns_estimate_to_complete = Float64(_t1_estimate_to_complete - _t0_estimate_to_complete) / Float64(N)
    print("MOJO_TIMING project_management::estimate_to_complete", _ns_estimate_to_complete, _acc_estimate_to_complete)
    var _result_estimate_to_complete = estimate_to_complete(0.5, 0.5)
    var _summary_estimate_to_complete = _summary_float64(_result_estimate_to_complete)
    print("MOJO_RESULT project_management::estimate_to_complete", _summary_estimate_to_complete)
    var _acc_variance_at_completion: Float64 = 0.0
    var _t0_variance_at_completion = perf_counter_ns()
    for _ in range(N):
        _acc_variance_at_completion += variance_at_completion(0.5, 0.5)
    var _t1_variance_at_completion = perf_counter_ns()
    var _ns_variance_at_completion = Float64(_t1_variance_at_completion - _t0_variance_at_completion) / Float64(N)
    print("MOJO_TIMING project_management::variance_at_completion", _ns_variance_at_completion, _acc_variance_at_completion)
    var _result_variance_at_completion = variance_at_completion(0.5, 0.5)
    var _summary_variance_at_completion = _summary_float64(_result_variance_at_completion)
    print("MOJO_RESULT project_management::variance_at_completion", _summary_variance_at_completion)
    var _acc_to_complete_performance_index: Float64 = 0.0
    var _t0_to_complete_performance_index = perf_counter_ns()
    for _ in range(N):
        _acc_to_complete_performance_index += to_complete_performance_index(0.5, 0.5, 0.5)
    var _t1_to_complete_performance_index = perf_counter_ns()
    var _ns_to_complete_performance_index = Float64(_t1_to_complete_performance_index - _t0_to_complete_performance_index) / Float64(N)
    print("MOJO_TIMING project_management::to_complete_performance_index", _ns_to_complete_performance_index, _acc_to_complete_performance_index)
    var _result_to_complete_performance_index = to_complete_performance_index(0.5, 0.5, 0.5)
    var _summary_to_complete_performance_index = _summary_float64(_result_to_complete_performance_index)
    print("MOJO_RESULT project_management::to_complete_performance_index", _summary_to_complete_performance_index)
    var _acc_critical_path_duration: Float64 = 0.0
    var _t0_critical_path_duration = perf_counter_ns()
    for _ in range(N):
        _acc_critical_path_duration += critical_path_duration(0.5)
    var _t1_critical_path_duration = perf_counter_ns()
    var _ns_critical_path_duration = Float64(_t1_critical_path_duration - _t0_critical_path_duration) / Float64(N)
    print("MOJO_TIMING project_management::critical_path_duration", _ns_critical_path_duration, _acc_critical_path_duration)
    var _result_critical_path_duration = critical_path_duration(0.5)
    var _summary_critical_path_duration = _summary_float64(_result_critical_path_duration)
    print("MOJO_RESULT project_management::critical_path_duration", _summary_critical_path_duration)
    var _acc_float_time: Float64 = 0.0
    var _t0_float_time = perf_counter_ns()
    for _ in range(N):
        _acc_float_time += float_time(0.5, 0.5)
    var _t1_float_time = perf_counter_ns()
    var _ns_float_time = Float64(_t1_float_time - _t0_float_time) / Float64(N)
    print("MOJO_TIMING project_management::float_time", _ns_float_time, _acc_float_time)
    var _result_float_time = float_time(0.5, 0.5)
    var _summary_float_time = _summary_float64(_result_float_time)
    print("MOJO_RESULT project_management::float_time", _summary_float_time)
    var _acc_pert_estimate: Float64 = 0.0
    var _t0_pert_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_pert_estimate += pert_estimate(0.5, 0.5, 0.5)
    var _t1_pert_estimate = perf_counter_ns()
    var _ns_pert_estimate = Float64(_t1_pert_estimate - _t0_pert_estimate) / Float64(N)
    print("MOJO_TIMING project_management::pert_estimate", _ns_pert_estimate, _acc_pert_estimate)
    var _result_pert_estimate = pert_estimate(0.5, 0.5, 0.5)
    var _summary_pert_estimate = _summary_float64(_result_pert_estimate)
    print("MOJO_RESULT project_management::pert_estimate", _summary_pert_estimate)
