"""test_residentk_prefill_attn_kernels.mojo — Gate 0 for the tiled-MMA-attention plan's Phase 1:
`_pf_attn8_kernel_simd` (one online-softmax rescale per block of 8 keys) diffed against
the byte-unmodified `_pf_attn_tiled_kernel_simd` oracle (one rescale per key) — the exact recurrence
already verified on host, in Float64, against `attnk.sdpa`/`attnk.flash`, by
`benchmarks/llm_smoke/attn_block_update_probe.mojo`. This file is the GPU-side half of that same
gate: same math, now checked in Float32 on real device kernels.

Hand-written, mirroring `test_residentk_prefill_gemm_kernels.mojo`'s own isolated-kernel-diff
pattern: `DeviceContext.enqueue_function` directly, bypassing `metaldispatch`'s shim entirely — the
question here is "do these two kernels compute the same function," not "does the session's
descriptor plan wire them correctly."

    cd /Users/angel/Developer/decision-engine/mojo_env
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -D ALGENTA_GPU -I ../mojo/engine \
        ../mojo/tests/libs/test_residentk_prefill_attn_kernels.mojo

Edge cases, matching Phase 0's own host-side sweep so a bug is caught at the same granularity in
both places: `m_rows` not a multiple of the 8-key block size, a `pos_base` (KV-cache offset) that
puts some rows' causal cutoffs strictly inside a block rather than on a block boundary, `m_rows=1`
(degenerate, single-key first block), and the real Qwen3-0.6B-Base dims (`h_q=16, h_kv=8, d_head=
128`) at `PREFILL_MAX_TILE=512`.

KNOWN, EXPECTED failure at `m_rows=1, h_q=2, h_kv=1, d_head=32`: this is the exact degenerate shape
(single warp, single key) at which `_pf_attn_tiled_kernel_simd`'s own shared reduction primitive
deterministically loses lanes 0 and 1's contribution — a real, pre-existing Mojo 1.0.0b2 compiler
bug in the oracle itself, not a math error in `_pf_attn8_kernel_simd` — see `_sdpa_kernel_simd`'s
docstring and `benchmarks/llm_smoke/attn_reduction_lane_zero_bug_repro.mojo`. Both kernels inherit
it but not identically at every shape, so this ONE case reliably shows the two kernels disagree,
while both are equally "wrong" relative to true causal attention. Every other case here exercises a
production-realistic shape, where the bug's own rate (~1% of dispatches) makes an occasional,
non-reproducible failure possible but unlikely — rerun before concluding a NEW failure elsewhere in
this file is a math bug rather than another instance of the same known issue.
"""

