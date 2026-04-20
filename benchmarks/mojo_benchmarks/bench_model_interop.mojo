"""bench_model_interop.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_interop import safetensors_tensor_offset, gguf_kv_metadata_size, onnx_node_flops, hf_config_head_dim, hf_rope_theta_scale, dtype_convert_scale, checkpoint_version_compat, weight_remap_cost, tokenizer_vocab_overlap, model_card_perplexity
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

    var _acc_safetensors_tensor_offset: Float64 = 0.0
    var _t0_safetensors_tensor_offset = perf_counter_ns()
    for _ in range(N):
        _acc_safetensors_tensor_offset += safetensors_tensor_offset(0.5, 0.5)
    var _t1_safetensors_tensor_offset = perf_counter_ns()
    var _ns_safetensors_tensor_offset = Float64(_t1_safetensors_tensor_offset - _t0_safetensors_tensor_offset) / Float64(N)
    print("MOJO_TIMING model_interop::safetensors_tensor_offset", _ns_safetensors_tensor_offset, _acc_safetensors_tensor_offset)
    var _acc_gguf_kv_metadata_size: Float64 = 0.0
    var _t0_gguf_kv_metadata_size = perf_counter_ns()
    for _ in range(N):
        _acc_gguf_kv_metadata_size += gguf_kv_metadata_size(0.5, 0.5, 0.5)
    var _t1_gguf_kv_metadata_size = perf_counter_ns()
    var _ns_gguf_kv_metadata_size = Float64(_t1_gguf_kv_metadata_size - _t0_gguf_kv_metadata_size) / Float64(N)
    print("MOJO_TIMING model_interop::gguf_kv_metadata_size", _ns_gguf_kv_metadata_size, _acc_gguf_kv_metadata_size)
    var _acc_onnx_node_flops: Float64 = 0.0
    var _t0_onnx_node_flops = perf_counter_ns()
    for _ in range(N):
        _acc_onnx_node_flops += onnx_node_flops(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_onnx_node_flops = perf_counter_ns()
    var _ns_onnx_node_flops = Float64(_t1_onnx_node_flops - _t0_onnx_node_flops) / Float64(N)
    print("MOJO_TIMING model_interop::onnx_node_flops", _ns_onnx_node_flops, _acc_onnx_node_flops)
    var _acc_hf_config_head_dim: Float64 = 0.0
    var _t0_hf_config_head_dim = perf_counter_ns()
    for _ in range(N):
        _acc_hf_config_head_dim += hf_config_head_dim(0.5, 0.5)
    var _t1_hf_config_head_dim = perf_counter_ns()
    var _ns_hf_config_head_dim = Float64(_t1_hf_config_head_dim - _t0_hf_config_head_dim) / Float64(N)
    print("MOJO_TIMING model_interop::hf_config_head_dim", _ns_hf_config_head_dim, _acc_hf_config_head_dim)
    var _acc_hf_rope_theta_scale: Float64 = 0.0
    var _t0_hf_rope_theta_scale = perf_counter_ns()
    for _ in range(N):
        _acc_hf_rope_theta_scale += hf_rope_theta_scale(0.5, 0.5)
    var _t1_hf_rope_theta_scale = perf_counter_ns()
    var _ns_hf_rope_theta_scale = Float64(_t1_hf_rope_theta_scale - _t0_hf_rope_theta_scale) / Float64(N)
    print("MOJO_TIMING model_interop::hf_rope_theta_scale", _ns_hf_rope_theta_scale, _acc_hf_rope_theta_scale)
    var _acc_dtype_convert_scale: Float64 = 0.0
    var _t0_dtype_convert_scale = perf_counter_ns()
    for _ in range(N):
        _acc_dtype_convert_scale += dtype_convert_scale(0.5, 0.5)
    var _t1_dtype_convert_scale = perf_counter_ns()
    var _ns_dtype_convert_scale = Float64(_t1_dtype_convert_scale - _t0_dtype_convert_scale) / Float64(N)
    print("MOJO_TIMING model_interop::dtype_convert_scale", _ns_dtype_convert_scale, _acc_dtype_convert_scale)
    var _acc_checkpoint_version_compat: Float64 = 0.0
    var _t0_checkpoint_version_compat = perf_counter_ns()
    for _ in range(N):
        _acc_checkpoint_version_compat += checkpoint_version_compat(0.5, 0.5)
    var _t1_checkpoint_version_compat = perf_counter_ns()
    var _ns_checkpoint_version_compat = Float64(_t1_checkpoint_version_compat - _t0_checkpoint_version_compat) / Float64(N)
    print("MOJO_TIMING model_interop::checkpoint_version_compat", _ns_checkpoint_version_compat, _acc_checkpoint_version_compat)
    var _acc_weight_remap_cost: Float64 = 0.0
    var _t0_weight_remap_cost = perf_counter_ns()
    for _ in range(N):
        _acc_weight_remap_cost += weight_remap_cost(0.5, 0.5, 0.5)
    var _t1_weight_remap_cost = perf_counter_ns()
    var _ns_weight_remap_cost = Float64(_t1_weight_remap_cost - _t0_weight_remap_cost) / Float64(N)
    print("MOJO_TIMING model_interop::weight_remap_cost", _ns_weight_remap_cost, _acc_weight_remap_cost)
    var _acc_tokenizer_vocab_overlap: Float64 = 0.0
    var _t0_tokenizer_vocab_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_tokenizer_vocab_overlap += tokenizer_vocab_overlap(0.5, 0.5, 0.5)
    var _t1_tokenizer_vocab_overlap = perf_counter_ns()
    var _ns_tokenizer_vocab_overlap = Float64(_t1_tokenizer_vocab_overlap - _t0_tokenizer_vocab_overlap) / Float64(N)
    print("MOJO_TIMING model_interop::tokenizer_vocab_overlap", _ns_tokenizer_vocab_overlap, _acc_tokenizer_vocab_overlap)
    var _acc_model_card_perplexity: Float64 = 0.0
    var _t0_model_card_perplexity = perf_counter_ns()
    for _ in range(N):
        _acc_model_card_perplexity += model_card_perplexity(0.5, 0.5)
    var _t1_model_card_perplexity = perf_counter_ns()
    var _ns_model_card_perplexity = Float64(_t1_model_card_perplexity - _t0_model_card_perplexity) / Float64(N)
    print("MOJO_TIMING model_interop::model_card_perplexity", _ns_model_card_perplexity, _acc_model_card_perplexity)
