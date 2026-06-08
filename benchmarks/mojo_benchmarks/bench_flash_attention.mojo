"""bench_flash_attention.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from flash_attention import flash_block_max, flash_block_sum_exp, flash_block_output, flash_rescale_output, flash_final_normalize, paged_attention_block_score, sliding_window_attention, sparse_attention_block_density, grouped_query_attention_scale, ring_attention_chunk_size
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

    var _acc_flash_block_max: Float64 = 0.0
    var _t0_flash_block_max = perf_counter_ns()
    for _ in range(N):
        _acc_flash_block_max += flash_block_max(0.5, 0.5)
    var _t1_flash_block_max = perf_counter_ns()
    var _ns_flash_block_max = Float64(_t1_flash_block_max - _t0_flash_block_max) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_block_max", _ns_flash_block_max, _acc_flash_block_max)
    var _result_flash_block_max = flash_block_max(0.5, 0.5)
    var _summary_flash_block_max = _summary_float64(_result_flash_block_max)
    print("MOJO_RESULT flash_attention::flash_block_max", _summary_flash_block_max)
    var _acc_flash_block_sum_exp: Float64 = 0.0
    var _t0_flash_block_sum_exp = perf_counter_ns()
    for _ in range(N):
        _acc_flash_block_sum_exp += flash_block_sum_exp(0.5, 0.5, 0.5, 0.5)
    var _t1_flash_block_sum_exp = perf_counter_ns()
    var _ns_flash_block_sum_exp = Float64(_t1_flash_block_sum_exp - _t0_flash_block_sum_exp) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_block_sum_exp", _ns_flash_block_sum_exp, _acc_flash_block_sum_exp)
    var _result_flash_block_sum_exp = flash_block_sum_exp(0.5, 0.5, 0.5, 0.5)
    var _summary_flash_block_sum_exp = _summary_float64(_result_flash_block_sum_exp)
    print("MOJO_RESULT flash_attention::flash_block_sum_exp", _summary_flash_block_sum_exp)
    var _acc_flash_block_output: Float64 = 0.0
    var _t0_flash_block_output = perf_counter_ns()
    for _ in range(N):
        _acc_flash_block_output += flash_block_output(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_flash_block_output = perf_counter_ns()
    var _ns_flash_block_output = Float64(_t1_flash_block_output - _t0_flash_block_output) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_block_output", _ns_flash_block_output, _acc_flash_block_output)
    var _result_flash_block_output = flash_block_output(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_flash_block_output = _summary_float64(_result_flash_block_output)
    print("MOJO_RESULT flash_attention::flash_block_output", _summary_flash_block_output)
    var _acc_flash_rescale_output: Float64 = 0.0
    var _t0_flash_rescale_output = perf_counter_ns()
    for _ in range(N):
        _acc_flash_rescale_output += flash_rescale_output(0.5, 0.5, 0.5, 0.5)
    var _t1_flash_rescale_output = perf_counter_ns()
    var _ns_flash_rescale_output = Float64(_t1_flash_rescale_output - _t0_flash_rescale_output) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_rescale_output", _ns_flash_rescale_output, _acc_flash_rescale_output)
    var _result_flash_rescale_output = flash_rescale_output(0.5, 0.5, 0.5, 0.5)
    var _summary_flash_rescale_output = _summary_float64(_result_flash_rescale_output)
    print("MOJO_RESULT flash_attention::flash_rescale_output", _summary_flash_rescale_output)
    var _acc_flash_final_normalize: Float64 = 0.0
    var _t0_flash_final_normalize = perf_counter_ns()
    for _ in range(N):
        _acc_flash_final_normalize += flash_final_normalize(0.5, 0.5)
    var _t1_flash_final_normalize = perf_counter_ns()
    var _ns_flash_final_normalize = Float64(_t1_flash_final_normalize - _t0_flash_final_normalize) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_final_normalize", _ns_flash_final_normalize, _acc_flash_final_normalize)
    var _result_flash_final_normalize = flash_final_normalize(0.5, 0.5)
    var _summary_flash_final_normalize = _summary_float64(_result_flash_final_normalize)
    print("MOJO_RESULT flash_attention::flash_final_normalize", _summary_flash_final_normalize)
    var _acc_paged_attention_block_score: Float64 = 0.0
    var _t0_paged_attention_block_score = perf_counter_ns()
    for _ in range(N):
        _acc_paged_attention_block_score += paged_attention_block_score(0.5, 0.5, 0.5, 0.5)
    var _t1_paged_attention_block_score = perf_counter_ns()
    var _ns_paged_attention_block_score = Float64(_t1_paged_attention_block_score - _t0_paged_attention_block_score) / Float64(N)
    print("MOJO_TIMING flash_attention::paged_attention_block_score", _ns_paged_attention_block_score, _acc_paged_attention_block_score)
    var _result_paged_attention_block_score = paged_attention_block_score(0.5, 0.5, 0.5, 0.5)
    var _summary_paged_attention_block_score = _summary_float64(_result_paged_attention_block_score)
    print("MOJO_RESULT flash_attention::paged_attention_block_score", _summary_paged_attention_block_score)
    var _acc_sliding_window_attention: Float64 = 0.0
    var _t0_sliding_window_attention = perf_counter_ns()
    for _ in range(N):
        _acc_sliding_window_attention += sliding_window_attention(0.5, 0.5, 0.5)
    var _t1_sliding_window_attention = perf_counter_ns()
    var _ns_sliding_window_attention = Float64(_t1_sliding_window_attention - _t0_sliding_window_attention) / Float64(N)
    print("MOJO_TIMING flash_attention::sliding_window_attention", _ns_sliding_window_attention, _acc_sliding_window_attention)
    var _result_sliding_window_attention = sliding_window_attention(0.5, 0.5, 0.5)
    var _summary_sliding_window_attention = _summary_float64(_result_sliding_window_attention)
    print("MOJO_RESULT flash_attention::sliding_window_attention", _summary_sliding_window_attention)
    var _acc_sparse_attention_block_density: Float64 = 0.0
    var _t0_sparse_attention_block_density = perf_counter_ns()
    for _ in range(N):
        _acc_sparse_attention_block_density += sparse_attention_block_density(0.5, 0.5)
    var _t1_sparse_attention_block_density = perf_counter_ns()
    var _ns_sparse_attention_block_density = Float64(_t1_sparse_attention_block_density - _t0_sparse_attention_block_density) / Float64(N)
    print("MOJO_TIMING flash_attention::sparse_attention_block_density", _ns_sparse_attention_block_density, _acc_sparse_attention_block_density)
    var _result_sparse_attention_block_density = sparse_attention_block_density(0.5, 0.5)
    var _summary_sparse_attention_block_density = _summary_float64(_result_sparse_attention_block_density)
    print("MOJO_RESULT flash_attention::sparse_attention_block_density", _summary_sparse_attention_block_density)
    var _acc_grouped_query_attention_scale: Float64 = 0.0
    var _t0_grouped_query_attention_scale = perf_counter_ns()
    for _ in range(N):
        _acc_grouped_query_attention_scale += grouped_query_attention_scale(0.5, 0.5)
    var _t1_grouped_query_attention_scale = perf_counter_ns()
    var _ns_grouped_query_attention_scale = Float64(_t1_grouped_query_attention_scale - _t0_grouped_query_attention_scale) / Float64(N)
    print("MOJO_TIMING flash_attention::grouped_query_attention_scale", _ns_grouped_query_attention_scale, _acc_grouped_query_attention_scale)
    var _result_grouped_query_attention_scale = grouped_query_attention_scale(0.5, 0.5)
    var _summary_grouped_query_attention_scale = _summary_float64(_result_grouped_query_attention_scale)
    print("MOJO_RESULT flash_attention::grouped_query_attention_scale", _summary_grouped_query_attention_scale)
    var _acc_ring_attention_chunk_size: Float64 = 0.0
    var _t0_ring_attention_chunk_size = perf_counter_ns()
    for _ in range(N):
        _acc_ring_attention_chunk_size += ring_attention_chunk_size(0.5, 0.5)
    var _t1_ring_attention_chunk_size = perf_counter_ns()
    var _ns_ring_attention_chunk_size = Float64(_t1_ring_attention_chunk_size - _t0_ring_attention_chunk_size) / Float64(N)
    print("MOJO_TIMING flash_attention::ring_attention_chunk_size", _ns_ring_attention_chunk_size, _acc_ring_attention_chunk_size)
    var _result_ring_attention_chunk_size = ring_attention_chunk_size(0.5, 0.5)
    var _summary_ring_attention_chunk_size = _summary_float64(_result_ring_attention_chunk_size)
    print("MOJO_RESULT flash_attention::ring_attention_chunk_size", _summary_ring_attention_chunk_size)
