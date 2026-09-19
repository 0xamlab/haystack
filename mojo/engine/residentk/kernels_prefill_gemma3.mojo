"""
residentk.kernels_prefill_gemma3 — the Gemma 3 family's TILED PREFILL kernels (Gemma 3 lane,
2026-08-24). Zero Python. ADDITIVE: nothing in `residentk.kernels`, `residentk.kernels_gemma3`,
or the v2 prefill GEMM family is touched — the Qwen3/llama arms stay byte-for-byte what they
were.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, float16
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/gemma3/ref_transformers_gemma3.py
benchmark: benchmarks/llm_smoke/nvidia_race/gemma3_correctness_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

Same private-name discipline as `residentk.kernels` (leading underscores keep every launch out
of the inventory/contract/dispatch; shader codegen only ever sees these through the static call
graph of a driver that imports them).

What already exists, reused VERBATIM by the gemma3 tiled prefill (no twin needed)
----------------------------------------------------------------------------------
* `_pf_rmsnorm_rows_kernel` (residentk.kernels) — batched RMSNorm over m rows; the rebased
  (1+w) gain is data, and Gemma 3's input_layernorm / pre_feedforward_layernorm sit exactly
  where llama's input_layernorm does (on the residual stream, pre-projection).
* `_pf_ropewrt_kernel` (residentk.kernels) — batched q_norm + k_norm + RoPE + in-place KV-cache
  write, qk_norm=1; the SESSION selects the per-layer rope-table pointer (global vs local
  theta), which is how Gemma 3's dual rope lands with no kernel change — exactly the same
  pointer-selection the decode path already uses.
* `_pf_gemm_assign_kernel_v2` / `_pf_gemm_accum_kernel_v2` (residentk.kernels_prefill_f32_v2)
  — family-agnostic register-blocked tiled GEMMs (`y = x @ W^T`, `w` resident [n,k]); the f32
  gemma3 session dispatches them for the fused QKV projection (ASSIGN) and, for o/down, into a
  BRANCH scratch (ASSIGN again — Gemma's post-branch norm forbids the llama-style residual
  accumulate).

What is NEW here, and why
-------------------------
* `_pf_gemm_geglu_kernel_v2` / `_pf_gemm_geglu_kernel_v2h` — the GeGLU prefill epilogue:
  `_pf_gemm_swiglu_kernel_v2`'s exact register-blocked / double-buffered structure with the
  epilogue swapped to gelu_pytorch_tanh (`0.5*g*(1 + tanh(sqrt(2/pi)*(g + 0.044715*g^3))) * u`,
  the SAME expression `_g3_norm_gemv2_geglu_kernel` fuses for decode).
* `_pf_gemm_assign_kernel_v2h` / `_pf_gemm_accum_kernel_v2h` — the f16-RESIDENT-WEIGHT twins of
  the v2 family (the 27B race arm holds its projections in Float16 — f32 does not fit one 80 GB
  H100). Geometry, double buffering, register block and accumulation ORDER are the v2 family's
  verbatim; only the B-tile cooperative load differs: width-4 Float16 global loads widened to
  Float32 before staging into the shared tile. Activations, shared tiles, and accumulators stay
  Float32 — the eager decode arm's exact arithmetic, at half the weight-storage bytes.
* `_pf_attn_window_kernel` — windowed CAUSAL prefill attention: `_pf_attn_tiled_kernel_simd`
  with a per-row key lower bound. Row `m` (absolute position `pos_base + m`) attends keys
  `[key_lo, pos_base + m + 1)` where `key_lo = 0` for full-attention layers and
  `max(0, pos_base + m + 1 - window)` for Gemma 3's sliding layers — the batched twin of the
  decode bound `_g3_sdpa_window_kernel` applies (the window is the mask; causal by construction).
* `_pf_norm_accum_rows_kernel` — the row-batched twin of `_g3_norm_accum_kernel`:
  `hidden[row] += rmsnorm(y[row]) * gamma` per row. This is the four-norm wiring the family
  needs twice per layer (o_proj and down_proj branch outputs are normed BEFORE the residual
  add).
* `_pf_embed_rows_g3_kernel` (+ `_f16`) — the m-row embedding gather MULTIPLIED BY
  sqrt(hidden_size) (Gemma's Gemma3TextScaledWordEmbedding; the tied lm_head stays unscaled).
* `_pf_geglu_rows_kernel` — the row-elementwise GeGLU combine for the TC escape-hatch path
  (cuBLAS GemmEx writes the [m, 2*d_ff] gate/up result; this kernel applies the SAME
  gelu_pytorch_tanh(gate) * up expression the fused kernel does). The twin of the TC seam's
  `_pf_swiglu_rows_kernel`.
* `_pf_row_copy_kernel` — one row of a [m, n] device buffer into a flat buffer (the prefill's
  final residual row into the decode `hidden` so `dump_logits` and the decode `step` chain see
  the same state the serial-ingest path leaves).
"""

from std.origin import MutAnyOrigin
from std.gpu import block_idx, block_dim, thread_idx, lane_id, warp_id, WARP_SIZE
from max.gpu import barrier
from max.gpu.memory import AddressSpace
from std.math import exp, sqrt, tanh
from std.memory import stack_allocation
from std.gpu.primitives.warp import shuffle_xor as _shuffle_xor, sum as _warp_sum
from residentk.contract import RESIDENT_MAX_HEAD_DIM
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BN,
    _G2_BK,
    _G2_TM,
    _G2_TN,
    _G2_APAD,
    _G2_BPAD,
)
from residentk.loadvec import L0_ALIGN, _ld4, _st4

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
alias _HP = UnsafePointer[Float16, origin=MutAnyOrigin]
alias _IP = UnsafePointer[Int32, origin=MutAnyOrigin]

comptime _TG: Int = 256
comptime _LANES: Int = 32
comptime _SUBS: Int = _TG // _LANES
comptime _NEG_HUGE: Float32 = -3.0e38

comptime _G3_GEGLUV_VEC: Int = 8
"""ROUND 18: f16 elements ONE THREAD owns in `_pf_geglu_rows_f16_vec_kernel`
(`-D ALGENTA_G3_PF_GEGLU_V2`). 8 x Float16 = 16 bytes = `ld.global.v4.b32` /
`st.global.v4.b32`, the widest single global access the ISA has, so one instruction per operand
replaces the scalar twin's eight 2-byte accesses. This is the f16 analogue of `_VEC`/`_VEC_H` in
`residentk.kernels`; `_VEC_H = 4` there is a METAL finding (half4 is a real MSL type) and does not
carry over — on CUDA the transaction is 16 bytes wide regardless of element type."""


@always_inline
def _ld8h(p: _HP, off: Int) -> SIMD[DType.float16, _G3_GEGLUV_VEC]:
    """A 16-byte global Float16 load at ELEMENT offset `off`, which MUST be a multiple of
    `_G3_GEGLUV_VEC` at every call site. The f16 twin of `residentk.loadvec._ld4`: with
    `L0_ALIGN` it carries the `alignment=16` annotation that lets the backend emit ONE
    `ld.global.v4.b32` instead of eight scalar `ld.global.u16`, which is the defect the
    micro-autopsy root-caused for f32 and which `_pf_geglu_rows_f16_kernel` still has — every
    kernel-pointer parameter lowers `.param .u64 .ptr .align 1`, so no alignment survives to PTX
    unless the load site states it.

    MATH IS BIT-IDENTICAL: this changes only the load INSTRUCTION WIDTH, not the loaded bytes."""
    @parameter
    if L0_ALIGN:
        return p.load[width=_G3_GEGLUV_VEC, alignment=16](off)
    else:
        return p.load[width=_G3_GEGLUV_VEC](off)


@always_inline
def _st8h(p: _HP, off: Int, v: SIMD[DType.float16, _G3_GEGLUV_VEC]):
    """The STORE twin of `_ld8h` — a 16-byte global Float16 store at element offset `off`, which
    MUST be a multiple of `_G3_GEGLUV_VEC` at every call site. Same reasoning as `loadvec._st4`:
    vectorising the loads and then writing back eight scalar `st.global.u16` would leave half the
    issue-slot pressure in place. MATH IS BIT-IDENTICAL: instruction width only."""
    @parameter
    if L0_ALIGN:
        p.store[width=_G3_GEGLUV_VEC, alignment=16](off, v)
    else:
        p.store[width=_G3_GEGLUV_VEC](off, v)


@always_inline
def _g3_geglu_f16_elem(g: Float16, u: Float16) -> Float16:
    """ONE GeGLU element, f16 in / f16 out. This is `_pf_geglu_rows_f16_kernel`'s body
    TRANSPOSED VERBATIM — same constants, same f32 intermediate arithmetic, same operation order
    (`inner = c0 * (g + c1*g*g*g)`, then `0.5*g*(1+tanh(inner))*u`), same single f16 rounding at
    the end — so the vector kernel that calls it eight times is BIT-IDENTICAL to the scalar twin
    per element. Nothing is re-associated, because there is nothing to re-associate: GeGLU is
    purely elementwise, with no reduction across elements. That is exactly why this lever can
    promise bit-identity where ROPEVEC could not (ROPEVEC moved the qk_norm reduction's
    association; there is no reduction here).

    Kept as its own `@always_inline` function rather than inlined at the eight call sites so the
    transcription is in ONE place and a future reader diffs one body against one body."""
    var gf = Float32(g)
    var uf = Float32(u)
    var inner = Float32(0.7978845608028654) * (gf + Float32(0.044715) * gf * gf * gf)
    return Float16(Float32(0.5) * gf * (Float32(1.0) + tanh(inner)) * uf)


comptime G3_PF_TILE: Int = 1024
"""Largest m_rows tile one gemma3 prefill chunk processes. 1024 puts both raced sonnet shapes
(256 and 550 tokens) in ONE pass (one M-parallel grid per projection per layer — the H100
autopsy's wave-quantization finding: 128-row chunks pin occupancy and re-read the weights per
tile), while staying inside the scratch budget the sessions allocate (~0.5 GB at 27B's shapes).
Prompts longer than the tile run ceil(len/tile) passes; the KV-cache addressing is absolute, so
passes compose exactly the way the decode path's steps do."""


def _pf_embed_rows_g3_kernel(
    hidden: _FP, embed: _FP, token_ids: _IP, d_model_i64: Int64, m_rows_i64: Int64,
    embed_scale: Float32,
):
    """`hidden[m, :] = embed[token_ids[m], :] * embed_scale` for `m_rows` rows in ONE dispatch —
    `_pf_embed_rows_kernel` with Gemma's sqrt(hidden_size) input-embedding scale (the scale is a
    forward-pass property of the INPUT path; the tied lm_head reads the raw table). Grid/block
    flattening is the prefill family's own (`unit = block_idx.x % n_units`, `m = block_idx.x //
    n_units`)."""
    var d_model = Int(d_model_i64)
    var m_rows = Int(m_rows_i64)
    var n_units = (d_model + _TG - 1) // _TG
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var i = unit * _TG + Int(thread_idx.x)
    if i < d_model:
        var token_id = Int(token_ids[m])
        hidden[m * d_model + i] = embed[token_id * d_model + i] * embed_scale


def _pf_embed_rows_g3_kernel_f16(
    hidden: _FP, embed: _HP, token_ids: _IP, d_model_i64: Int64, m_rows_i64: Int64,
    embed_scale: Float32,
):
    """The fp16-table twin of `_pf_embed_rows_g3_kernel` (the 27B race arm's table is resident
    Float16; widen on load, then scale)."""
    var d_model = Int(d_model_i64)
    var m_rows = Int(m_rows_i64)
    var n_units = (d_model + _TG - 1) // _TG
    var unit = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var i = unit * _TG + Int(thread_idx.x)
    if i < d_model:
        var token_id = Int(token_ids[m])
        hidden[m * d_model + i] = Float32(embed[token_id * d_model + i]) * embed_scale


def _pf_norm_accum_rows_kernel(
    hidden: _FP, y: _FP, gamma: _FP, n_i64: Int64, eps: Float32, m_rows_i64: Int64
):
    """`hidden[m, :] += rmsnorm(y[m, :]) * gamma` for every one of `m_rows` rows — the batched
    twin of `_g3_norm_accum_kernel` (Gemma 3's post-branch norm + residual add, needed twice per
    layer: post_attention_layernorm on the o_proj output, post_feedforward_layernorm on the
    down_proj output). `grid_dim = m_rows`, `block_dim = _TG`; the sum-of-squares reduction is
    `_pf_rmsnorm_rows_kernel`'s own (warp-sum per SIMD-group + one combining barrier), and gamma
    carries the converter's rebased (1.0 + weight) gain."""
    var n = Int(n_i64)
    var m_rows = Int(m_rows_i64)
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var m = Int(block_idx.x)
    if m >= m_rows:
        return
    var row = m * n
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var ss = Float32(0.0)
    var i = tid
    while i < n:
        var v = y[row + i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(n) + eps)

    var t = tid
    while t < n:
        hidden[row + t] = hidden[row + t] + y[row + t] * inv * gamma[t]
        t += _TG


def _pf_attn_window_kernel(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    window_i64: Int64, is_global_i64: Int64, scale: Float32, m_rows_i64: Int64,
):
    """Windowed causal prefill attention — `_pf_attn_tiled_kernel_simd` with a per-row key LOWER
    BOUND. `grid_dim = h_q * m_rows` (`h = block_idx.x % h_q`, `m = block_idx.x // h_q`),
    `block_dim = d_head`, IDENTICAL per-key online-softmax math and IDENTICAL two-level SIMD-
    shuffle reduction. Row `m` is query position `pos_base + m`, causal by construction
    (`n_keys = pos_base + m + 1`), and — for a sliding layer (`is_global = 0`) — starts at
    `key_lo = max(0, n_keys - window)`: Gemma 3's local layers attend only their last
    `sliding_window` keys. Full layers (`is_global = 1`) pass key_lo = 0 and are the tiled
    kernel exactly. The KV slots `[pos_base, pos_base + m_rows)` were written by the batched
    ropewrt dispatch immediately before this one, so row `m`'s loop — which stops at row `m`'s
    own slot — never reaches a later row's key."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var window = Int(window_i64)
    var is_global = Int(is_global_i64)
    var m_rows = Int(m_rows_i64)
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var n_q = h_q * d_head
    var h = Int(block_idx.x) % h_q
    var m = Int(block_idx.x) // h_q
    if m >= m_rows:
        return
    var n_keys = pos_base + m + 1
    var key_lo = 0
    if is_global != 1:
        key_lo = n_keys - window
        if key_lo < 0:
            key_lo = 0
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[m * n_q + h * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    var mx = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_lo, n_keys):
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

        var nm = mx if mx > s else s
        var corr = exp(mx - nm)
        var w = exp(s - nm)
        o = o * corr + w * cv[kb + e]
        denom = denom * corr + w
        mx = nm

    attn_out[m * n_q + h * d_head + e] = o / denom


def _pf_geglu_rows_kernel(act: _FP, gu: _FP, total_i64: Int64, n_ff_i64: Int64):
    """`act[row, j] = gelu_pytorch_tanh(gu[row, j]) * gu[row, n_ff + j]` over `m * n_ff`
    outputs — the TC seam's GeGLU epilogue (gate columns `0 .. n_ff`, up columns
    `n_ff .. 2*n_ff`, the concatenation order the resident `[2*d_ff, d_model]` gate/up table
    guarantees). The SAME gelu_pytorch_tanh expression `_g3_norm_gemv2_geglu_kernel` applies
    in-kernel for decode, elementwise-exact against whatever the GEMM produced. Twin of the TC
    seam's `_pf_swiglu_rows_kernel`. Grid: `ceil(m * n_ff / _TG)`, block `_TG`."""
    var total = Int(total_i64)
    var n_ff = Int(n_ff_i64)
    var i = Int(block_idx.x) * Int(block_dim.x) + Int(thread_idx.x)
    if i < total:
        var row = i // n_ff
        var j = i - row * n_ff
        var g = gu[row * 2 * n_ff + j]
        var u = gu[row * 2 * n_ff + n_ff + j]
        var inner = Float32(0.7978845608028654) * (g + Float32(0.044715) * g * g * g)
        act[i] = Float32(0.5) * g * (Float32(1.0) + tanh(inner)) * u


