"""
residentk.contract — the one status vocabulary, shape check and dispatch budget for `residentk`.
Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_residentk_session.mojo
benchmark: benchmarks/llm_smoke/qwen3_generate_metal.mojo
docs: none
version_introduced: 0.7.0
deprecation_state: active
@endcapability

This module imports no `std.gpu` and launches nothing
--------------------------------------------------------
It is an ordinary contract module in the sense `accel.contract` is: a caller on any host — Linux CI
with no shader compiler and no accelerator included — can ask "what does this status code mean",
"is this model shape one the resident session can hold", "how many GPU dispatches would one token
cost" and get an honest answer with no device involved. Everything that touches a device lives in
`residentk.session` and `residentk.kernels`, both of which are private and neither of which is a
contract module.

Status range
------------
`residentk` owns **600-619**. Free at the time this was written: `tensorx` holds 300-319, `gemm`
320-339, `accel`/`causal_inference` 340-359, `attnk`/`evaluation` 360-379, `normk` 380-389, `mlpk`
390-399, `discrete_event`/`data_quality` 400-449, `strategy` 450-489, `llmk` 560-579, `lossk`
580-599, `progexec` 1400-1419 (rule 4e — ranges are per PACKAGE, and the block is recorded here so
the next package can see what is taken).

Why a DISPATCH BUDGET is a contract function and not a comment
-----------------------------------------------------------------
`ctx.enqueue_function` blocks until the kernel completes on this backend (measured: a 20 ms kernel
returns from the "enqueue" in 20.392 ms, and the following `synchronize()` costs 35 us). So a
token's wall time is the SUM over dispatches of submission-plus-kernel, with no overlap, and at
~180 us of host time per dispatch the COUNT is the dominant term for a 0.6B model — 2.38 GB of
Float32 weights is only ~5.8 ms of unavoidable reads at this host's measured 411 GB/s streaming
ceiling.

A design that drifts from 6 dispatches per layer to 10 loses a third of its throughput without any
kernel getting slower, and nothing in a docstring would catch that. `residentk_dispatch_budget` is
the arithmetic the session actually implements, exported so a test asserts it.

Public API:
  residentk_status_name(code)                                    — the status vocabulary
  residentk_dims_check(d_model, h_q, h_kv, d_head, d_ff)         — is this a shape the session holds
  residentk_context_check(pos, n_new, max_ctx)                   — does the whole run fit the cache,
                                                                    and is max_ctx itself sane
  residentk_dispatch_budget(n_layers)                            — GPU dispatches for ONE token
  residentk_dispatch_budget_deep(n_layers)                       — GPU dispatches for ONE token
                                                                    on the split-K deep path
  residentk_cache_elements(n_layers, h_kv, d_head, max_ctx)      — KV-cache Float32 count at max_ctx
  residentk_weight_elems(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab, max_ctx=512)
                                                                  — resident Float32 count
  residentk_splitk_should_split(n_keys)                          — is this depth worth splitting at all
  residentk_splitk_policy(n_keys, n_cores, h_q)                  — the split count to use AT this depth
  residentk_splitk_max_n_splits(n_cores, h_q)                    — the ceiling to size scratch buffers for

Why the split-K depth policy lives HERE and not in `metaldispatch.session`
-----------------------------------------------------------------------------
Every OTHER host-side, no-device-needed decision this design makes (is this shape supported, does
this run fit the cache, how many dispatches does a token cost) already lives in this file, checked by
`test_residentk_contract.mojo` with no GPU. `residentk_splitk_policy` is exactly that kind of
decision — pure arithmetic over `n_keys`/`n_cores`/`h_q`, no buffer, no kernel, no device — so it
belongs beside `residentk_dispatch_budget`, not inside `metaldispatch.session._MBQwen3I8AllSimd7`
where it would be untestable without a Metal device.
"""

from std.math import log
from tensorx.contract import tx_finite

# ── status codes: residentk owns 600-619 ──────────────────────────────────────

comptime RESIDENT_OK: Int = 600
"""The session is holding the shape it was asked to hold, or the step ran."""

comptime RESIDENT_ERR_EMPTY_DIM: Int = 601
"""A declared dimension was < 1."""

comptime RESIDENT_ERR_DIM_TOO_LARGE: Int = 602
"""A declared dimension exceeds this package's own ceiling — see the constants below."""

comptime RESIDENT_ERR_HEAD_MISMATCH: Int = 603
"""`h_q % h_kv != 0`, so grouped-query attention has no integer group size, or the head dimension
is not a power of two (the threadgroup tree reduction inside the RoPE and SDPA kernels halves a
uniform stride, and an odd width would drop lanes silently rather than loudly)."""

comptime RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT: Int = 604
"""The binary was built without `-D ALGENTA_GPU`, so no kernel was compiled into it. A build
decision, distinct from 605 which is a deployment one."""

comptime RESIDENT_ERR_NO_DEVICE: Int = 605
"""Built with GPU kernels, but this host has no accelerator."""

