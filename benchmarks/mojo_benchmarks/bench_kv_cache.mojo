"""bench_kv_cache.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from kv_cache import kv_cache_memory_per_layer, kv_cache_total_memory, kv_cache_utilization, paged_attention_block_count, prefix_cache_hit_bytes, kv_eviction_score_lru, kv_eviction_score_h2o, incremental_decode_kv_append, radix_cache_shared_prefix_len, kv_quantization_error
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

    var _acc_kv_cache_memory_per_layer: Float64 = 0.0
    var _t0_kv_cache_memory_per_layer = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_memory_per_layer += kv_cache_memory_per_layer(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_kv_cache_memory_per_layer = perf_counter_ns()
    var _ns_kv_cache_memory_per_layer = Float64(_t1_kv_cache_memory_per_layer - _t0_kv_cache_memory_per_layer) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_cache_memory_per_layer", _ns_kv_cache_memory_per_layer, _acc_kv_cache_memory_per_layer)
    var _result_kv_cache_memory_per_layer = kv_cache_memory_per_layer(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_kv_cache_memory_per_layer = _summary_float64(_result_kv_cache_memory_per_layer)
    print("MOJO_RESULT kv_cache::kv_cache_memory_per_layer", _summary_kv_cache_memory_per_layer)
    var _acc_kv_cache_total_memory: Float64 = 0.0
    var _t0_kv_cache_total_memory = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_total_memory += kv_cache_total_memory(0.5, 0.5)
    var _t1_kv_cache_total_memory = perf_counter_ns()
    var _ns_kv_cache_total_memory = Float64(_t1_kv_cache_total_memory - _t0_kv_cache_total_memory) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_cache_total_memory", _ns_kv_cache_total_memory, _acc_kv_cache_total_memory)
    var _result_kv_cache_total_memory = kv_cache_total_memory(0.5, 0.5)
    var _summary_kv_cache_total_memory = _summary_float64(_result_kv_cache_total_memory)
    print("MOJO_RESULT kv_cache::kv_cache_total_memory", _summary_kv_cache_total_memory)
    var _acc_kv_cache_utilization: Float64 = 0.0
    var _t0_kv_cache_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_utilization += kv_cache_utilization(0.5, 0.5)
    var _t1_kv_cache_utilization = perf_counter_ns()
    var _ns_kv_cache_utilization = Float64(_t1_kv_cache_utilization - _t0_kv_cache_utilization) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_cache_utilization", _ns_kv_cache_utilization, _acc_kv_cache_utilization)
    var _result_kv_cache_utilization = kv_cache_utilization(0.5, 0.5)
    var _summary_kv_cache_utilization = _summary_float64(_result_kv_cache_utilization)
    print("MOJO_RESULT kv_cache::kv_cache_utilization", _summary_kv_cache_utilization)
    var _acc_paged_attention_block_count: Float64 = 0.0
    var _t0_paged_attention_block_count = perf_counter_ns()
    for _ in range(N):
        _acc_paged_attention_block_count += paged_attention_block_count(0.5, 0.5)
    var _t1_paged_attention_block_count = perf_counter_ns()
    var _ns_paged_attention_block_count = Float64(_t1_paged_attention_block_count - _t0_paged_attention_block_count) / Float64(N)
    print("MOJO_TIMING kv_cache::paged_attention_block_count", _ns_paged_attention_block_count, _acc_paged_attention_block_count)
    var _result_paged_attention_block_count = paged_attention_block_count(0.5, 0.5)
    var _summary_paged_attention_block_count = _summary_float64(_result_paged_attention_block_count)
    print("MOJO_RESULT kv_cache::paged_attention_block_count", _summary_paged_attention_block_count)
    var _acc_prefix_cache_hit_bytes: Float64 = 0.0
    var _t0_prefix_cache_hit_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_prefix_cache_hit_bytes += prefix_cache_hit_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_prefix_cache_hit_bytes = perf_counter_ns()
    var _ns_prefix_cache_hit_bytes = Float64(_t1_prefix_cache_hit_bytes - _t0_prefix_cache_hit_bytes) / Float64(N)
    print("MOJO_TIMING kv_cache::prefix_cache_hit_bytes", _ns_prefix_cache_hit_bytes, _acc_prefix_cache_hit_bytes)
    var _result_prefix_cache_hit_bytes = prefix_cache_hit_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_prefix_cache_hit_bytes = _summary_float64(_result_prefix_cache_hit_bytes)
    print("MOJO_RESULT kv_cache::prefix_cache_hit_bytes", _summary_prefix_cache_hit_bytes)
    var _acc_kv_eviction_score_lru: Float64 = 0.0
    var _t0_kv_eviction_score_lru = perf_counter_ns()
    for _ in range(N):
        _acc_kv_eviction_score_lru += kv_eviction_score_lru(0.5, 0.5)
    var _t1_kv_eviction_score_lru = perf_counter_ns()
    var _ns_kv_eviction_score_lru = Float64(_t1_kv_eviction_score_lru - _t0_kv_eviction_score_lru) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_eviction_score_lru", _ns_kv_eviction_score_lru, _acc_kv_eviction_score_lru)
    var _result_kv_eviction_score_lru = kv_eviction_score_lru(0.5, 0.5)
    var _summary_kv_eviction_score_lru = _summary_float64(_result_kv_eviction_score_lru)
    print("MOJO_RESULT kv_cache::kv_eviction_score_lru", _summary_kv_eviction_score_lru)
    var _acc_kv_eviction_score_h2o: Float64 = 0.0
    var _t0_kv_eviction_score_h2o = perf_counter_ns()
    for _ in range(N):
        _acc_kv_eviction_score_h2o += kv_eviction_score_h2o(0.5, 0.5)
    var _t1_kv_eviction_score_h2o = perf_counter_ns()
    var _ns_kv_eviction_score_h2o = Float64(_t1_kv_eviction_score_h2o - _t0_kv_eviction_score_h2o) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_eviction_score_h2o", _ns_kv_eviction_score_h2o, _acc_kv_eviction_score_h2o)
    var _result_kv_eviction_score_h2o = kv_eviction_score_h2o(0.5, 0.5)
    var _summary_kv_eviction_score_h2o = _summary_float64(_result_kv_eviction_score_h2o)
    print("MOJO_RESULT kv_cache::kv_eviction_score_h2o", _summary_kv_eviction_score_h2o)
    var _acc_incremental_decode_kv_append: Float64 = 0.0
    var _t0_incremental_decode_kv_append = perf_counter_ns()
    for _ in range(N):
        _acc_incremental_decode_kv_append += incremental_decode_kv_append(0.5)
    var _t1_incremental_decode_kv_append = perf_counter_ns()
    var _ns_incremental_decode_kv_append = Float64(_t1_incremental_decode_kv_append - _t0_incremental_decode_kv_append) / Float64(N)
    print("MOJO_TIMING kv_cache::incremental_decode_kv_append", _ns_incremental_decode_kv_append, _acc_incremental_decode_kv_append)
    var _result_incremental_decode_kv_append = incremental_decode_kv_append(0.5)
    var _summary_incremental_decode_kv_append = _summary_float64(_result_incremental_decode_kv_append)
    print("MOJO_RESULT kv_cache::incremental_decode_kv_append", _summary_incremental_decode_kv_append)
    var _acc_radix_cache_shared_prefix_len: Float64 = 0.0
    var _t0_radix_cache_shared_prefix_len = perf_counter_ns()
    for _ in range(N):
        _acc_radix_cache_shared_prefix_len += radix_cache_shared_prefix_len(0.5, 0.5, 0.5)
    var _t1_radix_cache_shared_prefix_len = perf_counter_ns()
    var _ns_radix_cache_shared_prefix_len = Float64(_t1_radix_cache_shared_prefix_len - _t0_radix_cache_shared_prefix_len) / Float64(N)
    print("MOJO_TIMING kv_cache::radix_cache_shared_prefix_len", _ns_radix_cache_shared_prefix_len, _acc_radix_cache_shared_prefix_len)
    var _result_radix_cache_shared_prefix_len = radix_cache_shared_prefix_len(0.5, 0.5, 0.5)
    var _summary_radix_cache_shared_prefix_len = _summary_float64(_result_radix_cache_shared_prefix_len)
    print("MOJO_RESULT kv_cache::radix_cache_shared_prefix_len", _summary_radix_cache_shared_prefix_len)
    var _acc_kv_quantization_error: Float64 = 0.0
    var _t0_kv_quantization_error = perf_counter_ns()
    for _ in range(N):
        _acc_kv_quantization_error += kv_quantization_error(0.5, 0.5, 0.5)
    var _t1_kv_quantization_error = perf_counter_ns()
    var _ns_kv_quantization_error = Float64(_t1_kv_quantization_error - _t0_kv_quantization_error) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_quantization_error", _ns_kv_quantization_error, _acc_kv_quantization_error)
    var _result_kv_quantization_error = kv_quantization_error(0.5, 0.5, 0.5)
    var _summary_kv_quantization_error = _summary_float64(_result_kv_quantization_error)
    print("MOJO_RESULT kv_cache::kv_quantization_error", _summary_kv_quantization_error)
