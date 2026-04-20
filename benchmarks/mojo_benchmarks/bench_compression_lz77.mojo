"""bench_compression_lz77.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compression.lz77 import bytes_to_ints, ints_to_string, find_longest_match, lz77_encode, compression_ratio
from std.time import perf_counter_ns

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

    var _acc_bytes_to_ints: Float64 = 0.0
    var _t0_bytes_to_ints = perf_counter_ns()
    for _ in range(N):
        var _r_bytes_to_ints = bytes_to_ints("test")
        _acc_bytes_to_ints += Float64(len(_r_bytes_to_ints))
    var _t1_bytes_to_ints = perf_counter_ns()
    var _ns_bytes_to_ints = Float64(_t1_bytes_to_ints - _t0_bytes_to_ints) / Float64(N)
    print("MOJO_TIMING compression_lz77::bytes_to_ints", _ns_bytes_to_ints, _acc_bytes_to_ints)
    var _acc_ints_to_string: Float64 = 0.0
    var _t0_ints_to_string = perf_counter_ns()
    for _ in range(N):
        _ = ints_to_string(_li5)
    var _t1_ints_to_string = perf_counter_ns()
    var _ns_ints_to_string = Float64(_t1_ints_to_string - _t0_ints_to_string) / Float64(N)
    print("MOJO_TIMING compression_lz77::ints_to_string", _ns_ints_to_string, _acc_ints_to_string)
    var _acc_find_longest_match: Float64 = 0.0
    var _t0_find_longest_match = perf_counter_ns()
    for _ in range(N):
        var _r_find_longest_match = find_longest_match(_li5, 5, 5, 5)
        _acc_find_longest_match += Float64(len(_r_find_longest_match))
    var _t1_find_longest_match = perf_counter_ns()
    var _ns_find_longest_match = Float64(_t1_find_longest_match - _t0_find_longest_match) / Float64(N)
    print("MOJO_TIMING compression_lz77::find_longest_match", _ns_find_longest_match, _acc_find_longest_match)
    var _acc_lz77_encode: Float64 = 0.0
    var _t0_lz77_encode = perf_counter_ns()
    for _ in range(N):
        var _r_lz77_encode = lz77_encode(_li5, 5, 5)
        _acc_lz77_encode += Float64(len(_r_lz77_encode))
    var _t1_lz77_encode = perf_counter_ns()
    var _ns_lz77_encode = Float64(_t1_lz77_encode - _t0_lz77_encode) / Float64(N)
    print("MOJO_TIMING compression_lz77::lz77_encode", _ns_lz77_encode, _acc_lz77_encode)
    var _acc_compression_ratio: Float64 = 0.0
    var _t0_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_compression_ratio += compression_ratio(5, 5)
    var _t1_compression_ratio = perf_counter_ns()
    var _ns_compression_ratio = Float64(_t1_compression_ratio - _t0_compression_ratio) / Float64(N)
    print("MOJO_TIMING compression_lz77::compression_ratio", _ns_compression_ratio, _acc_compression_ratio)
