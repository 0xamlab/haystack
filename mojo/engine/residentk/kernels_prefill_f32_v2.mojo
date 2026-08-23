"""
residentk.kernels_prefill_f32_v2 — the SECOND-GENERATION Float32-weight prefill GEMM kernels:
register-blocked 4x4, software-pipelined (double-buffered shared tiles), vectorized float4
global loads, bank-conflict-padded shared layouts. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/prefill_gemm_probe.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/prefill_gemm_probe.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` and
`residentk.kernels_prefill_f32` state: shader codegen follows the statically REACHABLE call
graph at COMPILE time, so a public name here would put a GPU launch in the generated dispatch's
call graph. Leading underscores keep these out of the inventory, the contract, and the dispatch;
`residentk.session_cuda` is the only module that reaches them.

WHY THIS FILE EXISTS — the measured gap it attacks
----------------------------------------------------
The kernel-by-kernel sweep on the A100-SXM4-40GB (REALRACE_RESULTS.md, "LEVER 3a VERIFIED")
measured the first-generation prefill tiled GEMMs (`residentk.kernels_prefill_f32`) at 1.7-3.0%
of the A100's 19.5 TFLOP/s FP32 SIMT peak at the real layer shapes — a 5-10x measured headroom
INSIDE f32 SIMT, before any format question. The first-generation kernel's structure names the
losses: a 32x32 output tile with a 2x2 register block per thread (4 FMAs per k-step against 4
shared loads = a 1:1 FMA:LDS instruction mix), scalar 4-byte global loads, and TWO barriers per
16-deep k-step with the next tile's HBM latency fully exposed.

This file's answer, mechanism by mechanism
-------------------------------------------
* REGISTER BLOCK 4x4 on a 64x64 output tile, 256 threads: each thread owns 16 accumulator
  scalars (declared as 16 explicit `var`s — never an indexed array — so codegen has NO choice
  but to keep them in registers) and issues 16 FMAs per k-step against 8 shared loads (4 A +
  4 B) — a 2:1 FMA:LDS mix instead of 1:1.
* SOFTWARE PIPELINING (double buffering): two shared copies of each tile; while the current
  tile is consumed, the NEXT tile's global loads are in flight into the other copy. One barrier
  per k-step serves both directions (it releases the consumed tile for overwrite AND publishes
  the prefetched tile), where the first generation used two barriers and hid nothing.
* VECTORIZED GLOBAL LOADS: exactly one `load[width=4]` (128-bit float4) per thread per tile per
  step — the same `UnsafePointer.load[width=N]` idiom the decode GEMV family's HBM-peak runs use
  (probe battery: Float32 vector loads are the ONLY SIMD loads that stream at HBM speed on the
  Mojo 1.0.0 / MAX 26.5 CUDA backend, so this kernel stays inside that proven surface).
* BANK-CONFLICT-AWARE SHARED LAYOUT: `a_s` stored row-major with row stride `_G2_APAD = BK + 4`
  (the +4 pad moves the 4-row register-block stride off the same bank set); `b_s` stored
  TRANSPOSED (`[BK][BN + 1]`) so (a) the inner loop's per-thread B reads hit consecutive banks
  (a thread's four register columns are tx, tx+16, tx+32, tx+48 — 16 distinct banks per load
  instruction), and (b) the cooperative float4 loads from `w`'s `[n, k]` layout scatter-write
  into distinct banks (stride BPAD = 65 = 1 mod 32).
* COLUMN OWNERSHIP `c = tx + 16*j` (stride BN/TN across the tile instead of consecutive):
  this is what makes the B reads conflict-free under the transposed layout, and it costs
  nothing in the epilogue (guarded scalar stores).

Same math, same accumulation ORDER as the first generation: each output element accumulates
k = 0..K-1 in ascending order, step-major — so the only numerical difference vs the baseline is
codegen-level (FMA contraction), bounded to ulps; the probe gate (max relative difference vs the
baseline kernel on real weights) and the session's 16/16 greedy oracle are the acceptance test.

Shapes served (Qwen3-0.6B, all probed): qkv M=128 K=1024 N=4096; o_proj M=128 K=2048 N=1024;
gate/up M=128 K=1024 N=3072 (paired); down M=128 K=3072 N=1024. K is a multiple of `_G2_BK` and
N a multiple of `_G2_BN` at every one of these (the vector-load fast path relies on it; a scalar
guarded tail keeps the kernel correct off-divisibility, same contract as the first generation).
M is arbitrary — the prompt's final chunk can be any row count, and every load/store guards it.

Mojo 1.0.0 kernel-parameter discipline
----------------------------------------
Every scalar parameter is a fixed-width `Int64` (DevicePassable), widened back to `Int` once at
entry — `accel/launch.mojo`'s pattern, the same one `residentk.kernels` uses.
"""

