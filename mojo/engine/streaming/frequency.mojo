"""
streaming.frequency — Count-Min frequencies with per-row keyed columns, merge and snapshot.

Classification of every capability here
---------------------------------------
* **existing-frozen, CALLED not rewritten.** `sketch.cms_hash` performs the final column
  reduction for every cell this module touches, reached through `contract.stm_key_bucket`.
  `sketch.create_cms` is called by `frequency_frozen_row_collisions` to READ the frozen row
  seed schedule rather than copy it. `bloom_counting.cb_optimal_hashes` is the frozen
  answer to "how many rows", and `frequency_suggested_depth` routes to it.
* **missing-driver.** Nothing ingests a stream into a Count-Min sketch, and `cms_add` takes
  `mut sketch`, which cannot cross a stateless dispatch. The drivers here take a sketch and
  return one.
* **genuinely-missing.** The per-row keyed column, the flat snapshot, cell-wise merge, the
  total-mass accounting the epsilon bound needs, and heavy hitters.
* **surface-gap.** `CountMinSketch` is owned by `sketch.mojo` and `cms_add` mutates, so the
  frozen surface is not reachable as a value from the SDK. Nothing in `sketch.mojo` changes.

Why the columns are keyed per row: a measured defect, not a preference
---------------------------------------------------------------------
A Count-Min sketch's `depth` exists for exactly one reason. Each row over-estimates an
item's count by more than `e/width * total` with probability at most `1/e`, so taking the
MINIMUM over `depth` INDEPENDENT rows drops that to `e^-depth`. Independence of the rows is
the entire mechanism.

The frozen `create_cms` seeds row `d` with `d * 1000003 + 7`, and the frozen `cms_hash`
reduces `item * seed + 17` modulo 1000003 before modulo `width`. Every one of those seeds is
congruent to 7 modulo 1000003. In the regime where `item * seed` does not overflow, every
row therefore computes THE SAME COLUMN. Measured on this tree:

    cms_hash(5, 7, 100) == cms_hash(5, 1000010, 100) == cms_hash(5, 2000013, 100) == 52

and over the first 20,000 non-negative items at width 4096 all four rows of a depth-4 sketch
agree on 20,000 of 20,000. The minimum is then taken over one number, `depth` buys nothing,
and the `e^-depth` claim is unearned. Worse, the shared modulus makes 0, 1000003 and 2000006
collide in every row: add 1000 copies of item 0 to a 4096x4 frozen sketch and
`cms_query(2000006)` returns 1000, for an item never added, where `e/4096 * 1000 = 0.66` was
the claimed allowance.

The defect is in the SEED SCHEDULE, and `sketch.mojo` is frozen. So `stm_key_bucket` keeps
`cms_hash` as the column reduction and hands it a per-row keyed Philox word instead of the
raw item. The rows are then independent because their INPUTS are independent, whatever the
row seed does. `frequency_frozen_row_collisions` and `frequency_keyed_row_collisions` make
that difference a number the suite and the benchmark assert on, so the justification is
measured on every run rather than asserted in this comment.

The two bounds, and which one is absolute
-----------------------------------------
* **Deterministic and always true, asserted with no probability attached:** the estimate
  never UNDER-states the true count (every cell holding the item has at least the item's own
  mass in it), and it never exceeds the sketch's TOTAL mass (a cell holds at most everything
  that was ever added). Both are asserted absolutely in the suite.
* **Probabilistic, and therefore stated with its confidence:** the over-estimate exceeds
  `stm_cms_epsilon(width) * total` for a given item with probability at most
  `stm_cms_delta(depth)`. The suite measures the actual over-estimate for every item of a
  real Zipf-like distribution against exact counts, asserts the MEAN over-estimate sits
  inside the epsilon allowance, and asserts the FRACTION of items breaching it sits inside a
  stated multiple of delta. Asserting that no item ever breaches an `e^-depth`-probability
  bound would be asserting that an unlikely event is impossible.

Mergeability
------------
Cell-wise addition is associative and commutative, so `merge(a, b) == sketch(A ++ B)` cell
for cell, EXACTLY, and the suite asserts it with `==`. Merge is NOT idempotent -- adding a
sketch to itself doubles every count, which is correct arithmetic and the reason a replayed
partial must be de-duplicated by the caller. That asymmetry with `distinct.distinct_merge`
is stated because assuming the wrong one silently double counts.

Bounding memory is not bounding work
------------------------------------
Memory is `depth * width` cells, and `depth * width` is checked with the frozen
`dims_fit`-backed `stm_cells_fit` so the product is never formed as a wrapping multiply.
Work is `n * depth` keyed hashes -- ONE PER ROW PER ITEM, not one per item -- and is charged
as that product through `stm_work_fits`. Charging `n + depth` for an `n * depth` loop is the
failure this package refuses to repeat: it makes a small, cheap-looking request burn minutes.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: true
seed_requirements: required
supported_dtypes: int64, float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_streaming_frequency.mojo
benchmark: benchmarks/mojo_benchmarks/bench_streaming.mojo
docs: gitbook/engine/streaming-sketches.md
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from bloom_counting import cb_optimal_hashes
from sketch import cms_hash, create_cms

from streaming.contract import (
    MAX_STM_WORK,
    STM_ERR_COUNT,
    STM_ERR_DEPTH,
    STM_ERR_INCOMPATIBLE_MERGE,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_ITEM_BUDGET,
    STM_ERR_MEMORY_BUDGET,
    STM_ERR_PARAM_RANGE,
    STM_ERR_SEED_RANGE,
    STM_ERR_SNAPSHOT_SHAPE,
    STM_ERR_WIDTH,
    STM_ERR_WORK_BUDGET,
    STM_OK,
    stm_cells_fit,
    stm_cms_delta,
    stm_cms_epsilon,
    stm_finite,
    stm_items_ok,
    stm_key_bucket,
    stm_seed_ok,
    stm_work_fits,
)

#: Snapshot tag, so a distinct-count snapshot is refused here rather than reinterpreted as
#: counter cells and turned into confident wrong frequencies.
comptime FREQUENCY_SNAPSHOT_MAGIC: Int = 0x46524551

#: Header words before the cells: magic, width, depth, seed, total.
comptime FREQUENCY_HEADER: Int = 5

#: Total mass ceiling. Two of these sum during a merge, and 2^41 is nowhere near the Int64
#: range, so the merge addition cannot wrap. Without a mass ceiling the merge of two
#: near-maximal snapshots would wrap to a NEGATIVE total and the epsilon allowance computed
#: from it would be negative -- a bound that accepts everything.
comptime MAX_STM_MASS: Int = 1 << 40

#: `contract.MAX_STM_WIDTH` / `MAX_STM_DEPTH`, restated here because a declared ceiling must
#: name a constant in the SAME file as the kernel that tests it -- otherwise the declaration
#: and the check are two different numbers that can drift apart. These are the constants this
#: file's guards test against, and `test_streaming_frequency.mojo` asserts they still equal
#: the contract's, so the copy cannot rot silently either.
comptime FREQUENCY_MAX_WIDTH: Int = 1 << 14
comptime FREQUENCY_MAX_DEPTH: Int = 16


struct FrequencySketch(Copyable, Movable):
    """A Count-Min frequency sketch, as a value the caller owns.

    `valid == False` means this is not a sketch, `cells` is empty and `status` says why.
    Declared in this file: a struct owned by another module is silently dropped from the
    runtime contract, which is also why the frozen `CountMinSketch` stays internal.

    `cells` is row-major, `depth` rows of `width` columns. `row * width + col` cannot wrap
    once `depth <= 16` and `width <= 16384` are validated, which bounds the index at 262,128.
    """

    var cells: List[Int]
    var width: Int
    var depth: Int
    var total: Int
    var seed: Int
    var status: Int
    var valid: Bool

    fn __init__(
        out self,
        cells: List[Int],
        width: Int,
        depth: Int,
        total: Int,
        seed: Int,
        status: Int,
        valid: Bool,
    ):
        self.cells = cells.copy()
        self.width = width
        self.depth = depth
        self.total = total
        self.seed = seed
        self.status = status
        self.valid = valid


struct FrequencyEstimate(Copyable, Movable):
    """An estimated count with the bounds that apply to it, or its absence.

    `present == False` means there was no sketch to ask -- and `count` is 0, which is not an
    answer. `present == True` with `count == 0` IS an answer, and a deliberate one: a sketch
    with `total == 0` had nothing added, so every item's count is exactly zero and reporting
    absence there would hide a fact the sketch does know. The contrast with
    `quantiles.quantile_at`, where an empty sketch genuinely has no quantile to report, is
    the whole distinction between "could not compute" and "computed, and it is zero".

    `slack` is `epsilon * total`, the ABSOLUTE additive allowance for this query, so a caller
    reads `count`, `count - slack` and `count` as the interval without recomputing anything.
    """

    var count: Int
    var present: Bool
    var epsilon: Float64
    var delta: Float64
    var slack: Float64
    var total: Int
    var status: Int

    fn __init__(
        out self,
        count: Int,
        present: Bool,
        epsilon: Float64,
        delta: Float64,
        slack: Float64,
        total: Int,
        status: Int,
    ):
        self.count = count
        self.present = present
        self.epsilon = epsilon
        self.delta = delta
        self.slack = slack
        self.total = total
        self.status = status


struct FrequencyList(Copyable, Movable):
    """A list of counts or of keys, WITH a presence flag and a status.

    A bare `List[Int]` return cannot say why it is empty, and this module has two answers that
    are both legitimately empty: "no candidate met the threshold" and "the request was refused".
    Collapsing them is not a cosmetic problem -- `frequency_heavy_hitters` with a NaN threshold
    returned an empty list, which its own contract defines as "no heavy hitters", so a
    non-finite parameter was silently ANSWERED. `present == False` is now the refusal and
    `status` names it; `present == True` with an empty `items` is the real "none of them".

    Declared in this file, like every other struct here: a struct owned by another module is
    silently dropped from the runtime contract.
    """

    var items: List[Int]
    var present: Bool
    var n_items: Int
    var status: Int

    fn __init__(out self, items: List[Int], present: Bool, n_items: Int, status: Int):
        self.items = items.copy()
        self.present = present
        self.n_items = n_items
        self.status = status


fn _invalid(status: Int) -> FrequencySketch:
    """Not a sketch, with the reason."""
    return FrequencySketch(List[Int](), 0, 0, 0, 0, status, False)


fn _no_list(status: Int) -> FrequencyList:
    """No list, with the reason. `items` is empty and that emptiness is NOT an answer."""
    return FrequencyList(List[Int](), False, 0, status)


fn _absent(status: Int) -> FrequencyEstimate:
    """No estimate, with the reason. `count` is 0 and means nothing."""
    return FrequencyEstimate(0, False, 0.0, 0.0, 0.0, 0, status)


fn _params_ok(width: Int, depth: Int, seed: Int) -> Int:
    """`STM_OK`, or the status that refuses these parameters."""
    if width < 1 or width > FREQUENCY_MAX_WIDTH:
        return STM_ERR_WIDTH
    if depth < 1 or depth > FREQUENCY_MAX_DEPTH:
        return STM_ERR_DEPTH
    if not stm_seed_ok(seed):
        return STM_ERR_SEED_RANGE
    if not stm_cells_fit(depth, width, depth * width):
        return STM_ERR_MEMORY_BUDGET
    return STM_OK


fn _shape_ok(sketch: FrequencySketch) -> Int:
    """`STM_OK`, or the status refusing this sketch's SHAPE. O(1), and every entry point calls it.

    THE STRUCT PATH IS A CALLER PATH. `FrequencySketch` is decoded from caller JSON by the
    generated dispatch, which validates FIELD TYPES and no cross-field invariant, so
    `valid: true` beside `width: 512`, `depth: 4` and an EMPTY `cells` list is an accepted
    request. Every subscript in this module is `row * sketch.width + col` -- the caller's width,
    never `len(cells)`. Measured before this function existed, five public functions each took one
    well-typed request and killed the worker process on an uncatchable bounds assertion:
    `frequency_query`, `frequency_query_many`, `frequency_heavy_hitters`, `frequency_add` and
    `frequency_cell`. `try/except` in the dispatch arm contained none of them.

    `frequency_cell` was the pointed one. It guarded `row < sketch.depth` and `col <
    sketch.width` -- fields of the SAME caller-supplied struct -- so `(0, 0)` walked off an empty
    list while both guards passed. A bound the caller supplies is not a bound.

    The relation is `depth * width == len(cells)`, and it is decided by DIVISION through the
    frozen `sparse_numerics.csr.dims_fit` (via `stm_cells_fit`), never by forming the product:
    `3 * 6148914691236517206 == 2` in wrapping 64-bit arithmetic, which is how a sibling package
    walked past exactly this guard and crashed. `total` is range-checked in the same breath
    because `epsilon * total` is the slack attached to every estimate, and a negative `total`
    makes that a bound which accepts everything.

    This relation is not expressible in a `counts:` block: the manifest grammar's `len(NAME)`
    takes a PARAMETER name, and `len(sketch.cells)` is a struct field, which the checker reports
    as `relation_unknown_parameter`. The kernel is the only place it can live.
    """
    if not sketch.valid:
        return STM_ERR_INVALID_SKETCH
    var bad = _params_ok(sketch.width, sketch.depth, sketch.seed)
    if bad != STM_OK:
        return bad
    if not stm_cells_fit(sketch.depth, sketch.width, len(sketch.cells)):
        return STM_ERR_SNAPSHOT_SHAPE
    if sketch.total < 0 or sketch.total > MAX_STM_MASS:
        return STM_ERR_ITEM_BUDGET
    return STM_OK


fn _cell_in_range(value: Int, total: Int) -> Bool:
    """True when one counter cell is a possible counter value for this sketch's mass.

    A NEGATIVE cell would let the minimum over rows fall BELOW the true count and destroy the one
    property Count-Min guarantees absolutely. A cell above `total` means the header and the body
    disagree, so the `epsilon * total` slack reported beside the estimate is a bound on nothing.
    Checked per cell READ rather than by scanning the table, so `frequency_query` stays O(depth)
    and `frequency_cell` stays O(1) -- the values that could produce a wrong answer for a given
    query are exactly the values that query touches.
    """
    return value >= 0 and value <= total


fn _cells_ok(sketch: FrequencySketch) -> Int:
    """`STM_OK`, or the status refusing this sketch's cell VALUES. O(depth * width).

    Called only from the entry points that are already O(depth * width) -- the ones that copy or
    emit the whole table. Charging a full table scan to an O(depth) point query would be the
    cheap-guard-expensive-request inversion this package charges its budgets to avoid.
    """
    var bad = _shape_ok(sketch)
    if bad != STM_OK:
        return bad
    for i in range(len(sketch.cells)):
        if not _cell_in_range(sketch.cells[i], sketch.total):
            return STM_ERR_SNAPSHOT_SHAPE
    return STM_OK


fn frequency_empty(width: Int, depth: Int, seed: Int) -> FrequencySketch:
    """An empty sketch of `depth` rows by `width` columns, keyed by `seed`.

    Valid, with `total == 0`. Every query against it answers 0 and is PRESENT, because
    nothing having been added determines every count exactly.

    @capability frequency_empty
    complexity: O(depth * width)
    counts:
    - dim width <= FREQUENCY_MAX_WIDTH [kernel_validated]
    - dim depth <= FREQUENCY_MAX_DEPTH [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(width, depth, seed)
    if bad != STM_OK:
        return _invalid(bad)
    var cells = List[Int]()
    for _ in range(depth * width):
        cells.append(0)
    return FrequencySketch(cells^, width, depth, 0, seed, STM_OK, True)


fn frequency_add(sketch: FrequencySketch, item: Int, count: Int) -> FrequencySketch:
    """`sketch` with `count` more occurrences of `item`, as a new value.

    A negative `count` is refused rather than applied. Count-Min's one absolutely reliable
    property is that it never under-states, and that property depends on every increment
    being non-negative; allowing a decrement silently converts the sketch into one whose
    estimate can be below the truth while still reporting the same bounds.

    `sketch` arrives from caller JSON, so `_cells_ok` relates `len(cells)` to its own `depth` and
    `width` fields before the first `d * sketch.width + col` write. Without it, `width: 512` beside
    an empty cell list killed the worker. The full cell scan is free here: this function copies
    the whole table anyway.

    @capability frequency_add
    complexity: O(depth * width)
    counts: none
    @endcapability
    """
    var shape = _cells_ok(sketch)
    if shape != STM_OK:
        return _invalid(shape)
    if count < 0:
        return _invalid(STM_ERR_PARAM_RANGE)
    if count > MAX_STM_MASS or sketch.total > MAX_STM_MASS - count:
        return _invalid(STM_ERR_ITEM_BUDGET)
    var cells = sketch.cells.copy()
    for d in range(sketch.depth):
        var col = stm_key_bucket(sketch.seed, d, item, sketch.width)
        if col < 0:
            return _invalid(STM_ERR_WIDTH)
        cells[d * sketch.width + col] += count
    return FrequencySketch(
        cells^, sketch.width, sketch.depth, sketch.total + count, sketch.seed,
        STM_OK, True,
    )


fn frequency_ingest(
    items: List[Int], width: Int, depth: Int, seed: Int
) -> FrequencySketch:
    """A sketch of every element of `items`, each counted once.

    The element count is `len(items)` and is never a parameter, which removes the
    `n > len(v)` class from this entry point by construction.

    @capability frequency_ingest
    complexity: O(len(items) * depth + depth * width)
    counts:
    - dim width <= FREQUENCY_MAX_WIDTH [kernel_validated]
    - dim depth <= FREQUENCY_MAX_DEPTH [kernel_validated]
    @endcapability
    """
    return frequency_ingest_prefix(items, len(items), width, depth, seed)


fn frequency_ingest_prefix(
    items: List[Int], n: Int, width: Int, depth: Int, seed: Int
) -> FrequencySketch:
    """A sketch of `items[0..n)`, for replaying a prefix of a stored stream.

    `n` is a redundant count and is validated in BOTH directions before anything is indexed.
    An `n` past the end reads past the `List` end, which is an abort `try/except` cannot
    contain: it kills the worker and every dataset resident in it. A negative `n` reads
    nothing rather than aborting, and is still refused, because "sketch of minus three
    items" is not a request with an answer.

    The work charge is the PRODUCT `n * depth`, because that is how many keyed hashes run.

    @capability frequency_ingest_prefix
    complexity: O(n * depth + depth * width)
    counts:
    - n <= len(items) [kernel_validated]
    - dim width <= FREQUENCY_MAX_WIDTH [kernel_validated]
    - dim depth <= FREQUENCY_MAX_DEPTH [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(width, depth, seed)
    if bad != STM_OK:
        return _invalid(bad)
    if n < 0 or n > len(items):
        return _invalid(STM_ERR_COUNT)
    if not stm_items_ok(n) or n > MAX_STM_MASS:
        return _invalid(STM_ERR_ITEM_BUDGET)
    if not stm_work_fits(n, depth, MAX_STM_WORK):
        return _invalid(STM_ERR_WORK_BUDGET)

    var cells = List[Int]()
    for _ in range(depth * width):
        cells.append(0)
    for i in range(n):
        for d in range(depth):
            var col = stm_key_bucket(seed, d, items[i], width)
            if col < 0:
                return _invalid(STM_ERR_WIDTH)
            cells[d * width + col] += 1
    return FrequencySketch(cells^, width, depth, n, seed, STM_OK, True)


fn frequency_ingest_weighted(
    items: List[Int], weights: List[Int], width: Int, depth: Int, seed: Int
) -> FrequencySketch:
    """A sketch of `items` with `weights[i]` occurrences of `items[i]`.

    For a pre-aggregated stream, where the payload is already `(key, count)` pairs. The two
    lists must be the same length; a mismatch is refused rather than truncated to the shorter
    one, because truncating drops mass silently and the epsilon bound is stated relative to
    total mass.

    @capability frequency_ingest_weighted
    complexity: O(len(items) * depth + depth * width)
    counts:
    - dim width <= FREQUENCY_MAX_WIDTH [kernel_validated]
    - dim depth <= FREQUENCY_MAX_DEPTH [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(width, depth, seed)
    if bad != STM_OK:
        return _invalid(bad)
    var n = len(items)
    if len(weights) != n:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    if not stm_items_ok(n):
        return _invalid(STM_ERR_ITEM_BUDGET)
    if not stm_work_fits(n, depth, MAX_STM_WORK):
        return _invalid(STM_ERR_WORK_BUDGET)

    var total = 0
    for i in range(n):
        if weights[i] < 0:
            return _invalid(STM_ERR_PARAM_RANGE)
        if weights[i] > MAX_STM_MASS or total > MAX_STM_MASS - weights[i]:
            return _invalid(STM_ERR_ITEM_BUDGET)
        total += weights[i]

    var cells = List[Int]()
    for _ in range(depth * width):
        cells.append(0)
    for i in range(n):
        for d in range(depth):
            var col = stm_key_bucket(seed, d, items[i], width)
            if col < 0:
                return _invalid(STM_ERR_WIDTH)
            cells[d * width + col] += weights[i]
    return FrequencySketch(cells^, width, depth, total, seed, STM_OK, True)


fn frequency_merge(a: FrequencySketch, b: FrequencySketch) -> FrequencySketch:
    """Cell-wise sum of `a` and `b` — EXACTLY the sketch of `A ++ B`.

    Refuses when width, depth or seed differ: three different shapes and two different hash
    functions have no cell correspondence, and picking one would be inventing an answer for
    a caller who mixed up two sketches.

    NOT idempotent. `merge(a, a)` doubles every count, which is the correct arithmetic for
    concatenating a stream with itself and the reason a replayed partial snapshot must be
    de-duplicated by the caller. `distinct.distinct_merge` IS idempotent, and confusing the
    two silently double counts.

    Both inputs are validated against their OWN count fields, not just for `valid`. A merge that
    accepted a forged empty used to emit a `valid: true` sketch that aborts one dispatch later,
    in whoever queries it -- a surviving call that manufactures a crash for the next caller.

    @capability frequency_merge
    complexity: O(depth * width)
    counts: none
    @endcapability
    """
    var shape_a = _cells_ok(a)
    if shape_a != STM_OK:
        return _invalid(shape_a)
    var shape_b = _cells_ok(b)
    if shape_b != STM_OK:
        return _invalid(shape_b)
    if a.width != b.width or a.depth != b.depth or a.seed != b.seed:
        return _invalid(STM_ERR_INCOMPATIBLE_MERGE)
    if len(a.cells) != len(b.cells):
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    if a.total > MAX_STM_MASS - b.total:
        return _invalid(STM_ERR_ITEM_BUDGET)
    var out = List[Int]()
    for i in range(len(a.cells)):
        out.append(a.cells[i] + b.cells[i])
    return FrequencySketch(
        out^, a.width, a.depth, a.total + b.total, a.seed, STM_OK, True
    )


fn frequency_query(sketch: FrequencySketch, item: Int) -> FrequencyEstimate:
    """Estimated count of `item`: the MINIMUM over the rows, with its bounds attached.

    The minimum is what makes the estimate never under-state: every row's cell for this item
    contains the item's own mass plus whatever else collided there, so every row is an upper
    bound and the smallest of them is the tightest one available.

    `_shape_ok` first, in O(1), because `d * sketch.width + col` indexes by the CALLER's `width`
    and a forged empty `cells` list otherwise aborts the worker here. Each cell is then
    range-checked as it is read, which keeps this function O(depth) instead of paying for a whole
    table scan on a point query.

    @capability frequency_query
    complexity: O(depth)
    counts: none
    @endcapability
    """
    var shape = _shape_ok(sketch)
    if shape != STM_OK:
        return _absent(shape)
    var eps = stm_cms_epsilon(sketch.width)
    var dlt = stm_cms_delta(sketch.depth)
    if not eps.present or not dlt.present:
        return _absent(STM_ERR_SNAPSHOT_SHAPE)
    var best = -1
    for d in range(sketch.depth):
        var col = stm_key_bucket(sketch.seed, d, item, sketch.width)
        if col < 0:
            return _absent(STM_ERR_WIDTH)
        var c = sketch.cells[d * sketch.width + col]
        if not _cell_in_range(c, sketch.total):
            return _absent(STM_ERR_SNAPSHOT_SHAPE)
        if best < 0 or c < best:
            best = c
    if best < 0:
        return _absent(STM_ERR_DEPTH)
    return FrequencyEstimate(
        best, True, eps.value, dlt.value, eps.value * Float64(sketch.total),
        sketch.total, STM_OK,
    )


fn frequency_query_many(
    sketch: FrequencySketch, items: List[Int]
) -> FrequencyList:
    """Estimated counts for every element of `items`, in order, or a typed refusal.

    Never a list of zeros for a bad sketch: a same-length list of zeros is indistinguishable
    from a real answer. And never a bare empty list either, because `items` being empty is a
    legitimate request whose answer is an empty list -- so the refusal rides in `present` and
    `status`, and `present == True` with no items means the caller asked about nothing.

    @capability frequency_query_many
    complexity: O(len(items) * depth)
    counts: none
    @endcapability
    """
    var shape = _shape_ok(sketch)
    if shape != STM_OK:
        return _no_list(shape)
    if not stm_work_fits(len(items), sketch.depth, MAX_STM_WORK):
        return _no_list(STM_ERR_WORK_BUDGET)
    var out = List[Int]()
    for i in range(len(items)):
        var est = frequency_query(sketch, items[i])
        if not est.present:
            return _no_list(est.status)
        out.append(est.count)
    var n = len(out)
    return FrequencyList(out^, True, n, STM_OK)


fn frequency_heavy_hitters(
    sketch: FrequencySketch, candidates: List[Int], min_fraction: Float64
) -> FrequencyList:
    """Those `candidates` whose estimated count is at least `min_fraction * total`.

    Candidates are supplied rather than discovered, because a Count-Min sketch cannot
    enumerate its own keys -- it stores counters, not items. Pretending otherwise is the
    classic misuse; the honest surface takes the candidate set from the caller, who has it.

    Order is preserved from `candidates`, so the result is deterministic.

    A NON-FINITE `min_fraction` IS REFUSED, AND THAT IS THE POINT OF THE RETURN TYPE. `NaN < 0.0`
    and `NaN > 1.0` are BOTH false, so a NaN sailed through a plain range gate; `threshold` became
    NaN; every `count >= NaN` was false; and the function returned an empty list, which its own
    contract read as "no heavy hitters". A refusal was reported as an answer. `stm_finite` is now
    checked FIRST -- an ordering that matters, because no comparison against a NaN can catch it --
    and `present == False` under `STM_ERR_PARAM_RANGE` is a refusal the caller can see, which a
    bare `List[Int]` return could not express at all.

    @capability frequency_heavy_hitters
    complexity: O(len(candidates) * depth)
    counts: none
    @endcapability
    """
    var shape = _shape_ok(sketch)
    if shape != STM_OK:
        return _no_list(shape)
    if not stm_finite(min_fraction) or min_fraction < 0.0 or min_fraction > 1.0:
        return _no_list(STM_ERR_PARAM_RANGE)
    if not stm_work_fits(len(candidates), sketch.depth, MAX_STM_WORK):
        return _no_list(STM_ERR_WORK_BUDGET)
    var threshold = min_fraction * Float64(sketch.total)
    var out = List[Int]()
    for i in range(len(candidates)):
        var est = frequency_query(sketch, candidates[i])
        if not est.present:
            return _no_list(est.status)
        if Float64(est.count) >= threshold:
            out.append(candidates[i])
    var n = len(out)
    return FrequencyList(out^, True, n, STM_OK)


fn frequency_cell(sketch: FrequencySketch, row: Int, col: Int) -> Int:
    """One counter cell, or -1 when `(row, col)` is outside the table.

    `row` and `col` are SUBSCRIPTS, so both are guarded in both directions. A negative count
    is harmless -- `range(-3)` reads nothing -- but a negative index is fatal: `cells[-1]`
    aborts the process, and `try/except` does not contain it. -1 is returned rather than 0
    because 0 is a legitimate cell value.

    GUARDING AGAINST THE RIGHT QUANTITY. `row < sketch.depth` and `col < sketch.width` are
    necessary and were not sufficient: `depth` and `width` are fields of the same
    caller-supplied struct, so `frequency_cell(sketch, 0, 0)` on `depth: 4, width: 512, cells:
    []` passed both guards and walked off an empty list -- in the one function whose docstring
    promised that a negative index aborts the process and is therefore guarded. `_shape_ok`
    relates `len(cells)` to `depth * width` by division first, so the row/col guards are then
    guards against the real table.

    The two `dim` relations below stay `[kernel_validated]`, and now honestly: the pre-call guard
    stands down because the kernel really does the check, against the payload and not against a
    number the caller chose. The relation that matters -- `depth * width == len(cells)` -- cannot
    be written here, because the manifest grammar's `len(NAME)` takes a parameter name and
    `sketch.cells` is a struct field; `_shape_ok` documents it and enforces it.

    @capability frequency_cell
    complexity: O(1)
    counts:
    - dim row <= FREQUENCY_MAX_DEPTH [kernel_validated]
    - dim col <= FREQUENCY_MAX_WIDTH [kernel_validated]
    @endcapability
    """
    if _shape_ok(sketch) != STM_OK:
        return -1
    if row < 0 or row >= sketch.depth:
        return -1
    if col < 0 or col >= sketch.width:
        return -1
    var value = sketch.cells[row * sketch.width + col]
    if not _cell_in_range(value, sketch.total):
        return -1
    return value


fn frequency_snapshot(sketch: FrequencySketch) -> List[Int]:
    """Flat snapshot: `[magic, width, depth, seed, total] ++ cells`.

    An unusable sketch snapshots as an EMPTY list, never as a header with no body: a
    zero-length payload is unambiguously not a sketch, where a bare header would round-trip
    into a plausible empty one and lose the refusal. That promise was broken on the struct path:
    a forged sketch with `width: 512, depth: 4` and no cells emitted
    `[1179796817, 512, 4, 0, 0]` -- exactly the bare header the docstring rules out. `_cells_ok`
    is the whole fix, and the suite pins the empty list.

    @capability frequency_snapshot
    complexity: O(depth * width)
    counts: none
    @endcapability
    """
    var out = List[Int]()
    if _cells_ok(sketch) != STM_OK:
        return out^
    out.append(FREQUENCY_SNAPSHOT_MAGIC)
    out.append(sketch.width)
    out.append(sketch.depth)
    out.append(sketch.seed)
    out.append(sketch.total)
    for i in range(len(sketch.cells)):
        out.append(sketch.cells[i])
    return out^


fn frequency_from_snapshot(snapshot: List[Int]) -> FrequencySketch:
    """A sketch from a flat snapshot, or a refusal naming what was wrong with it.

    Validated against the header IN BAND, so a truncated payload is refused instead of read
    to whatever length arrived. Every cell must be non-negative and no cell may exceed
    `total`: a cell above the declared total means the header and the body disagree, and the
    epsilon allowance computed from that total would then be a bound on nothing. A negative
    cell would let the minimum over rows fall below the true count and destroy the one
    property Count-Min guarantees absolutely.

    @capability frequency_from_snapshot
    complexity: O(len(snapshot))
    counts: none
    @endcapability
    """
    if len(snapshot) < FREQUENCY_HEADER:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    if snapshot[0] != FREQUENCY_SNAPSHOT_MAGIC:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    var width = snapshot[1]
    var depth = snapshot[2]
    var seed = snapshot[3]
    var total = snapshot[4]
    var bad = _params_ok(width, depth, seed)
    if bad != STM_OK:
        return _invalid(bad)
    if total < 0 or total > MAX_STM_MASS:
        return _invalid(STM_ERR_ITEM_BUDGET)
    var n_cells = depth * width
    if len(snapshot) != FREQUENCY_HEADER + n_cells:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    var cells = List[Int]()
    for i in range(n_cells):
        var value = snapshot[FREQUENCY_HEADER + i]
        if not _cell_in_range(value, total):
            return _invalid(STM_ERR_SNAPSHOT_SHAPE)
        cells.append(value)
    var out = FrequencySketch(cells^, width, depth, total, seed, STM_OK, True)
    # ONE predicate, reached by both the snapshot path and the struct path, so the two cannot
    # drift into two behaviours under one name. This is also the assertion that every sketch
    # this module hands out satisfies `_cells_ok`, which the suite checks directly.
    var shape = _cells_ok(out)
    if shape != STM_OK:
        return _invalid(shape)
    return out^


fn frequency_merge_snapshots(a: List[Int], b: List[Int]) -> FrequencySketch:
    """Merge two flat snapshots directly, for combining partials from two processes.

    @capability frequency_merge_snapshots
    complexity: O(len(a) + len(b))
    counts: none
    @endcapability
    """
    return frequency_merge(frequency_from_snapshot(a), frequency_from_snapshot(b))


fn frequency_suggested_depth(width: Int, n_items: Int) -> Int:
    """Row count to use, from the frozen `bloom_counting.cb_optimal_hashes`.

    The frozen answer to "how many hash functions for this many cells and this many items"
    is `(size / n_items) * ln 2`, and it is the same optimisation here: rows cost work per
    item and buy failure probability. Clamped into `[1, FREQUENCY_MAX_DEPTH]` rather than returned
    raw, because the frozen function can return 0 for a saturated table and 0 rows is not a
    sketch.

    @capability frequency_suggested_depth
    complexity: O(1)
    counts:
    - dim width <= FREQUENCY_MAX_WIDTH [kernel_validated]
    @endcapability
    """
    if width < 1 or width > FREQUENCY_MAX_WIDTH or n_items < 1:
        return 1
    var suggested = cb_optimal_hashes(width, n_items)
    if suggested < 1:
        return 1
    if suggested > FREQUENCY_MAX_DEPTH:
        return FREQUENCY_MAX_DEPTH
    return suggested


fn frequency_frozen_row_collisions(items: List[Int], width: Int, depth: Int) -> Int:
    """How many of `items` have ALL `depth` frozen rows landing in the same column.

    The row seeds come from the frozen `sketch.create_cms(width, depth)` and the columns from
    the frozen `sketch.cms_hash`, so this measures the frozen schedule rather than a copy of
    it. For a schedule with independent rows this should be about `len(items) / width^(depth-1)`
    -- effectively zero. Measured on this tree it is `len(items)`: every row agrees on every
    item, because every frozen row seed is congruent to 7 modulo 1000003.

    This function exists so the justification for keying is a number the suite asserts on,
    not a claim in a docstring that could rot.

    @capability frequency_frozen_row_collisions
    complexity: O(len(items) * depth)
    counts:
    - dim width <= FREQUENCY_MAX_WIDTH [kernel_validated]
    - dim depth <= FREQUENCY_MAX_DEPTH [kernel_validated]
    @endcapability
    """
    if width < 1 or width > FREQUENCY_MAX_WIDTH or depth < 2 or depth > FREQUENCY_MAX_DEPTH:
        return -1
    if not stm_work_fits(len(items), depth, MAX_STM_WORK):
        return -1
    var frozen = create_cms(width, depth)
    var collisions = 0
    for i in range(len(items)):
        var first = cms_hash(items[i], frozen.hash_seeds[0], width)
        var all_same = True
        for d in range(1, depth):
            if cms_hash(items[i], frozen.hash_seeds[d], width) != first:
                all_same = False
        if all_same:
            collisions += 1
    return collisions


fn frequency_keyed_row_collisions(
    items: List[Int], width: Int, depth: Int, seed: Int
) -> Int:
    """The same measurement for the keyed columns this module actually uses.

    Independent rows make an all-rows agreement vanishingly rare, so this should be near
    zero where `frequency_frozen_row_collisions` is `len(items)`. The pair is the evidence
    that the keying does the thing it is there to do.

    @capability frequency_keyed_row_collisions
    complexity: O(len(items) * depth)
    counts:
    - dim width <= FREQUENCY_MAX_WIDTH [kernel_validated]
    - dim depth <= FREQUENCY_MAX_DEPTH [kernel_validated]
    @endcapability
    """
    if width < 1 or width > FREQUENCY_MAX_WIDTH or depth < 2 or depth > FREQUENCY_MAX_DEPTH:
        return -1
    if not stm_seed_ok(seed):
        return -1
    if not stm_work_fits(len(items), depth, MAX_STM_WORK):
        return -1
    var collisions = 0
    for i in range(len(items)):
        var first = stm_key_bucket(seed, 0, items[i], width)
        var all_same = True
        for d in range(1, depth):
            if stm_key_bucket(seed, d, items[i], width) != first:
                all_same = False
        if all_same:
            collisions += 1
    return collisions
