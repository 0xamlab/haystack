"""bench_model_serialization.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_serialization import weight_quantization_bits, checkpoint_size_estimate, delta_compression_ratio, weight_sparsity_ratio, model_flops_estimate, onnx_op_count_estimate, lora_parameter_count, pruning_sparsity_speedup, weight_sharing_ratio, version_hash_component
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

    var _acc_weight_quantization_bits: Float64 = 0.0
    var _t0_weight_quantization_bits = perf_counter_ns()
    for _ in range(N):
        _acc_weight_quantization_bits += weight_quantization_bits(0.5)
    var _t1_weight_quantization_bits = perf_counter_ns()
    var _ns_weight_quantization_bits = Float64(_t1_weight_quantization_bits - _t0_weight_quantization_bits) / Float64(N)
    print("MOJO_TIMING model_serialization::weight_quantization_bits", _ns_weight_quantization_bits, _acc_weight_quantization_bits)
    var _acc_checkpoint_size_estimate: Float64 = 0.0
    var _t0_checkpoint_size_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_checkpoint_size_estimate += checkpoint_size_estimate(0.5, 0.5, 0.5)
    var _t1_checkpoint_size_estimate = perf_counter_ns()
    var _ns_checkpoint_size_estimate = Float64(_t1_checkpoint_size_estimate - _t0_checkpoint_size_estimate) / Float64(N)
    print("MOJO_TIMING model_serialization::checkpoint_size_estimate", _ns_checkpoint_size_estimate, _acc_checkpoint_size_estimate)
    var _acc_delta_compression_ratio: Float64 = 0.0
    var _t0_delta_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_delta_compression_ratio += delta_compression_ratio(0.5, 0.5)
    var _t1_delta_compression_ratio = perf_counter_ns()
    var _ns_delta_compression_ratio = Float64(_t1_delta_compression_ratio - _t0_delta_compression_ratio) / Float64(N)
    print("MOJO_TIMING model_serialization::delta_compression_ratio", _ns_delta_compression_ratio, _acc_delta_compression_ratio)
    var _acc_weight_sparsity_ratio: Float64 = 0.0
    var _t0_weight_sparsity_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_weight_sparsity_ratio += weight_sparsity_ratio(0.5, 0.5, 0.5)
    var _t1_weight_sparsity_ratio = perf_counter_ns()
    var _ns_weight_sparsity_ratio = Float64(_t1_weight_sparsity_ratio - _t0_weight_sparsity_ratio) / Float64(N)
    print("MOJO_TIMING model_serialization::weight_sparsity_ratio", _ns_weight_sparsity_ratio, _acc_weight_sparsity_ratio)
    var _acc_model_flops_estimate: Float64 = 0.0
    var _t0_model_flops_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_model_flops_estimate += model_flops_estimate(0.5, 0.5, 0.5)
    var _t1_model_flops_estimate = perf_counter_ns()
    var _ns_model_flops_estimate = Float64(_t1_model_flops_estimate - _t0_model_flops_estimate) / Float64(N)
    print("MOJO_TIMING model_serialization::model_flops_estimate", _ns_model_flops_estimate, _acc_model_flops_estimate)
    var _acc_onnx_op_count_estimate: Float64 = 0.0
    var _t0_onnx_op_count_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_onnx_op_count_estimate += onnx_op_count_estimate(0.5, 0.5, 0.5)
    var _t1_onnx_op_count_estimate = perf_counter_ns()
    var _ns_onnx_op_count_estimate = Float64(_t1_onnx_op_count_estimate - _t0_onnx_op_count_estimate) / Float64(N)
    print("MOJO_TIMING model_serialization::onnx_op_count_estimate", _ns_onnx_op_count_estimate, _acc_onnx_op_count_estimate)
    var _acc_lora_parameter_count: Float64 = 0.0
    var _t0_lora_parameter_count = perf_counter_ns()
    for _ in range(N):
        _acc_lora_parameter_count += lora_parameter_count(0.5, 0.5, 0.5)
    var _t1_lora_parameter_count = perf_counter_ns()
    var _ns_lora_parameter_count = Float64(_t1_lora_parameter_count - _t0_lora_parameter_count) / Float64(N)
    print("MOJO_TIMING model_serialization::lora_parameter_count", _ns_lora_parameter_count, _acc_lora_parameter_count)
    var _acc_pruning_sparsity_speedup: Float64 = 0.0
    var _t0_pruning_sparsity_speedup = perf_counter_ns()
    for _ in range(N):
        _acc_pruning_sparsity_speedup += pruning_sparsity_speedup(0.5, 0.5)
    var _t1_pruning_sparsity_speedup = perf_counter_ns()
    var _ns_pruning_sparsity_speedup = Float64(_t1_pruning_sparsity_speedup - _t0_pruning_sparsity_speedup) / Float64(N)
    print("MOJO_TIMING model_serialization::pruning_sparsity_speedup", _ns_pruning_sparsity_speedup, _acc_pruning_sparsity_speedup)
    var _acc_weight_sharing_ratio: Float64 = 0.0
    var _t0_weight_sharing_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_weight_sharing_ratio += weight_sharing_ratio(0.5, 0.5)
    var _t1_weight_sharing_ratio = perf_counter_ns()
    var _ns_weight_sharing_ratio = Float64(_t1_weight_sharing_ratio - _t0_weight_sharing_ratio) / Float64(N)
    print("MOJO_TIMING model_serialization::weight_sharing_ratio", _ns_weight_sharing_ratio, _acc_weight_sharing_ratio)
    var _acc_version_hash_component: Float64 = 0.0
    var _t0_version_hash_component = perf_counter_ns()
    for _ in range(N):
        _acc_version_hash_component += version_hash_component(0.5, 0.5, 0.5)
    var _t1_version_hash_component = perf_counter_ns()
    var _ns_version_hash_component = Float64(_t1_version_hash_component - _t0_version_hash_component) / Float64(N)
    print("MOJO_TIMING model_serialization::version_hash_component", _ns_version_hash_component, _acc_version_hash_component)
