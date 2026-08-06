"""
normk.contract — the one status vocabulary and work budget for normalization kernels. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_normk_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_normk.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Status range
------------
`normk` owns **380-389**, after `tensorx` 300-319, `gemm` 320-339 and `attnk` 360-379 (rule 4e).
Finiteness comes from `tensorx.contract.tx_finite`, not a fifth private copy.

Normalization is the cheapest layer and the one most able to poison a whole model
-----------------------------------------------------------------------------------
A norm is `O(rows * cols)` — next to attention's `O(s^2)` it is free. What makes it worth its own
contract is that it sits on the residual stream: every token passes through one before every block,
so a wrong `eps`, a row length that does not match the weight vector, or a variance computed over the
wrong axis does not produce a crash. It produces a model that trains and is quietly worse. Those are
exactly the conditions this file refuses.

Why `eps` is validated rather than clamped
--------------------------------------------
`eps` is not a tuning knob a kernel may improve on. A checkpoint trained with `1e-6` and served with
`1e-5` gives different logits, and the difference survives every downstream check because both values
are reasonable. So a non-finite or negative `eps` is an error, and a *valid* one is used exactly as
given — never floored, never substituted.

Public API:
  norm_status_name(code)                        — the status vocabulary
  norm_dims_check(n_rows, n_cols, eps)          — shape agreement and a usable epsilon
  norm_work_fits(n_rows, n_cols, ceiling)       — no wrapping product
"""

from tensorx.contract import tx_finite

# ── status codes: normk owns 380-389 ──────────────────────────────────────────

comptime NORM_OK: Int = 380
comptime NORM_ERR_EMPTY_DIM: Int = 381
comptime NORM_ERR_LENGTH_MISMATCH: Int = 382
comptime NORM_ERR_DIM_TOO_LARGE: Int = 383
comptime NORM_ERR_WORK_TOO_LARGE: Int = 384
comptime NORM_ERR_NON_FINITE_SCALAR: Int = 385
comptime NORM_ERR_BAD_EPS: Int = 386
comptime NORM_ERR_HEAD_MISMATCH: Int = 387

comptime NORM_MAX_COLS: Int = 1 << 20
"""Longest normalized row — the hidden or per-head dimension.

Qwen3-8B is 4096 hidden and 128 per head; 2^20 is far above any of it. The point is not the headroom,
it is that a caller who passes a byte count or a flattened total where a row width belongs gets an
error instead of a reduction over the wrong axis, which is invisible in the output shape."""

comptime NORM_MAX_ROWS: Int = 1 << 24
"""Rows in one call: tokens times batch. 2^24 is ~16.7M tokens, past any single step."""

comptime NORM_MAX_WORK_CELLS: Int = 1 << 34
"""Bound on `n_rows * n_cols`. High enough that no real layer reaches it, low enough that a
transposed pair of dimensions returns an error rather than running long enough to look like a hang —
which from a caller's side is indistinguishable from rule 1's uncatchable abort."""


def norm_status_name(code: Int) -> String:
    """Name a status code. Unknown codes say so rather than borrowing a neighbour's meaning."""
    if code == NORM_OK:
        return String("ok")
    if code == NORM_ERR_EMPTY_DIM:
        return String("empty_dimension")
    if code == NORM_ERR_LENGTH_MISMATCH:
        return String("length_mismatch")
    if code == NORM_ERR_DIM_TOO_LARGE:
        return String("dimension_too_large")
    if code == NORM_ERR_WORK_TOO_LARGE:
        return String("work_budget_exceeded")
    if code == NORM_ERR_NON_FINITE_SCALAR:
        return String("non_finite_scalar")
    if code == NORM_ERR_BAD_EPS:
        return String("bad_epsilon")
    if code == NORM_ERR_HEAD_MISMATCH:
        return String("head_count_mismatch")
    return String("unknown_status")


def norm_work_fits(n_rows: Int, n_cols: Int, ceiling: Int) -> Bool:
    """True when `n_rows * n_cols` fits in `ceiling`, computed WITHOUT forming the product.

    Grown by division, one factor at a time. A wrapping 64-bit multiply is how a product guard was
    walked past in `sparse_numerics` and aborted the worker; the same shape of guard is used here for
    the same reason, even though two factors are fewer than attention's five.

    @capability norm_work_fits
    complexity: O(1)
    counts:
    - dim n_rows <= NORM_MAX_ROWS [kernel_validated]
    - dim n_cols <= NORM_MAX_COLS [kernel_validated]
    @endcapability
    """
    if n_rows <= 0 or n_cols <= 0 or ceiling <= 0:
        return False
    if n_rows > NORM_MAX_ROWS or n_cols > NORM_MAX_COLS:
        return False
    if n_rows > ceiling:
        return False
    return n_cols <= ceiling // n_rows


def norm_eps_ok(eps: Float64) -> Bool:
    """True when `eps` is finite and non-negative.

    Zero is allowed: it is the mathematically correct choice for a row that is known non-zero, and
    refusing it would force a caller to invent a value the checkpoint did not train with. A negative
    `eps` is refused because it can drive `variance + eps` below zero and make `sqrt` return NaN for
    perfectly ordinary input — a failure that appears far from its cause.
    """
    return tx_finite(eps) and eps >= 0.0


def norm_dims_check(n_rows: Int, n_cols: Int, eps: Float64) -> Int:
    """Validate a `[n_rows][n_cols]` normalization request and its epsilon.

    @capability norm_dims_check
    complexity: O(1)
    counts:
    - dim n_rows <= NORM_MAX_ROWS [kernel_validated]
    - dim n_cols <= NORM_MAX_COLS [kernel_validated]
    @endcapability
    """
    if n_rows <= 0 or n_cols <= 0:
        return NORM_ERR_EMPTY_DIM
    if n_rows > NORM_MAX_ROWS or n_cols > NORM_MAX_COLS:
        return NORM_ERR_DIM_TOO_LARGE
    if not norm_eps_ok(eps):
        return NORM_ERR_BAD_EPS
    if not norm_work_fits(n_rows, n_cols, NORM_MAX_WORK_CELLS):
        return NORM_ERR_WORK_TOO_LARGE
    return NORM_OK


def norm_tol_for(magnitude: Float64, n_cols: Int) -> Float64:
    """Tolerance for comparing two spellings of a normalized value of size `magnitude`.

    Rule 4b: the tolerance scales with the quantity being judged AND with the reduction that produced
    it. A norm sums `n_cols` squares before it divides, so its rounding error grows with the row
    width — a fixed 1e-12 that passes at 128 columns is a false negative at 16384. The `1.0 +` floor
    keeps a value that legitimately normalizes to near zero from being held to an impossible bound.
    """
    var width = Float64(n_cols) if n_cols > 0 else 1.0
    var mag = magnitude if magnitude >= 0.0 else -magnitude
    return 1.0e-14 * (1.0 + mag) * (1.0 + width)
