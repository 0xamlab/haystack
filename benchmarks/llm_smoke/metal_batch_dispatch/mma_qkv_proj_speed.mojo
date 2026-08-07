"""mma_qkv_proj_speed.mojo — Phase 1 real GPU measurement: scalar oracle `_pf_gemm_assign_kernel_i8`
vs. hardware-MMA `_qkv_proj_gemm_mma8x8`, at Qwen3-0.6B-Base's real qkv_proj shape
(K=1024 hidden, N=2048 combined q+k+v with GQA, both multiples of 32 -- satisfies this kernel's
Phase-1 tile-alignment requirement), M=256 (the scalar-GEMM effort's own established "real win"
measurement point, PR #584). `N_ITERS` repeated dispatches of ONE kernel per `algenta_run_token`
call, host-side wall-clock around the call -- amortizes per-call overhead, same approach as this
package's own `submission_fixed_vs_marginal_probe.m` already established for isolating steady-state
per-dispatch cost.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_qkv_proj_speed.mojo \
        -o /tmp/mma_qkv_proj_speed \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o \
        -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/mma_qkv_proj_speed
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
from residentk.kernels import _pf_gemm_assign_kernel_i8

comptime M: Int = 256
comptime K: Int = 1024
comptime N: Int = 2048
comptime N_ITERS: Int = 200


def main() raises:
    from std.gpu.host import DeviceContext
    var cctx = DeviceContext()
    _ = cctx.compile_function[_pf_gemm_assign_kernel_i8]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    var oracle_idx = -1
    var mma_idx = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        if "gemm_ass" in name:
            oracle_idx = i
        if "qkv_proj_gemm_mma8x8" in name:
            mma_idx = i
    if oracle_idx < 0 or mma_idx < 0:
        print("FAIL: pipelines not discovered, oracle_idx=", oracle_idx, "mma_idx=", mma_idx)
        return

    var xn_addr: UInt64 = 0
    var xn_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w_addr: UInt64 = 0
    var w_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale_addr: UInt64 = 0
    var wscale_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_addr: UInt64 = 0
    var y_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    if _mb_alloc_buffer(M * K * 4, xn_addr, xn_contents) < 0:
        print("FAIL: alloc xn")
        return
    if _mb_alloc_buffer(N * K, w_addr, w_contents) < 0:
        print("FAIL: alloc w")
        return
    if _mb_alloc_buffer(N * 4, wscale_addr, wscale_contents) < 0:
        print("FAIL: alloc wscale")
        return
    if _mb_alloc_buffer(M * N * 4, y_addr, y_contents) < 0:
        print("FAIL: alloc y")
        return

    var xn_f32 = xn_contents.bitcast[Float32]()
    for i in range(M * K):
        xn_f32[i] = Float32((i * 7 + 3) % 13) / 6.0 - 1.0
    var w_i8 = w_contents.bitcast[Int8]()
    for i in range(N * K):
        w_i8[i] = Int8((i * 11 + 5) % 17) - 8
    var wscale_f32 = wscale_contents.bitcast[Float32]()
    for i in range(N):
        wscale_f32[i] = Float32(0.01) + Float32(i % 5) * Float32(0.001)

    var n_tile_cols = (N + 32 - 1) // 32
    var n_tile_rows = (M + 32 - 1) // 32
    var grid = n_tile_cols * n_tile_rows

    var flops = Float64(2) * Float64(M) * Float64(K) * Float64(N) * Float64(N_ITERS)

    for which in range(2):
        var idx = oracle_idx if which == 0 else mma_idx
        var label = "SCALAR ORACLE" if which == 0 else "HARDWARE MMA"

        var descs = _mb_alloc_descriptors(N_ITERS)
        for it in range(N_ITERS):
            _mb_set_header(descs, it, idx, grid, 256, 7)
            _mb_set_arg_ptr(descs, it, 0, y_addr)
            _mb_set_arg_ptr(descs, it, 1, xn_addr)
            _mb_set_arg_ptr(descs, it, 2, w_addr)
            _mb_set_arg_ptr(descs, it, 3, wscale_addr)
            _mb_set_arg_int(descs, it, 4, M)
            _mb_set_arg_int(descs, it, 5, K)
            _mb_set_arg_int(descs, it, 6, N)

        # one warmup token (pipeline-state/first-dispatch overhead, excluded from the timed run)
        if _mb_run_token(descs, N_ITERS) != 0:
            print("FAIL: warmup run_token failed for", label)
            return

        var t0 = perf_counter_ns()
        if _mb_run_token(descs, N_ITERS) != 0:
            print("FAIL: timed run_token failed for", label)
            return
        var t1 = perf_counter_ns()

        var elapsed_s = Float64(t1 - t0) / 1.0e9
        var gflops = (flops / 1.0e9) / elapsed_s
        var us_per_call = (elapsed_s * 1.0e6) / Float64(N_ITERS)
        print(label, ": ", elapsed_s * 1000.0, "ms total /", N_ITERS, "iters =", us_per_call,
              "us/call,", gflops, "GFLOP/s")
