"""residentk.kernels_prefill_f32_v3 — the H100-tuned THIRD-GENERATION f32 prefill GEMM
variants. Additive — the v2 family is byte-unmodified. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/h100_gemm_probe.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/h100_gemm_probe.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

WHY THIS FILE EXISTS — the H100 autopsy evidence it answers
------------------------------------------------------------
The windowed nsys + ncu autopsy on algenta-ent-h100 (H100 80GB, sm_90) measured the v2
family's prefill GEMMs as INSTRUCTION-ISSUE-BOUND, not FLOP-pipe- or bandwidth-bound:

  * M=1152 one-pass grids (the serve admission shape): issue active 47-57%, FMA pipe only
    28-35%, DRAM <=3%, L2 hit 82-92%, occupancy 24-44%. FMA is ~62% of issued instructions;
    the other 38% (shared loads, address arithmetic, loop control) caps the FMA pipe.
  * H100 doubled the FP32 datapath per SM vs A100 (128 lanes vs 64) WITHOUT widening issue
    (4 warp instructions/cycle/SM both generations). Feeding the doubled pipe needs ~2x the
    FMA fraction of issue; the v2 4x4 register block (16 FMAs per 8 shared loads per k-step)
    cannot supply it — this is the measured root cause of the 1.54x A100->H100 fixture
    scaling vs the 3.4x f32-peak ratio (the GEMM-only scaling at equal M is 1.71x = exactly
    the SM-count x clock product, i.e. issue-bound).
  * M=128 fixture chunks: occupancy pinned 12.5% = ONE block/SM because the narrow-N roles
    launch only 32 blocks (o/down) on 132 SMs (waves 0.06) — grid underfill, not residency.

The two variant families below answer each half:

* v3 (WIDE): BM=128, BN=64, BK=16, register block TM=8 x TN=4 = 32 accumulator scalars on
  256 threads. Per k-step: 32 FMAs against 12 shared loads (8 A + 4 B) = 2.67:1 (v2 = 2:1),
  and the loop/address overhead amortizes over 2x the arithmetic. Same float4-only global
  load surface, same ascending-k accumulation order, same double buffering; the 128-row A
  tile stages in TWO float4 passes per thread (rows lr and lr+64), exactly the pattern the
  v2n narrow twin already proved on this backend.
* v3s (SMALL-M NARROW): BM=32, BN=64, TM=4, TN=4 on 128 threads, for the o_proj/down_proj
  ACCUM roles at small M. At M=256 the v2 accum kernel launches ceil(256/64)*16 = 64 blocks
  (48% of 132 SMs); BM=32 quadruples the row-tiles -> 128 blocks = a single wave on 97% of
  the SMs. The 32-row A tile is ONE float4 per thread; the B tile stages in two passes.

Same math, same ascending-k accumulation ORDER as the v2 family: the only numerical
difference is codegen-level (FMA contraction), bounded to ulps. The probe gate (max relative
difference vs v2 on real weights) and the session's 16/16 greedy oracle are the acceptance
test. NOT a contract module — leading underscores, only `residentk.session_cuda` / the serve
driver reach these.

Mojo 1.0.0 kernel-parameter discipline: every scalar parameter is a fixed-width `Int64`
(DevicePassable), widened back to `Int` once at entry.
"""

