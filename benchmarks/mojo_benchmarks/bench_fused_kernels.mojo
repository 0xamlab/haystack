"""bench_fused_kernels.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fused_kernels import fused_attention_score, fused_softmax_mask, fused_layernorm_element, fused_matmul_bias_relu, fused_matmul_bias_gelu, fused_rope_attention, fused_add_norm, fused_scale_shift, fused_dropout_residual, kernel_fusion_savings
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

    var _acc_fused_attention_score: Float64 = 0.0
    var _t0_fused_attention_score = perf_counter_ns()
    for _ in range(N):
        _acc_fused_attention_score += fused_attention_score(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_attention_score = perf_counter_ns()
    var _ns_fused_attention_score = Float64(_t1_fused_attention_score - _t0_fused_attention_score) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_attention_score", _ns_fused_attention_score, _acc_fused_attention_score)
    var _acc_fused_softmax_mask: Float64 = 0.0
    var _t0_fused_softmax_mask = perf_counter_ns()
    for _ in range(N):
        _acc_fused_softmax_mask += fused_softmax_mask(0.5, 0.5, 0.5, 0.5)
    var _t1_fused_softmax_mask = perf_counter_ns()
    var _ns_fused_softmax_mask = Float64(_t1_fused_softmax_mask - _t0_fused_softmax_mask) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_softmax_mask", _ns_fused_softmax_mask, _acc_fused_softmax_mask)
    var _acc_fused_layernorm_element: Float64 = 0.0
    var _t0_fused_layernorm_element = perf_counter_ns()
    for _ in range(N):
        _acc_fused_layernorm_element += fused_layernorm_element(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_layernorm_element = perf_counter_ns()
    var _ns_fused_layernorm_element = Float64(_t1_fused_layernorm_element - _t0_fused_layernorm_element) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_layernorm_element", _ns_fused_layernorm_element, _acc_fused_layernorm_element)
    var _acc_fused_matmul_bias_relu: Float64 = 0.0
    var _t0_fused_matmul_bias_relu = perf_counter_ns()
    for _ in range(N):
        _acc_fused_matmul_bias_relu += fused_matmul_bias_relu(0.5, 0.5)
    var _t1_fused_matmul_bias_relu = perf_counter_ns()
    var _ns_fused_matmul_bias_relu = Float64(_t1_fused_matmul_bias_relu - _t0_fused_matmul_bias_relu) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_matmul_bias_relu", _ns_fused_matmul_bias_relu, _acc_fused_matmul_bias_relu)
    var _acc_fused_matmul_bias_gelu: Float64 = 0.0
    var _t0_fused_matmul_bias_gelu = perf_counter_ns()
    for _ in range(N):
        _acc_fused_matmul_bias_gelu += fused_matmul_bias_gelu(0.5, 0.5)
    var _t1_fused_matmul_bias_gelu = perf_counter_ns()
    var _ns_fused_matmul_bias_gelu = Float64(_t1_fused_matmul_bias_gelu - _t0_fused_matmul_bias_gelu) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_matmul_bias_gelu", _ns_fused_matmul_bias_gelu, _acc_fused_matmul_bias_gelu)
    var _acc_fused_rope_attention: Float64 = 0.0
    var _t0_fused_rope_attention = perf_counter_ns()
    for _ in range(N):
        _acc_fused_rope_attention += fused_rope_attention(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_rope_attention = perf_counter_ns()
    var _ns_fused_rope_attention = Float64(_t1_fused_rope_attention - _t0_fused_rope_attention) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_rope_attention", _ns_fused_rope_attention, _acc_fused_rope_attention)
    var _acc_fused_add_norm: Float64 = 0.0
    var _t0_fused_add_norm = perf_counter_ns()
    for _ in range(N):
        _acc_fused_add_norm += fused_add_norm(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_fused_add_norm = perf_counter_ns()
    var _ns_fused_add_norm = Float64(_t1_fused_add_norm - _t0_fused_add_norm) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_add_norm", _ns_fused_add_norm, _acc_fused_add_norm)
    var _acc_fused_scale_shift: Float64 = 0.0
    var _t0_fused_scale_shift = perf_counter_ns()
    for _ in range(N):
        _acc_fused_scale_shift += fused_scale_shift(0.5, 0.5, 0.5)
    var _t1_fused_scale_shift = perf_counter_ns()
    var _ns_fused_scale_shift = Float64(_t1_fused_scale_shift - _t0_fused_scale_shift) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_scale_shift", _ns_fused_scale_shift, _acc_fused_scale_shift)
    var _acc_fused_dropout_residual: Float64 = 0.0
    var _t0_fused_dropout_residual = perf_counter_ns()
    for _ in range(N):
        _acc_fused_dropout_residual += fused_dropout_residual(0.5, 0.5, 0.5, 0.5)
    var _t1_fused_dropout_residual = perf_counter_ns()
    var _ns_fused_dropout_residual = Float64(_t1_fused_dropout_residual - _t0_fused_dropout_residual) / Float64(N)
    print("MOJO_TIMING fused_kernels::fused_dropout_residual", _ns_fused_dropout_residual, _acc_fused_dropout_residual)
    var _acc_kernel_fusion_savings: Float64 = 0.0
    var _t0_kernel_fusion_savings = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_fusion_savings += kernel_fusion_savings(0.5, 0.5, 0.5)
    var _t1_kernel_fusion_savings = perf_counter_ns()
    var _ns_kernel_fusion_savings = Float64(_t1_kernel_fusion_savings - _t0_kernel_fusion_savings) / Float64(N)
    print("MOJO_TIMING fused_kernels::kernel_fusion_savings", _ns_kernel_fusion_savings, _acc_kernel_fusion_savings)
