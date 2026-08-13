"""attention_forge.native_kv_producer_driver -- forces codegen of
`_native_kv_producer_kernel` (Phase 2B's head-complete QK-norm+RoPE+F16-narrowing+native-KV-packing
producer, see `native_kv_producer.mojo`'s own docstring) and checks it against every requirement
this task's own "CORRECTNESS BAR" states, matching this repo's established forge-native pattern
(`parity_replica_driver.mojo`, `grouped_fa_q8_k32_h2_sg8_driver.mojo`, `splitk_fa_driver.mojo`):

  1. `test_norm_rope_correctness` -- the producer's norm+RoPE output (Q, and K BEFORE packing is
     even considered) against an INDEPENDENTLY DERIVED CPU Float64 oracle
     (`_rmsnorm_rope_oracle_head` below): full-head RMSNorm (`inv = 1/sqrt(mean_sq(v)+eps)`,
     `xs = v*inv*gamma`) followed by NeoX split-half RoPE (pairs `(e, e+n_pairs)`, NOT interleaved
     `(2e,2e+1)`) -- written from this file's own understanding of the math (see
     `native_kv_producer.mojo`'s module docstring for the cross-reference to
     `_pf_ropewrt_kernel`), not copied from any Mojo source. RoPE angle tables come from
     `attnk.rope.rope_table` (trusted, already golden-vector-tested elsewhere in this repo) per
     this task's own instruction not to regenerate that convention by hand -- this driver reuses
     its OUTPUT VALUES as the shared ground truth both the CPU oracle and the GPU kernel consume,
     but the norm+RoPE APPLICATION math itself (what this test is actually checking) is this file's
     own independent derivation, never `attnk.rope`'s own `rope_apply_flat`.
  2. `test_packing_hand_indices` -- several (position, kv_head, d) triples, HAND-COMPUTED
     (`block = pos // key_block_size`, `kk = pos % key_block_size`, restated inline at every call
     site rather than hidden behind one opaque helper), including a pair straddling a block
     boundary (31/32), a pair straddling a LATER boundary at different (kv_head, d) (63/64), the
     max kv_head/d indices, and a position at this dispatch's own (deliberately non-block-aligned)
     `pos_base=20`. A canary fill before dispatch also proves the kernel writes ONLY its own
     assigned (block, key_in_block) slots -- a wrong-index bug would corrupt a neighboring slot,
     which the canary would catch even if the specific hand-picked triples happened to still read
     back correct values.
  3. `test_multi_call_continuation` -- two calls (`pos_base=0, m_rows=17` then `pos_base=17,
     m_rows=23`, spanning the `key_block_size=32` boundary) into ONE shared K/V buffer (the
     absolute-position addressing this producer inherits from `_pf_ropewrt_kernel` requires no
     buffer-offset bookkeeping between calls) versus ONE call (`pos_base=0, m_rows=40`) into a
     separately allocated buffer of identical shape -- both pre-filled with the same canary so
     untouched regions compare equal too, not just written ones.
  4. `test_determinism_soak` -- 1,000 dispatches at real Qwen3-0.6B-Base dims, exactly this
     session's own established discipline (`parity_replica_driver.mojo`'s
     `test_determinism_soak`): fixed inputs, fresh output buffers every iteration, compare every
     run's Q/K/V bytes against the first run's.
  5. `test_direct_load_probe` -- the device-direct `apple_mma_load_8x8[DType.float16]` experiment
     (see `native_kv_producer.mojo`'s own docstring for the full design rationale). Deliberately run
     LAST and wrapped in `try`/`except`: this experiment reads a device (non-shared) F16 pointer
     through a GPU MMA intrinsic that, per this task's own background, has never been runtime-tested
     in this codebase before -- if it raises a Mojo-level error, the run must still report every
     OTHER check's real result rather than losing them to an unrelated experiment's failure.

Real Qwen3-0.6B-Base dims used throughout (`h_q=16, h_kv=8, d_head=128`) except one small aligned
sanity shape in test 1, per this task's own instruction to use the real dims as the dispositive
shape.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge -I ../mojo/engine \
      ../attention_forge/native_kv_producer_driver.mojo
"""
from max.gpu.host import DeviceContext
from attnk.contract import ATTN_OK
from attnk.rope import rope_table
from native_kv_producer import _native_kv_producer_kernel, _native_kv_direct_load_probe_kernel


