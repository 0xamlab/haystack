"""
query.join — hash and merge joins over RecordBatches. Zero Python.

A join is expressed as two aligned index lists — `left_rows` and `right_rows` — and
only then materialized through `columnar.batch.take_column`. Keeping the row pairing
separate from the gather means an outer join's unmatched side is just `NO_ROW` in the
index list, and `take_column` already turns an out-of-range index into a null. There is
no second code path for "the row that isn't there".

A null key matches nothing. This is the opposite of DISTINCT
-----------------------------------------------------------
`null = null` is unknown, and a join is a sequence of equality tests, so a row whose
key is missing joins to nothing:

  * INNER — the row disappears.
  * LEFT  — the row survives once, with nulls across every right column.

`query.executor.distinct_indices` deliberately does the opposite: there, two rows
missing the same field ARE the same row. Both rules are right for their operation and
using either one for the other is a silent wrong answer — an inner join that matched
nulls would fabricate pairings between unrelated rows that happen to both be
incomplete. Both are tested against each other.

A NaN key is a MISSING key, on every path
-----------------------------------------
IEEE-754 says NaN is not equal to anything, including itself, so a NaN key cannot
satisfy the equality test a join is built out of. It is therefore routed through the
null path above — counted in `null_key_rows`, dropped by INNER, emitted once with
`NO_ROW` by LEFT, in neither half of semi/anti — and `is_matchable_key` is the single
predicate that decides it for keys on both sides of both algorithms.

Two things forced that to be explicit rather than incidental:

  * `columnar.hash_index.normalize_bits` collapses every NaN to ONE canonical NaN so a
    group-by cannot invent a group per NaN row. Correct there, wrong here: probing that
    table with a NaN would pair a NaN left key with a NaN right key and report a match
    that IEEE-754 says does not exist. So NaN keys never enter the table and never probe
    it.
  * a NaN reaching the merge join's `< > ==` cursor ladder answered False to all three
    comparisons, advanced NEITHER cursor, and span forever — a hung worker, which takes
    every resident dataset with it. See `merge_join_indices`.

NaN arrives from ordinary finite input (`inf - inf`, `0/0`, a projected expression), so
this cannot be pushed out to ingest-time validation of literals.

Duplicate keys multiply, they do not collapse
--------------------------------------------
Three left rows and two right rows sharing a key produce six output rows. That is what
a join means and it is the usual source of a surprise row count, so `JoinResult`
carries `left_unmatched` and the output length rather than making a caller infer them.
`left_unmatched` is counted for an INNER join too, where those rows are *dropped*: a
join silently losing rows is the single thing a caller most needs counted, and a count
that only exists under LEFT is a count that is absent exactly where it matters.

Hash join vs merge join
-----------------------
`hash_join` builds a table on the right and probes with the left: O(n+m), no ordering
requirement. `merge_join` walks two already-sorted inputs: O(n+m) with no table at all,
which is what makes it the right choice when a previous operator already sorted — the
plan should not pay twice. `merge_join` verifies its inputs are sorted rather than
trusting the claim, because an unsorted input silently produces a partial join, and a
join that quietly drops matches is worse than one that refuses.

Parallel probe and gather (2026-08)
------------------------------------
The H2O join-track baseline (`benchmarks/h2o_join/RESULTS.md`) found
`hash_join_indices`'s probe loop and `materialize`'s per-column gather entirely
single-threaded, the root cause of a flat multi-x loss to Polars and a DuckDB-specific
loss on a 1e7-row near-1:1 build side. Both loops get a row-banded parallel path above
their own measured threshold; below it, or on any doubt, the ORIGINAL single-thread
walk runs unchanged, and both paths are proven bit-identical (not just row-count
identical) by the suite.

Same blueprint as `query.aggregate.group_by_many_radix`'s round-3 "counted scatter",
because a probe's output size is per-row VARIABLE (0, 1 or a whole duplicate-key
chain) the way a fixed-slot merge (`query.composed`'s `group_by_composed_dense_parallel`)
is not: pass A counts survivors per worker with the identical per-row branch the serial
walk takes, a serial prefix sum over `workers` (not rows — cheap) turns those counts
into disjoint write offsets, and pass B re-walks the same bands and writes at its own
cursor with raw indexed stores instead of `.append()`. The final cursors are CHECKED
against the counts after pass B; a mismatch abandons the scatter and falls back to the
plain serial walk rather than trust a mis-sized result — the same discipline
`group_by_many_radix` uses for the same reason.

Order, exactly: worker 0 owns the lowest left-row band and the lowest write-offset
range, worker 1 the next, and so on — band order IS offset order IS output order, so
the design changes who does the arithmetic and not the association: output is
bit-for-bit identical to the serial walk, row for row, at every worker count.

Safety of the concurrent reads: `slot_of`/`first_row`/`next_row` (the right-side table)
are fully built, and never written again, before either pass starts —
`HashIndex.find` takes `self`, not `mut self` — so every worker's read of them is a
read of already-immutable state, the same argument `query.composed`'s
`compose_exact_domain` makes for reading a key column from every worker.

`_build_right_index` itself and `merge_join_indices` are UNCHANGED by this pass — the
build mutates one shared table per right row rather than touching independent rows,
which is a different hazard than a probe's read-only concurrent lookups, and no H2O
join-track question exercises `merge_join`. The build's own follow-on is the next
section.

Parallel build (2026-08, follow-on)
------------------------------------
Per-phase telemetry on the parallel probe/gather above found `_build_right_index`
responsible for most of what was left of the DuckDB and Polars gaps on q5 specifically
(the one near-1:1, 10,000,000-row build side in the H2O join-track) while being noise
on every other question — see `_build_right_index_parallel`'s own section docstring
below for the full numbers and the radix-partitioned design that fixes it without ever
mutating one `HashIndex` from two threads. `_build_right_index` itself stays exactly
as it was above; `hash_join_indices` now has a second, additive way to reach the table
its probe needs, gated by `JOIN_BUILD_PARALLEL_MIN_ROWS`.

Per-row constant factor: one validity check instead of two, one hash instead of two
(2026-08, second follow-on)
------------------------------------------------------------------------------------
With build and probe both parallelized, `benchmarks/h2o_join/RESULTS.md`'s per-phase
telemetry found the REMAINING Polars gap on q1-q4 flat across worker counts — the
signature of a per-row constant-factor cost, not a parallelism gap — and attributed
70-90% of it to `materialize`'s gather. The cause: every present cell in a gather (i.e.
almost the whole output) called `Float64Array.get`, which itself calls `is_valid_at` —
so a caller like `_take_column_join`, which had ALREADY called `is_valid_at` to decide
which branch to take, paid for the exact same bounds-check-plus-bitmap-test twice per
cell. `is_matchable_key` — probed on every row of both build and probe, on both
sides — had the identical shape: `is_valid_at` then `get`, which re-ran it.

The fix is `columnar.array.Float64Array.get_unchecked`: `get`'s read with no check of
its own, for a caller that has ALREADY confirmed `is_valid_at` — exactly the shape
every one of these call sites already has. This is a pure internal-mechanics change:
every call site that adopts it was already inside a branch that had just proven the
index valid, so the value read is identical, the row is identical, and nothing about
NaN, null, or duplicate-key handling moves — only the redundant second check is gone.

The partitioned probe (`_hash_join_probe_serial_partitioned` and
`_hash_join_probe_parallel_partitioned`, from the parallel build above) had a second,
narrower version of the same shape: both already compute `h = hash_bits(normalize_
bits(key))` once to route a left row to its partition, then called `tables[p].find
(key)` — which recomputes `normalize_bits` and `hash_bits` a SECOND time internally,
because `HashIndex.find` had no hashed-entry overload to hand the already-computed
pair to. `HashIndex.find_bits(bits, h)` is that overload — `get_or_assign_bits`'s exact
read-side mirror, same contract (`bits` MUST be `normalize_bits(key)`, `h` MUST be
`hash_bits(bits)`), same "the suite pins it slot-for-slot against `find`" discipline.

None of this touches `hash_join_indices`'s signature, its build/probe dispatch
thresholds, or any NaN/null/duplicate-key rule above — it is strictly cheaper per row
on paths that already existed, additive in the same sense `get_or_assign_bits` was:
a new way to reach an unchanged answer, never a new answer.
"""
from std.algorithm.functional import parallelize
from std.memory import alloc
from std.sys import info

