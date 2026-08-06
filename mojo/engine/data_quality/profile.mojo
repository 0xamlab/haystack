"""
data_quality.profile — the null / NaN / zero census. Zero Python imports.

The one distinction this module exists to keep
---------------------------------------------
NULL, NaN and 0.0 are three different facts, and a profile that merges any two of them is
wrong in the way that matters most for data quality:

  * NULL is "the value is not there". It travels in the presence mask, never as a value,
    because a sentinel value has to steal a real number out of the domain to work.
  * NaN is "the value is there and is not a number". It is a value, it arrived, and it
    tells you a computation upstream went wrong — which is a completely different repair
    from a missing field.
  * 0.0 is a number. A column of 100 zeros and a column of 100 nulls have the same sum and
    nothing else in common.

`ColumnProfile` therefore counts `n_null`, `n_nan`, `n_pos_inf`, `n_neg_inf`, `n_zero`,
`n_negative` and `n_positive` as separate integers, and every one of them is a real answer
(a count of nothing is 0). Every STATISTIC, by contrast, carries a `has_*` flag, because a
mean, spread, extremum or median of nothing does not exist — `numeric.contract` is the
policy and this module follows it. No value slot ever holds a raw non-finite: when a
`has_*` flag is False the slot is 0.0 and the flag is the answer.

What is frozen here and what is not
-----------------------------------
EXISTING-FROZEN, called:

  * `numeric.reduce.reduce_mean` (Welford), `reduce_stddev`, `reduce_min`, `reduce_max` —
    every statistic below one of them. This module computes no mean of its own.
  * `stats.median` — O(n log n) through `fast_sort`. `numeric.reduce.reduce_median` sorts
    with insertion sort, which is O(n^2) and would turn a large valid profile into a hang;
    the two agree by construction (both take the mean of the middle pair for an even
    count) and the suite asserts that on a hand-checked case rather than assuming it.
  * `columnar.hash_index.HashIndex` — the distinct count, O(n) expected on the normalized
    bit pattern. An insertion-sort dedup (what `engines/column_profiler` does) is O(n^2).
  * `validate.check_monotonic` — the ordering fact, for a column that is supposed to be a
    sorted key or a timestamp.

SURFACE-GAP made reachable: `engines/column_profiler.run_column_profile` is the tree's
only profiler and it is under `engines/`, excluded from the runtime contract. It also has
no concept of a null — its input is a JSON array and `_extract_float_array` skips a `null`
token silently, so a column that is 90% missing profiles as a dense column of whatever
remained. It stays frozen and untouched; nothing here calls it, because a profile that
starts from parsed JSON cannot separate "absent" from "unparseable".

GENUINELY-MISSING, written here: the census itself, the `has_*` discipline, and the
whole-table pass that names all-absent and constant columns.

Frozen failure values this module turns into absences
----------------------------------------------------
`stats.median` funnels through `quantile`, which returns 0.0 for an empty finite set — so
"the median is zero" and "there is no median" are the same return value. `math_ext.stdev`
and `math_ext.correlation` do the same. Every one of those is guarded here by checking the
live count FIRST and setting `has_median` / `has_stddev` rather than reading the number.

Status codes: profile owns 410-419 of the package's 400-449. It returns 410 and the
contract-range codes; the vocabulary is `contract.dq_status_name`.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, bool
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_data_quality_profile.mojo
benchmark: benchmarks/mojo_benchmarks/bench_data_quality.mojo
docs: gitbook/engine/data-quality.md
version_introduced: 0.1.0
deprecation_state: active
@endcapability
"""
from std.math import isinf, isnan

from columnar.hash_index import HashIndex
from numeric.reduce import reduce_max, reduce_mean, reduce_min, reduce_stddev
from stats import median as stats_median
from validate import check_monotonic

from data_quality.contract import (
    DQ_ERR_COLUMN_INDEX,
    DQ_ERR_LENGTH_MISMATCH,
    DQ_OK,
    dq_column,
    dq_column_mask,
    dq_live_and_finite,
    dq_mask_defect,
    dq_status_name,
    dq_table_defect,
)

# ── status codes: profile owns 410-419 ────────────────────────────────────────
comptime DQ_PROFILE_ERR_NO_COLUMNS: Int = 410

# Live-and-finite values below which an ORDER does not exist. Two, because monotonicity is
# a relation between a value and its predecessor and one value has no predecessor. The
# frozen `check_monotonic` returns 1 for a sequence of length 0 or 1 — vacuously true for
# both directions — and reporting that as "strictly increasing" is an answer about nothing.
comptime DQ_MONOTONIC_MIN_VALUES: Int = 2


