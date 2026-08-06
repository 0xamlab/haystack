"""
streaming.contract — the package's single vocabulary. Zero Python imports.

Everything in `streaming/` reaches its status codes, its ceilings, its definition of
"finite", its tolerance builder, its work budget and its KEYED HASH through THIS file.
One vocabulary per package, because the alternative has already been measured in this
tree: two files in one package independently numbered their statuses and the same integer
named two different defects, so a logged code could not be disambiguated.

STATUS CODE RANGE: 360-379, all twenty allocated below, and this package uses no other
range. 300-319 is forecasting, 320-339 is inference/gemm, 340-359 is causal_inference,
200-219 is determinism/retrieval; 360-379 was unclaimed.

What a sketch IS, and what makes one worth having
-------------------------------------------------
A sketch answers a question about a stream in less space than the stream. Three properties
decide whether it is worth having, and this package treats all three as claims to be
checked rather than folklore to be repeated:

1. **Mergeability.** `merge(a, b)` must be the sketch of the concatenated stream. For the
   distinct-count and frequency sketches here that holds EXACTLY -- register-wise maximum
   and cell-wise addition are both associative and commutative, so the merged sketch is
   bit-identical to the one-pass sketch and the suite asserts it with `==`, never a
   tolerance. For the quantile sketch it holds only within the sketch's stated rank error,
   because compaction is lossy; that bound is a named function (`stm_kll_rank_error`) and
   the suite measures the actual error against an exact sort and asserts it falls inside.

2. **A bound that was measured, not quoted.** `stm_hll_relative_error`,
   `stm_cms_epsilon`, `stm_cms_delta` and `stm_kll_rank_error` return the CLAIM. The
   hand-written suite and the benchmark compute the exact answer over a real distribution
   and assert the observed error sits inside the claim. A bound nobody checked is a guess
   with a citation.

3. **Determinism.** Every hash and every compaction coin in this package comes from
   `determinism.counter_rng.philox_word` at explicit coordinates, seeded by the caller.
   `random_float64` appears nowhere: the frozen `reservoir.reservoir_sample` draws from
   process-global randomness and therefore cannot be replayed, which is precisely why a
   keyed lane is added beside it rather than the frozen one being called.

Why the keyed hash exists — a MEASURED defect in an unkeyed one
---------------------------------------------------------------
The frozen `sketch.create_cms` seeds row `d` with `d * 1000003 + 7`, and the frozen
`sketch.cms_hash(item, seed, width)` reduces `item * seed + 17` modulo 1000003 before
modulo `width`. Every one of those seeds is congruent to 7 modulo 1000003, so in the
no-overflow regime EVERY ROW COMPUTES THE SAME COLUMN. Measured on this tree:

    cms_hash(5, 7, 100) == cms_hash(5, 1000010, 100) == cms_hash(5, 2000013, 100) == 52

and over the first 20,000 non-negative items at width 4096, all four rows of a depth-4
sketch agree on 20,000 of 20,000. A Count-Min sketch's `depth` exists to make the failure
probability `e^-depth`; with identical rows the minimum is taken over one number and depth
buys nothing. The same modulus makes items 0, 1000003 and 2000006 collide in every row, so
adding 1000 copies of item 0 makes `cms_query(2000006)` return 1000 for an item that was
never added -- a 1000-count error where `e/4096 * 1000 = 0.66` was claimed.

That defect is in the HASH SCHEDULE, not in the counter table, and the frozen file is
immutable. So `stm_key_bucket` keeps the frozen `cms_hash` as the final column reduction
and supplies it a DIFFERENT keyed word per row, drawn from `philox_word`. The rows are then
independent because their inputs are independent, whatever the row seed does. The frozen
kernel is called, not replaced, and the part that was broken is the part that is new.

`cms_hash` also returns `(val % 1000003) % width`, so a width above 1000003 has columns
that are never reachable: at width 2,000,000 the highest column seen over 50,000 items was
350,010. `MAX_STM_WIDTH` is 16384 for that reason -- comfortably inside the modulus, with a
residual non-uniformity of at most `width / 1000003` = 1.6% that `stm_cms_epsilon` folds
into the claim instead of ignoring.

Reads past a List end are UNCATCHABLE
-------------------------------------
`try/except` does not contain an out-of-bounds `List` read; it kills the worker process and
every dataset resident in it. Two rules follow, and both are declared per function in the
`counts:` blocks rather than left to a reader:

  * A redundant count parameter is validated with `n < 0 or n > len(v)` before anything is
    indexed, and the function returns a typed absent result. Every such relation in this
    package is `[kernel_validated]`, and every one of them is a real `if` -- declaring
    `[kernel_validated]` tells the SDK guard to stand down, so declaring it without writing
    the check is worse than declaring nothing.
  * A negative COUNT is harmless (`for i in range(-3)` reads nothing) but a negative INDEX
    is fatal (`a[-1]` aborts). Any parameter used as a subscript -- `row` and `col` in
    `frequency.frequency_cell`, `position` in `windows.window_at` -- is guarded in BOTH
    directions, not just against the upper end.

Bounding memory is not bounding work
------------------------------------
A ceiling on a sketch's size says nothing about how long filling it takes. `stm_work_fits`
is the division-based budget check used to charge the PRODUCT: ingesting `n` items into a
depth-`d` frequency sketch is `n * d` hash-and-increment steps, and a windowed standard
deviation over `n` positions of width `w` is `n * w` element visits because the frozen
`timeseries_stats.rolling_std` recomputes each window. Both are charged as products. The
division form is not a stylistic preference: `3 * 6148914691236517206 == 2` in wrapping
64-bit arithmetic, so a guard written as `n * d > budget` is not a guard.
`sparse_numerics.csr.dims_fit` is the frozen version of the same idea for exact shapes and
is called directly by `stm_cells_fit`.

Non-finite results and absence
------------------------------
JSON has no NaN and no infinity, and the dispatch refuses a non-finite rather than
serialising it -- so one non-finite field makes the WHOLE response a typed error. Every
result struct in this package therefore pairs a value slot with a `present` flag, and when
`present` is False the value slot holds 0.0, which is representable and means nothing. The
flag is the answer. This is also why a quantile of an empty sketch is ABSENT rather than
0.0: "no data" and "the answer is zero" are different facts, and returning the second for
the first is the silent-wrong-answer this tree keeps paying for.

Tolerance
---------
`stm_tolerance(quantity, abs_tol)` is `abs_tol + STM_TOL_SLACK * STM_DBL_EPSILON *
|quantity|`, where `quantity` is THE ONE NUMBER BEING JUDGED. Not `1 + |quantity|` (that is
an absolute allowance of one whole unit at small scale), not a sum or a maximum over other
items (that lets many ordinary items swallow one contradiction), and the relative
multiplier is `STM_DBL_EPSILON` and never the caller's `abs_tol`.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: true
seed_requirements: required
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_streaming_contract.mojo
benchmark: benchmarks/mojo_benchmarks/bench_streaming.mojo
docs: gitbook/engine/streaming-sketches.md
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs, exp, isinf, isnan, sqrt

from determinism.counter_rng import philox_word
from sketch import cms_hash
from sparse_numerics.csr import dims_fit

# ── status codes: 360-379, this package's entire allocation ────────────────────

comptime STM_OK: Int = 360
comptime STM_EMPTY: Int = 361
comptime STM_ERR_NON_FINITE: Int = 362
comptime STM_ERR_COUNT: Int = 363
comptime STM_ERR_PRECISION: Int = 364
comptime STM_ERR_WIDTH: Int = 365
comptime STM_ERR_DEPTH: Int = 366
comptime STM_ERR_CAPACITY: Int = 367
comptime STM_ERR_SEED_RANGE: Int = 368
comptime STM_ERR_WORK_BUDGET: Int = 369
comptime STM_ERR_MEMORY_BUDGET: Int = 370
comptime STM_ERR_SNAPSHOT_SHAPE: Int = 371
comptime STM_ERR_INCOMPATIBLE_MERGE: Int = 372
comptime STM_ERR_INVALID_SKETCH: Int = 373
comptime STM_ERR_QUANTILE_RANGE: Int = 374
comptime STM_ERR_WINDOW: Int = 375
comptime STM_ERR_INDEX_RANGE: Int = 376
comptime STM_ERR_PARAM_RANGE: Int = 377
comptime STM_ERR_LEVEL_OVERFLOW: Int = 378
comptime STM_ERR_ITEM_BUDGET: Int = 379

# ── ceilings, with the allocation arithmetic stated ───────────────────────────
#
# Each ceiling is a `comptime NAME: Int` so a `dim x <= NAME` declaration can NAME the
# constant the kernel tests against instead of copying its value and rotting.

#: Items ingested by one call. 16,777,216 Float64 inputs is a ~134 MB payload, which is
#: already past what a request should carry; the point of the ceiling is that the work
#: charge below is then a bounded number rather than an unbounded one.
comptime MAX_STM_ITEMS: Int = 1 << 24

#: HyperLogLog register-index bits. 4 -> 16 registers (relative error 26%, still useful as
#: a smoke value), 16 -> 65,536 registers (0.41%). Above 16 the frozen `hll_add` runs out
#: of usable mantissa: it works in a 31-bit hash, and `31 - p` remaining bits at p = 17
#: leaves 14 bits of leading-zero runway, which caps the reachable register value and
#: silently biases the estimate low.
comptime MIN_STM_PRECISION: Int = 4
comptime MAX_STM_PRECISION: Int = 16

#: Count-Min columns. Bounded well below the frozen `cms_hash` modulus of 1000003 so that
#: every column is reachable and the modulo bias stays under width/1000003 = 1.6%.
comptime MAX_STM_WIDTH: Int = 1 << 14

#: Count-Min rows. delta = e^-16 = 1.1e-7 is already past the point where more rows buy
#: anything measurable, and each row multiplies the per-item work.
comptime MAX_STM_DEPTH: Int = 16

#: Count-Min cells. Checked with `dims_fit`, so `depth * width` is never formed as a
#: wrapping product.
comptime MAX_STM_CELLS: Int = 1 << 18

#: KLL level capacity. Rank error scales as 1/k, so k = 4096 is a 0.2% claim; k must be
#: even because a compaction promotes exactly half a full level.
comptime MIN_STM_K: Int = 4
comptime MAX_STM_K: Int = 1 << 12

#: KLL levels. Level i carries weight 2^i and the top level holds about k items, so
#: 2^levels * k bounds the representable stream length; 40 levels at k = 4 is 4.4e12
#: items, far past MAX_STM_ITEMS. The ceiling exists so a corrupted snapshot cannot ask
#: for an unbounded allocation.
comptime MAX_STM_LEVELS: Int = 40

#: Elementary steps one call may perform. Charged as a PRODUCT via `stm_work_fits`.
comptime MAX_STM_WORK: Int = 1 << 27

#: Windowed-aggregate window width.
comptime MAX_STM_WINDOW: Int = 1 << 16

#: Seeds are `Int` so they survive a JSON round trip without losing precision; 2^53 is the
#: largest integer a IEEE-754 double represents exactly, and a JSON number is a double.
comptime MAX_STM_SEED: Int = 1 << 53

# ── hashing coordinates ───────────────────────────────────────────────────────
#
# `philox_word(master_seed, scenario_id, replication_id, dim0, dim1, stream_id, draw_index)`
# is the frozen counter-based generator. This package fixes scenario/stream and varies
# `dim1` (the row or level) and `draw_index` (the item or the compaction index), so a hash
# is a pure function of (seed, row, item) with no hidden state and no call ordering.

#: ASCII "STREAM" with a version tail, so a future coordinate change is a visible constant
#: change rather than a silent re-keying of everybody's stored sketches.
comptime STM_SCENARIO: UInt64 = 0x53545245414D0001

#: `determinism.streams.stream_id("algenta.streaming")`. Copied as a constant because
#: `stream_id` hashes a String and this sits in a per-item loop; the hand-written suite
#: asserts the constant still equals the frozen derivation, so it cannot rot silently.
comptime STM_STREAM: UInt64 = 9982

#: Compaction coins live on a different row axis from item hashes, so a coin can never
#: alias an item hash at the same coordinates.
comptime STM_COIN_ROW_BASE: Int = 1 << 20

# ── numeric constants ─────────────────────────────────────────────────────────

comptime STM_DBL_EPSILON: Float64 = 2.220446049250313e-16
comptime STM_TOL_SLACK: Float64 = 64.0

#: The frozen `cms_hash` modulus. Named because two claims depend on it: reachable column
#: count and modulo bias.
comptime STM_CMS_MODULUS: Int = 1000003

#: Euler's number, the constant in the Count-Min additive bound eps = e/width.
comptime STM_E: Float64 = 2.718281828459045

#: HyperLogLog's standard relative standard error constant: sigma_rel = 1.04 / sqrt(m).
comptime STM_HLL_SIGMA: Float64 = 1.04

#: KLL rank-error constant, DERIVED rather than tuned. Every compaction at level i shifts a
#: query's estimated rank by at most 2^i, with mean zero because the offset is a fair coin,
#: and the shifts are independent across compactions. Level i is compacted about
#: n / (2^i * k) times, so the variance is sum_i 4^i * n / (2^i * k) = (n/k) * sum_i 2^i,
#: and with a top level of weight 2^H ~ n/k that sums to about 2 (n/k)^2 -- a standard
#: deviation of about 1.41 n/k. 8.0 is a 5.7-sigma allowance, which also covers the union
#: bound over the ~100 quantiles the suite probes simultaneously. It is not a fudge factor:
#: raising it to make a failing measurement pass would be a behaviour change.
comptime STM_KLL_C: Float64 = 8.0


# ── status names ──────────────────────────────────────────────────────────────


def stm_status_name(code: Int) -> String:
    """Name for a status code, so a refusal surfaces the defect and not a bare number.

    @capability stm_status_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if code == STM_OK:
        return "ok"
    if code == STM_EMPTY:
        return "no_observations_so_no_answer_exists"
    if code == STM_ERR_NON_FINITE:
        return "non_finite_input"
    if code == STM_ERR_COUNT:
        return "count_outside_input_length"
    if code == STM_ERR_PRECISION:
        return "hll_precision_out_of_range"
    if code == STM_ERR_WIDTH:
        return "sketch_width_out_of_range"
    if code == STM_ERR_DEPTH:
        return "sketch_depth_out_of_range"
    if code == STM_ERR_CAPACITY:
        return "quantile_capacity_out_of_range"
    if code == STM_ERR_SEED_RANGE:
        return "seed_out_of_range"
    if code == STM_ERR_WORK_BUDGET:
        return "work_budget_exceeded"
    if code == STM_ERR_MEMORY_BUDGET:
        return "memory_budget_exceeded"
    if code == STM_ERR_SNAPSHOT_SHAPE:
        return "snapshot_shape_inconsistent"
    if code == STM_ERR_INCOMPATIBLE_MERGE:
        return "sketch_parameters_differ_so_merge_is_undefined"
    if code == STM_ERR_INVALID_SKETCH:
        return "input_sketch_is_not_valid"
    if code == STM_ERR_QUANTILE_RANGE:
        return "quantile_outside_unit_interval"
    if code == STM_ERR_WINDOW:
        return "window_out_of_range"
    if code == STM_ERR_INDEX_RANGE:
        return "index_out_of_range"
    if code == STM_ERR_PARAM_RANGE:
        return "parameter_out_of_range"
    if code == STM_ERR_LEVEL_OVERFLOW:
        return "sketch_levels_exceeded"
    if code == STM_ERR_ITEM_BUDGET:
        return "item_count_exceeds_ceiling"
    return "unknown_status"


