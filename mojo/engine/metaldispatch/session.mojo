"""
metaldispatch.session — the resident Qwen3 decode session, dispatched through the batched C shim
instead of `DeviceContext.enqueue_function`. Zero Python.

@capability-module
deterministic: true
stateful: true
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: float32
backend: metal
surfaces: none
golden_vectors: mojo/tests/libs/test_metaldispatch_session.mojo
benchmark: benchmarks/llm_smoke/metal_batch_dispatch/qwen3_generate_batch.mojo
version_introduced: 0.7.0
deprecation_state: active
@endcapability

NOT a contract module. Every entry point here is private, and every launch is compile-time gated
--------------------------------------------------------------------------------------------------
Identical discipline to `residentk.session` (see that file's module docstring for the full
reasoning): leading underscores keep this out of `apps/runtime/mojo_inventory.py`, and every
function that would force shader codegen opens with `@parameter if not MB_GPU_BUILD: return
<toolchain_absent>`. `MB_GPU_BUILD` keys off the exact same `-D ALGENTA_GPU` define
`residentk.session.RESIDENT_GPU_BUILD` and `accel.gemm_metal.ACCEL_GPU_BUILD` do (imported directly
from `residentk.session`, not redeclared — a second `is_defined` call reading the same flag is a
value duplicated at two call sites for no reason, and rule 3's spirit is "don't restate an existing
answer" as much as "don't restate an existing kernel").

Why this package's buffers are NOT `residentk`'s `DeviceBuffer`s
---------------------------------------------------------------------
The batched shim needs to mark every buffer a dispatch touches as an in-use Metal resource
(`useResource:usage:`) before the encoder that dispatch belongs to is committed — required by the
proven ABI recipe (a buffer's ADDRESS, not a `setBuffer:` binding, is what a Mojo-compiled kernel's
pointer argument actually reads, so Metal's automatic residency tracking never sees it touched
unless told explicitly). That call needs a live `id<MTLBuffer>` Objective-C object. A prior,
separate investigation (`.worktrees/metalffi`, Route A) proved that no such object is reachable from
`DeviceContext`/`DeviceFunction`'s own handles via heap-scanning; the same is true of
`DeviceBuffer` — MAX's C++ runtime does not expose one.

So this package allocates its OWN resident buffers, through the shim
(`metaldispatch.ffi._mb_alloc_buffer`), which DOES hand back a real `id<MTLBuffer>` (the shim holds
the strong reference and marks it resident internally) alongside the raw `gpuAddress` a kernel's
pointer argument binds to and a CPU-writable `contents` pointer for the one-time upload. The
WEIGHT LAYOUT, the upload/transpose math, the KV-cache in-place write scheme and the 171-dispatch
fusion plan are `residentk`'s own, reused exactly (`_narrow_into`/`_narrow_transposed_into` below
are the same arithmetic as `residentk.session`'s, ported to write through a raw pointer instead of
through `DeviceBuffer.map_to_host()` — MAX's own upload primitive `map_to_host()` is itself
unavailable for a buffer this package allocated outside MAX). Only WHERE the resident memory lives,
and HOW a dispatch reaches it, differ from `residentk.session` — never the kernels themselves
(`residentk.kernels`' functions are imported directly, never copied) and never the fusion grouping,
grid shapes or KV-cache scheme (`_ceil_div`, `_TG`, `_SUBS`, `_LM_BLOCKS`, `_TILE` are the exact same
constants `residentk.session` uses, several imported directly).

The pipeline table is discovered by NAME, not by call order
----------------------------------------------------------------
`metaldispatch.ffi._mb_open_session` extracts every embedded `.metallib` from this binary's own
`__TEXT,__const` and builds one pipeline per blob, in the order the blobs happen to appear —
measured to NOT match the order `compile_function_unchecked` was called in (the two were compared
directly while building this package; they differ). So `_resolve_pipelines` below reads each
pipeline's real Metal function name back from the shim and classifies it by substring against
`residentk.kernels`' own function names, once, at session open.

Why `_MBQwen3F16` is a SEPARATE binary's struct, not a second set of roles in the same one
------------------------------------------------------------------------------------------------
Measured directly while adding the fp16 arm this package's own `#505`-combination task called for:
Mojo's Metal AIR function name (what `algenta_pipeline_name` reads back) is truncated to a short,
shared, human-readable prefix followed by a per-specialization hash suffix — e.g. the Float32 and
Float16 twins of `_norm_gemv_kernel` both surface as `residentk_kernels__norm_gemv_k6A6A6A6A_<hash>`
with DIFFERENT (opaque) hashes but an IDENTICAL visible prefix. `_classify_pipeline`'s substring
match cannot tell them apart if both are compiled into the same binary — there would be two
pipelines answering to `_ROLE_NORM_GEMV` with no text-based way to say which is which. Rather than
add a runtime discrimination probe (dispatch each candidate against a known bit pattern and check
which one reads it as Float32), `_MBQwen3F16`'s constructor simply never compiles the Float32 GEMV-
shaped kernels at all — its binary (`qwen3_generate_batch_f16.mojo`) embeds exactly one pipeline per
role, the same invariant `_MBQwen3`'s binary already relies on, so the existing name-substring
classifier needs no changes and no new ambiguity is possible. `_qk_rope_write_kernel`, `_sdpa_kernel`
and `_argmax_reduce_kernel` have no fp16 twin (`residentk`'s own fp16 session reuses them
unmodified — see `_ResidentQwen3F16`'s own field list) so both binaries embed the identical Float32
versions of those three, harmlessly.
"""

from std.builtin.type_aliases import MutAnyOrigin
from std.gpu import WARP_SIZE
from std.math import abs
from std.sys import has_accelerator
from residentk.contract import RESIDENT_MAX_CONTEXT
from residentk.kernels import (
    _TG,
    _SUBS,
    _argmax_reduce_kernel,
    _argmax_reduce_kernel_simd,
    _splitk_partial_kernel_simd,
    _splitk_merge_kernel_simd,
    _embed_row_kernel,
    _embed_row_kernel_f16,
    _embed_row_kernel_i8,
    _gemv_accum_kernel,
    _gemv_accum_kernel_f16,
    _gemv_accum_kernel_i8,
    _gemv_accum_kernel_simd_i8,
    _lmhead_argmax_kernel,
    _lmhead_argmax_kernel_f16,
    _lmhead_argmax_kernel_i8,
    _lmhead_argmax_kernel_simd_i8,
    _norm_gemv2_swiglu_kernel,
    _norm_gemv2_swiglu_kernel_f16,
    _norm_gemv2_swiglu_kernel_i8,
    _norm_gemv2_swiglu_kernel_simd_i8,
    _norm_gemv_kernel,
    _norm_gemv_kernel_f16,
    _norm_gemv_kernel_i8,
    _norm_gemv_kernel_simd_i8,
    _qk_rope_write_kernel,
    _qk_rope_write_kernel_kvf16,
    _sdpa_kernel,
    _sdpa_kernel_kvf16,
    _sdpa_kernel_simd,
)
from residentk.session import RESIDENT_GPU_BUILD
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
)

comptime MB_GPU_BUILD: Bool = RESIDENT_GPU_BUILD
"""Reuses `residentk.session`'s own build flag — see the module docstring."""

comptime _LM_BLOCKS: Int = 2048
"""Same value, same reason, as `residentk.session._LM_BLOCKS` (imported by value, not import,
because `residentk.session._LM_BLOCKS` is itself a module-private `comptime` and not re-exported;
restating a single already-justified constant is not the kind of duplication rule 3 warns about --
the ARITHMETIC that constant embodies is not repeated, only its value)."""

comptime _TILE: Int = 64
"""Host-side transpose tile — see `residentk.session._TILE`'s docstring for the measurement."""

comptime _ROLE_EMBED: Int = 0
comptime _ROLE_NORM_GEMV: Int = 1
comptime _ROLE_GEMV_ACCUM: Int = 2
comptime _ROLE_NORM_GEMV2_SWIGLU: Int = 3
comptime _ROLE_QK_ROPE: Int = 4
comptime _ROLE_SDPA: Int = 5
comptime _ROLE_LMHEAD_ARGMAX: Int = 6
comptime _ROLE_ARGMAX_REDUCE: Int = 7
comptime _N_ROLES: Int = 8


