"""bench_compression_delta.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compression.delta import delta_encode, delta_decode, delta_encode_float, delta_decode_float, xor_delta_encode, xor_delta_decode, zigzag_delta_encode, zigzag_delta_decode, double_delta_encode, double_delta_decode, compression_savings
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

    var _acc_delta_encode: Float64 = 0.0
    var _t0_delta_encode = perf_counter_ns()
    for _ in range(N):
        var _r_delta_encode = delta_encode(_li5)
        _acc_delta_encode += Float64(len(_r_delta_encode))
    var _t1_delta_encode = perf_counter_ns()
    var _ns_delta_encode = Float64(_t1_delta_encode - _t0_delta_encode) / Float64(N)
    print("MOJO_TIMING compression_delta::delta_encode", _ns_delta_encode, _acc_delta_encode)
    var _acc_delta_decode: Float64 = 0.0
    var _t0_delta_decode = perf_counter_ns()
    for _ in range(N):
        var _r_delta_decode = delta_decode(_li5)
        _acc_delta_decode += Float64(len(_r_delta_decode))
    var _t1_delta_decode = perf_counter_ns()
    var _ns_delta_decode = Float64(_t1_delta_decode - _t0_delta_decode) / Float64(N)
    print("MOJO_TIMING compression_delta::delta_decode", _ns_delta_decode, _acc_delta_decode)
    var _acc_delta_encode_float: Float64 = 0.0
    var _t0_delta_encode_float = perf_counter_ns()
    for _ in range(N):
        var _r_delta_encode_float = delta_encode_float(_lf5, 5)
        _acc_delta_encode_float += Float64(len(_r_delta_encode_float))
    var _t1_delta_encode_float = perf_counter_ns()
    var _ns_delta_encode_float = Float64(_t1_delta_encode_float - _t0_delta_encode_float) / Float64(N)
    print("MOJO_TIMING compression_delta::delta_encode_float", _ns_delta_encode_float, _acc_delta_encode_float)
    var _acc_delta_decode_float: Float64 = 0.0
    var _t0_delta_decode_float = perf_counter_ns()
    for _ in range(N):
        var _r_delta_decode_float = delta_decode_float(_li5, 5)
        _acc_delta_decode_float += Float64(len(_r_delta_decode_float))
    var _t1_delta_decode_float = perf_counter_ns()
    var _ns_delta_decode_float = Float64(_t1_delta_decode_float - _t0_delta_decode_float) / Float64(N)
    print("MOJO_TIMING compression_delta::delta_decode_float", _ns_delta_decode_float, _acc_delta_decode_float)
    var _acc_xor_delta_encode: Float64 = 0.0
    var _t0_xor_delta_encode = perf_counter_ns()
    for _ in range(N):
        var _r_xor_delta_encode = xor_delta_encode(_li5)
        _acc_xor_delta_encode += Float64(len(_r_xor_delta_encode))
    var _t1_xor_delta_encode = perf_counter_ns()
    var _ns_xor_delta_encode = Float64(_t1_xor_delta_encode - _t0_xor_delta_encode) / Float64(N)
    print("MOJO_TIMING compression_delta::xor_delta_encode", _ns_xor_delta_encode, _acc_xor_delta_encode)
    var _acc_xor_delta_decode: Float64 = 0.0
    var _t0_xor_delta_decode = perf_counter_ns()
    for _ in range(N):
        var _r_xor_delta_decode = xor_delta_decode(_li5)
        _acc_xor_delta_decode += Float64(len(_r_xor_delta_decode))
    var _t1_xor_delta_decode = perf_counter_ns()
    var _ns_xor_delta_decode = Float64(_t1_xor_delta_decode - _t0_xor_delta_decode) / Float64(N)
    print("MOJO_TIMING compression_delta::xor_delta_decode", _ns_xor_delta_decode, _acc_xor_delta_decode)
    var _acc_zigzag_delta_encode: Float64 = 0.0
    var _t0_zigzag_delta_encode = perf_counter_ns()
    for _ in range(N):
        var _r_zigzag_delta_encode = zigzag_delta_encode(_li5)
        _acc_zigzag_delta_encode += Float64(len(_r_zigzag_delta_encode))
    var _t1_zigzag_delta_encode = perf_counter_ns()
    var _ns_zigzag_delta_encode = Float64(_t1_zigzag_delta_encode - _t0_zigzag_delta_encode) / Float64(N)
    print("MOJO_TIMING compression_delta::zigzag_delta_encode", _ns_zigzag_delta_encode, _acc_zigzag_delta_encode)
    var _acc_zigzag_delta_decode: Float64 = 0.0
    var _t0_zigzag_delta_decode = perf_counter_ns()
    for _ in range(N):
        var _r_zigzag_delta_decode = zigzag_delta_decode(_li5)
        _acc_zigzag_delta_decode += Float64(len(_r_zigzag_delta_decode))
    var _t1_zigzag_delta_decode = perf_counter_ns()
    var _ns_zigzag_delta_decode = Float64(_t1_zigzag_delta_decode - _t0_zigzag_delta_decode) / Float64(N)
    print("MOJO_TIMING compression_delta::zigzag_delta_decode", _ns_zigzag_delta_decode, _acc_zigzag_delta_decode)
    var _acc_double_delta_encode: Float64 = 0.0
    var _t0_double_delta_encode = perf_counter_ns()
    for _ in range(N):
        var _r_double_delta_encode = double_delta_encode(_li5)
        _acc_double_delta_encode += Float64(len(_r_double_delta_encode))
    var _t1_double_delta_encode = perf_counter_ns()
    var _ns_double_delta_encode = Float64(_t1_double_delta_encode - _t0_double_delta_encode) / Float64(N)
    print("MOJO_TIMING compression_delta::double_delta_encode", _ns_double_delta_encode, _acc_double_delta_encode)
    var _acc_double_delta_decode: Float64 = 0.0
    var _t0_double_delta_decode = perf_counter_ns()
    for _ in range(N):
        var _r_double_delta_decode = double_delta_decode(_li5)
        _acc_double_delta_decode += Float64(len(_r_double_delta_decode))
    var _t1_double_delta_decode = perf_counter_ns()
    var _ns_double_delta_decode = Float64(_t1_double_delta_decode - _t0_double_delta_decode) / Float64(N)
    print("MOJO_TIMING compression_delta::double_delta_decode", _ns_double_delta_decode, _acc_double_delta_decode)
    var _acc_compression_savings: Float64 = 0.0
    var _t0_compression_savings = perf_counter_ns()
    for _ in range(N):
        _acc_compression_savings += compression_savings(5, 5)
    var _t1_compression_savings = perf_counter_ns()
    var _ns_compression_savings = Float64(_t1_compression_savings - _t0_compression_savings) / Float64(N)
    print("MOJO_TIMING compression_delta::compression_savings", _ns_compression_savings, _acc_compression_savings)