def _pf_geglu_rows_f16_kernel(act16: _HP, gu16: _HP, total_i64: Int64, n_ff_i64: Int64):
    """`_pf_geglu_rows_kernel` with BOTH operands f16 — the GeGLU half of the A-convert
    elimination (`-D ALGENTA_G3_PF_F16MLP`, the gemma-3 twin of the 7B lane's
    `_pf_swiglu_rows_f16_kernel`): the gate/up GEMM writes its `[m, 2*d_ff]` result as f16 C
    (`_tc_gemm_f16_16c_pre`) and this combine reads that f16 and writes the f16 A the
    down_proj GEMM consumes directly (`_tc_gemm_f16_32c_pre`), so neither the widest activation
    tensor in the layer nor the down A round-trips f32 and neither needs a shim convert pass.

    The gelu_pytorch_tanh expression is the f32 twin's VERBATIM — same constants, same
    operation order, same f32 intermediate arithmetic — and the output rounds to f16 once at
    the store, which is exactly the rounding the shim's `_f32_to_f16_kernel` would have applied
    to the same f32 value one launch later. So the down_proj A is bit-identical to the f32
    chain's; the ONLY numeric difference this lever introduces is upstream of it, where the
    gate/up C rounds to f16 at the GEMM epilogue instead of after it. That is why the lever
    carries its own build flag and its own token-identity gate.

    Grid: `ceil(m * n_ff / _TG)`, block `_TG`."""
    var total = Int(total_i64)
    var n_ff = Int(n_ff_i64)
    var i = Int(block_idx.x) * Int(block_dim.x) + Int(thread_idx.x)
    if i < total:
        var row = i // n_ff
        var j = i - row * n_ff
        var g = Float32(gu16[row * 2 * n_ff + j])
        var u = Float32(gu16[row * 2 * n_ff + n_ff + j])
        var inner = Float32(0.7978845608028654) * (g + Float32(0.044715) * g * g * g)
        act16[i] = Float16(Float32(0.5) * g * (Float32(1.0) + tanh(inner)) * u)


def _pf_geglu_rows_f16_vec_kernel(act16: _HP, gu16: _HP, total_i64: Int64, n_ff_i64: Int64):
    """`_pf_geglu_rows_f16_kernel` with the scalar 2-byte accesses replaced by 16-byte
    `_ld8h`/`_st8h` — `-D ALGENTA_G3_PF_GEGLU_V2`, ROUND 18's lever #1.

    WHY THIS KERNEL AND NOT ANOTHER. Round 15's exactly-attributed bucket census put this kernel
    at **45.687 ms / 434 instances / 8.22% of `--from-first-attn` region busy** — larger than the
    entire fused-attention bucket (38.114 ms) and never examined by any round before it. Round 17
    priced it: its traffic is 6 bytes per output element (f16 gate read + f16 up read + f16
    activation write), no re-reads, so over the region's 365056 rows x 21504 elements it moves
    **47.101 GB**, whose roof at the campaign's own 4.8 TB/s HBM3e constant is **9.813 ms**. It
    measures 4.656x that, i.e. it achieves **1.031 TB/s = 21.5% of roof**. And it is not compute:
    the 70.65 GFLOP of elementwise math prices at 0.0714 ms (0.156% of measured) at the 1410
    MHz-pinned 989 TF/s, and even charging every one of the 7.850 G `tanh` calls to the SFU at
    16/SM/clk x 132 SM x 1.41 GHz leaves 2.636 ms = 5.8%. **The 4.66x gap to roof is an
    access-pattern problem, and the source says which one:** one thread per element, three 2-byte
    global accesses each. `-D ALGENTA_G3_GEGLU_U4` is in the shipped default's flag stack but
    vectorises the DECODE GEMV (`_g3_norm_gemv2_geglu_kernel_f16_u4`, `grid = ceil(d_ff/_SUBS)`);
    the prefill f16 GeGLU had **no vectorised twin at all**.

    THE PRECEDENT IS IN-LANE AND MEASURED. ROPEVEC (`-D ALGENTA_G3_PF_ROPEVEC`, round 13, now
    default ON) made exactly this change to the RoPE family — scalar 4-byte accesses to
    `_ld4`/`_st4` 16-byte quads — and delivered **-1.687 ms on rag4096 at 14.5x its bracket drift
    armor**. That was against a 6.680 ms pool. This one is 45.687 ms at 21.5% of roof, so the
    same mechanism is being applied to a pool 6.8x larger and 4.4x further from its roof.

    WHAT CHANGES. Thread `t` of block `b` owns the EIGHT CONTIGUOUS elements
    `g8 = b * (_TG * _G3_GEGLUV_VEC) + t * _G3_GEGLUV_VEC`, so:

        per 8 output elements, scalar twin   ->  this kernel
        global loads   16 x ld.global.u16    ->  2  x ld.global.v4.b32
        global stores   8 x st.global.u16    ->  1  x st.global.v4.b32
        memory instrs  24                   ->  3        (8x fewer)
        threads       8                     ->  1
        grid blocks   ceil(total/256)       ->  ceil(total/2048)   (8x fewer launches)
        cross-lane     none                 ->  none
        arithmetic     8 elements' worth    ->  the same 8 elements' worth, unchanged

    A warp of 32 lanes now covers 256 contiguous f16 = 512 bytes per instruction, which is four
    fully-coalesced 128-byte sectors — the scalar twin's warp covered 64 bytes and wasted three
    quarters of every sector it touched.

    **BIT-IDENTICAL BY CONSTRUCTION, and this is the strongest correctness claim in the file.**
    GeGLU is purely ELEMENTWISE: there is no reduction, no accumulation and no cross-element
    data movement anywhere in it, so there is no association order to change. Each of the eight
    lanes is computed by `_g3_geglu_f16_elem`, which is the scalar twin's body transposed
    VERBATIM — the same two constants `0.7978845608028654` / `0.044715`, the same f32 widening of
    both operands, the same `inner = c0 * (g + c1*g*g*g)` order, the same
    `0.5*g*(1+tanh(inner))*u` order, the same single f16 rounding at the store. The SIMD lanes do
    not interact. So the output tensor is bit-for-bit the scalar twin's, element for element, at
    every m. Contrast ROPEVEC, which had to re-associate the qk_norm sum-of-squares and is
    therefore certified by the fp32 oracle rather than claimed exact. **This lever is still put
    through the same G0/G1 oracle gates with a bit-identical repeat, because a claim of
    bit-identity is a hypothesis until the gate says so** — but unlike ROPEVEC and LTALGO the
    expected result is EXACT equality with the control arm, not merely oracle agreement.

    STRUCTURAL CONTRACT, discharged at the dispatch site (which keeps the scalar twin for any
    shape that does not meet it, so no build can reach this kernel with a ragged tail):
      * `n_ff % _G3_GEGLUV_VEC == 0`. gemma-3-27b's `d_ff = 21504 = 8 x 2688`, so this holds;
        it is what makes `total = m * n_ff` a multiple of 8 too, so the group guard `g8 < total`
        is exact and NO thread can read or write past either buffer.
      * 16-BYTE ALIGNMENT of all three access streams. Both buffers are `DeviceBuffer` bases,
        which `align_check_probe.mojo` PROVED 256-byte aligned on the A100 (a superset of 16);
        the gate/up element offset is `row * 2*n_ff + j` with `j` a multiple of 8 and `2*n_ff`
        therefore a multiple of 16, and the up half adds `n_ff` which is itself a multiple of 8 —
        so gate, up and activation offsets are all multiples of 8 elements = 16 bytes. That is
        the same promise `loadvec` exists to make, restated for f16 and for this layout.

    Grid `ceil(m * n_ff / (_TG * _G3_GEGLUV_VEC))`, block `_TG` — the scalar twin's grid divided
    by `_G3_GEGLUV_VEC`, with the same `_TG` block so occupancy per SM is unchanged."""
    var total = Int(total_i64)
    var n_ff = Int(n_ff_i64)
    # The element index of this thread's FIRST owned element. Multiples of _G3_GEGLUV_VEC by
    # construction, which is what discharges both halves of the alignment contract above.
    var g8 = (Int(block_idx.x) * _TG + Int(thread_idx.x)) * _G3_GEGLUV_VEC
    if g8 < total:
        var row = g8 // n_ff
        var j = g8 - row * n_ff
        var base = row * 2 * n_ff + j
        var gv = _ld8h(gu16, base)          # gate columns j .. j+7
        var uv = _ld8h(gu16, base + n_ff)   # their up partners, n_ff + j .. n_ff + j+7
        _st8h(
            act16,
            g8,
            SIMD[DType.float16, _G3_GEGLUV_VEC](
                _g3_geglu_f16_elem(gv[0], uv[0]),
                _g3_geglu_f16_elem(gv[1], uv[1]),
                _g3_geglu_f16_elem(gv[2], uv[2]),
                _g3_geglu_f16_elem(gv[3], uv[3]),
                _g3_geglu_f16_elem(gv[4], uv[4]),
                _g3_geglu_f16_elem(gv[5], uv[5]),
                _g3_geglu_f16_elem(gv[6], uv[6]),
                _g3_geglu_f16_elem(gv[7], uv[7]),
            ),
        )


comptime _G3_ROPE_WARPS_PER_BLOCK: Int = 8
comptime _G3_ROPE_NTHREADS: Int = _G3_ROPE_WARPS_PER_BLOCK * WARP_SIZE


def _pf_ropewrt_warps_kernel(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64,
    d_head_i64: Int64, eps: Float32, m_rows_i64: Int64, qk_norm_i64: Int64,
    blocks_per_row_i64: Int64,
):
    """`residentk.kernels._pf_ropewrt_kernel` with ONE WARP PER HEAD instead of one BLOCK per
    head — `-D ALGENTA_G3_PF_ROPE2`, and BIT-IDENTICAL to it (proof below).

    WHY. The twin it replaces launches `(h_q + h_kv) * m_rows` blocks of `d_head` threads, so at
    gemma-3-27b's shapes (h_q=32, h_kv=16, d_head=128) one 1024-row tile is 49,152 blocks of 128
    threads in which every thread owns ONE element, and the q_norm/k_norm sum-of-squares is a
    seven-step SHARED-MEMORY tree with a `barrier()` at every step. That is 344,064 block-wide
    barriers per layer per tile to move 67 MB — at RAG-4096 (4 tiles x 62 layers) 12.2 million
    block launches, and round 4's decomposition put this bucket 25.355 ms behind TensorRT-LLM's
    single `applyBiasRopeUpdateKVCacheV2`. The kernel is barrier- and launch-bound, not
    bandwidth-bound.

    Here one WARP owns one head: 32 lanes x 4 elements = d_head, so a 256-thread block covers 8
    heads and a 1024-row tile is 6 x 1024 = 6,144 blocks — 8x fewer launches — with ZERO
    `barrier()` calls and ZERO shared memory, because the reduction is five `shuffle_xor` steps.
    Lane `t` owns elements {t, t+32, t+64, t+96} (stride WARP_SIZE, not contiguous), which keeps
    every load and store a fully coalesced 128-byte warp transaction AND puts each RoPE pair
    (e, e + d_head/2) inside one lane — and that is what makes the reduction tree reproducible.

    BIT-IDENTICAL, by construction. The twin's tree is `red[e] = v[e]^2` for e < d_head, then
    `red[i] += red[i + stride]` for stride = 64, 32, 16, 8, 4, 2, 1. Unrolled for lane t:
      stride 64: red[t] = v[t]^2 + v[t+64]^2 ; red[t+32] = v[t+32]^2 + v[t+96]^2   (intra-lane)
      stride 32: red[t] = (v[t]^2 + v[t+64]^2) + (v[t+32]^2 + v[t+96]^2)           (intra-lane)
      stride 16..1: red[i] += red[i + stride]                                       (cross-lane)
    so the first two steps happen inside one lane's registers in the written order and the last
    five are `shuffle_xor(16)`, `(8)`, `(4)`, `(2)`, `(1)` — the same operand pairs in the same
    association. The lanes the twin leaves stale (i >= stride) carry the same value by f32
    addition's commutativity, and every lane ends with the total the twin reads out of `red[0]`.
    `inv = 1 / sqrt(total / d_head + eps)`, `x = v * inv * g` and the rotation
    `o0 = a0*c - a1*s`, `o1 = a0*s + a1*c` are the twin's expressions verbatim, so every stored
    byte is the same f32 bit pattern.

    STRUCTURAL CONTRACT: `d_head == 4 * WARP_SIZE` (128), which is also what makes
    `n_pairs == d_head/2 == 2 * WARP_SIZE` put both halves of a pair in one lane. The dispatch
    site gates on that fact and keeps the twin for any other head width; `blocks_per_row` is
    `ceil((h_q + h_kv) / _G3_ROPE_WARPS_PER_BLOCK)` and warps past `h_q + h_kv` return.
    Grid `m_rows * blocks_per_row`, block `_G3_ROPE_NTHREADS`."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var m_rows = Int(m_rows_i64)
    var qk_norm = Int(qk_norm_i64)
    var bpr = Int(blocks_per_row_i64)
    var n_units = h_q + h_kv

    var m = Int(block_idx.x) // bpr
    if m >= m_rows:
        return
    var sub = Int(block_idx.x) - m * bpr
    var b = sub * _G3_ROPE_WARPS_PER_BLOCK + Int(warp_id())
    if b >= n_units:
        return
    var t = Int(lane_id())
    var pos = pos_base + m
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = m * n_qkv
    var is_q = b < h_q
    var head = b if is_q else b - h_q

    var w1 = WARP_SIZE
    var w2 = 2 * WARP_SIZE
    var w3 = 3 * WARP_SIZE
    var src = row_qkv + (head * d_head if is_q else (h_q + head) * d_head)
    var v0 = qkv[src + t]
    var v1 = qkv[src + t + w1]
    var v2 = qkv[src + t + w2]
    var v3 = qkv[src + t + w3]

    var x0 = v0
    var x1 = v1
    var x2 = v2
    var x3 = v3
    if qk_norm == 1:
        # the twin's stride-64 then stride-32 steps, intra-lane, in its exact association
        var ss = (v0 * v0 + v2 * v2) + (v1 * v1 + v3 * v3)
        ss = ss + _shuffle_xor(ss, 16)
        ss = ss + _shuffle_xor(ss, 8)
        ss = ss + _shuffle_xor(ss, 4)
        ss = ss + _shuffle_xor(ss, 2)
        ss = ss + _shuffle_xor(ss, 1)
        var inv = 1.0 / sqrt(ss / Float32(d_head) + eps)
        if is_q:
            x0 = v0 * inv * qn_w[t]
            x1 = v1 * inv * qn_w[t + w1]
            x2 = v2 * inv * qn_w[t + w2]
            x3 = v3 * inv * qn_w[t + w3]
        else:
            x0 = v0 * inv * kn_w[t]
            x1 = v1 * inv * kn_w[t + w1]
            x2 = v2 * inv * kn_w[t + w2]
            x3 = v3 * inv * kn_w[t + w3]

    var n_pairs = d_head // 2
    var cb = pos * n_pairs
    var c0 = cos_t[cb + t]
    var s0 = sin_t[cb + t]
    var c1 = cos_t[cb + t + w1]
    var s1 = sin_t[cb + t + w1]
    # pair (t, t + n_pairs) is (x0, x2) and pair (t + w1, t + w1 + n_pairs) is (x1, x3), because
    # n_pairs == 2 * WARP_SIZE at d_head == 4 * WARP_SIZE
    var o0 = x0 * c0 - x2 * s0
    var o1 = x0 * s0 + x2 * c0
    var o2 = x1 * c1 - x3 * s1
    var o3 = x1 * s1 + x3 * c1

    if is_q:
        var qb = m * h_q * d_head + head * d_head
        q_rot[qb + t] = o0
        q_rot[qb + t + w1] = o2
        q_rot[qb + t + w2] = o1
        q_rot[qb + t + w3] = o3
    else:
        var kb = (pos * h_kv + head) * d_head
        ck[kb + t] = o0
        ck[kb + t + w1] = o2
        ck[kb + t + w2] = o1
        ck[kb + t + w3] = o3
        # V is neither normalized nor rotated: the twin copies it straight through and so does
        # this. Its slice starts after the h_q + h_kv Q and K slices of the fused qkv row.
        var vsrc = row_qkv + (h_q + h_kv + head) * d_head
        cv[kb + t] = qkv[vsrc + t]
        cv[kb + t + w1] = qkv[vsrc + t + w1]
        cv[kb + t + w2] = qkv[vsrc + t + w2]
        cv[kb + t + w3] = qkv[vsrc + t + w3]


comptime _G3_ROPEV_HEADS_PER_WARP: Int = 2
"""Heads per warp in `_pf_ropewrt_warps_vec_kernel`: one HALF-warp (16 lanes) per head, so a
lane's two float4 groups are `e0` and `e0 + d_head/2` and both halves of every RoPE pair stay
inside one lane. That is what keeps the kernel free of cross-lane data movement despite the
contiguous-per-lane access pattern."""

comptime _G3_ROPEV_HEADS_PER_BLOCK: Int = (
    _G3_ROPEV_HEADS_PER_WARP * _G3_ROPE_WARPS_PER_BLOCK
)
"""Heads per block: 8 warps x 2 = 16, so gemma-3-27b's h_q + h_kv = 48 units take 3 blocks per
row instead of the warps kernel's 6 — half the launches again."""


