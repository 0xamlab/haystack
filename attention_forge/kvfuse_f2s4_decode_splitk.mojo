"""attention_forge.kvfuse_f2s4_decode_splitk -- feat/metal-beat (2026-08-23): the d_head=64
K V P R O D - F U S E D 4-key-staged SIMD-K split-K decode attention PARTIAL.

WHY (measured, not assumed)
---------------------------
The feat/llama-q80gap GPU-counter profile on the TinyLlama native fast path measured the
per-token non-GEMV remainder as kvprod 0.21 ms + merge 0.12 ms, BOTH at their per-dispatch
launch floors (kvprod_f1 proved the kvprod cost is launch-floor dominated, not scratch/barrier:
its scratch-free twin ran 1.005x), with 157 dispatches/token and wall <= GPU-sum (host encoding
fully overlapped). The remaining TinyLlama-vs-Q8_0 decode gap (~5% @256, ~7.5% @1024 on the
2026-08-23 fresh baseline) is therefore dispatch-count-bound, not bandwidth-bound. This kernel
removes the per-layer kvprod dispatch by FUSING its math into the split-K partial's prologue --
157 -> 135 dispatches/token for a 22-layer d64 model.

HOW THE FUSION STAYS RACE-FREE (the design constraint Metal imposes)
--------------------------------------------------------------------
Metal has NO cross-threadgroup barrier, so no TG may read what another TG of the SAME dispatch
writes. The fused kernel therefore makes every TG SELF-SUFFICIENT:

1. Q: each TG (h, split) re-derives its own head's roped Q in registers straight from the F32
   qkv scratch (the exact `_native_kv_producer_kernel` qk_norm=0 formula sequence, including the
   Float16 narrowing round-trip the kvprod->partial handoff performs), instead of reading the
   `q_rot` F16 buffer. The q_rot WRITE disappears with its read.
2. The NEW key (position `pos` == n_keys-1, always in the LAST split's key slice): each
   last-split TG re-derives its kv head's roped-K pair + V pair for its own two head-elements
   in registers, and the attention body's FINAL single-key iteration consumes those register
   values instead of cache loads. One designated TG per kv head (h % (h_q//h_kv) == 0) also
   writes the packed K/V slot exactly as the standalone producer did -- future tokens read it
   from the cache (dispatch boundaries guarantee visibility); NO same-dispatch TG ever READS
   that slot, so the concurrent write races nothing.
3. Every key < pos was written by a PRIOR dispatch (prefill/earlier steps) and is read from the
   cache exactly as f2s4 does.

BIT-IDENTITY: the per-key attention arithmetic is copied byte-for-byte from f2s4 (same online-
softmax accumulation order, same `_warp_sum` reductions), and the fused prologue evaluates the
kvprod formulas with the SAME operations on the SAME values -- including the
Float32(Float16(x)) narrowing round-trips the separate-dispatch path physically performs -- so
the (m, l, o) partials are bit-identical to kvprod+f2s4 run separately, and the greedy sequence
is unchanged. d64 + qk_norm=0 only (llama family): the engine's gate selects this kernel only
for the d64/qk0 pairing; qk_norm=1 models never dispatch it (and the kernel early-returns if
they ever did, so a miswire is loud, not silent).

CONTRACT otherwise IDENTICAL to f2s4: same grid `h_q * n_splits`, block_dim 32, same per-(head,
split) partial layout, same empty-split sentinel discipline (`m = _NEG_HUGE`, `l = 0`, `o = 0`),
so the engine's `_splitk_merge_kernel_simd` merges it UNCHANGED. ARG LAYOUT: args 0-13 are
f2s4's, EXCEPT arg 3 binds the F32 `qkv` scratch (f2s4 binds the `q_rot` F16 buffer there --
this kernel never reads q_rot), then trailing cos/sin tables, the absolute `pos` (patched per
step, exactly like the standalone producer's pos_base), and the qk_norm flag. 18 args total --
the `metaldispatch.ffi.MB_MAX_ARGS` raise 17 -> 18 this kernel lands with.

DISCOVERY NAMING: module name `kvfuse_f2s4_decode_splitk` (25 chars -- survives the ~32-char
AIR truncation intact); the session discovers it via the substring `kvfuse_f2s4`, checked
longest-first in the splitk chain; no other module's AIR label can contain that prefix.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build --emit object -I . -I ../attention_forge \
        -o /tmp/kvfuse_f2s4_decode_splitk_forge.o \
        ../attention_forge/kvfuse_f2s4_decode_splitk_blob_driver.mojo
    python3 tools/extract_blob.py /tmp/kvfuse_f2s4_decode_splitk_forge.o \
      ../attention_forge/generated/kvfuse_f2s4_decode_splitk_blob.c \
      --symbol algenta_kvfuse_f2s4_decode_splitk_blob
"""

