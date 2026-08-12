"""attention_forge.native_kv_decode_attn_i8kv -- beat-llama.cpp campaign (2026-08-12): the
INT8-KV split-K decode partial, v4 per-key-scale SIMD-dequant variant, in its OWN module so the
blob's AIR name cannot collide with the f16 split-K family.

WHY A SEPARATE MODULE (naming is load-bearing here -- see REALRACE_RESULTS.md "THIRD discovery
collision" + the batched `kvprod_batched` precedent): the dev file `native_kv_decode_attn_splitk_
i8kv.mojo`'s 33-char module name truncates to EXACTLY `native_kv_decode_attn_splitk` at the AIR
28-char limit -- byte-identical to the f4u2 blob's name family, an unresolvable discovery
collision. THIS module's name is 26 chars (under the truncation limit, no truncation), so the AIR
name lands as `native_kv_decode_attn_i8kv_<hex>` and the session discovers it by its own
longest-first substring `"native_kv_decode_attn_i8kv"` (longer than the naive kernel's
`"native_kv_decode_attn"`, checked before it in the elif chain -- scan order irrelevant).

THE KERNEL: v4 of the int8-KV milestone (the v1/v2/v3 history lives in the dev file). SIMD int8
dequant on mm8.mojo's production-proven vecload4 pattern (load[width=4] -> SIMD[Int8,4] ->
.cast[DType.float32] -> SIMD scale-multiply), per-KEY absmax scales (incremental-friendly: decode
appends one key per token, no block re-quant; tighter numerics; the block/kk index arithmetic
deleted), Q splatted once, SIMD[Float32,4] O accumulator, f4u2's key-order online-softmax
recurrence preserved. Validated in the dev driver: consistency 0.0 vs v3 on the harness, 1.34x
@4096 / 1.48x @8192 vs f4u2. `key_block_size`/`n_blocks` stay in the signature for dispatch parity
with f4u2 (unused here).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build --emit object -I . -I ../attention_forge \\
        -o /tmp/native_kv_decode_attn_i8kv_forge.o \\
        ../attention_forge/native_kv_decode_attn_i8kv_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_i8kv_forge.o \\
      ../attention_forge/generated/native_kv_decode_attn_i8kv_blob.c \\
      --symbol algenta_native_kv_decode_attn_i8kv_blob
"""
from std.gpu import thread_idx, block_idx
from std.gpu.primitives.warp import shuffle_xor as _shuffle_xor
from std.math import exp

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _I8P = UnsafePointer[Int8, origin=MutAnyOrigin]

comptime _NEG_HUGE: Float32 = -1.0e30


def _warp_sum(v: Float32) -> Float32:
    var t = v + _shuffle_xor(v, UInt32(16))
    t = t + _shuffle_xor(t, UInt32(8))
    t = t + _shuffle_xor(t, UInt32(4))
    t = t + _shuffle_xor(t, UInt32(2))
    t = t + _shuffle_xor(t, UInt32(1))
    return t


