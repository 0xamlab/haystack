"""attention_forge.native_kv_decode_attn_splitk_batched -- Project Slipstream Phase 3 (2026-08-09):
the BATCHED / continuous-batching flash-decoding twin of
`native_kv_decode_attn_splitk._native_kv_decode_splitk_partial_kernel`. Single-stream decode is
weight-streaming-bound for every engine; the wide-margin lever is batching B sequences so each
projection becomes a `[B, d_model] @ weights` GEMM (the prefill shape, already measured to collapse
per-token cost). The GEMM side is reusable via `_apply_m_rows(B)`; the one genuinely new capability
is ATTENTION with a SEQUENCE dimension -- each of B sequences attending its OWN KV cache with its
OWN key count. This module is that capability: the partial + merge flash-decoding pair generalized
from grid `h_q * n_splits` (one sequence) to `B * h_q * n_splits` / `B * h_q` (B sequences).

CONTRACT (generalizes the single-stream pair, deliberate):
- PARTIAL writes UNNORMALIZED `(m, l, o)` partials at the globally-flattened index
  `idx = b * (h_q*n_splits) + h * n_splits + sidx = block_idx.x`, i.e. a `[B, h_q, n_splits]`
  layout that reduces to the single-stream `[h_q, n_splits]` layout when b==0. o UNNORMALIZED,
  same finite sentinel `_NEG_HUGE` for empty splits, so the merge folds empty splits as no-ops.
- MERGE is the B-aware twin of `residentk.kernels._splitk_merge_kernel_simd`: one threadgroup per
  (sequence, query head) (`grid = B * h_q`), associative online-softmax combine over `n_splits`
  partials, writes `attn_out[b*h_q*d_head + h*d_head + e] = o / denom`.

PER-SEQUENCE STATE, MINIMAL DEVICE-SIDE INDICTION (the novel mechanism, scoped by the Slipstream
Phase 3 infra map): all B sequences' KV caches live in ONE contiguous buffer each (K and V), which
keeps buffer count flat (the shim's ALGENTA_MAX_BUFFERS constraint) and means a sequence's cache is
selected by a scalar ELEMENT OFFSET, not by dereferencing an array of pointers. Because every cache
is provisioned to the same max_ctx, that offset is uniform-stride: `kv_off = b * kv_stride`, paid
as a scalar multiply in-kernel -- NO pointer-array dereference, NO extra device read for the offset.
The ONLY per-sequence device array is `nkeys` (B Int64 used-key counts), read once per threadgroup.
Q is a contiguous `[B, h_q*d_head]` row stack (the batched qkv_proj GEMM already produces it), so a
sequence's query row is pure index arithmetic `q_native[b*h_q*d_head + h*d_head + e]`.

NATIVE-PACKED ADDRESSING: identical incremental formulas to the single-stream kernel
(K: `kv_off + ((hk*n_blocks+block)*d_head+e)*key_block_size+kk`;
 V: `kv_off + ((hk*n_blocks+block)*key_block_size+kk)*d_head+e`), block/kk advanced with wrap,
the two divisions paid once per threadgroup at the slice start. `n_blocks` is the PROVISIONED cache
block count (uniform across B, since all caches share max_ctx), distinct from the per-sequence USED
count `nkeys[b]` that bounds the key loop.

INHERITED, KNOWN, NOT-NEW RISKS: (1) the two-level SIMD-shuffle reduction carries the same documented
rare Mojo 1.0.0b2 self-race as the single-stream kernel, now with B x more exposure; (2) `d_head % 32
== 0` (caller-enforced); (3) `_MAX_HEAD_DIM = 128` is a shared-mem sizing ceiling -- a model with
d_head > 128 would break the scratch array.

DISCOVERY NAMING (for the later engine wiring, flagged now): the module/kernel name deliberately
CONTAINS `native_kv_decode_attn_splitk` -- when this blob is wired into
`_MBQwen3I8AllSimd7Prefill.__init__`'s discovery loop, that loop MUST check the LONGER
`native_kv_decode_attn_splitk_batched` substring BEFORE `native_kv_decode_attn_splitk`, or the two
split-K pipelines cross-wire. Not yet wired; standalone correctness only at this stage.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_decode_attn_splitk_batched_driver.mojo
"""
from std.gpu import thread_idx, block_idx
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _IP = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _MAX_HEAD_DIM: Int64 = 128
comptime _WARP_SIZE: Int64 = 32
comptime _MAX_SIMD_GROUPS: Int64 = _MAX_HEAD_DIM // _WARP_SIZE

