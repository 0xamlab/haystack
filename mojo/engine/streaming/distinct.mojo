"""
streaming.distinct — HyperLogLog distinct counts that merge and survive a snapshot.

Classification of every capability here
---------------------------------------
* **existing-frozen, CALLED not rewritten.** `sketch.create_hll` allocates the register
  array; `sketch.hll_add` performs the register update (index from the top `p` bits,
  leading-zero run of the rest, keep the maximum); `sketch.hll_count` is the alpha-corrected
  harmonic-mean estimator with its small-range correction; `sketch.leading_zeros` is the bit
  scan underneath. None of that arithmetic is reimplemented here. `_frozen` rebuilds the
  frozen struct around this module's registers precisely so the frozen update runs.
* **missing-driver.** Nothing in the tree ingests a stream into an HLL, and nothing merges
  two of them. `hll_add` takes `mut hll` and one item, which cannot cross a stateless
  dispatch: the sketch would be created and destroyed inside one call. The drivers here take
  a sketch and return a sketch, so the caller holds the state and a partial sketch is a
  value that can be stored, shipped and merged.
* **genuinely-missing.** `distinct_merge` (register-wise maximum), the flat snapshot, and
  the keyed hash. The frozen `hll_hash` takes no seed, so two deployments cannot be given
  independent hash keys and a caller cannot re-key after a bad collision; `stm_key_hash31`
  supplies a keyed 31-bit word and the frozen mixer runs on top of it, which keeps the
  frozen kernel in the path and makes the sketch a function of an explicit seed.
* **surface-gap.** `hll_add`'s `mut` parameter and `HyperLogLog`'s ownership by another
  module both remove it from the SDK contract. Nothing in `sketch.mojo` changes; the
  reachable shape is added here.

Mergeability is the property that makes this worth having
---------------------------------------------------------
An HLL register holds the maximum leading-zero run seen for that register. Maximum is
associative, commutative and idempotent, so

    merge(sketch(A), sketch(B))  ==  sketch(A ++ B)

holds EXACTLY -- register for register, bit for bit -- and the hand-written suite asserts it
with `==` and no tolerance at all. That is a stronger statement than the sketch's accuracy
claim and it is worth separating: merging is exact, ESTIMATING is approximate. Merge is also
idempotent (`merge(a, a) == a` in registers), which is what makes it safe to replay a
partial snapshot after a crash without double counting a distinct item.

Idempotence has one deliberate exception: `n_ingested` is a count of ADD CALLS, not of
distinct items, and it sums on merge. It is reported so a caller can tell "no data" from
"data whose cardinality is small", and it is not part of the cardinality answer.

The bound is a claim, and it is checked
---------------------------------------
`stm_hll_relative_error(p)` returns `1.04 / sqrt(2^p)` -- ONE standard deviation of the
relative error, not a guarantee. The suite and the benchmark compute the exact distinct
count over a real stream and assert the observed relative error sits inside a STATED
multiple of that sigma. Asserting inside one sigma would be asserting a coin lands heads.

Bounding memory is not bounding work
------------------------------------
Memory is `2^precision` register slots, ceilinged by `MAX_STM_PRECISION`. Work is one keyed
hash and one register update per item, so `n * 1` steps, charged against `MAX_STM_WORK` by
division. Both are charged; neither is inferred from the other.

A corrupted snapshot is the non-finite hazard here
-------------------------------------------------
The frozen estimator forms `sum_j 2^-register[j]`. A register of 10^18 makes every term
underflow to 0.0, the sum is 0.0, and the estimate is a division by zero -- an infinity,
which the dispatch refuses, so the WHOLE response becomes a typed error rather than one
field being wrong. A negative register makes the term `2^+big` and the estimate 0.0, which
is worse: a plausible-looking answer. So `distinct_from_snapshot` validates every register
into `[0, 32 - precision]`, the range the frozen `hll_add` can actually produce, and refuses
otherwise. That check is the reason this module can promise a representable answer.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: true
seed_requirements: required
supported_dtypes: int64, float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_streaming_distinct.mojo
benchmark: benchmarks/mojo_benchmarks/bench_streaming.mojo
docs: gitbook/engine/streaming-sketches.md
version_introduced: 0.9.0
deprecation_state: active
@endcapability
"""
from sketch import HyperLogLog, hll_add, hll_count

