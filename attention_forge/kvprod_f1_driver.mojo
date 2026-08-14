"""kvprod_f1_driver.mojo -- feat/llama-q80gap (2026-08-13): standalone BIT-EXACT cross-check +
timing race for the lane-fused no-QK-norm producer (`kvprod_f1._kvprod_f1_kernel`) against the
shipped `native_kv_producer._native_kv_producer_kernel` (qk_norm=0 arm), at the TinyLlama decode
shape (h_q=32, h_kv=4, d_head=64, kbs=32, m_rows=1) + ragged pos_base continuation cases.

GATE 1 (bit-exact): both kernels over IDENTICAL inputs must produce IDENTICAL q_rot/k_native/
v_native bytes (worst-abs-diff 0.0) -- the lane-fused kernel changes only the parallelization
(no shared staging / no barrier), never the per-element arithmetic sequence. Sweep: several
pos_base values (block-aligned, mid-block, zero) -- this is the byte-identical greedy gate's
kernel-level evidence for the kvprod swap.
GATE 2 (timing): interleaved-round per-dispatch wall, original vs f1, m_rows=1 decode shape.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge ../attention_forge/kvprod_f1_driver.mojo
"""

from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from native_kv_producer import _native_kv_producer_kernel
from kvprod_f1 import _kvprod_f1_kernel