from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, Schema, take_column
from columnar.hash_index import HashIndex, hash_bits, normalize_bits

# Matches `query.executor.NO_ROW`. An index of -1 is what `take_column` turns into a
# null, so an unmatched outer row needs no special case anywhere downstream.
comptime NO_ROW: Int = -1

comptime JOIN_INNER: Int = 0
comptime JOIN_LEFT: Int = 1

comptime JOIN_PROBE_PARALLEL_MIN_ROWS: Int = 1 << 19
"""Left rows at or above which `hash_join_indices`'s probe fans out over row bands.

Measured on this host (16 physical cores), not copied from `query.aggregate`'s
`PARALLEL_MIN_ROWS` (a different loop shape — hash + accumulate, not hash + chain-walk)
or `query.composed`'s `COMPOSE_PARALLEL_MERGE_MIN_FOLDS` (a different currency — folds,
not rows): a 10-row-build-side probe over an all-present key runs ~7.7-7.9 ns/row
single-threaded, and an empty `parallelize` call on this host costs 45-125 us quiet,
0.44-0.53 ms under load (the figure `query.aggregate`'s and `query.composed`'s own
docstrings measured for THIS host, not re-derived here). This path pays for two such
calls (count then scatter), so break-even against 16-way parallelism lands
between ~12k rows (quiet) and ~137k rows (under load) — `overhead / (per_row_cost *
(1 - 1/workers))`. 1<<19 = 524,288 sits 4-40x above that range, which is the property
a threshold should have per `query.composed`'s own reasoning: comfortably clear of
the noise in the estimate, and three-plus orders of magnitude below the H2O
join-track's 10,000,000-row left side, which is what actually needs this."""

comptime JOIN_GATHER_PARALLEL_MIN_ROWS: Int = 1 << 18
"""Output rows at or above which `materialize`'s per-column gather fans out.

Its own measurement, not `hash_join_indices`'s probe threshold reused: a gather is one
bounds check plus a copy, cheaper per row (~4.5-9.6 ns/row measured here) than a
probe's hash-and-chain-walk, and it pays for only ONE `parallelize` call (no counting
pass — `materialize` already knows `result.n_rows()` exactly, so the output can be
pre-sized directly). Break-even against 16-way parallelism is ~27k-107k rows over the
same quiet/under-load overhead range as above; 1<<18 = 262,144 sits comfortably past
it with margin, and — again — three-plus orders of magnitude below the 9-10M row
outputs the H2O join-track actually produces."""

comptime JOIN_BUILD_RADIX_BITS: Int = 4
comptime JOIN_BUILD_RADIX_PARTITIONS: Int = 1 << JOIN_BUILD_RADIX_BITS
"""Partition fan-out for the parallel build (`_build_right_index_parallel`) below.

Copied from `query.aggregate`'s own `RADIX_BITS` (4, so 16 partitions) rather than
re-derived: same reasoning applies verbatim — 16 partitions gives every one of this
host's 16 physical cores a task in the build's own pass 2 (one partition per task, see
`_build_right_index_parallel`'s docstring), and the split is on the TOP bits of the same
FNV-1a hash `HashIndex` already probes with on its LOW bits (`hash_bits(bits) & mask`),
so partition routing and in-partition table position are independent signals from one
hash rather than two, exactly `group_by_many_radix`'s own argument for the same split."""

comptime JOIN_BUILD_PARALLEL_MIN_ROWS: Int = 1 << 19
"""Right rows at or above which `hash_join_indices` builds the table with the
radix-partitioned parallel build (`_build_right_index_parallel`) instead of the plain
serial `_build_right_index`.

Same order of magnitude as `JOIN_PROBE_PARALLEL_MIN_ROWS` and for the same reason: the
parallel build pays for two `parallelize` calls over row bands (count, scatter) plus one
more over the 16 partitions, so a small right side must not pay that fan-out for
nothing. Measured on the H2O join-track's own shapes (see
`benchmarks/h2o_join/RESULTS.md`'s 2026-08 build-phase update): q1-q4's build sides
(10-10,000 rows) are nowhere near this threshold and always take the serial path
unchanged; q5's 10,000,000-row near-1:1 build side is more than an order of magnitude
past it, which is what this threshold exists for."""


struct JoinResult(Copyable, Movable):
    """Aligned row indices for the two sides, plus what did not match.

    `right_rows[i] == NO_ROW` marks a left row that found no partner. Counting them
    separately as `left_unmatched` means a caller can report "40 of 500 orders had no
    customer" without rescanning the result.

    Counter semantics, because these two overlap and the overlap used to be invisible:

      * `left_unmatched` — EVERY left row that found no partner, whatever the join type.
        Under LEFT those rows are in the output carrying `NO_ROW`; under INNER they are
        not in the output at all. So `n_rows() + left_unmatched == left.n_rows` holds
        for an INNER join with unique keys, and `n_rows()` already includes them under
        LEFT.
      * `null_key_rows` — the SUBSET of `left_unmatched` whose key was unusable (absent,
        or NaN). It is a subset, never an addend: a row with no key cannot match, so it
        is unmatched by construction. `describe()` says so, because reporting the two as
        if they were disjoint makes the numbers fail to add up to `n_rows` and invites a
        caller to double-count the same row.

    `join_type` is carried so `describe()` can state what happened to the unmatched rows
    rather than leaving a lineage line that reads the same whether the rows were kept
    with nulls or dropped.
    """

    var left_rows: List[Int]
    var right_rows: List[Int]
    var left_unmatched: Int
    var null_key_rows: Int
    var join_type: Int

    fn __init__(
        out self,
        var left_rows: List[Int],
        var right_rows: List[Int],
        left_unmatched: Int,
        null_key_rows: Int,
        join_type: Int,
    ):
        self.left_rows = left_rows^
        self.right_rows = right_rows^
        self.left_unmatched = left_unmatched
        self.null_key_rows = null_key_rows
        self.join_type = join_type

    fn n_rows(self) -> Int:
        return len(self.left_rows)

    fn describe(self) -> String:
        """Lineage text. States the overlap between the two counters explicitly.

        The alternative — presenting `left_unmatched` and `null_key_rows` side by side —
        reads as two disjoint groups, so a reader adding them to `n_rows` gets a number
        larger than the left input. The row with no key is in both.
        """
        var out = String(len(self.left_rows)) + " joined rows"
        if self.left_unmatched > 0:
            out += ", " + String(self.left_unmatched) + " left rows unmatched"
            if self.join_type == JOIN_LEFT:
                out += " (kept with nulls)"
            else:
                out += " (dropped)"
        if self.null_key_rows > 0:
            out += (
                ", "
                + String(self.null_key_rows)
                + " left rows had a null key (null or NaN; already inside the unmatched"
                " count, not additional to it)"
            )
        return out


fn is_matchable_key(column: Float64Array, row: Int) -> Bool:
    """True when the cell at `row` can take part in an equality test at all.

    THE single definition of "usable join key" for both algorithms and both sides. Two
    cells fail it:

      * an absent cell — `null = null` is unknown, per the module docstring.
      * a NaN — `NaN = NaN` is FALSE, so it matches nothing, not even the identical bit
        pattern in the other input. This is not a policy choice; treating it as a
        matchable key would have to invent an equality IEEE-754 does not define.

    Both fail for the same reason at the call sites: the key is not something an equality
    test can answer about, so the row's partner set is empty rather than unknown-sized.

    Out of range is not matchable either. `is_valid_at` bounds-checks and `get` returns
    0.0 for anything it rejects, so this never reads past the column — reading past the
    end of a List is an uncatchable process abort, not an exception (rule 1).
    """
    if not column.is_valid_at(row):
        return False
    var value = column.get_unchecked(row)
    # NaN is the ONLY Float64 that is not equal to itself. No `isnan` import needed and
    # no dependence on a sign bit or a payload, so a signalling NaN is caught too.
    return value == value