def stm_version() -> String:
    """Identity of the hashing and compaction rules. Deterministic, zero-argument.

    Two sketches whose `stm_version` agrees were built by the same rules and may be merged;
    a change to the coordinates in `stm_key_word`, to `STM_SCENARIO`, or to the compaction
    rule is a change to this string. Stored snapshots name it.

    @capability stm_version
    complexity: O(1)
    counts: none
    @endcapability
    """
    return "streaming/1.0.0 philox4x64-10 scenario=0x53545245414D0001 stream=9982"


# ── finiteness, tolerance ─────────────────────────────────────────────────────


def stm_finite(x: Float64) -> Bool:
    """True when `x` is a real number a JSON response can carry.

    @capability stm_finite
    complexity: O(1)
    counts: none
    @endcapability
    """
    return not (isnan(x) or isinf(x))


def stm_tolerance(quantity: Float64, abs_tol: Float64) -> Float64:
    """Rounding allowance for judging ONE number: `abs_tol + slack * eps * |quantity|`.

    `quantity` is the number being judged and nothing else -- never a sum or a maximum over
    other items, never `1 + |quantity|`, and the relative multiplier is `STM_DBL_EPSILON`
    rather than `abs_tol`.

    @capability stm_tolerance
    complexity: O(1)
    counts: none
    @endcapability
    """
    var base = abs_tol if abs_tol > 0.0 else 0.0
    if not stm_finite(quantity):
        return base
    return base + STM_TOL_SLACK * STM_DBL_EPSILON * fabs(quantity)


