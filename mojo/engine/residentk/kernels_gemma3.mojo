"""
residentk.kernels_gemma3 — the Gemma 3 family's decode kernels (Gemma 3 lane, 2026-08-23).
Zero Python. ADDITIVE: nothing in `residentk.kernels` is touched — the Qwen3/llama arms stay
byte-for-byte what they were.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/gemma3/ref_gemma3_torch.py
benchmark: benchmarks/llm_smoke/nvidia_race/gemma3_correctness_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Same private-name discipline as `residentk.kernels` (leading underscores keep every launch out of
the inventory/contract/dispatch; shader codegen only ever sees these through the static call graph
of a driver that imports them).

What Gemma 3 changes vs the Qwen3/llama decode chain, kernel by kernel
-----------------------------------------------------------------------
* `_g3_embed_row_kernel` — the input-embedding gather MULTIPLIED BY sqrt(hidden_size). Gemma's
  `Gemma3TextScaledWordEmbedding` scales inputs_embeds by embed_scale; the tied lm_head side is
  NOT scaled (that is a property of the forward, not of the table, so the argmax kernel keeps
  reading the raw table).
* `_g3_norm_gemv2_geglu_kernel` — the fused pre-FFN-norm + gate/up projection twin of
  `_norm_gemv2_swiglu_kernel` with GeGLU's epilogue: `gelu_pytorch_tanh(gate) * up` instead of
  `swish(gate) * up`. gelu_pytorch_tanh is PyTorch's tanh approximation
  `0.5*g*(1 + tanh(sqrt(2/pi)*(g + 0.044715*g^3)))`.
* `_g3_gemv_kernel` — a PLAIN GEMV `y = W @ x` (no residual add): Gemma 3 applies a norm to the
  o_proj / down_proj branch outputs BEFORE the residual add, so the branch output must be
  materialised (llama/Qwen3 accumulate it straight into the stream).
* `_g3_norm_accum_kernel` — `hidden += rmsnorm(y) * gain`: the post-branch norm + residual add
  (post_attention_layernorm after o_proj, post_feedforward_layernorm after down_proj). The gain
  buffers carry the converter's REBASED (1.0 + weight) values, so the gain-multiply computes
  Gemma's (1+w) convention exactly.
* `_g3_norm_inplace_kernel` — `x = rmsnorm(x) * gain` in place (the final norm before a dumped
  logits row).
* `_g3_sdpa_window_kernel` — `_sdpa_kernel` with a key lower bound: sliding-window layers attend
  only keys `[key_lo, n_keys)`. Full-attention layers pass key_lo = 0 and are bit-identical to
  the original.

What is REUSED verbatim from `residentk.kernels` (no twin needed):
* `_norm_gemv_kernel` (input_layernorm + fused QKV GEMV — Gemma's norm1 sits exactly where
  llama's does; the rebased (1+w) gain is just data to its gain-multiply),
* `_qk_rope_write_kernel` with qk_norm=1 (per-head RMSNorm-then-RoPE-then-cache-write — Gemma's
  exact order; the (1+w)-rebased q_norm/k_norm gains are data; the SESSION selects the per-layer
  rope table pointer, which is how dual theta lands with no kernel change),
* `_lmhead_argmax_kernel` + `_argmax_reduce_kernel` (final-norm + tied lm_head + argmax — the
  rebased final norm gain and the unscaled table are both data-level).
"""

from std.origin import MutAnyOrigin
from std.gpu import block_dim, block_idx, grid_dim, thread_idx, lane_id, warp_id, WARP_SIZE
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.gpu.primitives.warp import sum as _warp_sum
from std.math import exp, sqrt, tanh
from std.memory import stack_allocation
from residentk.contract import RESIDENT_MAX_D_MODEL, RESIDENT_MAX_HEAD_DIM

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
alias _I64P = UnsafePointer[Int64, origin=MutAnyOrigin]