fn _build_right_index(
    right_key: Float64Array,
    n_rows: Int,
    mut slot_of: HashIndex,
    mut first_row: List[Int],
    mut next_row: List[Int],
) -> Int:
    """A key -> chain-of-rows table over the right side. Returns the unusable-key count.

    One slot per distinct key holding the head of a linked list through `next_row`,
    which is how duplicate right keys are represented without a list-of-lists: row
    chaining costs one Int per row and no allocation per key.

    Rows are chained in ASCENDING order (the list is appended to at the tail) so a
    probe emits partners in right-row order, which makes the join output deterministic
    rather than reverse-of-insertion.

    A right row whose key is not matchable — null OR NaN — is never inserted, so it can
    never be probed into. NaN matters specifically here: `HashIndex` normalizes every NaN
    to one canonical bit pattern (right, for group-by), so inserting a NaN key would let
    a NaN left key find it and report a pairing that `NaN == NaN` denies.
    """
    var null_keys = 0
    var last_row = List[Int]()
    for r in range(n_rows):
        next_row.append(NO_ROW)
    for r in range(n_rows):
        if not is_matchable_key(right_key, r):
            null_keys += 1
            continue
        var next_slot = len(first_row)
        var slot = slot_of.get_or_assign(right_key.get_unchecked(r), next_slot)
        if slot == next_slot:
            first_row.append(r)
            last_row.append(r)
        else:
            next_row[last_row[slot]] = r
            last_row[slot] = r
    return null_keys


# ─── Parallel radix-partitioned build (2026-08, build-phase parallelization) ──────
#
# `benchmarks/h2o_join/RESULTS.md`'s per-phase telemetry found `_build_right_index`
# above -- the one phase the original "Parallel probe and gather" pass explicitly left
# serial -- responsible for 87% of the remaining DuckDB-relative gap and 65% of the
# Polars-relative gap on q5 (the H2O join-track's near-1:1, 10,000,000-row build side),
# while being noise (<0.3% of runtime) on every other question. What follows is
# additive: `hash_join_indices`'s own signature and every observable behaviour are
# unchanged (see its own docstring); only its INTERNAL dispatch gains a second, faster
# way to reach the same `JoinResult`, exactly the way `JOIN_PROBE_PARALLEL_MIN_ROWS`
# and `JOIN_GATHER_PARALLEL_MIN_ROWS` already gate a second way to run the probe and
# the gather without touching either's public contract.
#
# Why a single shared `HashIndex` cannot simply be filled by N workers each handed a
# row band (the naive analog of the probe's own parallelization): `HashIndex.get_or_
# assign` MUTATES shared state -- the open-addressed `slots`/`slot_keys` arrays, plus a
# `_grow()` that reallocates them -- so two workers racing to insert two DIFFERENT keys
# that happen to probe the same or adjacent table positions is a real data race, not a
# theoretical one; and `_grow()` firing mid-insert from two threads at once would
# corrupt the table for every key, not just the colliding two. There is no way to make
# `get_or_assign` itself thread-safe without a lock on the hot path this measurement
# just proved is 60%+ of build time on the tier that matters.
#
# The fix, adapted from `query.aggregate.group_by_many_radix`'s own solved version of
# the identical problem (a group-by's accumulator table has the exact same shared-
# mutable-state hazard): radix-partition the right side by the TOP bits of the same
# FNV-1a hash `HashIndex` already probes with on its LOW bits, so two rows can share a
# partition only if a real hash collision put them there -- which the equality check
# inside that partition's own table still resolves correctly, exactly as it always has.
# Partitioning on a DIFFERENT bit range of the SAME hash (not two different hashes)
# means a key's partition and its in-partition table position are independent signals,
# not two chances to disagree about identity.
#
#   pass A (parallel over `workers` contiguous row bands): hash each matchable right
#     row ONCE (`hash_bits(normalize_bits(key))`), keep the hash in a row-indexed
#     buffer, and COUNT the row into (worker, partition) -- no table touched yet, so
#     nothing to race on.
#
#   prefix sum (serial, `workers x JOIN_BUILD_RADIX_PARTITIONS` entries -- cheap):
#     counts become segment offsets, PARTITION-major with band order inside a
#     partition, so partition p's whole region ends up in ascending global row order --
#     the same layout `group_by_many_radix` uses and for the same reason: a later pass
#     that just walks a partition's segment in order reproduces the serial algorithm's
#     row order for free, no sort needed.
#
#   pass B (parallel, same bands): re-walk each band with the IDENTICAL matchable-key
#     test pass A ran (deterministic, so the same rows survive), and write each
#     survivor's (row index, hash) at its own (worker, partition) cursor with raw
#     indexed stores -- disjoint by construction, the same cursor-bounds argument
#     `_hash_join_probe_parallel` already makes for its own scatter. Checked afterward,
#     not trusted; a mismatch abandons the whole parallel build for the serial one.
#
#   pass 2 (parallel, ONE task per partition -- `JOIN_BUILD_RADIX_PARTITIONS` of them,
#     independent of `workers`, mirroring `group_by_many_radix`'s own pass 2): each
#     partition builds its OWN PRIVATE `HashIndex` and its OWN slot-indexed `first_row`
#     list, walking its segment in the ascending row order the prefix sum already
#     established, using `get_or_assign_bits` to probe with the hash pass A already
#     computed rather than re-deriving it. `next_row` (row-indexed, one shared list
#     across every partition) is written directly by whichever partition's segment the
#     row landed in -- safe because a right row belongs to EXACTLY ONE partition, so no
#     two partitions ever write the same `next_row[r]`.
#
# Duplicate keys across a "band" boundary (pass A/B's worker split) chain together
# correctly because band membership only decides WHEN a row is counted/hashed, never
# which partition or table it lands in -- that is decided solely by the row's own key
# hash, identically in pass A and pass B. Two rows with the same key are GUARANTEED the
# same partition (same hash, same top bits) however far apart their row indices or
# whichever worker's band each falls in, so they always chain together in the one
# partition table that owns that key -- never silently split across two tables the way
# a naive "one partition per worker, keyed by row range" scheme would.
#
# What this does NOT change: `_build_right_index` above (the plain serial build) is
# byte-for-byte untouched and is exactly what a right side below
# `JOIN_BUILD_PARALLEL_MIN_ROWS` still runs, and exactly what the parallel build itself
# falls back to, whole, if its own scatter invariant ever fails its check.
# `join_output_rows` and `semi_join_indices` also keep calling the plain serial build
# unchanged -- neither is on the H2O join-track's measured path, and the size-estimation
# and semi-join operators they serve are a separate, smaller-scoped follow-on, not
# attempted here.


