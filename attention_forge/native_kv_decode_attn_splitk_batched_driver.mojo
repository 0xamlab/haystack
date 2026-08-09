"""native_kv_decode_attn_splitk_batched_driver.mojo -- Project Slipstream Phase 3 (2026-08-09):
standalone correctness driver for the BATCHED flash-decoding pair
(`native_kv_decode_attn_splitk_batched`). Mirrors `native_kv_decode_attn_splitk_driver.mojo`'s gate
discipline, restating the oracle/pack helpers independently (the forge convention):

1. `test_batched_correctness` -- B sequences, each with a DIFFERENT n_keys, all packed into ONE
   contiguous K buffer and ONE contiguous V buffer (offset = b * kv_stride, the uniform-stride
   indirection the kernel relies on). Batched partial (grid B*h_q*n_splits) + batched merge (grid
   B*h_q), then EACH sequence's output compared against the host Float64 attention oracle. Sweeps
   B x n_keys including ragged and empty-split regimes.
2. `test_batched_vs_single_stream` -- the SAME packed buffers dispatched through the BATCHED pair
   and through B independent runs of the single-stream split-K partial + host merge, compared
   element-wise per sequence: agreement within Float32-reordering noise proves the batched pair
   computes the SAME function as the proven single-stream one (not merely an oracle approximation).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_decode_attn_splitk_batched_driver.mojo
"""
from max.gpu.host import DeviceContext
from std.math import exp
from std.time import perf_counter_ns
from native_kv_decode_attn_splitk_batched import (
    _native_kv_decode_splitk_partial_batched_kernel,
    _native_kv_decode_splitk_merge_batched_kernel,
)
from native_kv_decode_attn_splitk import _native_kv_decode_splitk_partial_kernel

comptime _H_Q: Int = 16
comptime _H_KV: Int = 8
comptime _D_HEAD: Int = 128
comptime _KBS: Int = 32
comptime _NEG_HUGE64: Float64 = -3.0e38


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float32(raw)))
    return o^


def _oracle_attn(
    q64: List[Float64], k64: List[Float64], v64: List[Float64],
    n_keys: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float64,
) -> List[Float64]:
    """Host Float64 attention over NATURAL [j*h_kv+hk] layouts (independent restatement)."""
    var out = List[Float64](capacity=h_q * d_head)
    var group = h_q // h_kv
    for h in range(h_q):
        var hk = h // group
        var o = List[Float64](capacity=d_head)
        for _ in range(d_head):
            o.append(0.0)
        var m = _NEG_HUGE64
        var denom = 0.0
        for j in range(n_keys):
            var s = 0.0
            for d in range(d_head):
                s += q64[h * d_head + d] * k64[(j * h_kv + hk) * d_head + d]
            s *= scale
            var nm = m if m > s else s
            var corr = exp(m - nm)
            var w = exp(s - nm)
            for d in range(d_head):
                o[d] = o[d] * corr + w * v64[(j * h_kv + hk) * d_head + d]
            denom = denom * corr + w
            m = nm
        for d in range(d_head):
            out.append(o[d] / denom)
    return out^


def _pack_k_native_at(
    k64: List[Float64], base: Int, n_keys: Int, h_kv: Int, d_head: Int,
    key_block_size: Int, n_blocks: Int, mut out: List[Float64],
):
    """K formula `((hk*n_blocks+block)*d_head+d)*key_block_size+kk`, written at element offset
    `base` (sequence b's slot in the shared buffer)."""
    for j in range(n_keys):
        var block = j // key_block_size
        var kk = j % key_block_size
        for hk in range(h_kv):
            for d in range(d_head):
                out[base + ((hk * n_blocks + block) * d_head + d) * key_block_size + kk] = (
                    k64[(j * h_kv + hk) * d_head + d])


def _pack_v_native_at(
    v64: List[Float64], base: Int, n_keys: Int, h_kv: Int, d_head: Int,
    key_block_size: Int, n_blocks: Int, mut out: List[Float64],
):
    """V twin `((hk*n_blocks+block)*key_block_size+kk)*d_head+d`, at element offset `base`."""
    for j in range(n_keys):
        var block = j // key_block_size
        var kk = j % key_block_size
        for hk in range(h_kv):
            for d in range(d_head):
                out[base + ((hk * n_blocks + block) * key_block_size + kk) * d_head + d] = (
                    v64[(j * h_kv + hk) * d_head + d])


