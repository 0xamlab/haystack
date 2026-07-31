"""
gemm.contract — the one status vocabulary, dimension check and work budget for `gemm`. Zero Python.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_gemm_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_tensorx_and_gemm.mojo
docs: none
version_introduced: 0.1.0
deprecation_state: active
@endcapability

Status range
------------
`gemm` owns **320-339**, after `tensorx` 300-319. One vocabulary per package (rule 4e): a logged
status must not mean two things depending on which module produced it.

Finiteness comes from `tensorx`, not from a second copy
---------------------------------------------------------
`tx_finite` is imported rather than redeclared. `optimization/` grew six byte-identical private
`_finite` helpers, none of which could be imported by the others, and the copies then drifted — a
duplicated guard reads as defence in depth while providing one arbitrary behaviour per call site.

Two ceilings, because they bound different things
---------------------------------------------------
`GEMM_MAX_DIM_ELEMS` bounds any single buffer. `GEMM_MAX_FLOP_CELLS` bounds `m * n * k`, which is a
different quantity and the one that actually runs away: three dimensions can each be far inside the
element ceiling while their product is not reachable this decade. Rule 1c states the general form —
a budget that charges one factor of a product is not a budget — and a GEMM is the cleanest example of
it in the tree.

Both are checked by division. `rows * cols` is a wrapping 64-bit multiply, and
`3 * 6148914691236517206 == 2` is how a product guard was walked past in `sparse_numerics` and
aborted the worker; the same shape generalises to three factors here.

The element ceiling is scaled down, deliberately
--------------------------------------------------
A dense GEMM holds A, B and C live at once, so the per-object budget is divided by three rather than
applied three times. Rule 1c: a driver allocating k arrays of a bounded length is bounded at
k x that length, not at it.

Public API:
  gemm_status_name(code)                      — the status vocabulary
  gemm_backend_name(code)                     — which kernel ran, for the result envelope
  gemm_work_fits(m, n, k, ceiling)            — division-based m*n*k bound, no wrapping product
  gemm_dims_check(m, n, k, len_a, len_b)      — shapes agree with the buffers, exactly
"""

from tensorx.contract import TX_MAX_ELEMS, tx_finite

# ── status codes: gemm owns 320-339 ───────────────────────────────────────────

comptime GEMM_OK: Int = 320
comptime GEMM_ERR_EMPTY_DIM: Int = 321
comptime GEMM_ERR_A_LENGTH: Int = 322
comptime GEMM_ERR_B_LENGTH: Int = 323
comptime GEMM_ERR_DIM_TOO_LARGE: Int = 324
comptime GEMM_ERR_WORK_TOO_LARGE: Int = 325
comptime GEMM_ERR_NON_FINITE_SCALAR: Int = 326
comptime GEMM_ERR_SCALE_LENGTH: Int = 327
comptime GEMM_ERR_BLOCK_SIZE: Int = 328
comptime GEMM_ERR_CODE_OUT_OF_RANGE: Int = 329

# ── backend tags, carried on every result ─────────────────────────────────────
# `device_used` and `kernel_variant` are a product requirement, not diagnostics: a benchmark that
# cannot say which kernel ran is not evidence, and "no silent fallback" is unverifiable if the
# result does not say what executed.

comptime GEMM_BACKEND_SCALAR: Int = 0
comptime GEMM_BACKEND_CPU_SIMD: Int = 1
comptime GEMM_BACKEND_METAL: Int = 2
comptime GEMM_BACKEND_CUDA: Int = 3
comptime GEMM_BACKEND_ROCM: Int = 4

comptime GEMM_MAX_DIM_ELEMS: Int = 22369621
"""Per-buffer element bound: `TX_MAX_ELEMS // 3` == `(1 << 26) // 3`, because A, B and C are all live
for the duration of the call (rule 1c: k arrays of a bounded length are bounded at k x that length).

Written as a literal rather than as the expression, because a `dim ... <= NAME` capability relation
must name a same-file `comptime <NAME>: Int` the manifest parser can evaluate, and it understands
literals and `1 << N` but not a division. `test_gemm_contract.mojo` asserts this equals
`TX_MAX_ELEMS // 3`, so the two cannot drift apart silently."""

comptime GEMM_MAX_FLOP_CELLS: Int = 1 << 36
"""Bound on `m * n * k`.

2^36 multiply-accumulates is a few seconds of scalar CPU work — large enough that no legitimate
reference call hits it, small enough that a caller who fat-fingers a dimension gets an error instead
of a hang. A hang is indistinguishable from the uncatchable abort in rule 1 from the client side, so
the work budget exists for the same reason the length guards do."""


