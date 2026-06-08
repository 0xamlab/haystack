"""bench_set_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from set_ops import set_union, set_intersection, set_difference, set_symmetric_difference, is_subset, is_superset, set_equals, power_set_size, jaccard_index, to_set, set_contains, set_cardinality
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

    var _acc_set_union: Float64 = 0.0
    var _t0_set_union = perf_counter_ns()
    for _ in range(N):
        var _r_set_union = set_union(_li5, _li5)
        _acc_set_union += Float64(len(_r_set_union))
    var _t1_set_union = perf_counter_ns()
    var _ns_set_union = Float64(_t1_set_union - _t0_set_union) / Float64(N)
    print("MOJO_TIMING set_ops::set_union", _ns_set_union, _acc_set_union)
    var _result_set_union = set_union(_li5, _li5)
    var _summary_set_union = _summary_list_int(_result_set_union)
    print("MOJO_RESULT set_ops::set_union", _summary_set_union)
    var _acc_set_intersection: Float64 = 0.0
    var _t0_set_intersection = perf_counter_ns()
    for _ in range(N):
        var _r_set_intersection = set_intersection(_li5, _li5)
        _acc_set_intersection += Float64(len(_r_set_intersection))
    var _t1_set_intersection = perf_counter_ns()
    var _ns_set_intersection = Float64(_t1_set_intersection - _t0_set_intersection) / Float64(N)
    print("MOJO_TIMING set_ops::set_intersection", _ns_set_intersection, _acc_set_intersection)
    var _result_set_intersection = set_intersection(_li5, _li5)
    var _summary_set_intersection = _summary_list_int(_result_set_intersection)
    print("MOJO_RESULT set_ops::set_intersection", _summary_set_intersection)
    var _acc_set_difference: Float64 = 0.0
    var _t0_set_difference = perf_counter_ns()
    for _ in range(N):
        var _r_set_difference = set_difference(_li5, _li5)
        _acc_set_difference += Float64(len(_r_set_difference))
    var _t1_set_difference = perf_counter_ns()
    var _ns_set_difference = Float64(_t1_set_difference - _t0_set_difference) / Float64(N)
    print("MOJO_TIMING set_ops::set_difference", _ns_set_difference, _acc_set_difference)
    var _result_set_difference = set_difference(_li5, _li5)
    var _summary_set_difference = _summary_list_int(_result_set_difference)
    print("MOJO_RESULT set_ops::set_difference", _summary_set_difference)
    var _acc_set_symmetric_difference: Float64 = 0.0
    var _t0_set_symmetric_difference = perf_counter_ns()
    for _ in range(N):
        var _r_set_symmetric_difference = set_symmetric_difference(_li5, _li5)
        _acc_set_symmetric_difference += Float64(len(_r_set_symmetric_difference))
    var _t1_set_symmetric_difference = perf_counter_ns()
    var _ns_set_symmetric_difference = Float64(_t1_set_symmetric_difference - _t0_set_symmetric_difference) / Float64(N)
    print("MOJO_TIMING set_ops::set_symmetric_difference", _ns_set_symmetric_difference, _acc_set_symmetric_difference)
    var _result_set_symmetric_difference = set_symmetric_difference(_li5, _li5)
    var _summary_set_symmetric_difference = _summary_list_int(_result_set_symmetric_difference)
    print("MOJO_RESULT set_ops::set_symmetric_difference", _summary_set_symmetric_difference)
    var _acc_is_subset: Float64 = 0.0
    var _t0_is_subset = perf_counter_ns()
    for _ in range(N):
        _acc_is_subset += Float64(is_subset(_li5, _li5))
    var _t1_is_subset = perf_counter_ns()
    var _ns_is_subset = Float64(_t1_is_subset - _t0_is_subset) / Float64(N)
    print("MOJO_TIMING set_ops::is_subset", _ns_is_subset, _acc_is_subset)
    var _result_is_subset = is_subset(_li5, _li5)
    var _summary_is_subset = _summary_bool(_result_is_subset)
    print("MOJO_RESULT set_ops::is_subset", _summary_is_subset)
    var _acc_is_superset: Float64 = 0.0
    var _t0_is_superset = perf_counter_ns()
    for _ in range(N):
        _acc_is_superset += Float64(is_superset(_li5, _li5))
    var _t1_is_superset = perf_counter_ns()
    var _ns_is_superset = Float64(_t1_is_superset - _t0_is_superset) / Float64(N)
    print("MOJO_TIMING set_ops::is_superset", _ns_is_superset, _acc_is_superset)
    var _result_is_superset = is_superset(_li5, _li5)
    var _summary_is_superset = _summary_bool(_result_is_superset)
    print("MOJO_RESULT set_ops::is_superset", _summary_is_superset)
    var _acc_set_equals: Float64 = 0.0
    var _t0_set_equals = perf_counter_ns()
    for _ in range(N):
        _acc_set_equals += Float64(set_equals(_li5, _li5))
    var _t1_set_equals = perf_counter_ns()
    var _ns_set_equals = Float64(_t1_set_equals - _t0_set_equals) / Float64(N)
    print("MOJO_TIMING set_ops::set_equals", _ns_set_equals, _acc_set_equals)
    var _result_set_equals = set_equals(_li5, _li5)
    var _summary_set_equals = _summary_bool(_result_set_equals)
    print("MOJO_RESULT set_ops::set_equals", _summary_set_equals)
    var _acc_power_set_size: Float64 = 0.0
    var _t0_power_set_size = perf_counter_ns()
    for _ in range(N):
        _acc_power_set_size += Float64(power_set_size(5))
    var _t1_power_set_size = perf_counter_ns()
    var _ns_power_set_size = Float64(_t1_power_set_size - _t0_power_set_size) / Float64(N)
    print("MOJO_TIMING set_ops::power_set_size", _ns_power_set_size, _acc_power_set_size)
    var _result_power_set_size = power_set_size(5)
    var _summary_power_set_size = _summary_int(_result_power_set_size)
    print("MOJO_RESULT set_ops::power_set_size", _summary_power_set_size)
    var _acc_jaccard_index: Float64 = 0.0
    var _t0_jaccard_index = perf_counter_ns()
    for _ in range(N):
        _acc_jaccard_index += jaccard_index(_li5, _li5)
    var _t1_jaccard_index = perf_counter_ns()
    var _ns_jaccard_index = Float64(_t1_jaccard_index - _t0_jaccard_index) / Float64(N)
    print("MOJO_TIMING set_ops::jaccard_index", _ns_jaccard_index, _acc_jaccard_index)
    var _result_jaccard_index = jaccard_index(_li5, _li5)
    var _summary_jaccard_index = _summary_float64(_result_jaccard_index)
    print("MOJO_RESULT set_ops::jaccard_index", _summary_jaccard_index)
    var _acc_to_set: Float64 = 0.0
    var _t0_to_set = perf_counter_ns()
    for _ in range(N):
        var _r_to_set = to_set(_li5)
        _acc_to_set += Float64(len(_r_to_set))
    var _t1_to_set = perf_counter_ns()
    var _ns_to_set = Float64(_t1_to_set - _t0_to_set) / Float64(N)
    print("MOJO_TIMING set_ops::to_set", _ns_to_set, _acc_to_set)
    var _result_to_set = to_set(_li5)
    var _summary_to_set = _summary_list_int(_result_to_set)
    print("MOJO_RESULT set_ops::to_set", _summary_to_set)
    var _acc_set_contains: Float64 = 0.0
    var _t0_set_contains = perf_counter_ns()
    for _ in range(N):
        _acc_set_contains += Float64(set_contains(_li5, 5))
    var _t1_set_contains = perf_counter_ns()
    var _ns_set_contains = Float64(_t1_set_contains - _t0_set_contains) / Float64(N)
    print("MOJO_TIMING set_ops::set_contains", _ns_set_contains, _acc_set_contains)
    var _result_set_contains = set_contains(_li5, 5)
    var _summary_set_contains = _summary_bool(_result_set_contains)
    print("MOJO_RESULT set_ops::set_contains", _summary_set_contains)
    var _acc_set_cardinality: Float64 = 0.0
    var _t0_set_cardinality = perf_counter_ns()
    for _ in range(N):
        _acc_set_cardinality += Float64(set_cardinality(_li5))
    var _t1_set_cardinality = perf_counter_ns()
    var _ns_set_cardinality = Float64(_t1_set_cardinality - _t0_set_cardinality) / Float64(N)
    print("MOJO_TIMING set_ops::set_cardinality", _ns_set_cardinality, _acc_set_cardinality)
    var _result_set_cardinality = set_cardinality(_li5)
    var _summary_set_cardinality = _summary_int(_result_set_cardinality)
    print("MOJO_RESULT set_ops::set_cardinality", _summary_set_cardinality)
