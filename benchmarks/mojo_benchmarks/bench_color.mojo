"""bench_color.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from color import clamp01, hex_to_rgb, RGB
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

    var _acc_clamp01: Float64 = 0.0
    var _t0_clamp01 = perf_counter_ns()
    for _ in range(N):
        _acc_clamp01 += clamp01(0.5)
    var _t1_clamp01 = perf_counter_ns()
    var _ns_clamp01 = Float64(_t1_clamp01 - _t0_clamp01) / Float64(N)
    print("MOJO_TIMING color::clamp01", _ns_clamp01, _acc_clamp01)
    var _keeper_hex_to_rgb = List[RGB]()
    _keeper_hex_to_rgb.append(hex_to_rgb("test"))
    var _acc_hex_to_rgb: Float64 = 0.0
    var _t0_hex_to_rgb = perf_counter_ns()
    for _ in range(N):
        _keeper_hex_to_rgb[0] = hex_to_rgb("test")
        _acc_hex_to_rgb += Float64(len(_keeper_hex_to_rgb))
    var _t1_hex_to_rgb = perf_counter_ns()
    var _ns_hex_to_rgb = Float64(_t1_hex_to_rgb - _t0_hex_to_rgb) / Float64(N)
    print("MOJO_TIMING color::hex_to_rgb", _ns_hex_to_rgb, _acc_hex_to_rgb)
