"""residentk.kernels_prefill_attn_flash2 — the LATENCY-PIPELINED twin of the flash-style
M-parallel prefill attention kernel. Additive — kernels_prefill_attn_flash is byte-unmodified.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest
benchmark: benchmarks/llm_smoke/nvidia_race/h100_attn_probe.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

WHY THIS FILE EXISTS — the H100 ncu evidence it answers
--------------------------------------------------------
The rag admission prefill on algenta-ent-h100 spends 559.6 ms of the 707 ms per-request
prefill GPU in `_pf_attn_flash_kernel` (nsys window, 4096-token prompt). The ncu per-kernel
capture of that kernel at the M=1152 pass shape measured:

  * issue active 40%, FMA pipe 21%, DRAM 0.26%, L2 (lts) 5.8%, L1TEX 41% — NO bandwidth
    wall anywhere;
  * occupancy 26.6% (80 regs/thread);
  * stall mix per issue-active cycle: long-scoreboard 3.75 vs wait 2.17 vs not-selected
    0.61 vs math-pipe-throttle 0.07.

long-scoreboard dominance = the per-key K/V global loads' LATENCY is exposed: every key's
`ck.load`/`cv.load` stalls the warp and there is not enough occupancy to cover it. This
twin restructures the load order WITHOUT touching the math:

  1. The V_j load is issued BEFORE key j's score reduction (it was after), so the V fetch
     overlaps the warp-shuffle score tree + the two exp evaluations instead of chaining
     after them.
  2. K_{j+1} is prefetched into a register quad while key j is consumed (double-buffered
     one step, +4 registers), so the next key's load latency runs under the current key's
     softmax/O-update arithmetic.

Same per-key ascending-j order, same online-softmax recurrence VERBATIM, same warp-shuffle
score tree — the result is bit-identical to the one-row-order form by construction; the
probe gate (max-abs diff vs `_pf_attn_flash_kernel` on identical buffers) and the serve
driver's selftest are the acceptance test. Same geometry/contract: d_head == 128, one warp
per four consecutive rows of one head, `grid_dim = ceil(m_rows/32) * h_q`, block 256.

Mojo 1.0.0 kernel-parameter discipline: every scalar parameter is a fixed-width `Int64`.
"""

from std.gpu import block_idx, lane_id, warp_id
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import exp
from std.origin import MutAnyOrigin
from residentk.kernels import _NEG_HUGE as _PF_FLASH2_NEG_HUGE
from residentk.kernels_prefill_attn_flash import (
    _PF_FLASH_ROWS_PER_WARP,
    _PF_FLASH_WARPS_PER_BLOCK,
    _PF_FLASH_ROWS_PER_BLOCK,
    _PF_FLASH_NTHREADS,
    _PF_FLASH_ELEMS_PER_LANE,
)

