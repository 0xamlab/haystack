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
measured to NOT match the order `compile_function` was called in (the two were compared
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
from residentk.contract import (
    RESIDENT_MAX_CONTEXT,
    residentk_splitk_should_split,
    residentk_splitk_policy,
    residentk_splitk_max_n_splits,
)
from residentk.kernels import (
    _TG,
    _SUBS,
    _argmax_reduce_kernel,
    _argmax_reduce_kernel_simd,
    _splitk_partial_kernel_simd,
    _splitk_partial_kernel_simd_batched4,
    _splitk_partial_kernel_simd_native,
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


def _ceil_div(a: Int, b: Int) -> Int:
    return (a + b - 1) // b


def _classify_pipeline(name: String) -> Int:
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

comptime _ATTN_SPLITK_N_SPLITS_NATIVE: Int = 80
"""Split count for `_MBQwen3I8AllSimd6`'s deep-context SDPA path ONLY — `_splitk_partial_kernel_
simd_native` + `_splitk_merge_kernel_simd` — a SEPARATE symbol from `_ATTN_SPLITK_N_SPLITS` above,
deliberately never shared with it: `_MBQwen3I8AllSimd3` (the shipped, race-verified two-level kernel)
and `_MBQwen3I8AllSimd5` (the reduction-shape-only race at `_ATTN_SPLITK_N_SPLITS` UNCHANGED, see its
own docstring for the honest regression that motivated this constant) must stay byte-for-byte
unaffected by whatever value THIS constant takes — bumping the shared constant instead would have
silently changed those two structs' own already-verified, already-raced behavior too.

Chosen from a real, embedded, GPU-counter-isolated sweep on `_MBQwen3I8AllSimd5`'s own descriptor
plan (`qwen3_probe_counters_i8_allsimd5_splitk_deepctx.mojo`, `splitk_partial`'s role-level GPU time,
`n_keys=4000`, `_ATTN_SPLITK_N_SPLITS` temporarily overridden per candidate value and rebuilt — the
exact production kernel and dispatch code, never a scratch/throwaway kernel, per this task's own
"not a scratch probe" instruction) — deliberately NOT the design phase's own isolated single-role
probe, whose "64 splits, 2.16x" projection this task was explicitly told to re-check rather than
inherit; that probe's own methodology, once re-run EMBEDDED in the real 199-descriptor pipeline
(the same lesson `_MBQwen3I8AllSimd5`'s honest regression already taught for `n_splits=16`), does not
transfer even for the sweep's own optimum, as the numbers below show.

Candidates {16, 24, 32, 40, 48, 56, 64, 68, 72, 76, 80, 84, 88, 96, 112, 120(*), 128, 160, 192, 224,
256} were swept (`(*)`: 120 not separately measured, bracketed by 112/128); `splitk_partial`'s own
GPU time (28-layer sum, ms, `n_keys=4000`) was NOT monotonic in `n_splits` -- it fell sharply to
`n_splits~=64`, KEPT falling to a clear minimum in the `68-80` band, then rose sharply again at
`84-96` (WORSE than 64!), fell again by `128`, rose again at `160`, then plateaued `192-256` -- e.g.
`~18.0ms` at 16, `~9.7ms` at 32, `~5.5ms` at 64, `~7.3-7.4ms` at 84-88, `~6.8ms` at 96, `~5.6-5.8ms`
at 128, `~6.3-6.4ms` at 160. This non-monotonic shape is consistent with GPU-core-count occupancy
quantization, not noise: this machine's own Metal device reports 40 GPU cores
(`system_profiler SPDisplaysDataType`), and `h_q * n_splits` IS the total warp count this dispatch
puts in flight (`block_dim = WARP_SIZE`, one warp per threadgroup) -- at `h_q=16`, `n_splits=80`
gives exactly `16*80 = 1280 = 32 * 40` warps, an EXACT multiple of the core count, where 84/88/96
(`1344`/`1408`/`1536` warps) are not. Repeated rounds (5x) at the `68-80` band's own candidates
measured `80` as the reproducible minimum (mean `~4.90ms`, individual samples `4.73-5.14ms`) against
`72`'s own `~5.26ms`, `68`'s `~5.43ms`, `64`'s `~5.54ms`, and `76`'s `~5.56ms` -- close enough between
`68-80` that core-count quantization, not a smooth "more parallelism is strictly better" curve, is
the better explanation than picking a single global optimum by formula. `splitk_merge` (this same
sweep's own by-product measurement) stays a small fraction of `splitk_partial` even at this 5x-wider
split count (`~0.45ms` at `n_splits=80` vs. `~0.16ms` at the shipped `n_splits=16`) — not a new
bottleneck. Embedded in the real, full 28-layer pipeline at `n_splits=80`, AT `n_keys=4000` SPECIFICALLY:
`splitk_partial` alone is `~1.55x` faster than `_MBQwen3I8AllSimd3`'s own shipped `n_splits=16` two-
level kernel (`~5.0ms` vs. `~7.7ms`), and the pipeline's own TOTAL per-token GPU time (sum of every
role, `n_keys=4000`) is `~1.30x` faster (`~8.3ms` vs. `~10.8ms`). That number is AT ONE DEPTH, not
averaged over a whole run -- see `_MBQwen3I8AllSimd6`'s own docstring for the real, full 4096-token
decode-tok/s self-comparison, which averages over every depth from 0 to 4095 (most of them shallower
than `n_keys=4000`, many below `_ATTN_SPLITK_THRESHOLD` entirely) and, for exactly that reason, shows
a smaller but still real overall win, not this depth-specific ratio restated as a whole-run number."""

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


def _classify_splitk_pipeline(name: String) -> Int:
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
       guess, the ACTUAL boundary.

    3. A THIRD collision, found by this repo's own Attention Compiler Plan v1.0 multi-blob
       coexistence validation (not yet landed as a production struct, but confirmed by direct
       string inspection of a binary linking both blobs): `attention_forge/splitk_fa.mojo`'s own
       `_attn_splitk_partial_kernel`/`_attn_splitk_merge_kernel` discover as `splitk_fa__attn_
       splitk_partial_...`/`splitk_fa__attn_splitk_merge_ke...` — genuinely DIFFERENT kernels in a
       DIFFERENT module, but containing the bare `splitk_part`/`splitk_merg` substrings too, since
       the MODULE prefix (unlike the kernel's own name) is never truncated (confirmed: `residentk_
       kernels__<11 chars>` for every kernel in this file's own module; `splitk_fa__<5 chars>` for
       attention_forge's differently-named module). The patterns below are therefore module-
       qualified (`residentk_kernels__splitk_part`/`residentk_kernels__splitk_merg`) so they match
       ONLY this file's own two kernels and never `attention_forge`'s module-distinct namesakes,
       should both ever be linked into the same binary."""
    if name.find("residentk_kernels__splitk_part") >= 0:
        return 0
    if name.find("residentk_kernels__splitk_merg") >= 0:
        return 1
    return -1


comptime _PFROLE_EMBED: Int = 0
comptime _PFROLE_RMSNORM: Int = 1
comptime _PFROLE_GEMM_ASSIGN: Int = 2
comptime _PFROLE_ROPEWRT: Int = 3
comptime _PFROLE_ATTN: Int = 4
comptime _PFROLE_GEMM_ACCUM: Int = 5
comptime _PFROLE_GEMM_SWIGLU: Int = 6
comptime _PFROLE_GEMM_ASSIGN_NARROW: Int = 7
comptime _PFROLE_GEMM_ACCUM_NARROW: Int = 8
comptime _PFROLE_GEMM_SWIGLU_NARROW: Int = 9
comptime _PFROLE_GEMM_ASSIGN_MMA: Int = 10
comptime _PFROLE_GEMM_ACCUM_MMA: Int = 11
comptime _PFROLE_GEMM_SWIGLU_MMA: Int = 12
comptime _PFROLE_ATTN_BLOCK8: Int = 13
comptime _PF_N_ROLES: Int = 14
"""Was 6 roles (`_PFROLE_QKV_PROJ`/`_PFROLE_GEMV_ACCUM`/`_PFROLE_SWIGLU`) through PR #584's own
Phase 1, then 7 once those became weight-stationary-tiled-GEMM roles, then 10 once the narrow-tile
twins landed. The three `_MMA` roles (`_PFROLE_GEMM_ASSIGN_MMA`/`_PFROLE_GEMM_ACCUM_MMA`/
`_PFROLE_GEMM_SWIGLU_MMA`) are real Apple hardware `simdgroup_matrix` 8x8 kernels
(`_qkv_proj_gemm_mma8x8`/`_gemm_accum_mma8x8`/`_swiglu_gemm_mma8x8`), built and correctness-gated in
the isolated `mma_forge/` cross-toolchain project (own pixi env, `mojo>=1.0` + the proprietary `max`
package — never a dependency of this repo's own pinned `mojo_env`), extracted as a raw `.metallib`
blob (`mma_forge/tools/extract_blob.py`) and linked into the SAME production binary as one more
`-Xlinker` object (`mma_forge/generated/mm8_blob.c`, compiled with plain `clang -c`) — the pipeline-
discovery mechanism below is provenance-agnostic, so these need no different handling than any
other kernel here once linked. Measured on this exact M4 Max, at Qwen3-0.6B-Base-scale shapes,
against the scalar oracles they replace: qkv_proj 2.37x, o_proj 2.19x, down_proj 2.22x, swiglu
3.24x (real GFLOP/s, `benchmarks/llm_smoke/metal_batch_dispatch/mma_qkv_proj_speed.mojo` and
`mma_phase2_speed.mojo`). Selected per `prefill_batch()` call in place of the wide/narrow scalar
roles when `m_rows % 32 == 0` (these kernels' own Phase-1/2 scope: no partial-tile M/N padding yet
— `residentk.contract`'s own module docstring on the wide/narrow split is the precedent this
three-way choice extends); the scalar-FMA path (wide OR narrow, exactly as already selected) remains
the fallback for every `m_rows` not a multiple of 32, so this is purely additive to the existing
policy, never a replacement of it.

`_PFROLE_ATTN_BLOCK8` (`residentk.kernels._pf_attn8_kernel_simd`) is Phase 1 of the separate
tiled-MMA-attention plan: one online-softmax rescale per block of 8 keys instead of one per key,
same per-key SIMD-shuffle dot-product reduction otherwise. Its classifier pattern (`pf_attn8`) MUST
be checked before the existing `pf_attn` pattern below -- `pf_attn` is a PREFIX of `pf_attn8`, so
`.find()` would otherwise match this kernel's discovered name against the OLD role first and never
reach the new one, the exact ordering hazard `_pf_ropewrt_kernel`'s own naming note two paragraphs
below already warns about for a different pair.

The three `_NARROW` roles (`_PFROLE_GEMM_ASSIGN_NARROW`/`_PFROLE_GEMM_ACCUM_NARROW`/
`_PFROLE_GEMM_SWIGLU_NARROW`) are `residentk.kernels`' narrow-tile GEMM twins
(`_pf_gnrw_assign_kernel_i8`/`_pf_gnrw_accum_kernel_i8`/`_pf_gnrw_swiglu_kernel_i8`) — selected per
`prefill_batch()` call, in place of the wide roles three lines up, by `residentk.contract.
residentk_prefill_gemm_use_narrow_tile(m_rows)`. See that function's own docstring for the real
two-anchor measurement this choice rests on: `_pf_qkv_proj_kernel_simd_i8`/`_pf_gemv_accum_kernel_
simd_i8`/`_pf_swiglu_kernel_simd_i8` all stay byte-unmodified in `residentk.kernels`, now serving
only as Gate-0 oracles `test_residentk_prefill_gemm_kernels.mojo` diffs against, compiled and
dispatched there directly via `DeviceContext`, never through this file's own pipeline-discovery
mechanism. `_MBQwen3I8AllSimd7Prefill` is the ONLY struct that reads this enum (iterated on in place
per that struct's own docstring, not yet raced/published), so renumbering here carries no risk to
any OTHER struct in this file."""


def _classify_prefill_pipeline(name: String) -> Int:
    """Which of the TEN `residentk.kernels` batched-prefill functions a discovered pipeline's
    Metal function name belongs to — `0`..`9`, or `-1` (neither). A THIRD classifier, deliberately
    never folded into `_classify_pipeline`'s shared `_N_ROLES`/`pipeline_idx` (every struct in this
    file would then be forced to compile ten kernels it never uses) nor into `_classify_splitk_
    pipeline` (a different, unrelated role pair) — the identical reasoning that function's own
    docstring gives for staying separate from `_classify_pipeline`, applied a second time for a
    second, independent addition.

    Every pattern below is verified DIRECTLY against this binary's own real, possibly-truncated Metal
    AIR names (`benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_prefill_naming.mojo`, run for
    real — not merely inspected in source), and confirmed to collide with none of `_classify_
    pipeline`'s eight patterns nor `_classify_splitk_pipeline`'s two, nor with each other. Note the
    THREE `pf_gemm_*` (wide) names share an 8-character prefix (`pf_gemm_`) and diverge only at
    character 9 or 10, still inside the 11-character surviving window (`pf_gemm_ass` / `pf_gemm_acc`
    / `pf_gemm_swi`) — confirmed distinct by the same probe, not merely counted by hand, exactly the
    discipline this near-collision calls for. Their NARROW-tile twins are deliberately NOT named
    `_pf_gemm_*_narrow`: that suffix falls AFTER the 11-character survivor boundary, so all three
    would have truncated IDENTICALLY to their wide twins — `residentk.kernels`' own module comment
    for the narrow-tile section has the full account of that rejected naming and the `pf_gnrw_*`
    prefix (`pf_gnrw_ass` / `pf_gnrw_acc` / `pf_gnrw_swi`) chosen instead, verified distinct from
    every `pf_gemm_*` pattern by the same probe. `_pf_ropewrt_kernel` is named deliberately unlike
    its single-row twin `_qk_rope_write_kernel`: the truncation-surviving prefix of the OBVIOUS name
    (`_pf_qk_rope_write_kernel` -> `pf_qk_rope_`) contains `_classify_pipeline`'s own `qk_rope`
    substring, which would have made every discovered pipeline of THIS kernel also match role
    `_ROLE_QK_ROPE` in `_classify_pipeline`'s scan — harmless for `_classify_pipeline` itself (its
    own loop never sees this kernel's pipeline unless `_classify_prefill_pipeline` also runs, and
    this file's session structs only ever call ONE of the two classifiers per discovered name, never
    both blindly) but a needless landmine for the next person changing either function — the same
    "diverge before the surviving window ends" fix `splitk_part`/`splitk_merg`'s own rename already
    used."""
    if name.find("pf_embed") >= 0:
        return _PFROLE_EMBED
    if name.find("pf_rmsnorm") >= 0:
        return _PFROLE_RMSNORM
    if name.find("pf_gemm_ass") >= 0:
        return _PFROLE_GEMM_ASSIGN
    if name.find("pf_gnrw_ass") >= 0:
        return _PFROLE_GEMM_ASSIGN_NARROW
    if name.find("pf_ropewrt") >= 0:
        return _PFROLE_ROPEWRT
    if name.find("pf_attn8") >= 0:
        return _PFROLE_ATTN_BLOCK8
    if name.find("pf_attn") >= 0:
        return _PFROLE_ATTN
    if name.find("pf_gemm_acc") >= 0:
        return _PFROLE_GEMM_ACCUM
    if name.find("pf_gnrw_acc") >= 0:
        return _PFROLE_GEMM_ACCUM_NARROW
    if name.find("pf_gemm_swi") >= 0:
        return _PFROLE_GEMM_SWIGLU
    if name.find("pf_gnrw_swi") >= 0:
        return _PFROLE_GEMM_SWIGLU_NARROW
    if name.find("proj_gemm_mma8x8") >= 0:
        return _PFROLE_GEMM_ASSIGN_MMA
    if name.find("gemm_accum_mma8x8") >= 0:
        return _PFROLE_GEMM_ACCUM_MMA
    if name.find("swiglu_gemm_mma8x8") >= 0:
        return _PFROLE_GEMM_SWIGLU_MMA
    return -1


comptime _AFROLE_NATIVE_KV_PRODUCER: Int = 0
comptime _AFROLE_GROUPED_FA_ATTN: Int = 1
comptime _AF_N_ROLES: Int = 2
"""Attention Compiler Plan v1.0, Phase 2C production wiring: the two cross-toolchain-forged
`attention_forge/` blobs (`native_kv_producer.mojo`'s `_native_kv_producer_kernel`,
`grouped_fa_q8_k32_h2_sg8.mojo`'s `_attn_grouped_fa_kernel` -- Candidate A) that
`_MBQwen3I8AllSimd7Prefill`'s new `use_native_grouped_fa_attn` flag dispatches INSTEAD OF
`_pf_ropewrt_kernel`/`_pf_attn_tiled_kernel_simd` when set. A FOURTH classifier, deliberately never
folded into `_classify_pipeline`'s shared `_N_ROLES` (nor `_classify_splitk_pipeline`'s two roles,
nor `_classify_prefill_pipeline`'s ten) for the exact reason every one of those three functions'
own docstrings already gives: `_MBQwen3I8AllSimd7Prefill` is the ONLY struct that ever links these
two blobs, and folding them into a SHARED, required-role enum would force every OTHER struct in
this file to demand pipelines it never compiles and never will. Unlike the other three classifiers,
a MISSING match here is NOT fatal at session-open time -- see `_MBQwen3I8AllSimd7Prefill.__init__`'s
own handling: this pair is genuinely OPTIONAL production capability, present only in a binary that
was deliberately built with both forged blobs linked in (via `-Xlinker`, following
`candidate_a_blob_test.mojo`'s/`native_kv_producer_blob_driver.mojo`'s own proven
build-and-extract recipe) -- a binary that never linked them (every EXISTING benchmark/production
build, unchanged by this addition) must keep working with both roles simply undiscovered.

Patterns chosen, and why they are safe by construction (verified empirically, not guessed --
`candidate_a_native_kv_discovery_check.mojo` built and ran the exact three-blob combination
production wiring needs -- Candidate A + the native-KV-producer + the EXISTING `mm8` GEMM blob --
in one binary and printed every discovered pipeline's real, un-truncated name):
  - Candidate A: `grouped_fa_q8_k32_h2_sg8__attn_6A6A_d7a1249b06314ef7` -- matched on the FULL,
    never-truncated module name `grouped_fa_q8_k32_h2_sg8` (this module contains exactly one
    kernel, so the module name alone already disambiguates -- the same pattern
    `candidate_a_blob_test.mojo`'s own identification loop already established).
  - Native-KV-producer: `native_kv_producer__native_kv_p6A6A_496a269190b956c5` -- matched on the
    FULL, never-truncated module name `native_kv_producer` (also exactly one kernel per module).
Neither substring collides with `_classify_pipeline`'s eight patterns, `_classify_splitk_pipeline`'s
two, `_classify_prefill_pipeline`'s ten, or `mm8`'s own three discovered names (`mm8__qkv_proj_
gemm_mma8x8_...`, `mm8__gemm_accum_mma8x8_...`, `mm8__swiglu_gemm_mma8x8_...`) -- confirmed both by
direct inspection of the five real names above and, more strongly, by the discovery check's own
five-pipelines-found, one-match-each verification at runtime. Should a THIRD attention_forge module
ever be linked into the same binary as these two, re-verify empirically exactly as this check did --
per every other classifier in this file, "module names don't collide" is a measured property of
the two modules THIS session forged, not a guarantee about Mojo's name-mangling in general."""


def _classify_attention_forge_pipeline(name: String) -> Int:
    """Which of the TWO `attention_forge/` production kernels (native-KV-producer / Candidate A's
    grouped-head fused-FlashAttention) a discovered pipeline's name belongs to -- `0` / `1` / `-1`
    (neither). See `_AF_N_ROLES`'s own docstring immediately above for why this classifier stays
    separate from the other three in this file, and for the empirical verification behind each
    pattern below."""
    if name.find("native_kv_producer") >= 0:
        return _AFROLE_NATIVE_KV_PRODUCER
    if name.find("grouped_fa_q8_k32_h2_sg8") >= 0:
        return _AFROLE_GROUPED_FA_ATTN
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


def _narrow_into(
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


def _narrow_transposed_into(
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


def _narrow_into_f16(
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


def _narrow_transposed_into_f16(
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


def _quantize_row_i8(v: Float64, inv_scale: Float64) -> Int8:
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


def _quantize_into_i8(
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


def _quantize_transposed_into_i8(
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

    def __init__(
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
        # `compile_function` forces codegen; the DeviceContext it needs exists only for
        # that side effect and is dropped immediately after — this package does not dispatch
        # through it, the shim does.
        from std.gpu.host import DeviceContext
        var cctx = DeviceContext()
        _ = cctx.compile_function[_embed_row_kernel]()
        _ = cctx.compile_function[_norm_gemv_kernel]()
        _ = cctx.compile_function[_gemv_accum_kernel]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel]()
        _ = cctx.compile_function[_lmhead_argmax_kernel]()
        _ = cctx.compile_function[_argmax_reduce_kernel]()

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
            var ln1a = UInt64(0); var ln1p = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var ln2a = UInt64(0); var ln2p = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var qna = UInt64(0); var qnp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var kna = UInt64(0); var knp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wqkva = UInt64(0); var wqkvp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var woa = UInt64(0); var wop = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wgua = UInt64(0); var wgup = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wdowna = UInt64(0); var wdownp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

        self.embed_addr = UInt64(0); self.embed_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.final_norm_addr = UInt64(0); self.final_norm_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.cos_addr = UInt64(0); self.cos_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.sin_addr = UInt64(0); self.sin_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        if _mb_alloc_buffer(vocab * d_model * 4, self.embed_addr, self.embed_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (embed)")
        if _mb_alloc_buffer(d_model * 4, self.final_norm_addr, self.final_norm_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (final_norm)")
        if _mb_alloc_buffer(max_ctx * n_pairs * 4, self.cos_addr, self.cos_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (cos)")
        if _mb_alloc_buffer(max_ctx * n_pairs * 4, self.sin_addr, self.sin_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (sin)")

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

    def _build_descriptors(mut self, n_qkv: Int) raises:
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

    def device_name(self) -> String:
        return "metal (batched shim)"

    def dispatch_budget(self) -> Int:
        return self.n_descriptors

    def upload_globals(
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

    def seal(mut self) -> Int:
        """No-op: Shared-storage buffers are CPU/GPU coherent as soon as they're written, unlike
        `residentk.session.seal`'s `ctx.synchronize()` drain of MAX's own upload queue. Kept as a
        function so the two sessions' driver code reads identically."""
        return MB_OK

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
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
    apart. This struct's constructor therefore never calls `compile_function` on
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

    def __init__(
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
        _ = cctx.compile_function[_embed_row_kernel_f16]()
        _ = cctx.compile_function[_norm_gemv_kernel_f16]()
        _ = cctx.compile_function[_gemv_accum_kernel_f16]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_f16]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_f16]()
        _ = cctx.compile_function[_argmax_reduce_kernel]()

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
            var ln1a = UInt64(0); var ln1p = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var ln2a = UInt64(0); var ln2p = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var qna = UInt64(0); var qnp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var kna = UInt64(0); var knp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wqkva = UInt64(0); var wqkvp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var woa = UInt64(0); var wop = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wgua = UInt64(0); var wgup = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
            var wdowna = UInt64(0); var wdownp = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

        self.embed_addr = UInt64(0); self.embed_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.final_norm_addr = UInt64(0); self.final_norm_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.cos_addr = UInt64(0); self.cos_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.sin_addr = UInt64(0); self.sin_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        if _mb_alloc_buffer(vocab * d_model * 2, self.embed_addr, self.embed_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (embed f16)")
        if _mb_alloc_buffer(d_model * 4, self.final_norm_addr, self.final_norm_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (final_norm)")
        if _mb_alloc_buffer(max_ctx * n_pairs * 4, self.cos_addr, self.cos_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (cos)")
        if _mb_alloc_buffer(max_ctx * n_pairs * 4, self.sin_addr, self.sin_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (sin)")

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

    def _build_descriptors(mut self, n_qkv: Int) raises:
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

    def device_name(self) -> String:
        return "metal (batched shim, fp16 weights)"

    def dispatch_budget(self) -> Int:
        return self.n_descriptors

    def upload_globals(
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

    def upload_layer(
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

    def seal(mut self) -> Int:
        return MB_OK

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
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
    therefore never calls `compile_function` on the Float32 or Float16 GEMV-shaped
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

    def __init__(
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel]()

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

    def _build_descriptors(mut self, n_qkv: Int) raises:
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

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights)"

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
    constructor therefore never calls `compile_function` on `_sdpa_kernel` — only
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

    def __init__(
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel]()

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

    def _build_descriptors(mut self, n_qkv: Int) raises:
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

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA SIMD-shuffle reduction)"

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
    struct's constructor therefore never calls `compile_function` on any of the four
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

    def __init__(
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel]()

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

    def _build_descriptors(mut self, n_qkv: Int) raises:
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

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV SIMD-shuffle reduction)"

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
    `compile_function` on the barrier-tree `_lmhead_argmax_kernel_i8` — only its `_simd`
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

    def __init__(
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel]()

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

    def _build_descriptors(mut self, n_qkv: Int) raises:
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

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV + lm_head SIMD-shuffle reduction)"

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
    `compile_function` on the barrier-tree `_argmax_reduce_kernel` — only its `_simd`
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

    A SIXTH addition, fixing a real (if modest) side effect of the fifth: `self.descriptors_deep` and
    its two kernel compiles / three scratch buffers are now built LAZILY, by `_ensure_deep_
    initialized`, the first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` — not
    unconditionally in `__init__` the way the fifth addition first shipped them. A controlled,
    interleaved A/B against real installed mlx-lm found the FIFTH addition's unconditional
    construction-time cost (~560us, measured: ~71.5us kernel compiles + ~486us buffer allocs + ~13us
    descriptor-table alloc/build) was small in absolute terms but real and structural, present in
    EVERY session including one that only ever runs shallow (e.g. the published 16-token race), which
    the owner's zero-tolerance-for-regression bar does not accept even at this size. See
    `_ensure_deep_initialized`'s own docstring for why deferring it is safe: `_sdpa_kernel_simd`, the
    `self.descriptors` table, and the branch that submits it remain UNTOUCHED (as the fifth addition's
    own docstring above already establishes) — this sixth addition only changes WHEN the deep path's
    OWN one-time setup cost is paid, never what either path computes.
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel_simd]()
        # ── the deep-context occupancy fix's two kernels are DELIBERATELY NOT compiled here.
        # `_ensure_deep_initialized` (below) calls `compile_function` on both, lazily, the
        # first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` -- see that method's own
        # docstring for why. This does NOT remove either kernel from THIS binary: both are still
        # referenced by a `compile_function[...]` call reachable from this struct (just a
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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
        self.m_partial_addr = UInt64(0); self.m_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.l_partial_addr = UInt64(0); self.l_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.o_partial_addr = UInt64(0); self.o_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

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
        self.descriptors_deep = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
          - `compile_function[_splitk_partial_kernel_simd]`/`[_splitk_merge_kernel_simd]`:
            deferring WHEN this Mojo statement executes does not change WHICH pipelines
            `_mb_open_session` discovers in `__init__` (this file's own module docstring: pipeline
            discovery is driven by scanning this binary's embedded `.metallib` blobs by NAME, not by
            `compile_function` call order) — `self.pipeline_idx_split`/`pipeline_idx_merge`
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
        _ = cctx.compile_function[_splitk_partial_kernel_simd]()
        _ = cctx.compile_function[_splitk_merge_kernel_simd]()

        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * 4, self.m_partial_addr, self.m_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk m_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * 4, self.l_partial_addr, self.l_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk l_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * self.d_head * 4, self.o_partial_addr, self.o_partial_ptr) < 0:
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

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV + lm_head + argmax-reduce SIMD-shuffle reduction)"

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


