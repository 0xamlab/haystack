"""metaldispatch.session_prefill_policy — a single, resolved SESSION execution plan (attention +
GEMM + the KV-cache producer/consumer contract they imply -- round 5, 2026-08-08).

@capability-module
deterministic: true
stateful: false
batch_capable: false
stream_capable: false
seed_requirements: none
supported_dtypes: none
backend: mojo
surfaces: none
golden_vectors: mojo/tests/libs/test_metaldispatch_session_prefill_policy.mojo
benchmark: none
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

This module holds the plan types + pure resolution logic for
`_MBQwen3I8AllSimd7Prefill`, replacing the overlapping-boolean-flag pile
(`use_native_grouped_fa_attn` / `use_native_grouped_fa_attn_no_mirror` / `use_qkv_proj_bm64` /
`use_vecload4_all_roles`) that grew, additively, across the Attention Compiler Plan v1.0 / Project
Redline reopening's own Phase 2C and step 2/4 entries.

WHY THIS FILE EXISTS
---------------------
Two real, independently-reproduced regressions came from exactly the same root cause: the request
was represented as several INDEPENDENT `Bool` fields that can hold a mutually-contradictory
combination at the same time (both `True`), with no way to tell "the caller explicitly asked for
this" apart from "this is just sitting at whatever `__init__`'s own hardcoded default happens to
be today." (1) Flipping `use_native_grouped_fa_attn_no_mirror`'s own hardcoded default to `True`
(to measure the blast radius of shipping it) broke the OFF-path suite, which never links the AF
blobs at all -- fixed by a graceful blob-availability fallback. (2) The SAME default flip broke the
WITH-MIRROR AF suite too: `prefill_batch` checked `use_native_grouped_fa_attn_no_mirror` BEFORE
`use_native_grouped_fa_attn`, so with the AF blobs linked (as that suite does) and the no-mirror
default now `True`, the no-mirror branch silently outranked an EXPLICIT `use_native_grouped_fa_
attn=True` request from a test that never touched the no-mirror flag at all. Reordering the two
`if` statements would only relocate the ambiguity, not remove it -- with two independent `Bool`
fields, *some* precedence rule is unavoidable, and every possible rule is arbitrary from the
perspective of whichever flag's value the caller did not actually intend to set.

THE FIX: a single, resolved plan. `ResolvedSessionExecutionPlan` holds exactly one attention-path choice
and exactly one GEMM-tier choice -- both closed, small, mutually exclusive sets, matching this
file's own established convention for such a set elsewhere in `metaldispatch.session` (`_ROLE_*`
/ `_PFROLE_*` / `_AFROLE_*`, `Int`-backed named constants -- this pinned Mojo toolchain
(1.0.0b2) has no `enum`/tagged-union keyword; a bare `enum Foo: A; B; C` fails to parse). Because a
single `Int` field cannot simultaneously hold two contradictory values, there is no state in which
"an explicit request" and "some other path's own default" can both be present to compete over --
the ambiguity that caused regression #2 is structurally unrepresentable, not merely avoided by
careful ordering.

`resolve_prefill_execution_plan` (a pure function, not a method, so both `_MBQwen3I8AllSimd7Prefill.
__init__` and its own public `resolve_plan` re-resolution method can share one implementation
without either needing to call a `mut self` method on a not-yet-fully-initialized `self`) takes the
caller's REQUESTED plan plus this session's own real pipeline-availability booleans and produces a
VALIDATED plan: an explicit request for a path whose blobs are not linked into this binary degrades
gracefully to the OFF / original path (matching the already-fixed blob-availability fallback
behavior from regression #1) -- it is never a hard error. An explicit request for a path whose
blobs ARE available is always honored: there is no "silently overridden by a different path's own
default" step anywhere in this function, because there is only ever one requested value to resolve
in the first place.

PROJECT REDLINE REOPENING (2026-08-08), MAKE UNRESOLVED PLAN STATE UNREPRESENTABLE
------------------------------------------------------------------------------------
A THIRD real, disclosed gap survived the redesign above (found by this same investigation's own
adversarial-verify pass, restated in full in `REALRACE_RESULTS.md`'s "PrefillExecutionPlan" entry):
nothing stopped a caller from constructing `_MBQwen3I8AllSimd7Prefill` and dispatching from it
WITHOUT EVER SUPPLYING an explicit request at all -- `__init__`'s own `requested_plan` parameter had
a default, and a caller who never touches it (or never calls `resolve_plan` afterward) silently gets
whatever that hardcoded default happens to be TODAY, with no signal that this is different from a
caller who deliberately wants exactly that default. Two real call sites did precisely this: `test_
metaldispatch_session_prefill_af.mojo`'s own Gate A, and the ONE function actually wired into the
real runtime-library-dispatch catalog, `qwen3_i8_allsimd7_prefill_decode_flat`. Both happen to be
safe TODAY only because the default itself happens to be the always-safe `PF_ATTN_OFF`/`PF_GEMM_
ORIGINAL` -- but nothing about either call site's OWN code says so; a future change to the literal
default value inside `__init__`'s signature would silently change what both of them do, with zero
compiler or runtime signal.

THE FIX, two independent layers (this file's module docstring's own established "make it
structurally impossible, don't just fix the one case you found" discipline, applied a second time):

  1. TYPE-LEVEL, compiler-enforced: `ResolvedSessionExecutionPlan` used to serve BOTH roles at once -- "a
     caller's raw, un-validated request" AND "the validated value a dispatch decision actually
     reads" -- conflated into one type, which is exactly what let a request be indistinguishable
     from an already-resolved value. `UnresolvedPrefillConfig` (below) is now the ONLY type a
     caller's own request can be -- a DIFFERENT Mojo type than `ResolvedSessionExecutionPlan`, so passing an
     un-resolved request where a resolved plan is expected (or vice versa) is a COMPILE error, not a
     runtime one. `UnresolvedPrefillConfig.resolve(available_pipelines: PrefillPipelineAvailability)
     -> ResolvedSessionExecutionPlan` is the only public way to turn one into the other (a thin wrapper
     around this file's own pre-existing `resolve_prefill_execution_plan`, kept as a free function
     too -- see that struct's own docstring). `_MBQwen3I8AllSimd7Prefill.__init__`'s own
     `requested_plan` parameter is now typed `UnresolvedPrefillConfig`, not `ResolvedSessionExecutionPlan` --
     its default is UNCHANGED in VALUE (`UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL)`,
     byte-for-byte the same all-off default this parameter has always had), but a caller can no
     longer mistake "I am handing the constructor an already-resolved plan" for "I am making a
     request" -- there is no overload or code path that accepts a `ResolvedSessionExecutionPlan` there at
     all anymore.

  2. RUNTIME, defense-in-depth: `PF_UNRESOLVED` (below) is a sentinel `Int` value `resolve_prefill_
     execution_plan`'s own exhaustive `if`/`elif`/`else` branches never produce for either field --
     every real call path that ever WRITES `_MBQwen3I8AllSimd7Prefill.plan` (the constructor, and the
     public `resolve_plan` method) goes through `UnresolvedPrefillConfig.resolve`, so `self.plan` is
     ALWAYS genuinely resolved after either one returns; there is no code path in this file that
     leaves it at a sentinel. But `self.plan` is a public `var` field, and this pinned Mojo toolchain
     (1.0.0b2) has no cross-module private-field enforcement -- nothing stops a caller from directly
     assigning `session.plan = ResolvedSessionExecutionPlan(PF_UNRESOLVED, PF_UNRESOLVED)` (or any other
     out-of-range value), bypassing resolution entirely. `ResolvedSessionExecutionPlan.is_resolved()` gives
     `prefill_batch`/`_apply_m_rows_af_nomirror` (see their own docstrings) a concrete, checkable
     invariant to enforce, so THAT bypass is a loud, immediate `raise`, never a silent re-default to
     `PF_ATTN_OFF` -- closing exactly the class of "one more silent default" this whole file's module
     docstring already exists to eliminate, for a case regression #1/#2's own fix did not cover.

Layer 1 makes the ORIGINAL gap (a caller who never states an intent) unrepresentable at the type
level: `_MBQwen3I8AllSimd7Prefill.__init__` and `.resolve_plan` both still need SOME value to resolve
(Mojo's definite-initialization rule requires `self.plan` be assigned by the end of `__init__`, and a
caller who truly supplies nothing gets the STATED, self-documenting `UnresolvedPrefillConfig(PF_ATTN_
OFF, PF_GEMM_ORIGINAL)` default -- explicit in this file's own source, not a hidden landmine) --
what layer 1 removes is the ABILITY to hand the constructor something that LOOKS already-resolved
and skip the whole point of resolution. Layer 2 is the belt-and-suspenders backstop for the one
remaining way `self.plan` could ever hold a genuinely invalid value: direct field mutation, which no
version of Mojo's type system available in this toolchain can prevent.

PROJECT REDLINE REOPENING (2026-08-08), ROUND 5: THE PLAN NOW OWNS THE WHOLE SESSION'S KV-CACHE
CONTRACT, NOT JUST THE PREFILL DISPATCH CHOICE
------------------------------------------------------------------------------------------------
Round 4's own adversarial pass (restated in full in `REALRACE_RESULTS.md`'s "PrefillExecutionPlan,
round 4" entry) found a FOURTH real, disclosed gap, orthogonal to the three above: `attention`/`gemm`
only resolve a PREFILL dispatch choice, but `PF_ATTN_GROUPED_FA_NO_MIRROR` also changes what the
PERSISTENT KV-cache buffers look like for every DECODE call that follows, for the lifetime of this
session instance -- and nothing in the type this file exports captured that producer/consumer
contract. Concretely: `PF_ATTN_GROUPED_FA_NO_MIRROR` leaves the natural F32 `ck`/`cv` cache genuinely
unwritten and populates ONLY the packed F16 native buffers, so it pairs correctly with ONLY the
decode path that reads those buffers -- but the real production entry point's decode loop called
plain `step()` unconditionally, which only ever knew how to read the natural F32 cache. Pairing
`PF_ATTN_GROUPED_FA_NO_MIRROR` prefill with that decode path would silently corrupt every
multi-token decode past the first generated token -- exactly the kind of state this file's own prior
rounds already made unrepresentable for "unresolved," now needed for "resolved to a self-
contradictory pair."

THE FIX, same discipline as every round above -- make the contradiction structurally impossible to
construct, not merely absent from the one call site that happens to be audited today: this struct
(renamed from `PrefillExecutionPlan` to `ResolvedSessionExecutionPlan` -- restated below -- because
its own scope no longer stops at the prefill dispatch, it now owns the whole session's producer/
consumer contract) grows exactly two new fields, `kv_contract` and `decode`, alongside the pre-
existing `attention`/`gemm`. Neither new field is EVER a caller-supplied request -- there is no
constructor parameter, on `UnresolvedPrefillConfig` or anywhere else, that a caller could use to
directly set either one. Both are derived, deterministically and exhaustively, from `attention`
ALONE, by the two free functions `_derive_kv_contract_for_attention`/`_derive_decode_path_for_
attention` below -- the SAME two functions are called from BOTH sides of the contract: the WRITE
side (`resolve_prefill_execution_plan`, the only place that ever constructs a fully-populated
`ResolvedSessionExecutionPlan`) and the CHECK side (`ResolvedSessionExecutionPlan.is_resolved()`,
which re-derives what `kv_contract`/`decode` MUST be from `self.attention` and compares). Because
both sides call the identical pure function, there is no code path -- not a new caller, not a future
edit to `resolve_prefill_execution_plan`, not a direct field assignment `is_resolved()` would ever
have to catch -- that can produce `PF_ATTN_GROUPED_FA_NO_MIRROR` paired with `DECODE_PATH_LEGACY_
NATURAL_KV`/`KV_CONTRACT_NATURAL_F32`: the pairing is not merely correct today, it is the ONLY
pairing either derivation function is capable of returning for that `attention` value.

`KVCacheContract` (`KV_CONTRACT_NATURAL_F32` / `KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16` /
`KV_CONTRACT_PACKED_F16_NATIVE`) names WHICH persistent KV-cache buffers a `prefill_batch()` call
under this plan leaves populated for every subsequent call on this instance -- restating, as a
checkable value instead of only prose, exactly what each `PF_ATTN_*` constant's own docstring above
already asserts about `ck`/`cv` vs. the native-packed buffers. `DecodePath` (`DECODE_PATH_LEGACY_
NATURAL_KV` / `DECODE_PATH_NATIVE_PACKED_KV`) names which underlying decode implementation the
PUBLIC `step()` method (see `session_prefill.mojo`'s own module docstring addendum) must route to
for THIS plan's own `kv_contract` to be read correctly -- `step()` reads `self.plan.decode` itself
now, so this is no longer a fact a caller needs to know and act on manually (the round-4 gap was
exactly that: the caller-visible API gave no signal that a decision made at PREFILL time obligated a
specific DECODE call afterward)."""

