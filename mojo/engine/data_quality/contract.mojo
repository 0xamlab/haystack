"""
data_quality.contract — the package's one vocabulary. Zero Python imports.

Everything in this file exists once so nothing in the package carries a second copy
(rule 3 applies inside a package: `optimization/` shipped `_finite` six times, and one
declared invariant enforced at three strengths under three status codes).

What is defined here, and why exactly here
------------------------------------------
* the status codes, 400-449, sub-allocated per module
* the ceilings and the single WORK budget every driver charges against
* `dq_is_finite`, which is the frozen `numeric.reduce.is_finite_value` and not a
  reimplementation of it
* `dq_relative_tolerance` and `dq_ulp_tolerance` — the ONLY two tolerance builders. Both
  take the magnitude of the ONE quantity being judged. Neither takes a sum or a maximum
  over other items, neither has a `1 +` floor, and neither multiplies the caller's
  tolerance by a magnitude (rule 4b, all four spellings)
* `dq_values_equal` — the package's stated float equality, delegated to the frozen
  `columnar.hash_index.normalize_bits`
* `dq_quantize` / `dq_quantize_exact` — the declared decimal grid, for a caller who
  needs measured floats compared at a stated precision
* `dq_column` / `dq_column_prefix` and their mask companions — the guarded row-major
  column extractors. Every driver goes through one of them, so there is one place where an
  out-of-range column index cannot become an out-of-range read, and one place where a
  budget-truncated pass gets a column the size of the prefix it charged for

The decimal grid, and the frozen rounder it is NOT
--------------------------------------------------
`currency.round_currency` is the tree's existing decimal rounder and it uses the identical
repeated-multiply scale build plus `floor(x * 10^d + 0.5) / 10^d`. `dq_quantize` is written
new anyway, and the reason is a difference in the ANSWER, not a difference in style:
`round_currency` is half-toward-`+inf` (`round_currency(-0.5, 0) == 0.0`) while a grid used
as a hash KEY has to be sign-symmetric, so `dq_quantize(-0.5, 0) == -1.0`, half-away-from-
zero. `round_currency` additionally has no `decimals` range guard and no representability
guard, so `round_currency(1e300, 15)` returns a number computed from an overflowed
intermediate. Calling it here would have been the wrong answer twice over; naming it is the
prior-art citation this classification owes the reader.

Shape validation is a DIVISION, not a multiply
----------------------------------------------
`dq_table_defect` calls the frozen `sparse_numerics.csr.dims_fit`. `n_rows * n_cols` is a
wrapping 64-bit multiply — `3 * 6148914691236517206 == 2` — so a product comparison is
not a bound at all, and `dims_fit` is the frozen kernel that already got this right.

A mask must be exactly as long as the data
------------------------------------------
`dq_mask_defect` REFUSES `len(null_mask) != n_rows`. The frozen convention
(`numeric.reduce._is_live`, `columnar.array.float64_with_nulls`) reads a position with no
mask entry as ABSENT, which is the right conservative default for a reduction. For a
profile whose entire job is null accounting it is the wrong default: a caller who forgot
the mask would be told the column is 100% null, which is a confident wrong answer rather
than a refusal. A caller with no nulls says so explicitly with `dq_mask_all_valid`.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_data_quality_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_data_quality.mojo
docs: gitbook/engine/data-quality.md
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, floor

from columnar.hash_index import normalize_bits
from numeric.reduce import all_valid, is_finite_value
from sparse_numerics.csr import dims_fit

# ── status codes: data_quality owns 400-449 ───────────────────────────────────
# contract 400-409 · profile 410-419 · expect 420-429 · leakage 430-439 ·
# duplicates 440-449. Recorded here and in each module so the next author picks from
# what is left rather than colliding the way optimization.integer and
# optimization.explain both claimed 80-84.

comptime DQ_OK: Int = 0
comptime DQ_ERR_NEGATIVE_SHAPE: Int = 400
comptime DQ_ERR_TABLE_SHAPE: Int = 401
comptime DQ_ERR_ROWS_TOO_LARGE: Int = 402
comptime DQ_ERR_COLS_TOO_LARGE: Int = 403
comptime DQ_ERR_WORK_BUDGET: Int = 404
comptime DQ_ERR_MASK_LENGTH: Int = 405
comptime DQ_ERR_COLUMN_INDEX: Int = 406
comptime DQ_ERR_LENGTH_MISMATCH: Int = 407
comptime DQ_ERR_DECIMALS: Int = 408
comptime DQ_ERR_NOT_QUANTIZABLE: Int = 409

# ── ceilings ─────────────────────────────────────────────────────────────────
# Rule 1c: a per-item ceiling is not a bound on total allocation, so each number below
# is justified by counting the arrays a driver allocates PER UNIT of that dimension.
#
# DQ_MAX_ROWS (2^22 = 4,194,304). The row-indexed arrays a single call may hold:
#   profile     — one Bool live-mask (1 B/row) plus one HashIndex entry per distinct
#                 value (16 B/row worst case)     -> ~71 MB
#   duplicates  — group_of_row (8 B/row) plus a CompositeKeyIndex whose key_store is
#                 n_key_cols Float64 per group    -> charged against DQ_MAX_WORK
#   expect      — query.eval allocates one List[Float64] AND one List[Bool] per plan
#                 NODE across all rows, i.e. 9 B per (node, row) -> charged as work
# so rows alone is not the binding constraint; the products are, which is why every
# driver charges its product against DQ_MAX_WORK as well.
comptime DQ_MAX_ROWS: Int = 1 << 22

# DQ_MAX_COLS (2^12 = 4096). A table is materialised column by column, never all at
# once, so the ceiling here only has to keep `n_cols` well inside the range where
# `n_rows * n_cols` is checkable; the memory is bounded by the work budget.
comptime DQ_MAX_COLS: Int = 1 << 12

# DQ_MAX_WORK (2^22 = 4,194,304). ONE budget for every product that drives cost:
#   n_rows * n_cols        a table's cells
#   n_nodes * rows         an expectation evaluation (9 B each -> 38 MB at the ceiling)
#   n_expect * rows        a suite
#   n_rows * n_key_cols    a duplicate scan's key store (8 B each -> 34 MB)
# Bounding memory is not bounding work and vice versa, so this is charged as WORK: a
# driver that exceeds it either refuses (a duplicate scan cannot be partial and still be
# correct) or checks a prefix and reports the remainder (an expectation can).
comptime DQ_MAX_WORK: Int = 1 << 22

# Detail rows a report may carry. 4096 * ~40 B = 164 KB, and the caller learns it was
# capped from `reports_truncated` rather than seeing a short list and guessing.
comptime DQ_MAX_REPORTS: Int = 4096

# Nodes in a caller-supplied expectation plan. query.eval allocates two lists per node,
# so this multiplies into the work budget rather than standing alone.
comptime DQ_MAX_NODES: Int = 1 << 10

# Expectations in one suite, and key columns in one duplicate key.
comptime DQ_MAX_EXPECTATIONS: Int = 256
comptime DQ_MAX_KEY_COLS: Int = 64

# ── numeric constants ────────────────────────────────────────────────────────
# 2^-52, the spacing of Float64 at 1.0. The only multiplier a relative tolerance in this
# package is built from.
comptime DQ_DBL_EPSILON: Float64 = 2.220446049250313e-16

# 2^53. Above this Float64 no longer represents every integer, so a decimal grid cannot
# be applied without changing the value it is supposed to preserve. `Float64(Int(v))`
# past `Int`'s range is undefined rather than truncated (rule 4c), so the guard is on the
# SCALED magnitude and the rounding is `std.math.floor`, which is total over every finite
# Float64.
comptime DQ_INT_GRID_MAX: Float64 = 9.007199254740992e15

# Decimal places a declared grid may ask for. 10^15 is the largest power of ten that is
# exactly representable and still leaves headroom under DQ_INT_GRID_MAX.
comptime DQ_MAX_DECIMALS: Int = 15


fn dq_status_name(code: Int) -> String:
    """Name for any status code this package can return.

    One vocabulary for all five modules: a caller that logs a bare integer must be able
    to resolve it without knowing which module produced it.

    @capability dq_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if code == DQ_OK:
        return "ok"
    if code == DQ_ERR_NEGATIVE_SHAPE:
        return "negative_shape"
    if code == DQ_ERR_TABLE_SHAPE:
        return "table_shape_does_not_match_cell_count"
    if code == DQ_ERR_ROWS_TOO_LARGE:
        return "rows_exceed_ceiling"
    if code == DQ_ERR_COLS_TOO_LARGE:
        return "columns_exceed_ceiling"
    if code == DQ_ERR_WORK_BUDGET:
        return "work_budget_exceeded"
    if code == DQ_ERR_MASK_LENGTH:
        return "null_mask_length_is_not_row_count"
    if code == DQ_ERR_COLUMN_INDEX:
        return "column_index_out_of_range"
    if code == DQ_ERR_LENGTH_MISMATCH:
        return "parallel_lists_have_different_lengths"
    if code == DQ_ERR_DECIMALS:
        return "decimal_grid_out_of_range"
    if code == DQ_ERR_NOT_QUANTIZABLE:
        return "value_cannot_be_placed_on_the_declared_grid"
    if code >= 410 and code <= 419:
        return _profile_status_text(code)
    if code >= 420 and code <= 429:
        return _expect_status_text(code)
    if code >= 430 and code <= 439:
        return _leakage_status_text(code)
    if code >= 440 and code <= 449:
        return _duplicates_status_text(code)
    return "unknown_status_" + String(code)


