"""
attnk.rope — rotary position embedding: frequency tables, application, and the theta convention.
Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_attnk_rope.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

The theta convention is a choice, and it is made here explicitly
------------------------------------------------------------------
Two frozen kernels compute "the theta for an extended context" and they do not agree. Measured:

    model_abi.rope_theta_scale(10000, 2048, 8192)   -> 160000     (squared in the factor)
    model_interop.hf_rope_theta_scale(10000, 4.0)   ->  40000     (linear in the factor)

Both describe the same 4x extension and differ by 4x. Both conventions exist in real checkpoints, so
neither kernel is wrong; they answer different questions and were written for different callers.
Both stay reachable and unchanged.

**This module's default is the linear convention** — `theta * factor` — because that is what the
scaling field in a Hugging Face config means, and a checkpoint's own config is the only authority on
how its weights were trained. `ROPE_SCALING_SQUARED` selects the other, and `rope_theta_agreement()`
returns both values and their ratio so a caller comparing implementations gets a number.

This is the most dangerous constant in the package. A model loaded with the wrong theta does not
crash and does not produce obvious garbage — it produces fluent text whose quality decays as context
grows, which reads as a mediocre model rather than a wrong constant.

Why the table is always f32 or wider
--------------------------------------
`cos`/`sin` tables are built in Float64 here and must never be stored in bf16. bf16 has 8 significand
bits, so at position 4000 the representable spacing exceeds one radian at the low-frequency
dimensions — the rotation for adjacent positions collapses to the same value and the model loses
positional resolution exactly where long context needs it. `tensorx.dtype` states the same rule for
the plane as a whole; it is repeated here because this is where it gets violated.

Interleaved versus split-half is a real fork
----------------------------------------------
Two layouts are in use. GPT-J style pairs adjacent dimensions `(0,1), (2,3), ...`; GPT-NeoX style
pairs a dimension with the one half a head away, `(0, d/2), (1, d/2+1), ...`. A checkpoint converted
with the wrong one loads, runs, and produces fluent nonsense — it is the single most common
conversion bug in the ecosystem. Both are implemented, neither is guessed, and `interleaved` has no
default.

Public API:
  rope_theta_for(base, factor, scaling_code)      — the convention, chosen explicitly
  rope_theta_agreement(base, orig_ctx, target_ctx) — both frozen answers and their ratio
  rope_inv_freq(head_dim, theta)                   — one inverse frequency per dimension pair
  rope_table(head_dim, max_pos, theta)             — cos/sin for every (position, pair)
  rope_apply_flat(x, cos, sin, n_tok, n_heads, head_dim, pos, interleaved)
  rope_apply_inverse_flat(...)                     — the exact inverse, for round-trip proof
"""

from std.math import cos as mcos, sin as msin, pow as mpow
from attnk.contract import (
    ATTN_ERR_DIM_TOO_LARGE,
    ATTN_ERR_EMPTY_DIM,
    ATTN_ERR_LENGTH_MISMATCH,
    ATTN_ERR_NON_FINITE_SCALAR,
    ATTN_ERR_UNKNOWN_SCALING,
    ATTN_MAX_HEAD_DIM,
    ATTN_MAX_SEQ,
    ATTN_OK,
)
from model_abi import rope_theta_scale
from model_interop import hf_rope_theta_scale
from tensorx.contract import TX_OK, tx_count_ok, tx_finite

comptime ROPE_SCALING_NONE: Int = 0
comptime ROPE_SCALING_LINEAR: Int = 1
comptime ROPE_SCALING_SQUARED: Int = 2

comptime ROPE_MAX_TABLE_CELLS: Int = 1 << 24
"""Cap on `max_pos * head_dim / 2` table entries — 16M pairs, two Float64 arrays, ~256 MB.

The table is materialized, unlike the score matrix, because it is reused across every layer and head
and rebuilding it per call would dominate. That makes it worth a ceiling of its own: rule 1c, two
arrays of this length is the real allocation, not one."""


@fieldwise_init
struct RopeTable(Copyable, Movable):
    """cos and sin for every (position, dimension-pair), row-major over positions."""

    var cos_table: List[Float64]
    var sin_table: List[Float64]
    var max_pos: Int
    var n_pairs: Int
    var theta: Float64
    var status: Int


@fieldwise_init
struct RopeApplied(Copyable, Movable):
    """Rotated values, same length and layout as the input."""

    var values: List[Float64]
    var n_tok: Int
    var n_heads: Int
    var head_dim: Int
    var status: Int


@fieldwise_init
struct RopeAgreement(Copyable, Movable):
    """What each frozen theta kernel says, and how far apart they are."""

    var squared_convention: Float64
    var linear_convention: Float64
    var ratio: Float64
    var agree: Bool


