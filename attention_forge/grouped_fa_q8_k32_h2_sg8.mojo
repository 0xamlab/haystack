"""attention_forge.grouped_fa_steel_k32 -- beat-llama.cpp campaign (2026-08-11): a from-scratch
RE-LAYOUT of the prefill flash-attention kernel to MLX `steel_attention`'s ownership scheme, the
structure the MLX teardown (REALRACE_RESULTS.md) identified as the reason MLX leads every prefill
depth by ~33%.

THE ARCHITECTURE (vs the prior `grouped_fa_unpaired_lean_k32`):
- ONE query head per threadgroup, BQ=32 query rows, split as 4 simdgroups x 8 rows (simdgroup sg
  owns rows [sg*8, sg*8+8)). block_dim=128.
- Each simdgroup is a SELF-CONTAINED 8-row flash-attention unit: it computes the full QK^T for its
  8 rows across ALL 32 keys of the block, keeps the score tile S and the output accumulator O in
  REGISTERS for the whole KV loop, and runs the online softmax with a 2-shuffle row reduction.
  There is NO shared-memory round-trip for S or P (the prior kernel stored QK^T to `ss`, read it
  back for softmax, wrote P to `sp`, and read it back for PV).
- Base-2 softmax: the attention scale is folded with log2(e) once, all exp/softmax runs as `exp2`
  on base-2 scores, and the running max m is tracked in base-2 units (converted back for lse).
- Q is staged to shared memory once (8KB); K and V are read DEVICE-DIRECT from the native packed
  layout (K is already the transposed `[d][k]` QK^T B-operand; V is the `[k][d]` PV B-operand).
  Shared footprint is just the Q tile (~8KB) and NOTHING is written to shared inside the KV loop,
  so the loop body has ZERO barriers (the prior kernel had 3 per iteration).

Fragment layout: the `apple_mma` 8x8 fragment owns, per lane, 2 contiguous columns of one row
(`_frag_row_col`: row_lo=((lane&6)>>1)+((lane&16)>>2), col_base=((lane&1)<<1)+((lane&8)>>1)); the 4
lanes sharing a row are {l, l^1, l^8, l^9}, so a full-row reduction is exactly two `shuffle_xor`
(masks 1 and 8) -- the same butterfly MLX uses.

Causal masking is applied per score element in-register (key position vs query position), and fully
masked keys are set to a finite -3e38 so exp2 -> 0. Ragged Q rows (gi >= n_tok_q) are zero-staged
and skipped at the output store.
"""
from std.gpu import thread_idx, block_idx
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp2, log
from std.gpu.primitives.warp import shuffle_xor as _shuffle_xor
from max.gpu.compute.arch.mma_apple import (
    _mma_apple_8x8,
    apple_mma_load_8x8,
)

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _D: Int64 = 128
comptime _QT: Int64 = 32
comptime _KT: Int64 = 32
comptime _NSG: Int64 = 4
comptime _NTHREADS: Int64 = 128
comptime _LOG2E: Float32 = 1.4426950408889634
comptime _LN2: Float32 = 0.6931471805599453
comptime _NEG_INF: Float32 = -3.0e38


def _frag_row_col(tid: Int64) -> SIMD[DType.int64, 2]:
    var lane = tid % 32
    var row_lo = ((lane & 6) >> 1) + ((lane & 16) >> 2)
    var col_base = ((lane & 1) << 1) + ((lane & 8) >> 1)
    return SIMD[DType.int64, 2](row_lo, col_base)


def _row_max2(v: Float32, off: UInt32) -> Float32:
    var other = _shuffle_xor(v, off)
    return v if v >= other else other


def _row_sum2(v: Float32, off: UInt32) -> Float32:
    return v + _shuffle_xor(v, off)