from std.gpu.host import DeviceContext
from std.math import sqrt
from std.sys import has_accelerator
from residentk.session import RESIDENT_GPU_BUILD
from residentk.kernels import _pf_attn_tiled_kernel_simd, _pf_attn8_kernel_simd


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    var o = List[Float32](capacity=n)
    for i in range(n):
        var a = Float32((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float32((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def _run_case(
    ctx: DeviceContext, m_rows: Int, pos_base: Int, h_q: Int, h_kv: Int, d_head: Int,
    mut passed: Int, mut failed: Int,
) raises:
    var n_q = h_q * d_head
    var n_keys_total = pos_base + m_rows
    var scale = Float32(1.0) / sqrt(Float32(d_head))

    var q_vals = _pseudo_f32(m_rows * n_q, 3 + m_rows + pos_base, 0.6)
    var k_vals = _pseudo_f32(n_keys_total * h_kv * d_head, 11 + m_rows + pos_base, 0.5)
    var v_vals = _pseudo_f32(n_keys_total * h_kv * d_head, 29 + m_rows + pos_base, 0.4)

    var q_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * n_q)
    var k_buf = ctx.enqueue_create_buffer[DType.float32](n_keys_total * h_kv * d_head)
    var v_buf = ctx.enqueue_create_buffer[DType.float32](n_keys_total * h_kv * d_head)
    var out_oracle = ctx.enqueue_create_buffer[DType.float32](m_rows * n_q)
    var out_block8 = ctx.enqueue_create_buffer[DType.float32](m_rows * n_q)
    with q_buf.map_to_host() as h:
        for i in range(m_rows * n_q):
            h[i] = q_vals[i]
    with k_buf.map_to_host() as h:
        for i in range(n_keys_total * h_kv * d_head):
            h[i] = k_vals[i]
    with v_buf.map_to_host() as h:
        for i in range(n_keys_total * h_kv * d_head):
            h[i] = v_vals[i]

    var grid = h_q * m_rows
    var f_oracle = ctx.compile_function[_pf_attn_tiled_kernel_simd]()
    ctx.enqueue_function(
        f_oracle,
        out_oracle.unsafe_ptr(), q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        pos_base, h_q, h_kv, d_head, scale, m_rows,
        grid_dim=grid, block_dim=d_head,
    )

    var f_block8 = ctx.compile_function[_pf_attn8_kernel_simd]()
    ctx.enqueue_function(
        f_block8,
        out_block8.unsafe_ptr(), q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        pos_base, h_q, h_kv, d_head, scale, m_rows,
        grid_dim=grid, block_dim=d_head,
    )
    ctx.synchronize()

    comptime _F32_EPS: Float32 = 1.1920929e-7
    var name = "m_rows=" + String(m_rows) + " pos_base=" + String(pos_base) + " h_q=" + String(h_q) + " h_kv=" + String(h_kv) + " d_head=" + String(d_head)

    var worst = Float32(0.0)
    var worst_i = -1
    var max_val = Float32(1.0e-6)
    with out_oracle.map_to_host() as ho:
        with out_block8.map_to_host() as hn:
            for i in range(m_rows * n_q):
                var d = _abs32(ho[i] - hn[i])
                if d > worst:
                    worst = d
                    worst_i = i
                var av = _abs32(ho[i])
                if av > max_val:
                    max_val = av
    # Same shape of bound `test_residentk_prefill_gemm_kernels.mojo` uses: scaled by the reduction
    # length (here, the number of keys, since that is how many terms accumulate into `o`/`denom`)
    # and by the largest output magnitude, with slack for the block form's different summation order.
    var bound = _F32_EPS * Float32(n_keys_total) * (1.0 + max_val) * 8.0
    if worst <= bound:
        passed += 1
        print("  ✅ ", name, ": block-of-8 agrees with the per-key oracle, worst delta", worst, "bound", bound)
    else:
        failed += 1
        print(
            "  ❌ ", name, ": block-of-8 DIVERGES from the per-key oracle, worst delta", worst, "bound", bound,
            " at flat index", worst_i, "(h=", worst_i // d_head, "e=", worst_i % d_head, ")",
        )


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    @parameter
    if not RESIDENT_GPU_BUILD:
        print("  (skipped: built without -D ALGENTA_GPU)")
        print("  [residentk.kernels prefill-attn block8] Passed:", passed, "Failed:", failed)
        return
    else:
        if not has_accelerator():
            print("  (skipped: no accelerator on this host)")
            print("  [residentk.kernels prefill-attn block8] Passed:", passed, "Failed:", failed)
            return

        var ctx = DeviceContext()

        # Small dims first, cheap to reason about by hand if something breaks.
        _run_case(ctx, 1, 0, 2, 1, 32, passed, failed)          # degenerate: single row, single key
        _run_case(ctx, 8, 0, 2, 1, 32, passed, failed)           # exactly one block, row 7 has 8 keys
        _run_case(ctx, 9, 0, 2, 1, 32, passed, failed)           # row 8 straddles block boundary
        _run_case(ctx, 20, 5, 2, 1, 32, passed, failed)          # KV-cache offset, mid-block cutoffs
        _run_case(ctx, 37, 0, 2, 1, 32, passed, failed)          # not a multiple of 8

        # Real Qwen3-0.6B-Base dims: h_q=16, h_kv=8 (GQA g=2), d_head=128.
        _run_case(ctx, 1, 0, 16, 8, 128, passed, failed)
        _run_case(ctx, 8, 0, 16, 8, 128, passed, failed)
        _run_case(ctx, 17, 37, 16, 8, 128, passed, failed)      # non-8-aligned tile, nonzero offset
        _run_case(ctx, 33, 0, 16, 8, 128, passed, failed)
        _run_case(ctx, 128, 0, 16, 8, 128, passed, failed)
        _run_case(ctx, 512, 0, 16, 8, 128, passed, failed)      # PREFILL_MAX_TILE
        _run_case(ctx, 512, 511, 16, 8, 128, passed, failed)    # PREFILL_MAX_TILE, deep KV-cache offset

        print("  [residentk.kernels prefill-attn block8] Passed:", passed, "Failed:", failed)
