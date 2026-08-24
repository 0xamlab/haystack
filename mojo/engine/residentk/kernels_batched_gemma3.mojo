"""
residentk.kernels_batched_gemma3 — the Gemma 3 family's BATCHED DECODE kernels (Gemma 3 lane,
2026-08-24): the B-sequence decode step kernels the single-stream gemma3 chain does not have.
Zero Python. ADDITIVE: nothing in `residentk.kernels`, `residentk.kernels_gemma3`, or the
Qwen3 batched modules is touched.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32, float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/gemma3_batched_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/gemma3_batched_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Same private-name discipline as `residentk.kernels`.

What is NEW here, and what is reused instead
--------------------------------------------
* `_g3_ropewrt_batched_kernel` — the B-row twin of `_pf_ropewrt_kernel` with a DEVICE `poss`
  array: row `b` is sequence `b`'s decode token at ABSOLUTE position `poss[b]` (the Qwen3
  batched chain splits rope/KV-write into a producer that reads `poss`; Gemma 3's fused
  q_norm + k_norm + RoPE + KV-write kernel takes the sequence axis directly — one dispatch
  instead of two). The KV write lands at `b * kv_stride + (pos * h_kv + head) * d_head`:
  every sequence's cache lives in ONE contiguous buffer, selected by the scalar element
  offset — the uniform-stride contract `attention_forge.native_kv_decode_attn_splitk_batched_f32`
  establishes. The SESSION passes the per-layer global/local rope-table pointers, which is how
  Gemma's dual theta lands with no kernel change (same pointer-select the single-stream path
  uses). qk_norm stays a runtime flag (Gemma 3 always passes 1).
* `_g3_kv_decode_splitk_partial_batched_kernel` — the WINDOWED batched flash-decoding partial:
  `_native_kv_decode_splitk_partial_batched_f32_kernel` with Gemma's sliding-window lower
  bound. `window = 0` = a full-attention layer (key_lo = 0, the qwen3 kernel exactly);
  `window > 0` = a sliding layer, attending only `[max(0, n_keys - window), n_keys)` — the
  SAME split-the-span partition `_g3_splitk_partial_kernel_simd_g` uses for the single-stream
  graph arm, widened with the sequence axis. Per-key math and the (m, l, o) unnormalized
  contract are byte-for-byte the batched qwen3 kernel's.
* `_g3_batched_lmhead_argmax_kernel_f16` — the Float16-weight twin of
  `_batched_lmhead_argmax_kernel_f32`: all-B-rows-per-weight-sweep lm_head + per-vocab-slice
  argmax, weights resident Float16 widened on load (the 27B race arm's storage), same strict-`>`
  lowest-id tie-break, same `_BATCH_LMHEAD_MAX_ROWS` ceiling.

MERGE is REUSED verbatim: `attention_forge.native_kv_decode_attn_splitk_batched_f32.
_native_kv_decode_splitk_merge_batched_f32_kernel` is KV- and weight-agnostic (it only folds
the `[B, h_q, n_splits]` partials), and the partial layout this module writes is that contract
exactly. The B-row argmax reduce reuses `residentk.kernels._batched_argmax_reduce_kernel_simd`
(weight-agnostic by construction).
"""

from std.origin import MutAnyOrigin
from std.gpu import block_idx, grid_dim, lane_id, thread_idx, warp_id, WARP_SIZE
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.math import exp, sqrt
from std.memory import stack_allocation
from std.gpu.primitives.warp import sum as _warp_sum
from residentk.contract import RESIDENT_MAX_HEAD_DIM
from residentk.loadvec import _ld4
from residentk.kernels import (
    _TG,
    _LANES,
    _SUBS,
    _BATCH_LMHEAD_MAX_ROWS,
    _NEG_HUGE,
)

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _VEC: Int = 4
comptime _VEC_STRIDE: Int = _LANES * _VEC


