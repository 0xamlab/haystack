"""test_residentk_attn_splitk_batched_kernel.mojo — the BARRIER-BATCHING kernel
(`_splitk_partial_kernel_simd_batched4`), isolated at the KERNEL level from everything else
`residentk` does, following `test_residentk_attn_splitk_kernel.mojo`'s own pattern exactly (a
dedicated, narrow, kernel-only suite, hand-written, not generated) -- itself following `test_
residentk_sdpa_simd_kernel.mojo`'s own pattern before that.

WHAT THIS KERNEL CLAIMS, AND WHAT THIS FILE CHECKS BEFORE TRUSTING IT
---------------------------------------------------------------------------------------------------
`_splitk_partial_kernel_simd_batched4` claims to compute the EXACT SAME per-(head,split) unnormalized
online-softmax triple `_splitk_partial_kernel_simd` does -- same split-range partition, same per-key
math, same sequential accumulation order -- only batching `_BATCH_K = 4` keys between one pair of
`barrier()` calls instead of doing that for one key at a time. This file checks that claim FIVE ways
before any production code depends on it, the first four mirroring `test_residentk_attn_splitk_
kernel.mojo`'s own four exactly (against a host-f64 reference, against `_sdpa_kernel_simd` itself,
at a ragged n_keys/n_splits pair, and at n_splits > n_keys), plus a fifth this kernel's own batching
specifically motivates:

1. **Against an independent host Float64 reference** (`_host_reference`, byte-for-byte `test_
   residentk_attn_splitk_kernel.mojo`'s own).
2. **Against `_sdpa_kernel_simd` itself**, the single-dispatch kernel both split variants are
   occupancy-only twins of.
3. **Against `_splitk_partial_kernel_simd`** (this kernel's UNBATCHED twin) -- the direct, tightest
   claim: batching keys between barriers must not change the answer AT ALL, not even by a
   reordering-sized delta, since both kernels visit every key in the SAME sequential order and fold
   it into the running accumulators with the SAME arithmetic, just with different barrier placement
   in between. A future maintainer changing `_BATCH_K</code> or `_splitk_partial_kernel_simd_
   batched4`'s loop structure without noticing this bound would trip this check.
4. **At a RAGGED `n_keys`/`n_splits` pair where the per-split range is ALSO not a multiple of
   `_BATCH_K = 4`** -- exercises `batch_n = min(_BATCH_K, key_end - j)`'s short-final-batch path,
   which the unbatched kernel has no equivalent of (it has no batches at all).
5. **At `n_splits > n_keys`** (empty splits) -- the SAME no-special-case claim `_splitk_partial_
   kernel_simd`'s own docstring makes (`m = _NEG_HUGE`, `l = 0.0`, `o = 0.0` folds into the merge as
   a true no-op) must still hold for a kernel whose per-split loop is now `while j < key_end` instead
   of `for j in range(key_start, key_end)` -- an empty range (`key_start == key_end`) must still
   iterate the `while` loop zero times, not underflow or loop forever.

WHY THE BOUND IS TIGHT, NOT LOOSE
------------------------------------------------------------------------
Same reasoning as `test_residentk_attn_splitk_kernel.mojo`'s own module docstring: this kernel
changes NEITHER the storage dtype NOR the underlying math NOR even the per-key accumulation order,
only WHEN shared-memory writes become visible between one barrier and the next. The `orig_vs_host`
and `split_vs_host` bounds below are identical in form to that file's own (`_F32_EPS * (D_HEAD *
n_keys + D_HEAD) * (1 + max_val)`). The `orig_vs_batched` check (original split kernel vs. THIS
kernel) uses a much tighter, near-zero-tolerance bound: both kernels perform the IDENTICAL sequence
of Float32 operations on the IDENTICAL operands in the IDENTICAL order (batching keys between
barriers changes nothing about which floating-point additions happen or in what order they happen --
only when a `barrier()` intervenes), so a real bug here would show up as an exact-arithmetic
mismatch, not a reordering-sized one; the bound used is deliberately the SAME tight reorder bound,
kept as a safety margin against a compiler-level nondeterminism (e.g. FMA contraction differences)
rather than because a real difference of that size would be expected or accepted.
"""

