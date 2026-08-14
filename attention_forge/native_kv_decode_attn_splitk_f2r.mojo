"""attention_forge.native_kv_decode_attn_splitk_f2r -- feat/llama-q80gap (2026-08-13):
REGISTER-BLOCKED d_head=64 split-K partial A/B variants of `native_kv_decode_attn_splitk_f2.
_f2u2` -- the REFUTED wider-staging arms of the search whose winner is the width-4
constant-index kernel in its OWN module, `native_kv_decode_attn_splitk_f2s4` (the production
kernel). This file stays as the A/B record: `_f2r8` (width-8 K staging, runtime-indexed
consumption loop) measured 0.79-0.85x of f2u2 and `_f2r16` (width-16) measured ~0.67-0.74x --
both BIT-EXACT but slower: runtime SIMD-register indexing spills, and the wider staging
registers eat the load-pipelining gain. Companion width-8 CONSTANT-INDEX twin (f2s8, generated
variant, never landed) measured only 1.01-1.06x -- the width-4 unroll of `_f2s4` is the sweet
spot. See `native_kv_decode_attn_splitk_f2r_driver.mojo` for the bit-exact gates + races.

WHY THE SEARCH EXISTED
----------------------
The GPU-counter profile of the TinyLlama native fast path (feat/llama-q80gap probe
`tinyllama_probe_counters_decode_native.mojo`) measured the f2u2 partial as the largest
non-GEMV decode cost: 0.34ms/token @288 keys, 0.60ms/token @1056 keys (n_splits=16), and an
n_splits sweep showed MORE splits make it SLOWER (0.60->0.72ms at 64 splits) -- the bottleneck
is per-key efficiency inside the kernel, not parallelism. Root cause (mutant dissection): K/V
memory access is ~59% of f2u2's cost; the packed K layout is ELEMENT-major inside a block
(`K[hk][block][e][kk]` -- contiguous across keys for one element), so f2u2's per-key strided
scalar K loads (`k[e0][kk]`, `k[e0+1][kk]`, 64B apart) each touch a DIFFERENT 64-byte cache
line for 2 useful bytes (~3% line utilization). With GQA 32:4 the same K/V lines are re-read by
8 q-head threadgroups, amplifying the waste.

THE STAGING IDEA (what the winner `_f2s4` and these refuted arms share): because K is contiguous
ACROSS keys for a fixed element, lane `l` loads its two element rows `e0 = 2l`, `e0+1` for the
next C keys as one WIDTH-C SIMD load each, which -- once the key cursor is aligned to a chunk
boundary -- uses each fetched K cache line fully across the chunk (lines hold key_block_size=32
keys; C divides 32). V stays per-key contiguous-pair loads (its layout is already key-major,
line utilization already ~100%). The staged keys are then consumed EXACTLY in key order with
the SAME online-softmax update sequence f2/f2u2 evaluate -- every per-key arithmetic expression
is byte-for-byte the same source, so the per-(head, split) partials are bit-identical to
`_f2u2`'s (proven element-wise in the driver's cross-check, worst diff 0.0).

CHUNK-BOUNDARY DISCIPLINE: chunks never cross a key block. The lead-in runs the exact `_f2`
single-key body until `kk % C == 0` (at most C-1 keys); every C-key chunk then starts at a
block-interior chunk-aligned kk and, because C divides key_block_size (guarded at runtime; the
production dispatch is key_block_size=32), ends before the block wraps; the odd tail (< C keys)
runs the single-key body again. `block`/`kk` advance only at chunk/single-key boundaries.

CONTRACT, IDENTICAL to f2/f2u2 (deliberate): same signature, same grid `h_q * n_splits`,
block_dim 32, same per-(head, split) partial layout (`m_out[idx]`, `l_out[idx]`,
`o_out[idx * d_head + e]`, o UNNORMALIZED, `idx = h * n_splits + sidx`), same empty-split
sentinel discipline (`m = _NEG_HUGE`, `l = 0`, `o = 0` fold through `_splitk_merge_kernel_simd`
as a genuine no-op), same key-order online-softmax accumulation -- the engine's EXISTING
`_splitk_merge_kernel_simd` merges this kernel's output COMPLETELY UNCHANGED. REQUIRES
d_head == 64 at dispatch (the engine's own gate; the kernel covers exactly 64 elements).

DISCOVERY: NONE -- this module is a research A/B record, never forged into a blob and never
wired into the session; the PRODUCTION winner `_f2s4` carries the discovery naming (see its own
module docstring's TRUNCATION CAUTION).

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_decode_attn_splitk_f2r_driver.mojo
"""