comptime PF_ATTN_OFF: Int = 0
"""The byte-for-byte pre-Attention-Compiler-Plan path: `_pf_ropewrt_kernel` + `_pf_attn_tiled_
kernel_simd` (or the block-of-8 variant, an orthogonal, always-`False`-gated lever inside `_apply_m_
rows` itself -- never part of this plan). Requires no `attention_forge/` blobs at all; always
resolvable regardless of what is linked into this binary."""

comptime PF_ATTN_GROUPED_FA_WITH_MIRROR: Int = 1
"""Native-KV-producer + Candidate A's grouped-head fused-FlashAttention, PLUS a second, additive
per-layer dispatch that double-writes the natural F32 `ck`/`cv` cache decode reads (`self.
kvprod_mirror_af_d`) -- see `session_prefill.mojo`'s own module docstring addendum for the full
account. Derives to `DECODE_PATH_LEGACY_NATURAL_KV` (round 5, 2026-08-08): the public `step()`
therefore dispatches `_step_legacy_impl` for it, exactly as for `PF_ATTN_OFF`. Requires BOTH
`attention_forge/` blobs (native-KV-producer, Candidate A) to be linked; degrades to `PF_ATTN_OFF`
otherwise."""

comptime PF_ATTN_GROUPED_FA_NO_MIRROR: Int = 2
"""Structurally identical to `PF_ATTN_GROUPED_FA_WITH_MIRROR` except it never dispatches the
natural-cache mirror -- `ck`/`cv` are left genuinely unwritten by this path. Derives to `DECODE_
PATH_NATIVE_PACKED_KV` (round 5, 2026-08-08): the public `step()` therefore dispatches `_step_
native_kv_impl` for it automatically -- a caller no longer needs to know to call `step_native_kv`
itself (that method remains, test-only, for a caller that wants the implementation directly). Requires
the SAME two `attention_forge/` blobs as
`PF_ATTN_GROUPED_FA_WITH_MIRROR` (identical availability guard); degrades to `PF_ATTN_OFF`
otherwise. `PF_GEMM_BM64` still has no wiring into either `PF_ATTN_OFF`'s or `PF_ATTN_GROUPED_FA_
WITH_MIRROR`'s own descriptor tables, by design (see `session_prefill.mojo`'s `use_qkv_proj_
bm64`-equivalent field docstring history for why: those two tables' own qkv_proj role stays
byte-for-byte its pre-existing self, fully rollback-able) -- BM64 was, and remains, paired only with
this attention path.

Project Redline reopening (2026-08-08), round 7, WIRING GAP CLOSED: this comptime's own docstring
used to also claim this was "the ONLY attention path that ever consults `ResolvedSessionExecutionPlan.
gemm`" for `PF_GEMM_VECLOAD4_ALL_ROLES` too -- that was a real, disclosed gap, not a design choice:
`attention=PF_ATTN_GROUPED_FA_WITH_MIRROR` + `gemm=PF_GEMM_VECLOAD4_ALL_ROLES` resolved to a
genuinely valid, `is_resolved()==True` plan (the two fields resolve independently, with no
cross-field validation rejecting this pairing), yet `_apply_m_rows_af` silently ignored `self.plan.
gemm` and always dispatched the ORIGINAL GEMM kernels -- the combination had simply never been wired
up to have any effect, and had therefore never been measured. Closed additively: `_apply_m_rows_af`
now applies the SAME per-role vecload4 substitution `_apply_m_rows_af_nomirror` already does (see
that method's own docstring in `session_prefill.mojo`) whenever `self.plan.gemm == PF_GEMM_VECLOAD4_
ALL_ROLES` is resolved alongside `PF_ATTN_GROUPED_FA_WITH_MIRROR` -- `PF_ATTN_GROUPED_FA_NO_MIRROR`
is no longer the only attention path that consults `.gemm`; it remains the only one BM64 has any
effect under."""