def _median(vals: List[Float64]) -> Float64:
    var n = len(vals)
    if n == 0:
        return 0.0
    var a = List[Float64](capacity=n)
    for i in range(n):
        a.append(vals[i])
    for i in range(1, n):
        var key = a[i]
        var j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    return a[n // 2]


def main() raises:
    var h_q = 32
    var h_kv = 4
    var d_head = 64
    var kbs = 32
    var max_ctx = 2048
    var n_blocks = (max_ctx + kbs - 1) // kbs
    var n_pairs = d_head // 2
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var eps = Float32(1.0e-6)
    var scale_unused = Float32(1.0)
    _ = scale_unused

    var ctx = DeviceContext()

    # ── inputs (IDENTICAL for both kernels) ──
    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](n_qkv)
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](max_ctx * n_pairs)
    with qkv_buf.map_to_host() as h:
        for i in range(n_qkv):
            h[i] = Float32(Float64((i * 37 + 11) % 29) / 7.0 - 2.0)
    with qn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(1.0)
    with kn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(1.0)
    with cos_buf.map_to_host() as h:
        for i in range(max_ctx * n_pairs):
            h[i] = Float32(Float64((i * 13 + 5) % 17) / 8.0 - 1.0)
    with sin_buf.map_to_host() as h:
        for i in range(max_ctx * n_pairs):
            h[i] = Float32(Float64((i * 7 + 3) % 19) / 9.0 - 1.0)

    var q0 = ctx.enqueue_create_buffer[DType.float16](h_q * d_head)
    var k0 = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d_head * kbs)
    var v0 = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * kbs * d_head)
    var q1 = ctx.enqueue_create_buffer[DType.float16](h_q * d_head)
    var k1 = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d_head * kbs)
    var v1 = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * kbs * d_head)

    var all_ok = True
    var poses = List[Int]()
    poses.append(17)
    poses.append(31)
    poses.append(32)
    poses.append(33)
    poses.append(255)
    poses.append(256)
    poses.append(1057)
    for pi in range(len(poses)):
        var pos_base = poses[pi]
        ctx.enqueue_function[_native_kv_producer_kernel](
            q0.unsafe_ptr(), k0.unsafe_ptr(), v0.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
            Int64(pos_base), Int64(h_q), Int64(h_kv), Int64(d_head), Int64(kbs), Int64(n_blocks),
            eps, Int64(1), Int64(0),
            grid_dim=h_q + h_kv, block_dim=d_head,
        )
        ctx.enqueue_function[_kvprod_f1_kernel](
            q1.unsafe_ptr(), k1.unsafe_ptr(), v1.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
            Int64(pos_base), Int64(h_q), Int64(h_kv), Int64(d_head), Int64(kbs), Int64(n_blocks),
            eps, Int64(1), Int64(0),
            grid_dim=h_q + h_kv, block_dim=d_head // 2,
        )
        ctx.synchronize()
        # Q: the whole buffer is written by both kernels -> full compare.
        var worst_q = 0.0
        with q0.map_to_host() as a:
            with q1.map_to_host() as b:
                for i in range(h_q * d_head):
                    var diff = Float64(a[i]) - Float64(b[i])
                    if diff < 0.0:
                        diff = -diff
                    if diff > worst_q:
                        worst_q = diff
        # K/V: one dispatch writes exactly ONE key (pos_base) per kv head -> compare exactly the
        # written slots (the rest of the cache is untouched by either kernel).
        var block = pos_base // kbs
        var kk = pos_base % kbs
        var worst_k = 0.0
        with k0.map_to_host() as a:
            with k1.map_to_host() as b:
                for hk in range(h_kv):
                    for e in range(d_head):
                        var idx = ((hk * n_blocks + block) * d_head + e) * kbs + kk
                        var diff = Float64(a[idx]) - Float64(b[idx])
                        if diff < 0.0:
                            diff = -diff
                        if diff > worst_k:
                            worst_k = diff
        var worst_v = 0.0
        with v0.map_to_host() as a:
            with v1.map_to_host() as b:
                for hk in range(h_kv):
                    var v_base = ((hk * n_blocks + block) * kbs + kk) * d_head
                    for e in range(d_head):
                        var diff = Float64(a[v_base + e]) - Float64(b[v_base + e])
                        if diff < 0.0:
                            diff = -diff
                        if diff > worst_v:
                            worst_v = diff
        var ok = worst_q == 0.0 and worst_k == 0.0 and worst_v == 0.0
        all_ok &= ok
        print("  [kvprod_f1 bit-exact] pos_base=", pos_base, " worst_abs q=", worst_q,
              " k=", worst_k, " v=", worst_v, " ", "BIT-EXACT" if ok else "FAIL")
    print("ALL BIT-EXACT:", "PASS" if all_ok else "FAIL")

    # ── timing race, m_rows=1 decode shape ──
    var rounds = 9
    var reps = 300
    for _ in range(10):
        ctx.enqueue_function[_native_kv_producer_kernel](
            q0.unsafe_ptr(), k0.unsafe_ptr(), v0.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
            Int64(256), Int64(h_q), Int64(h_kv), Int64(d_head), Int64(kbs), Int64(n_blocks),
            eps, Int64(1), Int64(0),
            grid_dim=h_q + h_kv, block_dim=d_head,
        )
        ctx.enqueue_function[_kvprod_f1_kernel](
            q1.unsafe_ptr(), k1.unsafe_ptr(), v1.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
            Int64(256), Int64(h_q), Int64(h_kv), Int64(d_head), Int64(kbs), Int64(n_blocks),
            eps, Int64(1), Int64(0),
            grid_dim=h_q + h_kv, block_dim=d_head // 2,
        )
    ctx.synchronize()
    var s0 = List[Float64](capacity=rounds)
    var s1 = List[Float64](capacity=rounds)
    for r in range(rounds):
        var t0 = perf_counter_ns()
        for _ in range(reps):
            ctx.enqueue_function[_native_kv_producer_kernel](
                q0.unsafe_ptr(), k0.unsafe_ptr(), v0.unsafe_ptr(),
                qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
                cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
                Int64(256), Int64(h_q), Int64(h_kv), Int64(d_head), Int64(kbs), Int64(n_blocks),
                eps, Int64(1), Int64(0),
                grid_dim=h_q + h_kv, block_dim=d_head,
            )
        ctx.synchronize()
        var t1 = perf_counter_ns()
        s0.append(Float64(t1 - t0) / 1.0e6 / Float64(reps))
        var t2 = perf_counter_ns()
        for _ in range(reps):
            ctx.enqueue_function[_kvprod_f1_kernel](
                q1.unsafe_ptr(), k1.unsafe_ptr(), v1.unsafe_ptr(),
                qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
                cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
                Int64(256), Int64(h_q), Int64(h_kv), Int64(d_head), Int64(kbs), Int64(n_blocks),
                eps, Int64(1), Int64(0),
                grid_dim=h_q + h_kv, block_dim=d_head // 2,
            )
        ctx.synchronize()
        var t3 = perf_counter_ns()
        s1.append(Float64(t3 - t2) / 1.0e6 / Float64(reps))
    var med0 = _median(s0)
    var med1 = _median(s1)
    print("  [bench m_rows=1] original=", med0, "ms/dispatch  f1=", med1, "ms  (",
          med0 / med1 if med1 > 1.0e-9 else -1.0, "x)")
