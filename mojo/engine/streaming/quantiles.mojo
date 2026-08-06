"""
streaming.quantiles — a KLL compactor stack: quantiles from a sketch, with a checked bound.

WHICH SKETCH, AND WHY: **KLL**, not t-digest. A t-digest's accuracy is a description of how
its centroids happen to be laid out and has no theorem behind it, so a bound could only be
quoted, never derived. A KLL compactor stack has an error whose variance can be WRITTEN DOWN
from the algorithm -- one term per compaction -- so the claim in `stm_kll_rank_error` is
derived arithmetic and the suite can check a measurement against it. A bound you cannot
derive is a bound you cannot check.

Classification of every capability here
---------------------------------------
* **genuinely-missing.** There is no quantile sketch of any kind in the tree: not KLL, not
  t-digest, not Greenwald-Khanna, not a q-digest. `anomaly.percentile` and
  `metrics_agg.histogram_percentile` are the two exact/bucketed alternatives and both need
  the whole dataset or a pre-declared bucket layout. So the compactor stack, its levels, its
  keyed coin, its merge and its snapshot are all new, in this namespace.
* **existing-frozen, CALLED not rewritten.** `sorting.mergesort` sorts every level -- chosen
  over the frozen `quicksort` because a Lomuto partition on already-sorted data is O(m^2)
  and a compacted level is always nearly sorted. `anomaly.percentile` is the EXACT oracle the
  suite and the benchmark measure this sketch against. `determinism.counter_rng.philox_word`,
  through `contract.stm_coin`, is the compaction coin.
* **missing-driver.** Nothing composed those into a streaming quantile answer.

The algorithm, stated so the bound can be derived
-------------------------------------------------
Level `i` holds items each standing for `2^i` stream items. An arriving item joins level 0.
When a level reaches `k` items it is SORTED and COMPACTED: a fair keyed coin picks offset 0
or 1, every other item from that offset is promoted to level `i+1` at double weight, and the
rest are discarded. Only an EVEN prefix is compacted, so `m` items of weight `2^i` become
exactly `m/2` items of weight `2^(i+1)` and any odd leftover stays behind at its own weight.
Total weight is therefore preserved EXACTLY at every step, which is the invariant
`quantile_total_weight` re-derives and the suite asserts against `n`.

The error follows directly. For a fixed query, one compaction at level `i` shifts the
estimated rank by at most `2^i`, and by `+2^i` or `-2^i` with equal probability because the
offset is a fair coin -- so the shift has mean zero. Shifts from different compactions are
independent. Level `i` is compacted about `n / (2^i * k)` times, so

    Var  =  sum_i  4^i * n/(2^i * k)  =  (n/k) * sum_i 2^i  ~  2 (n/k)^2

because the top level's weight `2^H` is about `n/k`. The standard deviation is about
`1.41 n/k`, and `STM_KLL_C = 8.0` is a 5.7-sigma allowance that also absorbs the union bound
over the ~100 quantiles probed at once. The constant is derived, not tuned: raising it to
make a failing measurement pass would be a behaviour change, not a fix.

The minimum and the maximum are tracked EXACTLY and separately, because compaction can
discard either and `q = 0` returning something above the true minimum is the one error a
reader will always notice.

Mergeability, and the honest form of the claim
---------------------------------------------
`distinct` and `frequency` merge EXACTLY. This sketch does not, and saying so is the point:
compaction is lossy, so `merge(a, b)` is A sketch of `A ++ B` rather than THE sketch of it.
The claim is therefore the sketch's own stated bound, and the suite checks exactly that:

  * every rank the MERGED sketch reports is within `stm_kll_rank_error(k) * (n_a + n_b)` of
    the rank computed by an exact sort of the concatenated stream;
  * when neither input ever compacted, the merge IS exact -- the union of two verbatim
    buffers -- and the suite asserts that case with `==`, so the lossy case is bounded by a
    measurement and the lossless case by an equality;
  * `merge(a, b)` and `merge(b, a)` hold the same multiset, because levels are sorted before
    compaction and the compaction counters combine with a maximum, both order-independent.

WHICH QUANTILE DEFINITION: NEAREST-RANK, with the rank a CEILING
---------------------------------------------------------------
`quantile_at(sk, q)` returns the smallest stored value whose estimated rank is at least
`ceil(q * n)`. That is the nearest-rank definition, and `ceil` is load-bearing: with
truncation, `q = 0.29` over 1.0 .. 100.0 returned 28.0 where the 29th smallest is 29.0, under a
success status and inside a sketch that had not approximated anything -- a one-item rank error
against a self-reported slack of 0.195 items. `_rank_of` states the rule and the reason the
floating product `q * n` needs a tolerance in BOTH directions. `quantile_rank` is the exact
inverse of this definition, and the suite asserts the round trip rather than trusting it.

No interpolation: every value this sketch returns is a value that was actually observed. The
frozen `anomaly.percentile` interpolates linearly between neighbours and is the EXACT oracle the
suite measures against, so the two differ by up to one rank step by construction, and the suite
compares RANKS -- which is the space the bound is stated in -- rather than values.

EVERY SKETCH ARRIVES FROM A CALLER
----------------------------------
`QuantileSketch` is decoded from caller JSON by the generated dispatch, which validates field
TYPES and no cross-field invariant. `level_sizes`, `compactions` and `n` are therefore
CALLER-SUPPLIED counts over CALLER-SUPPLIED lists, and every subscript in this module is driven
by those counts. `_levels_ok` relates them to `len(values)` and `len(compactions)` before the
first read, and every public entry point calls it or `_sketch_ok`. That relation cannot be
declared in a `counts:` block -- the manifest grammar's `len(NAME)` takes a parameter name, not
a struct field -- so the kernel is the only place it can live.

Absence
-------
A quantile of an empty sketch is ABSENT, under `STM_EMPTY`, with the value slot at 0.0 and
meaningless. It is not 0.0, and it is not the minimum of nothing. This differs on purpose
from `frequency.frequency_query` on an empty sketch, which is PRESENT with count 0: nothing
having been added determines every COUNT exactly, and determines no QUANTILE at all.

Bounding memory is not bounding work
------------------------------------
Memory is `k` items per level and at most `MAX_STM_LEVELS` levels. Work is `n` appends plus
`2n log2(k)` comparisons -- two compactions' worth of sorting amortised over each item -- and
is charged as the PRODUCT `n * (log2(k) + 1)`, not as `n + k`. `quantile_profile` is O(M * L)
once and every query after it is a binary search, which is why `quantile_batch` exists: 100
quantiles built on 100 independent profiles would be 100x the work for the same answer.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: true
seed_requirements: required
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_streaming_quantiles.mojo
benchmark: benchmarks/mojo_benchmarks/bench_streaming.mojo
docs: gitbook/engine/streaming-sketches.md
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from sorting import mergesort

from streaming.contract import (
    MAX_STM_LEVELS,
    MAX_STM_WORK,
    STM_EMPTY,
    STM_ERR_CAPACITY,
    STM_ERR_COUNT,
    STM_ERR_INCOMPATIBLE_MERGE,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_ITEM_BUDGET,
    STM_ERR_LEVEL_OVERFLOW,
    STM_ERR_NON_FINITE,
    STM_ERR_QUANTILE_RANGE,
    STM_ERR_SEED_RANGE,
    STM_ERR_SNAPSHOT_SHAPE,
    STM_ERR_WORK_BUDGET,
    STM_OK,
    stm_coin,
    stm_finite,
    stm_items_ok,
    stm_kll_rank_error,
    stm_log2_floor,
    stm_seed_ok,
    stm_tolerance,
    stm_work_fits,
)

#: Snapshot tag on the integer header.
comptime QUANTILE_SNAPSHOT_MAGIC: Int = 0x4B4C4C51

#: Integer header words before the per-level arrays: magic, k, seed, n, n_levels.
comptime QUANTILE_HEADER: Int = 5

#: Float payload words before the level items: minimum, maximum.
comptime QUANTILE_VALUE_HEADER: Int = 2

#: `contract.MIN_STM_K` / `MAX_STM_K`, restated here because a declared ceiling must name a
#: constant in the SAME file as the kernel that tests it -- otherwise the declaration and the
#: check are two different numbers that can drift apart. These are the constants `_params_ok`
#: tests against, and `test_streaming_quantiles.mojo` asserts they still equal the contract's.
comptime QUANTILE_MIN_K: Int = 4
comptime QUANTILE_MAX_K: Int = 4096


struct QuantileSketch(Copyable, Movable):
    """A KLL compactor stack, as a value the caller owns.

    `values` holds the levels concatenated in level order, `level_sizes[i]` items for level
    `i`; an item in level `i` stands for `2^i` stream items. `compactions[i]` is how many
    times level `i` has been compacted and is carried so that a sketch resumed from a
    snapshot draws FRESH coins instead of replaying the ones it already used.

    `minimum` and `maximum` are exact. When `n == 0` they are 0.0 and mean nothing, which is
    why every query checks `n` and not the value slots.

    Declared in this file: a struct owned by another module is silently dropped from the
    runtime contract.
    """

    var values: List[Float64]
    var level_sizes: List[Int]
    var compactions: List[Int]
    var k: Int
    var n: Int
    var seed: Int
    var minimum: Float64
    var maximum: Float64
    var status: Int
    var valid: Bool

    def __init__(
        out self,
        values: List[Float64],
        level_sizes: List[Int],
        compactions: List[Int],
        k: Int,
        n: Int,
        seed: Int,
        minimum: Float64,
        maximum: Float64,
        status: Int,
        valid: Bool,
    ):
        self.values = values.copy()
        self.level_sizes = level_sizes.copy()
        self.compactions = compactions.copy()
        self.k = k
        self.n = n
        self.seed = seed
        self.minimum = minimum
        self.maximum = maximum
        self.status = status
        self.valid = valid


struct QuantileEstimate(Copyable, Movable):
    """One quantile or one rank, or its absence.

    `present == False` means no such quantity exists -- an empty sketch, an invalid one, or a
    `q` outside `[0, 1]` -- and `value` is 0.0 and is not an answer.

    `rank_error` is the CLAIMED rank error as a fraction of `n`; `rank_slack` is the same
    number in items, so a caller reads the interval without recomputing it.
    """

    var value: Float64
    var present: Bool
    var rank_error: Float64
    var rank_slack: Float64
    var n: Int
    var status: Int

    def __init__(
        out self,
        value: Float64,
        present: Bool,
        rank_error: Float64,
        rank_slack: Float64,
        n: Int,
        status: Int,
    ):
        self.value = value
        self.present = present
        self.rank_error = rank_error
        self.rank_slack = rank_slack
        self.n = n
        self.status = status


struct QuantileSeries(Copyable, Movable):
    """Many quantiles at once, each with its own presence flag.

    A per-element flag rather than one for the batch: `q = 0.5` has an answer in the same
    call where `q = 1.7` does not, and collapsing that into a single flag would either
    discard a good answer or return 0.0 as if it were one.
    """

    var values: List[Float64]
    var present: List[Bool]
    var rank_error: Float64
    var n: Int
    var status: Int
    var valid: Bool

    def __init__(
        out self,
        values: List[Float64],
        present: List[Bool],
        rank_error: Float64,
        n: Int,
        status: Int,
        valid: Bool,
    ):
        self.values = values.copy()
        self.present = present.copy()
        self.rank_error = rank_error
        self.n = n
        self.status = status
        self.valid = valid


struct QuantileProfile(Copyable, Movable):
    """The sketch's estimated distribution: sorted values with cumulative weights.

    `cumulative[j]` is the estimated number of stream items less than or equal to
    `values[j]`, so this is the whole estimated CDF in one object. Built once in O(M * L) and
    then queried by binary search, which is what makes a batch of quantiles cheap.

    The last cumulative entry equals `n` exactly, because compaction preserves total weight.
    """

    var values: List[Float64]
    var cumulative: List[Int]
    var n: Int
    var status: Int
    var valid: Bool

    def __init__(
        out self,
        values: List[Float64],
        cumulative: List[Int],
        n: Int,
        status: Int,
        valid: Bool,
    ):
        self.values = values.copy()
        self.cumulative = cumulative.copy()
        self.n = n
        self.status = status
        self.valid = valid


struct QuantileSnapshot(Copyable, Movable):
    """A sketch split into an integer header and a float payload.

    Two flat lists rather than one, because packing level sizes into a `List[Float64]` would
    make an integer count a float that a reader has to trust round-trips. `header` is
    `[magic, k, seed, n, n_levels] ++ level_sizes ++ compactions`; `values` is
    `[minimum, maximum] ++ level items in level order`.

    An invalid sketch snapshots as two EMPTY lists, never as a header with no payload.
    """

    var header: List[Int]
    var values: List[Float64]

    def __init__(out self, header: List[Int], values: List[Float64]):
        self.header = header.copy()
        self.values = values.copy()


def _invalid(status: Int) -> QuantileSketch:
    """Not a sketch, with the reason."""
    return QuantileSketch(
        List[Float64](), List[Int](), List[Int](), 0, 0, 0, 0.0, 0.0, status, False
    )


def _absent(status: Int, n: Int) -> QuantileEstimate:
    """No quantile, with the reason. `value` is 0.0 and means nothing."""
    return QuantileEstimate(0.0, False, 0.0, 0.0, n, status)


def _params_ok(k: Int, seed: Int) -> Int:
    """`STM_OK`, or the status that refuses these parameters.

    `k` must be EVEN: a compaction promotes exactly half a full level, and an odd capacity
    would leave the halving to a rounding rule instead of to arithmetic.
    """
    if k < QUANTILE_MIN_K or k > QUANTILE_MAX_K or (k % 2) != 0:
        return STM_ERR_CAPACITY
    if not stm_seed_ok(seed):
        return STM_ERR_SEED_RANGE
    return STM_OK


def _levels_ok(sketch: QuantileSketch) -> Int:
    """`STM_OK`, or the status refusing this sketch's SHAPE. O(number of levels).

    THE STRUCT PATH IS A CALLER PATH. `QuantileSketch` is decoded from caller JSON by the
    generated dispatch, which validates FIELD TYPES and no cross-field invariant, so
    `valid: true` beside an empty `values` list and a `level_sizes` of `[8]` is an accepted
    request. Every subscript in this module -- `_levels_of`'s `values[cursor + j]`, `_compact`'s
    `comps[index]` -- is driven by those count FIELDS, not by `len()` of the list being read, so
    without this function `quantile_at`, `quantile_add`, `quantile_batch`, `quantile_rank`,
    `quantile_profile` and `quantile_merge` each take one well-typed request and kill the worker
    process on an uncatchable bounds assertion. Measured, before this existed: all six died at
    `quantiles.mojo:339`, and `try/except` in the dispatch arm did not contain any of them.
    `*_from_snapshot` had these checks all along; the struct path simply never reached them.

    So the relations a caller could otherwise break are all checked here, cheaply, before the
    first read:

      * `sum(level_sizes) == len(values)` -- the flat level layout. Without it `_levels_of`
        walks off the end of `values`.
      * `len(compactions) == len(level_sizes)` -- `_compact` reads `comps[index]` for a level
        index it did not create, so a short `compactions` aborts just as surely.
      * `1 <= len(level_sizes) <= MAX_STM_LEVELS` -- checked BEFORE the weight loop, which is
        what makes `size * (1 << i)` a non-wrapping product: 40 levels bound the shift at
        `2^39`, and `4096 * 2^39 * 40 < 2^63`.
      * every `level_sizes[i]` in `[0, QUANTILE_MAX_K]` and every `compactions[i]` non-negative.
      * the re-derived total weight equals `n`, and `n` is inside the item ceiling.

    None of those is expressible in a `counts:` block: the manifest grammar's `len(NAME)` takes
    a PARAMETER name, and `len(sketch.values)` is a struct field, which the checker reports as
    `relation_unknown_parameter`. The kernel is therefore the only place the relation can live,
    which is why it lives here and why every entry point calls it.
    """
    if not sketch.valid:
        return STM_ERR_INVALID_SKETCH
    var bad = _params_ok(sketch.k, sketch.seed)
    if bad != STM_OK:
        return bad
    var n_levels = len(sketch.level_sizes)
    if n_levels < 1 or n_levels > MAX_STM_LEVELS:
        return STM_ERR_LEVEL_OVERFLOW
    if len(sketch.compactions) != n_levels:
        return STM_ERR_SNAPSHOT_SHAPE
    if sketch.n < 0 or not stm_items_ok(sketch.n):
        return STM_ERR_ITEM_BUDGET
    var stored = 0
    var weight = 0
    for i in range(n_levels):
        var size = sketch.level_sizes[i]
        if size < 0 or size > QUANTILE_MAX_K:
            return STM_ERR_SNAPSHOT_SHAPE
        if sketch.compactions[i] < 0:
            return STM_ERR_SNAPSHOT_SHAPE
        stored += size
        weight += size * (1 << i)
    if stored != len(sketch.values):
        return STM_ERR_SNAPSHOT_SHAPE
    if weight != sketch.n:
        return STM_ERR_SNAPSHOT_SHAPE
    return STM_OK


def _bounds_ok(sketch: QuantileSketch) -> Int:
    """`STM_OK`, or the status refusing this sketch's exact minimum and maximum. O(1).

    `minimum` and `maximum` are returned VERBATIM by `quantile_minimum`, `quantile_maximum` and
    the `q = 0` / `q = 1` arms of `quantile_at`, so a forged non-finite in either slot is not a
    wrong number in one field -- it makes the WHOLE response a typed error, because the dispatch
    refuses to serialise a non-finite.
    """
    if not stm_finite(sketch.minimum) or not stm_finite(sketch.maximum):
        return STM_ERR_NON_FINITE
    if sketch.n > 0 and sketch.minimum > sketch.maximum:
        return STM_ERR_SNAPSHOT_SHAPE
    return STM_OK


def _sketch_ok(sketch: QuantileSketch) -> Int:
    """`STM_OK`, or the status refusing this sketch. Shape, bounds, then every stored value.

    O(M + L). The value scan is the last step because it is the only expensive one, and every
    caller of this function is already O(M) or more.
    """
    var bad = _levels_ok(sketch)
    if bad != STM_OK:
        return bad
    bad = _bounds_ok(sketch)
    if bad != STM_OK:
        return bad
    for j in range(len(sketch.values)):
        if not stm_finite(sketch.values[j]):
            return STM_ERR_NON_FINITE
    return STM_OK


def _levels_of(sketch: QuantileSketch) -> List[List[Float64]]:
    """The sketch's levels as nested lists. Requires `_levels_ok(sketch) == STM_OK`."""
    var out = List[List[Float64]]()
    var cursor = 0
    for i in range(len(sketch.level_sizes)):
        var level = List[Float64]()
        for j in range(sketch.level_sizes[i]):
            level.append(sketch.values[cursor + j])
        cursor += sketch.level_sizes[i]
        out.append(level^)
    return out^