comptime RESIDENT_ERR_CONTEXT_FULL: Int = 606
"""The requested run would need more KV-cache positions than the session's OWN `max_ctx` — the
runtime capacity that particular session was opened with, not the `RESIDENT_MAX_CONTEXT` safety
ceiling (a request past THAT ceiling is `RESIDENT_ERR_DIM_TOO_LARGE` instead, refused before the
question of whether a run fits is even asked). The cache is allocated once and written IN PLACE, so
its capacity is fixed at session open — refusing here is what stops a step from writing past the
last slot, which on a GPU is silent corruption."""

comptime RESIDENT_ERR_UPLOAD_LENGTH: Int = 607
"""A weight handed to the session is not the element count its declared shape implies."""

comptime RESIDENT_ERR_LAUNCH_FAILED: Int = 608
"""A device call raised. Reported as a status rather than propagated, matching `accel`'s own
convention that a capability answer must not throw."""

comptime RESIDENT_ERR_NON_FINITE_SCALAR: Int = 609
"""`eps` or the attention scale was NaN or infinite."""

comptime RESIDENT_ERR_CODE_OUT_OF_RANGE: Int = 610
"""Not one of the codes above. Returned by `residentk_status_name` for an unrecognized code."""

# ── ceilings ──────────────────────────────────────────────────────────────────

comptime RESIDENT_MAX_D_MODEL: Int = 3072
"""Largest vector width the fused kernels stage in threadgroup memory.

Not an arbitrary round number: the fused `rmsnorm + projection` kernels copy the normalized input
into a shared-memory array so the 8 output columns a threadgroup owns each read it from there
instead of from device memory 8 times over. That array is sized at COMPILE time, so this constant
is literally the shared allocation, and 3072 Float32 is 12 KiB against Apple silicon's 32 KiB
threadgroup budget — leaving room for the 1 KiB reduction scratch alongside it. `d_ff` is staged by
the down-projection, so this bounds `d_ff` too, not only `d_model`."""

comptime RESIDENT_MAX_HEAD_DIM: Int = 256
"""Largest attention head dimension. The RoPE and SDPA kernels run ONE threadgroup per head with one
thread per head element, so this is a threadgroup size — 256 is the portable ceiling and also the
largest tree reduction those kernels perform."""

comptime RESIDENT_MAX_CONTEXT: Int = 65536
"""SAFETY CEILING on `max_ctx`, not the allocation size. `_ResidentQwen3` (and every sibling arm in
`residentk.session`, and every `_MBQwen3*` arm in `metaldispatch.session`) allocates its KV cache at
`n_layers * 2 * max_ctx * h_kv * d_head` Float32 elements where `max_ctx` is a genuine RUNTIME
parameter the caller passes at session-open time — exactly like `n_layers`, `h_kv` and `d_head`
already are. The cache is still allocated ONCE and written one slot per step IN PLACE (that is the
point of the design: `llmk.generate.kv_cache_append_flat` builds a NEW buffer of `cache_len + n_new`
and copies the whole cache every call, twice per layer per step, which is O(N^2) copying across a
generation; here there is no copy at all, at ANY `max_ctx`), so this constant's only remaining job
is `residentk_context_check`'s refusal of a nonsensical or pathological request (a caller asking
for billions of positions) BEFORE a device is touched — it no longer bounds what a session may
actually hold.

65536 rather than 512: 512 was never a Metal or Mojo limitation, it was this constant doing double
duty as both the ceiling and the allocation size, which made every caller's session exactly as big
as the ceiling whether it needed to be or not. 65536 comfortably covers Qwen3's native 32,768
context with headroom, while a session that asks for less (the default below, or anything else a
caller chooses) pays only for what it asked for — see `residentk_cache_elements` for that byte math,
and `RESIDENT_DEFAULT_CONTEXT` for the value every call site in this tree requested before this
constant's role changed."""

comptime RESIDENT_DEFAULT_CONTEXT: Int = 512
"""The `max_ctx` every call site in this tree requested back when `RESIDENT_MAX_CONTEXT` was both
the ceiling and the allocation size. Kept as its own named constant, rather than inlining `512`, so
every existing race binary and test that wants "today's behaviour, unchanged" has one symbol to
import — `residentk_weight_elems`'s own default parameter is the clearest example. Nothing about
this value is special to Qwen3-0.6B or to Metal; it is a historical default, not a second ceiling."""

comptime RESIDENT_MAX_LAYERS: Int = 128
"""Layer ceiling. Bounds the number of weight buffers a session allocates, which is the thing that
actually scales: 6 device buffers per layer plus 2 KV buffers per layer."""

comptime RESIDENT_MAX_VOCAB: Int = 1 << 21
"""Vocabulary ceiling for the tied lm_head projection. 2M rows at `d_model = 3072` in Float32 is
25 GB, so this bound is not the binding one for memory — it exists so a caller who passes an element
count where a row count belongs is refused rather than handed a device out-of-memory."""

# ── the dispatch plan, as arithmetic ──────────────────────────────────────────