comptime PF_ATTN_PARAMETRIC_NATIVE_DECODE: Int = 3
"""Llama-family native fast path (feat/llama-native-deep, 2026-08-13): PREFILL attention stays the
runtime-parametric OFF family (`_pf_ropewrt_kernel` + `_pf_attn_tiled_kernel_simd`, validated for
any power-of-two d_head up to RESIDENT_MAX_HEAD_DIM), but the prefill table ALSO dispatches the
attention-forge native-KV-producer per layer, so BOTH persistent KV representations end up
populated: the natural F32 `ck`/`cv` cache (which this plan's own prefill attention reads) AND the
packed F16 native buffers (which every subsequent decode step reads). Derives to
`DECODE_PATH_NATIVE_PACKED_KV` (decode = kvprod-at-m_rows=1 append + split-K flash-decoding
partial + the engine merge -- the SAME `_step_native_kv_impl` `PF_ATTN_GROUPED_FA_NO_MIRROR` uses).

This is the path a power-of-two d_head model the steel prefill pairing does not cover (any d_head
other than 128, or d_head=64 WITH QK-norm -- see `session_prefill.mojo`'s pairing gate: d128 both
families since feat/llama-d128-ropescale, d64 llama-family only since feat/llama-prefill) routes
onto when the native decode kernels are linked: NOTHING about the native DECODE half is structural
-- the kvprod carries the qk_norm flag and the split-K partial has a d_head=64 one-simdgroup twin
(`native_kv_decode_attn_splitk_f2`), so such a model gets the packed-F16-KV + flash-decoding decode
economics without a steel prefill kernel. Requires the native-KV-
producer blob + the naive native decode-attn blob + a split-K partial suited to this d_head (the
f4u2 blob at d_head=128, the f2 blob at d_head=64); degrades to `PF_ATTN_OFF` otherwise. A
request for `PF_ATTN_GROUPED_FA_NO_MIRROR` that cannot resolve (structural gate fails) degrades to
THIS plan when its own availability holds -- closest-capability-first -- before `PF_ATTN_OFF`."""

comptime PF_GEMM_ORIGINAL: Int = 0
"""The pre-existing `_PFROLE_GEMM_ASSIGN_MMA` / `_PFROLE_GEMM_ACCUM_MMA` / `_PFROLE_GEMM_SWIGLU_MMA`
kernel selection for all four GEMM-shaped prefill roles (qkv_proj, o_proj, down_proj, swiglu).
Always resolvable; needs no optional blob."""

comptime PF_GEMM_BM64: Int = 1
"""qkv_proj role ONLY substitutes `_qkv_proj_gemm_mma8x8_bm64` (`BM=64`, ~9-11% isolated/dense-
batched win, `REALRACE_RESULTS.md`'s "F1 sector reframing" entry) in place of the original MMA
kernel; o_proj/down_proj/swiglu are UNCHANGED (`BM=32`) either way. Requires `mma_forge/generated/
mm8_bm64_blob.c` to be linked; degrades to `PF_GEMM_ORIGINAL` otherwise."""

