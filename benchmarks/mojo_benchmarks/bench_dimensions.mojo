"""bench_dimensions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dimensions import infer_from_samples, propagate, propagate_is_valid, validate_formula, can_sum, can_avg, aggregation_valid, role_for_dimension, dimension_name, dimension_from_role
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

    var _acc_infer_from_samples: Float64 = 0.0
    var _t0_infer_from_samples = perf_counter_ns()
    for _ in range(N):
        _acc_infer_from_samples += Float64(infer_from_samples(_lf5))
    var _t1_infer_from_samples = perf_counter_ns()
    var _ns_infer_from_samples = Float64(_t1_infer_from_samples - _t0_infer_from_samples) / Float64(N)
    print("MOJO_TIMING dimensions::infer_from_samples", _ns_infer_from_samples, _acc_infer_from_samples)
    var _acc_propagate: Float64 = 0.0
    var _t0_propagate = perf_counter_ns()
    for _ in range(N):
        _acc_propagate += Float64(propagate("test", 5, 5))
    var _t1_propagate = perf_counter_ns()
    var _ns_propagate = Float64(_t1_propagate - _t0_propagate) / Float64(N)
    print("MOJO_TIMING dimensions::propagate", _ns_propagate, _acc_propagate)
    var _acc_propagate_is_valid: Float64 = 0.0
    var _t0_propagate_is_valid = perf_counter_ns()
    for _ in range(N):
        _acc_propagate_is_valid += Float64(propagate_is_valid("test", 5, 5))
    var _t1_propagate_is_valid = perf_counter_ns()
    var _ns_propagate_is_valid = Float64(_t1_propagate_is_valid - _t0_propagate_is_valid) / Float64(N)
    print("MOJO_TIMING dimensions::propagate_is_valid", _ns_propagate_is_valid, _acc_propagate_is_valid)
    var _acc_validate_formula: Float64 = 0.0
    var _t0_validate_formula = perf_counter_ns()
    for _ in range(N):
        _acc_validate_formula += Float64(validate_formula("test", 5, 5, 5))
    var _t1_validate_formula = perf_counter_ns()
    var _ns_validate_formula = Float64(_t1_validate_formula - _t0_validate_formula) / Float64(N)
    print("MOJO_TIMING dimensions::validate_formula", _ns_validate_formula, _acc_validate_formula)
    var _acc_can_sum: Float64 = 0.0
    var _t0_can_sum = perf_counter_ns()
    for _ in range(N):
        _acc_can_sum += Float64(can_sum(5))
    var _t1_can_sum = perf_counter_ns()
    var _ns_can_sum = Float64(_t1_can_sum - _t0_can_sum) / Float64(N)
    print("MOJO_TIMING dimensions::can_sum", _ns_can_sum, _acc_can_sum)
    var _acc_can_avg: Float64 = 0.0
    var _t0_can_avg = perf_counter_ns()
    for _ in range(N):
        _acc_can_avg += Float64(can_avg(5))
    var _t1_can_avg = perf_counter_ns()
    var _ns_can_avg = Float64(_t1_can_avg - _t0_can_avg) / Float64(N)
    print("MOJO_TIMING dimensions::can_avg", _ns_can_avg, _acc_can_avg)
    var _acc_aggregation_valid: Float64 = 0.0
    var _t0_aggregation_valid = perf_counter_ns()
    for _ in range(N):
        _acc_aggregation_valid += Float64(aggregation_valid("test", 5))
    var _t1_aggregation_valid = perf_counter_ns()
    var _ns_aggregation_valid = Float64(_t1_aggregation_valid - _t0_aggregation_valid) / Float64(N)
    print("MOJO_TIMING dimensions::aggregation_valid", _ns_aggregation_valid, _acc_aggregation_valid)
    var _acc_role_for_dimension: Float64 = 0.0
    var _t0_role_for_dimension = perf_counter_ns()
    for _ in range(N):
        _ = role_for_dimension(5)
    var _t1_role_for_dimension = perf_counter_ns()
    var _ns_role_for_dimension = Float64(_t1_role_for_dimension - _t0_role_for_dimension) / Float64(N)
    print("MOJO_TIMING dimensions::role_for_dimension", _ns_role_for_dimension, _acc_role_for_dimension)
    var _acc_dimension_name: Float64 = 0.0
    var _t0_dimension_name = perf_counter_ns()
    for _ in range(N):
        _ = dimension_name(5)
    var _t1_dimension_name = perf_counter_ns()
    var _ns_dimension_name = Float64(_t1_dimension_name - _t0_dimension_name) / Float64(N)
    print("MOJO_TIMING dimensions::dimension_name", _ns_dimension_name, _acc_dimension_name)
    var _acc_dimension_from_role: Float64 = 0.0
    var _t0_dimension_from_role = perf_counter_ns()
    for _ in range(N):
        _acc_dimension_from_role += Float64(dimension_from_role("test"))
    var _t1_dimension_from_role = perf_counter_ns()
    var _ns_dimension_from_role = Float64(_t1_dimension_from_role - _t0_dimension_from_role) / Float64(N)
    print("MOJO_TIMING dimensions::dimension_from_role", _ns_dimension_from_role, _acc_dimension_from_role)
