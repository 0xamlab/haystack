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
    _argmax_reduce_kernel_simd,
    _splitk_partial_kernel_simd_native,
    _splitk_merge_kernel_simd,
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

    var prompt_ids_addr: UInt64
    var prompt_ids_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]

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
    var use_native_grouped_fa_attn: Bool
    """Default `False`, following `metaldispatch.session._apply_n_splits`-adjacent `use_block8_attn`'s
    own established precedent in THIS file (`_apply_m_rows`, a hardcoded, source-level toggle, not a
    constructor parameter) for what a not-yet-unconditionally-shipped attention lever looks like in
    this codebase -- except this one DOES need to be a real struct field (not a local var scoped to
    one method): unlike `use_block8_attn` (which only ever repoints ONE existing, signature-compatible
    descriptor slot inside `_apply_m_rows`), Candidate A's kernel is NOT signature-compatible with the
    existing attention path (F16 not F32 Q/K/V, an `lse` scratch buffer the old path has no use for,
    and a whole EXTRA per-layer dispatch for the native-KV-producer that has no old-path equivalent at
    all) -- so this flag must be visible to BOTH `_apply_m_rows_af` (narrows the alternate table) AND
    `prefill_batch` (decides which of the two complete descriptor tables to submit), which a
    method-local variable cannot be. Hardcoded `False` in `__init__` below, exactly like every other
    `use_*` toggle in this file (`use_mma`, `use_narrow`, `use_block8_attn`) -- flipping it means
    editing this source and rebuilding, never a runtime setter, matching this file's own established
    discipline for a lever that has not yet won its own unconditional-default promotion.

    DECODE-AFTER-AF-PREFILL GAP, CLOSED: this flag originally shipped (PR #599) with a documented,
    itemized gap -- setting it `True` made `prefill_batch` populate ONLY the F16 native-packed K/V
    buffers, never the natural F32 `ck`/`cv` cache `step()` (decode) reads, so a decode call after an
    AF-enabled prefill read stale/uninitialized cache and produced wrong tokens. `self.descriptors_
    prefill_af` now carries a THIRD per-layer dispatch (`self.kvprod_mirror_af_d`, see its own field
    docstring) that double-writes `ck`/`cv` via the byte-unmodified `_pf_ropewrt_kernel` every
    `prefill_batch(use_native_grouped_fa_attn=True)` call -- `step()` itself is completely untouched,
    still always reading `self.layers[layer].ck_addr`/`cv_addr` exactly as it always has, and now
    finds them correctly populated. Proven by `test_metaldispatch_session_prefill_af.mojo`'s Gate C:
    a session with this flag set `True` BEFORE its first `prefill_batch()` call, followed by real
    `step()` decode calls, matches an independent CPU Float64 oracle computed over the full prompt +
    generated-token sequence. Scope of what is proven: single-chunk prefill (`pos_base=0`) followed by
    decode. NOT separately verified by that test: multi-chunk AF prefill (`prefill_batch` called more
    than once with increasing `pos_base` on one AF-enabled instance) followed by decode -- the
    underlying kernels' own multi-call continuation is verified (Phase 2B's `native_kv_producer_
    driver.mojo`, `_pf_ropewrt_kernel`'s own decode-cache precedent), but the full wired multi-chunk-
    then-decode sequence through THIS struct has not been exercised end-to-end."""
    var af_pipeline_idx: List[Int]
    """Sized `_AF_N_ROLES` (2), resolved via `_classify_attention_forge_pipeline` during pipeline
    discovery below -- UNLIKE `self.pipeline_idx`/`self.prefill_pipeline_idx`, a `-1` entry here is
    NOT fatal at construction time (see `_classify_attention_forge_pipeline`'s own docstring in
    `metaldispatch.session` for why): every EXISTING benchmark/production binary that instantiates
    this struct without linking the two `attention_forge/` blobs must keep constructing successfully,
    with both entries `-1` and `self.use_native_grouped_fa_attn` staying `False` (its own hardcoded
    default) -- this pair is optional, additive capability, never a new required dependency."""
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

    var descriptors_prefill_af: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors_prefill_af: Int
    """A COMPLETE, SEPARATE descriptor table -- never a partial overlay onto `self.descriptors_
    prefill` -- built only if BOTH `self.af_pipeline_idx` entries were discovered (`> 0` here implies
    that; `0` means the two `attention_forge/` blobs were not linked into this binary, and
    `prefill_batch` must refuse `use_native_grouped_fa_attn=True` with a clear error rather than
    dispatch a table that was never populated). `1 + n_layers*9 + 2` dispatches -- ONE MORE per layer
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

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
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

        # ── Attention Compiler Plan v1.0, Phase 2C: hardcoded OFF by default -- see this field's
        # own docstring above for why this is a struct field (not a `_apply_m_rows`-local var like
        # `use_block8_attn`) and why flipping it means editing this line and rebuilding, not a
        # runtime setter.
        self.use_native_grouped_fa_attn = False
        self.af_n_blocks = (max_ctx + _AF_KEY_BLOCK_SIZE - 1) // _AF_KEY_BLOCK_SIZE

        # ── resident buffers: SAME shapes as `_MBQwen3I8AllSimd7` for weights/KV-cache/globals.
        var n_qkv = self.n_qkv
        var n_pairs = d_head // 2

        self.af_ck_native_addr = List[UInt64]()
        self.af_ck_native_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()
        self.af_cv_native_addr = List[UInt64]()
        self.af_cv_native_ptr = List[UnsafePointer[UInt8, origin=MutAnyOrigin]]()

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
            # regardless of `self.use_native_grouped_fa_attn`, per this struct's own documented
            # choice to always allocate the AF buffers and simply never populate/dispatch them when
            # the flag is off (see `self.af_ck_native_addr`'s own field docstring). Same total
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
        self.n_descriptors_prefill_af = 1 + self.n_layers * 9 + 2
        self.descriptors_prefill_af = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.embed_af_d = -1
        self.rmsnorm_af_d = List[Int]()
        self.gemm_assign_af_d = List[Int]()
        self.kvprod_af_d = List[Int]()
        self.kvprod_mirror_af_d = List[Int]()
        self.attn_af_d = List[Int]()
        self.gemv_o_af_d = List[Int]()
        self.rmsnorm2_af_d = List[Int]()
        self.swiglu_af_d = List[Int]()
        self.gemv_down_af_d = List[Int]()
        self.lmhead_af_d = -1

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

            # ── NEW role: native-KV-producer, replaces `ropewrt`. 16 args -- see `native_kv_
            # producer.mojo`'s own `_native_kv_producer_kernel` signature for the exact order.
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

    def _apply_m_rows_af(mut self, m_rows: Int, pos_base: Int) raises:
        """AF-table twin of `_apply_m_rows` -- narrows every M-scaled descriptor in `self.
        descriptors_prefill_af` to `m_rows`'s real grid width and patches every `m_rows`/`pos_base`
        scalar argument, restated for the SEPARATE AF table (see that table's own field docstring
        for why it is separate). Deliberately mirrors `_apply_m_rows`'s own GEMM-tiling policy choice
        (`use_mma`/`use_narrow`) byte-for-byte, so the ONLY variable this table's own existence
        isolates is the attention-dispatch change itself -- the Attention Compiler Plan v1.0's own
        "never combine multiple ablations into one measurement" discipline (stop rule 5). Only ever
        called from `prefill_batch`, and only when `self.use_native_grouped_fa_attn` is `True` AND
        this table was actually built -- see that method's own guard."""
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
            self.descriptors_prefill_af, self.embed_af_d, self.prefill_pipeline_idx[_PFROLE_EMBED],
            n_units_embed * m_rows, _TG, 6,
        )
        _mb_set_arg_int(self.descriptors_prefill_af, self.embed_af_d, 5, m_rows)

        for layer in range(self.n_layers):
            var d_norm = self.rmsnorm_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_norm, self.prefill_pipeline_idx[_PFROLE_RMSNORM],
                m_rows, _TG, 6,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_norm, 5, m_rows)

            var d_gemm = self.gemm_assign_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_gemm, pf_assign,
                n_tile_rows_qkv * n_tile_cols_qkv, gemm_nthreads, 7,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_gemm, 4, m_rows)

            var d_kv = self.kvprod_af_d[layer]
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
                n_tile_rows_qkv * n_tile_cols_gemv, gemm_nthreads, 7,
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
                n_tile_rows_qkv * n_tile_cols_ff, gemm_nthreads, 7,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_sw, 4, m_rows)

            var d_gd = self.gemv_down_af_d[layer]
            _mb_set_header(
                self.descriptors_prefill_af, d_gd, pf_accum,
                n_tile_rows_qkv * n_tile_cols_gemv, gemm_nthreads, 7,
            )
            _mb_set_arg_int(self.descriptors_prefill_af, d_gd, 4, m_rows)

        var last_row_addr = self.hidden_addr + UInt64((m_rows - 1) * self.d_model * 4)
        _mb_set_arg_ptr(self.descriptors_prefill_af, self.lmhead_af_d, 2, last_row_addr)

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
        return MB_OK

    def seal(mut self) -> Int:
        return MB_OK

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-identical to `_MBQwen3I8AllSimd7.step` -- see that method's own docstring. Untouched
        by this struct's own `prefill_batch()` addition: reads/writes exactly row 0 of every
        activation buffer, regardless of how many rows `prefill_batch()` most recently used."""
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

        Attention Compiler Plan v1.0, Phase 2C addendum: when `self.use_native_grouped_fa_attn` is
        `True` (default `False` -- see that field's own docstring), this method submits the SEPARATE
        `self.descriptors_prefill_af` table (native-KV-producer + a natural-cache double-write +
        Candidate A's attention, per layer) instead of `self.descriptors_prefill` (`_pf_ropewrt_
        kernel` + `_pf_attn_tiled_kernel_simd`) -- every other role, and every buffer none of those
        roles touch, is identical either way.

        DECODE-AFTER-AF-PREFILL GAP, CLOSED (was: a known, itemized, NOT-yet-closed gap in PR #599):
        this method's own AF table now ALSO dispatches `_pf_ropewrt_kernel` a second time per layer
        (`self.kvprod_mirror_af_d`, see its own field docstring) purely to populate `self.
        layers[layer].ck_addr`/`cv_addr` (the F32 natural-layout cache `step()` reads) -- a
        double-write alongside the native-KV-producer's own F16 native-packed write, not a
        replacement of it. `step()` itself is completely unmodified and still always reads `ck`/
        `cv` unconditionally, regardless of `self.use_native_grouped_fa_attn`; it now finds them
        correctly populated after an AF-enabled call, exactly as it always has after an OFF-path
        call. Proven by `test_metaldispatch_session_prefill_af.mojo`'s Gate C: a FRESH instance with
        this flag set `True` before its first `prefill_batch()` call, followed by real `step()`
        decode calls, matches an independent CPU Float64 oracle computed over the full prompt +
        generated-token sequence -- see that test for the exact scenario and tolerance.

        Precisely what remains unverified, so this is not overclaimed: this method's OWN handling of
        a SECOND `prefill_batch()` call with `pos_base > 0` on an AF-enabled instance (multi-chunk AF
        continuation), followed by decode, has not been exercised end-to-end through this exact
        wired path -- only the underlying kernels' own multi-call continuation (Phase 2B's `native_
        kv_producer_driver.mojo`, and `_pf_ropewrt_kernel`'s own long-standing decode-cache
        precedent) is separately verified. Single-chunk AF prefill (`pos_base=0`) followed by decode
        is the scenario this fix is proven for."""
        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
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

            if self.use_native_grouped_fa_attn:
                if (
                    self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] < 0
                    or self.af_pipeline_idx[_AFROLE_GROUPED_FA_ATTN] < 0
                ):
                    return _StepOut(
                        -1, 0.0, 0,
                        MB_ERR_PIPELINE_NOT_FOUND,
                    )
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