def _compact(
    mut levels: List[List[Float64]], mut comps: List[Int], index: Int, k: Int, seed: Int
) -> Bool:
    """Compact level `index` into `index + 1`. False when a new level cannot be created.

    Sorts with the frozen `sorting.mergesort`, then promotes every other item of the largest
    EVEN prefix from a coin-chosen offset. Even prefix only, so `m` items of weight `2^i`
    become exactly `m/2` of weight `2^(i+1)` and the total weight is preserved to the item.
    """
    if index + 1 >= MAX_STM_LEVELS:
        return False
    if index + 1 >= len(levels):
        levels.append(List[Float64]())
        comps.append(0)
    var sorted_level = mergesort(levels[index])
    var m = (len(sorted_level) // 2) * 2
    var offset = 1 if stm_coin(seed, index, comps[index]) else 0
    var promoted = List[Float64]()
    var j = offset
    while j < m:
        promoted.append(sorted_level[j])
        j += 2
    var leftover = List[Float64]()
    for t in range(m, len(sorted_level)):
        leftover.append(sorted_level[t])
    for t in range(len(promoted)):
        levels[index + 1].append(promoted[t])
    levels[index] = leftover^
    comps[index] += 1
    return True


def _cascade(
    mut levels: List[List[Float64]], mut comps: List[Int], k: Int, seed: Int
) -> Bool:
    """Compact every over-full level, lowest first. False on level overflow.

    One ascending sweep is enough: a compaction only pushes items UPWARD, and it leaves at
    most one item behind, so no level can become over-full again after its own turn.
    """
    var i = 0
    while i < len(levels):
        if len(levels[i]) >= k:
            if not _compact(levels, comps, i, k, seed):
                return False
        i += 1
    return True


def _pack(
    levels: List[List[Float64]],
    comps: List[Int],
    k: Int,
    n: Int,
    seed: Int,
    minimum: Float64,
    maximum: Float64,
) -> QuantileSketch:
    """Flatten nested levels back into the flat sketch representation."""
    var values = List[Float64]()
    var sizes = List[Int]()
    for i in range(len(levels)):
        sizes.append(len(levels[i]))
        for j in range(len(levels[i])):
            values.append(levels[i][j])
    return QuantileSketch(
        values^, sizes^, comps, k, n, seed, minimum, maximum, STM_OK, True
    )


def quantile_empty(k: Int, seed: Int) -> QuantileSketch:
    """An empty sketch with level capacity `k`, keyed by `seed`.

    Valid, and with no quantile: `quantile_at` reports ABSENT for it. An empty sketch is the
    merge identity, which is why it is valid rather than refused.

    @capability quantile_empty
    complexity: O(1)
    counts:
    - dim k <= QUANTILE_MAX_K [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(k, seed)
    if bad != STM_OK:
        return _invalid(bad)
    var levels = List[List[Float64]]()
    levels.append(List[Float64]())
    var comps = List[Int]()
    comps.append(0)
    return _pack(levels, comps, k, 0, seed, 0.0, 0.0)


def quantile_add(sketch: QuantileSketch, x: Float64) -> QuantileSketch:
    """`sketch` with one more observation, as a new value.

    A non-finite observation is refused rather than stored. Storing one would put it into a
    level, into the minimum or maximum, and eventually into a returned quantile -- and a
    non-finite field makes the WHOLE response a typed error rather than one field being
    wrong. Refusing at the door is the only place the refusal is cheap.

    `sketch` arrives from caller JSON, so its own list lengths are validated against its own
    count fields by `_sketch_ok` before the first subscript. Without that, `level_sizes = [8]`
    beside an empty `values` killed the worker at `_levels_of`.

    @capability quantile_add
    complexity: O(M + k log k) amortised over k additions
    counts: none
    @endcapability
    """
    var shape = _sketch_ok(sketch)
    if shape != STM_OK:
        return _invalid(shape)
    if not stm_finite(x):
        return _invalid(STM_ERR_NON_FINITE)
    if sketch.n >= 0 and not stm_items_ok(sketch.n + 1):
        return _invalid(STM_ERR_ITEM_BUDGET)
    var levels = _levels_of(sketch)
    var comps = sketch.compactions.copy()
    levels[0].append(x)
    if not _cascade(levels, comps, sketch.k, sketch.seed):
        return _invalid(STM_ERR_LEVEL_OVERFLOW)
    var lo = x if sketch.n == 0 or x < sketch.minimum else sketch.minimum
    var hi = x if sketch.n == 0 or x > sketch.maximum else sketch.maximum
    return _pack(levels, comps, sketch.k, sketch.n + 1, sketch.seed, lo, hi)


def quantile_ingest(values: List[Float64], k: Int, seed: Int) -> QuantileSketch:
    """A sketch of every element of `values`.

    The element count is `len(values)` and is never a parameter, which removes the
    `n > len(v)` class from this entry point by construction.

    @capability quantile_ingest
    complexity: O(len(values) * log k)
    counts:
    - dim k <= QUANTILE_MAX_K [kernel_validated]
    @endcapability
    """
    return quantile_ingest_prefix(values, len(values), k, seed)


def quantile_ingest_prefix(
    values: List[Float64], n: Int, k: Int, seed: Int
) -> QuantileSketch:
    """A sketch of `values[0..n)`, for replaying a prefix of a stored stream.

    `n` is a redundant count and is validated in BOTH directions before anything is indexed.
    An `n` past the end reads past the `List` end, which aborts the process in a way
    `try/except` cannot contain and takes every resident dataset with it. A negative `n`
    reads nothing rather than aborting, and is refused anyway because it is not a request.

    The work charge is the PRODUCT `n * (log2(k) + 1)`: every item is sorted into a level
    roughly twice per level it survives, which totals about `2 n log2(k)` comparisons.
    Charging `n + k` here would let a legitimate-looking request run for minutes.

    @capability quantile_ingest_prefix
    complexity: O(n * log k)
    counts:
    - n <= len(values) [kernel_validated]
    - dim k <= QUANTILE_MAX_K [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(k, seed)
    if bad != STM_OK:
        return _invalid(bad)
    if n < 0 or n > len(values):
        return _invalid(STM_ERR_COUNT)
    if not stm_items_ok(n):
        return _invalid(STM_ERR_ITEM_BUDGET)
    if not stm_work_fits(n, stm_log2_floor(k) + 1, MAX_STM_WORK):
        return _invalid(STM_ERR_WORK_BUDGET)
    for i in range(n):
        if not stm_finite(values[i]):
            return _invalid(STM_ERR_NON_FINITE)

    var levels = List[List[Float64]]()
    levels.append(List[Float64]())
    var comps = List[Int]()
    comps.append(0)
    var lo: Float64 = 0.0
    var hi: Float64 = 0.0
    for i in range(n):
        var x = values[i]
        if i == 0 or x < lo:
            lo = x
        if i == 0 or x > hi:
            hi = x
        levels[0].append(x)
        if len(levels[0]) >= k:
            if not _cascade(levels, comps, k, seed):
                return _invalid(STM_ERR_LEVEL_OVERFLOW)
    return _pack(levels, comps, k, n, seed, lo, hi)


def quantile_merge(a: QuantileSketch, b: QuantileSketch) -> QuantileSketch:
    """A sketch of `A ++ B`, within `stm_kll_rank_error(k) * (a.n + b.n)` of the exact one.

    Corresponding levels are concatenated and the result re-compacted where it exceeds `k`.
    Compaction counters combine with a MAXIMUM so the merged sketch draws coins it has not
    used before; that keeps the merge deterministic while keeping the coins independent.

    Refuses when `k` or `seed` differ: two different capacities give two different level
    structures and two different seeds give two different coin sequences, so there is no
    correspondence to merge along.

    Not exact in general -- compaction is lossy. When neither input has compacted, the merged
    sketch holds the exact union and IS the one-pass sketch, and the suite asserts that case
    with `==` alongside the bounded case.

    Both inputs are validated against their OWN count fields first. Merging a forged sketch
    would otherwise abort in `_levels_of`, and -- worse -- a merge that survived would emit a
    `valid: true` sketch that aborts one dispatch later in whoever queries it.

    @capability quantile_merge
    complexity: O((M_a + M_b) log k)
    counts: none
    @endcapability
    """
    var shape_a = _sketch_ok(a)
    if shape_a != STM_OK:
        return _invalid(shape_a)
    var shape_b = _sketch_ok(b)
    if shape_b != STM_OK:
        return _invalid(shape_b)
    if a.k != b.k or a.seed != b.seed:
        return _invalid(STM_ERR_INCOMPATIBLE_MERGE)
    if not stm_items_ok(a.n + b.n):
        return _invalid(STM_ERR_ITEM_BUDGET)

    var la = _levels_of(a)
    var lb = _levels_of(b)
    var depth = len(la) if len(la) > len(lb) else len(lb)
    if depth > MAX_STM_LEVELS:
        return _invalid(STM_ERR_LEVEL_OVERFLOW)
    var levels = List[List[Float64]]()
    var comps = List[Int]()
    for i in range(depth):
        var merged = List[Float64]()
        if i < len(la):
            for j in range(len(la[i])):
                merged.append(la[i][j])
        if i < len(lb):
            for j in range(len(lb[i])):
                merged.append(lb[i][j])
        levels.append(merged^)
        var ca = a.compactions[i] if i < len(a.compactions) else 0
        var cb = b.compactions[i] if i < len(b.compactions) else 0
        comps.append(ca if ca > cb else cb)
    if not _cascade(levels, comps, a.k, a.seed):
        return _invalid(STM_ERR_LEVEL_OVERFLOW)

    var n = a.n + b.n
    var lo: Float64 = 0.0
    var hi: Float64 = 0.0
    if a.n > 0 and b.n > 0:
        lo = a.minimum if a.minimum < b.minimum else b.minimum
        hi = a.maximum if a.maximum > b.maximum else b.maximum
    elif a.n > 0:
        lo = a.minimum
        hi = a.maximum
    elif b.n > 0:
        lo = b.minimum
        hi = b.maximum
    return _pack(levels, comps, a.k, n, a.seed, lo, hi)


def quantile_profile(sketch: QuantileSketch) -> QuantileProfile:
    """The sketch's estimated CDF: ascending values with cumulative weights.

    Built by an L-way merge over the per-level sorted arrays, so it is produced once in
    O(M * L) and every query afterwards is a binary search. `cumulative` ends at `n` exactly.

    An invalid or empty sketch yields `valid == False` with empty lists — not a zero-length
    CDF that a caller could mistake for a distribution concentrated at zero.

    @capability quantile_profile
    complexity: O(M * L)
    counts: none
    @endcapability
    """
    var shape = _sketch_ok(sketch)
    if shape != STM_OK:
        return QuantileProfile(List[Float64](), List[Int](), 0, shape, False)
    if sketch.n <= 0:
        return QuantileProfile(List[Float64](), List[Int](), 0, STM_EMPTY, False)

    var levels = _levels_of(sketch)
    var sorted_levels = List[List[Float64]]()
    var cursors = List[Int]()
    var weights = List[Int]()
    for i in range(len(levels)):
        sorted_levels.append(mergesort(levels[i]))
        cursors.append(0)
        weights.append(1 << i)

    var values = List[Float64]()
    var cumulative = List[Int]()
    var running = 0
    while True:
        var best = -1
        var best_value: Float64 = 0.0
        for i in range(len(sorted_levels)):
            if cursors[i] >= len(sorted_levels[i]):
                continue
            var candidate = sorted_levels[i][cursors[i]]
            if best < 0 or candidate < best_value:
                best = i
                best_value = candidate
        if best < 0:
            break
        cursors[best] += 1
        running += weights[best]
        # Equal values collapse into one ladder rung, so `cumulative` is strictly increasing
        # and a rank query cannot land between two entries that name the same value.
        if len(values) > 0 and values[len(values) - 1] == best_value:
            cumulative[len(cumulative) - 1] = running
        else:
            values.append(best_value)
            cumulative.append(running)
    return QuantileProfile(values^, cumulative^, sketch.n, STM_OK, True)


def _search_rank(profile: QuantileProfile, target: Int) -> Int:
    """Smallest index whose cumulative weight is at least `target`, or the last index."""
    var lo = 0
    var hi = len(profile.cumulative) - 1
    while lo < hi:
        var mid = lo + (hi - lo) // 2
        if profile.cumulative[mid] >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def quantile_at(sketch: QuantileSketch, q: Float64) -> QuantileEstimate:
    """The value at quantile `q`, or ABSENCE.

    `q` outside `[0, 1]` is refused rather than clamped: clamping turns a caller's unit
    mix-up -- 95 for the 95th percentile -- into the maximum, which looks like an answer.
    `q = 0` and `q = 1` return the EXACT minimum and maximum, which are tracked separately
    precisely because compaction can discard them.

    An empty sketch has no quantile: `present == False` under `STM_EMPTY`, and `value` is 0.0
    and means nothing.

    @capability quantile_at
    complexity: O(M * L)
    counts: none
    @endcapability
    """
    var shape = _sketch_ok(sketch)
    if shape != STM_OK:
        return _absent(shape, 0)
    if not stm_finite(q) or q < 0.0 or q > 1.0:
        return _absent(STM_ERR_QUANTILE_RANGE, sketch.n)
    if sketch.n <= 0:
        return _absent(STM_EMPTY, sketch.n)
    var claim = stm_kll_rank_error(sketch.k)
    if not claim.present:
        return _absent(STM_ERR_CAPACITY, sketch.n)
    var slack = claim.value * Float64(sketch.n)
    if q <= 0.0:
        return QuantileEstimate(
            sketch.minimum, True, claim.value, slack, sketch.n, STM_OK
        )
    if q >= 1.0:
        return QuantileEstimate(
            sketch.maximum, True, claim.value, slack, sketch.n, STM_OK
        )
    var profile = quantile_profile(sketch)
    if not profile.valid or len(profile.values) == 0:
        return _absent(STM_EMPTY, sketch.n)
    return _from_profile(profile, q, claim.value, slack, sketch.n)


def _rank_of(q: Float64, n: Int) -> Int:
    """The NEAREST-RANK target for quantile `q` of `n` items: `ceil(q * n)`, clamped to `[1, n]`.

    A CEILING, and not `Int(q * Float64(n))`. Truncation returns the WRONG QUANTILE, and it does
    so on a sketch that stores every item verbatim and has no approximation in it at all.
    Measured before this function existed, on 1.0 .. 100.0 at `k = 4096` where nothing ever
    compacts: `quantile_at(sk, 0.29)` returned 28.0 under status `ok`, while the 29th smallest
    item is 29.0 and this module's own `quantile_rank(sk, 29.0)` returned exactly 0.29 -- the
    pair contradicted itself, both under a success status. The rank error was a full item against
    a self-reported `rank_slack` of 0.1953125 items, a 5.12x breach of the sketch's own interval.
    Across `q = i/100` for `i` in 1..99 at five stream lengths, truncation missed the ceiling in
    228 of 495 cases; this function misses it in 0 of 9,990 over a `q = i/1000` sweep.

    THE MECHANISM IS THE FLOATING PRODUCT, AND IT CUTS BOTH WAYS. `0.29 * 100.0` is
    `28.999999999999996`, so a bare `Int()` truncates to 28; but `0.07 * 100.0` is
    `7.000000000000001`, so a bare `ceil` would return 8 for a rank that is exactly 7. Neither
    rounding rule alone is right. So `raw` is snapped to its own floor when it sits within
    `stm_tolerance(raw, 0.0)` of it -- a per-item allowance scaled by THE NUMBER BEING JUDGED
    times `DBL_EPSILON`, never by `n`, never by the caller's `q`, and never `1 + |raw|` -- and
    the strict ceiling is taken otherwise.

    Clamped into `[1, n]` afterwards. `target` is a RANK and is fed to `_search_rank`, never to a
    subscript, so the clamp is about the answer being defined rather than about memory safety;
    `q` is already known finite and inside `[0, 1]` by the time this is called.
    """
    var raw = q * Float64(n)
    var low = Int(raw)
    var target = low
    if raw - Float64(low) > stm_tolerance(raw, 0.0):
        target = low + 1
    if target < 1:
        target = 1
    if target > n:
        target = n
    return target


def _from_profile(
    profile: QuantileProfile, q: Float64, rank_error: Float64, slack: Float64, n: Int
) -> QuantileEstimate:
    """One quantile read off an already-built profile, at the nearest RANK to `q * n`.

    An empty profile has no rung to read, so it is ABSENT rather than `values[0]` -- which would
    be a read past the end of an empty `List` and an uncatchable process abort.
    """
    if len(profile.values) == 0:
        return _absent(STM_EMPTY, n)
    var index = _search_rank(profile, _rank_of(q, n))
    return QuantileEstimate(
        profile.values[index], True, rank_error, slack, n, STM_OK
    )


def quantile_batch(sketch: QuantileSketch, qs: List[Float64]) -> QuantileSeries:
    """Many quantiles from ONE profile build, each with its own presence flag.

    This is the reason `quantile_profile` is a separate step: 100 quantiles through
    `quantile_at` would build 100 identical profiles and cost 100 times as much for the same
    answer. Out-of-range and non-finite entries are marked absent individually rather than
    failing the whole batch.

    @capability quantile_batch
    complexity: O(M * L + len(qs) * log M)
    counts: none
    @endcapability
    """
    var values = List[Float64]()
    var present = List[Bool]()
    var shape = _sketch_ok(sketch)
    if shape != STM_OK:
        return QuantileSeries(values^, present^, 0.0, 0, shape, False)
    var claim = stm_kll_rank_error(sketch.k)
    if not claim.present:
        return QuantileSeries(values^, present^, 0.0, sketch.n, STM_ERR_CAPACITY, False)
    if sketch.n <= 0:
        for _ in range(len(qs)):
            values.append(0.0)
            present.append(False)
        return QuantileSeries(values^, present^, claim.value, 0, STM_EMPTY, True)

    var profile = quantile_profile(sketch)
    if not profile.valid or len(profile.values) == 0:
        for _ in range(len(qs)):
            values.append(0.0)
            present.append(False)
        return QuantileSeries(values^, present^, claim.value, sketch.n, STM_EMPTY, True)
    var slack = claim.value * Float64(sketch.n)
    for i in range(len(qs)):
        var q = qs[i]
        if not stm_finite(q) or q < 0.0 or q > 1.0:
            values.append(0.0)
            present.append(False)
        elif q <= 0.0:
            values.append(sketch.minimum)
            present.append(True)
        elif q >= 1.0:
            values.append(sketch.maximum)
            present.append(True)
        else:
            var one = _from_profile(profile, q, claim.value, slack, sketch.n)
            values.append(one.value)
            present.append(one.present)
    return QuantileSeries(values^, present^, claim.value, sketch.n, STM_OK, True)


def quantile_rank(sketch: QuantileSketch, x: Float64) -> QuantileEstimate:
    """Estimated fraction of the stream at or below `x`, in `[0, 1]`, or ABSENCE.

    The inverse of `quantile_at`, and the direction the error bound is actually stated in:
    the returned fraction is claimed to be within `stm_kll_rank_error(k)` of the true
    fraction. A value below everything seen returns 0.0 and is PRESENT -- that is a computed
    zero, not an absence -- while an empty sketch returns absent.

    @capability quantile_rank
    complexity: O(M * L)
    counts: none
    @endcapability
    """
    var shape = _sketch_ok(sketch)
    if shape != STM_OK:
        return _absent(shape, 0)
    if not stm_finite(x):
        return _absent(STM_ERR_NON_FINITE, sketch.n)
    if sketch.n <= 0:
        return _absent(STM_EMPTY, sketch.n)
    var claim = stm_kll_rank_error(sketch.k)
    if not claim.present:
        return _absent(STM_ERR_CAPACITY, sketch.n)
    var profile = quantile_profile(sketch)
    if not profile.valid or len(profile.values) == 0:
        return _absent(STM_EMPTY, sketch.n)
    var weight = 0
    for j in range(len(profile.values)):
        if profile.values[j] <= x:
            weight = profile.cumulative[j]
        else:
            break
    var fraction = Float64(weight) / Float64(sketch.n)
    return QuantileEstimate(
        fraction, True, claim.value, claim.value * Float64(sketch.n), sketch.n, STM_OK
    )


def quantile_minimum(sketch: QuantileSketch) -> QuantileEstimate:
    """The EXACT smallest observation, or ABSENCE for an empty sketch.

    Exact, not estimated: it is tracked outside the levels so compaction cannot discard it.

    A forged sketch is refused rather than having its `minimum` slot echoed back: a non-finite
    there makes the whole response a typed error, and an `n` that its own levels cannot account
    for is not a stream this value is the minimum of.

    @capability quantile_minimum
    complexity: O(L)
    counts: none
    @endcapability
    """
    var shape = _levels_ok(sketch)
    if shape != STM_OK:
        return _absent(shape, 0)
    var bounds = _bounds_ok(sketch)
    if bounds != STM_OK:
        return _absent(bounds, sketch.n)
    if sketch.n <= 0:
        return _absent(STM_EMPTY, sketch.n)
    return QuantileEstimate(sketch.minimum, True, 0.0, 0.0, sketch.n, STM_OK)


def quantile_maximum(sketch: QuantileSketch) -> QuantileEstimate:
    """The EXACT largest observation, or ABSENCE for an empty sketch.

    @capability quantile_maximum
    complexity: O(L)
    counts: none
    @endcapability
    """
    var shape = _levels_ok(sketch)
    if shape != STM_OK:
        return _absent(shape, 0)
    var bounds = _bounds_ok(sketch)
    if bounds != STM_OK:
        return _absent(bounds, sketch.n)
    if sketch.n <= 0:
        return _absent(STM_EMPTY, sketch.n)
    return QuantileEstimate(sketch.maximum, True, 0.0, 0.0, sketch.n, STM_OK)


def quantile_total_weight(sketch: QuantileSketch) -> Int:
    """`sum_i level_sizes[i] * 2^i`, which must equal `n`, or -1 for an unusable sketch.

    Compaction converts `m` items of weight `2^i` into exactly `m/2` of weight `2^(i+1)`, so
    this re-derived total is `n` at every step. A mismatch means a level array and the stored
    `n` disagree, which is the shape a corrupted snapshot takes, and -1 is returned for an
    unusable sketch rather than 0 because 0 is a legitimate total.

    THE LEVEL COUNT IS CHECKED BEFORE THE SHIFT, and that is not tidiness. `1 << i` wraps once
    `i` reaches 63, so this function used to return a WRAPPED INTEGER under a contract promising
    a non-negative total: 64 level_sizes entries of 1 each summed to exactly -1 -- colliding with
    this function's own "unusable sketch" sentinel -- and other forged shapes returned
    -9223372036854775807. `MAX_STM_LEVELS` was enforced in `quantile_from_snapshot` and nowhere
    on the struct path, which is the path a caller reaches. `_levels_ok` bounds the level count
    at 40 first, so every shift here is at most `2^39` and the whole sum is under `2^57`.

    @capability quantile_total_weight
    complexity: O(L)
    counts: none
    @endcapability
    """
    if _levels_ok(sketch) != STM_OK:
        return -1
    var total = 0
    for i in range(len(sketch.level_sizes)):
        total += sketch.level_sizes[i] * (1 << i)
    return total


def quantile_snapshot(sketch: QuantileSketch) -> QuantileSnapshot:
    """Flat snapshot as an integer header plus a float payload.

    An invalid sketch snapshots as two EMPTY lists, never as a header with no payload: a
    zero-length pair is unambiguously not a sketch, where a bare header would round-trip into
    a plausible empty one and lose the refusal.

    @capability quantile_snapshot
    complexity: O(M + L)
    counts: none
    @endcapability
    """
    var header = List[Int]()
    var values = List[Float64]()
    if _sketch_ok(sketch) != STM_OK:
        return QuantileSnapshot(header^, values^)
    var n_levels = len(sketch.level_sizes)
    header.append(QUANTILE_SNAPSHOT_MAGIC)
    header.append(sketch.k)
    header.append(sketch.seed)
    header.append(sketch.n)
    header.append(n_levels)
    for i in range(n_levels):
        header.append(sketch.level_sizes[i])
    for i in range(n_levels):
        header.append(sketch.compactions[i] if i < len(sketch.compactions) else 0)
    values.append(sketch.minimum)
    values.append(sketch.maximum)
    for j in range(len(sketch.values)):
        values.append(sketch.values[j])
    return QuantileSnapshot(header^, values^)


def quantile_from_snapshot(
    header: List[Int], values: List[Float64]
) -> QuantileSketch:
    """A sketch from a flat snapshot pair, or a refusal naming what was wrong with it.

    Every field is validated, because the caller here is a stored payload and not a
    programmer. In particular: the level sizes must sum to exactly the float payload's length
    minus its two-word header, no level may be negative, the re-derived total weight must
    equal the stored `n`, and every stored value must be finite. A non-finite value would
    flow into a returned quantile, and one non-finite field makes the whole response a typed
    error rather than one field being wrong.

    @capability quantile_from_snapshot
    complexity: O(M + L)
    counts: none
    @endcapability
    """
    if len(header) < QUANTILE_HEADER:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    if header[0] != QUANTILE_SNAPSHOT_MAGIC:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    var k = header[1]
    var seed = header[2]
    var n = header[3]
    var n_levels = header[4]
    var bad = _params_ok(k, seed)
    if bad != STM_OK:
        return _invalid(bad)
    if n < 0 or not stm_items_ok(n):
        return _invalid(STM_ERR_ITEM_BUDGET)
    if n_levels < 1 or n_levels > MAX_STM_LEVELS:
        return _invalid(STM_ERR_LEVEL_OVERFLOW)
    if len(header) != QUANTILE_HEADER + 2 * n_levels:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)

    var sizes = List[Int]()
    var stored = 0
    var weight = 0
    for i in range(n_levels):
        var size = header[QUANTILE_HEADER + i]
        if size < 0 or size > QUANTILE_MAX_K:
            return _invalid(STM_ERR_SNAPSHOT_SHAPE)
        sizes.append(size)
        stored += size
        weight += size * (1 << i)
    if weight != n:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    if len(values) != QUANTILE_VALUE_HEADER + stored:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)

    var comps = List[Int]()
    for i in range(n_levels):
        var count = header[QUANTILE_HEADER + n_levels + i]
        if count < 0:
            return _invalid(STM_ERR_SNAPSHOT_SHAPE)
        comps.append(count)

    var minimum = values[0]
    var maximum = values[1]
    if not stm_finite(minimum) or not stm_finite(maximum):
        return _invalid(STM_ERR_NON_FINITE)
    if n > 0 and minimum > maximum:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    var body = List[Float64]()
    for j in range(stored):
        var value = values[QUANTILE_VALUE_HEADER + j]
        if not stm_finite(value):
            return _invalid(STM_ERR_NON_FINITE)
        body.append(value)
    return QuantileSketch(
        body^, sizes^, comps^, k, n, seed, minimum, maximum, STM_OK, True
    )


def quantile_merge_snapshots(
    header_a: List[Int],
    values_a: List[Float64],
    header_b: List[Int],
    values_b: List[Float64],
) -> QuantileSketch:
    """Merge two flat snapshots directly, for combining partials from two processes.

    @capability quantile_merge_snapshots
    complexity: O((M_a + M_b) log k)
    counts: none
    @endcapability
    """
    return quantile_merge(
        quantile_from_snapshot(header_a, values_a),
        quantile_from_snapshot(header_b, values_b),
    )
