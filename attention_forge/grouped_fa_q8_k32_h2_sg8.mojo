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
per-head recurrence CONCURRENTLY against the SAME K/V tile -- ONE K-tile's worth of K/V data is
read ONCE per K-tile iteration and consumed by SGs 0-3 for head `h0` and SGs 4-7 for head `h1`
without any second device read -- this is the 2x K/V-read-traffic reduction this candidate exists
to prove is a net win (measured separately from this file, per the plan's own note that latency
comparisons happen outside this task to avoid cross-run GPU contention). (Historical note: at the
time this paragraph was first written, "read once" meant "staged into shared memory `skv` once";
per the "K/V CONSUMPTION UPDATE" section below, K has since moved to a device-direct MMA load with
no shared-memory staging at all, while V still stages into `skv` once per tile exactly as
described here -- the "read once, consumed by both heads" claim itself is unchanged for either.)

Deviation from `parity_replica.mojo`'s own barrier placement, stated explicitly: this kernel adds
one EXTRA `barrier()` at the bottom of the K-tile while-loop (after the PV MMA, before the loop
back-edge re-stages V into the SAME `skv` buffer) that `parity_replica.mojo` does not have at the
equivalent point. Reasoning: `parity_replica.mojo`'s own K-tile loop restages K/V into `skv` via
ALL SIMD groups cooperatively (`idx = tid + s*_NTHREADS`, striding across every SG's thread range),
while the immediately-preceding PV MMA reads `skv` (V data) via each SG's OWN disjoint
`col_blk_d`-range fragment loads -- meaning a straggling SIMD group's PV read and another SIMD
group's next-iteration V write can, in principle, touch overlapping shared memory addresses without
an intervening synchronization point. This candidate has TWICE the SIMD-group count of
`parity_replica.mojo` (8 vs 4) sharing the SAME `skv` tile across two independent per-head
recurrences, which only widens that theoretical window -- so this file closes it explicitly with
one more `barrier()` than the read-only reference uses, at negligible cost, rather than inheriting
an assumption this session did not need to take on faith. (`parity_replica.mojo` itself is treated
as read-only and unmodified per this task's constraints; this is not a claim that it is wrong, only
that this candidate does not need to take the same risk.) This reasoning was written when `skv`
staged BOTH K and V every iteration; it still holds verbatim for V now that K has moved to
device-direct loads (see below) -- `skv` is V-only now, but the same straggler/restage hazard this
barrier closes is unchanged for V's own restaging.

Everything else -- F16 K/V storage, F32 softmax state (`m`/`l` running max/sum, kept as per-SG
registers exactly like `parity_replica.mojo`), hardware MMA for both QK^T and PV, analytic
causal/ragged masking (`j < n_tok_k and j <= pos_base+i`, no additional key offset), the 5-step
`shuffle_xor` max butterfly, `Int64`-typed kernel scalar arguments, `Int(...)`-wrapped
pointer/index arithmetic -- is `parity_replica.mojo`'s own proven pattern, reused directly per this
task's own instruction to do so wherever the algorithm doesn't require something different.

K/V CONSUMPTION UPDATE (Attention Compiler Plan v1.0, Phase 2B wiring): NATIVE PACKED LAYOUT,
NOT NATURAL [position][kv_head][d_head]
-------------------------------------------------------------------------------------------------
`q_ptr`/`k_ptr`/`v_ptr` used to all be natural `[position][kv_head][d_head]` device buffers, with
K re-staged into shared memory transposed (`d = idx // _KT; kk = idx % _KT`) and V re-staged
reordered (`kk = idx // _D; d = idx % _D`) every single K-tile dispatch. `k_ptr`/`v_ptr` are now
`attention_forge.abi.KV_LAYOUT_NATIVE_PACKED_V2`-shaped buffers -- the exact layout
`native_kv_producer.mojo`'s `_native_kv_producer_kernel` writes, at `key_block_size=32` (== this
file's own `_KT`, by construction, so every K-tile iteration maps to EXACTLY one native block, no
remainder ever needed):

  K: `((hk * n_blocks + block) * _D + d) * _KT + kk`  -- `[kv_head][key_block][d_chunk][key_in_block]`
  V: `((hk * n_blocks + block) * _KT + kk) * _D + d`  -- `[kv_head][key_block][key_in_block][d_chunk]`

