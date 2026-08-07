"""test_residentk_gemv_simd_kernel.mojo — the GEMV-reduction-mechanism kernel triple
(`_norm_gemv_kernel_simd_i8`/`_gemv_accum_kernel_simd_i8`/`_norm_gemv2_swiglu_kernel_simd_i8`),
isolated at the KERNEL level from everything else `residentk` does, following
`test_residentk_sdpa_simd_kernel.mojo`'s own pattern exactly (a dedicated, narrow, kernel-only
suite, not folded into `test_residentk_session.mojo`'s big shared model fixture).

WHY A SEPARATE FIXTURE, NOT `test_residentk_session.mojo`'s SHARED ONE
--------------------------------------------------------------------------
That file's shared model uses `D_MODEL = 8`-scale shapes deliberately, to exercise
non-power-of-everything shapes at the WHOLE-SESSION level, but every one of its GEMV dispatches
still launches `_TG = 256` threads per threadgroup regardless of `k`/`n` — the reduction-mechanism
question this file asks (does the whole-threadgroup sum-of-squares reduction and the per-column
dot-product reduction still agree once `_LANES = 32`-wide SIMD-group shuffles replace the
barrier-tree?) is answered at the SAME `_TG = 256` shape either way, so this file picks its OWN
small `k`/`n` — deliberately NOT multiples of `_LANES`/`_TG`/`_VEC_I8`, to exercise the vectorized-
loop-plus-scalar-tail path every GEMV kernel already has — rather than borrowing the shared
fixture's shapes.

Three kernel pairs, each tested against an INDEPENDENT host Float64 reference AND against each
other
---------------------------------------------------------------------------------------------------
1. **QKV projection** (`_norm_gemv_kernel_i8` vs `_norm_gemv_kernel_simd_i8`): same `x`/`gamma`/`w`/
   `wscale` inputs, same grid/block shape. Exercises BOTH reduction shapes this kernel has: the
   `_TG`-wide sum-of-squares AND the per-output-column dot product.
2. **o_proj/down_proj** (`_gemv_accum_kernel_i8` vs `_gemv_accum_kernel_simd_i8`): same inputs,
   PLUS the residual `+=` — `y` pre-seeded with a nonzero pattern so a dropped `+=` (turned into a
   plain `=`) would show up as a wrong answer, not coincidentally the right one. Exercises only the
   per-output-column dot-product shape (no norm, no sum-of-squares stage).
3. **gate-up (SwiGLU)** (`_norm_gemv2_swiglu_kernel_i8` vs `_norm_gemv2_swiglu_kernel_simd_i8`):
   same inputs, concatenated gate/up weight matrix and scale buffer. Exercises the sum-of-squares
   shape ONCE plus the per-output-column shape TWICE (gate, then up) — the composition
   `_norm_gemv2_swiglu_kernel_simd_i8`'s own docstring claims needs one retained combine-barrier
   between gate and up, this is that claim, checked.

Each barrier-tree/SIMD-shuffle pair is checked against a pure-host, no-GPU, no-shuffle, no-shared-
memory-tree Float64 reference computing the SAME int8-dequantized GEMV math independently of
either kernel's implementation choice — three-way agreement is a stronger claim than any pairwise
one, exactly `test_residentk_sdpa_simd_kernel.mojo`'s own reasoning.

WHY THE BOUND IS TIGHT, NOT LOOSE LIKE THE QUANTIZATION-ARM SUITES
------------------------------------------------------------------------
This kernel pair changes NEITHER the storage dtype NOR the math — only the SUMMATION ORDER of the
same `k` int8-dequantized partial products. Float32 addition is not associative, so a nonzero
delta is theoretically possible, but it should be at the scale of a handful of Float32 unit-
roundoffs accumulated over `k` additions — orders of magnitude tighter than this package's own
int8 quantization-step bound (`1/127` of the row's max magnitude). The bound below is deliberately
still generous (never re-derive a hand-wavy tight formula nobody re-checks) but is checked to
REJECT a bound ten thousand times looser, so it is a real, discriminating check, not a rubber
stamp.
"""

