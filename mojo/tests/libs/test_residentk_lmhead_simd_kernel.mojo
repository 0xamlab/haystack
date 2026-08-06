"""test_residentk_lmhead_simd_kernel.mojo — the LMHEAD-reduction-mechanism kernel pair
(`_lmhead_argmax_kernel_i8`/`_lmhead_argmax_kernel_simd_i8`), isolated at the KERNEL level from
everything else `residentk` does, following `test_residentk_gemv_simd_kernel.mojo`'s own pattern
exactly (a dedicated, narrow, kernel-only suite, not folded into `test_residentk_session.mojo`'s big
shared model fixture).

WHY A SEPARATE FIXTURE, AND WHY IT IS NOT JUST `test_residentk_gemv_simd_kernel.mojo` AGAIN
-------------------------------------------------------------------------------------------------
`_lmhead_argmax_kernel_i8` shares its STAGE-1 (sum-of-squares) and STAGE-3-inner (per-column dot
product) shapes with `_norm_gemv_kernel_i8`, already covered by that file -- but it is NOT a bare
reduction-order twin of a plain GEMV kernel. Two things are genuinely different and this file exists
to check them:

1. It walks the WHOLE `n`-row vocabulary in a `for it in range(n_iters):` grid-stride loop, re-using
   the SAME per-thread `best`/`best_i` registers (and, in the barrier-tree original, the SAME shared
   `red[]` array) across MULTIPLE iterations -- a plain GEMV kernel launches once per output column
   and never loops. This file picks `grid_dim`/`n`/`_SUBS` so `n_iters > 1`, with the LAST iteration
   only partially populated for at least one threadgroup, to exercise exactly that multi-iteration
   reuse (both the barrier-tree version's `red[]`-reuse-across-iterations safety barrier, and the
   SIMD-shuffle version's claim that removing it changes nothing, since it never writes `red[]` at
   all).
2. It reduces to an ARGMAX (a `(value, id)` pair with a strict-`>`, lowest-id-wins tie-break), not a
   plain sum -- `warp.sum` only replaces the VALUE reduction; the argmax bookkeeping itself is
   unchanged register logic in both kernels, and this file checks the tie-break-relevant SCAN ORDER
   (`sub` outer, `it` inner per sub, then the final per-threadgroup combine over `sub` in ascending
   order) produces the IDENTICAL winning index in the host reference, the barrier-tree kernel, and
   the SIMD-shuffle kernel, all three, at every threadgroup.

Checked against an INDEPENDENT host Float64 reference AND against each other
------------------------------------------------------------------------------
Same `x`/`gamma`/`w`/`wscale` inputs, same `grid_dim`/`n_iters`, both kernels' per-threadgroup
`(blk_val[b], blk_idx[b])` outputs compared to a pure-host Float64 reference that recomputes the
EXACT same block-strided scan (not merely a global argmax over all `n` columns -- the per-BLOCK
winner is what this kernel actually produces, one block's own `_SUBS`-column stride at a time).
Value deltas bounded the same tight `reorder_bound`
`test_residentk_gemv_simd_kernel.mojo`'s own docstring derives and justifies (Float32
unit-roundoff accumulated over `K` additions, not this package's looser `1/127` int8-quantization
bound); argmax INDICES are compared for EXACT equality (ties are as good as impossible with these
pseudo-random inputs, so "exact" is the real, discriminating check, not a rubber stamp).
"""

from std.gpu.host import DeviceContext
from std.math import sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _lmhead_argmax_kernel_i8,
    _lmhead_argmax_kernel_simd_i8,
    _TG,
    _SUBS,
)

comptime K: Int = 137
"""Deliberately not a multiple of `_LANES=32`, `_VEC_I8=4`, or `_TG=256` -- exercises the
vectorized-main-loop-plus-scalar-tail path both kernels share, same choice
`test_residentk_gemv_simd_kernel.mojo` makes for the same reason."""

comptime N: Int = 67
"""Deliberately not a multiple of `_SUBS=8`, and small enough that `GRID_DIM * _SUBS * N_ITERS`
overshoots it (the LAST `it` iteration is partially populated for the threadgroups holding the
tail columns), exercising the `j < n` guard exactly the way a real, non-power-of-everything
vocabulary size would."""

comptime GRID_DIM: Int = 3
"""Threadgroups. `GRID_DIM * _SUBS = 24` columns per full `it` iteration; with `N = 67` that forces
`N_ITERS = 3` (`ceil(67 / 24)`), so every threadgroup's own per-thread `best`/`best_i` registers get
exercised across THREE iterations, not one -- the genuinely new thing this file checks that
`test_residentk_gemv_simd_kernel.mojo` has no occasion to."""

comptime N_ITERS: Int = 3

comptime EPS: Float32 = 1.0e-6


