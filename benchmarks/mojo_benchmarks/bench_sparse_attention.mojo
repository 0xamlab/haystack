"""bench_sparse_attention.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sparse_attention import local_window_mask, longformer_global_score, bigbird_random_block_select, streaming_llm_sink_score, landmark_token_score, chunk_cross_attention_weight, linear_attention_kernel, recurrent_memory_update, block_sparse_density, hyper_attention_estimate
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

    var _acc_local_window_mask: Float64 = 0.0
    var _t0_local_window_mask = perf_counter_ns()
    for _ in range(N):
        _acc_local_window_mask += local_window_mask(0.5, 0.5, 0.5, 0.5)
    var _t1_local_window_mask = perf_counter_ns()
    var _ns_local_window_mask = Float64(_t1_local_window_mask - _t0_local_window_mask) / Float64(N)
    print("MOJO_TIMING sparse_attention::local_window_mask", _ns_local_window_mask, _acc_local_window_mask)
    var _acc_longformer_global_score: Float64 = 0.0
    var _t0_longformer_global_score = perf_counter_ns()
    for _ in range(N):
        _acc_longformer_global_score += longformer_global_score(0.5, 0.5, 0.5, 0.5)
    var _t1_longformer_global_score = perf_counter_ns()
    var _ns_longformer_global_score = Float64(_t1_longformer_global_score - _t0_longformer_global_score) / Float64(N)
    print("MOJO_TIMING sparse_attention::longformer_global_score", _ns_longformer_global_score, _acc_longformer_global_score)
    var _acc_bigbird_random_block_select: Float64 = 0.0
    var _t0_bigbird_random_block_select = perf_counter_ns()
    for _ in range(N):
        _acc_bigbird_random_block_select += bigbird_random_block_select(0.5, 0.5, 0.5, 0.5)
    var _t1_bigbird_random_block_select = perf_counter_ns()
    var _ns_bigbird_random_block_select = Float64(_t1_bigbird_random_block_select - _t0_bigbird_random_block_select) / Float64(N)
    print("MOJO_TIMING sparse_attention::bigbird_random_block_select", _ns_bigbird_random_block_select, _acc_bigbird_random_block_select)
    var _acc_streaming_llm_sink_score: Float64 = 0.0
    var _t0_streaming_llm_sink_score = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_llm_sink_score += streaming_llm_sink_score(0.5, 0.5, 0.5, 0.5)
    var _t1_streaming_llm_sink_score = perf_counter_ns()
    var _ns_streaming_llm_sink_score = Float64(_t1_streaming_llm_sink_score - _t0_streaming_llm_sink_score) / Float64(N)
    print("MOJO_TIMING sparse_attention::streaming_llm_sink_score", _ns_streaming_llm_sink_score, _acc_streaming_llm_sink_score)
    var _acc_landmark_token_score: Float64 = 0.0
    var _t0_landmark_token_score = perf_counter_ns()
    for _ in range(N):
        _acc_landmark_token_score += landmark_token_score(0.5, 0.5, 0.5)
    var _t1_landmark_token_score = perf_counter_ns()
    var _ns_landmark_token_score = Float64(_t1_landmark_token_score - _t0_landmark_token_score) / Float64(N)
    print("MOJO_TIMING sparse_attention::landmark_token_score", _ns_landmark_token_score, _acc_landmark_token_score)
    var _acc_chunk_cross_attention_weight: Float64 = 0.0
    var _t0_chunk_cross_attention_weight = perf_counter_ns()
    for _ in range(N):
        _acc_chunk_cross_attention_weight += chunk_cross_attention_weight(0.5, 0.5, 0.5, 0.5)
    var _t1_chunk_cross_attention_weight = perf_counter_ns()
    var _ns_chunk_cross_attention_weight = Float64(_t1_chunk_cross_attention_weight - _t0_chunk_cross_attention_weight) / Float64(N)
    print("MOJO_TIMING sparse_attention::chunk_cross_attention_weight", _ns_chunk_cross_attention_weight, _acc_chunk_cross_attention_weight)
    var _acc_linear_attention_kernel: Float64 = 0.0
    var _t0_linear_attention_kernel = perf_counter_ns()
    for _ in range(N):
        _acc_linear_attention_kernel += linear_attention_kernel(0.5)
    var _t1_linear_attention_kernel = perf_counter_ns()
    var _ns_linear_attention_kernel = Float64(_t1_linear_attention_kernel - _t0_linear_attention_kernel) / Float64(N)
    print("MOJO_TIMING sparse_attention::linear_attention_kernel", _ns_linear_attention_kernel, _acc_linear_attention_kernel)
    var _acc_recurrent_memory_update: Float64 = 0.0
    var _t0_recurrent_memory_update = perf_counter_ns()
    for _ in range(N):
        _acc_recurrent_memory_update += recurrent_memory_update(0.5, 0.5, 0.5, 0.5)
    var _t1_recurrent_memory_update = perf_counter_ns()
    var _ns_recurrent_memory_update = Float64(_t1_recurrent_memory_update - _t0_recurrent_memory_update) / Float64(N)
    print("MOJO_TIMING sparse_attention::recurrent_memory_update", _ns_recurrent_memory_update, _acc_recurrent_memory_update)
    var _acc_block_sparse_density: Float64 = 0.0
    var _t0_block_sparse_density = perf_counter_ns()
    for _ in range(N):
        _acc_block_sparse_density += block_sparse_density(0.5, 0.5)
    var _t1_block_sparse_density = perf_counter_ns()
    var _ns_block_sparse_density = Float64(_t1_block_sparse_density - _t0_block_sparse_density) / Float64(N)
    print("MOJO_TIMING sparse_attention::block_sparse_density", _ns_block_sparse_density, _acc_block_sparse_density)
    var _acc_hyper_attention_estimate: Float64 = 0.0
    var _t0_hyper_attention_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_hyper_attention_estimate += hyper_attention_estimate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_hyper_attention_estimate = perf_counter_ns()
    var _ns_hyper_attention_estimate = Float64(_t1_hyper_attention_estimate - _t0_hyper_attention_estimate) / Float64(N)
    print("MOJO_TIMING sparse_attention::hyper_attention_estimate", _ns_hyper_attention_estimate, _acc_hyper_attention_estimate)