fn _ceil_div(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


fn _classify_pipeline(name: String) -> Int:
    """Which of the eight `residentk.kernels` functions a discovered pipeline's Metal function name
    belongs to, by substring match against the (possibly truncated) mangled name. Order matters:
    `norm_gemv2` is checked before the plain `norm_gemv` it would otherwise also match, and
    `lmhead` before the bare `argmax` that `_lmhead_argmax_kernel`'s own name also contains."""
    if name.find("embed_row") >= 0:
        return _ROLE_EMBED
    if name.find("norm_gemv2") >= 0:
        return _ROLE_NORM_GEMV2_SWIGLU
    if name.find("norm_gemv") >= 0:
        return _ROLE_NORM_GEMV
    if name.find("gemv_accum") >= 0:
        return _ROLE_GEMV_ACCUM
    if name.find("qk_rope") >= 0:
        return _ROLE_QK_ROPE
    if name.find("sdpa") >= 0:
        return _ROLE_SDPA
    if name.find("lmhead") >= 0:
        return _ROLE_LMHEAD_ARGMAX
    if name.find("argmax_redu") >= 0:
        return _ROLE_ARGMAX_REDUCE
    return -1


comptime _ATTN_SPLITK_N_SPLITS: Int = 16
"""Fixed split count for `_MBQwen3I8AllSimd3`'s deep-context SDPA path (`_splitk_partial_
kernel_simd` + `_splitk_merge_kernel_simd`, `residentk.kernels`) — baked in at construction
time, not derived from `n_keys` per step, because the batched descriptor plan this struct dispatches
through fixes every descriptor's grid size at `_build_descriptors_deep` time (see that method's own
docstring for why `n_keys`-DEPENDENT occupancy is not available in this architecture the way it is
in `residentk.session`'s own per-role `enqueue_function` calls). Chosen from the scratch probe PR
#519's long-context investigation ran against the real production grid/block shape (`grid_dim=16,
block_dim=128`): 16 splits measured a 4.3x-10.6x speedup from `n_keys=2000` up (`P=16` was inside the
measured-best range at every depth from 500 through 8000 that probe tried), without needing a second,
deeper-only split count."""

comptime _ATTN_SPLITK_THRESHOLD: Int = 512
"""Below this `n_keys`, `_MBQwen3I8AllSimd3.step` dispatches the ORIGINAL, byte-unmodified
`_sdpa_kernel_simd` (`self.descriptors`) exactly as before this fix — never the split/merge pair.
The same scratch probe that picked `_ATTN_SPLITK_N_SPLITS` found splitting a REGRESSION at the
published race's own depth (16 tokens: two dispatches' fixed launch overhead outweighs the extra
parallelism when there is barely any work to spread across it) and the first real win around
`n_keys ~= 500`. Set at 512, one clean power-of-two step above that measured crossover, so the
gate's own overhead-vs-benefit tradeoff has margin on both sides rather than sitting exactly on the
knee. `_MBQwen3I8AllSimd3.step`'s own docstring has the re-measurement against the real (not
isolated-probe) kernel that confirms this threshold."""


fn _classify_splitk_pipeline(name: String) -> Int:
    """Which of the TWO occupancy-fix kernels (`_splitk_partial_kernel_simd` /
    `_splitk_merge_kernel_simd`) a discovered pipeline's name belongs to — `0` / `1` / `-1`
    (neither). A SEPARATE function from `_classify_pipeline` above, deliberately never folded into
    it or into that function's own `_N_ROLES`-sized `pipeline_idx` list: `_classify_pipeline` and
    its 8-role resolution loop are SHARED by every struct in this file (`_MBQwen3`, `_MBQwen3F16`,
    every `_MBQwen3I8*` variant), and every one of them runs `for role in range(_N_ROLES): if
    self.pipeline_idx[role] < 0: raise Error(...)` — bumping the shared `_N_ROLES` to cover these two
    NEW roles would make every OTHER struct's constructor start demanding two pipelines it never
    compiles, breaking every arm that is not `_MBQwen3I8AllSimd3`. Neither substring below collides
    with any of `_classify_pipeline`'s own eight patterns (`sdpa` included: `splitk_partial`/
    `splitk_merge` contain no `sdpa` substring at all, checked directly against the real,
    possibly-truncated Metal AIR names this struct's own binary produces, not merely by inspection of
    the Mojo source names).

    THE TRUNCATION ITSELF, measured directly TWICE (`/tmp/probe_pipeline_names.mojo`, a throwaway
    scratch probe, not committed, plus a temporary debug `print` in this very constructor, since
    removed): every one of `_classify_pipeline`'s own eight kernels' real discovered names is
    `residentk_kernels__<11 visible chars>6A6A6A6A_<opaque hash>` — EXACTLY 11 characters of the Mojo
    function's own base name survive before the filler, confirmed across all eight (e.g. `_norm_
    gemv2_swiglu_kernel_simd_i8` -> `norm_gemv2_` visible, `_lmhead_argmax_kernel_simd_i8` ->
    `lmhead_argm` visible). TWO real, measured failures while landing this pair, in order:

    1. An EARLIER, since-abandoned naming attempt (`_attn_splitk_partial_kernel_simd` / `_attn_
       splitk_merge_kernel_simd`) shared an 11-character prefix (`attn_splitk`) and surfaced as two
       IDENTICAL visible names — this struct's constructor raised `MB_ERR_PIPELINE_NOT_FOUND` for
       both. Renamed to the current `_splitk_partial_kernel_simd` / `_splitk_merge_kernel_simd`,
       whose shared prefix is only `splitk_` (7 characters), diverging (`p` vs `m`) at character 8 —
       inside the 11-character surviving window.
    2. Even after that rename, matching against the FULL kernel names (`splitk_partial`, 14
       characters; `splitk_merge`, 12) STILL failed the same way — `.find()` was searching for
       characters (`ial` / the trailing `e`) that the 11-character truncation had already cut off
       the discovered name entirely, so neither substring could ever be present no matter how the
       kernels were named. The fix is the patterns below: `splitk_part` / `splitk_merg`, each exactly
       the 11 characters this measurement shows genuinely survive — not a shorter, easier-to-write
       guess, the ACTUAL boundary."""
    if name.find("splitk_part") >= 0:
        return 0
    if name.find("splitk_merg") >= 0:
        return 1
    return -1


@fieldwise_init
struct _StepOut(Copyable, Movable):
    var token_id: Int
    var logit: Float64
    var dispatches: Int
    var status: Int


@fieldwise_init
struct _MBLayerBufI8(Copyable, Movable):
    """The int8-weight twin of `_MBLayerBuf`: the four GEMV weight matrices' shim-allocated buffers
    are Int8 storage, each with its OWN companion Float32 per-output-row scale buffer (gpuAddress +
    CPU pointer pair, same as every other buffer in this file) — mirrors
    `residentk.session._LayerGpuI8` exactly, ported to raw shim pointers the same way `_MBLayerBuf`
    itself mirrors `residentk.session._LayerGpu`."""

    var ln1_addr: UInt64
    var ln1_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var ln2_addr: UInt64
    var ln2_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var qn_addr: UInt64
    var qn_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var kn_addr: UInt64
    var kn_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_qkv_addr: UInt64
    var w_qkv_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_qkv_scale_addr: UInt64
    var w_qkv_scale_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_o_addr: UInt64
    var w_o_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_o_scale_addr: UInt64
    var w_o_scale_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_gu_addr: UInt64
    var w_gu_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_gu_scale_addr: UInt64
    var w_gu_scale_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_down_addr: UInt64
    var w_down_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_down_scale_addr: UInt64
    var w_down_scale_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var ck_addr: UInt64
    var ck_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var cv_addr: UInt64
    var cv_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]


@fieldwise_init
struct _MBLayerBuf(Copyable, Movable):
    """One transformer layer's resident buffers: gpuAddress (for kernel args) + CPU pointer (for
    upload), one pair per tensor. Same four-matrix packing `residentk.session._LayerGpu` uses."""

    var ln1_addr: UInt64
    var ln1_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var ln2_addr: UInt64
    var ln2_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var qn_addr: UInt64
    var qn_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var kn_addr: UInt64
    var kn_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_qkv_addr: UInt64
    var w_qkv_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_o_addr: UInt64
    var w_o_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_gu_addr: UInt64
    var w_gu_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var w_down_addr: UInt64
    var w_down_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var ck_addr: UInt64
    var ck_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
    var cv_addr: UInt64
    var cv_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]


fn _narrow_into(
    dst: UnsafePointer[UInt8, origin=MutAnyOrigin], src: List[Float64], n: Int, dst_off: Int
) raises -> Int:
    """Narrow `n` Float64 elements into a raw Float32 device pointer at `dst_off`. Same one-time
    conversion `residentk.session._narrow_into` performs, ported from `DeviceBuffer.map_to_host()`
    to a plain pointer write (Shared storage is CPU-visible with no map/unmap step)."""
    if len(src) != n:
        return MB_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    var dp = dst.bitcast[Float32]()
    for i in range(n):
        dp[dst_off + i] = Float32(sp[i])
    return MB_OK


fn _narrow_transposed_into(
    dst: UnsafePointer[UInt8, origin=MutAnyOrigin], src: List[Float64], k_in: Int, n_out: Int, row_off: Int
) raises -> Int:
    """Narrow and transpose `[k_in, n_out]` Float64 into `[n_out, k_in]` Float32 at row `row_off`.
    Same blocked-tile arithmetic as `residentk.session._narrow_transposed_into` — see that
    function's docstring for why the layout and the tiling both matter."""
    if len(src) != k_in * n_out:
        return MB_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    var dp = dst.bitcast[Float32]()
    var i0 = 0
    while i0 < k_in:
        var i1 = i0 + _TILE
        if i1 > k_in:
            i1 = k_in
        var j0 = 0
        while j0 < n_out:
            var j1 = j0 + _TILE
            if j1 > n_out:
                j1 = n_out
            for j in range(j0, j1):
                var dbase = (row_off + j) * k_in
                for i in range(i0, i1):
                    dp[dbase + i] = Float32(sp[i * n_out + j])
            j0 = j1
        i0 = i1
    return MB_OK


fn _narrow_into_f16(
    dst: UnsafePointer[UInt8, origin=MutAnyOrigin], src: List[Float64], n: Int, dst_off: Int
) raises -> Int:
    """The fp16 twin of `_narrow_into`: Float64 -> Float16, no transpose. Same arithmetic as
    `residentk.session._narrow_into_f16`, ported from `DeviceBuffer.map_to_host()` to a plain
    pointer write (Shared storage needs no map/unmap step)."""
    if len(src) != n:
        return MB_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    var dp = dst.bitcast[Float16]()
    for i in range(n):
        dp[dst_off + i] = Float16(Float32(sp[i]))
    return MB_OK


fn _narrow_transposed_into_f16(
    dst: UnsafePointer[UInt8, origin=MutAnyOrigin], src: List[Float64], k_in: Int, n_out: Int, row_off: Int
) raises -> Int:
    """The fp16 twin of `_narrow_transposed_into`: Float64 -> Float16, WITH the same blocked
    `[k_in, n_out]` -> `[n_out, k_in]` transpose. Same arithmetic as
    `residentk.session._narrow_transposed_into_f16`, ported to a raw pointer."""
    if len(src) != k_in * n_out:
        return MB_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    var dp = dst.bitcast[Float16]()
    var i0 = 0
    while i0 < k_in:
        var i1 = i0 + _TILE
        if i1 > k_in:
            i1 = k_in
        var j0 = 0
        while j0 < n_out:
            var j1 = j0 + _TILE
            if j1 > n_out:
                j1 = n_out
            for j in range(j0, j1):
                var dbase = (row_off + j) * k_in
                for i in range(i0, i1):
                    dp[dbase + i] = Float16(Float32(sp[i * n_out + j]))
            j0 = j1
        i0 = i1
    return MB_OK