from streaming.contract import (
    MAX_STM_ITEMS,
    MAX_STM_WORK,
    STM_EMPTY,
    STM_ERR_COUNT,
    STM_ERR_INCOMPATIBLE_MERGE,
    STM_ERR_INVALID_SKETCH,
    STM_ERR_ITEM_BUDGET,
    STM_ERR_PRECISION,
    STM_ERR_SEED_RANGE,
    STM_ERR_SNAPSHOT_SHAPE,
    STM_ERR_WORK_BUDGET,
    STM_OK,
    stm_finite,
    stm_hll_relative_error,
    stm_items_ok,
    stm_key_hash31,
    stm_seed_ok,
    stm_work_fits,
)

#: Snapshot tag. A frequency snapshot fed to `distinct_from_snapshot` is refused on this
#: word rather than reinterpreted as registers, which would produce a confident wrong
#: cardinality from well-formed-looking data.
comptime DISTINCT_SNAPSHOT_MAGIC: Int = 0x44495354

#: Header words before the registers: magic, precision, seed, n_ingested.
comptime DISTINCT_HEADER: Int = 4

#: `contract.MIN_STM_PRECISION` / `MAX_STM_PRECISION`, restated here because a declared
#: ceiling must name a constant in the SAME file as the kernel that tests it -- otherwise
#: the declaration and the check are two different numbers that can drift apart. These are
#: the constants `_params_ok` tests against, and `test_streaming_distinct.mojo` asserts they
#: still equal the contract's, so the copy cannot rot silently either.
comptime DISTINCT_MIN_PRECISION: Int = 4
comptime DISTINCT_MAX_PRECISION: Int = 16


struct DistinctSketch(Copyable, Movable):
    """A HyperLogLog distinct-count sketch, as a value the caller owns.

    `valid == False` means this is not a sketch and `registers` is empty; `status` says
    why. Every function here refuses an invalid input rather than reading its registers, so
    an invalid sketch propagates as a refusal instead of as a wrong number.

    Declared in this file. A struct owned by another module is silently dropped from the
    runtime contract, which would remove this module from the SDK with no error at all --
    which is also why the frozen `sketch.HyperLogLog` is used only internally.
    """

    var registers: List[Int]
    var precision: Int
    var seed: Int
    var n_ingested: Int
    var status: Int
    var valid: Bool

    fn __init__(
        out self,
        registers: List[Int],
        precision: Int,
        seed: Int,
        n_ingested: Int,
        status: Int,
        valid: Bool,
    ):
        self.registers = registers.copy()
        self.precision = precision
        self.seed = seed
        self.n_ingested = n_ingested
        self.status = status
        self.valid = valid


struct DistinctEstimate(Copyable, Movable):
    """A cardinality estimate, or its absence.

    `present == False` means no cardinality exists to report -- an empty sketch, or an
    invalid one -- and `value` is 0.0 and is not an answer. Zero distinct items and "no
    observations" are different facts and this struct keeps them apart: the first is
    `present == True` with `value == 0.0` and cannot arise from a non-empty stream, the
    second is `present == False` under `STM_EMPTY`.

    THAT FIRST SENTENCE IS A CHECKED CLAIM AND NOT A HOPE. It was false once: a caller-supplied
    sketch of all-zero registers with `n_ingested = 5` returned `present == True, value == 0.0`,
    because the frozen small-range branch evaluates `m * ln(m/zeros)` to exactly zero when every
    register is zero. `_sketch_ok` now refuses `n_ingested > 0` beside an all-zero register array
    -- a state the frozen `hll_add` cannot produce, since it always writes at least 1 -- and the
    suite pins it. A present zero here therefore means an empty stream that was genuinely
    measured, and nothing else.

    `relative_error` is the CLAIMED one-sigma relative error for this register count, so a
    caller receives the bound beside the number rather than having to look it up.
    """

    var value: Float64
    var present: Bool
    var relative_error: Float64
    var n_registers: Int
    var n_ingested: Int
    var status: Int

    fn __init__(
        out self,
        value: Float64,
        present: Bool,
        relative_error: Float64,
        n_registers: Int,
        n_ingested: Int,
        status: Int,
    ):
        self.value = value
        self.present = present
        self.relative_error = relative_error
        self.n_registers = n_registers
        self.n_ingested = n_ingested
        self.status = status


