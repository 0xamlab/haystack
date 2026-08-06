"""qwen3_probe_splitk_native_sweep.mojo — MEASUREMENT-ONLY calibration sweep for the native
single-SIMD-group split-K kernel's `n_splits` choice, across MULTIPLE depth buckets, on this
machine's REAL production kernel/dispatch code -- never a scratch/throwaway kernel.

Built for the "genuinely dynamic split policy" investigation that follows PR #523 (`_ATTN_SPLITK_
N_SPLITS_NATIVE = 80`, tuned at ONE depth, `n_keys=4000`, only): that constant's own docstring
already sweeps 21 candidates but ONLY at `n_keys=4000`; this file sweeps a similar candidate set at
EIGHT depth buckets (`128, 256, 500, 750, 1000, 2000, 4000, 8000`), several repeated rounds each, so
the Policy phase has real per-depth optima to fit a formula/table to, not one point.

WHY ONE BUILD SUFFICES FOR THE WHOLE SWEEP (no rebuild per `n_splits` candidate)
------------------------------------------------------------------------------------
`_splitk_partial_kernel_simd_native` and `_splitk_merge_kernel_simd` (`residentk.kernels`, both
byte-unmodified by this file) take `n_splits` as a plain RUNTIME `Int` argument, never a compile-time
template parameter -- only `metaldispatch.session._MBQwen3I8AllSimd6`'s own HOST-SIDE dispatch code
bakes `_ATTN_SPLITK_N_SPLITS_NATIVE` in as a `comptime` for convenience (grid width + scratch-buffer
sizing). `_MBQwen3I8SplitKSweep` below (additive, this file only, not imported anywhere else) is
`_MBQwen3I8AllSimd6` with that one convenience un-done: `n_splits_max` is a constructor argument
(scratch buffers sized for the LARGEST candidate up front), and `set_n_splits` cheaply repatches the
split dispatch's grid width and both kernels' `n_splits` value arguments for every layer, in place,
between candidates -- see that struct's own docstring for the full account, including exactly which
bytes `_mb_set_header` touches (never the argument area) and why a smaller `new_n_splits` can never
overrun a buffer sized for a larger `n_splits_max`.

`_MBQwen3I8AllSimd6`, `_ATTN_SPLITK_N_SPLITS_NATIVE`, `_ATTN_SPLITK_THRESHOLD`, and every kernel in
`residentk.kernels` are untouched by this file's existence -- purely additive scratch tooling in
`benchmarks/llm_smoke/`, matching this task's own instruction.

Methodology, reusing `qwen3_probe_counters_i8_allsimd6_splitk_deepctx.mojo`'s own GPU-counter
machinery unchanged (same `batch_shim_counters.m`, same calibration, same "one command buffer, one
encoder, one commit, one wait" discipline -- see that file's own module docstring for the full
account of why this is real GPU-side time, not a host/GPU sync artifact): for every `(n_splits,
depth)` pair below, `N_ROUNDS` independent rounds, each round averaging `N_SAMPLES` dispatch-and-
sample repetitions, reporting `splitk_partial`'s and `splitk_merge`'s own summed-over-28-layers GPU
time in milliseconds. `depth` here means `n_keys` exactly (`pos = depth - 1`, `n_keys = pos + 1`).

    cd /Users/angel/Developer/decision-engine/mojo_env
    clang -c -fobjc-arc -O2 <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/batch_shim_counters.m \
        -o /tmp/batch_shim_counters.o
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer \
      pixi run mojo build -D ALGENTA_GPU -I <worktree>/mojo/engine \
        <worktree>/benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_splitk_native_sweep.mojo \
        -o /tmp/probe_splitk_sweep \
        -Xlinker /tmp/batch_shim_counters.o -Xlinker -framework -Xlinker Metal \
        -Xlinker -framework -Xlinker Foundation
    DEVELOPER_DIR=/Applications/Xcode-26.6.0.app/Contents/Developer /tmp/probe_splitk_sweep
"""

from std.ffi import external_call
from std.memory import alloc
from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import WARP_SIZE
from std.sys import argv, has_accelerator
from std.time import perf_counter_ns
from json.parser import json_get_array, json_get_float, json_get_int, json_get_object, json_array_tokens
from conv import parse_int
from attnk.rope import rope_table
from attnk.contract import ATTN_OK
from residentk.contract import RESIDENT_DEFAULT_CONTEXT
from residentk.kernels import (
    _TG,
    _SUBS,
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
)
from metaldispatch.contract import (
    MB_ERR_BUFFER_ALLOC_FAILED,
    MB_ERR_CONTEXT_FULL,
    MB_ERR_DISPATCH_COUNT_MISMATCH,
    MB_ERR_DISPATCH_FAILED,
    MB_ERR_NO_DEVICE,
    MB_ERR_PIPELINE_NOT_FOUND,
    MB_ERR_SESSION_OPEN_FAILED,
    MB_ERR_SHADER_TOOLCHAIN_ABSENT,
    MB_ERR_UPLOAD_LENGTH,
    MB_OK,
    metaldispatch_dispatch_budget,
    metaldispatch_status_name,
)
from metaldispatch.ffi import (
    _mb_alloc_buffer,
    _mb_alloc_descriptors,
    _mb_open_session,
    _mb_pipeline_count,
    _mb_pipeline_name,
    _mb_run_token,
    _mb_set_arg_f32,
    _mb_set_arg_int,
    _mb_set_arg_ptr,
    _mb_set_header,
    MB_DESC_STRIDE,
)
from metaldispatch.session import (
    _MBLayerBufI8,
    _StepOut,
    _classify_pipeline,
    _classify_splitk_pipeline,
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
    _LM_BLOCKS,
    _ATTN_SPLITK_THRESHOLD,
    MB_GPU_BUILD,
    _mb_preflight,
)

