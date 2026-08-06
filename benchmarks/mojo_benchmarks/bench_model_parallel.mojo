"""bench_model_parallel.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_parallel import data_parallel_gradient_scale, tensor_parallel_split_dim, pipeline_bubble_fraction, gradient_all_reduce_bytes, activation_checkpointing_ratio, pipeline_stage_assignment, microbatch_throughput, zero_stage3_param_bytes, communication_computation_ratio, ddp_sync_overhead
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

    var _acc_data_parallel_gradient_scale: Float64 = 0.0
    var _t0_data_parallel_gradient_scale = perf_counter_ns()
    for _ in range(N):
        _acc_data_parallel_gradient_scale += data_parallel_gradient_scale(0.5)
    var _t1_data_parallel_gradient_scale = perf_counter_ns()
    var _ns_data_parallel_gradient_scale = Float64(_t1_data_parallel_gradient_scale - _t0_data_parallel_gradient_scale) / Float64(N)
    print("MOJO_TIMING model_parallel::data_parallel_gradient_scale", _ns_data_parallel_gradient_scale, _acc_data_parallel_gradient_scale)
    var _result_data_parallel_gradient_scale = data_parallel_gradient_scale(0.5)
    var _summary_data_parallel_gradient_scale = _summary_float64(_result_data_parallel_gradient_scale)
    print("MOJO_RESULT model_parallel::data_parallel_gradient_scale", _summary_data_parallel_gradient_scale)
    var _acc_tensor_parallel_split_dim: Float64 = 0.0
    var _t0_tensor_parallel_split_dim = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_parallel_split_dim += tensor_parallel_split_dim(0.5, 0.5)
    var _t1_tensor_parallel_split_dim = perf_counter_ns()
    var _ns_tensor_parallel_split_dim = Float64(_t1_tensor_parallel_split_dim - _t0_tensor_parallel_split_dim) / Float64(N)
    print("MOJO_TIMING model_parallel::tensor_parallel_split_dim", _ns_tensor_parallel_split_dim, _acc_tensor_parallel_split_dim)
    var _result_tensor_parallel_split_dim = tensor_parallel_split_dim(0.5, 0.5)
    var _summary_tensor_parallel_split_dim = _summary_float64(_result_tensor_parallel_split_dim)
    print("MOJO_RESULT model_parallel::tensor_parallel_split_dim", _summary_tensor_parallel_split_dim)
    var _acc_pipeline_bubble_fraction: Float64 = 0.0
    var _t0_pipeline_bubble_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_pipeline_bubble_fraction += pipeline_bubble_fraction(0.5, 0.5)
    var _t1_pipeline_bubble_fraction = perf_counter_ns()
    var _ns_pipeline_bubble_fraction = Float64(_t1_pipeline_bubble_fraction - _t0_pipeline_bubble_fraction) / Float64(N)
    print("MOJO_TIMING model_parallel::pipeline_bubble_fraction", _ns_pipeline_bubble_fraction, _acc_pipeline_bubble_fraction)
    var _result_pipeline_bubble_fraction = pipeline_bubble_fraction(0.5, 0.5)
    var _summary_pipeline_bubble_fraction = _summary_float64(_result_pipeline_bubble_fraction)
    print("MOJO_RESULT model_parallel::pipeline_bubble_fraction", _summary_pipeline_bubble_fraction)
    var _acc_gradient_all_reduce_bytes: Float64 = 0.0
    var _t0_gradient_all_reduce_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_all_reduce_bytes += gradient_all_reduce_bytes(0.5, 0.5, 0.5)
    var _t1_gradient_all_reduce_bytes = perf_counter_ns()
    var _ns_gradient_all_reduce_bytes = Float64(_t1_gradient_all_reduce_bytes - _t0_gradient_all_reduce_bytes) / Float64(N)
    print("MOJO_TIMING model_parallel::gradient_all_reduce_bytes", _ns_gradient_all_reduce_bytes, _acc_gradient_all_reduce_bytes)
    var _result_gradient_all_reduce_bytes = gradient_all_reduce_bytes(0.5, 0.5, 0.5)
    var _summary_gradient_all_reduce_bytes = _summary_float64(_result_gradient_all_reduce_bytes)
    print("MOJO_RESULT model_parallel::gradient_all_reduce_bytes", _summary_gradient_all_reduce_bytes)
    var _acc_activation_checkpointing_ratio: Float64 = 0.0
    var _t0_activation_checkpointing_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_activation_checkpointing_ratio += activation_checkpointing_ratio(0.5, 0.5)
    var _t1_activation_checkpointing_ratio = perf_counter_ns()
    var _ns_activation_checkpointing_ratio = Float64(_t1_activation_checkpointing_ratio - _t0_activation_checkpointing_ratio) / Float64(N)
    print("MOJO_TIMING model_parallel::activation_checkpointing_ratio", _ns_activation_checkpointing_ratio, _acc_activation_checkpointing_ratio)
    var _result_activation_checkpointing_ratio = activation_checkpointing_ratio(0.5, 0.5)
    var _summary_activation_checkpointing_ratio = _summary_float64(_result_activation_checkpointing_ratio)
    print("MOJO_RESULT model_parallel::activation_checkpointing_ratio", _summary_activation_checkpointing_ratio)
    var _acc_pipeline_stage_assignment: Float64 = 0.0
    var _t0_pipeline_stage_assignment = perf_counter_ns()
    for _ in range(N):
        _acc_pipeline_stage_assignment += pipeline_stage_assignment(0.5, 0.5, 0.5)
    var _t1_pipeline_stage_assignment = perf_counter_ns()
    var _ns_pipeline_stage_assignment = Float64(_t1_pipeline_stage_assignment - _t0_pipeline_stage_assignment) / Float64(N)
    print("MOJO_TIMING model_parallel::pipeline_stage_assignment", _ns_pipeline_stage_assignment, _acc_pipeline_stage_assignment)
    var _result_pipeline_stage_assignment = pipeline_stage_assignment(0.5, 0.5, 0.5)
    var _summary_pipeline_stage_assignment = _summary_float64(_result_pipeline_stage_assignment)
    print("MOJO_RESULT model_parallel::pipeline_stage_assignment", _summary_pipeline_stage_assignment)
    var _acc_microbatch_throughput: Float64 = 0.0
    var _t0_microbatch_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_microbatch_throughput += microbatch_throughput(0.5, 0.5, 0.5)
    var _t1_microbatch_throughput = perf_counter_ns()
    var _ns_microbatch_throughput = Float64(_t1_microbatch_throughput - _t0_microbatch_throughput) / Float64(N)
    print("MOJO_TIMING model_parallel::microbatch_throughput", _ns_microbatch_throughput, _acc_microbatch_throughput)
    var _result_microbatch_throughput = microbatch_throughput(0.5, 0.5, 0.5)
    var _summary_microbatch_throughput = _summary_float64(_result_microbatch_throughput)
    print("MOJO_RESULT model_parallel::microbatch_throughput", _summary_microbatch_throughput)
    var _acc_zero_stage3_param_bytes: Float64 = 0.0
    var _t0_zero_stage3_param_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_zero_stage3_param_bytes += zero_stage3_param_bytes(0.5, 0.5)
    var _t1_zero_stage3_param_bytes = perf_counter_ns()
    var _ns_zero_stage3_param_bytes = Float64(_t1_zero_stage3_param_bytes - _t0_zero_stage3_param_bytes) / Float64(N)
    print("MOJO_TIMING model_parallel::zero_stage3_param_bytes", _ns_zero_stage3_param_bytes, _acc_zero_stage3_param_bytes)
    var _result_zero_stage3_param_bytes = zero_stage3_param_bytes(0.5, 0.5)
    var _summary_zero_stage3_param_bytes = _summary_float64(_result_zero_stage3_param_bytes)
    print("MOJO_RESULT model_parallel::zero_stage3_param_bytes", _summary_zero_stage3_param_bytes)
    var _acc_communication_computation_ratio: Float64 = 0.0
    var _t0_communication_computation_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_communication_computation_ratio += communication_computation_ratio(0.5, 0.5, 0.5)
    var _t1_communication_computation_ratio = perf_counter_ns()
    var _ns_communication_computation_ratio = Float64(_t1_communication_computation_ratio - _t0_communication_computation_ratio) / Float64(N)
    print("MOJO_TIMING model_parallel::communication_computation_ratio", _ns_communication_computation_ratio, _acc_communication_computation_ratio)
    var _result_communication_computation_ratio = communication_computation_ratio(0.5, 0.5, 0.5)
    var _summary_communication_computation_ratio = _summary_float64(_result_communication_computation_ratio)
    print("MOJO_RESULT model_parallel::communication_computation_ratio", _summary_communication_computation_ratio)
    var _acc_ddp_sync_overhead: Float64 = 0.0
    var _t0_ddp_sync_overhead = perf_counter_ns()
    for _ in range(N):
        _acc_ddp_sync_overhead += ddp_sync_overhead(0.5, 0.5)
    var _t1_ddp_sync_overhead = perf_counter_ns()
    var _ns_ddp_sync_overhead = Float64(_t1_ddp_sync_overhead - _t0_ddp_sync_overhead) / Float64(N)
    print("MOJO_TIMING model_parallel::ddp_sync_overhead", _ns_ddp_sync_overhead, _acc_ddp_sync_overhead)
    var _result_ddp_sync_overhead = ddp_sync_overhead(0.5, 0.5)
    var _summary_ddp_sync_overhead = _summary_float64(_result_ddp_sync_overhead)
    print("MOJO_RESULT model_parallel::ddp_sync_overhead", _summary_ddp_sync_overhead)
