"""bench_lora_adapters.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lora_adapters import lora_forward, lora_merge_weight, qlora_dequant_forward, lora_gradient_a, lora_gradient_b, adapter_scaling_factor, prefix_tuning_key_aug, prompt_tuning_embed, dora_magnitude_scale, adapter_param_efficiency
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

    var _acc_lora_forward: Float64 = 0.0
    var _t0_lora_forward = perf_counter_ns()
    for _ in range(N):
        _acc_lora_forward += lora_forward(0.5, 0.5, 0.5, 0.5)
    var _t1_lora_forward = perf_counter_ns()
    var _ns_lora_forward = Float64(_t1_lora_forward - _t0_lora_forward) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_forward", _ns_lora_forward, _acc_lora_forward)
    var _result_lora_forward = lora_forward(0.5, 0.5, 0.5, 0.5)
    var _summary_lora_forward = _summary_float64(_result_lora_forward)
    print("MOJO_RESULT lora_adapters::lora_forward", _summary_lora_forward)
    var _acc_lora_merge_weight: Float64 = 0.0
    var _t0_lora_merge_weight = perf_counter_ns()
    for _ in range(N):
        _acc_lora_merge_weight += lora_merge_weight(0.5, 0.5, 0.5, 0.5)
    var _t1_lora_merge_weight = perf_counter_ns()
    var _ns_lora_merge_weight = Float64(_t1_lora_merge_weight - _t0_lora_merge_weight) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_merge_weight", _ns_lora_merge_weight, _acc_lora_merge_weight)
    var _result_lora_merge_weight = lora_merge_weight(0.5, 0.5, 0.5, 0.5)
    var _summary_lora_merge_weight = _summary_float64(_result_lora_merge_weight)
    print("MOJO_RESULT lora_adapters::lora_merge_weight", _summary_lora_merge_weight)
    var _acc_qlora_dequant_forward: Float64 = 0.0
    var _t0_qlora_dequant_forward = perf_counter_ns()
    for _ in range(N):
        _acc_qlora_dequant_forward += qlora_dequant_forward(0.5, 0.5, 0.5, 0.5)
    var _t1_qlora_dequant_forward = perf_counter_ns()
    var _ns_qlora_dequant_forward = Float64(_t1_qlora_dequant_forward - _t0_qlora_dequant_forward) / Float64(N)
    print("MOJO_TIMING lora_adapters::qlora_dequant_forward", _ns_qlora_dequant_forward, _acc_qlora_dequant_forward)
    var _result_qlora_dequant_forward = qlora_dequant_forward(0.5, 0.5, 0.5, 0.5)
    var _summary_qlora_dequant_forward = _summary_float64(_result_qlora_dequant_forward)
    print("MOJO_RESULT lora_adapters::qlora_dequant_forward", _summary_qlora_dequant_forward)
    var _acc_lora_gradient_a: Float64 = 0.0
    var _t0_lora_gradient_a = perf_counter_ns()
    for _ in range(N):
        _acc_lora_gradient_a += lora_gradient_a(0.5, 0.5, 0.5, 0.5)
    var _t1_lora_gradient_a = perf_counter_ns()
    var _ns_lora_gradient_a = Float64(_t1_lora_gradient_a - _t0_lora_gradient_a) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_gradient_a", _ns_lora_gradient_a, _acc_lora_gradient_a)
    var _result_lora_gradient_a = lora_gradient_a(0.5, 0.5, 0.5, 0.5)
    var _summary_lora_gradient_a = _summary_float64(_result_lora_gradient_a)
    print("MOJO_RESULT lora_adapters::lora_gradient_a", _summary_lora_gradient_a)
    var _acc_lora_gradient_b: Float64 = 0.0
    var _t0_lora_gradient_b = perf_counter_ns()
    for _ in range(N):
        _acc_lora_gradient_b += lora_gradient_b(0.5, 0.5, 0.5)
    var _t1_lora_gradient_b = perf_counter_ns()
    var _ns_lora_gradient_b = Float64(_t1_lora_gradient_b - _t0_lora_gradient_b) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_gradient_b", _ns_lora_gradient_b, _acc_lora_gradient_b)
    var _result_lora_gradient_b = lora_gradient_b(0.5, 0.5, 0.5)
    var _summary_lora_gradient_b = _summary_float64(_result_lora_gradient_b)
    print("MOJO_RESULT lora_adapters::lora_gradient_b", _summary_lora_gradient_b)
    var _acc_adapter_scaling_factor: Float64 = 0.0
    var _t0_adapter_scaling_factor = perf_counter_ns()
    for _ in range(N):
        _acc_adapter_scaling_factor += adapter_scaling_factor(0.5, 0.5)
    var _t1_adapter_scaling_factor = perf_counter_ns()
    var _ns_adapter_scaling_factor = Float64(_t1_adapter_scaling_factor - _t0_adapter_scaling_factor) / Float64(N)
    print("MOJO_TIMING lora_adapters::adapter_scaling_factor", _ns_adapter_scaling_factor, _acc_adapter_scaling_factor)
    var _result_adapter_scaling_factor = adapter_scaling_factor(0.5, 0.5)
    var _summary_adapter_scaling_factor = _summary_float64(_result_adapter_scaling_factor)
    print("MOJO_RESULT lora_adapters::adapter_scaling_factor", _summary_adapter_scaling_factor)
    var _acc_prefix_tuning_key_aug: Float64 = 0.0
    var _t0_prefix_tuning_key_aug = perf_counter_ns()
    for _ in range(N):
        _acc_prefix_tuning_key_aug += prefix_tuning_key_aug(0.5, 0.5, 0.5, 0.5)
    var _t1_prefix_tuning_key_aug = perf_counter_ns()
    var _ns_prefix_tuning_key_aug = Float64(_t1_prefix_tuning_key_aug - _t0_prefix_tuning_key_aug) / Float64(N)
    print("MOJO_TIMING lora_adapters::prefix_tuning_key_aug", _ns_prefix_tuning_key_aug, _acc_prefix_tuning_key_aug)
    var _result_prefix_tuning_key_aug = prefix_tuning_key_aug(0.5, 0.5, 0.5, 0.5)
    var _summary_prefix_tuning_key_aug = _summary_float64(_result_prefix_tuning_key_aug)
    print("MOJO_RESULT lora_adapters::prefix_tuning_key_aug", _summary_prefix_tuning_key_aug)
    var _acc_prompt_tuning_embed: Float64 = 0.0
    var _t0_prompt_tuning_embed = perf_counter_ns()
    for _ in range(N):
        _acc_prompt_tuning_embed += prompt_tuning_embed(0.5, 0.5, 0.5, 0.5)
    var _t1_prompt_tuning_embed = perf_counter_ns()
    var _ns_prompt_tuning_embed = Float64(_t1_prompt_tuning_embed - _t0_prompt_tuning_embed) / Float64(N)
    print("MOJO_TIMING lora_adapters::prompt_tuning_embed", _ns_prompt_tuning_embed, _acc_prompt_tuning_embed)
    var _result_prompt_tuning_embed = prompt_tuning_embed(0.5, 0.5, 0.5, 0.5)
    var _summary_prompt_tuning_embed = _summary_float64(_result_prompt_tuning_embed)
    print("MOJO_RESULT lora_adapters::prompt_tuning_embed", _summary_prompt_tuning_embed)
    var _acc_dora_magnitude_scale: Float64 = 0.0
    var _t0_dora_magnitude_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dora_magnitude_scale += dora_magnitude_scale(0.5, 0.5, 0.5)
    var _t1_dora_magnitude_scale = perf_counter_ns()
    var _ns_dora_magnitude_scale = Float64(_t1_dora_magnitude_scale - _t0_dora_magnitude_scale) / Float64(N)
    print("MOJO_TIMING lora_adapters::dora_magnitude_scale", _ns_dora_magnitude_scale, _acc_dora_magnitude_scale)
    var _result_dora_magnitude_scale = dora_magnitude_scale(0.5, 0.5, 0.5)
    var _summary_dora_magnitude_scale = _summary_float64(_result_dora_magnitude_scale)
    print("MOJO_RESULT lora_adapters::dora_magnitude_scale", _summary_dora_magnitude_scale)
    var _acc_adapter_param_efficiency: Float64 = 0.0
    var _t0_adapter_param_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_adapter_param_efficiency += adapter_param_efficiency(0.5, 0.5)
    var _t1_adapter_param_efficiency = perf_counter_ns()
    var _ns_adapter_param_efficiency = Float64(_t1_adapter_param_efficiency - _t0_adapter_param_efficiency) / Float64(N)
    print("MOJO_TIMING lora_adapters::adapter_param_efficiency", _ns_adapter_param_efficiency, _acc_adapter_param_efficiency)
    var _result_adapter_param_efficiency = adapter_param_efficiency(0.5, 0.5)
    var _summary_adapter_param_efficiency = _summary_float64(_result_adapter_param_efficiency)
    print("MOJO_RESULT lora_adapters::adapter_param_efficiency", _summary_adapter_param_efficiency)
