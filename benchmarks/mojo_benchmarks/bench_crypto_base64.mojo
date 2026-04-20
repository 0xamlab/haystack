"""bench_crypto_base64.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.base64 import b64_encode, b64_decode, b64_url_encode, b64_url_decode
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

    var _acc_b64_encode: Float64 = 0.0
    var _t0_b64_encode = perf_counter_ns()
    for _ in range(N):
        _ = b64_encode("test")
    var _t1_b64_encode = perf_counter_ns()
    var _ns_b64_encode = Float64(_t1_b64_encode - _t0_b64_encode) / Float64(N)
    print("MOJO_TIMING crypto_base64::b64_encode", _ns_b64_encode, _acc_b64_encode)
    var _acc_b64_decode: Float64 = 0.0
    var _t0_b64_decode = perf_counter_ns()
    for _ in range(N):
        _ = b64_decode("test")
    var _t1_b64_decode = perf_counter_ns()
    var _ns_b64_decode = Float64(_t1_b64_decode - _t0_b64_decode) / Float64(N)
    print("MOJO_TIMING crypto_base64::b64_decode", _ns_b64_decode, _acc_b64_decode)
    var _acc_b64_url_encode: Float64 = 0.0
    var _t0_b64_url_encode = perf_counter_ns()
    for _ in range(N):
        _ = b64_url_encode("test")
    var _t1_b64_url_encode = perf_counter_ns()
    var _ns_b64_url_encode = Float64(_t1_b64_url_encode - _t0_b64_url_encode) / Float64(N)
    print("MOJO_TIMING crypto_base64::b64_url_encode", _ns_b64_url_encode, _acc_b64_url_encode)
    var _acc_b64_url_decode: Float64 = 0.0
    var _t0_b64_url_decode = perf_counter_ns()
    for _ in range(N):
        _ = b64_url_decode("test")
    var _t1_b64_url_decode = perf_counter_ns()
    var _ns_b64_url_decode = Float64(_t1_b64_url_decode - _t0_b64_url_decode) / Float64(N)
    print("MOJO_TIMING crypto_base64::b64_url_decode", _ns_b64_url_decode, _acc_b64_url_decode)
