"""bench_dimensions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dimensions import infer_from_samples, propagate, propagate_is_valid, validate_formula, can_sum, can_avg, aggregation_valid, role_for_dimension, dimension_name, dimension_from_role
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_infer_from_samples: Float64 = 0.0
    var _t0_infer_from_samples = perf_counter_ns()
    for _ in range(N):
        _acc_infer_from_samples += Float64(infer_from_samples(_lf5))
    var _t1_infer_from_samples = perf_counter_ns()
    var _ns_infer_from_samples = Float64(_t1_infer_from_samples - _t0_infer_from_samples) / Float64(N)
    print("MOJO_TIMING dimensions::infer_from_samples", _ns_infer_from_samples, _acc_infer_from_samples)
    var _result_infer_from_samples = infer_from_samples(_lf5)
    var _summary_infer_from_samples = _summary_int(_result_infer_from_samples)
    print("MOJO_RESULT dimensions::infer_from_samples", _summary_infer_from_samples)
    var _acc_propagate: Float64 = 0.0
    var _t0_propagate = perf_counter_ns()
    for _ in range(N):
        _acc_propagate += Float64(propagate("test", 5, 5))
    var _t1_propagate = perf_counter_ns()
    var _ns_propagate = Float64(_t1_propagate - _t0_propagate) / Float64(N)
    print("MOJO_TIMING dimensions::propagate", _ns_propagate, _acc_propagate)
    var _result_propagate = propagate("test", 5, 5)
    var _summary_propagate = _summary_int(_result_propagate)
    print("MOJO_RESULT dimensions::propagate", _summary_propagate)
    var _acc_propagate_is_valid: Float64 = 0.0
    var _t0_propagate_is_valid = perf_counter_ns()
    for _ in range(N):
        _acc_propagate_is_valid += Float64(propagate_is_valid("test", 5, 5))
    var _t1_propagate_is_valid = perf_counter_ns()
    var _ns_propagate_is_valid = Float64(_t1_propagate_is_valid - _t0_propagate_is_valid) / Float64(N)
    print("MOJO_TIMING dimensions::propagate_is_valid", _ns_propagate_is_valid, _acc_propagate_is_valid)
    var _result_propagate_is_valid = propagate_is_valid("test", 5, 5)
    var _summary_propagate_is_valid = _summary_bool(_result_propagate_is_valid)
    print("MOJO_RESULT dimensions::propagate_is_valid", _summary_propagate_is_valid)
    var _acc_validate_formula: Float64 = 0.0
    var _t0_validate_formula = perf_counter_ns()
    for _ in range(N):
        _acc_validate_formula += Float64(validate_formula("test", 5, 5, 5))
    var _t1_validate_formula = perf_counter_ns()
    var _ns_validate_formula = Float64(_t1_validate_formula - _t0_validate_formula) / Float64(N)
    print("MOJO_TIMING dimensions::validate_formula", _ns_validate_formula, _acc_validate_formula)
    var _result_validate_formula = validate_formula("test", 5, 5, 5)
    var _summary_validate_formula = _summary_bool(_result_validate_formula)
    print("MOJO_RESULT dimensions::validate_formula", _summary_validate_formula)
    var _acc_can_sum: Float64 = 0.0
    var _t0_can_sum = perf_counter_ns()
    for _ in range(N):
        _acc_can_sum += Float64(can_sum(5))
    var _t1_can_sum = perf_counter_ns()
    var _ns_can_sum = Float64(_t1_can_sum - _t0_can_sum) / Float64(N)
    print("MOJO_TIMING dimensions::can_sum", _ns_can_sum, _acc_can_sum)
    var _result_can_sum = can_sum(5)
    var _summary_can_sum = _summary_bool(_result_can_sum)
    print("MOJO_RESULT dimensions::can_sum", _summary_can_sum)
    var _acc_can_avg: Float64 = 0.0
    var _t0_can_avg = perf_counter_ns()
    for _ in range(N):
        _acc_can_avg += Float64(can_avg(5))
    var _t1_can_avg = perf_counter_ns()
    var _ns_can_avg = Float64(_t1_can_avg - _t0_can_avg) / Float64(N)
    print("MOJO_TIMING dimensions::can_avg", _ns_can_avg, _acc_can_avg)
    var _result_can_avg = can_avg(5)
    var _summary_can_avg = _summary_bool(_result_can_avg)
    print("MOJO_RESULT dimensions::can_avg", _summary_can_avg)
    var _acc_aggregation_valid: Float64 = 0.0
    var _t0_aggregation_valid = perf_counter_ns()
    for _ in range(N):
        _acc_aggregation_valid += Float64(aggregation_valid("test", 5))
    var _t1_aggregation_valid = perf_counter_ns()
    var _ns_aggregation_valid = Float64(_t1_aggregation_valid - _t0_aggregation_valid) / Float64(N)
    print("MOJO_TIMING dimensions::aggregation_valid", _ns_aggregation_valid, _acc_aggregation_valid)
    var _result_aggregation_valid = aggregation_valid("test", 5)
    var _summary_aggregation_valid = _summary_bool(_result_aggregation_valid)
    print("MOJO_RESULT dimensions::aggregation_valid", _summary_aggregation_valid)
    var _acc_role_for_dimension: Float64 = 0.0
    var _t0_role_for_dimension = perf_counter_ns()
    for _ in range(N):
        _ = role_for_dimension(5)
    var _t1_role_for_dimension = perf_counter_ns()
    var _ns_role_for_dimension = Float64(_t1_role_for_dimension - _t0_role_for_dimension) / Float64(N)
    print("MOJO_TIMING dimensions::role_for_dimension", _ns_role_for_dimension, _acc_role_for_dimension)
    var _result_role_for_dimension = role_for_dimension(5)
    var _summary_role_for_dimension = _summary_string(_result_role_for_dimension)
    print("MOJO_RESULT dimensions::role_for_dimension", _summary_role_for_dimension)
    var _acc_dimension_name: Float64 = 0.0
    var _t0_dimension_name = perf_counter_ns()
    for _ in range(N):
        _ = dimension_name(5)
    var _t1_dimension_name = perf_counter_ns()
    var _ns_dimension_name = Float64(_t1_dimension_name - _t0_dimension_name) / Float64(N)
    print("MOJO_TIMING dimensions::dimension_name", _ns_dimension_name, _acc_dimension_name)
    var _result_dimension_name = dimension_name(5)
    var _summary_dimension_name = _summary_string(_result_dimension_name)
    print("MOJO_RESULT dimensions::dimension_name", _summary_dimension_name)
    var _acc_dimension_from_role: Float64 = 0.0
    var _t0_dimension_from_role = perf_counter_ns()
    for _ in range(N):
        _acc_dimension_from_role += Float64(dimension_from_role("test"))
    var _t1_dimension_from_role = perf_counter_ns()
    var _ns_dimension_from_role = Float64(_t1_dimension_from_role - _t0_dimension_from_role) / Float64(N)
    print("MOJO_TIMING dimensions::dimension_from_role", _ns_dimension_from_role, _acc_dimension_from_role)
    var _result_dimension_from_role = dimension_from_role("test")
    var _summary_dimension_from_role = _summary_int(_result_dimension_from_role)
    print("MOJO_RESULT dimensions::dimension_from_role", _summary_dimension_from_role)
