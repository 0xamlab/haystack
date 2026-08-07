"""attention_forge.parity_replica -- Attention Compiler Plan v1.0, Phase 1 (Stage 2 of the
teardown methodology): a faithful Mojo replica of llama.cpp's matrix-path FlashAttention kernel
(`kernel_flash_attn_ext_f16_dk128_dv128`, torn down in `benchmarks/competitors/llama_cpp/teardown/
EXECUTION_DIAGRAM.md`), built to answer ONE question: same algorithm (Q_TILE=8, K_TILE=64,
H_TILE=1, 4 SIMD groups, F16 K/V storage, F32 running softmax state, hardware MMA for BOTH QK^T
and PV, online softmax), Mojo-forged vs. hand-written Metal -- what is the measured difference,
and why. This is the control for the Phase 2 tournament, not a candidate itself.

Deliberate, itemized deviations from the control (§2 of the teardown), each chosen because it
changes NOTHING about the axis Stage 2 is measuring (the QK/PV MMA schedule and the online-softmax
organization) while avoiding disproportionate extra engineering on an orthogonal axis:

1. **No separate mask tensor + `kernel_flash_attn_ext_blk` pre-pass.** Causal (and ragged-tail)
   visibility is computed analytically, per key, per row, in-register: key `j` is visible to row
   `i` (query position `pos_base+i`) iff `j < n_tok_k and j <= pos_base+i`. This is evaluated
   UNCONDITIONALLY for every dispatched tile (2 comparisons per lane per row, matching llama.cpp's
   own 2-columns-per-lane granularity) rather than llama.cpp's 3-way `blk` classification, which
   additionally short-circuits the mask ADD entirely for provably-all-visible tiles (`blk==2`).
   Net effect: this kernel does a constant, small amount of extra per-lane comparison work on
   tiles llama.cpp would fast-path -- not expected to be measurable at these tile counts, but
   itemized rather than hidden.
2. **Whole-tile skip via a tighter loop bound, not iterate-and-`continue`.** No key beyond
   `min(n_tok_k-1, pos_base+row0+7)` is EVER visible to any row in this Q-block, so the K-tile
   loop simply does not iterate past it -- the same total tile count llama.cpp's `blk==0`
   short-circuit converges to at runtime, reached via a different mechanism (a loop bound instead
   of a per-iteration skip), so it does not bias the comparison: both control and replica dispatch
   the same causal tile count, at proportionally the same total FLOPs.
3. **A hand-rolled 5-step `shuffle_xor` butterfly stands in for `simd_max`.** This toolchain does
   not expose a direct SIMD-group max intrinsic (only `std.gpu.primitives.warp.sum` is proven in
   this codebase, e.g. `mojo/engine/residentk/kernels.mojo`'s own `_warp_sum`/`_shuffle_xor`
   argmax precedent); the butterfly is the same asymptotic cost (5 steps for 32 lanes) as
   `simd_max`'s own hardware lowering, not a scalar fallback.
4. **K and V are staged into threadgroup memory before every MMA use; V is not read directly from
   device.** Mojo's `apple_mma_load_8x8` has no transposed-load flag (`mma_forge/mm8.mojo`'s own
   documented gap), so K MUST be staged transposed for the QK^T "B" operand regardless; staging V
   too (rather than reading it device-direct, as llama.cpp does) is a simplicity choice that costs
   one extra shared-memory write+read per tile -- a real, measurable difference, explicitly
   attributed rather than absorbed into "the algorithm is slower."
5. **Blocked, not interleaved, SIMD-group row/column ownership.** llama.cpp assigns SG `s` rows/
   columns `{s, s+4}` (interleaved); this replica assigns contiguous blocks (`{2s, 2s+1}` for rows,
   `[16s, 16s+16)` for QK columns, `[32s, 32s+32)` for PV/output columns). Mathematically
   equivalent partitioning of the same 8 rows / 64 keys / 128 dims across 4 SIMD groups; changes
   which threads own which data, not what gets computed.

Shared-memory budget (F16 KV, D=128, Q_TILE=8, K_TILE=64): `sq` 2048B + `so` 4096B + `skv`
(K-transposed/V-natural, ALIASED -- K is fully consumed by QK^T before V staging overwrites it,
mirroring the aliasing technique the teardown itself documents for llama.cpp's own quantized-KV
`sk`/`sv` staging) 16384B + `ss` (raw scores) 2048B + `sp` (post-softmax probabilities) 1024B +
`s_corr`/`s_l` (32B each) = 25664B, comfortably under the 32KiB static threadgroup-memory budget
this plan's own Phase 1 hard gate requires checking.

Grid: `block_idx.x` encodes `(q_block, h)` as `h * n_q_blocks + q_block`; one threadgroup per
(8-query block, query head) pair, batch=1 (this plan's prefill scope). GQA head mapping: `hk =
h // (h_q // h_kv)`, matching `attnk.mask.mask_causal_flat`'s own `offset`-relative causal
convention exactly (query absolute position = `pos_base + row`; key absolute position = its own
0-based index into the K/V arrays -- no additional offset applied to keys).
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


def _attn_parity_replica_kernel(
    out_ptr: _FP, lse_ptr: _FP,
    q_ptr: _F16P, k_ptr: _F16P, v_ptr: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    scale: Float32, pos_base: Int64,
):
    var sq = stack_allocation[Int(_QT * _D), DType.float16, address_space = AddressSpace.SHARED]()
    var so = stack_allocation[Int(_QT * _D), DType.float32, address_space = AddressSpace.SHARED]()
    var skv = stack_allocation[128 * 64, DType.float16, address_space = AddressSpace.SHARED]()
    var ss = stack_allocation[Int(_QT * _KT), DType.float32, address_space = AddressSpace.SHARED]()
    var sp = stack_allocation[Int(_QT * _KT), DType.float16, address_space = AddressSpace.SHARED]()
    var s_corr = stack_allocation[Int(_QT), DType.float32, address_space = AddressSpace.SHARED]()
    var s_l = stack_allocation[Int(_QT), DType.float32, address_space = AddressSpace.SHARED]()

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

    barrier()

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

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

            sp[Int(r * 64 + c0)] = Float16(e0)
            sp[Int(r * 64 + c1)] = Float16(e1)
            if lane == 0:
                s_corr[Int(r)] = corr

            if which == 0:
                m0 = m_new
                l0 = l_new
            else:
                m1 = m_new
                l1 = l_new

        barrier()

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

        for e in range(Int64(8)):
            var idx = lane + e * 32
            var rr = idx // 32
            var dd = idx % 32
            var col = sg * 32 + dd
            var corr_r = s_corr[Int(rr)]
            so[Int(rr * 128 + col)] = so[Int(rr * 128 + col)] * corr_r

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

        j0 += _KT

    if lane == 0:
        s_l[Int(r0)] = l0
        s_l[Int(r1)] = l1

    barrier()

    for which in range(Int64(2)):
        var r = r0 if which == 0 else r1
        var gi = row0 + r
        if gi < n_tok_q and lane == 0:
            var mm = m0 if which == 0 else m1
            var ll = l0 if which == 0 else l1
            lse_ptr[Int(h * n_tok_q + gi)] = (mm + log(ll)) if ll > 0.0 else _NEG_SENTINEL

    for e in range(Int64(8)):
        var idx = lane + e * 32
        var rr = idx // 32
        var dd = idx % 32
        var col = sg * 32 + dd
        var gi = row0 + rr
        if gi < n_tok_q:
            var ll = s_l[Int(rr)]
            var val = so[Int(rr * 128 + col)]
            out_ptr[Int((gi * h_q + h) * _D + col)] = (val / ll) if ll > 0.0 else Float32(0.0)