fn rope_theta_agreement(
    base: Float64, original_context: Float64, target_context: Float64
) -> RopeAgreement:
    """Both frozen theta answers for the same extension, plus their ratio.

    Exists so the disagreement is a reported number rather than a discovery. Neither frozen kernel is
    modified and both remain reachable; a caller integrating against an existing checkpoint can call
    this, see the two candidates, and match whichever its config implies.
    """
    if not tx_finite(base) or original_context <= 0.0 or target_context <= 0.0:
        return RopeAgreement(0.0, 0.0, 0.0, False)
    var factor = target_context / original_context
    var squared = rope_theta_scale(base, original_context, target_context)
    var linear = hf_rope_theta_scale(base, factor)
    var ratio = squared / linear if linear != 0.0 else 0.0
    # A tolerance rather than equality: these are two float computations of the same intent, and an
    # exact-equality test would call them different over a rounding difference.
    var diff = squared - linear
    if diff < 0.0:
        diff = -diff
    var scale_of = linear if linear > 0.0 else 1.0
    return RopeAgreement(squared, linear, ratio, diff <= 1e-9 * scale_of)


fn rope_theta_for(base: Float64, factor: Float64, scaling_code: Int) -> Float64:
    """The theta this module will use. `-1.0` for an unknown scaling code — never a silent default.

    `ROPE_SCALING_LINEAR` is what a Hugging Face config's scaling factor means, and a checkpoint's own
    config is the only authority on how its weights were trained. `ROPE_SCALING_SQUARED` is offered
    because the other frozen kernel implements it and some checkpoints want it.

    Returning `-1.0` rather than falling back to `base` matters: a silent fallback on a typo'd code
    produces an unscaled model that works at short context and degrades at long, which is the failure
    this whole module is trying to make impossible to reach by accident.
    """
    if not tx_finite(base) or base <= 0.0:
        return -1.0
    if scaling_code == ROPE_SCALING_NONE:
        return base
    if not tx_finite(factor) or factor <= 0.0:
        return -1.0
    if scaling_code == ROPE_SCALING_LINEAR:
        return hf_rope_theta_scale(base, factor)
    if scaling_code == ROPE_SCALING_SQUARED:
        # The frozen kernel takes contexts rather than a factor; feed it a unit original so the
        # factor means the same thing on both branches.
        return rope_theta_scale(base, 1.0, factor)
    return -1.0


fn rope_inv_freq(head_dim: Int, theta: Float64) -> List[Float64]:
    """Inverse frequency per dimension pair: `theta ** (-2i / head_dim)` for i in 0..head_dim/2.

    Empty list on an odd or out-of-range `head_dim`. RoPE rotates pairs, so an odd head dimension has
    no valid pairing and is rejected rather than silently dropping the last element.
    """
    var out = List[Float64]()
    if head_dim <= 0 or head_dim > ATTN_MAX_HEAD_DIM or head_dim % 2 != 0:
        return out^
    if not tx_finite(theta) or theta <= 0.0:
        return out^
    var n_pairs = head_dim // 2
    for i in range(n_pairs):
        var exponent = -2.0 * Float64(i) / Float64(head_dim)
        out.append(mpow(theta, exponent))
    return out^


fn rope_table(head_dim: Int, max_pos: Int, theta: Float64) -> RopeTable:
    """Build cos/sin for every (position, pair). Row-major: `pos * n_pairs + pair`.

    Always Float64. See the module docstring — a bf16 table loses positional resolution at long
    context, and it does so silently.

    @capability rope_table
    complexity: O(max_pos * head_dim)
    counts:
    - dim head_dim <= ATTN_MAX_HEAD_DIM [kernel_validated]
    - dim max_pos <= ATTN_MAX_SEQ [kernel_validated]
    @endcapability
    """
    var c = List[Float64]()
    var s = List[Float64]()
    if head_dim <= 0 or max_pos <= 0:
        return RopeTable(c^, s^, 0, 0, theta, ATTN_ERR_EMPTY_DIM)
    if head_dim > ATTN_MAX_HEAD_DIM or max_pos > ATTN_MAX_SEQ or head_dim % 2 != 0:
        return RopeTable(c^, s^, 0, 0, theta, ATTN_ERR_DIM_TOO_LARGE)
    if not tx_finite(theta) or theta <= 0.0:
        return RopeTable(c^, s^, 0, 0, theta, ATTN_ERR_NON_FINITE_SCALAR)

    var n_pairs = head_dim // 2
    # Division rather than a multiply: max_pos * n_pairs is a wrapping product at these ceilings.
    if n_pairs > ROPE_MAX_TABLE_CELLS // max_pos:
        return RopeTable(c^, s^, 0, 0, theta, ATTN_ERR_DIM_TOO_LARGE)

    var inv = rope_inv_freq(head_dim, theta)
    if len(inv) != n_pairs:
        return RopeTable(c^, s^, 0, 0, theta, ATTN_ERR_DIM_TOO_LARGE)

    for pos in range(max_pos):
        var p = Float64(pos)
        for pair in range(n_pairs):
            var angle = p * inv[pair]
            c.append(mcos(angle))
            s.append(msin(angle))
    return RopeTable(c^, s^, max_pos, n_pairs, theta, ATTN_OK)