from std.gpu import block_idx, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp

from residentk.loadvec import _ld4
alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels` uses."""

comptime _G2_BM: Int = 64
"""Rows of C one block computes. 64 = 2x the first generation's 32: with CUDA_PREFILL_TILE = 128
a full chunk is exactly two row-tiles, and 64 rows amortize each weight tile's loads over twice
the arithmetic while still leaving enough row-tiles x col-tiles to fill 108 SMs at this model's
N values (qkv: 2 x 64 = 128 blocks; gu: 2 x 48 = 96; o/down: 2 x 16 = 32 — the narrow-N roles
underfill at this tile and are the probe's named follow-up if their share stays dominant)."""

comptime _G2_BN: Int = 64
"""Columns of C one block computes. 64 keeps the block square (the register block and the
cooperative-load mapping are symmetric in M/N except the weight layout) and keeps the shared
footprint of the double-buffered pair small enough for several resident blocks per SM."""

comptime _G2_BK: Int = 16
"""K-depth of one staged tile. 16 = exactly one float4 per thread per tile (BM*BK = 1024
elements / 256 threads / 4 wide), so the cooperative load is ONE 128-bit load instruction per
thread per tile — no load loop, no per-thread loop-carried address arithmetic."""

comptime _G2_TM: Int = 4
comptime _G2_TN: Int = 4
"""The per-thread register block: 4 rows x 4 cols = 16 accumulator scalars, 16 FMAs per k-step."""

comptime _G2_NTHREADS: Int = (_G2_BM // _G2_TM) * (_G2_BN // _G2_TN)
"""256 threads = 8 warps, derived from the tile and the register block exactly the way the first
generation's `_GEMM_NTHREADS` is (never a magic constant)."""

comptime _G2_APAD: Int = _G2_BK + 4
"""`a_s` shared row stride. The +4 pad is the bank-conflict fix: a warp's A read for one register
row touches TWO tile rows `4*ty + i` and `4*(ty+1) + i` (the warp spans two `ty` values); at
stride BK = 16 those rows are 64 floats = 0 mod 32 banks apart (same bank set, guaranteed
conflict), at stride 20 they are 80 = 16 mod 32 apart (distinct banks)."""

comptime _G2_BPAD: Int = _G2_BN + 1
"""`b_s` shared row stride (the transposed tile is `[BK][BPAD]`). 65 = 1 mod 32 makes the
cooperative scatter-writes (four consecutive k-values of one weight row) hit four distinct
banks, and leaves the inner-loop reads `b_s[kk*BPAD + tx + 16*j]` on 16 distinct banks per load
instruction for fixed kk and j."""


def _pf_gemm_assign_kernel_v2(
    y: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """Register-blocked, double-buffered, float4-loaded drop-in for `_pf_gemm_assign_kernel`:
    `y[M,n] = xn[M,k] @ W^T[k,n]`, `w` stored `[n,k]` row-major, ASSIGNING into `y`. Fused QKV
    projection of the prefill pass. Grid contract is UNCHANGED except the tile constants:
    `grid_dim = ceil(m/_G2_BM) * ceil(n/_G2_BN)`, flattened `(tile_row, tile_col)` with
    `tile_col = block_idx.x % n_tile_cols` — the same flattening the whole prefill family uses.
    """
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G2_BM
    comptime BN = _G2_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime NTHREADS = _G2_NTHREADS
    comptime APAD = _G2_APAD
    comptime BPAD = _G2_BPAD

    # Double-buffered shared tiles: `a_s` row-major `[BM][APAD]`, `b_s` TRANSPOSED `[BK][BPAD]`.
    var a0 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var a1 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    # Cooperative-load mapping: BM*BK = 1024 elements = one float4 per thread, no loop.
    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    # 16 explicit accumulator scalars — registers by construction.
    var c00 = Float32(0.0)
    var c01 = Float32(0.0)
    var c02 = Float32(0.0)
    var c03 = Float32(0.0)
    var c10 = Float32(0.0)
    var c11 = Float32(0.0)
    var c12 = Float32(0.0)
    var c13 = Float32(0.0)
    var c20 = Float32(0.0)
    var c21 = Float32(0.0)
    var c22 = Float32(0.0)
    var c23 = Float32(0.0)
    var c30 = Float32(0.0)
    var c31 = Float32(0.0)
    var c32 = Float32(0.0)
    var c33 = Float32(0.0)

    # ── prologue: stage step 0 into buffer 0 ──
    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = _ld4(xn, gr0 * k + lc)
        a0[lr * APAD + lc + 0] = va[0]
        a0[lr * APAD + lc + 1] = va[1]
        a0[lr * APAD + lc + 2] = va[2]
        a0[lr * APAD + lc + 3] = va[3]
    elif gr0 < m_rows:
        for e in range(4):
            a0[lr * APAD + lc + e] = xn[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            a0[lr * APAD + lc + e] = Float32(0.0)
    var wr0 = block_col + lr
    if wr0 < n and lc + 3 < k:
        var vb = _ld4(w, wr0 * k + lc)
        b0[(lc + 0) * BPAD + lr] = vb[0]
        b0[(lc + 1) * BPAD + lr] = vb[1]
        b0[(lc + 2) * BPAD + lr] = vb[2]
        b0[(lc + 3) * BPAD + lr] = vb[3]
    elif wr0 < n:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = w[wr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = Float32(0.0)
    barrier()

    var cur = 0
    for step in range(n_steps):
        # ── prefetch step+1 into the buffer NOT being consumed ──
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            var agr = block_row + lr
            if cur == 0:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a1[lr * APAD + lc + 0] = va[0]
                    a1[lr * APAD + lc + 1] = va[1]
                    a1[lr * APAD + lc + 2] = va[2]
                    a1[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = _ld4(w, wgr * k + ngc)
                    b1[(lc + 0) * BPAD + lr] = vb[0]
                    b1[(lc + 1) * BPAD + lr] = vb[1]
                    b1[(lc + 2) * BPAD + lr] = vb[2]
                    b1[(lc + 3) * BPAD + lr] = vb[3]
                elif wgr < n:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = Float32(0.0)
            else:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a0[lr * APAD + lc + 0] = va[0]
                    a0[lr * APAD + lc + 1] = va[1]
                    a0[lr * APAD + lc + 2] = va[2]
                    a0[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = _ld4(w, wgr * k + ngc)
                    b0[(lc + 0) * BPAD + lr] = vb[0]
                    b0[(lc + 1) * BPAD + lr] = vb[1]
                    b0[(lc + 2) * BPAD + lr] = vb[2]
                    b0[(lc + 3) * BPAD + lr] = vb[3]
                elif wgr < n:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = Float32(0.0)

        # ── consume the current buffer: 4x4 register block, 16 FMAs per k-step ──
        var acur = a0 if cur == 0 else a1
        var bcur = b0 if cur == 0 else b1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xb0 = bcur[kk * BPAD + tx]
            var xb1 = bcur[kk * BPAD + tx + 16]
            var xb2 = bcur[kk * BPAD + tx + 32]
            var xb3 = bcur[kk * BPAD + tx + 48]
            c00 += xa0 * xb0
            c01 += xa0 * xb1
            c02 += xa0 * xb2
            c03 += xa0 * xb3
            c10 += xa1 * xb0
            c11 += xa1 * xb1
            c12 += xa1 * xb2
            c13 += xa1 * xb3
            c20 += xa2 * xb0
            c21 += xa2 * xb1
            c22 += xa2 * xb2
            c23 += xa2 * xb3
            c30 += xa3 * xb0
            c31 += xa3 * xb1
            c32 += xa3 * xb2
            c33 += xa3 * xb3
        barrier()
        cur = 1 - cur

    # ── epilogue: 16 guarded stores, column ownership c = tx + 16*j ──
    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    if r0 < m_rows and cc0 < n:
        y[r0 * n + cc0] = c00
    if r0 < m_rows and cc1 < n:
        y[r0 * n + cc1] = c01
    if r0 < m_rows and cc2 < n:
        y[r0 * n + cc2] = c02
    if r0 < m_rows and cc3 < n:
        y[r0 * n + cc3] = c03
    if r1 < m_rows and cc0 < n:
        y[r1 * n + cc0] = c10
    if r1 < m_rows and cc1 < n:
        y[r1 * n + cc1] = c11
    if r1 < m_rows and cc2 < n:
        y[r1 * n + cc2] = c12
    if r1 < m_rows and cc3 < n:
        y[r1 * n + cc3] = c13
    if r2 < m_rows and cc0 < n:
        y[r2 * n + cc0] = c20
    if r2 < m_rows and cc1 < n:
        y[r2 * n + cc1] = c21
    if r2 < m_rows and cc2 < n:
        y[r2 * n + cc2] = c22
    if r2 < m_rows and cc3 < n:
        y[r2 * n + cc3] = c23
    if r3 < m_rows and cc0 < n:
        y[r3 * n + cc0] = c30
    if r3 < m_rows and cc1 < n:
        y[r3 * n + cc1] = c31
    if r3 < m_rows and cc2 < n:
        y[r3 * n + cc2] = c32
    if r3 < m_rows and cc3 < n:
        y[r3 * n + cc3] = c33


def _pf_gemm_accum_kernel_v2(
    y: _FP, x: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """Register-blocked, double-buffered, float4-loaded drop-in for `_pf_gemm_accum_kernel`:
    `y[M,n] += x[M,k] @ W^T[k,n]` — the residual-add half of o_proj and down_proj. Byte-for-byte
    the same structure as `_pf_gemm_assign_kernel_v2` above except the epilogue ACCUMULATES
    (`y[r*n+c] = y[r*n+c] + cIJ`).
    """
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G2_BM
    comptime BN = _G2_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime NTHREADS = _G2_NTHREADS
    comptime APAD = _G2_APAD
    comptime BPAD = _G2_BPAD

    var a0 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var a1 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()

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

    var c00 = Float32(0.0)
    var c01 = Float32(0.0)
    var c02 = Float32(0.0)
    var c03 = Float32(0.0)
    var c10 = Float32(0.0)
    var c11 = Float32(0.0)
    var c12 = Float32(0.0)
    var c13 = Float32(0.0)
    var c20 = Float32(0.0)
    var c21 = Float32(0.0)
    var c22 = Float32(0.0)
    var c23 = Float32(0.0)
    var c30 = Float32(0.0)
    var c31 = Float32(0.0)
    var c32 = Float32(0.0)
    var c33 = Float32(0.0)

    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = _ld4(x, gr0 * k + lc)
        a0[lr * APAD + lc + 0] = va[0]
        a0[lr * APAD + lc + 1] = va[1]
        a0[lr * APAD + lc + 2] = va[2]
        a0[lr * APAD + lc + 3] = va[3]
    elif gr0 < m_rows:
        for e in range(4):
            a0[lr * APAD + lc + e] = x[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            a0[lr * APAD + lc + e] = Float32(0.0)
    var wr0 = block_col + lr
    if wr0 < n and lc + 3 < k:
        var vb = _ld4(w, wr0 * k + lc)
        b0[(lc + 0) * BPAD + lr] = vb[0]
        b0[(lc + 1) * BPAD + lr] = vb[1]
        b0[(lc + 2) * BPAD + lr] = vb[2]
        b0[(lc + 3) * BPAD + lr] = vb[3]
    elif wr0 < n:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = w[wr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = Float32(0.0)
    barrier()

    var cur = 0
    for step in range(n_steps):
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            var agr = block_row + lr
            if cur == 0:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(x, agr * k + ngc)
                    a1[lr * APAD + lc + 0] = va[0]
                    a1[lr * APAD + lc + 1] = va[1]
                    a1[lr * APAD + lc + 2] = va[2]
                    a1[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = x[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = _ld4(w, wgr * k + ngc)
                    b1[(lc + 0) * BPAD + lr] = vb[0]
                    b1[(lc + 1) * BPAD + lr] = vb[1]
                    b1[(lc + 2) * BPAD + lr] = vb[2]
                    b1[(lc + 3) * BPAD + lr] = vb[3]
                elif wgr < n:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = Float32(0.0)
            else:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(x, agr * k + ngc)
                    a0[lr * APAD + lc + 0] = va[0]
                    a0[lr * APAD + lc + 1] = va[1]
                    a0[lr * APAD + lc + 2] = va[2]
                    a0[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = x[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = _ld4(w, wgr * k + ngc)
                    b0[(lc + 0) * BPAD + lr] = vb[0]
                    b0[(lc + 1) * BPAD + lr] = vb[1]
                    b0[(lc + 2) * BPAD + lr] = vb[2]
                    b0[(lc + 3) * BPAD + lr] = vb[3]
                elif wgr < n:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = Float32(0.0)

        var acur = a0 if cur == 0 else a1
        var bcur = b0 if cur == 0 else b1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xb0 = bcur[kk * BPAD + tx]
            var xb1 = bcur[kk * BPAD + tx + 16]
            var xb2 = bcur[kk * BPAD + tx + 32]
            var xb3 = bcur[kk * BPAD + tx + 48]
            c00 += xa0 * xb0
            c01 += xa0 * xb1
            c02 += xa0 * xb2
            c03 += xa0 * xb3
            c10 += xa1 * xb0
            c11 += xa1 * xb1
            c12 += xa1 * xb2
            c13 += xa1 * xb3
            c20 += xa2 * xb0
            c21 += xa2 * xb1
            c22 += xa2 * xb2
            c23 += xa2 * xb3
            c30 += xa3 * xb0
            c31 += xa3 * xb1
            c32 += xa3 * xb2
            c33 += xa3 * xb3
        barrier()
        cur = 1 - cur

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    if r0 < m_rows and cc0 < n:
        y[r0 * n + cc0] = y[r0 * n + cc0] + c00
    if r0 < m_rows and cc1 < n:
        y[r0 * n + cc1] = y[r0 * n + cc1] + c01
    if r0 < m_rows and cc2 < n:
        y[r0 * n + cc2] = y[r0 * n + cc2] + c02
    if r0 < m_rows and cc3 < n:
        y[r0 * n + cc3] = y[r0 * n + cc3] + c03
    if r1 < m_rows and cc0 < n:
        y[r1 * n + cc0] = y[r1 * n + cc0] + c10
    if r1 < m_rows and cc1 < n:
        y[r1 * n + cc1] = y[r1 * n + cc1] + c11
    if r1 < m_rows and cc2 < n:
        y[r1 * n + cc2] = y[r1 * n + cc2] + c12
    if r1 < m_rows and cc3 < n:
        y[r1 * n + cc3] = y[r1 * n + cc3] + c13
    if r2 < m_rows and cc0 < n:
        y[r2 * n + cc0] = y[r2 * n + cc0] + c20
    if r2 < m_rows and cc1 < n:
        y[r2 * n + cc1] = y[r2 * n + cc1] + c21
    if r2 < m_rows and cc2 < n:
        y[r2 * n + cc2] = y[r2 * n + cc2] + c22
    if r2 < m_rows and cc3 < n:
        y[r2 * n + cc3] = y[r2 * n + cc3] + c23
    if r3 < m_rows and cc0 < n:
        y[r3 * n + cc0] = y[r3 * n + cc0] + c30
    if r3 < m_rows and cc1 < n:
        y[r3 * n + cc1] = y[r3 * n + cc1] + c31
    if r3 < m_rows and cc2 < n:
        y[r3 * n + cc2] = y[r3 * n + cc2] + c32
    if r3 < m_rows and cc3 < n:
        y[r3 * n + cc3] = y[r3 * n + cc3] + c33


def _pf_gemm_swiglu_kernel_v2(
    act: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_ff_i64: Int64
):
    """Register-blocked, double-buffered, float4-loaded drop-in for `_pf_gemm_swiglu_kernel`:
    the fused gate/up projection + SwiGLU — `w` is the resident `[2*n_ff, k]` gate-THEN-up
    concatenation, `act[M,n_ff] = silu(xn @ W_gate^T) * (xn @ W_up^T)`. Same 4x4 register block
    and double buffering as the assign/accum twins, with TWO transposed B tiles per stage
    (gate + up) staged against the ONE shared `a` tile — each weight element is read once per
    row tile, exactly as the first-generation twin states. 32 accumulator scalars per thread.
    """
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    comptime BM = _G2_BM
    comptime BN = _G2_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime NTHREADS = _G2_NTHREADS
    comptime APAD = _G2_APAD
    comptime BPAD = _G2_BPAD

    var a0 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var a1 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bg0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bg1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bu0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bu1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()

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

    var g00 = Float32(0.0)
    var g01 = Float32(0.0)
    var g02 = Float32(0.0)
    var g03 = Float32(0.0)
    var g10 = Float32(0.0)
    var g11 = Float32(0.0)
    var g12 = Float32(0.0)
    var g13 = Float32(0.0)
    var g20 = Float32(0.0)
    var g21 = Float32(0.0)
    var g22 = Float32(0.0)
    var g23 = Float32(0.0)
    var g30 = Float32(0.0)
    var g31 = Float32(0.0)
    var g32 = Float32(0.0)
    var g33 = Float32(0.0)
    var u00 = Float32(0.0)
    var u01 = Float32(0.0)
    var u02 = Float32(0.0)
    var u03 = Float32(0.0)
    var u10 = Float32(0.0)
    var u11 = Float32(0.0)
    var u12 = Float32(0.0)
    var u13 = Float32(0.0)
    var u20 = Float32(0.0)
    var u21 = Float32(0.0)
    var u22 = Float32(0.0)
    var u23 = Float32(0.0)
    var u30 = Float32(0.0)
    var u31 = Float32(0.0)
    var u32 = Float32(0.0)
    var u33 = Float32(0.0)

    # ── prologue: stage step 0 into buffer 0 (one a tile + gate and up b tiles) ──
    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = _ld4(xn, gr0 * k + lc)
        a0[lr * APAD + lc + 0] = va[0]
        a0[lr * APAD + lc + 1] = va[1]
        a0[lr * APAD + lc + 2] = va[2]
        a0[lr * APAD + lc + 3] = va[3]
    elif gr0 < m_rows:
        for e in range(4):
            a0[lr * APAD + lc + e] = xn[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            a0[lr * APAD + lc + e] = Float32(0.0)
    var wr0 = block_col + lr
    if wr0 < n_ff and lc + 3 < k:
        var vg = _ld4(w, wr0 * k + lc)
        var vu = _ld4(w, (n_ff + wr0) * k + lc)
        bg0[(lc + 0) * BPAD + lr] = vg[0]
        bg0[(lc + 1) * BPAD + lr] = vg[1]
        bg0[(lc + 2) * BPAD + lr] = vg[2]
        bg0[(lc + 3) * BPAD + lr] = vg[3]
        bu0[(lc + 0) * BPAD + lr] = vu[0]
        bu0[(lc + 1) * BPAD + lr] = vu[1]
        bu0[(lc + 2) * BPAD + lr] = vu[2]
        bu0[(lc + 3) * BPAD + lr] = vu[3]
    elif wr0 < n_ff:
        for e in range(4):
            var ge = w[wr0 * k + lc + e] if lc + e < k else Float32(0.0)
            var ue = w[(n_ff + wr0) * k + lc + e] if lc + e < k else Float32(0.0)
            bg0[(lc + e) * BPAD + lr] = ge
            bu0[(lc + e) * BPAD + lr] = ue
    else:
        for e in range(4):
            bg0[(lc + e) * BPAD + lr] = Float32(0.0)
            bu0[(lc + e) * BPAD + lr] = Float32(0.0)
    barrier()

    var cur = 0
    for step in range(n_steps):
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            var agr = block_row + lr
            var wgr = block_col + lr
            if cur == 0:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a1[lr * APAD + lc + 0] = va[0]
                    a1[lr * APAD + lc + 1] = va[1]
                    a1[lr * APAD + lc + 2] = va[2]
                    a1[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = Float32(0.0)
                if wgr < n_ff and ngc + 3 < k:
                    var vg = _ld4(w, wgr * k + ngc)
                    var vu = _ld4(w, (n_ff + wgr) * k + ngc)
                    bg1[(lc + 0) * BPAD + lr] = vg[0]
                    bg1[(lc + 1) * BPAD + lr] = vg[1]
                    bg1[(lc + 2) * BPAD + lr] = vg[2]
                    bg1[(lc + 3) * BPAD + lr] = vg[3]
                    bu1[(lc + 0) * BPAD + lr] = vu[0]
                    bu1[(lc + 1) * BPAD + lr] = vu[1]
                    bu1[(lc + 2) * BPAD + lr] = vu[2]
                    bu1[(lc + 3) * BPAD + lr] = vu[3]
                elif wgr < n_ff:
                    for e in range(4):
                        var ge = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                        var ue = w[(n_ff + wgr) * k + ngc + e] if ngc + e < k else Float32(0.0)
                        bg1[(lc + e) * BPAD + lr] = ge
                        bu1[(lc + e) * BPAD + lr] = ue
                else:
                    for e in range(4):
                        bg1[(lc + e) * BPAD + lr] = Float32(0.0)
                        bu1[(lc + e) * BPAD + lr] = Float32(0.0)
            else:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a0[lr * APAD + lc + 0] = va[0]
                    a0[lr * APAD + lc + 1] = va[1]
                    a0[lr * APAD + lc + 2] = va[2]
                    a0[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = Float32(0.0)
                if wgr < n_ff and ngc + 3 < k:
                    var vg = _ld4(w, wgr * k + ngc)
                    var vu = _ld4(w, (n_ff + wgr) * k + ngc)
                    bg0[(lc + 0) * BPAD + lr] = vg[0]
                    bg0[(lc + 1) * BPAD + lr] = vg[1]
                    bg0[(lc + 2) * BPAD + lr] = vg[2]
                    bg0[(lc + 3) * BPAD + lr] = vg[3]
                    bu0[(lc + 0) * BPAD + lr] = vu[0]
                    bu0[(lc + 1) * BPAD + lr] = vu[1]
                    bu0[(lc + 2) * BPAD + lr] = vu[2]
                    bu0[(lc + 3) * BPAD + lr] = vu[3]
                elif wgr < n_ff:
                    for e in range(4):
                        var ge = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                        var ue = w[(n_ff + wgr) * k + ngc + e] if ngc + e < k else Float32(0.0)
                        bg0[(lc + e) * BPAD + lr] = ge
                        bu0[(lc + e) * BPAD + lr] = ue
                else:
                    for e in range(4):
                        bg0[(lc + e) * BPAD + lr] = Float32(0.0)
                        bu0[(lc + e) * BPAD + lr] = Float32(0.0)

        var acur = a0 if cur == 0 else a1
        var bgcur = bg0 if cur == 0 else bg1
        var bucur = bu0 if cur == 0 else bu1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xg0 = bgcur[kk * BPAD + tx]
            var xg1 = bgcur[kk * BPAD + tx + 16]
            var xg2 = bgcur[kk * BPAD + tx + 32]
            var xg3 = bgcur[kk * BPAD + tx + 48]
            var xu0 = bucur[kk * BPAD + tx]
            var xu1 = bucur[kk * BPAD + tx + 16]
            var xu2 = bucur[kk * BPAD + tx + 32]
            var xu3 = bucur[kk * BPAD + tx + 48]
            g00 += xa0 * xg0
            g01 += xa0 * xg1
            g02 += xa0 * xg2
            g03 += xa0 * xg3
            g10 += xa1 * xg0
            g11 += xa1 * xg1
            g12 += xa1 * xg2
            g13 += xa1 * xg3
            g20 += xa2 * xg0
            g21 += xa2 * xg1
            g22 += xa2 * xg2
            g23 += xa2 * xg3
            g30 += xa3 * xg0
            g31 += xa3 * xg1
            g32 += xa3 * xg2
            g33 += xa3 * xg3
            u00 += xa0 * xu0
            u01 += xa0 * xu1
            u02 += xa0 * xu2
            u03 += xa0 * xu3
            u10 += xa1 * xu0
            u11 += xa1 * xu1
            u12 += xa1 * xu2
            u13 += xa1 * xu3
            u20 += xa2 * xu0
            u21 += xa2 * xu1
            u22 += xa2 * xu2
            u23 += xa2 * xu3
            u30 += xa3 * xu0
            u31 += xa3 * xu1
            u32 += xa3 * xu2
            u33 += xa3 * xu3
        barrier()
        cur = 1 - cur

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    if r0 < m_rows and cc0 < n_ff:
        act[r0 * n_ff + cc0] = (g00 / (1.0 + exp(-g00))) * u00
    if r0 < m_rows and cc1 < n_ff:
        act[r0 * n_ff + cc1] = (g01 / (1.0 + exp(-g01))) * u01
    if r0 < m_rows and cc2 < n_ff:
        act[r0 * n_ff + cc2] = (g02 / (1.0 + exp(-g02))) * u02
    if r0 < m_rows and cc3 < n_ff:
        act[r0 * n_ff + cc3] = (g03 / (1.0 + exp(-g03))) * u03
    if r1 < m_rows and cc0 < n_ff:
        act[r1 * n_ff + cc0] = (g10 / (1.0 + exp(-g10))) * u10
    if r1 < m_rows and cc1 < n_ff:
        act[r1 * n_ff + cc1] = (g11 / (1.0 + exp(-g11))) * u11
    if r1 < m_rows and cc2 < n_ff:
        act[r1 * n_ff + cc2] = (g12 / (1.0 + exp(-g12))) * u12
    if r1 < m_rows and cc3 < n_ff:
        act[r1 * n_ff + cc3] = (g13 / (1.0 + exp(-g13))) * u13
    if r2 < m_rows and cc0 < n_ff:
        act[r2 * n_ff + cc0] = (g20 / (1.0 + exp(-g20))) * u20
    if r2 < m_rows and cc1 < n_ff:
        act[r2 * n_ff + cc1] = (g21 / (1.0 + exp(-g21))) * u21
    if r2 < m_rows and cc2 < n_ff:
        act[r2 * n_ff + cc2] = (g22 / (1.0 + exp(-g22))) * u22
    if r2 < m_rows and cc3 < n_ff:
        act[r2 * n_ff + cc3] = (g23 / (1.0 + exp(-g23))) * u23
    if r3 < m_rows and cc0 < n_ff:
        act[r3 * n_ff + cc0] = (g30 / (1.0 + exp(-g30))) * u30
    if r3 < m_rows and cc1 < n_ff:
        act[r3 * n_ff + cc1] = (g31 / (1.0 + exp(-g31))) * u31
    if r3 < m_rows and cc2 < n_ff:
        act[r3 * n_ff + cc2] = (g32 / (1.0 + exp(-g32))) * u32
    if r3 < m_rows and cc3 < n_ff:
        act[r3 * n_ff + cc3] = (g33 / (1.0 + exp(-g33))) * u33
