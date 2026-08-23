"""p3b_smallm_probe.mojo — LEVER L6 battery: the batched packed3 decode GEMMs at the SERVE
shapes (B=8 rows), measured in effective weight GB/s per role against the shipped kernel
(the ledger's ncu number: ~136 GB/s vs the B=1 GEMV probe's 470-497 GB/s — instruction/
latency bound inside the B-wide inner loop, long-scoreboard at k=3072, barrier + idle-lane
effects at k=1024). Variants, each gated by the serve selftest IF adopted:

  V1  the shipped `_batched_p3_gemv_assign/accum_kernel` (control)
  V2  V1 + SOFTWARE-PIPELINED weight loads (the next chunk's words+scale/zero in flight
      while the current chunk computes — attacks the k=3072 long-scoreboard) + FMA-form
      dequant with precomputed z*s (one op fewer per quant)
  V3  V2 + TWO OUTPUT ROWS PER BLOCK (halved grid; the B activation loads amortize over
      two rows' weight streams — the brief's "multiple rows per block with per-row
      accumulators")
  V4  V2 at 96 threads (the k=1024 shapes pack 86 chunks: 42 of 128 lanes idle today)

Roles at Qwen3-0.6B shapes, B=8:
  qkv ASSIGN  k=1024 n=2560      down ACCUM k=3072 n=1024
  o    ACCUM  k=2048 n=1024      (gu swiglu measured separately — same ASSIGN structure)

Build:
    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/p3b_smallm_probe.mojo -o p3bprobe
"""