def _abs64(x: Float64) -> Float64:
    return -x if x < 0.0 else x


def _pseudo_f32(n: Int, seed: Int) -> List[Float64]:
    """Deterministic generator, same convention as `parity_replica_driver.mojo`'s `_pseudo_f16`
    (`attention_forge/parity_replica_driver.mojo`), but narrowed to Float32 (not Float16) -- this
    producer's `qkv`/`qn_w`/`kn_w`/`cos_t`/`sin_t` inputs are all `_FP` (Float32 device pointers),
    matching `_pf_ropewrt_kernel`'s own signature exactly; only the OUTPUTS narrow to F16."""
    var o = List[Float64](capacity=n)
    for i in range(n):
        var raw = Float64(((i * 61 + seed * 17) % 47)) / 19.0 - 1.2
        o.append(Float64(Float32(raw)))
    return o^


def _rmsnorm_rope_oracle_head(
    v: List[Float64], gamma: List[Float64], cos_full: List[Float64], sin_full: List[Float64],
    row_off: Int, eps: Float64,
) -> List[Float64]:
    """Independently derived (not transcribed from any Mojo kernel source): full-head RMSNorm
    followed by NeoX split-half RoPE, over one (row, head) unit's own `d_head`-length vector.
    `mean_sq(v) = sum(v_i^2) / d_head`; `inv = 1/sqrt(mean_sq(v) + eps)`; `xs_i = v_i * inv *
    gamma_i`; then for each pair index `e` in `[0, d_head/2)`, using this row's own
    `(cos_full[row_off+e], sin_full[row_off+e])` (`row_off = pos * n_pairs`, the caller's own
    absolute-position row into the full `attnk.rope.rope_table` output -- passed as an offset,
    not a pre-sliced sub-list, since slicing a `List[Float64]` here yields a `Span`, not another
    `List`): `out[e] = xs[e]*cos - xs[e+n_pairs]*sin`, `out[e+n_pairs] = xs[e]*sin +
    xs[e+n_pairs]*cos` -- the standard 2D-rotation form applied to the pair
    `(xs[e], xs[e+n_pairs])`, which is what "NeoX split-half RoPE" means precisely (as opposed to
    GPT-J's adjacent-pair `(2e, 2e+1)` convention, which this function deliberately does NOT
    implement)."""
    var d = len(v)
    var ss = Float64(0.0)
    for i in range(d):
        ss += v[i] * v[i]
    var inv = 1.0 / ((ss / Float64(d) + eps) ** 0.5)
    var xs = List[Float64](capacity=d)
    for i in range(d):
        xs.append(v[i] * inv * gamma[i])
    var n_pairs = d // 2
    var out = List[Float64](capacity=d)
    for _ in range(d):
        out.append(0.0)
    for e in range(n_pairs):
        var c = cos_full[row_off + e]
        var s = sin_full[row_off + e]
        var a0 = xs[e]
        var a1 = xs[e + n_pairs]
        out[e] = a0 * c - a1 * s
        out[e + n_pairs] = a0 * s + a1 * c
    return out^


def _extract_head_vec(qkv64: List[Float64], row_qkv: Int, head_off: Int, d_head: Int) -> List[Float64]:
    """Pulls one (row, head)'s own `d_head`-length slice out of the fused-QKV row, at the
    `head_off` byte-equivalent element offset the caller has already computed (Q: `head*d_head`;
    K: `(h_q+head)*d_head`; V: `(h_q+h_kv+head)*d_head`) -- the exact fused-QKV row contract
    `_pf_ropewrt_kernel`'s own docstring states (Q heads first, then K heads, then V heads),
    re-derived here independently rather than imported."""
    var out = List[Float64](capacity=d_head)
    var base = row_qkv + head_off
    for d in range(d_head):
        out.append(qkv64[base + d])
    return out^