comptime RESIDENT_DISPATCH_PER_LAYER: Int = 6
"""GPU dispatches one transformer layer costs in this design.

    1  rmsnorm(input_layernorm) + fused Q/K/V projection
    2  q_norm + k_norm + RoPE + KV-cache slot write (in place)
    3  scaled dot-product attention, online softmax, one threadgroup per query head
    4  o_proj accumulated straight into the residual stream
    5  rmsnorm(post_attention_layernorm) + fused gate/up projection + SwiGLU
    6  down_proj accumulated straight into the residual stream

Six is a floor imposed by hardware, not a target someone stopped at. Metal has no grid-wide
barrier, and every boundary above is a genuine grid-wide dependency: an `rmsnorm` needs the whole
vector the previous projection produced, and at `d_ff = 3072` that vector spans far more than one
threadgroup. Fusing further needs a persistent kernel with a device-scope spin barrier — possible,
high-risk, and deliberately not attempted here.

What IS fused is everything that does not cross such a boundary: the two normalizations are folded
into the projections that consume them, the three QKV projections share one normalization and one
dispatch, gate and up share another, SwiGLU rides on the gate/up kernel, and both residual adds are
a `+=` inside the projection that produces the term. A version of this driver with each elementwise
op as its own dispatch would be ~20 per layer — about 100 ms of pure submission overhead per token
on this host, i.e. slower than the Float64 CPU path it replaces."""

comptime RESIDENT_DISPATCH_FIXED: Int = 3
"""Per-token dispatches outside the layer loop: the embedding-row gather, the fused
final-rmsnorm + lm_head + per-threadgroup argmax, and the final argmax reduction.

The argmax lives on the device on purpose. Bringing 151,936 Float32 logits back per step would be
608 KB of download plus a host scan; bringing back the winning `(id, logit)` pair is 8 bytes. That
is the "or better, just the argmax" half of the resident design, and it is why the logits array
never crosses the bus during decode."""


def residentk_status_name(code: Int) -> String:
    """Human name for a status code. Every code above appears here exactly once.

    @capability residentk_status_name
    complexity: O(1)
    @endcapability
    """
    if code == RESIDENT_OK:
        return String("resident_ok")
    if code == RESIDENT_ERR_EMPTY_DIM:
        return String("resident_empty_dimension")
    if code == RESIDENT_ERR_DIM_TOO_LARGE:
        return String("resident_dimension_too_large")
    if code == RESIDENT_ERR_HEAD_MISMATCH:
        return String("resident_head_geometry_unsupported")
    if code == RESIDENT_ERR_SHADER_TOOLCHAIN_ABSENT:
        return String("resident_shader_toolchain_absent")
    if code == RESIDENT_ERR_NO_DEVICE:
        return String("resident_no_accelerator_present")
    if code == RESIDENT_ERR_CONTEXT_FULL:
        return String("resident_kv_context_full")
    if code == RESIDENT_ERR_UPLOAD_LENGTH:
        return String("resident_weight_length_mismatch")
    if code == RESIDENT_ERR_LAUNCH_FAILED:
        return String("resident_launch_failed")
    if code == RESIDENT_ERR_NON_FINITE_SCALAR:
        return String("resident_non_finite_scalar")
    return String("resident_code_out_of_range")


def residentk_dims_check(d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int) -> Int:
    """Is this a model shape the resident session can actually hold and run?

    Checks the three things the kernels genuinely require and nothing else: every dimension positive
    and inside this package's own ceilings; `h_q` an exact multiple of `h_kv` so grouped-query
    attention has an integer group size; and `d_head` a power of two, because the RoPE and SDPA
    kernels reduce across a threadgroup by halving a uniform stride and a non-power-of-two width
    would drop the odd lane silently.

    Note what is NOT checked: that `h_q * d_head == d_model`. Qwen3-0.6B-Base has
    `16 * 128 == 2048 != 1024`, so a kernel that assumed the usual identity would be wrong on the
    very model this package was built for.

    @capability residentk_dims_check
    complexity: O(1)
    counts:
    - dim d_model <= RESIDENT_MAX_D_MODEL [kernel_validated]
    - dim d_ff <= RESIDENT_MAX_D_MODEL [kernel_validated]
    - dim d_head <= RESIDENT_MAX_HEAD_DIM [kernel_validated]
    @endcapability
    """
    if d_model < 1 or h_q < 1 or h_kv < 1 or d_head < 1 or d_ff < 1:
        return RESIDENT_ERR_EMPTY_DIM
    if d_model > RESIDENT_MAX_D_MODEL or d_ff > RESIDENT_MAX_D_MODEL:
        return RESIDENT_ERR_DIM_TOO_LARGE
    if d_head > RESIDENT_MAX_HEAD_DIM:
        return RESIDENT_ERR_DIM_TOO_LARGE
    if h_q > RESIDENT_MAX_D_MODEL or h_kv > RESIDENT_MAX_D_MODEL:
        return RESIDENT_ERR_DIM_TOO_LARGE
    if h_q % h_kv != 0:
        return RESIDENT_ERR_HEAD_MISMATCH
    # A power of two has exactly one bit set; `d & (d - 1)` clears the lowest set bit.
    if d_head & (d_head - 1) != 0:
        return RESIDENT_ERR_HEAD_MISMATCH
    # The projection kernels stage `h_q * d_head` (the attention output) in the same shared array
    # `d_model` and `d_ff` use, so it is bounded by the same constant.
    if h_q > RESIDENT_MAX_D_MODEL // d_head:
        return RESIDENT_ERR_DIM_TOO_LARGE
    return RESIDENT_OK