comptime _I8_MAX: Float64 = 127.0
"""Same symmetric-range choice as `residentk.session._I8_MAX` — see that constant's docstring."""


fn _quantize_row_i8(v: Float64, inv_scale: Float64) -> Int8:
    """Round-half-away-from-zero, clamp to `[-127, 127]`. Byte-identical arithmetic to
    `residentk.session._quantize_row_i8`, restated here rather than imported because that function
    is module-private to `residentk.session` and not re-exported (the same restraint
    `metaldispatch.session._LM_BLOCKS`'s own docstring explains for a duplicated constant — the
    VALUE and the ARITHMETIC are not new, only the call site)."""
    var q = v * inv_scale
    var r = Int(q + 0.5) if q >= 0.0 else Int(q - 0.5)
    if r > 127:
        r = 127
    if r < -127:
        r = -127
    return Int8(r)


fn _quantize_into_i8(
    dst_w: UnsafePointer[UInt8, origin=MutAnyOrigin],
    dst_scale: UnsafePointer[UInt8, origin=MutAnyOrigin],
    src: List[Float64], n_rows: Int, width: Int, row_off: Int, scale_off: Int,
) raises -> Int:
    """Per-output-row symmetric int8 quantization, NO transpose — the shim-pointer twin of
    `residentk.session._quantize_into_i8`. Used only for the tied embedding/lm_head table; see that
    function's docstring for the quantization scheme."""
    if len(src) != n_rows * width:
        return MB_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    var dw = dst_w.bitcast[Int8]()
    var ds = dst_scale.bitcast[Float32]()
    for r in range(n_rows):
        var base = r * width
        var maxabs = 0.0
        for i in range(width):
            var av = abs(sp[base + i])
            if av > maxabs:
                maxabs = av
        var scale = (maxabs / _I8_MAX) if maxabs > 0.0 else 1.0
        ds[scale_off + r] = Float32(scale)
        var inv_scale = 1.0 / scale
        var dbase = (row_off + r) * width
        for i in range(width):
            dw[dbase + i] = _quantize_row_i8(sp[base + i], inv_scale)
    return MB_OK


fn _quantize_transposed_into_i8(
    dst_w: UnsafePointer[UInt8, origin=MutAnyOrigin],
    dst_scale: UnsafePointer[UInt8, origin=MutAnyOrigin],
    src: List[Float64], k_in: Int, n_out: Int, row_off: Int, scale_off: Int,
) raises -> Int:
    """Narrow, TRANSPOSE, and per-output-row symmetric-int8-quantize — the shim-pointer twin of
    `residentk.session._quantize_transposed_into_i8`. Same two-blocked-passes structure as that
    function (a row's scale depends on every element of the row, so no element quantizes until the
    whole row is scanned); see that function's docstring for why blocking is used twice."""
    if len(src) != k_in * n_out:
        return MB_ERR_UPLOAD_LENGTH
    var sp = src.unsafe_ptr()
    var dw = dst_w.bitcast[Int8]()
    var ds = dst_scale.bitcast[Float32]()

    # ── pass 1: per-row max |value|, blocked, then converted to a scale ──
    for j in range(n_out):
        ds[scale_off + j] = 0.0
    var i0 = 0
    while i0 < k_in:
        var i1 = i0 + _TILE
        if i1 > k_in:
            i1 = k_in
        var j0 = 0
        while j0 < n_out:
            var j1 = j0 + _TILE
            if j1 > n_out:
                j1 = n_out
            for j in range(j0, j1):
                var m = ds[scale_off + j]
                for i in range(i0, i1):
                    var av = Float32(abs(sp[i * n_out + j]))
                    if av > m:
                        m = av
                ds[scale_off + j] = m
            j0 = j1
        i0 = i1
    for j in range(n_out):
        var m = ds[scale_off + j]
        ds[scale_off + j] = (m / Float32(_I8_MAX)) if m > 0.0 else 1.0

    # ── pass 2: transpose + quantize, using the now-fixed scale ──
    var i0b = 0
    while i0b < k_in:
        var i1b = i0b + _TILE
        if i1b > k_in:
            i1b = k_in
        var j0b = 0
        while j0b < n_out:
            var j1b = j0b + _TILE
            if j1b > n_out:
                j1b = n_out
            for j in range(j0b, j1b):
                var scale = Float64(ds[scale_off + j])
                var inv_scale = 1.0 / scale
                var dbase = (row_off + j) * k_in
                for i in range(i0b, i1b):
                    dw[dbase + i] = _quantize_row_i8(sp[i * n_out + j], inv_scale)
            j0b = j1b
        i0b = i1b
    return MB_OK


