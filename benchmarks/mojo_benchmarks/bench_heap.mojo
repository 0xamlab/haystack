"""bench_heap.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from heap import heapify_min, heapify_max, heap_push_min, heap_pop_min, heap_push_max, heap_pop_max, heap_peek_min, heap_peek_max, k_smallest, k_largest, merge_sorted_lists, running_median, is_min_heap
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

    var _acc_heapify_min: Float64 = 0.0
    var _t0_heapify_min = perf_counter_ns()
    for _ in range(N):
        _ = heapify_min(_lf5)
    var _t1_heapify_min = perf_counter_ns()
    var _ns_heapify_min = Float64(_t1_heapify_min - _t0_heapify_min) / Float64(N)
    print("MOJO_TIMING heap::heapify_min", _ns_heapify_min, _acc_heapify_min)
    var _result_heapify_min = heapify_min(_lf5)
    var _summary_heapify_min = "none"
    print("MOJO_RESULT heap::heapify_min", _summary_heapify_min)
    var _acc_heapify_max: Float64 = 0.0
    var _t0_heapify_max = perf_counter_ns()
    for _ in range(N):
        _ = heapify_max(_lf5)
    var _t1_heapify_max = perf_counter_ns()
    var _ns_heapify_max = Float64(_t1_heapify_max - _t0_heapify_max) / Float64(N)
    print("MOJO_TIMING heap::heapify_max", _ns_heapify_max, _acc_heapify_max)
    var _result_heapify_max = heapify_max(_lf5)
    var _summary_heapify_max = "none"
    print("MOJO_RESULT heap::heapify_max", _summary_heapify_max)
    var _acc_heap_push_min: Float64 = 0.0
    var _t0_heap_push_min = perf_counter_ns()
    for _ in range(N):
        _ = heap_push_min(_lf5, 0.5)
    var _t1_heap_push_min = perf_counter_ns()
    var _ns_heap_push_min = Float64(_t1_heap_push_min - _t0_heap_push_min) / Float64(N)
    print("MOJO_TIMING heap::heap_push_min", _ns_heap_push_min, _acc_heap_push_min)
    var _result_heap_push_min = heap_push_min(_lf5, 0.5)
    var _summary_heap_push_min = "none"
    print("MOJO_RESULT heap::heap_push_min", _summary_heap_push_min)
    var _acc_heap_pop_min: Float64 = 0.0
    var _t0_heap_pop_min = perf_counter_ns()
    for _ in range(N):
        _acc_heap_pop_min += heap_pop_min(_lf5)
    var _t1_heap_pop_min = perf_counter_ns()
    var _ns_heap_pop_min = Float64(_t1_heap_pop_min - _t0_heap_pop_min) / Float64(N)
    print("MOJO_TIMING heap::heap_pop_min", _ns_heap_pop_min, _acc_heap_pop_min)
    var _result_heap_pop_min = heap_pop_min(_lf5)
    var _summary_heap_pop_min = _summary_float64(_result_heap_pop_min)
    print("MOJO_RESULT heap::heap_pop_min", _summary_heap_pop_min)
    var _acc_heap_push_max: Float64 = 0.0
    var _t0_heap_push_max = perf_counter_ns()
    for _ in range(N):
        _ = heap_push_max(_lf5, 0.5)
    var _t1_heap_push_max = perf_counter_ns()
    var _ns_heap_push_max = Float64(_t1_heap_push_max - _t0_heap_push_max) / Float64(N)
    print("MOJO_TIMING heap::heap_push_max", _ns_heap_push_max, _acc_heap_push_max)
    var _result_heap_push_max = heap_push_max(_lf5, 0.5)
    var _summary_heap_push_max = "none"
    print("MOJO_RESULT heap::heap_push_max", _summary_heap_push_max)
    var _acc_heap_pop_max: Float64 = 0.0
    var _t0_heap_pop_max = perf_counter_ns()
    for _ in range(N):
        _acc_heap_pop_max += heap_pop_max(_lf5)
    var _t1_heap_pop_max = perf_counter_ns()
    var _ns_heap_pop_max = Float64(_t1_heap_pop_max - _t0_heap_pop_max) / Float64(N)
    print("MOJO_TIMING heap::heap_pop_max", _ns_heap_pop_max, _acc_heap_pop_max)
    var _result_heap_pop_max = heap_pop_max(_lf5)
    var _summary_heap_pop_max = _summary_float64(_result_heap_pop_max)
    print("MOJO_RESULT heap::heap_pop_max", _summary_heap_pop_max)
    var _acc_heap_peek_min: Float64 = 0.0
    var _t0_heap_peek_min = perf_counter_ns()
    for _ in range(N):
        _acc_heap_peek_min += heap_peek_min(_lf5)
    var _t1_heap_peek_min = perf_counter_ns()
    var _ns_heap_peek_min = Float64(_t1_heap_peek_min - _t0_heap_peek_min) / Float64(N)
    print("MOJO_TIMING heap::heap_peek_min", _ns_heap_peek_min, _acc_heap_peek_min)
    var _result_heap_peek_min = heap_peek_min(_lf5)
    var _summary_heap_peek_min = _summary_float64(_result_heap_peek_min)
    print("MOJO_RESULT heap::heap_peek_min", _summary_heap_peek_min)
    var _acc_heap_peek_max: Float64 = 0.0
    var _t0_heap_peek_max = perf_counter_ns()
    for _ in range(N):
        _acc_heap_peek_max += heap_peek_max(_lf5)
    var _t1_heap_peek_max = perf_counter_ns()
    var _ns_heap_peek_max = Float64(_t1_heap_peek_max - _t0_heap_peek_max) / Float64(N)
    print("MOJO_TIMING heap::heap_peek_max", _ns_heap_peek_max, _acc_heap_peek_max)
    var _result_heap_peek_max = heap_peek_max(_lf5)
    var _summary_heap_peek_max = _summary_float64(_result_heap_peek_max)
    print("MOJO_RESULT heap::heap_peek_max", _summary_heap_peek_max)
    var _acc_k_smallest: Float64 = 0.0
    var _t0_k_smallest = perf_counter_ns()
    for _ in range(N):
        var _r_k_smallest = k_smallest(_lf5, 5)
        _acc_k_smallest += Float64(len(_r_k_smallest))
    var _t1_k_smallest = perf_counter_ns()
    var _ns_k_smallest = Float64(_t1_k_smallest - _t0_k_smallest) / Float64(N)
    print("MOJO_TIMING heap::k_smallest", _ns_k_smallest, _acc_k_smallest)
    var _result_k_smallest = k_smallest(_lf5, 5)
    var _summary_k_smallest = _summary_list_float64(_result_k_smallest)
    print("MOJO_RESULT heap::k_smallest", _summary_k_smallest)
    var _acc_k_largest: Float64 = 0.0
    var _t0_k_largest = perf_counter_ns()
    for _ in range(N):
        var _r_k_largest = k_largest(_lf5, 5)
        _acc_k_largest += Float64(len(_r_k_largest))
    var _t1_k_largest = perf_counter_ns()
    var _ns_k_largest = Float64(_t1_k_largest - _t0_k_largest) / Float64(N)
    print("MOJO_TIMING heap::k_largest", _ns_k_largest, _acc_k_largest)
    var _result_k_largest = k_largest(_lf5, 5)
    var _summary_k_largest = _summary_list_float64(_result_k_largest)
    print("MOJO_RESULT heap::k_largest", _summary_k_largest)
    var _acc_merge_sorted_lists: Float64 = 0.0
    var _t0_merge_sorted_lists = perf_counter_ns()
    for _ in range(N):
        var _r_merge_sorted_lists = merge_sorted_lists([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_merge_sorted_lists += Float64(len(_r_merge_sorted_lists))
    var _t1_merge_sorted_lists = perf_counter_ns()
    var _ns_merge_sorted_lists = Float64(_t1_merge_sorted_lists - _t0_merge_sorted_lists) / Float64(N)
    print("MOJO_TIMING heap::merge_sorted_lists", _ns_merge_sorted_lists, _acc_merge_sorted_lists)
    var _result_merge_sorted_lists = merge_sorted_lists([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_merge_sorted_lists = _summary_list_float64(_result_merge_sorted_lists)
    print("MOJO_RESULT heap::merge_sorted_lists", _summary_merge_sorted_lists)
    var _acc_running_median: Float64 = 0.0
    var _t0_running_median = perf_counter_ns()
    for _ in range(N):
        var _r_running_median = running_median(_lf5)
        _acc_running_median += Float64(len(_r_running_median))
    var _t1_running_median = perf_counter_ns()
    var _ns_running_median = Float64(_t1_running_median - _t0_running_median) / Float64(N)
    print("MOJO_TIMING heap::running_median", _ns_running_median, _acc_running_median)
    var _result_running_median = running_median(_lf5)
    var _summary_running_median = _summary_list_float64(_result_running_median)
    print("MOJO_RESULT heap::running_median", _summary_running_median)
    var _acc_is_min_heap: Float64 = 0.0
    var _t0_is_min_heap = perf_counter_ns()
    for _ in range(N):
        _acc_is_min_heap += Float64(is_min_heap(_lf5))
    var _t1_is_min_heap = perf_counter_ns()
    var _ns_is_min_heap = Float64(_t1_is_min_heap - _t0_is_min_heap) / Float64(N)
    print("MOJO_TIMING heap::is_min_heap", _ns_is_min_heap, _acc_is_min_heap)
    var _result_is_min_heap = is_min_heap(_lf5)
    var _summary_is_min_heap = _summary_bool(_result_is_min_heap)
    print("MOJO_RESULT heap::is_min_heap", _summary_is_min_heap)