from max.gpu.host import DeviceBuffer, DeviceContext
from std.gpu import block_idx, grid_dim, thread_idx, global_idx
from std.origin import MutAnyOrigin
from std.sys import exit, has_accelerator, is_defined
from std.time import perf_counter_ns
from std.gpu.primitives.warp import sum as _warp_sum
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.memory import bitcast, stack_allocation
from residentk.kernels import _SUBS, _BATCH_LMHEAD_MAX_ROWS
from residentk.kernels_packed3 import _P3_CHUNK, _P3_BLOCK, _P3_QUANTS_PER_WORD
from residentk.kernels_packed3_batched import (
    _P3B_TG,
    _P3B_GROUPS,
    _batched_p3_gemv_assign_kernel,
    _batched_p3_gemv_accum_kernel,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime REPS: Int = 50
comptime B: Int = 8

comptime _V2_TG: Int = 128
comptime _V2_GROUPS: Int = _V2_TG // 32
comptime _V4_TG: Int = 96
comptime _V4_GROUPS: Int = _V4_TG // 32


def _p3b_v2_assign_kernel(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, B_i64: Int64,
):
    """V2: the shipped assign kernel + (a) software-pipelined weight/scale loads — the next
    chunk's float4 word and block-32 scale/zero issue BEFORE the current chunk's compute,
    hiding HBM latency behind FMAs (the k=3072 long-scoreboard) — and (b) FMA-form dequant
    with the per-block z*s hoisted (d = q*s - zs, one fewer op per quant). Structure,
    accumulation order per row, and the two-level reduction are the shipped kernel's."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var Bm = Int(B_i64)
    var row = Int(block_idx.x)
    if row >= n:
        return
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var grp = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var acc_hi = stack_allocation[_BATCH_LMHEAD_MAX_ROWS - 8, DType.float32]()

    var tid = Int(thread_idx.x)
    var lane = tid % 32
    var sub = tid // 32

    var a0 = Float32(0.0)
    var a1 = Float32(0.0)
    var a2 = Float32(0.0)
    var a3 = Float32(0.0)
    var a4 = Float32(0.0)
    var a5 = Float32(0.0)
    var a6 = Float32(0.0)
    var a7 = Float32(0.0)
    for b in range(8, Bm):
        acc_hi[b - 8] = Float32(0.0)

    var wbase = row * words_per_row
    var sbase = row * nblocks
    var stride = _V2_TG * _P3_CHUNK

    # ── prologue: chunk 0's word + scales in flight ──
    var t = tid * _P3_CHUNK
    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28
    var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
    var blk = t >> 5
    var s0 = wscale[sbase + blk]
    var z0 = wzero[sbase + blk]
    var s_lo = s0
    var z_lo = z0
    var s_hi = s0
    var z_hi = z0
    if cross_hi:
        s_hi = wscale[sbase + blk + 1]
        z_hi = wzero[sbase + blk + 1]
        if cross_lo:
            s_lo = s_hi
            z_lo = z_hi

    while t < k_pack:
        # ── prefetch the NEXT chunk (in flight while this chunk computes) ──
        var tn = t + stride
        var vn = wp.load[width=4](wbase + tn // _P3_QUANTS_PER_WORD)
        var blkn = tn >> 5
        var sn0 = wscale[sbase + blkn]
        var zn0 = wzero[sbase + blkn]
        var sn_lo = sn0
        var zn_lo = zn0
        var sn_hi = sn0
        var zn_hi = zn0
        if cross_hi:
            sn_hi = wscale[sbase + blkn + 1]
            zn_hi = wzero[sbase + blkn + 1]
            if cross_lo:
                sn_lo = sn_hi
                zn_lo = zn_hi

        var w = bitcast[DType.int32, 4](v)
        # FMA-form dequant: d = q*s - z*s, with z*s hoisted per block segment
        var zs0 = z0 * s0
        var zs_lo = z_lo * s_lo
        var zs_hi = z_hi * s_hi
        var d0 = Float32(w[0] & 255) * s0 - zs0
        var d1 = Float32((w[0] >> 8) & 255) * s0 - zs0
        var d2 = Float32((w[0] >> 16) & 255) * s0 - zs0
        var d3 = Float32(w[1] & 255) * s0 - zs0
        var d4 = Float32((w[1] >> 8) & 255) * s_lo - zs_lo
        var d5 = Float32((w[1] >> 16) & 255) * s_lo - zs_lo
        var d6 = Float32(w[2] & 255) * s_lo - zs_lo
        var d7 = Float32((w[2] >> 8) & 255) * s_lo - zs_lo
        var d8 = Float32((w[2] >> 16) & 255) * s_hi - zs_hi
        var d9 = Float32(w[3] & 255) * s_hi - zs_hi
        var d10 = Float32((w[3] >> 8) & 255) * s_hi - zs_hi
        var d11 = Float32((w[3] >> 16) & 255) * s_hi - zs_hi

        if t + _P3_CHUNK <= k:
            if Bm >= 1:
                var xv0 = x.load[width=4](t)
                var xv1 = x.load[width=4](t + 4)
                var xv2 = x.load[width=4](t + 8)
                a0 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a0 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a0 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if Bm >= 2:
                var xv0 = x.load[width=4](k + t)
                var xv1 = x.load[width=4](k + t + 4)
                var xv2 = x.load[width=4](k + t + 8)
                a1 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a1 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a1 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if Bm >= 3:
                var xv0 = x.load[width=4](2 * k + t)
                var xv1 = x.load[width=4](2 * k + t + 4)
                var xv2 = x.load[width=4](2 * k + t + 8)
                a2 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a2 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a2 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if Bm >= 4:
                var xv0 = x.load[width=4](3 * k + t)
                var xv1 = x.load[width=4](3 * k + t + 4)
                var xv2 = x.load[width=4](3 * k + t + 8)
                a3 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a3 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a3 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if Bm >= 5:
                var xv0 = x.load[width=4](4 * k + t)
                var xv1 = x.load[width=4](4 * k + t + 4)
                var xv2 = x.load[width=4](4 * k + t + 8)
                a4 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a4 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a4 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if Bm >= 6:
                var xv0 = x.load[width=4](5 * k + t)
                var xv1 = x.load[width=4](5 * k + t + 4)
                var xv2 = x.load[width=4](5 * k + t + 8)
                a5 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a5 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a5 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if Bm >= 7:
                var xv0 = x.load[width=4](6 * k + t)
                var xv1 = x.load[width=4](6 * k + t + 4)
                var xv2 = x.load[width=4](6 * k + t + 8)
                a6 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a6 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a6 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if Bm >= 8:
                var xv0 = x.load[width=4](7 * k + t)
                var xv1 = x.load[width=4](7 * k + t + 4)
                var xv2 = x.load[width=4](7 * k + t + 8)
                a7 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a7 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a7 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            for b in range(8, Bm):
                var xb = b * k + t
                var xv0 = x.load[width=4](xb)
                var xv1 = x.load[width=4](xb + 4)
                var xv2 = x.load[width=4](xb + 8)
                var av = d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                av += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                av += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                acc_hi[b - 8] += av
        else:
            var dq = stack_allocation[_P3_CHUNK, DType.float32]()
            dq[0] = d0
            dq[1] = d1
            dq[2] = d2
            dq[3] = d3
            dq[4] = d4
            dq[5] = d5
            dq[6] = d6
            dq[7] = d7
            dq[8] = d8
            dq[9] = d9
            dq[10] = d10
            dq[11] = d11
            for e in range(_P3_CHUNK):
                if t + e < k:
                    var de = dq[e]
                    if Bm >= 1:
                        a0 += de * x[t + e]
                    if Bm >= 2:
                        a1 += de * x[k + t + e]
                    if Bm >= 3:
                        a2 += de * x[2 * k + t + e]
                    if Bm >= 4:
                        a3 += de * x[3 * k + t + e]
                    if Bm >= 5:
                        a4 += de * x[4 * k + t + e]
                    if Bm >= 6:
                        a5 += de * x[5 * k + t + e]
                    if Bm >= 7:
                        a6 += de * x[6 * k + t + e]
                    if Bm >= 8:
                        a7 += de * x[7 * k + t + e]
                    for b in range(8, Bm):
                        acc_hi[b - 8] += de * x[b * k + t + e]

        # ── advance: the prefetched chunk becomes current ──
        v = vn
        s0 = sn0
        z0 = zn0
        s_lo = sn_lo
        z_lo = zn_lo
        s_hi = sn_hi
        z_hi = zn_hi
        t = tn

    if Bm >= 1:
        var total = _warp_sum(a0)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
    if Bm >= 2:
        var total = _warp_sum(a1)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
    if Bm >= 3:
        var total = _warp_sum(a2)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
    if Bm >= 4:
        var total = _warp_sum(a3)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
    if Bm >= 5:
        var total = _warp_sum(a4)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
    if Bm >= 6:
        var total = _warp_sum(a5)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
    if Bm >= 7:
        var total = _warp_sum(a6)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
    if Bm >= 8:
        var total = _warp_sum(a7)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
    for b in range(8, Bm):
        var total = _warp_sum(acc_hi[b - 8])
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
    barrier()
    if tid < Bm:
        var o = Float32(0.0)
        for g in range(_V2_GROUPS):
            o += grp[g * _BATCH_LMHEAD_MAX_ROWS + tid]
        y[tid * n + row] = o


def _p3b_v3_assign_kernel(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, B_i64: Int64,
):
    """V3: V2's pipelined chunk loop with TWO OUTPUT ROWS per block — rows `row` and
    `row + n/2` (grid = n/2): the B activation float4s load ONCE per chunk and feed both
    rows' dequant streams (per-row accumulators a0..a7 / c0..c7), halving activation
    traffic per streamed weight byte and the grid size. Same per-row math and reduction."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var Bm = Int(B_i64)
    var row0 = Int(block_idx.x)
    var row1 = row0 + n // 2
    if row0 >= n // 2:
        return
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var grp = stack_allocation[
        2 * _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var acc_hi = stack_allocation[2 * (_BATCH_LMHEAD_MAX_ROWS - 8), DType.float32]()

    var tid = Int(thread_idx.x)
    var lane = tid % 32
    var sub = tid // 32

    var a0 = Float32(0.0)
    var a1 = Float32(0.0)
    var a2 = Float32(0.0)
    var a3 = Float32(0.0)
    var a4 = Float32(0.0)
    var a5 = Float32(0.0)
    var a6 = Float32(0.0)
    var a7 = Float32(0.0)
    var c0 = Float32(0.0)
    var c1 = Float32(0.0)
    var c2 = Float32(0.0)
    var c3 = Float32(0.0)
    var c4 = Float32(0.0)
    var c5 = Float32(0.0)
    var c6 = Float32(0.0)
    var c7 = Float32(0.0)
    for b in range(8, Bm):
        acc_hi[b - 8] = Float32(0.0)
        acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8] = Float32(0.0)

    var wbase0 = row0 * words_per_row
    var sbase0 = row0 * nblocks
    var wbase1 = row1 * words_per_row
    var sbase1 = row1 * nblocks
    var stride = _V2_TG * _P3_CHUNK

    var t = tid * _P3_CHUNK
    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28
    var v0 = wp.load[width=4](wbase0 + t // _P3_QUANTS_PER_WORD)
    var v1 = wp.load[width=4](wbase1 + t // _P3_QUANTS_PER_WORD)
    var blk = t >> 5
    var s0 = wscale[sbase0 + blk]
    var z0 = wzero[sbase0 + blk]
    var s_lo = s0
    var z_lo = z0
    var s_hi = s0
    var z_hi = z0
    if cross_hi:
        s_hi = wscale[sbase0 + blk + 1]
        z_hi = wzero[sbase0 + blk + 1]
        if cross_lo:
            s_lo = s_hi
            z_lo = z_hi
    var u0 = wscale[sbase1 + blk]
    var y0 = wzero[sbase1 + blk]
    var u_lo = u0
    var y_lo = y0
    var u_hi = u0
    var y_hi = y0
    if cross_hi:
        u_hi = wscale[sbase1 + blk + 1]
        y_hi = wzero[sbase1 + blk + 1]
        if cross_lo:
            u_lo = u_hi
            y_lo = y_hi

    while t < k_pack:
        var tn = t + stride
        var vn0 = wp.load[width=4](wbase0 + tn // _P3_QUANTS_PER_WORD)
        var vn1 = wp.load[width=4](wbase1 + tn // _P3_QUANTS_PER_WORD)
        var blkn = tn >> 5
        var sn0 = wscale[sbase0 + blkn]
        var zn0 = wzero[sbase0 + blkn]
        var sn_lo = sn0
        var zn_lo = zn0
        var sn_hi = sn0
        var zn_hi = zn0
        var un0 = wscale[sbase1 + blkn]
        var yn0 = wzero[sbase1 + blkn]
        var un_lo = un0
        var yn_lo = yn0
        var un_hi = un0
        var yn_hi = yn0
        if cross_hi:
            sn_hi = wscale[sbase0 + blkn + 1]
            zn_hi = wzero[sbase0 + blkn + 1]
            un_hi = wscale[sbase1 + blkn + 1]
            yn_hi = wzero[sbase1 + blkn + 1]
            if cross_lo:
                sn_lo = sn_hi
                zn_lo = zn_hi
                un_lo = un_hi
                yn_lo = yn_hi

        var w = bitcast[DType.int32, 4](v0)
        var zs0 = z0 * s0
        var zs_lo = z_lo * s_lo
        var zs_hi = z_hi * s_hi
        var d0 = Float32(w[0] & 255) * s0 - zs0
        var d1 = Float32((w[0] >> 8) & 255) * s0 - zs0
        var d2 = Float32((w[0] >> 16) & 255) * s0 - zs0
        var d3 = Float32(w[1] & 255) * s0 - zs0
        var d4 = Float32((w[1] >> 8) & 255) * s_lo - zs_lo
        var d5 = Float32((w[1] >> 16) & 255) * s_lo - zs_lo
        var d6 = Float32(w[2] & 255) * s_lo - zs_lo
        var d7 = Float32((w[2] >> 8) & 255) * s_lo - zs_lo
        var d8 = Float32((w[2] >> 16) & 255) * s_hi - zs_hi
        var d9 = Float32(w[3] & 255) * s_hi - zs_hi
        var d10 = Float32((w[3] >> 8) & 255) * s_hi - zs_hi
        var d11 = Float32((w[3] >> 16) & 255) * s_hi - zs_hi

        var wq = bitcast[DType.int32, 4](v1)
        var ys0 = y0 * u0
        var ys_lo = y_lo * u_lo
        var ys_hi = y_hi * u_hi
        var e0 = Float32(wq[0] & 255) * u0 - ys0
        var e1 = Float32((wq[0] >> 8) & 255) * u0 - ys0
        var e2 = Float32((wq[0] >> 16) & 255) * u0 - ys0
        var e3 = Float32(wq[1] & 255) * u0 - ys0
        var e4 = Float32((wq[1] >> 8) & 255) * u_lo - ys_lo
        var e5 = Float32((wq[1] >> 16) & 255) * u_lo - ys_lo
        var e6 = Float32(wq[2] & 255) * u_lo - ys_lo
        var e7 = Float32((wq[2] >> 8) & 255) * u_lo - ys_lo
        var e8 = Float32((wq[2] >> 16) & 255) * u_hi - ys_hi
        var e9 = Float32(wq[3] & 255) * u_hi - ys_hi
        var e10 = Float32((wq[3] >> 8) & 255) * u_hi - ys_hi
        var e11 = Float32((wq[3] >> 16) & 255) * u_hi - ys_hi

        if t + _P3_CHUNK <= k:
            if Bm >= 1:
                var xv0 = x.load[width=4](t)
                var xv1 = x.load[width=4](t + 4)
                var xv2 = x.load[width=4](t + 8)
                a0 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a0 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a0 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c0 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c0 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c0 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if Bm >= 2:
                var xv0 = x.load[width=4](k + t)
                var xv1 = x.load[width=4](k + t + 4)
                var xv2 = x.load[width=4](k + t + 8)
                a1 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a1 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a1 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c1 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c1 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c1 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if Bm >= 3:
                var xv0 = x.load[width=4](2 * k + t)
                var xv1 = x.load[width=4](2 * k + t + 4)
                var xv2 = x.load[width=4](2 * k + t + 8)
                a2 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a2 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a2 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c2 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c2 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c2 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if Bm >= 4:
                var xv0 = x.load[width=4](3 * k + t)
                var xv1 = x.load[width=4](3 * k + t + 4)
                var xv2 = x.load[width=4](3 * k + t + 8)
                a3 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a3 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a3 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c3 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c3 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c3 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if Bm >= 5:
                var xv0 = x.load[width=4](4 * k + t)
                var xv1 = x.load[width=4](4 * k + t + 4)
                var xv2 = x.load[width=4](4 * k + t + 8)
                a4 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a4 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a4 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c4 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c4 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c4 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if Bm >= 6:
                var xv0 = x.load[width=4](5 * k + t)
                var xv1 = x.load[width=4](5 * k + t + 4)
                var xv2 = x.load[width=4](5 * k + t + 8)
                a5 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a5 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a5 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c5 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c5 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c5 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if Bm >= 7:
                var xv0 = x.load[width=4](6 * k + t)
                var xv1 = x.load[width=4](6 * k + t + 4)
                var xv2 = x.load[width=4](6 * k + t + 8)
                a6 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a6 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a6 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c6 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c6 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c6 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if Bm >= 8:
                var xv0 = x.load[width=4](7 * k + t)
                var xv1 = x.load[width=4](7 * k + t + 4)
                var xv2 = x.load[width=4](7 * k + t + 8)
                a7 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a7 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a7 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c7 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c7 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c7 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            for b in range(8, Bm):
                var xb = b * k + t
                var xv0 = x.load[width=4](xb)
                var xv1 = x.load[width=4](xb + 4)
                var xv2 = x.load[width=4](xb + 8)
                var av = d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                av += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                av += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                acc_hi[b - 8] += av
                var cv = e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                cv += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                cv += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
                acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8] += cv
        else:
            var dq = stack_allocation[_P3_CHUNK, DType.float32]()
            var eq = stack_allocation[_P3_CHUNK, DType.float32]()
            dq[0] = d0
            dq[1] = d1
            dq[2] = d2
            dq[3] = d3
            dq[4] = d4
            dq[5] = d5
            dq[6] = d6
            dq[7] = d7
            dq[8] = d8
            dq[9] = d9
            dq[10] = d10
            dq[11] = d11
            eq[0] = e0
            eq[1] = e1
            eq[2] = e2
            eq[3] = e3
            eq[4] = e4
            eq[5] = e5
            eq[6] = e6
            eq[7] = e7
            eq[8] = e8
            eq[9] = e9
            eq[10] = e10
            eq[11] = e11
            for e in range(_P3_CHUNK):
                if t + e < k:
                    var de = dq[e]
                    var ee = eq[e]
                    if Bm >= 1:
                        a0 += de * x[t + e]
                        c0 += ee * x[t + e]
                    if Bm >= 2:
                        a1 += de * x[k + t + e]
                        c1 += ee * x[k + t + e]
                    if Bm >= 3:
                        a2 += de * x[2 * k + t + e]
                        c2 += ee * x[2 * k + t + e]
                    if Bm >= 4:
                        a3 += de * x[3 * k + t + e]
                        c3 += ee * x[3 * k + t + e]
                    if Bm >= 5:
                        a4 += de * x[4 * k + t + e]
                        c4 += ee * x[4 * k + t + e]
                    if Bm >= 6:
                        a5 += de * x[5 * k + t + e]
                        c5 += ee * x[5 * k + t + e]
                    if Bm >= 7:
                        a6 += de * x[6 * k + t + e]
                        c6 += ee * x[6 * k + t + e]
                    if Bm >= 8:
                        a7 += de * x[7 * k + t + e]
                        c7 += ee * x[7 * k + t + e]
                    for b in range(8, Bm):
                        acc_hi[b - 8] += de * x[b * k + t + e]
                        acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8] += ee * x[b * k + t + e]

        v0 = vn0
        v1 = vn1
        s0 = sn0
        z0 = zn0
        s_lo = sn_lo
        z_lo = zn_lo
        s_hi = sn_hi
        z_hi = zn_hi
        u0 = un0
        y0 = yn0
        u_lo = un_lo
        y_lo = yn_lo
        u_hi = un_hi
        y_hi = yn_hi
        t = tn

    # ── reduction, both rows ──
    if Bm >= 1:
        var total = _warp_sum(a0)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
        total = _warp_sum(c0)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 0] = total
    if Bm >= 2:
        var total = _warp_sum(a1)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
        total = _warp_sum(c1)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 1] = total
    if Bm >= 3:
        var total = _warp_sum(a2)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
        total = _warp_sum(c2)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 2] = total
    if Bm >= 4:
        var total = _warp_sum(a3)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
        total = _warp_sum(c3)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 3] = total
    if Bm >= 5:
        var total = _warp_sum(a4)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
        total = _warp_sum(c4)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 4] = total
    if Bm >= 6:
        var total = _warp_sum(a5)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
        total = _warp_sum(c5)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 5] = total
    if Bm >= 7:
        var total = _warp_sum(a6)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
        total = _warp_sum(c6)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 6] = total
    if Bm >= 8:
        var total = _warp_sum(a7)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
        total = _warp_sum(c7)
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 7] = total
    for b in range(8, Bm):
        var total = _warp_sum(acc_hi[b - 8])
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
        total = _warp_sum(acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8])
        if lane == 0:
            grp[(_V2_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + b] = total
    barrier()
    if tid < Bm:
        var o0 = Float32(0.0)
        var o1 = Float32(0.0)
        for g in range(_V2_GROUPS):
            o0 += grp[g * _BATCH_LMHEAD_MAX_ROWS + tid]
            o1 += grp[(_V2_GROUPS + g) * _BATCH_LMHEAD_MAX_ROWS + tid]
        y[tid * n + row0] = o0
        y[tid * n + row1] = o1


def _fill_kernel(dst: _FP, scale_i64: Int64, mod_i64: Int64, n_i64: Int64):
    var scale = Float32(Float64(scale_i64) / 1.0e6)
    var mod = Int(mod_i64)
    var n = Int(n_i64)
    var i = Int(global_idx.x)
    var stride = Int(grid_dim.x) * 256
    while i < n:
        dst[i] = scale * Float32(i % mod)
        i += stride


def _fill_const_kernel(dst: _FP, val_i64: Int64, n_i64: Int64):
    var val = Float32(Float64(val_i64) / 1.0e6)
    var n = Int(n_i64)
    var i = Int(global_idx.x)
    var stride = Int(grid_dim.x) * 256
    while i < n:
        dst[i] = val
        i += stride


def _fill_const(mut ctx: DeviceContext, addr: Int, n: Int, val: Float64) raises:
    var ptr = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=addr)
    var grid = (n + 255) // 256
    if grid > 4096:
        grid = 4096
    ctx.enqueue_function[_fill_const_kernel](
        ptr, Int64(val * 1.0e6), Int64(n), grid_dim=grid, block_dim=256)


