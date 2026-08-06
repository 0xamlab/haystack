"""bench_model_serialization.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_serialization import weight_quantization_bits, checkpoint_size_estimate, delta_compression_ratio, weight_sparsity_ratio, model_flops_estimate, onnx_op_count_estimate, lora_parameter_count, pruning_sparsity_speedup, weight_sharing_ratio, version_hash_component
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

    var _acc_weight_quantization_bits: Float64 = 0.0
    var _t0_weight_quantization_bits = perf_counter_ns()
    for _ in range(N):
        _acc_weight_quantization_bits += weight_quantization_bits(0.5)
    var _t1_weight_quantization_bits = perf_counter_ns()
    var _ns_weight_quantization_bits = Float64(_t1_weight_quantization_bits - _t0_weight_quantization_bits) / Float64(N)
    print("MOJO_TIMING model_serialization::weight_quantization_bits", _ns_weight_quantization_bits, _acc_weight_quantization_bits)
    var _result_weight_quantization_bits = weight_quantization_bits(0.5)
    var _summary_weight_quantization_bits = _summary_float64(_result_weight_quantization_bits)
    print("MOJO_RESULT model_serialization::weight_quantization_bits", _summary_weight_quantization_bits)
    var _acc_checkpoint_size_estimate: Float64 = 0.0
    var _t0_checkpoint_size_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_checkpoint_size_estimate += checkpoint_size_estimate(0.5, 0.5, 0.5)
    var _t1_checkpoint_size_estimate = perf_counter_ns()
    var _ns_checkpoint_size_estimate = Float64(_t1_checkpoint_size_estimate - _t0_checkpoint_size_estimate) / Float64(N)
    print("MOJO_TIMING model_serialization::checkpoint_size_estimate", _ns_checkpoint_size_estimate, _acc_checkpoint_size_estimate)
    var _result_checkpoint_size_estimate = checkpoint_size_estimate(0.5, 0.5, 0.5)
    var _summary_checkpoint_size_estimate = _summary_float64(_result_checkpoint_size_estimate)
    print("MOJO_RESULT model_serialization::checkpoint_size_estimate", _summary_checkpoint_size_estimate)
    var _acc_delta_compression_ratio: Float64 = 0.0
    var _t0_delta_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_delta_compression_ratio += delta_compression_ratio(0.5, 0.5)
    var _t1_delta_compression_ratio = perf_counter_ns()
    var _ns_delta_compression_ratio = Float64(_t1_delta_compression_ratio - _t0_delta_compression_ratio) / Float64(N)
    print("MOJO_TIMING model_serialization::delta_compression_ratio", _ns_delta_compression_ratio, _acc_delta_compression_ratio)
    var _result_delta_compression_ratio = delta_compression_ratio(0.5, 0.5)
    var _summary_delta_compression_ratio = _summary_float64(_result_delta_compression_ratio)
    print("MOJO_RESULT model_serialization::delta_compression_ratio", _summary_delta_compression_ratio)
    var _acc_weight_sparsity_ratio: Float64 = 0.0
    var _t0_weight_sparsity_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_weight_sparsity_ratio += weight_sparsity_ratio(0.5, 0.5, 0.5)
    var _t1_weight_sparsity_ratio = perf_counter_ns()
    var _ns_weight_sparsity_ratio = Float64(_t1_weight_sparsity_ratio - _t0_weight_sparsity_ratio) / Float64(N)
    print("MOJO_TIMING model_serialization::weight_sparsity_ratio", _ns_weight_sparsity_ratio, _acc_weight_sparsity_ratio)
    var _result_weight_sparsity_ratio = weight_sparsity_ratio(0.5, 0.5, 0.5)
    var _summary_weight_sparsity_ratio = _summary_float64(_result_weight_sparsity_ratio)
    print("MOJO_RESULT model_serialization::weight_sparsity_ratio", _summary_weight_sparsity_ratio)
    var _acc_model_flops_estimate: Float64 = 0.0
    var _t0_model_flops_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_model_flops_estimate += model_flops_estimate(0.5, 0.5, 0.5)
    var _t1_model_flops_estimate = perf_counter_ns()
    var _ns_model_flops_estimate = Float64(_t1_model_flops_estimate - _t0_model_flops_estimate) / Float64(N)
    print("MOJO_TIMING model_serialization::model_flops_estimate", _ns_model_flops_estimate, _acc_model_flops_estimate)
    var _result_model_flops_estimate = model_flops_estimate(0.5, 0.5, 0.5)
    var _summary_model_flops_estimate = _summary_float64(_result_model_flops_estimate)
    print("MOJO_RESULT model_serialization::model_flops_estimate", _summary_model_flops_estimate)
    var _acc_onnx_op_count_estimate: Float64 = 0.0
    var _t0_onnx_op_count_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_onnx_op_count_estimate += onnx_op_count_estimate(0.5, 0.5, 0.5)
    var _t1_onnx_op_count_estimate = perf_counter_ns()
    var _ns_onnx_op_count_estimate = Float64(_t1_onnx_op_count_estimate - _t0_onnx_op_count_estimate) / Float64(N)
    print("MOJO_TIMING model_serialization::onnx_op_count_estimate", _ns_onnx_op_count_estimate, _acc_onnx_op_count_estimate)
    var _result_onnx_op_count_estimate = onnx_op_count_estimate(0.5, 0.5, 0.5)
    var _summary_onnx_op_count_estimate = _summary_float64(_result_onnx_op_count_estimate)
    print("MOJO_RESULT model_serialization::onnx_op_count_estimate", _summary_onnx_op_count_estimate)
    var _acc_lora_parameter_count: Float64 = 0.0
    var _t0_lora_parameter_count = perf_counter_ns()
    for _ in range(N):
        _acc_lora_parameter_count += lora_parameter_count(0.5, 0.5, 0.5)
    var _t1_lora_parameter_count = perf_counter_ns()
    var _ns_lora_parameter_count = Float64(_t1_lora_parameter_count - _t0_lora_parameter_count) / Float64(N)
    print("MOJO_TIMING model_serialization::lora_parameter_count", _ns_lora_parameter_count, _acc_lora_parameter_count)
    var _result_lora_parameter_count = lora_parameter_count(0.5, 0.5, 0.5)
    var _summary_lora_parameter_count = _summary_float64(_result_lora_parameter_count)
    print("MOJO_RESULT model_serialization::lora_parameter_count", _summary_lora_parameter_count)
    var _acc_pruning_sparsity_speedup: Float64 = 0.0
    var _t0_pruning_sparsity_speedup = perf_counter_ns()
    for _ in range(N):
        _acc_pruning_sparsity_speedup += pruning_sparsity_speedup(0.5, 0.5)
    var _t1_pruning_sparsity_speedup = perf_counter_ns()
    var _ns_pruning_sparsity_speedup = Float64(_t1_pruning_sparsity_speedup - _t0_pruning_sparsity_speedup) / Float64(N)
    print("MOJO_TIMING model_serialization::pruning_sparsity_speedup", _ns_pruning_sparsity_speedup, _acc_pruning_sparsity_speedup)
    var _result_pruning_sparsity_speedup = pruning_sparsity_speedup(0.5, 0.5)
    var _summary_pruning_sparsity_speedup = _summary_float64(_result_pruning_sparsity_speedup)
    print("MOJO_RESULT model_serialization::pruning_sparsity_speedup", _summary_pruning_sparsity_speedup)
    var _acc_weight_sharing_ratio: Float64 = 0.0
    var _t0_weight_sharing_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_weight_sharing_ratio += weight_sharing_ratio(0.5, 0.5)
    var _t1_weight_sharing_ratio = perf_counter_ns()
    var _ns_weight_sharing_ratio = Float64(_t1_weight_sharing_ratio - _t0_weight_sharing_ratio) / Float64(N)
    print("MOJO_TIMING model_serialization::weight_sharing_ratio", _ns_weight_sharing_ratio, _acc_weight_sharing_ratio)
    var _result_weight_sharing_ratio = weight_sharing_ratio(0.5, 0.5)
    var _summary_weight_sharing_ratio = _summary_float64(_result_weight_sharing_ratio)
    print("MOJO_RESULT model_serialization::weight_sharing_ratio", _summary_weight_sharing_ratio)
    var _acc_version_hash_component: Float64 = 0.0
    var _t0_version_hash_component = perf_counter_ns()
    for _ in range(N):
        _acc_version_hash_component += version_hash_component(0.5, 0.5, 0.5)
    var _t1_version_hash_component = perf_counter_ns()
    var _ns_version_hash_component = Float64(_t1_version_hash_component - _t0_version_hash_component) / Float64(N)
    print("MOJO_TIMING model_serialization::version_hash_component", _ns_version_hash_component, _acc_version_hash_component)
    var _result_version_hash_component = version_hash_component(0.5, 0.5, 0.5)
    var _summary_version_hash_component = _summary_float64(_result_version_hash_component)
    print("MOJO_RESULT model_serialization::version_hash_component", _summary_version_hash_component)