def residentk_context_check(n_prompt: Int, n_new: Int, max_ctx: Int) -> Int:
    """Does a whole run — prompt plus every generated token — fit the session's OWN fixed-capacity
    KV cache, and is the requested capacity itself sane?

    Asked ONCE, before the first step, rather than per step. The cache is written in place and its
    capacity — `max_ctx`, a genuine runtime value the caller chooses at session-open time, not a
    fixed constant — is fixed AT THAT OPEN, so the honest time to refuse is before any token is
    produced rather than after the caller has half a sequence.

    Two independent refusals live here, deliberately not split into two functions because a caller
    always needs both answered before opening a session: `max_ctx` itself might be nonsensical (0,
    negative, or past `RESIDENT_MAX_CONTEXT`'s safety ceiling — billions of positions was never a
    request this package should attempt to satisfy), or `max_ctx` might be perfectly reasonable but
    too small for THIS run's own `n_prompt + n_new`.

    @capability residentk_context_check
    complexity: O(1)
    counts:
    - dim max_ctx <= RESIDENT_MAX_CONTEXT [kernel_validated]
    @endcapability
    """
    if n_prompt < 1 or n_new < 1 or max_ctx < 1:
        return RESIDENT_ERR_EMPTY_DIM
    if max_ctx > RESIDENT_MAX_CONTEXT:
        return RESIDENT_ERR_DIM_TOO_LARGE
    # Subtraction rather than addition: `n_prompt + n_new` is a wrapping 64-bit add at the ceilings
    # this function is meant to police, and a wrapped sum compares as small.
    if n_prompt > max_ctx - n_new:
        return RESIDENT_ERR_CONTEXT_FULL
    return RESIDENT_OK


def residentk_cache_elements(n_layers: Int, h_kv: Int, d_head: Int, max_ctx: Int) -> Int:
    """Float32 elements the KV cache holds for a session opened at `max_ctx` positions, or 0 if any
    dimension is unsupported. `n_layers * 2 * max_ctx * h_kv * d_head` — one `ck` and one `cv`
    buffer per layer, each `max_ctx * h_kv * d_head` elements, exactly what
    `residentk.session._ResidentQwen3.__init__` (and every sibling arm, including every
    `metaldispatch._MBQwen3*` arm) actually allocates via `ctx.enqueue_create_buffer`.

    Extracted as its own function, rather than left inline in `residentk_weight_elems`, so a caller
    can ask "how much memory would THIS `max_ctx` cost" independently of the full resident-weight
    total — which is exactly what sizing a deployment before opening a session needs, and exactly
    what let this function's own docstring replace `residentk_weight_elems`'s previous inline use of
    the (now much larger) `RESIDENT_MAX_CONTEXT` safety ceiling as if it were the allocation size.

    @capability residentk_cache_elements
    complexity: O(1)
    counts:
    - dim n_layers <= RESIDENT_MAX_LAYERS [kernel_validated]
    - dim max_ctx <= RESIDENT_MAX_CONTEXT [kernel_validated]
    @endcapability
    """
    if n_layers < 1 or n_layers > RESIDENT_MAX_LAYERS:
        return 0
    if h_kv < 1 or d_head < 1:
        return 0
    if max_ctx < 1 or max_ctx > RESIDENT_MAX_CONTEXT:
        return 0
    return n_layers * 2 * max_ctx * h_kv * d_head


def residentk_dispatch_budget(n_layers: Int) -> Int:
    """GPU dispatches ONE decode token costs: `n_layers * 6 + 3`. Zero or less on a bad layer count.

    Exported so a test asserts the count the session actually issues against the count this design
    claims. Every dispatch is ~180 us of BLOCKED host time on this backend, so this number times
    that constant is the floor of a token's latency before any arithmetic happens — which is why it
    is a checked contract value rather than a comment.

    @capability residentk_dispatch_budget
    complexity: O(1)
    counts:
    - dim n_layers <= RESIDENT_MAX_LAYERS [kernel_validated]
    @endcapability
    """
    if n_layers < 1 or n_layers > RESIDENT_MAX_LAYERS:
        return 0
    return n_layers * RESIDENT_DISPATCH_PER_LAYER + RESIDENT_DISPATCH_FIXED


def residentk_dispatch_budget_deep(n_layers: Int) -> Int:
    """GPU dispatches ONE token costs once `residentk_splitk_should_split(n_keys)` is true for that
    token's `n_keys` — the SDPA role becomes a partial-plus-merge dispatch PAIR instead of one
    dispatch, so this is `residentk_dispatch_budget(n_layers)` plus exactly one extra dispatch per
    layer, restated as its own formula (`1 + n_layers * 7 + 2`) to match the exact arithmetic every
    `_MBQwen3I8...AllSimd*` session struct's own `n_descriptors_deep` field already computes — see
    `metaldispatch.session`'s deep-path structs for that arithmetic's derivation.

    Exported for the same reason `residentk_dispatch_budget` is: a caller validating a real step's
    dispatch count needs to know WHICH of the two budgets applies, and get it from one named place
    rather than re-deriving `n_layers * 7 + 3` at every call site.

    @capability residentk_dispatch_budget_deep
    complexity: O(1)
    counts:
    - dim n_layers <= RESIDENT_MAX_LAYERS [kernel_validated]
    @endcapability
    """
    if n_layers < 1 or n_layers > RESIDENT_MAX_LAYERS:
        return 0
    return 1 + n_layers * 7 + 2