def _fill(
    mut ctx: DeviceContext, addr: Int, n: Int, scale: Float64, mod: Int,
) raises:
    var ptr = UnsafePointer[Float32, origin=MutAnyOrigin](unsafe_from_address=addr)
    var grid = (n + 255) // 256
    if grid > 4096:
        grid = 4096
    ctx.enqueue_function[_fill_kernel](
        ptr, Int64(scale * 1.0e6), Int64(mod), Int64(n),
        grid_dim=grid, block_dim=256)


def main() raises:
    @parameter
    if not (is_defined["ALGENTA_GPU"]() and is_defined["ALGENTA_CUDA"]()):
        print("p3b_smallm_probe: needs -D ALGENTA_GPU -D ALGENTA_CUDA")
        return
    else:
        if not has_accelerator():
            print("p3b_smallm_probe: no accelerator")
            return

        var ctx = DeviceContext()
        print("p3b_smallm_probe: device:", ctx.name(), "| B =", B, "| reps =", REPS)

        # role table: (name, k, n)
        var names = List[String]()
        var ks = List[Int]()
        var ns = List[Int]()
        names.append("qkv_assign")
        ks.append(1024)
        ns.append(2560)
        names.append("o_accum")
        ks.append(2048)
        ns.append(1024)
        names.append("down_accum")
        ks.append(3072)
        ns.append(1024)

        # ── in-battery calibration: launch_cal's exact pattern (fresh buffers, no fill) ──
        var cwp = ctx.enqueue_create_buffer[DType.float32](2560 * 344)
        var cws = ctx.enqueue_create_buffer[DType.float32](2560 * 33)
        var cwz = ctx.enqueue_create_buffer[DType.float32](2560 * 33)
        var cx = ctx.enqueue_create_buffer[DType.float32](8 * 1024)
        var cy = ctx.enqueue_create_buffer[DType.float32](8 * 2560)
        _ = ctx.enqueue_function[_batched_p3_gemv_assign_kernel](
            cy.unsafe_ptr(), cx.unsafe_ptr(), cwp.unsafe_ptr(), cws.unsafe_ptr(),
            cwz.unsafe_ptr(), Int64(1024), Int64(2560), Int64(8),
            grid_dim=2560, block_dim=_P3B_TG)
        ctx.synchronize()
        var tc0 = perf_counter_ns()
        for _ in range(50):
            ctx.enqueue_function[_batched_p3_gemv_assign_kernel](
                cy.unsafe_ptr(), cx.unsafe_ptr(), cwp.unsafe_ptr(), cws.unsafe_ptr(),
                cwz.unsafe_ptr(), Int64(1024), Int64(2560), Int64(8),
                grid_dim=2560, block_dim=_P3B_TG)
        ctx.synchronize()
        print("calibration (launch_cal pattern):",
              Float64(perf_counter_ns() - tc0) / 50.0 / 1000.0, "us per launch")

        for role in range(3):
            var k = ks[role]
            var n = ns[role]
            var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
            var words_per_row = k_pack // _P3_QUANTS_PER_WORD
            var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

            var wp = ctx.enqueue_create_buffer[DType.float32](n * words_per_row)
            var ws = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
            var wz = ctx.enqueue_create_buffer[DType.float32](n * nblocks)
            var x = ctx.enqueue_create_buffer[DType.float32](B * k)
            var y = ctx.enqueue_create_buffer[DType.float32](B * n)
            # deterministic DEVICE-side fill (the first cut's map_to_host fills perturbed
            # the timing 800x — launch_cal_probe located it): scales ~1/128, zeros ~128,
            # quants patterned, acts ~0.0001
            _fill_const(ctx, Int(ws.unsafe_ptr()), n * nblocks, 0.0078125)
            _fill_const(ctx, Int(wz.unsafe_ptr()), n * nblocks, 128.0)
            _fill(ctx, Int(wp.unsafe_ptr()), n * words_per_row, 0.01, 251)
            _fill(ctx, Int(x.unsafe_ptr()), B * k, 0.0001, 97)
            ctx.synchronize()

            var weight_bytes = Float64(n) * Float64(words_per_row) * 4.0

            # ── V1 control (shipped) ──
            for _ in range(3):
                ctx.enqueue_function[_batched_p3_gemv_assign_kernel](
                    y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
                    wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
                    grid_dim=n, block_dim=_P3B_TG)
            ctx.synchronize()
            var t0 = perf_counter_ns()
            for _ in range(REPS):
                ctx.enqueue_function[_batched_p3_gemv_assign_kernel](
                    y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
                    wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
                    grid_dim=n, block_dim=_P3B_TG)
            var t_enq = Float64(perf_counter_ns() - t0) / Float64(REPS)
            ctx.synchronize()
            var v1_us = Float64(perf_counter_ns() - t0) / Float64(REPS)
            print(names[role], " V1 host-enqueue-only:", t_enq / 1000.0,
                  "us | enqueue+drain:", v1_us / 1000.0, "us")

            # ── V2 pipelined ──
            for _ in range(3):
                ctx.enqueue_function[_p3b_v2_assign_kernel](
                    y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
                    wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
                    grid_dim=n, block_dim=_V2_TG)
            ctx.synchronize()
            t0 = perf_counter_ns()
            for _ in range(REPS):
                ctx.enqueue_function[_p3b_v2_assign_kernel](
                    y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
                    wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
                    grid_dim=n, block_dim=_V2_TG)
            ctx.synchronize()
            var v2_us = Float64(perf_counter_ns() - t0) / Float64(REPS)

            # ── V3 two rows per block ──
            for _ in range(3):
                ctx.enqueue_function[_p3b_v3_assign_kernel](
                    y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
                    wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
                    grid_dim=n // 2, block_dim=_V2_TG)
            ctx.synchronize()
            t0 = perf_counter_ns()
            for _ in range(REPS):
                ctx.enqueue_function[_p3b_v3_assign_kernel](
                    y.unsafe_ptr(), x.unsafe_ptr(), wp.unsafe_ptr(), ws.unsafe_ptr(),
                    wz.unsafe_ptr(), Int64(k), Int64(n), Int64(B),
                    grid_dim=n // 2, block_dim=_V2_TG)
            ctx.synchronize()
            var v3_us = Float64(perf_counter_ns() - t0) / Float64(REPS)

            print(names[role], "k=", k, "n=", n, ":")
            print("  V1 shipped :", v1_us, "us ->", weight_bytes / (v1_us * 1e-6) / 1e9, "GB/s")
            print("  V2 pipeline:", v2_us, "us ->", weight_bytes / (v2_us * 1e-6) / 1e9,
                  "GB/s  (", v1_us / v2_us, "x )")
            print("  V3 2rows   :", v3_us, "us ->", weight_bytes / (v3_us * 1e-6) / 1e9,
                  "GB/s  (", v1_us / v3_us, "x )")

        print("p3b_smallm_probe: done")
