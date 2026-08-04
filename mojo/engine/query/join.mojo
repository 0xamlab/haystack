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

`_build_right_index` (the table build over the right side) and `merge_join_indices`
are UNCHANGED by this — the build mutates one shared table per right row rather than
touching independent rows, and no H2O join-track question exercises `merge_join`. Both
are documented as separate, harder follow-on work, not attempted here.
"""
from std.algorithm.functional import parallelize
from std.sys import info

from columnar.array import Float64Array, float64_with_nulls
from columnar.batch import RecordBatch, Schema, take_column
from columnar.hash_index import HashIndex

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
    var value = column.get(row)
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
        var slot = slot_of.get_or_assign(right_key.get(r), next_slot)
        if slot == next_slot:
            first_row.append(r)
            last_row.append(r)
        else:
            next_row[last_row[slot]] = r
            last_row[slot] = r
    return null_keys


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

        var slot = slot_of.find(left_key.get(l))
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
            var slot = slot_of.find(left_key.get(l))
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
            var slot = slot_of.find(left_key.get(l))
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

    The build stays serial (`_build_right_index`); the probe fans out over left-row
    bands above `JOIN_PROBE_PARALLEL_MIN_ROWS` — see the module docstring's "Parallel
    probe and gather" section and `_hash_join_probe`'s own dispatch.
    """
    var left_key = left.column(left_key_column)
    var right_key = right.column(right_key_column)

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
        var value = key.get(r)
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

        var lv = left_key.get(l)

        # The left run FIRST, and starting at l + 1: row `l` belongs to its own run by
        # definition rather than by comparison, so `left_run_end > l` unconditionally and
        # every `l = left_run_end` below is real progress. Measuring the left run before
        # touching the right side is what decouples termination from the comparisons.
        var left_run_end = l + 1
        while (
            left_run_end < left.n_rows
            and is_matchable_key(left_key, left_run_end)
            and left_key.get(left_run_end) == lv
        ):
            left_run_end += 1

        # Advance the right cursor to the first row that could match. An unusable right
        # key stops the scan outright rather than being skipped past: nulls and NaNs are
        # last, so one here means there is nothing matchable left. `lv` is a real number
        # by now, so this `<` is a genuine ordering test.
        while (
            r < right.n_rows
            and is_matchable_key(right_key, r)
            and right_key.get(r) < lv
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
            or not (right_key.get(r) == lv)
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
            and right_key.get(run_end) == lv
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
                vp[i] = source.get(index)
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
        var slot = slot_of.find(left_key.get(l))
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
        var found = slot_of.find(left_key.get(l)) >= 0
        if found == keep_matching:
            out.append(l)
    return out^