fn gemm_status_name(code: Int) -> String:
    """Name a status code. An unknown code says so rather than borrowing a neighbour's meaning."""
    if code == GEMM_OK:
        return String("ok")
    if code == GEMM_ERR_EMPTY_DIM:
        return String("empty_dimension")
    if code == GEMM_ERR_A_LENGTH:
        return String("a_length_mismatch")
    if code == GEMM_ERR_B_LENGTH:
        return String("b_length_mismatch")
    if code == GEMM_ERR_DIM_TOO_LARGE:
        return String("dimension_too_large")
    if code == GEMM_ERR_WORK_TOO_LARGE:
        return String("work_budget_exceeded")
    if code == GEMM_ERR_NON_FINITE_SCALAR:
        return String("non_finite_scalar")
    if code == GEMM_ERR_SCALE_LENGTH:
        return String("scale_length_mismatch")
    if code == GEMM_ERR_BLOCK_SIZE:
        return String("invalid_block_size")
    if code == GEMM_ERR_CODE_OUT_OF_RANGE:
        return String("code_out_of_range")
    return String("unknown_status")


fn gemm_backend_name(code: Int) -> String:
    """Name a backend tag, for the `kernel_variant` field of a result envelope."""
    if code == GEMM_BACKEND_SCALAR:
        return String("cpu_scalar")
    if code == GEMM_BACKEND_CPU_SIMD:
        return String("cpu_simd")
    if code == GEMM_BACKEND_METAL:
        return String("metal")
    if code == GEMM_BACKEND_CUDA:
        return String("cuda")
    if code == GEMM_BACKEND_ROCM:
        return String("rocm")
    return String("unknown_backend")


fn gemm_work_fits(m: Int, n: Int, k: Int, ceiling: Int) -> Bool:
    """True when `m * n * k` fits in `ceiling`, computed WITHOUT forming the product.

    Grows the bound by division one factor at a time, so no oversized product is ever materialized
    and a wrapping multiply cannot produce a small number from three large ones.

    @capability gemm_work_fits
    complexity: O(1)
    counts:
    - dim m <= GEMM_MAX_DIM_ELEMS [kernel_validated]
    - dim n <= GEMM_MAX_DIM_ELEMS [kernel_validated]
    - dim k <= GEMM_MAX_DIM_ELEMS [kernel_validated]
    @endcapability
    """
    if m <= 0 or n <= 0 or k <= 0 or ceiling <= 0:
        return False
    if m > ceiling:
        return False
    var remaining = ceiling // m
    if n > remaining:
        return False
    remaining = remaining // n
    return k <= remaining


fn gemm_dims_check(m: Int, n: Int, k: Int, len_a: Int, len_b: Int) -> Int:
    """Validate a GEMM's shapes against its real buffer lengths. Exact equality, both operands.

    Transposition does not change either count — A holds `m * k` values whether it is read as m-by-k
    or k-by-m — so one check serves both orientations.

    Exact, not `>=`: a buffer longer than its declared shape means the caller and the kernel disagree
    about what the data is, and quietly using a prefix returns a confident answer for a different
    matrix. That is the failure mode this whole check exists for; an out-of-bounds read at least
    announces itself by killing the process.

    @capability gemm_dims_check
    complexity: O(1)
    counts:
    - dim m <= GEMM_MAX_DIM_ELEMS [kernel_validated]
    - dim n <= GEMM_MAX_DIM_ELEMS [kernel_validated]
    - dim k <= GEMM_MAX_DIM_ELEMS [kernel_validated]
    @endcapability
    """
    if m <= 0 or n <= 0 or k <= 0:
        return GEMM_ERR_EMPTY_DIM
    if m > GEMM_MAX_DIM_ELEMS or n > GEMM_MAX_DIM_ELEMS or k > GEMM_MAX_DIM_ELEMS:
        return GEMM_ERR_DIM_TOO_LARGE
    # Each operand's own element count must fit a single buffer before its product is considered.
    if not gemm_work_fits(m, k, 1, GEMM_MAX_DIM_ELEMS):
        return GEMM_ERR_DIM_TOO_LARGE
    if not gemm_work_fits(k, n, 1, GEMM_MAX_DIM_ELEMS):
        return GEMM_ERR_DIM_TOO_LARGE
    if not gemm_work_fits(m, n, k, GEMM_MAX_FLOP_CELLS):
        return GEMM_ERR_WORK_TOO_LARGE
    if len_a != m * k:
        return GEMM_ERR_A_LENGTH
    if len_b != k * n:
        return GEMM_ERR_B_LENGTH
    return GEMM_OK


fn gemm_scalars_ok(alpha: Float64, beta: Float64) -> Bool:
    """True when both scaling factors are finite.

    Checked before any tolerance or accumulation is built from them: a NaN alpha makes every output
    NaN, and a NaN in a later comparison makes every `>` False, so an audit passes having counted
    zero violations (rule 4d).
    """
    return tx_finite(alpha) and tx_finite(beta)