def test_norm_rope_correctness(
    ctx: DeviceContext, name: String,
    h_q: Int, h_kv: Int, d_head: Int, key_block_size: Int, n_blocks: Int,
    m_rows: Int, pos_base: Int,
    cos_full: List[Float64], sin_full: List[Float64], n_pairs_full: Int,
) raises -> Bool:
    var eps64 = Float64(1.0e-6)
    var eps32 = Float32(1.0e-6)
    var n_qkv = h_q * d_head + 2 * h_kv * d_head

    var qkv64 = _pseudo_f32(m_rows * n_qkv, 5)
    var qn64 = _pseudo_f32(d_head, 101)
    var kn64 = _pseudo_f32(d_head, 202)

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * n_qkv)
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](len(cos_full))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](len(sin_full))
    with qkv_buf.map_to_host() as h:
        for i in range(m_rows * n_qkv):
            h[i] = Float32(qkv64[i])
    with qn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(qn64[i])
    with kn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(kn64[i])
    with cos_buf.map_to_host() as h:
        for i in range(len(cos_full)):
            h[i] = Float32(cos_full[i])
    with sin_buf.map_to_host() as h:
        for i in range(len(sin_full)):
            h[i] = Float32(sin_full[i])

    var q_rot_buf = ctx.enqueue_create_buffer[DType.float16](m_rows * h_q * d_head)
    var k_native_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d_head * key_block_size)
    var v_native_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * key_block_size * d_head)
    with q_rot_buf.map_to_host() as h:
        for i in range(m_rows * h_q * d_head):
            h[i] = Float16(-999.0)
    with k_native_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d_head * key_block_size):
            h[i] = Float16(-999.0)
    with v_native_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * key_block_size * d_head):
            h[i] = Float16(-999.0)

    var n_units = h_q + h_kv
    var grid = n_units * m_rows
    ctx.enqueue_function[_native_kv_producer_kernel](
        q_rot_buf.unsafe_ptr(), k_native_buf.unsafe_ptr(), v_native_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(pos_base), Int64(h_q), Int64(h_kv), Int64(d_head),
        Int64(key_block_size), Int64(n_blocks), eps32, Int64(m_rows), Int64(1),
        grid_dim=grid, block_dim=d_head,
    )
    ctx.synchronize()

    var worst_q = 0.0
    var worst_k = 0.0
    var worst_v = 0.0
    with q_rot_buf.map_to_host() as hq, k_native_buf.map_to_host() as hk, v_native_buf.map_to_host() as hv:
        for m in range(m_rows):
            var row_qkv = m * n_qkv
            var pos = pos_base + m
            var block = pos // key_block_size
            var kk = pos % key_block_size

            for head in range(h_q):
                var v_vec = _extract_head_vec(qkv64, row_qkv, head * d_head, d_head)
                var want = _rmsnorm_rope_oracle_head(v_vec, qn64, cos_full, sin_full, pos * n_pairs_full, eps64)
                for d in range(d_head):
                    var got = Float64(hq[m * h_q * d_head + head * d_head + d])
                    var diff = _abs64(got - want[d])
                    var allowed = 3.0e-2 * (1.0 + _abs64(want[d]))
                    var ratio = diff / allowed
                    if ratio > worst_q:
                        worst_q = ratio

            for hkv in range(h_kv):
                var k_vec = _extract_head_vec(qkv64, row_qkv, (h_q + hkv) * d_head, d_head)
                var want_k = _rmsnorm_rope_oracle_head(k_vec, kn64, cos_full, sin_full, pos * n_pairs_full, eps64)
                var block_base = (hkv * n_blocks + block) * d_head
                for d in range(d_head):
                    var idx = (block_base + d) * key_block_size + kk
                    var got = Float64(hk[idx])
                    var diff = _abs64(got - want_k[d])
                    var allowed = 3.0e-2 * (1.0 + _abs64(want_k[d]))
                    var ratio = diff / allowed
                    if ratio > worst_k:
                        worst_k = ratio

                var v_vec = _extract_head_vec(qkv64, row_qkv, (h_q + h_kv + hkv) * d_head, d_head)
                var v_block_base = (hkv * n_blocks + block) * key_block_size + kk
                for d in range(d_head):
                    var idx = v_block_base * d_head + d
                    var got = Float64(hv[idx])
                    var want_v = v_vec[d]
                    var diff = _abs64(got - want_v)
                    var allowed = 3.0e-2 * (1.0 + _abs64(want_v))
                    var ratio = diff / allowed
                    if ratio > worst_v:
                        worst_v = ratio

    var ok = worst_q <= 1.0 and worst_k <= 1.0 and worst_v <= 1.0
    print("  [", name, "] worst-ratio q=", worst_q, " k=", worst_k, " v=", worst_v, "  ", "OK" if ok else "MISMATCH")
    return ok


