"""bench_bloom_counting.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bloom_counting import cb_create, cb_hash, cb_false_positive_rate, cb_optimal_hashes, CountingBloom
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

    var _keeper_cb_create = List[CountingBloom]()
    _keeper_cb_create.append(cb_create(5, 5))
    var _acc_cb_create: Float64 = 0.0
    var _t0_cb_create = perf_counter_ns()
    for _ in range(N):
        _keeper_cb_create[0] = cb_create(5, 5)
        _acc_cb_create += Float64(len(_keeper_cb_create))
    var _t1_cb_create = perf_counter_ns()
    var _ns_cb_create = Float64(_t1_cb_create - _t0_cb_create) / Float64(N)
    print("MOJO_TIMING bloom_counting::cb_create", _ns_cb_create, _acc_cb_create)
    var _acc_cb_hash: Float64 = 0.0
    var _t0_cb_hash = perf_counter_ns()
    for _ in range(N):
        _acc_cb_hash += Float64(cb_hash(5, 5, 5))
    var _t1_cb_hash = perf_counter_ns()
    var _ns_cb_hash = Float64(_t1_cb_hash - _t0_cb_hash) / Float64(N)
    print("MOJO_TIMING bloom_counting::cb_hash", _ns_cb_hash, _acc_cb_hash)
    var _result_cb_hash = cb_hash(5, 5, 5)
    var _summary_cb_hash = _summary_int(_result_cb_hash)
    print("MOJO_RESULT bloom_counting::cb_hash", _summary_cb_hash)
    var _acc_cb_false_positive_rate: Float64 = 0.0
    var _t0_cb_false_positive_rate = perf_counter_ns()
    for _ in range(N):
        _acc_cb_false_positive_rate += cb_false_positive_rate(5, 5, 5)
    var _t1_cb_false_positive_rate = perf_counter_ns()
    var _ns_cb_false_positive_rate = Float64(_t1_cb_false_positive_rate - _t0_cb_false_positive_rate) / Float64(N)
    print("MOJO_TIMING bloom_counting::cb_false_positive_rate", _ns_cb_false_positive_rate, _acc_cb_false_positive_rate)
    var _result_cb_false_positive_rate = cb_false_positive_rate(5, 5, 5)
    var _summary_cb_false_positive_rate = _summary_float64(_result_cb_false_positive_rate)
    print("MOJO_RESULT bloom_counting::cb_false_positive_rate", _summary_cb_false_positive_rate)
    var _acc_cb_optimal_hashes: Float64 = 0.0
    var _t0_cb_optimal_hashes = perf_counter_ns()
    for _ in range(N):
        _acc_cb_optimal_hashes += Float64(cb_optimal_hashes(5, 5))
    var _t1_cb_optimal_hashes = perf_counter_ns()
    var _ns_cb_optimal_hashes = Float64(_t1_cb_optimal_hashes - _t0_cb_optimal_hashes) / Float64(N)
    print("MOJO_TIMING bloom_counting::cb_optimal_hashes", _ns_cb_optimal_hashes, _acc_cb_optimal_hashes)
    var _result_cb_optimal_hashes = cb_optimal_hashes(5, 5)
    var _summary_cb_optimal_hashes = _summary_int(_result_cb_optimal_hashes)
    print("MOJO_RESULT bloom_counting::cb_optimal_hashes", _summary_cb_optimal_hashes)
