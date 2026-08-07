"""attn_reduction_lane_zero_bug_repro.mojo — minimal repro for a real Mojo 1.0.0b2 compiler bug in
the two-level SIMD-shuffle reduction shared by `residentk.kernels._pf_attn_tiled_kernel_simd`
(batched prefill attention) and `_sdpa_kernel_simd` (decode attention, byte-identical math). Found
while gating Phase 1 of the tiled-MMA-attention plan (`_pf_attn8_kernel_simd`): that new kernel
showed a rare divergence from the byte-unmodified oracle, which traced back to the ORACLE itself,
not anything new -- both kernels are affected, and neither was modified to produce this.

Hand-written, throwaway (not registered in `generate_mojo_tests.py`), same category as
`sdpa_simd_reduce_probe.mojo`/`debug_narrow_accum.mojo` before it: kept as a repro for whoever
investigates this upstream, not a golden-vector suite. Run with the pinned toolchain:

    cd mojo_env && DEVELOPER_DIR=/Applications/Xcode-<version>.app/Contents/Developer \\
      pixi run mojo run -D ALGENTA_GPU -I ../mojo/engine \\
        ../benchmarks/llm_smoke/attn_reduction_lane_zero_bug_repro.mojo

What the bug is
------------------
The shared reduction, once per key: each of the `d_head` threads computes `partial = qv * kv[e]`;
`warp.sum` folds it to one total per 32-lane SIMD-group; lane 0 of each group writes that group's
total to a small shared array `grp[]`; a barrier; every thread sums `grp[]`'s few entries into `s`
(now uniform across all threads); a second barrier; then each thread updates its own online-softmax
accumulator: `o = o*corr + w*kv[e]`.

At `d_head=32` (one SIMD-group, `n_keys=1`, the smallest possible dispatch), lanes 0 and 1
DETERMINISTICALLY compute `o=0.0` instead of the correct `kv[e]`, on every single run -- while every
other lane (2 through 31) is exactly correct, every time. Confirmed via internal-state dumps
(section 1 below): `s`, `corr`, `w` are all correctly uniform across every lane (including 0 and 1)
at the point they are used, and the dot-product SUM they feed into (`group_total`, computed via a
warp-wide reduction that necessarily includes lanes 0 and 1's own contributions) is also correct --
so the individual `qv[e]*kv[e]` terms for e=0,1 were read correctly once, earlier, for the reduction,
but the SECOND read of the identical `kv[e]` a few lines later (`w * kv[e]` in the accumulate step)
silently loses its contribution specifically for the two lowest lane indices. This is the exact
"zero-contribution" signature already documented on `_pf_gnrw_accum_kernel_i8` in
`residentk/kernels.mojo` for the (dead-code) narrow-tile scalar GEMM path -- same toolchain, same
bug family, but this instance lives in the CURRENTLY-DISPATCHED production attention path.

At the real Qwen3-0.6B-Base shape (`d_head=128`, four SIMD-groups, `h_q=16`, `h_kv=8`,
`m_rows=512`), section 2 below shows the same class of failure, but rare (~1% of dispatches,
random lane/position each time rather than always lanes 0/1) -- consistent with a real,
occupancy/scheduling-sensitive codegen bug whose probability of manifesting depends on the exact
launch configuration, worse (deterministic) at the most degenerate shape and rare at production
scale. Reproduced by dispatching the SAME compiled kernel twice with IDENTICAL inputs and diffing
the two outputs against each other -- no oracle-vs-candidate comparison involved, so this is the
kernel's own nondeterminism, not a diff artifact.
"""
from std.gpu.host import DeviceContext
from std.gpu import barrier, block_idx, thread_idx
from std.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as warp_sum
from std.gpu.primitives.id import lane_id, warp_id
from std.gpu.globals import WARP_SIZE
from std.memory import stack_allocation
from std.math import exp, sqrt
from std.sys import has_accelerator
from std.builtin.type_aliases import MutAnyOrigin
from residentk.kernels import _pf_attn_tiled_kernel_simd, _sdpa_kernel_simd

comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _IP = UnsafePointer[Int32, origin=MutAnyOrigin]
comptime _D_HEAD_MIN: Int = 32
comptime _NEG_HUGE: Float32 = -3.0e38


def _pseudo_f32(n: Int, seed: Int, amp: Float32) -> List[Float32]:
    var o = List[Float32](capacity=n)
    for i in range(n):
        var a = Float32((i * 37 + seed * 101) % 61) / 30.0 - 1.0
        var b = Float32((i * 13 + seed * 7) % 29) / 14.0 - 1.0
        o.append(amp * (a + 0.5 * b))
    return o^


def _abs32(x: Float32) -> Float32:
    return -x if x < 0.0 else x


# ============================================================================
# Section 1: minimal, deterministic repro -- a standalone copy of the shared reduction, isolated
# from the rest of the kernel, at the single-SIMD-group / single-key shape.
# ============================================================================