fn _build_right_index_parallel(
    right_key: Float64Array,
    n_rows: Int,
    workers: Int,
    mut tables: List[HashIndex],
    mut first_row: List[List[Int]],
    mut next_row: List[Int],
    mut ok: Bool,
) -> Int:
    """Radix-partitioned parallel build. Returns the unusable-key count, same as
    `_build_right_index`. Fills `tables`/`first_row` with exactly
    `JOIN_BUILD_RADIX_PARTITIONS` entries (partition `p`'s slot-indexed first-row list
    is `first_row[p]`, its table is `tables[p]`) and `next_row` with one entry per right
    row, matching `_build_right_index`'s own row-indexed layout exactly -- a caller
    probing partition `p`'s slot with `next_row` needs no partition-aware indexing for
    that array, only for `tables`/`first_row`.

    Sets `ok = False` and leaves `tables`/`first_row`/`next_row` in an unspecified,
    UNUSABLE state if the pass-B scatter's own write-cursor invariant fails -- the
    caller MUST check `ok` and re-run the whole build serially via `_build_right_index`
    rather than trust anything here, the same discipline
    `_hash_join_probe_parallel` already applies to its own scatter, just surfaced
    outward instead of handled internally, because unlike that function this one cannot
    fall back to a same-shape alternative on its own: its OUTPUT shape (partitioned)
    differs from `_build_right_index`'s (one flat table), so only the caller — which
    also owns dispatching the matching probe shape — can pick the right whole
    alternative.

    `workers` MUST be >= 1; callers gate this behind `JOIN_BUILD_PARALLEL_MIN_ROWS` and
    a computed worker count, exactly as `_hash_join_probe`'s own dispatch does for the
    probe.
    """
    ok = True
    next_row = List[Int](length=n_rows, fill=NO_ROW)
    if n_rows <= 0:
        tables = List[HashIndex]()
        first_row = List[List[Int]]()
        for _ in range(JOIN_BUILD_RADIX_PARTITIONS):
            tables.append(HashIndex(64))
            first_row.append(List[Int]())
        return 0

    var band = (n_rows + workers - 1) // workers

    # ── pass A: hash every matchable row once, count into (worker, partition) ───────
    var hrow = alloc[UInt64](n_rows)
    var counts = List[Int](length=workers * JOIN_BUILD_RADIX_PARTITIONS, fill=0)
    var w_nulls = List[Int](length=workers, fill=0)
    var cp = counts.unsafe_ptr()
    var np = w_nulls.unsafe_ptr()

    @parameter
    fn count_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var local = List[Int](length=JOIN_BUILD_RADIX_PARTITIONS, fill=0)
        var lp = local.unsafe_ptr()
        var nulls = 0
        for r in range(lo, hi):
            if not is_matchable_key(right_key, r):
                nulls += 1
                continue
            var h = hash_bits(normalize_bits(right_key.get_unchecked(r)))
            hrow[r] = h
            lp[Int(h >> (64 - JOIN_BUILD_RADIX_BITS))] += 1
        for p in range(JOIN_BUILD_RADIX_PARTITIONS):
            cp[w * JOIN_BUILD_RADIX_PARTITIONS + p] = lp[p]
        np[w] = nulls

    parallelize[count_worker](workers)

    # ── prefix sum: counts to segment offsets, partition-major with band order
    #    inside a partition (see the section docstring above) ───────────────────────
    var offsets = List[Int](length=workers * JOIN_BUILD_RADIX_PARTITIONS, fill=0)
    var part_start = List[Int](length=JOIN_BUILD_RADIX_PARTITIONS + 1, fill=0)
    var running = 0
    for p in range(JOIN_BUILD_RADIX_PARTITIONS):
        part_start[p] = running
        for w in range(workers):
            offsets[w * JOIN_BUILD_RADIX_PARTITIONS + p] = running
            running += counts[w * JOIN_BUILD_RADIX_PARTITIONS + p]
    part_start[JOIN_BUILD_RADIX_PARTITIONS] = running
    var survivors = running

    # ── pass B: write (row, hash) at each row's (worker, partition) cursor ──────────
    var prow = alloc[Int](survivors if survivors > 0 else 1)
    var phash = alloc[UInt64](survivors if survivors > 0 else 1)
    var cursors = List[Int](length=workers * JOIN_BUILD_RADIX_PARTITIONS, fill=0)
    for i in range(workers * JOIN_BUILD_RADIX_PARTITIONS):
        cursors[i] = offsets[i]
    var up = cursors.unsafe_ptr()

    @parameter
    fn scatter_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var local = List[Int](length=JOIN_BUILD_RADIX_PARTITIONS, fill=0)
        var lp = local.unsafe_ptr()
        for p in range(JOIN_BUILD_RADIX_PARTITIONS):
            lp[p] = up[w * JOIN_BUILD_RADIX_PARTITIONS + p]
        for r in range(lo, hi):
            if not is_matchable_key(right_key, r):
                continue
            var h = hrow[r]
            var part = Int(h >> (64 - JOIN_BUILD_RADIX_BITS))
            var s = lp[part]
            lp[part] = s + 1
            prow[s] = r
            phash[s] = h
        for p in range(JOIN_BUILD_RADIX_PARTITIONS):
            up[w * JOIN_BUILD_RADIX_PARTITIONS + p] = lp[p]

    parallelize[scatter_worker](workers)
    hrow.free()

    var scatter_ok = True
    for i in range(workers * JOIN_BUILD_RADIX_PARTITIONS):
        if cursors[i] != offsets[i] + counts[i]:
            scatter_ok = False

    if not scatter_ok:
        prow.free()
        phash.free()
        print(
            "query.join: build scatter write-cursor invariant violated;"
            " falling back to the serial build"
        )
        ok = False
        return 0

    # ── pass 2: one task per partition, over its own contiguous, ascending-row-
    #    order segment. Builds that partition's PRIVATE table and first_row list,
    #    and writes `next_row` for its own rows only (disjoint across partitions by
    #    construction -- see the section docstring above). ──────────────────────────
    tables = List[HashIndex]()
    first_row = List[List[Int]]()
    for _ in range(JOIN_BUILD_RADIX_PARTITIONS):
        tables.append(HashIndex(64))
        first_row.append(List[Int]())
    var tp = tables.unsafe_ptr()
    var fp = first_row.unsafe_ptr()
    var nrp = next_row.unsafe_ptr()

    @parameter
    fn partition_worker(p: Int):
        var s0 = part_start[p]
        var s1 = part_start[p + 1]
        var last_row = List[Int]()
        var group_count = 0
        for s in range(s0, s1):
            var r = prow[s]
            var h = phash[s]
            # `r` came from pass B's own scatter, which only ever wrote rows that
            # passed `is_matchable_key` — so `is_valid_at(r)` is already known True
            # here and `get_unchecked` skips re-deriving it.
            var bits = normalize_bits(right_key.get_unchecked(r))
            var slot = tp[p].get_or_assign_bits(bits, h, group_count)
            if slot == group_count:
                group_count += 1
                fp[p].append(r)
                last_row.append(r)
            else:
                nrp[last_row[slot]] = r
                last_row[slot] = r

    parallelize[partition_worker](JOIN_BUILD_RADIX_PARTITIONS)
    prow.free()
    phash.free()
    # Keep the containers whose raw pointers the closures captured alive past the
    # joins: Mojo destroys a value after its last USE and `unsafe_ptr()` is not one.
    _ = len(counts) + len(offsets) + len(cursors) + len(tables) + len(first_row)

    var null_keys = 0
    for w in range(workers):
        null_keys += w_nulls[w]
    return null_keys


fn _hash_join_probe_serial_partitioned(
    left_key: Float64Array,
    n_rows: Int,
    tables: List[HashIndex],
    first_row: List[List[Int]],
    next_row: List[Int],
    join_type: Int,
) -> JoinResult:
    """The serial probe walk over a PARTITIONED build (`_build_right_index_parallel`'s
    output): the plain-table `_hash_join_probe_serial` above, adapted to look up a
    left key's partition first (the same top-bits-of-hash split the build used) and
    then find within that partition's own table. Below `JOIN_PROBE_PARALLEL_MIN_ROWS`,
    or as the fallback target for `_hash_join_probe_parallel_partitioned`'s own
    write-cursor check, exactly mirroring `_hash_join_probe`'s existing dispatch shape.
    """
    var out_left = List[Int]()
    var out_right = List[Int]()
    var unmatched = 0
    var null_keys = 0

    for l in range(n_rows):
        if not is_matchable_key(left_key, l):
            null_keys += 1
            unmatched += 1
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
            continue

        var key = left_key.get_unchecked(l)
        var bits = normalize_bits(key)
        var h = hash_bits(bits)
        var p = Int(h >> (64 - JOIN_BUILD_RADIX_BITS))
        var slot = tables[p].find_bits(bits, h)
        if slot < 0:
            unmatched += 1
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
            continue

        var r = first_row[p][slot]
        while r != NO_ROW:
            out_left.append(l)
            out_right.append(r)
            r = next_row[r]

    return JoinResult(out_left^, out_right^, unmatched, null_keys, join_type)


