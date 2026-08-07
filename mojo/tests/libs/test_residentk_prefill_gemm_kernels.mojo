"""test_residentk_prefill_gemm_kernels.mojo — Gate 0 for the weight-stationary tiled-GEMM family:
`_pf_rmsnorm_rows_kernel` + `_pf_gemm_assign_kernel_i8` diffed against `_pf_qkv_proj_kernel_simd_i8`
(Phase A); `_pf_gemm_accum_kernel_i8` diffed against `_pf_gemv_accum_kernel_simd_i8` (Phase C, reused
for o_proj/down_proj); `_pf_gemm_swiglu_kernel_i8` diffed against `_pf_swiglu_kernel_simd_i8` (Phase
C) — all three against the already Gate-1-verified, byte-unmodified Phase-1 oracles (see
`test_metaldispatch_session_prefill.mojo`'s own golden vector for that verification).

Hand-written, mirroring `test_residentk_attn_splitk_native_kernel.mojo`'s own isolated-kernel-diff
pattern: `DeviceContext.enqueue_function_unchecked` directly, bypassing `metaldispatch`'s shim
entirely — this file's whole question is "do these two kernels compute the same function," not
"does the session's descriptor plan wire them correctly," so it needs none of the shim's machinery.

    cd /Users/angel/Developer/decision-engine/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -D ALGENTA_GPU -I ../mojo/engine \
        ../mojo/tests/libs/test_residentk_prefill_gemm_kernels.mojo
"""