def _pf_ropewrt_warps_vec_kernel(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64,
    d_head_i64: Int64, eps: Float32, m_rows_i64: Int64, qk_norm_i64: Int64,
    blocks_per_row_i64: Int64,
):
    """`_pf_ropewrt_warps_kernel` with the scalar 4-byte global accesses replaced by 16-byte
    `_ld4`/`_st4` — `-D ALGENTA_G3_PF_ROPEVEC`, round 7's compensation lever.

    WHY, AND WHY IT IS NOT ALREADY DONE. `_pf_biasropewrt_vec_kernel` (FRONT 5 lever 2,
    `-D ALGENTA_7B_PF_ROPEVEC`) already made exactly this change for the 7B lane and measured
    the family at ~43% of the traffic roof before it, but it DECLINES whenever `qk_norm != 0`
    because there the norm's sum-of-squares reduction needs every element of the head reachable
    from one thread. Gemma 3 always has QK-norm (this session's dispatch passes a literal 1),
    so the 7B vector kernel never runs here and gemma-3 kept the scalar accesses. Round 6's own
    decomposition is the same signature on this model: the rope bucket is ~6.2 ms measured
    against a 3.39 ms traffic roof (56 KB/row x 1024 rows x 62 layers x 4 tiles = 14.56 GB at
    4.8 TB/s), i.e. ~49% of roof, while TensorRT-LLM's `applyBiasRopeUpdateKVCacheV2` sits at
    3.47 ms — essentially AT that roof. So ~2.7 ms of this bucket is not bandwidth, it is the
    kernel's own instruction shape.

    WHAT CHANGES. The warps kernel gives lane `t` the four STRIDED elements {t, t+32, t+64,
    t+96}: four separate coalesced 128-byte warp transactions per array, and four scalar
    `ld.global.b32` per lane, because without the `alignment=16` annotation that `loadvec`
    exists to supply, `load[width=4]` lowers to four scalar loads rather than one
    `ld.global.v4.b32`. Here a HALF-warp owns one head and lane `q = t & 15` takes the two
    CONTIGUOUS quads `e0 = 4q` and `e0 + d_head/2`, so every access is one `_ld4`/`_st4`:

        per head, scalar warps kernel      ->  this kernel
        qkv loads        4                 ->  2   (both RoPE halves)
        norm-weight      4                 ->  2
        cos, sin         2 + 2             ->  1 + 1
        q_rot/ck stores  4                 ->  2
        V copy (K heads) 4 loads + 4 stores->  1 + 1 each
        -----------------------------------------------
        memory instrs   ~24                ->  ~8      (3x fewer)
        cross-lane       5 shuffle_xor     ->  4 shuffle_xor (norm only)

    Because a lane holds BOTH halves of its four pairs, the rotation needs NO cross-lane data
    movement at all — the only shuffles left are the norm reduction's, and there are fewer of
    them (4 over a half-warp instead of 5 over a full warp). Launches also drop again: 16 heads
    per block instead of 8, so gemma-3-27b's 48 units take 3 blocks per row rather than 6.

    NOT BIT-IDENTICAL, AND WHY THAT IS THE RIGHT CALL. Keeping the strided lane mapping is what
    made the warps kernel bit-exact against its block-per-head twin: it put both halves of a
    pair in one lane AND made the twin's stride-64/stride-32 reduction steps intra-lane, so the
    five `shuffle_xor` steps reproduced the twin's tree exactly. Contiguous quads cannot do
    that — the qk_norm sum-of-squares now associates eight intra-lane terms then four
    half-warp shuffles instead of four intra-lane terms then five full-warp shuffles, so the
    f32 rounding of `ss` differs and `inv` differs in the last bits. The rotation and the
    scaling EXPRESSIONS are the warps kernel's verbatim (`x = v * inv * w`,
    `o0 = x0*c - x1*s`, `o1 = x0*s + x1*c`, evaluated on SIMD lanes that do not interact), so
    the only changed quantity is the norm's reduction order. That is the same class of change as
    round 5's windowed-TC kernel and round 6's raw-mma port, and like them it carries its own
    build flag and goes through the fp32-oracle token gates rather than being asserted exact on
    the strength of the source text. The reduction order is written out explicitly below so it
    is reproducible and so a future round can compare against a stated association.

    STRUCTURAL CONTRACT (gated at the dispatch site, which keeps the warps kernel otherwise):
    `d_head == 4 * WARP_SIZE == 128`, which is what makes one half-warp of four-element quads
    cover half a head, and every row stride a multiple of 4 elements so the 16-byte alignment
    promise `_ld4`/`_st4` make is discharged by the caller. `blocks_per_row` is
    `ceil((h_q + h_kv) / _G3_ROPEV_HEADS_PER_BLOCK)` and heads past `h_q + h_kv` return.
    Grid `m_rows * blocks_per_row`, block `_G3_ROPE_NTHREADS`."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var m_rows = Int(m_rows_i64)
    var qk_norm = Int(qk_norm_i64)
    var bpr = Int(blocks_per_row_i64)
    var n_units = h_q + h_kv
    var n_pairs = d_head // 2

    var m = Int(block_idx.x) // bpr
    if m >= m_rows:
        return
    var sub = Int(block_idx.x) - m * bpr
    var t = Int(lane_id())
    var half = t // 16                      # which head of this warp: 0 or 1
    var q = t - half * 16                   # lane inside the half-warp: 0..15
    var b = sub * _G3_ROPEV_HEADS_PER_BLOCK + Int(warp_id()) * 2 + half
    if b >= n_units:
        return
    var pos = pos_base + m
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = m * n_qkv
    var is_q = b < h_q
    var head = b if is_q else b - h_q
    var e0 = 4 * q                          # 0, 4, ... , 60 — a multiple of 4 by construction

    var src = row_qkv + (head * d_head if is_q else (h_q + head) * d_head)
    var a0 = _ld4(qkv, src + e0)            # elements e0 .. e0+3
    var a1 = _ld4(qkv, src + e0 + n_pairs)  # their RoPE partners, e0+64 .. e0+67

    var x0 = a0
    var x1 = a1
    if qk_norm == 1:
        # sum of squares over all d_head elements, in a STATED order: the lane's own eight
        # terms left-to-right (first quad, then partner quad), then four shuffle_xor steps that
        # reduce within the 16-lane half-warp only (t ^ 8/4/2/1 never crosses the half).
        var ss = a0[0] * a0[0] + a0[1] * a0[1] + a0[2] * a0[2] + a0[3] * a0[3]
        ss = ss + a1[0] * a1[0]
        ss = ss + a1[1] * a1[1]
        ss = ss + a1[2] * a1[2]
        ss = ss + a1[3] * a1[3]
        ss = ss + _shuffle_xor(ss, 8)
        ss = ss + _shuffle_xor(ss, 4)
        ss = ss + _shuffle_xor(ss, 2)
        ss = ss + _shuffle_xor(ss, 1)
        var inv = 1.0 / sqrt(ss / Float32(d_head) + eps)
        var w0 = _ld4(qn_w, e0) if is_q else _ld4(kn_w, e0)
        var w1 = _ld4(qn_w, e0 + n_pairs) if is_q else _ld4(kn_w, e0 + n_pairs)
        x0 = a0 * inv * w0
        x1 = a1 * inv * w1

    # cos/sin are indexed by the LOW half of the pair, so both quads of this lane share one
    # float4 of each — one load apiece, where the strided mapping needed two.
    var cb = pos * n_pairs + e0
    var c = _ld4(cos_t, cb)
    var s = _ld4(sin_t, cb)
    var o0 = x0 * c - x1 * s                # -> elements e0 .. e0+3
    var o1 = x0 * s + x1 * c                # -> elements e0+64 .. e0+67

    if is_q:
        var qb = m * h_q * d_head + head * d_head
        _st4(q_rot, qb + e0, o0)
        _st4(q_rot, qb + e0 + n_pairs, o1)
    else:
        var kb = (pos * h_kv + head) * d_head
        _st4(ck, kb + e0, o0)
        _st4(ck, kb + e0 + n_pairs, o1)
        # V is neither normalized nor rotated: the warps kernel copies it straight through and
        # so does this. Its slice starts after the h_q + h_kv Q and K slices of the fused row.
        var vsrc = row_qkv + (h_q + h_kv + head) * d_head
        _st4(cv, kb + e0, _ld4(qkv, vsrc + e0))
        _st4(cv, kb + e0 + n_pairs, _ld4(qkv, vsrc + e0 + n_pairs))


def _pf_row_copy_kernel(dst: _FP, src: _FP, row_i64: Int64, n_i64: Int64):
    """`dst[0:n] = src[row, 0:n]` — one row of a [m, n] buffer into a flat buffer (the prefill's
    final residual row into the decode-shaped `hidden`). Grid `ceil(n / _TG)`, block `_TG`."""
    var n = Int(n_i64)
    var row = Int(row_i64)
    var i = Int(block_idx.x) * _TG + Int(thread_idx.x)
    if i < n:
        dst[i] = src[row * n + i]


def _pf_ropewrt_kernel_h(
    q_rot: _FP, ck: _HP, cv: _HP, qkv: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64, eps: Float32, m_rows_i64: Int64,
    qk_norm_i64: Int64,
):
    """Float16-KV twin of `residentk.kernels._pf_ropewrt_kernel` — byte-for-byte the same
    q_norm/k_norm/RoPE math and row layout; ONLY the in-place KV-cache write narrows to
    Float16 at the store (the C=50 fit lever's ingest half)."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var m_rows = Int(m_rows_i64)
    var qk_norm = Int(qk_norm_i64)
    var n_units = h_q + h_kv
    var b = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var pos = pos_base + m
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = m * n_qkv
    var n_q = h_q * d_head
    var row_q_rot = m * n_q

    var xs = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var e = Int(thread_idx.x)
    var is_q = b < h_q
    var head = b if is_q else b - h_q

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
            var kb = (pos * h_kv + head) * d_head
            ck[kb + e] = Float16(o0)
            ck[kb + e + n_pairs] = Float16(o1)

    if not is_q:
        cv[(pos * h_kv + head) * d_head + e] = \
            Float16(qkv[row_qkv + (h_q + h_kv + head) * d_head + e])


def _pf_attn_window_kernel_h(
    attn_out: _FP, q_rot: _FP, ck: _HP, cv: _HP,
    pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    window_i64: Int64, is_global_i64: Int64, scale: Float32, m_rows_i64: Int64,
):
    """Float16-KV twin of `_pf_attn_window_kernel` — windowed causal prefill attention reading a
    Float16 KV cache (each element widened to f32 before the multiply; f32 accumulation
    throughout). Per-row key lower bound and online softmax are the f32-KV kernel's exactly."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var window = Int(window_i64)
    var is_global = Int(is_global_i64)
    var m_rows = Int(m_rows_i64)
    comptime _SIMD_GROUPS: Int = RESIDENT_MAX_HEAD_DIM // WARP_SIZE
    var grp = stack_allocation[_SIMD_GROUPS, DType.float32, address_space = AddressSpace.SHARED]()
    var n_q = h_q * d_head
    var h = Int(block_idx.x) % h_q
    var m = Int(block_idx.x) // h_q
    if m >= m_rows:
        return
    var n_keys = pos_base + m + 1
    var key_lo = 0
    if is_global != 1:
        key_lo = n_keys - window
        if key_lo < 0:
            key_lo = 0
    var e = Int(thread_idx.x)
    var hk = h // (h_q // h_kv)
    var qv = q_rot[m * n_q + h * d_head + e]
    var lane = lane_id()
    var grp_id = warp_id()
    var n_groups = d_head // WARP_SIZE

    var mx = _NEG_HUGE
    var denom = Float32(0.0)
    var o = Float32(0.0)

    for j in range(key_lo, n_keys):
        var kb = (j * h_kv + hk) * d_head
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

        var nm = mx if mx > s else s
        var corr = exp(mx - nm)
        var w = exp(s - nm)
        o = o * corr + w * Float32(cv[kb + e])
        denom = denom * corr + w
        mx = nm

    attn_out[m * n_q + h * d_head + e] = o / denom


comptime _G3_PF_FLASH_ROWS_PER_WARP: Int = 4
"""Query rows ONE WARP computes against the SAME head's K/V stream — the geometry
`residentk.kernels_prefill_attn_flash._pf_attn_flash_kernel` established and the A100 serve
lane proved (its 1-row/warp cut was load-pressure-bound at 88.8% L1TEX; sharing the K/V
float4 loads across four rows cut the attention K/V wavefronts ~4x). Rows are consecutive,
causality is four staggered prefixes (Gemma 3 adds four staggered WINDOW lower bounds),
each row keeps its OWN online-softmax state — bit-identical row math, only the load sharing
and the barrier-free warp-shuffle score tree change."""

comptime _G3_PF_FLASH_WARPS_PER_BLOCK: Int = 8

comptime _G3_PF_FLASH_ROWS_PER_BLOCK: Int = (
    _G3_PF_FLASH_ROWS_PER_WARP * _G3_PF_FLASH_WARPS_PER_BLOCK
)
"""Query rows one block covers: 8 warps x 4 rows of one head."""

comptime _G3_PF_FLASH_NTHREADS: Int = _G3_PF_FLASH_WARPS_PER_BLOCK * 32
"""Threads per block: 8 warps."""


def _pf_attn_window_flash_kernel(
    attn_out: _FP, q_rot: _FP, ck: _FP, cv: _FP,
    pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    window_i64: Int64, is_global_i64: Int64, scale: Float32, m_rows_i64: Int64,
):
    """FLASH-STYLE M-parallel twin of `_pf_attn_window_kernel` — the TTFT lever of the
    vLLM-flip round (nsys 2026-08-24: the windowed barrier-tree prefill attention was 140.3 ms
    = 72.5% of the 263.8 ms TTFT@550 GPU time, 62 dispatches x 2.26 ms), a FAITHFUL Gemma 3
    windowed port of the serve lane's PROVEN `_pf_attn_flash_kernel`
    (`residentk.kernels_prefill_attn_flash`):

    * FOUR CONSECUTIVE ROWS PER WARP, one head per block-column — `grid_dim =
      ceil(m_rows / _G3_PF_FLASH_ROWS_PER_BLOCK) * h_q`, `block_dim = 256`; block `g` covers
      head `g % h_q` and rows `(g // h_q) * ROWS_PER_BLOCK + warp_id()*4 + 0..3`; the warp's
      K/V float4 loads are paid ONCE for all four rows;
    * ZERO barriers, ZERO shared memory — one `_warp_sum` (hardware shuffle) per row per key
      replaces the full-block two-barrier + shared round-trip reduction; lane `l` owns the
      four d_head elements `[4l, 4l+4)` (d_head == 128 = WARP_SIZE x 4, caller-enforced) so Q,
      K and V all stream as ONE coalesced 128-bit `_ld4` per lane;
    * per-row online-softmax recurrence VERBATIM, keys ASCENDING — the ONLY numerical
      difference vs the tiled kernel is the score dot's reduction tree (ulp-level), the
      proven byte-compatible contract;
    * GEMMA 3 WINDOW carried through: row `m` (absolute position `pos_base + m`) attends keys
      `[key_lo, pos_base + m + 1)`, `key_lo = 0` for full-attention layers (`is_global == 1`)
      and `max(0, pos_base + m + 1 - window)` for sliding layers — `_pf_attn_window_kernel`'s
      per-row bound exactly; the warp loop runs `[min key_lo, max n_keys)` and each row
      accumulates only inside its own `[key_lo, n_keys)`, so the four staggered windows fold
      into ONE key stream. Empty rows beyond `m_rows` stay inactive; an all-inactive warp
      cannot occur (row 0 of each block is in-range by the grid guard)."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var window = Int(window_i64)
    var is_global = Int(is_global_i64)
    var m_rows = Int(m_rows_i64)

    var h = Int(block_idx.x) % h_q
    var m_base = (Int(block_idx.x) // h_q) * _G3_PF_FLASH_ROWS_PER_BLOCK \
        + Int(warp_id()) * _G3_PF_FLASH_ROWS_PER_WARP
    if m_base >= m_rows:
        return

    var lane = Int(lane_id())
    var e0 = lane * 4
    var hk = h // (h_q // h_kv)
    var n_q = h_q * d_head

    # ── per-row state (rows beyond m_rows are inactive; row 0 is always active here) ──
    var m0 = m_base
    var m1 = m_base + 1
    var m2 = m_base + 2
    var m3 = m_base + 3
    var act1 = m1 < m_rows
    var act2 = m2 < m_rows
    var act3 = m3 < m_rows
    var nk0 = pos_base + m0 + 1
    var nk1 = pos_base + m1 + 1
    var nk2 = pos_base + m2 + 1
    var nk3 = pos_base + m3 + 1
    # Gemma 3 window lower bounds (0 for full-attention layers).
    var lo0 = 0
    var lo1 = 0
    var lo2 = 0
    var lo3 = 0
    if is_global != 1:
        lo0 = nk0 - window
        if lo0 < 0:
            lo0 = 0
        lo1 = nk1 - window
        if lo1 < 0:
            lo1 = 0
        lo2 = nk2 - window
        if lo2 < 0:
            lo2 = 0
        lo3 = nk3 - window
        if lo3 < 0:
            lo3 = 0
    var nk_max = nk3 if act3 else (nk2 if act2 else (nk1 if act1 else nk0))

    var qb = m0 * n_q + h * d_head + e0
    var q04 = _ld4(q_rot, qb)
    var q00 = q04[0]
    var q01 = q04[1]
    var q02 = q04[2]
    var q03 = q04[3]
    var q10 = Float32(0.0)
    var q11 = Float32(0.0)
    var q12 = Float32(0.0)
    var q13 = Float32(0.0)
    var q20 = Float32(0.0)
    var q21 = Float32(0.0)
    var q22 = Float32(0.0)
    var q23 = Float32(0.0)
    var q30 = Float32(0.0)
    var q31 = Float32(0.0)
    var q32 = Float32(0.0)
    var q33 = Float32(0.0)
    if act1:
        var q14 = _ld4(q_rot, m1 * n_q + h * d_head + e0)
        q10 = q14[0]
        q11 = q14[1]
        q12 = q14[2]
        q13 = q14[3]
    if act2:
        var q24 = _ld4(q_rot, m2 * n_q + h * d_head + e0)
        q20 = q24[0]
        q21 = q24[1]
        q22 = q24[2]
        q23 = q24[3]
    if act3:
        var q34 = _ld4(q_rot, m3 * n_q + h * d_head + e0)
        q30 = q34[0]
        q31 = q34[1]
        q32 = q34[2]
        q33 = q34[3]

    var mx0 = _NEG_HUGE
    var mx1 = _NEG_HUGE
    var mx2 = _NEG_HUGE
    var mx3 = _NEG_HUGE
    var den0 = Float32(0.0)
    var den1 = Float32(0.0)
    var den2 = Float32(0.0)
    var den3 = Float32(0.0)
    var o00 = Float32(0.0)
    var o01 = Float32(0.0)
    var o02 = Float32(0.0)
    var o03 = Float32(0.0)
    var o10 = Float32(0.0)
    var o11 = Float32(0.0)
    var o12 = Float32(0.0)
    var o13 = Float32(0.0)
    var o20 = Float32(0.0)
    var o21 = Float32(0.0)
    var o22 = Float32(0.0)
    var o23 = Float32(0.0)
    var o30 = Float32(0.0)
    var o31 = Float32(0.0)
    var o32 = Float32(0.0)
    var o33 = Float32(0.0)

    var j = lo0
    while j < nk_max:
        var kb = (j * h_kv + hk) * d_head + e0
        var kv4 = _ld4(ck, kb)
        # per-row activity at key j (warp-uniform): the four staggered [key_lo, n_keys) spans
        var a0 = lo0 <= j and j < nk0
        var a1 = act1 and lo1 <= j and j < nk1
        var a2 = act2 and lo2 <= j and j < nk2
        var a3 = act3 and lo3 <= j and j < nk3
        var s0 = _NEG_HUGE
        var s1 = _NEG_HUGE
        var s2 = _NEG_HUGE
        var s3 = _NEG_HUGE
        if a0:
            s0 = _warp_sum(
                q00 * kv4[0] + q01 * kv4[1] + q02 * kv4[2] + q03 * kv4[3]) * scale
        if a1:
            s1 = _warp_sum(
                q10 * kv4[0] + q11 * kv4[1] + q12 * kv4[2] + q13 * kv4[3]) * scale
        if a2:
            s2 = _warp_sum(
                q20 * kv4[0] + q21 * kv4[1] + q22 * kv4[2] + q23 * kv4[3]) * scale
        if a3:
            s3 = _warp_sum(
                q30 * kv4[0] + q31 * kv4[1] + q32 * kv4[2] + q33 * kv4[3]) * scale
        # ONE shared V load per key for all four rows
        var vv4 = _ld4(cv, kb)
        if a0:
            var nm0 = mx0 if mx0 > s0 else s0
            var corr0 = exp(mx0 - nm0)
            var w0 = exp(s0 - nm0)
            o00 = o00 * corr0 + w0 * vv4[0]
            o01 = o01 * corr0 + w0 * vv4[1]
            o02 = o02 * corr0 + w0 * vv4[2]
            o03 = o03 * corr0 + w0 * vv4[3]
            den0 = den0 * corr0 + w0
            mx0 = nm0
        if a1:
            var nm1 = mx1 if mx1 > s1 else s1
            var corr1 = exp(mx1 - nm1)
            var w1 = exp(s1 - nm1)
            o10 = o10 * corr1 + w1 * vv4[0]
            o11 = o11 * corr1 + w1 * vv4[1]
            o12 = o12 * corr1 + w1 * vv4[2]
            o13 = o13 * corr1 + w1 * vv4[3]
            den1 = den1 * corr1 + w1
            mx1 = nm1
        if a2:
            var nm2 = mx2 if mx2 > s2 else s2
            var corr2 = exp(mx2 - nm2)
            var w2 = exp(s2 - nm2)
            o20 = o20 * corr2 + w2 * vv4[0]
            o21 = o21 * corr2 + w2 * vv4[1]
            o22 = o22 * corr2 + w2 * vv4[2]
            o23 = o23 * corr2 + w2 * vv4[3]
            den2 = den2 * corr2 + w2
            mx2 = nm2
        if a3:
            var nm3 = mx3 if mx3 > s3 else s3
            var corr3 = exp(mx3 - nm3)
            var w3 = exp(s3 - nm3)
            o30 = o30 * corr3 + w3 * vv4[0]
            o31 = o31 * corr3 + w3 * vv4[1]
            o32 = o32 * corr3 + w3 * vv4[2]
            o33 = o33 * corr3 + w3 * vv4[3]
            den3 = den3 * corr3 + w3
            mx3 = nm3
        j += 1

    var ob0 = m0 * n_q + h * d_head + e0
    attn_out[ob0 + 0] = o00 / den0
    attn_out[ob0 + 1] = o01 / den0
    attn_out[ob0 + 2] = o02 / den0
    attn_out[ob0 + 3] = o03 / den0
    if act1:
        var ob1 = m1 * n_q + h * d_head + e0
        attn_out[ob1 + 0] = o10 / den1
        attn_out[ob1 + 1] = o11 / den1
        attn_out[ob1 + 2] = o12 / den1
        attn_out[ob1 + 3] = o13 / den1
    if act2:
        var ob2 = m2 * n_q + h * d_head + e0
        attn_out[ob2 + 0] = o20 / den2
        attn_out[ob2 + 1] = o21 / den2
        attn_out[ob2 + 2] = o22 / den2
        attn_out[ob2 + 3] = o23 / den2
    if act3:
        var ob3 = m3 * n_q + h * d_head + e0
        attn_out[ob3 + 0] = o30 / den3
        attn_out[ob3 + 1] = o31 / den3
        attn_out[ob3 + 2] = o32 / den3
        attn_out[ob3 + 3] = o33 / den3



def _pf_attn_window_flash_kernel_h(
    attn_out: _FP, q_rot: _FP, ck: _HP, cv: _HP,
    pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, d_head_i64: Int64,
    window_i64: Int64, is_global_i64: Int64, scale: Float32, m_rows_i64: Int64,
):
    """Float16-KV twin of `_pf_attn_window_flash_kernel` — identical four-rows-per-warp flash
    structure and windowed per-row bounds; ONLY the K/V loads differ: 8-byte vectorized f16
    (`alignment=8`) widened to f32 before the dot / V-accum (f32 accumulation throughout, the
    kv16 barrier-tree kernel's exact arithmetic). The batched session's per-sequence ingest
    dispatches this twin under `-D ALGENTA_G3_PF_ATTN_FLASH` + `-D ALGENTA_G3_KV_F16`
    (d_head == 128 fact-driven)."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var window = Int(window_i64)
    var is_global = Int(is_global_i64)
    var m_rows = Int(m_rows_i64)

    var h = Int(block_idx.x) % h_q
    var m_base = (Int(block_idx.x) // h_q) * _G3_PF_FLASH_ROWS_PER_BLOCK \
        + Int(warp_id()) * _G3_PF_FLASH_ROWS_PER_WARP
    if m_base >= m_rows:
        return

    var lane = Int(lane_id())
    var e0 = lane * 4
    var hk = h // (h_q // h_kv)
    var n_q = h_q * d_head

    var m0 = m_base
    var m1 = m_base + 1
    var m2 = m_base + 2
    var m3 = m_base + 3
    var act1 = m1 < m_rows
    var act2 = m2 < m_rows
    var act3 = m3 < m_rows
    var nk0 = pos_base + m0 + 1
    var nk1 = pos_base + m1 + 1
    var nk2 = pos_base + m2 + 1
    var nk3 = pos_base + m3 + 1
    var lo0 = 0
    var lo1 = 0
    var lo2 = 0
    var lo3 = 0
    if is_global != 1:
        lo0 = nk0 - window
        if lo0 < 0:
            lo0 = 0
        lo1 = nk1 - window
        if lo1 < 0:
            lo1 = 0
        lo2 = nk2 - window
        if lo2 < 0:
            lo2 = 0
        lo3 = nk3 - window
        if lo3 < 0:
            lo3 = 0
    var nk_max = nk3 if act3 else (nk2 if act2 else (nk1 if act1 else nk0))

    var qb = m0 * n_q + h * d_head + e0
    var q04 = _ld4(q_rot, qb)
    var q00 = q04[0]
    var q01 = q04[1]
    var q02 = q04[2]
    var q03 = q04[3]
    var q10 = Float32(0.0)
    var q11 = Float32(0.0)
    var q12 = Float32(0.0)
    var q13 = Float32(0.0)
    var q20 = Float32(0.0)
    var q21 = Float32(0.0)
    var q22 = Float32(0.0)
    var q23 = Float32(0.0)
    var q30 = Float32(0.0)
    var q31 = Float32(0.0)
    var q32 = Float32(0.0)
    var q33 = Float32(0.0)
    if act1:
        var q14 = _ld4(q_rot, m1 * n_q + h * d_head + e0)
        q10 = q14[0]
        q11 = q14[1]
        q12 = q14[2]
        q13 = q14[3]
    if act2:
        var q24 = _ld4(q_rot, m2 * n_q + h * d_head + e0)
        q20 = q24[0]
        q21 = q24[1]
        q22 = q24[2]
        q23 = q24[3]
    if act3:
        var q34 = _ld4(q_rot, m3 * n_q + h * d_head + e0)
        q30 = q34[0]
        q31 = q34[1]
        q32 = q34[2]
        q33 = q34[3]

    var mx0 = _NEG_HUGE
    var mx1 = _NEG_HUGE
    var mx2 = _NEG_HUGE
    var mx3 = _NEG_HUGE
    var den0 = Float32(0.0)
    var den1 = Float32(0.0)
    var den2 = Float32(0.0)
    var den3 = Float32(0.0)
    var o00 = Float32(0.0)
    var o01 = Float32(0.0)
    var o02 = Float32(0.0)
    var o03 = Float32(0.0)
    var o10 = Float32(0.0)
    var o11 = Float32(0.0)
    var o12 = Float32(0.0)
    var o13 = Float32(0.0)
    var o20 = Float32(0.0)
    var o21 = Float32(0.0)
    var o22 = Float32(0.0)
    var o23 = Float32(0.0)
    var o30 = Float32(0.0)
    var o31 = Float32(0.0)
    var o32 = Float32(0.0)
    var o33 = Float32(0.0)

    var j = lo0
    while j < nk_max:
        var kb = (j * h_kv + hk) * d_head + e0
        var kv4 = ck.load[width=4, alignment=8](kb).cast[DType.float32]()
        var a0 = lo0 <= j and j < nk0
        var a1 = act1 and lo1 <= j and j < nk1
        var a2 = act2 and lo2 <= j and j < nk2
        var a3 = act3 and lo3 <= j and j < nk3
        var s0 = _NEG_HUGE
        var s1 = _NEG_HUGE
        var s2 = _NEG_HUGE
        var s3 = _NEG_HUGE
        if a0:
            s0 = _warp_sum(
                q00 * kv4[0] + q01 * kv4[1] + q02 * kv4[2] + q03 * kv4[3]) * scale
        if a1:
            s1 = _warp_sum(
                q10 * kv4[0] + q11 * kv4[1] + q12 * kv4[2] + q13 * kv4[3]) * scale
        if a2:
            s2 = _warp_sum(
                q20 * kv4[0] + q21 * kv4[1] + q22 * kv4[2] + q23 * kv4[3]) * scale
        if a3:
            s3 = _warp_sum(
                q30 * kv4[0] + q31 * kv4[1] + q32 * kv4[2] + q33 * kv4[3]) * scale
        var vv4 = cv.load[width=4, alignment=8](kb).cast[DType.float32]()
        if a0:
            var nm0 = mx0 if mx0 > s0 else s0
            var corr0 = exp(mx0 - nm0)
            var w0 = exp(s0 - nm0)
            o00 = o00 * corr0 + w0 * vv4[0]
            o01 = o01 * corr0 + w0 * vv4[1]
            o02 = o02 * corr0 + w0 * vv4[2]
            o03 = o03 * corr0 + w0 * vv4[3]
            den0 = den0 * corr0 + w0
            mx0 = nm0
        if a1:
            var nm1 = mx1 if mx1 > s1 else s1
            var corr1 = exp(mx1 - nm1)
            var w1 = exp(s1 - nm1)
            o10 = o10 * corr1 + w1 * vv4[0]
            o11 = o11 * corr1 + w1 * vv4[1]
            o12 = o12 * corr1 + w1 * vv4[2]
            o13 = o13 * corr1 + w1 * vv4[3]
            den1 = den1 * corr1 + w1
            mx1 = nm1
        if a2:
            var nm2 = mx2 if mx2 > s2 else s2
            var corr2 = exp(mx2 - nm2)
            var w2 = exp(s2 - nm2)
            o20 = o20 * corr2 + w2 * vv4[0]
            o21 = o21 * corr2 + w2 * vv4[1]
            o22 = o22 * corr2 + w2 * vv4[2]
            o23 = o23 * corr2 + w2 * vv4[3]
            den2 = den2 * corr2 + w2
            mx2 = nm2
        if a3:
            var nm3 = mx3 if mx3 > s3 else s3
            var corr3 = exp(mx3 - nm3)
            var w3 = exp(s3 - nm3)
            o30 = o30 * corr3 + w3 * vv4[0]
            o31 = o31 * corr3 + w3 * vv4[1]
            o32 = o32 * corr3 + w3 * vv4[2]
            o33 = o33 * corr3 + w3 * vv4[3]
            den3 = den3 * corr3 + w3
            mx3 = nm3
        j += 1

    var ob0 = m0 * n_q + h * d_head + e0
    attn_out[ob0 + 0] = o00 / den0
    attn_out[ob0 + 1] = o01 / den0
    attn_out[ob0 + 2] = o02 / den0
    attn_out[ob0 + 3] = o03 / den0
    if act1:
        var ob1 = m1 * n_q + h * d_head + e0
        attn_out[ob1 + 0] = o10 / den1
        attn_out[ob1 + 1] = o11 / den1
        attn_out[ob1 + 2] = o12 / den1
        attn_out[ob1 + 3] = o13 / den1
    if act2:
        var ob2 = m2 * n_q + h * d_head + e0
        attn_out[ob2 + 0] = o20 / den2
        attn_out[ob2 + 1] = o21 / den2
        attn_out[ob2 + 2] = o22 / den2
        attn_out[ob2 + 3] = o23 / den2
    if act3:
        var ob3 = m3 * n_q + h * d_head + e0
        attn_out[ob3 + 0] = o30 / den3
        attn_out[ob3 + 1] = o31 / den3
        attn_out[ob3 + 2] = o32 / den3
        attn_out[ob3 + 3] = o33 / den3



# ── the v2-family GEMM twins ─────────────────────────────────────────────────────────────────
# Geometry, double buffering, register block, column ownership and accumulation ORDER are
# residentk.kernels_prefill_f32_v2's verbatim (the constants are IMPORTED from that module, so
# they cannot drift). Two families:
#   * `_pf_gemm_geglu_kernel_v2`  — f32 weights (the f32 gemma3 session),
#   * `_pf_gemm_*_kernel_v2h`     — f16-RESIDENT weights (the 27B race arm), f32 activations /
#     shared tiles / accumulators; the B cooperative load widens width-4 Float16 loads.


def _pf_gemm_geglu_kernel_v2(
    act: _FP, xn: _FP, w: _FP, m_rows_i64: Int64, k_i64: Int64, n_ff_i64: Int64
):
    """The GeGLU epilogue twin of `_pf_gemm_swiglu_kernel_v2`: the fused gate/up projection +
    gelu_pytorch_tanh combine — `w` is the resident `[2*n_ff, k]` gate-THEN-up concatenation,
    `act[M,n_ff] = gelu_pytorch_tanh(xn @ W_gate^T) * (xn @ W_up^T)`. Structure is byte-for-byte
    the SwiGLU twin's (4x4 register block, double-buffered a/gate/up tiles, 32 accumulators per
    thread); ONLY the epilogue expression differs."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    comptime BM = _G2_BM
    comptime BN = _G2_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime APAD = _G2_APAD
    comptime BPAD = _G2_BPAD

    var a0 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var a1 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bg0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bg1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bu0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bu1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n_ff + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    var g00 = Float32(0.0)
    var g01 = Float32(0.0)
    var g02 = Float32(0.0)
    var g03 = Float32(0.0)
    var g10 = Float32(0.0)
    var g11 = Float32(0.0)
    var g12 = Float32(0.0)
    var g13 = Float32(0.0)
    var g20 = Float32(0.0)
    var g21 = Float32(0.0)
    var g22 = Float32(0.0)
    var g23 = Float32(0.0)
    var g30 = Float32(0.0)
    var g31 = Float32(0.0)
    var g32 = Float32(0.0)
    var g33 = Float32(0.0)
    var u00 = Float32(0.0)
    var u01 = Float32(0.0)
    var u02 = Float32(0.0)
    var u03 = Float32(0.0)
    var u10 = Float32(0.0)
    var u11 = Float32(0.0)
    var u12 = Float32(0.0)
    var u13 = Float32(0.0)
    var u20 = Float32(0.0)
    var u21 = Float32(0.0)
    var u22 = Float32(0.0)
    var u23 = Float32(0.0)
    var u30 = Float32(0.0)
    var u31 = Float32(0.0)
    var u32 = Float32(0.0)
    var u33 = Float32(0.0)

    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = _ld4(xn, gr0 * k + lc)
        a0[lr * APAD + lc + 0] = va[0]
        a0[lr * APAD + lc + 1] = va[1]
        a0[lr * APAD + lc + 2] = va[2]
        a0[lr * APAD + lc + 3] = va[3]
    elif gr0 < m_rows:
        for e in range(4):
            a0[lr * APAD + lc + e] = xn[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            a0[lr * APAD + lc + e] = Float32(0.0)
    var wr0 = block_col + lr
    if wr0 < n_ff and lc + 3 < k:
        var vg = _ld4(w, wr0 * k + lc)
        var vu = _ld4(w, (n_ff + wr0) * k + lc)
        bg0[(lc + 0) * BPAD + lr] = vg[0]
        bg0[(lc + 1) * BPAD + lr] = vg[1]
        bg0[(lc + 2) * BPAD + lr] = vg[2]
        bg0[(lc + 3) * BPAD + lr] = vg[3]
        bu0[(lc + 0) * BPAD + lr] = vu[0]
        bu0[(lc + 1) * BPAD + lr] = vu[1]
        bu0[(lc + 2) * BPAD + lr] = vu[2]
        bu0[(lc + 3) * BPAD + lr] = vu[3]
    elif wr0 < n_ff:
        for e in range(4):
            var ge = w[wr0 * k + lc + e] if lc + e < k else Float32(0.0)
            var ue = w[(n_ff + wr0) * k + lc + e] if lc + e < k else Float32(0.0)
            bg0[(lc + e) * BPAD + lr] = ge
            bu0[(lc + e) * BPAD + lr] = ue
    else:
        for e in range(4):
            bg0[(lc + e) * BPAD + lr] = Float32(0.0)
            bu0[(lc + e) * BPAD + lr] = Float32(0.0)
    barrier()

    var cur = 0
    for step in range(n_steps):
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            var agr = block_row + lr
            var wgr = block_col + lr
            if cur == 0:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a1[lr * APAD + lc + 0] = va[0]
                    a1[lr * APAD + lc + 1] = va[1]
                    a1[lr * APAD + lc + 2] = va[2]
                    a1[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = Float32(0.0)
                if wgr < n_ff and ngc + 3 < k:
                    var vg = _ld4(w, wgr * k + ngc)
                    var vu = _ld4(w, (n_ff + wgr) * k + ngc)
                    bg1[(lc + 0) * BPAD + lr] = vg[0]
                    bg1[(lc + 1) * BPAD + lr] = vg[1]
                    bg1[(lc + 2) * BPAD + lr] = vg[2]
                    bg1[(lc + 3) * BPAD + lr] = vg[3]
                    bu1[(lc + 0) * BPAD + lr] = vu[0]
                    bu1[(lc + 1) * BPAD + lr] = vu[1]
                    bu1[(lc + 2) * BPAD + lr] = vu[2]
                    bu1[(lc + 3) * BPAD + lr] = vu[3]
                elif wgr < n_ff:
                    for e in range(4):
                        var ge = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                        var ue = w[(n_ff + wgr) * k + ngc + e] if ngc + e < k else Float32(0.0)
                        bg1[(lc + e) * BPAD + lr] = ge
                        bu1[(lc + e) * BPAD + lr] = ue
                else:
                    for e in range(4):
                        bg1[(lc + e) * BPAD + lr] = Float32(0.0)
                        bu1[(lc + e) * BPAD + lr] = Float32(0.0)
            else:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a0[lr * APAD + lc + 0] = va[0]
                    a0[lr * APAD + lc + 1] = va[1]
                    a0[lr * APAD + lc + 2] = va[2]
                    a0[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = Float32(0.0)
                if wgr < n_ff and ngc + 3 < k:
                    var vg = _ld4(w, wgr * k + ngc)
                    var vu = _ld4(w, (n_ff + wgr) * k + ngc)
                    bg0[(lc + 0) * BPAD + lr] = vg[0]
                    bg0[(lc + 1) * BPAD + lr] = vg[1]
                    bg0[(lc + 2) * BPAD + lr] = vg[2]
                    bg0[(lc + 3) * BPAD + lr] = vg[3]
                    bu0[(lc + 0) * BPAD + lr] = vu[0]
                    bu0[(lc + 1) * BPAD + lr] = vu[1]
                    bu0[(lc + 2) * BPAD + lr] = vu[2]
                    bu0[(lc + 3) * BPAD + lr] = vu[3]
                elif wgr < n_ff:
                    for e in range(4):
                        var ge = w[wgr * k + ngc + e] if ngc + e < k else Float32(0.0)
                        var ue = w[(n_ff + wgr) * k + ngc + e] if ngc + e < k else Float32(0.0)
                        bg0[(lc + e) * BPAD + lr] = ge
                        bu0[(lc + e) * BPAD + lr] = ue
                else:
                    for e in range(4):
                        bg0[(lc + e) * BPAD + lr] = Float32(0.0)
                        bu0[(lc + e) * BPAD + lr] = Float32(0.0)

        var acur = a0 if cur == 0 else a1
        var bgcur = bg0 if cur == 0 else bg1
        var bucur = bu0 if cur == 0 else bu1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xg0 = bgcur[kk * BPAD + tx]
            var xg1 = bgcur[kk * BPAD + tx + 16]
            var xg2 = bgcur[kk * BPAD + tx + 32]
            var xg3 = bgcur[kk * BPAD + tx + 48]
            var xu0 = bucur[kk * BPAD + tx]
            var xu1 = bucur[kk * BPAD + tx + 16]
            var xu2 = bucur[kk * BPAD + tx + 32]
            var xu3 = bucur[kk * BPAD + tx + 48]
            g00 += xa0 * xg0
            g01 += xa0 * xg1
            g02 += xa0 * xg2
            g03 += xa0 * xg3
            g10 += xa1 * xg0
            g11 += xa1 * xg1
            g12 += xa1 * xg2
            g13 += xa1 * xg3
            g20 += xa2 * xg0
            g21 += xa2 * xg1
            g22 += xa2 * xg2
            g23 += xa2 * xg3
            g30 += xa3 * xg0
            g31 += xa3 * xg1
            g32 += xa3 * xg2
            g33 += xa3 * xg3
            u00 += xa0 * xu0
            u01 += xa0 * xu1
            u02 += xa0 * xu2
            u03 += xa0 * xu3
            u10 += xa1 * xu0
            u11 += xa1 * xu1
            u12 += xa1 * xu2
            u13 += xa1 * xu3
            u20 += xa2 * xu0
            u21 += xa2 * xu1
            u22 += xa2 * xu2
            u23 += xa2 * xu3
            u30 += xa3 * xu0
            u31 += xa3 * xu1
            u32 += xa3 * xu2
            u33 += xa3 * xu3
        barrier()
        cur = 1 - cur

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    if r0 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g00 + Float32(0.044715) * g00 * g00 * g00)
        act[r0 * n_ff + cc0] = Float32(0.5) * g00 * (Float32(1.0) + tanh(inn)) * u00
    if r0 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g01 + Float32(0.044715) * g01 * g01 * g01)
        act[r0 * n_ff + cc1] = Float32(0.5) * g01 * (Float32(1.0) + tanh(inn)) * u01
    if r0 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g02 + Float32(0.044715) * g02 * g02 * g02)
        act[r0 * n_ff + cc2] = Float32(0.5) * g02 * (Float32(1.0) + tanh(inn)) * u02
    if r0 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g03 + Float32(0.044715) * g03 * g03 * g03)
        act[r0 * n_ff + cc3] = Float32(0.5) * g03 * (Float32(1.0) + tanh(inn)) * u03
    if r1 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g10 + Float32(0.044715) * g10 * g10 * g10)
        act[r1 * n_ff + cc0] = Float32(0.5) * g10 * (Float32(1.0) + tanh(inn)) * u10
    if r1 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g11 + Float32(0.044715) * g11 * g11 * g11)
        act[r1 * n_ff + cc1] = Float32(0.5) * g11 * (Float32(1.0) + tanh(inn)) * u11
    if r1 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g12 + Float32(0.044715) * g12 * g12 * g12)
        act[r1 * n_ff + cc2] = Float32(0.5) * g12 * (Float32(1.0) + tanh(inn)) * u12
    if r1 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g13 + Float32(0.044715) * g13 * g13 * g13)
        act[r1 * n_ff + cc3] = Float32(0.5) * g13 * (Float32(1.0) + tanh(inn)) * u13
    if r2 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g20 + Float32(0.044715) * g20 * g20 * g20)
        act[r2 * n_ff + cc0] = Float32(0.5) * g20 * (Float32(1.0) + tanh(inn)) * u20
    if r2 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g21 + Float32(0.044715) * g21 * g21 * g21)
        act[r2 * n_ff + cc1] = Float32(0.5) * g21 * (Float32(1.0) + tanh(inn)) * u21
    if r2 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g22 + Float32(0.044715) * g22 * g22 * g22)
        act[r2 * n_ff + cc2] = Float32(0.5) * g22 * (Float32(1.0) + tanh(inn)) * u22
    if r2 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g23 + Float32(0.044715) * g23 * g23 * g23)
        act[r2 * n_ff + cc3] = Float32(0.5) * g23 * (Float32(1.0) + tanh(inn)) * u23
    if r3 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g30 + Float32(0.044715) * g30 * g30 * g30)
        act[r3 * n_ff + cc0] = Float32(0.5) * g30 * (Float32(1.0) + tanh(inn)) * u30
    if r3 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g31 + Float32(0.044715) * g31 * g31 * g31)
        act[r3 * n_ff + cc1] = Float32(0.5) * g31 * (Float32(1.0) + tanh(inn)) * u31
    if r3 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g32 + Float32(0.044715) * g32 * g32 * g32)
        act[r3 * n_ff + cc2] = Float32(0.5) * g32 * (Float32(1.0) + tanh(inn)) * u32
    if r3 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g33 + Float32(0.044715) * g33 * g33 * g33)
        act[r3 * n_ff + cc3] = Float32(0.5) * g33 * (Float32(1.0) + tanh(inn)) * u33


