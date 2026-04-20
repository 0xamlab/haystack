"""bench_crypto_crc32.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from crypto.crc32 import crc32, crc32_hex, crc32_combine
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

    var _acc_crc32: Float64 = 0.0
    var _t0_crc32 = perf_counter_ns()
    for _ in range(N):
        _acc_crc32 += Float64(crc32("test"))
    var _t1_crc32 = perf_counter_ns()
    var _ns_crc32 = Float64(_t1_crc32 - _t0_crc32) / Float64(N)
    print("MOJO_TIMING crypto_crc32::crc32", _ns_crc32, _acc_crc32)
    var _acc_crc32_hex: Float64 = 0.0
    var _t0_crc32_hex = perf_counter_ns()
    for _ in range(N):
        _ = crc32_hex("test")
    var _t1_crc32_hex = perf_counter_ns()
    var _ns_crc32_hex = Float64(_t1_crc32_hex - _t0_crc32_hex) / Float64(N)
    print("MOJO_TIMING crypto_crc32::crc32_hex", _ns_crc32_hex, _acc_crc32_hex)
    var _acc_crc32_combine: Float64 = 0.0
    var _t0_crc32_combine = perf_counter_ns()
    for _ in range(N):
        _acc_crc32_combine += Float64(crc32_combine(1, 1, 5))
    var _t1_crc32_combine = perf_counter_ns()
    var _ns_crc32_combine = Float64(_t1_crc32_combine - _t0_crc32_combine) / Float64(N)
    print("MOJO_TIMING crypto_crc32::crc32_combine", _ns_crc32_combine, _acc_crc32_combine)
