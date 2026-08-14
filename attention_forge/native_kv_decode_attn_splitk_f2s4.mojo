"""attention_forge.native_kv_decode_attn_splitk_f2s4 -- feat/llama-q80gap (2026-08-13): the
d_head=64 4-KEY-STAGED SIMD-K split-K decode attention PARTIAL -- the kernel that closes the
deep-context attention gap the TinyLlama native-fast-path profile named (f2u2 partial = the
largest non-GEMV decode cost: 0.34ms/token @288 keys, 0.60ms/token @1056 keys at n_splits=16).

WHY (measured, not assumed)
---------------------------
The GPU-counter profile (`tinyllama_probe_counters_decode_native.mojo`) + mutant dissection
(f2_mutants*.mojo, mma_forge nightly) on the production shape proved: (1) shuffle/exp compute is
NOT the bottleneck (removing either saves < 3%); (2) K/V memory access is ~59% of f2u2's cost;
(3) a key-major-addressed K mutant recovers 1.25x. Root cause: the packed K layout is
ELEMENT-major inside a block (`K[hk][block][e][kk]` -- contiguous ACROSS keys for one element),
so f2u2's per-key strided scalar K loads (`k[e0][kk]`, 2 bytes, 64B line stride) use ~3% of
every fetched cache line.

THE FIX, LAYOUT-PRESERVING: stage the next 4 keys' K as two WIDTH-4 SIMD loads per lane (16B
contiguous ACROSS keys = full-line streaming within the 32-key block), then consume the staged
values with EXACTLY `_f2`'s per-key scalar arithmetic in key order (constant SIMD-index
extracts only -- the width-8/runtime-indexed twins measured 1.00x or WORSE because dynamic SIMD
indexing spills; 4 is the unroll sweet spot). V keeps its per-key width-2 contiguous pair loads.
Chunk discipline: 4 divides the production key_block_size (32; runtime-guarded), a lead-in runs
the exact f2 body until kk is 4-aligned, and an odd tail runs the f2 body -- so `block`/`kk`
wrap only on chunk/single-key boundaries.

CONTRACT, IDENTICAL to f2/f2u2 (deliberate): same signature, same grid `h_q * n_splits`,
block_dim 32, same per-(head, split) partial layout (`m_out[idx]`, `l_out[idx]`,
`o_out[idx * d_head + e]`, o UNNORMALIZED, `idx = h * n_splits + sidx`), same empty-split
sentinel discipline (`m = _NEG_HUGE`, `l = 0`, `o = 0` fold through `_splitk_merge_kernel_simd`
as a genuine no-op), same key-order online-softmax accumulation. PROVEN BIT-IDENTICAL to f2u2:
the A/B driver's cross-check measures worst-abs-diff 0.0 on (m, l, o) across aligned/ragged/
empty-split (n_keys, n_splits) pairs -- staging changes only WHEN loads issue, never the
arithmetic sequence, which is the byte-identical greedy gate's kernel-level evidence. REQUIRES
d_head == 64 at dispatch (the engine's own gate).

MEASURED (standalone interleaved median-of-9, TinyLlama shape h_q=32/h_kv=4/d_head=64/kbs=32,
production n_splits: 16 @288/1056, 32 @2048): f2s4 = 1.00x f2u2 @288 keys (too shallow for the
staging to pay its lead-in; a no-regression tie), 1.30x @1056 keys (25.99 -> 20.00 us/dispatch),
1.48x @2048 keys (40.34 -> 27.17 us/dispatch) -- the gain GROWS with depth exactly where the
Q8_0 gap grows.

DISCOVERY NAMING: module name `native_kv_decode_attn_splitk_f2s4` -- the session's discovery
checks the LONGER `..._f2s4` substring BEFORE the shorter `..._f2` substring the f2u2 blob owns,
BEFORE the generic `native_kv_decode_attn_splitk` one -- same longest-first discipline the
`_bat`/`_f2` arms use, scan order irrelevant.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/native_kv_decode_attn_splitk_f2s4_forge.o \
        ../attention_forge/native_kv_decode_attn_splitk_f2s4_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/native_kv_decode_attn_splitk_f2s4_forge.o \
      ../attention_forge/generated/native_kv_decode_attn_splitk_f2s4_blob.c \
      --symbol algenta_native_kv_decode_attn_splitk_f2s4_blob
"""

