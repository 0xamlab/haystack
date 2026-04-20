"""bench_gpu_kernels.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from gpu_kernels import tile_size_for_smem, warp_occupancy, arithmetic_intensity, roofline_performance, memory_coalescing_efficiency, kernel_launch_overhead_ratio, tensor_core_flops, flash_attention_hbm_reads, register_pressure, stream_multiprocessor_util
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

    var _acc_tile_size_for_smem: Float64 = 0.0
    var _t0_tile_size_for_smem = perf_counter_ns()
    for _ in range(N):
        _acc_tile_size_for_smem += tile_size_for_smem(0.5, 0.5, 0.5)
    var _t1_tile_size_for_smem = perf_counter_ns()
    var _ns_tile_size_for_smem = Float64(_t1_tile_size_for_smem - _t0_tile_size_for_smem) / Float64(N)
    print("MOJO_TIMING gpu_kernels::tile_size_for_smem", _ns_tile_size_for_smem, _acc_tile_size_for_smem)
    var _acc_warp_occupancy: Float64 = 0.0
    var _t0_warp_occupancy = perf_counter_ns()
    for _ in range(N):
        _acc_warp_occupancy += warp_occupancy(0.5, 0.5)
    var _t1_warp_occupancy = perf_counter_ns()
    var _ns_warp_occupancy = Float64(_t1_warp_occupancy - _t0_warp_occupancy) / Float64(N)
    print("MOJO_TIMING gpu_kernels::warp_occupancy", _ns_warp_occupancy, _acc_warp_occupancy)
    var _acc_arithmetic_intensity: Float64 = 0.0
    var _t0_arithmetic_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_arithmetic_intensity += arithmetic_intensity(0.5, 0.5)
    var _t1_arithmetic_intensity = perf_counter_ns()
    var _ns_arithmetic_intensity = Float64(_t1_arithmetic_intensity - _t0_arithmetic_intensity) / Float64(N)
    print("MOJO_TIMING gpu_kernels::arithmetic_intensity", _ns_arithmetic_intensity, _acc_arithmetic_intensity)
    var _acc_roofline_performance: Float64 = 0.0
    var _t0_roofline_performance = perf_counter_ns()
    for _ in range(N):
        _acc_roofline_performance += roofline_performance(0.5, 0.5, 0.5)
    var _t1_roofline_performance = perf_counter_ns()
    var _ns_roofline_performance = Float64(_t1_roofline_performance - _t0_roofline_performance) / Float64(N)
    print("MOJO_TIMING gpu_kernels::roofline_performance", _ns_roofline_performance, _acc_roofline_performance)
    var _acc_memory_coalescing_efficiency: Float64 = 0.0
    var _t0_memory_coalescing_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_memory_coalescing_efficiency += memory_coalescing_efficiency(0.5, 0.5)
    var _t1_memory_coalescing_efficiency = perf_counter_ns()
    var _ns_memory_coalescing_efficiency = Float64(_t1_memory_coalescing_efficiency - _t0_memory_coalescing_efficiency) / Float64(N)
    print("MOJO_TIMING gpu_kernels::memory_coalescing_efficiency", _ns_memory_coalescing_efficiency, _acc_memory_coalescing_efficiency)
    var _acc_kernel_launch_overhead_ratio: Float64 = 0.0
    var _t0_kernel_launch_overhead_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_launch_overhead_ratio += kernel_launch_overhead_ratio(0.5, 0.5)
    var _t1_kernel_launch_overhead_ratio = perf_counter_ns()
    var _ns_kernel_launch_overhead_ratio = Float64(_t1_kernel_launch_overhead_ratio - _t0_kernel_launch_overhead_ratio) / Float64(N)
    print("MOJO_TIMING gpu_kernels::kernel_launch_overhead_ratio", _ns_kernel_launch_overhead_ratio, _acc_kernel_launch_overhead_ratio)
    var _acc_tensor_core_flops: Float64 = 0.0
    var _t0_tensor_core_flops = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_core_flops += tensor_core_flops(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_tensor_core_flops = perf_counter_ns()
    var _ns_tensor_core_flops = Float64(_t1_tensor_core_flops - _t0_tensor_core_flops) / Float64(N)
    print("MOJO_TIMING gpu_kernels::tensor_core_flops", _ns_tensor_core_flops, _acc_tensor_core_flops)
    var _acc_flash_attention_hbm_reads: Float64 = 0.0
    var _t0_flash_attention_hbm_reads = perf_counter_ns()
    for _ in range(N):
        _acc_flash_attention_hbm_reads += flash_attention_hbm_reads(0.5, 0.5, 0.5, 0.5)
    var _t1_flash_attention_hbm_reads = perf_counter_ns()
    var _ns_flash_attention_hbm_reads = Float64(_t1_flash_attention_hbm_reads - _t0_flash_attention_hbm_reads) / Float64(N)
    print("MOJO_TIMING gpu_kernels::flash_attention_hbm_reads", _ns_flash_attention_hbm_reads, _acc_flash_attention_hbm_reads)
    var _acc_register_pressure: Float64 = 0.0
    var _t0_register_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_register_pressure += register_pressure(0.5, 0.5)
    var _t1_register_pressure = perf_counter_ns()
    var _ns_register_pressure = Float64(_t1_register_pressure - _t0_register_pressure) / Float64(N)
    print("MOJO_TIMING gpu_kernels::register_pressure", _ns_register_pressure, _acc_register_pressure)
    var _acc_stream_multiprocessor_util: Float64 = 0.0
    var _t0_stream_multiprocessor_util = perf_counter_ns()
    for _ in range(N):
        _acc_stream_multiprocessor_util += stream_multiprocessor_util(0.5, 0.5)
    var _t1_stream_multiprocessor_util = perf_counter_ns()
    var _ns_stream_multiprocessor_util = Float64(_t1_stream_multiprocessor_util - _t0_stream_multiprocessor_util) / Float64(N)
    print("MOJO_TIMING gpu_kernels::stream_multiprocessor_util", _ns_stream_multiprocessor_util, _acc_stream_multiprocessor_util)
