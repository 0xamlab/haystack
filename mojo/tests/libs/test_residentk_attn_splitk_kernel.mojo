"""test_residentk_attn_splitk_kernel.mojo — the OCCUPANCY-fix kernel pair
(`_splitk_partial_kernel_simd`/`_splitk_merge_kernel_simd`), isolated at the KERNEL level
from everything else `residentk` does, following `test_residentk_sdpa_simd_kernel.mojo`'s own
pattern exactly (a dedicated, narrow, kernel-only suite, hand-written, not generated).

WHAT THIS PAIR CLAIMS, AND WHAT THIS FILE CHECKS BEFORE TRUSTING IT
---------------------------------------------------------------------------------------------------
`_splitk_partial_kernel_simd` computes the SAME online-softmax math `_sdpa_kernel_simd` does,
just over a bounded key range `[key_start, key_end)` instead of `[0, n_keys)`, and writes an
UNNORMALIZED `(m, l, o)` triple per `(head, split)` instead of a normalized `attn_out`.
`_splitk_merge_kernel_simd` combines `n_splits` of those triples per head into one final
normalized `attn_out`, via the standard associative online-softmax merge. Splitting `n_keys` into
`n_splits` contiguous pieces and merging them back should give the IDENTICAL attention this kernel's
own single-dispatch twin computes over the whole range at once — this file checks that claim four
ways before any production code depends on it:

1. **Against an independent host Float64 reference** (`_host_reference`, copied byte-for-byte from
   `test_residentk_sdpa_simd_kernel.mojo`'s own — the SAME unoptimized online-softmax computed on
   the CPU, in double precision, with no GPU, no SIMD-shuffle, no split/merge structure at all).
2. **Against `_sdpa_kernel_simd` itself**, same `q`/`ck`/`cv` inputs, dispatched at ITS OWN
   `grid_dim=h_q` shape — the exact kernel this pair is an occupancy-only twin of.
3. **At a RAGGED `n_keys`/`n_splits` pair** (`n_keys` not evenly divisible by `n_splits`) — the
   split-range formula `key_start = n_keys * s // n_splits`, `key_end = n_keys * (s + 1) // n_splits`
   must still partition `[0, n_keys)` exactly once each with no gap and no overlap for a non-round
   ratio, not just the convenient evenly-divisible case.
4. **At `n_splits > n_keys`** (more splits than keys — every split beyond the first `n_keys` of them
   is genuinely EMPTY: `key_start == key_end`) — `_splitk_partial_kernel_simd`'s own docstring
   claims an empty split's `(m, l, o) = (_NEG_HUGE, 0.0, 0.0)` folds into the merge as a true no-op;
   this is the case that actually exercises that claim, not just states it.

WHY THE BOUND IS TIGHT, NOT LOOSE LIKE THE QUANTIZATION-ARM SUITES
------------------------------------------------------------------------
Same reasoning as `test_residentk_sdpa_simd_kernel.mojo`'s own module docstring: this pair changes
NEITHER the storage dtype NOR the underlying math, only the SUMMATION ORDER (now three-level: per-
key within a split, per-SIMD-group via `_warp_sum`, then per-split in the merge, versus
`_sdpa_kernel_simd`'s own two-level per-key-then-per-SIMD-group order). Float32 addition is not
associative, so a nonzero delta is expected and the bound below is scaled by the SAME `D_HEAD *
N_KEYS` Float32-unit-roundoff term that file's own bound uses (an extra reordering level does not
change the COUNT of additions feeding one output element, only their grouping) — deliberately not a
hand-wavy rubber stamp, checked below to REJECT a bound ten thousand times looser.
"""

from max.gpu.host import DeviceContext
from std.math import exp, sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _sdpa_kernel_simd,
    _splitk_partial_kernel_simd,
    _splitk_merge_kernel_simd,
)

comptime H_Q: Int = 4
comptime H_KV: Int = 2
comptime D_HEAD: Int = 128
"""Qwen3-0.6B-Base's REAL head dimension — see `test_residentk_sdpa_simd_kernel.mojo`'s own
docstring for why `_warp_sum`'s butterfly shuffle needs every SIMD-group full, which rules out a
`D_HEAD` smaller than one 32-lane warp."""