fn _hash_join_probe_parallel_partitioned(
    left_key: Float64Array,
    n_rows: Int,
    tables: List[HashIndex],
    first_row: List[List[Int]],
    next_row: List[Int],
    join_type: Int,
    workers: Int,
) -> JoinResult:
    """`_hash_join_probe_parallel`'s exact two-pass counted-scatter blueprint, adapted
    to a PARTITIONED build the same way the serial version above is: every per-row
    lookup routes through the row's own partition first. Safety argument for the
    concurrent reads is unchanged from the plain version -- every `tables[p]`/
    `first_row[p]`/`next_row` entry is fully built and never written again before
    either pass here starts, and `HashIndex.find` takes `self`, not `mut self`.

    `chain_length` is a single flat buffer indexed by `slot_base[p] + slot` (partition
    `p`'s slots occupy a contiguous range starting at `slot_base[p]`, the same
    "segment per partition" layout the build's own pass 2 uses), computed once per
    partition -- independent work across partitions, so it runs in its own
    `parallelize` over the partitions rather than serially; this is a strict
    improvement on the plain version's serial precompute, not a behavior change, since
    chain length depends only on that partition's own `first_row`/`next_row`, never on
    another partition's.
    """
    var slot_base = List[Int](length=JOIN_BUILD_RADIX_PARTITIONS + 1, fill=0)
    var running_slots = 0
    for p in range(JOIN_BUILD_RADIX_PARTITIONS):
        slot_base[p] = running_slots
        running_slots += len(first_row[p])
    slot_base[JOIN_BUILD_RADIX_PARTITIONS] = running_slots
    var total_slots = running_slots
    var sbp = slot_base.unsafe_ptr()

    var chain_len = alloc[Int](total_slots if total_slots > 0 else 1)
    var fp = first_row.unsafe_ptr()

    @parameter
    fn chain_worker(p: Int):
        var base = sbp[p]
        for s in range(len(fp[p])):
            var r = fp[p][s]
            var length = 0
            while r != NO_ROW:
                length += 1
                r = next_row[r]
            chain_len[base + s] = length

    parallelize[chain_worker](JOIN_BUILD_RADIX_PARTITIONS)

    var band = (n_rows + workers - 1) // workers
    var emit_unmatched = join_type == JOIN_LEFT

    var counts = List[Int](length=workers, fill=0)
    var w_unmatched = List[Int](length=workers, fill=0)
    var w_null = List[Int](length=workers, fill=0)
    var cp = counts.unsafe_ptr()
    var ump = w_unmatched.unsafe_ptr()
    var nlp = w_null.unsafe_ptr()

    @parameter
    fn count_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var local_count = 0
        var local_unmatched = 0
        var local_null = 0
        for l in range(lo, hi):
            if not is_matchable_key(left_key, l):
                local_null += 1
                local_unmatched += 1
                if emit_unmatched:
                    local_count += 1
                continue
            var key = left_key.get_unchecked(l)
            var bits = normalize_bits(key)
            var h = hash_bits(bits)
            var p = Int(h >> (64 - JOIN_BUILD_RADIX_BITS))
            var slot = tables[p].find_bits(bits, h)
            if slot < 0:
                local_unmatched += 1
                if emit_unmatched:
                    local_count += 1
                continue
            local_count += chain_len[sbp[p] + slot]
        cp[w] = local_count
        ump[w] = local_unmatched
        nlp[w] = local_null

    parallelize[count_worker](workers)

    var offsets = List[Int](length=workers, fill=0)
    var ofp = offsets.unsafe_ptr()
    var running = 0
    for w in range(workers):
        ofp[w] = running
        running += cp[w]
    var total = running

    var out_left = List[Int](length=total, fill=0)
    var out_right = List[Int](length=total, fill=0)
    var olp = out_left.unsafe_ptr()
    var orp = out_right.unsafe_ptr()
    var cursors = List[Int](length=workers, fill=0)
    for w in range(workers):
        cursors[w] = ofp[w]
    var curp = cursors.unsafe_ptr()

    @parameter
    fn scatter_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var cur = curp[w]
        for l in range(lo, hi):
            if not is_matchable_key(left_key, l):
                if emit_unmatched:
                    olp[cur] = l
                    orp[cur] = NO_ROW
                    cur += 1
                continue
            var key = left_key.get_unchecked(l)
            var bits = normalize_bits(key)
            var h = hash_bits(bits)
            var p = Int(h >> (64 - JOIN_BUILD_RADIX_BITS))
            var slot = tables[p].find_bits(bits, h)
            if slot < 0:
                if emit_unmatched:
                    olp[cur] = l
                    orp[cur] = NO_ROW
                    cur += 1
                continue
            var r = first_row[p][slot]
            while r != NO_ROW:
                olp[cur] = l
                orp[cur] = r
                cur += 1
                r = next_row[r]
        curp[w] = cur

    parallelize[scatter_worker](workers)
    chain_len.free()
    _ = len(slot_base) + len(counts) + len(offsets)

    var ok = True
    for w in range(workers):
        if curp[w] != ofp[w] + cp[w]:
            ok = False

    if not ok:
        print(
            "query.join: partitioned probe scatter write-cursor invariant violated;"
            " falling back to the serial partitioned probe"
        )
        return _hash_join_probe_serial_partitioned(
            left_key, n_rows, tables, first_row, next_row, join_type
        )

    var unmatched = 0
    var null_keys = 0
    for w in range(workers):
        unmatched += ump[w]
        null_keys += nlp[w]

    return JoinResult(out_left^, out_right^, unmatched, null_keys, join_type)


fn _hash_join_probe_partitioned(
    left_key: Float64Array,
    n_rows: Int,
    tables: List[HashIndex],
    first_row: List[List[Int]],
    next_row: List[Int],
    join_type: Int,
) -> JoinResult:
    """Dispatch over a PARTITIONED build, mirroring `_hash_join_probe`'s own dispatch
    exactly: below `JOIN_PROBE_PARALLEL_MIN_ROWS` or a collapsed worker count, run the
    serial partitioned walk; above it, try the parallel scatter, which falls back to
    the serial walk itself on its own invariant failure.
    """
    if n_rows < JOIN_PROBE_PARALLEL_MIN_ROWS:
        return _hash_join_probe_serial_partitioned(
            left_key, n_rows, tables, first_row, next_row, join_type
        )

    var workers = info.num_physical_cores()
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows
    if workers <= 1:
        return _hash_join_probe_serial_partitioned(
            left_key, n_rows, tables, first_row, next_row, join_type
        )

    return _hash_join_probe_parallel_partitioned(
        left_key, n_rows, tables, first_row, next_row, join_type, workers
    )


fn _hash_join_probe_serial(
    left_key: Float64Array,
    n_rows: Int,
    slot_of: HashIndex,
    first_row: List[Int],
    next_row: List[Int],
    join_type: Int,
) -> JoinResult:
    """The ORIGINAL single-thread probe walk, unchanged, extracted so the parallel
    path below can share this exact contract instead of re-deriving it: same inputs,
    same `JoinResult`. This is what runs below `JOIN_PROBE_PARALLEL_MIN_ROWS`, and
    what the parallel path itself falls back to if its own write-cursor invariant
    ever fails its check — so this loop's behaviour IS the specification the
    parallel path is checked against, not merely a fast default.
    """
    var out_left = List[Int]()
    var out_right = List[Int]()
    var unmatched = 0
    var null_keys = 0

    for l in range(n_rows):
        if not is_matchable_key(left_key, l):
            # An unknown key equals nothing, not even another unknown; a NaN equals
            # nothing, not even itself. Same empty partner set, same branch.
            null_keys += 1
            unmatched += 1
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
            continue

        var slot = slot_of.find(left_key.get_unchecked(l))
        if slot < 0:
            unmatched += 1
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
            continue

        var r = first_row[slot]
        while r != NO_ROW:
            out_left.append(l)
            out_right.append(r)
            r = next_row[r]

    return JoinResult(out_left^, out_right^, unmatched, null_keys, join_type)


