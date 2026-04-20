"""bench_quantization.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from quantization import quantize_symmetric, dequantize_symmetric, quantize_asymmetric, dequantize_asymmetric, quantization_error, scale_from_range, zero_point_from_range, clamp_to_int8, fp16_to_fp32_scale, int4_pack_error
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

    var _acc_quantize_symmetric: Float64 = 0.0
    var _t0_quantize_symmetric = perf_counter_ns()
    for _ in range(N):
        _acc_quantize_symmetric += quantize_symmetric(0.5, 0.5)
    var _t1_quantize_symmetric = perf_counter_ns()
    var _ns_quantize_symmetric = Float64(_t1_quantize_symmetric - _t0_quantize_symmetric) / Float64(N)
    print("MOJO_TIMING quantization::quantize_symmetric", _ns_quantize_symmetric, _acc_quantize_symmetric)
    var _acc_dequantize_symmetric: Float64 = 0.0
    var _t0_dequantize_symmetric = perf_counter_ns()
    for _ in range(N):
        _acc_dequantize_symmetric += dequantize_symmetric(0.5, 0.5)
    var _t1_dequantize_symmetric = perf_counter_ns()
    var _ns_dequantize_symmetric = Float64(_t1_dequantize_symmetric - _t0_dequantize_symmetric) / Float64(N)
    print("MOJO_TIMING quantization::dequantize_symmetric", _ns_dequantize_symmetric, _acc_dequantize_symmetric)
    var _acc_quantize_asymmetric: Float64 = 0.0
    var _t0_quantize_asymmetric = perf_counter_ns()
    for _ in range(N):
        _acc_quantize_asymmetric += quantize_asymmetric(0.5, 0.5, 0.5)
    var _t1_quantize_asymmetric = perf_counter_ns()
    var _ns_quantize_asymmetric = Float64(_t1_quantize_asymmetric - _t0_quantize_asymmetric) / Float64(N)
    print("MOJO_TIMING quantization::quantize_asymmetric", _ns_quantize_asymmetric, _acc_quantize_asymmetric)
    var _acc_dequantize_asymmetric: Float64 = 0.0
    var _t0_dequantize_asymmetric = perf_counter_ns()
    for _ in range(N):
        _acc_dequantize_asymmetric += dequantize_asymmetric(0.5, 0.5, 0.5)
    var _t1_dequantize_asymmetric = perf_counter_ns()
    var _ns_dequantize_asymmetric = Float64(_t1_dequantize_asymmetric - _t0_dequantize_asymmetric) / Float64(N)
    print("MOJO_TIMING quantization::dequantize_asymmetric", _ns_dequantize_asymmetric, _acc_dequantize_asymmetric)
    var _acc_quantization_error: Float64 = 0.0
    var _t0_quantization_error = perf_counter_ns()
    for _ in range(N):
        _acc_quantization_error += quantization_error(0.5, 0.5)
    var _t1_quantization_error = perf_counter_ns()
    var _ns_quantization_error = Float64(_t1_quantization_error - _t0_quantization_error) / Float64(N)
    print("MOJO_TIMING quantization::quantization_error", _ns_quantization_error, _acc_quantization_error)
    var _acc_scale_from_range: Float64 = 0.0
    var _t0_scale_from_range = perf_counter_ns()
    for _ in range(N):
        _acc_scale_from_range += scale_from_range(0.5, 0.5)
    var _t1_scale_from_range = perf_counter_ns()
    var _ns_scale_from_range = Float64(_t1_scale_from_range - _t0_scale_from_range) / Float64(N)
    print("MOJO_TIMING quantization::scale_from_range", _ns_scale_from_range, _acc_scale_from_range)
    var _acc_zero_point_from_range: Float64 = 0.0
    var _t0_zero_point_from_range = perf_counter_ns()
    for _ in range(N):
        _acc_zero_point_from_range += zero_point_from_range(0.5, 0.5, 0.5)
    var _t1_zero_point_from_range = perf_counter_ns()
    var _ns_zero_point_from_range = Float64(_t1_zero_point_from_range - _t0_zero_point_from_range) / Float64(N)
    print("MOJO_TIMING quantization::zero_point_from_range", _ns_zero_point_from_range, _acc_zero_point_from_range)
    var _acc_clamp_to_int8: Float64 = 0.0
    var _t0_clamp_to_int8 = perf_counter_ns()
    for _ in range(N):
        _acc_clamp_to_int8 += clamp_to_int8(0.5)
    var _t1_clamp_to_int8 = perf_counter_ns()
    var _ns_clamp_to_int8 = Float64(_t1_clamp_to_int8 - _t0_clamp_to_int8) / Float64(N)
    print("MOJO_TIMING quantization::clamp_to_int8", _ns_clamp_to_int8, _acc_clamp_to_int8)
    var _acc_fp16_to_fp32_scale: Float64 = 0.0
    var _t0_fp16_to_fp32_scale = perf_counter_ns()
    for _ in range(N):
        _acc_fp16_to_fp32_scale += fp16_to_fp32_scale(0.5)
    var _t1_fp16_to_fp32_scale = perf_counter_ns()
    var _ns_fp16_to_fp32_scale = Float64(_t1_fp16_to_fp32_scale - _t0_fp16_to_fp32_scale) / Float64(N)
    print("MOJO_TIMING quantization::fp16_to_fp32_scale", _ns_fp16_to_fp32_scale, _acc_fp16_to_fp32_scale)
    var _acc_int4_pack_error: Float64 = 0.0
    var _t0_int4_pack_error = perf_counter_ns()
    for _ in range(N):
        _acc_int4_pack_error += int4_pack_error(0.5, 0.5)
    var _t1_int4_pack_error = perf_counter_ns()
    var _ns_int4_pack_error = Float64(_t1_int4_pack_error - _t0_int4_pack_error) / Float64(N)
    print("MOJO_TIMING quantization::int4_pack_error", _ns_int4_pack_error, _acc_int4_pack_error)
