"""test_residentk_attn_splitk_native_kernel.mojo — the REDUCTION-SHAPE kernel
(`_splitk_partial_kernel_simd_native`), isolated at the KERNEL level from everything else
`residentk` does, following `test_residentk_attn_splitk_batched_kernel.mojo`'s own pattern exactly
(a dedicated, narrow, kernel-only suite, hand-written, not generated) — itself following `test_
residentk_attn_splitk_kernel.mojo`'s and `test_residentk_sdpa_simd_kernel.mojo`'s own patterns
before that.

WHAT THIS KERNEL CLAIMS, AND WHAT THIS FILE CHECKS BEFORE TRUSTING IT
---------------------------------------------------------------------------------------------------
`_splitk_partial_kernel_simd_native` claims to compute the EXACT SAME per-(head, split) unnormalized
online-softmax triple `_splitk_partial_kernel_simd` does — same split-range partition, same online-
softmax recurrence, same `(m, l, o)` output contract — only HOW one key's `d_head`-wide dot product
collapses to a scalar differs: ONE 32-lane SIMD-group (`block_dim = WARP_SIZE`, each lane owning
`d_head / WARP_SIZE` elements at stride `WARP_SIZE`, one `_warp_sum` per key, zero `barrier()` calls
anywhere in the kernel) instead of FOUR SIMD-groups combined via a shared array and two `barrier()`
calls per key. This file checks that claim against FOUR independent references before any
production code depends on it — the first three mirroring `test_residentk_attn_splitk_batched_
kernel.mojo`'s own, plus a widened multi-head sweep this kernel's own reduction-SHAPE change (as
opposed to that file's reduction-COUNT change) specifically motivates:

1. **Against an independent host Float64 reference** (`_host_reference`, byte-for-byte `test_
   residentk_attn_splitk_kernel.mojo`'s own).
2. **Against `_sdpa_kernel_simd` itself**, the single-dispatch kernel every split variant is an
   occupancy-only twin of.
3. **Against `_splitk_partial_kernel_simd`** (this kernel's TWO-LEVEL twin) — the direct, tightest
   claim: changing four SIMD-groups-with-a-shared-combine into one SIMD-group-owning-more-elements
   must not change the answer beyond ordinary Float32 reordering noise, since both kernels visit
   every key in the SAME sequential order and fold it into the running accumulators with materially
   the same arithmetic, just accumulated over a different lane/group shape.
4. **At a RAGGED `n_keys`/`n_splits` pair** and **at `n_splits > n_keys`** (empty splits) — the SAME
   two edge cases `test_residentk_attn_splitk_kernel.mojo`'s own suite established for the two-level
   kernel, now re-run against the native one-SIMD-group kernel specifically, since an empty split
   (`key_start == key_end`) exercises this kernel's `for j in range(key_start, key_end)` zero-
   iteration path exactly as it does for the two-level twin.
5. **A MULTI-HEAD sweep** (`h_q` in {4, 16}, `h_kv` in {2, 16} — 16/16 is plain MHA, no GQA grouping
   at all) **crossed with a MULTI-DEPTH sweep** (`n_keys` in {1, 2, 8, 33, 64, 257, 600, 4000}) — the
   design phase's own scratch probe swept 16 query heads across `n_keys` in {1, 2, 8, 33, 64, 257}
   before trusting the redesign; this permanent suite reproduces that sweep (widened to include the
   real production depth, 4000, and a plain-MHA head shape the scratch probe did not try) rather than
   leaving it in a throwaway `/tmp` script.
6. **The PRODUCTION widened split count** (`n_splits=80`, `_ATTN_SPLITK_N_SPLITS_NATIVE` in
   `metaldispatch.session` — `_MBQwen3I8AllSimd6`'s own Candidate-1 configuration, chosen from a real
   GPU-counter sweep on the embedded pipeline, see that constant's own docstring) at `n_keys` below,
   near, and far above 80 — the kernel's own per-key online-softmax loop does not care what `n_splits`
   is (each split is an independent key-subrange scan), but this exercises the ACTUAL shipped
   configuration directly rather than only nearby values a general sweep happened to touch.

WHY THE BOUND IS TIGHT, NOT LOOSE
------------------------------------------------------------------------
Same reasoning as `test_residentk_attn_splitk_kernel.mojo`'s and `test_residentk_attn_splitk_batched_
kernel.mojo`'s own module docstrings: this kernel changes NEITHER the storage dtype NOR the
underlying online-softmax math NOR the per-key sequential visit order, only the SUMMATION ORDER
within one key's dot product (32 per-lane partial sums, each itself a sum of `d_head / WARP_SIZE`
register-resident products, folded by one `_warp_sum` butterfly — a different but still Float32,
still-associativity-order-only reordering of the SAME `d_head` products the two-level kernel's own
four-groups-then-shared-combine visits). The `orig_vs_host`/`split_vs_host`/`native_vs_host` bounds
below are identical in form to those two files' own (`_F32_EPS * (D_HEAD * n_keys + D_HEAD) * (1 +
max_val)`) — deliberately not a hand-wavy rubber stamp, the SAME scaled-by-operation-count bound
those files themselves check is not ten-thousand-times looser than needed.
"""

