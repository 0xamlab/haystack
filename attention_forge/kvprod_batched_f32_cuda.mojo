"""attention_forge.kvprod_batched_f32_cuda — W1 (continuous-batching decode on the CUDA lane):
the F32-KV batched twin of `kvprod_batched._native_kv_producer_batched_kernel`. Additive — the
Metal f16-native original is byte-unmodified.

WHY A TWIN AT ALL
-----------------
The campaign's proven load-path physics on this CUDA backend: ONLY Float32 vector loads stream
at HBM speed (f16 loads scalarize at 4-7% of peak). The Metal batched KV stack is Float16
native-packed (block-interleaved `[hk, block, d_head, kk]` addressing), but the CUDA resident
session (`residentk.session_cuda`) holds its KV cache as FLAT Float32 `[max_ctx, h_kv, d_head]`
per cache — the layout `_qk_rope_write_kernel` writes and `_splitk_partial_kernel_simd` reads.
This module is the batched KV producer for that world: QK-norm + RoPE + F32 packing for all B
sequences' new rows in ONE dispatch, appending each sequence's K/V into its OWN cache at its OWN
position.

CONTRACT (generalizes the single-stream CUDA producer `_qk_rope_write_kernel` the same way
`kvprod_batched` generalizes the Metal one):
- `grid_dim = (h_q + h_kv) * B`, `block_dim = d_head`. `block_idx.x` flattens to
  `seq = bidx // n_units`, `unit = bidx % n_units` (n_units = h_q + h_kv); `unit` is a Q head
  (unit < h_q) or a KV head (unit - h_q, owning both K and V rows). ONE ROW PER SEQUENCE (decode
  appends one token), so the single-stream row index collapses to the sequence index.
- PER-SEQUENCE STATE via the minimal-indirection mechanism the Metal batched pair established:
  all B sequences' KV caches live in ONE contiguous K buffer + ONE contiguous V buffer, a
  sequence's cache selected by the scalar ELEMENT OFFSET `kv_off = seq * kv_stride`
  (uniform-stride, every cache provisioned to the same max_ctx). The ONLY per-sequence device
  arrays are `poss` (B Int64 absolute positions), read once per threadgroup; the RoPE angle and
  the cache slot both derive from `pos = poss[seq]`.
- KV ADDRESSING is the CUDA lane's flat convention (NOT the Metal block-interleaved one):
  K slot `kv_off + (pos * h_kv + hk) * d_head + e`, V slot `kv_off + (pos * h_kv + hk) * d_head + e`
  — byte-for-byte the offset `_qk_rope_write_kernel` uses for the single-stream `ck`/`cv`, with
  the sequence offset added. The Metal twin's `key_block_size`/`n_blocks` arguments therefore do
  not exist here: the flat layout has no block structure.
- Q is written to the contiguous `[B, h_q*d_head]` F32 stack `q_rot[seq*h_q*d_head + head*d_head + e]`
  — the exact layout `native_kv_decode_attn_splitk_batched_f32`'s partial kernel reads as its
  per-sequence query row.
- The TRAILING `qk_norm` flag carries the SAME family convention the Metal producer's flag does:
  1 = Qwen3 per-head RMSNorm-then-gain before rotating (the CUDA resident session is Qwen3-family
  and always passes 1); 0 = rotate-the-raw-projection, `qn_w`/`kn_w` never read.

INHERITED, KNOWN, NOT-NEW: `d_head % 2 == 0` for the split-half RoPE; `_MAX_HEAD_DIM = 128`
shared-mem sizing ceiling (Qwen3 d_head=128 sits exactly at it).
"""

from std.gpu import block_idx, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import sqrt

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _MAX_HEAD_DIM: Int = 128
"""Shared-mem sizing ceiling, the same constant the sibling forge modules use."""


def _native_kv_producer_batched_f32_kernel(
    q_rot: _FP, k_cache: _FP, v_cache: _FP,
    qkv: _FP, qn_w: _FP, kn_w: _FP, cos_t: _FP, sin_t: _FP,
    poss: _I64P, kv_stride_i64: Int64,
    h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    eps: Float32, qk_norm_i64: Int64,
):
    """BATCHED f32 producer — one threadgroup per (sequence, head-unit)
    (`grid_dim = (h_q+h_kv)*B`, `block_dim = d_head`). Per-sequence state (position `poss[seq]`,
    cache offset `seq*kv_stride`) via the minimal-indirection mechanism; norm + RoPE math
    byte-for-byte the single-stream `_qk_rope_write_kernel`'s own (same shared-memory tree
    reduction, same NeoX split-half rotation), only the KV write gains the flat sequence offset.
    See the module docstring for the layout contract."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)
    var qk_norm = Int(qk_norm_i64)

    var xs = stack_allocation[_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED]()

    var n_units = h_q + h_kv
    var seq = Int(block_idx.x) // n_units
    var unit = Int(block_idx.x) % n_units
    var pos = Int(poss[seq])
    var kv_off = seq * kv_stride
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = seq * n_qkv
    var row_q_rot = seq * (h_q * d_head)

    var e = Int(thread_idx.x)
    var is_q = unit < h_q
    var head = unit if is_q else unit - h_q  # for K/V units, `head` IS the kv-head index `hk`

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    var v = qkv[src_off]

    if qk_norm == 1:
        var g = qn_w[e] if is_q else kn_w[e]

        # Full-head RMSNorm reduction — shared-memory tree reduction over v*v across all d_head
        # lanes, byte-identical formula to the single-stream CUDA producer.
        red[e] = v * v
        barrier()
        var stride = d_head // 2
        while stride > 0:
            if e < stride:
                red[e] = red[e] + red[e + stride]
            barrier()
            stride //= 2
        var inv = 1.0 / sqrt(red[0] / Float32(d_head) + eps)
        xs[e] = v * inv * g
        barrier()
    else:
        # No QK-norm: rotate the RAW projection; `qn_w`/`kn_w` never read. Same barrier
        # discipline as the norm arm: every lane publishes its `xs` slot before the NeoX
        # split-half exchange below reads its partner's slot.
        xs[e] = v
        barrier()

    # NeoX split-half RoPE: pairs (e, e+n_pairs), never the interleaved (2e,2e+1) convention.
    var n_pairs = d_head // 2
    if e < n_pairs:
        var c = cos_t[pos * n_pairs + e]
        var s = sin_t[pos * n_pairs + e]
        var a0 = xs[e]
        var a1 = xs[e + n_pairs]
        var o0 = a0 * c - a1 * s
        var o1 = a0 * s + a1 * c
        if is_q:
            var qb = row_q_rot + head * d_head
            q_rot[qb + e] = o0
            q_rot[qb + e + n_pairs] = o1
        else:
            # Flat CUDA KV layout: position-major within the kv-head, offset by the sequence slot.
            var kb = kv_off + (pos * h_kv + head) * d_head
            k_cache[kb + e] = o0
            k_cache[kb + e + n_pairs] = o1

    # V is neither normalized nor rotated — straight into its cache slot. All d_head threads
    # participate, which is why this is outside the `e < n_pairs` guard above.
    if not is_q:
        v_cache[kv_off + (pos * h_kv + head) * d_head + e] = qkv[
            row_qkv + (h_q + h_kv + head) * d_head + e
        ]