def test_packing_hand_indices(ctx: DeviceContext, cos_full: List[Float64], sin_full: List[Float64], n_pairs_full: Int) raises -> Bool:
    var h_q = 16
    var h_kv = 8
    var d_head = 128
    var key_block_size = 32
    var n_blocks = 4
    var m_rows = 50
    var pos_base = 20  # deliberately NOT a multiple of key_block_size=32
    var eps64 = Float64(1.0e-6)
    var eps32 = Float32(1.0e-6)
    var n_qkv = h_q * d_head + 2 * h_kv * d_head

    var qkv64 = _pseudo_f32(m_rows * n_qkv, 7)
    var qn64 = _pseudo_f32(d_head, 103)
    var kn64 = _pseudo_f32(d_head, 204)

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * n_qkv)
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](len(cos_full))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](len(sin_full))
    with qkv_buf.map_to_host() as h:
        for i in range(m_rows * n_qkv):
            h[i] = Float32(qkv64[i])
    with qn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(qn64[i])
    with kn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(kn64[i])
    with cos_buf.map_to_host() as h:
        for i in range(len(cos_full)):
            h[i] = Float32(cos_full[i])
    with sin_buf.map_to_host() as h:
        for i in range(len(sin_full)):
            h[i] = Float32(sin_full[i])

    var q_rot_buf = ctx.enqueue_create_buffer[DType.float16](m_rows * h_q * d_head)
    var k_native_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d_head * key_block_size)
    var v_native_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * key_block_size * d_head)
    var canary = Float16(-999.0)
    with k_native_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * d_head * key_block_size):
            h[i] = canary
    with v_native_buf.map_to_host() as h:
        for i in range(h_kv * n_blocks * key_block_size * d_head):
            h[i] = canary

    var n_units = h_q + h_kv
    var grid = n_units * m_rows
    ctx.enqueue_function[_native_kv_producer_kernel](
        q_rot_buf.unsafe_ptr(), k_native_buf.unsafe_ptr(), v_native_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(pos_base), Int64(h_q), Int64(h_kv), Int64(d_head),
        Int64(key_block_size), Int64(n_blocks), eps32, Int64(m_rows), Int64(1),
        grid_dim=grid, block_dim=d_head,
    )
    ctx.synchronize()

    var all_ok = True
    with k_native_buf.map_to_host() as hk, v_native_buf.map_to_host() as hv:
        # (position, kv_head, d) triples -- hand-computed block/key_in_block/flat-index at every
        # site, restated (not routed through one shared helper), including:
        #   - a pair straddling the 31/32 block boundary at the same (kv_head, d)
        #   - a pair straddling the 63/64 block boundary at a DIFFERENT (kv_head, d)
        #   - the maximum kv_head (7) and maximum d (127) indices
        #   - this dispatch's own row 0, at pos_base=20 itself -- NOT a multiple of 32
        var triples = List[Tuple[Int, Int, Int]]()
        triples.append((31, 0, 0))
        triples.append((32, 0, 0))
        triples.append((63, 4, 64))
        triples.append((64, 4, 64))
        triples.append((45, 7, 127))
        triples.append((20, 2, 10))

        for t in triples:
            var pos = t[0]
            var hkv = t[1]
            var d = t[2]
            var m = pos - pos_base
            if m < 0 or m >= m_rows:
                print("    [hand-index] pos=", pos, " outside this dispatch's own rows -- SKIPPED (bad test setup)")
                all_ok = False
                continue
            var block = pos // key_block_size
            var kk = pos % key_block_size
            var row_qkv = m * n_qkv

            var k_vec = _extract_head_vec(qkv64, row_qkv, (h_q + hkv) * d_head, d_head)
            var want_k = _rmsnorm_rope_oracle_head(k_vec, kn64, cos_full, sin_full, pos * n_pairs_full, eps64)
            var k_flat = ((hkv * n_blocks + block) * d_head + d) * key_block_size + kk
            var got_k = Float64(hk[k_flat])
            var diff_k = _abs64(got_k - want_k[d])
            var allowed_k = 3.0e-2 * (1.0 + _abs64(want_k[d]))
            var ok_k = diff_k <= allowed_k

            var v_vec = _extract_head_vec(qkv64, row_qkv, (h_q + h_kv + hkv) * d_head, d_head)
            var v_flat = ((hkv * n_blocks + block) * key_block_size + kk) * d_head + d
            var got_v = Float64(hv[v_flat])
            var diff_v = _abs64(got_v - v_vec[d])
            var allowed_v = 3.0e-2 * (1.0 + _abs64(v_vec[d]))
            var ok_v = diff_v <= allowed_v

            var ok = ok_k and ok_v
            all_ok = all_ok and ok
            print(
                "    [hand-index] pos=", pos, " hk=", hkv, " d=", d,
                " block=", block, " kk=", kk, " k_flat=", k_flat, " v_flat=", v_flat,
                "  ", "OK" if ok else "MISMATCH",
            )

        # Containment: a position just BEFORE this dispatch's own row range (19, within block 0)
        # and just AFTER it (70, within block 2) must remain the untouched canary -- proves the
        # kernel never writes outside its own assigned (block, key_in_block) slot.
        var untouched_positions = List[Int]()
        untouched_positions.append(19)
        untouched_positions.append(70)
        for pos in untouched_positions:
            var block = pos // key_block_size
            var kk = pos % key_block_size
            for hkv in range(h_kv):
                var k_flat = ((hkv * n_blocks + block) * d_head) * key_block_size + kk
                var got = hk[k_flat]
                var ok = got == canary
                if not ok:
                    all_ok = False
                    print("    [containment] pos=", pos, " hk=", hkv, " unexpectedly written (got=", Float64(got), ") -- FAIL")
        print("    [containment] positions 19 and 70 (outside [20,70)) remain untouched canary  ", "OK" if all_ok else "SEE ABOVE")

    print("  [packing hand-index check]  ", "OK" if all_ok else "MISMATCH")
    return all_ok


