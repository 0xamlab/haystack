"""bench_model_parallel.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from model_parallel import data_parallel_gradient_scale, tensor_parallel_split_dim, pipeline_bubble_fraction, gradient_all_reduce_bytes, activation_checkpointing_ratio, pipeline_stage_assignment, microbatch_throughput, zero_stage3_param_bytes, communication_computation_ratio, ddp_sync_overhead
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

    var _acc_data_parallel_gradient_scale: Float64 = 0.0
    var _t0_data_parallel_gradient_scale = perf_counter_ns()
    for _ in range(N):
        _acc_data_parallel_gradient_scale += data_parallel_gradient_scale(0.5)
    var _t1_data_parallel_gradient_scale = perf_counter_ns()
    var _ns_data_parallel_gradient_scale = Float64(_t1_data_parallel_gradient_scale - _t0_data_parallel_gradient_scale) / Float64(N)
    print("MOJO_TIMING model_parallel::data_parallel_gradient_scale", _ns_data_parallel_gradient_scale, _acc_data_parallel_gradient_scale)
    var _acc_tensor_parallel_split_dim: Float64 = 0.0
    var _t0_tensor_parallel_split_dim = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_parallel_split_dim += tensor_parallel_split_dim(0.5, 0.5)
    var _t1_tensor_parallel_split_dim = perf_counter_ns()
    var _ns_tensor_parallel_split_dim = Float64(_t1_tensor_parallel_split_dim - _t0_tensor_parallel_split_dim) / Float64(N)
    print("MOJO_TIMING model_parallel::tensor_parallel_split_dim", _ns_tensor_parallel_split_dim, _acc_tensor_parallel_split_dim)
    var _acc_pipeline_bubble_fraction: Float64 = 0.0
    var _t0_pipeline_bubble_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_pipeline_bubble_fraction += pipeline_bubble_fraction(0.5, 0.5)
    var _t1_pipeline_bubble_fraction = perf_counter_ns()
    var _ns_pipeline_bubble_fraction = Float64(_t1_pipeline_bubble_fraction - _t0_pipeline_bubble_fraction) / Float64(N)
    print("MOJO_TIMING model_parallel::pipeline_bubble_fraction", _ns_pipeline_bubble_fraction, _acc_pipeline_bubble_fraction)
    var _acc_gradient_all_reduce_bytes: Float64 = 0.0
    var _t0_gradient_all_reduce_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_all_reduce_bytes += gradient_all_reduce_bytes(0.5, 0.5, 0.5)
    var _t1_gradient_all_reduce_bytes = perf_counter_ns()
    var _ns_gradient_all_reduce_bytes = Float64(_t1_gradient_all_reduce_bytes - _t0_gradient_all_reduce_bytes) / Float64(N)
    print("MOJO_TIMING model_parallel::gradient_all_reduce_bytes", _ns_gradient_all_reduce_bytes, _acc_gradient_all_reduce_bytes)
    var _acc_activation_checkpointing_ratio: Float64 = 0.0
    var _t0_activation_checkpointing_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_activation_checkpointing_ratio += activation_checkpointing_ratio(0.5, 0.5)
    var _t1_activation_checkpointing_ratio = perf_counter_ns()
    var _ns_activation_checkpointing_ratio = Float64(_t1_activation_checkpointing_ratio - _t0_activation_checkpointing_ratio) / Float64(N)
    print("MOJO_TIMING model_parallel::activation_checkpointing_ratio", _ns_activation_checkpointing_ratio, _acc_activation_checkpointing_ratio)
    var _acc_pipeline_stage_assignment: Float64 = 0.0
    var _t0_pipeline_stage_assignment = perf_counter_ns()
    for _ in range(N):
        _acc_pipeline_stage_assignment += pipeline_stage_assignment(0.5, 0.5, 0.5)
    var _t1_pipeline_stage_assignment = perf_counter_ns()
    var _ns_pipeline_stage_assignment = Float64(_t1_pipeline_stage_assignment - _t0_pipeline_stage_assignment) / Float64(N)
    print("MOJO_TIMING model_parallel::pipeline_stage_assignment", _ns_pipeline_stage_assignment, _acc_pipeline_stage_assignment)
    var _acc_microbatch_throughput: Float64 = 0.0
    var _t0_microbatch_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_microbatch_throughput += microbatch_throughput(0.5, 0.5, 0.5)
    var _t1_microbatch_throughput = perf_counter_ns()
    var _ns_microbatch_throughput = Float64(_t1_microbatch_throughput - _t0_microbatch_throughput) / Float64(N)
    print("MOJO_TIMING model_parallel::microbatch_throughput", _ns_microbatch_throughput, _acc_microbatch_throughput)
    var _acc_zero_stage3_param_bytes: Float64 = 0.0
    var _t0_zero_stage3_param_bytes = perf_counter_ns()
    for _ in range(N):
        _acc_zero_stage3_param_bytes += zero_stage3_param_bytes(0.5, 0.5)
    var _t1_zero_stage3_param_bytes = perf_counter_ns()
    var _ns_zero_stage3_param_bytes = Float64(_t1_zero_stage3_param_bytes - _t0_zero_stage3_param_bytes) / Float64(N)
    print("MOJO_TIMING model_parallel::zero_stage3_param_bytes", _ns_zero_stage3_param_bytes, _acc_zero_stage3_param_bytes)
    var _acc_communication_computation_ratio: Float64 = 0.0
    var _t0_communication_computation_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_communication_computation_ratio += communication_computation_ratio(0.5, 0.5, 0.5)
    var _t1_communication_computation_ratio = perf_counter_ns()
    var _ns_communication_computation_ratio = Float64(_t1_communication_computation_ratio - _t0_communication_computation_ratio) / Float64(N)
    print("MOJO_TIMING model_parallel::communication_computation_ratio", _ns_communication_computation_ratio, _acc_communication_computation_ratio)
    var _acc_ddp_sync_overhead: Float64 = 0.0
    var _t0_ddp_sync_overhead = perf_counter_ns()
    for _ in range(N):
        _acc_ddp_sync_overhead += ddp_sync_overhead(0.5, 0.5)
    var _t1_ddp_sync_overhead = perf_counter_ns()
    var _ns_ddp_sync_overhead = Float64(_t1_ddp_sync_overhead - _t0_ddp_sync_overhead) / Float64(N)
    print("MOJO_TIMING model_parallel::ddp_sync_overhead", _ns_ddp_sync_overhead, _acc_ddp_sync_overhead)
