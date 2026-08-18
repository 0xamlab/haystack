"""mma_small_m_speed.mojo — does the hardware-MMA kernel (fixed BM=32 tile) still win at SMALL
m_rows, where the scalar NARROW tile (BM=8) exists specifically because the WIDE scalar tile wastes
most of a 32-row tile? MMA's compute cost per dispatch doesn't shrink with M within one tile (all 8
simdgroups still run full 8x8 MMA ops regardless of how many rows are real) the same way the
narrow scalar kernel's smaller BM does -- this decides whether the partial-tile fix should make MMA
UNCONDITIONAL, or whether small `m_rows` should still prefer the narrow scalar path.

M=5, the exact anchor `residentk_prefill_gemm_use_narrow_tile`'s own calibration already used
(narrow measured 110.1 tok/s there against wide's 91.6, end to end) -- qkv_proj shape (K=1024,
N=2048), matching every other real-shape measurement in this effort.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_small_m_speed.mojo \
        -o /tmp/mma_small_m_speed \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/mma_small_m_speed
"""

from std.time import perf_counter_ns
from metaldispatch.contract import MB_ERR_SESSION_OPEN_FAILED
from metaldispatch.ffi import (
    _mb_open_session,
    _mb_pipeline_count,
    _mb_pipeline_name,
    _mb_alloc_buffer,
    _mb_alloc_descriptors,
    _mb_set_header,
    _mb_set_arg_ptr,
    _mb_set_arg_int,
    _mb_run_token,
)
from residentk.kernels import _pf_gnrw_assign_kernel_i8

comptime M: Int = 5
comptime K: Int = 1024
comptime N: Int = 2048
comptime N_ITERS: Int = 200


def main() raises:
    from max.gpu.host import DeviceContext
    var cctx = DeviceContext()
    _ = cctx.compile_function[_pf_gnrw_assign_kernel_i8]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    var narrow_idx = -1
    var mma_idx = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        if "qkv_proj_gemm_mma8x8" in name:
            mma_idx = i
        elif "gnrw_ass" in name:
            narrow_idx = i
    if narrow_idx < 0 or mma_idx < 0:
        print("FAIL: pipelines not discovered, narrow_idx=", narrow_idx, "mma_idx=", mma_idx)
        return

    var xn_addr: UInt64 = 0
    var xn_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w_addr: UInt64 = 0
    var w_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale_addr: UInt64 = 0
    var wscale_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_addr: UInt64 = 0
    var y_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    _ = _mb_alloc_buffer(M * K * 4, xn_addr, xn_c)
    _ = _mb_alloc_buffer(N * K, w_addr, w_c)
    _ = _mb_alloc_buffer(N * 4, wscale_addr, wscale_c)
    _ = _mb_alloc_buffer(M * N * 4, y_addr, y_c)

    var xn_f32 = xn_c.bitcast[Float32]()
    for i in range(M * K):
        xn_f32[i] = Float32((i * 7 + 3) % 13) / 6.0 - 1.0
    var w_i8 = w_c.bitcast[Int8]()
    for i in range(N * K):
        w_i8[i] = Int8((i * 11 + 5) % 17) - 8
    var wscale_f32 = wscale_c.bitcast[Float32]()
    for i in range(N):
        wscale_f32[i] = Float32(0.01) + Float32(i % 5) * Float32(0.001)

    var flops = Float64(2) * Float64(M) * Float64(K) * Float64(N) * Float64(N_ITERS)

    for which in range(2):
        var idx = narrow_idx if which == 0 else mma_idx
        var tile_bm = 8 if which == 0 else 32
        var tile_nthreads = 128 if which == 0 else 256
        var grid = ((M + tile_bm - 1) // tile_bm) * ((N + 31) // 32)
        var label = "NARROW SCALAR (BM=8)" if which == 0 else "HARDWARE MMA (BM=32)"

        var descs = _mb_alloc_descriptors(N_ITERS)
        for it in range(N_ITERS):
            _mb_set_header(descs, it, idx, grid, tile_nthreads, 7)
            _mb_set_arg_ptr(descs, it, 0, y_addr)
            _mb_set_arg_ptr(descs, it, 1, xn_addr)
            _mb_set_arg_ptr(descs, it, 2, w_addr)
            _mb_set_arg_ptr(descs, it, 3, wscale_addr)
            _mb_set_arg_int(descs, it, 4, M)
            _mb_set_arg_int(descs, it, 5, K)
            _mb_set_arg_int(descs, it, 6, N)

        if _mb_run_token(descs, N_ITERS) != 0:
            print("FAIL: warmup for", label)
            return
        var t0 = perf_counter_ns()
        if _mb_run_token(descs, N_ITERS) != 0:
            print("FAIL: timed run for", label)
            return
        var t1 = perf_counter_ns()

        var elapsed_s = Float64(t1 - t0) / 1.0e9
        var gflops = (flops / 1.0e9) / elapsed_s
        print(label, ": ", elapsed_s * 1000.0, "ms /", N_ITERS, "iters,", gflops, "GFLOP/s")