fn _invalid(status: Int) -> DistinctSketch:
    """Not a sketch, with the reason."""
    return DistinctSketch(List[Int](), 0, 0, 0, status, False)


fn _absent(status: Int, n_registers: Int, n_ingested: Int) -> DistinctEstimate:
    """No cardinality, with the reason. `value` is 0.0 and means nothing."""
    return DistinctEstimate(0.0, False, 0.0, n_registers, n_ingested, status)


fn _params_ok(precision: Int, seed: Int) -> Int:
    """`STM_OK`, or the status that refuses these parameters."""
    if precision < DISTINCT_MIN_PRECISION or precision > DISTINCT_MAX_PRECISION:
        return STM_ERR_PRECISION
    if not stm_seed_ok(seed):
        return STM_ERR_SEED_RANGE
    return STM_OK


fn _max_register(precision: Int) -> Int:
    """Largest register value the frozen `hll_add` can write at this precision.

    It hashes into 31 bits, spends `precision` of them on the register index, and counts
    the leading-zero run of the remaining `31 - precision` bits plus one.
    """
    return 32 - precision


fn _sketch_ok(sketch: DistinctSketch) -> Int:
    """`STM_OK`, or the status refusing this sketch. O(2^precision).

    THE STRUCT PATH IS A CALLER PATH. `DistinctSketch` is decoded from caller JSON by the
    generated dispatch, which validates FIELD TYPES and no cross-field invariant, so
    `valid: true` beside `precision: 12` and an EMPTY `registers` list is an accepted request.
    `_frozen` then hands that empty list to the frozen `hll_add`/`hll_count`, which index by
    `1 << precision` -- the caller's number, not `len(registers)`. Measured before this function
    existed: `distinct_estimate` died at `sketch.mojo:253` and `distinct_add` at
    `sketch.mojo:218`, both on an uncatchable bounds assertion that `try/except` in the dispatch
    arm did not contain and that takes every dataset resident in the worker with it.

    Four relations, all of which `distinct_from_snapshot` already checked and the struct path
    never reached:

      * `len(registers) == 2^precision` -- the one that stops the abort.
      * every register in `[0, 32 - precision]`, the range the frozen `hll_add` can produce. A
        register of 10^18 underflows every `2^-r` term to zero, so the frozen estimator divides
        by zero and returns an infinity that makes the WHOLE response a typed error; a NEGATIVE
        register drives it to 0.0, which is worse because it looks like an answer.
      * `n_ingested` non-negative and inside the item ceiling.
      * `n_ingested > 0` implies at least one non-zero register -- the cross-field relation,
        below.

    THE CROSS-FIELD RELATION, AND THE WRONG ANSWER IT FIXES
    ------------------------------------------------------
    Every register value is independently legal at 0, and `n_ingested = 5` is independently
    legal, and TOGETHER they are impossible: the frozen `hll_add` computes
    `leading_zeros(w, bits) + 1`, which is at least 1 for every input, so one add call leaves at
    least one register non-zero. A snapshot of `[magic, 4, 0, 5] ++ [0]*16` passed every
    per-field check and produced `distinct_estimate -> value 0.0, present True, status ok` -- a
    stream of five items reported as zero distinct items, which is arithmetically impossible and
    falsified this module's own docstring promise that a present zero "cannot arise from a
    non-empty stream". The frozen small-range branch is where it comes from and it is not wrong:
    with all 16 registers zero, `sum_inv` is 16, the raw estimate `0.673 * 256 / 16 = 10.77` is
    below `2.5 * 16`, so `m * ln(m/zeros) = 16 * ln(1) = 0.0`. The frozen estimator was asked
    about a state no stream can be in. This check is what stops it being asked.
    """
    if not sketch.valid:
        return STM_ERR_INVALID_SKETCH
    var bad = _params_ok(sketch.precision, sketch.seed)
    if bad != STM_OK:
        return bad
    if len(sketch.registers) != (1 << sketch.precision):
        return STM_ERR_SNAPSHOT_SHAPE
    if sketch.n_ingested < 0 or not stm_items_ok(sketch.n_ingested):
        return STM_ERR_ITEM_BUDGET
    var ceiling = _max_register(sketch.precision)
    var touched = 0
    for j in range(len(sketch.registers)):
        var value = sketch.registers[j]
        if value < 0 or value > ceiling:
            return STM_ERR_SNAPSHOT_SHAPE
        if value != 0:
            touched += 1
    if sketch.n_ingested > 0 and touched == 0:
        return STM_ERR_SNAPSHOT_SHAPE
    # A register is touched by at least one add call, and one add call touches at most one
    # register, so more touched registers than add calls is the same impossibility from the
    # other side. Free to check: `touched` is already counted.
    if touched > sketch.n_ingested:
        return STM_ERR_SNAPSHOT_SHAPE
    return STM_OK


