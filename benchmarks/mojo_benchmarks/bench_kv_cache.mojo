"""bench_kv_cache.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from kv_cache import kv_cache_memory_per_layer, kv_cache_total_memory, kv_cache_utilization, paged_attention_block_count, prefix_cache_hit_bytes, kv_eviction_score_lru, kv_eviction_score_h2o, incremental_decode_kv_append, radix_cache_shared_prefix_len, kv_quantization_error
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

    var _acc_kv_cache_memory_per_layer: Float64 = 0.0
    var _t0_kv_cache_memory_per_layer = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_memory_per_layer += kv_cache_memory_per_layer(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_kv_cache_memory_per_layer = perf_counter_ns()
    var _ns_kv_cache_memory_per_layer = Float64(_t1_kv_cache_memory_per_layer - _t0_kv_cache_memory_per_layer) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_cache_memory_per_layer", _ns_kv_cache_memory_per_layer, _acc_kv_cache_memory_per_layer)
    var _acc_kv_cache_total_memory: Float64 = 0.0
    var _t0_kv_cache_total_memory = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_total_memory += kv_cache_total_memory(0.5, 0.5)
    var _t1_kv_cache_total_memory = perf_counter_ns()
    var _ns_kv_cache_total_memory = Float64(_t1_kv_cache_total_memory - _t0_kv_cache_total_memory) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_cache_total_memory", _ns_kv_cache_total_memory, _acc_kv_cache_total_memory)
    var _acc_kv_cache_utilization: Float64 = 0.0
    var _t0_kv_cache_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_kv_cache_utilization += kv_cache_utilization(0.5, 0.5)
    var _t1_kv_cache_utilization = perf_counter_ns()
    var _ns_kv_cache_utilization = Float64(_t1_kv_cache_utilization - _t0_kv_cache_utilization) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_cache_utilization", _ns_kv_cache_utilization, _acc_kv_cache_utilization)
    var _acc_paged_attention_block_count: Float64 = 0.0
    var _t0_paged_attention_block_count = perf_counter_ns()
    for _ in range(N):
        _acc_paged_attention_block_count += paged_attention_block_count(0.5, 0.5)
    var _t1_paged_attention_block_count = perf_counter_ns()
    var _ns_paged_attention_block_count = Float64(_t1_paged_attention_block_count - _t0_paged_attention_block_count) / Float64(N)
    print("MOJO_TIMING kv_cache::paged_attention_block_count", _ns_paged_attention_block_count, _acc_paged_attention_block_count)
    var _acc_prefix_cache_hit_bytes: Float64 = 0.0
    var _t0_prefix_cache_hit_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_prefix_cache_hit_bytes += prefix_cache_hit_bytes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_prefix_cache_hit_bytes = perf_counter_ns()
    var _ns_prefix_cache_hit_bytes = Float64(_t1_prefix_cache_hit_bytes - _t0_prefix_cache_hit_bytes) / Float64(N)
    print("MOJO_TIMING kv_cache::prefix_cache_hit_bytes", _ns_prefix_cache_hit_bytes, _acc_prefix_cache_hit_bytes)
    var _acc_kv_eviction_score_lru: Float64 = 0.0
    var _t0_kv_eviction_score_lru = perf_counter_ns()
    for _ in range(N):
        _acc_kv_eviction_score_lru += kv_eviction_score_lru(0.5, 0.5)
    var _t1_kv_eviction_score_lru = perf_counter_ns()
    var _ns_kv_eviction_score_lru = Float64(_t1_kv_eviction_score_lru - _t0_kv_eviction_score_lru) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_eviction_score_lru", _ns_kv_eviction_score_lru, _acc_kv_eviction_score_lru)
    var _acc_kv_eviction_score_h2o: Float64 = 0.0
    var _t0_kv_eviction_score_h2o = perf_counter_ns()
    for _ in range(N):
        _acc_kv_eviction_score_h2o += kv_eviction_score_h2o(0.5, 0.5)
    var _t1_kv_eviction_score_h2o = perf_counter_ns()
    var _ns_kv_eviction_score_h2o = Float64(_t1_kv_eviction_score_h2o - _t0_kv_eviction_score_h2o) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_eviction_score_h2o", _ns_kv_eviction_score_h2o, _acc_kv_eviction_score_h2o)
    var _acc_incremental_decode_kv_append: Float64 = 0.0
    var _t0_incremental_decode_kv_append = perf_counter_ns()
    for _ in range(N):
        _acc_incremental_decode_kv_append += incremental_decode_kv_append(0.5)
    var _t1_incremental_decode_kv_append = perf_counter_ns()
    var _ns_incremental_decode_kv_append = Float64(_t1_incremental_decode_kv_append - _t0_incremental_decode_kv_append) / Float64(N)
    print("MOJO_TIMING kv_cache::incremental_decode_kv_append", _ns_incremental_decode_kv_append, _acc_incremental_decode_kv_append)
    var _acc_radix_cache_shared_prefix_len: Float64 = 0.0
    var _t0_radix_cache_shared_prefix_len = perf_counter_ns()
    for _ in range(N):
        _acc_radix_cache_shared_prefix_len += radix_cache_shared_prefix_len(0.5, 0.5, 0.5)
    var _t1_radix_cache_shared_prefix_len = perf_counter_ns()
    var _ns_radix_cache_shared_prefix_len = Float64(_t1_radix_cache_shared_prefix_len - _t0_radix_cache_shared_prefix_len) / Float64(N)
    print("MOJO_TIMING kv_cache::radix_cache_shared_prefix_len", _ns_radix_cache_shared_prefix_len, _acc_radix_cache_shared_prefix_len)
    var _acc_kv_quantization_error: Float64 = 0.0
    var _t0_kv_quantization_error = perf_counter_ns()
    for _ in range(N):
        _acc_kv_quantization_error += kv_quantization_error(0.5, 0.5, 0.5)
    var _t1_kv_quantization_error = perf_counter_ns()
    var _ns_kv_quantization_error = Float64(_t1_kv_quantization_error - _t0_kv_quantization_error) / Float64(N)
    print("MOJO_TIMING kv_cache::kv_quantization_error", _ns_kv_quantization_error, _acc_kv_quantization_error)
