"""kvfuse_f2s4_decode_splitk_driver.mojo -- feat/metal-beat (2026-08-23): standalone
correctness + timing driver for the kvprod-FUSED d64 split-K partial (`_f2s4k`) against the
production REFERENCE PATH = `_native_kv_producer_kernel` (kvprod, qk_norm=0) dispatched ahead
of `_native_kv_decode_splitk_partial_kernel_f2s4`, at the TinyLlama-1.1B shape (h_q=32,
h_kv=4, d_head=64, key_block_size=32, n_splits=16). Gates:

1. BIT-EXACT vs the reference path on (m, l, o) partials -- worst-abs-diff must be 0.0 across
   aligned/ragged/edge (n_keys, n_splits) pairs (the byte-identical greedy gate's kernel-level
   evidence: the fusion changes WHERE the kvprod math runs, never the arithmetic sequence).
2. BIT-EXACT packed-cache APPEND: the K/V slot the fused kernel writes at `pos` must equal the
   standalone producer's byte-for-byte (future tokens read it).
3. Oracle: Float64 host merge of the fused partials vs a Float64 host attention oracle
   (f16-bound tolerance), proving the fused path is still end-to-end correct, not merely
   reference-matching.
4. Soak: repeated fused dispatches reproduce the identical partials every time (determinism).
5. Bench: interleaved-round wall of the reference PAIR (kvprod + f2s4, 2 dispatches) vs the
   fused SINGLE dispatch at the race depths (288 = @256 run's mid-decode n_keys, 1056 = the
   @1024 run's).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/kvfuse_f2s4_decode_splitk_driver.mojo
"""

from max.gpu.host import DeviceContext
from std.time import perf_counter_ns
from std.math import exp
from native_kv_producer import _native_kv_producer_kernel
from native_kv_decode_attn_splitk_f2s4 import _native_kv_decode_splitk_partial_kernel_f2s4
from kvfuse_f2s4_decode_splitk import _native_kv_decode_splitk_partial_kernel_f2s4k

comptime _H_Q: Int = 32
comptime _H_KV: Int = 4
comptime _D: Int = 64
comptime _KBS: Int = 32
comptime _N_SPLITS: Int = 16
comptime _N_QKV: Int = (_H_Q + 2 * _H_KV) * _D
comptime _NEG_HUGE64: Float64 = -3.0e38


def _pseudo_f32(n: Int, seed: Int) -> List[Float64]:
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float32(raw)))
    return o^


def _pack_k_native(
    k_raw: List[Float64], n_keys: Int, h_kv: Int, d_head: Int, kbs: Int, n_blocks: Int,
    mut dst: List[Float64],
):
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
    for j in range(n_keys):
        var block = j // kbs
        var kk = j % kbs
        for hk in range(h_kv):
            for e in range(d_head):
                dst[((hk * n_blocks + block) * kbs + kk) * d_head + e] = v_raw[(j * h_kv + hk) * d_head + e]


def _host_rope_qkv(
    qkv: List[Float64], cos_t: List[Float64], sin_t: List[Float64],
    pos: Int, h_q: Int, h_kv: Int, d_head: Int,
    mut q64: List[Float64], mut k64_nat: List[Float64], mut v64_nat: List[Float64],
):
    """Host twin of the kvprod qk_norm=0 math (NeoX split-half rope at absolute `pos`), writing
    NATURAL-layout per-key q/k/v rows the Float64 oracle consumes."""
    var n_pairs = d_head // 2
    for h in range(h_q):
        for e in range(n_pairs):
            var a0 = qkv[h * d_head + e]
            var a1 = qkv[h * d_head + e + n_pairs]
            var c = cos_t[pos * n_pairs + e]
            var s = sin_t[pos * n_pairs + e]
            q64[h * d_head + e] = Float64(Float16(Float32(a0 * c - a1 * s)))
            q64[h * d_head + e + n_pairs] = Float64(Float16(Float32(a0 * s + a1 * c)))
    for hk in range(h_kv):
        for e in range(n_pairs):
            var a0 = qkv[(h_q + hk) * d_head + e]
            var a1 = qkv[(h_q + hk) * d_head + e + n_pairs]
            var c = cos_t[pos * n_pairs + e]
            var s = sin_t[pos * n_pairs + e]
            k64_nat[hk * d_head + e] = Float64(Float16(Float32(a0 * c - a1 * s)))
            k64_nat[hk * d_head + e + n_pairs] = Float64(Float16(Float32(a0 * s + a1 * c)))
        for e in range(d_head):
            v64_nat[hk * d_head + e] = Float64(Float16(Float32(qkv[(h_q + h_kv + hk) * d_head + e])))


