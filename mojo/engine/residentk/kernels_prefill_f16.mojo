"""
residentk.kernels_prefill_f16 — the Float16-weight prefill kernels the CUDA-native F16 resident
session is built from. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/qwen3_generate_cuda.mojo
benchmark: benchmarks/llm_smoke/qwen3_bench_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states
-------------------------------------------------------------------------------------------
Leading underscores keep these out of `apps/runtime/mojo_inventory.py`'s inventory, out of the
contract, and out of the generated dispatch; `residentk.session_cuda_f16` (also private) is the
only module that reaches them.

What this file is: the WIDEN-AT-LOAD twins of `residentk.kernels_prefill_f32`'s four
weight-reading prefill kernels. Tiling, grid flattening, zero-padded partial tiles, accumulator
discipline — all byte-for-byte the f32 originals; the ONLY difference is the weight tile loads
read Float16 and widen to Float32 the instant they land in the shared tile, so every accumulate
stays Float32 (the same mixed-precision contract the decode arm's f16 twins document: storage
shrinks, arithmetic does not). The three weightless prefill roles (rmsnorm-rows, ropewrt,
tiled attention) are dtype-agnostic on activations and are dispatched from `residentk.kernels`
BYTE-UNMODIFIED by the f16 session, exactly as the f32 session does.

Why these exist at all (measured, not assumed)
-----------------------------------------------
The A100 kernel sweep (REALRACE_RESULTS.md 2026-08-20) put the f32 prefill tiled GEMMs at
1.7-3.0% of FP32 SIMT peak, and the race decode arm's GEMV family at the f32 bandwidth floor —
halving the weight BYTES is the only way to move either without tensor cores; this file is the
prefill half of that halving for the format-fair F16-vs-F16 race arm.

Mojo 1.0.0 kernel-parameter discipline
----------------------------------------
Every scalar parameter is a fixed-width `Int64` (DevicePassable), widened back to `Int` once at
entry — `accel/launch.mojo`'s pattern, the same one `residentk.kernels`' own 1.0.0 migration uses.
"""