def _g3_ropewrt_batched_kernel(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, poss: _I64P, kv_stride_i64: Int64,
    h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64, eps: Float32, B_i64: Int64,
    qk_norm_i64: Int64,
):
    """BATCHED twin of `_pf_ropewrt_kernel` for B sequences' decode tokens — IDENTICAL per-row
    q_norm/k_norm/RoPE math, with TWO differences: row `b`'s absolute position comes from the
    device array `poss[b]` (one decode token per sequence, each at its own position), and the
    KV-cache write lands at `b * kv_stride + (pos * h_kv + head) * d_head` — the uniform-stride
    batch-cache contract. `grid_dim = (h_q + h_kv) * B`, `block_dim = d_head`,
    `b = block_idx.x % ...` flattened exactly the way `_pf_ropewrt_kernel` flattens `(unit, m)`.
    `q_rot` is `[B, h_q * d_head]` row-major; the batched attention dispatch immediately after
    this one reads row `b` as sequence `b`'s query."""
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var B = Int(B_i64)
    var qk_norm = Int(qk_norm_i64)
    var kv_stride = Int(kv_stride_i64)
    var n_units = h_q + h_kv
    var unit = Int(block_idx.x) % n_units
    var b = Int(block_idx.x) // n_units
    if b >= B:
        return
    var pos = Int(poss[b])
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = b * n_qkv
    var n_q = h_q * d_head
    var row_q_rot = b * n_q

    var xs = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var e = Int(thread_idx.x)
    var is_q = unit < h_q
    var head = unit if is_q else unit - h_q

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    var v = qkv[src_off]
    if qk_norm == 1:
        var g = qn_w[e] if is_q else kn_w[e]

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
        xs[e] = v
        barrier()

    var n_pairs = d_head // 2
    var kv_off = b * kv_stride
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
            var kb = kv_off + (pos * h_kv + head) * d_head
            ck[kb + e] = o0
            ck[kb + e + n_pairs] = o1

    if not is_q:
        cv[kv_off + (pos * h_kv + head) * d_head + e] = \
            qkv[row_qkv + (h_q + h_kv + head) * d_head + e]


