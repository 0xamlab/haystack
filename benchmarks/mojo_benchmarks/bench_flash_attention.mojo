"""bench_flash_attention.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from flash_attention import flash_block_max, flash_block_sum_exp, flash_block_output, flash_rescale_output, flash_final_normalize, paged_attention_block_score, sliding_window_attention, sparse_attention_block_density, grouped_query_attention_scale, ring_attention_chunk_size
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

    var _acc_flash_block_max: Float64 = 0.0
    var _t0_flash_block_max = perf_counter_ns()
    for _ in range(N):
        _acc_flash_block_max += flash_block_max(0.5, 0.5)
    var _t1_flash_block_max = perf_counter_ns()
    var _ns_flash_block_max = Float64(_t1_flash_block_max - _t0_flash_block_max) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_block_max", _ns_flash_block_max, _acc_flash_block_max)
    var _acc_flash_block_sum_exp: Float64 = 0.0
    var _t0_flash_block_sum_exp = perf_counter_ns()
    for _ in range(N):
        _acc_flash_block_sum_exp += flash_block_sum_exp(0.5, 0.5, 0.5, 0.5)
    var _t1_flash_block_sum_exp = perf_counter_ns()
    var _ns_flash_block_sum_exp = Float64(_t1_flash_block_sum_exp - _t0_flash_block_sum_exp) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_block_sum_exp", _ns_flash_block_sum_exp, _acc_flash_block_sum_exp)
    var _acc_flash_block_output: Float64 = 0.0
    var _t0_flash_block_output = perf_counter_ns()
    for _ in range(N):
        _acc_flash_block_output += flash_block_output(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_flash_block_output = perf_counter_ns()
    var _ns_flash_block_output = Float64(_t1_flash_block_output - _t0_flash_block_output) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_block_output", _ns_flash_block_output, _acc_flash_block_output)
    var _acc_flash_rescale_output: Float64 = 0.0
    var _t0_flash_rescale_output = perf_counter_ns()
    for _ in range(N):
        _acc_flash_rescale_output += flash_rescale_output(0.5, 0.5, 0.5, 0.5)
    var _t1_flash_rescale_output = perf_counter_ns()
    var _ns_flash_rescale_output = Float64(_t1_flash_rescale_output - _t0_flash_rescale_output) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_rescale_output", _ns_flash_rescale_output, _acc_flash_rescale_output)
    var _acc_flash_final_normalize: Float64 = 0.0
    var _t0_flash_final_normalize = perf_counter_ns()
    for _ in range(N):
        _acc_flash_final_normalize += flash_final_normalize(0.5, 0.5)
    var _t1_flash_final_normalize = perf_counter_ns()
    var _ns_flash_final_normalize = Float64(_t1_flash_final_normalize - _t0_flash_final_normalize) / Float64(N)
    print("MOJO_TIMING flash_attention::flash_final_normalize", _ns_flash_final_normalize, _acc_flash_final_normalize)
    var _acc_paged_attention_block_score: Float64 = 0.0
    var _t0_paged_attention_block_score = perf_counter_ns()
    for _ in range(N):
        _acc_paged_attention_block_score += paged_attention_block_score(0.5, 0.5, 0.5, 0.5)
    var _t1_paged_attention_block_score = perf_counter_ns()
    var _ns_paged_attention_block_score = Float64(_t1_paged_attention_block_score - _t0_paged_attention_block_score) / Float64(N)
    print("MOJO_TIMING flash_attention::paged_attention_block_score", _ns_paged_attention_block_score, _acc_paged_attention_block_score)
    var _acc_sliding_window_attention: Float64 = 0.0
    var _t0_sliding_window_attention = perf_counter_ns()
    for _ in range(N):
        _acc_sliding_window_attention += sliding_window_attention(0.5, 0.5, 0.5)
    var _t1_sliding_window_attention = perf_counter_ns()
    var _ns_sliding_window_attention = Float64(_t1_sliding_window_attention - _t0_sliding_window_attention) / Float64(N)
    print("MOJO_TIMING flash_attention::sliding_window_attention", _ns_sliding_window_attention, _acc_sliding_window_attention)
    var _acc_sparse_attention_block_density: Float64 = 0.0
    var _t0_sparse_attention_block_density = perf_counter_ns()
    for _ in range(N):
        _acc_sparse_attention_block_density += sparse_attention_block_density(0.5, 0.5)
    var _t1_sparse_attention_block_density = perf_counter_ns()
    var _ns_sparse_attention_block_density = Float64(_t1_sparse_attention_block_density - _t0_sparse_attention_block_density) / Float64(N)
    print("MOJO_TIMING flash_attention::sparse_attention_block_density", _ns_sparse_attention_block_density, _acc_sparse_attention_block_density)
    var _acc_grouped_query_attention_scale: Float64 = 0.0
    var _t0_grouped_query_attention_scale = perf_counter_ns()
    for _ in range(N):
        _acc_grouped_query_attention_scale += grouped_query_attention_scale(0.5, 0.5)
    var _t1_grouped_query_attention_scale = perf_counter_ns()
    var _ns_grouped_query_attention_scale = Float64(_t1_grouped_query_attention_scale - _t0_grouped_query_attention_scale) / Float64(N)
    print("MOJO_TIMING flash_attention::grouped_query_attention_scale", _ns_grouped_query_attention_scale, _acc_grouped_query_attention_scale)
    var _acc_ring_attention_chunk_size: Float64 = 0.0
    var _t0_ring_attention_chunk_size = perf_counter_ns()
    for _ in range(N):
        _acc_ring_attention_chunk_size += ring_attention_chunk_size(0.5, 0.5)
    var _t1_ring_attention_chunk_size = perf_counter_ns()
    var _ns_ring_attention_chunk_size = Float64(_t1_ring_attention_chunk_size - _t0_ring_attention_chunk_size) / Float64(N)
    print("MOJO_TIMING flash_attention::ring_attention_chunk_size", _ns_ring_attention_chunk_size, _acc_ring_attention_chunk_size)
