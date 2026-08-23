"""residentk.kernels_packed3_batched — the BATCHED (M = B rows, one weight sweep for all B
tokens) packed3 decode GEMM kernels: the A100 autopsy's lever L4. The continuous-batching
decode step streams the resident weights ONCE per step no matter how many sequences step
together — the f32 batched arm does that through `residentk.kernels_prefill_f32_v2`'s tiled
GEMMs at m_rows = B (2.62 GB/token-set at 93 GB/s = 28.9 ms TPOT); this file is the packed3
twin of the four weight-reading roles (qkv ASSIGN, o_proj ACCUM, gate/up+SwiGLU, down_proj
ACCUM) plus the batched lm_head+argmax tail, so the B-token step streams ~0.94 GB of packed3
words instead of 2.62 GB of f32. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32, uint8-packed
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_serve_batched_cuda.mojo --selftest
benchmark: benchmarks/llm_smoke/nvidia_race/enterprise_bench.py
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Nothing here is public, the same rule `residentk.kernels` states —
leading underscores keep these out of the inventory, the contract, and the generated
dispatch; only `residentk.session_cuda_batched_p3_graph` reaches them, gated behind
`CUDA_SESSION_BUILD` exactly the way every other residentk launch site gates.

RELATIONSHIP TO THE SINGLE-STREAM PACKED3 FAMILY
-------------------------------------------------
`residentk.kernels_packed3` carries the batch-1 GEMV arm (ONE output row per block, ONE
token's activation): 470-497 GB/s measured on this exact A100, gates ALL PASS. Per-row GEMV
at B tokens would sweep the weights B times — the exact loss continuous batching exists to
delete — so these kernels are the M=B form instead: ONE block per output row computes the
row's dot against ALL B activation rows, weights streamed ONCE. The front-end is
`_packed3_gemv_kernel_v2`'s verbatim (float4 word loads, int32 word-view shift/AND unpack,
hoisted block-32 crossing classification — bit-identical dequant values); what is new is
the B-wide activation side and the B-row reduction/tail.

INNER-LOOP DISCIPLINE (the measured cost this file's structure pays for)
-------------------------------------------------------------------------
nsys on the first cut of these kernels measured the four roles at only 40-70 GB/s effective
(vs the batch-1 probe's 470-497) at B = 8: per-weight-byte INSTRUCTION pressure, not
bandwidth, was the wall — a runtime-indexed `acc[b]` in thread-local memory costs a load +
store per element per row, and a dequant array costs a reload per use, tripling the chunk's
instruction count on top of the B x FMA work. This file's answer, mechanism by mechanism:
* NAMED DEQUANT SCALARS `d0..d11`: the chunk's twelve dequantized weights are computed ONCE
  into twelve explicit scalars (never an indexed array) and reused across all B rows.
* NAMED ACCUMULATORS `a0..a7` for the first eight sequence rows — the serve cells the race
  measures (B <= 8 hot) never touch an indexed accumulator in the chunk loop; rows b >= 8
  fall back to a thread-local `acc_hi` array (correct at every B, fast where it matters).
* UNIFORM `if B >= i` guards per unrolled row — branch-uniform across the whole block, so
  the unroll costs no divergence.
* VECTOR ACTIVATION LOADS: three coalesced float4s per row per chunk when the chunk sits
  fully inside `k`; only the boundary chunk (the padded tail) takes the guarded scalar path.

ACTIVATION TAIL (the one contract difference vs the batch-1 family): the batched activation
buffers are raw `[B, k]` — NOT zero-padded to `k_pack`. The padded quant slots exist only in
the final 12-element chunk of a row (k_pack - k <= 11), so every chunk fully inside `k` runs
the vector path and only the boundary chunk takes the per-element guarded path. The padding
quants still dequantize and multiply — against nothing: the guarded loads skip them, so
their contribution is exactly zero, the same invariant the batch-1 family buys with
activation-side zero padding.

REDUCTIONS copy the proven patterns: `_warp_sum` per 32-lane group (hardware shuffle, no
barrier) then ONE shared combine across the 8 groups per output row, per sequence row —
`residentk.kernels_batched_cuda._batched_lmhead_argmax_kernel_f32`'s shared layout for the
lm_head tail (`sv[sub * _BATCH_LMHEAD_MAX_ROWS + b]`), the same strict-`>` lowest-id
tie-break. Accumulation ORDER: per-lane chunk partials (chunks ascending) combined by the
two-level tree — the batch-1 p3 GEMV's own order extended across rows; these kernels add
quantization to the batched decode path, so the f32 batched arm stays the A/B control and
the serve driver's selftest (16/16 campaign oracle + token identity) is the acceptance gate.

Mojo 1.0.0 kernel-parameter discipline: every scalar parameter is a fixed-width `Int64`
(DevicePassable), widened back to `Int` once at entry — `accel/launch.mojo`'s pattern.
"""

from std.origin import MutAnyOrigin
from std.gpu import block_idx, grid_dim, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import exp
from std.memory import bitcast, stack_allocation
from residentk.kernels import (
    _TG,
    _LANES,
    _SUBS,
    _NEG_HUGE,
    _BATCH_LMHEAD_MAX_ROWS,
)
from residentk.kernels_packed3 import (
    _P3_QUANTS_PER_WORD,
    _P3_CHUNK,
    _P3_BLOCK,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — the SAME spelling `residentk.kernels`
uses. The packed weight stream is typed Float32 too, on purpose: it is read as Float32 WORDS
(the only SIMD load this backend streams at HBM speed) and reinterpreted AFTER the load —
`residentk.kernels_packed3`'s Layout spec."""

alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]
"""A device Int32 buffer — the argmax token ids, the same spelling `residentk.kernels` uses."""

comptime _P3B_TG: Int = 128
"""Threads per block for the three GEMM roles: 4 warps. MEASURED, NOT ASSUMED: the first
256-thread cut left 66% of the lanes idle at k=1024 (k_pack=1032 chunks / 256 lanes — ncu:
58% barrier stall, 57 GB/s) and starved the k=3072 roles of in-flight weight loads (one
chunk per lane, long-scoreboard 28%). At 128 threads the same chunks distribute 86/128
(k=1024), 171 -> two chunks on 43 lanes (k=2048), 256 -> two chunks per lane (k=3072) —
more active lanes AND more concurrent weight loads per lane."""

comptime _P3B_GROUPS: Int = _P3B_TG // 32
"""Warp groups in the two-level reduction at `_P3B_TG` threads."""