def residentk_weight_elems(
    d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int, n_layers: Int, vocab: Int,
    max_ctx: Int = RESIDENT_DEFAULT_CONTEXT,
) -> Int:
    """Float32 elements a session holds resident on the device, or 0 if the shape is unsupported.

    Per layer: two norm gains (`d_model` each), two head-norm gains (`d_head` each), the fused QKV
    matrix `(h_q + 2*h_kv) * d_head` by `d_model`, `o_proj` `d_model` by `h_q * d_head`, the fused
    gate/up matrix `2 * d_ff` by `d_model`, and `down_proj` `d_model` by `d_ff`. Plus, once: the tied
    embedding/lm_head table `vocab` by `d_model`, the final norm gain, and the KV cache at
    `residentk_cache_elements(n_layers, h_kv, d_head, max_ctx)`.

    `max_ctx` defaults to `RESIDENT_DEFAULT_CONTEXT` (512, this package's historical fixed size)
    rather than to `RESIDENT_MAX_CONTEXT` (now a much larger safety ceiling, not a size) so every
    existing call site that predates `max_ctx` becoming a real parameter here — this function's own
    golden-vector test among them — reports the EXACT same number it always did, with no call site
    changes required. A caller sizing a session at a different `max_ctx` passes it explicitly.

    The number matters because it IS the one-time cost the resident design front-loads, and because
    at 4 bytes each it is also the per-token memory traffic floor: nothing can decode faster than
    this many bytes divided by the device's streaming bandwidth.

    @capability residentk_weight_elems
    complexity: O(1)
    counts:
    - dim n_layers <= RESIDENT_MAX_LAYERS [kernel_validated]
    - dim vocab <= RESIDENT_MAX_VOCAB [kernel_validated]
    - dim max_ctx <= RESIDENT_MAX_CONTEXT [kernel_validated]
    @endcapability
    """
    if residentk_dims_check(d_model, h_q, h_kv, d_head, d_ff) != RESIDENT_OK:
        return 0
    if n_layers < 1 or n_layers > RESIDENT_MAX_LAYERS:
        return 0
    if vocab < 1 or vocab > RESIDENT_MAX_VOCAB:
        return 0
    var cache = residentk_cache_elements(n_layers, h_kv, d_head, max_ctx)
    if cache <= 0:
        return 0

    var n_qkv = (h_q + 2 * h_kv) * d_head
    var per_layer = 2 * d_model + 2 * d_head
    per_layer += n_qkv * d_model
    per_layer += d_model * (h_q * d_head)
    per_layer += 2 * d_ff * d_model
    per_layer += d_model * d_ff
    return n_layers * per_layer + cache + vocab * d_model + d_model


def residentk_scalars_ok(eps: Float64, scale: Float64) -> Bool:
    """Both attention/normalization scalars finite and positive.

    Separate from the dimension check because a NaN defeats an unvalidated threshold silently: a NaN
    `eps` makes every `1 / sqrt(x + eps)` a NaN, which then propagates through 28 layers and comes
    back as an argmax over a vector of NaNs — an answer-shaped non-answer. Rule 4d.

    @capability residentk_scalars_ok
    complexity: O(1)
    @endcapability
    """
    if not tx_finite(eps) or not tx_finite(scale):
        return False
    return eps > 0.0 and scale > 0.0


