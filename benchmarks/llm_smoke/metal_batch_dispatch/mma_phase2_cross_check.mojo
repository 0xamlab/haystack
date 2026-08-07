"""mma_phase2_cross_check.mojo — Phase 2 cross-toolchain correctness check for the two new roles:
`_gemm_accum_mma8x8` (vs. scalar oracle `_pf_gemm_accum_kernel_i8`, reused for o_proj/down_proj)
and `_swiglu_gemm_mma8x8` (vs. scalar oracle `_pf_gemm_swiglu_kernel_i8`). Same methodology as
`mma_qkv_proj_cross_check.mojo`: identical inputs, both kernels dispatched through the SAME
production `algenta_run_token()`, diffed on the host. M=64, K=48, N=64 for accum (multi-tile,
multi-K-step); M=64, K=48, N_FF=64 for swiglu.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_phase2_cross_check.mojo \
        -o /tmp/mma_phase2_cross_check \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o \
        -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/mma_phase2_cross_check
"""

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

comptime M: Int = 64
comptime K: Int = 48
comptime N: Int = 64


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def main() raises:
    from std.gpu.host import DeviceContext
    var cctx = DeviceContext()
    _ = cctx.compile_function[_pf_gemm_accum_kernel_i8]()
    _ = cctx.compile_function[_pf_gemm_swiglu_kernel_i8]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    print("discovered pipelines:", count)
    var accum_oracle_idx = -1
    var accum_mma_idx = -1
    var swiglu_oracle_idx = -1
    var swiglu_mma_idx = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        print(" [", i, "]", name)
        if "gemm_acc" in name:
            accum_oracle_idx = i
        if "gemm_accum_mma8x8" in name:
            accum_mma_idx = i
        if "gemm_swi" in name:
            swiglu_oracle_idx = i
        if "swiglu_gemm_mma8x8" in name:
            swiglu_mma_idx = i

    if accum_oracle_idx < 0 or accum_mma_idx < 0 or swiglu_oracle_idx < 0 or swiglu_mma_idx < 0:
        print("FAIL: pipeline not discovered:", accum_oracle_idx, accum_mma_idx, swiglu_oracle_idx, swiglu_mma_idx)
        return

    var n_tile_cols = (N + 32 - 1) // 32
    var n_tile_rows = (M + 32 - 1) // 32
    var grid = n_tile_cols * n_tile_rows

    # --- accum test ---
    var x_vals = List[Float32](capacity=M * K)
    for i in range(M * K):
        x_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=N * K)
    for i in range(N * K):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=N)
    for i in range(N):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))
    var y_init_vals = List[Float32](capacity=M * N)
    for i in range(M * N):
        y_init_vals.append(Float32((i * 3 + 1) % 9) / 4.0 - 1.0)

    var x_addr: UInt64 = 0
    var x_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w_addr: UInt64 = 0
    var w_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale_addr: UInt64 = 0
    var wscale_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_oracle_addr: UInt64 = 0
    var y_oracle_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_mma_addr: UInt64 = 0
    var y_mma_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    _ = _mb_alloc_buffer(M * K * 4, x_addr, x_contents)
    _ = _mb_alloc_buffer(N * K, w_addr, w_contents)
    _ = _mb_alloc_buffer(N * 4, wscale_addr, wscale_contents)
    _ = _mb_alloc_buffer(M * N * 4, y_oracle_addr, y_oracle_contents)
    _ = _mb_alloc_buffer(M * N * 4, y_mma_addr, y_mma_contents)

    var x_f32 = x_contents.bitcast[Float32]()
    for i in range(M * K):
        x_f32[i] = x_vals[i]
    var w_i8 = w_contents.bitcast[Int8]()
    for i in range(N * K):
        w_i8[i] = w_vals[i]
    var wscale_f32 = wscale_contents.bitcast[Float32]()
    for i in range(N):
        wscale_f32[i] = wscale_vals[i]
    var y_oracle_f32 = y_oracle_contents.bitcast[Float32]()
    var y_mma_f32 = y_mma_contents.bitcast[Float32]()
    for i in range(M * N):
        y_oracle_f32[i] = y_init_vals[i]
        y_mma_f32[i] = y_init_vals[i]

    var descs = _mb_alloc_descriptors(2)
    _mb_set_header(descs, 0, accum_oracle_idx, grid, 256, 7)
    _mb_set_arg_ptr(descs, 0, 0, y_oracle_addr)
    _mb_set_arg_ptr(descs, 0, 1, x_addr)
    _mb_set_arg_ptr(descs, 0, 2, w_addr)
    _mb_set_arg_ptr(descs, 0, 3, wscale_addr)
    _mb_set_arg_int(descs, 0, 4, M)
    _mb_set_arg_int(descs, 0, 5, K)
    _mb_set_arg_int(descs, 0, 6, N)
    _mb_set_header(descs, 1, accum_mma_idx, grid, 256, 7)
    _mb_set_arg_ptr(descs, 1, 0, y_mma_addr)
    _mb_set_arg_ptr(descs, 1, 1, x_addr)
    _mb_set_arg_ptr(descs, 1, 2, w_addr)
    _mb_set_arg_ptr(descs, 1, 3, wscale_addr)
    _mb_set_arg_int(descs, 1, 4, M)
    _mb_set_arg_int(descs, 1, 5, K)
    _mb_set_arg_int(descs, 1, 6, N)

    if _mb_run_token(descs, 2) != 0:
        print("FAIL: accum run_token failed")
        return

    var worst_accum = Float32(0.0)
    for i in range(M * N):
        var d = _abs32(y_oracle_f32[i] - y_mma_f32[i])
        if d > worst_accum:
            worst_accum = d
    print("accum worst |oracle-mma| delta:", worst_accum)

    # --- swiglu test ---
    var w2_vals = List[Int8](capacity=2 * N * K)
    for i in range(2 * N * K):
        w2_vals.append(Int8((i * 13 + 7) % 19) - 9)
    var wscale2_vals = List[Float32](capacity=2 * N)
    for i in range(2 * N):
        wscale2_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))

    var w2_addr: UInt64 = 0
    var w2_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale2_addr: UInt64 = 0
    var wscale2_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var act_oracle_addr: UInt64 = 0
    var act_oracle_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var act_mma_addr: UInt64 = 0
    var act_mma_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    _ = _mb_alloc_buffer(2 * N * K, w2_addr, w2_contents)
    _ = _mb_alloc_buffer(2 * N * 4, wscale2_addr, wscale2_contents)
    _ = _mb_alloc_buffer(M * N * 4, act_oracle_addr, act_oracle_contents)
    _ = _mb_alloc_buffer(M * N * 4, act_mma_addr, act_mma_contents)

    var w2_i8 = w2_contents.bitcast[Int8]()
    for i in range(2 * N * K):
        w2_i8[i] = w2_vals[i]
    var wscale2_f32 = wscale2_contents.bitcast[Float32]()
    for i in range(2 * N):
        wscale2_f32[i] = wscale2_vals[i]

    var descs2 = _mb_alloc_descriptors(2)
    _mb_set_header(descs2, 0, swiglu_oracle_idx, grid, 256, 7)
    _mb_set_arg_ptr(descs2, 0, 0, act_oracle_addr)
    _mb_set_arg_ptr(descs2, 0, 1, x_addr)
    _mb_set_arg_ptr(descs2, 0, 2, w2_addr)
    _mb_set_arg_ptr(descs2, 0, 3, wscale2_addr)
    _mb_set_arg_int(descs2, 0, 4, M)
    _mb_set_arg_int(descs2, 0, 5, K)
    _mb_set_arg_int(descs2, 0, 6, N)
    _mb_set_header(descs2, 1, swiglu_mma_idx, grid, 256, 7)
    _mb_set_arg_ptr(descs2, 1, 0, act_mma_addr)
    _mb_set_arg_ptr(descs2, 1, 1, x_addr)
    _mb_set_arg_ptr(descs2, 1, 2, w2_addr)
    _mb_set_arg_ptr(descs2, 1, 3, wscale2_addr)
    _mb_set_arg_int(descs2, 1, 4, M)
    _mb_set_arg_int(descs2, 1, 5, K)
    _mb_set_arg_int(descs2, 1, 6, N)

    if _mb_run_token(descs2, 2) != 0:
        print("FAIL: swiglu run_token failed")
        return

    var act_oracle_f32 = act_oracle_contents.bitcast[Float32]()
    var act_mma_f32 = act_mma_contents.bitcast[Float32]()
    var worst_swiglu = Float32(0.0)
    for i in range(M * N):
        var d2 = _abs32(act_oracle_f32[i] - act_mma_f32[i])
        if d2 > worst_swiglu:
            worst_swiglu = d2
    print("swiglu worst |oracle-mma| delta:", worst_swiglu)

    if worst_accum <= 0.01 and worst_swiglu <= 0.01:
        print("PHASE 2 CROSS-TOOLCHAIN PROBE: PASS")
    else:
        print("PHASE 2 CROSS-TOOLCHAIN PROBE: FAIL")
