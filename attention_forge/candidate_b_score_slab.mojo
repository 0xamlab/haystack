"""attention_forge.candidate_b_score_slab -- Attention Compiler Plan v1.0, Phase 2A, Candidate B:
triangular score-slab attention for the `pos_base=0` / 128-512-token short-prompt regime (the
MATERIALIZED family, contrasted with `parity_replica.mojo`'s tiled ONLINE-softmax recurrence).

The defining difference from `parity_replica.mojo`: parity_replica walks K in tiles and carries a
RUNNING (m, l, O) state forward, rescaling `O` by `exp(m_old - m_new)` every tile because the row
max can still change on a later tile. This file's three sub-variants never rescale an output
accumulator, because each of them determines the row's final max/denominator BEFORE any PV
accumulation happens (either because the whole row's scores are already sitting in device memory,
or because a first full pass over the row already computed the final stats). That is the actual
algorithmic content of "materialized, not online" here -- not "zero looping": Apple's hardware MMA
still needs K/V staged into threadgroup memory in bounded chunks (this file uses `K_TILE=64`,
identical to parity_replica's own staging granularity), so a K-tile STAGING loop is still present
in every kernel below. What is gone is the per-tile CORRECTION arithmetic on the O accumulator.

Reused verbatim from `parity_replica.mojo` (see that file's own docstring for why each is correct):
causal-visibility test (`j < n_tok_k and j <= pos_base+i`, no separate mask tensor), GQA head
mapping (`hk = h // (h_q // h_kv)`), K-transpose shared-memory staging for the QK MMA "B" operand,
the 5-step `shuffle_xor` max butterfly standing in for the absent `simd_max`, `_warp_sum` for the
sum reduction, blocked (not interleaved) SIMD-group row ownership (`{2s, 2s+1}`), and F16
storage/F32 state throughout.

One correctness-relevant addition beyond parity_replica's own pattern: this file inserts an EXTRA
`barrier()` at the very end of every K-tile loop body (after the PV/QK matmul that consumes a
tile's staged shared memory, before looping back to re-stage that SAME shared buffer for the next
tile). `parity_replica.mojo`'s own loop does not have this trailing barrier -- its 1,000-dispatch
soak found zero mismatches, so it evidently never gets exercised on this hardware/toolchain at the
shapes tested, but it is a real, nameable hazard (`skv`'s reuse across SIMD groups without a
synchronization point between the last MMA read of tile N's data and the first store of tile N+1's
data), and since this file was written fresh rather than inherited, the extra barrier costs a few
nanoseconds and removes a possible source of nondeterminism outright.

Grid convention (all six kernels): `block_idx.x = h * n_q_blocks + q_block`, one threadgroup per
(8-query block, query head), batch=1. `block_dim=128` (4 SIMD groups of 32).

Score slab layout: `scores[h_q][n_tok_q][n_tok_k]`, F16, row-major -- the
`score_slab[h_q][q_rows][kv_rows]` of the plan (2 MiB F16 at 256 tokens/16 heads, matching the
plan's own arithmetic). A Q-block only ever computes/reads/writes the causal-visible prefix
`[0, kv_upper]` of its own row range (`kv_upper = min(n_tok_k-1, pos_base+row0+7)`), never the
"upper triangle" beyond it -- that is the "triangular" of the name: within the computed rectangle
`[row0, row0+7] x [0, kv_upper]`, per-row visibility still varies (row `r`'s own visible bound is
`min(kv_upper, pos_base+row0+r)`), so masking is still a genuine per-element analytic test applied
by whichever stage first needs normalized probability, not baked into the QK stage.

Per-lane softmax-reduction register cap: `_b1_softmax_kernel` and `_b2_stats_kernel` cache each
lane's own strided slice of one row's scores in a 16-slot `InlineArray[Float32, 16]` (register-
resident, no shared memory) so the row is read from device memory exactly once regardless of how
many softmax sub-passes touch it. 16 slots/lane x 32 lanes = 512 columns -- the ceiling this
candidate's own regime (`pos_base=0`, "128-512-token regime") is scoped to. A row with more than
512 visible keys silently reads/writes past the array; this file does not runtime-guard that,
matching the plan's own scoping of Candidate B (Candidate A/C own the deep-context regime).

Threadgroup-memory budgets (all comfortably under the 32KiB static limit):
  - `_score_slab_qk_kernel`: sq 2048B + skv 16384B (K-transpose only, D x K_TILE) + ss 2048B
    (raw-score MMA landing pad, F32) = 20480B.
  - `_b1_softmax_kernel` / `_b2_stats_kernel`: no shared memory at all -- purely per-lane
    register work plus one `_warp_sum`/`shuffle_xor` reduction per row.
  - `_b1_pv_kernel`: sp 1024B (F16 probs) + skv 16384B (V-natural) + so 4096B (F32 accumulator)
    = 21504B.
  - `_b2_pv_kernel`: same as B1's PV kernel plus `s_m`/`s_linv` (32B each) = 21568B.
  - `_b3_fused_kernel`: sq 2048B + so 4096B + skv 16384B (K-transpose, then V-natural, ALIASED
    exactly as parity_replica's own `skv`) + ss 2048B + sp 1024B + s_m/s_linv (32B each) =
    25664B -- identical to parity_replica's own total, because B3's shared-memory shape IS
    parity_replica's shape; the two passes differ in what they do with the SAME buffers, not in
    how much memory they need.
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
comptime _KT: Int64 = 64
comptime _NSG: Int64 = 4
comptime _NTHREADS: Int64 = 128
comptime _NEG_MASK: Float32 = -1.0e9
comptime _NEG_SENTINEL: Float32 = -3.0e38


# ---------------------------------------------------------------------------------------------
# Stage 1 (shared by B1 and B2): materialize Q@K^T into the device-global score slab.
# ---------------------------------------------------------------------------------------------
def _score_slab_qk_kernel(
    scores_ptr: _F16P,
    q_ptr: _F16P, k_ptr: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    scale: Float32, pos_base: Int64,
):
    """Writes scaled raw scores for one (Q-block, head)'s full causal-visible column range
    `[0, kv_upper]` into `scores_ptr[h][n_tok_q][n_tok_k]`. No masking is applied here -- every
    column in the computed rectangle gets a real scaled dot product, even columns some rows in
    the block cannot see -- because masking is a cheap per-element test the softmax/stats/PV
    stages apply anyway, and applying it twice would just be redundant work, not a correctness
    issue either way. Rows with `gi >= n_tok_q` are simply never written (never read downstream).
    """
    var sq = stack_allocation[Int(_QT * _D), DType.float16, address_space = AddressSpace.SHARED]()
    var skv = stack_allocation[Int(_D * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var ss = stack_allocation[Int(_QT * _KT), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var h = bidx // n_q_blocks
    var group = h_q // h_kv
    var hk = h // group
    var row0 = q_block * _QT

    for s in range(Int64(8)):
        var idx = tid + s * _NTHREADS
        var i = idx // _D
        var d = idx % _D
        var gi = row0 + i
        if gi < n_tok_q:
            sq[Int(idx)] = q_ptr[Int((gi * h_q + h) * _D + d)]
        else:
            sq[Int(idx)] = Float16(0.0)

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

    barrier()

    var j0: Int64 = 0
    while j0 <= kv_upper:
        var nb = _KT if (_KT < n_tok_k - j0) else (n_tok_k - j0)

        for s in range(Int64(64)):
            var idx = tid + s * _NTHREADS
            var d = idx // 64
            var kk = idx % 64
            var gk = j0 + kk
            if kk < nb:
                skv[Int(idx)] = k_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        for cb in range(Int64(2)):
            var col_blk = sg * 2 + cb
            var acc = SIMD[DType.float32, 2](0.0, 0.0)
            for dstep in range(Int64(16)):
                var a_frag = apple_mma_load_8x8[DType.float16](sq + Int(dstep * 8), Int(_D))
                var b_frag = apple_mma_load_8x8[DType.float16](skv + Int(dstep * 8 * 64 + col_blk * 8), 64)
                _mma_apple_8x8(acc, a_frag, b_frag, acc)
            apple_mma_store_8x8[DType.float32](ss + Int(col_blk * 8), 64, acc)

        barrier()

        for s in range(Int64(4)):
            var idx = tid + s * _NTHREADS
            var r = idx // 64
            var c = idx % 64
            var gi = row0 + r
            var gk = j0 + c
            if gi < n_tok_q and c < nb:
                var raw = ss[Int(idx)]
                scores_ptr[Int((h * n_tok_q + gi) * n_tok_k + gk)] = Float16(raw * scale)

        barrier()
        j0 += _KT


# ---------------------------------------------------------------------------------------------
# B1: in-place probabilities.
# ---------------------------------------------------------------------------------------------
def _b1_softmax_kernel(
    scores_ptr: _F16P, lse_ptr: _FP,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64,
    pos_base: Int64,
):
    """Reads each visible row once into a 16-slot per-lane register cache, reduces max then sum
    (exp evaluated exactly once per element), then overwrites `scores_ptr` IN PLACE with the final
    normalized F16 probability -- no separate probability buffer. `lse_ptr[h*n_tok_q+gi]` is
    written here since this is the only stage that ever computes `m`/`l`.
    """
    var tid = Int64(thread_idx.x)
    var sg = tid // 32
    var lane = tid % 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var h = bidx // n_q_blocks
    var row0 = q_block * _QT

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi
    var n_cols = kv_upper + 1
    var per_lane = (n_cols + 31) // 32

    for which in range(Int64(2)):
        var r = sg * 2 + which
        var gi = row0 + r
        if gi >= n_tok_q:
            continue
        var qpos = pos_base + gi
        var base = Int((h * n_tok_q + gi) * n_tok_k)

        var cached = InlineArray[Float32, 16](fill=_NEG_SENTINEL)

        var local_max = _NEG_SENTINEL
        var t: Int64 = 0
        while t < per_lane:
            var c = lane + t * 32
            var v = _NEG_SENTINEL
            if c <= kv_upper and c <= qpos:
                v = Float32(scores_ptr[base + Int(c)])
            cached[Int(t)] = v
            if v > local_max:
                local_max = v
            t += 1

        var off: UInt32 = 16
        while off > 0:
            var other = _shuffle_xor(local_max, off)
            if other > local_max:
                local_max = other
            off //= 2
        var m_final = local_max

        var local_sum = Float32(0.0)
        var t2: Int64 = 0
        while t2 < per_lane:
            var e = exp(cached[Int(t2)] - m_final)
            cached[Int(t2)] = e
            local_sum += e
            t2 += 1

        var l_final = _warp_sum(local_sum)

        if lane == 0:
            lse_ptr[Int(h * n_tok_q + gi)] = (m_final + log(l_final)) if l_final > 0.0 else _NEG_SENTINEL

        var l_inv = (Float32(1.0) / l_final) if l_final > 0.0 else Float32(0.0)
        var t3: Int64 = 0
        while t3 < per_lane:
            var c = lane + t3 * 32
            if c <= kv_upper:
                scores_ptr[base + Int(c)] = Float16(cached[Int(t3)] * l_inv)
            t3 += 1


def _b1_pv_kernel(
    out_ptr: _FP,
    probs_ptr: _F16P, v_ptr: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    pos_base: Int64,
):
    """PV: `probs_ptr` already holds the final normalized probability for every visible cell (and
    an explicit zero for every causally-invisible cell within the computed rectangle) -- so this
    is a straight tiled matmul-and-accumulate, with NO output-rescale step at all (contrast
    parity_replica's `so[...] *= corr` between tiles)."""
    var sp = stack_allocation[Int(_QT * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var skv = stack_allocation[Int(_KT * _D), DType.float16, address_space = AddressSpace.SHARED]()
    var so = stack_allocation[Int(_QT * _D), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var h = bidx // n_q_blocks
    var group = h_q // h_kv
    var hk = h // group
    var row0 = q_block * _QT

    for s in range(Int64(8)):
        var idx = tid + s * _NTHREADS
        so[Int(idx)] = Float32(0.0)

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

    barrier()

    var j0: Int64 = 0
    while j0 <= kv_upper:
        var nb = _KT if (_KT < kv_upper - j0 + 1) else (kv_upper - j0 + 1)

        for s in range(Int64(4)):
            var idx = tid + s * _NTHREADS
            var r = idx // 64
            var c = idx % 64
            var gi = row0 + r
            var gk = j0 + c
            if c < nb and gi < n_tok_q:
                sp[Int(idx)] = probs_ptr[Int((h * n_tok_q + gi) * n_tok_k + gk)]
            else:
                sp[Int(idx)] = Float16(0.0)

        for s in range(Int64(64)):
            var idx = tid + s * _NTHREADS
            var kk = idx // 128
            var d = idx % 128
            var gk = j0 + kk
            if kk < nb:
                skv[Int(idx)] = v_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        for cb in range(Int64(4)):
            var col_blk_d = sg * 4 + cb
            var seed = apple_mma_load_8x8[DType.float32](so + Int(col_blk_d * 8), 128)
            var acc = seed
            for kstep in range(Int64(8)):
                var p_frag = apple_mma_load_8x8[DType.float16](sp + Int(kstep * 8), 64)
                var v_frag = apple_mma_load_8x8[DType.float16](skv + Int(kstep * 8 * 128 + col_blk_d * 8), 128)
                _mma_apple_8x8(acc, p_frag, v_frag, acc)
            apple_mma_store_8x8[DType.float32](so + Int(col_blk_d * 8), 128, acc)

        barrier()
        j0 += _KT

    var lane = tid % 32
    for e in range(Int64(8)):
        var idx = lane + e * 32
        var rr = idx // 32
        var dd = idx % 32
        var col = sg * 32 + dd
        var gi = row0 + rr
        if gi < n_tok_q:
            out_ptr[Int((gi * h_q + h) * _D + col)] = so[Int(rr * 128 + col)]


# ---------------------------------------------------------------------------------------------
# B2: statistics-only.
# ---------------------------------------------------------------------------------------------
def _b2_stats_kernel(
    scores_ptr: _F16P, lse_ptr: _FP, stats_m_ptr: _FP, stats_linv_ptr: _FP,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64,
    pos_base: Int64,
):
    """Same max/sum reduction as `_b1_softmax_kernel`, but never writes a probability back:
    only the row's max and `1/sum` are stored (`stats_m_ptr`/`stats_linv_ptr`, one F32 each per
    (head, query) row). `scores_ptr` is left untouched -- `_b2_pv_kernel` rereads it."""
    var tid = Int64(thread_idx.x)
    var sg = tid // 32
    var lane = tid % 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var h = bidx // n_q_blocks
    var row0 = q_block * _QT

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi
    var n_cols = kv_upper + 1
    var per_lane = (n_cols + 31) // 32

    for which in range(Int64(2)):
        var r = sg * 2 + which
        var gi = row0 + r
        if gi >= n_tok_q:
            continue
        var qpos = pos_base + gi
        var base = Int((h * n_tok_q + gi) * n_tok_k)

        var local_max = _NEG_SENTINEL
        var t: Int64 = 0
        while t < per_lane:
            var c = lane + t * 32
            if c <= kv_upper and c <= qpos:
                var v = Float32(scores_ptr[base + Int(c)])
                if v > local_max:
                    local_max = v
            t += 1

        var off: UInt32 = 16
        while off > 0:
            var other = _shuffle_xor(local_max, off)
            if other > local_max:
                local_max = other
            off //= 2
        var m_final = local_max

        var local_sum = Float32(0.0)
        var t2: Int64 = 0
        while t2 < per_lane:
            var c2 = lane + t2 * 32
            if c2 <= kv_upper and c2 <= qpos:
                var v2 = Float32(scores_ptr[base + Int(c2)])
                local_sum += exp(v2 - m_final)
            t2 += 1

        var l_final = _warp_sum(local_sum)

        if lane == 0:
            lse_ptr[Int(h * n_tok_q + gi)] = (m_final + log(l_final)) if l_final > 0.0 else _NEG_SENTINEL
            stats_m_ptr[Int(h * n_tok_q + gi)] = m_final
            stats_linv_ptr[Int(h * n_tok_q + gi)] = (Float32(1.0) / l_final) if l_final > 0.0 else Float32(0.0)


def _b2_pv_kernel(
    out_ptr: _FP,
    scores_ptr: _F16P, v_ptr: _F16P, stats_m_ptr: _FP, stats_linv_ptr: _FP,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    pos_base: Int64,
):
    """Reconstructs probability values on the fly from the ORIGINAL scores plus the per-row
    max/`1/sum` (`exp` evaluated a second time here, once per element, matching the plan's
    "exp evaluated twice total"). `s_m`/`s_linv` are broadcast into shared memory once per
    threadgroup because the P-staging loop below sweeps all 8 rows with a flat thread index, not
    a per-SIMD-group row assignment -- any thread may need any row's stats."""
    var sp = stack_allocation[Int(_QT * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var skv = stack_allocation[Int(_KT * _D), DType.float16, address_space = AddressSpace.SHARED]()
    var so = stack_allocation[Int(_QT * _D), DType.float32, address_space = AddressSpace.SHARED]()
    var s_m = stack_allocation[Int(_QT), DType.float32, address_space = AddressSpace.SHARED]()
    var s_linv = stack_allocation[Int(_QT), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var h = bidx // n_q_blocks
    var group = h_q // h_kv
    var hk = h // group
    var row0 = q_block * _QT

    for s in range(Int64(8)):
        var idx = tid + s * _NTHREADS
        so[Int(idx)] = Float32(0.0)

    if tid < _QT:
        var gi = row0 + tid
        if gi < n_tok_q:
            s_m[Int(tid)] = stats_m_ptr[Int(h * n_tok_q + gi)]
            s_linv[Int(tid)] = stats_linv_ptr[Int(h * n_tok_q + gi)]
        else:
            s_m[Int(tid)] = Float32(0.0)
            s_linv[Int(tid)] = Float32(0.0)

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

    barrier()

    var j0: Int64 = 0
    while j0 <= kv_upper:
        var nb = _KT if (_KT < kv_upper - j0 + 1) else (kv_upper - j0 + 1)

        for s in range(Int64(4)):
            var idx = tid + s * _NTHREADS
            var r = idx // 64
            var c = idx % 64
            var gi = row0 + r
            var gk = j0 + c
            if c < nb and gi < n_tok_q:
                var qpos = pos_base + gi
                if gk <= qpos:
                    var raw = Float32(scores_ptr[Int((h * n_tok_q + gi) * n_tok_k + gk)])
                    sp[Int(idx)] = Float16(exp(raw - s_m[Int(r)]) * s_linv[Int(r)])
                else:
                    sp[Int(idx)] = Float16(0.0)
            else:
                sp[Int(idx)] = Float16(0.0)

        for s in range(Int64(64)):
            var idx = tid + s * _NTHREADS
            var kk = idx // 128
            var d = idx % 128
            var gk = j0 + kk
            if kk < nb:
                skv[Int(idx)] = v_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        for cb in range(Int64(4)):
            var col_blk_d = sg * 4 + cb
            var seed = apple_mma_load_8x8[DType.float32](so + Int(col_blk_d * 8), 128)
            var acc = seed
            for kstep in range(Int64(8)):
                var p_frag = apple_mma_load_8x8[DType.float16](sp + Int(kstep * 8), 64)
                var v_frag = apple_mma_load_8x8[DType.float16](skv + Int(kstep * 8 * 128 + col_blk_d * 8), 128)
                _mma_apple_8x8(acc, p_frag, v_frag, acc)
            apple_mma_store_8x8[DType.float32](so + Int(col_blk_d * 8), 128, acc)

        barrier()
        j0 += _KT

    var lane = tid % 32
    for e in range(Int64(8)):
        var idx = lane + e * 32
        var rr = idx // 32
        var dd = idx % 32
        var col = sg * 32 + dd
        var gi = row0 + rr
        if gi < n_tok_q:
            out_ptr[Int((gi * h_q + h) * _D + col)] = so[Int(rr * 128 + col)]


# ---------------------------------------------------------------------------------------------
# B3: fused softmax/PV, no device-global slab at all.
# ---------------------------------------------------------------------------------------------
def _b3_fused_kernel(
    out_ptr: _FP, lse_ptr: _FP,
    q_ptr: _F16P, k_ptr: _F16P, v_ptr: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    scale: Float32, pos_base: Int64,
):
    """Two full passes over the same causal-visible K range, in ONE dispatch, with no device-
    memory score slab at any point:

    Pass 1 recomputes exactly parity_replica.mojo's own per-tile max/sum update (same shuffle_xor
    butterfly, same `_warp_sum`, same online `m_new`/`l_new` recurrence) but stops there -- no `so`
    accumulation, no correction multiply, because pass 1's ONLY job is to discover each row's
    final `m`/`l` before any PV work starts. Those are staged into `s_m`/`s_linv` (shared memory,
    broadcast to all 4 SIMD groups, since pass 2's V-staging loop is a flat sweep that is not
    partitioned by row-owning SIMD group).

    Pass 2 re-walks the SAME K tiles (re-staging K into `skv` and redoing the QK MMA -- this
    candidate's one real, itemized extra cost versus parity_replica: the QK matmul happens TWICE),
    but this time with `m`/`l` already final, so it exponentiates and accumulates into `so`
    directly with NO rescale between tiles at all (contrast parity_replica's `so[...] *= corr`).
    Both `sq`'s output-dimension partitioning (128 columns split 32/SIMD-group) and the per-tile
    `ss`/`sp` shapes are byte-for-byte parity_replica's own -- see the module docstring's
    threadgroup-memory-budget note for why B3 needed no NEW shared-memory shape at all, only a
    different sequence of operations over the same one.
    """
    var sq = stack_allocation[Int(_QT * _D), DType.float16, address_space = AddressSpace.SHARED]()
    var so = stack_allocation[Int(_QT * _D), DType.float32, address_space = AddressSpace.SHARED]()
    var skv = stack_allocation[128 * 64, DType.float16, address_space = AddressSpace.SHARED]()
    var ss = stack_allocation[Int(_QT * _KT), DType.float32, address_space = AddressSpace.SHARED]()
    var sp = stack_allocation[Int(_QT * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var s_m = stack_allocation[Int(_QT), DType.float32, address_space = AddressSpace.SHARED]()
    var s_linv = stack_allocation[Int(_QT), DType.float32, address_space = AddressSpace.SHARED]()

    var tid = Int64(thread_idx.x)
    var sg = tid // 32
    var lane = tid % 32

    var n_q_blocks = (n_tok_q + _QT - 1) // _QT
    var bidx = Int64(block_idx.x)
    var q_block = bidx % n_q_blocks
    var h = bidx // n_q_blocks
    var group = h_q // h_kv
    var hk = h // group
    var row0 = q_block * _QT

    for s in range(Int64(8)):
        var idx = tid + s * _NTHREADS
        var i = idx // _D
        var d = idx % _D
        var gi = row0 + i
        if gi < n_tok_q:
            sq[Int(idx)] = q_ptr[Int((gi * h_q + h) * _D + d)]
        else:
            sq[Int(idx)] = Float16(0.0)
        so[Int(idx)] = Float32(0.0)

    var m0 = _NEG_SENTINEL
    var m1 = _NEG_SENTINEL
    var l0 = Float32(0.0)
    var l1 = Float32(0.0)
    var r0 = sg * 2
    var r1 = sg * 2 + 1

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

    barrier()

    # ---- Pass 1: discover final (m, l) per row, no PV work at all. ----
    var j0: Int64 = 0
    while j0 <= kv_upper:
        var nb = _KT if (_KT < n_tok_k - j0) else (n_tok_k - j0)

        for s in range(Int64(64)):
            var idx = tid + s * _NTHREADS
            var d = idx // 64
            var kk = idx % 64
            var gk = j0 + kk
            if kk < nb:
                skv[Int(idx)] = k_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        for cb in range(Int64(2)):
            var col_blk = sg * 2 + cb
            var acc = SIMD[DType.float32, 2](0.0, 0.0)
            for dstep in range(Int64(16)):
                var a_frag = apple_mma_load_8x8[DType.float16](sq + Int(dstep * 8), Int(_D))
                var b_frag = apple_mma_load_8x8[DType.float16](skv + Int(dstep * 8 * 64 + col_blk * 8), 64)
                _mma_apple_8x8(acc, a_frag, b_frag, acc)
            apple_mma_store_8x8[DType.float32](ss + Int(col_blk * 8), 64, acc)

        barrier()

        for which in range(Int64(2)):
            var r = r0 if which == 0 else r1
            var c0 = lane * 2
            var c1 = c0 + 1
            var gk0 = j0 + c0
            var gk1 = j0 + c1
            var raw0 = ss[Int(r * 64 + c0)]
            var raw1 = ss[Int(r * 64 + c1)]
            var qpos = pos_base + row0 + r
            var vis0 = (gk0 < n_tok_k) and (gk0 <= qpos)
            var vis1 = (gk1 < n_tok_k) and (gk1 <= qpos)
            var s0 = raw0 * scale if vis0 else _NEG_MASK
            var s1 = raw1 * scale if vis1 else _NEG_MASK

            var local_max = s0 if s0 > s1 else s1
            var off: UInt32 = 16
            while off > 0:
                var other = _shuffle_xor(local_max, off)
                if other > local_max:
                    local_max = other
                off //= 2

            var m_old = m0 if which == 0 else m1
            var m_new = local_max if local_max > m_old else m_old
            var corr = exp(m_old - m_new)
            var e0 = exp(s0 - m_new)
            var e1 = exp(s1 - m_new)
            var local_sum = e0 + e1
            var block_sum = _warp_sum(local_sum)
            var l_old = l0 if which == 0 else l1
            var l_new = l_old * corr + block_sum

            if which == 0:
                m0 = m_new
                l0 = l_new
            else:
                m1 = m_new
                l1 = l_new

        barrier()
        j0 += _KT

    if lane == 0:
        s_m[Int(r0)] = m0
        s_m[Int(r1)] = m1
        s_linv[Int(r0)] = (Float32(1.0) / l0) if l0 > 0.0 else Float32(0.0)
        s_linv[Int(r1)] = (Float32(1.0) / l1) if l1 > 0.0 else Float32(0.0)

    for which in range(Int64(2)):
        var r = r0 if which == 0 else r1
        var gi = row0 + r
        if gi < n_tok_q and lane == 0:
            var mm = m0 if which == 0 else m1
            var ll = l0 if which == 0 else l1
            lse_ptr[Int(h * n_tok_q + gi)] = (mm + log(ll)) if ll > 0.0 else _NEG_SENTINEL

    barrier()

    # ---- Pass 2: re-derive scores, exponentiate with FINAL stats, accumulate PV directly. ----
    var j0b: Int64 = 0
    while j0b <= kv_upper:
        var nb2 = _KT if (_KT < n_tok_k - j0b) else (n_tok_k - j0b)

        for s in range(Int64(64)):
            var idx = tid + s * _NTHREADS
            var d = idx // 64
            var kk = idx % 64
            var gk = j0b + kk
            if kk < nb2:
                skv[Int(idx)] = k_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        for cb in range(Int64(2)):
            var col_blk = sg * 2 + cb
            var acc = SIMD[DType.float32, 2](0.0, 0.0)
            for dstep in range(Int64(16)):
                var a_frag = apple_mma_load_8x8[DType.float16](sq + Int(dstep * 8), Int(_D))
                var b_frag = apple_mma_load_8x8[DType.float16](skv + Int(dstep * 8 * 64 + col_blk * 8), 64)
                _mma_apple_8x8(acc, a_frag, b_frag, acc)
            apple_mma_store_8x8[DType.float32](ss + Int(col_blk * 8), 64, acc)

        barrier()

        for which in range(Int64(2)):
            var r = r0 if which == 0 else r1
            var c0 = lane * 2
            var c1 = c0 + 1
            var gk0 = j0b + c0
            var gk1 = j0b + c1
            var raw0 = ss[Int(r * 64 + c0)]
            var raw1 = ss[Int(r * 64 + c1)]
            var qpos = pos_base + row0 + r
            var vis0 = (gk0 < n_tok_k) and (gk0 <= qpos)
            var vis1 = (gk1 < n_tok_k) and (gk1 <= qpos)
            var mm = s_m[Int(r)]
            var linv = s_linv[Int(r)]
            var s0 = raw0 * scale if vis0 else _NEG_MASK
            var s1 = raw1 * scale if vis1 else _NEG_MASK
            var p0 = exp(s0 - mm) * linv
            var p1 = exp(s1 - mm) * linv
            sp[Int(r * 64 + c0)] = Float16(p0)
            sp[Int(r * 64 + c1)] = Float16(p1)

        barrier()

        for s in range(Int64(64)):
            var idx = tid + s * _NTHREADS
            var kk = idx // 128
            var d = idx % 128
            var gk = j0b + kk
            if kk < nb2:
                skv[Int(idx)] = v_ptr[Int((gk * h_kv + hk) * _D + d)]
            else:
                skv[Int(idx)] = Float16(0.0)

        barrier()

        for cb in range(Int64(4)):
            var col_blk_d = sg * 4 + cb
            var seed = apple_mma_load_8x8[DType.float32](so + Int(col_blk_d * 8), 128)
            var acc2 = seed
            for kstep in range(Int64(8)):
                var p_frag = apple_mma_load_8x8[DType.float16](sp + Int(kstep * 8), 64)
                var v_frag = apple_mma_load_8x8[DType.float16](skv + Int(kstep * 8 * 128 + col_blk_d * 8), 128)
                _mma_apple_8x8(acc2, p_frag, v_frag, acc2)
            apple_mma_store_8x8[DType.float32](so + Int(col_blk_d * 8), 128, acc2)

        barrier()
        j0b += _KT

    for e in range(Int64(8)):
        var idx = lane + e * 32
        var rr = idx // 32
        var dd = idx % 32
        var col = sg * 32 + dd
        var gi = row0 + rr
        if gi < n_tok_q:
            out_ptr[Int((gi * h_q + h) * _D + col)] = so[Int(rr * 128 + col)]