fn _hash_join_probe_parallel(
    left_key: Float64Array,
    n_rows: Int,
    slot_of: HashIndex,
    first_row: List[Int],
    next_row: List[Int],
    join_type: Int,
    workers: Int,
) -> JoinResult:
    """Two-pass counted scatter over left-row bands — the blueprint is
    `query.aggregate.group_by_many_radix`'s round-3 counted scatter (see that
    module's docstring, "Opcode-specialized updates, counted scatter, batched
    hashing"), adapted from folding accumulators to emitting index pairs.

    `chain_length[s]` — how many right rows share slot `s` — is computed ONCE,
    serially, up front: the same quantity `join_output_rows` computes, so pass A can
    COUNT a match's contribution without re-walking its `next_row` chain (that walk
    happens exactly once, in pass B, same as the serial loop).

    Pass A (parallel, read-only): each worker walks its own contiguous band with the
    IDENTICAL branch `_hash_join_probe_serial` takes — `is_matchable_key`, then
    `slot_of.find`, then `chain_length[slot]` (or 1 for an unmatched/null-key row
    under LEFT, 0 under INNER) — and accumulates only its own private `count`,
    `unmatched` and `null_keys`. Nothing is written to `slot_of`/`first_row`/
    `next_row` anywhere in this module after `_build_right_index` returns, and
    `HashIndex.find` takes `self` rather than `mut self`, so every worker's
    concurrent read of the fully-built right-side table is a read of unchanging
    state — the same argument `query.composed`'s `compose_exact_domain` makes for
    concurrent reads of a key column.

    A serial prefix sum (over `workers`, not rows — cheap) turns per-worker counts
    into disjoint write offsets, and the two pre-sized output lists are allocated
    once at the total.

    Pass B (parallel, writing): each worker re-walks the SAME band with the SAME
    branch, this time actually walking the matched chain, and writes each emitted
    pair at its own cursor — starting at its offset, bumped once per row — with raw
    indexed stores instead of `.append()`. Disjointness argument: worker `w`'s cursor
    starts at `offset[w] = sum(count[i] for i < w)` and bumps exactly `count[w]`
    times by construction (pass A and pass B run the identical per-row branch), so
    worker `w`'s writes land in `[offset[w], offset[w] + count[w])` and no two
    workers' ranges can overlap — no lock or atomic needed, matching the round-3
    scatter's own safety argument.

    The final cursors are CHECKED against `offset + count` after pass B. On any
    mismatch this discards the scatter and falls back to `_hash_join_probe_serial`
    itself (rather than reporting failure outward, which would force every caller of
    this private helper to duplicate the same fallback) — a total function, always a
    valid `JoinResult`, exactly like every other route-with-a-fallback in this
    codebase (`group_by_many_radix`'s own scatter does the same on the same class of
    failure).

    Order: worker 0 owns the lowest band and the lowest offset range, worker 1 the
    next, and so on — band order IS offset order IS output order, so this is
    bit-for-bit identical to the serial walk's output, row for row, not merely as a
    multiset. The suite pins this exactly, the same way `group_by_many_radix`'s own
    suite pins its scatter against its serial reference.
    """
    var chain_length = List[Int](length=len(first_row), fill=0)
    var clp = chain_length.unsafe_ptr()
    for s in range(len(first_row)):
        var r = first_row[s]
        var length = 0
        while r != NO_ROW:
            length += 1
            r = next_row[r]
        clp[s] = length

    var band = (n_rows + workers - 1) // workers
    var emit_unmatched = join_type == JOIN_LEFT

    var counts = List[Int](length=workers, fill=0)
    var w_unmatched = List[Int](length=workers, fill=0)
    var w_null = List[Int](length=workers, fill=0)
    var cp = counts.unsafe_ptr()
    var ump = w_unmatched.unsafe_ptr()
    var nlp = w_null.unsafe_ptr()

    @parameter
    fn count_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var local_count = 0
        var local_unmatched = 0
        var local_null = 0
        for l in range(lo, hi):
            if not is_matchable_key(left_key, l):
                local_null += 1
                local_unmatched += 1
                if emit_unmatched:
                    local_count += 1
                continue
            var slot = slot_of.find(left_key.get_unchecked(l))
            if slot < 0:
                local_unmatched += 1
                if emit_unmatched:
                    local_count += 1
                continue
            local_count += clp[slot]
        cp[w] = local_count
        ump[w] = local_unmatched
        nlp[w] = local_null

    parallelize[count_worker](workers)

    # ── prefix sum: per-worker counts to disjoint write offsets (workers, not
    #    rows — trivially cheap) ─────────────────────────────────────────────────
    var offsets = List[Int](length=workers, fill=0)
    var ofp = offsets.unsafe_ptr()
    var running = 0
    for w in range(workers):
        ofp[w] = running
        running += cp[w]
    var total = running

    var out_left = List[Int](length=total, fill=0)
    var out_right = List[Int](length=total, fill=0)
    var olp = out_left.unsafe_ptr()
    var orp = out_right.unsafe_ptr()
    var cursors = List[Int](length=workers, fill=0)
    for w in range(workers):
        cursors[w] = ofp[w]
    var curp = cursors.unsafe_ptr()

    @parameter
    fn scatter_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n_rows:
            hi = n_rows
        var cur = curp[w]
        for l in range(lo, hi):
            if not is_matchable_key(left_key, l):
                if emit_unmatched:
                    olp[cur] = l
                    orp[cur] = NO_ROW
                    cur += 1
                continue
            var slot = slot_of.find(left_key.get_unchecked(l))
            if slot < 0:
                if emit_unmatched:
                    olp[cur] = l
                    orp[cur] = NO_ROW
                    cur += 1
                continue
            var r = first_row[slot]
            while r != NO_ROW:
                olp[cur] = l
                orp[cur] = r
                cur += 1
                r = next_row[r]
        curp[w] = cur

    parallelize[scatter_worker](workers)
    # Keep the containers whose raw pointers the closures captured alive past the
    # joins: Mojo destroys a value after its last USE and `unsafe_ptr()` is not one.
    _ = len(chain_length) + len(counts) + len(offsets)

    var ok = True
    for w in range(workers):
        if curp[w] != ofp[w] + cp[w]:
            ok = False

    if not ok:
        print(
            "query.join: probe scatter write-cursor invariant violated;"
            " falling back to the serial probe"
        )
        return _hash_join_probe_serial(
            left_key, n_rows, slot_of, first_row, next_row, join_type
        )

    var unmatched = 0
    var null_keys = 0
    for w in range(workers):
        unmatched += ump[w]
        null_keys += nlp[w]

    return JoinResult(out_left^, out_right^, unmatched, null_keys, join_type)


fn _hash_join_probe(
    left_key: Float64Array,
    n_rows: Int,
    slot_of: HashIndex,
    first_row: List[Int],
    next_row: List[Int],
    join_type: Int,
) -> JoinResult:
    """Dispatch: below `JOIN_PROBE_PARALLEL_MIN_ROWS` rows, or when a computed
    worker count collapses to 1, run the plain serial walk — a small join must not
    pay a fan-out for nothing, and an empty `parallelize` on this host has a real,
    measured, non-zero cost (see `JOIN_PROBE_PARALLEL_MIN_ROWS`'s own docstring).
    Above it, try the parallel scatter and fall back to serial if its own invariant
    check fails.
    """
    if n_rows < JOIN_PROBE_PARALLEL_MIN_ROWS:
        return _hash_join_probe_serial(
            left_key, n_rows, slot_of, first_row, next_row, join_type
        )

    var workers = info.num_physical_cores()
    if workers < 1:
        workers = 1
    if workers > n_rows:
        workers = n_rows
    if workers <= 1:
        return _hash_join_probe_serial(
            left_key, n_rows, slot_of, first_row, next_row, join_type
        )

    # `_hash_join_probe_parallel` is itself total: it falls back to the serial walk
    # internally if its own write-cursor invariant fails, so there is nothing further
    # to check here.
    return _hash_join_probe_parallel(
        left_key, n_rows, slot_of, first_row, next_row, join_type, workers
    )