struct ColumnProfile(Copyable, Movable):
    """One column's hygiene facts. Counts are answers; statistics carry `has_*`.

    `n_rows == n_null + n_present` and `n_present == n_nan + n_pos_inf + n_neg_inf +
    n_finite` always hold, and the suite asserts both — a census whose parts do not sum to
    the whole is two mutually exclusive claims in one returned value.

    `monotonic_direction` is an Int and it is flag-paired too, for the same reason every
    Float64 here is. An ORDER is a relation between at least two values, so
    `has_monotonic_direction` is True only when the column has at least
    `DQ_MONOTONIC_MIN_VALUES` live-and-finite values, and the slot is 0 otherwise. Without
    the flag, 0 conflated {no data, all-NaN, constant, genuinely out of order} and 1
    conflated {strictly increasing, exactly one value} — the frozen `validate.check_monotonic`
    answers 1 for a sequence of length 0 or 1, which is correct for it (both directions hold
    vacuously) and useless as a reported ordering fact. With the flag, the two remaining
    readings of a 0 are separable inside this same struct: `n_distinct_finite == 1` is
    constant, and anything more is genuinely out of order.
    """

    var status: Int
    var n_rows: Int
    var n_present: Int
    var n_null: Int
    var n_nan: Int
    var n_pos_inf: Int
    var n_neg_inf: Int
    var n_finite: Int
    var n_zero: Int
    var n_negative: Int
    var n_positive: Int
    var n_distinct_finite: Int
    var has_null_fraction: Bool
    var null_fraction: Float64
    var has_mean: Bool
    var mean: Float64
    var has_stddev: Bool
    var stddev: Float64
    var has_min: Bool
    var min_value: Float64
    var has_max: Bool
    var max_value: Float64
    var has_median: Bool
    var median_value: Float64
    var has_monotonic_direction: Bool
    var monotonic_direction: Int

    def __init__(out self, status: Int, n_rows: Int):
        self.status = status
        self.n_rows = n_rows
        self.n_present = 0
        self.n_null = 0
        self.n_nan = 0
        self.n_pos_inf = 0
        self.n_neg_inf = 0
        self.n_finite = 0
        self.n_zero = 0
        self.n_negative = 0
        self.n_positive = 0
        self.n_distinct_finite = 0
        self.has_null_fraction = False
        self.null_fraction = 0.0
        self.has_mean = False
        self.mean = 0.0
        self.has_stddev = False
        self.stddev = 0.0
        self.has_min = False
        self.min_value = 0.0
        self.has_max = False
        self.max_value = 0.0
        self.has_median = False
        self.median_value = 0.0
        self.has_monotonic_direction = False
        self.monotonic_direction = 0


struct TableProfile(Copyable, Movable):
    """Per-column hygiene counts for a whole table, plus the two lists that matter.

    Parallel lists indexed by column: a caller reads `null_counts[c]` for column `c`.
    `all_absent_columns` and `constant_columns` are the two findings a reader acts on
    first, so they are extracted rather than left to be derived.
    """

    var status: Int
    var n_rows: Int
    var n_cols: Int
    var null_counts: List[Int]
    var nan_counts: List[Int]
    var infinite_counts: List[Int]
    var zero_counts: List[Int]
    var finite_counts: List[Int]
    var distinct_counts: List[Int]
    var all_absent_columns: List[Int]
    var constant_columns: List[Int]

    def __init__(out self, status: Int, n_rows: Int, n_cols: Int):
        self.status = status
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.null_counts = List[Int]()
        self.nan_counts = List[Int]()
        self.infinite_counts = List[Int]()
        self.zero_counts = List[Int]()
        self.finite_counts = List[Int]()
        self.distinct_counts = List[Int]()
        self.all_absent_columns = List[Int]()
        self.constant_columns = List[Int]()


