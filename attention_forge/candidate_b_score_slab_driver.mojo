"""attention_forge.candidate_b_score_slab_driver -- forces codegen of all six
`candidate_b_score_slab` kernels and checks all three sub-variants (B1/B2/B3) two ways, following
`parity_replica_driver.mojo`'s own established pattern exactly:

  1. Correctness against `attnk.sdpa.sdpa_forward_flat` at a sweep of shapes (tiny aligned, ragged
     K, nonzero causal offset/KV-cache continuation, real Qwen3-0.6B-Base dims, and a full
     256-token single-shot prefill). Q/K/V are narrowed to Float16 first, then that SAME narrowed
     value is what the CPU oracle consumes.
  2. A 1,000-dispatch determinism soak on the real-Qwen3-dims shape, run separately for each of
     B1/B2/B3 (three independent soaks, since they are three genuinely different kernel
     sequences, not one kernel run three times).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge -I ../mojo/engine \
      ../attention_forge/candidate_b_score_slab_driver.mojo

Candidate B is scoped to `pos_base=0`/short-prompt regimes by the tournament plan, but this driver
still exercises a nonzero-offset (KV-cache-continuation) shape because the general task
requirement calls for one, and the kernels above accept `pos_base` as a genuine parameter --
nothing in their causal-visibility math assumes `pos_base=0`, only the per-lane softmax register
cap of 16 slots assumes `n_tok_k <= 512`, which every shape below respects.

Each helper below (`_run_b1`/`_run_b2`/`_run_b3`) allocates its OWN device buffers and does its OWN
host-side error accumulation inline, rather than returning `DeviceBuffer` values across function
boundaries -- every other Mojo probe/driver in this codebase (`parity_replica_driver.mojo`,
`mma_forge/probes/correctness_probe*.mojo`) follows the same discipline; `DeviceBuffer` is not
spelled out as an explicit cross-function type anywhere in this tree, and attempting to do so here
(an earlier draft of this file) hit a real compile error (`'DeviceContext' value has no attribute
'DeviceBuffer'` -- the type is not nested under `DeviceContext` the way it read at first).
"""
from max.gpu.host import DeviceContext
from attnk.contract import ATTN_OK
from attnk.mask import mask_causal_flat
from attnk.sdpa import sdpa_forward_flat
from candidate_b_score_slab import (
    _score_slab_qk_kernel,
    _b1_softmax_kernel,
    _b1_pv_kernel,
    _b2_stats_kernel,
    _b2_pv_kernel,
    _b3_fused_kernel,
)


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f16(n: Int, seed: Int) -> List[Float64]:
    """Same deterministic generator convention as `parity_replica_driver.mojo`'s `_pseudo_f16`."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float16(raw)))
    return o^


def _worst_ratio(got_list: List[Float32], want: List[Float64], n: Int) -> Float64:
    var worst = 0.0
    for i in range(n):
        var got = Float64(got_list[i])
        var w = want[i]
        var diff = _abs64(got - w)
        var allowed = 5.0e-2 * (1.0 + _abs64(w))
        var ratio = diff / allowed
        if ratio > worst:
            worst = ratio
    return worst


def _run_b1(
    ctx: DeviceContext,
    q64: List[Float64], k64: List[Float64], v64: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, offset: Int,
) raises -> Tuple[List[Float32], List[Float32]]:
    """QK -> B1-softmax -> B1-PV. Returns (flat out, flat lse), copied to host."""
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(v64[i])

    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * h_q
    var scores_buf = ctx.enqueue_create_buffer[DType.float16](h_q * n_tok_q * n_tok_k)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    with out_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float32(-999.0)

    ctx.enqueue_function[_score_slab_qk_kernel](
        scores_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset),
        grid_dim=grid, block_dim=128,
    )
    ctx.enqueue_function[_b1_softmax_kernel](
        scores_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(offset),
        grid_dim=grid, block_dim=128,
    )
    ctx.enqueue_function[_b1_pv_kernel](
        out_buf.unsafe_ptr(),
        scores_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv), Int64(offset),
        grid_dim=grid, block_dim=128,
    )
    ctx.synchronize()

    var out_host = List[Float32](capacity=n_tok_q * h_q * d)
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q * d):
            out_host.append(ho[i])
    var lse_host = List[Float32](capacity=h_q * n_tok_q)
    with lse_buf.map_to_host() as hl:
        for i in range(h_q * n_tok_q):
            lse_host.append(hl[i])
    return (out_host^, lse_host^)


def _run_b2(
    ctx: DeviceContext,
    q64: List[Float64], k64: List[Float64], v64: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, offset: Int,
) raises -> Tuple[List[Float32], List[Float32]]:
    """QK -> B2-stats -> B2-PV. Returns (flat out, flat lse), copied to host."""
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(v64[i])

    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * h_q
    var scores_buf = ctx.enqueue_create_buffer[DType.float16](h_q * n_tok_q * n_tok_k)
    var stats_m_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    var stats_linv_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    with out_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float32(-999.0)

    ctx.enqueue_function[_score_slab_qk_kernel](
        scores_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset),
        grid_dim=grid, block_dim=128,
    )
    ctx.enqueue_function[_b2_stats_kernel](
        scores_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        stats_m_buf.unsafe_ptr(), stats_linv_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(offset),
        grid_dim=grid, block_dim=128,
    )
    ctx.enqueue_function[_b2_pv_kernel](
        out_buf.unsafe_ptr(),
        scores_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        stats_m_buf.unsafe_ptr(), stats_linv_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv), Int64(offset),
        grid_dim=grid, block_dim=128,
    )
    ctx.synchronize()

    var out_host = List[Float32](capacity=n_tok_q * h_q * d)
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q * d):
            out_host.append(ho[i])
    var lse_host = List[Float32](capacity=h_q * n_tok_q)
    with lse_buf.map_to_host() as hl:
        for i in range(h_q * n_tok_q):
            lse_host.append(hl[i])
    return (out_host^, lse_host^)


def _run_b3(
    ctx: DeviceContext,
    q64: List[Float64], k64: List[Float64], v64: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, offset: Int,
) raises -> Tuple[List[Float32], List[Float32]]:
    """Single fused B3 dispatch. Returns (flat out, flat lse), copied to host."""
    var q_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_q * h_q * d)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](n_tok_k * h_kv * d)
    with q_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(k64[i])
    with v_buf.map_to_host() as h:
        for i in range(n_tok_k * h_kv * d):
            h[i] = Float16(v64[i])

    var n_q_blocks = (n_tok_q + 7) // 8
    var grid = n_q_blocks * h_q
    var out_buf = ctx.enqueue_create_buffer[DType.float32](n_tok_q * h_q * d)
    var lse_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_tok_q)
    with out_buf.map_to_host() as h:
        for i in range(n_tok_q * h_q * d):
            h[i] = Float32(-999.0)

    ctx.enqueue_function[_b3_fused_kernel](
        out_buf.unsafe_ptr(), lse_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        Int64(n_tok_q), Int64(n_tok_k), Int64(h_q), Int64(h_kv),
        Float32(scale), Int64(offset),
        grid_dim=grid, block_dim=128,
    )
    ctx.synchronize()

    var out_host = List[Float32](capacity=n_tok_q * h_q * d)
    with out_buf.map_to_host() as ho:
        for i in range(n_tok_q * h_q * d):
            out_host.append(ho[i])
    var lse_host = List[Float32](capacity=h_q * n_tok_q)
    with lse_buf.map_to_host() as hl:
        for i in range(h_q * n_tok_q):
            lse_host.append(hl[i])
    return (out_host^, lse_host^)


def test_correctness(
    ctx: DeviceContext, name: String,
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int,
) raises -> Bool:
    if d != 128:
        print("  [", name, "] SKIPPED: candidate B is specialized to d_qk=d_v=128 (Qwen3-0.6B-Base)")
        return True

    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)

    var cm = mask_causal_flat(n_tok_q, n_tok_k, offset)
    if cm.status != ATTN_OK:
        print("  [", name, "] mask build FAILED")
        return False

    var scale = 1.0 / Float64(d) ** 0.5
    var oracle = sdpa_forward_flat(q64, k64, v64, cm.bias, n_tok_q, n_tok_k, h_q, h_kv, d, scale, True)
    if oracle.status != ATTN_OK:
        print("  [", name, "] oracle FAILED, status=", oracle.status)
        return False

    var all_ok = True

    var r1 = _run_b1(ctx, q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset)
    var wo1 = _worst_ratio(r1[0], oracle.out, n_tok_q * h_q * d)
    var wl1 = _worst_ratio(r1[1], oracle.lse, h_q * n_tok_q)
    var ok1 = wo1 <= 1.0 and wl1 <= 1.0
    print("  [", name, "/ B1 ] worst-ratio out=", wo1, " lse=", wl1, "  ", "OK" if ok1 else "MISMATCH")
    all_ok = ok1 and all_ok

    var r2 = _run_b2(ctx, q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset)
    var wo2 = _worst_ratio(r2[0], oracle.out, n_tok_q * h_q * d)
    var wl2 = _worst_ratio(r2[1], oracle.lse, h_q * n_tok_q)
    var ok2 = wo2 <= 1.0 and wl2 <= 1.0
    print("  [", name, "/ B2 ] worst-ratio out=", wo2, " lse=", wl2, "  ", "OK" if ok2 else "MISMATCH")
    all_ok = ok2 and all_ok

    var r3 = _run_b3(ctx, q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset)
    var wo3 = _worst_ratio(r3[0], oracle.out, n_tok_q * h_q * d)
    var wl3 = _worst_ratio(r3[1], oracle.lse, h_q * n_tok_q)
    var ok3 = wo3 <= 1.0 and wl3 <= 1.0
    print("  [", name, "/ B3 ] worst-ratio out=", wo3, " lse=", wl3, "  ", "OK" if ok3 else "MISMATCH")
    all_ok = ok3 and all_ok

    return all_ok


def _soak_variant(
    ctx: DeviceContext, vname: String,
    q64: List[Float64], k64: List[Float64], v64: List[Float64],
    n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int,
    scale: Float64, offset: Int, n_runs: Int, variant: Int,
) raises -> Bool:
    var first = List[Float32](capacity=n_tok_q * h_q * d)
    var worst_flip = 0
    for run in range(n_runs):
        var out: List[Float32]
        if variant == 0:
            var r = _run_b1(ctx, q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset)
            out = r[0].copy()
        elif variant == 1:
            var r2 = _run_b2(ctx, q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset)
            out = r2[0].copy()
        else:
            var r3 = _run_b3(ctx, q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset)
            out = r3[0].copy()

        if run == 0:
            for i in range(n_tok_q * h_q * d):
                first.append(out[i])
        else:
            for i in range(n_tok_q * h_q * d):
                if out[i] != first[i]:
                    worst_flip += 1

    var ok = worst_flip == 0
    print("  determinism soak [", vname, "]: n_runs=", n_runs, " mismatching-element-dispatches=", worst_flip,
          "  ", "OK" if ok else "NONDETERMINISTIC")
    return ok


def test_determinism_soak(
    ctx: DeviceContext, n_tok_q: Int, n_tok_k: Int, h_q: Int, h_kv: Int, d: Int, offset: Int, n_runs: Int,
) raises -> Bool:
    var q64 = _pseudo_f16(n_tok_q * h_q * d, 3)
    var k64 = _pseudo_f16(n_tok_k * h_kv * d, 11)
    var v64 = _pseudo_f16(n_tok_k * h_kv * d, 29)
    var scale = 1.0 / Float64(d) ** 0.5

    var all_ok = True
    all_ok = _soak_variant(ctx, "B1", q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset, n_runs, 0) and all_ok
    all_ok = _soak_variant(ctx, "B2", q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset, n_runs, 1) and all_ok
    all_ok = _soak_variant(ctx, "B3", q64, k64, v64, n_tok_q, n_tok_k, h_q, h_kv, d, scale, offset, n_runs, 2) and all_ok
    return all_ok


def main() raises:
    var ctx = DeviceContext()
    var all_ok = True

    print("=== Candidate B (triangular score-slab): correctness vs attnk.sdpa, B1/B2/B3 ===")
    all_ok = test_correctness(ctx, "tiny aligned", 8, 64, 2, 1, 128, 0) and all_ok
    all_ok = test_correctness(ctx, "tiny ragged K", 8, 37, 2, 1, 128, 0) and all_ok
    all_ok = test_correctness(ctx, "two q-blocks, offset", 16, 96, 2, 1, 128, 13) and all_ok
    all_ok = test_correctness(ctx, "real Qwen3-0.6B-Base dims, m=17 offset=37", 17, 130, 16, 8, 128, 37) and all_ok
    all_ok = test_correctness(ctx, "real dims, 256-token single-shot prefill", 256, 256, 16, 8, 128, 0) and all_ok

    print("")
    print("=== 1,000-dispatch determinism soak (real dims, single-shot prefill), per sub-variant ===")
    all_ok = test_determinism_soak(ctx, 256, 256, 16, 8, 128, 0, 1000) and all_ok

    print("")
    if all_ok:
        print("CANDIDATE B (score slab, B1/B2/B3): PASS (correct vs CPU oracle, deterministic over 1,000 dispatches each)")
    else:
        print("CANDIDATE B (score slab, B1/B2/B3): FAIL")
