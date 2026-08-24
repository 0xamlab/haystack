"""
residentk.session_cuda_p3 — the packed3 (arithmetic-packed-int8) DECODE twin of the CUDA-native
resident session: `_CudaResidentQwen3P3` streams the four per-layer projection roles and the tied
lm_head at the packed3 layout's ~1.5833 B/weight instead of Float32's 4 B/weight, while prefill,
normalization, RoPE, attention and the KV cache stay BYTE-UNMODIFIED from
`residentk.session_cuda._CudaResidentQwen3`. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32, uint8-packed
backend: cuda
surfaces: none
golden_vectors: benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo
benchmark: benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point is private and every launch compile-time gated — the
same two defences `residentk.session_cuda`'s module docstring documents:

1. **Private.** Nothing in this file is public, so `apps/runtime/mojo_inventory.py` skips it, it
   never enters the runtime contract, and the generated dispatch never imports it. Today only
   `benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo` reaches it.
2. **Compile-time gated.** Every function here that issues an `enqueue_function` opens with
   `@parameter if not CUDA_SESSION_BUILD: return <shader_toolchain_absent>` — the SAME gate
   comptime `residentk.session_cuda` defines (`-D ALGENTA_GPU` conjuncted with `-D ALGENTA_CUDA`),
   imported, not re-decided. The constructor carries no gate and is instead protected
   structurally: the struct is constructed ONLY from inside a `@parameter if CUDA_SESSION_BUILD`
   branch.

What this session is FOR — decode = packed3, prefill = f32, stated as the split it is
-------------------------------------------------------------------------------------------
`REALRACE_RESULTS.md` established decode on this stack sits at its f32 bandwidth floor: 2.62 GB
of Float32 weights streamed per token, 54-91% of HBM peak per role. `residentk.kernels_packed3`
landed the kernel family that cuts that traffic: three unsigned int8 quants per Float32 word,
block-32 zero-point scale+zero, streamed through the ONE load path this toolchain streams at HBM
speed (128-bit `load[width=4]` on a Float32 pointer) and unpacked on-device with
`std.memory.bitcast`. This session wires that family into a resident session:

  * DECODE (`step_p3`) streams every projection weight as packed3 — 1.5833 B/weight
    (4/3 B/w packed words + 8/32 B/w block-32 f32 scale+zero pair), so the 0.6B's 2.38 GB of f32
    projection+lm_head weights become ~0.94 GB and per-token traffic ~1.18 GB all-in (the
    module docstring of `residentk.kernels_packed3` states the ledger math).
  * PREFILL (`prefill`) is delegated WHOLESALE to the inner f32 session — the compute-bound
    m_rows > 1 pass keeps the f32 v2 tiled GEMMs. A packed prefill GEMM is future work; this
    file deliberately does NOT attempt it.

THE TWIN SESSION MEMORY MODEL (documented, not hidden): because prefill stays f32 and the f32
prefill GEMMs read f32 weights, this session keeps BOTH formats resident — the inner f32
session's full Float32 weight set (2.38 GB at 0.6B) PLUS the packed3 decode twins (~0.94 GB):
~3.32 GB of weights total, plus the f32 KV cache. That is the price of a single session that
runs both arms; a decode-only packed arm could drop the f32 projection matrices later. The f32
embedding table stays resident in the inner session for the decode embed gather AND the f32
prefill's embed/lm_head; the packed3 twin of the tied table exists ONLY as lm_head weights here.

Kernel substitution table — `step` (f32) vs `step_p3` (packed3), per dispatch role
-------------------------------------------------------------------------------------------
| role                        | f32 session kernel            | this session dispatches            |
|-----------------------------|-------------------------------|------------------------------------|
| embed gather                | `_embed_row_kernel`           | UNCHANGED (embed stays f32)        |
| rmsnorm(ln1) + qkv proj     | `_norm_gemv_kernel`           | `_norm_gemv_kernel_p3` (packed3)   |
| qk_norm + RoPE + KV write   | `_qk_rope_write_kernel`       | UNCHANGED (f32 KV cache)           |
| attention                   | `_sdpa_kernel`                | UNCHANGED (f32 KV cache)           |
| o_proj + residual add       | `_gemv_accum_kernel`          | `_packed3_gemv_accum_kernel` (new) |
| rmsnorm(ln2) + gate/up/SwiGLU | `_norm_gemv2_swiglu_kernel` | `_norm_gemv2_swiglu_kernel_p3` (new) |
| down_proj + residual add    | `_gemv_accum_kernel`          | `_packed3_gemv_accum_kernel` (new) |
| final norm + lm_head + argmax | `_lmhead_argmax_kernel`     | `_lmhead_argmax_kernel_p3` (new)   |
| argmax reduce               | `_argmax_reduce_kernel`       | UNCHANGED                          |

The dispatch PLAN is byte-identical to the f32 chain: `1 + 6 * n_layers + 2` dispatches per
token = `residentk_dispatch_budget(n_layers)`, checked by the driver every step.

DEVIATION FROM THE CAMPAIGN BRIEF, recorded: the brief sketched all four projections and the
lm_head through `residentk.kernels_packed3._packed3_gemv_kernel`. That kernel is ASSIGN-only and
one-row-per-block — composing it for the session's ACCUMULATE roles (o_proj/down_proj fuse the
residual `+=`), the fused gate/up+SwiGLU role, and the logits-never-materialised lm_head+argmax
role would need scratch buffers PLUS extra add/swiglu/argmax dispatches, breaking the frozen
dispatch budget and adding per-token host cost. `step_p3` therefore keeps the f32 chain's
dispatch shape exactly by dispatching the three packed3 twins defined in THIS file, each derived
from its f32 twin by changing ONLY the weight load+dequant to the kernels_packed3 unpack — the
same derivation `_norm_gemv_kernel_p3` performed for the qkv role (its docstring names itself
"the structural mirror ... a session integration dispatches"). `_packed3_gemv_kernel` remains
the probe's correctness/bandwidth kernel and is NOT dispatched by this session.

The three new kernels, and the ONE rule they share with `residentk.kernels_packed3`
-------------------------------------------------------------------------------------------
Every scalar parameter is a fixed-width `Int64` (DevicePassable), widened back to `Int` once at
entry — Mojo 1.0.0 kernel-parameter discipline, `accel/launch.mojo`'s pattern. The weight stream
is typed Float32 (`_FP`) on purpose: it is read as Float32 WORDS (the only SIMD load this backend
streams at HBM speed) and reinterpreted AFTER the load with `bitcast[DType.uint8, 16]`.

THE v2/v3 TWINS: each of the three kernels (plus `residentk.kernels_packed3`'s qkv kernel)
has `_v2` and `_v3` twins in this arm. v2 changes ONLY the chunk loop's unpack —
`bitcast[DType.int32, 4]` word view + shift/AND byte extraction instead of the u8x16
byte-view lane selection, and the block-32 crossing classification hoisted out of the loop
(loop-invariant). Same integer quants, same dequant expression, same accumulation order, so
a v2 kernel computes bit-identical output to its v1 twin — the graph arm's gate driver diffs
the two token for token. v3 adds three interleaved accumulators (the 12 per-chunk products
split by element index mod 3, combined at loop end) — the dependent-add chain per chunk is
the latency wall the probe battery measured, and splitting it CHANGES accumulation order
(ulp-level deltas; the gate driver's G1 switches to the vs-f32 flip-reporting form for v3
builds, G0 stays hard). `residentk.session_cuda_p3_graph.P3_GRAPH_V2_KERNELS` /
`P3_GRAPH_V3_KERNELS` select which generation the captured graph dispatches; this file's
per-dispatch `step_p3` always dispatches the v1 bodies, so the diff runs graph-variant vs v1
on ONE session.

ACTIVATION TAIL CONTRACT: packed3 rows pad to `k_pack = ceil(k/12)*12` slots, and the padded
slots contribute EXACTLY zero because the activation side is zero there too. The two kernels
`residentk.kernels_packed3` ships handle that on their caller's side; the twins in THIS file
stage the activation into shared memory ZERO-FILLING the `k_pack - k` tail themselves, so
`step_p3` needs no padded device copies of `attn_out` / `act` / `hidden` (the buffers stay the
same sizes the f32 session allocates). `k_pack <= RESIDENT_MAX_D_MODEL` for every contract-legal
`k` (`residentk_dims_check`'s `stage_needed = max(d_model, h_q*d_head, d_ff)` bound plus both
staging tiers being multiples of 12), so the shared staging never overflows — the exact ceiling
argument `residentk.kernels_packed3`'s `_P3_STAGE` docstring makes.

Host pack flow (upload)
------------------------
`upload_globals` / `upload_layer` first forward every tensor to the INNER f32 session (its
proven `_narrow_into` / `_narrow_transposed_into` helpers — the f32 half is byte-identical to
`_CudaResidentQwen3`), then pack the SAME Float64 wire tensors — narrowed to Float32 exactly the
way the f32 path narrows them, so quantization error is measured against the identical values —
through `residentk.kernels_packed3._pack_f32_to_packed3` (the reference pack: pad K to a
multiple of 12, block-32 zero-point quant, padding slots take the rounded zero-point and
contribute exactly zero) and upload the packed words + scales + zeros buffers.

Build / compile verification (macOS build host, NVPTX ships in the toolchain, no GPU needed)
---------------------------------------------------------------------------------------------
The module compiles THROUGH the gate driver — the campaign's compile-verification form, which
also guarantees the kernels are actually LOWERED (an unreachable kernel would compile vacuously):

    mojo build -D ALGENTA_GPU -D ALGENTA_CUDA --target-accelerator sm_80 \
        -I mojo/engine benchmarks/llm_smoke/nvidia_race/qwen3_p3_session_cuda.mojo \
        -o /tmp/qwen3_p3_session_cuda_sm80
(same with `sm_89` for the L4/4090 lane; the object+link fallback recipe lives in the driver's
docstring, mirrored from `qwen3_serve_cuda.mojo`'s).
"""

from max.gpu.host import DeviceBuffer
from std.gpu import block_idx, grid_dim, thread_idx
from max.gpu import barrier  # Mojo 1.0.0: moved out of std.gpu
from max.gpu.memory import AddressSpace
from std.math import exp, sqrt
from std.memory import bitcast, stack_allocation
from std.origin import MutAnyOrigin
from residentk.contract import (
    RESIDENT_ERR_CONTEXT_FULL,
    RESIDENT_ERR_LAUNCH_FAILED,
    RESIDENT_ERR_UPLOAD_LENGTH,
    RESIDENT_OK,
    RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT,
    residentk_dispatch_budget,
)
from residentk.kernels import (
    _TG,
    _LANES,
    _SUBS,
    _NEG_HUGE,
    _embed_row_kernel,
    _qk_rope_write_kernel,
    _sdpa_kernel,
    _argmax_reduce_kernel,
)
from residentk.kernels_packed3 import (
    _P3_CHUNK,
    _P3_QUANTS_PER_WORD,
    _P3_BLOCK,
    _P3_STAGE,
    _norm_gemv_kernel_p3,
    _pack_f32_to_packed3,
    _p3_pack_from_f64,
    _p3_dequant_rows_kernel,
    _p3_words_per_row,
    _p3_blocks_per_row,
)
from residentk.kernels import (
    _pf_rmsnorm_rows_kernel,
    _pf_ropewrt_kernel,
    _pf_attn_tiled_kernel_simd,
    _qkv_bias_add_rows_kernel,
    _lmhead_argmax_kernel,
)
from residentk.kernels_prefill_attn_flash import (
    _PF_FLASH_NTHREADS,
    _PF_FLASH_ROWS_PER_BLOCK,
    _pf_attn_flash_kernel,
)
from residentk.kernels_prefill_attn_flash2 import (
    _pf_attn_flash2_kernel,
)
from residentk.kernels_prefill_f32 import (
    _pf_embed_rows_kernel,
)
from residentk.kernels_prefill_f32_v2 import (
    _G2_BM,
    _G2_BN,
    _G2_NTHREADS,
    _pf_gemm_assign_kernel_v2,
    _pf_gemm_accum_kernel_v2,
    _pf_gemm_swiglu_kernel_v2,
)
from residentk.session import (
    _LM_BLOCKS,
    _StepOut,
    _ceil_div,
)
from residentk.session_cuda import (
    CUDA_SESSION_BUILD,
    CUDA_PREFILL_TILE,
    CUDA_PREFILL_ONEPASS_B1,
    CUDA_PREFILL_FLASH_B1,
    CUDA_PREFILL_FLASH2_B1,
    _B1_PASS_MAX,
    _B1_PF_ROWS,
    _CudaResidentQwen3,
)
from residentk.loadvec import _ld4
from residentk.tc_shim_bridge import (
    TC_SHIM_BUILD,
    TC_MIN_M,
    TC_ACC_MODE,
    TC_NOSEAM,
    _tc_init,
    _tc_noseam,
    _tc_last_error,
    _tc_stage_f32_to_f16,
    _tc_gemm_dispatch,
    _tc_dequant_packed3_f16_dense,
    _pf_swiglu_rows_kernel,
)
from std.time import perf_counter_ns

alias _FP = UnsafePointer[Float32, origin=MutAnyOrigin]
"""A device Float32 buffer as a kernel parameter — `residentk.kernels`' spelling, and the
packed3 weight stream is typed Float32 on purpose (module docstring)."""


# ── the three packed3 decode twins ─────────────────────────────────────────────