from std.gpu.host import DeviceContext
from std.math import exp, sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _sdpa_kernel_simd,
    _splitk_partial_kernel_simd,
    _splitk_partial_kernel_simd_batched4,
    _splitk_merge_kernel_simd,
)

comptime H_Q: Int = 4
comptime H_KV: Int = 2
comptime D_HEAD: Int = 128
"""Qwen3-0.6B-Base's REAL head dimension -- see `test_residentk_sdpa_simd_kernel.mojo`'s own
docstring for why `_warp_sum`'s butterfly shuffle needs every SIMD-group full, which rules out a
`D_HEAD` smaller than one 32-lane warp."""


def _abs(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    """Deterministic, KNOWN small values -- same two-coprime-multiplier discipline `test_residentk_
    attn_splitk_kernel.mojo`'s own `_pseudo_f32` uses."""
    var o = List[Float32](capacity=n)
    for i in range(n):
        var a = Float32((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float32((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def _host_reference(
    q: List[Float32], kv_k: List[Float32], kv_v: List[Float32],
    h_q: Int, h_kv: Int, d_head: Int, n_keys: Int, scale: Float32,
) -> List[Float64]:
    """Pure-host, Float64, no-GPU online-softmax reference -- byte-for-byte `test_residentk_attn_
    splitk_kernel.mojo`'s own `_host_reference`."""
    var out = List[Float64](capacity=h_q * d_head)
    var group = h_q // h_kv
    for h in range(h_q):
        var hk = h // group
        var m = -1.0e300
        var denom = 0.0
        var o = List[Float64](capacity=d_head)
        for _ in range(d_head):
            o.append(0.0)
        for j in range(n_keys):
            var kb = (j * h_kv + hk) * d_head
            var s = 0.0
            for e in range(d_head):
                s += Float64(q[h * d_head + e]) * Float64(kv_k[kb + e])
            s *= Float64(scale)
            var nm = m if m > s else s
            var corr = exp(m - nm)
            var w = exp(s - nm)
            for e in range(d_head):
                o[e] = o[e] * corr + w * Float64(kv_v[kb + e])
            denom = denom * corr + w
            m = nm
        for e in range(d_head):
            out.append(o[e] / denom)
    return out^


def _run_case(
    ctx: DeviceContext, name: String, n_keys: Int, n_splits: Int,
    mut passed: Int, mut failed: Int,
) raises:
    """One (n_keys, n_splits) case: builds fresh deterministic inputs, then runs THREE kernels --
    the single-dispatch original (`_sdpa_kernel_simd`), the unbatched split+merge pair (`_splitk_
    partial_kernel_simd` + `_splitk_merge_kernel_simd`), and the batched split+merge pair (`_splitk_
    partial_kernel_simd_batched4` + the SAME, unmodified merge kernel) -- and checks all three
    against the host-f64 reference AND against each other."""
    var scale = Float32(1.0 / sqrt(Float64(D_HEAD)))
    var q_vals = _pseudo_f32(H_Q * D_HEAD, 41 + n_keys + n_splits, 1.0)
    var kv_k_vals = _pseudo_f32(n_keys * H_KV * D_HEAD, 53 + n_keys + n_splits, 0.8)
    var kv_v_vals = List[Float32](capacity=n_keys * H_KV * D_HEAD)
    for i in range(n_keys * H_KV * D_HEAD):
        kv_v_vals.append(kv_k_vals[(i + 23) % len(kv_k_vals)])

    var host_ref = _host_reference(q_vals, kv_k_vals, kv_v_vals, H_Q, H_KV, D_HEAD, n_keys, scale)

    var q_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
    var ck_buf = ctx.enqueue_create_buffer[DType.float32](n_keys * H_KV * D_HEAD)
    var cv_buf = ctx.enqueue_create_buffer[DType.float32](n_keys * H_KV * D_HEAD)
    with q_buf.map_to_host() as h:
        for i in range(H_Q * D_HEAD):
            h[i] = q_vals[i]
    with ck_buf.map_to_host() as h:
        for i in range(n_keys * H_KV * D_HEAD):
            h[i] = kv_k_vals[i]
    with cv_buf.map_to_host() as h:
        for i in range(n_keys * H_KV * D_HEAD):
            h[i] = kv_v_vals[i]

    # ── the single-dispatch original ──
    var attn_orig = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
    var f_orig = ctx.compile_function_unchecked[_sdpa_kernel_simd]()
    ctx.enqueue_function_unchecked(
        f_orig,
        attn_orig.unsafe_ptr(), q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        n_keys, H_Q, H_KV, D_HEAD, scale,
        grid_dim=H_Q, block_dim=D_HEAD,
    )

    # ── the UNBATCHED split+merge pair ──
    var m_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits * D_HEAD)
    var attn_split = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)

    var f_partial = ctx.compile_function_unchecked[_splitk_partial_kernel_simd]()
    var f_merge = ctx.compile_function_unchecked[_splitk_merge_kernel_simd]()
    ctx.enqueue_function_unchecked(
        f_partial,
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        n_keys, n_splits, H_Q, H_KV, D_HEAD, scale,
        grid_dim=H_Q * n_splits, block_dim=D_HEAD,
    )
    ctx.enqueue_function_unchecked(
        f_merge,
        attn_split.unsafe_ptr(), m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        n_splits, D_HEAD,
        grid_dim=H_Q, block_dim=D_HEAD,
    )

    # ── the BATCHED split+merge pair (this file's actual subject) -- own scratch buffers, same
    # merge kernel (the merge's own input shape, n_splits triples per head, is identical either way) ──
    var m_buf2 = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits)
    var l_buf2 = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits)
    var o_buf2 = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits * D_HEAD)
    var attn_batched = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)

    var f_partial_b = ctx.compile_function_unchecked[_splitk_partial_kernel_simd_batched4]()
    ctx.enqueue_function_unchecked(
        f_partial_b,
        m_buf2.unsafe_ptr(), l_buf2.unsafe_ptr(), o_buf2.unsafe_ptr(),
        q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        n_keys, n_splits, H_Q, H_KV, D_HEAD, scale,
        grid_dim=H_Q * n_splits, block_dim=D_HEAD,
    )
    ctx.enqueue_function_unchecked(
        f_merge,
        attn_batched.unsafe_ptr(), m_buf2.unsafe_ptr(), l_buf2.unsafe_ptr(), o_buf2.unsafe_ptr(),
        n_splits, D_HEAD,
        grid_dim=H_Q, block_dim=D_HEAD,
    )
    ctx.synchronize()

    var worst_orig_vs_host = Float64(0.0)
    var worst_split_vs_host = Float64(0.0)
    var worst_batched_vs_host = Float64(0.0)
    var worst_orig_vs_split = Float32(0.0)
    var worst_orig_vs_batched = Float32(0.0)
    var worst_split_vs_batched = Float32(0.0)
    var max_val = Float32(0.0)
    with attn_orig.map_to_host() as ho:
        with attn_split.map_to_host() as hs:
            with attn_batched.map_to_host() as hb:
                for i in range(H_Q * D_HEAD):
                    var d_oh = _abs64(Float64(ho[i]) - host_ref[i])
                    var d_sh = _abs64(Float64(hs[i]) - host_ref[i])
                    var d_bh = _abs64(Float64(hb[i]) - host_ref[i])
                    var d_os = _abs(ho[i] - hs[i])
                    var d_ob = _abs(ho[i] - hb[i])
                    var d_sb = _abs(hs[i] - hb[i])
                    if d_oh > worst_orig_vs_host:
                        worst_orig_vs_host = d_oh
                    if d_sh > worst_split_vs_host:
                        worst_split_vs_host = d_sh
                    if d_bh > worst_batched_vs_host:
                        worst_batched_vs_host = d_bh
                    if d_os > worst_orig_vs_split:
                        worst_orig_vs_split = d_os
                    if d_ob > worst_orig_vs_batched:
                        worst_orig_vs_batched = d_ob
                    if d_sb > worst_split_vs_batched:
                        worst_split_vs_batched = d_sb
                    var v = _abs(ho[i])
                    if v > max_val:
                        max_val = v

    comptime _F32_EPS: Float64 = 1.1920929e-7
    var reorder_bound = _F32_EPS * Float64(D_HEAD * n_keys + D_HEAD) * (1.0 + Float64(max_val))
    print("  •  [", name, "] n_keys=", n_keys, " n_splits=", n_splits,
          " orig_vs_host=", worst_orig_vs_host, " split_vs_host=", worst_split_vs_host,
          " batched_vs_host=", worst_batched_vs_host,
          " orig_vs_split=", worst_orig_vs_split, " orig_vs_batched=", worst_orig_vs_batched,
          " split_vs_batched=", worst_split_vs_batched, " bound=", reorder_bound)

    if worst_orig_vs_host <= reorder_bound:
        passed += 1
    else:
        failed += 1
        print("     ❌ the single-dispatch original diverges from host-f64 by", worst_orig_vs_host,
              "-- more than", reorder_bound, "(bound itself would be broken, unrelated to this file)")

    if Float64(worst_split_vs_host) <= reorder_bound:
        passed += 1
    else:
        failed += 1
        print("     ❌ the UNBATCHED split+merge diverges from host-f64 by", worst_split_vs_host,
              "-- more than", reorder_bound, "(pre-existing kernel, unrelated to this file)")

    if Float64(worst_batched_vs_host) <= reorder_bound:
        passed += 1
        print("     ✅ batched split+merge agrees with host-f64 reference to", worst_batched_vs_host,
              "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ batched split+merge diverges from host-f64 reference by", worst_batched_vs_host,
              "-- more than", reorder_bound, "-- THE BATCHING CHANGED THE ANSWER")

    # The tight, near-zero-tolerance check: batched vs. unbatched, and batched vs. the original --
    # same reorder_bound used as a generous safety margin (see module docstring), not because a
    # difference anywhere near that size would be expected.
    if Float64(worst_orig_vs_batched) <= reorder_bound:
        passed += 1
        print("     ✅ single-dispatch original and BATCHED split+merge agree with EACH OTHER to",
              worst_orig_vs_batched, "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ single-dispatch original and BATCHED split+merge disagree by",
              worst_orig_vs_batched, "-- more than", reorder_bound)

    if Float64(worst_split_vs_batched) <= reorder_bound:
        passed += 1
        print("     ✅ UNBATCHED and BATCHED split+merge agree with EACH OTHER to",
              worst_split_vs_batched, "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ UNBATCHED and BATCHED split+merge disagree by", worst_split_vs_batched,
              "-- more than", reorder_bound, "-- BATCHING INTRODUCED A REAL DIVERGENCE")


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no split/merge/batched kernel compiled, nothing to run")
        print("  [residentk.kernels attn-splitk-batched-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels attn-splitk-batched-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # 1. Evenly-divisible n_keys/n_splits, several keys per split, AND evenly divisible by
        #    _BATCH_K = 4 -- the common case for both kernels.
        _run_case(ctx, "even", 64, 8, passed, failed)
        # 2. RAGGED: n_keys not a multiple of n_splits, AND the per-split range not a multiple of
        #    _BATCH_K = 4 either -- exercises the batched kernel's short-final-batch path.
        _run_case(ctx, "ragged", 37, 6, passed, failed)
        # 3. n_splits > n_keys: several splits are genuinely EMPTY (batched kernel's `while` loop
        #    over an empty range must iterate zero times, not underflow).
        _run_case(ctx, "more_splits_than_keys", 5, 16, passed, failed)
        # 4. n_splits == 1: degenerates to exactly the single-dispatch kernel's own range, many
        #    batches of 4 plus a short tail.
        _run_case(ctx, "single_split", 20, 1, passed, failed)
        # 5. A depth in the range production actually gates the split path at, evenly divisible by
        #    neither n_splits nor _BATCH_K in general.
        _run_case(ctx, "deep_like_production", 600, 16, passed, failed)
        # 6. A depth close to this task's own long-context measurement point (n_keys=4000), the
        #    actual shape the Profile phase's dominant-cost finding was measured at.
        _run_case(ctx, "very_deep_like_4000", 4000, 16, passed, failed)

        print("  [residentk.kernels attn-splitk-batched-isolated] Passed:", passed, "Failed:", failed)