def _batched_p3_gemv_assign_kernel(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, B_i64: Int64,
):
    """`y[B, n] = x[B, k] @ W^T` with `W` held packed3, one output row per block
    (`grid_dim = n`, `block_dim = _TG`), ASSIGNING into `y` — the batched qkv-projection
    role. CONTRACT: `B <= _BATCH_LMHEAD_MAX_ROWS`; `x` is raw `[B, k]` (the activation-tail
    section of the module docstring); `wp` holds `n * words_per_row` words, `wscale`/`wzero`
    `n * nblocks` each."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var B = Int(B_i64)
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
    var lane = tid % _LANES
    var sub = tid // _LANES

    # named accumulators, rows 0..7; the array carries rows >= 8 (cold cells)
    var a0 = Float32(0.0)
    var a1 = Float32(0.0)
    var a2 = Float32(0.0)
    var a3 = Float32(0.0)
    var a4 = Float32(0.0)
    var a5 = Float32(0.0)
    var a6 = Float32(0.0)
    var a7 = Float32(0.0)
    for b in range(8, B):
        acc_hi[b - 8] = Float32(0.0)

    var wbase = row * words_per_row
    var sbase = row * nblocks

    # hoisted crossing classification — `_packed3_gemv_kernel_v2`'s own: the lane's chunk
    # offsets are `tid*12 + i*(256*12)` and `256*12 % 32 == 0`, so the residue is invariant.
    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    var t = tid * _P3_CHUNK
    while t < k_pack:
        var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
        var w = bitcast[DType.int32, 4](v)
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

        # ── dequant ONCE into named scalars, reuse across all B rows (ascending element
        #    order, the batch-1 kernel's own expression) ──
        var d0 = (Float32(w[0] & 255) - z0) * s0
        var d1 = (Float32((w[0] >> 8) & 255) - z0) * s0
        var d2 = (Float32((w[0] >> 16) & 255) - z0) * s0
        var d3 = (Float32(w[1] & 255) - z0) * s0
        var d4 = (Float32((w[1] >> 8) & 255) - z_lo) * s_lo
        var d5 = (Float32((w[1] >> 16) & 255) - z_lo) * s_lo
        var d6 = (Float32(w[2] & 255) - z_lo) * s_lo
        var d7 = (Float32((w[2] >> 8) & 255) - z_lo) * s_lo
        var d8 = (Float32((w[2] >> 16) & 255) - z_hi) * s_hi
        var d9 = (Float32(w[3] & 255) - z_hi) * s_hi
        var d10 = (Float32((w[3] >> 8) & 255) - z_hi) * s_hi
        var d11 = (Float32((w[3] >> 16) & 255) - z_hi) * s_hi

        if t + _P3_CHUNK <= k:
            # ── the fast path: three coalesced float4 activation loads per row ──
            if B >= 1:
                var xv0 = x.load[width=4](t)
                var xv1 = x.load[width=4](t + 4)
                var xv2 = x.load[width=4](t + 8)
                a0 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a0 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a0 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 2:
                var xv0 = x.load[width=4](k + t)
                var xv1 = x.load[width=4](k + t + 4)
                var xv2 = x.load[width=4](k + t + 8)
                a1 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a1 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a1 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 3:
                var xv0 = x.load[width=4](2 * k + t)
                var xv1 = x.load[width=4](2 * k + t + 4)
                var xv2 = x.load[width=4](2 * k + t + 8)
                a2 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a2 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a2 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 4:
                var xv0 = x.load[width=4](3 * k + t)
                var xv1 = x.load[width=4](3 * k + t + 4)
                var xv2 = x.load[width=4](3 * k + t + 8)
                a3 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a3 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a3 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 5:
                var xv0 = x.load[width=4](4 * k + t)
                var xv1 = x.load[width=4](4 * k + t + 4)
                var xv2 = x.load[width=4](4 * k + t + 8)
                a4 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a4 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a4 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 6:
                var xv0 = x.load[width=4](5 * k + t)
                var xv1 = x.load[width=4](5 * k + t + 4)
                var xv2 = x.load[width=4](5 * k + t + 8)
                a5 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a5 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a5 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 7:
                var xv0 = x.load[width=4](6 * k + t)
                var xv1 = x.load[width=4](6 * k + t + 4)
                var xv2 = x.load[width=4](6 * k + t + 8)
                a6 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a6 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a6 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 8:
                var xv0 = x.load[width=4](7 * k + t)
                var xv1 = x.load[width=4](7 * k + t + 4)
                var xv2 = x.load[width=4](7 * k + t + 8)
                a7 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a7 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a7 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            for b in range(8, B):
                var xb = b * k + t
                var xv0 = x.load[width=4](xb)
                var xv1 = x.load[width=4](xb + 4)
                var xv2 = x.load[width=4](xb + 8)
                var av = d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                av += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                av += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                acc_hi[b - 8] += av
        else:
            # ── boundary chunk: the k_pack - k padding slots have no activation element ──
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
                    if B >= 1:
                        a0 += de * x[t + e]
                    if B >= 2:
                        a1 += de * x[k + t + e]
                    if B >= 3:
                        a2 += de * x[2 * k + t + e]
                    if B >= 4:
                        a3 += de * x[3 * k + t + e]
                    if B >= 5:
                        a4 += de * x[4 * k + t + e]
                    if B >= 6:
                        a5 += de * x[5 * k + t + e]
                    if B >= 7:
                        a6 += de * x[6 * k + t + e]
                    if B >= 8:
                        a7 += de * x[7 * k + t + e]
                    for b in range(8, B):
                        acc_hi[b - 8] += de * x[b * k + t + e]
        t += _P3B_TG * _P3_CHUNK

    # ── two-level reduction per sequence row: warp shuffle sum per group, ONE shared
    #    combine across the 8 groups, then one writer per sequence row ──
    if B >= 1:
        var total = _warp_sum(a0)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
    if B >= 2:
        var total = _warp_sum(a1)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
    if B >= 3:
        var total = _warp_sum(a2)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
    if B >= 4:
        var total = _warp_sum(a3)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
    if B >= 5:
        var total = _warp_sum(a4)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
    if B >= 6:
        var total = _warp_sum(a5)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
    if B >= 7:
        var total = _warp_sum(a6)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
    if B >= 8:
        var total = _warp_sum(a7)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
    for b in range(8, B):
        var total = _warp_sum(acc_hi[b - 8])
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
    barrier()
    if tid < B:
        var o = Float32(0.0)
        for g in range(_P3B_GROUPS):
            o += grp[g * _BATCH_LMHEAD_MAX_ROWS + tid]
        y[tid * n + row] = o


def _batched_p3_gemv_accum_kernel(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, B_i64: Int64,
):
    """`y[B, n] += x[B, k] @ W^T` with `W` held packed3 — the batched o_proj / down_proj
    residual-add roles. Structurally `_batched_p3_gemv_assign_kernel` verbatim except the
    epilogue ACCUMULATES (`y[b*n + row] = y[b*n + row] + o`)."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var B = Int(B_i64)
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
    var lane = tid % _LANES
    var sub = tid // _LANES

    var a0 = Float32(0.0)
    var a1 = Float32(0.0)
    var a2 = Float32(0.0)
    var a3 = Float32(0.0)
    var a4 = Float32(0.0)
    var a5 = Float32(0.0)
    var a6 = Float32(0.0)
    var a7 = Float32(0.0)
    for b in range(8, B):
        acc_hi[b - 8] = Float32(0.0)

    var wbase = row * words_per_row
    var sbase = row * nblocks

    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    var t = tid * _P3_CHUNK
    while t < k_pack:
        var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
        var w = bitcast[DType.int32, 4](v)
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

        var d0 = (Float32(w[0] & 255) - z0) * s0
        var d1 = (Float32((w[0] >> 8) & 255) - z0) * s0
        var d2 = (Float32((w[0] >> 16) & 255) - z0) * s0
        var d3 = (Float32(w[1] & 255) - z0) * s0
        var d4 = (Float32((w[1] >> 8) & 255) - z_lo) * s_lo
        var d5 = (Float32((w[1] >> 16) & 255) - z_lo) * s_lo
        var d6 = (Float32(w[2] & 255) - z_lo) * s_lo
        var d7 = (Float32((w[2] >> 8) & 255) - z_lo) * s_lo
        var d8 = (Float32((w[2] >> 16) & 255) - z_hi) * s_hi
        var d9 = (Float32(w[3] & 255) - z_hi) * s_hi
        var d10 = (Float32((w[3] >> 8) & 255) - z_hi) * s_hi
        var d11 = (Float32((w[3] >> 16) & 255) - z_hi) * s_hi

        if t + _P3_CHUNK <= k:
            if B >= 1:
                var xv0 = x.load[width=4](t)
                var xv1 = x.load[width=4](t + 4)
                var xv2 = x.load[width=4](t + 8)
                a0 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a0 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a0 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 2:
                var xv0 = x.load[width=4](k + t)
                var xv1 = x.load[width=4](k + t + 4)
                var xv2 = x.load[width=4](k + t + 8)
                a1 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a1 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a1 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 3:
                var xv0 = x.load[width=4](2 * k + t)
                var xv1 = x.load[width=4](2 * k + t + 4)
                var xv2 = x.load[width=4](2 * k + t + 8)
                a2 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a2 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a2 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 4:
                var xv0 = x.load[width=4](3 * k + t)
                var xv1 = x.load[width=4](3 * k + t + 4)
                var xv2 = x.load[width=4](3 * k + t + 8)
                a3 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a3 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a3 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 5:
                var xv0 = x.load[width=4](4 * k + t)
                var xv1 = x.load[width=4](4 * k + t + 4)
                var xv2 = x.load[width=4](4 * k + t + 8)
                a4 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a4 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a4 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 6:
                var xv0 = x.load[width=4](5 * k + t)
                var xv1 = x.load[width=4](5 * k + t + 4)
                var xv2 = x.load[width=4](5 * k + t + 8)
                a5 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a5 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a5 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 7:
                var xv0 = x.load[width=4](6 * k + t)
                var xv1 = x.load[width=4](6 * k + t + 4)
                var xv2 = x.load[width=4](6 * k + t + 8)
                a6 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a6 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a6 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            if B >= 8:
                var xv0 = x.load[width=4](7 * k + t)
                var xv1 = x.load[width=4](7 * k + t + 4)
                var xv2 = x.load[width=4](7 * k + t + 8)
                a7 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a7 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a7 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
            for b in range(8, B):
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
                    if B >= 1:
                        a0 += de * x[t + e]
                    if B >= 2:
                        a1 += de * x[k + t + e]
                    if B >= 3:
                        a2 += de * x[2 * k + t + e]
                    if B >= 4:
                        a3 += de * x[3 * k + t + e]
                    if B >= 5:
                        a4 += de * x[4 * k + t + e]
                    if B >= 6:
                        a5 += de * x[5 * k + t + e]
                    if B >= 7:
                        a6 += de * x[6 * k + t + e]
                    if B >= 8:
                        a7 += de * x[7 * k + t + e]
                    for b in range(8, B):
                        acc_hi[b - 8] += de * x[b * k + t + e]
        t += _P3B_TG * _P3_CHUNK

    if B >= 1:
        var total = _warp_sum(a0)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
    if B >= 2:
        var total = _warp_sum(a1)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
    if B >= 3:
        var total = _warp_sum(a2)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
    if B >= 4:
        var total = _warp_sum(a3)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
    if B >= 5:
        var total = _warp_sum(a4)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
    if B >= 6:
        var total = _warp_sum(a5)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
    if B >= 7:
        var total = _warp_sum(a6)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
    if B >= 8:
        var total = _warp_sum(a7)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
    for b in range(8, B):
        var total = _warp_sum(acc_hi[b - 8])
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
    barrier()
    if tid < B:
        var o = Float32(0.0)
        for g in range(_P3B_GROUPS):
            o += grp[g * _BATCH_LMHEAD_MAX_ROWS + tid]
        y[tid * n + row] = y[tid * n + row] + o