def _oracle_attn(
    q64: List[Float64], k_hist: List[Float64], v_hist: List[Float64],
    k_new: List[Float64], v_new: List[Float64],
    n_hist: Int, h_q: Int, h_kv: Int, d_head: Int, scale: Float64,
) -> List[Float64]:
    """Float64 attention over the `n_hist` packed-history keys plus the new key at `pos`."""
    var out = List[Float64](capacity=h_q * d_head)
    var group = h_q // h_kv
    for h in range(h_q):
        var hk = h // group
        var o = List[Float64](capacity=d_head)
        for _ in range(d_head):
            o.append(0.0)
        var m = _NEG_HUGE64
        var denom = 0.0
        for j in range(n_hist + 1):
            var s = 0.0
            for d in range(d_head):
                var kval = k_hist[(j * h_kv + hk) * d_head + d] if j < n_hist else k_new[hk * d_head + d]
                s += q64[h * d_head + d] * kval
            s *= scale
            var nm = m if m > s else s
            var corr = exp(m - nm)
            var w = exp(s - nm)
            for d in range(d_head):
                var vval = v_hist[(j * h_kv + hk) * d_head + d] if j < n_hist else v_new[hk * d_head + d]
                o[d] = o[d] * corr + w * vval
            denom = denom * corr + w
            m = nm
        for d in range(d_head):
            out.append(o[d] / denom)
    return out^


def _host_merge(
    m64: List[Float64], l64: List[Float64], o64: List[Float64],
    n_splits: Int, h_q: Int, d_head: Int,
) -> List[Float64]:
    """EXACT associative online-softmax combine `_splitk_merge_kernel_simd` applies."""
    var out = List[Float64](capacity=h_q * d_head)
    for h in range(h_q):
        var nm = _NEG_HUGE64
        for s in range(n_splits):
            var mv = m64[h * n_splits + s]
            if mv > nm:
                nm = mv
        var denom = 0.0
        for s in range(n_splits):
            denom += l64[h * n_splits + s] * exp(m64[h * n_splits + s] - nm)
        for d in range(d_head):
            var acc = 0.0
            for s in range(n_splits):
                acc += o64[(h * n_splits + s) * d_head + d] * exp(m64[h * n_splits + s] - nm)
            out.append(acc / denom)
    return out^