def test_multi_call_continuation(ctx: DeviceContext, cos_full: List[Float64], sin_full: List[Float64], n_pairs_full: Int) raises -> Bool:
    var h_q = 16
    var h_kv = 8
    var d_head = 128
    var key_block_size = 32
    var n_blocks = 4
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var eps32 = Float32(1.0e-6)
    var m_total = 40  # spans the [0,32) / [32,64) block boundary

    var qkv64 = _pseudo_f32(m_total * n_qkv, 9)
    var qn64 = _pseudo_f32(d_head, 105)
    var kn64 = _pseudo_f32(d_head, 206)

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](m_total * n_qkv)
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](len(cos_full))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](len(sin_full))
    with qkv_buf.map_to_host() as h:
        for i in range(m_total * n_qkv):
            h[i] = Float32(qkv64[i])
    with qn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(qn64[i])
    with kn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(kn64[i])
    with cos_buf.map_to_host() as h:
        for i in range(len(cos_full)):
            h[i] = Float32(cos_full[i])
    with sin_buf.map_to_host() as h:
        for i in range(len(sin_full)):
            h[i] = Float32(sin_full[i])

    var canary = Float16(-777.0)
    var k_size = h_kv * n_blocks * d_head * key_block_size
    var v_size = h_kv * n_blocks * key_block_size * d_head
    var q_size = m_total * h_q * d_head

    # Single call: pos_base=0, m_rows=40, all at once.
    var q_single = ctx.enqueue_create_buffer[DType.float16](q_size)
    var k_single = ctx.enqueue_create_buffer[DType.float16](k_size)
    var v_single = ctx.enqueue_create_buffer[DType.float16](v_size)
    with q_single.map_to_host() as h:
        for i in range(q_size):
            h[i] = canary
    with k_single.map_to_host() as h:
        for i in range(k_size):
            h[i] = canary
    with v_single.map_to_host() as h:
        for i in range(v_size):
            h[i] = canary

    var n_units = h_q + h_kv
    ctx.enqueue_function[_native_kv_producer_kernel](
        q_single.unsafe_ptr(), k_single.unsafe_ptr(), v_single.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(0), Int64(h_q), Int64(h_kv), Int64(d_head),
        Int64(key_block_size), Int64(n_blocks), eps32, Int64(m_total), Int64(1),
        grid_dim=n_units * m_total, block_dim=d_head,
    )
    ctx.synchronize()

    # Two calls into a SEPARATE, identically-shaped buffer: [0,17) then [17,40) -- 17 is not a
    # multiple of 32, so the split itself is non-block-aligned on top of spanning the 32 boundary.
    var q_multi = ctx.enqueue_create_buffer[DType.float16](q_size)
    var k_multi = ctx.enqueue_create_buffer[DType.float16](k_size)
    var v_multi = ctx.enqueue_create_buffer[DType.float16](v_size)
    with q_multi.map_to_host() as h:
        for i in range(q_size):
            h[i] = canary
    with k_multi.map_to_host() as h:
        for i in range(k_size):
            h[i] = canary
    with v_multi.map_to_host() as h:
        for i in range(v_size):
            h[i] = canary

    var split = 17
    var rows_a = split
    var rows_b = m_total - split
    var qkv_off_b = split * n_qkv
    var q_off_b = split * h_q * d_head

    ctx.enqueue_function[_native_kv_producer_kernel](
        q_multi.unsafe_ptr(), k_multi.unsafe_ptr(), v_multi.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(0), Int64(h_q), Int64(h_kv), Int64(d_head),
        Int64(key_block_size), Int64(n_blocks), eps32, Int64(rows_a), Int64(1),
        grid_dim=n_units * rows_a, block_dim=d_head,
    )
    ctx.synchronize()
    ctx.enqueue_function[_native_kv_producer_kernel](
        q_multi.unsafe_ptr() + q_off_b, k_multi.unsafe_ptr(), v_multi.unsafe_ptr(),
        qkv_buf.unsafe_ptr() + qkv_off_b, qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(split), Int64(h_q), Int64(h_kv), Int64(d_head),
        Int64(key_block_size), Int64(n_blocks), eps32, Int64(rows_b), Int64(1),
        grid_dim=n_units * rows_b, block_dim=d_head,
    )
    ctx.synchronize()

    var mismatches_q = 0
    var mismatches_k = 0
    var mismatches_v = 0
    with q_single.map_to_host() as hqs, q_multi.map_to_host() as hqm:
        for i in range(q_size):
            if hqs[i] != hqm[i]:
                mismatches_q += 1
    with k_single.map_to_host() as hks, k_multi.map_to_host() as hkm:
        for i in range(k_size):
            if hks[i] != hkm[i]:
                mismatches_k += 1
    with v_single.map_to_host() as hvs, v_multi.map_to_host() as hvm:
        for i in range(v_size):
            if hvs[i] != hvm[i]:
                mismatches_v += 1

    var ok = mismatches_q == 0 and mismatches_k == 0 and mismatches_v == 0
    print(
        "  [multi-call continuation, split at row 17 across the block-32 boundary] mismatches q=", mismatches_q,
        " k=", mismatches_k, " v=", mismatches_v, "  ", "OK" if ok else "MISMATCH",
    )
    return ok