# ── budgets: division, never a wrapping product ───────────────────────────────


def stm_work_fits(units: Int, per_unit: Int, budget: Int) -> Bool:
    """True when `units * per_unit <= budget`, decided WITHOUT forming the product.

    A guard written as `units * per_unit > budget` is not a guard: the multiply wraps, and
    `3 * 6148914691236517206 == 2` in this tree. `sparse_numerics.csr.dims_fit` is the
    frozen precedent for the shape; this is the inequality form of it.

    Zero units or zero work per unit is zero work, which fits any non-negative budget.

    @capability stm_work_fits
    complexity: O(1)
    counts: none
    @endcapability
    """
    if units < 0 or per_unit < 0 or budget < 0:
        return False
    if units == 0 or per_unit == 0:
        return True
    return units <= budget // per_unit


def stm_cells_fit(depth: Int, width: Int, length: Int) -> Bool:
    """True when `depth` rows of `width` columns are exactly `length` cells.

    Delegates to the frozen `sparse_numerics.csr.dims_fit`, which is the tree's one
    division-based shape check, and then applies this package's own cell ceiling.

    @capability stm_cells_fit
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not dims_fit(depth, width, length):
        return False
    return length <= MAX_STM_CELLS


def stm_seed_ok(seed: Int) -> Bool:
    """True when `seed` survives a JSON round trip exactly, so a replay reproduces.

    @capability stm_seed_ok
    complexity: O(1)
    counts: none
    @endcapability
    """
    return seed >= 0 and seed <= MAX_STM_SEED


def stm_items_ok(n: Int) -> Bool:
    """True when `n` observations are inside the per-call item ceiling.

    @capability stm_items_ok
    complexity: O(1)
    counts: none
    @endcapability
    """
    return n >= 0 and n <= MAX_STM_ITEMS


# ── the keyed hash ────────────────────────────────────────────────────────────


def stm_u64_of(value: Int) -> UInt64:
    """Two's-complement bit pattern of `value` as a UInt64, for negative values too.

    `UInt64(negative)` is the whole reason this exists: item identifiers arrive from a
    caller as `List[Int]` and may be negative, and a hash that only accepts non-negative
    inputs would either refuse ordinary data or fold `-5` onto `5`.

    @capability stm_u64_of
    complexity: O(1)
    counts: none
    @endcapability
    """
    if value >= 0:
        return UInt64(value)
    return ~UInt64(-(value + 1))


def stm_key_word(seed: Int, row: Int, item: Int) -> UInt64:
    """Keyed 64-bit hash of `item` on `row`, from the frozen Philox generator.

    Deterministic and reproducible: a pure function of the three arguments with no process
    state, so two runs -- and two machines -- produce identical sketches from identical
    input. `random_float64` is never reached from this package.

    `row` is folded into Philox's `dim1` coordinate and `item` into `draw_index`, so
    distinct rows are independent counters rather than the same counter re-seeded.

    @capability stm_key_word
    complexity: O(1)
    counts: none
    @endcapability
    """
    return philox_word(
        stm_u64_of(seed), STM_SCENARIO, 0, 0, stm_u64_of(row), STM_STREAM,
        stm_u64_of(item),
    )


def stm_key_hash31(seed: Int, row: Int, item: Int) -> Int:
    """Keyed hash reduced to a NON-NEGATIVE 31-bit `Int`.

    Non-negative matters twice over: the frozen `cms_hash` negates its intermediate when it
    goes negative, and negating the most negative Int64 overflows; and 31 bits is the width
    the frozen `sketch.hll_hash` mixer works in, so a value handed to `hll_add` stays inside
    the domain the frozen kernel was written for.

    @capability stm_key_hash31
    complexity: O(1)
    counts: none
    @endcapability
    """
    return Int(stm_key_word(seed, row, item) & 0x7FFFFFFF)


def stm_key_bucket(seed: Int, row: Int, item: Int, width: Int) -> Int:
    """Keyed column in `[0, width)` for `item` on `row`, or -1 when `width` is unusable.

    The frozen `sketch.cms_hash` performs the final reduction; what is added here is that
    its input is a per-ROW keyed word rather than the item itself. That is the whole fix:
    the frozen row seeds are all congruent to 7 modulo 1000003, so feeding the raw item
    makes every row compute the same column and `depth` stops meaning anything. Feeding
    independent keyed words makes the rows independent whatever the row seed does.

    Returns -1 rather than a column when `width` is outside range, so a caller that ignores
    the ceiling gets an unusable value instead of a silent index into the wrong cell. -1 is
    never used as a subscript by this package.

    @capability stm_key_bucket
    complexity: O(1)
    counts:
    - dim width <= MAX_STM_WIDTH [kernel_validated]
    @endcapability
    """
    if width < 1 or width > MAX_STM_WIDTH:
        return -1
    return cms_hash(stm_key_hash31(seed, row, item), 7, width)


def stm_coin(seed: Int, level: Int, index: Int) -> Bool:
    """Fair keyed coin for compaction at `level`, `index`-th time.

    Lives on a row axis offset by `STM_COIN_ROW_BASE` so a coin cannot collide with an item
    hash at the same coordinates.

    @capability stm_coin
    complexity: O(1)
    counts: none
    @endcapability
    """
    return (stm_key_word(seed, STM_COIN_ROW_BASE + level, index) & 1) == 1


def stm_stream_id() -> UInt64:
    """The Philox stream id this package hashes on.

    Exposed so a caller can prove the constant matches
    `determinism.streams.stream_id("algenta.streaming")` without importing the substrate.

    @capability stm_stream_id
    complexity: O(1)
    counts: none
    @endcapability
    """
    return STM_STREAM


# ── the error claims, each one absent for an unusable parameter ────────────────


struct StmClaim(Copyable, Movable):
    """An error bound a sketch CLAIMS, or the absence of one.

    `present == False` means the parameter it was asked about is not a usable sketch
    parameter, so there is no bound to state and `value` is 0.0 and means nothing. Declared
    in this file rather than shared from elsewhere: a struct owned by another module is
    silently dropped from the runtime contract, which would remove these functions from the
    SDK without any error at all.
    """

    var value: Float64
    var present: Bool
    var status: Int

    def __init__(out self, value: Float64, present: Bool, status: Int):
        self.value = value
        self.present = present
        self.status = status


def stm_no_claim(status: Int) -> StmClaim:
    """No bound, with the reason. `value` is 0.0 and is not a bound.

    @capability stm_no_claim
    complexity: O(1)
    counts: none
    @endcapability
    """
    return StmClaim(0.0, False, status)


def stm_hll_relative_error(precision: Int) -> StmClaim:
    """HyperLogLog's claimed relative standard error, `1.04 / sqrt(2^precision)`.

    This is ONE standard deviation, not a guarantee. A suite that asserts an observed
    relative error inside `1.04/sqrt(m)` is asserting a coin lands heads; the honest
    assertion is against a stated multiple of it, and the multiple must be stated.

    @capability stm_hll_relative_error
    complexity: O(1)
    counts:
    - dim precision <= MAX_STM_PRECISION [kernel_validated]
    @endcapability
    """
    if precision < MIN_STM_PRECISION or precision > MAX_STM_PRECISION:
        return stm_no_claim(STM_ERR_PRECISION)
    var m = Float64(1 << precision)
    return StmClaim(STM_HLL_SIGMA / sqrt(m), True, STM_OK)


def stm_cms_epsilon(width: Int) -> StmClaim:
    """Count-Min's claimed additive over-estimate as a FRACTION of total mass.

    `e / width`, inflated by `1 + width / 1000003` for the modulo bias the frozen
    `cms_hash` introduces when 1000003 is not a multiple of `width`. Ignoring that factor
    would be quoting a bound for a uniform hash while using a slightly non-uniform one.

    The estimate for an item is then claimed to exceed its true count by at most
    `epsilon * total` with probability at least `1 - stm_cms_delta(depth)`.

    @capability stm_cms_epsilon
    complexity: O(1)
    counts:
    - dim width <= MAX_STM_WIDTH [kernel_validated]
    @endcapability
    """
    if width < 1 or width > MAX_STM_WIDTH:
        return stm_no_claim(STM_ERR_WIDTH)
    var w = Float64(width)
    var bias = 1.0 + w / Float64(STM_CMS_MODULUS)
    return StmClaim(STM_E * bias / w, True, STM_OK)


def stm_cms_delta(depth: Int) -> StmClaim:
    """Count-Min's claimed failure probability for the epsilon bound: `e^-depth`.

    One row over-estimates by more than `e/width * total` with probability at most `1/e` by
    Markov's inequality; independent rows and a minimum over them give `e^-depth`. That
    independence is exactly what the keyed per-row hash restores and what the frozen row
    seeds destroy, so this number is a claim about `stm_key_bucket` and not about
    `cms_hash` alone.

    @capability stm_cms_delta
    complexity: O(1)
    counts:
    - dim depth <= MAX_STM_DEPTH [kernel_validated]
    @endcapability
    """
    if depth < 1 or depth > MAX_STM_DEPTH:
        return stm_no_claim(STM_ERR_DEPTH)
    return StmClaim(exp(-Float64(depth)), True, STM_OK)


def stm_kll_rank_error(k: Int) -> StmClaim:
    """The quantile sketch's claimed rank error as a FRACTION of the stream length.

    `STM_KLL_C / k`, derived in this module's constant block from the variance of the
    compaction shifts rather than quoted. A rank returned by the sketch is claimed to be
    within `value * n` of the true rank.

    @capability stm_kll_rank_error
    complexity: O(1)
    counts:
    - dim k <= MAX_STM_K [kernel_validated]
    @endcapability
    """
    if k < MIN_STM_K or k > MAX_STM_K or (k % 2) != 0:
        return stm_no_claim(STM_ERR_CAPACITY)
    return StmClaim(STM_KLL_C / Float64(k), True, STM_OK)


def stm_hll_registers(precision: Int) -> Int:
    """Register count `2^precision`, or 0 when `precision` is out of range.

    0 is not a register count, so a caller that ignores the range gets an allocation of
    nothing rather than a shift by a negative amount.

    @capability stm_hll_registers
    complexity: O(1)
    counts:
    - dim precision <= MAX_STM_PRECISION [kernel_validated]
    @endcapability
    """
    if precision < MIN_STM_PRECISION or precision > MAX_STM_PRECISION:
        return 0
    return 1 << precision


def stm_log2_floor(value: Int) -> Int:
    """`floor(log2(value))` for `value >= 1`, and -1 for anything below 1.

    Integer-only, so it never disagrees with a shift the way a `log(x)/log(2)` rounding
    would at a power of two.

    @capability stm_log2_floor
    complexity: O(log value)
    counts: none
    @endcapability
    """
    if value < 1:
        return -1
    var v = value
    var out = 0
    while v > 1:
        v >>= 1
        out += 1
    return out
