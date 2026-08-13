"""attention_forge.native_kv_decode_attn_splitk_f2 -- feat/llama-native-deep (2026-08-13): the
d_head=64 (llama-family, one simdgroup, two-elements-per-lane) twins of the d_head=128-specific
`_native_kv_decode_splitk_partial_kernel_f4` / `_f4u2` in `native_kv_decode_attn_splitk.mojo`.

WHY A SEPARATE MODULE
----------------------
The f4/f4u2 production kernel's block_dim is `d_head // 4` = 32 = exactly ONE Apple SIMD group,
each lane owning FOUR head-elements; for d_head=64 that formula gives 16 threads (half a SIMD
group -- `_warp_sum` would sum nonexistent lanes), so a d_head=64 model cannot dispatch it. This
module's kernels keep the EXACT one-simdgroup-per-(head, split) shape with block_dim=32 FIXED and
two head-elements per lane (32 lanes x 2 = 64 = d_head): each key's dot product is still a single
`simd_sum` over the 32 lanes, NO cross-group barrier, NO shared scratch -- the same single-level
SIMD reduction that made f4/f4u2 win at depth, translated to d_head=64. REQUIRES d_head == 64 at
dispatch (the engine's own gate; the kernel covers exactly 64 elements).

CONTRACT, IDENTICAL to f4/f4u2 (deliberate): same signature, same grid `h_q * n_splits`, same
per-(head, split) partial layout (`m_out[idx]`, `l_out[idx]`, `o_out[idx * d_head + e]`, o
UNNORMALIZED, `idx = h * n_splits + sidx`), same empty-split sentinel discipline (`m = _NEG_HUGE`,
`l = 0`, `o = 0` fold through `_splitk_merge_kernel_simd` as a genuine no-op), same key-order
online-softmax accumulation -- so the engine's EXISTING `_splitk_merge_kernel_simd` merges this
kernel's output COMPLETELY UNCHANGED.

DISCOVERY NAMING: module name `native_kv_decode_attn_splitk_f2` (31 chars -- fits the AIR name's
~32-char truncation budget intact, so the session's discovery can match the LONGER
`native_kv_decode_attn_splitk_f2` substring BEFORE the generic `native_kv_decode_attn_splitk`
substring the f4u2 blob owns -- same longest-first discipline the batched `_bat` arm uses).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_splitk_f2_forge.o \
        ../attention_forge/native_kv_decode_attn_splitk_f2_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_splitk_f2_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_splitk_f2_blob.c \
      --symbol algenta_native_kv_decode_attn_splitk_f2_blob
"""
from std.gpu import thread_idx, block_idx
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same finite sentinel as the f4/f4u2 kernels and `_splitk_merge_kernel_simd` -- never IEEE
`-inf`, so empty splits' `exp(m - nm)` underflows cleanly to 0.0 at merge time."""


def _native_kv_decode_splitk_partial_kernel_f2(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """d_head=64 split-K PARTIAL: `grid_dim = h_q * n_splits`, `block_dim = 32` (ONE simdgroup
    per (head, split)), lane owns TWO head-elements (`e0 = lane*2, e0+1`), K as two strided
    scalars, V as two CONTIGUOUS values, one `simd_sum` per key. Dispatch requires d_head == 64.
    Partial (m, l, o) contract byte-identical to `_f4`'s -- see module docstring."""
    var idx = Int64(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var lane = Int64(thread_idx.x)
    var e0 = lane * 2
    var group = h_q // h_kv
    var hk = h // group

    var qv0 = Float32(q_native[Int(h * d_head + e0)])
    var qv1 = Float32(q_native[Int(h * d_head + e0 + 1)])

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)

    var block = key_start // key_block_size
    var kk = key_start % key_block_size

    var j = key_start
    while j < key_end:
        var k_base = (hk * n_blocks + block) * d_head * key_block_size + kk
        var partial = qv0 * Float32(k_native[Int(k_base + e0 * key_block_size)]) \
            + qv1 * Float32(k_native[Int(k_base + (e0 + 1) * key_block_size)])
        var s = _warp_sum(partial) * scale

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)

        var v_base = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        o0 = o0 * corr + w * Float32(v_native[Int(v_base)])
        o1 = o1 * corr + w * Float32(v_native[Int(v_base + 1)])
        denom = denom * corr + w
        m = nm

        kk += 1
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 1

    if lane == 0:
        m_out[Int(idx)] = m
        l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e0)] = o0
    o_out[Int(idx * d_head + e0 + 1)] = o1