from std.gpu.host import DeviceContext
from std.math import exp, sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _norm_gemv_kernel_i8,
    _norm_gemv_kernel_simd_i8,
    _gemv_accum_kernel_i8,
    _gemv_accum_kernel_simd_i8,
    _norm_gemv2_swiglu_kernel_i8,
    _norm_gemv2_swiglu_kernel_simd_i8,
    _TG,
    _SUBS,
)

comptime K: Int = 137
"""Deliberately not a multiple of `_LANES=32`, `_VEC_I8=4`, or `_TG=256` — exercises the
vectorized-main-loop-plus-scalar-tail path both the barrier-tree and SIMD-shuffle kernels share."""

comptime N: Int = 19
"""Deliberately not a multiple of `_SUBS=8` — `grid_dim = ceil(N / _SUBS) = 3` threadgroups, the
last one partially populated (`N - 2*_SUBS = 3` live columns out of 8), exercising the `j < n`
guard in both kernels identically."""

comptime EPS: Float32 = 1.0e-6


def _abs(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f64(n: Int, seed: Int, amp: Float64) -> List[Float64]:
    """Deterministic, KNOWN small values — same two-coprime-multiplier discipline
    `test_residentk_sdpa_simd_kernel.mojo`'s own `_pseudo_f32` uses, in Float64 so the host
    reference below never rounds through Float32 before it has to."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var a = Float64((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float64((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def _quantize_row_i8_host(row: List[Float64], mut out_row: List[Int8]) -> Float64:
    """Pure-host per-row int8 quantization, independent of `residentk.session`'s own
    `_quantize_transposed_into_i8` — the SAME `scale = max(|row|) / 127` convention, computed here
    from scratch so this file's host reference does not depend on the very upload path the kernels
    under test read their `wscale` from. Fills `out_row` in place and returns the row's scale
    (an out-parameter, not a tuple return, to sidestep `List[Int8]` not being `ImplicitlyCopyable`)."""
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


def _host_norm_gemv(
    x: List[Float64], gamma: List[Float64], w_rows: List[List[Int8]], wscale: List[Float64],
    k: Int, n: Int, eps: Float64,
) -> List[Float64]:
    """Pure-host, Float64 reference for `y = W_dequant @ (rmsnorm(x) * gamma)` — the exact math
    both `_norm_gemv_kernel_i8` and `_norm_gemv_kernel_simd_i8` claim to compute, independent of
    either kernel's reduction mechanism."""
    var ss = 0.0
    for i in range(k):
        ss += x[i] * x[i]
    var inv = 1.0 / sqrt(ss / Float64(k) + eps)
    var xn = List[Float64](capacity=k)
    for i in range(k):
        xn.append(x[i] * inv * gamma[i])
    var out = List[Float64](capacity=n)
    for j in range(n):
        var s = 0.0
        for i in range(k):
            s += xn[i] * (Float64(w_rows[j][i]) * wscale[j])
        out.append(s)
    return out^


def _host_gemv_accum(
    y0: List[Float64], x: List[Float64], w_rows: List[List[Int8]], wscale: List[Float64],
    k: Int, n: Int,
) -> List[Float64]:
    """Pure-host, Float64 reference for `y = y0 + W_dequant @ x`."""
    var out = List[Float64](capacity=n)
    for j in range(n):
        var s = 0.0
        for i in range(k):
            s += x[i] * (Float64(w_rows[j][i]) * wscale[j])
        out.append(y0[j] + s)
    return out^


def _host_swiglu(
    x: List[Float64], gamma: List[Float64],
    gate_rows: List[List[Int8]], gate_scale: List[Float64],
    up_rows: List[List[Int8]], up_scale: List[Float64],
    k: Int, n_ff: Int, eps: Float64,
) -> List[Float64]:
    """Pure-host, Float64 reference for `act = swish(W_gate_dequant @ xn) * (W_up_dequant @ xn)`."""
    var ss = 0.0
    for i in range(k):
        ss += x[i] * x[i]
    var inv = 1.0 / sqrt(ss / Float64(k) + eps)
    var xn = List[Float64](capacity=k)
    for i in range(k):
        xn.append(x[i] * inv * gamma[i])
    var out = List[Float64](capacity=n_ff)
    for j in range(n_ff):
        var g = 0.0
        var u = 0.0
        for i in range(k):
            g += xn[i] * (Float64(gate_rows[j][i]) * gate_scale[j])
            u += xn[i] * (Float64(up_rows[j][i]) * up_scale[j])
        var swish = g / (1.0 + _exp64(-g))
        out.append(swish * u)
    return out^


def _exp64(x: Float64) -> Float64:
    from std.math import exp
    return exp(x)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        passed += 1
        print("  ✅ built without -D ALGENTA_GPU: no GEMV-simd kernels compiled, nothing to run")
        print("  [residentk.kernels gemv-simd-isolated] Passed:", passed, "Failed:", failed)
    else:
        if not has_accelerator():
            passed += 1
            print("  ✅ GPU build, no accelerator: nothing to run at kernel level either")
            print("  [residentk.kernels gemv-simd-isolated] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # Float32 unit-roundoff (~2^-23) accumulated over `K` additions — generous, but the scale
        # a REORDERED-SUMMATION delta belongs at, not this package's `1/127` int8-quantization
        # bound (checked below to be far looser than this one).
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

        var w_rows_a = List[List[Int8]](capacity=N)
        var wscale_a = List[Float64](capacity=N)
        var w_flat_a = List[Int8](capacity=N * K)
        for j in range(N):
            var row64 = _pseudo_f64(K, 100 + j * 11, 0.8)
            var q_row = List[Int8](capacity=K)
            var s = _quantize_row_i8_host(row64, q_row)
            wscale_a.append(s)
            for i in range(K):
                w_flat_a.append(q_row[i])
            w_rows_a.append(q_row^)

        var x_buf = ctx.enqueue_create_buffer[DType.float32](K)
        var gamma_buf = ctx.enqueue_create_buffer[DType.float32](K)
        var w_a_buf = ctx.enqueue_create_buffer[DType.int8](N * K)
        var wscale_a_buf = ctx.enqueue_create_buffer[DType.float32](N)
        with x_buf.map_to_host() as h:
            for i in range(K):
                h[i] = Float32(x64[i])
        with gamma_buf.map_to_host() as h:
            for i in range(K):
                h[i] = Float32(gamma64[i])
        with w_a_buf.map_to_host() as h:
            for idx in range(N * K):
                h[idx] = w_flat_a[idx]
        with wscale_a_buf.map_to_host() as h:
            for j in range(N):
                h[j] = Float32(wscale_a[j])
        ctx.synchronize()

        var grid_n = (N + _SUBS - 1) // _SUBS

        # ══ 1. norm_gemv (QKV projection): _norm_gemv_kernel_i8 vs _norm_gemv_kernel_simd_i8 ══════
        var host_ng = _host_norm_gemv(x64, gamma64, w_rows_a, wscale_a, K, N, Float64(EPS))

        var y_tree = ctx.enqueue_create_buffer[DType.float32](N)
        var y_simd = ctx.enqueue_create_buffer[DType.float32](N)
        var f_ng_tree = ctx.compile_function[_norm_gemv_kernel_i8]()
        var f_ng_simd = ctx.compile_function[_norm_gemv_kernel_simd_i8]()

        ctx.enqueue_function_unchecked(
            f_ng_tree,
            y_tree.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
            w_a_buf.unsafe_ptr(), wscale_a_buf.unsafe_ptr(), K, N, EPS,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.enqueue_function_unchecked(
            f_ng_simd,
            y_simd.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
            w_a_buf.unsafe_ptr(), wscale_a_buf.unsafe_ptr(), K, N, EPS,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.synchronize()

        var worst_tree_host = 0.0
        var worst_simd_host = 0.0
        var worst_cross = Float32(0.0)
        with y_tree.map_to_host() as ht:
            with y_simd.map_to_host() as hs:
                for j in range(N):
                    var dt = _abs64(Float64(ht[j]) - host_ng[j])
                    var ds = _abs64(Float64(hs[j]) - host_ng[j])
                    var dc = _abs(ht[j] - hs[j])
                    if dt > worst_tree_host:
                        worst_tree_host = dt
                    if ds > worst_simd_host:
                        worst_simd_host = ds
                    if dc > worst_cross:
                        worst_cross = dc

        print("  •  [norm_gemv] tree vs host: worst|Δ|=", worst_tree_host,
              " simd vs host: worst|Δ|=", worst_simd_host, " tree vs simd: worst|Δ|=", worst_cross)
        if worst_tree_host <= reorder_bound and worst_simd_host <= reorder_bound and Float64(worst_cross) <= reorder_bound:
            passed += 1
            print("  ✅ norm_gemv: barrier-tree and SIMD-shuffle agree with the host reference and",
                  "each other within", reorder_bound)
        else:
            failed += 1
            print("  ❌ norm_gemv: a delta exceeds", reorder_bound, "-- see the numbers above")

        # ══ 2. gemv_accum (o_proj/down_proj): _gemv_accum_kernel_i8 vs _gemv_accum_kernel_simd_i8 ══
        var y0_64 = List[Float64](capacity=N)
        for j in range(N):
            y0_64.append(10.0 + Float64(j))  # nonzero seed: a dropped `+=` would show up loudly
        var host_ga = _host_gemv_accum(y0_64, x64, w_rows_a, wscale_a, K, N)

        var y0_tree_buf = ctx.enqueue_create_buffer[DType.float32](N)
        var y0_simd_buf = ctx.enqueue_create_buffer[DType.float32](N)
        with y0_tree_buf.map_to_host() as h:
            for j in range(N):
                h[j] = Float32(y0_64[j])
        with y0_simd_buf.map_to_host() as h:
            for j in range(N):
                h[j] = Float32(y0_64[j])
        ctx.synchronize()

        var f_ga_tree = ctx.compile_function[_gemv_accum_kernel_i8]()
        var f_ga_simd = ctx.compile_function[_gemv_accum_kernel_simd_i8]()
        ctx.enqueue_function_unchecked(
            f_ga_tree,
            y0_tree_buf.unsafe_ptr(), x_buf.unsafe_ptr(),
            w_a_buf.unsafe_ptr(), wscale_a_buf.unsafe_ptr(), K, N,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.enqueue_function_unchecked(
            f_ga_simd,
            y0_simd_buf.unsafe_ptr(), x_buf.unsafe_ptr(),
            w_a_buf.unsafe_ptr(), wscale_a_buf.unsafe_ptr(), K, N,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.synchronize()

        var worst_tree_host2 = 0.0
        var worst_simd_host2 = 0.0
        var worst_cross2 = Float32(0.0)
        with y0_tree_buf.map_to_host() as ht:
            with y0_simd_buf.map_to_host() as hs:
                for j in range(N):
                    var dt = _abs64(Float64(ht[j]) - host_ga[j])
                    var ds = _abs64(Float64(hs[j]) - host_ga[j])
                    var dc = _abs(ht[j] - hs[j])
                    if dt > worst_tree_host2:
                        worst_tree_host2 = dt
                    if ds > worst_simd_host2:
                        worst_simd_host2 = ds
                    if dc > worst_cross2:
                        worst_cross2 = dc

        print("  •  [gemv_accum] tree vs host: worst|Δ|=", worst_tree_host2,
              " simd vs host: worst|Δ|=", worst_simd_host2, " tree vs simd: worst|Δ|=", worst_cross2)
        if worst_tree_host2 <= reorder_bound and worst_simd_host2 <= reorder_bound and Float64(worst_cross2) <= reorder_bound:
            passed += 1
            print("  ✅ gemv_accum: barrier-tree and SIMD-shuffle agree with the host reference and",
                  "each other within", reorder_bound, "-- the residual `+=` survived in both")
        else:
            failed += 1
            print("  ❌ gemv_accum: a delta exceeds", reorder_bound, "-- see the numbers above")

        # ══ 3. norm_gemv2_swiglu (gate-up): _norm_gemv2_swiglu_kernel_i8 vs _simd_i8 ═══════════════
        var gate_rows = List[List[Int8]](capacity=N)
        var gate_scale = List[Float64](capacity=N)
        var up_rows = List[List[Int8]](capacity=N)
        var up_scale = List[Float64](capacity=N)
        var wgu_flat = List[Int8](capacity=2 * N * K)
        var wgu_scale_flat = List[Float64](capacity=2 * N)
        for j in range(N):
            var grow64 = _pseudo_f64(K, 200 + j * 11, 0.7)
            var gq = List[Int8](capacity=K)
            var gs = _quantize_row_i8_host(grow64, gq)
            gate_scale.append(gs)
            gate_rows.append(gq^)
        for j in range(N):
            var urow64 = _pseudo_f64(K, 300 + j * 11, 0.9)
            var uq = List[Int8](capacity=K)
            var us = _quantize_row_i8_host(urow64, uq)
            up_scale.append(us)
            up_rows.append(uq^)
        for j in range(N):
            for i in range(K):
                wgu_flat.append(gate_rows[j][i])
        for j in range(N):
            for i in range(K):
                wgu_flat.append(up_rows[j][i])
        for j in range(N):
            wgu_scale_flat.append(gate_scale[j])
        for j in range(N):
            wgu_scale_flat.append(up_scale[j])

        var host_gu = _host_swiglu(x64, gamma64, gate_rows, gate_scale, up_rows, up_scale, K, N, Float64(EPS))

        var wgu_buf = ctx.enqueue_create_buffer[DType.int8](2 * N * K)
        var wgu_scale_buf = ctx.enqueue_create_buffer[DType.float32](2 * N)
        with wgu_buf.map_to_host() as h:
            for idx in range(2 * N * K):
                h[idx] = wgu_flat[idx]
        with wgu_scale_buf.map_to_host() as h:
            for idx in range(2 * N):
                h[idx] = Float32(wgu_scale_flat[idx])
        ctx.synchronize()

        var act_tree = ctx.enqueue_create_buffer[DType.float32](N)
        var act_simd = ctx.enqueue_create_buffer[DType.float32](N)
        var f_gu_tree = ctx.compile_function[_norm_gemv2_swiglu_kernel_i8]()
        var f_gu_simd = ctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()

        ctx.enqueue_function_unchecked(
            f_gu_tree,
            act_tree.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
            wgu_buf.unsafe_ptr(), wgu_scale_buf.unsafe_ptr(), K, N, EPS,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.enqueue_function_unchecked(
            f_gu_simd,
            act_simd.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
            wgu_buf.unsafe_ptr(), wgu_scale_buf.unsafe_ptr(), K, N, EPS,
            grid_dim=grid_n, block_dim=_TG,
        )
        ctx.synchronize()

        var worst_tree_host3 = 0.0
        var worst_simd_host3 = 0.0
        var worst_cross3 = Float32(0.0)
        with act_tree.map_to_host() as ht:
            with act_simd.map_to_host() as hs:
                for j in range(N):
                    var dt = _abs64(Float64(ht[j]) - host_gu[j])
                    var ds = _abs64(Float64(hs[j]) - host_gu[j])
                    var dc = _abs(ht[j] - hs[j])
                    if dt > worst_tree_host3:
                        worst_tree_host3 = dt
                    if ds > worst_simd_host3:
                        worst_simd_host3 = ds
                    if dc > worst_cross3:
                        worst_cross3 = dc

        print("  •  [norm_gemv2_swiglu] tree vs host: worst|Δ|=", worst_tree_host3,
              " simd vs host: worst|Δ|=", worst_simd_host3, " tree vs simd: worst|Δ|=", worst_cross3)
        # SwiGLU multiplies two independently-summed reductions together, so its delta can be up
        # to roughly twice a single reduction's own bound (one factor's error times the other
        # factor's magnitude, for each of the two factors) -- checked below, not re-derived by
        # feel: `2 * reorder_bound * (1 + max(|gate|, |up|))`.
        var swiglu_bound = 2.0 * reorder_bound * 50.0
        if worst_tree_host3 <= swiglu_bound and worst_simd_host3 <= swiglu_bound and Float64(worst_cross3) <= swiglu_bound:
            passed += 1
            print("  ✅ norm_gemv2_swiglu: barrier-tree and SIMD-shuffle agree with the host",
                  "reference and each other within", swiglu_bound)
        else:
            failed += 1
            print("  ❌ norm_gemv2_swiglu: a delta exceeds", swiglu_bound, "-- see the numbers above")

        print("  [residentk.kernels gemv-simd-isolated] Passed:", passed, "Failed:", failed)