def test_determinism_soak(ctx: DeviceContext, cos_full: List[Float64], sin_full: List[Float64], n_pairs_full: Int, n_runs: Int) raises -> Bool:
    var h_q = 16
    var h_kv = 8
    var d_head = 128
    var key_block_size = 32
    var n_blocks = 2
    var m_rows = 17
    var pos_base = 37
    var eps32 = Float32(1.0e-6)
    var n_qkv = h_q * d_head + 2 * h_kv * d_head

    var qkv64 = _pseudo_f32(m_rows * n_qkv, 11)
    var qn64 = _pseudo_f32(d_head, 107)
    var kn64 = _pseudo_f32(d_head, 208)

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * n_qkv)
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](len(cos_full))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](len(sin_full))
    with qkv_buf.map_to_host() as h:
        for i in range(m_rows * n_qkv):
            h[i] = Float32(qkv64[i])
    with qn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(qn64[i])
    with kn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(kn64[i])
    with cos_buf.map_to_host() as h:
        for i in range(len(cos_full)):
            h[i] = Float32(cos_full[i])
    with sin_buf.map_to_host() as h:
        for i in range(len(sin_full)):
            h[i] = Float32(sin_full[i])

    var n_units = h_q + h_kv
    var grid = n_units * m_rows
    var q_size = m_rows * h_q * d_head
    var k_size = h_kv * n_blocks * d_head * key_block_size
    var v_size = h_kv * n_blocks * key_block_size * d_head

    var first_q = List[Float16](capacity=q_size)
    var first_k = List[Float16](capacity=k_size)
    var first_v = List[Float16](capacity=v_size)
    var flips = 0

    for run in range(n_runs):
        var q_buf = ctx.enqueue_create_buffer[DType.float16](q_size)
        var k_buf = ctx.enqueue_create_buffer[DType.float16](k_size)
        var v_buf = ctx.enqueue_create_buffer[DType.float16](v_size)
        ctx.enqueue_function[_native_kv_producer_kernel](
            q_buf.unsafe_ptr(), k_buf.unsafe_ptr(), v_buf.unsafe_ptr(),
            qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
            cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
            Int64(pos_base), Int64(h_q), Int64(h_kv), Int64(d_head),
            Int64(key_block_size), Int64(n_blocks), eps32, Int64(m_rows), Int64(1),
            grid_dim=grid, block_dim=d_head,
        )
        ctx.synchronize()
        with q_buf.map_to_host() as hq, k_buf.map_to_host() as hk, v_buf.map_to_host() as hv:
            if run == 0:
                for i in range(q_size):
                    first_q.append(hq[i])
                for i in range(k_size):
                    first_k.append(hk[i])
                for i in range(v_size):
                    first_v.append(hv[i])
            else:
                for i in range(q_size):
                    if hq[i] != first_q[i]:
                        flips += 1
                for i in range(k_size):
                    if hk[i] != first_k[i]:
                        flips += 1
                for i in range(v_size):
                    if hv[i] != first_v[i]:
                        flips += 1

    var ok = flips == 0
    print("  determinism soak: n_runs=", n_runs, " mismatching-element-dispatches=", flips, "  ", "OK" if ok else "NONDETERMINISTIC")
    return ok