def _g3_kv_decode_splitk_partial_batched_kernel(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    nkeys: _I64P, kv_stride_i64: Int64,
    n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32, window_i64: Int64,
):
    """WINDOWED batched flash-decoding partial — `_native_kv_decode_splitk_partial_batched_f32_kernel`
    plus Gemma 3's sliding-window lower bound. `grid_dim = B * h_q * n_splits`,
    `block_dim = d_head`; one threadgroup per (sequence, query head, split). `window = 0`
    (a full-attention layer) attends `[0, n_keys)` — the qwen3 kernel exactly; `window > 0`
    (a sliding layer) attends `[max(0, n_keys - window), n_keys)`, and the split partition
    covers THAT span: split `s` owns `[key_lo + span*s//n_splits, key_lo + span*(s+1)//n_splits)`
    — `_g3_splitk_partial_kernel_simd_g`'s partition widened with the sequence axis. Per-key
    two-level warp-shuffle reduction and the unnormalized `(m, l, o)` contract are the batched
    qwen3 kernel's byte-for-byte; empty splits fold into the merge as no-ops."""
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)
    var window = Int(window_i64)
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
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
    var key_lo = 0
    if window > 0:
        key_lo = n_keys - window
        if key_lo < 0:
            key_lo = 0
    var span = n_keys - key_lo
    var key_start = key_lo + (span * sidx) // n_splits
    var key_end = key_lo + (span * (sidx + 1)) // n_splits

    var kv_off = b * kv_stride
    var qv = q_rot[(b * h_q + h) * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

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


def _g3_ropewrt_batched_kernel_kv16(
    q_rot: _FP, ck: _HP, cv: _HP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, poss: _I64P, kv_stride_i64: Int64,
    h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64, eps: Float32, B_i64: Int64,
    qk_norm_i64: Int64,
):
    """Float16-KV twin of `_g3_ropewrt_batched_kernel` — identical rope math (f32 throughout);
    ONLY the KV-cache write narrows to Float16 at the store. The C=50 fit lever: the batched
    KV cache halves its VRAM footprint so 50 sequences x the sonnet shape fit one 80 GB H100
    next to the 54 GB f16 weight residency."""
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var B = Int(B_i64)
    var qk_norm = Int(qk_norm_i64)
    var kv_stride = Int(kv_stride_i64)
    var n_units = h_q + h_kv
    var unit = Int(block_idx.x) % n_units
    var b = Int(block_idx.x) // n_units
    if b >= B:
        return
    var pos = Int(poss[b])
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = b * n_qkv
    var n_q = h_q * d_head
    var row_q_rot = b * n_q

    var xs = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var e = Int(thread_idx.x)
    var is_q = unit < h_q
    var head = unit if is_q else unit - h_q

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    var v = qkv[src_off]
    if qk_norm == 1:
        var g = qn_w[e] if is_q else kn_w[e]

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
        xs[e] = v
        barrier()

    var n_pairs = d_head // 2
    var kv_off = b * kv_stride
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
            var kb = kv_off + (pos * h_kv + head) * d_head
            ck[kb + e] = Float16(o0)
            ck[kb + e + n_pairs] = Float16(o1)

    if not is_q:
        cv[kv_off + (pos * h_kv + head) * d_head + e] = \
            Float16(qkv[row_qkv + (h_q + h_kv + head) * d_head + e])


def _g3_kv_decode_splitk_partial_batched_kernel_kv16(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _HP, cv: _HP,
    nkeys: _I64P, kv_stride_i64: Int64,
    n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32, window_i64: Int64,
):
    """Float16-KV twin of `_g3_kv_decode_splitk_partial_batched_kernel`: the windowed batched
    flash-decoding partial reading a Float16 KV cache (each element widened to f32 before the
    multiply — the accumulation stays f32, byte-for-byte the f32-KV kernel's math otherwise)."""
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)
    var window = Int(window_i64)
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
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
    var key_lo = 0
    if window > 0:
        key_lo = n_keys - window
        if key_lo < 0:
            key_lo = 0
    var span = n_keys - key_lo
    var key_start = key_lo + (span * sidx) // n_splits
    var key_end = key_lo + (span * (sidx + 1)) // n_splits

    var kv_off = b * kv_stride
    var qv = q_rot[(b * h_q + h) * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_start, key_end):
        var kb = kv_off + (j * h_kv + hk) * d_head
        var partial = qv * Float32(ck[kb + e])
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
        o = o * corr + w * Float32(cv[kb + e])
        denom = denom * corr + w
        m = nm

    m_out[idx] = m
    l_out[idx] = denom
    o_out[idx * d_head + e] = o


