"""bench_gpu_kernels.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from gpu_kernels import tile_size_for_smem, warp_occupancy, arithmetic_intensity, roofline_performance, memory_coalescing_efficiency, kernel_launch_overhead_ratio, tensor_core_flops, flash_attention_hbm_reads, register_pressure, stream_multiprocessor_util
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

    var _acc_tile_size_for_smem: Float64 = 0.0
    var _t0_tile_size_for_smem = perf_counter_ns()
    for _ in range(N):
        _acc_tile_size_for_smem += tile_size_for_smem(0.5, 0.5, 0.5)
    var _t1_tile_size_for_smem = perf_counter_ns()
    var _ns_tile_size_for_smem = Float64(_t1_tile_size_for_smem - _t0_tile_size_for_smem) / Float64(N)
    print("MOJO_TIMING gpu_kernels::tile_size_for_smem", _ns_tile_size_for_smem, _acc_tile_size_for_smem)
    var _result_tile_size_for_smem = tile_size_for_smem(0.5, 0.5, 0.5)
    var _summary_tile_size_for_smem = _summary_float64(_result_tile_size_for_smem)
    print("MOJO_RESULT gpu_kernels::tile_size_for_smem", _summary_tile_size_for_smem)
    var _acc_warp_occupancy: Float64 = 0.0
    var _t0_warp_occupancy = perf_counter_ns()
    for _ in range(N):
        _acc_warp_occupancy += warp_occupancy(0.5, 0.5)
    var _t1_warp_occupancy = perf_counter_ns()
    var _ns_warp_occupancy = Float64(_t1_warp_occupancy - _t0_warp_occupancy) / Float64(N)
    print("MOJO_TIMING gpu_kernels::warp_occupancy", _ns_warp_occupancy, _acc_warp_occupancy)
    var _result_warp_occupancy = warp_occupancy(0.5, 0.5)
    var _summary_warp_occupancy = _summary_float64(_result_warp_occupancy)
    print("MOJO_RESULT gpu_kernels::warp_occupancy", _summary_warp_occupancy)
    var _acc_arithmetic_intensity: Float64 = 0.0
    var _t0_arithmetic_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_arithmetic_intensity += arithmetic_intensity(0.5, 0.5)
    var _t1_arithmetic_intensity = perf_counter_ns()
    var _ns_arithmetic_intensity = Float64(_t1_arithmetic_intensity - _t0_arithmetic_intensity) / Float64(N)
    print("MOJO_TIMING gpu_kernels::arithmetic_intensity", _ns_arithmetic_intensity, _acc_arithmetic_intensity)
    var _result_arithmetic_intensity = arithmetic_intensity(0.5, 0.5)
    var _summary_arithmetic_intensity = _summary_float64(_result_arithmetic_intensity)
    print("MOJO_RESULT gpu_kernels::arithmetic_intensity", _summary_arithmetic_intensity)
    var _acc_roofline_performance: Float64 = 0.0
    var _t0_roofline_performance = perf_counter_ns()
    for _ in range(N):
        _acc_roofline_performance += roofline_performance(0.5, 0.5, 0.5)
    var _t1_roofline_performance = perf_counter_ns()
    var _ns_roofline_performance = Float64(_t1_roofline_performance - _t0_roofline_performance) / Float64(N)
    print("MOJO_TIMING gpu_kernels::roofline_performance", _ns_roofline_performance, _acc_roofline_performance)
    var _result_roofline_performance = roofline_performance(0.5, 0.5, 0.5)
    var _summary_roofline_performance = _summary_float64(_result_roofline_performance)
    print("MOJO_RESULT gpu_kernels::roofline_performance", _summary_roofline_performance)
    var _acc_memory_coalescing_efficiency: Float64 = 0.0
    var _t0_memory_coalescing_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_memory_coalescing_efficiency += memory_coalescing_efficiency(0.5, 0.5)
    var _t1_memory_coalescing_efficiency = perf_counter_ns()
    var _ns_memory_coalescing_efficiency = Float64(_t1_memory_coalescing_efficiency - _t0_memory_coalescing_efficiency) / Float64(N)
    print("MOJO_TIMING gpu_kernels::memory_coalescing_efficiency", _ns_memory_coalescing_efficiency, _acc_memory_coalescing_efficiency)
    var _result_memory_coalescing_efficiency = memory_coalescing_efficiency(0.5, 0.5)
    var _summary_memory_coalescing_efficiency = _summary_float64(_result_memory_coalescing_efficiency)
    print("MOJO_RESULT gpu_kernels::memory_coalescing_efficiency", _summary_memory_coalescing_efficiency)
    var _acc_kernel_launch_overhead_ratio: Float64 = 0.0
    var _t0_kernel_launch_overhead_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_kernel_launch_overhead_ratio += kernel_launch_overhead_ratio(0.5, 0.5)
    var _t1_kernel_launch_overhead_ratio = perf_counter_ns()
    var _ns_kernel_launch_overhead_ratio = Float64(_t1_kernel_launch_overhead_ratio - _t0_kernel_launch_overhead_ratio) / Float64(N)
    print("MOJO_TIMING gpu_kernels::kernel_launch_overhead_ratio", _ns_kernel_launch_overhead_ratio, _acc_kernel_launch_overhead_ratio)
    var _result_kernel_launch_overhead_ratio = kernel_launch_overhead_ratio(0.5, 0.5)
    var _summary_kernel_launch_overhead_ratio = _summary_float64(_result_kernel_launch_overhead_ratio)
    print("MOJO_RESULT gpu_kernels::kernel_launch_overhead_ratio", _summary_kernel_launch_overhead_ratio)
    var _acc_tensor_core_flops: Float64 = 0.0
    var _t0_tensor_core_flops = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_core_flops += tensor_core_flops(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_tensor_core_flops = perf_counter_ns()
    var _ns_tensor_core_flops = Float64(_t1_tensor_core_flops - _t0_tensor_core_flops) / Float64(N)
    print("MOJO_TIMING gpu_kernels::tensor_core_flops", _ns_tensor_core_flops, _acc_tensor_core_flops)
    var _result_tensor_core_flops = tensor_core_flops(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_tensor_core_flops = _summary_float64(_result_tensor_core_flops)
    print("MOJO_RESULT gpu_kernels::tensor_core_flops", _summary_tensor_core_flops)
    var _acc_flash_attention_hbm_reads: Float64 = 0.0
    var _t0_flash_attention_hbm_reads = perf_counter_ns()
    for _ in range(N):
        _acc_flash_attention_hbm_reads += flash_attention_hbm_reads(0.5, 0.5, 0.5, 0.5)
    var _t1_flash_attention_hbm_reads = perf_counter_ns()
    var _ns_flash_attention_hbm_reads = Float64(_t1_flash_attention_hbm_reads - _t0_flash_attention_hbm_reads) / Float64(N)
    print("MOJO_TIMING gpu_kernels::flash_attention_hbm_reads", _ns_flash_attention_hbm_reads, _acc_flash_attention_hbm_reads)
    var _result_flash_attention_hbm_reads = flash_attention_hbm_reads(0.5, 0.5, 0.5, 0.5)
    var _summary_flash_attention_hbm_reads = _summary_float64(_result_flash_attention_hbm_reads)
    print("MOJO_RESULT gpu_kernels::flash_attention_hbm_reads", _summary_flash_attention_hbm_reads)
    var _acc_register_pressure: Float64 = 0.0
    var _t0_register_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_register_pressure += register_pressure(0.5, 0.5)
    var _t1_register_pressure = perf_counter_ns()
    var _ns_register_pressure = Float64(_t1_register_pressure - _t0_register_pressure) / Float64(N)
    print("MOJO_TIMING gpu_kernels::register_pressure", _ns_register_pressure, _acc_register_pressure)
    var _result_register_pressure = register_pressure(0.5, 0.5)
    var _summary_register_pressure = _summary_float64(_result_register_pressure)
    print("MOJO_RESULT gpu_kernels::register_pressure", _summary_register_pressure)
    var _acc_stream_multiprocessor_util: Float64 = 0.0
    var _t0_stream_multiprocessor_util = perf_counter_ns()
    for _ in range(N):
        _acc_stream_multiprocessor_util += stream_multiprocessor_util(0.5, 0.5)
    var _t1_stream_multiprocessor_util = perf_counter_ns()
    var _ns_stream_multiprocessor_util = Float64(_t1_stream_multiprocessor_util - _t0_stream_multiprocessor_util) / Float64(N)
    print("MOJO_TIMING gpu_kernels::stream_multiprocessor_util", _ns_stream_multiprocessor_util, _acc_stream_multiprocessor_util)
    var _result_stream_multiprocessor_util = stream_multiprocessor_util(0.5, 0.5)
    var _summary_stream_multiprocessor_util = _summary_float64(_result_stream_multiprocessor_util)
    print("MOJO_RESULT gpu_kernels::stream_multiprocessor_util", _summary_stream_multiprocessor_util)