struct _MBQwen3(Movable):
    """Everything a batched-shim decode session holds, alive across the whole generation. See the
    module docstring for why these are shim-allocated Metal buffers rather than `residentk`'s own
    `DeviceBuffer`s."""

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

    var pipeline_idx: List[Int]  # role -> discovered pipeline index, length _N_ROLES

    var layers: List[_MBLayerBuf]
    var embed_addr: UInt64
    var embed_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
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
    var token_id_offset: Int      # arg slot, desc 0 (embed)
    var pos_offsets: List[Int]    # one per layer, the qk_rope descriptor's `pos` arg
    var nkeys_offsets: List[Int]  # one per layer, the sdpa descriptor's `n_keys` arg

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """Open the shim session, resolve every pipeline by name, allocate every resident buffer,
        and build the (mostly-static) descriptor array. Called only from inside a `@parameter if
        MB_GPU_BUILD` branch — see the module docstring on why a constructor cannot carry the gate
        itself."""
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

        # ── force every kernel to be compiled + embedded in THIS binary's __TEXT,__const ──
        # `compile_function_unchecked` forces codegen; the DeviceContext it needs exists only for
        # that side effect and is dropped immediately after — this package does not dispatch
        # through it, the shim does.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )

        # ── resident buffers, identical shapes to residentk.session._ResidentQwen3 ──
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_MBLayerBuf]()
        for _ in range(n_layers):
            var ln1a = UInt64(0); var ln1p = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var ln2a = UInt64(0); var ln2p = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var qna = UInt64(0); var qnp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var kna = UInt64(0); var knp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wqkva = UInt64(0); var wqkvp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var woa = UInt64(0); var wop = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wgua = UInt64(0); var wgup = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wdowna = UInt64(0); var wdownp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
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
            if _mb_alloc_buffer(n_qkv * d_model * 4, wqkva, wqkvp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_qkv)")
            if _mb_alloc_buffer(d_model * h_q * d_head * 4, woa, wop) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_o)")
            if _mb_alloc_buffer(2 * d_ff * d_model * 4, wgua, wgup) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_gu)")
            if _mb_alloc_buffer(d_model * d_ff * 4, wdowna, wdownp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_down)")
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 4, cka, ckp) < 0:
                raise Error("metaldispatch: buffer alloc failed (ck)")
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 4, cva, cvp) < 0:
                raise Error("metaldispatch: buffer alloc failed (cv)")
            self.layers.append(_MBLayerBuf(
                ln1a, ln1p, ln2a, ln2p, qna, qnp, kna, knp, wqkva, wqkvp,
                woa, wop, wgua, wgup, wdowna, wdownp, cka, ckp, cva, cvp,
            ))

        self.embed_addr = UInt64(0); self.embed_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.final_norm_addr = UInt64(0); self.final_norm_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.cos_addr = UInt64(0); self.cos_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.sin_addr = UInt64(0); self.sin_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        if _mb_alloc_buffer(vocab * d_model * 4, self.embed_addr, self.embed_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (embed)")
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

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()
        self._build_descriptors(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
        """Build every one of `n_descriptors` dispatch descriptors ONCE. `token_id`, `pos` and
        `n_keys` are written as placeholder `0`; `step()` patches only those slots per call — see
        the module docstring's pipeline-discovery note and `residentk.session.step`'s own dispatch
        sequence, which this mirrors exactly, one descriptor per launch there."""
        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        var d = 0

        _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_EMBED], _ceil_div(self.d_model, _TG), _TG, 4)
        _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors, d, 1, self.embed_addr)
        _mb_set_arg_int(self.descriptors, d, 2, 0)  # token_id, patched per step
        self.token_id_offset = d
        _mb_set_arg_int(self.descriptors, d, 3, self.d_model)
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_NORM_GEMV],
                _ceil_div(n_qkv, _SUBS), _TG, 7,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.ln1_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_qkv_addr)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            _mb_set_arg_int(self.descriptors, d, 5, n_qkv)
            _mb_set_arg_f32(self.descriptors, d, 6, self.eps)
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
                _ceil_div(self.d_model, _SUBS), _TG, 5,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.w_o_addr)
            _mb_set_arg_int(self.descriptors, d, 3, n_q)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_NORM_GEMV2_SWIGLU],
                _ceil_div(self.d_ff, _SUBS), _TG, 7,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.ln2_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_gu_addr)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            _mb_set_arg_int(self.descriptors, d, 5, self.d_ff)
            _mb_set_arg_f32(self.descriptors, d, 6, self.eps)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 5,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.w_down_addr)
            _mb_set_arg_int(self.descriptors, d, 3, self.d_ff)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            d += 1

        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 9)
        _mb_set_arg_ptr(self.descriptors, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors, d, 2, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors, d, 4, self.embed_addr)
        _mb_set_arg_int(self.descriptors, d, 5, self.d_model)
        _mb_set_arg_int(self.descriptors, d, 6, self.vocab)
        _mb_set_arg_f32(self.descriptors, d, 7, self.eps)
        _mb_set_arg_int(self.descriptors, d, 8, n_iters)
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

    fn device_name(self) -> String:
        return "metal (batched shim)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return MB_ERR_CONTEXT_FULL
        var s = _narrow_into(self.embed_ptr, embed, self.vocab * self.d_model, 0)
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

    fn upload_layer(
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
        s = _narrow_transposed_into(lw.w_qkv_ptr, wq, self.d_model, n_q, 0)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into(lw.w_qkv_ptr, wk, self.d_model, n_kv, n_q)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into(lw.w_qkv_ptr, wv, self.d_model, n_kv, n_q + n_kv)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into(lw.w_o_ptr, wo, n_q, self.d_model, 0)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into(lw.w_gu_ptr, wgate, self.d_model, self.d_ff, 0)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into(lw.w_gu_ptr, wup, self.d_model, self.d_ff, self.d_ff)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into(lw.w_down_ptr, wdown, self.d_ff, self.d_model, 0)
        if s != MB_OK:
            return s
        return MB_OK

    fn seal(mut self) -> Int:
        """No-op: Shared-storage buffers are CPU/GPU coherent as soon as they're written, unlike
        `residentk.session.seal`'s `ctx.synchronize()` drain of MAX's own upload queue. Kept as a
        function so the two sessions' driver code reads identically."""
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """ONE token, dispatched as ONE call into the shim. Patches the small set of per-token-
        varying scalar argument slots (`token_id` once, `pos`/`n_keys` once per layer — the VALUES
        are the same across all layers of one step, only the identity of which descriptor holds
        them differs), then issues every descriptor behind a single command buffer/encoder/commit/
        wait inside `algenta_run_token`."""

        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            _mb_set_arg_int(self.descriptors, self.token_id_offset, 2, token_id)
            var n_keys = pos + 1
            for layer in range(self.n_layers):
                _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

            var rc = _mb_run_token(self.descriptors, self.n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors, MB_OK)


struct _MBQwen3F16(Movable):
    """The fp16-weight twin of `_MBQwen3`: identical descriptor plan, identical `step()` contract,
    dispatched through the SAME batched shim — the only difference is that the four GEMV weight
    matrices per layer plus the tied `embed`/lm_head table are resident as Float16 rather than
    Float32, read through `residentk.kernels`' `_f16` twins. Mirrors
    `residentk.session._ResidentQwen3F16` exactly (mixed precision: activations, the KV cache, norm
    gains and RoPE tables all stay Float32 — see that struct's own docstring for why).

    MUST be built into its OWN binary (`qwen3_generate_batch_f16.mojo`), never alongside
    `_MBQwen3` in the same one — see the module docstring's "separate binary" section for why:
    compiling both a role's Float32 and Float16 kernel into the same binary makes the two
    pipelines' truncated Metal names collide, and `_classify_pipeline` has no way to tell them
    apart. This struct's constructor therefore never calls `compile_function_unchecked` on
    `_norm_gemv_kernel`/`_gemv_accum_kernel`/`_norm_gemv2_swiglu_kernel`/`_lmhead_argmax_kernel`/
    `_embed_row_kernel` (the Float32 GEMV-shaped kernels) — only their `_f16` twins, plus the three
    shared kernels (`_qk_rope_write_kernel`, `_sdpa_kernel`, `_argmax_reduce_kernel`) that have no
    fp16 variant at all, exactly as `_ResidentQwen3F16` compiles them.
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

    var pipeline_idx: List[Int]  # role -> discovered pipeline index, length _N_ROLES

    var layers: List[_MBLayerBuf]
    var embed_addr: UInt64
    var embed_ptr: UnsafePointer[UInt8, origin=MutAnyOrigin]
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

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
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

        # ── force every kernel THIS ARM needs to be compiled + embedded in THIS binary's
        # __TEXT,__const — the fp16 GEMV-shaped twins plus the three kernels with no fp16 variant.
        # Deliberately NEVER the Float32 GEMV-shaped kernels — see the struct docstring.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel_f16]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel_f16]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel_f16]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_f16]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel_f16]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )

        # ── resident buffers: SAME shapes as _MBQwen3, but the four GEMV weight matrices per
        # layer and `embed` are half the byte size (Float16, 2 bytes/element, vs Float32's 4).
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

        self.layers = List[_MBLayerBuf]()
        for _ in range(n_layers):
            var ln1a = UInt64(0); var ln1p = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var ln2a = UInt64(0); var ln2p = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var qna = UInt64(0); var qnp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var kna = UInt64(0); var knp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wqkva = UInt64(0); var wqkvp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var woa = UInt64(0); var wop = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wgua = UInt64(0); var wgup = UnsafePointer[UInt8, origin=MutAnyOrigin]()
            var wdowna = UInt64(0); var wdownp = UnsafePointer[UInt8, origin=MutAnyOrigin]()
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
            if _mb_alloc_buffer(n_qkv * d_model * 2, wqkva, wqkvp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_qkv f16)")
            if _mb_alloc_buffer(d_model * h_q * d_head * 2, woa, wop) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_o f16)")
            if _mb_alloc_buffer(2 * d_ff * d_model * 2, wgua, wgup) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_gu f16)")
            if _mb_alloc_buffer(d_model * d_ff * 2, wdowna, wdownp) < 0:
                raise Error("metaldispatch: buffer alloc failed (w_down f16)")
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 4, cka, ckp) < 0:
                raise Error("metaldispatch: buffer alloc failed (ck)")
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 4, cva, cvp) < 0:
                raise Error("metaldispatch: buffer alloc failed (cv)")
            self.layers.append(_MBLayerBuf(
                ln1a, ln1p, ln2a, ln2p, qna, qnp, kna, knp, wqkva, wqkvp,
                woa, wop, wgua, wgup, wdowna, wdownp, cka, ckp, cva, cvp,
            ))

        self.embed_addr = UInt64(0); self.embed_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.final_norm_addr = UInt64(0); self.final_norm_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.cos_addr = UInt64(0); self.cos_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.sin_addr = UInt64(0); self.sin_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        if _mb_alloc_buffer(vocab * d_model * 2, self.embed_addr, self.embed_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (embed f16)")
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

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()
        self._build_descriptors(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
        """Byte-for-byte the same descriptor plan as `_MBQwen3._build_descriptors` — same roles,
        same grid/threadgroup shapes, same argument SLOTS. Only the buffer addresses bound at each
        pointer slot differ (the fp16-sized ones above); a kernel argument slot's tag is still
        `MB_TAG_PTR` either way, since the shim binds a pointer argument as an address VALUE
        regardless of what the address points at."""
        var n_q = self.h_q * self.d_head
        var n_kv = self.h_kv * self.d_head
        var d = 0

        _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_EMBED], _ceil_div(self.d_model, _TG), _TG, 4)
        _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors, d, 1, self.embed_addr)
        _mb_set_arg_int(self.descriptors, d, 2, 0)  # token_id, patched per step
        self.token_id_offset = d
        _mb_set_arg_int(self.descriptors, d, 3, self.d_model)
        d += 1

        for layer in range(self.n_layers):
            ref lw = self.layers[layer]

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_NORM_GEMV],
                _ceil_div(n_qkv, _SUBS), _TG, 7,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.qkv_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.ln1_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_qkv_addr)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            _mb_set_arg_int(self.descriptors, d, 5, n_qkv)
            _mb_set_arg_f32(self.descriptors, d, 6, self.eps)
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
                _ceil_div(self.d_model, _SUBS), _TG, 5,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.w_o_addr)
            _mb_set_arg_int(self.descriptors, d, 3, n_q)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_NORM_GEMV2_SWIGLU],
                _ceil_div(self.d_ff, _SUBS), _TG, 7,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.act_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.ln2_addr)
            _mb_set_arg_ptr(self.descriptors, d, 3, lw.w_gu_addr)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            _mb_set_arg_int(self.descriptors, d, 5, self.d_ff)
            _mb_set_arg_f32(self.descriptors, d, 6, self.eps)
            d += 1

            _mb_set_header(
                self.descriptors, d, self.pipeline_idx[_ROLE_GEMV_ACCUM],
                _ceil_div(self.d_model, _SUBS), _TG, 5,
            )
            _mb_set_arg_ptr(self.descriptors, d, 0, self.hidden_addr)
            _mb_set_arg_ptr(self.descriptors, d, 1, self.act_addr)
            _mb_set_arg_ptr(self.descriptors, d, 2, lw.w_down_addr)
            _mb_set_arg_int(self.descriptors, d, 3, self.d_ff)
            _mb_set_arg_int(self.descriptors, d, 4, self.d_model)
            d += 1

        var n_iters = _ceil_div(self.vocab, _LM_BLOCKS * _SUBS)
        _mb_set_header(self.descriptors, d, self.pipeline_idx[_ROLE_LMHEAD_ARGMAX], _LM_BLOCKS, _TG, 9)
        _mb_set_arg_ptr(self.descriptors, d, 0, self.blk_val_addr)
        _mb_set_arg_ptr(self.descriptors, d, 1, self.blk_idx_addr)
        _mb_set_arg_ptr(self.descriptors, d, 2, self.hidden_addr)
        _mb_set_arg_ptr(self.descriptors, d, 3, self.final_norm_addr)
        _mb_set_arg_ptr(self.descriptors, d, 4, self.embed_addr)
        _mb_set_arg_int(self.descriptors, d, 5, self.d_model)
        _mb_set_arg_int(self.descriptors, d, 6, self.vocab)
        _mb_set_arg_f32(self.descriptors, d, 7, self.eps)
        _mb_set_arg_int(self.descriptors, d, 8, n_iters)
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

    fn device_name(self) -> String:
        return "metal (batched shim, fp16 weights)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """The tied embedding/lm_head table narrowed to Float16; the final norm gain and RoPE
        tables stay Float32 — same split as `_ResidentQwen3F16.upload_globals`."""
        var n_pairs = self.d_head // 2
        if n_pos > self.max_ctx:
            return MB_ERR_CONTEXT_FULL
        var s = _narrow_into_f16(self.embed_ptr, embed, self.vocab * self.d_model, 0)
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

    fn upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """Norm gains narrowed to Float32 exactly as `_MBQwen3.upload_layer` does; the four GEMV
        weight matrices narrowed (and transposed) to Float16 instead."""
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
        s = _narrow_transposed_into_f16(lw.w_qkv_ptr, wq, self.d_model, n_q, 0)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_qkv_ptr, wk, self.d_model, n_kv, n_q)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_qkv_ptr, wv, self.d_model, n_kv, n_q + n_kv)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_o_ptr, wo, n_q, self.d_model, 0)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_gu_ptr, wgate, self.d_model, self.d_ff, 0)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_gu_ptr, wup, self.d_model, self.d_ff, self.d_ff)
        if s != MB_OK:
            return s
        s = _narrow_transposed_into_f16(lw.w_down_ptr, wdown, self.d_ff, self.d_model, 0)
        if s != MB_OK:
            return s
        return MB_OK

    fn seal(mut self) -> Int:
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-for-byte `_MBQwen3.step`'s own body — see that function's docstring. Duplicated
        rather than shared because Mojo has no common base for two structs with different field
        sets to dispatch through; the STEPS taken are identical, only the resident buffers a few of
        this struct's OWN fields point at differ."""

        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            _mb_set_arg_int(self.descriptors, self.token_id_offset, 2, token_id)
            var n_keys = pos + 1
            for layer in range(self.n_layers):
                _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

            var rc = _mb_run_token(self.descriptors, self.n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors, MB_OK)


struct _MBQwen3I8(Movable):
    """The int8-weight twin of `_MBQwen3`/`_MBQwen3F16`: identical descriptor plan, identical
    `step()` contract, dispatched through the SAME batched shim — the four GEMV weight matrices per
    layer plus the tied `embed`/lm_head table are resident as Int8, each with a companion
    per-output-row Float32 scale buffer, read through `residentk.kernels`' `_i8` kernel twins.
    Mirrors `_MBQwen3F16` exactly, with one structural difference the weight-plus-scale format
    forces: every descriptor for a GEMV-shaped role (`_ROLE_EMBED`, `_ROLE_NORM_GEMV`,
    `_ROLE_GEMV_ACCUM`, `_ROLE_NORM_GEMV2_SWIGLU`, `_ROLE_LMHEAD_ARGMAX`) carries one MORE pointer
    argument than its Float32/Float16 counterpart — the row-scale buffer — so `_build_descriptors`
    below is not byte-identical to either sibling's, only structurally identical (same roles, same
    grid/threadgroup shapes, same PER-STEP-varying slots).

    MUST be built into its OWN binary (`qwen3_generate_batch_i8.mojo`), never alongside `_MBQwen3`
    or `_MBQwen3F16` in the same one — see the module docstring's "separate binary" section: any
    two of a role's Float32/Float16/Int8 pipelines compiled into the same binary collide under the
    truncated-name classifier the same way the Float32/Float16 pair did. This struct's constructor
    therefore never calls `compile_function_unchecked` on the Float32 or Float16 GEMV-shaped
    kernels — only the `_i8` twins, plus the three shared kernels
    (`_qk_rope_write_kernel`/`_sdpa_kernel`/`_argmax_reduce_kernel`) that have no per-dtype variant
    at all, exactly as `_MBQwen3F16` compiles them.
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

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
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

        # ── force every kernel THIS ARM needs to be compiled + embedded in THIS binary's
        # __TEXT,__const — the int8 GEMV-shaped twins plus the three kernels with no per-dtype
        # variant. Deliberately NEVER the Float32 or Float16 GEMV-shaped kernels — see the struct
        # docstring.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel_i8]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_i8]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )

        # ── resident buffers: SAME shapes as _MBQwen3, but the four GEMV weight matrices per
        # layer and `embed` are Int8 (1 byte/element), each with its own Float32 (4 bytes/row)
        # per-output-row scale buffer.
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

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()
        self._build_descriptors(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
        """Same descriptor PLAN as `_MBQwen3`/`_MBQwen3F16`'s own — same roles, same grid/
        threadgroup shapes, same per-step-varying slots — but every GEMV-shaped role's descriptor
        carries one more pointer argument: that matrix's per-output-row scale buffer, positioned
        immediately after the weight-matrix pointer, matching `residentk.kernels`' `_i8` kernel
        signatures (`w` then `wscale`) exactly."""
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

    fn device_name(self) -> String:
        return "metal (batched shim, int8 weights)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
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

    fn upload_layer(
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

    fn seal(mut self) -> Int:
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-for-byte `_MBQwen3.step`'s/`_MBQwen3F16.step`'s own body — see `_MBQwen3.step`'s
        docstring."""

        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            _mb_set_arg_int(self.descriptors, self.token_id_offset, 3, token_id)
            var n_keys = pos + 1
            for layer in range(self.n_layers):
                _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

            var rc = _mb_run_token(self.descriptors, self.n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors, MB_OK)


struct _MBQwen3I8SDPASimd(Movable):
    """The SDPA-reduction-mechanism twin of `_MBQwen3I8`: identical descriptor plan, identical
    `step()` contract, identical int8 weight storage (`_MBLayerBufI8`, the `_i8` kernel twins,
    the per-output-row Float32 scales) — the ONLY difference from `_MBQwen3I8` is that the SDPA
    role dispatches through `residentk.kernels._sdpa_kernel_simd` instead of `_sdpa_kernel`.

    `_sdpa_kernel_simd` computes IDENTICAL online-softmax math over the IDENTICAL Float32 KV
    cache `_sdpa_kernel` uses — only HOW each key's `d_head`-wide dot product collapses to one
    scalar differs (hardware SIMD-group shuffle reduction, two `barrier()` calls per key, instead
    of a shared-memory tree with nine). See `_sdpa_kernel_simd`'s own docstring for the mechanism
    and PR #510/#512's GPU-counter findings this arm's task responds to.

    MUST be built into its OWN binary, never alongside `_MBQwen3I8` (or `_MBQwen3`/`_MBQwen3F16`) —
    see the module docstring's "separate binary" section and `_MBQwen3I8`'s own docstring: two
    pipelines answering to the same `_classify_pipeline` substring ("sdpa") compiled into one binary
    collide under the truncated-name classifier with no way to tell them apart. This struct's
    constructor therefore never calls `compile_function_unchecked` on `_sdpa_kernel` — only
    `_sdpa_kernel_simd`, exactly the same one-pipeline-per-role discipline `_MBQwen3I8`'s own
    constructor already follows for the GEMV-shaped roles across the Float32/Float16/Int8 arms.
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

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """REFUSES a `d_head` that is not an exact multiple of `std.gpu.WARP_SIZE` (32 on this
        Apple GPU target), BEFORE any GPU work happens -- see `_ResidentQwen3I8SDPASimd.__init__`'s
        own docstring in `residentk.session` for why: `_sdpa_kernel_simd`'s two-level reduction
        assumes every `d_head / WARP_SIZE` SIMD-group launched is FULLY populated, which Qwen3-
        0.6B's real `d_head = 128` (four full groups) satisfies cleanly but an arbitrary shape
        might not.
        """
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8SDPASimd: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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

        # ── force every kernel THIS ARM needs to be compiled + embedded in THIS binary's
        # __TEXT,__const — the int8 GEMV-shaped twins plus the three kernels with no per-dtype
        # variant. Deliberately NEVER the Float32 or Float16 GEMV-shaped kernels — see the struct
        # docstring.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel_i8]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_i8]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel_simd]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )

        # ── resident buffers: SAME shapes as _MBQwen3, but the four GEMV weight matrices per
        # layer and `embed` are Int8 (1 byte/element), each with its own Float32 (4 bytes/row)
        # per-output-row scale buffer.
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

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()
        self._build_descriptors(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
        """Same descriptor PLAN as `_MBQwen3`/`_MBQwen3F16`'s own — same roles, same grid/
        threadgroup shapes, same per-step-varying slots — but every GEMV-shaped role's descriptor
        carries one more pointer argument: that matrix's per-output-row scale buffer, positioned
        immediately after the weight-matrix pointer, matching `residentk.kernels`' `_i8` kernel
        signatures (`w` then `wscale`) exactly."""
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

    fn device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA SIMD-shuffle reduction)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
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

    fn upload_layer(
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

    fn seal(mut self) -> Int:
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-for-byte `_MBQwen3.step`'s/`_MBQwen3F16.step`'s own body — see `_MBQwen3.step`'s
        docstring."""

        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            _mb_set_arg_int(self.descriptors, self.token_id_offset, 3, token_id)
            var n_keys = pos + 1
            for layer in range(self.n_layers):
                _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

            var rc = _mb_run_token(self.descriptors, self.n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors, MB_OK)


struct _MBQwen3I8AllSimd(Movable):
    """The GEMV-reduction-mechanism twin of `_MBQwen3I8SDPASimd`: identical descriptor plan,
    identical `step()` contract, identical int8 weight storage (`_MBLayerBufI8`), identical
    `_sdpa_kernel_simd` SDPA role — the ONLY difference from `_MBQwen3I8SDPASimd` is that the
    three GEMV-shaped roles (`norm_gemv`/QKV-proj, `gemv_accum`/o_proj+down_proj,
    `norm_gemv2_swiglu`/gate-up) now dispatch through `residentk.kernels._norm_gemv_kernel_simd_i8`,
    `_gemv_accum_kernel_simd_i8`, `_norm_gemv2_swiglu_kernel_simd_i8` instead of their barrier-tree
    `_i8` twins. This struct therefore composes BOTH reduction-mechanism fixes shipped so far —
    SDPA-simd (already `_MBQwen3I8SDPASimd`'s own, and today's production SDPA role) plus this
    struct's own new GEMV-simd, since `_MBQwen3I8` itself (barrier-tree everywhere) is not what
    production runs anymore.

    Each of the three new kernels computes IDENTICAL math to its `_i8` twin — only HOW their
    reductions collapse to a scalar differs. See `_norm_gemv_kernel_simd_i8`'s own docstring in
    `residentk.kernels` for the full account: a `_TG = 256`-wide sum-of-squares reduction (fixed
    the SAME multi-SIMD-group way `_sdpa_kernel_simd` fixed its own) plus one or two `_LANES = 32`-
    wide per-output-column dot-product reductions (needing NO cross-group combine at all, unlike
    `_sdpa_kernel_simd`'s cross-group softmax score, since one SIMD group maps 1:1 to one
    independent output column).

    MUST be built into its OWN binary, never alongside `_MBQwen3I8`/`_MBQwen3I8SDPASimd` (or
    `_MBQwen3`/`_MBQwen3F16`) — see the module docstring's "separate binary" section and
    `_MBQwen3I8`'s own docstring: `_classify_pipeline` matches by ROLE substring
    ("norm_gemv"/"gemv_accum"/"norm_gemv2"/"sdpa"), not by exact kernel variant, so two pipelines
    for the SAME role compiled into one binary would collide with no way to tell them apart. This
    struct's constructor therefore never calls `compile_function_unchecked` on any of the four
    barrier-tree kernels it replaces — only their four `_simd` twins, exactly the same
    one-pipeline-per-role discipline `_MBQwen3I8SDPASimd`'s own constructor already follows.
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

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """REFUSES a `d_head` that is not an exact multiple of `std.gpu.WARP_SIZE` (32 on this
        Apple GPU target), BEFORE any GPU work happens -- see `_ResidentQwen3I8SDPASimd.__init__`'s
        own docstring in `residentk.session` for why: `_sdpa_kernel_simd`'s two-level reduction
        assumes every `d_head / WARP_SIZE` SIMD-group launched is FULLY populated, which Qwen3-
        0.6B's real `d_head = 128` (four full groups) satisfies cleanly but an arbitrary shape
        might not.
        """
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8AllSimd: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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

        # ── force every kernel THIS ARM needs to be compiled + embedded in THIS binary's
        # __TEXT,__const — the int8 GEMV-shaped twins plus the three kernels with no per-dtype
        # variant. Deliberately NEVER the Float32 or Float16 GEMV-shaped kernels — see the struct
        # docstring.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel_simd]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )

        # ── resident buffers: SAME shapes as _MBQwen3, but the four GEMV weight matrices per
        # layer and `embed` are Int8 (1 byte/element), each with its own Float32 (4 bytes/row)
        # per-output-row scale buffer.
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

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()
        self._build_descriptors(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
        """Same descriptor PLAN as `_MBQwen3`/`_MBQwen3F16`'s own — same roles, same grid/
        threadgroup shapes, same per-step-varying slots — but every GEMV-shaped role's descriptor
        carries one more pointer argument: that matrix's per-output-row scale buffer, positioned
        immediately after the weight-matrix pointer, matching `residentk.kernels`' `_i8` kernel
        signatures (`w` then `wscale`) exactly."""
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

    fn device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV SIMD-shuffle reduction)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
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

    fn upload_layer(
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

    fn seal(mut self) -> Int:
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-for-byte `_MBQwen3.step`'s/`_MBQwen3F16.step`'s own body — see `_MBQwen3.step`'s
        docstring."""

        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            _mb_set_arg_int(self.descriptors, self.token_id_offset, 3, token_id)
            var n_keys = pos + 1
            for layer in range(self.n_layers):
                _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

            var rc = _mb_run_token(self.descriptors, self.n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors, MB_OK)


struct _MBQwen3I8AllSimd2(Movable):
    """The LMHEAD-reduction-mechanism twin of `_MBQwen3I8AllSimd`: identical descriptor plan,
    identical `step()` contract, identical int8 weight storage, identical `_sdpa_kernel_simd` SDPA
    role, identical `_norm_gemv_kernel_simd_i8`/`_gemv_accum_kernel_simd_i8`/
    `_norm_gemv2_swiglu_kernel_simd_i8` GEMV-shaped roles — the ONLY difference from
    `_MBQwen3I8AllSimd` is that the `lm_head` role now dispatches through
    `residentk.kernels._lmhead_argmax_kernel_simd_i8` instead of its barrier-tree twin
    `_lmhead_argmax_kernel_i8`. This struct therefore composes ALL THREE reduction-mechanism fixes
    shipped so far — SDPA-simd, GEMV-simd (both already `_MBQwen3I8AllSimd`'s own) plus this
    struct's own new lm_head-simd — since `_lmhead_argmax_kernel_i8` is the single largest
    individual dispatch in the whole per-token cost (~12-13% of per-token GPU time per PR #510's
    counters) and had never been examined through this lens before.

    `_lmhead_argmax_kernel_simd_i8` computes IDENTICAL math to `_lmhead_argmax_kernel_i8` — only HOW
    its two internal reductions collapse to a scalar differs. See that kernel's own docstring in
    `residentk.kernels` for the full account: the SAME `_TG = 256`-wide sum-of-squares reduction
    `_norm_gemv_kernel_simd_i8`'s own stage 1 already fixed, run ONCE per launch, plus a `_LANES =
    32`-wide per-output-column dot-product-with-argmax reduction run ONCE PER ITERATION of the
    kernel's own grid-stride `it` loop (needing NO cross-group combine at all, same reasoning as
    every other per-column shape this file's siblings already fixed) — AND, because that stage
    never touches shared memory at all once the tree is gone, the tree version's own trailing
    per-iteration safety barrier has nothing left to guard either, so it drops too.

    MUST be built into its OWN binary, never alongside `_MBQwen3I8AllSimd` (or any other lm_head
    variant) — same truncated-Metal-AIR-name collision every sibling struct's own docstring
    documents: `_classify_pipeline` matches the `lmhead` role by substring, not by exact kernel
    variant, so two pipelines for the SAME role compiled into one binary would collide with no way
    to tell them apart. This struct's constructor therefore never calls
    `compile_function_unchecked` on the barrier-tree `_lmhead_argmax_kernel_i8` — only its `_simd`
    twin, exactly the same one-pipeline-per-role discipline every other struct in this file follows.
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

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """REFUSES a `d_head` that is not an exact multiple of `std.gpu.WARP_SIZE` (32 on this
        Apple GPU target), BEFORE any GPU work happens — see `_MBQwen3I8AllSimd.__init__`'s own
        docstring for why: `_sdpa_kernel_simd`'s two-level reduction assumes every `d_head /
        WARP_SIZE` SIMD-group launched is FULLY populated, unaffected by this struct's own
        lm_head-simd change.
        """
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8AllSimd2: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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

        # ── force every kernel THIS ARM needs to be compiled + embedded in THIS binary's
        # __TEXT,__const — the int8 GEMV-shaped twins, the lm_head-simd twin, plus the two kernels
        # with no per-dtype variant. Deliberately NEVER the Float32/Float16 GEMV-shaped kernels NOR
        # the barrier-tree `_lmhead_argmax_kernel_i8` — see the struct docstring.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel_simd]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
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

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()
        self._build_descriptors(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
        """Same descriptor PLAN as `_MBQwen3I8AllSimd`'s own — same roles, same grid/threadgroup
        shapes, same per-step-varying slots; the lm_head role's descriptor is unaffected (it still
        carries the SAME 10 arguments, `_lmhead_argmax_kernel_i8` and `_lmhead_argmax_kernel_simd_i8`
        share an identical signature), only which compiled pipeline `_ROLE_LMHEAD_ARGMAX` resolves
        to differs, decided entirely by which kernel this struct's constructor compiled."""
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

    fn device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV + lm_head SIMD-shuffle reduction)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
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

    fn upload_layer(
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

    fn seal(mut self) -> Int:
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-for-byte `_MBQwen3I8AllSimd.step`'s own body — see that function's docstring."""

        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            _mb_set_arg_int(self.descriptors, self.token_id_offset, 3, token_id)
            var n_keys = pos + 1
            for layer in range(self.n_layers):
                _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

            var rc = _mb_run_token(self.descriptors, self.n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors, MB_OK)


struct _MBQwen3I8AllSimd3(Movable):
    """The ARGMAX-REDUCE-reduction-mechanism twin of `_MBQwen3I8AllSimd2`: identical descriptor
    plan, identical `step()` contract, identical int8 weight storage, identical `_sdpa_kernel_simd`
    SDPA role, identical `_norm_gemv_kernel_simd_i8`/`_gemv_accum_kernel_simd_i8`/
    `_norm_gemv2_swiglu_kernel_simd_i8` GEMV-shaped roles, identical `_lmhead_argmax_kernel_simd_i8`
    lm_head role — the ONLY difference from `_MBQwen3I8AllSimd2` is that the `argmax_reduce` role
    (the SMALL, single-threadgroup dispatch that collapses `lm_head`'s per-block `(logit, id)` pairs
    to the one final pair) now dispatches through `residentk.kernels._argmax_reduce_kernel_simd`
    instead of its barrier-tree twin `_argmax_reduce_kernel`. This struct therefore composes ALL
    FOUR reduction-mechanism fixes this sweep has shipped — SDPA-simd (PR #513), GEMV-simd
    (PR #514), lm_head-simd (PR #515, both already `_MBQwen3I8AllSimd2`'s own) plus this struct's
    own new argmax-reduce-simd (PR #510's own count-every-barrier-tree sweep, closed out) — and is
    the LAST kernel in the decode path PR #510 named at all: every barrier-tree reduction that sweep
    identified has now been examined and fixed where a fix applies.

    `_argmax_reduce_kernel_simd` computes IDENTICAL math to `_argmax_reduce_kernel` — only HOW its
    single `_TG = 256`-wide combine collapses to a scalar differs. See that kernel's own docstring
    in `residentk.kernels` for the full account: a per-thread grid-stride local-best scan (unchanged
    register logic in both kernels), then a two-level combine — a hand-rolled `shuffle_xor`
    compare-exchange butterfly per 32-lane SIMD group (no barrier), then ONE shared-memory combine
    barrier across the `_SUBS = 8` per-group winners, then a final 8-way scalar combine by thread 0
    — replacing the original's `log2(256) = 8`-level barrier-synchronized halving tree (plus its own
    leading write-visibility barrier, 9 hits total). This is also the SMALLEST dispatch this whole
    sweep has touched (~0.3-0.4% of per-token GPU time per PR #510's counters, against `lm_head`'s
    own 12-13% or `sdpa`'s 26.85%) — landed anyway to complete the sweep, not because the measurable
    effect is expected to move the per-token total outside run-to-run noise.

    MUST be built into its OWN binary, never alongside `_MBQwen3I8AllSimd2` (or any other
    argmax_reduce variant) — same truncated-Metal-AIR-name collision every sibling struct's own
    docstring documents: `_classify_pipeline` matches the `argmax_redu` role by substring
    (`_argmax_reduce_kernel` and `_argmax_reduce_kernel_simd` both contain it), not by exact kernel
    variant, so two pipelines for the SAME role compiled into one binary would collide with no way
    to tell them apart. This struct's constructor therefore never calls
    `compile_function_unchecked` on the barrier-tree `_argmax_reduce_kernel` — only its `_simd`
    twin, exactly the same one-pipeline-per-role discipline every other struct in this file follows.

    A FIFTH addition, orthogonal to the four reduction-mechanism fixes above and landed later: this
    is also the arm PR #519's long-context investigation found degrading 21-29x faster with position
    than either of two real, installed opponents (mlx-lm, llama.cpp), root-caused to `_sdpa_kernel_
    simd`'s FIXED grid size (`grid_x=h_q`, independent of `n_keys`). This struct now holds TWO
    complete, independently-built descriptor tables — `self.descriptors` (this docstring's own plan,
    UNCHANGED) and `self.descriptors_deep` (`_build_descriptors_deep`'s plan, substituting
    `residentk.kernels._splitk_partial_kernel_simd` + `_splitk_merge_kernel_simd` for the
    one `_sdpa_kernel_simd` dispatch) — and `step()` picks between them per call based on `n_keys`
    against `_ATTN_SPLITK_THRESHOLD`. See `step()`'s own docstring for the gate and `_ATTN_SPLITK_
    THRESHOLD`/`_ATTN_SPLITK_N_SPLITS`'s own docstrings for the measurements that picked their
    values. `_sdpa_kernel_simd` itself, and every byte of the `self.descriptors` table and the
    branch that submits it, are UNTOUCHED by this addition — the published race's own short-context
    (16-token) behavior takes that exact, unmodified path.
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
    """See `_ATTN_SPLITK_THRESHOLD`'s own docstring and this struct's `step()` for the full account
    of the two fields above `descriptors_deep` onward: a SECOND, fully independent, fixed descriptor
    table built once at construction (`_build_descriptors_deep`) alongside the original
    `descriptors` — never a replacement for it. `step()` picks WHICH table to patch-and-submit each
    call based on the CURRENT `n_keys`; the other table's stale contents from a previous call simply
    do not matter until it is chosen again, at which point its own `pos`/`n_keys` slots are repatched
    fresh before submission — the same "mutate this step's arguments into an already-built plan"
    discipline `step()`'s pre-existing `pos_offsets`/`nkeys_offsets` patching already relies on, just
    duplicated across two plans instead of one."""

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """REFUSES a `d_head` that is not an exact multiple of `std.gpu.WARP_SIZE` (32 on this
        Apple GPU target), BEFORE any GPU work happens — see `_MBQwen3I8AllSimd.__init__`'s own
        docstring for why: `_sdpa_kernel_simd`'s two-level reduction assumes every `d_head /
        WARP_SIZE` SIMD-group launched is FULLY populated, unaffected by this struct's own
        lm_head-simd and argmax-reduce-simd changes (the latter's own SIMD-group reduction is over
        `_TG = 256` threads fixed at compile time, not `d_head`, so it never needed this refusal on
        its own account — restated here only because this struct inherits the SDPA-simd role's
        requirement unchanged). `_splitk_partial_kernel_simd`'s own per-key SIMD-group reduction
        inherits the identical requirement (it is `_sdpa_kernel_simd`'s per-key loop body, unmodified,
        just bounded to a key subrange), so no separate refusal is needed for it either.
        """
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8AllSimd3: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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
        # ── the deep-context occupancy fix's two kernels — ADDITIVE, alongside `_sdpa_kernel_simd`
        # above, never a replacement for it. See `_ATTN_SPLITK_THRESHOLD`'s own docstring and this
        # struct's `step()` for why BOTH are compiled into this one binary.
        _ = cctx.compile_function_unchecked[_splitk_partial_kernel_simd]()
        _ = cctx.compile_function_unchecked[_splitk_merge_kernel_simd]()

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
                "metaldispatch: _MBQwen3I8AllSimd3 attn-splitk pipeline(s) not found among "
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
        self.m_partial_addr = UInt64(0); self.m_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.l_partial_addr = UInt64(0); self.l_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        self.o_partial_addr = UInt64(0); self.o_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin]()
        if _mb_alloc_buffer(h_q * _ATTN_SPLITK_N_SPLITS * 4, self.m_partial_addr, self.m_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk m_partial)")
        if _mb_alloc_buffer(h_q * _ATTN_SPLITK_N_SPLITS * 4, self.l_partial_addr, self.l_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk l_partial)")
        if _mb_alloc_buffer(h_q * _ATTN_SPLITK_N_SPLITS * d_head * 4, self.o_partial_addr, self.o_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk o_partial)")

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()

        # ── the SECOND, deep-context descriptor table's OWN fields, allocated here (every field
        # must hold a value before `self` is "fully constructed enough" to call a method on it, so
        # this cannot wait until after `self._build_descriptors(n_qkv)` below) -- see `step()`'s own
        # docstring for the gate this table exists to serve.
        self.n_descriptors_deep = 1 + self.n_layers * 7 + 2
        self.descriptors_deep = _mb_alloc_descriptors(self.n_descriptors_deep)
        self.token_id_offset_deep = -1
        self.pos_offsets_deep = List[Int]()
        self.nkeys_offsets_deep = List[Int]()

        self._build_descriptors(n_qkv)
        self._build_descriptors_deep(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
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

    fn _build_descriptors_deep(mut self, n_qkv: Int) raises:
        """The SECOND descriptor table `step()` submits when `n_keys >= _ATTN_SPLITK_THRESHOLD` —
        IDENTICAL per-layer plan to `_build_descriptors` above, roles and order both, with exactly
        ONE substitution: the single `_ROLE_SDPA` dispatch (`grid_x=h_q`) is replaced by TWO
        dispatches, `_splitk_partial_kernel_simd` (`grid_x = h_q * _ATTN_SPLITK_N_SPLITS`) then
        `_splitk_merge_kernel_simd` (`grid_x = h_q`, same shape the SDPA dispatch it replaces
        used) — 7 descriptors per layer here against that method's 6. Every OTHER role (`norm_gemv`,
        `qk_rope`, both `gemv_accum`s, `norm_gemv2_swiglu`, `lm_head`, `argmax_reduce`) is copied
        byte-for-byte, reading and writing the SAME resident buffers (`hidden`/`qkv`/`q_rot`/
        `attn_out`/per-layer `ck`/`cv`/weights) `_build_descriptors`'s own plan does — this table is
        an ALTERNATE PLAN over the identical resident state, not a second independent model.

        `q_rot`/`ck`/`cv` are written by THIS table's own `qk_rope` dispatch every step it is chosen,
        exactly as `_build_descriptors`'s plan writes them every step IT is chosen — whichever plan
        `step()` did not pick on the PREVIOUS call left no residue either plan depends on, since
        `qk_rope` fully overwrites this step's KV-cache slot and `q_rot` regardless of which table
        runs it.
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
            # dispatch `_build_descriptors` issues here with a grid `_ATTN_SPLITK_N_SPLITS` times
            # bigger, recruiting that many times the warps for the SAME query token.
            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx_split,
                self.h_q * _ATTN_SPLITK_N_SPLITS, self.d_head, 12,
            )
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.m_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.l_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, self.o_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, self.q_rot_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 4, lw.ck_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 5, lw.cv_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 6, 0)  # n_keys, patched per step
            self.nkeys_offsets_deep.append(d)
            _mb_set_arg_int(self.descriptors_deep, d, 7, _ATTN_SPLITK_N_SPLITS)
            _mb_set_arg_int(self.descriptors_deep, d, 8, self.h_q)
            _mb_set_arg_int(self.descriptors_deep, d, 9, self.h_kv)
            _mb_set_arg_int(self.descriptors_deep, d, 10, self.d_head)
            _mb_set_arg_f32(self.descriptors_deep, d, 11, self.scale)
            d += 1

            # ── merge: the `_ATTN_SPLITK_N_SPLITS` partials -> ONE normalized attn_out, same shape
            # (`grid_x=h_q`) the SDPA dispatch it replaces wrote its own final output at.
            _mb_set_header(self.descriptors_deep, d, self.pipeline_idx_merge, self.h_q, self.d_head, 6)
            _mb_set_arg_ptr(self.descriptors_deep, d, 0, self.attn_out_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 1, self.m_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 2, self.l_partial_addr)
            _mb_set_arg_ptr(self.descriptors_deep, d, 3, self.o_partial_addr)
            _mb_set_arg_int(self.descriptors_deep, d, 4, _ATTN_SPLITK_N_SPLITS)
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

    fn device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV + lm_head + argmax-reduce SIMD-shuffle reduction)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
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

    fn upload_layer(
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

    fn seal(mut self) -> Int:
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """`_MBQwen3I8AllSimd2.step`'s own body (which is itself `_MBQwen3I8AllSimd.step`'s), PLUS
        one gate: below `_ATTN_SPLITK_THRESHOLD`, this is BYTE-FOR-BYTE that body, patching and
        submitting `self.descriptors` exactly as every sibling struct's `step()` does — the published
        race's own short-context depth (16 tokens) takes this branch, unchanged, which is what makes
        that race's regression gate trivially satisfied by construction, not by a separate check.

        At or above the threshold, this patches and submits `self.descriptors_deep`
        (`_build_descriptors_deep`'s plan: `_splitk_partial_kernel_simd` + `_splitk_merge_
        kernel_simd` in place of the one `_sdpa_kernel_simd` dispatch) instead — same `token_id`/
        `pos`/`n_keys` values, just patched into that table's own offsets, since the two tables are
        different PLANS over the identical resident buffers (this struct's own field docstring has
        the full account of why the choice per step is safe).

        `PR #519`'s long-context investigation measured `_ATTN_SPLITK_THRESHOLD = 512` against the
        REAL production grid/block shape, not the isolated single-role scratch probe that first
        suggested the number: at `n_keys=256` (below threshold) this branch is never taken; the
        split path's own first real win starts around `n_keys ~= 500` and only grows from there, so
        512 leaves margin on both sides of the measured crossover rather than sitting on top of it.
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
                dispatches_used = self.n_descriptors_deep
                _mb_set_arg_int(self.descriptors_deep, self.token_id_offset_deep, 3, token_id)
                for layer in range(self.n_layers):
                    _mb_set_arg_int(self.descriptors_deep, self.pos_offsets_deep[layer], 8, pos)
                    # arg index 6, not 4: `_splitk_partial_kernel_simd`'s own signature puts
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


struct _MBQwen3I8KVF16(Movable):
    """The fp16-KV-CACHE twin of `_MBQwen3I8`: identical int8 weight storage (same `_MBLayerBufI8`
    layout — `ck_ptr`/`cv_ptr` are raw byte pointers there, dtype-agnostic at the struct level, so
    no new layer-buffer struct is needed), identical descriptor PLAN (same roles, same argument
    COUNT per descriptor — a pointer argument's slot tag is `MB_TAG_PTR` regardless of what dtype
    the address points at, exactly the reasoning `_MBQwen3F16._build_descriptors`'s own docstring
    gives for why weight-dtype changes never touch descriptor shape). The ONLY differences from
    `_MBQwen3I8`: `ck`/`cv` are allocated at HALF the bytes (Float16, 2 bytes/element, instead of
    Float32's 4), and the rope-write/sdpa roles compile+dispatch through
    `_qk_rope_write_kernel_kvf16`/`_sdpa_kernel_kvf16` instead of the Float32-cache kernels every
    other struct in this file uses for those two roles.

    This is the arm the task that built this struct measures: fp16 KV-cache storage ORTHOGONAL to
    int8 weight storage, on top of the current int8-weight production baseline (`_MBQwen3I8`,
    235.05 tok/s median per `REALRACE_RESULTS.md`'s "Final race + permanent per-role artifact"
    section) — see `residentk.kernels`' module docstring for why the two axes share no buffer and
    combine freely.

    MUST be built into its OWN binary, never alongside `_MBQwen3I8` (or any sibling) in the same
    one — same truncated-Metal-AIR-name collision `_MBQwen3F16`'s own docstring documents, which
    applies to the rope-write/sdpa roles here exactly as it does to the GEMV-shaped roles there:
    compiling both `_qk_rope_write_kernel` and `_qk_rope_write_kernel_kvf16` (or the `_sdpa_kernel`
    pair) into one binary would give two pipelines answering to the same role with no way to tell
    them apart. This struct's constructor therefore never calls `compile_function_unchecked` on the
    Float32-cache `_qk_rope_write_kernel`/`_sdpa_kernel` — only their `_kvf16` twins, alongside the
    int8 GEMV-shaped kernels `_MBQwen3I8` already uses and the one role
    (`_argmax_reduce_kernel`) with no per-arm variant on either axis.
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

    fn __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
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

        # ── force every kernel THIS ARM needs to be compiled + embedded in THIS binary's
        # __TEXT,__const — the int8 GEMV-shaped twins (weight axis) plus the fp16-KV-cache
        # rope-write/sdpa twins (cache axis) plus the one role with no per-arm variant on either
        # axis. Deliberately NEVER the Float32-cache `_qk_rope_write_kernel`/`_sdpa_kernel`, and
        # NEVER the Float32/Float16 GEMV-shaped weight kernels — see the struct docstring.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function_unchecked[_embed_row_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv_kernel_i8]()
        _ = cctx.compile_function_unchecked[_gemv_accum_kernel_i8]()
        _ = cctx.compile_function_unchecked[_norm_gemv2_swiglu_kernel_i8]()
        _ = cctx.compile_function_unchecked[_qk_rope_write_kernel_kvf16]()
        _ = cctx.compile_function_unchecked[_sdpa_kernel_kvf16]()
        _ = cctx.compile_function_unchecked[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function_unchecked[_argmax_reduce_kernel]()

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        self.pipeline_idx = List[Int]()
        for _ in range(_N_ROLES):
            self.pipeline_idx.append(-1)
        var count = _mb_pipeline_count()
        for i in range(count):
            var name = String()
            _ = _mb_pipeline_name(i, name)
            var role = _classify_pipeline(name)
            if role >= 0:
                self.pipeline_idx[role] = i
        for role in range(_N_ROLES):
            if self.pipeline_idx[role] < 0:
                raise Error(
                    "metaldispatch: pipeline role " + String(role)
                    + " not found among " + String(count) + " discovered pipelines, status="
                    + String(MB_ERR_PIPELINE_NOT_FOUND)
                )

        # ── resident buffers: SAME shapes/bytes as `_MBQwen3I8` for every weight buffer; `ck`/`cv`
        # are HALF the bytes (Float16, 2 bytes/element, instead of Float32's 4) — the one allocation
        # difference this arm exists to make.
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
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 2, cka, ckp) < 0:
                raise Error("metaldispatch: buffer alloc failed (ck f16)")
            if _mb_alloc_buffer(max_ctx * h_kv * d_head * 2, cva, cvp) < 0:
                raise Error("metaldispatch: buffer alloc failed (cv f16)")
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

        self.n_descriptors = metaldispatch_dispatch_budget(n_layers)
        self.descriptors = _mb_alloc_descriptors(self.n_descriptors)
        self.token_id_offset = -1
        self.pos_offsets = List[Int]()
        self.nkeys_offsets = List[Int]()
        self._build_descriptors(n_qkv)

    fn _build_descriptors(mut self, n_qkv: Int) raises:
        """Byte-for-byte the same descriptor plan as `_MBQwen3I8._build_descriptors` — every
        argument slot, tag and count is identical; only the addresses bound at the `ck`/`cv`
        pointer slots point at half-sized (Float16) allocations, which changes nothing about the
        descriptor itself (a pointer slot's tag is `MB_TAG_PTR` regardless of what the address
        points at — see `_MBQwen3F16._build_descriptors`'s own docstring for this exact reasoning
        on the weight axis)."""
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

    fn device_name(self) -> String:
        return "metal (batched shim, int8 weights + fp16 kv-cache)"

    fn dispatch_budget(self) -> Int:
        return self.n_descriptors

    fn upload_globals(
        mut self, embed: List[Float64], final_norm: List[Float64],
        cos_t: List[Float64], sin_t: List[Float64], n_pos: Int,
    ) raises -> Int:
        """Byte-for-byte `_MBQwen3I8.upload_globals` — the KV cache is not a checkpoint tensor, it
        holds nothing until `step()` writes the first slot, so this function's own arithmetic does
        not change; only `__init__`'s allocation size for `ck`/`cv` differs."""
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

    fn upload_layer(
        mut self, layer: Int,
        ln1: List[Float64], ln2: List[Float64], qn: List[Float64], kn: List[Float64],
        wq: List[Float64], wk: List[Float64], wv: List[Float64], wo: List[Float64],
        wgate: List[Float64], wup: List[Float64], wdown: List[Float64],
    ) raises -> Int:
        """Byte-for-byte `_MBQwen3I8.upload_layer` — see that function's docstring reasoning above."""
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

    fn seal(mut self) -> Int:
        return MB_OK

    fn step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
        """Byte-for-byte `_MBQwen3I8.step`'s own body — see `_MBQwen3.step`'s docstring."""

        @parameter
        if not MB_GPU_BUILD:
            return _StepOut(-1, 0.0, 0, MB_ERR_SHADER_TOOLCHAIN_ABSENT)
        else:
            if pos < 0 or pos >= self.max_ctx:
                return _StepOut(-1, 0.0, 0, MB_ERR_CONTEXT_FULL)
            if token_id < 0 or token_id >= self.vocab:
                return _StepOut(-1, 0.0, 0, MB_ERR_UPLOAD_LENGTH)

            _mb_set_arg_int(self.descriptors, self.token_id_offset, 3, token_id)
            var n_keys = pos + 1
            for layer in range(self.n_layers):
                _mb_set_arg_int(self.descriptors, self.pos_offsets[layer], 8, pos)
                _mb_set_arg_int(self.descriptors, self.nkeys_offsets[layer], 4, n_keys)

            var rc = _mb_run_token(self.descriptors, self.n_descriptors)
            if rc != 0:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)

            var tok = Int(self.out_idx_ptr.bitcast[Int32]()[0])
            var lg = Float64(self.out_val_ptr.bitcast[Float32]()[0])
            if tok < 0 or tok >= self.vocab:
                return _StepOut(-1, 0.0, self.n_descriptors, MB_ERR_DISPATCH_FAILED)
            return _StepOut(tok, lg, self.n_descriptors, MB_OK)


fn _mb_preflight(
    d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
    n_layers: Int, n_prompt: Int, n_new: Int, max_ctx: Int, eps: Float64, scale: Float64,
) -> Int:
    """Every refusal a caller can hit, answered before a device or the shim is touched. Reuses
    `residentk`'s own shape/context checks (rule 3) rather than restating them."""
    from residentk.contract import RESIDENT_MAX_CONTEXT, residentk_context_check, residentk_dims_check
    from residentk.contract import RESIDENT_OK as _R_OK

    var shape = residentk_dims_check(d_model, h_q, h_kv, d_head, d_ff)
    if shape != _R_OK:
        return shape
    if n_layers < 1:
        return MB_ERR_UPLOAD_LENGTH
    var ctxs = residentk_context_check(n_prompt, n_new, max_ctx)
    if ctxs != _R_OK:
        return ctxs
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return MB_ERR_CONTEXT_FULL
    if eps <= 0.0 or scale <= 0.0:
        return MB_ERR_UPLOAD_LENGTH

    @parameter
    if not MB_GPU_BUILD:
        return MB_ERR_SHADER_TOOLCHAIN_ABSENT
    if not has_accelerator():
        return MB_ERR_NO_DEVICE
    return MB_OK
