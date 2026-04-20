"""bench_quantization_stack.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from quantization_stack import bf16_to_fp32_round, fp16_overflow_check, absmax_calibration_scale, percentile_calibration_scale, smooth_quant_scale, gptq_hessian_update, awq_activation_scale, bnb_double_quant_scale, kv_cache_int8_scale, quant_aware_straight_through
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

    var _acc_bf16_to_fp32_round: Float64 = 0.0
    var _t0_bf16_to_fp32_round = perf_counter_ns()
    for _ in range(N):
        _acc_bf16_to_fp32_round += bf16_to_fp32_round(0.5)
    var _t1_bf16_to_fp32_round = perf_counter_ns()
    var _ns_bf16_to_fp32_round = Float64(_t1_bf16_to_fp32_round - _t0_bf16_to_fp32_round) / Float64(N)
    print("MOJO_TIMING quantization_stack::bf16_to_fp32_round", _ns_bf16_to_fp32_round, _acc_bf16_to_fp32_round)
    var _acc_fp16_overflow_check: Float64 = 0.0
    var _t0_fp16_overflow_check = perf_counter_ns()
    for _ in range(N):
        _acc_fp16_overflow_check += fp16_overflow_check(0.5)
    var _t1_fp16_overflow_check = perf_counter_ns()
    var _ns_fp16_overflow_check = Float64(_t1_fp16_overflow_check - _t0_fp16_overflow_check) / Float64(N)
    print("MOJO_TIMING quantization_stack::fp16_overflow_check", _ns_fp16_overflow_check, _acc_fp16_overflow_check)
    var _acc_absmax_calibration_scale: Float64 = 0.0
    var _t0_absmax_calibration_scale = perf_counter_ns()
    for _ in range(N):
        _acc_absmax_calibration_scale += absmax_calibration_scale(0.5, 0.5)
    var _t1_absmax_calibration_scale = perf_counter_ns()
    var _ns_absmax_calibration_scale = Float64(_t1_absmax_calibration_scale - _t0_absmax_calibration_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::absmax_calibration_scale", _ns_absmax_calibration_scale, _acc_absmax_calibration_scale)
    var _acc_percentile_calibration_scale: Float64 = 0.0
    var _t0_percentile_calibration_scale = perf_counter_ns()
    for _ in range(N):
        _acc_percentile_calibration_scale += percentile_calibration_scale(0.5, 0.5)
    var _t1_percentile_calibration_scale = perf_counter_ns()
    var _ns_percentile_calibration_scale = Float64(_t1_percentile_calibration_scale - _t0_percentile_calibration_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::percentile_calibration_scale", _ns_percentile_calibration_scale, _acc_percentile_calibration_scale)
    var _acc_smooth_quant_scale: Float64 = 0.0
    var _t0_smooth_quant_scale = perf_counter_ns()
    for _ in range(N):
        _acc_smooth_quant_scale += smooth_quant_scale(0.5, 0.5, 0.5)
    var _t1_smooth_quant_scale = perf_counter_ns()
    var _ns_smooth_quant_scale = Float64(_t1_smooth_quant_scale - _t0_smooth_quant_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::smooth_quant_scale", _ns_smooth_quant_scale, _acc_smooth_quant_scale)
    var _acc_gptq_hessian_update: Float64 = 0.0
    var _t0_gptq_hessian_update = perf_counter_ns()
    for _ in range(N):
        _acc_gptq_hessian_update += gptq_hessian_update(0.5, 0.5, 0.5)
    var _t1_gptq_hessian_update = perf_counter_ns()
    var _ns_gptq_hessian_update = Float64(_t1_gptq_hessian_update - _t0_gptq_hessian_update) / Float64(N)
    print("MOJO_TIMING quantization_stack::gptq_hessian_update", _ns_gptq_hessian_update, _acc_gptq_hessian_update)
    var _acc_awq_activation_scale: Float64 = 0.0
    var _t0_awq_activation_scale = perf_counter_ns()
    for _ in range(N):
        _acc_awq_activation_scale += awq_activation_scale(0.5, 0.5)
    var _t1_awq_activation_scale = perf_counter_ns()
    var _ns_awq_activation_scale = Float64(_t1_awq_activation_scale - _t0_awq_activation_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::awq_activation_scale", _ns_awq_activation_scale, _acc_awq_activation_scale)
    var _acc_bnb_double_quant_scale: Float64 = 0.0
    var _t0_bnb_double_quant_scale = perf_counter_ns()
    for _ in range(N):
        _acc_bnb_double_quant_scale += bnb_double_quant_scale(0.5, 0.5)
    var _t1_bnb_double_quant_scale = perf_counter_ns()
    var _ns_bnb_double_quant_scale = Float64(_t1_bnb_double_quant_scale - _t0_bnb_double_quant_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::bnb_double_quant_scale", _ns_bnb_double_quant_scale, _acc_bnb_double_quant_scale)
    var _acc_kv_cache_int8_scale: Float64 = 0.0
    var _t0_kv_cache_int8_scale = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_int8_scale += kv_cache_int8_scale(0.5)
    var _t1_kv_cache_int8_scale = perf_counter_ns()
    var _ns_kv_cache_int8_scale = Float64(_t1_kv_cache_int8_scale - _t0_kv_cache_int8_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::kv_cache_int8_scale", _ns_kv_cache_int8_scale, _acc_kv_cache_int8_scale)
    var _acc_quant_aware_straight_through: Float64 = 0.0
    var _t0_quant_aware_straight_through = perf_counter_ns()
    for _ in range(N):
        _acc_quant_aware_straight_through += quant_aware_straight_through(0.5, 0.5, 0.5, 0.5)
    var _t1_quant_aware_straight_through = perf_counter_ns()
    var _ns_quant_aware_straight_through = Float64(_t1_quant_aware_straight_through - _t0_quant_aware_straight_through) / Float64(N)
    print("MOJO_TIMING quantization_stack::quant_aware_straight_through", _ns_quant_aware_straight_through, _acc_quant_aware_straight_through)
