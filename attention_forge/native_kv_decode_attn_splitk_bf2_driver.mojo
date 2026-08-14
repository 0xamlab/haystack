"""native_kv_decode_attn_splitk_bf2_driver.mojo -- feat/batched-llama (2026-08-14): standalone
correctness driver for the d_head=64 BATCHED split-K partial
(`native_kv_decode_attn_splitk_bf2._native_kv_decode_splitk_partial_batched_kernel_bf2u2`),
mirroring `native_kv_decode_attn_splitk_batched_driver.mojo`'s gate discipline:

1. `test_bf2_correctness` -- B sequences with DIFFERENT n_keys packed into ONE contiguous K + ONE
   V buffer (offset = b * kv_stride), bf2u2 partial (grid B*h_q*n_splits, block_dim=32) + the
   forge batched merge, each sequence compared against the host Float64 attention oracle (f16
   bound 2e-2), incl ragged + empty-split regimes.
2. `test_bf2_vs_single_stream` -- the SAME packed buffers dispatched through the BATCHED bf2u2
   pair and through B independent runs of the single-stream `_native_kv_decode_splitk_partial_
   kernel_f2u2` + host merge: element-wise agreement (tight, same-math kernels) proves the batched
   twin computes the SAME function as the proven single-stream f2u2.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_decode_attn_splitk_bf2_driver.mojo
"""
from max.gpu.host import DeviceContext
from std.math import exp
from native_kv_decode_attn_splitk_bf2 import _native_kv_decode_splitk_partial_batched_kernel_bf2u2
from native_kv_decode_attn_splitk_batched import _native_kv_decode_splitk_merge_batched_kernel
from native_kv_decode_attn_splitk_f2 import _native_kv_decode_splitk_partial_kernel_f2u2

comptime _H_Q: Int = 32
comptime _H_KV: Int = 4
comptime _D_HEAD: Int = 64
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


def test_bf2_correctness(
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

    ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_kernel_bf2u2](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        nkeys_buf.unsafe_ptr(), Int64(kv_stride),
        Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
        Float32(scale), Int64(kbs), Int64(n_blocks),
        grid_dim=B * h_q * n_splits, block_dim=32,
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
    print("  [bf2 correctness] B=", B, " nkeys=", nkeys_list, " n_splits=", n_splits,
          " worst_ratio=", worst_all, " ", "OK" if all_ok else "FAIL")
    return all_ok


def test_bf2_vs_single_stream(
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

    # BATCHED path: bf2u2 partial + batched merge.
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

    ctx.enqueue_function[_native_kv_decode_splitk_partial_batched_kernel_bf2u2](
        m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
        q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        nkeys_buf.unsafe_ptr(), Int64(kv_stride),
        Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
        Float32(scale), Int64(kbs), Int64(n_blocks),
        grid_dim=B * h_q * n_splits, block_dim=32,
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

    # SINGLE-STREAM path: B independent f2u2 partial dispatches over each sequence's own slice
    # (kv_off=b*kv_stride baked into a per-seq view is impossible device-side here, so re-pack
    # each sequence into its own contiguous cache -- the single-stream kernel's own layout).
    var worst_cross = 0.0
    for b in range(B):
        var nk = nkeys_list[b]
        var q1 = ctx.enqueue_create_buffer[DType.float16](h_q * d_head)
        var k1 = ctx.enqueue_create_buffer[DType.float16](kv_stride)
        var v1 = ctx.enqueue_create_buffer[DType.float16](kv_stride)
        var m1 = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
        var l1 = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
        var o1 = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits * d_head)
        with q1.map_to_host() as h:
            for i in range(h_q * d_head):
                h[i] = Float16(q_stack[b * h_q * d_head + i])
        with k1.map_to_host() as h:
            for i in range(kv_stride):
                h[i] = Float16(k_native[b * kv_stride + i])
        with v1.map_to_host() as h:
            for i in range(kv_stride):
                h[i] = Float16(v_native[b * kv_stride + i])
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2u2](
            m1.unsafe_ptr(), l1.unsafe_ptr(), o1.unsafe_ptr(),
            q1.unsafe_ptr(), k1.unsafe_ptr(), v1.unsafe_ptr(),
            Int64(nk), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(kbs), Int64(n_blocks),
            grid_dim=h_q * n_splits, block_dim=32,
        )
        ctx.synchronize()
        var m64 = List[Float64](capacity=h_q * n_splits)
        var l64 = List[Float64](capacity=h_q * n_splits)
        var o64 = List[Float64](capacity=h_q * n_splits * d_head)
        with m1.map_to_host() as h:
            for i in range(h_q * n_splits):
                m64.append(Float64(h[i]))
        with l1.map_to_host() as h:
            for i in range(h_q * n_splits):
                l64.append(Float64(h[i]))
        with o1.map_to_host() as h:
            for i in range(h_q * n_splits * d_head):
                o64.append(Float64(h[i]))
        var single_out = _host_merge_partial(m64, l64, o64, 0, n_splits, h_q, d_head)
        var got_b = List[Float64](capacity=h_q * d_head)
        for i in range(h_q * d_head):
            got_b.append(batched_out[b * h_q * d_head + i])
        # Same-math kernels: allow only Float32 tail noise (tight 1e-4 relative).
        var worst = _worst_ratio(got_b, single_out, 1.0e-4)
        if worst > worst_cross:
            worst_cross = worst
    var ok = worst_cross <= 1.0
    print("  [bf2 vs single-stream f2u2] B=", B, " nkeys=", nkeys_list,
          " worst_ratio=", worst_cross, " ", "OK" if ok else "FAIL")
    return ok


def main() raises:
    var ctx = DeviceContext()
    var ok = True
    print("bf2 batched partial driver (d_head=64, h_q=32, h_kv=4)")
    var nkeys_a = List[Int](); nkeys_a.append(7); nkeys_a.append(86)
    var nkeys_b = List[Int](); nkeys_b.append(1); nkeys_b.append(32); nkeys_b.append(33); nkeys_b.append(257)
    var nkeys_c = List[Int](); nkeys_c.append(0); nkeys_c.append(5)  # empty-split regime
    var nkeys_d = List[Int](); nkeys_d.append(288); nkeys_d.append(288)  # deep twins
    ok = test_bf2_correctness(ctx, nkeys_a, 16, 1) and ok
    ok = test_bf2_correctness(ctx, nkeys_b, 16, 2) and ok
    ok = test_bf2_correctness(ctx, nkeys_c, 16, 3) and ok
    ok = test_bf2_correctness(ctx, nkeys_d, 16, 4) and ok
    ok = test_bf2_vs_single_stream(ctx, nkeys_a, 16, 11) and ok
    ok = test_bf2_vs_single_stream(ctx, nkeys_b, 16, 12) and ok
    ok = test_bf2_vs_single_stream(ctx, nkeys_d, 16, 13) and ok
    print("BF2 DRIVER:", "ALL PASS" if ok else "FAILURES")