comptime _NEG_HUGE: Float32 = -3.0e38


def _native_kv_decode_splitk_partial_batched_kernel(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    nkeys: _IP, kv_stride: Int64,
    n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """BATCHED PARTIAL half -- one threadgroup per (sequence, query head, split)
    (`grid_dim = B * h_q * n_splits`, `block_dim = d_head`). Per-key math byte-for-byte the
    single-stream kernel's two-level SIMD-shuffle reduction; only the sequence decode (b from
    block_idx.x), the per-sequence key count (`nkeys[b]`), the KV element offset (`b * kv_stride`),
    and the Q row selection differ. See the module docstring for the layout/indirection contract."""
    var grp = stack_allocation[Int(_MAX_SIMD_GROUPS), DType.float32, address_space = AddressSpace.SHARED]()
    var idx = Int64(block_idx.x)
    var per_seq = h_q * n_splits
    var b = idx // per_seq
    var rem = idx % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits
    var e = Int64(thread_idx.x)
    var group = h_q // h_kv
    var hk = h // group

    var n_keys = nkeys[Int(b)]
    var kv_off = b * kv_stride

    var qv = Float32(q_native[Int(b * h_q * d_head + h * d_head + e)])
    var lane = e % _WARP_SIZE
    var grp_id = e // _WARP_SIZE
    var n_groups = d_head // _WARP_SIZE

    # Split `sidx` of `n_splits` owns keys [key_start, key_end) of THIS sequence's `n_keys` -- the
    # exact partition the single-stream kernel uses, applied per sequence. Two divisions paid once
    # per threadgroup.
    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    var block = key_start // key_block_size
    var kk = key_start % key_block_size

    var j = key_start
    while j < key_end:
        var k_idx = kv_off + ((hk * n_blocks + block) * d_head + e) * key_block_size + kk
        var v_idx = kv_off + ((hk * n_blocks + block) * key_block_size + kk) * d_head + e

        var partial = qv * Float32(k_native[Int(k_idx)])
        var group_total = _warp_sum(partial)
        if lane == 0:
            grp[Int(grp_id)] = group_total
        barrier()
        var s = Float32(0.0)
        for g in range(Int(n_groups)):
            s += grp[g]
        s *= scale
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * Float32(v_native[Int(v_idx)])
        denom = denom * corr + w
        m = nm

        kk += 1
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 1

    m_out[Int(idx)] = m
    l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e)] = o


def _native_kv_decode_splitk_merge_batched_kernel(
    attn_out: _FP, m_in: _FP, l_in: _FP, o_in: _FP,
    n_splits: Int64, h_q: Int64, d_head: Int64,
):
    """BATCHED MERGE half -- B-aware twin of `residentk.kernels._splitk_merge_kernel_simd`: one
    threadgroup per (sequence, query head) (`grid_dim = B * h_q`, `block_dim = d_head`), combining
    the `[B, h_q, n_splits]` partials this module's partial kernel wrote. Same associative
    online-softmax rescale-and-add; empty splits are genuine no-ops. Layout-agnostic over how the
    partials were produced, same as the single-stream merge."""
    var idx = Int64(block_idx.x)
    var b = idx // h_q
    var h = idx % h_q
    var e = Int64(thread_idx.x)
    # Partial index of split 0 for this (b, h): b * (h_q*n_splits) + h * n_splits.
    var base = b * (h_q * n_splits) + h * n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)
    for s in range(Int(n_splits)):
        var pidx = base + Int64(s)
        var sm = m_in[Int(pidx)]
        var sl = l_in[Int(pidx)]
        var nm = m if m > sm else sm
        var corr = exp(m - nm)
        var w = exp(sm - nm)
        o = o * corr + w * o_in[Int(pidx * d_head + e)]
        denom = denom * corr + w * sl
        m = nm
    attn_out[Int((b * h_q + h) * d_head + e)] = o / denom


