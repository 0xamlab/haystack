"""bench_quantization_stack.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from quantization_stack import bf16_to_fp32_round, fp16_overflow_check, absmax_calibration_scale, percentile_calibration_scale, smooth_quant_scale, gptq_hessian_update, awq_activation_scale, bnb_double_quant_scale, kv_cache_int8_scale, quant_aware_straight_through
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

    var _acc_bf16_to_fp32_round: Float64 = 0.0
    var _t0_bf16_to_fp32_round = perf_counter_ns()
    for _ in range(N):
        _acc_bf16_to_fp32_round += bf16_to_fp32_round(0.5)
    var _t1_bf16_to_fp32_round = perf_counter_ns()
    var _ns_bf16_to_fp32_round = Float64(_t1_bf16_to_fp32_round - _t0_bf16_to_fp32_round) / Float64(N)
    print("MOJO_TIMING quantization_stack::bf16_to_fp32_round", _ns_bf16_to_fp32_round, _acc_bf16_to_fp32_round)
    var _result_bf16_to_fp32_round = bf16_to_fp32_round(0.5)
    var _summary_bf16_to_fp32_round = _summary_float64(_result_bf16_to_fp32_round)
    print("MOJO_RESULT quantization_stack::bf16_to_fp32_round", _summary_bf16_to_fp32_round)
    var _acc_fp16_overflow_check: Float64 = 0.0
    var _t0_fp16_overflow_check = perf_counter_ns()
    for _ in range(N):
        _acc_fp16_overflow_check += fp16_overflow_check(0.5)
    var _t1_fp16_overflow_check = perf_counter_ns()
    var _ns_fp16_overflow_check = Float64(_t1_fp16_overflow_check - _t0_fp16_overflow_check) / Float64(N)
    print("MOJO_TIMING quantization_stack::fp16_overflow_check", _ns_fp16_overflow_check, _acc_fp16_overflow_check)
    var _result_fp16_overflow_check = fp16_overflow_check(0.5)
    var _summary_fp16_overflow_check = _summary_float64(_result_fp16_overflow_check)
    print("MOJO_RESULT quantization_stack::fp16_overflow_check", _summary_fp16_overflow_check)
    var _acc_absmax_calibration_scale: Float64 = 0.0
    var _t0_absmax_calibration_scale = perf_counter_ns()
    for _ in range(N):
        _acc_absmax_calibration_scale += absmax_calibration_scale(0.5, 0.5)
    var _t1_absmax_calibration_scale = perf_counter_ns()
    var _ns_absmax_calibration_scale = Float64(_t1_absmax_calibration_scale - _t0_absmax_calibration_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::absmax_calibration_scale", _ns_absmax_calibration_scale, _acc_absmax_calibration_scale)
    var _result_absmax_calibration_scale = absmax_calibration_scale(0.5, 0.5)
    var _summary_absmax_calibration_scale = _summary_float64(_result_absmax_calibration_scale)
    print("MOJO_RESULT quantization_stack::absmax_calibration_scale", _summary_absmax_calibration_scale)
    var _acc_percentile_calibration_scale: Float64 = 0.0
    var _t0_percentile_calibration_scale = perf_counter_ns()
    for _ in range(N):
        _acc_percentile_calibration_scale += percentile_calibration_scale(0.5, 0.5)
    var _t1_percentile_calibration_scale = perf_counter_ns()
    var _ns_percentile_calibration_scale = Float64(_t1_percentile_calibration_scale - _t0_percentile_calibration_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::percentile_calibration_scale", _ns_percentile_calibration_scale, _acc_percentile_calibration_scale)
    var _result_percentile_calibration_scale = percentile_calibration_scale(0.5, 0.5)
    var _summary_percentile_calibration_scale = _summary_float64(_result_percentile_calibration_scale)
    print("MOJO_RESULT quantization_stack::percentile_calibration_scale", _summary_percentile_calibration_scale)
    var _acc_smooth_quant_scale: Float64 = 0.0
    var _t0_smooth_quant_scale = perf_counter_ns()
    for _ in range(N):
        _acc_smooth_quant_scale += smooth_quant_scale(0.5, 0.5, 0.5)
    var _t1_smooth_quant_scale = perf_counter_ns()
    var _ns_smooth_quant_scale = Float64(_t1_smooth_quant_scale - _t0_smooth_quant_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::smooth_quant_scale", _ns_smooth_quant_scale, _acc_smooth_quant_scale)
    var _result_smooth_quant_scale = smooth_quant_scale(0.5, 0.5, 0.5)
    var _summary_smooth_quant_scale = _summary_float64(_result_smooth_quant_scale)
    print("MOJO_RESULT quantization_stack::smooth_quant_scale", _summary_smooth_quant_scale)
    var _acc_gptq_hessian_update: Float64 = 0.0
    var _t0_gptq_hessian_update = perf_counter_ns()
    for _ in range(N):
        _acc_gptq_hessian_update += gptq_hessian_update(0.5, 0.5, 0.5)
    var _t1_gptq_hessian_update = perf_counter_ns()
    var _ns_gptq_hessian_update = Float64(_t1_gptq_hessian_update - _t0_gptq_hessian_update) / Float64(N)
    print("MOJO_TIMING quantization_stack::gptq_hessian_update", _ns_gptq_hessian_update, _acc_gptq_hessian_update)
    var _result_gptq_hessian_update = gptq_hessian_update(0.5, 0.5, 0.5)
    var _summary_gptq_hessian_update = _summary_float64(_result_gptq_hessian_update)
    print("MOJO_RESULT quantization_stack::gptq_hessian_update", _summary_gptq_hessian_update)
    var _acc_awq_activation_scale: Float64 = 0.0
    var _t0_awq_activation_scale = perf_counter_ns()
    for _ in range(N):
        _acc_awq_activation_scale += awq_activation_scale(0.5, 0.5)
    var _t1_awq_activation_scale = perf_counter_ns()
    var _ns_awq_activation_scale = Float64(_t1_awq_activation_scale - _t0_awq_activation_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::awq_activation_scale", _ns_awq_activation_scale, _acc_awq_activation_scale)
    var _result_awq_activation_scale = awq_activation_scale(0.5, 0.5)
    var _summary_awq_activation_scale = _summary_float64(_result_awq_activation_scale)
    print("MOJO_RESULT quantization_stack::awq_activation_scale", _summary_awq_activation_scale)
    var _acc_bnb_double_quant_scale: Float64 = 0.0
    var _t0_bnb_double_quant_scale = perf_counter_ns()
    for _ in range(N):
        _acc_bnb_double_quant_scale += bnb_double_quant_scale(0.5, 0.5)
    var _t1_bnb_double_quant_scale = perf_counter_ns()
    var _ns_bnb_double_quant_scale = Float64(_t1_bnb_double_quant_scale - _t0_bnb_double_quant_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::bnb_double_quant_scale", _ns_bnb_double_quant_scale, _acc_bnb_double_quant_scale)
    var _result_bnb_double_quant_scale = bnb_double_quant_scale(0.5, 0.5)
    var _summary_bnb_double_quant_scale = _summary_float64(_result_bnb_double_quant_scale)
    print("MOJO_RESULT quantization_stack::bnb_double_quant_scale", _summary_bnb_double_quant_scale)
    var _acc_kv_cache_int8_scale: Float64 = 0.0
    var _t0_kv_cache_int8_scale = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_int8_scale += kv_cache_int8_scale(0.5)
    var _t1_kv_cache_int8_scale = perf_counter_ns()
    var _ns_kv_cache_int8_scale = Float64(_t1_kv_cache_int8_scale - _t0_kv_cache_int8_scale) / Float64(N)
    print("MOJO_TIMING quantization_stack::kv_cache_int8_scale", _ns_kv_cache_int8_scale, _acc_kv_cache_int8_scale)
    var _result_kv_cache_int8_scale = kv_cache_int8_scale(0.5)
    var _summary_kv_cache_int8_scale = _summary_float64(_result_kv_cache_int8_scale)
    print("MOJO_RESULT quantization_stack::kv_cache_int8_scale", _summary_kv_cache_int8_scale)
    var _acc_quant_aware_straight_through: Float64 = 0.0
    var _t0_quant_aware_straight_through = perf_counter_ns()
    for _ in range(N):
        _acc_quant_aware_straight_through += quant_aware_straight_through(0.5, 0.5, 0.5, 0.5)
    var _t1_quant_aware_straight_through = perf_counter_ns()
    var _ns_quant_aware_straight_through = Float64(_t1_quant_aware_straight_through - _t0_quant_aware_straight_through) / Float64(N)
    print("MOJO_TIMING quantization_stack::quant_aware_straight_through", _ns_quant_aware_straight_through, _acc_quant_aware_straight_through)
    var _result_quant_aware_straight_through = quant_aware_straight_through(0.5, 0.5, 0.5, 0.5)
    var _summary_quant_aware_straight_through = _summary_float64(_result_quant_aware_straight_through)
    print("MOJO_RESULT quantization_stack::quant_aware_straight_through", _summary_quant_aware_straight_through)
