"""attention_forge.native_kv_decode_attn_splitk_bf2 -- feat/batched-llama (2026-08-14): the
d_head=64 (llama-family) BATCHED / continuous-batching split-K decode partial -- the batched twin
of `native_kv_decode_attn_splitk_f2._native_kv_decode_splitk_partial_kernel_f2u2`, exactly the way
`native_kv_decode_attn_splitk_batched._native_kv_decode_splitk_partial_batched_kernel_f4u2` is the
batched twin of the d_head=128 single-stream f4u2.

WHY A SEPARATE MODULE
----------------------
The shipped batched partial blob (`native_kv_decode_attn_splitk_batched`, the f4u2 family) runs
one simdgroup per (sequence, head, split) at `block_dim = d_head // 4` -- for d_head=64 that is 16
threads (half a SIMD group -- `_warp_sum` would sum nonexistent lanes), so a d_head=64 model cannot
dispatch it. This module's kernel keeps the EXACT one-simdgroup-per-(seq, head, split) shape with
block_dim=32 FIXED and two head-elements per lane (32 lanes x 2 = 64 = d_head): each key's dot
product is a single `simd_sum` over the 32 lanes, NO cross-group barrier, NO shared scratch -- the
f2/f2u2 single-stream reduction translated to the batched indirection. REQUIRES d_head == 64 at
dispatch (the engine's own gate; the kernel covers exactly 64 elements).

CONTRACT, IDENTICAL to the d128 batched pair (deliberate): PARTIAL writes UNNORMALIZED `(m, l, o)`
partials at the globally-flattened index `idx = b * (h_q*n_splits) + h * n_splits + sidx =
block_idx.x` (a `[B, h_q, n_splits]` layout), o UNNORMALIZED, same finite `_NEG_HUGE` empty-split
sentinel, so the engine's `_batched_splitk_merge_kernel_simd` merges this kernel's output COMPLETELY
UNCHANGED (merge is layout-agnostic over d_head: `grid = B*h_q`, `block_dim = d_head`). Per-key math
is byte-for-byte the single-stream `_f2u2` body (16 independent loads in flight for the key pair,
pipelined simd_sums, odd-key epilogue, key-order online softmax) -- only the sequence decode (b from
block_idx.x), the per-sequence key count (`nkeys[b]` read once per threadgroup), the KV element
offset (`kv_off = b * kv_stride`, uniform-stride), and the Q row selection
(`q_native[b*h_q*d_head + h*d_head + e]`) differ. So a batch of B d64 sequences computes BIT-IDENTICAL
per-sequence partials to B single-stream f2u2 dispatches -- the byte-identical-batched-vs-single
property the d128 f4u2 batched pair already proved.

DISCOVERY NAMING: module name `native_kv_decode_attn_splitk_bf2` (32 chars -- fits the AIR name's
~32-char truncation budget; empirically re-verified on the forged blob before wiring, same as the
f2s4 truncation caution). It CONTAINS the generic `native_kv_decode_attn_splitk` substring, so the
session's discovery checks the LONGER `native_kv_decode_attn_splitk_bf2` substring BEFORE the
generic split-K arm -- same longest-first discipline as the `_bat`/`_f2s`/`_f2` arms. It does NOT
contain `native_kv_decode_attn_splitk_bat` (the d128 batched partial's substring -- "_bf2" diverges
from "_bat" at the second char), `_f2`, `_f2s`, or the engine-side `batched_spl` substring.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_splitk_bf2_forge.o \
        ../attention_forge/native_kv_decode_attn_splitk_bf2_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_splitk_bf2_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_splitk_bf2_blob.c \
      --symbol algenta_native_kv_decode_attn_splitk_bf2_blob
"""
from std.gpu import thread_idx, block_idx
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _IP = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same finite sentinel as the f2/f4 families and `_batched_splitk_merge_kernel_simd` -- never IEEE
`-inf`, so empty splits' `exp(m - nm)` underflows cleanly to 0.0 at merge time."""