def main() raises:
    var ctx = DeviceContext()
    var h_q = _H_Q
    var h_kv = _H_KV
    var d_head = _D
    var kbs = _KBS
    var n_pairs = d_head // 2
    var n_units = h_q + h_kv
    var scale64: Float64 = 1.0 / Float64(d_head) ** 0.5
    var scale = Float32(scale64)

    var max_n_keys = 1056
    var n_blocks = (max_n_keys + kbs - 1) // kbs
    var kv_elems = h_kv * n_blocks * d_head * kbs

    var qkv64 = _pseudo_f32(_N_QKV, 3)
    var k_hist64 = _pseudo_f32((max_n_keys - 1) * h_kv * d_head, 5)
    var v_hist64 = _pseudo_f32((max_n_keys - 1) * h_kv * d_head, 7)
    var max_pos = max_n_keys - 1
    var cos64 = _pseudo_f32((max_pos + 1) * n_pairs, 11)
    var sin64 = _pseudo_f32((max_pos + 1) * n_pairs, 13)

    # ── main-scope buffers, reused across cells/soak/bench ──
    var qrot_buf = ctx.enqueue_create_buffer[DType.float16](h_q * d_head)
    var a_k = ctx.enqueue_create_buffer[DType.float16](kv_elems)
    var a_v = ctx.enqueue_create_buffer[DType.float16](kv_elems)
    var b_k = ctx.enqueue_create_buffer[DType.float16](kv_elems)
    var b_v = ctx.enqueue_create_buffer[DType.float16](kv_elems)
    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](_N_QKV)
    var dummy_qn = ctx.enqueue_create_buffer[DType.float32](d_head)
    var dummy_kn = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32]((max_pos + 1) * n_pairs)
    var sin_buf = ctx.enqueue_create_buffer[DType.float32]((max_pos + 1) * n_pairs)
    var a_m = ctx.enqueue_create_buffer[DType.float32](h_q * _N_SPLITS)
    var a_l = ctx.enqueue_create_buffer[DType.float32](h_q * _N_SPLITS)
    var a_o = ctx.enqueue_create_buffer[DType.float32](h_q * _N_SPLITS * d_head)
    var b_m = ctx.enqueue_create_buffer[DType.float32](h_q * _N_SPLITS)
    var b_l = ctx.enqueue_create_buffer[DType.float32](h_q * _N_SPLITS)
    var b_o = ctx.enqueue_create_buffer[DType.float32](h_q * _N_SPLITS * d_head)
    with qkv_buf.map_to_host() as h:
        for i in range(_N_QKV):
            h[i] = Float32(qkv64[i])
    with cos_buf.map_to_host() as h:
        for i in range((max_pos + 1) * n_pairs):
            h[i] = Float32(cos64[i])
    with sin_buf.map_to_host() as h:
        for i in range((max_pos + 1) * n_pairs):
            h[i] = Float32(sin64[i])

    var cells = List[Int](capacity=8)
    cells.append(32)
    cells.append(33)
    cells.append(47)
    cells.append(64)
    cells.append(288)
    cells.append(1056)

    var worst_mlo = 0.0
    var worst_kvslot = 0.0
    var worst_oracle = 0.0

    for ci in range(len(cells)):
        var n_keys = cells[ci]
        var pos = n_keys - 1
        var n_hist = pos
        var n_splits = _N_SPLITS

        # Host packs for the HISTORY keys [0, pos) -- identical starting cache for both paths.
        var kpack = List[Float64](capacity=kv_elems)
        var vpack = List[Float64](capacity=kv_elems)
        for i in range(kv_elems):
            kpack.append(0.0)
            vpack.append(0.0)
        _pack_k_native(k_hist64, n_hist, h_kv, d_head, kbs, n_blocks, kpack)
        _pack_v_native(v_hist64, n_hist, h_kv, d_head, kbs, n_blocks, vpack)

        var q64 = List[Float64](capacity=h_q * d_head)
        var knew64 = List[Float64](capacity=h_kv * d_head)
        var vnew64 = List[Float64](capacity=h_kv * d_head)
        for i in range(h_q * d_head):
            q64.append(0.0)
        for i in range(h_kv * d_head):
            knew64.append(0.0)
            vnew64.append(0.0)
        _host_rope_qkv(qkv64, cos64, sin64, pos, h_q, h_kv, d_head, q64, knew64, vnew64)

        # ══ PATH A (reference): kvprod dispatch, then f2s4 dispatch ══
        with a_k.map_to_host() as h:
            for i in range(kv_elems):
                h[i] = Float16(kpack[i])
        with a_v.map_to_host() as h:
            for i in range(kv_elems):
                h[i] = Float16(vpack[i])
        ctx.enqueue_function[_native_kv_producer_kernel](
            qrot_buf.unsafe_ptr(), a_k.unsafe_ptr(), a_v.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), dummy_qn.unsafe_ptr(), dummy_kn.unsafe_ptr(),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
            Int64(pos), Int64(h_q), Int64(h_kv), Int64(d_head),
            Int64(kbs), Int64(n_blocks), Float32(1e-5), Int64(1), Int64(0),
            grid_dim=n_units, block_dim=d_head)
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4](
            a_m.unsafe_ptr(), a_l.unsafe_ptr(), a_o.unsafe_ptr(),
            qrot_buf.unsafe_ptr(), a_k.unsafe_ptr(), a_v.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            scale, Int64(kbs), Int64(n_blocks),
            grid_dim=h_q * n_splits, block_dim=32)
        ctx.synchronize()
        var ref_m = List[Float64](capacity=h_q * n_splits)
        var ref_l = List[Float64](capacity=h_q * n_splits)
        var ref_o = List[Float64](capacity=h_q * n_splits * d_head)
        with a_m.map_to_host() as h:
            for i in range(h_q * n_splits):
                ref_m.append(Float64(h[i]))
        with a_l.map_to_host() as h:
            for i in range(h_q * n_splits):
                ref_l.append(Float64(h[i]))
        with a_o.map_to_host() as h:
            for i in range(h_q * n_splits * d_head):
                ref_o.append(Float64(h[i]))
        var ref_kslot = List[Float64](capacity=h_kv * d_head)
        var ref_vslot = List[Float64](capacity=h_kv * d_head)
        var block_p = pos // kbs
        var kk_p = pos % kbs
        with a_k.map_to_host() as h:
            for hk in range(h_kv):
                for e in range(d_head):
                    ref_kslot.append(Float64(h[((hk * n_blocks + block_p) * d_head + e) * kbs + kk_p]))
        with a_v.map_to_host() as h:
            for hk in range(h_kv):
                for e in range(d_head):
                    ref_vslot.append(Float64(h[((hk * n_blocks + block_p) * kbs + kk_p) * d_head + e]))

        # ══ PATH B (fused): one f2s4k dispatch over the SAME history cache ══
        with b_k.map_to_host() as h:
            for i in range(kv_elems):
                h[i] = Float16(kpack[i])
        with b_v.map_to_host() as h:
            for i in range(kv_elems):
                h[i] = Float16(vpack[i])
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4k](
            b_m.unsafe_ptr(), b_l.unsafe_ptr(), b_o.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), b_k.unsafe_ptr(), b_v.unsafe_ptr(),
            Int64(n_keys), Int64(n_splits), Int64(h_q), Int64(h_kv), Int64(d_head),
            scale, Int64(kbs), Int64(n_blocks),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(), Int64(pos), Int64(0),
            grid_dim=h_q * n_splits, block_dim=32)
        ctx.synchronize()
        var fus_m = List[Float64](capacity=h_q * n_splits)
        var fus_l = List[Float64](capacity=h_q * n_splits)
        var fus_o = List[Float64](capacity=h_q * n_splits * d_head)
        with b_m.map_to_host() as h:
            for i in range(h_q * n_splits):
                fus_m.append(Float64(h[i]))
        with b_l.map_to_host() as h:
            for i in range(h_q * n_splits):
                fus_l.append(Float64(h[i]))
        with b_o.map_to_host() as h:
            for i in range(h_q * n_splits * d_head):
                fus_o.append(Float64(h[i]))
        var fus_kslot = List[Float64](capacity=h_kv * d_head)
        var fus_vslot = List[Float64](capacity=h_kv * d_head)
        with b_k.map_to_host() as h:
            for hk in range(h_kv):
                for e in range(d_head):
                    fus_kslot.append(Float64(h[((hk * n_blocks + block_p) * d_head + e) * kbs + kk_p]))
        with b_v.map_to_host() as h:
            for hk in range(h_kv):
                for e in range(d_head):
                    fus_vslot.append(Float64(h[((hk * n_blocks + block_p) * kbs + kk_p) * d_head + e]))

        # ── GATE 1: bit-exact partials ──
        var w = 0.0
        for i in range(h_q * n_splits):
            var dm = ref_m[i] - fus_m[i]
            var dl = ref_l[i] - fus_l[i]
            w = w if w > (dm if dm > -dm else -dm) else (dm if dm > -dm else -dm)
            w = w if w > (dl if dl > -dl else -dl) else (dl if dl > -dl else -dl)
        for i in range(h_q * n_splits * d_head):
            var dv = ref_o[i] - fus_o[i]
            w = w if w > (dv if dv > -dv else -dv) else (dv if dv > -dv else -dv)
        if w > worst_mlo:
            worst_mlo = w
        print("cell n_keys=", n_keys, " bitexact(m,l,o) worst-diff = ", w)

        # ── GATE 2: bit-exact cache append at pos ──
        var wk = 0.0
        for i in range(h_kv * d_head):
            var dk = ref_kslot[i] - fus_kslot[i]
            var dv = ref_vslot[i] - fus_vslot[i]
            wk = wk if wk > (dk if dk > -dk else -dk) else (dk if dk > -dk else -dk)
            wk = wk if wk > (dv if dv > -dv else -dv) else (dv if dv > -dv else -dv)
        if wk > worst_kvslot:
            worst_kvslot = wk
        print("cell n_keys=", n_keys, " cache-slot(pos) worst-diff = ", wk)

        # ── GATE 3: oracle on the deepest + one ragged cell ──
        if n_keys == 288 or n_keys == 47:
            var merged = _host_merge(fus_m, fus_l, fus_o, n_splits, h_q, d_head)
            var oracle = _oracle_attn(q64, k_hist64, v_hist64, knew64, vnew64, n_hist, h_q, h_kv, d_head, scale64)
            var wo = 0.0
            for i in range(h_q * d_head):
                var num = merged[i] - oracle[i]
                var den = oracle[i]
                var r = (num if num > -num else -num) / (den if den > 0.01 else 1.0)
                wo = wo if wo > r else r
            if wo > worst_oracle:
                worst_oracle = wo
            print("cell n_keys=", n_keys, " oracle worst-ratio = ", wo)

    print("GATE SUMMARY: worst m/l/o diff = ", worst_mlo, " (must be 0.0)")
    print("GATE SUMMARY: worst cache-slot diff = ", worst_kvslot, " (must be 0.0)")
    print("GATE SUMMARY: worst oracle ratio = ", worst_oracle, " (f16 bound <= ~0.025)")
    if worst_mlo != 0.0 or worst_kvslot != 0.0 or worst_oracle > 0.025:
        print("RESULT: FAIL")
    else:
        print("RESULT: PASS")

    # ── GATE 4: soak -- 50 fused dispatches, deterministic partials every time ──
    var soak_bad = 0
    var n_keys_soak = 288
    var pos_soak = n_keys_soak - 1
    var kpack_s = List[Float64](capacity=kv_elems)
    var vpack_s = List[Float64](capacity=kv_elems)
    for i in range(kv_elems):
        kpack_s.append(0.0)
        vpack_s.append(0.0)
    _pack_k_native(k_hist64, pos_soak, h_kv, d_head, kbs, n_blocks, kpack_s)
    _pack_v_native(v_hist64, pos_soak, h_kv, d_head, kbs, n_blocks, vpack_s)
    with b_k.map_to_host() as h:
        for i in range(kv_elems):
            h[i] = Float16(kpack_s[i])
    with b_v.map_to_host() as h:
        for i in range(kv_elems):
            h[i] = Float16(vpack_s[i])
    var base_m = List[Float64](capacity=h_q * _N_SPLITS)
    for rep in range(50):
        ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4k](
            b_m.unsafe_ptr(), b_l.unsafe_ptr(), b_o.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), b_k.unsafe_ptr(), b_v.unsafe_ptr(),
            Int64(n_keys_soak), Int64(_N_SPLITS), Int64(h_q), Int64(h_kv), Int64(d_head),
            scale, Int64(kbs), Int64(n_blocks),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(), Int64(pos_soak), Int64(0),
            grid_dim=h_q * _N_SPLITS, block_dim=32)
        ctx.synchronize()
        if rep == 0:
            with b_m.map_to_host() as h:
                for i in range(h_q * _N_SPLITS):
                    base_m.append(Float64(h[i]))
        else:
            with b_m.map_to_host() as h:
                for i in range(h_q * _N_SPLITS):
                    if Float64(h[i]) != base_m[i]:
                        soak_bad += 1
    print("SOAK: 50 reps, mismatches = ", soak_bad, " (must be 0)")

    # ── BENCH: reference pair (2 dispatches) vs fused single dispatch ──
    for bi in range(2):
        var n_keys_b = 288 if bi == 0 else 1056
        var pos_b = n_keys_b - 1
        var rounds = 9
        var pair_times = List[Int](capacity=rounds)
        var fuse_times = List[Int](capacity=rounds)
        for r in range(rounds + 3):
            var t0 = perf_counter_ns()
            ctx.enqueue_function[_native_kv_producer_kernel](
                qrot_buf.unsafe_ptr(), a_k.unsafe_ptr(), a_v.unsafe_ptr(),
                qkv_buf.unsafe_ptr(), dummy_qn.unsafe_ptr(), dummy_kn.unsafe_ptr(),
                cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
                Int64(pos_b), Int64(h_q), Int64(h_kv), Int64(d_head),
                Int64(kbs), Int64(n_blocks), Float32(1e-5), Int64(1), Int64(0),
                grid_dim=n_units, block_dim=d_head)
            ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4](
                a_m.unsafe_ptr(), a_l.unsafe_ptr(), a_o.unsafe_ptr(),
                qrot_buf.unsafe_ptr(), a_k.unsafe_ptr(), a_v.unsafe_ptr(),
                Int64(n_keys_b), Int64(_N_SPLITS), Int64(h_q), Int64(h_kv), Int64(d_head),
                scale, Int64(kbs), Int64(n_blocks),
                grid_dim=h_q * _N_SPLITS, block_dim=32)
            ctx.synchronize()
            var t1 = perf_counter_ns()
            ctx.enqueue_function[_native_kv_decode_splitk_partial_kernel_f2s4k](
                b_m.unsafe_ptr(), b_l.unsafe_ptr(), b_o.unsafe_ptr(),
                qkv_buf.unsafe_ptr(), b_k.unsafe_ptr(), b_v.unsafe_ptr(),
                Int64(n_keys_b), Int64(_N_SPLITS), Int64(h_q), Int64(h_kv), Int64(d_head),
                scale, Int64(kbs), Int64(n_blocks),
                cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(), Int64(pos_b), Int64(0),
                grid_dim=h_q * _N_SPLITS, block_dim=32)
            ctx.synchronize()
            var t2 = perf_counter_ns()
            if r >= 3:
                pair_times.append(Int(t1 - t0))
                fuse_times.append(Int(t2 - t1))
        var pm = pair_times^
        var fm = fuse_times^
        for i in range(rounds - 1):
            for j2 in range(i + 1, rounds):
                if pm[j2] < pm[i]:
                    var t = pm[i]
                    pm[i] = pm[j2]
                    pm[j2] = t
                if fm[j2] < fm[i]:
                    var t2 = fm[i]
                    fm[i] = fm[j2]
                    fm[j2] = t2
        var pair_med = Float64(pm[rounds // 2]) / 1000.0
        var fuse_med = Float64(fm[rounds // 2]) / 1000.0
        print("BENCH n_keys=", n_keys_b, ": pair(kvprod+f2s4) = ", pair_med,
              " us | fused(f2s4k) = ", fuse_med, " us | pair/fused = ", pair_med / fuse_med)
    print("DRIVER DONE")
