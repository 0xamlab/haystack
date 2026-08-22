"""residentk.kernels_prefill_v2f16 — LEVER L3: the Float16-SIMD-accumulation twins of the
v2 prefill GEMM family (`residentk.kernels_prefill_f32_v2`), for the admission prefill of the
CUDA serve driver. Weight and activation STORAGE stays Float32 (the proven HBM-speed load
path — the probe battery measured every sub-f32 SIMD LOAD scalarized on this backend); the
arithmetic moves to Float16 SIMD: A/B tiles narrow to f16 as they land in shared memory, the
4x4 register-block inner loop accumulates in `SIMD[DType.float16, 4]` accumulators (the f16
SIMD arithmetic rate measured at 60.5 TF/s on this exact A100 by
`benchmarks/llm_smoke/nvidia_race/f16_simd_arith_probe.mojo`, vs 17.6 TF/s f32 SIMD), and
the epilogue widens back to f32. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest
benchmark: benchmarks/llm_smoke/nvidia_race/ttft_probe.py
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states —
leading underscores keep these out of the inventory, the contract, and the generated
dispatch; only the CUDA serve driver reaches them, gated behind its own `-D` flag
(`ALGENTA_PF_F16GEMM`) — and ADOPTION IS GATED by the serve driver's selftest (16/16
campaign oracle + token identity): f16 accumulation trades mantissa (10 bits) over the
k = 1024..3072 dot products, so these kernels are opt-in behind a correctness gate, exactly
as the lever brief states ("adopt ONLY if 16/16 oracle + token identity pass").

PRECISION, STATED HONESTLY: each output accumulates the full k-dot in Float16 — relative
rounding walks ~sqrt(k) x 2^-11 across the sum, i.e. ~1-3% logit error at these shapes.
Whether that flips greedy tokens is an EMPIRICAL question the gate answers per checkpoint;
the f32 v2 family stays the control arm and the default.

STRUCTURE: the v2 family's geometry verbatim (BM=BN=64, BK=16, 4x4 register block, 256
threads, column ownership c = tx + 16*j, weights `[n, k]`) with two deliberate simplifications
for the first cut: NO double buffering (one shared tile per operand, one barrier per k-step —
the f16 inner loop is the variable under test; pipelining is the follow-up if the rate lands)
and f16 shared tiles (half the smem bytes, 10-bit values). Cooperative loads read Float32
float4 from global (the proven path) and narrow into shared.

Mojo 1.0.0 kernel-parameter discipline: every scalar parameter is a fixed-width `Int64`
(DevicePassable), widened back to `Int` once at entry — `accel/launch.mojo`'s pattern.
"""

