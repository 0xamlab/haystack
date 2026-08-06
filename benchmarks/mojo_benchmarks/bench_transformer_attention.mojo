"""bench_transformer_attention.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from transformer_attention import scaled_dot_product_attention, attention_softmax_stable, multi_head_split, causal_mask_value, attention_entropy, kv_cache_memory_bytes, flash_attention_block_score, rope_rotation_angle, pow_approx, relative_position_bias, cross_attention_score
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

def _summary_list_float64_rounded6(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64_rounded6(value[i])
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
    var _lf12_colorcheck2x2 = List[Float64]()
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(200.0)
    var _lf48_video3x4x4 = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4.append(10.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4.append(200.0)
        else:
            _lf48_video3x4x4.append(10.0)
    for _ in range(16):
        _lf48_video3x4x4.append(200.0)
    var _lf48_video3x4x4_alt = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4_alt.append(12.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4_alt.append(188.0)
        else:
            _lf48_video3x4x4_alt.append(12.0)
    for _ in range(16):
        _lf48_video3x4x4_alt.append(192.0)
    var _lf36_video_rgb3x2x2 = List[Float64]()
    for _ in range(4):
        _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)
    for pixel in range(4):
        if pixel < 3:
            _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)
        else:
            _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)
    for _ in range(4):
        _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)
    var _lf25_block5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3:
                _lf25_block5x5.append(255.0)
            else:
                _lf25_block5x5.append(0.0)
    var _lf25_ring5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):
                _lf25_ring5x5.append(255.0)
            else:
                _lf25_ring5x5.append(0.0)
    var _lf36_components6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):
                _lf36_components6x6.append(255.0)
            else:
                _lf36_components6x6.append(0.0)
    var _lf64_doc8x8 = List[Float64]()
    var _lf64_doc8x8_alt = List[Float64]()
    var _lf64_docmask8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_doc8x8.append(20.0)
                _lf64_doc8x8_alt.append(60.0)
                _lf64_docmask8x8.append(255.0)
            else:
                _lf64_doc8x8.append(240.0)
                _lf64_doc8x8_alt.append(235.0)
                _lf64_docmask8x8.append(0.0)
    var _lf36_adaptive_doc6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y == 2 and x >= 2 and x <= 3:
                _lf36_adaptive_doc6x6.append(40.0)
            elif x < 3:
                _lf36_adaptive_doc6x6.append(220.0)
            else:
                _lf36_adaptive_doc6x6.append(245.0)
    var _lf36_skewmask6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y >= 1 and y <= 4 and x == y:
                _lf36_skewmask6x6.append(255.0)
            else:
                _lf36_skewmask6x6.append(0.0)
    var _lf64_blobdoc8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y >= 2 and y <= 4 and x >= 1 and x <= 3) or (x == 6 and (y == 1 or y == 2)):
                _lf64_blobdoc8x8.append(20.0)
            else:
                _lf64_blobdoc8x8.append(235.0)
    var _lf64_doccolumns8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):
                _lf64_doccolumns8x8.append(255.0)
            else:
                _lf64_doccolumns8x8.append(0.0)
    var _lf81_doctable9x9 = List[Float64]()
    for y in range(9):
        for x in range(9):
            if ((y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)) and ((x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)):
                _lf81_doctable9x9.append(255.0)
            else:
                _lf81_doctable9x9.append(0.0)
    var _lf256_texture16x16 = List[Float64]()
    for y in range(16):
        for x in range(16):
            if y >= 8 and x >= 8:
                _lf256_texture16x16.append(255.0 if (x + y) % 2 == 0 else 0.0)
            else:
                _lf256_texture16x16.append(64.0)
    var _lf75_video_motion3x5x5 = List[Float64]()
    for _ in range(25):
        _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 2 and x >= 1 and x <= 2:
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if (y >= 1 and y <= 2 and x >= 1 and x <= 2) or (x == 4 and y == 4):
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    var _lf16_grid4x4 = List[Float64]()
    for i in range(16):
        _lf16_grid4x4.append(Float64(i))
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _li4_box_a = List[Int]()
    _li4_box_a.append(0); _li4_box_a.append(0); _li4_box_a.append(2); _li4_box_a.append(2)
    var _li4_box_b = List[Int]()
    _li4_box_b.append(1); _li4_box_b.append(1); _li4_box_b.append(3); _li4_box_b.append(3)
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
    var _llf3_imageops = List[List[Float64]]()
    _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]())
    _llf3_imageops[0].append(0.5); _llf3_imageops[0].append(0.6); _llf3_imageops[0].append(0.7)
    _llf3_imageops[1].append(0.4); _llf3_imageops[1].append(0.3); _llf3_imageops[1].append(0.2)
    _llf3_imageops[2].append(0.1); _llf3_imageops[2].append(0.2); _llf3_imageops[2].append(0.3)
    var N: Int = 10000

    var _acc_scaled_dot_product_attention: Float64 = 0.0
    var _t0_scaled_dot_product_attention = perf_counter_ns()
    for _ in range(N):
        _acc_scaled_dot_product_attention += scaled_dot_product_attention(0.5, 0.5)
    var _t1_scaled_dot_product_attention = perf_counter_ns()
    var _ns_scaled_dot_product_attention = Float64(_t1_scaled_dot_product_attention - _t0_scaled_dot_product_attention) / Float64(N)
    print("MOJO_TIMING transformer_attention::scaled_dot_product_attention", _ns_scaled_dot_product_attention, _acc_scaled_dot_product_attention)
    var _result_scaled_dot_product_attention = scaled_dot_product_attention(0.5, 0.5)
    var _summary_scaled_dot_product_attention = _summary_float64(_result_scaled_dot_product_attention)
    print("MOJO_RESULT transformer_attention::scaled_dot_product_attention", _summary_scaled_dot_product_attention)
    var _acc_attention_softmax_stable: Float64 = 0.0
    var _t0_attention_softmax_stable = perf_counter_ns()
    for _ in range(N):
        _acc_attention_softmax_stable += attention_softmax_stable(0.5, 0.5, 0.5)
    var _t1_attention_softmax_stable = perf_counter_ns()
    var _ns_attention_softmax_stable = Float64(_t1_attention_softmax_stable - _t0_attention_softmax_stable) / Float64(N)
    print("MOJO_TIMING transformer_attention::attention_softmax_stable", _ns_attention_softmax_stable, _acc_attention_softmax_stable)
    var _result_attention_softmax_stable = attention_softmax_stable(0.5, 0.5, 0.5)
    var _summary_attention_softmax_stable = _summary_float64(_result_attention_softmax_stable)
    print("MOJO_RESULT transformer_attention::attention_softmax_stable", _summary_attention_softmax_stable)
    var _acc_multi_head_split: Float64 = 0.0
    var _t0_multi_head_split = perf_counter_ns()
    for _ in range(N):
        _acc_multi_head_split += multi_head_split(0.5, 0.5)
    var _t1_multi_head_split = perf_counter_ns()
    var _ns_multi_head_split = Float64(_t1_multi_head_split - _t0_multi_head_split) / Float64(N)
    print("MOJO_TIMING transformer_attention::multi_head_split", _ns_multi_head_split, _acc_multi_head_split)
    var _result_multi_head_split = multi_head_split(0.5, 0.5)
    var _summary_multi_head_split = _summary_float64(_result_multi_head_split)
    print("MOJO_RESULT transformer_attention::multi_head_split", _summary_multi_head_split)
    var _acc_causal_mask_value: Float64 = 0.0
    var _t0_causal_mask_value = perf_counter_ns()
    for _ in range(N):
        _acc_causal_mask_value += causal_mask_value(0.5, 0.5)
    var _t1_causal_mask_value = perf_counter_ns()
    var _ns_causal_mask_value = Float64(_t1_causal_mask_value - _t0_causal_mask_value) / Float64(N)
    print("MOJO_TIMING transformer_attention::causal_mask_value", _ns_causal_mask_value, _acc_causal_mask_value)
    var _result_causal_mask_value = causal_mask_value(0.5, 0.5)
    var _summary_causal_mask_value = _summary_float64(_result_causal_mask_value)
    print("MOJO_RESULT transformer_attention::causal_mask_value", _summary_causal_mask_value)
    var _acc_attention_entropy: Float64 = 0.0
    var _t0_attention_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_attention_entropy += attention_entropy(0.5, 0.5)
    var _t1_attention_entropy = perf_counter_ns()
    var _ns_attention_entropy = Float64(_t1_attention_entropy - _t0_attention_entropy) / Float64(N)
    print("MOJO_TIMING transformer_attention::attention_entropy", _ns_attention_entropy, _acc_attention_entropy)
    var _result_attention_entropy = attention_entropy(0.5, 0.5)
    var _summary_attention_entropy = _summary_float64(_result_attention_entropy)
    print("MOJO_RESULT transformer_attention::attention_entropy", _summary_attention_entropy)
    var _acc_kv_cache_memory_bytes: Float64 = 0.0
    var _t0_kv_cache_memory_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_memory_bytes += kv_cache_memory_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_kv_cache_memory_bytes = perf_counter_ns()
    var _ns_kv_cache_memory_bytes = Float64(_t1_kv_cache_memory_bytes - _t0_kv_cache_memory_bytes) / Float64(N)
    print("MOJO_TIMING transformer_attention::kv_cache_memory_bytes", _ns_kv_cache_memory_bytes, _acc_kv_cache_memory_bytes)
    var _result_kv_cache_memory_bytes = kv_cache_memory_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_kv_cache_memory_bytes = _summary_float64(_result_kv_cache_memory_bytes)
    print("MOJO_RESULT transformer_attention::kv_cache_memory_bytes", _summary_kv_cache_memory_bytes)
    var _acc_flash_attention_block_score: Float64 = 0.0
    var _t0_flash_attention_block_score = perf_counter_ns()
    for _ in range(N):
        _acc_flash_attention_block_score += flash_attention_block_score(0.5, 0.5, 0.5)
    var _t1_flash_attention_block_score = perf_counter_ns()
    var _ns_flash_attention_block_score = Float64(_t1_flash_attention_block_score - _t0_flash_attention_block_score) / Float64(N)
    print("MOJO_TIMING transformer_attention::flash_attention_block_score", _ns_flash_attention_block_score, _acc_flash_attention_block_score)
    var _result_flash_attention_block_score = flash_attention_block_score(0.5, 0.5, 0.5)
    var _summary_flash_attention_block_score = _summary_float64(_result_flash_attention_block_score)
    print("MOJO_RESULT transformer_attention::flash_attention_block_score", _summary_flash_attention_block_score)
    var _acc_rope_rotation_angle: Float64 = 0.0
    var _t0_rope_rotation_angle = perf_counter_ns()
    for _ in range(N):
        _acc_rope_rotation_angle += rope_rotation_angle(0.5, 0.5, 0.5, 0.5)
    var _t1_rope_rotation_angle = perf_counter_ns()
    var _ns_rope_rotation_angle = Float64(_t1_rope_rotation_angle - _t0_rope_rotation_angle) / Float64(N)
    print("MOJO_TIMING transformer_attention::rope_rotation_angle", _ns_rope_rotation_angle, _acc_rope_rotation_angle)
    var _result_rope_rotation_angle = rope_rotation_angle(0.5, 0.5, 0.5, 0.5)
    var _summary_rope_rotation_angle = _summary_float64(_result_rope_rotation_angle)
    print("MOJO_RESULT transformer_attention::rope_rotation_angle", _summary_rope_rotation_angle)
    var _acc_pow_approx: Float64 = 0.0
    var _t0_pow_approx = perf_counter_ns()
    for _ in range(N):
        _acc_pow_approx += pow_approx(0.5, 0.5)
    var _t1_pow_approx = perf_counter_ns()
    var _ns_pow_approx = Float64(_t1_pow_approx - _t0_pow_approx) / Float64(N)
    print("MOJO_TIMING transformer_attention::pow_approx", _ns_pow_approx, _acc_pow_approx)
    var _result_pow_approx = pow_approx(0.5, 0.5)
    var _summary_pow_approx = _summary_float64(_result_pow_approx)
    print("MOJO_RESULT transformer_attention::pow_approx", _summary_pow_approx)
    var _acc_relative_position_bias: Float64 = 0.0
    var _t0_relative_position_bias = perf_counter_ns()
    for _ in range(N):
        _acc_relative_position_bias += relative_position_bias(0.5, 0.5, 0.5, 0.5)
    var _t1_relative_position_bias = perf_counter_ns()
    var _ns_relative_position_bias = Float64(_t1_relative_position_bias - _t0_relative_position_bias) / Float64(N)
    print("MOJO_TIMING transformer_attention::relative_position_bias", _ns_relative_position_bias, _acc_relative_position_bias)
    var _result_relative_position_bias = relative_position_bias(0.5, 0.5, 0.5, 0.5)
    var _summary_relative_position_bias = _summary_float64(_result_relative_position_bias)
    print("MOJO_RESULT transformer_attention::relative_position_bias", _summary_relative_position_bias)
    var _acc_cross_attention_score: Float64 = 0.0
    var _t0_cross_attention_score = perf_counter_ns()
    for _ in range(N):
        _acc_cross_attention_score += cross_attention_score(0.5, 0.5, 0.5)
    var _t1_cross_attention_score = perf_counter_ns()
    var _ns_cross_attention_score = Float64(_t1_cross_attention_score - _t0_cross_attention_score) / Float64(N)
    print("MOJO_TIMING transformer_attention::cross_attention_score", _ns_cross_attention_score, _acc_cross_attention_score)
    var _result_cross_attention_score = cross_attention_score(0.5, 0.5, 0.5)
    var _summary_cross_attention_score = _summary_float64(_result_cross_attention_score)
    print("MOJO_RESULT transformer_attention::cross_attention_score", _summary_cross_attention_score)