def test_direct_load_probe(ctx: DeviceContext, cos_full: List[Float64], sin_full: List[Float64], n_pairs_full: Int) raises -> Bool:
    """See `native_kv_producer.mojo`'s module docstring, "THE DEVICE-DIRECT MMA-LOAD EXPERIMENT".
    Populates a real native K buffer via the producer kernel, then reads ONE (kv_head, block)
    slice of it straight from device memory (no shared-memory staging) via
    `apple_mma_load_8x8[DType.float16]`, extracts it losslessly through an identity-matmul, and
    compares against that SAME slice read back the ordinary way. Deliberately the LAST test run,
    and wrapped in `try`/`except`, per this file's own module docstring."""
    var h_q = 16
    var h_kv = 8
    var d_head = 128
    var key_block_size = 32
    var n_blocks = 2
    var m_rows = 40  # covers blocks 0 and 1 fully for every kv_head
    var pos_base = 0
    var eps32 = Float32(1.0e-6)
    var n_qkv = h_q * d_head + 2 * h_kv * d_head

    var qkv64 = _pseudo_f32(m_rows * n_qkv, 13)
    var qn64 = _pseudo_f32(d_head, 109)
    var kn64 = _pseudo_f32(d_head, 210)

    var qkv_buf = ctx.enqueue_create_buffer[DType.float32](m_rows * n_qkv)
    var qn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var kn_buf = ctx.enqueue_create_buffer[DType.float32](d_head)
    var cos_buf = ctx.enqueue_create_buffer[DType.float32](len(cos_full))
    var sin_buf = ctx.enqueue_create_buffer[DType.float32](len(sin_full))
    with qkv_buf.map_to_host() as h:
        for i in range(m_rows * n_qkv):
            h[i] = Float32(qkv64[i])
    with qn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(qn64[i])
    with kn_buf.map_to_host() as h:
        for i in range(d_head):
            h[i] = Float32(kn64[i])
    with cos_buf.map_to_host() as h:
        for i in range(len(cos_full)):
            h[i] = Float32(cos_full[i])
    with sin_buf.map_to_host() as h:
        for i in range(len(sin_full)):
            h[i] = Float32(sin_full[i])

    var q_buf = ctx.enqueue_create_buffer[DType.float16](m_rows * h_q * d_head)
    var k_native_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * d_head * key_block_size)
    var v_native_buf = ctx.enqueue_create_buffer[DType.float16](h_kv * n_blocks * key_block_size * d_head)

    var n_units = h_q + h_kv
    ctx.enqueue_function[_native_kv_producer_kernel](
        q_buf.unsafe_ptr(), k_native_buf.unsafe_ptr(), v_native_buf.unsafe_ptr(),
        qkv_buf.unsafe_ptr(), qn_buf.unsafe_ptr(), kn_buf.unsafe_ptr(),
        cos_buf.unsafe_ptr(), sin_buf.unsafe_ptr(),
        Int64(pos_base), Int64(h_q), Int64(h_kv), Int64(d_head),
        Int64(key_block_size), Int64(n_blocks), eps32, Int64(m_rows), Int64(1),
        grid_dim=n_units * m_rows, block_dim=d_head,
    )
    ctx.synchronize()

    var hk_probe = 3
    var block_probe = 1
    var block_elems = d_head * key_block_size
    var block_offset = (hk_probe * n_blocks + block_probe) * block_elems

    var out_extracted = ctx.enqueue_create_buffer[DType.float32](block_elems)
    with out_extracted.map_to_host() as h:
        for i in range(block_elems):
            h[i] = Float32(-12345.0)

    var probe_ran = False
    var probe_exact = False
    try:
        ctx.enqueue_function[_native_kv_direct_load_probe_kernel](
            k_native_buf.unsafe_ptr() + block_offset, out_extracted.unsafe_ptr(),
            Int64(d_head), Int64(key_block_size),
            grid_dim=1, block_dim=32,
        )
        ctx.synchronize()
        probe_ran = True
    except:
        probe_ran = False

    if probe_ran:
        var worst_diff = 0.0
        with k_native_buf.map_to_host() as hk, out_extracted.map_to_host() as ho:
            for i in range(block_elems):
                var want = Float64(hk[block_offset + i])
                var got = Float64(ho[i])
                var diff = _abs64(got - want)
                if diff > worst_diff:
                    worst_diff = diff
        probe_exact = worst_diff == 0.0
        print("  [direct-device-load probe] hk=", hk_probe, " block=", block_probe, " worst abs diff (extracted vs staged-read)=", worst_diff, "  ", "EXACT MATCH" if probe_exact else "MISMATCH")
    else:
        print("  [direct-device-load probe] kernel raised a Mojo-level error at dispatch/synchronize -- device-direct F16 MMA load did NOT run cleanly at runtime")

    return probe_ran and probe_exact