# ── the split-K depth policy: a GENUINELY DYNAMIC replacement for the fixed
# `metaldispatch.session._ATTN_SPLITK_N_SPLITS_NATIVE = 80` / `_ATTN_SPLITK_THRESHOLD = 512`
# ──────────────────────────────────────────────────────────────────────────────────────────
#
# BACKGROUND: PR #523 landed `_ATTN_SPLITK_N_SPLITS_NATIVE = 80`, a SINGLE split count re-tuned from
# scratch on the real production kernel — but at ONE depth only (`n_keys=4000`). A dedicated
# calibration sweep (8 depth buckets x 9 `n_splits` candidates x 5 rounds, plus a dedicated dead-zone
# extension down to `n_keys=16`, all on this same real kernel/pipeline, never a scratch kernel) found
# the true optimum is NOT that one constant: it steps with depth in units of "warps per core"
# (`h_q * n_splits / n_cores` — the total warp count this dispatch puts in flight, divided by this
# GPU's own core count), saturating at a ceiling around `n_keys ~= 1000` and staying there out to at
# least 8000 (2x further than PR #523's own sweep ever tested), while ALSO showing a real, growing win
# from splitting AT ALL down to `n_keys ~= 32` — well below the shipped `_ATTN_SPLITK_THRESHOLD = 512`
# gate.
#
# INDEPENDENT RE-VERIFICATION (this task's own Policy phase, before trusting the calibration above):
# re-ran the identical measurement at `n_keys in {256, 500, 750}` across the full 7-candidate set
# (`n_splits in {20,40,60,80,100,120,160}`), 5 rounds each. Two findings:
#   1. The ROBUST structure reproduces cleanly: the deep-regime ceiling (`n_keys=4000` favors
#      `n_splits=80` over both `60` and `120`, non-monotonically, by a wide and reproducible margin —
#      exactly PR #523's own finding) and the dead-zone win (small-`n_splits` native split-K beats the
#      unsplit kernel by ~2.5-2.8x at `n_keys` in `{64, 128, 256}`, growing with depth) both reproduce
#      independently, on a different day, on this same machine.
#   2. The EXACT optimum in the 256-750 "mid" range is NOT reliably pinned to single-`n_splits`
#      resolution: a first rerun found `n_splits=60` beating `40` by nearly 2x at `n_keys=256`; a
#      second, more complete rerun (same candidates, same depths, minutes later) found the OPPOSITE —
#      `n_splits=40` clearly best, `60` close behind — with the `n_splits=40` condition's own mean
#      moving by ~+30% between the two runs at fixed `n_keys`. This is real session-to-session /
#      thermal drift on this hardware, not a bug in either sweep (both used byte-identical
#      measurement code), and it is LARGER than the gap between neighboring `n_splits` candidates in
#      this middle range. Fitting a precise breakpoint to that noise would be overfitting it.
#
# THE FORMULA, and why a formula over a lookup table: `warps_per_core(n_keys)` is modeled as LINEAR
# IN log2(n_keys) between two anchors that ARE robust across every source above (PR #523's own sweep,
# the calibration phase's 8-bucket sweep, and this phase's own re-verification):
#   anchor low:  n_keys=128  -> warps_per_core=16  (n_splits=40 at this model's h_q=16, this
#                                machine's 40 cores) — the shallow end of the MAIN sweep, where every
#                                source agrees splitting has clearly started paying off but the
#                                widest configs are not yet worth it.
#   anchor high: n_keys=1000 -> warps_per_core=32  (n_splits=80) — where every source agrees the
#                                occupancy ceiling saturates and going wider NEVER wins, at any depth
#                                tested up to 8000.
# The SAME line, extrapolated (not clamped) below `n_keys=128`, reproduces the dead-zone's own
# shallower anchors reasonably (n_keys=32 -> ~13, measured optimum ~16; n_keys=64 -> ~27, measured
# optimum ~32) without being FIT to them — a genuine prediction from the two robust anchors, not a
# third calibrated point. `log2` scaling is the natural unit for a GPU occupancy/warp-scheduling
# curve (the same reason llama.cpp's own `nwg` split-count formula doubles a discrete state rather
# than scaling linearly in the raw key count) — this formula is llama.cpp's own idea (a formula over
# the real key count, evaluated fresh per dispatch) applied continuously instead of via `nsg *= 2`
# discrete doubling, because Algenta's own measured tiers are NOT power-of-two multiples of each
# other (16 -> 24 -> 32, not 16 -> 32 -> 64).
#
# Below `n_keys = 32` splitting is not worth it at all (`residentk_splitk_should_split`) — the
# dead-zone sweep measured `n_keys=16` a wash (~1.0x) against the unsplit kernel and `n_keys=32` a
# clear ~1.4x win, so the gate sits at the tested boundary, not an interpolated guess between the two.
# This is what retires the old, much higher, fixed `_ATTN_SPLITK_THRESHOLD = 512` gate: the data
# supports splitting from 32 onward, not 512.

comptime RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS: Int = 32
"""Below this many keys, don't split at all — take the unsplit SDPA path. Measured: `n_keys=16` is a
wash (~1.0x) against the unsplit kernel; `n_keys=32` is already a clear ~1.4x win. The gate sits at
32, the smaller MEASURED-WINNING depth, not a guess at the midpoint between the two."""

comptime RESIDENT_SPLITK_ANCHOR_LO_KEYS: Int = 128
comptime RESIDENT_SPLITK_ANCHOR_LO_WARPS_PER_CORE: Float64 = 16.0
comptime RESIDENT_SPLITK_ANCHOR_HI_KEYS: Int = 1000
comptime RESIDENT_SPLITK_ANCHOR_HI_WARPS_PER_CORE: Float64 = 32.0
"""The two robust calibration anchors `residentk_splitk_policy` interpolates (and extrapolates)
between, in log2(n_keys) space — see the module-level comment above this block for the full
grounding and the independent re-verification that found these two anchors, and only these two,
reproduce across separate sweep runs where finer-grained points in between did not."""

comptime RESIDENT_SPLITK_MIN_WARPS_PER_CORE: Float64 = 1.0
"""Floor on the interpolated occupancy target, so a pathologically small `n_keys` just above the
no-split gate (or a future anchor re-tune) can never drive `warps_per_core`, and therefore
`n_splits`, to zero or negative before the final `>= 1` clamp below even applies."""