from std.gpu import thread_idx, block_idx
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same finite sentinel as the f2/f2u2 kernels and `_splitk_merge_kernel_simd` -- never IEEE
`-inf`, so empty splits' `exp(m - nm)` underflows cleanly to 0.0 at merge time."""


def _native_kv_decode_splitk_partial_kernel_f2r8(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """8-KEY REGISTER-BLOCKED d_head=64 split-K partial. See the module docstring for the why
    and the chunk-boundary discipline. One 16B SIMD load per lane per staged element row; the
    8 staged keys are consumed in exact key order with f2's single-key arithmetic."""
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

    # Chunking is only legal when the block size is a multiple of 8 (production: 32). Any other
    # block size degrades to the exact single-key f2 body for the whole slice.
    var chunk_ok = key_block_size % 8 == 0

    # ── lead-in: exact `_f2` single-key body until the key cursor is chunk-aligned ──
    while chunk_ok and j < key_end and kk % 8 != 0:
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

    # ── 8-key chunks: staged SIMD K loads, V pair loads, then in-order consumption ──
    while chunk_ok and j + 8 <= key_end:
        var k_row_base = (hk * n_blocks + block) * d_head * key_block_size + kk
        var k0v = k_native.load[width=8](Int(k_row_base + e0 * key_block_size))
        var k1v = k_native.load[width=8](Int(k_row_base + (e0 + 1) * key_block_size))
        var v_block_base = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        var va0 = SIMD[DType.float16, 8]()
        var va1 = SIMD[DType.float16, 8]()
        for t in range(8):
            var vv = v_native.load[width=2](Int(v_block_base + Int64(t) * d_head))
            va0[t] = vv[0]
            va1[t] = vv[1]
        for t in range(8):
            var partial = qv0 * Float32(k0v[t]) + qv1 * Float32(k1v[t])
            var s = _warp_sum(partial) * scale
            var nm = m if m > s else s
            var corr = exp(m - nm)
            var w = exp(s - nm)
            o0 = o0 * corr + w * Float32(va0[t])
            o1 = o1 * corr + w * Float32(va1[t])
            denom = denom * corr + w
            m = nm
        kk += 8
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 8

    # ── tail (< 8 keys, or the whole slice when chunk_ok is False): exact `_f2` body ──
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


def _native_kv_decode_splitk_partial_kernel_f2r16(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """16-KEY REGISTER-BLOCKED twin of `_f2r8` -- one 32B SIMD load per lane per staged element
    row, 16 staged keys consumed in exact key order. Same contract, same chunk discipline
    (16 divides the production key_block_size=32; runtime-guarded). REFUTED by the driver bench
    (0.67x of f2u2 at 1056 keys -- SIMD-register staging spills on extraction); kept for the
    A/B record."""
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
    var chunk_ok = key_block_size % 16 == 0

    while chunk_ok and j < key_end and kk % 16 != 0:
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

    while chunk_ok and j + 16 <= key_end:
        var k_row_base = (hk * n_blocks + block) * d_head * key_block_size + kk
        var k0v = k_native.load[width=16](Int(k_row_base + e0 * key_block_size))
        var k1v = k_native.load[width=16](Int(k_row_base + (e0 + 1) * key_block_size))
        var v_block_base = ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        var va0 = SIMD[DType.float16, 16]()
        var va1 = SIMD[DType.float16, 16]()
        for t in range(16):
            var vv = v_native.load[width=2](Int(v_block_base + Int64(t) * d_head))
            va0[t] = vv[0]
            va1[t] = vv[1]
        for t in range(16):
            var partial = qv0 * Float32(k0v[t]) + qv1 * Float32(k1v[t])
            var s = _warp_sum(partial) * scale
            var nm = m if m > s else s
            var corr = exp(m - nm)
            var w = exp(s - nm)
            o0 = o0 * corr + w * Float32(va0[t])
            o1 = o1 * corr + w * Float32(va1[t])
            denom = denom * corr + w
            m = nm
        kk += 16
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 16

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
