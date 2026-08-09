"""native_kv_producer_batched_driver.mojo -- Project Slipstream Phase 3 (2026-08-09): standalone
correctness driver for `native_kv_producer_batched._native_kv_producer_batched_kernel`. Gate
discipline mirrors the attention batched driver: cross-check the BATCHED producer against B
independent runs of the PROVEN single-stream `_native_kv_producer_kernel` on identical per-sequence
inputs (same qkv row, same position, same norm weights, same RoPE tables, same provisioned
n_blocks). Element-wise agreement on Q_rot, K, V proves the batched producer computes the SAME
function as the single-stream one -- the strongest signal, since the single-stream producer is
already oracle-verified by its own driver.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_producer_batched_driver.mojo
"""
from max.gpu.host import DeviceContext
from kvprod_batched import _native_kv_producer_batched_kernel
from native_kv_producer import _native_kv_producer_kernel

comptime _H_Q: Int = 16
comptime _H_KV: Int = 8
comptime _D_HEAD: Int = 128
comptime _KBS: Int = 32
comptime _EPS: Float64 = 1.0e-6


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float32(raw)))
    return o^


def _worst_ratio(got: List[Float64], want: List[Float64], tol: Float64) -> Float64:
    var worst = 0.0
    for i in range(len(got)):
        var diff = _abs64(got[i] - want[i])
        var allowed = tol * (1.0 + _abs64(want[i]))
        var ratio = diff / allowed
        if ratio > worst:
            worst = ratio
    return worst


