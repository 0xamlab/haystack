"""attention_forge.grouped_fa_q8_k32_h2_sg8 -- Attention Compiler Plan v1.0, Phase 2A Round 1,
CANDIDATE A: grouped-head fused FlashAttention. Two GQA-sibling query heads sharing ONE K/V head
LOAD (staged into shared memory exactly once per K-tile, then consumed by BOTH heads) instead of
`parity_replica.mojo`'s one-head-per-dispatch organization -- the axis this candidate is built to
measure is whether halving K/V shared-memory staging traffic (one load serves two heads) beats the
extra bookkeeping of running two heads' online-softmax recurrences side by side in one threadgroup.

CONCRETE VARIANT SHIPPED, AND WHY IT DEVIATES FROM THE PLAN'S "AGGRESSIVE" SCHEDULE
-------------------------------------------------------------------------------------
The plan's own concrete first schedule for Candidate A is `q16/h2/k64/d128/sg8`: Q_TILE=16 PER
HEAD (two 8-row sub-blocks per head, four logical 8-row blocks total = 32 combined rows), 2 SIMD
groups per row block (a pair splits QK by KEY range and PV by OUTPUT-DIM range), K_TILE=64. That
schedule's own register-pressure risk -- explicitly called out in the plan ("8 output fragments
per SG at k64") -- comes from wanting the running PV accumulator (`O` in the online-softmax
recurrence) to live in PER-SG REGISTERS, persisted across the whole K-tile loop via
`_frag_row_col`-style per-lane row bookkeeping (the same technique `mma_forge/mm8.mojo`'s
`_gemm_accum_mma8x8_narrow` uses to seed/store an MMA accumulator straight from/to a DEVICE
pointer) -- because a SHARED-MEMORY-resident `O` accumulator sized for all 32 combined rows, at
F32, does not fit the 32KiB threadgroup budget alongside `sq`/`skv`/`ss`/`sp` at ANY K_TILE this
session tried (worked out by hand below). Implementing that register-resident accumulator
correctly -- extending `_frag_row_col`'s per-lane (row, col) formula through the online-softmax
rescale step, which `mm8.mojo` never needed because its accumulator carries no per-row rescale --
was assessed as materially higher implementation risk than this deliverable's correctness bar
justifies in the available time. So: **this file implements one of the plan's OWN explicitly
named fallback points in the Round-1 sweep** ("A variants q8/q16 x k32/k64 x sg4/sg8 (h2)",
Implementation sequence, PR 4) -- `q8` (Q_TILE=8 PER HEAD, one 8-row sub-block per head, not two),
`k32` (K_TILE=32, not 64), `sg8` (8 SIMD groups / 256 threads, still used fully -- see below), `h2`
(two sibling heads per dispatch, one shared K/V load) -- keeping the SAME proven
shared-memory-resident `O` accumulator technique `parity_replica.mojo` already uses (lowest
implementation risk, directly reusable), which fits comfortably at this smaller shape. This is a
real, itemized, honestly-reported scope cut, not a silent substitution.

Worked shared-memory budget (why q16/k64 does not fit, and why q8/k32 does):
- `so` (F32 running output accumulator) alone at 32 combined rows x 128 dims x 4B = 16384B; adding
  `sq` (32 x 128 x 2B F16 = 8192B) already reaches 24576B, leaving only 8192B for `skv`+`ss`+`sp`+
  scalars -- `skv` alone at K_TILE=64 (128 x 64 x 2B = 16384B) blows the remaining budget by itself,
  and even at K_TILE=32 (128 x 32 x 2B = 8192B) leaves zero room for `ss`/`sp`. q16/h2 simply cannot
  keep a shared-memory-resident `O` for both heads' full 32 rows AND a K/V tile AND score/prob
  scratch under 32KiB at any K_TILE -- hence needing the register-resident accumulator this file
  does not attempt.
- At q8/h2 (16 combined rows, this file's shape), K_TILE=32: `sq` 16x128x2B=4096B, `so`
  16x128x4B=8192B, `skv` 128x32x2B=8192B (STAGED ONCE, shared by both heads -- the whole point),
  `ss` 16x32x4B=2048B, `sp` 16x32x2B=1024B, `s_corr`/`s_l` 16x4B each = 64B+64B. Total = 23680B
  (~23.1KiB), comfortably under the 32KiB static threadgroup-memory limit, with ~9KiB of headroom
  this session chose not to spend chasing K_TILE=64 (34944B there, per the same arithmetic --
  still over budget by ~2.2KiB) given q8/k32/h2/sg8 already faithfully demonstrates the candidate's
  core claim (one K/V load consumed by two heads).

Grid and SIMD-group organization ("sg8" is genuinely used, not padding): `block_idx.x` encodes
`(q_block, pair_idx)` -- `pair_idx` ranges over `h_q // 2`, and this dispatch's two sibling heads
are `h0 = pair_idx*2`, `h1 = h0+1`, sharing KV head `hk = h0 // group` (`group = h_q // h_kv`; this
generalizes beyond group=2 as long as `group` is even, which holds for every GQA config this plan
targets, including Qwen3-0.6B-Base's group=2). Of the 8 SIMD groups (256 threads), SGs 0-3 own
head `h0`'s 8-row block and SGs 4-7 own head `h1`'s -- `hh = sg // 4` selects the head, `sg_local =
sg % 4` plays EXACTLY the role `parity_replica.mojo`'s own `sg` (0..3) plays for a single head:
`sg_local` owns one 8-key QK column-block (K_TILE=32 / 8 = 4 column-blocks = 4 SGs, one each --
simpler than parity's 2-per-SG at K_TILE=64/4SGs), 2 softmax-owned rows (`r0=sg_local*2,
r1=r0+1`), and one 32-wide PV output-dim chunk (`sg_local*32`). Both head-groups run the identical
per-head recurrence CONCURRENTLY against the SAME staged `skv` tile -- K and V are each staged
into shared memory ONCE per K-tile iteration (by all 256 threads cooperatively, regardless of
head), then consumed by SGs 0-3 for head `h0` and SGs 4-7 for head `h1` without any second device
read -- this is the 2x K/V-staging-traffic reduction this candidate exists to prove is a net win
(measured separately from this file, per the plan's own note that latency comparisons happen
outside this task to avoid cross-run GPU contention).

Deviation from `parity_replica.mojo`'s own barrier placement, stated explicitly: this kernel adds
one EXTRA `barrier()` at the bottom of the K-tile while-loop (after the PV MMA, before the loop
back-edge re-stages K into the SAME `skv` buffer) that `parity_replica.mojo` does not have at the
equivalent point. Reasoning: `parity_replica.mojo`'s own K-tile loop restages K/V into `skv` via
ALL SIMD groups cooperatively (`idx = tid + s*_NTHREADS`, striding across every SG's thread range),
while the immediately-preceding PV MMA reads `skv` (V data) via each SG's OWN disjoint
`col_blk_d`-range fragment loads -- meaning a straggling SIMD group's PV read and another SIMD
group's next-iteration K write can, in principle, touch overlapping shared memory addresses without
an intervening synchronization point. This candidate has TWICE the SIMD-group count of
`parity_replica.mojo` (8 vs 4) sharing the SAME `skv` tile across two independent per-head
recurrences, which only widens that theoretical window -- so this file closes it explicitly with
one more `barrier()` than the read-only reference uses, at negligible cost, rather than inheriting
an assumption this session did not need to take on faith. (`parity_replica.mojo` itself is treated
as read-only and unmodified per this task's constraints; this is not a claim that it is wrong, only
that this candidate does not need to take the same risk.)

Everything else -- F16 K/V storage, F32 softmax state (`m`/`l` running max/sum, kept as per-SG
registers exactly like `parity_replica.mojo`), hardware MMA for both QK^T and PV, analytic
causal/ragged masking (`j < n_tok_k and j <= pos_base+i`, no additional key offset), the 5-step
`shuffle_xor` max butterfly, `Int64`-typed kernel scalar arguments, `Int(...)`-wrapped
pointer/index arithmetic -- is `parity_replica.mojo`'s own proven pattern, reused directly per this
task's own instruction to do so wherever the algorithm doesn't require something different.
"""
from std.gpu import thread_idx, block_idx
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp, log
from std.gpu.primitives.warp import shuffle_xor as _shuffle_xor, sum as _warp_sum
from max.gpu.compute.arch.mma_apple import (
    _mma_apple_8x8,
    apple_mma_load_8x8,
    apple_mma_store_8x8,
)

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _D: Int64 = 128
comptime _QT: Int64 = 8
"""Per-head query tile: one 8-row block per sibling head per dispatch (the `q8` fallback -- see
module docstring -- from the plan's aggressive `q16` two-sub-block-per-head schedule)."""
comptime _KT: Int64 = 32
"""K_TILE fallback from the plan's aggressive 64, for shared-memory budget -- see module
docstring's worked arithmetic."""
comptime _NSG_PER_HEAD: Int64 = 4
comptime _NSG: Int64 = 8
comptime _NTHREADS: Int64 = 256
comptime _NROWS: Int64 = _QT * 2
"""Combined rows across BOTH sibling heads sharing this dispatch's one K/V load: 16."""
comptime _NEG_MASK: Float32 = -1.0e9
comptime _NEG_SENTINEL: Float32 = -3.0e38


