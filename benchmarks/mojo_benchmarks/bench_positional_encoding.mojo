"""bench_positional_encoding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from positional_encoding import sinusoidal_pe, rope_cos_component, rope_sin_component, rope_apply_cos, rope_apply_sin, alibi_slope, alibi_bias, learned_pe_init, relative_pe_bucket, xpos_scale
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

    var _acc_sinusoidal_pe: Float64 = 0.0
    var _t0_sinusoidal_pe = perf_counter_ns()
    for _ in range(N):
        _acc_sinusoidal_pe += sinusoidal_pe(0.5, 0.5, 0.5)
    var _t1_sinusoidal_pe = perf_counter_ns()
    var _ns_sinusoidal_pe = Float64(_t1_sinusoidal_pe - _t0_sinusoidal_pe) / Float64(N)
    print("MOJO_TIMING positional_encoding::sinusoidal_pe", _ns_sinusoidal_pe, _acc_sinusoidal_pe)
    var _result_sinusoidal_pe = sinusoidal_pe(0.5, 0.5, 0.5)
    var _summary_sinusoidal_pe = _summary_float64(_result_sinusoidal_pe)
    print("MOJO_RESULT positional_encoding::sinusoidal_pe", _summary_sinusoidal_pe)
    var _acc_rope_cos_component: Float64 = 0.0
    var _t0_rope_cos_component = perf_counter_ns()
    for _ in range(N):
        _acc_rope_cos_component += rope_cos_component(0.5, 0.5, 0.5)
    var _t1_rope_cos_component = perf_counter_ns()
    var _ns_rope_cos_component = Float64(_t1_rope_cos_component - _t0_rope_cos_component) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_cos_component", _ns_rope_cos_component, _acc_rope_cos_component)
    var _result_rope_cos_component = rope_cos_component(0.5, 0.5, 0.5)
    var _summary_rope_cos_component = _summary_float64(_result_rope_cos_component)
    print("MOJO_RESULT positional_encoding::rope_cos_component", _summary_rope_cos_component)
    var _acc_rope_sin_component: Float64 = 0.0
    var _t0_rope_sin_component = perf_counter_ns()
    for _ in range(N):
        _acc_rope_sin_component += rope_sin_component(0.5, 0.5, 0.5)
    var _t1_rope_sin_component = perf_counter_ns()
    var _ns_rope_sin_component = Float64(_t1_rope_sin_component - _t0_rope_sin_component) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_sin_component", _ns_rope_sin_component, _acc_rope_sin_component)
    var _result_rope_sin_component = rope_sin_component(0.5, 0.5, 0.5)
    var _summary_rope_sin_component = _summary_float64(_result_rope_sin_component)
    print("MOJO_RESULT positional_encoding::rope_sin_component", _summary_rope_sin_component)
    var _acc_rope_apply_cos: Float64 = 0.0
    var _t0_rope_apply_cos = perf_counter_ns()
    for _ in range(N):
        _acc_rope_apply_cos += rope_apply_cos(0.5, 0.5)
    var _t1_rope_apply_cos = perf_counter_ns()
    var _ns_rope_apply_cos = Float64(_t1_rope_apply_cos - _t0_rope_apply_cos) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_apply_cos", _ns_rope_apply_cos, _acc_rope_apply_cos)
    var _result_rope_apply_cos = rope_apply_cos(0.5, 0.5)
    var _summary_rope_apply_cos = _summary_float64(_result_rope_apply_cos)
    print("MOJO_RESULT positional_encoding::rope_apply_cos", _summary_rope_apply_cos)
    var _acc_rope_apply_sin: Float64 = 0.0
    var _t0_rope_apply_sin = perf_counter_ns()
    for _ in range(N):
        _acc_rope_apply_sin += rope_apply_sin(0.5, 0.5, 0.5, 0.5)
    var _t1_rope_apply_sin = perf_counter_ns()
    var _ns_rope_apply_sin = Float64(_t1_rope_apply_sin - _t0_rope_apply_sin) / Float64(N)
    print("MOJO_TIMING positional_encoding::rope_apply_sin", _ns_rope_apply_sin, _acc_rope_apply_sin)
    var _result_rope_apply_sin = rope_apply_sin(0.5, 0.5, 0.5, 0.5)
    var _summary_rope_apply_sin = _summary_float64(_result_rope_apply_sin)
    print("MOJO_RESULT positional_encoding::rope_apply_sin", _summary_rope_apply_sin)
    var _acc_alibi_slope: Float64 = 0.0
    var _t0_alibi_slope = perf_counter_ns()
    for _ in range(N):
        _acc_alibi_slope += alibi_slope(0.5, 0.5)
    var _t1_alibi_slope = perf_counter_ns()
    var _ns_alibi_slope = Float64(_t1_alibi_slope - _t0_alibi_slope) / Float64(N)
    print("MOJO_TIMING positional_encoding::alibi_slope", _ns_alibi_slope, _acc_alibi_slope)
    var _result_alibi_slope = alibi_slope(0.5, 0.5)
    var _summary_alibi_slope = _summary_float64(_result_alibi_slope)
    print("MOJO_RESULT positional_encoding::alibi_slope", _summary_alibi_slope)
    var _acc_alibi_bias: Float64 = 0.0
    var _t0_alibi_bias = perf_counter_ns()
    for _ in range(N):
        _acc_alibi_bias += alibi_bias(0.5, 0.5, 0.5)
    var _t1_alibi_bias = perf_counter_ns()
    var _ns_alibi_bias = Float64(_t1_alibi_bias - _t0_alibi_bias) / Float64(N)
    print("MOJO_TIMING positional_encoding::alibi_bias", _ns_alibi_bias, _acc_alibi_bias)
    var _result_alibi_bias = alibi_bias(0.5, 0.5, 0.5)
    var _summary_alibi_bias = _summary_float64(_result_alibi_bias)
    print("MOJO_RESULT positional_encoding::alibi_bias", _summary_alibi_bias)
    var _acc_learned_pe_init: Float64 = 0.0
    var _t0_learned_pe_init = perf_counter_ns()
    for _ in range(N):
        _acc_learned_pe_init += learned_pe_init(0.5)
    var _t1_learned_pe_init = perf_counter_ns()
    var _ns_learned_pe_init = Float64(_t1_learned_pe_init - _t0_learned_pe_init) / Float64(N)
    print("MOJO_TIMING positional_encoding::learned_pe_init", _ns_learned_pe_init, _acc_learned_pe_init)
    var _result_learned_pe_init = learned_pe_init(0.5)
    var _summary_learned_pe_init = _summary_float64(_result_learned_pe_init)
    print("MOJO_RESULT positional_encoding::learned_pe_init", _summary_learned_pe_init)
    var _acc_relative_pe_bucket: Float64 = 0.0
    var _t0_relative_pe_bucket = perf_counter_ns()
    for _ in range(N):
        _acc_relative_pe_bucket += relative_pe_bucket(0.5, 0.5, 0.5)
    var _t1_relative_pe_bucket = perf_counter_ns()
    var _ns_relative_pe_bucket = Float64(_t1_relative_pe_bucket - _t0_relative_pe_bucket) / Float64(N)
    print("MOJO_TIMING positional_encoding::relative_pe_bucket", _ns_relative_pe_bucket, _acc_relative_pe_bucket)
    var _result_relative_pe_bucket = relative_pe_bucket(0.5, 0.5, 0.5)
    var _summary_relative_pe_bucket = _summary_float64(_result_relative_pe_bucket)
    print("MOJO_RESULT positional_encoding::relative_pe_bucket", _summary_relative_pe_bucket)
    var _acc_xpos_scale: Float64 = 0.0
    var _t0_xpos_scale = perf_counter_ns()
    for _ in range(N):
        _acc_xpos_scale += xpos_scale(0.5, 0.5, 0.5, 0.5)
    var _t1_xpos_scale = perf_counter_ns()
    var _ns_xpos_scale = Float64(_t1_xpos_scale - _t0_xpos_scale) / Float64(N)
    print("MOJO_TIMING positional_encoding::xpos_scale", _ns_xpos_scale, _acc_xpos_scale)
    var _result_xpos_scale = xpos_scale(0.5, 0.5, 0.5, 0.5)
    var _summary_xpos_scale = _summary_float64(_result_xpos_scale)
    print("MOJO_RESULT positional_encoding::xpos_scale", _summary_xpos_scale)