def profile_status_name(code: Int) -> String:
    """Name for a status this module can return. One vocabulary, in `contract`.

    @capability profile_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    return dq_status_name(code)


def _distinct_finite(values: List[Float64], live: List[Bool]) -> Int:
    """Distinct live-and-finite values, on the frozen normalized bit pattern.

    `HashIndex.get_or_assign` is handed `n` as the next slot and returns it only when the
    key was new, so the count is exact rather than a load-factor estimate.
    """
    var index = HashIndex()
    var n_distinct = 0
    var upto = len(values)
    if len(live) < upto:
        upto = len(live)
    for i in range(upto):
        if not live[i]:
            continue
        if index.get_or_assign(values[i], n_distinct) == n_distinct:
            n_distinct += 1
    return n_distinct


def _compact(values: List[Float64], live: List[Bool]) -> List[Float64]:
    """The live-and-finite values, densely. `stats.median` needs a dense list."""
    var out = List[Float64]()
    var upto = len(values)
    if len(live) < upto:
        upto = len(live)
    for i in range(upto):
        if live[i]:
            out.append(values[i])
    return out^


def profile_column(
    values: List[Float64], null_mask: List[Bool], n_rows: Int
) raises -> ColumnProfile:
    """Profile one column. `null_mask[i] == True` means row `i` is PRESENT.

    The order of operations is the whole design:

      1. refuse a mask that does not describe exactly `n_rows` positions, and refuse a
         `n_rows` that is not exactly `len(values)`. A count the caller supplied is never
         trusted: `for i in range(n)` past `len(values)` is an uncatchable process abort,
         not an exception, so `try`/`except` above it does not help.
      2. classify every row into exactly ONE of null / NaN / +inf / -inf / finite. The
         five counts sum to `n_rows` by construction.
      3. build the live-and-finite mask and hand it to the frozen reductions. A non-finite
         never reaches a sum, so no statistic can come back NaN — the non-finites are
         reported as counts instead.
      4. set `has_*` from the reduction's own `present` flag, never from a value test.

    A statistic that does not exist leaves its slot at 0.0 and its flag False. That is not
    cosmetic: a raw non-finite in a returned Float64 field makes the whole response a
    typed serialization error, so the flag has to be the answer.

    `monotonic_direction` follows the identical rule with an Int slot: absent below
    `DQ_MONOTONIC_MIN_VALUES` live-and-finite values, because an order between fewer than
    two values does not exist.

    @capability profile_column
    complexity: O(n_rows log n_rows)
    counts:
    - n_rows == len(values, null_mask) [kernel_validated]
    - dim n_rows [kernel_validated]
    @endcapability
    """
    var mask_defect = dq_mask_defect(null_mask, n_rows)
    if mask_defect != DQ_OK:
        return ColumnProfile(mask_defect, 0)
    if len(values) != n_rows:
        return ColumnProfile(DQ_ERR_LENGTH_MISMATCH, 0)

    var out = ColumnProfile(DQ_OK, n_rows)
    for i in range(n_rows):
        if not null_mask[i]:
            out.n_null += 1
            continue
        out.n_present += 1
        var v = values[i]
        if isnan(v):
            out.n_nan += 1
            continue
        if isinf(v):
            if v > 0.0:
                out.n_pos_inf += 1
            else:
                out.n_neg_inf += 1
            continue
        out.n_finite += 1
        if v == 0.0:
            out.n_zero += 1
        elif v < 0.0:
            out.n_negative += 1
        else:
            out.n_positive += 1

    if n_rows > 0:
        out.has_null_fraction = True
        out.null_fraction = Float64(out.n_null) / Float64(n_rows)

    var live = dq_live_and_finite(values, null_mask)
    out.n_distinct_finite = _distinct_finite(values, live)

    var mean_r = reduce_mean(values, live)
    out.has_mean = mean_r.present
    out.mean = mean_r.value if mean_r.present else 0.0

    var sd_r = reduce_stddev(values, live)
    out.has_stddev = sd_r.present
    out.stddev = sd_r.value if sd_r.present else 0.0

    var min_r = reduce_min(values, live)
    out.has_min = min_r.present
    out.min_value = min_r.value if min_r.present else 0.0

    var max_r = reduce_max(values, live)
    out.has_max = max_r.present
    out.max_value = max_r.value if max_r.present else 0.0

    var dense = _compact(values, live)
    if len(dense) > 0:
        out.has_median = True
        out.median_value = stats_median(dense, len(dense))
    if len(dense) >= DQ_MONOTONIC_MIN_VALUES:
        # `check_monotonic` reports 1 / -1 / 0 over the DENSE live values, so a null does
        # not break a run. That is a decision, not an accident: a timestamp column with a
        # gap is still ordered, and reporting 0 there would hide the ordering fact.
        #
        # Guarded at two values, NOT at one: the frozen kernel answers 1 for a length-0 or
        # length-1 sequence, and passing a single live value straight through published
        # "strictly increasing" as a fact about one point. Below the floor the direction is
        # ABSENT (flag False, slot 0) — there is no order to report, which is a different
        # statement from "not ordered".
        out.has_monotonic_direction = True
        out.monotonic_direction = check_monotonic(dense)
    return out^


def profile_column_at(
    table: List[Float64], n_rows: Int, n_cols: Int, col: Int, null_mask: List[Bool]
) raises -> ColumnProfile:
    """Profile column `col` of a row-major table whose mask has the same shape.

    `col` is a subscript, so it is refused in BOTH directions before any read: a negative
    index into a `List` is an uncatchable abort, while a negative loop count merely reads
    nothing.

    @capability profile_column_at
    complexity: O(n_rows log n_rows)
    counts:
    - n_rows * n_cols == len(table, null_mask) [kernel_validated]
    - dim col [kernel_validated]
    @endcapability
    """
    var defect = dq_table_defect(table, n_rows, n_cols)
    if defect != DQ_OK:
        return ColumnProfile(defect, 0)
    if len(null_mask) != len(table):
        return ColumnProfile(dq_mask_defect(null_mask, len(table)), 0)
    if col < 0 or col >= n_cols:
        return ColumnProfile(DQ_ERR_COLUMN_INDEX, 0)
    var column = dq_column(table, n_rows, n_cols, col)
    var column_mask = dq_column_mask(null_mask, n_rows, n_cols, col)
    return profile_column(column, column_mask, n_rows)


def profile_table(
    table: List[Float64], n_rows: Int, n_cols: Int, null_mask: List[Bool]
) raises -> TableProfile:
    """Per-column counts for a whole table, plus the all-absent and constant columns.

    Work is `n_rows * n_cols`, charged by `dq_table_defect` against the one budget. A
    table over the budget is REFUSED rather than partially profiled: unlike an expectation
    (where a checked prefix is a useful partial answer), a per-column count over a prefix
    is a different statistic wearing the same name, and a caller comparing `null_counts`
    across columns would be comparing counts over different row sets.

    A column is CONSTANT when it has exactly one distinct live-and-finite value. A column
    with none is reported all-absent, not constant: nothing is not one thing.

    @capability profile_table
    complexity: O(n_rows * n_cols)
    counts:
    - n_rows * n_cols == len(table, null_mask) [kernel_validated]
    - dim n_cols [kernel_validated]
    @endcapability
    """
    var defect = dq_table_defect(table, n_rows, n_cols)
    if defect != DQ_OK:
        return TableProfile(defect, 0, 0)
    if len(null_mask) != len(table):
        return TableProfile(dq_mask_defect(null_mask, len(table)), 0, 0)
    if n_cols == 0:
        return TableProfile(DQ_PROFILE_ERR_NO_COLUMNS, n_rows, 0)

    var out = TableProfile(DQ_OK, n_rows, n_cols)
    for c in range(n_cols):
        var p = profile_column_at(table, n_rows, n_cols, c, null_mask)
        out.null_counts.append(p.n_null)
        out.nan_counts.append(p.n_nan)
        out.infinite_counts.append(p.n_pos_inf + p.n_neg_inf)
        out.zero_counts.append(p.n_zero)
        out.finite_counts.append(p.n_finite)
        out.distinct_counts.append(p.n_distinct_finite)
        if p.n_present == 0:
            out.all_absent_columns.append(c)
        elif p.n_distinct_finite == 1:
            out.constant_columns.append(c)
    return out^


def profile_is_constant(
    values: List[Float64], null_mask: List[Bool], n_rows: Int
) -> Bool:
    """True when the column has exactly ONE distinct live-and-finite value.

    Delegates to the same `_distinct_finite` that fills `ColumnProfile.n_distinct_finite`,
    so this predicate and that count cannot disagree. A second implementation here — even
    an obviously equivalent early-exit loop — is how one declared property acquires two
    strengths (rule 3), and the weaker one is a bug even before it fires.

    Equality is therefore the frozen `columnar.hash_index` normalized bit pattern, not
    `==`: a column of `-0.0` and `+0.0` IS constant, because collapsing the two zeros is one
    of the two normalizations that index applies.

    The index's OTHER normalization — every NaN to one quiet NaN — never comes into play
    here, and saying it does was a docstring that contradicted the code. `dq_live_and_finite`
    strips non-finites BEFORE `_distinct_finite` sees them, so a column of NaNs has zero
    live-and-finite values and is NOT constant. Measured: `profile_is_constant([nan, nan,
    nan], all-present, 3)` is False.

    False when nothing is live: nothing is not one thing (rule 4). Also False on any shape
    defect — the profile functions return a status for that; a Bool cannot.

    @capability profile_is_constant
    complexity: O(n_rows)
    counts:
    - n_rows == len(values, null_mask) [kernel_validated]
    - dim n_rows [kernel_validated]
    @endcapability
    """
    if dq_mask_defect(null_mask, n_rows) != DQ_OK or len(values) != n_rows:
        return False
    return _distinct_finite(values, dq_live_and_finite(values, null_mask)) == 1