from std.gpu import block_idx, thread_idx
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels` uses."""

# ══════════════════════════ v3 WIDE family (BM=128, TM=8x4) ══════════════════════════

comptime _G3_BM: Int = 128
comptime _G3_BN: Int = 64
comptime _G3_BK: Int = 16
comptime _G3_TM: Int = 8
comptime _G3_TN: Int = 4
comptime _G3_NTHREADS: Int = (_G3_BM // _G3_TM) * (_G3_BN // _G3_TN)
"""256 threads = 16 x 16, derived from the tile and the register block."""
comptime _G3_APAD: Int = _G3_BK + 4
comptime _G3_BPAD: Int = _G3_BN + 1


def _pf_gemm_assign_kernel_v3(
    y: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """H100 wide-register-block drop-in for `_pf_gemm_assign_kernel_v2`:
    `y[M,n] = xn[M,k] @ W^T[k,n]`, `w` stored `[n,k]` row-major, ASSIGNING into `y`.
    Grid contract unchanged: `grid_dim = ceil(m/_G3_BM) * ceil(n/_G3_BN)` flattened
    `(tile_row, tile_col)` with `tile_col = block_idx.x % n_tile_cols`."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G3_BM
    comptime BN = _G3_BN
    comptime BK = _G3_BK
    comptime TM = _G3_TM
    comptime TN = _G3_TN
    comptime NTHREADS = _G3_NTHREADS
    comptime APAD = _G3_APAD
    comptime BPAD = _G3_BPAD

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

    # Cooperative A load: BM*BK = 2048 elements = TWO float4 per thread (rows lr, lr+64).
    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    # 32 explicit accumulator scalars — registers by construction.
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
    var c40 = Float32(0.0)
    var c41 = Float32(0.0)
    var c42 = Float32(0.0)
    var c43 = Float32(0.0)
    var c50 = Float32(0.0)
    var c51 = Float32(0.0)
    var c52 = Float32(0.0)
    var c53 = Float32(0.0)
    var c60 = Float32(0.0)
    var c61 = Float32(0.0)
    var c62 = Float32(0.0)
    var c63 = Float32(0.0)
    var c70 = Float32(0.0)
    var c71 = Float32(0.0)
    var c72 = Float32(0.0)
    var c73 = Float32(0.0)

    # ── prologue: stage step 0 into buffer 0 ──
    var rpass = 0
    while rpass < 2:
        var arow = lr + rpass * 64
        var gr0 = block_row + arow
        if gr0 < m_rows and lc + 3 < k:
            var va = xn.load[width=4](gr0 * k + lc)
            a0[arow * APAD + lc + 0] = va[0]
            a0[arow * APAD + lc + 1] = va[1]
            a0[arow * APAD + lc + 2] = va[2]
            a0[arow * APAD + lc + 3] = va[3]
        elif gr0 < m_rows:
            for e in range(4):
                a0[arow * APAD + lc + e] = xn[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
        else:
            for e in range(4):
                a0[arow * APAD + lc + e] = Float32(0.0)
        rpass += 1
    var wr0 = block_col + lr
    if wr0 < n and lc + 3 < k:
        var vb = w.load[width=4](wr0 * k + lc)
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
            if cur == 0:
                var rpass2 = 0
                while rpass2 < 2:
                    var arow = lr + rpass2 * 64
                    var agr = block_row + arow
                    if agr < m_rows and ngc + 3 < k:
                        var va = xn.load[width=4](agr * k + ngc)
                        a1[arow * APAD + lc + 0] = va[0]
                        a1[arow * APAD + lc + 1] = va[1]
                        a1[arow * APAD + lc + 2] = va[2]
                        a1[arow * APAD + lc + 3] = va[3]
                    elif agr < m_rows:
                        for e in range(4):
                            a1[arow * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                    else:
                        for e in range(4):
                            a1[arow * APAD + lc + e] = Float32(0.0)
                    rpass2 += 1
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
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
                var rpass2 = 0
                while rpass2 < 2:
                    var arow = lr + rpass2 * 64
                    var agr = block_row + arow
                    if agr < m_rows and ngc + 3 < k:
                        var va = xn.load[width=4](agr * k + ngc)
                        a0[arow * APAD + lc + 0] = va[0]
                        a0[arow * APAD + lc + 1] = va[1]
                        a0[arow * APAD + lc + 2] = va[2]
                        a0[arow * APAD + lc + 3] = va[3]
                    elif agr < m_rows:
                        for e in range(4):
                            a0[arow * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                    else:
                        for e in range(4):
                            a0[arow * APAD + lc + e] = Float32(0.0)
                    rpass2 += 1
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
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

        # ── consume: 8x4 register block, 32 FMAs per k-step against 12 shared loads ──
        var acur = a0 if cur == 0 else a1
        var bcur = b0 if cur == 0 else b1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xa4 = acur[(ty * TM + 4) * APAD + kk]
            var xa5 = acur[(ty * TM + 5) * APAD + kk]
            var xa6 = acur[(ty * TM + 6) * APAD + kk]
            var xa7 = acur[(ty * TM + 7) * APAD + kk]
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
            c40 += xa4 * xb0
            c41 += xa4 * xb1
            c42 += xa4 * xb2
            c43 += xa4 * xb3
            c50 += xa5 * xb0
            c51 += xa5 * xb1
            c52 += xa5 * xb2
            c53 += xa5 * xb3
            c60 += xa6 * xb0
            c61 += xa6 * xb1
            c62 += xa6 * xb2
            c63 += xa6 * xb3
            c70 += xa7 * xb0
            c71 += xa7 * xb1
            c72 += xa7 * xb2
            c73 += xa7 * xb3
        barrier()
        cur = 1 - cur

    # ── epilogue: 32 guarded stores, column ownership c = tx + 16*j ──
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    for i in range(TM):
        var r = block_row + ty * TM + i
        if r < m_rows:
            var v0 = c00 if i == 0 else (c10 if i == 1 else (c20 if i == 2 else (c30 if i == 3 else (c40 if i == 4 else (c50 if i == 5 else (c60 if i == 6 else c70))))))
            var v1 = c01 if i == 0 else (c11 if i == 1 else (c21 if i == 2 else (c31 if i == 3 else (c41 if i == 4 else (c51 if i == 5 else (c61 if i == 6 else c71))))))
            var v2 = c02 if i == 0 else (c12 if i == 1 else (c22 if i == 2 else (c32 if i == 3 else (c42 if i == 4 else (c52 if i == 5 else (c62 if i == 6 else c72))))))
            var v3 = c03 if i == 0 else (c13 if i == 1 else (c23 if i == 2 else (c33 if i == 3 else (c43 if i == 4 else (c53 if i == 5 else (c63 if i == 6 else c73))))))
            if cc0 < n:
                y[r * n + cc0] = v0
            if cc1 < n:
                y[r * n + cc1] = v1
            if cc2 < n:
                y[r * n + cc2] = v2
            if cc3 < n:
                y[r * n + cc3] = v3


def _pf_gemm_accum_kernel_v3(
    y: _FP, x: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """H100 wide-register-block drop-in for `_pf_gemm_accum_kernel_v2`:
    `y[M,n] += x[M,k] @ W^T[k,n]` — the residual-add half of o_proj and down_proj.
    Byte-for-byte the same structure as `_pf_gemm_assign_kernel_v3` except the epilogue
    ACCUMULATES (`y[r*n+c] = y[r*n+c] + cIJ`)."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G3_BM
    comptime BN = _G3_BN
    comptime BK = _G3_BK
    comptime TM = _G3_TM
    comptime TN = _G3_TN
    comptime APAD = _G3_APAD
    comptime BPAD = _G3_BPAD

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
    var c40 = Float32(0.0)
    var c41 = Float32(0.0)
    var c42 = Float32(0.0)
    var c43 = Float32(0.0)
    var c50 = Float32(0.0)
    var c51 = Float32(0.0)
    var c52 = Float32(0.0)
    var c53 = Float32(0.0)
    var c60 = Float32(0.0)
    var c61 = Float32(0.0)
    var c62 = Float32(0.0)
    var c63 = Float32(0.0)
    var c70 = Float32(0.0)
    var c71 = Float32(0.0)
    var c72 = Float32(0.0)
    var c73 = Float32(0.0)

    var rpass = 0
    while rpass < 2:
        var arow = lr + rpass * 64
        var gr0 = block_row + arow
        if gr0 < m_rows and lc + 3 < k:
            var va = x.load[width=4](gr0 * k + lc)
            a0[arow * APAD + lc + 0] = va[0]
            a0[arow * APAD + lc + 1] = va[1]
            a0[arow * APAD + lc + 2] = va[2]
            a0[arow * APAD + lc + 3] = va[3]
        elif gr0 < m_rows:
            for e in range(4):
                a0[arow * APAD + lc + e] = x[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
        else:
            for e in range(4):
                a0[arow * APAD + lc + e] = Float32(0.0)
        rpass += 1
    var wr0 = block_col + lr
    if wr0 < n and lc + 3 < k:
        var vb = w.load[width=4](wr0 * k + lc)
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
            if cur == 0:
                var rpass2 = 0
                while rpass2 < 2:
                    var arow = lr + rpass2 * 64
                    var agr = block_row + arow
                    if agr < m_rows and ngc + 3 < k:
                        var va = x.load[width=4](agr * k + ngc)
                        a1[arow * APAD + lc + 0] = va[0]
                        a1[arow * APAD + lc + 1] = va[1]
                        a1[arow * APAD + lc + 2] = va[2]
                        a1[arow * APAD + lc + 3] = va[3]
                    elif agr < m_rows:
                        for e in range(4):
                            a1[arow * APAD + lc + e] = x[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                    else:
                        for e in range(4):
                            a1[arow * APAD + lc + e] = Float32(0.0)
                    rpass2 += 1
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
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
                var rpass2 = 0
                while rpass2 < 2:
                    var arow = lr + rpass2 * 64
                    var agr = block_row + arow
                    if agr < m_rows and ngc + 3 < k:
                        var va = x.load[width=4](agr * k + ngc)
                        a0[arow * APAD + lc + 0] = va[0]
                        a0[arow * APAD + lc + 1] = va[1]
                        a0[arow * APAD + lc + 2] = va[2]
                        a0[arow * APAD + lc + 3] = va[3]
                    elif agr < m_rows:
                        for e in range(4):
                            a0[arow * APAD + lc + e] = x[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                    else:
                        for e in range(4):
                            a0[arow * APAD + lc + e] = Float32(0.0)
                    rpass2 += 1
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
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
            var xa4 = acur[(ty * TM + 4) * APAD + kk]
            var xa5 = acur[(ty * TM + 5) * APAD + kk]
            var xa6 = acur[(ty * TM + 6) * APAD + kk]
            var xa7 = acur[(ty * TM + 7) * APAD + kk]
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
            c40 += xa4 * xb0
            c41 += xa4 * xb1
            c42 += xa4 * xb2
            c43 += xa4 * xb3
            c50 += xa5 * xb0
            c51 += xa5 * xb1
            c52 += xa5 * xb2
            c53 += xa5 * xb3
            c60 += xa6 * xb0
            c61 += xa6 * xb1
            c62 += xa6 * xb2
            c63 += xa6 * xb3
            c70 += xa7 * xb0
            c71 += xa7 * xb1
            c72 += xa7 * xb2
            c73 += xa7 * xb3
        barrier()
        cur = 1 - cur

    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    for i in range(TM):
        var r = block_row + ty * TM + i
        if r < m_rows:
            var v0 = c00 if i == 0 else (c10 if i == 1 else (c20 if i == 2 else (c30 if i == 3 else (c40 if i == 4 else (c50 if i == 5 else (c60 if i == 6 else c70))))))
            var v1 = c01 if i == 0 else (c11 if i == 1 else (c21 if i == 2 else (c31 if i == 3 else (c41 if i == 4 else (c51 if i == 5 else (c61 if i == 6 else c71))))))
            var v2 = c02 if i == 0 else (c12 if i == 1 else (c22 if i == 2 else (c32 if i == 3 else (c42 if i == 4 else (c52 if i == 5 else (c62 if i == 6 else c72))))))
            var v3 = c03 if i == 0 else (c13 if i == 1 else (c23 if i == 2 else (c33 if i == 3 else (c43 if i == 4 else (c53 if i == 5 else (c63 if i == 6 else c73))))))
            if cc0 < n:
                y[r * n + cc0] = y[r * n + cc0] + v0
            if cc1 < n:
                y[r * n + cc1] = y[r * n + cc1] + v1
            if cc2 < n:
                y[r * n + cc2] = y[r * n + cc2] + v2
            if cc3 < n:
                y[r * n + cc3] = y[r * n + cc3] + v3


# ══════════════════ v3s SMALL-M NARROW family (BM=32, 128 threads) ══════════════════

comptime _G3S_BM: Int = 32
comptime _G3S_BN: Int = 64
comptime _G3S_BK: Int = 16
comptime _G3S_TM: Int = 4
comptime _G3S_TN: Int = 4
comptime _G3S_NTHREADS: Int = (_G3S_BM // _G3S_TM) * (_G3S_BN // _G3S_TN)
"""128 threads = 8 x 16 — the narrow-N accum roles at small M."""
comptime _G3S_APAD: Int = _G3S_BK + 4
comptime _G3S_BPAD: Int = _G3S_BN + 1


def _pf_gemm_accum_kernel_v3s(
    y: _FP, x: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """SMALL-M NARROW-N twin of `_pf_gemm_accum_kernel_v2` (o_proj / down_proj ACCUM at
    M <= ~256): BM=32 quadruples the row-tile count (M=256: 64 -> 128 blocks = one wave on
    97% of the H100's 132 SMs instead of 48%), 128-thread blocks, TM=4 x TN=4 over a 32x64
    tile. The 32-row A tile stages in ONE float4 per thread; the 64-row B tile in two
    passes (weight rows lr and lr+32). Otherwise the v2 accum contract verbatim: ascending-k
    accumulation, double buffering, guarded tails, ACCUMULATING epilogue."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G3S_BM
    comptime BN = _G3S_BN
    comptime BK = _G3S_BK
    comptime TM = _G3S_TM
    comptime TN = _G3S_TN
    comptime APAD = _G3S_APAD
    comptime BPAD = _G3S_BPAD

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

    # ── prologue: A tile ONE float4/thread; B tile two passes (rows lr, lr+32) ──
    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = x.load[width=4](gr0 * k + lc)
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
    var bpass = 0
    while bpass < 2:
        var wrow = lr + bpass * 32
        var wr0 = block_col + wrow
        if wr0 < n and lc + 3 < k:
            var vb = w.load[width=4](wr0 * k + lc)
            b0[(lc + 0) * BPAD + wrow] = vb[0]
            b0[(lc + 1) * BPAD + wrow] = vb[1]
            b0[(lc + 2) * BPAD + wrow] = vb[2]
            b0[(lc + 3) * BPAD + wrow] = vb[3]
        elif wr0 < n:
            for e in range(4):
                b0[(lc + e) * BPAD + wrow] = w[wr0 * k + lc + e] if lc + e < k else Float32(0.0)
        else:
            for e in range(4):
                b0[(lc + e) * BPAD + wrow] = Float32(0.0)
        bpass += 1
    barrier()

    var cur = 0
    for step in range(n_steps):
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            if cur == 0:
                var agr = block_row + lr
                if agr < m_rows and ngc + 3 < k:
                    var va = x.load[width=4](agr * k + ngc)
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
                var bpass2 = 0
                while bpass2 < 2:
                    var wrow = lr + bpass2 * 32
                    var wgr = block_col + wrow
                    if wgr < n and ngc + 3 < k:
                        var vb = w.load[width=4](wgr * k + ngc)
                        b1[(lc + 0) * BPAD + wrow] = vb[0]
                        b1[(lc + 1) * BPAD + wrow] = vb[1]
                        b1[(lc + 2) * BPAD + wrow] = vb[2]
                        b1[(lc + 3) * BPAD + wrow] = vb[3]
                    elif wgr < n:
                        for e in range(4):
                            b1[(lc + e) * BPAD + wrow] = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                    else:
                        for e in range(4):
                            b1[(lc + e) * BPAD + wrow] = Float32(0.0)
                    bpass2 += 1
            else:
                var agr = block_row + lr
                if agr < m_rows and ngc + 3 < k:
                    var va = x.load[width=4](agr * k + ngc)
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
                var bpass2 = 0
                while bpass2 < 2:
                    var wrow = lr + bpass2 * 32
                    var wgr = block_col + wrow
                    if wgr < n and ngc + 3 < k:
                        var vb = w.load[width=4](wgr * k + ngc)
                        b0[(lc + 0) * BPAD + wrow] = vb[0]
                        b0[(lc + 1) * BPAD + wrow] = vb[1]
                        b0[(lc + 2) * BPAD + wrow] = vb[2]
                        b0[(lc + 3) * BPAD + wrow] = vb[3]
                    elif wgr < n:
                        for e in range(4):
                            b0[(lc + e) * BPAD + wrow] = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                    else:
                        for e in range(4):
                            b0[(lc + e) * BPAD + wrow] = Float32(0.0)
                    bpass2 += 1

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

    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
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
