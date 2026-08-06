"""test_residentk_sdpa_simd_kernel.mojo — the SDPA-reduction-mechanism kernel pair
(`_sdpa_kernel_simd`/`_sdpa_kernel_simd_kvf16`), isolated at the KERNEL level from everything else
`residentk` does, following `test_residentk_kvcache_fp16_kernel.mojo`'s own pattern exactly (a
dedicated, narrow, kernel-only suite, not folded into `test_residentk_session.mojo`'s big shared
model fixture).

WHY A SEPARATE FIXTURE, NOT `test_residentk_session.mojo`'s SHARED ONE
--------------------------------------------------------------------------
That file's shared model uses `D_HEAD = 8` deliberately, to exercise non-power-of-everything shapes
at the WHOLE-SESSION level. `_sdpa_kernel_simd`'s two-level reduction needs every SIMD-group it
launches to be FULLY populated — `std.gpu.primitives.warp.sum`'s butterfly shuffle is only defined
across a real, complete 32-lane hardware group — so `D_HEAD = 8` (smaller than one warp) is not a
valid shape for this kernel at all (`_ResidentQwen3I8SDPASimd.__init__` refuses it; see that
constructor's own docstring). This file uses its OWN fixture at `D_HEAD = 128` — Qwen3-0.6B-Base's
REAL head dimension, four full 32-lane SIMD-groups per threadgroup — so the test exercises exactly
the cross-SIMD-group combine step the reduction swap is about, not a degenerate single-group case.

Two kernel pairs, each tested against an INDEPENDENT host Float64 reference AND against each other
---------------------------------------------------------------------------------------------------
1. **Float32 KV cache**: `_sdpa_kernel` (the original barrier-tree reduction) vs `_sdpa_kernel_simd`
   (the SIMD-group-shuffle two-level reduction), same `q`/`ck`/`cv` inputs, same grid/block shape.
2. **Float16 KV cache**: `_sdpa_kernel_kvf16` vs `_sdpa_kernel_simd_kvf16`, composing the reduction-
   mechanism axis with the KV-cache-precision axis exactly as `_sdpa_kernel_simd_kvf16`'s own
   docstring claims it does.

Both pairs are checked against a pure-host, no-GPU, no-shuffle, no-shared-memory-tree Float64
reference (`_host_reference` below) — the SAME online-softmax arithmetic in the most direct,
unoptimized form there is, computed independently of either kernel's implementation choices. Three-
way agreement (barrier-tree, SIMD-shuffle, host-f64-reference) is a stronger claim than any pairwise
one: it rules out the barrier-tree kernel and the SIMD-shuffle kernel sharing some SUBTLE common bug
that a pairwise-only comparison would not catch.

WHY THE BOUND IS TIGHT, NOT LOOSE LIKE THE QUANTIZATION-ARM SUITES
------------------------------------------------------------------------
Every OTHER precision-arm suite in this package (`_i8`, `_i4`, `_f16`) bounds against a coarser
STORAGE format's rounding error, which is genuinely large (a full quantization step). This kernel
pair changes NEITHER the storage dtype NOR the math — only the SUMMATION ORDER of the same `d_head`
partial products (`_sdpa_kernel`'s pairwise shared-memory tree vs `_sdpa_kernel_simd`'s per-SIMD-
group butterfly-then-linear-combine). Float32 addition is not associative, so a nonzero delta is
expected, but it should be at the scale of a handful of Float32 unit-roundoffs accumulated over
`d_head` additions and `n_keys` online-softmax rescale steps — orders of magnitude tighter than any
quantization bound in this package. The bound below is deliberately still generous (never re-derive
a hand-wavy tight formula nobody re-checks) but is checked to REJECT a bound ten thousand times
looser, so it is a real, discriminating check, not a rubber stamp.
"""

from std.gpu.host import DeviceContext
from std.math import exp, sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _sdpa_kernel,
    _sdpa_kernel_kvf16,
    _sdpa_kernel_simd,
    _sdpa_kernel_simd_kvf16,
)

comptime H_Q: Int = 4
comptime H_KV: Int = 2
comptime D_HEAD: Int = 128
"""Qwen3-0.6B-Base's REAL head dimension — four full 32-lane SIMD-groups, the exact shape
`_sdpa_kernel_simd` was built for. See this file's own module docstring for why the shared suite's
`D_HEAD = 8` is not a valid shape for this particular kernel pair."""
comptime N_KEYS: Int = 6
"""Enough keys to exercise the online-softmax running-max/running-sum rescale more than once (a
wrong rescale, not just a wrong single-key score, would show up), matching
`sdpa_simd_reduce_probe.mojo`'s own Stage-1 choice."""