from std.gpu import thread_idx, block_idx
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]

comptime _NEG_HUGE: Float32 = -3.0e38
"""Same finite sentinel as the f2/f2u2/f2s4 kernels and `_splitk_merge_kernel_simd`."""

comptime _MAX_HEAD_DIM: Int64 = 64
"""This kernel is d_head=64-structural (the d64 llama family); shared scratch sized to it."""


def _native_kv_decode_splitk_partial_kernel_f2s4k(
    m_out: _FP, l_out: _FP, o_out: _FP,
    qkv: _FP, k_native: _F16P, v_native: _F16P,
    n_keys: Int64, n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
    cos_t: _FP, sin_t: _FP, pos: Int64, qk_norm: Int64,
):
    """THE feat/metal-beat kvprod-FUSED d64 split-K partial. See the module docstring for the
    race-free self-sufficiency design and the bit-identity argument. One threadgroup per
    (head, split); 32 lanes; lane owns head-elements e0 = 2*lane, e0+1."""
    if qk_norm != 0:
        # d64 fused partial is the llama-family (qk_norm=0) kernel -- the engine's pairing gate
        # only ever dispatches it there. Refuse LOUDLY rather than compute silently-wrong math.
        return

    var xs = stack_allocation[Int(_MAX_HEAD_DIM), DType.float32, address_space = AddressSpace.SHARED]()

    var idx = Int64(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var lane = Int64(thread_idx.x)
    var e0 = lane * 2
    var group = h_q // h_kv
    var hk = h // group
    var n_pairs = d_head // 2

    # ── fused Q prologue: re-derive this head's roped Q from the F32 qkv scratch, with the
    # exact `_native_kv_producer_kernel` (qk_norm=0) formula sequence INCLUDING the F16
    # narrowing round-trip of the kvprod->partial handoff. Publish raw elements to shared,
    # barrier, then NeoX split-half rope (pairs (e, e+n_pairs)).
    var vq0 = qkv[Int(h * d_head + e0)]
    var vq1 = qkv[Int(h * d_head + e0 + 1)]
    xs[Int(e0)] = vq0
    xs[Int(e0 + 1)] = vq1
    barrier()
    var qv0 = Float32(0.0)
    var qv1 = Float32(0.0)
    if e0 < n_pairs:
        var c0 = cos_t[Int(pos * n_pairs + e0)]
        var s0 = sin_t[Int(pos * n_pairs + e0)]
        var c1 = cos_t[Int(pos * n_pairs + e0 + 1)]
        var s1 = sin_t[Int(pos * n_pairs + e0 + 1)]
        var a0 = xs[Int(e0)]
        var a1 = xs[Int(e0 + n_pairs)]
        var b0 = xs[Int(e0 + 1)]
        var b1 = xs[Int(e0 + 1 + n_pairs)]
        qv0 = Float32(Float16(a0 * c0 - a1 * s0))
        qv1 = Float32(Float16(b0 * c1 - b1 * s1))
    else:
        var c0 = cos_t[Int(pos * n_pairs + e0 - n_pairs)]
        var s0 = sin_t[Int(pos * n_pairs + e0 - n_pairs)]
        var c1 = cos_t[Int(pos * n_pairs + e0 + 1 - n_pairs)]
        var s1 = sin_t[Int(pos * n_pairs + e0 + 1 - n_pairs)]
        var a0 = xs[Int(e0 - n_pairs)]
        var a1 = xs[Int(e0)]
        var b0 = xs[Int(e0 + 1 - n_pairs)]
        var b1 = xs[Int(e0 + 1)]
        qv0 = Float32(Float16(a0 * s0 + a1 * c0))
        qv1 = Float32(Float16(b0 * s1 + b1 * c1))

    # ── fused KV append (LAST split only -- its slice is the only one containing the new key
    # pos == n_keys-1): re-derive the kv head's roped-K pair + V pair for this lane's two
    # elements; the designated writer TG also packs them into the native cache for future
    # tokens (no same-dispatch TG reads that slot -- the final key below comes from registers).
    var is_last = sidx == n_splits - 1
    var reg_k0 = Float32(0.0)
    var reg_k1 = Float32(0.0)
    var reg_v0 = Float32(0.0)
    var reg_v1 = Float32(0.0)
    if is_last:
        var vk0 = qkv[Int((h_q + hk) * d_head + e0)]
        var vk1 = qkv[Int((h_q + hk) * d_head + e0 + 1)]
        xs[Int(e0)] = vk0
        xs[Int(e0 + 1)] = vk1
        barrier()
        if e0 < n_pairs:
            var c0 = cos_t[Int(pos * n_pairs + e0)]
            var s0 = sin_t[Int(pos * n_pairs + e0)]
            var c1 = cos_t[Int(pos * n_pairs + e0 + 1)]
            var s1 = sin_t[Int(pos * n_pairs + e0 + 1)]
            var a0 = xs[Int(e0)]
            var a1 = xs[Int(e0 + n_pairs)]
            var b0 = xs[Int(e0 + 1)]
            var b1 = xs[Int(e0 + 1 + n_pairs)]
            reg_k0 = Float32(Float16(a0 * c0 - a1 * s0))
            reg_k1 = Float32(Float16(b0 * c1 - b1 * s1))
        else:
            var c0 = cos_t[Int(pos * n_pairs + e0 - n_pairs)]
            var s0 = sin_t[Int(pos * n_pairs + e0 - n_pairs)]
            var c1 = cos_t[Int(pos * n_pairs + e0 + 1 - n_pairs)]
            var s1 = sin_t[Int(pos * n_pairs + e0 + 1 - n_pairs)]
            var a0 = xs[Int(e0 - n_pairs)]
            var a1 = xs[Int(e0)]
            var b0 = xs[Int(e0 + 1 - n_pairs)]
            var b1 = xs[Int(e0 + 1)]
            reg_k0 = Float32(Float16(a0 * s0 + a1 * c0))
            reg_k1 = Float32(Float16(b0 * s1 + b1 * c1))
        reg_v0 = Float32(Float16(qkv[Int((h_q + h_kv + hk) * d_head + e0)]))
        reg_v1 = Float32(Float16(qkv[Int((h_q + h_kv + hk) * d_head + e0 + 1)]))
        if h % group == 0:
            # Designated writer for kv head hk: pack the new key exactly as the standalone
            # `_native_kv_producer_kernel` did (Float16(reg) == the pre-widening value).
            var block_w = pos // key_block_size
            var kk_w = pos % key_block_size
            var kbb = (hk * n_blocks + block_w) * d_head
            k_native[Int((kbb + e0) * key_block_size + kk_w)] = Float16(reg_k0)
            k_native[Int((kbb + e0 + 1) * key_block_size + kk_w)] = Float16(reg_k1)
            var vbb = ((hk * n_blocks + block_w) * key_block_size + kk_w) * d_head + e0
            v_native[Int(vbb)] = Float16(reg_v0)
            v_native[Int(vbb + 1)] = Float16(reg_v1)

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits
    # Last split: the final key (pos) is consumed from registers AFTER the cache-reading body.
    var key_end_body = key_end - 1 if is_last else key_end

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)

    var block = key_start // key_block_size
    var kk = key_start % key_block_size

    var j = key_start
    var chunk_ok = key_block_size % 4 == 0

    # ── lead-in: exact `_f2s4` single-key body until the key cursor is 4-aligned ──
    while chunk_ok and j < key_end_body and kk % 4 != 0:
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

    # ── 4-key chunks: byte-for-byte f2s4's staging loop (the new key is never inside: the
    # last split's body stops one key early) ──
    while chunk_ok and j + 4 <= key_end_body:
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

    # ── tail (< 4 keys, or the whole slice when chunk_ok is False): exact `_f2s4` body ──
    while j < key_end_body:
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

    # ── the spliced new key (last split only): EXACT f2s4 per-key arithmetic, K/V from the
    # fused registers instead of cache loads -- bit-identical to reading the values the
    # standalone producer wrote (same Float16 round-trip applied on both paths).
    if is_last:
        var partial = qv0 * reg_k0 + qv1 * reg_k1
        var s = _warp_sum(partial) * scale
        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o0 = o0 * corr + w * reg_v0
        o1 = o1 * corr + w * reg_v1
        denom = denom * corr + w
        m = nm

    if lane == 0:
        m_out[Int(idx)] = m
        l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e0)] = o0
    o_out[Int(idx * d_head + e0 + 1)] = o1
