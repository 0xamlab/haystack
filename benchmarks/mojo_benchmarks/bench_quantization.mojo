"""bench_quantization.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from quantization import quantize_symmetric, dequantize_symmetric, quantize_asymmetric, dequantize_asymmetric, quantization_error, scale_from_range, zero_point_from_range, clamp_to_int8, fp16_to_fp32_scale, int4_pack_error
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

    var _acc_quantize_symmetric: Float64 = 0.0
    var _t0_quantize_symmetric = perf_counter_ns()
    for _ in range(N):
        _acc_quantize_symmetric += quantize_symmetric(0.5, 0.5)
    var _t1_quantize_symmetric = perf_counter_ns()
    var _ns_quantize_symmetric = Float64(_t1_quantize_symmetric - _t0_quantize_symmetric) / Float64(N)
    print("MOJO_TIMING quantization::quantize_symmetric", _ns_quantize_symmetric, _acc_quantize_symmetric)
    var _result_quantize_symmetric = quantize_symmetric(0.5, 0.5)
    var _summary_quantize_symmetric = _summary_float64(_result_quantize_symmetric)
    print("MOJO_RESULT quantization::quantize_symmetric", _summary_quantize_symmetric)
    var _acc_dequantize_symmetric: Float64 = 0.0
    var _t0_dequantize_symmetric = perf_counter_ns()
    for _ in range(N):
        _acc_dequantize_symmetric += dequantize_symmetric(0.5, 0.5)
    var _t1_dequantize_symmetric = perf_counter_ns()
    var _ns_dequantize_symmetric = Float64(_t1_dequantize_symmetric - _t0_dequantize_symmetric) / Float64(N)
    print("MOJO_TIMING quantization::dequantize_symmetric", _ns_dequantize_symmetric, _acc_dequantize_symmetric)
    var _result_dequantize_symmetric = dequantize_symmetric(0.5, 0.5)
    var _summary_dequantize_symmetric = _summary_float64(_result_dequantize_symmetric)
    print("MOJO_RESULT quantization::dequantize_symmetric", _summary_dequantize_symmetric)
    var _acc_quantize_asymmetric: Float64 = 0.0
    var _t0_quantize_asymmetric = perf_counter_ns()
    for _ in range(N):
        _acc_quantize_asymmetric += quantize_asymmetric(0.5, 0.5, 0.5)
    var _t1_quantize_asymmetric = perf_counter_ns()
    var _ns_quantize_asymmetric = Float64(_t1_quantize_asymmetric - _t0_quantize_asymmetric) / Float64(N)
    print("MOJO_TIMING quantization::quantize_asymmetric", _ns_quantize_asymmetric, _acc_quantize_asymmetric)
    var _result_quantize_asymmetric = quantize_asymmetric(0.5, 0.5, 0.5)
    var _summary_quantize_asymmetric = _summary_float64(_result_quantize_asymmetric)
    print("MOJO_RESULT quantization::quantize_asymmetric", _summary_quantize_asymmetric)
    var _acc_dequantize_asymmetric: Float64 = 0.0
    var _t0_dequantize_asymmetric = perf_counter_ns()
    for _ in range(N):
        _acc_dequantize_asymmetric += dequantize_asymmetric(0.5, 0.5, 0.5)
    var _t1_dequantize_asymmetric = perf_counter_ns()
    var _ns_dequantize_asymmetric = Float64(_t1_dequantize_asymmetric - _t0_dequantize_asymmetric) / Float64(N)
    print("MOJO_TIMING quantization::dequantize_asymmetric", _ns_dequantize_asymmetric, _acc_dequantize_asymmetric)
    var _result_dequantize_asymmetric = dequantize_asymmetric(0.5, 0.5, 0.5)
    var _summary_dequantize_asymmetric = _summary_float64(_result_dequantize_asymmetric)
    print("MOJO_RESULT quantization::dequantize_asymmetric", _summary_dequantize_asymmetric)
    var _acc_quantization_error: Float64 = 0.0
    var _t0_quantization_error = perf_counter_ns()
    for _ in range(N):
        _acc_quantization_error += quantization_error(0.5, 0.5)
    var _t1_quantization_error = perf_counter_ns()
    var _ns_quantization_error = Float64(_t1_quantization_error - _t0_quantization_error) / Float64(N)
    print("MOJO_TIMING quantization::quantization_error", _ns_quantization_error, _acc_quantization_error)
    var _result_quantization_error = quantization_error(0.5, 0.5)
    var _summary_quantization_error = _summary_float64(_result_quantization_error)
    print("MOJO_RESULT quantization::quantization_error", _summary_quantization_error)
    var _acc_scale_from_range: Float64 = 0.0
    var _t0_scale_from_range = perf_counter_ns()
    for _ in range(N):
        _acc_scale_from_range += scale_from_range(0.5, 0.5)
    var _t1_scale_from_range = perf_counter_ns()
    var _ns_scale_from_range = Float64(_t1_scale_from_range - _t0_scale_from_range) / Float64(N)
    print("MOJO_TIMING quantization::scale_from_range", _ns_scale_from_range, _acc_scale_from_range)
    var _result_scale_from_range = scale_from_range(0.5, 0.5)
    var _summary_scale_from_range = _summary_float64(_result_scale_from_range)
    print("MOJO_RESULT quantization::scale_from_range", _summary_scale_from_range)
    var _acc_zero_point_from_range: Float64 = 0.0
    var _t0_zero_point_from_range = perf_counter_ns()
    for _ in range(N):
        _acc_zero_point_from_range += zero_point_from_range(0.5, 0.5, 0.5)
    var _t1_zero_point_from_range = perf_counter_ns()
    var _ns_zero_point_from_range = Float64(_t1_zero_point_from_range - _t0_zero_point_from_range) / Float64(N)
    print("MOJO_TIMING quantization::zero_point_from_range", _ns_zero_point_from_range, _acc_zero_point_from_range)
    var _result_zero_point_from_range = zero_point_from_range(0.5, 0.5, 0.5)
    var _summary_zero_point_from_range = _summary_float64(_result_zero_point_from_range)
    print("MOJO_RESULT quantization::zero_point_from_range", _summary_zero_point_from_range)
    var _acc_clamp_to_int8: Float64 = 0.0
    var _t0_clamp_to_int8 = perf_counter_ns()
    for _ in range(N):
        _acc_clamp_to_int8 += clamp_to_int8(0.5)
    var _t1_clamp_to_int8 = perf_counter_ns()
    var _ns_clamp_to_int8 = Float64(_t1_clamp_to_int8 - _t0_clamp_to_int8) / Float64(N)
    print("MOJO_TIMING quantization::clamp_to_int8", _ns_clamp_to_int8, _acc_clamp_to_int8)
    var _result_clamp_to_int8 = clamp_to_int8(0.5)
    var _summary_clamp_to_int8 = _summary_float64(_result_clamp_to_int8)
    print("MOJO_RESULT quantization::clamp_to_int8", _summary_clamp_to_int8)
    var _acc_fp16_to_fp32_scale: Float64 = 0.0
    var _t0_fp16_to_fp32_scale = perf_counter_ns()
    for _ in range(N):
        _acc_fp16_to_fp32_scale += fp16_to_fp32_scale(0.5)
    var _t1_fp16_to_fp32_scale = perf_counter_ns()
    var _ns_fp16_to_fp32_scale = Float64(_t1_fp16_to_fp32_scale - _t0_fp16_to_fp32_scale) / Float64(N)
    print("MOJO_TIMING quantization::fp16_to_fp32_scale", _ns_fp16_to_fp32_scale, _acc_fp16_to_fp32_scale)
    var _result_fp16_to_fp32_scale = fp16_to_fp32_scale(0.5)
    var _summary_fp16_to_fp32_scale = _summary_float64(_result_fp16_to_fp32_scale)
    print("MOJO_RESULT quantization::fp16_to_fp32_scale", _summary_fp16_to_fp32_scale)
    var _acc_int4_pack_error: Float64 = 0.0
    var _t0_int4_pack_error = perf_counter_ns()
    for _ in range(N):
        _acc_int4_pack_error += int4_pack_error(0.5, 0.5)
    var _t1_int4_pack_error = perf_counter_ns()
    var _ns_int4_pack_error = Float64(_t1_int4_pack_error - _t0_int4_pack_error) / Float64(N)
    print("MOJO_TIMING quantization::int4_pack_error", _ns_int4_pack_error, _acc_int4_pack_error)
    var _result_int4_pack_error = int4_pack_error(0.5, 0.5)
    var _summary_int4_pack_error = _summary_float64(_result_int4_pack_error)
    print("MOJO_RESULT quantization::int4_pack_error", _summary_int4_pack_error)
