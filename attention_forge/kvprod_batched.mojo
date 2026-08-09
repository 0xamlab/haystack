"""attention_forge.native_kv_producer_batched -- Project Slipstream Phase 3 (2026-08-09): the
BATCHED / continuous-batching twin of `native_kv_producer._native_kv_producer_kernel`. Batched decode
runs B sequences, each producing ONE new token per step; this producer applies QK-norm + RoPE +
F16-narrowing + native-KV-packing for all B sequences' new rows in a single dispatch, appending each
sequence's K/V into its OWN cache at its OWN position. It is the KV-write half of the batched-decode
path whose attention half is `native_kv_decode_attn_splitk_batched`.

CONTRACT (generalizes the single-stream producer, deliberate): the grid/threadgroup organization, the
full-head RMSNorm reduction, and the NeoX split-half RoPE math are byte-for-byte the single-stream
kernel's; only the sequence decode and the per-sequence state differ:
- `grid_dim = (h_q + h_kv) * B`, `block_dim = d_head`. `block_idx.x` flattens to
  `seq = bidx // n_units`, `unit = bidx % n_units` (n_units = h_q + h_kv), where `unit` is a Q head
  (unit < h_q) or a KV head (unit - h_q, owning both K and V rows) exactly as the single-stream
  kernel's `b` does. ONE ROW PER SEQUENCE (decode appends one token), so there is no `m` loop -- the
  single-stream kernel's row index `m` collapses to the sequence index `seq`.
- PER-SEQUENCE STATE via the same minimal-indirection mechanism the batched attention kernel uses:
  all B sequences' KV caches live in ONE contiguous K buffer + ONE contiguous V buffer, so a
  sequence's cache is selected by the scalar ELEMENT OFFSET `kv_off = seq * kv_stride` (uniform-stride,
  all caches provisioned to the same max_ctx, `n_blocks` a uniform scalar). The ONLY per-sequence
  device array is `poss` (B Int64 absolute positions), read once per threadgroup; the RoPE angle and
  the (block, kk) cache slot both derive from `pos = poss[seq]`.
- Q is written to the contiguous `[B, h_q*d_head]` stack `q_rot[seq*h_q*d_head + head*d_head + e]` --
  the exact layout the batched attention kernel reads as its per-sequence query row.
- K/V native-packing flat-index formulas are identical to the single-stream producer's, offset by
  `kv_off`: K `kv_off + ((hk*n_blocks+block)*d_head+d)*key_block_size+kk`;
  V `kv_off + ((hk*n_blocks+block)*key_block_size+kk)*d_head+d`.

INHERITED, KNOWN, NOT-NEW: `d_head % 2 == 0` for the split-half RoPE (n_pairs = d_head//2);
`_MAX_HEAD_DIM = 128` shared-mem sizing ceiling (Qwen3 d_head=128 sits exactly at it).

DISCOVERY NAMING (for the later engine wiring, flagged now): the kernel name deliberately does NOT
embed the single-stream producer's discovery substring as a prefix the scan would hit first -- when
wired into the session's blob discovery, check the LONGER `native_kv_producer_batched` substring
BEFORE `native_kv_producer`, same longest-first discipline as the attention pair. Not yet wired;
standalone correctness only at this stage.

    cd mma_forge
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo run -I . -I ../attention_forge \
      ../attention_forge/native_kv_producer_batched_driver.mojo
"""
from std.gpu import thread_idx, block_idx
from max.gpu.sync import barrier
from max.gpu.memory import AddressSpace
from std.memory import stack_allocation
from std.math import sqrt

comptime _F16P = UnsafePointer[Float16, origin=MutAnyOrigin]
comptime _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
comptime _IP = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _MAX_HEAD_DIM: Int64 = 128


def _native_kv_producer_batched_kernel(
    q_rot: _F16P, k_native: _F16P, v_native: _F16P,
    qkv: _FP, qn_w: _FP, kn_w: _FP, cos_t: _FP, sin_t: _FP,
    poss: _IP, kv_stride: Int64,
    h_q: Int64, h_kv: Int64, d_head: Int64,
    key_block_size: Int64, n_blocks: Int64, eps: Float32,
):
    """BATCHED producer -- one threadgroup per (sequence, head-unit) (`grid_dim = (h_q+h_kv)*B`,
    `block_dim = d_head`). Per-sequence state (position `poss[seq]`, cache offset `seq*kv_stride`)
    via the minimal-indirection mechanism; norm + RoPE + packing byte-identical to the single-stream
    `_native_kv_producer_kernel`. See the module docstring for the layout contract."""
    var xs = stack_allocation[Int(_MAX_HEAD_DIM), DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[Int(_MAX_HEAD_DIM), DType.float32, address_space = AddressSpace.SHARED]()

    var n_units = h_q + h_kv
    var bidx = Int64(block_idx.x)
    var seq = bidx // n_units
    var unit = bidx % n_units
    var pos = poss[Int(seq)]
    var kv_off = seq * kv_stride
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = seq * n_qkv
    var row_q_rot = seq * (h_q * d_head)

    var e = Int64(thread_idx.x)
    var is_q = unit < h_q
    var head = unit if is_q else unit - h_q  # for K/V units, `head` IS the kv_head index `hk`

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    var v = qkv[Int(src_off)]
    var g = qn_w[Int(e)] if is_q else kn_w[Int(e)]

    # Full-head RMSNorm reduction -- shared-memory tree reduction over v*v across all d_head lanes,
    # byte-identical formula to the single-stream producer.
    red[Int(e)] = v * v
    barrier()
    var stride = d_head // 2
    while stride > 0:
        if e < stride:
            red[Int(e)] = red[Int(e)] + red[Int(e + stride)]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(d_head) + eps)
    xs[Int(e)] = v * inv * g
    barrier()

    # NeoX split-half RoPE: pairs (e, e+n_pairs), never the interleaved (2e,2e+1) convention.
    var n_pairs = d_head // 2
    if e < n_pairs:
        var c = cos_t[Int(pos * n_pairs + e)]
        var s = sin_t[Int(pos * n_pairs + e)]
        var a0 = xs[Int(e)]
        var a1 = xs[Int(e + n_pairs)]
        var o0 = a0 * c - a1 * s
        var o1 = a0 * s + a1 * c
        if is_q:
            var qb = row_q_rot + head * d_head
            q_rot[Int(qb + e)] = Float16(o0)
            q_rot[Int(qb + e + n_pairs)] = Float16(o1)
        else:
            var hk = head
            var block = pos // key_block_size
            var kk = pos % key_block_size
            # kv_off is a FLAT element offset into the shared K buffer (the batched attention
            # kernel's convention) -- added to the final packed index, never scaled by it.
            var block_base = (hk * n_blocks + block) * d_head
            k_native[Int(kv_off + (block_base + e) * key_block_size + kk)] = Float16(o0)
            k_native[Int(kv_off + (block_base + e + n_pairs) * key_block_size + kk)] = Float16(o1)

    if not is_q:
        var hk = head
        var block = pos // key_block_size
        var kk = pos % key_block_size
        var v_val = qkv[Int(row_qkv + (h_q + h_kv + head) * d_head + e)]
        var v_block_base = (hk * n_blocks + block) * key_block_size + kk
        v_native[Int(kv_off + v_block_base * d_head + e)] = Float16(v_val)