struct _MBQwen3I8AllSimd4(Movable):
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
    `compile_function` on the barrier-tree `_argmax_reduce_kernel` — only its `_simd`
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

    A SIXTH addition, fixing a real (if modest) side effect of the fifth: `self.descriptors_deep` and
    its two kernel compiles / three scratch buffers are now built LAZILY, by `_ensure_deep_
    initialized`, the first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` — not
    unconditionally in `__init__` the way the fifth addition first shipped them. A controlled,
    interleaved A/B against real installed mlx-lm found the FIFTH addition's unconditional
    construction-time cost (~560us, measured: ~71.5us kernel compiles + ~486us buffer allocs + ~13us
    descriptor-table alloc/build) was small in absolute terms but real and structural, present in
    EVERY session including one that only ever runs shallow (e.g. the published 16-token race), which
    the owner's zero-tolerance-for-regression bar does not accept even at this size. See
    `_ensure_deep_initialized`'s own docstring for why deferring it is safe: `_sdpa_kernel_simd`, the
    `self.descriptors` table, and the branch that submits it remain UNTOUCHED (as the fifth addition's
    own docstring above already establishes) — this sixth addition only changes WHEN the deep path's
    OWN one-time setup cost is paid, never what either path computes.

    A SEVENTH addition, and the ONLY difference from `_MBQwen3I8AllSimd3` (this struct's own
    immediate predecessor, byte-identical up to this point): `_ensure_deep_initialized` now compiles
    `residentk.kernels._splitk_partial_kernel_simd_batched4` — the BARRIER-BATCHING twin of the fifth
    addition's own `_splitk_partial_kernel_simd`, batching 4 keys per `barrier()` round instead of 1
    — for `_build_descriptors_deep`'s split dispatch instead of the unbatched kernel.
    `_build_descriptors_deep`'s PLAN is byte-unchanged (same grid/block shape, same argument order,
    same buffers): only WHICH compiled pipeline `self.pipeline_idx_split` resolves to differs.

    HONEST RESULT: this struct exists to RACE its own predecessor head to head, and the answer, fully
    measured (GPU-counter isolated AND full 4096-token generation, see `_splitk_partial_kernel_simd_
    batched4`'s own docstring for the numbers and the most likely explanation) is that batching does
    NOT win here — `splitk_partial`'s own GPU time REGRESSES ~4-10% at `n_keys=4000`, reproduced at
    two different batch sizes, ruling out per-key barrier count as this codebase's dominant remaining
    long-context lever. Every OTHER byte of `step()`'s behavior (correctness, the descriptor plan,
    the shallow/deep gate) is verified identical to `_MBQwen3I8AllSimd3`'s own — a full 4096-token
    generation from both structs, same prompt, same checkpoint, produced BIT-IDENTICAL token ids and
    logits at every one of 4096 positions (zero mismatches, max logit delta `0.0`) — so this struct
    is a real, correctness-verified, PERFORMANCE-NEGATIVE finding, landed as exactly that: additive,
    a new struct alongside the existing one, never a replacement, and never the arm the published
    race or any future race should reach for (this file's own "one pipeline per role, own binary"
    discipline already requires the unbatched and batched split kernels to never be compiled
    together, so a new struct — rather than a branch inside `_MBQwen3I8AllSimd3` — was the only way
    to race the two head to head without one shadowing the other's pipeline-name discovery).
    `_MBQwen3I8AllSimd3` itself, `_splitk_partial_kernel_simd`, and every byte of `self.descriptors`
    and the branch that submits it (this struct's own <threshold path, IDENTICAL to `_MBQwen3I8
    AllSimd3`'s) remain UNTOUCHED by this addition.
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
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """REFUSES a `d_head` that is not an exact multiple of `std.gpu.WARP_SIZE` (32 on this
        Apple GPU target), BEFORE any GPU work happens — see `_MBQwen3I8AllSimd.__init__`'s own
        docstring for why: `_sdpa_kernel_simd`'s two-level reduction assumes every `d_head /
        WARP_SIZE` SIMD-group launched is FULLY populated, unaffected by this struct's own
        lm_head-simd and argmax-reduce-simd changes (the latter's own SIMD-group reduction is over
        `_TG = 256` threads fixed at compile time, not `d_head`, so it never needed this refusal on
        its own account — restated here only because this struct inherits the SDPA-simd role's
        requirement unchanged). `_splitk_partial_kernel_simd_batched4`'s own per-key SIMD-group
        reduction inherits the identical requirement (it is `_sdpa_kernel_simd`'s per-key loop body,
        unmodified apart from batching 4 keys per barrier round, just bounded to a key subrange),
        so no separate refusal is needed for it either.
        """
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8AllSimd4: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel_simd]()
        # ── the deep-context occupancy fix's two kernels are DELIBERATELY NOT compiled here.
        # `_ensure_deep_initialized` (below) calls `compile_function` on both, lazily, the
        # first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` -- see that method's own
        # docstring for why. This does NOT remove either kernel from THIS binary: both are still
        # referenced by a `compile_function[...]` call reachable from this struct (just a
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
                "metaldispatch: _MBQwen3I8AllSimd4 attn-splitk pipeline(s) not found among "
                + String(count) + " discovered pipelines (split=" + String(self.pipeline_idx_split)
                + " merge=" + String(self.pipeline_idx_merge) + "), status="
                + String(MB_ERR_PIPELINE_NOT_FOUND)
            )

        # ── resident buffers: SAME shapes as _MBQwen3I8AllSimd.
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
        self.m_partial_addr = UInt64(0); self.m_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.l_partial_addr = UInt64(0); self.l_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.o_partial_addr = UInt64(0); self.o_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

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
        self.descriptors_deep = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
          - `compile_function[_splitk_partial_kernel_simd_batched4]`/`[_splitk_merge_kernel_simd]`:
            deferring WHEN this Mojo statement executes does not change WHICH pipelines
            `_mb_open_session` discovers in `__init__` (this file's own module docstring: pipeline
            discovery is driven by scanning this binary's embedded `.metallib` blobs by NAME, not by
            `compile_function` call order) — `self.pipeline_idx_split`/`pipeline_idx_merge`
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
        _ = cctx.compile_function[_splitk_partial_kernel_simd_batched4]()
        _ = cctx.compile_function[_splitk_merge_kernel_simd]()

        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * 4, self.m_partial_addr, self.m_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk m_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * 4, self.l_partial_addr, self.l_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk l_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * self.d_head * 4, self.o_partial_addr, self.o_partial_ptr) < 0:
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
        dispatches, `_splitk_partial_kernel_simd_batched4` (`grid_x = h_q * _ATTN_SPLITK_N_SPLITS`)
        then `_splitk_merge_kernel_simd` (`grid_x = h_q`, same shape the SDPA dispatch it replaces
        used) — 7 descriptors per layer here against that method's 6. (`_MBQwen3I8AllSimd3`'s
        own version of this method dispatches the UNBATCHED `_splitk_partial_kernel_simd` here
        instead — this struct's own docstring, seventh addition, has the full account.) Every OTHER role (`norm_gemv`,
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

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights, SDPA + GEMV + lm_head + argmax-reduce SIMD-shuffle reduction, deep split-K barrier-batched x4)"

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
        (`_build_descriptors_deep`'s plan: `_splitk_partial_kernel_simd_batched4` + `_splitk_
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
                    # arg index 6, not 4: `_splitk_partial_kernel_simd_batched4`'s own signature puts
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


struct _MBQwen3I8AllSimd5(Movable):
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
    `compile_function` on the barrier-tree `_argmax_reduce_kernel` — only its `_simd`
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

    A SIXTH addition, fixing a real (if modest) side effect of the fifth: `self.descriptors_deep` and
    its two kernel compiles / three scratch buffers are now built LAZILY, by `_ensure_deep_
    initialized`, the first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` — not
    unconditionally in `__init__` the way the fifth addition first shipped them. A controlled,
    interleaved A/B against real installed mlx-lm found the FIFTH addition's unconditional
    construction-time cost (~560us, measured: ~71.5us kernel compiles + ~486us buffer allocs + ~13us
    descriptor-table alloc/build) was small in absolute terms but real and structural, present in
    EVERY session including one that only ever runs shallow (e.g. the published 16-token race), which
    the owner's zero-tolerance-for-regression bar does not accept even at this size. See
    `_ensure_deep_initialized`'s own docstring for why deferring it is safe: `_sdpa_kernel_simd`, the
    `self.descriptors` table, and the branch that submits it remain UNTOUCHED (as the fifth addition's
    own docstring above already establishes) — this sixth addition only changes WHEN the deep path's
    OWN one-time setup cost is paid, never what either path computes.

    AN EIGHTH addition, and the ONLY difference from `_MBQwen3I8AllSimd3` (this struct's own
    immediate predecessor, byte-identical up to this point): `_ensure_deep_initialized` now compiles
    `residentk.kernels._splitk_partial_kernel_simd_native` -- the REDUCTION-SHAPE twin of the fifth
    addition's own `_splitk_partial_kernel_simd`, confining each (head, split)'s per-key reduction to
    ONE 32-lane SIMD-group (`block_dim = WARP_SIZE`, each lane owning `d_head / WARP_SIZE` elements,
    one `_warp_sum` per key, zero `barrier()` calls anywhere in the kernel) instead of FOUR SIMD-
    groups combined via a shared array and two `barrier()` calls per key -- for `_build_descriptors_
    deep`'s split dispatch instead of the two-level kernel. `_build_descriptors_deep`'s PLAN is
    otherwise byte-unchanged (same grid width, same argument order, same buffers): the ONLY two
    things that differ are WHICH compiled pipeline `self.pipeline_idx_split` resolves to, and that
    one dispatch's `block_dim` header field (`WARP_SIZE` instead of `self.d_head`) -- confirming
    directly, not just trusting, the design phase's own claim that `block_dim` is a per-dispatch
    header field (`metaldispatch._mb_set_header`), not baked into the compiled pipeline, so changing
    it really is the one-line change at the call site that claim said it would be.

    `_ATTN_SPLITK_N_SPLITS` is UNCHANGED (16, the value `_MBQwen3I8AllSimd3` itself already ships) --
    this struct fixes the reduction SHAPE only, deliberately isolated from any occupancy/grid-width
    change, so this struct's own race against `_MBQwen3I8AllSimd3` attributes any effect to exactly
    one variable. See `_splitk_partial_kernel_simd_native`'s own docstring (`residentk.kernels`) for
    the full root-cause account (grounded in mlx-lm's and llama.cpp's real source), the isolated
    kernel-level verification (`test_residentk_attn_splitk_native_kernel.mojo`), and -- most
    importantly -- the HONEST RESULT that docstring states first.

    HONEST RESULT: this struct exists to RACE its own predecessor head to head, and the answer, fully
    measured (GPU-counter isolated AND a full 4096-token generation, see `_splitk_partial_kernel_
    simd_native`'s own docstring for the complete numbers) is that this fix does NOT win at `_ATTN_
    SPLITK_N_SPLITS = 16` -- `splitk_partial`'s own GPU time REGRESSES, and the regression WIDENS with
    depth (near parity at `n_keys=50`, ~1.3x at 500, ~1.9x at 2000, ~2.3x at 4000), the opposite shape
    from the design phase's own isolated scratch-probe projection (which measured this exact change
    WINNING, and winning more with depth, at this same `n_splits=16`). The full-token effect matches:
    a real 4096-token generation from both structs, same prompt, same checkpoint, produced BIT-
    IDENTICAL token ids at every position (zero mismatches, max logit delta 3.36e-04 -- correctness is
    NOT in question) but measured 75.6-77.7 decode tok/s for this struct against `_MBQwen3I8AllSimd3`'s
    own 114.9-125.7 tok/s over the same run, interleaved, repeated rounds -- a reproducible ~1.5-1.6x
    SLOWDOWN. So this struct is a real, correctness-verified, PERFORMANCE-NEGATIVE finding, landed as
    exactly that: additive, a new struct alongside the existing one, never a replacement, and never
    the arm the published race or any future race should reach for at this `n_splits` value (this
    file's own "one pipeline per role, own binary" discipline already requires the two-level and
    native split kernels to never be compiled together, so a new struct -- rather than a branch inside
    `_MBQwen3I8AllSimd3` -- was the only way to race the two head to head without one shadowing the
    other's pipeline-name discovery). `_MBQwen3I8AllSimd3` itself, `_splitk_partial_kernel_simd`, and
    every byte of `self.descriptors` and the branch that submits it (this struct's own <threshold
    path, IDENTICAL to `_MBQwen3I8AllSimd3`'s) remain UNTOUCHED by this addition.
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
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
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
                "_MBQwen3I8AllSimd5: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel_simd]()
        # ── the deep-context occupancy fix's two kernels are DELIBERATELY NOT compiled here.
        # `_ensure_deep_initialized` (below) calls `compile_function` on both, lazily, the
        # first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` -- see that method's own
        # docstring for why. This does NOT remove either kernel from THIS binary: both are still
        # referenced by a `compile_function[...]` call reachable from this struct (just a
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
                "metaldispatch: _MBQwen3I8AllSimd5 attn-splitk pipeline(s) not found among "
                + String(count) + " discovered pipelines (split=" + String(self.pipeline_idx_split)
                + " merge=" + String(self.pipeline_idx_merge) + "), status="
                + String(MB_ERR_PIPELINE_NOT_FOUND)
            )

        # ── resident buffers: SAME shapes as _MBQwen3I8AllSimd.
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
        self.m_partial_addr = UInt64(0); self.m_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.l_partial_addr = UInt64(0); self.l_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.o_partial_addr = UInt64(0); self.o_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

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
        self.descriptors_deep = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
          - `compile_function[_splitk_partial_kernel_simd_native]`/`[_splitk_merge_kernel_simd]`:
            deferring WHEN this Mojo statement executes does not change WHICH pipelines
            `_mb_open_session` discovers in `__init__` (this file's own module docstring: pipeline
            discovery is driven by scanning this binary's embedded `.metallib` blobs by NAME, not by
            `compile_function` call order) — `self.pipeline_idx_split`/`pipeline_idx_merge`
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
        _ = cctx.compile_function[_splitk_partial_kernel_simd_native]()
        _ = cctx.compile_function[_splitk_merge_kernel_simd]()

        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * 4, self.m_partial_addr, self.m_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk m_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * 4, self.l_partial_addr, self.l_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk l_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS * self.d_head * 4, self.o_partial_addr, self.o_partial_ptr) < 0:
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
        dispatches, `_splitk_partial_kernel_simd_native` (`grid_x = h_q * _ATTN_SPLITK_N_SPLITS`,
        `block_dim = WARP_SIZE` -- the one field this struct's own dispatch differs on, see below)
        then `_splitk_merge_kernel_simd` (`grid_x = h_q`, `block_dim = d_head`, same shape the SDPA
        dispatch it replaces used) — 7 descriptors per layer here against that method's 6.
        (`_MBQwen3I8AllSimd3`'s own version of this method dispatches the TWO-LEVEL `_splitk_
        partial_kernel_simd` at `block_dim = d_head` here instead — this struct's own docstring,
        eighth addition, has the full account.) Every OTHER role (`norm_gemv`,
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
            # dispatch `_build_descriptors` issues here with a grid `_ATTN_SPLITK_N_SPLITS` times
            # bigger, recruiting that many times the warps for the SAME query token.
            _mb_set_header(
                self.descriptors_deep, d, self.pipeline_idx_split,
                self.h_q * _ATTN_SPLITK_N_SPLITS, WARP_SIZE, 12,
            )
            # `block_dim = WARP_SIZE` (32), NOT `self.d_head` (128) -- the ONE field this struct's
            # own split dispatch differs on from `_MBQwen3I8AllSimd3`'s own `_build_descriptors_
            # deep`: `_splitk_partial_kernel_simd_native` is ONE 32-lane SIMD-group per (head,
            # split), not four, per that kernel's own docstring. Confirms the design phase's own
            # claim directly: `block_dim` really is a one-line change at this call site, not new
            # plumbing -- every argument below, the grid width, and every OTHER descriptor in this
            # table are otherwise byte-identical to `_MBQwen3I8AllSimd3`'s own plan.
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



struct _MBQwen3I8AllSimd6(Movable):
    """Candidate 1 from `~/.claude/plans/sdpa-simdgroup-native-redesign.md`, built on top of
    `_MBQwen3I8AllSimd5`'s own Candidate 2 (this struct's immediate predecessor, byte-identical up to
    this point): identical descriptor plan, identical `step()` contract, identical `_ensure_deep_
    initialized` lazy-init discipline, identical `_splitk_partial_kernel_simd_native` reduction-shape
    kernel for the deep split dispatch — the ONLY difference is which `n_splits` constant that
    dispatch's grid width and this struct's own three scratch buffers (`m_partial`/`l_partial`/
    `o_partial`) are sized from: `_ATTN_SPLITK_N_SPLITS_NATIVE` (80, this file's own top-level
    constant — see its own docstring for the full sweep that picked it), NOT the shared `_ATTN_
    SPLITK_N_SPLITS` (16) `_MBQwen3I8AllSimd3` and `_MBQwen3I8AllSimd5` both still use, untouched by
    this addition.

    MOTIVATION: `_MBQwen3I8AllSimd5`'s own HONEST RESULT (see its docstring, and `_splitk_partial_
    kernel_simd_native`'s own) found the reduction-shape fix alone, at `n_splits` UNCHANGED, a REAL
    REGRESSION once embedded in the real pipeline (not the isolated design-phase probe's own
    projected win) — most likely because `block_dim = WARP_SIZE` drops total warps in flight 4x for
    this dispatch at a FIXED grid width, and 16 splits' worth of grid width was tuned for the OLD,
    4x-wider-per-threadgroup kernel, not this one. This struct is the plan's own next step: widen
    `n_splits` to recruit the freed SIMD-groups back as independent key-parallel workers, matching
    mlx-lm's own much wider grid split at this depth (128-way) — but RE-TUNED FROM SCRATCH for this
    specific kernel/hardware combination rather than assumed, since the plan itself flags that the
    old 16-32 plateau was found for the barrier-heavy kernel and the design phase's own isolated
    probe (which projected `n_splits=64` as its own best guess) was ALREADY shown, by `_MBQwen3I8
    AllSimd5`'s own honest result, not to transfer once embedded in the real pipeline.

    THE SWEEP: `_ATTN_SPLITK_N_SPLITS_NATIVE`'s own docstring has the complete account — a real,
    GPU-counter-isolated measurement of `splitk_partial`'s own role-level GPU time, `n_keys=4000`,
    on `_MBQwen3I8AllSimd5`'s OWN descriptor plan (the production kernel and dispatch code, `_ATTN_
    SPLITK_N_SPLITS` temporarily overridden per candidate and rebuilt — never a new scratch kernel),
    swept over 21 candidates from 16 to 256. The result was NOT a smooth, single-optimum curve: GPU-
    core-count occupancy quantization (this machine reports 40 Metal GPU cores; `h_q * n_splits` is
    the total warp count this dispatch puts in flight at `block_dim = WARP_SIZE`) produced sharp,
    non-monotonic swings — `n_splits=84-96` measured WORSE than both `64` and `128` despite being
    strictly wider. `n_splits=80` (`16*80 = 1280 = 32*40`, an exact multiple of the core count) was
    the reproducible minimum across 5 repeated rounds, chosen over the design phase's own untested
    guess of 64 specifically because it was measured, not assumed, on the real kernel this time.

    HONEST RESULT: widening the splits is a REAL WIN, reversing `_MBQwen3I8AllSimd5`'s own regression
    and then some — AT THE DEPTH THE ROLE-LEVEL PROBE MEASURED. `splitk_partial`'s own GPU time at
    `n_keys=4000` (28-layer sum): `_MBQwen3I8AllSimd3` (shipped, two-level, `n_splits=16`) `~7.6-
    7.8ms`; `_MBQwen3I8AllSimd5` (native, `n_splits=16`, the regression this struct fixes) `~17.8-
    18.0ms`; THIS struct (native, `n_splits=80`) `~4.7-5.5ms` — roughly `1.5x` FASTER than the shipped
    kernel there, and roughly `3.5x` faster than its own immediate predecessor's regressed
    configuration. Pipeline-wide AT THAT SAME `n_keys=4000` (sum of every role's own GPU time):
    `_MBQwen3I8AllSimd3` `~10.8ms` total vs. this struct's `~8.3ms` — `~1.30x` less total per-token GPU
    time AT THAT DEPTH.

    The real, full 4096-token, teacher-forced-independent decode-tok/s self-comparison against
    `_MBQwen3I8AllSimd3` (`qwen3_generate_batch_i8_allsimd6_longctx_probe.mojo` vs. `..._allsimd3_
    longctx_probe.mojo`, identical checkpoint/prompt, `max_ctx=8192`, freshly rebuilt binaries,
    interleaved, 3 rounds each) confirms correctness (0/4096 token mismatches, max logit delta
    2.63e-04, well inside this codebase's own established Float32-reordering bound) AND a real, but
    SMALLER, win than the single-depth role-level number alone would suggest: `_MBQwen3I8AllSimd3`
    120.9 / 120.9 / 128.8 tok/s (mean 123.5); this struct 132.2 / 132.7 / 128.0 tok/s (mean 130.9) —
    a reproducible `~1.06x` (`~6%`) WIN, this struct ahead in 2 of 3 rounds and a near-tie in the
    third, never behind by a meaningful margin in any round. This is honestly smaller than the
    `~1.30x` pipeline-wide number above because that number is AT ONE DEPTH (`n_keys=4000`, near the
    END of a 4096-token run); the full run's own decode-tok/s average is pulled down by the ~3584
    steps below `n_keys=4000` (many of them below `_ATTN_SPLITK_THRESHOLD=512` entirely, where
    NEITHER arm's split kernel runs at all) — a whole-run average necessarily dilutes a win that is
    concentrated at depth, exactly the shape this task's own methodology predicts, not a discrepancy
    to explain away.

    Same additive, one-struct-per-experiment discipline every sibling in this file follows:
    `_MBQwen3I8AllSimd3`, `_MBQwen3I8AllSimd5`, `_splitk_partial_kernel_simd`, `_splitk_partial_
    kernel_simd_native` itself, and every byte of `self.descriptors` and the branch that submits it
    (this struct's own <threshold path, IDENTICAL to `_MBQwen3I8AllSimd3`'s and `_MBQwen3I8AllSimd5`'s
    own) remain UNTOUCHED by this addition — this struct only differs from `_MBQwen3I8AllSimd5` in
    which `n_splits` constant `_ensure_deep_initialized`/`_build_descriptors_deep` read.
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
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
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
                "_MBQwen3I8AllSimd6: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_simd_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_simd_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_simd_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel]()
        _ = cctx.compile_function[_sdpa_kernel_simd]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_simd_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel_simd]()
        # ── the deep-context occupancy fix's two kernels are DELIBERATELY NOT compiled here.
        # `_ensure_deep_initialized` (below) calls `compile_function` on both, lazily, the
        # first time `step()` actually crosses `_ATTN_SPLITK_THRESHOLD` -- see that method's own
        # docstring for why. This does NOT remove either kernel from THIS binary: both are still
        # referenced by a `compile_function[...]` call reachable from this struct (just a
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
                "metaldispatch: _MBQwen3I8AllSimd6 attn-splitk pipeline(s) not found among "
                + String(count) + " discovered pipelines (split=" + String(self.pipeline_idx_split)
                + " merge=" + String(self.pipeline_idx_merge) + "), status="
                + String(MB_ERR_PIPELINE_NOT_FOUND)
            )

        # ── resident buffers: SAME shapes as _MBQwen3I8AllSimd.
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
        self.m_partial_addr = UInt64(0); self.m_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.l_partial_addr = UInt64(0); self.l_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.o_partial_addr = UInt64(0); self.o_partial_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)

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
        self.descriptors_deep = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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
          - `compile_function[_splitk_partial_kernel_simd_native]`/`[_splitk_merge_kernel_simd]`:
            deferring WHEN this Mojo statement executes does not change WHICH pipelines
            `_mb_open_session` discovers in `__init__` (this file's own module docstring: pipeline
            discovery is driven by scanning this binary's embedded `.metallib` blobs by NAME, not by
            `compile_function` call order) — `self.pipeline_idx_split`/`pipeline_idx_merge`
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
        _ = cctx.compile_function[_splitk_partial_kernel_simd_native]()
        _ = cctx.compile_function[_splitk_merge_kernel_simd]()

        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS_NATIVE * 4, self.m_partial_addr, self.m_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk m_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS_NATIVE * 4, self.l_partial_addr, self.l_partial_ptr) < 0:
            raise Error("metaldispatch: buffer alloc failed (attn splitk l_partial)")
        if _mb_alloc_buffer(self.h_q * _ATTN_SPLITK_N_SPLITS_NATIVE * self.d_head * 4, self.o_partial_addr, self.o_partial_ptr) < 0:
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
                self.h_q * _ATTN_SPLITK_N_SPLITS_NATIVE, WARP_SIZE, 12,
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
            _mb_set_arg_int(self.descriptors_deep, d, 7, _ATTN_SPLITK_N_SPLITS_NATIVE)
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
            _mb_set_arg_int(self.descriptors_deep, d, 4, _ATTN_SPLITK_N_SPLITS_NATIVE)
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


struct _MBQwen3I8AllSimd7(Movable):
    """The GENUINELY DYNAMIC, PER-STEP split-K twin of `_MBQwen3I8AllSimd6` — byte-identical shallow
    path, byte-identical `_splitk_partial_kernel_simd_native`/`_splitk_merge_kernel_simd` deep
    dispatch pair, byte-identical descriptor PLAN, but replaces BOTH of `_MBQwen3I8AllSimd6`'s fixed
    constants (`_ATTN_SPLITK_THRESHOLD = 512`, `_ATTN_SPLITK_N_SPLITS_NATIVE = 80`) with the calibrated
    formula in `residentk.contract` (`residentk_splitk_should_split`/`residentk_splitk_policy`/
    `residentk_splitk_max_n_splits` — see that module's own docstring for the full calibration and
    independent-re-verification account before trusting either number below).

    WHY A FIXED CONSTANT WAS NEVER GOING TO BE ENOUGH, restated from the calibration record: PR #523
    tuned `_ATTN_SPLITK_N_SPLITS_NATIVE = 80` at ONE depth (`n_keys=4000`) and measured a real
    ~11-12% narrowing of the gap THERE, but the AGGREGATE effect across a full generation barely
    moved, because a real decode's `n_keys` sweeps from 1 up to whatever context length the run
    reaches, passing through the untouched 256-511 "dead zone" and every shallow depth below it on
    the way — a single depth's own optimum does not generalize across that whole range. This struct
    computes the split count FRESH, from THIS step's own `n_keys` and THIS session's own detected GPU
    core count, exactly the same shape llama.cpp's own `nwg` formula takes (`nwg=32; nsg=1; while
    (2*nwg*nsg*32 < n_keys && nsg<4) nsg*=2` — a formula evaluated per dispatch, not a table entry).

    TWO THINGS ARE NOW DYNAMIC, NOT ONE:
      1. `n_cores` — queried ONCE, at session-open, via `metaldispatch.ffi._mb_gpu_core_count` (a new,
         additive IOKit `AGXAccelerator`/`gpu-core-count` registry probe in `batch_shim.m` — neither
         `accel.device`'s existing probe nor `MTLDevice`'s own public API expose a core count on this
         toolchain, confirmed by direct inspection before adding a new one). Stored as `self.n_cores`,
         whatever the probe returns (including a failure sentinel `<= 0`) — every place that reads it
         is a `residentk.contract` function that ALREADY applies the documented fallback
         (`RESIDENT_SPLITK_FALLBACK_N_CORES = 40`, chosen specifically because it reproduces PR #523's
         own `_ATTN_SPLITK_N_SPLITS_NATIVE = 80` exactly), so this struct never duplicates that
         fallback logic itself.
      2. `n_splits` — recomputed from `residentk_splitk_policy(n_keys, self.n_cores, self.h_q)` on
         EVERY deep-branch `step()` call, but only actually RE-PATCHED into the descriptor table
         (`_apply_n_splits`, below) when it differs from the previous step's value
         (`self.deep_last_n_splits`) — cheap either way (pure host arithmetic plus, at most, `7 *
         n_layers` small pointer writes, no device call), but skipping the write entirely on the
         (common, since the formula is a coarse log2 step, not a value that changes every single
         token) steps where the depth bucket has not changed yet is strictly cheaper and still
         correct, matching this task's own "once per step, or once when n_keys crosses into a new
         regime, whichever is cheaper" guidance.

    BUFFER SIZING, decided ONCE, matching PR #521's own lazy-init discipline: `self.n_splits_max =
    residentk_splitk_max_n_splits(self.n_cores, self.h_q)` — the ceiling `residentk_splitk_policy`
    could EVER return for this session's own `(n_cores, h_q)` — computed once in `__init__` (pure
    arithmetic, no allocation yet) and used by `_ensure_deep_initialized` to size `m_partial`/
    `l_partial`/`o_partial` ONCE, lazily, the first time `step()` actually calls it — exactly
    `_MBQwen3I8AllSimd6`'s own account of why those three allocations are deferred, just sized from a
    runtime-computed ceiling instead of the comptime `_ATTN_SPLITK_N_SPLITS_NATIVE`. Every subsequent
    `_apply_n_splits` call only ever NARROWS the grid width and the two kernels' `n_splits` value
    arguments to some `new_n_splits <= self.n_splits_max` (`residentk_splitk_policy`'s own ceiling
    clamp guarantees this), so a smaller step never touches memory past what the buffers were sized
    for at construction — the identical safety argument `_MBQwen3I8SplitKSweep.set_n_splits`'s own
    docstring makes for the calibration sweep tool this struct's `_apply_n_splits` is modeled on.

    RETIRES THE FIXED THRESHOLD TOO: `_ATTN_SPLITK_THRESHOLD = 512` is never read here.
    `residentk_splitk_should_split` gates at `n_keys = 32` instead — the calibration record's own
    dead-zone extension (and this task's own independent re-verification of it) found the native
    kernel a real, growing win from `n_keys = 32` onward (a measured ~1.4x at 32, ~1.8-2.8x at
    64-256), not merely "no longer a loss" — so the old, much higher gate was leaving a real win on
    the table across that whole range, not just at the one depth PR #523 tuned for.

    CORRECTNESS IS UNCHANGED FROM `_MBQwen3I8AllSimd6`: this struct dispatches the SAME two kernels
    (`_splitk_partial_kernel_simd_native`, `_splitk_merge_kernel_simd`, both byte-unmodified, both
    proven correct for ANY `n_splits` including `n_splits > n_keys` — see that kernel's own
    docstring) through the SAME descriptor plan; only WHICH `n_splits` value and WHICH GPU core count
    feed that plan's arithmetic are now runtime-computed instead of comptime constants. See this
    task's own staged-correctness account (isolated probe, shallow 16-token regression, deep teacher-
    forced spot-check, full generation match) for the verification this claim rests on before any
    speed comparison was trusted.

    Same additive, one-struct-per-experiment discipline every sibling in this file follows:
    `_MBQwen3I8AllSimd6` (this struct's immediate predecessor) is byte-unmodified by this addition,
    and so is every kernel in `residentk.kernels`.
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
    var n_cores: Int
    """Detected GPU core count, queried ONCE via `_mb_gpu_core_count()` in `__init__` — see the
    struct docstring. May be `<= 0` (probe failed); every reader is a `residentk.contract` function
    that already applies the documented fallback, so this field is stored exactly as the probe
    returned it, never pre-corrected here."""
    var n_splits_max: Int
    """`residentk_splitk_max_n_splits(self.n_cores, self.h_q)` — the ceiling the three scratch
    buffers below are sized for. Computed once in `__init__`; never recomputed after, since `n_cores`
    and `h_q` are themselves fixed for this session's whole life."""
    var deep_last_n_splits: Int
    """The `n_splits` value currently patched into `self.descriptors_deep` (or -1 before the first
    deep-branch call) — lets `step()` skip `_apply_n_splits` entirely on a step whose policy-computed
    `n_splits` has not changed from the previous deep step's, per the struct docstring's account of
    why that is cheaper and still correct."""
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
    """See `_MBQwen3I8AllSimd6`'s own field docstring for the full account of the lazy, two-table
    discipline these fields (from `descriptors_deep` onward) implement — unchanged here except that
    the deep table's OWN `n_splits` is no longer fixed at construction; see `_apply_n_splits`."""

    def __init__(
        out self, d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int,
        n_layers: Int, vocab: Int, max_ctx: Int, eps: Float64, scale: Float64,
    ) raises:
        """Identical refusal to `_MBQwen3I8AllSimd6.__init__`'s own — see that constructor's
        docstring for why `d_head` must be a positive multiple of `WARP_SIZE`."""
        if d_head % WARP_SIZE != 0:
            raise Error(
                "_MBQwen3I8AllSimd7: d_head=" + String(d_head) + " is not a multiple of WARP_SIZE="
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

        # ── same kernel set as `_MBQwen3I8AllSimd6.__init__` -- see that constructor's own docstring
        # for why the deep-context pair is deliberately NOT compiled here (deferred to
        # `_ensure_deep_initialized`).
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

        var opened = _mb_open_session()
        if opened < 0:
            raise Error("metaldispatch: algenta_open_session failed, status=" + String(MB_ERR_SESSION_OPEN_FAILED))

        # ── the ONE new runtime query this struct adds over `_MBQwen3I8AllSimd6`: this host's GPU
        # core count, read ONCE here (never per step -- the hardware does not change mid-session) via
        # the IOKit-registry probe `metaldispatch.ffi._mb_gpu_core_count` added alongside this struct.
        # A negative/zero result (probe failed) is stored AS-IS, not corrected here -- see the field's
        # own docstring for why every reader already handles that case.
        self.n_cores = _mb_gpu_core_count()
        self.n_splits_max = residentk_splitk_max_n_splits(self.n_cores, self.h_q)
        self.deep_last_n_splits = -1

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
                "metaldispatch: _MBQwen3I8AllSimd7 attn-splitk pipeline(s) not found among "
                + String(count) + " discovered pipelines (split=" + String(self.pipeline_idx_split)
                + " merge=" + String(self.pipeline_idx_merge) + "), status="
                + String(MB_ERR_PIPELINE_NOT_FOUND)
            )

        # ── resident buffers: SAME shapes as `_MBQwen3I8AllSimd6`.
        var n_qkv = (h_q + 2 * h_kv) * d_head
        var n_pairs = d_head // 2

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

        # ── deep-context split/merge scratch: sized for `self.n_splits_max` (the runtime-computed
        # ceiling), not the old comptime `_ATTN_SPLITK_N_SPLITS_NATIVE` -- see the struct docstring's
        # "BUFFER SIZING" paragraph. Still a null placeholder until `_ensure_deep_initialized`
        # allocates lazily, same discipline as `_MBQwen3I8AllSimd6`.
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

        self._build_descriptors(n_qkv)

    def _ensure_deep_initialized(mut self) raises:
        """Identical lazy-init discipline to `_MBQwen3I8AllSimd6._ensure_deep_initialized` — see
        that method's own docstring for the full account of why deferring each of these four costs
        (two kernel compiles, three buffer allocs, the descriptor build) to the first deep-branch
        `step()` call is safe. The only difference: the three scratch buffers are sized for
        `self.n_splits_max` (computed once in `__init__` from the runtime-detected core count),
        not a comptime constant."""
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
        """Byte-identical plan to `_MBQwen3I8AllSimd6._build_descriptors` — see that method's own
        docstring."""
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
        """Byte-identical PLAN to `_MBQwen3I8AllSimd6._build_descriptors_deep` -- same roles, same
        order, same argument layout -- with exactly one difference: the split dispatch's initial grid
        width and both kernels' initial `n_splits` value arguments are seeded from `self.n_splits_max`
        (the runtime-computed ceiling) instead of the comptime `_ATTN_SPLITK_N_SPLITS_NATIVE`. This
        initial value is provisional -- `step()` calls `_apply_n_splits` with the REAL, policy-
        computed value for that step's own `n_keys` before ever submitting this table for the first
        time, exactly the same "build wide, then narrow before first use" sequencing `_MBQwen3I8
        SplitKSweep`'s own `__init__`/`set_n_splits` pair already established for the calibration
        sweep tool this method is modeled on."""
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

            # ── split: unnormalized partial (m, l, o) per (head, split) — grid width seeded from
            # `self.n_splits_max` here; `_apply_n_splits` narrows both this header's `grid_x` and the
            # `n_splits` value argument below to the real per-step value before first use.
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

            # ── merge: the (currently `self.n_splits_max`, later `_apply_n_splits`-narrowed) partials
            # -> ONE normalized attn_out, same shape (`grid_x=h_q`) the SDPA dispatch it replaces used.
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
        """Re-patches the split dispatch's grid width and both kernels' `n_splits` value arguments
        for every layer, IN PLACE, to `new_n_splits` — the production twin of `_MBQwen3I8SplitKSweep.
        set_n_splits` (`benchmarks/llm_smoke/metal_batch_dispatch/qwen3_probe_splitk_native_sweep.
        mojo`, this struct's own calibration tool), same offsets, same safety argument: `_mb_set_
        header` only ever writes a descriptor's 16-byte HEADER, never the args area, so narrowing
        `grid_x` here cannot corrupt any argument already in that same descriptor; the two `n_splits`
        VALUE arguments (`splitk_partial`'s arg index 7, `splitk_merge`'s arg index 4) are repatched
        separately, right after. Safe for any `new_n_splits` in `[1, self.n_splits_max]` — the three
        scratch buffers stay sized for `self.n_splits_max` (`_ensure_deep_initialized`), so a smaller
        grid width and a smaller `n_splits` value together only ever address a PREFIX of each buffer.
        `residentk_splitk_policy`'s own ceiling clamp guarantees every value `step()` ever passes here
        already satisfies that bound — this method does not re-check it, matching `set_n_splits`'s own
        precedent of trusting its caller's own clamp rather than re-deriving it.

        Does not touch `n_keys` (arg index 6 on the split descriptor) — `step()`'s own pre-existing
        `nkeys_offsets_deep` patching sets that separately, exactly as every other per-step-varying
        argument in this file already works."""
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
        return "metal (batched shim, int8 weights, SDPA + GEMV + lm_head + argmax-reduce SIMD-shuffle reduction, deep split-K native single-SIMD-group reduction, DYNAMIC per-step n_splits policy)"

    def dispatch_budget(self) -> Int:
        return self.n_descriptors

    def n_cores_detected(self) -> Int:
        """The GPU core count this session queried at open time (may be `<= 0` if the probe failed —
        see the `n_cores` field's own docstring). Exposed read-only for observability (probes/tests
        that want to print or assert on what this session actually detected), never mutated after
        `__init__`."""
        return self.n_cores

    def n_splits_currently_applied(self) -> Int:
        """The `n_splits` value currently patched into the deep descriptor table, or -1 if `step()`
        has never taken the deep branch yet this session. Exposed for the same observability reason
        as `n_cores_detected` — lets a probe log/assert which policy-computed configuration a given
        depth actually ran with, without re-deriving it independently."""
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
        """`_MBQwen3I8AllSimd6.step`'s own body, PLUS the dynamic policy: the branch gate is now
        `residentk_splitk_should_split(n_keys)` (32) instead of the fixed `_ATTN_SPLITK_THRESHOLD`
        (512), and the deep branch computes `n_splits = residentk_splitk_policy(n_keys, self.n_cores,
        self.h_q)` FRESH every call, applying it via `_apply_n_splits` only when it differs from the
        previous deep step's value — see the struct docstring's "TWO THINGS ARE NOW DYNAMIC" section
        for the full account of why recompute-every-step-but-only-patch-on-change is both cheap and
        correct.

        Below the gate, this is BYTE-FOR-BYTE `_MBQwen3I8AllSimd6`'s own shallow branch — patching and
        submitting `self.descriptors`, no policy call at all, so a session that never crosses the
        (now much lower) gate pays nothing extra over any sibling struct's own shallow path."""

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
    them apart. This struct's constructor therefore never calls `compile_function` on the
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

    def __init__(
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
        _ = cctx.compile_function[_embed_row_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv_kernel_i8]()
        _ = cctx.compile_function[_gemv_accum_kernel_i8]()
        _ = cctx.compile_function[_norm_gemv2_swiglu_kernel_i8]()
        _ = cctx.compile_function[_qk_rope_write_kernel_kvf16]()
        _ = cctx.compile_function[_sdpa_kernel_kvf16]()
        _ = cctx.compile_function[_lmhead_argmax_kernel_i8]()
        _ = cctx.compile_function[_argmax_reduce_kernel]()

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

        self.hidden_addr = UInt64(0); self.hidden_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.qkv_addr = UInt64(0); self.qkv_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.q_rot_addr = UInt64(0); self.q_rot_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.attn_out_addr = UInt64(0); self.attn_out_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.act_addr = UInt64(0); self.act_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_val_addr = UInt64(0); self.blk_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.blk_idx_addr = UInt64(0); self.blk_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_val_addr = UInt64(0); self.out_val_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
        self.out_idx_addr = UInt64(0); self.out_idx_ptr = UnsafePointer[UInt8, origin=MutAnyOrigin](unsafe_from_address=1)
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

    def _build_descriptors(mut self, n_qkv: Int) raises:
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

    def device_name(self) -> String:
        return "metal (batched shim, int8 weights + fp16 kv-cache)"

    def dispatch_budget(self) -> Int:
        return self.n_descriptors

    def upload_globals(
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

    def upload_layer(
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

    def seal(mut self) -> Int:
        return MB_OK

    def step(mut self, token_id: Int, pos: Int) raises -> _StepOut:
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


def _mb_preflight(
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
