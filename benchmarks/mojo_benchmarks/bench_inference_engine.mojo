"""bench_inference_engine.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from inference_engine import batch_padding_mask, dynamic_batching_priority, kv_cache_hit_ratio, latency_percentile_estimate, throughput_tokens_per_sec, speculative_decode_accept_rate, continuous_batching_capacity, quantized_inference_speedup, prefill_time_estimate, decode_time_per_token
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

fn _summary_list_float64_rounded6(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64_rounded6(value[i])
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

    var _acc_batch_padding_mask: Float64 = 0.0
    var _t0_batch_padding_mask = perf_counter_ns()
    for _ in range(N):
        _acc_batch_padding_mask += batch_padding_mask(0.5, 0.5)
    var _t1_batch_padding_mask = perf_counter_ns()
    var _ns_batch_padding_mask = Float64(_t1_batch_padding_mask - _t0_batch_padding_mask) / Float64(N)
    print("MOJO_TIMING inference_engine::batch_padding_mask", _ns_batch_padding_mask, _acc_batch_padding_mask)
    var _result_batch_padding_mask = batch_padding_mask(0.5, 0.5)
    var _summary_batch_padding_mask = _summary_float64(_result_batch_padding_mask)
    print("MOJO_RESULT inference_engine::batch_padding_mask", _summary_batch_padding_mask)
    var _acc_dynamic_batching_priority: Float64 = 0.0
    var _t0_dynamic_batching_priority = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_batching_priority += dynamic_batching_priority(0.5, 0.5, 0.5)
    var _t1_dynamic_batching_priority = perf_counter_ns()
    var _ns_dynamic_batching_priority = Float64(_t1_dynamic_batching_priority - _t0_dynamic_batching_priority) / Float64(N)
    print("MOJO_TIMING inference_engine::dynamic_batching_priority", _ns_dynamic_batching_priority, _acc_dynamic_batching_priority)
    var _result_dynamic_batching_priority = dynamic_batching_priority(0.5, 0.5, 0.5)
    var _summary_dynamic_batching_priority = _summary_float64(_result_dynamic_batching_priority)
    print("MOJO_RESULT inference_engine::dynamic_batching_priority", _summary_dynamic_batching_priority)
    var _acc_kv_cache_hit_ratio: Float64 = 0.0
    var _t0_kv_cache_hit_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_hit_ratio += kv_cache_hit_ratio(0.5, 0.5)
    var _t1_kv_cache_hit_ratio = perf_counter_ns()
    var _ns_kv_cache_hit_ratio = Float64(_t1_kv_cache_hit_ratio - _t0_kv_cache_hit_ratio) / Float64(N)
    print("MOJO_TIMING inference_engine::kv_cache_hit_ratio", _ns_kv_cache_hit_ratio, _acc_kv_cache_hit_ratio)
    var _result_kv_cache_hit_ratio = kv_cache_hit_ratio(0.5, 0.5)
    var _summary_kv_cache_hit_ratio = _summary_float64(_result_kv_cache_hit_ratio)
    print("MOJO_RESULT inference_engine::kv_cache_hit_ratio", _summary_kv_cache_hit_ratio)
    var _acc_latency_percentile_estimate: Float64 = 0.0
    var _t0_latency_percentile_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_latency_percentile_estimate += latency_percentile_estimate(0.5, 0.5, 0.5)
    var _t1_latency_percentile_estimate = perf_counter_ns()
    var _ns_latency_percentile_estimate = Float64(_t1_latency_percentile_estimate - _t0_latency_percentile_estimate) / Float64(N)
    print("MOJO_TIMING inference_engine::latency_percentile_estimate", _ns_latency_percentile_estimate, _acc_latency_percentile_estimate)
    var _result_latency_percentile_estimate = latency_percentile_estimate(0.5, 0.5, 0.5)
    var _summary_latency_percentile_estimate = _summary_float64(_result_latency_percentile_estimate)
    print("MOJO_RESULT inference_engine::latency_percentile_estimate", _summary_latency_percentile_estimate)
    var _acc_throughput_tokens_per_sec: Float64 = 0.0
    var _t0_throughput_tokens_per_sec = perf_counter_ns()
    for _ in range(N):
        _acc_throughput_tokens_per_sec += throughput_tokens_per_sec(0.5, 0.5, 0.5)
    var _t1_throughput_tokens_per_sec = perf_counter_ns()
    var _ns_throughput_tokens_per_sec = Float64(_t1_throughput_tokens_per_sec - _t0_throughput_tokens_per_sec) / Float64(N)
    print("MOJO_TIMING inference_engine::throughput_tokens_per_sec", _ns_throughput_tokens_per_sec, _acc_throughput_tokens_per_sec)
    var _result_throughput_tokens_per_sec = throughput_tokens_per_sec(0.5, 0.5, 0.5)
    var _summary_throughput_tokens_per_sec = _summary_float64(_result_throughput_tokens_per_sec)
    print("MOJO_RESULT inference_engine::throughput_tokens_per_sec", _summary_throughput_tokens_per_sec)
    var _acc_speculative_decode_accept_rate: Float64 = 0.0
    var _t0_speculative_decode_accept_rate = perf_counter_ns()
    for _ in range(N):
        _acc_speculative_decode_accept_rate += speculative_decode_accept_rate(0.5, 0.5)
    var _t1_speculative_decode_accept_rate = perf_counter_ns()
    var _ns_speculative_decode_accept_rate = Float64(_t1_speculative_decode_accept_rate - _t0_speculative_decode_accept_rate) / Float64(N)
    print("MOJO_TIMING inference_engine::speculative_decode_accept_rate", _ns_speculative_decode_accept_rate, _acc_speculative_decode_accept_rate)
    var _result_speculative_decode_accept_rate = speculative_decode_accept_rate(0.5, 0.5)
    var _summary_speculative_decode_accept_rate = _summary_float64(_result_speculative_decode_accept_rate)
    print("MOJO_RESULT inference_engine::speculative_decode_accept_rate", _summary_speculative_decode_accept_rate)
    var _acc_continuous_batching_capacity: Float64 = 0.0
    var _t0_continuous_batching_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_continuous_batching_capacity += continuous_batching_capacity(0.5, 0.5, 0.5)
    var _t1_continuous_batching_capacity = perf_counter_ns()
    var _ns_continuous_batching_capacity = Float64(_t1_continuous_batching_capacity - _t0_continuous_batching_capacity) / Float64(N)
    print("MOJO_TIMING inference_engine::continuous_batching_capacity", _ns_continuous_batching_capacity, _acc_continuous_batching_capacity)
    var _result_continuous_batching_capacity = continuous_batching_capacity(0.5, 0.5, 0.5)
    var _summary_continuous_batching_capacity = _summary_float64(_result_continuous_batching_capacity)
    print("MOJO_RESULT inference_engine::continuous_batching_capacity", _summary_continuous_batching_capacity)
    var _acc_quantized_inference_speedup: Float64 = 0.0
    var _t0_quantized_inference_speedup = perf_counter_ns()
    for _ in range(N):
        _acc_quantized_inference_speedup += quantized_inference_speedup(0.5, 0.5, 0.5)
    var _t1_quantized_inference_speedup = perf_counter_ns()
    var _ns_quantized_inference_speedup = Float64(_t1_quantized_inference_speedup - _t0_quantized_inference_speedup) / Float64(N)
    print("MOJO_TIMING inference_engine::quantized_inference_speedup", _ns_quantized_inference_speedup, _acc_quantized_inference_speedup)
    var _result_quantized_inference_speedup = quantized_inference_speedup(0.5, 0.5, 0.5)
    var _summary_quantized_inference_speedup = _summary_float64(_result_quantized_inference_speedup)
    print("MOJO_RESULT inference_engine::quantized_inference_speedup", _summary_quantized_inference_speedup)
    var _acc_prefill_time_estimate: Float64 = 0.0
    var _t0_prefill_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_prefill_time_estimate += prefill_time_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_prefill_time_estimate = perf_counter_ns()
    var _ns_prefill_time_estimate = Float64(_t1_prefill_time_estimate - _t0_prefill_time_estimate) / Float64(N)
    print("MOJO_TIMING inference_engine::prefill_time_estimate", _ns_prefill_time_estimate, _acc_prefill_time_estimate)
    var _result_prefill_time_estimate = prefill_time_estimate(0.5, 0.5, 0.5, 0.5)
    var _summary_prefill_time_estimate = _summary_float64(_result_prefill_time_estimate)
    print("MOJO_RESULT inference_engine::prefill_time_estimate", _summary_prefill_time_estimate)
    var _acc_decode_time_per_token: Float64 = 0.0
    var _t0_decode_time_per_token = perf_counter_ns()
    for _ in range(N):
        _acc_decode_time_per_token += decode_time_per_token(0.5, 0.5, 0.5)
    var _t1_decode_time_per_token = perf_counter_ns()
    var _ns_decode_time_per_token = Float64(_t1_decode_time_per_token - _t0_decode_time_per_token) / Float64(N)
    print("MOJO_TIMING inference_engine::decode_time_per_token", _ns_decode_time_per_token, _acc_decode_time_per_token)
    var _result_decode_time_per_token = decode_time_per_token(0.5, 0.5, 0.5)
    var _summary_decode_time_per_token = _summary_float64(_result_decode_time_per_token)
    print("MOJO_RESULT inference_engine::decode_time_per_token", _summary_decode_time_per_token)