def _g3_batched_lmhead_argmax_kernel_f16(
    blk_val: _FP, blk_idx: _IP, xn: _FP, w: _HP,
    B_i64: Int64, k_i64: Int64, n_i64: Int64, n_iters_i64: Int64,
):
    """Float16-weight twin of `_batched_lmhead_argmax_kernel_f32`: batched lm_head +
    per-vocab-slice argmax for B rows — all B rows of `xn` (`[B, k]`, PRE-NORMALIZED by the
    B-row final rmsnorm dispatch that runs immediately before) dotted against each `w` row in
    ONE sweep (the tokens-per-weight-sweep win), weights resident Float16 widened on load.
    Same vocab partitioning (`j = block_idx.x*_SUBS + sub + it*stride_cols`), same strict-`>`
    lowest-id tie-break, same `_BATCH_LMHEAD_MAX_ROWS` ceiling, same passed-in `n_iters`
    uniform-trip-count contract, and the SAME `(blk_val, blk_idx)` pair layout the f32 twin
    writes — `_batched_argmax_reduce_kernel_simd` consumes it byte-unmodified."""
    var B = Int(B_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    var n_iters = Int(n_iters_i64)
    var sv = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var si = stack_allocation[
        _SUBS * _BATCH_LMHEAD_MAX_ROWS, DType.int32, address_space = AddressSpace.SHARED
    ]()
    var acc = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.float32]()
    var best = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.float32]()
    var best_i = stack_allocation[_BATCH_LMHEAD_MAX_ROWS, DType.int32]()

    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    for b in range(B):
        best[b] = _NEG_HUGE
        best_i[b] = Int32(-1)

    var stride_cols = Int(grid_dim.x) * _SUBS
    var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        if j < n:
            for b in range(B):
                acc[b] = Float32(0.0)
            var base = j * k
            var t = lane * _VEC
            while t < k_vec:
                var wv = w.load[width=_VEC](base + t).cast[DType.float32]()
                for b in range(B):
                    var xv = xn.load[width=_VEC](b * k + t)
                    var pv = xv * wv
                    acc[b] += pv[0] + pv[1] + pv[2] + pv[3]
                t += _VEC_STRIDE
            var tt = k_vec + lane
            while tt < k:
                var wvv = Float32(w[base + tt])
                for b in range(B):
                    acc[b] += xn[b * k + tt] * wvv
                tt += _LANES
            for b in range(B):
                var total = _warp_sum(acc[b])
                if lane == 0:
                    if total > best[b]:
                        best[b] = total
                        best_i[b] = Int32(j)

    if lane == 0:
        for b in range(B):
            sv[sub * _BATCH_LMHEAD_MAX_ROWS + b] = best[b]
            si[sub * _BATCH_LMHEAD_MAX_ROWS + b] = best_i[b]
    barrier()
    if tid == 0:
        for b in range(B):
            var bv = sv[b]
            var bi = si[b]
            for u in range(1, _SUBS):
                # Strictly greater, so the lowest id survives an exact tie.
                if sv[u * _BATCH_LMHEAD_MAX_ROWS + b] > bv:
                    bv = sv[u * _BATCH_LMHEAD_MAX_ROWS + b]
                    bi = si[u * _BATCH_LMHEAD_MAX_ROWS + b]
            blk_val[b * Int(grid_dim.x) + Int(block_idx.x)] = bv
            blk_idx[b * Int(grid_dim.x) + Int(block_idx.x)] = bi


comptime _G3_DECODE_FLASH_NTHREADS: Int = 256
"""Threads per block of the flash batched partial: 8 warps, one (sequence, head, split) unit
per warp — the geometry `residentk.kernels_decode_attn_flash._splitk_partial_batched_flash_kernel`
established and the serve lane proved."""

comptime _G3_DECODE_FLASH_WARPS_PER_BLOCK: Int = _G3_DECODE_FLASH_NTHREADS // 32


