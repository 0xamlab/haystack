"""residentk.kernels_prefill_f32_v2n — the NARROW-N (BN=32) twin of the v2 prefill ACCUM
GEMM, for the o_proj / down_proj roles at M-parallel admission prefill. Additive — the v2
family module is byte-unmodified; the serve driver dispatches this twin for the narrow-N
accum roles under the same one-pass prefill arm. Same mixed-precision-free f32 contract,
same ascending-k accumulation order, same acceptance gate (the driver selftest). Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

WHY: the A100 autopsy named the narrow-N roles as the v2 family's grid underfill — at BN=64
o_proj/down_proj launch only ceil(M/64)*16 blocks (272 at M=1038 for 108 SMs) while qkv/gu
launch 5-7x more; BN=32 doubles the narrow roles' blocks at 128-thread blocks, the tile
arithmetic staying register-blocked 4x4 (TM x TN over 64x32). The 64-row A tile stages in
two float4 passes per thread (rows lr and lr+32); the 32-row B tile stages in one.
"""

from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BK,
    _G2_TM,
    _G2_TN,
    _G2_APAD,
)
from std.gpu import block_idx, thread_idx
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.origin import MutAnyOrigin

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels` uses."""

comptime _G2N_BN: Int = 32
comptime _G2N_NTHREADS: Int = (_G2_BM // _G2_TM) * (_G2N_BN // _G2_TN)
comptime _G2N_BPAD: Int = _G2N_BN + 1

def _pf_gemm_accum_kernel_v2n(
    y: _FP, x: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """NARROW-N twin of `_pf_gemm_accum_kernel_v2` for the o_proj / down_proj ACCUM roles at
    M-parallel admission prefill (the autopsy's named v2 underfill: at BN=64 their grids are
    only ceil(M/64)*16 blocks). BN=32 doubles the grid (ceil(M/64)*32); the block halves to
    128 threads (TM=4 x TN=4 over a 64x32 tile), so the 64-row A tile stages in TWO
    float4 passes per thread (rows lr and lr+32) while the 32-row B tile stages in one —
    everything else (double buffering, float4 global loads, pad conventions, ascending-k
    accumulation) is the 256-thread accum twin verbatim."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G2_BM
    comptime BN = _G2N_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime NTHREADS = _G2N_NTHREADS
    comptime APAD = _G2_APAD
    comptime BPAD = _G2N_BPAD

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

    var rpass = 0
    while rpass < 2:
        var arow = lr + rpass * 32
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
                var rpass = 0
                while rpass < 2:
                    var arow = lr + rpass * 32
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
                    rpass += 1
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
                var rpass = 0
                while rpass < 2:
                    var arow = lr + rpass * 32
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
                    rpass += 1
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
            var xb0 = bcur[kk * BPAD + tx]
            var xb1 = bcur[kk * BPAD + tx + 8]
            var xb2 = bcur[kk * BPAD + tx + 16]
            var xb3 = bcur[kk * BPAD + tx + 24]
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
    var cc1 = cc0 + 8
    var cc2 = cc0 + 16
    var cc3 = cc0 + 24
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