def _packed3_gemv_accum_kernel(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP, k_i64: Int64, n_i64: Int64,
):
    """`y += W @ x` with `W` held packed3 — the packed3 twin of `_gemv_accum_kernel`: 8 output
    rows per block (`grid_dim = ceil(n / 8)`), the projection AND its residual add in one
    dispatch (`+=` is the whole point for o_proj/down_proj's residual feed — each output element
    is owned by exactly one SIMD group, so the read-modify-write has no race). ONLY the weight
    load+dequant differs from the f32 twin; the shared staging, the accumulator and the
    barrier-tree reduction are copied from it line for line.

    ACTIVATION TAIL (module docstring): `x` arrives at its natural `k` elements; the staging
    loop zero-fills the `k_pack - k` tail, so the 12-wide chunk loop's padded reads multiply
    padding quants by exactly zero.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)


    # ── one SIMD group per output row, packed3 chunk loop ──
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
            var b = bitcast[DType.uint8, 16](v)
            var xv0 = _ld4(x, t)
            var xv1 = _ld4(x, t + 4)
            var xv2 = _ld4(x, t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s1 = s0
            var z1 = z0
            var r = t & 31
            var cross = _P3_CHUNK
            if r == 24:
                cross = 8
            if r == 28:
                cross = 4
            if cross < _P3_CHUNK:
                s1 = wscale[sbase + blk + 1]
                z1 = wzero[sbase + blk + 1]
            var s_lo = s0
            var z_lo = z0
            if cross == 4:
                s_lo = s1
                z_lo = z1
            var s_hi = s0
            var z_hi = z0
            if cross <= 8:
                s_hi = s1
                z_hi = z1

            # MUST stay in sync with `_packed3_gemv_kernel`'s 12 dequant+mac lines in
            # residentk.kernels_packed3 (and with the two other twins in this file).
            acc += xv0[0] * ((Float32(Int32(b[0])) - z0) * s0)
            acc += xv0[1] * ((Float32(Int32(b[1])) - z0) * s0)
            acc += xv0[2] * ((Float32(Int32(b[2])) - z0) * s0)
            acc += xv0[3] * ((Float32(Int32(b[4])) - z0) * s0)
            acc += xv1[0] * ((Float32(Int32(b[5])) - z_lo) * s_lo)
            acc += xv1[1] * ((Float32(Int32(b[6])) - z_lo) * s_lo)
            acc += xv1[2] * ((Float32(Int32(b[8])) - z_lo) * s_lo)
            acc += xv1[3] * ((Float32(Int32(b[9])) - z_lo) * s_lo)
            acc += xv2[0] * ((Float32(Int32(b[10])) - z_hi) * s_hi)
            acc += xv2[1] * ((Float32(Int32(b[12])) - z_hi) * s_hi)
            acc += xv2[2] * ((Float32(Int32(b[13])) - z_hi) * s_hi)
            acc += xv2[3] * ((Float32(Int32(b[14])) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = y[j] + red[sub * _LANES]


def _packed3_gemv_accum_kernel_v2(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP, k_i64: Int64, n_i64: Int64,
):
    """`_packed3_gemv_accum_kernel`'s v2 twin — the SAME `y += W @ x` (projection AND residual
    add in one dispatch, 8 rows per block, shared staging with the `k_pack - k` tail
    zero-filled) with ONLY the chunk loop's unpack changed: `bitcast[DType.int32, 4]` word
    view + shift/AND byte extraction, and the crossing classification hoisted out of the loop
    (loop-invariant — the lane's chunk offsets are `lane*12 + i*(32*12)` and `384 % 32 == 0`).
    Same integer quants, same dequant expression, same accumulation order -> bit-identical
    output (the rule `residentk.kernels_packed3`'s v2 docstring states). Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V2_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)


    # ── one SIMD group per output row, v2 chunk loop ──
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc = Float32(0.0)
    if j < n:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var r0 = (lane * _P3_CHUNK) & 31
        var cross_hi = r0 == 24 or r0 == 28
        var cross_lo = r0 == 28
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
            var w = bitcast[DType.int32, 4](v)
            var xv0 = _ld4(x, t)
            var xv1 = _ld4(x, t + 4)
            var xv2 = _ld4(x, t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s_lo = s0
            var z_lo = z0
            var s_hi = s0
            var z_hi = z0
            if cross_hi:
                s_hi = wscale[sbase + blk + 1]
                z_hi = wzero[sbase + blk + 1]
                if cross_lo:
                    s_lo = s_hi
                    z_lo = z_hi

            # MUST stay in sync with `_packed3_gemv_kernel_v2`'s 12 dequant+mac lines in
            # residentk.kernels_packed3 (and with the other v2 twins in this file).
            acc += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
            acc += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
            acc += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
            acc += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
            acc += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
            acc += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
            acc += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
            acc += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
            acc += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
            acc += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
            acc += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
            acc += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
    red[tid] = acc
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = y[j] + red[sub * _LANES]


def _packed3_gemv_accum_kernel_v3(
    y: _FP, x: _FP, wp: _FP, wscale: _FP, wzero: _FP, k_i64: Int64, n_i64: Int64,
):
    """`_packed3_gemv_accum_kernel`'s v3 twin — v2's unpack PLUS three interleaved
    accumulators (the chunk's 12 products split by element index mod 3 into 4-deep chains,
    combined at loop end as `(acc0 + acc1) + acc2`); the `y += W @ x` shape, staging, 8 rows
    per block and the barrier-tree reduction are verbatim. The reassociation CHANGES
    accumulation order, so this variant is ulp-different from v1/v2 (the rule
    `residentk.kernels_packed3._packed3_gemv_kernel_v3`'s docstring states). Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V3_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)


    # ── one SIMD group per output row, v3 chunk loop ──
    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var acc0 = Float32(0.0)
    var acc1 = Float32(0.0)
    var acc2 = Float32(0.0)
    if j < n:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var r0 = (lane * _P3_CHUNK) & 31
        var cross_hi = r0 == 24 or r0 == 28
        var cross_lo = r0 == 28
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
            var w = bitcast[DType.int32, 4](v)
            var xv0 = _ld4(x, t)
            var xv1 = _ld4(x, t + 4)
            var xv2 = _ld4(x, t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s_lo = s0
            var z_lo = z0
            var s_hi = s0
            var z_hi = z0
            if cross_hi:
                s_hi = wscale[sbase + blk + 1]
                z_hi = wzero[sbase + blk + 1]
                if cross_lo:
                    s_lo = s_hi
                    z_lo = z_hi

            # The same 12 dequant+mac terms as v2, regrouped into three 4-deep chains.
            acc0 += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
            acc1 += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
            acc2 += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
            acc0 += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
            acc1 += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
            acc2 += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
            acc0 += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
            acc1 += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
            acc2 += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
            acc0 += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
            acc1 += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
            acc2 += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
    red[tid] = (acc0 + acc1) + acc2
    barrier()
    var st = _LANES // 2
    while st > 0:
        if lane < st:
            red[tid] = red[tid] + red[tid + st]
        barrier()
        st //= 2
    if lane == 0 and j < n:
        y[j] = y[j] + red[sub * _LANES]


def _norm_gemv2_swiglu_kernel_p3(
    act: _FP, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_ff_i64: Int64, eps: Float32,
):
    """`act = swish(W_gate @ xn) * (W_up @ xn)` with `xn = rmsnorm(x) * gamma`, `W_gate`/`W_up`
    held packed3 — the packed3 twin of `_norm_gemv2_swiglu_kernel`, 8 output pairs per block
    (`grid_dim = ceil(n_ff / 8)`). `wp` is the gate and up matrices CONCATENATED as
    `[2 * n_ff, k]` row-major, gate rows first — packed row-wise, so the gate row `j` lives at
    packed word offset `j * words_per_row` and its up partner at `(n_ff + j) * words_per_row`
    (same layout statement the f32 twin makes, only the storage format changed). ONLY the weight
    load+dequant differs from the f32 twin; the normalization, the shared staging, the two
    barrier-tree reductions and the SwiGLU combine (including its `swish(gate) * up` convention,
    which backwards would generate different text) are copied from it line for line.

    ACTIVATION TAIL (module docstring): the staging loop stages the NORMALIZED vector with the
    `k_pack - k` tail zero-filled.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
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

    # ── 2. stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var s = tid
    while s < k_pack:
        if s < k:
            xs[s] = x[s] * inv * gamma[s]
        else:
            xs[s] = Float32(0.0)
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub

    # ── gate ──
    var acc = Float32(0.0)
    if j < n_ff:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
            var b = bitcast[DType.uint8, 16](v)
            var xv0 = xs.load[width=4](t)
            var xv1 = xs.load[width=4](t + 4)
            var xv2 = xs.load[width=4](t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s1 = s0
            var z1 = z0
            var r = t & 31
            var cross = _P3_CHUNK
            if r == 24:
                cross = 8
            if r == 28:
                cross = 4
            if cross < _P3_CHUNK:
                s1 = wscale[sbase + blk + 1]
                z1 = wzero[sbase + blk + 1]
            var s_lo = s0
            var z_lo = z0
            if cross == 4:
                s_lo = s1
                z_lo = z1
            var s_hi = s0
            var z_hi = z0
            if cross <= 8:
                s_hi = s1
                z_hi = z1

            # MUST stay in sync with `_packed3_gemv_kernel`'s 12 dequant+mac lines.
            acc += xv0[0] * ((Float32(Int32(b[0])) - z0) * s0)
            acc += xv0[1] * ((Float32(Int32(b[1])) - z0) * s0)
            acc += xv0[2] * ((Float32(Int32(b[2])) - z0) * s0)
            acc += xv0[3] * ((Float32(Int32(b[4])) - z0) * s0)
            acc += xv1[0] * ((Float32(Int32(b[5])) - z_lo) * s_lo)
            acc += xv1[1] * ((Float32(Int32(b[6])) - z_lo) * s_lo)
            acc += xv1[2] * ((Float32(Int32(b[8])) - z_lo) * s_lo)
            acc += xv1[3] * ((Float32(Int32(b[9])) - z_lo) * s_lo)
            acc += xv2[0] * ((Float32(Int32(b[10])) - z_hi) * s_hi)
            acc += xv2[1] * ((Float32(Int32(b[12])) - z_hi) * s_hi)
            acc += xv2[2] * ((Float32(Int32(b[13])) - z_hi) * s_hi)
            acc += xv2[3] * ((Float32(Int32(b[14])) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
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
        var wbase2 = (n_ff + j) * words_per_row
        var sbase2 = (n_ff + j) * nblocks
        var t2 = lane * _P3_CHUNK
        while t2 < k_pack:
            var v2 = _ld4(wp, wbase2 + t2 // _P3_QUANTS_PER_WORD)
            var b2 = bitcast[DType.uint8, 16](v2)
            var xv0 = xs.load[width=4](t2)
            var xv1 = xs.load[width=4](t2 + 4)
            var xv2 = xs.load[width=4](t2 + 8)

            var blk2 = t2 >> 5
            var u0 = wscale[sbase2 + blk2]
            var uz0 = wzero[sbase2 + blk2]
            var u1 = u0
            var uz1 = uz0
            var r2 = t2 & 31
            var cross2 = _P3_CHUNK
            if r2 == 24:
                cross2 = 8
            if r2 == 28:
                cross2 = 4
            if cross2 < _P3_CHUNK:
                u1 = wscale[sbase2 + blk2 + 1]
                uz1 = wzero[sbase2 + blk2 + 1]
            var ulo = u0
            var uzlo = uz0
            if cross2 == 4:
                ulo = u1
                uzlo = uz1
            var uhi = u0
            var uzhi = uz0
            if cross2 <= 8:
                uhi = u1
                uzhi = uz1

            # MUST stay in sync with `_packed3_gemv_kernel`'s 12 dequant+mac lines.
            acc2 += xv0[0] * ((Float32(Int32(b2[0])) - uz0) * u0)
            acc2 += xv0[1] * ((Float32(Int32(b2[1])) - uz0) * u0)
            acc2 += xv0[2] * ((Float32(Int32(b2[2])) - uz0) * u0)
            acc2 += xv0[3] * ((Float32(Int32(b2[4])) - uz0) * u0)
            acc2 += xv1[0] * ((Float32(Int32(b2[5])) - uzlo) * ulo)
            acc2 += xv1[1] * ((Float32(Int32(b2[6])) - uzlo) * ulo)
            acc2 += xv1[2] * ((Float32(Int32(b2[8])) - uzlo) * ulo)
            acc2 += xv1[3] * ((Float32(Int32(b2[9])) - uzlo) * ulo)
            acc2 += xv2[0] * ((Float32(Int32(b2[10])) - uzhi) * uhi)
            acc2 += xv2[1] * ((Float32(Int32(b2[12])) - uzhi) * uhi)
            acc2 += xv2[2] * ((Float32(Int32(b2[13])) - uzhi) * uhi)
            acc2 += xv2[3] * ((Float32(Int32(b2[14])) - uzhi) * uhi)
            t2 += _LANES * _P3_CHUNK
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
        act[j] = (g / (1.0 + exp(-g))) * u


def _norm_gemv2_swiglu_kernel_p3_v2(
    act: _FP, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_ff_i64: Int64, eps: Float32,
):
    """`_norm_gemv2_swiglu_kernel_p3`'s v2 twin — the SAME fused rmsnorm + gate/up + SwiGLU
    (8 output pairs per block, gate rows at packed-row `j`, up partners at `n_ff + j`, the
    `swish(gate) * up` convention kept verbatim) with ONLY the two chunk loops' unpack
    changed: `bitcast[DType.int32, 4]` word view + shift/AND byte extraction, and the
    crossing classification hoisted out of each loop (loop-invariant). Same integer quants,
    same dequant expression, same accumulation order -> bit-identical output (the rule
    `residentk.kernels_packed3`'s v2 docstring states). Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V2_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
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

    # ── 2. stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var s = tid
    while s < k_pack:
        if s < k:
            xs[s] = x[s] * inv * gamma[s]
        else:
            xs[s] = Float32(0.0)
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    # ── hoisted crossing classification (loop-invariant — both chunk loops visit the same
    #    residues `lane*12 + i*(32*12)`, and `384 % 32 == 0`) ──
    var r0 = (lane * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    # ── gate ──
    var acc = Float32(0.0)
    if j < n_ff:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
            var w = bitcast[DType.int32, 4](v)
            var xv0 = xs.load[width=4](t)
            var xv1 = xs.load[width=4](t + 4)
            var xv2 = xs.load[width=4](t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s_lo = s0
            var z_lo = z0
            var s_hi = s0
            var z_hi = z0
            if cross_hi:
                s_hi = wscale[sbase + blk + 1]
                z_hi = wzero[sbase + blk + 1]
                if cross_lo:
                    s_lo = s_hi
                    z_lo = z_hi

            # MUST stay in sync with `_packed3_gemv_kernel_v2`'s 12 dequant+mac lines.
            acc += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
            acc += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
            acc += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
            acc += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
            acc += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
            acc += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
            acc += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
            acc += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
            acc += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
            acc += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
            acc += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
            acc += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
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
        var wbase2 = (n_ff + j) * words_per_row
        var sbase2 = (n_ff + j) * nblocks
        var t2 = lane * _P3_CHUNK
        while t2 < k_pack:
            var v2 = _ld4(wp, wbase2 + t2 // _P3_QUANTS_PER_WORD)
            var w2 = bitcast[DType.int32, 4](v2)
            var xv0 = xs.load[width=4](t2)
            var xv1 = xs.load[width=4](t2 + 4)
            var xv2 = xs.load[width=4](t2 + 8)

            var blk2 = t2 >> 5
            var u0 = wscale[sbase2 + blk2]
            var uz0 = wzero[sbase2 + blk2]
            var ulo = u0
            var uzlo = uz0
            var uhi = u0
            var uzhi = uz0
            if cross_hi:
                uhi = wscale[sbase2 + blk2 + 1]
                uzhi = wzero[sbase2 + blk2 + 1]
                if cross_lo:
                    ulo = uhi
                    uzlo = uzhi

            # MUST stay in sync with `_packed3_gemv_kernel_v2`'s 12 dequant+mac lines.
            acc2 += xv0[0] * ((Float32(w2[0] & 255) - uz0) * u0)
            acc2 += xv0[1] * ((Float32((w2[0] >> 8) & 255) - uz0) * u0)
            acc2 += xv0[2] * ((Float32((w2[0] >> 16) & 255) - uz0) * u0)
            acc2 += xv0[3] * ((Float32(w2[1] & 255) - uz0) * u0)
            acc2 += xv1[0] * ((Float32((w2[1] >> 8) & 255) - uzlo) * ulo)
            acc2 += xv1[1] * ((Float32((w2[1] >> 16) & 255) - uzlo) * ulo)
            acc2 += xv1[2] * ((Float32(w2[2] & 255) - uzlo) * ulo)
            acc2 += xv1[3] * ((Float32((w2[2] >> 8) & 255) - uzlo) * ulo)
            acc2 += xv2[0] * ((Float32((w2[2] >> 16) & 255) - uzhi) * uhi)
            acc2 += xv2[1] * ((Float32(w2[3] & 255) - uzhi) * uhi)
            acc2 += xv2[2] * ((Float32((w2[3] >> 8) & 255) - uzhi) * uhi)
            acc2 += xv2[3] * ((Float32((w2[3] >> 16) & 255) - uzhi) * uhi)
            t2 += _LANES * _P3_CHUNK
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
        act[j] = (g / (1.0 + exp(-g))) * u


def _norm_gemv2_swiglu_kernel_p3_v3(
    act: _FP, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_ff_i64: Int64, eps: Float32,
):
    """`_norm_gemv2_swiglu_kernel_p3`'s v3 twin — v2's unpack PLUS three interleaved
    accumulators in EACH of the gate and up chunk loops (12 products split by element index
    mod 3 into 4-deep chains, combined at loop end); normalization, staging, reductions and
    the `swish(gate) * up` combine are verbatim. The reassociation CHANGES accumulation
    order, so this variant is ulp-different from v1/v2 (the rule
    `residentk.kernels_packed3._packed3_gemv_kernel_v3`'s docstring states). Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V3_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
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

    # ── 2. stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var s = tid
    while s < k_pack:
        if s < k:
            xs[s] = x[s] * inv * gamma[s]
        else:
            xs[s] = Float32(0.0)
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var r0 = (lane * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    # ── gate ──
    var acc0 = Float32(0.0)
    var acc1 = Float32(0.0)
    var acc2 = Float32(0.0)
    if j < n_ff:
        var wbase = j * words_per_row
        var sbase = j * nblocks
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
            var w = bitcast[DType.int32, 4](v)
            var xv0 = xs.load[width=4](t)
            var xv1 = xs.load[width=4](t + 4)
            var xv2 = xs.load[width=4](t + 8)

            var blk = t >> 5
            var s0 = wscale[sbase + blk]
            var z0 = wzero[sbase + blk]
            var s_lo = s0
            var z_lo = z0
            var s_hi = s0
            var z_hi = z0
            if cross_hi:
                s_hi = wscale[sbase + blk + 1]
                z_hi = wzero[sbase + blk + 1]
                if cross_lo:
                    s_lo = s_hi
                    z_lo = z_hi

            # The same 12 dequant+mac terms as v2, regrouped into three 4-deep chains.
            acc0 += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
            acc1 += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
            acc2 += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
            acc0 += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
            acc1 += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
            acc2 += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
            acc0 += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
            acc1 += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
            acc2 += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
            acc0 += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
            acc1 += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
            acc2 += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
            t += _LANES * _P3_CHUNK
    red[tid] = (acc0 + acc1) + acc2
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
    var ucc0 = Float32(0.0)
    var ucc1 = Float32(0.0)
    var ucc2 = Float32(0.0)
    if j < n_ff:
        var wbase2 = (n_ff + j) * words_per_row
        var sbase2 = (n_ff + j) * nblocks
        var t2 = lane * _P3_CHUNK
        while t2 < k_pack:
            var v2 = _ld4(wp, wbase2 + t2 // _P3_QUANTS_PER_WORD)
            var w2 = bitcast[DType.int32, 4](v2)
            var xv0 = xs.load[width=4](t2)
            var xv1 = xs.load[width=4](t2 + 4)
            var xv2 = xs.load[width=4](t2 + 8)

            var blk2 = t2 >> 5
            var u0 = wscale[sbase2 + blk2]
            var uz0 = wzero[sbase2 + blk2]
            var ulo = u0
            var uzlo = uz0
            var uhi = u0
            var uzhi = uz0
            if cross_hi:
                uhi = wscale[sbase2 + blk2 + 1]
                uzhi = wzero[sbase2 + blk2 + 1]
                if cross_lo:
                    ulo = uhi
                    uzlo = uzhi

            # The same 12 dequant+mac terms as v2, regrouped into three 4-deep chains.
            ucc0 += xv0[0] * ((Float32(w2[0] & 255) - uz0) * u0)
            ucc1 += xv0[1] * ((Float32((w2[0] >> 8) & 255) - uz0) * u0)
            ucc2 += xv0[2] * ((Float32((w2[0] >> 16) & 255) - uz0) * u0)
            ucc0 += xv0[3] * ((Float32(w2[1] & 255) - uz0) * u0)
            ucc1 += xv1[0] * ((Float32((w2[1] >> 8) & 255) - uzlo) * ulo)
            ucc2 += xv1[1] * ((Float32((w2[1] >> 16) & 255) - uzlo) * ulo)
            ucc0 += xv1[2] * ((Float32(w2[2] & 255) - uzlo) * ulo)
            ucc1 += xv1[3] * ((Float32((w2[2] >> 8) & 255) - uzlo) * ulo)
            ucc2 += xv2[0] * ((Float32((w2[2] >> 16) & 255) - uzhi) * uhi)
            ucc0 += xv2[1] * ((Float32(w2[3] & 255) - uzhi) * uhi)
            ucc1 += xv2[2] * ((Float32((w2[3] >> 8) & 255) - uzhi) * uhi)
            ucc2 += xv2[3] * ((Float32((w2[3] >> 16) & 255) - uzhi) * uhi)
            t2 += _LANES * _P3_CHUNK
    red[tid] = (ucc0 + ucc1) + ucc2
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
        act[j] = (g / (1.0 + exp(-g))) * u


def _norm_gemv2_swiglu_kernel_p3_v4(
    act: _FP, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_ff_i64: Int64, eps: Float32,
):
    """`_norm_gemv2_swiglu_kernel_p3`'s v4 twin — the v2 unpack with the gate and up chunk
    loops FUSED: one pass over the staged activation feeds BOTH dot products, so the
    kernel's shared x traffic halves (the ncu autopsy of the packed3 GEMV family: L1/TEX at
    70% of pipe with DRAM at only 24% — the kernels are issue/L1-bound on per-chunk work,
    not bandwidth-bound, which is why cheaper unpacks and split accumulators both measured
    at parity). Two independent accumulators (`acc_g`, `acc_u`) also give the two weight
    streams natural instruction-level overlap. Each dot product keeps its v2 element-order
    accumulation EXACTLY, and both reductions stay the v1/v2 barrier tree verbatim, so v4
    computes bit-identical output to v1/v2. Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V4_KERNELS` (the default generation)."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n_ff = Int(n_ff_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var gsh = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var tid = Int(thread_idx.x)

    # ── 1. sum of squares over the whole vector, tree-reduced across the group ──
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

    # ── 2. stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var s = tid
    while s < k_pack:
        if s < k:
            xs[s] = x[s] * inv * gamma[s]
        else:
            xs[s] = Float32(0.0)
        s += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var j = Int(block_idx.x) * _SUBS + sub
    var r0 = (lane * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28

    # ── gate + up in ONE pass: two weight streams, one shared activation read per chunk ──
    var acc_g = Float32(0.0)
    var acc_u = Float32(0.0)
    if j < n_ff:
        var wbase_g = j * words_per_row
        var sbase_g = j * nblocks
        var wbase_u = (n_ff + j) * words_per_row
        var sbase_u = (n_ff + j) * nblocks
        var t = lane * _P3_CHUNK
        while t < k_pack:
            var vg = _ld4(wp, wbase_g + t // _P3_QUANTS_PER_WORD)
            var vu = _ld4(wp, wbase_u + t // _P3_QUANTS_PER_WORD)
            var wg = bitcast[DType.int32, 4](vg)
            var wu = bitcast[DType.int32, 4](vu)
            var xv0 = xs.load[width=4](t)
            var xv1 = xs.load[width=4](t + 4)
            var xv2 = xs.load[width=4](t + 8)

            var blk = t >> 5
            # ── gate block-32 scale+zero (v2's hoisted-crossing form) ──
            var gs0 = wscale[sbase_g + blk]
            var gz0 = wzero[sbase_g + blk]
            var gs_lo = gs0
            var gz_lo = gz0
            var gs_hi = gs0
            var gz_hi = gz0
            if cross_hi:
                gs_hi = wscale[sbase_g + blk + 1]
                gz_hi = wzero[sbase_g + blk + 1]
                if cross_lo:
                    gs_lo = gs_hi
                    gz_lo = gz_hi
            # ── up block-32 scale+zero ──
            var us0 = wscale[sbase_u + blk]
            var uz0 = wzero[sbase_u + blk]
            var us_lo = us0
            var uz_lo = uz0
            var us_hi = us0
            var uz_hi = uz0
            if cross_hi:
                us_hi = wscale[sbase_u + blk + 1]
                uz_hi = wzero[sbase_u + blk + 1]
                if cross_lo:
                    us_lo = us_hi
                    uz_lo = uz_hi

            # ── gate: v2's 12 dequant+mac terms in element order ──
            acc_g += xv0[0] * ((Float32(wg[0] & 255) - gz0) * gs0)
            acc_g += xv0[1] * ((Float32((wg[0] >> 8) & 255) - gz0) * gs0)
            acc_g += xv0[2] * ((Float32((wg[0] >> 16) & 255) - gz0) * gs0)
            acc_g += xv0[3] * ((Float32(wg[1] & 255) - gz0) * gs0)
            acc_g += xv1[0] * ((Float32((wg[1] >> 8) & 255) - gz_lo) * gs_lo)
            acc_g += xv1[1] * ((Float32((wg[1] >> 16) & 255) - gz_lo) * gs_lo)
            acc_g += xv1[2] * ((Float32(wg[2] & 255) - gz_lo) * gs_lo)
            acc_g += xv1[3] * ((Float32((wg[2] >> 8) & 255) - gz_lo) * gs_lo)
            acc_g += xv2[0] * ((Float32((wg[2] >> 16) & 255) - gz_hi) * gs_hi)
            acc_g += xv2[1] * ((Float32(wg[3] & 255) - gz_hi) * gs_hi)
            acc_g += xv2[2] * ((Float32((wg[3] >> 8) & 255) - gz_hi) * gs_hi)
            acc_g += xv2[3] * ((Float32((wg[3] >> 16) & 255) - gz_hi) * gs_hi)
            # ── up: the same 12 terms on the up weight stream ──
            acc_u += xv0[0] * ((Float32(wu[0] & 255) - uz0) * us0)
            acc_u += xv0[1] * ((Float32((wu[0] >> 8) & 255) - uz0) * us0)
            acc_u += xv0[2] * ((Float32((wu[0] >> 16) & 255) - uz0) * us0)
            acc_u += xv0[3] * ((Float32(wu[1] & 255) - uz0) * us0)
            acc_u += xv1[0] * ((Float32((wu[1] >> 8) & 255) - uz_lo) * us_lo)
            acc_u += xv1[1] * ((Float32((wu[1] >> 16) & 255) - uz_lo) * us_lo)
            acc_u += xv1[2] * ((Float32(wu[2] & 255) - uz_lo) * us_lo)
            acc_u += xv1[3] * ((Float32((wu[2] >> 8) & 255) - uz_lo) * us_lo)
            acc_u += xv2[0] * ((Float32((wu[2] >> 16) & 255) - uz_hi) * us_hi)
            acc_u += xv2[1] * ((Float32(wu[3] & 255) - uz_hi) * us_hi)
            acc_u += xv2[2] * ((Float32((wu[3] >> 8) & 255) - uz_hi) * us_hi)
            acc_u += xv2[3] * ((Float32((wu[3] >> 16) & 255) - uz_hi) * us_hi)
            t += _LANES * _P3_CHUNK

    # ── gate reduction, v2's barrier tree verbatim ──
    red[tid] = acc_g
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

    # ── up reduction, same tree; then the SwiGLU combine ──
    red[tid] = acc_u
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
        act[j] = (g / (1.0 + exp(-g))) * u


def _lmhead_argmax_kernel_p3(
    blk_val: _FP, blk_idx: _I32P, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, eps: Float32, n_iters_i64: Int64,
):
    """Final rmsnorm, the full-vocabulary packed3 projection, and a per-threadgroup argmax — the
    packed3 twin of `_lmhead_argmax_kernel`. The logits are NEVER materialised and never leave
    the device, exactly as the f32 twin's docstring states: only each threadgroup's best
    `(logit, id)` pair is written out, and the unchanged `_argmax_reduce_kernel` collapses those
    to one pair the host reads as 8 bytes.

    The GRID-STRIDE LOOP structure, the passed-in `n_iters` (uniform trip count — the loop
    contains `barrier()`, and a barrier reached by only some threads hangs the GPU), and the
    tie-resolves-to-lowest-id convention are copied from the f32 twin line for line; ONLY the
    weight load+dequant differs.

    ACTIVATION TAIL (module docstring): the staging loop stages the NORMALIZED vector with the
    `k_pack - k` tail zero-filled.
    """
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var n_iters = Int(n_iters_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
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

    # ── stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var st0 = tid
    while st0 < k_pack:
        if st0 < k:
            xs[st0] = x[st0] * inv * gamma[st0]
        else:
            xs[st0] = Float32(0.0)
        st0 += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var stride_cols = Int(grid_dim.x) * _SUBS
    var best = _NEG_HUGE
    var best_i = Int32(-1)

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc = Float32(0.0)
        if j < n:
            var wbase = j * words_per_row
            var sbase = j * nblocks
            var t = lane * _P3_CHUNK
            while t < k_pack:
                var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
                var b = bitcast[DType.uint8, 16](v)
                var xv0 = xs.load[width=4](t)
                var xv1 = xs.load[width=4](t + 4)
                var xv2 = xs.load[width=4](t + 8)

                var blk = t >> 5
                var s0 = wscale[sbase + blk]
                var z0 = wzero[sbase + blk]
                var s1 = s0
                var z1 = z0
                var r = t & 31
                var cross = _P3_CHUNK
                if r == 24:
                    cross = 8
                if r == 28:
                    cross = 4
                if cross < _P3_CHUNK:
                    s1 = wscale[sbase + blk + 1]
                    z1 = wzero[sbase + blk + 1]
                var s_lo = s0
                var z_lo = z0
                if cross == 4:
                    s_lo = s1
                    z_lo = z1
                var s_hi = s0
                var z_hi = z0
                if cross <= 8:
                    s_hi = s1
                    z_hi = z1

                # MUST stay in sync with `_packed3_gemv_kernel`'s 12 dequant+mac lines.
                acc += xv0[0] * ((Float32(Int32(b[0])) - z0) * s0)
                acc += xv0[1] * ((Float32(Int32(b[1])) - z0) * s0)
                acc += xv0[2] * ((Float32(Int32(b[2])) - z0) * s0)
                acc += xv0[3] * ((Float32(Int32(b[4])) - z0) * s0)
                acc += xv1[0] * ((Float32(Int32(b[5])) - z_lo) * s_lo)
                acc += xv1[1] * ((Float32(Int32(b[6])) - z_lo) * s_lo)
                acc += xv1[2] * ((Float32(Int32(b[8])) - z_lo) * s_lo)
                acc += xv1[3] * ((Float32(Int32(b[9])) - z_lo) * s_lo)
                acc += xv2[0] * ((Float32(Int32(b[10])) - z_hi) * s_hi)
                acc += xv2[1] * ((Float32(Int32(b[12])) - z_hi) * s_hi)
                acc += xv2[2] * ((Float32(Int32(b[13])) - z_hi) * s_hi)
                acc += xv2[3] * ((Float32(Int32(b[14])) - z_hi) * s_hi)
                t += _LANES * _P3_CHUNK
        red[tid] = acc
        barrier()
        var st = _LANES // 2
        while st > 0:
            if lane < st:
                red[tid] = red[tid] + red[tid + st]
            barrier()
            st //= 2
        if lane == 0 and j < n:
            var val = red[sub * _LANES]
            if val > best:
                best = val
                best_i = Int32(j)
        barrier()

    if lane == 0:
        sv[sub] = best
        si[sub] = best_i
    barrier()
    if tid == 0:
        var bv = sv[0]
        var bi = si[0]
        for u in range(1, _SUBS):
            # Strictly greater, so the lowest id survives an exact tie.
            if sv[u] > bv:
                bv = sv[u]
                bi = si[u]
        blk_val[Int(block_idx.x)] = bv
        blk_idx[Int(block_idx.x)] = bi


def _lmhead_argmax_kernel_p3_v2(
    blk_val: _FP, blk_idx: _I32P, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, eps: Float32, n_iters_i64: Int64,
):
    """`_lmhead_argmax_kernel_p3`'s v2 twin — the SAME final rmsnorm + full-vocabulary packed3
    projection + per-threadgroup argmax (grid-stride loop with the passed-in uniform
    `n_iters`, logits never materialised, tie-resolves-to-lowest-id) with ONLY the chunk
    loop's unpack changed: `bitcast[DType.int32, 4]` word view + shift/AND byte extraction,
    and the crossing classification hoisted OUT of the grid-stride loop (it depends only on
    the lane, so it is constant across every iteration). Same integer quants, same dequant
    expression, same accumulation order -> bit-identical logits, so the argmax cannot move.
    Selected by `residentk.session_cuda_p3_graph.P3_GRAPH_V2_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var n_iters = Int(n_iters_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
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

    # ── stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var st0 = tid
    while st0 < k_pack:
        if st0 < k:
            xs[st0] = x[st0] * inv * gamma[st0]
        else:
            xs[st0] = Float32(0.0)
        st0 += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var stride_cols = Int(grid_dim.x) * _SUBS
    # ── hoisted crossing classification: constant across the whole grid-stride loop ──
    var r0 = (lane * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28
    var best = _NEG_HUGE
    var best_i = Int32(-1)

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc = Float32(0.0)
        if j < n:
            var wbase = j * words_per_row
            var sbase = j * nblocks
            var t = lane * _P3_CHUNK
            while t < k_pack:
                var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
                var w = bitcast[DType.int32, 4](v)
                var xv0 = xs.load[width=4](t)
                var xv1 = xs.load[width=4](t + 4)
                var xv2 = xs.load[width=4](t + 8)

                var blk = t >> 5
                var s0 = wscale[sbase + blk]
                var z0 = wzero[sbase + blk]
                var s_lo = s0
                var z_lo = z0
                var s_hi = s0
                var z_hi = z0
                if cross_hi:
                    s_hi = wscale[sbase + blk + 1]
                    z_hi = wzero[sbase + blk + 1]
                    if cross_lo:
                        s_lo = s_hi
                        z_lo = z_hi

                # MUST stay in sync with `_packed3_gemv_kernel_v2`'s 12 dequant+mac lines.
                acc += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
                acc += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
                acc += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
                acc += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
                acc += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
                acc += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
                acc += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
                acc += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
                acc += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
                acc += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
                acc += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
                acc += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
                t += _LANES * _P3_CHUNK
        red[tid] = acc
        barrier()
        var st = _LANES // 2
        while st > 0:
            if lane < st:
                red[tid] = red[tid] + red[tid + st]
            barrier()
            st //= 2
        if lane == 0 and j < n:
            var val = red[sub * _LANES]
            if val > best:
                best = val
                best_i = Int32(j)
        barrier()

    if lane == 0:
        sv[sub] = best
        si[sub] = best_i
    barrier()
    if tid == 0:
        var bv = sv[0]
        var bi = si[0]
        for u in range(1, _SUBS):
            # Strictly greater, so the lowest id survives an exact tie.
            if sv[u] > bv:
                bv = sv[u]
                bi = si[u]
        blk_val[Int(block_idx.x)] = bv
        blk_idx[Int(block_idx.x)] = bi


def _lmhead_argmax_kernel_p3_v3(
    blk_val: _FP, blk_idx: _I32P, x: _FP, gamma: _FP, wp: _FP, wscale: _FP, wzero: _FP,
    k_i64: Int64, n_i64: Int64, eps: Float32, n_iters_i64: Int64,
):
    """`_lmhead_argmax_kernel_p3`'s v3 twin — v2's unpack PLUS three interleaved
    accumulators in the chunk loop (12 products split by element index mod 3 into 4-deep
    chains, combined at loop end); the grid-stride structure, uniform `n_iters`, reductions
    and the tie-resolves-to-lowest-id argmax are verbatim. The reassociation CHANGES
    accumulation order — the logits become ulp-different, so an argmax on a near-tie MAY
    move vs v1/v2 (the rule `residentk.kernels_packed3._packed3_gemv_kernel_v3`'s docstring
    states; G0 stays the hard gate). Selected by
    `residentk.session_cuda_p3_graph.P3_GRAPH_V3_KERNELS`."""
    # Mojo 1.0.0: GPU kernel parameters must be fixed-width DevicePassable; widened
    # back to Int once at entry, where all the arithmetic lives (accel/launch.mojo's pattern).
    var k = Int(k_i64)
    var n = Int(n_i64)
    var n_iters = Int(n_iters_i64)
    var k_pack = ((k + _P3_CHUNK - 1) // _P3_CHUNK) * _P3_CHUNK
    var words_per_row = k_pack // _P3_QUANTS_PER_WORD
    var nblocks = (k_pack + _P3_BLOCK - 1) // _P3_BLOCK

    var xs = stack_allocation[_P3_STAGE, DType.float32, address_space = AddressSpace.SHARED]()
    var red = stack_allocation[_TG, DType.float32, address_space = AddressSpace.SHARED]()
    var sv = stack_allocation[_SUBS, DType.float32, address_space = AddressSpace.SHARED]()
    var si = stack_allocation[_SUBS, DType.int32, address_space = AddressSpace.SHARED]()
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

    # ── stage the normalized, gamma-scaled vector; zero-fill the padded tail ──
    var st0 = tid
    while st0 < k_pack:
        if st0 < k:
            xs[st0] = x[st0] * inv * gamma[st0]
        else:
            xs[st0] = Float32(0.0)
        st0 += _TG
    barrier()

    var lane = tid % _LANES
    var sub = tid // _LANES
    var stride_cols = Int(grid_dim.x) * _SUBS
    var r0 = (lane * _P3_CHUNK) & 31
    var cross_hi = r0 == 24 or r0 == 28
    var cross_lo = r0 == 28
    var best = _NEG_HUGE
    var best_i = Int32(-1)

    for it in range(n_iters):
        var j = Int(block_idx.x) * _SUBS + sub + it * stride_cols
        var acc0 = Float32(0.0)
        var acc1 = Float32(0.0)
        var acc2 = Float32(0.0)
        if j < n:
            var wbase = j * words_per_row
            var sbase = j * nblocks
            var t = lane * _P3_CHUNK
            while t < k_pack:
                var v = _ld4(wp, wbase + t // _P3_QUANTS_PER_WORD)
                var w = bitcast[DType.int32, 4](v)
                var xv0 = xs.load[width=4](t)
                var xv1 = xs.load[width=4](t + 4)
                var xv2 = xs.load[width=4](t + 8)

                var blk = t >> 5
                var s0 = wscale[sbase + blk]
                var z0 = wzero[sbase + blk]
                var s_lo = s0
                var z_lo = z0
                var s_hi = s0
                var z_hi = z0
                if cross_hi:
                    s_hi = wscale[sbase + blk + 1]
                    z_hi = wzero[sbase + blk + 1]
                    if cross_lo:
                        s_lo = s_hi
                        z_lo = z_hi

                # The same 12 dequant+mac terms as v2, regrouped into three 4-deep chains.
                acc0 += xv0[0] * ((Float32(w[0] & 255) - z0) * s0)
                acc1 += xv0[1] * ((Float32((w[0] >> 8) & 255) - z0) * s0)
                acc2 += xv0[2] * ((Float32((w[0] >> 16) & 255) - z0) * s0)
                acc0 += xv0[3] * ((Float32(w[1] & 255) - z0) * s0)
                acc1 += xv1[0] * ((Float32((w[1] >> 8) & 255) - z_lo) * s_lo)
                acc2 += xv1[1] * ((Float32((w[1] >> 16) & 255) - z_lo) * s_lo)
                acc0 += xv1[2] * ((Float32(w[2] & 255) - z_lo) * s_lo)
                acc1 += xv1[3] * ((Float32((w[2] >> 8) & 255) - z_lo) * s_lo)
                acc2 += xv2[0] * ((Float32((w[2] >> 16) & 255) - z_hi) * s_hi)
                acc0 += xv2[1] * ((Float32(w[3] & 255) - z_hi) * s_hi)
                acc1 += xv2[2] * ((Float32((w[3] >> 8) & 255) - z_hi) * s_hi)
                acc2 += xv2[3] * ((Float32((w[3] >> 16) & 255) - z_hi) * s_hi)
                t += _LANES * _P3_CHUNK
        red[tid] = (acc0 + acc1) + acc2
        barrier()
        var st = _LANES // 2
        while st > 0:
            if lane < st:
                red[tid] = red[tid] + red[tid + st]
            barrier()
            st //= 2
        if lane == 0 and j < n:
            var val = red[sub * _LANES]
            if val > best:
                best = val
                best_i = Int32(j)
        barrier()

    if lane == 0:
        sv[sub] = best
        si[sub] = best_i
    barrier()
    if tid == 0:
        var bv = sv[0]
        var bi = si[0]
        for u in range(1, _SUBS):
            # Strictly greater, so the lowest id survives an exact tie.
            if sv[u] > bv:
                bv = sv[u]
                bi = si[u]
        blk_val[Int(block_idx.x)] = bv
        blk_idx[Int(block_idx.x)] = bi


alias _I32P = UnsafePointer[Int32, origin=MutAnyOrigin]
"""The `blk_idx` buffer as a kernel parameter — `residentk.kernels`' `_IP` spelling."""


# ── host-side pack+upload helpers ──────────────────────────────────────────────


def _pack_transposed_f64_into_p3(
    dst_packed: DeviceBuffer[DType.float32],
    dst_scales: DeviceBuffer[DType.float32],
    dst_zeros: DeviceBuffer[DType.float32],
    src: List[Float64], k_in: Int, n_out: Int, row_off: Int,
) raises -> Int:
    """Narrow+TRANSPOSE `[k_in, n_out]` Float64 into `[n_out, k_in]` Float32 (the SAME
    transpose-once packing `_narrow_transposed_into` performs for the f32 half), pack through
    `residentk.kernels_packed3._pack_f32_to_packed3`, and upload the packed words + scales +
    zeros into the three device buffers starting at row `row_off`. The checkpoint on disk is
    `[in, out]`; the packed3 layout is per-row `[n, k]`, exactly as every residentk arm wants.

    One-time upload cost, paid at session load — the per-token path never sees Float64, and the
    Float32 values quantized here are EXACTLY the values the f32 session streams (same single
    Float64 -> Float32 narrowing), so the packed3 arm's only added error vs the f32 arm is the
    block-32 quantization itself.
    """
    if len(src) != k_in * n_out:
        return RESIDENT_ERR_UPLOAD_LENGTH
    # 7B-lane (enablement #5): pack STREAMING from the Float64 wire tensor — the transient
    # host footprint is one `k_in`-wide row buffer, not a whole-matrix Float32 copy. A 7B
    # gate/up matrix is 18944 x 3584 (67.9 M elements); the pre-streaming form held that
    # whole matrix as a second Float32 list on top of the Float64 source.
    var p = _p3_pack_from_f64(src, k_in, n_out, True)
    var pp = p.packed.unsafe_ptr()
    with dst_packed.map_to_host() as h:
        var off = row_off * p.words_per_row
        for i in range(n_out * p.words_per_row):
            h[off + i] = pp[i]
    var scp = p.scales.unsafe_ptr()
    with dst_scales.map_to_host() as h:
        var soff = row_off * p.nblocks
        for i in range(n_out * p.nblocks):
            h[soff + i] = scp[i]
    var zp = p.zeros.unsafe_ptr()
    with dst_zeros.map_to_host() as h:
        var zoff = row_off * p.nblocks
        for i in range(n_out * p.nblocks):
            h[zoff + i] = zp[i]
    return RESIDENT_OK


def _pack_f64_into_p3(
    dst_packed: DeviceBuffer[DType.float32],
    dst_scales: DeviceBuffer[DType.float32],
    dst_zeros: DeviceBuffer[DType.float32],
    src: List[Float64], k: Int, n: Int,
) raises -> Int:
    """The no-transpose twin: `src` is ALREADY `[n, k]` row-major Float64 (the tied
    embedding/lm_head table's checkpoint layout), narrowed to Float32, packed, uploaded.
    7B-lane (enablement #5): packs STREAMING — peak transient host memory is one `k`-wide
    row buffer, so the 7B lm_head (152064 x 3584 = 545 M elements) never materializes a
    whole-table Float32 copy."""
    if len(src) != n * k:
        return RESIDENT_ERR_UPLOAD_LENGTH
    var p = _p3_pack_from_f64(src, k, n, False)
    var pp = p.packed.unsafe_ptr()
    with dst_packed.map_to_host() as h:
        for i in range(n * p.words_per_row):
            h[i] = pp[i]
    var scp = p.scales.unsafe_ptr()
    with dst_scales.map_to_host() as h:
        for i in range(n * p.nblocks):
            h[i] = scp[i]
    var zp = p.zeros.unsafe_ptr()
    with dst_zeros.map_to_host() as h:
        for i in range(n * p.nblocks):
            h[i] = zp[i]
    return RESIDENT_OK


# ── the session ────────────────────────────────────────────────────────────────


@fieldwise_init
struct _LayerP3(Copyable, Movable):
    """One layer's packed3 decode twins — four roles x (packed words + block-32 scales +
    block-32 zeros), all Float32-typed device buffers because the packed word stream IS Float32
    words (bit-pattern containers, `residentk.kernels_packed3`'s Layout spec). The f32
    projection matrices, the norm weights and the KV cache live in the INNER f32 session's
    `_LayerGpu` — this struct holds ONLY what decode's packed3 dispatches read."""

    var p3_qkv: DeviceBuffer[DType.float32]
    var p3_qkv_s: DeviceBuffer[DType.float32]
    var p3_qkv_z: DeviceBuffer[DType.float32]
    var p3_o: DeviceBuffer[DType.float32]
    var p3_o_s: DeviceBuffer[DType.float32]
    var p3_o_z: DeviceBuffer[DType.float32]
    var p3_gu: DeviceBuffer[DType.float32]
    var p3_gu_s: DeviceBuffer[DType.float32]
    var p3_gu_z: DeviceBuffer[DType.float32]
    var p3_down: DeviceBuffer[DType.float32]
    var p3_down_s: DeviceBuffer[DType.float32]
    var p3_down_z: DeviceBuffer[DType.float32]


@fieldwise_init
struct _CudaResidentQwen3P3(Movable):
    """The packed3 decode twin of `_CudaResidentQwen3`: the inner f32 session, held BY VALUE,
    supplies everything the f32 chain needs — the prefill pass (delegated wholesale), the
    decode embed gather, the norm weights, RoPE tables, the f32 KV cache, every scratch buffer,
    and the f32 projection matrices the f32 prefill GEMMs read — and this struct adds ONLY the
    packed3 weight twins the `step_p3` chain streams. Same residency discipline as the inner
    session: everything allocated ONCE, alive for the session's life, in the same struct as its
    context.

    `Movable` is mandatory for the same reason the inner session's own docstring gives.
    """

    var f32: _CudaResidentQwen3
    var layers_p3: List[_LayerP3]
    var p3_lm: DeviceBuffer[DType.float32]
    var p3_lm_s: DeviceBuffer[DType.float32]
    var p3_lm_z: DeviceBuffer[DType.float32]
    # JIT-dequant prefill staging (7B memory fit; allocated only with skip_f32_projections=1 —
    # or ALWAYS under TC_SHIM_BUILD, where the sub-threshold prefill tiles fall back to the
    # JIT-dequant plan in BOTH residency modes)
    var stg_qkv: DeviceBuffer[DType.float32]
    var stg_o: DeviceBuffer[DType.float32]
    var stg_gu: DeviceBuffer[DType.float32]
    var stg_down: DeviceBuffer[DType.float32]

    # ── TC escape-hatch prefill (feat/tc-int): the packed3->f16 dual-resident weight tables
    #    the cuBLAS HMMA GEMMs read, plus the per-tile staging scratch. Allocated at REAL size
    #    ONLY under TC_SHIM_BUILD (the VRAM headroom check: the dual residency is +1.02 GB at
    #    0.6B / +15.24 GB at 7B-scale, measured by the probe); every other build holds
    #    1-element placeholders and `tc_staged = -1` — the native chain, byte-unmodified.
    #    `tc_staged`: 0 = allocated, staging pending; 1 = staged and dispatching; -1 = absent
    #    (build flag off OR the headroom allocation failed — fallback recorded, never fatal).
    var w16_qkv: List[DeviceBuffer[DType.float16]]
    var w16_o: List[DeviceBuffer[DType.float16]]
    var w16_gu: List[DeviceBuffer[DType.float16]]
    var w16_down: List[DeviceBuffer[DType.float16]]
    var tc_a16: DeviceBuffer[DType.float16]
    var tc_c16: DeviceBuffer[DType.float16]
    var tc_gu: DeviceBuffer[DType.float32]
    var tc_staged: Int

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
        qk_norm: Int = 1, has_lm_head: Int = 0, skip_f32_projections: Int = 0,
        has_qkv_bias: Int = 0,
    ) raises:
        """Open the inner f32 session (context + every f32 buffer, ONCE) and allocate the
        packed3 decode twins beside it. Called only from inside a `@parameter if
        CUDA_SESSION_BUILD` branch — the constructor cannot carry the gate itself, the same
        structural protection the inner session's constructor documents. The caller must have
        validated the shape with `residentk_dims_check` first (via `_resident_preflight`).

        The 7B-lane flags (`qk_norm`, `has_lm_head`, `skip_f32_projections`, `has_qkv_bias`)
        forward verbatim to the inner f32 session's constructor; with `skip_f32_projections=1`
        this struct additionally allocates the four JIT-dequant staging buffers `prefill`
        dequantizes each layer's packed3 matrices into (the inner session's f32 projections
        stay 1-element placeholders — a 7B's dual residency exceeds a 40 GB device)."""
        self.f32 = _CudaResidentQwen3(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, max_ctx, eps, scale,
            qk_norm, has_lm_head, skip_f32_projections, has_qkv_bias,
        )

        var n_q = h_q * d_head
        var n_kv = h_kv * d_head
        var n_qkv = n_q + 2 * n_kv

        # ── packed3 buffer sizes, per role (layout arithmetic carried by kernels_packed3's
        #    helpers so this file never re-derives it): words/row = k_pack/3, blocks/row =
        #    ceil(k_pack/32), both identical for qkv/gu (k = d_model) and for o/down's
        #    distinct k's ──
        var qkv_words = n_qkv * _p3_words_per_row(d_model)
        var qkv_meta = n_qkv * _p3_blocks_per_row(d_model)
        var o_words = d_model * _p3_words_per_row(n_q)
        var o_meta = d_model * _p3_blocks_per_row(n_q)
        var gu_words = 2 * d_ff * _p3_words_per_row(d_model)
        var gu_meta = 2 * d_ff * _p3_blocks_per_row(d_model)
        var down_words = d_model * _p3_words_per_row(d_ff)
        var down_meta = d_model * _p3_blocks_per_row(d_ff)

        self.layers_p3 = List[_LayerP3]()
        for _ in range(n_layers):
            self.layers_p3.append(
                _LayerP3(
                    self.f32.ctx.enqueue_create_buffer[DType.float32](qkv_words),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](qkv_meta),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](qkv_meta),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](o_words),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](o_meta),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](o_meta),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](gu_words),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](gu_meta),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](gu_meta),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](down_words),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](down_meta),
                    self.f32.ctx.enqueue_create_buffer[DType.float32](down_meta),
                )
            )

        self.p3_lm = self.f32.ctx.enqueue_create_buffer[DType.float32](
            vocab * _p3_words_per_row(d_model)
        )
        self.p3_lm_s = self.f32.ctx.enqueue_create_buffer[DType.float32](
            vocab * _p3_blocks_per_row(d_model)
        )
        self.p3_lm_z = self.f32.ctx.enqueue_create_buffer[DType.float32](
            vocab * _p3_blocks_per_row(d_model)
        )

        var stg_full = skip_f32_projections == 1
        @parameter
        if TC_SHIM_BUILD:
            # Sub-threshold prefill tiles run the JIT-dequant plan as their fallback in BOTH
            # residency modes, so the staging buffers must exist at full size either way.
            stg_full = True
        if stg_full:
            self.stg_qkv = self.f32.ctx.enqueue_create_buffer[DType.float32](n_qkv * d_model)
            self.stg_o = self.f32.ctx.enqueue_create_buffer[DType.float32](d_model * n_q)
            self.stg_gu = self.f32.ctx.enqueue_create_buffer[DType.float32](2 * d_ff * d_model)
            self.stg_down = self.f32.ctx.enqueue_create_buffer[DType.float32](d_model * d_ff)
        else:
            self.stg_qkv = self.f32.ctx.enqueue_create_buffer[DType.float32](1)
            self.stg_o = self.f32.ctx.enqueue_create_buffer[DType.float32](1)
            self.stg_gu = self.f32.ctx.enqueue_create_buffer[DType.float32](1)
            self.stg_down = self.f32.ctx.enqueue_create_buffer[DType.float32](1)

        # ── TC escape-hatch residency: the constructor allocates ONLY placeholders (every
        #    build, cheap); `tc_staged = 0` under the build flag marks the lazy path in
        #    `_tc_stage_weights`, which performs the REAL allocation inside its headroom
        #    try/except on the first prefill (a constructor cannot borrow self inside a try
        #    before every field is initialized — Mojo's definite-initialization refuses it).
        self.w16_qkv = List[DeviceBuffer[DType.float16]]()
        self.w16_o = List[DeviceBuffer[DType.float16]]()
        self.w16_gu = List[DeviceBuffer[DType.float16]]()
        self.w16_down = List[DeviceBuffer[DType.float16]]()
        self.tc_a16 = self.f32.ctx.enqueue_create_buffer[DType.float16](1)
        self.tc_c16 = self.f32.ctx.enqueue_create_buffer[DType.float16](1)
        self.tc_gu = self.f32.ctx.enqueue_create_buffer[DType.float32](1)
        self.tc_staged = -1
        @parameter
        if TC_SHIM_BUILD:
            self.tc_staged = 0

    def _tc_alloc(
        mut self, n_layers: Int, n_qkv: Int, n_q: Int, d_model: Int, d_ff: Int,
    ) raises:
        """The REAL TC residency (called inside the constructor's headroom try): one dense
        f16 `[rows, k]` table per role per layer (the probe's measured dual-residency delta:
        +1.02 GB at 0.6B, +15.24 GB at 7B-scale) plus the tile scratch — `tc_a16` holds the
        per-call A staging at the widest K, `tc_c16` the rung-2 f16-C staging at the widest
        N, `tc_gu` the `[rows, 2*d_ff]` f32 gate/up result the swiglu epilogue reads. Rows
        are capped at the inner session's prefill scratch rows (`_B1_PF_ROWS`), the largest
        tile `prefill` can ever dispatch."""
        var rows = _B1_PF_ROWS
        var max_k = d_model
        if n_q > max_k:
            max_k = n_q
        if d_ff > max_k:
            max_k = d_ff
        var max_n = n_qkv
        if 2 * d_ff > max_n:
            max_n = 2 * d_ff
        for _ in range(n_layers):
            self.w16_qkv.append(
                self.f32.ctx.enqueue_create_buffer[DType.float16](n_qkv * d_model))
            self.w16_o.append(
                self.f32.ctx.enqueue_create_buffer[DType.float16](d_model * n_q))
            self.w16_gu.append(
                self.f32.ctx.enqueue_create_buffer[DType.float16](2 * d_ff * d_model))
            self.w16_down.append(
                self.f32.ctx.enqueue_create_buffer[DType.float16](d_model * d_ff))
        self.tc_a16 = self.f32.ctx.enqueue_create_buffer[DType.float16](rows * max_k)
        self.tc_c16 = self.f32.ctx.enqueue_create_buffer[DType.float16](rows * max_n)
        self.tc_gu = self.f32.ctx.enqueue_create_buffer[DType.float32](rows * 2 * d_ff)

    def device_name(self) raises -> String:
        return self.f32.device_name()

    def dispatch_budget(self) -> Int:
        """The DECODE budget — `n_layers * 6 + 3`, UNCHANGED from the f32 session: `step_p3`
        issues exactly the f32 chain's dispatch shape (module docstring, substitution table).
        Prefill's budget is reported by the delegated `prefill` itself."""
        return residentk_dispatch_budget(self.f32.n_layers)

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The embedding table, the final norm gain, and the RoPE tables.

        TWO uploads happen for a TIED checkpoint (Qwen3): the inner f32 session's own
        `upload_globals` (embed stays f32 — the decode embed gather and the f32 prefill's
        embed read it), then the packed3 twin of the SAME tied table as lm_head weights for
        `step_p3` (no transpose — the checkpoint's `[vocab, d_model]` is already the packed
        layout's `[n, k]`).

        For an UNTIED checkpoint (`has_lm_head=1`, Qwen2.5-7B) the embed table is NOT the
        lm_head — this method uploads embed as embed only, and the caller follows with
        `upload_lm_head`, which fills BOTH the inner f32 lm_head table and its packed3 twin."""
        var s = self.f32.upload_globals(embed, final_norm, cos_t, sin_t, n_pos)
        if s != RESIDENT_OK:
            return s
        if self.f32.has_lm_head == 1:
            return RESIDENT_OK
        s = _pack_f64_into_p3(
            self.p3_lm, self.p3_lm_s, self.p3_lm_z,
            embed, self.f32.d_model, self.f32.vocab,
        )
        if s != RESIDENT_OK:
            return s
        return RESIDENT_OK

    def upload_lm_head(mut self, lm: List[Float64]) raises -> Int:
        """The SEPARATE lm_head table (7B-lane enablement, 2026-08-22): the untied
        `lm_head.weight`, uploaded TWICE — narrowed into the inner f32 session's `lm_head`
        buffer (the f32 arm's lm_head+argmax binds it) and packed into this session's
        `p3_lm` twin (the packed3 decode arm's `_lmhead_argmax_kernel_p3` binds it). Refused
        unless the session was opened with `has_lm_head=1`."""
        if self.f32.has_lm_head != 1:
            return RESIDENT_ERR_UPLOAD_LENGTH
        var s = self.f32.upload_lm_head(lm)
        if s != RESIDENT_OK:
            return s
        return _pack_f64_into_p3(
            self.p3_lm, self.p3_lm_s, self.p3_lm_z,
            lm, self.f32.d_model, self.f32.vocab,
        )

    def upload_qkv_bias(
        mut self, layer: Int, q_bias: List[Float64], k_bias: List[Float64],
        v_bias: List[Float64],
    ) raises -> Int:
        """One layer's q/k/v projection biases (7B-lane, 2026-08-23) — delegated to the inner
        f32 session's `upload_qkv_bias` (the bias vector is small, stays f32 there, and is read
        by the SAME `_qkv_bias_add_rows_kernel` dispatch both the JIT-dequant prefill and the
        packed3 decode chain insert after their QKV projection). Refused unless the session was
        opened with `has_qkv_bias=1`."""
        return self.f32.upload_qkv_bias(layer, q_bias, k_bias, v_bias)

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """One layer's eleven checkpoint tensors — TWICE: the inner f32 session's own
        `upload_layer` (the f32 matrices the prefill GEMMs read, unchanged), then the packed3
        twins of the four projection roles, packed row-wise from the SAME Float64 wire tensors:

        * qkv: q, k, v rows packed into ONE `[n_qkv, d_model]` buffer at row offsets
          0 / n_q / n_q+n_kv — the layout is per-row, so concatenation is a row-offset
          arithmetic, exactly the concatenation the f32 half performs;
        * o_proj: `[d_model, n_q]` (k = n_q = h_q * d_head);
        * gate/up: gate rows 0..d_ff, up rows d_ff..2*d_ff of ONE `[2*d_ff, d_model]` buffer;
        * down_proj: `[d_model, d_ff]` (k = d_ff).

        Norm weights (ln1/ln2/qn/kn) are tiny and stay f32 in the inner session only."""
        if layer < 0 or layer >= self.f32.n_layers:
            return RESIDENT_ERR_UPLOAD_LENGTH
        var s = self.f32.upload_layer(
            layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wgate, wup, wdown
        )
        if s != RESIDENT_OK:
            return s

        ref lp = self.layers_p3[layer]
        var n_q = self.f32.h_q * self.f32.d_head
        var n_kv = self.f32.h_kv * self.f32.d_head
        var d_model = self.f32.d_model
        var d_ff = self.f32.d_ff

        s = _pack_transposed_f64_into_p3(
            lp.p3_qkv, lp.p3_qkv_s, lp.p3_qkv_z, wq, d_model, n_q, 0
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_qkv, lp.p3_qkv_s, lp.p3_qkv_z, wk, d_model, n_kv, n_q
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_qkv, lp.p3_qkv_s, lp.p3_qkv_z, wv, d_model, n_kv, n_q + n_kv
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_o, lp.p3_o_s, lp.p3_o_z, wo, n_q, d_model, 0
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_gu, lp.p3_gu_s, lp.p3_gu_z, wgate, d_model, d_ff, 0
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_gu, lp.p3_gu_s, lp.p3_gu_z, wup, d_model, d_ff, d_ff
        )
        if s != RESIDENT_OK:
            return s
        s = _pack_transposed_f64_into_p3(
            lp.p3_down, lp.p3_down_s, lp.p3_down_z, wdown, d_ff, d_model, 0
        )
        if s != RESIDENT_OK:
            return s
        return RESIDENT_OK

    def seal(mut self) raises -> Int:
        """Drain every upload (f32 AND packed3) before the first dispatch. One synchronize for
        the whole load — the inner session's context owns both halves."""
        return self.f32.seal()

    def _tc_stage_weights(mut self) raises:
        """The ONE-TIME session-open TC enablement the prefill amortizes, lazy on the first
        `prefill` (every packed3 byte is resident by then — the driver's `seal` has drained
        the uploads): (1) the VRAM headroom check — allocate the REAL f16 dual residency +
        scratch (the constructor holds placeholders only; probe-measured delta +1.02 GB at
        0.6B / +15.24 GB at 7B-scale); failure demotes the session to the native chain for
        life with a printed record, never fatal. (2) `tc_shim_init` (cuBLAS handle on Mojo's
        context). (3) every layer's four packed3 tables dequantized to their dense f16
        twins by `tc_shim_dequant_packed3_f16_dense` (probe-measured cost: 5.55 ms at 0.6B
        / 55.4 ms at 7B-scale on A100 — repaid inside ~8 prefill waves at the per-call
        GEMM savings). Any non-zero status demotes with a printed record; a staged session
        prints its cost + the dual-residency delta."""
        if self.tc_staged != 0:
            return
        var n_q = self.f32.h_q * self.f32.d_head
        var n_kv = self.f32.h_kv * self.f32.d_head
        var n_qkv = n_q + 2 * n_kv
        var d_model = self.f32.d_model
        var d_ff = self.f32.d_ff
        try:
            self._tc_alloc(self.f32.n_layers, n_qkv, n_q, d_model, d_ff)
        except e:
            print("TC: VRAM headroom check FAILED — the f16 dual residency could not be",
                  "allocated; prefill stays on the native chain. Recorded:", e)
            self.tc_staged = -1
            return
        var t0 = perf_counter_ns()
        var r = _tc_init()
        if r != 0:
            print("TC: tc_shim_init failed:", r, "last_error:", _tc_last_error(),
                  "| prefill stays on the native chain")
            self.tc_staged = -1
            return
        @parameter
        if TC_NOSEAM:
            r = _tc_noseam(1)
            if r != 0:
                print("TC: tc_shim_noseam failed:", r, "last_error:", _tc_last_error(),
                      "| prefill stays on the native chain (NOSEAM is all-or-nothing —",
                      "the seam-skip and the legacy-stream switch must both hold)")
                self.tc_staged = -1
                return
        for layer in range(self.f32.n_layers):
            ref lp = self.layers_p3[layer]
            r = _tc_dequant_packed3_f16_dense(
                Int(lp.p3_qkv.unsafe_ptr()), Int(lp.p3_qkv_s.unsafe_ptr()),
                Int(lp.p3_qkv_z.unsafe_ptr()), Int(self.w16_qkv[layer].unsafe_ptr()),
                n_qkv, d_model, _p3_words_per_row(d_model), _p3_blocks_per_row(d_model))
            if r == 0:
                r = _tc_dequant_packed3_f16_dense(
                    Int(lp.p3_o.unsafe_ptr()), Int(lp.p3_o_s.unsafe_ptr()),
                    Int(lp.p3_o_z.unsafe_ptr()), Int(self.w16_o[layer].unsafe_ptr()),
                    d_model, n_q, _p3_words_per_row(n_q), _p3_blocks_per_row(n_q))
            if r == 0:
                r = _tc_dequant_packed3_f16_dense(
                    Int(lp.p3_gu.unsafe_ptr()), Int(lp.p3_gu_s.unsafe_ptr()),
                    Int(lp.p3_gu_z.unsafe_ptr()), Int(self.w16_gu[layer].unsafe_ptr()),
                    2 * d_ff, d_model, _p3_words_per_row(d_model),
                    _p3_blocks_per_row(d_model))
            if r == 0:
                r = _tc_dequant_packed3_f16_dense(
                    Int(lp.p3_down.unsafe_ptr()), Int(lp.p3_down_s.unsafe_ptr()),
                    Int(lp.p3_down_z.unsafe_ptr()), Int(self.w16_down[layer].unsafe_ptr()),
                    d_model, d_ff, _p3_words_per_row(d_ff), _p3_blocks_per_row(d_ff))
            if r != 0:
                print("TC: packed3->f16 staging FAILED at layer", layer, "status", r,
                      "last_error:", _tc_last_error(), "| prefill stays on the native chain")
                self.tc_staged = -1
                return
        self.f32.ctx.synchronize()
        self.tc_staged = 1
        var f16_bytes = Float64(self.f32.n_layers) * Float64(
            n_qkv * d_model + d_model * n_q + 2 * d_ff * d_model + d_model * d_ff) * 2.0
        print("TC: prefill f16 dual residency STAGED |",
              Float64(perf_counter_ns() - t0) / 1.0e6, "ms one-time | dequant tables:",
              f16_bytes / 1.0e9, "GB | compute mode:", TC_ACC_MODE)

    def _prefill_tc(mut self, prompt_ids: List[Int]) raises -> _StepOut:
        """The TC escape-hatch prefill — called ONLY with `tc_staged == 1` under
        `TC_SHIM_BUILD` (both call sites above gate on it). Per tile of `m` rows:

        * `m >= TC_MIN_M` (128, runtime — the FINAL tile carries whatever rows remain): the
          four projection roles dispatch through `_tc_gemm_dispatch` (cuBLAS f16 HMMA,
          COMPUTE_32F + f32 C by default) over the staged f16 tables — qkv ASSIGN, o_proj
          ACCUMULATE (beta 1 into the f32 residual), gate/up ASSIGN into the `tc_gu` scratch
          followed by the native `_pf_swiglu_rows_kernel` epilogue, down_proj ACCUMULATE.
          Every shim call is bracketed by the probe's seam: `ctx.synchronize()` before, the
          shim stream-syncs before returning. Attention, RoPE, norms, the qkv bias and the
          lm_head tail stay the native kernels, byte-unmodified.
        * `m < TC_MIN_M`: the JIT-dequant plan (the 7B path's layer plan, verbatim) — it
          works in BOTH residency modes because `stg_*` exist at full size under this build.

        The tail matches the residency mode the oracle gates: `skip_f32_projections=1` ends
        on the packed3 lm_head + argmax (the 7B arm's convention); the f32-resident mode
        ends on the f32 lm_head + argmax (the delegation path's convention, kept so the
        0.6B oracle's first token is produced by the identical weights it always was)."""
        @parameter
        if not TC_SHIM_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            var n_prompt = len(prompt_ids)
            var n_q = self.f32.h_q * self.f32.d_head
            var n_kv = self.f32.h_kv * self.f32.d_head
            var n_qkv = n_q + 2 * n_kv
            var issued = 0
            var pos = 0
            var last_m = 0
            while pos < n_prompt:
                var m = CUDA_PREFILL_TILE
                @parameter
                if CUDA_PREFILL_ONEPASS_B1:
                    m = _B1_PASS_MAX
                if n_prompt - pos < m:
                    m = n_prompt - pos
                last_m = m
                var use_tc = m >= TC_MIN_M

                # ── this chunk's token ids, uploaded once ──
                with self.f32.pf_tokens.map_to_host() as h:
                    for i in range(m):
                        h[i] = Int32(prompt_ids[pos + i])
                self.f32.ctx.synchronize()

                # ── the embedding rows, gathered on-device from the resident f32 table ──
                self.f32.ctx.enqueue_function[_pf_embed_rows_kernel](
                    self.f32.pf_hidden.unsafe_ptr(), self.f32.embed.unsafe_ptr(),
                    self.f32.pf_tokens.unsafe_ptr(),
                    Int64(self.f32.d_model), Int64(m),
                    grid_dim=_ceil_div(self.f32.d_model, _TG) * m, block_dim=_TG,
                )
                issued += 1

                for layer in range(self.f32.n_layers):
                    ref lw = self.f32.layers[layer]
                    ref lp = self.layers_p3[layer]

                    if use_tc:
                        # ══ TC LAYER PLAN ══
                        # 1 ── rmsnorm(input_layernorm) over every row (native)
                        self.f32.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                            self.f32.pf_xn.unsafe_ptr(), self.f32.pf_hidden.unsafe_ptr(),
                            lw.ln1.unsafe_ptr(),
                            Int64(self.f32.d_model), self.f32.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                        # 2 ── qkv ASSIGN through the TC seam (the ctx.synchronize() seam:
                        #      drain Mojo's stream, the shim stream-syncs before returning;
                        #      NOSEAM drops both halves — legacy-stream ordering instead)
                        @parameter
                        if not TC_NOSEAM:
                            self.f32.ctx.synchronize()
                        var r = _tc_gemm_dispatch(
                            Int(self.f32.pf_xn.unsafe_ptr()),
                            Int(self.w16_qkv[layer].unsafe_ptr()),
                            Int(lw.w_qkv.unsafe_ptr())
                            if self.f32.skip_f32_projections != 1 else 0,
                            m, self.f32.d_model, n_qkv,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.f32.pf_qkv.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        # 2b ── 7B-lane attention bias (native, before RoPE)
                        if self.f32.has_qkv_bias == 1:
                            self.f32.ctx.enqueue_function[_qkv_bias_add_rows_kernel](
                                self.f32.pf_qkv.unsafe_ptr(),
                                self.f32.qkv_biases[layer].unsafe_ptr(),
                                Int64(m), Int64(n_qkv),
                                grid_dim=_ceil_div(m * n_qkv, _TG), block_dim=_TG,
                            )
                            issued += 1
                        # 3 ── q_norm + k_norm + RoPE + the in-place KV-cache write
                        self.f32.ctx.enqueue_function[_pf_ropewrt_kernel](
                            self.f32.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(),
                            lw.cv.unsafe_ptr(),
                            self.f32.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(),
                            lw.kn.unsafe_ptr(),
                            self.f32.cos_t.unsafe_ptr(), self.f32.sin_t.unsafe_ptr(),
                            Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                            Int64(self.f32.d_head), self.f32.eps, Int64(m),
                            Int64(self.f32.qk_norm),
                            grid_dim=(self.f32.h_q + self.f32.h_kv) * m,
                            block_dim=self.f32.d_head,
                        )
                        # 4 ── causal attention, the SAME native selection f32.prefill runs
                        #      (flash2 under L-H4, flash under L-H3, tiled otherwise)
                        @parameter
                        if CUDA_PREFILL_FLASH_B1:
                            if self.f32.d_head == 128 and CUDA_PREFILL_FLASH2_B1:
                                self.f32.ctx.enqueue_function[_pf_attn_flash2_kernel](
                                    self.f32.pf_attn.unsafe_ptr(),
                                    self.f32.pf_q_rot.unsafe_ptr(),
                                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                                    Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                                    Int64(self.f32.d_head),
                                    self.f32.scale, Int64(m),
                                    grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK)
                                    * self.f32.h_q,
                                    block_dim=_PF_FLASH_NTHREADS,
                                )
                            elif self.f32.d_head == 128:
                                self.f32.ctx.enqueue_function[_pf_attn_flash_kernel](
                                    self.f32.pf_attn.unsafe_ptr(),
                                    self.f32.pf_q_rot.unsafe_ptr(),
                                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                                    Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                                    Int64(self.f32.d_head),
                                    self.f32.scale, Int64(m),
                                    grid_dim=_ceil_div(m, _PF_FLASH_ROWS_PER_BLOCK)
                                    * self.f32.h_q,
                                    block_dim=_PF_FLASH_NTHREADS,
                                )
                            else:
                                self.f32.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                                    self.f32.pf_attn.unsafe_ptr(),
                                    self.f32.pf_q_rot.unsafe_ptr(),
                                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                                    Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                                    Int64(self.f32.d_head),
                                    self.f32.scale, Int64(m),
                                    grid_dim=self.f32.h_q * m, block_dim=self.f32.d_head,
                                )
                        else:
                            self.f32.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                                self.f32.pf_attn.unsafe_ptr(),
                                self.f32.pf_q_rot.unsafe_ptr(),
                                lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                                Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                                Int64(self.f32.d_head), self.f32.scale, Int64(m),
                                grid_dim=self.f32.h_q * m, block_dim=self.f32.d_head,
                            )
                        # 5 ── o_proj ACCUMULATE into the residual through the TC seam
                        @parameter
                        if not TC_NOSEAM:
                            self.f32.ctx.synchronize()
                        r = _tc_gemm_dispatch(
                            Int(self.f32.pf_attn.unsafe_ptr()),
                            Int(self.w16_o[layer].unsafe_ptr()),
                            Int(lw.w_o.unsafe_ptr())
                            if self.f32.skip_f32_projections != 1 else 0,
                            m, n_q, self.f32.d_model,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.f32.pf_hidden.unsafe_ptr()), 1)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        # 6 ── rmsnorm(post_attention_layernorm) (native)
                        self.f32.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                            self.f32.pf_xn.unsafe_ptr(), self.f32.pf_hidden.unsafe_ptr(),
                            lw.ln2.unsafe_ptr(),
                            Int64(self.f32.d_model), self.f32.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                        # 7 ── gate/up ASSIGN through the TC seam + native SwiGLU epilogue
                        @parameter
                        if not TC_NOSEAM:
                            self.f32.ctx.synchronize()
                        r = _tc_gemm_dispatch(
                            Int(self.f32.pf_xn.unsafe_ptr()),
                            Int(self.w16_gu[layer].unsafe_ptr()),
                            Int(lw.w_gu.unsafe_ptr())
                            if self.f32.skip_f32_projections != 1 else 0,
                            m, self.f32.d_model, 2 * self.f32.d_ff,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.tc_gu.unsafe_ptr()), 0)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        self.f32.ctx.enqueue_function[_pf_swiglu_rows_kernel](
                            self.f32.pf_act.unsafe_ptr(), self.tc_gu.unsafe_ptr(),
                            Int64(m * self.f32.d_ff), Int64(self.f32.d_ff),
                            grid_dim=_ceil_div(m * self.f32.d_ff, _TG), block_dim=_TG,
                        )
                        # 8 ── down_proj ACCUMULATE into the residual through the TC seam
                        @parameter
                        if not TC_NOSEAM:
                            self.f32.ctx.synchronize()
                        r = _tc_gemm_dispatch(
                            Int(self.f32.pf_act.unsafe_ptr()),
                            Int(self.w16_down[layer].unsafe_ptr()),
                            Int(lw.w_down.unsafe_ptr())
                            if self.f32.skip_f32_projections != 1 else 0,
                            m, self.f32.d_ff, self.f32.d_model,
                            Int(self.tc_a16.unsafe_ptr()), Int(self.tc_c16.unsafe_ptr()),
                            Int(self.f32.pf_hidden.unsafe_ptr()), 1)
                        if r != 0:
                            return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
                        issued += 8
                    else:
                        # ══ sub-threshold tile: the JIT-dequant plan, verbatim ══
                        self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                            self.stg_qkv.unsafe_ptr(), lp.p3_qkv.unsafe_ptr(),
                            lp.p3_qkv_s.unsafe_ptr(), lp.p3_qkv_z.unsafe_ptr(),
                            Int64(self.f32.d_model), Int64(n_qkv),
                            grid_dim=n_qkv, block_dim=_TG,
                        )
                        self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                            self.stg_o.unsafe_ptr(), lp.p3_o.unsafe_ptr(),
                            lp.p3_o_s.unsafe_ptr(), lp.p3_o_z.unsafe_ptr(),
                            Int64(n_q), Int64(self.f32.d_model),
                            grid_dim=self.f32.d_model, block_dim=_TG,
                        )
                        self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                            self.stg_gu.unsafe_ptr(), lp.p3_gu.unsafe_ptr(),
                            lp.p3_gu_s.unsafe_ptr(), lp.p3_gu_z.unsafe_ptr(),
                            Int64(self.f32.d_model), Int64(2 * self.f32.d_ff),
                            grid_dim=2 * self.f32.d_ff, block_dim=_TG,
                        )
                        self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                            self.stg_down.unsafe_ptr(), lp.p3_down.unsafe_ptr(),
                            lp.p3_down_s.unsafe_ptr(), lp.p3_down_z.unsafe_ptr(),
                            Int64(self.f32.d_ff), Int64(self.f32.d_model),
                            grid_dim=self.f32.d_model, block_dim=_TG,
                        )
                        issued += 4
                        self.f32.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                            self.f32.pf_xn.unsafe_ptr(), self.f32.pf_hidden.unsafe_ptr(),
                            lw.ln1.unsafe_ptr(),
                            Int64(self.f32.d_model), self.f32.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                        self.f32.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                            self.f32.pf_qkv.unsafe_ptr(), self.f32.pf_xn.unsafe_ptr(),
                            self.stg_qkv.unsafe_ptr(),
                            Int64(m), Int64(self.f32.d_model), Int64(n_qkv),
                            grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                        if self.f32.has_qkv_bias == 1:
                            self.f32.ctx.enqueue_function[_qkv_bias_add_rows_kernel](
                                self.f32.pf_qkv.unsafe_ptr(),
                                self.f32.qkv_biases[layer].unsafe_ptr(),
                                Int64(m), Int64(n_qkv),
                                grid_dim=_ceil_div(m * n_qkv, _TG), block_dim=_TG,
                            )
                            issued += 1
                        self.f32.ctx.enqueue_function[_pf_ropewrt_kernel](
                            self.f32.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(),
                            lw.cv.unsafe_ptr(),
                            self.f32.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(),
                            lw.kn.unsafe_ptr(),
                            self.f32.cos_t.unsafe_ptr(), self.f32.sin_t.unsafe_ptr(),
                            Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                            Int64(self.f32.d_head), self.f32.eps, Int64(m),
                            Int64(self.f32.qk_norm),
                            grid_dim=(self.f32.h_q + self.f32.h_kv) * m,
                            block_dim=self.f32.d_head,
                        )
                        self.f32.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                            self.f32.pf_attn.unsafe_ptr(), self.f32.pf_q_rot.unsafe_ptr(),
                            lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                            Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                            Int64(self.f32.d_head), self.f32.scale, Int64(m),
                            grid_dim=self.f32.h_q * m, block_dim=self.f32.d_head,
                        )
                        self.f32.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                            self.f32.pf_hidden.unsafe_ptr(), self.f32.pf_attn.unsafe_ptr(),
                            self.stg_o.unsafe_ptr(),
                            Int64(m), Int64(n_q), Int64(self.f32.d_model),
                            grid_dim=_ceil_div(m, _G2_BM)
                            * _ceil_div(self.f32.d_model, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                        self.f32.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                            self.f32.pf_xn.unsafe_ptr(), self.f32.pf_hidden.unsafe_ptr(),
                            lw.ln2.unsafe_ptr(),
                            Int64(self.f32.d_model), self.f32.eps, Int64(m),
                            grid_dim=m, block_dim=_TG,
                        )
                        self.f32.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                            self.f32.pf_act.unsafe_ptr(), self.f32.pf_xn.unsafe_ptr(),
                            self.stg_gu.unsafe_ptr(),
                            Int64(m), Int64(self.f32.d_model), Int64(self.f32.d_ff),
                            grid_dim=_ceil_div(m, _G2_BM)
                            * _ceil_div(self.f32.d_ff, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                        self.f32.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                            self.f32.pf_hidden.unsafe_ptr(), self.f32.pf_act.unsafe_ptr(),
                            self.stg_down.unsafe_ptr(),
                            Int64(m), Int64(self.f32.d_ff), Int64(self.f32.d_model),
                            grid_dim=_ceil_div(m, _G2_BM)
                            * _ceil_div(self.f32.d_model, _G2_BN),
                            block_dim=_G2_NTHREADS,
                        )
                        issued += 8
                pos += m

            # ── final rmsnorm + lm_head + argmax on the LAST row — tail matches the
            #    residency mode's oracle convention (docstring) ──
            var n_iters = _ceil_div(self.f32.vocab, _LM_BLOCKS * _SUBS)
            if self.f32.skip_f32_projections == 1:
                self.f32.ctx.enqueue_function[_lmhead_argmax_kernel_p3](
                    self.f32.blk_val.unsafe_ptr(), self.f32.blk_idx.unsafe_ptr(),
                    self.f32.pf_hidden.unsafe_ptr() + (last_m - 1) * self.f32.d_model,
                    self.f32.final_norm.unsafe_ptr(),
                    self.p3_lm.unsafe_ptr(), self.p3_lm_s.unsafe_ptr(),
                    self.p3_lm_z.unsafe_ptr(),
                    Int64(self.f32.d_model), Int64(self.f32.vocab), self.f32.eps,
                    Int64(n_iters),
                    grid_dim=_LM_BLOCKS, block_dim=_TG,
                )
            else:
                var lm_w = self.f32.lm_head_w()
                self.f32.ctx.enqueue_function[_lmhead_argmax_kernel](
                    self.f32.blk_val.unsafe_ptr(), self.f32.blk_idx.unsafe_ptr(),
                    self.f32.pf_hidden.unsafe_ptr() + (last_m - 1) * self.f32.d_model,
                    self.f32.final_norm.unsafe_ptr(), lm_w,
                    Int64(self.f32.d_model), Int64(self.f32.vocab), self.f32.eps,
                    Int64(n_iters),
                    grid_dim=_LM_BLOCKS, block_dim=_TG,
                )
            self.f32.ctx.enqueue_function[_argmax_reduce_kernel](
                self.f32.out_val.unsafe_ptr(), self.f32.out_idx.unsafe_ptr(),
                self.f32.blk_val.unsafe_ptr(), self.f32.blk_idx.unsafe_ptr(),
                Int64(_LM_BLOCKS),
                grid_dim=1, block_dim=_TG,
            )
            issued += 2

            self.f32.ctx.enqueue_copy(self.f32.host_val, self.f32.out_val)
            self.f32.ctx.enqueue_copy(self.f32.host_idx, self.f32.out_idx)
            self.f32.ctx.synchronize()
            var tok = Int(self.f32.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.f32.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.f32.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)

    def prefill(mut self, prompt_ids: List[Int]) raises -> _StepOut:
        """The whole prompt.

        DEFAULT (f32 projections resident): DELEGATED WHOLESALE to the inner f32 session —
        the chunked batched m_rows prefill through `residentk.kernels_prefill_f32_v2`'s tiled
        GEMMs reading the resident f32 weights, ending in the f32 lm_head + argmax.

        7B MEMORY-FIT (skip_f32_projections=1): the f32 projections are NOT resident (a 7B's
        f32+packed3 dual residency exceeds a 40 GB device), so this runs the SAME chunked f32
        prefill plan with each layer's four projection matrices JIT-dequantized from their
        packed3 twins into the staging buffers immediately before that layer's GEMMs
        (`residentk.kernels_packed3._p3_dequant_rows_kernel`, one dequant dispatch per role —
        the kernel's docstring states the seam). Every arithmetic op the GEMMs run is
        therefore the packed3 decode arm's dequantized arithmetic; the tail is the packed3
        lm_head + argmax (not the f32 twin), so a 7B prefill+decode run streams packed3
        end-to-end. `pos` bookkeeping is the caller's, exactly as the f32 session's own
        `prefill` documents.

        TC ESCAPE HATCH (`-D ALGENTA_TC_SHIM`, feat/tc-int): with the shim staged
        (`tc_staged == 1`), BOTH residency modes run `_prefill_tc` instead — every tile of
        `TC_MIN_M` (128) rows or more dispatches its four projection GEMMs through the
        cuBLAS f16 tensor-core seam over the session-open packed3->f16 dual residency
        (attention, RoPE, norms, epilogues stay native; decode is untouched); sub-threshold
        tiles fall back to the JIT-dequant plan. Flag-off builds never reach any of it —
        the two legacy paths below are byte-unmodified."""
        @parameter
        if TC_SHIM_BUILD:
            self._tc_stage_weights()
        if self.f32.skip_f32_projections != 1:
            @parameter
            if TC_SHIM_BUILD:
                if self.tc_staged == 1:
                    return self._prefill_tc(prompt_ids)
            return self.f32.prefill(prompt_ids)

        @parameter
        if not CUDA_SESSION_BUILD:
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            var n_prompt = len(prompt_ids)
            if n_prompt < 1:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)
            if n_prompt > self.f32.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            for i in range(n_prompt):
                if prompt_ids[i] < 0 or prompt_ids[i] >= self.f32.vocab:
                    return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            @parameter
            if TC_SHIM_BUILD:
                if self.tc_staged == 1:
                    return self._prefill_tc(prompt_ids)

            var n_q = self.f32.h_q * self.f32.d_head
            var n_kv = self.f32.h_kv * self.f32.d_head
            var n_qkv = n_q + 2 * n_kv
            var issued = 0
            var pos = 0
            var last_m = 0
            while pos < n_prompt:
                var m = CUDA_PREFILL_TILE
                if n_prompt - pos < m:
                    m = n_prompt - pos
                last_m = m

                # ── this chunk's token ids, uploaded once ──
                with self.f32.pf_tokens.map_to_host() as h:
                    for i in range(m):
                        h[i] = Int32(prompt_ids[pos + i])
                self.f32.ctx.synchronize()

                # ── the embedding rows, gathered on-device from the resident f32 table ──
                self.f32.ctx.enqueue_function[_pf_embed_rows_kernel](
                    self.f32.pf_hidden.unsafe_ptr(), self.f32.embed.unsafe_ptr(),
                    self.f32.pf_tokens.unsafe_ptr(),
                    Int64(self.f32.d_model), Int64(m),
                    grid_dim=_ceil_div(self.f32.d_model, _TG) * m, block_dim=_TG,
                )
                issued += 1

                for layer in range(self.f32.n_layers):
                    ref lw = self.f32.layers[layer]
                    ref lp = self.layers_p3[layer]

                    # 0 ── JIT-dequant this layer's four packed3 matrices into staging ──
                    self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                        self.stg_qkv.unsafe_ptr(), lp.p3_qkv.unsafe_ptr(),
                        lp.p3_qkv_s.unsafe_ptr(), lp.p3_qkv_z.unsafe_ptr(),
                        Int64(self.f32.d_model), Int64(n_qkv),
                        grid_dim=n_qkv, block_dim=_TG,
                    )
                    self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                        self.stg_o.unsafe_ptr(), lp.p3_o.unsafe_ptr(),
                        lp.p3_o_s.unsafe_ptr(), lp.p3_o_z.unsafe_ptr(),
                        Int64(n_q), Int64(self.f32.d_model),
                        grid_dim=self.f32.d_model, block_dim=_TG,
                    )
                    self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                        self.stg_gu.unsafe_ptr(), lp.p3_gu.unsafe_ptr(),
                        lp.p3_gu_s.unsafe_ptr(), lp.p3_gu_z.unsafe_ptr(),
                        Int64(self.f32.d_model), Int64(2 * self.f32.d_ff),
                        grid_dim=2 * self.f32.d_ff, block_dim=_TG,
                    )
                    self.f32.ctx.enqueue_function[_p3_dequant_rows_kernel](
                        self.stg_down.unsafe_ptr(), lp.p3_down.unsafe_ptr(),
                        lp.p3_down_s.unsafe_ptr(), lp.p3_down_z.unsafe_ptr(),
                        Int64(self.f32.d_ff), Int64(self.f32.d_model),
                        grid_dim=self.f32.d_model, block_dim=_TG,
                    )
                    issued += 4

                    # 1 ── rmsnorm(input_layernorm) over every row
                    self.f32.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.f32.pf_xn.unsafe_ptr(), self.f32.pf_hidden.unsafe_ptr(),
                        lw.ln1.unsafe_ptr(),
                        Int64(self.f32.d_model), self.f32.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 2 ── fused Q/K/V projection, one tiled GEMM (ASSIGN) — staged weights
                    self.f32.ctx.enqueue_function[_pf_gemm_assign_kernel_v2](
                        self.f32.pf_qkv.unsafe_ptr(), self.f32.pf_xn.unsafe_ptr(),
                        self.stg_qkv.unsafe_ptr(),
                        Int64(m), Int64(self.f32.d_model), Int64(n_qkv),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(n_qkv, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 2b ── 7B-lane attention bias: q/k/v biases onto the QKV output BEFORE RoPE
                    # (dispatched only when the session carries biases; a Qwen3 session never
                    # reaches this launch).
                    if self.f32.has_qkv_bias == 1:
                        self.f32.ctx.enqueue_function[_qkv_bias_add_rows_kernel](
                            self.f32.pf_qkv.unsafe_ptr(),
                            self.f32.qkv_biases[layer].unsafe_ptr(),
                            Int64(m), Int64(n_qkv),
                            grid_dim=_ceil_div(m * n_qkv, _TG), block_dim=_TG,
                        )
                        issued += 1
                    # 3 ── q_norm + k_norm + RoPE + the in-place KV-cache write, every row
                    self.f32.ctx.enqueue_function[_pf_ropewrt_kernel](
                        self.f32.pf_q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        self.f32.pf_qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                        self.f32.cos_t.unsafe_ptr(), self.f32.sin_t.unsafe_ptr(),
                        Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                        Int64(self.f32.d_head), self.f32.eps, Int64(m),
                        Int64(self.f32.qk_norm),  # qk_norm: runtime flag (Qwen3=1; Qwen2.5/llama=0)
                        grid_dim=(self.f32.h_q + self.f32.h_kv) * m,
                        block_dim=self.f32.d_head,
                    )
                    # 4 ── causal attention, one threadgroup per (row, query head)
                    self.f32.ctx.enqueue_function[_pf_attn_tiled_kernel_simd](
                        self.f32.pf_attn.unsafe_ptr(), self.f32.pf_q_rot.unsafe_ptr(),
                        lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                        Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                        Int64(self.f32.d_head), self.f32.scale, Int64(m),
                        grid_dim=self.f32.h_q * m, block_dim=self.f32.d_head,
                    )
                    # 5 ── o_proj ACCUMULATED into the residual stream — staged weights
                    self.f32.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                        self.f32.pf_hidden.unsafe_ptr(), self.f32.pf_attn.unsafe_ptr(),
                        self.stg_o.unsafe_ptr(),
                        Int64(m), Int64(n_q), Int64(self.f32.d_model),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.f32.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 6 ── rmsnorm(post_attention_layernorm) over every row
                    self.f32.ctx.enqueue_function[_pf_rmsnorm_rows_kernel](
                        self.f32.pf_xn.unsafe_ptr(), self.f32.pf_hidden.unsafe_ptr(),
                        lw.ln2.unsafe_ptr(),
                        Int64(self.f32.d_model), self.f32.eps, Int64(m),
                        grid_dim=m, block_dim=_TG,
                    )
                    # 7 ── gate/up + SwiGLU, one tiled GEMM pair — staged weights
                    self.f32.ctx.enqueue_function[_pf_gemm_swiglu_kernel_v2](
                        self.f32.pf_act.unsafe_ptr(), self.f32.pf_xn.unsafe_ptr(),
                        self.stg_gu.unsafe_ptr(),
                        Int64(m), Int64(self.f32.d_model), Int64(self.f32.d_ff),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.f32.d_ff, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    # 8 ── down_proj ACCUMULATED into the residual stream — staged weights
                    self.f32.ctx.enqueue_function[_pf_gemm_accum_kernel_v2](
                        self.f32.pf_hidden.unsafe_ptr(), self.f32.pf_act.unsafe_ptr(),
                        self.stg_down.unsafe_ptr(),
                        Int64(m), Int64(self.f32.d_ff), Int64(self.f32.d_model),
                        grid_dim=_ceil_div(m, _G2_BM) * _ceil_div(self.f32.d_model, _G2_BN),
                        block_dim=_G2_NTHREADS,
                    )
                    issued += 8
                pos += m

            # ── final rmsnorm + packed3 lm_head + per-threadgroup argmax on the LAST row ──
            var n_iters = _ceil_div(self.f32.vocab, _LM_BLOCKS * _SUBS)
            self.f32.ctx.enqueue_function[_lmhead_argmax_kernel_p3](
                self.f32.blk_val.unsafe_ptr(), self.f32.blk_idx.unsafe_ptr(),
                self.f32.pf_hidden.unsafe_ptr() + (last_m - 1) * self.f32.d_model,
                self.f32.final_norm.unsafe_ptr(),
                self.p3_lm.unsafe_ptr(), self.p3_lm_s.unsafe_ptr(), self.p3_lm_z.unsafe_ptr(),
                Int64(self.f32.d_model), Int64(self.f32.vocab), self.f32.eps, Int64(n_iters),
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.f32.ctx.enqueue_function[_argmax_reduce_kernel](
                self.f32.out_val.unsafe_ptr(), self.f32.out_idx.unsafe_ptr(),
                self.f32.blk_val.unsafe_ptr(), self.f32.blk_idx.unsafe_ptr(),
                Int64(_LM_BLOCKS),
                grid_dim=1, block_dim=_TG,
            )
            issued += 2

            self.f32.ctx.enqueue_copy(self.f32.host_val, self.f32.out_val)
            self.f32.ctx.enqueue_copy(self.f32.host_idx, self.f32.out_idx)
            self.f32.ctx.synchronize()
            var tok = Int(self.f32.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.f32.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.f32.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)

    def step_p3(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE decode token through the packed3 chain — the f32 session's `step` dispatch plan
        with ONLY the four projection roles and the lm_head swapped to their packed3 twins
        (module docstring, substitution table): `_norm_gemv_kernel_p3` for the fused
        norm+qkv, this file's `_packed3_gemv_accum_kernel` for o_proj/down_proj, this file's
        `_norm_gemv2_swiglu_kernel_p3` for gate/up+SwiGLU, and this file's
        `_lmhead_argmax_kernel_p3` for the final norm + lm_head + per-threadgroup argmax.
        Embed gather, qk_norm+RoPE+KV write, attention, and the argmax reduce are dispatched
        BYTE-UNMODIFIED from `residentk.kernels` — f32 KV cache, f32 activations, unchanged.

        Same `_StepOut` contract as the f32 `step`, including the dispatch budget report:
        `1 + 6 * n_layers + 2` = `residentk_dispatch_budget(n_layers)`, checked by the driver
        every step."""

        @parameter
        if not CUDA_SESSION_BUILD:
            # Removed before shader codegen; this is what a non-CUDA build compiles and runs.
            return _StepOut(-1, 0.0, 0, RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.f32.max_ctx:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.f32.vocab:
                return _StepOut(-1, 0.0, 0, RESIDENT_ERR_UPLOAD_LENGTH)

            var n_q = self.f32.h_q * self.f32.d_head
            var n_kv = self.f32.h_kv * self.f32.d_head
            var n_qkv = n_q + 2 * n_kv
            var n_keys = pos + 1
            var issued = 0

            # ── the embedding row, gathered on-device from the resident f32 table ──
            self.f32.ctx.enqueue_function[_embed_row_kernel](
                self.f32.hidden.unsafe_ptr(), self.f32.embed.unsafe_ptr(),
                Int64(token_id), Int64(self.f32.d_model),
                grid_dim=_ceil_div(self.f32.d_model, _TG), block_dim=_TG,
            )
            issued += 1

            for layer in range(self.f32.n_layers):
                ref lw = self.f32.layers[layer]
                ref lp = self.layers_p3[layer]

                # 1 ── rmsnorm(input_layernorm) + fused Q/K/V projection — packed3
                self.f32.ctx.enqueue_function[_norm_gemv_kernel_p3](
                    self.f32.qkv.unsafe_ptr(), self.f32.hidden.unsafe_ptr(),
                    lw.ln1.unsafe_ptr(),
                    lp.p3_qkv.unsafe_ptr(), lp.p3_qkv_s.unsafe_ptr(),
                    lp.p3_qkv_z.unsafe_ptr(),
                    Int64(self.f32.d_model), Int64(n_qkv), self.f32.eps,
                    grid_dim=_ceil_div(n_qkv, _SUBS), block_dim=_TG,
                )
                # 1b ── 7B-lane attention bias: q/k/v biases onto the QKV output BEFORE RoPE
                # (dispatched only when the session carries biases; a Qwen3 session never
                # reaches this launch).
                if self.f32.has_qkv_bias == 1:
                    self.f32.ctx.enqueue_function[_qkv_bias_add_rows_kernel](
                        self.f32.qkv.unsafe_ptr(),
                        self.f32.qkv_biases[layer].unsafe_ptr(),
                        Int64(1), Int64(n_qkv),
                        grid_dim=_ceil_div(n_qkv, _TG), block_dim=_TG,
                    )
                    issued += 1
                # 2 ── q_norm + k_norm + RoPE + the in-place KV-cache slot write (unchanged)
                self.f32.ctx.enqueue_function[_qk_rope_write_kernel](
                    self.f32.q_rot.unsafe_ptr(), lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    self.f32.qkv.unsafe_ptr(), lw.qn.unsafe_ptr(), lw.kn.unsafe_ptr(),
                    self.f32.cos_t.unsafe_ptr(), self.f32.sin_t.unsafe_ptr(),
                    Int64(pos), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                    Int64(self.f32.d_head), self.f32.eps,
                    Int64(self.f32.qk_norm),  # qk_norm: runtime flag (Qwen3=1; Qwen2.5/llama=0)
                    grid_dim=self.f32.h_q + self.f32.h_kv, block_dim=self.f32.d_head,
                )
                # 3 ── attention over every cached key, online softmax (unchanged, f32 KV)
                self.f32.ctx.enqueue_function[_sdpa_kernel](
                    self.f32.attn_out.unsafe_ptr(), self.f32.q_rot.unsafe_ptr(),
                    lw.ck.unsafe_ptr(), lw.cv.unsafe_ptr(),
                    Int64(n_keys), Int64(self.f32.h_q), Int64(self.f32.h_kv),
                    Int64(self.f32.d_head), self.f32.scale,
                    grid_dim=self.f32.h_q, block_dim=self.f32.d_head,
                )
                # 4 ── o_proj + residual add — packed3 accum twin
                self.f32.ctx.enqueue_function[_packed3_gemv_accum_kernel](
                    self.f32.hidden.unsafe_ptr(), self.f32.attn_out.unsafe_ptr(),
                    lp.p3_o.unsafe_ptr(), lp.p3_o_s.unsafe_ptr(), lp.p3_o_z.unsafe_ptr(),
                    Int64(n_q), Int64(self.f32.d_model),
                    grid_dim=_ceil_div(self.f32.d_model, _SUBS), block_dim=_TG,
                )
                # 5 ── rmsnorm(post_attention_layernorm) + gate/up + SwiGLU — packed3 twin
                self.f32.ctx.enqueue_function[_norm_gemv2_swiglu_kernel_p3](
                    self.f32.act.unsafe_ptr(), self.f32.hidden.unsafe_ptr(),
                    lw.ln2.unsafe_ptr(),
                    lp.p3_gu.unsafe_ptr(), lp.p3_gu_s.unsafe_ptr(), lp.p3_gu_z.unsafe_ptr(),
                    Int64(self.f32.d_model), Int64(self.f32.d_ff), self.f32.eps,
                    grid_dim=_ceil_div(self.f32.d_ff, _SUBS), block_dim=_TG,
                )
                # 6 ── down_proj + residual add — packed3 accum twin
                self.f32.ctx.enqueue_function[_packed3_gemv_accum_kernel](
                    self.f32.hidden.unsafe_ptr(), self.f32.act.unsafe_ptr(),
                    lp.p3_down.unsafe_ptr(), lp.p3_down_s.unsafe_ptr(),
                    lp.p3_down_z.unsafe_ptr(),
                    Int64(self.f32.d_ff), Int64(self.f32.d_model),
                    grid_dim=_ceil_div(self.f32.d_model, _SUBS), block_dim=_TG,
                )
                issued += 6

            # ── final rmsnorm + packed3 lm_head + per-threadgroup argmax, then the reduce ──
            var n_iters = _ceil_div(self.f32.vocab, _LM_BLOCKS * _SUBS)
            self.f32.ctx.enqueue_function[_lmhead_argmax_kernel_p3](
                self.f32.blk_val.unsafe_ptr(), self.f32.blk_idx.unsafe_ptr(),
                self.f32.hidden.unsafe_ptr(), self.f32.final_norm.unsafe_ptr(),
                self.p3_lm.unsafe_ptr(), self.p3_lm_s.unsafe_ptr(), self.p3_lm_z.unsafe_ptr(),
                Int64(self.f32.d_model), Int64(self.f32.vocab), self.f32.eps, Int64(n_iters),
                grid_dim=_LM_BLOCKS, block_dim=_TG,
            )
            self.f32.ctx.enqueue_function[_argmax_reduce_kernel](
                self.f32.out_val.unsafe_ptr(), self.f32.out_idx.unsafe_ptr(),
                self.f32.blk_val.unsafe_ptr(), self.f32.blk_idx.unsafe_ptr(),
                Int64(_LM_BLOCKS),
                grid_dim=1, block_dim=_TG,
            )
            issued += 2

            # ── 8 bytes back, not 608 KB ──
            self.f32.ctx.enqueue_copy(self.f32.host_val, self.f32.out_val)
            self.f32.ctx.enqueue_copy(self.f32.host_idx, self.f32.out_idx)
            self.f32.ctx.synchronize()
            var tok = Int(self.f32.host_idx.unsafe_ptr()[0])
            var lg = Float64(self.f32.host_val.unsafe_ptr()[0])
            if tok < 0 or tok >= self.f32.vocab:
                return _StepOut(-1, 0.0, issued, RESIDENT_ERR_LAUNCH_FAILED)
            return _StepOut(tok, lg, issued, RESIDENT_OK)