def _g3_kv_decode_splitk_partial_batched_kernel_kv16_flash(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _HP, cv: _HP,
    nkeys: _I64P, B_i64: Int64, kv_stride_i64: Int64,
    n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32, window_i64: Int64,
):
    """FLASH-STYLE twin of `_g3_kv_decode_splitk_partial_batched_kernel_kv16` — lever 1 of the
    vLLM-flip round (nsys 2026-08-24: the barrier-tree partial streamed the 20.6 GB C=50 KV at
    only 630 GB/s = 19% HBM3), a FAITHFUL kv16 + Gemma3-windowed port of the serve lane's
    PROVEN `_splitk_partial_batched_flash_kernel` (`residentk.kernels_decode_attn_flash`):

    * ONE WARP per (sequence, query head, split) unit — `grid_dim =
      ceil(B * h_q * n_splits / 8)`, `block_dim = 256` (8 warp-units per block); the per-key
      FULL-BLOCK barrier tree (TWO `barrier()` hits per key) is deleted entirely;
    * keys stream ASCENDING within each split, exactly the legacy accumulation order — the
      online-softmax recurrence is byte-for-byte the barrier-tree kernel's per-key math, and
      the ONLY numerical difference is the score dot's reduction tree (one warp's 32-lane
      butterfly over 4-element lane partials vs four warps + shared combine): the same 128
      products, ulp-level reordering — the proven byte-compatible contract;
    * BLOCK-8 online softmax (the serve lane's measured latency lever): 8 independent K
      loads + dots, ONE rescale for the block max, then the block's V-accum — the serial
      load->score->rescale->V-accum chain cut ~8x;
    * K/V rows load as ONE 8-byte vectorized f16 load per lane (`alignment=8`, provable:
      the batch-KV row base is 256-byte aligned, `lane*4` elements = `lane*8` bytes), widened
      to f32 before the multiply — accumulation stays f32, the kv16 kernel's exact arithmetic.

    Gemma 3 window: split `sidx` owns `[key_lo + span*sidx//n_splits, key_lo +
    span*(sidx+1)//n_splits)` of `span = n_keys - key_lo`, `key_lo = max(0, n_keys - window)`
    (`window = 0` = a full-attention layer) — `_g3_kv_decode_splitk_partial_batched_kernel_kv16`'s
    partition verbatim. Empty splits write the same finite `_NEG_HUGE`/0 sentinel and fold into
    the unchanged merge kernel as genuine no-ops. CONTRACT: `d_head == 128` (caller-enforced,
    fact-driven capability dispatch)."""
    var B = Int(B_i64)
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var kv_stride = Int(kv_stride_i64)
    var window = Int(window_i64)

    var per_seq = h_q * n_splits
    var u = Int(block_idx.x) * _G3_DECODE_FLASH_WARPS_PER_BLOCK + Int(warp_id())
    if u >= B * per_seq:
        return
    var b = u // per_seq
    var rem = u % per_seq
    var h = rem // n_splits
    var sidx = rem % n_splits

    var lane = Int(lane_id())
    var e0 = lane * 4
    var hk = h // (h_q // h_kv)

    var n_keys = Int(nkeys[b])
    var kv_off = b * kv_stride

    var key_lo = 0
    if window > 0:
        key_lo = n_keys - window
        if key_lo < 0:
            key_lo = 0
    var span = n_keys - key_lo
    var key_start = key_lo + (span * sidx) // n_splits
    var key_end = key_lo + (span * (sidx + 1)) // n_splits

    var qv = _ld4(q_rot, (b * h_q + h) * d_head + e0)
    var q0 = qv[0]
    var q1 = qv[1]
    var q2 = qv[2]
    var q3 = qv[3]

    var mx = _NEG_HUGE
    var denom = Float32(0.0)
    var o0 = Float32(0.0)
    var o1 = Float32(0.0)
    var o2 = Float32(0.0)
    var o3 = Float32(0.0)

    # ── block-8 online softmax: 8 independent scores, ONE rescale, then the block's V-accum ──
    var j0 = key_start
    while j0 < key_end:
        var nb = key_end - j0
        if nb > 8:
            nb = 8

        var bs0 = _NEG_HUGE
        var bs1 = _NEG_HUGE
        var bs2 = _NEG_HUGE
        var bs3 = _NEG_HUGE
        var bs4 = _NEG_HUGE
        var bs5 = _NEG_HUGE
        var bs6 = _NEG_HUGE
        var bs7 = _NEG_HUGE
        if nb >= 1:
            var kb = kv_off + (j0 * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs0 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 2:
            var kb = kv_off + ((j0 + 1) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs1 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 3:
            var kb = kv_off + ((j0 + 2) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs2 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 4:
            var kb = kv_off + ((j0 + 3) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs3 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 5:
            var kb = kv_off + ((j0 + 4) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs4 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 6:
            var kb = kv_off + ((j0 + 5) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs5 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 7:
            var kb = kv_off + ((j0 + 6) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs6 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale
        if nb >= 8:
            var kb = kv_off + ((j0 + 7) * h_kv + hk) * d_head + e0
            var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
            bs7 = _warp_sum(q0 * kv4[0] + q1 * kv4[1] + q2 * kv4[2] + q3 * kv4[3]) * scale

        # ONE rescale for the whole block
        var bmax = bs0
        if bs1 > bmax:
            bmax = bs1
        if bs2 > bmax:
            bmax = bs2
        if bs3 > bmax:
            bmax = bs3
        if bs4 > bmax:
            bmax = bs4
        if bs5 > bmax:
            bmax = bs5
        if bs6 > bmax:
            bmax = bs6
        if bs7 > bmax:
            bmax = bs7
        var nm = mx if mx > bmax else bmax
        var corr = exp(mx - nm)
        o0 = o0 * corr
        o1 = o1 * corr
        o2 = o2 * corr
        o3 = o3 * corr
        denom = denom * corr
        mx = nm

        if nb >= 1:
            var w = exp(bs0 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + (j0 * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 2:
            var w = exp(bs1 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + ((j0 + 1) * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 3:
            var w = exp(bs2 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + ((j0 + 2) * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 4:
            var w = exp(bs3 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + ((j0 + 3) * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 5:
            var w = exp(bs4 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + ((j0 + 4) * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 6:
            var w = exp(bs5 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + ((j0 + 5) * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 7:
            var w = exp(bs6 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + ((j0 + 6) * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w
        if nb >= 8:
            var w = exp(bs7 - nm)
            var vv4 = cv.load[width=4, alignment=8](
                kv_off + ((j0 + 7) * h_kv + hk) * d_head + e0).cast[DType.float32]()
            o0 += w * vv4[0]
            o1 += w * vv4[1]
            o2 += w * vv4[2]
            o3 += w * vv4[3]
            denom += w

        j0 += 8

    var idx = u
    if lane == 0:
        m_out[idx] = mx
        l_out[idx] = denom
    var ob = idx * d_head + e0
    o_out[ob + 0] = o0
    o_out[ob + 1] = o1
    o_out[ob + 2] = o2
    o_out[ob + 3] = o3


def _g3_logits_argmax_kernel(
    out_val: _FP, out_idx: _IP, logits: _FP, B_i64: Int64, n_i64: Int64,
):
    """Per-row argmax over a materialised `[B, n]` f32 logits table — ONE block per row,
    ascending sweep, strict-`>` comparison, so the LOWEST id survives an exact tie: the
    byte-for-byte tie-break contract of `_g3_batched_lmhead_argmax_kernel_f16`. This is the
    second half of the G3_STREAM lm_head lever (nsys, 2026-08-24): the batched fused kernel
    cost 48.2 ms/step at B=50 (43% of the 112 ms C=50 step — its per-thread B-row
    accumulator arrays collapse occupancy at B=50), while the same logits GEMM through the
    stream-ordered cuBLAS seam streams the 2.8 GB tie table at HBM speed; this kernel then
    sweeps the `[B, vocab]` logits once for the per-row maxima. `grid_dim = B`,
    `block_dim = _TG`; writes `out_val[b]` / `out_idx[b]` directly — the reduce stage the
    fused kernel needed is gone with it."""
    var B = Int(B_i64)
    var n = Int(n_i64)
    var b = Int(block_idx.x)
    if b >= B:
        return
    var tid = Int(thread_idx.x)
    var nt = _TG
    var base = b * n
    var bv = _NEG_HUGE
    var bi = Int32(-1)
    var j = tid
    while j < n:
        var v = logits[base + j]
        if v > bv:
            bv = v
            bi = Int32(j)
        j += nt
    var sv = stack_allocation[
        _TG, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var si = stack_allocation[
        _TG, DType.int32, address_space = AddressSpace.SHARED
    ]()
    sv[tid] = bv
    si[tid] = bi
    barrier()
    if tid == 0:
        var mv = sv[0]
        var mi = si[0]
        for u in range(1, nt):
            if sv[u] > mv:
                mv = sv[u]
                mi = si[u]
        out_val[b] = mv
        out_idx[b] = mi