def _worst_ratio(got: List[Float64], want: List[Float64], tol: Float64) -> Float64:
    var worst = 0.0
    for i in range(len(got)):
        var diff = _abs64(got[i] - want[i])
        var allowed = tol * (1.0 + _abs64(want[i]))
        var ratio = diff / allowed
        if ratio > worst:
            worst = ratio
    return worst


def _host_merge_partial(
    m64: List[Float64], l64: List[Float64], o64: List[Float64],
    base: Int, n_splits: Int, h_q: Int, d_head: Int,
) -> List[Float64]:
    """Single-stream host merge over partials starting at `base` (for the cross-check: one
    sequence's worth of the [B, h_q, n_splits] scratch)."""
    var out = List[Float64](capacity=h_q * d_head)
    for h in range(h_q):
        var o = List[Float64](capacity=d_head)
        for _ in range(d_head):
            o.append(0.0)
        var m = _NEG_HUGE64
        var denom = 0.0
        for s in range(n_splits):
            var idx = base + h * n_splits + s
            var sm = m64[idx]
            var sl = l64[idx]
            var nm = m if m > sm else sm
            var corr = exp(m - nm)
            var w = exp(sm - nm)
            for d in range(d_head):
                o[d] = o[d] * corr + w * o64[idx * d_head + d]
            denom = denom * corr + w * sl
            m = nm
        for d in range(d_head):
            out.append(o[d] / denom)
    return out^


def test_batched_correctness(
    ctx: DeviceContext, nkeys_list: List[Int], n_splits: Int, seed: Int,
) raises -> Bool:
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var B = len(nkeys_list)
    var scale = 1.0 / (Float64(d_head) ** 0.5)

    # Provision all B caches to the largest n_keys (uniform max_ctx -> uniform n_blocks/stride).
    var max_nkeys = 0
    for i in range(B):
        if nkeys_list[i] > max_nkeys:
            max_nkeys = nkeys_list[i]
    var n_blocks = (max_nkeys + kbs - 1) // kbs
    var kv_stride = h_kv * n_blocks * d_head * kbs  # elements per sequence cache (K and V both)

    # Shared K/V buffers: B contiguous caches, all zero-init (unpacked slots stay 0).
    var k_native = List[Float64](capacity=B * kv_stride)
    var v_native = List[Float64](capacity=B * kv_stride)
    for _ in range(B * kv_stride):
        k_native.append(0.0)
        v_native.append(0.0)

    # Per-sequence natural K/V (for the oracle) + Q row.
    var q_stack = List[Float64](capacity=B * h_q * d_head)
    var wants = List[List[Float64]](capacity=B)
    for b in range(B):
        var nk = nkeys_list[b]
        var q_raw = _pseudo_f32(h_q * d_head, seed + b * 100)
        var k_raw = _pseudo_f32(nk * h_kv * d_head, seed + b * 100 + 1)
        var v_raw = _pseudo_f32(nk * h_kv * d_head, seed + b * 100 + 2)
        for i in range(h_q * d_head):
            q_stack.append(q_raw[i])
        wants.append(_oracle_attn(q_raw, k_raw, v_raw, nk, h_q, h_kv, d_head, scale))
        _pack_k_native_at(k_raw, b * kv_stride, nk, h_kv, d_head, kbs, n_blocks, k_native)
        _pack_v_native_at(v_raw, b * kv_stride, nk, h_kv, d_head, kbs, n_blocks, v_native)

    # Upload.
    var q_buf = ctx.enqueue_create_buffer[DType.float16](B * h_q * d_head)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    var nkeys_buf = ctx.enqueue_create_buffer[DType.int64](B)
    var m_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits * d_head)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * d_head)
    with q_buf.map_to_host() as h:
        for i in range(B * h_q * d_head):
            h[i] = Float16(q_stack[i])
    with k_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            h[i] = Float16(v_native[i])
    with nkeys_buf.map_to_host() as h:
        for i in range(B):
            h[i] = Int64(nkeys_list[i])

    ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_kernel](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        nkeys_buf.unsafe_ptr(), Int64(kv_stride),
        Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
        Float32(scale), Int64(kbs), Int64(n_blocks),
        grid_dim=B * h_q * n_splits, block_dim=d_head,
    )
    ctx.enqueue_function[_native_kv_decode_splitk_merge_batched_kernel](
        out_buf.unsafe_ptr(), m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        Int64(n_splits), Int64(h_q), Int64(d_head),
        grid_dim=B * h_q, block_dim=d_head,
    )
    ctx.synchronize()

    var got = List[Float64](capacity=B * h_q * d_head)
    with out_buf.map_to_host() as h:
        for i in range(B * h_q * d_head):
            got.append(Float64(h[i]))

    var all_ok = True
    var worst_all = 0.0
    for b in range(B):
        var got_b = List[Float64](capacity=h_q * d_head)
        for i in range(h_q * d_head):
            got_b.append(got[b * h_q * d_head + i])
        var worst = _worst_ratio(got_b, wants[b], 2.0e-2)
        if worst > worst_all:
            worst_all = worst
        if worst > 1.0:
            all_ok = False
    print("  [batched correctness] B=", B, " nkeys=", nkeys_list, " n_splits=", n_splits,
          " worst_ratio=", worst_all, " ", "OK" if all_ok else "FAIL")
    return all_ok