comptime PF_GEMM_VECLOAD4_ALL_ROLES: Int = 2
"""All FOUR GEMM-shaped roles independently substitute their own load-width-vecload4 twin
(`_qkv_proj_gemm_mma8x8_vecload4` / `_gemm_accum_mma8x8_vecload4` x2 / `_swiglu_gemm_mma8x8_
vecload4`) -- `REALRACE_RESULTS.md`'s "the single largest win in the tournament" entry, a real
~25-32% end-to-end throughput improvement, independently reproduced. Each of the three underlying
kernels is discovered independently (`self.qkv_proj_vecload4_pipeline_idx` / `self.gemm_accum_
vecload4_pipeline_idx` / `self.swiglu_vecload4_pipeline_idx`); a binary that links only SOME of the
three blobs still gets vecload4 for whichever roles it linked and the pre-existing kernel for the
rest -- this per-role fallback is finer-grained than this plan's own single `gemm` tier and is left
completely intact in BOTH `_apply_m_rows_af_nomirror` AND (round 7, 2026-08-08 -- see `PF_ATTN_
GROUPED_FA_NO_MIRROR`'s own docstring above for the wiring-gap account this closes) `_apply_m_rows_
af` (this tier only decides WHICH FAMILY to attempt; each role's own availability is still checked
independently, exactly as before, in either table). Degrades this
TIER, as a whole, to `PF_GEMM_BM64` (if that one blob is linked) or `PF_GEMM_ORIGINAL` only when
NONE of the three vecload4 blobs are linked at all -- `PF_GEMM_BM64` itself, unlike vecload4, is
still wired ONLY into `_apply_m_rows_af_nomirror`, not `_apply_m_rows_af`."""

comptime PF_GEMM_MSL_PARITY_ALL_ROLES: Int = 3
"""Phase 3 (hybrid per-role Metal GEMM backend, 2026-08-08, OPT-IN): all FOUR GEMM-shaped roles
independently substitute one of the three hand-written MSL replicas of llama.cpp's
`kernel_mul_mm_f16_f32` (`benchmarks/llm_smoke/metal_llama_parity_replica/msl_parity_{qkv_proj,
gemm_accum,swiglu}_mul_mm.metal` -- byte-for-byte the compute core the Project Redline ledger
measured at 1.01x of the REAL llama.cpp kernel on every role tested), shipped as raw metallibs
inside `mma_forge/generated/msl_parity_blob.c` through the EXISTING blob mechanism (never a new
linking path). qkv_proj uses the ASSIGN twin, o_proj AND down_proj the "+=" ACCUMULATE twin (one
kernel, reused for both exactly as `_gemm_accum_mma8x8`/its vecload4 twin already are), and the
fused gate+up swiglu role the swiglu twin. The three kernels read ALREADY-DEQUANTIZED Float16
weights -- the session materializes them, at upload time, from the EXACT SAME Int8 bytes + per-row
Float32 scale its Int8 twins read (`self.msl_w_*_f16_*` buffers, allocated only when at least one
MSL pipeline was discovered) -- so this arm computes the SAME math as the Int8/vecload4 arms (same
quantized weights, F32 accumulate) and must emit the same greedy tokens. Wired into BOTH `_apply_m_
rows_af` and `_apply_m_rows_af_nomirror` (same both-tables discipline vecload4's own round-7 wiring
gap established -- requesting this tier with `attention=PF_ATTN_OFF` has no GEMM effect, exactly as
`PF_GEMM_VECLOAD4_ALL_ROLES` under OFF has none; the OFF table is deliberately untouched). Per-role
fallback within the tier: a role whose MSL pipeline was NOT discovered runs the vecload4 twin for
that role if IT was linked, otherwise the original MMA kernel -- the tier only decides WHICH FAMILY
to attempt first; each role's own availability is still checked independently. Degrades this TIER,
as a whole, to `PF_GEMM_VECLOAD4_ALL_ROLES` (if any vecload4 blob is linked -- the round-4/5 lesson:
a blobs-absent binary must degrade to the standing default, never hard-error), else `PF_GEMM_BM64`,
else `PF_GEMM_ORIGINAL`, when NONE of the three MSL metallibs are linked at all."""


comptime PF_UNRESOLVED: Int = -1
"""Never a value `resolve_prefill_execution_plan`/`UnresolvedPrefillConfig.resolve` returns for
EITHER `ResolvedSessionExecutionPlan.attention` or `.gemm` -- every branch of both fields' own resolution
logic terminates in one of the three named `PF_ATTN_*`/`PF_GEMM_*` constants above, never here. This
codebase's own established `-1`-means-absent convention (`_MBQwen3I8AllSimd7Prefill.af_pipeline_idx`/
`.qkv_proj_bm64_pipeline_idx`/etc. all use it for "not discovered in this binary") reused for "not
yet resolved" -- see `ResolvedSessionExecutionPlan.is_resolved()` and this file's own module docstring
addendum ("make unresolved plan state unrepresentable") for exactly what this sentinel exists to let
`prefill_batch`/`_apply_m_rows_af_nomirror` defensively reject. Reused again, unchanged, as the
never-produced sentinel for `ResolvedSessionExecutionPlan.kv_contract`/`.decode` below -- round 5's
own "make unresolved plan state unrepresentable" extension to the two new fields."""


comptime KV_CONTRACT_NATURAL_F32: Int = 0
"""The persistent KV-cache buffers a `prefill_batch()` call under `PF_ATTN_OFF` leaves populated:
ONLY the natural F32 `ck`/`cv` cache every layer's `step()` decode call reads -- the packed F16
native buffers are simply never touched. The ONLY `kv_contract` value `_derive_kv_contract_for_
attention` ever returns for `attention == PF_ATTN_OFF`."""

comptime KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16: Int = 1
"""Both representations are populated: the packed F16 native buffers (written by the native-KV-
producer every plan resolving to `PF_ATTN_GROUPED_FA_WITH_MIRROR` dispatches) AND the natural F32
`ck`/`cv` cache (written by the SAME table's own additive mirror dispatch, `self.kvprod_mirror_af_d`
-- see that field's own docstring in `session_prefill.mojo`). The ONLY `kv_contract` value
`_derive_kv_contract_for_attention` ever returns for `attention == PF_ATTN_GROUPED_FA_WITH_MIRROR`."""

comptime KV_CONTRACT_PACKED_F16_NATIVE: Int = 2
"""ONLY the packed F16 native buffers are populated -- `PF_ATTN_GROUPED_FA_NO_MIRROR` never
dispatches the mirror, so the natural F32 `ck`/`cv` cache is left genuinely unwritten (not merely
stale). The ONLY `kv_contract` value `_derive_kv_contract_for_attention` ever returns for
`attention == PF_ATTN_GROUPED_FA_NO_MIRROR` -- see that comptime's own docstring above for the full
account of what reading `ck`/`cv` under this contract would produce (garbage, not a caught error) --
exactly why `DECODE_PATH_NATIVE_PACKED_KV` below is the ONLY decode path this contract may ever pair
with."""


comptime KV_CONTRACT_MIRRORED_NATIVE_DECODE: Int = 3
"""Both representations are populated -- the natural F32 `ck`/`cv` cache (written by the plan's own
`_pf_ropewrt_kernel` dispatch, read by the plan's own parametric prefill attention) AND the packed
F16 native buffers (written by the same table's native-KV-producer dispatch, read by every
subsequent native decode step) -- but unlike `KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16`
(the with-mirror grouped-FA plan's contract, which decodes LEGACY), decode here reads the NATIVE
side. The ONLY `kv_contract` value `_derive_kv_contract_for_attention` ever returns for
`attention == PF_ATTN_PARAMETRIC_NATIVE_DECODE`; paired with `DECODE_PATH_NATIVE_PACKED_KV` by the
same derivation, so the prefill-time double-write and the decode-time read can never disagree."""

