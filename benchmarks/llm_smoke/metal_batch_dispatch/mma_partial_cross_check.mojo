"""mma_partial_cross_check.mojo — cross-toolchain correctness check for the partial-tile M/N fix
(see `mma_forge/mm8.mojo`'s own module docstring), at a genuinely non-32-aligned shape, dispatched
through the SAME production `algenta_run_token()` shim used in production, against the real scalar
oracles. `mma_forge/probes/correctness_probe_partial.mojo` already verified this forge-natively at
seven shapes for all three kernels; this probe re-verifies ONE of those shapes (M=37, the
tile-boundary-straddling case) through the actual cross-compiler blob-extraction path, matching the
discipline `mma_qkv_proj_cross_check.mojo`/`mma_phase2_cross_check.mojo` already established for
the tile-aligned case.

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 ../benchmarks/llm_smoke/metal_batch_dispatch/batch_shim.m -o /tmp/batch_shim.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      clang -c -O2 ../mma_forge/generated/mm8_blob.c -o /tmp/mm8_blob.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I ../mojo/engine \
        ../benchmarks/llm_smoke/metal_batch_dispatch/mma_partial_cross_check.mojo \
        -o /tmp/mma_partial_cross_check \
        -Xlinker /tmp/batch_shim.o -Xlinker /tmp/mm8_blob.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation -Xlinker -framework -Xlinker IOKit
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer pixi run /tmp/mma_partial_cross_check
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
from residentk.kernels import _pf_gemm_assign_kernel_i8, _pf_gemm_accum_kernel_i8, _pf_gemm_swiglu_kernel_i8

comptime M: Int = 37
comptime K: Int = 48
comptime N: Int = 100


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def main() raises:
    from std.gpu.host import DeviceContext
    var cctx = DeviceContext()
    _ = cctx.compile_function[_pf_gemm_assign_kernel_i8]()
    _ = cctx.compile_function[_pf_gemm_accum_kernel_i8]()
    _ = cctx.compile_function[_pf_gemm_swiglu_kernel_i8]()

    var opened = _mb_open_session()
    if opened < 0:
        print("FAIL: algenta_open_session failed, status=", MB_ERR_SESSION_OPEN_FAILED)
        return

    var count = _mb_pipeline_count()
    print("discovered pipelines:", count)
    var assign_oracle = -1
    var assign_mma = -1
    var accum_oracle = -1
    var accum_mma = -1
    var swiglu_oracle = -1
    var swiglu_mma = -1
    for i in range(count):
        var name = String()
        _ = _mb_pipeline_name(i, name)
        if "qkv_proj_gemm_mma8x8" in name:
            assign_mma = i
        elif "gemm_ass" in name:
            assign_oracle = i
        elif "gemm_accum_mma8x8_narrow" in name:
            pass
        elif "gemm_accum_mma8x8" in name:
            accum_mma = i
        elif "gemm_acc" in name:
            accum_oracle = i
        elif "swiglu_gemm_mma8x8" in name:
            swiglu_mma = i
        elif "gemm_swi" in name:
            swiglu_oracle = i

    if (assign_oracle < 0 or assign_mma < 0 or accum_oracle < 0 or accum_mma < 0
            or swiglu_oracle < 0 or swiglu_mma < 0):
        print("FAIL: pipeline not discovered:", assign_oracle, assign_mma, accum_oracle,
              accum_mma, swiglu_oracle, swiglu_mma)
        return

    var xn_vals = List[Float32](capacity=M * K)
    for i in range(M * K):
        xn_vals.append(Float32((i * 7 + 3) % 13) / 6.0 - 1.0)
    var w_vals = List[Int8](capacity=N * K)
    for i in range(N * K):
        w_vals.append(Int8((i * 11 + 5) % 17) - 8)
    var wscale_vals = List[Float32](capacity=N)
    for i in range(N):
        wscale_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))
    var w2_vals = List[Int8](capacity=2 * N * K)
    for i in range(2 * N * K):
        w2_vals.append(Int8((i * 13 + 7) % 19) - 9)
    var wscale2_vals = List[Float32](capacity=2 * N)
    for i in range(2 * N):
        wscale2_vals.append(Float32(0.01) + Float32(i % 5) * Float32(0.001))
    var y_init_vals = List[Float32](capacity=M * N)
    for i in range(M * N):
        y_init_vals.append(Float32((i * 3 + 1) % 9) / 4.0 - 1.0)

    var xn_addr: UInt64 = 0
    var xn_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w_addr: UInt64 = 0
    var w_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale_addr: UInt64 = 0
    var wscale_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var w2_addr: UInt64 = 0
    var w2_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var wscale2_addr: UInt64 = 0
    var wscale2_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_assign_oracle_addr: UInt64 = 0
    var y_assign_oracle_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_assign_mma_addr: UInt64 = 0
    var y_assign_mma_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_accum_oracle_addr: UInt64 = 0
    var y_accum_oracle_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var y_accum_mma_addr: UInt64 = 0
    var y_accum_mma_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var act_oracle_addr: UInt64 = 0
    var act_oracle_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
    var act_mma_addr: UInt64 = 0
    var act_mma_c = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

    _ = _mb_alloc_buffer(M * K * 4, xn_addr, xn_c)
    _ = _mb_alloc_buffer(N * K, w_addr, w_c)
    _ = _mb_alloc_buffer(N * 4, wscale_addr, wscale_c)
    _ = _mb_alloc_buffer(2 * N * K, w2_addr, w2_c)
    _ = _mb_alloc_buffer(2 * N * 4, wscale2_addr, wscale2_c)
    _ = _mb_alloc_buffer(M * N * 4, y_assign_oracle_addr, y_assign_oracle_c)
    _ = _mb_alloc_buffer(M * N * 4, y_assign_mma_addr, y_assign_mma_c)
    _ = _mb_alloc_buffer(M * N * 4, y_accum_oracle_addr, y_accum_oracle_c)
    _ = _mb_alloc_buffer(M * N * 4, y_accum_mma_addr, y_accum_mma_c)
    _ = _mb_alloc_buffer(M * N * 4, act_oracle_addr, act_oracle_c)
    _ = _mb_alloc_buffer(M * N * 4, act_mma_addr, act_mma_c)

    var xn_f32 = xn_c.bitcast[Float32]()
    for i in range(M * K):
        xn_f32[i] = xn_vals[i]
    var w_i8 = w_c.bitcast[Int8]()
    for i in range(N * K):
        w_i8[i] = w_vals[i]
    var wscale_f32 = wscale_c.bitcast[Float32]()
    for i in range(N):
        wscale_f32[i] = wscale_vals[i]
    var w2_i8 = w2_c.bitcast[Int8]()
    for i in range(2 * N * K):
        w2_i8[i] = w2_vals[i]
    var wscale2_f32 = wscale2_c.bitcast[Float32]()
    for i in range(2 * N):
        wscale2_f32[i] = wscale2_vals[i]
    var y_accum_oracle_f32 = y_accum_oracle_c.bitcast[Float32]()
    var y_accum_mma_f32 = y_accum_mma_c.bitcast[Float32]()
    for i in range(M * N):
        y_accum_oracle_f32[i] = y_init_vals[i]
        y_accum_mma_f32[i] = y_init_vals[i]

    var grid = ((M + 31) // 32) * ((N + 31) // 32)

    var descs = _mb_alloc_descriptors(6)
    _mb_set_header(descs, 0, assign_oracle, grid, 256, 7)
    _mb_set_arg_ptr(descs, 0, 0, y_assign_oracle_addr)
    _mb_set_arg_ptr(descs, 0, 1, xn_addr)
    _mb_set_arg_ptr(descs, 0, 2, w_addr)
    _mb_set_arg_ptr(descs, 0, 3, wscale_addr)
    _mb_set_arg_int(descs, 0, 4, M)
    _mb_set_arg_int(descs, 0, 5, K)
    _mb_set_arg_int(descs, 0, 6, N)

    _mb_set_header(descs, 1, assign_mma, grid, 256, 7)
    _mb_set_arg_ptr(descs, 1, 0, y_assign_mma_addr)
    _mb_set_arg_ptr(descs, 1, 1, xn_addr)
    _mb_set_arg_ptr(descs, 1, 2, w_addr)
    _mb_set_arg_ptr(descs, 1, 3, wscale_addr)
    _mb_set_arg_int(descs, 1, 4, M)
    _mb_set_arg_int(descs, 1, 5, K)
    _mb_set_arg_int(descs, 1, 6, N)

    _mb_set_header(descs, 2, accum_oracle, grid, 256, 7)
    _mb_set_arg_ptr(descs, 2, 0, y_accum_oracle_addr)
    _mb_set_arg_ptr(descs, 2, 1, xn_addr)
    _mb_set_arg_ptr(descs, 2, 2, w_addr)
    _mb_set_arg_ptr(descs, 2, 3, wscale_addr)
    _mb_set_arg_int(descs, 2, 4, M)
    _mb_set_arg_int(descs, 2, 5, K)
    _mb_set_arg_int(descs, 2, 6, N)

    _mb_set_header(descs, 3, accum_mma, grid, 256, 7)
    _mb_set_arg_ptr(descs, 3, 0, y_accum_mma_addr)
    _mb_set_arg_ptr(descs, 3, 1, xn_addr)
    _mb_set_arg_ptr(descs, 3, 2, w_addr)
    _mb_set_arg_ptr(descs, 3, 3, wscale_addr)
    _mb_set_arg_int(descs, 3, 4, M)
    _mb_set_arg_int(descs, 3, 5, K)
    _mb_set_arg_int(descs, 3, 6, N)

    _mb_set_header(descs, 4, swiglu_oracle, grid, 256, 7)
    _mb_set_arg_ptr(descs, 4, 0, act_oracle_addr)
    _mb_set_arg_ptr(descs, 4, 1, xn_addr)
    _mb_set_arg_ptr(descs, 4, 2, w2_addr)
    _mb_set_arg_ptr(descs, 4, 3, wscale2_addr)
    _mb_set_arg_int(descs, 4, 4, M)
    _mb_set_arg_int(descs, 4, 5, K)
    _mb_set_arg_int(descs, 4, 6, N)

    _mb_set_header(descs, 5, swiglu_mma, grid, 256, 7)
    _mb_set_arg_ptr(descs, 5, 0, act_mma_addr)
    _mb_set_arg_ptr(descs, 5, 1, xn_addr)
    _mb_set_arg_ptr(descs, 5, 2, w2_addr)
    _mb_set_arg_ptr(descs, 5, 3, wscale2_addr)
    _mb_set_arg_int(descs, 5, 4, M)
    _mb_set_arg_int(descs, 5, 5, K)
    _mb_set_arg_int(descs, 5, 6, N)

    if _mb_run_token(descs, 6) != 0:
        print("FAIL: algenta_run_token failed")
        return

    var y_assign_oracle_f32 = y_assign_oracle_c.bitcast[Float32]()
    var y_assign_mma_f32 = y_assign_mma_c.bitcast[Float32]()
    var act_oracle_f32 = act_oracle_c.bitcast[Float32]()
    var act_mma_f32 = act_mma_c.bitcast[Float32]()

    var worst_assign = Float32(0.0)
    var worst_accum = Float32(0.0)
    var worst_swiglu = Float32(0.0)
    for i in range(M * N):
        var d0 = _abs32(y_assign_oracle_f32[i] - y_assign_mma_f32[i])
        if d0 > worst_assign:
            worst_assign = d0
        var d1 = _abs32(y_accum_oracle_f32[i] - y_accum_mma_f32[i])
        if d1 > worst_accum:
            worst_accum = d1
        var d2 = _abs32(act_oracle_f32[i] - act_mma_f32[i])
        if d2 > worst_swiglu:
            worst_swiglu = d2

    print("M=", M, "K=", K, "N=", N, "(non-32-aligned)")
    print("assign worst |oracle-mma| delta:", worst_assign)
    print("accum  worst |oracle-mma| delta:", worst_accum)
    print("swiglu worst |oracle-mma| delta:", worst_swiglu)
    if worst_assign <= 0.02 and worst_accum <= 0.02 and worst_swiglu <= 0.02:
        print("PARTIAL-TILE CROSS-TOOLCHAIN PROBE: PASS")
    else:
        print("PARTIAL-TILE CROSS-TOOLCHAIN PROBE: FAIL")
