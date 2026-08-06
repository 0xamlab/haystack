"""bench_operations_research.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from operations_research import simplex_objective_value_2, simplex_objective_value_3, transportation_cost, total_transportation_cost_2x2, assignment_cost_3, eoq_quantity, eoq_total_cost, newsvendor_critical_ratio, little_law_l, little_law_w, utilization_factor, mm1_expected_queue_length, mm1_expected_wait_time
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

    var _acc_simplex_objective_value_2: Float64 = 0.0
    var _t0_simplex_objective_value_2 = perf_counter_ns()
    for _ in range(N):
        _acc_simplex_objective_value_2 += simplex_objective_value_2(0.5, 0.5, 0.5, 0.5)
    var _t1_simplex_objective_value_2 = perf_counter_ns()
    var _ns_simplex_objective_value_2 = Float64(_t1_simplex_objective_value_2 - _t0_simplex_objective_value_2) / Float64(N)
    print("MOJO_TIMING operations_research::simplex_objective_value_2", _ns_simplex_objective_value_2, _acc_simplex_objective_value_2)
    var _result_simplex_objective_value_2 = simplex_objective_value_2(0.5, 0.5, 0.5, 0.5)
    var _summary_simplex_objective_value_2 = _summary_float64(_result_simplex_objective_value_2)
    print("MOJO_RESULT operations_research::simplex_objective_value_2", _summary_simplex_objective_value_2)
    var _acc_simplex_objective_value_3: Float64 = 0.0
    var _t0_simplex_objective_value_3 = perf_counter_ns()
    for _ in range(N):
        _acc_simplex_objective_value_3 += simplex_objective_value_3(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_simplex_objective_value_3 = perf_counter_ns()
    var _ns_simplex_objective_value_3 = Float64(_t1_simplex_objective_value_3 - _t0_simplex_objective_value_3) / Float64(N)
    print("MOJO_TIMING operations_research::simplex_objective_value_3", _ns_simplex_objective_value_3, _acc_simplex_objective_value_3)
    var _result_simplex_objective_value_3 = simplex_objective_value_3(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_simplex_objective_value_3 = _summary_float64(_result_simplex_objective_value_3)
    print("MOJO_RESULT operations_research::simplex_objective_value_3", _summary_simplex_objective_value_3)
    var _acc_transportation_cost: Float64 = 0.0
    var _t0_transportation_cost = perf_counter_ns()
    for _ in range(N):
        _acc_transportation_cost += transportation_cost(0.5, 0.5)
    var _t1_transportation_cost = perf_counter_ns()
    var _ns_transportation_cost = Float64(_t1_transportation_cost - _t0_transportation_cost) / Float64(N)
    print("MOJO_TIMING operations_research::transportation_cost", _ns_transportation_cost, _acc_transportation_cost)
    var _result_transportation_cost = transportation_cost(0.5, 0.5)
    var _summary_transportation_cost = _summary_float64(_result_transportation_cost)
    print("MOJO_RESULT operations_research::transportation_cost", _summary_transportation_cost)
    var _acc_total_transportation_cost_2x2: Float64 = 0.0
    var _t0_total_transportation_cost_2x2 = perf_counter_ns()
    for _ in range(N):
        _acc_total_transportation_cost_2x2 += total_transportation_cost_2x2(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_total_transportation_cost_2x2 = perf_counter_ns()
    var _ns_total_transportation_cost_2x2 = Float64(_t1_total_transportation_cost_2x2 - _t0_total_transportation_cost_2x2) / Float64(N)
    print("MOJO_TIMING operations_research::total_transportation_cost_2x2", _ns_total_transportation_cost_2x2, _acc_total_transportation_cost_2x2)
    var _result_total_transportation_cost_2x2 = total_transportation_cost_2x2(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_total_transportation_cost_2x2 = _summary_float64(_result_total_transportation_cost_2x2)
    print("MOJO_RESULT operations_research::total_transportation_cost_2x2", _summary_total_transportation_cost_2x2)
    var _acc_assignment_cost_3: Float64 = 0.0
    var _t0_assignment_cost_3 = perf_counter_ns()
    for _ in range(N):
        _acc_assignment_cost_3 += assignment_cost_3(0.5, 0.5, 0.5)
    var _t1_assignment_cost_3 = perf_counter_ns()
    var _ns_assignment_cost_3 = Float64(_t1_assignment_cost_3 - _t0_assignment_cost_3) / Float64(N)
    print("MOJO_TIMING operations_research::assignment_cost_3", _ns_assignment_cost_3, _acc_assignment_cost_3)
    var _result_assignment_cost_3 = assignment_cost_3(0.5, 0.5, 0.5)
    var _summary_assignment_cost_3 = _summary_float64(_result_assignment_cost_3)
    print("MOJO_RESULT operations_research::assignment_cost_3", _summary_assignment_cost_3)
    var _acc_eoq_quantity: Float64 = 0.0
    var _t0_eoq_quantity = perf_counter_ns()
    for _ in range(N):
        _acc_eoq_quantity += eoq_quantity(0.5, 0.5, 0.5)
    var _t1_eoq_quantity = perf_counter_ns()
    var _ns_eoq_quantity = Float64(_t1_eoq_quantity - _t0_eoq_quantity) / Float64(N)
    print("MOJO_TIMING operations_research::eoq_quantity", _ns_eoq_quantity, _acc_eoq_quantity)
    var _result_eoq_quantity = eoq_quantity(0.5, 0.5, 0.5)
    var _summary_eoq_quantity = _summary_float64(_result_eoq_quantity)
    print("MOJO_RESULT operations_research::eoq_quantity", _summary_eoq_quantity)
    var _acc_eoq_total_cost: Float64 = 0.0
    var _t0_eoq_total_cost = perf_counter_ns()
    for _ in range(N):
        _acc_eoq_total_cost += eoq_total_cost(0.5, 0.5, 0.5)
    var _t1_eoq_total_cost = perf_counter_ns()
    var _ns_eoq_total_cost = Float64(_t1_eoq_total_cost - _t0_eoq_total_cost) / Float64(N)
    print("MOJO_TIMING operations_research::eoq_total_cost", _ns_eoq_total_cost, _acc_eoq_total_cost)
    var _result_eoq_total_cost = eoq_total_cost(0.5, 0.5, 0.5)
    var _summary_eoq_total_cost = _summary_float64(_result_eoq_total_cost)
    print("MOJO_RESULT operations_research::eoq_total_cost", _summary_eoq_total_cost)
    var _acc_newsvendor_critical_ratio: Float64 = 0.0
    var _t0_newsvendor_critical_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_newsvendor_critical_ratio += newsvendor_critical_ratio(0.5, 0.5)
    var _t1_newsvendor_critical_ratio = perf_counter_ns()
    var _ns_newsvendor_critical_ratio = Float64(_t1_newsvendor_critical_ratio - _t0_newsvendor_critical_ratio) / Float64(N)
    print("MOJO_TIMING operations_research::newsvendor_critical_ratio", _ns_newsvendor_critical_ratio, _acc_newsvendor_critical_ratio)
    var _result_newsvendor_critical_ratio = newsvendor_critical_ratio(0.5, 0.5)
    var _summary_newsvendor_critical_ratio = _summary_float64(_result_newsvendor_critical_ratio)
    print("MOJO_RESULT operations_research::newsvendor_critical_ratio", _summary_newsvendor_critical_ratio)
    var _acc_little_law_l: Float64 = 0.0
    var _t0_little_law_l = perf_counter_ns()
    for _ in range(N):
        _acc_little_law_l += little_law_l(0.5, 0.5)
    var _t1_little_law_l = perf_counter_ns()
    var _ns_little_law_l = Float64(_t1_little_law_l - _t0_little_law_l) / Float64(N)
    print("MOJO_TIMING operations_research::little_law_l", _ns_little_law_l, _acc_little_law_l)
    var _result_little_law_l = little_law_l(0.5, 0.5)
    var _summary_little_law_l = _summary_float64(_result_little_law_l)
    print("MOJO_RESULT operations_research::little_law_l", _summary_little_law_l)
    var _acc_little_law_w: Float64 = 0.0
    var _t0_little_law_w = perf_counter_ns()
    for _ in range(N):
        _acc_little_law_w += little_law_w(0.5, 0.5)
    var _t1_little_law_w = perf_counter_ns()
    var _ns_little_law_w = Float64(_t1_little_law_w - _t0_little_law_w) / Float64(N)
    print("MOJO_TIMING operations_research::little_law_w", _ns_little_law_w, _acc_little_law_w)
    var _result_little_law_w = little_law_w(0.5, 0.5)
    var _summary_little_law_w = _summary_float64(_result_little_law_w)
    print("MOJO_RESULT operations_research::little_law_w", _summary_little_law_w)
    var _acc_utilization_factor: Float64 = 0.0
    var _t0_utilization_factor = perf_counter_ns()
    for _ in range(N):
        _acc_utilization_factor += utilization_factor(0.5, 0.5)
    var _t1_utilization_factor = perf_counter_ns()
    var _ns_utilization_factor = Float64(_t1_utilization_factor - _t0_utilization_factor) / Float64(N)
    print("MOJO_TIMING operations_research::utilization_factor", _ns_utilization_factor, _acc_utilization_factor)
    var _result_utilization_factor = utilization_factor(0.5, 0.5)
    var _summary_utilization_factor = _summary_float64(_result_utilization_factor)
    print("MOJO_RESULT operations_research::utilization_factor", _summary_utilization_factor)
    var _acc_mm1_expected_queue_length: Float64 = 0.0
    var _t0_mm1_expected_queue_length = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_expected_queue_length += mm1_expected_queue_length(0.5)
    var _t1_mm1_expected_queue_length = perf_counter_ns()
    var _ns_mm1_expected_queue_length = Float64(_t1_mm1_expected_queue_length - _t0_mm1_expected_queue_length) / Float64(N)
    print("MOJO_TIMING operations_research::mm1_expected_queue_length", _ns_mm1_expected_queue_length, _acc_mm1_expected_queue_length)
    var _result_mm1_expected_queue_length = mm1_expected_queue_length(0.5)
    var _summary_mm1_expected_queue_length = _summary_float64(_result_mm1_expected_queue_length)
    print("MOJO_RESULT operations_research::mm1_expected_queue_length", _summary_mm1_expected_queue_length)
    var _acc_mm1_expected_wait_time: Float64 = 0.0
    var _t0_mm1_expected_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_expected_wait_time += mm1_expected_wait_time(0.5, 0.5)
    var _t1_mm1_expected_wait_time = perf_counter_ns()
    var _ns_mm1_expected_wait_time = Float64(_t1_mm1_expected_wait_time - _t0_mm1_expected_wait_time) / Float64(N)
    print("MOJO_TIMING operations_research::mm1_expected_wait_time", _ns_mm1_expected_wait_time, _acc_mm1_expected_wait_time)
    var _result_mm1_expected_wait_time = mm1_expected_wait_time(0.5, 0.5)
    var _summary_mm1_expected_wait_time = _summary_float64(_result_mm1_expected_wait_time)
    print("MOJO_RESULT operations_research::mm1_expected_wait_time", _summary_mm1_expected_wait_time)