from residentk.loadvec import _ld4
alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def _pf_attn_flash2_kernel(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32, m_rows_i64: Int64,
):
    """Latency-pipelined drop-in for `_pf_attn_flash_kernel` — identical contract, identical
    row math, restructured load order: V_j issued before the score tree, K_{j+1} prefetched
    under key j's consume. `grid_dim = ceil(m_rows / _PF_FLASH_ROWS_PER_BLOCK) * h_q`,
    `block_dim = 256`; block `g` covers head `g % h_q` and rows
    `(g // h_q) * _PF_FLASH_ROWS_PER_BLOCK + warp_id()*4 + 0..3`."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var m_rows = Int(m_rows_i64)

    var h = Int(block_idx.x) % h_q
    var m_base = (Int(block_idx.x) // h_q) * _PF_FLASH_ROWS_PER_BLOCK \
        + Int(warp_id()) * _PF_FLASH_ROWS_PER_WARP
    if m_base >= m_rows:
        return

    var lane = Int(lane_id())
    var e0 = lane * _PF_FLASH_ELEMS_PER_LANE
    var hk = h // (h_q // h_kv)
    var n_q = h_q * d_head

    # ── per-row state (rows beyond m_rows are inactive; row 0 is always active here) ──
    var m0 = m_base
    var m1 = m_base + 1
    var m2 = m_base + 2
    var m3 = m_base + 3
    var act1 = m1 < m_rows
    var act2 = m2 < m_rows
    var act3 = m3 < m_rows
    var nk0 = pos_base + m0 + 1
    var nk1 = pos_base + m1 + 1
    var nk2 = pos_base + m2 + 1
    var nk3 = pos_base + m3 + 1
    var nk_max = nk3 if act3 else (nk2 if act2 else (nk1 if act1 else nk0))

    var qb = m0 * n_q + h * d_head + e0
    var q04 = _ld4(q_rot, qb)
    var q00 = q04[0]
    var q01 = q04[1]
    var q02 = q04[2]
    var q03 = q04[3]
    var q10 = Float32(0.0)
    var q11 = Float32(0.0)
    var q12 = Float32(0.0)
    var q13 = Float32(0.0)
    var q20 = Float32(0.0)
    var q21 = Float32(0.0)
    var q22 = Float32(0.0)
    var q23 = Float32(0.0)
    var q30 = Float32(0.0)
    var q31 = Float32(0.0)
    var q32 = Float32(0.0)
    var q33 = Float32(0.0)
    if act1:
        var q14 = _ld4(q_rot, m1 * n_q + h * d_head + e0)
        q10 = q14[0]
        q11 = q14[1]
        q12 = q14[2]
        q13 = q14[3]
    if act2:
        var q24 = _ld4(q_rot, m2 * n_q + h * d_head + e0)
        q20 = q24[0]
        q21 = q24[1]
        q22 = q24[2]
        q23 = q24[3]
    if act3:
        var q34 = _ld4(q_rot, m3 * n_q + h * d_head + e0)
        q30 = q34[0]
        q31 = q34[1]
        q32 = q34[2]
        q33 = q34[3]

    var mx0 = _PF_FLASH2_NEG_HUGE
    var mx1 = _PF_FLASH2_NEG_HUGE
    var mx2 = _PF_FLASH2_NEG_HUGE
    var mx3 = _PF_FLASH2_NEG_HUGE
    var den0 = Float32(0.0)
    var den1 = Float32(0.0)
    var den2 = Float32(0.0)
    var den3 = Float32(0.0)
    var o00 = Float32(0.0)
    var o01 = Float32(0.0)
    var o02 = Float32(0.0)
    var o03 = Float32(0.0)
    var o10 = Float32(0.0)
    var o11 = Float32(0.0)
    var o12 = Float32(0.0)
    var o13 = Float32(0.0)
    var o20 = Float32(0.0)
    var o21 = Float32(0.0)
    var o22 = Float32(0.0)
    var o23 = Float32(0.0)
    var o30 = Float32(0.0)
    var o31 = Float32(0.0)
    var o32 = Float32(0.0)
    var o33 = Float32(0.0)

    # ── prologue: K_0 staged before the loop ──
    var kb0 = (0 * h_kv + hk) * d_head + e0
    var k4 = _ld4(ck, kb0)

    for j in range(nk_max):
        # (a) prefetch K_{j+1} under this key's consume — latency runs under arithmetic
        var k4n = k4
        if j + 1 < nk_max:
            var kbn = ((j + 1) * h_kv + hk) * d_head + e0
            k4n = _ld4(ck, kbn)
        # (b) V_j issued BEFORE the score tree — overlaps shuffle+exp latency
        var vv4 = _ld4(cv, kb0)

        var s0 = _PF_FLASH2_NEG_HUGE
        var s1 = _PF_FLASH2_NEG_HUGE
        var s2 = _PF_FLASH2_NEG_HUGE
        var s3 = _PF_FLASH2_NEG_HUGE
        # row 0 carries the SAME causal guard rows 1-3 have: keys j >= nk0 belong to the
        # warp's own future rows (m0+1..m3) — without the guard row 0 attends them (found
        # by the 7B B1 gate bisection 2026-08-24; the NEG_HUGE score makes the update a
        # no-op exactly the way rows 1-3 mask, so this touches nothing but the leak).
        if j < nk0:
            s0 = _warp_sum(q00 * k4[0] + q01 * k4[1] + q02 * k4[2] + q03 * k4[3]) * scale
        if j < nk1:
            s1 = _warp_sum(q10 * k4[0] + q11 * k4[1] + q12 * k4[2] + q13 * k4[3]) * scale
        if j < nk2:
            s2 = _warp_sum(q20 * k4[0] + q21 * k4[1] + q22 * k4[2] + q23 * k4[3]) * scale
        if j < nk3:
            s3 = _warp_sum(q30 * k4[0] + q31 * k4[1] + q32 * k4[2] + q33 * k4[3]) * scale

        var nm0 = mx0 if mx0 > s0 else s0
        var corr0 = exp(mx0 - nm0)
        var w0 = exp(s0 - nm0)
        o00 = o00 * corr0 + w0 * vv4[0]
        o01 = o01 * corr0 + w0 * vv4[1]
        o02 = o02 * corr0 + w0 * vv4[2]
        o03 = o03 * corr0 + w0 * vv4[3]
        den0 = den0 * corr0 + w0
        mx0 = nm0

        if j < nk1:
            var nm1 = mx1 if mx1 > s1 else s1
            var corr1 = exp(mx1 - nm1)
            var w1 = exp(s1 - nm1)
            o10 = o10 * corr1 + w1 * vv4[0]
            o11 = o11 * corr1 + w1 * vv4[1]
            o12 = o12 * corr1 + w1 * vv4[2]
            o13 = o13 * corr1 + w1 * vv4[3]
            den1 = den1 * corr1 + w1
            mx1 = nm1
        if j < nk2:
            var nm2 = mx2 if mx2 > s2 else s2
            var corr2 = exp(mx2 - nm2)
            var w2 = exp(s2 - nm2)
            o20 = o20 * corr2 + w2 * vv4[0]
            o21 = o21 * corr2 + w2 * vv4[1]
            o22 = o22 * corr2 + w2 * vv4[2]
            o23 = o23 * corr2 + w2 * vv4[3]
            den2 = den2 * corr2 + w2
            mx2 = nm2
        if j < nk3:
            var nm3 = mx3 if mx3 > s3 else s3
            var corr3 = exp(mx3 - nm3)
            var w3 = exp(s3 - nm3)
            o30 = o30 * corr3 + w3 * vv4[0]
            o31 = o31 * corr3 + w3 * vv4[1]
            o32 = o32 * corr3 + w3 * vv4[2]
            o33 = o33 * corr3 + w3 * vv4[3]
            den3 = den3 * corr3 + w3
            mx3 = nm3

        # (c) rotate the K buffer
        k4 = k4n
        kb0 = ((j + 1) * h_kv + hk) * d_head + e0

    var ob0 = m0 * n_q + h * d_head + e0
    attn_out[ob0 + 0] = o00 / den0
    attn_out[ob0 + 1] = o01 / den0
    attn_out[ob0 + 2] = o02 / den0
    attn_out[ob0 + 3] = o03 / den0
    if act1:
        var ob1 = m1 * n_q + h * d_head + e0
        attn_out[ob1 + 0] = o10 / den1
        attn_out[ob1 + 1] = o11 / den1
        attn_out[ob1 + 2] = o12 / den1
        attn_out[ob1 + 3] = o13 / den1
    if act2:
        var ob2 = m2 * n_q + h * d_head + e0
        attn_out[ob2 + 0] = o20 / den2
        attn_out[ob2 + 1] = o21 / den2
        attn_out[ob2 + 2] = o22 / den2
        attn_out[ob2 + 3] = o23 / den2
    if act3:
        var ob3 = m3 * n_q + h * d_head + e0
        attn_out[ob3 + 0] = o30 / den3
        attn_out[ob3 + 1] = o31 / den3
        attn_out[ob3 + 2] = o32 / den3
        attn_out[ob3 + 3] = o33 / den3
