"""attention_forge.splitk_fa -- Attention Compiler Plan v1.0, Phase 2A (Round 1 screening),
Candidate C: associative GROUPED-HEAD split-K FlashAttention. Same per-tile QK^T/softmax/PV math as
`parity_replica.mojo` (Q_TILE=8/head, K_TILE=64, F16 K/V, F32 running-softmax state, hardware MMA for
BOTH matmuls, analytic causal masking, GQA head mapping) -- the difference is twofold, and BOTH parts
are this candidate's own defining features, per the tournament table's `agfa_splitk_q8_k64_h2_s2_sg4`
label:

1. **Split-K**: the KEY range for a given (Q-block, sibling-head-pair) is SPLIT across `n_splits`
   independent threadgroups, each producing an UNNORMALIZED partial state `(m_s, l_s, o_s)` over only
   its own key sub-range, and a SEPARATE merge kernel combines every split's partial into the final
   normalized output via the associative online-softmax identity `m = max(m_s); l = sum(l_s *
   exp(m_s - m)); o = sum(o_s * exp(m_s - m)); O = o / l` -- the exact identity
   `mojo/engine/residentk/kernels.mojo`'s own decode-time `_splitk_partial_kernel_simd` /
   `_splitk_merge_kernel_simd` pair already ships in production, here adapted from that kernel's
   per-key scalar-dot-product single-row shape to this plan's per-tile hardware-MMA Q_TILE=8-row
   shape.
2. **Grouped-head (H_TILE=2)**: two GQA-sibling query heads sharing ONE K/V head LOAD -- staged into
   shared memory ONCE per K-tile iteration (by all threads cooperatively), then consumed by BOTH
   heads' independent per-head online-softmax recurrences -- exactly `grouped_fa_q8_k32_h2_sg8.mojo`'s
   (Candidate A's) own technique, reused here directly.

**CORRECTION, 2026-08-07 (Phase 2A Round 1 adversarial review):** the version of this file merged
earlier shipped H_TILE=1 (one query head per threadgroup) -- it implemented split-K faithfully but
dropped the grouped-head half of the candidate's own spec entirely, which the review correctly
flagged as "Candidate C simply didn't build it." This file now implements BOTH halves together, as
the tournament label always specified. Mixing split-K and grouped-head in one kernel is NOT a
violation of the plan's "never combine five unmeasured modifications" stop rule -- both are this ONE
named candidate's own two defining axes, not two different candidates' features glued together;
Candidate A (grouped-head only, H_TILE=1... erm H_TILE=2 but no split) and the tournament's
score-slab candidate (Candidate B) remain the OTHER points in the 3-candidate design space that keep
each axis separately measurable.

Two kernels, two dispatches, no cross-threadgroup synchronization attempted between them (there is
no primitive for that on this hardware -- the merge is a second, independent kernel that reads
every split's own scratch write from device memory, exactly as the residentk precedent's own
docstring establishes):

1. `_attn_splitk_partial_kernel` -- one threadgroup per `(q_block, pair_idx, split)` triple, where
   `pair_idx` ranges over `h_q // 2` GQA-sibling head pairs (`h0 = pair_idx*2`, `h1 = h0+1`, shared
   KV head `hk = h0 // group`, `group = h_q // h_kv` -- generalizes to any even `group`, exactly as
   Candidate A's own docstring establishes; this plan's own Qwen3-0.6B-Base shape has `group=2`).
   Computes the SAME block-tiled online-softmax recurrence `parity_replica.mojo` runs over the WHOLE
   causal window, but bounded to only this split's own key sub-range -- so the recurrence still runs
   internally (possibly across several `K_TILE=64` iterations) whenever a split's own sub-range is
   wider than one K-tile, exactly as this candidate's own spec requires. Writes its own unnormalized
   `(m_s, l_s, o_s)` to a per-`(row, head, split)` device scratch buffer -- INDEPENDENTLY for h0 and
   h1, at their own separate `(row, head, split)` slots -- never divides by `l_s`; never reads
   another split's data. Of the 8 SIMD groups (256 threads), SGs 0-3 own sibling head `h0`'s
   row/column-block work and SGs 4-7 own `h1`'s (`hh = sg // 4` selects the head, `sg_local = sg % 4`
   plays exactly the role Candidate A's own `sg_local` plays, and exactly the role
   `parity_replica.mojo`'s single-head `sg` plays): K and V are staged into shared memory ONCE per
   K-tile iteration by ALL 256 threads cooperatively (regardless of head), then consumed by both
   head-groups' independent recurrences against the SAME staged tile -- the 2x K/V-staging-traffic
   reduction this candidate exists to prove is a net win when combined with split-K's own smaller
   per-threadgroup device-scratch write, measured separately from this file per the plan's own note
   that latency comparisons happen outside this task.
2. `_attn_splitk_merge_kernel` -- UNCHANGED by this correction (see below for why). One threadgroup
   per `(row, head)` pair, one thread per output dimension `e` (`block_dim=128`, mirroring
   `_splitk_merge_kernel_simd`'s own `block_dim=d_head` no-barrier-needed design). Folds every split
   into one normalized `(out, lse)` pair via the associative identity above.

**Why the merge kernel needs, and receives, NO changes.** `_attn_splitk_merge_kernel`'s own grid is
`(row, ANY head)` -- `bidx = row * h_q + h`, and its scratch-buffer indexing `pidx = (row * h_q + h) *
n_splits + s` is defined purely in terms of `h_q`, `n_splits`, and the actual head index `h`, with
zero reference to how the PARTIAL kernel organized its OWN dispatches (pairs vs. singles, which SIMD
groups computed which head). The merge kernel's correctness depends on exactly one contract from the
partial kernel: that EVERY individual head slot `h` in `[0, h_q)`, for every `(row, split)`, gets its
own correctly-populated `m_out[pidx]`/`l_out[pidx]`/`o_out[pidx*128+e]` -- which the corrected partial
kernel still provides, now writing h0's slots from SGs 0-3's registers and h1's slots from SGs 4-7's
registers instead of one dispatch-wide `h` shared by all 4 SGs. Re-read in full before this claim was
trusted (not assumed): confirmed no line of `_attn_splitk_merge_kernel` references pairing, SIMD-group
count, or anything about the partial kernel's own internal head-grouping -- it is genuinely agnostic.

**Per-block, not per-row, split key range -- computed ONCE per dispatch, shared by BOTH sibling
heads.** A `(q_block, pair_idx)` pair's own causal upper bound is computed EXACTLY as
`parity_replica.mojo` computes it for a single head -- `q_hi = pos_base + row0 + (Q_TILE-1)`,
`kv_upper = min(n_tok_k-1, q_hi)`, `n_keys_block = kv_upper + 1` -- using the LAST row's own horizon
(the widest of the 8 rows in the tile), then `n_keys_block` is partitioned into `n_splits`
contiguous, non-overlapping, gap-free ranges via the same integer-division formula
`_splitk_partial_kernel_simd` already uses: `key_start = (n_keys_block * s) // n_splits`,
`key_end = (n_keys_block * (s + 1)) // n_splits`. This block-level bound and this split partition are
IDENTICAL for sibling heads h0 and h1 -- they share `row0` (same query positions) and `hk` (same KV
head), so both quantities are computed exactly ONCE per dispatch, not once per head, and every SIMD
group (whichever head it owns) reads the SAME `key_start`/`key_end`. Individual ROWS inside the tile
still have their own, smaller, per-row horizon (`row`'s own `qpos = pos_base + row0 + row`), so the
existing per-row `gk <= qpos` mask check inside the K-tile loop (unchanged from `parity_replica.mojo`)
still masks out keys that fall inside a split's assigned range but beyond an earlier row's own
horizon -- splitting the BLOCK's key window does not require, or receive, any change to per-row
causal correctness, and this reasoning is unaffected by which head a given SIMD group happens to own.

**Empty-split contract, identical to the residentk precedent.** When `n_splits` exceeds the number
of causally-visible keys for a block (`key_start == key_end` for some `s`), the K-tile loop runs
zero iterations and the partial state is left at its untouched initial value: `m_s = _NEG_SENTINEL`
(`-3.0e38`, a large FINITE sentinel, never IEEE `-inf`, so `exp(_NEG_SENTINEL - anything_finite)`
underflows cleanly to `0.0` rather than producing a `-inf - -inf` NaN once a real split has been
merged), `l_s = 0.0`, `o_s = 0.0` -- the exact three-value empty-split contract
`_splitk_partial_kernel_simd`'s own docstring documents and `_splitk_merge_kernel_simd` already
folds as a genuine no-op. This is per-`(row, head, split)`, unaffected by pairing: h0 and h1 in the
same pair can independently be empty or non-empty for the same split (their own per-row horizons
differ even though the BLOCK-level split range is shared).

**Threadgroup memory budget, recomputed for H_TILE=2 (worked explicitly, and actually verified
against the toolchain's own pipeline-creation error, not just hand arithmetic -- see below for why
that mattered).** This candidate's baseline per-head shape was ALREADY `Q_TILE=8/head` (matching
`parity_replica.mojo` exactly, never the aggressive `q16/head` schedule Candidate A's own docstring
worked through and had to fall back from) -- so grouping two sibling heads here means `NROWS = 16`
combined rows, the SAME combined-row count Candidate A's own DELIVERED `q8/h2` fallback shape uses.
An EARLIER version of this correction assumed `K_TILE=64` (this candidate's original single-head
K_TILE) would still fit at H_TILE=2, on the reasoning that this file's baseline per-head shape was
already smaller than Candidate A's aggressive one -- that reasoning about the SHAPE was right, but
the arithmetic itself was not (a plain addition error), and the toolchain caught it immediately at
kernel-compile time (`Threadgroup memory size (34880) exceeds the maximum threadgroup memory
allowed (32768)`) rather than silently miscompiling. Redone correctly at `K_TILE=64`:
`sq=4096B, so=8192B, skv=128*64*2B=16384B, ss=16*64*4B=4096B, sp=16*64*2B=2048B, s_corr=64B` --
`4096+8192+16384+4096+2048+64 = 34880B`, which is 2112B OVER the 32KiB ceiling, not under it. So
this file, like Candidate A, falls back to `K_TILE=32`:
  - `sq` (F16, `NROWS x D`): `16 * 128 * 2B = 4096B`
  - `so` (F32, `NROWS x D`): `16 * 128 * 4B = 8192B`
  - `skv` (F16, `D x K_TILE`, aliased for K-then-V, STAGED ONCE and shared by BOTH sibling heads --
    unaffected by H_TILE; this is exactly the traffic this candidate's grouped-head half exists to
    halve): `128 * 32 * 2B = 8192B`
  - `ss` (F32, `NROWS x K_TILE`): `16 * 32 * 4B = 2048B`
  - `sp` (F16, `NROWS x K_TILE`): `16 * 32 * 2B = 1024B`
  - `s_corr` (F32, `NROWS`): `16 * 4B = 64B`
  - Total: `4096 + 8192 + 8192 + 2048 + 1024 + 64 = 23616B` (~23.1KiB), comfortably under the 32KiB
    static-threadgroup-memory ceiling, with ~9.0KiB (`32768 - 23616 = 9152B`) of headroom to spare
    -- essentially IDENTICAL to Candidate A's own `q8/k32/h2` budget (23680B), 64B smaller here
    because this kernel only needs `s_corr` (no `s_l` -- each SG writes its own `m`/`l` straight to
    device memory at the end, never needing a shared array for a later cross-SG readback the way
    Candidate A's single normalized-output writeback does). Splitting the key range across
    `n_splits` threadgroups does NOT itself change this arithmetic -- `skv`'s per-iteration size
    depends only on `K_TILE`, not on how much of the total causal window any one threadgroup's own
    split covers -- what `n_splits` changes is per-threadgroup ITERATION COUNT (a threadgroup
    owning a narrow split runs fewer `K_TILE=32` iterations) and DEVICE memory (below), not
    per-iteration shared-memory footprint. What DOES grow on DEVICE memory (the plan's own itemized
    new cost, "partial-output scratch + merge") is `2 * n_tok_q * h_q * n_splits` F32 scalars
    (`m`/`l`) plus `n_tok_q * h_q * n_splits * 128` F32 scalars (`o`) -- e.g. at this task's
    real-dims shape (`n_tok_q=17, h_q=16, n_splits=2`) that is 1,088 F32 scalars for `m`/`l` and
    69,632 for `o`, ~275KB total device scratch, unaffected by grouping heads into pairs (this is
    per-head scratch, indexed by the individual head `h`, not by pair).

Grid for the partial kernel: `block_idx.x` flattens `(split, pair_idx, q_block)` with `q_block`
fastest (`bidx = (split * n_pairs + pair_idx) * n_q_blocks + q_block`, `n_pairs = h_q // 2`), so
`grid_dim = n_q_blocks * n_pairs * n_splits`, `block_dim=256` (8 SIMD groups, 4 per sibling head,
mirroring Candidate A's own `hh`/`sg_local` split exactly). Grid for the merge kernel: UNCHANGED,
`block_idx.x` flattens `(row, h)` (`bidx = row * h_q + h`), so `grid_dim = n_tok_q * h_q`,
`block_dim=128` (one thread per output dimension `e`, `d=128` fixed) -- `h` here ranges over
INDIVIDUAL heads, not pairs, exactly as before. Partial-scratch layout: UNCHANGED,
`pidx(row, h, s) = (row * h_q + h) * n_splits + s`; `m_out[pidx]`, `l_out[pidx]`, `o_out[pidx * 128 +
e]`, populated per INDIVIDUAL head `h` (h0 and h1 separately) by the corrected partial kernel. Both
kernels specialize to `d_qk = d_v = 128` (Qwen3-0.6B-Base), exactly as `parity_replica.mojo` does --
the same GQA head mapping and the same causal convention (key `j` visible to row `i`, absolute
position `pos_base + i`, iff `j < n_tok_k and j <= pos_base + i`) apply identically here. `h_q` must
be even (one sibling pair per KV head boundary, `group` must be even) -- the same constraint
Candidate A's own docstring and driver already state and enforce; every shape this plan targets,
including Qwen3-0.6B-Base's `group=2`, satisfies it.

Deviation from `parity_replica.mojo`'s own barrier placement, inherited from Candidate A and now
doubly warranted: this kernel adds one EXTRA `barrier()` at the bottom of the K-tile while-loop
(after the PV MMA, before the loop back-edge re-stages V into the SAME `skv` buffer) that
`parity_replica.mojo` does not have at the equivalent point. This candidate has TWICE the SIMD-group
count of `parity_replica.mojo` (8 vs 4) sharing the SAME `skv` tile across two independent per-head
recurrences, which widens the theoretical window between a straggling SIMD group's PV read and
another SIMD group's next-iteration V write -- so this file closes it explicitly, exactly as
Candidate A's own docstring reasons through for its own (non-split) grouped-head kernel.

**PHASE 2B ADAPTATION, 2026-08-07 -- consuming the native packed KV layout instead of natural
layout + per-dispatch transpose gather.** `attention_forge/native_kv_producer.mojo` (a sibling
agent's own Phase 2B work, not modified here) now writes K/V once, at QK-norm+RoPE time, into a
persistent device-resident layout this file's own `skv`-staging shapes were ALREADY byte-identical
to: K packed `[kv_head][key_block][d_chunk][key_in_block]` at flat index
`((hk*n_blocks+block)*d_head+d)*key_block_size+kk`, V packed `[kv_head][key_block][key_in_block]
[d_chunk]` at flat index `((hk*n_blocks+block)*key_block_size+kk)*d_head+d`, `key_block_size=32`
matching this candidate's own `_KT`. `_attn_splitk_partial_kernel` (the only kernel here that ever
touched K/V; the merge kernel reads only its own partial scratch, see above) now takes `k_native`/
`v_native` device pointers in THIS layout plus a caller-supplied `n_blocks` (the packed buffer's
own per-`kv_head` block stride), instead of a natural `[position][kv_head][d_head]` pointer:

  - **K: device-direct MMA load, no shared-memory staging at all.** This candidate's own
    `apple_mma_load_8x8[DType.float16]` B-operand read for the QK^T step now points straight at
    `k_native + block_base_k + dstep*8*_KT + col_blk*8` (a plain device pointer, `address_space`
    unannotated) instead of `skv` -- the ENTIRE old "stage K, transposed [D,KT]" loop and its
    dedicated barrier are deleted, not merely simplified. This is the path this task asked to be
    tried FIRST, and it was kept (not the contiguous-copy fallback) because `native_kv_producer_
    driver.mojo`'s own `test_direct_load_probe` already proved, at runtime on this hardware, that
    `apple_mma_load_8x8[DType.float16]` reads a device (non-shared) F16 pointer correctly for
    exactly this block shape (`worst abs diff = 0.0`, reproduced on an independent run) -- this
    file's own driver (`splitk_fa_driver.mojo`) re-proves it end-to-end at the real consuming site
    (every existing correctness/isolation/determinism case, now fed packed inputs, still passes),
    which is the honest bar for "kept" rather than merely "type-checks."
  - **V: trivial, index-math-free contiguous copy into `skv`.** V is still staged into shared
    memory (this file did not attempt a device-direct load for V's `apple_mma_load_8x8` B-operand
    in the PV step -- only K's read was this task's explicit ask, and staging V costs nothing extra
    the K path doesn't already pay for skv's allocation, which is unchanged in size). The OLD
    natural-layout V-staging loop computed `kk = idx // _D; d = idx % _D` and read a STRIDED
    natural-layout address (`v_ptr[(gk*h_kv+hk)*_D+d]`, contiguous in `d` but jumping by `h_kv*_D`
    every `_D` elements); the packed V layout's own block shape is `skv`'s exact `[KT][D]` byte
    order, so the new loop is `skv[idx] = v_native[block_base_v + idx]` -- one pointer-offset add,
    no division, no modulo, no per-element source-index formula at all.
  - **Iteration is now native-block-aligned, not split-range-aligned.** The OLD scheme stepped
    `j0` from `key_start` in `_KT`-strides, so the final tile was naturally clipped to `key_end`
    (`nb = min(_KT, key_end-j0)`) and zero-padded beyond it -- safe only because the NATURAL k_ptr/
    v_ptr buffers were never read past `n_tok_k`. A native block, once fetched (device-direct or
    copied), is always fetched WHOLE (`kk` in `[0,32)`, never clipped) -- so this kernel now walks
    whole blocks `blk` in `[key_start // _KT, (key_end-1) // _KT]`. Two consequences, both handled:
      1. When `key_start` is not itself a multiple of `_KT` (an ordinary outcome of the split
         partition's own integer division, unrelated to block alignment), the FIRST block this
         split touches may be shared with the PRECEDING split (whose own `key_end` equals this
         split's `key_start`) -- so the per-lane visibility check gains a new `gk >= key_start`
         term (the trailing `gk < key_end` term already existed). Without it, keys in
         `[block_lo*_KT, key_start)` would be double-counted by both splits once merged; with it,
         each split contributes exactly its own `[key_start, key_end)` sub-range regardless of how
         many splits happen to share a native block's physical read.
      2. A split whose own range is NARROWER than one block but straddles a block boundary now
         costs one EXTRA iteration versus the old scheme (e.g. `key_start=30, key_end=34` touches
         blocks 0 AND 1, even though the old scheme needed only one `_KT`-tile) -- strictly a
         result of aligning reads to the persistent native layout instead of to each split's own
         arbitrary boundary; every column read by that extra iteration is masked out by the
         `gk >= key_start` / `gk < key_end` bounds above, so it costs GPU cycles in a rare edge
         case, never correctness. `_KT` and the native producer's `key_block_size` are BOTH 32 by
         construction (this candidate's own K_TILE fallback, and the producer's own choice to match
         it) -- so this iteration scheme never has to reconcile two different block sizes.
  - **No new zero-padding, and none needed.** A native block's `kk` slots for real key positions
    `>= n_tok_k` (a block only partially filled by real tokens, e.g. this task's own `pos_base=50`
    continuation case) hold whatever `native_kv_producer.mojo` last left there -- possibly stale
    data from an earlier call, never garbage from unallocated memory (the packed buffer is sized by
    `n_blocks` up front, so every block this kernel's own `block_hi` bound can reach is always
    in-bounds). Those columns are excluded from every reduction (`_warp_sum`, the `local_max`
    shuffle-xor tree) by the SAME per-lane `vis` substitution (`s_val = raw*scale if vis else
    _NEG_MASK`) this file already relied on before Phase 2B -- `raw`'s own bytes, real or stale,
    never reach the softmax state once `vis` is false, so the old scheme's zero-padding (needed
    ONLY to avoid an out-of-bounds read on the natural buffer, never for numerical correctness) has
    no native-layout equivalent to preserve.
  - **Threadgroup memory budget is UNCHANGED.** `skv` is still sized `_D * _KT` (now used for V
    only, never aliased with K); every other shared array (`sq`, `so`, `ss`, `sp`, `s_corr`) is
    untouched. The module docstring's worked arithmetic above (23616B, ~9.0KiB headroom) still
    describes this kernel exactly -- Phase 2B changed WHAT `skv` holds and WHEN it's written, not
    its size.

See `splitk_fa_driver.mojo`'s own module docstring for how its existing correctness/isolation/
determinism suite was adapted to build packed K/V buffers (by hand, independently of
`native_kv_producer.mojo`) instead of natural ones, and for the new dedicated hand-packed-buffer
case this task asked for.
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
"""Per-head query tile: one 8-row block per sibling head per dispatch, matching `parity_replica.mojo`
and Candidate A's own `q8` fallback shape."""
comptime _KT: Int64 = 32
"""K_TILE fallback from this candidate's original single-head 64, for H_TILE=2 shared-memory
budget -- see module docstring's worked arithmetic (mirroring Candidate A's own `k32` fallback)."""
comptime _NSG_PER_HEAD: Int64 = 4
comptime _NSG: Int64 = 8
comptime _NTHREADS: Int64 = 256
comptime _NROWS: Int64 = _QT * 2
"""Combined rows across BOTH sibling heads sharing this dispatch's one K/V load: 16."""
comptime _NEG_MASK: Float32 = -1.0e9
comptime _NEG_SENTINEL: Float32 = -3.0e38


