"""bench_positional_encoding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from positional_encoding import sinusoidal_pe, rope_cos_component, rope_sin_component, rope_apply_cos, rope_apply_sin, alibi_slope, alibi_bias, learned_pe_init, relative_pe_bucket, xpos_scale
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

    var _acc_sinusoidal_pe: Float64 = 0.0
    var _t0_sinusoidal_pe = perf_counter_ns()
    for _ in range(N):
        _acc_sinusoidal_pe += sinusoidal_pe(0.5, 0.5, 0.5)
    var _t1_sinusoidal_pe = perf_counter_ns()
    var _ns_sinusoidal_pe = Float64(_t1_sinusoidal_pe - _t0_sinusoidal_pe) / Float64(N)
    print("MOJO_TIMING positional_encoding::sinusoidal_pe", _ns_sinusoidal_pe, _acc_sinusoidal_pe)
    var _acc_rope_cos_component: Float64 = 0.0
    var _t0_rope_cos_component = perf_counter_ns()
    for _ in range(N):
        _acc_rope_cos_component += rope_cos_component(0.5, 0.5, 0.5)
    var _t1_rope_cos_component = perf_counter_ns()
    var _ns_rope_cos_component = Float64(_t1_rope_cos_component - _t0_rope_cos_component) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_cos_component", _ns_rope_cos_component, _acc_rope_cos_component)
    var _acc_rope_sin_component: Float64 = 0.0
    var _t0_rope_sin_component = perf_counter_ns()
    for _ in range(N):
        _acc_rope_sin_component += rope_sin_component(0.5, 0.5, 0.5)
    var _t1_rope_sin_component = perf_counter_ns()
    var _ns_rope_sin_component = Float64(_t1_rope_sin_component - _t0_rope_sin_component) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_sin_component", _ns_rope_sin_component, _acc_rope_sin_component)
    var _acc_rope_apply_cos: Float64 = 0.0
    var _t0_rope_apply_cos = perf_counter_ns()
    for _ in range(N):
        _acc_rope_apply_cos += rope_apply_cos(0.5, 0.5)
    var _t1_rope_apply_cos = perf_counter_ns()
    var _ns_rope_apply_cos = Float64(_t1_rope_apply_cos - _t0_rope_apply_cos) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_apply_cos", _ns_rope_apply_cos, _acc_rope_apply_cos)
    var _acc_rope_apply_sin: Float64 = 0.0
    var _t0_rope_apply_sin = perf_counter_ns()
    for _ in range(N):
        _acc_rope_apply_sin += rope_apply_sin(0.5, 0.5, 0.5, 0.5)
    var _t1_rope_apply_sin = perf_counter_ns()
    var _ns_rope_apply_sin = Float64(_t1_rope_apply_sin - _t0_rope_apply_sin) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_apply_sin", _ns_rope_apply_sin, _acc_rope_apply_sin)
    var _acc_alibi_slope: Float64 = 0.0
    var _t0_alibi_slope = perf_counter_ns()
    for _ in range(N):
        _acc_alibi_slope += alibi_slope(0.5, 0.5)
    var _t1_alibi_slope = perf_counter_ns()
    var _ns_alibi_slope = Float64(_t1_alibi_slope - _t0_alibi_slope) / Float64(N)
    print("MOJO_TIMING positional_encoding::alibi_slope", _ns_alibi_slope, _acc_alibi_slope)
    var _acc_alibi_bias: Float64 = 0.0
    var _t0_alibi_bias = perf_counter_ns()
    for _ in range(N):
        _acc_alibi_bias += alibi_bias(0.5, 0.5, 0.5)
    var _t1_alibi_bias = perf_counter_ns()
    var _ns_alibi_bias = Float64(_t1_alibi_bias - _t0_alibi_bias) / Float64(N)
    print("MOJO_TIMING positional_encoding::alibi_bias", _ns_alibi_bias, _acc_alibi_bias)
    var _acc_learned_pe_init: Float64 = 0.0
    var _t0_learned_pe_init = perf_counter_ns()
    for _ in range(N):
        _acc_learned_pe_init += learned_pe_init(0.5)
    var _t1_learned_pe_init = perf_counter_ns()
    var _ns_learned_pe_init = Float64(_t1_learned_pe_init - _t0_learned_pe_init) / Float64(N)
    print("MOJO_TIMING positional_encoding::learned_pe_init", _ns_learned_pe_init, _acc_learned_pe_init)
    var _acc_relative_pe_bucket: Float64 = 0.0
    var _t0_relative_pe_bucket = perf_counter_ns()
    for _ in range(N):
        _acc_relative_pe_bucket += relative_pe_bucket(0.5, 0.5, 0.5)
    var _t1_relative_pe_bucket = perf_counter_ns()
    var _ns_relative_pe_bucket = Float64(_t1_relative_pe_bucket - _t0_relative_pe_bucket) / Float64(N)
    print("MOJO_TIMING positional_encoding::relative_pe_bucket", _ns_relative_pe_bucket, _acc_relative_pe_bucket)
    var _acc_xpos_scale: Float64 = 0.0
    var _t0_xpos_scale = perf_counter_ns()
    for _ in range(N):
        _acc_xpos_scale += xpos_scale(0.5, 0.5, 0.5, 0.5)
    var _t1_xpos_scale = perf_counter_ns()
    var _ns_xpos_scale = Float64(_t1_xpos_scale - _t0_xpos_scale) / Float64(N)
    print("MOJO_TIMING positional_encoding::xpos_scale", _ns_xpos_scale, _acc_xpos_scale)