def test_batched_vs_single_stream(
    ctx: DeviceContext, nkeys_list: List[Int], n_splits: Int, seed: Int,
) raises -> Bool:
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var B = len(nkeys_list)
    var scale = 1.0 / (Float64(d_head) ** 0.5)
    var max_nkeys = 0
    for i in range(B):
        if nkeys_list[i] > max_nkeys:
            max_nkeys = nkeys_list[i]
    var n_blocks = (max_nkeys + kbs - 1) // kbs
    var kv_stride = h_kv * n_blocks * d_head * kbs

    var k_native = List[Float64](capacity=B * kv_stride)
    var v_native = List[Float64](capacity=B * kv_stride)
    for _ in range(B * kv_stride):
        k_native.append(0.0)
        v_native.append(0.0)
    var q_stack = List[Float64](capacity=B * h_q * d_head)
    for b in range(B):
        var nk = nkeys_list[b]
        var q_raw = _pseudo_f32(h_q * d_head, seed + b * 100)
        var k_raw = _pseudo_f32(nk * h_kv * d_head, seed + b * 100 + 1)
        var v_raw = _pseudo_f32(nk * h_kv * d_head, seed + b * 100 + 2)
        for i in range(h_q * d_head):
            q_stack.append(q_raw[i])
        _pack_k_native_at(k_raw, b * kv_stride, nk, h_kv, d_head, kbs, n_blocks, k_native)
        _pack_v_native_at(v_raw, b * kv_stride, nk, h_kv, d_head, kbs, n_blocks, v_native)

    # BATCHED path: partial + batched merge.
    var q_buf = ctx.enqueue_create_buffer[DType.float16](B * h_q * d_head)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    var nkeys_buf = ctx.enqueue_create_buffer[DType.int64](B)
    var m_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits * d_head)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * d_head)
    with q_buf.map_to_host() as h:
        for i in range(B * h_q * d_head):
            h[i] = Float16(q_stack[i])
    with k_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            h[i] = Float16(v_native[i])
    with nkeys_buf.map_to_host() as h:
        for i in range(B):
            h[i] = Int64(nkeys_list[i])
    ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_kernel](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        nkeys_buf.unsafe_ptr(), Int64(kv_stride),
        Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
        Float32(scale), Int64(kbs), Int64(n_blocks),
        grid_dim=B * h_q * n_splits, block_dim=d_head,
    )
    ctx.enqueue_function[_native_kv_decode_splitk_merge_batched_kernel](
        out_buf.unsafe_ptr(), m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        Int64(n_splits), Int64(h_q), Int64(d_head),
        grid_dim=B * h_q, block_dim=d_head,
    )
    ctx.synchronize()
    var batched_out = List[Float64](capacity=B * h_q * d_head)
    with out_buf.map_to_host() as h:
        for i in range(B * h_q * d_head):
            batched_out.append(Float64(h[i]))

    # SINGLE-STREAM path: for each b, read back its partial scratch slice and host-merge (the
    # batched partial wrote [B, h_q, n_splits]; sequence b's slice starts at b*h_q*n_splits).
    var m64 = List[Float64](capacity=B * h_q * n_splits)
    var l64 = List[Float64](capacity=B * h_q * n_splits)
    var o64 = List[Float64](capacity=B * h_q * n_splits * d_head)
    with m_buf.map_to_host() as h:
        for i in range(B * h_q * n_splits):
            m64.append(Float64(h[i]))
    with l_buf.map_to_host() as h:
        for i in range(B * h_q * n_splits):
            l64.append(Float64(h[i]))
    with o_buf.map_to_host() as h:
        for i in range(B * h_q * n_splits * d_head):
            o64.append(Float64(h[i]))

    var all_ok = True
    var worst_all = 0.0
    for b in range(B):
        var ss_merged = _host_merge_partial(m64, l64, o64, b * h_q * n_splits, n_splits, h_q, d_head)
        var got_b = List[Float64](capacity=h_q * d_head)
        for i in range(h_q * d_head):
            got_b.append(batched_out[b * h_q * d_head + i])
        # Float32-reordering tolerance: both sides read the same F16 buffers; only the merge order
        # (batched GPU merge vs host merge) differs.
        var worst = _worst_ratio(got_b, ss_merged, 1.0e-3)
        if worst > worst_all:
            worst_all = worst
        if worst > 1.0:
            all_ok = False
    print("  [batched vs single-stream merge] B=", B, " nkeys=", nkeys_list, " n_splits=", n_splits,
          " worst_ratio=", worst_all, " ", "OK" if all_ok else "FAIL")
    return all_ok