def _native_kv_decode_splitk_partial_batched_kernel_bf2u2(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    nkeys: _IP, kv_stride: Int64,
    n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """d_head=64 BATCHED split-K PARTIAL: `grid_dim = B * h_q * n_splits`, `block_dim = 32` (ONE
    simdgroup per (sequence, head, split)), lane owns TWO head-elements (`e0 = lane*2, e0+1`).
    Per-key math byte-for-byte the single-stream `_native_kv_decode_splitk_partial_kernel_f2u2`'s
    2-key-unrolled body; only the batched indirection differs (b/h/sidx decoded from block_idx.x,
    per-sequence key count `nkeys[b]`, KV selected by the uniform-stride element offset
    `kv_off = b * kv_stride`, Q row `b*h_q*d_head + h*d_head + e`). Dispatch requires d_head == 64.
    Partial (m, l, o) contract identical to the d128 batched partial -- see module docstring."""
    var idx = Int64(block_idx.x)
    var per_seq = h_q * n_splits
    var b = idx // per_seq
    var rem = idx % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits
    var lane = Int64(thread_idx.x)
    var e0 = lane * 2
    var group = h_q // h_kv
    var hk = h // group

    var n_keys = nkeys[Int(b)]
    var kv_off = b * kv_stride

    var qv0 = Float32(q_native[Int(b * h_q * d_head + h * d_head + e0)])
    var qv1 = Float32(q_native[Int(b * h_q * d_head + h * d_head + e0 + 1)])

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)

    var block = key_start // key_block_size
    var kk = key_start % key_block_size

    var j = key_start
    while j + 1 < key_end:
        # Second key's (block, kk): the pair may cross a block boundary.
        var kk2 = kk + 1
        var block2 = block
        if kk2 == key_block_size:
            kk2 = 0
            block2 = block + 1

        # Issue BOTH keys' K and V loads up front -- 8 independent loads in flight before either
        # softmax runs.
        var k_base_a = kv_off + (hk * n_blocks + block) * d_head * key_block_size + kk
        var k_base_b = kv_off + (hk * n_blocks + block2) * d_head * key_block_size + kk2
        var ka0 = Float32(k_native[Int(k_base_a + e0 * key_block_size)])
        var ka1 = Float32(k_native[Int(k_base_a + (e0 + 1) * key_block_size)])
        var kb0 = Float32(k_native[Int(k_base_b + e0 * key_block_size)])
        var kb1 = Float32(k_native[Int(k_base_b + (e0 + 1) * key_block_size)])
        var v_base_a = kv_off + ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        var v_base_b = kv_off + ((hk * n_blocks + block2) * key_block_size + kk2) * d_head + e0
        var va0 = Float32(v_native[Int(v_base_a)])
        var va1 = Float32(v_native[Int(v_base_a + 1)])
        var vb0 = Float32(v_native[Int(v_base_b)])
        var vb1 = Float32(v_native[Int(v_base_b + 1)])

        # Two INDEPENDENT dot products off the same Q registers -- pipelined simd_sums.
        var partial_a = qv0 * ka0 + qv1 * ka1
        var partial_b = qv0 * kb0 + qv1 * kb1
        var s_a = _warp_sum(partial_a) * scale
        var s_b = _warp_sum(partial_b) * scale

        # Key-order online softmax, first key then second (same accumulation sequence as `_f2u2`).
        var nm_a = m if m > s_a else s_a
        var corr_a = exp(m - nm_a)
        var w_a = exp(s_a - nm_a)
        o0 = o0 * corr_a + w_a * va0
        o1 = o1 * corr_a + w_a * va1
        denom = denom * corr_a + w_a
        m = nm_a

        var nm_b = m if m > s_b else s_b
        var corr_b = exp(m - nm_b)
        var w_b = exp(s_b - nm_b)
        o0 = o0 * corr_b + w_b * vb0
        o1 = o1 * corr_b + w_b * vb1
        denom = denom * corr_b + w_b
        m = nm_b

        kk = kk2
        block = block2
        kk += 1
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 2

    # Odd-key epilogue: EXACTLY `_f2`'s single-key body.
    if j < key_end:
        var k_base = kv_off + (hk * n_blocks + block) * d_head * key_block_size + kk
        var partial = qv0 * Float32(k_native[Int(k_base + e0 * key_block_size)])
        partial += qv1 * Float32(k_native[Int(k_base + (e0 + 1) * key_block_size)])
        var s = _warp_sum(partial) * scale
        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        var v_base = kv_off + ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        o0 = o0 * corr + w * Float32(v_native[Int(v_base)])
        o1 = o1 * corr + w * Float32(v_native[Int(v_base + 1)])
        denom = denom * corr + w
        m = nm

    if lane == 0:
        m_out[Int(idx)] = m
        l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e0)] = o0
    o_out[Int(idx * d_head + e0 + 1)] = o1