def _minimal_kernel(
    attn_out: _FP, qv_buf: _FP, kv_buf: _FP,
    dbg_grouptotal: _FP, dbg_s: _FP, dbg_corr: _FP, dbg_w: _FP,
):
    comptime _SIMD_GROUPS: Int = 8
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var e = Int(thread_idx.x)
    var qv = qv_buf[e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = _D_HEAD_MIN // WARP_SIZE

    var mx = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    var partial = qv * kv_buf[e]
    var group_total = warp_sum(partial)
    if lane == 0:
        grp[grp_id] = group_total
    barrier()
    var s = Float32(0.0)
    for g in range(n_groups):
        s += grp[g]
    barrier()

    var nm = mx if mx > s else s
    var corr = exp(mx - nm)
    var w = exp(s - nm)
    o = o * corr + w * kv_buf[e]
    denom = denom * corr + w

    attn_out[e] = o / denom
    dbg_grouptotal[e] = group_total
    dbg_s[e] = s
    dbg_corr[e] = corr
    dbg_w[e] = w


def _run_minimal_repro(ctx: DeviceContext) raises:
    print("--- Section 1: minimal repro, d_head=32, n_keys=1 -- lanes 0,1 vs the rest ---")
    var qv = _pseudo_f32(_D_HEAD_MIN, 4, 0.6)
    var kv = _pseudo_f32(_D_HEAD_MIN, 12, 0.5)

    var q_buf = ctx.enqueue_create_buffer[DType.float32](_D_HEAD_MIN)
    var k_buf = ctx.enqueue_create_buffer[DType.float32](_D_HEAD_MIN)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](_D_HEAD_MIN)
    var dbg_grouptotal = ctx.enqueue_create_buffer[DType.float32](_D_HEAD_MIN)
    var dbg_s = ctx.enqueue_create_buffer[DType.float32](_D_HEAD_MIN)
    var dbg_corr = ctx.enqueue_create_buffer[DType.float32](_D_HEAD_MIN)
    var dbg_w = ctx.enqueue_create_buffer[DType.float32](_D_HEAD_MIN)
    with q_buf.map_to_host() as h:
        for i in range(_D_HEAD_MIN):
            h[i] = qv[i]
    with k_buf.map_to_host() as h:
        for i in range(_D_HEAD_MIN):
            h[i] = kv[i]

    var f = ctx.compile_function[_minimal_kernel]()
    ctx.enqueue_function(
        f, out_buf.unsafe_ptr(), q_buf.unsafe_ptr(), k_buf.unsafe_ptr(),
        dbg_grouptotal.unsafe_ptr(), dbg_s.unsafe_ptr(), dbg_corr.unsafe_ptr(), dbg_w.unsafe_ptr(),
        grid_dim=1, block_dim=_D_HEAD_MIN,
    )
    ctx.synchronize()

    var n_wrong = 0
    with out_buf.map_to_host() as ho:
        with dbg_s.map_to_host() as hs:
            with dbg_corr.map_to_host() as hc:
                with dbg_w.map_to_host() as hw:
                    for e in range(_D_HEAD_MIN):
                        var expect = kv[e]  # n_keys=1: correct output is always kv[e] exactly
                        var wrong = _abs32(ho[e] - expect) > 1.0e-6
                        if wrong:
                            n_wrong += 1
                        print(
                            "  e=", e, " s=", hs[e], " corr=", hc[e], " w=", hw[e],
                            " out=", ho[e], " expect=", expect, " ", "WRONG" if wrong else "ok",
                        )
    print("  lanes wrong:", n_wrong, "/", _D_HEAD_MIN, "(expect exactly 2: lanes 0 and 1)")
    print("")


# ============================================================================
# Section 2: production-scale self-race -- dispatch the byte-unmodified prefill and decode oracle
# kernels each TWICE with identical inputs, diff the two outputs against each other. Any nonzero
# diff is the kernel disagreeing with itself -- proof this is not a diff-against-candidate artifact.
# ============================================================================


def _run_prefill_self_race(ctx: DeviceContext, m_rows: Int, n_reps: Int) raises:
    var pos_base = 0
    var h_q = 16
    var h_kv = 8
    var d_head = 128
    var n_q = h_q * d_head
    var scale = Float32(1.0) / sqrt(Float32(d_head))
    var n_keys_total = pos_base + m_rows

    var q_vals = _pseudo_f32(m_rows * n_q, 3 + m_rows, 0.6)
    var k_vals = _pseudo_f32(n_keys_total * h_kv * d_head, 11 + m_rows, 0.5)
    var v_vals = _pseudo_f32(n_keys_total * h_kv * d_head, 29 + m_rows, 0.4)

    var q_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * n_q)
    var k_buf = ctx.enqueue_create_buffer[DType.float32](n_keys_total * h_kv * d_head)
    var v_buf = ctx.enqueue_create_buffer[DType.float32](n_keys_total * h_kv * d_head)
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
    var f = ctx.compile_function[_pf_attn_tiled_kernel_simd]()
    var n_ok = 0
    var n_bad = 0
    for _ in range(n_reps):
        var out_a = ctx.enqueue_create_buffer[DType.float32](m_rows * n_q)
        var out_b = ctx.enqueue_create_buffer[DType.float32](m_rows * n_q)
        ctx.enqueue_function(
            f, out_a.unsafe_ptr(), q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            pos_base, h_q, h_kv, d_head, scale, m_rows, grid_dim=grid, block_dim=d_head,
        )
        ctx.enqueue_function(
            f, out_b.unsafe_ptr(), q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            pos_base, h_q, h_kv, d_head, scale, m_rows, grid_dim=grid, block_dim=d_head,
        )
        ctx.synchronize()
        var worst = Float32(0.0)
        with out_a.map_to_host() as ha:
            with out_b.map_to_host() as hb:
                for i in range(m_rows * n_q):
                    var d = _abs32(ha[i] - hb[i])
                    if d > worst:
                        worst = d
        if worst == 0.0:
            n_ok += 1
        else:
            n_bad += 1
    print(
        "  _pf_attn_tiled_kernel_simd (prefill) vs itself, m_rows=", m_rows,
        " h_q=16 h_kv=8 d_head=128: ok=", n_ok, " bad=", n_bad, "/", n_reps,
    )


def main() raises:
    if not has_accelerator():
        print("no accel")
        return
    var ctx = DeviceContext()
    _run_minimal_repro(ctx)
    print("--- Section 2: production-scale self-race, byte-unmodified prefill oracle ---")
    _run_prefill_self_race(ctx, 512, 60)
