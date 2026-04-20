"""bench_compression_rle.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compression.rle import rle_encode, rle_decode, rle_encode_string, rle_decode_string, compression_ratio
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

    var _acc_rle_encode: Float64 = 0.0
    var _t0_rle_encode = perf_counter_ns()
    for _ in range(N):
        var _r_rle_encode = rle_encode(_lub5)
        _acc_rle_encode += Float64(len(_r_rle_encode))
    var _t1_rle_encode = perf_counter_ns()
    var _ns_rle_encode = Float64(_t1_rle_encode - _t0_rle_encode) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_encode", _ns_rle_encode, _acc_rle_encode)
    var _acc_rle_decode: Float64 = 0.0
    var _t0_rle_decode = perf_counter_ns()
    for _ in range(N):
        var _r_rle_decode = rle_decode(_lub5)
        _acc_rle_decode += Float64(len(_r_rle_decode))
    var _t1_rle_decode = perf_counter_ns()
    var _ns_rle_decode = Float64(_t1_rle_decode - _t0_rle_decode) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_decode", _ns_rle_decode, _acc_rle_decode)
    var _acc_rle_encode_string: Float64 = 0.0
    var _t0_rle_encode_string = perf_counter_ns()
    for _ in range(N):
        _ = rle_encode_string("test")
    var _t1_rle_encode_string = perf_counter_ns()
    var _ns_rle_encode_string = Float64(_t1_rle_encode_string - _t0_rle_encode_string) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_encode_string", _ns_rle_encode_string, _acc_rle_encode_string)
    var _acc_rle_decode_string: Float64 = 0.0
    var _t0_rle_decode_string = perf_counter_ns()
    for _ in range(N):
        _ = rle_decode_string("test")
    var _t1_rle_decode_string = perf_counter_ns()
    var _ns_rle_decode_string = Float64(_t1_rle_decode_string - _t0_rle_decode_string) / Float64(N)
    print("MOJO_TIMING compression_rle::rle_decode_string", _ns_rle_decode_string, _acc_rle_decode_string)
    var _acc_compression_ratio: Float64 = 0.0
    var _t0_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_compression_ratio += compression_ratio(5, 5)
    var _t1_compression_ratio = perf_counter_ns()
    var _ns_compression_ratio = Float64(_t1_compression_ratio - _t0_compression_ratio) / Float64(N)
    print("MOJO_TIMING compression_rle::compression_ratio", _ns_compression_ratio, _acc_compression_ratio)
