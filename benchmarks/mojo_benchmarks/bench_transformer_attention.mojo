"""bench_transformer_attention.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from transformer_attention import scaled_dot_product_attention, attention_softmax_stable, multi_head_split, causal_mask_value, attention_entropy, kv_cache_memory_bytes, flash_attention_block_score, rope_rotation_angle, pow_approx, relative_position_bias, cross_attention_score
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

    var _acc_scaled_dot_product_attention: Float64 = 0.0
    var _t0_scaled_dot_product_attention = perf_counter_ns()
    for _ in range(N):
        _acc_scaled_dot_product_attention += scaled_dot_product_attention(0.5, 0.5)
    var _t1_scaled_dot_product_attention = perf_counter_ns()
    var _ns_scaled_dot_product_attention = Float64(_t1_scaled_dot_product_attention - _t0_scaled_dot_product_attention) / Float64(N)
    print("MOJO_TIMING transformer_attention::scaled_dot_product_attention", _ns_scaled_dot_product_attention, _acc_scaled_dot_product_attention)
    var _acc_attention_softmax_stable: Float64 = 0.0
    var _t0_attention_softmax_stable = perf_counter_ns()
    for _ in range(N):
        _acc_attention_softmax_stable += attention_softmax_stable(0.5, 0.5, 0.5)
    var _t1_attention_softmax_stable = perf_counter_ns()
    var _ns_attention_softmax_stable = Float64(_t1_attention_softmax_stable - _t0_attention_softmax_stable) / Float64(N)
    print("MOJO_TIMING transformer_attention::attention_softmax_stable", _ns_attention_softmax_stable, _acc_attention_softmax_stable)
    var _acc_multi_head_split: Float64 = 0.0
    var _t0_multi_head_split = perf_counter_ns()
    for _ in range(N):
        _acc_multi_head_split += multi_head_split(0.5, 0.5)
    var _t1_multi_head_split = perf_counter_ns()
    var _ns_multi_head_split = Float64(_t1_multi_head_split - _t0_multi_head_split) / Float64(N)
    print("MOJO_TIMING transformer_attention::multi_head_split", _ns_multi_head_split, _acc_multi_head_split)
    var _acc_causal_mask_value: Float64 = 0.0
    var _t0_causal_mask_value = perf_counter_ns()
    for _ in range(N):
        _acc_causal_mask_value += causal_mask_value(0.5, 0.5)
    var _t1_causal_mask_value = perf_counter_ns()
    var _ns_causal_mask_value = Float64(_t1_causal_mask_value - _t0_causal_mask_value) / Float64(N)
    print("MOJO_TIMING transformer_attention::causal_mask_value", _ns_causal_mask_value, _acc_causal_mask_value)
    var _acc_attention_entropy: Float64 = 0.0
    var _t0_attention_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_attention_entropy += attention_entropy(0.5, 0.5)
    var _t1_attention_entropy = perf_counter_ns()
    var _ns_attention_entropy = Float64(_t1_attention_entropy - _t0_attention_entropy) / Float64(N)
    print("MOJO_TIMING transformer_attention::attention_entropy", _ns_attention_entropy, _acc_attention_entropy)
    var _acc_kv_cache_memory_bytes: Float64 = 0.0
    var _t0_kv_cache_memory_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_memory_bytes += kv_cache_memory_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_kv_cache_memory_bytes = perf_counter_ns()
    var _ns_kv_cache_memory_bytes = Float64(_t1_kv_cache_memory_bytes - _t0_kv_cache_memory_bytes) / Float64(N)
    print("MOJO_TIMING transformer_attention::kv_cache_memory_bytes", _ns_kv_cache_memory_bytes, _acc_kv_cache_memory_bytes)
    var _acc_flash_attention_block_score: Float64 = 0.0
    var _t0_flash_attention_block_score = perf_counter_ns()
    for _ in range(N):
        _acc_flash_attention_block_score += flash_attention_block_score(0.5, 0.5, 0.5)
    var _t1_flash_attention_block_score = perf_counter_ns()
    var _ns_flash_attention_block_score = Float64(_t1_flash_attention_block_score - _t0_flash_attention_block_score) / Float64(N)
    print("MOJO_TIMING transformer_attention::flash_attention_block_score", _ns_flash_attention_block_score, _acc_flash_attention_block_score)
    var _acc_rope_rotation_angle: Float64 = 0.0
    var _t0_rope_rotation_angle = perf_counter_ns()
    for _ in range(N):
        _acc_rope_rotation_angle += rope_rotation_angle(0.5, 0.5, 0.5, 0.5)
    var _t1_rope_rotation_angle = perf_counter_ns()
    var _ns_rope_rotation_angle = Float64(_t1_rope_rotation_angle - _t0_rope_rotation_angle) / Float64(N)
    print("MOJO_TIMING transformer_attention::rope_rotation_angle", _ns_rope_rotation_angle, _acc_rope_rotation_angle)
    var _acc_pow_approx: Float64 = 0.0
    var _t0_pow_approx = perf_counter_ns()
    for _ in range(N):
        _acc_pow_approx += pow_approx(0.5, 0.5)
    var _t1_pow_approx = perf_counter_ns()
    var _ns_pow_approx = Float64(_t1_pow_approx - _t0_pow_approx) / Float64(N)
    print("MOJO_TIMING transformer_attention::pow_approx", _ns_pow_approx, _acc_pow_approx)
    var _acc_relative_position_bias: Float64 = 0.0
    var _t0_relative_position_bias = perf_counter_ns()
    for _ in range(N):
        _acc_relative_position_bias += relative_position_bias(0.5, 0.5, 0.5, 0.5)
    var _t1_relative_position_bias = perf_counter_ns()
    var _ns_relative_position_bias = Float64(_t1_relative_position_bias - _t0_relative_position_bias) / Float64(N)
    print("MOJO_TIMING transformer_attention::relative_position_bias", _ns_relative_position_bias, _acc_relative_position_bias)
    var _acc_cross_attention_score: Float64 = 0.0
    var _t0_cross_attention_score = perf_counter_ns()
    for _ in range(N):
        _acc_cross_attention_score += cross_attention_score(0.5, 0.5, 0.5)
    var _t1_cross_attention_score = perf_counter_ns()
    var _ns_cross_attention_score = Float64(_t1_cross_attention_score - _t0_cross_attention_score) / Float64(N)
    print("MOJO_TIMING transformer_attention::cross_attention_score", _ns_cross_attention_score, _acc_cross_attention_score)