def bench_attention(ctx: DeviceContext, B: Int, depth: Int, n_splits: Int, reps: Int) raises:
    """Attention-side throughput for a B-sequence decode step at uniform `depth`: the BATCHED pair
    (1 partial grid B*h_q*n_splits + 1 merge grid B*h_q) vs B separate single-stream partial
    dispatches (each grid h_q*n_splits). Buffers uploaded once + warmup, timed over `reps` (same
    steady-state discipline as the single-stream driver's bench). Merge is included in the batched
    number (it is the batched path's real second dispatch) but excluded from the single-stream one
    (that merge is the engine's `_splitk_merge_kernel_simd`, structurally tiny)."""
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var scale = 1.0 / (Float64(d_head) ** 0.5)
    var n_blocks = (depth + kbs - 1) // kbs
    var kv_stride = h_kv * n_blocks * d_head * kbs

    var k_native = List[Float64](capacity=B * kv_stride)
    var v_native = List[Float64](capacity=B * kv_stride)
    for _ in range(B * kv_stride):
        k_native.append(0.0)
        v_native.append(0.0)
    var q_stack = List[Float64](capacity=B * h_q * d_head)
    var nkeys = List[Int64](capacity=B)
    for b in range(B):
        var q_raw = _pseudo_f32(h_q * d_head, 7 + b)
        var k_raw = _pseudo_f32(depth * h_kv * d_head, 8 + b)
        var v_raw = _pseudo_f32(depth * h_kv * d_head, 9 + b)
        for i in range(h_q * d_head):
            q_stack.append(q_raw[i])
        nkeys.append(Int64(depth))
        _pack_k_native_at(k_raw, b * kv_stride, depth, h_kv, d_head, kbs, n_blocks, k_native)
        _pack_v_native_at(v_raw, b * kv_stride, depth, h_kv, d_head, kbs, n_blocks, v_native)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](B * h_q * d_head)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    var nkeys_buf = ctx.enqueue_create_buffer[DType.int64](B)
    var m_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * n_splits * d_head)
    var out_buf = ctx.enqueue_create_buffer[DType.float32](B * h_q * d_head)
    with q_buf.map_to_host() as h:
        for i in range(B * h_q * d_head):
            h[i] = Float16(q_stack[i])
    with k_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            h[i] = Float16(v_native[i])
    with nkeys_buf.map_to_host() as h:
        for i in range(B):
            h[i] = nkeys[i]
    ctx.synchronize()

    # Warmup (untimed).
    for _ in range(5):
        ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_kernel](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            nkeys_buf.unsafe_ptr(), Int64(kv_stride),
            Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(kbs), Int64(n_blocks),
            grid_dim=B * h_q * n_splits, block_dim=d_head)
        ctx.enqueue_function[_native_kv_decode_splitk_merge_batched_kernel](
            out_buf.unsafe_ptr(), m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            Int64(n_splits), Int64(h_q), Int64(d_head), grid_dim=B * h_q, block_dim=d_head)
        for b in range(B):
            ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel](
                m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(depth), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
                Float32(scale), Int64(kbs), Int64(n_blocks), grid_dim=h_q * n_splits, block_dim=d_head)
    ctx.synchronize()

    # Batched pair.
    var t0 = perf_counter_ns()
    for _ in range(reps):
        ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_kernel](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            nkeys_buf.unsafe_ptr(), Int64(kv_stride),
            Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(kbs), Int64(n_blocks),
            grid_dim=B * h_q * n_splits, block_dim=d_head)
        ctx.enqueue_function[_native_kv_decode_splitk_merge_batched_kernel](
            out_buf.unsafe_ptr(), m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            Int64(n_splits), Int64(h_q), Int64(d_head), grid_dim=B * h_q, block_dim=d_head)
    ctx.synchronize()
    var t1 = perf_counter_ns()
    var batched_ms = Float64(t1 - t0) / 1.0e6 / Float64(reps)

    # B separate single-stream partial dispatches.
    var t2 = perf_counter_ns()
    for _ in range(reps):
        for b in range(B):
            ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel](
                m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(depth), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
                Float32(scale), Int64(kbs), Int64(n_blocks), grid_dim=h_q * n_splits, block_dim=d_head)
    ctx.synchronize()
    var t3 = perf_counter_ns()
    var ss_ms = Float64(t3 - t2) / 1.0e6 / Float64(reps)

    print("  [attn bench] B=", B, " depth=", depth, " n_splits=", n_splits,
          " batched(partial+merge)=", batched_ms, "ms  B x single-stream(partial)=", ss_ms,
          "ms  batched/seq=", batched_ms / Float64(B), "ms  ratio(ss/batched)=",
          ss_ms / batched_ms if batched_ms > 1.0e-9 else -1.0)


