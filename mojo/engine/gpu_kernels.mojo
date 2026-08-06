"""
gpu_kernels.mojo — GPU kernel math: tile sizes, occupancy, bandwidth, memory.
Zero Python imports.

Public API:
  tile_size_for_smem             — optimal tile size given shared memory
  warp_occupancy                 — active warps / max warps per SM
  arithmetic_intensity           — FLOPs per byte (roofline model)
  roofline_performance           — compute or memory bound throughput
  memory_coalescing_efficiency   — coalesced vs strided access ratio
  kernel_launch_overhead_ratio   — kernel launch vs compute ratio
  tensor_core_flops              — tensor core TFLOPS for matmul shape
  flash_attention_hbm_reads      — HBM reads for flash attention block
  register_pressure              — registers per thread estimate
  stream_multiprocessor_util     — SM utilization estimate
"""
from std.math import sqrt, log, exp


def tile_size_for_smem(
    shared_mem_bytes: Float64, dtype_bytes: Float64, n_operands: Float64
) -> Float64:
    """Optimal square tile size fitting in shared memory.

    tile² × n_operands × dtype_bytes ≤ shared_mem_bytes

    Args:
        shared_mem_bytes: Available shared memory per block (bytes).
        dtype_bytes: Bytes per element (2=FP16, 4=FP32).
        n_operands: Number of tile operands (2 for matmul A+B, 3 for A+B+C).

    Returns:
        Largest tile dimension t such that t² fits.
    """
    if dtype_bytes <= 0.0 or n_operands <= 0.0:
        return 16.0
    var max_elements = shared_mem_bytes / (dtype_bytes * n_operands)
    var tile = sqrt(max_elements)
    var t = Float64(Int64(tile))
    # Round down to power of 2
    var p = 1.0
    while p * 2.0 <= t:
        p = p * 2.0
    return p


def warp_occupancy(
    active_warps: Float64, max_warps_per_sm: Float64
) -> Float64:
    """Warp occupancy: fraction of max warps that are active.

    Args:
        active_warps: Warps scheduled per SM.
        max_warps_per_sm: Hardware maximum (64 for H100, 48 for A100).

    Returns:
        Occupancy (0–1; >0.5 generally good).
    """
    if max_warps_per_sm <= 0.0:
        return 0.0
    var occ = active_warps / max_warps_per_sm
    if occ > 1.0:
        return 1.0
    return occ


def arithmetic_intensity(
    flops: Float64, bytes_transferred: Float64
) -> Float64:
    """Arithmetic intensity: FLOPs per byte (roofline x-axis).

    Args:
        flops: Total floating point operations.
        bytes_transferred: Total bytes read/written from HBM.

    Returns:
        Arithmetic intensity (FLOPs/byte).
    """
    if bytes_transferred <= 0.0:
        return 1e9
    return flops / bytes_transferred


def roofline_performance(
    arithmetic_intensity_val: Float64,
    peak_tflops: Float64, peak_bandwidth_tbs: Float64
) -> Float64:
    """Roofline model peak achievable performance (TFLOPS).

    perf = min(peak_tflops, bandwidth × intensity)

    Args:
        arithmetic_intensity_val: FLOPs/byte for this kernel.
        peak_tflops: GPU peak compute (TFLOPS).
        peak_bandwidth_tbs: GPU memory bandwidth (TB/s).

    Returns:
        Achievable TFLOPS under roofline model.
    """
    var memory_bound = peak_bandwidth_tbs * arithmetic_intensity_val
    if memory_bound < peak_tflops:
        return memory_bound
    return peak_tflops


def memory_coalescing_efficiency(
    useful_bytes: Float64, cache_line_bytes: Float64
) -> Float64:
    """Memory coalescing efficiency: fraction of cache line actually used.

    Args:
        useful_bytes: Bytes actually needed by warp.
        cache_line_bytes: Cache line size (typically 128 bytes on GPU).

    Returns:
        Efficiency (1.0 = fully coalesced, lower = wasted bandwidth).
    """
    if cache_line_bytes <= 0.0:
        return 1.0
    var eff = useful_bytes / cache_line_bytes
    if eff > 1.0:
        return 1.0
    return eff


def kernel_launch_overhead_ratio(
    kernel_duration_us: Float64, launch_overhead_us: Float64
) -> Float64:
    """Fraction of time spent on kernel launch overhead.

    Args:
        kernel_duration_us: Actual kernel execution time (µs).
        launch_overhead_us: CUDA kernel launch overhead (~5-10µs).

    Returns:
        Overhead ratio (lower = better; < 0.1 acceptable).
    """
    var total = kernel_duration_us + launch_overhead_us
    if total <= 0.0:
        return 0.0
    return launch_overhead_us / total


def tensor_core_flops(
    m: Float64, n: Float64, k: Float64, clock_ghz: Float64, n_sms: Float64
) -> Float64:
    """Theoretical tensor core TFLOPS for matmul M×N×K.

    TFLOPS = 2MNK × clock × n_sms × ops_per_cycle / 1e12

    Simplified: 2MNK operations, throughput in GFLOPS.

    Args:
        m: Matrix M dimension.
        n: Matrix N dimension.
        k: Matrix K dimension.
        clock_ghz: SM clock frequency (GHz).
        n_sms: Number of streaming multiprocessors.

    Returns:
        Estimated TFLOPS for this matmul shape.
    """
    var flops = 2.0 * m * n * k
    return flops * clock_ghz * n_sms / 1e3


def flash_attention_hbm_reads(
    seq_len: Float64, head_dim: Float64, n_heads: Float64, dtype_bytes: Float64
) -> Float64:
    """HBM reads for one Flash Attention forward pass.

    Standard attention: O(N²d) reads.
    Flash attention: O(N²) scalar reads + O(Nd) KV block reads.
    Simplified estimate: 3 × seq × head_dim × n_heads × dtype_bytes (QKV).

    Args:
        seq_len: Sequence length N.
        head_dim: Head dimension d.
        n_heads: Number of heads H.
        dtype_bytes: Bytes per element (2 for FP16).

    Returns:
        Estimated HBM bytes read.
    """
    return 3.0 * seq_len * head_dim * n_heads * dtype_bytes


def register_pressure(
    thread_local_vars: Float64, dtype_bytes: Float64
) -> Float64:
    """Register file usage estimate per thread.

    Args:
        thread_local_vars: Number of thread-local variables / temporaries.
        dtype_bytes: Bytes per variable (4 for FP32).

    Returns:
        Register bytes per thread.
    """
    return thread_local_vars * dtype_bytes


def stream_multiprocessor_util(
    active_cycles: Float64, total_cycles: Float64
) -> Float64:
    """SM utilization: fraction of cycles with active warps.

    Args:
        active_cycles: Cycles with ≥1 active warp.
        total_cycles: Total elapsed cycles.

    Returns:
        SM utilization (0–1).
    """
    if total_cycles <= 0.0:
        return 0.0
    var util = active_cycles / total_cycles
    if util > 1.0:
        return 1.0
    return util
