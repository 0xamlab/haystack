"""bench_category_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from category_theory import map_list_fn, filter_fn, fold_left, fold_right, compose, zip_with, scan_left, take_while, drop_while, flat_map
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

    var _acc_map_list_fn: Float64 = 0.0
    var _t0_map_list_fn = perf_counter_ns()
    for _ in range(N):
        var _r_map_list_fn = map_list_fn(_lf5, 5)
        _acc_map_list_fn += Float64(len(_r_map_list_fn))
    var _t1_map_list_fn = perf_counter_ns()
    var _ns_map_list_fn = Float64(_t1_map_list_fn - _t0_map_list_fn) / Float64(N)
    print("MOJO_TIMING category_theory::map_list_fn", _ns_map_list_fn, _acc_map_list_fn)
    var _result_map_list_fn = map_list_fn(_lf5, 5)
    var _summary_map_list_fn = _summary_list_float64(_result_map_list_fn)
    print("MOJO_RESULT category_theory::map_list_fn", _summary_map_list_fn)
    var _acc_filter_fn: Float64 = 0.0
    var _t0_filter_fn = perf_counter_ns()
    for _ in range(N):
        var _r_filter_fn = filter_fn(_lf5, 5, 0.5)
        _acc_filter_fn += Float64(len(_r_filter_fn))
    var _t1_filter_fn = perf_counter_ns()
    var _ns_filter_fn = Float64(_t1_filter_fn - _t0_filter_fn) / Float64(N)
    print("MOJO_TIMING category_theory::filter_fn", _ns_filter_fn, _acc_filter_fn)
    var _result_filter_fn = filter_fn(_lf5, 5, 0.5)
    var _summary_filter_fn = _summary_list_float64(_result_filter_fn)
    print("MOJO_RESULT category_theory::filter_fn", _summary_filter_fn)
    var _acc_fold_left: Float64 = 0.0
    var _t0_fold_left = perf_counter_ns()
    for _ in range(N):
        _acc_fold_left += fold_left(_lf5, 0.5, 5)
    var _t1_fold_left = perf_counter_ns()
    var _ns_fold_left = Float64(_t1_fold_left - _t0_fold_left) / Float64(N)
    print("MOJO_TIMING category_theory::fold_left", _ns_fold_left, _acc_fold_left)
    var _result_fold_left = fold_left(_lf5, 0.5, 5)
    var _summary_fold_left = _summary_float64(_result_fold_left)
    print("MOJO_RESULT category_theory::fold_left", _summary_fold_left)
    var _acc_fold_right: Float64 = 0.0
    var _t0_fold_right = perf_counter_ns()
    for _ in range(N):
        _acc_fold_right += fold_right(_lf5, 0.5, 5)
    var _t1_fold_right = perf_counter_ns()
    var _ns_fold_right = Float64(_t1_fold_right - _t0_fold_right) / Float64(N)
    print("MOJO_TIMING category_theory::fold_right", _ns_fold_right, _acc_fold_right)
    var _result_fold_right = fold_right(_lf5, 0.5, 5)
    var _summary_fold_right = _summary_float64(_result_fold_right)
    print("MOJO_RESULT category_theory::fold_right", _summary_fold_right)
    var _acc_compose: Float64 = 0.0
    var _t0_compose = perf_counter_ns()
    for _ in range(N):
        var _r_compose = compose(_lf5, 5, 5)
        _acc_compose += Float64(len(_r_compose))
    var _t1_compose = perf_counter_ns()
    var _ns_compose = Float64(_t1_compose - _t0_compose) / Float64(N)
    print("MOJO_TIMING category_theory::compose", _ns_compose, _acc_compose)
    var _result_compose = compose(_lf5, 5, 5)
    var _summary_compose = _summary_list_float64(_result_compose)
    print("MOJO_RESULT category_theory::compose", _summary_compose)
    var _acc_zip_with: Float64 = 0.0
    var _t0_zip_with = perf_counter_ns()
    for _ in range(N):
        var _r_zip_with = zip_with(_lf5, _lf5, 5)
        _acc_zip_with += Float64(len(_r_zip_with))
    var _t1_zip_with = perf_counter_ns()
    var _ns_zip_with = Float64(_t1_zip_with - _t0_zip_with) / Float64(N)
    print("MOJO_TIMING category_theory::zip_with", _ns_zip_with, _acc_zip_with)
    var _result_zip_with = zip_with(_lf5, _lf5, 5)
    var _summary_zip_with = _summary_list_float64(_result_zip_with)
    print("MOJO_RESULT category_theory::zip_with", _summary_zip_with)
    var _acc_scan_left: Float64 = 0.0
    var _t0_scan_left = perf_counter_ns()
    for _ in range(N):
        var _r_scan_left = scan_left(_lf5, 0.5, 5)
        _acc_scan_left += Float64(len(_r_scan_left))
    var _t1_scan_left = perf_counter_ns()
    var _ns_scan_left = Float64(_t1_scan_left - _t0_scan_left) / Float64(N)
    print("MOJO_TIMING category_theory::scan_left", _ns_scan_left, _acc_scan_left)
    var _result_scan_left = scan_left(_lf5, 0.5, 5)
    var _summary_scan_left = _summary_list_float64(_result_scan_left)
    print("MOJO_RESULT category_theory::scan_left", _summary_scan_left)
    var _acc_take_while: Float64 = 0.0
    var _t0_take_while = perf_counter_ns()
    for _ in range(N):
        var _r_take_while = take_while(_lf5, 5, 0.5)
        _acc_take_while += Float64(len(_r_take_while))
    var _t1_take_while = perf_counter_ns()
    var _ns_take_while = Float64(_t1_take_while - _t0_take_while) / Float64(N)
    print("MOJO_TIMING category_theory::take_while", _ns_take_while, _acc_take_while)
    var _result_take_while = take_while(_lf5, 5, 0.5)
    var _summary_take_while = _summary_list_float64(_result_take_while)
    print("MOJO_RESULT category_theory::take_while", _summary_take_while)
    var _acc_drop_while: Float64 = 0.0
    var _t0_drop_while = perf_counter_ns()
    for _ in range(N):
        var _r_drop_while = drop_while(_lf5, 5, 0.5)
        _acc_drop_while += Float64(len(_r_drop_while))
    var _t1_drop_while = perf_counter_ns()
    var _ns_drop_while = Float64(_t1_drop_while - _t0_drop_while) / Float64(N)
    print("MOJO_TIMING category_theory::drop_while", _ns_drop_while, _acc_drop_while)
    var _result_drop_while = drop_while(_lf5, 5, 0.5)
    var _summary_drop_while = _summary_list_float64(_result_drop_while)
    print("MOJO_RESULT category_theory::drop_while", _summary_drop_while)
    var _acc_flat_map: Float64 = 0.0
    var _t0_flat_map = perf_counter_ns()
    for _ in range(N):
        var _r_flat_map = flat_map(_lf5, 5)
        _acc_flat_map += Float64(len(_r_flat_map))
    var _t1_flat_map = perf_counter_ns()
    var _ns_flat_map = Float64(_t1_flat_map - _t0_flat_map) / Float64(N)
    print("MOJO_TIMING category_theory::flat_map", _ns_flat_map, _acc_flat_map)
    var _result_flat_map = flat_map(_lf5, 5)
    var _summary_flat_map = _summary_list_float64(_result_flat_map)
    print("MOJO_RESULT category_theory::flat_map", _summary_flat_map)