comptime RESIDENT_SPLITK_FALLBACK_N_CORES: Int = 40
"""Last-resort default for `n_cores` when the caller could not determine a real one (the runtime
probe failed, or a test calls this function directly without wiring one) — NOT a claim that every
host has 40 GPU cores. This is this development machine's own measured count (`system_profiler
SPDisplaysDataType`, cross-checked against an IOKit `AGXAccelerator`/`gpu-core-count` registry read —
see `metaldispatch.ffi._mb_gpu_core_count`), chosen as the fallback specifically because it reproduces
`_ATTN_SPLITK_N_SPLITS_NATIVE = 80` (this file's `residentk_splitk_max_n_splits(40, 16) == 80`) — i.e.
a host whose core count genuinely cannot be determined degrades to exactly PR #523's own last-known-
good, race-verified fixed behavior, never to an invented number that could be worse than what already
shipped."""


def _residentk_log2(x: Float64) -> Float64:
    """log base 2 via natural log — same one-line helper `audio`/`blockchain`/`ergonomics` each
    already carry their own private copy of, rather than a new cross-package dependency for one
    multiply."""
    comptime _LOG2_E: Float64 = 1.4426950408889634  # 1/ln(2)
    return log(x) * _LOG2_E


def residentk_splitk_should_split(n_keys: Int) -> Bool:
    """Is `n_keys` deep enough that splitting the SDPA dispatch is worth its own fixed overhead
    (a second kernel launch, plus the merge kernel) at all?

    @capability residentk_splitk_should_split
    complexity: O(1)
    @endcapability
    """
    return n_keys >= RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS


def residentk_splitk_max_n_splits(n_cores: Int, h_q: Int) -> Int:
    """The largest `n_splits` `residentk_splitk_policy` could EVER return for this `(n_cores, h_q)`
    pair — the occupancy ceiling, `round(RESIDENT_SPLITK_ANCHOR_HI_WARPS_PER_CORE * n_cores / h_q)`.

    A caller that must allocate split-K scratch buffers ONCE, before knowing any future step's
    `n_keys` (`metaldispatch.session._MBQwen3I8AllSimd7`'s own `_ensure_deep_initialized`), sizes them
    for THIS value — matching the existing lazy-init discipline `_MBQwen3I8AllSimd6` already uses for
    its own fixed `_ATTN_SPLITK_N_SPLITS_NATIVE`, just computed from the runtime-detected core count
    instead of a comptime constant. Falls back to `RESIDENT_SPLITK_FALLBACK_N_CORES` on a
    non-positive `n_cores` (a probe that failed) — see that constant's own docstring for why that
    fallback reproduces `_ATTN_SPLITK_N_SPLITS_NATIVE` exactly rather than guessing.

    @capability residentk_splitk_max_n_splits
    complexity: O(1)
    @endcapability
    """
    var cores = n_cores
    if cores < 1:
        cores = RESIDENT_SPLITK_FALLBACK_N_CORES
    var hq = h_q
    if hq < 1:
        hq = 1
    var raw = RESIDENT_SPLITK_ANCHOR_HI_WARPS_PER_CORE * Float64(cores) / Float64(hq)
    var n_splits = Int(raw + 0.5)
    if n_splits < 1:
        n_splits = 1
    return n_splits


def residentk_splitk_policy(n_keys: Int, n_cores: Int, h_q: Int) -> Int:
    """The split count to use for THIS decode step's `n_keys`, on a GPU with `n_cores` compute cores
    running `h_q` query heads — see the module-level comment above this block for the full
    calibration/re-verification account and the formula's derivation.

    `warps_per_core(n_keys)` is `RESIDENT_SPLITK_ANCHOR_LO_WARPS_PER_CORE` plus a slope times
    `log2(n_keys) - log2(RESIDENT_SPLITK_ANCHOR_LO_KEYS)`, where the slope is chosen so the line
    passes through BOTH anchors exactly (`warps_per_core(128) == 16.0`, `warps_per_core(1000) ==
    32.0`, verified as golden vectors in `test_residentk_splitk_policy.mojo`), clamped to
    `[RESIDENT_SPLITK_MIN_WARPS_PER_CORE, RESIDENT_SPLITK_ANCHOR_HI_WARPS_PER_CORE]` outside that
    range so neither a very shallow nor a very deep `n_keys` can push the target unboundedly. The
    final `n_splits` is `round(warps_per_core * n_cores / h_q)`, clamped to `[1,
    residentk_splitk_max_n_splits(n_cores, h_q)]`.

    Sane on every input, not just the calibrated range: `n_keys <= 0` or `h_q < 1` returns 1 (the
    smallest meaningful split count, never a crash or a negative/zero value a caller could feed to a
    GPU dispatch's grid width); `n_cores <= 0` falls back to `RESIDENT_SPLITK_FALLBACK_N_CORES` (see
    that constant's own docstring). Does NOT gate on `RESIDENT_SPLITK_NO_SPLIT_MAX_KEYS` itself — a
    caller checks `residentk_splitk_should_split` separately before ever using this value, exactly
    the same separation `metaldispatch.session` already has between `_ATTN_SPLITK_THRESHOLD` (the
    gate) and `_ATTN_SPLITK_N_SPLITS_NATIVE` (the value), just with both made dynamic instead of one
    of them fixed.

    Never changes any numerical OUTPUT of the split-K kernel pair — `_splitk_partial_kernel_simd_
    native`/`_splitk_merge_kernel_simd` are proven correct for ANY `n_splits` (including `n_splits >
    n_keys`, a genuinely empty split — see that kernel's own docstring and its isolated suite), so
    this function only ever chooses WHICH already-correct configuration computes a step, never
    perturbs the arithmetic itself.

    @capability residentk_splitk_policy
    complexity: O(1)
    @endcapability
    """
    if h_q < 1 or n_keys < 1:
        return 1
    var cores = n_cores
    if cores < 1:
        cores = RESIDENT_SPLITK_FALLBACK_N_CORES

    var log_nk = _residentk_log2(Float64(n_keys))
    var log_lo = _residentk_log2(Float64(RESIDENT_SPLITK_ANCHOR_LO_KEYS))
    var log_hi = _residentk_log2(Float64(RESIDENT_SPLITK_ANCHOR_HI_KEYS))
    var slope = (
        (RESIDENT_SPLITK_ANCHOR_HI_WARPS_PER_CORE - RESIDENT_SPLITK_ANCHOR_LO_WARPS_PER_CORE)
        / (log_hi - log_lo)
    )
    var warps_per_core = RESIDENT_SPLITK_ANCHOR_LO_WARPS_PER_CORE + slope * (log_nk - log_lo)
    if warps_per_core > RESIDENT_SPLITK_ANCHOR_HI_WARPS_PER_CORE:
        warps_per_core = RESIDENT_SPLITK_ANCHOR_HI_WARPS_PER_CORE
    if warps_per_core < RESIDENT_SPLITK_MIN_WARPS_PER_CORE:
        warps_per_core = RESIDENT_SPLITK_MIN_WARPS_PER_CORE

    var n_splits = Int(warps_per_core * Float64(cores) / Float64(h_q) + 0.5)
    if n_splits < 1:
        n_splits = 1
    var ceiling = residentk_splitk_max_n_splits(cores, h_q)
    if n_splits > ceiling:
        n_splits = ceiling
    return n_splits