fn _profile_status_text(code: Int) -> String:
    if code == 410:
        return "no_columns_to_profile"
    return "unknown_profile_status_" + String(code)


fn _expect_status_text(code: Int) -> String:
    if code == 420:
        return "unknown_expectation_op"
    if code == 421:
        return "expectation_bound_is_not_finite"
    if code == 422:
        return "request_contains_no_expectation_to_check"
    if code == 423:
        return "plan_node_arrays_disagree"
    if code == 424:
        return "plan_root_out_of_range"
    if code == 425:
        return "plan_uses_an_op_the_columnar_evaluator_cannot_run"
    if code == 426:
        return "plan_is_structurally_invalid"
    if code == 427:
        return "plan_evaluation_refused_a_masked_case"
    if code == 428:
        return "plan_exceeds_the_node_ceiling"
    if code == 429:
        return "suite_exceeds_the_expectation_ceiling"
    return "unknown_expect_status_" + String(code)


fn _leakage_status_text(code: Int) -> String:
    if code == 430:
        return "no_leakage_signal"
    if code == 431:
        return "suspicious_not_proven"
    if code == 432:
        return "proven_feature_is_the_target"
    if code == 433:
        return "proven_feature_is_an_affine_image_of_the_target"
    if code == 434:
        return "too_few_comparable_rows_to_decide"
    if code == 435:
        return "proven_feature_observed_after_the_target_event"
    if code == 436:
        return "correlation_threshold_out_of_range"
    return "unknown_leakage_status_" + String(code)


