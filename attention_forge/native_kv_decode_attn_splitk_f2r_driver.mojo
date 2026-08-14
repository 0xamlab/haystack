"""feat/llama-q80gap (2026-08-13): standalone correctness + timing driver for the d_head=64
split-K partial A/B family (REGISTER-BLOCKED `_f2r8/_f2r16` and STAGED-SIMD-K `_f2s4` in
`native_kv_decode_attn_splitk_f2r`) against the shipped `_f2u2` (the kernel the TinyLlama
native fast path dispatches today), at the TinyLlama-1.1B shape (h_q=32, h_kv=4, d_head=64,
key_block_size=32). Same three gate classes as `native_kv_decode_attn_splitk_driver.mojo`,
restated independently for this shape (and its buffer discipline: every helper allocates its OWN
device buffers inline -- DeviceBuffer values do not cross function boundaries in this tree):

1. oracle correctness -- GPU partial + host-side Float64 merge vs a host Float64 attention
   oracle, sweeping aligned/ragged/empty-split (n_keys, n_splits) pairs.
2. BIT-EXACT cross-check vs `_f2u2` over the SAME packed buffers: every variant must reproduce
   f2u2's (m, l, o) partials with ZERO worst-element difference -- they change only WHEN loads
   are issued and how reductions are vectorized, never the per-key arithmetic sequence (this is
   the byte-identical greedy gate's kernel-level evidence).
3. bench -- interleaved-round per-dispatch GPU wall of all five kernels at the race depths
   (288 = the @256 run's mid-decode n_keys, 1056 = the @1024 run's) + 2048, n_splits=16 (the
   production adaptive value at these depths).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_decode_attn_splitk_f2r_driver.mojo
"""

from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from std.math import exp
from native_kv_decode_attn_splitk_f2 import _native_kv_decode_splitk_partial_kernel_f2u2
from native_kv_decode_attn_splitk_f2r import _native_kv_decode_splitk_partial_kernel_f2r8
from native_kv_decode_attn_splitk_f2r import _native_kv_decode_splitk_partial_kernel_f2r16
from native_kv_decode_attn_splitk_f2r import _native_kv_decode_splitk_partial_kernel_f2s4

comptime _H_Q: Int = 32
comptime _H_KV: Int = 4
comptime _D_HEAD: Int = 64
comptime _KBS: Int = 32
comptime _NEG_HUGE64: Float64 = -3.0e38


