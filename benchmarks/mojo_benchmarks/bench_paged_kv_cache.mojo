"""bench_paged_kv_cache.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from paged_kv_cache import page_table_lookup, cache_compaction_gain, prefix_sharing_savings, speculative_branch_memory, cache_eviction_lru_score, cache_eviction_beladys_score, block_copy_cost, cache_hit_latency_saving, dynamic_ntk_rope_scale, context_extension_factor
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

    var _acc_page_table_lookup: Float64 = 0.0
    var _t0_page_table_lookup = perf_counter_ns()
    for _ in range(N):
        _acc_page_table_lookup += page_table_lookup(0.5, 0.5)
    var _t1_page_table_lookup = perf_counter_ns()
    var _ns_page_table_lookup = Float64(_t1_page_table_lookup - _t0_page_table_lookup) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::page_table_lookup", _ns_page_table_lookup, _acc_page_table_lookup)
    var _result_page_table_lookup = page_table_lookup(0.5, 0.5)
    var _summary_page_table_lookup = _summary_float64(_result_page_table_lookup)
    print("MOJO_RESULT paged_kv_cache::page_table_lookup", _summary_page_table_lookup)
    var _acc_cache_compaction_gain: Float64 = 0.0
    var _t0_cache_compaction_gain = perf_counter_ns()
    for _ in range(N):
        _acc_cache_compaction_gain += cache_compaction_gain(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cache_compaction_gain = perf_counter_ns()
    var _ns_cache_compaction_gain = Float64(_t1_cache_compaction_gain - _t0_cache_compaction_gain) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_compaction_gain", _ns_cache_compaction_gain, _acc_cache_compaction_gain)
    var _result_cache_compaction_gain = cache_compaction_gain(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_cache_compaction_gain = _summary_float64(_result_cache_compaction_gain)
    print("MOJO_RESULT paged_kv_cache::cache_compaction_gain", _summary_cache_compaction_gain)
    var _acc_prefix_sharing_savings: Float64 = 0.0
    var _t0_prefix_sharing_savings = perf_counter_ns()
    for _ in range(N):
        _acc_prefix_sharing_savings += prefix_sharing_savings(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_prefix_sharing_savings = perf_counter_ns()
    var _ns_prefix_sharing_savings = Float64(_t1_prefix_sharing_savings - _t0_prefix_sharing_savings) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::prefix_sharing_savings", _ns_prefix_sharing_savings, _acc_prefix_sharing_savings)
    var _result_prefix_sharing_savings = prefix_sharing_savings(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_prefix_sharing_savings = _summary_float64(_result_prefix_sharing_savings)
    print("MOJO_RESULT paged_kv_cache::prefix_sharing_savings", _summary_prefix_sharing_savings)
    var _acc_speculative_branch_memory: Float64 = 0.0
    var _t0_speculative_branch_memory = perf_counter_ns()
    for _ in range(N):
        _acc_speculative_branch_memory += speculative_branch_memory(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_speculative_branch_memory = perf_counter_ns()
    var _ns_speculative_branch_memory = Float64(_t1_speculative_branch_memory - _t0_speculative_branch_memory) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::speculative_branch_memory", _ns_speculative_branch_memory, _acc_speculative_branch_memory)
    var _result_speculative_branch_memory = speculative_branch_memory(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_speculative_branch_memory = _summary_float64(_result_speculative_branch_memory)
    print("MOJO_RESULT paged_kv_cache::speculative_branch_memory", _summary_speculative_branch_memory)
    var _acc_cache_eviction_lru_score: Float64 = 0.0
    var _t0_cache_eviction_lru_score = perf_counter_ns()
    for _ in range(N):
        _acc_cache_eviction_lru_score += cache_eviction_lru_score(0.5, 0.5)
    var _t1_cache_eviction_lru_score = perf_counter_ns()
    var _ns_cache_eviction_lru_score = Float64(_t1_cache_eviction_lru_score - _t0_cache_eviction_lru_score) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_eviction_lru_score", _ns_cache_eviction_lru_score, _acc_cache_eviction_lru_score)
    var _result_cache_eviction_lru_score = cache_eviction_lru_score(0.5, 0.5)
    var _summary_cache_eviction_lru_score = _summary_float64(_result_cache_eviction_lru_score)
    print("MOJO_RESULT paged_kv_cache::cache_eviction_lru_score", _summary_cache_eviction_lru_score)
    var _acc_cache_eviction_beladys_score: Float64 = 0.0
    var _t0_cache_eviction_beladys_score = perf_counter_ns()
    for _ in range(N):
        _acc_cache_eviction_beladys_score += cache_eviction_beladys_score(0.5, 0.5)
    var _t1_cache_eviction_beladys_score = perf_counter_ns()
    var _ns_cache_eviction_beladys_score = Float64(_t1_cache_eviction_beladys_score - _t0_cache_eviction_beladys_score) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_eviction_beladys_score", _ns_cache_eviction_beladys_score, _acc_cache_eviction_beladys_score)
    var _result_cache_eviction_beladys_score = cache_eviction_beladys_score(0.5, 0.5)
    var _summary_cache_eviction_beladys_score = _summary_float64(_result_cache_eviction_beladys_score)
    print("MOJO_RESULT paged_kv_cache::cache_eviction_beladys_score", _summary_cache_eviction_beladys_score)
    var _acc_block_copy_cost: Float64 = 0.0
    var _t0_block_copy_cost = perf_counter_ns()
    for _ in range(N):
        _acc_block_copy_cost += block_copy_cost(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_block_copy_cost = perf_counter_ns()
    var _ns_block_copy_cost = Float64(_t1_block_copy_cost - _t0_block_copy_cost) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::block_copy_cost", _ns_block_copy_cost, _acc_block_copy_cost)
    var _result_block_copy_cost = block_copy_cost(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_block_copy_cost = _summary_float64(_result_block_copy_cost)
    print("MOJO_RESULT paged_kv_cache::block_copy_cost", _summary_block_copy_cost)
    var _acc_cache_hit_latency_saving: Float64 = 0.0
    var _t0_cache_hit_latency_saving = perf_counter_ns()
    for _ in range(N):
        _acc_cache_hit_latency_saving += cache_hit_latency_saving(0.5, 0.5)
    var _t1_cache_hit_latency_saving = perf_counter_ns()
    var _ns_cache_hit_latency_saving = Float64(_t1_cache_hit_latency_saving - _t0_cache_hit_latency_saving) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::cache_hit_latency_saving", _ns_cache_hit_latency_saving, _acc_cache_hit_latency_saving)
    var _result_cache_hit_latency_saving = cache_hit_latency_saving(0.5, 0.5)
    var _summary_cache_hit_latency_saving = _summary_float64(_result_cache_hit_latency_saving)
    print("MOJO_RESULT paged_kv_cache::cache_hit_latency_saving", _summary_cache_hit_latency_saving)
    var _acc_dynamic_ntk_rope_scale: Float64 = 0.0
    var _t0_dynamic_ntk_rope_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dynamic_ntk_rope_scale += dynamic_ntk_rope_scale(0.5, 0.5, 0.5)
    var _t1_dynamic_ntk_rope_scale = perf_counter_ns()
    var _ns_dynamic_ntk_rope_scale = Float64(_t1_dynamic_ntk_rope_scale - _t0_dynamic_ntk_rope_scale) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::dynamic_ntk_rope_scale", _ns_dynamic_ntk_rope_scale, _acc_dynamic_ntk_rope_scale)
    var _result_dynamic_ntk_rope_scale = dynamic_ntk_rope_scale(0.5, 0.5, 0.5)
    var _summary_dynamic_ntk_rope_scale = _summary_float64(_result_dynamic_ntk_rope_scale)
    print("MOJO_RESULT paged_kv_cache::dynamic_ntk_rope_scale", _summary_dynamic_ntk_rope_scale)
    var _acc_context_extension_factor: Float64 = 0.0
    var _t0_context_extension_factor = perf_counter_ns()
    for _ in range(N):
        _acc_context_extension_factor += context_extension_factor(0.5, 0.5)
    var _t1_context_extension_factor = perf_counter_ns()
    var _ns_context_extension_factor = Float64(_t1_context_extension_factor - _t0_context_extension_factor) / Float64(N)
    print("MOJO_TIMING paged_kv_cache::context_extension_factor", _ns_context_extension_factor, _acc_context_extension_factor)
    var _result_context_extension_factor = context_extension_factor(0.5, 0.5)
    var _summary_context_extension_factor = _summary_float64(_result_context_extension_factor)
    print("MOJO_RESULT paged_kv_cache::context_extension_factor", _summary_context_extension_factor)
