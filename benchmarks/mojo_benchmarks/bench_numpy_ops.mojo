"""bench_numpy_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from numpy_ops import np_clip, np_log1p, np_expm1, np_sign, np_heaviside, np_sinc, np_logaddexp, np_hypot, np_lerp, np_digitize_bin
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

    var _acc_np_clip: Float64 = 0.0
    var _t0_np_clip = perf_counter_ns()
    for _ in range(N):
        _acc_np_clip += np_clip(0.5, 0.5, 0.5)
    var _t1_np_clip = perf_counter_ns()
    var _ns_np_clip = Float64(_t1_np_clip - _t0_np_clip) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_clip", _ns_np_clip, _acc_np_clip)
    var _acc_np_log1p: Float64 = 0.0
    var _t0_np_log1p = perf_counter_ns()
    for _ in range(N):
        _acc_np_log1p += np_log1p(0.5)
    var _t1_np_log1p = perf_counter_ns()
    var _ns_np_log1p = Float64(_t1_np_log1p - _t0_np_log1p) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_log1p", _ns_np_log1p, _acc_np_log1p)
    var _acc_np_expm1: Float64 = 0.0
    var _t0_np_expm1 = perf_counter_ns()
    for _ in range(N):
        _acc_np_expm1 += np_expm1(0.5)
    var _t1_np_expm1 = perf_counter_ns()
    var _ns_np_expm1 = Float64(_t1_np_expm1 - _t0_np_expm1) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_expm1", _ns_np_expm1, _acc_np_expm1)
    var _acc_np_sign: Float64 = 0.0
    var _t0_np_sign = perf_counter_ns()
    for _ in range(N):
        _acc_np_sign += np_sign(0.5)
    var _t1_np_sign = perf_counter_ns()
    var _ns_np_sign = Float64(_t1_np_sign - _t0_np_sign) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_sign", _ns_np_sign, _acc_np_sign)
    var _acc_np_heaviside: Float64 = 0.0
    var _t0_np_heaviside = perf_counter_ns()
    for _ in range(N):
        _acc_np_heaviside += np_heaviside(0.5, 0.5)
    var _t1_np_heaviside = perf_counter_ns()
    var _ns_np_heaviside = Float64(_t1_np_heaviside - _t0_np_heaviside) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_heaviside", _ns_np_heaviside, _acc_np_heaviside)
    var _acc_np_sinc: Float64 = 0.0
    var _t0_np_sinc = perf_counter_ns()
    for _ in range(N):
        _acc_np_sinc += np_sinc(0.5)
    var _t1_np_sinc = perf_counter_ns()
    var _ns_np_sinc = Float64(_t1_np_sinc - _t0_np_sinc) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_sinc", _ns_np_sinc, _acc_np_sinc)
    var _acc_np_logaddexp: Float64 = 0.0
    var _t0_np_logaddexp = perf_counter_ns()
    for _ in range(N):
        _acc_np_logaddexp += np_logaddexp(0.5, 0.5)
    var _t1_np_logaddexp = perf_counter_ns()
    var _ns_np_logaddexp = Float64(_t1_np_logaddexp - _t0_np_logaddexp) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_logaddexp", _ns_np_logaddexp, _acc_np_logaddexp)
    var _acc_np_hypot: Float64 = 0.0
    var _t0_np_hypot = perf_counter_ns()
    for _ in range(N):
        _acc_np_hypot += np_hypot(0.5, 0.5)
    var _t1_np_hypot = perf_counter_ns()
    var _ns_np_hypot = Float64(_t1_np_hypot - _t0_np_hypot) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_hypot", _ns_np_hypot, _acc_np_hypot)
    var _acc_np_lerp: Float64 = 0.0
    var _t0_np_lerp = perf_counter_ns()
    for _ in range(N):
        _acc_np_lerp += np_lerp(0.5, 0.5, 0.5)
    var _t1_np_lerp = perf_counter_ns()
    var _ns_np_lerp = Float64(_t1_np_lerp - _t0_np_lerp) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_lerp", _ns_np_lerp, _acc_np_lerp)
    var _acc_np_digitize_bin: Float64 = 0.0
    var _t0_np_digitize_bin = perf_counter_ns()
    for _ in range(N):
        _acc_np_digitize_bin += np_digitize_bin(0.5, 0.5, 0.5)
    var _t1_np_digitize_bin = perf_counter_ns()
    var _ns_np_digitize_bin = Float64(_t1_np_digitize_bin - _t0_np_digitize_bin) / Float64(N)
    print("MOJO_TIMING numpy_ops::np_digitize_bin", _ns_np_digitize_bin, _acc_np_digitize_bin)
