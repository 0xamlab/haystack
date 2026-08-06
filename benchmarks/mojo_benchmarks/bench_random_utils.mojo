"""bench_random_utils.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from random_utils import random_choice, random_shuffle, random_sample, random_bootstrap, random_uniform_int, random_permutation, stratified_sample
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

    var _acc_random_choice: Float64 = 0.0
    var _t0_random_choice = perf_counter_ns()
    for _ in range(N):
        _acc_random_choice += Float64(random_choice(_lf5))
    var _t1_random_choice = perf_counter_ns()
    var _ns_random_choice = Float64(_t1_random_choice - _t0_random_choice) / Float64(N)
    print("MOJO_TIMING random_utils::random_choice", _ns_random_choice, _acc_random_choice)
    var _result_random_choice = random_choice(_lf5)
    var _summary_random_choice = _summary_int(_result_random_choice)
    print("MOJO_RESULT random_utils::random_choice", _summary_random_choice)
    var _acc_random_shuffle: Float64 = 0.0
    var _t0_random_shuffle = perf_counter_ns()
    for _ in range(N):
        _ = random_shuffle(_lf5)
    var _t1_random_shuffle = perf_counter_ns()
    var _ns_random_shuffle = Float64(_t1_random_shuffle - _t0_random_shuffle) / Float64(N)
    print("MOJO_TIMING random_utils::random_shuffle", _ns_random_shuffle, _acc_random_shuffle)
    var _result_random_shuffle = random_shuffle(_lf5)
    var _summary_random_shuffle = "none"
    print("MOJO_RESULT random_utils::random_shuffle", _summary_random_shuffle)
    var _acc_random_sample: Float64 = 0.0
    var _t0_random_sample = perf_counter_ns()
    for _ in range(N):
        var _r_random_sample = random_sample(_lf5, 5)
        _acc_random_sample += Float64(len(_r_random_sample))
    var _t1_random_sample = perf_counter_ns()
    var _ns_random_sample = Float64(_t1_random_sample - _t0_random_sample) / Float64(N)
    print("MOJO_TIMING random_utils::random_sample", _ns_random_sample, _acc_random_sample)
    var _result_random_sample = random_sample(_lf5, 5)
    var _summary_random_sample = _summary_list_float64(_result_random_sample)
    print("MOJO_RESULT random_utils::random_sample", _summary_random_sample)
    var _acc_random_bootstrap: Float64 = 0.0
    var _t0_random_bootstrap = perf_counter_ns()
    for _ in range(N):
        var _r_random_bootstrap = random_bootstrap(_lf5, 5)
        _acc_random_bootstrap += Float64(len(_r_random_bootstrap))
    var _t1_random_bootstrap = perf_counter_ns()
    var _ns_random_bootstrap = Float64(_t1_random_bootstrap - _t0_random_bootstrap) / Float64(N)
    print("MOJO_TIMING random_utils::random_bootstrap", _ns_random_bootstrap, _acc_random_bootstrap)
    var _result_random_bootstrap = random_bootstrap(_lf5, 5)
    var _summary_random_bootstrap = _summary_list_float64(_result_random_bootstrap)
    print("MOJO_RESULT random_utils::random_bootstrap", _summary_random_bootstrap)
    var _acc_random_uniform_int: Float64 = 0.0
    var _t0_random_uniform_int = perf_counter_ns()
    for _ in range(N):
        _acc_random_uniform_int += Float64(random_uniform_int(5, 5))
    var _t1_random_uniform_int = perf_counter_ns()
    var _ns_random_uniform_int = Float64(_t1_random_uniform_int - _t0_random_uniform_int) / Float64(N)
    print("MOJO_TIMING random_utils::random_uniform_int", _ns_random_uniform_int, _acc_random_uniform_int)
    var _result_random_uniform_int = random_uniform_int(5, 5)
    var _summary_random_uniform_int = _summary_int(_result_random_uniform_int)
    print("MOJO_RESULT random_utils::random_uniform_int", _summary_random_uniform_int)
    var _acc_random_permutation: Float64 = 0.0
    var _t0_random_permutation = perf_counter_ns()
    for _ in range(N):
        var _r_random_permutation = random_permutation(5)
        _acc_random_permutation += Float64(len(_r_random_permutation))
    var _t1_random_permutation = perf_counter_ns()
    var _ns_random_permutation = Float64(_t1_random_permutation - _t0_random_permutation) / Float64(N)
    print("MOJO_TIMING random_utils::random_permutation", _ns_random_permutation, _acc_random_permutation)
    var _result_random_permutation = random_permutation(5)
    var _summary_random_permutation = _summary_list_int(_result_random_permutation)
    print("MOJO_RESULT random_utils::random_permutation", _summary_random_permutation)
    var _acc_stratified_sample: Float64 = 0.0
    var _t0_stratified_sample = perf_counter_ns()
    for _ in range(N):
        var _r_stratified_sample = stratified_sample(_lf5, 5)
        _acc_stratified_sample += Float64(len(_r_stratified_sample))
    var _t1_stratified_sample = perf_counter_ns()
    var _ns_stratified_sample = Float64(_t1_stratified_sample - _t0_stratified_sample) / Float64(N)
    print("MOJO_TIMING random_utils::stratified_sample", _ns_stratified_sample, _acc_stratified_sample)
    var _result_stratified_sample = stratified_sample(_lf5, 5)
    var _summary_stratified_sample = _summary_list_float64(_result_stratified_sample)
    print("MOJO_RESULT random_utils::stratified_sample", _summary_stratified_sample)