fn hash_join_indices(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
) -> JoinResult:
    """Pair left rows with right rows on equal keys. Build on the right, probe left.

    A left row whose key is not matchable — null or NaN — matches nothing: under INNER it
    vanishes, under LEFT it emits once with NO_ROW opposite it. Unmatchable right keys
    never enter the probe table and so never appear.

    `left_unmatched` counts every left row with no partner under BOTH join types. It used
    to be incremented only inside the `JOIN_LEFT` branch, which made it 0 for an inner
    join — so the one join that discards rows was the one that reported nothing about it,
    and `describe()` omitted the count entirely.

    The build itself fans out above `JOIN_BUILD_PARALLEL_MIN_ROWS` (radix-partitioned,
    see `_build_right_index_parallel`'s own section docstring), falling back to the
    plain serial `_build_right_index` below that threshold or on the parallel build's
    own invariant-check failure; the probe fans out over left-row bands above
    `JOIN_PROBE_PARALLEL_MIN_ROWS` either way — see the module docstring's "Parallel
    probe and gather" section and `_hash_join_probe`/`_hash_join_probe_partitioned`'s
    own dispatch. Either path returns the identical `JoinResult` a right side of that
    shape would always have produced; which path ran is an internal performance
    decision, never part of this function's contract.
    """
    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

    if right.n_rows >= JOIN_BUILD_PARALLEL_MIN_ROWS:
        var build_workers = info.num_physical_cores()
        if build_workers < 1:
            build_workers = 1
        if build_workers > right.n_rows:
            build_workers = right.n_rows
        if build_workers > 1:
            var tables = List[HashIndex]()
            var p_first_row = List[List[Int]]()
            var p_next_row = List[Int]()
            var build_ok = True
            _ = _build_right_index_parallel(
                right_key,
                right.n_rows,
                build_workers,
                tables,
                p_first_row,
                p_next_row,
                build_ok,
            )
            if build_ok:
                return _hash_join_probe_partitioned(
                    left_key, left.n_rows, tables, p_first_row, p_next_row, join_type
                )
            # else: the parallel build's own scatter invariant failed. Fall through
            # to the plain serial build+probe below rather than trust a partial
            # partitioned result — same discipline as every other fallback in this
            # module, just spanning both phases here since the two are paired.

    var slot_of = HashIndex(64)
    var first_row = List[Int]()
    var next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, first_row, next_row)

    return _hash_join_probe(
        left_key, left.n_rows, slot_of, first_row, next_row, join_type
    )


fn is_sorted_ascending(batch: RecordBatch, key_column: Int) -> Bool:
    """True when the key ascends, with every unusable key (null or NaN) at the end.

    Nulls at the end because that is `query.executor.sort_indices(..., nulls_last=True)`
    output, which is what a merge join is meant to consume. A null in the middle means
    the input was not produced by that sort and the merge would stop early.

    A NaN is held to the same position rule as a null, for the same reason and by the
    same predicate: it is not a usable key, so a merge cursor has to step over it, and a
    merge cursor can only step over unusable keys that are all together at the END. It
    also cannot be ORDERED into the middle in any meaningful sense — `NaN < x` and
    `x < NaN` are both False, so a NaN sitting between two values makes the run of
    comparisons non-transitive and this predicate's `value < previous` test would wave it
    through while the ordering it certifies does not exist. That is why the NaN check
    lives here and not only in the join loop.

    Note this is the SAME function `query.plan` calls before dispatching a merge join, so
    the two guards cannot drift apart in strength (rule 3).
    """
    var key = batch.column(key_column)
    var seen_unusable = False
    var previous: Float64 = 0.0
    var have_previous = False
    for r in range(batch.n_rows):
        if not is_matchable_key(key, r):
            seen_unusable = True
            continue
        if seen_unusable:
            return False
        var value = key.get_unchecked(r)
        if have_previous and value < previous:
            return False
        previous = value
        have_previous = True
    return True


fn merge_join_indices(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
) raises -> JoinResult:
    """Join two ascending-sorted inputs with no hash table.

    Raises if either side is not sorted. Checked rather than trusted: an unsorted input
    makes the merge terminate early and return a subset of the real matches, which
    looks like a correct join over less data — the failure mode that a "you must sort
    first" comment does not prevent.

    Equal-key runs on both sides produce their full cross product, walked in ascending
    row order on both sides so the output matches `hash_join_indices` exactly — including
    the treatment of a NaN key, which both algorithms handle as a missing key.

    TERMINATION. `l` advances by at least one row on every path through the loop body,
    and it is the loop variable. That is a structural property here, NOT a consequence of
    any comparison: the left run always starts at `l + 1`, and the "no partner" branch
    consumes the whole run it just measured. It has to be structural, because a three-way
    `< > ==` ladder is NOT exhaustive over Float64 — an unordered pair answers False to
    all three. The previous version derived both cursor updates from that ladder, so a
    single NaN key made it advance neither: `right < lv` False kept `r`, `right > lv`
    False skipped the unmatched branch, `right == lv` False gave an empty right run,
    `left == lv` False gave `left_run_end == l`, and the two assignments at the bottom
    restored both cursors unchanged — forever. A hung worker is the same class of outcome
    as an out-of-bounds read (rule 1): the client sees a timeout and every resident
    dataset in the process dies with it. Any future edit that makes an advance conditional
    on a float comparison reintroduces exactly that.
    """
    if not is_sorted_ascending(left, left_key_column):
        raise Error(
            "query.join: merge_join requires the left input sorted ascending on column "
            + String(left_key_column)
            + " with nulls last (a NaN key counts as null: NaN equals nothing, so it"
            " cannot be ordered or matched)"
        )
    if not is_sorted_ascending(right, right_key_column):
        raise Error(
            "query.join: merge_join requires the right input sorted ascending on column "
            + String(right_key_column)
            + " with nulls last (a NaN key counts as null: NaN equals nothing, so it"
            " cannot be ordered or matched)"
        )

    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

    var out_left = List[Int]()
    var out_right = List[Int]()
    var unmatched = 0
    var null_keys = 0

    var l = 0
    var r = 0
    while l < left.n_rows:
        if not is_matchable_key(left_key, l):
            # Unusable keys are last (is_sorted_ascending enforces it), so everything
            # from here on is a null or a NaN. Both match nothing.
            null_keys += 1
            unmatched += 1
            if join_type == JOIN_LEFT:
                out_left.append(l)
                out_right.append(NO_ROW)
            l += 1
            continue

        var lv = left_key.get_unchecked(l)

        # The left run FIRST, and starting at l + 1: row `l` belongs to its own run by
        # definition rather than by comparison, so `left_run_end > l` unconditionally and
        # every `l = left_run_end` below is real progress. Measuring the left run before
        # touching the right side is what decouples termination from the comparisons.
        #
        # Every `.get_unchecked` below sits after an `is_matchable_key` on the SAME row
        # in the SAME `and`/`or` chain, evaluated first — short-circuiting guarantees
        # `is_valid_at` already answered True before the unchecked read runs, the same
        # guarantee `is_matchable_key`'s own two-step check makes internally.
        var left_run_end = l + 1
        while (
            left_run_end < left.n_rows
            and is_matchable_key(left_key, left_run_end)
            and left_key.get_unchecked(left_run_end) == lv
        ):
            left_run_end += 1

        # Advance the right cursor to the first row that could match. An unusable right
        # key stops the scan outright rather than being skipped past: nulls and NaNs are
        # last, so one here means there is nothing matchable left. `lv` is a real number
        # by now, so this `<` is a genuine ordering test.
        while (
            r < right.n_rows
            and is_matchable_key(right_key, r)
            and right_key.get_unchecked(r) < lv
        ):
            r += 1

        # `== lv`, not `> lv`. After the scan above the right key is either equal to `lv`
        # or greater, so the two forms agree for ordered values — but only the equality
        # test stays correct if an unordered value ever reaches here, and this is the
        # branch whose being skipped dropped the row entirely. An unusable right key lands
        # here too, which is how a trailing NaN on the right becomes "no partner" instead
        # of a silently discarded left row.
        if (
            r >= right.n_rows
            or not is_matchable_key(right_key, r)
            or not (right_key.get_unchecked(r) == lv)
        ):
            for li in range(l, left_run_end):
                unmatched += 1
                if join_type == JOIN_LEFT:
                    out_left.append(li)
                    out_right.append(NO_ROW)
            l = left_run_end
            continue

        # A run of equal keys on the right; emit the cross product with the left run.
        var run_start = r
        var run_end = r
        while (
            run_end < right.n_rows
            and is_matchable_key(right_key, run_end)
            and right_key.get_unchecked(run_end) == lv
        ):
            run_end += 1

        for li in range(l, left_run_end):
            for ri in range(run_start, run_end):
                out_left.append(li)
                out_right.append(ri)

        l = left_run_end
        # The right cursor may advance past this run: the next left key is strictly
        # greater than `lv` (the left run ended, and the left side ascends), so no later
        # left row can match a row of this run.
        r = run_end

    return JoinResult(out_left^, out_right^, unmatched, null_keys, join_type)