def _pf_gemm_assign_kernel_v2h(
    y: _FP, xn: _FP, w: _HP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """The f16-RESIDENT-WEIGHT twin of `_pf_gemm_assign_kernel_v2`: `y[M,n] = xn[M,k] @ W^T[k,n]`,
    `w` stored `[n,k]` row-major in FLOAT16 (the 27B race arm's storage), ASSIGNING into `y`.
    Geometry / double buffering / register block / accumulation order are the v2 family's
    verbatim; the B-tile cooperative load reads width-4 Float16 and widens each element to
    Float32 BEFORE staging into the shared tile, so the inner loop and accumulators stay the
    proven Float32 path (the eager decode arm's exact arithmetic)."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G2_BM
    comptime BN = _G2_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime APAD = _G2_APAD
    comptime BPAD = _G2_BPAD

    var a0 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var a1 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    var c00 = Float32(0.0)
    var c01 = Float32(0.0)
    var c02 = Float32(0.0)
    var c03 = Float32(0.0)
    var c10 = Float32(0.0)
    var c11 = Float32(0.0)
    var c12 = Float32(0.0)
    var c13 = Float32(0.0)
    var c20 = Float32(0.0)
    var c21 = Float32(0.0)
    var c22 = Float32(0.0)
    var c23 = Float32(0.0)
    var c30 = Float32(0.0)
    var c31 = Float32(0.0)
    var c32 = Float32(0.0)
    var c33 = Float32(0.0)

    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = _ld4(xn, gr0 * k + lc)
        a0[lr * APAD + lc + 0] = va[0]
        a0[lr * APAD + lc + 1] = va[1]
        a0[lr * APAD + lc + 2] = va[2]
        a0[lr * APAD + lc + 3] = va[3]
    elif gr0 < m_rows:
        for e in range(4):
            a0[lr * APAD + lc + e] = xn[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            a0[lr * APAD + lc + e] = Float32(0.0)
    var wr0 = block_col + lr
    if wr0 < n and lc + 3 < k:
        var vb = w.load[width=4](wr0 * k + lc)
        b0[(lc + 0) * BPAD + lr] = Float32(vb[0])
        b0[(lc + 1) * BPAD + lr] = Float32(vb[1])
        b0[(lc + 2) * BPAD + lr] = Float32(vb[2])
        b0[(lc + 3) * BPAD + lr] = Float32(vb[3])
    elif wr0 < n:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = Float32(w[wr0 * k + lc + e]) if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = Float32(0.0)
    barrier()

    var cur = 0
    for step in range(n_steps):
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            var agr = block_row + lr
            if cur == 0:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a1[lr * APAD + lc + 0] = va[0]
                    a1[lr * APAD + lc + 1] = va[1]
                    a1[lr * APAD + lc + 2] = va[2]
                    a1[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
                    b1[(lc + 0) * BPAD + lr] = Float32(vb[0])
                    b1[(lc + 1) * BPAD + lr] = Float32(vb[1])
                    b1[(lc + 2) * BPAD + lr] = Float32(vb[2])
                    b1[(lc + 3) * BPAD + lr] = Float32(vb[3])
                elif wgr < n:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = Float32(w[wgr * k + ngc + e]) if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = Float32(0.0)
            else:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a0[lr * APAD + lc + 0] = va[0]
                    a0[lr * APAD + lc + 1] = va[1]
                    a0[lr * APAD + lc + 2] = va[2]
                    a0[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
                    b0[(lc + 0) * BPAD + lr] = Float32(vb[0])
                    b0[(lc + 1) * BPAD + lr] = Float32(vb[1])
                    b0[(lc + 2) * BPAD + lr] = Float32(vb[2])
                    b0[(lc + 3) * BPAD + lr] = Float32(vb[3])
                elif wgr < n:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = Float32(w[wgr * k + ngc + e]) if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = Float32(0.0)

        var acur = a0 if cur == 0 else a1
        var bcur = b0 if cur == 0 else b1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xb0 = bcur[kk * BPAD + tx]
            var xb1 = bcur[kk * BPAD + tx + 16]
            var xb2 = bcur[kk * BPAD + tx + 32]
            var xb3 = bcur[kk * BPAD + tx + 48]
            c00 += xa0 * xb0
            c01 += xa0 * xb1
            c02 += xa0 * xb2
            c03 += xa0 * xb3
            c10 += xa1 * xb0
            c11 += xa1 * xb1
            c12 += xa1 * xb2
            c13 += xa1 * xb3
            c20 += xa2 * xb0
            c21 += xa2 * xb1
            c22 += xa2 * xb2
            c23 += xa2 * xb3
            c30 += xa3 * xb0
            c31 += xa3 * xb1
            c32 += xa3 * xb2
            c33 += xa3 * xb3
        barrier()
        cur = 1 - cur

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    if r0 < m_rows and cc0 < n:
        y[r0 * n + cc0] = c00
    if r0 < m_rows and cc1 < n:
        y[r0 * n + cc1] = c01
    if r0 < m_rows and cc2 < n:
        y[r0 * n + cc2] = c02
    if r0 < m_rows and cc3 < n:
        y[r0 * n + cc3] = c03
    if r1 < m_rows and cc0 < n:
        y[r1 * n + cc0] = c10
    if r1 < m_rows and cc1 < n:
        y[r1 * n + cc1] = c11
    if r1 < m_rows and cc2 < n:
        y[r1 * n + cc2] = c12
    if r1 < m_rows and cc3 < n:
        y[r1 * n + cc3] = c13
    if r2 < m_rows and cc0 < n:
        y[r2 * n + cc0] = c20
    if r2 < m_rows and cc1 < n:
        y[r2 * n + cc1] = c21
    if r2 < m_rows and cc2 < n:
        y[r2 * n + cc2] = c22
    if r2 < m_rows and cc3 < n:
        y[r2 * n + cc3] = c23
    if r3 < m_rows and cc0 < n:
        y[r3 * n + cc0] = c30
    if r3 < m_rows and cc1 < n:
        y[r3 * n + cc1] = c31
    if r3 < m_rows and cc2 < n:
        y[r3 * n + cc2] = c32
    if r3 < m_rows and cc3 < n:
        y[r3 * n + cc3] = c33


def _pf_gemm_accum_kernel_v2h(
    y: _FP, x: _FP, w: _HP, m_rows_i64: Int64, k_i64: Int64, n_i64: Int64
):
    """The f16-resident-weight ACCUMULATE twin: `y[M,n] += x[M,k] @ W^T[k,n]` — byte-for-byte
    `_pf_gemm_assign_kernel_v2h`'s structure except the epilogue accumulates. (The gemma3 f16
    session dispatches the ASSIGN form into its branch scratch; this twin exists so the family
    is complete for any future residual-accumulate role and is A/B-gated alongside it.)"""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n = Int(n_i64)
    comptime BM = _G2_BM
    comptime BN = _G2_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime APAD = _G2_APAD
    comptime BPAD = _G2_BPAD

    var a0 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var a1 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var b1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    var c00 = Float32(0.0)
    var c01 = Float32(0.0)
    var c02 = Float32(0.0)
    var c03 = Float32(0.0)
    var c10 = Float32(0.0)
    var c11 = Float32(0.0)
    var c12 = Float32(0.0)
    var c13 = Float32(0.0)
    var c20 = Float32(0.0)
    var c21 = Float32(0.0)
    var c22 = Float32(0.0)
    var c23 = Float32(0.0)
    var c30 = Float32(0.0)
    var c31 = Float32(0.0)
    var c32 = Float32(0.0)
    var c33 = Float32(0.0)

    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = _ld4(x, gr0 * k + lc)
        a0[lr * APAD + lc + 0] = va[0]
        a0[lr * APAD + lc + 1] = va[1]
        a0[lr * APAD + lc + 2] = va[2]
        a0[lr * APAD + lc + 3] = va[3]
    elif gr0 < m_rows:
        for e in range(4):
            a0[lr * APAD + lc + e] = x[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            a0[lr * APAD + lc + e] = Float32(0.0)
    var wr0 = block_col + lr
    if wr0 < n and lc + 3 < k:
        var vb = w.load[width=4](wr0 * k + lc)
        b0[(lc + 0) * BPAD + lr] = Float32(vb[0])
        b0[(lc + 1) * BPAD + lr] = Float32(vb[1])
        b0[(lc + 2) * BPAD + lr] = Float32(vb[2])
        b0[(lc + 3) * BPAD + lr] = Float32(vb[3])
    elif wr0 < n:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = Float32(w[wr0 * k + lc + e]) if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            b0[(lc + e) * BPAD + lr] = Float32(0.0)
    barrier()

    var cur = 0
    for step in range(n_steps):
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            var agr = block_row + lr
            if cur == 0:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(x, agr * k + ngc)
                    a1[lr * APAD + lc + 0] = va[0]
                    a1[lr * APAD + lc + 1] = va[1]
                    a1[lr * APAD + lc + 2] = va[2]
                    a1[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = x[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
                    b1[(lc + 0) * BPAD + lr] = Float32(vb[0])
                    b1[(lc + 1) * BPAD + lr] = Float32(vb[1])
                    b1[(lc + 2) * BPAD + lr] = Float32(vb[2])
                    b1[(lc + 3) * BPAD + lr] = Float32(vb[3])
                elif wgr < n:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = Float32(w[wgr * k + ngc + e]) if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b1[(lc + e) * BPAD + lr] = Float32(0.0)
            else:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(x, agr * k + ngc)
                    a0[lr * APAD + lc + 0] = va[0]
                    a0[lr * APAD + lc + 1] = va[1]
                    a0[lr * APAD + lc + 2] = va[2]
                    a0[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = x[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = Float32(0.0)
                var wgr = block_col + lr
                if wgr < n and ngc + 3 < k:
                    var vb = w.load[width=4](wgr * k + ngc)
                    b0[(lc + 0) * BPAD + lr] = Float32(vb[0])
                    b0[(lc + 1) * BPAD + lr] = Float32(vb[1])
                    b0[(lc + 2) * BPAD + lr] = Float32(vb[2])
                    b0[(lc + 3) * BPAD + lr] = Float32(vb[3])
                elif wgr < n:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = Float32(w[wgr * k + ngc + e]) if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        b0[(lc + e) * BPAD + lr] = Float32(0.0)

        var acur = a0 if cur == 0 else a1
        var bcur = b0 if cur == 0 else b1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xb0 = bcur[kk * BPAD + tx]
            var xb1 = bcur[kk * BPAD + tx + 16]
            var xb2 = bcur[kk * BPAD + tx + 32]
            var xb3 = bcur[kk * BPAD + tx + 48]
            c00 += xa0 * xb0
            c01 += xa0 * xb1
            c02 += xa0 * xb2
            c03 += xa0 * xb3
            c10 += xa1 * xb0
            c11 += xa1 * xb1
            c12 += xa1 * xb2
            c13 += xa1 * xb3
            c20 += xa2 * xb0
            c21 += xa2 * xb1
            c22 += xa2 * xb2
            c23 += xa2 * xb3
            c30 += xa3 * xb0
            c31 += xa3 * xb1
            c32 += xa3 * xb2
            c33 += xa3 * xb3
        barrier()
        cur = 1 - cur

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    if r0 < m_rows and cc0 < n:
        y[r0 * n + cc0] = y[r0 * n + cc0] + c00
    if r0 < m_rows and cc1 < n:
        y[r0 * n + cc1] = y[r0 * n + cc1] + c01
    if r0 < m_rows and cc2 < n:
        y[r0 * n + cc2] = y[r0 * n + cc2] + c02
    if r0 < m_rows and cc3 < n:
        y[r0 * n + cc3] = y[r0 * n + cc3] + c03
    if r1 < m_rows and cc0 < n:
        y[r1 * n + cc0] = y[r1 * n + cc0] + c10
    if r1 < m_rows and cc1 < n:
        y[r1 * n + cc1] = y[r1 * n + cc1] + c11
    if r1 < m_rows and cc2 < n:
        y[r1 * n + cc2] = y[r1 * n + cc2] + c12
    if r1 < m_rows and cc3 < n:
        y[r1 * n + cc3] = y[r1 * n + cc3] + c13
    if r2 < m_rows and cc0 < n:
        y[r2 * n + cc0] = y[r2 * n + cc0] + c20
    if r2 < m_rows and cc1 < n:
        y[r2 * n + cc1] = y[r2 * n + cc1] + c21
    if r2 < m_rows and cc2 < n:
        y[r2 * n + cc2] = y[r2 * n + cc2] + c22
    if r2 < m_rows and cc3 < n:
        y[r2 * n + cc3] = y[r2 * n + cc3] + c23
    if r3 < m_rows and cc0 < n:
        y[r3 * n + cc0] = y[r3 * n + cc0] + c30
    if r3 < m_rows and cc1 < n:
        y[r3 * n + cc1] = y[r3 * n + cc1] + c31
    if r3 < m_rows and cc2 < n:
        y[r3 * n + cc2] = y[r3 * n + cc2] + c32
    if r3 < m_rows and cc3 < n:
        y[r3 * n + cc3] = y[r3 * n + cc3] + c33


def _pf_gemm_geglu_kernel_v2h(
    act: _FP, xn: _FP, w: _HP, m_rows_i64: Int64, k_i64: Int64, n_ff_i64: Int64
):
    """The f16-resident-weight GeGLU twin: `w` is the resident `[2*n_ff, k]` gate-THEN-up
    concatenation in FLOAT16; `act[M,n_ff] = gelu_pytorch_tanh(xn @ W_gate^T) * (xn @ W_up^T)`
    with f32 staging/accumulation — `_pf_gemm_geglu_kernel_v2`'s structure with the width-4
    Float16 B loads of the `_v2h` family."""
    var m_rows = Int(m_rows_i64)
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    comptime BM = _G2_BM
    comptime BN = _G2_BN
    comptime BK = _G2_BK
    comptime TM = _G2_TM
    comptime TN = _G2_TN
    comptime APAD = _G2_APAD
    comptime BPAD = _G2_BPAD

    var a0 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var a1 = stack_allocation[BM * APAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bg0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bg1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bu0 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()
    var bu1 = stack_allocation[BK * BPAD, DType.float32, address_space = AddressSpace.SHARED]()

    var n_tile_cols = (n_ff + BN - 1) // BN
    var tile_col = Int(block_idx.x) % n_tile_cols
    var tile_row = Int(block_idx.x) // n_tile_cols
    var block_row = tile_row * BM
    var block_col = tile_col * BN

    var tid = Int(thread_idx.x)
    var ty = tid // (BN // TN)
    var tx = tid % (BN // TN)

    var lr = tid // 4
    var lc = (tid % 4) * 4

    var n_steps = (k + BK - 1) // BK

    var g00 = Float32(0.0)
    var g01 = Float32(0.0)
    var g02 = Float32(0.0)
    var g03 = Float32(0.0)
    var g10 = Float32(0.0)
    var g11 = Float32(0.0)
    var g12 = Float32(0.0)
    var g13 = Float32(0.0)
    var g20 = Float32(0.0)
    var g21 = Float32(0.0)
    var g22 = Float32(0.0)
    var g23 = Float32(0.0)
    var g30 = Float32(0.0)
    var g31 = Float32(0.0)
    var g32 = Float32(0.0)
    var g33 = Float32(0.0)
    var u00 = Float32(0.0)
    var u01 = Float32(0.0)
    var u02 = Float32(0.0)
    var u03 = Float32(0.0)
    var u10 = Float32(0.0)
    var u11 = Float32(0.0)
    var u12 = Float32(0.0)
    var u13 = Float32(0.0)
    var u20 = Float32(0.0)
    var u21 = Float32(0.0)
    var u22 = Float32(0.0)
    var u23 = Float32(0.0)
    var u30 = Float32(0.0)
    var u31 = Float32(0.0)
    var u32 = Float32(0.0)
    var u33 = Float32(0.0)

    var gr0 = block_row + lr
    if gr0 < m_rows and lc + 3 < k:
        var va = _ld4(xn, gr0 * k + lc)
        a0[lr * APAD + lc + 0] = va[0]
        a0[lr * APAD + lc + 1] = va[1]
        a0[lr * APAD + lc + 2] = va[2]
        a0[lr * APAD + lc + 3] = va[3]
    elif gr0 < m_rows:
        for e in range(4):
            a0[lr * APAD + lc + e] = xn[gr0 * k + lc + e] if lc + e < k else Float32(0.0)
    else:
        for e in range(4):
            a0[lr * APAD + lc + e] = Float32(0.0)
    var wr0 = block_col + lr
    if wr0 < n_ff and lc + 3 < k:
        var vg = w.load[width=4](wr0 * k + lc)
        var vu = w.load[width=4]((n_ff + wr0) * k + lc)
        bg0[(lc + 0) * BPAD + lr] = Float32(vg[0])
        bg0[(lc + 1) * BPAD + lr] = Float32(vg[1])
        bg0[(lc + 2) * BPAD + lr] = Float32(vg[2])
        bg0[(lc + 3) * BPAD + lr] = Float32(vg[3])
        bu0[(lc + 0) * BPAD + lr] = Float32(vu[0])
        bu0[(lc + 1) * BPAD + lr] = Float32(vu[1])
        bu0[(lc + 2) * BPAD + lr] = Float32(vu[2])
        bu0[(lc + 3) * BPAD + lr] = Float32(vu[3])
    elif wr0 < n_ff:
        for e in range(4):
            var ge = Float32(w[wr0 * k + lc + e]) if lc + e < k else Float32(0.0)
            var ue = Float32(w[(n_ff + wr0) * k + lc + e]) if lc + e < k else Float32(0.0)
            bg0[(lc + e) * BPAD + lr] = ge
            bu0[(lc + e) * BPAD + lr] = ue
    else:
        for e in range(4):
            bg0[(lc + e) * BPAD + lr] = Float32(0.0)
            bu0[(lc + e) * BPAD + lr] = Float32(0.0)
    barrier()

    var cur = 0
    for step in range(n_steps):
        var ns = step + 1
        if ns < n_steps:
            var ngc = ns * BK + lc
            var agr = block_row + lr
            var wgr = block_col + lr
            if cur == 0:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a1[lr * APAD + lc + 0] = va[0]
                    a1[lr * APAD + lc + 1] = va[1]
                    a1[lr * APAD + lc + 2] = va[2]
                    a1[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a1[lr * APAD + lc + e] = Float32(0.0)
                if wgr < n_ff and ngc + 3 < k:
                    var vg = w.load[width=4](wgr * k + ngc)
                    var vu = w.load[width=4]((n_ff + wgr) * k + ngc)
                    bg1[(lc + 0) * BPAD + lr] = Float32(vg[0])
                    bg1[(lc + 1) * BPAD + lr] = Float32(vg[1])
                    bg1[(lc + 2) * BPAD + lr] = Float32(vg[2])
                    bg1[(lc + 3) * BPAD + lr] = Float32(vg[3])
                    bu1[(lc + 0) * BPAD + lr] = Float32(vu[0])
                    bu1[(lc + 1) * BPAD + lr] = Float32(vu[1])
                    bu1[(lc + 2) * BPAD + lr] = Float32(vu[2])
                    bu1[(lc + 3) * BPAD + lr] = Float32(vu[3])
                elif wgr < n_ff:
                    for e in range(4):
                        var ge = Float32(w[wgr * k + ngc + e]) if ngc + e < k else Float32(0.0)
                        var ue = Float32(w[(n_ff + wgr) * k + ngc + e]) if ngc + e < k else Float32(0.0)
                        bg1[(lc + e) * BPAD + lr] = ge
                        bu1[(lc + e) * BPAD + lr] = ue
                else:
                    for e in range(4):
                        bg1[(lc + e) * BPAD + lr] = Float32(0.0)
                        bu1[(lc + e) * BPAD + lr] = Float32(0.0)
            else:
                if agr < m_rows and ngc + 3 < k:
                    var va = _ld4(xn, agr * k + ngc)
                    a0[lr * APAD + lc + 0] = va[0]
                    a0[lr * APAD + lc + 1] = va[1]
                    a0[lr * APAD + lc + 2] = va[2]
                    a0[lr * APAD + lc + 3] = va[3]
                elif agr < m_rows:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = xn[agr * k + ngc + e] if ngc + e < k else Float32(0.0)
                else:
                    for e in range(4):
                        a0[lr * APAD + lc + e] = Float32(0.0)
                if wgr < n_ff and ngc + 3 < k:
                    var vg = w.load[width=4](wgr * k + ngc)
                    var vu = w.load[width=4]((n_ff + wgr) * k + ngc)
                    bg0[(lc + 0) * BPAD + lr] = Float32(vg[0])
                    bg0[(lc + 1) * BPAD + lr] = Float32(vg[1])
                    bg0[(lc + 2) * BPAD + lr] = Float32(vg[2])
                    bg0[(lc + 3) * BPAD + lr] = Float32(vg[3])
                    bu0[(lc + 0) * BPAD + lr] = Float32(vu[0])
                    bu0[(lc + 1) * BPAD + lr] = Float32(vu[1])
                    bu0[(lc + 2) * BPAD + lr] = Float32(vu[2])
                    bu0[(lc + 3) * BPAD + lr] = Float32(vu[3])
                elif wgr < n_ff:
                    for e in range(4):
                        var ge = Float32(w[wgr * k + ngc + e]) if ngc + e < k else Float32(0.0)
                        var ue = Float32(w[(n_ff + wgr) * k + ngc + e]) if ngc + e < k else Float32(0.0)
                        bg0[(lc + e) * BPAD + lr] = ge
                        bu0[(lc + e) * BPAD + lr] = ue
                else:
                    for e in range(4):
                        bg0[(lc + e) * BPAD + lr] = Float32(0.0)
                        bu0[(lc + e) * BPAD + lr] = Float32(0.0)

        var acur = a0 if cur == 0 else a1
        var bgcur = bg0 if cur == 0 else bg1
        var bucur = bu0 if cur == 0 else bu1
        for kk in range(BK):
            var xa0 = acur[(ty * TM + 0) * APAD + kk]
            var xa1 = acur[(ty * TM + 1) * APAD + kk]
            var xa2 = acur[(ty * TM + 2) * APAD + kk]
            var xa3 = acur[(ty * TM + 3) * APAD + kk]
            var xg0 = bgcur[kk * BPAD + tx]
            var xg1 = bgcur[kk * BPAD + tx + 16]
            var xg2 = bgcur[kk * BPAD + tx + 32]
            var xg3 = bgcur[kk * BPAD + tx + 48]
            var xu0 = bucur[kk * BPAD + tx]
            var xu1 = bucur[kk * BPAD + tx + 16]
            var xu2 = bucur[kk * BPAD + tx + 32]
            var xu3 = bucur[kk * BPAD + tx + 48]
            g00 += xa0 * xg0
            g01 += xa0 * xg1
            g02 += xa0 * xg2
            g03 += xa0 * xg3
            g10 += xa1 * xg0
            g11 += xa1 * xg1
            g12 += xa1 * xg2
            g13 += xa1 * xg3
            g20 += xa2 * xg0
            g21 += xa2 * xg1
            g22 += xa2 * xg2
            g23 += xa2 * xg3
            g30 += xa3 * xg0
            g31 += xa3 * xg1
            g32 += xa3 * xg2
            g33 += xa3 * xg3
            u00 += xa0 * xu0
            u01 += xa0 * xu1
            u02 += xa0 * xu2
            u03 += xa0 * xu3
            u10 += xa1 * xu0
            u11 += xa1 * xu1
            u12 += xa1 * xu2
            u13 += xa1 * xu3
            u20 += xa2 * xu0
            u21 += xa2 * xu1
            u22 += xa2 * xu2
            u23 += xa2 * xu3
            u30 += xa3 * xu0
            u31 += xa3 * xu1
            u32 += xa3 * xu2
            u33 += xa3 * xu3
        barrier()
        cur = 1 - cur

    var r0 = block_row + ty * TM + 0
    var r1 = block_row + ty * TM + 1
    var r2 = block_row + ty * TM + 2
    var r3 = block_row + ty * TM + 3
    var cc0 = block_col + tx
    var cc1 = cc0 + 16
    var cc2 = cc0 + 32
    var cc3 = cc0 + 48
    if r0 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g00 + Float32(0.044715) * g00 * g00 * g00)
        act[r0 * n_ff + cc0] = Float32(0.5) * g00 * (Float32(1.0) + tanh(inn)) * u00
    if r0 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g01 + Float32(0.044715) * g01 * g01 * g01)
        act[r0 * n_ff + cc1] = Float32(0.5) * g01 * (Float32(1.0) + tanh(inn)) * u01
    if r0 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g02 + Float32(0.044715) * g02 * g02 * g02)
        act[r0 * n_ff + cc2] = Float32(0.5) * g02 * (Float32(1.0) + tanh(inn)) * u02
    if r0 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g03 + Float32(0.044715) * g03 * g03 * g03)
        act[r0 * n_ff + cc3] = Float32(0.5) * g03 * (Float32(1.0) + tanh(inn)) * u03
    if r1 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g10 + Float32(0.044715) * g10 * g10 * g10)
        act[r1 * n_ff + cc0] = Float32(0.5) * g10 * (Float32(1.0) + tanh(inn)) * u10
    if r1 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g11 + Float32(0.044715) * g11 * g11 * g11)
        act[r1 * n_ff + cc1] = Float32(0.5) * g11 * (Float32(1.0) + tanh(inn)) * u11
    if r1 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g12 + Float32(0.044715) * g12 * g12 * g12)
        act[r1 * n_ff + cc2] = Float32(0.5) * g12 * (Float32(1.0) + tanh(inn)) * u12
    if r1 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g13 + Float32(0.044715) * g13 * g13 * g13)
        act[r1 * n_ff + cc3] = Float32(0.5) * g13 * (Float32(1.0) + tanh(inn)) * u13
    if r2 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g20 + Float32(0.044715) * g20 * g20 * g20)
        act[r2 * n_ff + cc0] = Float32(0.5) * g20 * (Float32(1.0) + tanh(inn)) * u20
    if r2 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g21 + Float32(0.044715) * g21 * g21 * g21)
        act[r2 * n_ff + cc1] = Float32(0.5) * g21 * (Float32(1.0) + tanh(inn)) * u21
    if r2 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g22 + Float32(0.044715) * g22 * g22 * g22)
        act[r2 * n_ff + cc2] = Float32(0.5) * g22 * (Float32(1.0) + tanh(inn)) * u22
    if r2 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g23 + Float32(0.044715) * g23 * g23 * g23)
        act[r2 * n_ff + cc3] = Float32(0.5) * g23 * (Float32(1.0) + tanh(inn)) * u23
    if r3 < m_rows and cc0 < n_ff:
        var inn = Float32(0.7978845608028654) * (g30 + Float32(0.044715) * g30 * g30 * g30)
        act[r3 * n_ff + cc0] = Float32(0.5) * g30 * (Float32(1.0) + tanh(inn)) * u30
    if r3 < m_rows and cc1 < n_ff:
        var inn = Float32(0.7978845608028654) * (g31 + Float32(0.044715) * g31 * g31 * g31)
        act[r3 * n_ff + cc1] = Float32(0.5) * g31 * (Float32(1.0) + tanh(inn)) * u31
    if r3 < m_rows and cc2 < n_ff:
        var inn = Float32(0.7978845608028654) * (g32 + Float32(0.044715) * g32 * g32 * g32)
        act[r3 * n_ff + cc2] = Float32(0.5) * g32 * (Float32(1.0) + tanh(inn)) * u32
    if r3 < m_rows and cc3 < n_ff:
        var inn = Float32(0.7978845608028654) * (g33 + Float32(0.044715) * g33 * g33 * g33)
        act[r3 * n_ff + cc3] = Float32(0.5) * g33 * (Float32(1.0) + tanh(inn)) * u33


# ── the tensor-core prefill-attention lever's pack / unpack helpers (2026-08-24) ──────────
# The strided-batched cuBLAS QK^T wants Q as [h_q, m, d] f16 (head-major, contiguous per
# head) but the tiled chain holds q_rot as [m, h_q*d] f32 (position-major). `_pf_q_pack_hm_f16`
# does that transpose+narrow; `_pf_attn_unpack_hm_f32` is the inverse for the PV output
# (head-major [h_q, m, d] f32 back to position-major [m, h_q*d] f32 for o_proj). Both are
# pure data movement, elementwise-exact.

def _pf_q_pack_hm_f16(
    q16: _HP, q_rot: _FP, m_rows_i64: Int64, h_q_i64: Int64, d_head_i64: Int64,
    scale: Float32,
):
    """q16[h, r, e] = Float16(q_rot[r, h*d + e] * scale); total h_q*m*d elements, one per
    thread. The attention scale rides the Q pack (pre-scaled Q into the QK^T GEMM = scaled
    scores, the SIMT kernel's `s *= scale` at no extra pass).
    `grid_dim = ceil(h_q*m*d / _TG)`, `block_dim = _TG`."""
    var m_rows = Int(m_rows_i64)
    var h_q = Int(h_q_i64)
    var d_head = Int(d_head_i64)
    var idx = Int(block_idx.x) * _TG + Int(thread_idx.x)
    var total = h_q * m_rows * d_head
    if idx >= total:
        return
    var md = m_rows * d_head
    var h = idx // md
    var rem = idx % md
    var r = rem // d_head
    var e = rem % d_head
    q16[idx] = Float16(q_rot[r * (h_q * d_head) + h * d_head + e] * scale)


def _pf_attn_unpack_hm_f32(
    attn: _FP, o32: _FP, m_rows_i64: Int64, h_q_i64: Int64, d_head_i64: Int64,
):
    """attn[r, h*d + e] = o32[h, r, e]; total h_q*m*d elements, one per thread (the inverse
    of `_pf_q_pack_hm_f16` but f32->f32). `grid_dim = ceil(h_q*m*d / _TG)`, `block_dim = _TG`."""
    var m_rows = Int(m_rows_i64)
    var h_q = Int(h_q_i64)
    var d_head = Int(d_head_i64)
    var idx = Int(block_idx.x) * _TG + Int(thread_idx.x)
    var total = h_q * m_rows * d_head
    if idx >= total:
        return
    var md = m_rows * d_head
    var h = idx // md
    var rem = idx % md
    var r = rem // d_head
    var e = rem % d_head
    attn[r * (h_q * d_head) + h * d_head + e] = o32[idx]


# ── FRONT-1 prefill levers (2026-09-15, the pp1024 / RAG-4096 gap round) ─────────────────
#
# The A100 pp1024 layer decomposition (nsys, m=1024 one-pass, 28 layers) put the TC
# attention's masked softmax at the TOP of the non-GEMM memory-traffic table: the shim's
# `_attn_softmax_mask_kernel` walks each score row THREE times (max pass, sum pass,
# normalize pass) over the FULL `n_keys` width, so at m=1024 it moves 3 x 117 MB of f32
# scores + 59 MB of f16 P per layer = 411 MB/layer = 11.5 GB across the prefill, ~7 ms of
# the 82 ms wall. Two independent facts make that traffic reducible without touching the
# maths:
#
#   * the row is only ~half valid — row `p` of a one-pass tile at `pos_base=0` attends keys
#     `0 .. p`, so looping to the row's own `qpos` instead of `n_keys` halves the reads;
#   * one global read suffices — cache the valid prefix in threadgroup shared memory (a
#     comptime-bounded 4096-float row = 16 KB/block, 8 blocks/SM at 256 threads, no
#     occupancy loss) and run max/sum/normalize off the cached copy, writing the exp'd
#     value back into the same slot so `exp` is evaluated ONCE per element instead of twice.
#
# Result: 1 bounded f32 read + 1 full f16 write per row (~117 MB/layer) — the same values,
# the same online-free three-stage softmax recurrence, ~3.5x less traffic. `_SM1P_MAX_KEYS`
# is the dispatch-side contract: rows wider than that stay on the shim kernel (the caller
# checks it at runtime, so a long-context tile degrades rather than overflows shared).


comptime _SM1P_MAX_KEYS: Int = 4096
"""Shared-memory row cache capacity for `_pf_attn_softmax_mask_1p` (floats, so 16 KB of the
A100's 48 KB static shared budget per block). The session dispatches the kernel only when
`n_keys <= _SM1P_MAX_KEYS` and keeps the shim's 3-pass kernel above that — a runtime check
because `n_keys = pos + m` grows with the chunk index of a multi-chunk prefill."""


def _pf_attn_softmax_mask_1p(
    s32: _FP, p16: _HP, n_keys_i64: Int64, m_rows_i64: Int64, pos_base_i64: Int64,
    window_i64: Int64,
):
    """Single-read masked causal(+window) softmax over one score row -> f16 attention
    weights. Row `r` = query head `r / m_rows`, tile position `p = r % m_rows`, global
    position `qpos = pos_base + p`; key `j` is attended iff `j <= qpos` AND (`window <= 0`
    OR `j >= qpos + 1 - window`) — the shim kernel's predicate, verbatim, so the two are
    drop-in equivalents and the f16 P they produce is elementwise identical for the same
    f32 scores.

    `grid_dim = h_q * m_rows`, `block_dim = _TG`. REQUIRES `n_keys <= _SM1P_MAX_KEYS`
    (checked at the dispatch site)."""
    var n_keys = Int(n_keys_i64)
    var m_rows = Int(m_rows_i64)
    var pos_base = Int(pos_base_i64)
    var window = Int(window_i64)
    var row = Int(block_idx.x)
    var p = row % m_rows
    var qpos = pos_base + p
    var lo = 0
    if window > 0:
        lo = qpos + 1 - window
    if lo < 0:
        lo = 0
    var hi = qpos
    if hi > n_keys - 1:
        hi = n_keys - 1
    var count = hi - lo + 1
    if count < 0:
        count = 0
    var tid = Int(thread_idx.x)
    var base = row * n_keys

    var rowc = stack_allocation[
        _SM1P_MAX_KEYS, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var red = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()

    # ── pass 1: cache the valid prefix in shared, track this thread's partial max ──
    var mx = Float32(-1.0e30)
    var j = tid
    while j < count:
        var v = s32[base + lo + j]
        rowc[j] = v
        if v > mx:
            mx = v
        j += _TG
    # warp max via the same shuffle_xor ladder `residentk.kernels`' argmax uses
    var off = UInt32(_LANES // 2)
    while off > 0:
        var other = _shuffle_xor(mx, off)
        if other > mx:
            mx = other
        off //= 2
    var lane = tid % _LANES
    var sub = tid // _LANES
    if lane == 0:
        red[sub] = mx
    barrier()
    # 8 shared reads per thread, every thread computes the block max itself (no broadcast)
    var row_max = Float32(-1.0e30)
    for g in range(_SUBS):
        if red[g] > row_max:
            row_max = red[g]
    # `red` is reused for the sum below — every thread must have consumed the max first.
    barrier()

    # ── pass 2: exp(v - max) INTO the cached slot + this thread's partial sum ──
    var sum = Float32(0.0)
    j = tid
    while j < count:
        var e = exp(rowc[j] - row_max)
        rowc[j] = e
        sum += e
        j += _TG
    var sum_group = _warp_sum(sum)
    if lane == 0:
        red[sub] = sum_group
    barrier()
    var row_sum = Float32(0.0)
    for g in range(_SUBS):
        row_sum += red[g]
    var inv = Float32(0.0)
    if row_sum > 0.0:
        inv = Float32(1.0) / row_sum

    # ── pass 3: normalize from shared, write the FULL row in absolute key order — the
    #    masked keys (below `lo` for a windowed layer, above `hi` for the causal tail) get
    #    an exact zero, which is what the PV GEMM must see for the keys this query does not
    #    attend. Absolute indexing keeps the windowed case (lo > 0) inside the row. ──
    j = tid
    while j < n_keys:
        var v = Float32(0.0)
        var rel = j - lo
        if rel >= 0 and rel < count:
            v = rowc[rel] * inv
        p16[base + j] = Float16(v)
        j += _TG


def _pf_rmsnorm_rows_f16_kernel(
    xn16: _HP, x: _FP, gamma: _FP, k_i64: Int64, eps: Float32, m_rows_i64: Int64,
):
    """`residentk.kernels._pf_rmsnorm_rows_kernel` with an f16 output — the producer half of
    the A-convert elimination (`-D ALGENTA_7B_PF_F16NORM`): the TC projection GEMM converts
    this f32 row block to f16 on every call anyway, so writing the f16 here removes one full
    read+write pass over `[m, d_model]` per norm per layer and lands on the IDENTICAL rounded
    value (f32 arithmetic in-kernel, one f32->f16 rounding at the store, exactly the
    rounding the shim's convert kernel would have applied to the same f32).

    Same grid/block contract as the f32 twin: `grid_dim = m_rows`, `block_dim = _TG`, the
    same two-level SIMD-group sum-of-squares reduction."""
    var k = Int(k_i64)
    var m_rows = Int(m_rows_i64)
    var grp = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var m = Int(block_idx.x)
    if m >= m_rows:
        return
    var row = m * k
    var tid = Int(thread_idx.x)
    var lane = tid % _LANES
    var sub = tid // _LANES

    var ss = Float32(0.0)
    var i = tid
    while i < k:
        var v = x[row + i]
        ss += v * v
        i += _TG
    var ss_group = _warp_sum(ss)
    if lane == 0:
        grp[sub] = ss_group
    barrier()
    var ss_total = Float32(0.0)
    for g in range(_SUBS):
        ss_total += grp[g]
    var inv = 1.0 / sqrt(ss_total / Float32(k) + eps)

    var s = tid
    while s < k:
        xn16[row + s] = Float16(x[row + s] * inv * gamma[s])
        s += _TG


def _pf_swiglu_rows_f16_kernel(act16: _HP, gu16: _HP, total_i64: Int64, n_ff_i64: Int64):
    """`residentk.tc_shim_bridge._pf_swiglu_rows_kernel` with BOTH operands f16 — the
    epilogue half of `-D ALGENTA_7B_PF_F16MLP`: the gate/up GEMM writes its `[m, 2*d_ff]`
    result as f16 C and this combine reads that f16 and writes the f16 A the down_proj GEMM
    consumes directly (no shim convert pass). Same `swish(gate) * up` expression and the same
    f32 intermediate arithmetic as the f32 twin; the difference is where the operands are
    rounded, which is why the lever carries its own token-identity gate.

    `act16[row, j] = swish(gu16[row, j]) * gu16[row, n_ff + j]` over `m * n_ff` outputs.
    Grid: `ceil(m * n_ff / _TG)`, block `_TG`."""
    var total = Int(total_i64)
    var n_ff = Int(n_ff_i64)
    var i = Int(block_idx.x) * Int(block_dim.x) + Int(thread_idx.x)
    if i < total:
        var row = i // n_ff
        var j = i - row * n_ff
        var g = Float32(gu16[row * 2 * n_ff + j])
        var u = Float32(gu16[row * 2 * n_ff + n_ff + j])
        act16[i] = Float16((g / (1.0 + exp(-g))) * u)


# ── FRONT-3 prefill levers (2026-09-15, the pp1024 / RAG-4096 TensorRT-LLM gap round) ─────
#
# The A100 layer decomposition of the adopted _c8 arm (~/trtllm/front1/nsys_decomposition.json)
# against TensorRT-LLM 1.2.1's kernel mix (~/trtllm/front1/trtllm_kernel_mix.txt) leaves three
# per-layer gaps once the projections are accounted for, and this file carries the two Mojo
# halves (the third, fused causal flash attention, is a tc_shim.cu kernel because it needs the
# HMMA surface Mojo 1.0.0 does not expose):
#
#   * bias + RoPE + KV-write, ours 92.5 us/layer (`_qkv_bias_add_rows_kernel` 31.6 +
#     `_pf_ropewrt_kernel` 61.0) vs TRT-LLM's ONE `applyBiasRopeUpdateKVCacheV2` at 21.7
#     us/call. The bias pass is a pure extra round trip over the widest tensor in the layer —
#     it reads and writes `[m, n_qkv]` f32 (21 MB + 21 MB at m=1024) only so the RoPE kernel
#     can read the same bytes back one launch later. `_pf_biasropewrt_kernel` below folds the
#     add into the read, which is BIT-EXACT: both forms evaluate one f32 addition of the same
#     two f32 operands, and the two-pass form rounded that sum to f32 in `pf_qkv` before the
#     RoPE kernel read it, so there is no second rounding point to diverge at.
#   * the SwiGLU epilogue's `exp`: carried by the shim's `__expf` twin
#     (`residentk.tc_shim_bridge._tc_swiglu_f16_fastexp`, `-D ALGENTA_7B_PF_FASTEXP`), not by a
#     Mojo kernel here, because ex2.approx.ftz is a single PTX instruction and the pinned
#     toolchain exposes no inline-asm hatch to reach it from Mojo.
#
# `_pf_fill_scale_kernel` is the third piece of lever 1's plumbing: the fused attention kernel
# takes the attention scale as a DEVICE POINTER rather than a float argument (no repo-proven
# float marshalling through `external_call`, and an ABI mismatch there would be a silent numeric
# bug), so the session writes its scale into a 1-element f32 buffer once at staging time.


def _pf_biasropewrt_kernel(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, bias: _FP, qn_w: _FP, kn_w: _FP,
    cos_t: _FP, sin_t: _FP, pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64,
    d_head_i64: Int64, eps: Float32, m_rows_i64: Int64, qk_norm_i64: Int64,
):
    """`residentk.kernels._pf_ropewrt_kernel` with the 7B q/k/v attention-bias add FOLDED IN —
    `-D ALGENTA_7B_PF_BIASROPE`, the one-pass replacement for the `_qkv_bias_add_rows_kernel`
    + `_pf_ropewrt_kernel` pair (TensorRT-LLM's `applyBiasRopeUpdateKVCacheV2` does the same
    three jobs in one launch).

    Bit-exact against the pair it replaces, by construction: the bias pass computes
    `pf_qkv[i] = pf_qkv[i] + bias[i % n_qkv]` in f32 and stores it back to the f32 `pf_qkv`,
    and this kernel computes the identical single f32 addition at the identical point in the
    expression — `v = qkv[src_off] + bias[src_off - row_qkv]` — so the value the q/k norm,
    the RoPE rotation and the V cache write each see is the same f32 bit pattern either way.
    `src_off - row_qkv` IS the pair's `i % n_qkv`: `src_off = row_qkv + col` with
    `0 <= col < n_qkv` by construction, for the Q, K and V sections alike.

    Same grid/block contract and the same shared-memory reduction as the twin it replaces:
    `grid_dim = (h_q + h_kv) * m_rows`, `block_dim = d_head`, `block_idx.x` flattening
    `(b, m)` as `b = block_idx.x % (h_q + h_kv)`. Dispatched INSTEAD OF the bias kernel, never
    in addition to it — the session skips step 2b under this flag."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives.
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var d_head = Int(d_head_i64)
    var m_rows = Int(m_rows_i64)
    var qk_norm = Int(qk_norm_i64)
    var n_units = h_q + h_kv
    var b = Int(block_idx.x) % n_units
    var m = Int(block_idx.x) // n_units
    if m >= m_rows:
        return
    var pos = pos_base + m
    var n_qkv = h_q * d_head + 2 * h_kv * d_head
    var row_qkv = m * n_qkv
    var n_q = h_q * d_head
    var row_q_rot = m * n_q

    var xs = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var red = stack_allocation[
        RESIDENT_MAX_HEAD_DIM, DType.float32, address_space = AddressSpace.SHARED
    ]()
    var e = Int(thread_idx.x)
    var is_q = b < h_q
    var head = b if is_q else b - h_q

    var src_off = row_qkv + (head * d_head + e if is_q else (h_q + head) * d_head + e)
    # ── the folded bias add: the ONLY difference from `_pf_ropewrt_kernel` ──
    var v = qkv[src_off] + bias[src_off - row_qkv]
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
            var kb = (pos * h_kv + head) * d_head
            ck[kb + e] = o0
            ck[kb + e + n_pairs] = o1

    if not is_q:
        var voff = (h_q + h_kv + head) * d_head + e
        cv[(pos * h_kv + head) * d_head + e] = qkv[row_qkv + voff] + bias[voff]


# ── FRONT 5 lever 2: the vectorized, barrier-free bias+RoPE+KV-write ──────────────────────
comptime _RV_D: Int = 128
"""The ONLY head_dim `_pf_biasropewrt_vec_kernel` implements; the session host-checks it and
keeps `_pf_biasropewrt_kernel` for anything else. Fixed rather than derived so the shift
constants below are compile-time and the kernel contains no integer division at all."""
comptime _RV_PAIRS: Int = _RV_D // 2
"""RoPE pairs per head (64): dimension `e` rotates with dimension `e + _RV_PAIRS`."""
comptime _RV_V4: Int = _RV_PAIRS // 4
"""float4 groups per head's RoPE half (16) — one task per group, so 16 threads cover a head."""
comptime _RV_V4SH: Int = 4
"""log2(_RV_V4). _RV_V4 is 16 by construction, so the task decode is a shift and a mask."""
comptime _RV_DV4: Int = _RV_D // 4
"""float4 groups per head for the V copy (32), which has no pairing to halve."""
comptime _RV_DV4SH: Int = 5
"""log2(_RV_DV4)."""
comptime _RV_TG: Int = 256
"""Threads per block: 8 warps, one row per block. At the 7B shape that is 512 RoPE tasks and
128 V tasks, i.e. two and one strided iterations — enough memory in flight per SM to stream,
without the 32,768 one-head-per-block launches the scalar kernel needs."""


def _pf_biasropewrt_vec_kernel(
    q_rot: _FP, ck: _FP, cv: _FP, qkv: _FP, bias: _FP, cos_t: _FP, sin_t: _FP,
    pos_base_i64: Int64, h_q_i64: Int64, h_kv_i64: Int64, m_rows_i64: Int64,
):
    """`_pf_biasropewrt_kernel` with the shared-memory staging, the barrier and the scalar
    4-byte accesses removed — `-D ALGENTA_7B_PF_ROPEVEC`, FRONT 5 lever 2.

    WHY. The A100 decomposition puts this family at 62.6 us/layer for ~40 MB of traffic =
    ~43% of the 1555 GB/s roof, against TensorRT-LLM's fused `applyBiasRopeUpdateKVCacheV2` at
    21.7 us. Its floor is pure traffic (40 MB = 25.7 us), so ~37 us/layer — 3.3 ms over a
    RAG-4096 prefill — is not bandwidth, it is the kernel's own shape. Two things cost that:

      1. A SHARED-MEMORY ROUND TRIP AND A BARRIER THAT BUY NOTHING ON THIS MODEL. The scalar
         kernel gives thread `e` element `e`, but RoPE pairs element `e` with element `e + 64`,
         so it stages all 128 elements into `xs` and barriers to let thread `e < 64` read both
         halves. That is necessary only when a q/k norm runs, because the norm's sum-of-squares
         reduction needs every element in shared anyway. Qwen2.5-7B has NO q/k norm
         (`qk_norm == 0`), so the staging exists purely to move a value 64 lanes sideways — and
         this kernel instead lets the thread that needs both halves LOAD both halves, which it
         was going to touch anyway. `xs`, `red`, their two barriers and the 128-thread
         half-idle tail all disappear.
      2. SCALAR 4-BYTE GLOBAL ACCESSES. `_pf_biasropewrt_kernel` reads `qkv[src_off]` and
         writes `q_rot[qb + e]` one Float32 at a time. This kernel uses `loadvec._ld4` /
         `_st4`, i.e. `load/store[width=4, alignment=16]`, which is the micro-autopsy's
         lever-0 fix: without the alignment annotation `width=4` lowers to FOUR scalar
         `ld.global.b32`, with it, to one `ld.global.v4.b32`. A quarter of the load and store
         instructions and of the address arithmetic for the same bytes.

    GRID. `grid_dim = m_rows`, `block_dim = _RV_TG` — one row per block, replacing
    `(h_q + h_kv) * m_rows` one-head blocks (32,768 of them at m=1024) with 1,024.

    BIT-EXACTNESS. The expression is the scalar kernel's verbatim, evaluated lane-wise:
    `a0 = qkv[e] + bias[e]`, `a1 = qkv[e+64] + bias[e+64]`, `o0 = a0*cos - a1*sin`,
    `o1 = a0*sin + a1*cos`, and the V write is `qkv[voff] + bias[voff]`. One f32 addition and
    the same two f32 multiply-adds per output, in the same order, on the same operands; SIMD
    lanes do not interact, so no reassociation is possible. The one thing that COULD move a bit
    is the backend contracting `a0*c - a1*s` into an FMA differently for vector than for scalar
    operands, which is why this arm goes through the token-identity gates rather than being
    asserted exact on the strength of the source text.

    DECLINED, never faked: the session keeps `_pf_biasropewrt_kernel` when `qk_norm != 0` (the
    norm's reduction genuinely needs the shared staging), when `d_head != _RV_D`, or when the
    row strides are not multiples of 4 elements — so the 16-byte alignment promise `_ld4`/`_st4`
    make is discharged by the caller, not assumed here."""
    var pos_base = Int(pos_base_i64)
    var h_q = Int(h_q_i64)
    var h_kv = Int(h_kv_i64)
    var m_rows = Int(m_rows_i64)
    var m = Int(block_idx.x)
    if m >= m_rows:
        return
    var pos = pos_base + m
    var n_qkv = (h_q + 2 * h_kv) * _RV_D
    var row_qkv = m * n_qkv
    var n_q = h_q * _RV_D
    var row_q_rot = m * n_q
    var n_rope = (h_q + h_kv) * _RV_V4
    var n_v = h_kv * _RV_DV4
    var tid = Int(thread_idx.x)

    # ── Q and K: bias add, RoPE rotation, and the write, one float4 pair-group per task.
    #    Task `t` decodes to head-unit `t >> _RV_V4SH` and float4 group `t & (_RV_V4-1)`; the
    #    first `h_q` units are Q and the rest are K, exactly the scalar kernel's `b < h_q`. ──
    var t = tid
    while t < n_rope:
        var unit = t >> _RV_V4SH
        var e0 = (t & (_RV_V4 - 1)) * 4
        var is_q = unit < h_q
        var head = unit if is_q else unit - h_q
        var src = row_qkv + (
            head * _RV_D + e0 if is_q else (h_q + head) * _RV_D + e0
        )
        var bsrc = src - row_qkv
        var a0 = _ld4(qkv, src) + _ld4(bias, bsrc)
        var a1 = _ld4(qkv, src + _RV_PAIRS) + _ld4(bias, bsrc + _RV_PAIRS)
        var cb = pos * _RV_PAIRS + e0
        var c = _ld4(cos_t, cb)
        var s = _ld4(sin_t, cb)
        var o0 = a0 * c - a1 * s
        var o1 = a0 * s + a1 * c
        if is_q:
            var qb = row_q_rot + head * _RV_D + e0
            _st4(q_rot, qb, o0)
            _st4(q_rot, qb + _RV_PAIRS, o1)
        else:
            var kb = (pos * h_kv + head) * _RV_D + e0
            _st4(ck, kb, o0)
            _st4(ck, kb + _RV_PAIRS, o1)
        t += _RV_TG

    # ── V: no rotation, just the folded bias add and the cache write. The scalar kernel does
    #    this from the K blocks; here it is its own task range so no thread waits on another. ──
    var u = tid
    while u < n_v:
        var head = u >> _RV_DV4SH
        var e0 = (u & (_RV_DV4 - 1)) * 4
        var voff = (h_q + h_kv + head) * _RV_D + e0
        _st4(
            cv, (pos * h_kv + head) * _RV_D + e0,
            _ld4(qkv, row_qkv + voff) + _ld4(bias, voff),
        )
        u += _RV_TG


def _pf_fill_scale_kernel(dst: _FP, s: Float32):
    """Write the session's attention scale into a 1-element device f32 buffer, once, at TC
    staging time. `residentk.tc_shim_bridge._tc_fa_causal_async` takes the scale as a device
    pointer rather than a float argument; this is the producer half of that contract.
    `grid_dim = 1`, `block_dim = 1`."""
    if Int(block_idx.x) == 0 and Int(thread_idx.x) == 0:
        dst[0] = s