comptime DECODE_PATH_LEGACY_NATURAL_KV: Int = 0
"""`step()` must route to `_step_legacy_impl` -- reads the natural F32 `ck`/`cv` cache, byte-
identical to `_MBQwen3I8AllSimd7.step`. Correct for, and the ONLY value `_derive_decode_path_for_
attention` ever returns for, `KV_CONTRACT_NATURAL_F32` and `KV_CONTRACT_MIRRORED_NATURAL_F32_AND_
PACKED_F16` (both leave `ck`/`cv` genuinely populated -- see each contract's own docstring)."""

comptime DECODE_PATH_NATIVE_PACKED_KV: Int = 1
"""`step()` must route to `_step_native_kv_impl` -- reads the packed F16 native buffers via
`attention_forge.native_kv_decode_attn`, exactly what `step_native_kv` (now a thin, test-only public
wrapper around the same implementation -- see `session_prefill.mojo`'s own module docstring
addendum) has always dispatched. The ONLY value `_derive_decode_path_for_attention` ever returns for
`KV_CONTRACT_PACKED_F16_NATIVE` -- this is the pairing round 5 exists to make structurally
unrepresentable to get wrong: nothing outside `_derive_kv_contract_for_attention`/`_derive_decode_
path_for_attention` themselves ever decides this value, so `DECODE_PATH_LEGACY_NATURAL_KV` can never
reach a session whose cache actually holds `KV_CONTRACT_PACKED_F16_NATIVE`, or vice versa."""


def _derive_kv_contract_for_attention(attention: Int) -> Int:
    """The ONE place `ResolvedSessionExecutionPlan.kv_contract` is EVER derived from `.attention` --
    called from BOTH `resolve_prefill_execution_plan` (the only place that WRITES this field) and
    `ResolvedSessionExecutionPlan.is_resolved()` (which re-derives and compares, catching a direct-
    field-mutation bypass the exact same way `PF_UNRESOLVED` already catches an unresolved
    `attention`/`gemm` -- see this file's own module docstring addendum, round 5, for the full
    "why a pure function of `attention` alone" account). Exhaustive by construction: every branch
    returns one of the three named `KV_CONTRACT_*` constants above, so this never returns
    `PF_UNRESOLVED` for any `attention` value this file's own `PF_ATTN_*` constants name -- an
    out-of-range `attention` (e.g. `PF_UNRESOLVED` itself, reachable only via direct field mutation)
    falls through the `else` to `KV_CONTRACT_NATURAL_F32`, which is intentionally NOT what
    `is_resolved()`'s own `attn_ok` check will already have rejected such a value for anyway -- see
    that method's own docstring."""
    if attention == PF_ATTN_GROUPED_FA_NO_MIRROR:
        return KV_CONTRACT_PACKED_F16_NATIVE
    elif attention == PF_ATTN_GROUPED_FA_WITH_MIRROR:
        return KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16
    elif attention == PF_ATTN_PARAMETRIC_NATIVE_DECODE:
        # feat/llama-native-deep (2026-08-13): both representations populated (the parametric
        # prefill attention reads the natural side; native decode reads the packed side).
        return KV_CONTRACT_MIRRORED_NATIVE_DECODE
    else:
        return KV_CONTRACT_NATURAL_F32


def _derive_decode_path_for_attention(attention: Int) -> Int:
    """The ONE place `ResolvedSessionExecutionPlan.decode` is EVER derived from `.attention` -- see
    `_derive_kv_contract_for_attention`'s own docstring immediately above for the full account
    (identical reasoning, restated for the decode-routing field instead of the cache-representation
    field; the two are always derived from the same `attention` value, by design, so they can never
    disagree with EACH OTHER either)."""
    if attention == PF_ATTN_GROUPED_FA_NO_MIRROR:
        return DECODE_PATH_NATIVE_PACKED_KV
    elif attention == PF_ATTN_PARAMETRIC_NATIVE_DECODE:
        # feat/llama-native-deep (2026-08-13): the parametric-prefill plan's own prefill table
        # populates the packed F16 native buffers (alongside the natural cache), so decode reads
        # the native side exactly as the no-mirror grouped-FA plan does.
        return DECODE_PATH_NATIVE_PACKED_KV
    else:
        return DECODE_PATH_LEGACY_NATURAL_KV


@fieldwise_init
struct UnresolvedPrefillConfig(Copyable, Movable):
    """What a caller REQUESTS -- a DIFFERENT Mojo type than `ResolvedSessionExecutionPlan` below, on purpose
    (Project Redline reopening, 2026-08-08, "make unresolved plan state unrepresentable" -- see this
    file's own module docstring addendum for the full account of the gap this closes). Before this
    split, a caller's raw, un-validated request and the validated value a dispatch decision actually
    reads were the SAME type (`ResolvedSessionExecutionPlan` served both roles), which is exactly what let an
    un-resolved value be indistinguishable, at the type level, from an already-resolved one.

    A caller builds one of these (or relies on `_MBQwen3I8AllSimd7Prefill.__init__`'s own default,
    `UnresolvedPrefillConfig(PF_ATTN_OFF, PF_GEMM_ORIGINAL)` -- byte-for-byte the same all-off default
    this constructor parameter has always had), then calls `.resolve(available_pipelines)` to obtain
    a genuine `ResolvedSessionExecutionPlan`. There is no other public way to produce one that this file's
    own dispatch code treats as valid -- see `ResolvedSessionExecutionPlan.is_resolved()`."""

    var attention_requested: Int
    """One of `PF_ATTN_OFF` / `PF_ATTN_GROUPED_FA_WITH_MIRROR` / `PF_ATTN_GROUPED_FA_NO_MIRROR` --
    the caller's own ask, BEFORE this session's own real pipeline availability is consulted."""
    var gemm_requested: Int
    """One of `PF_GEMM_ORIGINAL` / `PF_GEMM_BM64` / `PF_GEMM_VECLOAD4_ALL_ROLES` /
    `PF_GEMM_MSL_PARITY_ALL_ROLES` -- same caveat."""

    def resolve(self, available: PrefillPipelineAvailability) -> ResolvedSessionExecutionPlan:
        """The one public method a caller needing a `ResolvedSessionExecutionPlan` from a request should
        reach for -- a thin wrapper around this file's own `resolve_prefill_execution_plan` free
        function (kept, unchanged in behavior, for `_MBQwen3I8AllSimd7Prefill.__init__`/`.resolve_
        plan`'s own pre-existing direct references to it). See that function's own docstring for the
        exact graceful-degrade rule this delegates to."""
        return resolve_prefill_execution_plan(
            self,
            available.af_grouped_fa,
            available.bm64,
            available.vecload4_qkv,
            available.vecload4_accum,
            available.vecload4_swiglu,
            available.msl_parity_qkv,
            available.msl_parity_accum,
            available.msl_parity_swiglu,
            available.parametric_native_decode,
        )


