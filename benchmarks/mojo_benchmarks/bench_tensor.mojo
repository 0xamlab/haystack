"""bench_tensor.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from tensor import zeros, ones, full, arange, linspace, Tensor1D
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

    var _keeper_zeros = List[Tensor1D]()
    _keeper_zeros.append(zeros(5))
    var _acc_zeros: Float64 = 0.0
    var _t0_zeros = perf_counter_ns()
    for _ in range(N):
        _keeper_zeros[0] = zeros(5)
        _acc_zeros += Float64(len(_keeper_zeros))
    var _t1_zeros = perf_counter_ns()
    var _ns_zeros = Float64(_t1_zeros - _t0_zeros) / Float64(N)
    print("MOJO_TIMING tensor::zeros", _ns_zeros, _acc_zeros)
    var _keeper_ones = List[Tensor1D]()
    _keeper_ones.append(ones(5))
    var _acc_ones: Float64 = 0.0
    var _t0_ones = perf_counter_ns()
    for _ in range(N):
        _keeper_ones[0] = ones(5)
        _acc_ones += Float64(len(_keeper_ones))
    var _t1_ones = perf_counter_ns()
    var _ns_ones = Float64(_t1_ones - _t0_ones) / Float64(N)
    print("MOJO_TIMING tensor::ones", _ns_ones, _acc_ones)
    var _keeper_full = List[Tensor1D]()
    _keeper_full.append(full(5, 0.5))
    var _acc_full: Float64 = 0.0
    var _t0_full = perf_counter_ns()
    for _ in range(N):
        _keeper_full[0] = full(5, 0.5)
        _acc_full += Float64(len(_keeper_full))
    var _t1_full = perf_counter_ns()
    var _ns_full = Float64(_t1_full - _t0_full) / Float64(N)
    print("MOJO_TIMING tensor::full", _ns_full, _acc_full)
    var _keeper_arange = List[Tensor1D]()
    _keeper_arange.append(arange(0.5, 0.5, 0.5))
    var _acc_arange: Float64 = 0.0
    var _t0_arange = perf_counter_ns()
    for _ in range(N):
        _keeper_arange[0] = arange(0.5, 0.5, 0.5)
        _acc_arange += Float64(len(_keeper_arange))
    var _t1_arange = perf_counter_ns()
    var _ns_arange = Float64(_t1_arange - _t0_arange) / Float64(N)
    print("MOJO_TIMING tensor::arange", _ns_arange, _acc_arange)
    var _keeper_linspace = List[Tensor1D]()
    _keeper_linspace.append(linspace(0.5, 0.5, 5))
    var _acc_linspace: Float64 = 0.0
    var _t0_linspace = perf_counter_ns()
    for _ in range(N):
        _keeper_linspace[0] = linspace(0.5, 0.5, 5)
        _acc_linspace += Float64(len(_keeper_linspace))
    var _t1_linspace = perf_counter_ns()
    var _ns_linspace = Float64(_t1_linspace - _t0_linspace) / Float64(N)
    print("MOJO_TIMING tensor::linspace", _ns_linspace, _acc_linspace)