def _kernel_name(kid: Int) -> String:
    if kid == 0:
        return "f2u2"
    if kid == 1:
        return "f2r8"
    if kid == 2:
        return "f2r16"
    if kid == 3:
        return "f2s4"
    return "f2s4"


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int) -> List[Float64]:
    """Same deterministic generator convention as the d_head=128 driver's own `_pseudo_f32`."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float32(raw)))
    return o^


def _pack_k_native(
    k_raw: List[Float64], n_keys: Int, h_kv: Int, d_head: Int, kbs: Int, n_blocks: Int,
    mut dst: List[Float64],
):
    """K natural layout [j*h_kv+hk][e] -> packed [hk][block][e][kk]."""
    for j in range(n_keys):
        var block = j // kbs
        var kk = j % kbs
        for hk in range(h_kv):
            for e in range(d_head):
                dst[((hk * n_blocks + block) * d_head + e) * kbs + kk] = k_raw[(j * h_kv + hk) * d_head + e]


def _pack_v_native(
    v_raw: List[Float64], n_keys: Int, h_kv: Int, d_head: Int, kbs: Int, n_blocks: Int,
    mut dst: List[Float64],
):
    """V natural layout [j*h_kv+hk][e] -> packed [hk][block][kk][e]."""
    for j in range(n_keys):
        var block = j // kbs
        var kk = j % kbs
        for hk in range(h_kv):
            for e in range(d_head):
                dst[((hk * n_blocks + block) * kbs + kk) * d_head + e] = v_raw[(j * h_kv + hk) * d_head + e]


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


def _run_partial(
    ctx: DeviceContext, kernel_id: Int,
    q64: List[Float64], k_native64: List[Float64], v_native64: List[Float64],
    n_keys: Int, n_splits: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float64,
    key_block_size: Int, n_blocks: Int,
    mut m_out: List[Float64], mut l_out: List[Float64], mut o_out: List[Float64],
) raises:
    """kernel_id: 0=f2u2 1=f2r8 2=f2r16 3=f2s4. Allocates its own buffers, appends
    host-readback (m, l, o) partials."""
    var q_buf = ctx.enqueue_create_buffer[DType.float16](h_q * d_head)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](len(k_native64))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](len(v_native64))
    var m_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits * d_head)
    with q_buf.map_to_host() as h:
        for i in range(h_q * d_head):
            h[i] = Float16(q64[i])
    with k_buf.map_to_host() as h:
        for i in range(len(k_native64)):
            h[i] = Float16(k_native64[i])
    with v_buf.map_to_host() as h:
        for i in range(len(v_native64)):
            h[i] = Float16(v_native64[i])
    if kernel_id == 0:
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2u2](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(key_block_size), Int64(n_blocks),
            grid_dim=h_q * n_splits, block_dim=32)
    elif kernel_id == 1:
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2r8](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(key_block_size), Int64(n_blocks),
            grid_dim=h_q * n_splits, block_dim=32)
    elif kernel_id == 2:
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2r16](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(key_block_size), Int64(n_blocks),
            grid_dim=h_q * n_splits, block_dim=32)
    elif kernel_id == 3:
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(key_block_size), Int64(n_blocks),
            grid_dim=h_q * n_splits, block_dim=32)
    else:
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(key_block_size), Int64(n_blocks),
            grid_dim=h_q * n_splits, block_dim=32)
    ctx.synchronize()
    with m_buf.map_to_host() as h:
        for i in range(h_q * n_splits):
            m_out.append(Float64(h[i]))
    with l_buf.map_to_host() as h:
        for i in range(h_q * n_splits):
            l_out.append(Float64(h[i]))
    with o_buf.map_to_host() as h:
        for i in range(h_q * n_splits * d_head):
            o_out.append(Float64(h[i]))


def _host_merge(
    m64: List[Float64], l64: List[Float64], o64: List[Float64],
    n_splits: Int, h_q: Int, d_head: Int,
) -> List[Float64]:
    """EXACT associative online-softmax combine `_splitk_merge_kernel_simd` applies."""
    var out = List[Float64](capacity=h_q * d_head)
    for h in range(h_q):
        var m = _NEG_HUGE64
        var denom = 0.0
        var o = List[Float64](capacity=d_head)
        for _ in range(d_head):
            o.append(0.0)
        for s in range(n_splits):
            var idx = h * n_splits + s
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


def _worst_ratio(got: List[Float64], want: List[Float64], tol: Float64) -> Float64:
    var worst = 0.0
    for i in range(len(got)):
        var diff = _abs64(got[i] - want[i])
        var allowed = tol * (1.0 + _abs64(want[i]))
        var ratio = diff / allowed
        if ratio > worst:
            worst = ratio
    return worst


def _worst_abs(a: List[Float64], b: List[Float64]) -> Float64:
    var worst = 0.0
    for i in range(len(a)):
        var diff = _abs64(a[i] - b[i])
        if diff > worst:
            worst = diff
    return worst


def _make_case(
    n_keys: Int, seed: Int,
    mut q_raw: List[Float64], mut k_native: List[Float64], mut v_native: List[Float64],
) raises -> Int:
    """Fills q + packed K/V for one (n_keys, seed) case; returns n_blocks."""
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var n_blocks = (n_keys + kbs - 1) // kbs
    q_raw = _pseudo_f32(h_q * d_head, seed)
    var k_raw = _pseudo_f32(n_keys * h_kv * d_head, seed + 1)
    var v_raw = _pseudo_f32(n_keys * h_kv * d_head, seed + 2)
    for _ in range(h_kv * n_blocks * d_head * kbs):
        k_native.append(0.0)
    for _ in range(h_kv * n_blocks * kbs * d_head):
        v_native.append(0.0)
    _pack_k_native(k_raw, n_keys, h_kv, d_head, kbs, n_blocks, k_native)
    _pack_v_native(v_raw, n_keys, h_kv, d_head, kbs, n_blocks, v_native)
    return n_blocks


def test_correctness(
    ctx: DeviceContext, kernel_id: Int, n_keys: Int, n_splits: Int, seed: Int,
) raises -> Bool:
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var q_raw = List[Float64]()
    var k_native = List[Float64]()
    var v_native = List[Float64]()
    var n_blocks = _make_case(n_keys, seed, q_raw, k_native, v_native)
    var scale = 1.0 / (Float64(d_head) ** 0.5)
    var want = _oracle_attn(q_raw, _unpack_k_natural(k_native, n_keys, h_kv, d_head, kbs, n_blocks),
                            _unpack_v_natural(v_native, n_keys, h_kv, d_head, kbs, n_blocks),
                            n_keys, h_q, h_kv, d_head, scale)
    var m64 = List[Float64]()
    var l64 = List[Float64]()
    var o64 = List[Float64]()
    _run_partial(ctx, kernel_id, q_raw, k_native, v_native, n_keys, n_splits, h_q, h_kv, d_head,
                 scale, kbs, n_blocks, m64, l64, o64)
    var got = _host_merge(m64, l64, o64, n_splits, h_q, d_head)
    var worst = _worst_ratio(got, want, 2.0e-2)
    var ok = worst <= 1.0
    print("  [", _kernel_name(kernel_id), " correctness] n_keys=", n_keys, " n_splits=", n_splits,
          " worst_ratio=", worst, " ", "OK" if ok else "FAIL")
    return ok


def _unpack_k_natural(
    k_native: List[Float64], n_keys: Int, h_kv: Int, d_head: Int, kbs: Int, n_blocks: Int,
) -> List[Float64]:
    """packed [hk][block][e][kk] -> natural [j*h_kv+hk][e] for the oracle."""
    var out = List[Float64](capacity=n_keys * h_kv * d_head)
    for _ in range(n_keys * h_kv * d_head):
        out.append(0.0)
    for j in range(n_keys):
        var block = j // kbs
        var kk = j % kbs
        for hk in range(h_kv):
            for e in range(d_head):
                out[(j * h_kv + hk) * d_head + e] = k_native[((hk * n_blocks + block) * d_head + e) * kbs + kk]
    return out^


def _unpack_v_natural(
    v_native: List[Float64], n_keys: Int, h_kv: Int, d_head: Int, kbs: Int, n_blocks: Int,
) -> List[Float64]:
    """packed [hk][block][kk][e] -> natural [j*h_kv+hk][e] for the oracle."""
    var out = List[Float64](capacity=n_keys * h_kv * d_head)
    for _ in range(n_keys * h_kv * d_head):
        out.append(0.0)
    for j in range(n_keys):
        var block = j // kbs
        var kk = j % kbs
        for hk in range(h_kv):
            for e in range(d_head):
                out[(j * h_kv + hk) * d_head + e] = v_native[((hk * n_blocks + block) * kbs + kk) * d_head + e]
    return out^


def test_bit_exact_vs_f2u2(
    ctx: DeviceContext, kernel_id: Int, n_keys: Int, n_splits: Int, seed: Int,
) raises -> Bool:
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var q_raw = List[Float64]()
    var k_native = List[Float64]()
    var v_native = List[Float64]()
    var n_blocks = _make_case(n_keys, seed, q_raw, k_native, v_native)
    var scale = 1.0 / (Float64(d_head) ** 0.5)
    var m0 = List[Float64]()
    var l0 = List[Float64]()
    var o0 = List[Float64]()
    _run_partial(ctx, 0, q_raw, k_native, v_native, n_keys, n_splits, h_q, h_kv, d_head,
                 scale, kbs, n_blocks, m0, l0, o0)
    var m1 = List[Float64]()
    var l1 = List[Float64]()
    var o1 = List[Float64]()
    _run_partial(ctx, kernel_id, q_raw, k_native, v_native, n_keys, n_splits, h_q, h_kv, d_head,
                 scale, kbs, n_blocks, m1, l1, o1)
    var wm = _worst_abs(m0, m1)
    var wl = _worst_abs(l0, l1)
    var wo = _worst_abs(o0, o1)
    var ok = wm == 0.0 and wl == 0.0 and wo == 0.0
    print("  [", _kernel_name(kernel_id), " vs f2u2] n_keys=", n_keys, " n_splits=", n_splits,
          " worst_abs m=", wm, " l=", wl, " o=", wo, " ", "BIT-EXACT" if ok else "FAIL")
    return ok


def bench(ctx: DeviceContext, n_keys: Int, n_splits: Int, rounds: Int, reps: Int) raises:
    """Interleaved-round per-dispatch wall for all five kernels (median across rounds). All
    buffers allocated inline here -- DeviceBuffer values never cross function boundaries."""
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D_HEAD
    var kbs = _KBS
    var q_raw = List[Float64]()
    var k_native = List[Float64]()
    var v_native = List[Float64]()
    var n_blocks = _make_case(n_keys, 31, q_raw, k_native, v_native)
    var scale = 1.0 / (Float64(d_head) ** 0.5)

    var q_buf = ctx.enqueue_create_buffer[DType.float16](h_q * d_head)
    var k_buf = ctx.enqueue_create_buffer[DType.float16](len(k_native))
    var v_buf = ctx.enqueue_create_buffer[DType.float16](len(v_native))
    var m_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var l_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits)
    var o_buf = ctx.enqueue_create_buffer[DType.float32](h_q * n_splits * d_head)
    with q_buf.map_to_host() as h:
        for i in range(h_q * d_head):
            h[i] = Float16(q_raw[i])
    with k_buf.map_to_host() as h:
        for i in range(len(k_native)):
            h[i] = Float16(k_native[i])
    with v_buf.map_to_host() as h:
        for i in range(len(v_native)):
            h[i] = Float16(v_native[i])
    ctx.synchronize()

    # Untimed interleaved warmup (DVFS ramp + PSO first-dispatch, same shape, all arms).
    for _ in range(10):
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2u2](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(kbs), Int64(n_blocks), grid_dim=h_q * n_splits, block_dim=32)
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2r8](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(kbs), Int64(n_blocks), grid_dim=h_q * n_splits, block_dim=32)
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4](
            m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            Float32(scale), Int64(kbs), Int64(n_blocks), grid_dim=h_q * n_splits, block_dim=32)
    ctx.synchronize()

    var s0 = List[Float64](capacity=rounds)
    var s1 = List[Float64](capacity=rounds)
    var s3 = List[Float64](capacity=rounds)
    for r in range(rounds):
        var t0 = perf_counter_ns()
        for _ in range(reps):
            ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2u2](
                m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
                Float32(scale), Int64(kbs), Int64(n_blocks),
                grid_dim=h_q * n_splits, block_dim=32)
        ctx.synchronize()
        var t1 = perf_counter_ns()
        s0.append(Float64(t1 - t0) / 1.0e6 / Float64(reps))

        var t2 = perf_counter_ns()
        for _ in range(reps):
            ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2r8](
                m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
                Float32(scale), Int64(kbs), Int64(n_blocks),
                grid_dim=h_q * n_splits, block_dim=32)
        ctx.synchronize()
        var t3 = perf_counter_ns()
        s1.append(Float64(t3 - t2) / 1.0e6 / Float64(reps))

        var t4 = perf_counter_ns()
        for _ in range(reps):
            ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4](
                m_buf.unsafe_ptr(), l_buf.unsafe_ptr(), o_buf.unsafe_ptr(),
                q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
                Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
                Float32(scale), Int64(kbs), Int64(n_blocks),
                grid_dim=h_q * n_splits, block_dim=32)
        ctx.synchronize()
        var t5 = perf_counter_ns()
        s3.append(Float64(t5 - t4) / 1.0e6 / Float64(reps))


    var med0 = _median(s0)
    var med1 = _median(s1)
    var med3 = _median(s3)
    print("  [bench] n_keys=", n_keys, " n_splits=", n_splits, " rounds=", rounds,
          " reps=", reps, "  f2u2=", med0, "ms  f2r8=", med1, "ms (",
          med0 / med1 if med1 > 1.0e-9 else -1.0, "x)  f2s4=", med3, "ms (",
          med0 / med3 if med3 > 1.0e-9 else -1.0, "x)")


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
    var ctx = DeviceContext()
    print("=== correctness (TinyLlama shape 32/4/64, kbs=32) vs Float64 oracle ===")
    var all_ok = True
    for kid in range(1, 4):
        all_ok &= test_correctness(ctx, kid, 288, 16, 41)
        all_ok &= test_correctness(ctx, kid, 1056, 16, 42)
        all_ok &= test_correctness(ctx, kid, 257, 16, 43)
        all_ok &= test_correctness(ctx, kid, 130, 16, 44)
        all_ok &= test_correctness(ctx, kid, 128, 16, 45)
        all_ok &= test_correctness(ctx, kid, 33, 16, 46)
        all_ok &= test_correctness(ctx, kid, 3, 16, 47)
        all_ok &= test_correctness(ctx, kid, 1, 16, 48)
        all_ok &= test_correctness(ctx, kid, 2048, 32, 49)
    print("=== bit-exact cross-check vs f2u2 (same packed buffers) ===")
    for kid in range(1, 4):
        all_ok &= test_bit_exact_vs_f2u2(ctx, kid, 288, 16, 51)
        all_ok &= test_bit_exact_vs_f2u2(ctx, kid, 1056, 16, 52)
        all_ok &= test_bit_exact_vs_f2u2(ctx, kid, 257, 16, 53)
        all_ok &= test_bit_exact_vs_f2u2(ctx, kid, 130, 16, 54)
        all_ok &= test_bit_exact_vs_f2u2(ctx, kid, 33, 16, 55)
        all_ok &= test_bit_exact_vs_f2u2(ctx, kid, 3, 16, 56)
        all_ok &= test_bit_exact_vs_f2u2(ctx, kid, 2048, 32, 57)
    print("ALL CORRECTNESS:", "PASS" if all_ok else "FAIL")
    print("=== bench (per-dispatch wall, interleaved rounds; f2r16 dropped from the race) ===")
    bench(ctx, 288, 16, 9, 300)
    bench(ctx, 1056, 16, 9, 300)
    bench(ctx, 2048, 32, 9, 300)