fn _rope_apply(
    x: List[Float64], cos_t: List[Float64], sin_t: List[Float64],
    n_tok: Int, n_heads: Int, head_dim: Int, pos: List[Int],
    interleaved: Bool, inverse: Bool
) -> RopeApplied:
    """Shared body for the forward and inverse rotations. Sign of the sine term is the only difference."""
    var out = List[Float64]()
    if n_tok <= 0 or n_heads <= 0 or head_dim <= 0:
        return RopeApplied(out^, 0, 0, 0, ATTN_ERR_EMPTY_DIM)
    if head_dim % 2 != 0 or head_dim > ATTN_MAX_HEAD_DIM:
        return RopeApplied(out^, 0, 0, 0, ATTN_ERR_DIM_TOO_LARGE)
    if tx_count_ok(n_tok, len(pos)) != TX_OK:
        return RopeApplied(out^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    var n_pairs = head_dim // 2
    # Every index below is derived from these, so they are checked against the real lengths first.
    var needed = n_tok * n_heads * head_dim
    if needed <= 0 or len(x) < needed:
        return RopeApplied(out^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    var max_pos = 0
    for t in range(n_tok):
        if pos[t] < 0:
            return RopeApplied(out^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)
        if pos[t] > max_pos:
            max_pos = pos[t]
    if len(cos_t) < (max_pos + 1) * n_pairs or len(sin_t) < (max_pos + 1) * n_pairs:
        return RopeApplied(out^, 0, 0, 0, ATTN_ERR_LENGTH_MISMATCH)

    for _ in range(needed):
        out.append(0.0)

    var sign = -1.0 if inverse else 1.0
    for t in range(n_tok):
        var trow = pos[t] * n_pairs
        for h in range(n_heads):
            var base = (t * n_heads + h) * head_dim
            for pair in range(n_pairs):
                var cv = cos_t[trow + pair]
                var sv = sin_t[trow + pair] * sign
                # The layout fork. GPT-J pairs adjacent dimensions; GPT-NeoX pairs a dimension with
                # the one half a head away. Choosing wrong loads and runs and is wrong.
                var i0 = base + 2 * pair if interleaved else base + pair
                var i1 = base + 2 * pair + 1 if interleaved else base + pair + n_pairs
                var a = x[i0]
                var b = x[i1]
                out[i0] = a * cv - b * sv
                out[i1] = a * sv + b * cv

    return RopeApplied(out^, n_tok, n_heads, head_dim, ATTN_OK)


fn rope_apply_flat(
    x: List[Float64], cos_t: List[Float64], sin_t: List[Float64],
    n_tok: Int, n_heads: Int, head_dim: Int, pos: List[Int], interleaved: Bool
) -> RopeApplied:
    """Rotate `x` in place-equivalent form. Layout is `[token][head][dim]`, row-major.

    `pos` is per token rather than implicit, which is what makes packed sequences work: a packed
    batch restarts positions at each document boundary, and a kernel that assumed `pos == t` would
    rotate the second document as if it continued the first.

    @capability rope_apply_flat
    complexity: O(n_tok * n_heads * head_dim)
    counts:
    - n_tok <= len(pos) [enforced]
    - dim head_dim <= ATTN_MAX_HEAD_DIM [kernel_validated]
    @endcapability
    """
    return _rope_apply(x, cos_t, sin_t, n_tok, n_heads, head_dim, pos, interleaved, False)


fn rope_apply_inverse_flat(
    x: List[Float64], cos_t: List[Float64], sin_t: List[Float64],
    n_tok: Int, n_heads: Int, head_dim: Int, pos: List[Int], interleaved: Bool
) -> RopeApplied:
    """The exact inverse rotation — negate the angle.

    Exported so the test can assert a round trip rather than compare against numbers typed by hand.
    A rotation is orthogonal, so `inverse(apply(x))` must return `x` to floating-point tolerance for
    every layout, position and head count; that single property catches a wrong pairing, a wrong sign
    and a wrong table index at once, which per-element expected values would not.

    @capability rope_apply_inverse_flat
    complexity: O(n_tok * n_heads * head_dim)
    counts:
    - n_tok <= len(pos) [enforced]
    - dim head_dim <= ATTN_MAX_HEAD_DIM [kernel_validated]
    @endcapability
    """
    return _rope_apply(x, cos_t, sin_t, n_tok, n_heads, head_dim, pos, interleaved, True)