from std.gpu import thread_idx, block_idx
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same finite sentinel as the f2/f2u2 kernels and `_splitk_merge_kernel_simd` -- never IEEE
`-inf`, so empty splits' `exp(m - nm)` underflows cleanly to 0.0 at merge time."""


def _native_kv_decode_splitk_partial_kernel_f2s4(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """THE feat/llama-q80gap WINNER -- 4-KEY STAGED SIMD-K d_head=64 split-K partial.

    The packed K layout is ELEMENT-major inside a block (`K[hk][block][e][kk]` -- contiguous
    ACROSS keys for one element), so f2u2's per-key strided scalar K loads touch a fresh 64-byte
    cache line for 2 useful bytes (~3% line utilization); the mutant dissection proved K/V memory
    access is ~59% of f2u2's cost (0.0152 of 0.0259 ms/dispatch at 1056 keys), and a key-major-
    addressed mutant recovered 1.25x of it. This kernel stages the next 4 keys' K as two
    width-4 SIMD loads per lane (contiguous across keys = full-line streaming), then consumes
    them with EXACTLY f2's per-key scalar arithmetic in key order (constant SIMD-index extracts,
    no runtime indexing -- the width-8 twin measured 1.00x because dynamic/runtime SIMD indexing
    spills; 4 is the unroll sweet spot). Same contract, same empty-split sentinel discipline,
    same chunk-boundary discipline (4 divides the production key_block_size=32; runtime-guarded;
    lead-in aligns kk to 4, tail runs the f2 body), so the engine's `_splitk_merge_kernel_simd`
    merges it UNCHANGED and the partials are bit-identical to `_f2u2` (driver cross-check worst
    diff 0.0). Standalone race at TinyLlama shape (h_q=32,h_kv=4,d_head=64), n_keys=1056,
    n_splits=16: 1.28x f2u2 per dispatch."""
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
    var chunk_ok = key_block_size % 4 == 0

    # ── lead-in: exact `_f2` single-key body until the key cursor is 4-aligned ──
    while chunk_ok and j < key_end and kk % 4 != 0:
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

    # ── 4-key chunks: two width-4 SIMD K loads + four width-2 V loads, then in-order f2 bodies ──
    while chunk_ok and j + 4 <= key_end:
        var k_row_base = (hk * n_blocks + block) * d_head * key_block_size + kk
        var k0v = k_native.load[width=4](Int(k_row_base + e0 * key_block_size))
        var k1v = k_native.load[width=4](Int(k_row_base + (e0 + 1) * key_block_size))
        var v_block_base = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        var vv0 = v_native.load[width=2](Int(v_block_base))
        var vv1 = v_native.load[width=2](Int(v_block_base + d_head))
        var vv2 = v_native.load[width=2](Int(v_block_base + 2 * d_head))
        var vv3 = v_native.load[width=2](Int(v_block_base + 3 * d_head))

        var partial = qv0 * Float32(k0v[0]) + qv1 * Float32(k1v[0])
        var s = _warp_sum(partial) * scale
        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o0 = o0 * corr + w * Float32(vv0[0])
        o1 = o1 * corr + w * Float32(vv0[1])
        denom = denom * corr + w
        m = nm

        partial = qv0 * Float32(k0v[1]) + qv1 * Float32(k1v[1])
        s = _warp_sum(partial) * scale
        nm = m if m > s else s
        corr = exp(m - nm)
        w = exp(s - nm)
        o0 = o0 * corr + w * Float32(vv1[0])
        o1 = o1 * corr + w * Float32(vv1[1])
        denom = denom * corr + w
        m = nm

        partial = qv0 * Float32(k0v[2]) + qv1 * Float32(k1v[2])
        s = _warp_sum(partial) * scale
        nm = m if m > s else s
        corr = exp(m - nm)
        w = exp(s - nm)
        o0 = o0 * corr + w * Float32(vv2[0])
        o1 = o1 * corr + w * Float32(vv2[1])
        denom = denom * corr + w
        m = nm

        partial = qv0 * Float32(k0v[3]) + qv1 * Float32(k1v[3])
        s = _warp_sum(partial) * scale
        nm = m if m > s else s
        corr = exp(m - nm)
        w = exp(s - nm)
        o0 = o0 * corr + w * Float32(vv3[0])
        o1 = o1 * corr + w * Float32(vv3[1])
        denom = denom * corr + w
        m = nm

        kk += 4
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 4

    # ── tail (< 4 keys, or the whole slice when chunk_ok is False): exact `_f2` body ──
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