def test_batched_kvprod(ctx: DeviceContext, poss: List[Int], seed: Int) raises -> Bool:
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var eps = Float32(_EPS)
    var B = len(poss)
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var n_pairs = d_head // 2

    var max_pos = 0
    for i in range(B):
        if poss[i] > max_pos:
            max_pos = poss[i]
    # All caches provisioned to the largest position: block = pos//kbs must be < n_blocks.
    var n_blocks = (max_pos + 1 + kbs - 1) // kbs
    var kv_stride = h_kv * n_blocks * d_head * kbs

    # Shared inputs: qkv stack [B, n_qkv], norm weights, RoPE tables (identical for both arms).
    var qkv_stack = _pseudo_f32(B * n_qkv, seed)
    var qn_w = _pseudo_f32(d_head, seed + 1)
    var kn_w = _pseudo_f32(d_head, seed + 2)
    var cos_t = _pseudo_f32((max_pos + 1) * n_pairs, seed + 3)
    var sin_t = _pseudo_f32((max_pos + 1) * n_pairs, seed + 4)

    # ---- BATCHED arm ----
    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](B * n_qkv)
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32]((max_pos + 1) * n_pairs)
    var sin_buf = ctx.enqueue_create_buffer[DType.float32]((max_pos + 1) * n_pairs)
    var poss_buf = ctx.enqueue_create_buffer[DType.int64](B)
    var qrot_buf = ctx.enqueue_create_buffer[DType.float16](B * h_q * d_head)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    var v_buf = ctx.enqueue_create_buffer[DType.float16](B * kv_stride)
    with qkv_buf.map_to_host() as h:
        for i in range(B * n_qkv):
            h[i] = Float32(qkv_stack[i])
    with qn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(qn_w[i])
    with kn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(kn_w[i])
    with cos_buf.map_to_host() as h:
        for i in range((max_pos + 1) * n_pairs):
            h[i] = Float32(cos_t[i])
    with sin_buf.map_to_host() as h:
        for i in range((max_pos + 1) * n_pairs):
            h[i] = Float32(sin_t[i])
    with poss_buf.map_to_host() as h:
        for i in range(B):
            h[i] = Int64(poss[i])

    ctx.enqueue_function[_native_kv_producer_batched_kernel](
        qrot_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        poss_buf.unsafe_ptr(), Int64(kv_stride),
        Int64(h_q), Int64(h_kv), Int64(d_head), Int64(kbs), Int64(n_blocks), eps,
        grid_dim=(h_q + h_kv) * B, block_dim=d_head,
    )
    ctx.synchronize()

    var qrot_b = List[Float64](capacity=B * h_q * d_head)
    var k_b = List[Float64](capacity=B * kv_stride)
    var v_b = List[Float64](capacity=B * kv_stride)
    with qrot_buf.map_to_host() as h:
        for i in range(B * h_q * d_head):
            qrot_b.append(Float64(h[i]))
    with k_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            k_b.append(Float64(h[i]))
    with v_buf.map_to_host() as h:
        for i in range(B * kv_stride):
            v_b.append(Float64(h[i]))

    # ---- SINGLE-STREAM arm: B independent runs of the proven producer ----
    var worst_q = 0.0
    var worst_k = 0.0
    var worst_v = 0.0
    for b in range(B):
        # qkv row for seq b.
        var qkv_row_buf = ctx.enqueue_create_buffer[DType.float32](n_qkv)
        with qkv_row_buf.map_to_host() as h:
            for i in range(n_qkv):
                h[i] = Float32(qkv_stack[b * n_qkv + i])
        var qrot_ss_buf = ctx.enqueue_create_buffer[DType.float16](h_q * d_head)
        var k_ss_buf = ctx.enqueue_create_buffer[DType.float16](kv_stride)
        var v_ss_buf = ctx.enqueue_create_buffer[DType.float16](kv_stride)
        ctx.enqueue_function[_native_kv_producer_kernel](
            qrot_ss_buf.unsafe_ptr(), k_ss_buf.unsafe_ptr(), v_ss_buf.unsafe_ptr(),
            qkv_row_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
            Int64(poss[b]), Int64(h_q), Int64(h_kv), Int64(d_head),
            Int64(kbs), Int64(n_blocks), eps, Int64(1),
            grid_dim=(h_q + h_kv) * 1, block_dim=d_head,
        )
        ctx.synchronize()
        var qrot_ss = List[Float64](capacity=h_q * d_head)
        var k_ss = List[Float64](capacity=kv_stride)
        var v_ss = List[Float64](capacity=kv_stride)
        with qrot_ss_buf.map_to_host() as h:
            for i in range(h_q * d_head):
                qrot_ss.append(Float64(h[i]))
        with k_ss_buf.map_to_host() as h:
            for i in range(kv_stride):
                k_ss.append(Float64(h[i]))
        with v_ss_buf.map_to_host() as h:
            for i in range(kv_stride):
                v_ss.append(Float64(h[i]))

        # Compare batched seq-b slices against single-stream outputs.
        var qrot_b_slice = List[Float64](capacity=h_q * d_head)
        for i in range(h_q * d_head):
            qrot_b_slice.append(qrot_b[b * h_q * d_head + i])
        var k_b_slice = List[Float64](capacity=kv_stride)
        var v_b_slice = List[Float64](capacity=kv_stride)
        for i in range(kv_stride):
            k_b_slice.append(k_b[b * kv_stride + i])
            v_b_slice.append(v_b[b * kv_stride + i])
        # Tight tolerance: same computation, same order -> expect near bit-exact F16.
        var wq = _worst_ratio(qrot_b_slice, qrot_ss, 1.0e-3)
        var wk = _worst_ratio(k_b_slice, k_ss, 1.0e-3)
        var wv = _worst_ratio(v_b_slice, v_ss, 1.0e-3)
        if wq > worst_q:
            worst_q = wq
        if wk > worst_k:
            worst_k = wk
        if wv > worst_v:
            worst_v = wv

    var ok = worst_q <= 1.0 and worst_k <= 1.0 and worst_v <= 1.0
    print("  [batched kvprod vs single-stream] B=", B, " poss=", poss,
          " worst_q=", worst_q, " worst_k=", worst_k, " worst_v=", worst_v,
          " ", "OK" if ok else "FAIL")
    return ok


def main() raises:
    var ctx = DeviceContext()
    print("=== batched KV producer: cross-check vs proven single-stream producer ===")
    var all_ok = True
    var p1 = List[Int](); p1.append(0)
    var p2 = List[Int](); p2.append(0); p2.append(255)
    var p3 = List[Int](); p3.append(5); p3.append(100); p3.append(456); p3.append(33)
    var p4 = List[Int](); p4.append(17); p4.append(31); p4.append(32); p4.append(63)
    var p5 = List[Int]()
    for _ in range(8):
        p5.append(200)
    var p6 = List[Int](); p6.append(0); p6.append(1); p6.append(511); p6.append(128)
    all_ok &= test_batched_kvprod(ctx, p1, 11)
    all_ok &= test_batched_kvprod(ctx, p2, 12)
    all_ok &= test_batched_kvprod(ctx, p3, 13)
    all_ok &= test_batched_kvprod(ctx, p4, 14)  # block-boundary positions (31, 32, 63)
    all_ok &= test_batched_kvprod(ctx, p5, 15)
    all_ok &= test_batched_kvprod(ctx, p6, 16)
    if not all_ok:
        print("[batched kvprod driver] FAILED")
        return
    print("[batched kvprod driver] all gates PASSED")