fn _frozen(sketch: DistinctSketch) -> HyperLogLog:
    """The frozen `sketch.HyperLogLog` wrapped around these registers.

    This is how the frozen register update and the frozen estimator are reached: the
    arithmetic stays in `sketch.mojo` and only the ownership of the state moves here.
    """
    return HyperLogLog(
        sketch.registers, 1 << sketch.precision, sketch.precision
    )


fn distinct_empty(precision: Int, seed: Int) -> DistinctSketch:
    """An empty sketch with `2^precision` zeroed registers, keyed by `seed`.

    An empty sketch is valid and has no cardinality: `distinct_estimate` reports ABSENT for
    it. That distinction is the point -- an empty sketch is a usable merge identity, and its
    quantity of distinct items is unknown rather than zero.

    @capability distinct_empty
    complexity: O(2^precision)
    counts:
    - dim precision <= DISTINCT_MAX_PRECISION [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(precision, seed)
    if bad != STM_OK:
        return _invalid(bad)
    var regs = List[Int]()
    for _ in range(1 << precision):
        regs.append(0)
    return DistinctSketch(regs^, precision, seed, 0, STM_OK, True)


fn distinct_add(sketch: DistinctSketch, item: Int) -> DistinctSketch:
    """`sketch` with one more item folded in, as a new value.

    The register update is the frozen `sketch.hll_add`; what happens here is the keyed
    pre-hash and the copy-out. Adding an item already seen leaves every register unchanged,
    which is why merge is idempotent.

    `sketch` arrives from caller JSON, so `_sketch_ok` relates `len(registers)` to its own
    `precision` field before the frozen update indexes by that field. Without it, `precision: 12`
    beside an empty register list killed the worker inside `sketch.mojo`.

    @capability distinct_add
    complexity: O(2^precision)
    counts: none
    @endcapability
    """
    var shape = _sketch_ok(sketch)
    if shape != STM_OK:
        return _invalid(shape)
    if not stm_items_ok(sketch.n_ingested + 1):
        return _invalid(STM_ERR_ITEM_BUDGET)
    var h = _frozen(sketch)
    hll_add(h, stm_key_hash31(sketch.seed, 0, item))
    return DistinctSketch(
        h.registers, sketch.precision, sketch.seed, sketch.n_ingested + 1,
        STM_OK, True,
    )


fn distinct_ingest(items: List[Int], precision: Int, seed: Int) -> DistinctSketch:
    """A sketch of every element of `items`.

    The element count is `len(items)` and is never taken as a parameter, which removes the
    `n > len(v)` class from this entry point by construction.

    @capability distinct_ingest
    complexity: O(len(items) + 2^precision)
    counts:
    - dim precision <= DISTINCT_MAX_PRECISION [kernel_validated]
    @endcapability
    """
    return distinct_ingest_prefix(items, len(items), precision, seed)


fn distinct_ingest_prefix(
    items: List[Int], n: Int, precision: Int, seed: Int
) -> DistinctSketch:
    """A sketch of `items[0..n)`, for replaying a prefix of a stored stream.

    `n` is a redundant count and is therefore validated in BOTH directions before anything
    is indexed. A negative `n` would read nothing (`range(-3)` is empty) and an `n` past the
    end would read past the `List` end -- an abort that `try/except` cannot contain and that
    takes every dataset resident in the worker with it. Both are refused with
    `STM_ERR_COUNT`.

    @capability distinct_ingest_prefix
    complexity: O(n + 2^precision)
    counts:
    - n <= len(items) [kernel_validated]
    - dim precision <= DISTINCT_MAX_PRECISION [kernel_validated]
    @endcapability
    """
    var bad = _params_ok(precision, seed)
    if bad != STM_OK:
        return _invalid(bad)
    if n < 0 or n > len(items):
        return _invalid(STM_ERR_COUNT)
    if not stm_items_ok(n):
        return _invalid(STM_ERR_ITEM_BUDGET)
    if not stm_work_fits(n, 1, MAX_STM_WORK):
        return _invalid(STM_ERR_WORK_BUDGET)

    var base = distinct_empty(precision, seed)
    if not base.valid:
        return base^
    var h = _frozen(base)
    for i in range(n):
        hll_add(h, stm_key_hash31(seed, 0, items[i]))
    return DistinctSketch(h.registers, precision, seed, n, STM_OK, True)


fn distinct_merge(a: DistinctSketch, b: DistinctSketch) -> DistinctSketch:
    """The register-wise maximum of `a` and `b` — EXACTLY the sketch of `A ++ B`.

    Refuses rather than guesses when the two were not built by the same rules: differing
    precision means differing register counts and differing index extraction, and differing
    seeds mean two different hash functions, so neither combination has a meaning. Returning
    the larger of the two, or reducing to the smaller precision, would be inventing an
    answer for a caller who mixed up two sketches.

    An empty sketch is the identity, so merging in a partial snapshot that turned out to
    have no data changes nothing.

    Both inputs are validated against their OWN count fields, not just for `valid`. A merge of
    two forged empties used to SURVIVE and return a `valid: true` sketch with no registers and
    `n_ingested: 2` -- poison that aborts one dispatch later, in whoever estimates from it. A
    surviving call that manufactures a crash for the next caller is worse than a crash here.

    @capability distinct_merge
    complexity: O(2^precision)
    counts: none
    @endcapability
    """
    var shape_a = _sketch_ok(a)
    if shape_a != STM_OK:
        return _invalid(shape_a)
    var shape_b = _sketch_ok(b)
    if shape_b != STM_OK:
        return _invalid(shape_b)
    if a.n_ingested > MAX_STM_ITEMS - b.n_ingested:
        return _invalid(STM_ERR_ITEM_BUDGET)
    if a.precision != b.precision or a.seed != b.seed:
        return _invalid(STM_ERR_INCOMPATIBLE_MERGE)
    if len(a.registers) != len(b.registers):
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    var out = List[Int]()
    for j in range(len(a.registers)):
        var x = a.registers[j]
        var y = b.registers[j]
        out.append(x if x > y else y)
    return DistinctSketch(
        out^, a.precision, a.seed, a.n_ingested + b.n_ingested, STM_OK, True
    )


fn distinct_estimate(sketch: DistinctSketch) -> DistinctEstimate:
    """Estimated distinct count, or ABSENCE when there is nothing to estimate.

    The estimator is the frozen `sketch.hll_count`. Absence has two causes and they are kept
    apart from each other and from zero: an invalid sketch is `STM_ERR_INVALID_SKETCH`, a
    sketch nothing was ever added to is `STM_EMPTY`, and neither is `0.0`.

    A non-finite estimate is refused rather than returned, because a non-finite field makes
    the whole response a typed error instead of one field being wrong. It cannot arise from
    a sketch built here -- every register the frozen update writes is at least 1 -- but it
    can arise from a snapshot that was corrupted between processes, so the check stays.

    @capability distinct_estimate
    complexity: O(2^precision)
    counts: none
    @endcapability
    """
    var shape = _sketch_ok(sketch)
    if shape != STM_OK:
        return _absent(shape, 0, 0)
    var m = len(sketch.registers)
    if sketch.n_ingested <= 0:
        return _absent(STM_EMPTY, m, sketch.n_ingested)
    var claim = stm_hll_relative_error(sketch.precision)
    if not claim.present:
        return _absent(STM_ERR_PRECISION, m, sketch.n_ingested)
    var raw = hll_count(_frozen(sketch))
    # One definition of "finite" for the whole package: the contract's. A cardinality below
    # zero is not a cardinality either, so both are folded into `_representable`.
    if not _representable(raw):
        return _absent(STM_ERR_SNAPSHOT_SHAPE, m, sketch.n_ingested)
    var value = _feasible(raw, sketch.n_ingested)
    return DistinctEstimate(
        value, True, claim.value, m, sketch.n_ingested, STM_OK
    )


fn _representable(x: Float64) -> Bool:
    """Finite, per the contract, and non-negative: a cardinality below zero is not one."""
    return stm_finite(x) and x >= 0.0


fn _feasible(raw: Float64, n_ingested: Int) -> Float64:
    """`raw` projected onto `[1, n_ingested]`, the interval a cardinality can actually occupy.

    A stream of `n_ingested` add calls has between 1 and `n_ingested` distinct items. That is
    arithmetic, not an estimate, and the frozen estimator does not know it: it sees only
    registers. So an estimate outside the interval is provably wrong, and the nearest point
    inside is provably closer to the truth -- the projection is never worse than the raw value
    and is usually identical, because a well-formed sketch lands inside.

    It bites on a register array that no stream could have produced. A snapshot of 4095 registers
    at 1 and one at 0, declaring 4,096 add calls, is legal register-by-register and drives the
    frozen small-range correction to `4096 * ln(4096) = 34069.57` -- eight times more distinct
    items than there were add calls. That number now comes back as 4096.0, which is the most a
    4,096-add stream can have, instead of as an impossibility carrying a 1.6% error bar.

    The CLAIMED `relative_error` still describes the estimator and not this projection, which is
    why it is reported separately rather than folded in: the bound is a property of the register
    count, and clamping an out-of-range estimate does not make the bound tighter.
    """
    if n_ingested <= 0:
        return raw
    var ceiling = Float64(n_ingested)
    if raw > ceiling:
        return ceiling
    if raw < 1.0:
        return 1.0
    return raw


fn distinct_snapshot(sketch: DistinctSketch) -> List[Int]:
    """Flat snapshot: `[magic, precision, seed, n_ingested] ++ registers`.

    Flat because a snapshot has to cross a process boundary as JSON, and because a snapshot
    whose header travels IN BAND is self-describing: `distinct_from_snapshot` can refuse a
    truncated or mistyped payload instead of reading whatever length it was handed.

    An invalid sketch snapshots as an EMPTY list, never as a header with no body: a
    zero-length payload is unambiguously not a sketch, where a header alone would round-trip
    into a plausible empty sketch and lose the refusal.

    @capability distinct_snapshot
    complexity: O(2^precision)
    counts: none
    @endcapability
    """
    var out = List[Int]()
    if _sketch_ok(sketch) != STM_OK:
        return out^
    out.append(DISTINCT_SNAPSHOT_MAGIC)
    out.append(sketch.precision)
    out.append(sketch.seed)
    out.append(sketch.n_ingested)
    for j in range(len(sketch.registers)):
        out.append(sketch.registers[j])
    return out^


fn distinct_from_snapshot(snapshot: List[Int]) -> DistinctSketch:
    """A sketch from a flat snapshot, or a refusal naming what was wrong with it.

    Every field is validated, because the caller of this function is a stored byte string
    and not a programmer. In particular each register must lie in `[0, 32 - precision]`, the
    range the frozen `hll_add` can produce: a register of 10^18 drives the frozen estimator
    to a division by zero and an infinite result, which the dispatch refuses, turning the
    whole response into a typed error; a NEGATIVE register drives it to 0.0, which is worse
    because it looks like an answer.

    @capability distinct_from_snapshot
    complexity: O(len(snapshot))
    counts: none
    @endcapability
    """
    if len(snapshot) < DISTINCT_HEADER:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    if snapshot[0] != DISTINCT_SNAPSHOT_MAGIC:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    var precision = snapshot[1]
    var seed = snapshot[2]
    var n_ingested = snapshot[3]
    var bad = _params_ok(precision, seed)
    if bad != STM_OK:
        return _invalid(bad)
    if n_ingested < 0 or not stm_items_ok(n_ingested):
        return _invalid(STM_ERR_ITEM_BUDGET)
    var m = 1 << precision
    if len(snapshot) != DISTINCT_HEADER + m:
        return _invalid(STM_ERR_SNAPSHOT_SHAPE)
    var ceiling = _max_register(precision)
    var regs = List[Int]()
    for j in range(m):
        var value = snapshot[DISTINCT_HEADER + j]
        if value < 0 or value > ceiling:
            return _invalid(STM_ERR_SNAPSHOT_SHAPE)
        regs.append(value)
    var out = DistinctSketch(regs^, precision, seed, n_ingested, STM_OK, True)
    # The per-register loop above checks each value INDEPENDENTLY, and independent legality is
    # not joint legality: every register 0 is legal and `n_ingested = 5` is legal, and together
    # they describe a stream of five items with zero distinct items. `_sketch_ok` carries the
    # cross-field relation, so it is the last word here rather than a second opinion -- one
    # predicate, reached by both the snapshot path and the struct path, so the two cannot drift.
    var shape = _sketch_ok(out)
    if shape != STM_OK:
        return _invalid(shape)
    return out^


fn distinct_merge_snapshots(a: List[Int], b: List[Int]) -> DistinctSketch:
    """Merge two flat snapshots directly, for combining partials from two processes.

    Exactly `distinct_merge(distinct_from_snapshot(a), distinct_from_snapshot(b))`, spelled
    as one call because that is the shape of the actual job: two workers each shipped a
    snapshot and neither of them is here any more.

    @capability distinct_merge_snapshots
    complexity: O(len(a) + len(b))
    counts: none
    @endcapability
    """
    return distinct_merge(distinct_from_snapshot(a), distinct_from_snapshot(b))


fn distinct_register_count(sketch: DistinctSketch) -> Int:
    """Register count, or 0 for an unusable sketch. 0 is not a register count.

    Reports `len(registers)` and never `1 << precision`, so a caller who compares the two sees
    the disagreement this function would otherwise paper over. It is the one function here that
    stays O(1): it reads no register, so no shape check is needed to make it safe.

    @capability distinct_register_count
    complexity: O(1)
    counts: none
    @endcapability
    """
    if not sketch.valid:
        return 0
    return len(sketch.registers)


fn distinct_nonzero_registers(sketch: DistinctSketch) -> Int:
    """How many registers have ever been touched, or -1 for an unusable sketch.

    Useful as a saturation signal: when this approaches the register count the estimator has
    left its small-range correction and the claimed relative error is the one that applies.

    -1 and not 0 for an unusable sketch, because 0 IS an answer here: a fresh
    `distinct_empty(12, 7)` has zero touched registers and that is a fact about it. Returning 0
    for "there was no sketch to look at" would be the absence-reported-as-zero this package
    exists to avoid.

    @capability distinct_nonzero_registers
    complexity: O(2^precision)
    counts: none
    @endcapability
    """
    if _sketch_ok(sketch) != STM_OK:
        return -1
    var seen = 0
    for j in range(len(sketch.registers)):
        if sketch.registers[j] != 0:
            seen += 1
    return seen