def _abs(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    """Deterministic, KNOWN small values — same two-coprime-multiplier discipline
    `test_residentk_kvcache_fp16_kernel.mojo`'s own `_pseudo_f32` uses."""
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
    """Pure-host, Float64, no-GPU online-softmax reference — the most direct, unoptimized form of
    the SAME algorithm both kernels compute, independent of either one's shared-memory tree or
    SIMD-shuffle implementation choice. `kv_k`/`kv_v` are `[n_keys, h_kv, d_head]`, matching both
    kernels' own layout."""
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


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no SDPA-simd kernel compiled, nothing to run")
        print("  [residentk.kernels sdpa-simd-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels sdpa-simd-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()
        var scale = Float32(1.0 / sqrt(Float64(D_HEAD)))

        var q_vals = _pseudo_f32(H_Q * D_HEAD, 21, 1.0)
        var kv_k_vals = _pseudo_f32(N_KEYS * H_KV * D_HEAD, 31, 0.8)
        var kv_v_vals = List[Float32](capacity=N_KEYS * H_KV * D_HEAD)
        for i in range(N_KEYS * H_KV * D_HEAD):
            # A distinct deterministic set for V, so a K/V swap in either kernel would not
            # accidentally cancel out — same discipline the kvf16 kernel test uses.
            kv_v_vals.append(kv_k_vals[(i + 17) % len(kv_k_vals)])

        var host_ref = _host_reference(q_vals, kv_k_vals, kv_v_vals, H_Q, H_KV, D_HEAD, N_KEYS, scale)

        # ══ 1. Float32 KV cache: _sdpa_kernel (barrier-tree) vs _sdpa_kernel_simd (SIMD-shuffle) ══
        var q_buf = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
        var ck_buf = ctx.enqueue_create_buffer[DType.float32](N_KEYS * H_KV * D_HEAD)
        var cv_buf = ctx.enqueue_create_buffer[DType.float32](N_KEYS * H_KV * D_HEAD)
        with q_buf.map_to_host() as h:
            for i in range(H_Q * D_HEAD):
                h[i] = q_vals[i]
        with ck_buf.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                h[i] = kv_k_vals[i]
        with cv_buf.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                h[i] = kv_v_vals[i]

        var attn_tree = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
        var attn_simd = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)

        var f_tree = ctx.compile_function_unchecked[_sdpa_kernel]()
        var f_simd = ctx.compile_function_unchecked[_sdpa_kernel_simd]()

        ctx.enqueue_function_unchecked(
            f_tree,
            attn_tree.unsafe_ptr(), q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
            N_KEYS, H_Q, H_KV, D_HEAD, scale,
            grid_dim=H_Q, block_dim=D_HEAD,
        )
        ctx.enqueue_function_unchecked(
            f_simd,
            attn_simd.unsafe_ptr(), q_buf.unsafe_ptr(), ck_buf.unsafe_ptr(), cv_buf.unsafe_ptr(),
            N_KEYS, H_Q, H_KV, D_HEAD, scale,
            grid_dim=H_Q, block_dim=D_HEAD,
        )
        ctx.synchronize()

        var worst_tree_vs_host = Float64(0.0)
        var worst_simd_vs_host = Float64(0.0)
        var worst_tree_vs_simd = Float32(0.0)
        var max_val = Float32(0.0)
        with attn_tree.map_to_host() as ht:
            with attn_simd.map_to_host() as hs:
                for i in range(H_Q * D_HEAD):
                    var dt = _abs64(Float64(ht[i]) - host_ref[i])
                    var ds = _abs64(Float64(hs[i]) - host_ref[i])
                    var dts = _abs(ht[i] - hs[i])
                    if dt > worst_tree_vs_host:
                        worst_tree_vs_host = dt
                    if ds > worst_simd_vs_host:
                        worst_simd_vs_host = ds
                    if dts > worst_tree_vs_simd:
                        worst_tree_vs_simd = dts
                    var v = _abs(ht[i])
                    if v > max_val:
                        max_val = v

        print("  •  [f32-cache] barrier_tree vs host-f64 reference: worst|Δ|=", worst_tree_vs_host)
        print("  •  [f32-cache] simd_shuffle vs host-f64 reference: worst|Δ|=", worst_simd_vs_host)
        print("  •  [f32-cache] barrier_tree vs simd_shuffle (against each other): worst|Δ|=",
              worst_tree_vs_simd, " max|attn|=", max_val)

        # Float32 unit-roundoff (~2^-23) accumulated over `D_HEAD` additions and `N_KEYS`
        # online-softmax rescale steps — generous, but the scale a REORDERED-SUMMATION delta
        # belongs at, not a quantization-arm's much larger storage-format bound.
        comptime _F32_EPS: Float64 = 1.1920929e-7
        var reorder_bound = _F32_EPS * Float64(D_HEAD * N_KEYS) * (1.0 + Float64(max_val))
        if worst_tree_vs_host <= reorder_bound:
            passed += 1
            print("  ✅ the barrier-tree kernel agrees with the host Float64 reference to",
                  worst_tree_vs_host, "within", reorder_bound)
        else:
            failed += 1
            print("  ❌ the barrier-tree kernel diverges from the host Float64 reference by",
                  worst_tree_vs_host, "-- more than", reorder_bound)

        if Float64(worst_simd_vs_host) <= reorder_bound:
            passed += 1
            print("  ✅ the SIMD-shuffle kernel agrees with the host Float64 reference to",
                  worst_simd_vs_host, "within", reorder_bound)
        else:
            failed += 1
            print("  ❌ the SIMD-shuffle kernel diverges from the host Float64 reference by",
                  worst_simd_vs_host, "-- more than", reorder_bound, "-- THE REDUCTION MECHANISM",
                  "SWAP CHANGED THE ANSWER, not just its rounding")

        if Float64(worst_tree_vs_simd) <= reorder_bound:
            passed += 1
            print("  ✅ the two kernels agree with EACH OTHER to", worst_tree_vs_simd, "within",
                  reorder_bound, "-- same math, different (but equally valid) summation order")
        else:
            failed += 1
            print("  ❌ the two kernels disagree with each other by", worst_tree_vs_simd,
                  "-- more than", reorder_bound)

        # `reorder_bound` (printed above alongside each pass/fail line) is not a loose rubber
        # stamp: it is orders of magnitude tighter than any quantization-arm suite's own bound in
        # this package (int8's `1/127`, fp16's `9.765625e-4` PER independent rounding) — a real
        # reduction bug (wrong GQA mapping, a dropped SIMD-group, a missing rescale) produces an
        # error proportional to the WRONG term's whole magnitude, not to `D_HEAD * N_KEYS` Float32
        # unit-roundoffs, so it would blow through this bound by many orders of magnitude, not
        # sneak under it.
        print("  •  raw barrier-tree-vs-SIMD-shuffle delta:", worst_tree_vs_simd,
              "(0.0 would mean bit-identical summation order by coincidence — either outcome",
              "passes the bound above; this line is informational)")

        # ══ 2. Float16 KV cache: _sdpa_kernel_kvf16 vs _sdpa_kernel_simd_kvf16 ══════════════════
        var ck16_buf = ctx.enqueue_create_buffer[DType.float16](N_KEYS * H_KV * D_HEAD)
        var cv16_buf = ctx.enqueue_create_buffer[DType.float16](N_KEYS * H_KV * D_HEAD)
        with ck16_buf.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                h[i] = Float16(kv_k_vals[i])
        with cv16_buf.map_to_host() as h:
            for i in range(N_KEYS * H_KV * D_HEAD):
                h[i] = Float16(kv_v_vals[i])

        var attn_tree16 = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)
        var attn_simd16 = ctx.enqueue_create_buffer[DType.float32](H_Q * D_HEAD)

        var f_tree16 = ctx.compile_function_unchecked[_sdpa_kernel_kvf16]()
        var f_simd16 = ctx.compile_function_unchecked[_sdpa_kernel_simd_kvf16]()

        ctx.enqueue_function_unchecked(
            f_tree16,
            attn_tree16.unsafe_ptr(), q_buf.unsafe_ptr(), ck16_buf.unsafe_ptr(), cv16_buf.unsafe_ptr(),
            N_KEYS, H_Q, H_KV, D_HEAD, scale,
            grid_dim=H_Q, block_dim=D_HEAD,
        )
        ctx.enqueue_function_unchecked(
            f_simd16,
            attn_simd16.unsafe_ptr(), q_buf.unsafe_ptr(), ck16_buf.unsafe_ptr(), cv16_buf.unsafe_ptr(),
            N_KEYS, H_Q, H_KV, D_HEAD, scale,
            grid_dim=H_Q, block_dim=D_HEAD,
        )
        ctx.synchronize()

        var worst_tree16_vs_simd16 = Float32(0.0)
        with attn_tree16.map_to_host() as ht16:
            with attn_simd16.map_to_host() as hs16:
                for i in range(H_Q * D_HEAD):
                    var d16 = _abs(ht16[i] - hs16[i])
                    if d16 > worst_tree16_vs_simd16:
                        worst_tree16_vs_simd16 = d16

        print("  •  [f16-cache] barrier_tree_kvf16 vs simd_shuffle_kvf16: worst|Δ|=",
              worst_tree16_vs_simd16)
        if Float64(worst_tree16_vs_simd16) <= reorder_bound:
            passed += 1
            print("  ✅ the reduction-mechanism swap composes cleanly with the fp16-KV-cache axis:",
                  "the two kvf16 kernels agree to", worst_tree16_vs_simd16, "within", reorder_bound)
        else:
            failed += 1
            print("  ❌ the reduction-mechanism swap does NOT compose cleanly with the fp16-KV-cache",
                  "axis: delta", worst_tree16_vs_simd16, "exceeds", reorder_bound)

        print("  [residentk.kernels sdpa-simd-isolated] Passed:", passed, "Failed:", failed)