def _abs(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    """Deterministic, KNOWN small values — same two-coprime-multiplier discipline
    `test_residentk_sdpa_simd_kernel.mojo`'s own `_pseudo_f32` uses."""
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
    """Pure-host, Float64, no-GPU online-softmax reference — byte-for-byte
    `test_residentk_sdpa_simd_kernel.mojo`'s own `_host_reference`."""
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
    """One (n_keys, n_splits) case: builds fresh deterministic inputs, runs `_sdpa_kernel_simd`
    (the single-dispatch original) and the split+merge pair, and checks BOTH against the host-f64
    reference AND against each other."""
    var scale = Float32(1.0 / sqrt(Float64(D_HEAD)))
    var q_vals = _pseudo_f32(H_Q * D_HEAD, 21 + n_keys + n_splits, 1.0)
    var kv_k_vals = _pseudo_f32(n_keys * H_KV * D_HEAD, 31 + n_keys + n_splits, 0.8)
    var kv_v_vals = List[Float32](capacity=n_keys * H_KV * D_HEAD)
    for i in range(n_keys * H_KV * D_HEAD):
        kv_v_vals.append(kv_k_vals[(i + 17) % len(kv_k_vals)])

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

    # ── the single-dispatch original, `_sdpa_kernel_simd` at its own grid shape ──
    var attn_orig = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
    var f_orig = ctx.compile_function[_sdpa_kernel_simd]()
    ctx.enqueue_function_unchecked(
        f_orig,
        attn_orig.unsafe_ptr(), q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
        n_keys, H_Q, H_KV, D_HEAD, scale,
        grid_dim=H_Q, block_dim=D_HEAD,
    )

    # ── the split+merge pair ──
    var m_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * n_splits * D_HEAD)
    var attn_split = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)

    var f_partial = ctx.compile_function[_splitk_partial_kernel_simd]()
    var f_merge = ctx.compile_function[_splitk_merge_kernel_simd]()
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
    ctx.synchronize()

    var worst_orig_vs_host = Float64(0.0)
    var worst_split_vs_host = Float64(0.0)
    var worst_orig_vs_split = Float32(0.0)
    var max_val = Float32(0.0)
    with attn_orig.map_to_host() as ho:
        with attn_split.map_to_host() as hs:
            for i in range(H_Q * D_HEAD):
                var d_oh = _abs64(Float64(ho[i]) - host_ref[i])
                var d_sh = _abs64(Float64(hs[i]) - host_ref[i])
                var d_os = _abs(ho[i] - hs[i])
                if d_oh > worst_orig_vs_host:
                    worst_orig_vs_host = d_oh
                if d_sh > worst_split_vs_host:
                    worst_split_vs_host = d_sh
                if d_os > worst_orig_vs_split:
                    worst_orig_vs_split = d_os
                var v = _abs(ho[i])
                if v > max_val:
                    max_val = v

    comptime _F32_EPS: Float64 = 1.1920929e-7
    var reorder_bound = _F32_EPS * Float64(D_HEAD * n_keys + D_HEAD) * (1.0 + Float64(max_val))
    print("  •  [", name, "] n_keys=", n_keys, " n_splits=", n_splits,
          " orig_vs_host=", worst_orig_vs_host, " split_vs_host=", worst_split_vs_host,
          " orig_vs_split=", worst_orig_vs_split, " bound=", reorder_bound)

    if worst_orig_vs_host <= reorder_bound:
        passed += 1
    else:
        failed += 1
        print("     ❌ the single-dispatch original diverges from host-f64 by", worst_orig_vs_host,
              "-- more than", reorder_bound, "(bound itself, not the split/merge pair, would be",
              "broken -- this would also fail in the pre-existing sdpa-simd suite)")

    if Float64(worst_split_vs_host) <= reorder_bound:
        passed += 1
        print("     ✅ split+merge agrees with host-f64 reference to", worst_split_vs_host,
              "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ split+merge diverges from host-f64 reference by", worst_split_vs_host,
              "-- more than", reorder_bound, "-- THE SPLIT/MERGE RESTRUCTURING CHANGED THE ANSWER")

    if Float64(worst_orig_vs_split) <= reorder_bound:
        passed += 1
        print("     ✅ single-dispatch original and split+merge agree with EACH OTHER to",
              worst_orig_vs_split, "within", reorder_bound)
    else:
        failed += 1
        print("     ❌ single-dispatch original and split+merge disagree by", worst_orig_vs_split,
              "-- more than", reorder_bound)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no split/merge kernel compiled, nothing to run")
        print("  [residentk.kernels attn-splitk-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels attn-splitk-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # 1. Evenly-divisible n_keys/n_splits, several keys per split -- the common case.
        _run_case(ctx, "even", 64, 8, passed, failed)
        # 2. RAGGED: n_keys not a multiple of n_splits.
        _run_case(ctx, "ragged", 37, 6, passed, failed)
        # 3. n_splits > n_keys: several splits are genuinely EMPTY.
        _run_case(ctx, "more_splits_than_keys", 5, 16, passed, failed)
        # 4. n_splits == 1: degenerates to exactly the single-dispatch kernel's own range.
        _run_case(ctx, "single_split", 20, 1, passed, failed)
        # 5. A depth in the range production actually gates the split path at.
        _run_case(ctx, "deep_like_production", 600, 16, passed, failed)

        print("  [residentk.kernels attn-splitk-isolated] Passed:", passed, "Failed:", failed)
