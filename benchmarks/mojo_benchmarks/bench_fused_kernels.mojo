"""bench_fused_kernels.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fused_kernels import fused_attention_score, fused_softmax_mask, fused_layernorm_element, fused_matmul_bias_relu, fused_matmul_bias_gelu, fused_rope_attention, fused_add_norm, fused_scale_shift, fused_dropout_residual, kernel_fusion_savings
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_fused_attention_score: Float64 = 0.0
    var _t0_fused_attention_score = perf_counter_ns()
    for _ in range(N):
        _acc_fused_attention_score += fused_attention_score(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_attention_score = perf_counter_ns()
    var _ns_fused_attention_score = Float64(_t1_fused_attention_score - _t0_fused_attention_score) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_attention_score", _ns_fused_attention_score, _acc_fused_attention_score)
    var _result_fused_attention_score = fused_attention_score(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_fused_attention_score = _summary_float64(_result_fused_attention_score)
    print("MOJO_RESULT fused_kernels::fused_attention_score", _summary_fused_attention_score)
    var _acc_fused_softmax_mask: Float64 = 0.0
    var _t0_fused_softmax_mask = perf_counter_ns()
    for _ in range(N):
        _acc_fused_softmax_mask += fused_softmax_mask(0.5, 0.5, 0.5, 0.5)
    var _t1_fused_softmax_mask = perf_counter_ns()
    var _ns_fused_softmax_mask = Float64(_t1_fused_softmax_mask - _t0_fused_softmax_mask) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_softmax_mask", _ns_fused_softmax_mask, _acc_fused_softmax_mask)
    var _result_fused_softmax_mask = fused_softmax_mask(0.5, 0.5, 0.5, 0.5)
    var _summary_fused_softmax_mask = _summary_float64(_result_fused_softmax_mask)
    print("MOJO_RESULT fused_kernels::fused_softmax_mask", _summary_fused_softmax_mask)
    var _acc_fused_layernorm_element: Float64 = 0.0
    var _t0_fused_layernorm_element = perf_counter_ns()
    for _ in range(N):
        _acc_fused_layernorm_element += fused_layernorm_element(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_layernorm_element = perf_counter_ns()
    var _ns_fused_layernorm_element = Float64(_t1_fused_layernorm_element - _t0_fused_layernorm_element) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_layernorm_element", _ns_fused_layernorm_element, _acc_fused_layernorm_element)
    var _result_fused_layernorm_element = fused_layernorm_element(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_fused_layernorm_element = _summary_float64(_result_fused_layernorm_element)
    print("MOJO_RESULT fused_kernels::fused_layernorm_element", _summary_fused_layernorm_element)
    var _acc_fused_matmul_bias_relu: Float64 = 0.0
    var _t0_fused_matmul_bias_relu = perf_counter_ns()
    for _ in range(N):
        _acc_fused_matmul_bias_relu += fused_matmul_bias_relu(0.5, 0.5)
    var _t1_fused_matmul_bias_relu = perf_counter_ns()
    var _ns_fused_matmul_bias_relu = Float64(_t1_fused_matmul_bias_relu - _t0_fused_matmul_bias_relu) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_matmul_bias_relu", _ns_fused_matmul_bias_relu, _acc_fused_matmul_bias_relu)
    var _result_fused_matmul_bias_relu = fused_matmul_bias_relu(0.5, 0.5)
    var _summary_fused_matmul_bias_relu = _summary_float64(_result_fused_matmul_bias_relu)
    print("MOJO_RESULT fused_kernels::fused_matmul_bias_relu", _summary_fused_matmul_bias_relu)
    var _acc_fused_matmul_bias_gelu: Float64 = 0.0
    var _t0_fused_matmul_bias_gelu = perf_counter_ns()
    for _ in range(N):
        _acc_fused_matmul_bias_gelu += fused_matmul_bias_gelu(0.5, 0.5)
    var _t1_fused_matmul_bias_gelu = perf_counter_ns()
    var _ns_fused_matmul_bias_gelu = Float64(_t1_fused_matmul_bias_gelu - _t0_fused_matmul_bias_gelu) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_matmul_bias_gelu", _ns_fused_matmul_bias_gelu, _acc_fused_matmul_bias_gelu)
    var _result_fused_matmul_bias_gelu = fused_matmul_bias_gelu(0.5, 0.5)
    var _summary_fused_matmul_bias_gelu = _summary_float64(_result_fused_matmul_bias_gelu)
    print("MOJO_RESULT fused_kernels::fused_matmul_bias_gelu", _summary_fused_matmul_bias_gelu)
    var _acc_fused_rope_attention: Float64 = 0.0
    var _t0_fused_rope_attention = perf_counter_ns()
    for _ in range(N):
        _acc_fused_rope_attention += fused_rope_attention(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_rope_attention = perf_counter_ns()
    var _ns_fused_rope_attention = Float64(_t1_fused_rope_attention - _t0_fused_rope_attention) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_rope_attention", _ns_fused_rope_attention, _acc_fused_rope_attention)
    var _result_fused_rope_attention = fused_rope_attention(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_fused_rope_attention = _summary_float64(_result_fused_rope_attention)
    print("MOJO_RESULT fused_kernels::fused_rope_attention", _summary_fused_rope_attention)
    var _acc_fused_add_norm: Float64 = 0.0
    var _t0_fused_add_norm = perf_counter_ns()
    for _ in range(N):
        _acc_fused_add_norm += fused_add_norm(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_add_norm = perf_counter_ns()
    var _ns_fused_add_norm = Float64(_t1_fused_add_norm - _t0_fused_add_norm) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_add_norm", _ns_fused_add_norm, _acc_fused_add_norm)
    var _result_fused_add_norm = fused_add_norm(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_fused_add_norm = _summary_float64(_result_fused_add_norm)
    print("MOJO_RESULT fused_kernels::fused_add_norm", _summary_fused_add_norm)
    var _acc_fused_scale_shift: Float64 = 0.0
    var _t0_fused_scale_shift = perf_counter_ns()
    for _ in range(N):
        _acc_fused_scale_shift += fused_scale_shift(0.5, 0.5, 0.5)
    var _t1_fused_scale_shift = perf_counter_ns()
    var _ns_fused_scale_shift = Float64(_t1_fused_scale_shift - _t0_fused_scale_shift) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_scale_shift", _ns_fused_scale_shift, _acc_fused_scale_shift)
    var _result_fused_scale_shift = fused_scale_shift(0.5, 0.5, 0.5)
    var _summary_fused_scale_shift = _summary_float64(_result_fused_scale_shift)
    print("MOJO_RESULT fused_kernels::fused_scale_shift", _summary_fused_scale_shift)
    var _acc_fused_dropout_residual: Float64 = 0.0
    var _t0_fused_dropout_residual = perf_counter_ns()
    for _ in range(N):
        _acc_fused_dropout_residual += fused_dropout_residual(0.5, 0.5, 0.5, 0.5)
    var _t1_fused_dropout_residual = perf_counter_ns()
    var _ns_fused_dropout_residual = Float64(_t1_fused_dropout_residual - _t0_fused_dropout_residual) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_dropout_residual", _ns_fused_dropout_residual, _acc_fused_dropout_residual)
    var _result_fused_dropout_residual = fused_dropout_residual(0.5, 0.5, 0.5, 0.5)
    var _summary_fused_dropout_residual = _summary_float64(_result_fused_dropout_residual)
    print("MOJO_RESULT fused_kernels::fused_dropout_residual", _summary_fused_dropout_residual)
    var _acc_kernel_fusion_savings: Float64 = 0.0
    var _t0_kernel_fusion_savings = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_fusion_savings += kernel_fusion_savings(0.5, 0.5, 0.5)
    var _t1_kernel_fusion_savings = perf_counter_ns()
    var _ns_kernel_fusion_savings = Float64(_t1_kernel_fusion_savings - _t0_kernel_fusion_savings) / Float64(N)
    print("MOJO_TIMING fused_kernels::kernel_fusion_savings", _ns_kernel_fusion_savings, _acc_kernel_fusion_savings)
    var _result_kernel_fusion_savings = kernel_fusion_savings(0.5, 0.5, 0.5)
    var _summary_kernel_fusion_savings = _summary_float64(_result_kernel_fusion_savings)
    print("MOJO_RESULT fused_kernels::kernel_fusion_savings", _summary_kernel_fusion_savings)