from std.origin import MutAnyOrigin
from std.gpu import block_idx, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.math import exp
from std.memory import stack_allocation

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels` uses."""

comptime _F16G_BM: Int = 64
comptime _F16G_BN: Int = 64
comptime _F16G_BK: Int = 16
comptime _F16G_TM: Int = 4
comptime _F16G_TN: Int = 4
comptime _F16G_NTHREADS: Int = (_F16G_BM // _F16G_TM) * (_F16G_BN // _F16G_TN)
"""The v2 family's tile geometry, verbatim (64x64 output tile, 16-deep staged k, 4x4
register block, 256 threads)."""

comptime _F16G_APAD: Int = _F16G_BK + 8
"""`a_s` shared row stride in f16 elements: the +8 pad keeps the 4-row register-block stride
(4 x 24 = 96 elems = 192 B = 48 banks) off the same bank set (f16 = 2 B: bank period 128
elems); same fix-class as the f32 family's `_G2_APAD`."""

comptime _F16G_BPAD: Int = _F16G_BN + 8
"""`b_s` shared row stride (transposed tile `[BK][BPAD]`), the f32 family's `_G2_BPAD`
logic in f16 elements."""


def _pf_gemm_assign_kernel_v2f16(
    y: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """f16-accumulation twin of `_pf_gemm_assign_kernel_v2`: `y[M,n] = xn[M,k] @ W^T[k,n]`,
    `w` stored `[n,k]` row-major, ASSIGNING into `y`. Grid contract identical to the v2
    family: `grid_dim = ceil(m/_F16G_BM) * ceil(n/_F16G_BN)`, flattened `(tile_row,
    tile_col)` with `tile_col = block_idx.x % n_tile_cols`."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _F16G_BM
    comptime BN = _F16G_BN
    comptime BK = _F16G_BK
    comptime TM = _F16G_TM
    comptime TN = _F16G_TN
    comptime APAD = _F16G_APAD
    comptime BPAD = _F16G_BPAD

    var a_s = stack_allocation[BM * APAD, DType.float16, address_space = AddressSpace.SHARED]()
    var b_s = stack_allocation[BK * BPAD, DType.float16, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    # Cooperative-load mapping: BM*BK = 1024 f32 elements = one float4 per thread (the v2
    # family's own), narrowed into shared f16.
    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    # f16 SIMD accumulators, one SIMD4 per register row (columns tx, tx+16, tx+32, tx+48).
    var c0 = SIMD[DType.float16, 4](Float16(0.0))
    var c1 = SIMD[DType.float16, 4](Float16(0.0))
    var c2 = SIMD[DType.float16, 4](Float16(0.0))
    var c3 = SIMD[DType.float16, 4](Float16(0.0))

    for step in range(n_steps):
        # ── stage this k-step's A tile [BM, BK] and B tile [BK, BN] (transposed) ──
        var gc = step * BK + lc
        var gr = block_row + lr
        if gr < m_rows and gc + 3 < k:
            var va = xn.load[width=4](gr * k + gc)
            a_s[lr * APAD + lc + 0] = Float16(va[0])
            a_s[lr * APAD + lc + 1] = Float16(va[1])
            a_s[lr * APAD + lc + 2] = Float16(va[2])
            a_s[lr * APAD + lc + 3] = Float16(va[3])
        elif gr < m_rows:
            for e in range(4):
                a_s[lr * APAD + lc + e] = Float16(xn[gr * k + gc + e]) \
                    if gc + e < k else Float16(0.0)
        else:
            for e in range(4):
                a_s[lr * APAD + lc + e] = Float16(0.0)
        var wr = block_col + lr
        if wr < n and gc + 3 < k:
            var vb = w.load[width=4](wr * k + gc)
            b_s[(lc + 0) * BPAD + lr] = Float16(vb[0])
            b_s[(lc + 1) * BPAD + lr] = Float16(vb[1])
            b_s[(lc + 2) * BPAD + lr] = Float16(vb[2])
            b_s[(lc + 3) * BPAD + lr] = Float16(vb[3])
        elif wr < n:
            for e in range(4):
                b_s[(lc + e) * BPAD + lr] = Float16(w[wr * k + gc + e]) \
                    if gc + e < k else Float16(0.0)
        else:
            for e in range(4):
                b_s[(lc + e) * BPAD + lr] = Float16(0.0)
        barrier()

        # ── f16 SIMD inner loop: 4 register rows x SIMD4 columns ──
        for kk in range(BK):
            var b4 = SIMD[DType.float16, 4](
                b_s[kk * BPAD + tx],
                b_s[kk * BPAD + tx + 16],
                b_s[kk * BPAD + tx + 32],
                b_s[kk * BPAD + tx + 48],
            )
            var a0v = SIMD[DType.float16, 4](a_s[(ty * TM + 0) * APAD + kk])
            var a1v = SIMD[DType.float16, 4](a_s[(ty * TM + 1) * APAD + kk])
            var a2v = SIMD[DType.float16, 4](a_s[(ty * TM + 2) * APAD + kk])
            var a3v = SIMD[DType.float16, 4](a_s[(ty * TM + 3) * APAD + kk])
            c0 = a0v * b4 + c0
            c1 = a1v * b4 + c1
            c2 = a2v * b4 + c2
            c3 = a3v * b4 + c3
        barrier()

    # ── epilogue: widen to f32, guarded stores, column ownership c = tx + 16*j ──
    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    var c0f = c0.cast[DType.float32]()
    var c1f = c1.cast[DType.float32]()
    var c2f = c2.cast[DType.float32]()
    var c3f = c3.cast[DType.float32]()
    if r0 < m_rows and cc0 < n:
        y[r0 * n + cc0] = c0f[0]
    if r0 < m_rows and cc1 < n:
        y[r0 * n + cc1] = c0f[1]
    if r0 < m_rows and cc2 < n:
        y[r0 * n + cc2] = c0f[2]
    if r0 < m_rows and cc3 < n:
        y[r0 * n + cc3] = c0f[3]
    if r1 < m_rows and cc0 < n:
        y[r1 * n + cc0] = c1f[0]
    if r1 < m_rows and cc1 < n:
        y[r1 * n + cc1] = c1f[1]
    if r1 < m_rows and cc2 < n:
        y[r1 * n + cc2] = c1f[2]
    if r1 < m_rows and cc3 < n:
        y[r1 * n + cc3] = c1f[3]
    if r2 < m_rows and cc0 < n:
        y[r2 * n + cc0] = c2f[0]
    if r2 < m_rows and cc1 < n:
        y[r2 * n + cc1] = c2f[1]
    if r2 < m_rows and cc2 < n:
        y[r2 * n + cc2] = c2f[2]
    if r2 < m_rows and cc3 < n:
        y[r2 * n + cc3] = c2f[3]
    if r3 < m_rows and cc0 < n:
        y[r3 * n + cc0] = c3f[0]
    if r3 < m_rows and cc1 < n:
        y[r3 * n + cc1] = c3f[1]
    if r3 < m_rows and cc2 < n:
        y[r3 * n + cc2] = c3f[2]
    if r3 < m_rows and cc3 < n:
        y[r3 * n + cc3] = c3f[3]


def _pf_gemm_accum_kernel_v2f16(
    y: _FP, x: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """f16-accumulation twin of `_pf_gemm_accum_kernel_v2`: `y[M,n] += x[M,k] @ W^T[k,n]` —
    the o_proj / down_proj residual-add roles. Byte-for-byte the assign twin's structure
    except the epilogue ACCUMULATES into the f32 residual stream."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _F16G_BM
    comptime BN = _F16G_BN
    comptime BK = _F16G_BK
    comptime TM = _F16G_TM
    comptime TN = _F16G_TN
    comptime APAD = _F16G_APAD
    comptime BPAD = _F16G_BPAD

    var a_s = stack_allocation[BM * APAD, DType.float16, address_space = AddressSpace.SHARED]()
    var b_s = stack_allocation[BK * BPAD, DType.float16, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    var c0 = SIMD[DType.float16, 4](Float16(0.0))
    var c1 = SIMD[DType.float16, 4](Float16(0.0))
    var c2 = SIMD[DType.float16, 4](Float16(0.0))
    var c3 = SIMD[DType.float16, 4](Float16(0.0))

    for step in range(n_steps):
        var gc = step * BK + lc
        var gr = block_row + lr
        if gr < m_rows and gc + 3 < k:
            var va = x.load[width=4](gr * k + gc)
            a_s[lr * APAD + lc + 0] = Float16(va[0])
            a_s[lr * APAD + lc + 1] = Float16(va[1])
            a_s[lr * APAD + lc + 2] = Float16(va[2])
            a_s[lr * APAD + lc + 3] = Float16(va[3])
        elif gr < m_rows:
            for e in range(4):
                a_s[lr * APAD + lc + e] = Float16(x[gr * k + gc + e]) \
                    if gc + e < k else Float16(0.0)
        else:
            for e in range(4):
                a_s[lr * APAD + lc + e] = Float16(0.0)
        var wr = block_col + lr
        if wr < n and gc + 3 < k:
            var vb = w.load[width=4](wr * k + gc)
            b_s[(lc + 0) * BPAD + lr] = Float16(vb[0])
            b_s[(lc + 1) * BPAD + lr] = Float16(vb[1])
            b_s[(lc + 2) * BPAD + lr] = Float16(vb[2])
            b_s[(lc + 3) * BPAD + lr] = Float16(vb[3])
        elif wr < n:
            for e in range(4):
                b_s[(lc + e) * BPAD + lr] = Float16(w[wr * k + gc + e]) \
                    if gc + e < k else Float16(0.0)
        else:
            for e in range(4):
                b_s[(lc + e) * BPAD + lr] = Float16(0.0)
        barrier()

        for kk in range(BK):
            var b4 = SIMD[DType.float16, 4](
                b_s[kk * BPAD + tx],
                b_s[kk * BPAD + tx + 16],
                b_s[kk * BPAD + tx + 32],
                b_s[kk * BPAD + tx + 48],
            )
            var a0v = SIMD[DType.float16, 4](a_s[(ty * TM + 0) * APAD + kk])
            var a1v = SIMD[DType.float16, 4](a_s[(ty * TM + 1) * APAD + kk])
            var a2v = SIMD[DType.float16, 4](a_s[(ty * TM + 2) * APAD + kk])
            var a3v = SIMD[DType.float16, 4](a_s[(ty * TM + 3) * APAD + kk])
            c0 = a0v * b4 + c0
            c1 = a1v * b4 + c1
            c2 = a2v * b4 + c2
            c3 = a3v * b4 + c3
        barrier()

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    var c0f = c0.cast[DType.float32]()
    var c1f = c1.cast[DType.float32]()
    var c2f = c2.cast[DType.float32]()
    var c3f = c3.cast[DType.float32]()
    if r0 < m_rows and cc0 < n:
        y[r0 * n + cc0] = y[r0 * n + cc0] + c0f[0]
    if r0 < m_rows and cc1 < n:
        y[r0 * n + cc1] = y[r0 * n + cc1] + c0f[1]
    if r0 < m_rows and cc2 < n:
        y[r0 * n + cc2] = y[r0 * n + cc2] + c0f[2]
    if r0 < m_rows and cc3 < n:
        y[r0 * n + cc3] = y[r0 * n + cc3] + c0f[3]
    if r1 < m_rows and cc0 < n:
        y[r1 * n + cc0] = y[r1 * n + cc0] + c1f[0]
    if r1 < m_rows and cc1 < n:
        y[r1 * n + cc1] = y[r1 * n + cc1] + c1f[1]
    if r1 < m_rows and cc2 < n:
        y[r1 * n + cc2] = y[r1 * n + cc2] + c1f[2]
    if r1 < m_rows and cc3 < n:
        y[r1 * n + cc3] = y[r1 * n + cc3] + c1f[3]
    if r2 < m_rows and cc0 < n:
        y[r2 * n + cc0] = y[r2 * n + cc0] + c2f[0]
    if r2 < m_rows and cc1 < n:
        y[r2 * n + cc1] = y[r2 * n + cc1] + c2f[1]
    if r2 < m_rows and cc2 < n:
        y[r2 * n + cc2] = y[r2 * n + cc2] + c2f[2]
    if r2 < m_rows and cc3 < n:
        y[r2 * n + cc3] = y[r2 * n + cc3] + c2f[3]
    if r3 < m_rows and cc0 < n:
        y[r3 * n + cc0] = y[r3 * n + cc0] + c3f[0]
    if r3 < m_rows and cc1 < n:
        y[r3 * n + cc1] = y[r3 * n + cc1] + c3f[1]
    if r3 < m_rows and cc2 < n:
        y[r3 * n + cc2] = y[r3 * n + cc2] + c3f[2]
    if r3 < m_rows and cc3 < n:
        y[r3 * n + cc3] = y[r3 * n + cc3] + c3f[3]


def _pf_gemm_swiglu_kernel_v2f16(
    act: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_ff_i64: Int64
):
    """f16-accumulation twin of `_pf_gemm_swiglu_kernel_v2`: `w` is the resident
    `[2*n_ff, k]` gate-THEN-up concatenation; per output column both dots accumulate in f16
    SIMD4 register rows and `act[M,n_ff] = silu(gate) * up` is evaluated in f32 in the
    epilogue (the v2 family's own expression)."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    comptime BM = _F16G_BM
    comptime BN = _F16G_BN
    comptime BK = _F16G_BK
    comptime TM = _F16G_TM
    comptime TN = _F16G_TN
    comptime APAD = _F16G_APAD
    comptime BPAD = _F16G_BPAD

    var a_s = stack_allocation[BM * APAD, DType.float16, address_space = AddressSpace.SHARED]()
    var bg_s = stack_allocation[BK * BPAD, DType.float16, address_space = AddressSpace.SHARED]()
    var bu_s = stack_allocation[BK * BPAD, DType.float16, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n_ff + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    var g0 = SIMD[DType.float16, 4](Float16(0.0))
    var g1 = SIMD[DType.float16, 4](Float16(0.0))
    var g2 = SIMD[DType.float16, 4](Float16(0.0))
    var g3 = SIMD[DType.float16, 4](Float16(0.0))
    var u0 = SIMD[DType.float16, 4](Float16(0.0))
    var u1 = SIMD[DType.float16, 4](Float16(0.0))
    var u2 = SIMD[DType.float16, 4](Float16(0.0))
    var u3 = SIMD[DType.float16, 4](Float16(0.0))

    for step in range(n_steps):
        var gc = step * BK + lc
        var gr = block_row + lr
        if gr < m_rows and gc + 3 < k:
            var va = xn.load[width=4](gr * k + gc)
            a_s[lr * APAD + lc + 0] = Float16(va[0])
            a_s[lr * APAD + lc + 1] = Float16(va[1])
            a_s[lr * APAD + lc + 2] = Float16(va[2])
            a_s[lr * APAD + lc + 3] = Float16(va[3])
        elif gr < m_rows:
            for e in range(4):
                a_s[lr * APAD + lc + e] = Float16(xn[gr * k + gc + e]) \
                    if gc + e < k else Float16(0.0)
        else:
            for e in range(4):
                a_s[lr * APAD + lc + e] = Float16(0.0)
        var wr = block_col + lr
        if wr < n_ff and gc + 3 < k:
            var vg = w.load[width=4](wr * k + gc)
            var vu = w.load[width=4]((n_ff + wr) * k + gc)
            bg_s[(lc + 0) * BPAD + lr] = Float16(vg[0])
            bg_s[(lc + 1) * BPAD + lr] = Float16(vg[1])
            bg_s[(lc + 2) * BPAD + lr] = Float16(vg[2])
            bg_s[(lc + 3) * BPAD + lr] = Float16(vg[3])
            bu_s[(lc + 0) * BPAD + lr] = Float16(vu[0])
            bu_s[(lc + 1) * BPAD + lr] = Float16(vu[1])
            bu_s[(lc + 2) * BPAD + lr] = Float16(vu[2])
            bu_s[(lc + 3) * BPAD + lr] = Float16(vu[3])
        elif wr < n_ff:
            for e in range(4):
                bg_s[(lc + e) * BPAD + lr] = Float16(w[wr * k + gc + e]) \
                    if gc + e < k else Float16(0.0)
                bu_s[(lc + e) * BPAD + lr] = Float16(w[(n_ff + wr) * k + gc + e]) \
                    if gc + e < k else Float16(0.0)
        else:
            for e in range(4):
                bg_s[(lc + e) * BPAD + lr] = Float16(0.0)
                bu_s[(lc + e) * BPAD + lr] = Float16(0.0)
        barrier()

        for kk in range(BK):
            var bg4 = SIMD[DType.float16, 4](
                bg_s[kk * BPAD + tx],
                bg_s[kk * BPAD + tx + 16],
                bg_s[kk * BPAD + tx + 32],
                bg_s[kk * BPAD + tx + 48],
            )
            var bu4 = SIMD[DType.float16, 4](
                bu_s[kk * BPAD + tx],
                bu_s[kk * BPAD + tx + 16],
                bu_s[kk * BPAD + tx + 32],
                bu_s[kk * BPAD + tx + 48],
            )
            var a0v = SIMD[DType.float16, 4](a_s[(ty * TM + 0) * APAD + kk])
            var a1v = SIMD[DType.float16, 4](a_s[(ty * TM + 1) * APAD + kk])
            var a2v = SIMD[DType.float16, 4](a_s[(ty * TM + 2) * APAD + kk])
            var a3v = SIMD[DType.float16, 4](a_s[(ty * TM + 3) * APAD + kk])
            g0 = a0v * bg4 + g0
            g1 = a1v * bg4 + g1
            g2 = a2v * bg4 + g2
            g3 = a3v * bg4 + g3
            u0 = a0v * bu4 + u0
            u1 = a1v * bu4 + u1
            u2 = a2v * bu4 + u2
            u3 = a3v * bu4 + u3
        barrier()

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    var g0f = g0.cast[DType.float32]()
    var g1f = g1.cast[DType.float32]()
    var g2f = g2.cast[DType.float32]()
    var g3f = g3.cast[DType.float32]()
    var u0f = u0.cast[DType.float32]()
    var u1f = u1.cast[DType.float32]()
    var u2f = u2.cast[DType.float32]()
    var u3f = u3.cast[DType.float32]()
    if r0 < m_rows and cc0 < n_ff:
        act[r0 * n_ff + cc0] = (g0f[0] / (Float32(1.0) + exp(-g0f[0]))) * u0f[0]
    if r0 < m_rows and cc1 < n_ff:
        act[r0 * n_ff + cc1] = (g0f[1] / (Float32(1.0) + exp(-g0f[1]))) * u0f[1]
    if r0 < m_rows and cc2 < n_ff:
        act[r0 * n_ff + cc2] = (g0f[2] / (Float32(1.0) + exp(-g0f[2]))) * u0f[2]
    if r0 < m_rows and cc3 < n_ff:
        act[r0 * n_ff + cc3] = (g0f[3] / (Float32(1.0) + exp(-g0f[3]))) * u0f[3]
    if r1 < m_rows and cc0 < n_ff:
        act[r1 * n_ff + cc0] = (g1f[0] / (Float32(1.0) + exp(-g1f[0]))) * u1f[0]
    if r1 < m_rows and cc1 < n_ff:
        act[r1 * n_ff + cc1] = (g1f[1] / (Float32(1.0) + exp(-g1f[1]))) * u1f[1]
    if r1 < m_rows and cc2 < n_ff:
        act[r1 * n_ff + cc2] = (g1f[2] / (Float32(1.0) + exp(-g1f[2]))) * u1f[2]
    if r1 < m_rows and cc3 < n_ff:
        act[r1 * n_ff + cc3] = (g1f[3] / (Float32(1.0) + exp(-g1f[3]))) * u1f[3]
    if r2 < m_rows and cc0 < n_ff:
        act[r2 * n_ff + cc0] = (g2f[0] / (Float32(1.0) + exp(-g2f[0]))) * u2f[0]
    if r2 < m_rows and cc1 < n_ff:
        act[r2 * n_ff + cc1] = (g2f[1] / (Float32(1.0) + exp(-g2f[1]))) * u2f[1]
    if r2 < m_rows and cc2 < n_ff:
        act[r2 * n_ff + cc2] = (g2f[2] / (Float32(1.0) + exp(-g2f[2]))) * u2f[2]
    if r2 < m_rows and cc3 < n_ff:
        act[r2 * n_ff + cc3] = (g2f[3] / (Float32(1.0) + exp(-g2f[3]))) * u2f[3]
    if r3 < m_rows and cc0 < n_ff:
        act[r3 * n_ff + cc0] = (g3f[0] / (Float32(1.0) + exp(-g3f[0]))) * u3f[0]
    if r3 < m_rows and cc1 < n_ff:
        act[r3 * n_ff + cc1] = (g3f[1] / (Float32(1.0) + exp(-g3f[1]))) * u3f[1]
    if r3 < m_rows and cc2 < n_ff:
        act[r3 * n_ff + cc2] = (g3f[2] / (Float32(1.0) + exp(-g3f[2]))) * u3f[2]
    if r3 < m_rows and cc3 < n_ff:
        act[r3 * n_ff + cc3] = (g3f[3] / (Float32(1.0) + exp(-g3f[3]))) * u3f[3]
