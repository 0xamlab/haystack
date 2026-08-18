"""mma_phase2_speed.mojo — Phase 2 real GPU measurement: scalar oracle vs. hardware MMA for the
three remaining shapes, at realistic Qwen3-0.6B-Base-scale dimensions (hidden=1024, FFN
intermediate=3072, both multiples of 32):

  o_proj:     M=256, K=1024 (n_heads*head_dim), N=1024 (hidden)      -- accum kernel
  down_proj:  M=256, K=3072 (FFN intermediate), N=1024 (hidden)      -- accum kernel, same fn
  swiglu:     M=256, K=1024 (hidden), N_FF=3072 (FFN intermediate)   -- swiglu kernel

Same repeated-dispatch-per-token, host-wall-clock-around-the-call methodology as
`mma_qkv_proj_speed.mojo`.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_phase2_speed.mojo \
        -o /tmp/mma_phase2_speed \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o \
        -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/mma_phase2_speed
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
from residentk.kernels import _pf_gemm_accum_kernel_i8, _pf_gemm_swiglu_kernel_i8

comptime M: Int = 256
comptime N_ITERS: Int = 200


def bench_one(
    label: String, oracle_idx: Int, mma_idx: Int, k: Int, n: Int, w_mult: Int, tile_n: Int = 32,
) raises -> None:
    var x_addr: UInt64 = 0
    var x_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w_addr: UInt64 = 0
    var w_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale_addr: UInt64 = 0
    var wscale_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_addr: UInt64 = 0
    var y_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    if _mb_alloc_buffer(M * k * 4, x_addr, x_contents) < 0:
        print("FAIL: alloc x for", label)
        return
    if _mb_alloc_buffer(w_mult * n * k, w_addr, w_contents) < 0:
        print("FAIL: alloc w for", label)
        return
    if _mb_alloc_buffer(w_mult * n * 4, wscale_addr, wscale_contents) < 0:
        print("FAIL: alloc wscale for", label)
        return
    if _mb_alloc_buffer(M * n * 4, y_addr, y_contents) < 0:
        print("FAIL: alloc y for", label)
        return

    var x_f32 = x_contents.bitcast[Float32]()
    for i in range(M * k):
        x_f32[i] = Float32((i * 7 + 3) % 13) / 6.0 - 1.0
    var w_i8 = w_contents.bitcast[Int8]()
    for i in range(w_mult * n * k):
        w_i8[i] = Int8((i * 11 + 5) % 17) - 8
    var wscale_f32 = wscale_contents.bitcast[Float32]()
    for i in range(w_mult * n):
        wscale_f32[i] = Float32(0.01) + Float32(i % 5) * Float32(0.001)

    var n_tile_rows = (M + 32 - 1) // 32
    var flops = Float64(2) * Float64(w_mult) * Float64(M) * Float64(k) * Float64(n) * Float64(N_ITERS)

    for which in range(2):
        var idx = oracle_idx if which == 0 else mma_idx
        var this_tile_n = 32 if which == 0 else tile_n
        var n_tile_cols = (n + this_tile_n - 1) // this_tile_n
        var grid = n_tile_cols * n_tile_rows
        var sub_label = label + (" ORACLE" if which == 0 else " MMA")

        var descs = _mb_alloc_descriptors(N_ITERS)
        for it in range(N_ITERS):
            _mb_set_header(descs, it, idx, grid, 256, 7)
            _mb_set_arg_ptr(descs, it, 0, y_addr)
            _mb_set_arg_ptr(descs, it, 1, x_addr)
            _mb_set_arg_ptr(descs, it, 2, w_addr)
            _mb_set_arg_ptr(descs, it, 3, wscale_addr)
            _mb_set_arg_int(descs, it, 4, M)
            _mb_set_arg_int(descs, it, 5, k)
            _mb_set_arg_int(descs, it, 6, n)

        if _mb_run_token(descs, N_ITERS) != 0:
            print("FAIL: warmup for", sub_label)
            return
        var t0 = perf_counter_ns()
        if _mb_run_token(descs, N_ITERS) != 0:
            print("FAIL: timed run for", sub_label)
            return
        var t1 = perf_counter_ns()

        var elapsed_s = Float64(t1 - t0) / 1.0e9
        var gflops = (flops / 1.0e9) / elapsed_s
        print(sub_label, ": ", elapsed_s * 1000.0, "ms /", N_ITERS, "iters,", gflops, "GFLOP/s")


def main() raises:
    from max.gpu.host import DeviceContext
    var cctx = DeviceContext()
    _ = cctx.compile_function[_pf_gemm_accum_kernel_i8]()
    _ = cctx.compile_function[_pf_gemm_swiglu_kernel_i8]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    var accum_oracle_idx = -1
    var accum_mma_idx = -1
    var accum_mma_narrow_idx = -1
    var swiglu_oracle_idx = -1
    var swiglu_mma_idx = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        if "gemm_accum_mma8x8_narrow" in name:
            accum_mma_narrow_idx = i
        elif "gemm_accum_mma8x8" in name:
            accum_mma_idx = i
        elif "gemm_acc" in name:
            accum_oracle_idx = i
        elif "gemm_swi" in name:
            swiglu_oracle_idx = i
        elif "swiglu_gemm_mma8x8" in name:
            swiglu_mma_idx = i
    if (accum_oracle_idx < 0 or accum_mma_idx < 0 or accum_mma_narrow_idx < 0
            or swiglu_oracle_idx < 0 or swiglu_mma_idx < 0):
        print("FAIL: pipeline not discovered:", accum_oracle_idx, accum_mma_idx,
              accum_mma_narrow_idx, swiglu_oracle_idx, swiglu_mma_idx)
        return

    bench_one("o_proj    (K=1024,N=1024) wide  ", accum_oracle_idx, accum_mma_idx, 1024, 1024, 1)
    bench_one("o_proj    (K=1024,N=1024) narrow", accum_oracle_idx, accum_mma_narrow_idx, 1024, 1024, 1, tile_n=16)
    bench_one("down_proj (K=3072,N=1024) wide  ", accum_oracle_idx, accum_mma_idx, 3072, 1024, 1)
    bench_one("down_proj (K=3072,N=1024) narrow", accum_oracle_idx, accum_mma_narrow_idx, 3072, 1024, 1, tile_n=16)
    bench_one("swiglu    (K=1024,N=3072)", swiglu_oracle_idx, swiglu_mma_idx, 1024, 3072, 2)