def _native_kv_decode_splitk_partial_batched_kernel_f4u2(
    m_out: _FP, l_out: _FP, o_out: _FP,
    q_native: _F16P, k_native: _F16P, v_native: _F16P,
    nkeys: _IP, kv_stride: Int64,
    n_splits: Int64, h_q: Int64, h_kv: Int64, d_head: Int64,
    scale: Float32, key_block_size: Int64, n_blocks: Int64,
):
    """Beat-llama.cpp campaign concurrent front (2026-08-11): the 2-KEY-UNROLLED float4 successor of
the batched partial above -- one simdgroup per (sequence, query head, split), block_dim =
d_head // 4, per-key math the single-stream `_native_kv_decode_splitk_partial_kernel_f4u2`'s exact
2-key-unrolled body (16 independent loads in flight, pipelined simd_sums, odd-key epilogue), with
the SAME batched indirection the original batched partial uses: b/h/sidx decoded from block_idx.x,
per-sequence key count `nkeys[b]` read once per threadgroup, KV selected by the uniform-stride
element offset `kv_off = b * kv_stride`, Q row `b*h_q*d_head + h*d_head + e`. PARTIAL CONTRACT
UNCHANGED (unnormalized (m,l,o) at idx = b*(h_q*n_splits) + h*n_splits + sidx, same sentinel), so
`_native_kv_decode_splitk_merge_batched_kernel` merges it without changes -- the engine's only
delta is the threadgroup size (d_head -> d_head // 4)."""
    var idx = Int64(block_idx.x)
    var per_seq = h_q * n_splits
    var b = idx // per_seq
    var rem = idx % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits
    var lane = Int64(thread_idx.x)
    var e0 = lane * 4
    var group = h_q // h_kv
    var hk = h // group

    var n_keys = nkeys[Int(b)]
    var kv_off = b * kv_stride

    var qv0 = Float32(q_native[Int(b * h_q * d_head + h * d_head + e0)])
    var qv1 = Float32(q_native[Int(b * h_q * d_head + h * d_head + e0 + 1)])
    var qv2 = Float32(q_native[Int(b * h_q * d_head + h * d_head + e0 + 2)])
    var qv3 = Float32(q_native[Int(b * h_q * d_head + h * d_head + e0 + 3)])

    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)
    var o2 = Float32(0.0)
    var o3 = Float32(0.0)

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

        # Issue BOTH keys' K and V loads up front -- 16 independent loads in flight before either
        # softmax runs (`_f4` keeps only 8).
        var k_base_a = kv_off + (hk * n_blocks + block) * d_head * key_block_size + kk
        var k_base_b = kv_off + (hk * n_blocks + block2) * d_head * key_block_size + kk2
        var ka0 = Float32(k_native[Int(k_base_a + e0 * key_block_size)])
        var ka1 = Float32(k_native[Int(k_base_a + (e0 + 1) * key_block_size)])
        var ka2 = Float32(k_native[Int(k_base_a + (e0 + 2) * key_block_size)])
        var ka3 = Float32(k_native[Int(k_base_a + (e0 + 3) * key_block_size)])
        var kb0 = Float32(k_native[Int(k_base_b + e0 * key_block_size)])
        var kb1 = Float32(k_native[Int(k_base_b + (e0 + 1) * key_block_size)])
        var kb2 = Float32(k_native[Int(k_base_b + (e0 + 2) * key_block_size)])
        var kb3 = Float32(k_native[Int(k_base_b + (e0 + 3) * key_block_size)])
        var v_base_a = kv_off + ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        var v_base_b = kv_off + ((hk * n_blocks + block2) * key_block_size + kk2) * d_head + e0
        var va0 = Float32(v_native[Int(v_base_a)])
        var va1 = Float32(v_native[Int(v_base_a + 1)])
        var va2 = Float32(v_native[Int(v_base_a + 2)])
        var va3 = Float32(v_native[Int(v_base_a + 3)])
        var vb0 = Float32(v_native[Int(v_base_b)])
        var vb1 = Float32(v_native[Int(v_base_b + 1)])
        var vb2 = Float32(v_native[Int(v_base_b + 2)])
        var vb3 = Float32(v_native[Int(v_base_b + 3)])

        # Two INDEPENDENT dot products off the same Q registers -- pipelined simd_sums.
        var partial_a = qv0 * ka0 + qv1 * ka1 + qv2 * ka2 + qv3 * ka3
        var partial_b = qv0 * kb0 + qv1 * kb1 + qv2 * kb2 + qv3 * kb3
        var s_a = _warp_sum(partial_a) * scale
        var s_b = _warp_sum(partial_b) * scale

        # Key-order online softmax, first key then second (same accumulation sequence as `_f4`).
        var nm_a = m if m > s_a else s_a
        var corr_a = exp(m - nm_a)
        var w_a = exp(s_a - nm_a)
        o0 = o0 * corr_a + w_a * va0
        o1 = o1 * corr_a + w_a * va1
        o2 = o2 * corr_a + w_a * va2
        o3 = o3 * corr_a + w_a * va3
        denom = denom * corr_a + w_a
        m = nm_a

        var nm_b = m if m > s_b else s_b
        var corr_b = exp(m - nm_b)
        var w_b = exp(s_b - nm_b)
        o0 = o0 * corr_b + w_b * vb0
        o1 = o1 * corr_b + w_b * vb1
        o2 = o2 * corr_b + w_b * vb2
        o3 = o3 * corr_b + w_b * vb3
        denom = denom * corr_b + w_b
        m = nm_b

        kk = kk2
        block = block2
        kk += 1
        if kk == key_block_size:
            kk = 0
            block += 1
        j += 2

    # Odd-key epilogue: EXACTLY `_f4`'s single-key body.
    if j < key_end:
        var k_base = kv_off + (hk * n_blocks + block) * d_head * key_block_size + kk
        var partial = qv0 * Float32(k_native[Int(k_base + e0 * key_block_size)])
        partial += qv1 * Float32(k_native[Int(k_base + (e0 + 1) * key_block_size)])
        partial += qv2 * Float32(k_native[Int(k_base + (e0 + 2) * key_block_size)])
        partial += qv3 * Float32(k_native[Int(k_base + (e0 + 3) * key_block_size)])
        var s = _warp_sum(partial) * scale
        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        var v_base = kv_off + ((hk * n_blocks + block) * key_block_size + kk) * d_head + e0
        o0 = o0 * corr + w * Float32(v_native[Int(v_base)])
        o1 = o1 * corr + w * Float32(v_native[Int(v_base + 1)])
        o2 = o2 * corr + w * Float32(v_native[Int(v_base + 2)])
        o3 = o3 * corr + w * Float32(v_native[Int(v_base + 3)])
        denom = denom * corr + w
        m = nm

    if lane == 0:
        m_out[Int(idx)] = m
        l_out[Int(idx)] = denom
    o_out[Int(idx * d_head + e0)] = o0
    o_out[Int(idx * d_head + e0 + 1)] = o1
    o_out[Int(idx * d_head + e0 + 2)] = o2
    o_out[Int(idx * d_head + e0 + 3)] = o3
