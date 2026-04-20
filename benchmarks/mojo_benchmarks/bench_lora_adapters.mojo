"""bench_lora_adapters.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from lora_adapters import lora_forward, lora_merge_weight, qlora_dequant_forward, lora_gradient_a, lora_gradient_b, adapter_scaling_factor, prefix_tuning_key_aug, prompt_tuning_embed, dora_magnitude_scale, adapter_param_efficiency
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

    var _acc_lora_forward: Float64 = 0.0
    var _t0_lora_forward = perf_counter_ns()
    for _ in range(N):
        _acc_lora_forward += lora_forward(0.5, 0.5, 0.5, 0.5)
    var _t1_lora_forward = perf_counter_ns()
    var _ns_lora_forward = Float64(_t1_lora_forward - _t0_lora_forward) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_forward", _ns_lora_forward, _acc_lora_forward)
    var _acc_lora_merge_weight: Float64 = 0.0
    var _t0_lora_merge_weight = perf_counter_ns()
    for _ in range(N):
        _acc_lora_merge_weight += lora_merge_weight(0.5, 0.5, 0.5, 0.5)
    var _t1_lora_merge_weight = perf_counter_ns()
    var _ns_lora_merge_weight = Float64(_t1_lora_merge_weight - _t0_lora_merge_weight) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_merge_weight", _ns_lora_merge_weight, _acc_lora_merge_weight)
    var _acc_qlora_dequant_forward: Float64 = 0.0
    var _t0_qlora_dequant_forward = perf_counter_ns()
    for _ in range(N):
        _acc_qlora_dequant_forward += qlora_dequant_forward(0.5, 0.5, 0.5, 0.5)
    var _t1_qlora_dequant_forward = perf_counter_ns()
    var _ns_qlora_dequant_forward = Float64(_t1_qlora_dequant_forward - _t0_qlora_dequant_forward) / Float64(N)
    print("MOJO_TIMING lora_adapters::qlora_dequant_forward", _ns_qlora_dequant_forward, _acc_qlora_dequant_forward)
    var _acc_lora_gradient_a: Float64 = 0.0
    var _t0_lora_gradient_a = perf_counter_ns()
    for _ in range(N):
        _acc_lora_gradient_a += lora_gradient_a(0.5, 0.5, 0.5, 0.5)
    var _t1_lora_gradient_a = perf_counter_ns()
    var _ns_lora_gradient_a = Float64(_t1_lora_gradient_a - _t0_lora_gradient_a) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_gradient_a", _ns_lora_gradient_a, _acc_lora_gradient_a)
    var _acc_lora_gradient_b: Float64 = 0.0
    var _t0_lora_gradient_b = perf_counter_ns()
    for _ in range(N):
        _acc_lora_gradient_b += lora_gradient_b(0.5, 0.5, 0.5)
    var _t1_lora_gradient_b = perf_counter_ns()
    var _ns_lora_gradient_b = Float64(_t1_lora_gradient_b - _t0_lora_gradient_b) / Float64(N)
    print("MOJO_TIMING lora_adapters::lora_gradient_b", _ns_lora_gradient_b, _acc_lora_gradient_b)
    var _acc_adapter_scaling_factor: Float64 = 0.0
    var _t0_adapter_scaling_factor = perf_counter_ns()
    for _ in range(N):
        _acc_adapter_scaling_factor += adapter_scaling_factor(0.5, 0.5)
    var _t1_adapter_scaling_factor = perf_counter_ns()
    var _ns_adapter_scaling_factor = Float64(_t1_adapter_scaling_factor - _t0_adapter_scaling_factor) / Float64(N)
    print("MOJO_TIMING lora_adapters::adapter_scaling_factor", _ns_adapter_scaling_factor, _acc_adapter_scaling_factor)
    var _acc_prefix_tuning_key_aug: Float64 = 0.0
    var _t0_prefix_tuning_key_aug = perf_counter_ns()
    for _ in range(N):
        _acc_prefix_tuning_key_aug += prefix_tuning_key_aug(0.5, 0.5, 0.5, 0.5)
    var _t1_prefix_tuning_key_aug = perf_counter_ns()
    var _ns_prefix_tuning_key_aug = Float64(_t1_prefix_tuning_key_aug - _t0_prefix_tuning_key_aug) / Float64(N)
    print("MOJO_TIMING lora_adapters::prefix_tuning_key_aug", _ns_prefix_tuning_key_aug, _acc_prefix_tuning_key_aug)
    var _acc_prompt_tuning_embed: Float64 = 0.0
    var _t0_prompt_tuning_embed = perf_counter_ns()
    for _ in range(N):
        _acc_prompt_tuning_embed += prompt_tuning_embed(0.5, 0.5, 0.5, 0.5)
    var _t1_prompt_tuning_embed = perf_counter_ns()
    var _ns_prompt_tuning_embed = Float64(_t1_prompt_tuning_embed - _t0_prompt_tuning_embed) / Float64(N)
    print("MOJO_TIMING lora_adapters::prompt_tuning_embed", _ns_prompt_tuning_embed, _acc_prompt_tuning_embed)
    var _acc_dora_magnitude_scale: Float64 = 0.0
    var _t0_dora_magnitude_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dora_magnitude_scale += dora_magnitude_scale(0.5, 0.5, 0.5)
    var _t1_dora_magnitude_scale = perf_counter_ns()
    var _ns_dora_magnitude_scale = Float64(_t1_dora_magnitude_scale - _t0_dora_magnitude_scale) / Float64(N)
    print("MOJO_TIMING lora_adapters::dora_magnitude_scale", _ns_dora_magnitude_scale, _acc_dora_magnitude_scale)
    var _acc_adapter_param_efficiency: Float64 = 0.0
    var _t0_adapter_param_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_adapter_param_efficiency += adapter_param_efficiency(0.5, 0.5)
    var _t1_adapter_param_efficiency = perf_counter_ns()
    var _ns_adapter_param_efficiency = Float64(_t1_adapter_param_efficiency - _t0_adapter_param_efficiency) / Float64(N)
    print("MOJO_TIMING lora_adapters::adapter_param_efficiency", _ns_adapter_param_efficiency, _acc_adapter_param_efficiency)