def _batched_p3_swiglu_kernel(
    act: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_ff_i64: Int64, B_i64: Int64,
):
    """`act[B, n_ff] = silu(x @ W_gate^T) * (x @ W_up^T)` — the batched gate/up + SwiGLU
    role. `wp` is the resident `[2*n_ff, k]` gate-THEN-up packed concatenation: one block per
    output column `j` streams BOTH weight rows `j` (gate) and `n_ff + j` (up) against all B
    activation rows. Named gate/up accumulator pairs `g0..g7`/`u0..u7` (rows >= 8 fall to
    the thread-local arrays); `silu(g) = g / (1 + exp(-g))` — the f32 v2 swiglu kernel's
    own expression."""
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    var B = Int(B_i64)
    var j = Int(block_idx.x)
    if j >= n_ff:
        return
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var grp_g = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var grp_u = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var g_hi = stack_allocation[_BATCH_LMHEAD_MAX_ROWS - 8, DType.float32]()
    var u_hi = stack_allocation[_BATCH_LMHEAD_MAX_ROWS - 8, DType.float32]()

    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var g0 = Float32(0.0)
    var g1 = Float32(0.0)
    var g2 = Float32(0.0)
    var g3 = Float32(0.0)
    var g4 = Float32(0.0)
    var g5 = Float32(0.0)
    var g6 = Float32(0.0)
    var g7 = Float32(0.0)
    var u0 = Float32(0.0)
    var u1 = Float32(0.0)
    var u2 = Float32(0.0)
    var u3 = Float32(0.0)
    var u4 = Float32(0.0)
    var u5 = Float32(0.0)
    var u6 = Float32(0.0)
    var u7 = Float32(0.0)
    for b in range(8, B):
        g_hi[b - 8] = Float32(0.0)
        u_hi[b - 8] = Float32(0.0)

    var wgbase = j * words_per_row
    var wubase = (n_ff + j) * words_per_row
    var sgbase = j * nblocks
    var subase = (n_ff + j) * nblocks

    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    var t = tid * _P3_CHUNK
    while t < k_pack:
        var vg = wp.load[width=4](wgbase + t // _P3_QUANTS_PER_WORD)
        var wg4 = bitcast[DType.int32, 4](vg)
        var vu = wp.load[width=4](wubase + t // _P3_QUANTS_PER_WORD)
        var wu4 = bitcast[DType.int32, 4](vu)

        var blk = t >> 5
        # gate row scale/zero
        var gs0 = wscale[sgbase + blk]
        var gz0 = wzero[sgbase + blk]
        var gs_lo = gs0
        var gz_lo = gz0
        var gs_hi = gs0
        var gz_hi = gz0
        if cross_hi:
            gs_hi = wscale[sgbase + blk + 1]
            gz_hi = wzero[sgbase + blk + 1]
            if cross_lo:
                gs_lo = gs_hi
                gz_lo = gz_hi
        # up row scale/zero
        var us0 = wscale[subase + blk]
        var uz0 = wzero[subase + blk]
        var us_lo = us0
        var uz_lo = uz0
        var us_hi = us0
        var uz_hi = uz0
        if cross_hi:
            us_hi = wscale[subase + blk + 1]
            uz_hi = wzero[subase + blk + 1]
            if cross_lo:
                us_lo = us_hi
                uz_lo = uz_hi

        var dg0 = (Float32(wg4[0] & 255) - gz0) * gs0
        var dg1 = (Float32((wg4[0] >> 8) & 255) - gz0) * gs0
        var dg2 = (Float32((wg4[0] >> 16) & 255) - gz0) * gs0
        var dg3 = (Float32(wg4[1] & 255) - gz0) * gs0
        var dg4 = (Float32((wg4[1] >> 8) & 255) - gz_lo) * gs_lo
        var dg5 = (Float32((wg4[1] >> 16) & 255) - gz_lo) * gs_lo
        var dg6 = (Float32(wg4[2] & 255) - gz_lo) * gs_lo
        var dg7 = (Float32((wg4[2] >> 8) & 255) - gz_lo) * gs_lo
        var dg8 = (Float32((wg4[2] >> 16) & 255) - gz_hi) * gs_hi
        var dg9 = (Float32(wg4[3] & 255) - gz_hi) * gs_hi
        var dg10 = (Float32((wg4[3] >> 8) & 255) - gz_hi) * gs_hi
        var dg11 = (Float32((wg4[3] >> 16) & 255) - gz_hi) * gs_hi

        var du0 = (Float32(wu4[0] & 255) - uz0) * us0
        var du1 = (Float32((wu4[0] >> 8) & 255) - uz0) * us0
        var du2 = (Float32((wu4[0] >> 16) & 255) - uz0) * us0
        var du3 = (Float32(wu4[1] & 255) - uz0) * us0
        var du4 = (Float32((wu4[1] >> 8) & 255) - uz_lo) * us_lo
        var du5 = (Float32((wu4[1] >> 16) & 255) - uz_lo) * us_lo
        var du6 = (Float32(wu4[2] & 255) - uz_lo) * us_lo
        var du7 = (Float32((wu4[2] >> 8) & 255) - uz_lo) * us_lo
        var du8 = (Float32((wu4[2] >> 16) & 255) - uz_hi) * us_hi
        var du9 = (Float32(wu4[3] & 255) - uz_hi) * us_hi
        var du10 = (Float32((wu4[3] >> 8) & 255) - uz_hi) * us_hi
        var du11 = (Float32((wu4[3] >> 16) & 255) - uz_hi) * us_hi

        if t + _P3_CHUNK <= k:
            if B >= 1:
                var xv0 = x.load[width=4](t)
                var xv1 = x.load[width=4](t + 4)
                var xv2 = x.load[width=4](t + 8)
                g0 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g0 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g0 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u0 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u0 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u0 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            if B >= 2:
                var xv0 = x.load[width=4](k + t)
                var xv1 = x.load[width=4](k + t + 4)
                var xv2 = x.load[width=4](k + t + 8)
                g1 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g1 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g1 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u1 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u1 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u1 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            if B >= 3:
                var xv0 = x.load[width=4](2 * k + t)
                var xv1 = x.load[width=4](2 * k + t + 4)
                var xv2 = x.load[width=4](2 * k + t + 8)
                g2 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g2 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g2 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u2 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u2 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u2 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            if B >= 4:
                var xv0 = x.load[width=4](3 * k + t)
                var xv1 = x.load[width=4](3 * k + t + 4)
                var xv2 = x.load[width=4](3 * k + t + 8)
                g3 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g3 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g3 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u3 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u3 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u3 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            if B >= 5:
                var xv0 = x.load[width=4](4 * k + t)
                var xv1 = x.load[width=4](4 * k + t + 4)
                var xv2 = x.load[width=4](4 * k + t + 8)
                g4 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g4 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g4 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u4 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u4 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u4 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            if B >= 6:
                var xv0 = x.load[width=4](5 * k + t)
                var xv1 = x.load[width=4](5 * k + t + 4)
                var xv2 = x.load[width=4](5 * k + t + 8)
                g5 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g5 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g5 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u5 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u5 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u5 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            if B >= 7:
                var xv0 = x.load[width=4](6 * k + t)
                var xv1 = x.load[width=4](6 * k + t + 4)
                var xv2 = x.load[width=4](6 * k + t + 8)
                g6 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g6 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g6 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u6 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u6 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u6 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            if B >= 8:
                var xv0 = x.load[width=4](7 * k + t)
                var xv1 = x.load[width=4](7 * k + t + 4)
                var xv2 = x.load[width=4](7 * k + t + 8)
                g7 += dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                g7 += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                g7 += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                u7 += du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                u7 += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                u7 += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
            for b in range(8, B):
                var xb = b * k + t
                var xv0 = x.load[width=4](xb)
                var xv1 = x.load[width=4](xb + 4)
                var xv2 = x.load[width=4](xb + 8)
                var gv = dg0 * xv0[0] + dg1 * xv0[1] + dg2 * xv0[2] + dg3 * xv0[3]
                gv += dg4 * xv1[0] + dg5 * xv1[1] + dg6 * xv1[2] + dg7 * xv1[3]
                gv += dg8 * xv2[0] + dg9 * xv2[1] + dg10 * xv2[2] + dg11 * xv2[3]
                g_hi[b - 8] += gv
                var uv = du0 * xv0[0] + du1 * xv0[1] + du2 * xv0[2] + du3 * xv0[3]
                uv += du4 * xv1[0] + du5 * xv1[1] + du6 * xv1[2] + du7 * xv1[3]
                uv += du8 * xv2[0] + du9 * xv2[1] + du10 * xv2[2] + du11 * xv2[3]
                u_hi[b - 8] += uv
        else:
            var dqg = stack_allocation[_P3_CHUNK, DType.float32]()
            var dqu = stack_allocation[_P3_CHUNK, DType.float32]()
            dqg[0] = dg0
            dqg[1] = dg1
            dqg[2] = dg2
            dqg[3] = dg3
            dqg[4] = dg4
            dqg[5] = dg5
            dqg[6] = dg6
            dqg[7] = dg7
            dqg[8] = dg8
            dqg[9] = dg9
            dqg[10] = dg10
            dqg[11] = dg11
            dqu[0] = du0
            dqu[1] = du1
            dqu[2] = du2
            dqu[3] = du3
            dqu[4] = du4
            dqu[5] = du5
            dqu[6] = du6
            dqu[7] = du7
            dqu[8] = du8
            dqu[9] = du9
            dqu[10] = du10
            dqu[11] = du11
            for e in range(_P3_CHUNK):
                if t + e < k:
                    var xv = x[t + e]
                    if B >= 1:
                        g0 += dqg[e] * xv
                        u0 += dqu[e] * xv
                    if B >= 2:
                        var xv2r = x[k + t + e]
                        g1 += dqg[e] * xv2r
                        u1 += dqu[e] * xv2r
                    if B >= 3:
                        var xv3r = x[2 * k + t + e]
                        g2 += dqg[e] * xv3r
                        u2 += dqu[e] * xv3r
                    if B >= 4:
                        var xv4r = x[3 * k + t + e]
                        g3 += dqg[e] * xv4r
                        u3 += dqu[e] * xv4r
                    if B >= 5:
                        var xv5r = x[4 * k + t + e]
                        g4 += dqg[e] * xv5r
                        u4 += dqu[e] * xv5r
                    if B >= 6:
                        var xv6r = x[5 * k + t + e]
                        g5 += dqg[e] * xv6r
                        u5 += dqu[e] * xv6r
                    if B >= 7:
                        var xv7r = x[6 * k + t + e]
                        g6 += dqg[e] * xv7r
                        u6 += dqu[e] * xv7r
                    if B >= 8:
                        var xv8r = x[7 * k + t + e]
                        g7 += dqg[e] * xv8r
                        u7 += dqu[e] * xv8r
                    for b in range(8, B):
                        var xbr = x[b * k + t + e]
                        g_hi[b - 8] += dqg[e] * xbr
                        u_hi[b - 8] += dqu[e] * xbr
        t += _P3B_TG * _P3_CHUNK

    if B >= 1:
        var total = _warp_sum(g0)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
        total = _warp_sum(u0)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
    if B >= 2:
        var total = _warp_sum(g1)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
        total = _warp_sum(u1)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
    if B >= 3:
        var total = _warp_sum(g2)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
        total = _warp_sum(u2)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
    if B >= 4:
        var total = _warp_sum(g3)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
        total = _warp_sum(u3)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
    if B >= 5:
        var total = _warp_sum(g4)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
        total = _warp_sum(u4)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
    if B >= 6:
        var total = _warp_sum(g5)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
        total = _warp_sum(u5)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
    if B >= 7:
        var total = _warp_sum(g6)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
        total = _warp_sum(u6)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
    if B >= 8:
        var total = _warp_sum(g7)
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
        total = _warp_sum(u7)
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
    for b in range(8, B):
        var total = _warp_sum(g_hi[b - 8])
        if lane == 0:
            grp_g[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
        total = _warp_sum(u_hi[b - 8])
        if lane == 0:
            grp_u[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
    barrier()
    if tid < B:
        var g = Float32(0.0)
        var u = Float32(0.0)
        for gg in range(_P3B_GROUPS):
            g += grp_g[gg * _BATCH_LMHEAD_MAX_ROWS + tid]
            u += grp_u[gg * _BATCH_LMHEAD_MAX_ROWS + tid]
        act[tid * n_ff + j] = (g / (Float32(1.0) + exp(-g))) * u


def _batched_lmhead_argmax_kernel_p3(
    blk_val: _FP, blk_idx: _IP, xn: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    B_i64: Int64, k_i64: Int64, n_i64: Int64, n_iters_i64: Int64,
):
    """Batched lm_head + per-vocab-slice argmax with the vocabulary table held packed3 —
    the packed3 twin of `residentk.kernels_batched_cuda._batched_lmhead_argmax_kernel_f32`:
    `grid_dim = _LM_BLOCKS`, `block_dim = _TG`, same vocab partitioning (column
    `j = block_idx.x*_SUBS + sub + it*stride_cols`), same all-B-rows-per-weight-sweep
    structure (each SIMD group's vocab row streams ONCE for all B rows), same strict-`>`
    lowest-id tie-break, same `blk_val[b*grid_dim.x + block_idx.x]` output layout consumed
    by the weight-agnostic `_batched_argmax_reduce_kernel_simd`. `xn` is `[B, k]`
    PRE-NORMALIZED by the B-row final rmsnorm dispatch that runs immediately before this
    one — this kernel never normalizes. Named per-row accumulators for B <= 8 (the hot serve
    cells), array fallback beyond; `n_iters` is passed in (uniform trip count: the loop body
    carries barriers through the reductions; a barrier reached by only some threads hangs
    the GPU)."""
    var B = Int(B_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    var n_iters = Int(n_iters_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var sv = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var si = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.int32, address_space = AddressSpace.SHARED
    ]()
    var best = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.float32]()
    var best_i = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.int32]()
    var acc_hi = stack_allocation[_BATCH_LMHEAD_MAX_ROWS - 8, DType.float32]()

    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    for b in range(B):
        best[b] = _NEG_HUGE
        best_i[b] = Int32(-1)

    var stride_cols = Int(grid_dim.x) * _SUBS

    var r0 = (lane * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        if j < n:
            var a0 = Float32(0.0)
            var a1 = Float32(0.0)
            var a2 = Float32(0.0)
            var a3 = Float32(0.0)
            var a4 = Float32(0.0)
            var a5 = Float32(0.0)
            var a6 = Float32(0.0)
            var a7 = Float32(0.0)
            for b in range(8, B):
                acc_hi[b - 8] = Float32(0.0)

            var wbase = j * words_per_row
            var sbase = j * nblocks
            var t = lane * _P3_CHUNK
            while t < k_pack:
                var v = wp.load[width=4](wbase + t // _P3_QUANTS_PER_WORD)
                var w = bitcast[DType.int32, 4](v)
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

                var d0 = (Float32(w[0] & 255) - z0) * s0
                var d1 = (Float32((w[0] >> 8) & 255) - z0) * s0
                var d2 = (Float32((w[0] >> 16) & 255) - z0) * s0
                var d3 = (Float32(w[1] & 255) - z0) * s0
                var d4 = (Float32((w[1] >> 8) & 255) - z_lo) * s_lo
                var d5 = (Float32((w[1] >> 16) & 255) - z_lo) * s_lo
                var d6 = (Float32(w[2] & 255) - z_lo) * s_lo
                var d7 = (Float32((w[2] >> 8) & 255) - z_lo) * s_lo
                var d8 = (Float32((w[2] >> 16) & 255) - z_hi) * s_hi
                var d9 = (Float32(w[3] & 255) - z_hi) * s_hi
                var d10 = (Float32((w[3] >> 8) & 255) - z_hi) * s_hi
                var d11 = (Float32((w[3] >> 16) & 255) - z_hi) * s_hi

                if t + _P3_CHUNK <= k:
                    if B >= 1:
                        var xv0 = xn.load[width=4](t)
                        var xv1 = xn.load[width=4](t + 4)
                        var xv2 = xn.load[width=4](t + 8)
                        a0 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a0 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a0 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    if B >= 2:
                        var xv0 = xn.load[width=4](k + t)
                        var xv1 = xn.load[width=4](k + t + 4)
                        var xv2 = xn.load[width=4](k + t + 8)
                        a1 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a1 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a1 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    if B >= 3:
                        var xv0 = xn.load[width=4](2 * k + t)
                        var xv1 = xn.load[width=4](2 * k + t + 4)
                        var xv2 = xn.load[width=4](2 * k + t + 8)
                        a2 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a2 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a2 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    if B >= 4:
                        var xv0 = xn.load[width=4](3 * k + t)
                        var xv1 = xn.load[width=4](3 * k + t + 4)
                        var xv2 = xn.load[width=4](3 * k + t + 8)
                        a3 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a3 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a3 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    if B >= 5:
                        var xv0 = xn.load[width=4](4 * k + t)
                        var xv1 = xn.load[width=4](4 * k + t + 4)
                        var xv2 = xn.load[width=4](4 * k + t + 8)
                        a4 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a4 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a4 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    if B >= 6:
                        var xv0 = xn.load[width=4](5 * k + t)
                        var xv1 = xn.load[width=4](5 * k + t + 4)
                        var xv2 = xn.load[width=4](5 * k + t + 8)
                        a5 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a5 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a5 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    if B >= 7:
                        var xv0 = xn.load[width=4](6 * k + t)
                        var xv1 = xn.load[width=4](6 * k + t + 4)
                        var xv2 = xn.load[width=4](6 * k + t + 8)
                        a6 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a6 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a6 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    if B >= 8:
                        var xv0 = xn.load[width=4](7 * k + t)
                        var xv1 = xn.load[width=4](7 * k + t + 4)
                        var xv2 = xn.load[width=4](7 * k + t + 8)
                        a7 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                        a7 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                        a7 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                    for b in range(8, B):
                        var xb = b * k + t
                        var xv0 = xn.load[width=4](xb)
                        var xv1 = xn.load[width=4](xb + 4)
                        var xv2 = xn.load[width=4](xb + 8)
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
                            if B >= 1:
                                a0 += de * xn[t + e]
                            if B >= 2:
                                a1 += de * xn[k + t + e]
                            if B >= 3:
                                a2 += de * xn[2 * k + t + e]
                            if B >= 4:
                                a3 += de * xn[3 * k + t + e]
                            if B >= 5:
                                a4 += de * xn[4 * k + t + e]
                            if B >= 6:
                                a5 += de * xn[5 * k + t + e]
                            if B >= 7:
                                a6 += de * xn[6 * k + t + e]
                            if B >= 8:
                                a7 += de * xn[7 * k + t + e]
                            for b in range(8, B):
                                acc_hi[b - 8] += de * xn[b * k + t + e]
                t += _LANES * _P3_CHUNK

            if B >= 1:
                var total = _warp_sum(a0)
                if lane == 0 and total > best[0]:
                    best[0] = total
                    best_i[0] = Int32(j)
            if B >= 2:
                var total = _warp_sum(a1)
                if lane == 0 and total > best[1]:
                    best[1] = total
                    best_i[1] = Int32(j)
            if B >= 3:
                var total = _warp_sum(a2)
                if lane == 0 and total > best[2]:
                    best[2] = total
                    best_i[2] = Int32(j)
            if B >= 4:
                var total = _warp_sum(a3)
                if lane == 0 and total > best[3]:
                    best[3] = total
                    best_i[3] = Int32(j)
            if B >= 5:
                var total = _warp_sum(a4)
                if lane == 0 and total > best[4]:
                    best[4] = total
                    best_i[4] = Int32(j)
            if B >= 6:
                var total = _warp_sum(a5)
                if lane == 0 and total > best[5]:
                    best[5] = total
                    best_i[5] = Int32(j)
            if B >= 7:
                var total = _warp_sum(a6)
                if lane == 0 and total > best[6]:
                    best[6] = total
                    best_i[6] = Int32(j)
            if B >= 8:
                var total = _warp_sum(a7)
                if lane == 0 and total > best[7]:
                    best[7] = total
                    best_i[7] = Int32(j)
            for b in range(8, B):
                var total = _warp_sum(acc_hi[b - 8])
                if lane == 0 and total > best[b]:
                    best[b] = total
                    best_i[b] = Int32(j)

    if lane == 0:
        for b in range(B):
            sv[sub * _BATCH_LMHEAD_MAX_ROWS + b] = best[b]
            si[sub * _BATCH_LMHEAD_MAX_ROWS + b] = best_i[b]
    barrier()
    if tid == 0:
        for b in range(B):
            var bv = sv[b]
            var bi = si[b]
            for u in range(1, _SUBS):
                # Strictly greater, so the lowest id survives an exact tie.
                if sv[u * _BATCH_LMHEAD_MAX_ROWS + b] > bv:
                    bv = sv[u * _BATCH_LMHEAD_MAX_ROWS + b]
                    bi = si[u * _BATCH_LMHEAD_MAX_ROWS + b]
            blk_val[b * Int(grid_dim.x) + Int(block_idx.x)] = bv
            blk_idx[b * Int(grid_dim.x) + Int(block_idx.x)] = bi


# ── LEVER L6: TWO OUTPUT ROWS PER BLOCK (the p3b_smallm_probe battery's measured winner,
#    ~1.27x effective weight GB/s over the shipped one-row form at B=8, all three serve
#    roles) — the B activation float4 loads amortize over two rows' packed-weight streams,
#    halving activation traffic per streamed weight byte and the grid size. Same dequant
#    expression, same ascending-k accumulation order per row, same two-level reduction per
#    row (row0 in the low group half of `grp`, row1 in the high half) — bit-identical
#    per-row results vs the one-row kernels, so the serve selftest's token-identity gate
#    applies without a quantization-flip asterisk. Grid is n/2 blocks: rows `row` and
#    `row + n/2`. Requires even n (every serve role's n is even at Qwen3 shapes). ──


def _batched_p3_gemv_assign_kernel_r2(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, B_i64: Int64,
):
    """LEVER L6 ASSIGN: `_batched_p3_gemv_assign_kernel` with TWO output rows per block
    (`grid_dim = n/2`): rows `row` and `row + n/2` stream their packed weights while the B
    activation float4s load once per chunk. Per-row accumulators (a0..a7 / c0..c7 + the
    two `acc_hi` halves for B>8), per-row warp-sum + shared combine. Bit-identical per-row
    math to the one-row kernel."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var B = Int(B_i64)
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
    var lane = tid % _LANES
    var sub = tid // _LANES

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
    for b in range(8, B):
        acc_hi[b - 8] = Float32(0.0)
        acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8] = Float32(0.0)

    var wbase0 = row0 * words_per_row
    var sbase0 = row0 * nblocks
    var wbase1 = row1 * words_per_row
    var sbase1 = row1 * nblocks

    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    var t = tid * _P3_CHUNK
    while t < k_pack:
        # ── row0's chunk: weight word + block-32 scales, dequant ONCE across all B rows ──
        var v = wp.load[width=4](wbase0 + t // _P3_QUANTS_PER_WORD)
        var w = bitcast[DType.int32, 4](v)
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
        var d0 = (Float32(w[0] & 255) - z0) * s0
        var d1 = (Float32((w[0] >> 8) & 255) - z0) * s0
        var d2 = (Float32((w[0] >> 16) & 255) - z0) * s0
        var d3 = (Float32(w[1] & 255) - z0) * s0
        var d4 = (Float32((w[1] >> 8) & 255) - z_lo) * s_lo
        var d5 = (Float32((w[1] >> 16) & 255) - z_lo) * s_lo
        var d6 = (Float32(w[2] & 255) - z_lo) * s_lo
        var d7 = (Float32((w[2] >> 8) & 255) - z_lo) * s_lo
        var d8 = (Float32((w[2] >> 16) & 255) - z_hi) * s_hi
        var d9 = (Float32(w[3] & 255) - z_hi) * s_hi
        var d10 = (Float32((w[3] >> 8) & 255) - z_hi) * s_hi
        var d11 = (Float32((w[3] >> 16) & 255) - z_hi) * s_hi

        # ── row1's chunk: the same structure, row1's weights/scales ──
        var v1w = wp.load[width=4](wbase1 + t // _P3_QUANTS_PER_WORD)
        var w1 = bitcast[DType.int32, 4](v1w)
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
        var e0 = (Float32(w1[0] & 255) - y0) * u0
        var e1 = (Float32((w1[0] >> 8) & 255) - y0) * u0
        var e2 = (Float32((w1[0] >> 16) & 255) - y0) * u0
        var e3 = (Float32(w1[1] & 255) - y0) * u0
        var e4 = (Float32((w1[1] >> 8) & 255) - y_lo) * u_lo
        var e5 = (Float32((w1[1] >> 16) & 255) - y_lo) * u_lo
        var e6 = (Float32(w1[2] & 255) - y_lo) * u_lo
        var e7 = (Float32((w1[2] >> 8) & 255) - y_lo) * u_lo
        var e8 = (Float32((w1[2] >> 16) & 255) - y_hi) * u_hi
        var e9 = (Float32(w1[3] & 255) - y_hi) * u_hi
        var e10 = (Float32((w1[3] >> 8) & 255) - y_hi) * u_hi
        var e11 = (Float32((w1[3] >> 16) & 255) - y_hi) * u_hi

        if t + _P3_CHUNK <= k:
            # ── the fast path: the B activation float4s load ONCE, feed BOTH rows ──
            if B >= 1:
                var xv0 = x.load[width=4](t)
                var xv1 = x.load[width=4](t + 4)
                var xv2 = x.load[width=4](t + 8)
                a0 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a0 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a0 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c0 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c0 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c0 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 2:
                var xv0 = x.load[width=4](k + t)
                var xv1 = x.load[width=4](k + t + 4)
                var xv2 = x.load[width=4](k + t + 8)
                a1 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a1 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a1 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c1 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c1 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c1 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 3:
                var xv0 = x.load[width=4](2 * k + t)
                var xv1 = x.load[width=4](2 * k + t + 4)
                var xv2 = x.load[width=4](2 * k + t + 8)
                a2 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a2 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a2 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c2 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c2 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c2 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 4:
                var xv0 = x.load[width=4](3 * k + t)
                var xv1 = x.load[width=4](3 * k + t + 4)
                var xv2 = x.load[width=4](3 * k + t + 8)
                a3 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a3 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a3 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c3 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c3 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c3 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 5:
                var xv0 = x.load[width=4](4 * k + t)
                var xv1 = x.load[width=4](4 * k + t + 4)
                var xv2 = x.load[width=4](4 * k + t + 8)
                a4 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a4 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a4 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c4 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c4 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c4 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 6:
                var xv0 = x.load[width=4](5 * k + t)
                var xv1 = x.load[width=4](5 * k + t + 4)
                var xv2 = x.load[width=4](5 * k + t + 8)
                a5 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a5 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a5 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c5 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c5 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c5 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 7:
                var xv0 = x.load[width=4](6 * k + t)
                var xv1 = x.load[width=4](6 * k + t + 4)
                var xv2 = x.load[width=4](6 * k + t + 8)
                a6 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a6 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a6 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c6 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c6 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c6 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 8:
                var xv0 = x.load[width=4](7 * k + t)
                var xv1 = x.load[width=4](7 * k + t + 4)
                var xv2 = x.load[width=4](7 * k + t + 8)
                a7 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a7 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a7 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c7 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c7 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c7 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            for b in range(8, B):
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
            # ── boundary chunk: the k_pack - k padding slots have no activation element ──
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
                    if B >= 1:
                        a0 += de * x[t + e]
                        c0 += ee * x[t + e]
                    if B >= 2:
                        a1 += de * x[k + t + e]
                        c1 += ee * x[k + t + e]
                    if B >= 3:
                        a2 += de * x[2 * k + t + e]
                        c2 += ee * x[2 * k + t + e]
                    if B >= 4:
                        a3 += de * x[3 * k + t + e]
                        c3 += ee * x[3 * k + t + e]
                    if B >= 5:
                        a4 += de * x[4 * k + t + e]
                        c4 += ee * x[4 * k + t + e]
                    if B >= 6:
                        a5 += de * x[5 * k + t + e]
                        c5 += ee * x[5 * k + t + e]
                    if B >= 7:
                        a6 += de * x[6 * k + t + e]
                        c6 += ee * x[6 * k + t + e]
                    if B >= 8:
                        a7 += de * x[7 * k + t + e]
                        c7 += ee * x[7 * k + t + e]
                    for b in range(8, B):
                        acc_hi[b - 8] += de * x[b * k + t + e]
                        acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8] += ee * x[b * k + t + e]
        t += _P3B_TG * _P3_CHUNK

    # ── two-level reduction per sequence row, BOTH output rows — the one-row kernel's
    #    exact merge order per row (row0 in the low group half, row1 in the high half) ──
    if B >= 1:
        var total = _warp_sum(a0)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
        total = _warp_sum(c0)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 0] = total
    if B >= 2:
        var total = _warp_sum(a1)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
        total = _warp_sum(c1)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 1] = total
    if B >= 3:
        var total = _warp_sum(a2)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
        total = _warp_sum(c2)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 2] = total
    if B >= 4:
        var total = _warp_sum(a3)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
        total = _warp_sum(c3)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 3] = total
    if B >= 5:
        var total = _warp_sum(a4)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
        total = _warp_sum(c4)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 4] = total
    if B >= 6:
        var total = _warp_sum(a5)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
        total = _warp_sum(c5)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 5] = total
    if B >= 7:
        var total = _warp_sum(a6)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
        total = _warp_sum(c6)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 6] = total
    if B >= 8:
        var total = _warp_sum(a7)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
        total = _warp_sum(c7)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 7] = total
    for b in range(8, B):
        var total = _warp_sum(acc_hi[b - 8])
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
        total = _warp_sum(acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8])
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + b] = total
    barrier()
    if tid < B:
        var o0 = Float32(0.0)
        var o1 = Float32(0.0)
        for g in range(_P3B_GROUPS):
            o0 += grp[g * _BATCH_LMHEAD_MAX_ROWS + tid]
            o1 += grp[(_P3B_GROUPS + g) * _BATCH_LMHEAD_MAX_ROWS + tid]
        y[tid * n + row0] = o0
        y[tid * n + row1] = o1


def _batched_p3_gemv_accum_kernel_r2(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, B_i64: Int64,
):
    """LEVER L6 ACCUM: `_batched_p3_gemv_assign_kernel_r2` verbatim except the epilogue
    ACCUMULATES into `y` (the o_proj / down_proj residual-add roles)."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var B = Int(B_i64)
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
    var lane = tid % _LANES
    var sub = tid // _LANES

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
    for b in range(8, B):
        acc_hi[b - 8] = Float32(0.0)
        acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8] = Float32(0.0)

    var wbase0 = row0 * words_per_row
    var sbase0 = row0 * nblocks
    var wbase1 = row1 * words_per_row
    var sbase1 = row1 * nblocks

    var r0 = (tid * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    var t = tid * _P3_CHUNK
    while t < k_pack:
        var v = wp.load[width=4](wbase0 + t // _P3_QUANTS_PER_WORD)
        var w = bitcast[DType.int32, 4](v)
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
        var d0 = (Float32(w[0] & 255) - z0) * s0
        var d1 = (Float32((w[0] >> 8) & 255) - z0) * s0
        var d2 = (Float32((w[0] >> 16) & 255) - z0) * s0
        var d3 = (Float32(w[1] & 255) - z0) * s0
        var d4 = (Float32((w[1] >> 8) & 255) - z_lo) * s_lo
        var d5 = (Float32((w[1] >> 16) & 255) - z_lo) * s_lo
        var d6 = (Float32(w[2] & 255) - z_lo) * s_lo
        var d7 = (Float32((w[2] >> 8) & 255) - z_lo) * s_lo
        var d8 = (Float32((w[2] >> 16) & 255) - z_hi) * s_hi
        var d9 = (Float32(w[3] & 255) - z_hi) * s_hi
        var d10 = (Float32((w[3] >> 8) & 255) - z_hi) * s_hi
        var d11 = (Float32((w[3] >> 16) & 255) - z_hi) * s_hi

        var v1w = wp.load[width=4](wbase1 + t // _P3_QUANTS_PER_WORD)
        var w1 = bitcast[DType.int32, 4](v1w)
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
        var e0 = (Float32(w1[0] & 255) - y0) * u0
        var e1 = (Float32((w1[0] >> 8) & 255) - y0) * u0
        var e2 = (Float32((w1[0] >> 16) & 255) - y0) * u0
        var e3 = (Float32(w1[1] & 255) - y0) * u0
        var e4 = (Float32((w1[1] >> 8) & 255) - y_lo) * u_lo
        var e5 = (Float32((w1[1] >> 16) & 255) - y_lo) * u_lo
        var e6 = (Float32(w1[2] & 255) - y_lo) * u_lo
        var e7 = (Float32((w1[2] >> 8) & 255) - y_lo) * u_lo
        var e8 = (Float32((w1[2] >> 16) & 255) - y_hi) * u_hi
        var e9 = (Float32(w1[3] & 255) - y_hi) * u_hi
        var e10 = (Float32((w1[3] >> 8) & 255) - y_hi) * u_hi
        var e11 = (Float32((w1[3] >> 16) & 255) - y_hi) * u_hi

        if t + _P3_CHUNK <= k:
            if B >= 1:
                var xv0 = x.load[width=4](t)
                var xv1 = x.load[width=4](t + 4)
                var xv2 = x.load[width=4](t + 8)
                a0 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a0 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a0 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c0 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c0 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c0 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 2:
                var xv0 = x.load[width=4](k + t)
                var xv1 = x.load[width=4](k + t + 4)
                var xv2 = x.load[width=4](k + t + 8)
                a1 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a1 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a1 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c1 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c1 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c1 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 3:
                var xv0 = x.load[width=4](2 * k + t)
                var xv1 = x.load[width=4](2 * k + t + 4)
                var xv2 = x.load[width=4](2 * k + t + 8)
                a2 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a2 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a2 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c2 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c2 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c2 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 4:
                var xv0 = x.load[width=4](3 * k + t)
                var xv1 = x.load[width=4](3 * k + t + 4)
                var xv2 = x.load[width=4](3 * k + t + 8)
                a3 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a3 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a3 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c3 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c3 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c3 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 5:
                var xv0 = x.load[width=4](4 * k + t)
                var xv1 = x.load[width=4](4 * k + t + 4)
                var xv2 = x.load[width=4](4 * k + t + 8)
                a4 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a4 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a4 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c4 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c4 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c4 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 6:
                var xv0 = x.load[width=4](5 * k + t)
                var xv1 = x.load[width=4](5 * k + t + 4)
                var xv2 = x.load[width=4](5 * k + t + 8)
                a5 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a5 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a5 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c5 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c5 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c5 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 7:
                var xv0 = x.load[width=4](6 * k + t)
                var xv1 = x.load[width=4](6 * k + t + 4)
                var xv2 = x.load[width=4](6 * k + t + 8)
                a6 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a6 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a6 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c6 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c6 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c6 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            if B >= 8:
                var xv0 = x.load[width=4](7 * k + t)
                var xv1 = x.load[width=4](7 * k + t + 4)
                var xv2 = x.load[width=4](7 * k + t + 8)
                a7 += d0 * xv0[0] + d1 * xv0[1] + d2 * xv0[2] + d3 * xv0[3]
                a7 += d4 * xv1[0] + d5 * xv1[1] + d6 * xv1[2] + d7 * xv1[3]
                a7 += d8 * xv2[0] + d9 * xv2[1] + d10 * xv2[2] + d11 * xv2[3]
                c7 += e0 * xv0[0] + e1 * xv0[1] + e2 * xv0[2] + e3 * xv0[3]
                c7 += e4 * xv1[0] + e5 * xv1[1] + e6 * xv1[2] + e7 * xv1[3]
                c7 += e8 * xv2[0] + e9 * xv2[1] + e10 * xv2[2] + e11 * xv2[3]
            for b in range(8, B):
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
                    if B >= 1:
                        a0 += de * x[t + e]
                        c0 += ee * x[t + e]
                    if B >= 2:
                        a1 += de * x[k + t + e]
                        c1 += ee * x[k + t + e]
                    if B >= 3:
                        a2 += de * x[2 * k + t + e]
                        c2 += ee * x[2 * k + t + e]
                    if B >= 4:
                        a3 += de * x[3 * k + t + e]
                        c3 += ee * x[3 * k + t + e]
                    if B >= 5:
                        a4 += de * x[4 * k + t + e]
                        c4 += ee * x[4 * k + t + e]
                    if B >= 6:
                        a5 += de * x[5 * k + t + e]
                        c5 += ee * x[5 * k + t + e]
                    if B >= 7:
                        a6 += de * x[6 * k + t + e]
                        c6 += ee * x[6 * k + t + e]
                    if B >= 8:
                        a7 += de * x[7 * k + t + e]
                        c7 += ee * x[7 * k + t + e]
                    for b in range(8, B):
                        acc_hi[b - 8] += de * x[b * k + t + e]
                        acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8] += ee * x[b * k + t + e]
        t += _P3B_TG * _P3_CHUNK

    if B >= 1:
        var total = _warp_sum(a0)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 0] = total
        total = _warp_sum(c0)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 0] = total
    if B >= 2:
        var total = _warp_sum(a1)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 1] = total
        total = _warp_sum(c1)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 1] = total
    if B >= 3:
        var total = _warp_sum(a2)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 2] = total
        total = _warp_sum(c2)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 2] = total
    if B >= 4:
        var total = _warp_sum(a3)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 3] = total
        total = _warp_sum(c3)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 3] = total
    if B >= 5:
        var total = _warp_sum(a4)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 4] = total
        total = _warp_sum(c4)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 4] = total
    if B >= 6:
        var total = _warp_sum(a5)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 5] = total
        total = _warp_sum(c5)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 5] = total
    if B >= 7:
        var total = _warp_sum(a6)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 6] = total
        total = _warp_sum(c6)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 6] = total
    if B >= 8:
        var total = _warp_sum(a7)
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + 7] = total
        total = _warp_sum(c7)
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + 7] = total
    for b in range(8, B):
        var total = _warp_sum(acc_hi[b - 8])
        if lane == 0:
            grp[sub * _BATCH_LMHEAD_MAX_ROWS + b] = total
        total = _warp_sum(acc_hi[_BATCH_LMHEAD_MAX_ROWS - 8 + b - 8])
        if lane == 0:
            grp[(_P3B_GROUPS + sub) * _BATCH_LMHEAD_MAX_ROWS + b] = total
    barrier()
    if tid < B:
        var o0 = Float32(0.0)
        var o1 = Float32(0.0)
        for g in range(_P3B_GROUPS):
            o0 += grp[g * _BATCH_LMHEAD_MAX_ROWS + tid]
            o1 += grp[(_P3B_GROUPS + g) * _BATCH_LMHEAD_MAX_ROWS + tid]
        y[tid * n + row0] = y[tid * n + row0] + o0
        y[tid * n + row1] = y[tid * n + row1] + o1