def _abs(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f64(n: Int, seed: Int, amp: Float64) -> List[Float64]:
    """Deterministic, KNOWN small values -- same two-coprime-multiplier discipline
    `test_residentk_gemv_simd_kernel.mojo`'s own `_pseudo_f64` uses."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var a = Float64((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float64((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def _quantize_row_i8_host(row: List[Float64], mut out_row: List[Int8]) -> Float64:
    """Pure-host per-row int8 quantization -- the SAME `scale = max(|row|) / 127` convention
    `test_residentk_gemv_simd_kernel.mojo`'s own helper uses, duplicated here (not imported: this
    package has no shared test-helper module) so this file's host reference stays independent of
    the upload path the kernels under test read their `wscale` from."""
    var maxabs = 0.0
    for v in row:
        var a = _abs64(v)
        if a > maxabs:
            maxabs = a
    var scale = maxabs / 127.0 if maxabs > 0.0 else 1.0
    for v in row:
        var q = Int(v / scale)
        if q > 127:
            q = 127
        if q < -127:
            q = -127
        out_row.append(Int8(q))
    return scale


def _host_rmsnorm(x: List[Float64], gamma: List[Float64], k: Int, eps: Float64) -> List[Float64]:
    """Pure-host Float64 reference for the kernel's own stage 1+2: rmsnorm(x) * gamma. Both
    `_lmhead_argmax_kernel_i8` and `_lmhead_argmax_kernel_simd_i8` claim to compute the IDENTICAL
    normalized vector before either kernel's stage-3 argmax scan ever runs -- checking it here,
    once, independent of either kernel's OWN reduction mechanism."""
    var ss = 0.0
    for i in range(k):
        ss += x[i] * x[i]
    var inv = 1.0 / sqrt(ss / Float64(k) + eps)
    var out = List[Float64](capacity=k)
    for i in range(k):
        out.append(x[i] * inv * gamma[i])
    return out^


