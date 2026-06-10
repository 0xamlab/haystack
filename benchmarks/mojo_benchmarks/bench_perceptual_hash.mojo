"""bench_perceptual_hash.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from perceptual_hash import ahash, dhash, phash, hamming_distance, is_duplicate, ahash_flat, dhash_flat, phash_flat
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

    var _acc_ahash: Float64 = 0.0
    var _t0_ahash = perf_counter_ns()
    for _ in range(N):
        _acc_ahash += Float64(ahash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_ahash = perf_counter_ns()
    var _ns_ahash = Float64(_t1_ahash - _t0_ahash) / Float64(N)
    print("MOJO_TIMING perceptual_hash::ahash", _ns_ahash, _acc_ahash)
    var _result_ahash = ahash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_ahash = _summary_uint64(_result_ahash)
    print("MOJO_RESULT perceptual_hash::ahash", _summary_ahash)
    var _acc_dhash: Float64 = 0.0
    var _t0_dhash = perf_counter_ns()
    for _ in range(N):
        _acc_dhash += Float64(dhash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_dhash = perf_counter_ns()
    var _ns_dhash = Float64(_t1_dhash - _t0_dhash) / Float64(N)
    print("MOJO_TIMING perceptual_hash::dhash", _ns_dhash, _acc_dhash)
    var _result_dhash = dhash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_dhash = _summary_uint64(_result_dhash)
    print("MOJO_RESULT perceptual_hash::dhash", _summary_dhash)
    var _acc_phash: Float64 = 0.0
    var _t0_phash = perf_counter_ns()
    for _ in range(N):
        _acc_phash += Float64(phash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_phash = perf_counter_ns()
    var _ns_phash = Float64(_t1_phash - _t0_phash) / Float64(N)
    print("MOJO_TIMING perceptual_hash::phash", _ns_phash, _acc_phash)
    var _result_phash = phash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_phash = _summary_uint64(_result_phash)
    print("MOJO_RESULT perceptual_hash::phash", _summary_phash)
    var _acc_hamming_distance: Float64 = 0.0
    var _t0_hamming_distance = perf_counter_ns()
    for _ in range(N):
        _acc_hamming_distance += Float64(hamming_distance(UInt64(1), UInt64(1)))
    var _t1_hamming_distance = perf_counter_ns()
    var _ns_hamming_distance = Float64(_t1_hamming_distance - _t0_hamming_distance) / Float64(N)
    print("MOJO_TIMING perceptual_hash::hamming_distance", _ns_hamming_distance, _acc_hamming_distance)
    var _result_hamming_distance = hamming_distance(UInt64(1), UInt64(1))
    var _summary_hamming_distance = _summary_int(_result_hamming_distance)
    print("MOJO_RESULT perceptual_hash::hamming_distance", _summary_hamming_distance)
    var _acc_is_duplicate: Float64 = 0.0
    var _t0_is_duplicate = perf_counter_ns()
    for _ in range(N):
        _acc_is_duplicate += Float64(is_duplicate(UInt64(1), UInt64(1), 5))
    var _t1_is_duplicate = perf_counter_ns()
    var _ns_is_duplicate = Float64(_t1_is_duplicate - _t0_is_duplicate) / Float64(N)
    print("MOJO_TIMING perceptual_hash::is_duplicate", _ns_is_duplicate, _acc_is_duplicate)
    var _result_is_duplicate = is_duplicate(UInt64(1), UInt64(1), 5)
    var _summary_is_duplicate = _summary_bool(_result_is_duplicate)
    print("MOJO_RESULT perceptual_hash::is_duplicate", _summary_is_duplicate)
    var _acc_ahash_flat: Float64 = 0.0
    var _t0_ahash_flat = perf_counter_ns()
    for _ in range(N):
        _acc_ahash_flat += Float64(ahash_flat(_lf5, 5, 5))
    var _t1_ahash_flat = perf_counter_ns()
    var _ns_ahash_flat = Float64(_t1_ahash_flat - _t0_ahash_flat) / Float64(N)
    print("MOJO_TIMING perceptual_hash::ahash_flat", _ns_ahash_flat, _acc_ahash_flat)
    var _result_ahash_flat = ahash_flat(_lf5, 5, 5)
    var _summary_ahash_flat = _summary_uint64(_result_ahash_flat)
    print("MOJO_RESULT perceptual_hash::ahash_flat", _summary_ahash_flat)
    var _acc_dhash_flat: Float64 = 0.0
    var _t0_dhash_flat = perf_counter_ns()
    for _ in range(N):
        _acc_dhash_flat += Float64(dhash_flat(_lf5, 5, 5))
    var _t1_dhash_flat = perf_counter_ns()
    var _ns_dhash_flat = Float64(_t1_dhash_flat - _t0_dhash_flat) / Float64(N)
    print("MOJO_TIMING perceptual_hash::dhash_flat", _ns_dhash_flat, _acc_dhash_flat)
    var _result_dhash_flat = dhash_flat(_lf5, 5, 5)
    var _summary_dhash_flat = _summary_uint64(_result_dhash_flat)
    print("MOJO_RESULT perceptual_hash::dhash_flat", _summary_dhash_flat)
    var _acc_phash_flat: Float64 = 0.0
    var _t0_phash_flat = perf_counter_ns()
    for _ in range(N):
        _acc_phash_flat += Float64(phash_flat(_lf5, 5, 5))
    var _t1_phash_flat = perf_counter_ns()
    var _ns_phash_flat = Float64(_t1_phash_flat - _t0_phash_flat) / Float64(N)
    print("MOJO_TIMING perceptual_hash::phash_flat", _ns_phash_flat, _acc_phash_flat)
    var _result_phash_flat = phash_flat(_lf5, 5, 5)
    var _summary_phash_flat = _summary_uint64(_result_phash_flat)
    print("MOJO_RESULT perceptual_hash::phash_flat", _summary_phash_flat)