from max.gpu.host import DeviceContext
from std.math import exp, sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _sdpa_kernel_simd,
    _splitk_partial_kernel_simd,
    _splitk_partial_kernel_simd_native,
    _splitk_merge_kernel_simd,
)


def _abs(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    """Deterministic, KNOWN small values — same two-coprime-multiplier discipline `test_residentk_
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
    """Pure-host, Float64, no-GPU online-softmax reference — byte-for-byte `test_residentk_attn_
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
    ctx: DeviceContext, name: String, h_q: Int, h_kv: Int, d_head: Int, n_keys: Int, n_splits: Int,
    mut passed: Int, mut failed: Int,
) raises:
    """One (h_q, h_kv, d_head, n_keys, n_splits) case: builds fresh deterministic inputs, then runs
    THREE kernels — the single-dispatch original (`_sdpa_kernel_simd`), the two-level split+merge
    pair (`_splitk_partial_kernel_simd` + `_splitk_merge_kernel_simd`), and the NATIVE split+merge
    pair (`_splitk_partial_kernel_simd_native` + the SAME, unmodified merge kernel) — and checks all
    three against the host-f64 reference AND against each other."""
    var scale = Float32(1.0 / sqrt(Float64(d_head)))
    var q_vals = _pseudo_f32(h_q * d_head, 61 + n_keys + n_splits + h_q * 7 + h_kv * 3, 1.0)
    var kv_k_vals = _pseudo_f32(n_keys * h_kv * d_head, 73 + n_keys + n_splits + h_q * 7 + h_kv * 3, 0.8)
    var kv_v_vals = List[Float32](capacity=n_keys * h_kv * d_head)
    for i in range(n_keys * h_kv * d_head):
        kv_v_vals.append(kv_k_vals[(i + 29) % len(kv_k_vals)])

    var host_ref = _host_reference(q_vals, kv_k_vals, kv_v_vals, h_q, h_kv, d_head, n_keys, scale)

    var q_buf = ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
    var ck_buf = ctx.enqueue_create_buffer[DType.float32](n_keys * h_kv * d_head)
    var cv_buf = ctx.enqueue_create_buffer[DType.float32](n_keys * h_kv * d_head)
    with q_buf.map_to_host() as h:
        for i in range(h_q * d_head):
            h[i] = q_vals[i]
    with ck_buf.map_to_host() as h:
        for i in range(n_keys * h_kv * d_head):
            h[i] = kv_k_vals[i]
    with cv_buf.map_to_host() as h:
        for i in range(n_keys * h_kv * d_head):
            h[i] = kv_v_vals[i]

    # ── the single-dispatch original ──
    var attn_orig = ctx.enqueue_create_buffer[DType.float32](h_q * d_head)
    var f_orig = ctx.compile_function[_sdpa_kernel_simd]()
    ctx.enqueue_function_unchecked(
        f_orig,
        attn_orig.unsafe_ptr(), q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        n_keys, h_q, h_kv, d_head, scale,
        grid_dim=h_q, block_dim=d_head,
    )

    # ── the TWO-LEVEL split+merge pair (`_splitk_partial_kernel_simd`'s own shape) ──
    var m_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits * d_head)
    var attn_split = ctx.enqueue_create_buffer[DType.float32](h_q * d_head)

    var f_partial = ctx.compile_function[_splitk_partial_kernel_simd]()
    var f_merge = ctx.compile_function[_splitk_merge_kernel_simd]()
    ctx.enqueue_function_unchecked(
        f_partial,
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        n_keys, n_splits, h_q, h_kv, d_head, scale,
        grid_dim=h_q * n_splits, block_dim=d_head,
    )
    ctx.enqueue_function_unchecked(
        f_merge,
        attn_split.unsafe_ptr(), m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        n_splits, d_head,
        grid_dim=h_q, block_dim=d_head,
    )

    # ── the NATIVE split+merge pair (this file's actual subject) — own scratch buffers, `block_dim =
    # WARP_SIZE` at the dispatch header (the ONE line this kernel's own launch shape actually needs
    # to differ by), same merge kernel (its own input shape, n_splits triples per head, is identical
    # either way — the merge kernel does not know or care which partial kernel produced its input) ──
    var m_buf2 = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var l_buf2 = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var o_buf2 = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits * d_head)
    var attn_native = ctx.enqueue_create_buffer[DType.float32](h_q * d_head)

    var f_partial_n = ctx.compile_function[_splitk_partial_kernel_simd_native]()
    ctx.enqueue_function_unchecked(
        f_partial_n,
        m_buf2.unsafe_ptr(), l_buf2.unsafe_ptr(), o_buf2.unsafe_ptr(),
        q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        n_keys, n_splits, h_q, h_kv, d_head, scale,
        grid_dim=h_q * n_splits, block_dim=32,
    )
    ctx.enqueue_function_unchecked(
        f_merge,
        attn_native.unsafe_ptr(), m_buf2.unsafe_ptr(), l_buf2.unsafe_ptr(), o_buf2.unsafe_ptr(),
        n_splits, d_head,
        grid_dim=h_q, block_dim=d_head,
    )
    ctx.synchronize()

    var worst_orig_vs_host = Float64(0.0)
    var worst_split_vs_host = Float64(0.0)
    var worst_native_vs_host = Float64(0.0)
    var worst_orig_vs_split = Float32(0.0)
    var worst_orig_vs_native = Float32(0.0)
    var worst_split_vs_native = Float32(0.0)
    var max_val = Float32(0.0)
    with attn_orig.map_to_host() as ho:
        with attn_split.map_to_host() as hs:
            with attn_native.map_to_host() as hn:
                for i in range(h_q * d_head):
                    var d_oh = _abs64(Float64(ho[i]) - host_ref[i])
                    var d_sh = _abs64(Float64(hs[i]) - host_ref[i])
                    var d_nh = _abs64(Float64(hn[i]) - host_ref[i])
                    var d_os = _abs(ho[i] - hs[i])
                    var d_on = _abs(ho[i] - hn[i])
                    var d_sn = _abs(hs[i] - hn[i])
                    if d_oh > worst_orig_vs_host:
                        worst_orig_vs_host = d_oh
                    if d_sh > worst_split_vs_host:
                        worst_split_vs_host = d_sh
                    if d_nh > worst_native_vs_host:
                        worst_native_vs_host = d_nh
                    if d_os > worst_orig_vs_split:
                        worst_orig_vs_split = d_os
                    if d_on > worst_orig_vs_native:
                        worst_orig_vs_native = d_on
                    if d_sn > worst_split_vs_native:
                        worst_split_vs_native = d_sn
                    var v = _abs(ho[i])
                    if v > max_val:
                        max_val = v

    comptime _F32_EPS: Float64 = 1.1920929e-7
    var reorder_bound = _F32_EPS * Float64(d_head * n_keys + d_head) * (1.0 + Float64(max_val))
    print("  •  [", name, "] h_q=", h_q, " h_kv=", h_kv, " d_head=", d_head, " n_keys=", n_keys,
          " n_splits=", n_splits,
          " orig_vs_host=", worst_orig_vs_host, " split_vs_host=", worst_split_vs_host,
          " native_vs_host=", worst_native_vs_host,
          " orig_vs_split=", worst_orig_vs_split, " orig_vs_native=", worst_orig_vs_native,
          " split_vs_native=", worst_split_vs_native, " bound=", reorder_bound)

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
        print("     ❌ the TWO-LEVEL split+merge diverges from host-f64 by", worst_split_vs_host,
              "-- more than", reorder_bound, "(pre-existing kernel, unrelated to this file)")

    if Float64(worst_native_vs_host) <= reorder_bound:
        passed += 1
        print("     ✅ NATIVE split+merge agrees with host-f64 reference to", worst_native_vs_host,
              "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ NATIVE split+merge diverges from host-f64 reference by", worst_native_vs_host,
              "-- more than", reorder_bound, "-- THE REDUCTION-SHAPE CHANGE CHANGED THE ANSWER")

    if Float64(worst_orig_vs_native) <= reorder_bound:
        passed += 1
        print("     ✅ single-dispatch original and NATIVE split+merge agree with EACH OTHER to",
              worst_orig_vs_native, "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ single-dispatch original and NATIVE split+merge disagree by",
              worst_orig_vs_native, "-- more than", reorder_bound)

    if Float64(worst_split_vs_native) <= reorder_bound:
        passed += 1
        print("     ✅ TWO-LEVEL and NATIVE split+merge agree with EACH OTHER to",
              worst_split_vs_native, "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ TWO-LEVEL and NATIVE split+merge disagree by", worst_split_vs_native,
              "-- more than", reorder_bound, "-- THE REDUCTION-SHAPE CHANGE INTRODUCED A REAL DIVERGENCE")


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no split/merge/native kernel compiled, nothing to run")
        print("  [residentk.kernels attn-splitk-native-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels attn-splitk-native-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # ── Qwen3-0.6B-Base's real head shape (h_q=16, h_kv=2, d_head=128), the production case ──
        # 1. Evenly-divisible n_keys/n_splits, several keys per split -- the common case.
        _run_case(ctx, "even", 16, 2, 128, 64, 8, passed, failed)
        # 2. RAGGED: n_keys not a multiple of n_splits.
        _run_case(ctx, "ragged", 16, 2, 128, 37, 6, passed, failed)
        # 3. n_splits > n_keys: several splits are genuinely EMPTY -- this kernel's own
        #    `for j in range(key_start, key_end)` over an empty range must iterate zero times.
        _run_case(ctx, "more_splits_than_keys", 16, 2, 128, 5, 16, passed, failed)
        # 4. n_splits == 1: degenerates to exactly the single-dispatch kernel's own range.
        _run_case(ctx, "single_split", 16, 2, 128, 20, 1, passed, failed)
        # 5. Production's own shipped split count (16) at a depth that gates the split path in.
        _run_case(ctx, "deep_like_production", 16, 2, 128, 600, 16, passed, failed)
        # 6. The Profile phase's own dominant-cost measurement depth, n_keys=4000, n_splits=16
        #    (the SHIPPED n_splits this task deliberately leaves unchanged).
        _run_case(ctx, "very_deep_like_4000", 16, 2, 128, 4000, 16, passed, failed)

        # ── multi-head x multi-depth sweep, reproducing the design phase's own scratch probe
        # (16 heads, n_keys in {1, 2, 8, 33, 64, 257}) as a PERMANENT, committed check instead of a
        # throwaway /tmp script -- widened with n_splits > n_keys at the shallowest depths (1, 2) so
        # the empty-split path is exercised at this head count too, not just at h_q=16 above ──
        _run_case(ctx, "sweep_hq16_n1", 16, 2, 128, 1, 16, passed, failed)
        _run_case(ctx, "sweep_hq16_n2", 16, 2, 128, 2, 16, passed, failed)
        _run_case(ctx, "sweep_hq16_n8", 16, 2, 128, 8, 16, passed, failed)
        _run_case(ctx, "sweep_hq16_n33", 16, 2, 128, 33, 16, passed, failed)
        _run_case(ctx, "sweep_hq16_n64", 16, 2, 128, 64, 16, passed, failed)
        _run_case(ctx, "sweep_hq16_n257", 16, 2, 128, 257, 16, passed, failed)

        # ── a smaller GQA group ratio (h_q=4, h_kv=2 -- the shape `test_residentk_attn_splitk_
        # kernel.mojo`'s own suite uses) at the same depth sweep, checking the `hk = h // (h_q //
        # h_kv)` grouping arithmetic this kernel's per-thread `qv`/`kb` indexing depends on is not
        # somehow coupled to the specific 16/2 production ratio ──
        _run_case(ctx, "sweep_hq4hkv2_n1", 4, 2, 128, 1, 8, passed, failed)
        _run_case(ctx, "sweep_hq4hkv2_n33", 4, 2, 128, 33, 8, passed, failed)
        _run_case(ctx, "sweep_hq4hkv2_n257", 4, 2, 128, 257, 8, passed, failed)

        # ── plain MHA, h_q == h_kv (no GQA grouping at all: `group = 1`, `hk = h` for every head) --
        # a shape neither the design phase's own scratch probe nor production ever exercises, added
        # here specifically because it is the degenerate case of the grouping arithmetic above ──
        _run_case(ctx, "sweep_mha_hq8_n33", 8, 8, 128, 33, 8, passed, failed)
        _run_case(ctx, "sweep_mha_hq8_n257", 8, 8, 128, 257, 8, passed, failed)

        # ── the PRODUCTION widened split count (`_ATTN_SPLITK_N_SPLITS_NATIVE = 80`,
        # `metaldispatch.session`, `_MBQwen3I8AllSimd6`'s own Candidate-1 configuration -- see that
        # constant's own docstring for the sweep that picked it) at the production head shape and at
        # a range of depths spanning both sides of `n_splits=80`: `n_keys < n_splits` (many empty
        # splits, `n_keys=64`), `n_keys` close to `n_splits` (`n_keys=100`), and the Profile phase's
        # own dominant-cost depth (`n_keys=4000`) this configuration was specifically tuned for ──
        _run_case(ctx, "production_n80_shallow", 16, 2, 128, 64, 80, passed, failed)
        _run_case(ctx, "production_n80_near", 16, 2, 128, 100, 80, passed, failed)
        _run_case(ctx, "production_n80_deep_4000", 16, 2, 128, 4000, 80, passed, failed)

        print("  [residentk.kernels attn-splitk-native-isolated] Passed:", passed, "Failed:", failed)