@fieldwise_init
struct PrefillPipelineAvailability(Copyable, Movable):
    """Bundles the five independent `Bool` pipeline-availability facts `resolve_prefill_execution_
    plan` needs into one named value -- replaces five positional `Bool` parameters at the one call
    site that matters (`UnresolvedPrefillConfig.resolve`), matching this task's own "resolve(available_
    pipelines)" naming. Every field is a raw discovery fact about ONE real, already-constructed
    binary (`_MBQwen3I8AllSimd7Prefill`'s own `af_pipeline_idx`/`qkv_proj_bm64_pipeline_idx`/etc.),
    never a request -- see `resolve_prefill_execution_plan`'s own docstring for how each is used."""

    var af_grouped_fa: Bool
    """Gates BOTH `PF_ATTN_GROUPED_FA_WITH_MIRROR` and `PF_ATTN_GROUPED_FA_NO_MIRROR` -- see
    `PF_ATTN_GROUPED_FA_NO_MIRROR`'s own docstring for why one `Bool` covers both."""
    var bm64: Bool
    var vecload4_qkv: Bool
    var vecload4_accum: Bool
    var vecload4_swiglu: Bool
    var msl_parity_qkv: Bool
    """Phase 3 (2026-08-08): discovery fact for the OPTIONAL MSL-parity qkv_proj kernel
    (`msl_parity__qkv_proj_mul_mm_f16_f32`, one of the three metallibs inside `mma_forge/generated/
    msl_parity_blob.c`) -- same raw-discovery-fact convention as the vecload4 trio above, never a
    request. All three default `False` for a binary that never links that blob, and
    `resolve_prefill_execution_plan`'s own graceful degrade then makes a `PF_GEMM_MSL_PARITY_ALL_
    ROLES` request resolve to `PF_GEMM_VECLOAD4_ALL_ROLES` (or lower) -- never a hard error."""
    var msl_parity_accum: Bool
    var msl_parity_swiglu: Bool
    var parametric_native_decode: Bool
    """feat/llama-native-deep (2026-08-13): discovery fact for the llama-family native fast path
    (`PF_ATTN_PARAMETRIC_NATIVE_DECODE`) -- True iff the native-KV-producer blob, the naive native
    decode-attn blob, and a split-K partial suited to THIS session's own d_head are all linked
    (computed by `_MBQwen3I8AllSimd7Prefill` from its own discovery slots, never a request).
    Construction is positional (this pinned toolchain's `@fieldwise_init` takes no field
    defaults); both `_MBQwen3I8AllSimd7Prefill` resolution sites bind it explicitly, and
    `resolve_prefill_execution_plan`'s own matching trailing PARAMETER still defaults False for
    every direct caller that never knew this field existed (the policy suite's pre-existing
    calls)."""


@fieldwise_init
struct ResolvedSessionExecutionPlan(Copyable, Movable):
    """A fully-resolved SESSION execution plan -- exactly one attention-path choice, exactly one
    GEMM-tier choice, PLUS (round 5, 2026-08-08) exactly one KV-cache-contract fact and exactly one
    decode-routing fact, both DERIVED from the attention choice, never independently settable.
    Renamed from `PrefillExecutionPlan`: this struct's own scope stopped describing itself accurately
    once it became clear (round 4's own adversarial finding, restated in full in this file's own
    module docstring addendum) that `attention` does not merely pick a PREFILL dispatch table -- it
    also determines which persistent KV-cache representation every DECODE call on this SAME session
    instance must read for the rest of that instance's lifetime. `kv_contract`/`decode` make that
    whole-session obligation a checkable field instead of only a fact stated in `PF_ATTN_GROUPED_FA_
    NO_MIRROR`'s own docstring prose.

    In ordinary, non-adversarial use, ALWAYS produced by `UnresolvedPrefillConfig.resolve(...)`
    (equivalently, `resolve_prefill_execution_plan`) -- see `is_resolved()` below and this file's own
    module docstring addendum for the defense-in-depth that method exists to support, and for why
    this is a DIFFERENT type than `UnresolvedPrefillConfig` above (a caller requests `attention`/
    `gemm` ONLY -- there is no `kv_contract_requested`/`decode_requested` field anywhere, by design:
    these two are never a request, only a consequence)."""

    var attention: Int
    """One of `PF_ATTN_OFF` / `PF_ATTN_GROUPED_FA_WITH_MIRROR` / `PF_ATTN_GROUPED_FA_NO_MIRROR` in
    any value produced by `UnresolvedPrefillConfig.resolve`; `PF_UNRESOLVED` is possible ONLY via a
    direct field assignment that bypasses resolution entirely -- see `is_resolved()`. The ONE field
    `kv_contract`/`decode` are ever derived from -- see `_derive_kv_contract_for_attention`/`_derive_
    decode_path_for_attention`."""
    var gemm: Int
    """One of `PF_GEMM_ORIGINAL` / `PF_GEMM_BM64` / `PF_GEMM_VECLOAD4_ALL_ROLES` /
    `PF_GEMM_MSL_PARITY_ALL_ROLES` in any value produced by `UnresolvedPrefillConfig.resolve`.
    Consulted by `_apply_m_rows_af_nomirror`, by `_apply_m_rows_af` (round 7 wired vecload4 in;
    Phase 3 wires the MSL-parity tier into BOTH -- see each comptime's own docstring), never by the
    OFF-path `_apply_m_rows`."""
    var kv_contract: Int
    """Round 5 (2026-08-08): one of `KV_CONTRACT_NATURAL_F32` / `KV_CONTRACT_MIRRORED_NATURAL_F32_
    AND_PACKED_F16` / `KV_CONTRACT_PACKED_F16_NATIVE` -- ALWAYS `_derive_kv_contract_for_attention(
    self.attention)`, in every value `resolve_prefill_execution_plan` ever returns; never a caller-
    supplied request (see this file's own module docstring addendum, round 5, for why that is exactly
    what makes an `attention`/`kv_contract` mismatch structurally unrepresentable, not merely absent
    from today's call sites). Names which persistent KV-cache buffers a `prefill_batch()` call under
    this plan leaves populated for every subsequent call on this SAME session instance."""
    var decode: Int
    """Round 5 (2026-08-08): one of `DECODE_PATH_LEGACY_NATURAL_KV` / `DECODE_PATH_NATIVE_PACKED_KV`
    -- ALWAYS `_derive_decode_path_for_attention(self.attention)`, same non-caller-supplied guarantee
    as `kv_contract` above (both derived from the identical `attention` value, so they can never
    disagree with each other either). `session_prefill.mojo`'s own public `step()` reads THIS field
    to route to `_step_legacy_impl`/`_step_native_kv_impl` -- see that method's own docstring."""

    def is_resolved(self) -> Bool:
        """`True` iff `attention`/`gemm` each hold one of their own three named `PF_ATTN_*`/
        `PF_GEMM_*` constants AND `kv_contract`/`decode` each equal exactly what `_derive_kv_
        contract_for_attention`/`_derive_decode_path_for_attention` would derive from `self.
        attention` right now -- `False` for `PF_UNRESOLVED`, for any other out-of-range `Int` a
        direct field assignment could otherwise smuggle into any of the four fields, AND (round 5)
        for a `kv_contract`/`decode` that disagrees with `self.attention` even if every field
        individually looks like a valid named constant -- e.g. a direct `session.plan.decode =
        DECODE_PATH_LEGACY_NATURAL_KV` on an otherwise-genuinely-resolved `PF_ATTN_GROUPED_FA_NO_
        MIRROR` plan is caught HERE, not silently accepted just because `DECODE_PATH_LEGACY_NATURAL_
        KV` is individually a real, named value. `resolve_prefill_execution_plan`'s own exhaustive
        `if`/`elif`/`else` branches, calling the same two derivation functions this check calls, make
        this `True` for EVERY value that function (equivalently, `UnresolvedPrefillConfig.resolve`)
        can ever return -- so, in ordinary use, this check is expected to never actually fail;
        `_MBQwen3I8AllSimd7Prefill.prefill_batch`/`_apply_m_rows_af_nomirror`/`step()` all call it
        before reading `self.plan` for a real dispatch decision anyway, as defense-in-depth against
        the one way it COULD fail (a direct `session.plan = ...` or `session.plan.<field> = ...`
        assignment bypassing resolution -- see `PF_UNRESOLVED`'s own docstring). See their own
        docstrings."""
        var attn_ok = (
            self.attention == PF_ATTN_OFF
            or self.attention == PF_ATTN_GROUPED_FA_WITH_MIRROR
            or self.attention == PF_ATTN_GROUPED_FA_NO_MIRROR
            # feat/llama-native-deep (2026-08-13): the fourth attention path joins the closed set
            # -- same single-producer invariant as the other three (`resolve_prefill_execution_
            # plan`'s own exhaustive branches are the only producer).
            or self.attention == PF_ATTN_PARAMETRIC_NATIVE_DECODE
        )
        var gemm_ok = (
            self.gemm == PF_GEMM_ORIGINAL
            or self.gemm == PF_GEMM_BM64
            or self.gemm == PF_GEMM_VECLOAD4_ALL_ROLES
            # Phase 3 (2026-08-08): the fourth, opt-in MSL-parity tier joins the closed set --
            # `resolve_prefill_execution_plan`'s own exhaustive branches are the only producer, same
            # invariant as the other three.
            or self.gemm == PF_GEMM_MSL_PARITY_ALL_ROLES
        )
        var kv_contract_ok = self.kv_contract == _derive_kv_contract_for_attention(self.attention)
        var decode_ok = self.decode == _derive_decode_path_for_attention(self.attention)
        return attn_ok and gemm_ok and kv_contract_ok and decode_ok