fn _take_column_join(source: Float64Array, indices: List[Int]) -> Float64Array:
    """`take_column`'s answer, parallel over disjoint OUTPUT-row bands above
    `JOIN_GATHER_PARALLEL_MIN_ROWS`. Scoped to `materialize` rather than changing
    `take_column` itself, which `query.executor`'s filter and sort share and which
    this module has no reason to touch.

    Simpler than the probe: by the time this runs, `len(indices)` is already known
    exactly (`materialize` computed `result.n_rows()` before calling this), so there
    is no variable fan-out to COUNT first — every worker's output range is a fixed
    `[lo, hi)` slice of `indices`, known before either loop runs. Below the
    threshold, or once a computed worker count collapses to 1, this returns
    `take_column`'s own unmodified answer directly rather than duplicating its logic
    for nothing.

    Each worker reads `source` (unmutated for the whole call, so concurrent reads
    from every worker are safe — the same argument the probe's docstring makes for
    `slot_of`/`first_row`/`next_row`) and `indices` (also unmutated) over its own
    band, and writes `values[i]`/`mask[i]` for its own `i` range only: disjoint by
    construction, the same as `_hash_join_probe_parallel`'s write ranges, and here
    there is no counting pass to get wrong because the ranges are fixed slices of a
    known-length input rather than a variable-size scatter.

    The per-row test is copied character for character from `take_column` — same
    bounds check, same `is_valid_at`, same 0.0-and-False-when-absent — so a cell
    that would be null under the serial gather is null here too, at the same index,
    for the same reason. Splitting the loop into ranges changes nothing about which
    cells go null; it only changes which thread visits which index.
    """
    var n = len(indices)
    if n < JOIN_GATHER_PARALLEL_MIN_ROWS:
        return take_column(source, indices)

    var workers = info.num_physical_cores()
    if workers < 1:
        workers = 1
    if workers > n:
        workers = n
    if workers <= 1:
        return take_column(source, indices)

    var values = List[Float64](length=n, fill=0.0)
    var mask = List[Bool](length=n, fill=False)
    var vp = values.unsafe_ptr()
    var mp = mask.unsafe_ptr()
    var ip = indices.unsafe_ptr()
    var band = (n + workers - 1) // workers

    @parameter
    fn gather_worker(w: Int):
        var lo = w * band
        var hi = lo + band
        if hi > n:
            hi = n
        for i in range(lo, hi):
            var index = ip[i]
            if index < 0 or index >= source.length or not source.is_valid_at(index):
                vp[i] = 0.0
                mp[i] = False
            else:
                # `is_valid_at(index)` already answered True on this branch (the `or`
                # chain's short-circuit means it is the reason we are here at all), so
                # `get_unchecked` skips `get`'s own re-derivation of the exact same
                # check — this `else` is almost the entire row volume of a gather.
                vp[i] = source.get_unchecked(index)
                mp[i] = True

    parallelize[gather_worker](workers)
    # Keep `indices` alive past the join: the closure captured its raw pointer, and
    # Mojo destroys a value after its last USE, which `unsafe_ptr()` is not.
    _ = len(indices)

    return float64_with_nulls(values^, mask)


fn materialize(
    left: RecordBatch,
    right: RecordBatch,
    result: JoinResult,
    right_name_prefix: String,
) -> RecordBatch:
    """Build the joined batch: every left column then every right column.

    Right column names get `right_name_prefix` so a self-join or a shared column name
    does not produce two columns answering to the same name — `Schema.index_of` returns
    the first match, so a collision would silently resolve every reference to the left
    one.

    Unmatched right rows are NO_ROW, which `take_column` renders as a null. That is why
    an outer join needs no separate materialization path.

    The gather itself runs through `_take_column_join`, which fans out over output-row
    bands above `JOIN_GATHER_PARALLEL_MIN_ROWS` and calls `take_column` directly,
    unmodified, below it — see the module docstring's "Parallel probe and gather"
    section.
    """
    var columns = List[Float64Array]()
    var names = List[String]()
    var dtypes = List[Int]()

    for c in range(left.width()):
        columns.append(_take_column_join(left.columns[c], result.left_rows))
        names.append(left.schema.name_at(c))
        dtypes.append(left.schema.dtype_at(c))
    for c in range(right.width()):
        columns.append(_take_column_join(right.columns[c], result.right_rows))
        names.append(right_name_prefix + right.schema.name_at(c))
        dtypes.append(right.schema.dtype_at(c))

    return RecordBatch(Schema(names^, dtypes^), columns^, result.n_rows())


fn hash_join(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
    right_name_prefix: String,
) -> RecordBatch:
    return materialize(
        left,
        right,
        hash_join_indices(left, left_key_column, right, right_key_column, join_type),
        right_name_prefix,
    )


fn merge_join(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
    right_name_prefix: String,
) raises -> RecordBatch:
    return materialize(
        left,
        right,
        merge_join_indices(left, left_key_column, right, right_key_column, join_type),
        right_name_prefix,
    )


fn join_output_rows(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    join_type: Int,
) -> Int:
    """How many rows `hash_join_indices` WOULD emit, allocating nothing per output row.

    This exists because a join is the one operator whose output can be enormously larger
    than its input, and `hash_join_indices` allocates two Ints per output row before
    there is any result to inspect. Two side tables of 30,000 rows sharing one key fit in
    a ~1 MB request and ask for 9e8 output rows — 14 GB of index lists — so a caller
    bounding the RESULT is bounding something that never exists. The frame cap bounds the
    input and says nothing about the product.

    So the size check needs the count BEFORE the join. One extra O(n+m) pass is the price
    of not turning a 1 MB request into a multi-terabyte allocation, and a plan skips it
    entirely whenever `left.n_rows * right.n_rows` is already under the cap — which is
    every small join.

    Right chains are measured ONCE (total work: one visit per right row) rather than
    re-walked per probing left row. Walking the chain per left row would cost as many
    steps as the join it is protecting against, which would defeat the point.

    Counts exactly what `hash_join_indices` emits, including a LEFT join's one row per
    unmatched or null-key left row. `merge_join_indices` documents that its output
    matches `hash_join_indices` row for row, so this is the count for `merge` too.
    """
    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

    var slot_of = HashIndex(64)
    var first_row = List[Int]()
    var next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, first_row, next_row)

    var chain_length = List[Int]()
    for s in range(len(first_row)):
        var r = first_row[s]
        var length = 0
        while r != NO_ROW:
            length += 1
            r = next_row[r]
        chain_length.append(length)

    var total = 0
    for l in range(left.n_rows):
        if not is_matchable_key(left_key, l):
            # An unknown key equals nothing and a NaN equals nothing — through the SAME
            # predicate the join itself uses, so this count cannot drift from the join's
            # actual output. A looser check here would under-count and let the join it is
            # protecting allocate past the cap.
            if join_type == JOIN_LEFT:
                total += 1
            continue
        var slot = slot_of.find(left_key.get_unchecked(l))
        if slot < 0:
            if join_type == JOIN_LEFT:
                total += 1
            continue
        total += chain_length[slot]
    return total


fn semi_join_indices(
    left: RecordBatch,
    left_key_column: Int,
    right: RecordBatch,
    right_key_column: Int,
    keep_matching: Bool,
) -> List[Int]:
    """Left rows that have (or lack) a partner. One row out per row in, never more.

    `keep_matching=True` is EXISTS, `False` is NOT EXISTS. Distinct from a join because
    it cannot multiply rows: `EXISTS` over three partners is still one row, and getting
    three is the classic accidental fan-out.

    A null left key satisfies neither: it does not match, and it is not *known* not to
    match. It is excluded from both, which is what SQL's `NOT IN` with nulls does and
    the reason that construct surprises people. A NaN key is excluded from both for the
    same reason, through the same `is_matchable_key` predicate — `x = NaN` is UNKNOWN in
    SQL exactly as `x = NULL` is, so `len(semi) + len(anti)` counts neither.
    """
    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

    var slot_of = HashIndex(64)
    var first_row = List[Int]()
    var next_row = List[Int]()
    _ = _build_right_index(right_key, right.n_rows, slot_of, first_row, next_row)

    var out = List[Int]()
    for l in range(left.n_rows):
        if not is_matchable_key(left_key, l):
            continue
        var found = slot_of.find(left_key.get_unchecked(l)) >= 0
        if found == keep_matching:
            out.append(l)
    return out^
