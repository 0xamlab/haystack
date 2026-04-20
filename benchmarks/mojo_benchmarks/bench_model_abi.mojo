"""bench_model_abi.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_abi import tensor_layout_stride, dtype_byte_width, attention_head_dim, rope_theta_scale, weight_shard_offset, activation_layout_index, model_config_head_count, kv_head_group_size, ffn_dim_from_model_dim, abi_version_compatible
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

    var _acc_tensor_layout_stride: Float64 = 0.0
    var _t0_tensor_layout_stride = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_layout_stride += tensor_layout_stride(0.5, 0.5, 0.5)
    var _t1_tensor_layout_stride = perf_counter_ns()
    var _ns_tensor_layout_stride = Float64(_t1_tensor_layout_stride - _t0_tensor_layout_stride) / Float64(N)
    print("MOJO_TIMING model_abi::tensor_layout_stride", _ns_tensor_layout_stride, _acc_tensor_layout_stride)
    var _acc_dtype_byte_width: Float64 = 0.0
    var _t0_dtype_byte_width = perf_counter_ns()
    for _ in range(N):
        _acc_dtype_byte_width += dtype_byte_width(0.5)
    var _t1_dtype_byte_width = perf_counter_ns()
    var _ns_dtype_byte_width = Float64(_t1_dtype_byte_width - _t0_dtype_byte_width) / Float64(N)
    print("MOJO_TIMING model_abi::dtype_byte_width", _ns_dtype_byte_width, _acc_dtype_byte_width)
    var _acc_attention_head_dim: Float64 = 0.0
    var _t0_attention_head_dim = perf_counter_ns()
    for _ in range(N):
        _acc_attention_head_dim += attention_head_dim(0.5, 0.5)
    var _t1_attention_head_dim = perf_counter_ns()
    var _ns_attention_head_dim = Float64(_t1_attention_head_dim - _t0_attention_head_dim) / Float64(N)
    print("MOJO_TIMING model_abi::attention_head_dim", _ns_attention_head_dim, _acc_attention_head_dim)
    var _acc_rope_theta_scale: Float64 = 0.0
    var _t0_rope_theta_scale = perf_counter_ns()
    for _ in range(N):
        _acc_rope_theta_scale += rope_theta_scale(0.5, 0.5, 0.5)
    var _t1_rope_theta_scale = perf_counter_ns()
    var _ns_rope_theta_scale = Float64(_t1_rope_theta_scale - _t0_rope_theta_scale) / Float64(N)
    print("MOJO_TIMING model_abi::rope_theta_scale", _ns_rope_theta_scale, _acc_rope_theta_scale)
    var _acc_weight_shard_offset: Float64 = 0.0
    var _t0_weight_shard_offset = perf_counter_ns()
    for _ in range(N):
        _acc_weight_shard_offset += weight_shard_offset(0.5, 0.5, 0.5)
    var _t1_weight_shard_offset = perf_counter_ns()
    var _ns_weight_shard_offset = Float64(_t1_weight_shard_offset - _t0_weight_shard_offset) / Float64(N)
    print("MOJO_TIMING model_abi::weight_shard_offset", _ns_weight_shard_offset, _acc_weight_shard_offset)
    var _acc_activation_layout_index: Float64 = 0.0
    var _t0_activation_layout_index = perf_counter_ns()
    for _ in range(N):
        _acc_activation_layout_index += activation_layout_index(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_activation_layout_index = perf_counter_ns()
    var _ns_activation_layout_index = Float64(_t1_activation_layout_index - _t0_activation_layout_index) / Float64(N)
    print("MOJO_TIMING model_abi::activation_layout_index", _ns_activation_layout_index, _acc_activation_layout_index)
    var _acc_model_config_head_count: Float64 = 0.0
    var _t0_model_config_head_count = perf_counter_ns()
    for _ in range(N):
        _acc_model_config_head_count += model_config_head_count(0.5, 0.5)
    var _t1_model_config_head_count = perf_counter_ns()
    var _ns_model_config_head_count = Float64(_t1_model_config_head_count - _t0_model_config_head_count) / Float64(N)
    print("MOJO_TIMING model_abi::model_config_head_count", _ns_model_config_head_count, _acc_model_config_head_count)
    var _acc_kv_head_group_size: Float64 = 0.0
    var _t0_kv_head_group_size = perf_counter_ns()
    for _ in range(N):
        _acc_kv_head_group_size += kv_head_group_size(0.5, 0.5)
    var _t1_kv_head_group_size = perf_counter_ns()
    var _ns_kv_head_group_size = Float64(_t1_kv_head_group_size - _t0_kv_head_group_size) / Float64(N)
    print("MOJO_TIMING model_abi::kv_head_group_size", _ns_kv_head_group_size, _acc_kv_head_group_size)
    var _acc_ffn_dim_from_model_dim: Float64 = 0.0
    var _t0_ffn_dim_from_model_dim = perf_counter_ns()
    for _ in range(N):
        _acc_ffn_dim_from_model_dim += ffn_dim_from_model_dim(0.5, 0.5, 0.5)
    var _t1_ffn_dim_from_model_dim = perf_counter_ns()
    var _ns_ffn_dim_from_model_dim = Float64(_t1_ffn_dim_from_model_dim - _t0_ffn_dim_from_model_dim) / Float64(N)
    print("MOJO_TIMING model_abi::ffn_dim_from_model_dim", _ns_ffn_dim_from_model_dim, _acc_ffn_dim_from_model_dim)
    var _acc_abi_version_compatible: Float64 = 0.0
    var _t0_abi_version_compatible = perf_counter_ns()
    for _ in range(N):
        _acc_abi_version_compatible += abi_version_compatible(0.5, 0.5, 0.5)
    var _t1_abi_version_compatible = perf_counter_ns()
    var _ns_abi_version_compatible = Float64(_t1_abi_version_compatible - _t0_abi_version_compatible) / Float64(N)
    print("MOJO_TIMING model_abi::abi_version_compatible", _ns_abi_version_compatible, _acc_abi_version_compatible)
