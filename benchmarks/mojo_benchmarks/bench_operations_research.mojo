"""bench_operations_research.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from operations_research import simplex_objective_value_2, simplex_objective_value_3, transportation_cost, total_transportation_cost_2x2, assignment_cost_3, eoq_quantity, eoq_total_cost, newsvendor_critical_ratio, little_law_l, little_law_w, utilization_factor, mm1_expected_queue_length, mm1_expected_wait_time
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

    var _acc_simplex_objective_value_2: Float64 = 0.0
    var _t0_simplex_objective_value_2 = perf_counter_ns()
    for _ in range(N):
        _acc_simplex_objective_value_2 += simplex_objective_value_2(0.5, 0.5, 0.5, 0.5)
    var _t1_simplex_objective_value_2 = perf_counter_ns()
    var _ns_simplex_objective_value_2 = Float64(_t1_simplex_objective_value_2 - _t0_simplex_objective_value_2) / Float64(N)
    print("MOJO_TIMING operations_research::simplex_objective_value_2", _ns_simplex_objective_value_2, _acc_simplex_objective_value_2)
    var _acc_simplex_objective_value_3: Float64 = 0.0
    var _t0_simplex_objective_value_3 = perf_counter_ns()
    for _ in range(N):
        _acc_simplex_objective_value_3 += simplex_objective_value_3(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_simplex_objective_value_3 = perf_counter_ns()
    var _ns_simplex_objective_value_3 = Float64(_t1_simplex_objective_value_3 - _t0_simplex_objective_value_3) / Float64(N)
    print("MOJO_TIMING operations_research::simplex_objective_value_3", _ns_simplex_objective_value_3, _acc_simplex_objective_value_3)
    var _acc_transportation_cost: Float64 = 0.0
    var _t0_transportation_cost = perf_counter_ns()
    for _ in range(N):
        _acc_transportation_cost += transportation_cost(0.5, 0.5)
    var _t1_transportation_cost = perf_counter_ns()
    var _ns_transportation_cost = Float64(_t1_transportation_cost - _t0_transportation_cost) / Float64(N)
    print("MOJO_TIMING operations_research::transportation_cost", _ns_transportation_cost, _acc_transportation_cost)
    var _acc_total_transportation_cost_2x2: Float64 = 0.0
    var _t0_total_transportation_cost_2x2 = perf_counter_ns()
    for _ in range(N):
        _acc_total_transportation_cost_2x2 += total_transportation_cost_2x2(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_total_transportation_cost_2x2 = perf_counter_ns()
    var _ns_total_transportation_cost_2x2 = Float64(_t1_total_transportation_cost_2x2 - _t0_total_transportation_cost_2x2) / Float64(N)
    print("MOJO_TIMING operations_research::total_transportation_cost_2x2", _ns_total_transportation_cost_2x2, _acc_total_transportation_cost_2x2)
    var _acc_assignment_cost_3: Float64 = 0.0
    var _t0_assignment_cost_3 = perf_counter_ns()
    for _ in range(N):
        _acc_assignment_cost_3 += assignment_cost_3(0.5, 0.5, 0.5)
    var _t1_assignment_cost_3 = perf_counter_ns()
    var _ns_assignment_cost_3 = Float64(_t1_assignment_cost_3 - _t0_assignment_cost_3) / Float64(N)
    print("MOJO_TIMING operations_research::assignment_cost_3", _ns_assignment_cost_3, _acc_assignment_cost_3)
    var _acc_eoq_quantity: Float64 = 0.0
    var _t0_eoq_quantity = perf_counter_ns()
    for _ in range(N):
        _acc_eoq_quantity += eoq_quantity(0.5, 0.5, 0.5)
    var _t1_eoq_quantity = perf_counter_ns()
    var _ns_eoq_quantity = Float64(_t1_eoq_quantity - _t0_eoq_quantity) / Float64(N)
    print("MOJO_TIMING operations_research::eoq_quantity", _ns_eoq_quantity, _acc_eoq_quantity)
    var _acc_eoq_total_cost: Float64 = 0.0
    var _t0_eoq_total_cost = perf_counter_ns()
    for _ in range(N):
        _acc_eoq_total_cost += eoq_total_cost(0.5, 0.5, 0.5)
    var _t1_eoq_total_cost = perf_counter_ns()
    var _ns_eoq_total_cost = Float64(_t1_eoq_total_cost - _t0_eoq_total_cost) / Float64(N)
    print("MOJO_TIMING operations_research::eoq_total_cost", _ns_eoq_total_cost, _acc_eoq_total_cost)
    var _acc_newsvendor_critical_ratio: Float64 = 0.0
    var _t0_newsvendor_critical_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_newsvendor_critical_ratio += newsvendor_critical_ratio(0.5, 0.5)
    var _t1_newsvendor_critical_ratio = perf_counter_ns()
    var _ns_newsvendor_critical_ratio = Float64(_t1_newsvendor_critical_ratio - _t0_newsvendor_critical_ratio) / Float64(N)
    print("MOJO_TIMING operations_research::newsvendor_critical_ratio", _ns_newsvendor_critical_ratio, _acc_newsvendor_critical_ratio)
    var _acc_little_law_l: Float64 = 0.0
    var _t0_little_law_l = perf_counter_ns()
    for _ in range(N):
        _acc_little_law_l += little_law_l(0.5, 0.5)
    var _t1_little_law_l = perf_counter_ns()
    var _ns_little_law_l = Float64(_t1_little_law_l - _t0_little_law_l) / Float64(N)
    print("MOJO_TIMING operations_research::little_law_l", _ns_little_law_l, _acc_little_law_l)
    var _acc_little_law_w: Float64 = 0.0
    var _t0_little_law_w = perf_counter_ns()
    for _ in range(N):
        _acc_little_law_w += little_law_w(0.5, 0.5)
    var _t1_little_law_w = perf_counter_ns()
    var _ns_little_law_w = Float64(_t1_little_law_w - _t0_little_law_w) / Float64(N)
    print("MOJO_TIMING operations_research::little_law_w", _ns_little_law_w, _acc_little_law_w)
    var _acc_utilization_factor: Float64 = 0.0
    var _t0_utilization_factor = perf_counter_ns()
    for _ in range(N):
        _acc_utilization_factor += utilization_factor(0.5, 0.5)
    var _t1_utilization_factor = perf_counter_ns()
    var _ns_utilization_factor = Float64(_t1_utilization_factor - _t0_utilization_factor) / Float64(N)
    print("MOJO_TIMING operations_research::utilization_factor", _ns_utilization_factor, _acc_utilization_factor)
    var _acc_mm1_expected_queue_length: Float64 = 0.0
    var _t0_mm1_expected_queue_length = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_expected_queue_length += mm1_expected_queue_length(0.5)
    var _t1_mm1_expected_queue_length = perf_counter_ns()
    var _ns_mm1_expected_queue_length = Float64(_t1_mm1_expected_queue_length - _t0_mm1_expected_queue_length) / Float64(N)
    print("MOJO_TIMING operations_research::mm1_expected_queue_length", _ns_mm1_expected_queue_length, _acc_mm1_expected_queue_length)
    var _acc_mm1_expected_wait_time: Float64 = 0.0
    var _t0_mm1_expected_wait_time = perf_counter_ns()
    for _ in range(N):
        _acc_mm1_expected_wait_time += mm1_expected_wait_time(0.5, 0.5)
    var _t1_mm1_expected_wait_time = perf_counter_ns()
    var _ns_mm1_expected_wait_time = Float64(_t1_mm1_expected_wait_time - _t0_mm1_expected_wait_time) / Float64(N)
    print("MOJO_TIMING operations_research::mm1_expected_wait_time", _ns_mm1_expected_wait_time, _acc_mm1_expected_wait_time)
