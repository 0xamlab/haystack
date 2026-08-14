"""attention_forge.kvprod_f1 -- feat/llama-q80gap (2026-08-13): the LANE-FUSED no-QK-norm twin
of `native_kv_producer._native_kv_producer_kernel`, purpose-built for llama-family DECODE append
(m_rows=1, qk_norm=0) at TinyLlama shape (and any even d_head).

WHY (measured, not assumed)
---------------------------
The GPU-counter profile of the TinyLlama native fast path (`tinyllama_probe_counters_decode_
native.mojo`) measured the decode kvprod dispatch at 0.21ms/token = ~9.5us/layer -- roughly 2x
the ~4.5-5us per-dispatch floor the same profile measures for the trivially-small embed/argmax
dispatches. The qk_norm=0 decode append does almost no math (no RMSNorm reduction -- the llama
family rotates the RAW projection), yet the shared kernel still: allocates two `_MAX_HEAD_DIM`
shared F32 scratch arrays per threadgroup, publishes every element through shared + a
threadgroup barrier, then re-reads the partner half for the NeoX split-half exchange. All of
that machinery exists ONLY to move one value from lane `e` to the lane that pairs with `e +
n_pairs` -- and with `block_dim = d_head` the pair (e, e + d_head//2) is always exactly
d_head//2 lanes away.

THE FIX: run `block_dim = d_head // 2` and give each lane BOTH halves of its RoPE pair: lane
`l` owns elements `e = l` and `e + n_pairs`, loads both QKV values itself, rotates them with
the SAME cos/sin (indexed by the low element `e`, exactly as the reference), and writes both
outputs. No shared memory, no barrier, half the threads.

BYTE-IDENTICAL to the qk_norm=0 arm of `_native_kv_producer_kernel`: every arithmetic
expression is the same source formula evaluated on the same two F32 values (`o0 = a0*c - a1*s`,
`o1 = a0*s + a1*c`, `Float16(...)` narrowing) -- staging through shared memory added no
arithmetic, so removing it changes nothing about the bits; K/V/q_rot land at the SAME flat
indices (formulas carried over verbatim). qk_norm=1 is NOT covered (the RMSNorm reduction needs
a whole-head cross-lane sum with a specific shared-tree order; that family keeps the original
kernel) -- the engine gate dispatches this kernel only when `qk_norm == 0`.

MODULE NAMING: deliberately `kvprod_f1`, NOT `native_kv_producer_*` -- the shared
`_classify_attention_forge_pipeline` matches the `native_kv_producer` substring for the
ORIGINAL producer role, so a `native_kv_producer_f1` module would cross-wire the two (the exact
collision the batched producer avoided by naming itself `kvprod_batched`; same discipline).
Session-side discovery matches the unique `kvprod_f1` substring independently.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \\
      pixi run mojo build --emit object -I . -I ../attention_forge \\
        -o /tmp/kvprod_f1_forge.o ../attention_forge/kvprod_f1_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/kvprod_f1_forge.o \\
      ../attention_forge/generated/kvprod_f1_blob.c --symbol algenta_kvprod_f1_blob
"""

from std.gpu import thread_idx, block_idx

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]


def _kvprod_f1_kernel(
    q_rot: _F16P, k_native: _F16P, v_native: _F16P,
    qkv: _FP, qn_w: _FP, kn_w: _FP, cos_t: _FP, sin_t: _FP,
    pos_base: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    key_block_size: Int64, n_blocks: Int64, eps: Float32, m_rows: Int64,
    qk_norm: Int64,
):
    """Lane-fused qk_norm=0 producer. SIGNATURE-IDENTICAL to `_native_kv_producer_kernel` (same
    17 args, same positional order -- the `qk_norm` trailing flag included -- so the engine's
    descriptor wiring changes ONLY the pipeline index + block_dim), `block_dim = d_head // 2`,
    `grid_dim = (h_q + h_kv) * m_rows` as before. REQUIRES qk_norm == 0 at dispatch (engine
    gate; `qn_w`/`kn_w` are never read, exactly as the original's qk_norm=0 arm)."""
    var n_units = h_q + h_kv
    var bidx = Int64(block_idx.x)
    var b = bidx % n_units
    var m = bidx // n_units
    if m >= m_rows:
        return
    var pos = pos_base + m
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = m * n_qkv
    var row_q_rot = m * (h_q * d_head)

    var n_pairs = d_head // 2
    var e = Int64(thread_idx.x)  # 0 .. n_pairs-1; owns elements e AND e + n_pairs
    var is_q = b < h_q
    var head = b if is_q else b - h_q

    var src_lo = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    var a0 = qkv[Int(src_lo)]
    var a1 = qkv[Int(src_lo + n_pairs)]

    var c = cos_t[Int(pos * n_pairs + e)]
    var s = sin_t[Int(pos * n_pairs + e)]
    var o0 = a0 * c - a1 * s
    var o1 = a0 * s + a1 * c

    if is_q:
        # Q: UNCHANGED layout, [m_rows][h_q*d_head] row-major -- only the dtype narrows to F16.
        var qb = row_q_rot + head * d_head
        q_rot[Int(qb + e)] = Float16(o0)
        q_rot[Int(qb + e + n_pairs)] = Float16(o1)
    else:
        # K: native transposed packing -- SAME flat-index formula as the original producer.
        var hk = head
        var block = pos // key_block_size
        var kk = pos % key_block_size
        var block_base = (hk * n_blocks + block) * d_head
        k_native[Int((block_base + e) * key_block_size + kk)] = Float16(o0)
        k_native[Int((block_base + e + n_pairs) * key_block_size + kk)] = Float16(o1)

    if not is_q:
        # V: no RoPE, F16-narrow-and-pack into the native NATURAL layout -- both halves, SAME
        # flat-index formula as the original producer's unconditional V write.
        var hk = head
        var block = pos // key_block_size
        var kk = pos % key_block_size
        var v_row = row_qkv + (h_q + h_kv + head) * d_head
        var v_val0 = qkv[Int(v_row + e)]
        var v_val1 = qkv[Int(v_row + e + n_pairs)]
        var v_block_base = (hk * n_blocks + block) * key_block_size + kk
        v_native[Int(v_block_base * d_head + e)] = Float16(v_val0)
        v_native[Int(v_block_base * d_head + e + n_pairs)] = Float16(v_val1)