`n_blocks` is a NEW kernel parameter (the packed buffer's own per-`kv_head` block count, a property
of how the caller sized the scratch buffer -- see `native_kv_producer.mojo`'s docstring item 5 for
why this can't be derived from any other argument). `block = j0 // _KT` is exact with zero
remainder because `j0` starts at 0 and increments by exactly `_KT` every iteration -- the same
`pos // key_block_size` convention the producer uses, at the same block size, so this kernel's own
per-tile block index and the producer's own per-position block index always agree.

Caller contract: `n_blocks` must be `>= ceil(n_tok_k / _KT)` -- large enough to cover every
position this dispatch's own `kv_upper` can reach -- otherwise a `block` computed above indexes
outside the allocated K/V buffer. This is a new obligation, but the same KIND of obligation the
old natural-layout kernel already had implicitly (that `k_ptr`/`v_ptr` be sized to at least
`n_tok_k * h_kv * d_head` elements) -- not a new category of caller trust, just a differently
shaped one.

K: DEVICE-DIRECT MMA LOAD, NO SHARED-MEMORY STAGING AT ALL. The old "stage K, transposed" loop
(and the `barrier()` that guarded it) is gone -- `apple_mma_load_8x8[DType.float16]` now reads the
QK^T "B" operand straight from `k_ptr`, a per-thread-group READ-ONLY device buffer, so no
producer/consumer hazard exists between threads and no barrier is needed at that point (the
`barrier()` immediately after QK^T-store, before the softmax read of `ss`, is untouched -- that one
guards a real intra-threadgroup hazard, unrelated to K staging). This choice was made, not merely
attempted and left in a hopeful state: Phase 2B's own `native_kv_producer_driver.mojo` already
proved `apple_mma_load_8x8[DType.float16]` against a device (non-shared) pointer is exact-correct
at runtime (`worst abs diff = 0.0`, identity-matmul extraction, reproduced on two independent runs)
for the SAME primitive composition (`_mma_apple_8x8` with the B operand loaded off-device) this
file's own QK^T loop already uses for every OTHER load -- and this file's own driver
(`grouped_fa_q8_k32_h2_sg8_driver.mojo`) re-validates it end-to-end (not just via an isolated
identity-multiply probe) by running every existing correctness/determinism case through the real
attention math against the CPU oracle. It is SAFE even for the ragged K-tile tail (positions
`>= n_tok_k` within the last, partially-filled native block, whose bytes this kernel never
initializes and may be garbage/NaN): those columns' `raw` score is read from `ss` but the
`s_val = raw*scale if vis else _NEG_MASK` ternary NEVER assigns the `raw*scale` branch's value when
`vis` is false -- it is computed and discarded, never stored, never fed into `exp`/`m`/`l` -- so no
garbage or NaN in the unread tail of a native K block can ever reach the final output, regardless
of what bit pattern happens to live there. (This is exactly why the old kernel's explicit
`else: skv[idx] = Float16(0.0)` zero-fill for K's ragged tail was DEFENSIVE, not load-bearing --
dropping it is not a silent risk, it is removing dead-weight safety that was never actually needed
for K specifically.)

V: STILL STAGED INTO SHARED MEMORY, BUT THE COPY IS NOW TRIVIAL. V's native block
(`[key_in_block][d_chunk]`) is byte-identical, in order AND address arithmetic, to what `skv`
already needs (`skv[idx] = v_ptr[v_block_off + idx]`, a single add, no `d`/`kk` recombination at
all) -- this removes the reorder/transpose-adjacent index math the old natural-layout gather did
(`(gk*h_kv+hk)*_D+d`), even though V's old gather was already axis-order-preserving and never
needed a true transpose. The boundary zero-fill (`kk < nb`) is KEPT for V, deliberately NOT dropped
the way K's was: V's masked contribution is a REAL multiply-by-probability inside the PV MMA sum
(`p_frag * v_frag`, `p ≈ 0` for masked keys, not a discarded ternary branch), and IEEE754
`0.0 * NaN == NaN` -- an unguarded read of a garbage/NaN tail byte would corrupt the ENTIRE output
row's accumulator, not just one discarded scalar. K and V are NOT treated the same way here on
purpose; this asymmetry is itemized, not an oversight.
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
comptime _QT: Int64 = 16
"""Per-head query tile, raised 8 -> 16 on 2026-08-11 to halve deep-KV re-read traffic (each
threadgroup now re-reads the KV cache for 16 query rows instead of 8). The output accumulator moved
OUT of shared memory into per-lane registers to free the budget this doubles (see module docstring
and the register-resident `o_*` accumulators below). NOTE: the file/module name still says `q8`
(legacy); the kernel is Q_TILE=16."""
comptime _KT: Int64 = 32
"""K_TILE fallback from the plan's aggressive 64, for shared-memory budget -- see module
docstring's worked arithmetic."""
comptime _NSG_PER_HEAD: Int64 = 4
comptime _NSG: Int64 = 8
comptime _NTHREADS: Int64 = 256
comptime _NROWS: Int64 = _QT * 2
"""Combined rows across BOTH sibling heads sharing this dispatch's one K/V load: 32."""
comptime _NEG_MASK: Float32 = -1.0e9
comptime _NEG_SENTINEL: Float32 = -3.0e38


def _frag_row_col(tid: Int64) -> SIMD[DType.int64, 2]:
    """This lane's (row_lo, col_base) within its 8x8 MMA fragment -- the SAME per-lane mapping
    `apple_mma_load_8x8`/`apple_mma_store_8x8` use internally, copied verbatim from
    `mma_forge/mm8.mojo`'s `_frag_row_col` (this file does not import mma_forge). Needed by the
    register-resident output accumulator to know which row/col each lane owns for the per-row corr
    rescale and the bounds-checked final store."""
    var lane = tid % 32
    var row_lo = ((lane & 6) >> 1) + ((lane & 16) >> 2)
    var col_base = ((lane & 1) << 1) + ((lane & 8) >> 1)
    return SIMD[DType.int64, 2](row_lo, col_base)


def _attn_grouped_fa_kernel(
    out_ptr: _FP, lse_ptr: _FP,
    q_ptr: _F16P, k_ptr: _F16P, v_ptr: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    scale: Float32, pos_base: Int64, n_blocks: Int64,
):
    var sq = stack_allocation[Int(_NROWS * _D), DType.float16, address_space = AddressSpace.SHARED]()
    # NOTE: the output accumulator `so` (previously [_NROWS,_D] F32 in shared memory) is now
    # REGISTER-RESIDENT (the `o_*` SIMD accumulators declared below) -- at Q_TILE=16 the shared
    # budget cannot hold it, so it moved to per-lane registers (see module docstring).
    # `skv` is now V-ONLY -- K reads device-direct (see module docstring), so this buffer is never
    # written for K at all anymore; kept at the same size/name (still sized for a full [_D,_KT] or
    # [_KT,_D] tile, both equal at 4096 elements) to minimize churn on the rest of the file.
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

    # Q load: both sibling heads' 16-row blocks, at the SAME query positions row0..row0+15 --
    # combined row index cr = hh*_QT + r_local packs head hh's row r_local into one buffer.
    for s in range(Int64(16)):
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

    var hh = sg // _NSG_PER_HEAD
    var sg_local = sg % _NSG_PER_HEAD
    var h = h0 if hh == 0 else h1

    # This SG's REGISTER-RESIDENT output accumulator: head hh's full 16 rows x this sg_local's
    # 32 output dims, as 2 row-blocks x 4 col-blocks of 8x8 MMA fragments (each SIMD[F32,2] is this
    # lane's owned same-row pair). Persistent across the whole K-tile loop -- the old `so` lived in
    # shared memory and was seeded/stored every tile; registers keep it resident instead.
    var o_r0_c0 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_r0_c1 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_r0_c2 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_r0_c3 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_r1_c0 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_r1_c1 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_r1_c2 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_r1_c3 = SIMD[DType.float32, 2](0.0, 0.0)
    # This lane's owned (row_lo, col_base) within each 8x8 accumulator fragment -- constant per lane.
    var rc = _frag_row_col(tid)
    var row_lo = rc[0]
    var col_base = rc[1]

    # Per-owned-row online-softmax state: this sg_local owns 4 rows (sg_local*4 .. sg_local*4+3).
    var m0 = _NEG_SENTINEL
    var m1 = _NEG_SENTINEL
    var m2 = _NEG_SENTINEL
    var m3 = _NEG_SENTINEL
    var l0 = Float32(0.0)
    var l1 = Float32(0.0)
    var l2 = Float32(0.0)
    var l3 = Float32(0.0)

    barrier()

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

    var j0: Int64 = 0
    while j0 <= kv_upper:
        var nb = _KT if (_KT < n_tok_k - j0) else (n_tok_k - j0)

        # `j0` starts at 0 and increments by exactly `_KT` every iteration, and `_KT == 32 ==
        # key_block_size` (the native producer's own block size), so `block` below is always
        # exact -- this K-tile iteration IS native block `block` of kv_head `hk`, with zero
        # remainder, never needing any re-derivation from a query-side offset.
        var block = j0 // _KT
        var k_block_off = (hk * n_blocks + block) * _D * _KT
        var v_block_off = (hk * n_blocks + block) * _KT * _D

        # QK^T: this SG's head (hh), one 8-key column block (sg_local owns [sg_local*8,+8)),
        # all 16 of that head's local rows as TWO 8-row blocks (a_frag row-offset
        # (hh*_QT + rb*8)*_D). K's "B" operand is read DEVICE-DIRECT from the native packed buffer
        # -- no shared-memory staging at all; see module docstring's "K: DEVICE-DIRECT MMA LOAD"
        # section for why this is both safe and runtime-proven, not merely type-checked.
        var col_blk = sg_local
        for rb in range(Int64(2)):
            var acc = SIMD[DType.float32, 2](0.0, 0.0)
            for dstep in range(Int64(16)):
                var a_frag = apple_mma_load_8x8[DType.float16](
                    sq + Int((hh * _QT + rb * 8) * _D + dstep * 8), Int(_D)
                )
                var b_frag = apple_mma_load_8x8[DType.float16](
                    k_ptr + Int(k_block_off + dstep * 8 * _KT + col_blk * 8), Int(_KT)
                )
                _mma_apple_8x8(acc, a_frag, b_frag, acc)
            apple_mma_store_8x8[DType.float32](
                ss + Int((hh * _QT + rb * 8) * _KT + col_blk * 8), Int(_KT), acc
            )

        barrier()

        # Softmax update: this SG's 4 owned rows (sg_local*4 .. sg_local*4+3); K_TILE == warp size,
        # so each lane owns exactly one key column (simpler than parity_replica's 2-per-lane at
        # K_TILE=64).
        for which in range(Int64(4)):
            var r_local = sg_local * 4 + which
            var cr = hh * _QT + r_local
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

            var m_old = _NEG_SENTINEL
            var l_old = Float32(0.0)
            if which == 0:
                m_old = m0
                l_old = l0
            elif which == 1:
                m_old = m1
                l_old = l1
            elif which == 2:
                m_old = m2
                l_old = l2
            else:
                m_old = m3
                l_old = l3

            var m_new = local_max if local_max > m_old else m_old
            var corr = exp(m_old - m_new)
            var e = exp(s_val - m_new)
            var block_sum = _warp_sum(e)
            var l_new = l_old * corr + block_sum

            sp[Int(cr * _KT + c)] = Float16(e)
            if lane == 0:
                s_corr[Int(cr)] = corr

            if which == 0:
                m0 = m_new
                l0 = l_new
            elif which == 1:
                m1 = m_new
                l1 = l_new
            elif which == 2:
                m2 = m_new
                l2 = l_new
            else:
                m3 = m_new
                l3 = l_new

        barrier()

        # Stage V, ONCE for this tile -- consumed by BOTH sibling heads below. The native V block's
        # own [key_in_block][d_chunk] order is byte-identical to `skv`'s own [KT,D] shape, so this
        # is now a trivial 1:1 copy (`v_block_off + idx`, no `d`/`kk` recombination at all) instead
        # of the old natural-layout gather's `(gk*h_kv+hk)*_D+d`. The `kk < nb` boundary zero-fill
        # is KEPT (unlike K's) -- see module docstring's "V: STILL STAGED" section for why V's
        # ragged tail genuinely needs it and K's did not.
        for s in range(Int64(16)):
            var idx = tid + s * _NTHREADS
            var kk = idx // _D
            if kk < nb:
                skv[Int(idx)] = v_ptr[Int(v_block_off + idx)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        # Rescale THIS head's own REGISTER-resident output accumulator by this iteration's corr.
        # Each accumulator o_r{rb}_c{cb} owns a same-row element pair; the row is
        # hh*_QT + rb*8 + row_lo, so there are two corr values (rb=0 and rb=1). s_corr holds all
        # 16 of the head's rows (populated by the 4 sg_local's softmax above), so every row this SG
        # accumulates has its corr available.
        var corr_r0 = s_corr[Int(hh * _QT + row_lo)]
        var corr_r1 = s_corr[Int(hh * _QT + 8 + row_lo)]
        o_r0_c0 = SIMD[DType.float32, 2](o_r0_c0[0] * corr_r0, o_r0_c0[1] * corr_r0)
        o_r0_c1 = SIMD[DType.float32, 2](o_r0_c1[0] * corr_r0, o_r0_c1[1] * corr_r0)
        o_r0_c2 = SIMD[DType.float32, 2](o_r0_c2[0] * corr_r0, o_r0_c2[1] * corr_r0)
        o_r0_c3 = SIMD[DType.float32, 2](o_r0_c3[0] * corr_r0, o_r0_c3[1] * corr_r0)
        o_r1_c0 = SIMD[DType.float32, 2](o_r1_c0[0] * corr_r1, o_r1_c0[1] * corr_r1)
        o_r1_c1 = SIMD[DType.float32, 2](o_r1_c1[0] * corr_r1, o_r1_c1[1] * corr_r1)
        o_r1_c2 = SIMD[DType.float32, 2](o_r1_c2[0] * corr_r1, o_r1_c2[1] * corr_r1)
        o_r1_c3 = SIMD[DType.float32, 2](o_r1_c3[0] * corr_r1, o_r1_c3[1] * corr_r1)

        barrier()

        # PV: this SG's head (hh), its 32-wide output-dim chunk (sg_local*32..+32), all 16 of that
        # head's rows (2 row-blocks), all KT keys -- accumulated into the register-resident
        # accumulators. v_frag depends only on (kstep, cb) so it is loaded once and reused for both
        # row-blocks; p_frag is per row-block. skv was staged once above, shared by all SGs.
        for kstep in range(Int64(4)):
            var v_frag0 = apple_mma_load_8x8[DType.float16](
                skv + Int(kstep * 8 * _D + (sg_local * 4) * 8), Int(_D)
            )
            var v_frag1 = apple_mma_load_8x8[DType.float16](
                skv + Int(kstep * 8 * _D + (sg_local * 4 + 1) * 8), Int(_D)
            )
            var v_frag2 = apple_mma_load_8x8[DType.float16](
                skv + Int(kstep * 8 * _D + (sg_local * 4 + 2) * 8), Int(_D)
            )
            var v_frag3 = apple_mma_load_8x8[DType.float16](
                skv + Int(kstep * 8 * _D + (sg_local * 4 + 3) * 8), Int(_D)
            )
            var p_frag_r0 = apple_mma_load_8x8[DType.float16](
                sp + Int(hh * _QT * _KT + kstep * 8), Int(_KT)
            )
            _mma_apple_8x8(o_r0_c0, p_frag_r0, v_frag0, o_r0_c0)
            _mma_apple_8x8(o_r0_c1, p_frag_r0, v_frag1, o_r0_c1)
            _mma_apple_8x8(o_r0_c2, p_frag_r0, v_frag2, o_r0_c2)
            _mma_apple_8x8(o_r0_c3, p_frag_r0, v_frag3, o_r0_c3)
            var p_frag_r1 = apple_mma_load_8x8[DType.float16](
                sp + Int((hh * _QT + 8) * _KT + kstep * 8), Int(_KT)
            )
            _mma_apple_8x8(o_r1_c0, p_frag_r1, v_frag0, o_r1_c0)
            _mma_apple_8x8(o_r1_c1, p_frag_r1, v_frag1, o_r1_c1)
            _mma_apple_8x8(o_r1_c2, p_frag_r1, v_frag2, o_r1_c2)
            _mma_apple_8x8(o_r1_c3, p_frag_r1, v_frag3, o_r1_c3)

        # Extra safety barrier vs. parity_replica.mojo's own loop back-edge -- see module
        # docstring's "Deviation from parity_replica.mojo's own barrier placement" section.
        barrier()

        j0 += _KT

    # Write the normalizers l for this sg_local's 4 softmax-owned rows (sg_local*4 .. +3).
    if lane == 0:
        s_l[Int(hh * _QT + sg_local * 4)] = l0
        s_l[Int(hh * _QT + sg_local * 4 + 1)] = l1
        s_l[Int(hh * _QT + sg_local * 4 + 2)] = l2
        s_l[Int(hh * _QT + sg_local * 4 + 3)] = l3

    barrier()

    # lse for this sg_local's 4 softmax-owned rows.
    for which in range(Int64(4)):
        var r_local = sg_local * 4 + which
        var gi = row0 + r_local
        if gi < n_tok_q and lane == 0:
            var mm = m0
            var ll = l0
            if which == 1:
                mm = m1
                ll = l1
            elif which == 2:
                mm = m2
                ll = l2
            elif which == 3:
                mm = m3
                ll = l3
            lse_ptr[Int(h * n_tok_q + gi)] = (mm + log(ll)) if ll > 0.0 else _NEG_SENTINEL

    # Output from the REGISTER-resident accumulators: this sg_local writes all 16 of the head's rows
    # for its own 32 output dims. rb=0 -> head-row row_lo, rb=1 -> head-row 8+row_lo; cb -> col
    # offset (sg_local*4+cb)*8 + col_base. s_l for every row was populated by the combined softmax
    # of the 4 sg_local above.
    var base_col = (sg_local * 4) * 8 + col_base
    # rb = 0
    var gi_r0 = row0 + row_lo
    if gi_r0 < n_tok_q:
        var ll_r0 = s_l[Int(hh * _QT + row_lo)]
        var out_base_r0 = (gi_r0 * h_q + h) * _D + base_col
        for cb in range(Int64(4)):
            var v0 = Float32(0.0)
            var v1 = Float32(0.0)
            if cb == 0:
                v0 = o_r0_c0[0]
                v1 = o_r0_c0[1]
            elif cb == 1:
                v0 = o_r0_c1[0]
                v1 = o_r0_c1[1]
            elif cb == 2:
                v0 = o_r0_c2[0]
                v1 = o_r0_c2[1]
            else:
                v0 = o_r0_c3[0]
                v1 = o_r0_c3[1]
            if ll_r0 > 0.0:
                out_ptr[Int(out_base_r0 + cb * 8)] = v0 / ll_r0
                out_ptr[Int(out_base_r0 + cb * 8 + 1)] = v1 / ll_r0
            else:
                out_ptr[Int(out_base_r0 + cb * 8)] = Float32(0.0)
                out_ptr[Int(out_base_r0 + cb * 8 + 1)] = Float32(0.0)
    # rb = 1
    var gi_r1 = row0 + 8 + row_lo
    if gi_r1 < n_tok_q:
        var ll_r1 = s_l[Int(hh * _QT + 8 + row_lo)]
        var out_base_r1 = (gi_r1 * h_q + h) * _D + base_col
        for cb in range(Int64(4)):
            var v0 = Float32(0.0)
            var v1 = Float32(0.0)
            if cb == 0:
                v0 = o_r1_c0[0]
                v1 = o_r1_c0[1]
            elif cb == 1:
                v0 = o_r1_c1[0]
                v1 = o_r1_c1[1]
            elif cb == 2:
                v0 = o_r1_c2[0]
                v1 = o_r1_c2[1]
            else:
                v0 = o_r1_c3[0]
                v1 = o_r1_c3[1]
            if ll_r1 > 0.0:
                out_ptr[Int(out_base_r1 + cb * 8)] = v0 / ll_r1
                out_ptr[Int(out_base_r1 + cb * 8 + 1)] = v1 / ll_r1
            else:
                out_ptr[Int(out_base_r1 + cb * 8)] = Float32(0.0)
                out_ptr[Int(out_base_r1 + cb * 8 + 1)] = Float32(0.0)
