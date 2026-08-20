"""
residentk.kernels_prefill_f32 — the Float32-weight prefill kernels the CUDA-native resident
session is built from. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/qwen3_generate_cuda.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states
-------------------------------------------------------------------------------------------
Shader codegen follows the statically REACHABLE call graph at COMPILE time, so a public name here
would put a GPU launch in the generated dispatch's call graph and every build host would start
requiring an accelerator toolchain. Leading underscores keep these out of `apps/runtime/
mojo_inventory.py`'s inventory, out of the contract, and out of the dispatch; `residentk.
session_cuda` (also private) is the only module that reaches them.

What this file is, and why it is NOT a copy of the `_pf_*_i8` family
-----------------------------------------------------------------------
`residentk.kernels` already carries a batched (m_rows > 1) prefill family — the `_pf_*_i8`
weight-quantized kernels the Metal batched-dispatch arm races with. Four of those kernels read
WEIGHTS through the int8-plus-scale storage format (`_pf_embed_rows_kernel_i8`, `_pf_gemm_assign_
kernel_i8`, `_pf_gemm_accum_kernel_i8`, `_pf_gemm_swiglu_kernel_i8`); this file supplies their
Float32-weight twins for the resident Float32 session `residentk.session_cuda` holds, exactly as
`_norm_gemv_kernel` is the Float32 twin of `_norm_gemv_kernel_i8` on the decode side. Same fusion,
same tiled-GEMM structure, same Float32 activation/accumulator discipline — only the resident
weight buffer is `_FP` instead of `_I8P` + scale, with no dequantize step in the tile load.

The other three prefill roles touch NO weight matrix and are therefore weight-dtype-agnostic:
`residentk.session_cuda` dispatches `_pf_rmsnorm_rows_kernel`, `_pf_ropewrt_kernel` and
`_pf_attn_tiled_kernel_simd` from `residentk.kernels` BYTE-UNMODIFIED rather than writing twins —
rule 3's "call it, never copy it", applied inside the package.

The tiled-GEMM constants (`_GEMM_BM`/`_GEMM_BN`/`_GEMM_BK`/`_GEMM_TM`/`_GEMM_TN`/
`_GEMM_NTHREADS`) are likewise imported from `residentk.kernels`, not re-declared: one tile shape
for the whole prefill family. The NARROW-tile variants are deliberately NOT twinned here — their
i8 originals' own module comment documents a live Mojo miscompilation of the narrow+accumulate
combination, and the wide tile is the only shape a Float32 prefill needs while that stands.

Mojo 1.0.0 kernel-parameter discipline
----------------------------------------
Every scalar parameter is a fixed-width `Int64` (DevicePassable), widened back to `Int` once at
entry — `accel/launch.mojo`'s pattern, the same one `residentk.kernels`' own 1.0.0 migration uses.
"""

from std.gpu import block_idx, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp
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

alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]
"""A device Int32 buffer — the resident prompt-token-id buffer's element type."""


def _pf_embed_rows_kernel(
    hidden: _FP, embed: _FP, token_ids: _IP, d_model_i64: Int64, m_rows_i64: Int64
):
    """Float32-weight twin of `_pf_embed_rows_kernel_i8`: gathers `m_rows` embedding rows in ONE
    dispatch. `grid_dim = ceil_div(d_model, _TG) * m_rows`; `block_idx.x` flattens `(unit, m)` as
    `unit = block_idx.x % n_units`, `m = block_idx.x // n_units` — the SAME flattening convention
    the whole prefill family uses. `hidden` is `[m_rows, d_model]` row-major; row `m` is exactly
    what `_embed_row_kernel` would have written for token `token_ids[m]`, independent of every
    other row. The embedding table is NOT transposed (`[vocab, d_model]` serves both the gather
    and the tied lm_head), same as the decode arm.
    """
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
        hidden[m * d_model + i] = embed[token_id * d_model + i]


def _pf_gemm_assign_kernel(
    y: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """Float32-weight twin of `_pf_gemm_assign_kernel_i8`: weight-stationary tiled GEMM
    `y[M,n] = xn[M,k] @ W^T[k,n]`, `w` stored `[n,k]` row-major, ASSIGNING (not accumulating)
    into `y`. Used for the fused QKV projection of the prefill pass — the one projection whose
    output is a fresh buffer every dispatch, so assign beats accumulate.

    Same tiling, same zero-padded partial-tile discipline, same flattened `(tile_row, tile_col)`
    grid as the i8 original's own docstring documents: `n_tile_cols = ceil(n / _GEMM_BN);
    tile_col = block_idx.x % n_tile_cols; tile_row = block_idx.x // n_tile_cols`, `b_tile` stored
    `[BN, BK]` so each lane's cooperative load stays contiguous along `k` in `w`'s `[n,k]` layout.
    The ONLY difference from the i8 twin: the weight tile loads read Float32 directly, no
    per-row-scale dequantize.
    """
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
            b_tile[idx2] = w[gr2 * k + gc2] if (gr2 < n and gc2 < k) else Float32(0.0)

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


def _pf_gemm_accum_kernel(
    y: _FP, x: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """Float32-weight twin of `_pf_gemm_accum_kernel_i8`: `y[M,n] += x[M,k] @ W^T[k,n]`, `w`
    stored `[n,k]` row-major, ACCUMULATING into `y` — the residual-add half of o_proj and
    down_proj, folded into the projection exactly as the decode arm's `_gemv_accum_kernel` folds
    it. Byte-for-byte the same tiled structure as `_pf_gemm_assign_kernel` above except the final
    store is `y[r*n+c] = y[r*n+c] + acc[...]`.
    """
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
            b_tile[idx2] = w[gr2 * k + gc2] if (gr2 < n and gc2 < k) else Float32(0.0)

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


def _pf_gemm_swiglu_kernel(
    act: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_ff_i64: Int64
):
    """Float32-weight twin of `_pf_gemm_swiglu_kernel_i8`: the fused gate/up projection + SwiGLU
    for `m_rows` rows — `w` is the resident `[2 * n_ff, k]` gate-THEN-up concatenation the
    session's upload packs, and `act[M,n_ff] = silu(xn @ W_gate^T) * (xn @ W_up^T)`. Both
    projections run against the SAME staged `a_tile`, so each weight element is read once per row
    tile exactly as the i8 twin's own docstring states; the final store applies the SwiGLU
    pointwise. Float32 weights: the tile loads read directly, no dequantize.
    """
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
                bg_tile[idx2] = w[gr2 * k + gc2]
                bu_tile[idx2] = w[(n_ff + gr2) * k + gc2]
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