comptime MANIFEST_PATH: String = "/tmp/qwen3smoke/manifest.json"
comptime BLOB_PATH: String = "/tmp/qwen3smoke/weights.blob"


struct _MBQwen3I8SplitKSweep(Movable):
    """Scratch calibration-sweep twin of `_MBQwen3I8AllSimd6` (`metaldispatch.session`), built for
    `qwen3_probe_splitk_native_sweep.mojo` -- NOT a production struct, not imported by anything else,
    additive-only, and `metaldispatch.session`/`residentk.kernels` are byte-unmodified by this file's
    existence. Identical to `_MBQwen3I8AllSimd6` in every respect (same fields, same `__init__` body,
    same `_build_descriptors_deep` plan dispatching `_splitk_partial_kernel_simd_native` +
    `_splitk_merge_kernel_simd`, same lazy `_ensure_deep_initialized`) EXCEPT:

    1. A new `n_splits_max: Int` constructor parameter replaces the comptime `_ATTN_SPLITK_N_SPLITS_
       NATIVE` constant everywhere it drove a RUNTIME quantity (the three scratch buffers' sizes, the
       split dispatch's initial grid width, the `n_splits` value arguments) -- the buffers are
       allocated once, big enough for the LARGEST `n_splits` this sweep will ever request.
    2. A new `set_n_splits(mut self, new_n_splits: Int)` method (below `_build_descriptors_deep`)
       cheaply repatches the split dispatch's grid width and the two kernels' `n_splits` value
       arguments for every layer, in place, without reallocating or rebuilding anything else -- safe
       for any `new_n_splits <= n_splits_max`, since it only ever asks for FEWER (head, split) slots
       than the buffers were sized for. This is what lets one binary sweep many `n_splits` candidates
       without a rebuild per candidate, matching `_ATTN_SPLITK_N_SPLITS_NATIVE`'s own docstring's
       account of how 80 was originally found (temporarily overridden per candidate and rebuilt) but
       collapsing the "rebuild" step into a cheap in-place descriptor patch instead, since `n_splits`
       is already a plain runtime `Int` argument to both kernels, never a compile-time template
       parameter -- nothing about the kernels themselves needs to change for this to be sound.

    `_MBQwen3I8AllSimd6` and every kernel it dispatches remain completely untouched; this struct reads
    the same imported pipeline-classification/quantization/descriptor helpers `metaldispatch.session`
    already exports and re-derives nothing.
    """

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
    var n_splits_max: Int

    var pipeline_idx: List[Int]

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

    var descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var n_descriptors: Int
    var token_id_offset: Int
    var pos_offsets: List[Int]
    var nkeys_offsets: List[Int]

    var pipeline_idx_split: Int
    var pipeline_idx_merge: Int
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
    """See `_ATTN_SPLITK_THRESHOLD`'s own docstring, `_ensure_deep_initialized`'s, and this struct's
    `step()` for the full account of the fields above `descriptors_deep` onward: a SECOND, fully
    independent, fixed descriptor table built once, LAZILY (on the first `step()` call that crosses
    `_ATTN_SPLITK_THRESHOLD`, via `_ensure_deep_initialized`, guarded by `deep_ready`) — never a
    replacement for `descriptors`, and never built at all for a session that stays shallow its whole
    life. `step()` picks WHICH table to patch-and-submit each call based on the CURRENT `n_keys`; the
    other table's stale contents from a previous call simply do not matter until it is chosen again,
    at which point its own `pos`/`n_keys` slots are repatched fresh before submission — the same
    "mutate this step's arguments into an already-built plan" discipline `step()`'s pre-existing
    `pos_offsets`/`nkeys_offsets` patching already relies on, just duplicated across two plans instead
    of one."""

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64, n_splits_max: Int,
    ) raises:
        """REFUSES a `d_head` that is not an exact multiple of `std.gpu.WARP_SIZE` (32 on this
        Apple GPU target), BEFORE any GPU work happens — see `_MBQwen3I8AllSimd.__init__`'s own
        docstring for why: `_sdpa_kernel_simd`'s two-level reduction assumes every `d_head /
        WARP_SIZE` SIMD-group launched is FULLY populated, unaffected by this struct's own
        lm_head-simd and argmax-reduce-simd changes (the latter's own SIMD-group reduction is over
        `_TG = 256` threads fixed at compile time, not `d_head`, so it never needed this refusal on
        its own account — restated here only because this struct inherits the SDPA-simd role's
        requirement unchanged). `_splitk_partial_kernel_simd_native`'s own per-key SIMD-group
        reduction inherits a MODIFIED form of the identical requirement: it needs `d_head` to be a
        POSITIVE multiple of `WARP_SIZE` (its `d_head / WARP_SIZE` elements-per-lane mapping has no
        meaning otherwise), which this exact check already provides -- see that kernel's own
        docstring, "GENERALITY GAP" paragraph, for why no separate, kernel-specific refusal is needed.
        """
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8SplitKSweep: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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
        self.n_splits_max = n_splits_max

        # ── force every kernel THIS ARM needs to be compiled + embedded in THIS binary's
        # __TEXT,__const — the int8 GEMV-shaped twins, the lm_head-simd twin, the argmax-reduce-simd
        # twin, plus the two kernels with no per-dtype variant. Deliberately NEVER the
        # Float32/Float16 GEMV-shaped kernels, NOR the barrier-tree `_lmhead_argmax_kernel_i8`, NOR
        # the barrier-tree `_argmax_reduce_kernel` — see the struct docstring.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel_simd]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel_simd]()
        # ── the deep-context occupancy fix's two kernels are DELIBERATELY NOT compiled here.
        # `_ensure_deep_initialized` (below) calls `compile_function_unchecked` on both, lazily, the
        # first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` -- see that method's own
        # docstring for why. This does NOT remove either kernel from THIS binary: both are still
        # referenced by a `compile_function_unchecked[...]` call reachable from this struct (just a
        # later one), which is all the whole-program build needs to embed their `.metallib` blobs in
        # `__TEXT,__const` -- see this file's own module docstring ("The pipeline table is discovered
        # by NAME, not by call order") for why deferring WHEN this Mojo statement executes changes
        # neither which pipelines `_mb_open_session` below discovers nor their names, only when the
        # (measured, real, ~71.5us for both) cost of the two calls themselves is paid.

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        self.pipeline_idx_split = -1
        self.pipeline_idx_merge = -1
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
            # `_classify_splitk_pipeline` scans the SAME discovered-pipeline list, entirely
            # independently of `_classify_pipeline`/`_N_ROLES` above — see that function's own
            # docstring for why the two roles it resolves are never folded into the shared list.
            var splitk_role = _classify_splitk_pipeline(name)
            if splitk_role == 0:
                self.pipeline_idx_split = i
            elif splitk_role == 1:
                self.pipeline_idx_merge = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )
        if self.pipeline_idx_split < 0 or self.pipeline_idx_merge < 0:
            raise Error(
                "metaldispatch: _MBQwen3I8SplitKSweep attn-splitk pipeline(s) not found among "
                + String(count) + " discovered pipelines (split=" + String(self.pipeline_idx_split)
                + " merge=" + String(self.pipeline_idx_merge) + "), status="
                + String(MB_ERR_PIPELINE_NOT_FOUND)
            )

        # ── resident buffers: SAME shapes as _MBQwen3I8AllSimd.
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_MBLayerBufI8]()
        for _ in range(n_layers):
            var ln1a = UInt64(0); var ln1p = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var ln2a = UInt64(0); var ln2p = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var qna = UInt64(0); var qnp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var kna = UInt64(0); var knp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wqkva = UInt64(0); var wqkvp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wqkvsa = UInt64(0); var wqkvsp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var woa = UInt64(0); var wop = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wosa = UInt64(0); var wosp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wgua = UInt64(0); var wgup = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wgusa = UInt64(0); var wgusp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wdowna = UInt64(0); var wdownp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wdownsa = UInt64(0); var wdownsp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var cka = UInt64(0); var ckp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var cva = UInt64(0); var cvp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
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

        self.embed_addr = UInt64(0); self.embed_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.embed_scale_addr = UInt64(0); self.embed_scale_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.final_norm_addr = UInt64(0); self.final_norm_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.cos_addr = UInt64(0); self.cos_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.sin_addr = UInt64(0); self.sin_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        if _mb_alloc_buffer(d_model * 4, self.hidden_addr, self.hidden_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (hidden)")
        if _mb_alloc_buffer(n_qkv * 4, self.qkv_addr, self.qkv_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (qkv)")
        if _mb_alloc_buffer(h_q * d_head * 4, self.q_rot_addr, self.q_rot_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (q_rot)")
        if _mb_alloc_buffer(h_q * d_head * 4, self.attn_out_addr, self.attn_out_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn_out)")
        if _mb_alloc_buffer(d_ff * 4, self.act_addr, self.act_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (act)")
        if _mb_alloc_buffer(_LM_BLOCKS * 4, self.blk_val_addr, self.blk_val_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (blk_val)")
        if _mb_alloc_buffer(_LM_BLOCKS * 4, self.blk_idx_addr, self.blk_idx_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (blk_idx)")
        if _mb_alloc_buffer(4, self.out_val_addr, self.out_val_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (out_val)")
        if _mb_alloc_buffer(4, self.out_idx_addr, self.out_idx_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (out_idx)")

        # ── deep-context split/merge scratch: ONE shared buffer, reused across layers exactly the
        # way `q_rot`/`attn_out` already are (attention for layer L+1 never starts before layer L's
        # own SDPA role has both read and finished with its inputs, so overwriting this scratch next
        # layer is safe -- the same sequencing argument this file's docstring makes for `attn_out`).
        # NOT allocated here: a session that never crosses `_ATTN_SPLITK_THRESHOLD` never needs this
        # scratch, so `_ensure_deep_initialized` (below) allocates it lazily, the first time `step()`
        # actually needs it. Every field still gets a value now (a null placeholder) -- Mojo requires
        # `self` fully initialized before `__init__` returns, and `_ensure_deep_initialized` is a
        # separate `mut self` method, not a continuation of this constructor.
        self.m_partial_addr = UInt64(0); self.m_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.l_partial_addr = UInt64(0); self.l_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.o_partial_addr = UInt64(0); self.o_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()

        # ── the SECOND, deep-context descriptor table's OWN fields. `n_descriptors_deep` is pure
        # arithmetic (no allocation, no measurable cost) so it stays here -- `step()`'s dispatch-count
        # bookkeeping and `_ensure_deep_initialized`'s own budget check both need it before either
        # runs. `descriptors_deep` itself is a null placeholder until `_ensure_deep_initialized`
        # allocates and builds it lazily -- see that method's own docstring for why (the measured,
        # real, one-time construction cost this whole block used to pay: ~3us for the allocation,
        # ~10us for `_build_descriptors_deep` itself, on top of the two kernels' ~71.5us compile and
        # the three scratch buffers' ~486us alloc above -- ~560us total, paid even by a session that
        # never once crosses `_ATTN_SPLITK_THRESHOLD`, which is exactly the published 16-token race's
        # own session).
        self.n_descriptors_deep = 1 + self.n_layers * 7 + 2
        self.descriptors_deep = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.token_id_offset_deep = -1
        self.pos_offsets_deep = List[Int]()
        self.nkeys_offsets_deep = List[Int]()
        self.deep_ready = False

        self._build_descriptors(n_qkv)

    def _ensure_deep_initialized(mut self) raises:
        """Lazily finishes constructing the deep-context (split/merge) path — the two kernel
        compiles, the three scratch-buffer allocations, and building `self.descriptors_deep` — the
        FIRST time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD`, instead of unconditionally in
        `__init__` for every session regardless of whether it ever goes deep. Idempotent (`self.
        deep_ready` guards it) since `step()` calls this on EVERY deep-branch call, not just the
        first.

        Why this is safe to defer, item by item (each is now measured, see the RootCause investigation
        this fix implements):
          - `compile_function_unchecked[_splitk_partial_kernel_simd_native]`/`[_splitk_merge_kernel_simd]`:
            deferring WHEN this Mojo statement executes does not change WHICH pipelines
            `_mb_open_session` discovers in `__init__` (this file's own module docstring: pipeline
            discovery is driven by scanning this binary's embedded `.metallib` blobs by NAME, not by
            `compile_function_unchecked` call order) — `self.pipeline_idx_split`/`pipeline_idx_merge`
            are already resolved by `__init__`'s existing discovery loop before this method ever runs.
            What IS deferred is the real, measured ~71.5us cost of executing the two calls themselves.
          - The three `_mb_alloc_buffer` calls: real GPU buffer allocations (measured ~486us for these
            three), genuinely skipped, not merely postponed, for any session that never goes deep.
          - `_mb_alloc_descriptors` + `_build_descriptors_deep`: a CPU-side heap allocation (~3us)
            plus filling it in (~10us), same reasoning.

        `step()`'s own docstring has the gate this method serves; correctness is unaffected either
        way — `_build_descriptors_deep`'s plan is unchanged, just built once, later, instead of once,
        immediately."""
        if self.deep_ready:
            return
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_splitk_partial_kernel_simd_native]()
        _ = cctx.compile_function_unchecked[_splitk_merge_kernel_simd]()

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
        """Same descriptor PLAN as `_MBQwen3I8AllSimd2`'s own — same roles, same grid/threadgroup
        shapes, same per-step-varying slots; both the lm_head role's AND the argmax_reduce role's
        descriptors are unaffected (each still carries the SAME argument count and order —
        `_argmax_reduce_kernel` and `_argmax_reduce_kernel_simd` share an identical 5-argument
        signature, exactly as the lm_head pair shares its 10-argument one), only which compiled
        pipeline `_ROLE_ARGMAX_REDUCE` resolves to differs, decided entirely by which kernel this
        struct's constructor compiled."""
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
        """The SECOND descriptor table `step()` submits when `n_keys >= _ATTN_SPLITK_THRESHOLD` —
        IDENTICAL per-layer plan to `_build_descriptors` above, roles and order both, with exactly
        ONE substitution: the single `_ROLE_SDPA` dispatch (`grid_x=h_q`) is replaced by TWO
        dispatches, `_splitk_partial_kernel_simd_native` (`grid_x = h_q * _ATTN_SPLITK_N_SPLITS_NATIVE`,
        `block_dim = WARP_SIZE` -- the one field this struct's own dispatch differs on, see below)
        then `_splitk_merge_kernel_simd` (`grid_x = h_q`, `block_dim = d_head`, same shape the SDPA
        dispatch it replaces used) — 7 descriptors per layer here against that method's 6.
        (`_MBQwen3I8AllSimd3`'s own version of this method dispatches the TWO-LEVEL `_splitk_
        partial_kernel_simd` at `block_dim = d_head`, grid `h_q * _ATTN_SPLITK_N_SPLITS` (16) here
        instead; `_MBQwen3I8AllSimd5`'s own version dispatches THIS SAME native kernel but at that
        same narrower `_ATTN_SPLITK_N_SPLITS` (16) grid width, the configuration its own docstring
        found a regression -- this struct's own docstring has the full account of why `_ATTN_SPLITK_
        N_SPLITS_NATIVE` (80) is used here instead.) Every OTHER role (`norm_gemv`,
        `qk_rope`, both `gemv_accum`s, `norm_gemv2_swiglu`, `lm_head`, `argmax_reduce`) is copied
        byte-for-byte, reading and writing the SAME resident buffers (`hidden`/`qkv`/`q_rot`/
        `attn_out`/per-layer `ck`/`cv`/weights) `_build_descriptors`'s own plan does — this table is
        an ALTERNATE PLAN over the identical resident state, not a second independent model.

        `q_rot`/`ck`/`cv` are written by THIS table's own `qk_rope` dispatch every step it is chosen,
        exactly as `_build_descriptors`'s plan writes them every step IT is chosen — whichever plan
        `step()` did not pick on the PREVIOUS call left no residue either plan depends on, since
        `qk_rope` fully overwrites this step's KV-cache slot and `q_rot` regardless of which table
        runs it.

        Called from `_ensure_deep_initialized`, lazily, the first time `step()` crosses
        `_ATTN_SPLITK_THRESHOLD` — NOT from `__init__` (see that method's own docstring for why).
        `self.descriptors_deep` must already be allocated (by the caller) before this runs; this
        method only fills it in, exactly as it always did.
        """
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

            # ── split: unnormalized partial (m, l, o) per (head, split) — replaces the ONE SDPA
            # dispatch `_build_descriptors` issues here with a grid `_ATTN_SPLITK_N_SPLITS_NATIVE` times
            # bigger, recruiting that many times the warps for the SAME query token.
            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx_split,
                self.h_q * self.n_splits_max, WARP_SIZE, 12,
            )
            # `block_dim = WARP_SIZE` (32), NOT `self.d_head` (128) -- the SAME field `_MBQwen3I8
            # AllSimd5`'s own split dispatch already differs on from `_MBQwen3I8AllSimd3`'s own
            # `_build_descriptors_deep`. THIS struct's own additional difference from BOTH: the grid
            # width itself is `h_q * _ATTN_SPLITK_N_SPLITS_NATIVE` (80), not `h_q * _ATTN_SPLITK_
            # N_SPLITS` (16) -- `_ATTN_SPLITK_N_SPLITS_NATIVE`'s own docstring has the sweep that
            # picked 80. Every OTHER argument below, and every OTHER descriptor in this table, are
            # otherwise byte-identical to `_MBQwen3I8AllSimd5`'s own plan.
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

            # ── merge: the `_ATTN_SPLITK_N_SPLITS_NATIVE` partials -> ONE normalized attn_out, same shape
            # (`grid_x=h_q`) the SDPA dispatch it replaces wrote its own final output at.
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

    def set_n_splits(mut self, new_n_splits: Int) raises:
        """Scratch-sweep-only mutator. `_mb_set_header` (`metaldispatch.ffi`) only ever writes a
        descriptor's 16-byte HEADER (pipeline_idx/grid_x/threads_x/num_args) -- never the args area --
        so calling it again here to change `grid_x` cannot corrupt any argument this same descriptor
        already holds; the two `n_splits` VALUE arguments (`splitk_partial`'s arg index 7,
        `splitk_merge`'s arg index 4) are repatched separately, immediately after, via the ordinary
        `_mb_set_arg_int`. Safe for any `new_n_splits` in `[1, self.n_splits_max]` -- the three scratch
        buffers stay sized for `self.n_splits_max` (see `_ensure_deep_initialized`), so a SMALLER grid
        width and a SMALLER `n_splits` value together only ever address a PREFIX of each buffer, never
        past its end. Does not touch `n_keys` (arg index 6 on the split descriptor) -- that stays
        whatever the caller's own per-position patching (`_mb_set_arg_int(..., 6, n_keys)`) last set,
        exactly like every other per-step-varying argument in this file's descriptor tables.

        Offsets are `_build_descriptors_deep`'s own fixed layout, not rediscovered: one `embed`
        descriptor at index 0, then exactly 7 per layer in the fixed order `norm_gemv, qk_rope,
        splitk_partial, splitk_merge, gemv_accum, norm_gemv2_swiglu, gemv_accum` -- so layer `L`'s
        split slot is `1 + 7*L + 2` and its merge slot is `1 + 7*L + 3`, matching that method's own
        `d` bookkeeping exactly (verified against it by inspection, not re-derived at runtime)."""
        for layer in range(self.n_layers):
            var d_split = 1 + 7 * layer + 2
            var d_merge = 1 + 7 * layer + 3
            _mb_set_header(
                self.descriptors_deep, d_split, self.pipeline_idx_split,
                self.h_q * new_n_splits, WARP_SIZE, 12,
            )
            _mb_set_arg_int(self.descriptors_deep, d_split, 7, new_n_splits)
            _mb_set_arg_int(self.descriptors_deep, d_merge, 4, new_n_splits)

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV + lm_head + argmax-reduce SIMD-shuffle reduction, deep split-K native single-SIMD-group reduction)"

    def dispatch_budget(self) -> Int:
        return self.n_descriptors

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
        """`_MBQwen3I8AllSimd2.step`'s own body (which is itself `_MBQwen3I8AllSimd.step`'s), PLUS
        one gate: below `_ATTN_SPLITK_THRESHOLD`, this is BYTE-FOR-BYTE that body, patching and
        submitting `self.descriptors` exactly as every sibling struct's `step()` does — the published
        race's own short-context depth (16 tokens) takes this branch, unchanged, which is what makes
        that race's regression gate trivially satisfied by construction, not by a separate check.

        At or above the threshold, this patches and submits `self.descriptors_deep`
        (`_build_descriptors_deep`'s plan: `_splitk_partial_kernel_simd_native` + `_splitk_
        merge_kernel_simd` in place of the one `_sdpa_kernel_simd` dispatch) instead — same `token_id`/
        `pos`/`n_keys` values, just patched into that table's own offsets, since the two tables are
        different PLANS over the identical resident buffers (this struct's own field docstring has
        the full account of why the choice per step is safe).

        `PR #519`'s long-context investigation measured `_ATTN_SPLITK_THRESHOLD = 512` against the
        REAL production grid/block shape, not the isolated single-role scratch probe that first
        suggested the number: at `n_keys=256` (below threshold) this branch is never taken; the
        split path's own first real win starts around `n_keys ~= 500` and only grows from there, so
        512 leaves margin on both sides of the measured crossover rather than sitting on top of it.

        The deep branch's FIRST call (per session) also pays `_ensure_deep_initialized`'s one-time
        cost (kernel compiles + scratch-buffer allocs + building `self.descriptors_deep`) — see that
        method's own docstring. A session that never crosses `_ATTN_SPLITK_THRESHOLD` never calls it
        at all, which is the whole point of this gate existing (a shallow-only session, e.g. the
        published 16-token race, now pays NONE of that cost, where it used to pay all of it
        unconditionally in `__init__`).
        """

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

            if n_keys < _ATTN_SPLITK_THRESHOLD:
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
                _mb_set_arg_int(self.descriptors_deep, self.token_id_offset_deep, 3, token_id)
                for layer in range(self.n_layers):
                    _mb_set_arg_int(self.descriptors_deep, self.pos_offsets_deep[layer], 8, pos)
                    # arg index 6, not 4: `_splitk_partial_kernel_simd_native`'s own signature puts
                    # `n_keys` after the THREE partial-output pointers plus `q_rot`/`ck`/`cv` (6
                    # pointer args before it), where `_sdpa_kernel_simd`'s puts it after 4.
                    _mb_set_arg_int(self.descriptors_deep, self.nkeys_offsets_deep[layer], 6, n_keys)

                var rc = _mb_run_token(self.descriptors_deep, self.n_descriptors_deep)
                if rc != 0:
                    return _StepOut(-1, 0.0, self.n_descriptors_deep, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, dispatches_used, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, dispatches_used, MB_OK)


def _mb_counters_supported() -> Int:
    return Int(external_call["algenta_counters_supported", Int64]())


def _mb_timestamp_frequency() -> UInt64:
    return external_call["algenta_timestamp_frequency", UInt64]()


def _mb_sample_gpu_timestamp() -> UInt64:
    return external_call["algenta_sample_gpu_timestamp", UInt64]()


def _calibrate_gpu_tick_ns(hold_ms: Int) raises -> Float64:
    var t_wall0 = perf_counter_ns()
    var gpu0 = _mb_sample_gpu_timestamp()
    var deadline = t_wall0 + UInt(hold_ms) * 1_000_000
    while perf_counter_ns() < deadline:
        pass
    var gpu1 = _mb_sample_gpu_timestamp()
    var t_wall1 = perf_counter_ns()
    if gpu1 <= gpu0:
        raise Error("qwen3_probe_splitk_native_sweep: GPU timestamp calibration did not advance")
    var wall_seconds = Float64(Int(t_wall1 - t_wall0)) / 1.0e9
    var tick_rate_hz = Float64(gpu1 - gpu0) / wall_seconds
    return 1.0e9 / tick_rate_hz


def _mb_open_counters(max_samples: Int) -> Int:
    return Int(external_call["algenta_open_counters", Int64, Int64](Int64(max_samples)))


def _mb_run_token_counters(
    descriptors: UnsafePointer[UInt8, origin=MutAnyOrigin],
    n: Int,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
) -> Int:
    return Int(
        external_call[
            "algenta_run_token_counters", Int64,
            UnsafePointer[UInt8, origin=MutAnyOrigin], Int64,
            UnsafePointer[UInt64, origin=MutAnyOrigin],
        ](descriptors, Int64(n), out_ticks)
    )


def _read_text_file(path: String) raises -> String:
    var f = open(path, "r")
    var raw = f.read_bytes()
    f.close()
    return String(from_utf8=raw)


@fieldwise_init
struct TensorLoc(Copyable, Movable):
    var offset: Int
    var n_elements: Int


def _tensor_loc(tensors_obj: String, name: String) raises -> TensorLoc:
    var entry = json_get_object(tensors_obj, name)
    var offset = json_get_int(entry, "offset", -1)
    var n = json_get_int(entry, "n_elements", -1)
    if offset < 0 or n < 0:
        raise Error("qwen3_probe_splitk_native_sweep: tensor not found in manifest: " + name)
    return TensorLoc(offset, n)


def _read_f64_slice(path: String, byte_offset: Int, n_elements: Int) raises -> List[Float64]:
    var f = open(path, "r")
    _ = f.seek(UInt64(byte_offset))
    var raw = f.read_bytes(n_elements * 8)
    f.close()
    if len(raw) != n_elements * 8:
        raise Error("qwen3_probe_splitk_native_sweep: short read at byte offset " + String(byte_offset))
    var out = List[Float64](capacity=n_elements)
    var fp = raw.unsafe_ptr().bitcast[Float64]()
    for i in range(n_elements):
        out.append(fp[i])
    return out^


def _load_tensor(blob_path: String, tensors_obj: String, name: String) raises -> List[Float64]:
    var loc = _tensor_loc(tensors_obj, name)
    return _read_f64_slice(blob_path, loc.offset * 8, loc.n_elements)


def _check_mb(status: Int) raises:
    if status != MB_OK:
        raise Error(
            "qwen3_probe_splitk_native_sweep: metaldispatch call failed, status=" + String(status)
            + " (" + metaldispatch_status_name(status) + ")"
        )


def _sample_shallow_sdpa(
    mut s: _MBQwen3I8SplitKSweep,
    pos: Int,
    n_samples: Int,
    ns_per_tick: Float64,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
    mut sdpa_ms_out: Float64,
    mut wall_ms_out: Float64,
) raises:
    """PART 5 (dead-zone) baseline: sums the UNSPLIT `_sdpa_kernel_simd` role's own GPU dispatch time
    over all `n_layers` layers, via `s.descriptors` (`_build_descriptors`'s plan, built unconditionally
    in `__init__`, exactly as every sibling struct's shallow table is) -- never `s.descriptors_deep`.
    Reaches in directly, bypassing `step()`'s threshold gate entirely, so this can sample the unsplit
    kernel at ANY position, including ones at or above `_ATTN_SPLITK_THRESHOLD` -- the whole point of
    this comparison being reachable in the dead zone (`n_keys` in `[256, 511]`) where PRODUCTION code
    never dispatches the split kernel at all.

    Offsets are `_build_descriptors`'s own fixed layout (one `embed` descriptor at index 0, then
    exactly 6 per layer in the fixed order `norm_gemv, qk_rope, sdpa, gemv_accum, norm_gemv2_swiglu,
    gemv_accum`) -- layer `L`'s `sdpa` slot is `1 + 6*L + 2`."""
    var n_keys = pos + 1
    _mb_set_arg_int(s.descriptors, s.token_id_offset, 3, 13)
    for layer in range(s.n_layers):
        _mb_set_arg_int(s.descriptors, s.pos_offsets[layer], 8, pos)
        _mb_set_arg_int(s.descriptors, s.nkeys_offsets[layer], 4, n_keys)
    var sdpa_total_ns = 0.0
    var wall_total_ms = 0.0
    for _ in range(n_samples):
        var t0 = perf_counter_ns()
        var rc = _mb_run_token_counters(s.descriptors, s.n_descriptors, out_ticks)
        var t1 = perf_counter_ns()
        if rc != 0:
            raise Error("qwen3_probe_splitk_native_sweep: algenta_run_token_counters failed (shallow)")
        wall_total_ms += Float64(Int(t1 - t0)) / 1.0e6
        for layer in range(s.n_layers):
            var d_sdpa = 1 + 6 * layer + 2
            var t0v = out_ticks[2 * d_sdpa]
            var t1v = out_ticks[2 * d_sdpa + 1]
            if t1v >= t0v:
                sdpa_total_ns += Float64(t1v - t0v) * ns_per_tick
    sdpa_ms_out = sdpa_total_ns / Float64(n_samples) / 1.0e6
    wall_ms_out = wall_total_ms / Float64(n_samples)


def _sample_split_merge(
    mut s: _MBQwen3I8SplitKSweep,
    pos: Int,
    n_samples: Int,
    ns_per_tick: Float64,
    out_ticks: UnsafePointer[UInt64, origin=MutAnyOrigin],
    mut split_ms_out: Float64,
    mut merge_ms_out: Float64,
    mut wall_ms_out: Float64,
) raises:
    """Sums `splitk_partial`'s and `splitk_merge`'s own GPU dispatch time over all `n_layers` layers,
    averaged over `n_samples` dispatch-and-sample repetitions at one `pos` (`n_keys = pos + 1`) --
    the sweep's own per-(n_splits, depth, round) unit of measurement. Descriptor offsets are
    `_build_descriptors_deep`'s fixed layout (see `_MBQwen3I8SplitKSweep.set_n_splits`'s own
    docstring for the exact formula), not rediscovered per call."""
    var n_keys = pos + 1
    _mb_set_arg_int(s.descriptors_deep, s.token_id_offset_deep, 3, 13)  # any valid vocab id
    for layer in range(s.n_layers):
        _mb_set_arg_int(s.descriptors_deep, s.pos_offsets_deep[layer], 8, pos)
        _mb_set_arg_int(s.descriptors_deep, s.nkeys_offsets_deep[layer], 6, n_keys)
    var split_total_ns = 0.0
    var merge_total_ns = 0.0
    var wall_total_ms = 0.0
    for _ in range(n_samples):
        var t0 = perf_counter_ns()
        var rc = _mb_run_token_counters(s.descriptors_deep, s.n_descriptors_deep, out_ticks)
        var t1 = perf_counter_ns()
        if rc != 0:
            raise Error("qwen3_probe_splitk_native_sweep: algenta_run_token_counters failed")
        wall_total_ms += Float64(Int(t1 - t0)) / 1.0e6
        for layer in range(s.n_layers):
            var d_split = 1 + 7 * layer + 2
            var d_merge = 1 + 7 * layer + 3
            var s0 = out_ticks[2 * d_split]
            var s1 = out_ticks[2 * d_split + 1]
            if s1 >= s0:
                split_total_ns += Float64(s1 - s0) * ns_per_tick
            var m0 = out_ticks[2 * d_merge]
            var m1 = out_ticks[2 * d_merge + 1]
            if m1 >= m0:
                merge_total_ns += Float64(m1 - m0) * ns_per_tick
    split_ms_out = split_total_ns / Float64(n_samples) / 1.0e6
    merge_ms_out = merge_total_ns / Float64(n_samples) / 1.0e6
    wall_ms_out = wall_total_ms / Float64(n_samples)


def main() raises:
    var args = argv()
    var max_ctx = 8192
    var n_splits_max = 256
    var n_samples = 16
    var n_rounds = 5
    if len(args) > 1:
        max_ctx = parse_int(String(args[1]))
    if len(args) > 2:
        n_splits_max = parse_int(String(args[2]))
    if len(args) > 3:
        n_samples = parse_int(String(args[3]))
    if len(args) > 4:
        n_rounds = parse_int(String(args[4]))

    var manifest = _read_text_file(MANIFEST_PATH)
    var config = json_get_object(manifest, "config")
    var d_model = json_get_int(config, "hidden_size", -1)
    var n_layers = json_get_int(config, "num_hidden_layers", -1)
    var h_q = json_get_int(config, "num_attention_heads", -1)
    var h_kv = json_get_int(config, "num_key_value_heads", -1)
    var d_head = json_get_int(config, "head_dim", -1)
    var d_ff = json_get_int(config, "intermediate_size", -1)
    var vocab_size = json_get_int(config, "vocab_size", -1)
    var theta = json_get_float(config, "rope_theta", -1.0)
    var eps = json_get_float(config, "rms_norm_eps", -1.0)
    var n_prompt = json_get_int(config, "n_tokens", -1)

    if d_model < 1 or n_layers < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1 \
       or vocab_size < 1 or n_prompt < 1:
        raise Error("qwen3_probe_splitk_native_sweep: manifest config did not parse")

    from std.math import sqrt
    var scale = 1.0 / sqrt(Float64(d_head))

    print("qwen3_probe_splitk_native_sweep: max_ctx=", max_ctx, "n_splits_max=", n_splits_max,
          "n_samples=", n_samples, "n_rounds=", n_rounds, "n_layers=", n_layers)

    var pre = _mb_preflight(
        d_model, h_q, h_kv, d_head, d_ff, n_layers, n_prompt, 2, max_ctx, eps, scale
    )
    if pre != MB_OK:
        print("qwen3_probe_splitk_native_sweep: cannot run a batched session here:",
              metaldispatch_status_name(pre))
        return

    @parameter
    if not MB_GPU_BUILD:
        print("qwen3_probe_splitk_native_sweep: built without -D ALGENTA_GPU")
        return
    else:
        if not has_accelerator():
            print("qwen3_probe_splitk_native_sweep: no accelerator on this host")
            return

        var tensors_obj = json_get_object(manifest, "tensors")
        var s = _MBQwen3I8SplitKSweep(
            d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab_size, max_ctx, eps, scale, n_splits_max
        )
        print("  device:", s.device_name())

        var rt = rope_table(d_head, max_ctx, theta)
        _ = ATTN_OK
        var embed_table = _load_tensor(BLOB_PATH, tensors_obj, "model.embed_tokens.weight")
        var final_norm_w = _load_tensor(BLOB_PATH, tensors_obj, "model.norm.weight")
        _check_mb(s.upload_globals(embed_table, final_norm_w, rt.cos_table, rt.sin_table, max_ctx))

        for layer in range(n_layers):
            var prefix = "model.layers." + String(layer) + "."
            var ln1 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "input_layernorm.weight")
            var ln2 = _load_tensor(BLOB_PATH, tensors_obj, prefix + "post_attention_layernorm.weight")
            var qn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_norm.weight")
            var kn = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_norm.weight")
            var wq = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.q_proj.weight")
            var wk = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.k_proj.weight")
            var wv = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.v_proj.weight")
            var wo = _load_tensor(BLOB_PATH, tensors_obj, prefix + "self_attn.o_proj.weight")
            var wg = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.gate_proj.weight")
            var wu = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.up_proj.weight")
            var wd = _load_tensor(BLOB_PATH, tensors_obj, prefix + "mlp.down_proj.weight")
            _check_mb(s.upload_layer(layer, ln1, ln2, qn, kn, wq, wk, wv, wo, wg, wu, wd))
        _ = s.seal()
        print("  weights loaded + sealed")

        s._ensure_deep_initialized()

        var supported = _mb_counters_supported()
        if supported != 1:
            print("qwen3_probe_splitk_native_sweep: counter sampling not available, status=", supported)
            return
        var ns_per_tick = _calibrate_gpu_tick_ns(200)
        print("  calibrated ns/tick:", ns_per_tick)
        var counters_rc = _mb_open_counters(2 * s.n_descriptors_deep)
        if counters_rc != 0:
            raise Error("qwen3_probe_splitk_native_sweep: algenta_open_counters failed, rc=" + String(counters_rc))
        var out_ticks = alloc[UInt64](2 * s.n_descriptors_deep)

        var depths = List[Int]()
        depths.append(128); depths.append(256); depths.append(500); depths.append(750)
        depths.append(1000); depths.append(2000); depths.append(4000); depths.append(8000)

        var candidates = List[Int]()
        candidates.append(20); candidates.append(40); candidates.append(60); candidates.append(80)
        candidates.append(100); candidates.append(120); candidates.append(160); candidates.append(200)
        candidates.append(256)

        print("")
        print("RESULT_HEADER n_splits,depth,round,split_ms,merge_ms,total_ms,wall_ms")
        for ci in range(len(candidates)):
            var nsplit = candidates[ci]
            if nsplit > n_splits_max:
                print("  skipping n_splits=", nsplit, "(> n_splits_max=", n_splits_max, ")")
                continue
            s.set_n_splits(nsplit)
            for di in range(len(depths)):
                var depth = depths[di]
                if depth >= max_ctx:
                    continue
                var pos = depth - 1
                for r in range(n_rounds):
                    var split_ms = 0.0
                    var merge_ms = 0.0
                    var wall_ms = 0.0
                    _sample_split_merge(s, pos, n_samples, ns_per_tick, out_ticks, split_ms, merge_ms, wall_ms)
                    print(
                        "RESULT", nsplit, ",", depth, ",", r, ",", split_ms, ",", merge_ms, ",",
                        split_ms + merge_ms, ",", wall_ms,
                    )
        print("")
        print("═══ PART 5: dead-zone (n_keys < _ATTN_SPLITK_THRESHOLD=", _ATTN_SPLITK_THRESHOLD,
              ") -- unsplit sdpa vs. small-n_splits native split-K, same positions ═══")
        var dz_depths = List[Int]()
        dz_depths.append(16); dz_depths.append(32); dz_depths.append(64)
        dz_depths.append(128); dz_depths.append(200); dz_depths.append(256)
        dz_depths.append(300); dz_depths.append(400); dz_depths.append(480)

        print("")
        print("DEADZONE_BASELINE_HEADER depth,round,sdpa_unsplit_ms,wall_ms")
        for di in range(len(dz_depths)):
            var depth = dz_depths[di]
            var pos = depth - 1
            for r in range(n_rounds):
                var sdpa_ms = 0.0
                var wall_ms = 0.0
                _sample_shallow_sdpa(s, pos, n_samples, ns_per_tick, out_ticks, sdpa_ms, wall_ms)
                print("DEADZONE_BASELINE", depth, ",", r, ",", sdpa_ms, ",", wall_ms)

        var dz_candidates = List[Int]()
        dz_candidates.append(4); dz_candidates.append(8); dz_candidates.append(16)
        dz_candidates.append(20); dz_candidates.append(32); dz_candidates.append(40)

        print("")
        print("DEADZONE_SPLIT_HEADER n_splits,depth,round,split_ms,merge_ms,total_ms,wall_ms")
        for ci in range(len(dz_candidates)):
            var nsplit = dz_candidates[ci]
            s.set_n_splits(nsplit)
            for di in range(len(dz_depths)):
                var depth = dz_depths[di]
                var pos = depth - 1
                for r in range(n_rounds):
                    var split_ms = 0.0
                    var merge_ms = 0.0
                    var wall_ms = 0.0
                    _sample_split_merge(s, pos, n_samples, ns_per_tick, out_ticks, split_ms, merge_ms, wall_ms)
                    print(
                        "DEADZONE_SPLIT", nsplit, ",", depth, ",", r, ",", split_ms, ",", merge_ms, ",",
                        split_ms + merge_ms, ",", wall_ms,
                    )

        print("")
        print("qwen3_probe_splitk_native_sweep: DONE")