def _attn_grouped_fa_kernel(
    out_ptr: _FP, lse_ptr: _FP,
    q_ptr: _F16P, k_ptr: _F16P, v_ptr: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    scale: Float32, pos_base: Int64,
):
    var sq = stack_allocation[Int(_NROWS * _D), DType.float16, address_space = AddressSpace.SHARED]()
    var so = stack_allocation[Int(_NROWS * _D), DType.float32, address_space = AddressSpace.SHARED]()
    var skv = stack_allocation[Int(_D * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var ss = stack_allocation[Int(_NROWS * _KT), DType.float32, address_space = AddressSpace.SHARED]()
    var sp = stack_allocation[Int(_NROWS * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var s_corr = stack_allocation[Int(_NROWS), DType.float32, address_space = AddressSpace.SHARED]()
    var s_l = stack_allocation[Int(_NROWS), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32
    var lane = tid % 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var pair_idx = bidx // n_q_blocks
    var group = h_q // h_kv
    var h0 = pair_idx * 2
    var h1 = h0 + 1
    var hk = h0 // group

    var row0 = q_block * _QT

    # Q load: both sibling heads' 8-row blocks, at the SAME query positions row0..row0+7 --
    # combined row index cr = hh*_QT + r_local packs head hh's row r_local into one buffer.
    for s in range(Int64(8)):
        var idx = tid + s * _NTHREADS
        var cr = idx // _D
        var d = idx % _D
        var hh_l = cr // _QT
        var r_l = cr % _QT
        var h_sel = h0 if hh_l == 0 else h1
        var gi = row0 + r_l
        if gi < n_tok_q:
            sq[Int(idx)] = q_ptr[Int((gi * h_q + h_sel) * _D + d)]
        else:
            sq[Int(idx)] = Float16(0.0)
        so[Int(idx)] = Float32(0.0)

    var hh = sg // _NSG_PER_HEAD
    var sg_local = sg % _NSG_PER_HEAD
    var h = h0 if hh == 0 else h1
    var r0 = sg_local * 2
    var r1 = r0 + 1
    var cr0 = hh * _QT + r0
    var cr1 = hh * _QT + r1

    var m0 = _NEG_SENTINEL
    var m1 = _NEG_SENTINEL
    var l0 = Float32(0.0)
    var l1 = Float32(0.0)

    barrier()

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

    var j0: Int64 = 0
    while j0 <= kv_upper:
        var nb = _KT if (_KT < n_tok_k - j0) else (n_tok_k - j0)

        # Stage K, transposed [D, KT], ONCE for this tile -- consumed by BOTH sibling heads below.
        for s in range(Int64(16)):
            var idx = tid + s * _NTHREADS
            var d = idx // _KT
            var kk = idx % _KT
            var gk = j0 + kk
            if kk < nb:
                skv[Int(idx)] = k_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        # QK^T: this SG's head (hh), one 8-key column block (sg_local owns [sg_local*8,+8)),
        # all 8 of that head's local rows via the a_frag row-offset hh*_QT*_D.
        var col_blk = sg_local
        var acc = SIMD[DType.float32, 2](0.0, 0.0)
        for dstep in range(Int64(16)):
            var a_frag = apple_mma_load_8x8[DType.float16](sq + Int(hh * _QT * _D + dstep * 8), Int(_D))
            var b_frag = apple_mma_load_8x8[DType.float16](skv + Int(dstep * 8 * _KT + col_blk * 8), Int(_KT))
            _mma_apple_8x8(acc, a_frag, b_frag, acc)
        apple_mma_store_8x8[DType.float32](ss + Int(hh * _QT * _KT + col_blk * 8), Int(_KT), acc)

        barrier()

        # Softmax update: this SG's 2 owned rows; K_TILE == warp size, so each lane owns exactly
        # one key column (simpler than parity_replica's 2-per-lane at K_TILE=64).
        for which in range(Int64(2)):
            var cr = cr0 if which == 0 else cr1
            var r_local = r0 if which == 0 else r1
            var c = lane
            var gk = j0 + c
            var raw = ss[Int(cr * _KT + c)]
            var qpos = pos_base + row0 + r_local
            var vis = (gk < n_tok_k) and (gk <= qpos)
            var s_val = raw * scale if vis else _NEG_MASK

            var local_max = s_val
            var off: UInt32 = 16
            while off > 0:
                var other = _shuffle_xor(local_max, off)
                if other > local_max:
                    local_max = other
                off //= 2

            var m_old = m0 if which == 0 else m1
            var m_new = local_max if local_max > m_old else m_old
            var corr = exp(m_old - m_new)
            var e = exp(s_val - m_new)
            var block_sum = _warp_sum(e)
            var l_old = l0 if which == 0 else l1
            var l_new = l_old * corr + block_sum

            sp[Int(cr * _KT + c)] = Float16(e)
            if lane == 0:
                s_corr[Int(cr)] = corr

            if which == 0:
                m0 = m_new
                l0 = l_new
            else:
                m1 = m_new
                l1 = l_new

        barrier()

        # Stage V, natural [KT, D], ONCE for this tile -- consumed by BOTH sibling heads below.
        for s in range(Int64(16)):
            var idx = tid + s * _NTHREADS
            var kk = idx // _D
            var d = idx % _D
            var gk = j0 + kk
            if kk < nb:
                skv[Int(idx)] = v_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        # Rescale THIS head's own output-accumulator rows by this iteration's corr -- disjoint
        # per (hh, sg_local), matching parity_replica.mojo's own per-SG rescale exactly.
        for e in range(Int64(8)):
            var idx = lane + e * 32
            var rr = idx // 32
            var dd = idx % 32
            var col = sg_local * 32 + dd
            var cr_rs = hh * _QT + rr
            var corr_r = s_corr[Int(cr_rs)]
            so[Int(cr_rs * _D + col)] = so[Int(cr_rs * _D + col)] * corr_r

        barrier()

        # PV: this SG's head (hh), one 32-wide output-dim chunk, all 8 of that head's rows, all
        # KT keys -- p_frag's row-offset hh*_QT*_KT selects this head's own probability rows;
        # v_frag reads the SAME shared skv tile every SG (of both heads) just staged once above.
        for cb in range(Int64(4)):
            var col_blk_d = sg_local * 4 + cb
            var seed = apple_mma_load_8x8[DType.float32](so + Int(hh * _QT * _D + col_blk_d * 8), Int(_D))
            var acc2 = seed
            for kstep in range(Int64(4)):
                var p_frag = apple_mma_load_8x8[DType.float16](sp + Int(hh * _QT * _KT + kstep * 8), Int(_KT))
                var v_frag = apple_mma_load_8x8[DType.float16](skv + Int(kstep * 8 * _D + col_blk_d * 8), Int(_D))
                _mma_apple_8x8(acc2, p_frag, v_frag, acc2)
            apple_mma_store_8x8[DType.float32](so + Int(hh * _QT * _D + col_blk_d * 8), Int(_D), acc2)

        # Extra safety barrier vs. parity_replica.mojo's own loop back-edge -- see module
        # docstring's "Deviation from parity_replica.mojo's own barrier placement" section.
        barrier()

        j0 += _KT

    if lane == 0:
        s_l[Int(cr0)] = l0
        s_l[Int(cr1)] = l1

    barrier()

    for which in range(Int64(2)):
        var r_local = r0 if which == 0 else r1
        var gi = row0 + r_local
        if gi < n_tok_q and lane == 0:
            var mm = m0 if which == 0 else m1
            var ll = l0 if which == 0 else l1
            lse_ptr[Int(h * n_tok_q + gi)] = (mm + log(ll)) if ll > 0.0 else _NEG_SENTINEL

    for e in range(Int64(8)):
        var idx = lane + e * 32
        var rr = idx // 32
        var dd = idx % 32
        var col = sg_local * 32 + dd
        var cr_out = hh * _QT + rr
        var gi = row0 + rr
        if gi < n_tok_q:
            var ll = s_l[Int(cr_out)]
            var val = so[Int(cr_out * _D + col)]
            out_ptr[Int((gi * h_q + h) * _D + col)] = (val / ll) if ll > 0.0 else Float32(0.0)