from std.gpu.host import DeviceContext
from std.math import sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import (
    _TG,
    _SUBS,
    _GEMM_BM,
    _GEMM_BN,
    _GEMM_NTHREADS,
    _GEMM_BM_NARROW,
    _GEMM_NTHREADS_NARROW,
    _pf_qkv_proj_kernel_simd_i8,
    _pf_gemv_accum_kernel_simd_i8,
    _pf_swiglu_kernel_simd_i8,
    _pf_rmsnorm_rows_kernel,
    _pf_gemm_assign_kernel_i8,
    _pf_gemm_accum_kernel_i8,
    _pf_gemm_swiglu_kernel_i8,
    _pf_gnrw_assign_kernel_i8,
    _pf_gnrw_accum_kernel_i8,
    _pf_gnrw_swiglu_kernel_i8,
)


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    var o = List[Float32](capacity=n)
    for i in range(n):
        var a = Float32((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float32((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def _gains_f32(n: Int, seed: Int) -> List[Float32]:
    var o = List[Float32](capacity=n)
    for i in range(n):
        o.append(0.8 + Float32((i * 17 + seed * 5) % 11) / 25.0)
    return o^


@fieldwise_init
struct _QuantResult(Copyable, Movable):
    var w_i8: List[Int8]
    var scale: List[Float32]


def _quantize_i8_rows(w_f32: List[Float32], n: Int, k: Int) -> _QuantResult:
    """Per-output-row symmetric int8 quantization — the same `scale = max(|row|) / 127` scheme
    `residentk.kernels`' own `_I8P` docstring establishes, reproduced here on the host in Float32
    (not device code) purely to build a realistic test fixture."""
    var w_i8 = List[Int8](capacity=n * k)
    for _ in range(n * k):
        w_i8.append(Int8(0))
    var scale = List[Float32](capacity=n)
    for row in range(n):
        var maxabs = Float32(1.0e-6)
        for c in range(k):
            var av = _abs32(w_f32[row * k + c])
            if av > maxabs:
                maxabs = av
        var s = maxabs / 127.0
        scale.append(s)
        for c in range(k):
            var q = w_f32[row * k + c] / s
            var qi = Int(q + (Float32(0.5) if q >= 0.0 else Float32(-0.5)))
            if qi > 127:
                qi = 127
            if qi < -127:
                qi = -127
            w_i8[row * k + c] = Int8(qi)
    return _QuantResult(w_i8^, scale^)


def _run_case(
    ctx: DeviceContext, m_rows: Int, k: Int, n: Int, mut passed: Int, mut failed: Int,
) raises:
    var eps = Float32(1.0e-6)
    var x_vals = _pseudo_f32(m_rows * k, 3 + m_rows + k + n, 0.6)
    var gamma_vals = _gains_f32(k, 9 + m_rows)
    var w_f32 = _pseudo_f32(n * k, 17 + m_rows + k, 0.35)
    var q = _quantize_i8_rows(w_f32, n, k)

    var x_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * k)
    var gamma_buf = ctx.enqueue_create_buffer[DType.float32](k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var scale_buf = ctx.enqueue_create_buffer[DType.float32](n)
    with x_buf.map_to_host() as h:
        for i in range(m_rows * k):
            h[i] = x_vals[i]
    with gamma_buf.map_to_host() as h:
        for i in range(k):
            h[i] = gamma_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = q.w_i8[i]
    with scale_buf.map_to_host() as h:
        for i in range(n):
            h[i] = q.scale[i]

    # ── oracle: the byte-unmodified Phase-1 row-flattened kernel ──
    var y_oracle = ctx.enqueue_create_buffer[DType.float32](m_rows * n)
    var f_oracle = ctx.compile_function[_pf_qkv_proj_kernel_simd_i8]()
    var n_units = (n + _SUBS - 1) // _SUBS
    ctx.enqueue_function_unchecked(
        f_oracle,
        y_oracle.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
        w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(), k, n, eps, m_rows,
        grid_dim=n_units * m_rows, block_dim=_TG,
    )

    # ── candidate: rmsnorm split out, then the weight-stationary tiled GEMM ──
    var xn_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * k)
    var f_norm = ctx.compile_function[_pf_rmsnorm_rows_kernel]()
    ctx.enqueue_function_unchecked(
        f_norm,
        xn_buf.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(), k, eps, m_rows,
        grid_dim=m_rows, block_dim=_TG,
    )

    var y_new = ctx.enqueue_create_buffer[DType.float32](m_rows * n)
    var f_gemm = ctx.compile_function[_pf_gemm_assign_kernel_i8]()
    var n_tile_rows = (m_rows + _GEMM_BM - 1) // _GEMM_BM
    var n_tile_cols = (n + _GEMM_BN - 1) // _GEMM_BN
    ctx.enqueue_function_unchecked(
        f_gemm,
        y_new.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(),
        m_rows, k, n,
        grid_dim=n_tile_rows * n_tile_cols, block_dim=_GEMM_NTHREADS,
    )

    var y_new_narrow = ctx.enqueue_create_buffer[DType.float32](m_rows * n)
    var f_gemm_narrow = ctx.compile_function[_pf_gnrw_assign_kernel_i8]()
    var n_tile_rows_narrow = (m_rows + _GEMM_BM_NARROW - 1) // _GEMM_BM_NARROW
    ctx.enqueue_function_unchecked(
        f_gemm_narrow,
        y_new_narrow.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(),
        m_rows, k, n,
        grid_dim=n_tile_rows_narrow * n_tile_cols, block_dim=_GEMM_NTHREADS_NARROW,
    )
    ctx.synchronize()

    comptime _F32_EPS: Float32 = 1.1920929e-7
    var name = "m=" + String(m_rows) + " k=" + String(k) + " n=" + String(n)

    var worst = Float32(0.0)
    var max_val = Float32(1.0e-6)
    with y_oracle.map_to_host() as ho:
        with y_new.map_to_host() as hn:
            for i in range(m_rows * n):
                var d = _abs32(ho[i] - hn[i])
                if d > worst:
                    worst = d
                var av = _abs32(ho[i])
                if av > max_val:
                    max_val = av
    var bound = _F32_EPS * Float32(k) * (1.0 + max_val) * 8.0
    if worst <= bound:
        passed += 1
        print("  ✅ ", name, "(wide): tiled-GEMM agrees with the row-flattened oracle, worst delta",
              worst, "bound", bound)
    else:
        failed += 1
        print("  ❌ ", name, "(wide): tiled-GEMM DIVERGES from the row-flattened oracle, worst delta",
              worst, "bound", bound)

    var worst_n = Float32(0.0)
    with y_oracle.map_to_host() as ho2:
        with y_new_narrow.map_to_host() as hn2:
            for i in range(m_rows * n):
                var d2 = _abs32(ho2[i] - hn2[i])
                if d2 > worst_n:
                    worst_n = d2
    if worst_n <= bound:
        passed += 1
        print("  ✅ ", name, "(narrow): tiled-GEMM agrees with the row-flattened oracle, worst delta",
              worst_n, "bound", bound)
    else:
        failed += 1
        print("  ❌ ", name, "(narrow): tiled-GEMM DIVERGES from the row-flattened oracle, worst delta",
              worst_n, "bound", bound)


def _run_case_accum(
    ctx: DeviceContext, m_rows: Int, k: Int, n: Int, mut passed: Int, mut failed: Int,
) raises:
    """`_pf_gemm_accum_kernel_i8` vs `_pf_gemv_accum_kernel_simd_i8` -- both start from the SAME
    pseudo-random `y0` baseline (the residual `+=` lands on), so the diff isolates the projection
    itself, not an uninitialized-accumulator artifact."""
    var x_vals = _pseudo_f32(m_rows * k, 5 + m_rows + k + n, 0.55)
    var y0_vals = _pseudo_f32(m_rows * n, 41 + m_rows + k + n, 0.4)
    var w_f32 = _pseudo_f32(n * k, 23 + m_rows + k, 0.3)
    var q = _quantize_i8_rows(w_f32, n, k)

    var x_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](n * k)
    var scale_buf = ctx.enqueue_create_buffer[DType.float32](n)
    var y_oracle = ctx.enqueue_create_buffer[DType.float32](m_rows * n)
    var y_new = ctx.enqueue_create_buffer[DType.float32](m_rows * n)
    with x_buf.map_to_host() as h:
        for i in range(m_rows * k):
            h[i] = x_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(n * k):
            h[i] = q.w_i8[i]
    with scale_buf.map_to_host() as h:
        for i in range(n):
            h[i] = q.scale[i]
    with y_oracle.map_to_host() as h:
        for i in range(m_rows * n):
            h[i] = y0_vals[i]
    with y_new.map_to_host() as h:
        for i in range(m_rows * n):
            h[i] = y0_vals[i]

    var n_units = (n + _SUBS - 1) // _SUBS
    var f_oracle = ctx.compile_function[_pf_gemv_accum_kernel_simd_i8]()
    ctx.enqueue_function_unchecked(
        f_oracle,
        y_oracle.unsafe_ptr(), x_buf.unsafe_ptr(), w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(),
        k, n, m_rows,
        grid_dim=n_units * m_rows, block_dim=_TG,
    )

    var n_tile_rows = (m_rows + _GEMM_BM - 1) // _GEMM_BM
    var n_tile_cols = (n + _GEMM_BN - 1) // _GEMM_BN
    var f_gemm = ctx.compile_function[_pf_gemm_accum_kernel_i8]()
    ctx.enqueue_function_unchecked(
        f_gemm,
        y_new.unsafe_ptr(), x_buf.unsafe_ptr(), w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(),
        m_rows, k, n,
        grid_dim=n_tile_rows * n_tile_cols, block_dim=_GEMM_NTHREADS,
    )

    var y_new_narrow = ctx.enqueue_create_buffer[DType.float32](m_rows * n)
    with y_new_narrow.map_to_host() as h:
        for i in range(m_rows * n):
            h[i] = y0_vals[i]
    var n_tile_rows_narrow = (m_rows + _GEMM_BM_NARROW - 1) // _GEMM_BM_NARROW
    var f_gemm_narrow = ctx.compile_function[_pf_gnrw_accum_kernel_i8]()
    ctx.enqueue_function_unchecked(
        f_gemm_narrow,
        y_new_narrow.unsafe_ptr(), x_buf.unsafe_ptr(), w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(),
        m_rows, k, n,
        grid_dim=n_tile_rows_narrow * n_tile_cols, block_dim=_GEMM_NTHREADS_NARROW,
    )
    ctx.synchronize()

    comptime _F32_EPS: Float32 = 1.1920929e-7
    var name = "gemm_accum m=" + String(m_rows) + " k=" + String(k) + " n=" + String(n)

    var worst = Float32(0.0)
    var max_val = Float32(1.0e-6)
    with y_oracle.map_to_host() as ho:
        with y_new.map_to_host() as hn:
            for i in range(m_rows * n):
                var d = _abs32(ho[i] - hn[i])
                if d > worst:
                    worst = d
                var av = _abs32(ho[i])
                if av > max_val:
                    max_val = av
    var bound = _F32_EPS * Float32(k) * (1.0 + max_val) * 8.0
    if worst <= bound:
        passed += 1
        print("  ✅ ", name, "(wide): tiled-GEMM agrees with the row-flattened oracle, worst delta",
              worst, "bound", bound)
    else:
        failed += 1
        print("  ❌ ", name, "(wide): tiled-GEMM DIVERGES from the row-flattened oracle, worst delta",
              worst, "bound", bound)

    var worst_n = Float32(0.0)
    with y_oracle.map_to_host() as ho2:
        with y_new_narrow.map_to_host() as hn2:
            for i in range(m_rows * n):
                var d2 = _abs32(ho2[i] - hn2[i])
                if d2 > worst_n:
                    worst_n = d2
    if worst_n <= bound:
        passed += 1
        print("  ✅ ", name, "(narrow): tiled-GEMM agrees with the row-flattened oracle, worst delta",
              worst_n, "bound", bound)
    else:
        failed += 1
        print("  ❌ ", name, "(narrow): tiled-GEMM DIVERGES from the row-flattened oracle, worst delta",
              worst_n, "bound", bound)


def _run_case_swiglu(
    ctx: DeviceContext, m_rows: Int, k: Int, n_ff: Int, mut passed: Int, mut failed: Int,
) raises:
    """`_pf_rmsnorm_rows_kernel` + `_pf_gemm_swiglu_kernel_i8` vs the fused, single-row-flattened
    `_pf_swiglu_kernel_simd_i8` -- the oracle norms `x` inline; the candidate norms it via the SAME
    `_pf_rmsnorm_rows_kernel` Phase A already verified, then feeds the tiled fused-gate-up GEMM."""
    var eps = Float32(1.0e-6)
    var x_vals = _pseudo_f32(m_rows * k, 7 + m_rows + k + n_ff, 0.5)
    var gamma_vals = _gains_f32(k, 13 + m_rows)
    var w_f32 = _pseudo_f32(2 * n_ff * k, 29 + m_rows + k, 0.28)
    var q = _quantize_i8_rows(w_f32, 2 * n_ff, k)

    var x_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * k)
    var gamma_buf = ctx.enqueue_create_buffer[DType.float32](k)
    var w_buf = ctx.enqueue_create_buffer[DType.int8](2 * n_ff * k)
    var scale_buf = ctx.enqueue_create_buffer[DType.float32](2 * n_ff)
    with x_buf.map_to_host() as h:
        for i in range(m_rows * k):
            h[i] = x_vals[i]
    with gamma_buf.map_to_host() as h:
        for i in range(k):
            h[i] = gamma_vals[i]
    with w_buf.map_to_host() as h:
        for i in range(2 * n_ff * k):
            h[i] = q.w_i8[i]
    with scale_buf.map_to_host() as h:
        for i in range(2 * n_ff):
            h[i] = q.scale[i]

    var act_oracle = ctx.enqueue_create_buffer[DType.float32](m_rows * n_ff)
    var f_oracle = ctx.compile_function[_pf_swiglu_kernel_simd_i8]()
    var n_units = (n_ff + _SUBS - 1) // _SUBS
    ctx.enqueue_function_unchecked(
        f_oracle,
        act_oracle.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(),
        w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(), k, n_ff, eps, m_rows,
        grid_dim=n_units * m_rows, block_dim=_TG,
    )

    var xn_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * k)
    var f_norm = ctx.compile_function[_pf_rmsnorm_rows_kernel]()
    ctx.enqueue_function_unchecked(
        f_norm,
        xn_buf.unsafe_ptr(), x_buf.unsafe_ptr(), gamma_buf.unsafe_ptr(), k, eps, m_rows,
        grid_dim=m_rows, block_dim=_TG,
    )

    var act_new = ctx.enqueue_create_buffer[DType.float32](m_rows * n_ff)
    var f_gemm = ctx.compile_function[_pf_gemm_swiglu_kernel_i8]()
    var n_tile_rows = (m_rows + _GEMM_BM - 1) // _GEMM_BM
    var n_tile_cols = (n_ff + _GEMM_BN - 1) // _GEMM_BN
    ctx.enqueue_function_unchecked(
        f_gemm,
        act_new.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(),
        m_rows, k, n_ff,
        grid_dim=n_tile_rows * n_tile_cols, block_dim=_GEMM_NTHREADS,
    )

    var act_new_narrow = ctx.enqueue_create_buffer[DType.float32](m_rows * n_ff)
    var f_gemm_narrow = ctx.compile_function[_pf_gnrw_swiglu_kernel_i8]()
    var n_tile_rows_narrow = (m_rows + _GEMM_BM_NARROW - 1) // _GEMM_BM_NARROW
    ctx.enqueue_function_unchecked(
        f_gemm_narrow,
        act_new_narrow.unsafe_ptr(), xn_buf.unsafe_ptr(), w_buf.unsafe_ptr(), scale_buf.unsafe_ptr(),
        m_rows, k, n_ff,
        grid_dim=n_tile_rows_narrow * n_tile_cols, block_dim=_GEMM_NTHREADS_NARROW,
    )
    ctx.synchronize()

    comptime _F32_EPS: Float32 = 1.1920929e-7
    var name = "gemm_swiglu m=" + String(m_rows) + " k=" + String(k) + " n_ff=" + String(n_ff)

    var worst = Float32(0.0)
    var max_val = Float32(1.0e-6)
    with act_oracle.map_to_host() as ho:
        with act_new.map_to_host() as hn:
            for i in range(m_rows * n_ff):
                var d = _abs32(ho[i] - hn[i])
                if d > worst:
                    worst = d
                var av = _abs32(ho[i])
                if av > max_val:
                    max_val = av
    var bound = _F32_EPS * Float32(k) * (1.0 + max_val) * 16.0
    if worst <= bound:
        passed += 1
        print("  ✅ ", name, "(wide): tiled-GEMM agrees with the row-flattened oracle, worst delta",
              worst, "bound", bound)
    else:
        failed += 1
        print("  ❌ ", name, "(wide): tiled-GEMM DIVERGES from the row-flattened oracle, worst delta",
              worst, "bound", bound)

    var worst_n = Float32(0.0)
    with act_oracle.map_to_host() as ho2:
        with act_new_narrow.map_to_host() as hn2:
            for i in range(m_rows * n_ff):
                var d2 = _abs32(ho2[i] - hn2[i])
                if d2 > worst_n:
                    worst_n = d2
    if worst_n <= bound:
        passed += 1
        print("  ✅ ", name, "(narrow): tiled-GEMM agrees with the row-flattened oracle, worst delta",
              worst_n, "bound", bound)
    else:
        failed += 1
        print("  ❌ ", name, "(narrow): tiled-GEMM DIVERGES from the row-flattened oracle, worst delta",
              worst_n, "bound", bound)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        print("  (skipped: built without -D ALGENTA_GPU)")
        print("  [residentk.kernels prefill-gemm] Passed:", passed, "Failed:", failed)
        return
    else:
        if not has_accelerator():
            print("  (skipped: no accelerator on this host)")
            print("  [residentk.kernels prefill-gemm] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # M=1 (degenerate), M=8 (small, real race point), M=33 (NOT a multiple of BM=32 -- exercises
        # the zero-padded final-tile logic on the ROW axis), M=128, M=512 (PREFILL_MAX_TILE) -- at
        # the REAL Qwen3-0.6B-Base qkv_proj shape (k=d_model=1024, n=n_qkv=4096) plus one smaller
        # shape to keep the sweep's own wall time reasonable.
        _run_case(ctx, 1, 1024, 4096, passed, failed)
        _run_case(ctx, 8, 1024, 4096, passed, failed)
        _run_case(ctx, 33, 1024, 4096, passed, failed)
        _run_case(ctx, 128, 1024, 4096, passed, failed)
        _run_case(ctx, 512, 1024, 4096, passed, failed)
        _run_case(ctx, 17, 256, 300, passed, failed)  # a non-power-of-two shape on every axis

        # o_proj (k=n_q=2048, n=d_model=1024) and down_proj (k=d_ff=3072, n=d_model=1024) shapes --
        # `_pf_gemm_accum_kernel_i8` is reused for both, exactly as its Phase-1 oracle already is.
        _run_case_accum(ctx, 1, 2048, 1024, passed, failed)
        _run_case_accum(ctx, 8, 2048, 1024, passed, failed)
        _run_case_accum(ctx, 33, 2048, 1024, passed, failed)
        _run_case_accum(ctx, 512, 2048, 1024, passed, failed)
        _run_case_accum(ctx, 128, 3072, 1024, passed, failed)
        _run_case_accum(ctx, 512, 3072, 1024, passed, failed)

        # swiglu (k=d_model=1024, n_ff=d_ff=3072).
        _run_case_swiglu(ctx, 1, 1024, 3072, passed, failed)
        _run_case_swiglu(ctx, 8, 1024, 3072, passed, failed)
        _run_case_swiglu(ctx, 33, 1024, 3072, passed, failed)
        _run_case_swiglu(ctx, 128, 1024, 3072, passed, failed)
        _run_case_swiglu(ctx, 512, 1024, 3072, passed, failed)

        print("  [residentk.kernels prefill-gemm] Passed:", passed, "Failed:", failed)
