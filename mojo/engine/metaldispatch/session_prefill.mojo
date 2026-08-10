"""metaldispatch.session_prefill — batched prefill (prompt-processing) for the resident Qwen3
decode session. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: metal
surfaces: none
golden_vectors: mojo/tests/libs/test_metaldispatch_session_prefill.mojo
benchmark: benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch_i8_allsimd7_prefill.mojo
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Same discipline as `metaldispatch.session` -- see that file's own module
docstring for the full reasoning (leading underscores, `MB_GPU_BUILD` compile-time gate).

WHY THIS FILE EXISTS, in one number
------------------------------------
`metaldispatch.qwen3_decode`'s own prefill loop is `for t in range(n_prompt): s.step(prompt_ids[t],
t)` -- the single-token decode kernel, called once per PROMPT token, zero batching. Measured for
real (same Qwen3-0.6B-Base checkpoint, same M4 Max GPU, ~260-token prompt): Algenta 285.6 tok/s
against mlx-lm's 2,827.1 and llama.cpp's 7,117.6 -- not because Metal itself is slow (both real
opponents run on the identical GPU), but because Algenta had no batched, matmul-shaped prefill path
at all. This file is that path.

`_MBQwen3I8AllSimd7Prefill` duplicates `_MBQwen3I8AllSimd7`'s fields, `__init__`, descriptor-building
methods, `upload_globals`/`upload_layer`/`seal`, and `step()` BYTE-FOR-BYTE (the same `AllSimd[n] ->
[n+1]` copy-and-extend precedent every prior struct in `metaldispatch.session` already follows for
its own additions) and adds exactly one new capability: `prefill_batch(prompt_ids, pos_base)`, which
processes an entire prompt in `1 + n_layers * 6 + 2` dispatches total instead of `n_layers * 6 + 3`
dispatches PER PROMPT TOKEN. One struct instance owns the KV-cache buffers for its whole lifetime --
`prefill_batch` writes cache slots `[pos_base, pos_base + m_rows)`, and the byte-identical `step()`
then continues generation from `pos = pos_base + m_rows` on the SAME instance, no cross-struct
buffer hand-off.

Of the seven per-layer/once-per-token kernel roles a decode step dispatches, six get a genuinely new,
row-flattened batched kernel (`residentk.kernels`' `_pf_*` family, its own module docstring section
has the full account of why each is a mechanical row-flattening of an already-verified single-row
kernel) -- the SEVENTH, final-norm+lm_head+argmax, needs no new kernel at all: only the LAST prefill
row ever needs a next-token id, so the existing, byte-unmodified `_lmhead_argmax_kernel_simd_i8` /
`_argmax_reduce_kernel_simd` are dispatched once, with the `x` (hidden-state) pointer argument
patched to `self.hidden_addr`'s `gpuAddress` PLUS `(m_rows - 1) * d_model * 4` bytes -- `gpuAddress`
is a real, byte-offsettable 64-bit device virtual address (`metaldispatch.ffi`'s own module
docstring: "value holds the target buffer's gpuAddress ... bound via setBytes:length:atIndex:"), so
this is ordinary pointer arithmetic on a real address, not a new mechanism -- the kernel receives a
pointer that already starts at row `m_rows - 1`'s first element and has no way to tell it apart from
a genuine single-row buffer. `argmax_reduce` needs no per-call patching at all: it only ever reads
`blk_val`/`blk_idx`, which the lm_head dispatch immediately before it always writes at their usual,
un-batched size and address, regardless of `m_rows`.

BUFFER SIZING: `hidden`/`qkv`/`q_rot`/`attn_out`/`act` are allocated at `PREFILL_MAX_TILE` ROWS
instead of `_MBQwen3I8AllSimd7`'s one -- every OTHER buffer (per-layer weights, `ck`/`cv`, `embed`,
`cos`/`sin`, `blk_val`/`blk_idx`/`out_val`/`out_idx`) is UNCHANGED, byte-identical in size and
address role to `_MBQwen3I8AllSimd7`'s own. `step()`'s own descriptor plan (`self.descriptors`/
`self.descriptors_deep`) is completely unaware its activation buffers are now bigger than one row --
every kernel `step()` dispatches still receives `d_model`/`n_qkv`/etc. (never `PREFILL_MAX_TILE *
d_model`) as its own bound, so it only ever touches row 0 of each buffer, exactly as if the buffer
had never grown. One new buffer, `prompt_ids` (a resident Int32 array of up to `PREFILL_MAX_TILE`
prompt token ids), exists for `_pf_embed_rows_kernel_i8` alone: a decode step's single `token_id` was
always a plain scalar kernel argument, but a BATCH of them needs a buffer, since a Metal dispatch's
scalar arguments are fixed at descriptor-BUILD time, not re-suppliable per row within one dispatch.

DISPATCH PLAN: `self.descriptors_prefill` is built ONCE, in `__init__`, at a FIXED ceiling
(`PREFILL_MAX_TILE` rows per M-scaled dispatch's grid width) -- exactly the same "build wide, then
narrow before first use" sequencing `_build_descriptors_deep`'s own docstring establishes for
`n_splits_max`. `_apply_m_rows`, called at the START of every `prefill_batch()` call, re-patches
every M-scaled dispatch's `grid_x` (via `_mb_set_header`, which only ever touches a descriptor's
16-byte header, never its argument area -- `_apply_n_splits`'s own docstring has the full safety
argument, reused unchanged here) down to `m_rows`'s own real value, plus the `m_rows` and
`pos_base` scalar arguments every batched kernel actually reads. Always repatched unconditionally
(never a cached "skip if unchanged" the way `step()`'s own deep-branch `n_splits` is) -- unlike a
decode step, `prefill_batch()` is called at most once or twice per generation, so the "only patch on
change" optimization `step()`'s own docstring justifies for a called-every-token quantity buys
nothing here and would only add a second code path to keep correct.

PROJECT REDLINE REOPENING (2026-08-08), ROUND 5: `step()` IS NOW PLAN-AWARE
----------------------------------------------------------------------------
Round 4's own adversarial pass found that `PF_ATTN_GROUPED_FA_NO_MIRROR` prefill leaves the natural
F32 `ck`/`cv` cache genuinely unwritten, populating ONLY the packed F16 native buffers -- but this
struct's public decode entry point, `step()`, was BYTE-FOR-BYTE `_MBQwen3I8AllSimd7.step` (see this
docstring's own opening paragraphs above), which only ever knows how to read `ck`/`cv`. The ONE other
decode implementation that reads the native-packed buffers correctly, `step_native_kv`, was a
separate, never-production-wired public method -- nothing routed a real caller to it, so pairing
`PF_ATTN_GROUPED_FA_NO_MIRROR` prefill with an ordinary `step()`-based decode loop (the only kind any
real production entry point had) would silently corrupt every multi-token decode past the first
generated token. See `metaldispatch.session_prefill_policy`'s own module docstring addendum, round 5,
for the type-level half of this fix (`ResolvedSessionExecutionPlan.decode`, deterministically derived
from `.attention`, never independently settable).

THE FIX HERE: the two decode IMPLEMENTATIONS are unchanged, byte-for-byte, just renamed and made
private -- `_step_legacy_impl` (was the public `step()`'s own body) and `_step_native_kv_impl` (was
the public `step_native_kv()`'s own body). `step()` is now a THIN, PLAN-AWARE ROUTER: it reads
`self.plan.decode` (already resolved, by construction, to agree with whatever `self.plan.attention`
actually dispatched at the most recent `prefill_batch()` call on this instance) and calls whichever
implementation that value names -- `DECODE_PATH_NATIVE_PACKED_KV` -> `_step_native_kv_impl`,
`DECODE_PATH_LEGACY_NATURAL_KV` -> `_step_legacy_impl`. A caller that only ever used `PF_ATTN_OFF`/
`PF_ATTN_GROUPED_FA_WITH_MIRROR` sees ZERO behavior change: `self.plan.decode` always resolves to
`DECODE_PATH_LEGACY_NATURAL_KV` for either of those, so `step()` still dispatches `_step_legacy_impl`
-- the SAME table, SAME dispatches, SAME everything. The behavior change is exactly, and only, for a
caller that resolved `PF_ATTN_GROUPED_FA_NO_MIRROR`: `step()` now does the RIGHT thing automatically,
closing the round-4 landmine at its root instead of merely documenting the scope limit it used to
impose (`metaldispatch.qwen3_prefill_decode`'s own `_af_nomirror`/`_af_nomirror_vecload4` functions
no longer need to restrict themselves to `max_new_tokens=1` under that flag -- their decode loops
call plain `step()`, unchanged, and it now routes correctly for however many tokens are requested).

`step_native_kv()` REMAINS a public method -- a thin wrapper around `_step_native_kv_impl`, kept ONLY
as a test-only hook for existing test call sites that want to exercise that implementation directly,
bypassing plan-based routing (`test_metaldispatch_session_prefill_native_decode.mojo`'s own gates do
this deliberately, to test the native-KV implementation in isolation from the routing layer). NO
production entry point calls it directly anymore -- every real caller goes through `step()`.

DISPATCH-COUNT ACCOUNTING, GENERATED NOT DUPLICATED: round 4's own adversarial pass found a SECOND,
independent landmine alongside the routing one above -- `metaldispatch.qwen3_prefill_decode`'s own
per-wrapper dispatch-count sanity check computed its expected budget via a split-K-aware formula
(`metaldispatch_dispatch_budget`/`residentk_dispatch_budget_deep`, chosen by re-deriving `residentk_
splitk_should_split` itself) that has no equivalent for `step_native_kv`'s own table at all (it has
no split-K variant -- see `_build_descriptors_decode_native`'s own docstring). Applying that formula
to a real decode call through the native-KV path would raise a guaranteed FALSE-POSITIVE `MB_ERR_
DISPATCH_COUNT_MISMATCH` once `n_keys` crosses the split-K threshold, even though the actual dispatch
count never changes for that path. `expected_decode_dispatch_count(n_keys)` below is the fix: it
reads straight off THIS struct's own `self.n_descriptors`/`self.n_descriptors_deep`/`self.
n_descriptors_decode_native` fields -- each one already set, once, at the exact value its own
descriptor-BUILDER (`_build_descriptors`/`_build_descriptors_deep`/`_build_descriptors_decode_
native`) self-checks the actual encoded dispatch count against at build time (every one of those
three methods already `raise`s if what it built does not match the field this method reads -- see
each one's own tail). There is no second, independently-typed formula left anywhere for either decode
path to drift away from what its own descriptor builder actually does -- and a future third decode
path only ever needs one more branch here, reading THAT path's own already-self-checked field, never
a new formula.
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import WARP_SIZE
from residentk.contract import (
    RESIDENT_DEFAULT_CONTEXT,
    residentk_dispatch_budget_deep,
    residentk_prefill_gemm_use_narrow_tile,
    residentk_splitk_max_n_splits,
    residentk_splitk_policy,
    residentk_splitk_should_split,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _GEMM_BM,
    _GEMM_BN,
    _GEMM_NTHREADS,
    _GEMM_BM_NARROW,
    _GEMM_NTHREADS_NARROW,
    _embed_row_kernel_i8,
    _gemv_accum_kernel_simd_i8,
    _norm_gemv2_swiglu_kernel_simd_i8,
    _norm_gemv_kernel_simd_i8,
    _qk_rope_write_kernel,
    _sdpa_kernel_simd,
    _lmhead_argmax_kernel_simd_i8,
    _lmhead_logits_kernel_simd_i8,
    _argmax_reduce_kernel_simd,
    _splitk_partial_kernel_simd_native,
    _splitk_merge_kernel_simd,
    _batched_splitk_merge_kernel_simd,
    _batched_lmhead_argmax_kernel_simd_i8,
    _batched_argmax_reduce_kernel_simd,
    _pf_embed_rows_kernel_i8,
    _pf_rmsnorm_rows_kernel,
    _pf_gemm_assign_kernel_i8,
    _pf_ropewrt_kernel,
    _pf_attn_tiled_kernel_simd,
    _pf_attn8_kernel_simd,
    _pf_gemm_accum_kernel_i8,
    _pf_gemm_swiglu_kernel_i8,
    _pf_gnrw_assign_kernel_i8,
    _pf_gnrw_accum_kernel_i8,
    _pf_gnrw_swiglu_kernel_i8,
)
from metaldispatch.contract import (
    MB_ERR_BUFFER_ALLOC_FAILED,
    MB_ERR_CONTEXT_FULL,
    MB_ERR_DISPATCH_COUNT_MISMATCH,
    MB_ERR_DISPATCH_FAILED,
    MB_ERR_PIPELINE_NOT_FOUND,
    MB_ERR_SESSION_OPEN_FAILED,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_ERR_UPLOAD_LENGTH,
    MB_OK,
    metaldispatch_dispatch_budget,
)
from metaldispatch.ffi import (
    _mb_alloc_buffer,
    _mb_alloc_descriptors,
    _mb_gpu_core_count,
    _mb_open_session,
    _mb_pipeline_count,
    _mb_pipeline_name,
    _mb_run_token,
    _mb_set_arg_f32,
    _mb_set_arg_int,
    _mb_set_arg_ptr,
    _mb_set_header,
)
from metaldispatch.session import (
    _MBLayerBufI8,
    _StepOut,
    _SampledOut,
    _classify_pipeline,
    _classify_splitk_pipeline,
    _classify_prefill_pipeline,
    _ceil_div,
    _narrow_into,
    _quantize_into_i8,
    _quantize_transposed_into_i8,
    _ROLE_EMBED,
    _ROLE_NORM_GEMV,
    _ROLE_GEMV_ACCUM,
    _ROLE_NORM_GEMV2_SWIGLU,
    _ROLE_QK_ROPE,
    _ROLE_SDPA,
    _ROLE_LMHEAD_ARGMAX,
    _ROLE_ARGMAX_REDUCE,
    _N_ROLES,
    _PFROLE_EMBED,
    _PFROLE_RMSNORM,
    _PFROLE_GEMM_ASSIGN,
    _PFROLE_ROPEWRT,
    _PFROLE_ATTN,
    _PFROLE_ATTN_BLOCK8,
    _PFROLE_GEMM_ACCUM,
    _PFROLE_GEMM_SWIGLU,
    _PFROLE_GEMM_ASSIGN_NARROW,
    _PFROLE_GEMM_ACCUM_NARROW,
    _PFROLE_GEMM_SWIGLU_NARROW,
    _PFROLE_GEMM_ASSIGN_MMA,
    _PFROLE_GEMM_ACCUM_MMA,
    _PFROLE_GEMM_SWIGLU_MMA,
    _PF_N_ROLES,
    _AFROLE_NATIVE_KV_PRODUCER,
    _AFROLE_GROUPED_FA_ATTN,
    _AF_N_ROLES,
    _classify_attention_forge_pipeline,
    _LM_BLOCKS,
    MB_GPU_BUILD,
)
from metaldispatch.session_prefill_policy import (
    DECODE_PATH_LEGACY_NATURAL_KV,
    DECODE_PATH_NATIVE_PACKED_KV,
    PF_ATTN_OFF,
    PF_ATTN_GROUPED_FA_WITH_MIRROR,
    PF_ATTN_GROUPED_FA_NO_MIRROR,
    PF_GEMM_ORIGINAL,
    PF_GEMM_BM64,
    PF_GEMM_VECLOAD4_ALL_ROLES,
    PF_GEMM_MSL_PARITY_ALL_ROLES,
    ResolvedSessionExecutionPlan,
    PrefillPipelineAvailability,
    UnresolvedPrefillConfig,
)

comptime PREFILL_MAX_TILE: Int = RESIDENT_DEFAULT_CONTEXT
"""Ceiling on `m_rows` for one `prefill_batch()` call -- `self.descriptors_prefill`'s grid widths
are built at this ceiling once, then narrowed per call (see module docstring). Set to
`RESIDENT_DEFAULT_CONTEXT` (512) rather than restated: a prompt longer than this needs more than one
`prefill_batch()` call (chunked by the caller, `metaldispatch.qwen3_prefill_decode`'s own job), the
same ceiling the KV cache itself already imposes by default."""

comptime _AF_KEY_BLOCK_SIZE: Int = 32
"""Attention Compiler Plan v1.0, Phase 2C wiring: the native-packed KV block size BOTH
`attention_forge/native_kv_producer.mojo`'s `_native_kv_producer_kernel` (its own `key_block_size`
argument) and `attention_forge/grouped_fa_q8_k32_h2_sg8.mojo`'s `_attn_grouped_fa_kernel` (its own
comptime `_KT`, not a runtime argument -- hardcoded 32 in that file) are built around. Declared once
here, at the ONE place both this struct's producer-dispatch args and its native-buffer sizing read
from, so the two kernels' own independently-hardcoded assumptions about this value can never drift
apart from what this struct actually allocates."""

comptime _NATIVE_DECODE_N_SPLITS: Int = 16
"""Beat-llama.cpp campaign (2026-08-08 night): the FIXED split count the native-KV decode split-K
table (`self.descriptors_decode_native_splitk`) is built with -- grid = `h_q * _NATIVE_DECODE_N_
SPLITS` for the partial dispatch, `h_q` for the merge. 16 is the campaign driver's measured sweet
spot at the race's own decode depths (`attention_forge/native_kv_decode_attn_splitk_driver.mojo`'s
bench: 8.1x at n_keys=456 vs the naive kernel, 6.5x at 256; 32 splits measurably WORSE than 16 at
both -- occupancy already saturated, the same finding the legacy path's own n_splits retune
recorded). The legacy deep path's DYNAMIC per-step n_splits policy (`residentk`'s own) is
deliberately NOT replicated here: this table is one fixed grid, built once, matching this struct's
own decode-native table discipline of never re-calling `_mb_set_header` after construction."""

comptime _BATCH_DECODE_MAX_SEQS: Int = 32
"""Project Slipstream Phase 3 (2026-08-09): the FIXED maximum number of sequences the batched /
continuous-batching decode path (`_step_batched`) provisions per-sequence native-packed KV caches
for. Each of the B (<= this) sequences gets its OWN `h_kv * af_n_blocks * d_head * _AF_KEY_BLOCK_SIZE`
-element K cache and V cache per layer, laid out contiguously in ONE oversized buffer per layer per
K/V so sequence `b`'s cache is selected by the flat element offset `b * batch_kv_stride_elems` -- the
exact uniform-stride indirection the batched attention partial blob and the batched kvprod blob were
built and verified around (their `kv_stride` argument). 16 is the prototype cap (tuning knob): the
batched KV buffers are allocated ONLY when `decode_batched_built` (both batched blobs + the engine-side
merge discovered), so a blobs-absent binary pays none of this memory. The actual in-flight batch may be
any B <= this; the weight-sweep win grows with B (REALRACE_RESULTS.md batched-decode GEMM M-sweep)."""

comptime _NATIVE_DECODE_SPLITK_THRESHOLD: Int = 128
"""Beat-llama.cpp campaign (2026-08-08 night): `n_keys` at and above which `_step_native_kv_impl`
dispatches the split-K table instead of the naive single-dispatch one. NOT the legacy path's 512:
the naive NATIVE kernel collapses ~2.87x below the legacy path even at 256-token depth (round 5,
measured twice), so its break-even against the two-dispatch split-K overhead sits far shallower
than the legacy kernel's does; 128 is the campaign's first-cut value (the race's own decode range
257-457 sits comfortably above it), flagged for tuning, not claimed optimal. Below threshold --
and on any binary that never linked the split-K blob -- the naive table stays the one dispatched,
byte-unmodified."""


def _dequant_i8_into_f16(
    dst_f16: UnsafePointer[UInt8, origin=MutAnyOrigin],
    src_w: UnsafePointer[UInt8, origin=MutAnyOrigin],
    src_scale: UnsafePointer[UInt8, origin=MutAnyOrigin],
    n_rows: Int,
    width: Int,
) raises:
    """Phase 3 (2026-08-08): materialize the ALREADY-DEQUANTIZED Float16 twin of one per-output-row
    symmetric-int8-quantized weight buffer -- `dst_f16[row][i] = Float16(Float32(src_w[row][i]) *
    src_scale[row])`, reading back the EXACT Int8 bytes + per-row Float32 scale the production GEMM
    kernels read (the buffers `_quantize_transposed_into_i8` just wrote at upload time), never the
    original Float64 checkpoint -- so the MSL-parity arm computes the SAME quantized math (F32
    accumulate) as every Int8/vecload4 arm and must emit the same greedy tokens. Row-major `[n_rows,
    width]` in == row-major `[n_rows, width]` out, the same row ownership the Int8 buffer already
    holds post-transpose-quantize (see `msl_parity_*_mul_mm.metal`'s own WEIGHT LAYOUT headers)."""
    var dw = src_w.bitcast[Int8]()
    var ds = src_scale.bitcast[Float32]()
    var dh = dst_f16.bitcast[Float16]()
    for r in range(n_rows):
        var scale = ds[r]
        var base = r * width
        for i in range(width):
            dh[base + i] = Float16(Float32(dw[base + i]) * scale)


struct _MBQwen3I8AllSimd7Prefill(Movable):
    """See this file's own module docstring for the full account. Duplicates `_MBQwen3I8AllSimd7`
    byte-for-byte except: (1) `hidden`/`qkv`/`q_rot`/`attn_out`/`act` are sized for
    `PREFILL_MAX_TILE` rows instead of one, (2) a new `prompt_ids` buffer, (3) a new
    `prefill_pipeline_idx` array resolved via `_classify_prefill_pipeline`, (4) a new
    `descriptors_prefill` table and `prefill_batch()` method. `_MBQwen3I8AllSimd7` and every kernel
    it dispatches remain completely untouched."""

    var d_model: Int
    var h_q: Int
    var h_kv: Int
    var d_head: Int
    var d_ff: Int
    var n_layers: Int
    var vocab: Int
    var max_ctx: Int
    var eps: Float32
    var scale: Float32
    var n_qkv: Int

    var pipeline_idx: List[Int]
    var prefill_pipeline_idx: List[Int]

    var layers: List[_MBLayerBufI8]
    var embed_addr: UInt64
    var embed_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var embed_scale_addr: UInt64
    var embed_scale_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var final_norm_addr: UInt64
    var final_norm_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var cos_addr: UInt64
    var cos_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var sin_addr: UInt64
    var sin_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]

    var hidden_addr: UInt64
    var hidden_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var xn_addr: UInt64
    var xn_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    """`[PREFILL_MAX_TILE, d_model]` -- `_pf_rmsnorm_rows_kernel`'s output, `_pf_gemm_assign_kernel_
    i8`'s input. Split out specifically because the qkv_proj role became a pure GEMM (no norm baked
    in) -- see `residentk.kernels`' own module comment for why."""
    var qkv_addr: UInt64
    var qkv_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var q_rot_addr: UInt64
    var q_rot_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var attn_out_addr: UInt64
    var attn_out_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var act_addr: UInt64
    var act_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var blk_val_addr: UInt64
    var blk_val_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var blk_idx_addr: UInt64
    var blk_idx_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var out_val_addr: UInt64
    var out_val_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var out_idx_addr: UInt64
    var out_idx_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]

    # ── Parity gap 3 (sampling, 2026-08-10): the vocabulary-wide Float32 logits row the logits-
    # emitting lm_head twin writes for the host-side sampler. Same lifetime as every other buffer
    # here; the greedy path simply never reads it.
    var logits_addr: UInt64
    var logits_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]

    var prompt_ids_addr: UInt64
    var prompt_ids_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]

    # ── Project Slipstream Phase 3 (2026-08-09): batched-decode tail + per-sequence state buffers.
    # B-sized argmax partial/output buffers (the single-row tail's `blk_val/blk_idx/out_val/out_idx`
    # are scalar/one-row), the per-sequence position / key-count device arrays the batched kvprod and
    # batched attention-partial blobs read, and the batched descriptor table + its bookkeeping. All
    # allocated/built ONLY when `decode_batched_built`.
    var batch_blk_val_addr: UInt64
    var batch_blk_val_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var batch_blk_idx_addr: UInt64
    var batch_blk_idx_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var batch_out_val_addr: UInt64
    var batch_out_val_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var batch_out_idx_addr: UInt64
    var batch_out_idx_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var batch_poss_addr: UInt64
    var batch_poss_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var batch_nkeys_addr: UInt64
    var batch_nkeys_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var descriptors_decode_batched: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_decode_batched: Int
    var decode_batched_B: Int

    var descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors: Int
    var token_id_offset: Int
    var pos_offsets: List[Int]
    var nkeys_offsets: List[Int]

    var pipeline_idx_split: Int
    var pipeline_idx_merge: Int
    var n_cores: Int
    var n_splits_max: Int
    var deep_last_n_splits: Int
    var m_partial_addr: UInt64
    var m_partial_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var l_partial_addr: UInt64
    var l_partial_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var o_partial_addr: UInt64
    var o_partial_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var descriptors_deep: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_deep: Int
    var token_id_offset_deep: Int
    var pos_offsets_deep: List[Int]
    var nkeys_offsets_deep: List[Int]
    var deep_ready: Bool

    var descriptors_prefill: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_prefill: Int
    var embed_d: Int
    var rmsnorm_d: List[Int]
    var gemm_assign_d: List[Int]
    var ropewrt_d: List[Int]
    var attn_d: List[Int]
    var gemv_o_d: List[Int]
    var rmsnorm2_d: List[Int]
    var swiglu_d: List[Int]
    var gemv_down_d: List[Int]
    var lmhead_d: Int

    # ── Attention Compiler Plan v1.0, Phase 2C production wiring (Candidate A + the native-KV-
    # producer), ADDITIVE ONLY -- every field below is new; nothing above this line changed shape or
    # meaning. See module docstring addendum near `prefill_batch` for the full account.
    #
    # ── Project Redline reopening (2026-08-08), resolved-execution-plan refactor: this struct used to
    # carry FOUR independent, overlapping `Bool` fields here (`use_native_grouped_fa_attn`, `use_
    # native_grouped_fa_attn_no_mirror`, `use_qkv_proj_bm64`, `use_vecload4_all_roles`) -- exactly two
    # real, independently-reproduced regressions came from that representation letting a
    # mutually-contradictory combination exist at all (see `metaldispatch.session_prefill_policy`'s own
    # module docstring for the full account of both). Replaced by ONE resolved field, `self.plan`, of
    # type `ResolvedSessionExecutionPlan` (that module's own struct -- an `Int`-backed closed set, this pinned
    # Mojo toolchain's own stand-in for `enum`, matching `_ROLE_*`/`_PFROLE_*`/`_AFROLE_*`'s established
    # convention). `self.plan` is resolved ONCE, at the end of `__init__` (from the constructor's own
    # `requested_plan` parameter, defaulting to `UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL)`
    # -- byte-for-byte the old all-`False` default), and may be RE-resolved any time afterward via the
    # public `resolve_plan` method below -- every dispatch decision in this file (`prefill_batch`,
    # `_apply_m_rows_af`, `_apply_m_rows_af_nomirror`) reads ONLY `self.plan`, never a raw boolean.
    #
    # ── Project Redline reopening (2026-08-08), "make unresolved plan state unrepresentable": the
    # constructor's own `requested_plan` parameter is now typed `UnresolvedPrefillConfig`, a DIFFERENT
    # Mojo type than `self.plan`'s own `ResolvedSessionExecutionPlan` -- see `metaldispatch.session_prefill_
    # policy`'s own module docstring addendum for the full two-layer account (compiler-enforced type
    # split, plus a defensive `is_resolved()` check `prefill_batch`/`_apply_m_rows_af_nomirror` both
    # run before ever reading `self.plan` for a real dispatch decision).
    var plan: ResolvedSessionExecutionPlan
    """The resolved (never merely requested) prefill execution plan -- see `metaldispatch.session_
    prefill_policy`'s own module docstring for the full "why a single resolved field, not several
    overlapping booleans" account, and `resolve_prefill_execution_plan`'s own docstring for exactly
    how a request degrades to the next available path without ever being outranked by a different
    path's own default. Set at the end of `__init__` and by `self.resolve_plan(...)` -- both go
    through `UnresolvedPrefillConfig.resolve`, so `self.plan.is_resolved()` is always `True` after
    either one returns; never written anywhere else, and never read as raw booleans by `prefill_
    batch`/`_apply_m_rows_af`/`_apply_m_rows_af_nomirror` -- those methods read `self.plan.attention`/
    `self.plan.gemm` exclusively. `prefill_batch`, `_apply_m_rows_af_nomirror`, and (round 5,
    2026-08-08) the public `step()` router all call `self._require_resolved_plan()` first,
    independently of each other (since a defense-in-depth check should not rely on being reached
    only through one particular caller) -- see that method's own docstring for why this is
    defense-in-depth, not the primary guarantee. `step()` additionally reads `self.plan.decode` (see
    that field's own docstring in `metaldispatch.session_prefill_policy`) to route between `_step_
    legacy_impl`/`_step_native_kv_impl`.

    DECODE-AFTER-AF-PREFILL GAP, CLOSED (history, restated from the old `use_native_grouped_fa_attn`
    field's own docstring): `PF_ATTN_GROUPED_FA_WITH_MIRROR` originally shipped (PR #599) with a
    documented, itemized gap -- resolving to it made `prefill_batch` populate ONLY the F16
    native-packed K/V buffers, never the natural F32 `ck`/`cv` cache `step()` (decode) reads, so a
    decode call after an AF-enabled prefill read stale/uninitialized cache and produced wrong tokens.
    `self.descriptors_prefill_af` now carries a THIRD per-layer dispatch (`self.kvprod_mirror_af_d`,
    see its own field docstring) that double-writes `ck`/`cv` via the byte-unmodified `_pf_ropewrt_
    kernel` every `prefill_batch()` call this plan's `attention` resolves to `PF_ATTN_GROUPED_FA_
    WITH_MIRROR` for -- `step()` itself is completely untouched, still always reading `self.
    layers[layer].ck_addr`/`cv_addr` exactly as it always has, and now finds them correctly
    populated. Proven by `test_metaldispatch_session_prefill_af.mojo`'s Gate C: a session resolved to
    this path BEFORE its first `prefill_batch()` call, followed by real `step()` decode calls,
    matches an independent CPU Float64 oracle computed over the full prompt + generated-token
    sequence. Scope of what is proven: single-chunk prefill (`pos_base=0`) followed by decode. NOT
    separately verified by that test: multi-chunk AF prefill (`prefill_batch` called more than once
    with increasing `pos_base` on one AF-enabled instance) followed by decode -- the underlying
    kernels' own multi-call continuation is verified (Phase 2B's `native_kv_producer_driver.mojo`,
    `_pf_ropewrt_kernel`'s own decode-cache precedent), but the full wired multi-chunk-then-decode
    sequence through THIS struct has not been exercised end-to-end."""
    var af_pipeline_idx: List[Int]
    """Sized `_AF_N_ROLES` (2), resolved via `_classify_attention_forge_pipeline` during pipeline
    discovery below -- UNLIKE `self.pipeline_idx`/`self.prefill_pipeline_idx`, a `-1` entry here is
    NOT fatal at construction time (see `_classify_attention_forge_pipeline`'s own docstring in
    `metaldispatch.session` for why): every EXISTING benchmark/production binary that instantiates
    this struct without linking the two `attention_forge/` blobs must keep constructing successfully,
    with both entries `-1` and `self.plan.attention` resolving to `PF_ATTN_OFF` regardless of what
    was requested (`resolve_prefill_execution_plan`'s own graceful degrade) -- this pair is optional,
    additive capability, never a new required dependency."""
    var af_n_blocks: Int
    """`ceil(max_ctx / _AF_KEY_BLOCK_SIZE)` -- the FIXED per-`kv_head` native-packed-block stride both
    the native-KV-producer's writes and Candidate A's attention reads use for every call on this
    session (never `ceil(n_tok_k / _AF_KEY_BLOCK_SIZE)` for the CURRENT call's own `n_tok_k` -- see
    `native_kv_producer.mojo`'s own docstring item 5 for why the stride must be a property of how the
    scratch buffer was ALLOCATED, not of any one dispatch)."""
    var q_native_addr: UInt64
    var q_native_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    """`[PREFILL_MAX_TILE, h_q * d_head]` row-major, Float16 -- the native-KV-producer's own `q_rot`
    output (F16-narrowed, layout UNCHANGED from `self.q_rot_addr`'s F32 shape) and Candidate A's own
    `q_ptr` input. A SEPARATE buffer from `self.q_rot_addr` (never repurposed: the OFF path's
    `_pf_ropewrt_kernel` still writes `self.q_rot_addr` at F32 every call, completely unaware this
    buffer exists), reused across layers exactly like `self.q_rot_addr` already is."""
    var lse_scratch_addr: UInt64
    var lse_scratch_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    """`[h_q, PREFILL_MAX_TILE]`, Float32 -- Candidate A's own `lse_ptr` output argument. Written by
    the kernel every dispatch (numerically-stable log-sum-exp per row, per this task's own
    architecture) but never READ by anything downstream in this struct's own production dispatch
    chain (the kernel already divides by `l` internally before writing `out_ptr`) -- allocated purely
    because the kernel's own signature requires a valid, correctly-sized destination to write into,
    not because any consumer needs its contents."""
    var af_ck_native_addr: List[UInt64]
    var af_ck_native_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    var af_cv_native_addr: List[UInt64]
    var af_cv_native_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    """Per-layer, parallel to `self.layers[layer].ck_addr`/`cv_addr` but NOT added as new fields on
    `_MBLayerBufI8` itself -- that struct is shared by EVERY session struct in `metaldispatch.session`
    (decode-only, non-prefill, every `_MBQwen3I8AllSimd*` arm), and adding fields there would force
    every one of those OTHER structs' own `_MBLayerBufI8(...)` positional-constructor call sites to
    supply two new arguments they have no use for -- exactly the blast-radius `_classify_splitk_
    pipeline`'s and `_classify_attention_forge_pipeline`'s own docstrings warn against for the
    classifier side of this same "don't force an unrelated struct to carry a new dependency" rule,
    applied here to the BUFFER side instead. `attention_forge.native_kv_producer`'s own K/V native-
    packed flat-index formulas (`[kv_head][key_block][d_chunk][key_in_block]` for K,
    `[kv_head][key_block][key_in_block][d_chunk]` for V) are the two layouts these buffers hold,
    Float16, sized `h_kv * self.af_n_blocks * d_head * _AF_KEY_BLOCK_SIZE` elements each (same total
    element count for both; only the byte ORDER differs, per the producer's own module docstring)."""

    var batch_kv_stride_elems: Int
    var batch_ck_native_addr: List[UInt64]
    var batch_ck_native_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    var batch_cv_native_addr: List[UInt64]
    var batch_cv_native_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    """Project Slipstream Phase 3 (2026-08-09): per-layer native-packed K/V caches for the BATCHED
    decode path -- `_BATCH_DECODE_MAX_SEQS` independent sequences' caches per layer, concatenated into
    ONE oversized K buffer and ONE oversized V buffer per layer (same native-packed layouts as
    `af_ck_native_addr`/`af_cv_native_addr`). `batch_kv_stride_elems` = one sequence's cache element
    count (`h_kv * af_n_blocks * d_head * _AF_KEY_BLOCK_SIZE`), so sequence `b`'s K/V cache starts at
    element offset `b * batch_kv_stride_elems` -- the flat-offset indirection the batched attention +
    batched kvprod blobs take as their `kv_stride` argument. Allocated ONLY when `decode_batched_built`
    (gated, like the MSL f16 twins on `msl_any_linked`), so a blobs-absent binary pays none of this
    memory. Kept as separate lists parallel to `self.layers` (NOT fields on the shared `_MBLayerBufI8`)
    for the same blast-radius reason as `af_ck_native_addr` above."""

    var descriptors_prefill_af: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_prefill_af: Int
    """A COMPLETE, SEPARATE descriptor table -- never a partial overlay onto `self.descriptors_
    prefill` -- built only if BOTH `self.af_pipeline_idx` entries were discovered (`> 0` here implies
    that; `0` means the two `attention_forge/` blobs were not linked into this binary, and
    `resolve_prefill_execution_plan` degrades a `PF_ATTN_GROUPED_FA_WITH_MIRROR` request down to
    `PF_ATTN_OFF` rather than ever letting `prefill_batch` dispatch a table that was never
    populated). `1 + n_layers*9 + 2` dispatches -- ONE MORE per layer
    than `self.n_descriptors_prefill`'s own `1 + n_layers*8 + 2` (the native-KV-producer replaces
    `ropewrt` as one dispatch, Candidate A's attention replaces `attn` as one dispatch, and a THIRD,
    genuinely EXTRA per-layer dispatch -- `self.kvprod_mirror_af_d`, see its own field docstring --
    re-dispatches the byte-unmodified, already-linked `_pf_ropewrt_kernel` a SECOND time to also
    populate `self.layers[layer].ck_addr`/`cv_addr` (the natural F32 cache `step()` reads), closing
    the decode-after-AF-prefill gap this phase originally shipped with (see that field's own
    docstring, and `prefill_batch`'s, for the full account). Every OTHER dispatch in this table
    (embed, both GEMM-assign/accum/swiglu roles, both rmsnorm roles, lm_head+argmax) is a full,
    independent descriptor pointing at the exact SAME underlying buffers `self.descriptors_prefill`'s
    own equivalent slot uses -- safe because the two tables are mutually exclusive per call
    (`prefill_batch` submits exactly one), never concurrently dispatched."""
    var embed_af_d: Int
    var rmsnorm_af_d: List[Int]
    var gemm_assign_af_d: List[Int]
    var kvprod_af_d: List[Int]
    var kvprod_q_af_d: List[Int]
    """Beat-llama.cpp campaign Phase C: per-layer descriptor index of the V2 Q-pass dispatch
    (`_kvprod_qvec_kernel`) that FOLLOWS the V2 KV-pass dispatch in the with-mirror AF table --
    populated only when `kvprod_v2_built` (empty otherwise); patched per call alongside
    `kvprod_af_d` by `_apply_m_rows_af`."""

    var kvprod_mirror_af_d: List[Int]
    """Per-layer descriptor index of the natural-cache DOUBLE-WRITE dispatch -- see `self.
    descriptors_prefill_af`'s own field docstring for the full rationale and `_build_descriptors_
    prefill_af`'s own comment at this dispatch's build site for why it re-dispatches the EXISTING
    `_pf_ropewrt_kernel` (pipeline `self.prefill_pipeline_idx[_PFROLE_ROPEWRT]`, already compiled and
    discovered unconditionally, AF blobs or not) rather than extending `_native_kv_producer_kernel`'s
    own signature: that kernel's dispatch is ALREADY at `_mb_set_header`'s `num_args=16`, exactly
    `metaldispatch.ffi.MB_MAX_ARGS`'s hard ceiling (the fixed byte-stride shared with `batch_shim.m`'s
    own `ALGENTA_MAX_ARGS`) -- there is no room to add the two more pointer arguments (`ck_addr`/
    `cv_addr`) a same-kernel double-write would need without growing that ceiling for every OTHER
    dispatch table in this file too, a far larger blast radius than this gap-closing fix warrants."""
    var attn_af_d: List[Int]
    var gemv_o_af_d: List[Int]
    var rmsnorm2_af_d: List[Int]
    var swiglu_af_d: List[Int]
    var gemv_down_af_d: List[Int]
    var lmhead_af_d: Int
    """Same per-role descriptor-index bookkeeping convention as `self.rmsnorm_d`/`self.attn_d`/etc.,
    restated for the AF table -- `_apply_m_rows_af` narrows each of these exactly the way `_apply_m_
    rows` narrows its own OFF-path counterparts."""

    # ── Project Redline reopening (2026-08-08), ADDITIVE ONLY -- everything below is new; nothing
    # above this line changed shape or meaning. Removes the NEED for `self.kvprod_mirror_af_d`'s
    # double-write on a new, parallel path: a prefill table that skips the mirror
    # (`self.descriptors_prefill_af_nomirror`) plus a decode-side kernel/table that reads the
    # native-packed F16 buffers directly instead of `ck`/`cv` (`step_native_kv`, dispatching
    # `attention_forge.native_kv_decode_attn._native_kv_decode_attn_kernel`). `self.descriptors_
    # prefill_af`/`PF_ATTN_GROUPED_FA_WITH_MIRROR`/`step()` are all completely untouched -- see
    # `step_native_kv`'s own docstring, near the bottom of this file, for the full account.
    var native_decode_attn_pipeline_idx: Int
    """Discovered via a LOCAL, file-private substring match (`"native_kv_decode_attn"`, this new
    kernel's own full, never-truncated module name) inside `__init__`'s existing pipeline-discovery
    loop below -- verified empirically, not guessed, by `attention_forge/native_kv_decode_attn_
    discovery_check.mojo`'s own 4-blob coexistence run: real discovered name `native_kv_decode_
    attn__native_k6A6A_<hash>`, colliding with none of `_classify_pipeline`'s eight patterns,
    `_classify_splitk_pipeline`'s two, `_classify_prefill_pipeline`'s ten, `_classify_attention_
    forge_pipeline`'s two (`native_kv_producer`/`grouped_fa_q8_k32_h2_sg8` are each NOT a substring
    of `native_kv_decode_attn` and vice versa), or `mm8`'s own three. Kept as a file-private check
    here, never folded into `metaldispatch.session`'s own `_classify_attention_forge_pipeline`/
    `_AFROLE_*`/`_AF_N_ROLES`, so that shared file needs zero edits for this addition -- this struct
    is, once again, the ONLY consumer, the same reasoning `_AF_N_ROLES`'s own docstring already gives
    for staying separate from every OTHER shared classifier in that file. `-1` (not found) is NOT
    fatal at construction time, matching `self.af_pipeline_idx`'s own established non-fatal-miss
    precedent -- a binary that never links this new blob must keep constructing successfully;
    `step_native_kv` itself refuses with `MB_ERR_PIPELINE_NOT_FOUND` if this is `< 0`."""

    var native_decode_splitk_partial_pipeline_idx: Int
    """Beat-llama.cpp campaign (2026-08-08 night): the split-K/flash-decoding PARTIAL twin of the
    naive kernel above (`attention_forge/native_kv_decode_attn_splitk._native_kv_decode_splitk_
    partial_kernel`), the occupancy fix for this path's ~2.87x decode collapse (round 5). Discovered
    via the SAME file-private substring mechanism, with ONE ordering subtlety, stated precisely:
    this kernel's own discovered name CONTAINS the naive kernel's discovery substring
    (`native_kv_decode_attn` is a prefix of `native_kv_decode_attn_splitk...`), so the discovery
    loop below checks the LONGER substring (`"native_kv_decode_attn_splitk"`) FIRST and the naive
    one in an `elif` -- scan order inside `__TEXT,__const` can never cross-wire the two pipelines,
    whichever blob lands first. Non-fatal-miss (`-1`) exactly like the naive field above: a binary
    that never links `attention_forge/generated/native_kv_decode_attn_splitk_blob.c` keeps
    constructing successfully and simply never gets the split-K decode table -- `_step_native_kv_
    impl` falls back to the naive table unconditionally, byte-unmodified, and `expected_decode_
    dispatch_count` reports the naive count at every depth."""

    var kvprod_blk_pipeline_idx: Int
    var kvprod_qvec_pipeline_idx: Int
    """Beat-llama.cpp campaign Phase C (2026-08-08 night): the two kernels of the block-cooperative
    native-KV-producer V2 (`attention_forge/kvprod_v2.mojo`): `_kvprod_blk_kernel` (KV pass: one
    threadgroup per (kv_head, key_block), shared-tile assembly, coalesced writes, warp-sum norms,
    shuffle-based RoPE partner exchange) + `_kvprod_qvec_kernel` (Q pass: one warp per (q_head,
    row), vectorized contiguous stores). Together they replace the single naive `_native_kv_
    producer_kernel` dispatch inside the AF prefill tables when their blob
    (`attention_forge/generated/kvprod_v2_blob.c`) is linked -- 3.45x cheaper per dispatch at
    m_rows=256 in the campaign's isolated bench (0.2022 -> 0.0587 ms), correctness-gated against
    the naive kernel's own output there. Discovered via UNIQUE file-private substrings
    ("kvprod_blk"/"kvprod_qvec") -- the module is deliberately NOT named `native_kv_producer_*` so
    the shared `_classify_attention_forge_pipeline`'s "native_kv_producer" pattern can never match
    these pipelines (that classifier keeps owning the NAIVE producer's `af_pipeline_idx` slot,
    which the decode tables and the blobs-absent fallback still need). Non-fatal-miss (`-1`)
    exactly like every other optional pipeline field in this struct."""
    var kvprod_v2_built: Bool
    """True iff BOTH `kvprod_blk_pipeline_idx` and `kvprod_qvec_pipeline_idx` were discovered --
    the ONE flag the AF table builders and `_apply_m_rows_af`/`_apply_m_rows_af_nomirror` read to
    choose the V2 pair over the naive producer dispatch. Set once, in `__init__`, right after
    pipeline discovery."""

    # ── Project Slipstream Phase 3 (2026-08-09): the two BLOBS the continuous-batching / batched
    # decode path needs, plus the engine-side merge flag. All three verified collision-free by
    # `attention_forge/batched_kernels_discovery_check.mojo` (see REALRACE_RESULTS.md "batched-kernel
    # DISCOVERY NAMES" + "batched-kvprod module RENAMED" addenda for the truncation rule and the two
    # collisions these names were chosen to avoid).
    var native_decode_splitk_partial_batched_pipeline_idx: Int
    """The batched flash-decoding PARTIAL blob (`attention_forge/generated/
    native_kv_decode_attn_splitk_batched_blob.c`, module `native_kv_decode_attn_splitk_batched`,
    partial-only -- the merge is engine-side). Its AIR name truncates to
    `native_kv_decode_attn_splitk_bat_<hex>`; discovered via the file-private substring
    `"native_kv_decode_attn_splitk_bat"`, checked LONGEST-FIRST below (BEFORE the single-stream
    `"native_kv_decode_attn_splitk"` check) because the batched name contains the single-stream
    substring. A hex hash can never spell `_bat`, so this substring cannot false-match the
    single-stream split-K pipeline. Non-fatal-miss (`-1`) like every optional pipeline field."""
    var kvprod_batched_pipeline_idx: Int
    """The batched KV-producer blob (`attention_forge/generated/native_kv_producer_batched_blob.c`,
    module `kvprod_batched`). Deliberately NOT named `native_kv_producer_*` so the shared
    `_classify_attention_forge_pipeline`'s `"native_kv_producer"` pattern can never match it (that
    slot stays the NAIVE producer's). Discovered via the unique file-private substring
    `"kvprod_batched"`. Non-fatal-miss (`-1`)."""
    var batched_splitk_merge_pipeline_idx: Int
    """The engine-side B-aware merge `_batched_splitk_merge_kernel_simd` (residentk/kernels.mojo),
    compiled in this struct's early `__init__` block (before discovery). Discovered via the file-
    private substring `"batched_spl"` -- the engine-compiled-kernel 11-char truncation of
    `_batched_splitk_merge_kernel_simd` (see REALRACE_RESULTS.md "THIRD discovery collision"): this
    diverges from the single-stream merge's `splitk_merg` within the 11-char window, and `_classify_
    splitk_pipeline` (which owns `pipeline_idx_merge`) never matches it. Non-fatal-miss (`-1`)."""
    var batched_lmhead_pipeline_idx: Int
    """The fused B-row lm_head `_batched_lmhead_argmax_kernel_simd_i8` (residentk/kernels.mojo,
    Slipstream Phase 3 Option B), compiled in the early `__init__` block. Discovered via `"batched_
    lmh"` -- its own 11-char engine-kernel truncation, distinct from the single-row lm_head's
    `lmhead_argm`, the merge's `batched_spl`, and the reduce's `batched_arg`. Non-fatal-miss (`-1`)."""
    var batched_argmax_reduce_pipeline_idx: Int
    """The B-row argmax reduce `_batched_argmax_reduce_kernel_simd` (residentk/kernels.mojo), compiled
    in the early `__init__` block. Discovered via `"batched_arg"`, its own 11-char truncation.
    Non-fatal-miss (`-1`)."""
    var lmhead_logits_pipeline_idx: Int
    """Parity gap 3 (sampling, 2026-08-10): the logits-emitting twin `_lmhead_logits_kernel_simd_i8`
    (residentk/kernels.mojo), compiled in the early `__init__` block. Discovered via `"lmhead_logi"`
    -- its own 11-char engine-kernel truncation, which `_classify_pipeline` explicitly refuses
    (returns -1) so it can never land in `_ROLE_LMHEAD_ARGMAX`'s slot. Non-fatal-miss (`-1`): a
    session that never samples simply never dispatches it."""
    var decode_batched_built: Bool
    """True iff ALL FIVE batched-decode pipelines were discovered (`native_decode_splitk_partial_
    batched_pipeline_idx >= 0` AND `kvprod_batched_pipeline_idx >= 0` AND `batched_splitk_merge_
    pipeline_idx >= 0` AND `batched_lmhead_pipeline_idx >= 0` AND `batched_argmax_reduce_pipeline_idx
    >= 0`) -- the gate `_step_batched` reads before running the batched decode table (and refuses with
    `MB_ERR_PIPELINE_NOT_FOUND` otherwise). Set once, in `__init__`, right after pipeline discovery."""


    # ── Project Redline reopening (2026-08-08), resolved-execution-plan refactor: the old `use_
    # native_grouped_fa_attn_no_mirror: Bool` field that used to live here is gone -- folded into
    # `self.plan.attention == PF_ATTN_GROUPED_FA_NO_MIRROR`, see that field's own docstring above and
    # `metaldispatch.session_prefill_policy`'s own module docstring for the full account of why a
    # second, independent `Bool` here was exactly the defect that let an explicit `PF_ATTN_GROUPED_
    # FA_WITH_MIRROR` request be silently outranked (regression #2, closed by construction, not by
    # reordering the two branches that used to check these fields in `prefill_batch`).

    # ── Project Redline reopening (2026-08-08), step 4: combined no-mirror + BM64 GEMM build.
    # ADDITIVE ONLY -- composes with `PF_ATTN_GROUPED_FA_NO_MIRROR` above via `self.plan.gemm ==
    # PF_GEMM_BM64`, never replaces the attention choice; `self.plan.gemm` has zero effect unless
    # `self.plan.attention == PF_ATTN_GROUPED_FA_NO_MIRROR` -- `_apply_m_rows_af`/`_apply_m_rows` are
    # never touched by this addition, see below.
    var qkv_proj_bm64_pipeline_idx: Int
    """Discovered via a LOCAL, file-private substring match (`"mma8x8_bm64"`) inside `__init__`'s
    existing pipeline-discovery loop, mirroring `self.native_decode_attn_pipeline_idx`'s own
    established non-fatal-miss pattern exactly -- NOT folded into `metaldispatch.session`'s own
    `_PFROLE_*`/`_PF_N_ROLES` (which IS fatal-checked at construction time for every OTHER role):
    doing so would force every OTHER binary/test that constructs `_MBQwen3I8AllSimd7Prefill` without
    linking the new `mma_forge/generated/mm8_bm64_blob.c` to fail construction outright, breaking
    "coexists with every existing path." `-1` (not found) is never fatal here, and -- per the
    Sector-1 promotion-decision graceful-fallback fix (2026-08-08) -- never fatal at `prefill_batch`
    call time either: `_apply_m_rows_af_nomirror` only actually SELECTS `self.qkv_proj_bm64_pipeline_
    idx` when it is `>= 0` (see that method's own `use_bm64` local, which ANDs `self.plan.gemm ==
    PF_GEMM_BM64` with this field's own availability), silently keeping the original `_PFROLE_GEMM_
    ASSIGN_MMA` kernel/grid for the qkv_proj role otherwise -- a plan resolved to `PF_GEMM_BM64` on a
    binary that never linked `mm8_bm64_blob.c` would already have been degraded to `PF_GEMM_ORIGINAL`
    by `resolve_prefill_execution_plan` itself, so this is a correct, if unaccelerated, no-mirror
    prefill, never an error. `metaldispatch.session._classify_prefill_pipeline` was given one small, additive guard (checked
    BEFORE its existing `"proj_gemm_mma8x8"` pattern) so a binary linking BOTH `mm8_blob.c` and
    `mm8_bm64_blob.c` never has this kernel's own discovered pipeline corrupt `self.prefill_pipeline_
    idx[_PFROLE_GEMM_ASSIGN_MMA]`'s real mapping to the ORIGINAL `_qkv_proj_gemm_mma8x8` -- a real,
    empirically-confirmed name collision (`mm8__qkv_proj_gemm_mma8x8_bm646A6AoA_<hash>` DOES contain
    `"proj_gemm_mma8x8"`), verified directly via `attention_forge/mm8_bm64_discovery_check.mojo`
    before this field was added, not assumed."""

    # ── Project Redline reopening (2026-08-08), resolved-execution-plan refactor: the old `use_qkv_
    # proj_bm64: Bool` field that used to live here is gone -- folded into `self.plan.gemm ==
    # PF_GEMM_BM64`, consulted ONLY when `self.plan.attention == PF_ATTN_GROUPED_FA_NO_MIRROR` (see
    # `PF_GEMM_BM64`'s own docstring in `metaldispatch.session_prefill_policy` for the exact
    # substitution: qkv_proj role ONLY, `BM=64`, o_proj/down_proj/swiglu stay `BM=32` either way).
    # BM64 has no wiring into `self.descriptors_prefill_af`/`self.descriptors_prefill` at all, and
    # (unlike vecload4 immediately below, round 7) that remains unchanged.

    # ── Project Redline reopening (2026-08-08), step 2: combined no-mirror + ALL-4-ROLES vecload4
    # GEMM build. ADDITIVE ONLY, exactly the same discipline `PF_GEMM_BM64` above already established
    # -- composes with `PF_ATTN_GROUPED_FA_NO_MIRROR`, never replaces it; has zero effect on `self.
    # descriptors_prefill` (OFF), which remains byte-for-byte unchanged. Round 7 (2026-08-08):
    # ALSO now wired into `self.descriptors_prefill_af` (with-mirror) via `_apply_m_rows_af` -- see
    # that method's own docstring for the wiring-gap account this closes (the combination `attention=
    # PF_ATTN_GROUPED_FA_WITH_MIRROR` + `gemm=PF_GEMM_VECLOAD4_ALL_ROLES` used to resolve to a valid
    # plan that silently had no GEMM effect; it now does).
    var qkv_proj_vecload4_pipeline_idx: Int
    """Discovered via a LOCAL, file-private substring match (`"proj_gemm_mma8x8_veclo"`) inside
    `__init__`'s existing pipeline-discovery loop, mirroring `self.qkv_proj_bm64_pipeline_idx`'s own
    established non-fatal-miss pattern exactly. `-1` (not found) is never fatal, at construction OR at
    `prefill_batch` call time -- see `_apply_m_rows_af_nomirror`'s own `use_vecload4`-gated ternaries
    (and, round 7 (2026-08-08), `_apply_m_rows_af`'s own identical ternaries -- see that method's own
    docstring for the wiring-gap account of why they were added there too),
    each independently falling back to the ORIGINAL `_PFROLE_GEMM_ASSIGN_MMA` kernel/grid for this one
    role if this is `< 0`, the graceful-fallback discipline the Sector-1 promotion-decision fix
    (2026-08-08) established. `metaldispatch.session._classify_prefill_pipeline` was given an
    additive exclusion guard (checked before its existing `"proj_gemm_mma8x8"` pattern, same
    placement as the `"mma8x8_bm64"` guard) so a binary linking both `mm8_blob.c` and the new
    `mm8_vecload4_blob.c` never has this kernel's own discovered pipeline corrupt `self.prefill_
    pipeline_idx[_PFROLE_GEMM_ASSIGN_MMA]`'s real mapping to the ORIGINAL `_qkv_proj_gemm_mma8x8` --
    a real, empirically-confirmed collision (this binary's own truncated Metal AIR name is `mm8__qkv_
    proj_gemm_mma8x8_veclo6A6A_<hash>`, which DOES contain `"proj_gemm_mma8x8"`), verified directly
    via `attention_forge/vecload4_all_roles_discovery_check.mojo` before this field was added, not
    assumed. `ResolvedSessionExecutionPlan.gemm` is a SINGLE resolved value (`PF_GEMM_BM64` XOR `PF_GEMM_
    VECLOAD4_ALL_ROLES`, never both at once -- see `metaldispatch.session_prefill_policy`'s own
    module docstring for why that single-value design is exactly what makes a "which one wins"
    question unrepresentable, not merely resolved by a rule): a caller who wants vecload4 for the
    qkv_proj role specifically requests `PF_GEMM_VECLOAD4_ALL_ROLES`, which `resolve_prefill_
    execution_plan` honors whenever ANY of the three vecload4 blobs are linked -- REALRACE_RESULTS.
    md's own "BM64 + vecload4 stacked" entry found stacking the two kernels is cannibalization
    (statistically zero additional benefit over vecload4 alone), and the stacked kernel that WOULD
    combine them (`_qkv_proj_gemm_mma8x8_bm64_vecload4`) is never wired into this table at all -- so
    a caller wanting the larger, better-evidenced win simply requests `PF_GEMM_VECLOAD4_ALL_ROLES`
    directly, rather than this struct needing to arbitrate between two simultaneously-set flags."""

    var gemm_accum_vecload4_pipeline_idx: Int
    """Same non-fatal, file-private discovery pattern as `self.qkv_proj_vecload4_pipeline_idx` above,
    for the o_proj/down_proj role (`_gemm_accum_mma8x8_vecload4`, reused for BOTH roles exactly as the
    original `_gemm_accum_mma8x8` already is). Substring `"accum_mma8x8_vecload"` -- this kernel's own
    truncated name (`mm8__gemm_accum_mma8x8_vecload46A6A_<hash>`) happens to survive FULLY intact
    (unlike the qkv_proj kernel's own name, truncated mid-word), confirmed by the same discovery-check
    probe. `metaldispatch.session._classify_prefill_pipeline` was given the matching additive
    exclusion guard (checked before its existing `"gemm_accum_mma8x8"` pattern) for the identical
    collision reason."""

    var swiglu_vecload4_pipeline_idx: Int
    """Same non-fatal, file-private discovery pattern as `self.qkv_proj_vecload4_pipeline_idx` above,
    for the swiglu role (`_swiglu_gemm_mma8x8_vecload4`). Substring `"swiglu_gemm_mma8x8_vecload"` --
    this kernel's own truncated name (`mm8__swiglu_gemm_mma8x8_vecload6A6A_<hash>`) survives to one
    character short of the full literal `"vecload4"` (the trailing `"4"` is lost), confirmed by the
    same discovery-check probe. `metaldispatch.session._classify_prefill_pipeline` was given the
    matching additive exclusion guard (checked before its existing `"swiglu_gemm_mma8x8"` pattern) for
    the identical collision reason."""

    # ── Project Redline reopening (2026-08-08), resolved-execution-plan refactor: the old `use_
    # vecload4_all_roles: Bool` field that used to live here is gone -- folded into `self.plan.gemm ==
    # PF_GEMM_VECLOAD4_ALL_ROLES` (see that comptime's own docstring in `metaldispatch.session_
    # prefill_policy` for the full account: all four GEMM-shaped roles independently substitute their
    # own vecload4 twin, each still gated on its OWN kernel's own pipeline-discovery field, exactly the
    # same per-role graceful-degrade `_apply_m_rows_af_nomirror` already had -- only the TOP-LEVEL
    # selector moved from two overlapping booleans into one resolved plan field).

    # ── Phase 3 (2026-08-08), hybrid per-role Metal GEMM backend, OPT-IN. ADDITIVE ONLY -- the
    # three MSL parity replicas of llama.cpp's `kernel_mul_mm_f16_f32` (hand-written metallibs,
    # shipped through the EXISTING blob mechanism as `mma_forge/generated/msl_parity_blob.c`,
    # dispatched through the SAME `descriptors_prefill_af`/`descriptors_prefill_af_nomirror` tables
    # with a pipeline-index + arg-2-pointer + grid/threads patch only -- see each `_apply_m_rows_af*`
    # method's own Phase 3 note). The three kernels read ALREADY-DEQUANTIZED Float16 weights -- the
    # `msl_w_*_f16_*` buffers below, materialized at upload time from the EXACT SAME Int8 bytes +
    # per-row Float32 scale the Int8 twins read (same quantized weights -> same math -> same greedy
    # tokens as the vecload4 default arm).
    var msl_parity_qkv_proj_pipeline_idx: Int
    """Discovered via a LOCAL, file-private substring match (`"msl_parity__qkv_proj_mul_mm"`, the
    hand-written metallib's own UNMANGLED kernel name -- raw xcrun-compiled metallibs carry the name
    verbatim, no Mojo mangler truncation to budget for, unlike every Mojo-embedded kernel above)
    inside `__init__`'s existing pipeline-discovery loop, mirroring `self.qkv_proj_vecload4_
    pipeline_idx`'s own established non-fatal-miss pattern exactly. Checked against every existing
    classifier before being added: the three MSL names contain NONE of `_classify_pipeline`'s eight
    patterns, `_classify_splitk_pipeline`'s two, `_classify_prefill_pipeline`'s sixteen (including
    its bm64/vecload4 exclusion guards -- `"gemm_accum"` != `"gemv_accum"`, and nothing contains
    `"mma8x8"`), or `_classify_attention_forge_pipeline`'s two, so they need no exclusion guard of
    their own and corrupt no existing role's mapping. `-1` (not found) is never fatal, at
    construction OR at `prefill_batch` call time -- the tier's own graceful degrade (see
    `PF_GEMM_MSL_PARITY_ALL_ROLES`'s docstring in `metaldispatch.session_prefill_policy`) plus the
    per-role ternaries in `_apply_m_rows_af`/`_apply_m_rows_af_nomirror` handle every miss."""
    var msl_parity_gemm_accum_pipeline_idx: Int
    """Same non-fatal, file-private discovery pattern as `self.msl_parity_qkv_proj_pipeline_idx`
    above (substring `"msl_parity__gemm_accum_mul_mm"`), for the o_proj AND down_proj roles (one
    "+=" ACCUMULATE kernel, reused for both exactly as `_gemm_accum_mma8x8`/its vecload4 twin
    already are -- the descriptor table binds different buffers/k/n per role)."""
    var msl_parity_swiglu_pipeline_idx: Int
    """Same non-fatal, file-private discovery pattern as `self.msl_parity_qkv_proj_pipeline_idx`
    above (substring `"msl_parity__swiglu_mul_mm"`), for the fused gate+up swiglu role."""
    var msl_splitk8_pipeline_idx: Int
    """Beat-llama.cpp campaign front 2, fourth strike (2026-08-09): same non-fatal, file-private
    discovery pattern (substring `"msl_splitk8__gemm_accum"`, the raw xcrun-compiled name carried
    verbatim by `msl_splitk_blob.c`), for the OPTIONAL split-K replacement of the o_proj role's
    MSL-parity accum kernel. The grid-fill bench (`msl_gridfill_bench.m`) measured the two
    narrow-N accum roles (128 threadgroups at M=256) at only 67-68% of the 13.3 TFLOP/s MMA wall
    while the wide-N roles (512-768 tg) run at 90-97% -- the 40-core GPU is underfilled; split-K
    (S=8 for o_proj's K=2048 -> partial depth 256, grid x8) restores fill at constant tile shape
    and atomic-float-adds each partial into dst (no second kernel, "+=" semantics for free).
    Standalone: 1.30x over the parity accum kernel at the raced shape, correctness-gated at every
    M in {1,17,127,256,257,512}. `-1` (blob never linked) degrades to the parity accum kernel --
    never fatal, same discipline as every optional pipeline above. ONLY consulted when the
    MSL-parity accum tier is itself active (`use_msl_accum`) AND `n_q % 256 == 0` (the S=8 split
    requires K divisible by 256: split depth K/8 must be a multiple of the 32 K-step)."""
    var msl_splitk12_pipeline_idx: Int
    """Same pattern for the down_proj role's split-K replacement (substring
    `"msl_splitk12__gemm_accum"`, S=12 for K=3072 -> partial depth 256, grid x12; 1.33x
    standalone). Gated on `use_msl_accum` AND `d_ff % 384 == 0` (K/12 a multiple of 32)."""
    var msl_any_linked: Bool
    """`True` iff at least ONE of the three MSL pipelines above was discovered -- the ONE gate for
    the Float16-weight materialization below: a binary that never links `msl_parity_blob.c`
    allocates NONE of the `msl_w_*_f16_*` buffers and dequantizes nothing at upload time, staying
    byte-for-byte identical in memory layout and upload behavior to its pre-Phase-3 self (every
    existing suite/OFF-path binary is exactly such a binary)."""
    var msl_w_qkv_f16_addr: List[UInt64]
    var msl_w_qkv_f16_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    var msl_w_o_f16_addr: List[UInt64]
    var msl_w_o_f16_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    var msl_w_gu_f16_addr: List[UInt64]
    var msl_w_gu_f16_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    var msl_w_down_f16_addr: List[UInt64]
    var msl_w_down_f16_ptr: List[UnsafePointer[UInt8, origin=MutAnyOrigin]]
    """Per-layer, parallel to `self.layers[layer].w_qkv_addr`/`w_o_addr`/`w_gu_addr`/`w_down_addr`
    but Float16 and ALREADY DEQUANTIZED (`w_f16[row][i] = Float16(Float32(i8[row][i]) * scale[row])`,
    read back from the very Int8+scale buffers the production GEMM kernels read -- never from the
    original Float64 checkpoint, so this arm computes the SAME quantized math as every other arm).
    Layouts are the SAME row ownership the Int8 twins already hold post-`_quantize_transposed_
    into_i8` (qkv `[n_qkv, d_model]`, o `[d_model, n_q]`, gu `[2*d_ff, d_model]` gate rows first,
    down `[d_model, d_ff]`) -- the three MSL kernels' own headers cite these exact layouts, so no
    re-packing. Populated per layer ONLY when `self.msl_any_linked` (empty lists otherwise -- see
    that field's own docstring); kept as per-layer lists on THIS struct, never new fields on the
    shared `_MBLayerBufI8`, the same blast-radius discipline `self.af_ck_native_addr`'s own field
    docstring already gives."""

    var descriptors_prefill_af_nomirror: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_prefill_af_nomirror: Int
    """`1 + n_layers*8 + 2` -- see `PF_ATTN_GROUPED_FA_NO_MIRROR`'s own docstring. Built
    (copy-and-extend of `_build_descriptors_prefill_af`, minus the mirror dispatch) only if BOTH
    `self.af_pipeline_idx` entries were discovered -- the SAME guard `self.descriptors_prefill_af`
    itself uses, since this table needs the identical two `attention_forge/` kernels and nothing
    else new (never `self.native_decode_attn_pipeline_idx` -- decode's own kernel is irrelevant to
    prefill)."""
    var embed_af2_d: Int
    var rmsnorm_af2_d: List[Int]
    var gemm_assign_af2_d: List[Int]
    var kvprod_af2_d: List[Int]
    var kvprod_q_af2_d: List[Int]
    """No-mirror twin of `kvprod_q_af_d` -- per-layer descriptor index of the V2 Q-pass dispatch
    in `descriptors_prefill_af_nomirror`, patched per call by `_apply_m_rows_af_nomirror`."""

    var attn_af2_d: List[Int]
    var gemv_o_af2_d: List[Int]
    var rmsnorm2_af2_d: List[Int]
    var swiglu_af2_d: List[Int]
    var gemv_down_af2_d: List[Int]
    var lmhead_af2_d: Int
    """Same per-role descriptor-index bookkeeping convention as `self.rmsnorm_af_d`/etc. -- the `af2`
    suffix marks "AF table, mirror-free variant", parallel to (never replacing) the `af` suffix's own
    with-mirror table."""

    var descriptors_decode_native: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_decode_native: Int
    """Same dispatch COUNT as `self.descriptors` (`metaldispatch_dispatch_budget(n_layers)`, `1 +
    n_layers*6 + 2`) -- six per-layer roles either way (`norm_gemv`/native-KV-producer/native-decode-
    attn/`gemv_accum`(o)/`norm_gemv2_swiglu`/`gemv_accum`(down)); only two of those six roles read or
    write the native-packed buffers instead of `ck`/`cv`/`q_rot`/`hidden`. Built only if `self.af_
    pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] >= 0` (per-step cache append) AND `self.native_decode_
    attn_pipeline_idx >= 0` (the attention read itself) -- deliberately NOT gated on `self.af_
    pipeline_idx[_AFROLE_GROUPED_FA_ATTN]` (Candidate A) at all, since decode never dispatches that
    kernel; only `prefill_batch`'s own AF tables do."""
    var token_id_offset_native: Int
    var pos_offsets_native: List[Int]
    """Per-layer descriptor index of the native-KV-producer dispatch's own `pos_base` scalar arg
    (arg index 8, same position `_build_descriptors_prefill_af`'s own kvprod dispatch uses) --
    patched to the real decode `pos` every `step_native_kv` call, parallel to `self.pos_offsets`."""
    var nkeys_offsets_native: List[Int]
    """Per-layer descriptor index of the native-decode-attn dispatch's own `n_keys` scalar arg (arg
    index 4 of `_native_kv_decode_attn_kernel`'s own 11-arg signature) -- patched to `pos + 1` every
    `step_native_kv` call, parallel to `self.nkeys_offsets`."""

    var descriptors_decode_native_splitk: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_decode_native_splitk: Int
    """`1 + n_layers*7 + 2` -- the native-KV decode table's split-K twin (beat-llama.cpp campaign,
    2026-08-08 night): SAME seven per-layer roles minus one plus two -- the naive single-dispatch
    decode-attention slot is replaced by the flash-decoding PAIR (the split-K partial at grid
    `h_q * _NATIVE_DECODE_N_SPLITS` writing unnormalized (m, l, o) partials into `self.splitk_m_
    addr`/`l`/`o`, then the engine's EXISTING `_splitk_merge_kernel_simd` collapsing them into
    `self.attn_out_addr` -- the SAME merge kernel the legacy deep path uses, layout-agnostic by its
    own contract, reused completely unchanged). Built only if `self.af_pipeline_idx[_AFROLE_NATIVE_
    KV_PRODUCER] >= 0` AND `self.native_decode_attn_pipeline_idx >= 0` AND `self.native_decode_
    splitk_partial_pipeline_idx >= 0` AND `self.pipeline_idx_merge >= 0` -- the naive table's own
    two-kernel guard plus the two split-K-specific pipelines; `_step_native_kv_impl` dispatches this
    table exactly when `pos + 1 >= _NATIVE_DECODE_SPLITK_THRESHOLD`, the naive one below."""
    var native_decode_splitk_built: Bool
    """True iff `self.descriptors_decode_native_splitk` was actually allocated+populated by
    `__init__` (all four guard pipelines present) -- the ONE flag `_step_native_kv_impl` and
    `expected_decode_dispatch_count` read to decide whether the split-K table exists; never derived
    from the descriptor pointer or count, which both hold placeholder values regardless."""
    var token_id_offset_native_splitk: Int
    var pos_offsets_native_splitk: List[Int]
    var nkeys_offsets_native_splitk: List[Int]
    """Same three patch-point conventions as the naive table's own `token_id_offset_native`/
    `pos_offsets_native`/`nkeys_offsets_native` (the split-K table's embed token_id arg, per-layer
    producer pos_base arg, per-layer partial-kernel n_keys arg) -- `_step_native_kv_impl` patches
    whichever table it dispatches, never both."""
    var splitk_m_addr: UInt64
    var splitk_l_addr: UInt64
    var splitk_o_addr: UInt64
    """The split-K partial kernel's (m, l, o) scratch buffers -- `h_q * _NATIVE_DECODE_N_SPLITS`
    Float32s each for m/l, `h_q * _NATIVE_DECODE_N_SPLITS * d_head` for o. Allocated UNCONDITIONALLY
    (tiny: ~130 KB at this model) and simply never touched when the split-K table was not built --
    the same allocate-always/never-populate discipline the AF native buffers' own docstring
    documents; reused across ALL layers within one decode step (dispatches inside one command
    buffer execute in submission order, the same in-order reuse every other shared buffer in these
    tables already relies on)."""

    var batch_splitk_m_addr: UInt64
    var batch_splitk_l_addr: UInt64
    var batch_splitk_o_addr: UInt64
    """Project Slipstream Phase 3 (2026-08-09): the BATCHED split-K partial+merge pair's (m, l, o)
    scratch -- `_BATCH_DECODE_MAX_SEQS x` the single-stream `splitk_m/l/o_addr` sizes
    (`_BATCH_DECODE_MAX_SEQS * h_q * _NATIVE_DECODE_N_SPLITS` F32s each for m/l, `... * d_head` for
    o), the `[B, h_q, n_splits]` partial layout the batched partial blob writes and the engine-side
    `_batched_splitk_merge_kernel_simd` reads. Allocated ONLY when `decode_batched_built` (gated, so
    a blobs-absent binary pays none of this), reused across all layers within one batched step."""

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
        requested_plan: UnresolvedPrefillConfig = UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL),
    ) raises:
        """`requested_plan` defaults to `UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL)` --
        byte-for-byte the old all-`False`-booleans default -- so every existing call site that never
        supplies this new, additive, trailing parameter keeps constructing an instance that behaves
        exactly as it always has. Resolved ONCE, at the very end of this constructor (right after
        pipeline discovery, once every `*_pipeline_idx`/`af_pipeline_idx` this resolution reads is
        known), into `self.plan` -- see that field's own docstring and `metaldispatch.session_
        prefill_policy`'s own module docstring for the full account. A caller that wants to change the
        request AFTER construction (this file's own tests do, mirroring the pre-refactor idiom of
        mutating a `Bool` field post-construction, just now through one method instead of up to four
        independent fields) calls the public `self.resolve_plan(new_requested)` below, any time before
        the next `prefill_batch`/`step`/`step_native_kv` call whose behavior should reflect it.

        PROJECT REDLINE REOPENING (2026-08-08), "make unresolved plan state unrepresentable": this
        parameter is `UnresolvedPrefillConfig`, NOT `ResolvedSessionExecutionPlan` -- a caller cannot hand
        this constructor something that already LOOKS resolved and skip the point of resolution (see
        `metaldispatch.session_prefill_policy`'s own module docstring addendum for the full two-layer
        account this closes, including why the type split alone does not make an explicit-vs-default
        call SITE distinguishable -- Mojo has no way to detect "was this argument textually supplied",
        so the real, actionable half of this fix is auditing every construction site in this repo and
        making each one either already call `resolve_plan` explicitly or gain one, which this task's
        own audit did -- `grep -rn "_MBQwen3I8AllSimd7Prefill("` across the whole repo, every result
        checked)."""
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8AllSimd7Prefill: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
                + String(WARP_SIZE) + " -- _sdpa_kernel_simd's SIMD-group reduction requires every "
                + "group full; use _MBQwen3I8 (the barrier-tree _sdpa_kernel) for this shape instead"
            )
        self.d_model = d_model
        self.h_q = h_q
        self.h_kv = h_kv
        self.d_head = d_head
        self.d_ff = d_ff
        self.n_layers = n_layers
        self.vocab = vocab
        self.max_ctx = max_ctx
        self.eps = Float32(eps)
        self.scale = Float32(scale)
        self.n_qkv = (h_q + 2 * h_kv) * d_head

        # ── same eight decode kernels `_MBQwen3I8AllSimd7.__init__` compiles, PLUS the batched-
        # prefill kernels -- this struct's own `step()` needs the first eight; its own `prefill_
        # batch()` needs the rest, now including the weight-stationary-tiled-GEMM pair (`_pf_
        # rmsnorm_rows_kernel`/`_pf_gemm_assign_kernel_i8`) in place of `_pf_qkv_proj_kernel_simd_i8`
        # -- that kernel stays in `residentk.kernels`, byte-unmodified, but this struct no longer
        # compiles or dispatches it (see `_PF_N_ROLES`'s own docstring in `metaldispatch.session`).
        # The deep split-K pair is still deferred to `_ensure_deep_initialized`, unchanged from
        # `_MBQwen3I8AllSimd7`.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel_simd]()
        # ── Parity gap 3 (sampling, 2026-08-10): the logits-emitting lm_head twin, compiled in
        # this same early block so `lmhead_logits_pipeline_idx` is discoverable in this same
        # `__init__` (the sampled tail dispatches it in place of the argmax pair).
        _ = cctx.compile_function[_lmhead_logits_kernel_simd_i8]()
        _ = cctx.compile_function[_pf_embed_rows_kernel_i8]()
        _ = cctx.compile_function[_pf_rmsnorm_rows_kernel]()
        _ = cctx.compile_function[_pf_gemm_assign_kernel_i8]()
        _ = cctx.compile_function[_pf_ropewrt_kernel]()
        _ = cctx.compile_function[_pf_attn_tiled_kernel_simd]()
        _ = cctx.compile_function[_pf_attn8_kernel_simd]()
        _ = cctx.compile_function[_pf_gemm_accum_kernel_i8]()
        _ = cctx.compile_function[_pf_gemm_swiglu_kernel_i8]()
        _ = cctx.compile_function[_pf_gnrw_assign_kernel_i8]()
        _ = cctx.compile_function[_pf_gnrw_accum_kernel_i8]()
        _ = cctx.compile_function[_pf_gnrw_swiglu_kernel_i8]()
        # ── Project Slipstream Phase 3 (2026-08-09): the engine-side B-aware merge half of the
        # batched flash-decoding pair (the partial half is the `native_kv_decode_attn_splitk_batched`
        # blob). Compiled here -- in the early block that runs BEFORE `_mb_open_session` and the
        # pipeline-discovery loop below -- so `batched_splitk_merge_pipeline_idx` is discoverable in
        # this same `__init__` (the deep split-K pair is deferred to `_ensure_deep_initialized`, but
        # this one must be present at discovery time for the batched table to build).
        _ = cctx.compile_function[_batched_splitk_merge_kernel_simd]()
        # Slipstream Phase 3 Option B: the fused B-row lm_head + B-row argmax reduce that replace the
        # B separate single-row `_lmhead_argmax_kernel_simd_i8` tail dispatches, sweeping the lm_head
        # weight ONCE for all B rows. Compiled here (same early block, same discovery-time reason).
        _ = cctx.compile_function[_batched_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function[_batched_argmax_reduce_kernel_simd]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.n_cores = _mb_gpu_core_count()
        self.n_splits_max = residentk_splitk_max_n_splits(self.n_cores, self.h_q)
        self.deep_last_n_splits = -1

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        self.prefill_pipeline_idx = List[Int]()
        for _ in range(_PF_N_ROLES):
            self.prefill_pipeline_idx.append(-1)
        self.af_pipeline_idx = List[Int]()
        for _ in range(_AF_N_ROLES):
            self.af_pipeline_idx.append(-1)
        # ── Project Redline reopening (2026-08-08): ADDITIVE discovery slot for the new decode-side
        # kernel -- see this field's own docstring for the full non-fatal-miss precedent this follows.
        self.native_decode_attn_pipeline_idx = -1
        self.native_decode_splitk_partial_pipeline_idx = -1
        self.kvprod_blk_pipeline_idx = -1
        self.kvprod_qvec_pipeline_idx = -1
        self.kvprod_v2_built = False
        # ── Project Slipstream Phase 3 (2026-08-09): batched-decode discovery slots, same non-fatal-
        # miss pattern -- see each field's own docstring.
        self.native_decode_splitk_partial_batched_pipeline_idx = -1
        self.kvprod_batched_pipeline_idx = -1
        self.batched_splitk_merge_pipeline_idx = -1
        self.batched_lmhead_pipeline_idx = -1
        self.batched_argmax_reduce_pipeline_idx = -1
        self.lmhead_logits_pipeline_idx = -1
        self.decode_batched_built = False
        # ── Project Redline reopening (2026-08-08), step 4: same non-fatal-miss discovery slot,
        # for the OPTIONAL combined-build BM64 qkv_proj kernel -- see `self.qkv_proj_bm64_pipeline_
        # idx`'s own field docstring for the full account.
        self.qkv_proj_bm64_pipeline_idx = -1
        # ── Project Redline reopening (2026-08-08), step 2: same non-fatal-miss discovery slots,
        # for the OPTIONAL combined-build all-4-roles vecload4 GEMM kernels -- see each field's own
        # docstring for the full account.
        self.qkv_proj_vecload4_pipeline_idx = -1
        self.gemm_accum_vecload4_pipeline_idx = -1
        self.swiglu_vecload4_pipeline_idx = -1
        # ── Phase 3 (2026-08-08): same non-fatal-miss discovery slots, for the OPTIONAL hybrid
        # per-role Metal GEMM backend (three hand-written MSL parity metallibs inside `mma_forge/
        # generated/msl_parity_blob.c`) -- see each field's own docstring for the full account.
        self.msl_parity_qkv_proj_pipeline_idx = -1
        self.msl_parity_gemm_accum_pipeline_idx = -1
        self.msl_parity_swiglu_pipeline_idx = -1
        self.msl_splitk8_pipeline_idx = -1
        self.msl_splitk12_pipeline_idx = -1
        var count = _mb_pipeline_count()
        self.pipeline_idx_split = -1
        self.pipeline_idx_merge = -1
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
            var splitk_role = _classify_splitk_pipeline(name)
            if splitk_role == 0:
                self.pipeline_idx_split = i
            elif splitk_role == 1:
                self.pipeline_idx_merge = i
            var pf_role = _classify_prefill_pipeline(name)
            if pf_role >= 0:
                self.prefill_pipeline_idx[pf_role] = i
            # ── Attention Compiler Plan v1.0, Phase 2C: OPTIONAL, non-fatal discovery of the two
            # `attention_forge/` blobs -- see `self.af_pipeline_idx`'s own field docstring and
            # `_classify_attention_forge_pipeline`'s docstring (`metaldispatch.session`) for why a
            # miss here never raises, unlike every OTHER classifier's loop immediately below.
            var af_role = _classify_attention_forge_pipeline(name)
            if af_role >= 0:
                self.af_pipeline_idx[af_role] = i
            # ── Project Redline reopening (2026-08-08): a FOURTH, file-private, non-fatal-miss
            # discovery check -- see `self.native_decode_attn_pipeline_idx`'s own field docstring for
            # why this stays local to this struct rather than joining `_classify_attention_forge_
            # pipeline` in `metaldispatch.session`.
            # Beat-llama.cpp campaign (2026-08-08 night): LONGEST-SUBSTRING-FIRST ordering -- the
            # split-K partial's discovered name contains the naive kernel's substring, so check the
            # longer one first and the naive one in an `elif` (see `self.native_decode_splitk_
            # partial_pipeline_idx`'s own field docstring for why this makes blob scan order
            # irrelevant to which pipeline lands in which field).
            # ── Project Slipstream Phase 3 (2026-08-09): the BATCHED partial's discovered name ALSO
            # contains the single-stream split-K substring (`native_kv_decode_attn_splitk` is a prefix
            # of `native_kv_decode_attn_splitk_bat...`), so check the LONGEST substring (the batched
            # `_bat` one) FIRST, then the single-stream split-K, then the naive -- three-way longest-
            # first, scan order irrelevant.
            if name.find("native_kv_decode_attn_splitk_bat") >= 0:
                self.native_decode_splitk_partial_batched_pipeline_idx = i
            elif name.find("native_kv_decode_attn_splitk") >= 0:
                self.native_decode_splitk_partial_pipeline_idx = i
            elif name.find("native_kv_decode_attn") >= 0:
                self.native_decode_attn_pipeline_idx = i
            # ── Beat-llama.cpp campaign Phase C (2026-08-08 night): the V2 producer's two
            # kernels, unique substrings -- see their field docstrings above.
            if name.find("kvprod_blk") >= 0:
                self.kvprod_blk_pipeline_idx = i
            elif name.find("kvprod_qvec") >= 0:
                self.kvprod_qvec_pipeline_idx = i
            # ── Project Slipstream Phase 3 (2026-08-09): the BATCHED KV producer's unique substring
            # (module `kvprod_batched`, deliberately NOT `native_kv_producer_*` so the shared
            # attention-forge classifier never matches it) -- see its field docstring.
            if name.find("kvprod_batched") >= 0:
                self.kvprod_batched_pipeline_idx = i
            # ── Project Slipstream Phase 3 (2026-08-09): the engine-side B-aware merge, discovered by
            # its 11-char engine-kernel truncation `batched_spl` (distinct from the single-stream
            # merge's `splitk_merg`, which `_classify_splitk_pipeline` already owns) -- see its field
            # docstring and REALRACE_RESULTS.md "THIRD discovery collision".
            if name.find("batched_spl") >= 0:
                self.batched_splitk_merge_pipeline_idx = i
            # ── Project Slipstream Phase 3 Option B: the fused B-row lm_head and the B-row argmax
            # reduce, discovered by their own distinct 11-char engine-kernel truncations
            # (`batched_lmh` / `batched_arg`), each distinct from the single-row `lmhead_argm` and from
            # each other and from the merge's `batched_spl` -- see their field docstrings.
            if name.find("batched_lmh") >= 0:
                self.batched_lmhead_pipeline_idx = i
            if name.find("batched_arg") >= 0:
                self.batched_argmax_reduce_pipeline_idx = i
            # ── Parity gap 3 (sampling, 2026-08-10): the logits-emitting lm_head twin's own
            # 11-char truncation `lmhead_logi` -- `_classify_pipeline` refuses this substring
            # (returns -1), so only this field can ever hold it.
            if name.find("lmhead_logi") >= 0:
                self.lmhead_logits_pipeline_idx = i
            # ── Project Redline reopening (2026-08-08), step 4: same file-private, non-fatal
            # discovery pattern, for the OPTIONAL combined-build BM64 qkv_proj kernel. Checked
            # independently of `_classify_prefill_pipeline`'s own now-excluded "bm64" guard (see that
            # function's own docstring) -- this struct is the ONLY place this kernel's pipeline index
            # is ever read.
            if name.find("mma8x8_bm64") >= 0:
                self.qkv_proj_bm64_pipeline_idx = i
            # ── Project Redline reopening (2026-08-08), step 2: same file-private, non-fatal
            # discovery pattern, for the OPTIONAL combined-build all-4-roles vecload4 GEMM kernels.
            # Checked independently of `_classify_prefill_pipeline`'s own now-excluded "veclo"/
            # "vecload" guards (see that function's own docstring) -- this struct is the ONLY place
            # any of these three kernels' pipeline indices are ever read. Patterns empirically
            # verified against this binary's own real, truncated Metal AIR names via
            # `attention_forge/vecload4_all_roles_discovery_check.mojo` -- each kernel's own field
            # docstring has the exact truncated-name evidence.
            if name.find("proj_gemm_mma8x8_veclo") >= 0:
                self.qkv_proj_vecload4_pipeline_idx = i
            if name.find("accum_mma8x8_vecload") >= 0:
                self.gemm_accum_vecload4_pipeline_idx = i
            if name.find("swiglu_gemm_mma8x8_vecload") >= 0:
                self.swiglu_vecload4_pipeline_idx = i
            # ── Phase 3 (2026-08-08): same file-private, non-fatal discovery pattern, for the
            # OPTIONAL hybrid per-role Metal GEMM backend. Raw xcrun-compiled metallibs carry their
            # kernel names VERBATIM (no Mojo mangler, no truncation -- confirmed by the Phase 3
            # static gate's metal-objdump readback of all three entry points), so these patterns are
            # the exact full names, not truncation-budgeted substrings. Collides with NO existing
            # classifier's patterns -- see `self.msl_parity_qkv_proj_pipeline_idx`'s own field
            # docstring for the full checked-against-every-classifier account.
            if name.find("msl_parity__qkv_proj_mul_mm") >= 0:
                self.msl_parity_qkv_proj_pipeline_idx = i
            if name.find("msl_parity__gemm_accum_mul_mm") >= 0:
                self.msl_parity_gemm_accum_pipeline_idx = i
            if name.find("msl_parity__swiglu_mul_mm") >= 0:
                self.msl_parity_swiglu_pipeline_idx = i
            # ── Beat-llama.cpp campaign front 2, fourth strike (2026-08-09): same file-private,
            # non-fatal discovery pattern for the OPTIONAL split-K accum kernels of
            # `msl_splitk_blob.c` (raw xcrun-compiled names, carried verbatim). Collides with no
            # existing classifier's patterns: `_classify_prefill_pipeline`'s accum pattern is
            # `"gemv_accum"` (not `"gemm_accum"`), and nothing else matches `"msl_splitk"`.
            if name.find("msl_splitk8__gemm_accum") >= 0:
                self.msl_splitk8_pipeline_idx = i
            if name.find("msl_splitk12__gemm_accum") >= 0:
                self.msl_splitk12_pipeline_idx = i
        # ── Beat-llama.cpp campaign Phase C: V2 producer availability, both-or-neither.
        self.kvprod_v2_built = (
            self.kvprod_blk_pipeline_idx >= 0 and self.kvprod_qvec_pipeline_idx >= 0
        )
        # ── Project Slipstream Phase 3: batched-decode availability, all-five (both blobs + the
        # engine-side B-aware merge + the fused B-row lm_head + B-row argmax reduce) discovered or
        # the batched table cannot run.
        self.decode_batched_built = (
            self.native_decode_splitk_partial_batched_pipeline_idx >= 0
            and self.kvprod_batched_pipeline_idx >= 0
            and self.batched_splitk_merge_pipeline_idx >= 0
            and self.batched_lmhead_pipeline_idx >= 0
            and self.batched_argmax_reduce_pipeline_idx >= 0
        )

        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )
        if self.pipeline_idx_split < 0 or self.pipeline_idx_merge < 0:
            raise Error(
                "metaldispatch: _MBQwen3I8AllSimd7Prefill attn-splitk pipeline(s) not found among "
                + String(count) + " discovered pipelines (split=" + String(self.pipeline_idx_split)
                + " merge=" + String(self.pipeline_idx_merge) + "), status="
                + String(MB_ERR_PIPELINE_NOT_FOUND)
            )
        for pf_role in range(_PF_N_ROLES):
            if self.prefill_pipeline_idx[pf_role] < 0:
                raise Error(
                    "metaldispatch: prefill pipeline role " + String(pf_role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )
        # `self.af_pipeline_idx` is deliberately NOT range-checked here -- see its own field
        # docstring and `_classify_attention_forge_pipeline`'s docstring for why a miss is legal.

        # ── Project Redline reopening (2026-08-08), resolved-execution-plan refactor: resolve ONCE,
        # here, right after pipeline discovery (every `*_pipeline_idx`/`af_pipeline_idx` this reads is
        # already known by this point) -- from the constructor's own `requested_plan` parameter, which
        # defaults to `UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL)`, byte-for-byte the old
        # all-`False` default this replaces. See `self.plan`'s own field docstring, `resolve_plan`
        # below, and `metaldispatch.session_prefill_policy`'s own module docstring for the full
        # "explicit request beats default, unconditionally, by construction" account.
        self.plan = requested_plan.resolve(PrefillPipelineAvailability(
            self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] >= 0
            and self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN] >= 0,
            self.qkv_proj_bm64_pipeline_idx >= 0,
            self.qkv_proj_vecload4_pipeline_idx >= 0,
            self.gemm_accum_vecload4_pipeline_idx >= 0,
            self.swiglu_vecload4_pipeline_idx >= 0,
            self.msl_parity_qkv_proj_pipeline_idx >= 0,
            self.msl_parity_gemm_accum_pipeline_idx >= 0,
            self.msl_parity_swiglu_pipeline_idx >= 0,
        ))
        # ── Phase 3 (2026-08-08): the ONE gate for the Float16-weight materialization this struct
        # adds -- see `self.msl_any_linked`'s own field docstring for why a blobs-absent binary
        # stays byte-for-byte identical in memory layout and upload behavior.
        self.msl_any_linked = (
            self.msl_parity_qkv_proj_pipeline_idx >= 0
            or self.msl_parity_gemm_accum_pipeline_idx >= 0
            or self.msl_parity_swiglu_pipeline_idx >= 0
        )
        self.msl_w_qkv_f16_addr = List[UInt64]()
        self.msl_w_qkv_f16_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()
        self.msl_w_o_f16_addr = List[UInt64]()
        self.msl_w_o_f16_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()
        self.msl_w_gu_f16_addr = List[UInt64]()
        self.msl_w_gu_f16_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()
        self.msl_w_down_f16_addr = List[UInt64]()
        self.msl_w_down_f16_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()
        self.af_n_blocks = (max_ctx + _AF_KEY_BLOCK_SIZE - 1) // _AF_KEY_BLOCK_SIZE

        # ── resident buffers: SAME shapes as `_MBQwen3I8AllSimd7` for weights/KV-cache/globals.
        var n_qkv = self.n_qkv
        var n_pairs = d_head // 2

        self.af_ck_native_addr = List[UInt64]()
        self.af_ck_native_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()
        self.af_cv_native_addr = List[UInt64]()
        self.af_cv_native_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()

        # ── Project Slipstream Phase 3: batched-decode per-sequence KV cache lists (allocated per
        # layer below, gated on `decode_batched_built`). `batch_kv_stride_elems` = one sequence's
        # native-packed cache element count, the batched kernels' `kv_stride` argument.
        self.batch_kv_stride_elems = h_kv * self.af_n_blocks * d_head * _AF_KEY_BLOCK_SIZE
        self.batch_ck_native_addr = List[UInt64]()
        self.batch_ck_native_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()
        self.batch_cv_native_addr = List[UInt64]()
        self.batch_cv_native_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()

        self.layers = List[_MBLayerBufI8]()
        for _ in range(n_layers):
            var ln1a = UInt64(0); var ln1p = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var ln2a = UInt64(0); var ln2p = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var qna = UInt64(0); var qnp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var kna = UInt64(0); var knp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wqkva = UInt64(0); var wqkvp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wqkvsa = UInt64(0); var wqkvsp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var woa = UInt64(0); var wop = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wosa = UInt64(0); var wosp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wgua = UInt64(0); var wgup = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wgusa = UInt64(0); var wgusp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wdowna = UInt64(0); var wdownp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wdownsa = UInt64(0); var wdownsp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var cka = UInt64(0); var ckp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var cva = UInt64(0); var cvp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            if _mb_alloc_buffer(d_model * 4, ln1a, ln1p) < 0:
                raise Error("metaldispatch: buffer alloc failed (ln1), status=" + String(MB_ERR_BUFFER_ALLOC_FAILED))
            if _mb_alloc_buffer(d_model * 4, ln2a, ln2p) < 0:
                raise Error("metaldispatch: buffer alloc failed (ln2)")
            if _mb_alloc_buffer(d_head * 4, qna, qnp) < 0:
                raise Error("metaldispatch: buffer alloc failed (qn)")
            if _mb_alloc_buffer(d_head * 4, kna, knp) < 0:
                raise Error("metaldispatch: buffer alloc failed (kn)")
            if _mb_alloc_buffer(n_qkv * d_model * 1, wqkva, wqkvp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_qkv i8)")
            if _mb_alloc_buffer(n_qkv * 4, wqkvsa, wqkvsp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_qkv_scale)")
            if _mb_alloc_buffer(d_model * h_q * d_head * 1, woa, wop) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_o i8)")
            if _mb_alloc_buffer(d_model * 4, wosa, wosp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_o_scale)")
            if _mb_alloc_buffer(2 * d_ff * d_model * 1, wgua, wgup) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_gu i8)")
            if _mb_alloc_buffer(2 * d_ff * 4, wgusa, wgusp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_gu_scale)")
            if _mb_alloc_buffer(d_model * d_ff * 1, wdowna, wdownp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_down i8)")
            if _mb_alloc_buffer(d_model * 4, wdownsa, wdownsp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_down_scale)")
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 4, cka, ckp) < 0:
                raise Error("metaldispatch: buffer alloc failed (ck)")
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 4, cva, cvp) < 0:
                raise Error("metaldispatch: buffer alloc failed (cv)")
            self.layers.append(_MBLayerBufI8(
                ln1a, ln1p, ln2a, ln2p, qna, qnp, kna, knp,
                wqkva, wqkvp, wqkvsa, wqkvsp,
                woa, wop, wosa, wosp,
                wgua, wgup, wgusa, wgusp,
                wdowna, wdownp, wdownsa, wdownsp,
                cka, ckp, cva, cvp,
            ))

            # ── Attention Compiler Plan v1.0, Phase 2C: native-packed F16 K/V, ADDITIVE to (never a
            # replacement of) the `ck`/`cv` pair just allocated above -- allocated UNCONDITIONALLY,
            # regardless of `self.plan.attention`, per this struct's own documented choice to always
            # allocate the AF buffers and simply never populate/dispatch them when the resolved plan
            # is `PF_ATTN_OFF` (see `self.af_ck_native_addr`'s own field docstring). Same total
            # element count as `ck`/`cv` (`h_kv * af_n_blocks * d_head * _AF_KEY_BLOCK_SIZE`, vs.
            # `ck`/`cv`'s own `max_ctx * h_kv * d_head` -- equal since `af_n_blocks *
            # _AF_KEY_BLOCK_SIZE >= max_ctx` by construction), at 2 bytes (Float16) instead of 4.
            var ckna = UInt64(0); var cknp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var cvna = UInt64(0); var cvnp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var af_native_elems = h_kv * self.af_n_blocks * d_head * _AF_KEY_BLOCK_SIZE
            if _mb_alloc_buffer(af_native_elems * 2, ckna, cknp) < 0:
                raise Error("metaldispatch: buffer alloc failed (af ck_native)")
            if _mb_alloc_buffer(af_native_elems * 2, cvna, cvnp) < 0:
                raise Error("metaldispatch: buffer alloc failed (af cv_native)")
            self.af_ck_native_addr.append(ckna)
            self.af_ck_native_ptr.append(cknp)
            self.af_cv_native_addr.append(cvna)
            self.af_cv_native_ptr.append(cvnp)

            # ── Project Slipstream Phase 3 (2026-08-09): per-sequence BATCHED-decode KV caches for
            # this layer -- `_BATCH_DECODE_MAX_SEQS` concatenated sequence-caches per K and per V,
            # sequence `b` at element offset `b * self.batch_kv_stride_elems`. Allocated ONLY when the
            # batched decode pipelines were discovered (`decode_batched_built`), so a blobs-absent
            # binary pays none of this memory (same gating discipline as the MSL f16 twins below).
            if self.decode_batched_built:
                var bckna = UInt64(0); var bcknp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
                var bcvna = UInt64(0); var bcvnp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
                var batch_elems = _BATCH_DECODE_MAX_SEQS * self.batch_kv_stride_elems
                if _mb_alloc_buffer(batch_elems * 2, bckna, bcknp) < 0:
                    raise Error("metaldispatch: buffer alloc failed (batch ck_native)")
                if _mb_alloc_buffer(batch_elems * 2, bcvna, bcvnp) < 0:
                    raise Error("metaldispatch: buffer alloc failed (batch cv_native)")
                self.batch_ck_native_addr.append(bckna)
                self.batch_ck_native_ptr.append(bcknp)
                self.batch_cv_native_addr.append(bcvna)
                self.batch_cv_native_ptr.append(bcvnp)
            else:
                # Keep the per-layer lists parallel to `self.layers` even when not provisioned.
                self.batch_ck_native_addr.append(UInt64(0))
                self.batch_ck_native_ptr.append(UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1))
                self.batch_cv_native_addr.append(UInt64(0))
                self.batch_cv_native_ptr.append(UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1))

            # ── Phase 3 (2026-08-08): per-layer ALREADY-DEQUANTIZED Float16 twins of the four
            # GEMM weight buffers, allocated ONLY when at least one MSL parity pipeline was
            # discovered (see `self.msl_any_linked`'s own field docstring) -- same element counts as
            # the Int8 originals, 2 bytes instead of 1. A blobs-absent binary never reaches this
            # branch and keeps its pre-Phase-3 allocation sequence exactly.
            if self.msl_any_linked:
                var wqkva16 = UInt64(0); var wqkvp16 = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
                var wo16 = UInt64(0); var wop16 = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
                var wgu16 = UInt64(0); var wgup16 = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
                var wdown16 = UInt64(0); var wdownp16 = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
                if _mb_alloc_buffer(n_qkv * d_model * 2, wqkva16, wqkvp16) < 0:
                    raise Error("metaldispatch: buffer alloc failed (msl w_qkv f16)")
                if _mb_alloc_buffer(d_model * h_q * d_head * 2, wo16, wop16) < 0:
                    raise Error("metaldispatch: buffer alloc failed (msl w_o f16)")
                if _mb_alloc_buffer(2 * d_ff * d_model * 2, wgu16, wgup16) < 0:
                    raise Error("metaldispatch: buffer alloc failed (msl w_gu f16)")
                if _mb_alloc_buffer(d_model * d_ff * 2, wdown16, wdownp16) < 0:
                    raise Error("metaldispatch: buffer alloc failed (msl w_down f16)")
                self.msl_w_qkv_f16_addr.append(wqkva16)
                self.msl_w_qkv_f16_ptr.append(wqkvp16)
                self.msl_w_o_f16_addr.append(wo16)
                self.msl_w_o_f16_ptr.append(wop16)
                self.msl_w_gu_f16_addr.append(wgu16)
                self.msl_w_gu_f16_ptr.append(wgup16)
                self.msl_w_down_f16_addr.append(wdown16)
                self.msl_w_down_f16_ptr.append(wdownp16)

        self.embed_addr = UInt64(0); self.embed_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.embed_scale_addr = UInt64(0); self.embed_scale_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.final_norm_addr = UInt64(0); self.final_norm_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.cos_addr = UInt64(0); self.cos_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.sin_addr = UInt64(0); self.sin_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        if _mb_alloc_buffer(vocab * d_model * 1, self.embed_addr, self.embed_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (embed i8)")
        if _mb_alloc_buffer(vocab * 4, self.embed_scale_addr, self.embed_scale_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (embed_scale)")
        if _mb_alloc_buffer(d_model * 4, self.final_norm_addr, self.final_norm_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (final_norm)")
        if _mb_alloc_buffer(max_ctx * n_pairs * 4, self.cos_addr, self.cos_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (cos)")
        if _mb_alloc_buffer(max_ctx * n_pairs * 4, self.sin_addr, self.sin_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (sin)")

        # ── activation buffers: sized for `PREFILL_MAX_TILE` ROWS, not one -- see module docstring
        # "BUFFER SIZING". `step()`'s own descriptor plan below never asks for more than row 0.
        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.xn_addr = UInt64(0); self.xn_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.prompt_ids_addr = UInt64(0); self.prompt_ids_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        var n_q = h_q * d_head
        if _mb_alloc_buffer(PREFILL_MAX_TILE * d_model * 4, self.hidden_addr, self.hidden_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (hidden)")
        if _mb_alloc_buffer(PREFILL_MAX_TILE * d_model * 4, self.xn_addr, self.xn_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (xn)")
        if _mb_alloc_buffer(PREFILL_MAX_TILE * n_qkv * 4, self.qkv_addr, self.qkv_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (qkv)")
        if _mb_alloc_buffer(PREFILL_MAX_TILE * n_q * 4, self.q_rot_addr, self.q_rot_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (q_rot)")
        if _mb_alloc_buffer(PREFILL_MAX_TILE * n_q * 4, self.attn_out_addr, self.attn_out_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn_out)")
        if _mb_alloc_buffer(PREFILL_MAX_TILE * d_ff * 4, self.act_addr, self.act_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (act)")
        if _mb_alloc_buffer(_LM_BLOCKS * 4, self.blk_val_addr, self.blk_val_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (blk_val)")
        if _mb_alloc_buffer(_LM_BLOCKS * 4, self.blk_idx_addr, self.blk_idx_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (blk_idx)")
        if _mb_alloc_buffer(4, self.out_val_addr, self.out_val_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (out_val)")
        if _mb_alloc_buffer(4, self.out_idx_addr, self.out_idx_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (out_idx)")
        if _mb_alloc_buffer(PREFILL_MAX_TILE * 4, self.prompt_ids_addr, self.prompt_ids_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (prompt_ids)")
        # ── Parity gap 3 (sampling, 2026-08-10): vocab-wide Float32 logits row (~600 KB at
        # Qwen3 scale) -- the sampled tail's output buffer, read back host-side by the sampler.
        self.logits_addr = UInt64(0); self.logits_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        if _mb_alloc_buffer(vocab * 4, self.logits_addr, self.logits_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (logits)")

        # ── Project Slipstream Phase 3: batched-decode tail + per-sequence state buffers, gated on
        # `decode_batched_built` (blobs-absent pays none of it). The B single-row lm_head/argmax tail
        # reuses the single-row kernels dispatched B times (one per sequence) into B-sized partial/out
        # regions; `batch_poss`/`batch_nkeys` are the per-sequence Int64 device arrays the batched
        # kvprod / batched attention-partial blobs read.
        self.batch_blk_val_addr = UInt64(0); self.batch_blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.batch_blk_idx_addr = UInt64(0); self.batch_blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.batch_out_val_addr = UInt64(0); self.batch_out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.batch_out_idx_addr = UInt64(0); self.batch_out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.batch_poss_addr = UInt64(0); self.batch_poss_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.batch_nkeys_addr = UInt64(0); self.batch_nkeys_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.descriptors_decode_batched = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.n_descriptors_decode_batched = 0
        self.decode_batched_B = 0
        if self.decode_batched_built:
            var B = _BATCH_DECODE_MAX_SEQS
            if _mb_alloc_buffer(B * _LM_BLOCKS * 4, self.batch_blk_val_addr, self.batch_blk_val_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch blk_val)")
            if _mb_alloc_buffer(B * _LM_BLOCKS * 4, self.batch_blk_idx_addr, self.batch_blk_idx_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch blk_idx)")
            if _mb_alloc_buffer(B * 4, self.batch_out_val_addr, self.batch_out_val_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch out_val)")
            if _mb_alloc_buffer(B * 4, self.batch_out_idx_addr, self.batch_out_idx_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch out_idx)")
            if _mb_alloc_buffer(B * 8, self.batch_poss_addr, self.batch_poss_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch poss)")
            if _mb_alloc_buffer(B * 8, self.batch_nkeys_addr, self.batch_nkeys_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch nkeys)")

        # ── Attention Compiler Plan v1.0, Phase 2C: session-level AF activation buffers, ADDITIVE,
        # allocated UNCONDITIONALLY (same "always allocate, never populate/dispatch when off" choice
        # as the per-layer native K/V buffers above) -- see `self.q_native_addr`'s/`self.lse_scratch_
        # addr`'s own field docstrings.
        self.q_native_addr = UInt64(0); self.q_native_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.lse_scratch_addr = UInt64(0); self.lse_scratch_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        if _mb_alloc_buffer(PREFILL_MAX_TILE * n_q * 2, self.q_native_addr, self.q_native_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (af q_native)")
        if _mb_alloc_buffer(h_q * PREFILL_MAX_TILE * 4, self.lse_scratch_addr, self.lse_scratch_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (af lse_scratch)")

        # ── Beat-llama.cpp campaign (2026-08-08 night): the split-K DECODE partial kernel's
        # (m, l, o) scratch, allocated UNCONDITIONALLY (see the field docstring: tiny, and never
        # touched when the split-K table's own four-pipeline guard below leaves it unbuilt). Only
        # the device ADDRESSES are kept -- descriptor args are addresses, and no host-side readback
        # ever touches these buffers (the merge kernel reads them GPU-side).
        self.splitk_m_addr = UInt64(0)
        self.splitk_l_addr = UInt64(0)
        self.splitk_o_addr = UInt64(0)
        var splitk_m_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        var splitk_l_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        var splitk_o_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        if _mb_alloc_buffer(h_q * _NATIVE_DECODE_N_SPLITS * 4, self.splitk_m_addr, splitk_m_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (splitk m)")
        if _mb_alloc_buffer(h_q * _NATIVE_DECODE_N_SPLITS * 4, self.splitk_l_addr, splitk_l_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (splitk l)")
        if _mb_alloc_buffer(h_q * _NATIVE_DECODE_N_SPLITS * d_head * 4, self.splitk_o_addr, splitk_o_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (splitk o)")

        # ── Project Slipstream Phase 3: B-sized split-K scratch for the batched partial+merge pair,
        # gated on `decode_batched_built` (blobs-absent pays none of it).
        self.batch_splitk_m_addr = UInt64(0)
        self.batch_splitk_l_addr = UInt64(0)
        self.batch_splitk_o_addr = UInt64(0)
        if self.decode_batched_built:
            var bsm_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var bsl_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var bso_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var b_ml_elems = _BATCH_DECODE_MAX_SEQS * h_q * _NATIVE_DECODE_N_SPLITS
            if _mb_alloc_buffer(b_ml_elems * 4, self.batch_splitk_m_addr, bsm_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch splitk m)")
            if _mb_alloc_buffer(b_ml_elems * 4, self.batch_splitk_l_addr, bsl_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch splitk l)")
            if _mb_alloc_buffer(b_ml_elems * d_head * 4, self.batch_splitk_o_addr, bso_ptr) < 0:
                raise Error("metaldispatch: buffer alloc failed (batch splitk o)")

        self.m_partial_addr = UInt64(0); self.m_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.l_partial_addr = UInt64(0); self.l_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.o_partial_addr = UInt64(0); self.o_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()

        self.n_descriptors_deep = 1 + self.n_layers * 7 + 2
        self.descriptors_deep = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.token_id_offset_deep = -1
        self.pos_offsets_deep = List[Int]()
        self.nkeys_offsets_deep = List[Int]()
        self.deep_ready = False

        # Was `1 + n_layers*6 + 2` through PR #584's own Phase 1, then `1 + n_layers*7 + 2` once
        # `qkv_proj` became `rmsnorm` + `gemm_assign`. Now `o_proj`/`down_proj` are `gemm_accum`
        # (unchanged dispatch count, same role reused twice, just a different kernel) and `swiglu`
        # became a SECOND `rmsnorm` dispatch (its own gamma buffer, `ln2`) feeding `gemm_swiglu` --
        # one more dispatch per layer than the Phase-A state.
        self.n_descriptors_prefill = 1 + self.n_layers * 8 + 2
        self.descriptors_prefill = _mb_alloc_descriptors(self.n_descriptors_prefill)
        self.embed_d = -1
        self.rmsnorm_d = List[Int]()
        self.gemm_assign_d = List[Int]()
        self.ropewrt_d = List[Int]()
        self.attn_d = List[Int]()
        self.gemv_o_d = List[Int]()
        self.rmsnorm2_d = List[Int]()
        self.swiglu_d = List[Int]()
        self.gemv_down_d = List[Int]()
        self.lmhead_d = -1

        # ── Attention Compiler Plan v1.0, Phase 2C: a COMPLETE, SEPARATE table -- see `self.
        # descriptors_prefill_af`'s own field docstring. ONE MORE dispatch per layer than the OFF
        # table (`1 + n_layers*9 + 2`, not `...*8...`) regardless of whether it ends up actually
        # built below -- the extra dispatch is the natural-cache double-write (`self.kvprod_mirror_
        # af_d`) that closes the decode-after-AF-prefill gap; see that field's own docstring.
        self.n_descriptors_prefill_af = 1 + self.n_layers * 9 + 2 + (
            self.n_layers if self.kvprod_v2_built else 0)
        self.descriptors_prefill_af = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.embed_af_d = -1
        self.rmsnorm_af_d = List[Int]()
        self.gemm_assign_af_d = List[Int]()
        self.kvprod_af_d = List[Int]()
        self.kvprod_q_af_d = List[Int]()
        self.kvprod_mirror_af_d = List[Int]()
        self.attn_af_d = List[Int]()
        self.gemv_o_af_d = List[Int]()
        self.rmsnorm2_af_d = List[Int]()
        self.swiglu_af_d = List[Int]()
        self.gemv_down_af_d = List[Int]()
        self.lmhead_af_d = -1

        # ── Project Redline reopening (2026-08-08): placeholder init for the two NEW tables, same
        # "set the real budget now, allocate/build only if the guard below passes" discipline as
        # `self.descriptors_prefill_af` immediately above.
        self.n_descriptors_prefill_af_nomirror = 1 + self.n_layers * 8 + 2 + (
            self.n_layers if self.kvprod_v2_built else 0)
        self.descriptors_prefill_af_nomirror = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.embed_af2_d = -1
        self.rmsnorm_af2_d = List[Int]()
        self.gemm_assign_af2_d = List[Int]()
        self.kvprod_af2_d = List[Int]()
        self.kvprod_q_af2_d = List[Int]()
        self.attn_af2_d = List[Int]()
        self.gemv_o_af2_d = List[Int]()
        self.rmsnorm2_af2_d = List[Int]()
        self.swiglu_af2_d = List[Int]()
        self.gemv_down_af2_d = List[Int]()
        self.lmhead_af2_d = -1

        self.n_descriptors_decode_native = metaldispatch_dispatch_budget(n_layers)
        self.descriptors_decode_native = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.token_id_offset_native = -1
        self.pos_offsets_native = List[Int]()
        self.nkeys_offsets_native = List[Int]()

        # ── Beat-llama.cpp campaign (2026-08-08 night): split-K decode table placeholders, same
        # convention -- the count is `1 + n_layers*7 + 2` (the naive table's six per-layer roles,
        # with the single decode-attn dispatch replaced by the partial+merge PAIR), self-checked by
        # `_build_descriptors_decode_native_splitk`'s own tail; never actually allocated unless the
        # four-pipeline guard below passes.
        self.n_descriptors_decode_native_splitk = 1 + n_layers * 7 + 2
        self.descriptors_decode_native_splitk = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.native_decode_splitk_built = False
        self.token_id_offset_native_splitk = -1
        self.pos_offsets_native_splitk = List[Int]()
        self.nkeys_offsets_native_splitk = List[Int]()

        self._build_descriptors(n_qkv)
        self._build_descriptors_prefill(n_qkv)

        # ── Only actually BUILD the AF table if both `attention_forge/` blobs were discovered above
        # (see `self.af_pipeline_idx`'s own field docstring) -- otherwise leave `self.
        # descriptors_prefill_af` as the placeholder pointer and `self.n_descriptors_prefill_af`
        # unchanged from the value set above (still `1 + n_layers*9 + 2`, but never actually
        # allocated or populated); `prefill_batch` checks `self.af_pipeline_idx` again before ever
        # submitting this table, so a stale, never-built `n_descriptors_prefill_af` count alone
        # cannot cause a bad dispatch -- see that method's own guard.
        if (
            self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] >= 0
            and self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN] >= 0
        ):
            self.descriptors_prefill_af = _mb_alloc_descriptors(self.n_descriptors_prefill_af)
            self._build_descriptors_prefill_af(n_qkv)
            # ── Project Redline reopening (2026-08-08): the mirror-free prefill table needs the
            # identical two kernels this guard already confirmed are present -- see `self.
            # descriptors_prefill_af_nomirror`'s own field docstring.
            self.descriptors_prefill_af_nomirror = _mb_alloc_descriptors(self.n_descriptors_prefill_af_nomirror)
            self._build_descriptors_prefill_af_nomirror(n_qkv)

        # ── Project Redline reopening (2026-08-08): the new decode-native table has its OWN, looser
        # guard -- see `self.descriptors_decode_native`'s own field docstring for why Candidate A's
        # own pipeline is irrelevant here.
        if (
            self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] >= 0
            and self.native_decode_attn_pipeline_idx >= 0
        ):
            self.descriptors_decode_native = _mb_alloc_descriptors(self.n_descriptors_decode_native)
            self._build_descriptors_decode_native(n_qkv)

        # ── Beat-llama.cpp campaign (2026-08-08 night): the split-K decode table's OWN guard --
        # the naive table's two kernels PLUS the split-K partial blob PLUS the engine's existing
        # merge kernel (compiled unconditionally by THIS struct's own `__init__` split-K compile
        # pair above, so `self.pipeline_idx_merge` is always set once discovery saw it -- both
        # split-K kernels are pinned-toolchain code, never blobs). Any missing piece leaves the
        # table unbuilt and `_step_native_kv_impl` on the naive path at every depth.
        if (
            self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] >= 0
            and self.native_decode_attn_pipeline_idx >= 0
            and self.native_decode_splitk_partial_pipeline_idx >= 0
            and self.pipeline_idx_merge >= 0
        ):
            self.descriptors_decode_native_splitk = _mb_alloc_descriptors(self.n_descriptors_decode_native_splitk)
            self._build_descriptors_decode_native_splitk(n_qkv)
            self.native_decode_splitk_built = True

    def resolve_plan(mut self, requested: UnresolvedPrefillConfig) raises:
        """Project Redline reopening (2026-08-08), resolved-execution-plan refactor: the PUBLIC,
        explicit re-resolution entry point -- for a caller that wants to change `self.plan` AFTER
        construction (this file's own tests do; `__init__` already resolved once, from its own
        `requested_plan` parameter, using the exact SAME `UnresolvedPrefillConfig.resolve` method
        this method calls). Callable any number of times; each call is a full, independent
        re-resolution against this instance's OWN real pipeline availability (never a partial update
        layered on top of a previous call's result) -- so calling it twice with two different
        requests behaves exactly as if the second request were the only one ever made, matching
        `ResolvedSessionExecutionPlan`'s own "a single value, not several independently-mutable flags" design
        (see `metaldispatch.session_prefill_policy`'s own module docstring for why that is precisely
        the property that makes regression #2 -- an explicit request silently outranked by a
        different path's own stale default -- structurally impossible here, not merely fixed by
        reordering a check).

        `requested` is `UnresolvedPrefillConfig`, not `ResolvedSessionExecutionPlan` -- "make unresolved plan
        state unrepresentable" (2026-08-08): this is the ONE public entry point besides the
        constructor that ever writes `self.plan`, and it accepts only a request, never something
        that already looks resolved.

        Must be called before the next `prefill_batch`/`step`/`step_native_kv` call whose behavior
        should reflect the new request -- `self.plan` is read at DISPATCH time, not cached ahead of
        it in any way this method would need to invalidate."""
        self.plan = requested.resolve(PrefillPipelineAvailability(
            self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] >= 0
            and self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN] >= 0,
            self.qkv_proj_bm64_pipeline_idx >= 0,
            self.qkv_proj_vecload4_pipeline_idx >= 0,
            self.gemm_accum_vecload4_pipeline_idx >= 0,
            self.swiglu_vecload4_pipeline_idx >= 0,
            self.msl_parity_qkv_proj_pipeline_idx >= 0,
            self.msl_parity_gemm_accum_pipeline_idx >= 0,
            self.msl_parity_swiglu_pipeline_idx >= 0,
        ))

    def _require_resolved_plan(self) raises:
        """Project Redline reopening (2026-08-08), "make unresolved plan state unrepresentable" --
        defense-in-depth, NOT the primary guarantee (construction and `resolve_plan` both already
        always leave `self.plan` genuinely resolved -- see that field's own docstring). `self.plan`
        is a public `var` field, and this pinned Mojo toolchain (1.0.0b2) has no cross-module
        private-field enforcement, so nothing stops a caller from directly assigning `session.plan =
        ResolvedSessionExecutionPlan(PF_UNRESOLVED, PF_UNRESOLVED, PF_UNRESOLVED, PF_UNRESOLVED)` (or
        any other out-of-range OR self-contradictory value -- round 5, 2026-08-08: `is_resolved()`
        now also rejects a `kv_contract`/`decode` that disagrees with `self.attention` even if each
        field individually looks valid), bypassing `resolve_plan`/`UnresolvedPrefillConfig.resolve`
        entirely. Called by `prefill_batch` (before its own three-way branch), independently by
        `_apply_m_rows_af_nomirror` (so this guard does not silently depend on being reached only
        through `prefill_batch`), and (round 5) by the public `step()` router, independently of both
        -- see `metaldispatch.session_prefill_policy`'s own module docstring addendum and
        `ResolvedSessionExecutionPlan.is_resolved()`'s own docstring for the full account of why this
        raises a loud, clear error rather than silently treating an invalid plan as `PF_ATTN_OFF`/
        `PF_GEMM_ORIGINAL` -- the entire point of this redesign is that an unresolved/invalid plan
        must never become one more silent default alongside the two this file has already had to
        fix."""
        if not self.plan.is_resolved():
            raise Error(
                "_MBQwen3I8AllSimd7Prefill: refusing to dispatch -- self.plan (attention="
                + String(self.plan.attention) + ", gemm=" + String(self.plan.gemm)
                + ", kv_contract=" + String(self.plan.kv_contract) + ", decode="
                + String(self.plan.decode) + ") is not a resolved ResolvedSessionExecutionPlan "
                + "(is_resolved() == False). Call resolve_plan(UnresolvedPrefillConfig(...)) before "
                + "prefill_batch()/step(); under the public constructor/resolve_plan API this should "
                + "be unreachable, so this indicates self.plan was written some other way (e.g. a "
                + "direct field assignment)."
            )

    def _ensure_deep_initialized(mut self) raises:
        """Byte-identical lazy-init discipline to `_MBQwen3I8AllSimd7._ensure_deep_initialized`."""
        if self.deep_ready:
            return
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function[_splitk_partial_kernel_simd_native]()
        _ = cctx.compile_function[_splitk_merge_kernel_simd]()

        if _mb_alloc_buffer(self.h_q * self.n_splits_max * 4, self.m_partial_addr, self.m_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk m_partial)")
        if _mb_alloc_buffer(self.h_q * self.n_splits_max * 4, self.l_partial_addr, self.l_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk l_partial)")
        if _mb_alloc_buffer(self.h_q * self.n_splits_max * self.d_head * 4, self.o_partial_addr, self.o_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk o_partial)")

        self.descriptors_deep = _mb_alloc_descriptors(self.n_descriptors_deep)
        var n_qkv = (self.h_q + 2 * self.h_kv) * self.d_head
        self._build_descriptors_deep(n_qkv)
        self.deep_ready = True

    def _build_descriptors(mut self, n_qkv: Int) raises:
        """Byte-identical plan to `_MBQwen3I8AllSimd7._build_descriptors` -- builds `self.
        descriptors`, the table `step()` submits below `residentk_splitk_should_split`'s gate."""
        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        var d = 0

        _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_EMBED], _ceil_div(self.d_model, _TG), _TG, 5)
        _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors, d, 2, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors, d, 3, 0)  # token_id, patched per step
        self.token_id_offset = d
        _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_NORM_GEMV],
                _ceil_div(n_qkv, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.ln1_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors, d, 4, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors, d, 6, n_qkv)
            _mb_set_arg_f32(self.descriptors, d, 7, self.eps)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_QK_ROPE],
                self.h_q + self.h_kv, self.d_head, 13,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.cv_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors, d, 4, lw.qn_addr)
            _mb_set_arg_ptr(self.descriptors, d, 5, lw.kn_addr)
            _mb_set_arg_ptr(self.descriptors, d, 6, self.cos_addr)
            _mb_set_arg_ptr(self.descriptors, d, 7, self.sin_addr)
            _mb_set_arg_int(self.descriptors, d, 8, 0)  # pos, patched per step
            self.pos_offsets.append(d)
            _mb_set_arg_int(self.descriptors, d, 9, self.h_q)
            _mb_set_arg_int(self.descriptors, d, 10, self.h_kv)
            _mb_set_arg_int(self.descriptors, d, 11, self.d_head)
            _mb_set_arg_f32(self.descriptors, d, 12, self.eps)
            d += 1

            _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_SDPA], self.h_q, self.d_head, 9)
            _mb_set_arg_ptr(self.descriptors, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.cv_addr)
            _mb_set_arg_int(self.descriptors, d, 4, 0)  # n_keys, patched per step
            self.nkeys_offsets.append(d)
            _mb_set_arg_int(self.descriptors, d, 5, self.h_q)
            _mb_set_arg_int(self.descriptors, d, 6, self.h_kv)
            _mb_set_arg_int(self.descriptors, d, 7, self.d_head)
            _mb_set_arg_f32(self.descriptors, d, 8, self.scale)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors, d, 4, n_q)
            _mb_set_arg_int(self.descriptors, d, 5, self.d_model)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_NORM_GEMV2_SWIGLU],
                _ceil_div(self.d_ff, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.ln2_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors, d, 4, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors, d, 6, self.d_ff)
            _mb_set_arg_f32(self.descriptors, d, 7, self.eps)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_ff)
            _mb_set_arg_int(self.descriptors, d, 5, self.d_model)
            d += 1

        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(self.descriptors, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors, d, 2, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors, d, 4, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors, d, 5, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors, d, 7, self.vocab)
        _mb_set_arg_f32(self.descriptors, d, 8, self.eps)
        _mb_set_arg_int(self.descriptors, d, 9, n_iters)
        d += 1

        _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(self.descriptors, d, 0, self.out_val_addr)
        _mb_set_arg_ptr(self.descriptors, d, 1, self.out_idx_addr)
        _mb_set_arg_ptr(self.descriptors, d, 2, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors, d, 3, self.blk_idx_addr)
        _mb_set_arg_int(self.descriptors, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors:
            raise Error(
                "metaldispatch: built " + String(d) + " descriptors but the budget says "
                + String(self.n_descriptors) + " -- the design and the code disagree, status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )

    def _build_descriptors_deep(mut self, n_qkv: Int) raises:
        """Byte-identical plan to `_MBQwen3I8AllSimd7._build_descriptors_deep`."""
        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        var d = 0

        _mb_set_header(self.descriptors_deep, d, self.pipeline_idx[_ROLE_EMBED], _ceil_div(self.d_model, _TG), _TG, 5)
        _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 2, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_deep, d, 3, 0)  # token_id, patched per step
        self.token_id_offset_deep = d
        _mb_set_arg_int(self.descriptors_deep, d, 4, self.d_model)
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]

            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx[_ROLE_NORM_GEMV],
                _ceil_div(n_qkv, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, lw.ln1_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 4, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_deep, d, 6, n_qkv)
            _mb_set_arg_f32(self.descriptors_deep, d, 7, self.eps)
            d += 1

            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx[_ROLE_QK_ROPE],
                self.h_q + self.h_kv, self.d_head, 13,
            )
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, lw.cv_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 4, lw.qn_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 5, lw.kn_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 6, self.cos_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 7, self.sin_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 8, 0)  # pos, patched per step
            self.pos_offsets_deep.append(d)
            _mb_set_arg_int(self.descriptors_deep, d, 9, self.h_q)
            _mb_set_arg_int(self.descriptors_deep, d, 10, self.h_kv)
            _mb_set_arg_int(self.descriptors_deep, d, 11, self.d_head)
            _mb_set_arg_f32(self.descriptors_deep, d, 12, self.eps)
            d += 1

            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx_split,
                self.h_q * self.n_splits_max, WARP_SIZE, 12,
            )
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.m_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.l_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, self.o_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 4, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 5, lw.cv_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 6, 0)  # n_keys, patched per step
            self.nkeys_offsets_deep.append(d)
            _mb_set_arg_int(self.descriptors_deep, d, 7, self.n_splits_max)
            _mb_set_arg_int(self.descriptors_deep, d, 8, self.h_q)
            _mb_set_arg_int(self.descriptors_deep, d, 9, self.h_kv)
            _mb_set_arg_int(self.descriptors_deep, d, 10, self.d_head)
            _mb_set_arg_f32(self.descriptors_deep, d, 11, self.scale)
            d += 1

            _mb_set_header(self.descriptors_deep, d, self.pipeline_idx_merge, self.h_q, self.d_head, 6)
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.m_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, self.l_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, self.o_partial_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 4, self.n_splits_max)
            _mb_set_arg_int(self.descriptors_deep, d, 5, self.d_head)
            d += 1

            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 4, n_q)
            _mb_set_arg_int(self.descriptors_deep, d, 5, self.d_model)
            d += 1

            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx[_ROLE_NORM_GEMV2_SWIGLU],
                _ceil_div(self.d_ff, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, lw.ln2_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 4, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_deep, d, 6, self.d_ff)
            _mb_set_arg_f32(self.descriptors_deep, d, 7, self.eps)
            d += 1

            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 4, self.d_ff)
            _mb_set_arg_int(self.descriptors_deep, d, 5, self.d_model)
            d += 1

        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors_deep, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 2, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 4, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 5, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_deep, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors_deep, d, 7, self.vocab)
        _mb_set_arg_f32(self.descriptors_deep, d, 8, self.eps)
        _mb_set_arg_int(self.descriptors_deep, d, 9, n_iters)
        d += 1

        _mb_set_header(self.descriptors_deep, d, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.out_val_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.out_idx_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 2, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_deep, d, 3, self.blk_idx_addr)
        _mb_set_arg_int(self.descriptors_deep, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors_deep:
            raise Error(
                "metaldispatch: built " + String(d) + " deep descriptors but the budget says "
                + String(self.n_descriptors_deep) + " -- the design and the code disagree, status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )

    def _apply_n_splits(mut self, new_n_splits: Int) raises:
        """Byte-identical to `_MBQwen3I8AllSimd7._apply_n_splits` -- see that method's own
        docstring for the full safety argument."""
        for layer in range(self.n_layers):
            var d_split = 1 + 7 * layer + 2
            var d_merge = 1 + 7 * layer + 3
            _mb_set_header(
                self.descriptors_deep, d_split, self.pipeline_idx_split,
                self.h_q * new_n_splits, WARP_SIZE, 12,
            )
            _mb_set_arg_int(self.descriptors_deep, d_split, 7, new_n_splits)
            _mb_set_arg_int(self.descriptors_deep, d_merge, 4, new_n_splits)

    def _build_descriptors_prefill(mut self, n_qkv: Int) raises:
        """Builds `self.descriptors_prefill` -- ONE embed dispatch, eight per-layer batched
        dispatches (`rmsnorm`, `gemm_assign` [replacing the fused `qkv_proj`], `ropewrt`, `attn`,
        `gemm_accum` o_proj, a SECOND `rmsnorm` [its own gamma buffer, `ln2`], `gemm_swiglu`
        [replacing the fused `swiglu`], `gemm_accum` down_proj), then the UNMODIFIED `lmhead_argmax`/
        `argmax_reduce` pair, reused from the decode role table -- `1 + n_layers * 8 + 2`
        descriptors total. Every M-scaled dispatch is built at its own widest possible grid (the
        widest `_apply_m_rows` will ever need), recording its own descriptor index in
        `self.*_d`/`self.*_d[layer]` so `_apply_m_rows` can narrow it later -- see `_MBQwen3I8
        AllSimd7._build_descriptors_deep`'s own docstring for the "build wide, narrow before first
        use" precedent this follows. The `m_rows`/`pos_base` scalar arguments below are all
        placeholder zeros here too, for the identical reason: `_apply_m_rows` patches every one of
        them fresh before the very first `prefill_batch()` call ever submits this table."""
        var n_q = self.h_q * self.d_head
        var d = 0

        _mb_set_header(
            self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            _ceil_div(self.d_model, _TG) * PREFILL_MAX_TILE, _TG, 6,
        )
        _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 2, self.embed_scale_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 3, self.prompt_ids_addr)
        _mb_set_arg_int(self.descriptors_prefill, d, 4, self.d_model)
        _mb_set_arg_int(self.descriptors_prefill, d, 5, 0)  # m_rows, patched per call
        self.embed_d = d
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]

            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                PREFILL_MAX_TILE, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.ln1_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_prefill, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_prefill, d, 5, 0)  # m_rows, patched per call
            self.rmsnorm_d.append(d)
            d += 1

            var n_tile_rows_qkv_max = _ceil_div(PREFILL_MAX_TILE, _GEMM_BM)
            var n_tile_cols_qkv = _ceil_div(n_qkv, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN],
                n_tile_rows_qkv_max * n_tile_cols_qkv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 3, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_prefill, d, 6, n_qkv)
            self.gemm_assign_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_ROPEWRT],
                (self.h_q + self.h_kv) * PREFILL_MAX_TILE, self.d_head, 14,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.cv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 3, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 4, lw.qn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 5, lw.kn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 6, self.cos_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 7, self.sin_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 8, 0)  # pos_base, patched per call
            _mb_set_arg_int(self.descriptors_prefill, d, 9, self.h_q)
            _mb_set_arg_int(self.descriptors_prefill, d, 10, self.h_kv)
            _mb_set_arg_int(self.descriptors_prefill, d, 11, self.d_head)
            _mb_set_arg_f32(self.descriptors_prefill, d, 12, self.eps)
            _mb_set_arg_int(self.descriptors_prefill, d, 13, 0)  # m_rows, patched per call
            self.ropewrt_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_ATTN],
                self.h_q * PREFILL_MAX_TILE, self.d_head, 10,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 3, lw.cv_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 4, 0)  # pos_base, patched per call
            _mb_set_arg_int(self.descriptors_prefill, d, 5, self.h_q)
            _mb_set_arg_int(self.descriptors_prefill, d, 6, self.h_kv)
            _mb_set_arg_int(self.descriptors_prefill, d, 7, self.d_head)
            _mb_set_arg_f32(self.descriptors_prefill, d, 8, self.scale)
            _mb_set_arg_int(self.descriptors_prefill, d, 9, 0)  # m_rows, patched per call
            self.attn_d.append(d)
            d += 1

            var n_tile_rows_gemv_max = _ceil_div(PREFILL_MAX_TILE, _GEMM_BM)
            var n_tile_cols_gemv = _ceil_div(self.d_model, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_tile_rows_gemv_max * n_tile_cols_gemv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill, d, 5, n_q)
            _mb_set_arg_int(self.descriptors_prefill, d, 6, self.d_model)
            self.gemv_o_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                PREFILL_MAX_TILE, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.ln2_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_prefill, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_prefill, d, 5, 0)  # m_rows, patched per call
            self.rmsnorm2_d.append(d)
            d += 1

            var n_tile_cols_ff = _ceil_div(self.d_ff, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU],
                n_tile_rows_gemv_max * n_tile_cols_ff, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 3, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_prefill, d, 6, self.d_ff)
            self.swiglu_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_tile_rows_gemv_max * n_tile_cols_gemv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors_prefill, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill, d, 5, self.d_ff)
            _mb_set_arg_int(self.descriptors_prefill, d, 6, self.d_model)
            self.gemv_down_d.append(d)
            d += 1

        # ── final-norm+lm_head+argmax: the UNMODIFIED single-row kernel, reused unchanged -- see
        # module docstring for why the `x` pointer argument (index 2) is what `_apply_m_rows`
        # patches to point at row `m_rows - 1`, rather than this kernel needing a batched twin.
        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors_prefill, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 2, self.hidden_addr)  # patched per call
        _mb_set_arg_ptr(self.descriptors_prefill, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 4, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 5, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_prefill, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors_prefill, d, 7, self.vocab)
        _mb_set_arg_f32(self.descriptors_prefill, d, 8, self.eps)
        _mb_set_arg_int(self.descriptors_prefill, d, 9, n_iters)
        self.lmhead_d = d
        d += 1

        _mb_set_header(self.descriptors_prefill, d, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 0, self.out_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 1, self.out_idx_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 2, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill, d, 3, self.blk_idx_addr)
        _mb_set_arg_int(self.descriptors_prefill, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors_prefill:
            raise Error(
                "metaldispatch: built " + String(d) + " prefill descriptors but the budget says "
                + String(self.n_descriptors_prefill) + " -- the design and the code disagree, status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )

    def _build_descriptors_prefill_af(mut self, n_qkv: Int) raises:
        """Attention Compiler Plan v1.0, Phase 2C (+ the decode-after-AF-prefill gap fix): builds
        `self.descriptors_prefill_af` -- a COMPLETE SEPARATE table, structurally IDENTICAL to
        `_build_descriptors_prefill`'s own plan (one embed dispatch, the unmodified lmhead+argmax
        pair) except NINE per-layer dispatches instead of eight: the native-KV-producer
        (`attention_forge.native_kv_producer._native_kv_producer_kernel`, discovered as `self.
        af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER]`) replaces `ropewrt`; Candidate A's grouped-head
        fused-FlashAttention (`attention_forge.grouped_fa_q8_k32_h2_sg8._attn_grouped_fa_kernel`,
        `self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN]`) replaces `attn`; and ONE genuinely NEW
        dispatch (`self.kvprod_mirror_af_d`) immediately follows the native-KV-producer, re-running
        the byte-unmodified `_pf_ropewrt_kernel` a SECOND time to ALSO write `lw.ck_addr`/`cv_addr`
        (the natural F32 cache `step()` reads) -- a double-write, not a replacement, closing the gap
        PR #599 shipped with (see `self.kvprod_mirror_af_d`'s own field docstring for why this is a
        separate dispatch of an EXISTING kernel rather than extending `_native_kv_producer_kernel`'s
        own signature: that dispatch is already at the `metaldispatch.ffi.MB_MAX_ARGS` ceiling).
        Every OTHER dispatch below points at the EXACT SAME underlying buffers `_build_descriptors_
        prefill`'s own equivalent slot uses (`self.hidden_addr`/`self.xn_addr`/`self.qkv_addr`/`self.
        act_addr`/`self.attn_out_addr`/etc.) -- safe only because `prefill_batch` submits exactly ONE
        of the two tables per call, never both. Only ever called from `__init__`, and only once both
        `self.af_pipeline_idx` entries were discovered -- see the call site's own guard."""
        var n_q = self.h_q * self.d_head
        var d = 0

        _mb_set_header(
            self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            _ceil_div(self.d_model, _TG) * PREFILL_MAX_TILE, _TG, 6,
        )
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, self.embed_scale_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, self.prompt_ids_addr)
        _mb_set_arg_int(self.descriptors_prefill_af, d, 4, self.d_model)
        _mb_set_arg_int(self.descriptors_prefill_af, d, 5, 0)  # m_rows, patched per call
        self.embed_af_d = d
        d += 1

        var n_units_kvprod_max = (self.h_q + self.h_kv) * PREFILL_MAX_TILE
        var n_kv_tiles_max = _ceil_div(PREFILL_MAX_TILE, _AF_KEY_BLOCK_SIZE)
        var n_q_blocks_max = _ceil_div(PREFILL_MAX_TILE, 8)
        var n_units_attn_af_max = n_q_blocks_max * (self.h_q // 2)

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            var ck_native_addr = self.af_ck_native_addr[layer]
            var cv_native_addr = self.af_cv_native_addr[layer]

            _mb_set_header(
                self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                PREFILL_MAX_TILE, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.ln1_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_prefill_af, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 5, 0)  # m_rows, patched per call
            self.rmsnorm_af_d.append(d)
            d += 1

            var n_tile_rows_qkv_max = _ceil_div(PREFILL_MAX_TILE, _GEMM_BM)
            var n_tile_cols_qkv = _ceil_div(n_qkv, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN],
                n_tile_rows_qkv_max * n_tile_cols_qkv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 6, n_qkv)
            self.gemm_assign_af_d.append(d)
            d += 1

            # ── native-KV-producer, replaces `ropewrt` -- V2 CONDITIONAL (beat-llama.cpp
            # campaign Phase C): the block-cooperative pair (`kvprod_v2`) when its blob was
            # linked, the original naive 16-arg dispatch otherwise (byte-unmodified).
            if self.kvprod_v2_built:
                _mb_set_header(
                    self.descriptors_prefill_af, d, self.kvprod_blk_pipeline_idx,
                    n_kv_tiles_max * self.h_kv, 256, 14,
                )
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, ck_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, cv_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, self.qkv_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, lw.kn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 4, self.cos_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 5, self.sin_addr)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 6, 0)  # pos_base, patched per call
                _mb_set_arg_int(self.descriptors_prefill_af, d, 7, self.h_q)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 8, self.h_kv)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 9, self.d_head)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 10, _AF_KEY_BLOCK_SIZE)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 11, self.af_n_blocks)
                _mb_set_arg_f32(self.descriptors_prefill_af, d, 12, self.eps)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 13, 0)  # m_rows, patched per call
                self.kvprod_af_d.append(d)
                d += 1
                _mb_set_header(
                    self.descriptors_prefill_af, d, self.kvprod_qvec_pipeline_idx,
                    PREFILL_MAX_TILE * self.h_q, 32, 11,
                )
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.q_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.qkv_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.qn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, self.cos_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 4, self.sin_addr)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 5, 0)  # pos_base, patched per call
                _mb_set_arg_int(self.descriptors_prefill_af, d, 6, self.h_q)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 7, self.h_kv)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 8, self.d_head)
                _mb_set_arg_f32(self.descriptors_prefill_af, d, 9, self.eps)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 10, 0)  # m_rows, patched per call
                self.kvprod_q_af_d.append(d)
                d += 1
            else:
                _mb_set_header(
                    self.descriptors_prefill_af, d, self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER],
                    n_units_kvprod_max, self.d_head, 16,
                )
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.q_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, ck_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, cv_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, self.qkv_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 4, lw.qn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 5, lw.kn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 6, self.cos_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af, d, 7, self.sin_addr)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 8, 0)  # pos_base, patched per call
                _mb_set_arg_int(self.descriptors_prefill_af, d, 9, self.h_q)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 10, self.h_kv)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 11, self.d_head)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 12, _AF_KEY_BLOCK_SIZE)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 13, self.af_n_blocks)
                _mb_set_arg_f32(self.descriptors_prefill_af, d, 14, self.eps)
                _mb_set_arg_int(self.descriptors_prefill_af, d, 15, 0)  # m_rows, patched per call
                self.kvprod_af_d.append(d)
                d += 1

            # ── NEW role (gap fix, additive): natural-cache DOUBLE-WRITE. Re-dispatches the
            # byte-unmodified, already-linked (pinned-toolchain, always compiled) `_pf_ropewrt_
            # kernel` -- the EXACT same pipeline `_build_descriptors_prefill`'s own `ropewrt` role
            # uses -- a SECOND time, so `lw.ck_addr`/`lw.cv_addr` (the natural F32 KV cache `step()`
            # reads) end up populated exactly as they would after an OFF-path `prefill_batch()` call,
            # even though this table's own attention dispatch (below) never reads them -- it reads
            # `q_native_addr`/`ck_native_addr`/`cv_native_addr` instead. Also harmlessly re-writes
            # `self.q_rot_addr` (unread anywhere in THIS table; only the OFF table's own `attn` role
            # reads it, and the two tables are never submitted in the same call) -- accepted, not
            # worked around, because `_pf_ropewrt_kernel`'s own grid computes Q and K/V lanes in ONE
            # dispatch and cannot be told to skip the Q lanes. 14 args, IDENTICAL order to
            # `_build_descriptors_prefill`'s own `ropewrt` dispatch -- see that dispatch for the
            # cross-reference. This is a genuinely EXTRA per-layer dispatch (not a replacement of
            # anything), which is why `self.n_descriptors_prefill_af` is `1 + n_layers*9 + 2`, not
            # `...*8...` like the OFF table.
            _mb_set_header(
                self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_ROPEWRT],
                n_units_kvprod_max, self.d_head, 14,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.cv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 4, lw.qn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 5, lw.kn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 6, self.cos_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 7, self.sin_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 8, 0)  # pos_base, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af, d, 9, self.h_q)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 10, self.h_kv)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 11, self.d_head)
            _mb_set_arg_f32(self.descriptors_prefill_af, d, 12, self.eps)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 13, 0)  # m_rows, patched per call
            self.kvprod_mirror_af_d.append(d)
            d += 1

            # ── NEW role: Candidate A's grouped-head fused-FlashAttention, replaces `attn`. 12
            # args -- see `grouped_fa_q8_k32_h2_sg8.mojo`'s own `_attn_grouped_fa_kernel` signature.
            # Output writes DIRECTLY into `self.attn_out_addr` -- the SAME buffer the OFF path's
            # `attn` role writes (byte-identical `[m_rows, h_q*d_head]` row-major F32 layout), so
            # the `gemv_o` dispatch right after this one needs no changes at all, AF table or not.
            _mb_set_header(
                self.descriptors_prefill_af, d, self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN],
                n_units_attn_af_max, 256, 12,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.lse_scratch_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, ck_native_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 4, cv_native_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 5, 0)  # n_tok_q = m_rows, patched
            _mb_set_arg_int(self.descriptors_prefill_af, d, 6, 0)  # n_tok_k = pos_base+m_rows, patched
            _mb_set_arg_int(self.descriptors_prefill_af, d, 7, self.h_q)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 8, self.h_kv)
            _mb_set_arg_f32(self.descriptors_prefill_af, d, 9, self.scale)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 10, 0)  # pos_base, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af, d, 11, self.af_n_blocks)
            self.attn_af_d.append(d)
            d += 1

            var n_tile_rows_gemv_max = _ceil_div(PREFILL_MAX_TILE, _GEMM_BM)
            var n_tile_cols_gemv = _ceil_div(self.d_model, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_tile_rows_gemv_max * n_tile_cols_gemv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af, d, 5, n_q)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 6, self.d_model)
            self.gemv_o_af_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                PREFILL_MAX_TILE, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.ln2_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_prefill_af, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 5, 0)  # m_rows, patched per call
            self.rmsnorm2_af_d.append(d)
            d += 1

            var n_tile_cols_ff = _ceil_div(self.d_ff, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU],
                n_tile_rows_gemv_max * n_tile_cols_ff, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 6, self.d_ff)
            self.swiglu_af_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill_af, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_tile_rows_gemv_max * n_tile_cols_gemv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af, d, 5, self.d_ff)
            _mb_set_arg_int(self.descriptors_prefill_af, d, 6, self.d_model)
            self.gemv_down_af_d.append(d)
            d += 1

        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors_prefill_af, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, self.hidden_addr)  # patched per call
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 4, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 5, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_prefill_af, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors_prefill_af, d, 7, self.vocab)
        _mb_set_arg_f32(self.descriptors_prefill_af, d, 8, self.eps)
        _mb_set_arg_int(self.descriptors_prefill_af, d, 9, n_iters)
        self.lmhead_af_d = d
        d += 1

        _mb_set_header(self.descriptors_prefill_af, d, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 0, self.out_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 1, self.out_idx_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 2, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af, d, 3, self.blk_idx_addr)
        _mb_set_arg_int(self.descriptors_prefill_af, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors_prefill_af:
            raise Error(
                "metaldispatch: built " + String(d) + " AF prefill descriptors but the budget says "
                + String(self.n_descriptors_prefill_af) + " -- the design and the code disagree, status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )

    def _build_descriptors_prefill_af_nomirror(mut self, n_qkv: Int) raises:
        """Project Redline reopening (2026-08-08): copy-and-extend of `_build_descriptors_prefill_
        af` immediately above, minus its `self.kvprod_mirror_af_d` dispatch -- see `self.
        descriptors_prefill_af_nomirror`'s own field docstring for the full account of what this
        removes and why. Every OTHER dispatch below is otherwise IDENTICAL (same pipelines, same
        buffers, same arg order) to that method's own equivalent role -- restated in full (not
        shared via a helper) per this file's own established copy-and-extend precedent for a new
        descriptor table (see module docstring's "AllSimd[n] -> [n+1]" reference)."""
        var n_q = self.h_q * self.d_head
        var d = 0

        _mb_set_header(
            self.descriptors_prefill_af_nomirror, d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            _ceil_div(self.d_model, _TG) * PREFILL_MAX_TILE, _TG, 6,
        )
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, self.embed_scale_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, self.prompt_ids_addr)
        _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 4, self.d_model)
        _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, 0)  # m_rows, patched per call
        self.embed_af2_d = d
        d += 1

        var n_units_kvprod_max = (self.h_q + self.h_kv) * PREFILL_MAX_TILE
        var n_kv_tiles_max = _ceil_div(PREFILL_MAX_TILE, _AF_KEY_BLOCK_SIZE)
        var n_q_blocks_max = _ceil_div(PREFILL_MAX_TILE, 8)
        var n_units_attn_af_max = n_q_blocks_max * (self.h_q // 2)

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            var ck_native_addr = self.af_ck_native_addr[layer]
            var cv_native_addr = self.af_cv_native_addr[layer]

            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                PREFILL_MAX_TILE, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, lw.ln1_addr)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_prefill_af_nomirror, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, 0)  # m_rows, patched per call
            self.rmsnorm_af2_d.append(d)
            d += 1

            var n_tile_rows_qkv_max = _ceil_div(PREFILL_MAX_TILE, _GEMM_BM)
            var n_tile_cols_qkv = _ceil_div(n_qkv, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN],
                n_tile_rows_qkv_max * n_tile_cols_qkv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, n_qkv)
            self.gemm_assign_af2_d.append(d)
            d += 1

            # ── native-KV-producer, replaces `ropewrt` -- V2 CONDITIONAL, IDENTICAL to
            # `_build_descriptors_prefill_af`'s own equivalent dispatch above. NO mirror dispatch
            # follows this one -- that remains the ONE and ONLY structural difference.
            if self.kvprod_v2_built:
                _mb_set_header(
                    self.descriptors_prefill_af_nomirror, d, self.kvprod_blk_pipeline_idx,
                    n_kv_tiles_max * self.h_kv, 256, 14,
                )
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, ck_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, cv_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, self.qkv_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, lw.kn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 4, self.cos_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 5, self.sin_addr)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, 0)  # pos_base, patched per call
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 7, self.h_q)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 8, self.h_kv)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 9, self.d_head)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 10, _AF_KEY_BLOCK_SIZE)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 11, self.af_n_blocks)
                _mb_set_arg_f32(self.descriptors_prefill_af_nomirror, d, 12, self.eps)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 13, 0)  # m_rows, patched per call
                self.kvprod_af2_d.append(d)
                d += 1
                _mb_set_header(
                    self.descriptors_prefill_af_nomirror, d, self.kvprod_qvec_pipeline_idx,
                    PREFILL_MAX_TILE * self.h_q, 32, 11,
                )
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.q_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.qkv_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, lw.qn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, self.cos_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 4, self.sin_addr)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, 0)  # pos_base, patched per call
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, self.h_q)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 7, self.h_kv)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 8, self.d_head)
                _mb_set_arg_f32(self.descriptors_prefill_af_nomirror, d, 9, self.eps)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 10, 0)  # m_rows, patched per call
                self.kvprod_q_af2_d.append(d)
                d += 1
            else:
                _mb_set_header(
                    self.descriptors_prefill_af_nomirror, d, self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER],
                    n_units_kvprod_max, self.d_head, 16,
                )
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.q_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, ck_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, cv_native_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, self.qkv_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 4, lw.qn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 5, lw.kn_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 6, self.cos_addr)
                _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 7, self.sin_addr)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 8, 0)  # pos_base, patched per call
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 9, self.h_q)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 10, self.h_kv)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 11, self.d_head)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 12, _AF_KEY_BLOCK_SIZE)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 13, self.af_n_blocks)
                _mb_set_arg_f32(self.descriptors_prefill_af_nomirror, d, 14, self.eps)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 15, 0)  # m_rows, patched per call
                self.kvprod_af2_d.append(d)
                d += 1

            # ── Candidate A's grouped-head fused-FlashAttention, replaces `attn` -- IDENTICAL to
            # `_build_descriptors_prefill_af`'s own equivalent dispatch.
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d, self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN],
                n_units_attn_af_max, 256, 12,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.lse_scratch_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, ck_native_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 4, cv_native_addr)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, 0)  # n_tok_q = m_rows, patched
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, 0)  # n_tok_k = pos_base+m_rows, patched
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 7, self.h_q)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 8, self.h_kv)
            _mb_set_arg_f32(self.descriptors_prefill_af_nomirror, d, 9, self.scale)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 10, 0)  # pos_base, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 11, self.af_n_blocks)
            self.attn_af2_d.append(d)
            d += 1

            var n_tile_rows_gemv_max = _ceil_div(PREFILL_MAX_TILE, _GEMM_BM)
            var n_tile_cols_gemv = _ceil_div(self.d_model, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_tile_rows_gemv_max * n_tile_cols_gemv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, n_q)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, self.d_model)
            self.gemv_o_af2_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                PREFILL_MAX_TILE, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, lw.ln2_addr)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_prefill_af_nomirror, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, 0)  # m_rows, patched per call
            self.rmsnorm2_af2_d.append(d)
            d += 1

            var n_tile_cols_ff = _ceil_div(self.d_ff, _GEMM_BN)
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d, self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU],
                n_tile_rows_gemv_max * n_tile_cols_ff, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, self.d_ff)
            self.swiglu_af2_d.append(d)
            d += 1

            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_tile_rows_gemv_max * n_tile_cols_gemv, _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 4, 0)  # m_rows, patched per call
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 5, self.d_ff)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, self.d_model)
            self.gemv_down_af2_d.append(d)
            d += 1

        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors_prefill_af_nomirror, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, self.hidden_addr)  # patched per call
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 4, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 5, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 7, self.vocab)
        _mb_set_arg_f32(self.descriptors_prefill_af_nomirror, d, 8, self.eps)
        _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 9, n_iters)
        self.lmhead_af2_d = d
        d += 1

        _mb_set_header(self.descriptors_prefill_af_nomirror, d, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 0, self.out_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 1, self.out_idx_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 2, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, d, 3, self.blk_idx_addr)
        _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors_prefill_af_nomirror:
            raise Error(
                "metaldispatch: built " + String(d) + " AF-nomirror prefill descriptors but the budget says "
                + String(self.n_descriptors_prefill_af_nomirror) + " -- the design and the code disagree, status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )

    def _apply_m_rows_af(mut self, m_rows: Int, pos_base: Int) raises:
        """AF-table twin of `_apply_m_rows` -- narrows every M-scaled descriptor in `self.
        descriptors_prefill_af` to `m_rows`'s real grid width and patches every `m_rows`/`pos_base`
        scalar argument, restated for the SEPARATE AF table (see that table's own field docstring
        for why it is separate). Deliberately mirrors `_apply_m_rows`'s own GEMM-tiling policy choice
        (`use_mma`/`use_narrow`) byte-for-byte EXCEPT for the additive vecload4 substitution below --
        so the ONLY variable this table's own existence isolates, absent an explicit `PF_GEMM_
        VECLOAD4_ALL_ROLES` request, is the attention-dispatch change itself -- the Attention Compiler
        Plan v1.0's own "never combine multiple ablations into one measurement" discipline (stop rule
        5). Only ever called from `prefill_batch`, and only when `self.plan.attention == PF_ATTN_
        GROUPED_FA_WITH_MIRROR` -- see that method's own guard (this table's own construction already
        required the two AF blobs to be linked, so no additional availability check is needed here).

        Project Redline reopening (2026-08-08), round 7 -- WIRING GAP CLOSED: this method used to
        never consult `self.plan.gemm` at all (`PF_ATTN_GROUPED_FA_NO_MIRROR`'s own docstring in
        `metaldispatch.session_prefill_policy` used to assert this table was, "by design," one of the
        two the vecload4/BM64 substitutions had no wiring into) -- which meant `attention=PF_ATTN_
        GROUPED_FA_WITH_MIRROR` requested ALONGSIDE `gemm=PF_GEMM_VECLOAD4_ALL_ROLES` resolved to a
        genuinely valid `ResolvedSessionExecutionPlan` (both fields resolve independently in
        `resolve_prefill_execution_plan` -- there is no cross-field validation that would reject it),
        yet silently dispatched the ORIGINAL GEMM kernels for every role, discarding the caller's own
        explicit `gemm` request with no error, no fallback telemetry, nothing. That combination had
        simply never been measured before, because nothing wired it up to have a real effect. Fixed
        additively, by reusing (not duplicating) `_apply_m_rows_af_nomirror`'s own `use_vecload4_qkv`/
        `use_vecload4_accum`/`use_vecload4_swiglu` per-role gating exactly -- BM64 is deliberately NOT
        added here: `PF_GEMM_BM64`'s own docstring's design choice (qkv_proj-only, paired historically
        with no-mirror) is unaffected and unchanged by this fix, which is scoped to the one
        combination this round's own task named."""
        # ── Phase 3 (2026-08-08), hybrid per-role Metal GEMM backend: `self.plan.gemm == PF_GEMM_
        # MSL_PARITY_ALL_ROLES` now has a real effect in this table too -- each of the four GEMM
        # roles whose MSL parity pipeline was discovered dispatches its hand-written metallib
        # (pipeline-index + grid/threads + arg-2 weight-pointer patch on the SAME descriptor slot;
        # the slot's arg layout was designed for exactly this repointing -- see the `msl_parity_*_
        # mul_mm.metal` headers' ARG BINDING item). Roles whose MSL pipeline is missing fall back
        # inside the tier (vecload4 if linked, else original MMA); a blobs-absent binary never
        # resolves this tier at all (see `resolve_prefill_execution_plan`'s own graceful degrade).
        var n_qkv = self.n_qkv
        var n_units_embed = _ceil_div(self.d_model, _TG)
        var n_tile_cols_qkv = _ceil_div(n_qkv, _GEMM_BN)
        var n_tile_cols_gemv = _ceil_div(self.d_model, _GEMM_BN)
        var n_tile_cols_ff = _ceil_div(self.d_ff, _GEMM_BN)
        var n_units_kvprod = self.h_q + self.h_kv
        var n_q_blocks = _ceil_div(m_rows, 8)
        var n_units_attn_af = n_q_blocks * (self.h_q // 2)

        var use_mma = True
        var use_narrow = residentk_prefill_gemm_use_narrow_tile(m_rows)
        var gemm_bm = 32 if use_mma else (_GEMM_BM_NARROW if use_narrow else _GEMM_BM)
        var gemm_nthreads = 256 if use_mma else (_GEMM_NTHREADS_NARROW if use_narrow else _GEMM_NTHREADS)
        var n_tile_rows_qkv = _ceil_div(m_rows, gemm_bm)
        # ── Project Redline reopening (2026-08-08), round 7: same all-4-roles vecload4 substitution
        # `_apply_m_rows_af_nomirror` already applies, now ALSO wired into the with-mirror table --
        # see this method's own docstring above. Reuses the EXACT SAME `_BM=32/_BN=32/_BK=16` tile
        # constants/grid formula as the original MMA kernels, so no new tile-row-count variable is
        # needed (unlike BM64, which this method still does not wire in -- see docstring).
        # ── Phase 3 (2026-08-08), hybrid per-role Metal GEMM backend: the OPT-IN `PF_GEMM_MSL_
        # PARITY_ALL_ROLES` tier, wired additively ON TOP of round 7's vecload4 gating. Per-role
        # selection: a role runs its MSL parity metallib iff the tier resolved AND that role's own
        # pipeline was discovered; a role whose MSL pipeline is missing falls back INSIDE the tier
        # to the vecload4 twin if linked, else the original MMA kernel (the same per-role graceful
        # degrade the vecload4 tier itself already has). `self.plan.gemm` is a single resolved
        # value, so `use_msl_*` and the plain-vecload4 branch below can never both fire for one
        # role; the `or` in `use_vecload4_*` is the tier-internal fallback, not a second request.
        var msl_requested = self.plan.gemm == PF_GEMM_MSL_PARITY_ALL_ROLES
        var use_msl_qkv = msl_requested and self.msl_parity_qkv_proj_pipeline_idx >= 0
        var use_msl_accum = msl_requested and self.msl_parity_gemm_accum_pipeline_idx >= 0
        var use_msl_swiglu = msl_requested and self.msl_parity_swiglu_pipeline_idx >= 0
        var use_vecload4_qkv = (
            self.plan.gemm == PF_GEMM_VECLOAD4_ALL_ROLES
            or (msl_requested and not use_msl_qkv)
        ) and self.qkv_proj_vecload4_pipeline_idx >= 0
        var use_vecload4_accum = (
            self.plan.gemm == PF_GEMM_VECLOAD4_ALL_ROLES
            or (msl_requested and not use_msl_accum)
        ) and self.gemm_accum_vecload4_pipeline_idx >= 0
        var use_vecload4_swiglu = (
            self.plan.gemm == PF_GEMM_VECLOAD4_ALL_ROLES
            or (msl_requested and not use_msl_swiglu)
        ) and self.swiglu_vecload4_pipeline_idx >= 0
        var pf_assign = (
            self.msl_parity_qkv_proj_pipeline_idx if use_msl_qkv
            else self.qkv_proj_vecload4_pipeline_idx if use_vecload4_qkv
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN]
        )
        var pf_accum = (
            self.msl_parity_gemm_accum_pipeline_idx if use_msl_accum
            else self.gemm_accum_vecload4_pipeline_idx if use_vecload4_accum
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM]
        )
        var pf_swiglu = (
            self.msl_parity_swiglu_pipeline_idx if use_msl_swiglu
            else self.swiglu_vecload4_pipeline_idx if use_vecload4_swiglu
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU]
        )
        # ── Phase 3: the MSL parity kernels' OWN grid/threads (their headers' 1D linearization of
        # llama.cpp's 2D ownership: NR0=64 output-feature columns per threadgroup on the N axis,
        # NR1=32 rows per threadgroup on the M axis, 128 threads = 4 simdgroups -- see the kernels'
        # own `n_tiles_m`/`r0`/`r1` math). Distinct per role by N width: qkv n_qkv, o/down d_model,
        # swiglu d_ff. Non-MSL roles keep `gemm_nthreads`/the Mojo tile grid, byte-for-byte.
        var msl_n_tile_rows = _ceil_div(m_rows, 32)
        var grid_qkv = msl_n_tile_rows * _ceil_div(n_qkv, 64) if use_msl_qkv else n_tile_rows_qkv * n_tile_cols_qkv
        var grid_gemv = msl_n_tile_rows * _ceil_div(self.d_model, 64) if use_msl_accum else n_tile_rows_qkv * n_tile_cols_gemv
        var grid_ff = msl_n_tile_rows * _ceil_div(self.d_ff, 64) if use_msl_swiglu else n_tile_rows_qkv * n_tile_cols_ff
        var threads_qkv = 128 if use_msl_qkv else gemm_nthreads
        var threads_accum = 128 if use_msl_accum else gemm_nthreads
        var threads_swiglu = 128 if use_msl_swiglu else gemm_nthreads

        _mb_set_header(
            self.descriptors_prefill_af, self.embed_af_d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            n_units_embed * m_rows, _TG, 6,
        )
        _mb_set_arg_int(self.descriptors_prefill_af, self.embed_af_d, 5, m_rows)

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            var d_norm = self.rmsnorm_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_norm, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                m_rows, _TG, 6,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_norm, 5, m_rows)

            var d_gemm = self.gemm_assign_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_gemm, pf_assign,
                grid_qkv, threads_qkv, 7,
            )
            # ── Phase 3: arg 2 (weight pointer) tracks the selected kernel family -- the MSL
            # parity kernels read the ALREADY-DEQUANTIZED Float16 twin, the Int8/vecload4 kernels
            # the quantized original. Unconditionally re-set EVERY call so a plan re-resolution
            # between calls (this file's own tests flip plans on one instance) can never leave a
            # stale pointer from the other family bound. Arg 3 (wscale) stays bound to the same
            # scale buffer either way -- the MSL kernels take it and ignore it (their headers'
            # item 1), zero argument-area restructuring, exactly as designed.
            _mb_set_arg_ptr(
                self.descriptors_prefill_af, d_gemm, 2,
                self.msl_w_qkv_f16_addr[layer] if use_msl_qkv else lw.w_qkv_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_gemm, 4, m_rows)

            var d_kv = self.kvprod_af_d[layer]
            if self.kvprod_v2_built:
                # V2 pair: blk (KV) + qvec (Q) -- same per-call narrowing discipline, grids
                # recomputed for THIS call's m_rows (tiles = ceil(m_rows/kbs)).
                var n_tiles_call = _ceil_div(m_rows, _AF_KEY_BLOCK_SIZE)
                _mb_set_header(
                    self.descriptors_prefill_af, d_kv, self.kvprod_blk_pipeline_idx,
                    n_tiles_call * self.h_kv, 256, 14,
                )
                _mb_set_arg_int(self.descriptors_prefill_af, d_kv, 6, pos_base)
                _mb_set_arg_int(self.descriptors_prefill_af, d_kv, 13, m_rows)
                var d_qv = self.kvprod_q_af_d[layer]
                _mb_set_header(
                    self.descriptors_prefill_af, d_qv, self.kvprod_qvec_pipeline_idx,
                    self.h_q * m_rows, 32, 11,
                )
                _mb_set_arg_int(self.descriptors_prefill_af, d_qv, 5, pos_base)
                _mb_set_arg_int(self.descriptors_prefill_af, d_qv, 10, m_rows)
            else:
                _mb_set_header(
                    self.descriptors_prefill_af, d_kv, self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER],
                    n_units_kvprod * m_rows, self.d_head, 16,
                )
                _mb_set_arg_int(self.descriptors_prefill_af, d_kv, 8, pos_base)
                _mb_set_arg_int(self.descriptors_prefill_af, d_kv, 15, m_rows)

            # ── gap fix: natural-cache double-write, same `pos_base`/`m_rows` this call's own
            # native-KV-producer dispatch just got patched with, two lines above -- see `self.
            # kvprod_mirror_af_d`'s own field docstring.
            var d_kvm = self.kvprod_mirror_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_kvm, self.prefill_pipeline_idx[_PFROLE_ROPEWRT],
                n_units_kvprod * m_rows, self.d_head, 14,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_kvm, 8, pos_base)
            _mb_set_arg_int(self.descriptors_prefill_af, d_kvm, 13, m_rows)

            var d_attn = self.attn_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_attn, self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN],
                n_units_attn_af, 256, 12,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_attn, 5, m_rows)
            _mb_set_arg_int(self.descriptors_prefill_af, d_attn, 6, pos_base + m_rows)
            _mb_set_arg_int(self.descriptors_prefill_af, d_attn, 10, pos_base)

            var d_go = self.gemv_o_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_go, pf_accum,
                grid_gemv, threads_accum, 7,
            )
            _mb_set_arg_ptr(
                self.descriptors_prefill_af, d_go, 2,
                self.msl_w_o_f16_addr[layer] if use_msl_accum else lw.w_o_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_go, 4, m_rows)

            var d_norm2 = self.rmsnorm2_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_norm2, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                m_rows, _TG, 6,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_norm2, 5, m_rows)

            var d_sw = self.swiglu_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_sw, pf_swiglu,
                grid_ff, threads_swiglu, 7,
            )
            _mb_set_arg_ptr(
                self.descriptors_prefill_af, d_sw, 2,
                self.msl_w_gu_f16_addr[layer] if use_msl_swiglu else lw.w_gu_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_sw, 4, m_rows)

            var d_gd = self.gemv_down_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_gd, pf_accum,
                grid_gemv, threads_accum, 7,
            )
            _mb_set_arg_ptr(
                self.descriptors_prefill_af, d_gd, 2,
                self.msl_w_down_f16_addr[layer] if use_msl_accum else lw.w_down_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_gd, 4, m_rows)

        var last_row_addr = self.hidden_addr + UInt64((m_rows - 1) * self.d_model * 4)
        _mb_set_arg_ptr(self.descriptors_prefill_af, self.lmhead_af_d, 2, last_row_addr)

    def _apply_m_rows_af_nomirror(mut self, m_rows: Int, pos_base: Int) raises:
        """Project Redline reopening (2026-08-08): copy-and-extend of `_apply_m_rows_af` immediately
        above, minus the two lines that patch `self.kvprod_mirror_af_d` -- narrows/patches `self.
        descriptors_prefill_af_nomirror` instead of `self.descriptors_prefill_af`, using the `af2`
        field family. Two OPTIONAL, off-by-default, per-role GEMM-kernel substitutions live here too
        (`self.plan.gemm == PF_GEMM_BM64` / `PF_GEMM_VECLOAD4_ALL_ROLES`, each STILL additionally
        gated on its own kernel's own pipeline-discovery field being `>= 0` -- the fine-grained,
        per-role fallback `resolve_prefill_execution_plan` does NOT replace, see `PF_GEMM_VECLOAD4_
        ALL_ROLES`'s own docstring in `metaldispatch.session_prefill_policy`) -- every other line is
        otherwise identical to `_apply_m_rows_af`. Only ever called when `self.plan.attention ==
        PF_ATTN_GROUPED_FA_NO_MIRROR` (`prefill_batch`'s own guard). `self.plan.gemm == PF_GEMM_BM64`
        is never consulted by `_apply_m_rows_af`/`_apply_m_rows`, so it has no effect on either of
        those two tables regardless of its own value -- BM64 remains paired only with this
        (no-mirror) table, by design (see `PF_GEMM_BM64`'s own docstring). Round 7 (2026-08-08): `self.
        plan.gemm == PF_GEMM_VECLOAD4_ALL_ROLES` is DIFFERENT -- `_apply_m_rows_af` now consults it too
        (a real wiring gap closed, not a design choice -- see that method's own docstring for the full
        account), so vecload4 has an effect under `PF_ATTN_GROUPED_FA_WITH_MIRROR` as well as under
        this table's own `PF_ATTN_GROUPED_FA_NO_MIRROR`; `_apply_m_rows` (the OFF-path table) remains
        the only one neither substitution ever reaches.

        Calls `self._require_resolved_plan()` first, independently of `prefill_batch`'s own identical
        check -- see that method's own docstring for why this is defense-in-depth, not the primary
        guarantee, and why it is placed here too rather than relying solely on being reached only
        through `prefill_batch`."""
        self._require_resolved_plan()
        var n_qkv = self.n_qkv
        var n_units_embed = _ceil_div(self.d_model, _TG)
        var n_tile_cols_qkv = _ceil_div(n_qkv, _GEMM_BN)
        var n_tile_cols_gemv = _ceil_div(self.d_model, _GEMM_BN)
        var n_tile_cols_ff = _ceil_div(self.d_ff, _GEMM_BN)
        var n_units_kvprod = self.h_q + self.h_kv
        var n_q_blocks = _ceil_div(m_rows, 8)
        var n_units_attn_af = n_q_blocks * (self.h_q // 2)

        var use_mma = True
        var use_narrow = residentk_prefill_gemm_use_narrow_tile(m_rows)
        var gemm_bm = 32 if use_mma else (_GEMM_BM_NARROW if use_narrow else _GEMM_BM)
        var gemm_nthreads = 256 if use_mma else (_GEMM_NTHREADS_NARROW if use_narrow else _GEMM_NTHREADS)
        var n_tile_rows_qkv = _ceil_div(m_rows, gemm_bm)
        # ── Project Redline reopening (2026-08-08), step 2: all-4-roles vecload4 substitution.
        # Reuses the EXACT SAME `_BM=32/_BN=32/_BK=16` tile constants/grid formula as the original MMA
        # kernels (see `PF_GEMM_VECLOAD4_ALL_ROLES`'s own docstring) -- unlike BM64 below, no new
        # tile-row-count variable is needed for any of the three roles this introduces. Each
        # substitution is gated on its OWN kernel's own pipeline-discovery field being `>= 0` --
        # graceful per-role degrade to the original kernel if that ONE blob wasn't linked, the same
        # discipline the Sector-1 promotion-decision fix (2026-08-08) established for BM64 just below.
        # ── Phase 3 (2026-08-08), hybrid per-role Metal GEMM backend: the OPT-IN `PF_GEMM_MSL_
        # PARITY_ALL_ROLES` tier joins the two substitutions above, SAME both-tables wiring `_apply_
        # m_rows_af` got in the same phase (see that method's own Phase 3 docstring note) -- same
        # per-role selection, same tier-internal fallback (MSL missing for a role -> vecload4 if
        # linked, else original MMA), same pipeline-index + grid/threads + arg-2 weight-pointer
        # patch on the shared descriptor slot.
        var msl_requested = self.plan.gemm == PF_GEMM_MSL_PARITY_ALL_ROLES
        var use_msl_qkv = msl_requested and self.msl_parity_qkv_proj_pipeline_idx >= 0
        var use_msl_accum = msl_requested and self.msl_parity_gemm_accum_pipeline_idx >= 0
        var use_msl_swiglu = msl_requested and self.msl_parity_swiglu_pipeline_idx >= 0
        var use_vecload4_qkv = (
            self.plan.gemm == PF_GEMM_VECLOAD4_ALL_ROLES
            or (msl_requested and not use_msl_qkv)
        ) and self.qkv_proj_vecload4_pipeline_idx >= 0
        var use_vecload4_accum = (
            self.plan.gemm == PF_GEMM_VECLOAD4_ALL_ROLES
            or (msl_requested and not use_msl_accum)
        ) and self.gemm_accum_vecload4_pipeline_idx >= 0
        var use_vecload4_swiglu = (
            self.plan.gemm == PF_GEMM_VECLOAD4_ALL_ROLES
            or (msl_requested and not use_msl_swiglu)
        ) and self.swiglu_vecload4_pipeline_idx >= 0
        # ── Project Redline reopening (2026-08-08), step 4: qkv_proj-role-ONLY BM64 substitution --
        # a SEPARATE tile-row count and pipeline selection, deliberately NOT reusing `n_tile_rows_
        # qkv`/`gemm_bm` above (those still drive `pf_accum`/`pf_swiglu` below, the o_proj/down_proj/
        # swiglu roles this same table dispatches, which stay `BM=32`, UNCHANGED by this flag -- see
        # `PF_GEMM_BM64`'s own docstring for why reusing a BM64 grid for THEIR dispatch would be a
        # real correctness bug, not merely a missed optimization). Sector-1 promotion-decision fix
        # (2026-08-08): gated on `self.qkv_proj_bm64_pipeline_idx >= 0` too -- a plan resolved to
        # `PF_GEMM_BM64` on a binary that never linked `mm8_bm64_blob.c` would already have been
        # degraded to `PF_GEMM_ORIGINAL` by `resolve_prefill_execution_plan` itself, so this `>= 0`
        # check is a second, redundant-by-construction belt-and-suspenders, not the primary guard (see
        # `prefill_batch`'s own docstring for the full account). `use_vecload4_qkv` can never be `True`
        # at the same time as `self.plan.gemm == PF_GEMM_BM64` -- `self.plan.gemm` is a SINGLE resolved
        # value, not two independent flags, so there is no "both requested" state left to break a tie
        # over; the `and self.plan.gemm != PF_GEMM_VECLOAD4_ALL_ROLES` clause below is therefore
        # already implied by the `elif`-shaped mutual exclusion, kept explicit anyway for readability.
        var use_bm64 = self.plan.gemm == PF_GEMM_BM64 and self.qkv_proj_bm64_pipeline_idx >= 0
        var n_tile_rows_qkv_gemm = _ceil_div(m_rows, 64) if use_bm64 else n_tile_rows_qkv
        var pf_assign = (
            self.msl_parity_qkv_proj_pipeline_idx if use_msl_qkv
            else self.qkv_proj_vecload4_pipeline_idx if use_vecload4_qkv
            else self.qkv_proj_bm64_pipeline_idx if use_bm64
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN]
        )
        var pf_accum = (
            self.msl_parity_gemm_accum_pipeline_idx if use_msl_accum
            else self.gemm_accum_vecload4_pipeline_idx if use_vecload4_accum
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM]
        )
        var pf_swiglu = (
            self.msl_parity_swiglu_pipeline_idx if use_msl_swiglu
            else self.swiglu_vecload4_pipeline_idx if use_vecload4_swiglu
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU]
        )
        # ── Phase 3: MSL grid/threads, same formulas `_apply_m_rows_af`'s own Phase 3 block uses
        # (NR0=64/NR1=32/128 threads) -- distinct per role by N width.
        var msl_n_tile_rows = _ceil_div(m_rows, 32)
        var grid_qkv = msl_n_tile_rows * _ceil_div(n_qkv, 64) if use_msl_qkv else n_tile_rows_qkv_gemm * n_tile_cols_qkv
        var grid_gemv = msl_n_tile_rows * _ceil_div(self.d_model, 64) if use_msl_accum else n_tile_rows_qkv * n_tile_cols_gemv
        var grid_ff = msl_n_tile_rows * _ceil_div(self.d_ff, 64) if use_msl_swiglu else n_tile_rows_qkv * n_tile_cols_ff
        var threads_qkv = 128 if use_msl_qkv else gemm_nthreads
        var threads_accum = 128 if use_msl_accum else gemm_nthreads
        var threads_swiglu = 128 if use_msl_swiglu else gemm_nthreads
        # ── Beat-llama.cpp campaign front 2, fourth strike (2026-08-09): split-K GPU-fill
        # substitution for the two narrow-N accum roles ONLY (o_proj K=n_q, down_proj K=d_ff).
        # The grid-fill bench measured these two roles' 128-threadgroup parity grids at 67-68% of
        # the 13.3 TFLOP/s MMA wall while wide-N roles run at 90-97% -- the 40-core GPU is
        # underfilled. `msl_splitk_accum.metal`'s split-K kernels (same 32x64 tile, K split S ways,
        # atomic-float-add epilogue into dst = "+=" for free) standalone-bench at 1.30x (o_proj,
        # S=8) / 1.33x (down_proj, S=12), correctness-gated at every M in {1,17,127,256,257,512}.
        # Each substitution is gated THREE ways, mirroring the per-role graceful-degrade discipline
        # every other optional kernel in this method uses: the MSL-parity accum tier must itself be
        # active (`use_msl_accum` -- a splitk kernel without its f16 weight twins makes no sense),
        # its own pipeline must have been discovered (blob linked), AND the role's K must divide
        # cleanly into 256-deep splits (S=8: K % 256 == 0; S=12: K % 384 == 0 -- split depth K/S
        # must be a multiple of the kernels' 32 K-step). Any miss degrades that ONE role to the
        # parity accum kernel, exactly as before this strike.
        var n_q = self.h_q * self.d_head
        var use_splitk_o = use_msl_accum and self.msl_splitk8_pipeline_idx >= 0 and n_q % 256 == 0
        var use_splitk_down = use_msl_accum and self.msl_splitk12_pipeline_idx >= 0 and self.d_ff % 384 == 0
        var pf_accum_o = self.msl_splitk8_pipeline_idx if use_splitk_o else pf_accum
        var pf_accum_down = self.msl_splitk12_pipeline_idx if use_splitk_down else pf_accum
        var grid_gemv_o = grid_gemv * 8 if use_splitk_o else grid_gemv
        var grid_gemv_down = grid_gemv * 12 if use_splitk_down else grid_gemv

        _mb_set_header(
            self.descriptors_prefill_af_nomirror, self.embed_af2_d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            n_units_embed * m_rows, _TG, 6,
        )
        _mb_set_arg_int(self.descriptors_prefill_af_nomirror, self.embed_af2_d, 5, m_rows)

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            var d_norm = self.rmsnorm_af2_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d_norm, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                m_rows, _TG, 6,
            )
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_norm, 5, m_rows)

            var d_gemm = self.gemm_assign_af2_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d_gemm, pf_assign,
                grid_qkv, threads_qkv, 7,
            )
            # Phase 3: arg 2 tracks the selected kernel family -- see `_apply_m_rows_af`'s own
            # identical Phase 3 comment for the full "re-set EVERY call" rationale.
            _mb_set_arg_ptr(
                self.descriptors_prefill_af_nomirror, d_gemm, 2,
                self.msl_w_qkv_f16_addr[layer] if use_msl_qkv else lw.w_qkv_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_gemm, 4, m_rows)

            var d_kv = self.kvprod_af2_d[layer]
            if self.kvprod_v2_built:
                # V2 pair: blk (KV) + qvec (Q) -- same per-call narrowing discipline, grids
                # recomputed for THIS call's m_rows (tiles = ceil(m_rows/kbs)).
                var n_tiles_call = _ceil_div(m_rows, _AF_KEY_BLOCK_SIZE)
                _mb_set_header(
                    self.descriptors_prefill_af_nomirror, d_kv, self.kvprod_blk_pipeline_idx,
                    n_tiles_call * self.h_kv, 256, 14,
                )
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_kv, 6, pos_base)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_kv, 13, m_rows)
                var d_qv = self.kvprod_q_af2_d[layer]
                _mb_set_header(
                    self.descriptors_prefill_af_nomirror, d_qv, self.kvprod_qvec_pipeline_idx,
                    self.h_q * m_rows, 32, 11,
                )
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_qv, 5, pos_base)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_qv, 10, m_rows)
            else:
                _mb_set_header(
                    self.descriptors_prefill_af_nomirror, d_kv, self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER],
                    n_units_kvprod * m_rows, self.d_head, 16,
                )
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_kv, 8, pos_base)
                _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_kv, 15, m_rows)

            # ── NO mirror dispatch here -- the one and only difference from `_apply_m_rows_af`.

            var d_attn = self.attn_af2_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d_attn, self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN],
                n_units_attn_af, 256, 12,
            )
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_attn, 5, m_rows)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_attn, 6, pos_base + m_rows)
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_attn, 10, pos_base)

            var d_go = self.gemv_o_af2_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d_go, pf_accum_o,
                grid_gemv_o, threads_accum, 7,
            )
            _mb_set_arg_ptr(
                self.descriptors_prefill_af_nomirror, d_go, 2,
                self.msl_w_o_f16_addr[layer] if use_msl_accum else lw.w_o_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_go, 4, m_rows)

            var d_norm2 = self.rmsnorm2_af2_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d_norm2, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                m_rows, _TG, 6,
            )
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_norm2, 5, m_rows)

            var d_sw = self.swiglu_af2_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d_sw, pf_swiglu,
                grid_ff, threads_swiglu, 7,
            )
            _mb_set_arg_ptr(
                self.descriptors_prefill_af_nomirror, d_sw, 2,
                self.msl_w_gu_f16_addr[layer] if use_msl_swiglu else lw.w_gu_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_sw, 4, m_rows)

            var d_gd = self.gemv_down_af2_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af_nomirror, d_gd, pf_accum_down,
                grid_gemv_down, threads_accum, 7,
            )
            _mb_set_arg_ptr(
                self.descriptors_prefill_af_nomirror, d_gd, 2,
                self.msl_w_down_f16_addr[layer] if use_msl_accum else lw.w_down_addr,
            )
            _mb_set_arg_int(self.descriptors_prefill_af_nomirror, d_gd, 4, m_rows)

        var last_row_addr = self.hidden_addr + UInt64((m_rows - 1) * self.d_model * 4)
        _mb_set_arg_ptr(self.descriptors_prefill_af_nomirror, self.lmhead_af2_d, 2, last_row_addr)

    def _apply_m_rows(mut self, m_rows: Int, pos_base: Int) raises:
        """Narrows every M-scaled descriptor in `self.descriptors_prefill` to `m_rows`'s real grid
        width and patches every `m_rows`/`pos_base` scalar argument -- see module docstring's
        "DISPATCH PLAN" section for why this always runs unconditionally, unlike `step()`'s own
        change-gated `_apply_n_splits`. `_mb_set_header` only ever rewrites a descriptor's 16-byte
        header, never its argument area, so re-supplying the SAME `pipeline_idx`/`threads_x` every
        call alongside the new `grid_x` is exactly `_apply_n_splits`'s own established pattern, not
        a new risk."""
        var n_qkv = self.n_qkv
        var n_units_embed = _ceil_div(self.d_model, _TG)
        var n_tile_cols_qkv = _ceil_div(n_qkv, _GEMM_BN)
        var n_units_rope = self.h_q + self.h_kv
        var n_units_attn = self.h_q
        var n_tile_cols_gemv = _ceil_div(self.d_model, _GEMM_BN)
        var n_tile_cols_ff = _ceil_div(self.d_ff, _GEMM_BN)

        # ── the tile-config decision this method makes for every GEMM-shaped role this call
        # dispatches: hardware-MMA (`_qkv_proj_gemm_mma8x8`/`_gemm_accum_mma8x8`/
        # `_swiglu_gemm_mma8x8`, real Apple `simdgroup_matrix` 8x8 instructions) is now
        # UNCONDITIONAL, not gated on `m_rows`/model-dimension alignment. Originally these kernels
        # required `m_rows % 32 == 0` and 32-aligned model dims (their inner `BM=32,BN=32` tile had
        # no partial-tile padding). That padding was added -- the final store now checks each
        # lane's own `(row,col)` against `m_rows`/`n` individually before writing, same discipline
        # the scalar oracle's own store already used -- verified correct at seven deliberately
        # non-32-aligned `(M,K,N)` shapes (`mma_forge/probes/correctness_probe_partial.mojo`) and
        # bit-exact against the scalar oracles through this exact production shim at one of them
        # (`mma_partial_cross_check.mojo`). With that gate gone, MMA was re-measured against BOTH
        # scalar tiles across the full size range this policy used to split on: it wins at
        # Qwen3-0.6B-Base-scale shapes (2.2x-3.3x, unchanged) AND at `m_rows=5` -- the exact small-M
        # anchor `residentk_prefill_gemm_use_narrow_tile` was calibrated against -- where MMA still
        # beats the narrow scalar tile 1.83x (`mma_small_m_speed.mojo`, reproduced 3x). The
        # wide/narrow scalar split this file used to make below is therefore never selected in
        # practice anymore; left in place (not deleted) as the fallback path and because both
        # scalar kernels remain Gate-0 oracles the MMA kernels are diffed against.
        var use_mma = True
        # Phase 1 of the tiled-MMA-attention plan (separate from the GEMM MMA work above): one
        # online-softmax rescale per block of 8 keys instead of one per key, in
        # `_pf_attn8_kernel_simd`, gated in against the byte-unmodified `_pf_attn_tiled_kernel_simd`
        # oracle (`test_residentk_prefill_attn_kernels.mojo`). MEASURED, real pipeline, real
        # checkpoint, 3 runs at n_prompt=256: 1606-1788 tok/s prefill, vs. the ~1950-2025 tok/s
        # this same driver gets with `use_block8_attn = False` -- a real ~10-20% REGRESSION, not a
        # win. Consistent with the reduction itself (the two-level SIMD-shuffle dot product, still
        # one barrier pair per key either way) being the dominant per-key cost, not the
        # online-softmax bookkeeping this change targeted -- exactly the "does fewer rescales alone
        # help" question this phase was designed to isolate, answered no. Left `False`; the kernel,
        # its Gate-0 test, and this role stay in place as a correctness-verified artifact and as the
        # variable-isolation data point Phase 2 (hardware MMA for Q@K^T, which targets the
        # reduction itself) is designed around.
        var use_block8_attn = False
        var pf_attn = (
            self.prefill_pipeline_idx[_PFROLE_ATTN_BLOCK8] if use_block8_attn
            else self.prefill_pipeline_idx[_PFROLE_ATTN]
        )
        var use_narrow = residentk_prefill_gemm_use_narrow_tile(m_rows)
        var gemm_bm = 32 if use_mma else (_GEMM_BM_NARROW if use_narrow else _GEMM_BM)
        var gemm_nthreads = 256 if use_mma else (_GEMM_NTHREADS_NARROW if use_narrow else _GEMM_NTHREADS)
        var n_tile_rows_qkv = _ceil_div(m_rows, gemm_bm)
        var pf_assign = (
            self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN]
        )
        var pf_accum = (
            self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM]
        )
        var pf_swiglu = (
            self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU_MMA] if use_mma
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU_NARROW] if use_narrow
            else self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU]
        )

        _mb_set_header(
            self.descriptors_prefill, self.embed_d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            n_units_embed * m_rows, _TG, 6,
        )
        _mb_set_arg_int(self.descriptors_prefill, self.embed_d, 5, m_rows)

        for layer in range(self.n_layers):
            var d_norm = self.rmsnorm_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_norm, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                m_rows, _TG, 6,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_norm, 5, m_rows)

            var d_gemm = self.gemm_assign_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_gemm, pf_assign,
                n_tile_rows_qkv * n_tile_cols_qkv, gemm_nthreads, 7,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_gemm, 4, m_rows)

            var d_rope = self.ropewrt_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_rope, self.prefill_pipeline_idx[_PFROLE_ROPEWRT],
                n_units_rope * m_rows, self.d_head, 14,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_rope, 8, pos_base)
            _mb_set_arg_int(self.descriptors_prefill, d_rope, 13, m_rows)

            var d_attn = self.attn_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_attn, pf_attn,
                n_units_attn * m_rows, self.d_head, 10,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_attn, 4, pos_base)
            _mb_set_arg_int(self.descriptors_prefill, d_attn, 9, m_rows)

            var d_go = self.gemv_o_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_go, pf_accum,
                n_tile_rows_qkv * n_tile_cols_gemv, gemm_nthreads, 7,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_go, 4, m_rows)

            var d_norm2 = self.rmsnorm2_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_norm2, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                m_rows, _TG, 6,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_norm2, 5, m_rows)

            var d_sw = self.swiglu_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_sw, pf_swiglu,
                n_tile_rows_qkv * n_tile_cols_ff, gemm_nthreads, 7,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_sw, 4, m_rows)

            var d_gd = self.gemv_down_d[layer]
            _mb_set_header(
                self.descriptors_prefill, d_gd, pf_accum,
                n_tile_rows_qkv * n_tile_cols_gemv, gemm_nthreads, 7,
            )
            _mb_set_arg_int(self.descriptors_prefill, d_gd, 4, m_rows)

        # `hidden`'s `gpuAddress` plus `(m_rows - 1) * d_model` ELEMENTS (`* 4` bytes, Float32) --
        # ordinary pointer arithmetic on a real device virtual address, per module docstring.
        var last_row_addr = self.hidden_addr + UInt64((m_rows - 1) * self.d_model * 4)
        _mb_set_arg_ptr(self.descriptors_prefill, self.lmhead_d, 2, last_row_addr)

    def _build_descriptors_decode_native(mut self, n_qkv: Int) raises:
        """Project Redline reopening (2026-08-08): builds `self.descriptors_decode_native` -- ONE
        embed dispatch, SIX per-layer dispatches (`norm_gemv` [fused rmsnorm+qkv_proj, byte-identical
        role to `_build_descriptors`'s own first per-layer dispatch], the native-KV-producer
        [replaces `qk_rope`], the new native-decode-attn kernel [replaces `sdpa`], `gemv_accum` o_proj,
        `norm_gemv2_swiglu`, `gemv_accum` down_proj), then the UNMODIFIED `lmhead_argmax`/`argmax_
        reduce` pair -- `1 + n_layers*6 + 2` descriptors total, the SAME count `_build_descriptors`
        itself uses for `step()`'s own table. Unlike `_build_descriptors_prefill`/`_build_descriptors_
        prefill_af`, grid sizes here are all FIXED CONSTANTS set once (this table always processes
        exactly ONE row, never narrowed/widened per call) -- `step_native_kv` only ever patches
        `token_id`/`pos`/`n_keys` scalar arguments, exactly matching `step()`'s own discipline of
        never re-calling `_mb_set_header` after construction."""
        var n_q = self.h_q * self.d_head
        var n_units_kvprod = self.h_q + self.h_kv
        var d = 0

        _mb_set_header(self.descriptors_decode_native, d, self.pipeline_idx[_ROLE_EMBED], _ceil_div(self.d_model, _TG), _TG, 5)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_decode_native, d, 3, 0)  # token_id, patched per call
        self.token_id_offset_native = d
        _mb_set_arg_int(self.descriptors_decode_native, d, 4, self.d_model)
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            var ck_native_addr = self.af_ck_native_addr[layer]
            var cv_native_addr = self.af_cv_native_addr[layer]

            # ── role NORM_GEMV: byte-identical wiring to `_build_descriptors`'s own first per-layer
            # dispatch (fused rmsnorm+qkv_proj, writes `self.qkv_addr`).
            _mb_set_header(
                self.descriptors_decode_native, d, self.pipeline_idx[_ROLE_NORM_GEMV],
                _ceil_div(n_qkv, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, lw.ln1_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 4, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_decode_native, d, 6, n_qkv)
            _mb_set_arg_f32(self.descriptors_decode_native, d, 7, self.eps)
            d += 1

            # ── native-KV-producer at `m_rows=1` -- writes `self.q_native_addr` row 0 (F16 Q for
            # THIS decode step) and appends THIS step's own K/V into the native-packed buffers, at
            # whatever absolute `pos` `step_native_kv` patches into arg 8 below. Same 16-arg order
            # `_build_descriptors_prefill_af`'s own kvprod dispatch uses; `m_rows` (arg 15) is a
            # CONSTANT `1` here, never patched -- a decode step is always exactly one row.
            _mb_set_header(
                self.descriptors_decode_native, d, self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER],
                n_units_kvprod, self.d_head, 16,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, ck_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, cv_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 4, lw.qn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 5, lw.kn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 6, self.cos_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 7, self.sin_addr)
            _mb_set_arg_int(self.descriptors_decode_native, d, 8, 0)  # pos_base (== decode pos), patched per call
            self.pos_offsets_native.append(d)
            _mb_set_arg_int(self.descriptors_decode_native, d, 9, self.h_q)
            _mb_set_arg_int(self.descriptors_decode_native, d, 10, self.h_kv)
            _mb_set_arg_int(self.descriptors_decode_native, d, 11, self.d_head)
            _mb_set_arg_int(self.descriptors_decode_native, d, 12, _AF_KEY_BLOCK_SIZE)
            _mb_set_arg_int(self.descriptors_decode_native, d, 13, self.af_n_blocks)
            _mb_set_arg_f32(self.descriptors_decode_native, d, 14, self.eps)
            _mb_set_arg_int(self.descriptors_decode_native, d, 15, 1)  # m_rows, CONSTANT (decode = 1 row)
            # NOTE: no separate per-layer index list needed for THIS dispatch beyond `self.pos_
            # offsets_native` above (already the descriptor index `step_native_kv` patches arg 8 at)
            # -- deliberately NOT reusing `self.kvprod_af2_d` (that list belongs to the UNRELATED
            # no-mirror PREFILL table built by `_build_descriptors_prefill_af_nomirror`; appending to
            # it here would silently corrupt that table's own per-layer indexing).
            d += 1

            # ── the new decode-side kernel: reads `self.q_native_addr` row 0 + the native-packed
            # K/V the dispatch above just appended to, writes `self.attn_out_addr` row 0 -- SAME
            # buffer/layout `_ROLE_SDPA`'s own dispatch in `_build_descriptors` writes, so the
            # `gemv_accum` (o_proj) dispatch right after this one needs no changes at all. 11 args --
            # see `attention_forge.native_kv_decode_attn._native_kv_decode_attn_kernel`'s own
            # signature for the exact order.
            _mb_set_header(
                self.descriptors_decode_native, d, self.native_decode_attn_pipeline_idx,
                self.h_q, self.d_head, 11,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, ck_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, cv_native_addr)
            _mb_set_arg_int(self.descriptors_decode_native, d, 4, 0)  # n_keys, patched per call
            self.nkeys_offsets_native.append(d)
            _mb_set_arg_int(self.descriptors_decode_native, d, 5, self.h_q)
            _mb_set_arg_int(self.descriptors_decode_native, d, 6, self.h_kv)
            _mb_set_arg_int(self.descriptors_decode_native, d, 7, self.d_head)
            _mb_set_arg_f32(self.descriptors_decode_native, d, 8, self.scale)
            _mb_set_arg_int(self.descriptors_decode_native, d, 9, _AF_KEY_BLOCK_SIZE)
            _mb_set_arg_int(self.descriptors_decode_native, d, 10, self.af_n_blocks)
            # NOTE: same reasoning as the kvprod dispatch above -- `self.nkeys_offsets_native` is
            # this dispatch's own per-layer index; `self.attn_af2_d` belongs to the unrelated
            # no-mirror prefill table and must not be touched here.
            d += 1

            # ── role GEMV_ACCUM (o_proj): byte-identical wiring to `_build_descriptors`'s own.
            _mb_set_header(
                self.descriptors_decode_native, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native, d, 4, n_q)
            _mb_set_arg_int(self.descriptors_decode_native, d, 5, self.d_model)
            d += 1

            # ── role NORM_GEMV2_SWIGLU: byte-identical wiring to `_build_descriptors`'s own.
            _mb_set_header(
                self.descriptors_decode_native, d, self.pipeline_idx[_ROLE_NORM_GEMV2_SWIGLU],
                _ceil_div(self.d_ff, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, lw.ln2_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 4, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_decode_native, d, 6, self.d_ff)
            _mb_set_arg_f32(self.descriptors_decode_native, d, 7, self.eps)
            d += 1

            # ── role GEMV_ACCUM (down_proj): byte-identical wiring to `_build_descriptors`'s own.
            _mb_set_header(
                self.descriptors_decode_native, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native, d, 4, self.d_ff)
            _mb_set_arg_int(self.descriptors_decode_native, d, 5, self.d_model)
            d += 1

        # ── final-norm+lm_head+argmax: the UNMODIFIED single-row kernel, byte-identical wiring to
        # `_build_descriptors`'s own tail -- decode always reads row 0 of `self.hidden_addr`
        # directly, no offset patch needed (unlike prefill's own `last_row_addr` trick).
        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors_decode_native, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 4, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 5, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_decode_native, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors_decode_native, d, 7, self.vocab)
        _mb_set_arg_f32(self.descriptors_decode_native, d, 8, self.eps)
        _mb_set_arg_int(self.descriptors_decode_native, d, 9, n_iters)
        d += 1

        _mb_set_header(self.descriptors_decode_native, d, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 0, self.out_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 1, self.out_idx_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 2, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native, d, 3, self.blk_idx_addr)
        _mb_set_arg_int(self.descriptors_decode_native, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors_decode_native:
            raise Error(
                "metaldispatch: built " + String(d) + " decode-native descriptors but the budget says "
                + String(self.n_descriptors_decode_native) + " -- the design and the code disagree, status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )

    def _build_descriptors_decode_native_splitk(mut self, n_qkv: Int) raises:
        """Beat-llama.cpp campaign (2026-08-08 night): the split-K twin of `_build_descriptors_
        decode_native` -- byte-for-byte the SAME table (one embed dispatch, the same six per-layer
        roles, the unmodified lmhead/argmax tail) with EXACTLY ONE substitution: the naive single-
        dispatch decode-attention slot becomes the flash-decoding PAIR -- the split-K partial
        (`attention_forge.native_kv_decode_attn_splitk._native_kv_decode_splitk_partial_kernel`,
        grid `h_q * _NATIVE_DECODE_N_SPLITS`, writing unnormalized (m, l, o) partials into `self.
        splitk_m_addr`/`splitk_l_addr`/`splitk_o_addr`) immediately followed by the engine's own
        EXISTING `_splitk_merge_kernel_simd` (grid `h_q`, block `d_head`, layout-agnostic by its
        own contract -- it only ever reads the m/l/o scratch -- reused completely unchanged, the
        same pipeline the legacy deep path merges with). Same fixed-grid discipline as the naive
        table (grids set ONCE here; `step` patches only scalar args). The campaign's isolated
        driver measured this pair 6.5-10x faster per dispatch than the naive kernel at the race's
        own decode depths (256-1024 keys) with bit-for-bit-same-function output (its cross-check
        gate, Float32-reordering tolerance) -- see `attention_forge/native_kv_decode_attn_splitk_
        driver.mojo`."""
        var n_q = self.h_q * self.d_head
        var n_units_kvprod = self.h_q + self.h_kv
        var d = 0

        _mb_set_header(self.descriptors_decode_native_splitk, d, self.pipeline_idx[_ROLE_EMBED], _ceil_div(self.d_model, _TG), _TG, 5)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 3, 0)  # token_id, patched per call
        self.token_id_offset_native_splitk = d
        _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 4, self.d_model)
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            var ck_native_addr = self.af_ck_native_addr[layer]
            var cv_native_addr = self.af_cv_native_addr[layer]

            # ── role NORM_GEMV: byte-identical wiring to the naive table's own.
            _mb_set_header(
                self.descriptors_decode_native_splitk, d, self.pipeline_idx[_ROLE_NORM_GEMV],
                _ceil_div(n_qkv, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, lw.ln1_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 4, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 6, n_qkv)
            _mb_set_arg_f32(self.descriptors_decode_native_splitk, d, 7, self.eps)
            d += 1

            # ── native-KV-producer at m_rows=1: byte-identical wiring to the naive table's own
            # (per-step cache append + F16 Q narrow).
            _mb_set_header(
                self.descriptors_decode_native_splitk, d, self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER],
                n_units_kvprod, self.d_head, 16,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, ck_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, cv_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 4, lw.qn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 5, lw.kn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 6, self.cos_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 7, self.sin_addr)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 8, 0)  # pos_base (== decode pos), patched per call
            self.pos_offsets_native_splitk.append(d)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 9, self.h_q)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 10, self.h_kv)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 11, self.d_head)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 12, _AF_KEY_BLOCK_SIZE)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 13, self.af_n_blocks)
            _mb_set_arg_f32(self.descriptors_decode_native_splitk, d, 14, self.eps)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 15, 1)  # m_rows, CONSTANT (decode = 1 row)
            d += 1

            # ── THE substitution, dispatch 1/2: split-K PARTIAL over this step's full key range --
            # 14 args, exact order of `_native_kv_decode_splitk_partial_kernel`'s own signature.
            _mb_set_header(
                self.descriptors_decode_native_splitk, d, self.native_decode_splitk_partial_pipeline_idx,
                self.h_q * _NATIVE_DECODE_N_SPLITS, self.d_head, 14,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.splitk_m_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.splitk_l_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, self.splitk_o_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 4, ck_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 5, cv_native_addr)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 6, 0)  # n_keys, patched per call
            self.nkeys_offsets_native_splitk.append(d)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 7, _NATIVE_DECODE_N_SPLITS)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 8, self.h_q)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 9, self.h_kv)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 10, self.d_head)
            _mb_set_arg_f32(self.descriptors_decode_native_splitk, d, 11, self.scale)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 12, _AF_KEY_BLOCK_SIZE)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 13, self.af_n_blocks)
            d += 1

            # ── THE substitution, dispatch 2/2: the engine's EXISTING merge kernel collapses the
            # `_NATIVE_DECODE_N_SPLITS` partials per head into `self.attn_out_addr` row 0 -- the
            # SAME buffer the naive table's single dispatch writes, so every role after this one is
            # byte-identical to the naive table's own. 6 args, exact order of
            # `_splitk_merge_kernel_simd`'s own signature.
            _mb_set_header(
                self.descriptors_decode_native_splitk, d, self.pipeline_idx_merge,
                self.h_q, self.d_head, 6,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.splitk_m_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, self.splitk_l_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, self.splitk_o_addr)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 4, _NATIVE_DECODE_N_SPLITS)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 5, self.d_head)
            d += 1

            # ── role GEMV_ACCUM (o_proj): byte-identical wiring to the naive table's own.
            _mb_set_header(
                self.descriptors_decode_native_splitk, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 4, n_q)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 5, self.d_model)
            d += 1

            # ── role NORM_GEMV2_SWIGLU: byte-identical wiring to the naive table's own.
            _mb_set_header(
                self.descriptors_decode_native_splitk, d, self.pipeline_idx[_ROLE_NORM_GEMV2_SWIGLU],
                _ceil_div(self.d_ff, _SUBS), _TG, 8,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, lw.ln2_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 4, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 6, self.d_ff)
            _mb_set_arg_f32(self.descriptors_decode_native_splitk, d, 7, self.eps)
            d += 1

            # ── role GEMV_ACCUM (down_proj): byte-identical wiring to the naive table's own.
            _mb_set_header(
                self.descriptors_decode_native_splitk, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 4, self.d_ff)
            _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 5, self.d_model)
            d += 1

        # ── final-norm+lm_head+argmax pair: byte-identical wiring to the naive table's own tail.
        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors_decode_native_splitk, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 4, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 5, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 7, self.vocab)
        _mb_set_arg_f32(self.descriptors_decode_native_splitk, d, 8, self.eps)
        _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 9, n_iters)
        d += 1

        _mb_set_header(self.descriptors_decode_native_splitk, d, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 0, self.out_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 1, self.out_idx_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 2, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_native_splitk, d, 3, self.blk_idx_addr)
        _mb_set_arg_int(self.descriptors_decode_native_splitk, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors_decode_native_splitk:
            raise Error(
                "metaldispatch: built " + String(d) + " decode-native-splitk descriptors but the budget says "
                + String(self.n_descriptors_decode_native_splitk) + " -- the design and the code disagree, status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights, batched prefill + SDPA/GEMV/lm_head/argmax-reduce SIMD-shuffle reduction, deep split-K native single-SIMD-group reduction, DYNAMIC per-step n_splits policy)"

    def dispatch_budget(self) -> Int:
        return self.n_descriptors

    def prefill_dispatch_budget(self) -> Int:
        return self.n_descriptors_prefill

    def n_cores_detected(self) -> Int:
        return self.n_cores

    def n_splits_currently_applied(self) -> Int:
        return self.deep_last_n_splits

    def upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return MB_ERR_CONTEXT_FULL
        var s = _quantize_into_i8(
            self.embed_ptr, self.embed_scale_ptr, embed, self.vocab, self.d_model, 0, 0
        )
        if s != MB_OK:
            return s
        s = _narrow_into(self.final_norm_ptr, final_norm, self.d_model, 0)
        if s != MB_OK:
            return s
        if len(cos_t) < n_pos * n_pairs or len(sin_t) < n_pos * n_pairs:
            return MB_ERR_UPLOAD_LENGTH
        var cos_f = self.cos_ptr.bitcast[Float32]()
        var sin_f = self.sin_ptr.bitcast[Float32]()
        for i in range(n_pos * n_pairs):
            cos_f[i] = Float32(cos_t[i])
            sin_f[i] = Float32(sin_t[i])
        return MB_OK

    def upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        if layer < 0 or layer >= self.n_layers:
            return MB_ERR_UPLOAD_LENGTH
        ref lw = self.layers[layer]
        var s = _narrow_into(lw.ln1_ptr, ln1, self.d_model, 0)
        if s != MB_OK:
            return s
        s = _narrow_into(lw.ln2_ptr, ln2, self.d_model, 0)
        if s != MB_OK:
            return s
        s = _narrow_into(lw.qn_ptr, qn, self.d_head, 0)
        if s != MB_OK:
            return s
        s = _narrow_into(lw.kn_ptr, kn, self.d_head, 0)
        if s != MB_OK:
            return s

        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        s = _quantize_transposed_into_i8(
            lw.w_qkv_ptr, lw.w_qkv_scale_ptr, wq, self.d_model, n_q, 0, 0
        )
        if s != MB_OK:
            return s
        s = _quantize_transposed_into_i8(
            lw.w_qkv_ptr, lw.w_qkv_scale_ptr, wk, self.d_model, n_kv, n_q, n_q
        )
        if s != MB_OK:
            return s
        s = _quantize_transposed_into_i8(
            lw.w_qkv_ptr, lw.w_qkv_scale_ptr, wv, self.d_model, n_kv, n_q + n_kv, n_q + n_kv
        )
        if s != MB_OK:
            return s
        s = _quantize_transposed_into_i8(lw.w_o_ptr, lw.w_o_scale_ptr, wo, n_q, self.d_model, 0, 0)
        if s != MB_OK:
            return s
        s = _quantize_transposed_into_i8(
            lw.w_gu_ptr, lw.w_gu_scale_ptr, wgate, self.d_model, self.d_ff, 0, 0
        )
        if s != MB_OK:
            return s
        s = _quantize_transposed_into_i8(
            lw.w_gu_ptr, lw.w_gu_scale_ptr, wup, self.d_model, self.d_ff, self.d_ff, self.d_ff
        )
        if s != MB_OK:
            return s
        s = _quantize_transposed_into_i8(
            lw.w_down_ptr, lw.w_down_scale_ptr, wdown, self.d_ff, self.d_model, 0, 0
        )
        if s != MB_OK:
            return s
        # ── Phase 3 (2026-08-08): materialize the ALREADY-DEQUANTIZED Float16 twins the three MSL
        # parity kernels read, from the EXACT Int8 bytes + per-row Float32 scale just written above
        # (see `_dequant_i8_into_f16`'s own docstring for why this keeps the MSL arm's math the
        # SAME as every Int8/vecload4 arm). Gated on `self.msl_any_linked`: a binary that never
        # links `msl_parity_blob.c` skips this entirely (the lists are empty, the buffers were never
        # allocated) and keeps its pre-Phase-3 upload behavior byte-for-byte. Every scale array's
        # row offsets match the weight rows 1:1 in all four buffers (each `_quantize_transposed_
        # into_i8` call above used identical `row_off`/`scale_off` pairs), so a whole-buffer
        # dequantize per role is correct.
        if self.msl_any_linked:
            _dequant_i8_into_f16(
                self.msl_w_qkv_f16_ptr[layer], lw.w_qkv_ptr, lw.w_qkv_scale_ptr,
                self.n_qkv, self.d_model,
            )
            _dequant_i8_into_f16(
                self.msl_w_o_f16_ptr[layer], lw.w_o_ptr, lw.w_o_scale_ptr,
                self.d_model, n_q,
            )
            _dequant_i8_into_f16(
                self.msl_w_gu_f16_ptr[layer], lw.w_gu_ptr, lw.w_gu_scale_ptr,
                2 * self.d_ff, self.d_model,
            )
            _dequant_i8_into_f16(
                self.msl_w_down_f16_ptr[layer], lw.w_down_ptr, lw.w_down_scale_ptr,
                self.d_model, self.d_ff,
            )
        return MB_OK

    # ── Parity cheap wins (beat-llama.cpp campaign, 2026-08-10): quantized-state persistence ──
    # The one-shot entry points re-upload weights on EVERY call: read the flat Float64 blob (8
    # bytes/param), run the two-pass per-row quantization, then write the device buffers. These
    # three methods persist EXACTLY the post-quantization device bytes -- Int8 weights + per-row
    # Float32 scales + Float32 norms, 1 byte/param + scales -- so a second call on the same
    # converted checkpoint reads ~1/8 the bytes and runs NO quantization arithmetic at all. The
    # entry point owns the file format and the validity gate (manifest hash + dims); this struct
    # owns only the byte LAYOUT, which is its own business: `dump_quantized_state` writes the
    # regions below in this exact order, and `load_quantized_state` validates every region length
    # against its own dimensions and refuses the whole load on any mismatch (never a half-loaded
    # session). The RoPE tables are deliberately NOT part of this state: they derive from
    # theta/max_ctx (runtime parameters, not weights) and are cheap to rebuild -- the entry point
    # uploads them via `upload_rope_tables` on the cached path too.

    def quantized_state_bytes(self) -> Int:
        """The exact byte count `dump_quantized_state` produces -- lets a caller size its buffer
        (or a file-length gate) before reading a single byte."""
        var n_q = self.h_q * self.d_head
        var per_layer = (
            4 * (2 * self.d_model + 2 * self.d_head)
            + self.n_qkv * (self.d_model + 4)
            + self.d_model * (n_q + 4)
            + 2 * self.d_ff * (self.d_model + 4)
            + self.d_model * (self.d_ff + 4)
        )
        return self.vocab * (self.d_model + 4) + 4 * self.d_model + self.n_layers * per_layer

    def dump_quantized_state(mut self) raises -> List[UInt8]:
        """Serialize the EXACT post-quantization device bytes: embed Int8 + per-row Float32 scale,
        final-norm Float32, then per layer the four norms (Float32) and the four GEMM roles'
        Int8 weights + per-row Float32 scales, in the fixed region order `load_quantized_state`
        expects. Byte-identical to what `upload_globals`/`upload_layer` computed -- this reads the
        very buffers the GPU kernels read, never the f64 source -- so a restored session runs the
        SAME quantized math, token for token. (`mut self` for the same reason `upload_layer` is:
        `ref lw = self.layers[layer]` -- the pinned compiler has no implicit copy of
        `_MBLayerBufI8`, and this method changes nothing the read cannot see.)"""
        var n_q = self.h_q * self.d_head
        var out = List[UInt8](capacity=self.quantized_state_bytes())
        for i in range(self.vocab * self.d_model):
            out.append(self.embed_ptr[i])
        for i in range(self.vocab * 4):
            out.append(self.embed_scale_ptr[i])
        for i in range(self.d_model * 4):
            out.append(self.final_norm_ptr[i])
        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            for i in range(self.d_model * 4):
                out.append(lw.ln1_ptr[i])
            for i in range(self.d_model * 4):
                out.append(lw.ln2_ptr[i])
            for i in range(self.d_head * 4):
                out.append(lw.qn_ptr[i])
            for i in range(self.d_head * 4):
                out.append(lw.kn_ptr[i])
            for i in range(self.n_qkv * self.d_model):
                out.append(lw.w_qkv_ptr[i])
            for i in range(self.n_qkv * 4):
                out.append(lw.w_qkv_scale_ptr[i])
            for i in range(self.d_model * n_q):
                out.append(lw.w_o_ptr[i])
            for i in range(self.d_model * 4):
                out.append(lw.w_o_scale_ptr[i])
            for i in range(2 * self.d_ff * self.d_model):
                out.append(lw.w_gu_ptr[i])
            for i in range(2 * self.d_ff * 4):
                out.append(lw.w_gu_scale_ptr[i])
            for i in range(self.d_model * self.d_ff):
                out.append(lw.w_down_ptr[i])
            for i in range(self.d_model * 4):
                out.append(lw.w_down_scale_ptr[i])
        return out^

    def load_quantized_state(mut self, raw: List[UInt8]) raises -> Int:
        """The exact inverse of `dump_quantized_state`: validate the byte count against this
        session's own dimensions, copy each region into the same device buffers `upload_globals`/
        `upload_layer` would have written, then rebuild the Float16 dequantized twins the MSL
        kernels read (from the SAME restored Int8 + scale -- the same `_dequant_i8_into_f16` calls
        `upload_layer` runs, so the cached path and the f64 path land on byte-identical device
        state). Returns MB_OK, or MB_ERR_UPLOAD_LENGTH without touching any buffer the count check
        already ruled out."""
        if len(raw) != self.quantized_state_bytes():
            return MB_ERR_UPLOAD_LENGTH
        var n_q = self.h_q * self.d_head
        var cursor = 0
        for i in range(self.vocab * self.d_model):
            self.embed_ptr[i] = raw[cursor + i]
        cursor += self.vocab * self.d_model
        for i in range(self.vocab * 4):
            self.embed_scale_ptr[i] = raw[cursor + i]
        cursor += self.vocab * 4
        for i in range(self.d_model * 4):
            self.final_norm_ptr[i] = raw[cursor + i]
        cursor += self.d_model * 4
        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            for i in range(self.d_model * 4):
                lw.ln1_ptr[i] = raw[cursor + i]
            cursor += self.d_model * 4
            for i in range(self.d_model * 4):
                lw.ln2_ptr[i] = raw[cursor + i]
            cursor += self.d_model * 4
            for i in range(self.d_head * 4):
                lw.qn_ptr[i] = raw[cursor + i]
            cursor += self.d_head * 4
            for i in range(self.d_head * 4):
                lw.kn_ptr[i] = raw[cursor + i]
            cursor += self.d_head * 4
            for i in range(self.n_qkv * self.d_model):
                lw.w_qkv_ptr[i] = raw[cursor + i]
            cursor += self.n_qkv * self.d_model
            for i in range(self.n_qkv * 4):
                lw.w_qkv_scale_ptr[i] = raw[cursor + i]
            cursor += self.n_qkv * 4
            for i in range(self.d_model * n_q):
                lw.w_o_ptr[i] = raw[cursor + i]
            cursor += self.d_model * n_q
            for i in range(self.d_model * 4):
                lw.w_o_scale_ptr[i] = raw[cursor + i]
            cursor += self.d_model * 4
            for i in range(2 * self.d_ff * self.d_model):
                lw.w_gu_ptr[i] = raw[cursor + i]
            cursor += 2 * self.d_ff * self.d_model
            for i in range(2 * self.d_ff * 4):
                lw.w_gu_scale_ptr[i] = raw[cursor + i]
            cursor += 2 * self.d_ff * 4
            for i in range(self.d_model * self.d_ff):
                lw.w_down_ptr[i] = raw[cursor + i]
            cursor += self.d_model * self.d_ff
            for i in range(self.d_model * 4):
                lw.w_down_scale_ptr[i] = raw[cursor + i]
            cursor += self.d_model * 4
            if self.msl_any_linked:
                _dequant_i8_into_f16(
                    self.msl_w_qkv_f16_ptr[layer], lw.w_qkv_ptr, lw.w_qkv_scale_ptr,
                    self.n_qkv, self.d_model,
                )
                _dequant_i8_into_f16(
                    self.msl_w_o_f16_ptr[layer], lw.w_o_ptr, lw.w_o_scale_ptr,
                    self.d_model, n_q,
                )
                _dequant_i8_into_f16(
                    self.msl_w_gu_f16_ptr[layer], lw.w_gu_ptr, lw.w_gu_scale_ptr,
                    2 * self.d_ff, self.d_model,
                )
                _dequant_i8_into_f16(
                    self.msl_w_down_f16_ptr[layer], lw.w_down_ptr, lw.w_down_scale_ptr,
                    self.d_model, self.d_ff,
                )
        return MB_OK

    def upload_rope_tables(
        mut self, cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The RoPE half of `upload_globals`, split out so the quantized-state cache path -- which
        restores embed/norms/weights from disk and therefore never calls `upload_globals` -- still
        uploads the cos/sin tables (they are theta/max_ctx-derived, not weight-derived, so they
        are rebuilt, never cached). Byte-identical loop to `upload_globals`'s own."""
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return MB_ERR_CONTEXT_FULL
        if len(cos_t) < n_pos * n_pairs or len(sin_t) < n_pos * n_pairs:
            return MB_ERR_UPLOAD_LENGTH
        var cos_f = self.cos_ptr.bitcast[Float32]()
        var sin_f = self.sin_ptr.bitcast[Float32]()
        for i in range(n_pos * n_pairs):
            cos_f[i] = Float32(cos_t[i])
            sin_f[i] = Float32(sin_t[i])
        return MB_OK

    def seal(mut self) -> Int:
        return MB_OK

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """THE public decode entry point -- round 5 (2026-08-08), plan-aware routing. Calls `self.
        _require_resolved_plan()` first (same defense-in-depth `prefill_batch`/`_apply_m_rows_af_
        nomirror` already run before reading `self.plan` for a real dispatch decision), then routes
        on `self.plan.decode`: `DECODE_PATH_NATIVE_PACKED_KV` -> `self._step_native_kv_impl` (reads
        the packed F16 native buffers a `PF_ATTN_GROUPED_FA_NO_MIRROR` prefill populated),
        `DECODE_PATH_LEGACY_NATURAL_KV` -> `self._step_legacy_impl` (reads the natural F32 `ck`/`cv`
        cache every OTHER attention path populates). See `session_prefill_policy.ResolvedSession
        ExecutionPlan.decode`'s own docstring for why this field is ALWAYS derived from `self.plan.
        attention` and never independently wrong -- this router therefore can never read the wrong
        cache for whatever this instance's most recent `prefill_batch()` call actually populated.

        For every caller that only ever resolves `PF_ATTN_OFF`/`PF_ATTN_GROUPED_FA_WITH_MIRROR`
        (every real caller today, and every existing test/benchmark this file's own module docstring
        addendum, round 5, discusses), `self.plan.decode` always resolves to `DECODE_PATH_LEGACY_
        NATURAL_KV` -- this method dispatches `_step_legacy_impl` unconditionally for them, BYTE-FOR-
        BYTE what this method's own body used to be before this router was introduced. Zero behavior
        change for those callers; see that method's own docstring (moved here verbatim) for the full
        account of what it dispatches."""
        self._require_resolved_plan()
        if self.plan.decode == DECODE_PATH_NATIVE_PACKED_KV:
            return self._step_native_kv_impl(token_id, pos)
        return self._step_legacy_impl(token_id, pos)

    def step_native_kv(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """TEST-ONLY hook, round 5 (2026-08-08): a thin public wrapper around `self._step_native_kv_
        impl`, kept ONLY so existing test call sites that want to exercise the native-KV decode
        implementation directly, independent of plan-based routing, keep compiling and passing
        unmodified (`test_metaldispatch_session_prefill_native_decode.mojo`'s own gates do exactly
        this, deliberately, to test the implementation in isolation from `step()`'s own router).
        NO production entry point calls this method directly anymore -- see `session_prefill.mojo`'s
        own module docstring addendum, round 5, for the full account of why `step()` alone is now the
        one production-facing decode entry point, for EVERY resolved plan."""
        return self._step_native_kv_impl(token_id, pos)

    def _step_legacy_impl(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-identical to `_MBQwen3I8AllSimd7.step` -- see that method's own docstring. Untouched
        by this struct's own `prefill_batch()` addition: reads/writes exactly row 0 of every
        activation buffer, regardless of how many rows `prefill_batch()` most recently used. Renamed
        from the public `step()` (round 5, 2026-08-08) -- the public `step()` above is now a thin,
        plan-aware router; this method's own body is unchanged, byte-for-byte, from what `step()`
        used to be. Called for `DECODE_PATH_LEGACY_NATURAL_KV` -- reads the natural F32 `ck`/`cv`
        cache."""
        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            var n_keys = pos + 1
            var dispatches_used = self.n_descriptors

            if not residentk_splitk_should_split(n_keys):
                _mb_set_arg_int(self.descriptors, self.token_id_offset, 3, token_id)
                for layer in range(self.n_layers):
                    _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                    _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

                var rc = _mb_run_token(self.descriptors, self.n_descriptors)
                if rc != 0:
                    return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            else:
                self._ensure_deep_initialized()
                dispatches_used = self.n_descriptors_deep

                var n_splits = residentk_splitk_policy(n_keys, self.n_cores, self.h_q)
                if n_splits != self.deep_last_n_splits:
                    self._apply_n_splits(n_splits)
                    self.deep_last_n_splits = n_splits

                _mb_set_arg_int(self.descriptors_deep, self.token_id_offset_deep, 3, token_id)
                for layer in range(self.n_layers):
                    _mb_set_arg_int(self.descriptors_deep, self.pos_offsets_deep[layer], 8, pos)
                    _mb_set_arg_int(self.descriptors_deep, self.nkeys_offsets_deep[layer], 6, n_keys)

                var rc = _mb_run_token(self.descriptors_deep, self.n_descriptors_deep)
                if rc != 0:
                    return _StepOut(-1, 0.0, self.n_descriptors_deep, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, dispatches_used, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, dispatches_used, MB_OK)

    # ── Project Slipstream Phase 3 (2026-08-09): BATCHED / continuous-batching decode. B sequences
    # stepped together in ONE descriptor-table submission: every projection is the PREFILL tiled-GEMM
    # shape at m_rows=B (weights swept once for all B -- the tokens-per-weight-sweep win), attention
    # is the per-sequence flash-decoding partial blob + engine-side B-aware merge, KV is the per-layer
    # oversized batched buffers (seq b at `b * batch_kv_stride_elems`), and the tail is B single-row
    # lm_head/argmax dispatches into B-sized partial/out regions. `_ensure_decode_batched_ready(B)`
    # (re)builds the table for a given B; `_step_batched` writes the per-sequence token/pos/n_keys
    # state into the device buffers, submits, and reads back B tokens.
    def _ensure_decode_batched_ready(mut self, B: Int) raises:
        if not self.decode_batched_built:
            raise Error(
                "metaldispatch: batched decode requested but the batched pipelines were not all "
                + "discovered (decode_batched_built=False), status=" + String(MB_ERR_PIPELINE_NOT_FOUND)
            )
        if B < 1 or B > _BATCH_DECODE_MAX_SEQS:
            raise Error(
                "metaldispatch: batched decode B=" + String(B) + " out of range [1,"
                + String(_BATCH_DECODE_MAX_SEQS) + "], status=" + String(MB_ERR_CONTEXT_FULL)
            )
        if self.decode_batched_B == B:
            return

        var n_q = self.h_q * self.d_head
        var n_qkv = self.n_qkv
        var kv_stride = self.batch_kv_stride_elems
        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        var n_rows_tile = _ceil_div(B, _GEMM_BM)

        self.n_descriptors_decode_batched = 1 + self.n_layers * 9 + 3
        self.descriptors_decode_batched = _mb_alloc_descriptors(self.n_descriptors_decode_batched)
        var d = 0

        # embed: B token ids -> hidden [B, d_model] (prefill embed-rows kernel).
        _mb_set_header(
            self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            _ceil_div(self.d_model, _TG) * B, _TG, 6,
        )
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, self.embed_scale_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, self.prompt_ids_addr)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 4, self.d_model)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 5, B)
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]
            var ck_addr = self.batch_ck_native_addr[layer]
            var cv_addr = self.batch_cv_native_addr[layer]

            # rmsnorm -> xn
            _mb_set_header(
                self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                B, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, lw.ln1_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_decode_batched, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 5, B)
            d += 1

            # qkv_proj GEMM: xn [B,d_model] @ w_qkv -> qkv [B,n_qkv]
            _mb_set_header(
                self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ASSIGN],
                n_rows_tile * _ceil_div(n_qkv, _GEMM_BN), _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, lw.w_qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, lw.w_qkv_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 4, B)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 6, n_qkv)
            d += 1

            # batched KV producer: QK-norm + RoPE + pack Q -> q_native, K/V -> seq-b caches at poss[b]
            _mb_set_header(
                self.descriptors_decode_batched, d, self.kvprod_batched_pipeline_idx,
                (self.h_q + self.h_kv) * B, self.d_head, 16,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, ck_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, cv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 4, lw.qn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 5, lw.kn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 6, self.cos_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 7, self.sin_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 8, self.batch_poss_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 9, kv_stride)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 10, self.h_q)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 11, self.h_kv)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 12, self.d_head)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 13, _AF_KEY_BLOCK_SIZE)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 14, self.af_n_blocks)
            _mb_set_arg_f32(self.descriptors_decode_batched, d, 15, self.eps)
            d += 1

            # batched attention PARTIAL (blob): per-seq flash-decoding over [0, nkeys[b])
            _mb_set_header(
                self.descriptors_decode_batched, d, self.native_decode_splitk_partial_batched_pipeline_idx,
                B * self.h_q * _NATIVE_DECODE_N_SPLITS, self.d_head, 15,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.batch_splitk_m_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.batch_splitk_l_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, self.batch_splitk_o_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, self.q_native_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 4, ck_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 5, cv_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 6, self.batch_nkeys_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 7, kv_stride)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 8, _NATIVE_DECODE_N_SPLITS)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 9, self.h_q)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 10, self.h_kv)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 11, self.d_head)
            _mb_set_arg_f32(self.descriptors_decode_batched, d, 12, self.scale)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 13, _AF_KEY_BLOCK_SIZE)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 14, self.af_n_blocks)
            d += 1

            # batched attention MERGE (engine-side): collapse [B,h_q,n_splits] partials -> attn_out [B,n_q]
            _mb_set_header(
                self.descriptors_decode_batched, d, self.batched_splitk_merge_pipeline_idx,
                B * self.h_q, self.d_head, 7,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.batch_splitk_m_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, self.batch_splitk_l_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, self.batch_splitk_o_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 4, _NATIVE_DECODE_N_SPLITS)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 5, self.h_q)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 6, self.d_head)
            d += 1

            # o_proj GEMM accum: hidden += attn_out [B,n_q] @ w_o
            _mb_set_header(
                self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_rows_tile * _ceil_div(self.d_model, _GEMM_BN), _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, lw.w_o_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, lw.w_o_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 4, B)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 5, n_q)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 6, self.d_model)
            d += 1

            # rmsnorm2 -> xn
            _mb_set_header(
                self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                B, _TG, 6,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, lw.ln2_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 3, self.d_model)
            _mb_set_arg_f32(self.descriptors_decode_batched, d, 4, self.eps)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 5, B)
            d += 1

            # gate/up + swiglu GEMM: xn [B,d_model] @ w_gu -> act [B,d_ff]
            _mb_set_header(
                self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_GEMM_SWIGLU],
                n_rows_tile * _ceil_div(self.d_ff, _GEMM_BN), _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.xn_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, lw.w_gu_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, lw.w_gu_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 4, B)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 5, self.d_model)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 6, self.d_ff)
            d += 1

            # down_proj GEMM accum: hidden += act [B,d_ff] @ w_down
            _mb_set_header(
                self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_GEMM_ACCUM],
                n_rows_tile * _ceil_div(self.d_model, _GEMM_BN), _GEMM_NTHREADS, 7,
            )
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, lw.w_down_addr)
            _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, lw.w_down_scale_addr)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 4, B)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 5, self.d_ff)
            _mb_set_arg_int(self.descriptors_decode_batched, d, 6, self.d_model)
            d += 1

        # tail: BATCHED lm_head (Slipstream Phase 3 Option B) -- 3 dispatches instead of 2*B, and the
        # lm_head/embed weight is swept ONCE for all B rows instead of once per sequence.
        # (1) final rmsnorm: hidden [B, d_model] -> xn [B, d_model] (overwrites the stale rmsnorm2
        #     output the last swiglu already consumed; the next step's first rmsnorm rewrites xn again).
        _mb_set_header(
            self.descriptors_decode_batched, d, self.prefill_pipeline_idx[_PFROLE_RMSNORM], B, _TG, 6,
        )
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.xn_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, self.final_norm_addr)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 3, self.d_model)
        _mb_set_arg_f32(self.descriptors_decode_batched, d, 4, self.eps)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 5, B)
        d += 1

        # (2) fused batched lm_head + per-vocab-slice argmax: reads xn [B, d_model], sweeps the
        #     embed/lm_head weight once, writes per-row blk_val/blk_idx [B, _LM_BLOCKS].
        _mb_set_header(
            self.descriptors_decode_batched, d, self.batched_lmhead_pipeline_idx, _LM_BLOCKS, _TG, 9,
        )
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.batch_blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.batch_blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, self.xn_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, self.embed_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 4, self.embed_scale_addr)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 5, B)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 6, self.d_model)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 7, self.vocab)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 8, n_iters)
        d += 1

        # (3) batched argmax reduce: one threadgroup per sequence row, collapses that row's
        #     _LM_BLOCKS (logit, id) pairs to out_val[row]/out_idx[row].
        _mb_set_header(
            self.descriptors_decode_batched, d, self.batched_argmax_reduce_pipeline_idx, B, _TG, 5,
        )
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 0, self.batch_out_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 1, self.batch_out_idx_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 2, self.batch_blk_val_addr)
        _mb_set_arg_ptr(self.descriptors_decode_batched, d, 3, self.batch_blk_idx_addr)
        _mb_set_arg_int(self.descriptors_decode_batched, d, 4, _LM_BLOCKS)
        d += 1

        if d != self.n_descriptors_decode_batched:
            raise Error(
                "metaldispatch: built " + String(d) + " decode-batched descriptors but the budget says "
                + String(self.n_descriptors_decode_batched) + ", status="
                + String(MB_ERR_DISPATCH_COUNT_MISMATCH)
            )
        self.decode_batched_B = B

    def _step_batched(
        mut self, token_ids: List[Int], poss: List[Int],
    ) raises -> List[Int]:
        """Steps B sequences together (B = len(token_ids) == len(poss)); returns B next tokens.
        Writes the per-sequence token/pos/n_keys state into the device buffers, submits the single
        batched descriptor table, and reads back B greedy tokens."""
        var B = len(token_ids)
        if len(poss) != B:
            raise Error("metaldispatch: _step_batched token_ids/poss length mismatch")
        self._ensure_decode_batched_ready(B)

        # per-sequence state into the device buffers the batched kernels read.
        var ids32 = self.prompt_ids_ptr.bitcast[Int32]()
        var poss64 = self.batch_poss_ptr.bitcast[Int64]()
        var nkeys64 = self.batch_nkeys_ptr.bitcast[Int64]()
        for b in range(B):
            ids32[b] = Int32(token_ids[b])
            poss64[b] = Int64(poss[b])
            nkeys64[b] = Int64(poss[b] + 1)

        var rc = _mb_run_token(self.descriptors_decode_batched, self.n_descriptors_decode_batched)
        if rc != 0:
            raise Error("metaldispatch: _step_batched dispatch failed, status=" + String(MB_ERR_DISPATCH_FAILED))

        var out_idx32 = self.batch_out_idx_ptr.bitcast[Int32]()
        var toks = List[Int](capacity=B)
        for b in range(B):
            var t = Int(out_idx32[b])
            if t < 0 or t >= self.vocab:
                raise Error("metaldispatch: _step_batched seq " + String(b) + " produced out-of-range token " + String(t))
            toks.append(t)
        return toks^

    def _step_native_kv_impl(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Project Redline reopening (2026-08-08): a NEW, additive decode entry point -- reads the
        native-packed F16 K/V buffers (`self.af_ck_native_addr`/`af_cv_native_addr`) via the new
        `attention_forge.native_kv_decode_attn._native_kv_decode_attn_kernel`, instead of `_step_
        legacy_impl`'s own natural F32 `ck`/`cv` cache. `_step_legacy_impl` itself is completely
        UNTOUCHED by this method's existence -- zero lines of it changed; this is a fully separate
        method dispatching a fully separate descriptor table (`self.descriptors_decode_native`),
        matching this file's own established "a new capability is a new method + a new table"
        precedent (`prefill_batch` itself, over plain per-token decode, was exactly this shape when
        it was first added). Renamed from the public `step_native_kv` (round 5, 2026-08-08) -- see
        this file's own module docstring addendum, round 5, for the full account of why the public
        `step()` router now calls this directly, and `step_native_kv` remains only as a thin,
        test-only public wrapper.

        CALLER OBLIGATION, stated precisely: this method never writes anything into `ck`/`cv` and
        never reads anything from them either -- it depends ENTIRELY on the native-packed buffers
        having already been populated for every position `< pos` by a PRIOR `prefill_batch()` call
        whose `self.plan.attention` resolved to `PF_ATTN_GROUPED_FA_WITH_MIRROR` OR `PF_ATTN_GROUPED_
        FA_NO_MIRROR` (either populates the native buffers identically; only the natural-cache mirror
        differs between them, and this method never looks at the mirror). Calling this method on an
        instance whose native buffers were never populated (e.g. one that only ever ran the OFF-path
        `prefill_batch()`, or an all-`_step_legacy_impl` decode loop) produces garbage, not a caught
        error -- the same class of caller obligation `_step_legacy_impl` itself already has toward
        `ck`/`cv` (nothing in this file validates that EITHER cache was ever actually written before a
        decode call reads it). The public `step()` router above closes the ONE way this obligation was
        previously left to an uninstructed caller (pairing this implementation's own required prefill
        path with the WRONG decode call) -- everything else about this caller obligation is unchanged.

        EACH CALL appends this token's own K/V into the native-packed buffers (via a fresh, `m_rows=1`
        dispatch of the SAME native-KV-producer kernel `prefill_batch`'s own AF tables use) BEFORE
        reading them back for attention -- so a sequence of calls at increasing `pos` grows the native
        cache exactly the way repeated `_step_legacy_impl` calls grow `ck`/`cv`, using the identical
        absolute-position addressing (`block = pos // key_block_size`, `kk = pos % key_block_size`)
        `prefill_batch`'s own multi-chunk continuation already relies on -- see `native_kv_producer.
        mojo`'s own module docstring item 4.

        Refuses with `MB_ERR_PIPELINE_NOT_FOUND` if `self.descriptors_decode_native` was never built
        (either forge blob missing -- see that field's own docstring for the exact guard), and with
        the same `MB_ERR_CONTEXT_FULL`/`MB_ERR_UPLOAD_LENGTH` bounds `_step_legacy_impl` itself already
        checks, for the same reasons."""
        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if (
                self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] < 0
                or self.native_decode_attn_pipeline_idx < 0
            ):
                return _StepOut(-1, 0.0, 0, MB_ERR_PIPELINE_NOT_FOUND)
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            var n_keys = pos + 1

            # ── Beat-llama.cpp campaign (2026-08-08 night): depth-gated dispatch of the split-K
            # table -- at and above `_NATIVE_DECODE_SPLITK_THRESHOLD` keys the flash-decoding pair
            # (partial+merge) replaces the naive single dispatch; below it -- or on any binary that
            # never linked the split-K blob (`native_decode_splitk_built` False) -- the naive table
            # runs, byte-unmodified. Both tables share every buffer this step reads or writes
            # EXCEPT the attention partials scratch, so the rest of this method is table-agnostic.
            var use_splitk = self.native_decode_splitk_built and n_keys >= _NATIVE_DECODE_SPLITK_THRESHOLD
            var table = self.descriptors_decode_native_splitk if use_splitk else self.descriptors_decode_native
            var n_descriptors = self.n_descriptors_decode_native_splitk if use_splitk else self.n_descriptors_decode_native
            var token_id_offset = self.token_id_offset_native_splitk if use_splitk else self.token_id_offset_native
            _mb_set_arg_int(table, token_id_offset, 3, token_id)
            for layer in range(self.n_layers):
                if use_splitk:
                    _mb_set_arg_int(table, self.pos_offsets_native_splitk[layer], 8, pos)
                    _mb_set_arg_int(table, self.nkeys_offsets_native_splitk[layer], 6, n_keys)
                else:
                    _mb_set_arg_int(table, self.pos_offsets_native[layer], 8, pos)
                    _mb_set_arg_int(table, self.nkeys_offsets_native[layer], 4, n_keys)

            var rc = _mb_run_token(table, n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, n_descriptors, MB_OK)

    # ── Parity gap 3 (sampling, 2026-08-10): logits-emitting twins of the two single-stream tail
    # paths. The greedy tail is two dispatches (fused lm_head+argmax over `_LM_BLOCKS` partials,
    # then the block reduce); the sampled tail is ONE dispatch -- `_lmhead_logits_kernel_simd_i8`,
    # byte-identical dot products, writing the whole vocab row into `self.logits_addr` -- and the
    # host-side sampler draws the token. Mechanism: the tail descriptor is PATCHED in place before
    # the run (header + all args, positional shift included) and RESTORED to the byte-exact argmax
    # wiring immediately after, so interleaving sampled and greedy calls on one session is safe and
    # the greedy path never sees a mutated descriptor.

    def _patch_tail_logits(mut self, table: UnsafePointer[UInt8, origin=MutAnyOrigin], d_lm: Int, x_addr: UInt64) raises:
        """Overwrite tail slot `d_lm` with the logits kernel's header + 9 args (logits first, then
        the argmax kernel's args minus blk_val/blk_idx). Caller restores via `_restore_tail_argmax`."""
        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(table, d_lm, self.lmhead_logits_pipeline_idx, _LM_BLOCKS, _TG, 9)
        _mb_set_arg_ptr(table, d_lm, 0, self.logits_addr)
        _mb_set_arg_ptr(table, d_lm, 1, x_addr)
        _mb_set_arg_ptr(table, d_lm, 2, self.final_norm_addr)
        _mb_set_arg_ptr(table, d_lm, 3, self.embed_addr)
        _mb_set_arg_ptr(table, d_lm, 4, self.embed_scale_addr)
        _mb_set_arg_int(table, d_lm, 5, self.d_model)
        _mb_set_arg_int(table, d_lm, 6, self.vocab)
        _mb_set_arg_f32(table, d_lm, 7, self.eps)
        _mb_set_arg_int(table, d_lm, 8, n_iters)

    def _restore_tail_argmax(mut self, table: UnsafePointer[UInt8, origin=MutAnyOrigin], d_lm: Int, x_addr: UInt64) raises:
        """Byte-exact restoration of the greedy tail (both descriptors) after a logits run -- the
        same header + arg values the table builders wrote at construction."""
        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(table, d_lm, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 10)
        _mb_set_arg_ptr(table, d_lm, 0, self.blk_val_addr)
        _mb_set_arg_ptr(table, d_lm, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(table, d_lm, 2, x_addr)
        _mb_set_arg_ptr(table, d_lm, 3, self.final_norm_addr)
        _mb_set_arg_ptr(table, d_lm, 4, self.embed_addr)
        _mb_set_arg_ptr(table, d_lm, 5, self.embed_scale_addr)
        _mb_set_arg_int(table, d_lm, 6, self.d_model)
        _mb_set_arg_int(table, d_lm, 7, self.vocab)
        _mb_set_arg_f32(table, d_lm, 8, self.eps)
        _mb_set_arg_int(table, d_lm, 9, n_iters)
        _mb_set_header(table, d_lm + 1, self.pipeline_idx[_ROLE_ARGMAX_REDUCE], 1, _TG, 5)
        _mb_set_arg_ptr(table, d_lm + 1, 0, self.out_val_addr)
        _mb_set_arg_ptr(table, d_lm + 1, 1, self.out_idx_addr)
        _mb_set_arg_ptr(table, d_lm + 1, 2, self.blk_val_addr)
        _mb_set_arg_ptr(table, d_lm + 1, 3, self.blk_idx_addr)
        _mb_set_arg_int(table, d_lm + 1, 4, _LM_BLOCKS)

    def _read_logits(self) raises -> List[Float64]:
        var lp = self.logits_ptr.bitcast[Float32]()
        var out = List[Float64](capacity=self.vocab)
        for i in range(self.vocab):
            out.append(Float64(lp[i]))
        return out^

    def step_logits(mut self, token_id: Int, pos: Int) raises -> _SampledOut:
        """The sampling twin of `_step_native_kv_impl`: byte-identical per-layer dispatch (same
        table selection, same scalar patches), with the tail swapped to the logits kernel and the
        trailing reduce dropped -- dispatches `n_descriptors - 1`, returns the full vocab row for
        the host sampler instead of an argmax token. Restores the greedy tail before returning,
        whatever the outcome."""
        @parameter
        if not MB_GPU_BUILD:
            return _SampledOut(List[Float64](), 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if self.lmhead_logits_pipeline_idx < 0:
                return _SampledOut(List[Float64](), 0, MB_ERR_PIPELINE_NOT_FOUND)
            if (
                self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] < 0
                or self.native_decode_attn_pipeline_idx < 0
            ):
                return _SampledOut(List[Float64](), 0, MB_ERR_PIPELINE_NOT_FOUND)
            if pos < 0 or pos >= self.max_ctx:
                return _SampledOut(List[Float64](), 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _SampledOut(List[Float64](), 0, MB_ERR_UPLOAD_LENGTH)

            var n_keys = pos + 1
            var use_splitk = self.native_decode_splitk_built and n_keys >= _NATIVE_DECODE_SPLITK_THRESHOLD
            var table = self.descriptors_decode_native_splitk if use_splitk else self.descriptors_decode_native
            var n_descriptors = self.n_descriptors_decode_native_splitk if use_splitk else self.n_descriptors_decode_native
            var token_id_offset = self.token_id_offset_native_splitk if use_splitk else self.token_id_offset_native
            _mb_set_arg_int(table, token_id_offset, 3, token_id)
            for layer in range(self.n_layers):
                if use_splitk:
                    _mb_set_arg_int(table, self.pos_offsets_native_splitk[layer], 8, pos)
                    _mb_set_arg_int(table, self.nkeys_offsets_native_splitk[layer], 6, n_keys)
                else:
                    _mb_set_arg_int(table, self.pos_offsets_native[layer], 8, pos)
                    _mb_set_arg_int(table, self.nkeys_offsets_native[layer], 4, n_keys)

            var d_lm = n_descriptors - 2
            self._patch_tail_logits(table, d_lm, self.hidden_addr)
            var rc = _mb_run_token(table, n_descriptors - 1)
            self._restore_tail_argmax(table, d_lm, self.hidden_addr)
            if rc != 0:
                return _SampledOut(List[Float64](), n_descriptors - 1, MB_ERR_DISPATCH_FAILED)
            var logits = self._read_logits()
            return _SampledOut(logits^, n_descriptors - 1, MB_OK)

    def prefill_batch_logits(mut self, prompt_ids: List[Int], pos_base: Int) raises -> _SampledOut:
        """The sampling twin of `prefill_batch` for the NO-MIRROR arm (the only arm the sampled
        entry point runs -- any other resolved plan is refused here, not silently sampled): runs
        the identical `descriptors_prefill_af_nomirror` table with the tail swapped to the logits
        kernel, so the FIRST generated token can be drawn from the same distribution as every later
        one. Restores the greedy tail before returning, whatever the outcome."""
        @parameter
        if not MB_GPU_BUILD:
            return _SampledOut(List[Float64](), 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            self._require_resolved_plan()
            if self.lmhead_logits_pipeline_idx < 0:
                return _SampledOut(List[Float64](), 0, MB_ERR_PIPELINE_NOT_FOUND)
            if self.plan.attention != PF_ATTN_GROUPED_FA_NO_MIRROR:
                return _SampledOut(List[Float64](), 0, MB_ERR_PIPELINE_NOT_FOUND)
            var m_rows = len(prompt_ids)
            if m_rows < 1 or m_rows > PREFILL_MAX_TILE:
                return _SampledOut(List[Float64](), 0, MB_ERR_UPLOAD_LENGTH)
            if pos_base < 0 or pos_base + m_rows > self.max_ctx:
                return _SampledOut(List[Float64](), 0, MB_ERR_CONTEXT_FULL)
            var ids_i32 = self.prompt_ids_ptr.bitcast[Int32]()
            for m in range(m_rows):
                var tid = prompt_ids[m]
                if tid < 0 or tid >= self.vocab:
                    return _SampledOut(List[Float64](), 0, MB_ERR_UPLOAD_LENGTH)
                ids_i32[m] = Int32(tid)

            self._apply_m_rows_af_nomirror(m_rows, pos_base)
            var last_row_addr = self.hidden_addr + UInt64((m_rows - 1) * self.d_model * 4)
            self._patch_tail_logits(self.descriptors_prefill_af_nomirror, self.lmhead_af2_d, last_row_addr)
            var rc = _mb_run_token(
                self.descriptors_prefill_af_nomirror, self.n_descriptors_prefill_af_nomirror - 1
            )
            self._restore_tail_argmax(self.descriptors_prefill_af_nomirror, self.lmhead_af2_d, last_row_addr)
            if rc != 0:
                return _SampledOut(
                    List[Float64](), self.n_descriptors_prefill_af_nomirror - 1, MB_ERR_DISPATCH_FAILED
                )
            var logits = self._read_logits()
            return _SampledOut(logits^, self.n_descriptors_prefill_af_nomirror - 1, MB_OK)

    def expected_decode_dispatch_count(self, n_keys: Int) -> Int:
        """Round 5 (2026-08-08): the single GENERATED source of truth a caller's own dispatch-count
        sanity check should compare against, for WHICHEVER decode path `self.plan.decode` resolved
        to -- replaces `metaldispatch.qwen3_prefill_decode`'s own previously-separately-maintained
        formula (`metaldispatch_dispatch_budget(n_layers)` / `residentk_dispatch_budget_deep(
        n_layers)`, chosen by re-deriving `residentk_splitk_should_split(n_keys)` itself), which round
        4's own adversarial pass found silently wrong for the native-KV path specifically (`_step_
        native_kv_impl`'s own table has NO split-K variant at all -- applying that formula to it would
        raise a guaranteed false-positive `MB_ERR_DISPATCH_COUNT_MISMATCH` once `n_keys` crosses the
        split-K threshold, even though the actual dispatch count never changes for that path).

        Reads straight off THIS struct's own `self.n_descriptors`/`self.n_descriptors_deep`/`self.
        n_descriptors_decode_native` fields -- each one already set, once, in `__init__`, to the exact
        value its own descriptor-table BUILDER (`_build_descriptors`/`_build_descriptors_deep`/
        `_build_descriptors_decode_native`) self-checks the actual encoded dispatch count against at
        BUILD time (every one of those three methods already `raise`s if what it built does not match
        the field this method reads -- see each one's own tail, `MB_ERR_DISPATCH_COUNT_MISMATCH`).
        There is therefore no second, independently-typed formula anywhere left to drift away from
        what a descriptor builder actually does, for either decode path -- a future third decode path
        only ever needs one more branch here, reading THAT path's own already-self-checked field,
        never a new formula.

        `n_keys` is consulted ONLY for `DECODE_PATH_LEGACY_NATURAL_KV` (`_step_legacy_impl`'s own
        dynamic split-K switch, `residentk_splitk_should_split`) -- `DECODE_PATH_NATIVE_PACKED_KV`'s
        own table (`_step_native_kv_impl`) has no split-K variant at all, so this returns `self.
        n_descriptors_decode_native` unconditionally for it, regardless of `n_keys`."""
        if self.plan.decode == DECODE_PATH_NATIVE_PACKED_KV:
            # Beat-llama.cpp campaign (2026-08-08 night): ...EXCEPT when the split-K decode table
            # was actually built AND this depth crosses its threshold -- then `_step_native_kv_impl`
            # dispatches `self.n_descriptors_decode_native_splitk` (one MORE dispatch per layer:
            # partial+merge replacing the naive single dispatch), and this generated source of
            # truth reports exactly that. Binaries without the split-K blob keep `native_decode_
            # splitk_built` False and the naive count at every depth, byte-identical to before.
            if self.native_decode_splitk_built and n_keys >= _NATIVE_DECODE_SPLITK_THRESHOLD:
                return self.n_descriptors_decode_native_splitk
            return self.n_descriptors_decode_native
        if residentk_splitk_should_split(n_keys):
            return self.n_descriptors_deep
        return self.n_descriptors

    def prefill_batch(mut self, prompt_ids: List[Int], pos_base: Int) raises -> _StepOut:
        """Processes `len(prompt_ids)` prompt tokens in `self.n_descriptors_prefill` dispatches
        total -- see module docstring. Writes KV-cache slots `[pos_base, pos_base + m_rows)`; a
        subsequent `step()` call on this SAME instance continues correctly from `pos = pos_base +
        m_rows` (`step()` always overwrites `hidden`'s row 0 with the new token's own embedding as
        its first act, so this method leaves no state `step()` depends on beyond the KV cache and
        the per-layer weights it already shared with `step()` from `__init__` onward).

        Returns the token id predicted immediately after the whole prompt (row `m_rows - 1`'s own
        lm_head/argmax result) -- exactly the same `_StepOut` shape `step()` returns, so a driver's
        decode loop can treat this call's return value as "the first generated token" and proceed
        with ordinary `step()` calls from there.

        Attention Compiler Plan v1.0, Phase 2C addendum: when `self.plan.attention` resolves to
        `PF_ATTN_GROUPED_FA_WITH_MIRROR`, this method submits the SEPARATE `self.descriptors_
        prefill_af` table (native-KV-producer + a natural-cache double-write + Candidate A's
        attention, per layer) instead of `self.descriptors_prefill` (`_pf_ropewrt_kernel` + `_pf_
        attn_tiled_kernel_simd`) -- every other role, and every buffer none of those roles touch, is
        identical either way.

        DECODE-AFTER-AF-PREFILL GAP, CLOSED (was: a known, itemized, NOT-yet-closed gap in PR #599):
        this method's own AF table now ALSO dispatches `_pf_ropewrt_kernel` a second time per layer
        (`self.kvprod_mirror_af_d`, see its own field docstring) purely to populate `self.
        layers[layer].ck_addr`/`cv_addr` (the F32 natural-layout cache `step()` reads) -- a
        double-write alongside the native-KV-producer's own F16 native-packed write, not a
        replacement of it. `step()` itself is completely unmodified and still always reads `ck`/
        `cv` unconditionally, regardless of `self.plan.attention`; it now finds them correctly
        populated after an AF-enabled call, exactly as it always has after an OFF-path call. Proven
        by `test_metaldispatch_session_prefill_af.mojo`'s Gate C: a FRESH instance resolved to this
        path before its first `prefill_batch()` call, followed by real `step()` decode calls,
        matches an independent CPU Float64 oracle computed over the full prompt + generated-token
        sequence -- see that test for the exact scenario and tolerance.

        Precisely what remains unverified, so this is not overclaimed: this method's OWN handling of
        a SECOND `prefill_batch()` call with `pos_base > 0` on an AF-enabled instance (multi-chunk AF
        continuation), followed by decode, has not been exercised end-to-end through this exact
        wired path -- only the underlying kernels' own multi-call continuation (Phase 2B's `native_
        kv_producer_driver.mojo`, and `_pf_ropewrt_kernel`'s own long-standing decode-cache
        precedent) is separately verified. Single-chunk AF prefill (`pos_base=0`) followed by decode
        is the scenario this fix is proven for.

        Project Redline reopening (2026-08-08) addendum: when `self.plan.attention` resolves to
        `PF_ATTN_GROUPED_FA_NO_MIRROR` instead, this method submits `self.descriptors_prefill_af_
        nomirror` -- structurally identical to `self.descriptors_prefill_af` except it never
        dispatches the natural-cache double-write, so `ck`/`cv` are left untouched (not merely stale
        from a previous call -- genuinely never written by THIS table). Round 5 (2026-08-08): the
        public `step()` reads `self.plan.decode` (`DECODE_PATH_NATIVE_PACKED_KV` for this attention
        path) and routes to `_step_native_kv_impl` automatically -- see that method's own docstring
        for the full caller-obligation account this pairing still carries. Multi-chunk continuation
        (`pos_base > 0`) through THIS table is
        exercised by `test_metaldispatch_session_prefill_native_decode.mojo`'s own multi-chunk gate,
        unlike the with-mirror table's own scope limit stated in the paragraph above.

        Resolved-execution-plan refactor (2026-08-08): `self.plan.attention` is a SINGLE, ALREADY-
        VALIDATED value -- `resolve_prefill_execution_plan` (called once by `__init__`, and again by
        any later `self.resolve_plan(...)` call) already degraded a request for either grouped-FA
        path down to `PF_ATTN_OFF` if this binary never linked the two required `attention_forge/`
        blobs, and already degraded `self.plan.gemm` similarly. THIS method therefore never
        re-checks `self.af_pipeline_idx[...]` itself, and never needs the graceful-fallback `if
        flag and pipelines-available` pattern the old two-boolean version needed at this exact spot
        (the Sector-1 promotion-decision fix, and the second, flag-precedence regression it in turn
        exposed once a second overlapping boolean was added -- both closed by construction here:
        there is exactly ONE `self.plan.attention` value, so there is no second candidate's own
        stale default left to silently outrank an explicit request). Dispatch is a plain three-way
        `if`/`elif`/`else` on that one value, below.

        "MAKE UNRESOLVED PLAN STATE UNREPRESENTABLE" (2026-08-08): calls `self._require_resolved_
        plan()` FIRST, before that three-way branch reads `self.plan` at all -- see that method's
        own docstring for exactly what this defends against (a direct `session.plan = ...` field
        assignment bypassing `resolve_plan` entirely; construction and `resolve_plan` themselves
        already always leave `self.plan` genuinely resolved, so this is not expected to ever
        actually raise in ordinary use)."""
        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            self._require_resolved_plan()
            var m_rows = len(prompt_ids)
            if m_rows < 1 or m_rows > PREFILL_MAX_TILE:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)
            if pos_base < 0 or pos_base + m_rows > self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            var ids_i32 = self.prompt_ids_ptr.bitcast[Int32]()
            for m in range(m_rows):
                var tid = prompt_ids[m]
                if tid < 0 or tid >= self.vocab:
                    return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)
                ids_i32[m] = Int32(tid)

            if self.plan.attention == PF_ATTN_GROUPED_FA_NO_MIRROR:
                self._apply_m_rows_af_nomirror(m_rows, pos_base)
                var rc_af2 = _mb_run_token(self.descriptors_prefill_af_nomirror, self.n_descriptors_prefill_af_nomirror)
                if rc_af2 != 0:
                    return _StepOut(-1, 0.0, self.n_descriptors_prefill_af_nomirror, MB_ERR_DISPATCH_FAILED)

                var tok_af2 = Int(self.out_idx_ptr.bitcast[Int32]()[0])
                var lg_af2 = Float64(self.out_val_ptr.bitcast[Float32]()[0])
                if tok_af2 < 0 or tok_af2 >= self.vocab:
                    return _StepOut(-1, 0.0, self.n_descriptors_prefill_af_nomirror, MB_ERR_DISPATCH_FAILED)
                return _StepOut(tok_af2, lg_af2, self.n_descriptors_prefill_af_nomirror, MB_OK)

            if self.plan.attention == PF_ATTN_GROUPED_FA_WITH_MIRROR:
                self._apply_m_rows_af(m_rows, pos_base)
                var rc_af = _mb_run_token(self.descriptors_prefill_af, self.n_descriptors_prefill_af)
                if rc_af != 0:
                    return _StepOut(-1, 0.0, self.n_descriptors_prefill_af, MB_ERR_DISPATCH_FAILED)

                var tok_af = Int(self.out_idx_ptr.bitcast[Int32]()[0])
                var lg_af = Float64(self.out_val_ptr.bitcast[Float32]()[0])
                if tok_af < 0 or tok_af >= self.vocab:
                    return _StepOut(-1, 0.0, self.n_descriptors_prefill_af, MB_ERR_DISPATCH_FAILED)
                return _StepOut(tok_af, lg_af, self.n_descriptors_prefill_af, MB_OK)

            self._apply_m_rows(m_rows, pos_base)

            var rc = _mb_run_token(self.descriptors_prefill, self.n_descriptors_prefill)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors_prefill, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors_prefill, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors_prefill, MB_OK)
