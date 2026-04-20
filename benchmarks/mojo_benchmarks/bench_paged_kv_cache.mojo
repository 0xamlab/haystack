"""bench_paged_kv_cache.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from paged_kv_cache import page_table_lookup, cache_compaction_gain, prefix_sharing_savings, speculative_branch_memory, cache_eviction_lru_score, cache_eviction_beladys_score, block_copy_cost, cache_hit_latency_saving, dynamic_ntk_rope_scale, context_extension_factor
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

    var _acc_page_table_lookup: Float64 = 0.0
    var _t0_page_table_lookup = perf_counter_ns()
    for _ in range(N):
        _acc_page_table_lookup += page_table_lookup(0.5, 0.5)
    var _t1_page_table_lookup = perf_counter_ns()
    var _ns_page_table_lookup = Float64(_t1_page_table_lookup - _t0_page_table_lookup) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::page_table_lookup", _ns_page_table_lookup, _acc_page_table_lookup)
    var _acc_cache_compaction_gain: Float64 = 0.0
    var _t0_cache_compaction_gain = perf_counter_ns()
    for _ in range(N):
        _acc_cache_compaction_gain += cache_compaction_gain(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cache_compaction_gain = perf_counter_ns()
    var _ns_cache_compaction_gain = Float64(_t1_cache_compaction_gain - _t0_cache_compaction_gain) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_compaction_gain", _ns_cache_compaction_gain, _acc_cache_compaction_gain)
    var _acc_prefix_sharing_savings: Float64 = 0.0
    var _t0_prefix_sharing_savings = perf_counter_ns()
    for _ in range(N):
        _acc_prefix_sharing_savings += prefix_sharing_savings(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_prefix_sharing_savings = perf_counter_ns()
    var _ns_prefix_sharing_savings = Float64(_t1_prefix_sharing_savings - _t0_prefix_sharing_savings) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::prefix_sharing_savings", _ns_prefix_sharing_savings, _acc_prefix_sharing_savings)
    var _acc_speculative_branch_memory: Float64 = 0.0
    var _t0_speculative_branch_memory = perf_counter_ns()
    for _ in range(N):
        _acc_speculative_branch_memory += speculative_branch_memory(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_speculative_branch_memory = perf_counter_ns()
    var _ns_speculative_branch_memory = Float64(_t1_speculative_branch_memory - _t0_speculative_branch_memory) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::speculative_branch_memory", _ns_speculative_branch_memory, _acc_speculative_branch_memory)
    var _acc_cache_eviction_lru_score: Float64 = 0.0
    var _t0_cache_eviction_lru_score = perf_counter_ns()
    for _ in range(N):
        _acc_cache_eviction_lru_score += cache_eviction_lru_score(0.5, 0.5)
    var _t1_cache_eviction_lru_score = perf_counter_ns()
    var _ns_cache_eviction_lru_score = Float64(_t1_cache_eviction_lru_score - _t0_cache_eviction_lru_score) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_eviction_lru_score", _ns_cache_eviction_lru_score, _acc_cache_eviction_lru_score)
    var _acc_cache_eviction_beladys_score: Float64 = 0.0
    var _t0_cache_eviction_beladys_score = perf_counter_ns()
    for _ in range(N):
        _acc_cache_eviction_beladys_score += cache_eviction_beladys_score(0.5, 0.5)
    var _t1_cache_eviction_beladys_score = perf_counter_ns()
    var _ns_cache_eviction_beladys_score = Float64(_t1_cache_eviction_beladys_score - _t0_cache_eviction_beladys_score) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_eviction_beladys_score", _ns_cache_eviction_beladys_score, _acc_cache_eviction_beladys_score)
    var _acc_block_copy_cost: Float64 = 0.0
    var _t0_block_copy_cost = perf_counter_ns()
    for _ in range(N):
        _acc_block_copy_cost += block_copy_cost(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_block_copy_cost = perf_counter_ns()
    var _ns_block_copy_cost = Float64(_t1_block_copy_cost - _t0_block_copy_cost) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::block_copy_cost", _ns_block_copy_cost, _acc_block_copy_cost)
    var _acc_cache_hit_latency_saving: Float64 = 0.0
    var _t0_cache_hit_latency_saving = perf_counter_ns()
    for _ in range(N):
        _acc_cache_hit_latency_saving += cache_hit_latency_saving(0.5, 0.5)
    var _t1_cache_hit_latency_saving = perf_counter_ns()
    var _ns_cache_hit_latency_saving = Float64(_t1_cache_hit_latency_saving - _t0_cache_hit_latency_saving) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_hit_latency_saving", _ns_cache_hit_latency_saving, _acc_cache_hit_latency_saving)
    var _acc_dynamic_ntk_rope_scale: Float64 = 0.0
    var _t0_dynamic_ntk_rope_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_ntk_rope_scale += dynamic_ntk_rope_scale(0.5, 0.5, 0.5)
    var _t1_dynamic_ntk_rope_scale = perf_counter_ns()
    var _ns_dynamic_ntk_rope_scale = Float64(_t1_dynamic_ntk_rope_scale - _t0_dynamic_ntk_rope_scale) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::dynamic_ntk_rope_scale", _ns_dynamic_ntk_rope_scale, _acc_dynamic_ntk_rope_scale)
    var _acc_context_extension_factor: Float64 = 0.0
    var _t0_context_extension_factor = perf_counter_ns()
    for _ in range(N):
        _acc_context_extension_factor += context_extension_factor(0.5, 0.5)
    var _t1_context_extension_factor = perf_counter_ns()
    var _ns_context_extension_factor = Float64(_t1_context_extension_factor - _t0_context_extension_factor) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::context_extension_factor", _ns_context_extension_factor, _acc_context_extension_factor)
