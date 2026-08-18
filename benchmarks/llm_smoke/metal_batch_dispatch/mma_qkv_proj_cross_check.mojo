"""mma_qkv_proj_cross_check.mojo — Phase 1 cross-toolchain correctness check. Dispatches the
scalar oracle `_pf_gemm_assign_kernel_i8` (pinned toolchain, embedded normally) and the new hardware
MMA kernel `_qkv_proj_gemm_mma8x8` (forge toolchain, extracted via `mma_forge/tools/extract_blob.py`
into `mma_forge/generated/mm8_blob.c` and linked in as one more `-Xlinker` object) against IDENTICAL
`(xn, w, wscale)` inputs, through the SAME production `algenta_run_token()` dispatch path, and diffs
their `y` outputs on the host. `xn` is fed directly (no RMSNorm prerequisite) since this checks only
the GEMM math both kernels share, not the full prefill pipeline.

M=64, K=48, N=64 -- multi-tile in M and N (2x2 grid of BM=32/BN=32 tiles) and multi-step in K (3
steps of BK=16), so both the grid-tiling and K-accumulation paths are real, not vacuous. Both
kernels currently require M/N to be exact multiples of 32 (Phase 1 scope, see `mma_forge/mm8.mojo`'s
own docstring) -- this shape satisfies that for both.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_qkv_proj_cross_check.mojo \
        -o /tmp/mma_qkv_proj_cross_check \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o \
        -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/mma_qkv_proj_cross_check
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
from residentk.kernels import _pf_gemm_assign_kernel_i8

comptime M: Int = 64
comptime K: Int = 48
comptime N: Int = 64


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def main() raises:
    from max.gpu.host import DeviceContext
    var cctx = DeviceContext()
    _ = cctx.compile_function[_pf_gemm_assign_kernel_i8]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    print("discovered pipelines:", count)
    var oracle_idx = -1
    var mma_idx = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        print(" [", i, "]", name)
        if "gemm_ass" in name:
            oracle_idx = i
        if "qkv_proj_gemm_mma8x8" in name:
            mma_idx = i

    if oracle_idx < 0:
        print("FAIL: scalar oracle pipeline not discovered")
        return
    if mma_idx < 0:
        print("FAIL: MMA kernel pipeline not discovered -- extraction/relink mechanism broken")
        return
    print("oracle_idx =", oracle_idx, " mma_idx =", mma_idx)

    var xn_vals = List[Float32](capacity=M * K)
    for i in range(M * K):
        xn_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=N * K)
    for i in range(N * K):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=N)
    for i in range(N):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))

    var xn_addr: UInt64 = 0
    var xn_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w_addr: UInt64 = 0
    var w_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale_addr: UInt64 = 0
    var wscale_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_oracle_addr: UInt64 = 0
    var y_oracle_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_mma_addr: UInt64 = 0
    var y_mma_contents = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    if _mb_alloc_buffer(M * K * 4, xn_addr, xn_contents) < 0:
        print("FAIL: alloc xn")
        return
    if _mb_alloc_buffer(N * K, w_addr, w_contents) < 0:
        print("FAIL: alloc w")
        return
    if _mb_alloc_buffer(N * 4, wscale_addr, wscale_contents) < 0:
        print("FAIL: alloc wscale")
        return
    if _mb_alloc_buffer(M * N * 4, y_oracle_addr, y_oracle_contents) < 0:
        print("FAIL: alloc y_oracle")
        return
    if _mb_alloc_buffer(M * N * 4, y_mma_addr, y_mma_contents) < 0:
        print("FAIL: alloc y_mma")
        return

    var xn_f32 = xn_contents.bitcast[Float32]()
    for i in range(M * K):
        xn_f32[i] = xn_vals[i]
    var w_i8 = w_contents.bitcast[Int8]()
    for i in range(N * K):
        w_i8[i] = w_vals[i]
    var wscale_f32 = wscale_contents.bitcast[Float32]()
    for i in range(N):
        wscale_f32[i] = wscale_vals[i]

    var n_tile_cols = (N + 32 - 1) // 32
    var n_tile_rows = (M + 32 - 1) // 32
    var grid = n_tile_cols * n_tile_rows

    var descs = _mb_alloc_descriptors(2)
    _mb_set_header(descs, 0, oracle_idx, grid, 256, 7)
    _mb_set_arg_ptr(descs, 0, 0, y_oracle_addr)
    _mb_set_arg_ptr(descs, 0, 1, xn_addr)
    _mb_set_arg_ptr(descs, 0, 2, w_addr)
    _mb_set_arg_ptr(descs, 0, 3, wscale_addr)
    _mb_set_arg_int(descs, 0, 4, M)
    _mb_set_arg_int(descs, 0, 5, K)
    _mb_set_arg_int(descs, 0, 6, N)

    _mb_set_header(descs, 1, mma_idx, grid, 256, 7)
    _mb_set_arg_ptr(descs, 1, 0, y_mma_addr)
    _mb_set_arg_ptr(descs, 1, 1, xn_addr)
    _mb_set_arg_ptr(descs, 1, 2, w_addr)
    _mb_set_arg_ptr(descs, 1, 3, wscale_addr)
    _mb_set_arg_int(descs, 1, 4, M)
    _mb_set_arg_int(descs, 1, 5, K)
    _mb_set_arg_int(descs, 1, 6, N)

    if _mb_run_token(descs, 2) != 0:
        print("FAIL: algenta_run_token failed")
        return

    var y_oracle_f32 = y_oracle_contents.bitcast[Float32]()
    var y_mma_f32 = y_mma_contents.bitcast[Float32]()
    var worst = Float32(0.0)
    for i in range(M * N):
        var d = _abs32(y_oracle_f32[i] - y_mma_f32[i])
        if d > worst:
            worst = d
        if d > 0.01:
            print("MISMATCH at", i, ": oracle", y_oracle_f32[i], "mma", y_mma_f32[i])

    print("oracle[5] =", y_oracle_f32[5], " mma[5] =", y_mma_f32[5])
    print("worst |oracle-mma| delta:", worst)
    if worst <= 0.01:
        print("CROSS-TOOLCHAIN PROBE: PASS -- real hardware MMA kernel matches scalar oracle")
    else:
        print("CROSS-TOOLCHAIN PROBE: FAIL")