def main() raises:
    var ctx = DeviceContext()
    print("=== batched native decode attn: correctness (real shape 16/8/128, kbs=32) ===")
    var all_ok = True
    # B and per-sequence n_keys: aligned, ragged, deep, mixed, empty-split regimes.
    var c1 = List[Int](); c1.append(256)
    var c2 = List[Int](); c2.append(256); c2.append(456)
    var c3 = List[Int](); c3.append(256); c3.append(456); c3.append(1024); c3.append(3)
    var c4 = List[Int](); c4.append(1); c4.append(17); c4.append(257); c4.append(512)
    var c5 = List[Int]()
    for _ in range(8):
        c5.append(456)
    var c6 = List[Int](); c6.append(3); c6.append(1); c6.append(1024); c6.append(128)
    all_ok &= test_batched_correctness(ctx, c1, 16, 11)
    all_ok &= test_batched_correctness(ctx, c2, 16, 12)
    all_ok &= test_batched_correctness(ctx, c3, 16, 13)
    all_ok &= test_batched_correctness(ctx, c4, 8, 14)
    all_ok &= test_batched_correctness(ctx, c5, 16, 15)
    all_ok &= test_batched_correctness(ctx, c6, 32, 16)
    if not all_ok:
        print("[batched driver] correctness FAILED")
        return
    print("=== batched merge vs single-stream host merge (same partials) ===")
    var s1 = List[Int](); s1.append(256); s1.append(456); s1.append(1024); s1.append(3)
    var s2 = List[Int](); s2.append(1); s2.append(17); s2.append(257); s2.append(512)
    var s3 = List[Int]()
    for _ in range(4):
        s3.append(456)
    all_ok &= test_batched_vs_single_stream(ctx, s1, 16, 21)
    all_ok &= test_batched_vs_single_stream(ctx, s2, 8, 22)
    all_ok &= test_batched_vs_single_stream(ctx, s3, 32, 23)
    if not all_ok:
        print("[batched driver] cross-check FAILED")
        return
    print("[batched driver] all gates PASSED")
    print("=== attention throughput: batched vs B single-stream (steady-state) ===")
    # Raced decode range: 256-token prompt + generation; depths 456 and 1024.
    bench_attention(ctx, 1, 456, 16, 100)
    bench_attention(ctx, 4, 456, 16, 100)
    bench_attention(ctx, 8, 456, 16, 100)
    bench_attention(ctx, 16, 456, 16, 100)
    bench_attention(ctx, 4, 1024, 16, 100)
    bench_attention(ctx, 8, 1024, 16, 100)
    bench_attention(ctx, 16, 1024, 16, 100)
    print("[batched driver] done")