comptime RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M: Int = 32
"""Restates `residentk.kernels._GEMM_BM` (the WIDE weight-stationary-tiled-GEMM config's own row-
tile width) as a plain literal here, not an import — `residentk.contract` is a layering root
(`residentk.kernels` imports FROM this module, never the reverse), so the threshold is a second,
independent literal, matching the SAME "restate a value rather than create a layering cycle"
choice `metaldispatch.qwen3_decode`'s own `QWEN3_0_6B_BASE_D_MODEL` etc. already make for constants
that could otherwise be imported from a file this one must not depend on.

`m_rows < RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M` is exactly the point below which the WIDE tile
(`BM=32`) is GUARANTEED to be more than half zero-padding on the row axis for EVERY row-tile it
ever launches (`m_rows` fits inside a single `BM`-wide tile whenever `m_rows <= 32`, so a smaller
`m_rows` only shrinks how much of that one tile is real work) — the structural boundary
`residentk_prefill_gemm_use_narrow_tile`'s own threshold is anchored to, not a free-floating guess."""


fn residentk_prefill_gemm_use_narrow_tile(m_rows: Int) -> Bool:
    """Should THIS `prefill_batch()` call's weight-stationary-tiled-GEMM dispatches
    (`_pf_gemm_assign_kernel_i8`/`_pf_gemm_accum_kernel_i8`/`_pf_gemm_swiglu_kernel_i8`) use their
    NARROW-tile twins (`_pf_gnrw_assign_kernel_i8`/`_pf_gnrw_accum_kernel_i8`/`_pf_gnrw_swiglu_
    kernel_i8`, `residentk.kernels`) instead of the wide ones?

    A COARSE, two-point calibration, stated as such rather than oversold: real end-to-end runs on
    the actual Qwen3-0.6B-Base checkpoint found the WIDE config (`BM=32`) a real win at `m_rows=256`
    (1165 tok/s against the row-flattened family's own 558.9) but a real REGRESSION at `m_rows=5`
    (91.6 tok/s, WORSE than that same row-flattened family's short-prompt throughput); the NARROW
    config (`BM=8`) reverses both signs (110.1 tok/s at `m_rows=5`, but only 783.3 at `m_rows=256`,
    a real regression from the wide config's own 1165) — confirming NEITHER config is good across
    this arm's whole race range (8 to 512) and a real choice between them is needed, not a single
    constant. Only TWO configs were built and measured (not a fine-grained sweep across `BN`/`BK`/
    `TM`/`TN` too, and not a third or fourth `BM` candidate in between) — the implementation plan's
    own "let the data decide single-vs-multi-variant" step, decided in favor of "multi," with the
    SIMPLEST version of "multi" (a binary choice, not `residentk_splitk_policy`'s own continuous
    log-linear interpolation, since there is no continuous knob here — only two COMPILED kernel
    variants exist). The threshold itself (`RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M`, 32) is the
    structural boundary where the wide tile's own padding waste starts, not a third measured anchor
    point in its own right — a finer sweep (more `m_rows` points, more tile configs) could refine
    this boundary later; this is Phase B's first real answer, not its last word.

    @capability residentk_prefill_gemm_use_narrow_tile
    complexity: O(1)
    @endcapability
    """
    return m_rows < RESIDENT_PREFILL_GEMM_NARROW_THRESHOLD_M