def _host_lmhead_block_argmax(
    xn: List[Float64], w_rows: List[List[Int8]], wscale: List[Float64],
    k: Int, n: Int, grid_dim: Int, n_iters: Int,
    mut out_val: List[Float64], mut out_idx: List[Int],
):
    """Pure-host Float64 reference for the kernel's own stage 3: the block-strided per-column
    int8-dequantized dot product PLUS its running argmax. SAME scan order as both device kernels --
    each `sub` (one of `_SUBS` independent SIMD-groups per threadgroup) finds its OWN best across
    all `it` iterations first (matching each thread's own register-local scan, strict `>` so an
    exact tie keeps the EARLIER `it`), then the per-threadgroup combine walks `sub` in ASCENDING
    order with another strict `>` (so an exact tie keeps the LOWER `sub`) -- exactly
    `_lmhead_argmax_kernel_i8`'s own `if lane == 0: sv[sub] = best` / `for u in range(1, _SUBS):`
    combine, reproduced here rather than simplified to a global argmax, because a simplification
    could silently pick a DIFFERENT (equally-valid-looking but wrong-per-this-kernel) winner on
    a tie."""
    var stride_cols = grid_dim * _SUBS
    for b in range(grid_dim):
        var best = -1.0e30
        var best_i = -1
        for sub in range(_SUBS):
            var sub_best = -1.0e30
            var sub_best_i = -1
            for it in range(n_iters):
                var j = b * _SUBS + sub + it * stride_cols
                if j < n:
                    var s = 0.0
                    var base = j * k
                    for i in range(k):
                        s += xn[i] * (Float64(w_rows[j][i]) * wscale[j])
                    if s > sub_best:
                        sub_best = s
                        sub_best_i = j
            if sub_best_i >= 0 and sub_best > best:
                best = sub_best
                best_i = sub_best_i
        out_val.append(best)
        out_idx.append(best_i)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no lm_head-simd kernels compiled, nothing to run")
        print("  [residentk.kernels lmhead-simd-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels lmhead-simd-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # Float32 unit-roundoff (~2^-23) accumulated over `K` additions -- generous, but the scale
        # a REORDERED-SUMMATION delta belongs at, not this package's `1/127` int8-quantization
        # bound (checked below to be far looser than this one), same derivation
        # `test_residentk_gemv_simd_kernel.mojo` uses.
        comptime _F32_EPS: Float64 = 1.1920929e-7
        var reorder_bound = _F32_EPS * Float64(K) * 50.0
        var quant_bound = 1.0 / 127.0
        if reorder_bound >= quant_bound:
            print("  ❌ TEST BUG: reorder_bound is not tighter than the quantization-arm bound")
            failed += 1

        # ══ shared inputs ══════════════════════════════════════════════════════════════════════
        var x64 = _pseudo_f64(K, 3, 1.0)
        var gamma64 = List[Float64](capacity=K)
        for i in range(K):
            gamma64.append(1.0 + 0.1 * Float64((i * 7) % 5))

        var w_rows = List[List[Int8]](capacity=N)
        var wscale = List[Float64](capacity=N)
        var w_flat = List[Int8](capacity=N * K)
        for j in range(N):
            var row64 = _pseudo_f64(K, 100 + j * 11, 0.8)
            var q_row = List[Int8](capacity=K)
            var s = _quantize_row_i8_host(row64, q_row)
            wscale.append(s)
            for i in range(K):
                w_flat.append(q_row[i])
            w_rows.append(q_row^)

        var x_buf = ctx.enqueue_create_buffer[DType.float32](K)
        var gamma_buf = ctx.enqueue_create_buffer[DType.float32](K)
        var w_buf = ctx.enqueue_create_buffer[DType.int8](N * K)
        var wscale_buf = ctx.enqueue_create_buffer[DType.float32](N)
        with x_buf.map_to_host() as h:
            for i in range(K):
                h[i] = Float32(x64[i])
        with gamma_buf.map_to_host() as h:
            for i in range(K):
                h[i] = Float32(gamma64[i])
        with w_buf.map_to_host() as h:
            for idx in range(N * K):
                h[idx] = w_flat[idx]
        with wscale_buf.map_to_host() as h:
            for j in range(N):
                h[j] = Float32(wscale[j])
        ctx.synchronize()

        # ══ host reference: rmsnorm+gamma once, then the block-strided argmax scan ═════════════
        var xn64 = _host_rmsnorm(x64, gamma64, K, Float64(EPS))
        var host_val = List[Float64]()
        var host_idx = List[Int]()
        _host_lmhead_block_argmax(xn64, w_rows, wscale, K, N, GRID_DIM, N_ITERS, host_val, host_idx)

        # ══ device: _lmhead_argmax_kernel_i8 (barrier-tree) vs _lmhead_argmax_kernel_simd_i8 ═════
        var blk_val_tree = ctx.enqueue_create_buffer[DType.float32](GRID_DIM)
        var blk_idx_tree = ctx.enqueue_create_buffer[DType.int32](GRID_DIM)
        var blk_val_simd = ctx.enqueue_create_buffer[DType.float32](GRID_DIM)
        var blk_idx_simd = ctx.enqueue_create_buffer[DType.int32](GRID_DIM)
        var f_tree = ctx.compile_function_unchecked[_lmhead_argmax_kernel_i8]()
        var f_simd = ctx.compile_function_unchecked[_lmhead_argmax_kernel_simd_i8]()

        ctx.enqueue_function_unchecked(
            f_tree,
            blk_val_tree.unsafe_ptr(), blk_idx_tree.unsafe_ptr(),
            x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(), w_buf.unsafe_ptr(), wscale_buf.unsafe_ptr(),
            K, N, EPS, N_ITERS,
            grid_dim=GRID_DIM, block_dim=_TG,
        )
        ctx.enqueue_function_unchecked(
            f_simd,
            blk_val_simd.unsafe_ptr(), blk_idx_simd.unsafe_ptr(),
            x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(), w_buf.unsafe_ptr(), wscale_buf.unsafe_ptr(),
            K, N, EPS, N_ITERS,
            grid_dim=GRID_DIM, block_dim=_TG,
        )
        ctx.synchronize()

        var worst_tree_host = 0.0
        var worst_simd_host = 0.0
        var worst_cross = Float32(0.0)
        var idx_ok = True
        with blk_val_tree.map_to_host() as htv:
            with blk_idx_tree.map_to_host() as hti:
                with blk_val_simd.map_to_host() as hsv:
                    with blk_idx_simd.map_to_host() as hsi:
                        for b in range(GRID_DIM):
                            var dt = _abs64(Float64(htv[b]) - host_val[b])
                            var ds = _abs64(Float64(hsv[b]) - host_val[b])
                            var dc = _abs(htv[b] - hsv[b])
                            if dt > worst_tree_host:
                                worst_tree_host = dt
                            if ds > worst_simd_host:
                                worst_simd_host = ds
                            if dc > worst_cross:
                                worst_cross = dc
                            if Int(hti[b]) != host_idx[b] or Int(hsi[b]) != host_idx[b]:
                                idx_ok = False
                                print("  •  block", b, "argmax index mismatch: host=", host_idx[b],
                                      "tree=", Int(hti[b]), "simd=", Int(hsi[b]))

        print("  •  [lm_head value] tree vs host: worst|Δ|=", worst_tree_host,
              " simd vs host: worst|Δ|=", worst_simd_host, " tree vs simd: worst|Δ|=", worst_cross)
        print("  •  [lm_head argmax index] tree and simd both exactly match host at every block:",
              "OK" if idx_ok else "MISMATCH")
        if (
            worst_tree_host <= reorder_bound and worst_simd_host <= reorder_bound
            and Float64(worst_cross) <= reorder_bound and idx_ok
        ):
            passed += 1
            print("  ✅ lm_head argmax: barrier-tree and SIMD-shuffle agree with the host reference",
                  "and each other within", reorder_bound, "on VALUE, and EXACTLY on the winning",
                  "index, across", N_ITERS, "multi-iteration register-reuse passes")
        else:
            failed += 1
            print("  ❌ lm_head argmax: a value delta exceeds", reorder_bound,
                  "or an argmax index disagreed -- see the numbers above")

        print("  [residentk.kernels lmhead-simd-isolated] Passed:", passed, "Failed:", failed)