comptime _TG: Int = 256
comptime _LANES: Int = 32
comptime _SUBS: Int = _TG // _LANES
comptime _VEC: Int = 4
comptime _VEC_STRIDE: Int = _LANES * _VEC
# Float16-weight vector widths — the SAME values `residentk.kernels` measured for its `_f16` twins
# (half4 is a real vector type; half8 is not, and width 8 measured slower). Kept private here so
# this module stays self-contained.
comptime _VEC_H: Int = 4
comptime _VEC_STRIDE_H: Int = _LANES * _VEC_H
comptime _NEG_HUGE: Float32 = -3.0e38

# Gemma 3 27B's d_ff is 21504 — above any shared-staging tier — so the GEMV kernels carry the
# same large-tier escape hatch `residentk.kernels._gemv_accum_kernel` grew for Qwen2.5-7B: above
# the cap the activation is read from GLOBAL memory (it stays L2-resident across the block's
# output rows) instead of staged in shared.
comptime _G3_STAGE_CAP: Int = 6144


def _g3_embed_row_kernel(
    hidden: _FP, embed: _FP, token_id_i64: Int64, d_model_i64: Int64, embed_scale: Float32
):
    """`hidden = embed[token_id] * embed_scale` — Gemma's scaled input-embedding gather.
    embed_scale is sqrt(hidden_size) (verified: Gemma3TextScaledWordEmbedding). The multiply is
    per-element on the ONE gathered row; the tied lm_head table this same buffer serves is read
    WITHOUT the scale by the argmax kernel (the scale is a forward-pass property of the input
    path only)."""
    var token_id = Int(token_id_i64)
    var d_model = Int(d_model_i64)
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        hidden[i] = embed[token_id * d_model + i] * embed_scale


