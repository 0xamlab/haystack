"""bench_weight_loader.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from weight_loader import shard_offset_bytes, safetensors_header_size, lazy_load_priority, gguf_quantized_block_size, checkpoint_resume_step, weight_diff_norm, partial_load_coverage, adapter_merge_ratio, hf_model_index_shards, weight_hash_verify
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

    var _acc_shard_offset_bytes: Float64 = 0.0
    var _t0_shard_offset_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_shard_offset_bytes += shard_offset_bytes(0.5, 0.5, 0.5)
    var _t1_shard_offset_bytes = perf_counter_ns()
    var _ns_shard_offset_bytes = Float64(_t1_shard_offset_bytes - _t0_shard_offset_bytes) / Float64(N)
    print("MOJO_TIMING weight_loader::shard_offset_bytes", _ns_shard_offset_bytes, _acc_shard_offset_bytes)
    var _acc_safetensors_header_size: Float64 = 0.0
    var _t0_safetensors_header_size = perf_counter_ns()
    for _ in range(N):
        _acc_safetensors_header_size += safetensors_header_size(0.5, 0.5)
    var _t1_safetensors_header_size = perf_counter_ns()
    var _ns_safetensors_header_size = Float64(_t1_safetensors_header_size - _t0_safetensors_header_size) / Float64(N)
    print("MOJO_TIMING weight_loader::safetensors_header_size", _ns_safetensors_header_size, _acc_safetensors_header_size)
    var _acc_lazy_load_priority: Float64 = 0.0
    var _t0_lazy_load_priority = perf_counter_ns()
    for _ in range(N):
        _acc_lazy_load_priority += lazy_load_priority(0.5, 0.5, 0.5)
    var _t1_lazy_load_priority = perf_counter_ns()
    var _ns_lazy_load_priority = Float64(_t1_lazy_load_priority - _t0_lazy_load_priority) / Float64(N)
    print("MOJO_TIMING weight_loader::lazy_load_priority", _ns_lazy_load_priority, _acc_lazy_load_priority)
    var _acc_gguf_quantized_block_size: Float64 = 0.0
    var _t0_gguf_quantized_block_size = perf_counter_ns()
    for _ in range(N):
        _acc_gguf_quantized_block_size += gguf_quantized_block_size(0.5, 0.5)
    var _t1_gguf_quantized_block_size = perf_counter_ns()
    var _ns_gguf_quantized_block_size = Float64(_t1_gguf_quantized_block_size - _t0_gguf_quantized_block_size) / Float64(N)
    print("MOJO_TIMING weight_loader::gguf_quantized_block_size", _ns_gguf_quantized_block_size, _acc_gguf_quantized_block_size)
    var _acc_checkpoint_resume_step: Float64 = 0.0
    var _t0_checkpoint_resume_step = perf_counter_ns()
    for _ in range(N):
        _acc_checkpoint_resume_step += checkpoint_resume_step(0.5, 0.5)
    var _t1_checkpoint_resume_step = perf_counter_ns()
    var _ns_checkpoint_resume_step = Float64(_t1_checkpoint_resume_step - _t0_checkpoint_resume_step) / Float64(N)
    print("MOJO_TIMING weight_loader::checkpoint_resume_step", _ns_checkpoint_resume_step, _acc_checkpoint_resume_step)
    var _acc_weight_diff_norm: Float64 = 0.0
    var _t0_weight_diff_norm = perf_counter_ns()
    for _ in range(N):
        _acc_weight_diff_norm += weight_diff_norm(0.5, 0.5)
    var _t1_weight_diff_norm = perf_counter_ns()
    var _ns_weight_diff_norm = Float64(_t1_weight_diff_norm - _t0_weight_diff_norm) / Float64(N)
    print("MOJO_TIMING weight_loader::weight_diff_norm", _ns_weight_diff_norm, _acc_weight_diff_norm)
    var _acc_partial_load_coverage: Float64 = 0.0
    var _t0_partial_load_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_partial_load_coverage += partial_load_coverage(0.5, 0.5)
    var _t1_partial_load_coverage = perf_counter_ns()
    var _ns_partial_load_coverage = Float64(_t1_partial_load_coverage - _t0_partial_load_coverage) / Float64(N)
    print("MOJO_TIMING weight_loader::partial_load_coverage", _ns_partial_load_coverage, _acc_partial_load_coverage)
    var _acc_adapter_merge_ratio: Float64 = 0.0
    var _t0_adapter_merge_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_adapter_merge_ratio += adapter_merge_ratio(0.5, 0.5, 0.5)
    var _t1_adapter_merge_ratio = perf_counter_ns()
    var _ns_adapter_merge_ratio = Float64(_t1_adapter_merge_ratio - _t0_adapter_merge_ratio) / Float64(N)
    print("MOJO_TIMING weight_loader::adapter_merge_ratio", _ns_adapter_merge_ratio, _acc_adapter_merge_ratio)
    var _acc_hf_model_index_shards: Float64 = 0.0
    var _t0_hf_model_index_shards = perf_counter_ns()
    for _ in range(N):
        _acc_hf_model_index_shards += hf_model_index_shards(0.5, 0.5, 0.5)
    var _t1_hf_model_index_shards = perf_counter_ns()
    var _ns_hf_model_index_shards = Float64(_t1_hf_model_index_shards - _t0_hf_model_index_shards) / Float64(N)
    print("MOJO_TIMING weight_loader::hf_model_index_shards", _ns_hf_model_index_shards, _acc_hf_model_index_shards)
    var _acc_weight_hash_verify: Float64 = 0.0
    var _t0_weight_hash_verify = perf_counter_ns()
    for _ in range(N):
        _acc_weight_hash_verify += weight_hash_verify(0.5, 0.5, 0.5)
    var _t1_weight_hash_verify = perf_counter_ns()
    var _ns_weight_hash_verify = Float64(_t1_weight_hash_verify - _t0_weight_hash_verify) / Float64(N)
    print("MOJO_TIMING weight_loader::weight_hash_verify", _ns_weight_hash_verify, _acc_weight_hash_verify)