def _native_kv_decode_splitk_partial_kernel_f2u2(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """2-KEY-UNROLLED d_head=64 twin of `_native_kv_decode_splitk_partial_kernel_f4u2` -- per body
    it issues BOTH keys' K loads (4 strided scalars) and BOTH keys' V loads (4 contiguous) before
    either softmax runs, and the two dot products are independent simd_sums off the SAME Q
    registers (doubled memory-level parallelism, pipelined shuffle reductions). Block/kk advance
    computed per key (the pair may cross a 32-key block boundary); an odd trailing key runs the
    exact single-key f2 body as a scalar epilogue, so the per-split accumulation ORDER is
    byte-identical to `_f2`'s (key-order online softmax). Dispatch contract IDENTICAL to `_f2`
    (same grid/block shape, same partial layout, requires d_head == 64)."""
    var idx = Int64(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var lane = Int64(thread_idx.x)
    var e0 = lane * 2
    var group = h_q // h_kv
    var hk = h // group

    var qv0 = Float32(q_native[Int(h * d_head + e0)])
    var qv1 = Float32(q_native[Int(h * d_head + e0 + 1)])

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
        var k_base_a = (hk * n_blocks + block) * d_head * key_block_size + kk
        var k_base_b = (hk * n_blocks + block2) * d_head * key_block_size + kk2
        var ka0 = Float32(k_native[Int(k_base_a + e0 * key_block_size)])
        var ka1 = Float32(k_native[Int(k_base_a + (e0 + 1) * key_block_size)])
        var kb0 = Float32(k_native[Int(k_base_b + e0 * key_block_size)])
        var kb1 = Float32(k_native[Int(k_base_b + (e0 + 1) * key_block_size)])
        var v_base_a = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        var v_base_b = ((hk * n_blocks + block2) * key_block_size + kk2) * d_head + e0
        var va0 = Float32(v_native[Int(v_base_a)])
        var va1 = Float32(v_native[Int(v_base_a + 1)])
        var vb0 = Float32(v_native[Int(v_base_b)])
        var vb1 = Float32(v_native[Int(v_base_b + 1)])

        # Two INDEPENDENT dot products off the same Q registers -- pipelined simd_sums.
        var partial_a = qv0 * ka0 + qv1 * ka1
        var partial_b = qv0 * kb0 + qv1 * kb1
        var s_a = _warp_sum(partial_a) * scale
        var s_b = _warp_sum(partial_b) * scale

        # Key-order online softmax, first key then second (same accumulation sequence as `_f2`).
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
        var k_base = (hk * n_blocks + block) * d_head * key_block_size + kk
        var partial = qv0 * Float32(k_native[Int(k_base + e0 * key_block_size)])
        partial += qv1 * Float32(k_native[Int(k_base + (e0 + 1) * key_block_size)])
        var s = _warp_sum(partial) * scale
        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        var v_base = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        o0 = o0 * corr + w * Float32(v_native[Int(v_base)])
        o1 = o1 * corr + w * Float32(v_native[Int(v_base + 1)])
        denom = denom * corr + w
        m = nm

    if lane == 0:
        m_out[Int(idx)] = m
        l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e0)] = o0
    o_out[Int(idx * d_head + e0 + 1)] = o1