def pf_attn_path_name(path: Int) -> String:
    """Human-readable name for a `ResolvedSessionExecutionPlan.attention` value -- used only in test/telemetry
    output, never in a dispatch decision."""
    if path == PF_ATTN_OFF:
        return "off"
    if path == PF_ATTN_GROUPED_FA_WITH_MIRROR:
        return "grouped_fa_with_mirror"
    if path == PF_ATTN_GROUPED_FA_NO_MIRROR:
        return "grouped_fa_no_mirror"
    if path == PF_ATTN_PARAMETRIC_NATIVE_DECODE:
        return "parametric_native_decode"
    return "unknown(" + String(path) + ")"


def pf_gemm_path_name(path: Int) -> String:
    """Human-readable name for a `ResolvedSessionExecutionPlan.gemm` value -- used only in test/telemetry
    output, never in a dispatch decision."""
    if path == PF_GEMM_ORIGINAL:
        return "original"
    if path == PF_GEMM_BM64:
        return "bm64"
    if path == PF_GEMM_VECLOAD4_ALL_ROLES:
        return "vecload4_all_roles"
    if path == PF_GEMM_MSL_PARITY_ALL_ROLES:
        return "msl_parity_all_roles"
    return "unknown(" + String(path) + ")"


def kv_contract_name(contract: Int) -> String:
    """Human-readable name for a `ResolvedSessionExecutionPlan.kv_contract` value -- round 5
    (2026-08-08), same test/telemetry-only convention as `pf_attn_path_name`/`pf_gemm_path_name`
    above, never consulted in a dispatch decision."""
    if contract == KV_CONTRACT_NATURAL_F32:
        return "natural_f32"
    if contract == KV_CONTRACT_MIRRORED_NATURAL_F32_AND_PACKED_F16:
        return "mirrored_natural_f32_and_packed_f16"
    if contract == KV_CONTRACT_PACKED_F16_NATIVE:
        return "packed_f16_native"
    if contract == KV_CONTRACT_MIRRORED_NATIVE_DECODE:
        return "mirrored_native_decode"
    return "unknown(" + String(contract) + ")"


def decode_path_name(path: Int) -> String:
    """Human-readable name for a `ResolvedSessionExecutionPlan.decode` value -- round 5 (2026-08-08),
    same test/telemetry-only convention as `pf_attn_path_name`/`pf_gemm_path_name` above, never
    consulted in a dispatch decision."""
    if path == DECODE_PATH_LEGACY_NATURAL_KV:
        return "legacy_natural_kv"
    if path == DECODE_PATH_NATIVE_PACKED_KV:
        return "native_packed_kv"
    return "unknown(" + String(path) + ")"


