"""bench_pipeline.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pipeline import map_list, filter_list, reduce_sum, reduce_product, reduce_min, reduce_max, chain_map_filter, batch, flatten, zip_lists, window, unique_values
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

    var _acc_map_list: Float64 = 0.0
    var _t0_map_list = perf_counter_ns()
    for _ in range(N):
        var _r_map_list = map_list(_lf5, 5)
        _acc_map_list += Float64(len(_r_map_list))
    var _t1_map_list = perf_counter_ns()
    var _ns_map_list = Float64(_t1_map_list - _t0_map_list) / Float64(N)
    print("MOJO_TIMING pipeline::map_list", _ns_map_list, _acc_map_list)
    var _result_map_list = map_list(_lf5, 5)
    var _summary_map_list = _summary_list_float64(_result_map_list)
    print("MOJO_RESULT pipeline::map_list", _summary_map_list)
    var _acc_filter_list: Float64 = 0.0
    var _t0_filter_list = perf_counter_ns()
    for _ in range(N):
        var _r_filter_list = filter_list(_lf5, 5, 0.5)
        _acc_filter_list += Float64(len(_r_filter_list))
    var _t1_filter_list = perf_counter_ns()
    var _ns_filter_list = Float64(_t1_filter_list - _t0_filter_list) / Float64(N)
    print("MOJO_TIMING pipeline::filter_list", _ns_filter_list, _acc_filter_list)
    var _result_filter_list = filter_list(_lf5, 5, 0.5)
    var _summary_filter_list = _summary_list_float64(_result_filter_list)
    print("MOJO_RESULT pipeline::filter_list", _summary_filter_list)
    var _acc_reduce_sum: Float64 = 0.0
    var _t0_reduce_sum = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_sum += reduce_sum(_lf5)
    var _t1_reduce_sum = perf_counter_ns()
    var _ns_reduce_sum = Float64(_t1_reduce_sum - _t0_reduce_sum) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_sum", _ns_reduce_sum, _acc_reduce_sum)
    var _result_reduce_sum = reduce_sum(_lf5)
    var _summary_reduce_sum = _summary_float64(_result_reduce_sum)
    print("MOJO_RESULT pipeline::reduce_sum", _summary_reduce_sum)
    var _acc_reduce_product: Float64 = 0.0
    var _t0_reduce_product = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_product += reduce_product(_lf5)
    var _t1_reduce_product = perf_counter_ns()
    var _ns_reduce_product = Float64(_t1_reduce_product - _t0_reduce_product) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_product", _ns_reduce_product, _acc_reduce_product)
    var _result_reduce_product = reduce_product(_lf5)
    var _summary_reduce_product = _summary_float64(_result_reduce_product)
    print("MOJO_RESULT pipeline::reduce_product", _summary_reduce_product)
    var _acc_reduce_min: Float64 = 0.0
    var _t0_reduce_min = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_min += reduce_min(_lf5)
    var _t1_reduce_min = perf_counter_ns()
    var _ns_reduce_min = Float64(_t1_reduce_min - _t0_reduce_min) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_min", _ns_reduce_min, _acc_reduce_min)
    var _result_reduce_min = reduce_min(_lf5)
    var _summary_reduce_min = _summary_float64(_result_reduce_min)
    print("MOJO_RESULT pipeline::reduce_min", _summary_reduce_min)
    var _acc_reduce_max: Float64 = 0.0
    var _t0_reduce_max = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_max += reduce_max(_lf5)
    var _t1_reduce_max = perf_counter_ns()
    var _ns_reduce_max = Float64(_t1_reduce_max - _t0_reduce_max) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_max", _ns_reduce_max, _acc_reduce_max)
    var _result_reduce_max = reduce_max(_lf5)
    var _summary_reduce_max = _summary_float64(_result_reduce_max)
    print("MOJO_RESULT pipeline::reduce_max", _summary_reduce_max)
    var _acc_chain_map_filter: Float64 = 0.0
    var _t0_chain_map_filter = perf_counter_ns()
    for _ in range(N):
        var _r_chain_map_filter = chain_map_filter(_lf5, 5, 5, 0.5)
        _acc_chain_map_filter += Float64(len(_r_chain_map_filter))
    var _t1_chain_map_filter = perf_counter_ns()
    var _ns_chain_map_filter = Float64(_t1_chain_map_filter - _t0_chain_map_filter) / Float64(N)
    print("MOJO_TIMING pipeline::chain_map_filter", _ns_chain_map_filter, _acc_chain_map_filter)
    var _result_chain_map_filter = chain_map_filter(_lf5, 5, 5, 0.5)
    var _summary_chain_map_filter = _summary_list_float64(_result_chain_map_filter)
    print("MOJO_RESULT pipeline::chain_map_filter", _summary_chain_map_filter)
    var _acc_batch: Float64 = 0.0
    var _t0_batch = perf_counter_ns()
    for _ in range(N):
        var _r_batch = batch(_lf5, 5)
        _acc_batch += Float64(len(_r_batch))
    var _t1_batch = perf_counter_ns()
    var _ns_batch = Float64(_t1_batch - _t0_batch) / Float64(N)
    print("MOJO_TIMING pipeline::batch", _ns_batch, _acc_batch)
    var _result_batch = batch(_lf5, 5)
    var _summary_batch = _summary_list_list_float64(_result_batch)
    print("MOJO_RESULT pipeline::batch", _summary_batch)
    var _acc_flatten: Float64 = 0.0
    var _t0_flatten = perf_counter_ns()
    for _ in range(N):
        var _r_flatten = flatten([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_flatten += Float64(len(_r_flatten))
    var _t1_flatten = perf_counter_ns()
    var _ns_flatten = Float64(_t1_flatten - _t0_flatten) / Float64(N)
    print("MOJO_TIMING pipeline::flatten", _ns_flatten, _acc_flatten)
    var _result_flatten = flatten([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_flatten = _summary_list_float64(_result_flatten)
    print("MOJO_RESULT pipeline::flatten", _summary_flatten)
    var _acc_zip_lists: Float64 = 0.0
    var _t0_zip_lists = perf_counter_ns()
    for _ in range(N):
        var _r_zip_lists = zip_lists(_lf5, _lf5)
        _acc_zip_lists += Float64(len(_r_zip_lists))
    var _t1_zip_lists = perf_counter_ns()
    var _ns_zip_lists = Float64(_t1_zip_lists - _t0_zip_lists) / Float64(N)
    print("MOJO_TIMING pipeline::zip_lists", _ns_zip_lists, _acc_zip_lists)
    var _result_zip_lists = zip_lists(_lf5, _lf5)
    var _summary_zip_lists = _summary_list_list_float64(_result_zip_lists)
    print("MOJO_RESULT pipeline::zip_lists", _summary_zip_lists)
    var _acc_window: Float64 = 0.0
    var _t0_window = perf_counter_ns()
    for _ in range(N):
        var _r_window = window(_lf5, 5)
        _acc_window += Float64(len(_r_window))
    var _t1_window = perf_counter_ns()
    var _ns_window = Float64(_t1_window - _t0_window) / Float64(N)
    print("MOJO_TIMING pipeline::window", _ns_window, _acc_window)
    var _result_window = window(_lf5, 5)
    var _summary_window = _summary_list_list_float64(_result_window)
    print("MOJO_RESULT pipeline::window", _summary_window)
    var _acc_unique_values: Float64 = 0.0
    var _t0_unique_values = perf_counter_ns()
    for _ in range(N):
        var _r_unique_values = unique_values(_lf5)
        _acc_unique_values += Float64(len(_r_unique_values))
    var _t1_unique_values = perf_counter_ns()
    var _ns_unique_values = Float64(_t1_unique_values - _t0_unique_values) / Float64(N)
    print("MOJO_TIMING pipeline::unique_values", _ns_unique_values, _acc_unique_values)
    var _result_unique_values = unique_values(_lf5)
    var _summary_unique_values = _summary_list_float64(_result_unique_values)
    print("MOJO_RESULT pipeline::unique_values", _summary_unique_values)
