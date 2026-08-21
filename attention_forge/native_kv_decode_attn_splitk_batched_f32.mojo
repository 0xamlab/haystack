"""attention_forge.native_kv_decode_attn_splitk_batched_f32 — W1 (continuous-batching decode on
the CUDA lane): the F32-KV batched flash-decoding twin of
`native_kv_decode_attn_splitk_batched` (the Metal f16-native pair). Additive — the originals are
byte-unmodified.

WHY A TWIN AT ALL
-----------------
Same load-path physics as the sibling `kvprod_batched_f32_cuda` documents: on this CUDA backend
only Float32 loads stream at HBM speed, and the CUDA resident session's KV cache is FLAT Float32
`[max_ctx, h_kv, d_head]` per cache — so the batched attention half must read flat f32 KV, not
f16 native-packed blocks. Kernel STRUCTURE is copied from the verified batched pair (sequence
decode from `block_idx.x`, per-sequence key count from a device array, uniform-stride cache
selection by scalar element offset); the element type, the loads, and the addressing swap to the
CUDA lane's flat f32 convention — the exact addressing `residentk.kernels._splitk_partial_
kernel_simd` already uses for the single-stream f32 cache, with the sequence axis added.

CONTRACT (generalizes the single-stream CUDA split-K pair, deliberate):
- PARTIAL writes UNNORMALIZED `(m, l, o)` partials at the globally-flattened index
  `idx = b * (h_q*n_splits) + h * n_splits + sidx = block_idx.x`, i.e. a `[B, h_q, n_splits]`
  layout that reduces to the single-stream `[h_q, n_splits]` layout when b==0. o UNNORMALIZED,
  same finite sentinel `_NEG_HUGE` for empty splits, so the merge folds empty splits as no-ops.
- MERGE: one threadgroup per (sequence, query head) (`grid = B * h_q`), associative online-softmax
  combine over `n_splits` partials, writes `attn_out[(b*h_q + h)*d_head + e] = o / denom`.
  Deliberately NO barrier: thread `e` only ever reads column `e` of every split's `o_in` and
  writes column `e` of its own output row — the thread-private-column property the single-stream
  merge's docstring establishes.
- PER-SEQUENCE STATE, MINIMAL DEVICE-SIDE INDIRECTION: all B sequences' KV caches live in ONE
  contiguous buffer each, selected by the scalar ELEMENT OFFSET `kv_off = b * kv_stride` paid as
  a scalar multiply in-kernel — no pointer-array dereference. The ONLY per-sequence device array
  is `nkeys` (B Int64 used-key counts), read once per threadgroup — the RAGGED contract: each
  sequence loops over `[0, nkeys[b])` of its own cache. Q is a contiguous `[B, h_q*d_head]` F32
  row stack; a sequence's query row is pure index arithmetic.
- KV ADDRESSING: flat, `kv_off + (j * h_kv + hk) * d_head + e` for BOTH K and V — the CUDA lane's
  position-major convention (the Metal pair's `key_block_size`/`n_blocks` block arithmetic does
  not exist in a flat cache).

Split `s` of `n_splits` owns keys `[n_keys * s // n_splits, n_keys * (s + 1) // n_splits)` of ITS
sequence — the single-stream partition applied per sequence: exact once-each coverage of
`[0, n_keys)` for any `n_keys`/`n_splits`, empty ranges fall out of the same loop, empty splits
write the untouched accumulator initial values and fold into the merge as genuine no-ops.

INHERITED, KNOWN, NOT-NEW: `d_head % 32 == 0` (caller-enforced); `_MAX_HEAD_DIM = 128`
shared-mem sizing ceiling for the per-SIMD-group partial array (Qwen3 d_head=128 sits exactly at
it); the two-level warp-shuffle reduction is byte-for-byte the single-stream CUDA kernel's own.
"""

from std.gpu import block_idx, lane_id, thread_idx, warp_id, WARP_SIZE
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import exp
from std.gpu.primitives.warp import sum as _warp_sum

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _MAX_HEAD_DIM: Int = 128
comptime _NEG_HUGE: Float32 = -3.0e38
"""Finite softmax-initial maximum — the single-stream pair's own sentinel, so an empty split's
`exp(_NEG_HUGE - nm)` underflows to a clean 0.0 instead of `inf - inf`."""


def _native_kv_decode_splitk_partial_batched_f32_kernel(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    nkeys: _I64P, kv_stride_i64: Int64,
    n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32,
):
    """BATCHED f32 PARTIAL half — one threadgroup per (sequence, query head, split)
    (`grid_dim = B * h_q * n_splits`, `block_dim = d_head`). Per-key math byte-for-byte the
    single-stream `_splitk_partial_kernel_simd`'s two-level warp-shuffle reduction; only the
    sequence decode (b from block_idx.x), the per-sequence key count (`nkeys[b]`), the KV element
    offset (`b * kv_stride`), and the Q row selection differ. See the module docstring for the
    layout/indirection contract."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)
    comptime _SIMD_GROUPS: Int = _MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()

    var idx = Int(block_idx.x)
    var per_seq = h_q * n_splits
    var b = idx // per_seq
    var rem = idx % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)

    var n_keys = Int(nkeys[b])
    var kv_off = b * kv_stride
    var qv = q_rot[(b * h_q + h) * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    # Split `sidx` of `n_splits` owns keys [key_start, key_end) of THIS sequence's `n_keys`.
    var key_start = (n_keys * sidx) // n_splits
    var key_end = (n_keys * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_start, key_end):
        var kb = kv_off + (j * h_kv + hk) * d_head
        var partial = qv * ck[kb + e]
        var group_total = _warp_sum(partial)
        if lane == 0:
            grp[grp_id] = group_total
        barrier()
        var s = Float32(0.0)
        for g in range(n_groups):
            s += grp[g]
        s *= scale
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * cv[kb + e]
        denom = denom * corr + w
        m = nm

    m_out[idx] = m
    l_out[idx] = denom
    o_out[idx * d_head + e] = o


def _native_kv_decode_splitk_merge_batched_f32_kernel(
    attn_out: _FP, m_in: _FP, l_in: _FP, o_in: _FP,
    n_splits_i64: Int64, h_q_i64: Int64, d_head_i64: Int64,
):
    """BATCHED f32 MERGE half — one threadgroup per (sequence, query head) (`grid_dim = B * h_q`,
    `block_dim = d_head`), combining the `[B, h_q, n_splits]` partials this module's partial
    kernel wrote. Math byte-for-byte `residentk.kernels._batched_splitk_merge_kernel_simd`'s own
    (that engine-side copy is already f32 — the merge touches no KV at all); this copy exists so
    the CUDA batched attention pair stays a self-contained forge module pair, exactly the way the
    Metal lane's pair is. Same associative online-softmax rescale-and-add; empty splits are
    genuine no-ops (finite `_NEG_HUGE` sentinel)."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var d_head = Int(d_head_i64)

    var idx = Int(block_idx.x)
    var b = idx // h_q
    var h = idx % h_q
    var e = Int(thread_idx.x)
    # Partial index of split 0 for this (b, h): b * (h_q*n_splits) + h * n_splits.
    var base = b * (h_q * n_splits) + h * n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)
    for s in range(n_splits):
        var pidx = base + s
        var sm = m_in[pidx]
        var sl = l_in[pidx]
        var nm = m if m > sm else sm
        var corr = exp(m - nm)
        var w = exp(sm - nm)
        o = o * corr + w * o_in[pidx * d_head + e]
        denom = denom * corr + w * sl
        m = nm

    attn_out[(b * h_q + h) * d_head + e] = o / denom
