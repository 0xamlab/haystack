"""bench_weight_loader.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from weight_loader import shard_offset_bytes, safetensors_header_size, lazy_load_priority, gguf_quantized_block_size, checkpoint_resume_step, weight_diff_norm, partial_load_coverage, adapter_merge_ratio, hf_model_index_shards, weight_hash_verify
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
    var _result_shard_offset_bytes = shard_offset_bytes(0.5, 0.5, 0.5)
    var _summary_shard_offset_bytes = _summary_float64(_result_shard_offset_bytes)
    print("MOJO_RESULT weight_loader::shard_offset_bytes", _summary_shard_offset_bytes)
    var _acc_safetensors_header_size: Float64 = 0.0
    var _t0_safetensors_header_size = perf_counter_ns()
    for _ in range(N):
        _acc_safetensors_header_size += safetensors_header_size(0.5, 0.5)
    var _t1_safetensors_header_size = perf_counter_ns()
    var _ns_safetensors_header_size = Float64(_t1_safetensors_header_size - _t0_safetensors_header_size) / Float64(N)
    print("MOJO_TIMING weight_loader::safetensors_header_size", _ns_safetensors_header_size, _acc_safetensors_header_size)
    var _result_safetensors_header_size = safetensors_header_size(0.5, 0.5)
    var _summary_safetensors_header_size = _summary_float64(_result_safetensors_header_size)
    print("MOJO_RESULT weight_loader::safetensors_header_size", _summary_safetensors_header_size)
    var _acc_lazy_load_priority: Float64 = 0.0
    var _t0_lazy_load_priority = perf_counter_ns()
    for _ in range(N):
        _acc_lazy_load_priority += lazy_load_priority(0.5, 0.5, 0.5)
    var _t1_lazy_load_priority = perf_counter_ns()
    var _ns_lazy_load_priority = Float64(_t1_lazy_load_priority - _t0_lazy_load_priority) / Float64(N)
    print("MOJO_TIMING weight_loader::lazy_load_priority", _ns_lazy_load_priority, _acc_lazy_load_priority)
    var _result_lazy_load_priority = lazy_load_priority(0.5, 0.5, 0.5)
    var _summary_lazy_load_priority = _summary_float64(_result_lazy_load_priority)
    print("MOJO_RESULT weight_loader::lazy_load_priority", _summary_lazy_load_priority)
    var _acc_gguf_quantized_block_size: Float64 = 0.0
    var _t0_gguf_quantized_block_size = perf_counter_ns()
    for _ in range(N):
        _acc_gguf_quantized_block_size += gguf_quantized_block_size(0.5, 0.5)
    var _t1_gguf_quantized_block_size = perf_counter_ns()
    var _ns_gguf_quantized_block_size = Float64(_t1_gguf_quantized_block_size - _t0_gguf_quantized_block_size) / Float64(N)
    print("MOJO_TIMING weight_loader::gguf_quantized_block_size", _ns_gguf_quantized_block_size, _acc_gguf_quantized_block_size)
    var _result_gguf_quantized_block_size = gguf_quantized_block_size(0.5, 0.5)
    var _summary_gguf_quantized_block_size = _summary_float64(_result_gguf_quantized_block_size)
    print("MOJO_RESULT weight_loader::gguf_quantized_block_size", _summary_gguf_quantized_block_size)
    var _acc_checkpoint_resume_step: Float64 = 0.0
    var _t0_checkpoint_resume_step = perf_counter_ns()
    for _ in range(N):
        _acc_checkpoint_resume_step += checkpoint_resume_step(0.5, 0.5)
    var _t1_checkpoint_resume_step = perf_counter_ns()
    var _ns_checkpoint_resume_step = Float64(_t1_checkpoint_resume_step - _t0_checkpoint_resume_step) / Float64(N)
    print("MOJO_TIMING weight_loader::checkpoint_resume_step", _ns_checkpoint_resume_step, _acc_checkpoint_resume_step)
    var _result_checkpoint_resume_step = checkpoint_resume_step(0.5, 0.5)
    var _summary_checkpoint_resume_step = _summary_float64(_result_checkpoint_resume_step)
    print("MOJO_RESULT weight_loader::checkpoint_resume_step", _summary_checkpoint_resume_step)
    var _acc_weight_diff_norm: Float64 = 0.0
    var _t0_weight_diff_norm = perf_counter_ns()
    for _ in range(N):
        _acc_weight_diff_norm += weight_diff_norm(0.5, 0.5)
    var _t1_weight_diff_norm = perf_counter_ns()
    var _ns_weight_diff_norm = Float64(_t1_weight_diff_norm - _t0_weight_diff_norm) / Float64(N)
    print("MOJO_TIMING weight_loader::weight_diff_norm", _ns_weight_diff_norm, _acc_weight_diff_norm)
    var _result_weight_diff_norm = weight_diff_norm(0.5, 0.5)
    var _summary_weight_diff_norm = _summary_float64(_result_weight_diff_norm)
    print("MOJO_RESULT weight_loader::weight_diff_norm", _summary_weight_diff_norm)
    var _acc_partial_load_coverage: Float64 = 0.0
    var _t0_partial_load_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_partial_load_coverage += partial_load_coverage(0.5, 0.5)
    var _t1_partial_load_coverage = perf_counter_ns()
    var _ns_partial_load_coverage = Float64(_t1_partial_load_coverage - _t0_partial_load_coverage) / Float64(N)
    print("MOJO_TIMING weight_loader::partial_load_coverage", _ns_partial_load_coverage, _acc_partial_load_coverage)
    var _result_partial_load_coverage = partial_load_coverage(0.5, 0.5)
    var _summary_partial_load_coverage = _summary_float64(_result_partial_load_coverage)
    print("MOJO_RESULT weight_loader::partial_load_coverage", _summary_partial_load_coverage)
    var _acc_adapter_merge_ratio: Float64 = 0.0
    var _t0_adapter_merge_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_adapter_merge_ratio += adapter_merge_ratio(0.5, 0.5, 0.5)
    var _t1_adapter_merge_ratio = perf_counter_ns()
    var _ns_adapter_merge_ratio = Float64(_t1_adapter_merge_ratio - _t0_adapter_merge_ratio) / Float64(N)
    print("MOJO_TIMING weight_loader::adapter_merge_ratio", _ns_adapter_merge_ratio, _acc_adapter_merge_ratio)
    var _result_adapter_merge_ratio = adapter_merge_ratio(0.5, 0.5, 0.5)
    var _summary_adapter_merge_ratio = _summary_float64(_result_adapter_merge_ratio)
    print("MOJO_RESULT weight_loader::adapter_merge_ratio", _summary_adapter_merge_ratio)
    var _acc_hf_model_index_shards: Float64 = 0.0
    var _t0_hf_model_index_shards = perf_counter_ns()
    for _ in range(N):
        _acc_hf_model_index_shards += hf_model_index_shards(0.5, 0.5, 0.5)
    var _t1_hf_model_index_shards = perf_counter_ns()
    var _ns_hf_model_index_shards = Float64(_t1_hf_model_index_shards - _t0_hf_model_index_shards) / Float64(N)
    print("MOJO_TIMING weight_loader::hf_model_index_shards", _ns_hf_model_index_shards, _acc_hf_model_index_shards)
    var _result_hf_model_index_shards = hf_model_index_shards(0.5, 0.5, 0.5)
    var _summary_hf_model_index_shards = _summary_float64(_result_hf_model_index_shards)
    print("MOJO_RESULT weight_loader::hf_model_index_shards", _summary_hf_model_index_shards)
    var _acc_weight_hash_verify: Float64 = 0.0
    var _t0_weight_hash_verify = perf_counter_ns()
    for _ in range(N):
        _acc_weight_hash_verify += weight_hash_verify(0.5, 0.5, 0.5)
    var _t1_weight_hash_verify = perf_counter_ns()
    var _ns_weight_hash_verify = Float64(_t1_weight_hash_verify - _t0_weight_hash_verify) / Float64(N)
    print("MOJO_TIMING weight_loader::weight_hash_verify", _ns_weight_hash_verify, _acc_weight_hash_verify)
    var _result_weight_hash_verify = weight_hash_verify(0.5, 0.5, 0.5)
    var _summary_weight_hash_verify = _summary_float64(_result_weight_hash_verify)
    print("MOJO_RESULT weight_loader::weight_hash_verify", _summary_weight_hash_verify)
