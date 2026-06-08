"""bench_sketch.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sketch import create_cms, cms_hash, create_hll, hll_hash, leading_zeros, CountMinSketch, HyperLogLog
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

    var _keeper_create_cms = List[CountMinSketch]()
    _keeper_create_cms.append(create_cms(5, 5))
    var _acc_create_cms: Float64 = 0.0
    var _t0_create_cms = perf_counter_ns()
    for _ in range(N):
        _keeper_create_cms[0] = create_cms(5, 5)
        _acc_create_cms += Float64(len(_keeper_create_cms))
    var _t1_create_cms = perf_counter_ns()
    var _ns_create_cms = Float64(_t1_create_cms - _t0_create_cms) / Float64(N)
    print("MOJO_TIMING sketch::create_cms", _ns_create_cms, _acc_create_cms)
    var _acc_cms_hash: Float64 = 0.0
    var _t0_cms_hash = perf_counter_ns()
    for _ in range(N):
        _acc_cms_hash += Float64(cms_hash(5, 5, 5))
    var _t1_cms_hash = perf_counter_ns()
    var _ns_cms_hash = Float64(_t1_cms_hash - _t0_cms_hash) / Float64(N)
    print("MOJO_TIMING sketch::cms_hash", _ns_cms_hash, _acc_cms_hash)
    var _result_cms_hash = cms_hash(5, 5, 5)
    var _summary_cms_hash = _summary_int(_result_cms_hash)
    print("MOJO_RESULT sketch::cms_hash", _summary_cms_hash)
    var _keeper_create_hll = List[HyperLogLog]()
    _keeper_create_hll.append(create_hll(5))
    var _acc_create_hll: Float64 = 0.0
    var _t0_create_hll = perf_counter_ns()
    for _ in range(N):
        _keeper_create_hll[0] = create_hll(5)
        _acc_create_hll += Float64(len(_keeper_create_hll))
    var _t1_create_hll = perf_counter_ns()
    var _ns_create_hll = Float64(_t1_create_hll - _t0_create_hll) / Float64(N)
    print("MOJO_TIMING sketch::create_hll", _ns_create_hll, _acc_create_hll)
    var _acc_hll_hash: Float64 = 0.0
    var _t0_hll_hash = perf_counter_ns()
    for _ in range(N):
        _acc_hll_hash += Float64(hll_hash(5))
    var _t1_hll_hash = perf_counter_ns()
    var _ns_hll_hash = Float64(_t1_hll_hash - _t0_hll_hash) / Float64(N)
    print("MOJO_TIMING sketch::hll_hash", _ns_hll_hash, _acc_hll_hash)
    var _result_hll_hash = hll_hash(5)
    var _summary_hll_hash = _summary_int(_result_hll_hash)
    print("MOJO_RESULT sketch::hll_hash", _summary_hll_hash)
    var _acc_leading_zeros: Float64 = 0.0
    var _t0_leading_zeros = perf_counter_ns()
    for _ in range(N):
        _acc_leading_zeros += Float64(leading_zeros(5, 5))
    var _t1_leading_zeros = perf_counter_ns()
    var _ns_leading_zeros = Float64(_t1_leading_zeros - _t0_leading_zeros) / Float64(N)
    print("MOJO_TIMING sketch::leading_zeros", _ns_leading_zeros, _acc_leading_zeros)
    var _result_leading_zeros = leading_zeros(5, 5)
    var _summary_leading_zeros = _summary_int(_result_leading_zeros)
    print("MOJO_RESULT sketch::leading_zeros", _summary_leading_zeros)