from std.origin import MutAnyOrigin  # Mojo 1.0.0: origins left std.builtin.type_aliases
from std.gpu import block_idx, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.math import exp
from std.memory import stack_allocation
from residentk.kernels import (
    _TG,
    _GEMM_BM,
    _GEMM_BN,
    _GEMM_BK,
    _GEMM_TM,
    _GEMM_TN,
    _GEMM_NTHREADS,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels` uses."""

alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
"""A device Float16 buffer — the weight-storage type of this arm (activations stay _FP)."""

alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]
"""A device Int32 buffer — the resident prompt-token-id buffer's element type."""


def _pf_embed_rows_kernel_f16(
    hidden: _FP, embed: _HP, token_ids: _IP, d_model_i64: Int64, m_rows_i64: Int64
):
    """Float16-weight twin of `_pf_embed_rows_kernel`: gathers `m_rows` embedding rows from the
    Float16 tied table, widening each element to Float32 as it lands in `hidden` (activations
    stay Float32 throughout the arm). Same grid flattening and row-independence as the f32
    original's own docstring documents."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var d_model = Int(d_model_i64)
    var m_rows = Int(m_rows_i64)
    var n_units = (d_model + _TG - 1) // _TG
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var i = unit * _TG + Int(thread_idx.x)
    if i < d_model:
        var token_id = Int(token_ids[m])
        hidden[m * d_model + i] = Float32(embed[token_id * d_model + i])


def _pf_gemm_assign_kernel_f16(
    y: _FP, xn: _FP, w: _HP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """Float16-weight twin of `_pf_gemm_assign_kernel`: same weight-stationary tiled GEMM
    `y[M,n] = xn[M,k] @ W^T[k,n]` ASSIGNING into `y`; the weight tile loads read Float16 and
    widen into the shared tile, so the accumulate loop is byte-for-byte the f32 original."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _GEMM_BM
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_b = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc[i] = 0.0

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = xn[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            b_tile[idx2] = Float32(w[gr2 * k + gc2]) if (gr2 < n and gc2 < k) else Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_b[j2] = b_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc[i2 * TN + j2] += reg_a[i2] * reg_b[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n:
                y[r * n + c] = acc[i2 * TN + j2]


def _pf_gemm_accum_kernel_f16(
    y: _FP, x: _FP, w: _HP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """Float16-weight twin of `_pf_gemm_accum_kernel`: `y[M,n] += x[M,k] @ W^T[k,n]`
    ACCUMULATING into `y` (the residual-add half of o_proj and down_proj); weight tile loads
    widen Float16 -> Float32 at load, everything else byte-for-byte the f32 original."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _GEMM_BM
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var b_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_b = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc[i] = 0.0

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = x[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            b_tile[idx2] = Float32(w[gr2 * k + gc2]) if (gr2 < n and gc2 < k) else Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_b[j2] = b_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc[i2 * TN + j2] += reg_a[i2] * reg_b[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n:
                y[r * n + c] = y[r * n + c] + acc[i2 * TN + j2]


def _pf_gemm_swiglu_kernel_f16(
    act: _FP, xn: _FP, w: _HP, m_rows_i64: Int64, k_i64: Int64, n_ff_i64: Int64
):
    """Float16-weight twin of `_pf_gemm_swiglu_kernel`: fused gate/up + SwiGLU for `m_rows`
    rows against the resident `[2 * n_ff, k]` Float16 concatenation; both weight tile loads
    widen Float16 -> Float32 at load, everything else byte-for-byte the f32 original."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    comptime BM = _GEMM_BM
    comptime BN = _GEMM_BN
    comptime BK = _GEMM_BK
    comptime TM = _GEMM_TM
    comptime TN = _GEMM_TN
    comptime NTHREADS = _GEMM_NTHREADS

    var a_tile = stack_allocation[BM * BK, DType.float32, address_space = AddressSpace.SHARED]()
    var bg_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var bu_tile = stack_allocation[BK * BN, DType.float32, address_space = AddressSpace.SHARED]()
    var acc_g = stack_allocation[TM * TN, DType.float32]()
    var acc_u = stack_allocation[TM * TN, DType.float32]()
    var reg_a = stack_allocation[TM, DType.float32]()
    var reg_bg = stack_allocation[TN, DType.float32]()
    var reg_bu = stack_allocation[TN, DType.float32]()

    for i in range(TM * TN):
        acc_g[i] = 0.0
        acc_u[i] = 0.0

    var n_tile_cols = (n_ff + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var n_steps = (k + BK - 1) // BK
    for step in range(n_steps):
        for s in range(BM * BK // NTHREADS):
            var idx = tid + s * NTHREADS
            var ar = idx // BK
            var ac = idx % BK
            var gr = block_row + ar
            var gc = step * BK + ac
            a_tile[idx] = xn[gr * k + gc] if (gr < m_rows and gc < k) else Float32(0.0)
        for s in range(BN * BK // NTHREADS):
            var idx2 = tid + s * NTHREADS
            var br = idx2 // BK
            var bc = idx2 % BK
            var gr2 = block_col + br
            var gc2 = step * BK + bc
            if gr2 < n_ff and gc2 < k:
                bg_tile[idx2] = Float32(w[gr2 * k + gc2])
                bu_tile[idx2] = Float32(w[(n_ff + gr2) * k + gc2])
            else:
                bg_tile[idx2] = Float32(0.0)
                bu_tile[idx2] = Float32(0.0)

        barrier()

        for kk in range(BK):
            for i2 in range(TM):
                reg_a[i2] = a_tile[(ty * TM + i2) * BK + kk]
            for j2 in range(TN):
                reg_bg[j2] = bg_tile[(tx * TN + j2) * BK + kk]
                reg_bu[j2] = bu_tile[(tx * TN + j2) * BK + kk]
            for i2 in range(TM):
                for j2 in range(TN):
                    acc_g[i2 * TN + j2] += reg_a[i2] * reg_bg[j2]
                    acc_u[i2 * TN + j2] += reg_a[i2] * reg_bu[j2]

        barrier()

    for i2 in range(TM):
        for j2 in range(TN):
            var r = block_row + ty * TM + i2
            var c = block_col + tx * TN + j2
            if r < m_rows and c < n_ff:
                var g = acc_g[i2 * TN + j2]
                var u = acc_u[i2 * TN + j2]
                act[r * n_ff + c] = (g / (1.0 + exp(-g))) * u