def _g3_gemv_kernel(y: _FP, x: _FP, w: _FP, k_i64: Int64, n_i64: Int64):
    """`y = W @ x`, `W` held `[n, k]` row-major — a PLAIN GEMV with no residual add. Gemma 3's
    o_proj / down_proj outputs must be materialised because a norm is applied to them before the
    residual add (`_g3_norm_accum_kernel`), unlike llama's straight `+=`. Same one-SIMD-group-
    per-output-column shape and vectorized reduction as `residentk.kernels._gemv_accum_kernel`;
    activations wider than `_G3_STAGE_CAP` read from global memory (27B's d_ff = 21504)."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var xs = stack_allocation[_G3_STAGE_CAP, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var staged = k <= _G3_STAGE_CAP
    if staged:
        var s = tid
        while s < k:
            xs[s] = x[s]
            s += _TG
        barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE
        var t = lane * _VEC
        while t < k_vec:
            var wv = w.load[width=_VEC](base + t)
            var pv: SIMD[DType.float32, _VEC]
            if staged:
                var xv = xs.load[width=_VEC](t)
                pv = xv * wv
            else:
                var xv = x.load[width=_VEC](t)
                pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE
        var tt = k_vec + lane
        while tt < k:
            var xv = xs[tt] if staged else x[tt]
            acc += xv * w[base + tt]
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


def _g3_norm_accum_kernel(hidden: _FP, y: _FP, gamma: _FP, n_i64: Int64, eps: Float32):
    """`hidden += rmsnorm(y) * gamma` — Gemma 3's post-branch norm + residual add. One
    threadgroup walks the whole vector: sum-of-squares pass, then the scaled accumulate (n is
    d_model — 5376 at 27B — a single block's few dozen iterations against the GEMV it follows).
    gamma carries the rebased (1.0 + weight) gain."""
    var n = Int(n_i64)
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < n:
        var v = y[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(n) + eps)

    var t = tid
    while t < n:
        hidden[t] = hidden[t] + y[t] * inv * gamma[t]
        t += _TG


def _g3_norm_inplace_kernel(x: _FP, gamma: _FP, n_i64: Int64, eps: Float32):
    """`x = rmsnorm(x) * gamma` in place — the final norm before a dumped logits row. Same
    single-block shape as `_g3_norm_accum_kernel`."""
    var n = Int(n_i64)
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < n:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(n) + eps)

    var t = tid
    while t < n:
        x[t] = x[t] * inv * gamma[t]
        t += _TG


def _g3_norm_gemv2_geglu_kernel(
    act: _FP, x: _FP, gamma: _FP, w: _FP, k_i64: Int64, n_ff_i64: Int64, eps: Float32
):
    """`act = gelu_pytorch_tanh(W_gate @ xn) * (W_up @ xn)` with `xn = rmsnorm(x) * gamma` —
    the GeGLU twin of `residentk.kernels._norm_gemv2_swiglu_kernel` (identical norm + gate/up
    fusion; ONLY the epilogue differs). `w` is gate-then-up concatenated `[2*n_ff, k]`. gamma
    carries the rebased (1.0 + weight) gain of pre_feedforward_layernorm.

    gelu_pytorch_tanh is PyTorch's tanh approximation exactly:
        0.5 * g * (1 + tanh(sqrt(2/pi) * (g + 0.044715 * g^3)))
    """
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    var xs = stack_allocation[_G3_STAGE_CAP, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var k_vec = (k // _VEC_STRIDE) * _VEC_STRIDE

    # ── gate ────────────────────────────────────────────────────────────────────
    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * k
        var t = lane * _VEC
        while t < k_vec:
            var xv = xs.load[width=_VEC](t)
            var wv = w.load[width=_VEC](base + t)
            var pv = xv * wv
            acc += pv[0] + pv[1] + pv[2] + pv[3]
            t += _VEC_STRIDE
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * w[base + tt]
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0:
        gsh[sub] = red[sub * _LANES]
    barrier()

    # ── up ──────────────────────────────────────────────────────────────────────
    var acc2 = Float32(0.0)
    if j < n_ff:
        var base2 = (n_ff + j) * k
        var t2 = lane * _VEC
        while t2 < k_vec:
            var xv2 = xs.load[width=_VEC](t2)
            var wv2 = w.load[width=_VEC](base2 + t2)
            var pv2 = xv2 * wv2
            acc2 += pv2[0] + pv2[1] + pv2[2] + pv2[3]
            t2 += _VEC_STRIDE
        var tt2 = k_vec + lane
        while tt2 < k:
            acc2 += xs[tt2] * w[base2 + tt2]
            tt2 += _LANES
    red[tid] = acc2
    barrier()
    var st2 = _LANES // 2
    while st2 > 0:
        if lane < st2:
            red[tid] = red[tid] + red[tid + st2]
        barrier()
        st2 //= 2
    if lane == 0 and j < n_ff:
        var g = gsh[sub]
        var u = red[sub * _LANES]
        # gelu_pytorch_tanh: 0.5*g*(1 + tanh(sqrt(2/pi)*(g + 0.044715*g^3)))
        var inner = Float32(0.7978845608028654) * (g + Float32(0.044715) * g * g * g)
        act[j] = Float32(0.5) * g * (Float32(1.0) + tanh(inner)) * u


def _g3_sdpa_window_kernel(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    key_lo_i64: Int64, n_keys_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32,
):
    """Sliding-window decode attention: `_sdpa_kernel` with a key LOWER BOUND. One query token at
    the current position attends to cached keys `[key_lo, n_keys)`: full-attention layers pass
    key_lo = 0 (bit-identical to the original); Gemma 3's sliding layers pass
    `max(0, pos + 1 - sliding_window)` so a local layer sees exactly its window. The KV cache
    keeps every position (truncated-append semantics live in the READ range, not the layout —
    correctness over memory this round). Same online softmax, same GQA mapping, same no-mask
    causal argument (the window is the mask)."""
    var key_lo = Int(key_lo_i64)
    var n_keys = Int(n_keys_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var h = Int(block_idx.x)
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[h * d_head + e]

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_lo, n_keys):
        var kb = (j * h_kv + hk) * d_head
        red[e] = qv * ck[kb + e]
        barrier()
        var stride = d_head // 2
        while stride > 0:
            if e < stride:
                red[e] = red[e] + red[e + stride]
            barrier()
            stride //= 2
        var s = red[0] * scale
        barrier()

        var nm = m if m > s else s
        var corr = exp(m - nm)
        var w = exp(s - nm)
        o = o * corr + w * cv[kb + e]
        denom = denom * corr + w
        m = nm

    attn_out[h * d_head + e] = o / denom


# ── Float16-weight twins (the 27B race arm: f32 weights do not fit one 80 GB H100) ────────────
# Mixed-precision discipline identical to `residentk.kernels`' `_f16` family: ONLY the resident
# weight matrix `w` narrows to Float16; every activation, accumulator, norm gain, and the KV cache
# stays Float32. Each loaded weight element widens to Float32 immediately, before the multiply that
# consumes it, so the arithmetic is unchanged except the storage width.


def _g3_embed_row_kernel_f16(
    hidden: _FP, embed: _HP, token_id_i64: Int64, d_model_i64: Int64, embed_scale: Float32
):
    """The fp16-weight twin of `_g3_embed_row_kernel`: gather one embedding row (resident Float16),
    widen to Float32, multiply by sqrt(hidden_size)."""
    var token_id = Int(token_id_i64)
    var d_model = Int(d_model_i64)
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        hidden[i] = Float32(embed[token_id * d_model + i]) * embed_scale


def _g3_gemv_kernel_f16(y: _FP, x: _FP, w: _HP, k_i64: Int64, n_i64: Int64):
    """The fp16-weight twin of `_g3_gemv_kernel`: `y = W @ x` with `w` resident Float16, widened on
    load. o_proj / down_proj use this (their branch output is materialised, then normed + added)."""
    var k = Int(k_i64)
    var n = Int(n_i64)
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var xs = stack_allocation[_G3_STAGE_CAP, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var staged = k <= _G3_STAGE_CAP
    if staged:
        var s = tid
        while s < k:
            xs[s] = x[s]
            s += _TG
        barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var base = j * k
        var k_vec = (k // _VEC_STRIDE_H) * _VEC_STRIDE_H
        var t = lane * _VEC_H
        while t < k_vec:
            var wv = w.load[width=_VEC_H](base + t).cast[DType.float32]()
            var pv: SIMD[DType.float32, _VEC_H]
            if staged:
                var xv = xs.load[width=_VEC_H](t)
                pv = xv * wv
            else:
                var xv = x.load[width=_VEC_H](t)
                pv = xv * wv
            for lane_e in range(_VEC_H):
                acc += pv[lane_e]
            t += _VEC_STRIDE_H
        var tt = k_vec + lane
        while tt < k:
            var xv = xs[tt] if staged else x[tt]
            acc += xv * Float32(w[base + tt])
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = red[sub * _LANES]


def _g3_norm_gemv2_geglu_kernel_f16(
    act: _FP, x: _FP, gamma: _FP, w: _HP, k_i64: Int64, n_ff_i64: Int64, eps: Float32
):
    """The fp16-weight twin of `_g3_norm_gemv2_geglu_kernel`: pre-FFN norm + gate/up projections
    (resident Float16, widened on load) + GeGLU. Arithmetic identical to the Float32 kernel."""
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    var xs = stack_allocation[_G3_STAGE_CAP, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[i]
        ss += v * v
        i += _TG
    red[tid] = ss
    barrier()
    var stride = _TG // 2
    while stride > 0:
        if tid < stride:
            red[tid] = red[tid] + red[tid + stride]
        barrier()
        stride //= 2
    var inv = 1.0 / sqrt(red[0] / Float32(k) + eps)

    var s = tid
    while s < k:
        xs[s] = x[s] * inv * gamma[s]
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var k_vec = (k // _VEC_STRIDE_H) * _VEC_STRIDE_H

    # ── gate ──
    var acc = Float32(0.0)
    if j < n_ff:
        var base = j * k
        var t = lane * _VEC_H
        while t < k_vec:
            var xv = xs.load[width=_VEC_H](t)
            var wv = w.load[width=_VEC_H](base + t).cast[DType.float32]()
            var pv = xv * wv
            for lane_e in range(_VEC_H):
                acc += pv[lane_e]
            t += _VEC_STRIDE_H
        var tt = k_vec + lane
        while tt < k:
            acc += xs[tt] * Float32(w[base + tt])
            tt += _LANES
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0:
        gsh[sub] = red[sub * _LANES]
    barrier()

    # ── up ──
    var acc2 = Float32(0.0)
    if j < n_ff:
        var base2 = (n_ff + j) * k
        var t2 = lane * _VEC_H
        while t2 < k_vec:
            var xv2 = xs.load[width=_VEC_H](t2)
            var wv2 = w.load[width=_VEC_H](base2 + t2).cast[DType.float32]()
            var pv2 = xv2 * wv2
            for lane_e in range(_VEC_H):
                acc2 += pv2[lane_e]
            t2 += _VEC_STRIDE_H
        var tt2 = k_vec + lane
        while tt2 < k:
            acc2 += xs[tt2] * Float32(w[base2 + tt2])
            tt2 += _LANES
    red[tid] = acc2
    barrier()
    var st2 = _LANES // 2
    while st2 > 0:
        if lane < st2:
            red[tid] = red[tid] + red[tid + st2]
        barrier()
        st2 //= 2
    if lane == 0 and j < n_ff:
        var g = gsh[sub]
        var u = red[sub * _LANES]
        var inner = Float32(0.7978845608028654) * (g + Float32(0.044715) * g * g * g)
        act[j] = Float32(0.5) * g * (Float32(1.0) + tanh(inner)) * u


# ── CUDA-graph decode twins (the _g variants read dynamic scalars from the resident state buf) ──
# Same one-level-of-indirection pattern as residentk.kernels_cuda_graph: the captured graph's
# launch arguments stay fixed, and the session feeds token_id / pos / n_keys through `state`.


def _g3_embed_row_kernel_f16_g(
    hidden: _FP, embed: _HP, state: _I64P, d_model_i64: Int64, embed_scale: Float32
):
    """Graph-replay twin of `_g3_embed_row_kernel_f16`: `hidden = Float32(embed_f16[state[0]]) *
    embed_scale`. Body-identical save the token id's origin (state[0] instead of by-value)."""
    var token_id = Int(state[0])
    var d_model = Int(d_model_i64)
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < d_model:
        hidden[i] = Float32(embed[token_id * d_model + i]) * embed_scale


def _g3_splitk_partial_kernel_simd_g(
    m_out: _FP, l_out: _FP, o_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    state: _I64P, n_splits_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    scale: Float32, window_i64: Int64,
):
    """Graph-replay twin of the gemma3 WINDOWED split-K partial. Reads `n_keys` from `state[2]`;
    `window` is a capture-time per-layer constant (0 = full-history global layer, else the sliding
    window for a local layer). Splits `[key_lo, n_keys)` where `key_lo = max(0, n_keys - window)`,
    so a local layer attends only its last `window` keys even mid-graph. Same unnormalized
    (m, l, o) online-softmax contract as `residentk.kernels._splitk_partial_kernel_simd`; empty
    splits leave (m=_NEG_HUGE, l=0, o=0) and fold into the merge as no-ops.
    """
    var n_keys = Int(state[2])
    var n_splits = Int(n_splits_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var window = Int(window_i64)
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var idx = Int(block_idx.x)
    var h = idx // n_splits
    var sidx = idx % n_splits
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[h * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    # Sliding-window lower bound: full-history layers pass window=0 -> key_lo=0.
    var key_lo = 0
    if window > 0:
        key_lo = n_keys - window
        if key_lo < 0:
            key_lo = 0
    var span = n_keys - key_lo
    var key_start = key_lo + (span * sidx) // n_splits
    var key_end = key_lo + (span * (sidx + 1)) // n_splits

    var m = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_start, key_end):
        var kb = (j * h_kv + hk) * d_head
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