fn _duplicates_status_text(code: Int) -> String:
    if code == 440:
        return "no_key_columns_given"
    if code == 441:
        return "too_many_key_columns"
    if code == 442:
        return "duplicate_key_column_listed_twice"
    return "unknown_duplicates_status_" + String(code)


fn dq_is_finite(value: Float64) -> Bool:
    """True for a finite Float64. Delegates to the frozen `numeric.reduce`.

    Not reimplemented: this package and every reduction it calls must agree on what
    "finite" means, and two definitions one import apart is how `_is_live` and
    `float64_with_nulls` once disagreed about what a short mask meant.

    @capability dq_is_finite
    complexity: O(1)
    counts: none
    @endcapability
    """
    return is_finite_value(value)


fn dq_relative_tolerance(magnitude: Float64, absolute_tol: Float64) -> Float64:
    """`|absolute_tol| + DBL_EPSILON * |magnitude|`, where `magnitude` is THE quantity
    being judged.

    The four wrong spellings, all of which have shipped in this tree: a sum over other
    items, a maximum or norm over other items, `1 + |x|` whose 1.0 floor silently makes a
    "relative" test absolute, and `caller_tol * magnitude` which sizes the relative term
    by the caller's number instead of by DBL_EPSILON. This function admits neither an
    aggregate nor a floor, and the caller's tolerance is strictly ADDITIVE.

    A non-finite magnitude yields the caller's absolute tolerance alone: a `nan`
    threshold makes every `error > tol` comparison False, so an audit built on one passes
    having counted zero violations.

    @capability dq_relative_tolerance
    complexity: O(1)
    counts: none
    @endcapability
    """
    var absolute = fabs(absolute_tol) if is_finite_value(absolute_tol) else 0.0
    if not is_finite_value(magnitude):
        return absolute
    return absolute + DQ_DBL_EPSILON * fabs(magnitude)