def resolve_prefill_execution_plan(
    requested: UnresolvedPrefillConfig,
    af_grouped_fa_available: Bool,
    bm64_available: Bool,
    vecload4_qkv_available: Bool,
    vecload4_accum_available: Bool,
    vecload4_swiglu_available: Bool,
    msl_parity_qkv_available: Bool = False,
    msl_parity_accum_available: Bool = False,
    msl_parity_swiglu_available: Bool = False,
    parametric_native_decode_available: Bool = False,
) -> ResolvedSessionExecutionPlan:
    """The one place this whole plan's own graceful-degrade rule is implemented. Called from BOTH
    `_MBQwen3I8AllSimd7Prefill.__init__` (using the constructor's own `requested_plan` parameter,
    right after pipeline discovery) and its public `resolve_plan` method (for a caller that wants to
    change the request after construction, mirroring this struct's own pre-existing "construct, then
    configure, then use" idiom for every other lever in this file) -- a pure function, not a method,
    specifically so `__init__` never needs to call a `mut self` method on a `self` that has not
    finished initializing every field yet. `UnresolvedPrefillConfig.resolve` (its own method, added
    by the "make unresolved plan state unrepresentable" redesign) is a thin wrapper around this exact
    function -- both exist so neither `__init__`/`resolve_plan`'s own pre-existing direct references
    to this free function, nor a new caller preferring method syntax, need to change.

    `af_grouped_fa_available` gates BOTH `PF_ATTN_GROUPED_FA_WITH_MIRROR` and `PF_ATTN_GROUPED_FA_
    NO_MIRROR` -- by construction, not by coincidence: both need the identical two `attention_forge/`
    kernels (`self.af_pipeline_idx[_AFROLE_NATIVE_KV_PRODUCER] >= 0 and self.af_pipeline_idx[_
    AFROLE_GROUPED_FA_ATTN] >= 0`), so there is no scenario where one is available and the other is
    not -- see `PF_ATTN_GROUPED_FA_NO_MIRROR`'s own docstring.

    EXPLICIT REQUEST BEATS DEFAULT, UNCONDITIONALLY -- restated precisely: this function has exactly
    ONE `requested.attention_requested` value to resolve (never two independent flags that might
    disagree), so there is no "other path's own default" left anywhere in this call for the
    requested path to lose precedence to. If the requested path's own blobs are linked, it is always
    what gets returned; the only way this function ever returns something OTHER than the caller's
    own literal request is the graceful degrade documented on each `PF_ATTN_*`/`PF_GEMM_*` constant
    above, triggered SOLELY by that path's own missing blob(s) -- never by a different path's own
    hardcoded default.

    EXHAUSTIVE BY CONSTRUCTION, restated for `is_resolved()`'s own benefit: every branch below
    assigns `resolved_attn`/`resolved_gemm` from the closed, three-member `PF_ATTN_*`/`PF_GEMM_*` sets
    -- there is no path through this function's own `if`/`elif`/`else` ladders that leaves either
    variable at `PF_UNRESOLVED` or any other value, so the `ResolvedSessionExecutionPlan` this returns always
    satisfies `.is_resolved() == True`.

    ROUND 5 (2026-08-08): `resolved_kv_contract`/`resolved_decode` are NOT resolved independently --
    both are `_derive_kv_contract_for_attention(resolved_attn)`/`_derive_decode_path_for_attention(
    resolved_attn)`, called AFTER `resolved_attn` is already final (including its own graceful-
    degrade above), so a request that degrades from `PF_ATTN_GROUPED_FA_NO_MIRROR` down to `PF_ATTN_
    OFF` (missing blobs) correctly gets `KV_CONTRACT_NATURAL_F32`/`DECODE_PATH_LEGACY_NATURAL_KV` --
    the contract that matches what THIS resolved plan will actually dispatch, never the contract the
    caller's original, un-degraded request would have implied. This is the one and only place either
    derivation function is called from the WRITE side; see `ResolvedSessionExecutionPlan.is_
    resolved()` for the CHECK side that re-derives the identical values from a live `self.attention`."""
    var resolved_attn: Int
    if requested.attention_requested == PF_ATTN_GROUPED_FA_NO_MIRROR:
        # feat/llama-native-deep (2026-08-13): CLOSEST-CAPABILITY-FIRST degrade. The no-mirror
        # request's own intent is "fastest native-KV decode path"; when the steel prefill pairing
        # cannot resolve (a d_head the steel kernels do not cover -- any power-of-two other than
        # 128/64, or d_head=64 with QK-norm), the parametric-prefill + native-decode plan carries
        # that same decode half, so it outranks the plain OFF fallback. A binary linking none of
        # the native blobs still degrades all the way to PF_ATTN_OFF, byte-for-byte as before this
        # plan existed.
        if af_grouped_fa_available:
            resolved_attn = PF_ATTN_GROUPED_FA_NO_MIRROR
        elif parametric_native_decode_available:
            resolved_attn = PF_ATTN_PARAMETRIC_NATIVE_DECODE
        else:
            resolved_attn = PF_ATTN_OFF
    elif requested.attention_requested == PF_ATTN_GROUPED_FA_WITH_MIRROR:
        resolved_attn = PF_ATTN_GROUPED_FA_WITH_MIRROR if af_grouped_fa_available else PF_ATTN_OFF
    elif requested.attention_requested == PF_ATTN_PARAMETRIC_NATIVE_DECODE:
        resolved_attn = (
            PF_ATTN_PARAMETRIC_NATIVE_DECODE if parametric_native_decode_available else PF_ATTN_OFF
        )
    else:
        resolved_attn = PF_ATTN_OFF

    var resolved_gemm: Int
    # Phase 3 (2026-08-08): the opt-in MSL-parity tier. GRACEFUL FALLBACK, the round-4/5 lesson
    # restated for this tier: a binary that never links `mma_forge/generated/msl_parity_blob.c`
    # degrades a `PF_GEMM_MSL_PARITY_ALL_ROLES` request to the CURRENT production default tier
    # (`PF_GEMM_VECLOAD4_ALL_ROLES`, when any vecload4 blob is linked), then down the SAME chain
    # that tier already uses -- never a hard error. Proven by an actual blobs-absent build+run, not
    # assumed -- see REALRACE_RESULTS.md's Phase 3 entry.
    if requested.gemm_requested == PF_GEMM_MSL_PARITY_ALL_ROLES:
        if msl_parity_qkv_available or msl_parity_accum_available or msl_parity_swiglu_available:
            resolved_gemm = PF_GEMM_MSL_PARITY_ALL_ROLES
        elif vecload4_qkv_available or vecload4_accum_available or vecload4_swiglu_available:
            resolved_gemm = PF_GEMM_VECLOAD4_ALL_ROLES
        elif bm64_available:
            resolved_gemm = PF_GEMM_BM64
        else:
            resolved_gemm = PF_GEMM_ORIGINAL
    elif requested.gemm_requested == PF_GEMM_VECLOAD4_ALL_ROLES:
        if vecload4_qkv_available or vecload4_accum_available or vecload4_swiglu_available:
            resolved_gemm = PF_GEMM_VECLOAD4_ALL_ROLES
        elif bm64_available:
            resolved_gemm = PF_GEMM_BM64
        else:
            resolved_gemm = PF_GEMM_ORIGINAL
    elif requested.gemm_requested == PF_GEMM_BM64:
        resolved_gemm = PF_GEMM_BM64 if bm64_available else PF_GEMM_ORIGINAL
    else:
        resolved_gemm = PF_GEMM_ORIGINAL

    var resolved_kv_contract = _derive_kv_contract_for_attention(resolved_attn)
    var resolved_decode = _derive_decode_path_for_attention(resolved_attn)

    return ResolvedSessionExecutionPlan(resolved_attn, resolved_gemm, resolved_kv_contract, resolved_decode)