def _native_kv_decode_splitk_partial_i8kv4(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_i8: _I8P, v_i8: _I8P, k_scale: _FP, v_scale: _FP,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """int8-KV partial, v4: PER-KEY scales (the engine-wiring design). v3 proved SIMD dequant wins
    (1.15-1.22x) but carried per-BLOCK q8_0 scales inherited from v2 -- for the engine, per-key
    scales are strictly better: (1) INCREMENTAL-FRIENDLY -- decode appends one key at a time, and a
    per-block absmax would force re-quantizing the whole 32-key block on every append, while a
    per-key absmax quantizes each key ONCE, forever; (2) TIGHTER numerics (each key scaled by its
    own max, not inflated by the block's largest key); (3) the kernel's scale LOAD COUNT is
    unchanged (one scale per key either way), so timing is preserved. BONUS: with per-key scales the
    block/kk bookkeeping (a vestige of the packed f16 layout) is no longer needed at all -- v4 reads
    the flat [hk][key][d_head] int8 layout directly by key index and drops that arithmetic.
    `key_block_size`/`n_blocks` stay in the signature for dispatch parity but are unused."""
    var idx = Int64(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var lane = Int64(thread_idx.x)
    var e0 = lane * 4
    var group = h_q // h_kv
    var hk = h // group

    var qv0 = Float32(q_native[Int(h * d_head + e0)])
    var qv1 = Float32(q_native[Int(h * d_head + e0 + 1)])
    var qv2 = Float32(q_native[Int(h * d_head + e0 + 2)])
    var qv3 = Float32(q_native[Int(h * d_head + e0 + 3)])
    var qv_v = SIMD[DType.float32, 4](qv0, qv1, qv2, qv3)

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o_v = SIMD[DType.float32, 4](0.0, 0.0, 0.0, 0.0)

    var row_words = d_head // 4
    var kv_row_base = hk * n_keys

    var j = key_start
    while j + 1 < key_end:
        var row_a = (kv_row_base + j) * row_words + lane
        var row_b = (kv_row_base + j + 1) * row_words + lane
        var ks_a = k_scale[Int(kv_row_base + j)]
        var ks_b = k_scale[Int(kv_row_base + j + 1)]
        var vs_a = v_scale[Int(kv_row_base + j)]
        var vs_b = v_scale[Int(kv_row_base + j + 1)]
        var kdf_a = k_i8.load[width=4](Int(row_a * 4)).cast[DType.float32]() * SIMD[DType.float32, 4](ks_a)
        var kdf_b = k_i8.load[width=4](Int(row_b * 4)).cast[DType.float32]() * SIMD[DType.float32, 4](ks_b)

        var prod_a = qv_v * kdf_a
        var prod_b = qv_v * kdf_b
        var partial_a = (prod_a[0] + prod_a[1]) + (prod_a[2] + prod_a[3])
        var partial_b = (prod_b[0] + prod_b[1]) + (prod_b[2] + prod_b[3])
        var s_a = _warp_sum(partial_a) * scale
        var s_b = _warp_sum(partial_b) * scale

        var nm_a = m if m > s_a else s_a
        var corr_a = exp(m - nm_a)
        var w_a = exp(s_a - nm_a)
        var vv_a = v_i8.load[width=4](Int(row_a * 4)).cast[DType.float32]()
        o_v = o_v * SIMD[DType.float32, 4](corr_a) + vv_a * SIMD[DType.float32, 4](w_a * vs_a)
        denom = denom * corr_a + w_a
        m = nm_a

        var nm_b = m if m > s_b else s_b
        var corr_b = exp(m - nm_b)
        var w_b = exp(s_b - nm_b)
        var vv_b = v_i8.load[width=4](Int(row_b * 4)).cast[DType.float32]()
        o_v = o_v * SIMD[DType.float32, 4](corr_b) + vv_b * SIMD[DType.float32, 4](w_b * vs_b)
        denom = denom * corr_b + w_b
        m = nm_b

        j += 2

    if j < key_end:
        var row = (kv_row_base + j) * row_words + lane
        var kdf = k_i8.load[width=4](Int(row * 4)).cast[DType.float32]() * SIMD[DType.float32, 4](k_scale[Int(kv_row_base + j)])
        var prod = qv_v * kdf
        var partial = (prod[0] + prod[1]) + (prod[2] + prod[3])
        var s = _warp_sum(partial) * scale
        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        var vv = v_i8.load[width=4](Int(row * 4)).cast[DType.float32]()
        o_v = o_v * SIMD[DType.float32, 4](corr) + vv * SIMD[DType.float32, 4](w * v_scale[Int(kv_row_base + j)])
        denom = denom * corr + w
        m = nm

    var out_idx = h * n_splits + sidx
    if key_start >= key_end:
        m_out[Int(out_idx)] = _NEG_HUGE
        l_out[Int(out_idx)] = Float32(0.0)
        o_out[Int(out_idx * d_head + e0 + 0)] = Float32(0.0)
        o_out[Int(out_idx * d_head + e0 + 1)] = Float32(0.0)
        o_out[Int(out_idx * d_head + e0 + 2)] = Float32(0.0)
        o_out[Int(out_idx * d_head + e0 + 3)] = Float32(0.0)
    else:
        m_out[Int(out_idx)] = m
        l_out[Int(out_idx)] = denom
        o_out[Int(out_idx * d_head + e0 + 0)] = o_v[0]
        o_out[Int(out_idx * d_head + e0 + 1)] = o_v[1]
        o_out[Int(out_idx * d_head + e0 + 2)] = o_v[2]
        o_out[Int(out_idx * d_head + e0 + 3)] = o_v[3]