fn dq_ulp_tolerance(magnitude: Float64, ulps: Int) -> Float64:
    """`ulps * DBL_EPSILON * |magnitude|` — a few-ulp slack on ONE item's own magnitude.

    For a comparison against a value that took several arithmetic operations to compute,
    where one epsilon is too tight and any aggregate would be wrong. `ulps` is clamped to
    [0, 64]: a negative count would produce a negative tolerance, which accepts nothing,
    and an unbounded one is not a tolerance.

    @capability dq_ulp_tolerance
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not is_finite_value(magnitude):
        return 0.0
    var count = ulps
    if count < 0:
        count = 0
    if count > 64:
        count = 64
    return Float64(count) * DQ_DBL_EPSILON * fabs(magnitude)


fn dq_values_equal(a: Float64, b: Float64) -> Bool:
    """The package's stated float equality: identical normalized IEEE-754 bit patterns.

    Delegates to the frozen `columnar.hash_index.normalize_bits`, so two consequences are
    inherited rather than invented:

      * `-0.0` equals `+0.0`. They compare equal under `==` but differ in bits, and a
        key that split them would group two rows differently depending on how the number
        was produced.
      * every NaN equals every other NaN. `NaN != NaN` under `==`, so a bit-pattern key
        would otherwise create one group per NaN row and never find any of them again.

    This is an equivalence relation, which is what a hash key requires.
    `abs(a - b) < tol` is not one — it is not transitive — so it cannot key a table and
    is not used anywhere in this package for identity.

    @capability dq_values_equal
    complexity: O(1)
    counts: none
    @endcapability
    """
    return normalize_bits(a) == normalize_bits(b)


fn dq_decimal_scale(decimals: Int) -> Float64:
    """`10^decimals` for `decimals` in [0, DQ_MAX_DECIMALS], else 0.0.

    Built by repeated multiplication of exactly-representable powers of ten rather than
    `pow`, so the scale is bit-identical on every platform. 0.0 is returned for an
    out-of-range request and every caller treats it as a refusal, never as a scale.

    @capability dq_decimal_scale
    complexity: O(decimals)
    counts:
    - dim decimals <= DQ_MAX_DECIMALS [kernel_validated]
    @endcapability
    """
    if decimals < 0 or decimals > DQ_MAX_DECIMALS:
        return 0.0
    var scale: Float64 = 1.0
    for _ in range(decimals):
        scale *= 10.0
    return scale


fn dq_quantize_exact(value: Float64, decimals: Int) -> Bool:
    """Whether `value` can be placed on the `decimals`-place grid without invention.

    False when `decimals` is out of range, when `value` is not finite, or when
    `value * 10^decimals` leaves the range where Float64 represents every integer. In
    that last case rounding would return an arbitrary neighbour rather than the value's
    grid point, so the caller must be told instead of handed a number.

    @capability dq_quantize_exact
    complexity: O(decimals)
    counts:
    - dim decimals <= DQ_MAX_DECIMALS [kernel_validated]
    @endcapability
    """
    var scale = dq_decimal_scale(decimals)
    if scale <= 0.0:
        return False
    if not is_finite_value(value):
        return False
    var scaled = value * scale
    if not is_finite_value(scaled):
        return False
    return fabs(scaled) <= DQ_INT_GRID_MAX


fn dq_quantize(value: Float64, decimals: Int) -> Float64:
    """`value` rounded to `decimals` places, half away from zero.

    Returns `value` UNCHANGED when `dq_quantize_exact` is False, so this function never
    manufactures a number; the caller checks `dq_quantize_exact` first and returns
    `DQ_ERR_NOT_QUANTIZABLE` rather than grouping on an unrounded value it declared
    rounded.

    Rounding is `floor(x + 0.5)` for x >= 0 and `-floor(-x + 0.5)` for x < 0, both built
    from `std.math.floor`, which is total over every finite Float64. `Float64(Int(v))` is
    NOT used: `fptosi` outside `Int`'s range is undefined, and a `_finite` guard does not
    catch it because 1e300 is perfectly finite.

    @capability dq_quantize
    complexity: O(decimals)
    counts:
    - dim decimals <= DQ_MAX_DECIMALS [kernel_validated]
    @endcapability
    """
    if not dq_quantize_exact(value, decimals):
        return value
    var scale = dq_decimal_scale(decimals)
    var scaled = value * scale
    var rounded = floor(scaled + 0.5) if scaled >= 0.0 else -floor(-scaled + 0.5)
    return rounded / scale


fn dq_table_defect(table: List[Float64], n_rows: Int, n_cols: Int) -> Int:
    """`DQ_OK` when `n_rows` x `n_cols` is a sound row-major shape for `table`.

    Order matters: the ceilings are checked BEFORE the shape, so a caller cannot get a
    "shape ok" verdict for a table whose declared dimensions would then be used to size
    an allocation. `dims_fit` does the product check by division.

    @capability dq_table_defect
    complexity: O(1)
    counts:
    - n_rows * n_cols == len(table) [kernel_validated]
    - dim n_rows <= DQ_MAX_ROWS [kernel_validated]
    - dim n_cols <= DQ_MAX_COLS [kernel_validated]
    @endcapability
    """
    if n_rows < 0 or n_cols < 0:
        return DQ_ERR_NEGATIVE_SHAPE
    if n_rows > DQ_MAX_ROWS:
        return DQ_ERR_ROWS_TOO_LARGE
    if n_cols > DQ_MAX_COLS:
        return DQ_ERR_COLS_TOO_LARGE
    if not dq_work_fits(n_rows, n_cols):
        return DQ_ERR_WORK_BUDGET
    if not dims_fit(n_rows, n_cols, len(table)):
        return DQ_ERR_TABLE_SHAPE
    return DQ_OK


fn dq_work_fits(a: Int, b: Int) -> Bool:
    """True when `a * b <= DQ_MAX_WORK`, decided WITHOUT forming the product.

    `a * b` wraps at 64 bits, so a comparison against the budget is not a bound: with
    `a = 3` and `b = 6148914691236517206` the product is 2 and every budget check passes.
    Division cannot wrap.

    @capability dq_work_fits
    complexity: O(1)
    counts: none
    @endcapability
    """
    if a < 0 or b < 0:
        return False
    if a == 0 or b == 0:
        return True
    return a <= DQ_MAX_WORK // b


fn dq_rows_within_budget(n_rows: Int, unit_cost: Int) -> Int:
    """Rows of `n_rows` a driver may examine at `unit_cost` work units per row.

    `min(n_rows, DQ_MAX_WORK // unit_cost)`, and 0 for a non-positive `unit_cost` or a
    non-positive `n_rows`. The remainder is what a report must declare as NOT CHECKED: a
    driver that silently sampled would report a clean table for data it never read, which
    is a wrong answer rather than a partial one.

    WHAT THIS FUNCTION DOES NOT CHECK, now stated correctly. The relation below is `[clamped]`
    and it used to say `n_rows <= DQ_MAX_ROWS [kernel_validated]` — a claim to a check that
    is not in this body and never was. `n_rows` is CLAMPED by the budget, not validated
    against the row ceiling: `dq_rows_within_budget(DQ_MAX_ROWS + 1, 1)` answers
    `DQ_MAX_WORK`, not 0. That is deliberate and it is why the label rather than the body was
    corrected — this is pure budget arithmetic, the sibling of `dq_work_fits`, and the ROW
    CEILING is a different question owned by `dq_table_defect` and `dq_mask_defect`, which
    every driver calls first and which refuse with `DQ_ERR_ROWS_TOO_LARGE`. Answering a
    budget question with a ceiling refusal would make one declared invariant enforced at two
    strengths in two places. The return is an Int that is never used as a subscript and is
    bounded by `DQ_MAX_WORK` regardless of `n_rows`, so nothing downstream depends on the
    ceiling being re-checked here.

    @capability dq_rows_within_budget
    complexity: O(1)
    counts:
    - dim n_rows [clamped]
    @endcapability
    """
    if n_rows <= 0 or unit_cost <= 0:
        return 0
    var allowed = DQ_MAX_WORK // unit_cost
    return n_rows if n_rows < allowed else allowed


fn dq_mask_defect(null_mask: List[Bool], n_rows: Int) -> Int:
    """`DQ_OK` when `null_mask` describes exactly `n_rows` positions.

    `True` means the value at that position is PRESENT. A shorter or longer mask is
    refused rather than padded — see the module docstring for why padding is the wrong
    default here even though it is the right one for a reduction.

    @capability dq_mask_defect
    complexity: O(1)
    counts:
    - n_rows == len(null_mask) [kernel_validated]
    - dim n_rows <= DQ_MAX_ROWS [kernel_validated]
    @endcapability
    """
    if n_rows < 0:
        return DQ_ERR_NEGATIVE_SHAPE
    if n_rows > DQ_MAX_ROWS:
        return DQ_ERR_ROWS_TOO_LARGE
    if len(null_mask) != n_rows:
        return DQ_ERR_MASK_LENGTH
    return DQ_OK


fn dq_mask_all_valid(n_rows: Int) -> List[Bool]:
    """A mask marking every one of `n_rows` positions present — how a caller with no
    nulls says so.

    The frozen `numeric.reduce.all_valid` does the work; the ceiling guard is the
    addition, because an unbounded `n_rows` here is an allocation request with no payload
    behind it at all.

    @capability dq_mask_all_valid
    complexity: O(n_rows)
    counts:
    - dim n_rows <= DQ_MAX_ROWS [kernel_validated]
    @endcapability
    """
    if n_rows <= 0 or n_rows > DQ_MAX_ROWS:
        return List[Bool]()
    return all_valid(n_rows)


fn dq_column(table: List[Float64], n_rows: Int, n_cols: Int, col: Int) -> List[Float64]:
    """Column `col` of a row-major `table`, or an EMPTY list on any defect.

    The single place in this package that indexes a table, so the bounds argument is made
    once. `col` is a subscript, so it is guarded in BOTH directions: `range(-3)` reads
    nothing and is harmless, but `table[-1]` is an uncatchable process abort.

    Empty rather than a raise so a driver can convert the defect into a status field; the
    callers all check `dq_table_defect` first and never rely on the empty result.

    @capability dq_column
    complexity: O(n_rows)
    counts:
    - n_rows * n_cols == len(table) [kernel_validated]
    - dim col <= DQ_MAX_COLS [kernel_validated]
    @endcapability
    """
    var out = List[Float64]()
    if dq_table_defect(table, n_rows, n_cols) != DQ_OK:
        return out^
    if col < 0 or col >= n_cols:
        return out^
    for r in range(n_rows):
        out.append(table[r * n_cols + col])
    return out^


fn dq_column_mask(
    null_mask: List[Bool], n_rows: Int, n_cols: Int, col: Int
) -> List[Bool]:
    """The presence mask for column `col` of a row-major table mask, or EMPTY on defect.

    A table mask is the same row-major shape as the table: position `r * n_cols + c`.
    Guarded exactly like `dq_column`, and `len(null_mask)` is checked against the product
    by division for the same wrapping reason.

    @capability dq_column_mask
    complexity: O(n_rows)
    counts:
    - n_rows * n_cols == len(null_mask) [kernel_validated]
    - dim col <= DQ_MAX_COLS [kernel_validated]
    @endcapability
    """
    var out = List[Bool]()
    if n_rows < 0 or n_cols < 0 or n_rows > DQ_MAX_ROWS or n_cols > DQ_MAX_COLS:
        return out^
    if not dq_work_fits(n_rows, n_cols):
        return out^
    if not dims_fit(n_rows, n_cols, len(null_mask)):
        return out^
    if col < 0 or col >= n_cols:
        return out^
    for r in range(n_rows):
        out.append(null_mask[r * n_cols + col])
    return out^


fn dq_column_prefix(
    table: List[Float64], n_rows: Int, n_cols: Int, col: Int, rows: Int
) -> List[Float64]:
    """The FIRST `rows` entries of column `col`, or an EMPTY list on any defect.

    Exists because bounding memory is not bounding work. A driver that truncates to a row
    PREFIX to stay inside `DQ_MAX_WORK` and then extracts the FULL column per expectation
    pays `k * n_rows` for a request it charged `k * rows` — measured at the 4,194,304-cell
    ceiling, a 256-expectation suite examining 5,461 rows spent 29x the wall time of a
    single expectation examining 1,398,101 rows, at an identical declared cost. Extracting
    only the prefix makes the loop cost what the budget charges for it.

    `rows` is a COUNT of leading positions, so it is clamped to `[0, n_rows]` rather than
    refused; `col` is a SUBSCRIPT, so it is refused in both directions. `r * n_cols + col`
    cannot wrap for `r < rows <= n_rows`, because `dq_table_defect` has already bounded
    `n_rows * n_cols` by division against `DQ_MAX_WORK`.

    @capability dq_column_prefix
    complexity: O(rows)
    counts:
    - n_rows * n_cols == len(table) [kernel_validated]
    - dim col <= DQ_MAX_COLS [kernel_validated]
    - dim rows [clamped]
    @endcapability
    """
    var out = List[Float64]()
    if dq_table_defect(table, n_rows, n_cols) != DQ_OK:
        return out^
    if col < 0 or col >= n_cols:
        return out^
    var upto = rows
    if upto < 0:
        upto = 0
    if upto > n_rows:
        upto = n_rows
    for r in range(upto):
        out.append(table[r * n_cols + col])
    return out^


fn dq_column_mask_prefix(
    null_mask: List[Bool], n_rows: Int, n_cols: Int, col: Int, rows: Int
) -> List[Bool]:
    """The FIRST `rows` presence bits of column `col`, or an EMPTY list on any defect.

    The mask companion to `dq_column_prefix`, guarded identically and for the same reason:
    a truncated pass that extracted the full mask would pay the full price for it. The
    length agreement is checked against the product by DIVISION, never by forming it.

    @capability dq_column_mask_prefix
    complexity: O(rows)
    counts:
    - n_rows * n_cols == len(null_mask) [kernel_validated]
    - dim col <= DQ_MAX_COLS [kernel_validated]
    - dim rows [clamped]
    @endcapability
    """
    var out = List[Bool]()
    if n_rows < 0 or n_cols < 0 or n_rows > DQ_MAX_ROWS or n_cols > DQ_MAX_COLS:
        return out^
    if not dq_work_fits(n_rows, n_cols):
        return out^
    if not dims_fit(n_rows, n_cols, len(null_mask)):
        return out^
    if col < 0 or col >= n_cols:
        return out^
    var upto = rows
    if upto < 0:
        upto = 0
    if upto > n_rows:
        upto = n_rows
    for r in range(upto):
        out.append(null_mask[r * n_cols + col])
    return out^


fn dq_live_and_finite(values: List[Float64], null_mask: List[Bool]) -> List[Bool]:
    """A mask marking positions that are PRESENT and FINITE.

    This is the mask every statistic in this package is computed over, and building it is
    the point: `numeric.reduce` rejects a non-finite on ingest by design, so handing it a
    presence-only mask would surface a NaN where a figure belongs. Excluding non-finites
    HERE keeps the count of them (`ColumnProfile.n_nan`, `n_pos_inf`, `n_neg_inf`) as a
    reported fact rather than a poisoned mean.

    Shorter of the two lengths wins, so neither list is read past its end. Callers
    validate the lengths first and get a status; this function cannot abort either way.

    @capability dq_live_and_finite
    complexity: O(n)
    counts: none
    @endcapability
    """
    var n = len(values)
    if len(null_mask) < n:
        n = len(null_mask)
    var out = List[Bool]()
    for i in range(n):
        out.append(null_mask[i] and is_finite_value(values[i]))
    return out^