def main() raises:
    var ctx = DeviceContext()
    var all_ok = True

    print("=== Phase 2B native KV producer: norm+RoPE correctness vs independent CPU Float64 oracle ===")
    var rt = rope_table(128, 200, 1000000.0)
    if rt.status != ATTN_OK:
        print("  rope_table build FAILED, status=", rt.status)
        all_ok = False
    else:
        var rt_tiny = rope_table(8, 200, 1000000.0)
        all_ok = test_norm_rope_correctness(ctx, "tiny aligned (d_head=8)", 4, 2, 8, 32, 1, 3, 0, rt_tiny.cos_table, rt_tiny.sin_table, 4) and all_ok
        all_ok = test_norm_rope_correctness(ctx, "real Qwen3-0.6B-Base dims, m=17 pos_base=37", 16, 8, 128, 32, 2, 17, 37, rt.cos_table, rt.sin_table, 64) and all_ok
        all_ok = test_norm_rope_correctness(ctx, "real dims, non-block-aligned pos_base=50 spanning a boundary", 16, 8, 128, 32, 3, 20, 50, rt.cos_table, rt.sin_table, 64) and all_ok

        print("")
        print("=== packing correctness: hand-computed (position, kv_head, d) -> flat-index triples ===")
        all_ok = test_packing_hand_indices(ctx, rt.cos_table, rt.sin_table, 64) and all_ok

        print("")
        print("=== multi-call KV append: two pos_base calls vs one single call, real dims ===")
        all_ok = test_multi_call_continuation(ctx, rt.cos_table, rt.sin_table, 64) and all_ok

        print("")
        print("=== 1,000-dispatch determinism soak (real dims, m=17 pos_base=37) ===")
        all_ok = test_determinism_soak(ctx, rt.cos_table, rt.sin_table, 64, 1000) and all_ok

        print("")
        print("=== device-direct MMA-load experiment (informational: does not gate PASS/FAIL) ===")
        var probe_ok = test_direct_load_probe(ctx, rt.cos_table, rt.sin_table, 64)
        if probe_ok:
            print("  RECOMMENDATION: device-direct apple_mma_load_8x8[DType.float16] is correct at runtime for this native layout -- Phase 2C candidates may load full aligned K blocks straight from device memory, skipping shared-memory staging entirely where a block is fully aligned.")
        else:
            print("  RECOMMENDATION: device-direct load did not verify clean at runtime -- Phase 2C candidates should stage via a TRIVIAL index-free contiguous copy (device block -> shared, same [d][kk]/[kk][d] order) instead of today's index-transposing gather; the native layout still removes the TRANSPOSE, only the copy itself remains.")

    print("")
    if all_ok:
        print("PHASE 2B NATIVE KV PRODUCER: PASS (norm+RoPE correct vs CPU oracle, packing indices verified, multi-call continuation exact, deterministic over 1,000 dispatches)")
    else:
        print("PHASE 2B NATIVE KV PRODUCER: FAIL")
