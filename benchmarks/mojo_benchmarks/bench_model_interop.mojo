"""bench_model_interop.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_interop import safetensors_tensor_offset, gguf_kv_metadata_size, onnx_node_flops, hf_config_head_dim, hf_rope_theta_scale, dtype_convert_scale, checkpoint_version_compat, weight_remap_cost, tokenizer_vocab_overlap, model_card_perplexity
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

    var _acc_safetensors_tensor_offset: Float64 = 0.0
    var _t0_safetensors_tensor_offset = perf_counter_ns()
    for _ in range(N):
        _acc_safetensors_tensor_offset += safetensors_tensor_offset(0.5, 0.5)
    var _t1_safetensors_tensor_offset = perf_counter_ns()
    var _ns_safetensors_tensor_offset = Float64(_t1_safetensors_tensor_offset - _t0_safetensors_tensor_offset) / Float64(N)
    print("MOJO_TIMING model_interop::safetensors_tensor_offset", _ns_safetensors_tensor_offset, _acc_safetensors_tensor_offset)
    var _result_safetensors_tensor_offset = safetensors_tensor_offset(0.5, 0.5)
    var _summary_safetensors_tensor_offset = _summary_float64(_result_safetensors_tensor_offset)
    print("MOJO_RESULT model_interop::safetensors_tensor_offset", _summary_safetensors_tensor_offset)
    var _acc_gguf_kv_metadata_size: Float64 = 0.0
    var _t0_gguf_kv_metadata_size = perf_counter_ns()
    for _ in range(N):
        _acc_gguf_kv_metadata_size += gguf_kv_metadata_size(0.5, 0.5, 0.5)
    var _t1_gguf_kv_metadata_size = perf_counter_ns()
    var _ns_gguf_kv_metadata_size = Float64(_t1_gguf_kv_metadata_size - _t0_gguf_kv_metadata_size) / Float64(N)
    print("MOJO_TIMING model_interop::gguf_kv_metadata_size", _ns_gguf_kv_metadata_size, _acc_gguf_kv_metadata_size)
    var _result_gguf_kv_metadata_size = gguf_kv_metadata_size(0.5, 0.5, 0.5)
    var _summary_gguf_kv_metadata_size = _summary_float64(_result_gguf_kv_metadata_size)
    print("MOJO_RESULT model_interop::gguf_kv_metadata_size", _summary_gguf_kv_metadata_size)
    var _acc_onnx_node_flops: Float64 = 0.0
    var _t0_onnx_node_flops = perf_counter_ns()
    for _ in range(N):
        _acc_onnx_node_flops += onnx_node_flops(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_onnx_node_flops = perf_counter_ns()
    var _ns_onnx_node_flops = Float64(_t1_onnx_node_flops - _t0_onnx_node_flops) / Float64(N)
    print("MOJO_TIMING model_interop::onnx_node_flops", _ns_onnx_node_flops, _acc_onnx_node_flops)
    var _result_onnx_node_flops = onnx_node_flops(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_onnx_node_flops = _summary_float64(_result_onnx_node_flops)
    print("MOJO_RESULT model_interop::onnx_node_flops", _summary_onnx_node_flops)
    var _acc_hf_config_head_dim: Float64 = 0.0
    var _t0_hf_config_head_dim = perf_counter_ns()
    for _ in range(N):
        _acc_hf_config_head_dim += hf_config_head_dim(0.5, 0.5)
    var _t1_hf_config_head_dim = perf_counter_ns()
    var _ns_hf_config_head_dim = Float64(_t1_hf_config_head_dim - _t0_hf_config_head_dim) / Float64(N)
    print("MOJO_TIMING model_interop::hf_config_head_dim", _ns_hf_config_head_dim, _acc_hf_config_head_dim)
    var _result_hf_config_head_dim = hf_config_head_dim(0.5, 0.5)
    var _summary_hf_config_head_dim = _summary_float64(_result_hf_config_head_dim)
    print("MOJO_RESULT model_interop::hf_config_head_dim", _summary_hf_config_head_dim)
    var _acc_hf_rope_theta_scale: Float64 = 0.0
    var _t0_hf_rope_theta_scale = perf_counter_ns()
    for _ in range(N):
        _acc_hf_rope_theta_scale += hf_rope_theta_scale(0.5, 0.5)
    var _t1_hf_rope_theta_scale = perf_counter_ns()
    var _ns_hf_rope_theta_scale = Float64(_t1_hf_rope_theta_scale - _t0_hf_rope_theta_scale) / Float64(N)
    print("MOJO_TIMING model_interop::hf_rope_theta_scale", _ns_hf_rope_theta_scale, _acc_hf_rope_theta_scale)
    var _result_hf_rope_theta_scale = hf_rope_theta_scale(0.5, 0.5)
    var _summary_hf_rope_theta_scale = _summary_float64(_result_hf_rope_theta_scale)
    print("MOJO_RESULT model_interop::hf_rope_theta_scale", _summary_hf_rope_theta_scale)
    var _acc_dtype_convert_scale: Float64 = 0.0
    var _t0_dtype_convert_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dtype_convert_scale += dtype_convert_scale(0.5, 0.5)
    var _t1_dtype_convert_scale = perf_counter_ns()
    var _ns_dtype_convert_scale = Float64(_t1_dtype_convert_scale - _t0_dtype_convert_scale) / Float64(N)
    print("MOJO_TIMING model_interop::dtype_convert_scale", _ns_dtype_convert_scale, _acc_dtype_convert_scale)
    var _result_dtype_convert_scale = dtype_convert_scale(0.5, 0.5)
    var _summary_dtype_convert_scale = _summary_float64(_result_dtype_convert_scale)
    print("MOJO_RESULT model_interop::dtype_convert_scale", _summary_dtype_convert_scale)
    var _acc_checkpoint_version_compat: Float64 = 0.0
    var _t0_checkpoint_version_compat = perf_counter_ns()
    for _ in range(N):
        _acc_checkpoint_version_compat += checkpoint_version_compat(0.5, 0.5)
    var _t1_checkpoint_version_compat = perf_counter_ns()
    var _ns_checkpoint_version_compat = Float64(_t1_checkpoint_version_compat - _t0_checkpoint_version_compat) / Float64(N)
    print("MOJO_TIMING model_interop::checkpoint_version_compat", _ns_checkpoint_version_compat, _acc_checkpoint_version_compat)
    var _result_checkpoint_version_compat = checkpoint_version_compat(0.5, 0.5)
    var _summary_checkpoint_version_compat = _summary_float64(_result_checkpoint_version_compat)
    print("MOJO_RESULT model_interop::checkpoint_version_compat", _summary_checkpoint_version_compat)
    var _acc_weight_remap_cost: Float64 = 0.0
    var _t0_weight_remap_cost = perf_counter_ns()
    for _ in range(N):
        _acc_weight_remap_cost += weight_remap_cost(0.5, 0.5, 0.5)
    var _t1_weight_remap_cost = perf_counter_ns()
    var _ns_weight_remap_cost = Float64(_t1_weight_remap_cost - _t0_weight_remap_cost) / Float64(N)
    print("MOJO_TIMING model_interop::weight_remap_cost", _ns_weight_remap_cost, _acc_weight_remap_cost)
    var _result_weight_remap_cost = weight_remap_cost(0.5, 0.5, 0.5)
    var _summary_weight_remap_cost = _summary_float64(_result_weight_remap_cost)
    print("MOJO_RESULT model_interop::weight_remap_cost", _summary_weight_remap_cost)
    var _acc_tokenizer_vocab_overlap: Float64 = 0.0
    var _t0_tokenizer_vocab_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_tokenizer_vocab_overlap += tokenizer_vocab_overlap(0.5, 0.5, 0.5)
    var _t1_tokenizer_vocab_overlap = perf_counter_ns()
    var _ns_tokenizer_vocab_overlap = Float64(_t1_tokenizer_vocab_overlap - _t0_tokenizer_vocab_overlap) / Float64(N)
    print("MOJO_TIMING model_interop::tokenizer_vocab_overlap", _ns_tokenizer_vocab_overlap, _acc_tokenizer_vocab_overlap)
    var _result_tokenizer_vocab_overlap = tokenizer_vocab_overlap(0.5, 0.5, 0.5)
    var _summary_tokenizer_vocab_overlap = _summary_float64(_result_tokenizer_vocab_overlap)
    print("MOJO_RESULT model_interop::tokenizer_vocab_overlap", _summary_tokenizer_vocab_overlap)
    var _acc_model_card_perplexity: Float64 = 0.0
    var _t0_model_card_perplexity = perf_counter_ns()
    for _ in range(N):
        _acc_model_card_perplexity += model_card_perplexity(0.5, 0.5)
    var _t1_model_card_perplexity = perf_counter_ns()
    var _ns_model_card_perplexity = Float64(_t1_model_card_perplexity - _t0_model_card_perplexity) / Float64(N)
    print("MOJO_TIMING model_interop::model_card_perplexity", _ns_model_card_perplexity, _acc_model_card_perplexity)
    var _result_model_card_perplexity = model_card_perplexity(0.5, 0.5)
    var _summary_model_card_perplexity = _summary_float64(_result_model_card_perplexity)
    print("MOJO_RESULT model_interop::model_card_perplexity", _summary_model_card_perplexity)