def _attn_grouped_fa_kernel(
    out_ptr: _FP, lse_ptr: _FP,
    q_ptr: _F16P, k_ptr: _F16P, v_ptr: _F16P,
    n_tok_q: Int64, n_tok_k: Int64, h_q: Int64, h_kv: Int64,
    scale: Float32, pos_base: Int64, n_blocks: Int64,
):
    # Q tile: this head's 32 rows x 128 dims, staged once, shared by the 4 simdgroups.
    var sq = stack_allocation[Int(_QT * _D), DType.float16, address_space = AddressSpace.SHARED]()

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

    # Q staging: 32 rows x 128 = 4096 elems / 128 threads = 32 iters.
    for s in range(Int64(32)):
        var idx = tid + s * _NTHREADS
        var r_l = idx // _D
        var d = idx % _D
        var gi = row0 + r_l
        if gi < n_tok_q:
            sq[Int(idx)] = q_ptr[Int((gi * h_q + h) * _D + d)]
        else:
            sq[Int(idx)] = Float16(0.0)

    # This simdgroup's 8 rows within the 32-row tile.
    var sg_row0 = sg * 8

    # Lane's owned (row_lo, col_base) within an 8x8 fragment.
    var rc = _frag_row_col(tid)
    var row_lo = rc[0]
    var col_base = rc[1]
    # Global query position of this lane's owned row.
    var lane_qpos = pos_base + row0 + sg_row0 + row_lo

    # Output accumulator O: this simdgroup's 8 rows x 128 dims = 16 8x8 frags, each SIMD[F32,2].
    var o_f0 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f1 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f2 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f3 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f4 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f5 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f6 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f7 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f8 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f9 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f10 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f11 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f12 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f13 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f14 = SIMD[DType.float32, 2](0.0, 0.0)
    var o_f15 = SIMD[DType.float32, 2](0.0, 0.0)

    # Running softmax state (base-2 units), one row per lane.
    var m_b2 = _NEG_INF
    var l_sum = Float32(0.0)

    var scale2 = scale * _LOG2E

    barrier()

    var q_hi = pos_base + row0 + (_QT - 1)
    var kv_upper = (n_tok_k - 1) if (n_tok_k - 1 < q_hi) else q_hi

    var j0: Int64 = 0
    while j0 <= kv_upper:
        var block = j0 // _KT
        var k_block_off = (hk * n_blocks + block) * _D * _KT
        var v_block_off = (hk * n_blocks + block) * _KT * _D

        # ── QK^T: S[8 rows x 32 keys] = Q[8x128] x K^T[128x32], kept in registers (4 frags).
        var s_f0 = SIMD[DType.float32, 2](0.0, 0.0)
        var s_f1 = SIMD[DType.float32, 2](0.0, 0.0)
        var s_f2 = SIMD[DType.float32, 2](0.0, 0.0)
        var s_f3 = SIMD[DType.float32, 2](0.0, 0.0)
        for dd in range(Int64(16)):
            var q_frag = apple_mma_load_8x8[DType.float16](
                sq + Int(sg_row0 * _D + dd * 8), Int(_D)
            )
            var k_frag0 = apple_mma_load_8x8[DType.float16](
                k_ptr + Int(k_block_off + dd * 8 * _KT + 0), Int(_KT)
            )
            _mma_apple_8x8(s_f0, q_frag, k_frag0, s_f0)
            var k_frag1 = apple_mma_load_8x8[DType.float16](
                k_ptr + Int(k_block_off + dd * 8 * _KT + 8), Int(_KT)
            )
            _mma_apple_8x8(s_f1, q_frag, k_frag1, s_f1)
            var k_frag2 = apple_mma_load_8x8[DType.float16](
                k_ptr + Int(k_block_off + dd * 8 * _KT + 16), Int(_KT)
            )
            _mma_apple_8x8(s_f2, q_frag, k_frag2, s_f2)
            var k_frag3 = apple_mma_load_8x8[DType.float16](
                k_ptr + Int(k_block_off + dd * 8 * _KT + 24), Int(_KT)
            )
            _mma_apple_8x8(s_f3, q_frag, k_frag3, s_f3)

        # Fold attention scale + log2(e) into the scores (base-2 units) and apply the causal +
        # ragged mask in-register. This lane's owned keys in frag j are j*8+col_base, j*8+col_base+1.
        var s00 = s_f0[0] * scale2
        var s01 = s_f0[1] * scale2
        var s10 = s_f1[0] * scale2
        var s11 = s_f1[1] * scale2
        var s20 = s_f2[0] * scale2
        var s21 = s_f2[1] * scale2
        var s30 = s_f3[0] * scale2
        var s31 = s_f3[1] * scale2
        var k00 = j0 + 0 + col_base
        var k01 = j0 + 0 + col_base + 1
        var k10 = j0 + 8 + col_base
        var k11 = j0 + 8 + col_base + 1
        var k20 = j0 + 16 + col_base
        var k21 = j0 + 16 + col_base + 1
        var k30 = j0 + 24 + col_base
        var k31 = j0 + 24 + col_base + 1
        if (k00 >= n_tok_k) or (k00 > lane_qpos):
            s00 = _NEG_INF
        if (k01 >= n_tok_k) or (k01 > lane_qpos):
            s01 = _NEG_INF
        if (k10 >= n_tok_k) or (k10 > lane_qpos):
            s10 = _NEG_INF
        if (k11 >= n_tok_k) or (k11 > lane_qpos):
            s11 = _NEG_INF
        if (k20 >= n_tok_k) or (k20 > lane_qpos):
            s20 = _NEG_INF
        if (k21 >= n_tok_k) or (k21 > lane_qpos):
            s21 = _NEG_INF
        if (k30 >= n_tok_k) or (k30 > lane_qpos):
            s30 = _NEG_INF
        if (k31 >= n_tok_k) or (k31 > lane_qpos):
            s31 = _NEG_INF

        # ── Online softmax (base-2). Row max: local over this lane's 8 elems, then 2 shuffles.
        var local_max = s00
        if s01 > local_max:
            local_max = s01
        if s10 > local_max:
            local_max = s10
        if s11 > local_max:
            local_max = s11
        if s20 > local_max:
            local_max = s20
        if s21 > local_max:
            local_max = s21
        if s30 > local_max:
            local_max = s30
        if s31 > local_max:
            local_max = s31
        local_max = _row_max2(local_max, UInt32(1))
        local_max = _row_max2(local_max, UInt32(8))

        var new_m_b2 = m_b2 if m_b2 >= local_max else local_max
        var factor = exp2(m_b2 - new_m_b2)

        # P = exp2(S - new_m) for this lane's 8 elems.
        var p00 = exp2(s00 - new_m_b2)
        var p01 = exp2(s01 - new_m_b2)
        var p10 = exp2(s10 - new_m_b2)
        var p11 = exp2(s11 - new_m_b2)
        var p20 = exp2(s20 - new_m_b2)
        var p21 = exp2(s21 - new_m_b2)
        var p30 = exp2(s30 - new_m_b2)
        var p31 = exp2(s31 - new_m_b2)

        # Row sum of P: local over 8 elems, then 2 shuffles.
        var local_sum = p00 + p01 + p10 + p11 + p20 + p21 + p30 + p31
        local_sum = _row_sum2(local_sum, UInt32(1))
        local_sum = _row_sum2(local_sum, UInt32(8))

        l_sum = l_sum * factor + local_sum
        m_b2 = new_m_b2

        # Rescale the running output accumulator by factor.
        o_f0 = SIMD[DType.float32, 2](o_f0[0] * factor, o_f0[1] * factor)
        o_f1 = SIMD[DType.float32, 2](o_f1[0] * factor, o_f1[1] * factor)
        o_f2 = SIMD[DType.float32, 2](o_f2[0] * factor, o_f2[1] * factor)
        o_f3 = SIMD[DType.float32, 2](o_f3[0] * factor, o_f3[1] * factor)
        o_f4 = SIMD[DType.float32, 2](o_f4[0] * factor, o_f4[1] * factor)
        o_f5 = SIMD[DType.float32, 2](o_f5[0] * factor, o_f5[1] * factor)
        o_f6 = SIMD[DType.float32, 2](o_f6[0] * factor, o_f6[1] * factor)
        o_f7 = SIMD[DType.float32, 2](o_f7[0] * factor, o_f7[1] * factor)
        o_f8 = SIMD[DType.float32, 2](o_f8[0] * factor, o_f8[1] * factor)
        o_f9 = SIMD[DType.float32, 2](o_f9[0] * factor, o_f9[1] * factor)
        o_f10 = SIMD[DType.float32, 2](o_f10[0] * factor, o_f10[1] * factor)
        o_f11 = SIMD[DType.float32, 2](o_f11[0] * factor, o_f11[1] * factor)
        o_f12 = SIMD[DType.float32, 2](o_f12[0] * factor, o_f12[1] * factor)
        o_f13 = SIMD[DType.float32, 2](o_f13[0] * factor, o_f13[1] * factor)
        o_f14 = SIMD[DType.float32, 2](o_f14[0] * factor, o_f14[1] * factor)
        o_f15 = SIMD[DType.float32, 2](o_f15[0] * factor, o_f15[1] * factor)

        # ── PV: O[8 rows x 128 dims] += P[8 rows x 32 keys] x V[32 keys x 128 dims]. P comes
        # straight from the registers (rebuilt into the 4 score frags); V is device-direct.
        s_f0 = SIMD[DType.float32, 2](p00, p01)
        s_f1 = SIMD[DType.float32, 2](p10, p11)
        s_f2 = SIMD[DType.float32, 2](p20, p21)
        s_f3 = SIMD[DType.float32, 2](p30, p31)
        for j in range(Int64(4)):
            var p_frag = s_f0
            if j == 1:
                p_frag = s_f1
            elif j == 2:
                p_frag = s_f2
            elif j == 3:
                p_frag = s_f3
            var v_base = v_block_off + j * 8 * _D
            var v_frag0 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 0 * 8), Int(_D))
            _mma_apple_8x8(o_f0, p_frag, v_frag0, o_f0)
            var v_frag1 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 1 * 8), Int(_D))
            _mma_apple_8x8(o_f1, p_frag, v_frag1, o_f1)
            var v_frag2 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 2 * 8), Int(_D))
            _mma_apple_8x8(o_f2, p_frag, v_frag2, o_f2)
            var v_frag3 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 3 * 8), Int(_D))
            _mma_apple_8x8(o_f3, p_frag, v_frag3, o_f3)
            var v_frag4 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 4 * 8), Int(_D))
            _mma_apple_8x8(o_f4, p_frag, v_frag4, o_f4)
            var v_frag5 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 5 * 8), Int(_D))
            _mma_apple_8x8(o_f5, p_frag, v_frag5, o_f5)
            var v_frag6 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 6 * 8), Int(_D))
            _mma_apple_8x8(o_f6, p_frag, v_frag6, o_f6)
            var v_frag7 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 7 * 8), Int(_D))
            _mma_apple_8x8(o_f7, p_frag, v_frag7, o_f7)
            var v_frag8 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 8 * 8), Int(_D))
            _mma_apple_8x8(o_f8, p_frag, v_frag8, o_f8)
            var v_frag9 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 9 * 8), Int(_D))
            _mma_apple_8x8(o_f9, p_frag, v_frag9, o_f9)
            var v_frag10 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 10 * 8), Int(_D))
            _mma_apple_8x8(o_f10, p_frag, v_frag10, o_f10)
            var v_frag11 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 11 * 8), Int(_D))
            _mma_apple_8x8(o_f11, p_frag, v_frag11, o_f11)
            var v_frag12 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 12 * 8), Int(_D))
            _mma_apple_8x8(o_f12, p_frag, v_frag12, o_f12)
            var v_frag13 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 13 * 8), Int(_D))
            _mma_apple_8x8(o_f13, p_frag, v_frag13, o_f13)
            var v_frag14 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 14 * 8), Int(_D))
            _mma_apple_8x8(o_f14, p_frag, v_frag14, o_f14)
            var v_frag15 = apple_mma_load_8x8[DType.float16](v_ptr + Int(v_base + 15 * 8), Int(_D))
            _mma_apple_8x8(o_f15, p_frag, v_frag15, o_f15)

        j0 += _KT

    # ── Epilogue: normalize O by l and write; lse = m_b2*ln2 + log(l). The lane owning col_base==0
    # is the unique per-row writer of lse (all 4 row-lanes hold the same m_b2/l_sum).
    var gi = row0 + sg_row0 + row_lo
    if gi < n_tok_q:
        var inv_l = Float32(0.0)
        if l_sum > 0.0:
            inv_l = Float32(1.0) / l_sum
        var out_base = (gi * h_q + h) * _D + col_base
        out_ptr[Int(out_base + 0 * 8)] = o_f0[0] * inv_l
        out_ptr[Int(out_base + 0 * 8 + 1)] = o_f0[1] * inv_l
        out_ptr[Int(out_base + 1 * 8)] = o_f1[0] * inv_l
        out_ptr[Int(out_base + 1 * 8 + 1)] = o_f1[1] * inv_l
        out_ptr[Int(out_base + 2 * 8)] = o_f2[0] * inv_l
        out_ptr[Int(out_base + 2 * 8 + 1)] = o_f2[1] * inv_l
        out_ptr[Int(out_base + 3 * 8)] = o_f3[0] * inv_l
        out_ptr[Int(out_base + 3 * 8 + 1)] = o_f3[1] * inv_l
        out_ptr[Int(out_base + 4 * 8)] = o_f4[0] * inv_l
        out_ptr[Int(out_base + 4 * 8 + 1)] = o_f4[1] * inv_l
        out_ptr[Int(out_base + 5 * 8)] = o_f5[0] * inv_l
        out_ptr[Int(out_base + 5 * 8 + 1)] = o_f5[1] * inv_l
        out_ptr[Int(out_base + 6 * 8)] = o_f6[0] * inv_l
        out_ptr[Int(out_base + 6 * 8 + 1)] = o_f6[1] * inv_l
        out_ptr[Int(out_base + 7 * 8)] = o_f7[0] * inv_l
        out_ptr[Int(out_base + 7 * 8 + 1)] = o_f7[1] * inv_l
        out_ptr[Int(out_base + 8 * 8)] = o_f8[0] * inv_l
        out_ptr[Int(out_base + 8 * 8 + 1)] = o_f8[1] * inv_l
        out_ptr[Int(out_base + 9 * 8)] = o_f9[0] * inv_l
        out_ptr[Int(out_base + 9 * 8 + 1)] = o_f9[1] * inv_l
        out_ptr[Int(out_base + 10 * 8)] = o_f10[0] * inv_l
        out_ptr[Int(out_base + 10 * 8 + 1)] = o_f10[1] * inv_l
        out_ptr[Int(out_base + 11 * 8)] = o_f11[0] * inv_l
        out_ptr[Int(out_base + 11 * 8 + 1)] = o_f11[1] * inv_l
        out_ptr[Int(out_base + 12 * 8)] = o_f12[0] * inv_l
        out_ptr[Int(out_base + 12 * 8 + 1)] = o_f12[1] * inv_l
        out_ptr[Int(out_base + 13 * 8)] = o_f13[0] * inv_l
        out_ptr[Int(out_base + 13 * 8 + 1)] = o_f13[1] * inv_l
        out_ptr[Int(out_base + 14 * 8)] = o_f14[0] * inv_l
        out_ptr[Int(out_base + 14 * 8 + 1)] = o_f14[1] * inv_l
        out_ptr[Int(out_base + 15 * 8)] = o_f15[0] * inv_l
        out_ptr[Int(out_base + 15 * 8 + 1)] = o_f15[1] * inv_l
        if col_base == 0:
            lse_ptr[Int(h * n_tok_q + gi)] = (m_b2 * _LN2 + log(l_sum)) if l_sum > 0.0 else _NEG_INF
