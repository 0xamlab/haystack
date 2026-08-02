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
  residentk_context_check(pos, n_new, max_ctx)                   — does the whole run fit the cache
  residentk_dispatch_budget(n_layers)                            — GPU dispatches for ONE token
  residentk_weight_elems(d_model, h_q, h_kv, d_head, d_ff, n_layers, vocab)  — resident Float32 count
"""

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
"""The requested run would need more KV-cache positions than `RESIDENT_MAX_CONTEXT`. The cache is
allocated once and written IN PLACE, so its capacity is fixed at session open — refusing here is
what stops a step from writing past the last slot, which on a GPU is silent corruption."""

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

comptime RESIDENT_MAX_CONTEXT: Int = 512
"""Positions the resident KV cache holds, fixed at session open.

Allocated once as `n_layers * 2 * RESIDENT_MAX_CONTEXT * h_kv * d_head` Float32 and written one slot
per step IN PLACE. That is the point of the design: `llmk.generate.kv_cache_append_flat` builds a
NEW buffer of `cache_len + n_new` and copies the whole cache every call, twice per layer per step,
which is O(N^2) copying across a generation. Here there is no copy at all.

512 rather than a larger number because the allocation is unconditional: at Qwen3-0.6B's shape
(28 layers, 8 KV heads, 128 head dim) it is 117 MB of device memory that is paid whether the run
uses 20 positions or 500. A longer context is a real feature and a real allocation decision, not a
constant to raise casually."""

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


fn residentk_status_name(code: Int) -> String:
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


fn residentk_dims_check(d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int) -> Int:
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


fn residentk_context_check(n_prompt: Int, n_new: Int, max_ctx: Int) -> Int:
    """Does a whole run — prompt plus every generated token — fit the fixed-capacity KV cache?

    Asked ONCE, before the first step, rather than per step. The cache is written in place and its
    capacity was fixed at session open, so the honest time to refuse is before any token is produced
    rather than after the caller has half a sequence.

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


fn residentk_dispatch_budget(n_layers: Int) -> Int:
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


fn residentk_weight_elems(
    d_model: Int, h_q: Int, h_kv: Int, d_head: Int, d_ff: Int, n_layers: Int, vocab: Int
) -> Int:
    """Float32 elements a session holds resident on the device, or 0 if the shape is unsupported.

    Per layer: two norm gains (`d_model` each), two head-norm gains (`d_head` each), the fused QKV
    matrix `(h_q + 2*h_kv) * d_head` by `d_model`, `o_proj` `d_model` by `h_q * d_head`, the fused
    gate/up matrix `2 * d_ff` by `d_model`, and `down_proj` `d_model` by `d_ff`. Plus, once: the tied
    embedding/lm_head table `vocab` by `d_model`, the final norm gain, and the KV cache at
    `n_layers * 2 * RESIDENT_MAX_CONTEXT * h_kv * d_head`.

    The number matters because it IS the one-time cost the resident design front-loads, and because
    at 4 bytes each it is also the per-token memory traffic floor: nothing can decode faster than
    this many bytes divided by the device's streaming bandwidth.

    @capability residentk_weight_elems
    complexity: O(1)
    counts:
    - dim n_layers <= RESIDENT_MAX_LAYERS [kernel_validated]
    - dim vocab <= RESIDENT_MAX_VOCAB [kernel_validated]
    @endcapability
    """
    if residentk_dims_check(d_model, h_q, h_kv, d_head, d_ff) != RESIDENT_OK:
        return 0
    if n_layers < 1 or n_layers > RESIDENT_MAX_LAYERS:
        return 0
    if vocab < 1 or vocab > RESIDENT_MAX_VOCAB:
        return 0

    var n_qkv = (h_q + 2 * h_kv) * d_head
    var per_layer = 2 * d_model + 2 * d_head
    per_layer += n_qkv * d_model
    per_layer += d_model * (h_q * d_head)
    per_layer += 2 * d_ff * d_model
    per_layer += d_model * d_ff
    var cache = 2 * RESIDENT_MAX_CONTEXT * h_kv * d_head
    return n_layers * (per_layer + cache) + vocab * d_model + d_model


fn residentk_scalars_ok(eps: Float64, scale: Float64) -> Bool:
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