def _attn_splitk_partial_kernel(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_ptr: _F16P, k_native: _F16P, v_native: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    scale: Float32, pos_base: Int64, n_splits: Int64, n_blocks: Int64,
):
    """`k_native`/`v_native` are the Phase 2B native-packed device buffers (see module docstring's
    "PHASE 2B ADAPTATION" section for the exact flat-index formulas and why K is read device-direct
    while V is staged via a trivial contiguous copy) -- `n_blocks` is the packed buffer's own
    per-`kv_head` block stride, a property of how the caller sized the scratch buffer, not of this
    one dispatch."""
    var sq = stack_allocation[Int(_NROWS * _D), DType.float16, address_space = AddressSpace.SHARED]()
    var so = stack_allocation[Int(_NROWS * _D), DType.float32, address_space = AddressSpace.SHARED]()
    var skv = stack_allocation[Int(_D * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var ss = stack_allocation[Int(_NROWS * _KT), DType.float32, address_space = AddressSpace.SHARED]()
    var sp = stack_allocation[Int(_NROWS * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var s_corr = stack_allocation[Int(_NROWS), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32
    var lane = tid % 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var n_pairs = h_q // 2
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var rem = bidx // n_q_blocks
    var pair_idx = rem % n_pairs
    var split = rem // n_pairs

    var group = h_q // h_kv
    var h0 = pair_idx * 2
    var h1 = h0 + 1
    var hk = h0 // group

    var row0 = q_block * _QT

    # Q load: both sibling heads' 8-row blocks, at the SAME query positions row0..row0+7 --
    # combined row index cr = hh*_QT + r_local packs head hh's row r_local into one buffer, exactly
    # as Candidate A's own Q-load loop does.
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

    # Block-level (not per-row) causal upper bound -- the widest of the 8 rows' own horizons,
    # computed ONCE per dispatch and shared identically by BOTH sibling heads (they share row0
    # and hk, so this quantity does not depend on hh at all).
    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi
    var n_keys_block = kv_upper + 1
    if n_keys_block < 0:
        n_keys_block = 0

    # Gap-free, overlap-free, ANY-(n_keys_block, n_splits) partition -- identical formula to
    # `_splitk_partial_kernel_simd` (mojo/engine/residentk/kernels.mojo), including the
    # `key_start == key_end` empty-split case when `n_splits` exceeds the visible-key count. Also
    # computed ONCE per dispatch and shared by both sibling heads, for the same reason as above.
    var key_start = (n_keys_block * split) // n_splits
    var key_end = (n_keys_block * (split + 1)) // n_splits

    # Native-block-aligned iteration (Phase 2B): walk whole native blocks `blk` covering
    # `[key_start, key_end)`, instead of the old scheme's raw `_KT`-strides starting exactly at
    # `key_start` -- see module docstring's "PHASE 2B ADAPTATION" section for why (a native block
    # is always read WHOLE, never clipped) and for the new `gk >= key_start` visibility term this
    # requires below.
    if key_end > key_start:
        var block_lo = key_start // _KT
        var block_hi = (key_end - 1) // _KT
        var blk = block_lo
        while blk <= block_hi:
            var j0 = blk * _KT
            var block_base_k = (hk * n_blocks + blk) * _D * _KT
            var block_base_v = (hk * n_blocks + blk) * _KT * _D

            # QK^T: this SG's head (hh), its own single key-column block (K_TILE=32 / 8-wide
            # blocks = 4 total, exactly 1 per SG at 4 SGs/head), all 8 of that head's own local rows
            # via the a_frag row-offset hh*_QT*_D -- exactly `parity_replica.mojo`'s single-head QK
            # step, duplicated per head via the hh offset, exactly as Candidate A's own QK step does
            # (no cb loop needed at K_TILE=32, matching Candidate A's own `col_blk = sg_local`). K
            # is read DEVICE-DIRECT here -- no shared-memory staging, no index-transposing gather;
            # `k_native + block_base_k` is a plain device pointer, byte-identical in shape to what
            # `skv` used to hold after the OLD per-dispatch transpose-gather (see module docstring).
            var col_blk = sg_local
            var acc = SIMD[DType.float32, 2](0.0, 0.0)
            for dstep in range(Int64(16)):
                var a_frag = apple_mma_load_8x8[DType.float16](sq + Int(hh * _QT * _D + dstep * 8), Int(_D))
                var b_frag = apple_mma_load_8x8[DType.float16](
                    k_native + Int(block_base_k + dstep * 8 * _KT + col_blk * 8), Int(_KT)
                )
                _mma_apple_8x8(acc, a_frag, b_frag, acc)
            apple_mma_store_8x8[DType.float32](ss + Int(hh * _QT * _KT + col_blk * 8), Int(_KT), acc)

            barrier()

            # Softmax update: this SG's 2 owned rows of ITS OWN head (hh); K_TILE=32 / 32 lanes = 1
            # key column per lane (Candidate A's own single-column-per-lane shape at this K_TILE).
            # All split-K-specific logic (the `gk < key_end`/`gk >= key_start` bounds, the
            # fully-masked-tile `any_visible` detection) is UNCHANGED in spirit from the original
            # single-head kernel -- it operates on this row's own `qpos` and the dispatch-shared
            # `key_start`/`key_end`, neither of which depends on hh.
            for which in range(Int64(2)):
                var cr = cr0 if which == 0 else cr1
                var r_local = r0 if which == 0 else r1
                var c = lane
                var gk = j0 + c
                var raw = ss[Int(cr * _KT + c)]
                var qpos = pos_base + row0 + r_local
                # `gk < key_end` (this SPLIT's own upper bound, not just `n_tok_k`) excludes keys
                # beyond this split's own range that a WHOLE native block may still contain (a
                # trailing block only partially owned by this split). `gk >= key_start` (NEW for
                # Phase 2B's block-aligned iteration -- the old position-stepped scheme never needed
                # it, since `j0` itself started exactly at `key_start`) excludes keys BELOW this
                # split's own range that the FIRST native block this split touches may still
                # contain, whenever `key_start` isn't itself a multiple of `_KT` -- those keys
                # belong to the PRECEDING split (whose own `key_end` equals this split's
                # `key_start`), and counting them here too would double-count them once every
                # split's partial is merged.
                var vis = (gk < n_tok_k) and (gk <= qpos) and (gk < key_end) and (gk >= key_start)
                var s_val = raw * scale if vis else _NEG_MASK

                # Fully-masked-tile detection, REQUIRED here (unlike parity_replica.mojo, where the
                # outer loop bound `j0 <= kv_upper` is derived from the LAST row's own horizon, so
                # the row achieving `kv_upper` never hits this case, and no split of that shared
                # bound exists to make it common for every OTHER row): splitting the block's key
                # range across `n_splits` threadgroups means an EARLY row (small `qpos`) routinely
                # gets assigned to this tile purely because a LATER row's larger `qpos` sizes the
                # block-level split range, while every key in this specific tile is already beyond
                # the early row's own horizon. If no lane's `vis` is True, `local_max` degenerates to
                # `_NEG_MASK` itself (a large but FINITE sentinel), and comparing every masked score
                # against itself would wrongly yield `exp(0) == 1` per masked lane instead of the
                # intended `~0` -- silently adding up to 32 units of pure noise to `l` (and a
                # same-weighted, wrong contribution to `o`) for a tile that contributed NOTHING.
                # Detected via a `_warp_sum` all-reduce over each lane's own visible-count (0/1) --
                # reuses the same proven all-reduce primitive `parity_replica.mojo` already relies
                # on for `_warp_sum`, just summing a visibility indicator instead of a softmax
                # weight.
                var vis_count = Float32(1.0) if vis else Float32(0.0)
                var any_visible = _warp_sum(vis_count)

                var m_old = m0 if which == 0 else m1
                var l_old = l0 if which == 0 else l1
                var m_new: Float32
                var l_new: Float32
                var e: Float32
                var corr: Float32
                if any_visible > 0.0:
                    var local_max = s_val
                    var off: UInt32 = 16
                    while off > 0:
                        var other = _shuffle_xor(local_max, off)
                        if other > local_max:
                            local_max = other
                        off //= 2

                    m_new = local_max if local_max > m_old else m_old
                    corr = exp(m_old - m_new)
                    e = exp(s_val - m_new)
                    var block_sum = _warp_sum(e)
                    l_new = l_old * corr + block_sum
                else:
                    # Genuine no-op: nothing in this tile is visible to this row, so the running
                    # state must pass through UNCHANGED, exactly as an empty split's own initial
                    # state does.
                    m_new = m_old
                    l_new = l_old
                    e = Float32(0.0)
                    corr = Float32(1.0)

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

            # V staging: TRIVIAL, index-math-free contiguous copy from the native packed buffer --
            # no gather at all (contrast the OLD natural-layout version's `kk = idx // _D; d = idx %
            # _D; skv[idx] = v_ptr[(gk*h_kv+hk)*_D+d]`, a per-element STRIDED read from natural
            # layout). `native_kv_producer.mojo` packs V at exactly `((hk*n_blocks+block)*
            # key_block_size+kk)*d_head+d` for a whole `[KT][D]` block starting at `block_base_v` --
            # byte-identical, in order, to this buffer's own `skv` shape, so every thread copies its
            # own flat `idx` straight across with a single base-pointer offset, nothing else. K was
            # read device-direct above (no shared staging at all); V still stages into `skv` here
            # (see module docstring's "PHASE 2B ADAPTATION" section for why: only K's device-direct
            # read was this task's own explicit ask, and staging V costs nothing the K path doesn't
            # already pay for in `skv`'s allocation).
            for s in range(Int64(16)):
                var idx = tid + s * _NTHREADS
                skv[Int(idx)] = v_native[Int(block_base_v + idx)]

            barrier()

            # Rescale THIS head's own output-accumulator rows by this iteration's corr -- disjoint
            # per (hh, sg_local), matching Candidate A's own per-head rescale exactly.
            for e in range(Int64(8)):
                var idx = lane + e * 32
                var rr = idx // 32
                var dd = idx % 32
                var col = sg_local * 32 + dd
                var cr_rs = hh * _QT + rr
                var corr_r = s_corr[Int(cr_rs)]
                so[Int(cr_rs * _D + col)] = so[Int(cr_rs * _D + col)] * corr_r

            barrier()

            # PV: this SG's head (hh), one 32-wide output-dim chunk (4 8-wide MMA sub-blocks), all 8
            # of that head's rows, all KT keys of THIS block's current tile -- p_frag's row-offset
            # hh*_QT*_KT selects this head's own probability rows; v_frag reads the SAME shared skv
            # tile every SG (of both heads) just staged once above.
            for cb in range(Int64(4)):
                var col_blk_d = sg_local * 4 + cb
                var seed = apple_mma_load_8x8[DType.float32](so + Int(hh * _QT * _D + col_blk_d * 8), Int(_D))
                var acc2 = seed
                for kstep in range(Int64(4)):
                    var p_frag = apple_mma_load_8x8[DType.float16](sp + Int(hh * _QT * _KT + kstep * 8), Int(_KT))
                    var v_frag = apple_mma_load_8x8[DType.float16](skv + Int(kstep * 8 * _D + col_blk_d * 8), Int(_D))
                    _mma_apple_8x8(acc2, p_frag, v_frag, acc2)
                apple_mma_store_8x8[DType.float32](so + Int(hh * _QT * _D + col_blk_d * 8), Int(_D), acc2)

            # Extra safety barrier vs. parity_replica.mojo's own loop back-edge, inherited from
            # Candidate A and doubly warranted here (8 SGs across 2 heads sharing skv) -- see module
            # docstring's "Deviation from parity_replica.mojo's own barrier placement" section.
            barrier()

            blk += 1

    # No division by l -- this split's own state is UNNORMALIZED, written for the merge kernel,
    # per INDIVIDUAL head h (h0 or h1, whichever this SG owns) -- never a shared/paired slot.
    if lane == 0:
        var gi0 = row0 + r0
        if gi0 < n_tok_q:
            var pidx0 = (gi0 * h_q + h) * n_splits + split
            m_out[Int(pidx0)] = m0
            l_out[Int(pidx0)] = l0
        var gi1 = row0 + r1
        if gi1 < n_tok_q:
            var pidx1 = (gi1 * h_q + h) * n_splits + split
            m_out[Int(pidx1)] = m1
            l_out[Int(pidx1)] = l1

    barrier()

    for e in range(Int64(8)):
        var idx = lane + e * 32
        var rr = idx // 32
        var dd = idx % 32
        var col = sg_local * 32 + dd
        var cr_out = hh * _QT + rr
        var gi = row0 + rr
        if gi < n_tok_q:
            var pidx = (gi * h_q + h) * n_splits + split
            o_out[Int(pidx * _D + col)] = so[Int(cr_out * _D + col)]


def _attn_splitk_merge_kernel(
    out_ptr: _FP, lse_ptr: _FP,
    m_in: _FP, l_in: _FP, o_in: _FP,
    n_tok_q: Int64, h_q: Int64, n_splits: Int64,
):
    """The merge half -- `grid_dim = n_tok_q * h_q`, `block_dim = 128` (one thread per output
    dimension `e`). Deliberately NO barrier anywhere in this kernel: thread `e` only ever reads
    column `e` of every split's own `o_in` and writes column `e` of `out_ptr`, exactly the same
    "thread-private column, nothing for a barrier to order" property `_splitk_merge_kernel_simd`
    already relies on for its own head-only (no row) version of this same merge. UNCHANGED by the
    H_TILE=2 correction -- see module docstring's "Why the merge kernel needs, and receives, NO
    changes" section: this kernel's own grid and indexing are defined purely in terms of individual
    head `h`, never in terms of how the partial kernel paired heads for compute."""
    var bidx = Int64(block_idx.x)
    var gi = bidx // h_q
    var h = bidx % h_q
    var e = Int64(thread_idx.x)

    var m = _NEG_SENTINEL
    var l = Float32(0.0)
    var o = Float32(0.0)
    for s in range(n_splits):
        var pidx = (gi * h_q + h) * n_splits + s
        var sm = m_in[Int(pidx)]
        var sl = l_in[Int(pidx)]
        var so_ = o_in[Int(pidx * _D + e)]
        var nm = m if m > sm else sm
        var corr = exp(m - nm)
        var w = exp(sm - nm)
        o = o * corr + w * so_
        l = l * corr + w * sl
        m = nm

    out_ptr[Int((gi * h_q + h) * _D + e)] = (o / l) if l > 0.0 else Float32(0.0)
    if e == 0:
        lse_ptr[Int(h * n_tok_q + gi)] = (m + log(l)) if l > 0.0 else _NEG_SENTINEL
